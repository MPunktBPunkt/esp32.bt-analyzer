"""Host unit test: Music NP spine tick (no Bluetooth).

Covers frozen IDs 444/445/446/447 + events 660/661 + actions 336/248.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

from bcl_dummy_hu import PhoneClientSession  # noqa: E402
from etch_codec import decode_etch_message  # noqa: E402
from bcl_framer import BclFramer  # noqa: E402


def _decode_queued(phone: PhoneClientSession) -> list[dict]:
    frames: list[dict] = []
    fr = BclFramer()
    for chunk in phone.drain_tx():
        for f in fr.feed(chunk).frames:
            if f.cmd != 2 or not f.payload:
                continue
            try:
                frames.append(decode_etch_message(f.payload))
            except Exception:
                continue
    return frames


class TestMusicNpSpineSeq(unittest.TestCase):
    def test_tick_setdata_events_then_actions_complete(self):
        phone = PhoneClientSession(mybmw_sim=True, rhmi_music_np_seq=True)
        phone._rhmi_state = "RUNTIME_ACTIVE"
        phone._handles["rhmi_create"] = 23

        t0 = 1_000.0
        phone.tick_rhmi_music_np_seq(t0)
        self.assertEqual(phone._seq_phase, "stabilize")
        self.assertTrue(any(e.get("event") == "music_np_seq_start" for e in phone.events))

        phone.tick_rhmi_music_np_seq(t0 + 5.0)
        self.assertEqual(phone._seq_phase, "await_action")
        decoded = _decode_queued(phone)
        methods = [d.get("method") for d in decoded]
        self.assertEqual(methods.count("rhmi_setData"), 4)
        self.assertEqual(methods.count("rhmi_triggerEvent"), 2)
        model_ids = sorted(
            int((d.get("raw_fields") or {}).get("modelId"))
            for d in decoded
            if d.get("method") == "rhmi_setData"
        )
        event_ids = sorted(
            int((d.get("raw_fields") or {}).get("eventId"))
            for d in decoded
            if d.get("method") == "rhmi_triggerEvent"
        )
        self.assertEqual(model_ids, [444, 445, 446, 447])
        self.assertEqual(event_ids, [660, 661])

        # Simulate HU actions
        phone._dispatch_music_np_action({"actionId": 336, "handle": 23})
        self.assertIsNone(phone.selected_action)
        phone._dispatch_music_np_action({"actionId": 248, "handle": 23})
        self.assertEqual(phone.selected_action, "MUSIC_NP_SPINE")

        phone.tick_rhmi_music_np_seq(t0 + 8.0)
        self.assertEqual(phone._seq_phase, "complete")
        self.assertTrue(any(e.get("event") == "music_np_seq_complete" for e in phone.events))

    def test_load_music_description_when_seq_enabled(self):
        phone = PhoneClientSession(mybmw_sim=True, rhmi_music_np_seq=True)
        desc = phone._load_lab_description()
        self.assertEqual(len(desc), 92085)
        self.assertIn(b'applicationType="Multimedia"', desc)


if __name__ == "__main__":
    unittest.main()
