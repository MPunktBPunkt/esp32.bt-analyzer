# LAB P0 — PiDrive UI Sequence PASS

**claim_level:** LAB FACT  
**run:** `LAB_P0_RHMI_PIDRIVE_SEQ_DUAL_20261117T220723Z`  
**holds:** Dual-ESP BCL · `--rhmi-pidrive-seq` · ~90 s

## Verdict

**PASS.** Minimale eigene UI-Funktionskette auf dem Lab-Wire:

```
setData(100, "PiDrive")
        ↓
HU MENU_TEST_ACTION (actionId=200)
        ↓
phone rhmi_onActionEvent
        ↓
pidrive_action_sink → selected_action = PI_DRIVE_TEST
        ↓
rhmi_ackActionEvent
        ↓
pidrive_seq_complete
```

## Criteria

| Check | Result |
|-------|--------|
| RUNTIME_ACTIVE | yes |
| setData PiDrive | yes |
| Action TX (200) | yes |
| Action RX | yes |
| Ack | yes |
| Sink `PI_DRIVE_TEST` | yes |
| no abort / no fatal close | yes |

## Meaning

Nicht mehr nur „RHMI transportiert Daten/Events“, sondern:

> Eine RHMI-Interaktion löst eine deterministische PiDrive-interne Aktion aus (`selected_action=PI_DRIVE_TEST`).

## Next

1. Optional: UI-Sequenz gegen reale F20-Modelle/Action-IDs härten.  
2. **P3:** erster kontrollierter F20-Feldversuch (Resource-Auth, reale Modelle, reale Action-Zuordnung).  
3. modelId 4 / 213 bleibt P1-Nebenpfad, nicht blockierend.
