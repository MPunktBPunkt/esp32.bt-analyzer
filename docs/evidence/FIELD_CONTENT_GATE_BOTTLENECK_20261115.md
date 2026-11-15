# FIELD — Content-gate bottleneck freeze (2026-11-15 evening)

```yaml
claim_level: FREEZE search locus · not a new wire FACT for Phone→HU bytes
sources:
  - docs/analysis/ONEPLUS_BT_FORENSIC_20261115.md
  - docs/analysis/BMW_BT_CONNECTION_ANALYSIS_20261115.md
  - docs/evidence/FIELD_VS_LAB_INSIGHTS_20261115.md
  - docs/evidence/FIELD_P0_HOLD_* / FIELD_BURST_20261115
```

## What is settled

| Item | Stufe |
|------|-------|
| Analyzer→F20 BCL transport (INIT→HS v5→SP→KNOCK→OPEN5001→WD) without MyBMW | **FIELD FACT** |
| MyBMW/AAIdrive golden path S-B: ACL→SCN6→HS→~3.0 s→DATAACK10→DATA 0x0FA4→667 B CDS | **FIELD FACT** |
| HS / DATAACK10 hex on Phone RX | **FIELD FACT** |
| Exactly one `PORT_WriteDataCO: 56` immediately before DATAACK10 | **FIELD FACT** (length+timing) |
| Those 56 B **are** wire_v5 KNOCK UUID envelope | **STRONG INFERENCE** only — no Phone→HU hex in Oppo logs |
| OPEN4004 alone (analyzer) → ACK8 → no Etch/CDS | **FIELD FACT** |
| Oppo `bluetooth_*.log` replace HCI/btsnoop | **REJECTED** |
| HFP required for Connected content | **no evidence** in 15.11. corpus — deprioritize |
| SCN10 = equal BCL endpoint | **UNKNOWN** (S-A failover only) |

## The bottleneck (one sentence)

After HS, the real MyBMW client spends ~**3 s** on Phone→HU traffic that textlogs only show as **byte lengths** (notably **56**); then HU ACKs with **DATAACK10** and opens **0x0FA4 / CDS**. That blind window is the most likely **content-authorization** locus — not further OPEN4004 spam.

```text
Transport Gate (reproduced on .87)     Content Authorization (blind ~3 s)
INIT→HS→SP[/KNOCK]→OPEN5001→WD    →    Phone→HU ??? → ACK10 → Etch/CDS
```

## P0 capture requirement

**`btsnoop_hci` of MyBMW Session S-B** (both directions, RFCOMM filter **off**), optionally S-A (SCN6 DM→SCN10).

Must resolve: INIT / SP2|4 / 56-B payload / OPEN5001 / OPEN4004 / SAS / full 667 B / SDP PDU for ch6|10.

Oppo textlogs have reached diminishing returns for Wire-Truth Phone→HU.
