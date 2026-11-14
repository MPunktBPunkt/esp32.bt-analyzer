# LAB — Dummy F20-profile + Etch/SAS/CDS stub (template)

status: ready-to-run  
code: `bcl_dummy_hu` `--hu-profile f20` · `bcl_etch_stub.py`  
tests: `tests/host/test_bcl_dummy_hu.py` · `tests/host/test_bcl_etch_stub.py`

## Was der Dummy jetzt kann

| Layer | Verhalten |
|-------|-----------|
| HS | v5 / iid **14** / buf **0x4000** (F20-Fingerprint) |
| DATAACK | `u32BE(8+len)` src/dst 0 — OPEN→`0x08`, WD→`0x0C` |
| WD | Echo `13371337` auf dest 5001 |
| Etch 4004 | Reassemble `deadbeef`+len; PKCS7 → **16-B Challenge**; Follow-up → login-ok; CDS-Namen → Stub-JSON |

## Start (auf Dummy-Host, z. B. `.108` hci2)

```bash
# tools inkl. bcl_etch_stub.py hochladen, dann:
python3 bcl_dummy_hu_agent.py hu \
  --hu-profile f20 \
  --channel 6 \
  --name 'BMW 38304' \
  --log /tmp/bcl_dummy/hu_f20.jsonl \
  --ready /tmp/bcl_dummy/hu.ready \
  --session-id LAB_DUMMY_F20_YYYYMMDDTHHMMZ \
  --hold 600
```

Oder: `python3 tools/lab_bcl_dummy_hu_a2dp.py --peer external --hu-profile f20 --seconds 180`

## Erwartete jsonl-Events (Phone→Dummy)

1. `handshake_sent` version=5 instance_id=14 buffer_size=16384  
2. `selectproto_rx` value=**4** · `knock_rx` appType=1 param1=7  
3. `dataack_tx` · `watchdog_echo`  
4. `etch_open_rx` / `sas_certificate_rx` / **`sas_challenge_tx`**  
5. optional `sas_login_rx` · `cds_property_rx` / `cds_property_tx`

## Epistemik

- Challenge/Login-Stub = **Lab**, nicht echte HU-Krypto.  
- CDS-JSON = Stub-Konstanten (nicht Fahrzeugmesswerte).  
- UI-Grün allein ≠ SAS/CDS-Erfolg (M40).  
- Nächster Feldschritt bleibt F20-Proxy → echte SAS Challenge.
