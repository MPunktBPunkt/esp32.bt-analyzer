# LAB P0 PiDrive UI Sequence — pidrive

**verdict:** FAIL

- hold_s: **0.0**
- rhmi_state: `None`
- selected_action: `None`
- seq_phase: `None`
- counts: `{'setData_PiDrive': 0, 'action_tx': 1, 'action_rx': 0, 'acks': 0, 'sinks': 0, 'complete': 0}`
- inject: `None`

## Chain

- setData(100, PiDrive)
- HU MENU_TEST_ACTION(200)
- phone onActionEvent
- ack
- pidrive_action_sink → PI_DRIVE_TEST

## Criteria

| Check | OK |
|-------|----|
| `hold_ge_60s` | no |
| `runtime_active` | no |
| `no_abort` | yes |
| `no_hu_close_fatal` | no |
| `setData_PiDrive` | no |
| `action_tx_menu_test` | yes |
| `action_rx_menu_test` | no |
| `action_ack` | no |
| `pidrive_sink_PI_DRIVE_TEST` | no |
| `selected_action_done` | no |

