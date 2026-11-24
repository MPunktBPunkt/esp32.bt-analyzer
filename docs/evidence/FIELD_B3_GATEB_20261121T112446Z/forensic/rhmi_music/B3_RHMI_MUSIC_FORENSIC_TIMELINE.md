# B3 RHMI Music Forensic Timeline

```yaml
date: 2026-11-23
capture: FIELD_B3_GATEB_20261121T112446Z
epistemic: Wire-FACT before Interpretation; XML secondary; Technology-Audit last
primary_json:
  - INTERACTION_TIMELINE_HU.json
  - INTERACTION_TIMELINE_PHONE.json
cross_check:
  - RHMI_MUSIC_INTERACTION_AV_HOME_ANALYSIS.md
  - RHMI_MUSIC_UI_STATE_MACHINE.md
  - RHMI_MUSIC_HOME_MULTITRACK_ANALYSIS.md
  - ../F20_CONNECTED_MUSIC_END_TO_END_TIMELINE.md
  - etch_messages_full.csv
  - raw/phone_to_hu.bin + raw/hu_to_phone.bin
  - resources/ui_description_multimedia_v3.xml
  - resources/HANDLE23_CORRELATION.md
technology_audit:
  - /home/martin/projects/technology-audit/technologies/bmw-rhmi/SHEET.md
  - /home/martin/projects/technology-audit/technologies/bmw-av/SHEET.md
  - /home/martin/projects/technology-audit/audits/bmw-rhmi-music-handle23-field-2026-11-21/
machine_core: B3_RHMI_MUSIC_FORENSIC_TIMELINE_CORE.json
```

## 0. Method / framing

**FACT (korrigiert 2026-11-24).** Es gibt **keine gemeinsame Host-Wall-Clock** über beide Raw-Bins. Aber Phone-`message_id` in Etch **ist** eine brauchbare Phone-Uhr:

| Quelle | `message_id`-Lesart | Span in diesem Capture |
|--------|---------------------|------------------------|
| Phone→HU | Epochen-**ms** (UTC 2026-11-21 11:35:13.532 → 11:37:20.076) | **126 544 ms** (~127 s), 337 msgs |
| HU→Phone | Größenordnung Epochen-**µs**, faktisch **Monotonie-Zähler** (+1 … +10) | **623** Schritte / 573 msgs — **kein** nutzbarer Wall-Clock über die Session |

Cross-bin merge bleibt: `P@`/`H@` + `_inReplyTo`↔Phone-`message_id`. Phone-seitige Events zusätzlich als `t+Δms` relativ zu `min(phone message_id)` möglich. HU-initiierte Events (`rhmi_onActionEvent`, `av_connectionGranted`, CDS, …) haben **keine** Phone-ms-Ankunftszeit im Capture.

**FACT.** `in_reply_to` auf HU→Phone: **319 / 427** bit-genau ∈ Phone-`message_id` → Paarung **DIRECT** (nicht nur ORDERED). Die **108** Misses liegen fast alle bei `_result_rhmi_setData` / `_result_rhmi_setProperty` und zeigen auf IDs **im** Phone-Zeitfenster, die in `ETCH_TIMELINE.json` fehlen → **Decode-/Index-Lücke**, nicht „HU-initiiert“. (`ETCH_TIMELINE` fehlt u. a. `av_playerStateChanged@202150` und `ack 336@102266`; `INTERACTION_TIMELINE_*` ist für Music vollständiger.)

**FACT.** „HU-Verarbeitungslatenz in Phone-ms“ ist aus IDs **nicht** messbar: die Antwort trägt nur HU-Zähler-`message_id`, keinen Phone-Empfangszeitstempel.

**FACT.** Music-Phone-Spine nach `message_id` sortiert **ändert die Kausalreihenfolge nicht** (336→AV→NP→PLAY→661→248→660). Keine Neu-Sortierung der Forensic Timeline nötig — nur Anreicherung um Phone-`t+Δms` und DIRECT-Upgrade für gematchte `_result_*`.

**FACT.** `phone_to_hu.bin.txt` / `hu_to_phone.bin.txt` are **not present**. Authoritative byte sources are `raw/*.bin`. Textual indexes: `etch_messages_full.csv` (BCL-oriented, incomplete Etch method coverage) and the DEADBEEF forensic extracts under `forensic/rhmi_music/`.

**FACT.** PLAY control anchor = **`P@0x000315a6` (dec 202150)** = `av_playerStateChanged(PLAY)`. CSV candidate `0x30923` is **rejected** (BCL header without Etch at +8). Phone-ms for PLAY (`INTERACTION`): mid `1795260937953` ≈ **t+24.4 s** after first phone Etch mid (Session-relativ; absolute UTC from mid).

**Nebenbefunde (nicht Music-Reihenfolge):** SAS in Wellen (~0 / 3.3 / 6.5 / 7.5 / 19.6 s + späte Concat-Welle ~118 s) — multi-cycle / multi-INIT concat (Relay-Audit). BCL `src=dest=5001` DATA len=4 periodisch — **UNKNOWN** (Keepalive-Kandidat). Skew Phone-ms vs HU-µs-Interpretation ≈ **525 s** — erklärt warum keine gemeinsame absolute Achse.

**Planes (never mixed as one bus):**

| Plane | What it carries in this capture |
|-------|----------------------------------|
| RHMI/UI | Models, Actions, Events, setData/setProperty |
| AV Control | `av_*` session/player state |
| CDS | `cds_onPropertyChangedEvent` (menu/context) |
| Bluetooth/Audio transport | **NOT OBSERVED** in these bins |

---

## 1. Master chronological table (relevant messages)

Legend — **Evidenzstatus:** FACT / INFERENCE / UNKNOWN.  
**Technology-Audit:** CLOSED/FIELD FACT · SUPPORTED · INFERENCE · OPEN · CONTRADICTED · REJECTED (relative to `bmw-rhmi` / `bmw-av` sheets).

| # | Offset | Richtung | Etch-Methode | Handle | Action/Event/Model | Payload | Bedeutung | Evidenz | Technology-Audit |
|--:|--------|----------|--------------|--------|--------------------|---------|-----------|---------|------------------|
| 1 | P@6969 / `0x1b39` | PHONE → HU | `am_create` | — | — | — | AM bootstrap | FACT | SUPPORTED (Connected stack ≠ RHMI alone) |
| 2 | H@10935 | HU → PHONE | `_result_am_create` | — | result=1 | — | AM handle 1 | FACT | SUPPORTED |
| 3 | P@82515 | PHONE → HU | `rhmi_create` | — | pkg=calendar | meta | → handle 21 | FACT | CLOSED/FIELD FACT (handle map) |
| 4 | P@82699 | PHONE → HU | `rhmi_create` | — | pkg=readout | meta | → handle 22 | FACT | CLOSED/FIELD FACT |
| 5 | H@52368 | HU → PHONE | `_result_rhmi_create` | — | result=**21** | — | create ACK | FACT | CLOSED/FIELD FACT |
| 6 | H@52438 | HU → PHONE | `_result_rhmi_create` | — | result=**22** | — | create ACK | FACT | CLOSED/FIELD FACT |
| 7 | P@83527 / `0x14647` | PHONE → HU | `rhmi_create` | — | pkg=**…music** | vendor=me.hufman | Music create | FACT | CLOSED/FIELD FACT |
| 8 | H@52642 / `0xcda2` | HU → PHONE | `_result_rhmi_create` | — | result=**23** | — | **Handle 23 born** | FACT | CLOSED/FIELD FACT |
| 9 | P@83705 | PHONE → HU | `rhmi_create` | — | pkg=mapview | — | → 24 | FACT | CLOSED/FIELD FACT |
| 10 | H@52724 | HU → PHONE | `_result_rhmi_create` | — | result=**24** | — | create ACK | FACT | CLOSED/FIELD FACT |
| 11 | P@84259 | PHONE → HU | `rhmi_checkResource` | **23** | DESCRIPTION | MD5 `e9e31c31…` size=92085 name=`""` | H23 DESCRIPTION check | FACT | CLOSED; MD5≠SHA-256 whitelist |
| 12 | H@53120 | HU → PHONE | `_result_rhmi_checkResource` | — | result=**true** | — | cache hit ACK | FACT | CLOSED (`check true` ⇒ no upload *this capture*) |
| 13 | P@84856 | PHONE → HU | `rhmi_checkResource` | **23** | TEXTDB | MD5 `1a1f84fb…` size=393 | H23 TEXTDB | FACT | SUPPORTED |
| 14 | H@53702 | HU → PHONE | `_result_rhmi_checkResource` | — | result=**true** | — | ACK | FACT | CLOSED |
| 15 | P@89109 | PHONE → HU | `rhmi_checkResource` | **23** | IMAGEDB | MD5 `0b010109…` size=162483 | H23 IMAGEDB | FACT | SUPPORTED |
| 16 | H@54766 | HU → PHONE | `_result_rhmi_checkResource` | — | result=**true** | — | ACK | FACT | CLOSED |
| 17 | P@91943 | PHONE → HU | `rhmi_initialize` | **23** | — | — | H23 initialize | FACT | CLOSED/FIELD FACT |
| 18 | H@56050 | HU → PHONE | `_result_rhmi_initialize` | — | — | empty ack | initialize ACK | FACT | CLOSED |
| 19 | P@93000 | PHONE → HU | `rhmi_addActionEventHandler` | **23** | actionId=**-1** | ident=`…music` | wildcard actions | FACT | SUPPORTED |
| 20 | H@56535 | HU → PHONE | `_result_rhmi_addActionEventHandler` | — | — | — | ACK | FACT | SUPPORTED |
| 21 | P@93531 | PHONE → HU | `rhmi_addHmiEventHandler` | **23** | eventId=**-1** | ident=`…music` | wildcard HMI | FACT | SUPPORTED |
| 22 | H@57255 | HU → PHONE | `_result_rhmi_addHmiEventHandler` | — | — | — | ACK | FACT | SUPPORTED |
| 23 | P@92612 | PHONE → HU | `rhmi_create` | — | screenmirror | — | → 25 | FACT | CLOSED/FIELD FACT |
| 24 | H@56242 | HU → PHONE | `_result_rhmi_create` | — | result=**25** | — | create ACK | FACT | CLOSED/FIELD FACT |
| — | *(global)* | both | `rhmi_checkResource` / `_result_*` | 21–25 | ×11 | all results **true** | **0× `rhmi_setResource`** in capture | FACT | CLOSED/FIELD FACT; REJECTED “true⇒upload” |
| 25 | P@101787 | PHONE → HU | `am_addAppEventHandler` | 1 | ident=`…music` | — | AM music hook (≠ home tile) | FACT | REJECTED Spotify=`am_registerApp` |
| 26 | H@60714 / `0xed2a` | HU → PHONE | `rhmi_onActionEvent` | **23** | **Action 336** | `args={}` | 336 instance #1 | FACT | CLOSED wire; semantic INFERENCE |
| 27 | H@60829…62469 | HU → PHONE | `rhmi_onHmiEvent` | **23** | Event **2** | comps 70/84/102/114 | focus churn near 336#1 | FACT ids; semantics OPEN | OPEN (1/2/11 desk-mapped, B3 ids only) |
| 28 | P@102266 | PHONE → HU | `rhmi_ackActionEvent` | **23** | Action 336 | success=**true** confirmId=1 | ACK 336 #1 | FACT | CLOSED |
| 29 | H@68047 | HU → PHONE | `_result_rhmi_ackActionEvent` | — | — | — | HU result for ack | FACT | SUPPORTED |
| 30 | P@102700 / `0x1912c` | PHONE → HU | `av_create` | — | id=`…music` | instanceID=14 | AV session create | FACT | CLOSED (`bmw-av`) |
| 31 | H@68583 | HU → PHONE | `_result_av_create` | — | result=**1** | — | **AV handle 1** | FACT | CLOSED; RHMI23≠AV1 |
| 32 | P@108622 | PHONE → HU | `rhmi_setData` | **23** | Model **495** | `"Apps"` | toolbar tooltip text | FACT | SUPPORTED (248 XML path) |
| 33 | P@111986 | PHONE → HU | `rhmi_setData` | **23** | Model **458** | RHMIDataTable | playlist table | FACT | CLOSED/FIELD FACT |
| 34 | P@112791 | PHONE → HU | `rhmi_setData` | **23** | Model **445** | `"Halestorm, I Prevail"` | artist string | FACT | CLOSED/FIELD FACT |
| 35 | P@112870 | PHONE → HU | `rhmi_setData` | **23** | Model **446** | `"can u see me in the dark?"` | title-like string | FACT | CLOSED value; album-role XML |
| 36 | P@114167 | PHONE → HU | `rhmi_setData` | **23** | Model **447** | `"can u see me in the dark?"` | same title string | FACT | CLOSED value; track-role XML |
| 37 | P@114251 / `0x1be4b` | PHONE → HU | `rhmi_setData` | **23** | Model **456** | JPEG @P@114315 len=18474 sha256`3df57789…` | cover image payload | FACT (raw modelId `0x01c8`+JPEG); full codec decode PARTIAL | CLOSED/FIELD FACT w/ **decoder-gap note** |
| 38 | H@64021 | HU → PHONE | `cds_onPropertyChangedEvent` | — | Media/Radio | vis=20 listIndex=**7** | CDS menu | FACT | OPEN vs RHMI track-bus |
| 39 | H@69376 | HU → PHONE | `cds_onPropertyChangedEvent` | — | Media/Radio | listIndex=**8** | CDS menu step | FACT | OPEN track-bus |
| 40 | H@73825 / `0x12061` | HU → PHONE | `rhmi_onActionEvent` | **23** | **Action 336** | `{}` | 336 instance #2 | FACT | CLOSED wire |
| 41 | P@133872 | PHONE → HU | `rhmi_setData` | **23** | Model **445** | `"Halestorm"` | artist shortened | FACT | SUPPORTED |
| 42 | P@134074 | PHONE → HU | `av_requestConnection` | **1** | ENTERTAINMENT | — | AV connect request | FACT | CLOSED (`bmw-av`) |
| 43 | P@134438 | PHONE → HU | `rhmi_ackActionEvent` | **23** | Action 336 | success=true confirmId=1 | ACK 336 #2 | FACT | CLOSED |
| 44 | H@74749 | HU → PHONE | `_result_av_requestConnection` | — | — | — | AV connect ACK | FACT | CLOSED |
| 45 | H@75048 / `0x12528` | HU → PHONE | `av_requestPlayerState` | **1** | **PLAY** | ENTERTAINMENT | HU requests PLAY | FACT | CLOSED; ≠ audible audio |
| 46 | H@75709 / `0x127bd` | HU → PHONE | `av_connectionGranted` | **1** | ENTERTAINMENT | — | AV granted | FACT | CLOSED |
| 47 | H@77751 / `0x12fb7` | HU → PHONE | `rhmi_onActionEvent` | **23** | **Action 336** | `{}` | 336 instance #3 | FACT | CLOSED wire |
| 48 | H@78538 / `0x132ca` | HU → PHONE | `cds_onPropertyChangedEvent` | — | **visibleContext=50034** | menuTitle=`""` | CDS RHMI context | FACT | SUPPORTED menu path; NOT RHMI objectId |
| 49 | P@202150 / **`0x315a6`** | PHONE → HU | `av_playerStateChanged` | **1** | **PLAY** | ENTERTAINMENT | Control-plane PLAY | FACT | CLOSED; REJECTED “PLAY=audio proven” |
| 50 | H@76691 | HU → PHONE | `_result_av_playerStateChanged` | — | — | — | PLAY ACK | FACT | CLOSED |
| 51 | P@203436 | PHONE → HU | `rhmi_setData` | **23** | Model **655** | `"Spotify"` | statusbar text model | FACT | CLOSED/FIELD FACT |
| 52 | P@203763 | PHONE → HU | `rhmi_triggerEvent` | **23** | **Event 661** | `{0:null}` | after 655 | FACT | CLOSED wire; statusbar role INFERENCE |
| 53 | H@78175 | HU → PHONE | `_result_rhmi_triggerEvent` | — | — | — | Event 661 ACK | FACT | CLOSED |
| 54 | P@204105 | PHONE → HU | `rhmi_ackActionEvent` | **23** | Action 336 | success=true confirmId=1 | ACK 336 #3 | FACT | CLOSED |
| 55 | P@204442 | PHONE → HU | `rhmi_setData` | **23** | Model **653** | `"Halestorm"` | MM-info artist model | FACT | CLOSED value |
| 56 | P@204510 | PHONE → HU | `rhmi_setData` | **23** | Model **654** | `"can u see me in the dark?"` | MM-info title model | FACT | CLOSED value |
| 57 | P@204670 | PHONE → HU | `rhmi_setData` | **23** | Model **444** | `"Spotify"` | NP provider text | FACT | CLOSED/FIELD FACT |
| 58 | H@79158 | HU → PHONE | `rhmi_onHmiEvent` | **23** | Event **11** | comp=**10** `{23:true}` | toolbarHmiState (XML) | FACT ids; XML INFERENCE | SUPPORTED desk map Focus/Visible |
| 59 | H@79279 | HU → PHONE | `rhmi_onHmiEvent` | **23** | Event **1** | comp=**10** `{4:true}` | toolbar | FACT; semantics OPEN | OPEN |
| 60 | H@79424 / `0x13640` | HU → PHONE | `rhmi_onActionEvent` | **23** | **Action 248** | `{99:false}` | 248 instance | FACT | CLOSED wire; Apps-role INFERENCE |
| 61 | P@315513 | PHONE → HU | `rhmi_ackActionEvent` | **23** | Action 248 | success=true confirmId=1 | ACK 248 | FACT | CLOSED |
| 62 | H@81035 | HU → PHONE | `_result_rhmi_ackActionEvent` | — | — | — | HU result | FACT | SUPPORTED |
| 63 | P@315882 | PHONE → HU | `rhmi_triggerEvent` | **23** | **Event 660** | — | after ACK 248 | FACT | CLOSED wire; MM-info role INFERENCE |
| 64 | H@81433 | HU → PHONE | `_result_rhmi_triggerEvent` | — | — | — | Event 660 ACK | FACT | CLOSED |
| 65 | P@316391 | PHONE → HU | `rhmi_setData` | **23** | Model **505** | `"Zufallswiedergabe deaktivieren"` | shuffle UI text | FACT | OPEN vs NP spine |
| 66 | P@317041 | PHONE → HU | `rhmi_setData` | **23** | Model **536** | `"EntICPlaylist"` | playlist label | FACT | SUPPORTED playlist context |
| 67 | P@317113 | PHONE → HU | `rhmi_setData` | **23** | Model **535** | table 27 rows | IC playlist (≠ NP alone) | FACT | SUPPORTED; multi-track PARTIAL |
| 68 | — | — | *(boundary)* | — | — | — | **AUDIO TRANSPORT = NOT OBSERVED** | FACT (negative) | CLOSED as NOT PROVEN (`bmw-av`) |

Full interaction JSON has **144** RHMI/AV/AM rows (71 phone + 73 HU). Rows above are the Music/AV/CDS-relevant spine; HMI Event **2** churn and non-music handles abbreviated. Machine list: `B3_RHMI_MUSIC_FORENSIC_TIMELINE_CORE.json`.

---

## 2. Handle-23 Spur (isoliert)

### 2.1 Creation / resource / initialize

| Step | Wire FACT | XML / file | Interpretation |
|------|-----------|------------|----------------|
| create pkg `…music` @P@83527 → result **23** @H@52642 | FACT | — | Handle 23 = Music app session |
| check DESCRIPTION/TEXTDB/IMAGEDB @P@84259/84856/89109 → all **true** | FACT | DESCRIPTION file MD5 matches extract | Cache hit; no upload |
| **0×** `rhmi_setResource` (whole capture, all handles) | FACT | Lifecycle desk doc allows set on false | B3-only: true ⇒ no set |
| `rhmi_initialize` @P@91943 + empty `_result_` | FACT | — | Ready for handlers/UI |
| handlers action/hmi wildcard `-1`, ident=`…music` | FACT | — | Phone receives all H23 actions/events |

**Session checkResource count:** **11** phone checks / **11** HU `true` (handles 21–25 DESCRIPTION/TEXTDB/IMAGEDB mix). H23 subset = 3.

### 2.2 HMI events (handle 23)

| eventId | count (H23) | Wire | Semantics |
|--------:|------------:|------|-----------|
| 2 | 7–8 | FACT comps + args | UNKNOWN/OPEN (focus/visibility churn) |
| 11 | 1 | FACT comp=10 `{23:true}` | INFERENCE: Visible on toolbarHmiState (XML id 10) |
| 1 | 1 | FACT comp=10 `{4:true}` | INFERENCE: Focus (desk); not proven by wire alone |

### 2.3 Actions / models / events on H23

See §§3–9. All Music NP strings in this capture are `rhmi_setData` on **handle 23** (FACT).

---

## 3. Action 336 — jede Instanz

| Inst | HU onAction | Payload | Phone ACK | confirmId/success | Immediate neighbors (FACT offsets) |
|-----:|------------:|---------|-----------|-------------------|------------------------------------|
| #1 | H@**60714** | `{}` | P@**102266** | 1 / true | HMI ev2 comps 70/84/102/114; then `av_create` @102700 |
| #2 | H@**73825** | `{}` | P@**134438** | 1 / true | Near `av_requestConnection` @134074; artist refine 445 |
| #3 | H@**77751** | `{}` | P@**204105** | 1 / true | After PLAY @202150; after trigger 661 @203763 |

**Wire FACT:** Action **336** observed **3×** HU→Phone + **3×** Phone→HU ack (`success=true`). No objectId/modelId in action args. ident=`me.hufman.androidautoidrive.music`.

**XML EVIDENCE:** `entryButton` 145/656 → `action="335"` → `combinedAction id="335"` → nested `raAction id="336"`.

**INFERENCE:** 336 ≃ Music **entry** RA path (plugin entry), not Play/Pause.

**UNKNOWN:** HU-side Home/Launcher **objectId** / entry identifier on the action wire — **NOT OBSERVED**.

**Do not claim:** “336 is the Home button” as FACT.

---

## 4. Action 248

| Field | Value | Level |
|-------|-------|-------|
| HU onAction | H@**79424** | FACT |
| Payload | `{99: false}` | FACT |
| ACK | P@**315513** success=true confirmId=1 | FACT |
| Before | HMI 11+1 on comp 10; post-PLAY Spotify/661/444 path | FACT order |
| After | triggerEvent **660** @315882; setData 505/536/535 | FACT |
| XML | toolbar button id=49 `selectAction="248"` tooltipModel=495; wire 495=`"Apps"` | XML + FACT string |
| Semantik | Apps/toolbar select | **INFERENCE** |
| Meaning of key **99** | — | **UNKNOWN** |

---

## 5. Model mini-traces

### Model 444

| | |
|--|--|
| Wire FACT | `"Spotify"` @P@**204670** (after PLAY + 661) |
| XML | `audioHmiState` `textModel="444"` (provider) |
| Interpretation | NP provider/source model | INFERENCE role; FACT value |
| NP vs other | NP-facing after PLAY | FACT timing |

### Model 445

| | |
|--|--|
| Wire FACT | `"Halestorm, I Prevail"` @112791 → `"Halestorm"` @133872, @345020 |
| XML | `artistTextModel="445"` |
| Interpretation | Artist model | INFERENCE role; FACT values |

### Model 446 / 447

| | |
|--|--|
| Wire FACT | Both set to `"can u see me in the dark?"` (446 @112870; 447 @114167; later repeats) |
| XML | 446=`albumTextModel`, 447=`trackTextModel` |
| Interpretation | Title-bearing NP fields | INFERENCE |
| 446≠447 role from wire alone | **UNKNOWN** (identical strings; cannot separate album vs track from values) |

### Model 456 (Cover)

| | |
|--|--|
| Wire FACT | Etch envelope @P@**114251**; body encodes handle **23** and modelId **456** (`0x85 0x01 0xc8`); JPEG SOI @P@**114315**, len **18474**, sha256 `3df577892fcc5448…` |
| Decoder | `etch_codec.decode_etch_message` fails on value tag `0x9c` → absent from `RHMI_SETDATA_H23.jsonl` | FACT (tool gap) |
| XML | `coverImageModel="456"` |
| Interpretation | Cover image setData | **INFERENCE** strongly supported; modelId itself is **FACT** in raw bytes |
| Audit note | Prior prose sometimes cited decoded jsonl only → under-counted 456; E2E claim stands on raw encoding |

### Model 458

| | |
|--|--|
| Wire FACT | ≥6× `rhmi_setData` RHMIDataTable (PlayList), first @111986; continues through PLAY |
| XML | `playListModel="458"` modelType=PlayList |
| Interpretation | Playlist **context** table | INFERENCE |
| ≠ automatic “Now Playing row sole source” | Do not collapse 458 into NP title models | UNKNOWN finer row semantics |

### Models 653 / 654

| | |
|--|--|
| Wire FACT | 653=`"Halestorm"` @204442; 654=title @204510 (**after** Event 661 / ACK 336#3) |
| XML | `multimediaInfoEvent` 660 uses textModel1=653, textModel2=654 |
| vs Event 660 | Written ~111kB **before** trigger 660; not rewritten in the immediate pre-660 window | FACT |
| Interpretation | IC/multimedia info mirrors | INFERENCE |

### Model 655

| | |
|--|--|
| Wire FACT | `"Spotify"` @P@**203436** immediately before Event **661** |
| XML | `statusbarEvent` 661 `textModel="655"` |
| Interpretation | Statusbar provider text | INFERENCE |

### Models 535 / 536 (playlist/IC context)

| | |
|--|--|
| Wire FACT | After 248/660: 536=`"EntICPlaylist"`; 535=27-row table incl. current title + other songs |
| NP? | **Playlist/browse context**, not the NP spine 444–447 | FACT values; role INFERENCE |

---

## 6. Events 660 / 661

### Event 661

| | |
|--|--|
| Wire | P@**203763** `rhmi_triggerEvent` h=23 eventId=661; `_result_` H@78175 |
| Predecessor | setData **655**=`"Spotify"` @203436 | FACT |
| Followers | ACK 336#3; setData 653/654/444 | FACT |
| XML | statusbarEvent textModel=655 | STRONG secondary |
| User-origin? | Phone-triggered — **REJECTED** as HU `onHmiEvent` | FACT direction |

### Event 660

| | |
|--|--|
| Wire | P@**315882** after ACK 248; `_result_` H@81433 |
| XML | multimediaInfoEvent textModel1/2 = 653/654 | STRONG secondary |
| Causal to 248 | ORDERED after ACK 248 | FACT order; mediation INFERENCE |

---

## 7. AV Control Plane (getrennt)

```text
P@102700  av_create(id=…music, instanceID=14)
H@68583   _result_av_create → handle 1
P@134074  av_requestConnection(ENTERTAINMENT, h=1)
H@74749   _result_av_requestConnection
H@75048   av_requestPlayerState(PLAY)
H@75709   av_connectionGranted
P@202150  av_playerStateChanged(PLAY)          ← P@0x000315a6
H@76691   _result_av_playerStateChanged
```

**FACT:** All five control steps observed.  
**INFERENCE:** Together they form one AV entertainment session.  
**NOT implied:** audible audio / A2DP / RTP / PCM.

> **AV Player State PLAY is an observed control-plane state. It does not prove actual audio output or an observed audio transport.**

Post-PLAY bulk on BCL dest **4004** = continued Etch/RHMI fragments (**INFERENCE**); **not** proven audio.

---

## 8. RHMI ↔ AV temporal correlation (not identity)

```text
RHMI Action 336 #1  →  ACK  →  av_create
RHMI NP setData 445/446/447/456/458   (before PLAY)
RHMI Action 336 #2  ↔  av_requestConnection / grant / requestPlayerState
RHMI Action 336 #3  near PLAY
av_playerStateChanged(PLAY)  →  setData 655  →  Event 661  →  ACK 336 #3  →  444/653/654
RHMI Action 248  →  ACK  →  Event 660  →  playlist 535/536
```

Shared string `me.hufman.androidautoidrive.music` on RHMI and AV (FACT). Handles **23 ≠ 1** (FACT).  
Do **not** write “RHMI starts audio.”

---

## 9. CDS context (not RHMI track bus)

| Observation | Level |
|-------------|-------|
| Media/Radio listIndex **7→8** | FACT |
| Later `visibleContext=**50034**` | FACT |
| Near Action-336 / AV path in session order | FACT offsets / CORRELATED |
| CDS carries Spotify/Halestorm strings | **NOT OBSERVED** in targeted windows |
| CDS = RHMI track metadata bus | **NOT PROVEN** / UNKNOWN |

---

## 10. Audio transport

Searched artifacts: raw BCL/Etch bins, PLAY boundary skim, E2E status board, EXTRACTED_MEDIA (images only).

| Candidate | Result |
|-----------|--------|
| A2DP / SBC / RTP / PCM in these bins | **NOT OBSERVED** |
| Separate non-4004 audio channel | **NOT OBSERVED** |
| Operator “audio OK” for this relay capture | **UNKNOWN** (not in wire) |
| `av_playerStateChanged(PLAY)` | Control only |

**AUDIO TRANSPORT = NOT OBSERVED / UNKNOWN** (negative FACT for this capture).

---

## 11. Corrected causal Gesamtkette

JSON/timeline order **overrides** any template. Corrected:

```text
AUTH (SAS) — prior / CLOSED
 ↓
AM bootstrap
 ↓
RHMI handles 21–25 (create)
 ↓
Music Handle 23
 ↓
checkResource ×11 = TRUE   (H23: DESCRIPTION/TEXTDB/IMAGEDB)
 ↓
setResource ×0
 ↓
rhmi_initialize (h=23) + wildcard handlers
 ↓
Action 336 #1 → ACK
 ↓
av_create → AV handle 1
 ↓
RHMI Music models (pre-PLAY)
 ├─ 458 playlist table
 ├─ 445 artist = Halestorm, I Prevail → Halestorm
 ├─ 446/447 title = can u see me in the dark?
 └─ 456 cover JPEG
 ↓
Action 336 #2 → av_requestConnection → ACK 336 #2
 ↓
av_requestPlayerState(PLAY) → av_connectionGranted
 ↓
CDS visibleContext 50034   (parallel plane)
 ↓
Action 336 #3
 ↓
av_playerStateChanged(PLAY) @ P@0x315a6
 ↓
setData 655="Spotify" → Event 661 → ACK 336 #3
 ↓
setData 653/654 + 444="Spotify"
 ↓
Action 248 {99:false} → ACK → Event 660
 ↓
setData 505 / 536 / 535 (Apps/playlist context)
 ↓
AUDIO TRANSPORT = NOT OBSERVED
```

**Deviation from naive template:** NP models **precede** PLAY; Event **661** precedes Action **248**; Action 336 is **triplicated** with distinct AV coupling points.

---

## 12. Technology-Audit Abgleich (claim-by-claim)

Source: `technologies/bmw-rhmi/SHEET.md` (+ `bmw-av`).

| Claim | B3 verdict |
|-------|------------|
| RHMI = Connected-App-UI over Etch | **bestätigt** (FIELD FACT) |
| RHMI ≠ A2DP | **bestätigt** |
| RHMI ≠ USB-MSC | **unverändert / bestätigt** (architecture) |
| RHMI ≠ native iDrive UI | **bestätigt** (RHMI models vs CDS menu) |
| Uses `hmi.type`/`hmi.version`, not marketing “NBT” | **unverändert** (not re-probed here; no NBT protocol field in Music path) |
| `checkResource` uses MD5 | **bestätigt** (16 B hash field) |
| SAS whitelist SHA-256 | **unverändert** (not re-derived from Music path) |
| B3: `checkResource(true)` ⇒ no `setResource` | **bestätigt** |
| Handle 23 = Music | **bestätigt** |
| `me.hufman.androidautoidrive.music` = Music app id | **bestätigt** |
| Models 444–447 NP-relevant | **bestätigt** (values); 446 vs 447 role split **XML-only** |
| Model 456 = Cover | **bestätigt mit Präzisierung**: raw modelId+JPEG FACT; jsonl decoder gap |
| Model 458 = Playlist context | **bestätigt** |
| 653/654 = MultimediaInfo context | **bestätigt** (XML∩wire); not rewritten at Event 660 |
| Model 655 = Spotify/statusbar | **bestätigt** |
| Events 660/661 | **bestätigt** wire; XML roles INFERENCE |
| Actions 336/248 | **bestätigt** wire; entry/Apps roles INFERENCE |
| AV = session/player control ≠ audio transport | **bestätigt** |
| Audio transport not proven in B3 | **bestätigt** |
| Home/Launcher Entry Object-ID not observed | **bestätigt** |

**Gesamt:** B3 RHMI Music reconstruction **agrees** with current `bmw-rhmi` / `bmw-av` sheets. Concrete audit correction is **documentation hygiene** only:

1. Cover **456** must be cited from **raw envelope** (or fixed decoder), not only `RHMI_SETDATA_H23.jsonl`.
2. NP bind **before** PLAY must stay explicit in any lifecycle diagram.
3. Keep rejecting CSV `0x30923` as PLAY anchor.

No CONTRADICTED sheet-level architecture claims found in this pass.

---

## 13. Closure lists

### A. FIELD FACT (Wire closes)

- Handle **23** ↔ `me.hufman.androidautoidrive.music`
- Handles 21–25 package map
- 11× `checkResource` → true; **0×** `setResource`; then initialize
- DESCRIPTION MD5 `e9e31c31…` / 92085 B
- Action 336 ×3 + acks; Action 248 ×1 + ack; payloads as above
- Events 661, 660 + acks
- setData values: Spotify (655/444), Halestorm (445/653), title (446/447/654), playlist tables 458/535
- Cover JPEG tied to modelId **456** in raw Etch body
- Full AV control sequence ending PLAY @ **`P@0x315a6`**
- RHMI handle 23 ≠ AV handle 1
- AUDIO TRANSPORT **not observed** in these bins
- HOME_ENTRY_OBJECT_ID **not observed**

### B. Strong INFERENCES (Wire + XML + order)

- 336 ≃ Music entry (`entryButton`→combinedAction 335→raAction 336)
- 248 ≃ toolbar Apps selectAction
- 661 ≃ statusbarEvent; 660 ≃ multimediaInfoEvent
- 444 provider / 445 artist / 456 cover / 458 playlist roles
- AAIdrive mediates RHMI Action 336 ↔ AV session
- CDS Media/Radio → vis 50034 correlates with Music entry path (not objectId)

### C. UNKNOWN / OPEN

- Audible playback / which transport carries audio (if any under relay)
- Semantic meaning of action arg key **99**
- Exact onHmiEvent 1/2/11 semantics beyond desk maps
- Wire-only distinction album(446) vs track(447) when strings equal
- CDS as track-metadata bus
- Multi-track NP state machine beyond single Halestorm title
- Full SAS SHA-256 whitelist list
- Home/Launcher objectId

### D. REJECTED by B3

- `checkResource(true)` ⇒ upload required
- Spotify via `am_registerApp`
- Lab actionId **200** / modelId **100** as F20 Music map
- AV PLAY ⇒ proven audio transport
- CSV `0x30923` as PLAY Etch offset
- “RHMI starts audio” / RHMI = A2DP
- HOME entry object observed on action wire
- Action 336 = “Home button” as FACT

---

## 14. Sources used / not used

| Source | Role |
|--------|------|
| `INTERACTION_TIMELINE_{HU,PHONE}.json` | Primary method/id/offset index |
| `RHMI_*.json`, `AV.json`, `RHMI_SETDATA_H23.jsonl` | Payload detail |
| `raw/*.bin` | Cover 456 raw confirmation; PLAY offset |
| `ui_description_multimedia_v3.xml` | Secondary ID semantics only |
| `etch_messages_full.csv` | BCL/SAS orientation; **not** complete RHMI method catalog |
| `*.bin.txt` | **Absent** |
| `bmw-rhmi` / `bmw-av` SHEET | **Post**-wire audit check only |

---

## 15. One-line verdict

B3 proves the **RHMI Music Handle-23 UI plane** and the **AV control plane** end-to-end, with Action/Event/Model IDs closed as wire facts and XML-backed roles as inferences; **audio transport remains NOT OBSERVED**; current technology-audit sheets are **aligned**, with only cover-456 decoder/citation hygiene as a concrete doc fix.
