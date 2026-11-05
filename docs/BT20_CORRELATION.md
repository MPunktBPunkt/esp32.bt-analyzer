# BT20 — Cross-layer correlation (no MITM)

```yaml
status: scaffold_0.3.6
fw_required: "0.3.5+"
claim: cross_layer_window_via_debian_bridge_not_MITM
```

## Rule (frozen)

```text
BT Analyzer timeline (BT19)  ─┐
BlueZ host events (wall clock)├─→ debian_unix bridge → window overlap
usb-analyzer lane (later)    ─┤
hu-probe markers (later)     ─┘
```

This is **window correlation**, not transparent phone↔car forwarding.

| Claim | Status |
|-------|--------|
| PTP / shared clock | **NO** |
| MITM / proxy | **NO** |
| Air/RF | **NO** |
| Estimated window overlap via debian bridge | **YES** |

## Lanes

| Lane | Source | Time domain |
|------|--------|-------------|
| `bt_esp` | BT19 JSONL / sync-marker samples | `mono_us` + offset → `debian_unix_est` |
| `bt_host` | Proxmox BlueZ via `lab_bt_host_ssh.py` | debian wall clock at event |
| `usb` | usb-analyzer export / synth | `timestamp_us` or debian |
| `hu` | hu-probe `events.jsonl` / synth | `t_us` or debian |

## Tools

```bash
# Offline schema (no HW)
python3 tools/lab_bt20_correlate.py --synth

# Live: BlueZ × ESP triad (Proxmox + .88/.89/.87) — no usb/hu nodes required
python3 tools/lab_bt20_correlate.py --live-bt

# Offline fuse existing artifacts
python3 tools/lab_bt20_correlate.py \
  --bt19 docs/evidence/LAB_TIMELINE_<UTC>.meta.json \
  --usb-jsonl /path/to/usb.jsonl \
  --hu-jsonl /path/to/hu/events.jsonl
```

Evidence: `docs/evidence/LAB_BT20_*.json` + `.md`

## What is still UNKNOWN

- Live usb-analyzer + hu-probe nodes on the same session (needs operator flash / car)
- Sub-ms lock across radios
- Any claim that BT frames “are” USB AOA frames
