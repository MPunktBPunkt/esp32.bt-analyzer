# RHMI Music / Spotify UI — wire reconstruction (FIELD_B3_GATEB)

**Primary source:** `raw/phone_to_hu.bin`, `raw/hu_to_phone.bin` (DEADBEEF envelope scan + `etch_codec.decode_etch_message`).  
**Artifacts:** `RHMI_MUSIC_GRAPH.json`, `RHMI_SETDATA_CATALOG.jsonl`, `STRING_TO_RHMI.json` (this directory).  
**Raw bins:** not mutated.

Epistemic tags: **FACT** = decoded from wire; **INFERENCE** = interpretation; **OPEN** = unresolved.

---

## 0. Framing

**FACT.** BCL DATA frames use an 8-byte big-endian header `(cmd, src, dest, len)`. Each Etch message is a `DEADBEEF | u32BE(body_len) | body` envelope **inside** the BCL payload. There is no second 8-byte header before `DEADBEEF` outside BCL.

**FACT.** Large BCL DATA payloads can contain **multiple** complete Etch envelopes back-to-back. A BCL-only reassembler that consumes one envelope per DATA start under-counts (missed e.g. `av_playerStateChanged@202150`, `setData modelId=655 "Spotify"@203436`). This report uses a whole-bin DEADBEEF envelope scan as primary.

**FACT.** Scan totals: 442 phone→HU + 619 HU→phone = **1061** successfully decoded envelopes (26 phone-side length/body rejects).

---

## 1. Package → handle map

**FACT.** `rhmi_create` / `_result_rhmi_create` pairs:

| package | handle | create `_messageId` | create off (phone) | result off (HU) |
|---------|-------:|--------------------:|-------------------:|----------------:|
| `me.hufman.androidautoidrive.calendar` | 21 | 1795260933223 | 82515 | 52368 |
| `me.hufman.androidautoidrive.notification.readout` | 22 | 1795260933223† | 82699 | 52438 |
| **`me.hufman.androidautoidrive.music`** | **23** | **1795260933254** | **83527** | **52642** |
| `me.hufman.androidautoidrive.mapview` | 24 | 1795260933272 | 83705 | 52724 |
| `io.bimmergestalt.idriveconnectaddons.screenmirror` | 25 | 1795260933690 | 92612 | 56242 |

† **FACT.** Calendar and notification.readout reused the same `_messageId` (1795260933223); pairing is by chronological create/result order for that id.

Later session recreates calendar/notification/mapview with the same handles (21/22/24); **music was not re-created** in the second wave.

**FACT.** Music RHMI handle = **23**.

---

## 2. Resources / initialize (handle 23)

**FACT.** Phone → HU:

| method | type | size | MD5 (hash field) | name | off |
|--------|------|-----:|------------------|------|----:|
| `rhmi_checkResource` | DESCRIPTION | 92085 | `e9e31c31110680e13b7a112a7d77eb55` | `""` | 84259 |
| `rhmi_checkResource` | TEXTDB | 393 | `1a1f84fb6bf6504db2494dd274a72efc` | `""` | 84856 |
| `rhmi_checkResource` | IMAGEDB | 162483 | `0b010109a0fd4f3c7aced4fd0b4dcbd9` | `""` | 89109 |
| `rhmi_initialize` | — | — | — | — | 91943 |

**FACT.** All three `_result_rhmi_checkResource` return `result=True` (resource already present on HU). No `rhmi_setResource` for handle 23 in this capture. `_result_rhmi_initialize` is an empty ack (no `result` field).

**INFERENCE.** Empty `name` + check-only means AAIDRIVE relied on prior/cached multimedia DESCRIPTION assets rather than uploading in this session.

**FACT (prior extract).** DESCRIPTION MD5 `e9e31c31…` = `resources/ui_description_multimedia_v3.xml` (see `resources/EXTRACT.md`) — Wire∩file **CLOSED**.

---

## 3. Handlers (handle 23)

**FACT.**

- `rhmi_addActionEventHandler` — `handle=23`, `ident="me.hufman.androidautoidrive.music"`, `actionId=-1` (wildcard), off 93000.
- `rhmi_addHmiEventHandler` — `handle=23`, same `ident`, `eventId=-1` (wildcard), off 93531.
- Both `_result_*` acks present on HU→phone.

---

## 4. ID catalog (handle 23)

**FACT.** Counts from wire `rhmi_setData` / `rhmi_setProperty` / action-hmi traffic:

| class | count | values (abbrev) |
|-------|------:|-----------------|
| `modelId` (setData) | **78** | 168…658 (see graph) |
| nested / other data `id`s | 95 | modelIds ∪ table-cell ids |
| `componentId` (setProperty) | **20** | 27, 38, 51–54, 60, 69–73, 82, 84, 94, 100, 102, 112, 114, 646, 647 |
| `propertyId` | **8** | 1 ENABLED, 2 SELECTABLE, 3 VISIBLE, 4 VALID, 6 LIST_COLUMNWIDTH, 9 WIDTH, 22 BOOKMARKABLE, 37 CUTTYPE |
| `actionId` | **2** | 248, 336 |
| `eventId` | **5** | 1, 2, 11 (onHmiEvent); 660, 661 (triggerEvent) |
| **node+data+property IDs** | **123** | model ∪ data ∪ component ∪ property |
| **all UI ids** (+action/event) | **128** | |

**FACT.** `rhmi_setData` on handle 23: **117** messages (see `RHMI_SETDATA_CATALOG.jsonl`).  
**FACT.** `rhmi_setProperty` on handle 23: **38** messages; values live in field `values` (map, typically key `"0"`).

---

## 5. String → RHMI correlation

All targets found as UTF-8 inside handle-23 `rhmi_setData` envelopes:

| string | modelId(s) | method | notes |
|--------|------------|--------|-------|
| **Spotify** | **655**, **444** | `rhmi_setData` | offs 203436 (655), 204670 (444) |
| Halestorm / “Halestorm, I Prevail” | 445, 653, 488, 479, 535 | `rhmi_setData` | artist / info / list rows |
| I Prevail | 445 (inside “Halestorm, I Prevail”) | `rhmi_setData` | |
| can u see me | 446, 447, 458, 654, 540, 480, 481, 490, 535, … | `rhmi_setData` | full text `can u see me in the dark?` |
| Zufallswiedergabe | 505, 472 | `rhmi_setData` | “… nicht verfügbar” then “… deaktivieren” |

**FACT — Spotify.** Two wire hits, both handle 23 / `rhmi_setData`:
1. `modelId=655` value `"Spotify"` @ phone off 203436 (statusbar path; precedes `rhmi_triggerEvent` 661 @ 203763).
2. `modelId=444` value `"Spotify"` @ phone off 204670 (now-playing provider/text model).

**INFERENCE (secondary cross-check only).** `HANDLE23_CORRELATION.md` / XML map 444→provider, 655→statusbarEvent textModel; wire values agree. Treat XML roles as **INFERENCE** until DESCRIPTION hash is verified.

---

## 6. Actions / HMI events (handle 23)

**FACT — HU → phone (`on*`):**

| method | id | count (approx) | meaning (INFERENCE) |
|--------|---:|---------------:|---------------------|
| `rhmi_onActionEvent` | actionId **336** | 3 | focus/select on combinedAction spine |
| `rhmi_onActionEvent` | actionId **248** | 1 | secondary action (browse/entry) |
| `rhmi_onHmiEvent` | eventId **2** | 8 | focus/visibility churn |
| `rhmi_onHmiEvent` | eventId **11** | 1 | — |
| `rhmi_onHmiEvent` | eventId **1** | 1 | — |

**FACT — phone → HU:**

| method | id | offs |
|--------|---:|------|
| `rhmi_ackActionEvent` | 336 | 102266, 134438, 204105 |
| `rhmi_ackActionEvent` | 248 | 315513 |
| `rhmi_triggerEvent` | **661** | 203763 (after statusbar Spotify 655) |
| `rhmi_triggerEvent` | **660** | 315882 (after multimediaInfo 653/654 updates) |

**OPEN.** Exact semantics of onHmiEvent 1/2/11 without DESCRIPTION event table binding on wire.

---

## 7. AV ↔ music instance

**FACT.**

| step | method | key fields | off |
|------|--------|------------|----:|
| create | `av_create` | `instanceID=14`, `id="me.hufman.androidautoidrive.music"` | 102700 |
| create result | `_result_av_create` | `result=1` → **AV handle 1** | 68583 |
| request | `av_requestConnection` | handle=1, ENTERTAINMENT | 134074 |
| granted | `av_connectionGranted` | handle=1 | 75709 |
| HU asks state | `av_requestPlayerState` | PLAY | 75048 |
| phone reports | `av_playerStateChanged` | handle=1, PLAY | 202150 |
| ack | `_result_av_playerStateChanged` | inReplyTo create’s player msg | 76691 |

**FACT.** AV handle **1** ≠ RHMI handle **23**; correlation is by shared package string `me.hufman.androidautoidrive.music`.

**INFERENCE.** Now-playing setData burst (Spotify/Halestorm/progress) is gated on AV PLAY + connectionGranted.

---

## 8. UI state machine (wire timeline)

Offsets are phone→HU unless noted.

```
[CREATE] rhmi_create music → handle 23
    ↓
[RESOURCE] checkResource DESCRIPTION/TEXTDB/IMAGEDB → all True
    ↓
[INIT] rhmi_initialize + wildcard action/hmi handlers (ident=music pkg)
    ↓
[STATE: SHELL] setData icons/labels (Apps, Durchsuchen, …); setProperty list layout
    ↓
[AV CREATE] av_create(id=music) → av_handle 1
    ↓
[STATE: NP_BIND] populate artist/title/list (445/446/458…); cover/image models
    ↓  (HU: onActionEvent 336, onHmiEvent 2*)
[AV CONNECT] requestConnection → connectionGranted; requestPlayerState PLAY
    ↓
[STATE: PLAYING] playerStateChanged(PLAY)
                 setData 655="Spotify" → triggerEvent 661
                 setData 444="Spotify", 653/654 artist/title, 462=0.63, 451/452 times
    ↓
[STATE: BROWSE/SHUFFLE] ackAction 248; list 535 EntICPlaylist;
                        setData 505="Zufallswiedergabe deaktivieren";
                        triggerEvent 660
```

**INFERENCE — now-playing spine (wire values + secondary XML roles):**

| modelId | wire sample | role (INFERENCE / secondary) |
|--------:|-------------|------------------------------|
| 444 | Spotify | provider / app |
| 445 | Halestorm[, I Prevail] | artist |
| 444 | Spotify | XML `audioHmiState@24 textModel` |
| 445 | Halestorm… | XML `artistTextModel` |
| 446 | can u see me… | XML `albumTextModel` (wire often = title string) |
| 447 | can u see me… | XML `trackTextModel` |
| 451 / 452 | `2:32` / `3:58` | XML `currentTimeModel` / `elapsingTimeModel` |
| 462 | `0.63` | XML `playbackProgressModel` |
| 458 | RHMIDataTable | XML `playListModel` |
| **456** | JPEG 18442 B @ etch≈0x1BE4B | XML **`coverImageModel`** — **FACT** cover |
| 454 / 455 | PNG | artist/album image models |
| 653 / 654 | Halestorm / title | XML multimediaInfoEvent 660 |
| 655 | Spotify | XML statusbarEvent 661 textModel |
| 505 | Zufallswiedergabe… | shuffle control label |

---

## 9. Secondary cross-check (after wire)

Sources: `resources/HANDLE23_CORRELATION.md` + `.json`, `ui_description_multimedia_v3.xml` — **not** used to invent IDs.

| claim | wire | secondary | verdict |
|-------|------|-----------|---------|
| handle 23 = music pkg | FACT | same | agree |
| 78 unique modelIds | FACT (envelope scan) | 78 | agree |
| 20 componentIds | FACT | 20 | agree |
| actionIds 248, 336 | FACT | same | agree |
| Spotify @ 444 | FACT | provider model | agree |
| Spotify @ 655 | FACT | statusbar textModel | agree |
| track on 447 vs 446 | both carry title string on wire | XML splits album/track | **OPEN** which attribute is authoritative when both set |

---

## 10. Top OPEN questions

1. **Why no `rhmi_setResource`?** Cached HU assets vs earlier uncaptured upload.
2. **onHmiEvent 1 / 2 / 11:** Component binding not proven from envelopes alone.
3. **446 vs 447:** Both get the same title string on wire while XML splits album/track — which attribute wins when identical?
4. **Duplicate `_messageId` on create:** Calendar + notification share 1795260933223.
5. **26 undecodable DEADBEEF hits** on phone bin (fragments / JPEG false magics).
6. **PropertyId→widget** beyond the 8 decoded enums (ENABLED/VISIBLE/…): full component tree for every control.

---

## 11. Return metrics (this pass)

| metric | value |
|--------|------:|
| Report path | `docs/evidence/FIELD_B3_GATEB_20261121T112446Z/forensic/rhmi_music/RHMI_MUSIC_UI_STATE_MACHINE.md` |
| Music RHMI handle | **23** |
| `rhmi_setData` on handle 23 | **117** |
| Distinct modelIds | **78** |
| Distinct componentIds | **20** |
| Distinct propertyIds | **8** |
| Node+data+property IDs | **123** |
| Spotify correlation | **FACT:** `setData` handle 23, modelIds **655** and **444**, value `"Spotify"` |
