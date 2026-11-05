#!/usr/bin/env python3
"""R2a Real↔Synthetic claim split — same profile path, two peer classes.

Synthetic (default): BlueZ connect to .89 HID/FTMS stub + analyzer HOGP/FTMS MEASURE.
Real (optional): pass --real-addr when a foreign keyboard/bike is advertising.

Usage:
  python3 tools/lab_r2_real_synthetic.py
  python3 tools/lab_r2_real_synthetic.py --real-addr AA:BB:CC:DD:EE:FF --profiles hogp
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


def get(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=8) as r:
        return json.loads(r.read().decode())


def post(url: str, fields: dict | None = None) -> dict:
    data = urllib.parse.urlencode(fields or {}).encode()
    req = urllib.request.Request(url, data=data, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=12) as r:
            body = r.read().decode()
            try:
                return json.loads(body) if body else {"ok": True}
            except json.JSONDecodeError:
                return {"raw": body}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc)}


def load_ssh():
    import importlib.util

    spec = importlib.util.spec_from_file_location("lab_bt_host_ssh", ROOT / "tools" / "lab_bt_host_ssh.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def run_synthetic(analyzer: str, peer: str, profiles: str) -> dict:
    ssh = load_ssh()
    post(f"http://{peer}/api/bt/disconnect")
    post(f"http://{analyzer}/api/bt/disconnect")
    st = get(f"http://{peer}/api/status")
    bd = ((st.get("onchip") or {}).get("bdAddr") or "").lower()
    try:
        ssh.disconnect(bd)
    except Exception:  # noqa: BLE001
        pass
    post(f"http://{peer}/api/bt/advertise/start", {"name": "r2-synth", "hid": "1", "ftms": "1"})
    time.sleep(0.8)
    scan = ssh.scan(7.0)
    seen = bd in (scan.get("addrs") or [])
    conn = ssh.connect(bd, timeout_s=30) if seen else {"ok": False}
    # Analyzer path measures profiles (BlueZ GATT often empty on thin stub)
    post(f"http://{analyzer}/api/bt/scan/start")
    time.sleep(0.3)
    link = post(
        f"http://{analyzer}/api/bt/connect",
        {"addr": bd, "addrType": "0"},
    )
    time.sleep(1.0)
    disc = post(f"http://{analyzer}/api/bt/flavor/gatt/discover", {"mtu": "247"})
    time.sleep(1.2)
    hogp = ftms = {}
    if profiles in ("hogp", "both"):
        hogp = post(f"http://{analyzer}/api/bt/flavor/hogp/start")
        time.sleep(0.8)
    if profiles in ("ftms", "both"):
        ftms = post(f"http://{analyzer}/api/bt/flavor/ftms/start")
        time.sleep(0.8)
    st_a = get(f"http://{analyzer}/api/status")
    flavor = st_a.get("flavor") or {}
    hogp_st = st_a.get("hogp") or {}
    ftms_st = st_a.get("ftms") or {}
    ssh.disconnect(bd)
    post(f"http://{analyzer}/api/bt/disconnect")
    post(f"http://{peer}/api/bt/advertise/stop")
    post(f"http://{analyzer}/api/bt/scan/stop")
    analyzer_ok = bool(flavor.get("stimulusTx") or hogp_st or ftms_st or disc.get("ok") is not False)
    return {
        "class": "synthetic_esp_stub",
        "peer_bd": bd,
        "bluez_seen": seen,
        "bluez_connect": bool(conn.get("ok")),
        "analyzer_link": link,
        "hogp": {"start": hogp, "status": hogp_st},
        "ftms": {"start": ftms, "status": ftms_st},
        "flavor": flavor,
        "ok": bool(seen and conn.get("ok") and analyzer_ok),
        "claim": "STIMULUS_L2_over_HCI_not_air",
    }


def run_real(addr: str, profiles: str, analyzer: str) -> dict:
    """Foreign peer — analyzer only (no ESP advertise)."""
    post(f"http://{analyzer}/api/bt/disconnect")
    post(f"http://{analyzer}/api/bt/scan/start")
    time.sleep(0.5)
    link = post(f"http://{analyzer}/api/bt/connect", {"addr": addr.lower(), "addrType": "1"})
    time.sleep(1.2)
    post(f"http://{analyzer}/api/bt/flavor/gatt/discover", {"mtu": "247"})
    time.sleep(1.5)
    if profiles in ("hogp", "both"):
        post(f"http://{analyzer}/api/bt/flavor/hogp/start")
        time.sleep(1.0)
    if profiles in ("ftms", "both"):
        post(f"http://{analyzer}/api/bt/flavor/ftms/start")
        time.sleep(1.0)
    st = get(f"http://{analyzer}/api/status")
    post(f"http://{analyzer}/api/bt/disconnect")
    post(f"http://{analyzer}/api/bt/scan/stop")
    flavor = st.get("flavor") or {}
    return {
        "class": "foreign_real_device",
        "peer_bd": addr.lower(),
        "analyzer_link": link,
        "hogp": st.get("hogp"),
        "ftms": st.get("ftms"),
        "flavor": flavor,
        "ok": bool(flavor.get("stimulusRx") or flavor.get("stimulusTx") or (st.get("hogp") or st.get("ftms"))),
        "claim": "STIMULUS_L2_over_HCI_not_air",
        "note": "Success ≠ Wirkung for FTMS",
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--analyzer", default="192.168.178.88")
    ap.add_argument("--peer", default="192.168.178.89")
    ap.add_argument("--profiles", default="both", choices=("hogp", "ftms", "both"))
    ap.add_argument("--real-addr", default="", help="optional foreign BD_ADDR")
    ap.add_argument("--skip-synthetic", action="store_true")
    args = ap.parse_args()
    utc = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    EVIDENCE.mkdir(parents=True, exist_ok=True)

    arms = {}
    if not args.skip_synthetic:
        arms["synthetic"] = run_synthetic(args.analyzer, args.peer, args.profiles)
    if args.real_addr:
        arms["real"] = run_real(args.real_addr, args.profiles, args.analyzer)

    synth_ok = arms.get("synthetic", {}).get("ok", False)
    real = arms.get("real")
    # PASS when synthetic green; real arm optional (UNKNOWN if absent)
    ok = synth_ok if "synthetic" in arms else bool(real and real.get("ok"))
    out = {
        "utc": utc,
        "gate": "R2a_real_synthetic",
        "topology": "H_HOST_ORACLE",
        "profiles": args.profiles,
        "arms": arms,
        "claim_split": {
            "synthetic": "peer_stub_STIMULUS",
            "real": "foreign_peer_STIMULUS" if real else "UNKNOWN_no_foreign_device",
            "same_claim_tag": "STIMULUS_L2_over_HCI_not_air",
            "success_ne_wirkung": True,
        },
        "ok": ok,
    }
    stem = f"LAB_R2_REAL_SYNTHETIC_{utc}"
    (EVIDENCE / f"{stem}.json").write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    lines = [
        f"# LAB R2 Real↔Synthetic — {'PASS' if ok else 'FAIL'}",
        "",
        f"**UTC:** {utc} · profiles `{args.profiles}`",
        "",
        f"- synthetic: {arms.get('synthetic', {}).get('ok')}",
        f"- real: {arms.get('real', {}).get('ok', 'skipped')}",
        "",
        "Same claim tag on both arms; FTMS Success ≠ Wirkung.",
        "",
    ]
    (EVIDENCE / f"{stem}.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "ok": ok,
                "stem": stem,
                "synthetic": arms.get("synthetic", {}).get("ok"),
                "real": arms.get("real", {}).get("ok") if real else None,
            },
            indent=2,
        )
    )
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
