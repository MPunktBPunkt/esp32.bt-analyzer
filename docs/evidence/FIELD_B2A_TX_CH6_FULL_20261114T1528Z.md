# FIELD — B2-A-TX ch6 FULL-CLIENT nach HS v5 (2026-11-14 ~15:28)

```yaml
id: FIELD_B2A_TX_CH6_FULL_20261114T1528Z
kind: field_b2a_tx_full
verdict: BCL_FIELD_CONFIRMED
peer: D4:36:39:CF:E1:B5
local: C8:C9:A3:CB:37:96 (hci1)
mode: controlled_init + full_client (SELECTPROTO/KNOCK/OPEN 5001), 60 s
prior: FIELD_B2A_TX_CH6_LIVE_20261114T1525Z
btsnoop: FIELD_B2A_TX_CH6_FULL_20261114T1528Z.btsnoop
```

## Verdict

HS v5 erneut → Desk-Branch `version>3` ausgeführt. HU antwortet mit **2× DATAACK**, danach RX-Stille bis Session-Ende. Kein WD-Pong / kein weiteres OPEN 4004 in diesem Fenster.

| Richtung | Hex / Decode |
|----------|----------------|
| → HU | INIT `12345678` |
| ← HU | HS v5 / iid 14 / buf `0x4000` |
| → HU | SELECTPROTO **3** `00050000000000020003` |
| → HU | KNOCK (12 B payload) `00080000…0001` |
| → HU | OPEN dest **5001** (`0x1389`) `0001000113890000` |
| ← HU | DATAACK `0000000a` |
| ← HU | DATAACK `00000008` |
| — | ~60 s hold, `rx_silence` nach letztem ACK · DISC local |

## Wire (btsnoop decode)

- SABM×1 UA×1 UIH×8 DISC×1 · DM=0
- bytes_local 42 · bytes_remote 40
- `bcl_classification` remote: **BCL_FIELD_CONFIRMED**

## Offene Fragen

- Semantik DATAACK `0x0A` / `0x08` (M19)
- Ob HU nach SP(3)+KNOCK+OPEN5001 WD erwartet / anders branch’t (Wire Dummy nutzte SP(**2**))
- Etch / OPEN 4004 — nicht gesehen
- Stabiler WD-Zyklus — nicht gesehen (`active=true` nur client-seitig)

## Nächster Feldschritt (solange Auto online)

1. A/B: full-client mit **SELECTPROTO(2)** statt 3 (Dummy-Wire) — Code-Hebel oder manueller TX.
2. Längerer Hold + WD-Pong-Echo falls HU `13 37` sendet.
3. 2×2 nur noch für Admission DM-Zellen; ch6+INIT ist in **diesem** State grün.
