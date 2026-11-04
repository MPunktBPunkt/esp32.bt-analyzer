# BT16 — BLE ATT throughput (CAPABILITY vs BENCHMARK)

```yaml
status: active
host: .88 Central
peer: .89 Peripheral
layer: L2_over_HCI
fw: "0.2.9+"
```

## Exit classes

| Class | Criteria |
|-------|----------|
| **CAPABILITY_PASS** | connected + ATT traffic observed + HCI traffic observed |
| **BENCHMARK_PASS** | capability + `file_gaps==0` + `app_seq_gaps==0` + `app_reorder==0` + `capture_drops==0` + defined duration/MTU/payload |

A run may be CAPABILITY_PASS while BENCHMARK_FAIL (e.g. `file_gaps=1`).

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
python3 tools/lab_bt16_throughput.py --quick      # smoke
python3 tools/lab_bt16_impact.py                  # A–D × 60s × 3
python3 tools/lab_gap_classify.py --host … --btac …
```

## UI

Debian `:8081` live kB/s — diagnostic only, not the audit result.
