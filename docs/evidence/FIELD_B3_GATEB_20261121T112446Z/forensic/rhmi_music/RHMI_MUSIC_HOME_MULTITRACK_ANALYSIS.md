# RHMI Music — Home Entry + Multi-Track State Machine

```yaml
date: 2026-11-22
parent: RHMI_MUSIC_UI_STATE_MACHINE.md
prior: RHMI_MUSIC_INTERACTION_AV_HOME_ANALYSIS.md (617ff8e)
scope: Home/Menu → Action 336 → Handle 23; multi-track / playlist state machine
primary: raw/phone_to_hu.bin (P@) + raw/hu_to_phone.bin (H@)
scan_artifact: HOME_MULTITRACK_SCAN.json
xml_cross_check: resources/ui_description_multimedia_v3.xml (secondary only)
```

Epistemic tags: **FACT** | **INFERENCE** | **HYPOTHESIS** | **UNKNOWN** | **REJECTED**.

---

## 1. Scope

Close two remaining Music edges without reopening CLOSED wire facts:

1. Home/Menu → Music Entry → Action 336 → Handle 23 (object-ID hunt + menu path).
2. Multi-track state machine beyond the Halestorm Now-Playing spine.

**Not re-analyzed (CLOSED, used as facts only):** RHMI create; Handle-23 Object/Data map; Models 444/445/446/447/456/458/655; Action 248/336 wire; Event 660/661 wire; base RHMI↔AV order.

**No product code** in this run — state model only.

---

## 2. Ausgangsstand / bereits CLOSED

| Item | Status | Source |
|------|--------|--------|
| Handle 23 = `me.hufman.androidautoidrive.music` | FACT | UI state machine |
| NP models 444/445/446/447/456/458/655 | FACT map | UI state machine |
| Action 336 wire (`onActionEvent` ×3, empty args, ack) | FACT | Interaction report |
| Action 248 wire (`args={99:false}`) | FACT | Interaction report |
| Event 661 after `setData(655="Spotify")` | FACT | Interaction report |
| Event 660 after ack 248 | FACT | Interaction report |
| `Action 336 → av_create → av_requestConnection → … → setData/661` | FACT order | Interaction report |
| Home entry Object-ID | was OPEN / NOT FOUND | Interaction report |

---

## 3. Home/Menu Entry Analyse

### 3.1 RHMI-Seite (A1)

Handle-23 bootstrap (phone→HU) remains:

| Step | Offset | Method | FACT |
|------|-------:|--------|------|
| create | P@83527 | `rhmi_create` | music package |
| checkResource ×3 | P@84259…89109 | DESCRIPTION/TEXTDB/IMAGEDB | MD5s unchanged |
| initialize | P@91943 | `rhmi_initialize` | handle 23 |
| addActionEventHandler | P@93000 | wildcard `actionId=-1` | |
| addHmiEventHandler | P@93531 | handle 23 | |

No new `rhmi_create` / resource / handler evidence that names a Home-entry **objectId**. Action payloads for 336 still carry only:

```text
handle=23, actionId=336, ident=me.hufman.androidautoidrive.music, args={}
```

**FACT.** No Object-ID, Resource-ID, or modelId appears inside `rhmi_onActionEvent` for 336.

### 3.2 Home/Launcher-Semantik (A2)

String/payload sweep of both bins for Home/Launcher/Menu/Media/Music/entry/tile/335/336:

| Hit class | Result | Level |
|-----------|--------|-------|
| Exact `"Home"` / `"Launcher"` as RHMI object label on wire | not observed as entry object | FACT (absence) |
| CDS `hmi.graphicalContext` | **observed** — see below | FACT |
| `"Media/Radio"` menuTitle | H@64021, H@69376, H@77422 | FACT |
| `visibleContext` **20** → **50034** | after 3rd Action 336 | FACT |
| Action IDs 336/248 on wire | already CLOSED | FACT |
| `combinedAction` / `entryButton` string on wire | not present | FACT |
| XML `entryButton id="145"|"656" action="335"` | DESCRIPTION only | XML CORROBORATION |

**CDS `hmi.graphicalContext` unique values (21 events, 3 unique):**

| H@ | menuTitle | visibleContext | listIndex | widgetType |
|---:|-----------|---------------:|----------:|------------|
| 64021 (+copies) | `"Media/Radio"` | 20 | 7 | `LT_Button_1Row_1CheckLeft_1IconLeft` |
| 69376 | `"Media/Radio"` | 20 | 8 | same |
| 78538 (+copies) | `""` | **50034** | 0 | `GFXIDENTIFIER_INVALID` |

**INFERENCE.** HU navigates native Media/Radio list (listIndex 7→8), then after Action 336 path the graphical context switches to RHMI context **50034** (empty menuTitle). This is the strongest Home/Menu→Music Entry correlation in this capture — still **without** an RHMI entry Object-ID on the action wire.

### 3.3 Negativbefund (A4)

```text
HOME_ENTRY_OBJECT_ID = NOT OBSERVED
```

Classification:

| Possibility | Verdict |
|-------------|---------|
| Present in capture but not decodable | **REJECTED** for action 336 — Etch decode succeeds; `args={}` |
| Present but not safely assignable to Music Entry | N/A — no candidate objectId on 336 |
| Not present in capture | **FACT** |

---

## 4. Action-336-Origin

| Claim | Level |
|-------|-------|
| Triggered as `rhmi_onActionEvent` handle=23, actionId=336, args={} | **FACT** |
| Object X field on wire that fires 336 | **NOT OBSERVED** |
| XML: `raAction 336` ⊂ `combinedAction 335`; `entryButton` 145/656 → action 335 | **XML CORROBORATION** only |
| “336 is the Music entry button object” | remains **INFERENCE** (wire+XML), not FACT |
| CDS Media/Radio listIndex + later visibleContext 50034 near 336 | **FACT** offsets; causal UI semantics **INFERENCE** |

Wire origin for PiDrive/idrivesim:

```text
(unknown native/RHMI control)
        │
        ▼
rhmi_onActionEvent {handle:23, actionId:336, args:{}}   H@60714 / 73825 / 77751
        │
        ▼
rhmi_ackActionEvent {success:true, confirmId:1}         P@102266 / 134438 / 204105
```

---

## 5. Handle-23 Entry Correlation

Causal entry spine (duplex, offset-labeled):

```text
H@60714  onActionEvent 336          ─┐
H@64021  CDS Media/Radio list=7      │  (menu still native)
H@69376  CDS Media/Radio list=8      │
H@73825  onActionEvent 336          ─┤
H@75048  av_requestPlayerState PLAY  │
H@75709  av_connectionGranted        │
H@77422  CDS Media/Radio list=8      │
H@77751  onActionEvent 336          ─┤
H@78538  CDS visibleContext=50034   ─┘  ← RHMI context visible
H@79424  onActionEvent 248 (Apps)

P@83527  rhmi_create music → handle 23   (earlier than HU 336 in absolute P@,
                                          but session bootstrap; see §9 timing note)
P@93000  addActionEventHandler
P@102266 ack 336 #1
P@102700 av_create
P@112791 setData 445 "Halestorm, I Prevail"
P@112870 setData 446 title
P@114251 setData 456 JPEG cover
P@134074 av_requestConnection ENTERTAINMENT
P@134438 ack 336 #2
P@202150 av_playerStateChanged PLAY
P@203436 setData 655 "Spotify"
P@203763 triggerEvent 661
P@204105 ack 336 #3
P@204670 setData 444 "Spotify"
```

**FACT.** Every Action 336 targets handle **23**.  
**FACT.** RHMI Music UI population (445/446/447/456/458…) occurs on the same handle after the 336/AV path.  
**UNKNOWN.** Wall-clock sync between P@ and H@ (independent raw files; no shared timestamp field). Ordering above is **causal / message-id paired**, not absolute interleaving.

---

## 6. Track-State-Timeline

### 6.1 Observed music data (B1)

| Kind | Observed values | Level |
|------|-----------------|-------|
| Now-Playing artist | `"Halestorm, I Prevail"` → later `"Halestorm"` | FACT |
| Now-Playing title | `"can u see me in the dark?"` only | FACT |
| Provider | `"Spotify"` on 444 and 655 (each set once) | FACT |
| Cover JPEG (model 456) | P@114315, 18474 B, SHA-256 `3df577892fcc5448…` | FACT |
| Alt images | model **441** JPEG 18126 B sha `ed46591f…` @P@318539; model **453** JPEG 7353 B sha `7d729a00…` @P@336750 | FACT |
| Playlist (model **535** EntICPlaylist) | 27 rows incl. Halestorm current + titles Kryptonite, Rebel Yell, **Pink Floyd Cover**, … | FACT |
| Second distinct NP track (I Prevail album as new title, Pink Floyd as NP, etc.) | **not observed** | FACT (absence) |

**REJECTED.** Assumption that Pink Floyd / I Prevail appear as separate Now-Playing track states in this capture. Pink Floyd string is a **playlist row title** inside model 535, not models 445/446/447.

### 6.2 Chronological NP states (B2)

Only **one** Now-Playing track identity. Observable transitions are **refinement / surface sync**, not Track A→B:

| T | Phase | Offset | Method | Model / note |
|---|-------|-------:|--------|--------------|
| T0 | Entry Action 336 | H@60714 | onActionEvent | action=336 |
| T1 | AV create | P@102700 | av_create | handle later 1 |
| T2 | First NP texts | P@112791–114167 | setData | 445 full artist, 446/447 title, 458 table |
| T3 | Cover | P@114251 / jpeg@114315 | setData 456 | JPEG 18474 B |
| T4 | AV requestConnection | P@134074 | av_requestConnection | ENTERTAINMENT |
| T5 | Artist shortened | P@133872 | setData 445 | `"Halestorm"` (prev had feat.) |
| T6 | AV PLAY | P@202150 | av_playerStateChanged | PLAY |
| T7 | Provider + Event 661 | P@203436–203763 | setData 655; triggerEvent 661 | `"Spotify"` |
| T8 | Status models | P@204442–204670 | setData | 653/654/540/444 |
| T9 | Action 248 path | H@79424 → P@315513 ack | | |
| T10 | Event 660 + IC playlist | P@315882–317113 | triggerEvent 660; setData 536/535 | playlist dump |
| T11 | Progress refresh | P@344611–345787 | setData | times 2:32/3:58; 445/446/447/458 same track |

**No T-track-B** with a different title on 446/447.

---

## 7. Model-Change-Matrix

Comparing NP spine across the session (Track A only; Track B/C = not observed):

| Model | Initial NP | Later refresh | Playlist/IC path | Verhalten |
|------:|------------|---------------|------------------|-----------|
| 444 | — | `"Spotify"` once @204670 | not set again | gesetzt einmal; konstant |
| 445 | `"Halestorm, I Prevail"` @112791 | `"Halestorm"` @133872, @345020 | — | **geändert** (feat. stripped), then same value re-set |
| 446 | title @112870 | same title @133932, @345088 | — | **erneut gesetzt, gleicher Wert** |
| 447 | title @114167 | same @135450, @345787 | — | **erneut gesetzt, gleicher Wert** |
| 456 | JPEG `3df57789…` @114251 | later envelopes @135526/@345871 (decode/partial) | separate 441/453 images | Cover **einmal** als volles JPEG belegt; **kein** zweites NP-Cover für anderen Track |
| 458 | table @111986 (3 rows) | re-set @113544,133072,134827,202555,345164 | — | **erneut gesetzt**; row1 gains title string; not a new track list |
| 655 | `"Spotify"` @203436 | **not** re-set on later refresh | — | konstant nach einmaligem Set + Event 661 |
| 535 | — | — | full playlist @317113 | IC playlist, not NP model |
| 536 | — | — | `"EntICPlaylist"` @317041 | use-case string |

**Answers to explicit questions:**

- **444 Spotify constant?** Yes after first set — never overwritten with another provider (**FACT**).
- **655 Spotify on track change?** No second set observed; Event 661 only once (**FACT**).
- **445/446/447 sync?** Often adjacent in time; 445 can update independently (artist shorten) (**FACT**).
- **456 every track change?** No second NP track; only one proven full JPEG for 456 (**FACT**).
- **458 only initial?** Re-pushed multiple times with same track identity (**FACT**).

---

## 8. Event-660/661 State Correlation

Wire semantics remain CLOSED. State-machine role in this capture:

| Event | Observed trigger chain | Role |
|------:|------------------------|------|
| **661** | `setData(655="Spotify")` → `triggerEvent 661` → later 444/653/654 | **once**, after AV PLAY — statusbar/provider push (**FACT** order; XML statusbar = CORROBORATION) |
| **660** | ack Action **248** → `triggerEvent 660` → shuffle texts → `setData 535` playlist | **once**, Apps/browse path — not on NP title change (**FACT** order) |

**No** additional 660/661 on artist shorten or progress refresh.

```text
setData(655) ──► Event 661     (provider/statusbar path)
Action 248   ──► Event 660     (multimediaInfo / IC playlist path)
Track title change ──► (not observed) ──► no extra 660/661
```

---

## 9. AV Correlation

| Question | Answer | Level |
|----------|--------|-------|
| AV on every track change? | **No** — only session setup + one PLAY | FACT |
| AV only at Music session build? | **Yes** in this capture | FACT |
| `av_playerStateChanged` on track change? | Only one PLAY @P@202150; no track-B | FACT |
| `av_requestPlayerState`? | HU→Phone @H@75048 (PLAY) | FACT |
| AV explains Track A→B? | N/A — no Track B | — |

Observed AV-only timeline:

| Offset | Dir | Method |
|-------:|-----|--------|
| P@102700 | P→H | `av_create` |
| H@75048 | H→P | `av_requestPlayerState` PLAY |
| H@75709 | H→P | `av_connectionGranted` |
| P@134074 | P→H | `av_requestConnection` ENTERTAINMENT |
| P@202150 | P→H | `av_playerStateChanged` PLAY |

Derived pattern for this capture:

```text
Action 336 (entry)
    ↓
AV create / requestConnection / connectionGranted / PLAY
    ↓
MUSIC_ACTIVE (RHMI setData + Event 661)
    ↓
(progress / list refresh without new AV)
```

**REJECTED** for this capture: “AV fires per track change.”  
**UNKNOWN** globally: whether a real Track B would emit AV — not testable here.

---

## 10. CDS Correlation

| Property | Observation | Music SM role |
|----------|-------------|---------------|
| `hmi.graphicalContext` | Media/Radio → visibleContext 50034 | **Entry/menu path** FACT |
| `entertainment.multimedia` | placeholder `title:"NowPlayingTrack"` / empty; `source` 34→0 | **not** artist/title carrier |
| Other CDS ×155 | mostly unrelated HMI churn | not Music NP |

```text
CDS_MUSIC_CORRELATION = NOT PROVEN   # for track/artist/title/playlist/playback
CDS_MENU_ENTRY_CORRELATION = FACT    # Media/Radio + visibleContext 50034 near Action 336
```

**REJECTED:** “CDS steuert den Trackwechsel” (no trackwechsel; multimedia property empty).

---

## 11. Multi-Track State Machine

Derived from capture (template filled; Track B absent):

```text
NATIVE_MENU (CDS Media/Radio, vis=20)
  │  listIndex 7 → 8
  │  Action 336 ×1..3  (objectId NOT OBSERVED)
  ▼
MUSIC_ENTRY (handle 23)
  │  av_create / requestConnection / connectionGranted
  ▼
MUSIC_CONNECTING
  │  av_playerStateChanged PLAY
  ▼
MUSIC_ACTIVE / TRACK_A
  │  setData 445/446/447/456/458
  │  setData 655 "Spotify" → Event 661
  │  setData 444 "Spotify"
  │
  ├── ARTIST_REFINE  (445 "…, I Prevail" → "Halestorm")
  ├── PROGRESS_SYNC  (451/452/462/440 times; 458 re-push)
  ├── APPS_PATH      (Action 248 → Event 660 → model 535 playlist)
  └── TRACK_B        ✗ NOT OBSERVED
```

**MULTI_TRACK_STATE_MACHINE = PARTIAL (single NP track + multi-row IC playlist).**

---

## 12. FACT / INFERENCE / HYPOTHESIS / UNKNOWN / REJECTED

### New FACTs

- `HOME_ENTRY_OBJECT_ID = NOT OBSERVED` (action 336 `args={}`, no objectId field).
- CDS `menuTitle="Media/Radio"`, `listIndex` 7→8, then `visibleContext=50034` after Action 336 path.
- Only one NP title string on 446/447 for entire capture.
- Artist string shortens once on model 445.
- Model 535 EntICPlaylist carries 27 rows including Pink Floyd Cover **as playlist text**, not NP.
- Models 441/453 receive distinct JPEGs (IC/other surfaces), hashes ≠ 456 cover.
- 444 and 655 each set to `"Spotify"` once; 655 not refreshed later.
- AV methods appear only in session setup + one PLAY — not paired with title changes.
- Event 661 once (after 655); Event 660 once (after 248).

### New INFERENCES

- Media/Radio list selection is the native prelude to RHMI Music context 50034.
- Action 336 remains the Music **entry** trigger (unchanged from prior INFERENCE+XML).
- Playlist model 535 is populated on Apps/IC path after 248/660, not as NP Track B.

### HYPOTHESIS

- listIndex 8 row in Media/Radio corresponds to the AAIdrive/Spotify entry tile (not proven by objectId).
- visibleContext 50034 is the multimedia RHMI application context id on this HU.

### UNKNOWN

- Concrete RHMI/native Object-ID that owns Action 336.
- Inter-file wall-clock alignment of P@ vs H@.
- Wire behavior for a true Track A→B transition (needs new capture).
- Whether 441/453 images are alternate album art scales or unrelated UI chrome.

### REJECTED (this capture)

- Pink Floyd / multi-artist strings as Now-Playing Track B/C.
- CDS `entertainment.multimedia` as the Music metadata bus.
- AV per-track-change driver.
- Elevating XML-only “336 = entryButton” to FACT.

---

## 13. Negativbefunde

| ID | Status |
|----|--------|
| HOME_ENTRY_OBJECT_ID | **NOT OBSERVED** |
| TRACK_B_NP_STATE | **NOT OBSERVED** |
| TRACK_C_NP_STATE | **NOT OBSERVED** |
| AV_PER_TRACK | **NOT OBSERVED** |
| CDS_TRACK_METADATA | **NOT PROVEN** |

---

## 14. Konsequenzen für PiDrive

Do **not** implement yet. Required future Music state surface (wire-evidenced fields only):

```text
PiDrive Music State
├── provider          # 444 / 655 "Spotify"
├── artist            # 445 (+ mirrors 653/479/488…)
├── title             # 446 / 447 / 654 / …
├── cover             # 456 JPEG (and possibly 441/453 variants)
├── playlist          # 458 NP-adjacent table + 535 EntICPlaylist
├── progress          # 451/452/462/440
├── playbackState     # AV PLAY (session-level evidence)
└── actions           # respond to 336 (entry), 248 (Apps); emit 661/660 as observed
```

Mapping:

```text
PiDrive State
   ↓
RHMI setData(handle=23, modelId=…)
   ↓
triggerEvent 661 (after provider) / 660 (after Apps path)
   ↓
AV create/requestConnection/PLAY  (session, not per title in this capture)
```

Missing for closed product logic: real Track-B capture; entry Object-ID still absent (may remain HU-native).

---

## 15. Konsequenzen für iDriveSim

- Must accept Action 336 with empty args on music handle.
- Must tolerate missing entry objectId.
- Should simulate CDS `hmi.graphicalContext` Media/Radio → 50034 if menu fidelity matters.
- Multi-track UI: can stub playlist 535; must not invent NP Track B without evidence.
- AV: session PLAY once is enough to match this field shape.

---

## 16. Verbleibende offene Punkte

1. New field capture with explicit next-track / different album to close Track A→B.
2. Whether entry Object-ID ever appears on another action/property channel (still absent here).
3. Decode/role of image models 441/453 vs 456.
4. Wall-clock merge of the two raw files (if a sidecar timestamp ever exists).

---

## 17. Kombiniertes Ablaufdiagramm (P@ / H@ File-Positionen)

Die beiden Rohdateien sind **getrennte Richtungsstreams** ohne gemeinsames Wire-Timestamp-Feld. Das Diagramm ist daher eine **kausale Merged-Timeline** mit absoluten Offsets je Datei. Paare Action↔Ack folgen `_messageId` / Reihenfolge aus dem Interaction-Bericht.

```text
═══════════════════════════════════════════════════════════════════════════
 COMBINED MUSIC FLOW — phone_to_hu.bin = P@   |   hu_to_phone.bin = H@
═══════════════════════════════════════════════════════════════════════════

 [BOOTSTRAP — Phone]
 P@83527  rhmi_create music
 P@84259  rhmi_checkResource DESCRIPTION
 P@84856  rhmi_checkResource TEXTDB
 P@89109  rhmi_checkResource IMAGEDB
 P@91943  rhmi_initialize h=23
 P@93000  rhmi_addActionEventHandler h=23
 P@93531  rhmi_addHmiEventHandler h=23
 P@94099… setData resource/icon seeds …

 [NATIVE MENU — HU]
 H@35926  CDS entertainment.multimedia placeholder (source=34)
 H@60714  rhmi_onActionEvent action=336 h=23 args={}     ← ENTRY #1
 H@64021  CDS hmi.graphicalContext menu="Media/Radio" vis=20 list=7
 H@69376  CDS … Media/Radio vis=20 list=8
 H@73825  rhmi_onActionEvent action=336                  ← ENTRY #2
 H@75048  av_requestPlayerState PLAY h=1
 H@75377  CDS entertainment.multimedia cleared (source=0)
 H@75709  av_connectionGranted h=1
 H@77422  CDS Media/Radio vis=20 list=8
 H@77751  rhmi_onActionEvent action=336                  ← ENTRY #3
 H@78538  CDS hmi.graphicalContext vis=50034             ← RHMI context
 H@79424  rhmi_onActionEvent action=248 args={99:false}  ← Apps

 [PHONE FOLLOWS ENTRY / AV / NP]
 P@102266 rhmi_ackActionEvent 336 #1
 P@102700 av_create
 P@108747 setData 499 "Aktuelle Wiedergabe" …
 P@111986 setData 458 playlist-ish table (3 rows)
 P@112791 setData 445 "Halestorm, I Prevail"             ← TRACK_A artist
 P@112870 setData 446 "can u see me in the dark?"        ← TRACK_A title
 P@114167 setData 447 same title
 P@114251 setData 456 JPEG                               ← cover
          jpeg payload @P@114315 len=18474
          sha256=3df577892fcc5448b7d816ed515cc0ad2dcdb2e4f5db96781fbf98469eedca3c
 P@133872 setData 445 "Halestorm"                        ← artist refine
 P@134074 av_requestConnection ENTERTAINMENT
 P@134438 rhmi_ackActionEvent 336 #2
 P@202150 av_playerStateChanged PLAY
 P@203436 setData 655 "Spotify"
 P@203763 rhmi_triggerEvent 661
 P@204105 rhmi_ackActionEvent 336 #3
 P@204442 setData 653 "Halestorm"
 P@204510 setData 654 title
 P@204670 setData 444 "Spotify"
 P@206376… mirror artist/title models 488/479/480…

 [APPS / IC PLAYLIST — after 248]
 P@315513 rhmi_ackActionEvent 248
 P@315882 rhmi_triggerEvent 660
 P@317041 setData 536 "EntICPlaylist"
 P@317113 setData 535 table (27 rows; Pink Floyd Cover = row text)
 P@318539 setData 441 JPEG 18126 B sha=ed46591f603d6389…
 P@336750 setData 453 JPEG  7353 B sha=7d729a001251108b…

 [PROGRESS / SAME TRACK REFRESH]
 P@344611 setData 492/482 "  2:32"
 P@345020 setData 445 "Halestorm"
 P@345088 setData 446 title
 P@345164 setData 458
 P@345787 setData 447 title

 [NOT PRESENT]
 ✗ HOME_ENTRY_OBJECT_ID on any 336 payload
 ✗ Second NP title (Track B)
 ✗ AV replay per title change
 ✗ CDS artist/title driving RHMI models
═══════════════════════════════════════════════════════════════════════════
```

Machine-readable companion: `HOME_MULTITRACK_SCAN.json`.

---

## 18. Status board

| ID | Status |
|----|--------|
| HOME_ENTRY_OBJECT_ID | **NOT OBSERVED** |
| MULTI_TRACK_STATE_MACHINE | **PARTIAL** — single NP track + IC playlist multi-row |
| AV_TRACK_CORRELATION | **SESSION_ONLY** (not per track) |
| CDS_MUSIC_CORRELATION | **NOT PROVEN** (track); menu entry path **FACT** |
| Next analysis | Field capture with explicit next/prev track **or** alternate album NP; optional 441/453 image-role decode |
| E2E index | [`../F20_CONNECTED_MUSIC_END_TO_END_TIMELINE.md`](../F20_CONNECTED_MUSIC_END_TO_END_TIMELINE.md) |
