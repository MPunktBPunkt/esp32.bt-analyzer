# Gates — esp32.bt-analyzer

Each gate exit documents: **FACT · MEASURED · INFERENCE · UNKNOWN · NEXT TEST**.  
No release claim without green gate status.

| Gate | Ziel | Status |
|------|------|--------|
| **BT0** | Hub-Basis / OTA / Web UI / NVS / reboot / PSRAM | **CODE READY** |
| **BT1** | On-chip controller bring-up (VHCI) | **CODE READY** (0.2.7) |
| **BT2** | HCI host↔controller path (cmd/evt via VHCI) | **CODE READY** (0.2.7) |
| **BT3** | Raw HCI capture (ts, dir, type, payload) | **CODE READY** (VHCI) |
| **BT4** | TCP capture stream (BTAC framing) | **CODE READY** (`:9753`) |
| **BT5** | PSRAM ring buffer | **CODE READY** (512 slots S3 · fillPct) |
| **BT6** | Lossless lab capture (session drops + file gaps) | **CODE READY** (`lab_gap_classify.py`) |
| **BT6b** | Capture session START/MARK/STOP + BT_EVENT | **CODE READY** 0.3.9 · car-node drain lab **0.3.10** ([`CAPTURE_SESSION.md`](CAPTURE_SESSION.md)) |
| **BT16** | BLE ATT throughput (CAPABILITY / BENCHMARK) | **CODE READY** 0.3.0 (`lab_bt16_throughput.py`) |
| **BT17** | Classic A2DP/HFP/AVRCP (`.87` Bluedroid flavor) | **scaffold 0.3.3** (+ AVRCP host probe 0.3.7; no A2DP/OTA yet) |
| **BT18** | GATT Client + HOGP + FTMS Flavors (STIMULUS) | **CODE READY** 0.3.8 (+ FTMS Control Point · HOGP matrix · L2CAP/MTU CAPABILITY) |
| **BT19** | Multi-node timeline (offset estimation) | **CODE READY** ([`BT19_TIMELINE.md`](BT19_TIMELINE.md)) |
| **BT20** | Cross-layer window correlation (no MITM) | **scaffold 0.3.6** ([`BT20_CORRELATION.md`](BT20_CORRELATION.md) · BlueZ×ESP live) |
| **BT7** | Debian decoder (JSONL) | **CODE READY** (`btac_decode.py`) |
| **BT8** | PCAPNG export (HCI, not RF) | **CODE READY** (`btac_to_pcapng.py`) |
| **BT9** | BLE on-chip validation (scan/connect) | **CODE READY** (+ Method G multiview · Method H host oracle) |
| **BT10** | Classic on-chip validation (`.87`) | **CODE READY** (+ Method D classic+BLE mix) |
| **BT11** | Second ESP peer / stimulus | **CODE READY** (advertise/scan/connect) |
| **BT12** | Long capture | **CODE READY** (`lab_run_gates.py`) |
| **BT13** | WiFi/BT stress + recovery | **CODE READY** (toggle stress) |
| **BT14** | Technology-audit project green | **ready for external review** (`lab_gate_exits.py`) |
| **BT15** | RF / Air investigation (separate) | **deferred** ([`BT15_RF_AIR.md`](BT15_RF_AIR.md)) |

## Forbidden vague exits

- „Bluetooth works“ without layer (L0/L1/L2)
- „Sniffer“ without RF evidence
- HCI MEASURED sold as Air FACT
- Classic claims on ESP32-S3

## Lab topology

| ID | Next gate relevance |
|----|---------------------|
| **F_ONCHIP** | primary — all BT1–BT13 lab scripts |
| E_INJECT | pipeline-only |
| A_OBSERVE | legacy USB-dongle |

Gate exit must cite **topology ID** + FW pins + evidence path.

## Repro

```bash
python3 tools/lab_run_gates.py
python3 tools/lab_gap_classify.py --host 192.168.178.88 --btac docs/evidence/….btac
python3 tools/lab_gate_exits.py   # FACT/MEASURED/UNKNOWN exits → docs/GATE_EXITS.md
python3 tools/lab_bt16_throughput.py
```

**BT6 claim split:** `drops_delta==0` ⇒ ring enqueue ok im Fenster. **E2E** ⇒ zusätzlich `file_gaps==0`. Lifetime-`btac.seqGaps` nie mit Drop-Deltas vergleichen.
