# LAB BCL Dummy-HU SDP — FAIL

**UTC:** 20261112T062016Z · channel 5 · service `BMW Connected`
**claim:** ProfileManager SPP visible via phone-side sdptool — TEST, not BMW FACT

| Check | Result |
|-------|--------|
| overall | FAIL |
| profile registered | True |
| ACL | False |
| SDP verdict | `NONE: no RFCOMM data service in SDP (may appear only with app active)` |
| records | 0 |

## Records


## Epistemic

```text
YES:  Dummy-HU can advertise SPP/RFCOMM over BlueZ SDP
YES:  bcl_sdp_probe verdict path works against a known service
NO:   what the real BMW HU offers
```
