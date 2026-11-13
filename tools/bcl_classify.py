#!/usr/bin/env python3
"""BCL epistemic classification for UIH/RFCOMM byte streams (passive).

Levels (do not upgrade without evidence):
  UNKNOWN                 — no magic, no valid frame
  BCL_CANDIDATE           — INIT_MAGIC 12 34 56 78 seen (or alone)
  STRONG_BCL_CANDIDATE    — ≥1 valid 8-byte BCL header (+ payload complete)
  BCL_FIELD_CONFIRMED     — HANDSHAKE (cmd=4, payload len=8) after valid framing

Epistemic: desk/lab/field — caller sets origin. Magic alone ≠ FACT.

  python3 tools/bcl_classify.py --hex 12345678
  python3 tools/bcl_classify.py --file capture.bin
  python3 -m unittest tests/host/test_bcl_classify.py
"""

from __future__ import annotations

import argparse
import json
import struct
import sys
from pathlib import Path

_TOOLS = Path(__file__).resolve().parent
if str(_TOOLS) not in sys.path:
    sys.path.insert(0, str(_TOOLS))

from bcl_framer import (  # noqa: E402
    CMD_NAMES,
    HEADER_SIZE,
    INIT_MAGIC,
    MAX_PAYLOAD,
    BclFramer,
    BclParseError,
    dest_desk_label,
)

CMD_HANDSHAKE = 4

LEVELS = (
    "UNKNOWN",
    "BCL_CANDIDATE",
    "STRONG_BCL_CANDIDATE",
    "BCL_FIELD_CONFIRMED",
)


def _rank(level: str) -> int:
    return LEVELS.index(level)


def _bump(cur: str, new: str) -> str:
    return new if _rank(new) > _rank(cur) else cur


def classify_bytes(data: bytes | bytearray | memoryview | None) -> dict:
    """Classify a raw byte stream (e.g. concatenated UIH payloads)."""
    data = bytes(data or b"")
    out: dict = {
        "bcl_classification": "UNKNOWN",
        "magic_count": 0,
        "magic_offsets": [],
        "frames": [],
        "handshake": None,
        "framer_error": None,
        "incomplete": False,
        "bytes_len": len(data),
        "payload_hex_head": data[:64].hex(),
    }

    off = 0
    while True:
        i = data.find(INIT_MAGIC, off)
        if i < 0:
            break
        out["magic_offsets"].append(i)
        off = i + 1
    out["magic_count"] = len(out["magic_offsets"])
    if out["magic_count"]:
        out["bcl_classification"] = _bump(out["bcl_classification"], "BCL_CANDIDATE")

    fr = BclFramer()
    res = fr.feed(data)
    out["incomplete"] = bool(res.incomplete)
    out["session_inits_at_boundary"] = res.session_inits
    if res.session_inits:
        out["bcl_classification"] = _bump(out["bcl_classification"], "BCL_CANDIDATE")

    if res.error:
        out["framer_error"] = {
            "code": int(res.error_code),
            "name": BclParseError(res.error_code).name,
            "detail": res.error_detail,
        }

    for f in res.frames:
        entry = f.as_dict()
        out["frames"].append(entry)
        if 0 <= f.length <= MAX_PAYLOAD and len(f.raw) == HEADER_SIZE + f.length:
            out["bcl_classification"] = _bump(
                out["bcl_classification"], "STRONG_BCL_CANDIDATE"
            )
        if f.cmd == CMD_HANDSHAKE and f.length == 8 and len(f.payload) == 8:
            version, instance_id, buffer_size = struct.unpack(">HHI", f.payload)
            out["handshake"] = {
                "version": version,
                "instance_id": instance_id,
                "buffer_size": buffer_size,
                "src": f.src,
                "dest": f.dest,
            }
            out["bcl_classification"] = _bump(
                out["bcl_classification"], "BCL_FIELD_CONFIRMED"
            )

    if not out["frames"] and len(data) >= HEADER_SIZE and not out["magic_count"]:
        length = (data[6] << 8) | data[7]
        cmd = (data[0] << 8) | data[1]
        if cmd in CMD_NAMES and length <= MAX_PAYLOAD:
            out["bcl_classification"] = _bump(
                out["bcl_classification"], "STRONG_BCL_CANDIDATE"
            )
            out["note"] = "plausible_header_prefix_no_complete_frame"

    return out


def evidence_envelope(
    *,
    classification: dict,
    session_id: str,
    source: str,
    origin: str,
    tx_allowed: bool,
    mode: str | None = None,
    extra: dict | None = None,
) -> dict:
    """Minimal evidence fields for field/lab JSON."""
    env = {
        "session_id": session_id,
        "source": source,
        "origin": origin,
        "epistemic_status": {
            "UNKNOWN": "observed",
            "BCL_CANDIDATE": "candidate",
            "STRONG_BCL_CANDIDATE": "candidate",
            "BCL_FIELD_CONFIRMED": "confirmed",
        }.get(classification.get("bcl_classification", "UNKNOWN"), "observed"),
        "tx_allowed": bool(tx_allowed),
        "bcl_tx_enabled": bool(tx_allowed),
        "mode": mode,
        "bcl_classification": classification.get("bcl_classification"),
        "classification": classification,
    }
    if extra:
        env.update(extra)
    return env


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--hex", help="hex payload (no spaces or with spaces)")
    g.add_argument("--file", type=Path, help="raw bytes file")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    if args.hex is not None:
        data = bytes.fromhex(args.hex.replace(" ", ""))
    else:
        data = args.file.read_bytes()
    result = classify_bytes(data)
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(result["bcl_classification"])
        if result["magic_count"]:
            print(f"magic_count={result['magic_count']} offsets={result['magic_offsets']}")
        for f in result["frames"]:
            label = dest_desk_label(f["dest"]) or ""
            print(
                f"  frame cmd={f['cmd_name']}({f['cmd']}) "
                f"src={f['src']} dest={f['dest']}{('/' + label) if label else ''} "
                f"len={f['len']}"
            )
        if result.get("handshake"):
            print(f"  handshake={result['handshake']}")
        if result.get("framer_error"):
            print(f"  framer_error={result['framer_error']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
