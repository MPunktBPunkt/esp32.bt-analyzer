# LAB BCL Dummy-HU A2DP+SPP — NO_RFCOMM

**UTC:** 20261112T172006Z · peer external · HU-dummy `.131` · channel 5 · apps MyBMW + AAIDRIVE
**claim:** apps did not open RFCOMM to Dummy-HU — TEST, not BMW HU FACT

| Check | Result |
|-------|--------|
| re-pair with dummy up | yes |
| A2DP connected | yes |
| local SPP 0x1101 registered | yes |
| RFCOMM to dummy | no |
| AAIDRIVE connection attempt UI | none |

## Epistemic

```text
YES:  Dummy advertised A2DP sink + SPP; phone stayed A2DP-connected
YES:  No RFCOMM from MyBMW/AAIDRIVE to this dummy after re-pair
NO:   whether a real HU or another app stack would open BCL over BT
```

