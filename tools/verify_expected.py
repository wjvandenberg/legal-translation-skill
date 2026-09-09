#!/usr/bin/env python3
"""verify_expected.py - is the failing set EXACTLY the set this project declared?
CHECKER VERSION 1 (2026-08-31)

If a project's copy says a lower version than this one, it is stale - see the "Checkers"
line for each version in ...\\Coding\\templates\\TEMPLATE-CHANGELOG.md and re-copy.

THE GAP THIS FILLS. A gate that records only successful commands cannot record a project
that has a DECLARED, PERMANENT exemption - an over-cap charter, a template whose {{FILL}}
markers are the deliverable, a merge commit authored server-side by an account. Its verify
command exits 1 for ever, so `cycle_evidence.py` refuses it: a failing command is not
evidence, and that rule must not bend. THE CYCLE GATE IS THEREFORE UNUSABLE IN EXACTLY THE
PROJECTS MOST LIKELY TO WANT IT.

    uv run python tools/verify_expected.py             # every run the config declares
    uv run python tools/verify_expected.py --selftest
    uv run python tools/verify_expected.py --write-config

DECLARING N/A IS THE WRONG ROUTE, and that is why this exists at all. N/A says verify does
not APPLY. It applies, and it passes, apart from something already written down.

WHY A WRAPPER RATHER THAN A KEY INSIDE EACH CHECKER, decided rather than assumed. Both
shapes can compare a failing set to a declared one in both directions. WHAT SEPARATES THEM
IS WHERE THE TOLERANCE SITS: here the checker is run unmodified and still returns its own
honest code, so `verify_md.py` on its own always tells the truth and this script decides
separately what was expected. An `expected_failures` key inside the checker would make the
checker itself print PASS while something failed - and there would be no honest question
left to ask it.

BOTH DIRECTIONS, AND THE SECOND ONE IS THE POINT. An undeclared failure is the obvious
finding. A DECLARED failure that has started PASSING is the dangerous one: the exemption is
now stale, and a stale exemption silently absorbs the NEXT real regression in that file -
the failure would arrive already declared.

THE ONE HOLE THIS DOES NOT CLOSE, STATED RATHER THAN IMPLIED. A row that is failing today
can be declared tolerated today, and nothing mechanical can tell that from a genuine
exemption. What is enforced is that a reason is written down beside it, where a reader will
meet it - the same answer this house gives for a JUDGE.

A VOID RUN IS NEVER TOLERABLE. If a checker exits 2 it could not look, so there is no
failing set to compare and none may be declared: "the instrument was broken" must not become
a thing you write down once and stop being told about.

Exit codes:  0 = the failing set is exactly the declared set
             · 1 = it is not · 2 = a declared run could not be judged (VOID, never a pass)
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from house_common import (                                       # noqa: E402
    FAIL, NA, PASS, RC_COULD_NOT_RUN, RC_FAILED, RC_OK, REPORT_FLAG, VOID,
    Case, Report, finish, load_section, report_pairing, run_cases, safe_stdout,
    selftest_config, wants_report_json, write_section,
)

safe_stdout()

DEFAULT_CONFIG = {"runs": []}

CONFIG_COMMENT = {
    "runs": ("[{'name': 'documents', 'command': ['uv','run','python','tools/verify_md.py',"
             "'--report-json','*.md'], 'tolerated': {'verify_md.py::CLAUDE.md::file length':"
             " 'why this one is allowed to fail'}}] - each verify run this project makes, "
             "with the failures it has DECLARED. A key is checker::document::check, exactly "
             "as the checker reports it; leave the middle empty for a checker with no "
             "per-document rows. THE COMMAND MUST CARRY " + REPORT_FLAG + " or the run is "
             "VOID: this script reads rows, not prose. Every tolerated key needs a reason - "
             "a blank one prints as a decision nobody made."),
}


def load_config(root: Path):
    return load_section(root, "expected", DEFAULT_CONFIG)


def run_checker(root: Path, command) -> tuple[dict | None, str]:
    """Run one declared command and return (parsed report, why-not).

    THE COMMAND IS A LIST, NEVER A STRING, so nothing here has to quote or split it - a
    shell splitting a path with a space in it is a failure mode this house does not need to
    own, and on Windows the shell would not expand a glob anyway. The checkers expand their
    own globs.
    """
    if not isinstance(command, list) or not command:
        return None, "the command is not a non-empty list"
    if REPORT_FLAG not in command:
        return None, (f"the command does not carry {REPORT_FLAG}, so it prints prose and "
                      f"there are no rows to judge")
    try:
        p = subprocess.run(command, cwd=root, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", stdin=subprocess.DEVNULL)
    except OSError as e:
        return None, f"the command could not be started - {e}"
    if p.returncode == RC_COULD_NOT_RUN:
        # VOID IS NOT A FAILING SET. A checker that could not look has nothing to compare,
        # and letting it be declared would turn "the instrument was broken" into a
        # permanent, silent exemption.
        return None, "the checker exited 2 - it could not run, so nothing can be declared"
    try:
        return json.loads(p.stdout), ""
    except json.JSONDecodeError as e:
        return None, (f"the output is not the JSON this reads - {e}. Check that "
                      f"{REPORT_FLAG} is the FIRST argument after the script path")


def failing_of(report: dict) -> set[str]:
    """The FAILING rows as keys, at whatever granularity the checker reported them.

    Built from the serialised rows rather than re-derived, so this script and the checker
    cannot disagree about what a key is. VOID and JUDGE are not failures and are excluded
    here for the same reason house_common's failing_keys() excludes them.
    """
    checker = report.get("checker", "")
    return {f"{checker}::{r.get('doc') or ''}::{r.get('check', '')}"
            for r in report.get("rows", []) if r.get("status") == FAIL}


def check_runs(rep: Report, root: Path, cfg) -> None:
    runs = cfg.get("runs") or []
    if not runs:
        for name in ("every failure is declared", "every declaration still fails",
                     "every toleration states a reason"):
            rep.record(name, 0, [], na_reason="no verify run is declared for this project")
        return

    undeclared, stale, unreasoned, void = [], [], [], []
    judged = 0
    for entry in runs:
        label = entry.get("name") or " ".join(entry.get("command", []))[:40]
        tolerated = entry.get("tolerated") or {}
        for key, reason in tolerated.items():
            if not str(reason).strip():
                unreasoned.append(f"{label}: {key} is tolerated with no reason given")
        report, why = run_checker(root, entry.get("command"))
        if report is None:
            void.append(f"{label}: {why}")
            continue
        judged += 1
        failing = failing_of(report)
        declared = set(tolerated)
        for key in sorted(failing - declared):
            undeclared.append(f"{label}: {key} FAILED and is not declared")
        for key in sorted(declared - failing):
            stale.append(f"{label}: {key} is declared as failing and now PASSES - the "
                         f"exemption is stale, and a stale one absorbs the next real "
                         f"regression in that file")

    void_reason = "; ".join(void) if void else None
    rep.record("every failure is declared", judged, undeclared, void_reason=void_reason)
    rep.record("every declaration still fails", judged, stale, void_reason=void_reason)
    rep.record("every toleration states a reason",
               sum(len(e.get("tolerated") or {}) for e in runs), unreasoned)


def main(argv) -> int:
    root = Path.cwd()
    if "--write-config" in argv:
        write_section(root, "expected", DEFAULT_CONFIG, CONFIG_COMMENT)
        return RC_OK
    if argv and argv[0] == "--selftest":
        return selftest()

    quiet = wants_report_json(argv)
    cfg = load_config(root)
    rep = Report()
    check_runs(rep, root, cfg)
    seen = rep.statuses()
    if all(s == NA for s in seen):
        rc = RC_COULD_NOT_RUN
    elif any(s == VOID for s in seen):
        rc = RC_COULD_NOT_RUN
    else:
        rc = RC_FAILED if any(s == FAIL for s in seen) else RC_OK
    if not quiet:
        print(rep.render(name_width=34))
        print(f"\n{len(rep.rows)} checks")
        print("OVERALL: " + rep.verdict())
        if rc == RC_COULD_NOT_RUN and all(s == NA for s in seen):
            print("VOID: nothing was declared. Either declare this project's verify runs, "
                  "or record in CLAUDE.md that it has no permanent exemption.")
    return finish(rep, "verify_expected.py", rc, quiet)


# ------------------------------------------------------------------------------ selftest

# A STAND-IN CHECKER, so the wrapper's logic is tested without a real one. Using a real
# checker would make these cases depend on that checker's findings, which change - and a
# suite that fails when something unrelated changes is a suite people stop reading.
FAKE = '''import json, sys
rows = json.loads(sys.argv[2])
print(json.dumps({"checker": "fake.py", "row_verdict": "x",
                  "exit_code": int(sys.argv[3]), "judge_claims": 0, "rows": rows}))
raise SystemExit(int(sys.argv[3]))
'''

PROSE = '''print("OVERALL: FAIL - this one prints prose, like a checker without the flag")
raise SystemExit(1)
'''


def _fake(tmp: Path, name: str, body: str) -> Path:
    tmp.mkdir(parents=True, exist_ok=True)
    f = tmp / name
    f.write_bytes(body.encode("utf-8"))
    return f


def _cmd(script: Path, rows, rc: int):
    return [sys.executable, str(script), REPORT_FLAG, json.dumps(rows), str(rc)]


def _row(check, status, doc=None):
    return {"doc": doc, "check": check, "status": status, "examined": 1, "problems": []}


def _probe(idx):
    def run(built):
        cfg, root = built
        rep = Report()
        check_runs(rep, root, cfg)
        return rep.statuses()[idx]
    return run


def _cases(tmp: Path):
    declared, stale_row, reasons = _probe(0), _probe(1), _probe(2)
    fake = _fake(tmp, "fake.py", FAKE)
    prose = _fake(tmp, "prose.py", PROSE)
    one_fail = [_row("file length", FAIL, "CLAUDE.md"), _row("tables", PASS, "CLAUDE.md")]
    all_pass = [_row("file length", PASS, "CLAUDE.md"), _row("tables", PASS, "CLAUDE.md")]
    key = "fake.py::CLAUDE.md::file length"

    def cfg(rows, rc, tolerated):
        return lambda t: ({"runs": [{"name": "r", "command": _cmd(fake, rows, rc),
                                     "tolerated": tolerated}]}, tmp)

    return [
        # THE OBVIOUS HALF: something failed that nobody declared.
        Case("an UNDECLARED failure", declared,
             cfg(one_fail, 1, {}), cfg(one_fail, 1, {key: "declared, with a reason"})),
        # THE HALF THAT MATTERS: the declaration is still there and the thing now passes.
        # A stale exemption absorbs the next real regression in that file, so it is a
        # finding in its own right - which is what "both ways" means.
        Case("a STALE declaration that now passes", stale_row,
             cfg(all_pass, 0, {key: "declared, with a reason"}),
             cfg(all_pass, 0, {})),
        Case("a toleration with a blank reason", reasons,
             cfg(one_fail, 1, {key: "   "}), cfg(one_fail, 1, {key: "a real reason"})),
        # A CHECKER THAT COULD NOT RUN IS VOID, NEVER A TOLERATED FAILURE.
        Case("a checker that exited 2 is VOID", declared,
             cfg(one_fail, 2, {key: "declared"}),
             cfg(one_fail, 1, {key: "declared"}), want=VOID),
        # The flag is what makes rows available at all; without it there is prose to parse.
        Case("a command without the flag is VOID", declared,
             lambda t: ({"runs": [{"name": "r", "command": [sys.executable, str(prose)],
                                   "tolerated": {}}]}, tmp),
             cfg(one_fail, 1, {key: "declared"}), want=VOID),
        Case("nothing declared is N/A, never a pass", declared,
             cfg(one_fail, 1, {}), lambda t: ({"runs": []}, tmp), good_want=NA),
    ]


def _assert_exact_both_ways(tmp: Path) -> bool:
    """THE ACCEPTANCE: the SAME run that a bare checker FAILS is PASSED once judged.

    This is the whole point of the script and no single case row can state it - it is a
    claim about two different readings of one run. The bare checker exits 1 for ever
    because of a declared exemption, which is why the cycle gate could never record it;
    judged against the declaration, the same run is a PASS and becomes recordable.
    """
    fake = _fake(tmp, "fake.py", FAKE)
    rows = [_row("file length", FAIL, "CLAUDE.md")]
    key = "fake.py::CLAUDE.md::file length"
    bare = subprocess.run(_cmd(fake, rows, 1), cwd=tmp, capture_output=True, text=True, encoding="utf-8", errors="replace")
    rep = Report()
    check_runs(rep, tmp, {"runs": [{"name": "r", "command": _cmd(fake, rows, 1),
                                    "tolerated": {key: "declared, with a reason"}}]})
    judged = rep.exit_code
    good = bare.returncode == RC_FAILED and judged == RC_OK
    print(f"\n  {'OK  ' if good else 'MISS'} the same run: bare={bare.returncode} (FAIL), "
          f"judged={judged} (PASS)"
          f"{'' if good else '  (the two readings are not differing)'}")
    return good


def selftest() -> int:
    print("SELFTEST - each check must fire on a bad input AND stay quiet on a good one")
    print()
    tmp = Path(tempfile.mkdtemp(prefix="verify_expected_selftest_"))
    try:
        ok, paired, unpaired = run_cases(_cases(tmp), tmp, width=42)
        report_pairing(paired, unpaired)
        ok &= selftest_config(tmp, "expected", "runs", load_config, width=42)
        ok &= _assert_exact_both_ways(tmp)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print()
    print("SELFTEST: " + ("PASS" if ok else "FAIL"))
    return RC_OK if ok else RC_FAILED


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
