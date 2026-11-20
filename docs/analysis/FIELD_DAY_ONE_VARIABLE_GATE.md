# Field Day — One-Variable Auth Gate

```yaml
status: READY for car — Gate B only
variable: APP / APP_AUTH authorization context (F20 HU acceptance)
constants: phone, BT link, BCL, Etch, session build, payloads, timing
crypto: CLOSED — pad 0x02000000 · RSA-VERIFY 8/8 lab · see SAS_STATUS_CRYPTO_CLOSED_20261120.md
signer: CASE A closed — do not dig libaudio further
stop_rule: AUTHENTICATED → snapshot → END (no RHMI/AM/CDS/PiDrive)
```

Status: [`SAS_STATUS_CRYPTO_CLOSED_20261120.md`](SAS_STATUS_CRYPTO_CLOSED_20261120.md).  
Field question is **HU accept/reject**, not “where is the key” / “what is the formula.”

## Question (exactly one)

> Akzeptiert der echte F20 genau dieses `sas_certificate` + die korrekt erzeugte Signatur (`pad=MD5(0x02000000)`)?

```text
RFCOMM / BCL_ACTIVE
        ↓
sas_certificate
        ↓
challenge
        ↓
pad 0x02000000 → XOR → MD5 → RSA-4096
        ↓
sas_login
        ↓
AUTHENTICATED / rhmi_*   ← STOP + snapshot   (= Gate B)
```

## Run A — Auth Gate (mandatory)

1. Pair/connect as usual (OnePlus ↔ F20). ACL AUTH+ENCRYPT.
2. Start capture: btmon + B3 relay / phone jsonl with **authorized** SecurityModule context (Arm B). Optional Arm A first with lab/stub for reject baseline same day.
3. Agent flags: `--stop-on-authenticated` (and optionally `--stop-on-auth-reject` for Arm A).
4. On `AuthState=AUTHENTICATED`: **freeze** — write `AUTHENTICATED_SNAPSHOT.json` + raw frames; **end session**.
5. Do **not** TX AM / RHMI / Resource / CDS / PiDrive in Run A.
6. Offline: `PYTHONPATH=tools python3 tools/sas_pad_crosscheck.py --from-bcl-jsonl …` → expect `VALID`.

Arm table:

| Arm | Credential | Expected |
|-----|------------|----------|
| A | Lab/stub (known reject) | `CERTIFICATE_REJECTED` or `LOGIN_REJECTED` |
| B | Authorized APP + APP_AUTH (live MyBMW) | `AUTHENTICATED` **only** if HU reply positive + `inReplyTo` correlated |

## Run B — Topology (only if A ACCEPT)

Separate session after Run A evidence is secured:

```text
AUTHENTICATED → AM → RHMI → Resource → CDS → Runtime
```

Map F20 handles + real Model/Action/Resource IDs. Still **no** PiDrive integration.

## Lab anchors (pre-frozen)

| Artifact | Role |
|----------|------|
| `docs/analysis/SAS_PAD_RSA_VERIFY_LAB_20261120.md` | Crypto + A↔B Wire FACT (8/8) |
| `tools/sas_pad_crosscheck.py` | RSA-VERIFY offline |
| `tools/fixtures/auth_golden_lab_stub_login_ok.json` | Byte sequence (LAB) |
| `tools/lab_auth_ab_matrix.py` | A/B + freeze |
| `docs/analysis/GATE_E2E_COMPARISON.md` | Field vs Lab vs Replay |

## Explicitly do **not** touch

write11/EAGAIN · Dual-ESP discovery · Fake-Auth · Lab→F20 ID mapping · Resource upload · PiDrive · RHMI soak · PKCS#12 unwrap · Binder/TEE hunts · libaudio formula dig · VIN→key

Arm B means **live MyBMW SecurityModule** on phone — never a copied BMW private key on the Pi.

### Capture extras (RSA-VERIFY)

B3/HU jsonl must allow reassembly of:

1. `sas_certificate` (PKCS7 PEM/DER)  
2. HU **challenge_hex** (16 B)  
3. Phone **login_sig** (512 B)

```bash
PYTHONPATH=tools python3 tools/sas_pad_crosscheck.py --from-bcl-jsonl /path/to/b3.jsonl
```

Pad recipe (APP_AUTH): `pad = MD5(0x02000000_be); xored = challenge XOR pad; digest = MD5(xored)`.  
**Not** X509 serial. **Not** VIN→key.

## Operator one-liner (host)

```bash
# after bridges up + phone paired to F20 on field adapter:
python3 /tmp/bcl_dummy/bcl_dummy_hu_agent.py b2a-tx \
  --adapter-bd <PHONE_BD> --hu-bd <F20_BD> --channel 6 \
  --full-client --knock wire_v5 --selectproto 4 \
  --stop-on-authenticated --stop-on-auth-reject \
  --seconds 90 --log /tmp/bcl_dummy/FIELD_AUTH_GATE.jsonl
```

Prefer B3 Phone↔F20 relay for full wire capture. Never export BMW private keys.
