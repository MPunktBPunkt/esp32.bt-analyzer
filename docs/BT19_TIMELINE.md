# BT19 — Multi-node timeline (clock-offset estimation)

```yaml
status: active_scaffold
fw: "0.3.0+"
method: http_sync_marker_rtt_midpoint
```

## Claims (explicit)

| Claim | Status |
|-------|--------|
| PTP | **NO** |
| shared clock | **NO** |
| estimated timeline alignment | **YES** |

This is **clock-offset estimation**, not clock sync.

Per node the lab records:

- `offset_s` (debian_unix midpoint − mono_us/1e6)
- `rtt_ms` / jitter
- `uncertainty_ms` (≈ RTT/2)
- `sample_count`

## Tools

```bash
python3 tools/lab_clock_sync.py --rounds 20
python3 tools/lab_multi_node_timeline.py --seconds 20
python3 tools/lab_multi_node_timeline.py --dry-run   # offline schema + host_bt embed
```

Evidence: `docs/evidence/LAB_CLOCK_SYNC_*.json` · `LAB_TIMELINE_*.jsonl` + `.meta.json`

Meta embeds optional `host_bt` snapshot from [`lab_host_bt_probe.py`](../tools/lab_host_bt_probe.py) (Debian/Proxmox radio inventory).

## What this enables next

```text
BT analyzer timeline
    ├── USB analyzer timeline   (later)
    └── hu-probe / AOA timeline (later)
         ↓
    Cross-layer correlation (BT20) — no MITM claim
```

BT20 scaffold: [`BT20_CORRELATION.md`](BT20_CORRELATION.md) · `tools/lab_bt20_correlate.py` (0.3.6).

Prerequisite for BT17 Classic flavor start: BT16-B benchmark evidence + this timeline scaffold producing aligned JSONL.
