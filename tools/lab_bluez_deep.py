#!/usr/bin/env python3
"""Deeper Proxmox BlueZ host battery vs ESP triad (no external peripherals).

Steps: show → LE scan → connect/reconnect×N → classic discoverable .87 visibility →
optional timeline skew sample. GATT resolve on thin stub is best-effort.

Usage:
  python3 tools/lab_bluez_deep.py
  python3 tools/lab_bluez_deep.py --reconnects 3
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
    with urllib.request.urlopen(url, timeout=6) as r:
        return json.loads(r.read().decode())


def post(url: str, fields: dict | None = None) -> None:
    data = urllib.parse.urlencode(fields or {}).encode()
    req = urllib.request.Request(url, data=data, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=6) as r:
            r.read()
    except Exception:  # noqa: BLE001
        pass


def load_ssh():
    import importlib.util

    spec = importlib.util.spec_from_file_location("lab_bt_host_ssh", ROOT / "tools" / "lab_bt_host_ssh.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--peer", default="192.168.178.89")
    ap.add_argument("--classic", default="192.168.178.87")
    ap.add_argument("--reconnects", type=int, default=3)
    ap.add_argument("--scan-s", type=float, default=6.0)
    args = ap.parse_args()
    utc = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    ssh = load_ssh()

    steps = []

    def step(name, fn):
        t0 = time.time()
        try:
            res = fn()
            ok = bool(res.get("ok")) if isinstance(res, dict) else bool(res)
            steps.append({"step": name, "ok": ok, "elapsed_s": round(time.time() - t0, 3), "result": res})
            return ok
        except Exception as exc:  # noqa: BLE001
            steps.append({"step": name, "ok": False, "elapsed_s": round(time.time() - t0, 3), "error": str(exc)})
            return False

    show = ssh.show()
    step("show", lambda: show)

    post(f"http://{args.peer}/api/bt/disconnect")
    st = get(f"http://{args.peer}/api/status")
    bd = ((st.get("onchip") or {}).get("bdAddr") or "").lower()
    try:
        ssh.disconnect(bd)
    except Exception:  # noqa: BLE001
        pass
    post(f"http://{args.peer}/api/bt/advertise/start", {"name": "bluez-deep", "hid": "1", "ftms": "1"})
    time.sleep(0.7)

    step("scan_le", lambda: {"ok": bd in (ssh.scan(args.scan_s).get("addrs") or []), "bd": bd})

    reconnects = []
    for i in range(max(1, args.reconnects)):
        post(f"http://{args.peer}/api/bt/advertise/start", {"name": "bluez-deep"})
        time.sleep(0.4)
        c = ssh.connect(bd, timeout_s=25)
        d = ssh.disconnect(bd)
        reconnects.append({"i": i, "connect": bool(c.get("ok")), "disconnect": bool(d.get("ok")), "elapsed_s": c.get("elapsed_s")})
        time.sleep(0.5)
    step(
        "reconnect_matrix",
        lambda: {
            "ok": all(r["connect"] and r["disconnect"] for r in reconnects),
            "runs": reconnects,
        },
    )

    # Classic visibility: .87 discoverable, BlueZ scan should see BD
    st87 = get(f"http://{args.classic}/api/status")
    bd87 = ((st87.get("onchip") or {}).get("bdAddr") or "").lower()
    post(f"http://{args.classic}/api/bt/discoverable/start", {"name": "deep-classic-87"})
    time.sleep(0.8)
    scan2 = ssh.scan(max(8.0, args.scan_s))
    seen87 = bd87 in (scan2.get("addrs") or [])
    step("classic_visible", lambda: {"ok": seen87, "bd": bd87, "fw": st87.get("fwVersion") or st87.get("version")})
    post(f"http://{args.classic}/api/bt/discoverable/stop")
    post(f"http://{args.peer}/api/bt/advertise/stop")

    # Quick offset sample (.88/.89) for host×esp skew context
    skew = {}
    try:
        import importlib.util

        spec = importlib.util.spec_from_file_location("tl", ROOT / "tools" / "lab_multi_node_timeline.py")
        tl = importlib.util.module_from_spec(spec)
        assert spec and spec.loader
        spec.loader.exec_module(tl)
        offs = tl.estimate_offsets(5)
        skew = {k: {"ok": v.get("ok"), "rtt_ms": v.get("rtt_ms_median")} for k, v in offs.items()}
        step("timeline_offsets", lambda: {"ok": sum(1 for v in offs.values() if v.get("ok")) >= 2, "offsets": skew})
    except Exception as exc:  # noqa: BLE001
        step("timeline_offsets", lambda: {"ok": False, "error": str(exc)})

    required = ("show", "scan_le", "reconnect_matrix", "classic_visible")
    by = {s["step"]: s for s in steps}
    ok = all(by.get(n, {}).get("ok") for n in required)
    out = {
        "utc": utc,
        "gate": "BlueZ_deep",
        "topology": "H_HOST_ORACLE",
        "claim": "bluez_host_stability_vs_esp_not_air",
        "controller": show.get("controller"),
        "peer_bd": bd,
        "classic_bd": bd87,
        "steps": steps,
        "ok": ok,
    }
    stem = f"LAB_BLUEZ_DEEP_{utc}"
    (EVIDENCE / f"{stem}.json").write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    lines = [
        f"# LAB BlueZ Deep — {'PASS' if ok else 'FAIL'}",
        "",
        f"**UTC:** {utc}",
        "",
        "| step | ok | s |",
        "|------|----|---|",
    ]
    for s in steps:
        lines.append(f"| {s['step']} | {s.get('ok')} | {s.get('elapsed_s')} |")
    lines.append("")
    (EVIDENCE / f"{stem}.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"ok": ok, "stem": stem, "reconnects": reconnects}, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
