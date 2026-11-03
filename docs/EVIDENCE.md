# Evidence taxonomy

Authority: [MPunktBPunkt/technology-audit](https://github.com/MPunktBPunkt/technology-audit).  
Classification everywhere:

`FACT` · `MEASURED` · `INFERENCE` · `HYPOTHESIS` · `UNKNOWN` · `REJECTED`

## Starting facts (from technology-audit)

| Claim | Status | Source |
|-------|--------|--------|
| ESP32-S3 supports BLE (on-chip) | **FACT** | Espressif / silicon sheets |
| ESP32-S3 does **not** support Classic BR/EDR on-chip | **FACT** / **REJECTED** as Classic analyzer | `bluetooth-a2dp`, `bt-dual-mode-coex` |
| HCI ≠ RF / Air | **FACT** (epistemic) | `methods/bt-passive-host-sniff.md` |
| Endpoint events ≠ Phone↔Original traffic | **REJECTED** if equated | `bt-endpoint-event-stream` |
| USB Host OTG on S3 (FS) | **FACT** (chip) | `esp-usb-host` |
| S3 USB Host + BT dongle → HCI capture | **UNKNOWN** until Topology A lab | BT1–BT3 + method baseline |
| Inject→ring→drain pipeline | **MEASURED** (0.1.3, Topology E) | `tools/lab_inject_smoke.py` |
| Classic ESP32 (D1) USB-OTG Host | **REJECTED** | no OTG — REF_ENDPOINT only |

## Must NOT claim (V1)

- HCI capture = RF sniffer
- ESP32-S3 native Classic Bluetooth analyzer
- Universal Bluetooth MITM
- Profile decode on ESP as capture truth
- `.87` endpoint logs as USB-HCI evidence

## Lab corpus

Artifacts under `docs/evidence/` — naming: `LAB_<TOPIC>_….md` (+ `.json`).  
Methods: [`LAB_METHODS.md`](LAB_METHODS.md) · Inventory: [`LAB_INVENTORY.md`](LAB_INVENTORY.md) · Template: [`evidence/LAB_EVIDENCE_TEMPLATE.md`](evidence/LAB_EVIDENCE_TEMPLATE.md).

External method: technology-audit [`bt-usb-hci-observe-baseline`](https://github.com/MPunktBPunkt/technology-audit/blob/main/methods/bt-usb-hci-observe-baseline.md).
