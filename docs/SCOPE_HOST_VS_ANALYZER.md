# Scope — HCI Analyzer ≠ Universal Bluetooth Host

```yaml
status: frozen
fw: "0.3.2+"
claim_split: analyzer_vs_host
```

The current product is a **Bluetooth HCI measurement point** (VHCI → ring → BTAC).
It is **not** a universal Bluetooth host that can fully operate arbitrary keyboards or headsets.

```text
Bluetooth device
       │
       ▼
ESP32 Bluetooth Controller
       │
       ▼
HCI / VHCI          ← MEASURED today
       │
       ▼
Capture Ring → BTAC :9753 → JSONL / PCAPNG
```

If a supported thin-host / future flavor path establishes a link and generates HCI,
the analyzer can capture that HCI. It does **not** automatically reconstruct every
application profile from arbitrary HCI.

## Device matrix (today)

| Gerät | `.87` | `.88`/`.89` | Datenmessung heute |
|-------|-------|-------------|--------------------|
| BLE-Tastatur | ✅ HCI | ✅ HCI | ⚠️ HOGP Flavor 0.3.2 (stub green; foreign → [`REAL_DEVICES.md`](REAL_DEVICES.md)) |
| Classic-Tastatur | ✅ Hardware | ❌ kein Classic auf S3 | ⚠️ Host-/HID-Pfad fehlt |
| BLE-Headset | ⚠️ | ⚠️ | ⚠️ Audio-Profil fehlt |
| Classic-Headset | ✅ Hardware | ❌ | ❌ A2DP/HFP → BT17 scaffold 0.3.3 (no OTA) |
| BLE-GATT Testgerät | ✅ | ✅ | ⚠️ BT18 discovery MVP (not full GATT) |
| eigener BLE Test-Peer | ✅ | ✅ | ✅ BT16 + BT18 peer stub |
| DebianCursor Intel 9260 | — | — | ✅ radio FACT · BlueZ oracle via SSH→Proxmox ([`HOST_BT.md`](HOST_BT.md)) |

## Explicit NO (until separate flavor / gate)

| Feature | Status |
|---------|--------|
| HID keyboard keystroke path | **NO** → HOGP Flavor |
| A2DP / HFP audio receive | **NO** → BT17 Classic flavor |
| Full universal GATT client | **NO** — BT18 is bounded discovery/CCCD only |
| Transparent HCI passthrough MITM | **NO** |
| Semantic PROXY (Debian bridge) | **P0 inventory** → P1 AVRCP — [`PROXY.md`](PROXY.md) |
| BT15 RF/Air | **NO** |

## Architecture cut (frozen)

```text
Analyzer Core (.88/.89 + thin .87)
  ├── capture / BTAC / session-loss / timeline / evidence
  ├── thin ATT stimulus (BT16)
  └── Profile Flavors (opt-in STIMULUS) — see FLAVOR_BUS.md
        └── BT18 GATT Client MVP (0.3.2)

Classic Flavor (.87 only) — scaffold (BT17 / 0.3.3)
  └── env analyzer-esp32-classic-audio · Bluedroid A2DP/HFP TODO
```

Do **not** fold HID/A2DP into the F_ONCHIP Analyzer Core.
