# esp32.bt-analyzer

![Version](https://img.shields.io/badge/version-0.1.4-blue)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Gate](https://img.shields.io/badge/gate-BT3%20%2B%20Lab%20UI-yellow)](docs/GATE3_STATUS.md)

ESP32-S3 **Bluetooth USB/HCI Analyzer** lab: USB Bluetooth dongle → HCI capture → WiFi/TCP → Debian.

> **v0.1.4** — Node **Analyzer-Tab** + Debian Lab UI **`:8081`** (parallel zu usb-analyzer `:8080`).  
> **Nicht claimed:** RF/Air sniffer, Classic on-chip S3, MITM, drop-free.

Wissensbasis: [technology-audit](https://github.com/MPunktBPunkt/technology-audit) · Basis-FW: [ESP32.esp-hub](https://github.com/MPunktBPunkt/ESP32.esp-hub) `esp-hub-base` **v1.10.5** · Architektur-Referenz: [esp32.usb-analyzer](https://github.com/MPunktBPunkt/esp32.usb-analyzer).

---

## Goal architecture

```text
USB Bluetooth Dongle (HCI)
        │ USB
        ▼
┌─────────────────────┐
│ ESP32-S3 OBSERVE    │  USB Host · HCI Capture · PSRAM · TCP
└──────────┬──────────┘
           │ WiFi/TCP
           ▼
┌─────────────────────┐
│ Debian              │  Collector · Decoder · JSONL · PCAPNG
└─────────────────────┘
```

V1 = **L1 HCI capture**. L0 RF = UNKNOWN / later. L2 profiles = Debian.

## Hard boundaries

| Claim | Status |
|-------|--------|
| ESP32-S3 Classic BR/EDR analyzer (on-chip) | **REJECTED** |
| HCI capture = RF sniffer | **REJECTED** |
| Endpoint JSONL = Phone↔Original traffic | **REJECTED** |

## Lab hardware

| IP | Board | Role |
|----|-------|------|
| `.88` | YD-ESP32-S3 N8R2 | **OBSERVE_A** (USB-HCI) |
| `.89` | YD-ESP32-S3 N8R2 | OBSERVE_B / STIMULUS |
| `.87` | D1 Mini ESP32 | **REF_ENDPOINT** (Classic+BLE on-chip, **no** USB Host) |

Methods / topologies: [`docs/LAB_METHODS.md`](docs/LAB_METHODS.md) · Inventory: [`docs/LAB_INVENTORY.md`](docs/LAB_INVENTORY.md).

### UIs

| UI | URL |
|----|-----|
| Node (`.88`) | `http://192.168.178.88/` · Tab **Analyzer** |
| **Debian bt-analyzer** | **`http://192.168.178.187:8081/`** |
| Debian usb-analyzer (parallel) | `http://192.168.178.187:8080/` |

```bash
./tools/run_lab_controller.sh start   # :8081 + :9751
```

---

## Repo layout

```text
firmware/analyzer-node/   # PlatformIO · Analyzer tab UI
firmware/common/
controller/ · web/        # Debian Lab UI :8081
tools/flash_lab_ota.sh
docs/
tests/host/
```

## Build / OTA

```bash
cd firmware/analyzer-node && pio run -e analyzer-s3
./tools/flash_lab_ota.sh 192.168.178.88
./tools/flash_lab_ota.sh 192.168.178.89
```

Portal SSID: `BT-Analyzer-Setup` · Device name: `bt-analyzer`.  
OTG = DUT only; board typically does **not** source VBUS 5 V — use self-powered hub/dongle.

## Gates

See [`docs/GATES.md`](docs/GATES.md). BT3 partial ([`GATE3_STATUS.md`](docs/GATE3_STATUS.md)). First milestone: **BT0–BT6**.

## Epistemics

`FACT` · `MEASURED` · `INFERENCE` · `HYPOTHESIS` · `UNKNOWN` · `REJECTED` — [`docs/EVIDENCE.md`](docs/EVIDENCE.md).

## License

- Project code / docs: MIT (this repo).
- Vendored `firmware/analyzer-node/src/core/` from ESP32.esp-hub: **GPL-3.0** (retain headers; sync only from upstream).
