#!/usr/bin/env python3
"""R1b — BlueZ connect/reconnect matrix against ESP peripheral (bond optional).

Usage:
  python3 tools/lab_r1_pair_matrix.py
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
    ap.add_argument("--scan-s", type=float, default=8.0)
    args = ap.parse_args()
    utc = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    ssh = load_ssh()

    st = get(f"http://{args.peer}/api/status")
    bd = ((st.get("onchip") or {}).get("bdAddr") or "").lower()
    steps = []

    def step(name: str, fn):
        t0 = time.time()
        try:
            res = fn()
            ok = bool(res.get("ok")) if isinstance(res, dict) else bool(res)
            steps.append({"step": name, "ok": ok, "elapsed_s": round(time.time() - t0, 3), "result": res})
            return ok
        except Exception as exc:  # noqa: BLE001
            steps.append({"step": name, "ok": False, "elapsed_s": round(time.time() - t0, 3), "error": str(exc)})
            return False

    # Fresh advertise; avoid remove() which can confuse LE reconnect without SMP.
    # Pair/SMP first poisons BlueZ on thin ESP (AuthenticationCanceled) — do soft
    # connect/reconnect first, then optional bond attempt after a clean reset.
    post(f"http://{args.peer}/api/bt/disconnect")
    ssh.disconnect(bd)
    time.sleep(0.4)
    post(f"http://{args.peer}/api/bt/advertise/start", {"name": "r1b-pair-89"})
    time.sleep(0.8)
    step("scan", lambda: {"ok": bd in (ssh.scan(args.scan_s).get("addrs") or []), "bd": bd})
    step("connect1", lambda: ssh.connect(bd, timeout_s=35))
    step("disconnect1", lambda: ssh.disconnect(bd))
    time.sleep(0.8)
    post(f"http://{args.peer}/api/bt/advertise/start", {"name": "r1b-pair-89"})
    time.sleep(0.5)
    step("reconnect", lambda: ssh.connect(bd, timeout_s=35))
    step("disconnect2", lambda: ssh.disconnect(bd))

    # Optional bond: reset link state so a failed SMP does not spoil soft_ok.
    ssh.disconnect(bd)
    post(f"http://{args.peer}/api/bt/advertise/start", {"name": "r1b-pair-89"})
    time.sleep(0.5)
    step("pair_optional", lambda: ssh.pair(bd))
    ssh.disconnect(bd)

    by = {s["step"]: s for s in steps}
    soft_ok = all(by.get(n, {}).get("ok") for n in ("scan", "connect1", "disconnect1", "reconnect", "disconnect2"))
    out = {
        "utc": utc,
        "gate": "R1b_pair_matrix",
        "topology": "H_HOST_ORACLE",
        "claim": "bluez_reconnect_vs_esp_peripheral",
        "peer_bd": bd,
        "steps": steps,
        "pair_ok": by.get("pair_optional", {}).get("ok"),
        "soft_ok": soft_ok,
        "ok": soft_ok,
        "note": "Bond/SMP optional on thin ESP peer — soft_ok is connect/reconnect MEASURED",
    }
    stem = f"LAB_R1_PAIR_MATRIX_{utc}"
    (EVIDENCE / f"{stem}.json").write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    lines = [
        f"# LAB R1b Pair Matrix — {'PASS' if out['ok'] else 'FAIL'}",
        "",
        f"**UTC:** {utc} · peer `{bd}`",
        "",
        "| step | ok | s |",
        "|------|----|---|",
    ]
    for s in steps:
        lines.append(f"| {s['step']} | {s.get('ok')} | {s.get('elapsed_s')} |")
    lines += ["", f"pair_ok={out['pair_ok']} (optional)", ""]
    (EVIDENCE / f"{stem}.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    post(f"http://{args.peer}/api/bt/advertise/stop")
    print(json.dumps({"ok": out["ok"], "stem": stem, "pair_ok": out["pair_ok"]}, indent=2))
    return 0 if out["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
