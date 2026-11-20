# State-Machine Audit Changelog — 2026-11-18

```yaml
phase: A+B done; P1 AuthState implemented 2026-11-18
commits_docs: STATE_MACHINE_CURRENT / GAP / TRANSITIONS / P1_AUTH
code_changes: tools/bcl_dummy_hu.py, bcl_dummy_hu_agent.py, tests/host/test_auth_state_p1.py
```

## Artefakte

| File | Inhalt |
|------|--------|
| [`STATE_MACHINE_CURRENT.md`](STATE_MACHINE_CURRENT.md) | IST aus Source |
| [`STATE_MACHINE_GAP.md`](STATE_MACHINE_GAP.md) | Ist vs Ziel + Minimalplan |
| [`STATE_MACHINE_TRANSITIONS.md`](STATE_MACHINE_TRANSITIONS.md) | Transition-Matrix |
| [`DEEP_FORENSIC_FIELD_AUTH_REJECT_20261118.md`](DEEP_FORENSIC_FIELD_AUTH_REJECT_20261118.md) | Field Wire-Beweis |

## LAB FACT (bleibt)

- RHMI lifecycle → `RUNTIME_ACTIVE` auf f20_sim nach EAGAIN-Retry (`ffd28aa` / lifecycle PASS).
- Soak ~604 s: 97× setData, Multi-Model, 105 Actions/Acks, EAGAIN recovered, kein Abort (`a5187cb`).
- PiDrive seq: setData(100,"PiDrive") → Action(200) → `PI_DRIVE_TEST` → Ack (`1100644`).
- checkResource=true ⇒ kein automatisches setResource (Source `:1035+`).
- setData ServiceException 213 ⇒ Event, kein Session-Kill (Source `:1511+`).
- EAGAIN Retry-Budget 2 s / Poll 20 ms (nicht anfassen).

**IDs 100 / 200 / PI_DRIVE_TEST = LAB ONLY** — nicht F20.

## FIELD FACT (18.11.)

- Transport BCL_ACTIVE-äquivalent: HS v5/14/0x4000, WD stabil.
- Lab-Cert: HU Reject („Certificate is invalid or expired.“ / „Session is not logged in.“).
- Nachgelagerte AM/RHMI/CDS/Resource: **NOT_REACHED**, nicht widerlegt als „FAILED“.

## Gate follow-up (same day, autonomous)

- [`GATE_APP_AUTH_ACCEPTANCE_20261118.md`](GATE_APP_AUTH_ACCEPTANCE_20261118.md) — next Field variable = APP/APP_AUTH **HU acceptance** only.
- Lab A/B matrix + AUTHENTICATED freeze + B3 relay selftest: `docs/evidence/LAB_GATE_AUTH_AB_B3_20261118T133244Z/`.
- Agent: `--stop-on-authenticated` / `--stop-on-auth-reject`.
- Field-day prep: [`FIELD_DAY_ONE_VARIABLE_GATE.md`](FIELD_DAY_ONE_VARIABLE_GATE.md), [`GATE_E2E_COMPARISON.md`](GATE_E2E_COMPARISON.md), golden fixture `tools/fixtures/auth_golden_lab_stub_login_ok.json`, T5 hard-gate test, [`B3_RELAY_FREEZE.md`](B3_RELAY_FREEZE.md).

## Signer CASE A closed (2026-11-19)

- [`SAS_SIGNER_CASE_A_CLOSED_20261119.md`](SAS_SIGNER_CASE_A_CLOSED_20261119.md) — verified vs technology-audit README + FUNCTION-NOTES.
- Embedded PKCS#12 + PKEY name lookup: **FACT**; alias↔PKCS#12 identity: **INFERENCE**.
- Keystore/TEE/Binder/Asset on path: **REJECTED**. Unwrap/key export: **STOP**.

## Wire crypto closed (2026-11-20)

- Canonical: [`SAS_STATUS_CRYPTO_CLOSED_20261120.md`](SAS_STATUS_CRYPTO_CLOSED_20261120.md).
- Lab RSA-VERIFY: [`SAS_PAD_RSA_VERIFY_LAB_20261120.md`](SAS_PAD_RSA_VERIFY_LAB_20261120.md) — **8/8 VALID**.
- Pad u32 APP_AUTH = **`0x02000000`** (`MD5(02 00 00 00)`), **not** X509 serial `0x0AA9` — 2³² brute unique hit.
- PKCS#1 v1.5 + DigestInfo-MD5; Signer ↔ Wire-Cert = **FACT**.
- Lab HU: `sas_login` → `rhmi_*` = **FACT**.
- Dual gate: (A) crypto + Cert↔Sig **CLOSED** · (B) **F20** acceptance still **OPEN**.
- MyBMW as required protocol oracle: **REJECTED**; as sign carrier until standalone: still relevant.
- VIN→key: **REJECTED** as next step. No further libaudio formula dig.

## UNKNOWN

- Ob **F20** nach autorisiertem Cert denselben Resource-/AM-Pfad wie Lab nimmt (= Gate B).
- F20 Action-/Model-IDs / Handles.
- Ob Diagnose `NO_HCI_RX` vs `NO_ETCH_RX` mit heutiger Instrumentierung unterscheidbar (ohne neue Messpunkte → bei Impl `UNKNOWN`).
- PKCS#12 unwrap passphrase (intentionally **not** pursued).
- Standalone-Signer ohne Key-Extraktion (nach Gate B).

## Verworfene Annahmen (durch Audit + Field)

| Alte Annahme | Status |
|--------------|--------|
| `rhmi_state=SAS_AUTHENTICATED` ⇒ Wire-Auth OK | **REJECTED** (Field + Source `:1482-1485`) |
| Lab Soak/Seq ⇒ F20 Auto-ready | **REJECTED** (Audit PR #37 + Field) |
| `AM_REGISTERED` / `RUNTIME_ACTIVE` = Wire-ACK | **REJECTED** als Wire-Claim (TX-Queue States) |
| `WATCHDOG_MISS_NO_ETCH_REPLY` = eindeutige Ursache | **WEAK** — Sammelklasse, Split noch MISSING |
| checkResource=true ⇒ Upload fehlt = Fehler | **REJECTED** (seit Resource-Audit) |
| Signer = Binder / TEE / `/data/Asset` (modern MyBMW SAS) | **REJECTED** (CASE A / PR #44) |
| Nächster Schritt = PKCS#12-Key-Extraktion | **REJECTED** |
| APP_AUTH pad = X509 serial (`0x0AA9`) | **REJECTED** (Wire 2026-11-20) |
| MyBMW nötig für SAS-Protokollmathematik | **REJECTED** (Formel Wire-FACT) |
| VIN → Key | **REJECTED** als nächster Schritt |

## P1 Status

- `classify_result` + `AuthState` live; Field-Reject → `CERTIFICATE_REJECTED` (nie Schein-`SAS_AUTHENTICATED`).
- Lab RUNTIME_ACTIVE / menu / W0 / PiDrive host tests grün.
- `menu_upload` Dead-Gate entfernt.
- Siehe [`STATE_MACHINE_P1_AUTH_20261118.md`](STATE_MACHINE_P1_AUTH_20261118.md).

Keine F20-Feldbehauptung aus Lab-Verhalten.
