# LAB Auth A/B Gate Matrix — 20261120T085450Z

Claim levels: **LAB** / **REPLAY**. Never FIELD PROTOCOL ACCEPTANCE.

| Arm | Level | Expected | AuthState | Bootstrap | Pass |
|-----|-------|----------|-----------|-----------|------|
| `A_LABSIM_REJECT` | LAB | `CERTIFICATE_REJECTED` | `CERTIFICATE_REJECTED` | `NOT_REACHED` | PASS |
| `B_LAB_STUB_ACCEPT_FREEZE` | LAB | `AUTHENTICATED` | `AUTHENTICATED` | `HANDLES_CREATING` | PASS |
| `B_LAB_STUB_ACCEPT_FULL` | LAB | `AUTHENTICATED` | `AUTHENTICATED` | `HANDLES_READY` | PASS |
| `C_FIELD_REPLAY` | REPLAY | `CERTIFICATE_REJECTED` | `CERTIFICATE_REJECTED` | `NOT_REACHED` | PASS |

## Gate reminder

```text
SAS challenge  ✅
       │
       ▼
APP / APP_AUTH acceptance  ← next Field variable
```

## Notes

- **A_LABSIM_REJECT:** Simulates FIELD-style cert reject; bootstrap must stay NOT_REACHED
  - exception: `Certificate is invalid or expired.`
- **B_LAB_STUB_ACCEPT_FREEZE:** Freeze on AUTHENTICATED — causal snapshot before AM/RHMI
- **B_LAB_STUB_ACCEPT_FULL:** Full lab stub path to handles (not Field acceptance)
  - exception: `SetData was not successful.`
- **C_FIELD_REPLAY:** FIELD MEASURED bytes → REPLAY FACT only; not FIELD ACCEPTANCE
  - exception: `Certificate is invalid or expired.`
