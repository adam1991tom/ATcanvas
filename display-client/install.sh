#!/usr/bin/env bash
set -euo pipefail

REPO_URL="${AT_CANVAS_REPO_URL:-https://github.com/adam1991tom/ATcanvas.git}"
INSTALL_DIR="${AT_CANVAS_INSTALL_DIR:-/opt/at-canvas}"
BRANCH="${AT_CANVAS_BRANCH:-main}"
SERVER_URL="${AT_CANVAS_SERVER:-http://10.0.0.2:8077}"
KIOSK_USER="${AT_CANVAS_KIOSK_USER:-atcanvas}"

if [[ $EUID -ne 0 ]]; then
  echo "Run with sudo: sudo bash display-client/install.sh"
  exit 1
fi

echo "=== AT Canvas Display Client installer ==="
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y python3 git curl xserver-xorg x11-xserver-utils openbox lightdm unclutter
if apt-cache show chromium >/dev/null 2>&1; then
  apt-get install -y chromium
elif apt-cache show chromium-browser >/dev/null 2>&1; then
  apt-get install -y chromium-browser
else
  echo "WARNING: Chromium package not found automatically. Install Chromium before rebooting."
fi

if ! id "$KIOSK_USER" >/dev/null 2>&1; then
  useradd -m -s /bin/bash "$KIOSK_USER"
fi

if [[ -d "$INSTALL_DIR/.git" ]]; then
  git -C "$INSTALL_DIR" fetch origin
  git -C "$INSTALL_DIR" checkout -B "$BRANCH" "origin/$BRANCH"
  git -C "$INSTALL_DIR" reset --hard "origin/$BRANCH"
else
  rm -rf "$INSTALL_DIR"
  git clone --branch "$BRANCH" --single-branch "$REPO_URL" "$INSTALL_DIR"
fi

install -d -m 700 /var/lib/at-canvas
install -m 755 "$INSTALL_DIR/display-client/agent/at_canvas_client.py" /usr/local/bin/at_canvas_client.py
install -m 755 "$INSTALL_DIR/display-client/update.sh" /usr/local/sbin/at-canvas-update
install -m 644 "$INSTALL_DIR/display-client/systemd/at-canvas-client.service" /etc/systemd/system/at-canvas-client.service

install -d -m 755 /etc/at-canvas
cat >/etc/at-canvas/client.env <<EOF
AT_CANVAS_SERVER=$SERVER_URL
AT_CANVAS_STATE_DIR=/var/lib/at-canvas
AT_CANVAS_KIOSK_USER=$KIOSK_USER
AT_CANVAS_AUTO_LAUNCH=1
AT_CANVAS_UPDATE_BRANCH=$BRANCH
TZ=Europe/London
DISPLAY=:0
XAUTHORITY=/home/$KIOSK_USER/.Xauthority
EOF

install -d -m 755 "/home/$KIOSK_USER/.config/openbox"
cat >"/home/$KIOSK_USER/.config/openbox/autostart" <<'EOF'
xset s off
xset -dpms
xset s noblank
unclutter -idle 0.3 -root &
EOF
chown -R "$KIOSK_USER:$KIOSK_USER" "/home/$KIOSK_USER/.config"

cat >/etc/lightdm/lightdm.conf.d/50-at-canvas.conf <<EOF
[Seat:*]
autologin-user=$KIOSK_USER
autologin-user-timeout=0
user-session=openbox
EOF

systemctl daemon-reload
systemctl enable at-canvas-client.service
systemctl enable lightdm.service
systemctl restart at-canvas-client.service

echo
echo "AT Canvas Display Client installed."
echo "Branch: $BRANCH"
echo "Server: $SERVER_URL"
echo "Local client status: http://127.0.0.1:8787"
echo "Reboot the display to enter kiosk mode: sudo reboot"
