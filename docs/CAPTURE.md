# Capture format

## ESP → Debian (binary): BTAC v1

TCP port **9753** (ESP listens; Debian connects). Gate **BT4**.

| Offset | Size | Field | Notes |
|--------|------|-------|-------|
| 0 | 4 | magic | `BTAC` |
| 4 | 1 | version | `1` |
| 5 | 1 | flags | `0` reserved |
| 6 | 2 | stream_id | increments per TCP session |
| 8 | 4 | sequence | ring seq; gaps = DROP visibility |
| 12 | 8 | timestamp | µs (`esp_timer`) |
| 20 | 1 | direction | 1=H→C · 2=C→H |
| 21 | 1 | packet_type | 1=cmd · 2=evt · 3=ACL · 4=SCO · 5=ISO |
| 22 | 1 | endpoint | USB EP or `0` for VHCI |
| 23 | 1 | reserved | `0` |
| 24 | 2 | length | payload bytes (≤1024) |
| 26 | N | payload | raw HCI (often H4) |
| 26+N | 4 | crc32 | IEEE over header+payload |

All multi-byte fields **little-endian**. TCP must tolerate partial reads, coalescing, disconnect/reconnect, sequence gaps.

### Tooling

```bash
python3 tools/btac_recv.py 192.168.178.88 -n 64 -o /tmp/cap.btac --jsonl /tmp/cap.jsonl
python3 tools/btac_decode.py /tmp/cap.btac -o /tmp/cap.jsonl --stats   # BT7
python3 tools/btac_to_pcapng.py /tmp/cap.btac -o /tmp/cap.pcapng       # BT8 HCI
python3 tools/lab_f_onchip_peer_evidence.py   # F_ONCHIP peer
python3 tools/lab_run_gates.py                # BT5–BT13 batch
```


While a BTAC client is connected, the stream owns ring dequeues. HTTP `/api/capture/drain` remains for idle/poll use.

## Debian transforms

```text
BTAC → JSONL → PCAPNG → Wireshark
```

PCAP must be labeled as **HCI**, never as RF/Air capture.

## Metrics (required)

`captured` · `forwarded` · `dropped` · `seqGaps` · `ring_fill` · `ring_high_water` · `btac.bytes` · `btac.sendFails`

Silent data corruption is forbidden — DROPs and gaps stay visible.
