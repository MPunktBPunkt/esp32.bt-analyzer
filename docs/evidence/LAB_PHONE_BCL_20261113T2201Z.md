# LAB — OnePlus/MyBMW/AAIdrive BCL against Dummy-HU (2026-11-13 ~23:01)

```yaml
status: PASS (LAB_TEST)
verdict: PHONE_OPENED_BCL_TO_DUMMY
ui: AAIdrive „verbunden mit BMW“ (operator)
dummy: C8:C9:A3:CB:7B:0A · alias BMW 38304 · SPP „BMW Connected“ ch6 · answers HANDSHAKE
phone: OnePlus 12 AC:C0:48:5E:CB:20
capture: LAB_PHONE_BCL_20261113T2201Z.btsnoop
hu_log: LAB_PHONE_BCL_20261113T2201Z_hu.jsonl
```

## What happened

1. Lab `b2a-tx` from `.87`/`37:96` → Dummy ch6: INIT → HANDSHAKE (tool check).  
2. **OnePlus** then opened RFCOMM to the same Dummy SPP **three times**; each time: phone `12 34 56 78` → Dummy HANDSHAKE v3.  
3. After HANDSHAKE (~+3.1 s): phone `SELECTPROTO` payload **`0002`**, then **OPEN 5001** + Watchdog `13371337`, then **OPEN 4004** + `deadbeef`/PKCS7.
4. AAIdrive shows **„verbunden mit BMW“** — BT/BCL path, **not** USB-AOA.

Full byte/timing decode: [`LAB_PHONE_BCL_20261113T2201Z_DECODE.md`](LAB_PHONE_BCL_20261113T2201Z_DECODE.md).

## Epistemic

```text
YES:  Real phone (MyBMW stack) is RFCOMM client to 0x1101 SPP on a Dummy that looks car-like
YES:  Order: Phone INIT → HU HANDSHAKE → SELECTPROTO → OPEN 5001 → OPEN 4004
YES:  Watchdog TX period ≈ 2.5 s (desk 5 s outdated for this stack)
YES:  AAIdrive „verbunden“ tracks BT/BCL (C-L4/C-L5 were eligibility failures, not “AAIdrive never opens RFCOMM”)
NO:   Phone does not send HANDSHAKE — instanceId is HU→Phone only (Dummy sent 1)
NO:   F20 HU wire / real Etch/SAS answers
```

## Implication for F20

H-A strengthened for **lab**: when SPP+A2DP+HANDSHAKE-capable peer exists, the phone **does** TX INIT without us simulating State C in a car.  
State C / `b2a-tx` on the **real HU** remains the F20 confirmation — but Dummy is no longer a dead end for phone BCL.

## Artifacts

| File | Role |
|------|------|
| `*_hu.jsonl` | full Dummy session (RX frames incl. certs) |
| `*.btsnoop` | btmon on hci1 |
| `*.json` | frame-count summary |
