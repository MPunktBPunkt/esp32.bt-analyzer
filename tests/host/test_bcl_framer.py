"""Host tests for tools/bcl_framer.py (synthetic streams only).

  python3 -m unittest tests/host/test_bcl_framer.py

Evidence markers:
  source = synthetic
  evidence_level = TEST
  direct_observation = false
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
from bcl_framer import (  # noqa: E402
    CA_C1_LAB_CHUNKS,
    DEST_ETCH_DESK,
    HEADER_SIZE,
    INIT_MAGIC,
    MAX_PAYLOAD,
    BclFramer,
    BclParseError,
    build_ca_c1_lab_bcl_stream,
    build_phone_session_prelude,
    build_synthetic_frame,
    cmd_desk_name,
    dest_desk_label,
    feed_chunked,
)


class TestBclFramer(unittest.TestCase):
    def test_t1_complete(self):
        payload = bytes([0x01, 0x02, 0x03])
        raw = build_synthetic_frame(2, 0x0010, 0x0020, payload)
        r = BclFramer().feed(raw)
        self.assertEqual(len(r.frames), 1)
        self.assertFalse(r.error)
        self.assertFalse(r.incomplete)
        f = r.frames[0]
        self.assertEqual((f.cmd, f.src, f.dest, f.length, f.payload), (2, 0x10, 0x20, 3, payload))
        self.assertEqual(f.raw, raw)

    def test_t2_fragmented(self):
        raw = build_synthetic_frame(4, 1, 2, bytes([0xAA, 0xBB, 0xCC, 0xDD]))
        full = BclFramer().feed(raw).frames
        fr = BclFramer()
        got = []
        off = 0
        for c in (1, 3, 2):
            chunk = raw[off : off + c]
            off += c
            got.extend(fr.feed(chunk).frames)
        got.extend(fr.feed(raw[off:]).frames)
        self.assertEqual(len(got), 1)
        self.assertEqual(got[0], full[0])

    def test_t3_multiple(self):
        stream = b"".join(
            [
                build_synthetic_frame(1, 1, 2, bytes([0x11])),
                build_synthetic_frame(2, 3, 4, bytes([0x22, 0x33])),
                build_synthetic_frame(3, 5, 6, b""),
            ]
        )
        r = BclFramer().feed(stream)
        self.assertEqual(len(r.frames), 3)
        self.assertEqual(r.frames[2].payload, b"")

    def test_t4_zero_payload(self):
        raw = build_synthetic_frame(1, 0x100, 0x200, b"")
        f = BclFramer().feed(raw).frames[0]
        self.assertEqual(f.length, 0)
        self.assertEqual(len(f.raw), HEADER_SIZE)

    def test_t5_truncated_header(self):
        r = BclFramer().feed(bytes([0x00, 0x02, 0x00, 0x01, 0x0F]))
        self.assertEqual(r.frames, [])
        self.assertTrue(r.incomplete)
        self.assertFalse(r.error)

    def test_t6_truncated_payload(self):
        partial = bytes([0x00, 0x02, 0x00, 0x01, 0x00, 0x02, 0x00, 0x04, 0xDE, 0xAD])
        fr = BclFramer()
        r1 = fr.feed(partial)
        self.assertEqual(r1.frames, [])
        self.assertTrue(r1.incomplete)
        r2 = fr.feed(bytes([0xBE, 0xEF]))
        self.assertEqual(len(r2.frames), 1)
        self.assertEqual(r2.frames[0].payload, bytes([0xDE, 0xAD, 0xBE, 0xEF]))

    def test_t7_malformed_length(self):
        hdr = bytes([0x00, 0x02, 0x00, 0x00, 0x00, 0x00, 0x0F, 0xA1])  # len=4001
        fr = BclFramer()
        r = fr.feed(hdr)
        self.assertEqual(r.frames, [])
        self.assertTrue(r.error)
        self.assertEqual(r.error_code, BclParseError.PAYLOAD_TOO_LARGE)
        r2 = fr.feed(bytes(8))
        self.assertEqual(r2.frames, [])
        self.assertTrue(r2.error)
        fr.reset()
        r3 = fr.feed(build_synthetic_frame(2, 0, 0, bytes([0x01])))
        self.assertEqual(len(r3.frames), 1)
        self.assertFalse(r3.error)

    def test_t8_unknown_cmd(self):
        f = BclFramer().feed(build_synthetic_frame(0x00FE, 1, 2, bytes([0x99]))).frames[0]
        self.assertEqual(f.cmd, 0x00FE)
        self.assertEqual(cmd_desk_name(f.cmd), "UNKNOWN")

    def test_t9_dest_etch_desk(self):
        f = BclFramer().feed(build_synthetic_frame(2, 0x10, DEST_ETCH_DESK, bytes([0x01]))).frames[0]
        self.assertEqual(f.dest, 0x0FA4)
        self.assertEqual(dest_desk_label(f.dest), "Etch")

    def test_t10_no_deadbeef_resync(self):
        bad = bytes([0x00, 0x02, 0x00, 0x00, 0x00, 0x00, 0xFF, 0xFF])
        garbage = bytes([0xDE, 0xAD, 0xBE, 0xEF] * 2)
        valid = build_synthetic_frame(2, 1, 2, bytes([0x42]))
        fr = BclFramer()
        self.assertTrue(fr.feed(bad).error)
        self.assertEqual(fr.feed(garbage).frames, [])
        self.assertEqual(fr.feed(valid).frames, [])
        self.assertTrue(fr.has_error())

    def test_max_payload_boundary(self):
        raw = build_synthetic_frame(2, 0, 0, bytes([0x5A] * MAX_PAYLOAD))
        r = BclFramer().feed(raw)
        self.assertEqual(len(r.frames), 1)
        self.assertEqual(r.frames[0].length, MAX_PAYLOAD)

    def test_ca_c1_lab_stream_chunked(self):
        stream = build_ca_c1_lab_bcl_stream()
        frames, last = feed_chunked(stream, CA_C1_LAB_CHUNKS)
        self.assertEqual(len(frames), 3)
        self.assertEqual(frames[0].cmd, 4)
        self.assertEqual(cmd_desk_name(frames[0].cmd), "HANDSHAKE")
        self.assertEqual(frames[0].payload, bytes(8))
        self.assertEqual(frames[1].cmd, 2)
        self.assertEqual(frames[1].dest, DEST_ETCH_DESK)
        self.assertEqual(frames[1].payload, b"SYNTH01")
        self.assertEqual(frames[2].cmd, 0x00EE)
        self.assertEqual(frames[2].payload, b"")
        self.assertTrue(last.error)
        self.assertEqual(last.error_code, BclParseError.PAYLOAD_TOO_LARGE)

    def test_fragmentation_invariance(self):
        stream = b"".join(
            [
                build_synthetic_frame(1, 9, 8, bytes([1, 2, 3, 4, 5])),
                build_synthetic_frame(2, 7, 6, b""),
                build_synthetic_frame(12, 0, 0, bytes([0xFF])),
            ]
        )
        expected = BclFramer().feed(stream).frames
        for sizes in ((1,) * 8, (8, 5, 8, 1), (3, 10, 2, 1000), (len(stream),)):
            frames, last = feed_chunked(stream, sizes)
            self.assertFalse(last.error)
            self.assertEqual(frames, expected)


class TestSessionInit(unittest.TestCase):
    """Phone→HU prelude per BclCarLink desk evidence (not BMW wire FACT)."""

    def test_prelude_counts_inits_then_frames(self):
        fr = BclFramer()
        r = fr.feed(build_phone_session_prelude(repeats=3))
        self.assertFalse(r.error)
        self.assertEqual(r.session_inits, 3)
        self.assertEqual([f.cmd for f in r.frames], [5])
        self.assertEqual(r.frames[0].payload, bytes([0x00, 0x03]))
        self.assertEqual(fr.session_init_count(), 3)

    def test_prelude_bytewise(self):
        stream = build_phone_session_prelude(repeats=2)
        frames, last = feed_chunked(stream, (1,) * len(stream))
        self.assertFalse(last.error)
        self.assertEqual([f.cmd for f in frames], [5])

    def test_lone_magic_is_not_incomplete(self):
        r = BclFramer().feed(INIT_MAGIC)
        self.assertEqual(r.session_inits, 1)
        self.assertFalse(r.incomplete)
        self.assertEqual(r.frames, [])

    def test_magic_between_frames(self):
        stream = (build_synthetic_frame(2, 1, DEST_ETCH_DESK, b"A") + INIT_MAGIC
                  + build_synthetic_frame(2, 1, DEST_ETCH_DESK, b"B"))
        r = BclFramer().feed(stream)
        self.assertEqual([f.payload for f in r.frames], [b"A", b"B"])
        self.assertEqual(r.session_inits, 1)

    def test_magic_inside_payload_untouched(self):
        raw = build_synthetic_frame(2, 1, DEST_ETCH_DESK, INIT_MAGIC * 2)
        r = BclFramer().feed(raw)
        self.assertEqual(r.session_inits, 0)
        self.assertEqual(r.frames[0].payload, INIT_MAGIC * 2)


if __name__ == "__main__":
    unittest.main()
