# LAB HCI post-reset suite — MEASURED (partial)

**UTC:** 20261111T205603Z · fw `0.3.17` / `0.3.17` · after power-cycle both D1s
**claim:** transport/bridge/RTT still healthy; Classic ACL/inquiry currently RF-range limited in this placement

## What worked

- Both boards online `0.3.17`, bridges ESTAB to `:9754`, `wifi_ps` toggle OK
- HCI Command RTT samples increment (`rttSamples` Δ≈9–10 per 10 `hciconfig name`)
- Earlier same evening (pre-suite): `.87` inquiry saw `.131`; `hcitool cc` `.131→.87` OK; **host USB `hci0`→`.131` l2test transferred** (per-frame bursts up to ~77 kB/s on short N=10)

## What failed tonight (suite)

- Mutual Classic inquiry: neither side found the other during suite
- All l2test connects (`host→131`, `131→87`, `87→131`, min/none): **connected=false**, 0 kB/s
- WiFi RSSI ≈ **-84…-88 dBm** — correlates with flaky BT page/inquiry; not a firmware regression vs morning sweep

## RTT (post-reset)

| wifi_ps | HTTP .131 p50/p95 | HTTP .87 p50/p95 | HCI .131 last/max µs | HCI .87 last/max µs |
|---------|-------------------|------------------|----------------------|---------------------|
| min | 724.8/3810.9 | 657.0/690.8 | 2325/19082 | 1536/3058 |
| none | 704.2/725.0 | 652.2/742.2 | 1616/19082 | 1376/3058 |

## Throughput reference (still valid)

Morning/evening sweep `LAB_HCI_TCP_WIFI_PS_SWEEP_20261111T202605Z`: **~3.4–3.8 kB/s min/max**, **~38–39 kB/s none**, ringPeak≪24 KiB, drops=0 → **coex/PS limit**.

## Lab UI graphs

Empty/flat on `:8081` is expected while rates are 0 (no ACL) and/or `.131` briefly unreachable — not a UI bug.

## Next

- Reposition D1s closer (WiFi RSSI better than -70) before more ACL sweeps
- Car: A6 tomorrow; do not chase more buffer/rate in software
