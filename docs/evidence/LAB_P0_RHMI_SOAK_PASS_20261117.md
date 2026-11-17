# LAB P0 — RHMI Soak PASS (10 min + Actions)

**claim_level:** LAB FACT  
**run:** `LAB_P0_RHMI_SOAK_DUAL_20261117T213102Z`  
**commit context:** EAGAIN retry (`ffd28aa`) + RHMI soak harness

## Verdict

**PASS.** Dual-ESP Connected session held **~604 s** at `RUNTIME_ACTIVE` with phased RHMI traffic and no session abort.

| Phase | Result |
|-------|--------|
| 0–1 min stabilize | PASS |
| 1–3 min setData repeat | PASS · models 100/101 (`PiDrive` / Apps / …) |
| 3–5 min multi-model + setProperty | PASS |
| 5–7 min Actions | PASS · HU TX + phone RX + `rhmi_ackActionEvent` |
| 7–10 min mixed | PASS |

## Counts (this window)

| Signal | N |
|--------|--:|
| soak `setData` | 97 |
| soak `setProperty` | 21 |
| HU `rhmi_action_tx` | 105 |
| phone action RX / ACK | 105 / 105 |
| EAGAIN recovered | 2 |
| fatal HU close mid-soak | 0 (terminal `eof` at phone end only) |
| ServiceException | 1 (bootstrap modelId 4 / 213 — known, non-fatal) |
| ESP bootGen bump | 0 |

## Success criteria (met)

10 min + mehrere RHMI-Ops + Actions + kein Session-Abbruch → **Labpfad produktfähig genug für ersten gezielten F20-Versuch** (noch Lab-HU/`f20_sim`, nicht Field-Car).

## Next

1. ~~**P1:** minimale UI-Sequenz~~ → **PASS** see `LAB_P0_RHMI_PIDRIVE_SEQ_PASS_20261117.md`.  
2. **P1:** modelId 4 / 213 separat.  
3. **P2:** EAGAIN-Histogramm.  
4. **P3:** kontrollierter F20-Feldversuch.
