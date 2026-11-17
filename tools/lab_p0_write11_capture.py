#!/usr/bin/env python3
"""P0 write11 capture: BCL hold + dual btmon + pre-close window analysis.

Runs on the operator machine. Starts btmon on HU + phone HCI (by BD), runs a
BCL-only dual-ESP hold, then extracts the ±window around write_error:11 from
HU/phone jsonl and a btmon text dump of both btsnoop files.

Usage:
  python3 tools/lab_p0_write11_capture.py --hold 120 \\
    --out-dir docs/evidence/LAB_P0_WRITE11_CAP_...
"""

from __future__ import annotations

import argparse
import json
import re
import shlex
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SSH = "root@192.168.178.108"
HU_BD = "C8:C9:A3:CB:7B:0A"
PHONE_BD = "C8:C9:A3:CB:37:96"


def utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def ssh(remote: str, timeout: float = 120.0, host: str = DEFAULT_SSH) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=8", host, remote],
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def scp_from(remote_path: str, local: Path, host: str = DEFAULT_SSH) -> None:
    local.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["scp", "-o", "BatchMode=yes", f"{host}:{remote_path}", str(local)],
        check=True,
        capture_output=True,
        text=True,
        timeout=120,
    )


def scp_to(local: Path, remote_path: str, host: str = DEFAULT_SSH) -> None:
    subprocess.run(
        ["scp", "-o", "BatchMode=yes", str(local), f"{host}:{remote_path}"],
        check=True,
        capture_output=True,
        text=True,
        timeout=60,
    )


def resolve_hci_map(host: str) -> dict[str, str]:
    """BD -> hciN index string."""
    p = ssh(
        "python3 - <<'PY'\n"
        "import dbus,json\n"
        "bus=dbus.SystemBus()\n"
        "om=dbus.Interface(bus.get_object('org.bluez','/'),'org.freedesktop.DBus.ObjectManager')\n"
        "out={}\n"
        "for pth, ifaces in om.GetManagedObjects().items():\n"
        "  ad=ifaces.get('org.bluez.Adapter1')\n"
        "  if not ad: continue\n"
        "  addr=str(ad.get('Address','')).upper()\n"
        "  idx=pth.rsplit('/',1)[-1].replace('hci','')\n"
        "  out[addr]=idx\n"
        "print(json.dumps(out))\n"
        "PY",
        host=host,
    )
    data = json.loads(p.stdout.strip() or "{}")
    return {str(k).upper(): str(v) for k, v in data.items()}


def start_btmon(host: str, remote_dir: str, hci: str, tag: str) -> dict:
    path = f"{remote_dir}/{tag}_hci{hci}.btsnoop"
    log = f"{remote_dir}/{tag}_btmon.log"
    ssh(f"pkill -f 'btmon -i {hci} -w' >/dev/null 2>&1 || true", host=host, timeout=20)
    time.sleep(0.3)
    # Fully detach so SSH does not wait on btmon's open fds.
    remote = (
        f"mkdir -p {shlex.quote(remote_dir)}; "
        f"nohup btmon -i {hci} -w {shlex.quote(path)} "
        f">{shlex.quote(log)} 2>&1 </dev/null & "
        f"echo $!; disown || true"
    )
    p = ssh(f"bash -lc {shlex.quote(remote)}", host=host, timeout=30)
    pid = (p.stdout or "").strip().splitlines()[-1] if p.stdout else ""
    return {"hci": hci, "tag": tag, "btsnoop": path, "log": log, "pid": pid}


def stop_btmon(host: str, hci: str) -> None:
    ssh(f"pkill -INT -f 'btmon -i {hci} -w' || true; sleep 1", host=host, timeout=20)


def load_jsonl(path: Path) -> list[dict]:
    rows = []
    if not path.exists():
        return rows
    for line in path.read_text(errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def window_events(events: list[dict], center_ts: float, before: float, after: float) -> list[dict]:
    lo, hi = center_ts - before, center_ts + after
    return [e for e in events if isinstance(e.get("ts"), (int, float)) and lo <= float(e["ts"]) <= hi]


def summarize_tx(events: list[dict]) -> dict:
    tx = [e for e in events if e.get("event") == "tx_bytes"]
    rx = [e for e in events if e.get("event") == "rx_bytes"]
    sizes = [int(e.get("n") or 0) for e in tx]
    methods = [
        e.get("method")
        for e in events
        if e.get("event") in ("f20_rpc_rx", "mybmw_rpc_tx", "mybmw_rpc_rx", "etch_data_tx")
        and e.get("method")
    ]
    gaps = []
    for a, b in zip(tx, tx[1:]):
        if isinstance(a.get("ts"), (int, float)) and isinstance(b.get("ts"), (int, float)):
            gaps.append(float(b["ts"]) - float(a["ts"]))
    return {
        "tx_frames": len(tx),
        "tx_bytes": sum(sizes),
        "tx_max": max(sizes) if sizes else 0,
        "rx_frames": len(rx),
        "rx_bytes": sum(int(e.get("n") or 0) for e in rx),
        "mean_tx_gap_s": round(sum(gaps) / len(gaps), 4) if gaps else None,
        "min_tx_gap_s": round(min(gaps), 4) if gaps else None,
        "last_methods": methods[-12:],
    }


def btmon_text_excerpt(
    btsnoop_remote: str,
    out_txt: Path,
    keep_re: re.Pattern[str],
    *,
    host: str,
) -> list[str]:
    """Decode btsnoop on the BlueZ host (operator may lack btmon)."""
    remote_txt = btsnoop_remote + ".txt"
    ssh(
        f"btmon -r {shlex.quote(btsnoop_remote)} > {shlex.quote(remote_txt)} 2>/dev/null || true",
        host=host,
        timeout=180,
    )
    try:
        scp_from(remote_txt, out_txt, host=host)
        lines = out_txt.read_text(errors="replace").splitlines()
    except Exception:
        lines = []
        out_txt.write_text("")
    kept = [ln for ln in lines if keep_re.search(ln)]
    return kept


def analyze_capture(
    *,
    out_dir: Path,
    hold: dict,
    hu_events: list[dict],
    phone_events: list[dict],
    btmon_kept: dict[str, list[str]],
    window_s: float,
) -> dict:
    fail = next((e for e in reversed(hu_events) if e.get("event") == "tx_write_failed"), None)
    close = next(
        (
            e
            for e in reversed(hu_events)
            if e.get("event") == "rfcomm_closed" and "write_error:11" in str(e.get("reason") or "")
        ),
        None,
    )
    center = None
    if fail and isinstance(fail.get("ts"), (int, float)):
        center = float(fail["ts"])
    elif close and isinstance(close.get("ts"), (int, float)):
        center = float(close["ts"])

    hu_win = window_events(hu_events, center, window_s, window_s) if center else []
    phone_win = window_events(phone_events, center, window_s, window_s) if center else []

    report = {
        "hold": {
            "ok": (hold.get("hold") or {}).get("ok"),
            "send_err": (hold.get("hold") or {}).get("send_err"),
            "wait_class": (hold.get("hold") or {}).get("wait_class"),
            "abort_reason": (hold.get("hold") or {}).get("abort_reason"),
            "hold_s": (hold.get("hold") or {}).get("hold_s"),
            "phone_events": (hold.get("hold") or {}).get("phone_events"),
        },
        "center_ts": center,
        "window_s": window_s,
        "tx_write_failed": fail,
        "rfcomm_closed": close,
        "hu_session_tx": summarize_tx(hu_events),
        "phone_session_tx": summarize_tx(phone_events),
        "hu_window_events": [
            {
                k: e.get(k)
                for k in (
                    "ts",
                    "event",
                    "reason",
                    "n",
                    "method",
                    "errno",
                    "errno_name",
                    "bytes_attempted",
                    "tx_total",
                    "tx_frames",
                    "seconds_since_last_rx",
                    "seconds_since_last_tx_ok",
                    "cmd_name",
                    "src",
                    "dest",
                )
                if k in e or k in ("ts", "event")
            }
            for e in hu_win
        ],
        "phone_window_events": [
            {
                k: e.get(k)
                for k in (
                    "ts",
                    "event",
                    "reason",
                    "n",
                    "method",
                    "misses",
                    "wait_class",
                    "abort_reason",
                    "rhmi_state",
                )
                if k in e or k in ("ts", "event")
            }
            for e in phone_win
        ],
        "btmon_line_counts": {k: len(v) for k, v in btmon_kept.items()},
        "btmon_tail": {k: v[-80:] for k, v in btmon_kept.items()},
        "hypothesis_hints": [],
    }

    hints = report["hypothesis_hints"]
    if fail and fail.get("errno") == 11:
        hints.append("HU os.write failed with errno 11 (EAGAIN/EWOULDBLOCK) — transport not ready at write()")
    if fail and (fail.get("seconds_since_last_rx") or 0) > 1.0:
        hints.append(
            f"last RX was {fail.get('seconds_since_last_rx')}s before failed write — RX stall before TX fail"
        )
    if report["hu_session_tx"]["tx_max"] >= 1000:
        hints.append(f"session saw large HU TX frame(s) up to {report['hu_session_tx']['tx_max']} B")
    if (hold.get("hold") or {}).get("wait_class") == "WATCHDOG_MISS_NO_ETCH_REPLY":
        hints.append("phone classified abort as WATCHDOG_MISS_NO_ETCH_REPLY")
    if not center:
        hints.append("no write_error:11 / tx_write_failed found — capture may be bond-fail or eof path")

    return report


def write_md(report: dict, path: Path) -> None:
    fail = report.get("tx_write_failed") or {}
    close = report.get("rfcomm_closed") or {}
    lines = [
        f"# LAB P0 write11 capture — {path.parent.name}",
        "",
        f"- hold.ok: **{(report.get('hold') or {}).get('ok')}**",
        f"- wait_class: `{(report.get('hold') or {}).get('wait_class')}`",
        f"- abort: `{(report.get('hold') or {}).get('abort_reason')}`",
        f"- center_ts: `{report.get('center_ts')}` (±{report.get('window_s')}s)",
        f"- tx_write_failed errno: `{fail.get('errno')} ({fail.get('errno_name')})` "
        f"attempted={fail.get('bytes_attempted')} tx_total={fail.get('tx_total')} "
        f"since_rx={fail.get('seconds_since_last_rx')}s",
        f"- rfcomm_closed: `{close.get('reason')}`",
        "",
        "## Session TX",
        "",
        f"- HU: {json.dumps(report.get('hu_session_tx'))}",
        f"- Phone: {json.dumps(report.get('phone_session_tx'))}",
        "",
        "## Hints",
        "",
    ]
    for h in report.get("hypothesis_hints") or []:
        lines.append(f"- {h}")
    lines += ["", "## HU window (compact)", "", "```json"]
    lines.append(json.dumps(report.get("hu_window_events"), indent=2)[:6000])
    lines += ["```", "", "## btmon kept-line tails", ""]
    for tag, tail in (report.get("btmon_tail") or {}).items():
        lines.append(f"### {tag} ({report.get('btmon_line_counts', {}).get(tag)} lines)")
        lines.append("```")
        lines.extend(tail[-40:])
        lines.append("```")
        lines.append("")
    path.write_text("\n".join(lines) + "\n")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--hold", type=float, default=120.0)
    ap.add_argument("--window", type=float, default=0.5, help="seconds before/after write11")
    ap.add_argument("--ssh", default=DEFAULT_SSH)
    ap.add_argument("--out-dir", type=Path)
    args = ap.parse_args()

    stamp = utc_stamp()
    out_dir = args.out_dir or (ROOT / "docs" / "evidence" / f"LAB_P0_WRITE11_CAP_{stamp}")
    out_dir.mkdir(parents=True, exist_ok=True)
    remote_dir = f"/tmp/bcl_dummy/p0_write11_cap_{stamp}"
    host = args.ssh

    # Deploy instrumented HU agent
    scp_to(ROOT / "tools" / "bcl_dummy_hu_agent.py", "/tmp/bcl_dummy/bcl_dummy_hu_agent.py", host=host)

    hci_map = resolve_hci_map(host)
    hu_hci = hci_map.get(HU_BD.upper())
    phone_hci = hci_map.get(PHONE_BD.upper())
    (out_dir / "hci_map.json").write_text(json.dumps(hci_map, indent=2) + "\n")
    if not hu_hci or not phone_hci:
        print("missing HU/phone HCI", hci_map, file=sys.stderr)
        return 2

    print(f"HCI map HU=hci{hu_hci} phone=hci{phone_hci}", flush=True)
    # pin aliases by BD (indices can flip / drift)
    ssh(
        "python3 - <<'PY'\n"
        "import dbus\n"
        f"WANT={{'{HU_BD.upper()}':'BMW 38304','{PHONE_BD.upper()}':'BT-Analyzer-Phone'}}\n"
        "bus=dbus.SystemBus()\n"
        "om=dbus.Interface(bus.get_object('org.bluez','/'),'org.freedesktop.DBus.ObjectManager')\n"
        "for pth, ifaces in om.GetManagedObjects().items():\n"
        "  ad=ifaces.get('org.bluez.Adapter1')\n"
        "  if not ad: continue\n"
        "  addr=str(ad.get('Address','')).upper()\n"
        "  if addr in WANT:\n"
        "    dbus.Interface(bus.get_object('org.bluez',pth),'org.freedesktop.DBus.Properties')"
        ".Set('org.bluez.Adapter1','Alias',dbus.String(WANT[addr]))\n"
        "    print('alias', pth, addr, WANT[addr])\n"
        "PY",
        host=host,
    )
    ssh(f"mkdir -p {shlex.quote(remote_dir)}", host=host)
    caps = [
        start_btmon(host, remote_dir, hu_hci, "hu"),
        start_btmon(host, remote_dir, phone_hci, "phone"),
    ]
    (out_dir / "btmon_start.json").write_text(json.dumps(caps, indent=2) + "\n")
    print("btmon started", json.dumps(caps), flush=True)
    time.sleep(1.0)

    hold_out = out_dir / f"hold_{stamp}.json"
    print(f"running BCL hold {args.hold}s -> {hold_out}", flush=True)
    hold_rc = subprocess.run(
        [
            "python3",
            str(ROOT / "tools" / "lab_p0_dual_esp_hold.py"),
            "--hold",
            str(args.hold),
            "--out",
            str(hold_out),
            "--ssh",
            host,
        ],
        cwd=str(ROOT),
    ).returncode

    for c in caps:
        stop_btmon(host, c["hci"])

    # Pull remote hold artifacts + btsnoop
    # dual_esp_hold prints remote OUT; recover from latest p0_hold_* if needed
    remote_hold = (
        ssh("ls -1dt /tmp/bcl_dummy/p0_hold_* 2>/dev/null | head -1", host=host).stdout or ""
    ).strip()
    if remote_hold:
        for name in ("phone.jsonl", "hold.json", "esp_poll.jsonl", "esp_diag_pre.json", "esp_diag_post.json"):
            try:
                scp_from(f"{remote_hold}/{name}", out_dir / name, host=host)
            except Exception as e:  # noqa: BLE001
                print(f"skip {name}: {e}", flush=True)
        # HU session log used by hold
        try:
            scp_from("/tmp/bcl_dummy/hu_ab_87131.jsonl", out_dir / "hu_ab_87131.jsonl", host=host)
        except Exception as e:  # noqa: BLE001
            print(f"skip hu jsonl: {e}", flush=True)

    for c in caps:
        local = out_dir / Path(c["btsnoop"]).name
        try:
            scp_from(c["btsnoop"], local, host=host)
            c["local"] = str(local)
        except Exception as e:  # noqa: BLE001
            print(f"btsnoop pull failed {c['btsnoop']}: {e}", flush=True)

    keep_re = re.compile(
        r"ACL Data|RFCOMM|Channel|Credits|UIH|SABM|DISC|DM |Number of completed|"
        r"Handle|PB Flag|TX|RX|Error|L2CAP",
        re.I,
    )
    btmon_kept: dict[str, list[str]] = {}
    for c in caps:
        local_btsnoop = out_dir / Path(c["btsnoop"]).name
        if not local_btsnoop.exists() and not c.get("btsnoop"):
            continue
        kept = btmon_text_excerpt(
            c["btsnoop"],
            out_dir / f"{Path(c['btsnoop']).stem}.btmon.txt",
            keep_re,
            host=host,
        )
        btmon_kept[c["tag"]] = kept
        (out_dir / f"{c['tag']}_btmon_kept.txt").write_text("\n".join(kept) + "\n")

    hold = {}
    if hold_out.exists():
        hold = json.loads(hold_out.read_text())
    hu_events = load_jsonl(out_dir / "hu_ab_87131.jsonl")
    # Prefer session-local phone log from remote hold dir
    phone_events = load_jsonl(out_dir / "phone.jsonl")

    # Trim HU events to this capture roughly: last rfcomm_connected → end
    last_conn = next(
        (e for e in reversed(hu_events) if e.get("event") == "rfcomm_connected"),
        None,
    )
    if last_conn and isinstance(last_conn.get("ts"), (int, float)):
        t0 = float(last_conn["ts"]) - 1.0
        hu_events = [e for e in hu_events if isinstance(e.get("ts"), (int, float)) and float(e["ts"]) >= t0]

    report = analyze_capture(
        out_dir=out_dir,
        hold=hold,
        hu_events=hu_events,
        phone_events=phone_events,
        btmon_kept=btmon_kept,
        window_s=args.window,
    )
    report["hold_rc"] = hold_rc
    report["remote_hold"] = remote_hold
    report["btmon"] = caps
    (out_dir / "capture_report.json").write_text(json.dumps(report, indent=2) + "\n")
    write_md(report, out_dir / "CAPTURE.md")
    print(json.dumps({"out": str(out_dir), "hints": report["hypothesis_hints"], "fail": report.get("tx_write_failed")}, indent=2))
    print(f"wrote {out_dir / 'CAPTURE.md'}", flush=True)
    return 0 if report.get("tx_write_failed") or "write_error:11" in str((report.get("rfcomm_closed") or {}).get("reason")) else hold_rc


if __name__ == "__main__":
    raise SystemExit(main())
