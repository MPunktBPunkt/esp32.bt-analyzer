"""Unit tests for P0 ESP/RFCOMM flap correlator."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

from lab_esp_rfcomm_flap_correlate import (  # noqa: E402
    build_report,
    classify_flap,
    correlate_events,
)


class FlapCorrelateTest(unittest.TestCase):
    def test_classify_tx_pressure(self) -> None:
        before = [{"event": "etch_data_tx", "reason": "etch_reply"} for _ in range(5)]
        before.append({"event": "tx_bytes", "n": 12})
        close = {"event": "rfcomm_closed", "reason": "write_error:11"}
        self.assertEqual(
            classify_flap(close, before, []),
            "tx_pressure_during_etch_reply",
        )

    def test_correlate_reconnect(self) -> None:
        ev = [
            {"ts": 1.0, "event": "etch_data_tx", "reason": "etch_reply"},
            {"ts": 1.1, "event": "etch_data_tx", "reason": "etch_reply"},
            {"ts": 1.2, "event": "etch_data_tx", "reason": "etch_reply"},
            {"ts": 1.3, "event": "tx_bytes", "n": 12},
            {
                "ts": 1.4,
                "event": "rfcomm_closed",
                "reason": "write_error:11",
                "peer": "AA:BB",
                "rfcomm_channel": 6,
                "session_id": "S1",
            },
            {"ts": 5.0, "event": "rfcomm_connected", "peer": "AA:BB", "rfcomm_channel": 6},
            {"ts": 5.1, "event": "session_init"},
            {"ts": 5.2, "event": "handshake_sent"},
        ]
        corr = correlate_events(ev)
        self.assertEqual(corr["flap_count"], 1)
        flap = corr["flaps"][0]
        self.assertEqual(flap["class"], "tx_pressure_during_etch_reply")
        self.assertAlmostEqual(flap["reconnect_s"], 3.6, places=3)
        self.assertEqual(flap["session_id"], "S1")

    def test_build_report_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "hu.jsonl"
            rows = [
                {"ts": 1.0, "event": "watchdog_echo"},
                {"ts": 2.0, "event": "rfcomm_closed", "reason": "eof", "session_id": "X"},
                {"ts": 3.0, "event": "rfcomm_connected"},
                {"ts": 3.1, "event": "handshake_sent"},
            ]
            path.write_text("".join(json.dumps(r) + "\n" for r in rows))
            report = build_report(hu=path)
            self.assertEqual(report["correlation"]["flap_count"], 1)
            self.assertIn("hypothesis_hint", report)


if __name__ == "__main__":
    unittest.main()
