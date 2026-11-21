# EVAL — LAB_MUSIC_NP_LIVE_INJECT_20261121T1909Z

```yaml
result: FAIL (inject TX, 0 ack) — diagnostic PASS
topology: live AAIdrive green vs f20_sim
inject: Music Description actionIds 336 + 248 (+ HMI focus)
```

## Facts

- `_rhmi_action` / `_rhmi_hmi` inject path exercised on live session.
- Wire TX observed for 336/248; **zero** `rhmi_ackActionEvent`.
- Live PhoneClientSession ≠ Dual-ESP stub spine (stub PASS earlier same day).

## Implication

Do not treat Description-raAction IDs as live “start music NP” levers. Next: F20 field NP visibility trial.

## See also

`docs/analysis/LAB_HOME_LIVE_DEEP_20261121.md`
`docs/analysis/MUSIC_NP_SPINE_LAB_STUB_20261121.md`
