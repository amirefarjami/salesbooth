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
  libsdl2-mixer-2.0-0 libsdl2-ttf-2.0-0 \
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

# 5) kiosk boot tweaks: auto-login on tty1 not needed (fbcon service),
#    but silence HDMI blanking so the screen stays on:
if ! grep -q "chiz-kiosk-blanking" "$BOOT_CFG" 2>/dev/null; then
  sudo tee -a "$BOOT_CFG" >/dev/null <<'EOF'

# chiz-kiosk-blanking: keep HDMI alive for kiosk display
disable_overscan=1
hdmi_blanking=1
EOF
  echo "boot config updated (reboot needed)"
fi

# 6) temperature guard: log throttling; fan is wired to 5V/GPIO via MOSFET
#    (see docs/wiring.md). dtoverlay for PWM fan on GPIO 14 if desired:
#    echo "dtoverlay=gpio-fan,gpiopin=14,temp=60000" | sudo tee -a "$BOOT_CFG"

echo "== done =="
echo "kiosk:  systemctl status chiz-kiosk"
echo "admin:  http://chiz.local:8000/admin"
