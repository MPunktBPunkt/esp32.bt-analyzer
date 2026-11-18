# LAB CSR RFCOMM perf — 20261118T2108Z

**claim_level:** LAB FACT  
**verdict:** PASS  
**DUT:** `00:1A:7D:DA:71:02` (hci3, CSR8510)  
**Peer:** `C0:B8:83:34:F4:62` (hci0)  
**RFCOMM ch:** 22 · payload 240 B · duration 12.0s/dir

## Results

| Metric | Value |
|--------|-------|
| ACL connect | False |
| RFCOMM connect_s | 0.6828963756561279 |
| Ping median / p90 / max ms | 13.97 / 15.0 / 27.76 |
| Ping errors | 0 |
| Peer→DUT kB/s | 91.02 (bytes=1122156) |
| DUT→Peer kB/s | 93.08 (bytes=1148752) |
| Link | `RSSI return value: 0` / `Link quality: 255` |

Artifact: `/tmp/bcl_dummy/LAB_CSR_PERF_MATRIX_20261118T2107Z/p240/REPORT.json`
