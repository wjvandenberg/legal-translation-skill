#!/usr/bin/env python3
"""check_checkers.py - is this project's copy of each standard script current?
CHECKER VERSION 6 (2026-08-19)

Every project gets its OWN COPY of the standard scripts in its tools\\ folder. Copies drift:
the shared one gets fixed and yours does not hear about it, or yours gets edited and the fix
never travels back. Three very different situations look identical from the outside:

    * someone changed this copy on purpose, for a good project-specific reason
    * the shared copy moved on and this one is simply out of date
    * someone edited it carelessly and told nobody

This script tells them apart. Run it from a project root:

    uv run python tools/check_checkers.py
    uv run python tools/check_checkers.py --selftest

VERDICTS, one per file:
    CURRENT   byte-identical to the shared copy - nothing to do
    STALE     the shared copy has a higher CHECKER VERSION - re-copy it
    FORKED    locally changed AND the reason is recorded in a header - fine, a decision
    DIVERGED  locally changed with NO recorded reason - a finding, not a decision
    ABSENT    the shared folder has it, this project does not - fine if deliberate
    UNKNOWN   present in both but neither declares a CHECKER VERSION

A FORK IS DECLARED BY A HEADER LINE, the same discipline as a house contract template
amended for one counterparty - you note on the amended copy that it is amended and why:

    # FORKED FROM standard-scripts v2 ON 2026-08-20 BECAUSE this project's fixtures are
    # intentionally not UTF-8, so the encoding check has to be relaxed here.

Exit 0 if every file is CURRENT, FORKED or a declared ABSENT. Exit 1 on STALE, DIVERGED or
an undeclared absence - those need a decision from a person. Exit 2 when the comparison
COULD NOT RUN at all, because no tracked script was found to compare against - which is
not the same fact as having compared them and found nothing wrong.
"""
from __future__ import annotations

import argparse
import hashlib
import os
import re
import shutil
import sys
import tempfile
from pathlib import Path

# THE ONE THING DELIBERATELY DUPLICATED FROM house_common.py, AND THE REASON IT HAS TO BE.
# A report that crashes on a character the terminal's codepage cannot encode reports nothing
# - and this script must keep running when house_common.py is ABSENT, because reporting that
# absence is its job. Importing the shared guard would mean an ImportError instead of the
# finding. Four lines, declared here rather than shared: see CHANGELOG.md.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Scripts a project is expected to hold a copy of, and to keep in step. README is
# documentation, not a checker. new_charter.py is deliberately absent too: it is a
# GENERATOR run once at kickoff, not a control a project keeps running, so a project has
# no reason to hold a copy and drift in it cannot weaken any check. It carries a CHECKER
# VERSION anyway, so the roster in TEMPLATE-CHANGELOG.md can quote one that is real.
# review_scripts.py is absent for the same reason and one more: it reviews the SHARED
# folder only, so a copy of it inside a project would have nothing to review.
#
# house_common.py IS tracked, and it is the one entry that is not a checker. Every checker
# imports it, so a project holding verify_md.py without it has a checker that cannot start
# at all. That has to surface here as ABSENT - a decision a person makes - rather than as an
# ImportError at the moment someone finally runs the checks.
TRACKED = ["house_common.py", "verify_md.py", "verify_code.py", "verify_deliverable.py",
           "check_checkers.py", "run_tests.py"]


def default_shared() -> Path:
    """Find the shared folder WITHOUT hardcoding a machine path.

    This file is COPIED into project repos, and some of those repos are public - so an
    absolute path here publishes a username and a directory layout, and breaks on any other
    machine. Same rule as every pattern list in this house: the tool ships, the location does
    not.

    Order: an explicit HOUSE_SCRIPTS_DIR, then a folder named 'standard-scripts' found by
    walking up from wherever this file sits - checked BOTH as a direct child of each parent
    and one level down under 'templates', because the shared folder lives inside the
    template repository so that both can be committed and pushed as one thing.

    That second candidate is not defensive coding, it is the fix for a real break: with the
    scripts at <root>/templates/standard-scripts/, a project at <root>/myproject/tools/
    walks up through myproject and <root> and finds no 'standard-scripts' child at either.
    The lookup silently fell back to the file's own directory and every comparison became
    a file against itself.

    AND A CANDIDATE MUST CONTAIN A CHECKER, NOT MERELY CARRY THE RIGHT NAME. Matching on
    the name alone is how an emptied folder left behind by a move SHADOWS the real one:
    measured here, an old <root>/standard-scripts/ that had been moved out from under
    won the name match, held no checkers, and the run reported VOID. Exit 2 was the right
    answer to the wrong folder, which is the worst kind of correct.
    """
    env = os.environ.get("HOUSE_SCRIPTS_DIR")
    if env:
        return Path(env)
    here = Path(__file__).resolve()
    for parent in here.parents:
        for candidate in (parent / "standard-scripts",
                          parent / "templates" / "standard-scripts"):
            if candidate.is_dir() and any((candidate / n).is_file() for n in TRACKED):
                return candidate
    return here.parent


SHARED_DEFAULT = default_shared()
VERSION_RE = re.compile(r"CHECKER VERSION\s+(\d+)")
FORK_RE = re.compile(r"^#\s*FORKED FROM\s+\S+\s+v(\d+)\s+ON\s+(\S+)\s+BECAUSE\s+(.+)$",
                     re.I | re.M)

CURRENT, STALE, FORKED, DIVERGED, ABSENT, UNKNOWN = (
    "CURRENT", "STALE", "FORKED", "DIVERGED", "ABSENT", "UNKNOWN")
FAILING = {STALE, DIVERGED, UNKNOWN}


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def version_of(text: str):
    m = VERSION_RE.search(text)
    return int(m.group(1)) if m else None


def classify(local: Path, shared: Path, declared_absent):
    """Return (verdict, detail)."""
    if not shared.exists():
        return None, None                      # not a tracked script here
    if not local.exists():
        if local.name in declared_absent:
            return ABSENT, "declared not needed by this project"
        return ABSENT, "shared folder has it, this project does not - declare it or copy it"
    if sha(local) == sha(shared):
        return CURRENT, ""
    lt, st = local.read_text(encoding="utf-8", errors="replace"), \
        shared.read_text(encoding="utf-8", errors="replace")
    lv, sv = version_of(lt), version_of(st)
    fork = FORK_RE.search(lt)
    if fork:
        return FORKED, f"from v{fork.group(1)} on {fork.group(2)}: {fork.group(3)[:60]}"
    if lv is None or sv is None:
        return UNKNOWN, "differs, and no CHECKER VERSION on one side - cannot judge"
    if sv > lv:
        return STALE, f"local v{lv}, shared v{sv} - re-copy from the shared folder"
    if lv > sv:
        return DIVERGED, (f"local v{lv} is AHEAD of shared v{sv} - a fix was made here and "
                          "never promoted. Promote it or declare the fork")
    return DIVERGED, (f"same version (v{lv}) but different content - an undeclared local "
                      "edit. Record why, or re-copy")


def run(project: Path, shared: Path, declared_absent):
    rows = []
    for name in TRACKED:
        v, d = classify(project / "tools" / name, shared / name, declared_absent)
        if v is not None:
            rows.append((name, v, d))
    return rows


def report(rows):
    if not rows:
        print("VOID: no tracked scripts found in the shared folder. Is --shared correct?")
        return 2      # could not run, which is not the same as having found a problem
    width = max(len(n) for n, _, _ in rows)
    bad = 0
    for name, verdict, detail in rows:
        flag = "  " if verdict not in FAILING else "! "
        print(f"{flag}{verdict:<9} {name:<{width}}  {detail}")
        if verdict in FAILING:
            bad += 1
    print(f"\n{len(rows)} tracked, {bad} needing a decision")
    if bad:
        print("\nSTALE    -> copy the shared file over this project's copy.")
        print("DIVERGED -> either promote the fix to the shared folder (see the four")
        print("            questions in standard-scripts\\README.md) or declare the fork")
        print("            with a '# FORKED FROM ... BECAUSE ...' header.")
    return 1 if bad else 0


# -------------------------------------------------------------------------- selftest

def selftest() -> int:
    print("SELFTEST - every verdict must be reachable\n")
    ok = True
    tmp = Path(tempfile.mkdtemp(prefix="check_checkers_selftest_"))
    try:
        shared = tmp / "shared"
        tools = tmp / "proj" / "tools"
        shared.mkdir(parents=True)
        tools.mkdir(parents=True)

        def w(p: Path, body: str):
            p.write_text(body, encoding="utf-8")

        # shared copies, all at v2
        for n in TRACKED:
            w(shared / n, f'"""{n} CHECKER VERSION 2"""\nprint("hi")\n')

        # CURRENT - identical
        shutil.copy(shared / "verify_md.py", tools / "verify_md.py")
        # STALE - local is v1
        w(tools / "verify_code.py", '"""verify_code.py CHECKER VERSION 1"""\nprint("hi")\n')
        # FORKED - declared
        w(tools / "verify_deliverable.py",
          '# FORKED FROM standard-scripts v2 ON 2026-08-20 BECAUSE fixtures are not UTF-8\n'
          '"""verify_deliverable.py CHECKER VERSION 2"""\nprint("changed")\n')
        # DIVERGED - same version, different content, no header
        w(tools / "check_checkers.py",
          '"""check_checkers.py CHECKER VERSION 2"""\nprint("secretly edited")\n')

        rows = dict((n, v) for n, v, _ in run(tmp / "proj", shared, set()))
        expect = {"verify_md.py": CURRENT, "verify_code.py": STALE,
                  "verify_deliverable.py": FORKED, "check_checkers.py": DIVERGED}
        for n, want in expect.items():
            got = rows.get(n)
            good = got == want
            ok &= good
            print(f"  {'OK  ' if good else 'MISS'} {n:<24} expected {want:<9} got {got}")

        # ABSENT, undeclared then declared
        (tools / "verify_md.py").unlink()
        got = dict((n, v) for n, v, _ in run(tmp / "proj", shared, set()))["verify_md.py"]
        good = got == ABSENT
        ok &= good
        print(f"  {'OK  ' if good else 'MISS'} {'missing file':<24} expected {ABSENT:<9} got {got}")
        rows2 = run(tmp / "proj", shared, {"verify_md.py"})
        declared_fails = sum(1 for n, v, _ in rows2 if n == "verify_md.py" and v in FAILING)
        good = declared_fails == 0
        ok &= good
        print(f"  {'OK  ' if good else 'MISS'} {'declared absence passes':<24} "
              f"failing={declared_fails} (want 0)")

        # a run with nothing tracked must be VOID, not a silent pass - and VOID exits 2,
        # because "could not run" is a different fact from "found a problem"
        empty = tmp / "empty"
        empty.mkdir()
        rc = report(run(tmp / "proj", empty, set()))
        good = rc == 2
        ok &= good
        print(f"  {'OK  ' if good else 'MISS'} {'empty shared folder is VOID':<24} rc={rc} (want 2)")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print("\nSELFTEST: " + ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


def main(argv=None):
    p = argparse.ArgumentParser(description="Compare this project's checker copies "
                                            "against the shared standard scripts.")
    p.add_argument("--shared", default=str(SHARED_DEFAULT),
                   help="the shared standard-scripts folder")
    p.add_argument("--project", default=".", help="project root (expects a tools/ folder)")
    p.add_argument("--absent", default="",
                   help="comma-separated scripts this project deliberately does not use")
    p.add_argument("--selftest", action="store_true")
    args = p.parse_args(argv)
    if args.selftest:
        return selftest()
    declared = {s.strip() for s in args.absent.split(",") if s.strip()}
    return report(run(Path(args.project), Path(args.shared), declared))


if __name__ == "__main__":
    sys.exit(main())
