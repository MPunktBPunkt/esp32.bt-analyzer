#!/usr/bin/env python3
"""SBC bit rate per A2DP leg vs the measured HCI-TCP coex budget.

Reads the negotiated SBC configuration (AVDTP Set Configuration) from btmon
text or a btsnoop file and prints the wire rate each leg needs. The maximum
bitpool from Set Configuration is the upper bound the encoder may use; Android
and PipeWire encode at that maximum unless congestion lowers it.

Usage:
  python3 tools/a2dp_budget.py --btsnoop /tmp/relay.btsnoop --budget 38
  btmon -i hci1 | tee /tmp/b.txt ; python3 tools/a2dp_budget.py --btmon /tmp/b.txt
  python3 tools/a2dp_budget.py --table --budget 38          # bitpool table only
"""

from __future__ import annotations

import argparse
import math
import re
import subprocess
import sys

# Coex budget per ESP under wifi_ps=none (docs/evidence LAB_HCI_TCP_*: 36–45 kB/s sustained).
DEFAULT_BUDGET_KBPS = 38.0
DEFAULT_HEADROOM = 0.8
DEFAULT_MTU = 895
RTP_SBC_HDR = 12 + 1
L2CAP_ACL_H4_HDR = 4 + 4 + 1

_HDR = re.compile(r"^([<>@=]) .*?\[(hci\d+)\]")
_FIELDS = {
    "freq": re.compile(r"^\s*Frequency: (\d+)"),
    "mode": re.compile(r"^\s*Channel Mode: ([A-Za-z ]+?) \("),
    "blocks": re.compile(r"^\s*Block Length: (\d+)"),
    "subbands": re.compile(r"^\s*Subbands: (\d+)"),
    "min_bitpool": re.compile(r"^\s*Minimum Bitpool: (\d+)"),
    "max_bitpool": re.compile(r"^\s*Maximum Bitpool: (\d+)"),
}


def sbc_frame_len(bitpool: int, mode: str = "Joint Stereo", subbands: int = 8, blocks: int = 16) -> int:
    channels = 1 if mode == "Mono" else 2
    fixed = 4 + (4 * subbands * channels) // 8
    if mode in ("Mono", "Dual Channel"):
        return fixed + math.ceil(blocks * channels * bitpool / 8)
    join = subbands if mode == "Joint Stereo" else 0
    return fixed + math.ceil((join + blocks * bitpool) / 8)


def sbc_bitrate(bitpool: int, freq: int = 44100, mode: str = "Joint Stereo",
                subbands: int = 8, blocks: int = 16) -> float:
    """Codec bit rate in bit/s (no transport overhead)."""
    return 8 * sbc_frame_len(bitpool, mode, subbands, blocks) * freq / (subbands * blocks)


def wire_Bps(bitpool: int, freq: int = 44100, mode: str = "Joint Stereo",
             subbands: int = 8, blocks: int = 16, mtu: int = DEFAULT_MTU) -> float:
    """Bytes/s on the HCI link incl. RTP, L2CAP, ACL and H4 headers."""
    flen = sbc_frame_len(bitpool, mode, subbands, blocks)
    frames_per_pkt = max(1, min(15, (mtu - RTP_SBC_HDR) // flen))
    pkt_per_s = freq / (subbands * blocks) / frames_per_pkt
    return pkt_per_s * (frames_per_pkt * flen + RTP_SBC_HDR + L2CAP_ACL_H4_HDR)


def max_bitpool_for(budget_kBps: float, headroom: float = DEFAULT_HEADROOM, freq: int = 44100,
                    mode: str = "Joint Stereo", mtu: int = DEFAULT_MTU) -> int | None:
    limit = budget_kBps * 1000 * headroom
    fits = [bp for bp in range(2, 251) if wire_Bps(bp, freq, mode, mtu=mtu) <= limit]
    return max(fits) if fits else None


def parse_btmon_setconf(text: str) -> list[dict]:
    """SBC configs from AVDTP Set Configuration / Reconfigure commands in btmon text."""
    out: list[dict] = []
    hci = direction = None
    cur: dict | None = None
    for line in text.splitlines():
        m = _HDR.match(line)
        if m:
            direction, hci = ("tx" if m.group(1) == "<" else "rx"), m.group(2)
            if cur is not None:
                out.append(cur)
                cur = None
            continue
        if "AVDTP: Set Configuration" in line or "AVDTP: Reconfigure" in line:
            if cur is not None:
                out.append(cur)
            cur = {"hci": hci, "direction": direction, "command": " Command " in line}
            continue
        if cur is None:
            continue
        for key, rx in _FIELDS.items():
            fm = rx.match(line)
            if fm:
                val = fm.group(1).strip()
                cur[key] = val if key == "mode" else int(val)
    if cur is not None:
        out.append(cur)
    return [c for c in out if "max_bitpool" in c and c["command"]]


def leg_report(cfg: dict, budget_kBps: float, mtu: int) -> dict:
    freq = cfg.get("freq", 44100)
    mode = cfg.get("mode", "Joint Stereo")
    sb = cfg.get("subbands", 8)
    bl = cfg.get("blocks", 16)
    bp = cfg["max_bitpool"]
    need = wire_Bps(bp, freq, mode, sb, bl, mtu) / 1000
    return {
        "hci": cfg.get("hci"),
        "direction": cfg.get("direction"),
        "freq": freq,
        "mode": mode,
        "max_bitpool": bp,
        "codec_kbps": round(sbc_bitrate(bp, freq, mode, sb, bl) / 1000, 1),
        "wire_kBps": round(need, 1),
        "budget_kBps": budget_kBps,
        "load": round(need / budget_kBps, 2),
        "fits_80pct": need <= budget_kBps * DEFAULT_HEADROOM,
        "suggest_bitpool": max_bitpool_for(budget_kBps, DEFAULT_HEADROOM, freq, mode, mtu),
    }


def print_table(budget_kBps: float, mtu: int) -> None:
    print(f"budget {budget_kBps} kB/s per ESP · 80 % = {budget_kBps * DEFAULT_HEADROOM:.1f} kB/s · MTU {mtu}")
    print(f"{'bitpool':>7} {'44.1k kbps':>10} {'44.1k kB/s':>10} {'48k kB/s':>9}")
    for bp in (64, 53, 45, 40, 35, 32, 30, 25):
        r44 = wire_Bps(bp, 44100, mtu=mtu) / 1000
        r48 = wire_Bps(bp, 48000, mtu=mtu) / 1000
        mark = "ok" if r44 <= budget_kBps * DEFAULT_HEADROOM else ("tight" if r44 <= budget_kBps else "over")
        print(f"{bp:>7} {sbc_bitrate(bp) / 1000:>10.0f} {r44:>10.1f} {r48:>9.1f}  {mark}")
    print(f"max bitpool @44.1k within 80 %: {max_bitpool_for(budget_kBps, mtu=mtu)}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--btmon", help="btmon text output")
    ap.add_argument("--btsnoop", help="btsnoop file (decoded with btmon -r)")
    ap.add_argument("--budget", type=float, default=DEFAULT_BUDGET_KBPS, help="kB/s per ESP")
    ap.add_argument("--mtu", type=int, default=DEFAULT_MTU)
    ap.add_argument("--table", action="store_true")
    args = ap.parse_args()

    if args.table or not (args.btmon or args.btsnoop):
        print_table(args.budget, args.mtu)
        if not (args.btmon or args.btsnoop):
            return 0
    if args.btsnoop:
        text = subprocess.run(["btmon", "-r", args.btsnoop], capture_output=True, text=True).stdout
    else:
        with open(args.btmon, encoding="utf-8", errors="replace") as fh:
            text = fh.read()
    configs = parse_btmon_setconf(text)
    if not configs:
        print("no AVDTP Set Configuration with SBC found", file=sys.stderr)
        return 1
    print(f"\n{'hci':<6} {'set by':<7} {'freq':>6} {'mode':<13} {'bitpool':>7} {'kbps':>6} {'kB/s':>6} {'load':>5}  verdict")
    for cfg in configs:
        r = leg_report(cfg, args.budget, args.mtu)
        verdict = "ok" if r["fits_80pct"] else f"over → bitpool ≤ {r['suggest_bitpool']}"
        set_by = {"tx": "Linux", "rx": "remote"}.get(r["direction"], "-")
        print(f"{r['hci'] or '-':<6} {set_by:<7} {r['freq']:>6} {r['mode']:<13} {r['max_bitpool']:>7} "
              f"{r['codec_kbps']:>6} {r['wire_kBps']:>6} {r['load']:>5}  {verdict}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
