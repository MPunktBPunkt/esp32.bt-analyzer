#!/usr/bin/env python3
"""Packt web/index.html als gzip-PROGMEM nach src/core/UiPagesGz.h."""
from __future__ import annotations

import gzip
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / "src" / "core"


def _pack(src: Path, out: Path) -> None:
    raw = src.read_bytes()
    gz = gzip.compress(raw, compresslevel=9)
    lines = [
        "#pragma once",
        "",
        "#include <Arduino.h>",
        "",
        "/** Autogeneriert von tools/pack_ui.py — nicht von Hand editieren.",
        f" *  Quelle: {src.name} ({len(raw)} B) → gzip ({len(gz)} B).",
        " */",
        f"static const size_t PAGE_MAIN_GZ_LEN = {len(gz)};",
        "static const uint8_t PAGE_MAIN_GZ[] PROGMEM = {",
    ]
    row: list[str] = []
    for b in gz:
        row.append(f"0x{b:02x}")
        if len(row) == 12:
            lines.append("  " + ", ".join(row) + ",")
            row = []
    if row:
        lines.append("  " + ", ".join(row) + ",")
    lines.append("};")
    lines.append("")
    out.parent.mkdir(parents=True, exist_ok=True)
    text = "\n".join(lines) + "\n"
    if out.is_file() and out.read_text() == text:
        print(f"pack_ui: {out.name} unveraendert ({len(raw)} → {len(gz)} B)")
        return
    out.write_text(text)
    print(f"pack_ui: {src.name} {len(raw)} B → {out.name} {len(gz)} B gzip")


def main() -> int:
    # Always emit both; WebUi picks via BT_ANALYZER_BOARD_ESP32.
    full = ROOT / "web" / "index.html"
    mini = ROOT / "web" / "index_esp32_min.html"
    if not full.is_file():
        print(f"pack_ui: fehlt {full}", file=sys.stderr)
        return 1
    if not mini.is_file():
        print(f"pack_ui: fehlt {mini}", file=sys.stderr)
        return 1
    _pack(full, CORE / "UiPagesGz.h")
    _pack(mini, CORE / "UiPagesGzEsp32.h")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
