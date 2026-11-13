# BclCarLink@7cfd959 vs OnePlus wire (LAB evening 2026-11-13)

Pin verified: `7cfd959` = current `BimmerGestalt/BclCarLink` tip.  
Wire: OnePlus `AC:C0:48:5E:CB:20` → Dummy `C8:C9:A3:CB:7B:0A` ch6 · AAIdrive + MyBMW.

Evidence: `LAB_PHONE_BCL_20261113T2201Z*` · `LAB_L3_NO_HS_*` · `LAB_EVENING_COD_GATE_20261113T2342Z*`.

## Verdict

| Claim | Status |
|-------|--------|
| AAIdrive bundles newer BclCarLink → explains SELECTPROTO(2)/WD 2.5s | **NOT PROVEN** |
| Wire ≠ BclCarLink@7cfd959 | **YES** — wire primary, desk structural hypothesis |
| Wrong Dummy CoD → phone skips BCL INIT | **YES** — sends DEADBEEF+UUID probe instead |
| Wire client binary | **UNKNOWN** (MyBMW stack most likely) |

## Side-by-side

| Marker | BclCarLink@7cfd959 | OnePlus wire |
|--------|--------------------|--------------|
| INIT `12345678` | yes | yes, **1×** if Dummy CoD car-like + HS answers |
| INIT retry if no HS | two×`sleep(1000)` → **≈2 s** | **not measured** — observe-only got DEADBEEF probe, not INIT spam |
| First PDU if peer “not car/BCL” | (would still INIT) | **`deadbeefdead01…` + ASCII uuid + `deadbeefbeef`** (~9 s retry) |
| SELECTPROTO after HS **v3** | **no** (`version > 3` only → SelectProto(**3**)+KNOCK) | **yes**, payload **`0002`**, ~+3.1 s |
| KNOCK | only if version>3 | **absent** (ok for desk v3) |
| DATAACK after `readPacket` | yes | **absent** (Dummy TX only HS → expected; ACK not in `readHandshake`) |
| OPEN 5001 + WD `13371337` | interval **5000 ms**, TO **20 s** | interval **≈2505 ms**; session **≈38.3 s** → eof without pong |
| OPEN dest **4004** src≥10 | `ETCH_DEST_PORT` + grantor starts at **10** | src **10/11/12 → 4004** |
| OPEN **4007** | phone-local TCP proxy | **not on BT wire** |
| HANGUP (cmd 10) | clean shutdown | **not seen** (eof) |
| instanceId | HU→Phone HS → Android broadcast | Dummy sent **1**; phone does not TX HS |
| CoD / identity | A2DP+SPP eligibility in `hasBCL` | **CoD `0x340408` required** for INIT path (lab) |

## Desk code still useful

1. States: OPENING → HS → INITIALIZING → NEGOTIATING → ACTIVE.  
2. Fragile `available() >= 16` before HS read → analyzer = stream reassembly.  
3. Watchdog = post-ACTIVE port **5001**; pong = any bytes.  
4. Mux src ports from **10**.  
5. KNOCK layout + appType 0/1/7 comments.  
6. **4007** local / **4004** car-side Etch *candidate*.

## Decoder phases (F20)

```text
Transport (RFCOMM / UUID 0x1101)
  → first PDU classify: INIT | DEADBEEF_UUID_PROBE | other
  → HS identity (version, instanceId, bufferSize)
  → SELECTPROTO
  → ACTIVE: OPEN 5001, WD
  → OPEN channels (4004…)
  → Teardown: HANGUP? / DISC / eof
```

## Ops lesson

Dummy Class must stay **`0x340408`**. Drift to computer CoD → endless DEADBEEF probes, looks like app failure. Alias `BMW 38304` alone is not enough. After CoD change: **ACL bounce** (or phone BT toggle) so Android re-evaluates.

## A2DP liveness (lab check vs Mistral)

`LAB_A2DP_BCL_CORR_*` + `LAB_COD_AB_BOUNCE_*`: A2DP MediaTransport **`idle`** during BCL INIT/HS/WD and at close; ACL stayed connected. BclCarLink’s “shutdown when leaving A2DP connected set” did **not** explain the ~38 s eof here — phone sent **CLOSE 5001** then RFCOMM eof (no Dummy WD pong). CoD gate still holds; “CoD ⇒ A2DP drop ⇒ no BCL” is **not** required for this Dummy.

## Watchdog pong (C-L11)

`LAB_WD_PONG_*`: Dummy `--echo-watchdog` → minutes alive (final ~171 s / 288 pings until agent_stop). Without pong → CLOSE@~38 s. Wire WD ≈2.5 s; ~14 unanswered pings ≈ phone session cut.

## Phone simulation toward F20

`bcl_dummy_hu_agent.py phone` can RFCOMM-client the HU, but `PhoneClientSession` still follows **desk** BclCarLink (SP only if ver>3→3, +KNOCK, 5 s WD). Lab phone wire is different (SP(2) after v3, ~2.5 s WD, no KNOCK). **Do not claim wire-faithful phone sim until that client is patched.** Tomorrow: capture F20 with real phone first (`LAB_EOD_20261114T0030Z`).
