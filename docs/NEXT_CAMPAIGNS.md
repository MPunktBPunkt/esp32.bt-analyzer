# Next campaigns — Proxmox BlueZ host + ESP triad

```yaml
status: shipped_0.3.8
package: "0.3.8"
anchor: FTMS_CP_HOGP_L2CAP
fw_lab: "0.3.8"
lab_pass: 20261105T082512Z
```

Principle (frozen): **Analyzer ≠ Universal Bluetooth Host**.  
Layer focus (GPT): deepen **L2CAP/ATT state** before more GATT profile names.

## Packages in 0.3.8 (GPT P0/P1 morning)

| ID | Tool | Lab |
|----|------|-----|
| **FTMS CP** | `lab_ftms_control.py` | PASS `LAB_FTMS_CONTROL_20261105T082512Z` |
| **HOGP matrix** | `lab_hogp_matrix.py` | PASS `LAB_HOGP_MATRIX_20261105T081925Z` |
| **L2CAP/MTU** | `lab_l2cap_mtu_matrix.py` | PASS `LAB_L2CAP_MTU_20261105T082203Z` |
| **GATT disconnect** | `lab_gatt_disconnect_stress.py` | PASS `LAB_GATT_DISCONNECT_20261105T082025Z` |

## Evening (operator HW)

| ID | Command |
|----|---------|
| Real FTMS | `lab_ftms_recreate.py --peer-addr …` + pedaling |
| BMW AVRCP M1–M4 | `lab_avrcp_probe.py --addr <BMW> --classic-scan 20` |

## Deferred

BT20 usb/hu live · BT17 A2DP · Air/MITM · more GATT profiles
