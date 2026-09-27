# Pi & GPIO Dashboard

A local desktop dashboard for a Raspberry Pi 5 connected to a Keyestudio T-type GPIO shield. It places the live shield pin map beside a top-down Pi 5 schematic.

## What it shows

- The shield's printed 40-pin layout, digital pin level and mode, and editable custom labels for each physical pin.
- A GPIO17 LED blink switch and timing control. The dashboard only writes to GPIO17; other pins are read-only.
- CPU temperature, RAM and microSD use, Wi-Fi and Bluetooth state, both HDMI outputs, USB root-attached devices, Ethernet link, power/throttling flags, uptime, and I²C/SPI device-node counts.
- Nearby Wi-Fi networks and Bluetooth devices, including those **not connected**. Connected entries are highlighted. The Bluetooth list contains devices seen during the latest bounded scan, rather than every device in BlueZ's cache.

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

## Development

```sh
python3 -m unittest discover -s tests
python3 pi_gpio_dashboard.py
```

The desktop launcher template is in `packaging/`; `install.sh` fills in the current user's application directory.
