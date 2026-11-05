# Next campaigns — Capture recorder → AAIdrive / BMW

```yaml
status: shipped_0.3.13
package: "0.3.13"
anchor: REAL_FTMS_TC174_and_classic_inquiry_0x22
fw_lab_s3: "0.3.12"
fw_lab_87: "0.3.13"
```

## Measures (from GPT) — priority order

| Prio | Measure | Package |
|------|---------|---------|
| **P0** | Session START/STOP/MARK + raw HCI keep | **0.3.9** |
| **P0** | BT_EVENT view (seq/ts/dir/payload) | **0.3.9** |
| **P0** | Offline drain when no BTAC client | **already** + documented |
| **P0** | Remote trigger · local BT on `.89` · TCP drain only | **0.3.10** |
| **P0** | Real FTMS Hammer Varon (`TC174`) IBD + CP | **0.3.12** evidence |
| **P0** | Classic inquiry list (`0x22` RSSI results) | **0.3.13** |
| **P1** | Classic SDP/L2CAP/RFCOMM **observe** on real BMW run | evening (lab UUID inventory **0.3.10**) |
| **P1** | AVRCP payload in session (not just UUID inventory) | evening |
| **P1** | Full store-and-forward when WiFi drops | later (lab drain path **0.3.10**) |
| **P1** | BT17 Classic pair/A2DP (HD 4.40 seen, not connected) | deferred flavor |
| **P2** | USB×BT correlation IDs (BT20 live) | after car session |
| **NO** | Transparent BT proxy / RF tunnel / MITM | rejected |

## Labs

| Tool | Purpose | Pkg |
|------|---------|-----|
| `lab_capture_session.py` | START → marks → LE traffic → STOP → BTAC → BT_EVENT | 0.3.9 |
| `btac_to_btevent.py` | BTAC → BT_EVENT JSONL | 0.3.9 |
| `lab_capture_car_node.py` | Session on `.89`, stimulus `.88`, BTAC drain (not proxy) | 0.3.10 |
| `lab_sdp_inventory.py` | BlueZ UUID inventory + optional `.87` classic | 0.3.10 |
| `lab_capture_fault.py` | Session survives peer fault modes | 0.3.10 |
| `lab_ftms_recreate.py --peer-addr …` | Real/stub FTMS checklist | 0.3.7+ |

Findings: [`FINDINGS_LAB_20261105.md`](FINDINGS_LAB_20261105.md) · Real devices: [`REAL_DEVICES.md`](REAL_DEVICES.md)

## Evening BMW / AAIdrive

```text
.89 session START → MARK APP_START → … → MARK MENU_* → STOP → pull BTAC
→ decide SDP/RFCOMM/AVRCP decoder depth from observed channels only
```
