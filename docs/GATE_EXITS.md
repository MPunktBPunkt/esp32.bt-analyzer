# Gate exits — MEASURED pack (20261104T113804Z)

**Topology:** F_ONCHIP · **FW:** `.88` 0.2.7 · `.89` 0.2.7 · `.87` 0.2.7
**Source gates:** `docs/evidence/LAB_GATES_BT5_13_20261104T113719Z.json`
**Raw:** [`LAB_GATE_EXITS_20261104T113804Z.json`](evidence/LAB_GATE_EXITS_20261104T113804Z.json)

Classification: **FACT** · **MEASURED** · **INFERENCE** · **UNKNOWN** · **NEXT TEST**

| Gate | FACT | MEASURED | UNKNOWN | NEXT TEST |
|------|------|----------|---------|-----------|
| BT0 | esp-hub OTA/Web/NVS base present | `"nodes respond /api/status versions={'88': '0.2.7', '89': '0.2.7', '87` | long-term OTA reliability under BT load | keep flash_lab_ota in CI smoke |
| BT1 | ESP32-S3 has on-chip BLE controller; ESP32 has C | `".88 ready=True · .87 ready=True"` | silicon errata under continuous HCI floo | watch init_fail after mem_release regres |
| BT2 | HCI cmd/evt is the host↔controller contract | `"bdAddr pins: ['68:b6:b3:29:33:9d', '68:b6:b3:2b:c5:69', 'c8:c9:a3:cb:` | vendor events not decoded | extend event decode only when a gate nee |
| BT3 | Raw HCI frames are L1 (not Air) | `"capture capacity=512"` | absolute clock sync across nodes | keep LINKTYPE 201 claims explicit |
| BT4 | BTAC v1 framing on TCP :9753 | `"BT4 ok=True frames=120"` | multi-client BTAC fan-out | session UI + download on collector |
| BT5 | S3 has PSRAM usable for capture ring | `"BT5={'ok': True, 'capacity': 512, 'psram': True, 'fillPct': 0, 'frame` | ESP32 (no PSRAM) under long Classic floo | keep fillPct in status |
| BT6 | drops_delta==0 is lab lossless claim only | `"BT6={'ok': True, 'drops_delta': 0, 'btac_seqGaps': 7, 'frames': 120, ` | production multi-hour soak | BT12 long capture remains the soak pin |
| BT7 | JSONL is a Debian-side decode of HCI frames | `"BT7={'ok': True, 'stats': {'frames': 120, 'gaps': 2, 'crc_fail': 0, '` | full HCI opcode atlas | keep --stats off stdout pollution |
| BT8 | PCAPNG LINKTYPE 201 = Bluetooth HCI H4 | `"BT8={'ok': True, 'pcapng': 'docs/evidence/LAB_GATES_BT5_13_20261104T1` | Air LINKTYPE must never be claimed here | reject any RF label on this artifact |
| BT9 | LE Connect is GAP Central↔Peripheral over on-chi | `"BT9={'ok': True, 'leConnected': True, 'connHandle': 1, 'peerAddr': '6` | bonding / privacy / multi-conn | GATT read-name after connect (thin L2) |
| BT10 | Classic BR/EDR only on ESP32 (.87), not S3 | `"BT10={'ok': True, 'classicDiscoverable': True, 'inquiry_devices': 0, ` | Classic×Classic peer (single Classic boa | optional second Classic ESP or phone inq |
| BT11 | Second ESP is a lab stimulus peer, not MITM | `"BT11={'ok': True, 'peer_seen': True, 'devices': 2, 'matched': [{'addr` | interference from foreign advertisers | keep peer BD_ADDR pinned in evidence |
| BT12 | Long capture is duration+frame count, not Air so | `"BT12={'ok': True, 'frames': 200, 'duration_s': 11.41, 'btac': 'docs/e` | hour-scale continuous | collector session manager for operator r |
| BT13 | WiFi STA + BTDM coexist on same chip | `"BT13={'ok': True, 'toggle_fails': 0, 'host_ready': True, 'heap': 1757` | AP-mode + BT simultaneous | keep BT init before WiFi |
| BT14 | technology-audit SCOPE/STATUS/INVENTORY exist fo | `"BT14={'ok': True, 'missing': [], 'note': 'project-side audit pack pre` | external CI sign-off stamp | reviewer marks STATUS.md green in techno |
| BT15 | RF/Air is out of scope for esp32.bt-analyzer | `"docs/BT15_RF_AIR.md status=deferred"` | stakeholder need + named RF instrument | open separate repo/scope when Air is req |

## Claim boundary

| Claim | Status |
|-------|--------|
| HCI = RF/Air | **REJECTED** |
| Classic on ESP32-S3 on-chip | **REJECTED** |
| Thin ATT name read = full GATT | **REJECTED** (L2 over HCI ACL only) |

## L2 probe (bounded)

- API `/api/bt/gatt/read-name` → status `onchip.gattName`
- Layer **L2** · Air FACT / full GATT stack

## BT15

Deferred — see [`BT15_RF_AIR.md`](BT15_RF_AIR.md).

