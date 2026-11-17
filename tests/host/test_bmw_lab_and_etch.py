import json
import sys
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "tools"))
sys.path.insert(0, str(REPO_ROOT))

from controller.api.http_server import Handler  # noqa: E402
from controller.bmw_lab import BmwConnectedLab, DEMO_PIDRIVE_XML  # noqa: E402
from etch_codec import (  # noqa: E402
    build_cds_event,
    build_cds_get_property_call,
    decode_etch_message,
    encode_etch_packet,
    etch_hash,
    inspect_pkcs7_bundle,
)


class TestEtchCodec(unittest.TestCase):
    def test_etch_map_and_capabilities_roundtrip(self):
        self.assertEqual(etch_hash("_Etch_Map"), 0x7FEAE04B)
        self.assertEqual(etch_hash("keysAndValues"), 0xEE9FF760)
        caps = {"hmi.type": "BMW ID5", "iva_ENT_USB_COVER_ART_IPOD": "true", "_ENT_MTP_OFF": "false"}
        pkt = encode_etch_packet(
            "_result_rhmi_getCapabilities",
            {"_inReplyTo": 7, "_messageId": 8, "result": caps},
        )
        dec = decode_etch_message(pkt)
        self.assertEqual(dec["method"], "_result_rhmi_getCapabilities")
        self.assertEqual(dec["raw_fields"]["_inReplyTo"], 7)
        self.assertEqual(dec["raw_fields"]["result"], caps)

    def test_tiny_int_decode_full_etch_range(self):
        # Apache Etch encodes single-byte ints as 0x00-0x7F (0..127) and
        # 0xC0-0xFF (-64..-1). The decoder must accept the full range, not a
        # narrow 0x00-0x1F / 0xE0-0xFF subset (field logs from the real HU use
        # model IDs and values up to 127, e.g. RHMI model 100+ and tiny values).
        from etch_codec import _Reader  # noqa: WPS433

        for raw, expected in ((0x00, 0), (0x1F, 31), (0x20, 32), (0x64, 100), (0x7F, 127)):
            self.assertEqual(_Reader(bytes([raw])).read_int(), expected)
            self.assertEqual(_Reader(bytes([raw])).read_value(), expected)
        for raw, expected in ((0xFF, -1), (0xE0, -32), (0xCE, -50), (0xC0, -64)):
            self.assertEqual(_Reader(bytes([raw])).read_int(), expected)
            self.assertEqual(_Reader(bytes([raw])).read_value(), expected)

    def test_cds_get_and_event_roundtrip(self):
        q = build_cds_get_property_call(12, "vehicle.VIN", msg_id=42)
        dq = decode_etch_message(q)
        self.assertEqual(dq["method"], "cds_getPropertyAsync")
        self.assertEqual(dq["raw_fields"]["ident"], "87")
        self.assertEqual(dq["raw_fields"]["propertyName"], "vehicle.VIN")

        ev = build_cds_event(12, "engine.RPMSpeed", {"RPMSpeed": 1450}, msg_id=43)
        dev = decode_etch_message(ev)
        self.assertEqual(dev["method"], "cds_onPropertyChangedEvent")
        self.assertEqual(json.loads(dev["raw_fields"]["propertyValue"]), {"RPMSpeed": 1450})

    def test_inspect_real_captured_pkcs7_certs(self):
        cert_path = REPO_ROOT / "docs" / "evidence" / "LAB_DUMMY_ETCH_20261114T1550Z_certs" / "src11_b0.pem"
        if not cert_path.is_file():
            self.skipTest("src11_b0.pem not present")
        info = inspect_pkcs7_bundle(cert_path.read_bytes())
        self.assertTrue(info["uses_app_auth_xor"])
        self.assertIn("APP", info["cert_types"])
        self.assertIn("APP_AUTH", info["cert_types"])
        self.assertIn(
            "ab8f2a86e7f648fa4c3399b52d8001a5fe109bcefea790ccbd98f04a9301f93c",
            info["rhmi_description_sha256"],
        )


class TestBmwConnectedLab(unittest.TestCase):
    def test_cds_query_and_update(self):
        lab = BmwConnectedLab()
        q = lab.build_active_cds_query("vehicle.VIN")
        self.assertTrue(q["ok"])
        self.assertEqual(q["ident"], 87)
        self.assertEqual(len(q["tx_bcl_frames_hex"]), 2)  # subscribe + getPropertyAsync

        u = lab.update_cds_value("engine.RPMSpeed", "1950")
        self.assertTrue(u["ok"])
        self.assertEqual(u["value"], {"RPMSpeed": 1950})

    def test_simulated_vs_strict_whitelist_mode(self):
        lab = BmwConnectedLab()
        # In SIMULATED_AUTHORIZATION custom XML is accepted without cert
        ok_res = lab.check_or_load_rhmi_package(xml_text=DEMO_PIDRIVE_XML, app_title="Sim Menu")
        self.assertTrue(ok_res["accepted"])
        self.assertEqual(ok_res["auth_badge"], "SIMULATED_AUTHORIZATION")

        # Switch to F20_STRICT_WHITELIST: custom XML must be rejected even with real SmartThings cert!
        lab.set_auth_mode("F20_STRICT_WHITELIST")
        rej = lab.check_or_load_rhmi_package(
            cert_name_or_pem="src11_b0.pem",
            xml_text=DEMO_PIDRIVE_XML,
            app_title="Untrusted Custom XML",
        )
        self.assertFalse(rej["accepted"])
        self.assertIn("SHA-256", rej["reason"])

    def test_rhmi_set_data_property_and_action_event(self):
        lab = BmwConnectedLab()
        r1 = lab.rhmi_set_data(1, 101, "Sender: DLF (Live)")
        self.assertTrue(r1["ok"])
        self.assertEqual(lab.snapshot()["rhmi_apps"]["1"]["models"]["101"]["value"], "Sender: DLF (Live)")

        r2 = lab.rhmi_set_property(1, 301, 3, False)  # VISIBLE = False
        self.assertTrue(r2["ok"])
        self.assertFalse(lab.snapshot()["rhmi_apps"]["1"]["components"]["301"]["properties"]["VISIBLE"])

        r3 = lab.trigger_idrive_action(1, 302, 201)
        self.assertTrue(r3["ok"])
        self.assertEqual(r3["event"]["method"], "rhmi_onActionEvent")

    def test_ingest_f20_wire_frame(self):
        lab = BmwConnectedLab()
        # Full valid BCL DATA frame (src=10, dst=4004) carrying _result_sas_login
        pkt = encode_etch_packet("_result_sas_login", {"_inReplyTo": 1, "_messageId": 2})
        from bcl_framer import build_synthetic_frame

        bcl = build_synthetic_frame(2, 10, 4004, pkt)
        res = lab.ingest_wire_hex(bcl.hex())
        self.assertTrue(res["ok"])
        self.assertEqual(res["method"], "_result_sas_login")


class TestHttpBmwEndpoints(unittest.TestCase):
    def test_http_state_and_strict_reject(self):
        srv = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        port = srv.server_address[1]
        t = threading.Thread(target=srv.serve_forever, daemon=True)
        t.start()
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/v1/bmw/state", timeout=3) as r:
                st = json.loads(r.read().decode("utf-8"))
            self.assertTrue(st["ok"])
            self.assertGreaterEqual(len(st["cds"]), 15)

            req = urllib.request.Request(
                f"http://127.0.0.1:{port}/api/v1/bmw/cds/query",
                data=json.dumps({"propertyName": "driving.odometer"}).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=3) as r:
                qr = json.loads(r.read().decode("utf-8"))
            self.assertTrue(qr["ok"])
            self.assertEqual(qr["ident"], 39)
        finally:
            srv.shutdown()
            srv.server_close()


class TestFullF20BluetoothHuSimulation(unittest.TestCase):
    """End-to-end test: Phone (MyBMW + AAIdrive) <-> DummyHuSession(f20_sim) over BCL."""

    def test_mybmw_and_aaidrive_full_lifecycle_against_f20_sim(self):
        from bcl_dummy_hu import CMD_OPEN, DummyHuSession, apply_hu_profile
        from bcl_framer import BclFramer, DEST_ETCH_DESK, DEST_WATCHDOG_DESK, INIT_MAGIC, build_synthetic_frame
        from etch_codec import EtchStruct, encode_etch_enum

        hu = DummyHuSession(**apply_hu_profile("f20_sim"))
        framer = BclFramer()

        def send_and_parse(raw_tx: bytes):
            out = b"".join(hu.on_bytes(raw_tx))
            res = framer.feed(out)
            return res.frames

        # 1. BCL INIT -> HS v5 / iid=14 / buf=0x4000
        hs_frames = send_and_parse(INIT_MAGIC)
        self.assertEqual(len(hs_frames), 1)
        self.assertEqual(hs_frames[0].cmd, 4)

        # 2. OPEN(10, 4004) -> F20 sends ONLY DATAACK(8), no premature Etch packet!
        open_frames = send_and_parse(build_synthetic_frame(CMD_OPEN, 10, DEST_ETCH_DESK))
        self.assertEqual(len(open_frames), 1)
        self.assertEqual(open_frames[0].cmd, 6)  # DATAACK(8)

        # 3. sas_certificate (fragmented across 2 BCL frames like real 6.8 KB cert!) -> _result_sas_certificate (16B)
        cert_call = encode_etch_packet("sas_certificate", {"_messageId": 101, "data": b"MIIF" * 1200})
        self.assertEqual(
            [f.cmd for f in send_and_parse(build_synthetic_frame(2, 10, DEST_ETCH_DESK, cert_call[:4000]))],
            [6],  # DATAACK(4008) only until 2nd fragment completes!
        )
        ch_frames = send_and_parse(build_synthetic_frame(2, 10, DEST_ETCH_DESK, cert_call[4000:]))
        etch_replies = [f for f in ch_frames if f.cmd == 2]
        self.assertEqual(len(etch_replies), 1)
        self.assertEqual((etch_replies[0].src, etch_replies[0].dest), (10, DEST_ETCH_DESK))
        ch_dec = decode_etch_message(etch_replies[0].payload)
        self.assertEqual(ch_dec["method"], "_result_sas_certificate")
        self.assertEqual(ch_dec["raw_fields"]["_inReplyTo"], 101)
        self.assertEqual(len(ch_dec["raw_fields"]["result"]), 16)

        # 4. sas_login (512B RSA-4096 sig) -> _result_sas_login
        login_call = encode_etch_packet("sas_login", {"_messageId": 102, "data": b"\xaa" * 512})
        lg_frames = [f for f in send_and_parse(build_synthetic_frame(2, 10, DEST_ETCH_DESK, login_call)) if f.cmd == 2]
        self.assertEqual(decode_etch_message(lg_frames[0].payload)["method"], "_result_sas_login")

        # 5. rhmi_getCapabilities("", 255) -> _result_rhmi_getCapabilities (Map with BMW ID5 / F20)
        cap_call = encode_etch_packet("rhmi_getCapabilities", {"_messageId": 103, "component": "", "handle": 255})
        cap_frames = [f for f in send_and_parse(build_synthetic_frame(2, 10, DEST_ETCH_DESK, cap_call)) if f.cmd == 2]
        cap_dec = decode_etch_message(cap_frames[0].payload)
        self.assertEqual(cap_dec["method"], "_result_rhmi_getCapabilities")
        self.assertEqual(cap_dec["raw_fields"]["result"]["vehicle.type"], "F20")
        self.assertEqual(cap_dec["raw_fields"]["result"]["hmi.type"], "BMW ID5")

        # 6. CDS flow on src=12: cds_create -> cds_getPropertyAsync("vehicle.VIN") -> receives VIN event!
        send_and_parse(build_synthetic_frame(CMD_OPEN, 12, DEST_ETCH_DESK))
        c_create = encode_etch_packet("cds_create", {"_messageId": 201})
        cc_frames = [f for f in send_and_parse(build_synthetic_frame(2, 12, DEST_ETCH_DESK, c_create)) if f.cmd == 2]
        cds_handle = decode_etch_message(cc_frames[0].payload)["raw_fields"]["result"]
        self.assertIsInstance(cds_handle, int)

        vin_q = build_cds_get_property_call(cds_handle, "vehicle.VIN", msg_id=202)
        vin_frames = [f for f in send_and_parse(build_synthetic_frame(2, 12, DEST_ETCH_DESK, vin_q)) if f.cmd == 2]
        methods = [decode_etch_message(f.payload)["method"] for f in vin_frames]
        self.assertEqual(methods, ["_result_cds_getPropertyAsync", "cds_onPropertyChangedEvent"])
        vin_ev = decode_etch_message(vin_frames[1].payload)
        self.assertEqual(json.loads(vin_ev["raw_fields"]["propertyValue"])["VIN"], "WBA1S51080V838304")

        # 7. AAIdrive UI lifecycle on src=19: rhmi_create -> rhmi_checkResource(False) -> rhmi_setResource -> rhmi_initialize
        send_and_parse(build_synthetic_frame(CMD_OPEN, 19, DEST_ETCH_DESK))
        meta = EtchStruct(
            "RHMIMetaData",
            {
                "id": "me.hufman.androidautoidrive.music",
                "version": EtchStruct("VersionInfo", {"major": 0, "minor": 1, "revision": 0}),
                "name": "me.hufman.androidautoidrive.music",
                "vendor": "me.hufman",
            },
        )
        rc_call = encode_etch_packet("rhmi_create", {"_messageId": 301, "token": None, "metaData": meta})
        rc_frames = [f for f in send_and_parse(build_synthetic_frame(2, 19, DEST_ETCH_DESK, rc_call)) if f.cmd == 2]
        rhmi_handle = decode_etch_message(rc_frames[0].payload)["raw_fields"]["result"]
        self.assertGreaterEqual(rhmi_handle, 10)

        chk_call = encode_etch_packet(
            "rhmi_checkResource",
            {"_messageId": 302, "hash": b"\x11" * 16, "handle": rhmi_handle, "size": 120, "name": "", "type": 0},
        )
        chk_frames = [f for f in send_and_parse(build_synthetic_frame(2, 19, DEST_ETCH_DESK, chk_call)) if f.cmd == 2]
        self.assertIs(decode_etch_message(chk_frames[0].payload)["raw_fields"]["result"], False)

        sr_call = encode_etch_packet(
            "rhmi_setResource",
            {"_messageId": 303, "handle": rhmi_handle, "data": DEMO_PIDRIVE_XML.encode("utf-8"), "type": 0},
        )
        sr_frames = [f for f in send_and_parse(build_synthetic_frame(2, 19, DEST_ETCH_DESK, sr_call)) if f.cmd == 2]
        self.assertEqual(decode_etch_message(sr_frames[0].payload)["method"], "_result_rhmi_setResource")

        init_call = encode_etch_packet("rhmi_initialize", {"_messageId": 304, "handle": rhmi_handle})
        init_frames = [f for f in send_and_parse(build_synthetic_frame(2, 19, DEST_ETCH_DESK, init_call)) if f.cmd == 2]
        self.assertEqual(decode_etch_message(init_frames[0].payload)["method"], "_result_rhmi_initialize")

        # 8. Watchdog still echoed cleanly alongside Etch traffic
        wd_frames = send_and_parse(build_synthetic_frame(2, DEST_WATCHDOG_DESK, DEST_WATCHDOG_DESK, b"\x13\x37\x13\x37"))
        self.assertTrue(any(f.cmd == 2 and f.payload == b"\x13\x37\x13\x37" for f in wd_frames))


if __name__ == "__main__":
    unittest.main()
