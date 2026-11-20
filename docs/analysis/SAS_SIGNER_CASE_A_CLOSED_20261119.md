# SAS Signer — CASE A closed (2026-11-19)

```yaml
status: CLOSED for architecture forensics (client sign path)
claim_level: FACT where marked; see claim hygiene below
source: technology-audit libaudio-signchallenge-pipeline-2026-11-19 (CASE A)
  README: https://github.com/MPunktBPunkt/technology-audit/blob/main/audits/libaudio-signchallenge-pipeline-2026-11-19/README.md
  FUNCTION-NOTES: …/FUNCTION-NOTES.md
lib_sha256: 7bd16da13dc2662e505955425b16ce1facd78dbd81749356c3895d3f2b61ca90
updates: GATE_APP_AUTH · FIELD_DAY · DEEP_FORENSIC_ETCH_SAS §6.2 · cursor rule
```

## Verdict

> Client-side SAS signing is a **local OEM-app native component** (CASE A), not Keystore/TEE, Binder IPC, or `/data/Asset` on this path.  
> **Field blocker remains HU acceptance** of the cert/sign constellation — mechanism ≠ acceptance.

```text
SecurityModule.signChallenge()
        ↓
AudioModule.g()                 @ 0xbda2c
        ↓
native_sign_impl                @ 0xbd73c
        ↓
EVP_PKEY_sign()                 (static OpenSSL in libaudio.so)
        ↓
512-byte RSA signature
```

## Crypto pipeline (FACT — verified against audit §B)

```text
challenge[16]                         FACT — other lengths rejected
      ↓
pad16  = MD5(cert_serial_u32)         FACT — serial hashed to 16 B; NOT raw serial in XOR
      ↓
xored  = challenge[16] XOR pad16      FACT — NEON 16-byte eor
      ↓
digest = MD5(xored)                   FACT — EVP_md5, DigestUpdate(len=0x10)
      ↓
sig    = RSA EVP_PKEY_sign(digest)    FACT — RSA-4096 → typically 512 B
```

**Claim hygiene:** Do **not** write “XOR with cert_serial”. The serial enters only as **MD5(serial_u32) → pad**. Wrong pad reconstruction breaks later wire↔APK correlation.

## Key / signer source (claim hygiene)

| Claim | Status |
|-------|--------|
| Embedded PKCS#12 in `libaudio.so` @ `0x5249e`, len `0x10f2` (4338 B) | **FACT / CONFIRMED** (OID inventory) |
| OID `pkcs8ShroudedKeyBag` ×1; `pkcs7-encryptedData`; `pbeWithSHAAnd3-KeyTripleDES-CBC` ×2 | **FACT** |
| Sign path stays in-process (no `open`/`AAsset`/`socket` on depth≤3) | **FACT** |
| Android Keystore / TEE / KeyMint | **REJECTED** (`NOT_FOUND`) |
| External Binder/IPC signer | **REJECTED** for signChallenge path |
| `/data/Asset` / file load on sign path | **REJECTED** |
| PKEY lookup name `"com.bmwgroup.connected.bmw"` | **FACT** (lookup + name) |
| That alias **maps to** the embedded PKCS#12 identity | **INFERENCE** (audit §G: optional observe-only; not dynamically proven) |
| PKCS#12 unlock passphrase | **UNKNOWN** — **STOP** (no unwrap) |
| Key extraction as next research | **REJECTED** |

```text
MyBMW APK
 └── libaudio.so
      ├── embedded PKCS#12 (DER)     FACT present
      │     └── pkcs8ShroudedKeyBag  FACT OID
      └── OpenSSL → EVP_PKEY_sign    FACT
```

Init loads blob via `AudioModule_a` → parse `@0xca93c` (FACT presence). Unwrap into live `EVP_PKEY` is in-process PBE; passphrase details intentionally not pursued.

## What is PKCS#12 here (architecture note)

PKCS#12 (`.p12`/`.pfx`, RFC 7292) is an **encrypted container** for private key + certs — **not** a wire protocol. In this SO:

```text
PKCS#12 (DER)
 └── pkcs7-encryptedData
      └── pbeWithSHAAnd3-KeyTripleDES-CBC   ← passphrase KDF
           └── AuthenticatedSafes
                └── pkcs8ShroudedKeyBag     ← PKCS#8 private key, shrouded
                (+ certificate bags)
```

Load sketch: passphrase → PBE → decrypt → unwrap PKCS#8 → `EVP_PKEY`.  
`sas_login` itself is **outside** the container; it only carries the **signature bytes** from `signChallenge()`.  
3DES-PBE is weak; audit still **STOP**s unwrap — architecture value exhausted; further work = key material.

## APP_AUTH / certificate binding

| Observation | Class |
|-------------|-------|
| Sign uses X509 at `context+0x18` serial for XOR **pad** | **FACT** |
| Fallback embed cert has `SAS.CertificateType=APP` attrs | **FACT** |
| Literal `APP_AUTH` / `sas_certificate` in `libaudio.so` | **NOT_FOUND** |
| Java CertMangling / merge for wire `sas_certificate` | prior audit — **not re-proven** by PR #44 |

**APP_AUTH epistemic status:** **Partial CONFIRMED** (serial→pad→sign linkage). Not “APP_AUTH fully reconstructed.”

## Dual gate (do not collapse)

```text
A) Client can produce sas_login signature   → mechanism FACT (CASE A)
B) F20 HU accepts cert + signature context → OPEN (Field)
```

“SAS is not an unknown protocol problem” applies to **(A) client sign path only**.  
Overall Field blocker stays **(B)** — HU validates against the certs it received in `sas_certificate` (`context+0x18` / merge chain). Lab stub `AUTHENTICATED` ≠ Field.

### VIN-derived key?

| Claim | Status |
|-------|--------|
| Embedded RSA key in `libaudio.so` PKCS#12 | **FACT** |
| `private_key = f(VIN)` | **HYPOTHESIS / not evidenced** |
| VIN / account / vehicle profile selects which cert/key | **UNKNOWN** (not shown; do not investigate first) |

PR #44 shows **embedded software key**, not a VIN-KDF architecture. Next work is **cert↔key identity / wire pad check**, not VIN→key.

### A ↔ B identity (largest open link)

```text
embedded PKCS#12 (A)  ↔  wire sas_certificate / APP_AUTH context (B)
```

PKEY lookup name = **FACT**; alias maps to embedded PKCS#12 identity = **INFERENCE**.  
Only when A and B match does: cert → serial → pad → sign(matching key) → HU accept become a closed story.

### Field decode variables (next car / B3 run)

Separate cleanly:

1. **Certificate chain** (CNs, `SAS.Digests`, **serial** of effective signing cert)
2. **Signature correctness** (pad = MD5(serial_u32); XOR; MD5; RSA-4096) — Test A needs no private key
3. **Session structure** (BCL/Etch/mids) — already strong

Hard decode anchor: capture **effective cert serial** + challenge + `sas_login` from a real AAIdrive/MyBMW session, run `tools/sas_pad_crosscheck.py` — strongest APK↔wire bridge without key extraction.

## Logging coverage (bt-analyzer sources)

| Datum | Before 2026-11-20 | After (this update) |
|-------|-------------------|---------------------|
| Etch method + mid correlation (B3) | yes | yes |
| Raw bins both dirs (B3) | yes | yes |
| PKCS7 CNs / cert_types | HU `inspect_pkcs7` CNs only | + **serials / serial_u32 / pad16** |
| Challenge 16 B hex | often only in raw / memory | **jsonl** (`challenge_hex`) on B3 + f20_sim |
| Login sig 512 B | `sig_len` only | **sha256 + hex** (≤640 B) |
| Structured Test A input | **GAP** | `sas` object on B3 etch; HU `sas_challenge_tx` enriched |

Offline helper: `tools/sas_pad_crosscheck.py --from-jsonl b3.jsonl`  
Helpers: `etch_codec.sas_pad16_from_serial_u32`, `summarize_sas_wire_fields`, `extract_pkcs7_cert_serials`.

**Still not logged as FACT:** dynamic proof that PKEY alias == embedded PKCS#12 identity (observe-only optional; no dump).

## Closed architecture chain (client)

```text
Bluetooth SPP → BCL → Etch OPEN → sas_certificate
  → 16-byte challenge
  → signChallenge → libaudio (MD5(serial) XOR → MD5 → EVP_PKEY_sign)
  → 512-byte signature → sas_login
```

## What we must no longer investigate

1. Binder / CarSecurityService as modern MyBMW default signer for this path.
2. TEE / Android Keystore as required for this path.
3. `/data/Asset` as live private-key source for `signChallenge`.
4. PKCS#12 passphrase unwrap / private-key export.

Optional only (audit §G): observe-only confirm which PKEY alias binds after init — **no dump**.

## Measures (Do / Don't)

### Do

1. Treat client SAS signing as **CASE A OEM native block**; Field work = **HU acceptance**.
2. Arm B = **live** MyBMW `SecurityModule` on phone — no key on Pi (MyBMW optional for protocol *math*, still needed for Field *accept* until matching cert+sign exists).
3. Next capture: real session → serial + challenge + login → `tools/sas_pad_crosscheck.py` (Test A). Prefer B3 for Phone↔F20.
4. Keep `--stop-on-authenticated` + snapshot; one variable = credential constellation.
5. Keep APP_AUTH wording **Partial CONFIRMED**; pad = **MD5(serial_u32)**.
6. Distinguish FACT vs INFERENCE for PKEY-alias↔PKCS#12 mapping.
7. After pad matches: compare **public** cert identity (wire vs PKCS#12 inventory) — still no private-key export.

### Don't

1. Write “XOR with cert_serial” (omit MD5 pad step).
2. Mark “PKEY alias = embedded PKCS#12 identity” as FACT.
3. Unwrap PKCS#12 / recover passphrase / ship private keys.
4. Resume Binder/TEE/Asset hunts for this signature path.
5. Pursue **VIN→key** without a concrete native dataflow hit (currently unevidenced).
6. Claim Field `AUTHENTICATED` from Lab stub or from CASE A alone.

## Related docs

- [`GATE_APP_AUTH_ACCEPTANCE_20261118.md`](GATE_APP_AUTH_ACCEPTANCE_20261118.md)
- [`FIELD_DAY_ONE_VARIABLE_GATE.md`](FIELD_DAY_ONE_VARIABLE_GATE.md)
- [`GATE_E2E_COMPARISON.md`](GATE_E2E_COMPARISON.md)
- [`DEEP_FORENSIC_ETCH_SAS_20261116.md`](DEEP_FORENSIC_ETCH_SAS_20261116.md) §6.2
- [`STATE_MACHINE_CHANGELOG_20261118.md`](STATE_MACHINE_CHANGELOG_20261118.md)
- Lab B3 full-auth freeze: `docs/evidence/LAB_B3_TCP_FULLAUTH_20261119T091257Z/`
