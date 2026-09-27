# Pi & GPIO Dashboard

A local desktop dashboard for a Raspberry Pi 5 connected to a Keyestudio T-type GPIO shield. It places the live shield pin map beside a top-down Pi 5 schematic.

## What it shows

- The shield's printed 40-pin layout, digital pin level and mode, and editable custom labels for each physical pin.
- A GPIO17 LED blink switch and timing control. The dashboard only writes to GPIO17; other pins are read-only.
- CPU temperature, RAM and microSD use, Wi-Fi and Bluetooth state, both HDMI outputs, USB root-attached devices, Ethernet link, power/throttling flags, uptime, and I²C/SPI device-node counts.
- Nearby Wi-Fi networks and Bluetooth devices, including those **not connected**. Connected entries are highlighted. The Bluetooth list contains devices seen during the latest bounded scan, rather than every device in BlueZ's cache.
- A Maker Bot bridge for importing circuit design intent and exporting an offline bench snapshot.

The Pi drawing is a schematic, based on the [Raspberry Pi 5 product brief](https://datasheets.raspberrypi.com/rpi5/raspberry-pi-5-product-brief.pdf). The shield labels follow the Keyestudio T-type board silkscreen. Power and ground labels are nominal pin functions, not voltage measurements. USB devices are counted at their root connection and are not mapped to individual physical sockets. `No throttle flags` reflects `vcgencmd get_throttled`; it is not a voltage measurement.

## Install on the Pi

This installation expects Raspberry Pi OS with a desktop, Python 3 with Tkinter and GPIO Zero, and the `pinctrl`, `nmcli`, and `bluetoothctl` commands. On the target Pi these dependencies are already present.

```sh
git clone https://github.com/mkm-cdnz/Pi5-Dashboard.git
cd Pi5-Dashboard
bash install.sh
```

Open **Pi & GPIO Dashboard** from the desktop icon or application menu. The app runs entirely on the Pi. Raspberry Pi Connect can display and control the desktop remotely.

To update after a new version is pushed:

```sh
git pull
bash install.sh
```

Close and reopen the dashboard to load updated code.

## Pin labels and scanning

Click a pin on the shield map, enter a label, and choose **Save label**. **Remove** clears it. Labels are stored in `~/.config/pi-gpio-dashboard/pin_labels.json` on the Pi and are not committed to Git.

The dashboard refreshes GPIO levels every 0.4 seconds and system readings every 3 seconds. It rescans nearby Wi-Fi networks and runs a 6-second Bluetooth discovery roughly every 30 seconds while open. Discovery does not pair with or connect to devices. Radio names and scan results are displayed locally and are not saved to the repository.

## Agent handshake: Pi5-Dashboard ↔ Maker Bot

I maintain **Pi5-Dashboard**, the local runtime view of Matt's Pi 5 and Keyestudio shield. Maker Bot owns circuit design intent and BOM data. The dashboard accepts that intent as data, shows it beside live readings, and exports a bench snapshot for Maker Bot or a human to inspect offline. Importing a payload never configures a GPIO, connects a radio, or starts the LED. GPIO17 remains the only writable pin, through its existing on-screen blink control.

The bridge uses UTF-8 JSON files in `~/.config/pi-gpio-dashboard/bridge/` on the Pi:

| Direction | File | How to use it |
| --- | --- | --- |
| Maker Bot → dashboard | `design_intent.json` | Write a complete file atomically (temporary file, then rename). The open dashboard checks for changes every 2 seconds; **Import design** retries immediately. |
| Dashboard → Maker Bot | `bench_snapshot.json` | Click **Export bench**. The dashboard reads GPIO again and atomically replaces this file. Copy it to another machine or feed it to Maker Bot later. |

Physical pin numbers (`"1"` through `"40"`) are the keys in `pins`; `bcm` is checked against the Pi 5 header. The importer accepts `meta.sync_version: "1.0"`, a `pins` object, and these optional string fields per pin: `custom_label`, `project_id`, `direction`, `signal_type`, `voltage_logic`, `bom_component_id`, `bom_component_name`, `code_variable`, `color_tag` (`#RRGGBB`), and `safety_warning`. It rejects invalid pin mappings and oversized payloads. `color_tag` is retained in the loaded design and exported, but the current GUI does not apply it to the pin map.

Example downlink:

```json
{
  "meta": {"sync_version": "1.0", "source": "maker_bot_ssot", "device": "Raspberry_Pi_5"},
  "pins": {
    "11": {
      "bcm": 17,
      "custom_label": "STATUS_LED_RED",
      "project_id": "rpi_blink_led",
      "direction": "OUTPUT",
      "bom_component_name": "Red LED with series resistor",
      "code_variable": "LED_PIN",
      "safety_warning": "Check resistor and current before enabling output"
    }
  }
}
```

The shield shows an imported `custom_label` unless Matt has entered a local label for that physical pin. Local labels remain in `pin_labels.json`, independent of the design file. Selected-pin details show available BOM, project, direction, code binding, and warning text. Removing a local label reveals the imported design label again.

The uplink contains `meta` (`sync_version`, `source`, UTC `timestamp`, `device`), all 40 physical pins, and `system.cpu_temp_c`. Each pin reports `bcm`, `silkscreen_label`, `design_intent`, `design_label`, `user_override_label`, raw `actual_mode` and `actual_pull` from `pinctrl`, and `live_logic_level` (`0`, `1`, or `null`). `hardware_connected` and `detected_conflict` are `null`: the Pi cannot verify what Matt plugged into a breadboard or declare it safe from GPIO readings alone. CPU temperature is not ambient temperature. Power pin labels describe nominal header functions, not measured voltages. A snapshot is a point-in-time export, not a live stream.

## Development

```sh
python3 -m unittest discover -s tests
python3 pi_gpio_dashboard.py
```

The desktop launcher template is in `packaging/`; `install.sh` fills in the current user's application directory.
