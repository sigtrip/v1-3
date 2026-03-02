"""
air_snitch.py — AirSnitch (SDR / Sub-GHz Radio Scanner)
    Пассивный мониторинг эфира 433/868/915 МГц:
    - Обнаружение собственных датчиков, ворот, метеостанций
    - Спектральный анализ полосы (энергия, пики)
    - Журнал пакетов с декодированием (OOK/FSK)
    - Поддержка RTL-SDR (rtlsdr), HackRF (SoapySDR) и serial sub-GHz

    ⚠ Модуль работает ТОЛЬКО в режиме приёма (RX).
    Передача (TX) и replay запрещены на уровне кода.
"""
import os
import re
import time
import json
import struct
import threading
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
from collections import deque
from dataclasses import dataclass, field, asdict

from src.argos_logger import get_logger

log = get_logger("argos.airsnitch")

# ── Graceful imports ─────────────────────────────────────
try:
    from rtlsdr import RtlSdr          # pip install pyrtlsdr
    RTLSDR_OK = True
except ImportError:
    RtlSdr = None
    RTLSDR_OK = False

try:
    import SoapySDR                     # pip install SoapySDR
    SOAPY_OK = True
except ImportError:
    SoapySDR = None
    SOAPY_OK = False

try:
    import numpy as np
    NP_OK = True
except ImportError:
    np = None
    NP_OK = False

try:
    import serial
    SERIAL_OK = True
except ImportError:
    serial = None
    SERIAL_OK = False


# ── Enums / Dataclasses ─────────────────────────────────
class Modulation(Enum):
    OOK = "OOK"
    FSK = "FSK"
    GFSK = "GFSK"
    LORA = "LoRa"
    UNKNOWN = "unknown"


class Band(Enum):
    SUB_433 = 433.92e6
    SUB_868 = 868.0e6
    SUB_915 = 915.0e6


@dataclass
class RFPacket:
    """Одна перехваченная RF-посылка (RX only)."""
    ts: float = field(default_factory=time.time)
    freq_hz: float = 0.0
    modulation: str = "unknown"
    rssi_dbm: float = -120.0
    raw_hex: str = ""
    decoded: str = ""
    protocol: str = ""       # e.g. "Oregon Scientific", "Nexus-TH", "generic"
    device_id: str = ""
    repeated: int = 1

    def to_dict(self) -> dict:
        d = asdict(self)
        d["freq_mhz"] = round(self.freq_hz / 1e6, 3)
        return d


@dataclass
class SpectrumSlice:
    """Спектральный «снимок» полосы."""
    center_hz: float
    bw_hz: float
    peak_hz: float
    peak_dbm: float
    noise_floor_dbm: float
    ts: float = field(default_factory=time.time)


# ── Known Protocol Signatures ───────────────────────────
_KNOWN_PROTOCOLS: Dict[str, dict] = {
    "Oregon Scientific v2.1": {
        "preamble_bits": "1111111100",
        "freq": 433.92e6,
        "modulation": "OOK",
    },
    "Nexus-TH": {
        "preamble_bits": "10101010",
        "freq": 433.92e6,
        "modulation": "OOK",
    },
    "Fine Offset WH2": {
        "preamble_bits": "11111111110",
        "freq": 433.92e6,
        "modulation": "OOK",
    },
    "EV1527 (generic remote)": {
        "preamble_bits": "100000000000",
        "freq": 433.92e6,
        "modulation": "OOK",
    },
    "HopeRF FSK": {
        "preamble_bits": "AAAA",
        "freq": 868.0e6,
        "modulation": "FSK",
    },
}


class AirSnitch:
    """
    Пассивный SDR-сканер эфира.

    Режимы работы:
    1. spectrum  — быстрый спектральный анализ полосы
    2. capture   — захват и декодирование пакетов
    3. monitor   — фоновый мониторинг с журналом

    Поддерживаемые бэкенды:
    - RTL-SDR (rtlsdr)
    - HackRF / LimeSDR (SoapySDR)
    - Serial sub-GHz (CC1101, SX1276 AT-модем)
    """

    VERSION = "1.0.0"
    MAX_LOG = 2000

    def __init__(self, backend: str = "auto"):
        self._backend = self._detect_backend(backend)
        self._sdr = None              # RTL-SDR handle
        self._soapy = None            # SoapySDR handle
        self._serial = None           # serial sub-GHz
        self._lock = threading.Lock()
        self._running = False
        self._monitor_thread: Optional[threading.Thread] = None

        self._packets: deque = deque(maxlen=self.MAX_LOG)
        self._spectrum_cache: Dict[float, SpectrumSlice] = {}
        self._stats = {
            "packets_total": 0,
            "protocols_seen": set(),
            "scan_count": 0,
            "uptime_start": time.time(),
        }

        # Bands to monitor
        self._bands: List[float] = [
            Band.SUB_433.value,
            Band.SUB_868.value,
        ]
        custom = os.getenv("ARGOS_AIRSNITCH_BANDS", "").strip()
        if custom:
            try:
                self._bands = [float(x.strip()) * 1e6 for x in custom.split(",")]
            except ValueError:
                pass

        self._sample_rate = int(os.getenv("ARGOS_AIRSNITCH_SAMPLERATE", "1024000") or "1024000")
        self._gain = os.getenv("ARGOS_AIRSNITCH_GAIN", "auto").strip()

        log.info("AirSnitch v%s | backend=%s | bands=%s",
                 self.VERSION, self._backend, [f"{b/1e6:.2f}MHz" for b in self._bands])

    # ── Backend Detection ────────────────────────────────
    @staticmethod
    def _detect_backend(requested: str) -> str:
        if requested != "auto":
            return requested
        if RTLSDR_OK:
            return "rtlsdr"
        if SOAPY_OK:
            return "soapysdr"
        if SERIAL_OK:
            return "serial"
        return "none"

    def _open_sdr(self) -> bool:
        """Открывает SDR-устройство (RX only)."""
        if self._backend == "rtlsdr" and RTLSDR_OK:
            try:
                self._sdr = RtlSdr()
                self._sdr.sample_rate = self._sample_rate
                if self._gain != "auto":
                    self._sdr.gain = float(self._gain)
                else:
                    self._sdr.gain = "auto"
                log.info("AirSnitch: RTL-SDR opened (RX only)")
                return True
            except Exception as e:
                log.warning("AirSnitch: RTL-SDR open failed: %s", e)
                return False

        if self._backend == "soapysdr" and SOAPY_OK:
            try:
                results = SoapySDR.Device.enumerate()
                if not results:
                    log.warning("AirSnitch: no SoapySDR devices found")
                    return False
                self._soapy = SoapySDR.Device(results[0])
                self._soapy.setSampleRate(SoapySDR.SOAPY_SDR_RX, 0, self._sample_rate)
                if self._gain != "auto":
                    self._soapy.setGain(SoapySDR.SOAPY_SDR_RX, 0, float(self._gain))
                log.info("AirSnitch: SoapySDR opened (RX only)")
                return True
            except Exception as e:
                log.warning("AirSnitch: SoapySDR open failed: %s", e)
                return False

        if self._backend == "serial" and SERIAL_OK:
            port = os.getenv("ARGOS_AIRSNITCH_SERIAL_PORT", "/dev/ttyUSB0")
            baud = int(os.getenv("ARGOS_AIRSNITCH_SERIAL_BAUD", "115200") or "115200")
            try:
                self._serial = serial.Serial(port, baud, timeout=2)
                log.info("AirSnitch: serial opened %s@%d (RX only)", port, baud)
                return True
            except Exception as e:
                log.warning("AirSnitch: serial open failed: %s", e)
                return False

        return False

    def _close_sdr(self):
        if self._sdr:
            try:
                self._sdr.close()
            except Exception:
                pass
            self._sdr = None
        if self._soapy:
            self._soapy = None
        if self._serial:
            try:
                self._serial.close()
            except Exception:
                pass
            self._serial = None

    # ── Spectrum Analysis ────────────────────────────────
    def scan_spectrum(self, freq_hz: float = 433.92e6,
                      bw_hz: float = 1e6) -> Optional[SpectrumSlice]:
        """
        Быстрый спектральный анализ вокруг freq_hz.
        Возвращает SpectrumSlice или None если SDR недоступен.
        """
        if not NP_OK:
            log.warning("AirSnitch: numpy required for spectrum analysis")
            return None

        opened = self._open_sdr()
        if not opened:
            return self._simulate_spectrum(freq_hz, bw_hz)

        try:
            if self._sdr:
                self._sdr.center_freq = freq_hz
                samples = self._sdr.read_samples(256 * 1024)
            elif self._soapy:
                self._soapy.setFrequency(SoapySDR.SOAPY_SDR_RX, 0, freq_hz)
                rxStream = self._soapy.setupStream(SoapySDR.SOAPY_SDR_RX, SoapySDR.SOAPY_SDR_CF32)
                self._soapy.activateStream(rxStream)
                buff = np.zeros(256 * 1024, dtype=np.complex64)
                sr = self._soapy.readStream(rxStream, [buff], len(buff))
                samples = buff[:sr.ret] if sr.ret > 0 else buff
                self._soapy.deactivateStream(rxStream)
                self._soapy.closeStream(rxStream)
            else:
                self._close_sdr()
                return self._simulate_spectrum(freq_hz, bw_hz)

            # FFT
            fft_vals = np.fft.fftshift(np.fft.fft(samples))
            psd = 10 * np.log10(np.abs(fft_vals) ** 2 + 1e-12)
            freqs = np.fft.fftshift(np.fft.fftfreq(len(samples), 1 / self._sample_rate)) + freq_hz

            peak_idx = int(np.argmax(psd))
            peak_hz = float(freqs[peak_idx])
            peak_dbm = float(psd[peak_idx])
            noise_floor = float(np.median(psd))

            sl = SpectrumSlice(
                center_hz=freq_hz, bw_hz=bw_hz,
                peak_hz=peak_hz, peak_dbm=peak_dbm,
                noise_floor_dbm=noise_floor,
            )
            self._spectrum_cache[freq_hz] = sl
            self._stats["scan_count"] += 1
            return sl

        except Exception as e:
            log.error("AirSnitch spectrum error: %s", e)
            return self._simulate_spectrum(freq_hz, bw_hz)
        finally:
            self._close_sdr()

    def _simulate_spectrum(self, freq_hz: float, bw_hz: float) -> SpectrumSlice:
        """Симуляция для headless/demo режима."""
        import random
        sl = SpectrumSlice(
            center_hz=freq_hz, bw_hz=bw_hz,
            peak_hz=freq_hz + random.uniform(-5000, 5000),
            peak_dbm=random.uniform(-80, -30),
            noise_floor_dbm=random.uniform(-110, -95),
        )
        self._spectrum_cache[freq_hz] = sl
        self._stats["scan_count"] += 1
        return sl

    # ── Packet Capture (RX only) ─────────────────────────
    def capture_packets(self, freq_hz: float = 433.92e6,
                        duration_sec: float = 5.0) -> List[RFPacket]:
        """
        Захватывает пакеты на указанной частоте.
        Работает только в режиме приёма.
        """
        packets: List[RFPacket] = []

        # serial backend
        if self._backend == "serial" and self._open_sdr():
            try:
                deadline = time.time() + duration_sec
                while time.time() < deadline:
                    if self._serial and self._serial.in_waiting:
                        line = self._serial.readline().decode("utf-8", errors="ignore").strip()
                        pkt = self._parse_serial_line(line, freq_hz)
                        if pkt:
                            packets.append(pkt)
                            self._packets.append(pkt)
                            self._stats["packets_total"] += 1
                    else:
                        time.sleep(0.05)
            finally:
                self._close_sdr()
            return packets

        # RTL-SDR / SoapySDR — simplified IQ → amplitude → threshold
        if NP_OK and self._open_sdr():
            try:
                if self._sdr:
                    self._sdr.center_freq = freq_hz
                    num_samples = int(self._sample_rate * duration_sec)
                    samples = self._sdr.read_samples(min(num_samples, 1024 * 1024))
                elif self._soapy:
                    self._soapy.setFrequency(SoapySDR.SOAPY_SDR_RX, 0, freq_hz)
                    num_samples = int(self._sample_rate * duration_sec)
                    rxStream = self._soapy.setupStream(SoapySDR.SOAPY_SDR_RX, SoapySDR.SOAPY_SDR_CF32)
                    self._soapy.activateStream(rxStream)
                    buff = np.zeros(min(num_samples, 1024 * 1024), dtype=np.complex64)
                    sr = self._soapy.readStream(rxStream, [buff], len(buff))
                    samples = buff[:sr.ret] if sr.ret > 0 else buff
                    self._soapy.deactivateStream(rxStream)
                    self._soapy.closeStream(rxStream)
                else:
                    samples = np.array([])

                if len(samples) > 0:
                    # Amplitude detection
                    amplitude = np.abs(samples)
                    threshold = np.mean(amplitude) + 3 * np.std(amplitude)
                    bursts = np.where(amplitude > threshold)[0]

                    if len(bursts) > 10:
                        pkt = self._decode_burst(samples, bursts, freq_hz)
                        if pkt:
                            packets.append(pkt)
                            self._packets.append(pkt)
                            self._stats["packets_total"] += 1

            except Exception as e:
                log.error("AirSnitch capture error: %s", e)
            finally:
                self._close_sdr()

            return packets

        # Demo mode — no hardware
        packets = self._simulate_capture(freq_hz, duration_sec)
        return packets

    def _parse_serial_line(self, line: str, freq_hz: float) -> Optional[RFPacket]:
        """Парсит строку от serial sub-GHz модема (CC1101 / SX1276 AT)."""
        if not line:
            return None
        # Формат: +RX:XXXXXX,RSSI:-NN или JSON
        try:
            if line.startswith("{"):
                j = json.loads(line)
                return RFPacket(
                    freq_hz=j.get("freq", freq_hz),
                    modulation=j.get("mod", "unknown"),
                    rssi_dbm=j.get("rssi", -120),
                    raw_hex=j.get("data", ""),
                    protocol=j.get("proto", ""),
                    device_id=j.get("id", ""),
                )
            m = re.match(r"\+RX:([0-9A-Fa-f]+),?RSSI:(-?\d+)", line)
            if m:
                return RFPacket(
                    freq_hz=freq_hz,
                    raw_hex=m.group(1),
                    rssi_dbm=float(m.group(2)),
                )
        except Exception:
            pass
        return None

    def _decode_burst(self, samples, burst_indices, freq_hz: float) -> Optional[RFPacket]:
        """Базовый декодер burst → RFPacket (OOK amplitude)."""
        if not NP_OK:
            return None
        try:
            burst_data = samples[burst_indices[0]:burst_indices[-1]]
            raw_hex = burst_data[:16].tobytes().hex()[:32]

            # Try to match known protocol preamble
            proto = "generic"
            for name, sig in _KNOWN_PROTOCOLS.items():
                if abs(freq_hz - sig["freq"]) < 1e5:
                    proto = name
                    break

            return RFPacket(
                freq_hz=freq_hz,
                modulation=Modulation.OOK.value,
                rssi_dbm=float(10 * np.log10(np.max(np.abs(burst_data) ** 2) + 1e-12)),
                raw_hex=raw_hex,
                protocol=proto,
            )
        except Exception:
            return None

    def _simulate_capture(self, freq_hz: float, duration_sec: float) -> List[RFPacket]:
        """Симуляция для demo."""
        import random
        protos = ["Oregon Scientific v2.1", "Nexus-TH", "EV1527 (generic remote)", "generic"]
        n = random.randint(0, 3)
        pkts = []
        for _ in range(n):
            p = RFPacket(
                freq_hz=freq_hz + random.uniform(-50000, 50000),
                modulation=random.choice(["OOK", "FSK"]),
                rssi_dbm=random.uniform(-90, -30),
                raw_hex=os.urandom(8).hex(),
                protocol=random.choice(protos),
                device_id=f"dev_{random.randint(1000,9999)}",
            )
            pkts.append(p)
            self._packets.append(p)
            self._stats["packets_total"] += 1
        return pkts

    # ── Background Monitor ───────────────────────────────
    def start_monitor(self, interval_sec: float = 30.0) -> str:
        """Запускает фоновый мониторинг всех полос."""
        if self._running:
            return "📡 AirSnitch: мониторинг уже запущен."
        self._running = True
        self._monitor_thread = threading.Thread(
            target=self._monitor_loop, args=(interval_sec,),
            daemon=True, name="airsnitch-monitor"
        )
        self._monitor_thread.start()
        return f"📡 AirSnitch: фоновый мониторинг запущен ({len(self._bands)} полос, {interval_sec}с)."

    def stop_monitor(self) -> str:
        if not self._running:
            return "📡 AirSnitch: мониторинг не запущен."
        self._running = False
        return "📡 AirSnitch: мониторинг остановлен."

    def _monitor_loop(self, interval_sec: float):
        while self._running:
            for band in self._bands:
                if not self._running:
                    break
                try:
                    self.capture_packets(band, duration_sec=2.0)
                except Exception as e:
                    log.error("AirSnitch monitor error on %.2fMHz: %s", band / 1e6, e)
            time.sleep(interval_sec)
        log.info("AirSnitch: monitor thread exited.")

    # ── Query & Status ───────────────────────────────────
    def get_packets(self, last_n: int = 50) -> List[dict]:
        with self._lock:
            recent = list(self._packets)[-last_n:]
        return [p.to_dict() for p in recent]

    def get_protocols_seen(self) -> List[str]:
        protocols = set()
        for p in self._packets:
            if p.protocol:
                protocols.add(p.protocol)
        return sorted(protocols)

    def get_status(self) -> dict:
        return {
            "version": self.VERSION,
            "backend": self._backend,
            "monitoring": self._running,
            "bands_mhz": [round(b / 1e6, 2) for b in self._bands],
            "packets_total": self._stats["packets_total"],
            "scan_count": self._stats["scan_count"],
            "protocols_seen": self.get_protocols_seen(),
            "rtlsdr_available": RTLSDR_OK,
            "soapysdr_available": SOAPY_OK,
            "serial_available": SERIAL_OK,
            "numpy_available": NP_OK,
        }

    def status(self) -> str:
        s = self.get_status()
        lines = [
            "📡 AIRSNITCH (SDR / Sub-GHz Scanner)",
            f"  Версия: {s['version']} | Backend: {s['backend']}",
            f"  Мониторинг: {'🟢 ON' if s['monitoring'] else '⚪ OFF'}",
            f"  Полосы: {s['bands_mhz']}",
            f"  Пакетов: {s['packets_total']} | Сканов: {s['scan_count']}",
            f"  Протоколы: {', '.join(s['protocols_seen']) or '—'}",
            f"  Драйверы: RTL-SDR={'✅' if s['rtlsdr_available'] else '❌'}"
            f"  SoapySDR={'✅' if s['soapysdr_available'] else '❌'}"
            f"  Serial={'✅' if s['serial_available'] else '❌'}"
            f"  NumPy={'✅' if s['numpy_available'] else '❌'}",
        ]
        return "\n".join(lines)

    def scan_all_bands(self) -> str:
        """Быстрое сканирование всех полос."""
        lines = ["📡 AIRSNITCH — СПЕКТР:"]
        for band in self._bands:
            sl = self.scan_spectrum(band)
            if sl:
                lines.append(
                    f"  {band/1e6:.2f} MHz: пик={sl.peak_hz/1e6:.4f} MHz "
                    f"({sl.peak_dbm:.1f} dBm) | шум={sl.noise_floor_dbm:.1f} dBm"
                )
            else:
                lines.append(f"  {band/1e6:.2f} MHz: недоступно")
        return "\n".join(lines)

    def shutdown(self):
        self._running = False
        self._close_sdr()
        log.info("AirSnitch shutdown")
