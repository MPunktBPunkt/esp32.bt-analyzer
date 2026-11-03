# Capture format

## ESP → Debian (binary): BTAC

Efficient framed stream (design target BT4):

| Field | Notes |
|-------|-------|
| magic | `BTAC` |
| version | framing version |
| stream_id | session |
| sequence | monotonic; gaps = DROP visibility |
| timestamp | µs |
| direction | host↔controller |
| packet_type | cmd / evt / ACL / SCO / ISO |
| length | payload bytes |
| payload | raw |
| crc | frame integrity |

TCP must tolerate partial reads, coalescing, disconnect/reconnect, sequence gaps.

## Debian transforms

```text
BTAC → JSONL → PCAPNG → Wireshark
```

PCAP must be labeled as **HCI**, never as RF/Air capture.

## Metrics (required)

`captured` · `forwarded` · `dropped` · `sequence_gaps` · `ring_fill` · `ring_high_water` · `tcp_bytes` · `tcp_latency`

Silent data corruption is forbidden — DROPs and gaps stay visible.
