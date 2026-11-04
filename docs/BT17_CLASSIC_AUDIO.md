# BT17 — Classic audio / RFCOMM (separate Bluedroid flavor)

```yaml
status: scaffold_0.3.3
fw_core: "0.3.2+ thin VHCI analyzer"
flavor_env: analyzer-esp32-classic-audio
board: 192.168.178.87
phone_first: true
ota: deferred  # do not flash until Bluedroid path wired
```

See also: [`SCOPE_HOST_VS_ANALYZER.md`](SCOPE_HOST_VS_ANALYZER.md) — headset/keyboard ≠ current thin host.

## Architecture cut (frozen)

```text
Analyzer Core (.88/.89 + thin .87)
  ├── capture / BTAC / session-loss / timeline / evidence
  └── NO A2DP/HFP in thin VHCI host

Classic Flavor (.87 only) — PlatformIO env analyzer-esp32-classic-audio
  ├── src/classic_flavor/ClassicAudioFlavor.*  (scaffold API)
  ├── Bluedroid A2DP/HFP Phone-first           (TODO — not wired)
  └── may ship separate HCI snoop claim (≠ thin VHCI path)
```

Do **not** fold A2DP into the F_ONCHIP thin-host core.

## Scaffold (package 0.3.3 — no HW)

| Piece | Status |
|-------|--------|
| `platformio.ini` env `analyzer-esp32-classic-audio` | **present** |
| `ClassicAudioFlavor` API stub | **present** (`state=scaffold`) |
| Excluded from `analyzer-s3` / `analyzer-esp32` | **yes** |
| Bluedroid A2DP/HFP | **not wired** |
| HTTP `/api/bt/flavor/classic/*` | **not wired** |
| OTA to `.87` | **blocked** until phone-first path exists |

Build compile-check (no upload):

```bash
cd firmware/analyzer-node && pio run -e analyzer-esp32-classic-audio
```

## Prerequisites (must be green first)

1. BT16-B benchmark evidence (CAPABILITY + BENCHMARK exits) — **done 0.3.0**
2. Impact A–D with median/stdev
3. Clock-offset estimation claims explicit
4. BT19 multi-node timeline scaffold producing aligned JSONL — **done**
5. HOGP/FTMS STIMULUS path — **done 0.3.2** (peer stubs)

## Phone-first checklist (when flavor exists)

1. Build `analyzer-esp32-classic-audio`
2. Pair phone → `.87`
3. Play audio; capture stack HCI/snoop + Debian session
4. Evidence `LAB_BT17_*` with FACT/MEASURED split (profile ≠ Air)

## BMW / AAIdrive

Only after BT19 timeline + usb-analyzer/hu-probe correlation path — **no MITM claim**.

## Current thin-host stimulus only

```bash
curl -X POST http://192.168.178.87/api/bt/discoverable/start -d 'name=bt-classic-87'
python3 tools/lab_clock_sync.py
```
