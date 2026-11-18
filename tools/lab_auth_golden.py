#!/usr/bin/env python3
"""Capture / validate LAB golden positive SAS auth sequence (byte-level).

Sequence frozen:
  TX sas_certificate → RX challenge → TX sas_login → RX VOID_OK login
  → AuthState AUTHENTICATED (correlated inReplyTo only)

Claim level: LAB fixture — comparison anchor for Field AUTHENTICATED wire,
never FIELD PROTOCOL ACCEPTANCE by itself.

Usage:
  PYTHONPATH=tools python3 tools/lab_auth_golden.py capture \\
    --out tools/fixtures/auth_golden_lab_stub_login_ok.json
  PYTHONPATH=tools python3 tools/lab_auth_golden.py validate \\
    --fixture tools/fixtures/auth_golden_lab_stub_login_ok.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from bcl_dummy_hu import (  # noqa: E402
    AUTH_AUTHENTICATED,
    AUTH_CERTIFICATE_SENT,
    AUTH_CHALLENGE_RECEIVED,
    AUTH_LOGIN_SENT,
    CMD_DATA,
    DummyHuSession,
    PhoneClientSession,
    classify_result,
)
from bcl_framer import DEST_ETCH_DESK, BclFramer, build_synthetic_frame  # noqa: E402
from etch_codec import decode_etch_message, encode_etch_packet  # noqa: E402

DEFAULT_FIXTURE = ROOT / "tools" / "fixtures" / "auth_golden_lab_stub_login_ok.json"


def _drive_freeze() -> tuple[PhoneClientSession, DummyHuSession, list[dict[str, Any]]]:
    phone = PhoneClientSession(
        selectproto=4,
        wire_open5001=True,
        open_etch=True,
        etch_src=10,
        knock_payload="wire_v5",
        mybmw_sim=True,
    )
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

    steps: list[dict[str, Any]] = []
    seen_rx: set[str] = set()
    phone_framer = BclFramer()

    orig_queue = phone._queue_rpc

    def queue_rpc(type_name: str, fields: dict) -> None:
        body = encode_etch_packet(type_name, fields)
        if type_name in ("sas_certificate", "sas_login"):
            frame = build_synthetic_frame(
                CMD_DATA, int(phone.etch_src), DEST_ETCH_DESK, body
            )
            steps.append(
                {
                    "step": f"{type_name}_tx",
                    "dir": "phone→hu",
                    "method": type_name,
                    "msg_id": fields.get("_messageId"),
                    "bcl_src": int(phone.etch_src),
                    "bcl_dest": DEST_ETCH_DESK,
                    "etch_body_len": len(body),
                    "etch_body_sha256": __import__("hashlib")
                    .sha256(body)
                    .hexdigest(),
                    "etch_body_hex": body.hex(),
                    "bcl_frame_hex": frame.hex(),
                    "auth_state_after_queue": None,  # filled below
                }
            )
        orig_queue(type_name, fields)
        if type_name == "sas_certificate":
            steps[-1]["auth_state_after_queue"] = AUTH_CERTIFICATE_SENT
        elif type_name == "sas_login":
            steps[-1]["auth_state_after_queue"] = AUTH_LOGIN_SENT

    phone._queue_rpc = queue_rpc  # type: ignore[method-assign]

    orig_on = phone.on_bytes

    def on_bytes(data: bytes) -> list[bytes]:
        # Capture Etch DATA payloads before session consumes them.
        feed = phone_framer.feed(data)
        for fr in feed.frames:
            if fr.cmd != CMD_DATA or not fr.payload:
                continue
            try:
                dec = decode_etch_message(fr.payload)
            except Exception:  # noqa: BLE001
                continue
            method = dec.get("method") or ""
            if method not in (
                "_result_sas_certificate",
                "_result_sas_login",
            ):
                continue
            key = f"{method}:{fr.payload.hex()}"
            if key in seen_rx:
                continue
            seen_rx.add(key)
            fields = dec.get("raw_fields") or {}
            cls = classify_result(dec)
            steps.append(
                {
                    "step": f"{method}_rx",
                    "dir": "hu→phone",
                    "method": method,
                    "msg_id": fields.get("_messageId"),
                    "in_reply_to": fields.get("_inReplyTo"),
                    "bcl_src": fr.src,
                    "bcl_dest": fr.dest,
                    "classification": cls.get("classification"),
                    "challenge_len": cls.get("result_len"),
                    "challenge_hex": (
                        bytes(cls["result"]).hex()
                        if cls.get("classification") == "CHALLENGE"
                        and isinstance(cls.get("result"), (bytes, bytearray))
                        else None
                    ),
                    "etch_body_len": len(fr.payload),
                    "etch_body_sha256": __import__("hashlib")
                    .sha256(fr.payload)
                    .hexdigest(),
                    "etch_body_hex": fr.payload.hex(),
                    "bcl_frame_hex": fr.raw.hex() if fr.raw else None,
                }
            )
        return orig_on(data)

    phone.on_bytes = on_bytes  # type: ignore[method-assign]

    tx = [phone.session_init()]
    for _ in range(120):
        if phone._auth_state == AUTH_AUTHENTICATED:
            break
        rx_all: list[bytes] = []
        for chunk in tx:
            rx_all.extend(hu.on_bytes(chunk))
        tx = []
        for chunk in rx_all:
            tx.extend(phone.on_bytes(chunk))
        if not tx and phone.active:
            tx.append(phone.watchdog_ping())

    return phone, hu, steps


def build_fixture(steps: list[dict[str, Any]], phone: PhoneClientSession) -> dict[str, Any]:
    auth_steps = [
        s
        for s in steps
        if s.get("method")
        in (
            "sas_certificate",
            "sas_login",
            "_result_sas_certificate",
            "_result_sas_login",
        )
    ]
    transitions = []
    for e in phone.events:
        if e.get("event") == "mybmw_auth_state":
            transitions.append(
                {
                    "auth_state": e.get("auth_state"),
                    "msg_id": e.get("msg_id"),
                    "classification": e.get("classification"),
                }
            )
    return {
        "claim_level": "LAB",
        "fixture": "auth_golden_lab_stub_login_ok",
        "note": (
            "Positive LAB stub SAS sequence — byte anchor for Field AUTHENTICATED "
            "comparison. Not FIELD PROTOCOL ACCEPTANCE."
        ),
        "required_auth_transitions": [
            AUTH_CERTIFICATE_SENT,
            AUTH_CHALLENGE_RECEIVED,
            AUTH_LOGIN_SENT,
            AUTH_AUTHENTICATED,
        ],
        "final_auth_state": phone._auth_state,
        "cert_mid": phone._auth_cert_mid,
        "login_mid": phone._auth_login_mid,
        "auth_transitions_observed": transitions,
        "sequence": auth_steps,
        "freeze_snapshot": {
            **phone.forensic_snapshot(),
            "freeze_event": "AUTHENTICATED",
            "note": "golden capture freeze — no AM/RHMI/CDS continuation required",
        },
    }


def validate_fixture(fixture: dict[str, Any]) -> list[str]:
    """Return list of errors (empty = OK)."""
    errs: list[str] = []
    if fixture.get("final_auth_state") != AUTH_AUTHENTICATED:
        errs.append(f"final_auth_state={fixture.get('final_auth_state')}")
    seq = fixture.get("sequence") or []
    methods = [s.get("method") for s in seq]
    for need in (
        "sas_certificate",
        "_result_sas_certificate",
        "sas_login",
        "_result_sas_login",
    ):
        if need not in methods:
            errs.append(f"missing step {need}")
    # Correlation: login OK inReplyTo == login TX msg_id
    login_tx = next((s for s in seq if s.get("method") == "sas_login"), None)
    login_rx = next((s for s in seq if s.get("method") == "_result_sas_login"), None)
    if login_tx and login_rx:
        if login_rx.get("in_reply_to") != login_tx.get("msg_id"):
            errs.append(
                f"login inReplyTo={login_rx.get('in_reply_to')} "
                f"!= login msg_id={login_tx.get('msg_id')}"
            )
        if login_rx.get("classification") not in ("VOID_OK", "OK_INT"):
            errs.append(f"login classification={login_rx.get('classification')}")
    cert_tx = next((s for s in seq if s.get("method") == "sas_certificate"), None)
    cert_rx = next(
        (s for s in seq if s.get("method") == "_result_sas_certificate"), None
    )
    if cert_tx and cert_rx:
        if cert_rx.get("in_reply_to") != cert_tx.get("msg_id"):
            errs.append("challenge inReplyTo mismatch vs sas_certificate msg_id")
        if cert_rx.get("classification") != "CHALLENGE":
            errs.append(f"cert result class={cert_rx.get('classification')}")
    # Re-capture must still AUTHENTICATE
    phone, _, _ = _drive_freeze()
    if phone._auth_state != AUTH_AUTHENTICATED:
        errs.append("live re-drive did not reach AUTHENTICATED")
    return errs


def cmd_capture(out: Path) -> int:
    phone, _hu, steps = _drive_freeze()
    if phone._auth_state != AUTH_AUTHENTICATED:
        print("FAIL: did not reach AUTHENTICATED", phone._auth_state)
        return 1
    fixture = build_fixture(steps, phone)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(fixture, indent=2) + "\n")
    print(f"wrote {out} steps={len(fixture['sequence'])}")
    return 0


def cmd_validate(fixture_path: Path) -> int:
    fixture = json.loads(fixture_path.read_text())
    errs = validate_fixture(fixture)
    if errs:
        print("FAIL")
        for e in errs:
            print(" -", e)
        return 1
    print("PASS golden fixture + live re-drive AUTHENTICATED")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("capture")
    c.add_argument("--out", type=Path, default=DEFAULT_FIXTURE)
    v = sub.add_parser("validate")
    v.add_argument("--fixture", type=Path, default=DEFAULT_FIXTURE)
    args = ap.parse_args()
    if args.cmd == "capture":
        return cmd_capture(args.out)
    return cmd_validate(args.fixture)


if __name__ == "__main__":
    raise SystemExit(main())
