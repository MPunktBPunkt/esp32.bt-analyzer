# F20 Connected Music — End-to-End Timeline

```yaml
date: 2026-11-22
capture: FIELD_B3_GATEB_20261121T112446Z
based_on_commit: fff684417982e8bc3cd5230175ca24bc95db2213
role: forensic session index (NOT a new RHMI reverse-engineering pass)
machine_readable: F20_CONNECTED_MUSIC_END_TO_END_TIMELINE.json
```

**Zweck:** Eine chronologische, offset-genaue Gesamt-Timeline der Connected-Music-Session, die bereits CLOSED Teilanalysen (SAS/APP_AUTH → AM → RHMI → CDS → AV → Music Entry → Handle 23 → PLAY → Audio-Grenze) zu einem Arbeitsindex verbindet.

**Keine neuen Architektur-Behauptungen.** Detailquellen bleiben die Spezialberichte; hier nur Index + Rohdatenpositionen.

---

## 0. Primärquellen

| Artefakt | Pfad | Rolle |
|----------|------|-------|
| Phone→HU raw | `raw/phone_to_hu.bin` (417 174 B) | autoritative Byte-Positionen `P@` |
| HU→Phone raw | `raw/hu_to_phone.bin` (110 651 B) | autoritative Byte-Positionen `H@` |
| Etch CSV index | `etch_messages_full.csv` | BCL-orientierter Nachrichtenindex (`file_offset_hex`) |
| Auth verify | `forensic/SAS_CRYPTO_VERIFY.json` | Gate B / 18× VALID |
| Music detail | `forensic/rhmi_music/*.md` | NP/Action/Event/Home/Multitrack |
| Frame grammar | `FORENSIC_B3_FRAME_ANALYSIS_20261122.md` | BCL + Etch Framing |

**`phone_to_hu.bin.txt` / `hu_to_phone.bin.txt`:** im Repository **nicht vorhanden**. Analysten springen direkt in die Raw-Bins (oder erzeugen lokal einen Hex-Dump) anhand der hier angegebenen `P@0x…` / `H@0x…`.

---

## 1. Offset-Konventionen (Pflicht)

| Symbol | Bedeutung |
|--------|-----------|
| **`P@0x……`** | Start des Etch-Envelopes (`DE AD BE EF`) in `phone_to_hu.bin` |
| **`H@0x……`** | Start des Etch-Envelopes in `hu_to_phone.bin` |
| **`csv file_offset_hex`** | Eintrag in `etch_messages_full.csv` — typisch **BCL DATA-Header**; bei contiguous Layout gilt **Etch = csv + 8** |

### 1.1 Etch-Framing

```text
file_offset (CSV / BCL DATA header, wenn contiguous)
    + 8
    ↓
DE AD BE EF
    ↓
4 Byte BIG-ENDIAN payload length
    ↓
Etch payload

Beispiel sas_certificate:
  CSV offset 0x9a
      +8
      ↓
  DE AD BE EF          ← P@0x000000a2
      ↓
  00 00 17 e6          ← payload_len = 6118
      ↓
  payload = 6118 B
      ↓
  total etch frame = 6126 B
```

Vor `0x9a` liegt ein **Bridge-Envelope** (kein BT-Etch) — siehe FORENSIC_B3 §2.1.

### 1.2 CSV-Korrektur: benachbarte 44-Byte-Frames

Diese Offsets sind **drei getrennte** Frames und dürfen **nicht** als derselbe CSV-Treffer gelesen werden:

| CSV / Region | Etch-Start (autoritativ) | Method (Wire) |
|--------------|--------------------------|---------------|
| — / `0xe853` | **H@0xe853** | `_result_rhmi_setData` |
| `0xe87f` | **H@0xe887** (= csv+8) | `_result_rhmi_setProperty` |
| `0xe8ab` | **H@0xe8b3** (= csv+8) | `_result_rhmi_setData` |

Analog:

| CSV | Etch | Method |
|-----|------|--------|
| — / `0xec36` | H@0xec36 | `_result_rhmi_setData` |
| `0xec62` | H@0xec6a | `_result_rhmi_setData` |
| `0xec8e` | H@0xec96 | `_result_rhmi_setProperty` |

`etch_messages_full.csv` kollabiert teils mehrere Methoden auf `0xe87f` — **Raw Bytes gewinnen**.

### 1.3 Zeitachsen

| Achse | Status |
|-------|--------|
| File Order | FACT innerhalb einer Richtung |
| Wire Order | DIRECT-Paare + ORDERED/CORRELATED Querverweise |
| Wall-Clock | **nicht vorhanden** — keine gemeinsame Zeitachse erfinden |

`SESSION_START = NOT EXACTLY OBSERVED` (Capture beginnt mit Bridge-Envelope).

### 1.4 Kausalitätsklassen

| Klasse | Bedeutung |
|--------|-----------|
| **DIRECT** | Request/Result oder Action/Ack |
| **ORDERED** | Offset-Sequenz eindeutig, ohne explizite Korrelations-ID |
| **CORRELATED** | Mehrere Indizien, kein einziges Pairing-Feld |
| **UNKNOWN** | nicht belegbar |

---

## 2. Phasen-Übersicht

```text
APP_AUTH          CLOSED
   ↓
AM                CLOSED
   ↓
RHMI              CLOSED
   ↓
CDS               PARTIAL (menu path FACT; track bus NOT PROVEN)
   ↓
AV                CLOSED (session control)
   ↓
Music UI          CLOSED (Handle 23 NP spine)
   ↓
PLAY control      OBSERVED
   ↓
========================
 AUDIO TRANSPORT ?      ← NOT PROVEN
 ========================
 audible playback       ← NOT OBSERVED
```

Feldnotiz (Operator): *Spotify-Menü, Artist, Album und Song waren auf der HU sichtbar, aber es wurde kein Ton gehört.*

---

## 3. Chronologische Master-Tabelle

Spalten: Seq · Dir · Offset · CSV · Tot · Pay · Method · Causality · Bedeutung · Evidence

> Vollständige Maschinenform: `F20_CONNECTED_MUSIC_END_TO_END_TIMELINE.json` (`events[]`).

### Phase 0 — Transport / Session Start

| Seq | Dir | Offset | CSV | Tot | Pay | Method | Causality | Bedeutung | Evidence |
|----:|-----|--------|-----|----:|----:|--------|-----------|-----------|----------|
| 1 | P | `P@0x00000000` | n/a | — | — | bridge_envelope | ORDERED | Non-Etch Bridge vor BCL | FACT FORENSIC_B3 |
| 2 | P | BCL `0x9a` | `0x9a` | 8 | — | BCL_DATA | ORDERED | Erster BCL DATA; Etch @+8 | FACT |
| 3 | H | `H@0x00000000` | n/a | — | — | control_preamble | ORDERED | Preamble vor erstem Etch | FACT |
| 4 | H | `H@0x0000006c` | `0x64` | 67 | 59 | first_HU_etch | ORDERED | Erster HU-Etch | FACT |

### Phase 1 — SAS / APP_AUTH (erster Zyklus; Gate B)

| Seq | Dir | Offset | CSV | Tot | Pay | Method | Causality | Bedeutung | Evidence |
|----:|-----|--------|-----|----:|----:|--------|-----------|-----------|----------|
| 5 | P | `P@0x000000a2` | `0x9a` | 6126 | 6118 | `sas_certificate` | ORDERED | PKCS#7 APP_AUTH; pad `0x02000000` | FACT |
| 6 | H | `H@0x0000006c` | `0x64` | 67 | 59 | `_result_sas_certificate` | DIRECT | Challenge `8f873bb7…80da` | FACT CRYPTO |
| 7 | P | `P@0x000018a0` | `0x1898` | 551 | 543 | `sas_login` | DIRECT | RSA-4096 sig **512 B** | FACT CRYPTO |
| 8 | H | `H@0x000000c3` | `0xbb` | 44 | 36 | `_result_sas_login` | DIRECT | ACCEPT | FACT |
| 9 | — | — | — | — | — | AUTH_SUMMARY | CORRELATED | **18/18** VALID → Gate B CLOSED | FACT |

Krypto wird hier **nicht** neu bewiesen — siehe `SAS_CRYPTO_VERIFY.json`.

### Phase 2 — AM Bootstrap

| Seq | Dir | Offset | CSV | Method | Causality | Bedeutung |
|----:|-----|--------|-----|--------|-----------|-----------|
| 10 | P | `P@0x00001b39` | `0x1b31` | `am_create` | ORDERED | AM create |
| 11 | H | `H@0x00002ab7` | cand | `_result_am_create` | DIRECT | result |
| 12 | P | `P@0x00001b76` | `0x1b6e` | `am_addAppEventHandler` | ORDERED | early handler |
| 13 | P | `P@0x00014bdc` | cand | `am_registerApp` | ORDERED | assistant/Google (**nicht** Spotify) |
| 14 | P | `P@0x00015699` | cand | `am_registerApp` | ORDERED | screenmirror |
| 15 | P | `P@0x00018d9b` | cand | `am_addAppEventHandler` | ORDERED | ident=`…music` |
| 16 | P | `P@0x00019342` | cand | `am_registerApp` | ORDERED | spätere Welle |

Spotify ∈ AM registerApp: **REJECTED** (bestehender FACT).

### Phase 3 — RHMI Bootstrap (Music → Handle 23)

| Seq | Dir | Offset | Method | Causality | Bedeutung |
|----:|-----|--------|--------|-----------|-----------|
| 17 | P | `P@0x00014253` | `rhmi_create` | ORDERED | frühe Creates |
| 18 | P | `P@0x00014647` | `rhmi_create` | DIRECT | package `me.hufman.androidautoidrive.music` |
| 19 | H | `H@0x0000cda2` | `_result_rhmi_create` | DIRECT | **result=23** |
| 20 | P | `P@0x00014923` | `rhmi_checkResource` | ORDERED | DESCRIPTION MD5 `e9e31c31…` |
| 21 | P | `P@0x00014b78` | `rhmi_checkResource` | ORDERED | weitere Checks h=23 |
| 22 | P | `P@0x00016727` | `rhmi_initialize` | ORDERED | h=23 |
| 23 | P | `P@0x00016b48` | `rhmi_addActionEventHandler` | ORDERED | actionId=**-1**, h=23 |
| 24 | P | `P@0x00016d5b` | `rhmi_addHmiEventHandler` | ORDERED | h=23 |

Context **50034** erscheint später nur in CDS `hmi.graphicalContext` (Phase 4/6) — nicht als RHMI-create-Feld.

### Phase 4 — CDS

| Seq | Dir | Offset | Method | Causality | Bedeutung |
|----:|-----|--------|--------|-----------|-----------|
| 25 | P | `P@0x0000386f` | `cds_create` | ORDERED | CDS create |
| 26 | H | `H@0x00008c56` | `cds_onPropertyChangedEvent` | ORDERED | `entertainment.multimedia` Placeholder `NowPlayingTrack` / source=34 |
| 27 | H | `H@0x0000fa15` | `cds_onPropertyChangedEvent` | ORDERED | **Media/Radio** vis=20 **listIndex=7** |
| 28 | H | `H@0x00010f00` | `cds_onPropertyChangedEvent` | ORDERED | Media/Radio **listIndex=8** |
| 29 | H | `H@0x000132ca` | `cds_onPropertyChangedEvent` | CORRELATED | **visibleContext=50034** (nach Action-336-Pfad) |

**FACT:** listIndex 7→8; Menu-Pfad.  
**NOT PROVEN:** CDS als Track-Metadaten-Bus (Einstufung unverändert).

### Phase 5 — AV Session (Control ≠ Audio)

| Seq | Dir | Offset | CSV | Method | Causality | Bedeutung |
|----:|-----|--------|-----|--------|-----------|-----------|
| 30 | P | `P@0x0001912c` | `0x19124` | `av_create` | CORRELATED | id=`…music` (nach ack 336 #1) |
| 31 | H | `H@0x00010be7` | cand | `_result_av_create` | DIRECT | **AV handle 1** |
| 32 | P | `P@0x00020bba` | `0x20bb2` | `av_requestConnection` | ORDERED | ENTERTAINMENT |
| 33 | H | `H@0x000123fd` | cand | `_result_av_requestConnection` | DIRECT | result |
| 34 | H | `H@0x00012528` | `0x12520` | `av_requestPlayerState` | ORDERED | HU fordert PLAY |
| 35 | H | `H@0x000127bd` | `0x127b5` | `av_connectionGranted` | ORDERED | granted |
| 36 | P | `P@0x000315a6` | `0x30923*` | `av_playerStateChanged` | ORDERED | PLAY |

\*CSV `0x30923` zeigt BCL, aber **+8 ist nicht DEADBEEF**. Autoritativ: **`P@0x000315a6`**.

**AV Session Setup ≠ Audio Transport.**

### Phase 6 — Music Entry (Action 336 / 248)

| Seq | Dir | Offset | Method | IDs | Causality | Bedeutung |
|----:|-----|--------|--------|-----|-----------|-----------|
| 37 | H | `H@0x0000ed2a` | `rhmi_onActionEvent` | action=**336**, h=23, args=`{}` | DIRECT | Entry #1 |
| 38 | P | `P@0x00018f7a` | `rhmi_ackActionEvent` | 336 | DIRECT | ack #1 |
| 39 | H | `H@0x00012061` | `rhmi_onActionEvent` | 336 | DIRECT | Entry #2 |
| 40 | P | `P@0x00020d26` | `rhmi_ackActionEvent` | 336 | DIRECT | ack #2 |
| 41 | H | `H@0x00012fb7` | `rhmi_onActionEvent` | 336 | DIRECT | Entry #3 |
| 42 | P | `P@0x00031d49` | `rhmi_ackActionEvent` | 336 | DIRECT | ack #3 |
| 43 | H | `H@0x00013640` | `rhmi_onActionEvent` | **248**, args=`{99:false}` | DIRECT | Apps path |
| 44 | P | `P@0x0004d079` | `rhmi_ackActionEvent` | 248 | DIRECT | ack |

```text
HOME_ENTRY_OBJECT_ID = NOT OBSERVED
```

336 ≃ Music-Entry-Button: **INFERENCE + XML STRONG** (nicht FACT).

336 → av_create: **CORRELATED/ORDERED** (kein gemeinsames Pairing-Feld; zeitlich/session-logisch).

### Phase 7 — Handle 23 Wire-Map (kompakt)

| ID | Wire-Status | Evidence |
|----|-------------|----------|
| 444 | Provider `"Spotify"` | FACT `P@0x00031f7e` |
| 445 | Artist | FACT `P@0x0001b897` / refine `P@0x00020af0` |
| 446 | Title | FACT `P@0x0001b8e6` |
| 447 | zweites Title/NP-Feld | FACT `P@0x0001bdf7` |
| 456 | Cover JPEG | FACT `P@0x0001be4b` (JPEG @`P@0x0001be8b`, 18474 B, sha256 `3df57789…`) |
| 458 | Playlist/NP-Tabelle | FACT `P@0x0001b572` |
| 655 | Statusbar `"Spotify"` | FACT `P@0x00031aac` |
| 336 / 248 | Actions | Wire FACT |
| 660 / 661 | Events | Wire FACT |

Semantik 336/248/660/661: weiterhin **INFERENCE (+ XML)** — nicht aus dieser Timeline neu erhoben.

### Phase 8 — Konkreter Music-Zustand

| Feld | Wert | Offset |
|------|------|--------|
| Provider | Spotify | 444 @`P@0x31f7e`, 655 @`P@0x31aac` |
| Artist | Halestorm, I Prevail → Halestorm | 445 |
| Title | can u see me in the dark? | 446/447 |
| Cover | JPEG 18474 B | 456 |
| Playlist IC | Model **535** EntICPlaylist | `P@0x0004d6b9` |

- Nur **ein** NP-Titel beobachtet.
- Pink Floyd = Playlist-Zeile in 535 — **nicht** NP Track B/C.
- Multi-Track SM: **PARTIAL**.

### Phase 9 — Events 661 / 660

| Event | Offset | Vorgänger (ORDERED) |
|------:|--------|---------------------|
| **661** | `P@0x00031bf3` | `setData 655="Spotify"` @`P@0x00031aac` |
| **660** | `P@0x0004d1ea` | `ack 248` @`P@0x0004d079` |

### Phase 10 — PLAY und Audio-Grenze

| Ebene | Status |
|-------|--------|
| AUTH | PROVEN / CLOSED |
| RHMI / Music UI | PROVEN / CLOSED |
| AV session | PROVEN / CLOSED |
| PLAY-related control | OBSERVED (`av_playerStateChanged` PLAY) |
| actual audio transport | **NOT PROVEN** |
| audio reaching HU backend | **UNKNOWN** |
| audible playback | **NOT OBSERVED** |
| TCP-Brücke als Ursache | **UNKNOWN** (nicht behaupten) |

---

## 4. Kombiniertes Ablaufdiagramm (kausal, mit Offsets)

```text
PHONE                                              HU
  │                                                  │
  │ P@0x000000a2 sas_certificate                     │
  ├─────────────────────────────────────────────────>│
  │                           H@0x0000006c challenge │
  │<─────────────────────────────────────────────────┤
  │ P@0x000018a0 sas_login (512 B sig)               │
  ├─────────────────────────────────────────────────>│
  │                           H@0x000000c3 ACCEPT    │
  │<─────────────────────────────────────────────────┤
  │ P@0x00001b39 am_create                           │
  ├─────────────────────────────────────────────────>│
  │ P@0x00014647 rhmi_create …music                  │
  ├─────────────────────────────────────────────────>│
  │                           H@0x0000cda2 h=23      │
  │<─────────────────────────────────────────────────┤
  │ P@0x00016727 initialize / handlers 23            │
  ├─────────────────────────────────────────────────>│
  │                           H@0x0000ed2a Action336 │
  │<─────────────────────────────────────────────────┤
  │ P@0x00018f7a ack 336                             │
  ├─────────────────────────────────────────────────>│
  │ P@0x0001912c av_create …music                    │
  ├─────────────────────────────────────────────────>│
  │                           H@0x00010be7 AV h=1    │
  │<─────────────────────────────────────────────────┤
  │ P@0x0001b897.. setData 445/446/447/456           │
  ├─────────────────────────────────────────────────>│
  │ P@0x00020bba av_requestConnection                │
  ├─────────────────────────────────────────────────>│
  │                           H@0x000127bd granted   │
  │                           H@0x000132ca vis=50034 │
  │<─────────────────────────────────────────────────┤
  │ P@0x000315a6 av_playerStateChanged PLAY          │
  ├─────────────────────────────────────────────────>│
  │ P@0x00031aac setData 655 Spotify                 │
  │ P@0x00031bf3 triggerEvent 661                    │
  ├─────────────────────────────────────────────────>│
  │                           H@0x00013640 Action248 │
  │<─────────────────────────────────────────────────┤
  │ P@0x0004d079 ack 248                             │
  │ P@0x0004d1ea triggerEvent 660                    │
  │ P@0x0004d6b9 setData 535 playlist                │
  ├─────────────────────────────────────────────────>│
  │                                                  │
  │ ============ AUDIO TRANSPORT ? ================  │
  │              NOT PROVEN / NOT OBSERVED           │
```

---

## 5. Raw Evidence Index

### AUTH
- `sas_certificate`: **P@0x000000a2** (CSV `0x9a`)
- `_result_sas_certificate`: **H@0x0000006c**
- `sas_login`: **P@0x000018a0** (CSV `0x1898`)
- `_result_sas_login`: **H@0x000000c3**

### AM
- `am_create`: **P@0x00001b39**
- `_result_am_create`: **H@0x00002ab7**
- `am_addAppEventHandler` (music): **P@0x00018d9b**

### RHMI
- `rhmi_create` music: **P@0x00014647**
- `_result_rhmi_create` h=23: **H@0x0000cda2**
- `rhmi_initialize` 23: **P@0x00016727**
- `rhmi_addActionEventHandler` 23: **P@0x00016b48**

### CDS
- multimedia placeholder: **H@0x00008c56**
- Media/Radio listIndex 7: **H@0x0000fa15**
- Media/Radio listIndex 8: **H@0x00010f00**
- visibleContext 50034: **H@0x000132ca**

### AV
- `av_create`: **P@0x0001912c**
- `_result_av_create`: **H@0x00010be7**
- `av_requestConnection`: **P@0x00020bba**
- `av_requestPlayerState`: **H@0x00012528**
- `av_connectionGranted`: **H@0x000127bd**
- PLAY: **P@0x000315a6** `av_playerStateChanged`

### MUSIC
- Action 336: **H@0x0000ed2a**, **H@0x00012061**, **H@0x00012fb7**
- ack 336: **P@0x00018f7a**, **P@0x00020d26**, **P@0x00031d49**
- setData 444/445/446/447/456/458/655: siehe JSON / Phase 7
- Event 661: **P@0x00031bf3**
- Action 248: **H@0x00013640** · ack: **P@0x0004d079**
- Event 660: **P@0x0004d1ea**
- setData 535: **P@0x0004d6b9**

---

## 6. Reverse Lookup / Analyse-Einstieg

| Frage | Einstiegspunkt |
|-------|----------------|
| APP_AUTH genauer | `P@0x000000a2` |
| SAS Challenge | `H@0x0000006c` |
| Music Context / create | `P@0x00014647` → `H@0x0000cda2` |
| Action 336 | `H@0x0000ed2a` |
| AV Session | `P@0x0001912c` |
| PLAY control | `P@0x000315a6` |
| Cover | `P@0x0001be4b` / JPEG `P@0x0001be8b` |
| Event 661 | `P@0x00031bf3` |
| Event 660 | `P@0x0004d1ea` |
| CDS Media transition | `H@0x0000fa15` → `H@0x00010f00` → `H@0x000132ca` |
| möglicher Audio-Beginn | nach `P@0x000315a6` — **bisher keine Audio-Frames** |

---

## 7. Evidence Summary

| Bereich | Status |
|---------|--------|
| APP_AUTH | CLOSED |
| SAS certificate | CLOSED |
| SAS login | CLOSED |
| AM bootstrap | CLOSED |
| RHMI bootstrap | CLOSED |
| Music Handle 23 | CLOSED |
| Action 336 wire | CLOSED |
| Action 248 wire | CLOSED |
| Event 660 wire | CLOSED |
| Event 661 wire | CLOSED |
| RHMI↔AV ordering | CLOSED |
| Home Entry Object-ID | NOT OBSERVED |
| Multi-Track State Machine | PARTIAL |
| AV Track Correlation | SESSION_ONLY |
| CDS Track Metadata Bus | NOT PROVEN |
| PLAY control | OBSERVED |
| Audio transport | NOT PROVEN |
| Audible playback | NOT OBSERVED |

---

## 8. Verweise (Detailquellen, nicht duplizieren)

- Auth: `RAW_FORENSIC_ANALYSIS.md`, `SAS_CRYPTO_VERIFY.json`, `EVAL.md`
- Framing: `FORENSIC_B3_FRAME_ANALYSIS_20261122.md`
- Music: `rhmi_music/RHMI_MUSIC_UI_STATE_MACHINE.md`
- Interaction/AV/Home: `rhmi_music/RHMI_MUSIC_INTERACTION_AV_HOME_ANALYSIS.md`
- Multitrack/Home entry: `rhmi_music/RHMI_MUSIC_HOME_MULTITRACK_ANALYSIS.md`

---

## 9. PLAY-Boundary Skim (2026-11-22) + Lab-Overlay

Offline-Skim: [`PLAY_BOUNDARY_SKIM_20261122.md`](PLAY_BOUNDARY_SKIM_20261122.md).

Kurz: nach `P@0x000315a6` folgen RHMI `setData`/Event 661 und **große BCL-4000-Fragmente auf dest 4004** (RHMI-shaped, z. B. Etch @`P@0x00032784` len 66488). **Kein** weiteres `av_*`. Audio-Transport weiter **NOT PROVEN**.

Lab-Logs (`LAB_MUSIC_NP_SPINE_*`, `LAB_A2DP_BCL_CORR_*`, `AUDIOOK` B2A) sind **andere Sessions** — Overlay schließt B3-Audio nicht, liefert aber die Lab-Forderung: **Dual-Plane** (BCL + A2DP/transport) bei jedem Music-PLAY-Test.

## 10. Nächster Feldtest (aus Timeline abgeleitet)

Priorität vor Multi-Track A→B:

1. **hörbares** Playback (oder bewusster Fail) **und**
2. paralleles Dual-Plane-Log (BCL/Etch **und** A2DP/transport-state; Transport erst benennen nach Nachweis),  
   optional danach Next-Track für Track A→B,

damit die Grenze unter `P@0x000315a6` geschlossen werden kann.
