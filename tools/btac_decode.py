#!/usr/bin/env python3
"""BT7 — decode BTAC capture file → JSONL (+ stats).

Usage:
  python3 tools/btac_decode.py capture.btac -o capture.jsonl
  python3 tools/btac_decode.py capture.btac --stats
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Allow running as script from repo root or tools/
sys.path.insert(0, str(Path(__file__).resolve().parent))
import btac  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description="BTAC v1 → JSONL decoder (BT7)")
    ap.add_argument("input", type=Path, help=".btac file")
    ap.add_argument("-o", "--output", type=Path, help="JSONL output (default: stdout)")
    ap.add_argument("--stats", action="store_true", help="print summary JSON to stderr/stdout")
    ap.add_argument("--strict", action="store_true", help="fail on CRC error")
    args = ap.parse_args()

    if not args.input.is_file():
        print(f"missing {args.input}", file=sys.stderr)
        return 2

    frames: list[dict] = []
    out_f = args.output.open("w", encoding="utf-8") if args.output else None
    try:
        for fr in btac.iter_file(str(args.input)):
            if args.strict and not fr.get("crc_ok", True):
                print(f"CRC fail seq={fr.get('seq')}", file=sys.stderr)
                return 1
            frames.append(fr)
            line = json.dumps(fr, ensure_ascii=False) + "\n"
            if out_f:
                out_f.write(line)
            elif not args.stats:
                sys.stdout.write(line)
    finally:
        if out_f:
            out_f.close()

    summary = btac.summarize(frames)
    summary["input"] = str(args.input)
    summary["output"] = str(args.output) if args.output else None
    summary["ok"] = summary["crc_fail"] == 0 and summary["frames"] > 0
    if args.stats:
        print(json.dumps(summary, indent=2))
    return 0 if summary["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
