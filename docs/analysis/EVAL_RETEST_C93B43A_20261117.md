# Bewertung Retest `c93b43a` — 2026-11-17

**claim_level:** Lab PASS · USB air PARTIAL · checkResource-Reply OPEN (Fall A–D)  
**Bezug:** `docs/evidence/LAB_RETEST_LIFECYCLE_20261117.md` · Audit `AUDIT_RHMI_RESOURCE_LIFECYCLE_20261117.md`

## Executive

| Gate | Status |
|------|--------|
| Lab-Lifecycle / Cache-Miss/Hit | PASS |
| `wd_miss_limit=0` (Diagnose, kein Produktfix) | PASS |
| USB→`.131`→Air bis `checkResource` TX | PARTIAL |
| Dual-ESP | FAIL (separat) |

**Kern:** `wd_miss_limit=0` entfernt nur den künstlichen Abort. Es erklärt nicht die fehlende sichtbare Antwort auf `checkResource`.

Ungültige Kausalitäten:

- ~~`checkResource(true) → setResource fehlt → WD`~~  
- ~~WD-Limit zu streng~~  

Aktuell:

```text
checkResource TX → Reply unsichtbar/unverarbeitet/ausbleibend → WD-Misses
```

## Primärer Fehlerbaum (W0)

| Fall | Symptom | Ebene |
|------|---------|--------|
| **A** | kein HU→Phone BCL nach check TX | Request-Format / HU |
| **B** | F20 TX, `.131` kein RX | BT/HCI/RFCOMM |
| **C** | `.131` RX, Analyzer ohne BCL | Reassembly/Parser |
| **D** | Etch da, `inReplyTo` unmatched | Correlation |
| **E** | `true` → kein setResource | **kein Fehler** (Cache-Hit) |

## W0-Pflicht

Drei Roh-Ebenen parallel: HCI/RFCOMM · BCL · Etch.  
Transaktionstabelle mit `messageId`/`inReplyTo`/`(src,dest)`/`result`.  
Watchdog ≠ RHMI-Kanal. Dual-ESP getrennt.

## Lab vs Feld

Lab härtet Client/Simulator/Analyzer (State Machine, Cache-Matrix, Fault Injection, Replay).  
Lab ersetzt **nicht** F20-Autorisierung / Serien-Resource-Accept.

## Gate-Kette

W0 Raw-RX → W1 check-Sequenz → W2 Hit/Miss F20 → W3 initialize → W4 setData → W5 Property → W6 Action → W7 PiDrive.
