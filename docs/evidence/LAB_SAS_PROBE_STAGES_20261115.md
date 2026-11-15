# LAB — SAS probe stages + DATAACK 8+len (2026-11-15)

## DATAACK = 8 + payload_len (FIELD FACT)

| count | = 8+len | matches |
|------:|---------|---------|
| 10 | 8+2 | SELECTPROTO |
| 44 | 8+36 | KNOCK body / small DATA |
| 4008 | 8+4000 | BCL `MAX_PAYLOAD` fragment |

Dummy: `dataack_count_for_frame` / `DATAACK(8+len)` per RX frame (not cumulative).

## Adaptive SAS probe (`--sas-probe`)

| Stage | CLI | Dummy on OPEN 4004 |
|-------|-----|--------------------|
| (i) | `--sas-probe none` | no etch DATA (WD/HS only) |
| (ii) | `--sas-probe dataack` | DATAACK only; stub silent |
| (iii) | `--sas-probe challenge` | non-zero SAS-challenge (default f20) |
| (iv) | `--sas-probe challenge_rhmi` | challenge + RHMI/capabilities stub |

Measure Phone progress via jsonl: `sas_challenge_tx`, `sas_login_rx`, `cds_property_*`, `rhmi_capabilities_tx`.

## Run (Dummy host)

```bash
# upload tools then, stage ladder:
python3 bcl_dummy_hu_agent.py hu --hu-profile f20 --channel 6 \
  --name 'BMW 38304' --sas-probe none --handshake-delay 3 \
  --log /tmp/bcl_dummy/hu_probe_i.jsonl --ready /tmp/bcl_dummy/hu.ready --hold 300

# then dataack | challenge | challenge_rhmi
```

Or: `lab_bcl_dummy_hu_a2dp.py --peer external --hu-profile f20 --seconds 180` (passes profile; add agent flags after upload).

## Also shipped

- Field CDS names: `sensors.SOCBattery`, `_ENT_MTP_OFF`, `iva_MYV_LIGHT_INTERIOR`, VIN stub
- Accept KNOCK as cmd=8 **or** Silent-HU `deadbeef`+UUID envelope (`knock_envelope_rx`)
- `--handshake-delay` (~3 s field realism)
