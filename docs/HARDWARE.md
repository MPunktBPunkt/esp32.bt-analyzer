# Hardware

## Lab start set

| Item | Role |
|------|------|
| `.88` YD-ESP32-S3 **N8R2** | OBSERVE_A |
| `.89` YD-ESP32-S3 **N8R2** | OBSERVE_B / STIMULUS |
| `.87` D1 Mini **ESP32** | REF_ENDPOINT (Classic+BLE on-chip; **no** USB Host) |
| USB Bluetooth **BLE** dongle | BT9 / Topology A |
| USB Bluetooth **Classic** dongle | BT10 / Topology A |
| self-powered USB Hub | bus-powered dongles |
| Debian PC | collector / Wireshark |

See [`LAB_INVENTORY.md`](LAB_INVENTORY.md) · [`LAB_METHODS.md`](LAB_METHODS.md).

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
