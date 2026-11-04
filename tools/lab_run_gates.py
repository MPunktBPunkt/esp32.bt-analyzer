#!/usr/bin/env python3
"""Run BT5–BT13 lab checks against the live F_ONCHIP topology and write evidence.

Usage:
  python3 tools/lab_run_gates.py
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "docs" / "evidence"
HOST = "192.168.178.88"
PEER = "192.168.178.89"
CLASSIC = "192.168.178.87"


def get(url: str, timeout: float = 8.0) -> dict:
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return json.loads(r.read().decode())


def post(url: str, fields: dict | None = None, timeout: float = 8.0) -> tuple[int, str]:
    data = urllib.parse.urlencode(fields or {}).encode()
    req = urllib.request.Request(url, data=data, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.status, r.read().decode(errors="replace")


def quiet(*ips: str) -> None:
    for ip in ips:
        for path in (
            "/api/bt/scan/stop",
            "/api/bt/advertise/stop",
            "/api/bt/inquiry/stop",
            "/api/bt/discoverable/stop",
            "/api/bt/disconnect",
        ):
            try:
                post(f"http://{ip}{path}")
            except Exception:  # noqa: BLE001
                pass


def main() -> int:
    utc = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    stem = f"LAB_GATES_BT5_13_{utc}"
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    results: dict = {"utc": utc, "topology": "F_ONCHIP", "gates": {}}

    host0 = get(f"http://{HOST}/api/status")
    peer0 = get(f"http://{PEER}/api/status")
    classic0 = get(f"http://{CLASSIC}/api/status")
    results["versions"] = {
        HOST: host0.get("version"),
        PEER: peer0.get("version"),
        CLASSIC: classic0.get("version"),
    }
    results["bd"] = {
        HOST: (host0.get("onchip") or {}).get("bdAddr"),
        PEER: (peer0.get("onchip") or {}).get("bdAddr"),
        CLASSIC: (classic0.get("onchip") or {}).get("bdAddr"),
    }

    # --- BT5 ring / PSRAM ---
    cap = host0.get("capture") or {}
    bt5_ok = bool(cap.get("psram")) and int(cap.get("capacity") or 0) >= 256
    results["gates"]["BT5"] = {
        "ok": bt5_ok,
        "capacity": cap.get("capacity"),
        "psram": cap.get("psram"),
        "fillPct": cap.get("fillPct"),
        "frameBytes": cap.get("frameBytes"),
    }

    quiet(HOST, PEER, CLASSIC)
    time.sleep(0.5)

    # --- BT11 advertise + BT9 connect ---
    peer_bd = results["bd"][PEER]
    post(f"http://{PEER}/api/bt/advertise/start", {"name": "bt-peer-89"})
    time.sleep(1.0)
    post(f"http://{HOST}/api/bt/scan/start")
    time.sleep(5.0)
    devices = get(f"http://{HOST}/api/bt/devices").get("devices") or []
    peer_seen = any((d.get("addr") or "").lower() == str(peer_bd).lower() for d in devices)
    results["gates"]["BT11"] = {
        "ok": peer_seen,
        "peer_seen": peer_seen,
        "devices": len(devices),
        "matched": [d for d in devices if (d.get("addr") or "").lower() == str(peer_bd).lower()],
    }

    post(f"http://{HOST}/api/bt/scan/stop")
    time.sleep(0.3)
    if peer_bd:
        post(f"http://{HOST}/api/bt/connect", {"addr": peer_bd, "addrType": "0"})
    deadline = time.time() + 8.0
    connected = False
    conn_handle = 0
    while time.time() < deadline:
        st = get(f"http://{HOST}/api/status")
        oc = st.get("onchip") or {}
        if oc.get("leConnected"):
            connected = True
            conn_handle = oc.get("connHandle") or 0
            break
        time.sleep(0.4)
    gatt_name = None
    gatt_ok = False
    if connected:
        try:
            post(f"http://{HOST}/api/bt/gatt/read-name")
            deadline_g = time.time() + 4.0
            while time.time() < deadline_g:
                oc = (get(f"http://{HOST}/api/status").get("onchip") or {})
                if oc.get("gattName"):
                    gatt_name = oc.get("gattName")
                    gatt_ok = True
                    break
                time.sleep(0.3)
        except Exception as exc:  # noqa: BLE001
            results["gatt_error"] = str(exc)
    results["gates"]["BT9"] = {
        "ok": connected,
        "leConnected": connected,
        "connHandle": conn_handle,
        "peerAddr": (get(f"http://{HOST}/api/status").get("onchip") or {}).get("peerAddr"),
        "gattName": gatt_name,
        "gatt_l2_ok": gatt_ok,
        "l2_claim": "att_over_hci_acl_not_air",
    }
    try:
        post(f"http://{HOST}/api/bt/disconnect")
    except Exception:  # noqa: BLE001
        pass
    quiet(HOST, PEER)
    time.sleep(0.5)

    # --- BT6 lossless + BT4/BT7/BT8 path during peer traffic ---
    post(f"http://{PEER}/api/bt/advertise/start", {"name": "bt-peer-89"})
    post(f"http://{HOST}/api/bt/scan/start")
    time.sleep(0.5)
    btac = EVIDENCE / f"{stem}.btac"
    jsonl = EVIDENCE / f"{stem}.jsonl"
    pcap = EVIDENCE / f"{stem}.pcapng"
    before = get(f"http://{HOST}/api/status")
    # Prefer session counters when present; else lifetime delta in this window.
    def _sess_drop(st: dict) -> int:
        c = st.get("capture") or {}
        return int(c["droppedSession"]) if "droppedSession" in c else int(c.get("dropped") or 0)

    def _sess_gap(st: dict) -> int:
        b = st.get("btac") or {}
        return int(b["seqGapsSession"]) if "seqGapsSession" in b else int(b.get("seqGaps") or 0)

    drop_before = _sess_drop(before)
    gap_before = _sess_gap(before)
    (EVIDENCE / f"{stem}_status_before.json").write_text(
        json.dumps(before, indent=2) + "\n", encoding="utf-8"
    )
    recv = subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools" / "btac_recv.py"),
            HOST,
            "-n",
            "120",
            "-o",
            str(btac),
            "--jsonl",
            str(jsonl),
            "--idle",
            "4",
        ],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=90,
    )
    after = get(f"http://{HOST}/api/status")
    (EVIDENCE / f"{stem}_status_after.json").write_text(
        json.dumps(after, indent=2) + "\n", encoding="utf-8"
    )
    drops_delta = max(0, _sess_drop(after) - drop_before)
    # New BTAC client resets session counters → after may be absolute session value
    if "droppedSession" in (after.get("capture") or {}) and drop_before > _sess_drop(after):
        drops_delta = _sess_drop(after)
    gaps_delta = max(0, _sess_gap(after) - gap_before)
    if "seqGapsSession" in (after.get("btac") or {}) and gap_before > _sess_gap(after):
        gaps_delta = _sess_gap(after)
    lifetime_gaps = int((after.get("btac") or {}).get("seqGaps") or 0)
    dec = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "btac_decode.py"), str(btac), "--stats"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=30,
    )
    try:
        dec_j = json.loads(dec.stdout)
    except json.JSONDecodeError:
        dec_j = {"ok": False, "raw": dec.stdout[-500:]}
    file_gaps = int(dec_j.get("gaps") or 0)
    pcap_p = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "btac_to_pcapng.py"), str(btac), "-o", str(pcap)],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=30,
    )
    try:
        pcap_j = json.loads(pcap_p.stdout)
    except json.JSONDecodeError:
        pcap_j = {"ok": False, "stderr": pcap_p.stderr}

    gap_cls = subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools" / "lab_gap_classify.py"),
            "--from-status",
            str(EVIDENCE / f"{stem}_status_before.json"),
            str(EVIDENCE / f"{stem}_status_after.json"),
            "--btac",
            str(btac),
        ],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=30,
    )
    try:
        gap_j = json.loads(gap_cls.stdout)
    except json.JSONDecodeError:
        gap_j = {"ok": False, "raw": gap_cls.stdout[-400:]}

    # Ring ok + decode crc ok + frames; E2E = file_gaps==0 (separate claim).
    results["gates"]["BT6"] = {
        "ok": drops_delta == 0
        and int(dec_j.get("crc_fail") or 0) == 0
        and int(dec_j.get("frames") or 0) > 0,
        "drops_delta": drops_delta,
        "btac_seqGapsSession_delta": gaps_delta,
        "btac_seqGaps_lifetime": lifetime_gaps,
        "file_gaps": file_gaps,
        "e2e_ok": file_gaps == 0 and drops_delta == 0,
        "highWater": (after.get("capture") or {}).get("highWater"),
        "highWaterSession": (after.get("capture") or {}).get("highWaterSession"),
        "frames": dec_j.get("frames"),
        "crc_fail": dec_j.get("crc_fail"),
        "recv_rc": recv.returncode,
        "gap_classify": gap_j,
        "note": "drops_delta=ring enqueue; e2e_ok requires file_gaps==0; never compare lifetime seqGaps to drops_delta",
    }
    results["gates"]["BT7"] = {"ok": bool(dec_j.get("ok")), "stats": dec_j}
    results["gates"]["BT8"] = {"ok": bool(pcap_j.get("ok")), "pcapng": str(pcap.relative_to(ROOT)), "stats": pcap_j}
    results["gates"]["BT4"] = {
        "ok": int(dec_j.get("frames") or 0) > 0,
        "btac": str(btac.relative_to(ROOT)),
        "jsonl": str(jsonl.relative_to(ROOT)),
    }

    quiet(HOST, PEER)
    time.sleep(0.3)

    # --- BT10 Classic discoverable + inquiry on .87 ---
    post(f"http://{CLASSIC}/api/bt/discoverable/start")
    time.sleep(0.5)
    st_c = get(f"http://{CLASSIC}/api/status")
    disc = bool((st_c.get("onchip") or {}).get("classicDiscoverable"))
    post(f"http://{CLASSIC}/api/bt/inquiry/start")
    time.sleep(10.0)
    cdevs = get(f"http://{CLASSIC}/api/bt/devices").get("devices") or []
    post(f"http://{CLASSIC}/api/bt/inquiry/stop")
    post(f"http://{CLASSIC}/api/bt/discoverable/stop")
    # Pass if discoverable HCI path works; devices optional (lab may have no Classic peers)
    results["gates"]["BT10"] = {
        "ok": disc and bool((st_c.get("onchip") or {}).get("classic")),
        "classicDiscoverable": disc,
        "inquiry_devices": len(cdevs),
        "devices": cdevs[:8],
        "note": "inquiry device count depends on ambient Classic discoverables",
    }

    # --- BT12 short long-capture (30s / 200 frames max) ---
    post(f"http://{PEER}/api/bt/advertise/start", {"name": "bt-peer-89"})
    post(f"http://{HOST}/api/bt/scan/start")
    long_btac = EVIDENCE / f"{stem}_long.btac"
    t0 = time.time()
    long_recv = subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools" / "btac_recv.py"),
            HOST,
            "-n",
            "200",
            "-o",
            str(long_btac),
            "--idle",
            "8",
        ],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=120,
    )
    dur = time.time() - t0
    try:
        long_j = json.loads(long_recv.stdout.strip().splitlines()[-1] if long_recv.stdout.strip() else "{}")
    except json.JSONDecodeError:
        # btac_recv prints progress then final json — find last {
        txt = long_recv.stdout
        idx = txt.rfind("{")
        long_j = json.loads(txt[idx:]) if idx >= 0 else {}
    results["gates"]["BT12"] = {
        "ok": int(long_j.get("frames") or 0) >= 50,
        "frames": long_j.get("frames"),
        "duration_s": round(dur, 2),
        "btac": str(long_btac.relative_to(ROOT)),
    }
    quiet(HOST, PEER)

    # --- BT13 wifi/bt stress: toggle scan/adv while polling status ---
    fails = 0
    for i in range(8):
        try:
            post(f"http://{PEER}/api/bt/advertise/start", {"name": f"stress-{i}"})
            post(f"http://{HOST}/api/bt/scan/start")
            get(f"http://{HOST}/api/status")
            get(f"http://{PEER}/api/status")
            post(f"http://{HOST}/api/bt/scan/stop")
            post(f"http://{PEER}/api/bt/advertise/stop")
        except Exception as exc:  # noqa: BLE001
            fails += 1
            results.setdefault("stress_errors", []).append(str(exc))
        time.sleep(0.25)
    host_end = get(f"http://{HOST}/api/status")
    results["gates"]["BT13"] = {
        "ok": fails == 0 and bool((host_end.get("onchip") or {}).get("ready")),
        "toggle_fails": fails,
        "host_ready": (host_end.get("onchip") or {}).get("ready"),
        "heap": host_end.get("heap"),
    }

    # --- BT14 doc readiness (local checklist) ---
    needed = [
        ROOT / "docs" / "GATES.md",
        ROOT / "docs" / "EVIDENCE.md",
        ROOT / "docs" / "LAB_METHODS.md",
        ROOT / "docs" / "BT15_RF_AIR.md",
        ROOT / "docs" / "BT16_THROUGHPUT.md",
        ROOT / "tools" / "btac_to_pcapng.py",
        ROOT / "tools" / "btac_decode.py",
        ROOT / "tools" / "lab_gate_exits.py",
        ROOT / "tools" / "lab_gap_classify.py",
        ROOT / "tools" / "lab_bt16_throughput.py",
        ROOT / "controller" / "session.py",
    ]
    missing = [str(p.relative_to(ROOT)) for p in needed if not p.is_file()]
    results["gates"]["BT14"] = {
        "ok": not missing,
        "missing": missing,
        "note": "project-side audit pack present; external technology-audit review separate",
    }
    results["gates"]["BT15"] = {"ok": True, "status": "deferred", "note": "RF/Air out of scope"}

    all_ok = all(bool(g.get("ok")) for k, g in results["gates"].items() if k != "BT15")
    results["ok"] = all_ok

    meta = EVIDENCE / f"{stem}.json"
    md = EVIDENCE / f"{stem}.md"
    meta.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    lines = [
        f"# Lab gates BT5–BT13 — {'PASS' if all_ok else 'PARTIAL'}",
        "",
        f"**Date (UTC):** {utc}",
        "**Topology:** F_ONCHIP",
        f"**FW:** `.88` {results['versions'][HOST]} · `.89` {results['versions'][PEER]} · `.87` {results['versions'][CLASSIC]}",
        f"**Raw:** [`{stem}.json`]({stem}.json)",
        "",
        "| Gate | OK | Notes |",
        "|------|----|-------|",
    ]
    for k, g in results["gates"].items():
        lines.append(f"| {k} | {g.get('ok')} | `{json.dumps({kk: vv for kk, vv in g.items() if kk != 'devices' and kk != 'matched' and kk != 'stats'}, ensure_ascii=False)[:120]}` |")
    lines += [
        "",
        "## Claim boundary",
        "L1 HCI / onchip_vhci only. HCI ≠ RF/Air.",
        "",
    ]
    md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"ok": all_ok, "meta": str(meta), "md": str(md), "gates": {k: v.get("ok") for k, v in results["gates"].items()}}, indent=2))
    return 0 if all_ok else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except urllib.error.URLError as exc:
        print(f"HTTP error: {exc}", file=sys.stderr)
        sys.exit(2)
