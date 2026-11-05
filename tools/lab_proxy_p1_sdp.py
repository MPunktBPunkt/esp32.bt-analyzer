#!/usr/bin/env python3
"""PROXY P1.0 — Dual BTAC capture + Classic visibility/SDP inventory.

Starts Network-HCI BTAC on .131 (phone-side) and .87 (car-side), makes both
Classic discoverable, lets Proxmox BlueZ scan/inventory UUIDs, writes evidence.

Does NOT implement AVRCP bridge yet — measures dual-radio capture + discovery.

Usage:
  python3 tools/lab_proxy_p1_sdp.py
  python3 tools/lab_proxy_p1_sdp.py --scan-s 14 --capture-s 8
"""

from __future__ import annotations

import argparse
import json
import re
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "docs" / "evidence"
CTRL = "http://127.0.0.1:8081"

INTEREST = {
    "1101": "Serial Port (SPP)",
    "110a": "Audio Source (A2DP)",
    "110b": "Audio Sink (A2DP)",
    "110c": "AVRCP Target",
    "110e": "AVRCP",
    "110f": "AVRCP Controller",
    "111e": "HFP HF",
    "111f": "HFP AG",
    "1124": "HID",
    "1200": "PnP Information",
}

SIDES = {
    "phone_side": {"ip": "192.168.178.131", "name": "proxy-phone-131"},
    "car_side": {"ip": "192.168.178.87", "name": "proxy-car-87"},
}


def get(url: str, timeout: float = 6.0) -> dict:
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return json.loads(r.read().decode())


def post(url: str, fields: dict | None = None, timeout: float = 8.0) -> dict:
    data = json.dumps(fields or {}).encode()
    req = urllib.request.Request(
        url, data=data, method="POST", headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = r.read().decode()
            try:
                return json.loads(body) if body else {}
            except json.JSONDecodeError:
                return {"raw": body}
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc)}


def post_form(url: str, fields: dict | None = None) -> dict:
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


def load_ssh():
    import importlib.util

    spec = importlib.util.spec_from_file_location("lab_bt_host_ssh", ROOT / "tools" / "lab_bt_host_ssh.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def extract_interest(text: str) -> dict:
    found = {}
    low = (text or "").lower()
    for u, name in INTEREST.items():
        if u in low:
            found[u] = name
    return found


def node_bd(ip: str) -> str:
    st = get(f"http://{ip}/api/status")
    return ((st.get("onchip") or {}).get("bdAddr") or "").lower()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--scan-s", type=float, default=12.0)
    ap.add_argument("--capture-s", type=float, default=6.0, help="BTAC settle while discoverable")
    ap.add_argument("--ctrl", default=CTRL)
    args = ap.parse_args()
    utc = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    EVIDENCE.mkdir(parents=True, exist_ok=True)

    ctrl_health = get(f"{args.ctrl}/api/v1/health")
    proxy_ctl = get(f"{args.ctrl}/api/v1/proxy/controllers")
    if not proxy_ctl.get("dual_classic_ready"):
        print(json.dumps({"ok": False, "error": "dual_classic_not_ready", "proxy": proxy_ctl}, indent=2))
        return 1

    bds = {side: node_bd(meta["ip"]) for side, meta in SIDES.items()}

    # Dual BTAC
    post(f"{args.ctrl}/api/v1/proxy/session/stop")
    time.sleep(0.3)
    sess_start = post(f"{args.ctrl}/api/v1/proxy/session/start", {})
    time.sleep(0.5)

    # Discoverable both Classic radios
    disco = {}
    for side, meta in SIDES.items():
        disco[side] = post_form(
            f"http://{meta['ip']}/api/bt/discoverable/start",
            {"name": meta["name"]},
        )

    time.sleep(args.capture_s)

    ssh = load_ssh()
    show = ssh.show()
    scan = ssh.scan(args.scan_s)
    addrs = [a.lower() for a in (scan.get("addrs") or [])]

    seen = {}
    for side, bd in bds.items():
        hit = bd in addrs if bd else False
        info = ssh.info(bd) if hit and bd else {}
        raw = (info.get("raw") or "") + " " + " ".join(info.get("uuids") or [])
        seen[side] = {
            "bd": bd,
            "seen_by_bluez": hit,
            "name": info.get("name") or info.get("alias"),
            "uuids_interest": extract_interest(raw),
            "paired": info.get("paired"),
            "connected": info.get("connected"),
        }

    # Stop discoverable
    for side, meta in SIDES.items():
        post_form(f"http://{meta['ip']}/api/bt/discoverable/stop")

    time.sleep(0.5)
    proxy_st = get(f"{args.ctrl}/api/v1/proxy/session")
    frames = {
        "phone_side": get(f"{args.ctrl}/api/v1/proxy/session/frames?side=phone&n=8"),
        "car_side": get(f"{args.ctrl}/api/v1/proxy/session/frames?side=car&n=8"),
    }
    sess_stop = post(f"{args.ctrl}/api/v1/proxy/session/stop")

    phone_ok = bool(seen["phone_side"]["seen_by_bluez"])
    car_ok = bool(seen["car_side"]["seen_by_bluez"])
    dual_cap = bool((proxy_st.get("proxy") or {}).get("dual_active") or sess_start.get("ok"))
    # Capture evidence: each side got some BTAC frames during discoverable window
    phone_fr = int(((proxy_st.get("proxy") or {}).get("phone_side") or {}).get("frames") or 0)
    car_fr = int(((proxy_st.get("proxy") or {}).get("car_side") or {}).get("frames") or 0)
    # After stop, use stop payload
    phone_fr = max(phone_fr, int(((sess_stop.get("phone_side") or {}).get("session") or {}).get("frames") or 0))
    car_fr = max(car_fr, int(((sess_stop.get("car_side") or {}).get("session") or {}).get("frames") or 0))

    ok_capture = phone_fr > 0 and car_fr > 0 and bool(sess_start.get("ok"))
    ok_visibility_both = phone_ok and car_ok
    # Infra PASS: dual BTAC + at least one Classic radio visible to BlueZ.
    # Full PASS: both radios visible (may need .131 closer — WiFi RSSI often weaker).
    ok_infra = ok_capture and (phone_ok or car_ok)
    ok = ok_infra
    wifi_rssi = {}
    for side, meta in SIDES.items():
        try:
            wifi_rssi[side] = get(f"http://{meta['ip']}/api/status").get("rssi")
        except Exception:  # noqa: BLE001
            wifi_rssi[side] = None
    out = {
        "utc": utc,
        "gate": "PROXY_P1_0_dual_capture_sdp",
        "claim": "dual_btac_network_hci_plus_bluez_visibility_observe_not_avrcp_bridge",
        "ctrl_version": ctrl_health.get("version"),
        "hci_transport": "network_hci_wifi",
        "bds": bds,
        "discoverable": disco,
        "session_start": {k: sess_start.get(k) for k in ("ok", "phone_side", "car_side")},
        "bluez_show_ok": bool(show.get("ok")),
        "scan_n": len(addrs),
        "seen": seen,
        "wifi_rssi": wifi_rssi,
        "btac_frames": {"phone_side": phone_fr, "car_side": car_fr},
        "proxy_session_final": sess_stop,
        "sample_frames": {
            "phone_n": len((frames["phone_side"].get("frames") or [])),
            "car_n": len((frames["car_side"].get("frames") or [])),
        },
        "ok_capture": ok_capture,
        "ok_visibility_both": ok_visibility_both,
        "ok_infra": ok_infra,
        "ok": ok,
        "note": (
            "Thin VHCI has no Classic SDP service records yet — UUID interest may be empty. "
            "Infra PASS = dual BTAC + ≥1 BlueZ sighting. Full dual visibility may need .131 RF placement."
        ),
    }

    stem = f"LAB_PROXY_P1_SDP_{utc}"
    (EVIDENCE / f"{stem}.json").write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    label = "PASS" if ok else "FAIL"
    if ok and not ok_visibility_both:
        label = "PASS_INFRA"
    (EVIDENCE / f"{stem}.md").write_text(
        f"# LAB PROXY P1.0 Dual Capture/SDP — {label}\n\n"
        f"**UTC:** {utc} · ctrl `{ctrl_health.get('version')}` · FW nodes 0.3.15+\n\n"
        f"| Side | BD | BlueZ seen | BTAC frames | WiFi RSSI | UUIDs |\n"
        f"|------|----|------------|-------------|-----------|-------|\n"
        f"| phone `.131` | `{bds['phone_side']}` | {phone_ok} | {phone_fr} | "
        f"{wifi_rssi.get('phone_side')} | `{list(seen['phone_side']['uuids_interest'])}` |\n"
        f"| car `.87` | `{bds['car_side']}` | {car_ok} | {car_fr} | "
        f"{wifi_rssi.get('car_side')} | `{list(seen['car_side']['uuids_interest'])}` |\n\n"
        f"- ok_capture={ok_capture} · ok_visibility_both={ok_visibility_both} · ok_infra={ok_infra}\n"
        f"- claim: dual BTAC Network HCI · **not** AVRCP bridge yet\n"
        f"- if phone not seen: move `.131` closer to Proxmox BT (WiFi RSSI often correlates)\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "ok": ok,
                "label": label,
                "ok_capture": ok_capture,
                "ok_visibility_both": ok_visibility_both,
                "stem": stem,
                "phone_seen": phone_ok,
                "car_seen": car_ok,
                "btac_frames": out["btac_frames"],
                "wifi_rssi": wifi_rssi,
            },
            indent=2,
        )
    )
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
