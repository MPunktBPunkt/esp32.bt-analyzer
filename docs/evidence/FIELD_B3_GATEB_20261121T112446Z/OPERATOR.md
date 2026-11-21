# Field B3 Gate B — armed 2026-11-21T12:25:05+01:00

## Topology
Phone (OnePlus / MyBMW) → BMW 38304 C8:C9:A3:CB:7B:0A (.131 / hci2) ch6
  ↔ b3_rfcomm_relay
  ↔ BT-Analyzer-Phone C8:C9:A3:CB:37:96 (.87 / hci1) → F20 D4:36:39:CF:E1:B5 ch6

## Armed
- wifi_ps=none, coex=prefer_bt on both ESP
- USB hci0 powered off
- B3 listening on 7B:0A ch6 (pid in b3.pid)
- btmon on hci1 + hci2
- F20 bonded on .87, Connected=false until car connects

## Operator
1. Im Auto: HU mit BT-Analyzer-Phone (.87 / 37:96) verbinden → ACL Connected
2. Phone: MyBMW → BMW 38304 (7B:0A) verbinden / Stack starten (Arm B live sign)
3. Bei AUTHENTICATED oder Reject: freeze — kein AM/RHMI
4. Offline: sas_pad_crosscheck.py --from-bcl-jsonl b3.jsonl

Artifacts: b3.jsonl, raw/, btmon/
