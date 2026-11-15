# FIELD P0 Hold — frozen wire config (2026-11-15)

```yaml
gate: P0_HOLD
hu: D4:36:39:CF:E1:B5
phone_radio: .87 / hci1 / C8:C9:A3:CB:37:96
channel: 6   # SPP Server 1 / first 0x1101
claim_level: FREEZE for subsequent factor runs — one variable per later P1 test
```

## Frozen bootstrap (no OPEN 4004)

| Step | Value |
|------|-------|
| RFCOMM | Phone→HU SCN **6** |
| INIT | `12 34 56 78` (≤3× / 1 s until HS) |
| HANDSHAKE (HU) | expect **v5 / iid 14 / buf 0x4000** |
| SELECTPROTO | **4** |
| KNOCK | **wire_v5** = UUID `0e9b90c4-…56619` + TouchCommand **1/7** |
| OPEN WD | src=dest=**5001** (`--wire-open5001`) |
| OPEN Etch 4004 | **off** (P0 — measure unsolicited only) |
| WD ping | `13371337` @ **2.5 s** |
| Phone DATAACK | off (measure **HU** DATAACK only) |

## Abort / classify

- **3 consecutive missed WD echoes** → `hold_abort` / `wd_echo_miss_limit`
- RFCOMM eof / OSError → `rfcomm_closed` + reason
- Success window: hold duration completed with continuous WD RTT samples

## Metrics logged (JSONL)

- `watchdog_echo_rtt` → P50/P95 post-pass
- `hu_dataack` (`ack_n`, expect `8+len` → 10 / 44 / 4008 pattern)
- `hu_unsolicited` (OPEN/DATA src 10/12/18 or dest 4004) → Modell A
- btmon on `hci1` for full HCI evidence

## Modell D (operator)

During hold: use **iDrive / MyBMW screen / CarPlay** without changing analyzer TX.
Any `hu_unsolicited` correlated with UI time → UI-triggered OPEN 4004.

## Short precursor

`FIELD_B2A_TX_20261115T131825Z` (45 s): RFCOMM+HS v5+WD echo OK; KNOCK was desk-default by bug (explicit SP4 skipped auto wire_v5). Hold uses `--knock wire_v5` explicitly.

## Runs

| Session | Duration | Outcome |
|---------|----------|---------|
| `FIELD_P0_HOLD_20261115T132501Z` | ~174 s | abort 3× WD miss; DATAACK 10/8/12; unsolicited 0 |
| `FIELD_P0_HOLD_20261115T132919Z` | 1800 s target | in progress (RTT fix) |
