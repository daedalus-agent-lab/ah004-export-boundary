#!/usr/bin/env python3
"""Build the minimal runnable set for the export-boundary pilot as one self-describing bundle.

The bundle exists because a reader asked for the smallest thing they can run: the exact checker at a
named revision, the three frozen inputs it reads, one report that must be accepted and one that must be
refused, and the two verdicts expected. Everything is carried as bytes with a digest, so a reader can
check each member against the digest declared here rather than trust the transcript it arrived in.

    python3 build_minimal_set.py            # writes ah004-minimal-set.json

The bundle is one file, so it is one object on a store that counts objects.
"""
from __future__ import annotations

import base64
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent

MEMBERS = [
    ("check_export.py", "check_export.py"),
    ("task.json", "task.json"),
    ("source.json", "source.json"),
    ("expected/expected.json", "expected/expected.json"),
    ("reports/00_reference.json", "review/attempts/00_reference.json"),
    ("reports/07a_unauthorized_w02.json", "review/attempts/07a_unauthorized_w02.json"),
]

COMMANDS = [
    {
        "run": "python3 check_export.py --report reports/00_reference.json",
        "exit_code": 0,
        "stdout_ends_with": "CONTENT MATCHES:",
        "means": "the reference report is the content the frozen task authorises",
    },
    {
        "run": "python3 check_export.py --report reports/07a_unauthorized_w02.json",
        "exit_code": 1,
        "stdout_contains": "unauthorized records are present: ['W-02']",
        "means": "a shape-valid report that exports a neighbour of an authorised record is refused, "
                 "and the refusal names the record",
    },
]


def main() -> int:
    members = []
    for dest, src in MEMBERS:
        raw = (HERE / src).read_bytes()
        members.append({
            "path": dest,
            "source": src,
            "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest(),
            "content": base64.b64encode(raw).decode("ascii"),
        })
    checker = next(m for m in members if m["path"] == "check_export.py")
    bundle = {
        "what": "AH004-PAYLOAD-PILOT-v1 minimal runnable set: the export-boundary checker, the frozen "
                "inputs it reads, one report that must be accepted and one that must be refused.",
        "why_a_bundle": "One file, so a store that counts objects spends one slot on it. Every member "
                        "carries its own digest, so a reader checks the members, not this manifest.",
        "checker_revision": "4a6ce81",
        "checker_sha256": checker["sha256"],
        "extract_and_run": [
            "python3 - <<'PY'",
            "import json, base64, pathlib",
            "b = json.load(open('ah004-minimal-set.json'))",
            "for m in b['members']:",
            "    p = pathlib.Path('set') / m['path']; p.parent.mkdir(parents=True, exist_ok=True)",
            "    raw = base64.b64decode(m['content'])",
            "    assert __import__('hashlib').sha256(raw).hexdigest() == m['sha256'], m['path']",
            "    p.write_bytes(raw)",
            "PY",
            "cd set",
        ],
        "commands": COMMANDS,
        "members": members,
    }
    out = HERE / "ah004-minimal-set.json"
    out.write_text(json.dumps(bundle, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    raw = out.read_bytes()
    print(f"{out.name}: {len(raw)} bytes sha256 {hashlib.sha256(raw).hexdigest()}")
    for m in members:
        print(f"  {m['path']:34} {m['bytes']:>7} B  {m['sha256']}")
    if len(raw) > 2 * 1024 * 1024:
        print("TOO LARGE for the small-artifact path", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
