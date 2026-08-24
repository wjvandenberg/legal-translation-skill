#!/usr/bin/env python3
"""house_common.py - the plumbing every house checker shares.  CHECKER VERSION 5 (2026-08-21)

WHAT IS HERE AND WHY IT IS HERE. The result model (PASS / FAIL / VOID / N-A, the denominator
rule, the exit-code convention), reading verify.config.json, and the selftest that proves a
config still loads. None of it is specific to documents, code or deliverables - it is the
same in all three, and before this file it WAS the same in all three, three times over.

THE MEASUREMENT THAT PRODUCED THIS FILE. The first structural review found 218 lines of
identical code across the five scripts, 11% of the live total: three copies of the result
class, three of the config reader, three of the config selftest. Three of those five had
been written the same morning, by one session, while fixing four bugs - which is the exact
"a fix built on top of a fix" shape the review exists to catch, caught on its first run.

AND IT HAD ALREADY DRIFTED, which is the argument that settles it. The three copies were
not quite identical: one had grown a bespoke branch the others lacked. Duplication is not
merely three times the work - it is three things that stop being the same thing, silently.

THE COST, ACCEPTED KNOWINGLY. A checker is no longer one file you can copy on its own. Copy
this file alongside it, always. check_checkers.py tracks it for exactly that reason: a
project holding verify_md.py without house_common.py has a checker that cannot start, and
that must be a reported finding rather than a surprise at the worst moment.

STANDARD LIBRARY ONLY, like everything else here, so it runs wherever the checkers run.
"""
from __future__ import annotations

import json
import re
import shutil
import sys
import tempfile
from pathlib import Path

PASS, FAIL, VOID, NA = "PASS", "FAIL", "VOID", "N/A"


# --------------------------------------------------- printing a report that cannot crash

def safe_stdout(stream=None):
    """Make a stream survive characters the terminal's codepage cannot encode.

    A CHECKER THAT CRASHES REPORTS NOTHING, which is strictly worse than reporting a
    failure - and this crash lands at the PRINT, after the checks have run, so the rows
    scroll past and the traceback replaces the verdict. Nobody reading that output can tell
    a pass from a fail.

    MEASURED, on Windows: Python encodes redirected stdout with the ANSI codepage, and cp1252
    has no mapping for U+3014. A document merely CONTAINING that character made the report
    abort - so the checker's own coverage depended on which characters the documents it
    checks happen to use, which is not a property any control should have.

    Called at import below, deliberately as a side effect: every checker that imports this
    module gets it without having to remember, and a checker that forgets is exactly the one
    whose report will be missing when it matters.
    """
    s = stream if stream is not None else sys.stdout
    if hasattr(s, "reconfigure"):
        # utf-8 first, so a capable terminal prints the character properly; errors='replace'
        # so an incapable one prints a placeholder instead of ending the run.
        s.reconfigure(encoding="utf-8", errors="replace")
    return s


safe_stdout()

# Exit codes, and the reason they are three rather than two:
#   0  every check passed or was a declared N/A
#   1  at least one check FAILED - it ran, and found something
#   2  at least one check COULD NOT RUN, and none failed
# "It could not run" and "it failed" are different facts, and a caller that cannot tell
# them apart cannot react correctly to either. A FAIL outranks a VOID, because a defect you
# have found beats one you could not look for. Both are non-zero, so any gate wired to
# "non-zero blocks" behaves exactly as it did before the distinction existed.
RC_OK, RC_FAILED, RC_COULD_NOT_RUN = 0, 1, 2


# ------------------------------------------------------------------- the size of a charter

# A CLAUDE.md is loaded in full and never truncated, so being over the cap produces no error
# and no symptom - it is simply followed less well. The numbers are Anthropic's documented
# target, not ours. Section 7 gets its own because it is replaced every session and so
# bloats fastest, which a whole-file cap hides inside a total that looks fine.
# TWO CLASSES, NOT THREE. Class S (120) was retired 2026-08-21 on a measurement: a minimal
# FILLED charter - every optional subsection deleted, every prompt answered - measured ~200,
# because 63% of it is blanks and headings that writing less cannot remove. A cap nothing can
# meet gets declared-exempt every time, and a control that is always exempt is not a control.
# The classes are now told apart by HOW LONG A PROJECT RUNS, which is observable, rather than
# by how big it feels: M is 1-8 sessions, L is more than 8.
#
# WHICH ONE IS THE DEFAULT DEPENDS ON WHERE THE WORK HAPPENS, and the generator runs in Claude
# Code: a Code project here usually runs past 8 sessions, so L is the default there and M is
# chosen the moment a project is recognised as short. Cowork is the other way round. M remains
# Anthropic's documented target - being the target and being the default are different facts.
SIZE_CLASS = {"M": 200, "L": 350}
SIZE_CLASS_FOR = {"M": "1-8 sessions - Anthropic's documented target, and the usual Cowork case",
                  "L": "more than 8 sessions - the usual Claude Code case; state why it is L"}
SECTION_7_CAP = 60

HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.S)
COMMENTED = chr(0)   # marks a character Claude never receives


def loaded_lines(text):
    """The number of lines Claude ACTUALLY RECEIVES, which is not the number in the file.

    Block-level HTML comments are stripped before the content is injected into context, so
    they cost nothing and must not count against a cap - which is exactly what makes them
    the right home for a note addressed to a human maintainer. A line counts unless EVERY
    one of its characters sits inside a comment, so an inline comment leaves its line behind
    and a comment occupying whole lines removes them.

    COUNTING THE FILE INSTEAD WOULD MEASURE THE WRONG THING. The cap exists to predict
    adherence, and adherence depends on what was loaded.

    SHARED because two scripts need the same answer: the checker that reports a document
    over its cap, and the generator that must not hand a project a charter already over it.
    Two copies of a measurement is how the two come to disagree.
    """
    t = text.replace("\r\n", "\n").replace("\r", "\n")
    masked = HTML_COMMENT_RE.sub(lambda m: re.sub(r"[^\n]", COMMENTED, m.group(0)), t)
    lines = masked.split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    return sum(1 for ln in lines if COMMENTED not in ln or ln.strip(COMMENTED + " \t"))


class Report:
    """Rows of (doc, name, status, count, problems).

    'doc' is None for a checker that reports on a project rather than per file; the
    renderer groups by it only when at least one row has one. One shape for all three
    checkers, because two shapes is how the two renderers came to differ.
    """

    def __init__(self) -> None:
        self.rows: list[tuple] = []

    def _append(self, name, status, count, problems=(), doc=None):
        """The one place a row is built.

        record() calls THIS and never self.add(), deliberately. A subclass that reorders
        add()'s arguments - which verify_md.py does, because a document checker leads with
        the file - would otherwise have every row built from shuffled arguments the moment
        record() called it. Measured: it produced a Report whose every status read None,
        and all 21 selftest cases failed at once. A base class must not route its own work
        through a method subclasses are invited to change.
        """
        self.rows.append((doc, name, status, count, list(problems)))

    def add(self, name, status, count, problems=(), doc=None):
        self._append(name, status, count, problems, doc)

    def record(self, name, read_count, problems, *, na_reason=None, void_reason=None,
               doc=None):
        """PASS / FAIL / VOID / N-A from a read count and a problem list.

        EVERY CHECK REPORTS ITS DENOMINATOR. A check that examined nothing is VOID, not a
        pass: "0 problems found" over 0 items examined is not a result. A check that
        genuinely does not apply says N/A WITH ITS REASON, which is the difference between
        a decision and an oversight.

        void_reason forces VOID for a check that could not run for a reason of its own - a
        declared list that is not on disk, say. Without it such a check falls through to
        N/A and reads as a decision, when it is an accident.
        """
        if void_reason is not None:
            self._append(name, VOID, read_count, [void_reason], doc)
        elif na_reason is not None:
            self._append(name, NA, read_count, [na_reason], doc)
        elif read_count == 0:
            self._append(name, VOID, 0,
                         ["examined nothing - this check measured no items"], doc)
        elif problems:
            self._append(name, FAIL, read_count, problems, doc)
        else:
            self._append(name, PASS, read_count, [], doc)

    # -- accessors, so a caller never indexes into a tuple ---------------------------

    def statuses(self):
        return [s for _, _, s, _, _ in self.rows]

    def status_of(self, name):
        """The status of the first row with this name, or None. Used by selftests, so a
        change to the row shape cannot silently break every test that reads one."""
        for _, n, s, _, _ in self.rows:
            if n == name:
                return s
        return None

    def by_name(self):
        return {n: s for _, n, s, _, _ in self.rows}

    def count_of(self, status):
        return sum(1 for s in self.statuses() if s == status)

    @property
    def failed(self) -> bool:
        return any(s == FAIL for s in self.statuses())

    @property
    def voided(self) -> bool:
        return any(s == VOID for s in self.statuses())

    @property
    def exit_code(self) -> int:
        if self.failed:
            return RC_FAILED
        return RC_COULD_NOT_RUN if self.voided else RC_OK

    def render(self, name_width=30, max_problems=12) -> str:
        out, current, grouped = [], object(), any(d for d, _, _, _, _ in self.rows)
        for doc, name, status, count, problems in self.rows:
            if grouped and doc != current:
                out.append(f"\n{doc}")
                current = doc
            indent = "  " if grouped else "  "
            out.append(f"{indent}{status:<5} {name:<{name_width}} {count} examined")
            for p in problems[:max_problems]:
                out.append(f"          - {p}")
            if len(problems) > max_problems:
                out.append(f"          - ... and {len(problems) - max_problems} more")
        return "\n".join(out)

    def verdict(self) -> str:
        return {RC_OK: "PASS", RC_FAILED: "FAIL",
                RC_COULD_NOT_RUN: "VOID - a check could not run"}[self.exit_code]


# ------------------------------------------------------------------------ the config

CONFIG_NAME = "verify.config.json"


def read_config_json(f: Path):
    """Parse verify.config.json without crashing on the two ways it is usually malformed.

    'utf-8-sig' strips a byte-order mark if there is one and is identical to 'utf-8' if
    there is not. WINDOWS POWERSHELL WRITES THAT MARK BY DEFAULT, so a config created the
    most obvious way on this platform used to abort the entire run with a traceback. A
    checker that crashes reports nothing at all, which is strictly worse than reporting a
    failure.

    Bad JSON is a check that COULD NOT RUN, not one that passed: exit 2, with the parser's
    own message, which gives the line and column.
    """
    try:
        return json.loads(f.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as e:
        print(f"VOID: {f} is not valid JSON - {e}. Nothing was checked.")
        raise SystemExit(RC_COULD_NOT_RUN)
    except OSError as e:
        print(f"VOID: cannot read {f} - {e}. Nothing was checked.")
        raise SystemExit(RC_COULD_NOT_RUN)


def load_section(root: Path, section: str, defaults: dict) -> dict:
    """Defaults overlaid with this project's tailoring for one checker."""
    cfg = dict(defaults)
    f = root / CONFIG_NAME
    if f.exists():
        cfg.update(read_config_json(f).get(section, {}))
    return cfg


def write_section(root: Path, section: str, defaults: dict, comments: dict) -> None:
    """Add this checker's section to verify.config.json without disturbing the others."""
    f = root / CONFIG_NAME
    existing = read_config_json(f) if f.exists() else {}
    existing.setdefault(section, dict(defaults))
    existing.setdefault(f"_comments_{section}", comments)
    f.write_text(json.dumps(existing, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {f}")


# ----------------------------------------------------------------- the selftest harness

class Case:
    """One check, proved BOTH ways.

    A CHECK THAT CANNOT TELL GOOD FROM BAD IS NOT A CHECK, AND ONLY THE PAIR SHOWS IT.
    A suite of violations alone is passed perfectly by a check that fires on everything -
    it looks like full coverage and proves nothing about the check's judgement. The five
    scripts here were tested one-sidedly almost everywhere before this existed.

    * name    what is being proved, printed as-is
    * probe   takes whatever the builder returns, gives back a status string
    * bad     builds an input that MUST make the check fire
    * good    builds a CONFORMING input that must NOT make it fire
    * want / good_want   the statuses those two must produce

    IF THERE IS NO CONFORMING TWIN, SAY SO IN unpaired_reason. Some cases genuinely have
    none - an empty file has no non-empty version of itself. Leaving both out is refused
    by the runner, so a missing pair is a declared decision and never an oversight. That
    is the same rule this house applies to a check that does not apply.
    """

    def __init__(self, name, probe, bad, good=None, want=FAIL, good_want=PASS,
                 unpaired_reason=None):
        if good is None and not unpaired_reason:
            raise ValueError(
                f"case {name!r} has no conforming input and no unpaired_reason. "
                "State why there is no good twin, or write one - a one-sided case "
                "cannot show the check tells good from bad.")
        self.name, self.probe, self.bad, self.good = name, probe, bad, good
        self.want, self.good_want = want, good_want
        self.unpaired_reason = unpaired_reason


def _arm_dir(tmp: Path, n: int, arm: str) -> Path:
    """A FRESH DIRECTORY PER ARM, because a shared one makes fixture names collide.

    Every arm used to be handed the same directory, so two arms writing a fixture under one
    name REWROTE each other's file. On Windows that is worse than untidy: reopening a file
    the previous arm has just closed raises a transient PermissionError, because a closed
    handle is not always a released one. The runner reports it as CRASHED, so the suite
    fails SOMETIMES - the shape that teaches people to re-run a gate instead of reading it.

    Isolating the arms fixes the class rather than the instance. A builder that wants to
    reach the shared root still can: it is the parent of what it is handed.
    """
    d = tmp / f"case{n:02d}-{arm}"
    d.mkdir(parents=True, exist_ok=True)
    return d


def run_cases(cases, tmp: Path, indent="  ", width=32):
    """Run a case table. Returns (ok, paired, unpaired) and prints one line per result."""
    ok, paired, unpaired = True, 0, 0
    for n, c in enumerate(cases):
        try:
            got = c.probe(c.bad(_arm_dir(tmp, n, "bad")))
        except BaseException as e:                               # noqa: BLE001
            got = f"CRASHED ({type(e).__name__})"
        fired = got == c.want
        ok &= fired
        print(f"{indent}{'OK  ' if fired else 'MISS'} {c.name:<{width}} -> {got}")

        if c.good is None:
            unpaired += 1
            print(f"{indent}     {'':<{width}}    unpaired: {c.unpaired_reason}")
            continue
        paired += 1
        try:
            got2 = c.probe(c.good(_arm_dir(tmp, n, "good")))
        except BaseException as e:                               # noqa: BLE001
            got2 = f"CRASHED ({type(e).__name__})"
        quiet = got2 == c.good_want
        ok &= quiet
        label = f"...and stays quiet on a good one"
        print(f"{indent}{'OK  ' if quiet else 'MISS'} {label:<{width}} -> {got2}")
    return ok, paired, unpaired


def report_pairing(paired, unpaired, indent="  "):
    """Say how much of the suite is two-sided. A number, so it cannot be assumed."""
    total = paired + unpaired
    pct = 100 * paired / total if total else 0
    print(f"{indent}{total} cases: {paired} proved BOTH ways ({pct:.0f}%), "
          f"{unpaired} declared unpaired")


# ------------------------------------------------------------- the shared selftest case

def selftest_config(tmp: Path, section: str, key: str, loader, indent="  ", width=32):
    """A config carrying a BOM must LOAD; a malformed one must exit 2, never traceback.

    'loader' is the calling script's own load_config, so this tests the real path that
    script uses rather than a reimplementation of it standing in for it.
    """
    ok = True
    d = tmp / "cfgtest"
    d.mkdir(exist_ok=True)
    f = d / CONFIG_NAME
    # the exact three bytes Windows PowerShell's default UTF-8 encoder puts in front
    f.write_bytes(b"\xef\xbb\xbf" + json.dumps({section: {key: ["x.md"]}}).encode("utf-8"))
    try:
        got = loader(d)[key]
        good = got == ["x.md"]
    except BaseException as e:                                   # noqa: BLE001
        good, got = False, f"CRASHED ({type(e).__name__})"
    ok &= good
    print(f"{indent}{'OK  ' if good else 'MISS'} {'config with a BOM loads':<{width}} -> {got}")

    f.write_text("{ not json at all", encoding="utf-8")
    try:
        loader(d)
        rc = "no exit - it returned"
    except SystemExit as e:
        rc = e.code
    except BaseException as e:                                   # noqa: BLE001
        rc = f"CRASHED ({type(e).__name__})"
    good = rc == RC_COULD_NOT_RUN
    ok &= good
    print(f"{indent}{'OK  ' if good else 'MISS'} {'broken config exits 2':<{width}} -> {rc} "
          f"(want {RC_COULD_NOT_RUN})")
    return ok


def selftest() -> int:
    """The result model itself, proved. Every checker's verdict rests on these rules, so
    they are tested here once rather than inferred from three places that agree today."""
    print("SELFTEST - the shared result model\n")
    ok = True
    cases = [
        ("denominator: 0 examined is VOID", dict(read_count=0, problems=[]), VOID),
        ("problems make it FAIL", dict(read_count=5, problems=["x"]), FAIL),
        ("clean and non-empty is PASS", dict(read_count=5, problems=[]), PASS),
        ("declared N/A is not a VOID", dict(read_count=0, problems=[],
                                            na_reason="not applicable here"), NA),
        ("forced VOID beats N/A", dict(read_count=0, problems=[],
                                       na_reason="r", void_reason="could not run"), VOID),
    ]
    for label, kwargs, want in cases:
        r = Report()
        r.record("c", **kwargs)
        got = r.status_of("c")
        good = got == want
        ok &= good
        print(f"  {'OK  ' if good else 'MISS'} {label:<34} -> {got}")

    # loaded_lines, proved BOTH ways: five plain lines count five, and the same five
    # wrapped in a block-level HTML comment count zero. A measure that returned the file's
    # line count would pass the first and fail the second, and would push a maintainer to
    # delete a note that was free.
    plain = "\n".join(f"line {i}" for i in range(5))
    for label, text, want in (("loaded_lines counts plain lines", plain, 5),
                              ("loaded_lines ignores a comment", "<!--\n" + plain + "\n-->", 0),
                              ("an inline comment keeps its line", "a <!-- note --> b", 1)):
        got = loaded_lines(text)
        good = got == want
        ok &= good
        print(f"  {'OK  ' if good else 'MISS'} {label:<34} -> {got} (want {want})")

    # safe_stdout, PROVED BOTH WAYS on a stream that really cannot encode the character.
    # The bad arm has to be shown raising, or the good arm proves nothing: on a machine whose
    # terminal is already UTF-8 the write would succeed with or without the fix, and the case
    # would pass while protecting nothing.
    import io
    hazard = "〔RULE: topic〕"          # U+3014, absent from cp1252
    for label, fix, want in (("an unencodable char WOULD crash", False, "UnicodeEncodeError"),
                             ("safe_stdout prints it instead", True, "wrote")):
        stream = io.TextIOWrapper(io.BytesIO(), encoding="cp1252")
        if fix:
            safe_stdout(stream)
        try:
            stream.write(hazard)
            stream.flush()
            got = "wrote"
        except UnicodeEncodeError:
            got = "UnicodeEncodeError"
        except BaseException as e:                               # noqa: BLE001
            got = f"CRASHED ({type(e).__name__})"
        good = got == want
        ok &= good
        print(f"  {'OK  ' if good else 'MISS'} {label:<34} -> {got}")

    for label, statuses, want in (("FAIL outranks VOID", [FAIL, VOID], RC_FAILED),
                                  ("VOID alone exits 2", [VOID, PASS], RC_COULD_NOT_RUN),
                                  ("PASS and N/A exit 0", [PASS, NA], RC_OK)):
        r = Report()
        for s in statuses:
            r.add("c", s, 1)
        good = r.exit_code == want
        ok &= good
        print(f"  {'OK  ' if good else 'MISS'} {label:<34} -> {r.exit_code} (want {want})")

    r = Report()
    r.record("c", 1, ["a problem"], doc="one.md")
    grouped = "one.md" in r.render()
    r2 = Report()
    r2.record("c", 1, ["a problem"])
    ungrouped = "None" not in r2.render()
    ok &= grouped and ungrouped
    print(f"  {'OK  ' if grouped else 'MISS'} {'renders a doc heading when set':<34} -> {grouped}")
    print(f"  {'OK  ' if ungrouped else 'MISS'} {'and prints no None when unset':<34} -> {ungrouped}")

    # THE HARNESS ITSELF, tested on a check that is deliberately broken. This is the whole
    # argument for the case table: a one-sided suite passes a check that fires on
    # EVERYTHING, so the harness must be shown catching one.
    import io
    from contextlib import redirect_stdout

    def honest(x):
        return FAIL if x == "bad" else PASS

    def fires_on_everything(x):
        return FAIL

    tmp = Path(tempfile.mkdtemp(prefix="house_common_selftest_"))
    try:
        with redirect_stdout(io.StringIO()):
            good_ok, _, _ = run_cases(
                [Case("honest check", honest, lambda t: "bad", lambda t: "good")], tmp)
            bad_ok, _, _ = run_cases(
                [Case("broken check", fires_on_everything,
                      lambda t: "bad", lambda t: "good")], tmp)
            _, paired, unpaired = run_cases(
                [Case("no twin", honest, lambda t: "bad",
                      unpaired_reason="stated on purpose")], tmp)
        checks = [
            ("harness passes an honest check", good_ok, good_ok),
            ("harness FAILS one that always fires", not bad_ok, bad_ok),
            ("a declared unpaired case is counted", (paired, unpaired) == (0, 1),
             (paired, unpaired)),
        ]
        for label, good, got in checks:
            ok &= good
            print(f"  {'OK  ' if good else 'MISS'} {label:<34} -> {got}")

        # and refusing a case with NO pair and NO reason is what makes pairing systematic
        try:
            Case("silent omission", honest, lambda t: "bad")
            refused = False
        except ValueError:
            refused = True
        ok &= refused
        print(f"  {'OK  ' if refused else 'MISS'} {'refuses a silent one-sided case':<34} "
              f"-> {refused}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print("\nSELFTEST: " + ("PASS" if ok else "FAIL"))
    return RC_OK if ok else RC_FAILED


if __name__ == "__main__":
    # --selftest is accepted, and ignored, so this file is DISCOVERED like every other
    # script in the house. run_tests.py finds suites by looking for that flag, and the
    # shared module every checker imports was the one thing it did not run.
    sys.exit(selftest())
