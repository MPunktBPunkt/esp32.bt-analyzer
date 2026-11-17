# LAB Home Prep — 2026-11-17 (~30 min bis daheim)

**status:** READY  
**FW:** `.131` / `.87` = **0.3.20** · Bridges `.108` up  
**HU BD:** `C8:C9:A3:CB:7B:0A` (hci nach Restart prüfen)  
**Phone (OnePlus 12):** `AC:C0:48:5E:CB:20`  
**USB dongle (W0 air):** `C0:B8:83:34:F4:62`

## Ziel heute (zwei getrennte Läufe)

### Lauf A — P0: checkResource-Rückweg (A vs C)

Nur **einen** `checkResource(DESCRIPTION)` · kein setResource/init/setData erzwingen.  
Parallel: **btmon** + HU jsonl + Phone jsonl → Correlator.

```bash
# auf .108 (nach Prep-Skript oder manuell)
export BCL_RHMI_STOP_AFTER=description_check
# Phone-Sim USB→.131 mit stop_after (siehe lab_home_session_prep.sh --w0-usb)
```

Interpretation: siehe `docs/analysis/EVAL_A926B7D_NEXT_20261117.md`.

### Lauf B — OnePlus → f20_sim (Telefon→Lab)

Eligibility: Alias **BMW 38304**, CoD **0x340408**, SCN **6**, A2DP an, HFP möglichst aus.

1. Handy: BT an → **BMW 38304** verbinden (A2DP).  
2. MyBMW + AAIdrive force-stop → neu starten.  
3. Wire: HS v5 → SAS → AM/RHMI → checkResource…  
4. Erfolg = **LAB FACT** (nicht F20-Feldbeweis).

## Start (ein Befehl)

Vom Repo-Host:

```bash
./tools/lab_home_session_prep.sh          # sync + eligibility + HU f20_sim + btmon
# optional:
./tools/lab_home_session_prep.sh --w0-usb # zusätzlich USB-Phone W0 isolate
```

Live:

```bash
ssh root@192.168.178.108 'tail -f /tmp/bcl_dummy/hu_home.jsonl' \
  | python3 -c "import sys,json
for ln in sys.stdin:
  o=json.loads(ln); e=o.get('event')
  if e in ('rfcomm_connected','handshake_sent','sas_challenge_tx','sas_login_ok_tx','f20_rpc_rx','rhmi_check_resource','rhmi_resource_rx','rfcomm_closed'):
    print(e, {k:o.get(k) for k in ('method','peer','known','handle') if k in o})"
```

## Nicht anfassen während Test

Bridge/OTA · Pair-Agent stop · CoD/Alias-Pin killen · Profil auf legacy zurück.

## Evidence nach Lauf

```bash
STAMP=$(date -u +%Y%m%dT%H%MZ)
scp root@192.168.178.108:/tmp/bcl_dummy/hu_home.jsonl \
    docs/evidence/LAB_HOME_${STAMP}_hu.jsonl
scp root@192.168.178.108:/tmp/bcl_dummy/home_*.btsnoop \
    docs/evidence/ 2>/dev/null || true
```
