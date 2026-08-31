#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="${AT_CANVAS_ROOT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
BRANDING_DIR="$ROOT_DIR/display-client/branding"
PLYMOUTH_DIR="/usr/share/plymouth/themes/at-canvas"
ASSET_DIR="/usr/share/at-canvas/branding"

if [[ $EUID -ne 0 ]]; then
  echo "Run branding installer as root."
  exit 1
fi

apt-get install -y plymouth plymouth-themes
install -d -m 755 "$PLYMOUTH_DIR" "$ASSET_DIR"

base64 -d "$BRANDING_DIR/at-canvas-logo.png.b64" > "$ASSET_DIR/at-canvas-logo.png"
install -m 644 "$ASSET_DIR/at-canvas-logo.png" "$PLYMOUTH_DIR/logo.png"

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
Window.SetBackgroundTopColor(0.015, 0.018, 0.030);
Window.SetBackgroundBottomColor(0.015, 0.018, 0.030);

logo_image = Image("logo.png");
logo_sprite = Sprite(logo_image);
logo_sprite.SetX(Window.GetWidth() / 2 - logo_image.GetWidth() / 2);
logo_sprite.SetY(Window.GetHeight() / 2 - logo_image.GetHeight() / 2 - 40);
logo_sprite.SetZ(1000);

status = Image.Text("Starting AT Canvas...", 0.72, 0.72, 0.78);
status_sprite = Sprite(status);
status_sprite.SetX(Window.GetWidth() / 2 - status.GetWidth() / 2);
status_sprite.SetY(Window.GetHeight() / 2 + logo_image.GetHeight() / 2 - 5);
status_sprite.SetZ(1001);
EOF

plymouth-set-default-theme -R at-canvas

echo "AT Canvas boot branding installed."
