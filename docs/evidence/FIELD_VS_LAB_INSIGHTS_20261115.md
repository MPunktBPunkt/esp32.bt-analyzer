# Field vs Lab — insights 2026-11-15 (HU session end)

```yaml
field_legs: ".87/hci1 ↔ F20 D4:36:39:CF:E1:B5"
lab_legs: "OnePlus ↔ .131 Dummy-HU (parallel)"
artifacts:
  - FIELD_B2A_TX_20261115T131825Z
  - FIELD_P0_HOLD_20261115T132501Z / T132919Z
  - FIELD_BURST_20261115 (SP2/SP4/ETCH10)
  - LAB_PAR_131_* / prior LAB_SAS_* / LAB_WD_MAX3_*
hu_end: page-timeout / Host is down during SP3/Desk retries
revised: GPT/Grok cross-check of Hold JSONL timestamps (KNOCK≠ACK56)
```

## Burst matrix (this session)

| Pattern | RFCOMM | HS v5 | WD echo | OPEN 4004 TX | HU Etch/SAS RX | Note |
|---------|--------|-------|---------|--------------|----------------|------|
| SP4 + wire_v5 + OPEN5001 | ok | ok | ok ~150–300 ms | no | — | control |
| SP4 + wire_v5 + OPEN 4004 src10 | ok | ok | ok | **yes** (`0001000a0fa4`) | **none** | HU DATAACK **8** extra (= ACK empty OPEN) |
| SP2 + wire_v5 + OPEN5001 | ok | ok | ok | no | — | **SP2 tolerated** after HS v5 |
| SP4 + OPEN4004 src12 | busy | — | — | — | — | inconclusive |
| SP3 / Desk knock | busy / reset then **page-timeout** | — | — | — | — | HU powering down |

## FIELD FACTS

1. **F20 is BCL server on SCN 6** (`.87` phone-client): INIT→HS **v5/iid14/0x4000**→SP→KNOCK→OPEN5001→WD. Reproducible across holds+burst.
2. **Transport needs no MyBMW/AAIdrive** — analyzer-only session reaches WD.
3. **HS latency analyzer-direct ≈ 0.3–0.5 s** (Hold2 ~304 ms; Hold1 ~507 ms) — distinct from ~3 s MyBMW/AAIdrive session timing (app/stack overhead, not pure HU INIT RTT).
4. **WD RTT structured:** cluster ~150–165 ms + delayed ~240–360 ms then misses. p50~159 / p95~308 on Hold2. Exact HU WD timeout = **UNKNOWN** (prior miss tooling overwrote pending ping — fixed as FIFO+seq).
5. **DATAACK selective (M48)** — *not* universal per BCL command:
   - SP (10 B) → ACK **10**
   - OPEN empty (8 B) → ACK **8**
   - WD DATA (12 B) → ACK **12**
   - **KNOCK (56 B) → no ACK 56** in any Hold/Burst JSONL today  
   Corrected claim: *when the HU ACKs a frame, `ack_n` matches `8+payload_len`; KNOCK is an exception / different path.*
6. **SP2 after HS v5 → stable WD** (n=1). SP4 not uniquely required for keepalive.
7. **OPEN 4004**: BCL-accepted (ACK 8) but **no Etch/SAS/CDS** in 18 s — content gate **after** OPEN4004.
8. **Hold without iDrive: 0× unsolicited 4004** — Modell A not idle-default.
9. **Parallel Phone↔Dummy + `.87`↔F20 ≠ proxy**; B3 still missing.

## REJECTED / corrected

~~HU DATAACK = 8+len for every received BCL frame~~  

→ **HU DATAACK values for observed *acked* frames match 8+payload_len; KNOCK has no corresponding 56 in these runs.**

## Architecture (transport vs content)

```text
RFCOMM SCN6 → BCL bootstrap (INIT/HS/SP[/KNOCK?]/OPEN5001/WD)   FIELD FACT
OPEN 4004 → ACK 8 → [content authorization UNKNOWN] → SAS/Etch/CDS
```

Dummy opens Etch after OPEN4004; F20 ACKs and stays silent. Lab green ≠ F20 content.

## Cross-ref: OnePlus phone-stack forensic (same day)

Full corpus (8× `bluetooth_20261115_*.log`): [`ONEPLUS_BT_FORENSIC_20261115.md`](../analysis/ONEPLUS_BT_FORENSIC_20261115.md) · evening slice [`BMW_BT_CONNECTION_ANALYSIS_20261115.md`](../analysis/BMW_BT_CONNECTION_ANALYSIS_20261115.md) · stats JSON.

| Phone-log FACT | Aligns with analyzer Hold? |
|----------------|----------------------------|
| HU pages Phone (incoming ACL) | n/a (we were phone-client on `.87`) |
| HS→DATAACK10 silent ≈ **3.0 s** (Phone→HU blind) | Analyzer HS RTT ~0.3–0.5 s = **different plane** (no app stack) |
| One `PORT_WriteDataCO: 56` before ACK10 | Length+timing = **STRONG INFERENCE** KNOCK — **not** FACT (no hex) |
| SCN6 golden; SCN10 only S-A after DM | equal endpoint still **UNKNOWN** |
| First HU DATA→4004 then 667 B CDS | Content under MyBMW — not OPEN4004-alone |
| Textlogs ≠ HCI / SAS invisible | Oppo corpus **exhausted** for Wire-Truth Phone→HU |
| HFP explains content | **no evidence** — deprioritize |

**Bottleneck freeze:** [`FIELD_CONTENT_GATE_BOTTLENECK_20261115.md`](FIELD_CONTENT_GATE_BOTTLENECK_20261115.md) — transport ≠ content auth; locus = blind ~3 s after HS.

## Next (strict order)

1. **P0 `btsnoop_hci` MyBMW S-B** (both dirs, RFCOMM filter off) — resolve INIT/SP/56-B/OPEN/SAS/667.  
2. Optional S-A (SCN6 DM→SCN10 + SDP PDU).  
3. **P1** KNOCK isolation (`--knock none`) / Modell-D — **after** HCI, not instead.  
4. **Stop** OPEN4004-only analyzer spam.

## Lab facts that still stand

| Lab | Still valid? |
|-----|----------------|
| AAIdrive green on Dummy with WD-only / challenge stubs | yes — ≠ F20 SAS |
| Dummy `deadbeef`/PKCS7 Etch | lab-only; not from F20 this burst |
| WD-max3 Dummy keeps UI green | lab UX ≠ F20 miss behavior |
| CoD `0x340408` + alias gate | unchanged |
| SCN 6 first `0x1101`, failover 10 | SDP reconfirmed |
