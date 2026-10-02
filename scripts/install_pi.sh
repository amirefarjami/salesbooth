#!/usr/bin/env bash
# CHIZ Booth — Raspberry Pi installer (Raspberry Pi OS Bookworm, 64-bit).
#
#   bash scripts/install_pi.sh --test    deps + demo products only; nothing
#                                        starts at boot. Try it on the Pi's
#                                        desktop with:  make sim
#   bash scripts/install_pi.sh           full kiosk: services (kiosk, admin
#                                        panel, weekly backup), console boot,
#                                        screen never blanks. Reboot after.
#
# Safe to run again (idempotent). Works for any username (not only "pi").
# Full guide: docs/setup-pi.md
set -euo pipefail

MODE="kiosk"
[ "${1:-}" = "--test" ] && MODE="test"

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUN_USER="$(id -un)"
SERVICE_DIR=/etc/systemd/system
BOOT_DIR=/boot/firmware
[ -d "$BOOT_DIR" ] || BOOT_DIR=/boot

echo "== CHIZ Booth installer ($MODE) =="
echo "repo: $REPO_DIR   user: $RUN_USER"
[ "$RUN_USER" = "root" ] && { echo "run as your normal user (it uses sudo itself)"; exit 1; }

# 1) system packages -------------------------------------------------------
# No python3-pygame here: the venv uses pygame-ce and both import "pygame".
sudo apt-get update -y
sudo apt-get install -y \
  git python3-venv python3-pip python3-dev build-essential \
  libsdl2-2.0-0 libsdl2-image-2.0-0 libsdl2-mixer-2.0-0 libsdl2-ttf-2.0-0 \
  python3-lgpio sqlite3 avahi-daemon network-manager

# 2) python venv + deps ----------------------------------------------------
# --system-site-packages: lets the venv see apt's python3-lgpio (the GPIO
# backend gpiozero uses on Pi 3/4/5); everything else comes from pip.
cd "$REPO_DIR"
if [ ! -x .venv/bin/python ]; then
  python3 -m venv --system-site-packages .venv
fi
.venv/bin/pip install --upgrade pip wheel
.venv/bin/pip install -r requirements.txt

# 3) fonts -----------------------------------------------------------------
.venv/bin/python scripts/fetch_fonts.py || echo "!! fonts: see assets/fonts/README.md"
if [ ! -f assets/fonts/SSINABD.TTF ]; then
  echo "!! brand font missing: copy SSINABD.TTF into $REPO_DIR/assets/fonts/"
  echo "   (titles fall back to Lalezar until then)"
fi

# 4) config ----------------------------------------------------------------
if [ ! -f booth.toml ]; then
  cp booth.toml.example booth.toml
  if [ "$MODE" = "kiosk" ]; then
    sed -i 's/^fullscreen = false/fullscreen = true/' booth.toml
  fi
  echo "created booth.toml (edit it: payment, GPIO pins, screen_rotate)"
fi

# 5) user groups: display, input, sound, GPIO ------------------------------
sudo usermod -aG video,render,input,audio,gpio "$RUN_USER" || true

if [ "$MODE" = "test" ]; then
  # demo catalog with generated product pictures
  .venv/bin/python scripts/render_preview.py >/dev/null && echo "demo products added"
  echo
  echo "== test install done =="
  echo "on the Pi desktop:   cd $REPO_DIR && make sim        (window 480x800)"
  echo "admin panel:         make panel   →  http://$(hostname).local:8000/admin  (PIN 1390)"
  exit 0
fi

# 6) services --------------------------------------------------------------
for unit in chiz-kiosk.service chiz-admin.service chiz-backup.service chiz-backup.timer; do
  sed -e "s|/home/pi/salesbooth|$REPO_DIR|g" -e "s|^User=pi$|User=$RUN_USER|" \
      "deploy/$unit" | sudo tee "$SERVICE_DIR/$unit" >/dev/null
done
sudo systemctl daemon-reload
sudo systemctl enable chiz-admin chiz-kiosk chiz-backup.timer

# 7) kiosk boot ------------------------------------------------------------
# The kiosk draws straight to the screen (SDL kmsdrm), which needs the
# desktop out of the way: boot to the console instead of the desktop.
if [ "$(systemctl get-default)" = "graphical.target" ]; then
  sudo systemctl set-default multi-user.target
  echo "boot target: console (undo: sudo systemctl set-default graphical.target)"
fi
CMDLINE="$BOOT_DIR/cmdline.txt"
if [ -f "$CMDLINE" ] && ! grep -q "consoleblank=0" "$CMDLINE"; then
  sudo sed -i '1 s/$/ consoleblank=0/' "$CMDLINE"      # screen never blanks
fi
sudo sed -i '/chiz-kiosk-blanking/,+2d' "$BOOT_DIR/config.txt" 2>/dev/null || true

echo
echo "== kiosk install done — reboot now:  sudo reboot =="
echo "status:  systemctl status chiz-kiosk chiz-admin"
echo "logs:    journalctl -u chiz-kiosk -f"
echo "panel:   http://$(hostname).local:8000/admin  (PIN 1390 — change it)"
