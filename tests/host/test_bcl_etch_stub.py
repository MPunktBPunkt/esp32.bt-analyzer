import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))

from bcl_etch_stub import (  # noqa: E402
    CDS_STUB_VALUES,
    EtchChannelReassembler,
    EtchSasCdsStub,
    ETCH_MAGIC,
    build_sas_challenge_payload,
    wrap_etch_body,
)


class TestEtchEnvelope(unittest.TestCase):
    def test_wrap_roundtrip_len(self):
        body = b"abc"
        msg = wrap_etch_body(body)
        self.assertEqual(msg[:4], ETCH_MAGIC)
        self.assertEqual(int.from_bytes(msg[4:8], "big"), 3)
        self.assertEqual(msg[8:], body)

    def test_challenge_payload_16(self):
        msg = build_sas_challenge_payload(bytes(range(16)))
        self.assertTrue(msg.startswith(ETCH_MAGIC))
        self.assertIn(bytes(range(16)), msg)


class TestReassembler(unittest.TestCase):
    def test_fragmented(self):
        body = b"X" * 100
        full = wrap_etch_body(body)
        ra = EtchChannelReassembler()
        self.assertEqual(ra.feed(full[:20]), [])
        msgs = ra.feed(full[20:])
        self.assertEqual(len(msgs), 1)
        self.assertEqual(msgs[0], full)


class TestSasCdsStub(unittest.TestCase):
    def test_pkcs7_triggers_challenge(self):
        stub = EtchSasCdsStub()
        pem = b"-----BEGIN PKCS7-----\nMIIB\n-----END PKCS7-----\n"
        msg = wrap_etch_body(b"\x00" * 16 + pem + b"\x00")
        # fragmented
        mid = len(msg) // 2
        self.assertEqual(stub.on_etch_data(10, msg[:mid]), [])
        replies = stub.on_etch_data(10, msg[mid:])
        self.assertEqual(len(replies), 1)
        self.assertEqual(stub.certs_seen, 1)
        self.assertEqual(stub.challenges_sent, 1)
        self.assertTrue(any(e["event"] == "sas_challenge_tx" for e in stub.events))

    def test_cds_property_string(self):
        stub = EtchSasCdsStub()
        stub.challenges_sent = 1  # already past cert
        name = "engine.temperature"
        msg = wrap_etch_body(b"pad" + name.encode() + b"more")
        replies = stub.on_etch_data(12, msg)
        self.assertEqual(len(replies), 1)
        self.assertIn(name, stub.cds_hits)
        self.assertIn(CDS_STUB_VALUES[name].encode(), replies[0])

    def test_login_after_challenge(self):
        stub = EtchSasCdsStub()
        stub.challenges_sent = 1
        msg = wrap_etch_body(b"Z" * 40)
        replies = stub.on_etch_data(10, msg)
        self.assertEqual(len(replies), 1)
        self.assertEqual(stub.logins_seen, 1)


if __name__ == "__main__":
    unittest.main()
