# Hardware

## Lab start set

| Item | Role |
|------|------|
| `.88` YD-ESP32-S3 **N8R2** | OBSERVE_A — on-chip **BLE** VHCI |
| `.89` YD-ESP32-S3 **N8R2** | OBSERVE_B / peer — on-chip **BLE** |
| `.87` D1 Mini **ESP32** | Classic **+** BLE — PROXY **car-side** / analyzer |
| `.131` D1 Mini **ESP32** | PROXY **phone-side** Classic analyzer (was Metermaster) |
| Debian PC (`DebianCursor`) | Lab UI `:8081` · control `:9751` · PROXY brain |
| Intel Wireless-AC 9260 BT | Onboard host radio — BlueZ SSH oracle · [`HOST_BT.md`](HOST_BT.md) |

USB Bluetooth dongles are **not required** for F_ONCHIP. Optional for legacy A_OBSERVE. Host 9260 ≠ Air sniffer.

PROXY Classic endpoints = **`.87` + `.131` only** (not S3). Transport = Network HCI / WiFi — [`PROXY.md`](PROXY.md).

See [`LAB_INVENTORY.md`](LAB_INVENTORY.md) · [`LAB_METHODS.md`](LAB_METHODS.md).

## Board facts (N8R2)

- 8 MiB Flash · 2 MiB Quad PSRAM · USB OTG FS (GPIO19/20)
- Native USB Full-Speed only (no HS)
- Shared PHY: Serial monitor via **UART/COM**
- Configure PSRAM as in esp-hub (`qio_qspi`, `BOARD_HAS_PSRAM`)

## Chip boundary

| Capability | ESP32-S3 | ESP32 (D1) |
|------------|----------|------------|
| BLE on-chip | yes | yes |
| Classic BR/EDR on-chip | **no** | **yes** |
| USB OTG Host | yes (FS) | no |

Classic Bluetooth analyzer role = **`.87`**, not S3 radio.
