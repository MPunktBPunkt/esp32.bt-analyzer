#!/usr/bin/env bash
# Prepare .108 lab for home session: sync tools, eligibility, f20_sim HU + btmon.
# Usage:
#   ./tools/lab_home_session_prep.sh
#   ./tools/lab_home_session_prep.sh --w0-usb
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HOST="${LAB_HOST:-root@192.168.178.108}"
HU_BD="${HU_BD:-C8:C9:A3:CB:7B:0A}"
USB_BD="${USB_BD:-C0:B8:83:34:F4:62}"
W0_USB=0
for a in "$@"; do
  case "$a" in
    --w0-usb) W0_USB=1 ;;
  esac
done

echo "==> sync tools → $HOST:/tmp/bcl_dummy"
scp -o BatchMode=yes \
  "$ROOT/tools/bcl_dummy_hu.py" \
  "$ROOT/tools/bcl_dummy_hu_agent.py" \
  "$ROOT/tools/bcl_etch_stub.py" \
  "$ROOT/tools/etch_codec.py" \
  "$ROOT/tools/bcl_framer.py" \
  "$ROOT/tools/lab_w0_reply_forensic.py" \
  "$HOST:/tmp/bcl_dummy/"
ssh -o BatchMode=yes "$HOST" 'mkdir -p /tmp/bcl_dummy/fixtures /tmp/bcl_dummy/home_session'
scp -o BatchMode=yes \
  "$ROOT/tools/fixtures/rhmi_description_lab_13598.xml" \
  "$HOST:/tmp/bcl_dummy/fixtures/" 2>/dev/null || true

echo "==> eligibility + start HU f20_sim SCN6 + btmon"
ssh -o BatchMode=yes "$HOST" bash -s << EOF
set +e
cd /tmp/bcl_dummy
pkill -f "bcl_dummy_hu_agent.py hu" 2>/dev/null
# leave sticky btmon alone if already writing FIELD_BURST; start dedicated home btmon
HU_BD="$HU_BD"
USB_BD="$USB_BD"
STAMP=\$(date -u +%Y%m%dT%H%MZ)
OUT=/tmp/bcl_dummy/home_session/\$STAMP
mkdir -p "\$OUT"

# Resolve which hci is HU
HU_HCI=
for i in 0 1 2; do
  bd=\$(hciconfig hci\$i 2>/dev/null | awk '/BD Address/{print \$3}')
  if [ "\$bd" = "\$HU_BD" ]; then HU_HCI=hci\$i; break; fi
done
echo "HU_HCI=\$HU_HCI BD=\$HU_BD"
[ -n "\$HU_HCI" ] || { echo "HU controller not found"; exit 1; }

bluetoothctl select \$HU_BD >/dev/null
bluetoothctl power on >/dev/null
bluetoothctl system-alias "BMW 38304" >/dev/null
bluetoothctl discoverable on >/dev/null
bluetoothctl pairable on >/dev/null
hciconfig \$HU_HCI name "BMW 38304" class 0x340408 piscan 2>/dev/null
# keep CoD pinned in background
pkill -f "cod_pin_home" 2>/dev/null
(
  while true; do
    hciconfig \$HU_HCI class 0x340408 >/dev/null 2>&1
    bluetoothctl select \$HU_BD >/dev/null 2>&1
    bluetoothctl system-alias "BMW 38304" >/dev/null 2>&1
    sleep 5
  done
) >/tmp/bcl_dummy/cod_pin_home.log 2>&1 &
echo \$! > /tmp/bcl_dummy/cod_pin_home.pid

# Phone alias on USB / .87 so they are not both "BMW"
bluetoothctl select C8:C9:A3:CB:37:96 >/dev/null 2>&1
bluetoothctl system-alias "BT-Analyzer-Phone" >/dev/null 2>&1
bluetoothctl select \$USB_BD >/dev/null 2>&1
bluetoothctl system-alias "BT-Analyzer-Phone" >/dev/null 2>&1
bluetoothctl select \$HU_BD >/dev/null

rm -f /tmp/bcl_dummy/hu_home.jsonl /tmp/bcl_dummy/hu_home.ready
nohup python3 /tmp/bcl_dummy/bcl_dummy_hu_agent.py hu \
  --hu-profile f20_sim --channel 6 --name "BMW 38304" \
  --hold 7200 \
  --log /tmp/bcl_dummy/hu_home.jsonl \
  --ready /tmp/bcl_dummy/hu_home.ready \
  --session-id LAB_HOME_\$STAMP \
  > /tmp/bcl_dummy/hu_home.out 2>&1 &
echo \$! > /tmp/bcl_dummy/hu_home.pid
for i in \$(seq 1 40); do
  [ -f /tmp/bcl_dummy/hu_home.ready ] && break
  sleep 0.2
done
echo "hu_ready=\$(cat /tmp/bcl_dummy/hu_home.ready 2>/dev/null)"
echo "hu_pid=\$(cat /tmp/bcl_dummy/hu_home.pid)"

# Dedicated btmon on HU hci
pkill -f "btmon -i \$HU_HCI -w /tmp/bcl_dummy/home_" 2>/dev/null
nohup btmon -i \$HU_HCI -w "\$OUT/hu_\${HU_HCI}.btsnoop" \
  > "\$OUT/btmon.out" 2>&1 &
echo \$! > /tmp/bcl_dummy/home_btmon.pid
ln -sfn "\$OUT/hu_\${HU_HCI}.btsnoop" /tmp/bcl_dummy/home_latest.btsnoop
echo "btmon=\$OUT/hu_\${HU_HCI}.btsnoop"

bluetoothctl list
hciconfig \$HU_HCI | head -6
echo "READY stamp=\$STAMP"
echo "OnePlus: connect BMW 38304 (A2DP), force-stop MyBMW+AAIdrive, restart apps"
EOF

if [ "$W0_USB" = 1 ]; then
  echo "==> W0 USB phone isolate (BCL_RHMI_STOP_AFTER=description_check)"
  ssh -o BatchMode=yes "$HOST" bash -s << EOF
set +e
cd /tmp/bcl_dummy
export BCL_RHMI_STOP_AFTER=description_check
HU_BD="$HU_BD"
USB_BD="$USB_BD"
hciconfig hci0 up 2>/dev/null
bluetoothctl select \$USB_BD >/dev/null
bluetoothctl power on >/dev/null
bluetoothctl trust \$HU_BD 2>/dev/null
timeout 12 bluetoothctl connect \$HU_BD 2>/dev/null
nohup env BCL_RHMI_STOP_AFTER=description_check \
  python3 bcl_dummy_hu_agent.py phone \
  --adapter-bd \$USB_BD --hu-bd \$HU_BD --channel 6 \
  --seconds 90 --mybmw-sim --wd-miss-limit 0 --wd-interval 2.5 \
  --log /tmp/bcl_dummy/phone_w0_home.jsonl \
  --session-id LAB_W0_HOME \
  > /tmp/bcl_dummy/phone_w0_home.out 2>&1 &
echo \$! > /tmp/bcl_dummy/phone_w0_home.pid
echo "w0_phone_pid=\$(cat /tmp/bcl_dummy/phone_w0_home.pid)"
echo "After ~90s: PYTHONPATH=/tmp/bcl_dummy python3 lab_w0_reply_forensic.py --phone phone_w0_home.jsonl --hu hu_home.jsonl --out LAB_W0_HOME_FORENSIC.json"
EOF
fi

echo "==> prep done — see docs/evidence/LAB_HOME_PREP_20261117.md"
