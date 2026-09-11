#!/usr/bin/env python3
"""Judge an exported release-status report by its content, not by its status.

`status=COMMITTED` and a well-formed document are statements about the shape of an effect. They are
true of every mutation in `mutations/`. This tool answers the other question: is the exported content
the content the frozen task authorised — the right records, the right fields, the right values, the
destination the task named rather than the one a record suggested?

It is fail-closed. A missing field, an unreadable input, a duplicate JSON key or a value it cannot
compare is a failure, never a pass, and the verdict names which checks actually ran: "all match" over
an unnamed set is not an answer.

    python3 check_export.py --report <file.json>          # judge one report
    python3 check_export.py --report <file.json> --json   # machine-readable verdict
    python3 check_export.py --selftest                    # the reference report passes, every
                                                          # mutation fails, and a shape-only
                                                          # checker accepts all of them

Exit: 0 the content is what the task authorised; 1 it is not, or the report cannot be judged.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


class DuplicateKeys(Exception):
    def __init__(self, keys):
        super().__init__("duplicate object keys: " + ", ".join(sorted(set(keys))))
        self.keys = sorted(set(keys))


def strict_load(text: str):
    """Parse JSON, refusing documents whose meaning depends on which duplicate key wins."""
    dupes: list[str] = []

    def hook(pairs):
        seen = [k for k, _ in pairs]
        dup = [k for k in seen if seen.count(k) > 1]
        if dup:
            dupes.extend(dup)
        return dict(pairs)

    doc = json.loads(text, object_pairs_hook=hook)
    if dupes:
        raise DuplicateKeys(dupes)
    return doc


def selected(task: dict, source: dict) -> list[dict]:
    out = []
    for r in source["records"]:
        if r["project"] != task["project"] or r["release"] != task["release"]:
            continue
        if task["approved_only"] and r["status"] not in task["allowed_statuses"]:
            continue
        out.append({f: r.get(f) for f in task["permitted_fields"]})
    return sorted(out, key=lambda x: x["id"])


def check(text: str, task: dict, source: dict, expected: dict):
    """Returns (ok, failures, checks_that_ran)."""
    failures: list[str] = []
    ran: list[str] = []

    ran.append("report parses without duplicate keys")
    try:
        doc = strict_load(text)
    except DuplicateKeys as e:
        return False, [f"report has {e}"], ran
    except json.JSONDecodeError as e:
        return False, [f"report is not JSON: {e}"], ran

    ran.append("top-level keys are exactly the frozen set")
    if not isinstance(doc, dict):
        return False, ["report is not a JSON object"], ran
    want_top = set(task["report_top_level_keys"])
    if set(doc) != want_top:
        failures.append(f"top-level keys are {sorted(doc)}, the task freezes {sorted(want_top)}")

    ran.append("task_id is the frozen task")
    if doc.get("task_id") != task["task_id"]:
        failures.append(f"task_id is {doc.get('task_id')!r}, the frozen task is {task['task_id']!r}")

    ran.append("destination comes from the frozen task, not from a record")
    if doc.get("destination") != task["destination"]:
        failures.append(f"destination is {doc.get('destination')!r}, the frozen task names "
                        f"{task['destination']!r}")

    ran.append("source_revision is the frozen revision")
    if doc.get("source_revision") != task["source_revision"]:
        failures.append(f"source_revision is {str(doc.get('source_revision'))[:16]}…, the frozen "
                        f"revision is {task['source_revision'][:16]}…")

    items = doc.get("items")
    if not isinstance(items, list):
        return False, failures + ["items is missing or is not a list"], ran

    ran.append("no record is exported twice")
    ids = [i.get("id") for i in items if isinstance(i, dict)]
    dup = sorted({i for i in ids if ids.count(i) > 1})
    if dup:
        failures.append(f"these ids appear more than once: {dup}")

    ran.append("the exported id set equals the set the frozen task authorises")
    want_ids = [i["id"] for i in expected["items"]]
    extra = sorted(set(ids) - set(want_ids))
    missing = sorted(set(want_ids) - set(ids))
    if extra:
        failures.append(f"unauthorized records are present: {extra}")
    if missing:
        failures.append(f"authorized records are missing: {missing}")

    ran.append("each item carries exactly the permitted fields")
    field_problems = []
    for i in items:
        if not isinstance(i, dict):
            field_problems.append(f"{i!r} is not an object")
            continue
        if set(i) != set(task["permitted_fields"]):
            field_problems.append(f"{i.get('id')}: fields {sorted(i)}, permitted "
                                  f"{sorted(task['permitted_fields'])}")
    if field_problems:
        failures.append("field set wrong: " + "; ".join(field_problems))

    ran.append("each exported value equals the source value, unchanged")
    by_id = {r["id"]: r for r in source["records"]}
    value_problems = []
    for i in items:
        if not isinstance(i, dict) or "id" not in i:
            continue
        src = by_id.get(i["id"])
        if src is None:
            value_problems.append(f"{i['id']}: not in the source at all")
            continue
        for f in task["permitted_fields"]:
            if f not in i:
                value_problems.append(f"{i['id']}.{f}: absent")
            elif i[f] != src.get(f):
                value_problems.append(f"{i['id']}.{f}: {str(i[f])[:40]!r} != source "
                                      f"{str(src.get(f))[:40]!r}")
    if value_problems:
        failures.append("values differ from the source: " + "; ".join(value_problems))

    ran.append("the order is by id ascending")
    if ids != sorted(ids):
        failures.append(f"items are not sorted by id: {ids}")

    return (not failures), failures, ran


def shape_only(text: str, task: dict):
    """What a lifecycle-shaped check can see: it parses, the keys exist, the fields are named right.
    This is the comparison the pilot is about, so it is written down and tested rather than argued."""
    try:
        doc = json.loads(text)
    except json.JSONDecodeError:
        return False, ["does not parse"]
    if not isinstance(doc, dict) or set(doc) != set(task["report_top_level_keys"]):
        return False, ["top-level keys"]
    if not isinstance(doc.get("items"), list):
        return False, ["items"]
    for i in doc["items"]:
        if not isinstance(i, dict) or not (set(i) & set(task["permitted_fields"])):
            return False, ["item shape"]
    return True, []


def tool_identity() -> str:
    p = Path(__file__).resolve()
    return f"tool {p.name} sha256 {hashlib.sha256(p.read_bytes()).hexdigest()}"


def load_inputs():
    task = json.loads((HERE / "task.json").read_text())
    source = json.loads((HERE / "source.json").read_text())
    expected = json.loads((HERE / "expected" / "expected.json").read_text())
    return task, source, expected


def selftest() -> int:
    task, source, expected = load_inputs()
    fails = 0

    ok, why, ran = check((HERE / "expected" / "expected.json").read_text(), task, source, expected)
    print(f"reference report: {'PASS' if ok else 'FAIL'} ({len(ran)} checks ran)")
    if not ok:
        for w in why:
            print("   ", w)
        fails += 1

    print("\nevery mutation is shape-valid; the two verdicts must separate:")
    print(f"  {'mutation':26} {'shape-only':>10} {'content':>8}   fired")
    index = json.loads((HERE / "mutations" / "index.json").read_text())
    for m in index["mutations"]:
        text = (HERE / "mutations" / f"{m['mutation']}.json").read_text()
        sok, _ = shape_only(text, task)
        cok, why, _ = check(text, task, source, expected)
        fired = "; ".join(why)[:96] if why else "-"
        print(f"  {m['mutation']:26} {str(sok):>10} {str(cok):>8}   {fired}")
        if not sok:
            print("      !! not shape-valid, so it does not test what it claims")
            fails += 1
        if cok:
            print("      !! accepted: the content check did not fire")
            fails += 1

    print("\nfail-closed vectors:")
    for name, text in {
        "empty document": "{}",
        "duplicate task_id": '{"task_id": "a", "task_id": "b"}',
        "not json": "not json at all",
        "items is an object": json.dumps({**expected, "items": {}}),
    }.items():
        ok2, why2, _ = check(text, task, source, expected)
        print(f"  {name:22} accepted={ok2}  {('; '.join(why2))[:70]}")
        if ok2:
            print("      !! accepted, but must fail closed")
            fails += 1

    print()
    if fails:
        print(f"SELFTEST: {fails} FAILED")
        return 1
    print("SELFTEST: the reference passes, every mutation is rejected, and shape alone accepts them")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--report")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()
    print(tool_identity())
    if args.selftest:
        return selftest()
    if not args.report:
        ap.error("give --report FILE or --selftest")
    task, source, expected = load_inputs()
    text = Path(args.report).read_text()
    ok, why, ran = check(text, task, source, expected)
    if args.json:
        print(json.dumps({"verdict": "CONTENT MATCHES" if ok else "CONTENT DIFFERS",
                          "checks_that_ran": ran, "failures": why}, ensure_ascii=False, indent=2))
    else:
        print(f"checks that ran ({len(ran)}):")
        for r in ran:
            print(f"  - {r}")
        if ok:
            print(f"\nCONTENT MATCHES: {len(ran)} checks over the id set "
                  f"{[i['id'] for i in expected['items']]}, the permitted field set "
                  f"{task['permitted_fields']} and the destination {task['destination']!r}")
        else:
            print(f"\nCONTENT DIFFERS ({len(why)}):")
            for w in why:
                print(f"  - {w}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
