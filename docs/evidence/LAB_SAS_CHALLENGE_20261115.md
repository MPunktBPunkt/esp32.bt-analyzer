# LAB — sas-probe challenge (2026-11-15)

## Session

| | |
|--|--|
| session_id | `LAB_SAS_CHALLENGE_20261115T122806Z` |
| peer | OnePlus 12 `AC:C0:48:5E:CB:20` |
| flags | `--sas-probe challenge --handshake-delay 3` + DATAACK + WD |
| capture | [`LAB_SAS_CHALLENGE_20261115T122806Z.jsonl`](LAB_SAS_CHALLENGE_20261115T122806Z.jsonl) |

## Wire

1. INIT → HS v5 → SP4 → KNOCK → OPEN 5001 / OPEN 4004 (src 10→11→12)
2. HU sends **SAS challenge** on each OPEN 4004 and again after PKCS7 (`sas_challenge_tx` ×7)
3. Phone continues: PKCS7 certs on 10/11/12 — **same pattern as `none`**
4. **No** `sas_login_rx`, **no** new Phone→HU message class after challenge
5. WD stable; UI: AAIdrive „verbunden mit BMW 1 Series“, MyBMW verbunden

## Verdict

**LAB FACT (vorläufig):** Non-zero Challenge allein erzeugt **keinen** erkennbaren kausalen
Protokollübergang zu einer neuen Phone→HU-Aktion (kein Login-/RHMI-Kandidat im jsonl).

Grün/„verbunden“ ≠ SAS-Login auf dem Wire (wie bei `none`).

## Next

Freeze this log. Optional: `challenge_rhmi` or `adaptive` as separate run — do not stack
changes into this session.
