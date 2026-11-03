#!/usr/bin/env python3
"""Topology E_INJECT: pipeline smoke on OBSERVE_A (.88)."""

from __future__ import annotations

import json
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "docs" / "evidence"
DEFAULT_IP = "192.168.178.88"
HEX = "040e0401030c00"  # synthetic HCI Event-shaped bytes (not proof of controller)


def post_form(url: str, fields: dict[str, str], timeout: float = 5.0) -> tuple[int, str]:
    data = urllib.parse.urlencode(fields).encode()
    req = urllib.request.Request(url, data=data, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.status, resp.read().decode("utf-8", errors="replace")


def get_text(url: str, timeout: float = 5.0) -> str:
    with urllib.request.urlopen(url, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="replace")


def main() -> int:
    ip = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_IP
    now = datetime.now(timezone.utc)
    stamp = now.strftime("%Y%m%dT%H%M%SZ")

    status_before = json.loads(get_text(f"http://{ip}/api/status"))
    code, inj = post_form(f"http://{ip}/api/capture/inject", {"hex": HEX})
    drain = get_text(f"http://{ip}/api/capture/drain?n=8")
    status_after = json.loads(get_text(f"http://{ip}/api/status"))

    lines = [ln for ln in drain.strip().splitlines() if ln.strip()]
    ok = code == 200 and '"ok":true' in inj.replace(" ", "") and len(lines) >= 1

    doc = {
        "artifact": "LAB_BT_INJECT",
        "classification": "MEASURED",
        "topology_id": "E_INJECT",
        "utc": now.isoformat(),
        "node": ip,
        "fw_version": status_after.get("version"),
        "inject_http": code,
        "inject_body": inj,
        "drain_lines": lines,
        "capture_before": status_before.get("capture"),
        "capture_after": status_after.get("capture"),
        "hciCapture": status_after.get("hciCapture"),
        "pass": ok,
        "claim_boundary": {
            "in_scope": ["HTTP inject → ring → JSONL drain"],
            "out_of_scope": ["USB dongle", "HCI controller", "RF", "Bluetooth link"],
        },
    }

    EVIDENCE.mkdir(parents=True, exist_ok=True)
    path = EVIDENCE / f"LAB_BT_INJECT_{stamp}.json"
    path.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    md = EVIDENCE / f"LAB_BT_INJECT_{stamp}.md"
    md.write_text(
        f"# Lab BT inject smoke — MEASURED\n\n"
        f"**Date (UTC):** {stamp}\n"
        f"**Topology ID:** E_INJECT\n"
        f"**Firmware:** `{status_after.get('version')}` @ `{ip}`\n"
        f"**Raw:** [`{path.name}`]({path.name})\n"
        f"**Repro:** `python3 tools/lab_inject_smoke.py {ip}`\n\n"
        f"Classification: **MEASURED** (pipeline only).\n\n"
        f"## Claim boundary\n\n"
        f"| In scope | Out of scope |\n"
        f"|----------|----------------|\n"
        f"| inject→ring→drain | USB-HCI dongle, RF, controller |\n\n"
        f"## Result\n\n"
        f"- pass: **{ok}**\n"
        f"- drain lines: {len(lines)}\n"
        f"- capture: `{json.dumps(status_after.get('capture'))}`\n",
        encoding="utf-8",
    )
    print(f"wrote {path} pass={ok}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
