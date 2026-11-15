# LAB — sas-probe challenge_rhmi (2026-11-15)

## Session

| | |
|--|--|
| session_id | `LAB_SAS_CHALLENGE_RHMI_20261115T123408Z` |
| peer | OnePlus 12 `AC:C0:48:5E:CB:20` |
| flags | `--sas-probe challenge_rhmi --handshake-delay 3` |
| capture | [`LAB_SAS_CHALLENGE_RHMI_20261115T123408Z.jsonl`](LAB_SAS_CHALLENGE_RHMI_20261115T123408Z.jsonl) |

## Wire

1. HS v5 → SP4 → KNOCK → OPEN/DATA 4004 (src 10→11→12)
2. HU on each OPEN: **challenge + RHMI stub** (`sas_challenge_tx` ×7, `rhmi_capabilities_tx` ×7)
3. After PKCS7: again challenge+RHMI
4. Phone: only PKCS7 cert pattern — **no** `sas_login_rx`, no RHMI/CDS ASCII from Phone
5. WD stable; AAIdrive UI green („BMW 1 Series“)

## Verdict

**LAB FACT (vorläufig):** Stub-RHMI zusätzlich zur Challenge erzeugt **keinen** neuen
Phone→HU-Protokollschritt gegenüber `challenge` / `none`. Grün ≠ gültiges RHMI-Format.

## Ladder so far

| Stage | New Phone TX after HU probe? | UI green |
|-------|------------------------------|----------|
| none | (baseline certs) | sometimes |
| challenge | no | yes |
| challenge_rhmi | no | yes |
