"""Pairing agent status from the BlueZ host (SSH) for the Lab UI card.

The agent (tools/bt_pair_agent.py, unit bt-pair-agent) runs next to bluetoothd;
this module only reads its `--status` JSON and opens a pairing window.
"""

from __future__ import annotations

import json
import subprocess
import threading
import time
from typing import Any

from controller.btmon_live import SSH_TARGET

REMOTE_PY = "/opt/bt-analyzer/bt_pair_agent.py"
CACHE_S = 2.0

_lock = threading.Lock()
_cache: dict[str, Any] = {"t": 0.0, "data": None}


def _ssh(*remote: str, timeout: float = 10.0) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=5", SSH_TARGET, *remote],
        capture_output=True, text=True, timeout=timeout,
    )


def status() -> dict[str, Any]:
    with _lock:
        if _cache["data"] is not None and time.time() - _cache["t"] < CACHE_S:
            return _cache["data"]
    try:
        p = _ssh("python3", REMOTE_PY, "--status")
        data = {"ok": True, "ssh": SSH_TARGET, **json.loads(p.stdout)}
    except (OSError, subprocess.TimeoutExpired) as exc:
        data = {"ok": False, "ssh": SSH_TARGET, "error": str(exc)}
    except ValueError:
        err = (p.stderr or p.stdout or "").strip()[-300:]
        if "No such file" in err or "can't open file" in err:
            err = "Agent nicht installiert — python3 tools/lab_pair_agent.py deploy"
        data = {"ok": False, "ssh": SSH_TARGET, "error": err or f"exit {p.returncode}"}
    with _lock:
        _cache.update(t=time.time(), data=data)
    return data


def open_window(seconds: int) -> dict[str, Any]:
    seconds = max(10, min(int(seconds), 1800))
    try:
        p = _ssh("python3", REMOTE_PY, "--open-window", str(seconds))
        out = json.loads(p.stdout)
    except (OSError, subprocess.TimeoutExpired, ValueError) as exc:
        out = {"ok": False, "error": str(exc)}
    with _lock:
        _cache["data"] = None
    return out
