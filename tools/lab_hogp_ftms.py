#!/usr/bin/env python3
"""BT18b/c — HOGP + FTMS Profile Flavors lab (STIMULUS).

Modes:
  peer stub (.89 advertise) — default
  foreign peer — --peer-addr BD_ADDR (no .89 required)

Usage:
  python3 tools/lab_hogp_ftms.py
  python3 tools/lab_hogp_ftms.py --peer-addr AA:BB:CC:DD:EE:FF --addr-type 1 --profiles hogp
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
DEFAULT_HOST = "192.168.178.88"
DEFAULT_PEER = "192.168.178.89"


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


def quiet(host: str, peer: str | None) -> None:
    ips = [host] + ([peer] if peer else [])
    for ip in ips:
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


def ensure_link_stub(host: str, peer: str) -> str:
    quiet(host, peer)
    time.sleep(0.4)
    peer_bd = (get(f"http://{peer}/api/status").get("onchip") or {}).get("bdAddr")
    if not peer_bd:
        raise RuntimeError("peer_bd_missing")
    post(f"http://{peer}/api/bt/advertise/start", {"name": "bt-peer-89"})
    time.sleep(0.8)
    post(f"http://{host}/api/bt/scan/start")
    time.sleep(4.0)
    post(f"http://{host}/api/bt/scan/stop")
    post(f"http://{host}/api/bt/connect", {"addr": peer_bd, "addrType": "0"})
    for _ in range(40):
        if (get(f"http://{host}/api/status").get("onchip") or {}).get("leConnected"):
            return str(peer_bd)
        time.sleep(0.25)
    raise RuntimeError("connect_failed")


def ensure_link_foreign(host: str, addr: str, addr_type: str) -> str:
    quiet(host, None)
    time.sleep(0.3)
    post(f"http://{host}/api/bt/scan/start")
    time.sleep(5.0)
    post(f"http://{host}/api/bt/scan/stop")
    post(f"http://{host}/api/bt/connect", {"addr": addr, "addrType": addr_type})
    for _ in range(50):
        if (get(f"http://{host}/api/status").get("onchip") or {}).get("leConnected"):
            return addr
        time.sleep(0.25)
    raise RuntimeError("connect_failed_foreign")


def wait_flavor_ready(host: str, timeout: float = 20.0) -> dict:
    t0 = time.time()
    while time.time() - t0 < timeout:
        fl = get(f"http://{host}/api/status").get("flavor") or {}
        if fl.get("state") in ("ready", "error"):
            return fl
        time.sleep(0.25)
    return get(f"http://{host}/api/status").get("flavor") or {}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--host", default=DEFAULT_HOST)
    ap.add_argument("--peer", default=DEFAULT_PEER, help="stub peer IP (ignored with --peer-addr)")
    ap.add_argument("--peer-addr", default="", help="foreign BD_ADDR; skips .89 advertise")
    ap.add_argument("--addr-type", default="1", help="0=public 1=random")
    ap.add_argument(
        "--profiles",
        default="both",
        choices=("hogp", "ftms", "both"),
        help="which flavor starts after GATT discover",
    )
    args = ap.parse_args()

    utc = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    foreign = bool(args.peer_addr.strip())
    if foreign:
        peer_bd = ensure_link_foreign(args.host, args.peer_addr.strip(), args.addr_type)
        peer_kind = "foreign"
        peer_ip = None
    else:
        peer_bd = ensure_link_stub(args.host, args.peer)
        peer_kind = "stub_89"
        peer_ip = args.peer

    post(f"http://{args.host}/api/bt/flavor/gatt/discover", {"mtu": "247"})
    fl = wait_flavor_ready(args.host, 20.0)
    svc_uuids = [str(s.get("uuid", "")).upper() for s in (fl.get("svc") or [])]
    has_hid = any(u.endswith("1812") for u in svc_uuids)
    has_ftms = any(u.endswith("1826") for u in svc_uuids)
    want_hogp = args.profiles in ("hogp", "both")
    want_ftms = args.profiles in ("ftms", "both")
    disc_ok = fl.get("state") == "ready"
    if want_hogp:
        disc_ok = disc_ok and has_hid
    if want_ftms:
        disc_ok = disc_ok and has_ftms

    hogp: dict = {}
    hogp_ok = not want_hogp
    if want_hogp:
        post(f"http://{args.host}/api/bt/flavor/hogp/start")
        for _ in range(40):
            time.sleep(0.25)
            st = get(f"http://{args.host}/api/status")
            hogp = st.get("hogp") or {}
            if hogp.get("state") in ("ready", "error") and int(hogp.get("reports") or 0) >= 1:
                break
        hogp_ok = hogp.get("state") == "ready" and int(hogp.get("reports") or 0) >= 1

    ftms: dict = {}
    ftms_ok = not want_ftms
    if want_ftms:
        post(f"http://{args.host}/api/bt/flavor/ftms/start")
        for _ in range(40):
            time.sleep(0.25)
            st = get(f"http://{args.host}/api/status")
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
        "fw": "0.3.2+",
        "claim": "STIMULUS_profile_flavors_over_HCI_not_air",
        "peer": {
            "kind": peer_kind,
            "bd_addr": peer_bd,
            "addr_type": args.addr_type if foreign else "0",
            "ip": peer_ip,
        },
        "profiles": args.profiles,
        "discover": {"ok": disc_ok, "flavor": fl, "has_hid": has_hid, "has_ftms": has_ftms},
        "hogp": {"ok": hogp_ok, "status": hogp, "skipped": not want_hogp},
        "ftms": {
            "ok": ftms_ok,
            "status": ftms,
            "skipped": not want_ftms,
            "note": "Success_neq_Wirkung",
        },
        "capability_ok": disc_ok,
        "benchmark_ok": disc_ok and hogp_ok and ftms_ok,
        "ok": disc_ok and hogp_ok and ftms_ok,
    }
    stem = f"LAB_BT18_PROFILES_{utc}"
    (EVIDENCE / f"{stem}.json").write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    md = [
        f"# LAB BT18 HOGP+FTMS — {'PASS' if out['ok'] else 'FAIL'}",
        "",
        f"**UTC:** {utc} · **peer:** {peer_kind} `{peer_bd}` · **profiles:** {args.profiles}",
        f"**Raw:** [`{stem}.json`]({stem}.json)",
        "",
        f"- discover: {disc_ok} (HID={has_hid} FTMS={has_ftms} services={fl.get('services')})",
        f"- HOGP: skipped={not want_hogp} ok={hogp_ok} reports={hogp.get('reports')} "
        f"state={hogp.get('state')} key={hogp.get('lastKey')}",
        f"- FTMS: skipped={not want_ftms} ok={ftms_ok} notifies={ftms.get('notifies')} "
        f"power={ftms.get('lastPower')} cadence={ftms.get('lastCadence')}",
        "",
        "Claims: STIMULUS only · Success≠Wirkung · foreign peer ≠ stub guarantees.",
        "",
    ]
    (EVIDENCE / f"{stem}.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    quiet(args.host, peer_ip)
    print(
        json.dumps(
            {
                "ok": out["ok"],
                "stem": stem,
                "peer_kind": peer_kind,
                "hogp_ok": hogp_ok,
                "ftms_ok": ftms_ok,
            },
            indent=2,
        )
    )
    return 0 if out["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
