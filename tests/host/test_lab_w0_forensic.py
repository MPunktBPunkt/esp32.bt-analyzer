"""W0 reply forensic correlator + RHMI wait_class."""

from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

from bcl_dummy_hu import DummyHuSession, PhoneClientSession  # noqa: E402
from lab_w0_reply_forensic import analyze  # noqa: E402


def _loop(hu: DummyHuSession, phone: PhoneClientSession, *, until_menu: bool = True) -> None:
    tx = [phone.session_init()]
    saw_menu = False
    for _ in range(120):
        rx_all: list[bytes] = []
        for chunk in tx:
            rx_all.extend(hu.on_bytes(chunk))
        tx = []
        for chunk in rx_all:
            tx.extend(phone.on_bytes(chunk))
        if not tx and phone.active:
            tx.append(phone.watchdog_ping())
        if until_menu and any(e.get("event") == "mybmw_menu_upload_queued" for e in phone.events):
            saw_menu = True
        if saw_menu and not phone._open_txns:
            return
        if saw_menu and any(
            e.get("event") == "mybmw_setdata_service_exception" for e in phone.events
        ):
            # Drain a few more rounds so initialize/setData replies close txns.
            continue


class TestW0Forensic(unittest.TestCase):
    def test_stop_after_description_check_no_init(self):
        import os

        prev = os.environ.get("BCL_RHMI_STOP_AFTER")
        os.environ["BCL_RHMI_STOP_AFTER"] = "description_check"
        try:
            hu = DummyHuSession(
                version=5,
                instance_id=14,
                buffer_size=0x4000,
                echo_watchdog=True,
                send_dataack=True,
                etch_stub=True,
                sas_probe="f20_full",
                etch_reply_src=0,
            )
            phone = PhoneClientSession(
                selectproto=4,
                wire_open5001=True,
                open_etch=True,
                etch_src=10,
                knock_payload="wire_v5",
                mybmw_sim=True,
            )
            tx = [phone.session_init()]
            saw_hold = False
            for _ in range(100):
                rx_all: list[bytes] = []
                for chunk in tx:
                    rx_all.extend(hu.on_bytes(chunk))
                tx = []
                for chunk in rx_all:
                    tx.extend(phone.on_bytes(chunk))
                if not tx and phone.active:
                    tx.append(phone.watchdog_ping())
                if any(e.get("event") == "mybmw_rhmi_hold_after_check" for e in phone.events):
                    saw_hold = True
                    break
        finally:
            if prev is None:
                os.environ.pop("BCL_RHMI_STOP_AFTER", None)
            else:
                os.environ["BCL_RHMI_STOP_AFTER"] = prev
        self.assertTrue(saw_hold)
        self.assertFalse(
            any(e.get("event") == "mybmw_menu_upload_queued" for e in phone.events)
        )
        checks = [e for e in phone.events if e.get("event") == "mybmw_check_resource_tx"]
        self.assertEqual([c["type"] for c in checks], ["DESCRIPTION"])
        self.assertEqual(
            [e for e in phone.events if e.get("event") == "mybmw_set_resource_tx"],
            [],
        )

    def test_snapshot_wait_class_none_after_runtime(self):
        hu = DummyHuSession(
            version=5,
            instance_id=14,
            buffer_size=0x4000,
            echo_watchdog=True,
            send_dataack=True,
            etch_stub=True,
            sas_probe="f20_full",
            etch_reply_src=0,
        )
        phone = PhoneClientSession(
            selectproto=4,
            wire_open5001=True,
            open_etch=True,
            etch_src=10,
            knock_payload="wire_v5",
            mybmw_sim=True,
        )
        _loop(hu, phone)
        snap = phone.forensic_snapshot()
        self.assertEqual(snap["rhmi_state"], "RUNTIME_ACTIVE")
        self.assertIsNone(snap["wait_class"])
        self.assertEqual(snap["open_txns"], [])

    def test_correlator_on_synthetic_miss_path(self):
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            hu = DummyHuSession(
                version=5,
                instance_id=14,
                buffer_size=0x4000,
                echo_watchdog=True,
                send_dataack=True,
                etch_stub=True,
                sas_probe="f20_full",
                etch_reply_src=0,
            )
            phone = PhoneClientSession(
                selectproto=4,
                wire_open5001=True,
                open_etch=True,
                etch_src=10,
                knock_payload="wire_v5",
                mybmw_sim=True,
            )
            _loop(hu, phone)
            phone_path = td_path / "phone.jsonl"
            hu_path = td_path / "hu.jsonl"
            with phone_path.open("w") as fh:
                for e in phone.events:
                    fh.write(json.dumps(e, default=str) + "\n")
            with hu_path.open("w") as fh:
                for e in hu.events:
                    fh.write(json.dumps(e, default=str) + "\n")
            # Minimal phone_done
            with phone_path.open("a") as fh:
                fh.write(
                    json.dumps(
                        {
                            "event": "phone_done",
                            **phone.forensic_snapshot(),
                            "wd_misses": 0,
                        }
                    )
                    + "\n"
                )
            phone_ev = [json.loads(l) for l in phone_path.read_text().splitlines() if l.strip()]
            hu_ev = [json.loads(l) for l in hu_path.read_text().splitlines() if l.strip()]
            rep = analyze(phone_ev, hu_ev)
            self.assertGreaterEqual(rep["counts"]["check_tx"], 3)
            self.assertGreaterEqual(rep["counts"]["check_rx"], 3)
            self.assertIn(rep["case"], ("OK", "OK_PARTIAL", "E"))

    def test_correlator_flags_tx_without_rx(self):
        phone = [
            {"event": "rfcomm_connected"},
            {
                "event": "mybmw_check_resource_tx",
                "type": "DESCRIPTION",
                "msg_id": 1100,
                "hash": "x",
            },
            {"event": "watchdog_echo_missed", "misses": 5},
            {"event": "phone_done", "wd_misses": 5, "active": True},
        ]
        hu = [
            {"event": "rfcomm_connected"},
            {"event": "handshake_sent"},
            {"event": "f20_rpc_rx", "method": "rhmi_create"},
        ]
        rep = analyze(phone, hu)
        self.assertEqual(rep["case"], "A_or_C")
        self.assertEqual(rep["wait_class"], "WATCHDOG_MISS_NO_ETCH_REPLY")


if __name__ == "__main__":
    unittest.main()
