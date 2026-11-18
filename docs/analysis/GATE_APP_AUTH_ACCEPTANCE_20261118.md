# Gate — APP / APP_AUTH Acceptance (2026-11-18)

```yaml
status: OPEN — next field gate
transport: FIELD PASS (ACL/AUTH/ENCRYPT, SCN6, BCL HS v5, Etch 4004)
blocker: SAS certificate / login acceptance by F20 HU
frozen: write11/EAGAIN root-cause, Dual-ESP air, Lab Model/Action IDs as Field
```

## Epistemic correction (report wording)

| Claim | Correct reading |
|-------|-----------------|
| „F20 bis SAS/RHMI/AM/CDS feldseitig nachgewiesen“ | **Stack + RPCs** observed in earlier Connected sessions (FIELD PROTOCOL FACT for those sessions) |
| Current own client session | Stops at `CERTIFICATE_REJECTED` → AM/RHMI/CDS **NOT_REACHED** |
| Lab PiDrive `modelId=100` / `actionId=200` / `PI_DRIVE_TEST` | **LAB ONLY** — never copy as F20 Field IDs |

No contradiction: earlier captures prove the HU stack; this client has not completed that chain under a rejected credential.

## Current gate diagram

```text
Transport       ✅ FIELD
BCL             ✅ FIELD
Etch            ✅ FIELD
SAS challenge   ✅ FIELD
                 │
                 ▼
        APP / APP_AUTH acceptance
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
| B | Authorized APP + APP_AUTH context (Android/MyBMW path; **no** exported private key) | `AUTHENTICATED` **only** if HU reply is positive + mid-correlated |

### Must identify before TX

1. Which APP / APP_AUTH bundle is used (CN, `SAS.CertificateType`, source app/build).
2. Bundle source (device path / MyBMW asset) — use `etch_codec.inspect_pkcs7_bundle` for digests/CN; a `.p7b` alone does **not** sign.
3. Sign path: native SecurityModule / authorized helper — **never** copy BMW private key onto the Pi.

### Wire correlation (mandatory)

```text
sas_certificate TX  →  challenge RX  →  sas_login TX  →  login result RX
```

AuthState is taken **only** from HU reply via `classify_result` + `inReplyTo`:

- `CERTIFICATE_REJECTED`
- `LOGIN_REJECTED`
- `AUTHENTICATED`

### On AUTHENTICATED

1. `--stop-on-authenticated` (agent) → abort further AM/RHMI TX.
2. Write `AUTHENTICATED_SNAPSHOT.json` from `forensic_snapshot()` + raw frames.
3. Only then (separate run): AM → Resource → RHMI → CDS → measured Model/Action IDs.

Causal anchor if B succeeds and `am_registerApp` appears:

> Credential changed → SAS accepted → Connected control plane unlocked  
> (not „more bytes found“)

## Lab preparations shipped with this gate

| Item | Role | Claim level |
|------|------|-------------|
| `tools/lab_auth_ab_matrix.py` | A/B + freeze-on-AUTHENTICATED | LAB / REPLAY |
| `tools/lab_auth_golden.py` + `tools/fixtures/auth_golden_lab_stub_login_ok.json` | Byte-exact positive login sequence | LAB anchor |
| `tools/b3_rfcomm_relay.py` | Transparent RFCOMM/TCP relay + BCL/Etch decode | LAB scaffold; FIELD when Phone↔F20 |
| `bcl_dummy_hu_agent --stop-on-authenticated` | Field-safe halt after positive login | agent flag |
| Host unit tests T5 + golden | LOGIN_SENT≠AUTHENTICATED; fixture validate | LAB |
| `FIELD_DAY_ONE_VARIABLE_GATE.md` | Car operator runbook A then B | plan |
| `GATE_E2E_COMPARISON.md` | Field / Lab / Replay table | docs |
| `B3_RELAY_FREEZE.md` | Smoke only — no optimization | freeze |

## Explicitly out of scope until ACCEPT

- Dual-ESP air soak / discovery optimization
- EAGAIN / write11 root-cause
- F20 Action mapping from Lab IDs
- Fake auth bypass / unsigned challenge forgery
- Resource-upload / RHMI-soak / PiDrive-seq expansion
- Claiming Resource Digests = HU authorized resources
- ESP HCI-over-WiFi performance tuning
