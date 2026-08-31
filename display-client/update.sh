#!/usr/bin/env bash
set -euo pipefail

INSTALL_DIR="${AT_CANVAS_INSTALL_DIR:-/opt/at-canvas}"
BRANCH="${AT_CANVAS_UPDATE_BRANCH:-main}"

echo "=== AT Canvas Display Client update ==="

if [[ $EUID -ne 0 ]]; then
  echo "This updater must run as root."
  exit 1
fi

if [[ ! -d "$INSTALL_DIR/.git" ]]; then
  echo "AT Canvas repository not found at $INSTALL_DIR"
  exit 1
fi

git -C "$INSTALL_DIR" fetch --prune origin
git -C "$INSTALL_DIR" checkout "$BRANCH"
git -C "$INSTALL_DIR" reset --hard "origin/$BRANCH"

install -m 755 "$INSTALL_DIR/display-client/agent/at_canvas_client.py" /usr/local/bin/at_canvas_client.py
install -m 755 "$INSTALL_DIR/display-client/update.sh" /usr/local/sbin/at-canvas-update
install -m 644 "$INSTALL_DIR/display-client/systemd/at-canvas-client.service" /etc/systemd/system/at-canvas-client.service

systemctl daemon-reload
systemctl restart at-canvas-client.service

echo "AT Canvas Display Client updated successfully."
