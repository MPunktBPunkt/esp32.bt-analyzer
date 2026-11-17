"""P0–P2 lab improvements: ServiceException, checkResource digests, phone menu upload."""

from __future__ import annotations

import hashlib
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))

from bcl_dummy_hu import DummyHuSession, PhoneClientSession  # noqa: E402
from bcl_etch_stub import EtchSasCdsStub, build_service_exception  # noqa: E402
from etch_codec import (  # noqa: E402
    EtchStruct,
    TC_CUSTOM,
    decode_etch_message,
    encode_etch_packet,
)


class TestServiceExceptionWire(unittest.TestCase):
    def test_nested_custom_tag_and_fields(self):
        pkt = encode_etch_packet(
            "_result_rhmi_setData",
            {
                "_inReplyTo": 1,
                "_messageId": 2,
                "result": build_service_exception(),
            },
        )
        # After DEADBEEF+len, body starts 03 86 …; nested result must be 0x95
        self.assertIn(bytes([TC_CUSTOM]), pkt)
        dec = decode_etch_message(pkt)
        res = dec["raw_fields"]["result"]
        self.assertIsInstance(res, EtchStruct)
        self.assertIn("ServiceException", res.type_name)
        self.assertEqual(res.fields.get("errorCode"), 213)
        self.assertIn("SetData", str(res.fields.get("detailMessage")))


class TestF20CheckResourceDigest(unittest.TestCase):
    def test_unknown_false_known_true_after_upload(self):
        stub = EtchSasCdsStub(stage="f20_full")
        # Unknown digest → False
        req = encode_etch_packet(
            "rhmi_checkResource",
            {"_messageId": 10, "handle": 12, "hash": "a" * 64, "type": 0},
        )
        rep = stub.on_etch_data(10, req)
        self.assertEqual(len(rep), 1)
        dec = decode_etch_message(rep[0])
        self.assertEqual(dec["method"], "_result_rhmi_checkResource")
        self.assertIs(dec["raw_fields"]["result"], False)

        desc = b"<pluginApps>lab</pluginApps>"
        digest = hashlib.sha256(desc).hexdigest()
        import os

        prev = os.environ.get("BCL_RHMI_RESOURCES")
        with tempfile.TemporaryDirectory() as td:
            os.environ["BCL_RHMI_RESOURCES"] = td
            up = encode_etch_packet(
                "rhmi_setResource",
                {
                    "_messageId": 11,
                    "handle": 12,
                    "hash": digest,
                    "type": 0,
                    "data": desc,
                },
            )
            stub.on_etch_data(10, up)
            self.assertIn(digest, stub.known_digests)
            saved = list(Path(td).glob("*.bin"))
            self.assertEqual(len(saved), 1)
            self.assertEqual(saved[0].read_bytes(), desc)
        if prev is None:
            os.environ.pop("BCL_RHMI_RESOURCES", None)
        else:
            os.environ["BCL_RHMI_RESOURCES"] = prev

        req2 = encode_etch_packet(
            "rhmi_checkResource",
            {"_messageId": 12, "handle": 12, "hash": digest, "type": 0},
        )
        rep2 = stub.on_etch_data(10, req2)
        dec2 = decode_etch_message(rep2[0])
        self.assertIs(dec2["raw_fields"]["result"], True)


class TestF20SetDataImageIdZero(unittest.TestCase):
    def test_rejects_resource_identifier_id_zero(self):
        stub = EtchSasCdsStub(stage="f20_full")
        req = encode_etch_packet(
            "rhmi_setData",
            {
                "_messageId": 20,
                "handle": 12,
                "modelId": 4,
                "value": EtchStruct(
                    "de.bmw.idrive.BMWRemoting.RHMIResourceIdentifier",
                    {"id": 0},
                ),
            },
        )
        rep = stub.on_etch_data(17, req)
        self.assertEqual(len(rep), 1)
        dec = decode_etch_message(rep[0])
        self.assertEqual(dec["method"], "_result_rhmi_setData")
        res = dec["raw_fields"]["result"]
        self.assertIsInstance(res, EtchStruct)
        self.assertIn("ServiceException", res.type_name)
        self.assertEqual(stub.setdata_reject, 1)

    def test_string_setdata_void_ok(self):
        stub = EtchSasCdsStub(stage="f20_full")
        req = encode_etch_packet(
            "rhmi_setData",
            {
                "_messageId": 21,
                "handle": 12,
                "modelId": 100,
                "value": "Apps",
            },
        )
        rep = stub.on_etch_data(19, req)
        dec = decode_etch_message(rep[0])
        self.assertEqual(dec["method"], "_result_rhmi_setData")
        self.assertIsNone(dec["raw_fields"].get("result"))
        self.assertEqual(stub.setdata_reject, 0)


class TestPhoneHuLoopbackMenu(unittest.TestCase):
    def test_mybmw_sim_uploads_description_and_sees_exception(self):
        """In-process PhoneClientSession ↔ DummyHuSession (f20_sim) smoke."""
        hu = DummyHuSession(
            version=5,
            instance_id=14,
            buffer_size=0x4000,
            echo_watchdog=True,
            send_dataack=True,
            etch_stub=True,
            sas_probe="f20_full",
            etch_reply_src=0,  # F20 (phone_src, 4004)
        )
        phone = PhoneClientSession(
            selectproto=4,
            wire_open5001=True,
            open_etch=True,
            etch_src=10,
            knock_payload="wire_v5",
            mybmw_sim=True,
        )
        # Drive until menu upload + ServiceException or iteration cap
        tx = [phone.session_init()]
        saw_menu = False
        saw_exc = False
        for _ in range(80):
            rx_all: list[bytes] = []
            for chunk in tx:
                rx_all.extend(hu.on_bytes(chunk))
            tx = []
            for chunk in rx_all:
                tx.extend(phone.on_bytes(chunk))
            if not tx:
                # Still drain WD / pending
                if phone.active:
                    tx.append(phone.watchdog_ping())
            for ev in phone.events:
                if ev.get("event") == "mybmw_menu_upload_queued":
                    saw_menu = True
                if ev.get("event") == "mybmw_setdata_service_exception":
                    saw_exc = True
            if saw_menu and saw_exc:
                break
        self.assertTrue(saw_menu, msg=phone.events[-15:])
        self.assertTrue(saw_exc, msg=[e for e in phone.events if "setdata" in e.get("event", "")])
        assert hu.etch is not None
        self.assertGreaterEqual(hu.etch.resources_rx, 1)
        self.assertGreaterEqual(hu.etch.setdata_reject, 1)
        # Full check sequence: DESCRIPTION + TEXTDB + IMAGEDB
        checks = [e for e in phone.events if e.get("event") == "mybmw_check_resource_tx"]
        self.assertEqual([c["type"] for c in checks], ["DESCRIPTION", "TEXTDB", "IMAGEDB"])
        uploads = [e for e in phone.events if e.get("event") == "mybmw_set_resource_tx"]
        self.assertEqual(len(uploads), 1)
        self.assertEqual(uploads[0]["type"], "DESCRIPTION")
        skips = [e for e in phone.events if e.get("event") == "mybmw_set_resource_skipped"]
        self.assertEqual(len(skips), 2)
        menu = next(e for e in phone.events if e.get("event") == "mybmw_menu_upload_queued")
        self.assertEqual(menu.get("uploads"), 1)

    def test_cache_hit_skips_setresource_then_initialize(self):
        """Fall A: checkResource(true) must not force setResource (audit 2026-11-17)."""
        import os

        desc_path = (
            Path(__file__).resolve().parents[2]
            / "tools"
            / "fixtures"
            / "rhmi_description_lab_13598.xml"
        )
        desc = desc_path.read_bytes() if desc_path.is_file() else b"<pluginApps>lab</pluginApps>\n"
        digest = hashlib.sha256(desc).hexdigest()

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
        assert hu.etch is not None
        hu.etch.known_digests.add(digest)

        prev = os.environ.get("BCL_RHMI_CACHE_HIT")
        os.environ["BCL_RHMI_CACHE_HIT"] = "1"
        try:
            phone = PhoneClientSession(
                selectproto=4,
                wire_open5001=True,
                open_etch=True,
                etch_src=10,
                knock_payload="wire_v5",
                mybmw_sim=True,
            )
            tx = [phone.session_init()]
            saw_menu = False
            for _ in range(80):
                rx_all: list[bytes] = []
                for chunk in tx:
                    rx_all.extend(hu.on_bytes(chunk))
                tx = []
                for chunk in rx_all:
                    tx.extend(phone.on_bytes(chunk))
                if not tx and phone.active:
                    tx.append(phone.watchdog_ping())
                if any(e.get("event") == "mybmw_menu_upload_queued" for e in phone.events):
                    saw_menu = True
                    break
        finally:
            if prev is None:
                os.environ.pop("BCL_RHMI_CACHE_HIT", None)
            else:
                os.environ["BCL_RHMI_CACHE_HIT"] = prev

        self.assertTrue(saw_menu, msg=phone.events[-20:])
        uploads = [e for e in phone.events if e.get("event") == "mybmw_set_resource_tx"]
        self.assertEqual(uploads, [], msg="cache hit must not setResource DESCRIPTION")
        desc_rx = [
            e
            for e in phone.events
            if e.get("event") == "mybmw_check_resource_rx" and e.get("type") == "DESCRIPTION"
        ]
        self.assertTrue(desc_rx)
        self.assertEqual(desc_rx[0].get("cache"), "hit")
        self.assertEqual(hu.etch.resources_rx, 0)
        menu = next(e for e in phone.events if e.get("event") == "mybmw_menu_upload_queued")
        self.assertEqual(menu.get("uploads"), 0)
        self.assertGreaterEqual(menu.get("cache_hits"), 1)


if __name__ == "__main__":
    unittest.main()
