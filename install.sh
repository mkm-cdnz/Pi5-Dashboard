#!/usr/bin/env bash
set -euo pipefail

repository_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
application_dir="$HOME/Applications/pi-gpio-dashboard"
desktop_dir="$HOME/Desktop"
menu_dir="$HOME/.local/share/applications"

python3 -c 'import tkinter, gpiozero' >/dev/null
for command_name in pinctrl nmcli bluetoothctl; do
    command -v "$command_name" >/dev/null || {
        echo "Missing required command: $command_name" >&2
        exit 1
    }
done

mkdir -p "$application_dir/assets" "$desktop_dir" "$menu_dir"
install -m 0644 "$repository_dir/pi_gpio_dashboard.py" "$application_dir/pi_gpio_dashboard.py"
install -m 0644 "$repository_dir/assets/pi-gpio-dashboard.svg" \
    "$application_dir/assets/pi-gpio-dashboard.svg"
sed "s|@APP_DIR@|$application_dir|g" \
    "$repository_dir/packaging/pi-gpio-dashboard.desktop" \
    > "$application_dir/pi-gpio-dashboard.desktop"
install -m 0755 "$application_dir/pi-gpio-dashboard.desktop" \
    "$desktop_dir/pi-gpio-dashboard.desktop"
install -m 0755 "$application_dir/pi-gpio-dashboard.desktop" \
    "$menu_dir/pi-gpio-dashboard.desktop"

echo "Installed Pi & GPIO Dashboard. Open it from the desktop icon."
