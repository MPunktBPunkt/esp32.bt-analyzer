# LAB — SAS probe stages + DATAACK 8+len (2026-11-15)

## Epistemic scope

Das Lab kann testen, **welche App-Layer-Antworten das Phone benötigt**.
Es kann **nicht** aus sich heraus den echten SAS-/RHMI-Ablauf rekonstruieren.

Bekannt (FIELD/LAB FACT): BCL INIT, HS v5/iid14/0x4000, SP4, KNOCK UUID/TouchCommand,
DATAACK=`8+payload_len`, CDS-artige HU→Phone-Fragmente, Lab-BCL-Transport.

**UNKNOWN:** SAS-Challenge-Struktur, Login-Antwort, RHMI-Capability-Wire, volle CDS-Messages.
Erwartung „formalen SAS-Handshake durchbekommen“ = **nicht** dokumentiert.

## DATAACK = 8 + payload_len (FIELD FACT)

| count | = 8+len | matches |
|------:|---------|---------|
| 10 | 8+2 | SELECTPROTO |
| 44 | 8+36 | KNOCK body / small DATA |
| 4008 | 8+4000 | BCL `MAX_PAYLOAD` fragment |

Dummy: `dataack_count_for_frame` / `DATAACK(8+len)` per RX frame (not cumulative).

## SAS probe ladder (`--sas-probe`) — P0

Stufe für Stufe. Bei Interesse **einfrieren**, JSONL sichern, dann erst nächste Stufe.

| Stage | CLI | Dummy on OPEN 4004 |
|-------|-----|--------------------|
| (i) | `--sas-probe none` | no etch DATA (WD/HS only) — Kontrollgruppe; **2026-11-15: AAIdrive trotzdem grün** ([LAB_SAS_NONE_GREEN](LAB_SAS_NONE_GREEN_20261115.md)) — VIN/Daten ≠ Dummy-TX |
| (ii) | `--sas-probe dataack` | DATAACK only; stub silent |
| (iii) | `--sas-probe challenge` | non-zero SAS-challenge |
| (iv) | `--sas-probe challenge_rhmi` | challenge + RHMI stub |
| (v) | `--sas-probe adaptive` | challenge; RHMI erst nach Phone etch TX |

Jede Phone-Reaktion vollständig erfassen. jsonl-Korrelation:

```
OPEN 4004 → HU TX → Phone RX/TX → DATAACK → nächste Phone-Aktion → HU-Antwort → Ende/Fortsetzung
```

Events: `phone_tx_classified`, `sas_challenge_tx`, `sas_login_rx` (heuristic),
`cds_property_*`, `rhmi_capabilities_tx`, `etch_data_tx`, `dataack_tx`.

## P1 — Adaptive / field-shape / WD / SCN

| Flag | Zweck |
|------|--------|
| `--sas-probe adaptive` | classify→react; RHMI escalate nach Phone TX |
| `--etch-reply-src 12` | HU etch DATA als `src=N dest=4004` (Feld-Experiment) |
| `--hu-open-srcs 10,12,18` | nach KNOCK HU-initiierte OPEN→4004 |
| `--wd-pong-delay N` | WD-Pong verzögern (Timeout messen) |
| `--wd-pong-max N` | nach N Pongs stoppen |
| `--channel-refuse 6` + `--channel 10` | SCN6 sofort schließen, BCL auf SCN10 (Failover-Probe; kein echtes DM; BlueZ kann 2×0x1101 ablehnen) |

## Run (Dummy host)

```bash
# upload tools then, stage ladder:
python3 bcl_dummy_hu_agent.py hu --hu-profile f20 --channel 6 \
  --name 'BMW 38304' --sas-probe none --handshake-delay 3 \
  --log /tmp/bcl_dummy/hu_probe_i.jsonl --ready /tmp/bcl_dummy/hu.ready --hold 300

# then dataack | challenge | challenge_rhmi | adaptive
# optional field-shape:
#   --etch-reply-src 12 --hu-open-srcs 10,12,18
# SCN failover probe:
#   --channel 10 --channel-refuse 6
```

Or: `lab_bcl_dummy_hu_a2dp.py --peer external --hu-profile f20 --seconds 180`.

## Also shipped

- Field CDS names: `sensors.SOCBattery`, `_ENT_MTP_OFF`, `iva_MYV_LIGHT_INTERIOR`, VIN stub
- Accept KNOCK as cmd=8 **or** Silent-HU `deadbeef`+UUID envelope (`knock_envelope_rx`)
- `--handshake-delay` (~3 s field realism)
- `bcl_phone_tx_classify.py` → `phone_tx_classified` tags (INIT/SP/KNOCK/OPEN/SAS?/RHMI?/CDS?/DATAACK)

## Parallel außerhalb Lab (weiterhin P0)

Echter Golden-Session-btsnoop bleibt der einzige Weg, unbekannte Phone→HU-Nachrichten
direkt zu sehen. Lab beantwortet: „Was muss eine HU mindestens senden, damit das Phone
von X nach Y weitergeht?“
