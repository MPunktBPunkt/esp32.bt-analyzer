#!/usr/bin/env python3
"""Batch N× BCL-only dual-ESP holds; summarize write_error:11 / WATCHDOG_MISS."""

from __future__ import annotations

import argparse
import json
import subprocess
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def esp_pre() -> dict:
    out = {}
    for tag, ip in (("131", "192.168.178.131"), ("87", "192.168.178.87")):
        try:
            d = json.load(urllib.request.urlopen(f"http://{ip}/api/status", timeout=4))
            ha = d.get("hciAgent") or {}
            out[tag] = {
                "bootGen": d.get("bootGen"),
                "drops": ha.get("drops"),
                "uptime": d.get("uptime"),
            }
        except Exception as e:  # noqa: BLE001
            out[tag] = {"error": str(e)}
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("-n", type=int, default=5)
    ap.add_argument("--hold", type=float, default=90.0)
    ap.add_argument(
        "--out-dir",
        type=Path,
        default=ROOT / "docs" / "evidence" / f"LAB_P0_WRITE11_BATCH_{utc_stamp()}",
    )
    args = ap.parse_args()
    out = args.out_dir
    out.mkdir(parents=True, exist_ok=True)
    rows: list[dict] = []

    for i in range(1, args.n + 1):
        stamp = utc_stamp()
        local = out / f"run{i:02d}_{stamp}.json"
        print(f"=== RUN {i}/{args.n} hold={args.hold}s -> {local.name}", flush=True)
        pre = esp_pre()
        p = subprocess.run(
            [
                "python3",
                str(ROOT / "tools" / "lab_p0_dual_esp_hold.py"),
                "--hold",
                str(args.hold),
                "--out",
                str(local),
            ],
            cwd=str(ROOT),
        )
        try:
            data = json.loads(local.read_text())
        except Exception:
            data = {"parse_error": True, "rc": p.returncode}
        hold = data.get("hold") or {}
        closes = [
            e
            for e in (data.get("hu_key_events") or [])
            if e.get("event") == "rfcomm_closed"
        ]
        row = {
            "run": i,
            "rc": p.returncode,
            "pre": pre,
            "hold_ok": hold.get("ok"),
            "mode": hold.get("mode"),
            "hold_s": hold.get("hold_s"),
            "abort_reason": hold.get("abort_reason"),
            "wait_class": hold.get("wait_class"),
            "rhmi_state": hold.get("rhmi_state"),
            "send_err": hold.get("send_err"),
            "phone_events": hold.get("phone_events"),
            "hu_events": data.get("hu_events"),
            "hu_key_events": data.get("hu_key_events"),
            "hu_close_reasons": [e.get("reason") for e in closes],
            "esp_diag_pre": data.get("esp_diag_pre"),
            "esp_diag_post": data.get("esp_diag_post"),
            "file": local.name,
        }
        rows.append(row)
        print(
            "RESULT",
            json.dumps(
                {
                    k: row[k]
                    for k in (
                        "run",
                        "hold_ok",
                        "abort_reason",
                        "wait_class",
                        "hu_close_reasons",
                        "hold_s",
                        "esp_diag_post",
                    )
                },
                ensure_ascii=False,
            ),
            flush=True,
        )
        time.sleep(3)

    summary = {
        "n": args.n,
        "hold_s": args.hold,
        "write11_count": sum(
            1 for r in rows if "write_error:11" in (r.get("hu_close_reasons") or [])
        ),
        "watchdog_miss_count": sum(
            1
            for r in rows
            if (r.get("wait_class") or "") == "WATCHDOG_MISS_NO_ETCH_REPLY"
            or "WATCHDOG" in str(r.get("abort_reason") or "")
            or "wd_echo" in str(r.get("abort_reason") or "")
        ),
        "bootGen_bumps": [
            {
                "run": r["run"],
                "pre": r.get("esp_diag_pre"),
                "post": r.get("esp_diag_post"),
            }
            for r in rows
            if (r.get("esp_diag_pre") or {}).get("131", {}).get("bootGen")
            != (r.get("esp_diag_post") or {}).get("131", {}).get("bootGen")
            or (r.get("esp_diag_pre") or {}).get("87", {}).get("bootGen")
            != (r.get("esp_diag_post") or {}).get("87", {}).get("bootGen")
        ],
        "rows": rows,
    }
    (out / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    lines = [
        f"# LAB P0 write11 batch — {args.n}× BCL-only @ {args.hold}s",
        "",
        f"- write_error:11 closes: **{summary['write11_count']}/{args.n}**",
        f"- WATCHDOG_MISS: **{summary['watchdog_miss_count']}/{args.n}**",
        f"- bootGen bumps: **{len(summary['bootGen_bumps'])}**",
        "",
        "| Run | hold_s | wait_class | hu_close | bootGen post |",
        "|-----|--------|------------|----------|--------------|",
    ]
    for r in rows:
        post = r.get("esp_diag_post") or {}
        bg = (
            f"{(post.get('131') or {}).get('bootGen')}/"
            f"{(post.get('87') or {}).get('bootGen')}"
        )
        closes = ",".join(r.get("hu_close_reasons") or [])
        lines.append(
            f"| {r['run']} | {r.get('hold_s')} | `{r.get('wait_class')}` "
            f"| `{closes}` | {bg} |"
        )
    (out / "SUMMARY.md").write_text("\n".join(lines) + "\n")
    print("WROTE", out / "summary.json", out / "SUMMARY.md", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
