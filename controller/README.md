# controller (Debian)

Lab control plane for **bt-analyzer**, parallel to usb-analyzer.

| Service | Port | Notes |
|---------|------|-------|
| Lab Web UI + HTTP API | **8081** | `http://192.168.178.187:8081/` |
| Control TCP (HELLO later) | **9751** | placeholder accept loop |
| Capture BTAC (on ESP) | **9753** | Debian → `tools/btac_recv.py <ip>` |
| usb-analyzer (other project) | 8080 / 9750 | must not collide |

## Run

```bash
./tools/run_lab_controller.sh start   # or restart / status / stop
# optional user service:
# ./tools/install_lab_controller_service.sh
```

## API (v0)

| Path | Role |
|------|------|
| `GET /api/v1/health` | controller health |
| `GET /api/v1/nodes` | poll `.88`/`.89` `/api/status` (+ usb) |
| `GET /api/v1/node/<ip>/drain?n=32` | proxy capture JSONL |
| `POST /api/v1/node/<ip>/inject` | `{ "hex": "…" }` |
| `POST /api/v1/node/<ip>/hci-write` | host bulk write when HCI open |
| `GET /api/v1/agents` | hci-agent D1s (`.131`, `.87`): `hciAgent` status + B/s, pkt/s per direction |
| `POST /api/v1/btmon/start` · `/stop` | `ssh $BT_HOST_SSH stdbuf -oL btmon` (default `root@192.168.178.108`) |
| `GET /api/v1/btmon?since=<seq>&hci=<n>` | parsed btmon blocks (dir, proto, title, details), ring 400 |

Nodes are poll-proxied (no ESP HELLO required yet). BTAC capture is pull from ESP `:9753`.
