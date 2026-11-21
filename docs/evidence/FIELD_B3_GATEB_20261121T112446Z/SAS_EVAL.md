# Field SAS b2a-tx — 20261121T113123Z

**claim:** FIELD MEASURED (lab-stub cert → F20)
**path:** BT-Analyzer-Phone `.87` → F20 `D4:36:39:CF:E1:B5` ch6
**log:** `sas_b2a_tx.jsonl`

## Result

| Step | Outcome |
|------|---------|
| RFCOMM ch6 | connected |
| BCL HANDSHAKE | rx |
| `sas_certificate` | sent (mybmw-sim / lab stub) |
| HU reply | **CERTIFICATE_REJECTED** |
| Freeze | `--stop-on-auth-reject` OK |
| AM/RHMI | not started |

## Gate interpretation

- **Transport/SAS path to real F20:** works (Arm A style reject)
- **Gate B ACCEPT:** CLOSED in live B3 session (`EVAL.md`); this file is **Arm-A stub control only**

