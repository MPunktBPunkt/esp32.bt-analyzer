# Deep analysis — BCL audit sources vs lab (2026-11-12)

```yaml
status: desk_verified
pins:
  BclCarLink: 7cfd959   # /tmp/ta-audits/BclCarLink
  Simulator: local /tmp/bmw-auth-audit/Simulator
audits:
  - bimmergestalt-idrive-2026-foreign
  - bmw-bcl-rfcomm-role-2026-desk
  - bmw-connected-sas-auth-2026-11-06
claims_doc: pidrive HU-Technical-Facts §10 (C-D13…C-D29)
measures: docs/MASSNAHMEN_BCL_A6.md
```

Epistemic: Desk/code FACT unless marked otherwise. **No F20 wire FACT.**

## 1. Executive verdict

The multi-model analyses converge correctly on **Transport-Owner vs Etch-Consumer**. Code at BclCarLink@7cfd959 confirms: RFCOMM client → `12 34 56 78` → HANDSHAKE → optional SELECTPROTO/KNOCK → ACTIVE → **Watchdog OPEN 5001 first** → local TCP `:4007` listen → **ATTACHED** → only later, on consumer connect, **OPEN 4004**.

AAIdrive/`NO_RFCOMM` against Dummy-HU is **expected**. Simulator helps **Layer E only**. A6 remains the only path to channel X, SABM direction, and real `version`.

**Bug found, not patched upstream:** `BclOutputStream` (`C-D27`). Documented; our Python tools do not copy it.

## 2. Evidence strength map

| Layer | Strongest IDs | Strength | Weak / overclaim risk |
|-------|---------------|----------|------------------------|
| **T** RFCOMM | EVID-BCLRF-001/002/005 | FACT (client, SPP UUID, A2DP hint) | 003 HU=server = **INFERENCE** only |
| **B** BCL | EVID-BG-001…007, BclClientTransport | FACT framing/init/handshake rule | Init “8 bytes from hex” wording historically confusing → **4 B** |
| **WD** | EVID-BCLRF-004 + WatchdogProtocol | FACT request/timing | Pong layout often overclaimed → **UNKNOWN** |
| **E** Etch/SAS | EVID-BG-008…011, SAS audit | FACT API order | Simulator SAS = open stub ≠ crypto |
| USB/ENET BCL | EVID-BG-020/026 | Contradiction | Must **not** say REJECTED |
| Lab messkette | LAB_BCL_SYNTH_*, DUMMY_HU_SDP, A2DP NO_RFCOMM | MEASURED lab | Channel 5 lab-only |

## 3. Code-verified sequence (T → B → E)

```text
BtConnection: createRfcommSocketToServiceRecord(SDP_BCL=00001101…) → connect()
        ↓
BclClientTransport.connect():
  OPENING → write 12 34 56 78 every ~1s until ≥16 B available
        ↓
  readHandshake() must be HANDSHAKE else FAILED
        ↓
  NEGOTIATING: if version>3 → SelectProto(3) + Knock(empty×4, appType=0, param1=1)
        ↓
  ACTIVE
        ↓
BtConnection → multiplexer.openProtocols():
  1) WatchdogProtocol → openConnection(5001,5001)   ← BCL OPEN dest 5001
  2) factories: BclTunnelReport, EtchProxyService
        ↓
TcpProxyProtocol.startProxy():
  listen(:4007) → ProxyState.ACTIVE → announceProxy()
        ↓
  ACTION_CAR_ACCESSORY_ATTACHED (+ TRANSPORT_SWITCH=BT)
        ↓
  [idle until local TCP client]
        ↓
  consumer → :4007 → ProxyConnectionGrantor → openConnection(src, dest=4004)
        ↓
  BCL OPEN …→4004 → DATA (Etch)
```

**Knock empty fields:** `BclPacket.Knock` default data size 12; factory writes length-prefixed empty serial/bt/mac/wifi + appType + param1 → compact 12-byte payload + 8-byte header.

**Watchdog pong:** `watchdogListener.write(Int)` only updates `lastWatchdogPong` — any byte counts; **no** compare to `13 37 13 37`.

## 4. BclOutputStream defects (verified)

File: `…/bcl/BclOutputStream.kt` @7cfd959

| Method | Code | Correct Java/Kotlin OutputStream semantics |
|--------|------|-----------------------------------------------|
| `write(b: Int)` | `ByteArray(b)` | should write **one** byte `(b and 0xff)` |
| `write(buf, off, len)` | `sliceArray(off until len)` | should be `off until off+len` |

`SocketChannelOutputStream` in same tree is correct. Bootstrap paths usually call `write(fullArray)` → often masks the bug. **Etch proxy / partial writes = risk for B0.7/B0.8.**

Action: document only (`C-D27`); optional upstream issue; do not treat BclCarLink as gold wire.

## 5. Simulator value

| Proves | Does not prove |
|--------|----------------|
| Etch client happy-path against Fake-HU `:4006` | F20 SDP / RFCOMM / BCL version |
| SAS stub returns 16-byte challenge, login no-op | Cert/signature verification |
| RHMI/AM lab UX | OPEN 4004 on real HU |

**B0.8** = Layer E after a real BclCarLink BCL tunnel (or lab tunnel). Simulator ≠ Dummy-HU ≠ A6.

## 6. Corrections to prior analyses (keep / adjust)

| Theme | Verdict |
|-------|---------|
| Transport-Owner vs Etch-Consumer | **KEEP** — central |
| AAIdrive ≠ RFCOMM client | **KEEP** FACT (behavior) |
| MyBMW/Connected as RFCOMM opener | **UNKNOWN** on F20 — do not FACT |
| OPEN 4004 in deterministic bootstrap | **REJECT** that claim — consumer/TCP-triggered |
| ATTACHED after proxy listen | **KEEP** — before OPEN 4004 |
| Watchdog pong = 13371337 | **REJECT** as FACT — request only |
| USB/ENET BCL REJECTED | **REJECT** that meta-claim — Contradiction/HYPOTHESIS |
| A2DP = BCL transport | **REJECTED** — eligibility hint only |
| Four-direction chain SDP→SABM→INIT→HANDSHAKE | **KEEP** as B2 measurement design |
| States A–D for SDP | **KEEP** |
| Capture X/Y | **KEEP** |

## 7. Gap vs A6 readiness (bt-analyzer)

| Capability | Status |
|------------|--------|
| HCI-TCP dual D1 + bridge | PASS (lab) |
| `btmon -w` on `.87` hciN | available — **primary A6 capture** |
| `bcl_sdp_probe` | ready for B1 |
| `bcl_framer` streaming + session-init magic | ready for offline/post-process |
| Live HCI→L2CAP→RFCOMM→BCL state machine in Lab UI | **not required for A6** if btmon+offline framer used |
| BclCarLink on phone vs Dummy | B0.7 optional |
| Simulator wired into lab | B0.8 optional |

**Pre-A6 P1 only:** one smoke that a known RFCOMM capture feeds `bcl_framer` (INIT+HANDSHAKE). No new stack.

## 8. Delta measures (beyond MASSNAHMEN_BCL_A6)

Already covered there: A6, B1 A–D, B2 split, X/Y, B0.7/B0.8, OPEN 4004, WD pong UNKNOWN.

**Add:**

1. **P1** When post-processing A6 btsnoop: resync on `12 34 56 78` then require next frame `cmd=HANDSHAKE,len=8` — else `BCL_MISALIGNED` vs `NO_BCL`.
2. **P1** Log BclCarLink `instanceId` / `bufferSize` / `version` into evidence JSON schema fields (even if UNKNOWN until measured).
3. **P2** Optional upstream note/issue for `BclOutputStream` (no blocking).
4. **P2** Distinguish evidence labels: `BT_TRANSPORT` / `BCL_TRANSPORT` / `WD` / `ETCH_TUNNEL` / `SAS` / `RHMI` — never “Connected works”.
5. **P0 epistemic:** Official MyBMW opener remains UNKNOWN in Facts (`C-D28`) — do not upgrade without Wire.

## 9. Suggested doc patches (done / remaining)

| File | Status |
|------|--------|
| `HU-Technical-Facts` C-D16 sharpen, C-D24–29 | done |
| `MASSNAHMEN_BCL_A6.md` | done |
| `CAR_A6_B1.md` B1 states + B2 split | done · **superseded 2026-11-13** by B2-A/B2-B two-mode |
| Two-mode + Secondary fold-in | done — `BCL_RFCOMM_TWO_MODE_20261113.md` · pidrive C-D30/C-S* |
| `bmw-bcl` sheet Watchdog pong wording | **remaining** in technology-audit if still says pong=13371337 |
| Upstream BclCarLink issue | optional |
| B2-B observe-only code mode | **remaining** (ProfileManager reuse; BCL-TX off) |

## 10. One-liner

Desk stack is strong enough to **observe** A6 correctly; only the car closes channel, direction, and version. Simulator and BclCarLink are lab amplifiers for Layers E and B — not substitutes for F20 wire.
