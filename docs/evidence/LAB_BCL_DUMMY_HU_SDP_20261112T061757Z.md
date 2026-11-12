# LAB BCL Dummy-HU SDP — FAIL

**UTC:** 20261112T061757Z · channel 5 · service `BMW Connected`
**claim:** ProfileManager SPP visible via phone-side sdptool — TEST, not BMW FACT

| Check | Result |
|-------|--------|
| overall | FAIL |
| profile registered | True |
| ACL | True |
| SDP verdict | `None` |
| records | 0 |

## Records


## Epistemic

```text
YES:  Dummy-HU can advertise SPP/RFCOMM over BlueZ SDP
YES:  bcl_sdp_probe verdict path works against a known service
NO:   what the real BMW HU offers
```
