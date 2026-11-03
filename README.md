# esp32.bt-analyzer

![Version](https://img.shields.io/badge/version-0.1.3-blue)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Gate](https://img.shields.io/badge/gate-BT3%20capture%20partial-yellow)](docs/GATE3_STATUS.md)

ESP32-S3 **Bluetooth USB/HCI Analyzer** lab: USB Bluetooth dongle → HCI capture → WiFi/TCP → Debian.

> **v0.1.3** — BT0–BT2 + **BT3 raw capture** (PSRAM ring, bulk ACL, inject). Event interrupt IN noch offen.  
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


---

## Repo layout

```text
firmware/analyzer-node/   # PlatformIO · esp-hub-base AppCore (BT0)
firmware/common/          # shared headers
controller/               # Debian plane (BT4+)
tools/flash_lab_ota.sh    # OTA via /ota-upload
docs/                     # ARCHITECTURE · GATES · EVIDENCE · HCI · …
tests/host/               # offline decoder tests (BT7+)
```

## Build / OTA

```bash
cd firmware/analyzer-node
pio run -e analyzer-s3

# Hub-compatible artifact name:
#   bt-analyzer.0.1.3.esp32s3.bin
./tools/flash_lab_ota.sh 192.168.178.88

curl -s http://192.168.178.88/api/usb/status
curl -s -X POST -d 'hex=040e0401030c00' http://192.168.178.88/api/capture/inject
curl -s 'http://192.168.178.88/api/capture/drain?n=8'
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
