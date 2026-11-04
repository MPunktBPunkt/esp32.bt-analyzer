# LAB Method H Host Oracle — BLOCKED_HOST_ORACLE

**UTC:** 20261104T183839Z · **topology:** H_HOST_ORACLE
**Raw:** [`LAB_METHOD_H_ORACLE_20261104T183839Z.json`](LAB_METHOD_H_ORACLE_20261104T183839Z.json)

- host oracle ready: False
- userspace BT blocked: True (af_bluetooth=False)
- ESP lab peer visibility: True
- host sees lab ESPs: (n/a)
- foreign BD intersection host∩ESP: (none)

### Classification

| Claim | Status |
|-------|--------|
| Host radio present (sysfs/USB) | FACT |
| AF_BLUETOOTH in this CT | REJECTED/blocked |
| ESP lab LE visibility | MEASURED |
| BlueZ scan oracle | BLOCKED |
| Air/RF PHY sniffer | REJECTED |

### NEXT TEST
- Unblock: BlueZ on Proxmox host or BT-capable CT, re-run this tool
- Method G multiview for full RSSI matrix

