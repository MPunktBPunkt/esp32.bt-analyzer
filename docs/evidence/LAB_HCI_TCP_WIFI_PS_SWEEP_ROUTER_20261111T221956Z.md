# LAB HCI wifi_ps sweep on router AP — MEASURED

**UTC:** 20261111T221958Z · fw `0.3.18` · both D1 on **FRITZ!Box 7490** BSSID `5C:49:79:D1:8E:A6` ch6 · RSSI ≈ −45/−52 · 45 s l2test 672 B
**compare:** prior sweep on Repeater 2400 (`LAB_HCI_TCP_WIFI_PS_SWEEP_20261111T202605Z`) at RSSI ≈ −85

| Test | start | mid | ctrl/host kB/s | RSSI | ringPeak | drops | inst peak | ok |
|------|-------|-----|----------------|------|----------|-------|-----------|-----|
| T1_max | max | — | 4.13/4.12 | [-45, -52] | 513/1370 | 0 | 5.8 | True |
| T2_min | min | — | 0.0/0.0 | [-45, -52] | 516/1370 | 0 | 0.0 | False |
| T3_none | none | — | 36.27/36.9 | [-46, -50] | 774/4086 | 0 | 44.7 | True |
| T4_min_to_none | min | 10s→none | 37.69/38.3 | [-46, -51] | 1362/4086 | 0 | 44.1 | True |
| T5_none_to_min | none | 10s→min | 37.47/37.54 | [-46, -51] | 1362/4086 | 0 | 42.1 | True |

## Verdict

- Better WiFi RSSI (**−45/−52** vs −85) did **not** raise sustained ACL: `none` still ≈ **36–38 kB/s** (was ~38–39); `max` ≈ **4.1 kB/s**.
- Confirms bottleneck is **BT/WiFi coexistence on the ESP**, not the weak Repeater backhaul.
- `ringPeak` ≪ 24 KiB, drops=0 → still not a software queue limit.
- T2 `min` cold failed once (`Host is down`); T1 `max` and T3–T5 OK — page/ACL under `min` remains flaky, recipe stays bring-up then `none` for rate.
- Sticky: T5 after mid-switch to `min` still ~37 kB/s; immediate retest under API `min` after the suite also ~37.5/38.3 kB/s (label ≠ throttle until radio reset).
