# Gates — esp32.bt-analyzer

Each gate exit documents: **FACT · MEASURED · INFERENCE · UNKNOWN · NEXT TEST**.  
No release claim without green gate status.

| Gate | Ziel | Status |
|------|------|--------|
| **BT0** | Hub-Basis / OTA / Web UI / NVS / reboot / PSRAM | **IN PROGRESS** (skeleton) |
| **BT1** | USB Host enumeration (VID/PID/if/ep) | pending |
| **BT2** | HCI interface detection (cmd/evt/ACL/SCO/ISO) | pending |
| **BT3** | Raw HCI capture (ts, dir, type, payload) | pending |
| **BT4** | TCP capture stream (BTAC framing) | pending |
| **BT5** | PSRAM ring buffer | pending |
| **BT6** | Lossless lab capture (drops=0, gaps=0) | pending |
| **BT7** | Debian decoder (JSONL) | pending |
| **BT8** | PCAPNG export (HCI, not RF) | pending |
| **BT9** | BLE dongle validation | pending |
| **BT10** | Classic dongle validation | pending |
| **BT11** | Second ESP / HCI stimulus | pending |
| **BT12** | Long capture | pending |
| **BT13** | WiFi/USB stress + recovery | pending |
| **BT14** | Technology-audit project green | pending |
| **BT15** | RF / Air investigation (separate) | deferred |

## BT0 exit criteria

| Check | Expectation |
|-------|-------------|
| Hub registration | device appears with `version`, `chipModel`, heap/PSRAM |
| OTA | `./tools/flash_lab_ota.sh <IP>` → reboot → status OK |
| Web UI | `GET /` and `/api/status` 200 |
| NVS | WiFi credentials survive reboot |
| Reboot recovery | AppCore recovery path |
| PSRAM | `freePsram` / `psramSize` reported (N8R2) |

## Forbidden vague exits

- „Bluetooth works“ without layer (L0/L1/L2)
- „Sniffer“ without RF evidence
- HCI MEASURED sold as Air FACT
