#!/usr/bin/env bash
# OTA flash onto a lab ESP (esp-hub LocalWeb contract).
#
# Contract:
#   GET  http://$IP/api/status   → 200
#   POST http://$IP/ota-upload   multipart field "firmware"
#
# Default: bt-analyzer.${VERSION}.esp32s3.bin from analyzer-s3 build.
#
# Usage:
#   ./tools/flash_lab_ota.sh 192.168.178.88
#   ./tools/flash_lab_ota.sh 192.168.178.89
#   BIN_SRC=/path/to/esp-hub-base.1.10.5.esp32.bin FW_NAME=esp-hub-base.1.10.5.esp32.bin \
#     ./tools/flash_lab_ota.sh 192.168.178.87
#
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
IP="${1:-}"
ENV_NAME="${ENV:-analyzer-s3}"
VERSION="$(tr -d '[:space:]' <"$ROOT/VERSION")"
BIN_SRC="${BIN_SRC:-$ROOT/firmware/analyzer-node/.pio/build/${ENV_NAME}/firmware.bin}"
FW_NAME="${FW_NAME:-bt-analyzer.${VERSION}.esp32s3.bin}"
DIST="$ROOT/firmware/dist"

die() { echo "Fehler: $*" >&2; exit 1; }
[ -n "$IP" ] || die "IP fehlt (z.B. 192.168.178.88)"
[ -f "$BIN_SRC" ] || die "Bin fehlt: $BIN_SRC — zuerst bauen oder BIN_SRC setzen"

mkdir -p "$DIST"
cp -f "$BIN_SRC" "$DIST/$FW_NAME"
echo "==> target http://$IP/ota-upload"
echo "    file $DIST/$FW_NAME ($(wc -c <"$DIST/$FW_NAME") bytes)"

code="$(curl -sS -m 3 -o /dev/null -w '%{http_code}' "http://$IP/api/status" || true)"
[ "$code" = "200" ] || die "ESP $IP nicht erreichbar (HTTP $code)"

tmp="$(mktemp)"
set +e
http="$(curl -sS -m 180 -o "$tmp" -w '%{http_code}' \
  -F "firmware=@${DIST}/${FW_NAME};filename=${FW_NAME}" \
  "http://${IP}/ota-upload")"
set -e
echo "    HTTP $http  body=$(head -c 200 "$tmp")"
rm -f "$tmp"
[ "$http" = "200" ] || die "OTA fehlgeschlagen"

echo "    Upload OK — ESP rebootet."
sleep 8
if curl -sS -m 5 "http://${IP}/api/status" >/dev/null 2>&1; then
  echo "    /api/status wieder erreichbar:"
  curl -sS -m 5 "http://${IP}/api/status" | head -c 400
  echo
else
  echo "    Warte auf WiFi — prüfe Serial / Hub"
fi
exit 0
