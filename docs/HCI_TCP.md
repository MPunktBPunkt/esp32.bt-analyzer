# HCI over TCP — D1 Mini as a BlueZ controller (0.3.17)

```yaml
status: a1_a5_measured
fw_env: hci-agent-esp32
port: 9754
linux: tools/hci_tcp_bridge.py  (root, /dev/vhci)
boards: ".131 phone side · .87 car side (D1 Mini ESP32, Classic+BLE)"
claim: transport_only — profiles come from BlueZ, not from this firmware
evidence:
  - docs/evidence/LAB_HCI_TCP_A1A5_20261111T204600Z.md
  - docs/evidence/LAB_HCI_TCP_WIFI_PS_SWEEP_20261111T202605Z.md
not_claim: passive air sniff of an existing Phone↔HU link
```

## Why

The thin VHCI host in the analyzer image would need pairing, L2CAP, SDP, AVRCP
and A2DP written by hand before any proxy byte moves. BlueZ already has all of
it. The agent firmware only forwards raw H4 between the on-chip controller and
one TCP client; the Linux side registers that stream as a normal `hciN`.

```text
Phone ─BT─ D1 .131 ─WiFi TCP :9754─┐
                                   ├─ hci_tcp_bridge.py ×2 → /dev/vhci → hci1 / hci2
BMW HU ─BT─ D1 .87 ─WiFi TCP :9754─┘        BlueZ (bluetoothctl, btmon, Python bridge logic)
```

This is a **controlled measurement / relay point** (two real BT links terminated
on the ESP controllers). It is **not** a passive air sniffer of Phone↔HU.

## Where the Linux side runs

BlueZ must run in a kernel network namespace that owns Bluetooth — **not** in the
unprivileged CT100 ([`HOST_BT.md`](HOST_BT.md)). Options:

| Host | Note |
|------|------|
| Proxmox host `.108` | works today; BlueZ already active there |
| Small Debian **VM** | preferred long-term: own kernel, no SSH oracle needed |

## Build and flash

```bash
cd firmware/analyzer-node
pio run -e hci-agent-esp32
ENV=hci-agent-esp32 ./tools/flash_lab_ota.sh 192.168.178.131
```

OTA (`/ota-upload`), Web UI and hub heartbeat stay from esp-hub core, so the board
can be flashed back to `analyzer-esp32` the same way. Legacy heartbeat WDT is off
in this env (no hub in the car must not reset live links).

`GET /api/status` → `hciAgent{ready, bdAddr, client, sessions, toCtrlPkts/Bytes,
toHostPkts/Bytes, drops, framingErrors, ringBytes, ringUsed, ringPeak,
rttLastUs, rttMaxUs, rttSamples, wifiPs}`.

WiFi power save live toggle (default `min` for stable Classic ACL):

```bash
curl -s http://192.168.178.131/api/hci/wifi_ps
curl -s -X POST -d 'mode=none' http://192.168.178.131/api/hci/wifi_ps
```

Throughput (MEASURED, see `LAB_HCI_TCP_WIFI_PS_SWEEP_20261111T202605Z`):
`max`/`min` cold ≈ 3.4–3.8 kB/s; `none` ≈ 38–39 kB/s sustained 60 s (short-window
live peaks previously ~62 kB/s). `ringPeak` ≪ 24 KiB and drops=0 → coex/PS limit,
not software queue. After a `none` session, API `min` may not re-throttle until
radio/session reset.

## Attach

```bash
modprobe hci_vhci
python3 tools/hci_tcp_bridge.py 192.168.178.131      # prints "hci1 <-> …"
btmon -i hci1 -w /tmp/phone.btsnoop                   # optional capture
bluetoothctl list                                     # new controller visible
```

Permanent: copy the repo to `/opt/bt-analyzer`, then
`systemctl enable --now hci-tcp-bridge@192.168.178.131` (unit in `deploy/`).

## See the traffic

| Where | What |
|-------|------|
| Lab UI `:8081` card **HCI agents** | per D1: ready, bridge client, B/s and pkt/s per direction (graph) |
| Lab UI `:8081` card **btmon live** | decoded packets from the BlueZ host via SSH; filter by hci, text (AVRCP, ATT, Handle …) |
| `btmon -i hciN -w x.btsnoop` on `.108` | file for Wireshark (`btavrcp`, `btatt`, `btl2cap`) |

HCI is above the controller's link encryption: payloads (AVRCP, metadata, GATT
values, link keys during pairing) appear in clear text. The btmon card needs the
CT100 → `.108` SSH key that `lab_bt_host_ssh.py` already uses.

## Behaviour

- One TCP client; a new connection replaces the old one (reconnecting bridge wins).
- Client loss (close, keepalive ~11 s, WiFi down) → agent sends HCI_Reset, so
  phone/HU links drop instead of hanging; bridge closes vhci, `hciN` disappears.
- Controller→host queue 24 KiB; overflow increments `drops` (session stays up —
  a full HCI reset was worse for A2DP than a short ACL gap). `ringUsed` /
  `ringPeak` expose queue water level for coex stalls vs sustained-rate limits.
- Host bridge drains queued VHCI frames into one TCP write; agent batches the
  reverse path (~1200 B). Tiny per-frame `TCP_NODELAY` segments hurt under BT/WiFi coex.
- `rttLastUs` / `rttMaxUs` measure HCI Command → Command Complete/Status on the
  controller path (useful for BCL/RFCOMM latency, not just bulk kB/s).
- Malformed H4 from the host drops the client (`framingErrors`).

## Acceptance (lab, in this order)

| # | Step | Pass |
|---|------|------|
| A1 | Flash `.131`, `/api/status` | `hciAgent.ready=true`, `bdAddr` = lab BD `c8:c9:a3:cb:7b:0a` |
| A2 | Bridge on `.108` | `bluetoothctl list` shows the ESP BD as extra controller |
| A3 | `bluetoothctl` select it, `power on`, `scan on` | phone / HD 4.40 found |
| A4 | Pair phone ↔ ESP controller | bonded; `btmon` shows SSP |
| A5 | Unplug WiFi / stop bridge | phone shows disconnect ≤ 15 s; bridge reconnects, `hciN` back |
| A6 | Same for `.87`, BMW HU pairs | HU lists the ESP controller as phone |

**A1–A5: MEASURED** (evidence above). **A6: OPEN.**

Only after A1–A6: AVRCP bridge script (P1), the heart-rate GATT relay and the
BCL-over-BT probe ([`BCL_BT.md`](BCL_BT.md) B1 → B2 RFCOMM → BCL bytes).

## Limits

| Item | Status |
|------|--------|
| Port 9754 has no auth — anyone on the LAN controls the radio | lab LAN only |
| WiFi PS default `min`; `none` raises TCP rate but can break Classic page/ACL cold | toggle via `/api/hci/wifi_ps`; recipe min→none mid-stream |
| Sustained ACL ~4 kB/s (`min`/`max`) / ~39 kB/s (`none`); ringPeak ≪ capacity | MEASURED sweep; dual A2DP choppy = coex, not soft bug |
| Car ESP behind a phone hotspot (NAT) | not reachable as TCP server → needs dial-out or VPN (later) |
| SCO/HFP audio over HCI | not routed; P3 |
| A2DP over hotspot | expect dropouts; terminate locally in the car instead (later) |
| HCI ≠ Air | unchanged — no passive Phone↔HU air capture |
