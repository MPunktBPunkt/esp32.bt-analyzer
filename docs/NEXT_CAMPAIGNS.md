# Next campaigns — Proxmox BlueZ host + ESP triad

```yaml
status: planned
package: "0.3.4+"
anchor: HOST_BT_ssh_oracle
```

Principle (frozen): **Analyzer ≠ Universal Bluetooth Host**.  
Proxmox/BlueZ = real host experience · ESP = measure / controlled stimulus · not RF sniffer.

## Dreiklang

```text
reales Gerät  →  Linux BlueZ host  →  Anwendungserfahrung
ESP simulator →  kontrollierter Stimulus →  reproduzierbare Messung
BT Analyzer   →  HCI / Timeline / Loss-Evidenz
```

## Priority packages

| ID | Fokus | Inhalt |
|----|--------|--------|
| **R1** | Real devices → BlueZ | Tastatur, Headset, Phone, Ergometer, optional Auto — Discovery/Pair/Connect/Services/Traffic/Disconnect/Reconnect only |
| **R2** | ESP simulators | `.88`/`.89` GATT / FTMS / HID stubs + fault injection; Real↔Synthetic same profile |
| **R3** | Classic `.87` | Phone/Headset/Car/Keyboard — Inquiry/Pairing first; then BT17 A2DP/HFP |
| **R4** | Cross-layer | BT19 timeline × usb-analyzer × hu-probe → BT20 correlation |

## Methods already shipped (0.3.4)

| Method | Tool |
|--------|------|
| G Multiview | `lab_method_multiview.py` |
| H Host oracle (SSH→Proxmox BlueZ) | `lab_method_host_oracle.py` · `lab_bt_host_ssh.py` |
| D Classic+BLE mix | `lab_method_classic_ble_mix.py` |
| Foreign HOGP/FTMS | `lab_hogp_ftms.py --peer-addr …` |

See [`HOST_BT.md`](HOST_BT.md) · [`REAL_DEVICES.md`](REAL_DEVICES.md) · [`LAB_METHODS.md`](LAB_METHODS.md).

## Explicit defer

- HID/A2DP into thin VHCI core — **no**
- ESP as MITM / Air sniffer — **no**
- BMW protocol claims before Classic baseline — **no**
