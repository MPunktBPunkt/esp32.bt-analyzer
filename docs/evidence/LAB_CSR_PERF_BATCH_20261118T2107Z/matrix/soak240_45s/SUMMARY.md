# LAB CSR RFCOMM perf — 20261118T2110Z

**claim_level:** LAB FACT  
**verdict:** PASS  
**DUT:** `00:1A:7D:DA:71:02` (hci3, CSR8510)  
**Peer:** `C0:B8:83:34:F4:62` (hci0)  
**RFCOMM ch:** 22 · payload 240 B · duration 45.0s/dir

## Results

| Metric | Value |
|--------|-------|
| ACL connect | False |
| RFCOMM connect_s | 1.838317632675171 |
| Ping median / p90 / max ms | 13.53 / 15.02 / 27.0 |
| Ping errors | 0 |
| Peer→DUT kB/s | 90.81 (bytes=4188016) |
| DUT→Peer kB/s | 92.26 (bytes=4253652) |
| Link | `RSSI return value: 0` / `Link quality: 172` |

Artifact: `/tmp/bcl_dummy/LAB_CSR_PERF_MATRIX_20261118T2107Z/soak240_45s/REPORT.json`
