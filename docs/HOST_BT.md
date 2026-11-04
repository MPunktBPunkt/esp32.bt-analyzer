# Host Bluetooth — ThinkCentre / Proxmox → Cursor LXC

```yaml
status: ssh_oracle_active
host_hw: Lenovo ThinkCentre M75q-1
proxmox: 192.168.178.108
ct: DebianCursor 100 @ 192.168.178.187
controller: C0:B8:83:34:F4:62
claim: FACT_radio_presence_not_air
```

## Architecture (why SSH)

Unprivileged LXC has its **own netns**. Linux Bluetooth (`AF_BLUETOOTH`) is **not netns-aware** → inside Cursor: `EAFNOSUPPORT`.  
sysfs may still show `hci0` from the host view — that is **not** a usable stack.

```text
ThinkCentre M75q-1 (Proxmox .108)
  Intel 9260 BT  →  BlueZ bluetoothd  →  bluetoothctl
                         ↑
              SSH BatchMode (root@108)
                         ↑
              DebianCursor CT100 (.187)  labs / Cursor
```

## Setup done

| Step | Status |
|------|--------|
| BlueZ on Proxmox host | installed · `bluetooth.service` active |
| Controller | `C0:B8:83:34:F4:62` · Name `Proxmox` · Powered yes |
| SSH from CT → host | `root@192.168.178.108` (existing key) |
| Lab bridge | `tools/lab_bt_host_ssh.py` |

## Control from Cursor LXC

```bash
python3 tools/lab_bt_host_ssh.py show
python3 tools/lab_bt_host_ssh.py scan --seconds 8
python3 tools/lab_host_bt_probe.py          # expect ssh_oracle.ok=true
python3 tools/lab_method_host_oracle.py     # Method H via SSH BlueZ
```

Override target: `BT_HOST_SSH=root@192.168.178.108`

## Explicit NO

| Action | Status |
|--------|--------|
| Native BlueZ inside unprivileged CT | **NO** (netns) |
| Air/RF sniffer claim | **NO** |
| Share HCI with ESP analyzer core | **NO** |
| MITM | **NO** |
