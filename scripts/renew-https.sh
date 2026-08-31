#!/usr/bin/env bash
set -euo pipefail

DOMAIN="${AT_CANVAS_DOMAIN:-atserver1.ddns.net}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CERT_DIR="$ROOT/data/certs"
LE_DIR="$ROOT/data/letsencrypt"

mkdir -p "$CERT_DIR" "$LE_DIR"

echo "===== AT Canvas HTTPS certificate renewal ====="
echo "WAN TCP 80 must currently forward to this server TCP 8080."
read -r -p "Press Enter when the port forward is ready... "

docker run --rm \
  -p 8080:8080 \
  -v "$LE_DIR:/etc/letsencrypt" \
  certbot/certbot:latest renew \
  --standalone \
  --http-01-port 8080

cp -L "$LE_DIR/live/$DOMAIN/fullchain.pem" "$CERT_DIR/fullchain.pem"
cp -L "$LE_DIR/live/$DOMAIN/privkey.pem" "$CERT_DIR/privkey.pem"
chmod 644 "$CERT_DIR/fullchain.pem"
chmod 600 "$CERT_DIR/privkey.pem"

cd "$ROOT"
docker compose --profile https restart at-canvas-https

echo "HTTPS certificate renewal complete."
