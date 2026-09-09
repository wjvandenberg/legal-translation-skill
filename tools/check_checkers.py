#!/usr/bin/env python3
"""check_checkers.py - is this project's copy of each standard script current?
CHECKER VERSION 14 (2026-09-02)

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
    ABSENT    the shared folder has it, this project does not, AND THAT WAS DECLARED - a
              decision somebody took, recorded where the next reader can see it
    MISSING   the shared folder has it, this project does not, and nothing says why - a
              finding, not a decision, and the same distinction FORKED draws against DIVERGED
    UNKNOWN   present in both but neither declares a CHECKER VERSION

ABSENT AND MISSING WERE ONE VERDICT UNTIL v12, AND THAT MADE THE DOCSTRING BELOW FALSE.
classify() returned the same ABSENT either way, so --absent changed the wording of a row and
nothing else: a project holding NONE of the tracked scripts reported "0 needing a decision"
and exited 0, while printing a row per script each saying "declare it or copy it". THE SUMMARY
CONTRADICTED ITS OWN ROWS - and a never-propagated project was indistinguishable from one
perfectly in step, which is the reading that matters when the whole point of a run is to find
out whether anything has arrived yet.

A FORK IS DECLARED BY A HEADER LINE, the same discipline as a house contract template
amended for one counterparty - you note on the amended copy that it is amended and why:

    # FORKED FROM standard-scripts v2 ON 2026-08-20 BECAUSE this project's fixtures are
    # intentionally not UTF-8, so the encoding check has to be relaxed here.

Exit 0 if every file is CURRENT, FORKED or a declared ABSENT. Exit 1 on STALE, DIVERGED,
MISSING or UNKNOWN - those need a decision from a person. Exit 2 when the comparison
COULD NOT RUN at all, because no tracked script was found to compare against - which is
not the same fact as having compared them and found nothing wrong.

TWO WAYS TO DECLARE AN ABSENCE, AND ONLY ONE OF THEM CAN CARRY THE REASON.

    --absent name.py,other.py          ad-hoc, for one run
    verify.config.json                 durable, and it REQUIRES a reason per entry

        "checkers": {
          "declared_absent": {
            "auto_mode.py":       "this project runs no unattended chain",
            "auto_mode_guard.py": "declared with the counter - it cannot start without it"
          }
        }

The two are a UNION: the config is the standing decision, --absent adds to it for a single
run, and neither overrides the other.

A BLANK REASON IS REFUSED, AND THE FILE STAYS MISSING. That is the whole point of putting
declarations in a file: a command line cannot hold a reason, so until v13 the reason for
every absence lived in a document no script read, and the distinction between ABSENT and
MISSING rested on something unenforceable. An entry with an empty reason is not a quieter
declaration - it is a decision nobody made, and it reads afterwards exactly like one
somebody did. (Same rule, and the same wording, as run_tests.py's entry_points_exempt.)

A STALE DECLARATION IS A FINDING TOO, IN THE OTHER DIRECTION. If a script is declared
absent and the project HAS it, the declaration has outlived its reason - and a stale
exemption is not inert: it silently absorbs the next real change to that file, because
nobody rereads a line that never fires. Both directions, or the mechanism only works while
somebody remembers to maintain it.

THE ROSTER ARM, --roster, AND WHY IT IS HERE RATHER THAN IN A CROSS-DOCUMENT CHECKER.
Somewhere a document lists the scripts and the version of each - a charter's checker
roster, a changelog's. That list is a SECOND place recording what the docstrings already
say, and it is kept in step by memory alone:

    uv run python tools/check_checkers.py --roster ../TEMPLATE-CHANGELOG.md

Measured in the house that wrote this: such a roster had gone stale SEVEN times, and five
of the seven were found only when somebody retyped the whole list from scratch. One
staleness ran for days with the list naming THREE scripts against a folder holding sixteen.

IT IS NOT A CROSS-DOCUMENT CHECK, WHICH IS THE WHOLE REASON IT LIVES HERE. A cross-document
checker compares a document to another DOCUMENT; this compares a document to the FOLDER -
the derived kind, which that checker excludes by design. This script already reads every
docstring's CHECKER VERSION and already locates the folder, so the arm is an addition
rather than a new instrument.

    ROSTER OK       named, and the version matches the docstring
    ROSTER WRONG    named at a version the docstring does not carry - the drift
    ROSTER UNLISTED a script the folder holds and the roster never mentions
    ROSTER GHOST    a script the roster names and the folder does not have

THE REGION IS DELIMITED, AND AN ABSENT DELIMITER IS VOID RATHER THAN CLEAN. The roster
document also DISCUSSES past versions in prose - "verify_md.py stood at v18 against v19" -
and a scan of the whole file would read those as roster rows and report drift that is only
history. So the list sits between two marker lines, and a file without them cannot be
judged at all:

    <!-- ROSTER:BEGIN -->  ... the list ...  <!-- ROSTER:END -->

Without --roster the arm prints N/A and says so. It never silently does not run: a check
that opened no file is VOID, never CLEAN.
"""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import io
import json
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
# AUTO MODE'S TWO FILES ARE TRACKED FOR THE REASON house_common.py IS: a project holding the
# guard without the counter has a guard that CANNOT START, because the guard imports the
# counter's state reader - and a control that cannot start is the one failure that must never
# be a surprise at the worst moment. A project that never runs an unattended chain DECLARES
# the two - '--absent auto_mode.py,auto_mode_guard.py' - and passes.
# THAT SENTENCE USED TO READ "ABSENT is not a failing verdict, so a project ... simply reports
# two absent files and passes", AND THE REASONING WAS SOUND FOR TWO FILES OF TWELVE. It was
# never asked at TWELVE of twelve - the population propagating this house's regime creates on
# its first day in a new project - where the same silence reports a project that has received
# nothing as one needing no decision. The cost of the change is a one-off declaration; the
# cost of leaving it was an instrument that could not tell arrival from completion.
#
# verify_crossdoc.py IS TRACKED, AND THE TEST WAS ALREADY WRITTEN DOWN. trace_instructions.py
# is deliberately NOT in this list because it is an INSTRUMENT A PERSON READS, and the
# recorded reason says the accepted cost of an unreported drift is "tolerable for an
# instrument a person reads, NOT FOR A CHECKER THAT GATES". verify_crossdoc gates - it exits
# 1 on a disagreement - so the same sentence puts it in.
#
# verify_refs.py AND cycle_evidence.py JOIN ON THAT SAME SENTENCE, 2026-08-31 - and the
# second of the two is a CLASS fix, not a by-product. cycle_evidence.py was adopted on
# 2026-08-27 and its changelog entry says nothing at all about tracking; it gates, since its
# `check` exits 1 and refuses a commit, so the recorded test puts it in and silence is what
# left it out. Adding only the script this session happened to write would have been fixing
# the caller that bit and leaving caller N+1 carrying the same gap - which is how the next
# one surfaces later as an unconnected bug. A project holding neither DECLARES both and
# passes - see the note above on why a declaration is now required rather than optional.
# verify_confidential.py JOINS ON THAT SAME SENTENCE, 2026-09-02. It GATES - exit 1 on a
# forbidden phrase in a tracked file or in a repository's history - so the recorded test puts
# it in, and the accepted cost of an unreported drift ("tolerable for an instrument a person
# reads, NOT FOR A CHECKER THAT GATES") does not apply. It is also the entry whose drift
# matters most: a confidentiality scanner that has silently fallen behind reports CLEAN.
TRACKED = ["house_common.py", "verify_md.py", "verify_code.py", "verify_deliverable.py",
           "verify_crossdoc.py", "verify_refs.py", "verify_expected.py",
           "verify_confidential.py", "cycle_evidence.py", "check_checkers.py",
           "run_tests.py", "auto_mode.py", "auto_mode_guard.py"]


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

CURRENT, STALE, FORKED, DIVERGED, ABSENT, MISSING, UNKNOWN = (
    "CURRENT", "STALE", "FORKED", "DIVERGED", "ABSENT", "MISSING", "UNKNOWN")
# MISSING JOINED THIS SET IN v12, AND THE PAIR IT COMPLETES IS THE ARGUMENT FOR IT. An absence
# and a declared absence are as different as DIVERGED and FORKED, and that pair has always been
# split here: one is a finding, the other is a decision with its reason on the record. Absence
# was the one place this script asked for a declaration and then ignored whether it got one.
FAILING = {STALE, DIVERGED, MISSING, UNKNOWN}


CONFIG_NAME = "verify.config.json"
CLI_REASON = "declared on the command line for this run (no reason recorded)"


def read_declared_absent(project: Path):
    """Return ({name: reason}, [(name, why refused)]) from the project's config.

    THE SECOND RETURN VALUE IS THE POINT. An entry whose reason is blank is NOT quietly
    dropped, because a dropped entry is indistinguishable from one nobody wrote: it comes
    back as a refusal the report prints, and the file stays MISSING.

    READ WITH 'utf-8-sig', WHICH STRIPS A BYTE-ORDER MARK AND IS IDENTICAL TO 'utf-8' WHEN
    THERE IS NONE. Windows PowerShell writes that mark by default, so a config created the
    most obvious way on this platform is not malformed to a person and is malformed to
    json.loads.

    AND THE PARSING IS DUPLICATED FROM house_common.py DELIBERATELY, for the same reason
    the stdout guard above is: this script must keep running when house_common.py is the
    very file that is ABSENT, and importing it would turn that finding into an ImportError.
    A malformed or unreadable config degrades to NO DECLARATIONS rather than raising - the
    conservative direction, since the effect is that absences FAIL rather than pass.
    """
    f = project / CONFIG_NAME
    if not f.is_file():
        return {}, []
    try:
        raw = json.loads(f.read_text(encoding="utf-8-sig"))
    except (json.JSONDecodeError, OSError):
        return {}, [("(the config itself)", f"{f.name} could not be parsed - no declaration "
                                            f"in it counts, so absences FAIL rather than pass")]
    section = raw.get("checkers") or {}
    entries = section.get("declared_absent") or {}
    if not isinstance(entries, dict):
        return {}, [("(the config itself)", "'checkers.declared_absent' is not an object of "
                                            "{name: reason} - no declaration in it counts")]
    declared, refused = {}, []
    for name, reason in entries.items():
        text = reason.strip() if isinstance(reason, str) else ""
        if not text:
            refused.append((name, "declared absent with NO REASON - refused, so it is still "
                                  "MISSING. A blank reason prints as a decision nobody made"))
            continue
        declared[name] = text
    return declared, refused


def stale_declarations(project: Path, shared: Path, declared):
    """Names declared absent that the project actually HAS - the other direction.

    A declaration that has outlived its reason is not inert. Nobody rereads a line that
    never fires, so it sits there absorbing the next real change to that file.
    """
    out = []
    for name in sorted(declared):
        if (shared / name).is_file() and (project / "tools" / name).exists():
            out.append(name)
    return out


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
            # A dict since v13, so the REASON travels with the verdict and a reader of the
            # report never has to go and find out whether one was ever recorded.
            reason = declared_absent[local.name] if isinstance(declared_absent, dict) else ""
            return ABSENT, f"declared: {reason}" if reason else "declared not needed"
        return MISSING, "shared folder has it, this project does not - declare it or copy it"
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


def report(rows, refused=(), stale=()):
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
    # THE TWO WAYS A DECLARATION ITSELF IS THE FINDING, printed apart from the verdicts
    # because they are facts about the DECLARATION rather than about the file.
    for name, why in refused:
        print(f"! {'REFUSED':<9} {name:<{width}}  {why}")
        bad += 1
    for name in stale:
        print(f"! {'DECL-STALE':<9} {name:<{width}}  declared absent, but this project HAS it "
              f"- the declaration has outlived its reason")
        bad += 1
    print(f"\n{len(rows)} tracked, {bad} needing a decision")
    if bad:
        print("\nSTALE    -> copy the shared file over this project's copy.")
        print("DIVERGED -> either promote the fix to the shared folder (see the four")
        print("            questions in standard-scripts\\README.md) or declare the fork")
        print("            with a '# FORKED FROM ... BECAUSE ...' header.")
        print("MISSING  -> either copy the shared file into this project's tools\\ folder,")
        print("            or declare that it is deliberately not used, with a reason:")
        print("            --absent name.py          (this run only, no reason recorded)")
        print("            verify.config.json        (durable, and a reason is REQUIRED)")
        print("              \"checkers\": {\"declared_absent\": {\"name.py\": \"why\"}}")
        print("            A project holding NONE of them is a project nothing has been")
        print("            propagated to yet - which is a finding on its first day and a")
        print("            decision only once somebody has written down why.")
        print("REFUSED  -> a config entry with a blank reason. Write the reason, or delete")
        print("            the entry: an empty one reads afterwards exactly like a decision")
        print("            somebody took.")
        print("DECL-STALE -> the file is here after all. Delete the declaration, or the next")
        print("            real change to that file lands behind an exemption nobody rereads.")
    return 1 if bad else 0


# ---------------------------------------------------------------------------- roster

ROSTER_BEGIN = "<!-- ROSTER:BEGIN -->"
ROSTER_END = "<!-- ROSTER:END -->"
# Markdown emphasis and code ticks are stripped before matching, so the same pattern reads
# both house conventions - `name.py` **v3** and **`name.py` v3** - without either being
# privileged. A roster that has to be written one particular way is a roster somebody
# reformats and silently stops checking.
ROSTER_ROW_RE = re.compile(r"([A-Za-z_][A-Za-z0-9_]*\.py)\s+v(\d+)")

R_OK, R_WRONG, R_UNLISTED, R_GHOST = "OK", "WRONG", "UNLISTED", "GHOST"
ROSTER_FAILING = {R_WRONG, R_UNLISTED, R_GHOST}


def roster_region(text: str):
    """The delimited list, or None when the markers are missing or inverted.

    None is not an empty roster. It means the document cannot be judged, and the caller
    must report VOID - because a file scanned with no region found looks exactly like a
    file whose roster is perfect.
    """
    a, b = text.find(ROSTER_BEGIN), text.find(ROSTER_END)
    if a == -1 or b == -1 or b < a:
        return None
    return text[a + len(ROSTER_BEGIN):b]


def roster_claims(region: str):
    """{script name: version} as the document CLAIMS it, emphasis and ticks removed."""
    # `*` and the backtick only. NOT the underscore, though markdown treats it as emphasis:
    # it is also half the characters in auto_mode.py, and stripping it renamed every script
    # in the folder - the roster then read as sixteen GHOSTs beside sixteen UNLISTEDs. A
    # normaliser aimed at prose is the wrong normaliser for an identifier.
    flat = re.sub(r"[*`]", "", region)
    return {name: int(v) for name, v in ROSTER_ROW_RE.findall(flat)}


def actual_versions(shared: Path):
    """{script name: version} as each docstring DECLARES it - the authority.

    Only files that carry a CHECKER VERSION count. A helper with none is not something a
    roster is expected to list, and demanding it would make the arm fail on any project
    that keeps an ordinary module beside its checkers.
    """
    out = {}
    for p in sorted(shared.glob("*.py")):
        try:
            v = version_of(p.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            continue
        if v is not None:
            out[p.name] = v
    return out


def check_roster(roster: Path, shared: Path):
    """Return (rows, void_reason). Rows are (name, verdict, detail)."""
    try:
        text = roster.read_text(encoding="utf-8")
    except OSError as exc:
        return [], (f"cannot read {roster} - {type(exc).__name__}. A roster that was not "
                    f"opened proves nothing")
    region = roster_region(text)
    if region is None:
        return [], (f"no {ROSTER_BEGIN} / {ROSTER_END} region in {roster.name} - the list "
                    f"cannot be told apart from prose ABOUT past versions")
    claimed, actual = roster_claims(region), actual_versions(shared)
    if not actual:
        return [], f"no script in {shared} declares a CHECKER VERSION - nothing to check against"
    if not claimed:
        return [], (f"the roster region in {roster.name} names no script - an empty region "
                    f"is not an accurate roster, it is an unreadable one")
    rows = []
    for name in sorted(set(claimed) | set(actual)):
        want, got = actual.get(name), claimed.get(name)
        if want is None:
            rows.append((name, R_GHOST, f"roster says v{got}; the folder has no such script"))
        elif got is None:
            rows.append((name, R_UNLISTED, f"the folder has it at v{want}; the roster never "
                                           f"names it"))
        elif got != want:
            rows.append((name, R_WRONG, f"roster says v{got}, the docstring says v{want} - "
                                        f"re-derive the roster, do not edit one number"))
        else:
            rows.append((name, R_OK, ""))
    return rows, None


def roster_report(rows, void_reason, declared: bool):
    """Print the roster block and return its exit code: 0 pass, 1 finding, 2 VOID."""
    if not declared:
        print("\nROSTER  N/A  no roster document given (--roster PATH). The arm did not run;"
              "\n             that is different from having run and found nothing.")
        return 0
    if void_reason:
        print(f"\nROSTER  VOID  {void_reason}")
        return 2
    bad = [r for r in rows if r[1] in ROSTER_FAILING]
    width = max(len(n) for n, _, _ in rows)
    print()
    for name, verdict, detail in rows:
        flag = "  " if verdict not in ROSTER_FAILING else "! "
        print(f"{flag}ROSTER {verdict:<8} {name:<{width}}  {detail}")
    print(f"\n{len(rows)} rostered, {len(bad)} disagreeing with the docstrings")
    if bad:
        print("\nRE-DERIVE THE WHOLE LIST from the docstrings. Editing only the numbers you")
        print("came to change is how this list went stale seven times.")
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

        # AN ABSENCE, UNDECLARED THEN DECLARED - AND BOTH ARMS ARE REQUIRED, BECAUSE EACH
        # ALONE PASSES A DIFFERENT BROKEN VERSION. Check only the undeclared arm and a
        # blunt "absence always fails" ships, telling a project its considered decision is a
        # finding; check only the declared arm and the v11 defect ships back, because
        # returning ABSENT for both also passes it. The pair is the test.
        (tools / "verify_md.py").unlink()
        got = dict((n, v) for n, v, _ in run(tmp / "proj", shared, set()))["verify_md.py"]
        good = got == MISSING and MISSING in FAILING
        ok &= good
        print(f"  {'OK  ' if good else 'MISS'} {'undeclared absence':<24} "
              f"expected {MISSING:<9} got {got}, failing={got in FAILING} (want True)")
        rows2 = dict((n, v) for n, v, _ in run(tmp / "proj", shared,
                                               {"verify_md.py": "not needed here"}))
        got = rows2["verify_md.py"]
        good = got == ABSENT and ABSENT not in FAILING
        ok &= good
        print(f"  {'OK  ' if good else 'MISS'} {'declared absence':<24} "
              f"expected {ABSENT:<9} got {got}, failing={got in FAILING} (want False)")

        ok &= config_selftest(tmp, shared)

        # THE POPULATION ARM: A PROJECT HOLDING NONE OF THEM. This is the shape v11 got
        # wrong and the reason the verdict was split - four of five in-scope projects sat
        # here, each reporting "0 needing a decision" and exiting 0 while printing a row per
        # script telling somebody to declare it. The exit code AND the summary line are both
        # asserted: a code with no denominator behind it is the reading that went unnoticed.
        bare = tmp / "bare"
        (bare / "tools").mkdir(parents=True)
        n_tracked = len([n for n in TRACKED if (shared / n).is_file()])
        for label, declared, want_rc, want_bad in [
                ("holding none, undeclared", set(), 1, n_tracked),
                ("holding none, all declared", set(TRACKED), 0, 0)]:
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                rc = report(run(bare, shared, declared))
            text = buf.getvalue()
            summary = f"{n_tracked} tracked, {want_bad} needing a decision"
            good = rc == want_rc and summary in text
            ok &= good
            print(f"  {'OK  ' if good else 'MISS'} {label:<26} rc={rc} (want {want_rc}), "
                  f"summary {'matches' if summary in text else 'MISSING: ' + summary!r}")

        # a run with nothing tracked must be VOID, not a silent pass - and VOID exits 2,
        # because "could not run" is a different fact from "found a problem"
        empty = tmp / "empty"
        empty.mkdir()
        rc = report(run(tmp / "proj", empty, set()))
        good = rc == 2
        ok &= good
        print(f"  {'OK  ' if good else 'MISS'} {'empty shared folder is VOID':<24} rc={rc} (want 2)")

        ok &= roster_selftest(tmp, shared)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print("\nSELFTEST: " + ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


def config_selftest(tmp: Path, shared: Path) -> bool:
    """The config route, and every arm is a PAIR: the defect, then the wording that fixes it.

    A one-sided suite here ships the opposite bug in every case. Accept a blank reason and
    the reason stops being load-bearing, which is the only thing separating ABSENT from
    MISSING. Refuse a good reason and the durable route is unusable. Ignore a stale
    declaration and an exemption outlives the fact it was written about.
    """
    print("\nSELFTEST - the config route, each arm proved BOTH ways\n")
    ok = True
    seq = iter(range(1, 10_000))

    def project(config_text: str | None, hold: tuple[str, ...] = ()) -> Path:
        """A project holding `hold` in tools/, with the given config (or none at all)."""
        d = tmp / f"cfgproj{next(seq)}"
        (d / "tools").mkdir(parents=True)
        for n in hold:
            shutil.copy(shared / n, d / "tools" / n)
        if config_text is not None:
            (d / CONFIG_NAME).write_bytes(config_text.encode("utf-8"))
        return d

    def cfg(body: str) -> str:
        return '{"checkers": {"declared_absent": {' + body + '}}}'

    trials = [
        ("a config reason DECLARES the absence",
         cfg('"verify_md.py": "no documents in this project"'), ABSENT, [], []),
        ("a BLANK reason is refused, file stays MISSING",
         cfg('"verify_md.py": "   "'), MISSING, ["verify_md.py"], []),
        ("no config at all leaves it MISSING",
         None, MISSING, [], []),
        ("malformed JSON declares NOTHING (absences FAIL, not pass)",
         '{"checkers": {oops', MISSING, ["(the config itself)"], []),
        ("declared_absent of the wrong TYPE declares nothing",
         '{"checkers": {"declared_absent": ["verify_md.py"]}}', MISSING,
         ["(the config itself)"], []),
    ]
    for label, text, want_verdict, want_refused, want_stale in trials:
        d = project(text)
        declared, refused = read_declared_absent(d)
        verdict = dict((n, v) for n, v, _ in run(d, shared, declared))["verify_md.py"]
        stale = stale_declarations(d, shared, declared)
        good = (verdict == want_verdict
                and [n for n, _ in refused] == want_refused
                and stale == want_stale)
        ok &= good
        print(f"  {'OK  ' if good else 'MISS'} {label:<48} {verdict:<8} "
              f"refused={[n for n, _ in refused]} stale={stale}")

    # THE OTHER DIRECTION, and it is the arm a maintainer would leave out: the project HAS
    # the file the config says it does not. Proved against its own clean twin, so a check
    # that reported DECL-STALE for everything would fail here rather than look thorough.
    for label, hold, want in [("declared absent but PRESENT is DECL-STALE",
                               ("verify_md.py",), ["verify_md.py"]),
                              ("declared absent and genuinely gone is NOT", (), [])]:
        d = project(cfg('"verify_md.py": "no documents in this project"'), hold=hold)
        declared, _ = read_declared_absent(d)
        stale = stale_declarations(d, shared, declared)
        good = stale == want
        ok &= good
        print(f"  {'OK  ' if good else 'MISS'} {label:<48} stale={stale} (want {want})")

    # AND BOTH FINDINGS MUST REACH THE EXIT CODE, or they are decoration on a green run.
    for label, refused, stale, want_rc in [
            ("a refusal alone fails the run", [("x.py", "no reason")], [], 1),
            ("a stale declaration alone fails the run", [], ["x.py"], 1),
            ("neither, and the run passes", [], [], 0)]:
        d = project(cfg('"verify_md.py": "no documents in this project"'))
        declared, _ = read_declared_absent(d)
        rows = run(d, shared, dict.fromkeys(
            [n for n in TRACKED if (shared / n).is_file()], "declared for this arm"))
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = report(rows, refused, stale)
        good = rc == want_rc
        ok &= good
        print(f"  {'OK  ' if good else 'MISS'} {label:<48} rc={rc} (want {want_rc})")

    # A BYTE-ORDER MARK IS NOT A MALFORMED CONFIG. PowerShell writes one by default, so a
    # config created the most obvious way on this platform must still declare.
    d = tmp / "cfgbom"
    (d / "tools").mkdir(parents=True)
    (d / CONFIG_NAME).write_bytes(b"\xef\xbb\xbf" + cfg(
        '"verify_md.py": "no documents in this project"').encode("utf-8"))
    declared, refused = read_declared_absent(d)
    good = declared.get("verify_md.py") == "no documents in this project" and not refused
    ok &= good
    print(f"  {'OK  ' if good else 'MISS'} {'a UTF-8 BOM still parses and declares':<48} "
          f"declared={list(declared)} refused={[n for n, _ in refused]}")
    return ok


def roster_selftest(tmp: Path, shared: Path) -> bool:
    """Every roster verdict reachable, and each defect reproduced BEFORE its good arm.

    A check whose first run passes is not built correctly, so each row here is written as
    a pair: the wording that broke this house, then the wording that fixes it.
    """
    print("\nSELFTEST - the roster arm, each defect reproduced then fixed\n")
    ok = True
    names = sorted(actual_versions(shared))          # every fixture script sits at v2
    listed = " · ".join(f"**`{n}`** v2" for n in names)

    def doc(body: str) -> Path:
        p = tmp / f"roster{next(_ROSTER_SEQ)}.md"
        p.write_text(body, encoding="utf-8")
        return p

    def wrapped(rows: str) -> str:
        return (f"# Changelog\n\nProse ABOUT versions: `{names[0]}` stood at v99 once.\n\n"
                f"{ROSTER_BEGIN}\n{rows}\n{ROSTER_END}\n\nMore prose, `{names[1]}` v98.\n")

    # The prose above and below the region names two scripts at versions nothing carries.
    # If the region is ever ignored, the good arm below goes red and says so.
    def verdicts(body: str):
        rows, void = check_roster(doc(body), shared)
        return {n: v for n, v, _ in rows}, void

    trials = [
        ("a wrong version is WRONG",
         wrapped(listed.replace("v2", "v1", 1)), R_WRONG, names[0]),
        ("a script the roster omits is UNLISTED",
         wrapped(" · ".join(f"**`{n}`** v2" for n in names[1:])), R_UNLISTED, names[0]),
        ("a script the folder lacks is GHOST",
         wrapped(listed + " · **`no_such_script.py`** v3"), R_GHOST, "no_such_script.py"),
    ]
    for label, body, want, subject in trials:
        got, void = verdicts(body)
        bad_ok = void is None and got.get(subject) == want
        good, gvoid = verdicts(wrapped(listed))
        good_ok = gvoid is None and set(good.values()) == {R_OK}
        both = bad_ok and good_ok
        ok &= both
        print(f"  {'OK  ' if both else 'MISS'} {label:<40} defect={got.get(subject)} "
              f"(want {want}), clean={'all OK' if good_ok else good}")

    # VOID, NOT PASS. An undelimited file is the dangerous one: it looks like a document
    # with a perfect roster, and every verdict it could have produced is simply absent.
    for label, body in [("no region markers is VOID", "# Changelog\n\n" + listed + "\n"),
                        ("an empty region is VOID",
                         f"# C\n\n{ROSTER_BEGIN}\nnothing here\n{ROSTER_END}\n")]:
        _, void = verdicts(body)
        good = void is not None
        ok &= good
        print(f"  {'OK  ' if good else 'MISS'} {label:<40} void={bool(void)} (want True)")

    # The N/A arm must not be mistaken for a pass by the reader OR by the exit code.
    rc_na = roster_report([], None, declared=False)
    rc_void = roster_report([], "reason", declared=True)
    good = (rc_na, rc_void) == (0, 2)
    ok &= good
    print(f"  {'OK  ' if good else 'MISS'} {'N/A exits 0, VOID exits 2':<40} "
          f"got {rc_na}, {rc_void}")
    return ok


_ROSTER_SEQ = iter(range(1, 10_000))


def main(argv=None):
    p = argparse.ArgumentParser(description="Compare this project's checker copies "
                                            "against the shared standard scripts.")
    p.add_argument("--shared", default=str(SHARED_DEFAULT),
                   help="the shared standard-scripts folder")
    p.add_argument("--project", default=".", help="project root (expects a tools/ folder)")
    p.add_argument("--absent", default="",
                   help="comma-separated scripts this project deliberately does not use, "
                        "for THIS run. For a standing decision put them in "
                        "verify.config.json under checkers.declared_absent, where a reason "
                        "is required")
    p.add_argument("--roster", default="",
                   help="a document listing the scripts and their versions, checked "
                        "against the docstrings between its ROSTER:BEGIN/END markers")
    p.add_argument("--selftest", action="store_true")
    args = p.parse_args(argv)
    if args.selftest:
        return selftest()
    project, shared = Path(args.project), Path(args.shared)
    # A UNION, AND THE CONFIG IS READ FIRST SO A COMMAND-LINE NAME CANNOT ERASE ITS REASON.
    # The config is the standing decision; --absent adds to it for one run. Neither
    # overrides the other, because an override would let a hurried run silence a recorded
    # decision without anybody seeing which one was in force.
    declared, refused = read_declared_absent(project)
    for s in args.absent.split(","):
        name = s.strip()
        if name:
            declared.setdefault(name, CLI_REASON)
    stale = stale_declarations(project, shared, declared)
    rc = report(run(project, shared, declared), refused, stale)
    rows, void = ([], None) if not args.roster else check_roster(Path(args.roster), shared)
    rc_roster = roster_report(rows, void, declared=bool(args.roster))
    # The WORSE code wins, and 2 > 1 > 0 orders them correctly already: "the instrument
    # could not look" must never be absorbed into "it looked and found nothing".
    return max(rc, rc_roster)


if __name__ == "__main__":
    sys.exit(main())
