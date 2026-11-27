# WireGuard lab overlay (bt-analyzer)

Optional transport based on [esp32.wireguard](https://github.com/MPunktBPunkt/esp32.wireguard) **v0.4.9**.
BT scanning / capture must not depend on WireGuard.

| Env | Meaning |
|-----|---------|
| `analyzer-s3` | `BT_ANALYZER_ENABLE_WIREGUARD=0`, FW **0.3.20** |
| `analyzer-s3-wg` | linked stack, FW **0.3.21**, `wgEnable` default **false** |

Flash: `pio run -e analyzer-s3-wg -t upload`

Config: NVS namespace `bt_wg`, or `POST /api/wg/config` with `wgConfigText` / fields.
Status: `/api/status` → `wg.{enable,linked,active,peer_up,err}`.
USB lab: `LAB WG ON|OFF|STATUS`, `LAB WIFI ssid|pass`.
After erase (no WLAN NIC on build host): optional `-DLAB_WIFI_SSID=… -DLAB_WIFI_PASS=…` via CLI/`platformio_override.ini` — never commit secrets.

No WG Web-UI in this release — same policy as hu-probe 0.3.42.

## Lab E2E (2026-11-27, DUT `.88`)

| Step | Result |
|------|--------|
| WG default-off / linked | PASS |
| Guest `FRITZ!Box Gast` → `192.168.179.3` | PASS |
| Route `/24` + `peer_up=1` | PASS |
| Hub HB over WG (`192.168.178.113:8093`) | PASS |

Status wording: **optional WG Lab-validated** — not a field claim.