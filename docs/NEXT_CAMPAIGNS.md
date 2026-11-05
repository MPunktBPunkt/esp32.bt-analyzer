# Next campaigns — after 0.3.14 + PROXY track

```yaml
status: dual_track
observe_fw: "0.3.14"
proxy_doc: PROXY.md
anchor: OBSERVE_then_PROXY_P0_inventory
sources: "GPT+Grok proxy analysis 2026-11-05 · lab .131 Heizung FACT"
```

## Consensus

1. **0.3.14 observability shipped** — Remote Name/EIR, `:8081` live frames + session rates, scan/connect UI, `lab_classic_name.py`.  
2. **Proxy is now an explicit track** — semantic bridge on Debian + Classic D1s (`.131` phone-side, `.87` car-side). **Not** HCI passthrough. See [`PROXY.md`](PROXY.md).  
3. **`.131` + `.87` both Classic analyzer** — PROXY P0 `dual_classic_ready` PASS (2026-11-05).  
4. **S3 `.88`/`.89`** stay BLE observe/capture — never Classic proxy endpoints.

Findings: [`FINDINGS_LAB_20261105.md`](FINDINGS_LAB_20261105.md) · Proxy: [`PROXY.md`](PROXY.md) · Scope: [`SCOPE_HOST_VS_ANALYZER.md`](SCOPE_HOST_VS_ANALYZER.md)

---

## Shipped (reference)

| Pkg | Delivered |
|-----|-----------|
| **0.3.9–0.3.13** | Capture session · car-node · FTMS real · Classic inquiry `0x22` |
| **0.3.14** | Remote Name/EIR · live HCI frames · session rates · min UI scan/connect · adv resume |

---

## Track A — Observability / decode (continue)

### **0.3.15 — Decoders + timeline**

| # | Measure | Done when |
|---|---------|-----------|
| 1 | FTMS `2AD2` → rpm/W (`tools/ftms_ibd.py` + live overlay) | Hammer pedal → UI rpm/W |
| 2 | Connection/event timeline markers | CONNECT/DISC/MARK on session UI |
| 3 | `btac_to_pcapng` one-click from session download | README recipe |

### **0.3.16 — Classic discovery depth (observe)**

SDP / L2CAP CID summary / AVRCP observe from MEASURED channels only.

---

## Track B — PROXY (new)

### **P0 — Dual controller inventory** — *PASS*

| # | Measure | Done when |
|---|---------|-----------|
| 1 | Hardware matrix `.87` + `.131` | evidence + LAB_INVENTORY |
| 2 | Debian API lists both Classic slots | `/api/v1/proxy/controllers` |
| 3 | `.131` Metermaster → analyzer OTA | `POST /update` · Classic ready |

### **P1.0 — Dual BTAC + BlueZ visibility** ← *now*

| # | Measure | Done when |
|---|---------|-----------|
| 1 | Named multi-session BTAC | `phone_side` + `car_side` concurrent |
| 2 | `/api/v1/proxy/session/*` | start/stop/frames |
| 3 | `lab_proxy_p1_sdp.py` | both BDs seen + frames > 0 |

### **P1 — AVRCP semantic proxy**

SDP + dual pairing + AVRCP min bridge + modify/drop hooks.

### **P2 / P3**

A2DP SBC, then HFP — see [`PROXY.md`](PROXY.md).

---

## Explicit NO

| Item | Why |
|------|-----|
| HCI→TCP→HCI as product proxy | semantic bridge only |
| OTA `.131` without auth | live Heizung |
| Classic on S3 | hardware |
| A2DP in thin VHCI core | Debian host / later flavor |
| Air claims from HCI | BT15 |

---

## Build order

1. **P0 inventory + controller API** (this package).  
2. **0.3.15** FTMS overlay + timeline (observe track).  
3. **Operator frees `.131`** → flash `analyzer-esp32` → re-run `lab_dual_controller.py` until both Classic ready.  
4. **P1 AVRCP** — first PiDrive experiment harness.
