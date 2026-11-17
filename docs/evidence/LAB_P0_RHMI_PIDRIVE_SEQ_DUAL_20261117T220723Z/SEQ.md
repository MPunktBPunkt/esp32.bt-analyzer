# LAB P0 PiDrive UI Sequence — LAB_P0_RHMI_PIDRIVE_SEQ_DUAL_20261117T220723Z

**verdict:** PASS

- hold_s: **93.92**
- rhmi_state: `RUNTIME_ACTIVE`
- selected_action: `PI_DRIVE_TEST`
- seq_phase: `complete`
- counts: `{'setData_PiDrive': 2, 'action_tx': 1, 'action_rx': 1, 'acks': 1, 'sinks': 1, 'complete': 1}`
- inject: `{'injected': 1, 'actionId': 200, 'handle': 12, 't_rel_s': 25.0}`

## Chain

- setData(100, PiDrive)
- HU MENU_TEST_ACTION(200)
- phone onActionEvent
- ack
- pidrive_action_sink → PI_DRIVE_TEST

## Criteria

| Check | OK |
|-------|----|
| `hold_ge_60s` | yes |
| `runtime_active` | yes |
| `no_abort` | yes |
| `no_hu_close_fatal` | yes |
| `setData_PiDrive` | yes |
| `action_tx_menu_test` | yes |
| `action_rx_menu_test` | yes |
| `action_ack` | yes |
| `pidrive_sink_PI_DRIVE_TEST` | yes |
| `selected_action_done` | yes |

