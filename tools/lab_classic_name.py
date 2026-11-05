#!/usr/bin/env python3
"""0.3.14 — Classic inquiry → Remote Name / EIR on .87.

Done when: known headset (default HD 4.40) appears in /api/bt/devices with a
non-empty name after inquiry completes.

Usage:
  python3 tools/lab_classic_name.py
  python3 tools/lab_classic_name.py --expect-addr c4:xx:… --expect-name "HD 4.40"
"""

from __future__ import annotations

import argparse
import json
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "docs" / "evidence"
IP87 = "192.168.178.87"


def get(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=8) as r:
        return json.loads(r.read().decode())


def post(url: str, fields: dict | None = None) -> dict:
    data = urllib.parse.urlencode(fields or {}).encode()
    req = urllib.request.Request(url, data=data, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=8) as r:
            body = r.read().decode()
            try:
                return json.loads(body) if body else {}
            except json.JSONDecodeError:
                return {"raw": body}
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc)}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--esp", default=IP87)
    ap.add_argument("--inquiry-s", type=float, default=12.0)
    ap.add_argument("--settle-s", type=float, default=4.0, help="wait for Remote Name after inquiry")
    ap.add_argument("--expect-addr", default="", help="BD_ADDR substring/exact (optional)")
    ap.add_argument("--expect-name", default="HD 4.40", help="name substring; empty = any named classic")
    args = ap.parse_args()

    utc = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    EVIDENCE.mkdir(parents=True, exist_ok=True)

    st0 = get(f"http://{args.esp}/api/status")
    oc0 = st0.get("onchip") or {}
    if not oc0.get("classic"):
        print(json.dumps({"ok": False, "error": "no_classic", "status": oc0}, indent=2))
        return 1

    post(f"http://{args.esp}/api/bt/inquiry/stop")
    time.sleep(0.3)
    start = post(f"http://{args.esp}/api/bt/inquiry/start")
    time.sleep(args.inquiry_s)
    post(f"http://{args.esp}/api/bt/inquiry/stop")
    time.sleep(args.settle_s)

    dj = get(f"http://{args.esp}/api/bt/devices")
    devices = dj.get("devices") or []
    classic = [d for d in devices if d.get("classic")]
    named = [d for d in classic if (d.get("name") or "").strip()]

    expect_addr = (args.expect_addr or "").lower().replace("-", ":")
    expect_name = (args.expect_name or "").lower()

    hit = None
    for d in classic:
        addr = (d.get("addr") or "").lower()
        name = (d.get("name") or "")
        if expect_addr and expect_addr not in addr:
            continue
        if expect_name and expect_name not in name.lower():
            continue
        if not expect_name and not name.strip():
            continue
        hit = d
        break

    # Fallback: any named classic when no expect-name filter required beyond empty
    if hit is None and not expect_addr and not expect_name and named:
        hit = named[0]

    ok = hit is not None and bool((hit.get("name") or "").strip())
    out = {
        "utc": utc,
        "gate": "classic_remote_name",
        "fw": st0.get("version"),
        "esp": args.esp,
        "inquiry_s": args.inquiry_s,
        "settle_s": args.settle_s,
        "start": start,
        "devices_n": len(devices),
        "classic_n": len(classic),
        "named_n": len(named),
        "expect_addr": args.expect_addr,
        "expect_name": args.expect_name,
        "hit": hit,
        "devices": devices,
        "ok": ok,
        "claim": "inquiry_plus_remote_name_or_eir_fills_devices_name",
    }
    stem = f"LAB_CLASSIC_NAME_{utc}"
    (EVIDENCE / f"{stem}.json").write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    (EVIDENCE / f"{stem}.md").write_text(
        f"# LAB Classic Remote Name — {'PASS' if ok else 'FAIL'}\n\n"
        f"**UTC:** {utc} · FW `{st0.get('version')}` · `.87` inquiry\n\n"
        f"- classic devices: {len(classic)} · named: {len(named)}\n"
        f"- hit: `{json.dumps(hit, ensure_ascii=False) if hit else 'none'}`\n"
        f"- expect name≈`{args.expect_name}` addr≈`{args.expect_addr or 'any'}`\n",
        encoding="utf-8",
    )
    print(json.dumps({"ok": ok, "stem": stem, "hit": hit, "named_n": len(named)}, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
