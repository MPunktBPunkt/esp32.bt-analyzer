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

No WG Web-UI in this release — same policy as hu-probe 0.3.42.