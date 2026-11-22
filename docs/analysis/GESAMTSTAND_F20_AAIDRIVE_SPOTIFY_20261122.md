# BMW F20 NBT Evo / AAIdrive — technischer Gesamtstand

```yaml
date: 2026-11-22
claim_level: mixed — see tags
gate_b: CLOSED
app_auth_rsa_verify: CLOSED (18/18 FIELD)
primary_evidence: docs/evidence/FIELD_B3_GATEB_20261121T112446Z/
raw_forensic: …/RAW_FORENSIC_ANALYSIS.md
crypto: …/SAS_CRYPTO_VERIFY.json
next: RHMI Music object/data/property/action graph from wire
```

## 1. Kurzfassung

Feldversuch B3 (OnePlus/AAIdrive → B3 Relay → F20 NBT Evo) belegt:

> Android/AAIdrive kann über BCL/Etch eine gültige BMW `APP_AUTH`-Authentifizierung durchführen und anschließend RHMI/AM/CDS/AV mit sichtbarer Music/Spotify-UI aufbauen.

Vier technisch getrennte Ebenen:

1. **SAS / APP_AUTH** — Cert, Challenge, 512-B-Sig, Accept (**CRYPTO VERIFIED**)
2. **AM** — App-Lifecycle / `am_registerApp` (5 Apps; **nicht** Spotify)
3. **RHMI** — Remote-UI (Handle **23** = `…music`)
4. **CDS + AV** — Fahrzeugkontext + Entertainment-Audio

Spotify ist **keine** native NBT-Evo-App und **kein** `am_registerApp`-Eintrag. Music kommt von der Phone-Seite (`me.hufman.androidautoidrive.music`) über RHMI+AV.

## 2. Primärbeweis

| Datei | Größe | SHA-256 |
|-------|------:|---------|
| `raw/phone_to_hu.bin` | 417174 | `86272e98…5c158c` |
| `raw/hu_to_phone.bin` | 110651 | `0ca169d1…37ab2d` |

`b3.jsonl` = sekundär (u. a. kein `sas_certificate`-Decode; Fragment-`etch_decode_error`).

## 3. Transport

```text
RFCOMM → BCL (u16BE cmd/src/dest/len) → Etch (DEADBEEF|u32BE len|body) → BMWRemoting
```

- Phone fragmentiert große Etch oft bei BCL `len=4000`
- HU sendet Etch bis BCL `len=5306` in einem Frame
- **FACT — RAW** (siehe `RAW_FORENSIC_ANALYSIS.md` §4)

## 4. APP_AUTH — CLOSED

| Item | Status |
|------|--------|
| 12× `sas_certificate`, 19 Challenges, 18× `sas_login`, 18× Accept | **FACT — RAW** |
| Leaf `CN=a4a_app_BMWTouchCommand_Connection_00.00.10` serial `0x0AA9` RSA-4096 | **FACT — DECODED** |
| Pad `MD5(0x02000000)` XOR → MD5 → PKCS#1 v1.5 | **FACT — CRYPTO VERIFIED** |
| **18/18** HU-akzeptierte Logins RSA-VERIFY PASS | **FACT — CRYPTO VERIFIED** |
| Private-Key-Herkunft / Standalone-Signer | **OPEN** |
| Feature-PFX RSA-1536 = APP_AUTH | **REJECTED** |

Artefakte: `SAS_CERTIFICATE.der`, `SAS_CRYPTO_VERIFY.json`, `SAS_SIGNATURES/`.

## 5. Post-Auth Architektur

```text
SAS ACCEPT
   ├── AM  (registerApp ×5: Google, ScreenMirror, Alexa, BT, YouTube)
   ├── CDS (properties + onPropertyChanged — großer Laufzeitanteil)
   ├── RHMI (create/checkResource/initialize/setData/setProperty/events)
   └── AV  (create music → requestConnection ENTERTAINMENT → Granted → PLAY)
```

Multi-SAS: mehrere parallele OPEN-4004-Kanäle mit eigenen Cert/Challenge/Login — **FACT — RAW**.

## 6. Spotify / Music — Abgrenzung

| Claim | Level |
|-------|-------|
| Spotify auf HU sichtbar (Operator) | **FIELD FACT** |
| ASCII `Spotify`, `Halestorm`, `I Prevail`, Cover im Raw | **FIELD FACT** |
| Spotify ∈ fünf `am_registerApp` | **REJECTED** |
| RHMI `rhmi_create` → `…music` → Handle **23** | **FACT** |
| `setData` **444** + **655** = `"Spotify"` | **FACT** |
| **445** artist · **446/447** title · **456** cover JPEG | **FACT** (+ XML `audioHmiState@24` **STRONG**) |
| Actions **336**/ **248** · Events **660**/ **661** (wire lifecycle) | **FACT** |
| 336 ≃ Music entry / 248 ≃ Apps toolbar select | **INFERENCE** (+ XML STRONG) |
| 661 statusbar / 660 multimediaInfo | **INFERENCE** (+ XML STRONG) |
| AV id = `…music` → ENTERTAINMENT → PLAY; coupled after Action 336 | **FACT** order |
| BMW Home/Launcher Entry-Object-ID | **NOT OBSERVED** |
| CDS Media/Radio → visibleContext 50034 near Action 336 | **FACT** (menu path) |
| Multi-track NP (Track A→B) | **NOT OBSERVED** — single Halestorm NP; EntICPlaylist 535 multi-row |
| AV per track change | **NOT OBSERVED** (session-only) |

Detail: [`RHMI_MUSIC_UI_STATE_MACHINE.md`](../evidence/FIELD_B3_GATEB_20261121T112446Z/forensic/rhmi_music/RHMI_MUSIC_UI_STATE_MACHINE.md) · [`RHMI_MUSIC_INTERACTION_AV_HOME_ANALYSIS.md`](../evidence/FIELD_B3_GATEB_20261121T112446Z/forensic/rhmi_music/RHMI_MUSIC_INTERACTION_AV_HOME_ANALYSIS.md) · [`RHMI_MUSIC_HOME_MULTITRACK_ANALYSIS.md`](../evidence/FIELD_B3_GATEB_20261121T112446Z/forensic/rhmi_music/RHMI_MUSIC_HOME_MULTITRACK_ANALYSIS.md)

## 7. Was beschreibbar vs. offen ist

**Geschlossen:** Auth, Bootstrap-Architektur, Handle-23 NP-Spine (444–447, 456, 655), AV-Kopplung, Spotify≠AM, Home-Entry-Object-ID Negativbefund, single-track SM + playlist 535.

**Noch offen:** echte Track-A→B Feld-Session, 446-vs-447 Autorität, Property/Component-Semantik, Standalone-Signer.

## 8. Next workstream

1. ~~Wire RHMI Music graph~~ → **done** (2026-11-22)
2. ~~Home Entry + Multi-Track analysis~~ → **done** (2026-11-22; Track B still needs new capture)
3. Field capture with explicit next/prev track (close Track A→B)
4. Lab NP-spine stub mit wire-proven IDs (inkl. cover **456**) — after Track-B model closed enough
5. F20-Trial fremder RHMI-Client
6. PiDrive Music/RHMI (nicht Spotify-AM)

## 9. Related

- [`…/RAW_FORENSIC_ANALYSIS.md`](../evidence/FIELD_B3_GATEB_20261121T112446Z/RAW_FORENSIC_ANALYSIS.md)
- [`…/EVAL.md`](../evidence/FIELD_B3_GATEB_20261121T112446Z/EVAL.md) · [`ADDENDUM_RHMI_AM_20261121.md`](../evidence/FIELD_B3_GATEB_20261121T112446Z/ADDENDUM_RHMI_AM_20261121.md)
- [`SAS_STATUS_CRYPTO_CLOSED_20261120.md`](SAS_STATUS_CRYPTO_CLOSED_20261120.md)
- [`FIELD_GATE_B_CLOSED_NEXT_RHMI_TEMPLATE_20261121.md`](FIELD_GATE_B_CLOSED_NEXT_RHMI_TEMPLATE_20261121.md)
