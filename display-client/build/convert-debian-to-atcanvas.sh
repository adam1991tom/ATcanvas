#!/usr/bin/env bash
set -euo pipefail

SERVER_URL="${AT_CANVAS_SERVER:-http://10.0.0.2:8077}"
BRANCH="${AT_CANVAS_BRANCH:-display-client-v0.2-appliance}"
REPO_URL="${AT_CANVAS_REPO_URL:-https://github.com/adam1991tom/ATcanvas.git}"
INSTALL_DIR="${AT_CANVAS_INSTALL_DIR:-/opt/at-canvas}"
KIOSK_USER="${AT_CANVAS_KIOSK_USER:-atcanvas}"

if [[ $EUID -ne 0 ]]; then
  echo "Run this script with sudo/root."
  exit 1
fi

. /etc/os-release
if [[ "${ID:-}" != "debian" ]]; then
  echo "ERROR: This conversion build currently supports Debian only."
  exit 1
fi

echo "===================================================="
echo " AT Canvas Display OS - Debian conversion build"
echo "===================================================="
echo "Debian: ${VERSION:-unknown}"
echo "Server: $SERVER_URL"
echo "Branch: $BRANCH"
echo

export DEBIAN_FRONTEND=noninteractive

# Keep remote recovery available before touching the desktop stack.
apt-get update
apt-get install -y openssh-server ca-certificates curl git python3 dbus-x11 xserver-xorg-core xserver-xorg-input-libinput x11-xserver-utils xinit openbox unclutter chromium fonts-noto-core
systemctl enable --now ssh.service

# Dedicated, non-login-style kiosk account. It owns only the graphical session.
if ! id "$KIOSK_USER" >/dev/null 2>&1; then
  useradd -m -s /bin/bash "$KIOSK_USER"
fi

# Pull the exact AT Canvas build being converted.
if [[ -d "$INSTALL_DIR/.git" ]]; then
  git -C "$INSTALL_DIR" fetch --prune origin
  git -C "$INSTALL_DIR" checkout -B "$BRANCH" "origin/$BRANCH"
  git -C "$INSTALL_DIR" reset --hard "origin/$BRANCH"
else
  rm -rf "$INSTALL_DIR"
  git clone --branch "$BRANCH" --single-branch "$REPO_URL" "$INSTALL_DIR"
fi

install -d -m 700 /var/lib/at-canvas
install -d -m 755 /etc/at-canvas
install -m 755 "$INSTALL_DIR/display-client/agent/at_canvas_client.py" /usr/local/bin/at_canvas_client.py
install -m 755 "$INSTALL_DIR/display-client/update.sh" /usr/local/sbin/at-canvas-update

cat >/etc/at-canvas/client.env <<EOF
AT_CANVAS_SERVER=$SERVER_URL
AT_CANVAS_STATE_DIR=/var/lib/at-canvas
AT_CANVAS_KIOSK_USER=$KIOSK_USER
AT_CANVAS_AUTO_LAUNCH=0
AT_CANVAS_UPDATE_BRANCH=$BRANCH
TZ=Europe/London
DISPLAY=:0
XAUTHORITY=/home/$KIOSK_USER/.Xauthority
EOF

# X session: no desktop environment, panel, launcher, wallpaper app or login manager.
cat >"/home/$KIOSK_USER/.xinitrc" <<'EOF'
#!/bin/sh
xset s off
xset -dpms
xset s noblank
xsetroot -solid black
unclutter -idle 0.2 -root &
exec openbox-session
EOF
chmod 755 "/home/$KIOSK_USER/.xinitrc"
chown "$KIOSK_USER:$KIOSK_USER" "/home/$KIOSK_USER/.xinitrc"

install -d -m 755 "/home/$KIOSK_USER/.config/openbox"
cat >"/home/$KIOSK_USER/.config/openbox/autostart" <<'EOF'
/usr/bin/chromium \
  --kiosk \
  --no-first-run \
  --disable-session-crashed-bubble \
  --disable-infobars \
  --disable-translate \
  --disable-pinch \
  --overscroll-history-navigation=0 \
  --autoplay-policy=no-user-gesture-required \
  http://127.0.0.1:8787 &
EOF
chown -R "$KIOSK_USER:$KIOSK_USER" "/home/$KIOSK_USER/.config"

cat >/etc/systemd/system/at-canvas-client.service <<'EOF'
[Unit]
Description=AT Canvas Display Client
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
EnvironmentFile=-/etc/at-canvas/client.env
ExecStart=/usr/local/bin/at_canvas_client.py
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

cat >/etc/systemd/system/at-canvas-display.service <<EOF
[Unit]
Description=AT Canvas Display Engine
After=systemd-user-sessions.service network-online.target at-canvas-client.service
Wants=network-online.target at-canvas-client.service
Conflicts=getty@tty1.service

[Service]
User=$KIOSK_USER
PAMName=login
TTYPath=/dev/tty1
StandardInput=tty
StandardOutput=journal
StandardError=journal
Environment=HOME=/home/$KIOSK_USER
Environment=DISPLAY=:0
ExecStart=/usr/bin/startx /home/$KIOSK_USER/.xinitrc -- :0 -nolisten tcp vt1 -keeptty
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

# Console/boot appliance behaviour.
mkdir -p /etc/systemd/system/getty@tty1.service.d
cat >/etc/systemd/system/getty@tty1.service.d/disable.conf <<'EOF'
[Unit]
ConditionPathExists=/nonexistent-at-canvas-console
EOF

# Make the boot quieter without removing recovery options from GRUB.
if [[ -f /etc/default/grub ]]; then
  sed -i 's/^GRUB_TIMEOUT=.*/GRUB_TIMEOUT=0/' /etc/default/grub || true
  if grep -q '^GRUB_CMDLINE_LINUX_DEFAULT=' /etc/default/grub; then
    sed -i 's/^GRUB_CMDLINE_LINUX_DEFAULT=.*/GRUB_CMDLINE_LINUX_DEFAULT="quiet loglevel=3 systemd.show_status=false vt.global_cursor_default=0"/' /etc/default/grub
  fi
  update-grub || true
fi

# We no longer need a graphical login manager. Disable it before removing GNOME.
systemctl disable --now gdm.service gdm3.service display-manager.service 2>/dev/null || true

# Remove the desktop metapackages and the visible GNOME shell/login stack.
# apt autoremove then removes dependencies that are no longer required, while
# the kiosk packages installed above are explicitly marked as installed.
apt-get purge -y gnome gnome-core gnome-shell gnome-session gnome-session-bin gnome-session-xsession gdm3 gnome-software gnome-terminal gnome-tour 2>/dev/null || true
apt-get autoremove --purge -y
apt-get clean

systemctl daemon-reload
systemctl set-default multi-user.target
systemctl enable at-canvas-client.service at-canvas-display.service ssh.service
systemctl restart at-canvas-client.service

# Branding used by console/system identification.
echo "AT Canvas Display OS" >/etc/issue
cat >/etc/at-canvas/os-release <<EOF
NAME="AT Canvas Display OS"
VERSION="0.1 Development"
ID=atcanvas-display
BASE="Debian ${VERSION_ID:-13}"
ARCH="$(dpkg --print-architecture)"
EOF

echo
echo "===================================================="
echo " AT Canvas Display OS conversion complete"
echo "===================================================="
echo "SSH remains enabled for development."
echo "AT Canvas server: $SERVER_URL"
echo "The GNOME desktop/login manager has been removed."
echo "On reboot the machine will start the AT Canvas display engine directly."
echo
echo "REBOOT WHEN READY: sudo reboot"
