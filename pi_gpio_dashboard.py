#!/usr/bin/env python3
"""Live Raspberry Pi 5 and Keyestudio T-type shield desktop dashboard."""

from __future__ import annotations

import re
import os
import json
import shutil
import subprocess
import tkinter as tk
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from tkinter import messagebox

from gpiozero import LED


@dataclass(frozen=True)
class Pin:
    number: int
    label: str
    bcm: int | None = None
    kind: str = "gpio"


# Physical 40-pin header order, viewed from above with the ribbon cable at top.
# Labels follow the Keyestudio T-type board silkscreen.
PINS = [
    Pin(1, "3V3", kind="3v3"), Pin(2, "5V0", kind="5v"),
    Pin(3, "SDA1", 2), Pin(4, "5V0", kind="5v"),
    Pin(5, "SCL1", 3), Pin(6, "GND", kind="gnd"),
    Pin(7, "GPIO4", 4), Pin(8, "TXD0", 14),
    Pin(9, "GND", kind="gnd"), Pin(10, "RXD0", 15),
    Pin(11, "GPIO17", 17), Pin(12, "GPIO18", 18),
    Pin(13, "GPIO27", 27), Pin(14, "GND", kind="gnd"),
    Pin(15, "GPIO22", 22), Pin(16, "GPIO23", 23),
    Pin(17, "3V3", kind="3v3"), Pin(18, "GPIO24", 24),
    Pin(19, "SPIMOSI", 10), Pin(20, "GND", kind="gnd"),
    Pin(21, "SPIMISO", 9), Pin(22, "GPIO25", 25),
    Pin(23, "SPISCLK", 11), Pin(24, "SPICE0", 8),
    Pin(25, "GND", kind="gnd"), Pin(26, "SPICE1", 7),
    Pin(27, "ID_SD", 0), Pin(28, "ID_SC", 1),
    Pin(29, "GPIO5", 5), Pin(30, "GND", kind="gnd"),
    Pin(31, "GPIO6", 6), Pin(32, "GPIO12", 12),
    Pin(33, "GPIO13", 13), Pin(34, "GND", kind="gnd"),
    Pin(35, "GPIO19", 19), Pin(36, "GPIO16", 16),
    Pin(37, "GPIO26", 26), Pin(38, "GPIO20", 20),
    Pin(39, "GND", kind="gnd"), Pin(40, "GPIO21", 21),
]

BG = "#0b1220"
CARD = "#142033"
CARD_BORDER = "#27394d"
TEXT = "#f2f7f5"
MUTED = "#9aafbf"
TEAL = "#68e0ce"
HIGH = "#74e5b2"
LOW = "#85baf2"
IDLE = "#9daaba"
POWER = "#f5c96e"
GROUND = "#a9b6c3"
ERROR = "#ff9b96"
LABELS_FILE = Path.home() / ".config" / "pi-gpio-dashboard" / "pin_labels.json"


def load_pin_labels(path: Path = LABELS_FILE) -> dict[int, str]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    if not isinstance(raw, dict):
        return {}
    labels = {}
    for key, value in raw.items():
        try:
            pin = int(key)
        except (TypeError, ValueError):
            continue
        if 1 <= pin <= 40 and isinstance(value, str):
            cleaned = " ".join(value.split())[:40]
            if cleaned:
                labels[pin] = cleaned
    return labels


def save_pin_labels(labels: dict[int, str], path: Path = LABELS_FILE) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps({str(pin): value for pin, value in sorted(labels.items())},
                                    indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def read_gpio_states() -> dict[int, dict[str, str]]:
    result = subprocess.run(
        ["pinctrl", "get", "0-27"],
        capture_output=True, text=True, check=True, timeout=2,
    )
    states: dict[int, dict[str, str]] = {}
    for line in result.stdout.splitlines():
        match = re.match(r"\s*(\d+):\s+(\S+)\s+(.*?)\s*\|\s*(hi|lo|--)\s*//", line)
        if not match:
            continue
        number, function, settings, level = match.groups()
        pull = next((s for s in settings.split() if s in ("pu", "pd", "pn")), "?")
        states[int(number)] = {"function": function, "pull": pull, "level": level}
    if len(states) < 28:
        raise RuntimeError(f"Expected 28 GPIO readings, received {len(states)}")
    return states


def state_badge(pin: Pin, states: dict[int, dict[str, str]]) -> tuple[str, str, str]:
    if pin.kind == "3v3":
        return "3.3 V", POWER, "Supply label · not measured"
    if pin.kind == "5v":
        return "5 V", POWER, "Supply label · not measured"
    if pin.kind == "gnd":
        return "GND", GROUND, "Ground connection"
    state = states.get(pin.bcm)
    if not state:
        return "—", IDLE, "No reading"
    function = state["function"]
    if function == "no":
        return "IDLE", IDLE, "No function assigned"
    level = state["level"]
    if level == "hi":
        return "HIGH", HIGH, "Digital level high"
    if level == "lo":
        return "LOW", LOW, "Digital level low"
    return "—", IDLE, "Level unavailable"


def read_file(path: str | Path, fallback: str = "") -> str:
    try:
        return Path(path).read_text(encoding="utf-8").strip()
    except (OSError, UnicodeError):
        return fallback


def run_status(args: list[str], timeout: float = 1.5) -> str:
    try:
        return subprocess.run(args, capture_output=True, text=True,
                              timeout=timeout, check=True).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def collect_system_status() -> dict[str, object]:
    """Read system state without changing hardware configuration."""
    temperature = read_file("/sys/class/thermal/thermal_zone0/temp")
    try:
        temp_c = int(temperature) / 1000
    except ValueError:
        temp_c = None

    memory = {}
    for line in read_file("/proc/meminfo").splitlines():
        if ":" in line:
            name, value = line.split(":", 1)
            memory[name] = int(value.strip().split()[0])
    total = memory.get("MemTotal", 0)
    used = total - memory.get("MemAvailable", total)
    disk = shutil.disk_usage("/")
    uptime_text = read_file("/proc/uptime", "0").split()[0]
    uptime_hours = int(float(uptime_text) // 3600)

    wifi_up = read_file("/sys/class/net/wlan0/operstate") == "up"
    wifi_dbm = None
    wireless = re.search(r"^\s*wlan0:\s+\S+\s+[\d.]+\s+(-?[\d.]+)",
                         read_file("/proc/net/wireless"), re.MULTILINE)
    if wireless:
        wifi_dbm = int(float(wireless.group(1)))

    bt_softblocked = False
    for rfkill in Path("/sys/class/rfkill").glob("rfkill*"):
        if read_file(rfkill / "type") == "bluetooth":
            bt_softblocked = read_file(rfkill / "soft") == "1"
            break
    bt_info = run_status(["bluetoothctl", "show"])
    bt_powered = "Powered: yes" in bt_info and not bt_softblocked if bt_info else None
    bt_devices = run_status(["bluetoothctl", "devices", "Connected"])
    bt_count = len([line for line in bt_devices.splitlines() if line.startswith("Device ")])

    hdmi = {}
    for index in (1, 2):
        paths = list(Path("/sys/class/drm").glob(f"card*-HDMI-A-{index}/status"))
        hdmi[index] = read_file(paths[0], "unknown") if paths else "unknown"

    usb_devices = []
    for path in Path("/sys/bus/usb/devices").iterdir():
        if not re.fullmatch(r"\d+-\d+", path.name) or not (path / "idVendor").exists():
            continue
        usb_devices.append({
            "name": read_file(path / "product", "USB device"),
            "speed": read_file(path / "speed", "?"),
        })
    usb_devices.sort(key=lambda device: str(device["name"]))

    eth_link = read_file("/sys/class/net/eth0/carrier") == "1"
    eth_speed = read_file("/sys/class/net/eth0/speed") if eth_link else ""
    throttle_text = run_status(["vcgencmd", "get_throttled"])
    throttle = throttle_text.split("=", 1)[-1] if "=" in throttle_text else "?"
    try:
        load = os.getloadavg()[0]
    except OSError:
        load = None
    return {
        "temp_c": temp_c, "load": load,
        "mem_used": used * 1024, "mem_total": total * 1024,
        "disk_used": disk.used, "disk_total": disk.total,
        "uptime_hours": uptime_hours,
        "wifi_up": wifi_up, "wifi_dbm": wifi_dbm,
        "bt_powered": bt_powered, "bt_count": bt_count,
        "hdmi0": hdmi[1], "hdmi1": hdmi[2],
        "usb_devices": usb_devices,
        "eth_link": eth_link, "eth_speed": eth_speed,
        "throttle": throttle,
        "i2c_count": len(list(Path("/dev").glob("i2c-*"))),
        "spi_count": len(list(Path("/dev").glob("spidev*"))),
    }


def split_nmcli_fields(line: str) -> list[str]:
    fields, current = [], []
    escaped = False
    for character in line:
        if escaped:
            current.append(character)
            escaped = False
        elif character == "\\":
            escaped = True
        elif character == ":":
            fields.append("".join(current))
            current = []
        else:
            current.append(character)
    fields.append("".join(current))
    return fields


def collect_nearby_radios() -> dict[str, object]:
    """Run bounded local scans; report only devices seen in this scan window."""
    wifi_output = run_status(
        ["nmcli", "-t", "--escape", "yes", "-f", "IN-USE,SSID,SIGNAL,SECURITY",
         "device", "wifi", "list", "--rescan", "yes"], timeout=15,
    )
    wifi_by_name: dict[str, dict[str, object]] = {}
    for line in wifi_output.splitlines():
        fields = split_nmcli_fields(line)
        if len(fields) != 4:
            continue
        in_use, ssid, strength, security = fields
        ssid = " ".join(ssid.split()) or "Hidden network"
        try:
            signal = max(0, min(100, int(strength)))
        except ValueError:
            continue
        candidate = {"name": ssid[:38], "signal": signal,
                     "security": security or "Open", "connected": in_use == "*"}
        current = wifi_by_name.get(ssid)
        if current is None or candidate["connected"] or signal > current["signal"]:
            wifi_by_name[ssid] = candidate
    wifi = sorted(wifi_by_name.values(),
                  key=lambda item: (not item["connected"], -item["signal"], item["name"]))

    scan_output = run_status(["bluetoothctl", "--timeout", "6", "scan", "on"], timeout=9)
    scan_output = re.sub(r"\x1b\[[0-9;]*[A-Za-z]|[\x01\x02]", "", scan_output)
    fresh_addresses = set(re.findall(r"\bDevice ([0-9A-Fa-f:]{17})\b", scan_output))
    known_output = run_status(["bluetoothctl", "devices"])
    known = {}
    for line in known_output.splitlines():
        match = re.match(r"Device ([0-9A-Fa-f:]{17}) (.+)", line)
        if match:
            known[match.group(1).upper()] = match.group(2).strip()
    connected_output = run_status(["bluetoothctl", "devices", "Connected"])
    connected = {address.upper() for address in re.findall(
        r"\bDevice ([0-9A-Fa-f:]{17})\b", connected_output)}
    bluetooth = []
    for address in fresh_addresses:
        address = address.upper()
        name = known.get(address, "")
        if not name or name.replace("-", ":").upper() == address:
            name = f"Unnamed · …{address[-5:]}"
        bluetooth.append({"name": name[:38], "connected": address in connected})
    bluetooth.sort(key=lambda item: (not item["connected"], item["name"].startswith("Unnamed"),
                                      item["name"].lower()))
    return {"wifi": wifi, "bluetooth": bluetooth,
            "scanned_at": datetime.now().strftime("%H:%M:%S")}


class ShieldStudio:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Pi & GPIO Dashboard · Raspberry Pi 5")
        self.root.configure(bg=BG)
        width = min(1870, root.winfo_screenwidth() - 32)
        height = min(950, root.winfo_screenheight() - 105)
        self.root.geometry(f"{width}x{height}+20+20")
        self.root.minsize(1500, 800)
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.states: dict[int, dict[str, str]] = {}
        self.selected = PINS[10]  # GPIO17, physical pin 11
        self.pin_labels = load_pin_labels()
        self.label_var = tk.StringVar(value=self.pin_labels.get(self.selected.number, ""))
        self.led: LED | None = None
        self.badges: dict[int, tuple[int, int]] = {}
        self.rows: dict[int, int] = {}
        self.silk_items: dict[int, int] = {}
        self.custom_items: dict[int, int] = {}
        self.refresh_job: str | None = None
        self.system_job: str | None = None
        self.system_executor = ThreadPoolExecutor(max_workers=1)
        self.system_future = None
        self.radio_job: str | None = None
        self.radio_executor = ThreadPoolExecutor(max_workers=1)
        self.radio_future = None
        self.system_items: dict[str, int] = {}
        self.blink_seconds = tk.DoubleVar(value=0.5)
        self.build_ui()
        self.refresh()
        self.start_system_refresh()
        self.start_radio_scan()

    def build_ui(self) -> None:
        header = tk.Frame(self.root, bg=BG)
        header.pack(fill="x", padx=25, pady=(19, 10))
        intro = tk.Frame(header, bg=BG)
        intro.pack(side="left", fill="y")
        tk.Label(intro, text="Pi & GPIO Dashboard", bg=BG, fg=TEXT,
                 font=("DejaVu Sans", 24, "bold")).pack(anchor="w")
        tk.Label(intro, text="RASPBERRY PI 5  +  KEYESTUDIO T-TYPE SHIELD  ·  LIVE HARDWARE VIEW",
                 bg=BG, fg=TEAL, font=("DejaVu Sans", 10, "bold")).pack(anchor="w", pady=(3, 0))

        controls = tk.Frame(header, bg=CARD, highlightbackground=CARD_BORDER,
                            highlightthickness=1)
        controls.pack(side="right")
        led_control = tk.Frame(controls, bg=CARD)
        led_control.pack(side="left", padx=(14, 6), pady=8)
        self.blink_button = tk.Button(
            led_control, text="START GPIO17 BLINK", command=self.toggle_blink,
            bg=TEAL, fg="#08201f", activebackground="#9af2e4",
            activeforeground="#08201f", relief="flat", bd=0,
            font=("DejaVu Sans", 10, "bold"), cursor="hand2", pady=5,
        )
        self.blink_button.pack(fill="x")
        self.blink_status = tk.Label(led_control, text="●  OFF  ·  GPIO17 released",
                                     bg=CARD, fg=MUTED, font=("DejaVu Sans", 9, "bold"))
        self.blink_status.pack(anchor="w", pady=(4, 0))
        speed_control = tk.Frame(controls, bg=CARD)
        speed_control.pack(side="left", padx=(5, 12), pady=7)
        self.speed_label = tk.Label(speed_control, text="0.5 s on  ·  0.5 s off", bg=CARD,
                                    fg=MUTED, font=("DejaVu Sans", 9))
        self.speed_label.pack(anchor="w")
        tk.Scale(speed_control, from_=0.2, to=2.0, resolution=0.1, orient="horizontal",
                 variable=self.blink_seconds, command=self.change_speed,
                 bg=CARD, fg=TEXT, troughcolor="#2a3b4f", activebackground=TEAL,
                 highlightthickness=0, bd=0, length=180, showvalue=False,
                 sliderlength=16).pack()

        body = tk.Frame(self.root, bg=BG)
        body.pack(fill="both", expand=True, padx=25, pady=(0, 10))

        diagram_frame = tk.Frame(body, bg=CARD, highlightbackground=CARD_BORDER,
                                 highlightthickness=1)
        diagram_frame.pack(side="left", fill="both", expand=True)
        self.canvas = tk.Canvas(diagram_frame, bg=CARD, width=754, height=733,
                                highlightthickness=0)
        self.canvas.pack(fill="both", expand=True, padx=10, pady=9)
        self.draw_diagram()

        side = tk.Frame(body, bg=BG, width=380)
        side.pack(side="right", fill="y", padx=(18, 0))
        side.pack_propagate(False)

        pi_frame = tk.Frame(body, bg=CARD, width=630,
                            highlightbackground=CARD_BORDER, highlightthickness=1)
        pi_frame.pack(side="right", fill="y", padx=(18, 0))
        pi_frame.pack_propagate(False)
        self.pi_canvas = tk.Canvas(pi_frame, bg=CARD, width=608, height=745,
                                   highlightthickness=0)
        self.pi_canvas.pack(fill="both", expand=True, padx=10, pady=9)
        self.draw_pi_diagram()

        radio_card = self.card(side, pady=12)
        tk.Label(radio_card, text="Radio radar", bg=CARD, fg=TEXT,
                 font=("DejaVu Sans", 19, "bold")).pack(anchor="w", padx=17, pady=(14, 1))
        tk.Label(radio_card, text="Nearby, including devices not connected",
                 bg=CARD, fg=MUTED, font=("DejaVu Sans", 9)).pack(anchor="w", padx=17)
        self.radio_scan_label = tk.Label(radio_card, text="Scanning nearby…", bg=CARD,
                                         fg=TEAL, font=("DejaVu Sans", 9, "bold"))
        self.radio_scan_label.pack(anchor="w", padx=17, pady=(5, 9))
        tk.Label(radio_card, text="WI-FI NETWORKS", bg=CARD, fg=TEAL,
                 font=("DejaVu Sans", 9, "bold")).pack(anchor="w", padx=17, pady=(0, 3))
        self.wifi_rows = self.make_radio_rows(radio_card, 5)
        tk.Label(radio_card, text="BLUETOOTH DEVICES", bg=CARD, fg=TEAL,
                 font=("DejaVu Sans", 9, "bold")).pack(anchor="w", padx=17, pady=(9, 3))
        self.bt_rows = self.make_radio_rows(radio_card, 4)
        tk.Label(radio_card, text="Bluetooth shows devices seen in the latest 6 s scan.",
                 bg=CARD, fg=MUTED, font=("DejaVu Sans", 8)).pack(
                     anchor="w", padx=17, pady=(9, 13))

        selected_card = self.card(side)
        tk.Label(selected_card, text="SELECTED PIN", bg=CARD, fg=TEAL,
                 font=("DejaVu Sans", 9, "bold")).pack(anchor="w", padx=18, pady=(13, 3))
        self.selected_title = tk.Label(selected_card, bg=CARD, fg=TEXT,
                                       font=("DejaVu Sans", 16, "bold"))
        self.selected_title.pack(anchor="w", padx=18)
        self.selected_detail = tk.Label(selected_card, bg=CARD, fg=MUTED,
                                        font=("DejaVu Sans", 9), justify="left",
                                        wraplength=332)
        self.selected_detail.pack(anchor="w", padx=18, pady=(4, 11))
        tk.Label(selected_card, text="CUSTOM LABEL  ·  PHYSICAL PIN",
                 bg=CARD, fg=TEAL, font=("DejaVu Sans", 9, "bold")).pack(
                     anchor="w", padx=18, pady=(0, 4))
        entry = tk.Entry(selected_card, textvariable=self.label_var, bg="#223448",
                         fg=TEXT, insertbackground=TEXT, relief="flat", bd=0,
                         font=("DejaVu Sans", 10))
        entry.pack(fill="x", padx=18, ipady=6)
        entry.bind("<Return>", lambda _event: self.save_label())
        actions = tk.Frame(selected_card, bg=CARD)
        actions.pack(fill="x", padx=18, pady=(8, 0))
        tk.Button(actions, text="SAVE LABEL", command=self.save_label,
                  bg=TEAL, fg="#08201f", relief="flat", bd=0,
                  font=("DejaVu Sans", 9, "bold"), cursor="hand2").pack(
                      side="left", fill="x", expand=True, ipady=5)
        tk.Button(actions, text="REMOVE", command=self.remove_label,
                  bg="#2a3b4f", fg=TEXT, relief="flat", bd=0,
                  font=("DejaVu Sans", 9, "bold"), cursor="hand2").pack(
                      side="left", fill="x", expand=True, padx=(7, 0), ipady=5)
        self.label_message = tk.Label(selected_card,
            text="Click a shield pin to edit its label. Labels are saved on this Pi.",
            bg=CARD, fg=MUTED, font=("DejaVu Sans", 8))
        self.label_message.pack(anchor="w", padx=18, pady=(7, 12))

        footer = tk.Frame(self.root, bg=BG)
        footer.pack(fill="x", padx=25, pady=(0, 13))
        self.connection = tk.Label(footer, text="●  Reading pins…", bg=BG, fg=MUTED,
                                   font=("DejaVu Sans", 10))
        self.connection.pack(side="left")
        tk.Label(footer, text="Pi view is schematic · USB devices are grouped, not mapped to individual sockets",
                 bg=BG, fg=MUTED, font=("DejaVu Sans", 9)).pack(side="right")

    @staticmethod
    def card(parent: tk.Widget, pady: int = 0) -> tk.Frame:
        frame = tk.Frame(parent, bg=CARD, highlightbackground=CARD_BORDER,
                         highlightthickness=1)
        frame.pack(fill="x", pady=(0, pady))
        return frame

    @staticmethod
    def make_radio_rows(parent: tk.Widget, count: int) -> list[tuple[tk.Label, tk.Label]]:
        rows = []
        for index in range(count):
            row = tk.Frame(parent, bg="#1c2b3b" if index % 2 == 0 else "#192838",
                           height=29)
            row.pack(fill="x", padx=17, pady=1)
            row.pack_propagate(False)
            name = tk.Label(row, text="", bg=row["bg"], fg=TEXT,
                            font=("DejaVu Sans", 9), anchor="w")
            name.pack(side="left", fill="x", expand=True, padx=(7, 3))
            detail = tk.Label(row, text="", bg=row["bg"], fg=MUTED,
                              font=("DejaVu Sans", 8, "bold"), anchor="e")
            detail.pack(side="right", padx=(0, 7))
            rows.append((name, detail))
        return rows

    def draw_diagram(self) -> None:
        c = self.canvas
        c.create_text(20, 15, anchor="nw", text="LIVE PIN MAP", fill=TEAL,
                      font=("DejaVu Sans", 10, "bold"))
        c.create_text(730, 15, anchor="ne", text="40-PIN HEADER", fill=MUTED,
                      font=("DejaVu Sans", 9, "bold"))
        # Breadboard and its two power rails.
        c.create_rectangle(87, 50, 667, 713, fill="#e6ece9", outline="")
        c.create_rectangle(92, 52, 185, 711, fill="#dce5e1", outline="")
        c.create_rectangle(570, 52, 663, 711, fill="#dce5e1", outline="")
        for x, color in ((103, "#dc6f73"), (172, "#5f9ac7"),
                         (582, "#dc6f73"), (650, "#5f9ac7")):
            c.create_line(x, 63, x, 700, fill=color, width=2)
        # Board and cable socket.
        c.create_rectangle(195, 61, 559, 705, fill="#0d141c", outline="#465963", width=2)
        c.create_rectangle(178, 42, 576, 82, fill="#202c36", outline="#425462", width=2)
        for i in range(31):
            x = 185 + i * 12.8
            c.create_line(x, 44, x, 60, fill=("#566c79" if i % 2 else "#405562"), width=4)
        c.create_text(377, 71, text="GPIO EXTENSION BOARD", fill=POWER,
                      font=("DejaVu Sans", 10, "bold"))

        for index in range(20):
            y = 105 + index * 29.5
            for pin in (PINS[index * 2], PINS[index * 2 + 1]):
                left = pin.number % 2 == 1
                tag = f"pin{pin.number}"
                if left:
                    x1, x2 = 112, 177
                    dot_x, label_x, number_x = 217, 243, 188
                    anchor = "w"
                    connector = (178, 209)
                else:
                    x1, x2 = 578, 645
                    dot_x, label_x, number_x = 537, 512, 567
                    anchor = "e"
                    connector = (545, 577)
                stripe = c.create_rectangle(x1-7, y-12, x2+7, y+12,
                                             fill="#e6ece9", outline="", tags=(tag,))
                self.rows[pin.number] = stripe
                c.create_line(connector[0], y, connector[1], y,
                              fill="#aabcb8", width=2, tags=(tag,))
                c.create_oval(dot_x-4, y-4, dot_x+4, y+4, fill="#617580",
                              outline="#a9bcb9", tags=(tag,))
                c.create_text(number_x, y, text=f"{pin.number:02d}", fill="#627782",
                              font=("DejaVu Sans Mono", 8), tags=(tag,))
                silk = c.create_text(label_x, y, text=pin.label, anchor=anchor,
                                     fill=POWER if pin.kind != "gpio" else "#e1d775",
                                     font=("DejaVu Sans", 10, "bold"), tags=(tag,))
                custom = c.create_text(label_x, y+7, text="", anchor=anchor,
                                       fill=TEAL, font=("DejaVu Sans", 8, "bold"),
                                       tags=(tag,))
                self.silk_items[pin.number] = silk
                self.custom_items[pin.number] = custom
                back = c.create_rectangle(x1, y-10, x2, y+10, fill="#d1dadd",
                                          outline="", tags=(tag,))
                text = c.create_text((x1+x2)/2, y, text="…", fill="#21313d",
                                     font=("DejaVu Sans", 9, "bold"), tags=(tag,))
                self.badges[pin.number] = (back, text)
                c.tag_bind(tag, "<Button-1>", lambda _event, p=pin: self.select_pin(p))
                self.render_pin_label(pin)
        c.create_text(377, 687, text="TOP VIEW  ·  PHYSICAL PIN ORDER",
                      fill="#9aabb5", font=("DejaVu Sans", 8, "bold"))

    def draw_pi_diagram(self) -> None:
        c = self.pi_canvas
        c.create_text(20, 15, anchor="nw", text="RASPBERRY PI 5", fill=TEAL,
                      font=("DejaVu Sans", 11, "bold"))
        c.create_text(587, 15, anchor="ne", text="TOP VIEW  ·  SCHEMATIC",
                      fill=MUTED, font=("DejaVu Sans", 9, "bold"))
        c.create_text(20, 43, anchor="nw", text="Board components and external connections",
                      fill=MUTED, font=("DejaVu Sans", 10))

        # Physical arrangement follows the Raspberry Pi 5 mechanical drawing.
        c.create_rectangle(73, 169, 503, 514, fill="#1a6759",
                           outline="#4ecbb6", width=2)
        for x, y in ((88, 184), (488, 184), (88, 499), (488, 499)):
            c.create_oval(x-8, y-8, x+8, y+8, fill=CARD,
                          outline="#b7d0c4", width=2)
        c.create_text(385, 482, text="RASPBERRY PI 5", fill="#7bd6c3",
                      font=("DejaVu Sans", 10, "bold"))

        # Header to the shield. Individual GPIO levels remain in the left view.
        c.create_rectangle(105, 148, 463, 181, fill="#1d2830", outline="#95b9b5")
        for index in range(20):
            x = 114 + index * 17.8
            for y in (157, 170):
                c.create_oval(x-2, y-2, x+2, y+2, fill="#d8ba75", outline="")
        c.create_text(285, 132, text="40-PIN GPIO HEADER  →  SHIELD MAP",
                      fill=TEAL, font=("DejaVu Sans", 9, "bold"))

        # Main chips and the shared wireless module.
        c.create_rectangle(111, 208, 193, 307, fill="#132d36", outline="#83d8ca", width=2)
        c.create_text(152, 226, text="RADIO", fill=TEAL,
                      font=("DejaVu Sans", 9, "bold"))
        self.system_items["wifi_onboard"] = c.create_text(152, 254, text="Wi-Fi …",
                           fill=TEXT, font=("DejaVu Sans", 10, "bold"))
        self.system_items["bt_onboard"] = c.create_text(152, 281, text="BT …",
                           fill=TEXT, font=("DejaVu Sans", 10, "bold"))

        c.create_rectangle(216, 208, 342, 270, fill="#26333d", outline="#7f9fac", width=2)
        c.create_text(279, 227, text="LPDDR4X RAM", fill=MUTED,
                      font=("DejaVu Sans", 9, "bold"))
        self.system_items["ram_onboard"] = c.create_text(279, 250, text="… GiB used",
                           fill=TEXT, font=("DejaVu Sans", 10, "bold"))

        c.create_rectangle(209, 289, 342, 391, fill="#223843", outline="#a0c9cc", width=3)
        c.create_text(275, 314, text="BCM2712", fill=TEXT,
                      font=("DejaVu Sans", 12, "bold"))
        c.create_text(275, 335, text="CPU + GPU", fill=MUTED,
                      font=("DejaVu Sans", 9))
        self.system_items["cpu_onboard"] = c.create_text(275, 366, text="… °C",
                           fill=HIGH, font=("DejaVu Sans", 17, "bold"))

        c.create_rectangle(370, 272, 467, 367, fill="#223843", outline="#9bbfc1", width=2)
        c.create_text(418, 308, text="RP1", fill=TEXT,
                      font=("DejaVu Sans", 17, "bold"))
        c.create_text(418, 333, text="I/O controller", fill=MUTED,
                      font=("DejaVu Sans", 9))

        c.create_rectangle(110, 384, 194, 464, fill="#184940", outline="#7cafa2")
        c.create_text(152, 406, text="microSD", fill=TEXT,
                      font=("DejaVu Sans", 10, "bold"))
        c.create_text(152, 423, text="under board", fill=MUTED,
                      font=("DejaVu Sans", 8))
        self.system_items["disk_onboard"] = c.create_text(152, 446, text="… used",
                           fill=POWER, font=("DejaVu Sans", 10, "bold"))

        # Edge connectors. Colour denotes observed link status where available.
        c.create_rectangle(45, 278, 75, 328, fill="#d9e2e1", outline="#93aaa9")
        c.create_text(58, 344, text="PCIe", fill=MUTED,
                      font=("DejaVu Sans", 8, "bold"))
        for x, title in ((110, "USB-C"), (212, "HDMI0"), (301, "HDMI1")):
            c.create_rectangle(x, 505, x+58, 534, fill="#a5b9bc", outline="#dae8e5")
            c.create_text(x+29, 550, text=title, fill=TEXT,
                          font=("DejaVu Sans", 8, "bold"))
        self.system_items["hdmi0_onboard"] = c.create_text(241, 566, text="…", fill=MUTED,
                           font=("DejaVu Sans", 8, "bold"))
        self.system_items["hdmi1_onboard"] = c.create_text(330, 566, text="…", fill=MUTED,
                           font=("DejaVu Sans", 8, "bold"))
        for x, title in ((398, "MIPI0"), (454, "MIPI1")):
            c.create_rectangle(x, 495, x+30, 528, fill="#d9e5da", outline="#b6cfbb")
            c.create_text(x+15, 548, text=title, fill=MUTED,
                          font=("DejaVu Sans", 8))
        c.create_rectangle(499, 216, 550, 257, fill="#515f68", outline="#b8c7c8", width=2)
        c.create_rectangle(499, 272, 550, 329, fill="#377da6", outline="#aadcf3", width=2)
        c.create_text(555, 235, anchor="w", text="USB 2 ×2", fill=TEXT,
                      font=("DejaVu Sans", 8, "bold"))
        c.create_text(555, 299, anchor="w", text="USB 3 ×2", fill=TEXT,
                      font=("DejaVu Sans", 8, "bold"))
        c.create_rectangle(499, 387, 557, 462, fill="#a4b7b9", outline="#e0e9e5", width=2)
        c.create_text(559, 414, anchor="w", text="RJ45", fill=TEXT,
                      font=("DejaVu Sans", 8, "bold"))
        self.system_items["eth_onboard"] = c.create_text(559, 436, anchor="w",
                           text="…", fill=MUTED, font=("DejaVu Sans", 8, "bold"))

        def tile(x: int, y: int, title: str, key: str) -> None:
            c.create_rectangle(x, y, x+181, y+61, fill="#1c2b3b", outline="#32475a")
            c.create_text(x+12, y+15, anchor="w", text=title, fill=TEAL,
                          font=("DejaVu Sans", 8, "bold"))
            self.system_items[key] = c.create_text(x+12, y+40, anchor="w",
                          text="Reading…", fill=TEXT, width=160,
                          font=("DejaVu Sans", 9, "bold"))

        for x, y, title, key in (
            (20, 611, "WI-FI", "wifi_tile"),
            (212, 611, "BLUETOOTH", "bt_tile"),
            (404, 611, "USB DEVICES", "usb_tile"),
            (20, 683, "HDMI DISPLAYS", "hdmi_tile"),
            (212, 683, "ETHERNET", "eth_tile"),
            (404, 683, "POWER FLAGS", "power_tile"),
        ):
            tile(x, y, title, key)
        self.system_items["system_footer"] = c.create_text(
            22, 759, anchor="w", text="Live status loading…", fill=MUTED,
            font=("DejaVu Sans", 9), width=565,
        )

    def start_system_refresh(self) -> None:
        self.system_future = self.system_executor.submit(collect_system_status)
        self.poll_system_refresh()

    def poll_system_refresh(self) -> None:
        if not self.system_future.done():
            self.system_job = self.root.after(160, self.poll_system_refresh)
            return
        try:
            self.update_system(self.system_future.result())
        except Exception as exc:
            self.pi_canvas.itemconfigure(self.system_items["system_footer"],
                                         text=f"System read error: {exc}", fill=ERROR)
        self.system_job = self.root.after(3000, self.start_system_refresh)

    def update_system(self, status: dict[str, object]) -> None:
        c = self.pi_canvas
        def put(key: str, value: str, color: str = TEXT) -> None:
            c.itemconfigure(self.system_items[key], text=value, fill=color)

        temp = status["temp_c"]
        put("cpu_onboard", f"{temp:.1f} °C" if temp is not None else "No sensor",
            HIGH if temp is not None and temp < 70 else POWER)
        memory_total = int(status["mem_total"])
        memory_used = int(status["mem_used"])
        put("ram_onboard", f"{memory_used / 2**30:.1f} / {memory_total / 2**30:.1f} GiB")
        disk_total = int(status["disk_total"])
        disk_percent = round(int(status["disk_used"]) / disk_total * 100) if disk_total else 0
        put("disk_onboard", f"{disk_percent}% used", POWER if disk_percent > 85 else HIGH)

        wifi_up = bool(status["wifi_up"])
        dbm = status["wifi_dbm"]
        wifi_detail = f"Connected · {dbm} dBm" if wifi_up and dbm is not None else (
            "Connected" if wifi_up else "Disconnected")
        put("wifi_onboard", "Wi-Fi ON" if wifi_up else "Wi-Fi OFF",
            HIGH if wifi_up else IDLE)
        put("wifi_tile", wifi_detail, HIGH if wifi_up else IDLE)
        bt_powered = status["bt_powered"]
        bt_count = int(status["bt_count"])
        put("bt_onboard", "BT ON" if bt_powered else "BT OFF" if bt_powered is False else "BT ?",
            HIGH if bt_powered else IDLE)
        bt_detail = (f"On · {bt_count} connected" if bt_powered else
                     "Off" if bt_powered is False else "Unavailable")
        put("bt_tile", bt_detail, HIGH if bt_powered else IDLE)

        usb_devices = status["usb_devices"]
        usb_count = len(usb_devices)
        usb_name = str(usb_devices[0]["name"]) if usb_count else ""
        if len(usb_name) > 18:
            usb_name = usb_name[:17] + "…"
        usb_detail = (f"{usb_count} · {usb_name}" if usb_count == 1 else
                      f"{usb_count} root devices" if usb_count else "No root devices")
        put("usb_tile", usb_detail, HIGH if usb_count else IDLE)

        hdmi0 = str(status["hdmi0"])
        hdmi1 = str(status["hdmi1"])
        put("hdmi0_onboard", "ON" if hdmi0 == "connected" else "OFF" if hdmi0 == "disconnected" else "?",
            HIGH if hdmi0 == "connected" else IDLE)
        put("hdmi1_onboard", "ON" if hdmi1 == "connected" else "OFF" if hdmi1 == "disconnected" else "?",
            HIGH if hdmi1 == "connected" else IDLE)
        hdmi_word = lambda value: "ON" if value == "connected" else "OFF" if value == "disconnected" else "?"
        put("hdmi_tile", f"0 {hdmi_word(hdmi0)} · 1 {hdmi_word(hdmi1)}",
            HIGH if "connected" in (hdmi0, hdmi1) else IDLE)
        eth_link = bool(status["eth_link"])
        eth_detail = f"Link · {status['eth_speed']} Mb/s" if eth_link else "No cable / link"
        put("eth_onboard", "LINK" if eth_link else "OFF", HIGH if eth_link else IDLE)
        put("eth_tile", eth_detail, HIGH if eth_link else IDLE)

        throttle = str(status["throttle"])
        put("power_tile", "No throttle flags" if throttle == "0x0" else f"Flags {throttle}",
            HIGH if throttle == "0x0" else POWER)
        load = status["load"]
        load_text = f"Load {load:.2f}" if load is not None else "Load unavailable"
        uptime_hours = int(status["uptime_hours"])
        uptime_text = (f"{uptime_hours // 24}d {uptime_hours % 24}h" if uptime_hours >= 24
                       else f"{uptime_hours}h")
        put("system_footer",
            f"{load_text}  ·  Uptime {uptime_text}  ·  I²C {status['i2c_count']} buses  ·  "
            f"SPI {status['spi_count']} devices  ·  Refreshes every 3 s", MUTED)

    def start_radio_scan(self) -> None:
        self.radio_scan_label.configure(text="Scanning nearby…", fg=TEAL)
        self.radio_future = self.radio_executor.submit(collect_nearby_radios)
        self.poll_radio_scan()

    def poll_radio_scan(self) -> None:
        if not self.radio_future.done():
            self.radio_job = self.root.after(200, self.poll_radio_scan)
            return
        try:
            self.update_radio_lists(self.radio_future.result())
        except Exception as exc:
            self.radio_scan_label.configure(text=f"Scan error: {exc}", fg=ERROR)
        self.radio_job = self.root.after(25000, self.start_radio_scan)

    def update_radio_lists(self, result: dict[str, object]) -> None:
        wifi = result["wifi"]
        bluetooth = result["bluetooth"]
        self.radio_scan_label.configure(
            text=f"Last scan {result['scanned_at']}  ·  {len(wifi)} Wi-Fi  ·  {len(bluetooth)} BT",
            fg=HIGH,
        )

        def update_rows(rows: list[tuple[tk.Label, tk.Label]],
                        devices: list[dict[str, object]], kind: str) -> None:
            for index, (name_widget, detail_widget) in enumerate(rows):
                if index >= len(devices):
                    name_widget.configure(text="No nearby devices" if index == 0 and not devices else "",
                                          fg=MUTED)
                    detail_widget.configure(text="")
                    continue
                device = devices[index]
                name = str(device["name"])
                name = name if len(name) <= 22 else name[:21] + "…"
                connected = bool(device["connected"])
                name_widget.configure(text=("● " if connected else "○ ") + name,
                                      fg=HIGH if connected else TEXT)
                if kind == "wifi":
                    security = str(device["security"])
                    security = security[:8] + "…" if len(security) > 9 else security
                    detail = f"{device['signal']}%  {security}"
                else:
                    detail = "CONNECTED" if connected else "VISIBLE"
                detail_widget.configure(text=detail, fg=HIGH if connected else MUTED)

        update_rows(self.wifi_rows, wifi, "wifi")
        update_rows(self.bt_rows, bluetooth, "bluetooth")

    def refresh(self) -> None:
        try:
            self.states = read_gpio_states()
            for pin in PINS:
                badge, label = self.badges[pin.number]
                word, color, _ = state_badge(pin, self.states)
                self.canvas.itemconfigure(badge, fill=color)
                self.canvas.itemconfigure(label, text=word)
            self.connection.configure(text="●  LIVE  ·  GPIO levels refresh every 0.4 s", fg=HIGH)
            self.update_selected()
        except Exception as exc:
            self.connection.configure(text=f"●  Read error: {exc}", fg=ERROR)
        self.refresh_job = self.root.after(400, self.refresh)

    def select_pin(self, pin: Pin) -> None:
        self.canvas.itemconfigure(self.rows[self.selected.number], fill="#e6ece9")
        self.selected = pin
        self.canvas.itemconfigure(self.rows[pin.number], fill="#bcece4")
        self.label_var.set(self.pin_labels.get(pin.number, ""))
        self.label_message.configure(text="Click a shield pin to edit its label. Labels are saved on this Pi.",
                                     fg=MUTED)
        self.update_selected()

    def render_pin_label(self, pin: Pin) -> None:
        y = 105 + ((pin.number - 1) // 2) * 29.5
        silk = self.silk_items[pin.number]
        custom = self.custom_items[pin.number]
        x = self.canvas.coords(silk)[0]
        label = self.pin_labels.get(pin.number, "")
        if label:
            short = label if len(label) <= 17 else label[:16] + "…"
            self.canvas.coords(silk, x, y-6)
            self.canvas.coords(custom, x, y+7)
            self.canvas.itemconfigure(custom, text=short)
        else:
            self.canvas.coords(silk, x, y)
            self.canvas.itemconfigure(custom, text="")

    def save_label(self) -> None:
        label = " ".join(self.label_var.get().split())[:40]
        if not label:
            self.remove_label()
            return
        updated = dict(self.pin_labels)
        updated[self.selected.number] = label
        try:
            save_pin_labels(updated)
        except OSError as exc:
            self.label_message.configure(text=f"Could not save label: {exc}", fg=ERROR)
            return
        self.pin_labels = updated
        self.label_var.set(label)
        self.render_pin_label(self.selected)
        self.label_message.configure(text="Label saved on this Pi.", fg=HIGH)

    def remove_label(self) -> None:
        updated = dict(self.pin_labels)
        updated.pop(self.selected.number, None)
        try:
            save_pin_labels(updated)
        except OSError as exc:
            self.label_message.configure(text=f"Could not remove label: {exc}", fg=ERROR)
            return
        self.pin_labels = updated
        self.label_var.set("")
        self.render_pin_label(self.selected)
        self.label_message.configure(text="Label removed.", fg=HIGH)

    def update_selected(self) -> None:
        pin = self.selected
        word, _color, description = state_badge(pin, self.states)
        self.selected_title.configure(text=f"{pin.label}  ·  pin {pin.number}")
        if pin.bcm is None:
            detail = f"{description}\nThis position is not software-controllable."
        else:
            state = self.states.get(pin.bcm, {})
            mode = state.get("function", "?")
            mode_name = {"ip": "Input", "op": "Output", "no": "Unassigned"}.get(
                mode, f"Alternate function {mode[1:]}" if mode.startswith("a") else mode)
            pull = {"pu": "Pull-up", "pd": "Pull-down", "pn": "No pull"}.get(
                state.get("pull", "?"), "Unknown")
            detail = (f"BCM GPIO{pin.bcm}   ·   {word}\n"
                      f"Mode: {mode_name}   ·   {pull}\n{description}")
            if pin.number in (27, 28):
                detail += "\nReserved for HAT identification on many boards."
        self.selected_detail.configure(text=detail)

    def change_speed(self, _value: str) -> None:
        seconds = self.blink_seconds.get()
        self.speed_label.configure(text=f"{seconds:.1f} s on  ·  {seconds:.1f} s off")
        if self.led is not None:
            self.led.blink(on_time=seconds, off_time=seconds, background=True)

    def toggle_blink(self) -> None:
        if self.led is not None:
            self.stop_blink()
            return
        try:
            self.led = LED(17, initial_value=False)
            seconds = self.blink_seconds.get()
            self.led.blink(on_time=seconds, off_time=seconds, background=True)
            self.blink_button.configure(text="STOP BLINKING", bg=ERROR,
                                        activebackground="#ffbab5")
            self.blink_status.configure(text="●  BLINKING  ·  GPIO17 active", fg=HIGH)
            self.select_pin(PINS[10])
        except Exception as exc:
            self.stop_blink()
            messagebox.showerror("GPIO17 unavailable", str(exc))

    def stop_blink(self) -> None:
        if self.led is not None:
            try:
                self.led.off()
                self.led.close()
            finally:
                self.led = None
        self.blink_button.configure(text="START GPIO17 BLINK", bg=TEAL,
                                    activebackground="#9af2e4")
        self.blink_status.configure(text="●  OFF  ·  GPIO17 released", fg=MUTED)

    def close(self) -> None:
        if self.refresh_job is not None:
            self.root.after_cancel(self.refresh_job)
        if self.system_job is not None:
            self.root.after_cancel(self.system_job)
        self.system_executor.shutdown(wait=False, cancel_futures=True)
        if self.radio_job is not None:
            self.root.after_cancel(self.radio_job)
        self.radio_executor.shutdown(wait=False, cancel_futures=True)
        self.stop_blink()
        self.root.destroy()


def main() -> None:
    root = tk.Tk()
    ShieldStudio(root)
    root.mainloop()


if __name__ == "__main__":
    main()
