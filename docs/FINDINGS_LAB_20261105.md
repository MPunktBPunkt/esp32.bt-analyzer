# Lab findings — 2026-11-05 (real devices)

```yaml
fw_s3: "0.3.12+"
fw_classic_87: "0.3.13"
evidence_pass: LAB_FTMS_REAL_TC174_20261105T143641Z
```

## What we proved

### Hammer Varon XTR II (`TC174`, `c2:32:a5:1e:bf:b5`)

| Claim | Result |
|-------|--------|
| Seen in BLE scan | **yes** (RSSI lab ≈ −57…−73) |
| FTMS `0x1826` + Feature `2ACC` | **yes** (`featureLo=18086`) |
| Indoor Bike Data `2AD2` while pedaling | **PASS** — notifies≥14, ~87 rpm (raw/2), ~38 W |
| Control Point `2AD9` Request Control | **PASS** — response result=1 (Success) |
| Success ≠ Wirkung | **held** — wire values ≠ rider physics claim |

Cross-ref: working stack in [esp32.ergo](https://github.com/MPunktBPunkt/esp32.ergo) (same bike).

### Bugs found → fixed

1. **0.3.11** — Desc table filled before FTMS; stub CCCD `0x25` used → wrong subscribe on real bike.  
2. **0.3.12** — Varon CCCD Write Request → ATT `0x0A` put GATT client into `Error`, so IBD notifies were dropped though present on HCI. Ported ergo lessons: keep Ready, Write-Command fallback, IBD Instantaneous-Speed parse, CP **Notify** (not Indicate).  
3. **0.3.13** — Classic Inquiry Mode 1 emits event **`0x22`**; code only handled `0x02`/`0x2F` → `/api/bt/devices` empty despite HCI results (HD 4.40 at ≈ −37 dBm on wire).

### Sennheiser HD 4.40BT (`00:16:94:2e:85:db`)

| Claim | Result |
|-------|--------|
| BlueZ PC sees / name | **yes** (`HD 4.40BT`, A2DP/AVRCP/HFP UUIDs) |
| `.87` Classic inquiry after 0.3.13 | **yes** (RSSI ≈ −79 dBm next to ESP) |
| Connect / pair / A2DP on thin `.87` | **NO** — BT17 scaffold only; red blink = waiting for real Classic host |

S3 nodes (`.88`/`.89`) have no Classic radio — expected miss.

## Capture / topology (same day, earlier packages)

| Lab | Pkg | Result |
|-----|-----|--------|
| Car-node session on `.89` + TCP drain | 0.3.10 | PASS (not a BT proxy) |
| SDP UUID inventory (BlueZ) | 0.3.10 | PASS (observe-only) |
| Capture under peer fault | 0.3.10 | PASS |

## Still open → package map

See [`NEXT_CAMPAIGNS.md`](NEXT_CAMPAIGNS.md) (post-review 0.3.14+).

| Gap | Next pkg |
|-----|----------|
| Remote Name / EIR on `.87` | **0.3.14 shipped** (lab: `55" Crystal UHD` named; HD 4.40 when on air) |
| Live HCI frame list + rates on `:8081` | **0.3.14 shipped** |
| Scan/Connect in `.87` min UI | **0.3.14 shipped** (~2.6 KB OTA free left) |
| FTMS rpm/W overlay | **0.3.15 observe** (`tools/ftms_ibd.py` lite ready) |
| PROXY Dual Classic (`.131`+`.87`) | **P0 inventory** — `.131`=Heizung (flash blocked); see [`PROXY.md`](PROXY.md) |
| SDP / L2CAP observe (headset / BMW) | **0.3.16** |
| Pair / A2DP (HD 4.40 connected) | **BT17** (not thin core) |
| BMW AVRCP payload depth | evening car + 0.3.16 |
| Store-and-forward WiFi gap | later |
