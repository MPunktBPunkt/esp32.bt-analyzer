# LAB RHMI Deep Analysis — 2026-11-16

**claim_level:** LAB FACT (decoded from `LAB_F20SIM_LIVE_20261116T1741Z_hu.jsonl.gz`)  
**scope:** answer GPT/Mistral open points with wire evidence — not FIELD HU-SAS

## Verdict

Yes — a Tiefenanalyse **can** unblock the “len-only” story: payloads were never missing, only **not promoted** from `frame.payload_hex` into `f20_rpc_rx`. Hybrid decode recovers NowPlaying model IDs and values. Action-flood remains a **hypothesis**, not a root-cause FACT. Field SAS-Authorization stays independent P0.

## 1. Logging hole, not missing data

| Layer | What we have |
|-------|----------------|
| `f20_rpc_rx` `rhmi_setData` ×2896 | method + `len` + `src` only |
| `frame` DATA `dest=4004` | **`payload_hex` present** (3167/3170) |
| Hybrid decode | **324** complete `rhmi_setData` messages (direct-frame + partial reassembly) |

So Mistral’s “Decoder is Lab-P0 tooling” is right as an **instrumentation** task; the bytes for many NP updates are already in the gz.

## 2. NowPlaying model map (observed, src16)

| modelId | role | values seen |
|---------|------|-------------|
| **445** | artist / primary | `Scorpions`, `Disturbed` |
| **446** | secondary (album/playlist fragment) | `Best` |
| **447** | track title | `Wicked Game` |
| **451** | elapsed / placeholder | `"   :  "`, `2:39` |
| **452** | duration | `6:26`, `4:47` |
| **462** | progress fraction | `0.12`, `0.55` |

Timeline (src16): `445=Scorpions` → `446=Best` → later `447=Wicked Game` (HIM). That matches the earlier UI note (HIM/Scorpions) and shows **NP is plain Etch strings on model IDs**, not an undecodable blob — once logged.

Muse after reconnect: **not** seen in the successfully decoded subset (decode coverage ≪ 2896). Reconnect NP-staleness remains plausible; we still need full reassembly + live logging to prove Muse never arrived vs. arrived-but-unread.

## 3. SAS ×42 — GPT correction confirmed

`sas_certificate`/`sas_login` = **42 each**, but per-src only **~4–5**:

`src 12,16,17,15: 5×` · `11,10,14,13,18: 4×` · `19: 2×`

Plus **7×** `rfcomm_connected` / **6×** closed in the same window.  
→ **not** “42 app instances”; → **several Connected contexts × several sessions/reconnects**. Safe Doku wording: *SAS runs per Connected app context; multiplicity tracks sessions, not one-cert-per-app globally.*

## 4. Boot pipeline (wire-compact per src)

Typical RHMI app context (e.g. src16/17/18):

`sas_certificate → sas_login → rhmi_create → checkResource → setResource(+covers) → initialize → addAction/Hmi handlers → setData/setProperty`

src10/12 also carry AM/CDS (`am_create`, `cds_create`, capabilities). Spotify-heavy `setData` volume is dominated by **src17 (1811)** then src18/16 — multi-instance UI, not one pipe.

## 5. Resources / “rhmi_db ~13.9 kB”

`rhmi_resource_rx` sizes cluster at **393, 1576, 7195, 13598, 13943**, then **85–162 kB** (covers — match extracted PNG/JPEG).  
~13.9 kB doubles across src/handles are **strong candidates** for description/DB uploads after `checkResource→False`, but **runtime did not persist resource bytes into jsonl**; offline `setResource` full-body decode from fragments is still incomplete (`LAB_F20SIM_RHMI_DB_CANDIDATES_20261116/` empty until stub saves blobs). Covers on disk prove large resources were captured by a side path; the DB candidate needs the same.

## 6. Action flood — hypothesis, measure next

- 44 `rhmi_action_tx`; IDs **541×12, 542×10, 540×6, 365/364/284/283×4**
- Largest cluster: **~27 actions in ~3 ms** (ts 9836.958–961), fan-out across src 15–18
- Later closes: `write_error:104`, `write_error:11` — TX pressure **consistent with** flood, but stack layer unknown (stub / RFCOMM / bridge / coex)

Do **not** hardcode 50–100 ms yet. Ramp 1→2→5→10→20→44 with TX/RX, latency, queue, drop time.

## 7. Epistemic (agree with GPT)

| Claim | Status |
|-------|--------|
| Android client accepts `f20_sim` as working HU (UI green, CDS visible, RHMI live) | **LAB FACT** — higher than “syntax stub” |
| CDS inject → UI (99 / 5555 / 77) | **LAB FACT** (control-plane causality) |
| A2DP audio ⊥ RHMI covers | **LAB confirmed** |
| Action-flood root cause | **hypothesis** |
| `f20_sim` indistinguishable / F20 will authorize same client | **not claimed** |
| Field P0 = btsnoop S-B / real HU SAS | **unchanged** |

## 8. What Tiefenanalyse clarified vs. still open

**Clarified now**
- len-only was a logger design gap; NP text models 445/446/447 (+ time/progress) are decodable.
- SAS×42 ≠ 42 apps.
- Multi-src RHMI boot + resource size classes.
- Action burst timing is real and extreme; causality still unmeasured.

**Still open (needs code or field)**
1. Promote decode into live `f20_rpc_rx` + resource blob dump (Lab tooling P0).
2. Full fragment reassembly → all 2896 setData + setProperty + setResource/DB parse.
3. Action load ramp (before fixed pacing).
4. NP cache keyed by `(src,handle,modelId)` after reconnect.
5. Field: real F20 SAS authorization (independent line).

## Artifacts

- `LAB_F20SIM_RHMI_SETDATA_DECODED_20261116.jsonl` (324 rows)
- `LAB_F20SIM_RHMI_DEEP_20261116.json`
- Source: `LAB_F20SIM_LIVE_20261116T1741Z_hu.jsonl.gz`
