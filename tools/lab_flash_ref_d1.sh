#!/usr/bin/env bash
# OTA esp-hub-base (classic ESP32) onto lab D1 Mini (.87) as REF_ENDPOINT.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
IP="${1:-192.168.178.87}"
BASE_BIN="${BASE_BIN:-/home/martin/projects/esphub/ESP32.esp-hub/esp-hub-base.1.10.5.esp32.bin}"
[[ -f "$BASE_BIN" ]] || { echo "fehlt $BASE_BIN" >&2; exit 1; }
BIN_SRC="$BASE_BIN" FW_NAME="esp-hub-base.1.10.5.esp32.bin" \
  exec "$ROOT/tools/flash_lab_ota.sh" "$IP"
