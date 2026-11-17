# LAB f20_sim Session Eval — 2026-11-16

## Verdict
- **11c (phone↔f20_sim) PASS**: UI green (AAIdrive/MyBMW), SAS login, CDS + RHMI live.
- **CDS inject → UI confirmed**: speed/battery/RPM and further properties visible on phone.
- **Spotify A2DP audio works**; album covers + Spotify notification icon arrived via RHMI resources.
- **RHMI control / NowPlaying metadata incomplete**: action flood and reconnect left NP stale; A2DP can play without fresh Muse `rhmi_setData`.
- Epistemic note: protocol-ready ≠ indistinguishability from real HU.

## Live wire stats (`LAB_F20SIM_LIVE_20261116T1741Z_hu.jsonl`)
- Events parsed from full log; key subset → `LAB_F20SIM_SESSION_20261116_KEY.jsonl` (1004 lines).
- RFCOMM connect/disconnect events: 7
- Total f20_rpc_rx methods: 3776
- Top RPC:
  - `rhmi_setData`: 2896
  - `rhmi_setProperty`: 219
  - `cds_addPropertyChangedEventHandler`: 114
  - `cds_getPropertyAsync`: 110
  - `ver_getVersion`: 70
  - `rhmi_checkResource`: 48
  - `rhmi_setResource`: 47
  - `sas_certificate`: 42
  - `sas_login`: 42
  - `rhmi_create`: 22
  - `am_registerApp`: 19
  - `rhmi_initialize`: 19
- `cds_property_tx` property hits: 195 across 33 props
- Top CDS props: `vehicle.VIN`×10, `engine.info`×9, `sensors.battery`×8, `vehicle.time`×8, `controls.windowDriverFront`×8, `vehicle.language`×8, `driving.drivingStyle`×8, `sensors.fuel`×8, `sensors.SOCBatteryHybrid`×8, `driving.odometer`×6
- RHMI resources: {'None': 47}
- RHMI actions TX: 44; ids: {'541': 12, '542': 10, '540': 6, '365': 4, '364': 4, '284': 4, '283': 4}
- Inject RHMI requests in key stream: 44
- `rhmi_setData` by model (top): `None`×2896

## Track / NP samples (string-matched)
- No strong title/artist dict samples in filtered setData (metadata often opaque / model-coded).

## Artifacts
- `LAB_F20SIM_11C_READY_20261116.md` — preconditions/runbook
- `LAB_F20SIM_11C_20261116T1704Z.md` + `_hu.jsonl` — first green UI session
- `LAB_F20SIM_CDS_INJECT_UI_20261116T1715Z.md` — UI-confirmed CDS inject
- `LAB_F20SIM_COVERS_20261116/` + `LAB_F20SIM_COVERS_LIVE/` — extracted cover/icon binaries
- `LAB_F20SIM_LIVE_20261116T1741Z_hu.jsonl` — full end-of-day log (~28MB; optional local)
- Tools: `bcl_dummy_hu.py`, `bcl_dummy_hu_agent.py`, `bcl_etch_stub.py` — CDS/RHMI inject path

## Tooling delivered
- Pollable `/tmp/bcl_dummy/inject_cds.jsonl` with truncate-safe offset reset
- `_rhmi_action` inject for HU-side RHMI actions (play/pause/skip etc.)
- Etch stub CDS subscription / property push path

## Full CDS push (live, end of day)
- Appended 37-property burst → `inject_cds_request` with `open_conns: 1`
- Distinctive values for UI check: **speed 99**, **RPM 5555**, **battery 77**, fuel range 512 / tank 44, odo 114321
- Multiple `cds_property_tx` (reason=`inject`) across subscribed handles — phone should refresh if UI bound

## Open gaps
- Reliable AVRCP ↔ RHMI control loop without RFCOMM drop after action flood
- Fresh NowPlaying `setData` after BT reconnect (Muse audible, NP not refreshed)
- BFMV track path: not confirmed on wire this session

## Update 2026-11-17 — len-only gap CLOSED
Das `rhmi_setData`-„logged without decoded args (len-only)" lag am Etch-Tiny-Int-Decode-Bug in
`tools/etch_codec.py` (nur `0x00–0x1F`/`0xE0–0xFF` statt `0x00–0x7F`/`0xC0–0xFF`). Nach dem Fix
(Host-Tests 122/122) dekodiert die volle Reassemblierung von `LIVE_1741`:
**40 setData-Modelle** (445/446/447/451/452/458/462/456…), **0 Decode-Fehler**, **80-Einträge-Track-Timeline**
(z. B. `Scorpions – Best – Still Loving You`). Details: `docs/analysis/DEEP_FORENSIC_RHMI_SCREENMIRROR_20261117.md` §5/§7.
