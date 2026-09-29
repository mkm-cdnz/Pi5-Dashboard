# Pi OLED status demo

This is a standalone status display for the small 128×64 I²C OLED module marked `GME12864-11-12-13 V3.6`. It shows the Pi's local time/date, CPU temperature/load, RAM usage, Wi-Fi signal, and Wi-Fi IPv4 address. It only reads system status and writes to the OLED over I²C; it does not change GPIO outputs.

The module's exact controller cannot be identified from its outside markings. The default driver is SSD1306. If the display stays blank or the image is shifted, retry with `--driver sh1106`. The address-select pads on the back choose `0x3C` or `0x3D`; the default command uses `0x3C`.

## Breadboard wiring

Turn off and unplug the Pi before changing wires. Keep the screen's 4-pin header aligned with the labels printed beside it.

| OLED pin | Connect to Keyestudio T-type shield | Raspberry Pi header pin | Signal |
| --- | --- | ---: | --- |
| `VCC` | `3V3` | 1 | 3.3 V supply |
| `GND` | `GND` | 6 | Ground |
| `SCL` | `SCL1` | 5 | I²C clock, GPIO3 |
| `SDA` | `SDA1` | 3 | I²C data, GPIO2 |

Use four jumper wires and route each through the breadboard rows connected to the screen header. The shield pins are the 40-pin header columns nearest the center board; count physical pins from the end marked `3V3`/`5V0`, with odd numbers on the left column and even numbers on the right. Double-check the shield label and OLED label at each end before powering on. Leave the `5V0` shield pins unused. The Pi's I²C signals are 3.3 V logic.

After wiring, power on and find the OLED address:

```sh
sudo i2cdetect -y 1
```

Look for `3c` or `3d` in the table. No response usually means a wiring, address, or I²C-enable issue. I²C is enabled on the Pi 5 image used for this project; `i2cdetect` is provided by the `i2c-tools` package.

## Run

The Pi installer creates a virtual environment under `~/Applications/pi-oled-status-demo`:

```sh
cd ~/Applications/pi-oled-status-demo
.venv/bin/python oled_status.py --driver ssd1306 --address 0x3c
```

If the address scan showed `3d`, replace `0x3c` with `0x3d`. If SSD1306 renders incorrectly, stop with Ctrl+C and run:

```sh
.venv/bin/python oled_status.py --driver sh1106 --address 0x3c
```

The demo refreshes once per second and runs in the foreground. Press Ctrl+C to stop and clear the display. The app is intentionally not set to auto-start until the wiring and driver have been confirmed.

## Install dependencies

From the repository root on the Pi:

```sh
sudo apt install i2c-tools python3-venv
mkdir -p ~/Applications/pi-oled-status-demo
python3 -m venv ~/Applications/pi-oled-status-demo/.venv
~/Applications/pi-oled-status-demo/.venv/bin/pip install luma.oled
cp examples/oled_status/oled_status.py ~/Applications/pi-oled-status-demo/
```

`luma.oled` supplies SSD1306 and SH1106 drivers and a Pillow drawing canvas for Raspberry Pi/Linux I²C displays. See its [usage documentation](https://luma-oled.readthedocs.io/en/latest/python-usage.html).
