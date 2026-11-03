#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
UNIT_SRC="$ROOT/deploy/bt-analyzer-controller.service"
UNIT_DST="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user/bt-analyzer-controller.service"
mkdir -p "$(dirname "$UNIT_DST")"
sed "s|%h|$HOME|g" "$UNIT_SRC" >"$UNIT_DST"
systemctl --user daemon-reload
systemctl --user enable --now bt-analyzer-controller.service
systemctl --user status bt-analyzer-controller.service --no-pager | head -20
echo "UI: http://$(hostname -I | awk '{print $1}'):8081/"
