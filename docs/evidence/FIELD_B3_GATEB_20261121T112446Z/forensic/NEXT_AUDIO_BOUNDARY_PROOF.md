# Next Proof — Audio Boundary (accepted framing 2026-11-22)

```yaml
date: 2026-11-22
anchor: P@0x000315a6
parents:
  - F20_CONNECTED_MUSIC_END_TO_END_TIMELINE.md
  - PLAY_BOUNDARY_SKIM_20261122.md
role: experiment cut — not more RHMI RE
```

## Why the lab overlay still mattered

Other sessions are **not** B3-identical. They still deliver:

1. **Protocol signatures** — typical control-plane shape around Music PLAY.
2. **Transport-correlation pattern** — what must be logged in parallel next time (`LAB_A2DP_BCL_CORR_*`).
3. **Negativ against misread** — post-PLAY bulk on dest **4004** must **not** be auto-classified as audio (RHMI-fragment INFERENCE).

> “Much traffic after PLAY” ≠ evidence for or against an audio plane.

## Status board (control vs audio)

| Area | Status |
|------|--------|
| RHMI Music NP | FACT (lab + field) |
| AV control path | FACT (field) |
| PLAY @ `P@0x000315a6` | FACT |
| Traffic after PLAY | FACT |
| Bulk on 4004 = RHMI fragments | INFERENCE |
| Dual-plane lab pattern | FACT (other context) |
| B3 audio from other sessions | UNKNOWN (not transferable) |
| Audio transport in B3 | NOT PROVEN |
| Audible playback | NOT OBSERVED |
| Cause of no sound (bridge / missing PLAY audio / HU backend) | UNKNOWN — not separated yet |

## Architecture hypothesis (not FACT)

```text
4004  →  RHMI / Etch / Control
???   →  Audio   (HYPOTHESIS until same-run dual-plane proof)
```

## Priority (locked)

| P | Focus |
|---|-------|
| **P0** | Audio boundary: PLAY @ `0x315a6` → first audio-transport evidence (or proven absence) |
| **P1** | Identify transport (channel / protocol / direction / packet shape) — name only after evidence |
| **P2** | Transport present ≠ HU emits sound (backend / focus) |
| **P3** | Track A→B (does change re-init audio or only metadata?) |
| **P4** | Home Entry Object-ID |

## Minimal next field protocol

```text
T0  Capture START (dual-plane + shared monotonic clock)
T1  Music Entry
T2  Spotify / artist / title / cover visible
T3  PLAY
T4  wait 10–20 s
T5  observe audio-transport plane
T6  STOP / controlled next state
```

Planes (minimum):

```text
Etch/BCL   Phone ──P@/H@──► HU     (control; PLAY timestamp)
Audio?     Phone ──frames──► ?     (unknown until observed)
```

Success criterion example:

```text
PLAY @ t=123.456   (control plane)
first audio frame @ t=123.52 …
```

or equally valuable:

```text
PLAY @ t=…
audio plane: no frames in ±N s   → absence FACT for that capture setup
```

## Do not do next

- More RHMI-only deep dives as the primary workstream
- Home Entry / Track A→B ahead of dual-plane PLAY
- Claim “TCP bridge too slow” without separating missing transport vs slow transport vs HU backend
