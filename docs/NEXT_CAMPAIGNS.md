# Next campaigns — after 0.3.13 real-device day

```yaml
status: shipping_0.3.14
package_now: "0.3.13"
anchor: OBSERVABILITY_before_BT17_A2DP
fw_lab: "0.3.13"
sources: "Mistral + GPT + Grok review 2026-11-05 · FINDINGS_LAB_20261105"
```

## Consensus (all three reviews)

1. **Capture works** — HCI/VHCI → ring → BTAC → JSONL/PCAPNG is proven (incl. Hammer IBD on the wire while GATT was broken).  
2. **Bottleneck = visibility** — humans still dig in `.btac`/JSONL; `:8081` has rates canvas + session download but no live frame list / FTMS overlay.  
3. **HD 4.40 “not really seen” is not a radio miss on `.87`** — Inquiry+RSSI works (0.3.13); missing Remote Name/EIR + no Classic pair/A2DP (scope). S3 cannot Classic.  
4. **Do not rush BT17 A2DP** — Remote Name → SDP observe → live viewer → FTMS decoder first; A2DP is a separate flavor after discovery depth.

Findings: [`FINDINGS_LAB_20261105.md`](FINDINGS_LAB_20261105.md) · Scope: [`SCOPE_HOST_VS_ANALYZER.md`](SCOPE_HOST_VS_ANALYZER.md)

---

## Shipped (reference)

| Pkg | Delivered |
|-----|-----------|
| **0.3.9** | Capture session START/MARK/STOP · BT_EVENT |
| **0.3.10** | Car-node drain · SDP inventory lab · capture+fault |
| **0.3.11–0.3.12** | Real FTMS CCCD/IBD/CP (Hammer Varon PASS) |
| **0.3.13** | Classic inquiry event `0x22` → devices[] (HD 4.40 ADDR+RSSI) |

---

## Next packages

### **0.3.14 — Observability (P0)** — *shipping*

| # | Measure | Where | Done when |
|---|---------|-------|-----------|
| 1 | **Remote Name Request** after Classic inquiry (+ EIR name from `0x2F`, inquiry mode 2) | FW `.87` | `/api/bt/devices` shows `HD 4.40BT` (or EIR name) |
| 2 | **Live HCI frame stream** on Debian `:8081` during BTAC session | Collector UI | scrolling list: seq · ts · RX/TX · type · len · hex |
| 3 | **Rate strip hardwired to session** | Collector | Frames/s + Bytes/s RX/TX + gaps while session active |
| 4 | **Lab**: `lab_classic_name.py` | tools | PASS: inquiry → name for known HD 4.40 |
| 5 | **Scan/Connect in ESP UI** | `.87` min UI + S3 + `:8081` | BLE scan / Classic inquiry / Connect buttons |

**Out of scope for 0.3.14:** A2DP/HFP pair, Bluedroid, MITM.

**Architecture rule:** generic Event Stream first; profile decoders plug in beside it (not a FTMS-only monitor).

```text
BTAC session
    │
    ├─► Raw frame list + rates + gaps     ← 0.3.14
    └─► Decoder plugins (FTMS, later AVRCP) ← 0.3.15+
```

---

### **0.3.15 — Decoders + timeline (P1)**

| # | Measure | Done when |
|---|---------|-----------|
| 1 | Offline + live **FTMS `2AD2` → rpm/W** (reuse esp32.ergo flag rules) | Hammer pedal → UI shows rpm/W next to frames |
| 2 | Connection/event **timeline** markers (CONNECT / DISCONNECT / MARK / session meta) | MARK from CaptureSession visible on chart |
| 3 | Optional: Wireshark path documented one-click (`btac_to_pcapng` from session download) | README recipe |

---

### **0.3.16 — Classic discovery depth (P1, observe-only)**

| # | Measure | Done when |
|---|---------|-----------|
| 1 | **SDP** browse/observe from `.87` *or* BlueZ oracle labeled same BD_ADDR | UUID list for HD 4.40 / car HU without claiming host |
| 2 | L2CAP CID summary from HCI ACL (no audio decode) | evidence JSON with PSM/CID counts |
| 3 | AVRCP **observe** only if evening BMW/HU run produces channels | decoder depth from MEASURED only |

Still **NO** thin-host A2DP.

---

### **BT17 / later — Classic Audio Flavor (P2)**

Only after 0.3.14–0.3.16 green:

- Separate `analyzer-esp32-classic-audio` + Bluedroid phone-first / headset pair  
- HCI tap under full stack (not folding A2DP into thin VHCI core)  
- HD 4.40 red-blink → connected is a **flavor** claim, not analyzer-core

---

### Evening BMW / AAIdrive (unchanged gate)

```text
.89 session START → MARK … → STOP → BTAC
→ 0.3.14 viewer to cut sequences
→ 0.3.16 SDP/L2CAP/AVRCP depth from observed channels only
```

---

### Explicit NO (still)

| Item | Why |
|------|-----|
| Transparent BT proxy / MITM / RF tunnel | product NO |
| A2DP in thin VHCI core | BT17 separate |
| Expect Classic on `.88`/`.89` | S3 hardware |
| Sniffer/Air claims from HCI | BT15 deferred |

---

## Suggested build order (lab evenings)

1. **Tonight / next lab:** 0.3.14 items 1+4 (Remote Name) — small FW, immediate UX win for HD 4.40.  
2. **Same week:** 0.3.14 items 2–3 (frame list + rates on session) — unblocks Hammer live watching + BMW capture RE.  
3. **Then:** 0.3.15 FTMS decoder overlay (Hammer as demo).  
4. **Car evening:** capture with MARKs; decode depth only from what appears.  
5. **Only if needed:** BT17 for headset audio host.
