# Autonomous Lab — APP/APP_AUTH Gate Prep (2026-11-18)

```yaml
gate: APP_APP_AUTH_ACCEPTANCE
claim_levels: LAB | REPLAY
not_claimed: FIELD PROTOCOL ACCEPTANCE
```

## Verdict

Lab control plane remains green. Offline/replay phase stays closed. This cycle
ships the **next-field gate harness** only — no transport re-research, no fake auth.

| Check | Result | Level |
|-------|--------|-------|
| Host unittest suite | **157 OK** | LAB |
| Auth A/B matrix (A reject / B freeze / B full / C replay) | **PASS** | LAB+REPLAY |
| AUTHENTICATED freeze snapshot | **PASS** (`AUTH_AB/AUTHENTICATED_SNAPSHOT.json`) | LAB |
| B3 relay byte-identity selftest | **PASS** (95/95) | LAB |
| In-process Stub→AUTHENTICATED→RUNTIME_ACTIVE | **PASS** | LAB |
| Dual-ESP air | **BLOCKED** (Classic discovery) | infra |

## Deliverables

| Path | Purpose |
|------|---------|
| `docs/analysis/GATE_APP_AUTH_ACCEPTANCE_20261118.md` | Gate diagram + A/B protocol + epistemic correction |
| `tools/lab_auth_ab_matrix.py` | Lab A/B + freeze + field replay arm |
| `tools/b3_rfcomm_relay.py` | Transparent RFCOMM/TCP relay + BCL/Etch decode |
| `bcl_dummy_hu_agent --stop-on-authenticated` | Field halt after positive HU login |
| `tests/host/test_lab_auth_ab_matrix.py` | Matrix regression |
| `tests/host/test_b3_rfcomm_relay.py` | Relay identity regression |

## Auth A/B (this run)

| Arm | AuthState | Bootstrap | Pass |
|-----|-----------|-----------|------|
| A_LABSIM_REJECT | CERTIFICATE_REJECTED | NOT_REACHED | PASS |
| B_LAB_STUB_ACCEPT_FREEZE | AUTHENTICATED | HANDLES_CREATING | PASS |
| B_LAB_STUB_ACCEPT_FULL | AUTHENTICATED | HANDLES_READY | PASS |
| C_FIELD_REPLAY | CERTIFICATE_REJECTED | NOT_REACHED | PASS |

## Epistemic reminder (report wording)

- Earlier Connected captures = F20 stack/RPC **FIELD** evidence.
- Current own client session = stops at cert reject → AM/RHMI/CDS **NOT_REACHED**.
- Lab `modelId=100` / `actionId=200` / `PI_DRIVE_TEST` remain **LAB ONLY**.

## Next when car / authorized SecurityModule available

1. Identify APP/APP_AUTH bundle (`inspect_pkcs7_bundle`) — `.p7b` ≠ private key.
2. Single-variable A/B vs LABSIM.
3. Optional B3 RFCOMM relay Phone↔F20 for full bodies.
4. On `AUTHENTICATED`: `--stop-on-authenticated` → snapshot → stop.
5. Only then AM → RHMI → Resource → CDS → measured IDs.
