# esp-hub core sync

**Source:** `ESP32.esp-hub/esp-hub-base/src/core/` @ **v1.10.5**  
**Policy:** [docs/HUB-BASELINE.md](../../docs/HUB-BASELINE.md) — Stufe A, no silent divergence.

Vendored here as full `AppCore` stack for Phase **BT0** (Hub / WiFi / Web UI / OTA).

Refresh:

```bash
SRC=/home/martin/projects/esphub/ESP32.esp-hub/esp-hub-base
DST=firmware/analyzer-node
rsync -a --delete "$SRC/src/core/" "$DST/src/core/"
cp "$SRC/web/index.html" "$DST/web/index.html"
cp "$SRC/tools/pack_ui.py" "$DST/tools/pack_ui.py"
# SYNC.md lives next to platformio.ini (outside src/core)
```

Keep project `ProjectConfig.h`, `main.cpp`, and this file.
