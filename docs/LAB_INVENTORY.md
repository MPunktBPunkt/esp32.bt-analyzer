# Lab inventory — bt-analyzer

Stand: 2026-11-05 · Instrument FW **0.3.14** · PROXY P0 inventory

**Overwrite authorized** on `.87` / `.88` / `.89` for bt-analyzer gates (OTA).  
**`.131` overwrite blocked** — live Heizung/Metermaster (PROXY phone-side candidate). See [`PROXY.md`](PROXY.md).

| IP | Board | Chip | Role (assigned) | Notes |
|----|-------|------|-----------------|-------|
| `192.168.178.88` | YD-ESP32-S3 **N8R2** | ESP32-S3 | **OBSERVE_A** | On-chip **BLE** VHCI · 8 MiB + 2 MiB PSRAM |
| `192.168.178.89` | YD-ESP32-S3 **N8R2** | ESP32-S3 | **OBSERVE_B / peer** | On-chip **BLE** VHCI · future car observe |
| `192.168.178.87` | D1 Mini | ESP32-D0WDQ6 | **PROXY car-side / Classic analyzer** | Classic **+** BLE · BD `c8:c9:a3:cb:37:96` |
| `192.168.178.131` | D1 Mini | ESP32 (hub) | **PROXY phone-side candidate** | **Heizung today** · flash blocked · not bt-analyzer |

| Service | Address |
|---------|---------|
| Debian / Cursor LXC | `192.168.178.187` (`DebianCursor`) |
| **Host BT (onboard)** | Intel **Wireless-AC 9260** → Proxmox BlueZ SSH oracle — [`HOST_BT.md`](HOST_BT.md) |
| **bt-analyzer Lab UI** | `http://192.168.178.187:8081/` |
| bt-analyzer control TCP | `:9751` |
| usb-analyzer Lab UI (parallel) | `http://192.168.178.187:8080/` |
| esp-hub | `192.168.178.113:8093` |

## Chip capability matrix (FACT)

| Capability | `.88` / `.89` S3 | `.87` classic ESP32 |
|------------|------------------|---------------------|
| On-chip VHCI capture | **primary** | **primary** |
| BLE on-chip | yes | yes |
| Classic BR/EDR on-chip | **no** | **yes** |
| USB OTG Host | yes (legacy optional) | **no** |
| PSRAM (N8R2) | 2 MiB | typically none |

## Flash

```bash
# S3 BLE VHCI
./tools/flash_lab_ota.sh 192.168.178.88
./tools/flash_lab_ota.sh 192.168.178.89

# Classic ESP32 (.87)
ENV=analyzer-esp32 ./tools/flash_lab_ota.sh 192.168.178.87
```

## Serial

- S3: UART/COM (CH343)
- D1 Mini: USB-Serial as usual
