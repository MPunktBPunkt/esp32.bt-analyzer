# LAB CSR RFCOMM perf — 20261118T2016Z

**claim_level:** LAB FACT  
**verdict:** PASS  
**DUT:** `00:1A:7D:DA:71:02` (hci3, CSR8510)  
**Peer:** `C0:B8:83:34:F4:62` (hci0)  
**RFCOMM ch:** 22 · payload 240 B · duration 15.0s/dir

## Results

| Metric | Value |
|--------|-------|
| ACL connect | False |
| RFCOMM connect_s | 0.052396535873413086 |
| Ping median / p90 / max ms | 11.5 / 12.99 / 13.78 |
| Ping errors | 0 |
| Peer→DUT kB/s | 91.53 (bytes=1408856) |
| DUT→Peer kB/s | 91.71 (bytes=1414468) |
| Link | `RSSI return value: 0` / `Link quality: 208` |

Artifact: `/tmp/bcl_dummy/LAB_CSR_RFCOMM_PERF_run/REPORT.json`
