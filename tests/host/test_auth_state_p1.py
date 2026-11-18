"""P1 AuthState + classify_result — wire-validated AUTHENTICATED gate.

T1 Lab-Stub-Login → AUTHENTICATED, bootstrap starts
T2 Cert Exception → CERTIFICATE_REJECTED, no bootstrap
T3 Challenge→Login→Exception → LOGIN_REJECTED
T4 inReplyTo mismatch → ETCH_REPLY_UNMATCHED, no AUTHENTICATED
R5 SE(213) setData — session/runtime stays active (regression, untouched path)
Field replay: FIELD_AUTH_PROBE cert PDU → CERTIFICATE_REJECTED
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

from bcl_dummy_hu import (  # noqa: E402
    AUTH_AUTHENTICATED,
    AUTH_CERTIFICATE_REJECTED,
    AUTH_CERTIFICATE_SENT,
    AUTH_LOGIN_REJECTED,
    AUTH_LOGIN_SENT,
    CMD_DATA,
    DummyHuSession,
    PhoneClientSession,
    RESULT_CHALLENGE,
    RESULT_EXCEPTION,
    RESULT_OK_INT,
    RESULT_VOID_OK,
    classify_result,
)  # AUTH_LOGIN_SENT used by T5 hard-gate
from bcl_etch_stub import (  # noqa: E402
    build_sas_challenge_payload,
    build_sas_login_ok_payload,
    build_service_exception,
)
from bcl_framer import DEST_ETCH_DESK, build_synthetic_frame  # noqa: E402
from etch_codec import encode_etch_packet  # noqa: E402


def _etch_data(body: bytes, *, src: int = 10) -> bytes:
    return build_synthetic_frame(CMD_DATA, src, DEST_ETCH_DESK, body)


def _drive_to_auth(phone: PhoneClientSession, hu: DummyHuSession, *, rounds: int = 40) -> None:
    tx = [phone.session_init()]
    for _ in range(rounds):
        rx_all: list[bytes] = []
        for chunk in tx:
            rx_all.extend(hu.on_bytes(chunk))
        tx = []
        for chunk in rx_all:
            tx.extend(phone.on_bytes(chunk))
        if phone._auth_state in (AUTH_CERTIFICATE_REJECTED, AUTH_LOGIN_REJECTED):
            return
        # Keep flushing until bootstrap TX drained after AUTHENTICATED
        if (
            phone._auth_state == AUTH_AUTHENTICATED
            and phone._bootstrap_reached
            and not tx
        ):
            return
        if not tx and phone.active:
            tx.append(phone.watchdog_ping())


class TestClassifyResult(unittest.TestCase):
    def test_precedence_exception_over_other(self):
        ex = build_service_exception(detail="Certificate is invalid or expired.")
        dec = {
            "method": "_result_sas_certificate",
            "raw_fields": {"_inReplyTo": 1, "result": ex},
        }
        cls = classify_result(dec)
        self.assertEqual(cls["classification"], RESULT_EXCEPTION)
        self.assertIn("invalid", str(cls.get("error_text") or "").lower())

    def test_challenge_bytes(self):
        body = build_sas_challenge_payload(challenge=b"\x02" * 16, in_reply_to=5, msg_id=6)
        from etch_codec import decode_etch_message

        dec = decode_etch_message(body)
        cls = classify_result(dec)
        self.assertEqual(cls["classification"], RESULT_CHALLENGE)
        self.assertEqual(len(cls["result"]), 16)

    def test_login_void_ok(self):
        from etch_codec import decode_etch_message

        dec = decode_etch_message(build_sas_login_ok_payload(in_reply_to=9, msg_id=10))
        cls = classify_result(dec)
        self.assertEqual(cls["classification"], RESULT_VOID_OK)

    def test_ok_int(self):
        cls = classify_result(
            {
                "method": "_result_cds_create",
                "raw_fields": {"_inReplyTo": 1, "result": 10},
            }
        )
        self.assertEqual(cls["classification"], RESULT_OK_INT)
        self.assertEqual(cls["result"], 10)


class TestAuthStateP1(unittest.TestCase):
    def _hu(self) -> DummyHuSession:
        return DummyHuSession(
            version=5,
            instance_id=14,
            buffer_size=0x4000,
            echo_watchdog=True,
            send_dataack=True,
            etch_stub=True,
            sas_probe="f20_full",
            etch_reply_src=0,
        )

    def _phone(self) -> PhoneClientSession:
        return PhoneClientSession(
            selectproto=4,
            wire_open5001=True,
            open_etch=True,
            etch_src=10,
            knock_payload="wire_v5",
            mybmw_sim=True,
        )

    def test_t1_lab_stub_login_authenticated_bootstrap(self):
        hu, phone = self._hu(), self._phone()
        _drive_to_auth(phone, hu, rounds=120)
        self.assertEqual(phone._auth_state, AUTH_AUTHENTICATED)
        self.assertTrue(phone._bootstrap_reached)
        self.assertTrue(
            any(
                e.get("event") == "mybmw_auth_state" and e.get("auth_state") == AUTH_AUTHENTICATED
                for e in phone.events
            )
        )
        self.assertTrue(
            any(
                e.get("event") == "mybmw_rhmi_state"
                and e.get("rhmi_state") == "SAS_AUTHENTICATED"
                for e in phone.events
            )
        )
        self.assertTrue(
            any(e.get("event") == "mybmw_bootstrap_start" for e in phone.events)
        )
        # Lab path continues to RUNTIME_ACTIVE (same loopback as soak/menu tests)
        tx: list[bytes] = [phone.watchdog_ping()] if phone.active else []
        for _ in range(100):
            if phone._rhmi_state == "RUNTIME_ACTIVE":
                break
            rx_all: list[bytes] = []
            for chunk in tx:
                rx_all.extend(hu.on_bytes(chunk))
            tx = []
            for chunk in rx_all:
                tx.extend(phone.on_bytes(chunk))
            if not tx and phone.active:
                tx.append(phone.watchdog_ping())
        self.assertEqual(phone._rhmi_state, "RUNTIME_ACTIVE")
        for k in ("cds_create", "am_create", "rhmi_create", "av_create"):
            self.assertIn(k, phone._handles)
        snap = phone.forensic_snapshot()
        self.assertEqual(snap["auth_state"], AUTH_AUTHENTICATED)
        self.assertEqual(snap["bootstrap_state"], "HANDLES_READY")

    def test_t2_certificate_rejected_no_bootstrap(self):
        phone = self._phone()
        # Minimal HS + OPEN path then inject cert exception matching cert mid.
        from bcl_dummy_hu import parse_handshake  # noqa: F401 — ensure import side

        hu = self._hu()
        # Reach sas_cert TX via normal HS
        tx = [phone.session_init()]
        for _ in range(10):
            rx_all: list[bytes] = []
            for chunk in tx:
                rx_all.extend(hu.on_bytes(chunk))
            tx = []
            for chunk in rx_all:
                tx.extend(phone.on_bytes(chunk))
            if phone._auth_state == AUTH_CERTIFICATE_SENT:
                break
            if not tx and phone.active:
                break
        self.assertEqual(phone._auth_state, AUTH_CERTIFICATE_SENT)
        mid = phone._auth_cert_mid
        self.assertIsNotNone(mid)
        ex = build_service_exception(
            error_code=1, detail="Certificate is invalid or expired."
        )
        body = encode_etch_packet(
            "_result_sas_certificate",
            {"_inReplyTo": int(mid), "_messageId": 9001, "result": ex},
        )
        phone.on_bytes(_etch_data(body, src=10))
        self.assertEqual(phone._auth_state, AUTH_CERTIFICATE_REJECTED)
        self.assertNotEqual(phone._rhmi_state, "SAS_AUTHENTICATED")
        self.assertFalse(phone._bootstrap_reached)
        self.assertTrue(
            any(e.get("event") == "mybmw_bootstrap_blocked" for e in phone.events)
        )
        snap = phone.forensic_snapshot()
        self.assertEqual(snap["wait_class"], "ETCH_REPLY_EXCEPTION")
        self.assertEqual(snap["bootstrap_state"], "NOT_REACHED")
        # Must not have queued sas_login after reject
        self.assertFalse(
            any(
                e.get("event") == "mybmw_rpc_tx" and e.get("method") == "sas_login"
                for e in phone.events
            )
        )

    def test_t3_login_rejected(self):
        phone = self._phone()
        hu = self._hu()
        tx = [phone.session_init()]
        for _ in range(20):
            rx_all: list[bytes] = []
            for chunk in tx:
                rx_all.extend(hu.on_bytes(chunk))
            tx = []
            for chunk in rx_all:
                tx.extend(phone.on_bytes(chunk))
            if phone._auth_state == AUTH_LOGIN_SENT:
                break
            if not tx and phone.active:
                tx.extend(phone.drain_tx())
        self.assertEqual(phone._auth_state, AUTH_LOGIN_SENT)
        mid = phone._auth_login_mid
        self.assertIsNotNone(mid)
        # Drop any pending lab login-ok still in phone drain from HU race: inject reject
        ex = build_service_exception(
            error_code=2, detail="Client has not sent an app certificate yet."
        )
        body = encode_etch_packet(
            "_result_sas_login",
            {"_inReplyTo": int(mid), "_messageId": 9002, "result": ex},
        )
        phone.on_bytes(_etch_data(body, src=10))
        self.assertEqual(phone._auth_state, AUTH_LOGIN_REJECTED)
        self.assertFalse(phone._bootstrap_reached)
        self.assertNotEqual(phone._rhmi_state, "SAS_AUTHENTICATED")

    def test_t4_login_in_reply_mismatch(self):
        phone = self._phone()
        phone.handshake = {"version": 5, "instance_id": 14, "buffer_size": 0x4000}
        phone.active = True
        phone._auth_state = AUTH_LOGIN_SENT
        phone._auth_login_mid = 1002
        phone._etch_stage = "sas_login"
        # Positive VOID_OK but wrong mid
        body = build_sas_login_ok_payload(in_reply_to=9999, msg_id=50)
        phone.on_bytes(_etch_data(body, src=10))
        self.assertNotEqual(phone._auth_state, AUTH_AUTHENTICATED)
        self.assertTrue(
            any(
                e.get("event") == "mybmw_auth_unmatched"
                and e.get("wait_class") == "ETCH_REPLY_UNMATCHED"
                for e in phone.events
            )
        )
        self.assertFalse(phone._bootstrap_reached)

    def test_t5_login_sent_alone_is_not_authenticated(self):
        """Hard gate: sas_login TX must NEVER imply AUTHENTICATED."""
        phone = self._phone()
        phone.handshake = {"version": 5, "instance_id": 14, "buffer_size": 0x4000}
        phone.active = True
        phone._auth_state = AUTH_LOGIN_SENT
        phone._auth_login_mid = 1002
        phone._etch_stage = "sas_login"
        phone._rhmi_state = "ETCH_OPEN"
        # No HU reply yet — must stay LOGIN_SENT (Schein-AUTHENTICATED forbidden)
        self.assertEqual(phone._auth_state, AUTH_LOGIN_SENT)
        self.assertNotEqual(phone._auth_state, AUTH_AUTHENTICATED)
        self.assertNotEqual(phone._rhmi_state, "SAS_AUTHENTICATED")
        self.assertFalse(phone._bootstrap_reached)
        phone.on_bytes(b"")
        self.assertEqual(phone._auth_state, AUTH_LOGIN_SENT)
        self.assertFalse(phone._bootstrap_reached)
        # Only correlated positive HU reply may promote
        body = build_sas_login_ok_payload(in_reply_to=1002, msg_id=202)
        phone.on_bytes(_etch_data(body, src=10))
        self.assertEqual(phone._auth_state, AUTH_AUTHENTICATED)
        self.assertEqual(phone._rhmi_state, "SAS_AUTHENTICATED")
        self.assertTrue(phone._bootstrap_reached)

    def test_r5_setdata_service_exception_keeps_runtime(self):
        phone = self._phone()
        phone.handshake = {"version": 5, "instance_id": 14, "buffer_size": 0x4000}
        phone.active = True
        phone._auth_state = AUTH_AUTHENTICATED
        phone._rhmi_state = "RUNTIME_ACTIVE"
        phone._handles["rhmi_create"] = 12
        ex = build_service_exception(error_code=213, detail="SetData was not successful.")
        body = encode_etch_packet(
            "_result_rhmi_setData",
            {"_inReplyTo": 55, "_messageId": 56, "result": ex},
        )
        phone.on_bytes(_etch_data(body, src=10))
        self.assertEqual(phone._rhmi_state, "RUNTIME_ACTIVE")
        self.assertEqual(phone._auth_state, AUTH_AUTHENTICATED)
        se = [e for e in phone.events if e.get("event") == "mybmw_setdata_service_exception"]
        self.assertEqual(len(se), 1)
        self.assertEqual(se[0].get("errorCode"), 213)
        self.assertEqual(se[0].get("wait_class"), "ETCH_REPLY_EXCEPTION")

    def test_field_auth_probe_cert_reject_replay(self):
        """Abnahme: FIELD_AUTH_PROBE-style cert exception → never SAS_AUTHENTICATED."""
        phone = self._phone()
        hu = self._hu()
        tx = [phone.session_init()]
        for _ in range(15):
            rx_all: list[bytes] = []
            for chunk in tx:
                rx_all.extend(hu.on_bytes(chunk))
            tx = []
            for chunk in rx_all:
                tx.extend(phone.on_bytes(chunk))
            if phone._auth_cert_mid is not None:
                break
        mid = phone._auth_cert_mid
        self.assertIsNotNone(mid)
        # Structured SE matching the FIELD_AUTH_PROBE ASCII (correlated mid).
        ex = build_service_exception(
            error_code=1, detail="Certificate is invalid or expired."
        )
        body = encode_etch_packet(
            "_result_sas_certificate",
            {"_inReplyTo": int(mid), "_messageId": 1, "result": ex},
        )
        phone.on_bytes(_etch_data(body, src=10))
        self.assertEqual(phone._auth_state, AUTH_CERTIFICATE_REJECTED)
        self.assertNotEqual(phone._rhmi_state, "SAS_AUTHENTICATED")
        self.assertFalse(phone._bootstrap_reached)
        # Evidence file still documents the original Schein-PASS (pre-P1).
        evidence = ROOT / "docs/evidence/FIELD_AUTH_PROBE_20261118T061541Z/phone.jsonl"
        self.assertTrue(evidence.is_file())


class TestMenuUploadDeadGateRemoved(unittest.TestCase):
    def test_init_reentrancy_uses_rhmi_runtime_only(self):
        phone = PhoneClientSession(mybmw_sim=True)
        phone._auth_state = AUTH_AUTHENTICATED
        phone._handles = {
            "cds_create": 10,
            "am_create": 11,
            "rhmi_create": 12,
            "av_create": 13,
        }
        phone._rhmi_plan = []
        phone._rhmi_plan_i = 0
        phone._etch_stage = "apps"
        phone._queue_rhmi_initialize_and_runtime()
        self.assertEqual(phone._etch_stage, "rhmi_runtime")
        self.assertEqual(phone._rhmi_state, "RUNTIME_ACTIVE")
        # Second call is no-op (reentrancy)
        phone._queue_rhmi_initialize_and_runtime()
        menus = [e for e in phone.events if e.get("event") == "mybmw_menu_upload_queued"]
        self.assertEqual(len(menus), 1)


if __name__ == "__main__":
    unittest.main()
