# PLAY Boundary Skim — after `P@0x000315a6`

```yaml
date: 2026-11-22
anchor: P@0x000315a6 av_playerStateChanged PLAY (handle 1)
parent: F20_CONNECTED_MUSIC_END_TO_END_TIMELINE.md
scope: offline skim only (not full audio RE)
```

## Question

What happens in the raw bins **immediately after** the PLAY control event, and does any of it look like audio transport?

## Method

Whole-bin Etch scan + BCL DATA scan on `phone_to_hu.bin` from `P@0x000315a6` forward; HU scan from `av_connectionGranted` region for context. No wall-clock merge.

## Immediate phone Etch after PLAY (ORDERED)

| Offset | Method | Note |
|--------|--------|------|
| `P@0x000315a6` | `av_playerStateChanged` PLAY | **anchor** |
| `P@0x0003173b` | `rhmi_setData` h=23 model **458** | NP table refresh |
| `P@0x00031a03`… | models **462/451/452** | progress/times |
| `P@0x00031aac` | model **655** `"Spotify"` | |
| `P@0x00031bf3` | `rhmi_triggerEvent` **661** | |
| `P@0x00031d49` | `rhmi_ackActionEvent` 336 #3 | |
| `P@0x00031f7e` | model **444** `"Spotify"` | |
| `P@0x00031fc0` | model **442** (image resource) | |
| … | artist/title mirrors | same Halestorm track |
| `P@0x00032784` | large Etch `payload_len=66488` | RHMI-shaped header (`setData`-like); spans many BCL 4000 frames on **dest 4004** |

**FACT:** No further `av_*` method after PLAY in this capture.

## Bulk traffic classification

After PLAY, phone shows many BCL DATA frames `src=0x11 dest=0x0fa4 (4004)` with `len=4000` whose payload head is **not** `DEADBEEF` — these are **fragment continuations** of large Etch bodies already started (same pattern as certificate/cover fragmentation).

| Claim | Level |
|-------|-------|
| Bulk bytes exist after PLAY on BCL/Etch port 4004 | **FACT** |
| Those bulk bytes are RHMI `setData`/image fragments (same channel as Music UI) | **INFERENCE** (header/hash pattern + prior JPEG/PNG models) |
| Those bulk bytes are PCM / A2DP / iAP audio | **NOT PROVEN** |
| A separate non-4004 audio channel appears in these two raw bins | **NOT OBSERVED** |

## Case mapping (user hypothesis)

| Case | Fit to this skim |
|------|------------------|
| 1 — much data after PLAY | **Partial:** yes bulk, but on Etch/4004 UI path |
| 2 — nothing new / no audio | **Partial for audio:** no audio-typed stream; UI continues |
| 3 — audio on other transport | **Still OPEN** — these bins are BCL/Etch-only relay captures |

**TCP-bridge-too-slow** remains **UNKNOWN** (not supported or rejected by this skim).

## Lab logs that can be overlaid (not same session)

| Lab / Field artifact | What it adds | Overlay value |
|----------------------|--------------|---------------|
| `LAB_MUSIC_NP_SPINE_SEQ_DUAL_20261121T133709Z` | setData 444–447, actions 336/248, events 660/661 | Control/UI only — **no** `av_playerStateChanged` |
| `LAB_A2DP_BCL_CORR_20261113T2353Z.jsonl` | parallel A2DP transport state + HU edge samples | **Pattern** for dual-plane logging |
| `LAB_AVRCP_*` | AVRCP UUID probe | eligibility only; no F20 metadata |
| `FIELD_B2A_TX_CH*_AUDIOOK_*` | other field gate with TX/audio-ok label | **different session** — cannot prove B3 audio path |
| idrivesim Music NP lab PASS | stub UI without AV PLAY | Lab gap vs Field PLAY anchor |

**Conclusion:** Existing lab logs **cannot** close the B3 audio gap by overlay alone. They **do** justify lab improvements: always record A2DP/transport plane beside BCL when Music PLAY is under test.

## Lab improvements derived

1. **Dual-plane capture checklist** for every Music lab/field run: BCL/Etch JSONL **and** BlueZ A2DP transport state (or explicit “A2DP absent”).
2. **iDriveSim:** stub `av_create` → `requestConnection` → `connectionGranted` → `playerStateChanged(PLAY)` after Action 336 (Field order), without claiming audible audio.
3. **PiDrive:** treat Etch PLAY as **control-plane** only; audible path remains UNKNOWN until dual-plane evidence.
4. Next offline deep-dive: decode/reassemble Etch body at `P@0x00032784` (confirm modelId/image vs other) — still not audio unless proven otherwise.
5. Next field test: audible PLAY attempt with dual-plane log; Track A→B secondary.

## Status

```text
PLAY @ P@0x000315a6     OBSERVED (control)
post-PLAY Etch/UI       OBSERVED
post-PLAY bulk on 4004  OBSERVED (RHMI-fragment INFERENCE)
audio transport         NOT PROVEN
audible playback        NOT OBSERVED
```
