#!/usr/bin/env python3
"""Deploy and query the BlueZ pairing agent on the BlueZ host (docs/PAIRING.md).

  python3 tools/lab_pair_agent.py deploy        # copy, install unit, enable --now
  python3 tools/lab_pair_agent.py status        # adapters, paired devices, last events
  python3 tools/lab_pair_agent.py window 300    # accept pairing for 300 s (rule window)
  python3 tools/lab_pair_agent.py remove C8:C9:A3:CB:37:96 AA:BB:CC:DD:EE:FF

Override host: BT_HOST_SSH=user@host
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from lab_bt_host_ssh import DEFAULT_SSH, ssh_run  # noqa: E402

REMOTE_DIR = "/opt/bt-analyzer"
REMOTE_PY = f"{REMOTE_DIR}/bt_pair_agent.py"
UNIT = "bt-pair-agent.service"


def status() -> dict[str, Any]:
    try:
        p = ssh_run(["python3", REMOTE_PY, "--status"], timeout=12)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"ok": False, "ssh": DEFAULT_SSH, "error": str(exc)}
    try:
        return {"ok": True, "ssh": DEFAULT_SSH, **json.loads(p.stdout)}
    except ValueError:
        err = (p.stderr or p.stdout or "").strip()[-300:]
        if "No such file" in err or "can't open file" in err:
            err = f"agent not deployed ({REMOTE_PY}) — python3 tools/lab_pair_agent.py deploy"
        return {"ok": False, "ssh": DEFAULT_SSH, "error": err or f"exit {p.returncode}"}


def service_active() -> bool:
    try:
        p = ssh_run(["systemctl", "is-active", UNIT], timeout=10)
    except (OSError, subprocess.TimeoutExpired):
        return False
    return (p.stdout or "").strip() == "active"


def open_window(seconds: int) -> dict[str, Any]:
    try:
        p = ssh_run(["python3", REMOTE_PY, "--open-window", str(int(seconds))], timeout=12)
        return json.loads(p.stdout)
    except (OSError, subprocess.TimeoutExpired, ValueError) as exc:
        return {"ok": False, "error": str(exc)}


def remove_device(adapter_bd: str, device_bd: str) -> dict[str, Any]:
    script = f"select {adapter_bd}\nremove {device_bd}\nquit\n"
    p = ssh_run(["bluetoothctl"], timeout=20, input_text=script)
    out = (p.stdout or "") + (p.stderr or "")
    return {"ok": "Device has been removed" in out, "tail": out[-400:]}


def deploy() -> dict[str, Any]:
    files = [str(ROOT / "tools" / "bt_pair_agent.py"), str(ROOT / "tools" / UNIT)]
    ssh_run(["mkdir", "-p", REMOTE_DIR], timeout=15)
    p = subprocess.run(["scp", "-o", "BatchMode=yes", "-o", "ConnectTimeout=5", *files,
                        f"{DEFAULT_SSH}:{REMOTE_DIR}/"], capture_output=True, text=True, timeout=30)
    if p.returncode != 0:
        return {"ok": False, "step": "scp", "error": p.stderr.strip()}
    p = ssh_run(["bash", "-lc",
                 f"'install -m 644 {REMOTE_DIR}/{UNIT} /etc/systemd/system/{UNIT} && "
                 f"systemctl daemon-reload && systemctl enable {UNIT} && systemctl restart {UNIT} && "
                 f"sleep 5 && systemctl is-active {UNIT}; journalctl -u {UNIT} -n 15 --no-pager'"],
                timeout=60)
    out = (p.stdout or "") + (p.stderr or "")
    return {"ok": out.lstrip().startswith("active"), "log": out[-1500:]}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("deploy")
    sub.add_parser("status")
    w = sub.add_parser("window")
    w.add_argument("seconds", type=int, nargs="?", default=300)
    r = sub.add_parser("remove")
    r.add_argument("adapter_bd")
    r.add_argument("device_bd")
    args = ap.parse_args()

    if args.cmd == "deploy":
        out = deploy()
    elif args.cmd == "status":
        out = status()
    elif args.cmd == "window":
        out = open_window(args.seconds)
    else:
        out = remove_device(args.adapter_bd, args.device_bd)
    print(json.dumps(out, indent=2, ensure_ascii=False))
    return 0 if out.get("ok", True) else 1


if __name__ == "__main__":
    raise SystemExit(main())
