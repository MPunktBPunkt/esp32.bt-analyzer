#!/usr/bin/env python3
"""Auth A/B matrix for the APP/APP_AUTH acceptance gate (lab + replay).

Arms (epistemic tags preserved):
  A  LABSIM_REJECT     — cert ServiceException → CERTIFICATE_REJECTED   (LAB)
  B  LAB_STUB_ACCEPT   — f20_sim challenge+VOID_OK → AUTHENTICATED      (LAB)
     + optional freeze: capture snapshot and do NOT continue bootstrap TX
  C  FIELD_REPLAY      — FIELD_AUTH_PROBE JSONL → CERTIFICATE_REJECTED  (REPLAY)

Never claims FIELD PROTOCOL ACCEPTANCE. Never forges BMW signatures.

Usage:
  PYTHONPATH=tools python3 tools/lab_auth_ab_matrix.py \\
    --out docs/evidence/LAB_AUTH_AB_GATE_<stamp>/
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from bcl_dummy_hu import (  # noqa: E402
    AUTH_AUTHENTICATED,
    AUTH_CERTIFICATE_REJECTED,
    CMD_DATA,
    DummyHuSession,
    PhoneClientSession,
)
from bcl_etch_stub import build_service_exception  # noqa: E402
from bcl_framer import DEST_ETCH_DESK, build_synthetic_frame  # noqa: E402
from etch_codec import encode_etch_packet  # noqa: E402
from field_replay_fsm import replay_jsonl  # noqa: E402


DEFAULT_FIELD_JSONL = (
    ROOT
    / "docs/evidence/FIELD_AUTH_PROBE_20261118T061541Z/phone.jsonl"
)


@dataclass
class ArmResult:
    arm: str
    claim_level: str
    expected_auth: str
    auth_state: str
    bootstrap_state: str
    rhmi_state: str
    wait_class: str | None
    last_exception_text: str | None
    freeze_snapshot: dict[str, Any] = field(default_factory=dict)
    continued_past_auth: bool = False
    pass_: bool = False
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["pass"] = d.pop("pass_")
        return d


def _etch_data(body: bytes, *, src: int = 10) -> bytes:
    return build_synthetic_frame(CMD_DATA, src, DEST_ETCH_DESK, body)


def run_arm_a_reject() -> ArmResult:
    from bcl_dummy_hu import AUTH_CERTIFICATE_SENT

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
    # Reach CERTIFICATE_SENT then inject field-style reject (same pattern as T2)
    tx = [phone.session_init()]
    for _ in range(40):
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
    mid = getattr(phone, "_auth_cert_mid", None)
    if mid is not None:
        ex = build_service_exception(
            error_code=1, detail="Certificate is invalid or expired."
        )
        body = encode_etch_packet(
            "_result_sas_certificate",
            {"_messageId": 9001, "_inReplyTo": int(mid), "result": ex},
        )
        phone.on_bytes(_etch_data(body))

    snap = phone.forensic_snapshot()
    ok = snap.get("auth_state") == AUTH_CERTIFICATE_REJECTED and snap.get(
        "bootstrap_state"
    ) == "NOT_REACHED"
    return ArmResult(
        arm="A_LABSIM_REJECT",
        claim_level="LAB",
        expected_auth=AUTH_CERTIFICATE_REJECTED,
        auth_state=str(snap.get("auth_state")),
        bootstrap_state=str(snap.get("bootstrap_state")),
        rhmi_state=str(snap.get("rhmi_state")),
        wait_class=snap.get("wait_class"),
        last_exception_text=snap.get("last_exception_text"),
        freeze_snapshot=snap,
        continued_past_auth=False,
        pass_=ok,
        notes="Simulates FIELD-style cert reject; bootstrap must stay NOT_REACHED",
    )


def run_arm_b_accept(*, freeze: bool) -> ArmResult:
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
    continued = False
    freeze_snap: dict[str, Any] = {}
    tx = [phone.session_init()]
    for _ in range(120):
        if freeze and phone._auth_state == AUTH_AUTHENTICATED:
            freeze_snap = phone.forensic_snapshot()
            freeze_snap["freeze_event"] = "AUTHENTICATED"
            freeze_snap["note"] = (
                "LAB freeze — no further bootstrap drain after positive login"
            )
            break
        rx_all: list[bytes] = []
        for chunk in tx:
            rx_all.extend(hu.on_bytes(chunk))
        tx = []
        for chunk in rx_all:
            tx.extend(phone.on_bytes(chunk))
        if phone._auth_state == AUTH_AUTHENTICATED and not freeze:
            continued = True
            if phone._bootstrap_reached and not tx:
                break
        if not tx and phone.active:
            tx.append(phone.watchdog_ping())

    snap = freeze_snap or phone.forensic_snapshot()
    auth_ok = snap.get("auth_state") == AUTH_AUTHENTICATED
    if freeze:
        # Must not have started bootstrap handles yet (or at most early)
        boot_ok = snap.get("bootstrap_state") in ("NOT_REACHED", "HANDLES_CREATING")
        # Prefer NOT_REACHED when we freeze immediately
        ok = auth_ok and not continued
        notes = "Freeze on AUTHENTICATED — causal snapshot before AM/RHMI"
    else:
        ok = auth_ok and snap.get("bootstrap_state") == "HANDLES_READY"
        notes = "Full lab stub path to handles (not Field acceptance)"
    return ArmResult(
        arm="B_LAB_STUB_ACCEPT_FREEZE" if freeze else "B_LAB_STUB_ACCEPT_FULL",
        claim_level="LAB",
        expected_auth=AUTH_AUTHENTICATED,
        auth_state=str(snap.get("auth_state")),
        bootstrap_state=str(snap.get("bootstrap_state")),
        rhmi_state=str(snap.get("rhmi_state")),
        wait_class=snap.get("wait_class"),
        last_exception_text=snap.get("last_exception_text"),
        freeze_snapshot=snap,
        continued_past_auth=continued,
        pass_=ok and boot_ok if freeze else ok,
        notes=notes,
    )


def run_arm_c_field_replay(jsonl: Path) -> ArmResult:
    if not jsonl.is_file():
        return ArmResult(
            arm="C_FIELD_REPLAY",
            claim_level="REPLAY",
            expected_auth=AUTH_CERTIFICATE_REJECTED,
            auth_state="MISSING_CAPTURE",
            bootstrap_state="NOT_REACHED",
            rhmi_state="DISCONNECTED",
            wait_class=None,
            last_exception_text=None,
            pass_=False,
            notes=f"missing {jsonl}",
        )
    rep = replay_jsonl(jsonl, correlate_mids=True)
    auth = str(rep.auth.get("AuthState"))
    boot = str(rep.bootstrap.get("BootstrapState"))
    ok = auth == AUTH_CERTIFICATE_REJECTED and boot == "NOT_REACHED"
    return ArmResult(
        arm="C_FIELD_REPLAY",
        claim_level="REPLAY",
        expected_auth=AUTH_CERTIFICATE_REJECTED,
        auth_state=auth,
        bootstrap_state=boot,
        rhmi_state=str(rep.rhmi.get("RhmiState")),
        wait_class=(rep.phone_snapshot or {}).get("wait_class"),
        last_exception_text=(rep.phone_snapshot or {}).get("last_exception_text"),
        freeze_snapshot=rep.phone_snapshot or {},
        continued_past_auth=False,
        pass_=ok,
        notes="FIELD MEASURED bytes → REPLAY FACT only; not FIELD ACCEPTANCE",
    )


def run_matrix(*, field_jsonl: Path) -> list[ArmResult]:
    return [
        run_arm_a_reject(),
        run_arm_b_accept(freeze=True),
        run_arm_b_accept(freeze=False),
        run_arm_c_field_replay(field_jsonl),
    ]


def to_markdown(results: list[ArmResult], *, stamp: str) -> str:
    lines = [
        f"# LAB Auth A/B Gate Matrix — {stamp}",
        "",
        "Claim levels: **LAB** / **REPLAY**. Never FIELD PROTOCOL ACCEPTANCE.",
        "",
        "| Arm | Level | Expected | AuthState | Bootstrap | Pass |",
        "|-----|-------|----------|-----------|-----------|------|",
    ]
    for r in results:
        lines.append(
            f"| `{r.arm}` | {r.claim_level} | `{r.expected_auth}` | "
            f"`{r.auth_state}` | `{r.bootstrap_state}` | "
            f"{'PASS' if r.pass_ else 'FAIL'} |"
        )
    lines += [
        "",
        "## Gate reminder",
        "",
        "```text",
        "SAS challenge  ✅",
        "       │",
        "       ▼",
        "APP / APP_AUTH acceptance  ← next Field variable",
        "```",
        "",
        "## Notes",
        "",
    ]
    for r in results:
        lines.append(f"- **{r.arm}:** {r.notes}")
        if r.last_exception_text:
            lines.append(f"  - exception: `{r.last_exception_text}`")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--out",
        type=Path,
        default=None,
        help="evidence directory (default docs/evidence/LAB_AUTH_AB_GATE_<UTC>/)",
    )
    ap.add_argument(
        "--field-jsonl",
        type=Path,
        default=DEFAULT_FIELD_JSONL,
        help="FIELD_AUTH_PROBE phone.jsonl for arm C",
    )
    args = ap.parse_args()
    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    out = args.out or (ROOT / "docs/evidence" / f"LAB_AUTH_AB_GATE_{stamp}")
    out.mkdir(parents=True, exist_ok=True)

    results = run_matrix(field_jsonl=args.field_jsonl)
    payload = {
        "stamp": stamp,
        "gate": "APP_APP_AUTH_ACCEPTANCE",
        "arms": [r.to_dict() for r in results],
        "all_pass": all(r.pass_ for r in results),
    }
    (out / "MATRIX.json").write_text(json.dumps(payload, indent=2) + "\n")
    (out / "SUMMARY.md").write_text(to_markdown(results, stamp=stamp))
    # Persist freeze snapshot from arm B freeze
    for r in results:
        if r.arm == "B_LAB_STUB_ACCEPT_FREEZE" and r.freeze_snapshot:
            (out / "AUTHENTICATED_SNAPSHOT.json").write_text(
                json.dumps(r.freeze_snapshot, indent=2) + "\n"
            )
    # Refresh byte-level golden positive login sequence (LAB anchor)
    try:
        from lab_auth_golden import build_fixture, _drive_freeze

        phone, _hu, steps = _drive_freeze()
        golden = build_fixture(steps, phone)
        (out / "AUTH_GOLDEN_SEQUENCE.json").write_text(
            json.dumps(golden, indent=2) + "\n"
        )
        fixture_path = ROOT / "tools" / "fixtures" / "auth_golden_lab_stub_login_ok.json"
        fixture_path.parent.mkdir(parents=True, exist_ok=True)
        fixture_path.write_text(json.dumps(golden, indent=2) + "\n")
    except Exception as exc:  # noqa: BLE001
        print(f"golden capture skipped: {exc!r}")
    print(to_markdown(results, stamp=stamp))
    print(f"wrote {out}")
    return 0 if payload["all_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
