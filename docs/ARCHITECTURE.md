# Architecture — esp32.bt-analyzer

## Positioning

**HCI Analyzer** on the board’s own Bluetooth controller (VHCI), not a USB dongle, not RF sniffer, not MITM.

Epistemic rule: do not promote HYPOTHESIS/UNKNOWN to FACT.  
HCI ≠ Bluetooth Air.

## Capture layers

```text
L0  RF / PHY / Air          → UNKNOWN / later BT15 (separate capability)
L1  Controller / HCI (VHCI) → V1 primary (on-chip)
L2  Thin host (scan/connect)→ ESP lab UI + HCI cmds
L3  Debian Analysis         → Collector / JSONL / PCAPNG / Wireshark
```

## Target topology (F_ONCHIP)

```text
Peer (Phone / other ESP)
      │ BLE (S3) or Classic+BLE (ESP32)
      ▼
┌────────────────────────┐
│ ESP on-chip controller │
│ VHCI ↔ thin host       │
│ HCI Capture + ts       │
│ PSRAM/internal ring    │
└───────────┬────────────┘
            │ WiFi/HTTP
            ▼
┌────────────────────────┐
│ Debian :8081 / :9751   │
│ Collector / Decoder    │
└────────────────────────┘
```

USB-dongle observe (A_OBSERVE) remains **legacy/optional** (`BT_ANALYZER_ENABLE_USB_HOST=1`).

## Chip matrix

| Board | Chip | On-chip |
|-------|------|---------|
| `.88` / `.89` | ESP32-S3 | **BLE only** |
| `.87` | ESP32 | **Classic + BLE** |

## Modes

| Mode | Path | Phase |
|------|------|-------|
| **F — ONCHIP** | Controller ↔ VHCI host → capture → Debian | primary |
| **A — USB OBSERVE** | Dongle → USB Host → capture | legacy |
| **E — INJECT** | HTTP inject → ring (no radio) | pipeline test |

## Firmware basis

Derive from **esp-hub-base v1.10.5**. Capture path: VHCI recv/send → CaptureRing → drain JSONL.

## PROXY extension (planned)

Debian semantic bridge between two Classic D1 radios (`.131` phone-side, `.87` car-side).  
Not HCI passthrough. Details: [`PROXY.md`](PROXY.md).

## Hard boundaries

| Claim | Status |
|-------|--------|
| ESP32-S3 on-chip Classic BR/EDR | **REJECTED** (use `.87` / `.131`) |
| HCI capture = RF capture | **REJECTED** |
| USB dongle required | **REJECTED** for F_ONCHIP |
| Classic PROXY endpoints | **`.87` + `.131`** (Network HCI) |
