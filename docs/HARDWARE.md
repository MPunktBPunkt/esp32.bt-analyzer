# Hardware

## Lab start set

| Item | Role |
|------|------|
| 2 × YD-ESP32-S3 **N8R2** | Observe (+ later Stimulus) |
| 1 × USB Bluetooth **BLE** dongle | BT9 |
| 1 × USB Bluetooth **Classic** dongle | BT10 |
| 1 × self-powered USB Hub | bus-powered dongles |
| 1 × Debian PC | collector / Wireshark |

## Board facts (N8R2)

- 8 MiB Flash · 2 MiB Quad PSRAM · USB OTG FS (GPIO19/20)
- Native USB Full-Speed only (no HS)
- Shared PHY: Serial monitor via **UART/COM**, not OTG while Host active
- Configure PSRAM as in esp-hub / usb-analyzer (`qio_qspi`, `BOARD_HAS_PSRAM`)

## Chip boundary

| Capability | ESP32-S3 |
|------------|----------|
| BLE on-chip | yes |
| Classic BR/EDR on-chip | **no** |
| USB OTG Host | yes (FS) |

Classic Bluetooth in this project = **external USB controller**, not S3 radio.
