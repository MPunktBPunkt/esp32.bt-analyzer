"""Live BTAC capture session manager (Debian collector)."""

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
    # live observability (0.3.14)
    recent: collections.deque = field(default_factory=lambda: collections.deque(maxlen=FRAME_RING))
    bytes_rx: int = 0  # controller_to_host payload
    bytes_tx: int = 0  # host_to_controller payload
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
_session: Session | None = None
_thread: threading.Thread | None = None
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
    if direction == 2:  # controller_to_host
        sess.bytes_rx += plen
        sess._win_rx += plen
    elif direction == 1:  # host_to_controller
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
    out = SESS_DIR / f"session_{sess.ip.replace('.', '_')}_{int(sess.started_at)}.btac"
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


def start(ip: str, port: int = 9753) -> dict:
    global _session, _thread
    with _lock:
        if _session and _session.running:
            return {"ok": False, "error": "session_active", "session": status()}
        sess = Session(ip=ip, port=port)
        _session = sess
        _thread = threading.Thread(target=_recv_loop, args=(sess,), daemon=True, name="btac-session")
        _thread.start()
    time.sleep(0.2)
    return {"ok": True, "session": status()}


def stop() -> dict:
    global _session
    with _lock:
        if not _session:
            return {"ok": False, "error": "no_session"}
        _session.running = False
    if _thread:
        _thread.join(timeout=5.0)
    return {"ok": True, "session": status()}


def status() -> dict:
    with _lock:
        s = _session
    if not s:
        return {"active": False}
    return {
        "active": s.running,
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


def recent_frames(n: int = 64) -> dict:
    with _lock:
        s = _session
        if not s:
            return {"ok": True, "active": False, "frames": []}
        frames = list(s.recent)[: max(1, min(n, FRAME_RING))]
        return {
            "ok": True,
            "active": s.running,
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
