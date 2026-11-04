# Gate exits — MEASURED pack (20261104T171121Z)

**Topology:** F_ONCHIP · **FW:** `.88` 0.3.1 · `.89` 0.3.1 · `.87` 0.3.1
**Gate result source:** `docs/evidence/LAB_GATES_BT5_13_20261104T162638Z.json`
**BT16 source:** `docs/evidence/LAB_BT16_20261104T162753Z.json`
**BT18 source:** `docs/evidence/LAB_BT18_GATT_20261104T171044Z.json`
**Raw:** [`LAB_GATE_EXITS_20261104T171121Z.json`](evidence/LAB_GATE_EXITS_20261104T171121Z.json)

Classification: **FACT** · **MEASURED** · **INFERENCE** · **UNKNOWN** · **NEXT TEST**

| Gate | FACT | MEASURED | UNKNOWN | NEXT TEST |
|------|------|----------|---------|-----------|
| BT0 | esp-hub OTA/Web/NVS base present | `versions={'88': '0.3.1', '89': '0.3.1', '87': '0.3.1'}` | long-term OTA under BT | flash_lab_ota smoke |
| BT1 | S3 BLE; ESP32 Classic+BLE | `.88 ready=True .87 ready=True` | errata under flood | watch mem_release |
| BT2 | HCI cmd/evt host↔controller | `bd=['68:b6:b3:29:33:9d', '68:b6:b3:2b:c5:69', 'c8:c9:a3:cb:37:96']` | vendor events | decode on demand |
| BT3 | Raw HCI is L1 not Air | `capacity=512` | absolute sync | LINKTYPE 201 |
| BT4 | BTAC v1 :9753 | `ok=True detail={"ok": true, "btac": "docs/evidence/LAB_GATES_BT5_13_20261104T162638Z.btac"` | multi-client | session UI |
| BT5 | S3 PSRAM capture ring | `ok=True detail={"ok": true, "capacity": 512, "psram": true, "fillPct": 1, "frameBytes": 10` | ESP32 long flood | fillPct |
| BT6 | Ring drops_delta vs file_gaps split | `ok=True detail={"ok": true, "drops_delta": 0, "btac_seqGapsSession_delta": 2, "btac_seqGap` | multi-hour soak | lab_gap_classify |
| BT7 | JSONL HCI decode | `ok=True detail={"ok": true, "stats": {"frames": 120, "gaps": 2, "resync": 0, "crc_fail": 0` | opcode atlas | --stats |
| BT8 | PCAPNG LINKTYPE 201 | `ok=True detail={"ok": true, "pcapng": "docs/evidence/LAB_GATES_BT5_13_20261104T162638Z.pca` | never Air LINKTYPE | reject RF label |
| BT9 | LE Connect Central↔Peripheral | `ok=True detail={"ok": true, "leConnected": true, "connHandle": 1, "peerAddr": "68:b6:b3:2b` | bonding | gatt read-name |
| BT10 | Classic only on .87 | `ok=True detail={"ok": true, "classicDiscoverable": true, "inquiry_devices": 0, "devices": ` | Classic×Classic | second Classic/phone |
| BT11 | Second ESP stimulus peer | `ok=True detail={"ok": true, "peer_seen": true, "devices": 3, "matched": [{"addr": "68:b6:b` | ambient RF | pin peer BD |
| BT12 | Long capture duration+frames | `ok=True detail={"ok": true, "frames": 200, "duration_s": 7.32, "btac": "docs/evidence/LAB_` | hour soak | session manager |
| BT13 | WiFi STA + BTDM coex smoke | `ok=True detail={"ok": true, "toggle_fails": 0, "host_ready": true, "heap": 176180}` | AP+BT | BT before WiFi |
| BT14 | technology-audit pack present | `ok=True detail={"ok": true, "missing": [], "note": "project-side audit pack present; exter` | external stamp | STATUS green |
| BT15 | RF/Air out of scope | `docs/BT15_RF_AIR.md deferred` | named RF instrument | separate repo |
| BT16 | ATT Notify/Write is L2 over HCI ACL only | `latest=LAB_BT16_20261104T162753Z.json capability=True benchmark=False appTx=0 appRx=0` | full matrix soak | lab_bt16_throughput.py --benchmark |
| BT18 | GATT Client Flavor = STIMULUS discovery/CCCD ove | `latest=LAB_BT18_GATT_20261104T171044Z.json capability=True benchmark=True flavor=ready` | foreign peer discovery | lab_gatt_client.py → HOGP Flavor |

## Claim boundary

| Claim | Status |
|-------|--------|
| HCI = RF/Air | **REJECTED** |
| Classic on ESP32-S3 | **REJECTED** |
| Thin ATT = full GATT | **REJECTED** |
| kB/s without loss split = benchmark | **REJECTED** |

## Source policy

`lab_gate_exits.py` reads only `LAB_GATES_BT5_13_<UTC>.json` gate results — never `*_status_before/after.json`.

