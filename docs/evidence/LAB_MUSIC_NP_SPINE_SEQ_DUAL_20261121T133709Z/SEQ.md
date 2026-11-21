# LAB Music NP Spine Sequence — LAB_MUSIC_NP_SPINE_SEQ_DUAL_20261121T133709Z

**verdict:** PASS

- hold_s: **63.25**
- rhmi_state: `RUNTIME_ACTIVE`
- selected_action: `MUSIC_NP_SPINE`
- seq_phase: `complete`
- counts: `{'setData': 8, 'models_seen': [444, 445, 446, 447], 'triggers': 2, 'events_seen': [660, 661], 'action_tx': 2, 'action_rx': 2, 'acks': 2, 'sinks': 2, 'complete': 1}`

## Chain

- setData(444 source, 445 artist, 446/447 title)
- triggerEvent(660 multimediaInfo, 661 statusbar)
- HU actions 336 + 248
- phone ack + MUSIC_NP_SPINE sink

## Criteria

| Check | OK |
|-------|----|
| `hold_ge_45s` | yes |
| `runtime_active` | yes |
| `no_abort` | yes |
| `no_hu_close_fatal` | yes |
| `setData_models_444_447` | yes |
| `trigger_events_660_661` | yes |
| `action_tx_336_248` | yes |
| `action_rx_336_248` | yes |
| `action_ack_336_248` | yes |
| `music_np_sink` | yes |
| `selected_or_complete` | yes |

