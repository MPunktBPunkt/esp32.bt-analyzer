# Gate E2E Comparison — Field vs Lab Stub vs Field-Replay

```yaml
date: 2026-11-20
purpose: Make the open gate unambiguous — crypto closed, F20 Gate B open
canonical: SAS_STATUS_CRYPTO_CLOSED_20261120.md
```

| Phase | Field real (own client 18.11.) | Lab Stub (`f20_sim`) | Lab MyBMW→f20_sim (20.11.) | Field-Replay (`FIELD_AUTH_PROBE`) |
|-------|--------------------------------|----------------------|----------------------------|-----------------------------------|
| BCL | **PASS** | **PASS** | **PASS** | **PASS** |
| Etch OPEN 4004 | **PASS** | **PASS** | **PASS** | **PASS** |
| Certificate TX | **TX** | **TX** | **TX** (APP_AUTH bundle) | **TX** |
| Certificate response | **REJECT** | **ACCEPT** (challenge) | **ACCEPT** (challenge) | **REJECT** |
| Pad / RSA-VERIFY | n/a (reject) | stub | **8/8 VALID** (`0x02000000`) | n/a |
| Login | not successful | **PASS** (VOID_OK) | **PASS** → `rhmi_*` | not reached |
| AUTHENTICATED | ❌ | ✅ LAB only | ✅ LAB only | ❌ |
| AM / RHMI / CDS | not reached | PASS (lab) | PASS (lab) | not reached |

## Verdict

> Not Transport. Not BCL. Not Etch. Not the crypto formula. **F20 authorization (Gate B).**

| Layer | Status |
|-------|--------|
| Client sign path (CASE A) | **CLOSED** |
| Pad + PKCS#1 + Cert↔Sig (Wire) | **CLOSED** — [`SAS_PAD_RSA_VERIFY_LAB_20261120.md`](SAS_PAD_RSA_VERIFY_LAB_20261120.md) |
| Lab HU accept | **FACT** |
| F20 HU accept | **OPEN** — [`GATE_APP_AUTH_ACCEPTANCE_20261118.md`](GATE_APP_AUTH_ACCEPTANCE_20261118.md) |

Lab AUTHENTICATED ≠ Field AUTHENTICATED until HU positive correlated login is measured on the car.

## Evidence

- Field reject: `docs/evidence/FIELD_AUTH_PROBE_20261118T061541Z/`
- Lab RSA-VERIFY: `docs/analysis/SAS_PAD_RSA_VERIFY_LAB_20261120.md`
- Status: `docs/analysis/SAS_STATUS_CRYPTO_CLOSED_20261120.md`
- Lab A/B + freeze: `docs/evidence/LAB_GATE_AUTH_AB_B3_20261118T133244Z/`
- Runbook: `docs/analysis/FIELD_DAY_ONE_VARIABLE_GATE.md`
- Signer CASE A: `docs/analysis/SAS_SIGNER_CASE_A_CLOSED_20261119.md`
