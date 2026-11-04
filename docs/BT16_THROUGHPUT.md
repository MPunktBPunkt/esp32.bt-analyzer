# BT16 — BLE ATT throughput (CAPABILITY vs BENCHMARK)

```yaml
status: active
host: .88 Central
peer: .89 Peripheral
layer: L2_over_HCI
fw: "0.3.0+"
```

## Exit classes

| Class | Criteria |
|-------|----------|
| **CAPABILITY_PASS** | connected + ATT traffic observed + HCI traffic observed |
| **BENCHMARK_PASS** | capability + RX packets>0 + `file_gaps==0` + RX-side `app_seq_gaps==0` + `app_reorder==0` + `capture_drops==0` + ring drained + defined duration/MTU/payload/pace |

A run may be CAPABILITY_PASS while BENCHMARK_FAIL (e.g. `file_gaps=1`).

App loss is always scored on the **RX side** (host for Notify, peer for Write).
`file_resync` (seq decrease / stream change) is diagnostic — not counted as `file_gaps`.

## Evidence layers (must stay separate)

| Layer | Fields |
|-------|--------|
| Application | `app_tx/rx_packets`, `app_seq_gaps`, `app_reorder`, bytes, Bps median/p10/p90 |
| Capture | frames delta, `capture_drops` / `droppedSession` |
| BTAC | frames, `btac_seq_gaps` / `seqGapsSession` |
| File | `file_frames`, `file_gaps` |
| Transport | `hci_Bps`, `btac_Bps` |

## Tools

```bash
python3 tools/lab_bt16_throughput.py              # 30s × 3 full matrix
python3 tools/lab_bt16_throughput.py --quick      # smoke (duration<10 ⇒ no BENCHMARK)
python3 tools/lab_bt16_impact.py                  # A–D × 60s × 3
python3 tools/lab_gap_classify.py --host … --btac …
```

## Lab notes (0.3.0)

- BTAC starts **after** ATT warmup; HTTP `/api/capture/drain` returns 409 while BTAC owns the ring.
- Pace defaults: 18 ms (≤20 B) / 28 ms (≥100 B).
- Fresh controller state after many reconnects may require OTA/reboot if Notify RX stalls.

## MEASURED (0.3.0) — payload 20 B matrix

Evidence: `LAB_BT16_20261104T161828Z` · capability=PASS · **benchmark=PASS** (2×30 s)

| mode | mtu | payload | median B/s | bench |
|------|-----|---------|------------|-------|
| notify | 23 | 20 | 591 | 2/2 |
| notify | 247 | 20 | 562 | 2/2 |
| write | 23 | 20 | 762 | 2/2 |
| write | 247 | 20 | 755 | 2/2 |

Notify@247/200 remains CAPABILITY-only under load (app gaps) — not yet BENCHMARK green.

## UI

Debian `:8081` live kB/s — diagnostic only, not the audit result.
