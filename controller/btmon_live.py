"""Live btmon text from the BlueZ host (SSH) → parsed packet blocks for the Lab UI.

btmon runs where bluetoothd and hci_tcp_bridge.py run (Proxmox .108 or a VM);
the unprivileged CT cannot open AF_BLUETOOTH itself. Override: BT_HOST_SSH.
"""

from __future__ import annotations

import collections
import os
import re
import subprocess
import threading
import time
from typing import Any

SSH_TARGET = os.environ.get("BT_HOST_SSH", "root@192.168.178.108")
RING = 400
MAX_DETAIL_LINES = 40

HEADER_RE = re.compile(r"^([<>@=]) (.*)$")
META_RE = re.compile(r"^(.*?)\s{2,}((?:#\d+\s+)?(?:\{[^}]*\}\s+)?\[hci(\d+)\].*)$")
PROTOCOLS = ("AVRCP", "AVCTP", "AVDTP", "A2DP", "SDP", "RFCOMM", "SMP", "ATT", "L2CAP")


def classify(title: str, details: list[str]) -> str:
    for proto in PROTOCOLS:
        if any(proto in line for line in details[:6]):
            return proto
    if title.startswith("HCI Command"):
        return "CMD"
    if title.startswith("HCI Event"):
        return "EVT"
    if title.startswith(("ACL", "SCO", "ISO")):
        return title.split()[0]
    return "SYS"


class BtmonParser:
    """Line-wise btmon text parser; a block ends when the next header starts."""

    def __init__(self) -> None:
        self._cur: dict[str, Any] | None = None

    def feed(self, line: str) -> dict[str, Any] | None:
        line = line.rstrip("\n")
        m = HEADER_RE.match(line)
        if m:
            done = self.flush()
            body = m.group(2)
            meta = META_RE.match(body)
            self._cur = {
                "dir": {"<": "tx", ">": "rx", "@": "mgmt", "=": "note"}[m.group(1)],
                "title": (meta.group(1) if meta else body).strip(),
                "meta": meta.group(2).strip() if meta else "",
                "hci": int(meta.group(3)) if meta else None,
                "details": [],
            }
            return done
        if not line.strip():
            return None
        if self._cur is None:
            # btmon banner or ssh errors ("Permission denied") — keep visible.
            return {"dir": "note", "title": line.strip(), "meta": "", "hci": None,
                    "details": [], "proto": "SYS"}
        if len(self._cur["details"]) < MAX_DETAIL_LINES:
            self._cur["details"].append(line)
        return None

    def flush(self) -> dict[str, Any] | None:
        done, self._cur = self._cur, None
        if done is not None:
            done["proto"] = classify(done["title"], done["details"])
        return done


class BtmonLive:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._blocks: collections.deque = collections.deque(maxlen=RING)
        self._seq = 0
        self._proc: subprocess.Popen | None = None
        self._error: str | None = None
        self._started_at: float | None = None

    def _push(self, block: dict[str, Any]) -> None:
        with self._lock:
            self._seq += 1
            block["seq"] = self._seq
            block["t"] = round(time.time(), 3)
            self._blocks.append(block)

    def _reader(self, proc: subprocess.Popen) -> None:
        parser = BtmonParser()
        assert proc.stdout is not None
        for line in proc.stdout:
            block = parser.feed(line)
            if block:
                self._push(block)
        tail = parser.flush()
        if tail:
            self._push(tail)
        code = proc.wait()
        with self._lock:
            if self._proc is proc:
                self._proc = None
                self._error = f"btmon exited ({code})"

    def start(self) -> dict[str, Any]:
        with self._lock:
            if self._proc is not None:
                return self.status_locked()
            cmd = [
                "ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=5",
                "-o", "ServerAliveInterval=5", SSH_TARGET,
                "stdbuf -oL btmon",
            ]
            try:
                self._proc = subprocess.Popen(
                    cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    text=True, bufsize=1, errors="replace",
                )
            except OSError as exc:
                self._error = str(exc)
                return self.status_locked()
            self._error = None
            self._started_at = time.time()
            proc = self._proc
        threading.Thread(target=self._reader, args=(proc,), daemon=True).start()
        return self.status()

    def stop(self) -> dict[str, Any]:
        with self._lock:
            proc, self._proc = self._proc, None
        if proc is not None:
            proc.terminate()
        return self.status()

    def status_locked(self) -> dict[str, Any]:
        return {
            "ok": self._error is None,
            "running": self._proc is not None,
            "ssh": SSH_TARGET,
            "error": self._error,
            "started_at": self._started_at,
            "last_seq": self._seq,
        }

    def status(self) -> dict[str, Any]:
        with self._lock:
            return self.status_locked()

    def since(self, seq: int, hci: int | None = None, limit: int = 200) -> dict[str, Any]:
        with self._lock:
            blocks = [b for b in self._blocks if b["seq"] > seq and (hci is None or b["hci"] in (hci, None))]
            st = self.status_locked()
        return {**st, "blocks": blocks[-limit:]}


live = BtmonLive()
