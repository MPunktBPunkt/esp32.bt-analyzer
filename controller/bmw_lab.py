"""BMW F20 Connected Lab — CDS vehicle data store, Etch RPC workbench & F20 HU simulator.

Backs the `:8081` Lab UI card "BMW Connected Lab (CDS & F20 Simulator)" with two explicit
authorization modes so simulated runs are never mistaken for real F20 authentication:
  - SIMULATED_AUTHORIZATION: accepts any cert & any custom RHMI XML/resources
  - F20_STRICT_WHITELIST:    verifies resource SHA-256 against SAS.Digests.* from the .p7b
"""

from __future__ import annotations

import json
import re
import sys
import threading
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
TOOLS_DIR = REPO_ROOT / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from bcl_framer import DEST_ETCH_DESK, BclFramer, build_synthetic_frame  # noqa: E402

CMD_DATA = 2
from etch_codec import (  # noqa: E402
    CDS_BY_NAME,
    CDS_CATALOG,
    ETCH_MAGIC,
    RHMI_PROPERTIES,
    RHMI_RESOURCE_TYPES,
    build_cds_add_handler_call,
    build_cds_event,
    build_cds_get_property_call,
    build_rhmi_set_data_call,
    build_rhmi_set_property_call,
    decode_etch_message,
    encode_etch_packet,
    inspect_pkcs7_bundle,
    sha256_hex,
)

AUTH_MODES = ("SIMULATED_AUTHORIZATION", "F20_STRICT_WHITELIST")

# Default F20 118d LCI (2017) capability map (measured flags + representative NBT Evo ID5/ID6 keys)
DEFAULT_F20_CAPABILITIES: dict[str, str] = {
    "hmi.type": "BMW ID5",
    "hmi.version": "NBTevo_S_2026_F20_sim",
    "hmi.display-width": "1280",
    "hmi.display-height": "480",
    "hmi.role": "HU",
    "vehicle.type": "F20",
    "vehicle.country": "DE",
    "a4axl": "true",
    "tts": "true",
    "navi": "true",
    "map": "true",
    "voice": "true",
    "speedlock": "true",
    "touch_command": "false",
    "_ENT_MTP_OFF": "false",
    "iva_ENT_USB_COVER_ART_IPOD": "true",
    "iva_MYV_LIGHT_INTERIOR": "false",
    "iva_TC_REAR_WINDOW_C": "not_active",
}

DEFAULT_CDS_VALUES: dict[str, dict[str, Any]] = {
    "vehicle.VIN": {"VIN": "WBA1S51080V838304"},
    "vehicle.type": {"type": 15},
    "vehicle.country": {"country": 4},
    "vehicle.units": {"units": {"distance": 1, "fuel": 1, "temperature": 1}},
    "engine.RPMSpeed": {"RPMSpeed": 830},
    "driving.speedActual": {"speedActual": 0},
    "driving.speedDisplayed": {"speedDisplayed": 0},
    "driving.odometer": {"odometer": 114280},
    "driving.gear": {"gear": 0},
    "engine.temperature": {"temperature": {"engine": 88, "oil": 92}},
    "engine.consumption": {"consumption": 5.1},
    "engine.info": {"info": {"fuelType": 5, "numCylinders": 4, "capacity": 1995}},
    "sensors.fuel": {"fuel": {"range": 640, "reserve": 0, "tanklevel": 38}},
    "sensors.battery": {"battery": 84},
    "sensors.batteryTemp": {"batteryTemp": 21},
    "sensors.SOCBatteryHybrid": {"SOCBatteryHybrid": 255.0},  # Diesel invalid sentinel (C-BT39)
    "sensors.temperatureExterior": {"temperatureExterior": 13.5},
    "sensors.temperatureInterior": {"temperatureInterior": 20.5},
    "controls.lights": {"lights": {"brights": 0, "fogRear": 0, "parking": 1}},
    "entertainment.multimedia": {"multimedia": {"source": 5, "title": "Bayern 3", "artist": "PiDrive", "album": "USB/DAB"}},
    "entertainment.radioStation": {"radioStation": {"name": "BR3", "frequency": 98500}},
}


def parse_rhmi_xml_preview(xml_bytes: bytes) -> dict[str, Any]:
    """Parse an RHMI ui_description.xml (or lightweight demo XML) into states/components/models."""
    root = ET.fromstring(xml_bytes.decode("utf-8", errors="replace"))
    states: dict[str, Any] = {}
    components: dict[str, Any] = {}
    models: dict[str, Any] = {}
    actions: dict[str, Any] = {}

    for m in root.findall(".//models/*"):
        mid = m.attrib.get("id")
        if mid is not None:
            models[str(mid)] = {
                "id": int(mid) if mid.isdigit() else mid,
                "modelType": m.tag,
                "value": m.attrib.get("value", ""),
            }
    for act in root.findall(".//actions/*"):
        aid = act.attrib.get("id")
        if aid is not None:
            actions[str(aid)] = {
                "id": int(aid) if aid.isdigit() else aid,
                "actionType": act.tag,
                "targetModel": act.attrib.get("targetModel") or act.attrib.get("target"),
            }
    for st in root.findall(".//hmiStates/*"):
        sid = st.attrib.get("id")
        if sid is None:
            continue
        comp_list = []
        for comp in st.findall(".//components/*"):
            cid = comp.attrib.get("id")
            if cid is None:
                continue
            cobj = {
                "id": int(cid) if cid.isdigit() else cid,
                "type": comp.tag,
                "model": int(comp.attrib["model"]) if comp.attrib.get("model", "").isdigit() else comp.attrib.get("model"),
                "textModel": int(comp.attrib["textModel"]) if comp.attrib.get("textModel", "").isdigit() else comp.attrib.get("textModel"),
                "action": int(comp.attrib["action"]) if comp.attrib.get("action", "").isdigit() else comp.attrib.get("action"),
                "properties": {"VISIBLE": True, "ENABLED": True, "SELECTABLE": True},
            }
            components[str(cid)] = cobj
            comp_list.append(cobj["id"])
        states[str(sid)] = {
            "id": int(sid) if sid.isdigit() else sid,
            "stateType": st.tag,
            "titleModel": int(st.attrib["textModel"]) if st.attrib.get("textModel", "").isdigit() else st.attrib.get("textModel"),
            "title": st.attrib.get("title", f"State {sid}"),
            "components": comp_list,
        }
    return {
        "pluginAppType": root.attrib.get("type", root.tag),
        "models": models,
        "actions": actions,
        "states": states,
        "components": components,
    }


DEMO_PIDRIVE_XML = """<pluginApps type="PiDriveDemo">
  <models>
    <textModel id="100" value="PiDrive Radio &amp; Fahrzeug" />
    <textModel id="101" value="Sender: Bayern 3 (Live)" />
    <raDataModel id="102" value="" />
    <textModel id="103" value="Nächster Sender" />
    <textModel id="104" value="Fahrzeugdaten aktualisieren" />
  </models>
  <actions>
    <raAction id="200" />
    <raAction id="201" />
    <combinedAction id="202" target="11" />
  </actions>
  <hmiStates>
    <toolbarHmiState id="10" textModel="100" title="PiDrive Hauptmenü">
      <components>
        <label id="300" model="101" />
        <button id="301" model="103" action="200" />
        <button id="302" model="104" action="201" />
        <list id="303" model="102" action="202" />
      </components>
    </toolbarHmiState>
  </hmiStates>
</pluginApps>
"""


class BmwConnectedLab:
    """Thread-safe F20 simulator, Etch workbench & CDS vehicle table for :8081."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.auth_mode: str = "SIMULATED_AUTHORIZATION"
        self.capabilities: dict[str, str] = dict(DEFAULT_F20_CAPABILITIES)
        self.cds_values: dict[str, dict[str, Any]] = {
            k: dict(v) for k, v in DEFAULT_CDS_VALUES.items()
        }
        self.cds_updated_at: dict[str, float] = {
            k: time.time() for k in DEFAULT_CDS_VALUES
        }
        self.cds_source: dict[str, str] = {
            k: "sim_default" for k in DEFAULT_CDS_VALUES
        }
        self._msg_seq: int = 1
        self._next_handle: int = 10
        # Per logical BCL src channel (10..19)
        self.channels: dict[int, dict[str, Any]] = {}
        self.registered_apps: dict[str, dict[str, Any]] = {}
        self.rhmi_apps: dict[int, dict[str, Any]] = {}
        self.rpc_log: list[dict[str, Any]] = []
        self.outbound_queue: list[dict[str, Any]] = []
        # Seed a ready-to-explore demo RHMI screen in simulated mode
        self._seed_demo_rhmi_unlocked()

    def _next_msg_id(self) -> int:
        v = self._msg_seq
        self._msg_seq += 1
        return v

    def _log(self, direction: str, src: int, method: str, detail: dict[str, Any], bcl_frame: bytes | None = None) -> dict[str, Any]:
        entry = {
            "seq": len(self.rpc_log) + 1,
            "ts": round(time.time(), 3),
            "dir": direction,
            "src": src,
            "dest": DEST_ETCH_DESK,
            "auth_mode": self.auth_mode,
            "method": method,
            "detail": detail,
            "bcl_len": len(bcl_frame) if bcl_frame else None,
            "bcl_hex_head": bcl_frame[:40].hex() if bcl_frame else None,
        }
        self.rpc_log.append(entry)
        if len(self.rpc_log) > 250:
            del self.rpc_log[: len(self.rpc_log) - 250]
        return entry

    def _seed_demo_rhmi_unlocked(self) -> None:
        parsed = parse_rhmi_xml_preview(DEMO_PIDRIVE_XML.encode("utf-8"))
        parsed["models"]["102"]["value"] = [
            ["VIN", self.cds_values["vehicle.VIN"]["VIN"]],
            ["Drehzahl", f"{self.cds_values['engine.RPMSpeed']['RPMSpeed']} rpm"],
            ["Kilometerstand", f"{self.cds_values['driving.odometer']['odometer']} km"],
            ["Tankreichweite", f"{self.cds_values['sensors.fuel']['fuel']['range']} km"],
        ]
        self.rhmi_apps[1] = {
            "handle": 1,
            "src": 19,
            "appId": "pidrive.demo.menu",
            "name": "PiDrive Connected Demo",
            "vendor": "PiDrive Lab",
            "initialized": True,
            "auth_badge": "SIMULATED_AUTHORIZATION",
            "xml_sha256": sha256_hex(DEMO_PIDRIVE_XML.encode("utf-8")),
            **parsed,
        }

    # ------------------------------------------------------------------
    # Public state snapshot for GUI
    # ------------------------------------------------------------------

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            cds_rows = []
            for ident, name in sorted(CDS_CATALOG.items()):
                val = self.cds_values.get(name)
                cds_rows.append(
                    {
                        "ident": ident,
                        "name": name,
                        "value": val,
                        "source": self.cds_source.get(name, "unqueried"),
                        "updated_at": self.cds_updated_at.get(name),
                    }
                )
            # Include any custom/extra properties seen on wire
            known_names = set(CDS_CATALOG.values())
            for name, val in sorted(self.cds_values.items()):
                if name not in known_names:
                    cds_rows.append(
                        {
                            "ident": CDS_BY_NAME.get(name, -1),
                            "name": name,
                            "value": val,
                            "source": self.cds_source.get(name, "wire"),
                            "updated_at": self.cds_updated_at.get(name),
                        }
                    )
            return {
                "ok": True,
                "auth_mode": self.auth_mode,
                "auth_modes": list(AUTH_MODES),
                "capabilities_count": len(self.capabilities),
                "capabilities": dict(self.capabilities),
                "cds": cds_rows,
                "channels": {str(k): dict(v) for k, v in sorted(self.channels.items())},
                "registered_apps": dict(self.registered_apps),
                "rhmi_apps": {str(k): v for k, v in self.rhmi_apps.items()},
                "rhmi_properties_catalog": {str(k): v for k, v in RHMI_PROPERTIES.items()},
                "outbound_pending": len(self.outbound_queue),
                "rpc_log": list(self.rpc_log[-80:]),
                "lab_certs_available": self.list_lab_certs(),
            }

    def list_lab_certs(self) -> list[str]:
        cert_dir = REPO_ROOT / "docs" / "evidence" / "LAB_DUMMY_ETCH_20261114T1550Z_certs"
        if not cert_dir.is_dir():
            return []
        return sorted(p.name for p in cert_dir.glob("*.pem"))

    # ------------------------------------------------------------------
    # Mode & CDS controls
    # ------------------------------------------------------------------

    def set_auth_mode(self, mode: str) -> dict[str, Any]:
        m = (mode or "").strip().upper()
        if m not in AUTH_MODES:
            return {"ok": False, "error": f"mode must be one of {AUTH_MODES}"}
        with self._lock:
            self.auth_mode = m
            self._log("note", 0, "set_auth_mode", {"auth_mode": m})
        return {"ok": True, "auth_mode": m}

    def update_cds_value(self, prop_name: str, value: Any, *, source: str = "sim_ui") -> dict[str, Any]:
        if not prop_name:
            return {"ok": False, "error": "propertyName required"}
        if isinstance(value, str):
            try:
                parsed = json.loads(value)
                value = parsed if isinstance(parsed, dict) else {prop_name.split(".")[-1]: parsed}
            except json.JSONDecodeError:
                # Convenience: numeric string -> number under leaf key
                leaf = prop_name.split(".")[-1]
                try:
                    num = float(value) if "." in value else int(value)
                    value = {leaf: num}
                except ValueError:
                    value = {leaf: value}
        elif isinstance(value, (int, float, bool)):
            value = {prop_name.split(".")[-1]: value}
        elif not isinstance(value, dict):
            value = {"value": str(value)}

        with self._lock:
            self.cds_values[prop_name] = value
            self.cds_updated_at[prop_name] = time.time()
            self.cds_source[prop_name] = source
            # Keep demo list synced when RPM/VIN/odometer/fuel change
            self._sync_demo_list_unlocked()
            msg_id = self._next_msg_id()
            etch_pkt = build_cds_event(handle=12, prop_name=prop_name, value_obj=value, msg_id=msg_id)
            bcl_frame = build_synthetic_frame(CMD_DATA, 12, DEST_ETCH_DESK, etch_pkt)
            self.outbound_queue.append(
                {
                    "ts": time.time(),
                    "dir": "hu_to_phone",
                    "src": 12,
                    "dest": DEST_ETCH_DESK,
                    "method": "cds_onPropertyChangedEvent",
                    "bcl_hex": bcl_frame.hex(),
                }
            )
            ev = self._log(
                "hu->phone",
                12,
                "cds_onPropertyChangedEvent",
                {"ident": str(CDS_BY_NAME.get(prop_name, "?")), "propertyName": prop_name, "value": value},
                bcl_frame,
            )
        return {"ok": True, "propertyName": prop_name, "value": value, "bcl_hex": bcl_frame.hex(), "log": ev}

    def _sync_demo_list_unlocked(self) -> None:
        app = self.rhmi_apps.get(1)
        if not app or "102" not in app.get("models", {}):
            return
        app["models"]["102"]["value"] = [
            ["VIN", str((self.cds_values.get("vehicle.VIN") or {}).get("VIN", "—"))],
            ["Drehzahl", f"{(self.cds_values.get('engine.RPMSpeed') or {}).get('RPMSpeed', '—')} rpm"],
            ["Tempo", f"{(self.cds_values.get('driving.speedActual') or {}).get('speedActual', '—')} km/h"],
            ["Kilometerstand", f"{(self.cds_values.get('driving.odometer') or {}).get('odometer', '—')} km"],
            ["Tankreichweite", f"{((self.cds_values.get('sensors.fuel') or {}).get('fuel') or {}).get('range', '—')} km"],
            ["Bordbatterie", f"{(self.cds_values.get('sensors.battery') or {}).get('battery', '—')} %"],
        ]

    def build_active_cds_query(self, prop_name: str, *, src: int = 12, handle: int = 12, subscribe: bool = True) -> dict[str, Any]:
        """Build wire-exact Phone→HU `cds_getPropertyAsync` (+ optional subscription) BCL frames.

        In Simulator mode, immediately answers from the F20 Simulator store so the full
        request→reply roundtrip can be tested directly in the GUI.
        """
        if prop_name not in CDS_BY_NAME and "." not in prop_name:
            return {"ok": False, "error": f"unknown CDS property {prop_name!r}"}
        frames_hex: list[str] = []
        with self._lock:
            if subscribe:
                mid_sub = self._next_msg_id()
                sub_etch = build_cds_add_handler_call(handle, prop_name, 1000, mid_sub)
                sub_bcl = build_synthetic_frame(CMD_DATA, src, DEST_ETCH_DESK, sub_etch)
                frames_hex.append(sub_bcl.hex())
                self._log(
                    "phone->hu",
                    src,
                    "cds_addPropertyChangedEventHandler",
                    {"handle": handle, "propertyName": prop_name, "intervalLimit": 1000},
                    sub_bcl,
                )
            mid_get = self._next_msg_id()
            get_etch = build_cds_get_property_call(handle, prop_name, mid_get)
            get_bcl = build_synthetic_frame(CMD_DATA, src, DEST_ETCH_DESK, get_etch)
            frames_hex.append(get_bcl.hex())
            self.outbound_queue.append(
                {
                    "ts": time.time(),
                    "dir": "phone_to_hu",
                    "src": src,
                    "dest": DEST_ETCH_DESK,
                    "method": "cds_getPropertyAsync",
                    "bcl_hex": get_bcl.hex(),
                }
            )
            self._log(
                "phone->hu",
                src,
                "cds_getPropertyAsync",
                {"handle": handle, "ident": str(CDS_BY_NAME.get(prop_name, "?")), "propertyName": prop_name},
                get_bcl,
            )
            # Simulated HU immediately answers with _result_cds_getPropertyAsync + cds_onPropertyChangedEvent
            ack_etch = encode_etch_packet(
                "_result_cds_getPropertyAsync",
                {"_inReplyTo": mid_get, "_messageId": self._next_msg_id()},
            )
            ack_bcl = build_synthetic_frame(CMD_DATA, src, DEST_ETCH_DESK, ack_etch)
            val = self.cds_values.get(prop_name, {prop_name.split(".")[-1]: None})
            ev_etch = build_cds_event(handle, prop_name, val, self._next_msg_id())
            ev_bcl = build_synthetic_frame(CMD_DATA, src, DEST_ETCH_DESK, ev_etch)
            self.cds_updated_at[prop_name] = time.time()
            self._log("hu->phone", src, "_result_cds_getPropertyAsync", {"_inReplyTo": mid_get}, ack_bcl)
            self._log("hu->phone", src, "cds_onPropertyChangedEvent", {"propertyName": prop_name, "value": val}, ev_bcl)
        return {
            "ok": True,
            "propertyName": prop_name,
            "ident": CDS_BY_NAME.get(prop_name),
            "tx_bcl_frames_hex": frames_hex,
            "simulated_hu_value": val,
        }

    # ------------------------------------------------------------------
    # PKCS7 + RHMI resource whitelist check & live UI updates
    # ------------------------------------------------------------------

    def check_or_load_rhmi_package(
        self,
        *,
        cert_name_or_pem: str = "",
        xml_text: str = "",
        src: int = 19,
        app_id: str = "custom.pidrive.app",
        app_title: str = "PiDrive Custom App",
    ) -> dict[str, Any]:
        """Validate a (.p7b, ui_description.xml) pair under current auth_mode and mount it if accepted."""
        pem_bytes = b""
        cert_info: dict[str, Any] | None = None
        if cert_name_or_pem.strip():
            cand = (
                REPO_ROOT
                / "docs"
                / "evidence"
                / "LAB_DUMMY_ETCH_20261114T1550Z_certs"
                / cert_name_or_pem.strip()
            )
            if cand.is_file():
                pem_bytes = cand.read_bytes()
            else:
                pem_bytes = cert_name_or_pem.encode("utf-8")
            try:
                cert_info = inspect_pkcs7_bundle(pem_bytes)
            except Exception as exc:  # noqa: BLE001
                return {"ok": False, "error": f"invalid PKCS7 cert: {exc}"}

        xml_raw = (xml_text.strip() or DEMO_PIDRIVE_XML).encode("utf-8")
        xml_hash = sha256_hex(xml_raw)
        allowed_hashes = (cert_info or {}).get("rhmi_description_sha256") or []
        digest_match = xml_hash in allowed_hashes

        with self._lock:
            mode = self.auth_mode
            if mode == "F20_STRICT_WHITELIST":
                if not cert_info:
                    self._log(
                        "hu->phone",
                        src,
                        "SecurityException",
                        {"reason": "missing_sas_certificate", "xml_sha256": xml_hash},
                    )
                    return {
                        "ok": False,
                        "accepted": False,
                        "auth_mode": mode,
                        "reason": "F20_STRICT_WHITELIST verlangt ein gültiges BMW .p7b-Zertifikat (SAS).",
                        "xml_sha256": xml_hash,
                        "allowed_rhmi_sha256": allowed_hashes,
                    }
                if not digest_match:
                    self._log(
                        "hu->phone",
                        src,
                        "SecurityException",
                        {
                            "reason": "rhmi_description_sha256_not_in_cert_whitelist",
                            "xml_sha256": xml_hash,
                            "allowed": allowed_hashes,
                            "cert_cns": cert_info.get("cns"),
                        },
                    )
                    return {
                        "ok": False,
                        "accepted": False,
                        "auth_mode": mode,
                        "reason": "Abgelehnt wie am echten F20: SHA-256 der ui_description.xml steht nicht in SAS.Digests.RHMIDescriptions des APP-Zertifikats!",
                        "xml_sha256": xml_hash,
                        "allowed_rhmi_sha256": allowed_hashes,
                        "cert": cert_info,
                    }

            try:
                parsed = parse_rhmi_xml_preview(xml_raw)
            except ET.ParseError as exc:
                return {"ok": False, "error": f"XML-Fehler: {exc}"}

            handle = self._next_handle
            self._next_handle += 1
            badge = "F20_WHITELIST_MATCH" if digest_match else "SIMULATED_AUTHORIZATION"
            self.channels[src] = {
                "src": src,
                "sas_logged_in": True,
                "auth_badge": badge,
                "cert_cns": (cert_info or {}).get("cns", ["simulated_cert"]),
            }
            self.rhmi_apps[handle] = {
                "handle": handle,
                "src": src,
                "appId": app_id,
                "name": app_title,
                "vendor": "Lab",
                "initialized": True,
                "auth_badge": badge,
                "xml_sha256": xml_hash,
                **parsed,
            }
            self._log(
                "phone->hu",
                src,
                "rhmi_setResource+rhmi_initialize",
                {"handle": handle, "appId": app_id, "xml_sha256": xml_hash, "badge": badge},
            )
        return {
            "ok": True,
            "accepted": True,
            "auth_mode": mode,
            "auth_badge": badge,
            "handle": handle,
            "xml_sha256": xml_hash,
            "allowed_rhmi_sha256": allowed_hashes,
            "cert": cert_info,
        }

    def rhmi_set_data(self, handle: int, model_id: int, value: Any, *, src: int = 19) -> dict[str, Any]:
        with self._lock:
            app = self.rhmi_apps.get(handle)
            if not app:
                return {"ok": False, "error": f"unknown rhmi handle {handle}"}
            models = app.setdefault("models", {})
            models.setdefault(str(model_id), {"id": model_id, "modelType": "dynamic"})["value"] = value
            mid = self._next_msg_id()
            pkt = build_rhmi_set_data_call(handle, model_id, value, mid)
            bcl = build_synthetic_frame(CMD_DATA, src, DEST_ETCH_DESK, pkt)
            self._log("phone->hu", src, "rhmi_setData", {"handle": handle, "modelId": model_id, "value": value}, bcl)
            ack = encode_etch_packet("_result_rhmi_setData", {"_inReplyTo": mid, "_messageId": self._next_msg_id()})
            ack_bcl = build_synthetic_frame(CMD_DATA, src, DEST_ETCH_DESK, ack)
            self._log("hu->phone", src, "_result_rhmi_setData", {"_inReplyTo": mid}, ack_bcl)
        return {"ok": True, "handle": handle, "modelId": model_id, "tx_bcl_hex": bcl.hex()}

    def rhmi_set_property(self, handle: int, component_id: int, property_id: int, value: Any, *, src: int = 19) -> dict[str, Any]:
        prop_name = RHMI_PROPERTIES.get(property_id, f"PROP_{property_id}")
        with self._lock:
            app = self.rhmi_apps.get(handle)
            if not app:
                return {"ok": False, "error": f"unknown rhmi handle {handle}"}
            comp = app.get("components", {}).get(str(component_id))
            if not comp:
                return {"ok": False, "error": f"unknown componentId {component_id}"}
            comp.setdefault("properties", {})[prop_name] = value
            mid = self._next_msg_id()
            pkt = build_rhmi_set_property_call(handle, component_id, property_id, value, mid)
            bcl = build_synthetic_frame(CMD_DATA, src, DEST_ETCH_DESK, pkt)
            self._log(
                "phone->hu",
                src,
                "rhmi_setProperty",
                {"handle": handle, "componentId": component_id, "property": prop_name, "value": value},
                bcl,
            )
        return {"ok": True, "handle": handle, "componentId": component_id, "property": prop_name, "tx_bcl_hex": bcl.hex()}

    def trigger_idrive_action(self, handle: int, component_id: int, action_id: int, *, args: dict[str, Any] | None = None) -> dict[str, Any]:
        """Simulate user pressing an iDrive button / list row -> emits HU→Phone `rhmi_onActionEvent`."""
        with self._lock:
            app = self.rhmi_apps.get(handle)
            src = int(app.get("src", 19)) if app else 19
            ev_args = dict(args or {1: 0})
            mid = self._next_msg_id()
            pkt = encode_etch_packet(
                "rhmi_onActionEvent",
                {
                    "_messageId": mid,
                    "handle": handle,
                    "ident": app.get("appId", "sim") if app else "sim",
                    "actionId": action_id,
                    "args": ev_args,
                },
            )
            bcl = build_synthetic_frame(CMD_DATA, src, DEST_ETCH_DESK, pkt)
            self.outbound_queue.append(
                {
                    "ts": time.time(),
                    "dir": "hu_to_phone",
                    "src": src,
                    "dest": DEST_ETCH_DESK,
                    "method": "rhmi_onActionEvent",
                    "bcl_hex": bcl.hex(),
                }
            )
            log_ev = self._log(
                "hu->phone",
                src,
                "rhmi_onActionEvent",
                {"handle": handle, "componentId": component_id, "actionId": action_id, "args": ev_args},
                bcl,
            )
            # Demo convenience: button 301 cycles station, button 302 increments RPM slightly
            if handle == 1 and component_id == 301:
                stations = ["Bayern 3 (Live)", "Rock Antenne", "DLF Kultur", "FM 98.5 MHz"]
                cur = str(app["models"]["101"].get("value", ""))
                idx = next((i for i, s in enumerate(stations) if s in cur), -1)
                app["models"]["101"]["value"] = "Sender: " + stations[(idx + 1) % len(stations)]
            elif handle == 1 and component_id == 302:
                rpm = int((self.cds_values.get("engine.RPMSpeed") or {}).get("RPMSpeed", 830))
                self.cds_values["engine.RPMSpeed"] = {"RPMSpeed": 830 if rpm > 2400 else rpm + 350}
                self._sync_demo_list_unlocked()
        return {"ok": True, "bcl_hex": bcl.hex(), "event": log_ev}

    # ------------------------------------------------------------------
    # Decode arbitrary wire hex (BCL frame or raw Etch packet) into the lab
    # ------------------------------------------------------------------

    def ingest_wire_hex(self, hex_str: str, *, direction: str = "wire") -> dict[str, Any]:
        clean = re.sub(r"[^0-9a-fA-F]", "", hex_str or "")
        if len(clean) < 12 or len(clean) % 2 != 0:
            return {"ok": False, "error": "need even hex string >= 6 bytes"}
        raw = bytes.fromhex(clean)
        src = 0
        etch_bytes = raw
        if raw[:4] != ETCH_MAGIC and not (raw[0] == 0x03 and raw[1] == 0x86):
            framer = BclFramer()
            res = framer.feed(raw)
            if res.frames:
                fr = res.frames[0]
                src = fr.src
                etch_bytes = fr.payload
        dec = decode_etch_message(etch_bytes)
        method = dec["method"]
        rf = dec["raw_fields"]
        with self._lock:
            if method == "cds_onPropertyChangedEvent":
                pname = rf.get("propertyName")
                pval = rf.get("propertyValue")
                if isinstance(pname, str) and isinstance(pval, str):
                    try:
                        self.cds_values[pname] = json.loads(pval)
                    except json.JSONDecodeError:
                        self.cds_values[pname] = {"raw": pval}
                    self.cds_updated_at[pname] = time.time()
                    self.cds_source[pname] = "f20_wire"
                    self._sync_demo_list_unlocked()
            elif method == "_result_rhmi_getCapabilities" and isinstance(rf.get("result"), dict):
                for k, v in rf["result"].items():
                    self.capabilities[str(k)] = str(v)
            self._log(direction, src, method, dec["fields"], raw)
        return {"ok": True, "method": method, "type_hash": dec["type_hash"], "fields": dec["fields"]}


bmw_lab = BmwConnectedLab()
