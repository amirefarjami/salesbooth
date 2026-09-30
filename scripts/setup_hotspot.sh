#!/usr/bin/env bash
# CHIZ Booth — WiFi hotspot + uplink internet (NetworkManager).
#
# Makes the Pi broadcast "CHIZ-BOOTH" while staying connected to the
# internet on the built-in WiFi (Pi 3 B+/4 support AP+client at once on
# different channels) OR via Ethernet. The seller joins the hotspot and
# opens http://chiz.local:8000
#
# Usage:
#   bash scripts/setup_hotspot.sh "CHIZ-BOOTH" "chiz1390" "wlan0"
#   bash scripts/setup_hotspot.sh off          # revert to managed mode
set -euo pipefail

SSID="${1:-CHIZ-BOOTH}"
PASS="${2:-chiz1390}"
IFACE="${3:-wlan0}"

nmcli connection delete chiz-hotspot >/dev/null 2>&1 || true

if [ "$SSID" = "off" ]; then
  echo "Reverting $IFACE to managed (client) mode"
  nmcli device wifi connect "$SSID" || true
  exit 0
fi

[ ${#PASS} -ge 8 ] || { echo "password must be >= 8 chars"; exit 1; }

echo "Creating hotspot $SSID on $IFACE ..."
nmcli connection add type wifi ifname "$IFACE" con-name chiz-hotspot \
  autoconnect yes ssid "$SSID" \
  802-11-wireless.mode ap 802-11-wireless-band bg \
  802-11-wireless-security.key-mgmt wpa-psk \
  802-11-wireless-security.psk "$PASS" \
  ipv4.method shared \
  ipv4.addresses 10.42.0.1/24

nmcli connection up chiz-hotspot

echo
echo "Hotspot up:  SSID=$SSID  pass=$PASS"
echo "Panel:       http://10.42.0.1:8000/admin  (or http://chiz.local:8000)"
echo
echo "Internet uplink: connect Ethernet (recommended) or join your 4G router"
echo "from the Pi's second radio with:  nmcli device wifi connect <SSID> password <pass>"
