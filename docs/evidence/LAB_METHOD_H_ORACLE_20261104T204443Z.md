# LAB Method H Host Oracle — PASS

**UTC:** 20261104T204443Z · **topology:** H_HOST_ORACLE
**Raw:** [`LAB_METHOD_H_ORACLE_20261104T204443Z.json`](LAB_METHOD_H_ORACLE_20261104T204443Z.json)

- host oracle ready: True
- userspace BT blocked: True (af_bluetooth=False)
- ESP lab peer visibility: True
- host sees lab ESPs: ['68:b6:b3:29:33:9d', '68:b6:b3:2b:c5:69', 'c8:c9:a3:cb:37:96']
- foreign BD intersection host∩ESP: ['6c:70:cb:f0:08:65']

### Classification

| Claim | Status |
|-------|--------|
| Host radio present (sysfs/USB) | FACT |
| AF_BLUETOOTH in this CT | FACT |
| ESP lab LE visibility | MEASURED |
| BlueZ scan oracle | MEASURED |
| Air/RF PHY sniffer | REJECTED |

### NEXT TEST
- Unblock: BlueZ on Proxmox host or BT-capable CT, re-run this tool
- Method G multiview for full RSSI matrix

