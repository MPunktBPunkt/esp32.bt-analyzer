# FIELD — AAIdrive Bluetooth logs 2026-11-15 (revised)

Peer HU `d4:36:39:cf:e1:b5`, app uid **10479**.
Cross-ref: [`LAB_SILENT_HU_INIT_KNOCK_20261115.md`](LAB_SILENT_HU_INIT_KNOCK_20261115.md),
[`FIELD_AAIDRIVE_BTLOG_20261115_decode.json`](FIELD_AAIDRIVE_BTLOG_20261115_decode.json).

| Log | Role |
|-----|------|
| `docs/bluetooth_20261115_102033_30998.log` | Session A: SCN6 DM → SCN10 (2 attempts) |
| `docs/bluetooth_20261115_102058_28027.log` | Session B: SCN6 golden path → CDS |
| `docs/bluetooth_20261115_102217_29993.log` | BT restart / bond cache — no BCL |

## Verdict

**Yes — vehicle/CDS data is visible**, but only through a keyhole (~1.65 % hex).
**No — we do not have everything**; Phone→HU / SAS / full 667-B bodies need btsnoop.

```text
MyBMW/AAIdrive → SPP 0x1101 → SCN 6 (or SCN 10 failover)
  → BCL HS v5 / iid=14 / buf=0x4000
  → [Phone→HU ~3.0 s — UNKNOWN in oplus logs]
  → DATAACK + DATA dest=4004 + DEADBEEF
  → Etch → CDS vehicle properties (HU→Phone fragments)
```

## FIELD FACT

- SPP `0x1101`, HS v5 / iid 14 / `0x4000`
- Session B SCN6 end-to-end; Session A SCN10 carries BCL/Etch after SCN6 DM
- DATA → `0x0FA4` + DEADBEEF etch
- CDS property fragments: `sensors.SOCBatter*`, `:255.00}`, `_ENT_MTP_OFF`,
  `iva_MYV_LIGHT_INTERIOR*`, `false`
- src12 dominates (43/56) — aligns with lab `cdsbaseapp`
- 667 UIH burst starts **143 ms** after first DATA→4004
- Silent TX window HS→first DATAACK = **3.012 s** (contents still INFERENCE)

## Corrections (vs earlier decode / 14.11 field table)

### M29 — Silent-HU: 4-B = INIT, not WD

LAB FACT from Silent-HU hex: every 4-B chunk is `12345678` (INIT).
56-B chunks carry KNOCK UUID-serial `0e9b90c4-…56619` inside a `deadbeef` envelope
— **strong INFERENCE** KNOCK-related; **not** proven raw `BclPacket` cmd=8.

Silent-HU timing diverges from field → **not** a calibration of M9 timers.

### M30 — SCN6→SCN10 failover (carefully)

Session A timeline:

```text
10:20:35.279  connect SCN6
10:20:35.584  DM / Start failed[12]
              (no prior SCN6 session in this log)
10:20:37.089  SCN10 #1 → cleanup 10:20:45.321 (no HS dump)
10:20:48.873  SCN10 #2 → HS 10:20:49.112 → Etch → close 10:20:56
```

**FIELD FACT:** after SCN6 DM, AAIdrive can build BCL/Etch on SCN10.  
**UNKNOWN:** SDP meaning of SCN10; why SCN6 DM (stale-SCN6 hypothesis unsupported here).

Do **not** claim „SCN10 = second equal BCL endpoint“ without SDP from btsnoop.

### M31 — DATAACK model

**REJECTED:** monotonic running counter (values fall back: 2695→8→…→4008→3255).

**Best current model (Bimmer-backed, not fully proven on wire):**
`DataAck(8 + packet.data.size)` = ACK of each received BCL frame size.
Fits 8 (OPEN) and 44 (small DATA). Large values (559, 2695, 4008, …) —
frame vs reassembled Etch — **decide in btsnoop**.

## Coverage trap

| Metric (Session B SCN6) | Value |
|-------------------------|------:|
| UIH nonzero | 1088 |
| UIH bytes | 137775 |
| Hex captured | 2280 (~1.65 %) |
| UIH len=667 | 48 |
| Dumps declaring 667 | 3 |

`data_hex` hard-capped at 32 bytes. Large frames often appear as mid-payload
FRAGMENT dumps without BCL header.

## Etch notes

| Item | Status |
|------|--------|
| Type-id `0386ae0d3d69` @ src12 | dominant; method name UNKNOWN |
| 44-B `0386…0286EDA8C9A687000001` | void/ack-shaped RPC completion — not SAS |
| Prefixes `en/dr/se/ve/na…` | CDS namespace guesses |

## Epistemic bar

```text
Transport SCN6 / RFCOMM          ██████████  FIELD FACT
BCL Handshake v5                 ██████████  FIELD FACT
DATAACK + DATA→4004              ██████████  FIELD FACT
Etch DEADBEEF + CDS fragments    ████████░░  FIELD FACT (partial)
SCN10 failover works             ████████░░  FIELD FACT (SDP role UNKNOWN)
4-B silent = INIT                ██████████  LAB FACT
56-B = KNOCK-related UUID blob   ███████░░░  strong INFERENCE
DATAACK = BCL frame size         ██████░░░░  Bimmer-backed INFERENCE
Phone→HU / SAS                   ██░░░░░░░░  UNKNOWN
Full Etch bodies / type→method   █░░░░░░░░░  UNKNOWN
```

## Next (priority)

1. **P0** `btsnoop_hci` Session B — both directions, RFCOMM filter off  
2. **P0b** same for Session A (DM + SCN10 + SDP)  
3. Rebuild 667-B bodies → type-id mapping  
4. Isolate SAS inside the 3.012 s window  
5. Proxy / SAS-Replay only after that
