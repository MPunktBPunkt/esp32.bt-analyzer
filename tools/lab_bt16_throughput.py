#!/usr/bin/env python3
"""BT16 — BLE ATT throughput lab with CAPABILITY vs BENCHMARK exits.

Matrix (default): Notify+Write × MTU 23/247 × payload 20/200 (valid pairs only).
Default: --duration 30 --repeats 3

Evidence contract layers:
  Application: app_tx/rx_packets, app_seq_gaps, app_reorder, app_*_bytes
  Capture:     capture frames/drops (session)
  BTAC:        btac frames / seqGapsSession
  File:        file_frames / file_gaps
  Transport:   app_Bps, hci_Bps, btac_Bps

Usage:
  python3 tools/lab_bt16_throughput.py
  python3 tools/lab_bt16_throughput.py --duration 30 --repeats 3
  python3 tools/lab_bt16_throughput.py --quick   # 8s×1 smoke
"""

from __future__ import annotations

import argparse
import json
import statistics
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "docs" / "evidence"
HOST = "192.168.178.88"
PEER = "192.168.178.89"


def get(url: str, timeout: float = 8.0) -> dict:
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return json.loads(r.read().decode())


def post(url: str, fields: dict | None = None, timeout: float = 8.0) -> None:
    data = urllib.parse.urlencode(fields or {}).encode()
    req = urllib.request.Request(url, data=data, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        r.read()


def quiet() -> None:
    for ip in (HOST, PEER):
        for path in (
            "/api/bt/throughput/stop",
            "/api/bt/scan/stop",
            "/api/bt/advertise/stop",
            "/api/bt/disconnect",
        ):
            try:
                post(f"http://{ip}{path}")
            except Exception:  # noqa: BLE001
                pass


def ensure_link() -> str:
    quiet()
    time.sleep(0.4)
    peer_bd = (get(f"http://{PEER}/api/status").get("onchip") or {}).get("bdAddr")
    post(f"http://{PEER}/api/bt/advertise/start", {"name": "bt-peer-89"})
    time.sleep(0.8)
    post(f"http://{HOST}/api/bt/scan/start")
    time.sleep(4.0)
    post(f"http://{HOST}/api/bt/scan/stop")
    post(f"http://{HOST}/api/bt/connect", {"addr": peer_bd, "addrType": "0"})
    deadline = time.time() + 12
    while time.time() < deadline:
        if (get(f"http://{HOST}/api/status").get("onchip") or {}).get("leConnected"):
            return peer_bd or ""
        time.sleep(0.3)
    raise RuntimeError("connect_failed")


def pct(vals: list[float], p: float) -> float:
    if not vals:
        return 0.0
    s = sorted(vals)
    if len(s) == 1:
        return s[0]
    k = (len(s) - 1) * (p / 100.0)
    f = int(k)
    c = min(f + 1, len(s) - 1)
    if f == c:
        return s[f]
    return s[f] + (s[c] - s[f]) * (k - f)


def run_once(mode: str, mtu: int, payload: int, duration: float, capture: bool) -> dict:
    ensure_link()
    before = get(f"http://{HOST}/api/status")
    peer_before = get(f"http://{PEER}/api/status")
    btac_path = None
    recv = None
    if capture:
        btac_path = EVIDENCE / f"_bt16_{mode}_{mtu}_{payload}_{int(time.time())}.btac"
        recv = subprocess.Popen(
            [
                sys.executable,
                str(ROOT / "tools" / "btac_recv.py"),
                HOST,
                "-n",
                "200000",
                "-o",
                str(btac_path),
                "--idle",
                str(max(3, int(duration) + 3)),
            ],
            cwd=str(ROOT),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        time.sleep(0.5)

    post(f"http://{PEER}/api/bt/throughput/start", {"mode": mode, "payload": str(payload), "mtu": str(mtu)})
    post(f"http://{HOST}/api/bt/throughput/start", {"mode": mode, "payload": str(payload), "mtu": str(mtu)})
    time.sleep(2.0)

    samples = []
    t0 = time.time()
    while time.time() - t0 < duration:
        time.sleep(1.0)
        h = get(f"http://{HOST}/api/status")
        p = get(f"http://{PEER}/api/status")
        samples.append(
            {
                "app_Bps": float((h.get("onchip") or {}).get("appRxBps") or 0)
                + float((h.get("onchip") or {}).get("appTxBps") or 0),
                "appRx_Bps": float((h.get("onchip") or {}).get("appRxBps") or 0),
                "appTx_Bps": float((h.get("onchip") or {}).get("appTxBps") or 0),
                "hci_Bps": float((h.get("hciCapture") or {}).get("aclRxBps") or 0)
                + float((h.get("hciCapture") or {}).get("aclTxBps") or 0),
                "btac_Bps": float((h.get("btac") or {}).get("fwdBps") or 0),
                "peer_appTx_Bps": float((p.get("onchip") or {}).get("appTxBps") or 0),
            }
        )

    after = get(f"http://{HOST}/api/status")
    peer_after = get(f"http://{PEER}/api/status")
    quiet()

    file_gaps = None
    file_frames = None
    if recv:
        try:
            recv.wait(timeout=duration + 20)
        except Exception:  # noqa: BLE001
            recv.kill()
        if btac_path and btac_path.is_file():
            dec = subprocess.run(
                [sys.executable, str(ROOT / "tools" / "btac_decode.py"), str(btac_path), "--stats"],
                cwd=str(ROOT),
                capture_output=True,
                text=True,
                timeout=60,
            )
            try:
                dj = json.loads(dec.stdout)
                file_gaps = int(dj.get("gaps") or 0)
                file_frames = int(dj.get("frames") or 0)
            except json.JSONDecodeError:
                file_gaps = -1

    oc0, oc1 = before.get("onchip") or {}, after.get("onchip") or {}
    cap0, cap1 = before.get("capture") or {}, after.get("capture") or {}
    bt0, bt1 = before.get("btac") or {}, after.get("btac") or {}
    poc1 = peer_after.get("onchip") or {}

    def sess_delta(a: dict, b: dict, key: str, fallback: str) -> int:
        if key in a or key in b:
            return max(0, int(a.get(key) or 0) - int(b.get(key) or 0))
        return max(0, int(a.get(fallback) or 0) - int(b.get(fallback) or 0))

    # Prefer absolute session counters after a fresh BTAC connect
    capture_drops = int(cap1.get("droppedSession") if "droppedSession" in cap1 else sess_delta(cap1, cap0, "droppedSession", "dropped"))
    if "droppedSession" in cap1 and int(cap0.get("droppedSession") or 0) > int(cap1.get("droppedSession") or 0):
        capture_drops = int(cap1.get("droppedSession") or 0)
    btac_gaps = int(bt1.get("seqGapsSession") if "seqGapsSession" in bt1 else sess_delta(bt1, bt0, "seqGapsSession", "seqGaps"))
    if "seqGapsSession" in bt1 and int(bt0.get("seqGapsSession") or 0) > int(bt1.get("seqGapsSession") or 0):
        btac_gaps = int(bt1.get("seqGapsSession") or 0)

    app_rx_bps = [s["appRx_Bps"] for s in samples]
    app_tx_bps = [s["appTx_Bps"] for s in samples]
    peer_tx = [s["peer_appTx_Bps"] for s in samples]
    # Primary app rate: host RX for notify, host TX for write (plus peer TX fallback)
    primary = app_rx_bps if mode == "notify" else app_tx_bps
    if statistics.mean(primary or [0]) < 1 and peer_tx:
        primary = peer_tx

    hci_bps = [s["hci_Bps"] for s in samples]
    btac_bps = [s["btac_Bps"] for s in samples]

    app_tx_packets = int(oc1.get("appTxPackets") or 0)
    app_rx_packets = int(oc1.get("appRxPackets") or 0)
    # Also count peer TX packets for notify
    peer_tx_packets = int(poc1.get("appTxPackets") or 0)
    app_seq_gaps = int(oc1.get("appSeqGaps") or oc1.get("thrLoss") or 0)
    app_reorder = int(oc1.get("appReorder") or oc1.get("thrReorder") or 0)

    connected = bool(oc1.get("leConnected") or oc0.get("leConnected"))
    att_seen = (app_tx_packets + app_rx_packets + peer_tx_packets) > 0 or statistics.mean(primary or [0]) > 0
    hci_seen = statistics.mean(hci_bps or [0]) > 0 or int((after.get("hciCapture") or {}).get("rx") or 0) > int(
        (before.get("hciCapture") or {}).get("rx") or 0
    )

    capability_ok = connected and att_seen and hci_seen
    benchmark_ok = (
        capability_ok
        and int(file_gaps or 0) == 0
        and app_seq_gaps == 0
        and app_reorder == 0
        and capture_drops == 0
        and duration >= 10
    )

    return {
        "mode": mode,
        "mtu": mtu,
        "payload": payload,
        "duration_s": duration,
        "capture": capture,
        "application": {
            "app_tx_packets": app_tx_packets,
            "app_rx_packets": app_rx_packets,
            "peer_app_tx_packets": peer_tx_packets,
            "app_tx_bytes": oc1.get("appTxBytes"),
            "app_rx_bytes": oc1.get("appRxBytes"),
            "peer_app_tx_bytes": poc1.get("appTxBytes"),
            "app_seq_gaps": app_seq_gaps,
            "app_reorder": app_reorder,
            "app_Bps_median": statistics.median(primary) if primary else 0,
            "app_Bps_p10": pct(primary, 10),
            "app_Bps_p90": pct(primary, 90),
            "app_Bps_mean": statistics.mean(primary) if primary else 0,
        },
        "capture": {
            "capture_frames": int(cap1.get("captured") or 0) - int(cap0.get("captured") or 0),
            "capture_drops": capture_drops,
            "droppedSession": cap1.get("droppedSession"),
            "highWaterSession": cap1.get("highWaterSession"),
        },
        "btac": {
            "btac_frames": int(bt1.get("forwarded") or 0) - int(bt0.get("forwarded") or 0),
            "btac_seq_gaps": btac_gaps,
            "seqGapsSession": bt1.get("seqGapsSession"),
            "fwdBps_median": statistics.median(btac_bps) if btac_bps else 0,
        },
        "file": {"file_frames": file_frames, "file_gaps": file_gaps},
        "transport": {
            "hci_Bps_median": statistics.median(hci_bps) if hci_bps else 0,
            "btac_Bps_median": statistics.median(btac_bps) if btac_bps else 0,
        },
        "capability_status": "PASS" if capability_ok else "FAIL",
        "benchmark_status": "PASS" if benchmark_ok else "FAIL",
        "ok": capability_ok,  # smoke-compat
        "attMtu_host": oc1.get("attMtu"),
        "attMtu_peer": poc1.get("attMtu"),
    }


def summarize_repeats(runs: list[dict]) -> dict:
    medians = [r["application"]["app_Bps_median"] for r in runs]
    return {
        "repeats": len(runs),
        "app_Bps_median_of_medians": statistics.median(medians) if medians else 0,
        "app_Bps_p10_of_medians": pct(medians, 10),
        "app_Bps_p90_of_medians": pct(medians, 90),
        "capability_pass_count": sum(1 for r in runs if r.get("capability_status") == "PASS"),
        "benchmark_pass_count": sum(1 for r in runs if r.get("benchmark_status") == "PASS"),
        "runs": runs,
        "capability_status": "PASS" if any(r.get("capability_status") == "PASS" for r in runs) else "FAIL",
        "benchmark_status": "PASS" if all(r.get("benchmark_status") == "PASS" for r in runs) and runs else "FAIL",
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--duration", type=float, default=30.0)
    ap.add_argument("--repeats", type=int, default=3)
    ap.add_argument("--modes", default="notify,write")
    ap.add_argument("--mtus", default="23,247")
    ap.add_argument("--payloads", default="20,200")
    ap.add_argument("--no-capture", action="store_true")
    ap.add_argument("--quick", action="store_true", help="8s × 1 repeat smoke")
    args = ap.parse_args()
    if args.quick:
        args.duration = 8.0
        args.repeats = 1

    utc = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    modes = [m.strip() for m in args.modes.split(",") if m.strip()]
    mtus = [int(x) for x in args.mtus.split(",") if x.strip()]
    payloads = [int(x) for x in args.payloads.split(",") if x.strip()]

    cases = []
    for mode in modes:
        for mtu in mtus:
            for payload in payloads:
                if payload + 3 > mtu:
                    continue
                print(f"[bt16] {mode} mtu={mtu} payload={payload} ×{args.repeats} @{args.duration}s", flush=True)
                runs = []
                for i in range(args.repeats):
                    print(f"  repeat {i+1}/{args.repeats}", flush=True)
                    try:
                        runs.append(run_once(mode, mtu, payload, args.duration, not args.no_capture))
                    except Exception as exc:  # noqa: BLE001
                        runs.append(
                            {
                                "mode": mode,
                                "mtu": mtu,
                                "payload": payload,
                                "error": str(exc),
                                "capability_status": "FAIL",
                                "benchmark_status": "FAIL",
                                "application": {"app_Bps_median": 0},
                            }
                        )
                summary = summarize_repeats(runs)
                summary.update({"mode": mode, "mtu": mtu, "payload": payload, "duration_s": args.duration})
                cases.append(summary)

    capability_ok = any(c.get("capability_status") == "PASS" for c in cases)
    benchmark_ok = any(c.get("benchmark_status") == "PASS" for c in cases) and all(
        c.get("benchmark_pass_count", 0) > 0 for c in cases if c.get("capability_status") == "PASS"
    )
    # Strict: overall benchmark only if every completed capability case also has full-repeat benchmark
    benchmark_ok = all(c.get("benchmark_status") == "PASS" for c in cases) and bool(cases)

    results = {
        "utc": utc,
        "topology": "F_ONCHIP",
        "gate": "BT16",
        "contract": "CAPABILITY_vs_BENCHMARK",
        "claim": "L2_ATT_throughput_over_HCI_not_air",
        "duration_s": args.duration,
        "repeats": args.repeats,
        "capability_ok": capability_ok,
        "benchmark_ok": benchmark_ok,
        "cases": cases,
        "ok": capability_ok,  # smoke / legacy
    }

    stem = f"LAB_BT16_{utc}"
    meta = EVIDENCE / f"{stem}.json"
    md = EVIDENCE / f"{stem}.md"
    meta.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    lines = [
        f"# LAB BT16 — capability={'PASS' if capability_ok else 'FAIL'} · benchmark={'PASS' if benchmark_ok else 'FAIL'}",
        "",
        f"**UTC:** {utc} · **duration:** {args.duration}s × {args.repeats}",
        f"**Raw:** [`{stem}.json`]({stem}.json)",
        "",
        "| mode | mtu | payload | median B/s | p10 | p90 | cap PASS/n | bench PASS/n |",
        "|------|-----|---------|------------|-----|-----|------------|--------------|",
    ]
    for c in cases:
        lines.append(
            f"| {c.get('mode')} | {c.get('mtu')} | {c.get('payload')} | "
            f"{c.get('app_Bps_median_of_medians', 0):.0f} | {c.get('app_Bps_p10_of_medians', 0):.0f} | "
            f"{c.get('app_Bps_p90_of_medians', 0):.0f} | "
            f"{c.get('capability_pass_count')}/{c.get('repeats')} | "
            f"{c.get('benchmark_pass_count')}/{c.get('repeats')} |"
        )
    lines += [
        "",
        "## Exit classes",
        "- **CAPABILITY_PASS:** connected + ATT traffic + HCI traffic",
        "- **BENCHMARK_PASS:** capability + file_gaps=0 + app_seq_gaps=0 + app_reorder=0 + capture_drops=0",
        "",
    ]
    md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    quiet()
    print(
        json.dumps(
            {
                "capability_ok": capability_ok,
                "benchmark_ok": benchmark_ok,
                "meta": str(meta),
                "cases": len(cases),
            },
            indent=2,
        )
    )
    return 0 if capability_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
