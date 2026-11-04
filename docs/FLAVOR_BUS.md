# Profile Flavor Bus

```yaml
status: active
fw: "0.3.1+"
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
| 2 | HOGP Host | BT18b | deferred |
| 3 | FTMS (+ HR/CSC) | BT18c | deferred |
| 4 | Classic SDP/RFCOMM → HID → A2DP/HFP | BT17 | deferred (`.87` only) |

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
GET  /api/status                    # → onchip + flavor
```

Lab: `python3 tools/lab_gatt_client.py`
