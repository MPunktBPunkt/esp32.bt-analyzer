# esp32.bt-analyzer

![Version](https://img.shields.io/badge/version-0.2.8-blue)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Gate](https://img.shields.io/badge/gate-BT16%20throughput-yellow)](docs/GATES.md)

ESP **on-chip Bluetooth HCI analyzer** (VHCI): Controller ↔ Host über die Board-Radio, Capture nach Debian.  
**Kein USB-Dongle nötig** (Topologie **F_ONCHIP**).

> **v0.2.8** — BT16 ATT throughput · session gap classify · live kB/s charts `:8081` · clock-sync markers · impact matrix.  
> **Nicht claimed:** RF/Air-Sniffer · Classic auf S3 · MITM · voller GATT-Stack · HCI = Air.

Wissensbasis: [technology-audit / esp32-bt-analyzer](https://github.com/MPunktBPunkt/technology-audit/tree/main/projects/esp32-bt-analyzer) · Basis-FW: [ESP32.esp-hub](https://github.com/MPunktBPunkt/ESP32.esp-hub) `esp-hub-base` **v1.10.5**.

---

## Architecture

```text
Peer ESP / Phone
        │  BLE (S3) · Classic+BLE (.87)
        ▼
┌──────────────────────────┐
│ On-chip BT controller    │  VHCI thin host · HCI ring (PSRAM on S3)
│ .88 Central / .89 Peer   │  BTAC TCP :9753
│ .87 Classic+BLE          │
└────────────┬─────────────┘
             │ WiFi HTTP + BTAC
             ▼
┌──────────────────────────┐
│ Debian collector         │  Lab UI :8081 · control :9751
│ session → .btac          │  decode JSONL · PCAPNG LINKTYPE 201
└──────────────────────────┘
```

| Layer | Was hier gemessen wird |
|-------|-------------------------|
| **L1** | HCI / VHCI frames (primär) |
| **L2** | bounded ATT Read By Type `0x2A00` over HCI ACL (Probe, kein Full-Stack) |
| **L0** | RF/Air — **out of scope** → [`docs/BT15_RF_AIR.md`](docs/BT15_RF_AIR.md) |

## Hard boundaries

| Claim | Status |
|-------|--------|
| ESP32-S3 Classic BR/EDR on-chip | **REJECTED** (Classic nur `.87`) |
| HCI capture = RF sniffer | **REJECTED** |
| Thin ATT name read = full GATT | **REJECTED** |
| USB-Dongle required | **REJECTED** for F_ONCHIP |

## Lab hardware

| IP | Board | Role |
|----|-------|------|
| `.88` | YD-ESP32-S3 N8R2 | OBSERVE_A · BLE Central |
| `.89` | YD-ESP32-S3 N8R2 | Peer Peripheral (advertise) |
| `.87` | D1 Mini ESP32 | Classic+BLE · discoverable / inquiry |

Methods: [`docs/LAB_METHODS.md`](docs/LAB_METHODS.md) · Evidence: [`docs/EVIDENCE.md`](docs/EVIDENCE.md) · Exits: [`docs/GATE_EXITS.md`](docs/GATE_EXITS.md).

### UIs

| UI | URL |
|----|-----|
| Node (`.88`) | `http://192.168.178.88/` · Tab **Analyzer** |
| **Debian bt-analyzer** | **`http://192.168.178.187:8081/`** · BTAC session + peer actions |
| Debian usb-analyzer (parallel) | `http://192.168.178.187:8080/` |

```bash
./tools/run_lab_controller.sh start   # :8081 + :9751
```

Session API: `POST /api/v1/session/start` `{ip}` · `stop` · `GET …/download`.

---

## Build / OTA

```bash
cd firmware/analyzer-node
# PlatformIO: ~/.platformio/penv/bin/pio
pio run -e analyzer-s3
./tools/flash_lab_ota.sh 192.168.178.88
./tools/flash_lab_ota.sh 192.168.178.89

pio run -e analyzer-esp32          # -Os; field OTA slot on .87 is 1966080 B
ENV=analyzer-esp32 ./tools/flash_lab_ota.sh 192.168.178.87
```

Portal SSID: `BT-Analyzer-Setup` · Device name: `bt-analyzer`.

Useful node APIs: `/api/bt/scan|advertise|connect|disconnect`, `/api/bt/gatt/read-name`, `/api/bt/discoverable/*`, `/api/bt/classic/name`, BTAC on `:9753`.

## Lab / Gates

Primary topology **F_ONCHIP**. Status matrix: [`docs/GATES.md`](docs/GATES.md).

```bash
python3 tools/lab_run_gates.py          # BT5–BT14 + session gap classify
python3 tools/lab_gap_classify.py --host 192.168.178.88 --btac docs/evidence/….btac
python3 tools/lab_bt16_throughput.py    # ATT notify/write matrix
python3 tools/lab_bt16_impact.py        # analyzer impact (WiFi STA constant)
python3 tools/lab_clock_sync.py         # multi-node offset estimate
python3 tools/lab_gate_exits.py
```

| Gate band | Stand (0.2.8) |
|-----------|----------------|
| BT0–BT13 | **CODE READY** / lab MEASURED |
| BT14 | **ready for external review** |
| BT15 | **deferred** (RF/Air) |
| BT16 | **CODE READY** (thin ATT throughput + charts) |
| BT17 | **scaffold** ([`docs/BT17_CLASSIC_AUDIO.md`](docs/BT17_CLASSIC_AUDIO.md)) |

## License

- Project code / docs: MIT (this repo).
- Vendored `firmware/analyzer-node/src/core/` from ESP32.esp-hub: **GPL-3.0**.
