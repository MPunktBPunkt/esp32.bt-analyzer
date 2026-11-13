# LAB_PHONE_BCL decode — baseline freeze (2026-11-13)

Source: `LAB_PHONE_BCL_20261113T2201Z_{hu.jsonl,btsnoop}` · peer OnePlus `AC:C0:48:5E:CB:20` · Dummy `C8:C9:A3:CB:7B:0A` ch6.

## Reference signature (measured)

```text
RFCOMM CONNECT
  +100…200 ms  Phone TX  12 34 56 78
  ~same ts     Dummy TX  HANDSHAKE  (cmd=4,len=8)
  +~3.1 s      Phone TX  SELECTPROTO payload 0002
  +~70 ms      Phone TX  OPEN  src=5001 dst=5001
  +~0          Phone TX  DATA  5001  payload 13 37 13 37
  +~0.5 s      Phone TX  OPEN  src=10  dst=4004
  …            DATA Etch deadbeef + PKCS7 (app certs)
  +~2.5 s      Watchdog DATA 13371337 (steady)
```

Three almost identical phone sessions; reconnect gap after RFCOMM close ≈ **5.1–5.7 s**.

## HANDSHAKE / instanceId

| Field | Who | Value in this capture |
|-------|-----|------------------------|
| version | **HU→Phone** | **3** (Dummy) |
| instanceId | **HU→Phone** | **1** (Dummy default) |
| bufferSize | **HU→Phone** | **0x8000** (Dummy) |

Phone **does not** send HANDSHAKE. Desk expectation `instanceId 12–14` for “new Connected” applies to a **real HU** answer — not available here. Lab next: vary Dummy `instanceId` and observe phone reaction (still not F20 fingerprint).

Raw Dummy HANDSHAKE: `00 04 00 00 00 00 00 08 00 03 00 01 00 00 80 00`.

## Desk vs wire discrepancies (FACT updates)

| Claim (desk / BclCarLink) | Lab wire (AAIdrive/MyBMW stack) |
|---------------------------|----------------------------------|
| SELECTPROTO only if `version > 3`, payload **3** | Phone sends SELECTPROTO even for **version 3**, payload **`0002`** |
| Watchdog interval **5 s** | Median **~2505 ms** (n=13 deltas × 3 sessions) |
| OPEN 5001 before OPEN 4004 | **Confirmed** |
| INIT → HANDSHAKE → … | **Confirmed** (phone = RFCOMM client) |

## Etch / PKCS7 (generation / app fingerprint)

Envelope: `deadbeef` \| `u32be` length \| 16-byte digest \| PEM PKCS7 \| 15-byte trailer.

| BCL src → 4004 | App CN (leaf) |
|----------------|---------------|
| 10 | `a4a_app_myBMW.perm___applicationmanager_<hash>` |
| 11 | `a4a_app_mobile___com_smartthings_android_00.00.03` (OPEN then quick CLOSE/re-OPEN) |
| 12 | `a4a_app_myBMW.perm___cdsbaseapp_<hash>` |

Chain always includes `a4a_app_BMWTouchCommand_Connection_00.00.10` + `a4a_android-ca` ← `a4a_root-ca`.

So “verbunden mit BMW” rides on a **real BCL+Etch cert push** from MyBMW/AAIdrive apps — Dummy never answered SAS.

## Epistemic

```text
YES: Phone BCL client state machine against Dummy is reproducible
YES: Watchdog TX period ≈ 2.5 s (lab FACT for this stack)
YES: SELECTPROTO(2) after v3 HANDSHAKE (lab FACT; desk branch incomplete)
NO:  F20 HU version/instanceId
NO:  Which Connected “generation” instanceId 12–14 would look like on wire (need real HU HS)
```
