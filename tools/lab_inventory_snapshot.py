#!/usr/bin/env python3
"""Snapshot lab nodes .87/.88/.89 into docs/evidence/LAB_INVENTORY_<UTC>.json."""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "docs" / "evidence"

NODES = [
    {"ip": "192.168.178.87", "role_hint": "REF_ENDPOINT", "board_hint": "D1 Mini ESP32"},
    {"ip": "192.168.178.88", "role_hint": "OBSERVE_A", "board_hint": "YD-ESP32-S3 N8R2"},
    {"ip": "192.168.178.89", "role_hint": "OBSERVE_B_OR_STIMULUS", "board_hint": "YD-ESP32-S3 N8R2"},
]


def fetch_status(ip: str, timeout: float = 3.0) -> dict:
    url = f"http://{ip}/api/status"
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            return {"ok": True, "http": resp.status, "status": json.loads(body)}
    except Exception as exc:  # noqa: BLE001 — lab tool
        return {"ok": False, "http": None, "error": str(exc)}


def fetch_usb(ip: str, timeout: float = 3.0) -> dict | None:
    url = f"http://{ip}/api/usb/status"
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8", errors="replace"))
    except Exception:
        return None


def main() -> int:
    now = datetime.now(timezone.utc)
    stamp = now.strftime("%Y%m%dT%H%M%SZ")
    nodes_out = []
    for n in NODES:
        st = fetch_status(n["ip"])
        entry = {
            **n,
            "reachable": st["ok"],
            "status": st.get("status"),
            "error": st.get("error"),
        }
        if st["ok"]:
            entry["usb"] = fetch_usb(n["ip"])
        nodes_out.append(entry)

    doc = {
        "artifact": "LAB_INVENTORY",
        "classification": "MEASURED",
        "topology_note": "inventory only — not a capture campaign",
        "utc": now.isoformat(),
        "nodes": nodes_out,
        "claim_boundary": {
            "in_scope": ["HTTP /api/status reachability", "reported FW version/chip"],
            "out_of_scope": ["HCI capture", "RF", "dongle identity unless present in usb.dut"],
        },
    }

    EVIDENCE.mkdir(parents=True, exist_ok=True)
    path = EVIDENCE / f"LAB_INVENTORY_{stamp}.json"
    path.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    latest = EVIDENCE / "LAB_INVENTORY_LATEST.json"
    latest.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")

    print(f"wrote {path}")
    for n in nodes_out:
        st = n.get("status") or {}
        print(
            f"  {n['ip']} ok={n['reachable']} "
            f"name={st.get('name')} ver={st.get('version')} chip={st.get('chip')}"
        )
    return 0 if all(n["reachable"] for n in nodes_out) else 2


if __name__ == "__main__":
    sys.exit(main())
