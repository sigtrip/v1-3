"""
bootloader_manager.py — Управление загрузчиком (своё устройство)
  Windows: bcdedit, EFI entries
  Linux:   GRUB, systemd-boot, EFI
  Android: fastboot, TWRP
  ⚠️  Все операции требуют явного подтверждения.
"""
import json
import os
import platform
import subprocess
import sys

OS = platform.system()

CONFIRM_CODE = "ARGOS-BOOT-CONFIRM"


class BootloaderManager:
    def __init__(self):
        self.os_type    = OS
        self.is_android = "ANDROID_ROOT" in os.environ
        self._confirmed = False

    # ── Подтверждение ────────────────────────────────────
    def confirm(self, code: str) -> str:
        if code.strip().upper() == CONFIRM_CODE:
            self._confirmed = True
            return "✅ Подтверждение принято. Операции с загрузчиком разблокированы."
        return (f"⚠️ Введи код: {CONFIRM_CODE}\n"
                f"  Команда: подтверди {CONFIRM_CODE}")

    def _require_confirm(self) -> str | None:
        if not self._confirmed:
            return (f"🔒 Заблокировано. Требуется подтверждение.\n"
                    f"  Введи: подтверди {CONFIRM_CODE}")
        return None

    # ── Информация о загрузчике ──────────────────────────
    def get_boot_info(self) -> str:
        if self.is_android: return self._android_boot_info()
        if self.os_type == "Windows": return self._windows_boot_info()
        return self._linux_boot_info()

    def _windows_boot_info(self) -> str:
        try:
            r = subprocess.run(["bcdedit", "/enum", "all"],
                               capture_output=True, text=True, encoding="cp866")
            efi = self._check_windows_efi()
            lines = r.stdout.strip().split("\n")[:25]
            return (f"🖥️ ЗАГРУЗЧИК Windows:\n"
                    f"  Тип: {'UEFI/EFI' if efi else 'Legacy BIOS/MBR'}\n\n"
                    + "\n".join(lines))
        except Exception as e:
            return f"❌ bcdedit недоступен: {e}"

    def _check_windows_efi(self) -> bool:
        try:
            r = subprocess.run(["bcdedit", "/enum", "firmware"], capture_output=True)
            return r.returncode == 0
        except Exception:
            return False

    def _linux_boot_info(self) -> str:
        lines = ["🐧 ЗАГРУЗЧИК Linux:"]
        is_efi = os.path.exists("/sys/firmware/efi")
        lines.append(f"  Тип: {'UEFI/EFI' if is_efi else 'Legacy BIOS'}")
        if is_efi:
            try:
                r = subprocess.run(["efibootmgr", "-v"], capture_output=True, text=True)
                lines.append("\n📋 EFI записи:")
                lines.extend("  " + l for l in r.stdout.split("\n")[:20])
            except FileNotFoundError:
                lines.append("  (efibootmgr не установлен: sudo apt install efibootmgr)")
        for grub in ["/boot/grub/grub.cfg", "/boot/grub2/grub.cfg"]:
            if os.path.exists(grub):
                lines.append(f"\n✅ GRUB: {grub}"); break
        else:
            lines.append("\n⚠️ GRUB конфиг не найден")
        return "\n".join(lines)

    def _android_boot_info(self) -> str:
        lines = ["📱 Android ЗАГРУЗЧИК:"]
        for prop in ["ro.bootloader", "ro.boot.verifiedbootstate"]:
            try:
                r = subprocess.run(["getprop", prop], capture_output=True, text=True)
                lines.append(f"  {prop}: {r.stdout.strip()}")
            except Exception:
                pass
        try:
            r = subprocess.run(["getprop", "ro.boot.flash.locked"],
                                capture_output=True, text=True)
            locked = r.stdout.strip() == "1"
            lines.append(f"  Загрузчик: {'🔒 Заблокирован' if locked else '🔓 Разблокирован'}")
        except Exception:
            pass
        return "\n".join(lines)

    # ── Windows BCD ──────────────────────────────────────
    def windows_add_boot_entry(self, label: str, path: str) -> str:
        guard = self._require_confirm()
        if guard: return guard
        try:
            import re
            r = subprocess.run(["bcdedit", "/create", "/d", label,
                                 "/application", "bootsector"],
                                capture_output=True, text=True)
            guid = re.search(r"\{[a-f0-9-]+\}", r.stdout)
            if not guid:
                return f"❌ Не удалось создать BCD-запись:\n{r.stdout}"
            g = guid.group()
            subprocess.run(["bcdedit", "/set", g, "device", f"partition={path}"])
            subprocess.run(["bcdedit", "/set", g, "path", r"\argos\bootmgr"])
            subprocess.run(["bcdedit", "/displayorder", g, "/addlast"])
            return f"✅ BCD запись создана: {label} ({g})"
        except Exception as e:
            return f"❌ BCD: {e}"

    def windows_delete_boot_entry(self, guid: str) -> str:
        guard = self._require_confirm()
        if guard: return guard
        try:
            r = subprocess.run(["bcdedit", "/delete", guid], capture_output=True, text=True)
            return f"✅ BCD запись удалена: {guid}" if r.returncode == 0 else f"❌ {r.stdout}"
        except Exception as e:
            return f"❌ {e}"

    # ── Linux EFI/GRUB ───────────────────────────────────
    def linux_add_efi_entry(self, label: str, disk: str, part: int, loader: str) -> str:
        guard = self._require_confirm()
        if guard: return guard
        try:
            r = subprocess.run(["sudo", "efibootmgr", "-c",
                                 "-d", disk, "-p", str(part),
                                 "-L", label, "-l", loader],
                                capture_output=True, text=True)
            return f"✅ EFI-запись добавлена: {label}" if r.returncode == 0 else f"❌ {r.stderr[:300]}"
        except Exception as e:
            return f"❌ {e}"

    def linux_set_grub_default(self, entry: str) -> str:
        guard = self._require_confirm()
        if guard: return guard
        try:
            subprocess.run(["sudo", "grub-set-default", entry], check=True)
            return f"✅ GRUB по умолчанию: {entry}"
        except Exception as e:
            return f"❌ {e}"

    def linux_add_grub_entry(self, name: str, kernel: str,
                              initrd: str, params: str = "quiet splash") -> str:
        guard = self._require_confirm()
        if guard: return guard
        custom = "/etc/grub.d/40_custom"
        entry  = (f"\nmenuentry \'{name}\' {{\n"
                  f"    linux {kernel} {params}\n"
                  f"    initrd {initrd}\n"
                  f"}}\n")
        try:
            with open(custom, "a") as f:
                f.write(entry)
            subprocess.run(["sudo", "update-grub"])
            return f"✅ GRUB-запись \'{name}\' добавлена"
        except Exception as e:
            return f"❌ {e}"

    # ── Android fastboot ─────────────────────────────────
    def android_fastboot_info(self) -> str:
        try:
            r = subprocess.run(["fastboot", "getvar", "all"],
                                capture_output=True, text=True, timeout=10)
            return f"📱 Fastboot:\n{r.stderr[:500]}"
        except Exception as e:
            return (f"❌ fastboot недоступен: {e}\n"
                    "Устройство должно быть в режиме Fastboot: adb reboot bootloader")

    def android_unlock_bootloader(self) -> str:
        guard = self._require_confirm()
        if guard: return guard
        return (
            "📱 Разблокировка загрузчика Android:\n\n"
            "⚠️ ЭТО СОТРЁТ ВСЕ ДАННЫЕ!\n\n"
            "Шаги:\n"
            "  1. Включи OEM Unlock: Настройки → Для разработчиков\n"
            "  2. adb reboot bootloader\n"
            "  3. fastboot oem unlock  (или fastboot flashing unlock)\n"
            "  4. Подтверди на экране\n"
            "  5. fastboot reboot\n\n"
            "После разблокировки:\n"
            "  → fastboot flash recovery twrp.img\n"
            "  → Устанавливай Magisk для root"
        )

    def android_flash_image(self, partition: str, img_path: str) -> str:
        guard = self._require_confirm()
        if guard: return guard
        if not os.path.exists(img_path):
            return f"❌ Файл не найден: {img_path}"
        safe_parts = {"recovery", "boot", "system", "vendor", "vbmeta"}
        if partition not in safe_parts:
            return f"❌ Раздел \'{partition}\' не в безопасном списке: {safe_parts}"
        try:
            r = subprocess.run(["fastboot", "flash", partition, img_path],
                                capture_output=True, text=True, timeout=120)
            return (f"✅ {partition} прошит: {img_path}"
                    if r.returncode == 0 else f"❌ Fastboot:\n{r.stderr[:300]}")
        except Exception as e:
            return f"❌ {e}"

    # ── Persistence ──────────────────────────────────────
    def install_persistence(self) -> str:
        guard = self._require_confirm()
        if guard: return guard
        results = []
        if self.os_type == "Windows":
            try:
                import winreg
                key = winreg.CreateKey(winreg.HKEY_LOCAL_MACHINE,
                                       r"SYSTEM\CurrentControlSet\Control\EarlyLaunch")
                winreg.CloseKey(key)
                results.append("✅ Windows: Early Launch запись создана")
            except Exception as e:
                results.append(f"⚠️ Early Launch: {e}")
        elif self.os_type == "Linux":
            hook = ("#!/bin/sh\n. /usr/share/initramfs-tools/hook-functions\n"
                    "echo \"[ARGOS]: Pre-mount hook active\" >> /dev/kmsg\n")
            try:
                with open("/tmp/argos_initramfs", "w") as f:
                    f.write(hook)
                subprocess.run(["sudo", "cp", "/tmp/argos_initramfs",
                                 "/etc/initramfs-tools/scripts/init-premount/argos"],
                                capture_output=True)
                subprocess.run(["sudo", "chmod", "+x",
                                 "/etc/initramfs-tools/scripts/init-premount/argos"],
                                capture_output=True)
                subprocess.run(["sudo", "update-initramfs", "-u"], capture_output=True)
                results.append("✅ Linux: initramfs hook установлен (pre-mount уровень)")
            except Exception as e:
                results.append(f"⚠️ initramfs: {e}")
        return "\n".join(results) or "Persistence установлена."

    # ── Полный отчёт ─────────────────────────────────────
    def full_report(self) -> str:
        return (self.get_boot_info() + "\n\n"
                + f"🔒 Подтверждение: {'✅ Активно' if self._confirmed else '❌ Требуется'}\n"
                + f"Для разблокировки: подтверди {CONFIRM_CODE}")
