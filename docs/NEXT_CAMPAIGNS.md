# Next campaigns — Proxmox BlueZ host + ESP triad

```yaml
status: shipped_0.3.6
package: "0.3.6"
anchor: BT20_cross_layer
fw_lab: "0.3.5"
lab_pass: 20261105T071116Z
```

Principle (frozen): **Analyzer ≠ Universal Bluetooth Host**.  
Proxmox/BlueZ = real host · ESP = measure / controlled stimulus · not RF sniffer.

## Packages in 0.3.6

| ID | Tool | Stand-in | Lab |
|----|------|----------|-----|
| **BT20 synth** | `lab_bt20_correlate.py --synth` | schema + usb/hu synth lanes | PASS `LAB_BT20_20261105T070957Z` |
| **BT20 live** | `lab_bt20_correlate.py --live-bt` | BlueZ×ESP window correlate | PASS `LAB_BT20_20261105T071116Z` |
| **R1 device** | `lab_bluez_device.py` | BlueZ device evidence (ESP/`--addr`) | PASS `LAB_BLUEZ_DEVICE_20261105T070906Z` |
| **R2 split** | `lab_r2_real_synthetic.py` | Real↔Synthetic claim split | PASS `LAB_R2_REAL_SYNTHETIC_20261105T070920Z` |

Docs: [`BT20_CORRELATION.md`](BT20_CORRELATION.md)

## Shipped 0.3.5 (baseline)

| ID | Lab |
|----|-----|
| R1a/R1b/R2a/R2b/BT16-burst/R3 | PASS `20261104T224934Z`…`225209Z` |

## Still deferred

| ID | Why |
|----|-----|
| BT20 + usb/hu live | needs usb-analyzer / hu-probe nodes on session |
| BT17 A2DP | needs phone/headset + Bluedroid wiring |
| Foreign HOGP/FTMS | operator keyboard / bike (`--real-addr` / `--addr`) |
| Air/MITM | rejected |

## Dreiklang

```text
reales Gerät (or ESP stub) → BlueZ host → experience
ESP simulator → STIMULUS → reproducible MEASURED
BT Analyzer → HCI / Timeline / Loss evidence
     ↓
BT20 window correlate (debian bridge) — not MITM
```
