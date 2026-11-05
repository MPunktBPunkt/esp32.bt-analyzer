# Real devices — HOGP / FTMS / Classic (no peer stub)

```yaml
status: scaffold
fw_required: "0.3.2+"
peer_stubs: false
```

Peer stubs on `.89` prove **STIMULUS capability**. Real keyboards / ergometers prove **foreign peer** behaviour. Success ≠ Wirkung for FTMS (power numbers on wire ≠ rider physics).

## Lab CLI (ready offline; run when device present)

```bash
# Lab peer stub (existing)
python3 tools/lab_hogp_ftms.py

# BlueZ host path (Proxmox SSH oracle) — ESP stand-in or foreign addr
python3 tools/lab_bluez_device.py --peer 192.168.178.89
python3 tools/lab_bluez_device.py --addr AA:BB:CC:DD:EE:FF --no-esp --label foreign_keyboard

# Real↔Synthetic claim split (synth arm without foreign HW)
python3 tools/lab_r2_real_synthetic.py
python3 tools/lab_r2_real_synthetic.py --real-addr AA:BB:CC:DD:EE:FF --profiles hogp

# Foreign BLE peer — analyzer connect by BD_ADDR, no .89 advertise
python3 tools/lab_hogp_ftms.py --peer-addr AA:BB:CC:DD:EE:FF --addr-type 1 --profiles hogp
python3 tools/lab_hogp_ftms.py --peer-addr AA:BB:CC:DD:EE:FF --addr-type 0 --profiles ftms
python3 tools/lab_hogp_ftms.py --peer-addr AA:BB:CC:DD:EE:FF --profiles both
```

`--addr-type`: `0` public · `1` random (typical BLE HID peripherals).

## Checklist — BLE keyboard (HOGP)

1. Put keyboard in pairing / advertising mode  
2. On `.88`: scan → note ADDR + addrType  
3. `lab_hogp_ftms.py --peer-addr … --addr-type … --profiles hogp`  
4. Evidence must record: services contain `1812`, Report Map read, ≥1 Input Report notify  
5. Label: `peer=foreign_keyboard` · claim still `STIMULUS_*_over_HCI_not_air`  
6. UNKNOWN until green: full boot-protocol keystroke path / consumer keys

## Checklist — FTMS Indoor Bike

1. Bike advertising FTMS `1826`  
2. Same connect + `--profiles ftms`  
3. Evidence: Feature read + Indoor Bike Data notifies  
4. Note explicitly: **Success ≠ Wirkung**

## Checklist — Classic headset (BT17 — deferred)

Blocked on Classic Audio Flavor (scaffold in `analyzer-esp32-classic-audio`). Phone-first on `.87` only — see [`BT17_CLASSIC_AUDIO.md`](BT17_CLASSIC_AUDIO.md).

## Host oracle (optional)

After BlueZ on DebianCursor ([`HOST_BT.md`](HOST_BT.md)): pair the same keyboard to the PC **or** to ESP — never both controllers on one link. Streams labeled apart.
