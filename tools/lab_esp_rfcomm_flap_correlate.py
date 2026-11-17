#!/usr/bin/env python3
"""P0: correlate HU RFCOMM flaps with ESP status / nearby Etch traffic.

Offline (jsonl only):
  python3 tools/lab_esp_rfcomm_flap_correlate.py \\
    --hu docs/evidence/LAB_HOME_CONT8_20261117T1809Z_hu.jsonl \\
    --out docs/evidence/LAB_P0_ESP_RFCOMM_OFFLINE.json

Live (tail jsonl + poll ESP /api/status):
  python3 tools/lab_esp_rfcomm_flap_correlate.py \\
    --hu /tmp/bcl_dummy/hu_recover.jsonl --esp 192.168.178.131 \\
    --watch 60 --out /tmp/LAB_P0_ESP_RFCOMM_LIVE.json

Per rfcomm_closed the report records close reason, reconnect lag, last TX/RX,
nearby etch_data_tx, and (live) ESP bootGen/uptime/drops deltas.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from collections import Counter
from pathlib import Path
from typing import Any


INTERESTING = frozenset(
    {
        "rfcomm_closed",
        "rfcomm_connected",
        "etch_data_tx",
        "etch_data_rx",
        "etch_open_rx",
        "handshake_sent",
        "session_init",
        "knock_envelope_rx",
        "sas_login_ok_tx",
        "watchdog_echo",
        "rhmi_check_resource",
        "f20_rpc_rx",
        "phone_tx_classified",
        "tx_bytes",
        "rx_bytes",
        "error",
        "framer_error",
    }
)


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    with path.open() as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return out


def fetch_esp(host: str, timeout: float = 3.0) -> dict[str, Any] | None:
    url = f"http://{host}/api/status"
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return json.load(resp)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
        return None


def esp_snapshot(st: dict[str, Any] | None) -> dict[str, Any] | None:
    if not st:
        return None
    ha = st.get("hciAgent") or {}
    return {
        "ts": time.time(),
        "ip": st.get("ip"),
        "uptime": st.get("uptime"),
        "heap": st.get("heap"),
        "resetReason": st.get("resetReason"),
        "restartCause": st.get("restartCause"),
        "bootGen": st.get("bootGen"),
        "diagPrev": st.get("diagPrev"),
        "diagSnaps": st.get("diagSnaps"),
        "recoveryHist": st.get("recoveryHist"),
        "recoveryLast": st.get("recoveryLast"),
        "hci_sessions": ha.get("sessions"),
        "hci_drops": ha.get("drops"),
        "hci_framingErrors": ha.get("framingErrors"),
        "hci_writeRetries": ha.get("writeRetries"),
        "hci_client": ha.get("client"),
        "toHostBytes": ha.get("toHostBytes"),
        "toCtrlBytes": ha.get("toCtrlBytes"),
    }


def _compact(ev: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "ts",
        "event",
        "reason",
        "peer",
        "rfcomm_channel",
        "session_id",
        "method",
        "cmd_name",
        "type_name",
        "property",
        "handle",
        "msg_id",
        "n",
        "acked",
    )
    return {k: ev.get(k) for k in keys if k in ev and ev.get(k) is not None}


def classify_flap(close: dict[str, Any], before: list[dict], after: list[dict]) -> str:
    reason = str(close.get("reason") or "")
    etch_before = sum(1 for e in before if e.get("event") == "etch_data_tx")
    re_hs = any(e.get("event") in ("handshake_sent", "session_init") for e in after[:12])
    quick_eof = any(
        e.get("event") == "rfcomm_closed" and "eof" in str(e.get("reason") or "")
        for e in after[:6]
    )
    if "write_error:11" in reason and etch_before >= 3:
        return "tx_pressure_during_etch_reply"
    if "write_error:11" in reason and quick_eof:
        return "write11_then_eof_rehandshake" if re_hs else "write11_then_eof"
    if reason == "eof" and re_hs:
        return "eof_rehandshake"
    if reason == "eof":
        return "eof"
    return "other"


def correlate_events(events: list[dict[str, Any]], *, window: int = 12) -> dict[str, Any]:
    closes = [(i, e) for i, e in enumerate(events) if e.get("event") == "rfcomm_closed"]
    opens = [(i, e) for i, e in enumerate(events) if e.get("event") == "rfcomm_connected"]
    flaps: list[dict[str, Any]] = []

    for i, close in closes:
        before = [events[j] for j in range(max(0, i - window), i)]
        after = [events[j] for j in range(i + 1, min(len(events), i + 1 + window))]
        # reconnect lag: next rfcomm_connected after this close
        reconnect_s = None
        for j, op in opens:
            if j > i:
                try:
                    reconnect_s = float(op.get("ts") or 0) - float(close.get("ts") or 0)
                except (TypeError, ValueError):
                    reconnect_s = None
                break
        last_tx = next((e for e in reversed(before) if e.get("event") == "tx_bytes"), None)
        last_rx = next((e for e in reversed(before) if e.get("event") == "rx_bytes"), None)
        last_etch = next(
            (e for e in reversed(before) if e.get("event") == "etch_data_tx"), None
        )
        last_rpc = next(
            (
                e
                for e in reversed(before)
                if e.get("event") in ("f20_rpc_rx", "phone_tx_classified", "rhmi_check_resource")
            ),
            None,
        )
        interesting_before = [_compact(e) for e in before if e.get("event") in INTERESTING]
        interesting_after = [_compact(e) for e in after if e.get("event") in INTERESTING]
        flaps.append(
            {
                "ts": close.get("ts"),
                "reason": close.get("reason"),
                "peer": close.get("peer"),
                "rfcomm_channel": close.get("rfcomm_channel"),
                "session_id": close.get("session_id"),
                "class": classify_flap(close, before, after),
                "reconnect_s": None if reconnect_s is None else round(reconnect_s, 3),
                "last_tx": _compact(last_tx) if last_tx else None,
                "last_rx": _compact(last_rx) if last_rx else None,
                "last_etch_tx": _compact(last_etch) if last_etch else None,
                "last_rpc_or_check": _compact(last_rpc) if last_rpc else None,
                "before": interesting_before[-8:],
                "after": interesting_after[:8],
            }
        )

    by_class = Counter(f["class"] for f in flaps)
    by_reason = Counter(str(f.get("reason")) for f in flaps)
    return {
        "flap_count": len(flaps),
        "by_class": dict(by_class),
        "by_reason": dict(by_reason),
        "flaps": flaps,
    }


def watch_live(
    hu_path: Path,
    esp_host: str,
    *,
    seconds: float,
    poll_s: float = 1.0,
) -> dict[str, Any]:
    """Tail jsonl while polling ESP; attach snapshots around new rfcomm_closed."""
    pos = hu_path.stat().st_size if hu_path.exists() else 0
    esp_samples: list[dict[str, Any]] = []
    live_closes: list[dict[str, Any]] = []
    prev_esp = esp_snapshot(fetch_esp(esp_host))
    if prev_esp:
        esp_samples.append(prev_esp)

    end = time.time() + seconds
    buf = ""
    while time.time() < end:
        snap = esp_snapshot(fetch_esp(esp_host))
        if snap:
            delta = {}
            if prev_esp:
                for k in ("bootGen", "hci_drops", "hci_sessions", "toHostBytes", "toCtrlBytes"):
                    if snap.get(k) != prev_esp.get(k):
                        delta[k] = {"from": prev_esp.get(k), "to": snap.get(k)}
                if snap.get("uptime") != prev_esp.get("uptime") and (
                    snap.get("bootGen") != prev_esp.get("bootGen")
                    or (isinstance(snap.get("uptime"), str) and snap["uptime"].startswith("0min"))
                ):
                    delta["uptime_reset"] = {"from": prev_esp.get("uptime"), "to": snap.get("uptime")}
            if delta:
                snap["delta_from_prev"] = delta
                esp_samples.append(snap)
            prev_esp = snap

        if hu_path.exists():
            with hu_path.open() as fh:
                fh.seek(pos)
                chunk = fh.read()
                pos = fh.tell()
            if chunk:
                buf += chunk
                while "\n" in buf:
                    line, buf = buf.split("\n", 1)
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        ev = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if ev.get("event") == "rfcomm_closed":
                        live_closes.append(
                            {
                                "close": _compact(ev),
                                "esp_at_close": prev_esp,
                            }
                        )
        time.sleep(poll_s)

    return {
        "watch_s": seconds,
        "esp_host": esp_host,
        "esp_sample_count": len(esp_samples),
        "esp_samples": esp_samples[-20:],
        "live_closes": live_closes,
    }


def build_report(
    *,
    hu: Path | None,
    events: list[dict[str, Any]] | None = None,
    live: dict[str, Any] | None = None,
    esp_once: dict[str, Any] | None = None,
) -> dict[str, Any]:
    ev = events if events is not None else (load_jsonl(hu) if hu else [])
    corr = correlate_events(ev)
    # Hypothesis hint from offline classes
    pressure = corr["by_class"].get("tx_pressure_during_etch_reply", 0)
    write11 = sum(v for k, v in corr["by_reason"].items() if "write_error:11" in k)
    hint = (
        "Many flaps during etch_reply TX → transport/ESP pressure candidate "
        "for missing phone-side replies (not Fall A)."
        if pressure or write11
        else "Few/no write_error:11-during-etch patterns in this capture."
    )
    return {
        "claim_level": "LAB P0 CORRELATION",
        "hu": str(hu) if hu else None,
        "event_count": len(ev),
        "esp_once": esp_once,
        "correlation": corr,
        "live": live,
        "hypothesis_hint": hint,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--hu", type=Path, help="HU agent jsonl")
    ap.add_argument(
        "--esp",
        action="append",
        default=[],
        help="ESP IP for /api/status (repeatable; first used for live watch)",
    )
    ap.add_argument("--watch", type=float, default=0.0, help="live watch seconds")
    ap.add_argument("--out", type=Path, help="write JSON report")
    ap.add_argument("--md", type=Path, help="optional markdown summary")
    args = ap.parse_args(argv)

    if not args.hu and not (args.esp and args.watch):
        ap.error("need --hu and/or --esp with --watch")

    events = load_jsonl(args.hu) if args.hu else []
    esp_hosts = list(args.esp or [])
    esp_once = {h: esp_snapshot(fetch_esp(h)) for h in esp_hosts} if esp_hosts else None
    if esp_once and len(esp_once) == 1:
        esp_once = next(iter(esp_once.values()))
    live = None
    if esp_hosts and args.watch > 0:
        if not args.hu:
            ap.error("--watch requires --hu jsonl to tail")
        live = watch_live(args.hu, esp_hosts[0], seconds=args.watch)
        if len(esp_hosts) > 1:
            live["esp_hosts"] = esp_hosts
            live["esp_once_all"] = {h: esp_snapshot(fetch_esp(h)) for h in esp_hosts}

    report = build_report(hu=args.hu, events=events, live=live, esp_once=esp_once)
    text = json.dumps(report, indent=2, ensure_ascii=False)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text + "\n")
    else:
        print(text)

    if args.md:
        c = report["correlation"]
        lines = [
            f"# P0 ESP/RFCOMM flap correlation",
            "",
            f"- hu: `{report.get('hu')}`",
            f"- flaps: **{c.get('flap_count')}**",
            f"- by_reason: `{c.get('by_reason')}`",
            f"- by_class: `{c.get('by_class')}`",
            f"- hint: {report.get('hypothesis_hint')}",
            "",
        ]
        if esp_once:
            lines.append(f"- esp_once: `{esp_once}`")
            lines.append("")
        for i, flap in enumerate(c.get("flaps", [])[-8:], 1):
            lines.append(
                f"{i}. ts={flap.get('ts')} reason=`{flap.get('reason')}` "
                f"class=`{flap.get('class')}` reconnect_s={flap.get('reconnect_s')}"
            )
        args.md.write_text("\n".join(lines) + "\n")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
