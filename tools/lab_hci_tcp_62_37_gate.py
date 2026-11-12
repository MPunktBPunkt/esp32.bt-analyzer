#!/usr/bin/env python3
"""62-vs-37 kB/s gate — reproduce short-window peak vs sustained ACL mean.

Prior claims:
  A1A5:  min→none ~62 kB/s live / ~41.5 effective
  sweeps: none sustained ~36–39 kB/s, inst peaks ~42–45

This run answers whether ~62 is a real sustained rate or a short-window /
UI-sampling artefact. Uses ESP↔ESP l2test 672 B via HCI TCP (.131 → .87).

Run on BlueZ host (.108):
  scp tools/lab_hci_tcp_62_37_gate.py root@192.168.178.108:/tmp/
  ssh root@192.168.178.108 'SWEEP_DUR=60 python3 /tmp/lab_hci_tcp_62_37_gate.py'
"""

from __future__ import annotations

import json
import os
import signal
import subprocess
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

BD131, BD87 = "C8:C9:A3:CB:7B:0A", "C8:C9:A3:CB:37:96"
IP131, IP87 = "192.168.178.131", "192.168.178.87"
DUR = int(os.environ.get("SWEEP_DUR", "60"))
SAMPLE_S = float(os.environ.get("SAMPLE_S", "2"))
STAMP = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
OUT = os.environ.get("GATE_OUT", f"/tmp/hci_tcp_62_37_gate_{STAMP}.json")

# Gate thresholds (kB/s, agent toCtrl on .131 / toHost on .87)
SUSTAINED_NONE_LO, SUSTAINED_NONE_HI = 30.0, 45.0
PEAK_NOTE = 55.0  # ≥ this → "62-class short window observed"


def sh(cmd: str, timeout: float | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)


def status(ip: str, tries: int = 5) -> dict:
    last = None
    for _ in range(tries):
        try:
            j = json.load(urllib.request.urlopen(f"http://{ip}/api/status", timeout=10))
            h = j.get("hciAgent") or {}
            w = j.get("wifi") or {}
            keys = (
                "ready",
                "client",
                "wifiPs",
                "toCtrlBytes",
                "toHostBytes",
                "toCtrlPkts",
                "toHostPkts",
                "drops",
                "ringPeak",
                "ringUsed",
                "ringBytes",
                "rttLastUs",
                "rttMaxUs",
                "rttSamples",
            )
            return {
                "version": j.get("version"),
                "rssi": j.get("rssi"),
                "wifi": w,
                **{k: h.get(k) for k in keys},
            }
        except Exception as exc:  # noqa: BLE001
            last = exc
            time.sleep(0.8)
    raise RuntimeError(f"{ip}: {last}")


def setps(mode: str) -> None:
    for ip in (IP131, IP87):
        data = urllib.parse.urlencode({"mode": mode}).encode()
        urllib.request.urlopen(
            urllib.request.Request(f"http://{ip}/api/hci/wifi_ps", data=data, method="POST"),
            timeout=10,
        ).read()
    print(f"wifi_ps → {mode}", flush=True)


def find_hci(bd: str) -> str:
    out = sh("hciconfig -a").stdout
    for blk in out.split("\n\n"):
        if bd.lower() in blk.lower():
            return blk.strip().split(":")[0]
    raise RuntimeError(f"hci for {bd} not found")


def ensure(h: str) -> None:
    sh(f"hciconfig {h} up; hciconfig {h} piscan; hciconfig {h} sspmode 1")


def kill_l2() -> None:
    sh("pkill -f l2test || true")
    time.sleep(0.4)


def drop_acls() -> None:
    for h in ("hci0", "hci1", "hci2", "hci3", "hci4"):
        r = sh(f"hcitool -i {h} con 2>/dev/null")
        for line in r.stdout.splitlines():
            for p in line.split():
                if p.count(":") == 5:
                    sh(f"hcitool -i {h} dc {p} 2>/dev/null")
    kill_l2()
    time.sleep(0.8)


def radio_reset() -> None:
    """Clear sticky wifi_ps throttle state via adapter power cycle."""
    print("radio_reset (power cycle both ESP controllers)", flush=True)
    drop_acls()
    for bd in (BD131, BD87):
        sh(f"bluetoothctl -- select {bd} >/dev/null; bluetoothctl -- power off >/dev/null")
    time.sleep(2)
    for bd in (BD131, BD87):
        sh(f"bluetoothctl -- select {bd} >/dev/null; bluetoothctl -- power on >/dev/null")
    time.sleep(2)
    setps("min")
    time.sleep(1)


def window_rates(samples: list[dict], field_ip: str, field_bytes: str) -> list[dict]:
    out = []
    for i in range(1, len(samples)):
        dt = samples[i]["t"] - samples[i - 1]["t"]
        if dt <= 0:
            continue
        db = samples[i][field_ip][field_bytes] - samples[i - 1][field_ip][field_bytes]
        out.append(
            {
                "t": samples[i]["t"],
                "dt": round(dt, 2),
                "kBps": round(db / dt / 1024, 2),
                "ps": samples[i][field_ip].get("wifiPs"),
                "rssi": samples[i][field_ip].get("rssi"),
                "switched_to": samples[i].get("switched_to"),
            }
        )
    return out


def summarize_windows(wins: list[dict], after_t: float | None = None) -> dict:
    sel = [w for w in wins if after_t is None or w["t"] >= after_t]
    if not sel:
        return {"n": 0, "mean": None, "max": None, "p50": None, "ge55": 0, "ge45": 0}
    vals = sorted(w["kBps"] for w in sel)
    return {
        "n": len(vals),
        "mean": round(sum(vals) / len(vals), 2),
        "max": vals[-1],
        "p50": vals[len(vals) // 2],
        "ge55": sum(1 for v in vals if v >= PEAK_NOTE),
        "ge45": sum(1 for v in vals if v >= 45.0),
    }


def run_acl(tag: str, start_ps: str, seconds: int = DUR, mid: tuple | None = None) -> dict:
    drop_acls()
    setps("min")
    time.sleep(0.5)
    setps(start_ps)
    time.sleep(1)
    h1, h2 = find_hci(BD131), find_hci(BD87)
    ensure(h1)
    ensure(h2)
    print(f"=== {tag} {h1}->{h2} start={start_ps} mid={mid} sample={SAMPLE_S}s ===", flush=True)

    rx = subprocess.Popen(
        f"timeout {seconds + 15} l2test -i {h2} -r -b 672 >/tmp/gate_rx.txt 2>&1",
        shell=True,
        preexec_fn=os.setsid,
    )
    time.sleep(2)
    b131, b87 = status(IP131), status(IP87)
    t0 = time.time()
    switched = False
    switch_t = None
    samples: list[dict] = []
    tx = subprocess.Popen(
        f"timeout {seconds + 8} l2test -i {h1} -s -b 672 -M {BD87} >/tmp/gate_tx.txt 2>&1",
        shell=True,
        preexec_fn=os.setsid,
    )
    while time.time() - t0 < seconds:
        time.sleep(SAMPLE_S)
        s131, s87 = status(IP131), status(IP87)
        entry = {"t": round(time.time() - t0, 2), "131": s131, "87": s87}
        if mid and not switched and (time.time() - t0) >= mid[0]:
            setps(mid[1])
            switched = True
            switch_t = entry["t"]
            entry["switched_to"] = mid[1]
        samples.append(entry)

    for p in (tx, rx):
        try:
            os.killpg(os.getpgid(p.pid), signal.SIGTERM)
        except Exception:
            pass
    time.sleep(0.5)
    kill_l2()
    a131, a87 = status(IP131), status(IP87)
    dt = max(0.001, time.time() - t0)

    def rates(b, a):
        return {
            "kBps_toCtrl": round((a["toCtrlBytes"] - b["toCtrlBytes"]) / dt / 1024, 2),
            "kBps_toHost": round((a["toHostBytes"] - b["toHostBytes"]) / dt / 1024, 2),
            "pps_toCtrl": round((a["toCtrlPkts"] - b["toCtrlPkts"]) / dt, 2),
            "mean_pkt": round(
                (a["toCtrlBytes"] - b["toCtrlBytes"])
                / max(1, (a["toCtrlPkts"] - b["toCtrlPkts"])),
                1,
            ),
            "drops": a["drops"] - b["drops"],
        }

    r131, r87 = rates(b131, a131), rates(b87, a87)
    inst_ctrl = window_rates(samples, "131", "toCtrlBytes")
    inst_host = window_rates(samples, "87", "toHostBytes")
    post = switch_t if switch_t is not None else 0.0

    # Aggregate post-switch agent bytes (fairer than full-run mean when mid-switch).
    post_samples = [s for s in samples if s["t"] >= post]
    post_mean_ctrl = None
    post_mean_host = None
    if len(post_samples) >= 2:
        dtp = post_samples[-1]["t"] - post_samples[0]["t"]
        if dtp > 0:
            db_c = post_samples[-1]["131"]["toCtrlBytes"] - post_samples[0]["131"]["toCtrlBytes"]
            db_h = post_samples[-1]["87"]["toHostBytes"] - post_samples[0]["87"]["toHostBytes"]
            post_mean_ctrl = round(db_c / dtp / 1024, 2)
            post_mean_host = round(db_h / dtp / 1024, 2)

    tx_text = open("/tmp/gate_tx.txt").read()
    ok = ("Connected" in tx_text) or r131["kBps_toCtrl"] > 2
    res = {
        "tag": tag,
        "start_ps": start_ps,
        "mid": mid,
        "ok": ok,
        "elapsed_s": round(dt, 2),
        "switch_t": switch_t,
        "wifi": {"131": a131.get("wifi"), "87": a87.get("wifi")},
        "rssi": [a131.get("rssi"), a87.get("rssi")],
        "rates_131": r131,
        "rates_87": r87,
        "post_switch_mean_kBps": {"toCtrl": post_mean_ctrl, "toHost": post_mean_host},
        "windows_ctrl": summarize_windows(inst_ctrl),
        "windows_ctrl_post": summarize_windows(inst_ctrl, after_t=post),
        "windows_host": summarize_windows(inst_host),
        "windows_host_post": summarize_windows(inst_host, after_t=post),
        "ringPeak": [a131.get("ringPeak"), a87.get("ringPeak")],
        "ringBytes": [a131.get("ringBytes"), a87.get("ringBytes")],
        "rttMaxUs": [a131.get("rttMaxUs"), a87.get("rttMaxUs")],
        "inst_ctrl": inst_ctrl,
        "tx_tail": tx_text[-500:],
    }
    print(
        f"  sustained ctrl/host={r131['kBps_toCtrl']}/{r87['kBps_toHost']} "
        f"post={post_mean_ctrl}/{post_mean_host} "
        f"win_max={res['windows_ctrl']['max']}/{res['windows_host']['max']} "
        f"ok={ok} drops={r131['drops']}/{r87['drops']}",
        flush=True,
    )
    return res


def verdict(tests: list[dict]) -> dict:
    t4 = next((t for t in tests if t["tag"] == "T4_min_to_none"), None)
    t3 = next((t for t in tests if t["tag"] == "T3_none"), None)
    focus = t4 or t3
    if not focus or not focus.get("ok"):
        return {
            "gate": "62_vs_37",
            "result": "FAIL",
            "reason": "ACL/l2test did not connect or transfer",
        }

    sustained = focus["post_switch_mean_kBps"]["toCtrl"] or focus["rates_131"]["kBps_toCtrl"]
    peak = focus["windows_ctrl_post"]["max"] or focus["windows_ctrl"]["max"] or 0
    drops = focus["rates_131"]["drops"] + focus["rates_87"]["drops"]
    ring = max(focus["ringPeak"] or [0])
    ring_cap = (focus.get("ringBytes") or [24576])[0] or 24576

    in_band = SUSTAINED_NONE_LO <= sustained <= SUSTAINED_NONE_HI
    peak_is_62_class = peak >= PEAK_NOTE
    queue_ok = drops == 0 and ring < 0.5 * ring_cap

    if in_band and queue_ok and not peak_is_62_class:
        result = "PASS_37"
        reason = (
            f"sustained ~{sustained} kB/s under none; short-window max {peak} kB/s "
            f"(no ≥{PEAK_NOTE} 62-class window). Accept ~37–39 as coex budget."
        )
    elif in_band and queue_ok and peak_is_62_class:
        result = "PASS_EXPLAINED"
        reason = (
            f"sustained ~{sustained} kB/s; short-window max {peak} kB/s explains prior ~62 "
            f"as sampling artefact, not sustainable rate."
        )
    elif sustained >= PEAK_NOTE and queue_ok:
        result = "PASS_62"
        reason = f"sustained ~{sustained} kB/s reproduces the higher figure — revisit prior 37 claim."
    else:
        result = "FAIL"
        reason = (
            f"unexpected sustained={sustained} peak={peak} drops={drops} "
            f"ringPeak={ring}/{ring_cap}"
        )

    return {
        "gate": "62_vs_37",
        "result": result,
        "reason": reason,
        "sustained_kBps": sustained,
        "peak_window_kBps": peak,
        "drops": drops,
        "ringPeak": ring,
        "ringBytes": ring_cap,
        "focus_tag": focus["tag"],
    }


def main() -> int:
    h1, h2 = find_hci(BD131), find_hci(BD87)
    print(f"hci131={h1} hci87={h2} dur={DUR}s sample={SAMPLE_S}s -> {OUT}", flush=True)
    radio_reset()
    base = {"131": status(IP131), "87": status(IP87)}
    print("baseline", base["131"].get("wifiPs"), base["131"].get("rssi"), base["87"].get("rssi"), flush=True)

    report = {
        "utc": STAMP,
        "gate": "62_vs_37",
        "fw": {"131": base["131"]["version"], "87": base["87"]["version"]},
        "baseline": base,
        "duration_s": DUR,
        "sample_s": SAMPLE_S,
        "tests": [],
        "claim": "short-window peak vs sustained mean under wifi_ps none",
    }

    # Focused plan: cold none + the disputed recipe min→none.
    plan = [
        ("T3_none", "none", None),
        ("T4_min_to_none", "min", (10, "none")),
    ]
    for name, ps, mid in plan:
        report["tests"].append(run_acl(name, ps, DUR, mid))
        setps("min")
        time.sleep(2)

    setps("min")
    drop_acls()
    report["final"] = {"131": status(IP131), "87": status(IP87)}
    report["verdict"] = verdict(report["tests"])
    Path(OUT).write_text(json.dumps(report, indent=2) + "\n")
    print("WROTE", OUT, flush=True)
    print("VERDICT", json.dumps(report["verdict"]), flush=True)
    for t in report["tests"]:
        print(
            f"SUM {t['tag']}: sust={t['rates_131']['kBps_toCtrl']}/{t['rates_87']['kBps_toHost']} "
            f"post={t['post_switch_mean_kBps']} "
            f"win_max={t['windows_ctrl']['max']}/{t['windows_host']['max']} ok={t['ok']}",
            flush=True,
        )
    return 0 if report["verdict"]["result"].startswith("PASS") else 1


if __name__ == "__main__":
    raise SystemExit(main())
