# RHMI Music — Action / Event / Home / AV Graph

```yaml
date: 2026-11-22
parent: RHMI_MUSIC_UI_STATE_MACHINE.md
scope: open edges only (Actions 248/336, Events 660/661, Home entry, RHMI↔AV, CDS windows)
primary: raw/phone_to_hu.bin + raw/hu_to_phone.bin
xml_cross_check: resources/ui_description_multimedia_v3.xml (secondary only)
```

NP Object/Data map (444/445/446/447/456/458/655) remains **CLOSED** in the parent report — not re-derived here.

---

## A. Action Map

### Action **336**

| Field | Value | Level |
|-------|-------|-------|
| Context | RHMI handle **23**, `ident=me.hufman.androidautoidrive.music` | **FACT** |
| Direction | HU→Phone `rhmi_onActionEvent` (×3) → Phone→HU `rhmi_ackActionEvent` (×3, `success=true`, `confirmId=1`) | **FACT** |
| Wire args | `{}` (empty) on all three | **FACT** |
| Object/modelId on wire | none in action payload | **FACT** |
| Handler registration | wildcard `rhmi_addActionEventHandler` actionId=**-1** @ phone 93000 | **FACT** |
| Object binding (wire-only) | **UNKNOWN** | |
| XML cross-check | `raAction id="336"` inside `combinedAction id="335"`; `entryButton id="145"` and `id="656"` use `action="335"` | **STRONG** (secondary) |
| Semantik | **INFERENCE:** RA-Teil der Music-**Entry**-`combinedAction` 335 (Plugin-Entry), nicht NP-Play/Pause | |
| Folgeoperationen (zeitlich) | siehe Paare unten | **FACT** offsets / **INFERENCE** Kausalität |

| Pair | HU `onActionEvent` | Phone `ack` | Immediate phone follow-up (FACT offsets) |
|-----:|-------------------:|------------:|------------------------------------------|
| 0 | 60714 | 102266 | `av_create` @102700 (`…music`); later NP `setData` 445/446/447/458… |
| 1 | 73825 | 134438 | near `av_requestConnection` @134074; more list/title `setData` |
| 2 | 77751 | 204105 | after `av_playerStateChanged(PLAY)` @202150; then 653/654/444 updates |

Near pair0: HU `onHmiEvent` eventId=**2** on components 70/84/102/114.  
Near pair2: HU `onHmiEvent` eventId=**11** componentId=**10** (`args={23:true}`) and eventId=**1** componentId=**10** — component **10** = XML `toolbarHmiState` (**STRONG** secondary).

---

### Action **248**

| Field | Value | Level |
|-------|-------|-------|
| Context | handle **23**, music ident | **FACT** |
| Direction | HU→Phone `onActionEvent` ×1 @79424 → Phone `ack` @315513 | **FACT** |
| Wire args | `{99: false}` | **FACT** |
| Object/modelId on wire | none | **FACT** |
| XML cross-check | `button id="49"` in `toolbarHmiState id="10"`: `selectAction="248"`, `tooltipModel="495"` (wire tooltip text **"Apps"** on model 495) | **STRONG** |
| Semantik | **INFERENCE:** Toolbar-**Apps**-Select (nicht Spotify-Play) | |
| Folge | `rhmi_triggerEvent` **660** @315882; `setData` 505 shuffle text; `setData` 535/536 `EntICPlaylist` table | **FACT** |

---

## B. Event Map

### Event **661**

| Field | Value | Level |
|-------|-------|-------|
| Direction | Phone→HU `rhmi_triggerEvent` @203763, handle 23, `args={0:null}` | **FACT** |
| Preceding setData | modelId **655** = `"Spotify"` @203436 | **FACT** |
| Following setData | 653 artist, 654 title, **444** `"Spotify"` | **FACT** |
| XML | `statusbarEvent id="661" textModel="655"` | **STRONG** |
| Semantik | **INFERENCE:** Statusbar-Push mit Provider-Text Spotify nach AV PLAY | |
| User interaction? | **REJECTED** as user-origin — phone-triggered, not `onHmiEvent` | |

### Event **660**

| Field | Value | Level |
|-------|-------|-------|
| Direction | Phone→HU `rhmi_triggerEvent` @315882 | **FACT** |
| Context | Immediately after ack **248**; before shuffle/`EntICPlaylist` updates | **FACT** |
| XML | `multimediaInfoEvent id="660" textModel1="653" textModel2="654"` | **STRONG** |
| Semantik | **INFERENCE:** Multimedia-Info-Event (IC/cluster texts 653/654); fired on Apps/browse path after 248 | |
| Note | 653/654 were last written ~@204442–204510 (earlier PLAY path), not in the 8 KiB window before 660 | **FACT** |

### Other HMI events (handle 23) — not 660/661

| eventId | Direction | Notes | Level |
|--------:|-----------|-------|-------|
| 2 | HU→Phone | many; components 24,70,84,… — focus/visibility churn | **FACT** ids; semantics **OPEN** |
| 1, 11 | HU→Phone | on `componentId=10` (toolbar state) near action 248 | **FACT**; semantics **OPEN** |

---

## C. Home / Music Entry

### Searched (FACT)

- Raw ASCII/UTF-8 both bins: `Home`, `Launcher`, `Media`, `Musik`, `tile`, `widget`, `menu`, `Multimedia`, `Connected`, `Apps`, `EntIC*`
- Methods: `am_registerApp`, `am_create`, `am_addAppEventHandler`, `rhmi_create/initialize`, action/hmi events
- Hits: **Apps** (models 495/464/511), **EntICPlaylist** (536); **no** `Home`/`Launcher`/`Musik` menu strings
- Music **not** in five `am_registerApp` entries (**FACT**, prior)
- `am_addAppEventHandler(ident=…music)` @101787 — app-event hook, not a home tile (**FACT**)

### Verdict

| Claim | Level |
|-------|-------|
| BMW **HOME_ENTRY** widget ID on wire | **OPEN / NOT FOUND** |
| Music reachable via RHMI entry path | **INFERENCE:** Action **336** ↔ XML `entryButton`→`combinedAction 335`→`raAction 336` |
| Spotify AM home tile | **REJECTED** |

`HOME_ENTRY = OPEN` for a concrete home/launcher object. Closest closed edge: **Music Entry ≃ Action 336** (wire + DESCRIPTION entryButton).

---

## D. RHMI ↔ AV Correlation

### Sequence (FACT — two streams; order by mid/session logic + listed offsets)

```text
HU  onActionEvent(336)           @60714
PH  ackActionEvent(336)          @102266
PH  av_create(…music, inst=14)   @102700
HU  _result_av_create → handle 1 @68583
    … NP setData 445/446/447/456/458 …
HU  onActionEvent(336)           @73825
PH  av_requestConnection(ENT)    @134074
PH  ack(336)                     @134438
HU  _result_av_requestConnection @74749
HU  av_requestPlayerState(PLAY)  @75048
HU  av_connectionGranted         @75709
HU  onActionEvent(336)           @77751
PH  av_playerStateChanged(PLAY)  @202150
HU  _result_av_playerStateChanged@76691
PH  setData 655="Spotify"        @203436
PH  triggerEvent 661             @203763
PH  ack(336)                     @204105
PH  setData 653/654/444          @204442+
```

### Direction (FACT / INFERENCE)

```text
RHMI Action 336 (HU user/entry)
        ↓
AAIdrive
        ├── ackAction
        ├── av_create / requestConnection / playerStateChanged
        └── later rhmi_setData + triggerEvent 661
        ↓
HU AV grant + requestPlayerState
```

- AV is **not** the byte-source of 444/445/446/447/456 — those are `rhmi_setData` from the phone (**FACT**).
- AV PLAY and RHMI Spotify/NP updates are **session-coupled** via AAIdrive (**INFERENCE** causality; **FACT** ordering).
- Shared identity string: `me.hufman.androidautoidrive.music` on RHMI create/handlers and `av_create` (**FACT**).
- RHMI handle **23** ≠ AV handle **1** (**FACT**).

---

## E. Dynamic State Machine

Only **one** media item observed in this capture:

| Phase | Evidence |
|-------|----------|
| NP bind | 445=`Halestorm, I Prevail`, 446/447=title, 458 playlist, cover 456 |
| Refine | 445→`Halestorm` (shortened) |
| After AV PLAY | 655/444=`Spotify`, 653/654 artist/title, times 451/452, progress 462 |
| After Action 248 | 505 shuffle text change; 535 EntICPlaylist table |

**Pink Floyd:** not present in these raw bins (**FACT** — `find` miss).  
**Track A→B→C:** **OPEN** / not observable here (single title).

---

## F. CDS Correlation (targeted)

Windows ±2 KiB around onAction 336/248 and AV grant:

| Window | Notable CDS | Assessment |
|--------|-------------|------------|
| AV grant / requestPlayerState | `entertainment.multimedia` (×2) | **INFERENCE:** media-context property; not decoded further |
| onAction 336 #3 / 248 | `hmi.graphicalContext` (×3) | **INFERENCE:** HMI context churn with UI focus |
| Other | sunroof, battery, GPS, parkingBrake, time, … | **NO_CORRELATION** to Music IDs (noise) |

No CDS property carries Spotify/Halestorm strings in these windows.  
**Music-specific CDS semantics:** not closed beyond timing flags above.

---

## G. Final Graph (evidence-backed)

```text
BMW HOME / Launcher
        │
        │  HOME_ENTRY object ………… OPEN / NOT FOUND on wire
        ▼
MUSIC ENTRY  (INFERENCE ≃ Action 336 / XML entryButton→combinedAction 335)
        │
        ▼
RHMI HANDLE 23  (FACT …music)
   │
   ├── 444 Spotify          (FACT)
   ├── 445 Artist           (FACT)
   ├── 446 Title            (FACT)
   ├── 447 Title/NP         (FACT)
   ├── 456 Cover JPEG       (FACT)
   ├── 458 Playlist         (FACT)
   ├── 655 Statusbar text   (FACT)
   │
   ├── Action 336  ← HU onAction / PH ack
   │      │          INFERENCE: entry combinedAction RA
   │      └──► av_create → requestConnection → PLAY
   │               └──► setData 655/444 + trigger 661
   │
   ├── Action 248  ← HU onAction(args 99=false) / PH ack
   │      │          INFERENCE: toolbar Apps selectAction
   │      └──► trigger 660 → shuffle/EntICPlaylist setData
   │
   ├── Event 661  PH trigger  (INFERENCE: statusbarEvent)
   └── Event 660  PH trigger  (INFERENCE: multimediaInfoEvent)
              │
              ▼
         AV handle 1  (FACT id=…music)
              │
              ▼
         PlayerState PLAY  (FACT)
```

---

## Closure status

| Edge | Status |
|------|--------|
| Action 336 wire lifecycle | **CLOSED** (FACT) |
| Action 336 semantic (entry) | **INFERENCE** (+ XML STRONG) |
| Action 248 wire lifecycle | **CLOSED** (FACT) |
| Action 248 semantic (Apps select) | **INFERENCE** (+ XML STRONG) |
| Event 661 wire + Spotify 655 | **CLOSED** (FACT); statusbar role **INFERENCE**/XML STRONG |
| Event 660 wire after 248 | **CLOSED** (FACT); multimediaInfo role **INFERENCE**/XML STRONG |
| Home entry object | **OPEN / NOT FOUND** |
| RHMI↔AV coupling | **CLOSED** as ordered FACT graph; mediation **INFERENCE** |
| Multi-track state machine | **OPEN** (single track) |
| CDS music properties | **partial** (`entertainment.multimedia`, `hmi.graphicalContext` timing only) |

---

## Artifacts

- `INTERACTION_TIMELINE_PHONE.json` / `INTERACTION_TIMELINE_HU.json` (prior extract helpers)
- Parent: `RHMI_MUSIC_UI_STATE_MACHINE.md`
