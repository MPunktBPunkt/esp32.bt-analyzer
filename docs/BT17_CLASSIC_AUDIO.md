# BT17 — Classic audio / RFCOMM endpoint (.87)

```yaml
status: scaffold
fw_pin: "0.2.8+"
board: 192.168.178.87
claim_boundary: endpoint_HCI_not_air
```

## Goal

Use the **ESP32 Classic+BLE** node (`.87`) as a **Phone-first** A2DP/HFP or RFCOMM endpoint while capturing HCI where the stack allows.

## Why not in Thin-Host P0

The F_ONCHIP thin VHCI host deliberately owns `esp_vhci_host_callback` and tears down Bluedroid. A2DP/HFP need a full Classic host stack (Bluedroid/IDF). Options:

1. **Separate build flavor** `analyzer-esp32-classic-audio` with Bluedroid + optional HCI snoop tap (different claim: endpoint + stack logs, not same thin VHCI path).
2. **External Classic DUT** (second ESP32 / phone) while `.87` stays discoverable stimulus only (current BT10).

## Phone-first checklist

1. Flash Classic-audio flavor (when built) or use stock IDF A2DP sink example on a spare ESP32.
2. Pair phone → `.87` (or DUT).
3. Start playback; capture HCI/snoop + Debian session.
4. Evidence: `docs/evidence/LAB_BT17_*` with FACT/MEASURED split (profile events ≠ Air).

## BMW / AAIdrive

Deferred until:

- BT16 throughput + impact green
- Clock sync markers (`tools/lab_clock_sync.py`) produce stable offsets
- Multi-node timeline (BT19) exists

Then correlate usb-analyzer / hu-probe with `.87` Classic HCI — **no MITM claim**.

## Repro (current repo)

```bash
# Stimulus only (thin host):
curl -X POST http://192.168.178.87/api/bt/discoverable/start -d 'name=bt-classic-87'
python3 tools/lab_clock_sync.py
```
