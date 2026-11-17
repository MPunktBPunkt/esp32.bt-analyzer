#!/usr/bin/env python3
"""Apache Etch BinaryTaggedData (v3) codec + BMWRemoting / CDS / PKCS7 helpers.

Implements the exact wire format verified against BMW F20 NBT Evo captures:
  - 8-byte outer header:  DE AD BE EF | u32BE(body_len)
  - Etch v3 struct body:  03 | 86 <u32BE type_hash> | <int nfields> | (86 <u32BE field_hash> <val>)* | 81
  - Hash function:        sdbm with seed 5381 (org.apache.etch.util.Hash)
"""

from __future__ import annotations

import base64
import hashlib
import json
import re
import struct
from dataclasses import dataclass
from typing import Any

ETCH_MAGIC = b"\xde\xad\xbe\xef"
ETCH_VERSION = 0x03

# Apache Etch BinaryTaggedData TypeCodes
TC_NULL = 0x80
TC_NONE = 0x81  # end-of-struct / end-of-array marker
TC_BOOL_FALSE = 0x82
TC_BOOL_TRUE = 0x83
TC_BYTE = 0x84
TC_SHORT = 0x85
TC_INT = 0x86
TC_LONG = 0x87
TC_FLOAT = 0x88
TC_DOUBLE = 0x89
TC_BYTES = 0x8B
TC_ARRAY = 0x91
TC_EMPTY_STRING = 0x92
TC_STRING = 0x93
TC_STRUCT = 0x94
TC_CUSTOM = 0x95
TC_ANY = 0x96


def etch_hash(name: str) -> int:
    """Apache Etch sdbm hash with seed 5381 (unsigned 32-bit)."""
    h = 5381
    for b in name.encode("utf-8"):
        h = (b + (h << 6) + (h << 16) - h) & 0xFFFFFFFF
    return h


# Canonical BMWRemoting method, struct, exception & field names
BMW_METHODS: tuple[str, ...] = (
    "sas_certificate",
    "sas_crl",
    "sas_permission",
    "sas_login",
    "sas_logout",
    "info_getSystemInfo",
    "ver_getVersion",
    "cds_create",
    "cds_getVersion",
    "cds_addPropertyChangedEventHandler",
    "cds_removePropertyChangedEventHandler",
    "cds_getPropertyAsync",
    "cds_setPropertyAsync",
    "cds_setPropertyBinaryAsync",
    "cds_dispose",
    "cds_onPropertyChangedEvent",
    "am_create",
    "am_addAppEventHandler",
    "am_showLoadingHint",
    "am_showLoadedSuccessHint",
    "am_showLoadedFailHint",
    "am_registerApp",
    "am_removeAppEventHandler",
    "am_dispose",
    "am_onAppEvent",
    "rhmi_getCapabilities",
    "rhmi_create",
    "rhmi_create_version",
    "rhmi_initialize",
    "rhmi_dispose",
    "rhmi_getState",
    "rhmi_setState",
    "rhmi_checkResource",
    "rhmi_setResource",
    "rhmi_addActionEventHandler",
    "rhmi_addHmiEventHandler",
    "rhmi_onActionEvent",
    "rhmi_onHmiEvent",
    "rhmi_ackActionEvent",
    "rhmi_removeActionEventHandler",
    "rhmi_removeHmiEventHandler",
    "rhmi_setData",
    "rhmi_setProperty",
    "rhmi_triggerEvent",
    "av_create",
    "av_requestConnection",
    "av_connectionGranted",
    "av_connectionDenied",
    "av_connectionDeactivated",
    "av_closeConnection",
    "av_dispose",
    "av_requestPlayerState",
    "av_playerStateChanged",
    "av_multimediaButtonEvent",
    "map_create",
    "map_dispose",
    "map_initializeImport",
    "map_importData",
    "map_abortImport",
    "map_finalizeImport",
    "map_highlight",
    "map_showOverlay",
    "map_hideOverlay",
    "map_setMode",
    "map_remove",
    "map_onEvent",
)

BMW_STRUCTS_AND_ENUMS: tuple[str, ...] = (
    "RHMIDataTable",
    "RHMIMetaData",
    "RHMIResourceData",
    "RHMIResourceIdentifier",
    "VersionInfo",
    "RHMIResourceType",
    "RHMIVersion",
    "AMEvent",
    "AVConnectionType",
    "AVPlayerState",
    "AVButtonEvent",
    "IllegalArgumentException",
    "IllegalStateException",
    "SecurityException",
    "ServiceException",
)

BMW_FIELDS: tuple[str, ...] = (
    "_messageId",
    "_inReplyTo",
    "result",
    "e",
    "data",
    "handle",
    "ident",
    "propertyName",
    "propertyValue",
    "propertyBinaryValue",
    "intervalLimit",
    "deviceId",
    "bluetoothAddress",
    "appId",
    "values",
    "event",
    "component",
    "token",
    "metaData",
    "rhmiVersion",
    "state",
    "hash",
    "size",
    "name",
    "type",
    "actionId",
    "componentId",
    "eventId",
    "args",
    "confirmId",
    "success",
    "modelId",
    "value",
    "propertyId",
    "instanceID",
    "id",
    "connectionType",
    "playerState",
    "major",
    "minor",
    "errorCode",
    "detailMessage",
    "category",
    "appName",
    "revision",
    "vendor",
    "version",
    "virtualTableEnable",
    "fromRow",
    "numRows",
    "totalRows",
    "fromColumn",
    "numColumns",
    "totalColumns",
    "errorId",
    "errorMsg",
    "keysAndValues",
    "msg",
)

ETCH_BUILTINS: tuple[str, ...] = (
    "_Etch_Map",
    "_Etch_List",
    "_Etch_Set",
    "_Etch_Datetime",
    "_Etch_AuthException",
    "_Etch_RuntimeException",
    "_Etch_SerializeException",
    "_exception",
)

# Exact CDS catalog (ident -> propertyName) verified 1:1 against IDriveConnectKit CDSProperty.kt
CDS_CATALOG: dict[int, str] = {
    1: "climate.ACCompressor",
    3: "climate.ACMode",
    4: "climate.ACSystemTemperatures",
    8: "climate.seatHeatDriver",
    9: "climate.seatHeatPassenger",
    13: "controls.cruiseControl",
    16: "controls.headlights",
    18: "controls.lights",
    20: "controls.startStopStatus",
    22: "controls.turnSignal",
    28: "driving.acceleration",
    29: "driving.acceleratorPedal",
    30: "driving.averageConsumption",
    31: "driving.averageSpeed",
    32: "driving.brakeContact",
    35: "driving.DSCActive",
    37: "driving.gear",
    38: "driving.keyPosition",
    39: "driving.odometer",
    40: "driving.parkingBrake",
    42: "driving.speedActual",
    43: "driving.speedDisplayed",
    44: "driving.steeringWheel",
    45: "driving.mode",
    46: "engine.consumption",
    47: "engine.info",
    50: "engine.RPMSpeed",
    51: "engine.status",
    52: "engine.temperature",
    53: "engine.torque",
    54: "entertainment.multimedia",
    55: "entertainment.radioFrequency",
    56: "entertainment.radioStation",
    57: "navigation.currentPositionDetailedInfo",
    61: "navigation.GPSExtendedInfo",
    62: "navigation.GPSPosition",
    63: "navigation.guidanceStatus",
    68: "sensors.battery",
    70: "sensors.doors",
    71: "sensors.fuel",
    76: "sensors.seatOccupiedPassenger",
    78: "sensors.temperatureExterior",
    79: "sensors.temperatureInterior",
    81: "sensors.trunk",
    82: "vehicle.country",
    83: "vehicle.language",
    84: "vehicle.type",
    86: "vehicle.units",
    87: "vehicle.VIN",
    93: "sensors.SOCBatteryHybrid",
    94: "sensors.batteryTemp",
    95: "hmi.iDrive",
    104: "sensors.lid",
    105: "sensors.seatOccupiedDriver",
    109: "vehicle.time",
    620: "entertainment.descriptionCurrentSource",
    621: "entertainment.statusAvailableSources",
    636: "entertainment.md.coverArt",
    637: "entertainment.md.statusCurrentSource",
    638: "entertainment.md.mediabrowsing",
    639: "entertainment.md.statusPlayback",
    640: "entertainment.md.controlPlayback",
    641: "entertainment.md.statusMetaInfo",
    642: "entertainment.md.playList",
}

CDS_BY_NAME: dict[str, int] = {v: k for k, v in CDS_CATALOG.items()}

# RHMIProperty IDs from IDriveConnectKit RHMIProperty.kt
RHMI_PROPERTIES: dict[int, str] = {
    1: "ENABLED",
    2: "SELECTABLE",
    3: "VISIBLE",
    4: "VALID",
    5: "TOOLBARHMISTATE_PAGING",
    6: "LIST_COLUMNWIDTH",
    7: "LIST_HASIDCOLUMN",
    8: "LABEL_WAITINGANIMATION",
    9: "WIDTH",
    10: "HEIGHT",
    17: "ALIGNMENT",
    18: "OFFSET_X",
    19: "OFFSET_Y",
    20: "POSITION_X",
    21: "POSITION_Y",
    22: "BOOKMARKABLE",
    23: "SPEAKABLE",
    24: "HMISTATE_TABLETYPE",
    25: "CURSOR_WIDTH",
    26: "HMISTATE_TABLELAYOUT",
    35: "TOOLBARHMISTATE_PAGING_LIMITED",
    36: "SPEEDLOCK",
    37: "CUTTYPE",
    53: "CHECKED",
    55: "UUID",
    56: "MODAL",
}

RHMI_RESOURCE_TYPES: dict[int, str] = {
    0: "DESCRIPTION",
    1: "TEXTDB",
    2: "IMAGEDB",
    3: "TEXTID",
    4: "IMAGEID",
    5: "PREINSTTEXTID",
    6: "PREINSTIMAGEID",
    7: "IMAGEDATA",
    8: "IBADB",
    9: "FLOATDATA",
    10: "WIDGETDB",
    11: "ASSETDB",
}


BMW_ENUM_MEMBERS: tuple[str, ...] = (
    "AM_APP_START",
    "AV_CONNECTION_TYPE_ENTERTAINMENT",
    "AV_CONNECTION_TYPE_INTERRUPT",
    "AV_CONNECTION_TYPE_FINGERPRINT",
    "AV_PLAYERSTATE_PLAY",
    "AV_PLAYERSTATE_PAUSE",
    "AV_PLAYERSTATE_STOP",
    "DESCRIPTION",
    "TEXTDB",
    "IMAGEDB",
    "TEXTID",
    "IMAGEID",
    "PREINSTTEXTID",
    "PREINSTIMAGEID",
    "IMAGEDATA",
    "IBADB",
    "FLOATDATA",
    "WIDGETDB",
    "ASSETDB",
    "RHMI_VERSION_ID5",
    "RHMI_VERSION_ID6_LIGHT",
    "RHMI_VERSION_ID6",
)


def build_hash_registry() -> dict[int, str]:
    reg: dict[int, str] = {}
    for m in BMW_METHODS:
        reg[etch_hash(f"de.bmw.idrive.BMWRemoting.{m}")] = m
        reg[etch_hash(f"de.bmw.idrive.BMWRemoting._result_{m}")] = f"_result_{m}"
    for s in BMW_STRUCTS_AND_ENUMS:
        reg[etch_hash(f"de.bmw.idrive.BMWRemoting.{s}")] = s
        reg[etch_hash(f"de.bmw.idrive.{s}")] = s
    for em in BMW_ENUM_MEMBERS:
        reg[etch_hash(em)] = em
    for f in BMW_FIELDS:
        reg[etch_hash(f)] = f
    for b in ETCH_BUILTINS:
        reg[etch_hash(b)] = b
    return reg


HASH_REGISTRY: dict[int, str] = build_hash_registry()

H_MAP = etch_hash("_Etch_Map")
H_LIST = etch_hash("_Etch_List")
H_KEYS_AND_VALUES = etch_hash("keysAndValues")
H_VALUES = etch_hash("values")
H_MSG_ID = etch_hash("_messageId")
H_IN_REPLY_TO = etch_hash("_inReplyTo")
H_RESULT = etch_hash("result")


def fqn_hash(short_or_fqn: str) -> int:
    if "." in short_or_fqn or short_or_fqn.startswith("_Etch_"):
        return etch_hash(short_or_fqn)
    return etch_hash(f"de.bmw.idrive.BMWRemoting.{short_or_fqn}")


# ---------------------------------------------------------------------------
# Encoder
# ---------------------------------------------------------------------------


def encode_int_value(n: int, *, force_i64: bool = False) -> bytes:
    if force_i64 or n < -2147483648 or n > 2147483647:
        return b"\x87" + struct.pack(">q", n)
    if 0 <= n <= 31:
        return bytes([n])
    if -32 <= n <= -1:
        return bytes([n & 0xFF])
    if -128 <= n <= 127:
        return b"\x84" + struct.pack(">b", n)
    if -32768 <= n <= 32767:
        return b"\x85" + struct.pack(">h", n)
    return b"\x86" + struct.pack(">i", n)


def encode_value(val: Any) -> bytes:
    if val is None:
        return bytes([TC_NULL])
    if isinstance(val, bool):
        return bytes([TC_BOOL_TRUE if val else TC_BOOL_FALSE])
    if isinstance(val, int):
        return encode_int_value(val)
    if isinstance(val, float):
        return b"\x89" + struct.pack(">d", val)
    if isinstance(val, (bytes, bytearray)):
        b = bytes(val)
        return bytes([TC_BYTES]) + encode_int_value(len(b)) + b
    if isinstance(val, str):
        if val == "":
            return bytes([TC_EMPTY_STRING])
        b = val.encode("utf-8")
        return bytes([TC_STRING]) + encode_int_value(len(b)) + b
    if isinstance(val, dict):
        # Encode as _Etch_Map custom value (wire-verified against F20 _result_rhmi_getCapabilities)
        flat: list[Any] = []
        for k, v in val.items():
            flat.append(k)
            flat.append(v)
        arr = (
            bytes([TC_ARRAY, TC_ANY, 0x01])
            + encode_int_value(len(flat))
            + b"".join(encode_value(x) for x in flat)
            + bytes([TC_NONE])
        )
        return (
            bytes([TC_CUSTOM, TC_INT])
            + struct.pack(">I", H_MAP)
            + encode_int_value(1)
            + bytes([TC_INT])
            + struct.pack(">I", H_KEYS_AND_VALUES)
            + arr
            + bytes([TC_NONE])
        )
    if isinstance(val, (list, tuple)):
        # 2D table (e.g. RHMIDataTable object[][]) vs 1D array
        if val and all(isinstance(row, (list, tuple)) for row in val):
            sub = b"".join(
                bytes([TC_ARRAY, TC_ANY, 0x01])
                + encode_int_value(len(row))
                + b"".join(encode_value(cell) for cell in row)
                + bytes([TC_NONE])
                for row in val
            )
            return bytes([TC_ARRAY, TC_ANY, 0x02]) + encode_int_value(len(val)) + sub + bytes([TC_NONE])
        return (
            bytes([TC_ARRAY, TC_ANY, 0x01])
            + encode_int_value(len(val))
            + b"".join(encode_value(x) for x in val)
            + bytes([TC_NONE])
        )
    if isinstance(val, EtchStruct):
        # Exceptions / custom BMW types nest as TC_CUSTOM (0x95) on F20 wire
        # (field: ServiceException in _result_rhmi_setData), not TC_STRUCT (0x94).
        short = val.type_name.rsplit(".", 1)[-1]
        as_custom = short.endswith("Exception") or short.startswith("RHMI")
        return encode_struct(
            val.type_name, val.fields, nested=True, custom=as_custom
        )
    raise TypeError(f"Unsupported Etch value type: {type(val)!r}")


@dataclass
class EtchStruct:
    type_name: str
    fields: dict[str, Any]
    type_hash: int = 0

    def __post_init__(self) -> None:
        if not self.type_hash:
            self.type_hash = fqn_hash(self.type_name)


def encode_struct(
    type_name: str,
    fields: dict[str, Any],
    *,
    nested: bool = False,
    custom: bool = False,
) -> bytes:
    th = fqn_hash(type_name)
    out = bytearray()
    if nested:
        out.append(TC_CUSTOM if custom else TC_STRUCT)
    else:
        out.append(ETCH_VERSION)
    out.append(TC_INT)
    out.extend(struct.pack(">I", th))
    out.extend(encode_int_value(len(fields)))
    for fname, fval in fields.items():
        fh = etch_hash(fname)
        out.append(TC_INT)
        out.extend(struct.pack(">I", fh))
        if fname in ("_messageId", "_inReplyTo") and isinstance(fval, int):
            out.extend(encode_int_value(fval, force_i64=True))
        else:
            out.extend(encode_value(fval))
    out.append(TC_NONE)
    return bytes(out)


def encode_etch_enum(enum_type: str, member_name: str) -> bytes:
    """Encode a BMWRemoting enum value as Apache Etch TC_CUSTOM struct."""
    th = fqn_hash(enum_type)
    mh = etch_hash(member_name)
    return (
        bytes([TC_CUSTOM, TC_INT])
        + struct.pack(">I", th)
        + encode_int_value(1)
        + bytes([TC_INT])
        + struct.pack(">I", mh)
        + bytes([TC_BOOL_TRUE, TC_NONE])
    )


def encode_etch_packet(type_name: str, fields: dict[str, Any]) -> bytes:
    body = encode_struct(type_name, fields, nested=False)
    return ETCH_MAGIC + struct.pack(">I", len(body)) + body


# ---------------------------------------------------------------------------
# Decoder
# ---------------------------------------------------------------------------


class _Reader:
    def __init__(self, buf: bytes, pos: int = 0) -> None:
        self.buf = buf
        self.pos = pos

    def rem(self) -> int:
        return len(self.buf) - self.pos

    def u8(self) -> int:
        if self.pos >= len(self.buf):
            raise EOFError("unexpected EOF in Etch stream")
        b = self.buf[self.pos]
        self.pos += 1
        return b

    def take(self, n: int) -> bytes:
        if n < 0 or self.pos + n > len(self.buf):
            raise EOFError(f"need {n} bytes, have {self.rem()}")
        out = self.buf[self.pos : self.pos + n]
        self.pos += n
        return out

    def read_int(self) -> int:
        tag = self.u8()
        if tag <= 0x7F:
            return tag
        if 0xC0 <= tag <= 0xFF:
            return tag - 256
        if tag == TC_BYTE:
            return struct.unpack(">b", self.take(1))[0]
        if tag == TC_SHORT:
            return struct.unpack(">h", self.take(2))[0]
        if tag == TC_INT:
            return struct.unpack(">i", self.take(4))[0]
        if tag == TC_LONG:
            return struct.unpack(">q", self.take(8))[0]
        raise ValueError(f"expected int tag, got 0x{tag:02x} at {self.pos - 1}")

    def read_type_or_field_id(self) -> int:
        tag = self.u8()
        if tag == TC_INT:
            return struct.unpack(">I", self.take(4))[0]
        if tag <= 0x7F:
            return tag
        raise ValueError(f"expected id tag 0x86, got 0x{tag:02x}")

    def read_value(self) -> Any:
        tag = self.u8()
        if tag <= 0x7F:
            return tag
        if 0xC0 <= tag <= 0xFF:
            return tag - 256
        if tag == TC_NULL:
            return None
        if tag == TC_NONE:
            return _SENTINEL_NONE
        if tag == TC_BOOL_FALSE:
            return False
        if tag == TC_BOOL_TRUE:
            return True
        if tag == TC_BYTE:
            return struct.unpack(">b", self.take(1))[0]
        if tag == TC_SHORT:
            return struct.unpack(">h", self.take(2))[0]
        if tag == TC_INT:
            return struct.unpack(">i", self.take(4))[0]
        if tag == TC_LONG:
            return struct.unpack(">q", self.take(8))[0]
        if tag == TC_FLOAT:
            return struct.unpack(">f", self.take(4))[0]
        if tag == TC_DOUBLE:
            return struct.unpack(">d", self.take(8))[0]
        if tag == TC_EMPTY_STRING:
            return ""
        if tag == TC_BYTES:
            ln = self.read_int()
            return self.take(ln)
        if tag == TC_STRING:
            ln = self.read_int()
            return self.take(ln).decode("utf-8", errors="replace")
        if tag in (TC_STRUCT, TC_CUSTOM):
            return self.read_struct_body(is_custom=(tag == TC_CUSTOM))
        if tag == TC_ARRAY:
            elem_tc = self.u8()
            if elem_tc in (TC_STRUCT, TC_CUSTOM):
                _ = self.read_type_or_field_id()
            dim = self.read_int()
            length = self.read_int()
            items: list[Any] = []
            for _ in range(max(0, length)):
                if self.rem() > 0 and self.buf[self.pos] == TC_NONE:
                    break
                if elem_tc == TC_BYTE and dim == 1:
                    # Sometimes encoded as untagged or tagged; check peek
                    items.append(self.read_value())
                else:
                    v = self.read_value()
                    if v is _SENTINEL_NONE:
                        break
                    items.append(v)
            if self.rem() > 0 and self.buf[self.pos] == TC_NONE:
                self.pos += 1
            return items
        raise ValueError(f"unknown Etch tag 0x{tag:02x} at pos {self.pos - 1}")

    def read_struct_body(self, *, is_custom: bool = False) -> Any:
        th = self.read_type_or_field_id()
        tname = HASH_REGISTRY.get(th, f"0x{th:08x}")
        _nfields = self.read_int()
        fields: dict[str, Any] = {}
        while self.rem() > 0:
            if self.buf[self.pos] == TC_NONE:
                self.pos += 1
                break
            fh = self.read_type_or_field_id()
            fname = HASH_REGISTRY.get(fh, f"0x{fh:08x}")
            val = self.read_value()
            if val is _SENTINEL_NONE:
                break
            fields[fname] = val
        if is_custom and th == H_MAP:
            kv = fields.get("keysAndValues") or []
            out_map: dict[Any, Any] = {}
            for i in range(0, len(kv) - 1, 2):
                k = kv[i]
                if not isinstance(k, (str, int, float, bool)) and k is not None:
                    k = str(k)
                out_map[k] = kv[i + 1]
            return out_map
        if is_custom and th == H_LIST:
            return list(fields.get("values") or [])
        return EtchStruct(type_name=tname, fields=fields, type_hash=th)


class _Sentinel:
    pass


_SENTINEL_NONE = _Sentinel()


def decode_etch_message(data: bytes) -> dict[str, Any]:
    """Decode one `deadbeef|len|body` or raw `03 86 ...` Etch v3 message into a JSON-friendly dict."""
    body = data[8:] if len(data) >= 8 and data[:4] == ETCH_MAGIC else data
    if len(body) < 6 or body[0] != ETCH_VERSION:
        raise ValueError("not an Etch v3 BinaryTaggedData message")
    r = _Reader(body, 1)
    st: EtchStruct = r.read_struct_body(is_custom=False)
    return {
        "method": st.type_name,
        "type_hash": f"0x{st.type_hash:08x}",
        "fields": _json_safe(st.fields),
        "raw_fields": st.fields,
        "bytes_consumed": r.pos,
        "total_body_bytes": len(body),
    }


def _json_safe(obj: Any) -> Any:
    if isinstance(obj, (bytes, bytearray)):
        if len(obj) <= 48:
            return {"_bytes_hex": bytes(obj).hex(), "len": len(obj)}
        return {"_bytes_hex_head": bytes(obj[:32]).hex(), "len": len(obj)}
    if isinstance(obj, EtchStruct):
        return {"_struct": obj.type_name, **{k: _json_safe(v) for k, v in obj.fields.items()}}
    if isinstance(obj, dict):
        return {str(k): _json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_json_safe(x) for x in obj]
    return obj


# ---------------------------------------------------------------------------
# PKCS7 certificate & SHA-256 whitelist inspector
# ---------------------------------------------------------------------------

_DIGEST_KV_RE = re.compile(r"([A-Za-z0-9_.*]+)=([^&\x00-\x1f]+)")


def inspect_pkcs7_bundle(p7b_pem_or_der: bytes) -> dict[str, Any]:
    """Extract CNs, SAS.CertificateType (APP vs APP_AUTH) and SHA-256 resource whitelist from a BMW .p7b."""
    if b"-----BEGIN" in p7b_pem_or_der:
        b64 = b"".join(
            line.strip()
            for line in p7b_pem_or_der.splitlines()
            if line.strip() and not line.strip().startswith(b"-----")
        )
        der = base64.b64decode(b64)
    else:
        der = bytes(p7b_pem_or_der)

    cns = sorted({m.group(1).decode("ascii") for m in re.finditer(rb"(a4a_[A-Za-z0-9_.-]+)", der)})
    permissions: list[dict[str, str]] = []
    rhmi_digests: set[str] = set()
    image_digests: set[str] = set()
    text_digests: set[str] = set()
    cert_types: set[str] = set()

    for m in re.finditer(rb"[ -~]{20,}", der):
        s = m.group(0).decode("ascii", errors="ignore")
        if "SAS.CertificateType=" not in s and "CDS=" not in s:
            continue
        kv = {k: v for k, v in _DIGEST_KV_RE.findall(s)}
        if not kv:
            continue
        permissions.append(kv)
        ct = kv.get("SAS.CertificateType")
        if ct:
            cert_types.add(ct)
        for key, target in (
            ("SAS.Digests.RHMIDescriptions", rhmi_digests),
            ("SAS.Digests.ImageDatabases", image_digests),
            ("SAS.Digests.TextDatabases", text_digests),
        ):
            raw_d = kv.get(key, "")
            for tok in raw_d.split(","):
                tok = tok.strip().lower()
                # Strip trailing ASN.1 printable tail char if glued (65 chars -> 64 hex)
                if len(tok) == 65 and all(c in "0123456789abcdef" for c in tok[:64]):
                    tok = tok[:64]
                if len(tok) == 64 and all(c in "0123456789abcdef" for c in tok) and set(tok) != {"0"}:
                    target.add(tok)

    return {
        "der_bytes": len(der),
        "cns": cns,
        "cert_types": sorted(cert_types),
        "uses_app_auth_xor": "APP_AUTH" in cert_types,
        "rhmi_description_sha256": sorted(rhmi_digests),
        "image_db_sha256": sorted(image_digests),
        "text_db_sha256": sorted(text_digests),
        "permissions": permissions,
    }


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().lower()


# ---------------------------------------------------------------------------
# High-level BMWRemoting RPC builders (for active CDS queries & F20 simulator)
# ---------------------------------------------------------------------------


def build_cds_create_call(msg_id: int) -> bytes:
    return encode_etch_packet("cds_create", {"_messageId": msg_id})


def build_cds_add_handler_call(handle: int, prop_name: str, interval_ms: int, msg_id: int) -> bytes:
    ident = str(CDS_BY_NAME.get(prop_name, prop_name))
    return encode_etch_packet(
        "cds_addPropertyChangedEventHandler",
        {
            "_messageId": msg_id,
            "handle": handle,
            "ident": ident,
            "propertyName": prop_name,
            "intervalLimit": interval_ms,
        },
    )


def build_cds_get_property_call(handle: int, prop_name: str, msg_id: int) -> bytes:
    ident = str(CDS_BY_NAME.get(prop_name, prop_name))
    return encode_etch_packet(
        "cds_getPropertyAsync",
        {
            "_messageId": msg_id,
            "handle": handle,
            "ident": ident,
            "propertyName": prop_name,
        },
    )


def build_cds_event(handle: int, prop_name: str, value_obj: Any, msg_id: int) -> bytes:
    ident = str(CDS_BY_NAME.get(prop_name, "0"))
    val_str = value_obj if isinstance(value_obj, str) else json.dumps(value_obj, separators=(",", ":"))
    return encode_etch_packet(
        "cds_onPropertyChangedEvent",
        {
            "_messageId": msg_id,
            "handle": handle,
            "ident": ident,
            "propertyName": prop_name,
            "propertyValue": val_str,
        },
    )


def build_rhmi_set_data_call(handle: int, model_id: int, value: Any, msg_id: int) -> bytes:
    return encode_etch_packet(
        "rhmi_setData",
        {"_messageId": msg_id, "handle": handle, "modelId": model_id, "value": value},
    )


def build_rhmi_set_property_call(
    handle: int, component_id: int, property_id: int, value: Any, msg_id: int
) -> bytes:
    return encode_etch_packet(
        "rhmi_setProperty",
        {
            "_messageId": msg_id,
            "handle": handle,
            "componentId": component_id,
            "propertyId": property_id,
            "values": {0: value},
        },
    )
