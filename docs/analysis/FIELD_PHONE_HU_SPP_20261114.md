# Analyse — Phone↔F20-HU SPP/RFCOMM Logcat (2026-11-14)

```yaml
evidence: docs/evidence/FIELD_PHONE_HU_LOGCAT_20261114T0924Z.md
raw_full: docs/bluetooth_20261114_083313_01892.txt
raw_reduced: docs/bmw_aaidrive_field_reduced_20261114.txt
lab_contrast: docs/evidence/LAB_PHONE_BCL_20261113T2201Z_DECODE.md
massnahmen: docs/MASSNAHMEN_BCL_A6.md
verified: recount on reduced log 2026-11-14
```

## Konsens der vier Auswertungen

| Quelle | Stärke | Schwäche |
|--------|--------|----------|
| GPT / Grok | Transport-Pfad 1101→SCN6→OPEN klar | „Nutzdaten UNKNOWN“ zu schwach — Verbose zeigt Größen + **0 HU-RX** |
| Claude | Zählt RX/TX getrennt; Silent-HU; Rollen ACL/Mux; Typ A/B | UID≠AAIdrive noch Hypothese |
| Mistral | Retry-Kadenz 3,00 s vs Lab 2,5 s; Dummy „zu gut“ | HCI-Snoop weiterhin nützlich für Hex, nicht für HU-RX |

**Gemeinsamer FACT-Kern:** echte HU = SPP `0x1101` → SCN 6 → RFCOMM OPEN (DLCI 13). Phone schreibt; HU antwortet auf ch6 mit **0 Bytes**.

## Epistemik-Korrekturen

1. Lange Lab-Sessions mit Pong ≠ „so spricht die echte HU“. Feld = kurze Retry-Fenster.
2. Lab-Watchdog-Frames (`00 02 13 89 … 13 37 13 37`) nicht als HU-Wire lesen.
3. GPT „A2DP-Timeout erklärt kurze Sessions“ → **geschwächt**: A/B-Alternation erklärt die Längen besser.
4. `is_carkit` ohne Adresse im Lab nicht an BMW binden; Auto-Log: durchgängig true.

## Hypothesen-Update

| ID | Vorher | Nach Logcat |
|----|--------|-------------|
| H-A | BCL auf ch6, HU antwortet auf Phone-INIT | Transport ja; **Antwort nein** in diesem State → H-A für *Handshake* geschwächt, nicht für *Kanalwahl* |
| H-B | HU initiiert RFCOMM/BCL | **Mux/ACL ja**, SPP-DLC nein (Phone Client) |
| H-C | MyBMW-State nötig | unverändert offen |
| H-E | ch7–10 | **P0** — `0x1101` trifft immer nur ersten Record (ch6) |

## B2-A-Matrix (neu)

`connectSocket(0x1101)` kann ch7–10 nicht erreichen. Analyzer/`.87` muss Kanal **explizit** wählen:

| Kanal | UUID / Dienst | Aktion |
|------:|---------------|--------|
| 6 | `0x1101` SPP Server 1 | `b2a-tx --channel 6 --init-count N` @ 3 s, hold ≥15 s nach ACL |
| 7 | `0x1101` Server 2 | dasselbe |
| 8 | Server 3 | dasselbe |
| 9 | Server 4 | dasselbe |
| 10 | Server 5 | dasselbe |
| 5 | `deca-fade` | **nicht** BCL; optional Referenz |

Erfolgskriterium pro Kanal: UA + erste UIH-Klassifikation (`bcl_classify`). Negativ auf allen fünf = H-E geschwächt für diesen State.

## Lab-Folgen

- Dummy-Option **Silent-HU**: kein HANDSHAKE, kein WD-Pong → erwartet Typ A (56 B/~10 s) und Typ B (5×4 B/3 s).
- Pong-Modus bleibt für C-L11/Wire-Vergleich, ist aber **nicht** F20-default.
- Feld-Kadenz 3,0 s vs Lab-Wire 2,5 s dokumentieren (kein Desk-5 s).
