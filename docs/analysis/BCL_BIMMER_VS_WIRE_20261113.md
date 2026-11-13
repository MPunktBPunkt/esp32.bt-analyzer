# BclCarLink@7cfd959 vs OnePlus wire (LAB_PHONE_BCL)

Pin verified: `7cfd959` = current `BimmerGestalt/BclCarLink` tip (cloned 2026-11-13).  
Wire: OnePlus `AC:C0:48:5E:CB:20` → Dummy ch6 (`LAB_PHONE_BCL_20261113T2201Z` + 14 live sessions).

## Verdict (GPT over Mistral on pin-drift)

| Claim | Status |
|-------|--------|
| AAIdrive bundles a newer BclCarLink → explains SELECTPROTO(2)/WD 2.5s | **NOT PROVEN** — AAIdrive docs: uses MyBMW proxy; BclCarLink is separate experiment |
| Wire ≠ BclCarLink@7cfd959 for several markers | **YES** — treat wire as primary, desk as hypothesis |
| Which binary emitted the frames | **UNKNOWN** (MyBMW / Connected stack most likely) |

## Side-by-side

| Marker | BclCarLink@7cfd959 | OnePlus wire (n=14 sessions) |
|--------|--------------------|------------------------------|
| INIT on connect | yes `12345678` | yes, **exactly 1×** (Dummy HS in ≤300 ms) |
| INIT retry if no HS | `initSession()` + **two** `sleep(1000)` → **≈2 s** period (not 1 s) | pending L3 (observe-only) |
| SELECTPROTO after HS v3 | **no** (`if version > 3` only; then SelectProto(**3**)+KNOCK) | **yes**, payload **`0002`**, ~+3.1 s |
| KNOCK | only if version>3 | **absent** (consistent with desk for v3) |
| DATAACK after every `readPacket` | yes | **absent** — expected here: Dummy TX only HS; BclCarLink ACKs in `readPacket`, **not** in `readHandshake` |
| OPEN 5001 then WD `13371337` | yes, interval **5000 ms**, TO **20 s** | yes, interval **≈2505 ms**; session **≈38.3 s** then RFCOMM eof (≠ desk 20 s) |
| OPEN dest **4004** src 10+ | `ETCH_DEST_PORT=4004`, grantor `nextSocketIndex=10` | **src 10/11/12 → 4004** (same numbering convention) |
| OPEN **4007** | local TCP listen `ETCH_PROXY_PORT` (phone-side) | **not on BT wire** (localhost proxy) |
| HANGUP (cmd 10) | on clean shutdown | **not seen** (teardown = eof / agent_stop) |
| instanceId | HU→Phone HS field → Android `EXTRA_INSTANCE_ID` | Dummy sent **1**; phone does not TX HS |

## Code facts worth keeping (desk, still useful)

1. **State machine:** OPENING → wait HS → INITIALIZING → NEGOTIATING → ACTIVE (`BclClientTransport.connect`).
2. **Fragile HS read:** `available() >= 16` before `readHandshake` — can re-INIT while partial HS buffered (this client). Analyzer requirement = stream reassembly, not “must coalesce writes”.
3. **Watchdog** is post-ACTIVE DestProtocol on port **5001**; pong = any bytes; not a connection opener.
4. **Multiplexer:** `ProxyConnectionGrantor` starts src ports at **10** — matches wire Etch channels.
5. **KNOCK** layout: serial/bt/mac/wifi lens + appType + param1 (post-SELECTPROTO when version>3).
6. **4007** = phone-local Etch proxy announce; **4004** = BCL dest toward car (Etch *candidate* until F20 confirms).

## Capture checks already done

```text
DATAACK count = 0   (all sessions)
KNOCK count   = 0
HANGUP count  = 0
INIT count    = 1 per session (HS answered immediately)
WD median     ≈ 2505 ms
Session life  ≈ 38.3 s → eof (Dummy echo_watchdog=false)
```

## Implications

- Do **not** re-pin audit to a hypothetical AAIdrive-bundled lib without APK evidence.
- Do keep BclCarLink as **structural** reference (ports, HS layout, mux, states).
- F20 decoder phases: Transport → INIT(/retry) → HS identity → SELECTPROTO → ACTIVE (OPEN 5001) → OPEN channels → Teardown (HANGUP? / DISC).
- Lab L3 (no HS): **ran** (`LAB_L3_NO_HS_20261113T2329Z`) — phone opened RFCOMM 3× but sent **DEADBEEF+UUID announce**, not INIT. INIT-Kadenz still unmeasured; different opener/path under silent Dummy.

## L3 surprise (observe-only)

```text
deadbeef | dead0100 | len=0x2c | 01 01 | ASCII uuid | 00 | deadbeefbeef
uuid = 0e9b90c4-cbe1-4742-8283-d367e9a56619   (looks session-generated)
gap between RFCOMM attempts ≈ 9 s
```

Not BclCarLink `waitForHandshake` behavior (that would spam `12345678`). Strengthens: **wire client ≠ pinned BclCarLink**, and eligibility/handshake answering changes which phone PDU you see first.
