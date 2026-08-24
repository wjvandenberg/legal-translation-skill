#!/usr/bin/env python3
"""run_tests.py - one command that runs everything this project tests with.
CHECKER VERSION 2 (2026-08-21)

VERIFY asks "did this change do what it claimed?". TEST asks "did anything else break?".
This is the second one, and it exists so that question has a single answer rather than a
folder of commands someone has to remember.

    uv run python tools/run_tests.py             # run everything, report each suite
    uv run python tools/run_tests.py --list      # what would run, without running it
    uv run python tools/run_tests.py --quiet     # exit code only - for git bisect
    uv run python tools/run_tests.py --selftest
    uv run python tools/run_tests.py --write-config

WHY --quiet EXISTS. `git bisect` needs a cheap, deterministic pass/fail test it can run at
every commit without a human reading anything. Output is what makes a test suite unusable
for that, so this mode prints nothing and says everything in the exit code.

THIS SUITE MAKES NO QUALITY JUDGEMENT, and that is deliberate rather than a gap. It reports
whether each suite RAN and whether it PASSED. The moment it starts scoring how good the
output is, it stops being repeatable - and a suite that is not repeatable cannot serve as
the never-regress gate, which is the whole reason for having one.

EVERY SUITE REPORTS ITS DENOMINATOR. A configured suite that matched no tests is VOID, not
a pass. A run with no suites at all is VOID and exits 2: "there was nothing to test" and
"nothing was broken" are different facts.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from house_common import (                                       # noqa: E402
    FAIL, NA, PASS, RC_COULD_NOT_RUN, RC_FAILED, RC_OK, VOID, Case, Report,
    load_section, report_pairing, run_cases, selftest_config, write_section,
)

DEFAULT_CONFIG = {
    "suites": [],
    "selftest_globs": ["tools/*.py"],
    "timeout_seconds": 900,
    "stop_on_first_failure": False,
}

CONFIG_COMMENT = {
    "suites": "[{'name': 'smoke', 'command': 'uv run python tests/smoke_test.py'}] - the project's own suites, in the order they should run.",
    "selftest_globs": "Scripts whose --selftest counts as a suite. The house checkers are found by this, so a broken checker fails the test run.",
    "timeout_seconds": "Per suite. A hung suite is a failure, not a wait.",
    "stop_on_first_failure": "false runs everything and reports all of it - usually what you want. true is for a long suite you are iterating on.",
}


def discover(root: Path, cfg):
    """Every suite this project has: the configured ones, then every --selftest found.

    A checker's own --selftest is a test of this project, not a formality: if a checker
    stops being able to fail, every result it has ever reported becomes unfalsifiable.
    """
    out = [(s["name"], s["command"]) for s in cfg["suites"]]
    seen = set()
    for g in cfg["selftest_globs"]:
        for p in sorted(root.glob(g)):
            if p.name.startswith("_") or p in seen:
                continue
            body = p.read_text(encoding="utf-8", errors="replace")
            if "--selftest" in body:
                seen.add(p)
                rel = p.relative_to(root).as_posix()
                out.append((f"{p.stem} --selftest",
                            f'{sys.executable} "{rel}" --selftest'))
    return out


# Substrings that mark a line as saying WHAT went wrong. Deliberately broad: showing a line
# that turns out to be fine costs three seconds of reading, and hiding the only line that
# explains a failure costs a session.
FAILURE_MARKS = ("MISS", "FAIL", "ERROR", "Traceback", "AssertionError", "VOID", "!")


def diagnostic(text: str, limit: int):
    """The lines that say WHAT failed - not merely the LAST lines.

    A TAIL IS THE WRONG SELECTION, and this is a fix rather than a preference. A suite that
    prints one line per check puts its failures in the MIDDLE: the last lines are the trailing
    passes and the summary. So a tail reports "this suite failed" and hides every reason,
    which is the most expensive kind of report - it is believed, and it is useless. Measured:
    a real MISS was invisible in a six-line tail while the run said only that something failed.

    Marker lines win; the tail is the fallback when nothing matches, because an unrecognised
    output shape must still show something. The LAST line is always kept - it is usually the
    verdict - and anything dropped is COUNTED OUT LOUD, since silent truncation is what made
    the original wrong.
    """
    lines = text.strip().splitlines()
    if not lines:
        return []
    hits = [ln for ln in lines if any(m in ln for m in FAILURE_MARKS)]
    chosen = hits if hits else lines[-limit:]
    if lines[-1] not in chosen:                       # the verdict line, always
        chosen = chosen + [lines[-1]]
    shown, hidden = chosen[:limit], len(chosen) - limit
    out = [f"  {ln}" for ln in shown]
    if hidden > 0:
        out.append(f"  ... {hidden} more line(s) not shown - run this suite directly")
    return out


def run_suite(root: Path, name, command, timeout):
    try:
        r = subprocess.run(command, shell=True, cwd=root, capture_output=True,
                           text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return FAIL, [f"timed out after {timeout}s"]
    except OSError as e:
        return VOID, [f"could not start: {e}"]
    if r.returncode == RC_COULD_NOT_RUN:
        return VOID, ["exit 2 - the suite could not run"] + \
            diagnostic(r.stdout + r.stderr, 6)
    if r.returncode != 0:
        return FAIL, [f"exit {r.returncode}"] + diagnostic(r.stdout + r.stderr, 12)
    return PASS, []


def main(argv):
    root = Path.cwd()
    if "--write-config" in argv:
        write_section(root, "tests", DEFAULT_CONFIG, CONFIG_COMMENT)
        return RC_OK
    if "--selftest" in argv:
        return selftest()

    cfg = load_section(root, "tests", DEFAULT_CONFIG)
    quiet = "--quiet" in argv
    suites = discover(root, cfg)

    if "--list" in argv:
        for name, command in suites:
            print(f"  {name:<32} {command}")
        print(f"\n{len(suites)} suite(s)")
        return RC_OK if suites else RC_COULD_NOT_RUN

    if not suites:
        if not quiet:
            print("VOID: no suites configured and no --selftest found. Either declare "
                  "suites under 'tests' in verify.config.json, or record in CLAUDE.md "
                  "why this project has none. A run that tested nothing has not passed.")
        return RC_COULD_NOT_RUN

    rep = Report()
    for name, command in suites:
        status, problems = run_suite(root, name, command, cfg["timeout_seconds"])
        rep.add(name, status, 1, problems)
        if status == FAIL and cfg["stop_on_first_failure"]:
            rep.add("(remaining suites)", NA, 0, ["stopped at the first failure"])
            break

    if quiet:
        return rep.exit_code

    print(rep.render(name_width=34))
    print(f"\n{len(suites)} suite(s) run")
    print("OVERALL: " + rep.verdict())
    # THE CAVEAT ONLY APPLIES TO A PASS, and printing it after a FAIL asserted something
    # false: "every suite RAN and PASSED" under OVERALL: FAIL. A report that contradicts the
    # verdict three lines above it teaches the reader to skip the report.
    if rep.exit_code == RC_OK:
        print("\nThis says every suite RAN and PASSED. It says nothing about whether the "
              "output is any good -\nthat judgement is not repeatable, and a suite that is "
              "not repeatable cannot be a gate.")
    else:
        print("\nA suite above did not pass. The lines under it are the ones that SAY WHY, "
              "picked out of\nthe output rather than taken from its end - re-run that suite "
              "directly for the whole of it.")
    return rep.exit_code


# -------------------------------------------------------------------------- selftest

def _script(tmp: Path, name, code):
    d = tmp / "tools"
    d.mkdir(parents=True, exist_ok=True)
    (d / name).write_text(code, encoding="utf-8")
    return tmp


PASSING = 'import sys\nif "--selftest" in sys.argv:\n    sys.exit(0)\n'
FAILING = 'import sys\nif "--selftest" in sys.argv:\n    sys.exit(1)\n'
CANNOT_RUN = 'import sys\nif "--selftest" in sys.argv:\n    sys.exit(2)\n'


def probe(built):
    """Run the whole thing over a built project and give back the first suite's status."""
    cfg = dict(DEFAULT_CONFIG)
    suites = discover(built, cfg)
    if not suites:
        return VOID
    status, _ = run_suite(built, *suites[0], 120)
    return status


def selftest() -> int:
    print("SELFTEST - a runner that cannot report a failure is worse than no runner")
    print()
    import shutil
    import tempfile
    ok = True
    tmp = Path(tempfile.mkdtemp(prefix="run_tests_selftest_"))
    try:
        cases = [
            Case("a failing suite is FAIL", probe,
                 lambda t: _script(t / "bad", "t_one.py", FAILING),
                 lambda t: _script(t / "good", "t_one.py", PASSING)),
            Case("exit 2 is VOID, not FAIL", probe,
                 lambda t: _script(t / "void", "t_one.py", CANNOT_RUN),
                 lambda t: _script(t / "good2", "t_one.py", PASSING),
                 want=VOID),
        ]
        cok, paired, unpaired = run_cases(cases, tmp, width=34)
        ok &= cok
        report_pairing(paired, unpaired)

        # THE SELECTION OF DIAGNOSTIC LINES, proved on the shape that defeated the tail.
        # A per-check suite puts its failures in the middle; a tail shows the trailing
        # passes and the verdict, and reports a failure with none of its reasons.
        middle = "\n".join(["OK   check one", "MISS check two is the real defect"]
                           + [f"OK   check {i}" for i in range(3, 12)] + ["SELFTEST: FAIL"])
        got = diagnostic(middle, 12)
        checks = [
            ("the MISS in the middle is shown",
             any("MISS check two" in ln for ln in got)),
            ("the verdict line is kept",
             any("SELFTEST: FAIL" in ln for ln in got)),
            ("the trailing passes are dropped",
             not any("OK   check 9" in ln for ln in got)),
            # the fallback still has to show something for an unrecognised shape
            ("no marker: falls back to the tail",
             diagnostic("\n".join(f"line {i}" for i in range(20)), 3)
             == ["  line 17", "  line 18", "  line 19"]),
            # and truncation must be announced, because silent truncation caused the bug
            ("dropped lines are counted out loud",
             any("not shown" in ln for ln in
                 diagnostic("\n".join(f"MISS {i}" for i in range(20)), 4))),
            ("empty output yields no lines", diagnostic("   ", 6) == []),
        ]
        for label, good in checks:
            ok &= good
            print(f"  {'OK  ' if good else 'MISS'} {label}")

        # a project with nothing to test must be VOID and exit 2, never a silent pass
        empty = tmp / "empty"
        empty.mkdir()
        import os
        cwd = os.getcwd()
        try:
            os.chdir(empty)
            rc = main(["run_tests.py"])
        finally:
            os.chdir(cwd)
        good = rc == RC_COULD_NOT_RUN
        ok &= good
        print(f"  {'OK  ' if good else 'MISS'} {'nothing to test exits 2':<34} -> {rc}")

        # --quiet must print NOTHING and still carry the verdict, or git bisect cannot
        # use it - the one mode whose whole value is that it is silent
        import io
        from contextlib import redirect_stdout
        proj = _script(tmp / "q", "t_one.py", FAILING)
        buf = io.StringIO()
        try:
            os.chdir(proj)
            with redirect_stdout(buf):
                rc = main(["run_tests.py", "--quiet"])
        finally:
            os.chdir(cwd)
        silent = buf.getvalue() == ""
        good = silent and rc == RC_FAILED
        ok &= good
        print(f"  {'OK  ' if good else 'MISS'} {'--quiet is silent and still fails':<34} "
              f"-> printed={len(buf.getvalue())} chars, exit={rc}")

        ok &= selftest_config(tmp, "tests", "suites",
                              lambda d: load_section(d, "tests", DEFAULT_CONFIG), width=34)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print()
    print("SELFTEST: " + ("PASS" if ok else "FAIL"))
    return RC_OK if ok else RC_FAILED


if __name__ == "__main__":
    sys.exit(main(sys.argv))
