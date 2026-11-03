# Lab inventory — bt-analyzer

Stand: 2026-11-03 · Instrument FW **0.1.3** (S3) · Reference hub-base **1.10.5** (classic ESP32)

**Overwrite authorized** on `.87` / `.88` / `.89` for bt-analyzer gates (OTA).

| IP | Board | Chip | Role (assigned) | Notes |
|----|-------|------|-----------------|-------|
| `192.168.178.88` | YD-ESP32-S3 **N8R2** | ESP32-S3 | **OBSERVE_A** | USB OTG Host · HCI capture · 8 MiB + 2 MiB PSRAM · UART/COM for Serial |
| `192.168.178.89` | YD-ESP32-S3 **N8R2** | ESP32-S3 | **OBSERVE_B / STIMULUS** | Same HW class; reserved for Dual-Dongle (C) or USB-HCI Stimulus (B, BT11) |
| `192.168.178.87` | D1 Mini | ESP32-D0WDQ6 | **REF_ENDPOINT** | **Kein USB-OTG** · on-chip BLE **+ Classic BR/EDR** · Endpoint-/Korrelations-Node, nie USB-HCI Host |

| Service | Address |
|---------|---------|
| Debian / Cursor LXC | `192.168.178.187` |
| esp-hub | `192.168.178.113:8093` |

## Chip capability matrix (FACT)

| Capability | `.88` / `.89` S3 | `.87` classic ESP32 |
|------------|------------------|---------------------|
| USB OTG Host | yes (FS) | **no** |
| USB-HCI dongle capture | yes (project primary) | **REJECTED** |
| BLE on-chip | yes | yes |
| Classic BR/EDR on-chip | **no** | yes |
| PSRAM (N8R2) | 2 MiB | typically none |

## Flash

```bash
# S3 observe / capture image
./tools/flash_lab_ota.sh 192.168.178.88
./tools/flash_lab_ota.sh 192.168.178.89

# Classic ESP32 reference (hub-base, not bt-analyzer USB image)
./tools/flash_lab_ota.sh 192.168.178.87 \
  BIN_SRC=/path/to/esp-hub-base.1.10.5.esp32.bin \
  FW_NAME=esp-hub-base.1.10.5.esp32.bin
```

Or: `./tools/lab_flash_ref_d1.sh`

## Serial

- S3: UART/COM (CH343) — **not** OTG while Host active  
- D1 Mini: USB-Serial as usual  

## Power / USB-HCI

S3 OTG typically **does not source 5 V** → self-powered Hub/Dongle for OBSERVE topologies.
