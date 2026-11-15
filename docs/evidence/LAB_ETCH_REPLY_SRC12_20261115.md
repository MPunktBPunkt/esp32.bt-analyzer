# LAB — etch-reply-src 12 (field-shaped HU etch TX) 2026-11-15

## Session

| | |
|--|--|
| session_id | `LAB_ETCH_REPLY_SRC12_20261115T124240Z` |
| flags | `--sas-probe challenge --etch-reply-src 12` |
| capture | [`LAB_ETCH_REPLY_SRC12_20261115T124240Z.jsonl`](LAB_ETCH_REPLY_SRC12_20261115T124240Z.jsonl) |

## Result

- HU etch DATA all as **src=12 dest=4004** (`field_src_dest4004`) ×7
- Phone after challenge: same PKCS7/OPEN pattern as desk-direction baseline
- `sas_login_rx`: 0 · UI green

## Verdict

**LAB FACT:** Reply-port shape alone (12→4004 vs 4004→phone) does **not** change
Phone app-layer progress in this stub setup.
