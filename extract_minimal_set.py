#!/usr/bin/env python3
"""Safely extract the published AH004 minimal set.

This extractor is intentionally separate from the bundle: the bundle is untrusted input, while these
literals are the expected outer and member digests from the pinned publication. It validates every
byte and every path before creating or writing the output directory. It does not use assert, so -O
cannot remove a security check.

Usage: python3 extract_minimal_set.py ah004-minimal-set.json [output-dir]
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import sys
from pathlib import Path

BUNDLE_SHA256 = "05c03164a40da99bb07a3c7573f2e7b210444ab0bc76f417a19ff9c3828d33bb"
EXPECTED = {
    "check_export.py": "4ea9f25eba5e126ff95e77fd354b91c0e62e37d54f95c61305743e57918f84a4",
    "task.json": "877145258cfa805e31cfb77c8b6531cdf50ad43e10d7e7e734b3bb039b67f291",
    "source.json": "4a0fcaee90460de57bf2337c618846c399375807a62cc3c014ce411085068781",
    "expected/expected.json": "9c6a7f2f19dae1e1bef307923f2a15ff7264e4dc8beca3147578926f320436b3",
    "reports/00_reference.json": "9c6a7f2f19dae1e1bef307923f2a15ff7264e4dc8beca3147578926f320436b3",
    "reports/07a_unauthorized_w02.json": "5be59447b004d4ebebf3549f63b04971124bcce868a3e8ea7242b5870bee3519",
}


def fail(message: str) -> None:
    raise SystemExit("REFUSED: " + message)


def main(argv: list[str]) -> int:
    if len(argv) not in (2, 3):
        fail("usage: extract_minimal_set.py BUNDLE.json [OUTPUT_DIR]")
    bundle_path = Path(argv[1])
    output = Path(argv[2]) if len(argv) == 3 else Path("set")
    raw = bundle_path.read_bytes()
    actual = hashlib.sha256(raw).hexdigest()
    if not hmac.compare_digest(actual, BUNDLE_SHA256):
        fail(f"outer digest {actual} does not match pinned publication {BUNDLE_SHA256}")
    try:
        doc = json.loads(raw)
    except json.JSONDecodeError as exc:
        fail(f"bundle is not JSON: {exc}")
    members = doc.get("members") if isinstance(doc, dict) else None
    if not isinstance(members, list) or len(members) != len(EXPECTED):
        fail(f"members must be a list of exactly {len(EXPECTED)} entries")

    decoded: dict[str, bytes] = {}
    seen: set[str] = set()
    for member in members:
        if not isinstance(member, dict) or not isinstance(member.get("path"), str):
            fail("each member must have a string path")
        path = member["path"]
        if path in seen or path not in EXPECTED:
            fail(f"unexpected or duplicate member path: {path!r}")
        seen.add(path)
        p = Path(path)
        if p.is_absolute() or ".." in p.parts or "." in p.parts or not path:
            fail(f"unsafe member path: {path!r}")
        if not isinstance(member.get("content"), str):
            fail(f"member {path!r} has no base64 content")
        try:
            content = base64.b64decode(member["content"], validate=True)
        except Exception as exc:
            fail(f"member {path!r} has invalid base64: {exc}")
        actual_member = hashlib.sha256(content).hexdigest()
        if not hmac.compare_digest(actual_member, EXPECTED[path]):
            fail(f"member {path!r} digest {actual_member} does not match its pinned digest")
        decoded[path] = content
    if seen != set(EXPECTED):
        fail("member set is incomplete")
    if output.exists():
        if output.is_symlink() or not output.is_dir():
            fail(f"output exists but is not a real directory: {output}")
        fail(f"refusing to write into existing output directory: {output}")
    output.mkdir(parents=True)
    for path, content in decoded.items():
        destination = output / path
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(content)
    print(f"extracted {len(decoded)} pinned members into {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
