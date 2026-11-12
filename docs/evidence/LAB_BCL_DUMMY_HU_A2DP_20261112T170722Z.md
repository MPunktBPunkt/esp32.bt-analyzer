# LAB BCL Dummy-HU A2DP+SPP — ERROR

**UTC:** 20261112T170722Z · peer `external` · HU-dummy `.131` · channel 5 · hu_version 3
**claim:** Dummy-HU answers BCL session init behind the BclCarLink A2DP+SPP gate — TEST, not BMW FACT

| Check | Result |
|-------|--------|
| bt-pair-agent active | True |
| HU events | `{"session_init": 0, "frames": {}, "framer_error": false}` |

## First HU events

```text
```

## Epistemic

```text
YES:  Dummy-HU keeps RFCOMM open and answers session init with HANDSHAKE
YES:  BclCarLink gate (A2DP connected + SPP UUID) checked before RFCOMM
NO:   real HU HANDSHAKE values, KNOCK reply, watchdog pong layout
```
