#!/usr/bin/env python3
"""P0 — Dual Classic controller inventory (.87 car-side, .131 phone-side).

Classifies each node, checks Classic readiness, writes evidence.
Does NOT flash .131 (Heizung gate).

Usage:
  python3 tools/lab_dual_controller.py
  python3 tools/lab_dual_controller.py --flash-authorized   # only records intent; still no OTA
"""

from __future__ import annotations

import argparse
import json
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "docs" / "evidence"

NODES = {
    "car_side": {
        "ip": "192.168.178.87",
        "slot": "B",
        "role_target": "PROXY_CAR_SIDE",
        "expect_classic": True,
    },
    "phone_side": {
        "ip": "192.168.178.131",
        "slot": "A",
        "role_target": "PROXY_PHONE_SIDE",
        "expect_classic": True,
    },
}


def fetch(ip: str, path: str = "/api/status", timeout: float = 4.0) -> dict[str, Any]:
    url = f"http://{ip}{path}"
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            body = r.read().decode("utf-8", errors="replace")
            try:
                return {"ok": True, "http": r.status, "json": json.loads(body)}
            except json.JSONDecodeError:
                return {"ok": True, "http": r.status, "raw": body[:500]}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc)}


def classify(snap: dict[str, Any]) -> dict[str, Any]:
    if not snap.get("ok"):
        return {
            "class": "UNREACHABLE",
            "bt_analyzer": False,
            "classic_ready": False,
            "detail": snap.get("error"),
        }
    j = snap.get("json") or {}
    # Heizung / Metermaster shape
    if "value" in j and "unit" in j and "onchip" not in j and "version" not in j:
        return {
            "class": "HEIZUNG_METERMASTER",
            "bt_analyzer": False,
            "classic_ready": False,
            "detail": f"label={j.get('label')} unit={j.get('unit')} value={j.get('value')}",
            "flash_blocked": True,
        }
    oc = j.get("onchip") or {}
    if "onchip" in j or j.get("module") or (j.get("version") and oc):
        classic = bool(oc.get("classic"))
        ready = bool(oc.get("ready"))
        return {
            "class": "BT_ANALYZER",
            "bt_analyzer": True,
            "classic_ready": classic and ready,
            "version": j.get("version"),
            "chip": j.get("chip"),
            "mac": j.get("mac"),
            "bd_addr": oc.get("bdAddr"),
            "classic": classic,
            "ble": oc.get("ble"),
            "state": oc.get("state"),
            "sketch_used": j.get("sketchUsed"),
            "sketch_slot": j.get("sketch"),
            "flash_blocked": False,
        }
    return {
        "class": "UNKNOWN_HTTP",
        "bt_analyzer": False,
        "classic_ready": False,
        "detail": list(j.keys())[:12],
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--flash-authorized",
        action="store_true",
        help="record operator intent to flash .131 later (does not OTA)",
    )
    args = ap.parse_args()
    utc = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    EVIDENCE.mkdir(parents=True, exist_ok=True)

    slots: dict[str, Any] = {}
    for key, meta in NODES.items():
        snap = fetch(meta["ip"])
        cls = classify(snap)
        slots[key] = {**meta, "probe": snap, "classified": cls}

    car = slots["car_side"]["classified"]
    phone = slots["phone_side"]["classified"]

    checks = {
        "car_reachable": slots["car_side"]["probe"].get("ok") is True,
        "phone_reachable": slots["phone_side"]["probe"].get("ok") is True,
        "car_classic_ready": bool(car.get("classic_ready")),
        "phone_classic_ready": bool(phone.get("classic_ready")),
        "phone_is_heizung": phone.get("class") == "HEIZUNG_METERMASTER",
        "distinct_ips": NODES["car_side"]["ip"] != NODES["phone_side"]["ip"],
        "flash_131_authorized_flag": bool(args.flash_authorized),
        "flash_131_blocked": phone.get("class") == "HEIZUNG_METERMASTER"
        and not args.flash_authorized,
    }
    # P0 pass: both reachable, car Classic ready, phone classified, distinct, no silent overwrite
    p0_ok = (
        checks["car_reachable"]
        and checks["phone_reachable"]
        and checks["car_classic_ready"]
        and checks["distinct_ips"]
        and phone.get("class") in ("HEIZUNG_METERMASTER", "BT_ANALYZER", "UNKNOWN_HTTP")
    )
    dual_ready = checks["car_classic_ready"] and checks["phone_classic_ready"]

    out = {
        "utc": utc,
        "gate": "PROXY_P0_dual_controller",
        "claim": "inventory_network_hci_slots_not_proxy_yet",
        "hci_transport": "network_hci_wifi",
        "flash_131_authorized": bool(args.flash_authorized),
        "slots": slots,
        "checks": checks,
        "p0_inventory_ok": p0_ok,
        "dual_classic_ready": dual_ready,
        "next": (
            "flash .131 with ENV=analyzer-esp32 after Heizung vacated"
            if checks["phone_is_heizung"]
            else "both Classic — proceed P1 scaffolding"
        ),
        "docs": ["docs/PROXY.md", "docs/LAB_INVENTORY.md"],
    }

    stem = f"LAB_DUAL_CONTROLLER_{utc}"
    (EVIDENCE / f"{stem}.json").write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    md = [
        f"# LAB Dual Controller P0 — {'PASS' if p0_ok else 'FAIL'}",
        "",
        f"**UTC:** {utc}",
        f"**dual_classic_ready:** {dual_ready}",
        f"**hci_transport:** network_hci_wifi",
        f"**flash_131_authorized:** {args.flash_authorized}",
        "",
        "| Slot | IP | Class | Classic ready |",
        "|------|----|-------|---------------|",
        f"| A phone | {NODES['phone_side']['ip']} | `{phone.get('class')}` | {phone.get('classic_ready')} |",
        f"| B car | {NODES['car_side']['ip']} | `{car.get('class')}` | {car.get('classic_ready')} |",
        "",
        f"- car BD: `{car.get('bd_addr')}` · FW `{car.get('version')}`",
        f"- phone detail: {phone.get('detail') or phone.get('bd_addr') or '—'}",
        f"- next: {out['next']}",
        "",
        "OTA `.131` is **blocked** while class is `HEIZUNG_METERMASTER` unless operator auth.",
        "",
    ]
    (EVIDENCE / f"{stem}.md").write_text("\n".join(md), encoding="utf-8")
    print(
        json.dumps(
            {
                "ok": p0_ok,
                "dual_classic_ready": dual_ready,
                "stem": stem,
                "phone_class": phone.get("class"),
                "car_bd": car.get("bd_addr"),
                "next": out["next"],
            },
            indent=2,
        )
    )
    return 0 if p0_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
