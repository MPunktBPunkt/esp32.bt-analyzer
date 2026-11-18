# LAB CSR RFCOMM perf — 20261118T2109Z

**claim_level:** LAB FACT  
**verdict:** PASS  
**DUT:** `00:1A:7D:DA:71:02` (hci3, CSR8510)  
**Peer:** `C0:B8:83:34:F4:62` (hci0)  
**RFCOMM ch:** 22 · payload 300 B · duration 12.0s/dir

## Results

| Metric | Value |
|--------|-------|
| ACL connect | False |
| RFCOMM connect_s | 4.308038711547852 |
| Ping median / p90 / max ms | 12.99 / 14.03 / 15.02 |
| Ping errors | 0 |
| Peer→DUT kB/s | 114.55 (bytes=1416640) |
| DUT→Peer kB/s | 114.86 (bytes=1418768) |
| Link | `RSSI return value: 0` / `Link quality: 255` |

Artifact: `/tmp/bcl_dummy/LAB_CSR_PERF_MATRIX_20261118T2107Z/p300/REPORT.json`
