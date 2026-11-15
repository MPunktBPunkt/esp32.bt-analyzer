# FIELD — AAIdrive Bluetooth logs 2026-11-15 (deep decode)

Peer HU `d4:36:39:cf:e1:b5`, app uid **10479** (MyBMW/AAIdrive SPP client).

| Log | Role |
|-----|------|
| `docs/bluetooth_20261115_102033_30998.log` | Session A: SCN6 rejected → SCN10 short Etch |
| `docs/bluetooth_20261115_102058_28027.log` | Session B: SCN6 full Connected-App path |
| `docs/bluetooth_20261115_102217_29993.log` | BT restart / bonded cache only — no BCL |

## FIELD FACT (extends prior analysis)

```
Phone → SPP 0x1101 → RFCOMM SCN 6 (B) / 10 (A)
  → BCL HANDSHAKE v5 / iid=14 / buf=0x4000
  → DATAACK (running counter)
  → DATA dest=0x0FA4 (4004) + DEADBEEF etch
  → CDS-like vehicle properties (HU→Phone)
```

First Etch DATA (session B):

```
10:21:31.972  DATA src=10 dest=4004 plen=44
  DEADBEEF 00000024 0386A6B0FFCA 0286EDA8C9A687000001
```

## New details beyond the first pass

### 1. Two RFCOMM attempts, not one

Session A (`102033`):

- `connectSocket` 0x1101 → SDP **SCN 6** → `RFC_PORT_EVENT_DM` / `Start failed[12]`
- Retry → **SCN 10** connects; HS + Etch begin; **44× UIH len=667** already on SCN10
- Slot cleanup ~8s after connect — short session

Session B (`102058`): SCN 6 succeeds end-to-end (~47s of dumps).

### 2. Hex dumps are a tiny sample of the wire

| Metric (session B, SCN6) | Value |
|--------------------------|------:|
| RFCOMM UIH nonzero | 1088 |
| UIH payload bytes | 137775 |
| `data_hex` dumps | 82 |
| Hex bytes actually captured | 2280 (**~1.65%** of UIH) |
| UIH len=667 | 48 |
| Dumps declaring len=667 | 3 |

`data_hex` is hard-capped at **32 bytes**. Large Etch frames appear as mid-payload **FRAGMENT** dumps (`_ENT_MTP_OFF`, `sensors.SOCBatter…`) without BCL header in the visible window.

### 3. 667-byte flood starts 143 ms after first DATA

```
10:21:31.972  first DATA → 4004
10:21:32.115  first UIH 667   ← not 10:21:34
```

Early window 10:21:31–33 alone: **~17 KB** UIH (21×667). Capability/CDS bulk is already flowing before the first truncated 667 hex dump at 10:21:34.208.

### 4. src=12 is the CDS workhorse

Parsed DATA→4004 headers (session B):

| src | count | notes |
|----:|------:|-------|
| 12 | 43 | dominant; type-id `0386ae0d3d69` |
| 18 | 7 | small void-like `03869358a564…` |
| 10 | 1 | first reply after OPEN window |
| 11,14,17,19 | 1–2 each | other services |

Lab dummy etch mapped **src 12 → cdsbaseapp** cert — field traffic shape matches.

Etch string type **`0x93 | len | ascii`** prefixes on src12:

| prefix | declared lens | likely CDS ns |
|--------|---------------|---------------|
| `en…` | 11/13/15/18 | entertainment* |
| `dr…` | 20 | driving* |
| `se…` | 24 | sensors.* |
| `ve…` | 12 | vehicle* |
| `na…` | 26 | navigation* |

Confirmed plaintext fragments: `_ENT_MTP_OFF`, `iva_MYV_LIGHT_INTERIOR*`, `sensors.SOCBatter*`, `:255.00}`.

### 5. Small 44-byte DATA = etch “void/ack” shape

Body often:

```
0386 <type4> 0286EDA8C9A687000001
```

Same trailer across src 10/12/14/17/18/19 — not SAS challenge blobs; look like short RPC completions.

### 6. DATAACK is a live flow counter

Not only `OPEN → ACK 8`. Observed values include 10, 44, 559, 2695, **4008 (0x0FA8)**, 3255, …  
`0x0FA8` recurs often (4004+4 candidate / channel bookkeeping — still interpretive).

### 7. Silent Phone→HU window is ~3.0 s

```
HS 10:21:28.459  →  first DATAACK 10:21:31.471
```

That gap is where INIT / OPEN 4004 / `sas_certificate` must live. These oplus logs only show **HU→app**.

## Still UNKNOWN (needs btsnoop)

- Phone→HU etch: `sas_certificate` → challenge → `sas_login`
- Full 667-byte etch bodies
- Exact method names behind type-ids `0386********`

## Next capture

Same working MyBMW/AAIdrive session with **`btsnoop_hci.log`** (both directions on RFCOMM SCN6).
