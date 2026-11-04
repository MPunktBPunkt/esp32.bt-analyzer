# Scope — HCI Analyzer ≠ Universal Bluetooth Host

```yaml
status: frozen
fw: "0.3.0+"
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
| BLE-Tastatur | ✅ HCI | ✅ HCI | ⚠️ HID-GATT-Pfad fehlt |
| Classic-Tastatur | ✅ Hardware | ❌ kein Classic auf S3 | ⚠️ Host-/HID-Pfad fehlt |
| BLE-Headset | ⚠️ | ⚠️ | ⚠️ Audio-Profil fehlt |
| Classic-Headset | ✅ Hardware | ❌ | ❌ A2DP/HFP → BT17 flavor (deferred) |
| BLE-GATT Testgerät | ✅ | ✅ | ✅ thin ATT / BT16 |
| eigener BLE Test-Peer | ✅ | ✅ | ✅ BT16 vorhanden |

## Explicit NO (until separate flavor / gate)

| Feature | Status |
|---------|--------|
| HID keyboard keystroke path | **NO** (HCI connect foundation only) |
| A2DP / HFP audio receive | **NO** → BT17 Classic flavor after BT19 |
| Full GATT client/server | **NO** |
| MITM / complex replay | **NO** |
| BT15 RF/Air | **NO** |

## Architecture cut (frozen)

```text
Analyzer Core (.88/.89 + thin .87)
  ├── capture / BTAC / session-loss / timeline / evidence
  └── thin ATT stimulus (BT16) — not a profile host

Classic Flavor (.87 only) — future PlatformIO env (BT17)
  └── Bluedroid A2DP/HFP Phone-first
```

Do **not** fold HID/A2DP into the F_ONCHIP thin-host core.
