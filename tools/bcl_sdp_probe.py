#!/usr/bin/env python3
"""List RFCOMM data services (SPP, iAP2, vendor UUIDs) a BT device offers via SDP.

First step of the BCL-over-Bluetooth plan (docs/BCL_BT.md): does the BMW HU or
the phone with the Connected app offer an RFCOMM service that could carry BCL?
SDP needs no pairing, only an ACL link, so this works right after HCI_TCP A3/A6.
Runs where BlueZ owns the D1 controller (`.108`), uses `sdptool`, falls back to
`bluetoothctl info` (UUIDs only, no channels).

Usage:
  python3 tools/bcl_sdp_probe.py -i hci2 hu=AA:BB:CC:DD:EE:FF
  python3 tools/bcl_sdp_probe.py -i hci1 phone=11:22:33:44:55:66 --records --json /tmp/sdp.json
  python3 tools/bcl_sdp_probe.py --parse saved_sdptool_output.txt
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time

SPP_UUID16 = 0x1101
IAP2_UUID = "00000000-deca-fade-deca-deafdecacaff"
BT_BASE_SUFFIX = "-0000-1000-8000-00805f9b34fb"
NAME_HINT = re.compile(r"bmw|connected|bcl|etch|mobile office|mini", re.I)

_UUID16 = re.compile(r'(?:"([^"]*)"\s*)?\(0x([0-9a-fA-F]{4})\)')
_UUID128 = re.compile(r"UUID 128:\s*([0-9a-fA-F-]{36})")
_CTL_UUID = re.compile(r"UUID:\s*(.*?)\s*\(([0-9a-fA-F-]{36})\)")


def parse_sdptool(text: str) -> list[dict]:
    """Parse `sdptool browse|records` output into one dict per service record."""
    records: list[dict] = []
    cur: dict | None = None
    section = ""
    for raw in text.splitlines():
        line = raw.rstrip()
        if not line.strip():
            continue
        starts_new = cur is not None and (
            (line.startswith("Service Name:") and (cur["name"] or cur["handle"]))
            or (line.startswith("Service RecHandle:") and cur["handle"])
        )
        if starts_new:
            records.append(cur)
            cur = None
            section = ""
        if cur is None:
            cur = {"name": "", "handle": None, "classes": [], "protocols": [], "rfcomm": None}
        if line.startswith("Service Name:"):
            cur["name"] = line.split(":", 1)[1].strip()
        elif line.startswith("Service RecHandle:"):
            cur["handle"] = line.split(":", 1)[1].strip()
        elif line.endswith(":") and not line.startswith(" "):
            section = line[:-1]
        elif section in ("Service Class ID List", "Protocol Descriptor List"):
            target = cur["classes"] if section == "Service Class ID List" else cur["protocols"]
            m128 = _UUID128.search(line)
            m16 = _UUID16.search(line)
            chan = re.search(r"Channel:\s*(\d+)", line)
            if m128:
                target.append(m128.group(1).lower())
            elif m16:
                target.append(f"0x{m16.group(2).lower()}")
            elif chan and section == "Protocol Descriptor List":
                cur["rfcomm"] = int(chan.group(1))
    if cur is not None:
        records.append(cur)
    return [r for r in records if r["name"] or r["handle"] or r["classes"]]


def parse_bluetoothctl_info(text: str) -> list[dict]:
    """UUID lines of `bluetoothctl info` as pseudo records (no RFCOMM channel known)."""
    out = []
    for m in _CTL_UUID.finditer(text):
        uuid = m.group(2).lower()
        short = f"0x{uuid[4:8]}" if uuid.endswith(BT_BASE_SUFFIX) else uuid
        out.append({"name": m.group(1), "handle": None, "classes": [short], "protocols": [], "rfcomm": None})
    return out


def classify(rec: dict) -> list[str]:
    tags = []
    classes = rec["classes"]
    if f"0x{SPP_UUID16:04x}" in classes:
        tags.append("spp")
    if IAP2_UUID in classes:
        tags.append("iap2")
    if any(len(c) == 36 and c != IAP2_UUID and not c.endswith(BT_BASE_SUFFIX) for c in classes):
        tags.append("vendor128")
    if rec["rfcomm"] is not None:
        tags.append(f"rfcomm{rec['rfcomm']}")
    if NAME_HINT.search(rec["name"] or ""):
        tags.append("name_hint")
    return tags


def verdict(records: list[dict]) -> str:
    tagged = [classify(r) for r in records]
    data = [t for t in tagged if {"spp", "vendor128"} & set(t)]
    if any("name_hint" in t for t in data):
        return "CANDIDATE_STRONG: RFCOMM data service with BMW/Connected name"
    if data:
        return "CANDIDATE: RFCOMM data service present (SPP or vendor UUID)"
    if any("iap2" in t for t in tagged):
        return "IAP2_ONLY: Apple accessory path, no plain SPP"
    return "NONE: no RFCOMM data service in SDP (may appear only with app active)"


def run(cmd: list[str], timeout: float) -> str:
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return f"__error__ {exc}"
    return res.stdout + res.stderr


def probe(hci: str, addr: str, use_records: bool, timeout: float) -> tuple[str, list[dict], str]:
    mode = "records" if use_records else "browse"
    text = run(["sdptool", "-i", hci, mode, addr], timeout)
    recs = parse_sdptool(text) if not text.startswith("__error__") else []
    if recs:
        return f"sdptool {mode}", recs, text
    info = run(["bluetoothctl", "info", addr], timeout)
    return "bluetoothctl info", parse_bluetoothctl_info(info), text + "\n" + info


def report(label: str, source: str, recs: list[dict]) -> dict:
    print(f"\n== {label}  ({source}, {len(recs)} records)")
    for r in recs:
        tags = classify(r)
        mark = "*" if {"spp", "vendor128", "iap2"} & set(tags) else " "
        print(f" {mark} {r['name'] or '-':<28} {r['handle'] or '':<9} {','.join(r['classes'])}  [{' '.join(tags)}]")
    v = verdict(recs)
    print(f"   verdict: {v}")
    return {"label": label, "source": source, "verdict": v,
            "records": [dict(r, tags=classify(r)) for r in recs]}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("targets", nargs="*", help="label=BD_ADDR, e.g. hu=AA:BB:CC:DD:EE:FF")
    ap.add_argument("-i", "--hci", default="hci0", help="BlueZ controller of the D1 (hci1/hci2)")
    ap.add_argument("--records", action="store_true", help="probe all handles (finds non-browsable records)")
    ap.add_argument("--timeout", type=float, default=30.0)
    ap.add_argument("--json", help="write results to this file")
    ap.add_argument("--parse", help="parse a saved sdptool output file instead of probing")
    args = ap.parse_args()

    results = []
    if args.parse:
        with open(args.parse, encoding="utf-8", errors="replace") as fh:
            results.append(report(args.parse, "file", parse_sdptool(fh.read())))
    for target in args.targets:
        label, _, addr = target.rpartition("=")
        if not re.fullmatch(r"([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}", addr):
            print(f"bad target {target!r} (want label=AA:BB:CC:DD:EE:FF)", file=sys.stderr)
            return 2
        source, recs, raw = probe(args.hci, addr, args.records, args.timeout)
        entry = report(label or addr, source, recs)
        entry.update(addr=addr, hci=args.hci, raw=raw)
        results.append(entry)
    if not results:
        ap.print_help()
        return 2
    if args.json:
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump({"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "results": results}, fh, indent=2)
    return 0


if __name__ == "__main__":
    sys.exit(main())
