#!/usr/bin/env python3
"""run_tests.py - one command that runs everything this project tests with.
CHECKER VERSION 6 (2026-10-14)

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

A SUITE'S OWN COUNT IS KEPT WHEN IT SAYS HOW TO READ IT - AND UNTIL v6 IT WAS NEVER KEPT.
Every suite was added as "1 examined" and a passing suite's output thrown away, so a suite
of thousands of checks and a suite of one printed the same row - the very denominator the
paragraph above promises - and a session that needed the number ran the suite a SECOND
time to see it. Measured: a 47-check suite printed "PASS  smoke  1 examined", its own
"47 of 47" nowhere. So a configured suite may declare 'count', a pattern: WITH a group, the
number that group captures on the LAST matching line, stdout before stderr - "([0-9]+)
checks" for a summary line; WITHOUT one, the number of lines it matches - "^(?:PASS|FAIL) "
for a line per check. A declared count that reads nothing is VOID, no check having been
seen to run, and outranks a JUDGE; a group that captures a word, and a 'count' that is not
text at all, are refused rather than guessed at. A suite that declares none prints
as before AND SAYS its count is not kept, because the silent "1" was the defect. The
--selftest suites keep 1: each is one checker's proof, and counts its cases in its own output.

EVERY SUITE PRINTS ITS SECONDS, AND THE RUN ITS TOTAL - so a session plans its checks with a
figure taken on this run, never with one typed into a charter weeks ago, which goes stale
without saying so.

A SUITE CAN PASS AND STILL HAVE HANDED A CLAIM TO A PERSON, and that arrives as JUDGE
rather than PASS. A JUDGE deliberately exits 0 - a gate that blocks on a question nobody
can settle mechanically is a gate that gets switched off - so the exit code cannot carry it
across the process boundary and this runner reads the ARTEFACT instead: the JUDGE-CLAIMS
mark the suite printed. That is the same rule as everywhere else here, assert the artefact
and not the exit code, applied to a status that has no exit code of its own. --quiet is the
declared exception: it prints nothing by design, so it reports a JUDGE as the 0 it is.

A --selftest IS NOT THE TOOL, AND THAT GAP IS WHY entry_points EXISTS. Every suite above
was a checker's --selftest, so NO CHECKER'S REAL ENTRY POINT was exercised by anything.
Measured, and this is the whole argument: verify_deliverable.py's main() crashed with a
traceback on EVERY invocation - it unpacked four values from a five-tuple report row -
while this runner reported OVERALL: PASS, 13 of 13, for as long as that line existed. It
surfaced only because a newly promoted script copied the idiom and crashed on its first
real run. A checker can be completely broken in ordinary use while its --selftest is
perfect, because the two exercise different code.

SO THE ENTRY-POINT ARM ASSERTS THAT THE CHECKER RAN, AND DELIBERATELY IGNORES WHAT IT
FOUND. That inversion is the reason this could not simply be configured as a suite: a
checker reporting a real finding exits 1, so `suites` would turn every genuine finding
into a broken test run, and nobody would keep it. Here a finding is a PASS and only a
failure to START is a FAIL.

AND THE VERDICT READS THE ARTEFACT, BECAUSE THE EXIT CODE CANNOT CARRY IT. Measured on the
re-injected defect: the crash exited 1 - the same 1 as "I found problems". So a traceback
on the output, an empty report, or an exit code nobody defined is what fails this arm.

COVERAGE IS THE HALF THAT KEEPS IT HONEST. Declaring commands means a checker nobody listed
is invisible, so every script found by selftest_globs must be named by an entry point or
EXEMPT WITH A REASON. Declaring nothing at all is a JUDGE, not silence: a project that has
never thought about this needs to see it, and a hard failure on the day this arrives would
break green runs for a reason unrelated to any change and get switched off.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import time
from pathlib import Path

from house_common import (                                       # noqa: E402
    FAIL, JUDGE, JUDGE_MARK, NA, PASS, RC_COULD_NOT_RUN, RC_FAILED, RC_OK, VOID, Case,
    Report, judge_count, load_section, report_pairing, run_cases, selftest_config,
    write_section,
)

DEFAULT_CONFIG = {
    "suites": [],
    "selftest_globs": ["tools/*.py"],
    "entry_points": [],
    "entry_points_exempt": {},
    "timeout_seconds": 900,
    "stop_on_first_failure": False,
}

CONFIG_COMMENT = {
    "suites": "[{'name': 'smoke', 'command': 'uv run python tests/smoke_test.py', 'count': '^(?:PASS|FAIL) '}] - the project's own suites, in the order they should run. 'count' is optional: a pattern that reads the suite's OWN count off its output - with a group, the number it captures on the last matching line; without one, the number of lines it matches. Without it the row says 1 and that the count is not kept.",
    "selftest_globs": "Scripts whose --selftest counts as a suite. The house checkers are found by this, so a broken checker fails the test run.",
    "entry_points": "[{'command': 'uv run python tools/verify_md.py CLAUDE.md'}] - each checker's REAL entry point, run against this project. FINDINGS ARE IGNORED here: only a failure to START fails. That is why these cannot go in 'suites' - one legitimate finding would break the run.",
    "entry_points_exempt": "{'install_hooks.py': 'why'} - a checker deliberately not run this way, WITH ITS REASON. A blank reason is refused: it prints as a decision nobody made.",
    "timeout_seconds": "Per suite. A hung suite is a failure, not a wait.",
    "stop_on_first_failure": "false runs everything and reports all of it - usually what you want. true is for a long suite you are iterating on.",
}


def discover_scripts(root: Path, cfg):
    """The scripts this project's selftest globs match, in a stable order.

    SPLIT OUT OF discover() so the suite list and the COVERAGE arm cannot disagree about
    what "this project's checkers" means. Two walks of the same globs is how one arm comes
    to police a set the other does not have.
    """
    out, seen = [], set()
    for g in cfg["selftest_globs"]:
        for p in sorted(root.glob(g)):
            if p.name.startswith("_") or p in seen:
                continue
            body = p.read_text(encoding="utf-8", errors="replace")
            if "--selftest" in body:
                seen.add(p)
                out.append(p)
    return out


def discover(root: Path, cfg):
    """Every suite this project has, as (name, command, spec): the configured ones, then
    every --selftest found.

    A checker's own --selftest is a test of this project, not a formality: if a checker
    stops being able to fail, every result it has ever reported becomes unfalsifiable.

    SPEC IS THE SUITE'S OWN CONFIG ENTRY, None for a --selftest - so each suite carries its
    own count pattern. Looked up by name instead, two suites of one name shared the last
    one's pattern and the first read VOID.
    """
    out = [(s["name"], s["command"], s) for s in cfg["suites"]]
    for p in discover_scripts(root, cfg):
        rel = p.relative_to(root).as_posix()
        # THE INTERPRETER IS QUOTED, AND LEAVING IT UNQUOTED BREAKS EVERY PROJECT WHOSE
        # PATH HOLDS A SPACE. `rel` was quoted here from the start and sys.executable was
        # not - and under `uv run` the interpreter lives INSIDE the project (.venv), so its
        # path carries the project's spaces. Measured on a real project: all nine selftests
        # failed with "'C:\\...\\Coding\\Project' is not recognized", truncated exactly at
        # the space. Invisible in this folder, which has none - so it is correct where the
        # script lives and broken for the projects it is copied into.
        out.append((f"{p.stem} --selftest", f'"{sys.executable}" "{rel}" --selftest', None))
    return out


def script_in(command: str):
    """The script a command runs, by basename - the first token that ends in .py.

    INFERRED RATHER THAN DECLARED, so the coverage arm needs no second copy of a fact the
    command already carries. A copy is a thing that can disagree, and this one would go
    stale the first time somebody edited the command and not the label. An explicit
    'script' key still wins, for a wrapper whose command never names the file.
    """
    for tok in command.replace('"', " ").replace("'", " ").split():
        if tok.lower().endswith(".py"):
            return Path(tok).name
    return None


def entry_points(cfg):
    """The declared entry points as (name, command, script) triples.

    A name is optional because the command already says what it is, and a label nobody
    wants to invent is a reason not to declare the entry point at all.
    """
    out = []
    for e in cfg["entry_points"]:
        cmd = e["command"]
        script = e.get("script") or script_in(cmd)
        out.append((e.get("name") or f"{script or cmd} [entry]", cmd, script))
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


def suite_count(stdout: str, stderr: str, pattern):
    """A suite's OWN count, read off its output: (number, None), or (None, why it could not be).

    WITH A GROUP, the number that group captures on the LAST matching line - a summary line -
    looked for in stdout first and in stderr only if stdout has none, because a warning on
    stderr must not stand in for the summary on stdout. WITHOUT ONE, the number of lines it
    matches in both - one line per check. A group that captures a word is refused rather than
    guessed at: brackets around an alternative are a group, and the cure, (?:...), is named in
    the refusal. isdecimal(), not isdigit(): a superscript passes the second and crashes
    int(). Zero is not a count either - a declared count that reads nothing means no check was
    seen to run. And a 'count' that is not text - the expected TOTAL, written where its
    pattern belongs - is refused by name, never a traceback.
    """
    if not isinstance(pattern, str) or not pattern:
        return None, (f"its count {pattern!r} is not a pattern - 'count' is the text pattern "
                      f"that FINDS the count in the suite's output, not the count itself")
    try:
        rx = re.compile(pattern)
    except re.error as e:
        return None, f"its count pattern {pattern!r} is not a valid pattern ({e})"
    streams = (stdout.splitlines(), stderr.splitlines())
    if not rx.groups:
        n = sum(1 for lines in streams for ln in lines if rx.search(ln))
    else:
        last = next((m for lines in streams for m in map(rx.search, reversed(lines)) if m),
                    None)
        if last is None:
            return None, f"its count pattern {pattern!r} matched no line"
        got = last.group(1)
        if got is None:
            return None, ("its count pattern's group took no part in the last line it "
                          "matched, so it read no number")
        if not got.isdecimal():
            return None, (f"its count pattern's group captured {got!r}, not a number - "
                          f"write (?:...) to count the lines an alternative matches")
        n = int(got)
    if n == 0:
        return None, f"its count pattern {pattern!r} counted 0 - no check was seen to run"
    return n, None


def run_suite(root: Path, name, command, timeout, count=None, configured=False):
    """One suite's (status, detail lines, count examined).

    stdin=DEVNULL, AND IT IS NOT TIDINESS - IT IS THE DIFFERENCE BETWEEN A FAILURE AND A
    HANG. A checked command that reads stdin inherits this process's, which in an unattended
    or piped session never closes: the read blocks for ever and the whole run sits there
    producing nothing, which looks exactly like a slow suite. Measured here on a hook script
    whose entry point reads a payload from stdin - it hung the run until it was killed, and
    the timeout that would eventually have reported it was 900 seconds away. Applied to BOTH
    runners rather than the one that bit, because the second call site is the same shape.

    THE FIRST DETAIL LINE IS ALWAYS THE SUITE'S TIME, and, for a configured suite, where its
    count came from - or that it was not kept. A silent "1 examined" over a suite of
    thousands is the defect this line exists to end.
    """
    declared = count is not None
    unread = 0 if declared else 1
    start = time.monotonic()
    try:
        r = subprocess.run(command, shell=True, cwd=root, capture_output=True,
                           text=True, encoding="utf-8", errors="replace", timeout=timeout, stdin=subprocess.DEVNULL)
    except subprocess.TimeoutExpired:
        return FAIL, [f"timed out after {timeout}s"], unread
    except OSError as e:
        return VOID, [f"could not start: {e}"], unread
    took = f"{time.monotonic() - start:.1f} s"
    # JOINED ON A NEWLINE, so a stdout without a trailing one cannot fuse its last line with
    # stderr's first.
    out = "\n".join(s for s in (r.stdout, r.stderr) if s)
    examined, why = suite_count(r.stdout or "", r.stderr or "", count) if declared \
        else (1, None)
    if declared and why is None:
        note = f"{examined} counted by its pattern - {took}"
    elif declared:
        note, examined = f"{why} - {took}", 0
    elif configured:
        note = f"its own count is not kept - declare a 'count' pattern for it - {took}"
    else:
        note = took
    if r.returncode == RC_COULD_NOT_RUN:
        return VOID, ["exit 2 - the suite could not run", note] + diagnostic(out, 6), examined
    if r.returncode != 0:
        return FAIL, [f"exit {r.returncode}", note] + diagnostic(out, 12), examined
    # A DECLARED COUNT THAT READ NOTHING IS VOID, NOT PASS - the same rule as a suite that
    # matched no tests. A failure above outranks it, the suite's own verdict saying more; and
    # it outranks a JUDGE below, which exits 0 and would carry "no check was seen" out as a
    # clean run.
    if why:
        return VOID, [note], examined
    # A SUITE CAN PASS AND STILL HAVE HANDED SOMETHING TO A PERSON, and the exit code cannot
    # say so: a JUDGE deliberately exits 0, because a gate that blocks on a question nobody
    # can close mechanically is a gate that gets removed. So the ARTEFACT is read instead of
    # the exit code - which is this house's rule for every other check anyway. Without this,
    # a run that handed over twenty claims and one that found none are the same PASS here,
    # and the severity is invisible at exactly the layer everybody actually watches.
    if judge_count(out):
        return JUDGE, [note] + [ln.strip() for ln in out.splitlines() if JUDGE_MARK in ln], \
            examined
    return PASS, [note], examined


TRACEBACK_MARK = "Traceback (most recent call last)"
# A SHELL SAYING "no such command" IS NOT THE CHECKER SPEAKING, and it must never read as
# one. Windows cmd.exe reports a missing command as exit 1 - the same 1 a real finding uses -
# so the number cannot separate them and these two strings can. Narrow on purpose: a broad
# pattern would swallow a checker's own prose about a command.
NOT_STARTED_MARKS = ("is not recognized as an internal or external command",
                     "command not found")


def run_entry_point(root: Path, name, command, timeout):
    """Did this checker START and produce a report? What it FOUND is not this arm's business.

    THE ONE INVERSION THAT MAKES THE ARM POSSIBLE. A checker with a real finding exits 1, so
    judging an entry point by its exit code would turn every genuine finding into a failed
    test run - which is exactly why no project ever put these in 'suites', and why the
    crashing main() survived. Exit 0 and exit 1 are both PASS here.

    SO THE VERDICT IS READ OFF THE ARTEFACT, and that is not a stylistic choice: measured on
    the re-injected defect, the traceback exited 1 - indistinguishable from a finding by the
    number alone. What fails is a traceback, no report at all, or an exit code nobody
    defined.

    EXIT 2 IS A PASS HERE, AND THE MEASUREMENT THAT DECIDED IT IS WORTH THE PARAGRAPH. It
    was written as VOID first, on the house rule that a check examining nothing is not a
    pass. Then verify_deliverable.py - THE VERY SCRIPT WHOSE CRASH THIS ARM EXISTS FOR -
    turned out to exit 2 in this repo wherever it is run, because nothing is declared for it
    here. A rule that excludes the script it was built for is the wrong rule. And the two
    denominators are different things: the CHECKER examined nothing, while THIS ARM watched
    a process start, do its work and report properly, which is all it ever claimed to
    watch. Nothing is lost, because the traceback test runs FIRST and catches a crash at
    any exit code.

    SO VOID IS RESERVED FOR THIS ARM ITSELF EXAMINING NOTHING: no process ran at all. A
    declared script that is not on disk is VOID rather than FAIL - the same ruling as a
    declared-but-absent variant file - because a typo in a path is not evidence about the
    checker.
    """
    script = script_in(command)
    if script and not any(root.glob(f"**/{script}")):
        return VOID, [f"declared script {script} is not in this project - nothing ran, so "
                      f"this is not evidence about the checker"]
    try:
        r = subprocess.run(command, shell=True, cwd=root, capture_output=True,
                           text=True, encoding="utf-8", errors="replace", timeout=timeout, stdin=subprocess.DEVNULL)
    except subprocess.TimeoutExpired:
        return FAIL, [f"timed out after {timeout}s - a hung entry point is not a pass"]
    except OSError as e:
        return VOID, [f"could not start: {e}"]
    out = (r.stdout or "") + (r.stderr or "")
    if TRACEBACK_MARK in out:
        return FAIL, ["CRASHED - its main() raised, so this checker reports nothing at all "
                      "in ordinary use"] + diagnostic(out, 8)
    if any(m in out for m in NOT_STARTED_MARKS):
        return VOID, ["the shell could not start this command - nothing ran"] + \
            diagnostic(out, 4)
    if r.returncode not in (RC_OK, RC_FAILED, RC_COULD_NOT_RUN):
        return FAIL, [f"exit {r.returncode} - an exit code this house does not define"] + \
            diagnostic(out, 8)
    if not out.strip():
        return FAIL, ["produced NO output - it may have exited before reporting. A checker "
                      "that prints nothing has not been shown to run"]
    verdict = {RC_OK: "ran clean",
               RC_FAILED: "found something (exit 1) - a finding is a PASS to this arm",
               RC_COULD_NOT_RUN: "declined to run (exit 2) - it started and reported "
                                 "properly, which is all this arm asserts"}[r.returncode]
    return PASS, [verdict]


def check_coverage(rep, scripts, declared, cfg):
    """Every discovered checker is named by an entry point, or EXEMPT WITH A REASON.

    THE HALF THAT KEEPS A DECLARATION HONEST. Declared commands can only ever exercise what
    somebody remembered, and the defect this whole arm exists for was invisible precisely
    because nobody had thought about it. So a script in neither list is a FAIL, and silence
    is not available.

    NOTHING DECLARED AT ALL IS A JUDGE, NOT A FAIL. A project inheriting this checker has
    declared nothing yet, and failing its whole test run for a reason unrelated to any
    change it made is the shape of a gate people delete rather than satisfy. A JUDGE exits
    0, shows at the layer everyone watches, and is counted as a claim handed to a person.
    """
    names = [p.name for p in scripts]
    exempt = dict(cfg["entry_points_exempt"])
    if not names:
        rep.add("entry points cover the checkers", NA, 0,
                ["no scripts matched selftest_globs, so there is nothing to cover"])
        return
    # A BLANK REASON IS THE SILENT VERSION OF NO REASON, and it prints as a decision
    # nobody made. house_common refuses one in record(); these rows are built by hand, so
    # the same guard is applied here rather than assumed.
    blank = sorted(k for k, v in exempt.items() if not str(v).strip())
    if blank:
        rep.add("entry points cover the checkers", FAIL, len(names),
                [f"exempt with no reason: {', '.join(blank)} - state the reason or run it"])
        return
    if not declared:
        # THE MARK IS NOT WRITTEN INTO THIS TEXT, and that is deliberate rather than an
        # omission: main() emits it once from rep.judge_line(), the way every checker here
        # does. Put it in a row's prose and this script's own --selftest output carries the
        # mark from its FIXTURES, so a parent run reads a claim nobody made.
        rep.add("entry points cover the checkers", JUDGE, len(names),
                [f"no checker's REAL entry point is exercised by any suite: all "
                 f"{len(names)} are --selftest only, and a --selftest is not the tool. "
                 f"Declare 'entry_points' in verify.config.json, or declare each one "
                 f"exempt with its reason."])
        return
    covered = {s for _, _, s in declared if s}
    missing = [n for n in names if n not in covered and n not in exempt]
    rep.add("entry points cover the checkers", FAIL if missing else PASS, len(names),
            [f"named by no entry point and not exempt: {', '.join(missing)}"] if missing
            else [f"{len(covered & set(names))} exercised, {len(exempt)} exempt with a "
                  f"reason: {', '.join(f'{k} ({v})' for k, v in sorted(exempt.items()))}"
                  if exempt else f"{len(covered & set(names))} exercised, none exempt"])


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
    scripts = discover_scripts(root, cfg)
    eps = entry_points(cfg)

    if "--list" in argv:
        for name, command, _ in suites:
            print(f"  {name:<32} {command}")
        for name, command, _ in eps:
            print(f"  {name:<32} {command}")
        print(f"\n{len(suites)} suite(s), {len(eps)} entry point(s)")
        return RC_OK if suites or eps else RC_COULD_NOT_RUN

    if not suites and not eps:
        if not quiet:
            print("VOID: no suites configured and no --selftest found. Either declare "
                  "suites under 'tests' in verify.config.json, or record in CLAUDE.md "
                  "why this project has none. A run that tested nothing has not passed.")
        return RC_COULD_NOT_RUN

    rep = Report()
    stopped = False
    began = time.monotonic()
    for name, command, spec in suites:
        status, problems, examined = run_suite(root, name, command, cfg["timeout_seconds"],
                                               count=(spec or {}).get("count"),
                                               configured=spec is not None)
        rep.add(name, status, examined, problems)
        if status == FAIL and cfg["stop_on_first_failure"]:
            rep.add("(remaining suites)", NA, 0, ["stopped at the first failure"])
            stopped = True
            break
    suites_took = time.monotonic() - began

    # THE ENTRY-POINT ARM, and it runs AFTER the suites deliberately: these invoke the real
    # checkers against the real project, so a suite failure that has already stopped the run
    # must stop these too rather than pile a second kind of noise on top of it.
    if not stopped:
        for name, command, _ in eps:
            status, problems = run_entry_point(root, name, command, cfg["timeout_seconds"])
            rep.add(name, status, 1, problems)
        check_coverage(rep, scripts, eps, cfg)

    if quiet:
        return rep.exit_code

    print(rep.render(name_width=34))
    # THIS LINE'S SHAPE IS READ BY ANOTHER TOOL - a lane parses "<n> suite(s) run" - so the
    # time goes on a line of its own rather than onto the end of this one.
    print(f"\n{len(suites)} suite(s) run, {len(eps)} entry point(s) exercised")
    print(f"the suites took {suites_took:.1f} s in all")
    print("OVERALL: " + rep.verdict())
    # THE CAVEAT ONLY APPLIES TO A PASS, and printing it after a FAIL asserted something
    # false: "every suite RAN and PASSED" under OVERALL: FAIL. A report that contradicts the
    # verdict three lines above it teaches the reader to skip the report.
    if rep.exit_code == RC_OK and rep.judged:
        # THE SAME LESSON AS THE BRANCH BELOW, one severity later. "Every suite RAN and
        # PASSED" is true here and it is not the whole truth, and a caveat that omits the
        # one thing waiting on a reader teaches that reader to skip the caveat.
        print(f"\nEvery suite RAN and PASSED - and {rep.count_of(JUDGE)} of them handed a "
              "claim to a PERSON.\nNothing above will ever fail on those: they are questions "
              "no script can settle, listed\nunder the suite that raised them. Read them, "
              "decide, and write the decision down.")
    elif rep.exit_code == RC_OK:
        print("\nThis says every suite RAN and PASSED. It says nothing about whether the "
              "output is any good -\nthat judgement is not repeatable, and a suite that is "
              "not repeatable cannot be a gate.")
    else:
        print("\nA suite above did not pass. The lines under it are the ones that SAY WHY, "
              "picked out of\nthe output rather than taken from its end - re-run that suite "
              "directly for the whole of it.")
    # THE MACHINE-READABLE MARK, printed LAST and from one place. Every other checker here
    # ends this way, and this runner did not - so a JUDGE it raised itself was legible to a
    # reader and invisible to anything reading its output, including a parent run of this
    # very script. It is emitted here rather than inside a row's prose precisely so that
    # this script's own --selftest, whose fixtures talk about judging, cannot carry it.
    mark = rep.judge_line()
    if mark:
        print(mark)
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
# A suite that PASSES and hands a claim over: exit 0, and the mark on stdout. The two facts
# together are the whole protocol, and the fixture carries both so the case cannot pass by
# accident on either one alone.
JUDGING = ('import sys\nif "--selftest" in sys.argv:\n'
           '    print("' + JUDGE_MARK + ' 2 - a person must settle these")\n'
           '    sys.exit(0)\n')
# THE FALSE-POSITIVE GUARD, and it is the arm that matters: a suite whose output merely
# TALKS about judging must not be reported as judging. A substring search for the word - the
# obvious implementation - reports a judgement from this very file.
TALKS_ABOUT_IT = ('import sys\nif "--selftest" in sys.argv:\n'
                  '    print("we should add a JUDGE severity one day")\n'
                  '    sys.exit(0)\n')

# ---- the entry-point fixtures. EVERY ONE HAS A PERFECT --selftest, which is the point:
# these differ only in what their REAL entry point does, so any case that the --selftest arm
# could also have caught would be proving nothing about the new arm.
_SELFTEST_OK = 'import sys\nif "--selftest" in sys.argv:\n    sys.exit(0)\n'
# The measured defect, in miniature: a report is printed, THEN main() raises. Modelled on
# the real one - four values unpacked from a five-tuple - because the crash came after the
# rows, so "it printed something" is not evidence that it finished.
CRASHES_IN_MAIN = (_SELFTEST_OK + 'print("PASS  some check   3 examined")\n'
                   'rows = [(None, "n", "PASS", 1, [])]\n'
                   'a, b, c, d = rows[0]\n')
# A checker doing its job: real findings, exit 1, no traceback. THIS MUST PASS, and it is
# why these cannot live in 'suites' - there, one honest finding breaks the test run.
REPORTS_A_FINDING = (_SELFTEST_OK + 'print("FAIL  some check   3 examined")\n'
                     'sys.exit(1)\n')
RUNS_CLEAN = _SELFTEST_OK + 'print("PASS  some check   3 examined")\nsys.exit(0)\n'
# Exit 0 and not one word: it may have returned before reporting at all.
SILENT_MAIN = _SELFTEST_OK + 'sys.exit(0)\n'
CANNOT_RUN_MAIN = (_SELFTEST_OK + 'print("VOID: no config to read")\nsys.exit(2)\n')
UNDEFINED_EXIT = _SELFTEST_OK + 'print("something happened")\nsys.exit(3)\n'


def _project(tmp: Path, files, tests=None):
    """A fixture project: tools/ scripts, and the 'tests' config section if one is given."""
    d = tmp / "proj"
    (d / "tools").mkdir(parents=True, exist_ok=True)
    for name, code in files.items():
        (d / "tools" / name).write_text(code, encoding="utf-8")
    if tests is not None:
        (d / "verify.config.json").write_text(json.dumps({"tests": tests}),
                                              encoding="utf-8")
    return d


def _one(code):
    return lambda t: _project(t, {"t_one.py": code})


FAKE_SPACED_EXE = r"C:\Program Files\Some Python\python.exe"


def _shell_program(cmd: str) -> str:
    """What a shell takes as the PROGRAM: a quoted run if quoted, else up to the space."""
    if cmd.startswith('"'):
        return cmd[1:cmd.index('"', 1)]
    return cmd.split(" ", 1)[0]


def _assert_spaced_interpreter_is_quoted(tmp: Path) -> bool:
    """A PROJECT WHOSE PATH HOLDS A SPACE MUST STILL BE ABLE TO RUN ITS OWN SELFTESTS.

    THE DECIDING ASSERTION IS ON THE STRING, NOT ON A LIVE RUN, and that is deliberate: it
    only reproduces live when the AMBIENT interpreter path happens to contain a space, so a
    functional arm would pass or fail by accident of environment rather than by the fix.
    The string property is exact and holds everywhere.

    PAIRED, because "the command runs" alone is satisfied on any machine whose python sits
    in a path without spaces - which is precisely the machine this defect hid on for as
    long as it existed. So the twin builds the OLD form with a KNOWN spaced path and
    requires the shell to mis-read it.
    """
    d = tmp / "a project with a space"
    (d / "tools").mkdir(parents=True, exist_ok=True)
    (d / "tools" / "t_spaced.py").write_text(PASSING, encoding="utf-8")
    suites = discover(d, dict(DEFAULT_CONFIG))
    made = [c for n, c, _ in suites if "t_spaced" in n]
    # THE REAL BUILDER: whatever the interpreter is, the shell must see all of it.
    real_ok = bool(made) and _shell_program(made[0]) == sys.executable
    # THE FIXED FORM, on a path known to contain spaces.
    fixed_ok = _shell_program(f'"{FAKE_SPACED_EXE}" "x.py" --selftest') == FAKE_SPACED_EXE
    # THE TWIN: the old, unquoted form must MIS-READ that same path.
    old = _shell_program(f'{FAKE_SPACED_EXE} "x.py" --selftest')
    twin_fires = old != FAKE_SPACED_EXE and old == r"C:\Program"
    ok = real_ok and fixed_ok and twin_fires
    print(f"  {'OK  ' if ok else 'MISS'} a spaced interpreter path survives the shell -> "
          f"builder={real_ok}, quoted={fixed_ok}, unquoted-mis-reads={twin_fires}"
          f"{'' if ok else '  (unquoted, every selftest dies with is-not-recognized)'}")
    return ok


def entry_probe(built):
    """The new arm's verdict on tools/t_one.py."""
    status, _ = run_entry_point(built, "t_one.py [entry]",
                                f'"{sys.executable}" "tools/t_one.py"', 120)
    return status


def absent_probe(built):
    """The verdict when the declared command names a script the project does not have."""
    status, _ = run_entry_point(built, "t_named.py [entry]",
                                f'"{sys.executable}" "tools/t_named.py"', 120)
    return status


def both_arms_probe(built):
    """BOTH arms' verdicts off ONE fixture - the acceptance condition, which no single
    status can state. B4 taught this shape: the claim is not "the new arm fires", it is
    that the new arm fires WHERE THE OLD ONE PASSES AS CLEAN. If the old arm caught it too,
    the new one is decoration, and a case row asserting only FAIL cannot tell the
    difference."""
    cfg = dict(DEFAULT_CONFIG)
    suites = discover(built, cfg)
    old = run_suite(built, *suites[0][:2], 120)[0] if suites else VOID
    return f"selftest={old},entry={entry_probe(built)}"


def coverage_probe(built):
    """The coverage row's verdict, read through the REAL config loader."""
    cfg = load_section(built, "tests", DEFAULT_CONFIG)
    rep = Report()
    check_coverage(rep, discover_scripts(built, cfg), entry_points(cfg), cfg)
    return rep.status_of("entry points cover the checkers")


_EP_ONE = [{"command": 'python "tools/t_one.py"'}]
_TWO_SCRIPTS = {"t_one.py": RUNS_CLEAN, "t_two.py": RUNS_CLEAN}


# ---- A SUITE'S OWN COUNT. The fixture suite prints one PASS line per check, as a project's
# smoke suite does, so the only way the report can say 47 is by reading the suite's output.
_FORTY_SEVEN = [f"PASS check {i}" for i in range(47)]


def _suites(*specs):
    """A builder: a project whose configured suites - ALL NAMED 'smoke', on purpose - each
    print LINES on stdout and ERR on stderr, exit RC and declare COUNT.
    Each spec is (lines, count, rc, err)."""
    def build(t: Path):
        d = t / "proj"
        (d / "tests").mkdir(parents=True, exist_ok=True)
        suites = []
        for i, (lines, count, rc, err) in enumerate(specs):
            # UTF-8 OUT, OR A NON-ASCII FIXTURE PROVES NOTHING: printed to a pipe in the
            # platform's code page, a superscript arrived as a replacement character and the
            # case meant to reproduce its crash passed by accident.
            body = ("import sys\nsys.stdout.reconfigure(encoding='utf-8')\n"
                    "sys.stderr.reconfigure(encoding='utf-8')\n"
                    + "".join(f"print({ln!r})\n" for ln in lines)
                    + "".join(f"print({ln!r}, file=sys.stderr)\n" for ln in err)
                    + f"sys.exit({rc})\n")
            (d / "tests" / f"suite{i}.py").write_text(body, encoding="utf-8")
            suite = {"name": "smoke", "command": f'"{sys.executable}" "tests/suite{i}.py"'}
            if count is not None:
                suite["count"] = count
            suites.append(suite)
        (d / "verify.config.json").write_text(
            json.dumps({"tests": {"suites": suites, "selftest_globs": []}}), encoding="utf-8")
        return d
    return build


def _counted(lines, count=None, rc=0, err=()):
    """A builder: a project whose ONE configured suite prints LINES, exits RC, declares COUNT."""
    return _suites((lines, count, rc, err))


def run_main(built, *flags):
    """main() over a built project: (exit code, everything it printed). THE ONE HARNESS for
    every selftest that runs the whole thing, so the working directory is put back in one
    place, even when main() raises."""
    import io
    import os
    from contextlib import redirect_stdout
    buf, cwd = io.StringIO(), os.getcwd()
    try:
        os.chdir(built)
        with redirect_stdout(buf):
            rc = main(["run_tests.py", *flags])
    finally:
        os.chdir(cwd)
    return rc, buf.getvalue()


def count_probe(built):
    """The FIRST smoke row's status and count, read off the REPORT - the layer a session
    reads, and the one where the count used to be lost."""
    m = re.search(r"^\s*(\w+)\s+smoke\s+(\d+) examined", run_main(built)[1], re.M)
    return f"{m.group(1)} {m.group(2)}" if m else "NO ROW"


def probe(built):
    """Run the whole thing over a built project and give back the first suite's status."""
    cfg = dict(DEFAULT_CONFIG)
    suites = discover(built, cfg)
    if not suites:
        return VOID
    return run_suite(built, *suites[0][:2], 120)[0]


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
            # THE POINT OF THE WHOLE SEVERITY, ASSERTED AT THE LAYER PEOPLE WATCH. A suite
            # that exits 0 having handed two claims over must arrive here as JUDGE and not
            # as PASS, or the run that raised them is indistinguishable from a clean one.
            Case("a judging suite is JUDGE, not PASS", probe,
                 lambda t: _script(t / "judge", "t_one.py", JUDGING),
                 lambda t: _script(t / "good3", "t_one.py", PASSING),
                 want=JUDGE),
            Case("...and it is not FAIL either", probe,
                 lambda t: _script(t / "judge2", "t_one.py", JUDGING),
                 lambda t: _script(t / "talk", "t_one.py", TALKS_ABOUT_IT),
                 want=JUDGE),

            # ---- the entry-point arm. THE PAIR IN THE FIRST CASE IS THE WHOLE DESIGN:
            # a crash fails, an honest finding passes. Get that backwards and the arm is
            # either useless or unusable.
            Case("a traceback is FAIL", entry_probe,
                 _one(CRASHES_IN_MAIN), _one(RUNS_CLEAN)),
            Case("a crash fails where a finding passes", entry_probe,
                 _one(CRASHES_IN_MAIN), _one(REPORTS_A_FINDING)),
            # THE ACCEPTANCE CONDITION, off one fixture, in one string.
            Case("the --selftest arm is BLIND to it", both_arms_probe,
                 _one(CRASHES_IN_MAIN), _one(RUNS_CLEAN),
                 want=f"selftest={PASS},entry={FAIL}",
                 good_want=f"selftest={PASS},entry={PASS}"),
            Case("no output at all is FAIL", entry_probe,
                 _one(SILENT_MAIN), _one(RUNS_CLEAN)),
            # EXIT 2 IS A PASS TO THIS ARM, and the case is written the way round that
            # proves it: the crash still fails while the checker that declined to run does
            # not. Written as VOID first, until verify_deliverable.py - the script this arm
            # exists for - turned out to exit 2 wherever it runs in this repo.
            Case("a crash fails where exit 2 passes", entry_probe,
                 _one(CRASHES_IN_MAIN), _one(CANNOT_RUN_MAIN)),
            Case("an undefined exit code is FAIL", entry_probe,
                 _one(UNDEFINED_EXIT), _one(RUNS_CLEAN)),
            # A DECLARED SCRIPT THAT IS NOT THERE IS VOID, NEVER FAIL - a typo in a path is
            # not evidence about a checker. Same ruling as a declared-but-absent variant
            # file, and the two "nothing happened" states stay distinct.
            Case("a declared script that is absent is VOID", absent_probe,
                 lambda t: _project(t, {"t_one.py": RUNS_CLEAN}),
                 lambda t: _project(t, {"t_one.py": RUNS_CLEAN,
                                        "t_named.py": RUNS_CLEAN}), want=VOID),

            # ---- coverage: what keeps a DECLARED list from being a list of one's
            # favourites. The defect this arm exists for was invisible because nobody had
            # thought about it, so "nobody listed it" must not be a pass.
            Case("declaring nothing is JUDGE, not PASS", coverage_probe,
                 lambda t: _project(t, {"t_one.py": RUNS_CLEAN}, {"entry_points": []}),
                 lambda t: _project(t, {"t_one.py": RUNS_CLEAN},
                                    {"entry_points": _EP_ONE}),
                 want=JUDGE),
            Case("a checker named nowhere is FAIL", coverage_probe,
                 lambda t: _project(t, _TWO_SCRIPTS, {"entry_points": _EP_ONE}),
                 lambda t: _project(t, _TWO_SCRIPTS,
                                    {"entry_points": _EP_ONE,
                                     "entry_points_exempt":
                                         {"t_two.py": "writes real machine state"}})),
            # A BLANK REASON PRINTS AS A DECISION NOBODY MADE - the same guard
            # house_common applies in record(), applied to a row built by hand.
            Case("an exemption with no reason is FAIL", coverage_probe,
                 lambda t: _project(t, _TWO_SCRIPTS,
                                    {"entry_points": _EP_ONE,
                                     "entry_points_exempt": {"t_two.py": "   "}}),
                 lambda t: _project(t, _TWO_SCRIPTS,
                                    {"entry_points": _EP_ONE,
                                     "entry_points_exempt":
                                         {"t_two.py": "writes real machine state"}})),

            # ---- a suite's OWN COUNT. THE DEFECT: every suite was added as "1 examined" and
            # a passing suite's output dropped, so a session ran the suite a second time to
            # learn how many checks it held. Each case is read off the rendered report.
            Case("a declared count reaches the report", count_probe,
                 _counted(_FORTY_SEVEN), _counted(_FORTY_SEVEN, count=r"^PASS "),
                 want=f"{PASS} 1", good_want=f"{PASS} 47"),
            Case("a count that matches nothing is VOID", count_probe,
                 _counted(_FORTY_SEVEN, count=r"^OK "),
                 _counted(_FORTY_SEVEN, count=r"^PASS "),
                 want=f"{VOID} 0", good_want=f"{PASS} 47"),
            Case("a group reads the last line's number", count_probe,
                 _counted(["RESULT: ALL PASS"], count=r"(\d+) checks"),
                 _counted(_FORTY_SEVEN + ["RESULT: ALL PASS - 2408 checks, 0 failed"],
                          count=r"(\d+) checks"),
                 want=f"{VOID} 0", good_want=f"{PASS} 2408"),
            # THE TRAP IN THE SYNTAX: brackets around an alternative make a GROUP, and a group
            # means "read the number it captured". Capturing the word PASS is refused out loud,
            # never counted as some number nobody meant.
            Case("a group that captures no number is VOID", count_probe,
                 _counted(_FORTY_SEVEN, count=r"^(PASS|FAIL) "),
                 _counted(_FORTY_SEVEN, count=r"^(?:PASS|FAIL) "),
                 want=f"{VOID} 0", good_want=f"{PASS} 47"),
            Case("a failing suite keeps its count", count_probe,
                 _counted(_FORTY_SEVEN[:46] + ["FAIL check 46"], count=r"^(?:PASS|FAIL) ",
                          rc=1),
                 _counted(_FORTY_SEVEN, count=r"^(?:PASS|FAIL) "),
                 want=f"{FAIL} 47", good_want=f"{PASS} 47"),
            Case("a broken pattern is VOID, not a crash", count_probe,
                 _counted(_FORTY_SEVEN, count="(unclosed"),
                 _counted(_FORTY_SEVEN, count=r"^PASS "),
                 want=f"{VOID} 0", good_want=f"{PASS} 47"),
            # THE TOTAL WRITTEN WHERE ITS PATTERN BELONGS - the likeliest misreading of the key.
            Case("a count that is not a pattern is VOID", count_probe,
                 _counted(_FORTY_SEVEN, count=2408),
                 _counted(_FORTY_SEVEN, count=r"^PASS "),
                 want=f"{VOID} 0", good_want=f"{PASS} 47"),
            # A DIGIT TO isdigit() IS NOT ALWAYS ONE TO int(): a superscript passes the first
            # and crashes the second. Refused, never a traceback.
            Case("a captured superscript is VOID", count_probe,
                 _counted(["² checks"], count=r"(\S+) checks"),
                 _counted(["47 checks"], count=r"(\S+) checks"),
                 want=f"{VOID} 0", good_want=f"{PASS} 47"),
            # A JUDGE MUST NOT MASK A RUN IN WHICH NO CHECK WAS SEEN: VOID exits 2, JUDGE 0.
            Case("an unread count outranks a JUDGE", count_probe,
                 _counted([f"{JUDGE_MARK} 2 - a person must settle these"], count=r"^PASS "),
                 _counted(_FORTY_SEVEN + [f"{JUDGE_MARK} 2 - a person must settle these"],
                          count=r"^PASS "),
                 want=f"{VOID} 0", good_want=f"{JUDGE} 47"),
            # A WARNING ON stderr MUST NOT STAND IN FOR THE SUMMARY ON stdout.
            Case("stdout's summary beats stderr's", count_probe,
                 _counted(["RESULT: ALL PASS - 2408 checks"], count=r"(\d+) checks",
                          err=["warning: 3 checks skipped"]),
                 _counted(["RESULT: ALL PASS - 2408 checks"], count=r"(\d+) checks"),
                 want=f"{PASS} 2408", good_want=f"{PASS} 2408"),
            # EACH SUITE CARRIES ITS OWN PATTERN - two of one name must not share the last.
            Case("two suites of one name keep their own", count_probe,
                 _suites((_FORTY_SEVEN, r"^PASS ", 0, ()),
                         (["RESULT 5 checks"], r"(\d+) checks", 0, ())),
                 _counted(_FORTY_SEVEN, count=r"^PASS "),
                 want=f"{PASS} 47", good_want=f"{PASS} 47"),
        ]
        cok, paired, unpaired = run_cases(cases, tmp, width=34)
        ok &= cok
        report_pairing(paired, unpaired)
        ok &= _assert_spaced_interpreter_is_quoted(tmp)

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

        # EVERY SUITE SAYS HOW LONG IT TOOK, AND A SUITE WITHOUT A COUNT SAYS SO. The time is
        # printed fresh on every run, so no charter has to carry a figure that goes stale; the
        # note is what turns "1 examined" from a silent wrong denominator into a visible gap.
        plain = run_main(_counted(_FORTY_SEVEN)(tmp / "plain"))[1]
        timed = re.search(r"^\s+- .*\b\d+\.\d s\b", plain, re.M) is not None
        noted = "count is not kept" in plain
        total = re.search(r"^the suites took \d+\.\d s in all$", plain, re.M) is not None
        # A GROUP THAT TOOK NO PART IN THE LINE IT MATCHED is not "matched no line" - the
        # refusal must send the reader to the group, not off looking for a missing line.
        unset = run_main(_counted(["checks: none"], count=r"checks:? ?(\d+)?")(tmp / "unset"))[1]
        for label, good in (("every suite prints its seconds", timed),
                            ("an undeclared count says so", noted),
                            ("the run prints its total time", total),
                            ("an unset group is named as such", "took no part" in unset)):
            ok &= good
            print(f"  {'OK  ' if good else 'MISS'} {label}")

        # a project with nothing to test must be VOID and exit 2, never a silent pass
        empty = tmp / "empty"
        empty.mkdir()
        rc, _ = run_main(empty)
        good = rc == RC_COULD_NOT_RUN
        ok &= good
        print(f"  {'OK  ' if good else 'MISS'} {'nothing to test exits 2':<34} -> {rc}")

        # --quiet must print NOTHING and still carry the verdict, or git bisect cannot
        # use it - the one mode whose whole value is that it is silent
        rc, printed = run_main(_script(tmp / "q", "t_one.py", FAILING), "--quiet")
        good = printed == "" and rc == RC_FAILED
        ok &= good
        print(f"  {'OK  ' if good else 'MISS'} {'--quiet is silent and still fails':<34} "
              f"-> printed={len(printed)} chars, exit={rc}")

        # A JUDGE MUST NOT BLOCK, END TO END - not merely in the result model, but through
        # main() and out of the process, which is the number a gate or a git hook reads. And
        # the run must SAY SO on screen: exiting 0 silently is how the severity would fail.
        rc, printed = run_main(_script(tmp / "je", "t_one.py", JUDGING))
        said = "handed a claim to a PERSON" in printed
        good = rc == RC_OK and said
        ok &= good
        print(f"  {'OK  ' if good else 'MISS'} {'a JUDGE exits 0 and says so':<34} "
              f"-> exit={rc}, announced={said}")

        ok &= selftest_config(tmp, "tests", "suites",
                              lambda d: load_section(d, "tests", DEFAULT_CONFIG), width=34)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print()
    print("SELFTEST: " + ("PASS" if ok else "FAIL"))
    return RC_OK if ok else RC_FAILED


if __name__ == "__main__":
    sys.exit(main(sys.argv))
