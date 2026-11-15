# LAB — Silent-HU RX decode: INIT vs KNOCK (2026-11-15)

Source: [`LAB_SILENT_HU_result.json`](LAB_SILENT_HU_result.json) (Phone → silent Dummy-HU).

## LAB FACT: 4-byte chunks = BCL INIT

Every 4-byte chunk is exactly:

```text
12 34 56 78
```

Same bytes as `BclClientTransport.initSession()` / `INIT_MAGIC` in this repo.
**Not** Watchdog (`13 37 13 37`).

| Field-type (14.11 inference) | Corrected (15.11 LAB FACT) |
|------------------------------|----------------------------|
| Typ B, 5× 4 B @ ~3 s — „Watchdog-Ping“ | **INIT retries** `12345678` |

Silent-HU never leaves bootstrap → no WD phase. Therefore Silent-HU **cannot**
calibrate field WD / M9 tick edges. Useful as negative reference only.

## Strong INFERENCE: 56-byte chunk = KNOCK-related payload (UUID serial)

Hex (all 56-B sessions identical):

```text
deadbeef dead 01000000 2c0101
30 65 39 62 39 30 63 34 2d 63 62 65 31 2d 34 37 34 32 2d
38 32 38 33 2d 64 33 36 37 65 39 61 35 36 36 31 39
00 deadbeefbeef
```

| Offset | Bytes | Decode |
|-------:|-------|--------|
| 0–3 | `deadbeef` | envelope magic |
| 4–5 | `dead` | envelope tag |
| 6–9 | `01000000` | u32 LE = 1 |
| 10–12 | `2c 01 01` | meta (length/flags — layout still open) |
| 13–48 | ASCII | **`0e9b90c4-cbe1-4742-8283-d367e9a56619`** |
| 49 | `00` | NUL |
| 50–55 | `deadbeefbeef` | trailer |

Same UUID-serial as lab KNOCK (`LAB_LIVE_GREEN_*`, SP4+KNOCK appType=1/param1=7).

### What this is **not**

Not a raw `BclPacket` KNOCK wire frame (`cmd=8 | src | dest | len | …`).
No BCL 8-byte header; envelope is `deadbeef…deadbeefbeef`.

**Saubere Formulierung:** Etch-/session-bootstrap blob carrying the KNOCK
UUID-serial — **not** „BCL-KNOCK-Paket cmd=8“.

## Timing vs field (M29)

| | Field (14.11, silent HU) | Silent-HU lab (15.11) |
|--|-------------------------|------------------------|
| INIT spacing | ~3.000 s ±1 ms | 3–12 s, irregular |
| 56-B session | ~9.7–9.9 s then close | 9–124 s, single chunk |
| INIT session length | ~15.03 s | 15 / 32 / 58 / 109 / 125 s |

First lab sessions resemble field; later diverge. Field M9 tick edges are
**not** confirmed as constant client timers by Silent-HU.

## Consequence for field typology (14.11)

Phone traffic against a silent HU was INIT (+ occasional 56-B bootstrap),
never WD. Old „Phone TX = WD @ 3 s“ inference is **REJECTED**.
