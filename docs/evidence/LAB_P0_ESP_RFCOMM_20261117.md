# LAB P0 — ESP panic / RFCOMM flap correlation (2026-11-17)

**claim_level:** LAB P0 WORKSTREAM (post-freeze `c5cb0e6`)  
**tool:** `tools/lab_esp_rfcomm_flap_correlate.py`

## Why

After rejecting W0 Fall A and fixing the Alias infra race, the open question is whether missing phone-side Etch replies are **transport drops** (ESP panic / RFCOMM flap) rather than HU-not-replying.

## Recover session (`hu_recover.jsonl`)

| Metric | Value |
|--------|-------|
| flaps | **28** |
| reasons | `eof`×19 · `write_error:11`×9 |
| classes | `eof_rehandshake`×18 · `tx_pressure_during_etch_reply`×6 · `write11_then_eof_rehandshake`×3 · `eof`×1 |
| ESP at sample | `resetReason=panic`, `bootGen=24`, `hci_drops=91`, uptime ~27min (panic was **prior** boot, not every flap) |

**Pattern:** `write_error:11` often lands in a burst of `etch_data_tx` (`etch_reply`), then ~40s reconnect; many `eof` closes re-handshake in ~5s. ACL/`Connected` frequently survives.

→ Strong **transport/TX-pressure** candidate for phone-visible reply loss; **not** Fall A.

## CONT8 offline

7 flaps · same class mix (`tx_pressure_during_etch_reply`×2, `eof_rehandshake`×5).

## Live watch (~45s @ 19:45Z)

No new close in the short window; ESP `bootGen` stable (no mid-watch panic). Longer watch needed to catch panic-coincident flaps.

## Artifacts

- `LAB_P0_ESP_RFCOMM_RECOVER_20261117.{json,md}`
- `LAB_P0_ESP_RFCOMM_CONT8_OFFLINE.{json,md}`
- `LAB_P0_ESP_RFCOMM_GREEN_OFFLINE.{json,md}`
- `LAB_P0_ESP_RFCOMM_LIVE_20261117T1945Z.{json,md}`

## Next

1. Longer live watch until a flap coincides with `bootGen`/`uptime` reset (panic-linked) vs drops-only (bridge/HCI pressure).  
2. Capture panic backtrace/hub diag if ESP exposes it.  
3. Only then reopen field `WATCHDOG_MISS_NO_ETCH_REPLY` interpretation.
