# esp32.bt-analyzer

![Version](https://img.shields.io/badge/version-0.1.2-blue)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Gate](https://img.shields.io/badge/gate-BT2%20HCI%20detect-yellow)](docs/GATE2_STATUS.md)

ESP32-S3 **Bluetooth USB/HCI Analyzer** lab: USB Bluetooth dongle → HCI capture → WiFi/TCP → Debian.

> **v0.1.2** — BT0 Hub/OTA · BT1 USB enum · **BT2 USB-HCI role map** (descriptors).  
> **Nicht claimed:** HCI packet capture, RF/Air sniffer, Classic on-chip S3, MITM.

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

## Lab hardware (planned)

| Rolle | Gerät |
|-------|--------|
| ESP Observe | YD-ESP32-S3 N8R2 |
| ESP Stimulus (later) | YD-ESP32-S3 N8R2 |
| BT | USB BLE + Classic dongles + self-powered Hub |
| Control | Debian · esp-hub `:8093` |

Details: [`docs/HARDWARE.md`](docs/HARDWARE.md).

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
#   bt-analyzer.0.1.2.esp32s3.bin
./tools/flash_lab_ota.sh 192.168.178.88

# After USB dongle on OTG (UART/COM for Serial):
curl -s http://192.168.178.88/api/usb/status   # dut + hci.detected / endpoints
```

Portal SSID: `BT-Analyzer-Setup` · Device name: `bt-analyzer`.  
OTG = DUT only; board typically does **not** source VBUS 5 V — use self-powered hub/dongle.

## Gates

See [`docs/GATES.md`](docs/GATES.md). BT1/BT2 code ready. First milestone: **BT0–BT6**.

## Epistemics

`FACT` · `MEASURED` · `INFERENCE` · `HYPOTHESIS` · `UNKNOWN` · `REJECTED` — [`docs/EVIDENCE.md`](docs/EVIDENCE.md).

## License

- Project code / docs: MIT (this repo).
- Vendored `firmware/analyzer-node/src/core/` from ESP32.esp-hub: **GPL-3.0** (retain headers; sync only from upstream).
