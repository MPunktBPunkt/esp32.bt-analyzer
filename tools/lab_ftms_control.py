#!/usr/bin/env python3
"""P0 — FTMS Control Point matrix (2AD9 Write → Indication).

Opcodes exercised against ESP stub: Request Control, Reset, Start/Resume,
Stop/Pause, Set Resistance, Set Power, invalid opcode, write without CCCD.

Claim: STIMULUS · Success ≠ Wirkung.

Usage:
  python3 tools/lab_ftms_control.py
"""

from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "docs" / "evidence"


def get(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=8) as r:
        return json.loads(r.read().decode())


def post(url: str, fields: dict | None = None) -> dict:
    data = urllib.parse.urlencode(fields or {}).encode()
    req = urllib.request.Request(url, data=data, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=12) as r:
            body = r.read().decode()
            try:
                return json.loads(body) if body else {"ok": True}
            except json.JSONDecodeError:
                return {"raw": body}
    except urllib.error.HTTPError as exc:
        body = exc.read().decode(errors="replace")
        try:
            j = json.loads(body) if body else {}
        except json.JSONDecodeError:
            j = {"raw": body}
        j["ok"] = False
        j["http_status"] = exc.code
        return j
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc)}


def quiet(*ips: str) -> None:
    for ip in ips:
        for p in ("disconnect", "advertise/stop", "scan/stop", "throughput/stop"):
            post(f"http://{ip}/api/bt/{p}")


def wait_ftms_ready(host: str, timeout: float = 15.0) -> dict:
    t0 = time.time()
    while time.time() - t0 < timeout:
        ft = get(f"http://{host}/api/status").get("ftms") or {}
        if ft.get("state") == "ready" and int(ft.get("notifies") or 0) >= 1:
            return ft
        if ft.get("state") == "error":
            return ft
        time.sleep(0.25)
    return get(f"http://{host}/api/status").get("ftms") or {}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--analyzer", default="192.168.178.88")
    ap.add_argument("--peer", default="192.168.178.89")
    args = ap.parse_args()
    utc = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    EVIDENCE.mkdir(parents=True, exist_ok=True)

    quiet(args.analyzer, args.peer)
    time.sleep(0.4)
    bd = ((get(f"http://{args.peer}/api/status").get("onchip") or {}).get("bdAddr") or "").lower()
    post(f"http://{args.peer}/api/bt/advertise/start", {"name": "ftms-cp", "hid": "1", "ftms": "1"})
    time.sleep(0.7)
    post(f"http://{args.analyzer}/api/bt/scan/start")
    time.sleep(3.0)
    post(f"http://{args.analyzer}/api/bt/scan/stop")
    post(f"http://{args.analyzer}/api/bt/connect", {"addr": bd, "addrType": "0"})
    for _ in range(40):
        if (get(f"http://{args.analyzer}/api/status").get("onchip") or {}).get("leConnected"):
            break
        time.sleep(0.25)

    post(f"http://{args.analyzer}/api/bt/flavor/gatt/discover", {"mtu": "247"})
    for _ in range(80):
        if (get(f"http://{args.analyzer}/api/status").get("flavor") or {}).get("state") == "ready":
            break
        time.sleep(0.25)
    post(f"http://{args.analyzer}/api/bt/flavor/ftms/start")
    ft0 = wait_ftms_ready(args.analyzer)

    cases = []

    def case(name: str, fn):
        before = int((get(f"http://{args.analyzer}/api/status").get("ftms") or {}).get("cpIndications") or 0)
        fn()
        time.sleep(1.0)  # deferred peer Indication via poll()
        ft = get(f"http://{args.analyzer}/api/status").get("ftms") or {}
        after = int(ft.get("cpIndications") or 0)
        cases.append(
            {
                "name": name,
                "ind_delta": after - before,
                "lastCpReq": ft.get("lastCpReq"),
                "lastCpResult": ft.get("lastCpResult"),
                "ok": None,  # filled below
            }
        )
        return cases[-1]

    # Enable CP CCCD (Indicate) and wait for Write Response settle
    post(f"http://{args.analyzer}/api/bt/flavor/ftms/control", {"enable": "1"})
    time.sleep(1.2)
    # Warm-up write (discard) — first indication after CCCD can race
    post(f"http://{args.analyzer}/api/bt/flavor/ftms/control", {"opcode": "0"})
    time.sleep(1.0)

    case("request_control", lambda: post(f"http://{args.analyzer}/api/bt/flavor/ftms/control", {"opcode": "0"}))
    case("reset", lambda: post(f"http://{args.analyzer}/api/bt/flavor/ftms/control", {"opcode": "1"}))
    case("start_resume", lambda: post(f"http://{args.analyzer}/api/bt/flavor/ftms/control", {"opcode": "7"}))
    case("stop_pause", lambda: post(f"http://{args.analyzer}/api/bt/flavor/ftms/control", {"opcode": "8"}))
    case(
        "set_resistance",
        lambda: post(f"http://{args.analyzer}/api/bt/flavor/ftms/control", {"opcode": "4", "payload": "6400"}),
    )
    case(
        "set_power",
        lambda: post(f"http://{args.analyzer}/api/bt/flavor/ftms/control", {"opcode": "5", "payload": "6400"}),
    )
    case("invalid_opcode", lambda: post(f"http://{args.analyzer}/api/bt/flavor/ftms/control", {"opcode": "63"}))

    # Expect: valid → result 1; invalid → result 2; each with ind_delta>=1
    expect = {
        "request_control": (0, 1),
        "reset": (1, 1),
        "start_resume": (7, 1),
        "stop_pause": (8, 1),
        "set_resistance": (4, 1),
        "set_power": (5, 1),
        "invalid_opcode": (0x3F, 2),
    }
    for c in cases:
        exp = expect.get(c["name"])
        if not exp:
            c["ok"] = False
            continue
        req, res = exp
        got_req = c.get("lastCpReq")
        got_res = c.get("lastCpResult")
        c["ok"] = (
            c["ind_delta"] >= 1
            and got_req is not None
            and got_res is not None
            and int(got_req) == req
            and int(got_res) == res
        )

    # Write without CCCD: disable then write — expect no new indication
    post(f"http://{args.analyzer}/api/bt/flavor/ftms/control", {"enable": "0"})
    time.sleep(0.4)
    before = int((get(f"http://{args.analyzer}/api/status").get("ftms") or {}).get("cpIndications") or 0)
    post(f"http://{args.analyzer}/api/bt/flavor/ftms/control", {"opcode": "0"})
    time.sleep(0.6)
    after = int((get(f"http://{args.analyzer}/api/status").get("ftms") or {}).get("cpIndications") or 0)
    no_cccd = {"name": "write_without_cccd", "ind_delta": after - before, "ok": after == before}
    cases.append(no_cccd)

    ok = ft0.get("state") == "ready" and all(c.get("ok") for c in cases)
    out = {
        "utc": utc,
        "gate": "FTMS_control_point",
        "claim": "STIMULUS_FTMS_CP_over_HCI_not_air",
        "success_ne_wirkung": True,
        "peer_bd": bd,
        "ftms_ready": ft0,
        "cases": cases,
        "ok": ok,
    }
    stem = f"LAB_FTMS_CONTROL_{utc}"
    (EVIDENCE / f"{stem}.json").write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    lines = [f"# LAB FTMS Control Point — {'PASS' if ok else 'FAIL'}", "", f"**UTC:** {utc}", "", "| case | ok | Δind | req | result |", "|------|----|------|-----|--------|"]
    for c in cases:
        lines.append(
            f"| {c['name']} | {c.get('ok')} | {c.get('ind_delta')} | {c.get('lastCpReq', '—')} | {c.get('lastCpResult', '—')} |"
        )
    lines += ["", "Success ≠ Wirkung.", ""]
    (EVIDENCE / f"{stem}.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    quiet(args.analyzer, args.peer)
    print(json.dumps({"ok": ok, "stem": stem, "n_ok": sum(1 for c in cases if c.get("ok")), "n": len(cases)}, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
