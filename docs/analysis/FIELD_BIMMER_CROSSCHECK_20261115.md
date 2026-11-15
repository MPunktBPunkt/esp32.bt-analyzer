# BimmerGestalt@7cfd959 vs F20/MyBMW wire (2026-11-15)

Pins: BclCarLink `7cfd959` · Feld [`FIELD_AAIDRIVE_BTLOG_20261115`](../evidence/FIELD_AAIDRIVE_BTLOG_20261115.md) · Silent-HU [`LAB_SILENT_HU_INIT_KNOCK_20261115`](../evidence/LAB_SILENT_HU_INIT_KNOCK_20261115.md) · Facts C-BT23–30 / C-L14.

## Abgleichstabelle

| Thema | BclCarLink Desk | F20 / MyBMW Wire | Urteil |
|-------|-----------------|------------------|--------|
| INIT | `output.write("12345678".decodeHex())` | Silent-HU: alle 4‑B = `12345678` | **MATCH** LAB FACT |
| HS fields | version / instanceId / bufferSize | v5 / iid=14 / buf=`0x4000` | **MATCH** Layout; Werte Wire |
| SELECTPROTO | if version>3 → SP(**3**) | Lab/Feld nach v5 → SP(**4**) | **DESK STALE** |
| KNOCK | empty serial, appType **0** (A4A), param1 **1**; Kommentar „sonst 1+7“ | Wire: UUID-Serial + TouchCommand(**1**)/ **7** | **DESK DEFAULT ≠ Wire**; Kommentar trifft Wire |
| 56‑B Silent blob | — | `deadbeef` envelope + UUID-Serial, **kein** cmd=8 Header | KNOCK-**related** INFERENCE; ≠ `BclPacket.Knock` wire frame |
| Watchdog | INTERVAL **5000**, DATA `13 37 13 37`, TO **20000** | Lab ≈**2,5 s**; Feld-„3 s 4‑B“ = INIT nicht WD | **DESK ≠ Wire**; Silent-HU kalibriert keine WD-Timer |
| DATAACK | `DataAck(8 + packet.data.size)` per received packet | 8 (OPEN), 44 (small DATA) fit; large values open | **Best model**; not cumulative counter |
| OPEN 4004 | Consumer-triggered (`EtchProxy` / :4007) | Working session reaches DATA→4004 + CDS | Tunnel+Consumer path **FIELD** |
| dest Etch/WD | 0x0FA4 / 0x1389 | dest 4004 FIELD; WD not in oplus HU→app dumps | Etch **MATCH** |
| SAS | outside BclCarLink (AAIdrive/MyBMW) | not visible in oplus dumps | **UNKNOWN** → btsnoop |
| BclOutputStream bugs | C-D27 | n/a for capture | don't treat as gold encoder |

## Code anchors (7cfd959)

```kotlin
// BclClientTransport.initSession
output.write("12345678".decodeHex())

// selectProtocol — Desk forces 3 even on v4/v5 HS
if (version > 3) {
    packetOutput.writePacket(BclPacket.Specialized.SelectProto(3.toShort()))
    doKnock()  // empty serial, appType=0, param1=1
}

// readPacket — DATAACK = full BCL frame size
packetOutput.writePacket(BclPacket.Specialized.DataAck(8 + packet.data.size))
```

```kotlin
// WatchdogProtocol
WATCHDOG_DATA = 0x13,0x37,0x13,0x37
WATCHDOG_INTERVAL = 5000
WATCHDOG_TIMEOUT = 20000
```

## Lohnt sich weitere Tiefenanalyse der Text-Logs?

**Nein** als primärer nächster Schritt.

- Hex-Coverage ≈ **1,65 %**; Cap 32 B; Phone→HU fehlt komplett.
- INIT/KNOCK/DATAACK/CDS-Fragmente sind epistemisch ausgeschöpft.
- Marginaler Nutzen: weitere ASCII-Splitter aus 667‑B-Mittelstücken — ändert die Roadmap nicht.

**Ja** unmittelbar nach **`btsnoop_hci`** derselben Session: dann paketgenaue Direction/BCL/Etch/SAS-Rekonstruktion und Type-ID-Mapping.

## Konsequenz für unseren Client/Dummy

Nach HS v5 modellieren: **SP(4)+KNOCK(UUID,1,7)**, WD≈2,5 s, DATAACK=`8+len`, non-zero SAS-Challenge.
Desk-SP(3)/empty-Knock/WD-5 s nur als BclCarLink-Kompatibilität, nicht als F20-Gold.
