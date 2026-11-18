# CSR ↔ ESP air retest (phone disconnected, ESPs near PC)

| Peer | Verdict | Ping med | →DUT kB/s | DUT→ kB/s | LQ | Notes |
|------|---------|----------|-----------|-----------|----|-------|
| esp87 | PASS | 102.95 | 15.61 | 25.18 | Link quality: 255 |  |
| esp131 | PASS | 102.54 | 16.95 | 23.94 | Link quality: 249 |  |

## Soak 45s CSR ↔ .131 @240

- verdict: **PASS**
- ping median/p90/max: 101.7 / 107.36 / 211.8 ms
- →CSR: 15.57 kB/s · CSR→: 23.2 kB/s
- LQ: Link quality: 249

## ESP status post

- .87: drops=0 boot=3 wifi_rssi=-57 client=192.168.178.108
- .131: drops=0 boot=25 wifi_rssi=-86 client=192.168.178.108

## Comparison

| Path | Ping med | Throughput | Notes |
|------|----------|------------|-------|
| CSR ↔ USB-Phone (earlier) | ~13 ms | ~90–115 kB/s | same host, no WiFi hop |
| CSR ↔ ESP .87/.131 air (this) | ~102 ms | ~16–25 kB/s | HCI TCP over WiFi on ESP side |
| Prior CSR↔ESP attempt | FAIL | — | .87 bridge half-dead / ghost ACL |

**Interpretation:** Separating BT to the USB CSR removes PC-side BT/WiFi antenna sharing, and air RFCOMM now works with LQ≈249–255 and **0 ESP drops**. Remaining ~8× latency / ~4–6× lower Bps vs USB↔USB is dominated by **ESP HCI-over-WiFi bridge**, not stick RF quality.
