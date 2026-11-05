# Real devices — HOGP / FTMS / Classic (no peer stub)

```yaml
status: measured_20261105
fw_required: "0.3.12+ (FTMS real) · 0.3.13 (.87 Classic inquiry)"
peer_stubs: false
```

Peer stubs on `.89` prove **STIMULUS capability**. Real keyboards / ergometers prove **foreign peer** behaviour. Success ≠ Wirkung for FTMS (power numbers on wire ≠ rider physics).

## Measured — 2026-11-05

| Device | Addr | Path | Result |
|--------|------|------|--------|
| **Hammer Varon XTR II** (`TC174`) | `c2:32:a5:1e:bf:b5` public | `.89` FTMS client 0.3.12 | **PASS** IBD + CP Request Control — [`LAB_FTMS_REAL_TC174_20261105T143641Z`](evidence/LAB_FTMS_REAL_TC174_20261105T143641Z.md) |
| **Sennheiser HD 4.40BT** | `00:16:94:2e:85:db` | `.87` inquiry 0.3.13 · BlueZ | **seen**; pair/A2DP **not** on thin VHCI (BT17 deferred) |

Full write-up: [`FINDINGS_LAB_20261105.md`](FINDINGS_LAB_20261105.md). Ergo reference stack: `esp32.ergo`.

## Lab CLI

```bash
# Lab peer stub
python3 tools/lab_hogp_ftms.py

# Real FTMS bike (Hammer / any FTMS 1826)
python3 tools/lab_ftms_recreate.py --peer-addr c2:32:a5:1e:bf:b5 --addr-type 0 --skip-bluez
python3 tools/lab_hogp_ftms.py --peer-addr c2:32:a5:1e:bf:b5 --addr-type 0 --profiles ftms

# BlueZ host path
python3 tools/lab_bluez_device.py --peer 192.168.178.89
python3 tools/lab_bluez_device.py --addr AA:BB:CC:DD:EE:FF --no-esp --label foreign_keyboard

# Real↔Synthetic claim split
python3 tools/lab_r2_real_synthetic.py
python3 tools/lab_r2_real_synthetic.py --real-addr AA:BB:CC:DD:EE:FF --profiles hogp
```

`--addr-type`: `0` public · `1` random (typical BLE HID peripherals).

## Checklist — BLE keyboard (HOGP)

1. Put keyboard in pairing / advertising mode  
2. On `.88`: scan → note ADDR + addrType  
3. `lab_hogp_ftms.py --peer-addr … --addr-type … --profiles hogp`  
4. Evidence must record: services contain `1812`, Report Map read, ≥1 Input Report notify  
5. Label: `peer=foreign_keyboard` · claim still `STIMULUS_*_over_HCI_not_air`  
6. UNKNOWN until green: full boot-protocol keystroke path / consumer keys

## Checklist — FTMS Indoor Bike (Hammer Varon proven)

1. Bike advertising FTMS `1826`  
2. Connect + FTMS flavor (`--profiles ftms` or recreate)  
3. Evidence: Feature read + Indoor Bike Data notifies while pedaling  
4. Optional: CP Request Control (`opcode=0`) — Varon uses **Notify** on `2AD9`  
5. Note explicitly: **Success ≠ Wirkung**  
6. FW ≥ **0.3.12** (CCCD Write-Cmd fallback + IBD speed-aware decode)

## Checklist — Classic headset (BT17 — deferred)

Inquiry on `.87` **works** from **0.3.13** (event `0x22`).  
Connect/pair/A2DP still blocked on Classic Audio Flavor scaffold — see [`BT17_CLASSIC_AUDIO.md`](BT17_CLASSIC_AUDIO.md). Red blink on HD 4.40 = waiting for a real Classic host (e.g. BlueZ PC), not the thin analyzer.

## Host oracle (optional)

After BlueZ on DebianCursor ([`HOST_BT.md`](HOST_BT.md)): pair the same keyboard to the PC **or** to ESP — never both controllers on one link. Streams labeled apart.
