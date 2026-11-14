# FIELD — Echte HU sendet BCL-HANDSHAKE v5 (2026-11-14 ~11:13)

```yaml
id: FIELD_PHONE_HU_BCL_HS_V5_20261114T1113Z
kind: field_logcat_bcl_payload
peers: OnePlus ↔ HU D4:36:39:CF:E1:B5 · Dummy …:7B:0A (gleicher Capture)
window: ~10:44–11:24 (Session id 96: 11:13:52–11:14:17 ≈25 s)
source_report: Grok-Auswertung eines weiteren Phone-BT-Logs (nicht die 083313/103731-Captures)
raw_cleaned_expected: docs/bluetooth_20261114_104405_CLEANED.log  # noch nicht im Repo
raw_original_note: ~26 MB / 166 k Zeilen → CLEANED ~4.1 MB / ~23.8 k (Grok-Pfad /home/workdir/artifacts/…)
related_empty_hci: docs/BT_HCI_2026_1114_104405.cfa  # nur Header; Filter an
analysis: docs/analysis/FIELD_B2A_TX_PATTERNS_20261114.md
verified:
  hex_decode: local struct/framer 2026-11-14 (cmd/version/iid/buf)
  raw_lines: PENDING — CLEANED-Log noch nicht ingestiert
```

## Verdict

| Ebene | Status | Aussage |
|-------|--------|---------|
| Hex → HANDSHAKE-Felder | **DECODE OK** | `cmd=4 len=8` → v5 / iid `0x0E` / buf `0x4000` |
| HU→Phone BCL-HS im Capture | **REPORTED** | Session id 96, peer `e1:b5` — roh ausstehend |
| Dummy-HS v3 im selben Log | **REPORTED** | v3 / iid 1 / buf `0x8000` (Lab-Profil) |
| cmd `0x0006` HU→Phone | **REPORTED** | Desk-Name **DATAACK** (nicht OPEN/SELECTPROTO) |
| Session-Stabilität HU | **REPORTED** | ~25 s CLOSE; kein Dummy-artiger WD-Strom |
| Wire-HCI (btmon/snoop) | **UNKNOWN** | `.cfa` leer; Filter war an |

**Kern:** Wenn die Session-Zeilen stimmen, spricht die **echte F20 BCL** — mindestens den Handshake — mit einem **anderen Fingerprint** als der Dummy. Das verschiebt H-A von „HU antwortet nie“ zu „HU kann HS; Post-HS / Stabilität offen“.

## Decode (lokal gegen `bcl_framer` / `bcl_dummy_hu.parse_handshake`)

Header: `cmd u16 | dest u16 | src u16 | len u16 | payload`.

| Peer | Hex | cmd | payload | Felder |
|------|-----|----:|---------|--------|
| **HU `e1:b5`** | `00 04 00 00 00 00 00 08 00 05 00 0E 00 00 40 00` | 4 HANDSHAKE | 8 B | **version=5**, **instanceId=0x0E (14)**, **bufferSize=0x4000** |
| **Dummy `7b:0a`** | `00 04 00 00 00 00 00 08 00 03 00 01 00 00 80 00` | 4 HANDSHAKE | 8 B | version=3, instanceId=1, bufferSize=0x8000 |
| HU | `00 06 00 00 00 00 00 04 00 00 00 0A` | **6 DATAACK** | 4 B | payload `00 00 00 0A` |
| HU | `00 06 …` + `00 02 13 89 … 13 37 13 37` | 6 + Fragment | — | DATAACK + WD-Fragment (Stream-Koaleszenz? roh prüfen) |

Desk-Bezug: `instanceId` 12–14 = HU→Phone-Fingerprint (`HU-Technical-Facts` C-L*); **0x0E=14** passt.  
`version>3` → Desk-Branch SELECTPROTO(3)+KNOCK (`C-D29`) — Wire nach HS v5 noch **UNKNOWN**.

**Korrektur zu Grok M19:** cmd 6 ist im Framer **DATAACK**, nicht OPEN (1) / SELECTPROTO (5). Bedeutung am F20 weiter offen.

## Abgleich mit bereits ingestierten Logs

| Capture | HU DataInd / `data_hex` auf SCN6 | BCL-HS von HU |
|---------|----------------------------------|---------------|
| `…083313…` / `…103731…` | 0× dlci13 DataInd; keine HS-Hex an App | **nein** (silent nach OPEN) |
| dieses Log (Grok) | `send_data_to_app` / `data_hex` | **ja — HS v5** |

Frühere „0 RX“-FACTS bleiben für **jene** Captures gültig. Neu: es gibt mindestens einen HU-State, in dem BCL-HS die App erreicht.

## Muster M16–M19

| ID | Muster | Status |
|----|--------|--------|
| **M16** | Echte HU liefert BCL-HANDSHAKE (v5) | **REPORTED / DECODE OK** |
| **M17** | HS-Parameter peer-/versionsabhängig (Dummy v3 vs HU v5) | **REPORTED** |
| **M18** | HU-Session bleibt kurz (~25 s) | **REPORTED** |
| **M19** | cmd 0x0006 HU→Phone = **DATAACK** (Desk); Semantik offen | **REPORTED + Name korrigiert** |

## Nicht bewiesen (auch wenn roh bestätigt)

- Stabiler WD-Echo / OPEN 5001 / Etch zur echten HU
- Ob AAIdrive den Kanal schließt oder die HU
- Analyzer-`.87` kann denselben HS erzwingen
- HCI-Wire-Bytes (nur Stack→App-Dump berichtet)

## Ingest-Checkliste

1. `docs/bluetooth_20261114_104405_CLEANED.log` ins Repo legen (≤ GitHub-Limit).
2. Recount: Sessions scn6 × peer; alle `data_hex` mit peer `e1:b5` / `7b:0a`.
3. Session 96 Zeile-für-Zeile gegen Tabelle oben.
4. Danach Status REPORTED → **FIELD FACT** anheben.

## Nächste Schritte

1. **P0** CLEANED-Log ingestieren + recount.
2. **P0** Phone HCI-Snoop (RFCOMM-Filter **aus**) während HS-v5-Fenster.
3. Lab: Dummy optional `--hu-version 5` / iid 14 / buf `0x4000` — Phone-Branch nach v5 beobachten.
4. P0.5 2×2-Matrix unverändert (Admission UA|DM).
