# BT16 — BLE ATT throughput lab

```yaml
status: active
host: .88 Central
peer: .89 Peripheral
layer: L2_over_HCI
```

## What it measures

Application ATT payload rates vs HCI ACL vs BTAC forward — **not** RF/Air.

Payload format: `[seq:u32 LE][ts_us:u64 LE][pad…]`.

## APIs

- `POST /api/bt/throughput/start` `mode=notify|write` `payload=` `mtu=`
- `POST /api/bt/throughput/stop`
- `POST /api/bt/att/mtu` `mtu=`

## Tools

```bash
python3 tools/lab_bt16_throughput.py
python3 tools/lab_bt16_impact.py   # capture load matrix; WiFi STA constant
python3 tools/lab_gap_classify.py --host 192.168.178.88 --btac …
```

## UI

Debian `:8081` — live kB/s chart (App / HCI / BTAC).
