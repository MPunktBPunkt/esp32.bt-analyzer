# FIELD AUTH PROBE — 2026-11-18T061541Z

**claim_level:** FIELD FACT
**path:** `.87` / `hci1` `C8:C9:A3:CB:37:96` → HU `D4:36:39:CF:E1:B5` SCN **6**
**client:** `b2a-tx --full-client --mybmw-sim --knock wire_v5` (~70 s)

## Verdict

| Layer | Result |
|-------|--------|
| ACL + RFCOMM SCN6 | **PASS** |
| BCL HS v5 / iid14 / buf 0x4000 | **PASS** (`BCL_FIELD_CONFIRMED`) |
| Watchdog 5001 | **PASS** — 28/28 echoes, 0 miss, RTT min/p50/max = 55/157/265 ms |
| Lab `mybmw-sim` SAS/RHMI on F20 | **REJECTED by HU** (ServiceException texts) |
| Resource-Lifecycle / F20 Action-IDs | **not reached** (blocked at Auth) |

Local sim state `rhmi_state=SAS_AUTHENTICATED` is **misleading** — HU Etch replies are exceptions, not a real login.

## HU exception strings (ASCII from Etch DATA)

- `Certificate is invalid or expired.` (plen=98, `_result_sas_certificate`)
- `Client has not sent an app certificate yet.` (plen=107, `_result_sas_login`)
- `param component is invalid.` (plen=91)
- `param handle is invalid.` (plen=88, `_result_rhmi_getCapabilities`)
- `Session is not logged in.` (plen=89, cds/am/av create)
- `param metadata is invalid.` (plen=90, `rhmi_create`)

Deep analysis: [`../../analysis/DEEP_FORENSIC_FIELD_AUTH_REJECT_20261118.md`](../../analysis/DEEP_FORENSIC_FIELD_AUTH_REJECT_20261118.md)

## TX → RX map

| TX | RX len | Note |
|----|--------|------|
| sas_certificate | 98 | invalid/expired cert |
| sas_login | 107 | no app certificate yet |
| ver/info/rhmi_getCapabilities/cds/am/rhmi/av create | ~69–91 | exceptions (not logged in / invalid param) |

Compare: field AAIdrive `_result_rhmi_getCapabilities` was **5306 B** — here **88 B** = error PDU.

## Implication (Audit car_next)

Confirms claim boundary: Lab soak/seq ≠ F20 Auto-ready. Next useful step needs **real APP cert / digest match** (or capture of phone AAIdrive auth), not more transport holds.

