# LAB FTMS Control Point — PASS

**UTC:** 20261105T082512Z

| case | ok | Δind | req | result |
|------|----|------|-----|--------|
| request_control | True | 1 | 0 | 1 |
| reset | True | 1 | 1 | 1 |
| start_resume | True | 1 | 7 | 1 |
| stop_pause | True | 1 | 8 | 1 |
| set_resistance | True | 1 | 4 | 1 |
| set_power | True | 1 | 5 | 1 |
| invalid_opcode | True | 1 | 63 | 2 |
| write_without_cccd | True | 0 | — | — |

Success ≠ Wirkung.

