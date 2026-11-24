"""BCL frame walk + fragmentation-aware Etch reassembly (B3 Field raw bins).

Used for docs/evidence/FIELD_B3_GATEB_20261121T112446Z/FORENSIC_B3_FRAME_ANALYSIS_20261122.md
and etch_messages_full.csv generation. Prefer forensic/run_raw_forensic.py for full index/SHA.
"""

from __future__ import annotations

import struct
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import etch_codec as ec  # noqa: E402


class ChannelState:
    def __init__(self) -> None:
        self.buf = bytearray()
        self.target: int | None = None
        self.start_hdr_off: int | None = None


def walk_bcl(data: bytes | bytearray, start: int, end: int, direction: str, verbose_log=None):
    frames = []
    etch_msgs = []
    channels: dict[tuple[int, int], ChannelState] = {}
    pos = start
    while pos + 8 <= end:
        cmd, src, dest, length = struct.unpack(">HHHH", data[pos : pos + 8])
        hdr_off = pos
        payload_off = pos + 8
        if length == 0xFFFF or payload_off + length > end + 4096:
            frames.append(
                {
                    "offset": hdr_off,
                    "cmd": cmd,
                    "src": src,
                    "dest": dest,
                    "len": length,
                    "note": "SUSPECT HEADER - stopping",
                }
            )
            break
        payload = data[payload_off : payload_off + length]
        frames.append(
            {
                "offset": hdr_off,
                "cmd": cmd,
                "src": src,
                "dest": dest,
                "len": length,
                "payload_off": payload_off,
            }
        )
        pos = payload_off + length

        if cmd != 2 or length == 0:
            continue

        key = (src, dest)
        st = channels.setdefault(key, ChannelState())
        sub = payload
        subpos = 0
        while subpos < len(sub):
            if st.target is None:
                remaining = sub[subpos:]
                if len(st.buf) > 0:
                    etch_msgs.append(
                        {
                            "offset": st.start_hdr_off,
                            "error": "orphan buf flushed",
                            "len": len(st.buf),
                        }
                    )
                    st.buf = bytearray()
                if remaining[:4] == b"\xde\xad\xbe\xef" and len(remaining) >= 8:
                    bodylen = struct.unpack(">I", remaining[4:8])[0]
                    st.target = 8 + bodylen
                    st.start_hdr_off = hdr_off
                    st.buf = bytearray()
                    take = min(st.target, len(remaining))
                    st.buf += remaining[:take]
                    subpos += take
                    if len(st.buf) >= st.target:
                        _finish(st, etch_msgs, direction)
                else:
                    etch_msgs.append(
                        {
                            "offset": hdr_off + subpos,
                            "note": "non-etch-magic leftover",
                            "hex_preview": remaining[:16].hex(),
                            "len": len(remaining),
                        }
                    )
                    subpos = len(sub)
            else:
                need = st.target - len(st.buf)
                remaining = sub[subpos:]
                take = min(need, len(remaining))
                st.buf += remaining[:take]
                subpos += take
                if len(st.buf) >= st.target:
                    _finish(st, etch_msgs, direction)
    return frames, etch_msgs, pos


def _finish(st: ChannelState, etch_msgs: list, direction: str) -> None:
    try:
        msg = ec.decode_etch_message(bytes(st.buf[: st.target]))
        method = msg.get("type") or msg.get("method")
    except Exception as e:
        method = f"DECODE_FAIL: {e}"
    etch_msgs.append(
        {
            "offset": st.start_hdr_off,
            "total_len": st.target,
            "method": method,
            "direction": direction,
        }
    )
    st.target = None
    st.buf = bytearray()
    st.start_hdr_off = None