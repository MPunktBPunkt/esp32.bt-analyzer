# FIELD — OnePlus ↔ echte BMW-HU (Logcat, 2026-11-14 ~09:24)

```yaml
id: FIELD_PHONE_HU_LOGCAT_20261114T0924Z
kind: field_logcat
peers: OnePlus 12 (AC:C0:48:5E:CB:20) ↔ HU D4:36:39:CF:E1:B5 (BMW 38304, CoD 0x340408)
window: RFCOMM-Aktivität ~09:24:54–09:27:33 (Capture ~08:33–09:27)
source: Android BT-Stack Verbose Logcat (operator)
raw_full: docs/bluetooth_20261114_083313_01892.txt  # 11.8 MiB / 73566 lines
raw_reduced: docs/bmw_aaidrive_field_reduced_20261114.txt  # 2.2 MiB / 12967 lines
analysis: docs/analysis/FIELD_PHONE_HU_SPP_20261114.md
verified: 2026-11-14 local recount on reduced log
cross: C-BT15…C-BT20 · C-D28/C-D30 (pidrive HU-Technical-Facts)
consensus: GPT+Grok (Transport) · Claude+Mistral (Silent-HU + Retry-Kadenz)
```

## Verdict (kurz)

| Ebene | Status | Aussage |
|-------|--------|---------|
| SPP UUID `0x1101` | **FIELD FACT** | HU bietet den Dienst |
| SDP → SCN **6** | **FIELD FACT** | App findet denselben Kanal wie Lab/B1 |
| RFCOMM OPEN (UA) | **FIELD FACT** | ≥10 erfolgreiche Opens (ids 12–21) |
| Phone = RFCOMM-Client | **FIELD FACT** | UID **10479**, `is_server=false`, DLCI **13** |
| Phone TX auf ch6 | **FIELD FACT** | Größen sichtbar: **5×56 B** + **24×4 B** |
| HU RX auf ch6 | **FIELD FACT empty** | **0×** `PORT_DataInd` / UIH-Daten auf DLCI 13 |
| BCL-Inhalt | **UNKNOWN** | kein `data_hex`; 4 B/56 B nur Größen-Inferenz |
| Session-Stabilität | **MEASURED** | A/B-Alternation ~10 s / ~15 s, Retry |

**Kern:** Transport-Pfad ist gegen die echte F20-HU reproduziert. Die HU bleibt auf SCN 6 in diesem Zustand **stumm**. Lab-Dummy mit `--echo-watchdog` ist „zu gut“ gegenüber dem Feld.

## Session-Tabelle (Konsens Claude/Mistral)

| id | open | close | Dauer | Phone TX |
|----|------|-------|------:|----------|
| 12 | 09:25:02.58 | 09:25:04.13 | 1,55 s | 1× 56 B |
| 13 | 09:25:08.28 | 09:25:23.33 | 15,05 s | 5× 4 B @ 3,000 s |
| 14 | 09:25:27.45 | 09:25:37.15 | 9,71 s | 1× 56 B |
| 15 | 09:25:41.20 | 09:25:56.23 | 15,03 s | 5× 4 B |
| 16 | 09:26:00.40 | 09:26:10.32 | 9,93 s | 1× 56 B |
| 17 | 09:26:14.59 | 09:26:29.64 | 15,05 s | 5× 4 B |
| 18 | 09:26:33.93 | 09:26:43.71 | 9,78 s | 1× 56 B |
| 19 | 09:26:48.02 | 09:27:03.05 | 15,03 s | 5× 4 B |
| 20 | 09:27:07.27 | 09:27:17.16 | 9,89 s | 1× 56 B |
| 21 | 09:27:21.34 | Log-Ende | ≥9 s | 4× 4 B (5. fehlt) |

**Typ A (~10 s):** einmal 56 B nach OPEN → Pause → CLOSE.  
**Typ B (15,0 s):** 5× 4 B alle **3,000 s** → CLOSE genau 3 s nach 5. Ping.  
Zyklus A→~4 s→B→~4 s→A, Periode ≈ 33 s.

## RFCOMM-Parameter (Feld)

| Parameter | Wert |
|-----------|------|
| SCN | 6 |
| UUID | `0x1101` |
| DLCI | 13 (Mux von HU geöffnet → Phone ungerade DLCI) |
| MTU / N1 | 666 / 667 (einmal 660) |
| Credits | k=7, cl=`0xE0` |
| Flow | Credit Based |
| HU LMP | 6 (BT 4.0), Manufacturer `0x000D`, Subversion `0x1b76` |
| is_carkit | true (449× true / 0× false im Auto-Log) |

## ACL / Mux (Rollen)

- ACL: `initiator:remote` (~09:24:48) — **HU** baut die Classic-Verbindung auf.
- L2CAP PSM 3: Request von remote — **HU** öffnet den RFCOMM-Multiplexer.
- Phone: nur SPP-DLC (`connectSocket` UUID 1101 → SDP SCN 6 → SABM).
- Vor erstem UA: **5× DM** (~09:24:54–09:25:01); UA ~13,7 s nach ACL, nach A2DP/AVRCP-Aufbau der HU.

## Was **nicht** behauptet wird

- Bytes der 4 B-Pings = `13 37 13 37` — **Inferenz** (Größe+Kadenz), kein Hex.
- 56 B = DEADBEEF-Probe / SELECTPROTO — **Inferenz** (Lab-Größe), kein Hex.
- UID 10479 = AAIdrive — **verhaltenstypisch**, Package-Mapping noch `adb … \| grep 10479`.
- BCL auf ch6 in diesem Zustand — **unproven**; HU silent spricht eher gegen aktives BCL-Handshake.

## Recount (reduced log, verified)

| Metric | Count |
|--------|------:|
| `SetRfcommPortOpen` uuid `0x1101` | 10 |
| `on_cli_rfc_connect` scn 6 | 10 |
| `RFC_PORT_EVENT_DM` (pre-accept) | 5 |
| `PORT_WriteDataCO: 4 bytes` | 24 |
| `PORT_WriteDataCO: 56 bytes` | 5 |
| `PORT_DataInd` dlci 13 | **0** |
| `PORT_DataInd` dlci 8 (HFP) | 28 |
| `Is carkit: true` / `false` | 449 / 0 |
| ACL role at connect | **peripheral** (HU pages Phone) |

## Nächste Schritte (Priorität)

1. **B2-A-TX Matrix** ch **6–10**: INIT `12 34 56 78` im 3‑s-Takt, Start ≥15 s nach ACL (siehe `CAR_FIELD_1H.md`).
2. Optional: HCI-Snoop mit RFCOMM-Filter **aus** — Hex der 4/56 B; HU-RX auf ch6 ist per Verbose-Logcat bereits leer belegt.
3. Lab: **Silent-HU-Modus** (kein HS/Pong) → Retry A/B (10 s / 5×3 s) nachbilden.
4. `adb shell cmd package list packages -U | grep 10479` — Package hinter UID.
