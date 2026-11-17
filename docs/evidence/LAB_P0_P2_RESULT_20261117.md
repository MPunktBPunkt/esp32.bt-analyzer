# LAB P0–P2 Result — 2026-11-17

**claim_level:** LAB TEST PASS (in-process on `.108`) · AIR TRANSPORT FAIL (dual-ESP RFCOMM)  
**baseline before:** `861ade0` · **host tests:** 127 OK (+5 P0–P2)

## Delivered

| Prio | Change | Result |
|------|--------|--------|
| **P0** | `ServiceException` (TC_CUSTOM `0x95`, `errorCode=213`) on `rhmi_setData` with `RHMIResourceIdentifier{id=0}` | PASS |
| **P0** | `rhmi_checkResource` digest whitelist (`known_digests` + `/tmp/bcl_dummy/rhmi_digests.txt`) | PASS |
| **P0** | Resource persist SHA-256 under `BCL_RHMI_RESOURCES` | PASS (`src10_h12_sha3cf4795378d3_13598.bin`, 13598 B) |
| **P1** | Phone-Sim: `checkResource=False` → DESCRIPTION `setResource` → `initialize` → `setData` Apps/Durchsuchen + ImageID←0 probe | PASS |
| **P1** | Multi-`am_registerApp` (AAIdrive / Spotify / YouTube / Screen Mirroring) | PASS (4×) |
| **P2** | In-process Phone ↔ `f20_sim` on `.108` | PASS |
| **P2** | Dual-ESP air `.87`↔`.131` RFCOMM6 | FAIL |

## In-process smoke (`.108`)

```
menu: description_bytes=13598 sha256=3cf47953…4208b164
exc:  errorCode=213 detailMessage="SetData was not successful."
resources_rx=1 setdata_reject=1 am_registerApp=4
persisted: src10_h12_sha3cf4795378d3_13598.bin
```

Machine summary: `LAB_P0P2_RESULT_20261117.json`.

## Dual-ESP air (both boards online)

| Board | Role | BD | BlueZ |
|-------|------|----|-------|
| `.131` FW 0.3.20 | HU `f20_sim` SCN6 | `C8:C9:A3:CB:7B:0A` | hci2 BMW 38304 |
| `.87` FW 0.3.19 | Phone `--mybmw-sim` | `C8:C9:A3:CB:37:96` | hci1 |

- wifi_ps=`none`, coex=`prefer_bt` on both
- Re-pair SSP: **OK** (Bonded + SPP UUID cached)
- ACL: intermittent / `br-connection-busy` / `auth failed` / ghost LE
- RFCOMM6: **never** `rfcomm_connected` — `Invalid exchange` / `Host is down` / timeout
- Slim air logs: `LAB_P0P2_AIR_{phone,hu}_20261117.jsonl`

Same transport ceiling as `LAB_DUAL_MYBMW_SIM_20261116T1901Z` — protocol path is validated off-air.

## Code touchpoints

- `tools/etch_codec.py` — nested Exception/RHMI as TC_CUSTOM; `errorCode`/`detailMessage` fields
- `tools/bcl_etch_stub.py` — digests, persist, ImageID←0 → ServiceException (`id=0` falsy fix)
- `tools/bcl_dummy_hu.py` — multi-AM, menu upload, BCL fragment ≤4000 for DESCRIPTION
- `tools/fixtures/rhmi_description_lab_{13598,13943}.xml`
- `tests/host/test_lab_p0_p2_hu_phone.py`

## Epistemic

- **YES:** f20_sim rejects ImageID←0 with field-shaped ServiceException(213).
- **YES:** Unknown digest forces DESCRIPTION upload; upload seeds whitelist + disk blob.
- **YES:** Phone-Sim menu shell (Apps/Durchsuchen) + 4× AM register against f20_sim.
- **NO tonight:** end-to-end BCL/Etch over RFCOMM between the two D1s.

**Retest after FW align:** → [`LAB_P0P2_FW0320_RESULT_20261117.md`](LAB_P0P2_FW0320_RESULT_20261117.md) (beide 0.3.20).
