# Music NP Spine — Lab Stub Plan (frozen) 2026-11-21

```yaml
status: LAB PROOF PASS
lab_evidence: docs/evidence/LAB_MUSIC_NP_SPINE_SEQ_DUAL_20261121T133709Z/
bt_stack: CLOSED — do not widen
handoff: Reverse Engineering → PiDrive implementation (after one F20 proof)
upstream:
  - BT_CONTROL_PLANE_CLOSED_20261121.md
  - FIELD_B3_GATEB_…/resources/HANDLE23_CORRELATION.md
tools:
  - tools/lab_music_np_spine_seq.py
  - PhoneClientSession.tick_rhmi_music_np_seq (bcl_dummy_hu.py)
  - BCL_RHMI_MUSIC_NP_SEQ=1 / --rhmi-music-np-seq
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

### Lab result 2026-11-21T133709Z — **PASS**

Evidence: [`LAB_MUSIC_NP_SPINE_SEQ_DUAL_20261121T133709Z`](../evidence/LAB_MUSIC_NP_SPINE_SEQ_DUAL_20261121T133709Z/)

| Check | OK |
|-------|----|
| RUNTIME_ACTIVE / hold ≥45s | yes |
| setData 444–447 | yes |
| triggerEvent 660·661 | yes |
| action TX/RX/ack 336·248 | yes |
| sink `MUSIC_NP_SPINE` | yes |

First attempt (133537Z) failed: 92 KiB DESCRIPTION `setResource` → RFCOMM `TimeoutError`. Fixed via cache-hit + digest seed.

## How to run (lab)

```bash
# Host unit test (no BT)
PYTHONPATH=tools python3 -m unittest tests.host.test_music_np_spine_seq -v

# Dual-ESP hold on .108 (needs lab host + ESP up)
python3 tools/lab_music_np_spine_seq.py --hold 60
```

Env / flags: `BCL_RHMI_MUSIC_NP_SEQ=1` or `--rhmi-music-np-seq`.  
DESCRIPTION: Field-matched `ui_description_multimedia_v3.xml` (auto-deployed to `/tmp/bcl_dummy/`).  
Lab uses **`BCL_RHMI_CACHE_HIT=1`** + seeded `rhmi_digests.txt` (SHA-256) so the 92 KiB DESCRIPTION is not RFCOMM-uploaded (avoids phone `TimeoutError`).  
Mutually exclusive with `BCL_RHMI_PIDRIVE_SEQ` / soak.

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
