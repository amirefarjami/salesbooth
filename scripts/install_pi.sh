#!/usr/bin/env bash
# CHIZ Booth — Raspberry Pi installer.
# Run from the repo root on the Pi:   bash scripts/install_pi.sh
# Assumes Raspberry Pi OS Bookworm (Lite or Desktop) and user 'pi'.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SERVICE_DIR=/etc/systemd/system
BOOT_CFG=/boot/firmware/config.txt
[ -f /boot/config.txt ] && BOOT_CFG=/boot/config.txt

echo "== CHIZ Booth installer =="
echo "repo: $REPO_DIR"

# 1) system packages -------------------------------------------------------
sudo apt-get update -y
sudo apt-get install -y \
  python3-venv python3-pip python3-pygame \
  avahi-daemon \
  libsdl2-2.0-0 libsdl2-mixer-2.0-0 libsdl2-ttf-2.0-0 \
  python3-lgpio \
  network-manager

# 2) python venv + deps ----------------------------------------------------
cd "$REPO_DIR"
python3 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt || {
  echo "pygame-ce wheel failed; falling back to system pygame"
  .venv/bin/pip install --no-deps arabic-reshaper python-bidi fastapi \
    "uvicorn[standard]" jinja2 python-multipart httpx Pillow
  sudo mkdir -p /usr/local/lib/python3.11/dist-packages_link
  echo "link system pygame into venv manually if needed"
}

# 3) fonts -----------------------------------------------------------------
.venv/bin/python scripts/fetch_fonts.py || echo "fonts: download manually (see assets/fonts/README.md)"

# 4) services ---------------------------------------------------------------
sudo cp deploy/chiz-kiosk.service deploy/chiz-admin.service "$SERVICE_DIR/"
sudo sed -i "s|/home/pi/salesbooth|$REPO_DIR|g" "$SERVICE_DIR/chiz-kiosk.service" "$SERVICE_DIR/chiz-admin.service"
sudo systemctl daemon-reload
sudo systemctl enable --now chiz-admin
sudo systemctl enable --now chiz-kiosk

# 5) kiosk boot tweaks: keep the screen on (no console blanking) and let
#    the kiosk user reach the display, input and GPIO devices.
#    (hdmi_blanking=1 in config.txt does the opposite: it ALLOWS blanking.)
CMDLINE=/boot/firmware/cmdline.txt
[ -f "$CMDLINE" ] || CMDLINE=/boot/cmdline.txt
if [ -f "$CMDLINE" ] && ! grep -q "consoleblank=0" "$CMDLINE"; then
  sudo sed -i '1 s/$/ consoleblank=0/' "$CMDLINE"
  echo "cmdline: consoleblank=0 (reboot needed)"
fi
sudo sed -i '/chiz-kiosk-blanking/,+2d' "$BOOT_CFG" 2>/dev/null || true
sudo usermod -aG video,render,input,audio,gpio "$(id -un)" || true

# 6) temperature guard: log throttling; fan is wired to 5V/GPIO via MOSFET
#    (see docs/wiring.md). dtoverlay for PWM fan on GPIO 14 if desired:
#    echo "dtoverlay=gpio-fan,gpiopin=14,temp=60000" | sudo tee -a "$BOOT_CFG"

echo "== done =="
echo "kiosk:  systemctl status chiz-kiosk"
echo "admin:  http://chiz.local:8000/admin"
