# Profile Flavor Bus

```yaml
status: active
fw: "0.3.2+"
package: "0.3.6"
next: "docs/NEXT_CAMPAIGNS.md"
peer_fault: "POST /api/bt/peer/fault mode=off|slow|burst|gap|drop"
core: analyzer_vhci_capture
```

## Rule (frozen)

```text
Analyzer Core          Profile Flavors
─────────────────      ─────────────────────────
VHCI HCI capture       optional Stimulus/Client
PSRAM ring / BTAC      discovery / CCCD / profiles
loss / timeline        TX tagged STIMULUS
JSONL / PCAPNG         never owns the controller
```

Flavors **must not** replace the VHCI capture path. Host influence stays visible in status (`flavor.*`) and evidence.

## Adoption order

| # | Flavor | Gate | Status |
|---|--------|------|--------|
| 1 | **GATT Client MVP** | BT18 | **0.3.1** — discover + MTU + CCCD + read |
| 2 | **HOGP Host** | BT18b | **0.3.2** — Report Map + Input Report notify (peer stub) |
| 3 | **FTMS Client** | BT18c | **0.3.2** — Feature + Indoor Bike Data notify (peer stub) |
| 4 | Classic SDP/RFCOMM → HID → A2DP/HFP | BT17 | **scaffold 0.3.3** — env `analyzer-esp32-classic-audio` (no A2DP yet, no OTA) |

Runtime for BLE Flavors on this tree: **thin ATT over existing VHCI host** (same controller plane as capture). NimBLE/Bluedroid remain rejected as Core replacements (VHCI ownership conflict).

## STIMULUS tag

Every Flavor TX increments `flavor.stimulusTx`. Status block:

```json
"flavor": {
  "id": "gatt_client",
  "state": "ready|disc_svc|…|error|idle",
  "claim": "STIMULUS_L2_over_HCI_not_air",
  "stimulusTx": 12,
  "stimulusRx": 8
}
```

## APIs (GATT Client)

```bash
POST /api/bt/flavor/gatt/discover   # mtu=23|247
POST /api/bt/flavor/gatt/read       # handle=
POST /api/bt/flavor/gatt/subscribe  # cccd=  enable=1|0
POST /api/bt/flavor/hogp/start      # after discover
POST /api/bt/flavor/ftms/start      # after discover
GET  /api/status                    # → flavor + hogp + ftms
```

Labs:
```bash
python3 tools/lab_gatt_client.py
python3 tools/lab_hogp_ftms.py
python3 tools/lab_hogp_ftms.py --peer-addr AA:BB:… --profiles hogp   # foreign peer
python3 tools/lab_host_bt_probe.py                                   # Debian/Proxmox BT
```

Peer stubs ≠ real keyboard / ergometer — see [`REAL_DEVICES.md`](REAL_DEVICES.md).  
Host BT oracle: [`HOST_BT.md`](HOST_BT.md). FTMS: **Success ≠ Wirkung**.
