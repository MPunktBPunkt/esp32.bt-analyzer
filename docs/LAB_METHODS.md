# Lab methods — bt-analyzer (audit-ready)

Authority: [technology-audit](https://github.com/MPunktBPunkt/technology-audit) · Method sibling: [`bt-usb-hci-observe-baseline`](https://github.com/MPunktBPunkt/technology-audit/blob/main/methods/bt-usb-hci-observe-baseline.md)  
Epistemics: `FACT` · `MEASURED` · `INFERENCE` · `HYPOTHESIS` · `UNKNOWN` · `REJECTED`

**Rule:** One topology ID per campaign. Never merge L0 / L1 / L2 claims in one MEASURED block.

---

## Topology registry (preregistered)

| ID | Wiring | Primary claim layer | Nodes |
|----|--------|---------------------|-------|
| **F_ONCHIP** | Peer ↔ on-chip radio → VHCI host → WiFi → Debian | **L1 onchip_vhci** | `.88`/`.89` BLE; `.87` Classic+BLE |
| **A_OBSERVE** | BT-Dongle ─USB→ `.88` Host → WiFi → Debian | **L1 USB-HCI** (legacy) | OBSERVE_A |
| **B_STIMULUS** | `.88` ↔ `.89` HCI synth | **L1 synthetic** | OBSERVE_A + STIMULUS |
| **E_INJECT** | HTTP inject (no radio) | **pipeline only** | any |

### Explicitly out of registry (until own gate)

- Classic on-chip on S3  
- HCI MEASURED as RF/Air FACT  
- MITM Phone↔DUT via ESP  

---

## Method F — On-Chip VHCI Baseline (primary)

**Gate focus:** BT1–BT3, BT9 (BLE), BT10 (Classic on `.87`)  
**Pass story:** `onchip.ready=true` · HCI Reset complete · scan yields devices · drain has frames  

### Prerequisites

- `.88`/`.89` = bt-analyzer ≥0.2.0 (BLE)  
- `.87` = bt-analyzer `analyzer-esp32` ≥0.2.0 for Classic  
- No USB dongle required  

### Procedure

1. Inventory snapshot: `python3 tools/lab_inventory_snapshot.py`  
2. `GET /api/status` → `onchip.ready`, `onchip.ble` / `onchip.classic`, `bdAddr`  
3. Roles: one node **Peripheral** `POST /api/bt/advertise/start?name=bt-peer-89` · other **Central** `POST /api/bt/scan/start`  
4. `GET /api/bt/devices` on Central → peer name/BD_ADDR  
5. Capture: `tools/btac_recv.py` / `tools/lab_f_onchip_peer_evidence.py` → `.btac` + JSONL under `docs/evidence/`  
6. Decode: `tools/btac_decode.py … --stats` (BT7)  
7. Write MEASURED.md with topology **F_ONCHIP** + claim boundary  

---

## Method A — USB-HCI Observe Baseline (legacy)

**Gate focus:** optional USB path when `BT_ANALYZER_ENABLE_USB_HOST=1`  
**Pass story:** Dongle enumerates · USB-HCI frames  

### Prerequisites

- Build with USB Host enabled; self-powered hub + dongle  

### Procedure

1. Record inventory snapshot  
2. Attach dongle (+ hub) to OTG  
3. `GET /api/usb/status` → `dut.present`, HCI map  
4. Drain capture; document topology **A_OBSERVE**  

### Pass / Fail

| Check | Pass | Fail |
|-------|------|------|
| Enum | VID/PID + FS | no device / crash |
| HCI map | `hci.detected` | false on known BT dongle |
| Capture | frames ≥1 with ts/seq/type | only inject without declaring E_INJECT |
| Integrity | drops noted; gaps explicit | silent loss |
| Docs | FW + topology A + boundary | „Bluetooth works“ |

---

## Method B — USB HCI Stimulus Loop

**Gate focus:** BT11 (+ BT3/BT7 offline)  
**Pass story:** Known synthetic HCI bytes on wire USB → capture match  

### Prerequisites

- Both S3 on **instrument** FW (Stimulus image when available; until then defer)  
- OTG cable Host↔Device; **no** BT dongle required  

### Procedure

1. Topology B; inventory snapshot.  
2. Stimulus emits fixed vector (e.g. Event `0x0e` Command Complete).  
3. Observe drain must match golden hex (byte-exact).  
4. Repeat N=10; 0 mismatches.  

### Pass / Fail

| Check | Pass | Fail |
|-------|------|------|
| Golden match | 10/10 | any mismatch |
| Claim | synthetic USB-HCI | „over the air“ |

---

## Method C — Dual-Dongle Link

**Gate focus:** BT9/BT10 advanced · correlation  
**Pass story:** Two HCI streams, one `session_id`, independent MEASURED rows  

### Prerequisites

- `.88` + `.89` both OBSERVE images  
- Two dongles + powered hub(s)  
- Peer link established by **host stacks on Debian or on-dongle firmware** — ESPs capture only  

### Epistemic note

ESP does **not** run the Bluetooth host for the link under test unless explicitly scoped. Prefer BlueZ on Debian driving one dongle via USB while the other is on ESP — or document clearly if ESP hosts.

*(First campaigns: defer C until A is green twice.)*

---

## Method D — Classic/BLE Endpoint Reference (`.87`)

**Gate focus:** correlation / REJECTED-boundary checks  
**Pass story:** Endpoint events on classic ESP32 ≠ HCI on `.88`  

### Prerequisites

- `.87` hub-base or later endpoint FW  
- FACT: Classic available on `.87` only  

### Use

- Parallel session: Phone↔`.87` Classic/BLE while `.88` does unrelated HCI observe — prove streams are labeled apart.  
- Never cite `.87` logs as USB-HCI evidence.  

---

## Method E — Inject Pipeline Smoke

**Gate focus:** BT3/BT5 plumbing without Dongle  

```bash
curl -s -X POST -d 'hex=040e0401030c00' http://192.168.178.88/api/capture/inject
curl -s 'http://192.168.178.88/api/capture/drain?n=8'
```

**MEASURED** only as pipeline integrity — label topology **E_INJECT**.

---

## Gate exit template

Copy into `docs/GATE*_STATUS.md` or `docs/evidence/LAB_*_MEASURED.md`:

```markdown
## Gate BTx exit — <TITLE>

| Field | Value |
|-------|------|
| Date (UTC) | |
| Topology ID | A_OBSERVE / B_STIMULUS / … |
| FW .88 | |
| FW .89 | |
| FW .87 | |
| Dongle VID:PID | |
| Raw artifact | docs/evidence/LAB_….json(l) |
| Repro | `python3 tools/…` |

### Classification

| Claim | Status |
|-------|--------|
| … | MEASURED / INFERENCE / … |

### Claim boundary

| In scope | Out of scope |
|----------|----------------|
| | |

### Results

(tables)

### NEXT TEST
```

---

## Evidence naming

| Artifact | Pattern |
|----------|---------|
| Inventory | `LAB_INVENTORY_<UTC>.json` |
| Observe run | `LAB_BT_HCI_OBSERVE_<UTC>.json` + `.md` |
| Inject smoke | `LAB_BT_INJECT_<UTC>.json` |
| Stimulus | `LAB_BT_STIMULUS_<UTC>.json` |

Always pair JSON + MEASURED.md with FW pins and topology ID.

---

## Recommended campaign order

1. E_INJECT smoke (done in 0.1.3 lab)  
2. Inventory freeze (this doc + snapshot tool)  
3. A_OBSERVE with **one** BLE dongle (BT9)  
4. A_OBSERVE with **one** Classic dongle (BT10) — separate campaign  
5. BT4 BTAC `:9753` (`tools/btac_recv.py`) → BT7/BT8 JSONL/PCAPNG  
6. B_STIMULUS when `.89` stimulus image exists  
7. C_DUAL_DONGLE  
8. D_ENDPOINT_REF only for cross-layer discipline demos  
