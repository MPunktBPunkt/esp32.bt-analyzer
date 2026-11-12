#!/usr/bin/env bash
# Quick A6/B1 preflight for .87 car side. Run on operator machine with SSH to .108.
set -euo pipefail
SSH_HOST="${BT_HOST_SSH:-root@192.168.178.108}"
IP87="${IP87:-192.168.178.87}"
BD87="${BD87:-c8:c9:a3:cb:37:96}"

echo "== agent .87 =="
curl -sS -m 4 "http://${IP87}/api/status" | python3 -c '
import sys,json
d=json.load(sys.stdin); a=d.get("hciAgent") or {}
print("ip", d.get("ip"), "ver", d.get("version"), "rssi", d.get("rssi"))
print("ready", a.get("ready"), "client", a.get("client"), "bd", a.get("bdAddr"),
      "wifiPs", a.get("wifiPs"), "drops", a.get("drops"))
ok = bool(a.get("ready") and a.get("client"))
sys.exit(0 if ok else 1)
'

echo "== .108 controllers =="
ssh -o BatchMode=yes -o ConnectTimeout=5 "$SSH_HOST" "hciconfig -a | egrep 'hci|Address|Name|UP|DOWN'"

echo "== map .87 BD → hciN =="
ssh -o BatchMode=yes "$SSH_HOST" "python3 - <<'PY'
import subprocess
bd='${BD87}'.lower()
out=subprocess.check_output(['hciconfig','-a'],text=True)
for blk in out.split('\n\n'):
    if bd in blk.lower():
        print(blk.strip().split(':')[0])
        break
else:
    raise SystemExit('controller for .87 not found — start hci_tcp_bridge.py '+ '${IP87}')
PY"

echo "preflight OK — proceed A6 scan/connect, then B1:"
echo "  python3 tools/bcl_sdp_probe.py -i <hciN> hu=<HU_BD> --records --json /tmp/sdp_hu.json"
echo "Remember: RFCOMM channel = X from SDP (not lab channel 5)."
