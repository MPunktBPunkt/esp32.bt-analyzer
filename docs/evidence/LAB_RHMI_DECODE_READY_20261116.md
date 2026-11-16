# LAB — RHMI decode + paced inject ready (2026-11-16)

## Deployed on `.108` / `.131`
- Sessions: `LAB_RHMI_DECODE_*` → `LAB_RHMI_BROWSE_20261116T2002Z` · `f20_sim` ch6 · BMW 38304
- **setData/setProperty/am_registerApp** fields promoted into `f20_rpc_rx`
- **setResource** blobs → `/tmp/bcl_dummy/resources/`
- RHMI action inject default pace **80 ms** (`RHMI_ACTION_PACE_MS`, override `_pace_ms`)

## Browse outcome = Test A (confirmed)
OnePlus Connected, Spotify via **A2DP only**. Wire: calendar/News DESCRIPTION; **Music DESCRIPTION / initialize / setData = 0**.  
Flood is a **second** problem (inject `open_conns:0`), not the cause of missing Music RHMI.

Full eval: [`LAB_RHMI_BROWSE_20261116T2002Z.md`](./LAB_RHMI_BROWSE_20261116T2002Z.md)

## Test B (next — observe only)
1. Stable Connected.
2. Open **Spotify inside Connected/iDrive** (not phone A2DP alone).
3. No injects. Watch:

```bash
scp tools/rhmi_test_b_watch.py root@192.168.178.108:/tmp/
ssh root@192.168.178.108 'python3 /tmp/rhmi_test_b_watch.py'
```

Expect: Music DESCRIPTION → `initialize` → `setData`. Only then one paced action.
