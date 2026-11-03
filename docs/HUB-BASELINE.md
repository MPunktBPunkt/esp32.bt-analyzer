# ESP32.esp-hub baseline (Stufe A)

**Source of truth:** [MPunktBPunkt/ESP32.esp-hub](https://github.com/MPunktBPunkt/ESP32.esp-hub) `esp-hub-base` **v1.10.5**  
**Policy:** [ROLLOUT_DERIVED Stufe A](https://github.com/MPunktBPunkt/ESP32.esp-hub/blob/main/docs/update/ROLLOUT_DERIVED.md) — Core **vendorn/syncen**, nicht neu erfinden.  
**Vendored path:** `firmware/analyzer-node/src/core/` (see `SYNC.md`).

## Drei Ebenen (orthogonal)

```text
Hub (ioBroker :8093)              ← Heartbeat / Rename / OTA-Push
Debian bt-analyzer :8081 / :9751  ← Lab-UI + control (parallel)
Debian usb-analyzer :8080 / :9750 ← anderes Projekt, bleibt
ESP USB Host ── HCI ── BT Dongle
```

| Ebene | Rolle | Stört HCI-Capture? |
|-------|--------|-------------------|
| **Hub** | FW-Verteilung | Nein strukturell; WiFi-Coex messen (BT13) |
| **Debian bt** | Lab-UI `:8081` / Collector | Nein (Analyseebene L3) |
| **USB-HCI** | Capture-Pfad L1 | Messpfad |

## Stufe A — BT0

Vollständiger `AppCore`-Stack (WiFiManager, HubClient, WebUi, OtaService, Diag/Recovery, PSRAM via HardwareInfo).

**Noch nicht:** USB Host, HCI Capture, Debian ControlClient, zweiter ESP.

## Sync rule

1. Edit/fix only from `ESP32.esp-hub/esp-hub-base/src/core/`
2. No silent divergence in `src/core/`
3. Builds must succeed with vendored copy only
4. GPL-3.0 attribution on copied core files; project LICENSE is MIT (see README)

## Defaults (lab)

- `HUB_HOST` `192.168.178.113` · `HUB_PORT` `8093`
- Debian bt-analyzer `192.168.178.187:8081` (UI) · `:9751` (control TCP)
- usb-analyzer remains on `:8080` / `:9750`
- OTA artifact: `bt-analyzer.${VERSION}.esp32s3.bin`
