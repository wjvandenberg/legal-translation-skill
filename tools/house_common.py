#!/usr/bin/env python3
"""house_common.py - the plumbing every house checker shares.  CHECKER VERSION 17 (2026-09-09)

WHAT IS HERE AND WHY IT IS HERE. The result model (PASS / FAIL / VOID / N-A / JUDGE, the
denominator rule, the exit-code convention), reading verify.config.json, and the selftest that
proves a config still loads. None of it is specific to documents, code or deliverables - it is
the same in all three, and before this file it WAS the same in all three, three times over.

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

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

PASS, FAIL, VOID, NA, JUDGE = "PASS", "FAIL", "VOID", "N/A", "JUDGE"

# JUDGE - the fifth verdict, and the only one that is not the checker's own answer.
#
# WHAT IT MEANS. The check RAN, it examined items, and what it found is a CANDIDATE that no
# script can settle: the tool can see the shape and not the truth. A person must decide. It
# is not a weaker FAIL and it is not a softer VOID - a VOID could not look, a JUDGE looked
# and found something whose meaning is outside a script's reach.
#
# IT DOES NOT CHANGE THE EXIT CODE, AND THAT IS THE WHOLE DESIGN. A JUDGE that printed as a
# failure would turn every run red on a claim nobody can discharge mechanically, and a gate
# that is red every time gets silenced - which costs the four real verdicts their meaning
# too. So JUDGE exits 0, exactly like PASS and a declared N/A.
#
# WHICH LEAVES ONE PROBLEM, AND JUDGE_MARK BELOW IS THE ANSWER TO IT. A caller reading only
# an exit code cannot see a JUDGE at all, so a run that hands three claims to a person looks
# identical to a clean one. Silence is how this severity would fail: not by blocking too
# much, but by being invisible. The mark is a line the report PRINTS, which run_tests.py
# reads - the artefact rather than the exit code, which is this house's rule anyway.
#
# THE ABUSE ROUTE, NAMED BECAUSE NOTHING MECHANICAL STOPS IT. Any FAIL can be made to stop
# blocking by declaring it a JUDGE. Nothing here can tell a claim a script CANNOT settle
# from one the author did not want to. What is enforced is only that the reason is stated:
# a blank judge_reason is refused, so the excuse is at least written down where a reader
# will meet it.

# The protocol between a checker and whatever runs it. A checker prints it; run_tests.py
# parses it. BOTH SIDES LIVE HERE, deliberately: a wire format with the writer in one file
# and the reader in another is two things that stop being the same thing, which is the
# measurement that produced this module in the first place.
JUDGE_MARK = "JUDGE-CLAIMS:"
JUDGE_MARK_RE = re.compile(r"^\s*" + re.escape(JUDGE_MARK) + r"\s*(\d+)\b", re.M)


def judge_count(text: str) -> int:
    """How many claims the report in 'text' handed to a person. 0 if it handed over none.

    A PARSER RATHER THAN A SUBSTRING SEARCH, because the loose version was tried in this
    house and misfires: the word JUDGE appears in a docstring, in a case name and in this
    very comment, so anything sniffing for it reports a judgement from a file that merely
    discusses one. The mark is anchored to the start of a line and must carry a number.
    """
    m = JUDGE_MARK_RE.search(text or "")
    return int(m.group(1)) if m else 0


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
#   0  every check passed, was a declared N/A, or handed a claim to a person (JUDGE)
#   1  at least one check FAILED - it ran, and found something
#   2  at least one check COULD NOT RUN, and none failed
# "It could not run" and "it failed" are different facts, and a caller that cannot tell
# them apart cannot react correctly to either. A FAIL outranks a VOID, because a defect you
# have found beats one you could not look for. Both are non-zero, so any gate wired to
# "non-zero blocks" behaves exactly as it did before the distinction existed.
# THERE IS DELIBERATELY NO FOURTH CODE FOR JUDGE. It was considered and refused: a third
# non-zero code makes every run with an open question block, and a gate that blocks on a
# question nobody can close mechanically is a gate that gets removed. JUDGE is visible in
# the report and in JUDGE_MARK, not in the exit status.
RC_OK, RC_FAILED, RC_COULD_NOT_RUN = 0, 1, 2


# ------------------------------------------------------------------- the size of a charter

# A CLAUDE.md is loaded in full and never truncated, so being over a cap produces no error and
# no symptom - it is simply followed less well. That is why size is checked at all.
#
# THE CLASS NO LONGER CARRIES A WHOLE-FILE LINE CAP, AND THE NUMBERS ARE GONE RATHER THAN
# RAISED (2026-09-02). M was 200 and L was 350, and they were retired on the measurement that
# had already retired class S (120) in 2026-08-21: M's 200 was met by 0 of 11 archetypes and
# L's 350 by 3 of 11, while the generator's own smallest emit is 78% blank lines, headings,
# tables and markers - so deleting EVERY word of prose still leaves 242 lines against 200.
# A cap nothing can meet is declared-exempt every time, and a control that is always exempt is
# not a control. It was also a contradiction: the emitted verify.config.json sets the file cap
# to REPORT, so a generated charter announced a gate its own checker had disabled.
#
# THE NUMBERS ARE NOT KEPT "FOR REFERENCE". A constant named SIZE_CLASS holding {M: 200} is
# how a retired cap gets silently re-wired by the next person who needs a number - which is
# exactly what SECTION_7_CAP = 60 had already become here: defined once, read by nothing, and
# disagreeing with the 35 the generator actually emits. Both are deleted.
#
# WHAT THE CLASS STILL DECIDES IS WHICH RELOCATION ROUTES EXIST. M is mostly Cowork, which has
# no path-scoped rules and no hooks, so an M project reaches for a companion document, a skill
# or the plan instead. L is mostly Claude Code, where every route is open and which is why the
# generator defaults to L. Being Anthropic's documented target and being the default are
# different facts, and M is the first without being the second here.
#
# WHAT GATES INSTEAD is per-section: section 7 at 35, because it is REPLACED every session and
# so is nearly free to trim, and the other six at their MEASURED size once a charter is filled.
SIZE_CLASS_FOR = {"M": "1-8 sessions - Anthropic's documented target, and the usual Cowork case",
                  "L": "more than 8 sessions - the usual Claude Code case; state why it is L"}

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
               judge_reason=None, doc=None):
        """PASS / FAIL / VOID / N-A / JUDGE from a read count and a problem list.

        EVERY CHECK REPORTS ITS DENOMINATOR. A check that examined nothing is VOID, not a
        pass: "0 problems found" over 0 items examined is not a result. A check that
        genuinely does not apply says N/A WITH ITS REASON, which is the difference between
        a decision and an oversight.

        void_reason forces VOID for a check that could not run for a reason of its own - a
        declared list that is not on disk, say. Without it such a check falls through to
        N/A and reads as a decision, when it is an accident.

        judge_reason SAYS THE PROBLEMS ARE CANDIDATES, NOT FINDINGS - that this check can
        see a shape it cannot adjudicate, and a person must. It applies only WHEN THERE ARE
        CANDIDATES: a judging check that found nothing is a PASS, not a standing question.
        That is not a convenience, it is what makes the check provable BOTH WAYS - a check
        that hands over a claim whatever it reads cannot be shown to tell good from bad,
        and this house does not keep checks like that.

        THE PRECEDENCE, AND EACH STEP OF IT IS A CLAIM. A VOID outranks a JUDGE because a
        check that could not look has nothing to hand anyone. A declared N/A outranks it
        because a check that does not apply here has no candidates to offer. And an empty
        denominator is still VOID, never a JUDGE: nothing to judge is not a judgement.
        """
        for label, reason in (("na_reason", na_reason), ("void_reason", void_reason),
                              ("judge_reason", judge_reason)):
            # A REASON THAT IS SET BUT BLANK IS THE SILENT VERSION OF NO REASON AT ALL, and
            # it reads as a decision on the report. Refused for all three kinds rather than
            # for the new one only: this is the same guard Case applies to unpaired_reason,
            # and a guard inside the shared thing covers the call sites that do not exist
            # yet. None stays legal - `na_reason=None if files else "..."` is the idiom
            # every checker here already uses to mean "applies, so judge it normally".
            if reason is not None and not str(reason).strip():
                raise ValueError(
                    f"check {name!r} passed a blank {label}. State the reason or pass "
                    f"None - an empty one prints as a decision nobody made.")
        if void_reason is not None:
            self._append(name, VOID, read_count, [void_reason], doc)
        elif na_reason is not None:
            self._append(name, NA, read_count, [na_reason], doc)
        elif read_count == 0:
            self._append(name, VOID, 0,
                         ["examined nothing - this check measured no items"], doc)
        elif problems and judge_reason is not None:
            self._append(name, JUDGE, read_count, [judge_reason] + list(problems), doc)
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
    def judged(self) -> bool:
        return any(s == JUDGE for s in self.statuses())

    @property
    def exit_code(self) -> int:
        # JUDGE is absent from this method ON PURPOSE and the omission is the feature: see
        # the note beside the constant. A claim handed to a person does not block.
        if self.failed:
            return RC_FAILED
        return RC_COULD_NOT_RUN if self.voided else RC_OK

    def judge_line(self):
        """The machine-readable mark, or None when nothing was handed over.

        Printed by every checker AFTER its verdict, so a run that hands claims to a person
        cannot look - to a script or to a reader - like a run that found none. None rather
        than an empty string so a caller cannot print a blank line and believe it said
        something.
        """
        n = self.count_of(JUDGE)
        if not n:
            return None
        names = ", ".join(sorted({nm for _, nm, s, _, _ in self.rows if s == JUDGE}))
        return (f"{JUDGE_MARK} {n} - a person must settle these, and NOTHING here will "
                f"fail until they do: {names}")

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

    def as_dict(self, checker: str = "") -> dict:
        """The report as data, so something other than a person can read it.

        THE GAP THIS CLOSES. A checker's verdict reaches the outside world as an EXIT CODE
        and a page of prose. That is enough to know a run failed and useless for knowing
        WHAT failed - so anything wanting to judge a run against a declared set of tolerated
        failures had to re-invoke the checker once per file and parse its printed output.
        Parsing printed output is a second reader of a format that has no writer, which is
        the drift this whole module exists to stop.

        WHY IT SITS HERE RATHER THAN IN A WRAPPER. The row model is this class's; a wrapper
        that reconstructed rows from text would be a THIRD place that knows what a row is.
        Both sides of the wire live in one file, exactly as JUDGE_MARK does above.

        WHAT IT MAY CARRY IS THE SAME AS WHAT THE RENDER PRINTS - deliberately, and it is a
        confidentiality rule rather than a convenience. A forbidden-phrase finding is
        reported by POSITION and never by text, because echoing the phrase into a terminal
        or a CI log leaks it by a route nothing can clean up afterwards. Serialising the
        problems list carries exactly that and adds nothing, so the rule cannot be lost by
        the report acquiring a second output.
        """
        # TWO DIFFERENT ANSWERS, NAMED APART BECAUSE THEY LEGITIMATELY DIFFER. `row_verdict`
        # is what the ROWS say; `exit_code` is what the PROCESS returns, and a checker may
        # return a code its rows do not imply - a run where every row is a declared N/A
        # exits 2, "nothing was declared", while the rows alone read PASS. Emitting that
        # pair as `verdict: PASS, exit_code: 2` reads as a contradiction and invites a
        # wrapper to trust the wrong one. A CONSUMER JUDGES ON exit_code AND rows.
        return {
            "checker": checker,
            "row_verdict": self.verdict(),
            "exit_code": self.exit_code,
            "judge_claims": self.count_of(JUDGE),
            "rows": [{"doc": doc, "check": name, "status": status,
                      "examined": count, "problems": list(problems)}
                     for doc, name, status, count, problems in self.rows],
        }

    def failing_keys(self, checker: str = "") -> list[str]:
        """Every FAILING row as one stable string, at whatever granularity the checker has.

        THE GRANULARITY IS THE CHECKER'S, NOT THIS METHOD'S, and that is the point. Measured
        across one repository: a document checker fails per DOCUMENT, a code checker per
        CHECK ROW, and a deliverable checker can be VOID as a whole run. A key shaped around
        files would have covered one of those three, so the key is `checker::doc::check`
        with the parts that do not apply left empty rather than omitted - a fixed arity
        means a declaration cannot silently match the wrong thing.

        VOID IS NOT INCLUDED, AND THE OMISSION IS THE RULE: a check that could not run has
        not failed, and must not become declarable as a tolerated failure. Merging the two
        would let "the instrument was broken" be written down once and then stop being
        reported - which is the failure this house calls VOID rather than CLEAN.
        """
        return [f"{checker}::{doc or ''}::{name}"
                for doc, name, status, _, _ in self.rows if status == FAIL]

    def verdict(self) -> str:
        """The one line a reader takes away, and it must not swallow an open question.

        A JUDGE never changes the exit code, so without this the headline over a run that
        handed three claims to a person would read a bare PASS. It is APPENDED rather than
        substituted, because the four verdicts still mean what they meant: the run did pass,
        AND something is waiting on somebody.
        """
        base = {RC_OK: "PASS", RC_FAILED: "FAIL",
                RC_COULD_NOT_RUN: "VOID - a check could not run"}[self.exit_code]
        n = self.count_of(JUDGE)
        return base if not n else f"{base} - and {n} claim(s) need a person (JUDGE)"


# --------------------------------------------------------------- the machine-readable arm

REPORT_FLAG = "--report-json"


def wants_report_json(argv) -> bool:
    """Is this run being asked for data rather than prose?

    ONLY IN FIRST POSITION, and that is not tidiness. A wrapper hands a checker another
    program's arguments, and a flag scanned for anywhere in the list is one the PAYLOAD can
    contain: measured in this house, a `--selftest` sitting inside a wrapped command ran the
    WRAPPER's selftest, printed PASS, exited 0 and recorded nothing. Every signal said it had
    worked. A flag is only a flag in first position.
    """
    return bool(argv) and argv[0] == REPORT_FLAG


def finish(rep, checker: str, rc: int, quiet: bool) -> int:
    """A checker's single exit point: prose already printed, or JSON instead.

    THE EXIT CODE IS PASSED IN RATHER THAN RECOMPUTED, and that is a correctness rule, not
    style. Three checkers here return a code their own report does not imply - a run where
    every row is a declared N/A exits 2, "nothing was declared", while the report alone says
    PASS. Deriving the code from the report would make the JSON disagree with a bare run,
    and a wrapper judging on the JSON would then reach a different verdict from the gate it
    exists to serve.

    NOTHING ELSE ON STDOUT in JSON mode, so a caller can parse the stream without being
    taught to skip a banner - a parser that must strip prose breaks the day the prose is
    reworded.

    THE CHECKER'S OWN VERDICT IS UNTOUCHED EITHER WAY, AND THAT IS THE WHOLE SAFETY PROPERTY
    HERE. Whether a failure is tolerated is decided DOWNSTREAM, so running the checker bare
    always tells the truth - the difference between this and an `expected_failures` key
    inside the checker, where the checker itself would print PASS and there would be no
    honest question left to ask.
    """
    if quiet:
        print(json.dumps(rep.as_dict(checker) | {"exit_code": rc}, indent=2,
                         ensure_ascii=False))
    return rc


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


def read_phrase_list(path: Path):
    """One phrase per line; '#' comments and blanks ignored. None if unreadable.

    A '#' LINE IS A COMMENT, NOT A NEEDLE, and that distinction has been got wrong once
    with visible consequences: reading every line as a needle turned a list of six into a
    scan reporting hundreds of hits across every tracked file, while a tool parsing the
    same file correctly beside it printed six. A second parser for a list something already
    parses is how the two come to disagree - which is why this lives here and not in a
    caller.
    """
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError:
        return None
    out = []
    for ln in raw.splitlines():
        ln = ln.strip()
        if ln and not ln.startswith("#"):
            out.append(ln)
    return out


def resolve_list(root: Path, cfg, inline_key, file_key, env_var, kind):
    """Return (items, sources, void_reason) for ONE config-driven string list.

    Inline and external lists are MERGED rather than one overriding the other: a project
    may legitimately have a public list it is happy to commit and a private one it is not,
    and making them exclusive would force the public half out of the repository too.

    A list declared and not found is VOID, never N/A and never a silent pass. That is the
    whole trap an external list opens - the protection quietly stops running on any
    machine that lacks the file, and the report still says PASS.

    ONE FUNCTION FOR EVERY CLAIM KIND, and that is the point of it rather than a tidiness
    preference. Each kind needs the same three sources, the same merge rule and the same
    VOID trap; written twice, the second copy is where the trap comes to mean something
    slightly different, and nothing reports that - both copies keep passing their own
    tests. This house has measured that shape three times, so a guard inside the shared
    thing beats a second correct copy.

    MOVED HERE FROM THE DOCUMENT CHECKER ON 2026-09-02, WHEN A SECOND CHECKER NEEDED IT.
    It had one caller and the sentence above was already written; a whole-tree
    confidentiality scanner needs the identical resolver, and the paragraph arguing against
    a second copy would have been the first thing a second copy contradicted.

    'sources' records WHERE each item came from, per item, because a report's rules differ
    by origin: 'config' is already committed and may be named, 'env' and 'file' are outside
    the repository and may not.
    """
    items = [p for p in cfg.get(inline_key, []) if p.strip()]
    sources = ["config"] * len(items)

    declared = os.environ.get(env_var, "").strip()
    origin = "env"
    if not declared:
        declared = str(cfg.get(file_key, "") or "").strip()
        origin = "file"
    if not declared:
        return items, sources, None

    path = Path(declared)
    if not path.is_absolute():
        path = root / path
    extra = read_phrase_list(path)
    if extra is None:
        # THE FULL PATH IS WITHHELD, AND THIS IS THE SAME CLASS mask_phrases() FIXES with the
        # one difference that decides the shape: when the list cannot be READ there are no
        # needles to mask WITH, so the only safe form is not to print it. Measured in this
        # house - the list lives under a home directory whose own username is on the list, so
        # the message announcing that the guard had stopped running would itself have leaked
        # what the guard was for. The env var or config key names WHERE to look, which is what
        # a reader needs; the basename names WHICH file without naming who owns it.
        where = env_var if origin == "env" else file_key
        return [], [], (f"{where} points at a file named {path.name!r} which cannot be read "
                        f"- the {kind} list this check needs is not here, so it has NOT run. "
                        f"The full path is withheld: it may itself contain a {kind} string")
    items += extra
    sources += [origin] * len(extra)
    return items, sources, None


class isolated_env:
    """Clear named environment variables for a block, and restore them exactly.

    THE DEFECT THIS EXISTS FOR, AND IT IS A SELFTEST DEFECT RATHER THAN A CHECKER ONE.
    resolve_list() reads a path from the ENVIRONMENT in preference to the config, so that CI
    can supply a sensitive list as a secret. That is right for a real run and wrong for a
    selftest: a variable the CALLER set for a real scan silently replaces the fixture list a
    case had just written, and the case then measures the wrong list.

    MEASURED, BOTH WAYS, ON A REAL SUITE: with the variable unset the document checker's
    selftest exits 0; with it set to the house list it exits 1 on exactly two rows - "list
    read from a file" expecting FAIL and reading PASS, and "missing list is VOID" expecting
    VOID and reading PASS. **Both failures are in the direction where a guard stops
    guarding**, so a one-sided suite would have gone green while testing nothing.

    AND IT BITES ON THE HOUSE'S OWN DOCUMENTED WORKFLOW, which is what makes it worth a
    shared helper: the added-lines gate, the whole-tree audit and the confidentiality scan
    all tell you to set that variable - so anyone who does, and then runs the test runner in
    the same shell, gets a red suite for a reason that has nothing to do with the code. The
    failure looks INTERMITTENT, which is worse than reproducible: it gets dismissed as a
    flake instead of diagnosed.

    A SAVE AROUND THE ONE CASE THAT SETS THE VARIABLE IS NOT ENOUGH, and that is exactly what
    the affected suite already had. Every OTHER case ran on whatever the caller left behind.
    Wrap the WHOLE suite, so a case added later cannot inherit the trap.

    RESTORE IS EXACT: a variable that was absent is left absent, not set to "".
    """

    def __init__(self, *names: str):
        self.names = names
        self.prior: dict[str, str] = {}

    def __enter__(self):
        for n in self.names:
            if n in os.environ:
                self.prior[n] = os.environ[n]
                del os.environ[n]
        return self

    def __exit__(self, *_exc):
        for n in self.names:
            if n in self.prior:
                os.environ[n] = self.prior[n]
            else:
                os.environ.pop(n, None)
        return False


def mask_phrases(text: str, phrases) -> str:
    """Replace every forbidden phrase inside `text` with its POSITION in the list.

    THE GAP THIS CLOSES IS THE POSITIONS-ONLY RULE'S OWN BLIND SPOT. A confidentiality
    report is built to print a phrase's POSITION and never its text - and every finding it
    prints is LOCATED BY A FILE PATH. Where a path segment is itself a forbidden phrase, the
    report leaks it by the very route that rule exists to close: a terminal, a CI log, a
    pasted failure, or a document naming which files carry a phrase. Measured: two tracked
    paths in one project carried an identifier in the FILENAME, and both were printed
    verbatim by a report that had already declared it prints positions only.

    SO IT IS A GUARD IN THE SHARED THING RATHER THAN A PATCH AT EACH CALL SITE. Every
    checker that names a file names a path, so the next caller is not hypothetical; a fix
    applied only where it was noticed leaves callers 2 to N leaking, and each surfaces later
    as a new bug with nothing connecting it to this one.

    LITERAL AND CASE-INSENSITIVE, NEVER A PATTERN. Each needle is escaped before use: a
    backslash in a Windows path is a character, and a regex reading of it asks for
    whitespace where a separator was meant, matches nothing, and leaves the text unmasked
    while reporting success - this house's oldest silent-zero.

    ONE PASS, LONGEST NEEDLE FIRST. One alternation rather than a loop of replacements, so
    no substitution can be re-scanned and half-masked from the inside out, and so a needle
    that CONTAINS a shorter one is reported as itself.
    """
    kept = [(i + 1, p) for i, p in enumerate(phrases) if p and p.strip()]
    if not text or not kept:
        return text
    kept.sort(key=lambda pair: len(pair[1]), reverse=True)
    index = {p.lower(): i for i, p in kept}
    pattern = "|".join(re.escape(p) for _i, p in kept)
    return re.sub(pattern,
                  lambda m: f"<phrase #{index.get(m.group(0).lower(), 0)}>",
                  text, flags=re.I)


def list_fingerprint(phrases) -> str:
    """A stable identity for the LIST a verdict was taken against - never the needles.

    THE DEFECT THIS NAMES: A SCAN MEASURES A LIST AGAINST A TREE, AND ONLY ONE OF THE TWO
    WAS EVER RECORDED. Measured the day this was written - adding ONE needle took one
    project's finding from 27 locations in 6 files to 87 in 12, and turned another, closed
    and verified and force-pushed clean the day before, RED again on two arms with nothing
    in it changed. A CLEAN verdict carrying no record of the list behind it cannot be told
    from a current one, so the one-pass argument that justifies every irreversible history
    rewrite in this house is only ever as good as the list on the day the pass ran.

    A HASH AND NOT A COPY, AND THE CONSTRAINT IS THE WHOLE DESIGN: a copy of the list in a
    report is precisely the leak this plumbing exists to prevent. The count travels beside
    it because a hash alone says two runs differ and never by how much.

    ORDER-SENSITIVE ON PURPOSE. A report cites a needle BY POSITION - 'phrase #4 of 7' - so
    the same set in a different order makes '#4' mean something else. A fingerprint that
    normalised the order away would call two mutually unreadable reports identical, which is
    the opposite of what it is for.
    """
    kept = [p for p in phrases if p and p.strip()]
    if not kept:
        return "none"
    digest = hashlib.sha256("\n".join(kept).encode("utf-8")).hexdigest()
    return digest[:12]


def write_section(root: Path, section: str, defaults: dict, comments: dict) -> None:
    """Add this checker's section to verify.config.json without disturbing the others.

    IT WRITES BYTES, AND THAT IS A REPAIR RATHER THAN A STYLE CHOICE (v17, 2026-09-09). It
    used `Path.write_text`, which opens in TEXT mode - so on Windows every newline it wrote
    became CRLF and this helper silently rewrote EVERY LINE ENDING in a file it had been
    asked only to ADD a section to. Measured on a real project: a pure-LF 45-line config
    came back pure-CRLF at 77 lines, the content perfectly intact, so every content check
    passed and only a line-endings check saw it - while to git every line in the file had
    changed, which is a diff nobody can review.

    THE FIX IS IN THE SHARED HELPER BECAUSE EVERY `--write-config` IN THE HOUSE GOES
    THROUGH IT - eight callers on the day it was found, and caller nine is covered for
    free. Patching whichever checker happened to bite would have left the other seven.

    AND IT PRESERVES WHAT THE FILE ALREADY USED rather than imposing LF, because the first
    line of this docstring is the contract: a config that was CRLF must stay CRLF. Only a
    file that did not exist gets LF, which is what json.dumps itself produces.
    """
    f = root / CONFIG_NAME
    raw = f.read_bytes() if f.exists() else b""
    existing = read_config_json(f) if f.exists() else {}
    existing.setdefault(section, dict(defaults))
    existing.setdefault(f"_comments_{section}", comments)
    body = (json.dumps(existing, indent=2) + "\n").encode("utf-8")
    crlf = raw.count(b"\r\n")
    if crlf and crlf > raw.count(b"\n") - crlf:
        body = body.replace(b"\n", b"\r\n")
    f.write_bytes(body)
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


# ------------------------------------------------- scanning only what a change ADDED
#
# WHY THIS IS HERE AND NOT IN ONE CHECKER. Whole-file scanning drowns a result in
# pre-existing hits: measured on the project this technique came from, eight whole files
# gave 6 hits and the 102 added lines gave 0. Every checker that scans text inherits the
# problem, so the diff machinery is shared and the needle matching stays with whoever owns
# the needles.
#
# AND THE BASELINE IS THE DANGEROUS PART, not the diffing. A before-and-after check once
# read its "before" from HEAD; that worked only while the rewrite was uncommitted, and once
# committed it compared the new file against itself and reported 100% carried. Nothing
# failed - an empty diff reads exactly like a clean one.

HUNK_RE = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@")

# EVERY git CALL DISABLES PATH QUOTING, AND IT IS A GUARD IN THE SHARED THING RATHER THAN A
# PATCH AT EACH CALL SITE (v16, measured both ways).
#
# core.quotePath DEFAULTS TO TRUE, so every git command that OUTPUTS a path - ls-files,
# rev-list --objects, diff --name-only, status - wraps any path holding a byte above 0x80 in
# double quotes and escapes it in octal. A filename carrying an em dash comes back as
#     "Some Name \342\200\224 More.md"
# which is not a path. A caller that opens it gets OSError, and a caller that pattern-matches
# it silently fails to match. MEASURED: a repository of four tracked files whose three
# non-ASCII names were dropped, leaving a confidentiality scan reporting "PASS, 1 examined"
# over 4 - the denominator was wrong and the verdict read clean.
#
# IT IS FIXED HERE BECAUSE THE CALLERS DO NOT LOOK WRONG. Three sites in one checker alone
# read a path out of git, none of them mentions quoting, and each would have to be found. A
# guard in the shared call covers the sites that do not exist yet, which is the whole
# argument for fixing the class rather than the caller that bit.
#
# WHY NOT -z EVERYWHERE: -z is per-command and several of these commands do not take it
# (rev-list --objects has none), so a NUL-delimited fix would have to be argued per call
# site - which is the state this replaced. core.quotePath=false is accepted by every git
# command because it is a config override, not a flag.
#
# WHAT IT DOES NOT FIX, WHICH IS WHY scan_tree ALSO GAINED A GUARD: quotePath=false stops
# the quoting of high bytes ONLY. A path holding a control character, a double quote or a
# backslash is still quoted, and those are unreachable on Windows rather than impossible in
# general - so the residual case must be REPORTED by whoever opens the file, never skipped.
NO_QUOTE_PATH = ("-c", "core.quotePath=false")


def git(root: Path, *args):
    """git, with stdin closed and both streams captured. Never raises on a non-zero exit.

    stdin=DEVNULL because git will happily open a pager or prompt for credentials against
    an inherited terminal, and a checker that stops to ask a question inside an unattended
    run hangs it rather than failing it.

    encoding="utf-8", errors="replace" AND NOT A BARE text=True, and this one is bought.
    text=True decodes with the LOCALE codepage - cp1252 on this platform - so a UTF-8 byte
    outside it raises UnicodeDecodeError INSIDE subprocess's reader thread, where nothing
    catches it. The call then returns with returncode 0 and stdout None: a git run that
    reports SUCCESS AND NO OUTPUT. Measured here on a document holding one such byte, and
    the crash was the LUCKY outcome - a caller writing `r.stdout or ""` would have read zero
    added lines from a file full of them and reported a CLEAN scan over content nothing
    examined.

    NO_QUOTE_PATH is prepended so a path this returns is a PATH (v16). See the comment on
    that constant: the two failures are the same shape - a git call that succeeds while
    handing back something the caller cannot use, and reports nothing.
    """
    return subprocess.run(["git", *NO_QUOTE_PATH, *args], cwd=str(root), capture_output=True, text=True, encoding="utf-8", errors="replace",
                          stdin=subprocess.DEVNULL)


def git_bytes(root: Path, args, payload: bytes = b""):
    """git, RAW - stdout as bytes, with `payload` fed on stdin. For `cat-file --batch`.

    A SEPARATE FUNCTION RATHER THAN A FLAG ON git(), because the two differ in what they
    guarantee and a caller must pick deliberately. git() decodes with errors="replace",
    which is right for a diff a person will read and WRONG here: `cat-file --batch`
    interleaves a text header with RAW OBJECT CONTENT and the caller walks it by the byte
    length that header states. Replacing an undecodable byte changes the string's length,
    so every offset after the first binary blob is wrong - and the walk does not crash, it
    silently reads the next object from the middle of the last one and scans garbage. That
    is a clean-looking zero over a population nothing examined.

    stdin carries the object list because a repository can hold more object names than a
    command line can take, and the failure there is also silent: the shell truncates.

    IT TAKES NO_QUOTE_PATH TOO, and for a reason that is not symmetry: `cat-file --batch`
    echoes the object NAME it was given back in its header, so a caller that fed it a
    quoted path reads that quoted path back and matches it against nothing.
    """
    return subprocess.run(["git", *NO_QUOTE_PATH, *args], cwd=str(root), input=payload,
                          capture_output=True)


def resolve_revision(root: Path, spec: str):
    """A revision spec -> (full 40-character sha, error). Exactly one of the two is set.

    RESOLVED AND THEN PRINTED BY THE CALLER, because 'origin/main' names a different commit
    tomorrow. A report that says which SHA it compared against can be re-run; one that says
    'origin/main' cannot, and the difference only shows up when somebody disputes a result.
    """
    if not spec.strip():
        return None, None
    r = git(root, "rev-parse", "--verify", spec.strip() + "^{commit}")
    if r.returncode != 0:
        return None, (f"baseline {spec!r} does not resolve to a commit in this repository "
                      f"- nothing was compared")
    return r.stdout.strip(), None


def baseline_guard(root: Path, sha: str):
    """None if the baseline is genuinely older than the working tree, else the reason.

    THE GUARD IS MECHANICAL, AND THAT IS THE POINT OF IT. The rule it enforces is "pin the
    baseline to a revision, never to HEAD or the current file" - and forbidding the WORD
    'HEAD' enforces nothing: 'origin/main' pointing at HEAD, a tag on HEAD, or a SHA typed
    from the last commit all defeat it while reading as a proper revision. What actually
    distinguishes a real baseline is that the working tree DIFFERS FROM IT, so that is what
    is tested.

    AND THE VERDICT IS VOID, NEVER PASS. An empty diff means this arm examined nothing, and
    "no added lines, therefore no forbidden phrase was added" is the exact sentence the
    incident above produced. A check that could not look has not passed.
    """
    r = git(root, "diff", "--quiet", sha)
    if r.returncode == 0:
        return (f"the working tree is IDENTICAL to baseline {sha[:12]} - so there are no "
                f"added lines to scan and this arm examined nothing. Pin the baseline to a "
                f"revision the change is actually measured against, not to the state you "
                f"are in")
    if r.returncode != 1:                       # 1 = differences, which is what we want
        return (f"could not diff against baseline {sha[:12]} (git exited "
                f"{r.returncode}) - nothing was compared")
    return None


def added_line_runs(root: Path, sha: str, rel: str):
    """The lines this change ADDS to one file, as CONTIGUOUS RUNS of (line number, text).

    Runs rather than one flat list, and it is a correctness point rather than tidiness. The
    caller collapses whitespace before matching, so a phrase broken by a hard wrap is still
    found; collapse a flat list and two added lines a thousand lines apart join into a
    phrase nobody ever wrote. Inside a run that joining is a WRAP and wanted; across a gap
    it is an invention. Line numbers are the NEW file's, so a hit still points at something
    a reader can open.
    """
    r = git(root, "diff", "--unified=0", sha, "--", rel)
    if r.returncode not in (0, 1) or r.stdout is None:
        # stdout None WITH returncode 0 is the decode failure described on git() above. It
        # must return None - which the caller renders as VOID - and never fall through to
        # an empty scan, because "no added lines" and "the lines could not be read" look
        # identical from outside. The guard lives in the SHARED helper rather than at the
        # call site: it covers the callers that do not exist yet.
        return None
    runs, cur, nxt = [], [], None
    for ln in r.stdout.splitlines():
        m = HUNK_RE.match(ln)
        if m:
            if cur:
                runs.append(cur)
                cur = []
            nxt = int(m.group(1))
            continue
        if ln.startswith("+++"):
            continue
        if ln.startswith("+") and nxt is not None:
            cur.append((nxt, ln[1:]))
            nxt += 1
    if cur:
        runs.append(cur)
    return runs



# =========================================================== the selftest, in named parts
#
# SPLIT 2026-09-01, from one 230-line function into nine along the seams the module already
# had. The old shape was the third-longest function in the folder and it was not one idea:
# the status model, the JSON arm, two measures, the exit codes, the JUDGE mark, the refusals,
# the renderer and the case harness were simply stacked in one body.
#
# WHY THIS FILE DOES NOT USE THE CASE TABLE, which every other suite in the house does. The
# table lives HERE. Testing run_cases by running it through run_cases means a harness that is
# broken in both halves agrees with itself and passes - the one place where the house's own
# preferred shape is the wrong tool. So these stay imperative, and _selftest_case_harness()
# drives run_cases DELIBERATELY, on a check built to be broken, which is a different thing
# from using it as the harness for its own assertions.
#
# Each part owns its own `ok`, prints its own rows, and returns a bool. The order below is
# the order the rows were printed in before the split, so the output is comparable line for
# line - which is what made "not one assertion lost" a measurement rather than a hope.


def _selftest_status_model():
    """The severity rules every checker's verdict rests on."""
    def _rowless():
        """A report whose row carries no document - a code checker's shape."""
        r = Report()
        r.record("whole-run check", 2, ["a problem"])
        return r

    ok = True
    cases = [
        ("denominator: 0 examined is VOID", dict(read_count=0, problems=[]), VOID),
        ("problems make it FAIL", dict(read_count=5, problems=["x"]), FAIL),
        ("clean and non-empty is PASS", dict(read_count=5, problems=[]), PASS),
        ("declared N/A is not a VOID", dict(read_count=0, problems=[],
                                            na_reason="not applicable here"), NA),
        ("forced VOID beats N/A", dict(read_count=0, problems=[],
                                       na_reason="r", void_reason="could not run"), VOID),
        # THE PAIR THAT MATTERS, and it is here rather than in one checker's suite because
        # every checker's JUDGE rests on it: candidates plus a reason hands the claim over,
        # and THE SAME CHECK finding nothing is a PASS. Only the second half shows the
        # severity is a judgement about the input and not a property of the check.
        ("candidates + a reason is JUDGE", dict(read_count=9, problems=["a candidate"],
                                                judge_reason="no script can settle this"),
         JUDGE),
        ("...and nothing found still PASSES", dict(read_count=9, problems=[],
                                                   judge_reason="no script can settle this"),
         PASS),
        ("a VOID outranks a JUDGE", dict(read_count=0, problems=["c"],
                                         judge_reason="r", void_reason="could not look"),
         VOID),
        ("an N/A outranks a JUDGE", dict(read_count=4, problems=["c"],
                                         judge_reason="r", na_reason="does not apply"), NA),
        ("nothing examined is VOID, not JUDGE", dict(read_count=0, problems=[],
                                                     judge_reason="r"), VOID),
    ]
    for label, kwargs, want in cases:
        r = Report()
        r.record("c", **kwargs)
        got = r.status_of("c")
        good = got == want
        ok &= good
        print(f"  {'OK  ' if good else 'MISS'} {label:<34} -> {got}")

    # THE MACHINE-READABLE ARM, proved on the properties a wrapper will rely on. Each is a
    # pair, because a one-sided assertion here would pass on a serialiser that emitted
    # everything or nothing.
    r = Report()
    r.record("passing check", 5, [], doc="a.md")
    r.record("failing check", 5, ["a problem"], doc="a.md")
    r.record("broken check", 0, [], void_reason="could not run", doc="b.md")
    r.record("judged check", 3, ["a candidate"], judge_reason="a person must settle this")
    d = r.as_dict("verify_x.py")
    keys = r.failing_keys("verify_x.py")
    for label, got, want in (
        ("as_dict carries every row", len(d["rows"]), 4),
        ("as_dict keeps the real exit code", d["exit_code"], RC_FAILED),
        ("as_dict counts the JUDGE claims", d["judge_claims"], 1),
        ("failing_keys takes only FAIL", keys, ["verify_x.py::a.md::failing check"]),
        # VOID IS NOT A FAILING KEY, and it is the half that matters: if it were, "the
        # instrument could not run" could be declared as a tolerated failure once and then
        # never reported again - which is the exact difference between VOID and CLEAN.
        ("...and never a VOID",
         any("broken check" in k for k in keys), False),
        ("...and never a JUDGE", any("judged check" in k for k in keys), False),
        # A KEY IS FIXED-ARITY so a declaration cannot match the wrong granularity: a code
        # checker has no document and still produces three parts.
        ("a doc-less row still keys in 3 parts",
         Report.failing_keys.__get__(_rowless())("verify_y.py"),
         ["verify_y.py::::whole-run check"]),
        ("the flag counts only in first position",
         (wants_report_json([REPORT_FLAG, "x"]), wants_report_json(["run", REPORT_FLAG])),
         (True, False)),
    ):
        good = got == want
        ok &= good
        print(f"  {'OK  ' if good else 'MISS'} {label:<34} -> {got}")
    return ok


def _selftest_loaded_lines():
    """loaded_lines, proved BOTH ways: five plain lines count five, and the same five
    wrapped in a block-level HTML comment count zero. A measure that returned the file's
    line count would pass the first and fail the second, and would push a maintainer to
    delete a note that was free."""
    ok = True
    plain = "\n".join(f"line {i}" for i in range(5))
    for label, text, want in (("loaded_lines counts plain lines", plain, 5),
                              ("loaded_lines ignores a comment", "<!--\n" + plain + "\n-->", 0),
                              ("an inline comment keeps its line", "a <!-- note --> b", 1)):
        got = loaded_lines(text)
        good = got == want
        ok &= good
        print(f"  {'OK  ' if good else 'MISS'} {label:<34} -> {got} (want {want})")
    return ok


def _selftest_safe_stdout():
    """safe_stdout, PROVED BOTH WAYS on a stream that really cannot encode the character.

    The bad arm has to be shown raising, or the good arm proves nothing: on a machine whose
    terminal is already UTF-8 the write would succeed with or without the fix, and the case
    would pass while protecting nothing.
    """
    import io
    ok = True
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
    return ok


def _selftest_exit_codes():
    """Which severity wins when a run carries several."""
    ok = True
    for label, statuses, want in (("FAIL outranks VOID", [FAIL, VOID], RC_FAILED),
                                  ("VOID alone exits 2", [VOID, PASS], RC_COULD_NOT_RUN),
                                  ("PASS and N/A exit 0", [PASS, NA], RC_OK),
                                  # THE ONE THAT KEEPS THE SEVERITY USABLE. A JUDGE that
                                  # exited non-zero would turn every run with an open
                                  # question red, and a gate that is always red is a gate
                                  # somebody switches off - taking the other four verdicts
                                  # with it. Asserted, not left to the reading of a comment.
                                  ("a JUDGE alone exits 0", [JUDGE, PASS], RC_OK),
                                  ("but a FAIL beside it still fails",
                                   [JUDGE, FAIL], RC_FAILED),
                                  ("and a VOID beside it still voids",
                                   [JUDGE, VOID], RC_COULD_NOT_RUN)):
        r = Report()
        for s in statuses:
            r.add("c", s, 1)
        good = r.exit_code == want
        ok &= good
        print(f"  {'OK  ' if good else 'MISS'} {label:<34} -> {r.exit_code} (want {want})")
    return ok


def _selftest_judge_mark():
    """THE OTHER HALF OF EXITING 0: BEING SEEN ANYWAY. A JUDGE is invisible to a caller
    reading the exit status, so the report has to carry it - in the headline a person
    reads, and in a mark a script can parse. Both are proved, and both are proved ABSENT
    on a clean run, because a mark that is always printed says nothing."""
    ok = True
    judged, clean = Report(), Report()
    judged.record("cross-doc refs", 3, ["line 7"], judge_reason="a person must decide")
    judged.add("something else", PASS, 5)
    clean.add("something else", PASS, 5)
    line = judged.judge_line()
    for label, good, got in (
        ("a JUDGE is named in the verdict", "JUDGE" in judged.verdict(), judged.verdict()),
        ("a clean run's verdict is bare", clean.verdict() == "PASS", clean.verdict()),
        ("the mark carries the count", judge_count(line or "") == 1, line),
        ("the mark names the check", "cross-doc refs" in (line or ""), line),
        ("no mark at all when none", clean.judge_line() is None, clean.judge_line()),
        # the parser, shown NOT firing on prose that merely discusses judging - the loose
        # substring version would report a judgement from this very file
        ("prose mentioning JUDGE is not one",
         judge_count("we could add a JUDGE severity here") == 0, "0"),
        ("the row keeps its candidates",
         "line 7" in judged.render(), "line 7" in judged.render()),
    ):
        ok &= good
        print(f"  {'OK  ' if good else 'MISS'} {label:<34} -> {got}")
    return ok


def _selftest_blank_reasons():
    """A REASON THAT IS SET BUT BLANK, refused for every kind. It prints as a decision
    nobody made, which is the same defect as an undeclared N/A wearing a label."""
    ok = True
    for label, kw in (("blank judge_reason", dict(judge_reason=" ")),
                      ("blank na_reason", dict(na_reason="")),
                      ("blank void_reason", dict(void_reason="\t"))):
        try:
            Report().record("c", 1, ["p"], **kw)
            refused = False
        except ValueError:
            refused = True
        ok &= refused
        print(f"  {'OK  ' if refused else 'MISS'} {(label + ' is refused'):<34} -> {refused}")
    return ok


def _selftest_doc_grouping():
    """A row with a document groups under it; a row without one prints no 'None'."""
    r = Report()
    r.record("c", 1, ["a problem"], doc="one.md")
    grouped = "one.md" in r.render()
    r2 = Report()
    r2.record("c", 1, ["a problem"])
    ungrouped = "None" not in r2.render()
    print(f"  {'OK  ' if grouped else 'MISS'} {'renders a doc heading when set':<34} -> {grouped}")
    print(f"  {'OK  ' if ungrouped else 'MISS'} {'and prints no None when unset':<34} -> {ungrouped}")
    return grouped and ungrouped


def _selftest_case_harness():
    """THE HARNESS ITSELF, tested on a check that is deliberately broken. This is the whole
    argument for the case table: a one-sided suite passes a check that fires on
    EVERYTHING, so the harness must be shown catching one.

    THESE ASSERTIONS STAY IMPERATIVE, DECLARED RATHER THAN OVERLOOKED. Every other suite in
    the house is a Case table; this one may not be, because run_cases cannot be the harness
    for its own assertions - a harness broken in both halves would agree with itself. It is
    DRIVEN here, on fixtures built to be wrong, which is the opposite arrangement.
    """
    import io
    from contextlib import redirect_stdout

    def honest(x):
        return FAIL if x == "bad" else PASS

    def fires_on_everything(x):
        return FAIL

    ok = True
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
    return ok


def _selftest_isolated_env():
    """CLEARED INSIDE, RESTORED EXACTLY OUTSIDE - and the pair is the whole assertion.

    "It is cleared inside" alone is passed by a helper that never restores anything, which
    would silently strip a caller's real configuration. "It is restored" alone is passed by
    one that clears nothing, which IS the defect. And the two restore cases differ: a
    variable that was SET must come back with its exact value, while one that was ABSENT must
    be left ABSENT - restoring it as "" would turn "nobody declared a list" into "somebody
    declared an empty one", which is a different fact to every reader of it.
    """
    ok = True
    name_set, name_absent = "HOUSE_SELFTEST_ISO_SET", "HOUSE_SELFTEST_ISO_ABSENT"

    def probe(label, good):
        nonlocal ok
        ok &= good
        print(f"  {'OK  ' if good else 'MISS'} {label:<48} -> {good}")

    os.environ[name_set] = "original-value"
    os.environ.pop(name_absent, None)
    try:
        with isolated_env(name_set, name_absent):
            probe("a set variable is CLEARED inside", name_set not in os.environ)
            probe("an absent one stays absent inside", name_absent not in os.environ)
            os.environ[name_absent] = "written-inside"
        probe("the set one is restored to its VALUE",
              os.environ.get(name_set) == "original-value")
        probe("the absent one is left ABSENT, not ''", name_absent not in os.environ)
        # AND IT RESTORES AFTER AN EXCEPTION, because a suite that raises must not leave the
        # caller's environment stripped - the failure would surface in the NEXT thing to run.
        try:
            with isolated_env(name_set):
                raise RuntimeError("planted")
        except RuntimeError:
            pass
        probe("restored even when the block raised",
              os.environ.get(name_set) == "original-value")
    finally:
        os.environ.pop(name_set, None)
        os.environ.pop(name_absent, None)
    return ok


def _selftest_mask_phrases():
    """EVERY ARM PAIRED, because each one alone passes a DIFFERENT broken masker.

    Arm 1 alone - 'the needle is gone' - is passed perfectly by a masker that returns a
    constant, which destroys every report in the house. Arm 2 alone - 'the path survives' -
    is passed by one that masks nothing at all, which is the defect being fixed. Neither
    half is evidence without the other, and the second is the direction that ships, because
    a readable report is the answer everybody wants.
    """
    ok = True
    needles = ["Acme-Matter", "Acme", "C:\\Users\\somebody"]

    def probe(label, got, want):
        nonlocal ok
        good = got == want
        ok &= good
        print(f"  {'OK  ' if good else 'MISS'} {label:<48} -> {good}")

    # 1 AND 2 ARE THE PAIR. A path segment that IS a needle is replaced by its position; a
    # path with none is printed byte for byte, or the report stops locating anything.
    probe("a needle in a PATH is masked",
          mask_phrases("config/Acme-Matter.yaml:12", needles),
          "config/<phrase #1>.yaml:12")
    probe("and a clean path is left VERBATIM",
          mask_phrases("pbskill/sources/podio.py:49", needles),
          "pbskill/sources/podio.py:49")

    # LONGEST FIRST. Masked shortest-first, 'Acme-Matter' becomes '<phrase #2>-Matter' and
    # the half that identifies the client is still readable - a leak that looks like a fix.
    probe("a needle CONTAINING another masks as itself",
          mask_phrases("Acme-Matter", needles), "<phrase #1>")
    probe("and the contained needle still masks alone",
          mask_phrases("Acme", needles), "<phrase #2>")

    # A BACKSLASH IS A CHARACTER, NOT A REGEX ESCAPE. The twin is the regex READING of the
    # same needle - whitespace where a separator was meant - which must NOT be masked. This
    # is the pair that catches a masker handing an unescaped needle to the regex engine.
    probe("a backslash needle masks literally",
          mask_phrases("C:\\Users\\somebody\\x", needles), "<phrase #3>\\x")
    probe("and its \\s reading does NOT match",
          mask_phrases("C: Users somebody", needles), "C: Users somebody")

    # ONE PASS. A loop of replacements can re-scan its own output; here the substitution
    # text is never offered to the matcher, so a needle spelling 'phrase' cannot cascade.
    probe("the replacement text is not re-scanned",
          mask_phrases("Acme", ["Acme", "phrase"]), "<phrase #1>")

    # AN EMPTY LIST MASKS NOTHING AND DOES NOT CRASH. A checker whose list failed to resolve
    # still renders its VOID rows, and a masker that raised there would take the report with
    # it - reporting nothing at all, which reads exactly like a clean run.
    probe("an empty list leaves the text alone",
          mask_phrases("config/Acme-Matter.yaml", []), "config/Acme-Matter.yaml")
    return ok


def _selftest_list_fingerprint():
    """THE LIST A VERDICT WAS TAKEN AGAINST, identified - and the leak test that bounds it.

    Arm 1 alone - 'the same list gives the same answer' - is passed by a function returning
    a constant, which is precisely a fingerprint that can never detect a change. So every
    arm here is paired against its opposite, and the last pair is not about detection at
    all: a fingerprint that contained a needle would be the leak this plumbing exists to
    prevent, arriving in the field added to prevent it.
    """
    ok = True

    def probe(label, good):
        nonlocal ok
        ok &= good
        print(f"  {'OK  ' if good else 'MISS'} {label:<48} -> {good}")

    a, b = ["one", "two", "three"], ["one", "two", "three"]
    probe("the same list gives the same fingerprint",
          list_fingerprint(a) == list_fingerprint(b))
    probe("and ONE more needle changes it",
          list_fingerprint(a) != list_fingerprint(a + ["four"]))
    # ORDER-SENSITIVE ON PURPOSE: a report cites '#4 of 7', so the same set reordered makes
    # every citation in it mean something else. Normalising order away would call two
    # mutually unreadable reports identical.
    probe("a REORDERED list is a different list",
          list_fingerprint(a) != list_fingerprint(list(reversed(a))))
    # And the twin of that: a blank entry is not a needle, so it must not move the answer.
    probe("but a blank entry does not move it",
          list_fingerprint(a) == list_fingerprint(a + ["  "]))

    # NAMED `needle` AND NOT `secret`, ON A FINDING FROM THIS VERY SESSION. The source
    # checker's own pattern is `(secret|password|pwd)\s*[:=]\s*'...'`, and it fired on this
    # line - correctly: it cannot know a literal is a test fixture, and a checker that
    # guessed would be the wrong checker. The fix is the name, never the pattern.
    needle = "Acme-Matter"
    fp = list_fingerprint([needle, "other"])
    probe("the fingerprint carries no needle", needle.lower() not in fp.lower())
    probe("and it is not the empty-list answer", fp != list_fingerprint([]))
    # AN EMPTY LIST IS NAMED, NOT HASHED. A hash of nothing is a stable-looking hex string
    # that reads on a report exactly like the identity of a real list.
    probe("an empty list reports 'none'", list_fingerprint([]) == "none")
    probe("and so does a list of only blanks", list_fingerprint(["", " "]) == "none")
    return ok


def _selftest_write_section():
    """`--write-config` ADDS A SECTION - it does not reformat the file it was handed.

    THIS EXISTS BECAUSE THE FUNCTION USED `Path.write_text`, WHICH OPENS IN TEXT MODE, so
    on Windows every `\\n` it wrote became `\\r\\n` and a helper documented as working
    "without disturbing the others" silently rewrote EVERY LINE ENDING in the file.
    Measured on a real project: a pure-LF 45-line config came back pure-CRLF at 77 lines
    with the content perfectly intact - so every content check passed, only a
    line-endings check saw it, and to git every line in the file had changed.

    EVERY ARM IS PAIRED, because "the file is still LF" is passed perfectly by a function
    that writes nothing at all. So each line-ending arm sits beside an arm asserting the
    section actually arrived, and the LF case sits beside its CRLF twin - the fix must
    PRESERVE what the file used, not impose one answer on both.
    """
    ok = True

    def probe(label, good):
        nonlocal ok
        ok &= good
        print(f"  {'OK  ' if good else 'MISS'} {label:<48} -> {good}")

    def endings(b):
        crlf = b.count(b"\r\n")
        return crlf, b.count(b"\n") - crlf

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        cfg = root / CONFIG_NAME

        # ARM 1 - AN LF FILE STAYS LF. This is the arm the defect failed.
        cfg.write_bytes(b'{\n  "md": {\n    "files": ["CLAUDE.md"]\n  }\n}\n')
        write_section(root, "demo", {"k": 1}, {"k": "why"})
        raw = cfg.read_bytes()
        crlf, lf = endings(raw)
        probe("an LF config is still LF after a write", crlf == 0 and lf > 0)
        probe("and the new section actually arrived", "demo" in json.loads(raw.decode("utf-8")))
        probe("and the existing section survived", "md" in json.loads(raw.decode("utf-8")))

        # ARM 2 - ITS TWIN. A CRLF file must stay CRLF, or the fix has merely moved the
        # damage to the other kind of project.
        cfg.write_bytes(b'{\r\n  "md": {\r\n    "files": ["CLAUDE.md"]\r\n  }\r\n}\r\n')
        write_section(root, "demo2", {"k": 1}, {"k": "why"})
        raw = cfg.read_bytes()
        crlf, lf = endings(raw)
        probe("a CRLF config is still CRLF after a write", lf == 0 and crlf > 0)
        probe("and that section arrived too", "demo2" in json.loads(raw.decode("utf-8")))

        # ARM 3 - A FILE THAT DID NOT EXIST. There is nothing to preserve, so the answer is
        # what json.dumps itself produces: LF.
        cfg.unlink()
        write_section(root, "fresh", {"k": 1}, {"k": "why"})
        crlf, lf = endings(cfg.read_bytes())
        probe("a NEW config is written LF", crlf == 0 and lf > 0)

    return ok


# THE ORDER IS THE ORDER THE ROWS WERE PRINTED IN BEFORE THE SPLIT. A part that is written
# and never added here would be silently absent, so the count is PRINTED - the same reason
# report_pairing prints a number instead of letting a reader assume the suite is two-sided.
SELFTEST_PARTS = (_selftest_status_model, _selftest_loaded_lines, _selftest_safe_stdout,
                  _selftest_exit_codes, _selftest_judge_mark, _selftest_blank_reasons,
                  _selftest_doc_grouping, _selftest_case_harness, _selftest_mask_phrases,
                  _selftest_list_fingerprint, _selftest_isolated_env,
                  _selftest_write_section)


def selftest() -> int:
    """The result model itself, proved. Every checker's verdict rests on these rules, so
    they are tested here once rather than inferred from three places that agree today."""
    print("SELFTEST - the shared result model\n")
    ok = True
    for part in SELFTEST_PARTS:
        ok &= part()
    print(f"\n  {len(SELFTEST_PARTS)} part(s) run")
    print("\nSELFTEST: " + ("PASS" if ok else "FAIL"))
    return RC_OK if ok else RC_FAILED


if __name__ == "__main__":
    # --selftest is accepted, and ignored, so this file is DISCOVERED like every other
    # script in the house. run_tests.py finds suites by looking for that flag, and the
    # shared module every checker imports was the one thing it did not run.
    sys.exit(selftest())
