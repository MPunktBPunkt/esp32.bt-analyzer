# Autonomous Lab Job — post-`d64ae81` (2026-11-18)

## Epistemic key

| Tag | Meaning |
|-----|---------|
| **FIELD FACT** | Bytes observed OnePlus↔BMW |
| **REPLAY FACT** | Those bytes reprocessed by our stack |
| **FIELD PROTOCOL FACT** | Live HU accepted/continued — **not claimed here** |
| **LAB FACT** | f20_sim / in-process host loopback |

---

## P1 — Regression after AuthState

| Check | Result | Level |
|-------|--------|-------|
| Host suite (auth + p0_p2 + w0 + dummy_hu + etch) | **61 OK** | LAB |
| `test_auth_state_p1` T1–T4 + R5 | **PASS** | LAB |
| In-process Stub→AUTHENTICATED→RUNTIME_ACTIVE | **PASS** (~0.01 s) | LAB |
| SE 213 keeps RUNTIME_ACTIVE | **PASS** | LAB |
| Dual-ESP PiDrive/Soak over air | **BLOCKED** | infra |

Dual-ESP: `.87`↔`.131` bond fails (`HU not found` / discovery). Bridges up with pinned names; Classic inquiry between D1s not completing. **Not** an AuthState regression — transport pairing infra. Host-loopback covers SAS/RHMI/SE213 semantics.

Evidence: `LAB_P1_REGRESSION_20261118T102113Z/` (pidrive bond_failed + `INPROCESS_LIFECYCLE.txt`).

---

## P2 — Field capture replay

Tool: `tools/field_replay_fsm.py`

| Capture | AuthState (FSM) | Bootstrap | epistemic |
|---------|-----------------|-----------|-----------|
| `FIELD_AUTH_PROBE_…/phone.jsonl` | **CERTIFICATE_REJECTED** | NOT_REACHED | field_measured → **REPLAY FACT** |
| `FIELD_DUMP_…/bcl.jsonl` | **CERTIFICATE_REJECTED** | NOT_REACHED | same |

Reports: `AUTH_PROBE/FSM_REPORT.md`, `DUMP/FSM_REPORT.md`

```text
Transport   BCL_ACTIVE-equivalent (HS v5/14/0x4000)   REPLAY
Etch        RPC_ACTIVE                                REPLAY
Auth        CERTIFICATE_REJECTED                      REPLAY
Bootstrap   NOT_REACHED
AM/RHMI/Runtime NOT_REACHED
```

`auth_verdict = fsm_certificate_rejected` — **never** `accepted` from bytes alone.

---

## P3 — Auth test matrix

| Source | Expectation | Result |
|--------|-------------|--------|
| Lab Stub challenge+VOID_OK | AUTHENTICATED | PASS |
| Field-style cert Exception | CERTIFICATE_REJECTED | PASS |
| Challenge→Login Exception | LOGIN_REJECTED | PASS |
| Mutated challenge + VOID login | AUTHENTICATED (Lab; no crypto verify) | PASS |
| Full FIELD_AUTH_PROBE replay | CERTIFICATE_REJECTED | PASS |

Tests: `tests/host/test_field_replay_fsm.py` (18 with auth_state_p1: all OK).

---

## Explicitly not done (per freeze)

- No new F20 Model/Action IDs as Field
- No fake SAS authorization
- No write11/EAGAIN/Dual-ESP transport deep-dive
- No B3 Relay live yet (prep only via replay tooling)
- No claim that Resource Digests = HU accepted auth

---

## Next when home / car on

1. Fix Dual-ESP Classic discovery/bond → short Soak + PiDrive air regression  
2. Field session with real APP `.p7b` (single variable)  
3. B3 Relay Phone↔HU for live SAS bodies  
