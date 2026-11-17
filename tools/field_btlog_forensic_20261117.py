#!/usr/bin/env python3
"""Deterministic forensic parse of Oppo/OnePlus bluetooth_*.log (F20 peer e1:b5).

Follows docs/METHODIK_LOG_FORENSIK.md:
  - full-line parse (no LLM skim)
  - forward Etch sdbm hashes from etch_codec.HASH_REGISTRY
  - peer isolation (e1:b5)
  - TX length fingerprint + RX hex dumps
  - Δt timeline
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from etch_codec import HASH_REGISTRY, etch_hash  # noqa: E402

HU_PEER = "e1:b5"
TS_RE = re.compile(r"\[11-17 (\d{2}:\d{2}:\d{2}\.\d{3})\]")
WRITE_RE = re.compile(r"PORT_WriteDataCO:\s*(\d+)\s*bytes")
DUMP_RE = re.compile(
    r"oplus_send_data_to_app_dump:.*?scn=(\d+)\s+peer=([0-9a-f:]+)\s+len=(\d+)\s+data_hex=([0-9A-Fa-f.]+)"
)
UIH_RE = re.compile(r"RFCOMM_BufDataInd: Handling UIH event, buf_len=(\d+)")
SCN_OPEN_RE = re.compile(r"scn[=:](\d+).*?(e1:b5|38304)|e1:b5.*?scn[=:](\d+)", re.I)
ADAPTER_RE = re.compile(r"\[AdapterState\]\s+(\w+)\s*:\s*entered")
A2DP_RE = re.compile(
    r"btif_a2dp_source_(start_audio|on_started|suspend|stop|startup|shutdown|restart_session)|"
    r"A2DP_CTRL_CMD_|a2dp_source.*STATE_|AVDTP|btif_av_stream",
    re.I,
)
AVRCP_RE = re.compile(r"avrcp|Avrcp|AVRC_", re.I)
HFP_RE = re.compile(r"\bAT\+[A-Z]+|HFP|Headset|bta_hf|btif_hf", re.I)
ACL_RE = re.compile(r"Connection Complete|Disconnected|ACL.*e1:b5|e1:b5.*(connect|disconnect)", re.I)
BQR_RE = re.compile(r"BluetoothQualityReport|mLsto:|mUnusedAfhChannelCount")
SCREEN_RE = re.compile(
    r"miracast|WifiDisplay|WFD|screen.?share|MediaProjection|cast.?screen|Handoff|AOA|accessory",
    re.I,
)
UID_RE = re.compile(r"app_uid=(\d+)|uid[=:](\d+)")
RFCOMM_PORT_RE = re.compile(r"rfc_port_sm_opened:.*?scn:(\d+)|PORT_DataInd.*?dlci:(\d+)|connectSocket.*?scn[=:](\d+)")

# BCL opcodes (first 2 bytes of BCL header as type)
BCL_TYPES = {
    0x0001: "INIT?",
    0x0002: "DATA",
    0x0004: "HANDSHAKE",
    0x0005: "SELECTPROTO?",
    0x0006: "DATAACK/CTRL",
}


def parse_ts(s: str) -> datetime:
    return datetime.strptime(f"2026-11-17 {s}", "%Y-%m-%d %H:%M:%S.%f")


def resolve_hash(h: int) -> str:
    return HASH_REGISTRY.get(h, f"UNKNOWN_0x{h:08x}")


def scan_etch_hashes(hex_str: str) -> list[tuple[int, str]]:
    """Find all 0386<u32BE> type tags in a hex dump (truncated OK)."""
    h = hex_str.replace("...", "").upper()
    # strip trailing incomplete nibble
    if len(h) % 2:
        h = h[:-1]
    out: list[tuple[int, str]] = []
    i = 0
    while True:
        j = h.find("0386", i)
        if j < 0 or j + 12 > len(h):
            break
        try:
            hv = int(h[j + 4 : j + 12], 16)
        except ValueError:
            i = j + 4
            continue
        out.append((hv, resolve_hash(hv)))
        i = j + 12
    return out


def parse_bcl_prefix(hex_str: str) -> dict | None:
    h = hex_str.replace("...", "").upper()
    if len(h) % 2:
        h = h[:-1]
    if len(h) < 16:
        return None
    try:
        raw = bytes.fromhex(h[:64] if len(h) >= 64 else h)
    except ValueError:
        return None
    if len(raw) < 8:
        return None
    typ = int.from_bytes(raw[0:2], "big")
    src = int.from_bytes(raw[2:4], "big")
    dest = int.from_bytes(raw[4:6], "big")
    plen = int.from_bytes(raw[6:8], "big")
    info: dict = {
        "bcl_type": typ,
        "bcl_type_name": BCL_TYPES.get(typ, f"0x{typ:04x}"),
        "src": src,
        "dest": dest,
        "plen": plen,
    }
    # DATA frame: look for DEADBEEF after optional header packing
    dead = h.find("DEADBEEF")
    if dead >= 0 and dead + 16 <= len(h):
        try:
            etch_len = int(h[dead + 8 : dead + 16], 16)
            info["etch_len"] = etch_len
            info["deadbeef_off"] = dead // 2
        except ValueError:
            pass
        # DATA header often: 0002 src dest plen DEADBEEF...
        if typ == 0x0002 and len(raw) >= 8:
            info["data_src"] = src
            info["data_dest"] = dest
    # DATAACK wrapping DATA: 0006 ... then nested 0002
    nested = h.find("0002")
    if typ == 0x0006 and nested > 0:
        # try parse nested DATA at that offset
        try:
            nb = bytes.fromhex(h[nested : nested + 16])
            if len(nb) >= 8:
                info["nested_src"] = int.from_bytes(nb[2:4], "big")
                info["nested_dest"] = int.from_bytes(nb[4:6], "big")
                info["nested_plen"] = int.from_bytes(nb[6:8], "big")
        except ValueError:
            pass
    return info


@dataclass
class Event:
    t: str
    kind: str
    detail: dict = field(default_factory=dict)


def analyze_file(path: Path) -> dict:
    events: list[Event] = []
    write_lens: Counter = Counter()
    write_timeline: list[tuple[str, int]] = []
    uih_lens: Counter = Counter()
    dump_events: list[dict] = []
    etch_hits: Counter = Counter()
    etch_timeline: list[dict] = []
    adapter: list[tuple[str, str]] = []
    a2dp_marks: list[tuple[str, str]] = []
    screen_marks: list[tuple[str, str]] = []
    bqr: list[str] = []
    peers: Counter = Counter()
    scn_activity: Counter = Counter()
    uid_activity: Counter = Counter()
    unknown_hashes: set[str] = set()
    first_ts = last_ts = None
    e1_lines = 0
    total_lines = 0
    # fingerprint bursts of 666/667
    burst_windows: list[dict] = []

    with path.open("r", errors="replace") as f:
        for line in f:
            total_lines += 1
            mts = TS_RE.search(line)
            if not mts:
                continue
            ts = mts.group(1)
            if first_ts is None:
                first_ts = ts
            last_ts = ts

            is_e1 = HU_PEER in line
            if is_e1:
                e1_lines += 1

            if m := ADAPTER_RE.search(line):
                adapter.append((ts, m.group(1)))
                events.append(Event(ts, "adapter", {"state": m.group(1)}))

            if is_e1 or "AdapterState" in line:
                if A2DP_RE.search(line) and is_e1:
                    snippet = line.strip()[-160:]
                    a2dp_marks.append((ts, snippet))
                if SCREEN_RE.search(line):
                    screen_marks.append((ts, line.strip()[-200:]))

            if BQR_RE.search(line) and is_e1:
                bqr.append(f"{ts} {line.strip()[-220:]}")

            if m := WRITE_RE.search(line):
                # WriteDataCO is often without MAC on same line — accept if recent e1 context
                # Heuristic: count all WriteDataCO in these logs (HU is dominant SPP peer during session)
                n = int(m.group(1))
                write_lens[n] += 1
                write_timeline.append((ts, n))
                events.append(Event(ts, "tx_len", {"n": n}))

            if m := UIH_RE.search(line):
                if is_e1 or "e1:b5" in line or True:
                    # UIH lines often lack MAC; still count
                    uih_lens[int(m.group(1))] += 1

            if m := DUMP_RE.search(line):
                scn, peer, length, hexdata = m.group(1), m.group(2), int(m.group(3)), m.group(4)
                peers[peer] += 1
                scn_activity[int(scn)] += 1
                if HU_PEER not in peer:
                    continue
                bcl = parse_bcl_prefix(hexdata) or {}
                hashes = scan_etch_hashes(hexdata)
                for hv, name in hashes:
                    etch_hits[name] += 1
                    if name.startswith("UNKNOWN"):
                        unknown_hashes.add(name)
                    etch_timeline.append(
                        {
                            "t": ts,
                            "hash": f"0x{hv:08x}",
                            "name": name,
                            "len": length,
                            "scn": int(scn),
                            **{k: bcl[k] for k in ("src", "dest", "plen", "nested_src", "nested_plen", "etch_len") if k in bcl},
                        }
                    )
                # ASCII strings in dump (CDS property prefixes)
                ascii_hits = re.findall(rb"[\x20-\x7e]{4,}", bytes.fromhex(hexdata.replace("...", "")[: len(hexdata.replace("...", "")) - (len(hexdata.replace("...", "")) % 2)] or "00"))
                dump_events.append(
                    {
                        "t": ts,
                        "scn": int(scn),
                        "len": length,
                        "hex_prefix": hexdata[:96],
                        "bcl": bcl,
                        "hashes": [{"h": f"0x{hv:08x}", "n": n} for hv, n in hashes],
                        "ascii": [a.decode("ascii", "ignore") for a in ascii_hits[:8]],
                    }
                )
                events.append(Event(ts, "rx_dump", {"len": length, "hashes": [n for _, n in hashes], "bcl": bcl}))

            if m := UID_RE.search(line):
                uid = m.group(1) or m.group(2)
                if is_e1 or "10479" in line:
                    uid_activity[uid] += 1

    # Burst detection on write_timeline: sequences of 666 ending with remainder
    i = 0
    while i < len(write_timeline):
        ts, n = write_timeline[i]
        if n == 666:
            j = i
            total = 0
            while j < len(write_timeline) and write_timeline[j][1] == 666:
                total += 666
                j += 1
            rem = 0
            rem_ts = None
            if j < len(write_timeline) and write_timeline[j][1] not in (666, 667) and write_timeline[j][1] < 666:
                rem = write_timeline[j][1]
                rem_ts = write_timeline[j][0]
                total += rem
                j += 1
            count_666 = j - i - (1 if rem else 0)
            if count_666 >= 2:
                burst_windows.append(
                    {
                        "t0": ts,
                        "t_rem": rem_ts,
                        "n_666": count_666,
                        "rem": rem,
                        "sum": total,
                        "payload_est": total - 8 if rem or count_666 else total,  # rough
                    }
                )
            i = j
        else:
            i += 1

    # Classify TX lengths into BCL fingerprint buckets
    tx_classes = Counter()
    for n, c in write_lens.items():
        if n == 4:
            tx_classes["INIT(4)"] += c
        elif n == 10:
            tx_classes["SELECTPROTO(10)"] += c
        elif n == 56:
            tx_classes["KNOCK(56)"] += c
        elif n == 8:
            tx_classes["OPEN(8)"] += c
        elif n == 12:
            tx_classes["WD/ACK(12)"] += c
        elif n == 52:
            tx_classes["rhmi_getCapabilities?/52"] += c
        elif n == 559:
            tx_classes["sas_login(559)"] += c
        elif n == 666:
            tx_classes["MTU_frag_666"] += c
        elif n == 667:
            tx_classes["MTU_frag_667"] += c
        elif n == 44:
            tx_classes["void_result?/44"] += c
        else:
            tx_classes[f"other_{n}"] += c

    # Session milestones from events
    milestones = []
    for e in events:
        if e.kind == "adapter":
            milestones.append({"t": e.t, "m": f"ADAPTER_{e.detail['state']}"})
        elif e.kind == "tx_len" and e.detail["n"] in (4, 10, 56, 8, 559, 52):
            milestones.append({"t": e.t, "m": f"TX_{e.detail['n']}"})
        elif e.kind == "rx_dump" and e.detail.get("hashes"):
            for hname in e.detail["hashes"]:
                if any(x in hname for x in ("sas_", "rhmi_", "am_", "cds_", "av_")):
                    milestones.append({"t": e.t, "m": f"RX_{hname}", "len": e.detail["len"]})

    # Collapse consecutive identical milestone noise for setData floods
    collapsed = []
    for m in milestones:
        if collapsed and collapsed[-1]["m"] == m["m"] and m["m"].startswith("RX__result_rhmi_setData"):
            collapsed[-1]["count"] = collapsed[-1].get("count", 1) + 1
            collapsed[-1]["t_last"] = m["t"]
        else:
            mm = dict(m)
            mm["count"] = 1
            collapsed.append(mm)

    # Δt between first INIT(4) pairs (~3s timer)
    init_times = [parse_ts(t) for t, n in write_timeline if n == 4]
    init_deltas_ms = []
    for a, b in zip(init_times, init_times[1:]):
        init_deltas_ms.append(round((b - a).total_seconds() * 1000))

    # RHMI evidence summary
    rhmi_names = [n for n in etch_hits if "rhmi_" in n]
    setdata_count = etch_hits.get("_result_rhmi_setData", 0)
    setprop_count = etch_hits.get("_result_rhmi_setProperty", 0)
    on_action = etch_hits.get("rhmi_onActionEvent", 0) + etch_hits.get("_result_rhmi_onActionEvent", 0)
    # HU→Phone actions arrive as rhmi_onActionEvent (request), not _result_

    # TX inference for setData: look for many small writes after initialize
    # Typical setData request sizes vary; void result is 44B RX

    duration_s = None
    if first_ts and last_ts:
        duration_s = round((parse_ts(last_ts) - parse_ts(first_ts)).total_seconds(), 3)

    return {
        "file": path.name,
        "lines": total_lines,
        "e1_lines": e1_lines,
        "t0": first_ts,
        "t1": last_ts,
        "duration_s": duration_s,
        "adapter": adapter,
        "peers": dict(peers),
        "scn_activity": dict(scn_activity),
        "uid_activity": dict(uid_activity.most_common(10)),
        "tx_lens": dict(write_lens.most_common(40)),
        "tx_classes": dict(tx_classes),
        "tx_total_writes": sum(write_lens.values()),
        "tx_total_bytes": sum(n * c for n, c in write_lens.items()),
        "uih_lens_top": dict(uih_lens.most_common(20)),
        "etch_hits": dict(etch_hits.most_common()),
        "unknown_hashes": sorted(unknown_hashes),
        "rhmi_methods_seen": sorted(rhmi_names),
        "rhmi_setData_results": setdata_count,
        "rhmi_setProperty_results": setprop_count,
        "rhmi_onAction_hits": on_action,
        "dump_count_e1": len(dump_events),
        "bursts_666": burst_windows[:40],
        "burst_count": len(burst_windows),
        "init_deltas_ms": init_deltas_ms[:20],
        "milestones": collapsed[:200],
        "a2dp_marks": a2dp_marks[:30],
        "screen_marks": screen_marks[:40],
        "bqr": bqr[:20],
        "etch_timeline": etch_timeline,
        "dump_events": dump_events,
        "write_timeline": write_timeline,
    }


def print_report(r: dict) -> None:
    print("=" * 72)
    print(f"{r['file']}  {r['t0']} → {r['t1']}  ({r['duration_s']}s)  lines={r['lines']} e1={r['e1_lines']}")
    print("-" * 72)
    print("Adapter:", r["adapter"])
    print("Peers:", r["peers"])
    print("SCN:", r["scn_activity"])
    print("UID:", r["uid_activity"])
    print(f"TX writes={r['tx_total_writes']} bytes={r['tx_total_bytes']}")
    print("TX classes:", r["tx_classes"])
    print("TX lens top:", r["tx_lens"])
    print(f"RX dumps (e1): {r['dump_count_e1']}")
    print("Etch hits:", r["etch_hits"])
    print("Unknown hashes:", r["unknown_hashes"])
    print(
        f"RHMI: setData_results={r['rhmi_setData_results']} setProperty={r['rhmi_setProperty_results']} "
        f"onAction={r['rhmi_onAction_hits']} methods={r['rhmi_methods_seen']}"
    )
    print(f"666-bursts: {r['burst_count']} (showing first 15)")
    for b in r["bursts_666"][:15]:
        print(f"  {b}")
    print("INIT Δms:", r["init_deltas_ms"])
    print("Milestones:")
    for m in r["milestones"][:80]:
        extra = f" x{m['count']}" if m.get("count", 1) > 1 else ""
        print(f"  {m['t']}  {m['m']}{extra}" + (f"  len={m['len']}" if "len" in m else ""))
    if r["screen_marks"]:
        print("Screen/cast marks:")
        for t, s in r["screen_marks"][:15]:
            print(f"  {t}  {s[:160]}")
    if r["a2dp_marks"]:
        print("A2DP marks (sample):")
        for t, s in r["a2dp_marks"][:10]:
            print(f"  {t}  {s[:140]}")


def main() -> int:
    root = Path(__file__).resolve().parents[1] / "docs"
    files = sorted(root.glob("bluetooth_20261117_*.log"))
    if not files:
        print("no logs", file=sys.stderr)
        return 1

    # sanity: known hashes
    assert HASH_REGISTRY[etch_hash("de.bmw.idrive.BMWRemoting._result_rhmi_setData")].endswith("rhmi_setData")
    assert HASH_REGISTRY[0x9C6372B8] == "_result_sas_certificate"

    reports = []
    for f in files:
        r = analyze_file(f)
        print_report(r)
        reports.append(r)

    out_json = root / "analysis" / "FIELD_BTLOG_FORENSIC_20261117.json"
    # slim json: drop full write_timeline (huge), keep summary + etch_timeline + dumps
    slim = []
    for r in reports:
        s = {k: v for k, v in r.items() if k != "write_timeline"}
        slim.append(s)
    out_json.write_text(json.dumps(slim, indent=2))
    print(f"\nWrote {out_json}")

    # Cross-file RHMI verdict
    print("\n" + "=" * 72)
    print("CROSS-FILE VERDICT")
    total_setdata = sum(r["rhmi_setData_results"] for r in reports)
    total_setprop = sum(r["rhmi_setProperty_results"] for r in reports)
    all_etch = Counter()
    for r in reports:
        all_etch.update(r["etch_hits"])
    print(f"Σ _result_rhmi_setData = {total_setdata}")
    print(f"Σ _result_rhmi_setProperty = {total_setprop}")
    print("All etch:", dict(all_etch.most_common()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
