#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="${AT_CANVAS_ROOT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
BRANDING_DIR="$ROOT_DIR/display-client/branding"
PLYMOUTH_DIR="/usr/share/plymouth/themes/at-canvas"
ASSET_DIR="/usr/share/at-canvas/branding"
LOGO_B64="$BRANDING_DIR/at-canvas-logo.png.b64"
LOGO_PNG="$ASSET_DIR/at-canvas-logo.png"

if [[ $EUID -ne 0 ]]; then
  echo "Run branding installer as root."
  exit 1
fi

if [[ ! -s "$LOGO_B64" ]]; then
  echo "ERROR: Missing AT Canvas logo source: $LOGO_B64"
  exit 1
fi

echo "=== AT Canvas boot branding install ==="
apt-get update
apt-get install -y plymouth plymouth-themes plymouth-label initramfs-tools

rm -rf "$PLYMOUTH_DIR"
install -d -m 755 "$PLYMOUTH_DIR" "$ASSET_DIR"

base64 -d "$LOGO_B64" > "$LOGO_PNG"
install -m 644 "$LOGO_PNG" "$PLYMOUTH_DIR/logo.png"

cat >"$PLYMOUTH_DIR/at-canvas.plymouth" <<'EOF'
[Plymouth Theme]
Name=AT Canvas
Description=AT Canvas Display OS boot splash
ModuleName=script

[script]
ImageDir=/usr/share/plymouth/themes/at-canvas
ScriptFile=/usr/share/plymouth/themes/at-canvas/at-canvas.script
EOF

cat >"$PLYMOUTH_DIR/at-canvas.script" <<'EOF'
Window.SetBackgroundTopColor(0.008, 0.010, 0.018);
Window.SetBackgroundBottomColor(0.008, 0.010, 0.018);

logo_image = Image("logo.png");
logo_sprite = Sprite(logo_image);
logo_sprite.SetX(Window.GetWidth() / 2 - logo_image.GetWidth() / 2);
logo_sprite.SetY(Window.GetHeight() / 2 - logo_image.GetHeight() / 2 - 28);
logo_sprite.SetZ(1000);

status = Image.Text("Starting AT Canvas...", 0.70, 0.72, 0.80);
status_sprite = Sprite(status);
status_sprite.SetX(Window.GetWidth() / 2 - status.GetWidth() / 2);
status_sprite.SetY(Window.GetHeight() / 2 + logo_image.GetHeight() / 2 + 12);
status_sprite.SetZ(1001);
EOF

chmod 644 "$PLYMOUTH_DIR/at-canvas.plymouth" "$PLYMOUTH_DIR/at-canvas.script" "$PLYMOUTH_DIR/logo.png"

# Set theme first, then explicitly rebuild every initramfs. Some Debian installs
# retain the previously selected distro theme if only the -R shortcut is used.
plymouth-set-default-theme at-canvas
update-initramfs -u -k all

# Ensure the kernel actually requests Plymouth during boot.
if [[ -f /etc/default/grub ]]; then
  if grep -q '^GRUB_CMDLINE_LINUX_DEFAULT=' /etc/default/grub; then
    sed -i 's/^GRUB_CMDLINE_LINUX_DEFAULT=.*/GRUB_CMDLINE_LINUX_DEFAULT="quiet splash loglevel=3 systemd.show_status=false rd.systemd.show_status=false vt.global_cursor_default=0"/' /etc/default/grub
  else
    echo 'GRUB_CMDLINE_LINUX_DEFAULT="quiet splash loglevel=3 systemd.show_status=false rd.systemd.show_status=false vt.global_cursor_default=0"' >> /etc/default/grub
  fi
  update-grub
fi

echo
echo "===== BRANDING VERIFY ====="
echo -n "Plymouth theme: "
plymouth-set-default-theme
ls -lah "$PLYMOUTH_DIR"
echo
echo "Initramfs entries:"
lsinitramfs "/boot/initrd.img-$(uname -r)" | grep -E 'at-canvas|plymouth/themes/at-canvas' | head -30 || true

echo
echo "AT Canvas boot branding installed successfully."
