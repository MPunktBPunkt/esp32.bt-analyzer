# Next campaigns — Proxmox BlueZ host + ESP triad

```yaml
status: shipped_0.3.5
package: "0.3.5"
anchor: HOST_BT_ssh_oracle
lab_pass: 20261104T225209Z
```

Principle (frozen): **Analyzer ≠ Universal Bluetooth Host**.  
Proxmox/BlueZ = real host · ESP = measure / controlled stimulus · not RF sniffer.

## Packages in 0.3.5 (no external keyboard/headset required)

| ID | Tool | Stand-in | Lab |
|----|------|----------|-----|
| **R1a** | `lab_r1_bluez_esp.py` | BlueZ ↔ `.89` advertise/connect | PASS `LAB_R1_BLUEZ_ESP_20261104T224934Z` |
| **R1b** | `lab_r1_pair_matrix.py` | soft reconnect (bond optional) | PASS `LAB_R1_PAIR_MATRIX_20261104T224948Z` |
| **R2a** | `lab_r2_bluez_profiles.py` | BlueZ connect + analyzer HID/FTMS | PASS `LAB_R2_BLUEZ_PROFILES_20261104T225042Z` |
| **R2b** | `lab_r2_fault_inject.py` | peer fault modes (FW 0.3.5) | PASS `LAB_R2_FAULT_20261104T225114Z` |
| **BT16 burst** | `lab_bt16_burst.py` | idle/burst/idle notify | PASS `LAB_BT16_BURST_20261104T225151Z` |
| **R3 lite** | `lab_r3_classic_visible.py` | BlueZ sees `.87` discoverable | PASS `LAB_R3_CLASSIC_VISIBLE_20261104T225209Z` |

External real devices (keyboard/headset/bike/car) = operator tomorrow → same tools with foreign BD_ADDR / BlueZ pair to hardware.

## Still deferred

| ID | Why |
|----|-----|
| R4 BT20 | needs usb-analyzer/hu-probe correlation |
| BT17 A2DP | needs phone/headset + Bluedroid wiring |
| Air/MITM | rejected |

## Dreiklang

```text
reales Gerät (or ESP stub) → BlueZ host → experience
ESP simulator → STIMULUS → reproducible MEASURED
BT Analyzer → HCI / Timeline / Loss evidence
```
