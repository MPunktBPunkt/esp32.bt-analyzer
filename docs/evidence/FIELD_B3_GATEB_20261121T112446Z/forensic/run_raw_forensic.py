#!/usr/bin/env python3
"""Byte-accurate forensic analysis of FIELD_B3_GATEB raw bins.

Read-only on raw/*.bin. Writes artifacts under forensic/ and
RAW_FORENSIC_ANALYSIS.md one level up.
"""
from __future__ import annotations

import hashlib
import json
import re
import struct
import sys
import tempfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[4]  # bt-analyzer
EV = Path(__file__).resolve().parents[1]
OUT = Path(__file__).resolve().parent
RAW_P = EV / "raw" / "phone_to_hu.bin"
RAW_H = EV / "raw" / "hu_to_phone.bin"
REPORT = EV / "RAW_FORENSIC_ANALYSIS.md"

sys.path.insert(0, str(ROOT / "tools"))
from etch_codec import (  # noqa: E402
    HASH_REGISTRY,
    SAS_APP_AUTH_PAD_U32,
    decode_etch_message,
    inspect_pkcs7_bundle,
    sas_challenge_transform,
    summarize_sas_wire_fields,
)
from sas_pad_crosscheck import verify_session  # noqa: E402

CMD = {
    1: "OPEN",
    2: "DATA",
    3: "CLOSE",
    4: "HANDSHAKE",
    5: "SELECTPROTO",
    6: "DATAACK",
    7: "ACK",
    8: "KNOCK",
    9: "LAUNCH",
    10: "HANGUP",
    11: "BROADCAST",
    12: "REGISTER",
}
INIT_MAGIC = bytes.fromhex("12345678")
ETCH_MAGIC = b"\xde\xad\xbe\xef"
KNOCK_UUID = b"0e9b90c4-cbe1-4742-8283-d367e9a56619"


def sha256(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def md5(b: bytes) -> str:
    return hashlib.md5(b).hexdigest()


def sha1(b: bytes) -> str:
    return hashlib.sha1(b).hexdigest()


def hexdump(b: bytes, width: int = 16, limit: int = 64) -> str:
    lines = []
    view = b[:limit]
    for i in range(0, len(view), width):
        chunk = view[i : i + width]
        hx = " ".join(f"{x:02x}" for x in chunk)
        asc = "".join(chr(x) if 32 <= x < 127 else "." for x in chunk)
        lines.append(f"  {i:04x}  {hx:<{width*3}}  {asc}")
    if len(b) > limit:
        lines.append(f"  ... ({len(b)} bytes total)")
    return "\n".join(lines)


def ascii_preview(b: bytes, n: int = 80) -> str:
    return "".join(chr(x) if 32 <= x < 127 else "." for x in b[:n])


def parse_bcl_stream(data: bytes, direction: str) -> tuple[list[dict], list[dict], dict]:
    """Parse BCL with Etch-fragment awareness and sliding resync on desync.

    Returns (frames, gaps, coverage).
    """
    frames: list[dict] = []
    gaps: list[dict] = []
    i = 0
    session = 0
    etch_need = 0  # remaining etch wire bytes still expected in DATA payloads
    etch_buf = bytearray()
    etch_start_off = None
    etch_meta: dict[str, Any] = {}

    def finish_etch():
        nonlocal etch_need, etch_buf, etch_start_off, etch_meta
        if etch_buf and etch_start_off is not None:
            frames.append(
                {
                    "kind": "ETCH_REASSEMBLED",
                    "direction": direction,
                    "session": session,
                    "off": etch_start_off,
                    "raw_len": len(etch_buf),
                    "payload": bytes(etch_buf),
                    **etch_meta,
                }
            )
        etch_need = 0
        etch_buf = bytearray()
        etch_start_off = None
        etch_meta = {}

    def try_start_etch(off: int, pl: bytes, bcl_idx: int, src: int, dest: int):
        nonlocal etch_need, etch_buf, etch_start_off, etch_meta
        if len(pl) >= 8 and pl[:4] == ETCH_MAGIC:
            elen = struct.unpack_from(">I", pl, 4)[0]
            total = 8 + elen
            etch_buf = bytearray(pl)
            etch_start_off = off
            etch_need = max(0, total - len(pl))
            etch_meta = {
                "etch_elen": elen,
                "etch_total": total,
                "bcl_src": src,
                "bcl_dest": dest,
                "bcl_first_idx": bcl_idx,
                "fragmented": etch_need > 0,
            }
            if etch_need == 0:
                finish_etch()
            return True
        return False

    def consume_etch_continuation(pl: bytes):
        nonlocal etch_need
        if etch_need <= 0:
            return False
        take = min(len(pl), etch_need)
        etch_buf.extend(pl[:take])
        etch_need -= take
        if etch_need == 0:
            finish_etch()
            return True
        return True

    coverage = {
        "file_len": len(data),
        "bcl_bytes": 0,
        "init_bytes": 0,
        "gap_bytes": 0,
        "preamble_bytes": 0,
        "raw_etch_continuation_bytes": 0,
        "unparsed_tail": 0,
    }

    # Preamble before first INIT (phone: 56-B knock envelope)
    first_init = data.find(INIT_MAGIC)
    if first_init > 0:
        gaps.append(
            {
                "kind": "PREAMBLE",
                "off": 0,
                "len": first_init,
                "note": "bytes before first INIT",
                "payload": data[:first_init],
            }
        )
        coverage["preamble_bytes"] = first_init
        i = first_init

    while i + 4 <= len(data):
        if data[i : i + 4] == INIT_MAGIC:
            if etch_need > 0:
                # incomplete etch abandoned at session boundary
                gaps.append(
                    {
                        "kind": "INCOMPLETE_ETCH",
                        "off": etch_start_off,
                        "len": len(etch_buf),
                        "remain": etch_need,
                        "note": "etch incomplete at INIT boundary",
                    }
                )
                finish_etch()
            session += 1
            frames.append(
                {
                    "kind": "INIT",
                    "direction": direction,
                    "session": session,
                    "off": i,
                    "raw_len": 4,
                }
            )
            coverage["init_bytes"] += 4
            i += 4
            continue

        if i + 8 > len(data):
            break

        cmd, src, dest, ln = struct.unpack_from(">HHHH", data, i)
        if 1 <= cmd <= 12 and ln <= 65535 and i + 8 + ln <= len(data):
            pl = data[i + 8 : i + 8 + ln]
            bcl_idx = len(frames)
            rec = {
                "kind": "BCL",
                "direction": direction,
                "session": session,
                "off": i,
                "cmd": cmd,
                "cmd_name": CMD[cmd],
                "src": src,
                "dest": dest,
                "len": ln,
                "payload": pl,
                "raw_len": 8 + ln,
                "idx": bcl_idx,
            }
            frames.append(rec)
            coverage["bcl_bytes"] += 8 + ln

            if cmd == 2:
                if etch_need > 0:
                    # continuation fragment (may or may not start with deadbeef)
                    if pl[:4] == ETCH_MAGIC and len(pl) >= 8:
                        # nested new etch while previous incomplete — close gap
                        gaps.append(
                            {
                                "kind": "ETCH_TRUNCATED",
                                "off": etch_start_off,
                                "have": len(etch_buf),
                                "remain": etch_need,
                            }
                        )
                        finish_etch()
                        try_start_etch(i + 8, pl, bcl_idx, src, dest)
                    else:
                        consume_etch_continuation(pl)
                else:
                    try_start_etch(i + 8, pl, bcl_idx, src, dest)
            i += 8 + ln
            continue

        # Desync
        desync_off = i
        if etch_need > 0:
            # Try raw continuation of remaining etch bytes (capture quirk)
            take = min(etch_need, len(data) - i)
            # Only accept if after take we can resync to BCL or INIT
            candidate = i + take
            ok = False
            if candidate + 4 <= len(data) and data[candidate : candidate + 4] == INIT_MAGIC:
                ok = True
            elif candidate + 8 <= len(data):
                c, s, d, L = struct.unpack_from(">HHHH", data, candidate)
                if 1 <= c <= 12 and L <= 8000 and candidate + 8 + L <= len(data):
                    ok = True
            if ok:
                etch_buf.extend(data[i : i + take])
                frames.append(
                    {
                        "kind": "ETCH_RAW_CONTINUATION",
                        "direction": direction,
                        "session": session,
                        "off": i,
                        "raw_len": take,
                        "payload": data[i : i + take],
                        "note": "etch remainder without BCL header (capture/desync)",
                    }
                )
                coverage["raw_etch_continuation_bytes"] += take
                etch_need = 0
                finish_etch()
                i = candidate
                continue

        # Sliding-window resync: find next INIT or plausible BCL DATA with deadbeef
        best = None
        search_end = min(len(data), i + 20000)
        j = data.find(INIT_MAGIC, i)
        if j >= 0 and j < search_end:
            best = ("INIT", j)
        for k in range(i, search_end - 8):
            c, s, d, L = struct.unpack_from(">HHHH", data, k)
            if c == 2 and d in (4004, 5001) and 4 <= L <= 8000 and k + 8 + L <= len(data):
                pl = data[k + 8 : k + 12]
                if pl == ETCH_MAGIC or d == 5001:
                    # verify forward parse lasts a bit
                    t = k
                    good = 0
                    while t + 8 <= len(data) and good < 3:
                        if data[t : t + 4] == INIT_MAGIC:
                            break
                        cc, ss, dd, LL = struct.unpack_from(">HHHH", data, t)
                        if not (1 <= cc <= 12 and LL <= 8000 and t + 8 + LL <= len(data)):
                            break
                        t += 8 + LL
                        good += 1
                    if good >= 2:
                        best = ("BCL", k)
                        break
        if best is None:
            # abandon to end or next INIT anywhere
            j = data.find(INIT_MAGIC, i)
            if j < 0:
                gaps.append(
                    {
                        "kind": "UNPARSED_TAIL",
                        "off": i,
                        "len": len(data) - i,
                        "payload": data[i:],
                    }
                )
                coverage["unparsed_tail"] = len(data) - i
                coverage["gap_bytes"] += len(data) - i
                break
            best = ("INIT", j)

        gap_len = best[1] - i
        # If we had open etch, dump partial into gap note and try to attach media
        gap_payload = data[i : best[1]]
        gaps.append(
            {
                "kind": "DESYNC_GAP",
                "off": desync_off,
                "len": gap_len,
                "resync": best[0],
                "resync_off": best[1],
                "etch_remain_at_desync": etch_need,
                "payload": gap_payload,
                "cmd_attempt": (cmd, src, dest, ln),
            }
        )
        coverage["gap_bytes"] += gap_len
        if etch_need > 0:
            # keep partial etch as incomplete artifact
            frames.append(
                {
                    "kind": "ETCH_PARTIAL",
                    "direction": direction,
                    "session": session,
                    "off": etch_start_off,
                    "raw_len": len(etch_buf),
                    "payload": bytes(etch_buf),
                    "remain": etch_need,
                    **etch_meta,
                }
            )
            etch_need = 0
            etch_buf = bytearray()
            etch_start_off = None
            etch_meta = {}
        i = best[1]

    covered = (
        coverage["bcl_bytes"]
        + coverage["init_bytes"]
        + coverage["preamble_bytes"]
        + coverage["raw_etch_continuation_bytes"]
    )
    # gaps counted separately; overlap careful
    coverage["decoded_protocol_bytes"] = covered
    coverage["known_gap_bytes"] = coverage["gap_bytes"]
    coverage["coverage_pct"] = 100.0 * (len(data) - coverage["unparsed_tail"]) / max(1, len(data))
    return frames, gaps, coverage


def decode_etch_safe(payload: bytes) -> dict[str, Any] | None:
    try:
        return decode_etch_message(payload)
    except Exception as e:  # noqa: BLE001
        return {"decode_error": str(e)}


def extract_der_certs_from_blob(blob: bytes) -> list[bytes]:
    """Find X.509 DER certificates (SEQUENCE with tls cert-ish)."""
    certs = []
    # PEM
    for m in re.finditer(
        rb"-----BEGIN CERTIFICATE-----(.*?)-----END CERTIFICATE-----",
        blob,
        re.S,
    ):
        import base64

        b64 = re.sub(rb"\s+", b"", m.group(1))
        try:
            certs.append(base64.b64decode(b64))
        except Exception:  # noqa: BLE001
            pass
    # DER: scan for 30 82 xx xx
    i = 0
    while i + 4 < len(blob):
        if blob[i] == 0x30 and blob[i + 1] == 0x82:
            ln = struct.unpack_from(">H", blob, i + 2)[0]
            end = i + 4 + ln
            if 64 <= ln <= 8192 and end <= len(blob):
                # crude: look for rsa oid or common patterns
                der = blob[i:end]
                if b"\x06\x09\x2a\x86\x48\x86\xf7\x0d\x01\x01" in der or b"BMW" in der or b"a4a_" in der:
                    certs.append(der)
                    i = end
                    continue
            i += 1
        else:
            i += 1
    # unique by sha256
    seen = set()
    out = []
    for c in certs:
        h = sha256(c)
        if h not in seen:
            seen.add(h)
            out.append(c)
    return out


def openssl_x509_meta(der: bytes) -> dict[str, Any]:
    import subprocess

    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "c.der"
        p.write_bytes(der)
        r = subprocess.run(
            [
                "openssl",
                "x509",
                "-inform",
                "DER",
                "-in",
                str(p),
                "-noout",
                "-subject",
                "-issuer",
                "-serial",
                "-dates",
                "-fingerprint",
                "-sha256",
                "-fingerprint",
                "-sha1",
                "-text",
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if r.returncode != 0:
            return {"error": r.stderr.strip()}
        text = r.stdout
        meta: dict[str, Any] = {"openssl_text_head": "\n".join(text.splitlines()[:40])}
        for line in text.splitlines():
            if line.startswith("subject="):
                meta["subject"] = line[len("subject=") :]
            elif line.startswith("issuer="):
                meta["issuer"] = line[len("issuer=") :]
            elif line.startswith("serial="):
                meta["serial"] = line[len("serial=") :]
            elif "SHA256 Fingerprint=" in line:
                meta["sha256_fingerprint"] = line.split("=", 1)[1].strip()
            elif "SHA1 Fingerprint=" in line:
                meta["sha1_fingerprint"] = line.split("=", 1)[1].strip()
            elif "Public-Key:" in line:
                meta["public_key"] = line.strip()
            elif "Exponent:" in line:
                meta["exponent"] = line.strip()
        meta["sha256_der"] = sha256(der)
        meta["sha1_der"] = sha1(der)
        meta["len"] = len(der)
        return meta


def find_strings(data: bytes, min_len: int = 6) -> list[tuple[int, str, str]]:
    """Return (offset, encoding, string)."""
    out = []
    for m in re.finditer(rb"[\x20-\x7e]{" + str(min_len).encode() + rb",}", data):
        out.append((m.start(), "ASCII", m.group().decode("ascii")))
    # UTF-16LE
    i = 0
    while i + min_len * 2 <= len(data):
        if data[i] >= 32 and data[i] < 127 and data[i + 1] == 0:
            j = i
            chars = []
            while j + 1 < len(data) and data[j + 1] == 0 and 32 <= data[j] < 127:
                chars.append(chr(data[j]))
                j += 2
            if len(chars) >= min_len:
                out.append((i, "UTF-16LE", "".join(chars)))
                i = j
                continue
        i += 1
    return out


def classify_payload(pl: bytes) -> dict[str, Any]:
    info: dict[str, Any] = {"len": len(pl)}
    if not pl:
        info["class"] = "empty"
        return info
    if pl[:4] == ETCH_MAGIC:
        info["class"] = "etch_envelope"
        if len(pl) >= 8:
            info["etch_elen"] = struct.unpack_from(">I", pl, 4)[0]
        return info
    if pl[:3] == b"\xff\xd8\xff":
        info["class"] = "jpeg"
        return info
    if pl[:4] == b"\x89PNG":
        info["class"] = "png"
        return info
    if pl[:2] == b"\x1f\x8b":
        info["class"] = "gzip"
        return info
    if pl[:4] == b"PK\x03\x04":
        info["class"] = "zip"
        return info
    if pl[:4] == b"RIFF":
        info["class"] = "riff"
        return info
    if b"-----BEGIN" in pl[:64]:
        info["class"] = "pem"
        return info
    if pl[:1] == b"\x30" and pl[1:2] in (b"\x82", b"\x81"):
        info["class"] = "asn1_sequence"
        return info
    if pl[:4] == b"\x13\x37\x13\x37":
        info["class"] = "watchdog_13371337"
        return info
    # mostly printable?
    pr = sum(1 for x in pl if 32 <= x < 127 or x in (9, 10, 13))
    if len(pl) > 0 and pr / len(pl) > 0.85:
        info["class"] = "textish"
        info["preview"] = ascii_preview(pl, 120)
        return info
    info["class"] = "binary"
    info["entropy_hint"] = round(len(set(pl)) / max(1, min(256, len(pl))), 3)
    return info


def extract_images(blob: bytes, base_off: int, direction: str, out_dir: Path) -> list[dict]:
    found = []
    for magic, ext, end_magic in (
        (b"\xff\xd8\xff", "jpg", b"\xff\xd9"),
        (b"\x89PNG\r\n\x1a\n", "png", b"IEND\xaeB`\x82"),
    ):
        start = 0
        while True:
            j = blob.find(magic, start)
            if j < 0:
                break
            if ext == "jpg":
                k = blob.find(end_magic, j + 3)
                if k < 0:
                    start = j + 3
                    continue
                end = k + 2
            else:
                k = blob.find(end_magic, j + 8)
                if k < 0:
                    start = j + 8
                    continue
                end = k + len(end_magic)
            img = blob[j:end]
            if len(img) < 100:
                start = j + 1
                continue
            h = sha256(img)[:16]
            name = f"{direction}_{base_off + j:08x}_{len(img)}_{h}.{ext}"
            path = out_dir / name
            path.write_bytes(img)
            found.append(
                {
                    "path": str(path.relative_to(EV)),
                    "offset": base_off + j,
                    "len": len(img),
                    "sha256": sha256(img),
                    "format": ext,
                    "direction": direction,
                }
            )
            start = end
    return found


def main() -> None:
    (OUT / "SAS_SIGNATURES").mkdir(exist_ok=True)
    (OUT / "EXTRACTED_MEDIA").mkdir(exist_ok=True)

    p2h = RAW_P.read_bytes()
    h2p = RAW_H.read_bytes()

    integrity = {
        "phone_to_hu": {
            "path": str(RAW_P.relative_to(EV)),
            "size": len(p2h),
            "sha256": sha256(p2h),
            "md5": md5(p2h),
            "sha1": sha1(p2h),
            "offset0_hex": p2h[:32].hex(),
            "end_hex": p2h[-32:].hex(),
            "end_offset": len(p2h) - 1,
        },
        "hu_to_phone": {
            "path": str(RAW_H.relative_to(EV)),
            "size": len(h2p),
            "sha256": sha256(h2p),
            "md5": md5(h2p),
            "sha1": sha1(h2p),
            "offset0_hex": h2p[:32].hex(),
            "end_hex": h2p[-32:].hex(),
            "end_offset": len(h2p) - 1,
        },
    }

    fr_p, gaps_p, cov_p = parse_bcl_stream(p2h, "phone_to_hu")
    fr_h, gaps_h, cov_h = parse_bcl_stream(h2p, "hu_to_phone")

    # Decode all reassembled etch + single-frame etch from BCL DATA
    etch_msgs: list[dict] = []
    method_counts: Counter = Counter()
    unknown_type_hashes: Counter = Counter()
    sas_events: list[dict] = []
    rhmi_events: list[dict] = []
    am_events: list[dict] = []
    cds_events: list[dict] = []
    av_events: list[dict] = []
    unknown_frames: list[dict] = []
    images: list[dict] = []

    def handle_etch(payload: bytes, meta: dict):
        dec = decode_etch_safe(payload)
        if not dec or "decode_error" in dec:
            unknown_frames.append({**meta, "payload_len": len(payload), "decode": dec})
            return
        method = dec.get("method") or ""
        short = method.rsplit(".", 1)[-1] if method else "UNKNOWN"
        method_counts[short] += 1
        if method.startswith("0x"):
            unknown_type_hashes[method] += 1
        fields = dec.get("raw_fields") or {}
        rec = {
            **meta,
            "method": short,
            "method_fqn": method,
            "type_hash": dec.get("type_hash"),
            "fields_json": dec.get("fields"),
            "message_id": fields.get("_messageId"),
            "in_reply_to": fields.get("_inReplyTo"),
            "payload_len": len(payload),
            "payload_sha256": sha256(payload),
        }
        # SAS summarize
        if short.startswith("sas_") or short.startswith("_result_sas"):
            sas = summarize_sas_wire_fields(short, fields)
            rec["sas"] = {k: v for k, v in sas.items() if k != "login_sig_hex"}
            if "login_sig_hex" in sas:
                sig = bytes.fromhex(sas["login_sig_hex"])
                sig_path = OUT / "SAS_SIGNATURES" / f"sig_{meta.get('off', 0):08x}_{len(sig)}.bin"
                sig_path.write_bytes(sig)
                rec["sas"]["sig_file"] = str(sig_path.relative_to(EV))
                rec["sas"]["login_sig_sha256"] = sha256(sig)
                rec["sas"]["login_sig_len"] = len(sig)
            if short == "sas_certificate":
                data = fields.get("data")
                if isinstance(data, (bytes, bytearray)):
                    blob = bytes(data)
                    cert_path = OUT / "SAS_CERTIFICATE.p7b"
                    # keep first / longest
                    if not cert_path.exists() or len(blob) >= cert_path.stat().st_size:
                        cert_path.write_bytes(blob)
                    rec["sas"]["cert_blob_sha256"] = sha256(blob)
                    rec["sas"]["cert_blob_len"] = len(blob)
                    try:
                        rec["sas"]["pkcs7"] = inspect_pkcs7_bundle(blob)
                    except Exception as e:  # noqa: BLE001
                        rec["sas"]["pkcs7_error"] = str(e)
                    ders = extract_der_certs_from_blob(blob)
                    der_metas = []
                    for n, der in enumerate(ders):
                        der_file = OUT / f"SAS_CERT_{n}.der"
                        der_file.write_bytes(der)
                        der_metas.append({"file": str(der_file.relative_to(EV)), **openssl_x509_meta(der)})
                    rec["sas"]["der_certs"] = der_metas
            sas_events.append(rec)
        elif short.startswith("rhmi_") or short.startswith("_result_rhmi"):
            # pull interesting fields
            for k in ("handle", "id", "modelId", "propertyId", "resourceId", "actionId", "eventId", "stateId", "data", "value"):
                if k in fields:
                    v = fields[k]
                    if isinstance(v, (bytes, bytearray)):
                        rec[k] = {"len": len(v), "sha256": sha256(bytes(v)), "head": bytes(v)[:32].hex()}
                        if short == "rhmi_setData":
                            imgs = extract_images(bytes(v), meta.get("off", 0), meta["direction"], OUT / "EXTRACTED_MEDIA")
                            if imgs:
                                rec["embedded_images"] = imgs
                                images.extend(imgs)
                    else:
                        rec[k] = v
            rhmi_events.append(rec)
        elif short.startswith("am_") or short.startswith("_result_am"):
            for k in ("handle", "appId", "packageName", "category", "weight", "name", "appName"):
                if k in fields:
                    rec[k] = fields[k]
            am_events.append(rec)
        elif short.startswith("cds_") or short.startswith("_result_cds"):
            for k in ("handle", "propertyName", "ident", "value", "propertyValue"):
                if k in fields:
                    v = fields[k]
                    if isinstance(v, (bytes, bytearray)):
                        rec[k] = {"len": len(v), "preview": ascii_preview(bytes(v), 200)}
                    else:
                        rec[k] = v
            cds_events.append(rec)
        elif short.startswith("av_") or short.startswith("_result_av"):
            av_events.append(rec)
        else:
            if method.startswith("0x"):
                unknown_frames.append(rec)
            etch_msgs.append(rec)

        etch_msgs.append(rec)

        # images inside full etch payload
        imgs = extract_images(payload, meta.get("off", 0), meta["direction"], OUT / "EXTRACTED_MEDIA")
        for im in imgs:
            im["containing_method"] = short
            images.append(im)

    # Process frames
    for fr in fr_p + fr_h:
        if fr["kind"] in ("ETCH_REASSEMBLED", "ETCH_PARTIAL"):
            handle_etch(
                fr["payload"],
                {
                    "direction": fr["direction"],
                    "session": fr.get("session"),
                    "off": fr["off"],
                    "kind": fr["kind"],
                    "fragmented": fr.get("fragmented"),
                    "bcl_src": fr.get("bcl_src"),
                    "bcl_dest": fr.get("bcl_dest"),
                },
            )
        elif fr["kind"] == "BCL" and fr["cmd"] == 2:
            pl = fr["payload"]
            # Only decode if complete single-frame etch (not continuation)
            if pl[:4] == ETCH_MAGIC and len(pl) >= 8:
                elen = struct.unpack_from(">I", pl, 4)[0]
                if 8 + elen == len(pl):
                    handle_etch(
                        pl,
                        {
                            "direction": fr["direction"],
                            "session": fr.get("session"),
                            "off": fr["off"] + 8,
                            "kind": "ETCH_INLINE",
                            "bcl_src": fr["src"],
                            "bcl_dest": fr["dest"],
                            "bcl_off": fr["off"],
                        },
                    )
            elif pl == b"\x13\x37\x13\x37":
                pass  # watchdog
            elif fr["src"] == 5001:
                pass
            else:
                # non-etch DATA — classify
                cl = classify_payload(pl)
                if cl.get("class") not in ("etch_envelope", "empty", "watchdog_13371337"):
                    # likely fragment already counted in reassembly; skip if mid-etch head
                    if pl[:4] != ETCH_MAGIC and not pl[:3] == b"\xff\xd8\xff":
                        pass

    # Also scan gaps for media/strings
    gap_media = []
    for g in gaps_p + gaps_h:
        pl = g.get("payload") or b""
        if not pl:
            continue
        imgs = extract_images(pl, g["off"], "gap", OUT / "EXTRACTED_MEDIA")
        gap_media.extend(imgs)
        images.extend(imgs)

    # Dedup images by sha256
    uniq_img = {}
    for im in images:
        uniq_img[im["sha256"]] = im
    images = list(uniq_img.values())

    # --- Crypto verify all challenge/login pairs ---
    cert_blob = None
    cert_file = OUT / "SAS_CERTIFICATE.p7b"
    if cert_file.exists():
        cert_blob = cert_file.read_bytes()
    # Also search raw for PEM/PKCS7 if missing
    if cert_blob is None:
        for fr in fr_p:
            if fr["kind"] in ("ETCH_REASSEMBLED", "ETCH_PARTIAL", "BCL"):
                pl = fr.get("payload") or b""
                if b"-----BEGIN" in pl or b"PKCS" in pl or b"a4a_" in pl:
                    try:
                        dec = decode_etch_safe(pl if pl[:4] == ETCH_MAGIC else (ETCH_MAGIC + struct.pack(">I", len(pl)) + pl))
                    except Exception:
                        dec = None
                    if dec and dec.get("method", "").endswith("sas_certificate"):
                        data = (dec.get("raw_fields") or {}).get("data")
                        if isinstance(data, (bytes, bytearray)):
                            cert_blob = bytes(data)
                            cert_file.write_bytes(cert_blob)
                            break
        # brute: find largest PEM in phone raw
        if cert_blob is None:
            m = re.search(rb"-----BEGIN [^-]+-----.*?-----END [^-]+-----", p2h, re.S)
            if m:
                # may be inside etch; store surrounding via sas events later
                pass

    challenges = []
    logins = []
    for e in sas_events:
        s = e.get("sas") or {}
        if e["method"] == "_result_sas_certificate" and s.get("challenge_hex"):
            challenges.append(e)
        if e["method"] == "sas_login" and s.get("login_sig_len"):
            logins.append(e)
        if e["method"] == "sas_certificate" and cert_blob is None and s.get("cert_blob_sha256"):
            # already written
            if cert_file.exists():
                cert_blob = cert_file.read_bytes()

    # Pair by inReplyTo / sequence within session
    crypto_results = []
    if cert_blob:
        # For each login, find preceding challenge in same session / direction flow
        for login in logins:
            sig_file = EV / login["sas"]["sig_file"]
            sig = sig_file.read_bytes()
            # find challenge: previous _result_sas_certificate before this login (by offset / session)
            chal_e = None
            for c in challenges:
                if c["direction"] == "hu_to_phone" and c.get("session") == login.get("session"):
                    # prefer challenge whose message is replied by login.in_reply_to? login replies to challenge msg
                    # login._messageId; challenge has message_id; login may not include inReplyTo to challenge
                    if c["off"] < login.get("off", 10**12) or login["direction"] == "phone_to_hu":
                        # hu challenge offset vs phone login offset not comparable across files
                        chal_e = c
            # Better pairing: use inReplyTo on challenge pointing to cert msg_id, and login after challenge
            # Collect all challenges; pair index-wise per session
        # Session-wise pairing
        by_sess = defaultdict(lambda: {"chal": [], "login": [], "cert": []})
        for e in sas_events:
            by_sess[e.get("session")][e["method"].replace("_result_", "R_")].append(e) if False else None
        sess_map: dict[Any, dict] = defaultdict(lambda: {"challenges": [], "logins": [], "certs": []})
        for e in sas_events:
            sm = sess_map[e.get("session")]
            if e["method"] == "_result_sas_certificate":
                sm["challenges"].append(e)
            elif e["method"] == "sas_login":
                sm["logins"].append(e)
            elif e["method"] == "sas_certificate":
                sm["certs"].append(e)

        for sess, sm in sess_map.items():
            chals = sm["challenges"]
            logs = sm["logins"]
            # pair by order
            for idx, login in enumerate(logs):
                chal = chals[idx] if idx < len(chals) else (chals[-1] if chals else None)
                if not chal:
                    crypto_results.append(
                        {
                            "session": sess,
                            "login_off": login["off"],
                            "verdict": "UNABLE",
                            "reason": "no challenge in session",
                        }
                    )
                    continue
                chal_hex = chal["sas"]["challenge_hex"]
                sig = (EV / login["sas"]["sig_file"]).read_bytes()
                vr = verify_session(cert_blob, bytes.fromhex(chal_hex), sig, SAS_APP_AUTH_PAD_U32)
                crypto_results.append(
                    {
                        "session": sess,
                        "challenge_off": chal["off"],
                        "challenge_hex": chal_hex,
                        "login_off": login["off"],
                        "sig_len": len(sig),
                        "sig_sha256": sha256(sig),
                        **{k: vr[k] for k in vr if k not in ("signer",)},
                        "signer": vr.get("signer"),
                    }
                )
    else:
        crypto_results.append({"verdict": "UNABLE", "reason": "no certificate blob extracted from raw"})

    # --- Strings catalog (interesting keywords) ---
    keywords = [
        "BMW",
        "AAIdrive",
        "MyBMW",
        "Spotify",
        "music",
        "media",
        "RHMI",
        "SAS",
        "AUTH",
        "certificate",
        "RSA",
        "Connected",
        "BCL",
        "Etch",
        "CDS",
        "Halestorm",
        "Prevail",
        "androidautoidrive",
        "iva_",
        "APP_AUTH",
        "TouchCommand",
        "a4a_",
    ]
    string_hits = []
    for direction, blob in (("phone_to_hu", p2h), ("hu_to_phone", h2p)):
        for kw in keywords:
            for m in re.finditer(re.escape(kw).encode(), blob, re.I):
                off = m.start()
                ctx = blob[max(0, off - 20) : off + len(m.group()) + 40]
                string_hits.append(
                    {
                        "direction": direction,
                        "offset": off,
                        "keyword": kw,
                        "match": m.group().decode("ascii", "replace"),
                        "context": ascii_preview(ctx, 80),
                    }
                )

    # Extra notable ASCII from phone (tracks etc.)
    notable_phone = []
    for m in re.finditer(
        rb"(Halestorm|I Prevail|Spotify|Zufallswiedergabe[^\x00]{0,40}|can u see me[^\x00]{0,40}|Pink Floyd|androidautoidrive[^\x00]{0,60})",
        p2h,
    ):
        notable_phone.append({"off": m.start(), "text": m.group().decode("utf-8", "replace")[:80]})

    # --- Cross-corr b3.jsonl ---
    b3_methods = Counter()
    b3_sas = []
    b3_etch_count = 0
    b3_decode_errors = 0
    b3_path = EV / "b3.jsonl"
    with b3_path.open() as f:
        for line in f:
            o = json.loads(line)
            t = o.get("type") or o.get("event")
            if t == "etch":
                b3_etch_count += 1
                m = o.get("method") or ""
                short = m.rsplit(".", 1)[-1]
                b3_methods[short] += 1
                if "sas" in short:
                    b3_sas.append(
                        {
                            "method": short,
                            "challenge_hex": (o.get("etch") or {}).get("sas", {}).get("challenge_hex")
                            if isinstance(o.get("etch"), dict)
                            else o.get("challenge_hex"),
                            "ts": o.get("ts") or o.get("t"),
                        }
                    )
                    # richer
                    sas = None
                    if isinstance(o.get("etch"), dict):
                        sas = o["etch"].get("sas")
                    if sas and sas.get("challenge_hex"):
                        b3_sas[-1]["challenge_hex"] = sas["challenge_hex"]
                    if sas and sas.get("login_sig_sha256"):
                        b3_sas[-1]["login_sig_sha256"] = sas["login_sig_sha256"]
            elif t == "etch_decode_error":
                b3_decode_errors += 1

    # --- libaudio cross search ---
    libaudio = ROOT / "docs" / "libaudio.so"
    lib_hits = {}
    if libaudio.exists():
        la = libaudio.read_bytes()
        needles = {}
        if crypto_results:
            for cr in crypto_results:
                if cr.get("challenge_hex"):
                    needles[f"challenge_{cr['challenge_hex'][:8]}"] = bytes.fromhex(cr["challenge_hex"])
                if cr.get("sig_sha256"):
                    pass
        needles["pad_u32_be"] = struct.pack(">I", 0x02000000)
        needles["APP_AUTH"] = b"APP_AUTH"
        needles["CertificateType"] = b"CertificateType"
        needles["createSecurityContext"] = b"createSecurityContext"
        needles["sas_certificate"] = b"sas_certificate"
        needles["sas_login"] = b"sas_login"
        needles["signChallenge"] = b"signChallenge"
        needles["EVP_SignFinal"] = b"EVP_SignFinal"
        needles["EVP_PKEY_sign"] = b"EVP_PKEY_sign"
        # cert fingerprint ascii?
        for e in sas_events:
            if e["method"] == "sas_certificate":
                for d in (e.get("sas") or {}).get("der_certs") or []:
                    if d.get("sha256_der"):
                        needles["cert_sha256_bin"] = bytes.fromhex(d["sha256_der"])
        for name, nd in needles.items():
            pos = la.find(nd)
            lib_hits[name] = {"found": pos >= 0, "offset": pos if pos >= 0 else None, "len": len(nd)}

        # RSA modulus from first DER if any
        der0 = OUT / "SAS_CERT_0.der"
        if der0.exists():
            # extract modulus via openssl
            import subprocess

            r = subprocess.run(
                ["openssl", "x509", "-inform", "DER", "-in", str(der0), "-modulus", "-noout"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if r.returncode == 0 and "Modulus=" in r.stdout:
                mod_hex = r.stdout.strip().split("=", 1)[1].lower()
                # search first 32 bytes of modulus
                mod = bytes.fromhex(mod_hex)
                pos = la.find(mod[:32])
                lib_hits["rsa_modulus_head32"] = {
                    "found": pos >= 0,
                    "offset": pos if pos >= 0 else None,
                    "modulus_sha256": sha256(mod),
                    "modulus_len": len(mod),
                }
                (OUT / "SAS_RSA_MODULUS.hex").write_text(mod_hex + "\n")

    # --- BCL tables ---
    def bcl_table(frames):
        rows = []
        for f in frames:
            if f["kind"] != "BCL":
                continue
            rows.append(
                {
                    "off": f["off"],
                    "cmd": f["cmd_name"],
                    "src": f["src"],
                    "dest": f["dest"],
                    "len": f["len"],
                    "session": f.get("session"),
                    "head": f["payload"][:16].hex() if f["payload"] else "",
                    "class": classify_payload(f["payload"]).get("class"),
                }
            )
        return rows

    bcl_p = bcl_table(fr_p)
    bcl_h = bcl_table(fr_h)

    # --- Write RAW_FRAME_INDEX.jsonl ---
    with (OUT / "RAW_FRAME_INDEX.jsonl").open("w") as fh:
        for f in fr_p + fr_h:
            rec = {
                "direction": f.get("direction"),
                "session": f.get("session"),
                "kind": f["kind"],
                "off": f.get("off"),
                "raw_len": f.get("raw_len"),
            }
            if f["kind"] == "BCL":
                rec.update(
                    {
                        "cmd": f["cmd_name"],
                        "src": f["src"],
                        "dest": f["dest"],
                        "payload_len": f["len"],
                        "payload_sha256": sha256(f["payload"]) if f["payload"] else None,
                        "payload_head_hex": f["payload"][:32].hex() if f["payload"] else "",
                    }
                )
            elif f["kind"] in ("ETCH_REASSEMBLED", "ETCH_PARTIAL"):
                rec.update(
                    {
                        "etch_elen": f.get("etch_elen"),
                        "fragmented": f.get("fragmented"),
                        "payload_sha256": sha256(f["payload"]),
                        "bcl_src": f.get("bcl_src"),
                        "bcl_dest": f.get("bcl_dest"),
                    }
                )
            fh.write(json.dumps(rec) + "\n")

    # SAS_REASSEMBLY.json
    sas_reassembly = {
        "cert_present": cert_blob is not None,
        "cert_sha256": sha256(cert_blob) if cert_blob else None,
        "cert_len": len(cert_blob) if cert_blob else None,
        "sas_events": [
            {
                "method": e["method"],
                "direction": e["direction"],
                "session": e.get("session"),
                "off": e["off"],
                "message_id": e.get("message_id"),
                "in_reply_to": e.get("in_reply_to"),
                "sas": e.get("sas"),
            }
            for e in sas_events
        ],
        "crypto_results": crypto_results,
    }
    (OUT / "SAS_REASSEMBLY.json").write_text(json.dumps(sas_reassembly, indent=2, default=str))

    # UNKNOWN_FRAMES.md
    unk_lines = ["# Unknown / undecoded frames\n"]
    for u in unknown_frames[:200]:
        unk_lines.append(
            f"- {u.get('direction')} off=0x{u.get('off', 0):08x} method={u.get('method')} "
            f"type_hash={u.get('type_hash')} len={u.get('payload_len')} decode={u.get('decode')}\n"
        )
    unk_lines.append(f"\nTotal unknown_frames entries: {len(unknown_frames)}\n")
    unk_lines.append(f"Unknown type hashes: {dict(unknown_type_hashes)}\n")
    unk_lines.append("\n## Desync gaps\n")
    for g in gaps_p + gaps_h:
        unk_lines.append(
            f"- {g.get('kind')} off=0x{g['off']:08x} len={g.get('len')} note={g.get('note') or g.get('resync')}\n"
        )
    (OUT / "UNKNOWN_FRAMES.md").write_text("".join(unk_lines))

    # Summary stats artifact
    summary = {
        "integrity": integrity,
        "coverage_phone": cov_p,
        "coverage_hu": cov_h,
        "frame_counts": {
            "phone": Counter(f["kind"] for f in fr_p),
            "hu": Counter(f["kind"] for f in fr_h),
        },
        "bcl_cmd_phone": Counter(f["cmd_name"] for f in fr_p if f["kind"] == "BCL"),
        "bcl_cmd_hu": Counter(f["cmd_name"] for f in fr_h if f["kind"] == "BCL"),
        "etch_methods": dict(method_counts),
        "sas_event_count": len(sas_events),
        "rhmi_count": len(rhmi_events),
        "am_count": len(am_events),
        "cds_count": len(cds_events),
        "av_count": len(av_events),
        "images": len(images),
        "crypto_results": crypto_results,
        "lib_hits": lib_hits,
        "b3_etch_count": b3_etch_count,
        "b3_decode_errors": b3_decode_errors,
        "b3_methods": dict(b3_methods),
        "gaps_phone": [{k: v for k, v in g.items() if k != "payload"} for g in gaps_p],
        "gaps_hu": [{k: v for k, v in g.items() if k != "payload"} for g in gaps_h],
        "notable_phone": notable_phone[:40],
        "string_hit_counts": Counter(s["keyword"] for s in string_hits),
    }
    # convert Counters
    summary["frame_counts"]["phone"] = dict(summary["frame_counts"]["phone"])
    summary["frame_counts"]["hu"] = dict(summary["frame_counts"]["hu"])
    summary["bcl_cmd_phone"] = dict(summary["bcl_cmd_phone"])
    summary["bcl_cmd_hu"] = dict(summary["bcl_cmd_hu"])
    summary["string_hit_counts"] = dict(summary["string_hit_counts"])
    (OUT / "ANALYSIS_SUMMARY.json").write_text(json.dumps(summary, indent=2, default=str))

    # Image list
    (OUT / "EXTRACTED_MEDIA" / "INDEX.json").write_text(json.dumps(images, indent=2))

    # Lightweight event lists for report generation
    def slim(events, keys):
        out = []
        for e in events:
            out.append({k: e.get(k) for k in keys if k in e})
        return out

    (OUT / "RHMI_EVENTS.json").write_text(
        json.dumps(slim(rhmi_events, ["direction", "session", "off", "method", "handle", "id", "message_id", "type_hash", "embedded_images"]), indent=2, default=str)
    )
    (OUT / "AM_EVENTS.json").write_text(
        json.dumps(am_events, indent=2, default=str)
    )
    (OUT / "CDS_EVENTS.json").write_text(
        json.dumps(slim(cds_events, ["direction", "session", "off", "method", "handle", "propertyName", "ident", "value", "message_id"]), indent=2, default=str)
    )
    (OUT / "AV_EVENTS.json").write_text(json.dumps(av_events, indent=2, default=str))
    (OUT / "STRING_HITS.json").write_text(json.dumps(string_hits[:500], indent=2))

    # Chronology: merge by... we don't have shared clock; use per-direction sequence + session markers
    chrono = []
    for f in fr_p:
        if f["kind"] == "INIT":
            chrono.append({"seq": len(chrono), "dir": "phone_to_hu", "off": f["off"], "what": f"INIT session={f['session']}"})
        elif f["kind"] == "BCL" and f["cmd"] != 2:
            chrono.append(
                {
                    "seq": len(chrono),
                    "dir": "phone_to_hu",
                    "off": f["off"],
                    "what": f"{f['cmd_name']} src={f['src']} dest={f['dest']} len={f['len']}",
                }
            )
    for e in etch_msgs:
        if e.get("direction") == "phone_to_hu":
            chrono.append(
                {
                    "seq": len(chrono),
                    "dir": "phone_to_hu",
                    "off": e["off"],
                    "what": f"ETCH {e['method']} mid={e.get('message_id')}",
                }
            )
    # Actually better chronology: all BCL+etch in file order per direction, then note correlation via b3
    chrono_p = []
    for f in fr_p:
        if f["kind"] == "INIT":
            chrono_p.append({"off": f["off"], "ev": "INIT", "session": f["session"]})
        elif f["kind"] == "BCL":
            entry = {
                "off": f["off"],
                "ev": f["cmd_name"],
                "src": f["src"],
                "dest": f["dest"],
                "len": f["len"],
            }
            chrono_p.append(entry)
        elif f["kind"] in ("ETCH_REASSEMBLED", "ETCH_PARTIAL"):
            chrono_p.append({"off": f["off"], "ev": f["kind"], "len": f["raw_len"]})
    chrono_h = []
    for f in fr_h:
        if f["kind"] == "BCL":
            chrono_h.append(
                {
                    "off": f["off"],
                    "ev": f["cmd_name"],
                    "src": f["src"],
                    "dest": f["dest"],
                    "len": f["len"],
                }
            )
        elif f["kind"] in ("ETCH_REASSEMBLED", "ETCH_PARTIAL"):
            chrono_h.append({"off": f["off"], "ev": f["kind"], "len": f["raw_len"]})

    (OUT / "CHRONO_PHONE.json").write_text(json.dumps(chrono_p, indent=2))
    (OUT / "CHRONO_HU.json").write_text(json.dumps(chrono_h, indent=2))

    # Etch method timeline (decoded)
    etch_tl = [
        {
            "direction": e["direction"],
            "session": e.get("session"),
            "off": e["off"],
            "method": e["method"],
            "message_id": e.get("message_id"),
            "in_reply_to": e.get("in_reply_to"),
        }
        for e in etch_msgs
    ]
    # dedupe identical off+method
    seen = set()
    etch_tl_u = []
    for e in etch_tl:
        k = (e["direction"], e["off"], e["method"])
        if k in seen:
            continue
        seen.add(k)
        etch_tl_u.append(e)
    (OUT / "ETCH_TIMELINE.json").write_text(json.dumps(etch_tl_u, indent=2))

    print("DONE")
    print("phone frames", len(fr_p), "hu", len(fr_h))
    print("methods", method_counts.most_common(30))
    print("sas", len(sas_events), "rhmi", len(rhmi_events), "am", len(am_events), "cds", len(cds_events), "av", len(av_events))
    print("images", len(images))
    print("crypto", json.dumps(crypto_results, indent=2, default=str)[:2000])
    print("coverage p", cov_p)
    print("coverage h", cov_h)
    print("cert", cert_blob is not None, "len", len(cert_blob) if cert_blob else 0)


if __name__ == "__main__":
    main()
