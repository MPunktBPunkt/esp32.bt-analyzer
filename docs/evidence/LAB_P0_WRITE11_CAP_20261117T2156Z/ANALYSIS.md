# LAB P0 write11 capture analysis — 20261117T2156Z

**claim_level:** LAB FACT (instrumented)  
**artifacts:** `CAPTURE.md`, `capture_report.json`, `hu_hci2.btsnoop*`, `phone_hci1.btsnoop*`, `hu_ab_87131.jsonl`, `phone.jsonl`

## Confirmed

| Fact | Value |
|------|-------|
| `os.write` errno | **11 / EAGAIN** (`errno_name` logged) |
| bytes attempted at fail | **89** (small frame — not a 4k BCL blast) |
| time connect → fail | **~1.55 s** |
| phone `hold_s` until WD abort | ~24 s (WD miss is **consequence**, not the write moment) |
| tx before fail | 93 frames / 5250 B / max 500 B / mean gap **12 ms** |
| last RX before fail | **0.6 ms** earlier (RX healthy) |
| last OK TX before fail | **0.1 ms** earlier |
| context | mid **CDS subscribe / getPropertyAsync** reply flood |
| ESP bootGen | unchanged (25/3) |

## btmon (HU hci2)

- Dense RFCOMM UIH during the CDS burst
- Credit fields still show **~30–33** near the end (not an obvious air-credit=0 story in this decode)
- Then RFCOMM **DISC** / UA / L2CAP disconnect

## Interpretation vs prior ranking

**Still strong:** RFCOMM/socket TX backpressure — userspace blasts replies faster than the BlueZ RFCOMM socket (and/or dual-ESP ACL path) can accept → `EAGAIN` → agent closes → phone later reports `WATCHDOG_MISS_NO_ETCH_REPLY`.

**Nuance vs “long session”:** In this capture write11 is an **early burst** failure (~1.5 s), not a 5‑minute soak. Batch “~25 s” was the phone WD timeout after the socket was already dead.

**Credits:** Visible RFCOMM credits ≠ 0 at fail → points more to **socket/queue / host→controller drain** than classic “credits exhausted on wire”. Single-ESP A/B remains the discriminator for Bridge/Proxy amplification.

## Decision-matrix tick

| Observation | Bucket |
|-------------|--------|
| errno 11 EAGAIN on HU write | Flow / socket not ready |
| tiny 89 B write fails after burst | Queue full, not payload-too-large alone |
| credits still ~30 | less “air credits=0”, more host/bridge drain |
| Dual-ESP path | Bridge/Proxy still open (needs Single-ESP) |
| no bootGen bump | ESP panic out |

## Next

1. **Single-ESP BCL** (same instrumented agent) — Dual fail / Single pass ⇒ Bridge; both fail ⇒ BlueZ/HU-side socket.
2. Optional: pace CDS replies / coalesce TX in HU agent to test whether EAGAIN disappears (mitigation probe, not root cause claim).
