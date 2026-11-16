# LAB 11c — Ready: OnePlus ↔ `.131` `f20_sim`

```yaml
session_id: LAB_F20SIM_11C_20261116T1612Z
status: READY (waiting for phone at home)
prepared: 2026-11-16T16:12Z
hold_until: ~2h from start (agent --hold 7200)
dummy: hci1 C8:C9:A3:CB:7B:0A (.131)
profile: f20_sim (sas_probe=f20_full)
channel: 6
alias: BMW 38304
cod: 0x340408 (pinned)
fw: hci-agent 0.3.20
phone_paired: OnePlus 12 AC:C0:48:5E:CB:20 (Trusted, not connected)
jsonl: /tmp/bcl_dummy/hu.jsonl on .108
```

## Preflight (done)

| Check | State |
|-------|-------|
| `.131` FW 0.3.20 / HCI ready | OK · client `.108` |
| Tools sync inkl. `etch_codec.py` | OK → `/tmp/bcl_dummy/` |
| `bcl_dummy_hu_agent.py hu --hu-profile f20_sim --channel 6` | RUNNING |
| SPP UUID registered | OK |
| Alias `BMW 38304` + pair-agent drop-in | OK |
| CoD pin `hci1 → 0x340408` | OK (`cod_pin_hci1.sh`) |
| Alias pin | OK (`alias_pin_hci1.sh`) |

## Heim-Ablauf (~5 min)

1. **Handy:** Bluetooth an · Gerät **BMW 38304** verbinden (A2DP).
2. **Apps:** MyBMW + AAIdrive **force-stop**, dann beide starten (Connected/AAIdrive).
3. **Erwartung UI:** AAIdrive / MyBMW Connected nicht mehr nur „wartet“.
4. **Wire-Erfolg (jsonl):**  
   `handshake_sent` (v5/14/0x4000) → `selectproto`/`knock` → WD →  
   `OPEN 4004` → `sas_certificate` → **`sas_challenge_tx`** → **`sas_login` / `sas_login_ok_tx`** →  
   `rhmi_*` / `cds_*` / `am_*` / `av_*` (`f20_rpc_rx`).
5. **Fail-schnell:** nur A2DP ohne RFCOMM → Alias/CoD/App-Restart prüfen.  
   RFCOMM + `CLOSE` nach Challenge → Log ziehen (sollte mit heutigem Fix nicht mehr so sein).

## Live beobachten (von Arbeitsrechner)

```bash
ssh root@192.168.178.108 'tail -f /tmp/bcl_dummy/hu.jsonl' \
  | python3 -c "import sys,json
for ln in sys.stdin:
  o=json.loads(ln)
  e=o.get('event')
  if e in ('rfcomm_connected','handshake_sent','knock_rx','etch_open_rx','sas_challenge_tx','sas_login_ok_tx','f20_rpc_rx','rhmi_capabilities_tx','cds_property_tx','handle_created','rfcomm_closed','error'):
    print(e, {k:o.get(k) for k in ('method','src','sig_len','property','handle','rfcomm_channel') if k in o})"
```

## Evidence nach Lauf

```bash
# vom Repo-Host
STAMP=$(date -u +%Y%m%dT%H%MZ)
scp root@192.168.178.108:/tmp/bcl_dummy/hu.jsonl \
  docs/evidence/LAB_F20SIM_11C_${STAMP}_hu.jsonl
```

## Nicht anfassen während des Tests

- Bridge `.131` / FW-OTA
- Pair-Agent stoppen
- CoD-/Alias-Pin-Skripte killen
- Dummy auf `legacy`/`f20` zurückstellen

## Epistemik

- Erfolg = **LAB FACT** „Phone akzeptiert `f20_sim` als Connected-Gegenstelle“.
- Nicht = „unsichtbar wie F20“ (Capabilities-Stub, CDS-Stubs, BT-Controller ≠ TI/Alps).
