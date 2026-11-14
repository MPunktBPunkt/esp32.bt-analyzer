# FIELD B2-A-TX Matrix — 2026-11-14 Vormittag

```yaml
status: DONE · NEGATIVE (this state)
gate: B2-A-TX
hu: D4:36:39:CF:E1:B5 (BMW 38304)
local: C8:C9:A3:CB:37:96 (.87)
control: HFP AG OFF · Dummy parallel on .131 with Phone BCL
analysis: docs/analysis/FIELD_B2A_TX_PATTERNS_20261114.md
```

## Verdict

| Channel | Session IDs (prefix) | Socket | Wire (btmon) |
|--------:|----------------------|--------|--------------|
| 6 | `…T1008Z` `…T1009Z` `…AFTER15…` `…SETTLE…` `…AUDIOOK…T1115Z` | refused / host down | SABM→**DM** (nach Mux-UA) |
| 7 | `…T1009Z` `…AUDIOOK…T1116Z` | refused | DM |
| 8 | `…T1009Z` `…AUDIOOK…T1116Z` | refused | DM |
| 9 | `…AUDIOOK…T1116Z` | refused | DM |
| 10 | `…AUDIOOK…T1116Z` | refused | DM |
| 5 | `…AUDIOOK…T1116Z` | refused | DM |

**AUDIOOK:** HU-UI „BT-Audio mit BT-Analyzer verbunden“ + A2DP Sink aktiv — **änderte SPP-Accept nicht**.

Artefakte: `docs/evidence/FIELD_B2A_TX_CH{5,6,7,8,9,10}_*.{json,jsonl,md}`.

## Epistemik

- Negativ ≠ „kein BCL am F20“ (Phone-Logcat öffnet ch6).
- Negativ ≠ H-E gelöst: Reserve-Kanäle gleich tot.
- Contrast: B2-A observe-only 2026-11-13 = UA+empty; heute = DLC-DM vor Payload.
