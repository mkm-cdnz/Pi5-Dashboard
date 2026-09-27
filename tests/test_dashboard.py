import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pi_gpio_dashboard as dashboard


class DashboardDataTests(unittest.TestCase):
    def test_physical_header_map_is_complete(self):
        self.assertEqual([pin.number for pin in dashboard.PINS], list(range(1, 41)))
        self.assertEqual(dashboard.PINS[10].bcm, 17)
        self.assertEqual(dashboard.PINS[10].label, "GPIO17")

    def test_pin_labels_round_trip_and_filter_invalid_data(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "labels.json"
            dashboard.save_pin_labels({11: "LED", 40: "Sensor"}, path)
            self.assertEqual(dashboard.load_pin_labels(path), {11: "LED", 40: "Sensor"})
            path.write_text('{"0":"bad","11":"  LED  ","41":"bad"}', encoding="utf-8")
            self.assertEqual(dashboard.load_pin_labels(path), {11: "LED"})

    def test_nmcli_field_parser_preserves_colons_in_ssid(self):
        self.assertEqual(
            dashboard.split_nmcli_fields(r"*:Workshop\:Lab:78:WPA2"),
            ["*", "Workshop:Lab", "78", "WPA2"],
        )

    def test_bluetooth_list_only_contains_freshly_seen_devices(self):
        def fake_run(args, timeout=1.5):
            if args[0] == "nmcli":
                return "*:Home:80:WPA2\n:Workshop:46:WPA3"
            if "scan" in args:
                return "[NEW] Device AA:BB:CC:DD:EE:01 Sensor\n"
            if args[-1] == "Connected":
                return "Device AA:BB:CC:DD:EE:02 Old connected device"
            return ("Device AA:BB:CC:DD:EE:01 Sensor\n"
                    "Device AA:BB:CC:DD:EE:02 Old connected device")

        with patch.object(dashboard, "run_status", side_effect=fake_run):
            result = dashboard.collect_nearby_radios()
        self.assertEqual(len(result["wifi"]), 2)
        self.assertTrue(result["wifi"][0]["connected"])
        self.assertEqual(result["bluetooth"], [{"name": "Sensor", "connected": False}])


if __name__ == "__main__":
    unittest.main()
