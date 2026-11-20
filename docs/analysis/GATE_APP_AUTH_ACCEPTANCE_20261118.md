# Gate — APP / APP_AUTH Acceptance (2026-11-18)

```yaml
status: OPEN — next field gate (F20 HU acceptance only)
transport: FIELD PASS (ACL/AUTH/ENCRYPT, SCN6, BCL HS v5, Etch 4004)
blocker: SAS certificate / login acceptance by F20 HU  (= Gate B)
signer_arch: CLOSED — CASE A + Wire RSA-VERIFY 8/8 (2026-11-20)
crypto: CLOSED — pad 0x02000000 · PKCS#1 v1.5 DigestInfo-MD5 · Cert↔Sig FACT
canonical: SAS_STATUS_CRYPTO_CLOSED_20261120.md
frozen: write11/EAGAIN root-cause, Dual-ESP air, Lab Model/Action IDs as Field
```

**Signer / crypto (not the Field gate):** closed —  
[`SAS_STATUS_CRYPTO_CLOSED_20261120.md`](SAS_STATUS_CRYPTO_CLOSED_20261120.md) ·  
[`SAS_SIGNER_CASE_A_CLOSED_20261119.md`](SAS_SIGNER_CASE_A_CLOSED_20261119.md) ·  
[`SAS_PAD_RSA_VERIFY_LAB_20261120.md`](SAS_PAD_RSA_VERIFY_LAB_20261120.md).

SAS is a localized MyBMW native block (`libaudio.so` + embedded PKCS#12 + OpenSSL).  
Wire formula + Signer↔Cert = **FACT** (lab).  
**Still open:** whether the **F20 HU accepts** an authorized APP/APP_AUTH constellation on the wire.

## Epistemic correction (report wording)

| Claim | Correct reading |
|-------|-----------------|
| „F20 bis SAS/RHMI/AM/CDS feldseitig nachgewiesen“ | **Stack + RPCs** observed in earlier Connected sessions (FIELD PROTOCOL FACT for those sessions) |
| Current own client session | Stops at `CERTIFICATE_REJECTED` → AM/RHMI/CDS **NOT_REACHED** |
| Lab MyBMW → f20_sim RSA-VERIFY + `rhmi_*` | **LAB FACT** — crypto closed; ≠ F20 Gate B |
| Lab PiDrive `modelId=100` / `actionId=200` / `PI_DRIVE_TEST` | **LAB ONLY** — never copy as F20 Field IDs |

## Current gate diagram

```text
Transport       ✅ FIELD
BCL             ✅ FIELD
Etch            ✅ FIELD
SAS crypto      ✅ Wire FACT (pad 0x02000000, RSA-VERIFY 8/8)
                 │
                 ▼
        Gate B — F20 APP / APP_AUTH acceptance
                 │
        ┌────────┴────────┐
        │                 │
      REJECT            ACCEPT
        │                 │
      STOP       → AM/RHMI/CDS (then snapshot)
```

## Single-variable A/B (next car session)

Change **only** the credential / SecurityModule profile.

| Arm | Credential | Expected AuthState |
|-----|------------|--------------------|
| A | LABSIM / stub bundle (current) | `CERTIFICATE_REJECTED` or `LOGIN_REJECTED` |
| B | Authorized APP + APP_AUTH (live MyBMW path; **no** exported private key) | `AUTHENTICATED` **only** if HU reply is positive + mid-correlated |

### Must identify before TX

1. Which APP / APP_AUTH bundle is used (CN, `SAS.CertificateType`, source app/build).
2. Bundle source — `etch_codec.inspect_pkcs7_bundle`; a `.p7b` alone does **not** sign.
3. Sign path: **live** MyBMW `SecurityModule.signChallenge()` → `libaudio.so` / `EVP_PKEY_sign`.  
   **Never** extract PKCS#12 / private key onto the Pi.

### Crypto wording (post Wire FACT 2026-11-20)

| Claim | Status |
|-------|--------|
| Pad u32 APP_AUTH = `0x02000000` | **FACT** (8/8 + 2³²) |
| Pad = X509 serial `0x0AA9` | **REJECTED** |
| PKCS#1 v1.5 + DigestInfo-MD5 | **FACT** |
| Wire Cert ↔ login_sig | **FACT** |
| Literal `APP_AUTH` in native | **NOT_FOUND** |
| PKEY lookup `"com.bmwgroup.connected.bmw"` | **FACT** |
| PKEY alias ↔ embedded PKCS#12 identity | **INFERENCE** |
| Lab HU accept (`rhmi_*`) | **FACT** |
| F20 HU accept | **OPEN** (this gate) |

### Wire correlation (mandatory)

```text
sas_certificate TX  →  challenge RX  →  sas_login TX  →  login result RX
```

Offline: `PYTHONPATH=tools python3 tools/sas_pad_crosscheck.py --from-bcl-jsonl b3.jsonl`  
Expect `verdict=VALID` + pad `0x02000000` before interpreting Gate B.

AuthState **only** from HU reply via `classify_result` + `inReplyTo`:

- `CERTIFICATE_REJECTED`
- `LOGIN_REJECTED`
- `AUTHENTICATED`

### On AUTHENTICATED

1. `--stop-on-authenticated` → abort further AM/RHMI TX.
2. Write `AUTHENTICATED_SNAPSHOT.json` + raw frames.
3. Only then (separate run): AM → Resource → RHMI → CDS → measured Model/Action IDs.

## Lab preparations shipped with this gate

| Item | Role | Claim level |
|------|------|-------------|
| `tools/sas_pad_crosscheck.py --from-bcl-jsonl` | RSA-VERIFY + pad | LAB Wire FACT |
| `tools/lab_auth_ab_matrix.py` | A/B + freeze-on-AUTHENTICATED | LAB / REPLAY |
| `tools/b3_rfcomm_relay.py` | Transparent RFCOMM/TCP relay | LAB; FIELD when Phone↔F20 |
| `bcl_dummy_hu_agent --stop-on-authenticated` | Field-safe halt | agent flag |
| `FIELD_DAY_ONE_VARIABLE_GATE.md` | Car operator runbook | plan |
| `GATE_E2E_COMPARISON.md` | Field / Lab / Replay table | docs |

## Explicitly out of scope until ACCEPT

- Dual-ESP air soak / discovery optimization
- EAGAIN / write11 root-cause
- F20 Action mapping from Lab IDs
- Fake auth bypass / unsigned challenge forgery
- Resource-upload / RHMI-soak / PiDrive-seq expansion
- PKCS#12 unwrap / private-key extraction
- Binder / TEE / Keystore / further libaudio formula digs
- VIN→key
