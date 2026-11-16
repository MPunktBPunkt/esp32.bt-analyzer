# LAB — RHMI browse while Spotify A2DP (2026-11-16)

**claim_level:** LAB FACT  
**host:** `.108` / HU `.131` (`C8:C9:A3:CB:7B:0A`) · phone OnePlus 12 (`AC:C0:48:5E:CB:20`)  
**sessions:** `LAB_RHMI_DECODE_20261116T1914Z` → `LAB_RHMI_BROWSE_20261116T2002Z`  
**artifacts:** `LAB_RHMI_BROWSE_20261116T2002Z/{summary.json,hu.jsonl.gz,resources.tgz}`  
**claim refinement:** GPT review of `da0e09e` — flood ≠ missing Music RHMI; A/B Test B is the gate

## Verdict

Phone was **Connected + A2DP (Spotify playing)**. AAIdrive reached SAS/RHMI create + DESCRIPTION for **calendar/News only**. **No music DESCRIPTION, no `rhmi_initialize`, no `rhmi_setData`, no action handlers.**

> **Spotify as A2DP audio source ≠ Spotify as Connected RHMI app.**

Do **not** reconstruct Music-RHMI behaviour from this run — Music RHMI was never activated.

## Claim split

| Status | Claim |
|--------|--------|
| 🟢 LAB FACT | A2DP Spotify does **not** auto-create Music RHMI / setData |
| 🟢 LAB FACT | Calendar/News can have RHMI DESCRIPTION while Spotify is A2DP-only |
| 🟢 LAB FACT | Action flood destroyed browse injects (`30/31 open_conns=0`, `action_tx=0`, RFCOMM 16/12) |
| 🔴 no evidence | “Policy” blocked Music setData |
| 🟡 next | Opening Spotify **inside** Connected/iDrive yields Music DESCRIPTION → initialize → setData |

## Wire totals (combined log, sha256 in summary)

| Signal | Count |
|--------|------:|
| `f20_rpc_rx` | 281 |
| `sas_certificate` / `sas_login` | 64 / 58 |
| `rhmi_create` / `checkResource` / `setResource` | 24 / 24 / 8 |
| `am_registerApp` | 6 |
| `rhmi_setData` / `initialize` / `addActionEventHandler` | **0 / 0 / 0** |
| `inject_rhmi_request` / `rhmi_action_tx` | 31 / **0** |
| `rfcomm_connected` / `closed` | 16 / 12 |
| `framer_error` | 114 (real; **not** the primary cause of missing Music RHMI — track separately) |

## Resources persisted

DESCRIPTION blobs only (no music RHMI DB):

- calendar OnlineServices — **13598 B** (src12/13/16)
- News_1 OnlineServices — **13943 B** (src15/16)

AM strings on wire include `me.hufman.androidautoidrive.music`, but **no music plugin DESCRIPTION / setData** while Spotify was A2DP-only.

## Two problems (do not conflate)

1. **Missing Music RHMI** — already true *before* useful injects: no music DESCRIPTION → no initialize → no setData. Explained by A2DP-only Spotify, not by flood.
2. **Action flood** — second failure: killed RFCOMM / made injects land on `open_conns:0`. Explains failed browse attempts, **not** the absence of Music RHMI activation.

A/B pair with earlier live decode (`LAB_F20SIM_RHMI_SETDATA_DECODED_*`: setResource → initialize → setData ×2896 NP/browse) vs this counterexample (A2DP on, Music RHMI off).

## Test B protocol (next gate — observe only)

No injects. No action flood. Catch natural app lifecycle:

1. Stable Connected/RFCOMM to BMW 38304.
2. User opens **Spotify via Connected/iDrive menu** (not only phone Spotify/A2DP).
3. Passive wire watch for:

```
am_registerApp → Music DESCRIPTION → rhmi_create → checkResource
  → setResource → initialize → setData (± setProperty / handlers)
```

4. Only after a stable Music RHMI session: **one** paced action on one `(src,handle)`.

If Test B still yields no Music DESCRIPTION → then investigate plugin config / AM focus / wrong menu entry / missing `am_*` trigger — that is when the RHMI puzzle stays open.

Helper: `tools/rhmi_test_b_watch.py`

## Tooling shipped with this freeze

- `bcl_etch_stub.py`: promote `setData`/`setProperty`/`am_registerApp`; save `setResource` under `/tmp/bcl_dummy/resources/`
- `bcl_dummy_hu_agent.py`: default RHMI action pace **80 ms** (`RHMI_ACTION_PACE_MS` / `_pace_ms`)
