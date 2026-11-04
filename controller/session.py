"""Live BTAC capture session manager (Debian collector)."""

from __future__ import annotations

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
    }
