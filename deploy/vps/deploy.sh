#!/usr/bin/env bash
set -euo pipefail

APP_DIR="/opt/virtual-character-life-system"
REPO_URL="${REPO_URL:-https://github.com/zhengquanwei6-crypto/virtual-character-life-system.git}"
VERSION="${VERSION:-main}"

mkdir -p "$APP_DIR/releases" "$APP_DIR/shared/data" "$APP_DIR/backups"

if [ -d "$APP_DIR/current/.git" ]; then
  "$APP_DIR/current/deploy/vps/backup.sh" "$VERSION" || true
fi

rm -rf "$APP_DIR/releases/$VERSION"
git clone --depth 1 --branch "$VERSION" "$REPO_URL" "$APP_DIR/releases/$VERSION" 2>/dev/null || \
git clone --depth 1 --branch "${VERSION#v}" "$REPO_URL" "$APP_DIR/releases/$VERSION" 2>/dev/null || \
git clone --depth 1 "$REPO_URL" "$APP_DIR/releases/$VERSION"

ln -sfn "$APP_DIR/releases/$VERSION" "$APP_DIR/current"

if [ ! -f "$APP_DIR/shared/backend.env" ]; then
  cp "$APP_DIR/current/deploy/vps/backend.env.example" "$APP_DIR/shared/backend.env"
  echo "Created $APP_DIR/shared/backend.env. Edit it before enabling real LLM/ComfyUI."
fi

cd "$APP_DIR/current"
docker compose -f deploy/vps/docker-compose.yml up -d --build
docker compose -f deploy/vps/docker-compose.yml ps
