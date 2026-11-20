# SAS Status — Crypto closed, Gate B open (2026-11-20)

```yaml
status: Crypto + A↔B Wire = FACT; F20 Gate B = OPEN
claim_level: FACT where marked
lab_evidence: SAS_PAD_RSA_VERIFY_LAB_20261120.md
signer_arch: SAS_SIGNER_CASE_A_CLOSED_20261119.md
next: one F20 B3 run → AUTHENTICATED / rhmi_* ?
```

## Verdict

> Kryptoprotokoll und Signer↔Wire-Cert sind **geschlossen**.  
> „Standalone funktioniert am echten F20 ohne MyBMW“ ist **noch nicht** bewiesen — dafür fehlt genau **Gate B (F20-HU-Akzeptanz)**.  
> MyBMW ist für die **Protokollmathematik** nicht mehr nötig; als **Träger der Signierfähigkeit** vorerst weiter relevant.

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
| Signer ↔ Wire-Cert | **FACT** | 8/8 RSA-VERIFY gegen Public Key des Wire-Certs |
| Reproduzierbarkeit | **FACT** | 2³²-Bruteforce findet eindeutig `0x02000000` |
| Lab-HU-Akzeptanz | **FACT** | danach `rhmi_*` |
| Echter F20-HU-Akzeptanztest | **OPEN** | noch nicht mit diesem Stand bewiesen |
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
F20: derselbe Nachweis fehlt.

## Dual Gate (nicht kollabieren)

```text
Gate A — Signatur / Cert-Zuordnung     🟢 CLOSED (Wire FACT)
Gate B — F20 HU akzeptiert Cert+Sig    🟡 OPEN (ein Feldlauf)
```

Lab-HU ≠ F20-HU. Kein `AUTHENTICATED` aus Lab ableiten.

## MyBMW — saubere Trennung

| Frage | Antwort |
|-------|---------|
| Brauchen wir MyBMW, um die SAS-**Mathematik** zu verstehen? | **Nein** — Formel + PKCS#1 + A↔B Wire-FACT |
| Brauchen wir MyBMW (oder gleichwertige Signierfähigkeit), um am F20 einzuloggen? | **Noch ja / unbekannt** — bis Gate B + Standalone-Signer geklärt |
| Private-Key-Extraktion als nächster Schritt? | **REJECTED / STOP** |
| PKCS#12 in `libaudio.so` vorhanden? | **FACT** (OID); Alias↔Blob = **INFERENCE** |

## Einstufung

| Thema | Ampel |
|-------|-------|
| Kryptoprotokoll | 🟢 praktisch vollständig rekonstruiert |
| Signer ↔ Zertifikat (Wire) | 🟢 Wire-FACT |
| Lab-HU | 🟢 funktioniert |
| F20-HU | 🟡 genau ein Feldbeweis fehlt |
| MyBMW als Protokollinstanz | 🔴 widerlegt |
| MyBMW als Signierträger | 🟡 weiterhin relevant |
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

## Nächster Test (klein, höchster Informationsgewinn)

**Nicht** weiter in `libaudio.so` forensiken.

Ein echter F20-B3-Lauf:

```text
Phone (MyBMW / authorized APP_AUTH) ↔ B3 ↔ F20
  sas_certificate → challenge → pad 0x02000000 → sas_login
  → AUTHENTICATED / rhmi_* ?     ← Gate B
```

Capture: Cert + `challenge_hex` + `login_sig` + HU-Ergebnis.  
Offline: `tools/sas_pad_crosscheck.py --from-bcl-jsonl …`

Wenn F20 akzeptiert → Gate A+B geschlossen; Restaufgabe = Standalone-Signierseite **ohne** Key-Extraktion.

## Related

- [`SAS_PAD_RSA_VERIFY_LAB_20261120.md`](SAS_PAD_RSA_VERIFY_LAB_20261120.md) — 8/8 Zahlen
- [`SAS_SIGNER_CASE_A_CLOSED_20261119.md`](SAS_SIGNER_CASE_A_CLOSED_20261119.md) — native Architektur
- [`GATE_APP_AUTH_ACCEPTANCE_20261118.md`](GATE_APP_AUTH_ACCEPTANCE_20261118.md) — Field gate
- [`FIELD_DAY_ONE_VARIABLE_GATE.md`](FIELD_DAY_ONE_VARIABLE_GATE.md) — Operator-Runbook
