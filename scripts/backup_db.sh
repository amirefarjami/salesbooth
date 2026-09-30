#!/usr/bin/env bash
# CHIZ Booth — database backup with rotation (keeps 8 copies).
# Intended to run weekly from cron/systemd timer on the Pi:
#   sudo cp deploy/chiz-backup.timer deploy/chiz-backup.service /etc/systemd/system/
#   sudo systemctl enable --now chiz-backup.timer
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DB="$REPO_DIR/data/booth.db"
BACKUP_DIR="$REPO_DIR/data/backups"
KEEP=8

mkdir -p "$BACKUP_DIR"
STAMP="$(date +%Y-%m-%d_%H%M)"
DEST="$BACKUP_DIR/booth-$STAMP.db"

# Safe online backup (works while the kiosk/panel hold the DB open)
if command -v sqlite3 >/dev/null; then
  sqlite3 "$DB" ".backup '$DEST'"
else
  cp "$DB" "$DEST"
fi
gzip -f "$DEST"

# rotate
ls -1t "$BACKUP_DIR"/booth-*.db.gz 2>/dev/null | tail -n +$((KEEP + 1)) | xargs -r rm --
echo "backup written: $DEST.gz"
