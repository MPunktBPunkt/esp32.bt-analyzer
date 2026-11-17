# LAB P0 — EAGAIN retry mitigation (Dual + Single)

**claim_level:** LAB FACT  
**change:** `bcl_dummy_hu_agent.rfcomm_write_all` — on `EAGAIN` poll/retry up to `BCL_WRITE_EAGAIN_S` (default 2.0s) instead of immediate `rfcomm_closed`.

## Results

| Run | Topology | hold_s | write11 | WATCHDOG | eagain recovered | phone end |
|-----|----------|--------|---------|----------|------------------|-----------|
| baseline dual `…CAP_20261117T2156Z` | ESP↔ESP | ~24 (WD) | **yes** ~1.5s | yes | n/a (fail-fast) | abort |
| baseline single `…CAP_SINGLE_…` | USB↔ESP | ~23 (WD) | **yes** ~1.5s | yes | n/a | abort |
| **retry dual** (this) | ESP↔ESP | **93.7** | **no** | **no** | 2× (max 11 retries / 0.20s) | `RUNTIME_ACTIVE` |
| **retry single** `…RETRY_SINGLE_…` | USB↔ESP | **92.0** | **no** | **no** | 2× (max 6 retries / 0.12s) | `RUNTIME_ACTIVE` |

## Interpretation

EAGAIN still occurs during the CDS burst (backpressure is real), but **closing the socket was the bug that turned transient not-ready into WATCHDOG_MISS**.

Retry/poll converts the same pressure into a short wait (~0.1–0.2s) and the session continues to RHMI `RUNTIME_ACTIVE` for the full hold.

This does **not** prove the field phone stack must do the same — it proves the lab failure mode was **write-policy under backpressure**, not HU-not-replying and not ESP panic.

## Knobs

- `BCL_WRITE_EAGAIN_S` (default `2.0`, `0` = old fail-fast)
- `BCL_WRITE_EAGAIN_POLL_S` (default `0.02`)
