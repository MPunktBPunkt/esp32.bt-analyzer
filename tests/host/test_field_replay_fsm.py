"""P2/P3: Field capture replay through d64ae81 AuthState (REPLAY FACT only)."""

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
    AUTH_LOGIN_REJECTED,
    RESULT_EXCEPTION,
    RESULT_VOID_OK,
    PhoneClientSession,
    classify_result,
)
from bcl_etch_stub import (  # noqa: E402
    build_sas_challenge_payload,
    build_sas_login_ok_payload,
    build_service_exception,
)
from bcl_framer import DEST_ETCH_DESK, build_synthetic_frame  # noqa: E402
from etch_codec import decode_etch_message, encode_etch_packet  # noqa: E402
from field_replay_fsm import replay_jsonl  # noqa: E402

AUTH_JSONL = ROOT / "docs/evidence/FIELD_AUTH_PROBE_20261118T061541Z/phone.jsonl"
DUMP_JSONL = ROOT / "docs/evidence/FIELD_DUMP_20261118T061746Z/bcl.jsonl"


def _data(body: bytes, src: int = 10) -> bytes:
    from bcl_dummy_hu import CMD_DATA

    return build_synthetic_frame(CMD_DATA, src, DEST_ETCH_DESK, body)


class TestFieldReplayClassify(unittest.TestCase):
    def test_auth_probe_pdu_classifications(self):
        self.assertTrue(AUTH_JSONL.is_file())
        done = None
        with AUTH_JSONL.open() as fh:
            for ln in fh:
                o = json.loads(ln)
                if o.get("event") == "phone_done":
                    done = o
                    break
        self.assertIsNotNone(done)
        frames = (done.get("classification") or {}).get("frames") or []
        etch = [f for f in frames if f.get("dest") == 4004 and f.get("payload_hex")]
        self.assertGreaterEqual(len(etch), 2)
        cert = decode_etch_message(bytes.fromhex(etch[0]["payload_hex"]))
        login = decode_etch_message(bytes.fromhex(etch[1]["payload_hex"]))
        self.assertEqual(classify_result(cert)["classification"], RESULT_EXCEPTION)
        self.assertEqual(classify_result(login)["classification"], RESULT_EXCEPTION)
        self.assertIn("invalid", str(classify_result(cert).get("error_text") or "").lower())


class TestFieldReplayFsm(unittest.TestCase):
    def test_auth_probe_ends_certificate_rejected(self):
        rep = replay_jsonl(AUTH_JSONL, correlate_mids=True)
        self.assertEqual(rep.auth["AuthState"], AUTH_CERTIFICATE_REJECTED)
        self.assertEqual(rep.bootstrap["BootstrapState"], "NOT_REACHED")
        self.assertEqual(rep.am["AmState"], "NOT_REACHED")
        self.assertEqual(rep.runtime["RuntimeState"], "NOT_REACHED")
        self.assertEqual(rep.meta.origin, "field")
        self.assertEqual(rep.meta.transport, "replay")
        self.assertEqual(rep.meta.epistemic_status, "field_measured")
        self.assertNotEqual(rep.meta.auth_verdict, "accepted")
        self.assertEqual(rep.meta.auth_verdict, "fsm_certificate_rejected")

    def test_dump_probe_also_certificate_rejected(self):
        if not DUMP_JSONL.is_file():
            self.skipTest("dump jsonl missing")
        rep = replay_jsonl(DUMP_JSONL, correlate_mids=True)
        self.assertEqual(rep.auth["AuthState"], AUTH_CERTIFICATE_REJECTED)
        self.assertEqual(rep.bootstrap["BootstrapState"], "NOT_REACHED")


class TestAuthMatrixReplay(unittest.TestCase):
    """P3 matrix: lab stub / field reject / mutations — REPLAY or LAB only."""

    def _phone_after_hs(self) -> PhoneClientSession:
        phone = PhoneClientSession(
            selectproto=4,
            wire_open5001=True,
            open_etch=True,
            etch_src=10,
            knock_payload="wire_v5",
            mybmw_sim=True,
        )
        from bcl_dummy_hu import CMD_HANDSHAKE

        phone.on_bytes(build_synthetic_frame(CMD_HANDSHAKE, 0, 0, bytes.fromhex("0005000e00004000")))
        phone.drain_tx()
        return phone

    def test_lab_stub_challenge_then_void_ok(self):
        phone = self._phone_after_hs()
        self.assertEqual(phone._auth_state, "CERTIFICATE_SENT")
        mid = phone._auth_cert_mid
        chal = build_sas_challenge_payload(
            challenge=b"\x11" * 16, in_reply_to=int(mid), msg_id=1
        )
        phone.on_bytes(_data(chal))
        phone.drain_tx()
        self.assertEqual(phone._auth_state, "LOGIN_SENT")
        login_mid = phone._auth_login_mid
        ok = build_sas_login_ok_payload(in_reply_to=int(login_mid), msg_id=2)
        phone.on_bytes(_data(ok))
        self.assertEqual(phone._auth_state, AUTH_AUTHENTICATED)
        self.assertTrue(phone._bootstrap_reached)

    def test_field_style_cert_exception(self):
        phone = self._phone_after_hs()
        mid = phone._auth_cert_mid
        ex = build_service_exception(detail="Certificate is invalid or expired.")
        body = encode_etch_packet(
            "_result_sas_certificate",
            {"_inReplyTo": int(mid), "_messageId": 1, "result": ex},
        )
        phone.on_bytes(_data(body))
        self.assertEqual(phone._auth_state, AUTH_CERTIFICATE_REJECTED)
        self.assertFalse(phone._bootstrap_reached)

    def test_login_exception_after_challenge(self):
        phone = self._phone_after_hs()
        mid = phone._auth_cert_mid
        chal = build_sas_challenge_payload(
            challenge=b"\x22" * 16, in_reply_to=int(mid), msg_id=1
        )
        phone.on_bytes(_data(chal))
        phone.drain_tx()
        login_mid = phone._auth_login_mid
        ex = build_service_exception(detail="Client has not sent an app certificate yet.")
        body = encode_etch_packet(
            "_result_sas_login",
            {"_inReplyTo": int(login_mid), "_messageId": 2, "result": ex},
        )
        phone.on_bytes(_data(body))
        self.assertEqual(phone._auth_state, AUTH_LOGIN_REJECTED)

    def test_mutated_challenge_still_needs_valid_login(self):
        """Challenge bytes altered — still CHALLENGE class; login void → AUTH (Lab)."""
        phone = self._phone_after_hs()
        mid = phone._auth_cert_mid
        chal = build_sas_challenge_payload(
            challenge=b"\xAA" * 16, in_reply_to=int(mid), msg_id=1
        )
        phone.on_bytes(_data(chal))
        phone.drain_tx()
        self.assertEqual(len(phone._challenge or b""), 16)
        self.assertEqual(phone._challenge, b"\xAA" * 16)
        ok = build_sas_login_ok_payload(in_reply_to=int(phone._auth_login_mid), msg_id=2)
        phone.on_bytes(_data(ok))
        self.assertEqual(phone._auth_state, AUTH_AUTHENTICATED)
        # Note: crypto binding not verified — REPLAY/LAB only, not FIELD PROTOCOL FACT.


if __name__ == "__main__":
    unittest.main()
