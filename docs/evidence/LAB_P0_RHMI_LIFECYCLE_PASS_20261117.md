# LAB P0 — Connected RHMI lifecycle PASS (post-EAGAIN-retry)

**claim_level:** LAB FACT  
**source runs:** `LAB_P0_WRITE11_CAP_RETRY_DUAL_20261117T2210Z` · `…RETRY_SINGLE_20261117T2215Z`  
**commit context:** `ffd28aa` (EAGAIN retry) + this freeze note

## Verdict

With HU RFCOMM **EAGAIN retry/poll**, the lab phone path reaches:

```
checkResource(DESCRIPTION) → reply (miss)
setResource(DESCRIPTION)
checkResource(TEXTDB) → reply
checkResource(IMAGEDB) → reply
initialize → reply
setData → reply
RUNTIME_ACTIVE
```

and holds **~90 s** without WATCHDOG. Dual-ESP and Single-ESP (USB phone) both PASS.

## Dual timeline (ms after RFCOMM connect)

| dt_ms | State / RPC |
|------:|-------------|
| 918 | `SAS_AUTHENTICATED` |
| 1229 | `RHMI_CREATED` (handle 12) |
| 1239 | `AM_REGISTERED` → `RESOURCE_CHECKING` · TX `checkResource(DESCRIPTION)` |
| 3204 | RX `_result_checkResource` → `RESOURCE_UPLOAD` · TX `setResource` + `checkResource(TEXTDB)` |
| 3696 | TEXTDB result → TX `checkResource(IMAGEDB)` |
| 3899 | IMAGEDB result → TX `initialize` + **3× `setData`** → `RHMI_INITIALIZED` / **`RUNTIME_ACTIVE`** |
| 4096–4132 | RX `_result_initialize` + `_result_setData`×3 |
| 90199 | `phone_done` · `wait_class=None` · `rhmi_state=RUNTIME_ACTIVE` |

## setData content (first own UI data)

| modelId | value | HU |
|--------:|-------|----|
| 100 | `"Apps"` | accepted |
| 101 | `"Durchsuchen"` | accepted |
| 4 | `RHMIResourceIdentifier` | `rhmi_setdata_reject` errorCode **213** (non-fatal; session stays ACTIVE) |

## write11 freeze (status board)

| Area | Status |
|------|--------|
| RHMI state machine (lab) | **PASS** |
| checkResource ↔ reply | **PASS** |
| setResource / further checks | **PASS** |
| initialize ↔ reply | **PASS** |
| setData (own strings) ↔ reply | **PASS** |
| EAGAIN transient | **PASS** (still occurs) |
| EAGAIN retry recovery | **PASS** |
| WATCHDOG as primary cause | **REJECTED** |
| Dual-ESP as primary cause | **REJECTED** (single same) |
| ESP panic as primary cause | **REJECTED** |
| Backpressure *source* | **OPEN** (P2, non-blocking) |
| Stable Connected ~90 s | **PASS** |

## Epistemic notes

- This is **lab** phone (`mybmw-sim`) ↔ `f20_sim` HU over BlueZ (+ optional USB phone). Not a field OnePlus↔car claim.
- Transport stability was the missing piece after W0 Fall A rejection; retry makes the already-correct RHMI plan visible end-to-end.
- Remaining setData reject on modelId 4 is a separate F20-sim/client detail, not a session killer.

## Next (protocol product path)

1. Longer soak / more setData+actions under retry (optional).  
2. Field phone with same HU retry semantics only if reproducing on-car.  
3. P2: characterize EAGAIN wait histograms — **not** a Connected blocker.
