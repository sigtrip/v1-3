import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.connectivity.bluetooth_scanner import ArgosBluetoothScanner, DeviceType as BTDeviceType
import src.connectivity.iot_bridge as iot_bridge_module
from src.connectivity.iot_bridge import (
    IoTBridge,
    IoTRegistry,
    LoRaAdapter,
    MeshAdapter,
    TasmotaDiscoveryBridge,
    ZigbeeAdapter,
)
from src.connectivity.usb_diagnostics import USBDiagnostics


class _DummyMsg:
    def __init__(self, topic: str, payload: dict):
        self.topic = topic
        self.payload = json.dumps(payload).encode("utf-8")


class TestDeviceDiscovery(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="argos_discovery_")
        self.tmp_path = Path(self.tmp.name)
        self.devices_file = self.tmp_path / "iot_devices.json"
        self.db_path = self.tmp_path / "argos_iot.sqlite3"

        self.devices_patch = patch.object(iot_bridge_module, "DEVICES_FILE", str(self.devices_file))
        self.db_patch = patch.object(iot_bridge_module, "IOT_DB_PATH", str(self.db_path))
        self.devices_patch.start()
        self.db_patch.start()

    def tearDown(self):
        self.db_patch.stop()
        self.devices_patch.stop()
        self.tmp.cleanup()

    def test_zigbee_message_auto_registers_device(self):
        registry = IoTRegistry()
        adapter = ZigbeeAdapter(registry)

        msg = _DummyMsg("zigbee2mqtt/kitchen_sensor", {"temp": 23.4, "humidity": 40})
        adapter._on_mqtt_message(None, None, msg)

        device = registry.get("zb_kitchen_sensor")
        self.assertIsNotNone(device)
        self.assertEqual(device.protocol, "zigbee")
        self.assertEqual(device.state.get("temp"), 23.4)
        self.assertEqual(device.state.get("humidity"), 40)

    def test_lora_packet_auto_registers_and_parses_metrics(self):
        registry = IoTRegistry()
        adapter = LoRaAdapter(registry)

        adapter._parse_lora_packet("12", "temp:21.5,soil:78")

        device = registry.get("lora_12")
        self.assertIsNotNone(device)
        self.assertEqual(device.protocol, "lora")
        self.assertEqual(device.state.get("temp"), 21.5)
        self.assertEqual(device.state.get("soil"), 78.0)

    def test_mesh_packet_auto_registers_device(self):
        registry = IoTRegistry()
        adapter = MeshAdapter(registry)

        packet = {
            "id": "nodeA",
            "type": "sensor",
            "name": "MeshNodeA",
            "data": {"co2": 540, "temp": 24.1},
        }
        adapter._parse_packet(json.dumps(packet).encode("utf-8"), "192.168.1.20")

        device = registry.get("mesh_nodeA")
        self.assertIsNotNone(device)
        self.assertEqual(device.protocol, "mesh")
        self.assertEqual(device.address, "192.168.1.20")
        self.assertEqual(device.state.get("co2"), 540)
        self.assertEqual(device.state.get("temp"), 24.1)

    def test_tasmota_discovery_registers_and_persists_metadata(self):
        registry = IoTRegistry()
        bridge = TasmotaDiscoveryBridge(registry=registry, db_path=str(self.db_path))

        payload = {
            "name": "Boiler Relay",
            "state_topic": "stat/tasmota_A1B2/POWER",
            "command_topic": "cmnd/tasmota_A1B2/POWER",
            "device": {
                "identifiers": ["A1B2C3"],
                "manufacturer": "Tasmota",
                "model": "Sonoff Basic",
            },
        }
        msg = _DummyMsg("homeassistant/switch/tasmota_A1B2_power/config", payload)

        bridge._on_message(None, None, msg)

        device = registry.get("tasmota_a1b2c3")
        self.assertIsNotNone(device)
        self.assertEqual(device.type, "actuator")
        self.assertEqual(device.protocol, "mqtt")
        self.assertIn("manufacturer", device.state)

        conn = sqlite3.connect(str(self.db_path))
        row = conn.execute(
            "SELECT device_id, component FROM iot_devices WHERE device_id=?",
            ("tasmota_a1b2c3",),
        ).fetchone()
        conn.close()

        self.assertIsNotNone(row)
        self.assertEqual(row[0], "tasmota_a1b2c3")
        self.assertEqual(row[1], "switch")

    def test_bluetooth_identification_for_iot_device(self):
        inventory_path = self.tmp_path / "bt_inventory.json"
        scanner = ArgosBluetoothScanner(inventory_path=str(inventory_path))

        scanner._process_device(
            address="24:6F:28:AA:BB:CC",
            name="ESP Sensor Node",
            rssi=-62,
            is_ble=True,
            services=["0000181a-0000-1000-8000-00805f9b34fb"],
        )

        iot_devices = scanner.get_iot_devices()
        self.assertEqual(len(iot_devices), 1)
        self.assertEqual(iot_devices[0].device_type, BTDeviceType.IOT_SENSOR)
        self.assertEqual(iot_devices[0].manufacturer, "ESP32")

    def test_usb_vid_pid_detection(self):
        usb = USBDiagnostics(android_mode=False)

        device_type = usb._detect_device_type(0x303A, 0x1001)
        self.assertEqual(device_type, "esp32")

    def test_gateway_lookup_by_ip_and_mac(self):
        with patch.dict("os.environ", {"ARGOS_TASMOTA_DISCOVERY": "off"}, clear=False):
            bridge = IoTBridge()

        reg_result = bridge.register_gateway(
            dev_id="gw_zb_01",
            protocol="zigbee",
            ip="192.168.1.55",
            mac="aa-bb-cc-dd-ee-ff",
            name="Zigbee Gateway Home",
        )
        self.assertIn("✅", reg_result)

        by_ip = bridge.device_status("192.168.1.55")
        self.assertIn("gw_zb_01", by_ip)

        by_mac = bridge.device_status("AA:BB:CC:DD:EE:FF")
        self.assertIn("Zigbee Gateway Home", by_mac)


if __name__ == "__main__":
    unittest.main()
