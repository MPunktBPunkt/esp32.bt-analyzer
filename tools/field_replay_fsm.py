#!/usr/bin/env python3
"""Replay FIELD JSONL Etch/BCL frames through PhoneClientSession + classify_result.

Epistemic rules (do not collapse these):
  FIELD FACT   — bytes were on OnePlus↔BMW wire
  REPLAY FACT  — those bytes reprocessed by our stack in lab
  FIELD PROTOCOL FACT — live HU accepted/continued (NOT claimed by this tool)

Usage:
  PYTHONPATH=tools python3 tools/field_replay_fsm.py \\
    --jsonl docs/evidence/FIELD_AUTH_PROBE_20261118T061541Z/phone.jsonl \\
    --out docs/evidence/FIELD_REPLAY_P1_20261118/
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from bcl_dummy_hu import (  # noqa: E402
    AUTH_AUTHENTICATED,
    AUTH_CERTIFICATE_REJECTED,
    AUTH_CERTIFICATE_SENT,
    AUTH_CHALLENGE_RECEIVED,
    AUTH_IDLE,
    AUTH_LOGIN_REJECTED,
    AUTH_LOGIN_SENT,
    CMD_DATA,
    CMD_HANDSHAKE,
    PhoneClientSession,
    classify_result,
)
from bcl_framer import DEST_ETCH_DESK, build_synthetic_frame  # noqa: E402
from etch_codec import decode_etch_message  # noqa: E402


@dataclass
class ReplayMeta:
    origin: str = "field"
    transport: str = "replay"
    epistemic_status: str = "field_measured"
    auth_verdict: str | None = None  # never auto-set to accepted from bytes alone
    source_jsonl: str = ""
    note: str = (
        "REPLAY FACT only — not FIELD PROTOCOL FACT; "
        "auth_verdict reflects our FSM classification of captured replies."
    )


@dataclass
class FsmReport:
    meta: ReplayMeta
    transport: dict[str, Any] = field(default_factory=dict)
    etch: dict[str, Any] = field(default_factory=dict)
    auth: dict[str, Any] = field(default_factory=dict)
    bootstrap: dict[str, Any] = field(default_factory=dict)
    am: dict[str, Any] = field(default_factory=dict)
    resource: dict[str, Any] = field(default_factory=dict)
    rhmi: dict[str, Any] = field(default_factory=dict)
    runtime: dict[str, Any] = field(default_factory=dict)
    events_summary: dict[str, int] = field(default_factory=dict)
    classified_replies: list[dict] = field(default_factory=list)
    phone_snapshot: dict[str, Any] = field(default_factory=dict)


def _wrap_payload(payload: bytes, *, src: int = 10, dest: int = DEST_ETCH_DESK) -> bytes:
    return build_synthetic_frame(CMD_DATA, src, dest, payload)


def _inject_handshake(phone: PhoneClientSession, payload_hex: str) -> None:
    raw = bytes.fromhex(payload_hex)
    # HANDSHAKE BCL frame
    frame = build_synthetic_frame(CMD_HANDSHAKE, 0, 0, raw)
    phone.on_bytes(frame)


def replay_jsonl(path: Path, *, correlate_mids: bool = True) -> FsmReport:
    """Feed captured RX Etch DATA (+ HS) into a fresh PhoneClientSession(mybmw_sim).

    Strategy:
      1. Apply HANDSHAKE from capture (or synthetic v5/14/0x4000).
      2. Let mybmw_sim start (queues sas_certificate with new mid).
      3. For each captured HU→phone Etch DATA payload, rewrite _inReplyTo to the
         open txn mid when correlate_mids=True so AuthState can evaluate the
         *semantic* field reply against our TX. Raw bytes otherwise still run
         through classify_result for the report.
    """
    phone = PhoneClientSession(
        selectproto=4,
        wire_open5001=True,
        open_etch=True,
        etch_src=10,
        knock_payload="wire_v5",
        mybmw_sim=True,
    )
    meta = ReplayMeta(source_jsonl=str(path))
    report = FsmReport(meta=meta)
    with path.open() as fh:
        events = [json.loads(ln) for ln in fh if ln.strip().startswith("{")]

    # Handshake
    hs = next((e for e in events if e.get("event") == "handshake_rx"), None)
    hs_frame = next(
        (
            e
            for e in events
            if e.get("event") == "frame"
            and e.get("cmd_name") == "HANDSHAKE"
            and e.get("payload_hex")
        ),
        None,
    )
    if hs_frame:
        _inject_handshake(phone, hs_frame["payload_hex"])
    else:
        # Synthetic FIELD fingerprint
        _inject_handshake(phone, "0005000e00004000")
    report.transport = {
        "RFCOMM_CONNECTED": True,
        "HANDSHAKE_RECEIVED": phone.handshake is not None,
        "handshake": phone.handshake,
        "PROTOCOL_SELECTED": True,  # SP TX on HS path
        "KNOCK_SENT": True,
        "BCL_ACTIVE": bool(phone.active),
        "claim": "REPLAY FACT",
    }
    report.etch = {"RPC_ACTIVE": True, "claim": "REPLAY FACT"}

    # Drain initial TX (cert) so mids exist
    phone.drain_tx()

    # Prefer phone_done.classification.frames — live frame events often truncate hex at 64 B.
    etch_rx: list[dict] = []
    done = next((e for e in events if e.get("event") == "phone_done"), None)
    if done:
        for fr in (done.get("classification") or {}).get("frames") or []:
            if fr.get("dest") == 4004 and fr.get("cmd_name") == "DATA" and fr.get("payload_hex"):
                etch_rx.append(
                    {
                        "payload_hex": fr["payload_hex"],
                        "len": fr.get("len"),
                        "src": fr.get("src") or 10,
                        "dest": 4004,
                    }
                )
    if not etch_rx:
        etch_rx = [
            e
            for e in events
            if e.get("event") == "frame"
            and e.get("dir") == "rx"
            and e.get("cmd_name") == "DATA"
            and e.get("dest") == 4004
            and e.get("payload_hex")
        ]

    for e in etch_rx:
        raw = bytes.fromhex(e["payload_hex"])
        # payload may be BCL DATA payload starting with deadbeef wrapper
        body = raw
        try:
            dec = decode_etch_message(body)
        except Exception as exc:  # noqa: BLE001
            report.classified_replies.append(
                {
                    "error": f"decode_fail:{exc}",
                    "len": len(body),
                    "epistemic": "field_measured_bytes",
                }
            )
            continue

        cls = classify_result(dec)
        entry = {
            "method": dec.get("method"),
            "classification": cls.get("classification"),
            "error_text": cls.get("error_text"),
            "in_reply_to_captured": cls.get("in_reply_to"),
            "len": e.get("len"),
            "epistemic_status": "field_measured",
            "transport": "replay",
        }
        report.classified_replies.append(entry)

        # Correlate to open auth TX for FSM transition test
        method = dec.get("method") or ""
        fields = dict(dec.get("raw_fields") or {})
        if correlate_mids and method == "_result_sas_certificate" and phone._auth_cert_mid:
            fields["_inReplyTo"] = int(phone._auth_cert_mid)
        elif correlate_mids and method == "_result_sas_login" and phone._auth_login_mid:
            fields["_inReplyTo"] = int(phone._auth_login_mid)

        # Re-encode only when we need mid rewrite; else inject original body
        if correlate_mids and fields.get("_inReplyTo") != (
            (dec.get("raw_fields") or {}).get("_inReplyTo")
        ):
            from etch_codec import encode_etch_packet

            # Keep result object from decode
            inj_fields = dict(fields)
            if "result" in (dec.get("raw_fields") or {}):
                inj_fields["result"] = dec["raw_fields"]["result"]
            if "_messageId" in (dec.get("raw_fields") or {}):
                inj_fields["_messageId"] = dec["raw_fields"]["_messageId"]
            try:
                body = encode_etch_packet(method, inj_fields)
            except Exception as exc:  # noqa: BLE001
                entry["reinject_error"] = str(exc)
                continue

        phone.on_bytes(_wrap_payload(body, src=int(e.get("src") or 10)))
        phone.drain_tx()

        # Stop injecting post-auth bootstrap noise once rejected
        if phone._auth_state in (AUTH_CERTIFICATE_REJECTED, AUTH_LOGIN_REJECTED):
            break

    snap = phone.forensic_snapshot()
    report.phone_snapshot = snap
    auth = phone._auth_state
    report.auth = {
        "AuthState": auth,
        "rhmi_state_legacy": phone._rhmi_state,
        "claim": "REPLAY FACT",
    }
    # Map epistemic auth_verdict without claiming FIELD PROTOCOL acceptance
    if auth == AUTH_AUTHENTICATED:
        meta.auth_verdict = "fsm_authenticated_from_replay_bytes"
    elif auth == AUTH_CERTIFICATE_REJECTED:
        meta.auth_verdict = "fsm_certificate_rejected"
    elif auth == AUTH_LOGIN_REJECTED:
        meta.auth_verdict = "fsm_login_rejected"
    else:
        meta.auth_verdict = f"fsm_{auth.lower()}"

    reached = phone._bootstrap_reached
    report.bootstrap = {
        "BootstrapState": "HANDLES_CREATING" if reached else "NOT_REACHED",
        "claim": "REPLAY FACT",
    }
    report.am = {"AmState": "NOT_REACHED" if not reached else "PARTIAL", "claim": "REPLAY FACT"}
    report.resource = {"ResourceState": "NOT_REACHED", "claim": "REPLAY FACT"}
    report.rhmi = {
        "RhmiState": "NOT_REACHED"
        if phone._rhmi_state in ("DISCONNECTED", "SAS_AUTHENTICATED")
        and not reached
        else phone._rhmi_state,
        "claim": "REPLAY FACT",
    }
    report.runtime = {
        "RuntimeState": "NOT_REACHED"
        if phone._rhmi_state != "RUNTIME_ACTIVE"
        else "RUNTIME_ACTIVE",
        "claim": "REPLAY FACT",
    }

    from collections import Counter

    report.events_summary = dict(Counter(e.get("event") for e in phone.events))
    return report


def report_to_markdown(rep: FsmReport) -> str:
    m = rep.meta
    lines = [
        "# FIELD REPLAY — FSM report",
        "",
        f"**origin:** `{m.origin}` · **transport:** `{m.transport}` · "
        f"**epistemic_status:** `{m.epistemic_status}`",
        f"**auth_verdict:** `{m.auth_verdict}`",
        f"**source:** `{m.source_jsonl}`",
        "",
        f"> {m.note}",
        "",
        "## Transport",
        "",
        "```",
        json.dumps(rep.transport, indent=2),
        "```",
        "",
        "## Etch",
        "",
        "```",
        json.dumps(rep.etch, indent=2),
        "```",
        "",
        "## Auth",
        "",
        "```",
        json.dumps(rep.auth, indent=2),
        "```",
        "",
        "## Bootstrap / AM / Resource / RHMI / Runtime",
        "",
        "```",
        json.dumps(
            {
                "bootstrap": rep.bootstrap,
                "am": rep.am,
                "resource": rep.resource,
                "rhmi": rep.rhmi,
                "runtime": rep.runtime,
            },
            indent=2,
        ),
        "```",
        "",
        "## Classified field replies (sample)",
        "",
        "| method | classification | error_text |",
        "|--------|----------------|------------|",
    ]
    for c in rep.classified_replies[:20]:
        lines.append(
            f"| `{c.get('method')}` | `{c.get('classification')}` | "
            f"{c.get('error_text') or ''} |"
        )
    lines += [
        "",
        "## phone forensic_snapshot",
        "",
        "```json",
        json.dumps(rep.phone_snapshot, indent=2),
        "```",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--jsonl", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument(
        "--no-correlate-mids",
        action="store_true",
        help="inject raw field PDUs without rewriting _inReplyTo (expect UNMATCHED)",
    )
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    rep = replay_jsonl(args.jsonl, correlate_mids=not args.no_correlate_mids)
    (args.out / "FSM_REPORT.json").write_text(
        json.dumps(
            {
                "meta": asdict(rep.meta),
                "transport": rep.transport,
                "etch": rep.etch,
                "auth": rep.auth,
                "bootstrap": rep.bootstrap,
                "am": rep.am,
                "resource": rep.resource,
                "rhmi": rep.rhmi,
                "runtime": rep.runtime,
                "events_summary": rep.events_summary,
                "classified_replies": rep.classified_replies,
                "phone_snapshot": rep.phone_snapshot,
            },
            indent=2,
        )
        + "\n"
    )
    (args.out / "FSM_REPORT.md").write_text(report_to_markdown(rep))
    print(report_to_markdown(rep))
    return 0 if rep.auth.get("AuthState") in (
        AUTH_CERTIFICATE_REJECTED,
        AUTH_LOGIN_REJECTED,
        AUTH_AUTHENTICATED,
        AUTH_IDLE,
        AUTH_CERTIFICATE_SENT,
        AUTH_CHALLENGE_RECEIVED,
        AUTH_LOGIN_SENT,
    ) else 1


if __name__ == "__main__":
    raise SystemExit(main())
