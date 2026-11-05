# Capture Session — Recorder foundation (0.3.9)

```yaml
status: active_0.3.9
goal: AAIdrive_BMW_HU_capture_not_proxy
claim: HCI_session_recorder_not_air_not_MITM
```

## Measures derived (GPT → actionable)

| # | Measure | Why | Status |
|---|---------|-----|--------|
| M1 | Session-ID + START/STOP | Bind HCI frames into one reverse-engineering run | **0.3.9** |
| M2 | Operator MARK labels | Cut AAIdrive UI moments out of the stream | **0.3.9** |
| M3 | Keep raw HCI (BTAC) | Not only “GATT PASS” — transport bytes stay | **already BTAC** |
| M4 | TX/RX + mono µs + seq | Ordering for RE / later USB×BT correlate | **already BTAC** |
| M5 | BT_EVENT view | Same schema for Proxmox / PiDrive tooling | **0.3.9 mapper** |
| M6 | Offline drain | Capture must not depend on live TCP | **HTTP drain when no BTAC client** |
| M7 | Classic SDP/L2CAP/AVRCP decode | Observe first, implement later | **deferred until real BMW run** |
| M8 | Store-and-forward Auto↔Haus | `.89` ring → TCP when WiFi returns | **scaffold API; full S&F later** |
| M9 | Transparent BT proxy | BMW⇄Handy via TCP | **NO (out of scope)** |

## Architecture (frozen)

```text
BMW HU ⇄ Bluetooth ⇄ .89 (local BT + ring + session)
                         │  BTAC / HTTP drain (seq, gaps visible)
                         ▼
                      .88 / Proxmox collector
                         │
                         ▼
                   BT_EVENT JSONL / PCAPNG(HCI)
```

Capture **never** requires TCP to keep recording. Gaps are marked, never silent.

## BT_EVENT (conceptual)

Mapped from BTAC frames (+ session meta as `packet_type=meta`):

```json
{
  "seq": 18472,
  "timestamp_us": 123456789,
  "node_id": "89",
  "session_id": 42,
  "transport": "hci",
  "layer": "hci",
  "direction": "rx",
  "connection_id": 64,
  "event_type": "acl",
  "payload_hex": "..."
}
```

Session control events (`START` / `STOP` / `MARK` / `GAP`) use `event_type=session_*` and optional `label`.

## APIs

```bash
POST /api/capture/session/start   # → session_id, resets session drop baseline
POST /api/capture/session/mark    # label=MENU_NAVIGATION
POST /api/capture/session/stop
GET  /api/capture/session         # status
GET  /api/capture/drain?n=64      # offline path when BTAC client absent
```

## Labs

```bash
python3 tools/lab_capture_session.py
python3 tools/btac_to_btevent.py docs/evidence/….btac -o ….btevent.jsonl
```

## Evening BMW / AAIdrive

1. `.89` in car (or lab Classic peer) · session START  
2. MARK: `APP_START` / `MENU_OPEN` / …  
3. STOP · pull BTAC · map BT_EVENT  
4. Only then decide SDP/RFCOMM/AVRCP decoder depth from **observed** channels
