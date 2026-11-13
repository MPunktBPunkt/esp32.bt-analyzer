#!/usr/bin/env python3
"""Identify the HFP/audio stack on the BlueZ host and switch HFP/HSP off for BCL runs.

Background: docs/analysis/HFP_SLC_A6_20261113.md (BMW HU drops the SLC at AT+CHLD=?).

  python3 tools/lab_hfp_stack.py diag                 # processes, versions, roles config, adapter UUIDs
  python3 tools/lab_hfp_stack.py hfp-off              # dry run: show the drop-in that would be written
  python3 tools/lab_hfp_stack.py hfp-off --apply      # write drop-in, restart wireplumber
  python3 tools/lab_hfp_stack.py hfp-on --apply       # remove drop-in, restart wireplumber

hfp-off keeps A2DP (both directions) and removes all HFP/HSP roles for the whole PipeWire
instance, i.e. for every adapter on the host. Override host: BT_HOST_SSH=user@host
"""

from __future__ import annotations

import argparse
import json
import re
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from lab_bt_host_ssh import DEFAULT_SSH, ssh_run  # noqa: E402

DROPIN_05 = "/etc/wireplumber/wireplumber.conf.d/51-bt-analyzer-no-hfp.conf"
DROPIN_04 = "/etc/wireplumber/bluetooth.lua.d/51-bt-analyzer-no-hfp.lua"
CONTENT_05 = """# bt-analyzer: A2DP only, no HFP/HSP (docs/analysis/HFP_SLC_A6_20261113.md)
monitor.bluez.properties = {
  bluez5.roles = [ a2dp_sink a2dp_source ]
}
"""
CONTENT_04 = """-- bt-analyzer: A2DP only, no HFP/HSP (docs/analysis/HFP_SLC_A6_20261113.md)
bluez_monitor.properties["bluez5.roles"] = "[ a2dp_sink a2dp_source ]"
"""

DIAG_SCRIPT = r"""
echo '## ps'; ps -eo user=,comm=,args= | grep -E 'pipewire|wireplumber|ofonod|bluealsa|pulseaudio|bluetoothd' | grep -v grep
echo '## versions'
for b in pipewire wireplumber bluealsa ofonod pulseaudio bluetoothd; do
  command -v $b >/dev/null && echo "$b: $($b --version 2>&1 | head -n 3 | tr '\n' ' ')"
done
echo '## roles'
grep -rhs -E 'bluez5\.(roles|hfphsp-backend|enable-msbc|enable-sbc-xq)' \
  /etc/wireplumber /usr/share/wireplumber /etc/pipewire \
  /root/.config/wireplumber /home/*/.config/wireplumber 2>/dev/null \
  | grep -v '\.bak' | sort -u
echo '## dropins'; ls -1 /etc/wireplumber/wireplumber.conf.d /etc/wireplumber/bluetooth.lua.d 2>/dev/null
echo '## uuids'; bluetoothctl list; bluetoothctl show 2>/dev/null | grep -E 'Controller|UUID: (Handsfree|Headset|Audio)'
"""


def parse_diag(text: str) -> dict[str, Any]:
    """Section the diag output and guess which component answers HFP AT commands."""
    sections: dict[str, list[str]] = {}
    cur = None
    for line in text.splitlines():
        if line.startswith("## "):
            cur = line[3:].strip()
            sections[cur] = []
        elif cur and line.strip():
            sections[cur].append(line.rstrip())
    procs = " ".join(sections.get("ps", []))
    versions = {m.group(1): m.group(2).strip() for m in
                (re.match(r"(\w+): (.*)", v) for v in sections.get("versions", [])) if m}
    running = {name: bool(re.search(rf"\b{name}\b", procs))
               for name in ("pipewire", "wireplumber", "ofonod", "bluealsa", "pulseaudio", "bluetoothd")}
    roles = sections.get("roles", [])
    if running["ofonod"]:
        guess = "ofono"
    elif running["bluealsa"]:
        guess = "bluez-alsa"
    elif running["pipewire"] and running["wireplumber"]:
        guess = "pipewire-native" if not any("hfphsp-backend" in r and "ofono" in r for r in roles) else "pipewire+ofono"
    elif running["pulseaudio"]:
        guess = "pulseaudio"
    else:
        guess = "none"
    wp = versions.get("wireplumber", "")
    m = re.search(r"(\d+)\.(\d+)", wp.split("Linked")[-1] if "Linked" in wp else wp)
    wp_major_minor = (int(m.group(1)), int(m.group(2))) if m else None
    return {
        "running": running, "versions": versions, "roles_config": roles,
        "dropins": sections.get("dropins", []), "adapter_uuids": sections.get("uuids", []),
        "hfp_stack_guess": guess, "wireplumber_version": wp_major_minor,
        "hfp_off_active": any("51-bt-analyzer-no-hfp" in d for d in sections.get("dropins", [])),
    }


def dropin_for(wp_version: tuple[int, int] | None) -> tuple[str, str]:
    if wp_version and wp_version < (0, 5):
        return DROPIN_04, CONTENT_04
    return DROPIN_05, CONTENT_05


def diag() -> dict[str, Any]:
    try:
        p = ssh_run(["bash", "-lc", shlex.quote(DIAG_SCRIPT)], timeout=30)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"ok": False, "ssh": DEFAULT_SSH, "error": str(exc)}
    return {"ok": True, "ssh": DEFAULT_SSH, **parse_diag(p.stdout or "")}


def restart_wireplumber() -> str:
    """WirePlumber may be a systemd --user unit or a bare root process (lab .108)."""
    script = r"""
set +e
out=""
for u in $(ps -o user= -C wireplumber 2>/dev/null | sort -u); do
  if systemctl --machine=$u@.host --user restart wireplumber 2>/dev/null; then
    out="${out}restarted:$u "
  else
    # bare process (common when started outside systemd user session)
    pkill -u "$u" -x wireplumber
    sleep 1
    if [ "$u" = root ]; then
      export XDG_RUNTIME_DIR=/run/user/0
      mkdir -p /run/user/0
      nohup wireplumber >/tmp/wireplumber-root.log 2>&1 &
      out="${out}relaunched:root "
    else
      out="${out}killed:$u(no-systemd) "
    fi
  fi
done
# If 50-bt-lab.conf still lists HFP roles, WirePlumber may merge them back in.
# Ensure our drop-in is present; operator may also need to clear HFP from 50-bt-lab.
echo "$out"
"""
    p = ssh_run(["bash", "-lc", shlex.quote(script)], timeout=30)
    return ((p.stdout or "") + (p.stderr or "")).strip()


def hfp_off(apply: bool) -> dict[str, Any]:
    d = diag()
    if not d.get("ok"):
        return d
    path, content = dropin_for(d["wireplumber_version"])
    out = {"ok": True, "stack": d["hfp_stack_guess"], "wireplumber": d["wireplumber_version"],
           "path": path, "content": content, "applied": False}
    if d["hfp_stack_guess"] not in ("pipewire-native", "pipewire+ofono"):
        return {**out, "ok": False, "error": f"stack is {d['hfp_stack_guess']}, drop-in only works for PipeWire"}
    if not apply:
        return out
    p = ssh_run(["bash", "-lc", shlex.quote(f"mkdir -p {Path(path).parent.as_posix()} && cat > {path}")],
                timeout=15, input_text=content)
    if p.returncode != 0:
        return {**out, "ok": False, "error": (p.stderr or "").strip()}
    return {**out, "applied": True, "restart": restart_wireplumber()}


def hfp_on(apply: bool) -> dict[str, Any]:
    out = {"ok": True, "remove": [DROPIN_05, DROPIN_04], "applied": False}
    if not apply:
        return out
    ssh_run(["rm", "-f", DROPIN_05, DROPIN_04], timeout=15)
    return {**out, "applied": True, "restart": restart_wireplumber()}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("diag")
    for name in ("hfp-off", "hfp-on"):
        sub.add_parser(name).add_argument("--apply", action="store_true", help="change the host (default: dry run)")
    args = ap.parse_args()
    if args.cmd == "diag":
        out = diag()
    elif args.cmd == "hfp-off":
        out = hfp_off(args.apply)
    else:
        out = hfp_on(args.apply)
    print(json.dumps(out, indent=2, ensure_ascii=False))
    return 0 if out.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
