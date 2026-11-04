# Protocol — control vs data

## Planes

| Plane | Endpoint | Role |
|-------|----------|------|
| Hub | `:8093` | register / heartbeat / OTA URL |
| Node Web | HTTP `/`, `/api/status`, `/ota-upload` | local ops |
| Debian Lab UI | `:8081` | poll-proxy nodes + drain/inject |
| Debian control TCP | `:9751` | HELLO later; placeholder accept |
| Capture data | ESP `:9753` | **BTAC v1** stream (BT4) — ESP listens |

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
