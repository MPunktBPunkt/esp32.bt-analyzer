#!/usr/bin/env python3
"""Coex A/B — sustained ESP↔ESP ACL per /api/hci/coex mode (fw ≥ 0.3.19).

Same l2test path and counters as lab_hci_tcp_62_37_gate.py, run once per coex
mode with wifi_ps `min` and with the min→none recipe. Answers whether telling
the coex scheduler "A2DP streaming" (or prefer BT) raises the BT share.

Run on BlueZ host (.108), both bridges up:
  scp tools/lab_hci_coex_ab.py tools/lab_hci_tcp_62_37_gate.py tools/a2dp_budget.py root@192.168.178.108:/tmp/
  ssh root@192.168.178.108 'SWEEP_DUR=45 python3 /tmp/lab_hci_coex_ab.py'
  COEX_MODES=default,a2dp  → subset
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lab_hci_tcp_62_37_gate as gate  # noqa: E402
from a2dp_budget import max_bitpool_for, wire_Bps  # noqa: E402

MODES = [m for m in os.environ.get("COEX_MODES", "default,a2dp,prefer_bt").split(",") if m]
OUT = os.environ.get("COEX_OUT", f"/tmp/hci_coex_ab_{gate.STAMP}.json")
GAIN_NOTE = 1.15


def setcoex(mode: str) -> dict:
    res = {}
    for ip in (gate.IP131, gate.IP87):
        data = urllib.parse.urlencode({"mode": mode}).encode()
        req = urllib.request.Request(f"http://{ip}/api/hci/coex", data=data, method="POST")
        try:
            res[ip] = json.load(urllib.request.urlopen(req, timeout=10))
        except urllib.error.HTTPError as exc:
            res[ip] = {"ok": False, "http": exc.code, "body": exc.read().decode(errors="replace")}
    print(f"coex → {mode}: {res}", flush=True)
    return res


def sustained(test: dict) -> float:
    post = test["post_switch_mean_kBps"]["toCtrl"]
    return post if post is not None else test["rates_131"]["kBps_toCtrl"]


def verdict(rows: list[dict]) -> dict:
    base = next((r for r in rows if r["mode"] == "default"), None)
    out = {"modes": {}, "best": None}
    best_rate = -1.0
    for r in rows:
        entry = {"min": r["min_kBps"], "none": r["none_kBps"], "api_ok": r["api_ok"]}
        if base:
            for key in ("min", "none"):
                b = base[f"{key}_kBps"] or 0
                entry[f"gain_{key}"] = round(entry[key] / b, 2) if b else None
        out["modes"][r["mode"]] = entry
        if r["api_ok"] and (r["none_kBps"] or 0) > best_rate:
            best_rate, out["best"] = r["none_kBps"], r["mode"]
    gains = [v.get(f"gain_{k}") or 0 for m, v in out["modes"].items()
             if m != "default" and v["api_ok"] for k in ("min", "none")]
    out["result"] = "COEX_HELPS" if any(g >= GAIN_NOTE for g in gains) else "NO_GAIN"
    out["best_none_kBps"] = best_rate
    bp = max_bitpool_for(best_rate) if best_rate > 0 else None
    out["sbc_bitpool_80pct"] = bp
    out["sbc_wire_kBps"] = round(wire_Bps(bp) / 1000, 1) if bp else None
    return out


def main() -> int:
    h1, h2 = gate.find_hci(gate.BD131), gate.find_hci(gate.BD87)
    print(f"hci131={h1} hci87={h2} modes={MODES} dur={gate.DUR}s -> {OUT}", flush=True)
    report = {"utc": gate.STAMP, "gate": "coex_ab", "duration_s": gate.DUR, "rows": [],
              "claim": "sustained ESP↔ESP ACL per coex mode; not an A2DP audio-quality claim"}
    for mode in MODES:
        gate.radio_reset()
        api = setcoex(mode)
        api_ok = all(v.get("ok") for v in api.values())
        t_min = gate.run_acl(f"{mode}_min", "min", gate.DUR)
        gate.setps("min")
        t_none = gate.run_acl(f"{mode}_min_to_none", "min", gate.DUR, (10, "none"))
        gate.setps("min")
        report["rows"].append({
            "mode": mode,
            "api": api,
            "api_ok": api_ok,
            "min_kBps": sustained(t_min),
            "none_kBps": sustained(t_none),
            "drops": [t_min["rates_131"]["drops"] + t_min["rates_87"]["drops"],
                      t_none["rates_131"]["drops"] + t_none["rates_87"]["drops"]],
            "tests": [t_min, t_none],
        })
        time.sleep(2)
    setcoex("default")
    gate.setps("min")
    gate.drop_acls()
    report["verdict"] = verdict(report["rows"])
    Path(OUT).write_text(json.dumps(report, indent=2) + "\n")
    print("WROTE", OUT, flush=True)
    print("\n| coex | api | min kB/s | min→none kB/s | gain min | gain none | drops |")
    print("|------|-----|----------|---------------|----------|-----------|-------|")
    for r in report["rows"]:
        v = report["verdict"]["modes"][r["mode"]]
        print(f"| {r['mode']} | {'ok' if r['api_ok'] else 'FAIL'} | {r['min_kBps']} | {r['none_kBps']} "
              f"| {v.get('gain_min')} | {v.get('gain_none')} | {r['drops']} |")
    print("VERDICT", json.dumps({k: v for k, v in report["verdict"].items() if k != "modes"}), flush=True)
    return 0 if all(r["api_ok"] for r in report["rows"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
