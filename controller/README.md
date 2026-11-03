# controller (Debian)

Lab control plane for **bt-analyzer**, parallel to usb-analyzer.

| Service | Port | Notes |
|---------|------|-------|
| Lab Web UI + HTTP API | **8081** | `http://192.168.178.187:8081/` |
| Control TCP (HELLO later) | **9751** | placeholder accept loop |
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

Nodes are poll-proxied (no ESP HELLO required yet). BT4 may add discovery on `:9751`.
