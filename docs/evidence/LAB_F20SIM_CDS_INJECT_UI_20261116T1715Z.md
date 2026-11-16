# LAB — CDS inject visible in MyBMW UI

```yaml
status: PASS
claim_level: LAB FACT
utc: 2026-11-16T17:15Z
session: LAB_F20SIM_INJECT_20261116T1711Z
path: OnePlus MyBMW/AAIdrive ↔ .131 f20_sim CDS push
```

## UI-confirmed (operator)

| Inject | App visible |
|--------|-------------|
| `driving.speedActual` = 87 | ja (km/h) |
| `sensors.battery` = 42 | ja |
| `engine.RPMSpeed` = 4321 | ja |
| Tabelle aktualisiert | ja |

## Follow-up push (no ACL bounce)

Lab pushed without disconnect: speed 54/56, RPM 2100, gear 3, windows/sunroof, temp 7.5, fuel/batt 78, multimedia 2, LabFM 101.1, GPS München, odo 114281. RFCOMM stayed up; Phone continued `rhmi_setData` (~112/8s).

## Epistemic

Proves Phone CDS subscription path accepts Simulator `cds_onPropertyChangedEvent` into MyBMW UI. Not F20 wire identity.
