#!/usr/bin/env python3
"""Observe-only SAS pad + RSA-VERIFY cross-check (CASE A Test A).

No private keys. Pipeline:

  pad16  = MD5(serial_u32_be)          # APP_AUTH wire: 0x02000000
  xored  = challenge XOR pad16
  digest = MD5(xored)
  RSA_VERIFY(sig, DigestInfo-MD5||digest, wire X509 public key)

Usage:
  PYTHONPATH=tools python3 tools/sas_pad_crosscheck.py \\
    --serial-u32 0x02000000 --challenge-hex fc20… --sig-hex 37d2… \\
    --cert-pem path/to/touchcommand.pem

  # Reassemble + verify from raw HU/B3 BCL jsonl (rx/tx hex frames):
  PYTHONPATH=tools python3 tools/sas_pad_crosscheck.py --from-bcl-jsonl /tmp/hu.jsonl

  # Pad-only (legacy):
  PYTHONPATH=tools python3 tools/sas_pad_crosscheck.py \\
    --serial-u32 0x02000000 --challenge-hex fc20…
"""

from __future__ import annotations

import argparse
import json
import re
import struct
import subprocess
import sys
import tempfile
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from bcl_framer import BclFramer  # noqa: E402
from etch_codec import (  # noqa: E402
    SAS_APP_AUTH_PAD_U32,
    decode_etch_message,
    sas_challenge_transform,
)

CMD_DATA = 2
ETCH_MAGIC = b"\xde\xad\xbe\xef"
# DigestInfo for MD5 (RFC 8017 / PKCS#1 v1.5)
DIGESTINFO_MD5 = bytes.fromhex("3020300c06082a864886f70d020505000410")


def _openssl(*args: str, input_bytes: bytes | None = None) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        ["openssl", *args],
        input=input_bytes,
        capture_output=True,
        check=False,
    )


def pkcs7_x509_pems(cert_blob: bytes) -> list[str]:
    if b"BEGIN" in cert_blob:
        pem = cert_blob
    else:
        import base64

        pem = (
            b"-----BEGIN PKCS7-----\n"
            + base64.encodebytes(cert_blob)
            + b"-----END PKCS7-----\n"
        )
    with tempfile.NamedTemporaryFile(suffix=".p7b.pem", delete=False) as tf:
        tf.write(pem)
        path = tf.name
    try:
        r = _openssl("pkcs7", "-in", path, "-print_certs")
    finally:
        Path(path).unlink(missing_ok=True)
    if r.returncode != 0:
        return []
    text = r.stdout.decode("ascii", errors="ignore")
    return re.findall(
        r"-----BEGIN CERTIFICATE-----.*?-----END CERTIFICATE-----", text, re.S
    )


def cert_subject_serial(pem: str) -> str:
    with tempfile.NamedTemporaryFile("w", suffix=".pem", delete=False) as tf:
        tf.write(pem + "\n")
        path = tf.name
    try:
        r = _openssl("x509", "-in", path, "-noout", "-subject", "-serial")
        return r.stdout.decode().strip().replace("\n", " | ")
    finally:
        Path(path).unlink(missing_ok=True)


def rsa_verifyrecover(pem: str, sig: bytes) -> bytes | None:
    with tempfile.TemporaryDirectory() as td:
        c = Path(td) / "c.pem"
        s = Path(td) / "sig.bin"
        p = Path(td) / "pub.pem"
        c.write_text(pem + "\n")
        s.write_bytes(sig)
        if _openssl("x509", "-in", str(c), "-pubkey", "-noout").returncode != 0:
            return None
        pub = _openssl("x509", "-in", str(c), "-pubkey", "-noout")
        p.write_bytes(pub.stdout)
        r = _openssl("pkeyutl", "-verifyrecover", "-pubin", "-inkey", str(p), "-in", str(s))
        return r.stdout if r.returncode == 0 else None


def rsa_verify_digestinfo_md5(pem: str, digest16: bytes, sig: bytes) -> bool:
    with tempfile.TemporaryDirectory() as td:
        c = Path(td) / "c.pem"
        s = Path(td) / "sig.bin"
        d = Path(td) / "di.bin"
        p = Path(td) / "pub.pem"
        c.write_text(pem + "\n")
        s.write_bytes(sig)
        d.write_bytes(DIGESTINFO_MD5 + digest16)
        pub = _openssl("x509", "-in", str(c), "-pubkey", "-noout")
        if pub.returncode != 0:
            return False
        p.write_bytes(pub.stdout)
        r = _openssl(
            "pkeyutl",
            "-verify",
            "-pubin",
            "-inkey",
            str(p),
            "-sigfile",
            str(s),
            "-in",
            str(d),
        )
        return r.returncode == 0


def verify_session(
    cert_blob: bytes,
    challenge: bytes,
    sig: bytes,
    pad_u32: int = SAS_APP_AUTH_PAD_U32,
) -> dict:
    tr = sas_challenge_transform(challenge, pad_u32)
    digest = bytes.fromhex(tr["digest_md5_hex"])
    pems = pkcs7_x509_pems(cert_blob)
    signer_pem = None
    recovered = None
    for pem in pems:
        rec = rsa_verifyrecover(pem, sig)
        if rec is not None:
            signer_pem = pem
            recovered = rec
            break
    out: dict = {
        **tr,
        "pad_u32_hex": f"0x{pad_u32:08x}",
        "challenge_hex": challenge.hex(),
        "sig_len": len(sig),
        "cert_count": len(pems),
        "signer": cert_subject_serial(signer_pem) if signer_pem else None,
        "rsa_recover_ok": recovered is not None,
        "rsa_verify_ok": False,
        "digest_match": False,
        "pkcs1": None,
    }
    if recovered is None or signer_pem is None:
        out["verdict"] = "INVALID_NO_SIGNER"
        return out
    if recovered.startswith(DIGESTINFO_MD5) and len(recovered) == len(DIGESTINFO_MD5) + 16:
        out["pkcs1"] = "PKCS1_v1_5_DigestInfo_MD5"
        out["recovered_digest_hex"] = recovered[len(DIGESTINFO_MD5) :].hex()
        out["digest_match"] = recovered[len(DIGESTINFO_MD5) :] == digest
    else:
        out["pkcs1"] = f"unexpected_recover_len={len(recovered)}"
        out["recovered_hex"] = recovered.hex()
    out["rsa_verify_ok"] = rsa_verify_digestinfo_md5(signer_pem, digest, sig)
    if out["rsa_verify_ok"] and out["digest_match"]:
        out["verdict"] = "VALID"
    elif out["rsa_recover_ok"] and not out["digest_match"]:
        out["verdict"] = "SIGNER_OK_PAD_MISMATCH"
    else:
        out["verdict"] = "INVALID"
    return out


def _reassemble(pieces: list, direction: str) -> list[tuple[int, int, bytes]]:
    out: list[tuple[int, int, bytes]] = []
    buf = None
    need = 0
    key = None
    for d, src, dest, payload in pieces:
        if d != direction:
            continue
        k = (src, dest)
        if buf is None:
            if payload.startswith(ETCH_MAGIC) and len(payload) >= 8:
                total = 8 + struct.unpack(">I", payload[4:8])[0]
                if len(payload) >= total:
                    out.append((src, dest, payload[:total]))
                else:
                    buf = bytearray(payload)
                    need = total
                    key = k
        else:
            if k != key:
                buf = None
                need = 0
                key = None
                if payload.startswith(ETCH_MAGIC) and len(payload) >= 8:
                    total = 8 + struct.unpack(">I", payload[4:8])[0]
                    if len(payload) >= total:
                        out.append((src, dest, payload[:total]))
                    else:
                        buf = bytearray(payload)
                        need = total
                        key = k
                continue
            buf.extend(payload)
            if len(buf) >= need:
                out.append((key[0], key[1], bytes(buf[:need])))
                buf = None
                need = 0
                key = None
    return out


def from_bcl_jsonl(path: Path, pad_u32: int) -> int:
    rows = [
        json.loads(ln)
        for ln in path.read_text().splitlines()
        if ln.startswith("{")
    ]
    fr_rx, fr_tx = BclFramer(), BclFramer()
    pieces: list = []
    for o in rows:
        hx = o.get("hex")
        if not hx or o.get("event") not in ("rx_bytes", "tx_bytes"):
            continue
        direction = "rx" if o["event"] == "rx_bytes" else "tx"
        fr = fr_rx if direction == "rx" else fr_tx
        for f in fr.feed(bytes.fromhex(hx)).frames:
            if f.cmd == CMD_DATA:
                pieces.append((direction, f.src, f.dest, f.payload))

    certs: dict[int, list] = defaultdict(list)
    chals: dict[int, list] = defaultdict(list)
    logins: dict[int, list] = defaultdict(list)
    for direction, bucket, method_key, field in (
        ("rx", certs, "sas_certificate", "data"),
        ("tx", chals, "_result_sas_certificate", "result"),
        ("rx", logins, "sas_login", "data"),
    ):
        for src, _dest, payload in _reassemble(pieces, direction):
            try:
                dec = decode_etch_message(payload)
            except Exception:  # noqa: BLE001
                continue
            if dec.get("method") != method_key:
                continue
            val = (dec.get("raw_fields") or {}).get(field)
            if isinstance(val, (bytes, bytearray)):
                bucket[src].append(bytes(val))

    results = []
    for src in sorted(set(certs) & set(chals) & set(logins)):
        r = verify_session(certs[src][0], chals[src][0], logins[src][0], pad_u32)
        r["src"] = src
        results.append(r)
        print(
            f"src={src} verdict={r['verdict']} "
            f"rsa_verify={r['rsa_verify_ok']} digest_match={r['digest_match']} "
            f"signer={r['signer']}"
        )

    summary = {
        "source": str(path),
        "pad_u32_hex": f"0x{pad_u32:08x}",
        "sessions": len(results),
        "valid": sum(1 for r in results if r["verdict"] == "VALID"),
        "results": results,
    }
    print(json.dumps(summary, indent=2))
    return 0 if summary["valid"] == summary["sessions"] and summary["sessions"] else 1


def from_jsonl_enriched(path: Path, pad_u32: int) -> int:
    """Pad (+ optional RSA-VERIFY) from enriched B3 etch.sas or HU events."""
    serial = None
    challenge = None
    login_len = None
    login_sig = None
    cert_blob = None
    pad_source = None
    for ln in path.read_text().splitlines():
        if not ln.startswith("{"):
            continue
        try:
            o = json.loads(ln)
        except json.JSONDecodeError:
            continue
        sas = o.get("sas") if isinstance(o.get("sas"), dict) else {}
        method = o.get("method") or sas.get("sas_method")
        if method == "sas_certificate" or o.get("event") == "sas_challenge_tx":
            serial = (
                sas.get("effective_serial_u32")
                or o.get("effective_serial_u32")
                or serial
            )
            pad_source = sas.get("pad_u32_source") or o.get("pad_u32_source") or pad_source
        if method == "_result_sas_certificate" or o.get("event") == "sas_challenge_tx":
            hx = sas.get("challenge_hex") or o.get("challenge_hex")
            if hx:
                challenge = bytes.fromhex(hx)
        if method == "sas_login" or o.get("event") == "sas_login_ok_tx":
            login_len = (
                sas.get("login_sig_len")
                or o.get("sig_len")
                or o.get("login_sig_len")
                or login_len
            )
            hx = sas.get("login_sig_hex") or o.get("login_sig_hex")
            if hx:
                login_sig = bytes.fromhex(hx)
        # Optional: full cert PEM/DER if logged
        if method == "sas_certificate":
            pem = sas.get("cert_pem") or o.get("cert_pem")
            if isinstance(pem, str) and "BEGIN" in pem:
                cert_blob = pem.encode()
    if challenge is None:
        print(f"FAIL: need challenge_hex in {path}", file=sys.stderr)
        return 1
    use_u32 = int(serial) if serial is not None else int(pad_u32)
    t = sas_challenge_transform(challenge, use_u32)
    out: dict = {
        **t,
        "pad_u32_hex": f"0x{use_u32:08x}",
        "pad_u32_source": pad_source,
        "login_sig_len": login_len,
        "source": str(path),
    }
    if login_sig is not None and cert_blob is not None:
        out["rsa_verify"] = verify_session(cert_blob, challenge, login_sig, use_u32)
    elif login_sig is not None:
        out["rsa_verify"] = {
            "skipped": True,
            "reason": "no cert_pem in jsonl (use --from-bcl-jsonl raw HU capture for RSA-VERIFY)",
            "login_sig_len": len(login_sig),
            "digest_md5_hex": t["digest_md5_hex"],
        }
    print(json.dumps(out, indent=2))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--serial-u32", type=lambda x: int(x, 0), default=None)
    ap.add_argument("--challenge-hex")
    ap.add_argument("--sig-hex")
    ap.add_argument("--cert-pem", type=Path, help="Single X509 PEM (signer) or PKCS7 PEM")
    ap.add_argument("--from-jsonl", type=Path, help="Enriched events (pad-only)")
    ap.add_argument(
        "--from-bcl-jsonl",
        type=Path,
        help="Raw HU/B3 jsonl with rx_bytes/tx_bytes hex — full RSA-VERIFY",
    )
    ap.add_argument(
        "--pad-u32",
        type=lambda x: int(x, 0),
        default=SAS_APP_AUTH_PAD_U32,
        help=f"Pad input u32 (default APP_AUTH 0x{SAS_APP_AUTH_PAD_U32:08x})",
    )
    args = ap.parse_args()

    if args.from_bcl_jsonl:
        return from_bcl_jsonl(args.from_bcl_jsonl, args.pad_u32)
    if args.from_jsonl:
        return from_jsonl_enriched(args.from_jsonl, args.pad_u32)

    if args.challenge_hex and args.sig_hex and args.cert_pem:
        chal = bytes.fromhex(args.challenge_hex)
        sig = bytes.fromhex(args.sig_hex)
        cert = args.cert_pem.read_bytes()
        pad = args.serial_u32 if args.serial_u32 is not None else args.pad_u32
        print(json.dumps(verify_session(cert, chal, sig, pad), indent=2))
        return 0

    if args.serial_u32 is None or not args.challenge_hex:
        ap.error(
            "need --from-bcl-jsonl, or --serial-u32 + --challenge-hex "
            "[+ --sig-hex --cert-pem for RSA-VERIFY]"
        )
    t = sas_challenge_transform(bytes.fromhex(args.challenge_hex), args.serial_u32)
    print(json.dumps(t, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
