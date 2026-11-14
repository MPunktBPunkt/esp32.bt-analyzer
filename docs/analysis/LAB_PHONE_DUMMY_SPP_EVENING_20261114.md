# Analyse — Abend-BT-Logs Phone↔Dummy `.131` (2026-11-14)

```yaml
evidence: docs/evidence/LAB_PHONE_DUMMY_BTLOGS_20261114T1732Z.md
field_contrast: docs/evidence/FIELD_PHONE_HU_LOGCAT_20261114T0924Z.md
lab_wire: docs/evidence/LAB_PHONE_BCL_20261113T2201Z_DECODE.md
massnahmen: docs/MASSNAHMEN_BCL_A6.md
```

## Was die vier Files sind

Jeder Upload startet mit `BluetoothAdapterService` / `offToBleOn` → **ein BT-an-Zyklus**. BT-aus beendet den vorherigen Capture (nächste Datei = nächster Versuch). L3 ist nur Stack-Start ohne Peer-Arbeit.

Operator-Skript (BT an → connect → AAIdrive → MyBMW → grün → BT aus) ist in L1/L2 als **grünes Dummy-BCL** belegt; in L4 als **Retry gegen toten SPP-Server**, bis der Lab-HU-Agent wieder lief.

## Scharfer Kontrast: antwortender Dummy vs. stumme F20-HU

| Merkmal | Abend Lab Dummy (L1) | Morgen Feld HU |
|---------|----------------------|----------------|
| Peer | `…:7B:0A` `.131` | `…:E1:B5` F20 |
| Opener | UID **10479** | UID **10479** |
| UUID / SCN | `0x1101` / **6** | `0x1101` / **6** |
| DLCI | **12** (Phone-Mux) | **13** (HU-Mux) |
| Nach OPEN | 4 → 56 → **Cert-Burst** → **`12` @ 2,50 s** | Typ A `56`@~10 s / Typ B `4`@**3,00 s** |
| Peer RX auf SPP | **80×** DataInd dlci12 | **0×** DataInd dlci13 |
| Session | Minuten (bis BT aus) | 1,5–15 s Retry-Loop |
| UI „grün“ | passt zu Live-WD+Certs | Feld: Transport OPEN, App gibt auf |

**Schluss:** Dieselbe App (UID 10479) fährt **zwei Wire-Modi**:

1. **Silent-Peer-Modus** (Feld-HU): nur Probe/INIT-Retries, kein Cert-Burst, 4 B@3 s, kein RX.
2. **Live-BCL-Modus** (Dummy mit HS/Pong/Etch): nach positivem Handshake Cert-Upload + 12 B@2,5 s + dauerhaft RX.

Der 12‑Byte-Takt ist die **Lab-Wire-Watchdog-Kadenz** (vgl. `LAB_PHONE_BCL_*` ≈2,5 s). Die 4 B@3 s im Feld sind der **Pre-Handshake-/Silent-Retry**, nicht der Live-WD.

## AAIdrive adressiert den Dummy, nicht die echte HU

In allen Abend-Files: `connectSocket` / `btsock_connect` für SPP `0x1101` nur an `7B:0A`.  
`E1:B5` erscheint nur als **ACL-Page-Versuche** (Bonded-Car / MyBMW-Stack), ohne SPP.

→ Solange beide als „BMW 38304“ gebunden sind, entscheidet die App-/Bond-Auswahl, welcher Peer BCL bekommt. Abend = Dummy gewählt.

## L4 als Negativkontrolle (Dummy-HU tot)

62 Connect-Versuche, 59× Cleanup mit `scn: 0` (kein brauchbarer SDP/RFCOMM-Endpoint), 1× OPEN erst nach Agent-Restart — Session stirbt nach 1×4 B (~0,7 s).

Das erklärt den User-Report „mehrmals versucht, nicht mit AAIdrive verbunden“: **ACL kann stehen, SPP-Server nicht.**

## Nebenbefund `b7:21` / uid 10464

Fremdgerät mit eigenem SPP (`scn 16`, proprietary UUID). Erzeugt Rauschen (47/990‑Byte-Writes, DataInd dlci 33). Bei Zählungen immer nach **Peer-Tail / uid / scn** filtern.

## Epistemik

| Claim | Status |
|-------|--------|
| UID 10479 öffnet Dummy-SPP ch6 | **FACT** |
| Grün = Certs + WD `12`@2,5 s + Dummy-RX | **FACT** (Größen/Kadenz/DataInd) |
| 4 B = `12 34 56 78`, 12 B = WD-Frame, 990 B = Cert-Chunks | **starke Inferenz** (Lab-HU-JSONL parallel; kein Hex im Logcat) |
| Feld-HU silent vs Dummy live = App-State-Machine | **FACT-Verhalten**, Ursache HU-seitig weiter offen |
| MyBMW nötig für Grün | **unproven** in diesen Logs (MyBMW war an; ohne A/B) |

## Folgen für Lab / Feld

1. **Silent-HU-Modus** im Dummy bleibt P1: muss Feld-Retry (4@3 s / 56@10 s) erzeugen, nicht den 12@2,5‑Live-Pfad.
2. Live-Dummy (HS+Pong+Etch) kalibriert den **Grün-Pfad** — Abend-Logs sind die Phone-seitige Bestätigung.
3. Feld: HCI-Snoop weiter nur für Hex; HU-RX=0 schon logcat-FACT.
4. Bei parallelem Bond Dummy+F20: immer Peer-MAC in Evidence nennen.
