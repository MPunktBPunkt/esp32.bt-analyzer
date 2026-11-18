# Field Day — One-Variable Auth Gate

```yaml
status: READY for car
variable: APP / APP_AUTH authorization context only
constants: phone, BT link, BCL, Etch, session build, payloads, timing
stop_rule: AUTHENTICATED → snapshot → END (no RHMI/AM/CDS/PiDrive)
```

## Question (exactly one)

> What changes on the wire when the rejected auth constellation is replaced by an authorized APP/APP_AUTH constellation?

```text
RFCOMM / BCL_ACTIVE
        ↓
sas_certificate
        ↓
challenge
        ↓
sas_login
        ↓
AUTHENTICATED   ← STOP + snapshot
```

## Run A — Auth Gate (mandatory)

1. Pair/connect as usual (OnePlus ↔ F20). ACL AUTH+ENCRYPT.
2. Start capture: btmon + phone jsonl / agent with `--full-client` path using **authorized** SecurityModule context (Arm B). Optional Arm A first with lab/stub for reject baseline same day.
3. Agent flags: `--stop-on-authenticated` (and optionally `--stop-on-auth-reject` for Arm A).
4. On `AuthState=AUTHENTICATED`: **freeze** — write `AUTHENTICATED_SNAPSHOT.json` + raw frames; **end session**.
5. Do **not** TX AM / RHMI / Resource / CDS / PiDrive in Run A.

Arm table:

| Arm | Credential | Expected |
|-----|------------|----------|
| A | Lab/stub (known reject) | `CERTIFICATE_REJECTED` or `LOGIN_REJECTED` |
| B | Authorized APP + APP_AUTH | `AUTHENTICATED` **only** if HU reply positive + `inReplyTo` correlated |

## Run B — Topology (only if A ACCEPT)

Separate session after Run A evidence is secured:

```text
AUTHENTICATED → AM → RHMI → Resource → CDS → Runtime
```

Map F20 handles + real Model/Action/Resource IDs. Still **no** PiDrive integration.

## Lab anchors (pre-frozen)

| Artifact | Role |
|----------|------|
| `tools/fixtures/auth_golden_lab_stub_login_ok.json` | Byte sequence TX/RX + mid correlation (LAB) |
| `tools/lab_auth_ab_matrix.py` | A/B + freeze + field replay |
| `tests/host/test_auth_state_p1.py` T5 | LOGIN_SENT ≠ AUTHENTICATED |
| `docs/analysis/GATE_E2E_COMPARISON.md` | Field vs Lab vs Replay table |
| B3 relay selftest | Smoke only — no further optimization |

## Explicitly do **not** touch tomorrow

write11/EAGAIN · Dual-ESP discovery · Fake-Auth · Lab→F20 ID mapping · Resource upload · PiDrive seq · RHMI soak · checkResource · CDS guessing · ESP HCI-WiFi tuning

## Operator one-liner (host)

```bash
# after bridges up + phone paired to F20 on field adapter:
python3 /tmp/bcl_dummy/bcl_dummy_hu_agent.py b2a-tx \
  --adapter-bd <PHONE_BD> --hu-bd <F20_BD> --channel 6 \
  --full-client --knock wire_v5 --selectproto 4 \
  --stop-on-authenticated --stop-on-auth-reject \
  --seconds 90 --log /tmp/bcl_dummy/FIELD_AUTH_GATE.jsonl
```

Replace stub cert path with authorized APP context when available — **never** export BMW private keys.
