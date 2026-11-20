#!/usr/bin/env python3
"""Observe-only SAS pad cross-check (CASE A Test A).

No private keys. Given cert serial_u32 + 16-byte challenge, prints:
  pad16 = MD5(serial_u32_be)
  xored = challenge XOR pad16
  digest = MD5(xored)

Usage:
  PYTHONPATH=tools python3 tools/sas_pad_crosscheck.py \\
    --serial-u32 2729 --challenge-hex 1111…(32 hex chars)

  # From B3/HU jsonl after enriched logging:
  PYTHONPATH=tools python3 tools/sas_pad_crosscheck.py --from-jsonl path/to/b3.jsonl
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from etch_codec import sas_challenge_transform  # noqa: E402


def from_jsonl(path: Path) -> int:
    serial = None
    challenge = None
    login_len = None
    for ln in path.read_text().splitlines():
        if not ln.startswith("{"):
            continue
        try:
            o = json.loads(ln)
        except json.JSONDecodeError:
            continue
        sas = o.get("sas") if isinstance(o.get("sas"), dict) else {}
        # B3 enriched etch events
        if o.get("method") == "sas_certificate" or sas.get("sas_method") == "sas_certificate":
            serial = sas.get("effective_serial_u32") or o.get("effective_serial_u32") or serial
        if o.get("method") == "_result_sas_certificate" or sas.get("sas_method") == "_result_sas_certificate":
            hx = sas.get("challenge_hex") or o.get("challenge_hex")
            if hx:
                challenge = bytes.fromhex(hx)
        # HU f20_sim events
        if o.get("event") == "sas_challenge_tx":
            serial = o.get("effective_serial_u32") or serial
            hx = o.get("challenge_hex")
            if hx:
                challenge = bytes.fromhex(hx)
        if o.get("event") == "sas_login_ok_tx" or o.get("method") == "sas_login":
            login_len = sas.get("login_sig_len") or o.get("sig_len") or o.get("login_sig_len") or login_len
    if serial is None or challenge is None:
        print(
            f"FAIL: need serial_u32 + challenge_hex in {path} "
            f"(found serial={serial} challenge={'yes' if challenge else 'no'})",
            file=sys.stderr,
        )
        return 1
    t = sas_challenge_transform(challenge, int(serial))
    print(json.dumps({**t, "login_sig_len": login_len, "source": str(path)}, indent=2))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--serial-u32", type=lambda x: int(x, 0))
    ap.add_argument("--challenge-hex")
    ap.add_argument("--from-jsonl", type=Path)
    args = ap.parse_args()
    if args.from_jsonl:
        return from_jsonl(args.from_jsonl)
    if args.serial_u32 is None or not args.challenge_hex:
        ap.error("need --serial-u32 + --challenge-hex, or --from-jsonl")
    t = sas_challenge_transform(bytes.fromhex(args.challenge_hex), args.serial_u32)
    print(json.dumps(t, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
