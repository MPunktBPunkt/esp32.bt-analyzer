# Architecture — esp32.bt-analyzer

## Positioning

**HCI Analyzer** (Bluetooth host↔controller traffic), not RF sniffer, not MITM.

Epistemic rule: do not promote HYPOTHESIS/UNKNOWN to FACT.  
HCI ≠ Bluetooth Air. USB Host API ≠ USB Wire. Endpoint events ≠ HCI.

## Capture layers

```text
L0  RF / PHY / Air          → UNKNOWN / later BT15 (separate capability)
L1  Controller / HCI        → V1 primary (USB Bluetooth dongle)
L2  Host / Profiles         → Debian analysis (not ESP)
L3  Debian Analysis         → Collector / JSONL / PCAPNG / Wireshark
```

## Target topology

```text
Bluetooth DUT
      │ Bluetooth
      ▼
USB Bluetooth Controller (HCI)
      │ USB
      ▼
┌────────────────────────┐
│ ESP32-S3 #1 (OBSERVE)  │
│ USB OTG = HOST         │
│ HCI Capture + ts       │
│ PSRAM ring             │
│ TCP forward            │
└───────────┬────────────┘
            │ WiFi/TCP
            ▼
┌────────────────────────┐
│ Debian                 │
│ Collector / Decoder    │
│ JSONL / PCAPNG         │
└───────────┬────────────┘
            │ optional BT11+
            ▼
┌────────────────────────┐
│ ESP32-S3 #2 (STIMULUS) │
│ USB Device / HCI replay│
└────────────────────────┘
```

## Modes

| Mode | Path | Phase |
|------|------|-------|
| **A — HCI OBSERVE** | Dongle → ESP Host → TCP → Debian | BT1–BT6 |
| **B — HCI RELAY/STIMULUS** | Host ↔ ESP-A ↔ Debian ↔ ESP-B ↔ Controller | BT11+ experimental |

## Firmware basis

Derive from **esp-hub-base v1.10.5** only — not a fork of usb-analyzer firmware.  
usb-analyzer is the **architecture / gate / evidence** reference.

```text
ESP32.esp-hub / esp-hub-base
        │
        ▼
 bt-analyzer (AppCore BT0 → + USB/HCI modules)
```

## Capture pipeline (from BT3)

```text
USB callback → internal RAM → capture queue → PSRAM ring → TCP producer
```

Never: USB callback → TCP send directly.

## Hard boundaries

| Claim | Status |
|-------|--------|
| ESP32-S3 on-chip Classic BR/EDR analyzer | **REJECTED** |
| HCI capture = RF capture | **REJECTED** |
| Profile parsing on ESP as SoT | **REJECTED** for V1 |
