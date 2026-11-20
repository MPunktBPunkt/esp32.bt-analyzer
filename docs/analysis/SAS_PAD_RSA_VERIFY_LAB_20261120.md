# SAS Pad + RSA-VERIFY — Lab Wire FACT (2026-11-20)

```yaml
status: Wire-validated against lab MyBMW→f20_sim capture
claim_level: FACT where marked
source_capture: /tmp/hu_pre_browse.jsonl (lab OnePlus / MyBMW, BCL reassembled)
tool: tools/sas_pad_crosscheck.py --from-bcl-jsonl
canonical_status: SAS_STATUS_CRYPTO_CLOSED_20261120.md
```

## Verdict

> Aus einer echten MyBMW-Session (Lab) sind **Pad-Formel**, **PKCS#1-Modus** und **A↔B (Cert↔Signatur)** ohne Private Key geschlossen.  
> Der Pad-Input ist **`0x02000000`** (APP_AUTH / `MD5(02 00 00 00)`), **nicht** die X509-Serial `0x0AA9` des TouchCommand-Blatts.  
> 2³²-Bruteforce bestätigt denselben eindeutigen u32-Treffer.

## Rechnung (öffentlich)

```text
sas_certificate → PKCS7 → X509 (APP_AUTH leaf)
challenge[16]  +  login_sig[512]
        ↓
pad    = MD5(0x02000000_be)     # = MD5(02 00 00 00)
xored  = challenge XOR pad
digest = MD5(xored)
        ↓
RSA_VERIFY(sig, DigestInfo-MD5 || digest, leaf.public_key)
```

## Ergebnis — 8/8 Sessions VALID

| Feld | Wert |
|------|------|
| Signer CN | `a4a_app_BMWTouchCommand_Connection_00.00.10` |
| Signer X509 serial | `0x0AA9` (2729) — **nicht** Pad-Input |
| Pad u32 | `0x02000000` |
| Pad16 | `f2dd0dedb2c260419ece4a9e03b2e828` |
| Challenge (alle 8) | `fc20723f7b6760d4ea97d4b2f4ad71ee` |
| Digest | `06fae79665b94ec3ccf5fa3fabd0e85e` |
| PKCS#1 | v1.5 + DigestInfo-MD5 |
| RSA-VERIFY | **VALID** (8/8: src 10–13, 16–19) |
| 2³² Brute | **FOUND** `0x02000000` only |
| Kontrast `pad=MD5(0xAA9)` | Digest `cfcdd722…` ≠ recovered → **REJECTED** |

## A↔B

```text
Wire APP_AUTH leaf public key
        ↕ RSA-VERIFY VALID
login_sig[512]
```

→ **FACT:** Das gesendete TouchCommand-Zertifikat ist der Public-Counterpart des Keys, der die Wire-Signatur erzeugt hat.

PKCS#12 ↔ dasselbe Blatt bleibt **INFERENCE** (observe-only Cert-Bags; kein Unwrap).

## Gate B (HU-Trust)

| Ebene | Status |
|-------|--------|
| Lab `f20_sim` | **FACT** — `_result_sas_login` ohne Exception + `rhmi_*` |
| Echter F20 | **OPEN** — ein B3-Feldlauf mit demselben Paar |

Siehe [`SAS_STATUS_CRYPTO_CLOSED_20261120.md`](SAS_STATUS_CRYPTO_CLOSED_20261120.md).

## Korrektur gegenüber CASE-A-Serial-Annahme

Disassembly: „MD5(cert_serial_u32)“.  
Wire: für APP_AUTH-Pfad ist der effektive u32-Wert **`CertificateType`-artig `0x02000000`**, konsistent mit DEEP_FORENSIC §6.2 (`challenge XOR MD5(02 00 00 00)`).

`summarize_sas_wire_fields` setzt deshalb `effective_serial_u32 = 0x02000000` wenn APP_AUTH/XOR aktiv; X509-Serial bleibt unter `signer_serial_*`.

## Reproduktion

```bash
PYTHONPATH=tools python3 tools/sas_pad_crosscheck.py \
  --from-bcl-jsonl /tmp/hu_pre_browse.jsonl
```
