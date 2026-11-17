# LAB P0 RHMI Soak — LAB_P0_RHMI_SOAK_DUAL_20261117T213102Z

**verdict:** PASS

- hold_s: **603.96**
- rhmi_state: `RUNTIME_ACTIVE`
- abort: `None`
- wait_class: `None`
- soak setData: **97** models=[100, 101]
- HU action TX: **105** · phone RX **105** · acks **105**
- EAGAIN events: 4 (recovered=2)
- HU closes: `[]`
- ServiceExceptions: 1

## Pass criteria

| Check | OK |
|-------|----|
| `hold_ge_540s` | yes |
| `runtime_active` | yes |
| `no_abort` | yes |
| `no_hu_close_fatal` | yes |
| `setData_soak_ge_10` | yes |
| `actions_tx_ge_5` | yes |
| `action_acks_ge_5` | yes |

## Soak phases

```json
[
  {
    "ts": 1794951090.091,
    "event": "mybmw_soak_start",
    "phase": "stabilize",
    "note": "0-60s stabilize after RUNTIME_ACTIVE",
    "session_id": "LAB_P0_87_131_HOLD"
  },
  {
    "ts": 1794951150.227,
    "event": "mybmw_soak_phase",
    "phase": "setData_repeat",
    "elapsed_s": 60.1,
    "counts": {},
    "session_id": "LAB_P0_87_131_HOLD"
  },
  {
    "ts": 1794951270.19,
    "event": "mybmw_soak_phase",
    "phase": "multi_model",
    "elapsed_s": 180.1,
    "counts": {
      "setData": 24
    },
    "session_id": "LAB_P0_87_131_HOLD"
  },
  {
    "ts": 1794951390.274,
    "event": "mybmw_soak_phase",
    "phase": "actions_window",
    "elapsed_s": 300.2,
    "counts": {
      "setData": 54,
      "setProperty": 7,
      "actionRx": 3,
      "ackAction": 3
    },
    "session_id": "LAB_P0_87_131_HOLD"
  },
  {
    "ts": 1794951510.171,
    "event": "mybmw_soak_phase",
    "phase": "mixed",
    "elapsed_s": 420.1,
    "counts": {
      "setData": 54,
      "setProperty": 7,
      "actionRx": 62,
      "ackAction": 62
    },
    "session_id": "LAB_P0_87_131_HOLD"
  }
]
```

## Counts (phone_done)

```json
{
  "setData": 97,
  "setProperty": 21,
  "actionRx": 105,
  "ackAction": 105
}
```

