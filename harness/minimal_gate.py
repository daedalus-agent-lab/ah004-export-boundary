#!/usr/bin/env python3
"""Two matched gates over a real SQLite outbox: one that checks lifecycle, one that checks content.

The case in this repository separates shape from content with nine reports that a shape check must
accept and a content check must reject. `check_export.py`'s `shape_only` is my model of a lifecycle
check written by me, which is a weak thing to build a claim on. This harness replaces the model with an
implementation: two gates, identical in every lifecycle respect, differing in one place.

  L  the same owner / single-use / STOP / revocation / revision / integer-budget checks, plus a generic
     JSON shape check. It does not look at task-level data semantics. This is the design the
     PAYLOAD-PILOT calls L.
  V  the same lifecycle checks, and then the content relation against the frozen task at use.

Both write effects into SQLite tables, so "COMMITTED" is a row and a refusal is the absence of one.

What this does and does not show. It shows, on a machine, that the nine mutations land as committed
effects through L and as refusals through V — with a real store rather than an argument. It does NOT
show that any independently written L behaves this way: both gates are mine, and the pilot's own scope
already notes that shared author, fixtures and storage are not independent products. Read it as a
demonstration that the case has teeth, not as a measurement of anyone else's implementation.

  python3 minimal_gate.py --selftest
  python3 minimal_gate.py --arm L --report ../mutations/m2_private_field_leak.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent

SCHEMA = """
CREATE TABLE IF NOT EXISTS effects(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticket TEXT NOT NULL,
    destination TEXT,
    payload TEXT,
    stored_sha256 TEXT,
    checked_sha256 TEXT,
    outcome TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS tickets(ticket TEXT PRIMARY KEY, owner TEXT NOT NULL, used INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS control(k TEXT PRIMARY KEY, v TEXT NOT NULL);
"""


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def load_inputs():
    task = json.loads((ROOT / "task.json").read_text())
    source = json.loads((ROOT / "source.json").read_text())
    expected = json.loads((ROOT / "expected" / "expected.json").read_text())
    return task, source, expected


def authorised(task: dict, source: dict) -> dict:
    """The report the frozen task authorises, keyed by id. Second implementation of the same rule as
    check_export.py's selector, written separately so that a slip in one is visible in the other."""
    keep = {}
    for r in source["records"]:
        if r["project"] != task["project"]:
            continue
        if r["release"] != task["release"]:
            continue
        if task["approved_only"] and not any(r["status"] == s for s in task["allowed_statuses"]):
            continue
        keep[r["id"]] = {f: r[f] for f in task["permitted_fields"]}
    return dict(sorted(keep.items()))


class Gate:
    def __init__(self, task: dict, source: dict, arm: str, db: str = ":memory:"):
        assert arm in ("L", "V")
        self.arm = arm
        self.task = task
        self.source = source
        self.db = sqlite3.connect(db)
        self.db.executescript(SCHEMA)
        c = self.db.cursor()
        c.execute("INSERT OR REPLACE INTO control(k, v) VALUES('revision', ?)",
                  (task["source_revision"],))
        c.execute("INSERT OR REPLACE INTO control(k, v) VALUES('stop', '0')")
        c.execute("INSERT OR REPLACE INTO control(k, v) VALUES('revoked', '0')")
        c.execute("INSERT OR REPLACE INTO control(k, v) VALUES('exports_used', '0')")
        self.db.commit()

    # -- lifecycle ---------------------------------------------------------------------------------
    def _c(self, k: str) -> str:
        return self.db.execute("SELECT v FROM control WHERE k=?", (k,)).fetchone()[0]

    def issue(self, owner: str) -> str:
        t = sha(f"{owner}:{self._c('exports_used')}:{len(self.db.execute('SELECT id FROM effects').fetchall())}".encode())[:16]
        self.db.execute("INSERT INTO tickets(ticket, owner, used) VALUES(?,?,0)", (t, owner))
        self.db.commit()
        return t

    def stop(self) -> None:
        self.db.execute("UPDATE control SET v='1' WHERE k='stop'")
        self.db.commit()

    def revoke(self) -> None:
        self.db.execute("UPDATE control SET v='1' WHERE k='revoked'")
        self.db.commit()

    def _lifecycle(self, ticket: str, owner: str, revision: str) -> str | None:
        row = self.db.execute("SELECT owner, used FROM tickets WHERE ticket=?", (ticket,)).fetchone()
        if row is None:
            return "UNKNOWN_TICKET"
        if row[0] != owner:
            return "WRONG_OWNER"
        if row[1]:
            return "TICKET_ALREADY_USED"
        if self._c("stop") == "1":
            return "STOPPED"
        if self._c("revoked") == "1":
            return "REVOKED"
        if revision != self._c("revision"):
            return "STALE_REVISION"
        if int(self._c("exports_used")) >= int(self.task["budget_exports"]):
            return "EXPORT_BUDGET_EXHAUSTED"
        return None

    # -- the one place the two arms differ ---------------------------------------------------------
    def _content(self, doc) -> str | None:
        """Only V calls this. Returns None when the content is what the frozen task authorises."""
        if not isinstance(doc, dict):
            return "PAYLOAD_NOT_AN_OBJECT"
        if doc.get("destination") != self.task["destination"]:
            return "WRONG_DESTINATION"
        if doc.get("source_revision") != self.task["source_revision"]:
            return "WRONG_REVISION_IN_PAYLOAD"
        if doc.get("task_id") != self.task["task_id"]:
            return "WRONG_TASK_ID"
        items = doc.get("items")
        if not isinstance(items, list):
            return "ITEMS_NOT_A_LIST"
        want = authorised(self.task, self.source)
        seen = []
        for it in items:
            if not isinstance(it, dict):
                return "ITEM_NOT_AN_OBJECT"
            if "id" not in it:
                return "ITEM_WITHOUT_ID"
            # Refuse before hashing or sorting. An id that is a list or an object raises TypeError out of
            # set(); a gate that raises has not refused, and a caller that reads an empty reason as "no
            # finding" would then commit a payload the gate never judged.
            if not isinstance(it["id"], str):
                return f"ID_NOT_A_STRING({type(it['id']).__name__})"
            seen.append(it["id"])
        if len(seen) != len(set(seen)):
            return "DUPLICATE_RECORD"
        if set(seen) != set(want):
            missing = sorted(set(want) - set(seen))
            extra = sorted(set(seen) - set(want))
            return f"ID_SET_DIFFERS(missing={missing},extra={extra})"
        for it in items:
            src = want[it["id"]]
            if set(it) != set(self.task["permitted_fields"]):
                return f"FIELD_SET_DIFFERS({it['id']})"
            for f in self.task["permitted_fields"]:
                if it[f] != src[f]:
                    return f"VALUE_DIFFERS({it['id']}.{f})"
        if seen != sorted(seen):
            return "ORDER_DIFFERS"
        return None

    # -- one export attempt ------------------------------------------------------------------------
    def export(self, ticket: str, owner: str, payload: bytes, substitute=None) -> dict:
        """Refuse with no new effect, or commit exactly one. Nothing is written on any refusal.

        No input may reach the caller as a traceback. An unexpected exception is caught, the
        transaction is rolled back and the refusal is named, because a raise is not a refusal: a
        caller that treats an unnamed failure as "no finding" would let through a payload the gate
        never judged. The verdict stays REFUSED either way; what changes is that the reason always
        has a name.
        """
        try:
            return self._export(ticket, owner, payload, substitute=substitute)
        except Exception as exc:  # noqa: BLE001 - nothing escaping is the point
            self.db.rollback()
            reason = f"CHECK_ERROR({type(exc).__name__})"
            self._refuse(ticket, reason)
            return {"outcome": "REFUSED", "reason": reason, "new_effects": 0}

    def _export(self, ticket: str, owner: str, payload: bytes, substitute=None) -> dict:
        doc = None
        try:
            doc = json.loads(payload)
        except json.JSONDecodeError:
            doc = None
        if doc is None or not isinstance(doc, dict) or "items" not in doc:
            self._refuse(ticket, "NOT_A_REPORT")
            return {"outcome": "REFUSED", "reason": "NOT_A_REPORT", "new_effects": 0}

        rev = self._c("revision")
        bad = self._lifecycle(ticket, owner, rev)
        if bad:
            self._refuse(ticket, bad)
            return {"outcome": "REFUSED", "reason": bad, "new_effects": 0}

        checked_sha = sha(payload)
        if self.arm == "V":
            why = self._content(doc)
            if why:
                self._refuse(ticket, why)
                return {"outcome": "REFUSED", "reason": why, "new_effects": 0}

        to_write = payload if substitute is None else substitute(payload)
        if self.arm == "V" and sha(to_write) != checked_sha:
            # the bytes at the write differ from the bytes that were checked: refuse, write nothing
            self._refuse(ticket, "PAYLOAD_SUBSTITUTED_AFTER_CHECK")
            return {"outcome": "REFUSED", "reason": "PAYLOAD_SUBSTITUTED_AFTER_CHECK", "new_effects": 0}

        self.db.execute(
            "INSERT INTO effects(ticket, destination, payload, stored_sha256, checked_sha256, outcome)"
            " VALUES(?,?,?,?,?,?)",
            (ticket, doc.get("destination"), to_write.decode("utf-8", "replace"),
             sha(to_write), checked_sha, "COMMITTED"))
        self.db.execute("UPDATE tickets SET used=1 WHERE ticket=?", (ticket,))
        self.db.execute("UPDATE control SET v=? WHERE k='exports_used'",
                        (str(int(self._c("exports_used")) + 1),))
        self.db.commit()
        return {"outcome": "COMMITTED", "reason": None, "new_effects": 1}

    def _refuse(self, ticket: str, reason: str) -> None:
        self.db.execute("INSERT INTO effects(ticket, outcome) VALUES(?,?)", (ticket, "REFUSED:" + reason))
        self.db.execute("UPDATE tickets SET used=1 WHERE ticket=?", (ticket,))
        self.db.commit()

    def committed(self) -> list[dict]:
        return [{"id": r[0], "destination": r[1], "payload": r[2], "stored_sha256": r[3]}
                for r in self.db.execute(
                    "SELECT id, destination, payload, stored_sha256 FROM effects WHERE outcome='COMMITTED'")]

    def new_effects(self) -> int:
        return self.db.execute("SELECT COUNT(*) FROM effects WHERE outcome='COMMITTED'").fetchone()[0]


def run_one(arm: str, payload: bytes, task, source, owner="agent", substitute=None) -> dict:
    g = Gate(task, source, arm)
    t = g.issue(owner)
    r = g.export(t, owner, payload, substitute=substitute)
    r["effects_in_store"] = g.new_effects()
    r["rows"] = g.committed()
    return r


def selftest() -> int:
    task, source, expected = load_inputs()
    muts = json.loads((ROOT / "mutations" / "index.json").read_text())["mutations"]
    exp_bytes = (ROOT / "expected" / "expected.json").read_bytes()
    fails = 0

    print(f"{'report':28} {'L':>10} {'V':>10}  L reason / V reason")
    rows = [("expected", exp_bytes)]
    rows += [(m["mutation"], (ROOT / "mutations" / f"{m['mutation']}.json").read_bytes()) for m in muts]

    l_commits = v_commits = 0
    for name, payload in rows:
        l = run_one("L", payload, task, source)
        v = run_one("V", payload, task, source)
        l_ok = l["outcome"] == "COMMITTED"
        v_ok = v["outcome"] == "COMMITTED"
        if name != "expected":
            # the expected report is the control: only the mutations test whether the case has teeth
            l_commits += l_ok
            v_commits += v_ok
        else:
            if not (l_ok and v_ok):
                print("FAIL: the expected report must commit in BOTH arms; it is the control")
                fails += 1
        tag = "ok  " if (l_ok != v_ok) or name == "expected" else "??  "
        print(f"{tag}{name:26} {l['outcome']:>10} {v['outcome']:>10}  "
              f"{l['reason'] or '-'} / {v['reason'] or '-'}")

    print()
    want_l = len(muts)
    if l_commits != want_l:
        print(f"FAIL: L committed {l_commits} of {want_l} mutations; the case has no teeth against it")
        fails += 1
    else:
        print(f"ok   L committed all {want_l} mutations — each is a real effect in the outbox")
    if v_commits != 0:
        print(f"FAIL: V committed {v_commits} of the {want_l} mutations; it must commit none of them")
        fails += 1
    else:
        print("ok   V refused all nine mutations, and the control above shows it commits the "
              "expected report")

    print("\ncase D: substitution between the check and the write")
    for arm in ("L", "V"):
        r = run_one(arm, exp_bytes, task, source,
                    substitute=lambda b: b.replace(b'"owner": "o1"', b'"owner": "attacker"'))
        # search the WHOLE stored payload: the first replaced value sits past any short prefix
        stored = r["rows"][0]["payload"] if r["rows"] else ""
        substituted = '"owner": "attacker"' in stored
        print(f"  {arm}: {r['outcome']:>10}  effects={r['effects_in_store']}  "
              f"substituted bytes in the effect store: {substituted}")
        if arm == "L" and not substituted:
            print("  FAIL: L should carry the substituted bytes, that is what makes it L")
            fails += 1
        if arm == "V" and substituted:
            print("  FAIL: V carried substituted bytes into the effect")
            fails += 1

    print("\nrefusal leaves nothing behind (the request-local ERROR test)")
    g = Gate(task, source, "L")
    t = g.issue("agent")
    g.stop()
    before = g.new_effects()
    r = g.export(t, "agent", exp_bytes)
    after = g.new_effects()
    ok = r["outcome"] == "REFUSED" and before == after == 0
    print(f"  {'ok  ' if ok else 'FAIL'} after STOP: {r['outcome']}/{r['reason']}, "
          f"effects {before} -> {after}")
    fails += not ok

    print("\nhostile shapes: the gate must REFUSE by name, never raise")
    fails += hostile_checks()

    print()
    if fails:
        print(f"HARNESS SELFTEST: {fails} FAILED")
        return 1
    print("HARNESS SELFTEST: L commits every mutation, V refuses every mutation, substitution is "
          "caught by V and not by L")
    return 0


def hostile_checks() -> int:
    """Run the CLI as a subprocess, because the defect being guarded against is an exception on its
    way to the caller. An in-process call would let the exception surface as a crash of this file and
    prove the opposite of what is wanted: what is wanted is that nothing escapes at all."""
    import subprocess
    bad = 0
    here = Path(__file__).resolve().parent
    manifest = json.loads((here / "hostile" / "index.json").read_text())["fixtures"]
    for fx in manifest:
        path = here / "hostile" / fx["file"]
        p = subprocess.run([sys.executable, str(here / "minimal_gate.py"), "--arm", "V",
                            "--report", str(path)], capture_output=True, text=True, timeout=120)
        traceback = "Traceback" in p.stderr or p.stderr.strip() != ""
        named = "REFUSED" in p.stdout and '"reason": "' in p.stdout
        no_effect = '"effects_in_store": 0' in p.stdout
        ok = p.returncode != 0 and named and not traceback and no_effect
        if not ok:
            bad += 1
        print(f"  {'ok  ' if ok else 'FAIL'} {fx['file']:20} exit={p.returncode} "
              f"named={named} traceback={traceback} no_effect={no_effect}")
        if not ok:
            print(f"        wanted: {fx['must']}")
            if p.stderr.strip():
                print("        stderr: " + p.stderr.strip().splitlines()[-1][:160])
    print(f"  {'ok  ' if not bad else 'FAIL'} {len(manifest) - bad}/{len(manifest)} hostile shapes "
          f"refused by name with no traceback and no effect")
    return bad


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--arm", choices=["L", "V"])
    ap.add_argument("--report")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()
    p = Path(__file__).resolve()
    print(f"tool {p.name} sha256 {sha(p.read_bytes())}")
    if args.selftest:
        return selftest()
    if not (args.arm and args.report):
        ap.error("give --selftest, or --arm L|V --report FILE")
    task, source, _ = load_inputs()
    r = run_one(args.arm, Path(args.report).read_bytes(), task, source)
    print(json.dumps({k: v for k, v in r.items() if k != "rows"}, indent=2))
    if r["rows"]:
        print(json.dumps(r["rows"], indent=2)[:600])
    return 0 if r["outcome"] == "COMMITTED" else 1


if __name__ == "__main__":
    sys.exit(main())
