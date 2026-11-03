# Protocol — control vs data

## Planes

| Plane | Endpoint | Role |
|-------|----------|------|
| Hub | `:8093` | register / heartbeat / OTA URL |
| Node Web | HTTP `/`, `/api/status`, `/ota-upload` | local ops |
| Debian control | reserved `:9750` | discovery / session (BT4+) |
| Capture data | TCP (TBD port) | BTAC stream (BT4+) |

## Hub registration (BT0)

Stock esp-hub-base fields: `mac`, `name`, `version` (=`FW_VERSION`), `chipModel`, heap/PSRAM, `ios`.

OTA artifact naming for Hub inventory:

```text
bt-analyzer.<version>.esp32s3.bin
```

## Debian CLI (planned BT7+)

```text
bt-capture --node <ip>
bt-decode capture.btac
bt-to-pcap capture.btac
bt-stats capture.btac
```
