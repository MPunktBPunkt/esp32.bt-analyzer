#!/usr/bin/env python3
"""Harden BT0–BT16 gate exits into FACT/MEASURED/INFERENCE/UNKNOWN/NEXT TEST.

Source of truth for BT4–BT14 MEASURED values: the latest *gate-result* JSON
  docs/evidence/LAB_GATES_BT5_13_<UTC>.json
(NOT *_status_before.json / *_status_after.json).

Usage:
  python3 tools/lab_gate_exits.py
  python3 tools/lab_gate_exits.py --gates docs/evidence/LAB_GATES_….json
"""

from __future__ import annotations

import argparse
import json
import re
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "docs" / "evidence"
DOCS = ROOT / "docs"
HOSTS = {
    "88": "192.168.178.88",
    "89": "192.168.178.89",
    "87": "192.168.178.87",
}

# Strict gate-result stem: LAB_GATES_BT5_13_YYYYMMDDTHHMMSSZ.json
_GATE_RESULT_RE = re.compile(r"^LAB_GATES_BT5_13_\d{8}T\d{6}Z\.json$")
_BT16_RE = re.compile(r"^LAB_BT16_\d{8}T\d{6}Z\.json$")
_BT18_RE = re.compile(r"^LAB_BT18_GATT_\d{8}T\d{6}Z\.json$")


def get_status(ip: str) -> dict:
    try:
        with urllib.request.urlopen(f"http://{ip}/api/status", timeout=5) as r:
            return json.loads(r.read().decode())
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc)}


def latest_gate_result() -> Path | None:
    cands = [
        p
        for p in EVIDENCE.glob("LAB_GATES_BT5_13_*.json")
        if _GATE_RESULT_RE.match(p.name)
    ]
    return sorted(cands, reverse=True)[0] if cands else None


def latest_bt16() -> Path | None:
    cands = [p for p in EVIDENCE.glob("LAB_BT16_*.json") if _BT16_RE.match(p.name)]
    return sorted(cands, reverse=True)[0] if cands else None


def latest_bt18() -> Path | None:
    cands = [p for p in EVIDENCE.glob("LAB_BT18_GATT_*.json") if _BT18_RE.match(p.name)]
    return sorted(cands, reverse=True)[0] if cands else None


def block(gate: str, fact: str, measured: str, inference: str, unknown: str, next_test: str) -> dict:
    return {
        "gate": gate,
        "FACT": fact,
        "MEASURED": measured,
        "INFERENCE": inference,
        "UNKNOWN": unknown,
        "NEXT_TEST": next_test,
    }


def gstat(g: dict, key: str) -> str:
    entry = g.get(key)
    if entry is None:
        return "missing_in_gate_result"
    if isinstance(entry, dict):
        return f"ok={entry.get('ok')} detail={json.dumps({k: entry.get(k) for k in list(entry)[:6]}, ensure_ascii=False)[:100]}"
    return str(entry)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--gates", type=Path, help="Explicit gate-result JSON")
    args = ap.parse_args()

    utc = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    live = {k: get_status(ip) for k, ip in HOSTS.items()}
    versions = {k: (v.get("version") if isinstance(v, dict) else None) for k, v in live.items()}
    onchip = {k: (v.get("onchip") if isinstance(v, dict) else None) for k, v in live.items()}

    gates_path = args.gates if args.gates else latest_gate_result()
    gates_j: dict = {}
    if gates_path and gates_path.is_file():
        gates_j = json.loads(gates_path.read_text(encoding="utf-8"))
        # Refuse status snapshots masquerading as results
        if "_status_" in gates_path.name or "gates" not in gates_j:
            raise SystemExit(f"refusing non-gate-result file: {gates_path}")

    g = gates_j.get("gates") or {}
    bt16_path = latest_bt16()
    bt16_j: dict = {}
    if bt16_path and bt16_path.is_file():
        bt16_j = json.loads(bt16_path.read_text(encoding="utf-8"))
    bt18_path = latest_bt18()
    bt18_j: dict = {}
    if bt18_path and bt18_path.is_file():
        bt18_j = json.loads(bt18_path.read_text(encoding="utf-8"))

    sess_dir = EVIDENCE / "sessions"
    sess_files = list(sess_dir.glob("session_*.btac")) if sess_dir.is_dir() else []

    exits = [
        block("BT0", "esp-hub OTA/Web/NVS base present", f"versions={versions}", "hub path reusable", "long-term OTA under BT", "flash_lab_ota smoke"),
        block("BT1", "S3 BLE; ESP32 Classic+BLE", f".88 ready={(onchip.get('88') or {}).get('ready')} .87 ready={(onchip.get('87') or {}).get('ready')}", "VHCI without dongle", "errata under flood", "watch mem_release"),
        block("BT2", "HCI cmd/evt host↔controller", f"bd={[ (onchip.get(k) or {}).get('bdAddr') for k in HOSTS ]}", "masks+reset enough", "vendor events", "decode on demand"),
        block("BT3", "Raw HCI is L1 not Air", f"capacity={(live.get('88') or {}).get('capture', {}).get('capacity') if isinstance(live.get('88'), dict) else None}", "ring adequate", "absolute sync", "LINKTYPE 201"),
        block("BT4", "BTAC v1 :9753", gstat(g, "BT4"), "CRC framing lab-ok", "multi-client", "session UI"),
        block("BT5", "S3 PSRAM capture ring", gstat(g, "BT5"), "512 slots", "ESP32 long flood", "fillPct"),
        block("BT6", "Ring drops_delta vs file_gaps split", gstat(g, "BT6"), "session counters", "multi-hour soak", "lab_gap_classify"),
        block("BT7", "JSONL HCI decode", gstat(g, "BT7"), "CRC+seq", "opcode atlas", "--stats"),
        block("BT8", "PCAPNG LINKTYPE 201", gstat(g, "BT8"), "Wireshark opens", "never Air LINKTYPE", "reject RF label"),
        block("BT9", "LE Connect Central↔Peripheral", gstat(g, "BT9"), "L2 probe path", "bonding", "gatt read-name"),
        block("BT10", "Classic only on .87", f"{gstat(g, 'BT10')} name={(onchip.get('87') or {}).get('classicName')}", "Write_Local_Name", "Classic×Classic", "second Classic/phone"),
        block("BT11", "Second ESP stimulus peer", gstat(g, "BT11"), "adv/scan", "ambient RF", "pin peer BD"),
        block("BT12", "Long capture duration+frames", gstat(g, "BT12"), "minutes OK", "hour soak", "session manager"),
        block("BT13", "WiFi STA + BTDM coex smoke", gstat(g, "BT13"), "toggle ok", "AP+BT", "BT before WiFi"),
        block("BT14", "technology-audit pack present", gstat(g, "BT14"), "ready for review", "external stamp", "STATUS green"),
        block("BT15", "RF/Air out of scope", "docs/BT15_RF_AIR.md deferred", "no sniffer label", "named RF instrument", "separate repo"),
        block(
            "BT16",
            "ATT Notify/Write is L2 over HCI ACL only",
            f"latest={bt16_path.name if bt16_path else None} "
            f"capability={bt16_j.get('capability_ok')} benchmark={bt16_j.get('benchmark_ok')} "
            f"appTx={(onchip.get('88') or {}).get('appTxBps')} appRx={(onchip.get('88') or {}).get('appRxBps')}",
            "CAPABILITY≠BENCHMARK until loss/gaps zero",
            "full matrix soak",
            "lab_bt16_throughput.py --benchmark",
        ),
        block(
            "BT18",
            "GATT Client Flavor = STIMULUS discovery/CCCD over HCI",
            f"latest={bt18_path.name if bt18_path else None} "
            f"capability={bt18_j.get('capability_ok')} benchmark={bt18_j.get('benchmark_ok')} "
            f"flavor={(live.get('88') or {}).get('flavor', {}).get('state') if isinstance(live.get('88'), dict) else None}",
            "bounded MVP ≠ full GATT/HOGP/FTMS",
            "foreign peer discovery",
            "lab_gatt_client.py → HOGP Flavor",
        ),
    ]

    payload = {
        "utc": utc,
        "topology": "F_ONCHIP",
        "versions": versions,
        "onchip": onchip,
        "gate_result_source": str(gates_path.relative_to(ROOT)) if gates_path else None,
        "bt16_source": str(bt16_path.relative_to(ROOT)) if bt16_path else None,
        "bt18_source": str(bt18_path.relative_to(ROOT)) if bt18_path else None,
        "session_captures": len(sess_files),
        "source_policy": "gate_result_json_only_not_status_snapshots",
        "exits": exits,
        "claim_boundary": {
            "HCI_eq_Air": "REJECTED",
            "Classic_on_S3": "REJECTED",
            "thin_ATT_eq_full_GATT": "REJECTED",
            "gatt_client_mvp_eq_full_GATT": "REJECTED",
            "kbps_as_benchmark_without_loss_split": "REJECTED",
        },
    }

    EVIDENCE.mkdir(parents=True, exist_ok=True)
    json_path = EVIDENCE / f"LAB_GATE_EXITS_{utc}.json"
    md_path = EVIDENCE / f"LAB_GATE_EXITS_{utc}.md"
    latest_md = DOCS / "GATE_EXITS.md"
    json_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    lines = [
        f"# Gate exits — MEASURED pack ({utc})",
        "",
        f"**Topology:** F_ONCHIP · **FW:** `.88` {versions.get('88')} · `.89` {versions.get('89')} · `.87` {versions.get('87')}",
        f"**Gate result source:** `{payload['gate_result_source']}`",
        f"**BT16 source:** `{payload['bt16_source']}`",
        f"**BT18 source:** `{payload.get('bt18_source')}`",
        f"**Raw:** [`{json_path.name}`](evidence/{json_path.name})",
        "",
        "Classification: **FACT** · **MEASURED** · **INFERENCE** · **UNKNOWN** · **NEXT TEST**",
        "",
        "| Gate | FACT | MEASURED | UNKNOWN | NEXT TEST |",
        "|------|------|----------|---------|-----------|",
    ]
    for e in exits:
        lines.append(
            f"| {e['gate']} | {e['FACT'][:48]} | `{str(e['MEASURED'])[:90]}` | {e['UNKNOWN'][:40]} | {e['NEXT_TEST'][:40]} |"
        )
    lines += [
        "",
        "## Claim boundary",
        "",
        "| Claim | Status |",
        "|-------|--------|",
        "| HCI = RF/Air | **REJECTED** |",
        "| Classic on ESP32-S3 | **REJECTED** |",
        "| Thin ATT = full GATT | **REJECTED** |",
        "| kB/s without loss split = benchmark | **REJECTED** |",
        "",
        "## Source policy",
        "",
        "`lab_gate_exits.py` reads only `LAB_GATES_BT5_13_<UTC>.json` gate results — never `*_status_before/after.json`.",
        "",
    ]
    body = "\n".join(lines) + "\n"
    md_path.write_text(body, encoding="utf-8")
    latest_md.write_text(body, encoding="utf-8")
    print(
        json.dumps(
            {
                "ok": True,
                "md": str(latest_md.relative_to(ROOT)),
                "gate_result_source": payload["gate_result_source"],
                "bt16_source": payload["bt16_source"],
                "versions": versions,
                "gates_present": sorted(g.keys()),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
