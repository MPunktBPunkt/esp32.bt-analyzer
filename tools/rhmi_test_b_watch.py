#!/usr/bin/env python3
"""Passive Test B watcher: Connected Spotify open → Music RHMI lifecycle.

Observe-only. No injects. Prints when music DESCRIPTION / initialize / setData appear.

  ssh root@.108 'python3 /path/to/rhmi_test_b_watch.py'
  # or: HU_JSONL=/tmp/bcl_dummy/hu.jsonl python3 tools/rhmi_test_b_watch.py
"""
from __future__ import annotations

import json
import os
import re
import time
from collections import Counter
from pathlib import Path

HU = Path(os.environ.get("HU_JSONL", "/tmp/bcl_dummy/hu.jsonl"))
RES = Path(os.environ.get("RHMI_RESOURCES", "/tmp/bcl_dummy/resources"))
POLL_S = float(os.environ.get("POLL_S", "1.0"))

MUSIC_MARKERS = (
    "androidautoidrive.music",
    'applicationType="Multimedia"',
    "Spotify",
    'text="music"',
    'text="Music"',
)


def load_rows():
    if not HU.exists():
        return []
    out = []
    for line in HU.read_text().splitlines():
        if not line.startswith("{"):
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def last_rfcomm_slice(rows):
    last = 0
    for i, o in enumerate(rows):
        if o.get("event") == "rfcomm_connected":
            last = i
    return rows[last:]


def scan_resources():
    hits = []
    if not RES.exists():
        return hits
    for fp in sorted(RES.glob("*.bin")):
        try:
            txt = fp.read_bytes().decode("utf-8", "ignore")
        except OSError:
            continue
        if any(m.lower() in txt.lower() for m in MUSIC_MARKERS):
            hits.append((fp.name, fp.stat().st_size))
        elif "pluginApp" in txt:
            apps = re.findall(r'text="([^"]+)"', txt)
            hits.append((fp.name, fp.stat().st_size, apps[:4]))
    return hits


def main() -> int:
    print("Test B passive watch — NO injects")
    print("HU", HU, "RES", RES)
    print("Open Spotify inside Connected/iDrive, then wait.")
    n0 = len(HU.read_text().splitlines()) if HU.exists() else 0
    last_sig = None
    while True:
        rows = load_rows()
        slice_ = last_rfcomm_slice(rows)
        methods = Counter(o.get("method") for o in slice_ if o.get("event") == "f20_rpc_rx")
        sd = [o for o in slice_ if o.get("event") == "f20_rpc_rx" and o.get("method") == "rhmi_setData"]
        inits = methods.get("rhmi_initialize", 0)
        handlers = methods.get("rhmi_addActionEventHandler", 0)
        set_res = methods.get("rhmi_setResource", 0)
        am = methods.get("am_registerApp", 0)
        closed = sum(1 for o in slice_ if o.get("event") == "rfcomm_closed")
        connected = sum(1 for o in slice_ if o.get("event") == "rfcomm_connected")
        res = scan_resources()
        music_res = [r for r in res if isinstance(r, tuple) and len(r) == 2]
        sig = (
            am,
            set_res,
            inits,
            handlers,
            len(sd),
            len(music_res),
            closed,
            methods.get("rhmi_create", 0),
        )
        if sig != last_sig:
            print(
                "amReg=%s setRes=%s init=%s handlers=%s setData=%s music_desc_files=%s "
                "create=%s rf_closed_since=%s top=%s"
                % (
                    am,
                    set_res,
                    inits,
                    handlers,
                    len(sd),
                    len(music_res),
                    methods.get("rhmi_create", 0),
                    closed,
                    methods.most_common(8),
                )
            )
            for r in res[-6:]:
                print("  res", r)
            for o in sd[-8:]:
                print(
                    "  setData src=%s modelId=%s value=%r rows=%s"
                    % (o.get("src"), o.get("modelId"), o.get("value"), o.get("value_rows"))
                )
            last_sig = sig
        if music_res and inits and sd:
            print("TEST_B_PASS: Music DESCRIPTION + initialize + setData")
            return 0
        # also pass on setData alone if music models appear
        for o in sd:
            mid = o.get("modelId")
            if mid in (445, 446, 447, 451, 452, 462) or (
                isinstance(o.get("value"), str) and o.get("value")
            ):
                print("TEST_B_SETDATA: model", mid, repr(o.get("value"))[:80])
                return 0
        time.sleep(POLL_S)


if __name__ == "__main__":
    raise SystemExit(main())
