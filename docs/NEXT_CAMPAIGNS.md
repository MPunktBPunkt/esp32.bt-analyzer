# Next campaigns — Capture recorder → AAIdrive / BMW

```yaml
status: shipped_0.3.9
package: "0.3.9"
anchor: CAPTURE_session_foundation
fw_lab: "0.3.9"
```

## Measures (from GPT) — priority order

| Prio | Measure | Package |
|------|---------|---------|
| **P0** | Session START/STOP/MARK + raw HCI keep | **0.3.9** |
| **P0** | BT_EVENT view (seq/ts/dir/payload) | **0.3.9** |
| **P0** | Offline drain when no BTAC client | **already** + documented |
| **P1** | Classic SDP/L2CAP/RFCOMM **observe** on real BMW run | evening |
| **P1** | AVRCP payload in session (not just UUID inventory) | evening |
| **P1** | Store-and-forward Auto `.89` → Haus | next after first car capture |
| **P2** | USB×BT correlation IDs (BT20 live) | after car session |
| **NO** | Transparent BT proxy / RF tunnel / MITM | rejected |

## 0.3.9 labs

| Tool | Purpose |
|------|---------|
| `lab_capture_session.py` | START → marks → LE traffic → STOP → BTAC → BT_EVENT |
| `btac_to_btevent.py` | BTAC → BT_EVENT JSONL |

Docs: [`CAPTURE_SESSION.md`](CAPTURE_SESSION.md)

## Evening BMW / AAIdrive

```text
.89 session START → MARK APP_START → … → MARK MENU_* → STOP → pull BTAC
→ decide SDP/RFCOMM/AVRCP decoder depth from observed channels only
```
