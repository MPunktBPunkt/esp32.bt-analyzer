# LAB P0 write11 — Single-ESP A/B (20261117T2200Z)

**claim_level:** LAB FACT  
**setup:** Phone = USB `hci0` `C0:B8:83:34:F4:62` · HU = ESP `.131` / `hci2` · `.87` bridge paused during run

## Result

**Same failure as Dual-ESP.**

| Metric | Dual (`…CAP_20261117T2156Z`) | Single (this run) |
|--------|------------------------------|-------------------|
| errno | **11 EAGAIN** | **11 EAGAIN** |
| bytes_attempted | 89 | 89 |
| tx_total / frames / max | 5250 / 93 / 500 | 5250 / 93 / 500 |
| context | CDS reply flood | CDS reply flood |
| phone wait_class | WATCHDOG_MISS_NO_ETCH_REPLY | WATCHDOG_MISS_NO_ETCH_REPLY |
| bootGen bump | no | no |

Fingerprint is effectively identical (including the 89 B failing write after the same TX totals).

## Matrix tick

| Outcome | Implication |
|---------|-------------|
| Dual fail, Single **fail** | **Not** “phone-side ESP / dual-proxy required” |
| Still one ESP on HU path | HU-side BlueZ RFCOMM socket ↔ `.131` bridge remains in path |
| Identical burst totals | Failure tied to **HU agent TX pattern** (CDS flood → non-blocking write) more than dual-radio topology |

## Ranking update

1. **Strong:** HU userspace writes RFCOMM faster than the socket accepts (`EAGAIN`) during CDS burst.  
2. **Still open:** whether the not-ready condition is pure BlueZ socket buffering, or `.131` HCI-TCP drain limiting ACL TX.  
3. **Weakened:** Dual-ESP / phone `.87` bridge as primary cause.  
4. **Still out:** ESP panic/reboot.

## Next probes

1. **Mitigation probe:** pace/coalesce HU `os.write` (poll + retry on EAGAIN instead of close) — if WATCHDOG disappears, root is write policy under backpressure.  
2. **USB↔USB** (no ESP) if a second USB adapter is available — isolates `.131` bridge entirely.  
3. Or: same BCL flood with btmon Number-of-Completed-Packets latency during the 1.5 s burst on single-ESP (already captured in `phone_hci0.btsnoop` / `hu_hci2.btsnoop`).
