# LAB — CoD A/B with ACL bounce + A2DP correlation · 2026-11-13 ~23:55

```yaml
status: PASS
verdict: COD_WITH_RECONNECT_SELECTS_FIRST_PDU
dummy: BMW 38304 / ch6 HANDSHAKE / alias unchanged both phases
phone: OnePlus · AAIdrive+MyBMW · ACL bounced after each CoD change
```

## Controlled A/B (ACL bounce required)

| Phase | Dummy Class | After disconnect/connect | First PDU |
|-------|-------------|--------------------------|-----------|
| **A** | `0x4c0104` (Computer) | 3× CONNECT → **DEADBEEF+UUID** → eof | **no INIT** |
| **B** | `0x340408` (F20-like) | CONNECT → **`12345678`** → HANDSHAKE → … | **no DEADBEEF** |

Without ACL bounce, CoD changes alone are sticky (phone may keep prior path) — earlier weak A/B saw INIT under computer CoD until bounce.

## A2DP vs BCL session (correlation log)

`LAB_A2DP_BCL_CORR_20261113T2353Z.jsonl`: MediaTransport stayed **`idle`** through INIT/HS/WD and at RFCOMM close; Device **Connected=true**.

```text
REJECT (for this lab): "~38s BCL eof caused by A2DP drop" (Mistral Muster 2 as hard claim)
YES: phone sends CLOSE on dest 5001 then RFCOMM eof without Dummy watchdog pong
YES: CoD gate is outside BclCarLink@7cfd959 (no CoD check in BtClientService)
```

So C-L10 stands, but as **CoD(+reconnect) → first-PDU family**, not proven as “A2DP-liveness modulated by CoD” on this Dummy (A2DP profile present, transport idle both phases).

## Vs Bimmer code

- `isCar()` name prefix satisfied both phases (`BMW 38304`).
- `hasBCL()` / A2DP filter: A2DP object present; transport not `active` while BCL runs — BCL still starts under car CoD.
- Session teardown matches missing WD pong more than A2DP shutdown.
