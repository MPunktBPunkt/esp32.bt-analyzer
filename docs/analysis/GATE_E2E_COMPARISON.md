# Gate E2E Comparison — Field vs Lab Stub vs Field-Replay

```yaml
date: 2026-11-18
purpose: Make the open gate unambiguous before car session
```

| Phase | Field real (own client 18.11.) | Lab Stub (`f20_sim`) | Field-Replay (`FIELD_AUTH_PROBE`) |
|-------|--------------------------------|----------------------|-----------------------------------|
| BCL | **PASS** | **PASS** | **PASS** |
| Etch OPEN 4004 | **PASS** | **PASS** | **PASS** |
| Certificate TX | **TX** | **TX** | **TX** |
| Certificate response | **REJECT** | **ACCEPT** (challenge) | **REJECT** |
| Login | not successful | **PASS** (VOID_OK) | not reached |
| AUTHENTICATED | ❌ | ✅ LAB only | ❌ |
| AM | not reached | PASS (lab) | not reached |
| RHMI | not reached | PASS (lab) | not reached |
| CDS / Resource | not reached | PASS (lab) | not reached |

## Verdict

> Not Transport. Not BCL. Not Etch. Not RHMI. Not Resource. **Authorization.**

Next Field variable = APP / APP_AUTH acceptance only.  
Lab AUTHENTICATED ≠ Field AUTHENTICATED until HU positive correlated login is measured.

## Evidence

- Field reject: `docs/evidence/FIELD_AUTH_PROBE_20261118T061541Z/`
- Lab A/B + freeze: `docs/evidence/LAB_GATE_AUTH_AB_B3_20261118T133244Z/`
- Golden positive bytes (LAB): `tools/fixtures/auth_golden_lab_stub_login_ok.json`
- Runbook: `docs/analysis/FIELD_DAY_ONE_VARIABLE_GATE.md`
