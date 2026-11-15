# LAB — sas-probe adaptive (2026-11-15)

## Session

| | |
|--|--|
| session_id | `LAB_SAS_ADAPTIVE_20261115T123721Z` |
| peer | OnePlus 12 `AC:C0:48:5E:CB:20` |
| flags | `--sas-probe adaptive --handshake-delay 3` |
| capture | [`LAB_SAS_ADAPTIVE_20261115T123721Z.jsonl`](LAB_SAS_ADAPTIVE_20261115T123721Z.jsonl) |

## Wire

Two RFCOMM attempts (brief drop, then stable) — matches operator report.

Per successful session:

1. OPEN 4004 → HU **challenge only**
2. Phone PKCS7 → HU escalates **one** RHMI (`reason=phone_tx_after_challenge`)
3. Further OPENs 11/12 → challenge again; RHMI not re-sent (cap already used)
4. Phone pattern unchanged: certs only — **no** `sas_login_rx`
5. WD stable; AAIdrive green

## Verdict

**LAB FACT:** Adaptive classify→react works as designed (challenge → Phone TX → one RHMI).
It still does **not** elicit a new Phone→HU app-layer step beyond certs.

## P0 ladder complete (2026-11-15)

| Stage | HU probe | New Phone TX? | UI green |
|-------|----------|---------------|----------|
| none | no etch | baseline certs | yes (flaky) |
| challenge | challenge | no | yes |
| challenge_rhmi | challenge+RHMI | no | yes |
| adaptive | challenge→RHMI after Phone TX | no | yes |

**Conclusion:** Lab can keep BCL/WD/UI-green without reconstructing SAS/RHMI.
Next leverage = real Golden-Session btsnoop and/or differential payload probing
(field `--etch-reply-src`, HU-OPEN, altered challenge bytes) — not more static stubs.
