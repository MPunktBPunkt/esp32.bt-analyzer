#!/usr/bin/env python3
"""P0 lab: Just-Works bond .87↔.131, then RFCOMM/BCL hold with dual ESP polling.

Runs on the operator machine (SSH to BlueZ host). Default mapping matches the
home-session HU/phone roles:

  .131 / C8:C9:A3:CB:7B:0A  = HU   (BMW 38304)
  .87  / C8:C9:A3:CB:37:96  = Phone (BT-Analyzer-Phone)

Usage:
  python3 tools/lab_p0_dual_esp_hold.py --hold 300 \\
    --out docs/evidence/LAB_P0_87_131_HOLD_...json
"""

from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SSH = os.environ.get("BT_HOST_SSH", "root@192.168.178.108")
HU_IP = "192.168.178.131"
PHONE_IP = "192.168.178.87"
HU_BD = "C8:C9:A3:CB:7B:0A"
PHONE_BD = "C8:C9:A3:CB:37:96"
USB_PHONE_BD = "C0:B8:83:34:F4:62"  # .108 USB hci0 — single-ESP A/B phone side


def utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def ssh(
    remote: str, timeout: float = 120.0, *, host: str = DEFAULT_SSH
) -> subprocess.CompletedProcess[str]:
    cmd = [
        "ssh",
        "-o",
        "BatchMode=yes",
        "-o",
        "ConnectTimeout=8",
        host,
        remote,
    ]
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)


def scp_to(local: Path, remote_path: str, *, host: str = DEFAULT_SSH) -> None:
    subprocess.run(
        [
            "scp",
            "-o",
            "BatchMode=yes",
            str(local),
            f"{host}:{remote_path}",
        ],
        check=True,
        capture_output=True,
        text=True,
        timeout=60,
    )


REMOTE_SCRIPT = r'''
import errno, json, os, select, socket, subprocess, threading, time, urllib.request

HU_BD = os.environ["HU_BD"]
PHONE_BD = os.environ["PHONE_BD"]
HU_IP = os.environ["HU_IP"]
PHONE_IP = os.environ["PHONE_IP"]
CHANNEL = int(os.environ.get("RFCOMM_CHANNEL", "6"))
HOLD = float(os.environ.get("HOLD_S", "300"))
OUT = os.environ["OUT_DIR"]

os.makedirs(OUT, exist_ok=True)

def esp_snap(ip):
    o = json.load(urllib.request.urlopen(f"http://{ip}/api/status", timeout=3))
    ha = o.get("hciAgent") or {}
    return {
        "ts": time.time(),
        "ip": ip,
        "uptime": o.get("uptime"),
        "heap": o.get("heap"),
        "resetReason": o.get("resetReason"),
        "bootGen": o.get("bootGen"),
        "drops": ha.get("drops"),
        "sessions": ha.get("sessions"),
        "toHostBytes": ha.get("toHostBytes"),
        "toCtrlBytes": ha.get("toCtrlBytes"),
        "client": ha.get("client"),
        "ready": ha.get("ready"),
    }

def fetch_json(url, timeout=4.0):
    return json.load(urllib.request.urlopen(url, timeout=timeout))

def esp_diag(ip):
    out = {"ip": ip}
    try:
        out["boot"] = fetch_json(f"http://{ip}/api/diag/boot")
    except Exception as e:
        out["boot_error"] = str(e)
    try:
        out["status"] = esp_snap(ip)
    except Exception as e:
        out["status_error"] = str(e)
    return out

pre_diag = {"131": esp_diag(HU_IP)}
if PHONE_IP:
    pre_diag["87"] = esp_diag(PHONE_IP)
open(f"{OUT}/esp_diag_pre.json", "w").write(json.dumps(pre_diag, indent=2) + "\n")
print("PRE_DIAG", json.dumps({
    k: {
        "bootGen": (v.get("status") or {}).get("bootGen"),
        "resetReason": (v.get("status") or {}).get("resetReason"),
        "uptime": (v.get("status") or {}).get("uptime"),
    } for k, v in pre_diag.items()
}), flush=True)
print("MODE", json.dumps({"hu_bd": HU_BD, "phone_bd": PHONE_BD, "hu_ip": HU_IP, "phone_ip": PHONE_IP or None}), flush=True)

# --- pair agent Just Works ---
subprocess.run(["systemctl", "stop", "bt-pair-agent.service"], capture_output=True)
# deploy capability if present in /tmp
agent = "/tmp/bt_pair_agent_jw.py"
if not os.path.exists(agent):
    agent = "/opt/bt-analyzer/bt_pair_agent.py"
jw = subprocess.Popen([
    "python3", agent,
    "--capability", "NoInputNoOutput",
    "--mode", "always",
    f"--adapter={HU_BD}=car_audio:BMW 38304",
    f"--adapter={PHONE_BD}=phone:BT-Analyzer-Phone",
], stdout=open(f"{OUT}/pair_agent_jw.log","w"), stderr=subprocess.STDOUT)
time.sleep(3)

import dbus
from dbus.mainloop.glib import DBusGMainLoop
DBusGMainLoop(set_as_default=True)
bus = dbus.SystemBus()

def props(path):
    return dbus.Interface(bus.get_object("org.bluez", path), "org.freedesktop.DBus.Properties")

om = dbus.Interface(bus.get_object("org.bluez", "/"), "org.freedesktop.DBus.ObjectManager")

def find_adapter(bd):
    bd_u = bd.upper()
    for pth, ifaces in om.GetManagedObjects().items():
        ad = ifaces.get("org.bluez.Adapter1")
        if not ad:
            continue
        if str(ad.get("Address", "")).upper() == bd_u:
            return pth
    return None

hu_adapter = find_adapter(HU_BD)
phone_adapter = find_adapter(PHONE_BD)
adapters = {"hu": hu_adapter, "phone": phone_adapter}
open(f"{OUT}/adapters.json", "w").write(json.dumps(adapters, indent=2) + "\n")
print("ADAPTERS", json.dumps(adapters), flush=True)
if not hu_adapter or not phone_adapter:
    jw.terminate()
    subprocess.run(["systemctl", "start", "bt-pair-agent.service"], capture_output=True)
    raise SystemExit("missing HU/phone adapter by BD: " + json.dumps(adapters))

# io-cap Just Works on both virtual controllers (by resolved index)
for ap in (hu_adapter, phone_adapter):
    idx = ap.rsplit("/", 1)[-1].replace("hci", "")
    subprocess.run(["btmgmt", "--index", str(idx), "io-cap", "3"], capture_output=True)
    subprocess.run(["btmgmt", "--index", str(idx), "sc", "off"], capture_output=True)

for ap, alias in ((hu_adapter, "BMW 38304"), (phone_adapter, "BT-Analyzer-Phone")):
    p = props(ap)
    p.Set("org.bluez.Adapter1", "Powered", dbus.Boolean(True))
    p.Set("org.bluez.Adapter1", "Pairable", dbus.Boolean(True))
    p.Set("org.bluez.Adapter1", "Discoverable", dbus.Boolean(True))
    try:
        p.Set("org.bluez.Adapter1", "Alias", dbus.String(alias))
    except Exception:
        pass

ad_phone = dbus.Interface(bus.get_object("org.bluez", phone_adapter), "org.bluez.Adapter1")
ad_hu = dbus.Interface(bus.get_object("org.bluez", hu_adapter), "org.bluez.Adapter1")

# remove stale mutual devices on the phone↔HU adapters only
for pth, ifaces in list(om.GetManagedObjects().items()):
    if "org.bluez.Device1" not in ifaces:
        continue
    d = ifaces["org.bluez.Device1"]
    addr = str(d.get("Address", "")).upper()
    adap = str(d.get("Adapter", ""))
    if (addr == HU_BD.upper() and adap == phone_adapter) or (addr == PHONE_BD.upper() and adap == hu_adapter):
        try:
            dbus.Interface(bus.get_object("org.bluez", adap), "org.bluez.Adapter1").RemoveDevice(pth)
        except Exception:
            pass

time.sleep(1.0)
# Prefer already-known HU device; otherwise scan (BREDR).
path = None
for pth, ifaces in om.GetManagedObjects().items():
    if "org.bluez.Device1" not in ifaces:
        continue
    d = ifaces["org.bluez.Device1"]
    if str(d.get("Address", "")).upper() == HU_BD.upper() and str(d.get("Adapter")) == phone_adapter:
        path = pth
        break
if path is None:
    try:
        ad_phone.SetDiscoveryFilter({"Transport": "bredr"})
    except Exception:
        pass
    ad_phone.StartDiscovery()
    for _ in range(80):
        for pth, ifaces in om.GetManagedObjects().items():
            if "org.bluez.Device1" not in ifaces:
                continue
            d = ifaces["org.bluez.Device1"]
            if str(d.get("Address", "")).upper() == HU_BD.upper() and str(d.get("Adapter")) == phone_adapter:
                path = pth
                break
        if path:
            break
        time.sleep(0.4)
try:
    ad_phone.StopDiscovery()
except Exception:
    pass

bond = {"device_path": path, "paired": False, "error": None, "phone_adapter": phone_adapter, "hu_adapter": hu_adapter}
if not path:
    bond["error"] = f"HU not found on phone adapter {phone_adapter}"
else:
    dev = dbus.Interface(bus.get_object("org.bluez", path), "org.bluez.Device1")
    dp = props(path)
    dp.Set("org.bluez.Device1", "Trusted", dbus.Boolean(True))
    try:
        if not bool(dp.Get("org.bluez.Device1", "Paired")):
            # Pair blocks; agent JW auto-confirms
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(1) as ex:
                fut = ex.submit(dev.Pair)
                fut.result(timeout=60)
        bond["paired"] = bool(dp.Get("org.bluez.Device1", "Paired"))
        bond["trusted"] = bool(dp.Get("org.bluez.Device1", "Trusted"))
    except Exception as e:
        bond["error"] = repr(e)
        bond["paired"] = bool(dp.Get("org.bluez.Device1", "Paired"))

open(f"{OUT}/bond.json","w").write(json.dumps(bond, indent=2)+"\n")
print("BOND", json.dumps(bond), flush=True)

# Restart HU agent so RFCOMM server binds after bridge/panic recovery
ready = "/tmp/bcl_dummy/hu_ab_87131.ready"
subprocess.run(["pkill", "-f", "bcl_dummy_hu_agent.py hu .*LAB_AB_87_131"], capture_output=True)
try:
    os.remove(ready)
except FileNotFoundError:
    pass
subprocess.Popen([
    "python3", "/tmp/bcl_dummy/bcl_dummy_hu_agent.py", "hu",
    "--hu-profile", "f20_sim", "--channel", str(CHANNEL),
    "--name", "BMW 38304", "--hold", "7200",
    "--log", "/tmp/bcl_dummy/hu_ab_87131.jsonl",
    "--ready", ready, "--session-id", "LAB_AB_87_131",
], stdout=open("/tmp/bcl_dummy/hu_ab_87131.out","a"), stderr=subprocess.STDOUT)
for _ in range(40):
    if os.path.exists(ready):
        break
    time.sleep(0.3)

# Dual ESP poller during hold
esp_rows = []
stop = threading.Event()
prev = {}

def poll_esp():
    while not stop.is_set():
        row = {"ts": time.time()}
        targets = [(HU_IP, "131")]
        if PHONE_IP:
            targets.append((PHONE_IP, "87"))
        for ip, tag in targets:
            try:
                snap = esp_snap(ip)
                row[tag] = snap
                p = prev.get(tag)
                if p and (p.get("bootGen") != snap.get("bootGen") or p.get("drops") != snap.get("drops")):
                    row.setdefault("delta", {})[tag] = {"from": p, "to": snap}
                prev[tag] = snap
            except Exception as e:
                row[tag] = {"error": str(e)}
        esp_rows.append(row)
        time.sleep(2)

th = threading.Thread(target=poll_esp, daemon=True)
th.start()
time.sleep(1)

WANT_BCL = os.environ.get("BCL_PHONE", "1") == "1"
USE_BCL = WANT_BCL and bool(bond.get("paired"))
hold = {
    "channel": CHANNEL,
    "hold_s_requested": HOLD,
    "mode": "bcl_phone" if USE_BCL else ("raw_rfcomm" if not WANT_BCL else "bcl_bond_failed"),
}
t0 = time.time()
sent = 0
rx = 0
send_err = None
phone_proc = None
s = None

if WANT_BCL and not bond.get("paired"):
    stop.set()
    hold["rfcomm_connect_ok"] = False
    hold["connect_error"] = bond.get("error") or "not_paired"
    send_err = f"bond_required:{hold['connect_error']}"
    open(f"{OUT}/hold.json", "w").write(
        json.dumps(
            {
                "bond": bond,
                "adapters": adapters,
                "hold": {
                    **hold,
                    "hold_s": round(time.time() - t0, 2),
                    "sent": 0,
                    "rx": 0,
                    "send_err": send_err,
                    "ok": False,
                },
                "esp_sample_count": len(esp_rows),
                "esp_first": esp_rows[0] if esp_rows else None,
                "esp_last": esp_rows[-1] if esp_rows else None,
            },
            indent=2,
        )
        + "\n"
    )
    print("HOLD_FAIL", json.dumps({**hold, "send_err": send_err}), flush=True)
    jw.terminate()
    subprocess.run(["systemctl", "start", "bt-pair-agent.service"], capture_output=True)
    raise SystemExit(3)

RHMI_SOAK = os.environ.get("BCL_RHMI_SOAK", "").strip() in ("1", "true", "yes")
RHMI_PIDRIVE_SEQ = os.environ.get("BCL_RHMI_PIDRIVE_SEQ", "").strip() in ("1", "true", "yes")
RHMI_MUSIC_NP_SEQ = os.environ.get("BCL_RHMI_MUSIC_NP_SEQ", "").strip() in ("1", "true", "yes")
MENU_TEST_ACTION = int(os.environ.get("MENU_TEST_ACTION", "200"))
MUSIC_NP_ACTION_PRIMARY = int(os.environ.get("MUSIC_NP_ACTION_PRIMARY", "336"))
MUSIC_NP_ACTION_SECONDARY = int(os.environ.get("MUSIC_NP_ACTION_SECONDARY", "248"))
if RHMI_MUSIC_NP_SEQ:
    RHMI_PIDRIVE_SEQ = False
    RHMI_SOAK = False
elif RHMI_PIDRIVE_SEQ:
    RHMI_SOAK = False
hold["rhmi_soak"] = RHMI_SOAK
hold["rhmi_pidrive_seq"] = RHMI_PIDRIVE_SEQ
hold["rhmi_music_np_seq"] = RHMI_MUSIC_NP_SEQ
hold["menu_test_action"] = MENU_TEST_ACTION
hold["music_np_actions"] = [MUSIC_NP_ACTION_PRIMARY, MUSIC_NP_ACTION_SECONDARY]

def soak_action_injector(stop_evt):
    """HU→phone rhmi_onActionEvent during soak phases 5–10 min (hold wall clock)."""
    if not RHMI_SOAK or RHMI_PIDRIVE_SEQ or RHMI_MUSIC_NP_SEQ:
        return
    inject = "/tmp/bcl_dummy/inject_cds.jsonl"
    os.makedirs(os.path.dirname(inject), exist_ok=True)
    open(inject, "a").close()
    # Wait for actions window (~5 min after hold start; RUNTIME_ACTIVE ~+4s).
    while not stop_evt.is_set() and time.time() - t0 < 300:
        time.sleep(1.0)
    n = 0
    while not stop_evt.is_set() and time.time() - t0 < HOLD:
        elapsed = time.time() - t0
        # 5–7 min: dense actions; 7–10 min: mixed slower actions
        pace = 2.0 if elapsed < 420 else 4.0
        handles = (12, 13, 17, 19)
        action_ids = (541, 542, 543)
        h = handles[n % len(handles)]
        aid = action_ids[n % len(action_ids)]
        line = json.dumps({
            "_rhmi_action": {
                "src": 19,
                "handle": h,
                "actionId": aid,
                "args": {"0": n % 3},
            },
            "_pace_ms": 80,
        }) + "\n"
        with open(inject, "a") as f:
            f.write(line)
        n += 1
        time.sleep(pace)
    open(f"{OUT}/soak_actions.json", "w").write(json.dumps({"injected": n}, indent=2) + "\n")

def _rhmi_handle_from_phone_log() -> int:
    handle = 12
    phone_path = f"{OUT}/phone.jsonl"
    if os.path.exists(phone_path):
        for line in open(phone_path):
            try:
                o = json.loads(line)
            except Exception:
                continue
            if o.get("event") == "mybmw_handle" and o.get("method") == "rhmi_create":
                handle = int(o.get("handle") or 12)
    return handle

def pidrive_seq_injector(stop_evt):
    """One-shot MENU_TEST_ACTION after phone setData(PiDrive) (~25s hold clock)."""
    if not RHMI_PIDRIVE_SEQ:
        return
    inject = "/tmp/bcl_dummy/inject_cds.jsonl"
    os.makedirs(os.path.dirname(inject), exist_ok=True)
    open(inject, "a").close()
    # RUNTIME_ACTIVE ~4s + phone setData at +15s → inject ~25s after hold start.
    while not stop_evt.is_set() and time.time() - t0 < 25.0:
        time.sleep(0.5)
    if stop_evt.is_set():
        return
    handle = _rhmi_handle_from_phone_log()
    line = json.dumps({
        "_rhmi_action": {
            "src": 19,
            "handle": handle,
            "actionId": MENU_TEST_ACTION,
            "args": {"0": 0},
        },
        "_pace_ms": 80,
    }) + "\n"
    with open(inject, "a") as f:
        f.write(line)
    meta = {"injected": 1, "actionId": MENU_TEST_ACTION, "handle": handle, "t_rel_s": round(time.time() - t0, 1)}
    open(f"{OUT}/pidrive_seq_action.json", "w").write(json.dumps(meta, indent=2) + "\n")
    print("PIDRIVE_SEQ_INJECT", json.dumps(meta), flush=True)

def music_np_seq_injector(stop_evt):
    """Inject Field Music actions 336 then 248 after NP setData (~12s hold clock)."""
    if not RHMI_MUSIC_NP_SEQ:
        return
    inject = "/tmp/bcl_dummy/inject_cds.jsonl"
    os.makedirs(os.path.dirname(inject), exist_ok=True)
    open(inject, "a").close()
    # RUNTIME_ACTIVE ~4s + phone setData/events at +5s → inject ~12s / +2s.
    while not stop_evt.is_set() and time.time() - t0 < 12.0:
        time.sleep(0.5)
    if stop_evt.is_set():
        return
    handle = _rhmi_handle_from_phone_log()
    injected = []
    for aid in (MUSIC_NP_ACTION_PRIMARY, MUSIC_NP_ACTION_SECONDARY):
        if stop_evt.is_set():
            break
        line = json.dumps({
            "_rhmi_action": {
                "src": 19,
                "handle": handle,
                "actionId": aid,
                "args": {"0": 0},
            },
            "_pace_ms": 80,
        }) + "\n"
        with open(inject, "a") as f:
            f.write(line)
        injected.append({"actionId": aid, "handle": handle, "t_rel_s": round(time.time() - t0, 1)})
        time.sleep(2.0)
    meta = {"injected": len(injected), "actions": injected}
    open(f"{OUT}/music_np_seq_action.json", "w").write(json.dumps(meta, indent=2) + "\n")
    print("MUSIC_NP_SEQ_INJECT", json.dumps(meta), flush=True)

if USE_BCL:
    # Real BCL session owns RFCOMM; do not also raw-spam the same channel.
    phone_env = os.environ.copy()
    if RHMI_MUSIC_NP_SEQ:
        phone_env["BCL_RHMI_MUSIC_NP_SEQ"] = "1"
        # Prefer Field-matched Music DESCRIPTION when present on lab host.
        phone_env.setdefault(
            "BCL_RHMI_DESCRIPTION",
            "/tmp/bcl_dummy/ui_description_multimedia_v3.xml",
        )
    elif RHMI_PIDRIVE_SEQ:
        phone_env["BCL_RHMI_PIDRIVE_SEQ"] = "1"
    elif RHMI_SOAK:
        phone_env["BCL_RHMI_SOAK"] = "1"
    phone_cmd = [
        "python3", "/tmp/bcl_dummy/bcl_dummy_hu_agent.py", "phone",
        "--adapter-bd", PHONE_BD, "--hu-bd", HU_BD, "--channel", str(CHANNEL),
        "--seconds", str(int(HOLD)),
        "--full-client", "--mybmw-sim",
        "--log", f"{OUT}/phone.jsonl",
        "--session-id", "LAB_P0_87_131_HOLD",
    ]
    if RHMI_MUSIC_NP_SEQ:
        phone_cmd.append("--rhmi-music-np-seq")
    elif RHMI_PIDRIVE_SEQ:
        phone_cmd.append("--rhmi-pidrive-seq")
    elif RHMI_SOAK:
        phone_cmd.append("--rhmi-soak")
    phone_proc = subprocess.Popen(
        phone_cmd,
        stdout=open(f"{OUT}/phone.out","w"),
        stderr=subprocess.STDOUT,
        env=phone_env,
    )
    soak_th = threading.Thread(target=soak_action_injector, args=(stop,), daemon=True)
    soak_th.start()
    seq_th = threading.Thread(target=pidrive_seq_injector, args=(stop,), daemon=True)
    seq_th.start()
    music_th = threading.Thread(target=music_np_seq_injector, args=(stop,), daemon=True)
    music_th.start()
    hold["rfcomm_connect_ok"] = None  # determined from phone.jsonl later
    hold["connect_error"] = None
    while time.time() - t0 < HOLD:
        rc = phone_proc.poll()
        if rc is not None:
            if rc != 0 and send_err is None:
                send_err = f"phone_proc_exit_{rc}"
            break
        time.sleep(0.5)
    if phone_proc.poll() is None:
        try:
            phone_proc.wait(timeout=15)
        except Exception:
            phone_proc.kill()
    # summarize phone log
    phone_events = {}
    phone_connect_ok = False
    phone_path = f"{OUT}/phone.jsonl"
    if os.path.exists(phone_path):
        for line in open(phone_path):
            try:
                o = json.loads(line)
            except Exception:
                continue
            e = o.get("event") or "?"
            phone_events[e] = phone_events.get(e, 0) + 1
            if e == "rfcomm_connected":
                phone_connect_ok = True
            if e in ("rfcomm_connect_failed", "error", "session_error") and send_err is None:
                send_err = f"{e}:{o.get('error') or o.get('reason') or ''}"
    hold["rfcomm_connect_ok"] = phone_connect_ok
    hold["phone_events"] = phone_events
    hold["phone_returncode"] = phone_proc.returncode
    # pull abort classification from phone_done if present
    abort_reason = None
    wait_class = None
    if os.path.exists(phone_path):
        for line in open(phone_path):
            try:
                o = json.loads(line)
            except Exception:
                continue
            if o.get("event") == "hold_abort":
                abort_reason = o.get("reason")
            if o.get("event") == "phone_done":
                abort_reason = abort_reason or o.get("abort_reason")
                wait_class = o.get("wait_class")
                hold["rhmi_state"] = o.get("rhmi_state")
                hold["rx_total"] = o.get("rx_total")
                hold["soak_phase"] = o.get("soak_phase")
                hold["soak_counts"] = o.get("soak_counts")
                hold["soak_elapsed_s"] = o.get("soak_elapsed_s")
                hold["selected_action"] = o.get("selected_action")
                hold["seq_phase"] = o.get("seq_phase")
    hold["abort_reason"] = abort_reason
    hold["wait_class"] = wait_class
    if os.path.exists(f"{OUT}/soak_actions.json"):
        try:
            hold["soak_actions"] = json.loads(open(f"{OUT}/soak_actions.json").read())
        except Exception:
            pass
    if os.path.exists(f"{OUT}/pidrive_seq_action.json"):
        try:
            hold["pidrive_seq_action"] = json.loads(open(f"{OUT}/pidrive_seq_action.json").read())
        except Exception:
            pass
    if not phone_connect_ok and send_err is None:
        send_err = "bcl_phone_no_rfcomm_connected"
    elif abort_reason and send_err is None:
        send_err = f"hold_abort:{abort_reason}"
else:
    # Raw RFCOMM hold with EINPROGRESS-tolerant connect
    s = socket.socket(socket.AF_BLUETOOTH, socket.SOCK_STREAM, socket.BTPROTO_RFCOMM)
    s.bind((PHONE_BD, 0))
    s.setblocking(False)
    try:
        s.connect((HU_BD, CHANNEL))
    except BlockingIOError:
        pass
    ok = False
    cerr = None
    deadline = time.time() + 45
    while time.time() < deadline:
        _, w, x = select.select([], [s], [s], 0.5)
        if not w and not x:
            continue
        so = s.getsockopt(socket.SOL_SOCKET, socket.SO_ERROR)
        if so == 0:
            ok = True
            break
        if so in (errno.EINPROGRESS, errno.EALREADY, 114, 115):
            continue
        cerr = so
        break

    hold["rfcomm_connect_ok"] = ok
    hold["connect_error"] = cerr
    if not ok:
        stop.set()
        hold["esp_rows"] = len(esp_rows)
        open(f"{OUT}/hold.json","w").write(json.dumps({"bond": bond, "hold": hold, "esp": esp_rows[-5:]}, indent=2))
        print("HOLD_FAIL", json.dumps(hold), flush=True)
        jw.terminate()
        subprocess.run(["systemctl", "start", "bt-pair-agent.service"], capture_output=True)
        raise SystemExit(2)

    s.setblocking(True)
    s.settimeout(1.0)
    n = 0
    while time.time() - t0 < HOLD:
        n += 1
        try:
            payload = b"\x00\x00" + f"H{n:06d}".encode() + bytes([n & 0xff]) * 40
            s.send(payload)
            sent += len(payload)
        except OSError as e:
            send_err = repr(e)
            break
        try:
            chunk = s.recv(4096)
            if not chunk:
                send_err = "eof"
                break
            rx += len(chunk)
        except socket.timeout:
            pass
        except OSError as e:
            send_err = repr(e)
            break
        time.sleep(0.05)

    try:
        s.close()
    except Exception:
        pass

stop.set()
time.sleep(0.5)
if phone_proc is not None and phone_proc.poll() is None:
    try:
        phone_proc.wait(timeout=10)
    except Exception:
        phone_proc.kill()

# HU flaps in window
hu_flaps = []
hu_events = {}
hu_log = "/tmp/bcl_dummy/hu_ab_87131.jsonl"
if os.path.exists(hu_log):
    for line in open(hu_log):
        try:
            o = json.loads(line)
        except Exception:
            continue
        if (o.get("ts") or 0) < t0 - 2:
            continue
        e = o.get("event") or "?"
        hu_events[e] = hu_events.get(e, 0) + 1
        if e in ("rfcomm_connected", "rfcomm_closed", "handshake_sent", "session_init", "error"):
            hu_flaps.append({k: o.get(k) for k in ("ts", "event", "reason", "peer", "session_id") if k in o or k == "event"})

deltas = [r for r in esp_rows if r.get("delta")]
post_diag = {"131": esp_diag(HU_IP)}
if PHONE_IP:
    post_diag["87"] = esp_diag(PHONE_IP)
open(f"{OUT}/esp_diag_post.json", "w").write(json.dumps(post_diag, indent=2) + "\n")
result = {
    "mode": {
        "hu_bd": HU_BD,
        "phone_bd": PHONE_BD,
        "hu_ip": HU_IP,
        "phone_ip": PHONE_IP or None,
        "single_esp": not bool(PHONE_IP),
    },
    "bond": bond,
    "adapters": adapters,
    "hold": {
        **hold,
        "hold_s": round(time.time() - t0, 2),
        "sent": sent,
        "rx": rx,
        "send_err": send_err,
        "ok": send_err is None,
    },
    "esp_sample_count": len(esp_rows),
    "esp_deltas": deltas,
    "esp_first": esp_rows[0] if esp_rows else None,
    "esp_last": esp_rows[-1] if esp_rows else None,
    "esp_diag_pre": {
        k: {
            "bootGen": (v.get("status") or {}).get("bootGen"),
            "resetReason": (v.get("status") or {}).get("resetReason"),
            "uptime": (v.get("status") or {}).get("uptime"),
            "drops": (v.get("status") or {}).get("drops"),
        } for k, v in pre_diag.items()
    },
    "esp_diag_post": {
        k: {
            "bootGen": (v.get("status") or {}).get("bootGen"),
            "resetReason": (v.get("status") or {}).get("resetReason"),
            "uptime": (v.get("status") or {}).get("uptime"),
            "drops": (v.get("status") or {}).get("drops"),
            "status_error": v.get("status_error"),
            "boot_error": v.get("boot_error"),
        } for k, v in post_diag.items()
    },
    "hu_events": hu_events,
    "hu_key_events": hu_flaps,
    "phone_proc": phone_proc.returncode if phone_proc else None,
}
open(f"{OUT}/hold.json","w").write(json.dumps(result, indent=2) + "\n")
open(f"{OUT}/esp_poll.jsonl","w").write("\n".join(json.dumps(r) for r in esp_rows) + "\n")
print("RESULT", json.dumps({
    "bond_paired": bond.get("paired"),
    "hold_ok": result["hold"]["ok"],
    "sent": sent,
    "rx": rx,
    "send_err": send_err,
    "esp_deltas": len(deltas),
    "hu_flaps": len(hu_flaps),
    "bootGen_pre": {k: (v.get("status") or {}).get("bootGen") for k, v in pre_diag.items()},
    "bootGen_post": {k: (v.get("status") or {}).get("bootGen") for k, v in post_diag.items()},
}), flush=True)

# restore DisplayYesNo pair agent for phone↔BMW
jw.terminate()
try:
    jw.wait(timeout=3)
except Exception:
    jw.kill()
subprocess.run(["systemctl", "start", "bt-pair-agent.service"], capture_output=True)
print("RESTORED_PAIR_AGENT", flush=True)
'''


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--hold", type=float, default=300.0, help="RFCOMM hold seconds (default 300)")
    ap.add_argument("--channel", type=int, default=6)
    ap.add_argument("--no-bcl-phone", action="store_true", help="skip parallel mybmw-sim phone client")
    ap.add_argument(
        "--single-esp",
        action="store_true",
        help=f"phone on USB hci0 ({USB_PHONE_BD}), HU remains ESP .131 — A/B vs dual-ESP",
    )
    ap.add_argument("--phone-bd", default="", help="override phone BD (implies no phone ESP poll if not .87)")
    ap.add_argument("--out", type=Path, help="local evidence JSON path")
    ap.add_argument("--ssh", default=DEFAULT_SSH)
    ap.add_argument(
        "--rhmi-soak",
        action="store_true",
        help="enable phased RHMI soak (setData/Actions) via BCL_RHMI_SOAK=1",
    )
    ap.add_argument(
        "--rhmi-pidrive-seq",
        action="store_true",
        help="minimal PiDrive UI seq (setData→MENU_TEST_ACTION→sink) via BCL_RHMI_PIDRIVE_SEQ=1",
    )
    ap.add_argument(
        "--rhmi-music-np-seq",
        action="store_true",
        help=(
            "Music NP spine seq (444..447 / 660·661 / 336·248) via BCL_RHMI_MUSIC_NP_SEQ=1"
        ),
    )
    args = ap.parse_args()
    host = args.ssh

    phone_bd = USB_PHONE_BD if args.single_esp else (args.phone_bd or PHONE_BD)
    phone_ip = "" if (args.single_esp or (args.phone_bd and args.phone_bd.upper() != PHONE_BD.upper())) else PHONE_IP
    if args.phone_bd and not args.single_esp:
        phone_bd = args.phone_bd
        if phone_bd.upper() == PHONE_BD.upper():
            phone_ip = PHONE_IP
        else:
            phone_ip = ""

    stamp = utc_stamp()
    remote_out = f"/tmp/bcl_dummy/p0_hold_{stamp}"
    tag = "SINGLE" if (args.single_esp or not phone_ip) else "87_131"
    local_out = args.out or (ROOT / "docs" / "evidence" / f"LAB_P0_{tag}_HOLD_{stamp}.json")

    # upload pair agent + remote runner
    scp_to(ROOT / "tools" / "bt_pair_agent.py", "/tmp/bt_pair_agent_jw.py", host=host)
    # write remote script via ssh heredoc is messy; scp a temp file
    tmp = ROOT / "tools" / f".lab_p0_remote_{stamp}.py"
    tmp.write_text(REMOTE_SCRIPT)
    try:
        scp_to(tmp, "/tmp/lab_p0_dual_esp_hold_remote.py", host=host)
    finally:
        tmp.unlink(missing_ok=True)

    # Deploy session + agent modules so soak/EAGAIN code is live on .108
    for name in (
        "bcl_dummy_hu_agent.py",
        "bcl_dummy_hu.py",
        "bcl_etch_stub.py",
        "bcl_framer.py",
        "etch_codec.py",
    ):
        scp_to(ROOT / "tools" / name, f"/tmp/bcl_dummy/{name}", host=host)

    music_np = bool(args.rhmi_music_np_seq)
    pidrive = bool(args.rhmi_pidrive_seq) and not music_np
    soak = bool(args.rhmi_soak) and not music_np and not pidrive
    # Deploy Field Music DESCRIPTION alongside agent modules when NP spine is selected.
    if music_np:
        desc = (
            ROOT
            / "docs"
            / "evidence"
            / "FIELD_B3_GATEB_20261121T112446Z"
            / "resources"
            / "ui_description_multimedia_v3.xml"
        )
        if desc.is_file():
            scp_to(desc, "/tmp/bcl_dummy/ui_description_multimedia_v3.xml", host=host)
    env = (
        f"HU_BD={HU_BD} PHONE_BD={phone_bd} HU_IP={HU_IP} PHONE_IP={phone_ip} "
        f"RFCOMM_CHANNEL={args.channel} HOLD_S={args.hold} OUT_DIR={remote_out} "
        f"BCL_PHONE={'0' if args.no_bcl_phone else '1'} "
        f"BCL_RHMI_SOAK={'1' if soak else '0'} "
        f"BCL_RHMI_PIDRIVE_SEQ={'1' if pidrive else '0'} "
        f"BCL_RHMI_MUSIC_NP_SEQ={'1' if music_np else '0'} "
        f"MENU_TEST_ACTION=200 "
        f"MUSIC_NP_ACTION_PRIMARY=336 MUSIC_NP_ACTION_SECONDARY=248"
    )
    timeout = max(180.0, args.hold + 120.0)
    print(f"remote OUT={remote_out} hold={args.hold}s", flush=True)
    p = ssh(
        f"bash -lc {shlex.quote(f'mkdir -p {remote_out} && {env} python3 /tmp/lab_p0_dual_esp_hold_remote.py')}",
        timeout=timeout,
        host=host,
    )
    print(p.stdout)
    if p.stderr:
        print(p.stderr, file=sys.stderr)

    # fetch hold.json
    subprocess.run(
        ["scp", "-o", "BatchMode=yes", f"{host}:{remote_out}/hold.json", str(local_out)],
        check=False,
        timeout=60,
    )
    md = local_out.with_suffix(".md")
    try:
        data = json.loads(local_out.read_text())
    except Exception:
        data = {"raw_stdout": p.stdout, "returncode": p.returncode}

    lines = [
        f"# LAB P0 dual-ESP hold — {stamp}",
        "",
        f"- remote: `{remote_out}`",
        f"- hold requested: **{args.hold}s**",
        f"- bond.paired: **{(data.get('bond') or {}).get('paired')}**",
        f"- bond.error: `{(data.get('bond') or {}).get('error')}`",
        f"- hold.ok: **{(data.get('hold') or {}).get('ok')}**",
        f"- sent/rx: {(data.get('hold') or {}).get('sent')} / {(data.get('hold') or {}).get('rx')}",
        f"- send_err: `{(data.get('hold') or {}).get('send_err')}`",
        f"- esp_deltas: {len(data.get('esp_deltas') or [])}",
        f"- hu_key_events: {len(data.get('hu_key_events') or [])}",
        "",
        "## ESP last sample",
        "",
        f"```json\n{json.dumps(data.get('esp_last'), indent=2)}\n```",
        "",
    ]
    md.write_text("\n".join(lines) + "\n")
    print(f"wrote {local_out} and {md}", flush=True)
    return 0 if p.returncode == 0 else p.returncode


if __name__ == "__main__":
    raise SystemExit(main())
