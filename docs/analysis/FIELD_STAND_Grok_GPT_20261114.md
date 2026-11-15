# Feldstand — Abgleich Grok + GPT (nach `18117e9`, 2026-11-14)

Quellen: Grok-Gesamtbewertung · GPT-Gegenprüfung · `LAB_DUMMY_ETCH_*` · `FIELD_B2A_TX_CH6_*` · BclCarLink@7cfd959 · AAIdrive `CarProber.kt`@3e93419

## Urteil

BCL-Transport + HS v5 + WD-Maintenance sind **FIELD CONFIRMED**.  
Die Protokollgrenze ist jetzt: **BCL ACTIVE → OPEN 4004 / PKCS7 (App→HU) → erwartete SAS-Challenge (noch UNKNOWN am F20)**.  
UI-Grün ≠ SAS/RHMI/CDS.

## Epistemik (geschärft)

| Layer | Status |
|-------|--------|
| SCN6 / RFCOMM Client | **FIELD FACT** |
| HU BCL HANDSHAKE v5 / iid 0x0E / buf 0x4000 | **FIELD FACT** |
| WD 5001 / `13371337` / ≈2.5 s Echo (F20 + Dummy) | **FIELD FACT** (Maintenance) |
| SELECTPROTO/KNOCK nach HS v5 = SP4 + TouchCommand/7 | **LAB FACT** (MyBMW→Dummy); F20-Analyzer bisher SP2/3 |
| BCL OPEN 4004 (Analyzer→F20) + DATAACK | **FIELD FACT** |
| Etch `deadbeef` + PKCS7 App→HU | **LAB FACT** |
| Cert-Metadaten `CDS=true`/`RHMI=true`/`APPID=myBMW`/… | **LAB FACT** (OID `1.3.6.1.4.1.513.59.4.2`) |
| `sas_certificate` → Challenge → `sas_login` → `rhmi_getCapabilities` | **Desk FACT** (AAIdrive); **Feld UNKNOWN** |
| RHMI / CDS Property-JSON | Desk/Lab-App; Feld UNKNOWN |

## Desk ≠ Wire (Kern)

| | BclCarLink Desk | Wire (MyBMW/Lab) | F20 Analyzer |
|--|-----------------|------------------|--------------|
| HS | wartet auf HU | Dummy v5/1/0x8000 oder F20 v5/14/0x4000 | F20 v5 ✓ |
| SP wenn version>3 | **3** + leerer Knock A4A | **4** + UUID Knock TouchCommand/7 | bisher 2/3 getestet |
| WD | 5 s / TO 20 s | ≈**2.5 s** | ≈2.5 s Echo ✓ |

## Korrekturen an Grok/GPT

| Claim | Entscheidung |
|-------|----------------|
| M25 „drei parallele Etch-Kanäle“ | **korrigiert → sequenziell** (M37): OPEN10→DATA, OPEN11→CLOSE→OPEN11→DATA, OPEN12→DATA |
| src10/11/12 = bmw/mini/j29 | **INFERENCE only** — Wire-CNs = ApplicationManager / SmartThings / **cdsbaseapp**. CarProber-Brand-Loop ist *ähnliche* Probe-Idee, Zuordnung nicht FACT |
| cmd 0x0006 = OPEN/SP-Variante (älter Grok) | **REJECTED** — Framer: DATAACK (M19) |
| DATAACK `0x08` nach OPEN 4004 = Etch-Accept | **REJECTED** — passt zu BclCarLink `DATAACK(8+payload)` bei OPEN len=0 → **0x08** (M41) |
| DATAACK = 8+len für **jedes** BCL-Kommando | **REJECTED 2026-11-15 (M48)** — KNOCK 56 B ohne ACK56 in analyzer→F20 Holds; siehe `FIELD_VS_LAB_INSIGHTS_20261115` |
| AAIdrive grün = App-Layer OK | **REJECTED** — nur BCL/WD-Eligibility (M31/M40) |
| PKCS7 nur „irgendwelche Certs“ | **unterschätzt** — Capability-Landkarte im Cert (M39) ✓ GPT |

## Muster M29–M44 (adoptiert)

| ID | Muster | Status |
|----|--------|--------|
| **M29** | Setup vs Maintenance: HU WD-Echo erst nach Client-OPEN5001+WD-TX; Echo vor OPEN zu früh | FIELD+LAB |
| **M30** | HS Fingerprint peer-abhängig (Dummy alt v3/1/8000; F20 v5/14/4000; Dummy-v5 Lab iid1/8000) | FACT |
| **M31/M40** | UI-Grün = HS+SP/KNOCK+WD; ≠ SAS/RHMI/CDS | LAB FACT |
| **M32** | Session-Tod ohne Client-WD; SP2/SP3 beide OK mit WD | FIELD (n klein) |
| **M33** | Peer-Asymmetrie Phone↔HU vs Analyzer↔HU (Eligibility) | STRONG H |
| **M34** | *(alt)* cmd6-Semantik — erledigt als DATAACK; kein neues Mystery | closed |
| **M35** | Timing-Signatur: INIT/HS ~0.2 s → SP/KNOCK ~+3.2 s → OPEN5001 → OPEN4004 ~+3.7 s | LAB FACT |
| **M36** | WD startet sofort und läuft **parallel** zu Etch-Bootstrap | LAB FACT |
| **M37** | Cert-Pushes sequenziell, nicht parallel | LAB FACT |
| **M38** | cdsbaseapp = MyBMW CDS-Cert; CarProber nennt j29Cert „optional cdsBaseApp“ — Wire-CN bestätigt cdsbaseapp, Brand-Map offen | LAB + Desk |
| **M39** | PKCS7 OID-Permissions: `CDS=true&RHMI=true&APPID=myBMW&Make=BMW,MINI,J29&SAS.CertificateType=APP&…` | LAB FACT |
| **M41** | F20 DATAACK 0x08 nach OPEN4004 = BCL-Frame-ACK (8+0), nicht Etch-OK | STRONG |
| **M42** | SP-Pfad folgt HS-**version**; iid/buf = Fingerprint (beide v5→SP4) | LAB FACT |
| **M43** | Official Knock TouchCommand/7 = Desk-Kommentarpfad, jetzt gemessen | LAB FACT |
| **M44** | WD-Maintenance auf F20 **und** Dummy unabhängig | FIELD+LAB FACT |
| **M48** | DATAACK selektiv: SP→10, OPEN→8, WD→12; **kein ACK56 nach KNOCK** (analyzer→F20 2026-11-15) | FIELD FACT |
| **M49** | Transport-Plane ohne MyBMW; Content-Gate nach OPEN4004 (ACK≠Etch) | FIELD FACT |

## Soll-Sequenz nächster Feldtest

```
1) P0: btsnoop_hci MyBMW Session S-B (beide Richtungen, RFCOMM-Filter aus)
      → blind ~3s Phone→HU / 56-B / OPEN / SAS / volle 667-B
2) optional S-A (SCN6 DM → SCN10 + SDP)
3) P1: KNOCK isolation / Modell-D — nach HCI
4) Nicht: weiterer OPEN4004-Spam; HFP-als-Content depriorisieren
```
Siehe `docs/evidence/FIELD_CONTENT_GATE_BOTTLENECK_20261115.md`.

## Architektur (Stand 2026-11-15)

```
RFCOMM SCN6 → BCL bootstrap (INIT→HS v5→SP2|SP4→[KNOCK?]→OPEN5001→WD)  FIELD FACT
                 │
            OPEN 4004 → ACK 8 → [content authorization UNKNOWN] → SAS/Etch/CDS
                 │
            Dummy öffnet Etch hier künstlich; F20 bleibt still ohne Owner/UI
```
