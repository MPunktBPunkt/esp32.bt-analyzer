# LAB P0 RHMI Soak — LAB_P0_RHMI_SOAK_DUAL_20261117T212942Z

**verdict:** FAIL

- hold_s: **0.0**
- rhmi_state: `None`
- abort: `None`
- wait_class: `None`
- soak setData: **0** models=[]
- HU action TX: **0** · phone RX **0** · acks **0**
- EAGAIN events: 10 (recovered=4)
- HU closes: `['eof', 'eof', 'eof', 'eof', 'write_error:11', 'eof', 'eof', 'eof', 'write_error:11', 'write_error:11', 'write_error:11', 'write_error:11', 'write_error:11', 'write_error:11', 'write_error:11', 'eof', 'write_error:11', 'eof', 'write_error:11', 'write_error:11', 'eof', 'eof']`
- ServiceExceptions: 0

## Pass criteria

| Check | OK |
|-------|----|
| `hold_ge_540s` | no |
| `runtime_active` | no |
| `no_abort` | yes |
| `no_hu_close` | no |
| `setData_soak_ge_10` | no |
| `actions_tx_ge_5` | no |

## Soak phases

```json
[]
```

## Counts (phone_done)

```json
null
```

