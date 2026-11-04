# Lab F_ONCHIP peer — MEASURED

**Date (UTC):** 20261104T090145Z
**Topology ID:** F_ONCHIP
**Firmware:** host `192.168.178.88` 0.2.5 · peer `192.168.178.89` 0.2.5
**Raw:** [`LAB_F_ONCHIP_PEER_20261104T090145Z.json`](LAB_F_ONCHIP_PEER_20261104T090145Z.json) · [`LAB_F_ONCHIP_PEER_20261104T090145Z.btac`](LAB_F_ONCHIP_PEER_20261104T090145Z.btac) · [`LAB_F_ONCHIP_PEER_20261104T090145Z.jsonl`](LAB_F_ONCHIP_PEER_20261104T090145Z.jsonl)
**Repro:** `python3 tools/lab_f_onchip_peer_evidence.py`

Classification: **MEASURED** (this lab run).

## Claim boundary

| In scope | Out of scope |
|----------|----------------|
| L1 on-chip VHCI · BLE peer advertise/scan · BTAC/JSONL | RF / Air / MITM / Classic-on-S3 |

## Setup

| Item | Value |
|------|-------|
| Central (scan + BTAC) | `192.168.178.88` BD_ADDR `68:b6:b3:29:33:9d` |
| Peripheral (advertise) | `192.168.178.89` BD_ADDR `68:b6:b3:2b:c5:69` name `bt-peer-89` |
| Capture | ESP `:9753` BTAC v1 → JSONL (BT4/BT7) |

## Results

| Metric | Value |
|--------|------:|
| peer_seen_on_host | `True` |
| devices_listed | 3 |
| btac_frames | None |
| btac_gaps | None |
| crc_fail | None |

Matched: `[{"addr": "68:b6:b3:2b:c5:69", "addrType": 0, "rssi": -24, "classic": false, "ble": true, "name": ""}]`

## Epistemic notes

| Claim | Status |
|-------|--------|
| `.89` advertises; `.88` HCI scan lists peer | MEASURED |
| BTAC stream decode → JSONL | PARTIAL |
| HCI = Air/RF | **REJECTED** |

## NEXT TEST

BT8 PCAPNG export · BT9 longer BLE connect · BT10 Classic on `.87` discoverable
