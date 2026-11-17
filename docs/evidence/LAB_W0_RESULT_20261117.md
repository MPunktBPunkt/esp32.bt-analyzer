# LAB W0 — Reply/Watchdog Forensic — 2026-11-17

**claim_level:** Lab State-Machine PASS · USB air Fall **A_or_C** · `wait_class=WATCHDOG_MISS_NO_ETCH_REPLY`  
**eval:** `docs/analysis/EVAL_RETEST_C93B43A_20261117.md`  
**tool:** `tools/lab_w0_reply_forensic.py`

## Delivered (Lab)

- Explicit `_rhmi_state`: `SAS_AUTHENTICATED` → … → `RESOURCE_CHECKING` → (`RESOURCE_UPLOAD`) → `RHMI_INITIALIZED` → `RUNTIME_ACTIVE`
- Open Etch TXNs + `forensic_snapshot()` / `phone_done.wait_class`
- Timeout classes: `WATCHDOG_MISS_NO_ETCH_REPLY`, `WATCHDOG_MISS_REPLY_UNMATCHED`, `STATE_MACHINE_WAIT`
- Correlator Fall A–E on phone+HU jsonl

## Results

| Test | Result |
|------|--------|
| Host 131 tests | PASS |
| In-process miss → RUNTIME_ACTIVE, uploads=1 | PASS |
| In-process hit → RUNTIME_ACTIVE, uploads=0 | PASS |
| Prior USB `c93b43a` correlator | **A_or_C** / `WATCHDOG_MISS_NO_ETCH_REPLY` |
| Fresh USB→`.131` W0 | **A_or_C** · `rhmi_state=RESOURCE_CHECKING` · check TX, **kein** check RX · HU ohne `rhmi_checkResource` RPC |

## Lesart

`wd_miss_limit=0` hält die Session offen (Diagnose). Der Rückweg von `checkResource` fehlt sichtbar auf dem Analyzer-Pfad — **nicht** als „setResource fehlt“. Nächster Feld-/Air-Schritt: Roh-HCI/RFCOMM parallel zu BCL/Etch (Fall A vs C trennen). Dual-ESP weiter separat.

## Artefakte

- `LAB_W0_RESULT_20261117.json`
- `LAB_W0_USB_FORENSIC_20261117.json` (+ phone/hu jsonl)
- `LAB_W0_FORENSIC_C93B43A_20261117.json`
