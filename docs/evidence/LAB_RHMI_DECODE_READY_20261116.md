# LAB — RHMI decode + paced inject ready (2026-11-16)

## Deployed on `.108` / `.131`
- Sessions: `LAB_RHMI_DECODE_*` → `LAB_RHMI_BROWSE_20261116T2002Z` · `f20_sim` ch6 · BMW 38304
- **setData/setProperty/am_registerApp** fields promoted into `f20_rpc_rx`
- **setResource** blobs → `/tmp/bcl_dummy/resources/`
- RHMI action inject default pace **80 ms** (`RHMI_ACTION_PACE_MS`, override `_pace_ms`)

## Browse outcome (evening)
OnePlus **Connected**, Spotify via **A2DP**. Wire: SAS/RHMI create + calendar/News DESCRIPTION; **`setData=0`**, music DESCRIPTION absent.  
Inject burst: **31** requests, **30× `open_conns:0`**, **`rhmi_action_tx=0`** — RFCOMM killed by action flood, not a policy block.

Full eval: [`LAB_RHMI_BROWSE_20261116T2002Z.md`](./LAB_RHMI_BROWSE_20261116T2002Z.md)

## Next live gate
BT Connected + AAIdrive green → **Music/Spotify in Connected/HU öffnen** (nicht nur Phone-A2DP) → watch setData → paced actions on **one** `(src,handle)`.

```bash
grep 'rhmi_setData' /tmp/bcl_dummy/hu.jsonl | tail -20
ls /tmp/bcl_dummy/resources | head
# gentle (default 80ms pace) — do NOT flood
printf '%s\n' '{"_rhmi_action":{"src":16,"handle":12,"actionId":1,"args":{"0":0}}}' >> /tmp/bcl_dummy/inject_cds.jsonl
```
