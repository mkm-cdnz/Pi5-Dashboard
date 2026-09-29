#!/usr/bin/env python3
"""Standalone live Pi status screen for a 128x64 I2C OLED."""

from __future__ import annotations

import argparse
import os
import re
import socket
import subprocess
import time
from pathlib import Path

def cpu_temperature() -> float | None:
    try:
        return int(Path("/sys/class/thermal/thermal_zone0/temp").read_text().strip()) / 1000
    except (OSError, ValueError):
        return None


def memory_usage_gib() -> tuple[float, float] | None:
    try:
        values = {}
        for line in Path("/proc/meminfo").read_text().splitlines():
            key, raw = line.split(":", 1)
            values[key] = int(raw.split()[0])
        total = values["MemTotal"] / 1_048_576
        available = values["MemAvailable"] / 1_048_576
        return total - available, total
    except (OSError, ValueError, KeyError):
        return None


def wifi_status() -> tuple[str, str]:
    """Return a compact Wi-Fi signal reading and IPv4 address."""
    operstate = ""
    try:
        operstate = Path("/sys/class/net/wlan0/operstate").read_text().strip()
    except OSError:
        pass

    signal = "offline"
    if operstate == "up":
        try:
            wireless = Path("/proc/net/wireless").read_text()
            match = re.search(r"^\s*wlan0:\s+\S+\s+(-?[\d.]+)", wireless, re.MULTILINE)
            signal = f"{int(float(match.group(1)))} dBm" if match else "connected"
        except (OSError, ValueError):
            signal = "connected"

    address = "no Wi-Fi address"
    if operstate == "up":
        try:
            result = subprocess.run(
                ["ip", "-4", "-o", "addr", "show", "dev", "wlan0"],
                capture_output=True, text=True, timeout=1, check=False,
            )
            match = re.search(r"\binet\s+(\d+(?:\.\d+){3})/", result.stdout)
            if match:
                address = match.group(1)
        except (OSError, subprocess.SubprocessError):
            pass
    return signal, address


def load_font(size: int) -> ImageFont.ImageFont:
    for candidate in (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ):
        try:
            return ImageFont.truetype(candidate, size=size)
        except OSError:
            continue
    return ImageFont.load_default()


def draw_status(device, fonts: tuple[ImageFont.ImageFont, ImageFont.ImageFont]) -> None:
    small, large = fonts
    now = time.localtime()
    temperature = cpu_temperature()
    memory = memory_usage_gib()
    wifi_signal, ip_address = wifi_status()
    load = os.getloadavg()[0]

    with canvas(device) as draw:
        draw.rectangle(device.bounding_box, outline=1, fill=0)
        draw.text((5, 0), time.strftime("%H:%M", now), font=large, fill=1)
        draw.text((83, 7), time.strftime("%a %d %b", now).upper(), font=small, fill=1)
        draw.line((4, 21, device.width - 5, 21), fill=1)

        cpu = f"{temperature:.1f} C" if temperature is not None else "--.- C"
        draw.text((5, 24), f"CPU {cpu}", font=small, fill=1)
        draw.text((77, 24), f"LOAD {load:.2f}", font=small, fill=1)

        if memory:
            used, total = memory
            draw.text((5, 34), f"RAM {used:.1f}/{total:.1f} GB", font=small, fill=1)
        else:
            draw.text((5, 34), "RAM unavailable", font=small, fill=1)

        draw.text((5, 44), f"WIFI {wifi_signal}", font=small, fill=1)
        draw.text((5, 54), ip_address, font=small, fill=1)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--driver", choices=("ssd1306", "sh1106"), default="ssd1306",
                        help="OLED controller driver (default: ssd1306)")
    parser.add_argument("--address", type=lambda value: int(value, 0), default=0x3C,
                        help="I2C address, e.g. 0x3c or 0x3d (default: 0x3c)")
    parser.add_argument("--bus", type=int, default=1, help="I2C bus number (default: 1)")
    parser.add_argument("--interval", type=float, default=1.0,
                        help="Screen refresh interval in seconds (default: 1)")
    args = parser.parse_args()

    try:
        from luma.core.interface.serial import i2c
        from luma.core.render import canvas
        from luma.oled.device import sh1106, ssd1306
        from PIL import ImageFont
    except ImportError as exc:
        raise SystemExit(
            "OLED dependencies are missing. Install them with "
            "'python -m pip install luma.oled'."
        ) from exc

    serial = None
    device = None
    try:
        serial = i2c(port=args.bus, address=args.address)
        driver = ssd1306 if args.driver == "ssd1306" else sh1106
        device = driver(serial, width=128, height=64)
        fonts = (load_font(9), load_font(18))
        print(f"Pi OLED status running: {args.driver}, bus {args.bus}, address 0x{args.address:02x}.")
        print("Press Ctrl+C to stop.")
        while True:
            draw_status(device, fonts)
            time.sleep(max(0.25, args.interval))
    except KeyboardInterrupt:
        print("\nStopping OLED status display.")
    except OSError as exc:
        print(f"OLED I2C error: {exc}")
        print("Check the four wires, I2C address, and that I2C is enabled.")
        return 1
    finally:
        if device is not None:
            device.cleanup()
        elif serial is not None:
            serial.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
