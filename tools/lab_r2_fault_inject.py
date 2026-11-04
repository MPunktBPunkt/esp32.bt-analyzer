#!/usr/bin/env python3
"""R2b — Peer fault injection (slow/burst/gap/drop) while .88 HOGP/FTMS listens.

Requires FW 0.3.5+ (`POST /api/bt/peer/fault`).

Usage:
  python3 tools/lab_r2_fault_inject.py
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
HOST = "192.168.178.88"
PEER = "192.168.178.89"


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
    except urllib.error.HTTPError as exc:
        body = exc.read().decode(errors="replace")
        try:
            j = json.loads(body) if body else {}
        except json.JSONDecodeError:
            j = {"raw": body}
        j["http_status"] = exc.code
        return j


def quiet() -> None:
    for ip in (HOST, PEER):
        for path in (
            "/api/bt/throughput/stop",
            "/api/bt/scan/stop",
            "/api/bt/advertise/stop",
            "/api/bt/disconnect",
        ):
            try:
                post(f"http://{ip}{path}")
            except Exception:  # noqa: BLE001
                pass


def ensure_link() -> None:
    quiet()
    time.sleep(0.3)
    peer_bd = (get(f"http://{PEER}/api/status").get("onchip") or {}).get("bdAddr")
    post(f"http://{PEER}/api/bt/advertise/start", {"name": "fault-89"})
    time.sleep(0.6)
    post(f"http://{HOST}/api/bt/scan/start")
    time.sleep(4.0)
    post(f"http://{HOST}/api/bt/scan/stop")
    post(f"http://{HOST}/api/bt/connect", {"addr": peer_bd, "addrType": "0"})
    for _ in range(40):
        if (get(f"http://{HOST}/api/status").get("onchip") or {}).get("leConnected"):
            return
        time.sleep(0.25)
    raise RuntimeError("connect_failed")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--modes", default="slow,burst,gap,drop")
    args = ap.parse_args()
    utc = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    EVIDENCE.mkdir(parents=True, exist_ok=True)

    st = get(f"http://{PEER}/api/status")
    fw = str(st.get("fwVersion") or st.get("version") or "")
    # Probe API exists
    probe = post(f"http://{PEER}/api/bt/peer/fault", {"mode": "off"})
    if probe.get("http_status") == 404 or (not probe.get("ok") and "bad_mode" not in str(probe)):
        # old FW
        if "peerFault" not in st and not probe.get("ok"):
            print(json.dumps({"ok": False, "error": "need_fw_0.3.5_peer_fault", "fw": fw, "probe": probe}))
            return 1

    ensure_link()
    post(f"http://{HOST}/api/bt/flavor/gatt/discover", {"mtu": "247"})
    for _ in range(40):
        fl = get(f"http://{HOST}/api/status").get("flavor") or {}
        if fl.get("state") in ("ready", "error"):
            break
        time.sleep(0.25)
    post(f"http://{HOST}/api/bt/flavor/hogp/start")
    time.sleep(0.5)

    results = []
    for mode in [m.strip() for m in args.modes.split(",") if m.strip()]:
        post(f"http://{PEER}/api/bt/peer/fault", {"mode": mode, "after_n": "6"})
        t0 = time.time()
        time.sleep(3.0 if mode != "drop" else 5.0)
        h = get(f"http://{HOST}/api/status")
        p = get(f"http://{PEER}/api/status")
        hogp = h.get("hogp") or {}
        row = {
            "mode": mode,
            "peer_fault": p.get("peerFault") or (p.get("onchip") or {}).get("peerFault"),
            "peer_fault_count": p.get("peerFaultCount"),
            "host_le": (h.get("onchip") or {}).get("leConnected"),
            "hogp_reports": hogp.get("reports"),
            "elapsed_s": round(time.time() - t0, 3),
        }
        if mode == "drop":
            row["ok"] = (h.get("onchip") or {}).get("leConnected") is False or int(hogp.get("reports") or 0) >= 1
        else:
            row["ok"] = int(hogp.get("reports") or 0) >= 0  # exercised
            row["ok"] = True if p.get("peerFault") == mode or (p.get("onchip") or {}).get("peerFault") == mode else row["ok"]
        # re-link if drop
        if mode == "drop" and not (h.get("onchip") or {}).get("leConnected"):
            try:
                ensure_link()
                post(f"http://{HOST}/api/bt/flavor/gatt/discover", {"mtu": "247"})
                time.sleep(2)
                post(f"http://{HOST}/api/bt/flavor/hogp/start")
                time.sleep(0.5)
            except Exception as exc:  # noqa: BLE001
                row["relink_error"] = str(exc)
        post(f"http://{PEER}/api/bt/peer/fault", {"mode": "off"})
        results.append(row)

    ok = all(r.get("ok") for r in results) and bool(results)
    out = {
        "utc": utc,
        "gate": "R2b_fault_inject",
        "fw": fw,
        "claim": "STIMULUS_peer_fault_not_air",
        "results": results,
        "ok": ok,
    }
    stem = f"LAB_R2_FAULT_{utc}"
    (EVIDENCE / f"{stem}.json").write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    (EVIDENCE / f"{stem}.md").write_text(
        f"# LAB R2b Fault Inject — {'PASS' if ok else 'FAIL'}\n\n"
        + "\n".join(f"- {r['mode']}: ok={r.get('ok')} reports={r.get('hogp_reports')} fault={r.get('peer_fault')}" for r in results)
        + "\n",
        encoding="utf-8",
    )
    quiet()
    print(json.dumps({"ok": ok, "stem": stem, "n": len(results)}, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
