# LAB P0 — write_error:11 / WATCHDOG_MISS master (2026-11-17)

**claim_level:** LAB FACT  
**question:** Are phone-visible `WATCHDOG_MISS_NO_ETCH_REPLY` events coincident with ESP panic/reboot, or with RFCOMM TX pressure (`write_error:11`)?

## Answer (tonight)

**TX pressure / RFCOMM close — not ESP reboot.**

When Just-Works bond + BCL phone session succeed, the session reliably dies within ~25s as:

1. HU `rfcomm_closed` reason **`write_error:11`**
2. Phone `wait_class` **`WATCHDOG_MISS_NO_ETCH_REPLY`** / `hold_abort:wd_echo_miss_limit`
3. ESP `bootGen` **unchanged**, `drops` usually 0

Raw RFCOMM holds (180–360s) stay up without panic; earlier dual-panic after the first interrupted hold was **not** reproduced under steady raw load.

## Batches

| Package | Valid BCL | write11 | WATCHDOG_MISS | bootGen bumps |
|---------|-----------|---------|---------------|---------------|
| `LAB_P0_WRITE11_BATCH_20261117T2117Z` (5×90s) | 3 (runs 3–5) | 3 | 3 | 0 |
| `LAB_P0_WRITE11_BATCH_LONG_20261117T2125Z` (3×180s) | 2 (runs 1,3) | 2 | 2 | 0 |
| `LAB_P0_WRITE11_BATCH_CLEAN_20261117T2130Z` (4×120s) | 4 | 3 | 3 | 0 |
| `LAB_P0_87_131_HOLD_BCLONLY_20261117T1955Z` | 1 | 1 | 1 | 0 |
| Raw holds 180/300/360s | n/a | n/a | n/a | 0 (no panic) |

Bond flakes (`Page Timeout` / discovery miss) still occur between rapid restarts; BCL mode now **fails closed** instead of silently falling back to raw.

## Tooling shipped

- `tools/lab_p0_dual_esp_hold.py` — BD-resolved adapters, BCL vs raw exclusive, diag pre/post
- `tools/lab_p0_write11_batch.py` — multi-run summarizer
- `tools/bt_pair_agent.py` — `--capability` (lab JW)
- `tools/lab_esp_rfcomm_flap_correlate.py` — multi `--esp`

## UI

Debian Lab UI `:8081` reorganized into topic tabs + BMW subtabs + sticky status pills + howto on Übersicht.

## Instrumented capture (`LAB_P0_WRITE11_CAP_20261117T2156Z`)

- HU `os.write` → **errno 11 EAGAIN** after **~1.55 s**, during CDS reply flood (89 B attempt; 5250 B / 93 frames already sent).
- Phone `WATCHDOG_MISS` ~24 s later is the **aftermath**, not the write moment.
- btmon still shows RFCOMM credits ~30 near fail → prefer socket/queue/bridge-drain over air-credit=0.
- Details: `LAB_P0_WRITE11_CAP_20261117T2156Z/ANALYSIS.md`

## Single-ESP A/B (`LAB_P0_WRITE11_CAP_SINGLE_20261117T2200Z`)

USB phone (`hci0`) ↔ ESP HU `.131`: **same EAGAIN fingerprint** as Dual (89 B / 5250 B / 93 frames / CDS flood).  
→ Phone-side ESP / dual-proxy **not** required for the bug. See that dir’s `ANALYSIS.md`.

## Next (protocol, not panic)

1. HU write policy probe: retry/poll on EAGAIN instead of immediate close.  
2. Optional USB↔USB (no ESP) if second dongle available.  
Field `WATCHDOG_MISS_NO_ETCH_REPLY` = aftermath of RFCOMM EAGAIN — still not W0 Fall A.
