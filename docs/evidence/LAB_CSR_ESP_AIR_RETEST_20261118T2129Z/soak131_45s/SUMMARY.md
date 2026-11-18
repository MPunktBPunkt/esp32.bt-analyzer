# LAB CSR RFCOMM perf — 20261118T2131Z

**claim_level:** LAB FACT  
**verdict:** PASS  
**DUT:** `00:1A:7D:DA:71:02` (hci3, CSR8510)  
**Peer:** `C8:C9:A3:CB:7B:0A` (hci2)  
**RFCOMM ch:** 22 · payload 240 B · duration 45.0s/dir

## Results

| Metric | Value |
|--------|-------|
| ACL connect | False |
| RFCOMM connect_s | 5.7553935050964355 |
| Ping median / p90 / max ms | 101.7 / 107.36 / 211.8 |
| Ping errors | 0 |
| Peer→DUT kB/s | 15.57 (bytes=723460) |
| DUT→Peer kB/s | 23.2 (bytes=1071648) |
| Link | `RSSI return value: -6` / `Link quality: 249` |

Artifact: `/tmp/bcl_dummy/LAB_CSR_ESP_AIR_RETEST_20261118T2129Z/soak131_45s/REPORT.json`
