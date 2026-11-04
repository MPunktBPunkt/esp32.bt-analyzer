#!/usr/bin/env python3
"""R3 lite — .87 Classic discoverable visible to Proxmox BlueZ scan (no A2DP yet).

Usage:
  python3 tools/lab_r3_classic_visible.py
"""

from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "docs" / "evidence"
IP87 = "192.168.178.87"


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
    utc = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    ssh = load_ssh()
    st = get(f"http://{IP87}/api/status")
    bd = ((st.get("onchip") or {}).get("bdAddr") or "").lower()
    post(f"http://{IP87}/api/bt/discoverable/start", {"name": "r3-classic-87"})
    time.sleep(1.0)
    scan = ssh.scan(12.0)
    seen = bd in (scan.get("addrs") or [])
    # Also match by name in device lines
    name_hit = any("r3-classic-87" in ln or "bt-classic" in ln.lower() for ln in (scan.get("devices") or []))
    post(f"http://{IP87}/api/bt/discoverable/stop")
    ok = bool(seen or name_hit)
    out = {
        "utc": utc,
        "gate": "R3_classic_visible",
        "claim": "bluez_sees_87_classic_discoverable_not_a2dp",
        "peer_bd": bd,
        "seen_addr": seen,
        "seen_name": name_hit,
        "scan_n": len(scan.get("addrs") or []),
        "ok": ok,
        "note": "A2DP/HFP still BT17 scaffold — visibility only",
    }
    stem = f"LAB_R3_CLASSIC_VISIBLE_{utc}"
    (EVIDENCE / f"{stem}.json").write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    (EVIDENCE / f"{stem}.md").write_text(
        f"# LAB R3 Classic Visible — {'PASS' if ok else 'FAIL'}\n\n"
        f"**UTC:** {utc} · `{bd}` seen_addr={seen} seen_name={name_hit}\n",
        encoding="utf-8",
    )
    print(json.dumps({"ok": ok, "stem": stem, "seen_addr": seen, "seen_name": name_hit}, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
