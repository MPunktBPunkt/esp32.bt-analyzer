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
| **BT6** | Lossless lab capture (drops=0, gaps noted) | **CODE READY** (lab script) |
| **BT7** | Debian decoder (JSONL) | **CODE READY** (`btac_decode.py`) |
| **BT8** | PCAPNG export (HCI, not RF) | **CODE READY** (`btac_to_pcapng.py`) |
| **BT9** | BLE on-chip validation (scan/connect) | **CODE READY** (connect/disconnect) |
| **BT10** | Classic on-chip validation (`.87`) | **CODE READY** (discoverable + inquiry) |
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
python3 tools/lab_gate_exits.py   # FACT/MEASURED/UNKNOWN exits → docs/GATE_EXITS.md
```
