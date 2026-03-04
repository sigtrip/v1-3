import unittest

from src.connectivity.bacnet_bridge import BACnetBridge
from src.connectivity.bacnet_bridge import BACnetBridge


class TestBACnetBridge(unittest.TestCase):
    def setUp(self):
        self.bridge = BACnetBridge()

    def test_register_and_status(self):
        result = self.bridge.register_device(1001, "192.168.1.10", name="Boiler")
        self.assertIn("✅", result)
        status = self.bridge.status()
        self.assertIn("#1001", status)
        self.assertIn("Boiler", status)

    def test_sim_read_write_roundtrip(self):
        self.bridge.register_device(1002, "192.168.1.11", name="Pump")
        write_result = self.bridge.write_property(1002, "analogValue", 1, "presentValue", 42.5)
        self.assertIn("✅", write_result)
        read_result = self.bridge.read_property(1002, "analogValue", 1, "presentValue")
        self.assertIn("42.5", read_result)

    def test_scan_sim_mode(self):
        self.bridge.register_device(1003, "192.168.1.12")
        scan_result = self.bridge.scan()
        self.assertIn("BACnet", scan_result)
        self.assertIn("1003", scan_result)


if __name__ == "__main__":
    unittest.main()
