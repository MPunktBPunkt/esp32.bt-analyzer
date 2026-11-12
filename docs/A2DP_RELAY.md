# A2DP relay over two D1s — bit rate vs coex budget (0.3.19)

```yaml
status: dual relay audible but choppy (MEASURED) · fix plan below, untested
evidence:
  - docs/evidence/LAB_HCI_TCP_A1A5_20261111T204600Z.md       # single path stable, dual choppy, ~45 kB/s toHost
  - docs/evidence/LAB_HCI_TCP_WIFI_PS_SWEEP_ROUTER_20261111T221956Z.md
  - docs/evidence/LAB_HCI_TCP_62_37_GATE_20261112T061010Z.md  # 41–45 kB/s sustained under none
tools: tools/a2dp_budget.py · tools/lab_hci_coex_ab.py
```

## Why it is choppy

```text
Phone ─A2DP─ .131 ─TCP─┐                      ┌─TCP─ .87 ─A2DP─ headset
                       └─ BlueZ on .108: sink (decode) → source (encode) ┘
```

Each D1 carries one full A2DP leg. Sustained ACL per D1 is coex-limited to
~36–45 kB/s under `wifi_ps=none` (3–4 kB/s under `min`); better WiFi RSSI does not
raise it. Default SBC needs the same order of magnitude:

`python3 tools/a2dp_budget.py --table --budget 38` (joint stereo, 8 subbands, 16 blocks, MTU 895):

| Bitpool | kbit/s @44.1k | kB/s on HCI @44.1k | @48k | vs 38 kB/s |
|--------:|--------------:|-------------------:|-----:|-----------|
| 64 | 389 | 49.8 | 54.2 | over |
| 53 | 328 | 42.1 | 45.8 | over |
| 45 | 284 | 36.4 | 39.7 | tight |
| 35 | 229 | 29.4 | 31.9 | ok (≤ 80 %) |
| 32 | 212 | 27.2 | 29.6 | ok |

The observed ~45 kB/s toHost peak on `.131` matches bitpool 53 from the phone.
Single path had headroom from the other D1 being idle; the relay runs both D1s at
their limit, so every coex stall becomes audible.

## What the Linux audio stacks allow (checked in source, 2026-11-12)

| Stack | Source leg (→ headset) | Sink leg (phone →) |
|-------|------------------------|--------------------|
| PipeWire `spa/plugins/bluez5/a2dp-codec-sbc.c` | bitpool up to **64** @44.1k / 58 @48k (capped by headset caps); **no config key**; lowers bitpool by 2 on socket congestion (min 12) | advertises full range, phone picks (Android: 53) |
| bluez-alsa `bluealsad --sbc-quality=low\|medium\|high` | low 213 / medium 237 / high 345 kbit/s stereo | `--sbc-quality` does **not** touch sink caps; phone picks |
| PulseAudio | UNKNOWN (not checked) | UNKNOWN |

bluez-alsa can run one instance per controller (`bluealsad -B sink -i hciX -p a2dp-sink`,
`bluealsad -B source -i hciY -p a2dp-source`; needs a D-Bus policy entry for the
suffixed names, see `man bluealsad`).

## Steps (in order, each measurable)

| # | Step | Pass |
|---|------|------|
| R0 | Which stack runs the relay on `.108`: `ps -e \| egrep 'pipewire\|wireplumber\|pulseaudio\|bluealsa'` | stack recorded in evidence |
| R1 | Capture during relay: `btmon -w /tmp/relay.btsnoop`, then `python3 tools/a2dp_budget.py --btsnoop /tmp/relay.btsnoop --budget 38` | negotiated freq/bitpool per hci recorded (the max bitpool is the encoder's upper bound) |
| R2 | Coex A/B (fw 0.3.19): `SWEEP_DUR=45 python3 tools/lab_hci_coex_ab.py` | verdict `COEX_HELPS` or `NO_GAIN`; budget for R3 from the best mode |
| R3 | Headset leg: bluez-alsa source on the `.87` controller with `--sbc-quality=medium` (`low` if still choppy); with PipeWire this leg cannot be capped by config | headset leg ≤ 80 % of R2 budget in `a2dp_budget` |
| R4 | Phone leg: set the best coex mode on `.131`; phone at 44.1 kHz (Android developer options → Bluetooth audio sample rate) | listen test 2 min without dropouts, `drops=0` |

If R4 still drops: the phone leg can only be capped by advertising a lower
`max_bitpool` in the sink capabilities (one constant in bluez-alsa
`a2dp_sbc_sink`, e.g. 35). That is a local patch of the audio stack, not done here.

## Coex API (fw 0.3.19)

```bash
curl -s http://192.168.178.131/api/hci/coex
curl -s -X POST -d 'mode=a2dp' http://192.168.178.131/api/hci/coex      # default | a2dp | prefer_bt
```

| Mode | Call (ESP-IDF 5.5 `esp_coexist.h`) | Note |
|------|------------------------------------|------|
| `default` | clear `ESP_COEX_BT_ST_A2DP_STREAMING`, preference `BALANCE` | boot state |
| `a2dp` | `esp_coex_status_bit_set(ESP_COEX_ST_TYPE_BT, ESP_COEX_BT_ST_A2DP_STREAMING)` | the status Bluedroid sets while streaming; with BlueZ on Linux the chip never learns about A2DP otherwise |
| `prefer_bt` | `esp_coex_preference_set(ESP_COEX_PREFER_BT)` | deprecated in IDF 5.x; may have no effect — R2 shows it |

Modes do not stack; each call starts from `default`. `/api/status` →
`hciAgent.coex` / `coexErr`; `coexErr=no_coex_api` means the build has no
software coex (should not happen with BT+WiFi).
