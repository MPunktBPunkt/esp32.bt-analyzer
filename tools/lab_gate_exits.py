#!/usr/bin/env python3
"""Harden BT0–BT15 gate exits into FACT/MEASURED/INFERENCE/UNKNOWN/NEXT TEST.

Reads live F_ONCHIP status + latest lab evidence, writes:
  docs/GATE_EXITS.md
  docs/evidence/LAB_GATE_EXITS_<UTC>.md (+ .json)

Usage:
  python3 tools/lab_gate_exits.py
"""

from __future__ import annotations

import json
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


def get_status(ip: str) -> dict:
    try:
        with urllib.request.urlopen(f"http://{ip}/api/status", timeout=5) as r:
            return json.loads(r.read().decode())
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc)}


def latest_gates() -> Path | None:
    files = sorted(EVIDENCE.glob("LAB_GATES_BT5_13_*.json"), reverse=True)
    return files[0] if files else None


def block(gate: str, fact: str, measured: str, inference: str, unknown: str, next_test: str) -> dict:
    return {
        "gate": gate,
        "FACT": fact,
        "MEASURED": measured,
        "INFERENCE": inference,
        "UNKNOWN": unknown,
        "NEXT_TEST": next_test,
    }


def main() -> int:
    utc = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    live = {k: get_status(ip) for k, ip in HOSTS.items()}
    versions = {k: (v.get("version") if isinstance(v, dict) else None) for k, v in live.items()}
    onchip = {
        k: (v.get("onchip") if isinstance(v, dict) else None) for k, v in live.items()
    }

    gates_path = latest_gates()
    gates_j: dict = {}
    if gates_path and gates_path.is_file():
        gates_j = json.loads(gates_path.read_text(encoding="utf-8"))

    g = gates_j.get("gates") or {}
    sess_dir = EVIDENCE / "sessions"
    sess_files = list(sess_dir.glob("session_*.btac")) if sess_dir.is_dir() else []

    exits = [
        block(
            "BT0",
            "esp-hub OTA/Web/NVS base present",
            f"nodes respond /api/status versions={versions}",
            "hub telemetry path reusable",
            "long-term OTA reliability under BT load",
            "keep flash_lab_ota in CI smoke",
        ),
        block(
            "BT1",
            "ESP32-S3 has on-chip BLE controller; ESP32 has Classic+BLE",
            f".88 ready={ (onchip.get('88') or {}).get('ready') } · .87 ready={(onchip.get('87') or {}).get('ready')}",
            "VHCI host can drive controller without USB dongle",
            "silicon errata under continuous HCI flood",
            "watch init_fail after mem_release regressions",
        ),
        block(
            "BT2",
            "HCI cmd/evt is the host↔controller contract",
            f"bdAddr pins: {[ (onchip.get(k) or {}).get('bdAddr') for k in HOSTS ]}",
            "event mask + reset path sufficient for lab",
            "vendor events not decoded",
            "extend event decode only when a gate needs it",
        ),
        block(
            "BT3",
            "Raw HCI frames are L1 (not Air)",
            f"capture capacity={(live.get('88') or {}).get('capture', {}).get('capacity') if isinstance(live.get('88'), dict) else None}",
            "ring + VHCI capture adequate for lab bursts",
            "absolute clock sync across nodes",
            "keep LINKTYPE 201 claims explicit",
        ),
        block(
            "BT4",
            "BTAC v1 framing on TCP :9753",
            f"BT4 ok={ (g.get('BT4') or {}).get('ok') } frames={(g.get('BT4') or {}).get('frames') if False else (g.get('BT6') or {}).get('frames')}",
            "CRC framing lossless enough for lab",
            "multi-client BTAC fan-out",
            "session UI + download on collector",
        ),
        block(
            "BT5",
            "S3 has PSRAM usable for capture ring",
            f"BT5={g.get('BT5')}",
            "512-slot ring avoids host drops in lab",
            "ESP32 (no PSRAM) under long Classic flood",
            "keep fillPct in status",
        ),
        block(
            "BT6",
            "drops_delta==0 is lab lossless claim only",
            f"BT6={g.get('BT6')}",
            "lab traffic pattern does not overflow ring",
            "production multi-hour soak",
            "BT12 long capture remains the soak pin",
        ),
        block(
            "BT7",
            "JSONL is a Debian-side decode of HCI frames",
            f"BT7={g.get('BT7')}",
            "decoder matches BTAC CRC + seq",
            "full HCI opcode atlas",
            "keep --stats off stdout pollution",
        ),
        block(
            "BT8",
            "PCAPNG LINKTYPE 201 = Bluetooth HCI H4",
            f"BT8={g.get('BT8')}",
            "Wireshark can open lab exports",
            "Air LINKTYPE must never be claimed here",
            "reject any RF label on this artifact",
        ),
        block(
            "BT9",
            "LE Connect is GAP Central↔Peripheral over on-chip radio (still L1 evidence)",
            f"BT9={g.get('BT9')}",
            "connect path sufficient for L2 ATT probe",
            "bonding / privacy / multi-conn",
            "GATT read-name after connect (thin L2)",
        ),
        block(
            "BT10",
            "Classic BR/EDR only on ESP32 (.87), not S3",
            f"BT10={g.get('BT10')} classicName={(onchip.get('87') or {}).get('classicName')}",
            "Write_Local_Name + Scan_Enable deepen discoverable identity",
            "Classic×Classic peer (single Classic board in lab)",
            "optional second Classic ESP or phone inquiry",
        ),
        block(
            "BT11",
            "Second ESP is a lab stimulus peer, not MITM",
            f"BT11={g.get('BT11')}",
            "advertise/scan symmetry holds in apartment RF",
            "interference from foreign advertisers",
            "keep peer BD_ADDR pinned in evidence",
        ),
        block(
            "BT12",
            "Long capture is duration+frame count, not Air soak",
            f"BT12={g.get('BT12')}",
            "BTAC session survives minutes of traffic",
            "hour-scale continuous",
            "collector session manager for operator runs",
        ),
        block(
            "BT13",
            "WiFi STA + BTDM coexist on same chip",
            f"BT13={g.get('BT13')}",
            "toggle stress does not brick onchip.ready",
            "AP-mode + BT simultaneous",
            "keep BT init before WiFi",
        ),
        block(
            "BT14",
            "technology-audit SCOPE/STATUS/INVENTORY exist for this project",
            f"BT14={g.get('BT14')} · GATE_EXITS refreshed {utc}",
            "local pack ready for external reviewer",
            "external CI sign-off stamp",
            "reviewer marks STATUS.md green in technology-audit",
        ),
        block(
            "BT15",
            "RF/Air is out of scope for esp32.bt-analyzer",
            "docs/BT15_RF_AIR.md status=deferred",
            "HCI must not be relabeled as sniffer",
            "stakeholder need + named RF instrument",
            "open separate repo/scope when Air is required",
        ),
    ]

    # L2 probe note (post-BT9 capability, not a numbered gate)
    l2 = {
        "claim": "att_read_by_type_2a00_over_hci_acl",
        "layer": "L2",
        "not": "Air FACT / full GATT stack",
        "api": "/api/bt/gatt/read-name",
        "status_field": "onchip.gattName",
    }

    payload = {
        "utc": utc,
        "topology": "F_ONCHIP",
        "versions": versions,
        "onchip": onchip,
        "latest_gates_evidence": str(gates_path.relative_to(ROOT)) if gates_path else None,
        "session_captures": len(sess_files),
        "l2_probe": l2,
        "exits": exits,
        "claim_boundary": {
            "HCI_eq_Air": "REJECTED",
            "Classic_on_S3": "REJECTED",
            "thin_ATT_eq_full_GATT": "REJECTED",
        },
    }

    EVIDENCE.mkdir(parents=True, exist_ok=True)
    (EVIDENCE / "sessions").mkdir(parents=True, exist_ok=True)
    json_path = EVIDENCE / f"LAB_GATE_EXITS_{utc}.json"
    md_path = EVIDENCE / f"LAB_GATE_EXITS_{utc}.md"
    latest_md = DOCS / "GATE_EXITS.md"

    json_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    lines = [
        f"# Gate exits — MEASURED pack ({utc})",
        "",
        f"**Topology:** F_ONCHIP · **FW:** `.88` {versions.get('88')} · `.89` {versions.get('89')} · `.87` {versions.get('87')}",
        f"**Source gates:** `{payload['latest_gates_evidence']}`",
        f"**Raw:** [`{json_path.name}`](evidence/{json_path.name})",
        "",
        "Classification: **FACT** · **MEASURED** · **INFERENCE** · **UNKNOWN** · **NEXT TEST**",
        "",
        "| Gate | FACT | MEASURED | UNKNOWN | NEXT TEST |",
        "|------|------|----------|---------|-----------|",
    ]
    for e in exits:
        lines.append(
            f"| {e['gate']} | {e['FACT'][:48]} | `{json.dumps(e['MEASURED'], ensure_ascii=False)[:70]}` | {e['UNKNOWN'][:40]} | {e['NEXT_TEST'][:40]} |"
        )
    lines += [
        "",
        "## Claim boundary",
        "",
        "| Claim | Status |",
        "|-------|--------|",
        "| HCI = RF/Air | **REJECTED** |",
        "| Classic on ESP32-S3 on-chip | **REJECTED** |",
        "| Thin ATT name read = full GATT | **REJECTED** (L2 over HCI ACL only) |",
        "",
        "## L2 probe (bounded)",
        "",
        f"- API `{l2['api']}` → status `{l2['status_field']}`",
        f"- Layer **{l2['layer']}** · {l2['not']}",
        "",
        "## BT15",
        "",
        "Deferred — see [`BT15_RF_AIR.md`](BT15_RF_AIR.md).",
        "",
    ]
    body = "\n".join(lines) + "\n"
    md_path.write_text(body, encoding="utf-8")
    # Stable docs/GATE_EXITS.md uses relative links from docs/
    stable = body.replace(f"](evidence/{json_path.name})", f"](evidence/{json_path.name})")
    latest_md.write_text(stable, encoding="utf-8")

    print(
        json.dumps(
            {
                "ok": True,
                "md": str(latest_md.relative_to(ROOT)),
                "evidence_md": str(md_path.relative_to(ROOT)),
                "json": str(json_path.relative_to(ROOT)),
                "versions": versions,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
