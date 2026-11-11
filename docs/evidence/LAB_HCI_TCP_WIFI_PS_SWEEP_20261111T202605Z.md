# LAB HCI wifi_ps ACL sweep T1–T5 — MEASURED

**UTC:** 20261111T202605Z · fw `0.3.17` · commit `e1b02b9` · host `.108` · ESP↔ESP l2test 672 B
**claim:** sustained ACL throughput vs `wifi_ps`; ring water-level shows coex/PS limit, not software queue

| Test | start PS | mid switch | 131→ctrl kB/s | 87←host kB/s | pps | mean pkt | ringPeak 131/87 | drops | inst peak kB/s |
|------|----------|------------|---------------|--------------|-----|----------|-----------------|-------|----------------|
| T1_max | max | — | 3.38 | 3.36 | 5.44 | 637.3 | 521/1362 | 0 | 4.4 |
| T2_min | min | — | 3.81 | 3.75 | 5.77 | 675.9 | 521/1370 | 0 | 4.6 |
| T3_none | none | — | 38.5 | 38.84 | 58.36 | 675.5 | 1282/2043 | 0 | 45.6 |
| T4_min_to_none | min | 10s→none | 38.77 | 39.21 | 58.76 | 675.6 | 1362/4767 | 0 | 44.5 |
| T5_none_to_min | none | 10s→min | 37.93 | 38.45 | 57.51 | 675.4 | 1362/4767 | 0 | 45.2 |

## Verdict

- **Fall A (Coex / WiFi PS):** `max`/`min` cold ≈ **3.4–3.8 kB/s**; `none` ≈ **38–39 kB/s** sustained (60 s).
- **Not Fall B (queue):** `ringPeak` ≤ **4767 / 24576** (~19 %), **drops=0** in all T1–T5 → larger ring would not raise sustained rate.
- **Sticky high after `none`:** T4 first windows already ~42 kB/s while status still `min`; T5 stays ~42–45 kB/s after mid-switch to `min`. `wifi_ps=min` after a `none` session does **not** reliably re-throttle until radio/session reset (API label ≠ immediate duty-cycle restore).
- **l2ping:** ESP controllers report *Peer doesn't support Echo packets* — not usable for RTT; use `rttLastUs` / HTTP instead.
- **HTTP `/api/status`:** p50 ≈ **650–720 ms** (weak RSSI lab); HCI command RTT ≈ **1.5–1.8 ms** (`rttLastUs`) with Δsamples under `hciconfig name`.
- Prior live peak ~62 kB/s remains plausible as short-window max; 60 s mean under `none` here ≈ **39 kB/s**.

## Next

Accept ~39 kB/s `none` / ~4 kB/s `min` as coex budget for dual-leg A2DP; do not enlarge ring. Proceed A6/B1 for BMW — throughput is already above BCL/AVRCP needs.
