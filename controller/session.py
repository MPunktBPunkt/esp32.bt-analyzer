"""Live BTAC capture session manager (Debian collector).

Supports multiple named sessions (PROXY dual: phone_side + car_side) while
keeping the legacy single-session API (name=\"default\").
"""

from __future__ import annotations

import collections
import socket
import struct
import threading
import time
import zlib
from dataclasses import dataclass, field
from pathlib import Path

HDR_FMT = "<4sBBHIQBBBBH"
HDR_SIZE = struct.calcsize(HDR_FMT)
MAGIC = b"BTAC"
FRAME_RING = 128
DIR_NAME = {0: "unknown", 1: "TX", 2: "RX"}
TYPE_NAME = {
    0: "unknown",
    1: "cmd",
    2: "evt",
    3: "acl",
    4: "sco",
    5: "iso",
    0xFE: "meta",
}


def _frame_dict(hdr: bytes, payload: bytes) -> dict:
    _m, ver, flags, stream_id, seq, ts_us, direction, ptype, endpoint, _r, length = struct.unpack(
        HDR_FMT, hdr
    )
    hx = payload.hex()
    return {
        "version": ver,
        "flags": flags,
        "stream_id": stream_id,
        "seq": seq,
        "ts_us": ts_us,
        "dir": DIR_NAME.get(direction, str(direction)),
        "type": TYPE_NAME.get(ptype, str(ptype)),
        "endpoint": endpoint,
        "length": length,
        "payload_hex": hx,
        "payload_hex_short": (hx[:96] + "…") if len(hx) > 96 else hx,
        "crc_ok": True,
    }


@dataclass
class Session:
    ip: str
    name: str = "default"
    port: int = 9753
    started_at: float = field(default_factory=time.time)
    frames: int = 0
    bytes: int = 0
    gaps: int = 0
    errors: int = 0
    running: bool = False
    path: Path | None = None
    last_seq: int | None = None
    error: str | None = None
    recent: collections.deque = field(default_factory=lambda: collections.deque(maxlen=FRAME_RING))
    bytes_rx: int = 0
    bytes_tx: int = 0
    rate_frames: float = 0.0
    rate_bytes: float = 0.0
    rate_bps_rx: float = 0.0
    rate_bps_tx: float = 0.0
    _win_t0: float = field(default_factory=time.time)
    _win_frames: int = 0
    _win_bytes: int = 0
    _win_rx: int = 0
    _win_tx: int = 0


_lock = threading.Lock()
_sessions: dict[str, Session] = {}
_threads: dict[str, threading.Thread] = {}
SESS_DIR = Path(__file__).resolve().parents[1] / "docs" / "evidence" / "sessions"


def _read_exact(sock: socket.socket, n: int) -> bytes:
    buf = bytearray()
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            raise EOFError("closed")
        buf.extend(chunk)
    return bytes(buf)


def _update_rates(sess: Session, direction: int, plen: int) -> None:
    now = time.time()
    sess._win_frames += 1
    sess._win_bytes += plen
    if direction == 2:
        sess.bytes_rx += plen
        sess._win_rx += plen
    elif direction == 1:
        sess.bytes_tx += plen
        sess._win_tx += plen
    dt = now - sess._win_t0
    if dt >= 1.0:
        sess.rate_frames = sess._win_frames / dt
        sess.rate_bytes = sess._win_bytes / dt
        sess.rate_bps_rx = sess._win_rx / dt
        sess.rate_bps_tx = sess._win_tx / dt
        sess._win_t0 = now
        sess._win_frames = 0
        sess._win_bytes = 0
        sess._win_rx = 0
        sess._win_tx = 0


def _recv_loop(sess: Session) -> None:
    SESS_DIR.mkdir(parents=True, exist_ok=True)
    tag = sess.name.replace("/", "_")
    out = SESS_DIR / f"session_{tag}_{sess.ip.replace('.', '_')}_{int(sess.started_at)}.btac"
    sess.path = out
    try:
        sock = socket.create_connection((sess.ip, sess.port), timeout=8.0)
        sock.settimeout(2.0)
        with out.open("wb") as f:
            sess.running = True
            while sess.running:
                try:
                    hdr = _read_exact(sock, HDR_SIZE)
                    magic, ver, *_rest, length = struct.unpack(HDR_FMT, hdr)
                    if magic != MAGIC or ver != 1 or length > 1024:
                        sess.errors += 1
                        break
                    payload = _read_exact(sock, length) if length else b""
                    crc_raw = _read_exact(sock, 4)
                    crc_wire = struct.unpack("<I", crc_raw)[0]
                    if (zlib.crc32(hdr + payload) & 0xFFFFFFFF) != crc_wire:
                        sess.errors += 1
                        continue
                    seq = struct.unpack_from("<I", hdr, 8)[0]
                    if sess.last_seq is not None and seq > sess.last_seq + 1:
                        sess.gaps += seq - sess.last_seq - 1
                    sess.last_seq = seq
                    raw = hdr + payload + crc_raw
                    f.write(raw)
                    sess.frames += 1
                    sess.bytes += len(raw)
                    direction = struct.unpack_from("<B", hdr, 18)[0]
                    _update_rates(sess, direction, length)
                    try:
                        sess.recent.appendleft(_frame_dict(hdr, payload))
                    except Exception:  # noqa: BLE001
                        pass
                except socket.timeout:
                    continue
                except (EOFError, OSError) as exc:
                    sess.error = str(exc)
                    break
        sock.close()
    except OSError as exc:
        sess.error = str(exc)
    finally:
        sess.running = False


def _status_one(s: Session) -> dict:
    return {
        "active": s.running,
        "name": s.name,
        "ip": s.ip,
        "port": s.port,
        "frames": s.frames,
        "bytes": s.bytes,
        "gaps": s.gaps,
        "errors": s.errors,
        "path": str(s.path) if s.path else None,
        "error": s.error,
        "uptime_s": int(time.time() - s.started_at),
        "bytes_rx": s.bytes_rx,
        "bytes_tx": s.bytes_tx,
        "rate_fps": round(s.rate_frames, 1),
        "rate_Bps": round(s.rate_bytes, 1),
        "rate_rx_Bps": round(s.rate_bps_rx, 1),
        "rate_tx_Bps": round(s.rate_bps_tx, 1),
        "recent_n": len(s.recent),
    }


def start(ip: str, port: int = 9753, name: str = "default") -> dict:
    with _lock:
        cur = _sessions.get(name)
        if cur and cur.running:
            return {"ok": False, "error": "session_active", "session": _status_one(cur)}
        sess = Session(ip=ip, port=port, name=name)
        _sessions[name] = sess
        th = threading.Thread(target=_recv_loop, args=(sess,), daemon=True, name=f"btac-{name}")
        _threads[name] = th
        th.start()
    time.sleep(0.2)
    return {"ok": True, "session": status(name)}


def stop(name: str = "default") -> dict:
    with _lock:
        sess = _sessions.get(name)
        if not sess:
            return {"ok": False, "error": "no_session"}
        sess.running = False
        th = _threads.get(name)
    if th:
        th.join(timeout=5.0)
    return {"ok": True, "session": status(name)}


def stop_all() -> dict:
    names = list(_sessions.keys())
    results = {n: stop(n) for n in names}
    return {"ok": True, "stopped": results}


def status(name: str | None = "default") -> dict:
    """Legacy: status() / status(\"default\") → one session.
    status(None) → {sessions: {...}} for all.
    """
    with _lock:
        if name is None:
            return {
                "sessions": {n: _status_one(s) for n, s in _sessions.items()},
                "active_n": sum(1 for s in _sessions.values() if s.running),
            }
        s = _sessions.get(name)
    if not s:
        return {"active": False, "name": name}
    return _status_one(s)


def recent_frames(n: int = 64, name: str = "default") -> dict:
    with _lock:
        s = _sessions.get(name)
        if not s:
            return {"ok": True, "active": False, "name": name, "frames": []}
        frames = list(s.recent)[: max(1, min(n, FRAME_RING))]
        return {
            "ok": True,
            "active": s.running,
            "name": s.name,
            "ip": s.ip,
            "frames": frames,
            "session": {
                "frames": s.frames,
                "gaps": s.gaps,
                "rate_fps": round(s.rate_frames, 1),
                "rate_rx_Bps": round(s.rate_bps_rx, 1),
                "rate_tx_Bps": round(s.rate_bps_tx, 1),
            },
        }


# --- PROXY dual helpers -------------------------------------------------------

PROXY_SIDES = {
    "phone_side": "192.168.178.131",
    "car_side": "192.168.178.87",
}


def proxy_start(phone_ip: str | None = None, car_ip: str | None = None, port: int = 9753) -> dict:
    phone_ip = phone_ip or PROXY_SIDES["phone_side"]
    car_ip = car_ip or PROXY_SIDES["car_side"]
    a = start(phone_ip, port=port, name="phone_side")
    b = start(car_ip, port=port, name="car_side")
    return {
        "ok": bool(a.get("ok") and b.get("ok")),
        "phone_side": a,
        "car_side": b,
        "proxy": proxy_status(),
    }


def proxy_stop() -> dict:
    return {
        "ok": True,
        "phone_side": stop("phone_side"),
        "car_side": stop("car_side"),
        "proxy": proxy_status(),
    }


def proxy_status() -> dict:
    with _lock:
        phone = _sessions.get("phone_side")
        car = _sessions.get("car_side")
    return {
        "active": bool(phone and phone.running) or bool(car and car.running),
        "dual_active": bool(phone and phone.running and car and car.running),
        "phone_side": _status_one(phone) if phone else {"active": False, "name": "phone_side"},
        "car_side": _status_one(car) if car else {"active": False, "name": "car_side"},
    }
