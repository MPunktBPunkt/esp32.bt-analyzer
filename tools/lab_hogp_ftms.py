#!/usr/bin/env python3
"""BT18b/c — HOGP + FTMS Profile Flavors lab (STIMULUS over peer stubs).

Flow: connect → GATT discover → HOGP start → wait reports → FTMS start → wait IBD.

Usage:
  python3 tools/lab_hogp_ftms.py
"""

from __future__ import annotations

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
    time.sleep(0.4)
    peer_bd = (get(f"http://{PEER}/api/status").get("onchip") or {}).get("bdAddr")
    post(f"http://{PEER}/api/bt/advertise/start", {"name": "bt-peer-89"})
    time.sleep(0.8)
    post(f"http://{HOST}/api/bt/scan/start")
    time.sleep(4.0)
    post(f"http://{HOST}/api/bt/scan/stop")
    post(f"http://{HOST}/api/bt/connect", {"addr": peer_bd, "addrType": "0"})
    for _ in range(40):
        if (get(f"http://{HOST}/api/status").get("onchip") or {}).get("leConnected"):
            return
        time.sleep(0.25)
    raise RuntimeError("connect_failed")


def wait_flavor_ready(timeout: float = 20.0) -> dict:
    t0 = time.time()
    while time.time() - t0 < timeout:
        fl = get(f"http://{HOST}/api/status").get("flavor") or {}
        if fl.get("state") in ("ready", "error"):
            return fl
        time.sleep(0.25)
    return get(f"http://{HOST}/api/status").get("flavor") or {}


def main() -> int:
    utc = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    ensure_link()

    post(f"http://{HOST}/api/bt/flavor/gatt/discover", {"mtu": "247"})
    fl = wait_flavor_ready(20.0)
    svc_uuids = [str(s.get("uuid", "")).upper() for s in (fl.get("svc") or [])]
    has_hid = any(u.endswith("1812") for u in svc_uuids)
    has_ftms = any(u.endswith("1826") for u in svc_uuids)
    disc_ok = fl.get("state") == "ready" and has_hid and has_ftms

    post(f"http://{HOST}/api/bt/flavor/hogp/start")
    hogp = {}
    for _ in range(40):
        time.sleep(0.25)
        st = get(f"http://{HOST}/api/status")
        hogp = st.get("hogp") or {}
        if hogp.get("state") in ("ready", "error") and int(hogp.get("reports") or 0) >= 1:
            break
        if hogp.get("state") == "ready" and int(hogp.get("reports") or 0) == 0:
            continue
    hogp_ok = hogp.get("state") == "ready" and int(hogp.get("reports") or 0) >= 1

    post(f"http://{HOST}/api/bt/flavor/ftms/start")
    ftms = {}
    for _ in range(40):
        time.sleep(0.25)
        st = get(f"http://{HOST}/api/status")
        ftms = st.get("ftms") or {}
        if ftms.get("state") in ("ready", "error") and int(ftms.get("notifies") or 0) >= 1:
            break
    ftms_ok = (
        ftms.get("state") == "ready"
        and int(ftms.get("notifies") or 0) >= 1
        and int(ftms.get("lastPower") or 0) > 0
    )

    out = {
        "utc": utc,
        "topology": "F_ONCHIP",
        "gate": "BT18bc",
        "fw": "0.3.2",
        "claim": "STIMULUS_profile_flavors_over_HCI_not_air",
        "discover": {"ok": disc_ok, "flavor": fl, "has_hid": has_hid, "has_ftms": has_ftms},
        "hogp": {"ok": hogp_ok, "status": hogp},
        "ftms": {"ok": ftms_ok, "status": ftms, "note": "Success_neq_Wirkung"},
        "capability_ok": disc_ok,
        "benchmark_ok": disc_ok and hogp_ok and ftms_ok,
        "ok": disc_ok and hogp_ok and ftms_ok,
    }
    stem = f"LAB_BT18_PROFILES_{utc}"
    (EVIDENCE / f"{stem}.json").write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    md = [
        f"# LAB BT18 HOGP+FTMS — {'PASS' if out['ok'] else 'FAIL'}",
        "",
        f"**UTC:** {utc} · **fw:** 0.3.2",
        f"**Raw:** [`{stem}.json`]({stem}.json)",
        "",
        f"- discover HID+FTMS: {disc_ok} (services={fl.get('services')})",
        f"- HOGP reports: {hogp.get('reports')} state={hogp.get('state')} key={hogp.get('lastKey')}",
        f"- FTMS notifies: {ftms.get('notifies')} power={ftms.get('lastPower')} "
        f"cadence={ftms.get('lastCadence')}",
        "",
        "Claims: STIMULUS only · peer stubs ≠ real keyboard/ergometer · Success≠Wirkung.",
        "",
    ]
    (EVIDENCE / f"{stem}.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    quiet()
    print(json.dumps({"ok": out["ok"], "stem": stem, "hogp_ok": hogp_ok, "ftms_ok": ftms_ok}, indent=2))
    return 0 if out["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
