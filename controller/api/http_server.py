"""HTTP API + static Lab UI for bt-analyzer (ports default 8081)."""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from controller import agent_view
from controller import session as btac_session
from controller.btmon_live import live as btmon_live

WEB_ROOT = Path(__file__).resolve().parents[2] / "web"
STARTED = time.time()
VERSION = "0.3.16"

# Poll-proxy lab nodes (OBSERVE) — no HELLO required yet
LAB_NODES = [
    {"id": "observe_a", "ip": "192.168.178.88", "role": "OBSERVE_A"},
    {"id": "observe_b", "ip": "192.168.178.89", "role": "OBSERVE_B"},
    {"id": "classic_esp32", "ip": "192.168.178.87", "role": "F_ONCHIP_CLASSIC"},
]

# PROXY Classic slots (Network HCI) — see docs/PROXY.md
PROXY_CONTROLLERS = [
    {
        "id": "phone_side",
        "slot": "A",
        "ip": "192.168.178.131",
        "role": "PROXY_PHONE_SIDE",
        "flash_blocked_default": False,
    },
    {
        "id": "car_side",
        "slot": "B",
        "ip": "192.168.178.87",
        "role": "PROXY_CAR_SIDE",
        "flash_blocked_default": False,
    },
]


def _get_json(url: str, timeout: float = 2.5) -> dict[str, Any]:
    req = urllib.request.Request(url, method="GET")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8", errors="replace"))


def _get_text(url: str, timeout: float = 3.0) -> tuple[int, str]:
    req = urllib.request.Request(url, method="GET")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.status, resp.read().decode("utf-8", errors="replace")


def _post_form(url: str, fields: dict[str, str], timeout: float = 5.0) -> tuple[int, str]:
    data = urllib.parse.urlencode(fields).encode()
    req = urllib.request.Request(url, data=data, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.status, resp.read().decode("utf-8", errors="replace")


def fetch_node(ip: str) -> dict[str, Any]:
    out: dict[str, Any] = {"ip": ip, "ok": False}
    try:
        st = _get_json(f"http://{ip}/api/status")
        out["ok"] = True
        out["status"] = st
        try:
            out["usb"] = _get_json(f"http://{ip}/api/usb/status")
        except Exception as exc:  # noqa: BLE001
            out["usb_error"] = str(exc)
    except Exception as exc:  # noqa: BLE001
        out["error"] = str(exc)
    return out


def classify_proxy_status(st: dict[str, Any] | None, error: str | None = None) -> dict[str, Any]:
    """Classify HTTP /api/status for PROXY P0 (Heizung vs bt-analyzer Classic)."""
    if error or st is None:
        return {
            "class": "UNREACHABLE",
            "bt_analyzer": False,
            "classic_ready": False,
            "error": error,
        }
    if "value" in st and "unit" in st and "onchip" not in st and "version" not in st:
        return {
            "class": "HEIZUNG_METERMASTER",
            "bt_analyzer": False,
            "classic_ready": False,
            "flash_blocked": True,
            "label": st.get("label"),
        }
    agent = st.get("hciAgent")
    if agent is not None:
        return {
            "class": "HCI_AGENT",
            "bt_analyzer": True,
            "classic_ready": bool(agent.get("ready")),
            "flash_blocked": False,
            "version": st.get("version"),
            "bd_addr": agent.get("bdAddr"),
            "client": agent.get("client"),
        }
    oc = st.get("onchip") or {}
    if "onchip" in st or st.get("version"):
        classic = bool(oc.get("classic"))
        ready = bool(oc.get("ready"))
        return {
            "class": "BT_ANALYZER",
            "bt_analyzer": True,
            "classic_ready": classic and ready,
            "flash_blocked": False,
            "version": st.get("version"),
            "chip": st.get("chip"),
            "bd_addr": oc.get("bdAddr"),
            "state": oc.get("state"),
            "classic": classic,
            "ble": oc.get("ble"),
        }
    return {"class": "UNKNOWN_HTTP", "bt_analyzer": False, "classic_ready": False}


def fetch_proxy_controllers() -> dict[str, Any]:
    views = []
    for meta in PROXY_CONTROLLERS:
        snap = fetch_node(meta["ip"])
        st = snap.get("status") if snap.get("ok") else None
        classified = classify_proxy_status(st, None if snap.get("ok") else snap.get("error"))
        if classified.get("class") == "HEIZUNG_METERMASTER":
            classified["flash_blocked"] = True
        views.append({**meta, "ok": bool(snap.get("ok")), "classified": classified, "raw_ok": snap.get("ok")})
    car = next((v for v in views if v["id"] == "car_side"), None)
    phone = next((v for v in views if v["id"] == "phone_side"), None)
    dual = bool(
        car
        and phone
        and (car.get("classified") or {}).get("classic_ready")
        and (phone.get("classified") or {}).get("classic_ready")
    )
    return {
        "ok": True,
        "hci_transport": "network_hci_wifi",
        "dual_classic_ready": dual,
        "controllers": views,
        "doc": "docs/PROXY.md",
    }


class Handler(BaseHTTPRequestHandler):
    server_version = "bt-analyzer-controller/" + VERSION

    def log_message(self, fmt: str, *args: Any) -> None:
        print(f"[http] " + (fmt % args))

    def _send(self, code: int, body: bytes, content_type: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, code: int, obj: Any) -> None:
        raw = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self._send(code, raw, "application/json; charset=utf-8")

    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path

        if path in ("/", "/index.html"):
            self._serve_file(WEB_ROOT / "index.html", "text/html; charset=utf-8")
            return
        if path == "/styles.css":
            self._serve_file(WEB_ROOT / "styles.css", "text/css; charset=utf-8")
            return
        if path == "/app.js":
            self._serve_file(WEB_ROOT / "app.js", "application/javascript; charset=utf-8")
            return

        if path == "/api/v1/health":
            self._send_json(
                200,
                {
                    "ok": True,
                    "service": "bt-analyzer",
                    "version": VERSION,
                    "uptime_s": int(time.time() - STARTED),
                    "http_port_note": "8081 (usb-analyzer uses 8080)",
                    "control_port_note": "9751 (usb-analyzer uses 9750)",
                    "btac_port_note": "9753 on ESP (BTAC v1)",
                    "session": btac_session.status(),
                    "nodes": LAB_NODES,
                    "proxy": {
                        "hci_transport": "network_hci_wifi",
                        "controllers": PROXY_CONTROLLERS,
                    },
                },
            )
            return

        if path == "/api/v1/proxy/controllers":
            self._send_json(200, fetch_proxy_controllers())
            return

        if path == "/api/v1/proxy/session":
            self._send_json(200, {"ok": True, "proxy": btac_session.proxy_status()})
            return

        if path == "/api/v1/agents":
            agents = [{**meta, **agent_view.fetch_agent(meta["ip"])} for meta in PROXY_CONTROLLERS]
            self._send_json(200, {"ok": True, "agents": agents})
            return

        if path == "/api/v1/btmon":
            qs = parse_qs(parsed.query)
            since_arg = (qs.get("since") or ["0"])[0]
            since = int(since_arg) if since_arg.isdigit() else 0
            hci_arg = (qs.get("hci") or [""])[0]
            hci = int(hci_arg) if hci_arg.isdigit() else None
            self._send_json(200, btmon_live.since(since, hci=hci))
            return

        if path == "/api/v1/proxy/session/frames":
            qs = parse_qs(parsed.query)
            n = int((qs.get("n") or ["48"])[0])
            side = (qs.get("side") or ["phone_side"])[0]
            if side in ("phone", "a"):
                side = "phone_side"
            if side in ("car", "b"):
                side = "car_side"
            self._send_json(200, btac_session.recent_frames(n, name=side))
            return

        if path == "/api/v1/session":
            self._send_json(200, {"ok": True, "session": btac_session.status()})
            return

        if path == "/api/v1/session/frames":
            qs = parse_qs(parsed.query)
            n = int((qs.get("n") or ["64"])[0])
            name = (qs.get("name") or ["default"])[0]
            self._send_json(200, btac_session.recent_frames(n, name=name))
            return

        if path == "/api/v1/session/download":
            st = btac_session.status()
            p = Path(st["path"]) if st.get("path") else None
            if not p or not p.is_file():
                self._send_json(404, {"ok": False, "error": "no_capture_file"})
                return
            data = p.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "application/octet-stream")
            self.send_header("Content-Disposition", f'attachment; filename="{p.name}"')
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(data)
            return

        if path == "/api/v1/nodes":
            views = []
            for n in LAB_NODES:
                snap = fetch_node(n["ip"])
                views.append({**n, **snap})
            self._send_json(200, {"ok": True, "nodes": views})
            return

        if path.startswith("/api/v1/node/"):
            # /api/v1/node/<ip>/status|usb|drain
            parts = [p for p in path.split("/") if p]
            # api v1 node <ip> <action>
            if len(parts) < 5:
                self._send_json(404, {"ok": False, "error": "path"})
                return
            ip = parts[3]
            action = parts[4]
            qs = parse_qs(parsed.query)
            try:
                if action == "status":
                    self._send_json(200, {"ok": True, "ip": ip, "status": _get_json(f"http://{ip}/api/status")})
                    return
                if action == "usb":
                    self._send_json(200, {"ok": True, "ip": ip, "usb": _get_json(f"http://{ip}/api/usb/status")})
                    return
                if action == "drain":
                    n = int((qs.get("n") or ["32"])[0])
                    code, text = _get_text(f"http://{ip}/api/capture/drain?n={n}")
                    self._send(code, text.encode("utf-8"), "application/x-ndjson; charset=utf-8")
                    return
                if action == "devices":
                    dj = _get_json(f"http://{ip}/api/bt/devices")
                    self._send_json(200, {"ok": True, "ip": ip, **dj})
                    return
            except Exception as exc:  # noqa: BLE001
                self._send_json(502, {"ok": False, "ip": ip, "error": str(exc)})
                return

        self._send_json(404, {"ok": False, "error": "not_found"})

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b""
        ctype = self.headers.get("Content-Type") or ""

        fields: dict[str, str] = {}
        if "application/json" in ctype and raw:
            try:
                obj = json.loads(raw.decode("utf-8"))
                if isinstance(obj, dict):
                    fields = {str(k): str(v) for k, v in obj.items()}
            except json.JSONDecodeError:
                fields = {}
        else:
            fields = {k: (v[0] if v else "") for k, v in parse_qs(raw.decode("utf-8", errors="replace")).items()}

        if path == "/api/v1/btmon/start":
            self._send_json(200, btmon_live.start())
            return
        if path == "/api/v1/btmon/stop":
            self._send_json(200, btmon_live.stop())
            return

        parts = [p for p in path.split("/") if p]
        if len(parts) >= 4 and parts[0] == "api" and parts[1] == "v1" and parts[2] == "proxy" and parts[3] == "session":
            action = parts[4] if len(parts) >= 5 else ""
            if action == "start":
                self._send_json(
                    200,
                    btac_session.proxy_start(
                        phone_ip=fields.get("phone_ip") or None,
                        car_ip=fields.get("car_ip") or None,
                        port=int(fields.get("port") or 9753),
                    ),
                )
                return
            if action == "stop":
                self._send_json(200, btac_session.proxy_stop())
                return

        if len(parts) >= 4 and parts[0] == "api" and parts[1] == "v1" and parts[2] == "session":
            action = parts[3]
            if action == "start":
                ip = fields.get("ip") or fields.get("host") or ""
                if not ip:
                    self._send_json(400, {"ok": False, "error": "ip_required"})
                    return
                port = int(fields.get("port") or 9753)
                name = fields.get("name") or "default"
                self._send_json(200, btac_session.start(ip, port, name=name))
                return
            if action == "stop":
                name = fields.get("name") or "default"
                self._send_json(200, btac_session.stop(name=name))
                return

        # api v1 node <ip> inject|hci-write|advertise|scan|connect|gatt
        if len(parts) >= 5 and parts[0] == "api" and parts[1] == "v1" and parts[2] == "node":
            ip = parts[3]
            action = parts[4]
            try:
                if action == "inject":
                    code, text = _post_form(f"http://{ip}/api/capture/inject", {"hex": fields.get("hex", "")})
                    self._send(code, text.encode("utf-8"), "application/json; charset=utf-8")
                    return
                if action == "hci-write":
                    code, text = _post_form(f"http://{ip}/api/hci/write", {"hex": fields.get("hex", "")})
                    self._send(code, text.encode("utf-8"), "application/json; charset=utf-8")
                    return
                proxy_map = {
                    "scan-start": "/api/bt/scan/start",
                    "scan-stop": "/api/bt/scan/stop",
                    "inquiry-start": "/api/bt/inquiry/start",
                    "inquiry-stop": "/api/bt/inquiry/stop",
                    "advertise-start": "/api/bt/advertise/start",
                    "advertise-stop": "/api/bt/advertise/stop",
                    "connect": "/api/bt/connect",
                    "disconnect": "/api/bt/disconnect",
                    "gatt-read-name": "/api/bt/gatt/read-name",
                    "discoverable-start": "/api/bt/discoverable/start",
                    "discoverable-stop": "/api/bt/discoverable/stop",
                    "classic-name": "/api/bt/classic/name",
                    "throughput-start": "/api/bt/throughput/start",
                    "throughput-stop": "/api/bt/throughput/stop",
                    "att-mtu": "/api/bt/att/mtu",
                    "ftms-start": "/api/bt/flavor/ftms/start",
                }
                if action in proxy_map:
                    code, text = _post_form(f"http://{ip}{proxy_map[action]}", fields)
                    self._send(code, text.encode("utf-8"), "application/json; charset=utf-8")
                    return
            except Exception as exc:  # noqa: BLE001
                self._send_json(502, {"ok": False, "error": str(exc)})
                return

        self._send_json(404, {"ok": False, "error": "not_found"})

    def _serve_file(self, path: Path, content_type: str) -> None:
        if not path.is_file():
            self._send_json(404, {"ok": False, "error": f"missing {path.name}"})
            return
        self._send(200, path.read_bytes(), content_type)


def serve_forever(host: str, port: int) -> None:
    httpd = ThreadingHTTPServer((host, port), Handler)
    httpd.serve_forever()
