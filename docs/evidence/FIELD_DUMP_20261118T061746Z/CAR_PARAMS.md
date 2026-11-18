# Car parameters dump — 2026-11-18T061746Z

**claim_level:** FIELD FACT (BT/SDP/Link) · CDS vehicle props **blocked** (no SAS login)

## Vehicle CDS (VIN/fuel/odometer/…)

| Prop | Status |
|------|--------|
| vehicle.VIN / language / time | **not readable** |
| sensors.fuel / driving.* | **not readable** |
| Reason | HU: `Certificate is invalid…` → `Session is not logged in` on `cds_create` |

Needs real APP cert / AAIdrive auth — Lab mybmw-sim rejected.

## What we did get (BT identity + link)

| Param | Value |
|-------|-------|
| Name | BMW 38304 |
| BD | D4:36:39:CF:E1:B5 |
| Manufacturer (LMP) | Texas Instruments (13) |
| OUI | Texas Instruments |
| LMP | 4.0 / sub 0x1b76 |
| Class | 0x340408 (Audio/Headset) |
| Modalias | bluetooth:v05EBp0116d0103 |
| RSSI | **-46** (stable ×5) |
| Link quality | **209** |
| TX power | **3** |
| Clock | 0x14719e |

## SDP channels

| Service | Channel |
|---------|---------|
| SPP / BCL (`0x1101`) | **6** (+7–10) |
| Vendor `deca-fade` | **5** |
| Handsfree ALPS_HFM | **3** |
| MAP MNS | **1** |
| OBEX | **11** |
| A2DP SNK | present |

HFP AT on ch3 refused; ch7 connected but no AT reply (SPP, not HFP).
