# LAB Music NP Spine Sequence — LAB_MUSIC_NP_SPINE_SEQ_DUAL_20261121T133537Z

**verdict:** FAIL

- hold_s: **6.04**
- rhmi_state: `None`
- selected_action: `None`
- seq_phase: `None`
- counts: `{'setData': 0, 'models_seen': [], 'triggers': 0, 'events_seen': [], 'action_tx': 0, 'action_rx': 0, 'acks': 0, 'sinks': 0, 'complete': 0}`

## Chain

- setData(444 source, 445 artist, 446/447 title)
- triggerEvent(660 multimediaInfo, 661 statusbar)
- HU actions 336 + 248
- phone ack + MUSIC_NP_SPINE sink

## Criteria

| Check | OK |
|-------|----|
| `hold_ge_45s` | no |
| `runtime_active` | no |
| `no_abort` | yes |
| `no_hu_close_fatal` | no |
| `setData_models_444_447` | no |
| `trigger_events_660_661` | no |
| `action_tx_336_248` | no |
| `action_rx_336_248` | no |
| `action_ack_336_248` | no |
| `music_np_sink` | no |
| `selected_or_complete` | no |

