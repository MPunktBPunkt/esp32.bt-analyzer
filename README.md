# esp32.bt-analyzer

![Version](https://img.shields.io/badge/version-0.2.6-blue)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Gate](https://img.shields.io/badge/gate-BT3%20onchip%20VHCI-yellow)](docs/GATES.md)

ESP **on-chip Bluetooth HCI analyzer** (VHCI): board radio → HCI capture → WiFi → Debian.  
**Kein USB-Dongle nötig.**

> **v0.2.6** — BLE Advertise/Scan peer · BTAC `:9753` · JSONL decode (BT7) · F_ONCHIP evidence.  
> **Nicht claimed:** RF/Air sniffer, Classic on S3, MITM, drop-free.

Wissensbasis: [technology-audit](https://github.com/MPunktBPunkt/technology-audit) · Basis-FW: [ESP32.esp-hub](https://github.com/MPunktBPunkt/ESP32.esp-hub) `esp-hub-base` **v1.10.5**.

---

## Goal architecture

```text
Peer (Phone / ESP)
        │ BLE / Classic
        ▼
┌─────────────────────┐
│ On-chip controller  │  VHCI · thin host · Capture · PSRAM
│ .88/.89 S3 = BLE    │
│ .87 ESP32 = Classic+│
└──────────┬──────────┘
           │ WiFi/HTTP
           ▼
┌─────────────────────┐
│ Debian :8081/:9751  │  Lab UI · JSONL
└─────────────────────┘
```

V1 = **L1 HCI capture** + lab scan/connect. L0 RF = UNKNOWN / later.

## Hard boundaries

| Claim | Status |
|-------|--------|
| ESP32-S3 Classic BR/EDR on-chip | **REJECTED** (use `.87`) |
| HCI capture = RF sniffer | **REJECTED** |
| USB dongle required | **REJECTED** for F_ONCHIP |

## Lab hardware

| IP | Board | Role |
|----|-------|------|
| `.88` | YD-ESP32-S3 N8R2 | **OBSERVE_A** (BLE VHCI) |
| `.89` | YD-ESP32-S3 N8R2 | OBSERVE_B / peer |
| `.87` | D1 Mini ESP32 | Classic+BLE on-chip |

Methods: [`docs/LAB_METHODS.md`](docs/LAB_METHODS.md).

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

## Build / OTA

```bash
cd firmware/analyzer-node
pio run -e analyzer-s3
./tools/flash_lab_ota.sh 192.168.178.88
./tools/flash_lab_ota.sh 192.168.178.89

pio run -e analyzer-esp32
ENV=analyzer-esp32 ./tools/flash_lab_ota.sh 192.168.178.87
```

Portal SSID: `BT-Analyzer-Setup` · Device name: `bt-analyzer`.

## Gates

See [`docs/GATES.md`](docs/GATES.md). Primary topology **F_ONCHIP**.

## License

- Project code / docs: MIT (this repo).
- Vendored `firmware/analyzer-node/src/core/` from ESP32.esp-hub: **GPL-3.0**.
