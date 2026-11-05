# AVRCP measure — BlueZ host + car (no MITM)

```yaml
status: scaffold_0.3.7
host: Proxmox BlueZ @ 192.168.178.108
claim: host_avrcp_presence_and_sdp_not_air
car: BMW NBT Evo (operator evening)
```

## Why here

PiDrive / bt-gateway plan AVRCP Target↔BMW Controller.  
This repo measures the **host oracle path** (Proxmox BlueZ) and freezes a car checklist — not a Gateway implementation.

| Claim | Status |
|-------|--------|
| BlueZ advertises AVRCP Controller+Target UUID | **MEASURED** (local `bluetoothctl show`) |
| Car opens Browsing (`SetBrowsedPlayer`) | **UNKNOWN** until evening |
| Metadata 3 lines reach HU | **UNKNOWN** until evening |
| MITM / Air | **NO** |

## Local inventory (no car)

```bash
python3 tools/lab_avrcp_probe.py --local
```

Evidence: `LAB_AVRCP_*` with controller UUIDs `110c` / `110e`.

## Car checklist (operator)

1. Phone or Pi already paired to BMW as media source **or** pair Proxmox temporarily (one controller only).  
2. `python3 tools/lab_avrcp_probe.py --addr <BMW_BD> --classic-scan 20`  
3. Record: SDP/UUID has AVRCP? player menu lists transport?  
4. Pass-Through subset (Play/Pause/Next) — log only, no claim of iDrive MENU remap.  
5. Browsing attempt → evidence `LAB_AVRCP_CAR_*` with FACT/MEASURED/UNKNOWN split (see bt-gateway `AVRCP-MOEGLICHKEITEN.md` M1–M4).

## Explicit NO

- No A2DP in thin VHCI core  
- No claim that ESP `.87` is an AVRCP Target yet (BT17 Flavor deferred)  
- No MITM between phone and car
