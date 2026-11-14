# FIELD — B2-A-TX ch6 SELECTPROTO(3) + WD @2.5 s (Kontrolle, 2026-11-14 ~15:34)

```yaml
id: FIELD_B2A_TX_CH6_SP3WD_20261114T1534Z
kind: field_b2a_tx_full
verdict: BCL_FIELD_CONFIRMED · WD live ~45 s
selectproto: 3
wd_interval: 2.5
contrast_sp2: FIELD_B2A_TX_CH6_SP2_20261114T1531Z
contrast_sp3_no_wd: FIELD_B2A_TX_CH6_FULL_20261114T1528Z
```

## Verdict

**SP(3)+WD** = gleiche HU-Antwort wie SP(2)+WD: DATAACK `0x0A`/`0x08`, dann dauerhaft DATAACK `0x0C` + DATA `13371337`.

| | SP2+WD (90 s) | SP3+WD (45 s) | SP3 ohne WD-TX |
|--|---------------|---------------|----------------|
| HS v5 | ja | ja | ja |
| DATAACK 0x0A/0x08 | ja | ja | ja |
| WD-Echo `13371337` | **ja** (35×) | **ja** (18×) | **nein** |
| RX Bytes | 880 | 472 | 40 |

**Schluss:** Stabiler Post-HS-Betrieb braucht **Client-WD-Pings** (Bugfix in Agent). SP2 vs SP3 ist für diesen F20-State **kein** Diskriminator.
