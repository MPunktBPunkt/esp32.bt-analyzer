# Simulator-kt scope + analyzer effort (2026-11-13)

```yaml
status: desk_verified
decision: no multi-week analyzer rebuild; minimal field tools shipped
simulator: Layer E TCP :4006 only — not BCL/RFCOMM
field: docs/CAR_FIELD_1H.md
```

## Simulator

`Simulator-kt` = Fake-HU for **Etch/SAS-stub/RHMI/limited CDS** on `0.0.0.0:4006`.
Not: Bluetooth, SDP, RFCOMM, BCL handshake/watchdog, F20 capabilities, AV proof.

Three lab worlds stay separate: **A** F20 field · **B** Dummy-HU/BclCarLink · **C** Simulator Etch.

B0.8-direct (AAIdrive→:4006) = P1 later. BCL→Etch gateway = P2 only after need.

## Analyzer

Full 5-layer rebuild ≈ weeks — **rejected for now**.

Minimal (implemented):

| Piece | Location |
|-------|----------|
| BCL levels UNKNOWN→FIELD_CONFIRMED | `tools/bcl_classify.py` |
| B2-B/B2-A no TX | `bcl_dummy_hu_agent.py` `b2b`/`b2a` |
| ObserveOnlySession | `tools/bcl_dummy_hu.py` |
| 1h orchestrator | `tools/field_b1_b2.py` |

Still P1 (not blocking tonight): btmon UIH auto-extract; btsnoop import pipeline.

## Tonight

P0 = car B1 + B2-A + B2-B observe-only. See `CAR_FIELD_1H.md`.
