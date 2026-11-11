"""HCI agent (hci-agent-esp32) status + rates from cumulative /api/status counters."""

from __future__ import annotations

import json
import threading
import time
import urllib.request
from typing import Any

COUNTERS = ("toCtrlBytes", "toHostBytes", "toCtrlPkts", "toHostPkts")

_lock = threading.Lock()
_prev: dict[str, tuple[float, dict[str, int]]] = {}


def rates(prev: dict[str, int] | None, cur: dict[str, int], dt: float) -> dict[str, float]:
    """Per-second deltas; counter reset (reboot) or no history gives 0."""
    out = {}
    for key in COUNTERS:
        now = int(cur.get(key) or 0)
        before = int((prev or {}).get(key) or 0)
        delta = now - before
        out[key + "Ps"] = round(delta / dt, 1) if prev and dt > 0 and delta >= 0 else 0.0
    return out


def fetch_agent(ip: str, timeout: float = 2.5) -> dict[str, Any]:
    view: dict[str, Any] = {"ip": ip, "ok": False}
    try:
        with urllib.request.urlopen(f"http://{ip}/api/status", timeout=timeout) as resp:
            st = json.loads(resp.read().decode("utf-8", errors="replace"))
    except Exception as exc:  # noqa: BLE001
        view["error"] = str(exc)
        return view
    agent = st.get("hciAgent")
    view.update(ok=True, version=st.get("version"), is_agent=agent is not None)
    if agent is None:
        return view
    now = time.monotonic()
    cur = {k: int(agent.get(k) or 0) for k in COUNTERS}
    with _lock:
        last = _prev.get(ip)
        _prev[ip] = (now, cur)
    view["agent"] = agent
    view["rates"] = rates(last[1] if last else None, cur, now - last[0] if last else 0.0)
    return view
