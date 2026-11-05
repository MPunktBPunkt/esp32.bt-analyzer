# Next campaigns — Proxmox BlueZ host + ESP triad

```yaml
status: shipped_0.3.7
package: "0.3.7"
anchor: FTMS_recreate_AVRCP_BlueZ_deep
fw_lab: "0.3.5"
lab_pass: 20261105T074554Z
```

Principle (frozen): **Analyzer ≠ Universal Bluetooth Host**.  
Proxmox/BlueZ = real host · ESP = measure / controlled stimulus · not RF sniffer.

## Packages in 0.3.7 (evening HW optional)

| ID | Tool | Stand-in | Lab |
|----|------|----------|-----|
| **FTMS recreate** | `lab_ftms_recreate.py` | ftmsprobe checklist vs `.89` | PASS `LAB_FTMS_RECREATE_20261105T074554Z` |
| **BlueZ deep** | `lab_bluez_deep.py` | reconnect×3 + classic `.87` | PASS `LAB_BLUEZ_DEEP_20261105T074415Z` |
| **AVRCP local** | `lab_avrcp_probe.py --local` | BlueZ `110c`/`110e` inventory | PASS `LAB_AVRCP_20261105T074346Z` |

Docs: [`AVRCP_MEASURE.md`](AVRCP_MEASURE.md) · [`BT20_CORRELATION.md`](BT20_CORRELATION.md)

## Shipped

| Pkg | Labs |
|-----|------|
| 0.3.6 | BT20 synth/live · bluez_device · R2 real/synth |
| 0.3.5 | R1a/b · R2a/b · BT16-burst · R3 |

## Still deferred (operator evening)

| ID | Why |
|----|-----|
| Real FTMS bike | `--peer-addr` on `lab_ftms_recreate.py` + pedaling |
| AVRCP car M1–M4 | `lab_avrcp_probe.py --addr <BMW>` |
| BT20 usb/hu live | flash sibling nodes |
| BT17 A2DP | phone/headset + Bluedroid |
| Air/MITM | rejected |
