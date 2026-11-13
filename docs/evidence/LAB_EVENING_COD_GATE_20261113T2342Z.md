# LAB — CoD eligibility gate (DEADBEEF probe vs BCL INIT) · 2026-11-13 ~23:42

```yaml
status: PASS (LAB_TEST)
verdict: COD_SELECTS_PHONE_FIRST_PDU
dummy: C8:C9:A3:CB:7B:0A · alias BMW 38304 · SPP ch6 HANDSHAKE-ready
phone: OnePlus AC:C0:48:5E:CB:20 · AAIdrive + MyBMW running
```

## Finding

| Dummy Class | Phone first RFCOMM PDU | Follow-on |
|-------------|------------------------|-----------|
| `0x4c0104` / `0x4c0408` (Computer) | `deadbeef…` + ASCII UUID `0e9b90c4-…` + `deadbeefbeef` | RFCOMM eof ~9 s; **no** INIT |
| **`0x340408`** (F20-like) | **`12 34 56 78`** | Dummy HANDSHAKE → SELECTPROTO(2) → OPEN 5001/4004 → PKCS7 → WD ~2.5 s |

Same night log: **22×** DEADBEEF-sessions while CoD wrong / after observe-only; **3×** full BCL after CoD restore (`LAB_EVENING_COD_GATE_*_hu.jsonl`).

Also seen under pure observe-only (no HANDSHAKE): same DEADBEEF PDU (`LAB_L3_NO_HS_*`) — so the probe is the phone’s **non-BCL / pre-BCL** SPP opener when the peer fails the car/BCL eligibility path.

## Vs BclCarLink@7cfd959

BclCarLink has **no** `deadbeefdead…uuid` announce — only `12345678` in `waitForHandshake`. This PDU family is further evidence the live stack ≠ pinned BclCarLink, and that **CoD is part of the MyBMW eligibility gate** (alongside SPP `0x1101` + A2DP + HANDSHAKE answer).

## Ops

Keep Dummy: `hciconfig hci1 class 0x340408` + alias `BMW 38304`. Drift to computer CoD silently kills BCL and looks like “AAIdrive broken”.
