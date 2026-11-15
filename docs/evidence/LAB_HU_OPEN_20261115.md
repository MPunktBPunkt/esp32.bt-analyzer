# LAB — HU-initiated OPEN 10/12/18 (2026-11-15)

## Session

| | |
|--|--|
| session_id | `LAB_HU_OPEN_20261115T125018Z` |
| flags | `--sas-probe challenge --hu-open-srcs 10,12,18` |
| capture | [`LAB_HU_OPEN_20261115T125018Z.jsonl`](LAB_HU_OPEN_20261115T125018Z.jsonl) |

## Result

- After KNOCK: HU OPEN→4004 for src **10, 12, 18** (`hu_open_tx` ×3)
- Phone still OPENs 10→11→12 itself and sends PKCS7 certs
- No distinct reaction to HU OPEN 18; `sas_login_rx` 0; UI green

## Verdict

**LAB FACT:** Unsolicited HU OPEN ports do not change Phone app-layer progress
beyond the usual cert sequence in this stub lab.
