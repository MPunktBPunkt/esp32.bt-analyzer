# LAB B3 prep — 2026-11-19

## Verdict

| Path | Result | Claim |
|------|--------|-------|
| B3 **tcp-lab** phone→relay→f20_sim | **PASS** (HS + 30 BCL frames, decode) | LAB |
| B3 **RFCOMM air** USB→.131→relay→.87 | **FAIL** | LAB |

## RFCOMM air failure

- BlueZ Profile ch6 is host-global → HU must use **raw** RFCOMM on .87 (smoke script).
- B3 listen on .131 started OK.
- Phone USB→.131: `rfcomm_connect_failed Host is down`.
- Classic inquiry **.131↔.87** and **USB↔.131** found no peers (RSSI WiFi ~−81…−84). Same class of failure as prior Dual-ESP discovery notes.

## Evening implication

B3 does **not** need .131↔.87 bonded to each other. Needed bonds:

- Phone ↔ .131 (BMW)
- .87 ↔ F20

Userspace relay on .108 copies RFCOMM bytes. At this WiFi budget, **pre-existing bonds** + `wifi_ps=none` are mandatory; do not rely on fresh inquiry.

## Tooling shipped

- `tools/b3_rfcomm_relay.py`: `--connect-adapter-bd` for dual-radio outbound bind
- `tools/lab_b3_dual_esp_smoke.py`: orchestrated air smoke (blocked here by discovery)

## Artifacts

- `b3.jsonl` — tcp-lab relay decode
- `hu.jsonl` — f20_sim TCP HU
