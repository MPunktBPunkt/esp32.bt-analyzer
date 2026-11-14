# FIELD — B2-A-TX ch6 + OPEN Etch 4004 + Wire-OPEN5001 (2026-11-14 ~15:39)

```yaml
id: FIELD_B2A_TX_CH6_ETCH_20261114T1539Z
kind: field_b2a_tx_etch
verdict: BCL_FIELD_CONFIRMED · WD live · Etch HU-RX = empty
hold_s: 180
selectproto: 2
wire_open5001: true
open_etch: true
etch_src: 10
wd_interval: 2.5
peer: D4:36:39:CF:E1:B5
local: C8:C9:A3:CB:37:96
```

## Verdict

| Schritt | Ergebnis |
|---------|----------|
| HS v5 / iid14 | ja |
| SP(2)+KNOCK | ja |
| OPEN 5001 `src=dst=5001` | ja → HU-WD-Echo ebenfalls **src=dst=5001** |
| OPEN 4004 `src=10` | TX ja (`0001000a0fa40000`) |
| HU → Etch / `deadbeef` / PKCS7 | **nein** (0 Frames dest/src 4004) |
| WD 180 s | **70** Pings · RX **1732 B** · DATAACK `0x0C`×70 |

**Kern:** Die echte HU hält den Watchdog, **initiiert aber kein Etch**. OPEN 4004 allein reicht nicht — Cert/Etch-Push kommt von der **App** (Lab: MyBMW/AAIdrive → Dummy). Extra DATAACK `0x08` nach OPEN 4004 = vermutlich Accept des Ports, ohne Payload.

## TX (nach HS)

```
SP(2)
KNOCK
OPEN 5001  0001138913890000
OPEN 4004  0001000a0fa40000
WD DATA    src=5001 dest=5001  13371337  @2.5s
```

## RX-Profil

| Frame | n | Bedeutung |
|-------|--:|-----------|
| HANDSHAKE v5 | 1 | |
| DATAACK `0x0A` | 1 | |
| DATAACK `0x08` | 2 | eine mehr als ohne Etch-OPEN |
| DATAACK `0x0C` | 70 | pro WD |
| DATA `13371337` (5001↔5001) | 70 | HU-Echo |

## Folgerung

1. Analyzer kann F20-BCL **Transport+WD** allein.
2. Layer E (Etch/SAS/RHMI) braucht App-Zertifikatspfad oder Proxy — nicht von der HU unsolicited.
3. Nächster Sprung: Phone-HCI während AAIdrive-grün **oder** Etch-Payload aus Lab-Capture an dest 4004 replayen (nur nach Klassifikation).
