# LAB — RHMI browse while Spotify A2DP (2026-11-16)

**claim_level:** LAB FACT  
**host:** `.108` / HU `.131` (`C8:C9:A3:CB:7B:0A`) · phone OnePlus 12 (`AC:C0:48:5E:CB:20`)  
**sessions:** `LAB_RHMI_DECODE_20261116T1914Z` → `LAB_RHMI_BROWSE_20261116T2002Z`  
**artifacts:** `LAB_RHMI_BROWSE_20261116T2002Z/{summary.json,hu.jsonl.gz,resources.tgz}`

## Verdict

Phone was **Connected + A2DP (Spotify playing)**. AAIdrive reached SAS/RHMI create + DESCRIPTION upload for **calendar/News only**. **No `rhmi_setData`, no `rhmi_initialize`, no action handlers.** Spotify audio ≠ RHMI Music/NP path.

Browse inject **did not land on the wire**: `inject_rhmi_request` ×31 with `open_conns` **30×0 / 1×1**, `rhmi_action_tx` **0**. Same-ms action flood correlated with RFCOMM flaps (`connected` 16 / `closed` 12).

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

## Resources persisted

DESCRIPTION blobs only (no music RHMI DB):

- calendar OnlineServices — **13598 B** (src12/13/16)
- News_1 OnlineServices — **13943 B** (src15/16)

AM package names seen on wire include `me.hufman.androidautoidrive.music`, but **no music plugin DESCRIPTION / setData** followed while Spotify was only on A2DP.

## Root cause of “blocked” browse

1. **RFCOMM already down** for almost all injects (`open_conns:0`) → agent queued requests, sent nothing.
2. **Action flood** (many aids × many handles, `_pace_ms:0`) → reconnect storm; handshake often stuck at SAS before stable handles.
3. **Wrong media path expectation:** A2DP Spotify does not open Connected Music RHMI; NP models 445/446/447 need Music/Spotify **inside** AAIdrive/Connected UI (as in earlier decoded `LAB_F20SIM_RHMI_SETDATA_DECODED_*`).

## Tooling shipped with this freeze

- `bcl_etch_stub.py`: promote `setData`/`setProperty`/`am_registerApp` fields; save `setResource` under `/tmp/bcl_dummy/resources/`
- `bcl_dummy_hu_agent.py`: default RHMI action pace **80 ms** (`RHMI_ACTION_PACE_MS` / `_pace_ms`)

## Next lab gate

Stable RFCOMM → wait for `am_registerApp` + music DESCRIPTION → **open Music/Spotify in Connected** → confirm decoded `rhmi_setData` → then **paced** single-handle actions only.
