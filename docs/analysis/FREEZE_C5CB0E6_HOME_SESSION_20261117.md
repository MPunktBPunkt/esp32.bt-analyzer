# Freeze — c5cb0e6 Home Session (2026-11-17)

**commit:** `c5cb0e6`  
**claim_level:** LAB STATE FREEZE (not a new wire claim)

## Frozen verdicts

| Area | Status |
|------|--------|
| Pairing | **PASS** |
| AAIdrive | **PASS** |
| Spotify A2DP | **PASS** |
| CDS | **PASS** |
| RHMI (phone path) | **PASS** |
| AVRCP (CONT3–13 windows) | **PASS** |
| W0 Fall A — „HU erzeugt keinen Reply“ | **REJECTED** |
| Alias-Race (`BT-Analyzer-.87` loop) | **IDENTIFIED + FIXED** (infra) |
| ESP panics | **OPEN** (P0) |
| RFCOMM flaps | **OPEN** (P0) |
| checkResource return path (field/W0 miss) | **not finally explained** |

## What this is / is not

```
c5cb0e6
│
├─ Connected/Home Session:       PASS
├─ Peer/Alias Race:              FIXED   ← infrastructure, not RHMI protocol insight
├─ W0 "HU sends no reply":       REJECTED
│
├─ ESP stability:                OPEN    ← P0
├─ RFCOMM stability:             OPEN    ← P0
└─ checkResource return path:    PASS in lab after EAGAIN-retry (`ffd28aa` + `LAB_P0_RHMI_LIFECYCLE_PASS_20261117`)
                                 — field miss may still be transport; lab Fall A remains REJECTED
```

- Home session shows the real phone path works through CDS/RHMI.
- Alias fix (`system-alias` loop kill + bridge `--local-name`) must stay classified as **infra**, not as Connected/RHMI protocol knowledge.
- Prefer **not** re-interpreting F20 `WATCHDOG_MISS_NO_ETCH_REPLY` until ESP/RFCOMM flaps are deterministically correlated.

## Preferred next explanation class

```
TX checkResource
        ↓
HU answers (lab W0: reply seen)
        ↓
RFCOMM/ESP loses session or frame   ← candidate
        ↓
Etch sees incomplete / no reply
        ↓
WATCHDOG_MISS_NO_ETCH_REPLY
```

## P0 — deterministic capture

Per flap/panic correlate at minimum:

- ESP `resetReason` / `bootGen` / uptime / heap / `hciAgent.drops`
- panic/backtrace if available
- RFCOMM channel / close `reason` (`write_error:11`, `eof`, …)
- BT Connected / ACL state
- BCL `session_id`
- last TX / last RX / nearby `etch_data_tx` / `msg_id` if present
- reconnect → new handshake/session?

Hypothesis fork:

1. **Panic/disconnect before missing reply** → transport candidate for prior W0 miss  
2. **RFCOMM stable, only Etch reply vanishes** → go deeper into BCL/Etch

Tool: `tools/lab_esp_rfcomm_flap_correlate.py`  
Evidence: `docs/evidence/LAB_P0_ESP_RFCOMM_20261117.md` (+ CONT8/GREEN/RECOVER/LIVE JSON)

### First P0 offline read (recover jsonl)

28 flaps · `eof`×19 · `write_error:11`×9 · dominant classes `eof_rehandshake` / `tx_pressure_during_etch_reply`.  
`write_error:11` often mid-`etch_reply` TX burst → **transport/TX-pressure candidate**, not Fall A.  
ESP `resetReason=panic` reflects prior boot (`bootGen=24`); not every flap is a fresh panic.

## References

- Rollup: `docs/evidence/LAB_HOME_SESSION_REPORT_20261117.md`
- Alias fix: `docs/evidence/LAB_HOME_CONT12_20261117T1930Z.md`
- W0 Fall A reject: `docs/evidence/LAB_W0_20261117T1701Z.md`
