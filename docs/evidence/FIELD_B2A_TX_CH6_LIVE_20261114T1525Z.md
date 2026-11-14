# FIELD — B2-A-TX ch6 LIVE → HU HANDSHAKE v5 (2026-11-14 ~15:26)

```yaml
id: FIELD_B2A_TX_CH6_LIVE_20261114T1525Z
kind: field_b2a_tx
verdict: BCL_FIELD_CONFIRMED
peer: D4:36:39:CF:E1:B5 (BMW 38304)
local: C8:C9:A3:CB:37:96 (BT-Analyzer-Phone / hci1 / .87)
precondition: ACL UP · AUTH · ENCRYPT · A2DP sink bluez_output.D4_36_39_CF_E1_B5
mode: controlled_init (init×5, full_client=false, 45 s)
btsnoop: FIELD_B2A_TX_CH6_LIVE_20261114T1525Z.btsnoop
followup: FIELD_B2A_TX_CH6_FULL_20261114T1528Z
```

## Verdict

| Stufe | Ergebnis |
|-------|----------|
| RFCOMM SABM→UA ch6 | **PASS** (`accepted: true`, DM=0) |
| Phone TX INIT | `12 34 56 78` (1× ausreichend) |
| HU RX HANDSHAKE | **`00 04 … 00 08 00 05 00 0E 00 00 40 00`** |
| Felder | **version=5 · instanceId=14 (0x0E) · bufferSize=0x4000 (16384)** |
| Klassifikation | **`BCL_FIELD_CONFIRMED`** |
| Nach HS | 44,9 s RX-Stille (kein full-client) · DISC local |

**Kern:** Erstmals **mit unserem Tool** auf der echten F20: Analyzer-DLC akzeptiert **und** HU antwortet mit BCL-HS v5. Morgens Matrix = DM; jetzt = UA+HS → Admission-Gate **zustandsabhängig** (M7) ist FACT.

## Timeline (JSONL)

| t | Event |
|---|--------|
| 0 | `rfcomm_connected` ch6 |
| +0 | TX INIT `12345678` |
| +0,21 s | RX 16 B HANDSHAKE v5/iid14/buf0x4000 |
| ~45 s | `phone_done` active · closed_by_local |

## Kontrast

| Lauf | State | ch6 |
|------|-------|-----|
| Matrix AUDIOOK ~11:15 | A2DP OK, anderer Context | **DM / refuse** |
| Dieses LIVE | ACL+AUTH+ENCRYPT, Analyzer-A2DP | **UA + HS v5** |
| Phone-Logcat (Grok) | App-Pfad | HS v5 **REPORTED** → hier **FACT** |
