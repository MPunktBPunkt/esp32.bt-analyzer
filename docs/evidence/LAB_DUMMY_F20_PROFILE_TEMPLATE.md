# LAB — Dummy F20-profile + Etch/SAS/CDS stub (template)

status: ready-to-run  
code: `bcl_dummy_hu` `--hu-profile f20` · `bcl_etch_stub.py`  
tests: `tests/host/test_bcl_dummy_hu.py` · `tests/host/test_bcl_etch_stub.py`

## Was der Dummy jetzt kann

| Layer | Verhalten |
|-------|-----------|
| HS | v5 / iid **14** / buf **0x4000** (F20-Fingerprint) |
| DATAACK | `u32BE(8+len)` — FIELD: 10/44/4008 (=8+4000) bestätigt |
| WD | Echo `13371337` auf dest 5001 |
| Etch 4004 | `--sas-probe none\|dataack\|challenge\|challenge_rhmi` (default challenge) |
| CDS | inkl. Feld-Namen `sensors.SOCBattery`, `_ENT_MTP_OFF`, … |

Stufen-Laufbuch: [`LAB_SAS_PROBE_STAGES_20261115.md`](LAB_SAS_PROBE_STAGES_20261115.md).

## Start (auf Dummy-Host, z. B. `.108` hci2)

```bash
python3 bcl_dummy_hu_agent.py hu \
  --hu-profile f20 \
  --channel 6 \
  --name 'BMW 38304' \
  --sas-probe challenge \
  --handshake-delay 3 \
  --log /tmp/bcl_dummy/hu_f20.jsonl \
  --ready /tmp/bcl_dummy/hu.ready \
  --session-id LAB_DUMMY_F20_YYYYMMDDTHHMMZ \
  --hold 600
```

Oder: `python3 tools/lab_bcl_dummy_hu_a2dp.py --peer external --hu-profile f20 --seconds 180`

## Erwartete jsonl-Events (Phone→Dummy)

1. `handshake_sent` version=5 instance_id=14 buffer_size=16384  
2. `selectproto_rx` value=**4** · `knock_rx` / `knock_envelope_rx`  
3. `dataack_tx` (acked=8+payload_len) · `watchdog_echo`  
4. `etch_open_rx` → **`sas_challenge_tx`** (stage≥challenge)  
5. optional `sas_login_rx` · `cds_property_*` · `rhmi_capabilities_tx`

## Epistemik

- Challenge/Login-Stub = **Lab**, nicht echte HU-Krypto.  
- CDS-JSON = Stub-Konstanten (nicht Fahrzeugmesswerte).  
- UI-Grün allein ≠ SAS/CDS-Erfolg.  
- Volle HU-Skripte weiter nur via btsnoop Golden Session.
