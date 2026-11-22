# SAS Status — Crypto closed, Gate B CLOSED (Field 2026-11-21)

```yaml
status: Crypto + A↔B Wire = FACT; F20 Gate B = CLOSED (FIELD)
claim_level: FACT where marked
lab_evidence: SAS_PAD_RSA_VERIFY_LAB_20261120.md
field_gate_b: docs/evidence/FIELD_B3_GATEB_20261121T112446Z/EVAL.md
signer_arch: SAS_SIGNER_CASE_A_CLOSED_20261119.md
next: RHMI Music object graph (Handle 23) → PiDrive Music/RHMI; standalone signer later
field_rsa_verify: CLOSED 18/18 (2026-11-22 RAW_FORENSIC)
```

## Verdict

> Kryptoprotokoll und Signer↔Wire-Cert sind **geschlossen**.  
> **Gate B (F20-HU-Akzeptanz) ist FIELD-geschlossen** — B3 Profile-Relay, live AAIdrive/MyBMW, Challenge+Login OK, danach RHMI/Media (Spotify / Halestorm).  
> MyBMW bleibt **Signierträger** bis ein Standalone-Signer existiert; für Protokollmathematik nicht nötig.

## FACT-Tabelle

| Bereich | Status | Aussage |
|---------|--------|---------|
| BCL → Etch → SAS | **FACT** | Transport-/Protokollpfad verstanden |
| `sas_certificate` | **FACT** | Wire-Zertifikat liegt vor |
| Challenge | **FACT** | 16 Byte bekannt |
| Pad-Input | **FACT** | `0x02000000`, **nicht** X509-Serial |
| Pad | **FACT** | `MD5(02 00 00 00)` |
| Challenge-Verarbeitung | **FACT** | `challenge XOR pad → MD5` |
| RSA | **FACT** | RSA-4096, PKCS#1 v1.5, DigestInfo-MD5 |
| Signer ↔ Wire-Cert | **FACT** | Lab 8/8 + **Field B3 18/18** RSA-VERIFY (`SAS_CRYPTO_VERIFY.json`) |
| Reproduzierbarkeit | **FACT** | 2³²-Bruteforce findet eindeutig `0x02000000` |
| Lab-HU-Akzeptanz | **FACT** | danach `rhmi_*` |
| Echter F20-HU-Akzeptanztest | **FACT** | Field B3 2026-11-21 — `AUTHENTICATED` + RHMI/Media |
| VIN → Key | **REJECTED** | unevidenced; nicht nächster Schritt |
| MyBMW als notwendige Protokollinstanz | **REJECTED** | Formel öffentlich nachrechenbar |
| MyBMW als Träger der Signierfähigkeit | **OPEN** | Standalone-Signer ohne Extraktion noch nicht gebaut |

## Geschlossene Kette (Wire)

```text
Wire Certificate
      │
      ├── public key ──────┐
      │                    │
      │              RSA VERIFY = VALID
      │                    │
      └── CertificateType   │
             0x02000000   │
                    ↓      │
             MD5(02 00 00 00)
                    ↓      │
Challenge ── XOR ──────────┘
                    ↓
                  MD5
                    ↓
          RSA-4096 PKCS#1 v1.5
                    ↓
             512-B Signature → sas_login
```

Lab: `sas_login` → `rhmi_*` (akzeptiert).  
F20: `sas_login` → AM/RHMI/CDS/AV (Gate B FIELD CLOSED 2026-11-21).

## Dual Gate (nicht kollabieren)

```text
Gate A — Signatur / Cert-Zuordnung     🟢 CLOSED (Wire FACT)
Gate B — F20 HU akzeptiert Cert+Sig    🟢 CLOSED (FIELD B3 2026-11-21)
```

Lab-HU ≠ F20-HU — aber Field-Lauf liegt vor (`FIELD_B3_GATEB_20261121T112446Z`).

## MyBMW — saubere Trennung

| Frage | Antwort |
|-------|---------|
| Brauchen wir MyBMW, um die SAS-**Mathematik** zu verstehen? | **Nein** — Formel + PKCS#1 + A↔B Wire-FACT |
| Brauchen wir MyBMW (oder gleichwertige Signierfähigkeit), um am F20 einzuloggen? | **Als Signierträger ja**, bis Standalone existiert (Gate B Accept = FACT) |
| Private-Key-Extraktion als nächster Schritt? | **REJECTED / STOP** |
| PKCS#12 in `libaudio.so` vorhanden? | **FACT** (OID); Alias↔Blob = **INFERENCE** |
| Feature-PKI PFX @`0x5249e` (RSA-1536) vs APP_AUTH RSA-4096? | **getrennt** — Feature CLOSED; PFX≠APP_AUTH **REJECTED** overclaim; APP_AUTH native PKEY/`createSecurityContext` **OPEN** — [`PKCS12-ANATOMY`](https://github.com/MPunktBPunkt/technology-audit/blob/main/audits/libaudio-signchallenge-pipeline-2026-11-19/PKCS12-ANATOMY.md) rev. 2026-11-22e |

## Einstufung

| Thema | Ampel |
|-------|-------|
| Kryptoprotokoll | 🟢 praktisch vollständig rekonstruiert |
| Signer ↔ Zertifikat (Wire) | 🟢 Wire-FACT |
| Lab-HU | 🟢 funktioniert |
| F20-HU | 🟢 Gate B FIELD CLOSED |
| MyBMW als Protokollinstanz | 🔴 widerlegt |
| MyBMW als Signierträger | 🟡 weiterhin relevant (bis Standalone) |
| VIN→Key | 🔴 nicht nötig / nicht belegt |

## Lab-Prep (2026-11-20) — READY

| Check | Status |
|-------|--------|
| AuthState / golden / A/B unit tests | **PASS** |
| `lab_auth_ab_matrix` 4/4 | **PASS** |
| B3 tcp-lab `AUTHENTICATED` freeze | **PASS** — [`LAB_B3_TCP_FULLAUTH_20261120T090004Z`](../evidence/LAB_B3_TCP_FULLAUTH_20261120T090004Z/) |
| Comparable to 2026-11-19 FULLAUTH | **yes** (identical etch/BCL counts) |
| Logger challenge + login_sig | **PASS** (B3 + HU) |
| Stub RSA-VERIFY | N/A (LABSIM cert) — MyBMW 8/8 remains FACT |

Kein weiterer technology-audit vor dem F20-B3-Lauf.

## Nächster Schritt (nach Gate B)

Gate B erledigt — siehe [`FIELD_B3_GATEB_20261121T112446Z/EVAL.md`](../evidence/FIELD_B3_GATEB_20261121T112446Z/EVAL.md) + [`ADDENDUM_RHMI_AM_20261121.md`](../evidence/FIELD_B3_GATEB_20261121T112446Z/ADDENDUM_RHMI_AM_20261121.md).

Arbeitsfokus: [`FIELD_GATE_B_CLOSED_NEXT_RHMI_TEMPLATE_20261121.md`](FIELD_GATE_B_CLOSED_NEXT_RHMI_TEMPLATE_20261121.md)

1. Bluetooth Control Plane **CLOSED** — [`BT_CONTROL_PLANE_CLOSED_20261121.md`](BT_CONTROL_PLANE_CLOSED_20261121.md)  
2. Lab stub frozen — [`MUSIC_NP_SPINE_LAB_STUB_20261121.md`](MUSIC_NP_SPINE_LAB_STUB_20261121.md) (IDs 444·445·446/447·660·661·336·248)  
3. Lab proof → **ein** F20-Feldversuch (Suffizienz fremder RHMI-Client) → dann PiDrive-Implementierung  
4. Optional: RSA-VERIFY Field-Raw; Standalone-Signer später (nicht blocker)  
5. Optional observe-only: PLT `PKCS12_parse` password regs (Alias↔Blob / Passwort-Ursprung) — siehe PKCS12-ANATOMY; **kein** Key-Dump / kein PW-Brute  
6. Kein BT-Stack-/libaudio-Forensik als Blocker für RHMI/PiDrive; kein allgemeiner Technology-Audit

Tool für Field-SPP: `tools/b3_profile_relay.py` (SDP „BMW Connected“ ch6 + transparent relay).

## Related

- [`SAS_PAD_RSA_VERIFY_LAB_20261120.md`](SAS_PAD_RSA_VERIFY_LAB_20261120.md) — 8/8 Zahlen
- [`SAS_SIGNER_CASE_A_CLOSED_20261119.md`](SAS_SIGNER_CASE_A_CLOSED_20261119.md) — native Architektur
- [`GATE_APP_AUTH_ACCEPTANCE_20261118.md`](GATE_APP_AUTH_ACCEPTANCE_20261118.md) — Field gate
- [`FIELD_DAY_ONE_VARIABLE_GATE.md`](FIELD_DAY_ONE_VARIABLE_GATE.md) — Operator-Runbook
