# EVAL — LAB_HOME_20261121T1900Z

```yaml
result: MIXED (green sessions + write_error:11 + flaps)
topology: OnePlus → ESP .131 (7B:0A) → .108 f20_sim
artifacts:
  - hu_home_pre_restart.jsonl (~1703 s)
  - hu_home.jsonl (post-restart ~201 s)
```

## Facts

- Pre-restart: HS ×5, SAS ×50, fatal **`write_error:11`** under multi-app `setResource` flood.
- Post-restart: HS ×1, SAS ×11, stable green; Music NP BFMV / Tears Don't Fall (445–447 ×135).
- Screenmirror AM present early, often missing after flaps.
- Description-action injects (mapview/music): TX without reliable app start.

## See also

`docs/analysis/LAB_HOME_LIVE_DEEP_20261121.md`
