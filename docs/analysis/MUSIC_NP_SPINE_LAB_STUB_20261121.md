# Music NP Spine — Lab Stub Plan (frozen) 2026-11-21

```yaml
status: PLAN FROZEN
bt_stack: CLOSED — do not widen
handoff: Reverse Engineering → PiDrive implementation (after one F20 proof)
upstream:
  - BT_CONTROL_PLANE_CLOSED_20261121.md
  - FIELD_B3_GATEB_…/resources/HANDLE23_CORRELATION.md
```

## Bridge (FACT)

```
AAIdrive Source XML (643 unique IDs)
        │  Schnittmenge
        ▼
B3 FIELD Handle 23  (…music)
        ├── 78/78 Models
        ├── 20/20 Components
        ├── Action 336 · 248
        └── Event 660 · 661
```

## Lab stub — smallest NP spine only

Do **not** port the full Music tree. Stub only:

| ID | Role |
|---:|------|
| **444** | source / app / media (`Spotify`) |
| **445** | artist |
| **446** / **447** | title |
| **660** | `multimediaInfo` event |
| **661** | `statusbar` event |
| **336** | action (ack path) |
| **248** | action (ack path) |

Optional later (not in first lab proof): 451/452 time, 440/462 progress, 458 playlist.

## Lab proof chain

```
initialize
   ↓
setData(444…)
setData(445…)
setData(446…)
setData(447…)
   ↓
HU renders NP state
   ↓
Action 336 / 248
   ↓
Event handling (660 / 661)
```

Pass criteria (lab): stub session reaches visible NP-equivalent state on `f20_sim` / iDriveSim without BT-stack changes.

## Single F20 field trial (only after lab stable)

One variable. Question is **not** “does Bluetooth work?”

> Which of the real Music-RHMI Model/Action/Event definitions are **sufficient** for a foreign/own RHMI client on the F20 to produce a **visible and interactive** UI state?

## Explicit non-goals

- No further Bluetooth Classic / BCL / Etch / SAS research  
- No general technology-audit  
- No DESCRIPTION reassembly  
- No TEXTDB/IMAGEDB required for this first stub  
- No Standalone-Signer as blocker  

## After field answer

Schwerpunkt endgültig: **PiDrive-Implementierung** (Weg A template), nicht weiteres Wire-RE.
