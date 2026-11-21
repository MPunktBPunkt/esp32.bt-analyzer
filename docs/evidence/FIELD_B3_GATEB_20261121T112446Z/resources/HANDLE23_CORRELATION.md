# Handle 23 — ID correlation (first cut) 2026-11-21

```yaml
handle: 23
appId: me.hufman.androidautoidrive.music
description: ui_description_multimedia_v3.xml
claim_level: FIELD + DESK (intersection)
machine: HANDLE23_CORRELATION.json
```

## Method

1. Parse DESCRIPTION → 643 unique numeric `id=`  
2. ETCH-magic scan of `raw/phone_to_hu.bin` (BCL stream framer fails on multi-session concat; live `b3.jsonl` has only truncated `hex_head`)  
3. Keep messages with `handle==23`  
4. Intersect modelId / componentId with XML  

## Reduction

| Pool | Count |
|------|------:|
| XML numeric IDs | 643 |
| H23 unique `modelId` in Field | **78** (all in XML) |
| H23 unique `componentId` in Field | **20** (all in XML) |
| H23 `actionId` observed | **2** (`336`, `248`) |
| H23 `eventId` observed | **2** (`661`, `660`) |

→ ~907/643 → **~100 field-touched IDs**; PoC spine is smaller still.

## Now Playing spine (`audioHmiState` id=24)

| Role (XML attr) | modelId | XML tag | Field sample |
|-----------------|--------:|---------|--------------|
| provider / textModel | 444 | raDataModel | `Spotify` |
| artistTextModel | 445 | raDataModel | `Halestorm, I Prevail` |
| albumTextModel | 446 | raDataModel | track/album text |
| trackTextModel | 447 | raDataModel | `can u see me in the dark?` |
| currentTimeModel | 451 | raDataModel | `  2:32` |
| elapsingTimeModel | 452 | raDataModel | `  3:58` |
| playbackProgressModel | 462 | raDataModel (FloatingPoint) | `0.63` |
| Progress gauge | 440 | raGaugeModel | int 63 |
| playListModel | 458 | raListModel (PlayList) | RHMIDataTable |
| coverImageModel (XML) | 456 | (not in H23 setData this capture) | — |
| artist/album image models | 454/455 | imageIdModel hits via other IDs | — |

Cover path: component image **27** → model **441** (`raImageModel`); image **38** → **453**. Property toggles on toolbar buttons 51–54, 646–647.

## Actions / Events (H23)

| Kind | ID | XML |
|------|---:|-----|
| `rhmi_ackActionEvent` | 336 | `raAction` inside `combinedAction` 335 |
| `rhmi_ackActionEvent` | 248 | `raAction` |
| `rhmi_triggerEvent` | 661 | `statusbarEvent` textModel=655 (`Spotify`) |
| `rhmi_triggerEvent` | 660 | `multimediaInfoEvent` textModel1=653 / textModel2=654 (artist/title) |

Handlers registered: `rhmi_addActionEventHandler` + `rhmi_addHmiEventHandler` with `ident=me.hufman.androidautoidrive.music`, wildcard ids `-1`.

## modelId type mix (H23)

| XML tag | n |
|---------|--:|
| raDataModel | 39 |
| imageIdModel | 23 |
| raIntModel | 7 |
| textIdModel | 3 |
| raImageModel | 3 |
| raListModel | 2 |
| raGaugeModel | 1 |

## Minimal PoC — FROZEN for lab stub

Plan: [`MUSIC_NP_SPINE_LAB_STUB_20261121.md`](../../../analysis/MUSIC_NP_SPINE_LAB_STUB_20261121.md)

| ID | Role |
|---:|------|
| 444 | source/app/media |
| 445 | artist |
| 446 / 447 | title |
| 660 | multimediaInfo event |
| 661 | statusbar event |
| 336 | action |
| 248 | action |

Defer: 451/452/440/462/458. Full machine list: `HANDLE23_CORRELATION.json`.

## Epistemic

- Raw magic-scan can count **above** live `b3.jsonl` method histogram (105× `setData`) — multiple sessions in the bin. Handle assignment 21–25 matches Addendum.  
- Intersection 78/78 and 20/20 = **STRONG** that Field Music UI ≡ this DESCRIPTION tree.  
- Minimal PoC set = **INFERENCE** until lab/field stub reproduces NP on F20.
