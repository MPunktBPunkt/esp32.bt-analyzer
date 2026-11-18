# LAB CSR performance batch — 20261118T2107Z

**claim_level:** LAB FACT

## A) Host unit tests

- AuthState / field-replay / B3 / auth A-B / dummy HU / etch: **57 OK**

## B) CSR ↔ USB-Phone RFCOMM (ch 22)

| Run | Verdict | Payload | Dur s | Ping med ms | →CSR kB/s | CSR→ kB/s |
|-----|---------|---------|-------|-------------|-----------|-----------|
| `p240` | **PASS** | 240 | 12.0 | 13.97 | 91.02 | 93.08 |
| `p300` | **PASS** | 300 | 12.0 | 12.99 | 114.55 | 114.86 |
| `p64` | **PASS** | 64 | 12.0 | 13.0 | 49.39 | 28.83 |
| `soak240_45s` | **PASS** | 240 | 45.0 | 13.53 | 90.81 | 92.26 |

## C) CSR ↔ ESP .87 air RFCOMM

**FAIL** both role orientations (`Host is down` / accept timeout).
HCI shows ghost ACL (handle 3840, 0 ACL bytes on virtual hci1) — Classic RFCOMM
CSR↔ESP-bridge not usable for this perf path. USB↔USB remains the CSR capability proof.

- `air_esp_server`: `accept_failed: TimeoutError('timed out')` / client `OSError(112, 'Host is down')`

## Notes

- OnePlus ACL on HU `7B:0A` left intact during tests.
- CSR alias pinned `BT-Analyzer-CSR` after runs.
- Tool: `tools/lab_usb_rfcomm_perf.py`

