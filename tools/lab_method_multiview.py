#!/usr/bin/env python3
"""Method G — Multi-view LE visibility (ESP triangulation).

Each lab node advertises in turn; the others scan. Builds a who-sees-whom matrix
with RSSI. Topology: G_MULTIVIEW. Claim: LE adv visibility between lab radios
(HCI onchip) — not RF/Air PHY sniffer, not host BlueZ.

Usage:
  python3 tools/lab_method_multiview.py
  python3 tools/lab_method_multiview.py --scan-s 6
"""

from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "docs" / "evidence"

NODES = {
    "88": "192.168.178.88",
    "89": "192.168.178.89",
    "87": "192.168.178.87",
}


def get(url: str, timeout: float = 6.0) -> dict:
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return json.loads(r.read().decode())


def post(url: str, fields: dict | None = None, timeout: float = 6.0) -> dict:
    data = urllib.parse.urlencode(fields or {}).encode()
    req = urllib.request.Request(url, data=data, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = r.read().decode()
            try:
                return json.loads(body) if body else {"ok": True}
            except json.JSONDecodeError:
                return {"raw": body}
    except urllib.error.HTTPError as exc:
        return {"http_status": exc.code, "raw": exc.read().decode(errors="replace")}


def quiet_all() -> None:
    for ip in NODES.values():
        for path in (
            "/api/bt/throughput/stop",
            "/api/bt/scan/stop",
            "/api/bt/advertise/stop",
            "/api/bt/inquiry/stop",
            "/api/bt/disconnect",
        ):
            try:
                post(f"http://{ip}{path}")
            except Exception:  # noqa: BLE001
                pass


def node_meta() -> dict[str, dict]:
    out = {}
    for name, ip in NODES.items():
        st = get(f"http://{ip}/api/status")
        oc = st.get("onchip") or {}
        out[name] = {
            "ip": ip,
            "bd_addr": oc.get("bdAddr"),
            "ble": bool(oc.get("ble")),
            "classic": bool(oc.get("classic")),
            "ready": bool(oc.get("ready")),
            "fw": st.get("fwVersion") or st.get("version") or st.get("fw"),
        }
    return out


def find_device(devices: list, bd: str) -> dict | None:
    want = (bd or "").lower()
    for d in devices or []:
        if str(d.get("addr") or "").lower() == want:
            return d
    return None


def round_advertise(adv_name: str, adv_ip: str, scanners: list[str], scan_s: float) -> dict:
    post(f"http://{adv_ip}/api/bt/advertise/start", {"name": f"mv-{adv_name}"})
    time.sleep(0.5)
    for sc in scanners:
        post(f"http://{NODES[sc]}/api/bt/scan/start")
    time.sleep(scan_s)
    views = {}
    for sc in scanners:
        ip = NODES[sc]
        post(f"http://{ip}/api/bt/scan/stop")
        try:
            body = get(f"http://{ip}/api/bt/devices")
            devices = body.get("devices") if isinstance(body, dict) else []
        except Exception as exc:  # noqa: BLE001
            views[sc] = {"ok": False, "error": str(exc)}
            continue
        # also status.onchip sometimes mirrors count
        views[sc] = {
            "ok": True,
            "n_devices": len(devices or []),
            "devices": devices or [],
        }
    post(f"http://{adv_ip}/api/bt/advertise/stop")
    time.sleep(0.3)
    return views


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--scan-s", type=float, default=6.0)
    args = ap.parse_args()
    utc = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    EVIDENCE.mkdir(parents=True, exist_ok=True)

    quiet_all()
    time.sleep(0.4)
    meta = node_meta()

    matrix: dict[str, dict[str, dict]] = {}
    rounds = []
    for adv in NODES:
        if not meta[adv].get("ready") or not meta[adv].get("bd_addr"):
            rounds.append({"advertiser": adv, "ok": False, "error": "not_ready"})
            continue
        scanners = [n for n in NODES if n != adv and meta[n].get("ready")]
        quiet_all()
        time.sleep(0.3)
        views = round_advertise(adv, NODES[adv], scanners, args.scan_s)
        adv_bd = meta[adv]["bd_addr"]
        row = {}
        for sc, view in views.items():
            hit = find_device(view.get("devices") or [], adv_bd) if view.get("ok") else None
            cell = {
                "seen": hit is not None,
                "rssi": (hit or {}).get("rssi"),
                "name": (hit or {}).get("name"),
                "n_devices": view.get("n_devices"),
                "error": view.get("error"),
            }
            row[sc] = cell
            matrix.setdefault(sc, {})[adv] = cell
        rounds.append(
            {
                "advertiser": adv,
                "adv_bd": adv_bd,
                "ok": True,
                "views": {k: {"seen": v["seen"], "rssi": v["rssi"]} for k, v in row.items()},
            }
        )

    # expected directed edges: every ready pair (scanner, advertiser) with scanner!=adv
    expected = 0
    seen_n = 0
    missing = []
    for sc, row in matrix.items():
        for adv, cell in row.items():
            expected += 1
            if cell.get("seen"):
                seen_n += 1
            else:
                missing.append(f"{sc}↛{adv}")

    ok = expected > 0 and seen_n == expected and all(m.get("ready") for m in meta.values())
    out = {
        "utc": utc,
        "topology": "G_MULTIVIEW",
        "gate": "BT9_multiview",
        "method": "G_LE_multiview",
        "claim": "LE_adv_visibility_between_lab_radios_HCI_not_air_phy",
        "fw_field": "0.3.2",
        "scan_s": args.scan_s,
        "nodes": meta,
        "rounds": rounds,
        "matrix": matrix,
        "summary": {
            "edges_expected": expected,
            "edges_seen": seen_n,
            "missing": missing,
        },
        "ok": ok,
    }
    stem = f"LAB_METHOD_G_MULTIVIEW_{utc}"
    (EVIDENCE / f"{stem}.json").write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")

    lines = [
        f"# LAB Method G Multiview — {'PASS' if ok else 'FAIL'}",
        "",
        f"**UTC:** {utc} · **topology:** G_MULTIVIEW · **scan_s:** {args.scan_s}",
        f"**Raw:** [`{stem}.json`]({stem}.json)",
        "",
        f"Edges seen: **{seen_n}/{expected}**" + (f" · missing: {', '.join(missing)}" if missing else ""),
        "",
        "| scanner＼adv | " + " | ".join(NODES) + " |",
        "|---|" + "|".join(["---"] * len(NODES)) + "|",
    ]
    for sc in NODES:
        cells = []
        for adv in NODES:
            if sc == adv:
                cells.append("—")
                continue
            cell = (matrix.get(sc) or {}).get(adv) or {}
            if cell.get("seen"):
                cells.append(f"✓ {cell.get('rssi')}")
            else:
                cells.append("✗")
        lines.append(f"| {sc} | " + " | ".join(cells) + " |")
    lines += [
        "",
        "### Classification",
        "",
        "| Claim | Status |",
        "|-------|--------|",
        "| LE adv visibility lab↔lab | MEASURED |" if ok else "| LE adv visibility lab↔lab | FAIL |",
        "| RF/Air PHY sniffer | REJECTED |",
        "| Host BlueZ oracle | UNKNOWN (see Method H) |",
        "",
        "### NEXT TEST",
        "- Method H host oracle when AF_BLUETOOTH available",
        "- Method D classic+BLE mix on `.87`",
        "",
    ]
    (EVIDENCE / f"{stem}.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    quiet_all()
    print(json.dumps({"ok": ok, "stem": stem, "summary": out["summary"]}, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
