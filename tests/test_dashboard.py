import tempfile
import json
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

    def test_design_import_checks_physical_and_bcm_mapping(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "design.json"
            payload = {"meta": {"sync_version": "1.0", "source": "maker_bot_ssot"},
                       "pins": {"11": {"bcm": 17, "custom_label": "STATUS_LED",
                                       "safety_warning": "Use a resistor"}}}
            path.write_text(json.dumps(payload), encoding="utf-8")
            self.assertEqual(dashboard.load_design_intent(path)[11]["custom_label"],
                             "STATUS_LED")
            payload["pins"]["11"]["bcm"] = 18
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaises(ValueError):
                dashboard.load_design_intent(path)

    def test_snapshot_preserves_user_and_design_labels_without_inventing_hardware(self):
        states = {17: {"function": "op", "pull": "pn", "level": "hi"}}
        snapshot = dashboard.build_bench_snapshot(
            states, {11: "Bench LED"}, {11: {"custom_label": "Designed LED"}}, 42.5)
        self.assertEqual(snapshot["pins"]["11"]["live_logic_level"], 1)
        self.assertEqual(snapshot["pins"]["11"]["user_override_label"], "Bench LED")
        self.assertEqual(snapshot["pins"]["11"]["design_label"], "Designed LED")
        self.assertIsNone(snapshot["pins"]["11"]["hardware_connected"])
        self.assertIsNone(snapshot["pins"]["9"]["live_logic_level"])
        self.assertEqual(len(snapshot["pins"]), 40)

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
