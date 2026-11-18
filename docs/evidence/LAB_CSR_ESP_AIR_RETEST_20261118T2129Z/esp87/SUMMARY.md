# LAB CSR RFCOMM perf — 20261118T2129Z

**claim_level:** LAB FACT  
**verdict:** PASS  
**DUT:** `00:1A:7D:DA:71:02` (hci3, CSR8510)  
**Peer:** `C8:C9:A3:CB:37:96` (hci1)  
**RFCOMM ch:** 22 · payload 240 B · duration 15.0s/dir

## Results

| Metric | Value |
|--------|-------|
| ACL connect | True |
| RFCOMM connect_s | 0.5461981296539307 |
| Ping median / p90 / max ms | 102.95 / 111.86 / 204.93 |
| Ping errors | 0 |
| Peer→DUT kB/s | 15.61 (bytes=246196) |
| DUT→Peer kB/s | 25.18 (bytes=390400) |
| Link | `RSSI return value: 0` / `Link quality: 255` |

Artifact: `/tmp/bcl_dummy/LAB_CSR_ESP_AIR_RETEST_20261118T2129Z/esp87/REPORT.json`
