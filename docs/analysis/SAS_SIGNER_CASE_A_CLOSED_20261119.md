# SAS Signer — CASE A closed (2026-11-19)

```yaml
status: CLOSED for architecture forensics (client sign path)
claim_level: FACT where marked; see claim hygiene below
source: technology-audit libaudio-signchallenge-pipeline-2026-11-19 (CASE A)
  README: https://github.com/MPunktBPunkt/technology-audit/blob/main/audits/libaudio-signchallenge-pipeline-2026-11-19/README.md
  FUNCTION-NOTES: …/FUNCTION-NOTES.md
lib_sha256: 7bd16da13dc2662e505955425b16ce1facd78dbd81749356c3895d3f2b61ca90
updates: GATE_APP_AUTH · FIELD_DAY · DEEP_FORENSIC_ETCH_SAS §6.2 · cursor rule
wire_validation: SAS_PAD_RSA_VERIFY_LAB_20261120.md (8/8) · SAS_STATUS_CRYPTO_CLOSED_20261120.md
```

## Verdict

> Client-side SAS signing is a **local OEM-app native component** (CASE A), not Keystore/TEE, Binder IPC, or `/data/Asset` on this path.  
> **Wire validation (2026-11-20):** Pad-Formel + PKCS#1 + Signer↔Wire-Cert = **FACT** (8/8 RSA-VERIFY).  
> **Field blocker remains F20 HU acceptance** (Gate B) — mechanism ≠ acceptance; Lab ≠ Field.

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

## Crypto pipeline (FACT — audit §B + Wire 2026-11-20)

```text
challenge[16]                         FACT — other lengths rejected
      ↓
pad16  = MD5(u32_be)                  FACT — value hashed to 16 B; NOT raw XOR
      ↓
xored  = challenge[16] XOR pad16      FACT — NEON 16-byte eor
      ↓
digest = MD5(xored)                   FACT — EVP_md5, DigestUpdate(len=0x10)
      ↓
sig    = RSA EVP_PKEY_sign(digest)    FACT — RSA-4096, PKCS#1 v1.5, DigestInfo-MD5 → 512 B
```

**Wire FACT (lab 2026-11-20):** For APP_AUTH sessions the pad u32 is **`0x02000000`**
(`MD5(02 00 00 00)`), **not** the TouchCommand X509 serial `0x0AA9`.  
RSA-VERIFY against the wire leaf public key: **8/8 VALID**; 2³² brute unique hit `0x02000000`.  
See [`SAS_PAD_RSA_VERIFY_LAB_20261120.md`](SAS_PAD_RSA_VERIFY_LAB_20261120.md) ·
[`SAS_STATUS_CRYPTO_CLOSED_20261120.md`](SAS_STATUS_CRYPTO_CLOSED_20261120.md).

**Claim hygiene:** Do **not** write “XOR with cert_serial”. The pad input is
**MD5(u32) → pad**; on the APP_AUTH path that u32 is the CertificateType-shaped
constant `0x02000000`, not the X509 serial.

## Key / signer source (claim hygiene)

| Claim | Status |
|-------|--------|
| Embedded PKCS#12 in `libaudio.so` @ `0x5249e`, len `0x10f2` (4338 B) | **FACT / CONFIRMED** (OID inventory) |
| Local PFX pass + `PKCS12_parse` + RSA-4096 e=3 | **FACT** — [PKCS12-ANATOMY](https://github.com/MPunktBPunkt/technology-audit/blob/main/audits/libaudio-signchallenge-pipeline-2026-11-19/PKCS12-ANATOMY.md) |
| Alias → loader `0xbdf84`; `EVP_PKEY*` → x3 of `0x12e564` | **FACT** (rev. 2026-11-22c) |
| Innermost RSA/`EVP_PKEY_sign` inside `0x12e564` | **NEXT** (VERY STRONG that this is the APP_AUTH key) |
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

**MyBMW role (post Wire FACT):** not required for protocol *math*; still the practical *sign carrier* until a clean standalone signer exists (no key extract).

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
3DES-PBE is weak; audit still **STOP**s unwrap — architecture value exhausted; further work ≠ key material.

## APP_AUTH / certificate binding

| Observation | Class |
|-------------|-------|
| APP_AUTH wire pad u32 = `0x02000000` | **FACT** (RSA-VERIFY + 2³²) |
| Sign path uses context X509; Wire leaf = TouchCommand APP_AUTH | **FACT** (CN + RSA-VERIFY) |
| Fallback embed cert has `SAS.CertificateType=APP` attrs | **FACT** |
| Literal `APP_AUTH` / `sas_certificate` in `libaudio.so` | **NOT_FOUND** |
| Java CertMangling / merge for wire `sas_certificate` | prior audit — **not re-proven** by PR #44 |

**APP_AUTH epistemic status:** Wire pad + Signer↔Cert = **FACT**. Literal native string still **NOT_FOUND**.

## Dual gate (do not collapse)

```text
A) Client formula + Cert↔Sig (Wire)     → CLOSED FACT (2026-11-20)
B) F20 HU accepts cert + signature      → OPEN (Field)
```

Lab stub / lab MyBMW `rhmi_*` ≠ Field `AUTHENTICATED`.

### VIN-derived key?

| Claim | Status |
|-------|--------|
| Embedded RSA key in `libaudio.so` PKCS#12 | **FACT** |
| `private_key = f(VIN)` | **HYPOTHESIS / REJECTED as next step** |
| VIN / account / vehicle profile selects which cert/key | **UNKNOWN** (not shown; do not investigate first) |

### A ↔ B identity

| Link | Status |
|------|--------|
| Wire Cert public key ↔ login_sig | **FACT** (8/8 RSA-VERIFY) |
| embedded PKCS#12 ↔ Wire Cert leaf | **INFERENCE** (observe-only Cert-Bags; no unwrap) |

### Next Field decode (Gate B)

One F20 B3 run with authorized APP_AUTH constellation:

1. `sas_certificate` + challenge + `sas_login` + HU result  
2. Offline: `tools/sas_pad_crosscheck.py --from-bcl-jsonl` (expect VALID)  
3. Gate B: `AUTHENTICATED` / subsequent `rhmi_*`?

**Not next (product blocker):** further `libaudio.so` dig, VIN→key, PKCS#12 **decrypt**/key dump.  
Optional observe-only: PLT `PKCS12_parse` password regs — [PKCS12-ANATOMY](https://github.com/MPunktBPunkt/technology-audit/blob/main/audits/libaudio-signchallenge-pipeline-2026-11-19/PKCS12-ANATOMY.md).

## Logging coverage (bt-analyzer sources)

| Datum | Before 2026-11-20 | After |
|-------|-------------------|-------|
| Etch method + mid correlation (B3) | yes | yes |
| PKCS7 CNs / cert_types / serials | partial | + **signer_serial_*** + **effective_serial_u32=0x02000000** (APP_AUTH) |
| Challenge / login_sig | often raw only | **jsonl** hex + sha256 |
| RSA-VERIFY offline | **GAP** | `sas_pad_crosscheck.py --from-bcl-jsonl` |

Helpers: `etch_codec.sas_pad16_from_serial_u32`, `SAS_APP_AUTH_PAD_U32`, `summarize_sas_wire_fields`.

## Closed architecture chain (client + Wire)

```text
Bluetooth SPP → BCL → Etch OPEN → sas_certificate
  → 16-byte challenge
  → pad = MD5(0x02000000) → XOR → MD5 → EVP_PKEY_sign
  → 512-byte signature → sas_login
  → [Lab] rhmi_*     [F20] ???
```

## What we must no longer investigate

1. Binder / CarSecurityService as modern MyBMW default signer for this path.
2. TEE / Android Keystore as required for this path.
3. `/data/Asset` as live private-key source for `signChallenge`.
4. PKCS#12 passphrase unwrap / private-key export.
5. Pad u32 = X509 serial on APP_AUTH path (wire-**REJECTED**).
6. Further native dig of `libaudio.so` for crypto formula (Wire-closed).

Optional only (audit §G): observe-only confirm which PKEY alias binds after init — **no dump**.

## Measures (Do / Don't)

### Do

1. Treat crypto + Wire A↔B as **closed**; Field work = **F20 HU acceptance** (Gate B).
2. Arm B = **live** MyBMW `SecurityModule` on phone until standalone signer — no key on Pi.
3. Next capture: F20 B3 → Cert + challenge + login → `sas_pad_crosscheck.py` + AuthState.
4. Keep `--stop-on-authenticated` + snapshot; one variable = credential constellation.
5. Distinguish FACT (Wire Cert↔Sig) vs INFERENCE (PKCS#12↔Wire leaf).
6. After Gate B: evaluate standalone sign *without* key extraction.

### Don't

1. Write “XOR with cert_serial” / treat `0x0AA9` as APP_AUTH pad.
2. Mark “PKEY alias = embedded PKCS#12 identity” as FACT.
3. Unwrap PKCS#12 / recover passphrase / ship private keys.
4. Resume Binder/TEE/Asset / libaudio formula hunts.
5. Pursue **VIN→key**.
6. Claim Field `AUTHENTICATED` from Lab stub or crypto alone.

## Related docs

- [`SAS_STATUS_CRYPTO_CLOSED_20261120.md`](SAS_STATUS_CRYPTO_CLOSED_20261120.md) — **canonical status**
- [`SAS_PAD_RSA_VERIFY_LAB_20261120.md`](SAS_PAD_RSA_VERIFY_LAB_20261120.md)
- [`GATE_APP_AUTH_ACCEPTANCE_20261118.md`](GATE_APP_AUTH_ACCEPTANCE_20261118.md)
- [`FIELD_DAY_ONE_VARIABLE_GATE.md`](FIELD_DAY_ONE_VARIABLE_GATE.md)
- [`GATE_E2E_COMPARISON.md`](GATE_E2E_COMPARISON.md)
- [`DEEP_FORENSIC_ETCH_SAS_20261116.md`](DEEP_FORENSIC_ETCH_SAS_20261116.md) §6.2
- [`STATE_MACHINE_CHANGELOG_20261118.md`](STATE_MACHINE_CHANGELOG_20261118.md)
