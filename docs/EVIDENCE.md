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
| S3 USB Host + BT dongle → HCI capture | **UNKNOWN** until lab | first BT1–BT3 evidence |

## Must NOT claim (V1)

- HCI capture = RF sniffer
- ESP32-S3 native Classic Bluetooth analyzer
- Universal Bluetooth MITM
- Profile decode on ESP as capture truth

## Lab corpus

Artifacts under `docs/evidence/` — naming: `LAB_<TOPIC>_MEASURED.md` (+ `.json`).
