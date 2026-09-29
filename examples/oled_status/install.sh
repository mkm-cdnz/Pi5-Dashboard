#!/usr/bin/env bash
set -euo pipefail

repository_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
application_dir="$HOME/Applications/pi-oled-status-demo"

sudo apt-get update
sudo apt-get install -y i2c-tools python3-venv
mkdir -p "$application_dir"
python3 -m venv "$application_dir/.venv"
"$application_dir/.venv/bin/python" -m pip install luma.oled
install -m 0644 "$repository_dir/examples/oled_status/oled_status.py" \
    "$application_dir/oled_status.py"

echo "Installed OLED status demo in $application_dir"
echo "Run: cd $application_dir && .venv/bin/python oled_status.py --driver ssd1306 --address 0x3c"
