# HCI over TCP — D1 Mini as a BlueZ controller (0.3.16)

```yaml
status: code_ready_untested_on_hw
fw_env: hci-agent-esp32
port: 9754
linux: tools/hci_tcp_bridge.py  (root, /dev/vhci)
boards: ".131 phone side · .87 car side (D1 Mini ESP32, Classic+BLE)"
claim: transport_only — profiles come from BlueZ, not from this firmware
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

`GET /api/status` → `hciAgent{ready, bdAddr, client, sessions, toCtrlPkts,
toHostPkts, drops, framingErrors}`.

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
- Controller→host queue 16 KiB; overflow drops the client (no silent gaps).
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

Only after A1–A6: AVRCP bridge script (P1), the heart-rate GATT relay and the
BCL-over-BT probe ([`BCL_BT.md`](BCL_BT.md) B1).

## Limits

| Item | Status |
|------|--------|
| Port 9754 has no auth — anyone on the LAN controls the radio | lab LAN only |
| WiFi modem sleep is mandatory with BT on ESP32 | adds latency, fine for HCI timeouts (2 s) |
| Car ESP behind a phone hotspot (NAT) | not reachable as TCP server → needs dial-out or VPN (later) |
| SCO/HFP audio over HCI | not routed; P3 |
| A2DP over hotspot | expect dropouts; terminate locally in the car instead (later) |
| HCI ≠ Air | unchanged |
