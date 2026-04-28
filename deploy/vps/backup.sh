#!/usr/bin/env bash
set -euo pipefail

APP_DIR="/opt/virtual-character-life-system"
BACKUP_DIR="$APP_DIR/backups"
VERSION="${1:-manual}"
STAMP="$(date +%Y%m%d-%H%M%S)"
TARGET="$BACKUP_DIR/${STAMP}-${VERSION}.tar.gz"

mkdir -p "$BACKUP_DIR"
tar -czf "$TARGET" \
  -C "$APP_DIR" \
  --exclude='backups' \
  shared || true

echo "$TARGET"

