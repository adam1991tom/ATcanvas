#!/usr/bin/env bash
set -euo pipefail

DOMAIN="${AT_CANVAS_DOMAIN:-atserver1.ddns.net}"
EMAIL="${1:-}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CERT_DIR="$ROOT/data/certs"
LE_DIR="$ROOT/data/letsencrypt"

if [[ -z "$EMAIL" ]]; then
  echo "Usage: $0 your-email@example.com"
  echo ""
  echo "Before running this, forward WAN TCP port 80 to this server TCP port 8080."
  exit 1
fi

mkdir -p "$CERT_DIR" "$LE_DIR"

echo "===== AT Canvas HTTPS certificate setup ====="
echo "Domain: $DOMAIN"
echo "Challenge listener: host TCP 8080"
echo ""
echo "Google/Let's Encrypt will contact: http://$DOMAIN/.well-known/acme-challenge/... on WAN port 80"
echo "Your router must forward WAN TCP 80 -> this server TCP 8080 while this command runs."
echo
read -r -p "Press Enter when the port forward is ready... "

docker run --rm \
  -p 8080:8080 \
  -v "$LE_DIR:/etc/letsencrypt" \
  certbot/certbot:latest certonly \
  --standalone \
  --http-01-port 8080 \
  --non-interactive \
  --agree-tos \
  --email "$EMAIL" \
  -d "$DOMAIN"

cp -L "$LE_DIR/live/$DOMAIN/fullchain.pem" "$CERT_DIR/fullchain.pem"
cp -L "$LE_DIR/live/$DOMAIN/privkey.pem" "$CERT_DIR/privkey.pem"
chmod 644 "$CERT_DIR/fullchain.pem"
chmod 600 "$CERT_DIR/privkey.pem"

echo
echo "Certificate installed in $CERT_DIR"
echo "Starting AT Canvas HTTPS on port 8078..."
cd "$ROOT"
docker compose --profile https up -d --build

echo
echo "Test locally with:"
echo "  curl -I https://$DOMAIN:8078"
echo
echo "Google OAuth redirect URI:"
echo "  https://$DOMAIN:8078/api/google/callback"
