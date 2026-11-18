# B3 Transparent Relay — Freeze

```yaml
status: FROZEN for field day
selftest: 95/95 byte-identity PASS (LAB_GATE_AUTH_AB_B3)
```

No further optimization before the auth gate.

## Field-day smoke (only if relay needed)

```text
phone/CSR → B3 transparent relay → ESP/.87 → RFCOMM HU
```

Pass criteria: connect + byte-identity selftest + short bulk. Then freeze again.

CSR↔ESP air RFCOMM is already PASS (~LQ 249–255, 0 drops) — performance gap is HCI-over-WiFi, not a B3 blocker.

Tool: `tools/b3_rfcomm_relay.py selftest`
