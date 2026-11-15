# LAB — unsolicited CDS push (2026-11-15)

## Session

| | |
|--|--|
| session_id | `LAB_CDS_PUSH_20261115T125247Z` |
| flags | `--sas-probe challenge --cds-push` |
| capture | [`LAB_CDS_PUSH_20261115T125247Z.jsonl`](LAB_CDS_PUSH_20261115T125247Z.jsonl) |

## Result

- On first OPEN 4004: challenge + CDS TX for `sensors.SOCBattery`, `iva_MYV_LIGHT_INTERIOR`, `vehicle.VIN`
- Phone after push: same PKCS7/OPEN pattern (+ WD); no CDS/RHMI/SAS ASCII reply class
- `sas_login_rx` 0 · UI green

## Verdict

**LAB FACT:** Unsolicited stub CDS (incl. VIN) does **not** elicit a new Phone→HU
app-layer step. Displayed VIN/Fahrzeugdaten in AAIdrive remain consistent with
account/cache, not Dummy CDS bytes.
