#!/usr/bin/env python3
"""verify_md.py - the document checker.  CHECKER VERSION 31 (2026-10-14)

If a project's copy says a lower version than this one, it is stale - see the "Checkers"
line for each version in ...\\Coding\\templates\\TEMPLATE-CHANGELOG.md and re-copy.

v31 ADDS line_measure, WHAT A SIZE CAP COUNTS. 'physical' (the default for one release) counts
lines, so a Markdown table row is one line however long; 'wrapped' weighs each line at its
length / 120, rounded up. The size breakdown prints both, whichever gates. Copy it WITH
house_common.py v20, which holds the measure.

Checks Markdown deliverables: CLAUDE.md, plan documents, registers, READMEs, research
write-ups, guided-build playbooks. Standard library only, so it runs anywhere.

THREE FILES TRAVEL TOGETHER SINCE v30: this one, house_common.py and verify_charter.py. The
six CHARTER checks - structure, archetype, the CORE floor, sections agreed out, relocation
pointers, plan purpose - moved to verify_charter.py on 2026-10-12, because they mirror
CLAUDE-TEMPLATE.md and every template change was marking this file stale in every project.
This file still CALLS them for every document, so a project runs one command, reads one
report, and keeps every row name and every toleration key. Without verify_charter.py the six
rows FAIL, naming it; they never silently disappear.

    uv run python tools/verify_md.py                    # check what the config lists
    uv run python tools/verify_md.py FILE [FILE ...]    # check named files instead
    uv run python tools/verify_md.py --baseline REV     # ...and scan the ADDED LINES too
    uv run python tools/verify_md.py --selftest         # prove every check can FAIL

WHY --baseline EXISTS, AND WHY IT IS A FLAG RATHER THAN A SETTING. Whole-file scanning
drowns a forbidden-phrase result in pre-existing hits, and a report a reviewer skims is a
control nobody believes; the added-lines row reports only what THIS change introduced. The
whole-file row is never replaced - a confidentiality control is not weakened - and reading
the pair is what tells a new hit from an old one. It is a flag because a baseline belongs
to an INVOCATION: this is a pre-commit gate, and on a clean tree there is nothing to gate,
so a permanent setting would make every routine run VOID as soon as there was nothing to
commit. Pass a revision, never 'the current file': if the working tree turns out to be
identical to the baseline, the row is VOID rather than a pass, because that is the shape
in which a before-and-after check once compared a rewrite against itself and reported
100% carried.

WHY --selftest EXISTS. A check that has never been observed failing is a check you are
trusting on faith. --selftest copies each file, breaks it one way per check, and asserts
the check notices. It restores nothing because it never touches your originals - it works
on copies in a temp directory and verifies your files are byte-identical afterwards.

EVERY CHECK REPORTS ITS DENOMINATOR. "0 of 0 bad" is not a pass; a check that examined
nothing prints VOID unless the config declares it not applicable, with a reason.

EXIT CODES.  0 = every check passed or was a declared N/A.  1 = at least one check FAILED.
2 = at least one check COULD NOT RUN (VOID) and none failed. "It could not run" and "it
failed" are different facts and a caller that cannot tell them apart cannot react to
either correctly. A FAIL outranks a VOID, because a concrete defect outranks an
unestablished one; both are non-zero, so any gate wired to "non-zero blocks" is unchanged.

AND A FIFTH VERDICT THAT CHANGES NO EXIT CODE: JUDGE, for a claim this checker can SEE and
cannot settle. Here that is the cross-document reference - a section sign resolves against
its own file, so a line naming another document and using a sign is probably pointing at
the wrong section, and where the number happens to exist locally it passes silently. Only
the author knows which document was meant, so it is handed over rather than failed. It
prints in the report, in the OVERALL line and as a JUDGE-CLAIMS mark that run_tests.py
reads; it does not block, because a gate that is red on an unanswerable question gets
switched off.

A SENSITIVE FORBIDDEN LIST NEVER GOES IN THE CONFIG. verify.config.json is committed - a
project's tailoring belongs in its repository. So a forbidden list that is ITSELF the
sensitive material must be read from somewhere else, or the file publishes exactly what it
protects. Point 'forbidden_phrases_file' at a path outside the repository, or set
VERIFY_FORBIDDEN_LIST in the environment so CI can supply its own copy as a secret. The
scanner ships; the list never does. An ordinary list - a retired product name, an old
spelling - is not sensitive and belongs inline in the config, where it is simplest.

AND THE REPORT NEVER PRINTS A PHRASE THAT CAME FROM OUTSIDE THE REPOSITORY. It prints the
phrase's position in the list. Moving the list out of the repository and then echoing its
contents into a terminal, a CI log or a pasted failure report leaks it by a different
route - and that route reaches places no scanner can clean up afterwards.

THE MIRROR OF THAT LIST IS 'required_strings' - the REQUIRED claim kind, a fact that must
be PRESENT and is worth a check precisely because nothing complains when it quietly stops
being stated. It reads from the same three places by the same rules (inline, a file, or
VERIFY_REQUIRED_LIST), through the same resolver, so the trap that matters - a declared
list that cannot be read is VOID, never a silent pass - cannot come to mean two different
things in the two halves. It was one function copied twice for exactly one version.

AND IT MATCHES WHITESPACE-INSENSITIVELY, WHICH FOR *REQUIRED* IS THE OPPOSITE DIRECTION OF
WRONG. A hard-wrapped document splits a phrase across a line ending; a line-by-line search
then reports a fact MISSING from a document that plainly states it. Reproduced before this
was built: the naive search failed a conforming file. A forbidden check that is wrong that
way stays quiet about a real leak, and a required check that is wrong that way fails files
it is wrong about - so it gets switched off as noisy, taking the files it was RIGHT about
with it.

WHAT IS AND IS NOT PRINTED DIFFERS BY WHERE THE STRING CAME FROM, and the rule is one
sentence: a string listed INLINE is already committed in verify.config.json, so naming it
in the report publishes nothing that was not already in the repository - and a "something
is missing, work out what" report is not actionable. A string from a FILE or the
environment is deliberately outside the repository and is named by position only. Position
alone is all a forbidden hit ever needs, because the phrase is in the document you are
reading; a MISSING string has no position in the document at all, which is why this
distinction had to be made here rather than inherited.

CONFIGURE IT, DO NOT FORK IT. Settings live in verify.config.json under the "md" key.
Run --write-config once to get a commented starting point.
"""
from __future__ import annotations

import contextlib
import io
import os
import re
import shutil
import sys
import tempfile
from fnmatch import fnmatch
from hashlib import sha256
from pathlib import Path

# The shared plumbing. COPY house_common.py ALONGSIDE THIS FILE - without it the checker
# cannot start. check_checkers.py tracks it, so a project that copied one and not the other
# gets a reported finding rather than an import error at the worst possible moment.
from house_common import (                                       # noqa: E402
    CELL_PIPE, DELIM_RE, FAIL, INLINE_CODE, JUDGE, NA, PASS, RC_COULD_NOT_RUN, VOID, Case,
    Report, added_line_runs, baseline_guard, code_fence_mask, collapse, finish, git,
    headings, isolated_env, load_section, loaded_lines, raw_lines, read_phrase_list,
    report_pairing, resolve_list, resolve_revision, row_cells, run_cases, selftest_config,
    strip_inline_code, wants_report_json, write_section, WRAP_WIDTH, wrapped_lines,
)

#: THE TWO WAYS A SIZE CAP CAN COUNT (v31, 2026-10-14). "physical" counts lines in the file, so
#: a table row is one line however long; "wrapped" weighs each line at its length / WRAP_WIDTH,
#: rounded up. Physical stays the DEFAULT for one release, so nothing turns red without a
#: decision: every project's next session switches its own key and gets under its ORIGINAL
#: caps, which keep their numbers in the new unit (Wouter, 2026-10-14 (3)).
LINE_MEASURES = ("physical", "wrapped")


def measure_problem(measure):
    """Why this line_measure cannot be used, or None. A mistyped value is VOID rather than
    silently physical: a config asking for something unknown must not be gated on a measure
    nobody chose."""
    if measure in LINE_MEASURES:
        return None
    return (f"line_measure is {measure!r} - it must be one of "
            + ", ".join(repr(m) for m in LINE_MEASURES))

# THE CHARTER CHECKS, split out on 2026-10-12 (v30). COPY verify_charter.py ALONGSIDE THIS
# FILE as well. Unlike house_common, its absence must NOT stop the checker: every general
# check still works without it. So a failed import is remembered, and the six charter rows
# are then reported as FAIL naming the file - a missing row reads exactly like a passed one.
# ANY failure is caught, not only ImportError: a half-copied file with a syntax error must not
# take the general checks down with it. And "not installed" is said only when that is true - an
# installed copy that fails to import (a stale house_common beside a newer one) says so instead.
try:
    import verify_charter
    _CHARTER_MISSING = ""
except Exception as exc:                                         # pragma: no cover  # noqa: BLE001
    verify_charter = None
    if isinstance(exc, ModuleNotFoundError) and exc.name == "verify_charter":
        _CHARTER_MISSING = "verify_charter.py is not installed beside verify_md.py"
    else:
        _CHARTER_MISSING = (f"verify_charter.py is installed but could not be imported - "
                            f"{type(exc).__name__}: {exc}")

#: The six charter rows, by name, so they can be reported when verify_charter.py is missing.
#: A CONTRACT with that file's own ROWS: a declared toleration is keyed on these names, and
#: verify_charter.py's selftest asserts the two tuples agree.
CHARTER_ROWS = ("charter structure", "charter archetype", "core sections present",
                "sections agreed out", "relocation pointers", "plan purpose")

# --------------------------------------------------------------------------- config

FORBIDDEN_LIST_ENV = "VERIFY_FORBIDDEN_LIST"
REQUIRED_LIST_ENV = "VERIFY_REQUIRED_LIST"

DEFAULT_CONFIG = {
    "files": ["CLAUDE.md", "README.md"],
    "required_sections": [],
    "forbidden_phrases": [],
    "forbidden_phrases_file": "",
    "diff_baseline": "",
    "required_strings": [],
    "required_strings_file": "",
    # {{FILL}} is the house marker: braces are not markdown syntax, so no formatter
    # escapes them. The bracket forms are kept so an older document is still caught, and
    # the escaped form is listed because escaping is exactly how a marker goes invisible.
    "placeholder_markers": ["{{FILL", "[[FILL", "\\[\\[FILL", "TODO", "TBD", "FIXME",
                            "XXX", "<placeholder>"],
    "check_formatter_damage": True,
    "flag_trailing_hard_breaks": True,
    "check_numbered_headings": "auto",
    "check_internal_refs": True,
    "check_file_links": True,
    "check_status_agreement": True,
    "report_numeric_claims": True,
    "report_cross_doc_refs": True,
    "max_line_length": 0,
    "max_lines": 0,
    "section_caps": {},
    "line_measure": "physical",
    "charter_structure": {},
    "archetype_absent": None,
    "core_sections": {},
    "sections_agreed_out": {},
    "pointers": {},
    "size_scope": ["CLAUDE.md", "*/CLAUDE.md"],
    "plan_scope": [],
    "report_section_sizes": True,
    "report_section_shape": True,
}

#: THE TEMPLATE'S CONSTANTS - its subsection counts, the CORE and NEGOTIABLE sets and the
#: eleven archetypes - MOVED TO verify_charter.py ON 2026-10-12 (v30). They mirror
#: CLAUDE-TEMPLATE.md, so a template change now bumps that file and leaves this one alone.

CONFIG_COMMENT = {
    "files": "Documents to check when no filenames are given on the command line. GLOBS ARE ALLOWED and are how you cover a KIND rather than a list - 'PLAN-*.md' checks the next plan file too, which a literal list never does. A glob matching NOTHING is VOID, not a silent pass.",
    "required_sections": "Headings that must exist, e.g. ['7. Current status']. Empty = do not check.",
    "diff_baseline": "A revision to scan the ADDED LINES against - a SHA, a tag, 'origin/main', 'HEAD~1'. Adds a second forbidden-phrase row reporting only what THIS change introduces, because whole-file scanning drowns the result in pre-existing hits. The whole-file row is NOT replaced: a confidentiality control is never weakened, and the pair is what shows a hit is pre-existing rather than new. Empty = do not check. If the working tree is IDENTICAL to the baseline the row is VOID, never a pass - that is the trap this arm exists to avoid, and it is why the guard is mechanical instead of a ban on the word HEAD.",
    "forbidden_phrases": "Strings that must never appear, listed INLINE. For an ordinary list only - a retired product name, an old spelling. THIS FILE IS COMMITTED.",
    "forbidden_phrases_file": "Path to a list whose CONTENTS are themselves sensitive - one phrase per line, '#' comments ignored. Keep it OUTSIDE the repository, not merely gitignored. " + FORBIDDEN_LIST_ENV + " overrides this path, so CI can supply its own copy as a secret. Declared and not found = VOID, never a silent pass.",
    "required_strings": "The MIRROR of forbidden_phrases: strings that must be PRESENT, matched whitespace-insensitively over the whole document so a hard-wrapped fact still counts as stated. For a fact that must not quietly stop being stated - a commit-identity rule, a governing-law clause, an ownership line. Nothing complains when such a sentence is deleted, which is the entire reason to check it. Listed INLINE and therefore committed, so a missing one IS NAMED in the report - 'something is missing, work out what' is not actionable, and the string is already in the repository. Matching is case-insensitive: a fact restated in different capitals is still stated. Empty = do not check.",
    "required_strings_file": "Path to a required list whose CONTENTS are themselves sensitive - one string per line, '#' comments ignored. Same rules as forbidden_phrases_file, and read through the SAME resolver so the two cannot drift. " + REQUIRED_LIST_ENV + " overrides this path. Declared and not found = VOID, never a silent pass. A string from here is reported BY POSITION ONLY, never by value: it lives outside the repository deliberately, and a report naming it puts it back.",
    "placeholder_markers": "Unfilled-template markers. A finished document has none.",
    "check_numbered_headings": "'auto' checks only if the file uses numbered headings; true forces it.",
    "check_internal_refs": "Resolve every S-N.M reference to a real heading in the same file.",
    "check_file_links": "Resolve every relative markdown link to a file on disk.",
    "check_status_agreement": "A numbered work item - 'Item 5b', 'Phase 3' - stated in a heading AND in a tracking-table row above it must not disagree about whether it is done. Measured four times in one file here, always in the expensive direction: a heading reading NOT STARTED over work finished days earlier, which invites a session to redo it. Only a DONE-versus-OPEN disagreement fires; 'done' beside 'closed' is two words for one state. NOT covered: a tracker whose items are named rather than numbered, and a claim that is merely out of date rather than contradicted - those belong to the closing procedure's staleness step.",
    "report_numeric_claims": "List sentences asserting counts, so you can re-derive them. Never fails.",
    "report_cross_doc_refs": "Flag lines that name another .md AND use a section sign. A sign resolves against ITS OWN file, so such a line is probably pointing at the wrong section - and if the number happens to exist locally it passes SILENTLY. Reported as JUDGE, never FAIL: the checker cannot know which file was meant, so a person decides. A JUDGE does not affect the exit code. The key keeps its 'report_' name so existing configs are unaffected.",
    "max_line_length": "0 disables. Set e.g. 110 to keep documents diff-friendly.",
    "max_lines": "0 disables. Either ONE number for every file in size_scope, or a MAP of glob to cap - {\"CLAUDE.md\": 526, \"PLAN-*.md\": 120} - when a project has documents of different size classes. With a map, the LONGEST matching glob wins, a file matching none reports N/A, and two globs of the same length both matching is VOID rather than a silent pick. A charter's cap is its archetype's emit plus 120, written by new_charter.py; the plan-file cap is 120. THE NUMBER IS IN THE UNIT line_measure NAMES - the same figure in a new unit is a new cap, so say the unit beside it wherever you state it. Counts what LOADS, not what is in the file - block-level HTML comments are stripped before Claude receives them. Over the cap means RELOCATE, never delete.",
    "line_measure": "What a size cap counts - max_lines and section_caps alike. 'physical' (the default for one release): lines in the file, so a Markdown table row is ONE line however long it is. 'wrapped': each line weighs its length divided by 120, rounded up - a wrapped prose line still counts one, a 16,000-character row counts 134. Measured 2026-10-14, the physical count was as little as 43% of what a plan file loads and 55% of a charter, and moving one 16,155-character cell out of a charter saved 19% of its bytes and ZERO counted lines - so a physical cap could be met by moving prose into a table row. SWITCH TO 'wrapped' IN YOUR PROJECT'S NEXT SESSION and get under your ORIGINAL caps, which keep their numbers in the new unit (Wouter, 2026-10-14 (3)); the size report prints both counts until you do. Anything else is VOID.",
    "size_scope": "Which files the size checks apply to, as filename globs. A cap is a property of a CHARTER - a README has no size class, and a *-TEMPLATE.md contains a template FOR a section and is legitimately long. Anything outside this list reports N/A with that reason.",
    "archetype_absent": "DEVICE 3's declaration slot. Section 1.7 must NAME one of CLAUDE-TEMPLATE.md's eleven archetypes, because every optional-block lookup in the archetype table (11 rows x 10 columns at in/ask/out) starts by knowing which row this project is - a charter recording none makes the whole table unreadable, which is how a reduction came to be planned on 'these blocks are OPTIONAL, so they can be dropped' when the archetype's own row marked every one of them IN. Set this to a REASON STRING only for a project that genuinely fits none of the eleven; a blank reason is REFUSED, and a declaration standing over a charter that DOES name one FAILS as stale. It asks for a LABELLED line and not a phrase search, and that was measured both ways over six charters: searching for the eleven NAMES returns false positives from ordinary prose, and searching for the word 'archetype' passes a charter whose only hit is a sentence about emitted line counts - two naive needles answering wrongly in OPPOSITE directions. Punctuation and case are folded, so an em dash or a stray article never fails you.",
    "core_sections": "DEVICE 1's FLOOR - a map of CORE subsection -> reason, for a CORE subsection that genuinely cannot be written. Empty is the normal state. The check asserts every one of the tier table's fourteen CORE rows is PRESENT, which is the OPPOSITE question from 'charter structure': that one is a CEILING (never MORE than the template) and a subset is exactly what MAPPING produces, so it can never see an absence. Measured 2026-09-10 over six house charters: THREE were missing at least one CORE subsection including the house repository's own, and one was missing 5.4 - TEST - in a project already closed as fully propagated. ONLY CORE IS CHECKED, and that is the discriminator: a missing DEFAULT or OPTIONAL subsection is a decision Round 0.5 took, while CORE is 'never negotiated away' in the tier table's own words. So the honest remedy is almost always to WRITE the subsection. Blank reason REFUSED; a declaration for a subsection that IS present FAILS as stale.",
    "plan_scope": "Which files the 'plan purpose' check applies to, as filename globs - the LIVE plan file(s), and nothing else. EMPTY BY DEFAULT, reporting N/A with that reason rather than passing silently. IT IS DECLARED AND NOT INFERRED, on a measurement: of 15 plan files in the house repository the 14 CLOSED ones never used strikethrough - they recorded completion in a 'status' COLUMN - so 44 finished rows read as OPEN and a 'every PLAN-*.md' default reddens twelve finished records. And the next discriminator that suggests itself is worse: the LIVE file's status row contains the word CLOSED (naming which steps are), so prose-matching it marks the one live plan finished and the check passes over the very file it exists to read. Name the live plan file here; updating this glob is the same act as renaming the file when the phase turns over. A CLOSED plan file is left out - it is a finished record, and rewriting one to satisfy a convention it predates destroys evidence.",
    "section_caps": "Per-section caps, e.g. {\"7\": 25}, keyed by top-level section number, in the unit line_measure names. A capped section that is ABSENT is a finding, not a silent pass. Empty = do not check.",
    "report_section_sizes": "List each top-level section's loaded line count, so you can see WHERE the weight sits. Never fails.",
    "report_section_shape": "Beside each section size, what the section is MADE of - prose, table rows, headings, blanks - and the FLOOR those last three add up to. Never fails. It exists because a size alone cannot say whether a section is reducible: a heading may never be deleted (it is the return path every relocated pointer resolves against) and a table row is one PHYSICAL line however long it is, so under line_measure 'physical' rewriting a verbose row saves nothing on the gate and only the prose count answers 'how much can a rewrite touch'. Under 'wrapped' a long row is weight like any other, and the wrapped count beside each section size shows it. Measured on the first two reductions this house ran, savings estimated off the SPAN came in at about a third of estimate, uniformly optimistic, because the model assumed prose where the file held structure. The floor also settles reachability BEFORE the work rather than after: a target below blank+heading+table cannot be met without deleting a heading or dropping a rule, and finding that out at the end costs a session.",
}

SECTION_SIGN = "§"

# --------------------------------------------------------------------------- results


class Report(Report):
    """The shared Report, with the document moved to the front of the call.

    This checker reports per FILE and the other two report per project, so its calls
    naturally lead with the document. Rather than reorder ninety call sites - or fork the
    result model, which is what created three copies of it in the first place - the
    difference is confined to these six lines. Everything that decides a verdict, an exit
    code or a denominator is the shared one.
    """

    def record(self, doc, name, read_count, problems, **kw):
        return super().record(name, read_count, problems, doc=doc, **kw)

    def add(self, doc, name, status, count, problems=()):
        return super().add(name, status, count, problems, doc=doc)


# --------------------------------------------------------------------------- parsing

# HEADING_RE and NUMBERED_RE moved to house_common.py on 2026-10-12, with headings() below.
DOC_NAME_RE = re.compile(r"[A-Za-z0-9_.-]+[.]md")
REF_RE = re.compile(SECTION_SIGN + r"(\d+)(?:\.(\d+))?")
LINK_RE = re.compile(r"\[([^\]]*)\]\(([^)]+)\)")
# loaded_lines and the size-class table live in house_common: the GENERATOR needs the same
# measurement, and a second copy of a measurement is how the two come to disagree.
# "212 rows", "eleven of twelve", "3 of 5 scripts"
NUMERIC_CLAIM_RE = re.compile(
    r"\b(\d+)\s+(?:of\s+\d+\s+)?"
    r"(rows?|files?|lines?|scripts?|checks?|items?|findings?|documents?|tests?|sections?|entries)\b",
    re.I,
)


# headings() and code_fence_mask() MOVED TO house_common.py ON 2026-10-12 (v30), so that
# verify_charter.py reads headings and fenced blocks with the same code as this file.


# ---------------------------------------------------------------------------- checks

# CELL_PIPE, DELIM_RE and row_cells() moved to house_common.py on 2026-10-12, for the same
# reason: the plan-purpose check reads table cells too, and must split them the same way.


def cell_count(row: str) -> int:
    """Cells in a table row, counting only UNESCAPED pipes as separators."""
    return len(row_cells(row))


def check_tables(rep, doc, lines):
    """A table whose rows disagree on column count renders as broken text."""
    mask = code_fence_mask(lines)
    blocks, current = [], []
    for i, ln in enumerate(lines):
        is_row = ln.lstrip().startswith("|") and not mask[i]
        if is_row:
            current.append((i + 1, ln))
        elif current:
            blocks.append(current)
            current = []
    if current:
        blocks.append(current)

    problems = []
    for block in blocks:
        if len(block) < 2:
            problems.append(f"line {block[0][0]}: table row not part of a table")
            continue
        delim = block[1][1]
        if not DELIM_RE.match(delim):
            problems.append(f"line {block[1][0]}: table has no delimiter row - it will not render")
            continue
        widths = {cell_count(row) for _, row in block}
        if len(widths) > 1:
            problems.append(
                f"line {block[0][0]}: table columns disagree {sorted(widths)}"
            )
    rep.record(doc, "tables well-formed", len(blocks), problems,
               na_reason=None if blocks else "document contains no tables")


def check_headings(rep, doc, lines, mode):
    hs = list(headings(lines))
    numbered = [(i, k, t) for i, _, t, k in hs if k]
    if mode == "auto" and not numbered:
        rep.record(doc, "heading numbering", 0, [], na_reason="document uses no numbered headings")
        return
    problems, seen = [], {}
    for i, key, text in numbered:
        if key in seen:
            problems.append(f"line {i}: heading {key} duplicates line {seen[key]}")
        seen[key] = i
    # gapless within each top-level section
    tops = sorted({int(k.split(".")[0]) for _, k, _ in numbered})
    for top in tops:
        subs = sorted(int(k.split(".")[1]) for _, k, _ in numbered if "." in k and k.startswith(f"{top}."))
        if subs and subs != list(range(1, len(subs) + 1)):
            problems.append(f"section {top} subsections are {subs}, expected 1..{len(subs)}")
    rep.record(doc, "heading numbering", len(numbered), problems)


# ---------------------------------------------------------------- status agreement
#
# THE STALENESS CHECK. A work item is recorded twice - once as a row in a tracking table,
# once as its own heading - and the two drift apart. Measured in this house FOUR times in
# one file, and always in the same expensive direction: a heading reading NOT STARTED over
# work finished eight days earlier, which invites a session to redo it.
#
# WHY A CHECK AND NOT A HABIT. Nothing about the contradiction looks wrong. Both statements
# are well-formed, both are in the right place, and the reader sees whichever one they
# happened to open. It is only visible by comparing two parts of a file nobody reads
# together - which is what a machine is for.

#: A status word and the bucket it belongs to. ONLY A CROSS-BUCKET DISAGREEMENT IS A
#: FINDING: 'DONE' beside 'CLOSED' is two words for one state, and flagging it would train
#: people to ignore the check.
STATUS_WORDS = {
    "done": "done", "closed": "done", "complete": "done", "completed": "done",
    "built": "done", "absorbed": "done", "promoted": "done", "superseded": "done",
    "merged": "done", "delivered": "done", "shipped": "done", "fixed": "done",
    "not started": "open", "not done": "open", "todo": "open", "to do": "open",
    "open": "open", "in progress": "open", "outstanding": "open", "parked": "open",
    "deferred": "open", "blocked": "open", "pending": "open", "untouched": "open",
}

#: The nouns a numbered work item is introduced by. A heading must lead with one of these
#: plus an id, so an ordinary numbered section heading - '## 3 - Plan of action' - is not
#: mistaken for a work item and matched against whatever row happens to contain a 3.
ITEM_NOUNS = ("item", "backlog item", "phase", "step", "sub-step", "task", "proposal")

_ITEM_HEAD = re.compile(
    r"^(?:" + "|".join(ITEM_NOUNS) + r")\s+(\d+[a-z]?)\b", re.I)
_STATUS_ANY = re.compile(
    r"\b(" + "|".join(sorted((re.escape(w) for w in STATUS_WORDS), key=len, reverse=True))
    + r")\b", re.I)


def _plain(s: str) -> str:
    """Strip the decoration a status word is almost always wearing, and nothing else."""
    return re.sub(r"[*_`\[\]]", "", s).strip()


def _bucket_anywhere(s: str):
    """The bucket of the first status word in a string, or None."""
    m = _STATUS_ANY.search(_plain(s))
    return STATUS_WORDS[m.group(1).lower()] if m else None


def _bucket_leading(cell: str):
    """The bucket of a status word that BEGINS a cell, or None.

    LEADING, NOT ANYWHERE, and it is the difference between the check working and the check
    being useless. A real status cell reads 'not started. Partly done already: ...' - which
    contains a word from each bucket, so an anywhere-match calls the row ambiguous and skips
    exactly the rows worth reading. The first word is the verdict; the rest is commentary.
    """
    p = _plain(cell)
    m = _STATUS_ANY.match(p)
    return STATUS_WORDS[m.group(1).lower()] if m else None


def _row_cells(row: str):
    parts = CELL_PIPE.split(row.strip())
    if parts and parts[0] == "":
        parts = parts[1:]
    if parts and parts[-1] == "":
        parts = parts[:-1]
    return [p.strip() for p in parts]


def check_status_agreement(rep, doc, lines):
    """A heading's status word must not contradict the same item's row in a table above it.

    Scope, written down because a gate that does not state its own boundary has a silent
    one: it compares a NUMBERED work item - 'Item 5b', 'Phase 3', 'Step 12' - against a
    table row that carries the same id and opens a cell with a status word. A tracker that
    names its items rather than numbering them is NOT covered, and neither is a claim that
    is merely out of date rather than contradicted. Those stay with the closing procedure.
    """
    mask = code_fence_mask(lines)

    # Every table row above each point in the file, with the id(s) it might be about.
    rows = []                                   # (lineno, {ids}, bucket, text)
    for i, ln in enumerate(lines):
        if mask[i] or not ln.lstrip().startswith("|"):
            continue
        cells = _row_cells(ln)
        if len(cells) < 2 or DELIM_RE.match(ln):
            continue
        ids = set()
        for c in cells[:2]:                     # the id lives in a leading column
            m = re.fullmatch(r"\**\s*(\d+[a-z]?)\s*\**", c.strip())
            if m:
                ids.add(m.group(1).lower())
            m2 = _ITEM_HEAD.match(_plain(c))
            if m2:
                ids.add(m2.group(1).lower())
        bucket = next((b for b in (_bucket_leading(c) for c in reversed(cells)) if b), None)
        if ids and bucket:
            rows.append((i + 1, ids, bucket))

    problems, examined = [], 0
    for lineno, _level, text, _key in headings(lines):
        m = _ITEM_HEAD.match(_plain(text))
        if not m:
            continue
        head_bucket = _bucket_anywhere(text)
        if head_bucket is None:
            continue                            # a heading with no status word claims nothing
        item = m.group(1).lower()
        above = [r for r in rows if r[0] < lineno and item in r[1]]
        if not above:
            continue
        buckets = {r[2] for r in above}
        if len(buckets) > 1:
            # TWO ROWS ABOVE DISAGREE WITH EACH OTHER. Declared and skipped rather than
            # guessed at: picking one would report a contradiction against an arbitrary half.
            problems.append(
                f"line {lineno}: '{_plain(text)[:52]}' - two rows above disagree with each "
                f"other (lines {', '.join(str(r[0]) for r in above)}); cannot judge")
            examined += 1
            continue
        examined += 1
        row_line, _ids, row_bucket = above[-1]
        if row_bucket != head_bucket:
            problems.append(
                f"line {lineno}: heading says {head_bucket.upper()} - "
                f"'{_plain(text)[:52]}' - but its row at line {row_line} says "
                f"{row_bucket.upper()}. One of them is stale")
    rep.record(doc, "status words agree", examined, problems,
               na_reason=None if examined else
               "no numbered work item is stated both in a heading and in a table above it")


def check_internal_refs(rep, doc, lines, text):
    keys = {k for _, _, _, k in headings(lines) if k}
    if not keys:
        rep.record(doc, "internal refs resolve", 0, [], na_reason="no numbered headings to refer to")
        return
    mask = code_fence_mask(lines)
    refs, problems = [], []
    for i, ln in enumerate(lines):
        if mask[i]:
            continue
        # A reference shown inside backticks is a QUOTATION, not a reference - the same
        # rule the placeholder and formatter-damage scanners already apply via this helper.
        # Without it, a document that explains what a broken reference looks like is
        # reported as having broken references, which is the scanner matching itself.
        for m in REF_RE.finditer(strip_inline_code(ln)):
            key = m.group(1) if m.group(2) is None else f"{m.group(1)}.{m.group(2)}"
            refs.append(key)
            if key not in keys:
                # THE MESSAGE NAMES THE LIKELY CAUSE, because the check kept firing on the
                # same mistake and "no such heading" does not suggest the fix. A failing
                # reference is one of two things: a typo, or an attempt to point at ANOTHER
                # document - and the second is unwriteable with this notation, which is why
                # it keeps being attempted. Said unconditionally rather than guessed at from
                # the line: markdown wraps, so the filename is usually on a different line
                # from the reference, and a same-line heuristic misses the real cases.
                problems.append(
                    f"line {i + 1}: {SECTION_SIGN}{key} has no such heading - either a typo, "
                    f"or a CROSS-FILE reference, which this notation cannot express: a "
                    f"{SECTION_SIGN} resolves against THIS file only. For another document "
                    f'write it in words - "section {key} of `other.md`"')
    rep.record(doc, "internal refs resolve", len(refs), problems,
               na_reason=None if refs else f"no {SECTION_SIGN}N.M references in this document")


def check_file_links(rep, doc, path, lines):
    mask = code_fence_mask(lines)
    links, problems = [], []
    for i, ln in enumerate(lines):
        if mask[i]:
            continue
        for m in LINK_RE.finditer(ln):
            target = m.group(2).split()[0].strip("<>")
            if target.startswith(("http://", "https://", "mailto:", "#")):
                continue
            clean = target.split("#")[0]
            if not clean:
                continue
            links.append(clean)
            if not (path.parent / clean).exists():
                problems.append(f"line {i + 1}: link target not on disk - {clean}")
    rep.record(doc, "file links resolve", len(links), problems,
               na_reason=None if links else "no relative file links in this document")


def check_placeholders(rep, doc, lines, markers):
    if not markers:
        rep.record(doc, "no placeholders left", 0, [], na_reason="no markers configured")
        return
    mask = code_fence_mask(lines)
    hits = []
    for i, raw in enumerate(lines):
        if mask[i]:
            continue
        ln = strip_inline_code(raw)   # a marker shown in backticks is documentation
        for mk in markers:
            if mk in ln:
                hits.append(f"line {i + 1}: unfilled marker {mk!r}")
    # denominator is lines scanned, so an empty file reads as VOID rather than clean
    scanned = sum(1 for m in mask if not m)
    rep.record(doc, "no placeholders left", scanned, hits)


BACKSLASH = chr(92)
NL = chr(10)
# INLINE_CODE and strip_inline_code() moved to house_common.py on 2026-10-12: the archetype
# check blanks code spans before reading a declaration, and must blank them the same way.


def check_formatter_damage(rep, doc, lines, cfg):
    """Catch a markdown formatter having silently rewritten the file.

    VS Code's format-on-save did this to CLAUDE-TEMPLATE.md: it escaped every [[FILL]]
    marker and every numbered heading's trailing period, pushed emphasis markers inside
    code spans, and appended trailing hard breaks. It renders almost identically, which is
    why it went unnoticed for hours - while 85 of 160 section references quietly stopped
    resolving. The damage is mechanical, so it is detectable; this check is the alarm.
    """
    if not cfg.get("check_formatter_damage", True):
        rep.record(doc, "no formatter damage", 0, [], na_reason="disabled in config")
        return
    mask = code_fence_mask(lines)
    hard_breaks = cfg.get("flag_trailing_hard_breaks", True)
    problems, scanned = [], 0
    for i, raw in enumerate(lines):
        if mask[i]:
            continue
        scanned += 1
        n = i + 1
        # Only the escaped-bracket test uses prose-only text. For that one, documentation
        # and damage ARE distinguishable: a documented marker sits inside backticks, real
        # damage sits in prose. The emphasis tests must read the RAW line - blanking a code
        # span would either destroy the very pattern being looked for, or leave a gap that
        # looks like two adjacent bold runs. Measured: blanking produced both bugs.
        if BACKSLASH + "[" in strip_inline_code(raw) or BACKSLASH + "]" in strip_inline_code(raw):
            problems.append(f"line {n}: escaped square bracket - a formatter rewrote this")
        if re.match(r"^#{1,6} \d+" + re.escape(BACKSLASH) + r"\.", raw):
            problems.append(f"line {n}: escaped period in a numbered heading - breaks every parser")
        # NOT CHECKED: two adjacent bold runs ('**A** **B**'). It is a real symptom of a
        # split emphasis span, but it is also something an author legitimately writes - it
        # fired on this project's own prose. And it is redundant: every instance of the
        # damage ALSO left emphasis inside a code span, which the next test catches at
        # source. A check that flags correct writing stops being run, so it is gone.
        # Emphasis pushed INSIDE a code span: `**like this**`. Tested by extracting each
        # span and reading its CONTENT, never by matching backtick-star-...-star-backtick
        # across the raw line - that pattern runs from the CLOSING backtick of one span to
        # the OPENING backtick of the next, so ordinary prose like
        #     **`one.py`**. **`two.py`**
        # matched on the '. ' between them. Two bold-wrapped code spans separated by
        # punctuation is normal writing, and it appears throughout this house's own
        # documents; the check flagged them as damage.
        for span in INLINE_CODE.finditer(raw):
            inner = span.group(0)[1:-1]
            if inner.startswith("**") and inner.endswith("**") and len(inner) > 4:
                problems.append(f"line {n}: bold markers moved INSIDE a code span")
                break
        if hard_breaks and raw.strip() and raw != raw.rstrip():
            problems.append(f"line {n}: trailing whitespace - renders as a forced line break")
        # invisible characters: a formatter filled empty table cells with U+00A0, which
        # looks like a space, matches no pattern written with a plain space, and made an
        # Edit fail three times before anyone thought to look at the bytes.
        for ch, label in ((chr(0xA0), "U+00A0 non-breaking space"),
                          (chr(0x200B), "U+200B zero-width space"),
                          (chr(0xFEFF), "U+FEFF byte-order mark")):
            if ch in raw:
                problems.append(f"line {n}: {label} - invisible, use a plain space")
    rep.record(doc, "no formatter damage", scanned, problems)


def check_required_sections(rep, doc, lines, required):
    if not required:
        rep.record(doc, "required sections", 0, [], na_reason="none declared in config")
        return
    present = {t.strip() for _, _, t, _ in headings(lines)}
    problems = [f"missing required heading: {r}" for r in required
                if not any(r.lower() in p.lower() for p in present)]
    rep.record(doc, "required sections", len(required), problems)


WS_RUN = re.compile(r"\s+")


# collapse() MOVED TO house_common.py ON 2026-10-12 (v30). The forbidden and required arms
# here and the pointer check in verify_charter.py all need its wrap-tolerant matching, and a
# second copy of it is exactly where the two would quietly stop agreeing.


# read_phrase_list and resolve_list MOVED TO house_common.py ON 2026-09-02 (v12), when a
# second checker needed the identical resolver. resolve_list's own docstring already argued
# against a second copy - "written twice, the second copy is where the trap comes to mean
# something slightly different, and nothing reports that" - so a duplicate here would have
# been the first thing that paragraph contradicted. The two thin wrappers below stay, because
# they name THIS checker's config keys and nothing else does.


def resolve_forbidden(root: Path, cfg):
    """The FORBIDDEN list: strings that must not appear."""
    return resolve_list(root, cfg, "forbidden_phrases", "forbidden_phrases_file",
                        FORBIDDEN_LIST_ENV, "forbidden")


def resolve_required(root: Path, cfg):
    """The REQUIRED list: strings that must appear."""
    return resolve_list(root, cfg, "required_strings", "required_strings_file",
                        REQUIRED_LIST_ENV, "required")


def check_forbidden(rep, doc, lines, phrases, sources):
    """Phrases that must not appear - reported by POSITION, never by value.

    Printing the phrase would republish it into a terminal, a CI log or a pasted failure
    report. Moving the list out of the repository and then echoing its contents is the
    same leak by a different route, and it reaches places nothing can clean up afterwards.
    """
    if not phrases:
        rep.record(doc, "forbidden phrases absent", 0, [], na_reason="none declared in config")
        return
    text, where = collapse(lines)
    hits, total = [], len(phrases)
    for n, phrase in enumerate(phrases, 1):
        needle = WS_RUN.sub(" ", phrase.strip()).lower()
        if not needle:
            continue
        at = text.find(needle)
        while at != -1:
            hits.append(f"line {where[at]}: forbidden phrase #{n} of {total} "
                        f"(source: {sources[n - 1]})")
            at = text.find(needle, at + 1)
    rep.record(doc, "forbidden phrases absent", total, hits)


def _needle_hits(pairs, phrases, sources):
    """Forbidden hits inside one contiguous run of (line number, text). Positions only."""
    if not pairs:
        return []
    text, where = collapse([t for _, t in pairs], [n for n, _ in pairs])
    out, total = [], len(phrases)
    for n, phrase in enumerate(phrases, 1):
        needle = WS_RUN.sub(" ", phrase.strip()).lower()
        if not needle:
            continue
        at = text.find(needle)
        while at != -1:
            out.append(f"line {where[at]}: forbidden phrase #{n} of {total} "
                       f"(source: {sources[n - 1]}) - INTRODUCED BY THIS CHANGE")
            at = text.find(needle, at + 1)
    return out


def check_forbidden_added(rep, doc, path, phrases, sources, baseline):
    """The same needles, over the lines THIS CHANGE ADDED - not the whole file.

    WHY A SECOND ROW RATHER THAN A REPLACEMENT. Whole-file scanning drowns the result in
    pre-existing hits, and a report a reviewer skims is a control nobody believes. But the
    whole-file row STAYS: a confidentiality control is never weakened, and the pair is what
    makes a hit legible - both rows failing means the phrase was introduced here, only the
    first failing means it was already in the file and this change did not add it.

    N/A HERE IS SAFE ONLY BECAUSE THE RUN-LEVEL GUARD RAN FIRST. "This change adds nothing
    to this file" and "my baseline is the working tree" produce the same empty diff, and
    the second is the failure that reports 100% clean. house_common.baseline_guard settles
    which of the two it is ONCE PER RUN, before any file is judged, and hands VOID down
    here when it cannot.
    """
    sha, void, root = baseline
    if not sha:
        # DECLARED-BUT-UNRESOLVABLE IS VOID; NOTHING DECLARED IS N/A. These two were one
        # branch when this was written, which made a baseline naming a revision that does
        # not exist report as a decision rather than as an accident - A2's rule about a
        # declared-but-unreadable LIST, and the same conflation it was built to stop.
        if void:
            rep.record(doc, "forbidden in added lines", 0, [], void_reason=void)
        else:
            rep.record(doc, "forbidden in added lines", 0, [],
                       na_reason="no diff_baseline declared in config")
        return
    if void:
        rep.record(doc, "forbidden in added lines", 0, [], void_reason=void)
        return
    if not phrases:
        rep.record(doc, "forbidden in added lines", 0, [],
                   na_reason="no forbidden phrases declared")
        return
    # THE ROOT IS PASSED IN, NEVER READ FROM THE CURRENT DIRECTORY. A checker that resolves
    # a repository from cwd works perfectly until something calls it from elsewhere, and
    # then reports on the wrong tree - or on no tree - without failing.
    try:
        rel = path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        rep.record(doc, "forbidden in added lines", 0, [],
                   void_reason=f"{path} is outside the repository at {root} - not compared")
        return
    runs = added_line_runs(root, sha, rel)
    if runs is None:
        rep.record(doc, "forbidden in added lines", 0, [],
                   void_reason=f"could not diff {rel} against {sha[:12]}")
        return
    added = sum(len(r) for r in runs)
    if added == 0:
        rep.record(doc, "forbidden in added lines", 0, [],
                   na_reason=f"this change adds no lines to this file (baseline {sha[:12]})")
        return
    hits = []
    for run in runs:
        hits += _needle_hits(run, phrases, sources)
    rep.record(doc, "forbidden in added lines", added, hits)


def check_required(rep, doc, lines, items, sources):
    """Strings that MUST appear - the REQUIRED claim kind, and the mirror of the above.

    WHY A PRESENCE CHECK IS WORTH MORE THAN AN ABSENCE ONE HERE. A forbidden phrase
    arriving in a document is an act somebody performed; a required one LEAVING is
    usually not - it goes in a reflow, a paste, a section rewritten from memory, or a
    relocation that moved the only copy. Nothing errors, nothing renders differently, and
    the sentence that stated the rule is simply not there any more. This house has
    measured that exact loss: a relocation promoted a duplicate into the only copy, and a
    rule scoped to a glob that never fires was not relocated but lost.

    MATCHED OVER THE COLLAPSED DOCUMENT, reusing the same helper the forbidden check uses.
    That is A3's matcher, and the pairing matters: were this to grow its own, the two
    would answer differently on the same wrapped input and the report would contradict
    itself between two adjacent rows.

    THE REPORT NAMES AN INLINE STRING AND ONLY AN INLINE STRING. A missing string has no
    position IN THE DOCUMENT - that is what missing means - so 'phrase #3 of 7' is the
    entire finding, and for a committed list that is uselessly opaque when the value is
    sitting in verify.config.json anyway. For a list held outside the repository the
    calculation reverses completely: naming it publishes it, and by a route no scanner
    reaches afterwards. So origin decides, per item, and both halves are proved in the
    selftest so neither can be "simplified" away later.
    """
    if not items:
        rep.record(doc, "required strings present", 0, [],
                   na_reason="none declared in config")
        return
    text, _ = collapse(lines)
    missing, total = [], len(items)
    for n, item in enumerate(items, 1):
        needle = WS_RUN.sub(" ", item.strip()).lower()
        if not needle:
            continue
        if text.find(needle) == -1:
            src = sources[n - 1]
            # Named for 'config' only. See the docstring - this asymmetry is deliberate
            # and is asserted both ways in selftest_required.
            shown = f": {item.strip()!r}" if src == "config" else ""
            missing.append(f"required string #{n} of {total} is MISSING "
                           f"(source: {src}){shown}")
    rep.record(doc, "required strings present", total, missing)


def check_line_length(rep, doc, lines, limit):
    if not limit:
        rep.record(doc, "line length", 0, [], na_reason="max_line_length is 0 (disabled)")
        return
    mask = code_fence_mask(lines)
    long = [f"line {i + 1}: {len(ln)} chars" for i, ln in enumerate(lines)
            if not mask[i] and len(ln) > limit]
    rep.record(doc, "line length", len(lines), long)


def section_sizes(lines):
    """{'7': 60, ...} - lines per TOP-LEVEL numbered section, its heading line included.

    Measured by LISTING the span to the next heading of the SAME OR HIGHER level, never by
    adding subsections up. The first attempt at this measurement differenced against the
    next heading of ANY level and reported section 1 as two lines - which is the gap to
    section 1.1, not the size of section 1. It was caught by the answer being implausible.
    """
    return {key: len(span) for key, span in section_spans(lines).items()}


def section_spans(lines):
    """{'7': [its lines], ...} - each TOP-LEVEL numbered section's lines, heading included.

    THE ONE PLACE A SECTION'S SPAN IS TAKEN, since v31. section_sizes, section_shapes and the
    wrapped weight all read it, so a section's three measures cannot cover different lines -
    the span loop had already been written twice, and a third copy is how they come to differ.

    headings() reports ONE-BASED line numbers, which is why the slice is [i - 1:end - 1] and
    not [i:end]. Taken the obvious way a span starts one line late and ends one line early,
    and STILL SUMS TO THE RIGHT TOTAL - so a control on the total passes while every
    section's first line is the previous section's last.
    """
    hs = [(i, lvl, key) for i, lvl, _, key in headings(lines)]
    out = {}
    for at, (i, lvl, key) in enumerate(hs):
        if not key or "." in key:
            continue
        end = len(lines) + 1
        for j, lvl2, _ in hs[at + 1:]:
            if lvl2 <= lvl:
                end = j
                break
        out[key] = lines[i - 1:end - 1]
    return out


def section_wrapped_sizes(lines):
    """{'7': 31, ...} - each top-level section's WRAPPED weight, over the same span
    section_sizes counts, weighing only what LOADS: text inside an HTML comment weighs
    nothing, exactly as in the file-length row. Weighing the raw span instead let a long
    maintainer note fail a section cap the file row ignored (code review, v31).

    THE TRAILING NEWLINE IS LOAD-BEARING: wrapped_lines treats a final newline as ending the
    last line, so a span joined without one loses its last line whenever that line is blank -
    and most sections end on a blank line."""
    return {key: wrapped_lines("\n".join(span) + "\n")
            for key, span in section_spans(lines).items()}


def shape_of(lines):
    """{'blank': n, 'heading': n, 'table': n, 'prose': n} - what a span is MADE of.

    WHY A REDUCTION CANNOT BE PLANNED WITHOUT IT. Two blocks of eighty lines are not the
    same size of problem. A heading may never be deleted - it is the return path every
    relocated pointer resolves against - and a table row is one PHYSICAL line however long
    it is, so under line_measure 'physical' rewriting a verbose row saves nothing on the gate.
    Only the PROSE count is reducible by rewriting there, and a saving estimated off the span
    instead of off the prose is optimistic by however much structure the span holds.
    Measured on the first two reductions this house ran, estimates made that way came in at
    about a THIRD of estimate.

    THAT BLINDNESS WAS ALSO AN INCENTIVE, which is why line_measure 'wrapped' exists (v31): a
    physical cap could be met by moving prose INTO a table row, and a 16,155-character row
    counted as one line in a real charter. Under 'wrapped' a long row weighs its length like
    any line, and shortening it DOES reduce the section - the wrapped count printed beside
    each section size is that weight.

    IT IS ALSO THE FLOOR. blank + heading + table is the smallest a span can become without
    deleting a heading or dropping a rule - under either measure, each row being at least
    one line - so a target BELOW that floor is unreachable and can be shown to be unreachable
    before the work starts rather than after it.

    EVERY LINE IS COUNTED EXACTLY ONCE, so the four sum to the span and the sum is the
    control - a classifier that double-counts or drops a line reports a shape that looks
    plausible and is wrong. Fenced code is PROSE here on purpose: it is neither structure
    nor a rule, and it is reducible, which is the only question this measure is asked.
    """
    mask = code_fence_mask(lines)
    out = {"blank": 0, "heading": 0, "table": 0, "prose": 0}
    for i, ln in enumerate(lines):
        s = ln.strip()
        if not s:
            out["blank"] += 1
        elif mask[i]:
            out["prose"] += 1
        elif s.startswith("#"):
            out["heading"] += 1
        elif s.startswith("|"):
            out["table"] += 1
        else:
            out["prose"] += 1
    return out


def section_shapes(lines):
    """{'1': {...}, ...} - shape_of for each TOP-LEVEL numbered section.

    Spans are taken the same way section_sizes takes them, and the SUM of each section's
    four counts is asserted against section_sizes in the selftest - two span measurements in
    one report is how the report comes to disagree with itself, which is the defect
    section_size_report exists to make impossible.

    headings() reports ONE-BASED line numbers, which is why the slice is [i - 1:end - 1] and
    not [i:end]. Taken the obvious way this measure starts one line late and ends one line
    early, and STILL SUMS TO THE RIGHT TOTAL - so the control would have passed while every
    section's first line was the previous section's last. Caught only by reading the helper
    it borrows from. Since v31 the span comes from section_spans, the one place it is taken.
    """
    return {key: shape_of(span) for key, span in section_spans(lines).items()}


def expand_targets(root, entries):
    """Expand any glob in 'md.files'; return (paths, globs-that-matched-nothing).

    WHY THIS EXISTS. 'md.files' was a literal list, so a bare run checked only what somebody
    had remembered to name. In practice that meant the CHARTER and nothing else -- and the
    internal-reference check, which is the one that catches a section sign pointing at another
    document, never ran over the PLAN files at all. Three such references were written into
    plan files in one day before anyone noticed, each caught only by naming the file on the
    command line by hand.

    Listing plan files literally instead would move the defect rather than fix it: the NEXT
    plan file is not in the list, and nothing says so. A glob covers the kind. And because a
    glob can itself stop matching, main() reports an empty one as VOID rather than passing.

    Sorted, so the report order is stable and a diff of two runs is readable.
    """
    paths, empty = [], []
    for entry in entries:
        s = str(entry)
        if any(ch in s for ch in "*?["):
            hits = sorted(root.glob(s))
            if hits:
                paths.extend(hits)
            else:
                empty.append(s)
        else:
            paths.append(Path(s))
    seen, out = set(), []
    for p in paths:
        key = str(p).lower()
        if key not in seen:
            seen.add(key)
            out.append(p)
    return out, empty


def in_size_scope(path, globs):
    """Is this document one the size rule is even ABOUT?

    A cap belongs to a charter. Applied to every markdown file in a run it produces
    confident false failures - which is worse than no check, because the run then carries
    failures a reader has to learn to ignore, and a reader who ignores two will ignore three.
    Matched against the bare filename and the whole path, so both "CLAUDE.md" and
    "docs/CLAUDE.md" can be named.
    """
    name, full = Path(path).name, str(path).replace(chr(92), "/")
    return any(fnmatch(name, g) or fnmatch(full, g) for g in globs)


def cap_for(path, max_lines, in_scope):
    """The line cap that applies to ONE file, and the glob it came from.

    Returns (cap, glob, void_reason). cap 0 means no cap applies.

    max_lines is EITHER an int - one cap for everything in size_scope, the original shape -
    OR a mapping of glob to cap, which is what lets a 120-line plan file and a 350-line
    charter be judged in the same run. One cap per project stopped being enough the moment
    a project had two kinds of document with two size classes, and until this existed the
    smaller one was checked by a person reading a printed number.

    THE LONGEST MATCHING GLOB WINS, because overlap is the normal case and not a mistake:
    '*.md' sets a house default, 'PLAN-*.md' overrides it for one kind of document.

    A TIE IS REFUSED, NOT RESOLVED. Two globs of the same length both matching is a config
    no reader can predict, and picking one silently is how a file comes to be measured
    against a cap its author never chose - a wrong cap that PASSES is worse than no cap,
    because it is evidence of a check that did not happen.
    """
    if not isinstance(max_lines, dict):
        return (max_lines if in_scope else 0), None, None
    name, full = Path(path).name, str(path).replace(chr(92), "/")
    hits = [g for g in max_lines if fnmatch(name, g) or fnmatch(full, g)]
    if not hits:
        return 0, None, None
    longest = max(len(g) for g in hits)
    top = sorted(g for g in hits if len(g) == longest)
    if len(top) > 1:
        return 0, None, ("max_lines is ambiguous for this file - "
                         + " and ".join(repr(g) for g in top)
                         + " are the same length and both match. Make the more specific one "
                           "longer, or remove one")
    return max_lines[top[0]], top[0], None


def check_file_length(rep, doc, text, limit, in_scope=True, path=None, measure="physical"):
    """THE ONE DEFECT WITH NO ERROR MESSAGE. A charter over its cap is never truncated - it
    is loaded in full and simply followed less well, so nothing ever tells you it happened
    and you cannot tell the result from a session that was going badly anyway. Which is why
    it needs a check rather than a habit.

    Over the cap means RELOCATE, not delete. Length is not the defect; content that is not
    needed in every session being loaded in every session is the defect.

    `measure` IS line_measure (v31): 'physical' counts lines, 'wrapped' weighs each at its
    length. Whichever gates, an over-cap finding names the other, so a project sees what
    switching would do; a measure this file does not know is VOID.
    """
    per_glob = isinstance(limit, dict)
    cap, glob, void = cap_for(path if path is not None else doc, limit, in_scope)
    if void:
        rep.record(doc, "file length", 0, [], void_reason=void)
        return
    if not cap:
        if glob is not None:
            # A MATCHED GLOB DECLARING 0 IS AN EXEMPTION, and it must not read as "nothing
            # matched". They are different facts: one is a decision somebody took, the other
            # is a file the config forgot. Reporting both the same way hides the second.
            reason = f"exempt - {glob!r} declares a cap of 0"
        elif per_glob:
            reason = ("no glob in max_lines matches this file" if limit
                      else "max_lines is empty (disabled)")
        elif not limit:
            reason = "max_lines is 0 (disabled)"
        else:
            reason = "not in size_scope - a cap is a charter's"
        rep.record(doc, "file length", 0, [], na_reason=reason)
        return
    bad = measure_problem(measure)
    if bad:
        rep.record(doc, "file length", 0, [], void_reason=bad)
        return
    phys, raw, wrap = loaded_lines(text), raw_lines(text), wrapped_lines(text)
    got = wrap if measure == "wrapped" else phys
    unit = f"wrapped lines (at {WRAP_WIDTH})" if measure == "wrapped" else "lines"
    over = []
    if got > cap:
        via = f" (via {glob!r})" if glob else ""
        over.append(f"{got} {unit} loaded against a cap of {cap}{via} - {got - cap} over. "
                    f"RELOCATE, do not delete: a path-scoped rule, a companion document, "
                    f"a plan document, or a hook")
        # THE OTHER MEASURE, NAMED. Under physical it is what a switch will gate on; under
        # wrapped it is the count a project remembers its cap in. Equal numbers say nothing.
        if wrap != phys:
            other = (f"{phys} physical lines" if measure == "wrapped"
                     else f"{wrap} wrapped at {WRAP_WIDTH} - what line_measure 'wrapped' gates on")
            over.append(f"and {other}")
    # RAW BESIDE LOADED, AND ONLY WHEN THEY DIFFER. The cap is enforced on what Claude
    # receives, but it is READ as a promise about how much document a person scrolls, and
    # block-level HTML comments are invisible to exactly one of those two. Equal numbers say
    # nothing worth a line; unequal numbers mean a maintainer note exists and has to be
    # declared rather than found later. It is a FINDING, not a failure - the note may be
    # entirely legitimate - so it is appended only when the file is already over, and
    # otherwise carried in the size breakdown where a person reading sizes will see it.
    if raw != phys and over:
        over.append(f"and {raw} lines RAW - {raw - phys} line(s) sit inside HTML comments, "
                    f"which the cap does not count and a reader still scrolls past")
    rep.record(doc, "file length", got, over)


def check_section_caps(rep, doc, lines, caps, in_scope=True, measure="physical"):
    """A cap on ONE section, because the section that is replaced every session bloats
    fastest and a whole-file cap hides that inside a number that looks fine.

    A capped section that is ABSENT is a finding rather than a silent pass - but only in a
    document that uses numbered sections at all, or every README in the run would fail for
    not having a section 7.

    `measure` is line_measure (v31), as in check_file_length: the same span, counted or
    weighed.
    """
    if not caps:
        rep.record(doc, "section length", 0, [], na_reason="section_caps is empty (disabled)")
        return
    if not in_scope:
        rep.record(doc, "section length", 0, [], na_reason="not in size_scope - a cap is a charter's")
        return
    bad = measure_problem(measure)
    if bad:
        rep.record(doc, "section length", 0, [], void_reason=bad)
        return
    wrapped = measure == "wrapped"
    sizes = section_wrapped_sizes(lines) if wrapped else section_sizes(lines)
    unit = "wrapped lines" if wrapped else "lines"
    if not sizes:
        rep.record(doc, "section length", 0, [],
                   na_reason="document uses no numbered top-level sections")
        return
    problems = []
    for key in sorted(caps, key=lambda k: (len(str(k)), str(k))):
        cap = caps[key]
        if key not in sizes:
            problems.append(f"section {key} is capped at {cap} and has no heading here")
        elif sizes[key] > cap:
            problems.append(f"section {key}: {sizes[key]} {unit} against a cap of {cap} "
                            f"- {sizes[key] - cap} over")
    rep.record(doc, "section length", len(caps), problems)


def check_charter_rows(rep, doc, lines, cfg, scoped, plan_scoped):
    """The six charter rows - verify_charter.py's, or six FAILs naming it when it is missing.

    THE CHECKS THEMSELVES LIVE IN verify_charter.py SINCE 2026-10-12 (v30): charter structure,
    charter archetype, the CORE floor, sections agreed out, relocation pointers and plan
    purpose. They hold a charter to CLAUDE-TEMPLATE.md's shape, so they change whenever the
    template does - and while they lived here, every template change marked every project's
    copy of THIS file stale, for a change most documents could not feel.

    A MISSING verify_charter.py FAILS, IT NEVER VANISHES. Six rows that silently stopped
    being printed read exactly like six rows that passed, and only a reader who knew to count
    them would notice. The FAIL names the file, so the remedy is in the report itself.
    """
    if verify_charter is None:
        why = ((_CHARTER_MISSING or "verify_charter.py is not installed beside verify_md.py")
               + ", so this charter check did not run - copy verify_charter.py and "
               "house_common.py from the shared standard-scripts folder")
        for name in CHARTER_ROWS:
            rep.record(doc, name, 1, [why])
        return
    verify_charter.check_charter(rep, doc, lines, cfg, scoped, plan_scoped)


def section_size_report(path, body, cfg):
    """The per-section breakdown for one document, as lines. Returns [] if it has no
    numbered top-level sections.

    IT IS A FUNCTION BECAUSE IT WAS A PRINT LOOP INSIDE main(), AND THEREFORE UNTESTABLE -
    which is how it came to contradict the check beside it. It annotated every capped section
    with "cap N, OVER by M" whether or not the cap APPLIED to that file, while
    check_section_caps correctly reported N/A for the same file in the same run. One run said
    two different things about one document, and a reader who learns to ignore one of them
    learns to ignore the other.

    A cap belongs to a CHARTER. Out of size_scope, the sizes are still worth seeing - that is
    the point of a breakdown - but they are reported WITHOUT a verdict, and the reason is
    named rather than left for the reader to infer.

    BOTH MEASURES ARE PRINTED, ALWAYS (v31): the physical count and the wrapped weight, for
    the file and for every section, and the verdict mark follows the measure that gates. The
    release that added line_measure gates on physical lines by default, so this breakdown is
    where a project sees what a switch to 'wrapped' will do before it switches.
    """
    lines = body.splitlines()
    sizes = section_sizes(lines)
    if not sizes:
        return []
    wsizes = section_wrapped_sizes(lines)
    measure = cfg.get("line_measure", "physical")
    bad = measure_problem(measure)
    gated = wsizes if measure == "wrapped" else sizes
    unit = "wrapped lines" if measure == "wrapped" else "physical lines"
    scoped = in_size_scope(path, cfg["size_scope"])
    cap, glob, void = cap_for(path, cfg["max_lines"], scoped)
    if void:
        against = "  (no cap applies - max_lines is ambiguous for this file)"
    elif bad:
        against = f"  (no verdict - {bad})"
    elif cap:
        against = f" against a cap of {cap} {unit}" + (f" (via {glob!r})" if glob else "")
    elif glob is not None:
        # SAME ORDER AS check_file_length, deliberately. This branch existing after the
        # dict branch is what made the report say "no glob matches" about a file the check
        # had just called exempt - one run, one file, two answers, which is the defect this
        # function was extracted to make impossible.
        against = f"  (no cap applies - exempt, {glob!r} declares 0)"
    elif isinstance(cfg["max_lines"], dict):
        against = "  (no cap applies - no glob in max_lines matches)"
    elif not scoped:
        against = "  (no cap applies - not in size_scope)"
    else:
        against = " (no cap set)"
    got, raw, wrap = loaded_lines(body), raw_lines(body), wrapped_lines(body)
    also = "" if raw == got else f" ({raw} raw - {raw - got} in HTML comments)"
    out = [f"  {path}: {got} loaded ({wrap} wrapped at {WRAP_WIDTH}){also}{against}"]
    shapes = section_shapes(lines) if cfg["report_section_shape"] else {}
    for key in sorted(sizes, key=lambda k: (len(str(k)), str(k))):
        mark = ""
        sc = cfg["section_caps"].get(key)
        if sc and scoped and not bad:
            over = gated[key] - sc
            mark = f"  <- cap {sc}" + (f", OVER by {over}" if over > 0 else ", ok")
        elif sc and not bad:
            mark = "  <- capped elsewhere, not here"
        out.append(f"      section {key:<4} {sizes[key]:>5} lines {wsizes[key]:>5} wrapped{mark}")
        sh = shapes.get(key)
        if sh:
            # THE FLOOR IS PRINTED, NOT LEFT TO BE ADDED UP. blank + heading + table is the
            # smallest this section can become without deleting a heading or dropping a
            # rule, and a target under it is unreachable - which is worth knowing BEFORE
            # the rewriting starts rather than after. Only 'prose' answers "how much of
            # this can a rewrite touch", and an estimate taken off the span instead came
            # in at about a third of estimate on the first two reductions this house ran.
            floor = sh["blank"] + sh["heading"] + sh["table"]
            out.append(f"             shape: {sh['prose']:>4} prose  "
                       f"{sh['table']:>4} table  {sh['heading']:>3} heading  "
                       f"{sh['blank']:>4} blank   -> floor {floor}")
    return out


def list_numeric_claims(doc, lines):
    """Report-only. Cannot know whether '212 rows' is true - only that it must be re-derived."""
    mask = code_fence_mask(lines)
    out = []
    for i, ln in enumerate(lines):
        if mask[i]:
            continue
        for m in NUMERIC_CLAIM_RE.finditer(ln):
            out.append((i + 1, m.group(0)))
    return out


def list_cross_doc_refs(lines):
    """Lines that name another document AND use a section sign, which is probably a
    cross-document reference written the one way that cannot work.

    WHY THIS IS A REPORT AND NOT A CHECK. A section sign resolves against the file it appears
    in. The resolver can only complain when the number is ABSENT locally; where the number
    happens to exist, the reference passes against the wrong section - and it passes
    silently, which is the worse half. Measured on one 1,578-line charter: 27 genuine
    cross-document references, 5 reported, 22 passing against the wrong section.

    The checker cannot know which file a sign was meant for, so making it stricter would
    only trade silent wrong passes for confident wrong failures. It lists candidates and a
    person decides - the same contract as the numeric-claims report, and for the same reason:
    the tool can see the shape and not the truth.

    THAT LAST SENTENCE IS THE DEFINITION OF A JUDGE, and since CHECKER VERSION 17 this is
    one: check_cross_doc_refs below turns these candidates into a report ROW rather than a
    paragraph printed underneath the report. Nothing about the finding changed - what
    changed is that a run handing 22 wrong-section references to a person can no longer be
    mistaken, by a reader or by run_tests.py, for a run that found none.
    """
    mask = code_fence_mask(lines)
    out = []
    for i, ln in enumerate(lines):
        if mask[i]:
            continue
        bare = strip_inline_code(ln)
        if SECTION_SIGN not in bare:
            continue
        # a .md filename anywhere on the line, in code span or not - the filename is
        # usually backticked and the sign usually is not, so the raw line is the right input
        if DOC_NAME_RE.search(ln):
            out.append((i + 1, ln.strip()[:100]))
    return out


def check_cross_doc_refs(rep, doc, lines):
    """The candidates from list_cross_doc_refs, as a JUDGE row.

    WHY THIS IS A ROW AND NOT A PARAGRAPH. It was a paragraph, printed after the report and
    ending "check each BY HAND". Everything about that was true and none of it was reachable:
    the verdict line above it said PASS, the exit code said 0, and run_tests.py - which sees
    only an exit code and stdout - had no way to tell a run with 22 suspect references from
    a clean one. A finding whose only home is prose under a green verdict is a finding that
    gets scrolled past.

    IT MUST NEVER BE A FAIL, which is the other half of why the severity had to exist first.
    A section sign that resolves locally is not wrong - it is unprovable either way from
    here, and only the author knows which document was meant. Failing on it would trade
    silent wrong passes for confident wrong failures, and the confident kind gets the check
    disabled.
    """
    hits = list_cross_doc_refs(lines)
    # judge_reason is passed UNCONDITIONALLY and that is deliberate: record() judges only
    # when there are candidates, so a document with none PASSES here. Writing the condition
    # again at the call site would put the same rule in two places, and the checkers'
    # verdicts are the last thing that should have two copies of a rule.
    rep.record(doc, "cross-doc refs", len(lines),
               [f"line {n}: {snippet}" for n, snippet in hits],
               judge_reason="a section sign resolves against ITS OWN file - any of these "
                            "whose number also exists here has already PASSED against the "
                            "wrong section, silently. Only the author knows which document "
                            "was meant.")


# ------------------------------------------------------------------------ the runner

def read_doc(path):
    """Return (text, error). A file we cannot decode must FAIL, never crash the run -
    a traceback aborts every remaining check and produces no report at all."""
    try:
        return path.read_text(encoding="utf-8"), None
    except UnicodeDecodeError as e:
        return None, f"not valid UTF-8 at byte {e.start}: {e.reason}"
    except OSError as e:
        return None, f"cannot read: {e}"


def resolve_baseline(root: Path, cfg):
    """(sha, void_reason, root) for this run's diff baseline, resolved ONCE.

    Once, not per document, for the same reason the phrase lists are: a baseline that does
    not resolve is one fact about the run, and re-deriving it per file reports the same
    accident as many separate findings.
    """
    spec = str(cfg.get("diff_baseline", "") or "").strip()
    if not spec:
        return None, None, root
    sha, err = resolve_revision(root, spec)
    if err:
        return None, err, root
    return sha, baseline_guard(root, sha), root


def doc_label(path) -> str:
    """A document's name in the report: RELATIVE TO THE WORKING DIRECTORY where possible.

    TWO REASONS, AND THE SECOND ONE IS A CONFIDENTIALITY CONTROL.

    First, the label is now an IDENTIFIER, not just a caption: verify_expected.py keys a
    declared exemption on `checker::doc::check`. `str(path)` gave whatever form the caller
    happened to use - relative when a shell expanded the glob, ABSOLUTE when this script
    expanded it internally - so the same document produced two different keys depending on
    how it was invoked, and a declaration written from one invocation silently matched
    nothing in the other.

    Second, an absolute path on this platform contains a USERNAME. Emitting one into a
    report that gets pasted into a config, a commit message or a CI log publishes it - and
    in a repository that also scans for that username, writing the key into the committed
    config would make the scan fail on its own settings file.

    Falls back to the absolute path when the file is genuinely outside the working
    directory, because a wrong-but-short label is worse than a long true one.
    """
    try:
        return Path(path).resolve().relative_to(Path.cwd().resolve()).as_posix()
    except ValueError:
        return str(path)


def verify_file(rep, path, cfg, forbidden=None, required=None,
                baseline=(None, None, None)):
    doc = doc_label(path)
    text, err = read_doc(path)
    if err:
        rep.record(doc, "file is readable UTF-8", 1, [err])
        return
    phrases, sources, void_reason = forbidden if forbidden else ([], [], None)
    req, req_sources, req_void = required if required else ([], [], None)
    lines = text.splitlines()
    check_tables(rep, doc, lines)
    check_headings(rep, doc, lines, cfg["check_numbered_headings"])
    if cfg["check_internal_refs"]:
        check_internal_refs(rep, doc, lines, text)
    if cfg["check_file_links"]:
        check_file_links(rep, doc, path, lines)
    if cfg.get("check_status_agreement", True):
        check_status_agreement(rep, doc, lines)
    if cfg["report_cross_doc_refs"]:
        check_cross_doc_refs(rep, doc, lines)
    check_placeholders(rep, doc, lines, cfg["placeholder_markers"])
    check_formatter_damage(rep, doc, lines, cfg)
    check_required_sections(rep, doc, lines, cfg["required_sections"])
    if void_reason:
        rep.record(doc, "forbidden phrases absent", 0, [], void_reason=void_reason)
        rep.record(doc, "forbidden in added lines", 0, [], void_reason=void_reason)
    else:
        check_forbidden(rep, doc, lines, phrases, sources)
        # THE DIFF-SCOPED TWIN, always emitted so the pair can be read together. Silence
        # from this row would be indistinguishable from "nothing was introduced", which is
        # the one reading it must never permit.
        check_forbidden_added(rep, doc, path, phrases, sources, baseline)
    # The same two-branch shape as the forbidden half, and for the same reason: a declared
    # list that cannot be read must reach the report as VOID. Falling through to the check
    # with an empty list would print a PASS over a control that never ran.
    if req_void:
        rep.record(doc, "required strings present", 0, [], void_reason=req_void)
    else:
        check_required(rep, doc, lines, req, req_sources)
    check_line_length(rep, doc, lines, cfg["max_line_length"])
    scoped = in_size_scope(path, cfg["size_scope"])
    check_file_length(rep, doc, text, cfg["max_lines"], scoped, path, cfg["line_measure"])
    check_section_caps(rep, doc, lines, cfg["section_caps"], scoped, cfg["line_measure"])
    # THE SIX CHARTER ROWS, from verify_charter.py since v30. Both scope answers are worked out
    # HERE, because glob matching is this file's and serves the size caps as well. plan_scope
    # is a SEPARATE scope from size_scope: 'is this a charter' and 'is this a LIVE plan file'
    # are different populations, and the second one moves as phases close. None = disabled.
    plan_globs = cfg.get("plan_scope") or []
    plan_scoped = in_size_scope(path, plan_globs) if plan_globs else None
    check_charter_rows(rep, doc, lines, cfg, scoped, plan_scoped)


def load_config(root: Path):
    return load_section(root, "md", DEFAULT_CONFIG)


# -------------------------------------------------------------------------- selftest

BASE = "# Doc" + NL + NL + "## 1 - One" + NL + NL + "Body." + NL

# A VALID table that must NOT be flagged. An escaped pipe is a literal character in a
# cell; splitting on every pipe makes this row look one column wider than its neighbours.
GOOD_TABLE = (NL + "| syntax | meaning |" + NL + "| --- | --- |" + NL
              + "| `a " + BACKSLASH + "| b` | an escaped pipe, still one cell |" + NL
              + "| plain | an ordinary cell |" + NL)

# constructs that MUST NOT be flagged: a code span that legitimately shows literal
# markdown, a Python dunder, and a deliberate example of bold inside code.
FALSE_POSITIVE_GUARDS = [
    "| `> **X**` blockquote | shows literal markdown |",
    "the object's own `__repr__` shows which keys are set",
    "the document had been edited to `**82** tracked`, so the check matched nothing",
    "a glob like `**/*.py` selects every Python file",
    # TWO BOLD-WRAPPED CODE SPANS SEPARATED BY PUNCTUATION. The check used to match from
    # the closing backtick of the first to the opening backtick of the second and call it
    # damage. It is ordinary prose, and it appears throughout this house's own documents.
    "**`run_tests.py`** ships. **`smoke_test.py`** deliberately does not.",
    # an author legitimately writes two adjacent bold runs - this must NOT be flagged
    "**What landed.** **The three levels** are project, step and task.",
    # a document that DOCUMENTS the damage must not be reported as damaged
    "the formatter escaped it to `" + BACKSLASH + "[" + BACKSLASH + "[FILL: name"
    + BACKSLASH + "]" + BACKSLASH + "]` which broke the parser",
    "it turned the heading into `## 3" + BACKSLASH + ". Plan of action` overnight",
    # NOT included as a guard: showing an adjacent-bold-run example inside a single code
    # span is genuinely indistinguishable from the damage itself. Document that shape in a
    # fenced block, which the mask already excludes, rather than inline.
]
GUARDS = NL + (NL + NL).join(FALSE_POSITIVE_GUARDS) + NL

# A file that cannot be decoded must produce a FAIL row, not a traceback.
# A file that cannot be decoded must produce a FAIL row, not a traceback.
UNDECODABLE = bytes([35, 32, 84, 105, 116, 108, 101, 10, 10,        # "# Title" + 2 newlines
                     67, 97, 102, 0xE9, 32,                         # "Caf" + a LATIN-1 e-acute
                     114, 0xE9, 115, 117, 109, 0xE9, 10])           # "r" + more of the same

# INVENTED for the test, and it has to be: a selftest that carried a real forbidden phrase
# would put that phrase into a file copied into every project - which is the leak this
# check exists to prevent, committed inside the check itself.
INVENTED_PHRASE = "quicksilver kettle protocol"

SELFTEST_CFG = dict(DEFAULT_CONFIG, placeholder_markers=["TODO"], size_scope=["*.md"])


def writes(snippet, extra_file=None):
    """Builder: a document made of BASE plus a snippet. Returns its path."""
    def build(tmp):
        if extra_file:
            (tmp / extra_file).write_text("x", encoding="utf-8")
        q = tmp / "case.md"
        q.write_text(BASE + snippet, encoding="utf-8")
        return q
    return build


def checks(name):
    """Probe: run every check over the document and report one check's status."""
    def probe(path):
        rep = Report()
        verify_file(rep, path, SELFTEST_CFG)
        return rep.by_name().get(name)
    return probe


def checks_cfg(name, **over):
    """Like checks(), but for a check the DEFAULT config disables.

    max_lines and section_caps both default to 0/empty so that adding them changed no
    existing run. That makes them unprovable through the shared SELFTEST_CFG, and an
    unprovable check is the thing --selftest exists to refuse.
    """
    def probe(path):
        rep = Report()
        verify_file(rep, path, dict(SELFTEST_CFG, **over))
        return rep.by_name().get(name)
    return probe


def writes_body(count, comment_from=None):
    """A document of `count` body lines under section 1.

    With comment_from set, everything from that body line onward is wrapped in a
    block-level HTML comment - which Claude never receives, so it must not count.
    """
    def build(tmp):
        body = [f"Body line {i}." for i in range(count)]
        if comment_from is not None:
            body.insert(comment_from, "<!--")
            body.append("-->")
        q = tmp / "case.md"
        q.write_text("# Doc" + NL + NL + "## 1 - One" + NL + NL + NL.join(body) + NL,
                     encoding="utf-8")
        return q
    return build


def writes_sections(keys, per=2):
    """A document with one top-level numbered section per key, each `per` lines long."""
    def build(tmp):
        out = ["# Doc", ""]
        for k in keys:
            out += [f"## {k} - Section {k}", ""] + [f"Body {i}." for i in range(per)] + [""]
        q = tmp / "case.md"
        q.write_text(NL.join(out) + NL, encoding="utf-8")
        return q
    return build


def writes_scoped(count, globs):
    """A document of `count` body lines, paired with the size_scope to judge it under.

    The two arms of the report case differ ONLY in scope, so the builder has to carry it -
    a single probe cannot hold two configs, and using two probes would let the pair pass
    while comparing different things.
    """
    def build(tmp):
        return writes_body(count)(tmp), globs
    return build


def writes_body_under(count, max_lines):
    """A document of `count` body lines, paired with the max_lines map to judge it under.

    The per-glob arms differ only in the MAP, not in the document - so the builder has to
    carry it, exactly as writes_scoped does for size_scope. Two probes would let the pair
    pass while comparing two different things.
    """
    def build(tmp):
        return writes_body(count)(tmp), max_lines
    return build


def writes_row(length, commented=False):
    """A section-1 document holding a three-line table whose last row is `length` characters
    long - SEVEN physical lines however long that row is, which is the whole point.

    With commented set, the table sits inside a block-level HTML comment, which Claude never
    receives, so under either measure it must weigh nothing.
    """
    def build(tmp):
        row = "| " + "w" * max(1, length - 10) + " | row |"
        table = ["| a | b |", "| --- | --- |", row]
        if commented:
            table = ["<!--"] + table + ["-->"]
        q = tmp / "case.md"
        q.write_text("# Doc" + NL + NL + "## 1 - One" + NL + NL + NL.join(table) + NL,
                     encoding="utf-8")
        return q
    return build


def writes_row_under(length, measure):
    """writes_row paired with the line_measure to judge it under - the arms of the selector
    case differ ONLY in the measure, so the builder carries it, as writes_scoped does."""
    def build(tmp):
        return writes_row(length)(tmp), measure
    return build


# The charter fixtures - writes_charter, writes_plan, writes_subsections and the rest - and the
# three cross-check assertions MOVED TO verify_charter.py ON 2026-10-12 (v30), with the checks
# they prove. Its selftest still runs them through verify_file here, so they prove the whole
# path a project uses.


def checks_length_under(spec):
    """The file-length verdict for one document under one max_lines map."""
    path, max_lines = spec
    rep = Report()
    verify_file(rep, path, dict(SELFTEST_CFG, max_lines=max_lines))
    return rep.by_name().get(LENGTH)


def checks_length_measured(spec):
    """The file-length verdict for one document under one line_measure, cap 20."""
    path, measure = spec
    rep = Report()
    verify_file(rep, path, dict(SELFTEST_CFG, max_lines=20, line_measure=measure))
    return rep.by_name().get(LENGTH)


def report_shows_wrapped(spec):
    """Does the size breakdown print the wrapped weight beside the physical count, whichever
    measure gates? 'both' if it does. This is the REPORT-BOTH release's whole promise - a
    project sees what a switch would do before it switches."""
    path, measure = spec
    body, _ = read_doc(path)
    cfg = dict(SELFTEST_CFG, max_lines=20, section_caps={"1": 20}, line_measure=measure)
    out = NL.join(section_size_report(str(path), body, cfg))
    first, sec = out.splitlines()[0] if out else "", [ln for ln in out.splitlines()
                                                      if "section 1" in ln]
    row_weight = -(-16000 // WRAP_WIDTH)                  # the fixture's row, at the house width
    file_w, sec_w = 6 + row_weight, 4 + row_weight        # 6 and 4 other one-line lines
    return ("both" if (f"{file_w} wrapped" in first and sec and f"{sec_w} wrapped" in sec[0])
            else out[:200])


def report_agrees_with_check(spec):
    """Do the per-section REPORT and the file-length CHECK say the same thing about one file?

    Written because they did not. With a max_lines MAP, a glob declaring a cap of 0 is an
    exemption - the check said "exempt", while the report said "no glob matches" about the
    same file in the same run. Both are N/A, so no status differed and nothing failed; only
    the sentences disagreed, which is the shape a reader learns to stop reading.
    """
    path, max_lines = spec
    cfg = dict(SELFTEST_CFG, max_lines=max_lines)
    body, _ = read_doc(path)
    rep = Report()
    verify_file(rep, path, cfg)
    said = [" ".join(probs) for _, name, _, _, probs in rep.rows if name == LENGTH]
    if not said:
        return "the check said nothing"
    report = NL.join(section_size_report(str(path), body, cfg))
    if not report:
        return "no report"
    return "agree" if ("exempt" in said[0]) == ("exempt" in report) else "disagree"


def reports_verdict(spec):
    """Does the per-section breakdown pass a VERDICT on this file, or only report sizes?

    THIS IS THE CASE THAT WOULD HAVE CAUGHT THE CONTRADICTION. The old report annotated
    "cap N, OVER by M" for every capped section regardless of scope, while the check beside
    it reported N/A for the same file in the same run.
    """
    path, globs = spec
    body, _ = read_doc(path)
    cfg = dict(SELFTEST_CFG, section_caps={"1": 5}, size_scope=globs)
    out = NL.join(section_size_report(str(path), body, cfg))
    if not out:
        return "no sections"
    if "OVER by" in out:
        return "VERDICT"
    if "no cap applies" in out:
        return "sizes only"
    return "no verdict"


TABLES, HEADS = "tables well-formed", "heading numbering"
REFS, LINKS = "internal refs resolve", "file links resolve"
XDOC = "cross-doc refs"
MARKERS, DAMAGE = "no placeholders left", "no formatter damage"
LENGTH, SECT = "file length", "section length"
STATUS = "status words agree"
# The six charter row names are CHARTER_ROWS, at the top of this file.

#: A tracker whose table row and whose heading agree. The bad arms below change ONE word.
_TRACKER = (NL + "| # | item | status |" + NL + "| --- | --- | --- |" + NL
            + "| 4 | the monthly review | **DONE 2026-08-18** |" + NL)


def cases():
    """The case table. EVERY ROW IS PROVED BOTH WAYS unless it says why it cannot be.

    Before this, these were eleven mutations with no conforming twin - a shape that a
    check firing on EVERY input passes perfectly while proving nothing about its judgement.
    """
    return [
        Case("ragged table", checks(TABLES),
             writes("| a | b |" + NL + "|---|---|" + NL + "| 1 | 2 | 3 |" + NL),
             writes(GOOD_TABLE)),
        Case("table with no delimiter row", checks(TABLES),
             writes(NL + "| a | b |" + NL + "| | |" + NL + "| 1 | 2 |" + NL),
             writes(GOOD_TABLE)),
        # The first version of this pair used top-level headings and its bad case FAILED
        # for the wrong reason - a heading duplicating BASE's own section 1, not a gap.
        # The conforming twin is what exposed it, by failing too. A one-sided case would
        # have reported OK and proved nothing about the rule it names.
        Case("gap in subsection numbers", checks(HEADS),
             writes(NL + "### 1.1 A" + NL + NL + "### 1.3 C" + NL),
             writes(NL + "### 1.1 A" + NL + NL + "### 1.2 B" + NL)),
        Case("reference to a missing section", checks(REFS),
             writes(NL + "## 1. One" + NL + NL + "See " + SECTION_SIGN + "9.9 here." + NL),
             writes(NL + "## 1. One" + NL + NL + "See " + SECTION_SIGN + "1 here." + NL)),
        # The SAME missing reference, bare and then quoted. A document has to be able to
        # discuss a reference without being judged as making one.
        Case("a reference QUOTED in backticks is not a reference", checks(REFS),
             writes(NL + "## 1. One" + NL + NL + "See " + SECTION_SIGN + "9.9 here." + NL),
             writes(NL + "## 1. One" + NL + NL + "See " + SECTION_SIGN
                    + "1, and never write `" + SECTION_SIGN + "9.9` for another file." + NL)),
        # THE JUDGE CASE, and the good arm is the interesting half. A document naming
        # another .md is perfectly ordinary - this house's charter does it in thirty places.
        # What is unsettleable is naming one AND using a sign on the same line, so the twin
        # keeps the filename and drops the sign. Without that arm the check could be made to
        # pass by firing on every mention of a document, and every row of the document set
        # would be handed to a person forever.
        Case("cross-doc ref needs a person", checks(XDOC),
             writes(NL + "See PLAN-TEMPLATE.md " + SECTION_SIGN + "4 for the rule." + NL),
             writes(NL + "See PLAN-TEMPLATE.md rule 4 for the rule." + NL),
             want=JUDGE),
        Case("link to a file not on disk", checks(LINKS),
             writes(NL + "See [gone](no-such-file-here.md)." + NL),
             writes(NL + "See [here](there.md)." + NL, extra_file="there.md")),
        # THE FOUR REAL INSTANCES ALL READ THIS WAY ROUND - the table right, the heading
        # stale - so the bad arm is written that way round too rather than the tidier one.
        Case("heading contradicts its row", checks(STATUS),
             writes(_TRACKER + NL + "## Item 4 - the monthly review - NOT STARTED" + NL),
             writes(_TRACKER + NL + "## Item 4 - the monthly review - **DONE**" + NL)),
        # TWO WORDS FOR ONE STATE MUST NOT FIRE. Without this arm the check could be made
        # to pass by matching on the word rather than on what the word means, and every
        # tracker in the house would light up on its own vocabulary.
        Case("'closed' does not contradict 'done'", checks(STATUS),
             writes(_TRACKER + NL + "## Item 4 - the monthly review - OUTSTANDING" + NL),
             writes(_TRACKER + NL + "## Item 4 - the monthly review - **CLOSED**" + NL)),
        # A STATUS CELL THAT OPENS 'not started' AND GOES ON TO SAY 'partly done already'
        # is the shape that defeated the first version: an anywhere-match called the row
        # ambiguous and skipped the rows most worth reading.
        Case("commentary after the verdict does not confuse it", checks(STATUS),
             writes(NL + "| # | item | status |" + NL + "| --- | --- | --- |" + NL
                    + "| 6 | the table | not started. **Partly done already** |" + NL
                    + NL + "## Item 6 - the table - **DONE**" + NL),
             writes(NL + "| # | item | status |" + NL + "| --- | --- | --- |" + NL
                    + "| 6 | the table | not started. **Partly done already** |" + NL
                    + NL + "## Item 6 - the table - still OPEN" + NL)),
        # AN ORDINARY NUMBERED SECTION HEADING IS NOT A WORK ITEM. Without the leading
        # noun this check would match '## 3 - Plan of action' against any row holding a 3.
        Case("a plain section heading is not an item", checks(STATUS),
             writes(_TRACKER + NL + "## Item 4 - the monthly review - NOT STARTED" + NL),
             writes(_TRACKER + NL + "## 4 - Tech stack - nothing here is started" + NL),
             good_want=NA),
        Case("unfilled placeholder", checks(MARKERS),
             writes(NL + "TODO finish this." + NL),
             writes(NL + "This section is finished." + NL)),
        # each of these is a real thing VS Code's formatter did to CLAUDE-TEMPLATE.md, and
        # each is paired against the guard block, which documents the same shapes legitimately
        Case("escaped heading period", checks(DAMAGE),
             writes(NL + "## 2" + BACKSLASH + ". Escaped heading" + NL), writes(GUARDS)),
        Case("escaped square bracket", checks(DAMAGE),
             writes(NL + "An escaped " + BACKSLASH + "[" + BACKSLASH + "[FILL: marker}}." + NL),
             writes(GUARDS)),
        Case("emphasis inside a code span", checks(DAMAGE),
             writes(NL + "**bold into** `**a code span**` here." + NL), writes(GUARDS)),
        Case("trailing hard break", checks(DAMAGE),
             writes(NL + "A line with a trailing hard break  " + NL), writes(GUARDS)),
        Case("invisible NBSP in a cell", checks(DAMAGE),
             writes(NL + "| a |" + chr(0xA0) + "| a cell filled with NBSP |" + NL),
             writes(GUARDS)),
        # The size checks. Each is disabled by default, so each runs on its own config.
        Case("file over its line cap", checks_cfg(LENGTH, max_lines=10),
             writes_body(30), writes_body(3)),
        # PER-GLOB CAPS. The map form exists because one cap per project stopped being
        # enough: a 120-line plan file and a 350-line charter live in the same folder, and
        # until this the smaller was checked by a person reading a printed number.
        Case("a per-glob cap fires on the file its glob names",
             checks_cfg(LENGTH, max_lines={"case.md": 10}), writes_body(30), writes_body(3)),
        # The pair that proves the map SELECTS rather than applying one cap to everything:
        # the SAME 30-line document, under the same config, passing or failing only by which
        # glob matches it. A resolver that ignored the map would fail both arms.
        Case("the longest matching glob wins, not the first",
             checks_cfg(LENGTH, max_lines={"*.md": 10, "case*.md": 500}),
             writes_body(600), writes_body(30)),
        # BOTH ARMS ARE THE SAME 30-LINE DOCUMENT and differ only in the map, so a resolver
        # that always answered "no cap" would pass the first arm and fail the second.
        Case("a file no glob matches is N/A, never a silent pass", checks_length_under,
             writes_body_under(30, {"nothing-matches-this-*.md": 10}),
             writes_body_under(30, {"case.md": 10}), want=NA, good_want=FAIL),
        # The check and the report must say the SAME thing about one file. They did not:
        # "exempt" against "no glob matches", both N/A, so no status differed and nothing
        # failed - only the sentences disagreed. Proved on the config where it happened.
        Case("the report and the check agree about an exemption", report_agrees_with_check,
             writes_body_under(30, {"case.md": 0}), want="agree",
             unpaired_reason="this is a CONSISTENCY invariant, not a fire-on-bad check - "
                             "both arms would want 'agree', so a twin would prove nothing "
                             "the exempt path does not already prove"),
        # A wrong cap that PASSES is worse than no cap, so ambiguity is refused, not resolved.
        Case("two equal-length globs both matching is VOID, not a silent pick",
             checks_length_under,
             writes_body_under(30, {"cas?.md": 10, "ca*e.md": 500}),
             writes_body_under(30, {"cas?.md": 10, "case-other.md": 500}),
             want=VOID, good_want=FAIL),
        # THE CASE THAT PROVES THE COUNT IS OF WHAT LOADS. Both documents have the same
        # number of lines IN THE FILE; only the second puts most of them inside an HTML
        # comment, which is stripped before Claude sees it. A checker counting the file
        # would fail both, pass this table one-sidedly, and measure the wrong thing.
        Case("HTML comments do not count toward the cap", checks_cfg(LENGTH, max_lines=10),
             writes_body(30), writes_body(30, comment_from=3)),
        Case("section over its own cap", checks_cfg(SECT, section_caps={"1": 5}),
             writes_body(30), writes_body(2)),
        # A cap naming a section that is not there is a FINDING, not a silent pass - a
        # typed key must not quietly protect nothing.
        Case("capped section absent from the document", checks_cfg(SECT, section_caps={"2": 50}),
             writes_sections(["1"]), writes_sections(["1", "2"])),
        # THE REPORT MUST NOT CONTRADICT THE CHECK. Same document, same cap; only the scope
        # differs. In scope it earns a verdict, out of scope it reports sizes and says why -
        # because one run saying two things about one file teaches a reader to ignore both.
        Case("report passes no verdict out of scope", reports_verdict,
             writes_scoped(30, ["*.md"]), writes_scoped(30, ["nothing-matches-this"]),
             want="VERDICT", good_want="sizes only"),
        # THE SCOPE, proved both ways on ONE input: the same over-cap document FAILS when the
        # size rule is about it and reports N/A when it is not. Without this the checker
        # confidently failed two templates whose section 7 is a template FOR a section 7.
        Case("out of size_scope reports N/A, not a failure",
             checks_cfg(LENGTH, max_lines=10, size_scope=["nothing-matches-this"]),
             writes_body(30), writes_body(30), want=NA, good_want=NA),
        # THE LINE MEASURE (v31, 2026-10-14). A table row is ONE physical line however long,
        # so a 16,155-character row counted as one line in a real charter and both size caps
        # were blind to it. Under line_measure "wrapped" a line weighs its length / 120,
        # rounded up. THE FIXTURE IS THE DEFECT: one 16,000-character row, seven physical
        # lines, 140 wrapped ones, against a cap of 20.
        Case("a 16,000-char row weighs its length when the measure is wrapped",
             checks_cfg(LENGTH, max_lines=20, line_measure="wrapped"),
             writes_row(16000), writes_row(60)),
        # THE SELECTOR, proved on ONE document: the same row passes under physical lines and
        # fails under wrapped. A key that changed nothing would pass the first case's good arm
        # and fail here; a measure always wrapped would fail the physical arm.
        Case("the measure is the config key, not the document", checks_length_measured,
             writes_row_under(16000, "wrapped"), writes_row_under(16000, "physical")),
        Case("a section's long row weighs its length too",
             checks_cfg(SECT, section_caps={"1": 20}, line_measure="wrapped"),
             writes_row(16000), writes_row(60)),
        # What Claude never receives weighs nothing under either measure.
        Case("a long row inside an HTML comment weighs nothing",
             checks_cfg(LENGTH, max_lines=20, line_measure="wrapped"),
             writes_row(16000), writes_row(16000, commented=True)),
        Case("...and weighs nothing in its section either",
             checks_cfg(SECT, section_caps={"1": 20}, line_measure="wrapped"),
             writes_row(16000), writes_row(16000, commented=True)),
        # A MISTYPED MEASURE IS VOID, NEVER A SILENT DEFAULT: a config asking for something
        # this checker does not know would otherwise be gated on physical lines unannounced.
        Case("an unknown line_measure is VOID, not a silent default", checks_length_measured,
             writes_row_under(60, "characters"), writes_row_under(60, "wrapped"),
             want=VOID, good_want=PASS),
        Case("the size report prints the wrapped weight whichever measure gates",
             report_shows_wrapped, writes_row_under(16000, "physical"), want="both",
             unpaired_reason="a REPORTING promise, not a fire-on-bad check - every arm wants "
                             "'both'; the gating arms above prove the verdicts"),
        # THE CHARTER CASES - structure, the CORE floor, archetype, agreed out, pointers and
        # plan purpose - MOVED TO verify_charter.py's own table on 2026-10-12 (v30), row for
        # row, with the checks they prove.
    ]


def _repo(where: Path, committed: str, working: str = None, extra: str = None):
    """A real git repository: one document committed, then optionally edited.

    A REAL REPOSITORY, because a diff-scoped check cannot honestly be tested without one.
    Faking the diff would test the matcher against a string I wrote by hand and prove
    nothing about what git actually reports - and the hunk-header parsing is where this
    arm's line numbers come from.
    """
    where.mkdir(parents=True, exist_ok=True)
    doc = where / "fb.md"
    doc.write_text(committed, encoding="utf-8")
    (where / "other.md").write_text("# Other\n\n## 1 - One\n\nBody.\n", encoding="utf-8")
    for args in (("init", "-q"),
                 ("config", "user.email", "t@example.invalid"),
                 ("config", "user.name", "T"),
                 ("config", "commit.gpgsign", "false"),
                 ("add", "fb.md", "other.md"),
                 ("-c", "commit.gpgsign=false", "commit", "-q", "-m", "baseline")):
        git(where, *args)
    if working is not None:
        doc.write_text(working, encoding="utf-8")
    # 'extra' edits the OTHER file, which is how "this change touched the repository but
    # not THIS document" is built. Without a second file the run-level guard and the
    # per-file N/A cannot be told apart, because one file with no edit produces both.
    if extra is not None:
        (where / "other.md").write_text(extra, encoding="utf-8")
    return where


def selftest_added_lines(tmp: Path) -> bool:
    """The added-lines arm: BOTH rows read off ONE fixture, which is the whole claim.

    THE ACCEPTANCE CONDITION CANNOT BE A SINGLE STATUS, the same lesson B4 and B8 taught.
    It is not "the diff arm passes" - it is that the diff arm passes WHERE THE WHOLE-FILE
    ARM FAILS, on a pre-existing hit. Either row alone is satisfied by a check that reports
    the same thing for every input.
    """
    ok = True
    HEAD_LINES = "# Doc\n\n## 1 - One\n\n"
    inline = {"forbidden_phrases": [INVENTED_PHRASE]}

    def probe(label, want, cfg, committed, working, spec="HEAD", extra=None):
        nonlocal ok
        where = tmp / ("repo-" + re.sub(r"[^a-z0-9]+", "-", label.lower()))
        _repo(where, committed, working, extra)
        full = dict(DEFAULT_CONFIG, **cfg, diff_baseline=spec)
        rep = Report()
        verify_file(rep, where / "fb.md", full, resolve_forbidden(where, cfg), None,
                    resolve_baseline(where, full))
        by = rep.by_name()
        got = f"whole={by.get('forbidden phrases absent')},"\
              f"added={by.get('forbidden in added lines')}"
        good = got == want
        ok &= good
        print(f"  {'OK  ' if good else 'MISS'} {label:<34} -> {got}")
        return rep

    # THE PAIR THAT IS THE POINT. Same needle, same file, two verdicts: the phrase was
    # already committed, and this change added an innocent line beside it.
    probe("pre-existing hit is not THIS change", f"whole={FAIL},added={PASS}", inline,
          HEAD_LINES + f"The {INVENTED_PHRASE} was here already.\n",
          HEAD_LINES + f"The {INVENTED_PHRASE} was here already.\nA harmless new line.\n")

    # ...and the other direction: introduce it, and BOTH rows fail.
    rep = probe("a phrase introduced here fails both", f"whole={FAIL},added={FAIL}", inline,
                HEAD_LINES + "Nothing to see.\n",
                HEAD_LINES + f"Nothing to see.\nNow the {INVENTED_PHRASE} appears.\n")
    # AND THE REPORT STILL MUST NOT PRINT THE PHRASE - a new row is a new place to leak it.
    leaked = INVENTED_PHRASE in rep.render()
    ok &= not leaked
    print(f"  {'OK  ' if not leaked else 'MISS'} {'added row never prints phrase':<34} "
          f"-> leaked={leaked}")

    # A WRAP INSIDE THE ADDED LINES is still the phrase - the same matcher, so the same
    # tolerance. Without it, adding a hard-wrapped confidential phrase reads as clean.
    probe("wrapped phrase in added lines", f"whole={FAIL},added={FAIL}", inline,
          HEAD_LINES + "Nothing to see.\n",
          HEAD_LINES + "Nothing to see.\nkept under the quicksilver\nkettle protocol.\n")

    # THE TRAP THIS ARM EXISTS TO AVOID, and it must be VOID rather than a pass: the
    # baseline IS the working tree, so there are no added lines and nothing was examined.
    probe("baseline == working tree is VOID", f"whole={FAIL},added={VOID}", inline,
          HEAD_LINES + f"The {INVENTED_PHRASE} is committed.\n", None)

    # A file the change did not touch is N/A WITH ITS REASON - and it is only honest
    # because the run-level guard has already proved the baseline older. The change here
    # edits the OTHER file, so the repository differs while this document does not.
    probe("untouched file is N/A, not PASS", f"whole={PASS},added={NA}", inline,
          HEAD_LINES + "Clean.\n", HEAD_LINES + "Clean.\n",
          extra="# Other\n\n## 1 - One\n\nBody, edited.\n")

    # A BASELINE THAT DOES NOT RESOLVE IS VOID, NEVER N/A. Declared-and-unusable is an
    # accident; N/A reads as a decision somebody took.
    probe("unresolvable baseline is VOID", f"whole={PASS},added={VOID}", inline,
          HEAD_LINES + "Clean.\n", HEAD_LINES + "Clean.\nnew line.\n",
          spec="no-such-revision-anywhere")
    return ok


def selftest_forbidden(tmp: Path) -> bool:
    """The forbidden-list check: where the list may live, and what must never be printed."""
    ok = True

    def case(label, want, cfg, body):
        nonlocal ok
        p = tmp / "fb.md"
        p.write_text("# Doc\n\n## 1 - One\n\n" + body, encoding="utf-8")
        rep = Report()
        verify_file(rep, p, dict(DEFAULT_CONFIG, **cfg), resolve_forbidden(tmp, cfg))
        got = rep.by_name().get("forbidden phrases absent")
        good = got == want
        ok &= good
        print(f"  {'OK  ' if good else 'MISS'} {label:<28} -> {got}")
        return rep

    inline = {"forbidden_phrases": [INVENTED_PHRASE]}
    case("inline list catches it", FAIL, inline, f"It uses the {INVENTED_PHRASE} here.\n")

    # A3: hard-wrapped prose splits the phrase, and a line-by-line search reports CLEAN on
    # a document that plainly contains it - a confidentiality check saying nothing is there
    case("wrapped phrase caught", FAIL, inline,
         "It is maintained under the quicksilver\nkettle protocol and is restricted.\n")

    # the other half of the pair: one word of the phrase is not the phrase
    case("near miss NOT flagged", PASS, inline,
         "The quicksilver mirror is unrelated to any protocol.\n")

    listfile = tmp / "outside-the-repo.txt"
    listfile.write_text(f"# a comment, ignored\n\n{INVENTED_PHRASE}\n", encoding="utf-8")
    from_file = {"forbidden_phrases_file": str(listfile)}
    rep = case("list read from a file", FAIL, from_file, f"The {INVENTED_PHRASE} again.\n")

    # THE POINT OF MOVING THE LIST OUT: the report must not put it back. A phrase echoed
    # into a terminal or a CI log is published by a route no scanner can clean up after.
    rendered = rep.render()
    leaked = INVENTED_PHRASE in rendered
    ok &= not leaked
    print(f"  {'OK  ' if not leaked else 'MISS'} {'report never prints phrase':<28} "
          f"-> leaked={leaked}")

    prior = os.environ.get(FORBIDDEN_LIST_ENV)
    try:
        os.environ[FORBIDDEN_LIST_ENV] = str(listfile)
        case("environment variable wins", FAIL, {"forbidden_phrases_file": "nowhere.txt"},
             f"The {INVENTED_PHRASE} again.\n")
    finally:
        if prior is None:
            os.environ.pop(FORBIDDEN_LIST_ENV, None)
        else:
            os.environ[FORBIDDEN_LIST_ENV] = prior

    # A DECLARED LIST THAT IS NOT THERE MUST BE LOUD. This is the trap an external list
    # opens: the protection stops running on any machine without the file, and a check
    # that fell through to N/A or PASS would report success for exactly that reason.
    case("missing list is VOID", VOID, {"forbidden_phrases_file": "not-on-this-disk.txt"},
         f"The {INVENTED_PHRASE} is here and must still be noticed.\n")

    # exit codes: a defect you found outranks one you could not look for, and both block
    for label, statuses, want in (("FAIL outranks VOID", [FAIL, VOID], 1),
                                  ("VOID alone exits 2", [VOID, PASS], 2),
                                  ("all clear exits 0", [PASS, NA], 0)):
        rep = Report()
        for s in statuses:
            rep.add("doc", "x", s, 1, [])
        good = rep.exit_code == want
        ok &= good
        print(f"  {'OK  ' if good else 'MISS'} {label:<28} -> {rep.exit_code} (want {want})")
    return ok


REQUIRED_FACT = "every hop releases the lock as its last act"
# A SECOND, INVENTED string for the external-list arm. It must never be printed, so it has
# to be distinguishable from the inline one in the leak assertion - using one string for
# both arms would let a leak from the file arm hide behind a legitimate print from the
# inline arm, and the test would pass while the control was broken.
REQUIRED_SECRET = "the amber ledger reconciles nightly"


def selftest_required(tmp: Path) -> bool:
    """The required-string check: presence, wrapping, and which values may be printed."""
    ok = True

    def case(label, want, cfg, body):
        nonlocal ok
        p = tmp / "rq.md"
        p.write_text("# Doc\n\n## 1 - One\n\n" + body, encoding="utf-8")
        rep = Report()
        verify_file(rep, p, dict(DEFAULT_CONFIG, **cfg), None, resolve_required(tmp, cfg))
        got = rep.by_name().get("required strings present")
        good = got == want
        ok &= good
        print(f"  {'OK  ' if good else 'MISS'} {label:<32} -> {got}")
        return rep

    inline = {"required_strings": [REQUIRED_FACT]}

    # THE PAIR, both directions. A required check that fires on everything is passed
    # perfectly by a suite of absences alone, and proves nothing about its judgement.
    case("absent fact is caught", FAIL, inline,
         "This document says nothing about locks at all.\n")
    case("present fact stays quiet", PASS, inline,
         f"The rule is simple: {REQUIRED_FACT}, without exception.\n")

    # THE REPRODUCTION, KEPT IN THE SUITE. This is the case a naive line-by-line search
    # gets WRONG - it reports the fact missing from a document that states it, because the
    # document is hard-wrapped. Asserting the wrapped arm PASSES is only half of it; the
    # second assertion below proves the naive search really would have failed, so a later
    # refactor that quietly drops collapse() cannot leave this case still passing.
    wrapped = ("The rule is simple: every hop releases the lock\n"
               "as its last act, without exception.\n")
    case("wrapped fact still counts", PASS, inline, wrapped)
    naive_would_miss = not any(REQUIRED_FACT in ln for ln in wrapped.splitlines())
    ok &= naive_would_miss
    print(f"  {'OK  ' if naive_would_miss else 'MISS'} "
          f"{'naive search WOULD have missed it':<32} -> {naive_would_miss}")

    # the other half of near-miss: most of the phrase is not the phrase
    case("near miss counts as absent", FAIL, inline,
         "Every hop releases something, eventually, at some point.\n")

    listfile = tmp / "required-outside-the-repo.txt"
    listfile.write_text(f"# a comment, ignored\n\n{REQUIRED_SECRET}\n", encoding="utf-8")
    from_file = {"required_strings_file": str(listfile)}
    case("list read from a file", FAIL, from_file, "Nothing relevant here.\n")
    rep = case("file list satisfied", PASS, from_file,
               f"Note that {REQUIRED_SECRET} and has done for years.\n")

    # THE LEAK GUARD, on the FAILING arm - the one that prints problems. A list kept
    # outside the repository must not be put back by the report that reads it.
    rep = Report()
    p = tmp / "rq.md"
    p.write_text("# Doc\n\n## 1 - One\n\nNothing relevant here.\n", encoding="utf-8")
    verify_file(rep, p, dict(DEFAULT_CONFIG, **from_file), None,
                resolve_required(tmp, from_file))
    rendered = rep.render()
    leaked = REQUIRED_SECRET in rendered
    ok &= not leaked
    print(f"  {'OK  ' if not leaked else 'MISS'} {'external value never printed':<32} "
          f"-> leaked={leaked}")

    # AND THE OTHER HALF OF THAT RULE, asserted so nobody "tidies" it into silence: an
    # INLINE string is already committed, so the report names it. Without this the leak
    # guard above is satisfied most cheaply by printing nothing useful ever.
    rep = Report()
    verify_file(rep, p, dict(DEFAULT_CONFIG, **inline), None, resolve_required(tmp, inline))
    named = REQUIRED_FACT in rep.render()
    ok &= named
    print(f"  {'OK  ' if named else 'MISS'} {'inline value IS named':<32} -> {named}")

    prior = os.environ.get(REQUIRED_LIST_ENV)
    try:
        os.environ[REQUIRED_LIST_ENV] = str(listfile)
        case("environment variable wins", FAIL,
             {"required_strings_file": "nowhere.txt"}, "Nothing relevant here.\n")
    finally:
        if prior is None:
            os.environ.pop(REQUIRED_LIST_ENV, None)
        else:
            os.environ[REQUIRED_LIST_ENV] = prior

    # A2's RULE, WHICH IS THE WHOLE POINT OF THE ITEM. A declared list that is not on this
    # disk means the check did NOT run. Falling through to PASS would report success for
    # precisely the reason the control is absent - and the document below satisfies
    # nothing, so a PASS here would be doubly wrong.
    case("missing list is VOID", VOID,
         {"required_strings_file": "not-on-this-disk.txt"}, "Nothing relevant here.\n")

    # none declared is a DECISION, not an accident - N/A with its reason, never VOID
    case("none declared reports N/A", NA, {"required_strings": []}, "Anything.\n")
    return ok


def selftest(root: Path) -> int:
    """Hermetic since v24: the LIST ENV VARS ARE CLEARED FOR THE WHOLE SUITE.

    resolve_list() prefers the environment to the config, which is right for a real run and
    wrong here - a variable the CALLER set for a real scan replaces the fixture list a case
    just wrote, and the case measures the wrong list. Measured both ways: unset, exit 0; set
    to the house list, exit 1 on two rows - and BOTH in the direction where a guard stops
    guarding, so a one-sided suite would have gone green while testing nothing.

    A SAVE AROUND THE ONE CASE THAT SETS THE VARIABLE WAS NOT ENOUGH, and that is what this
    file already had: every other case ran on whatever the caller left behind. The two cases
    that deliberately set it keep their own save/restore, which still works inside this.
    """
    print("SELFTEST - each check must fire on a bad document AND stay quiet on a good one")
    print()
    cfg = SELFTEST_CFG
    tmp = Path(tempfile.mkdtemp(prefix="verify_md_selftest_"))
    with isolated_env(FORBIDDEN_LIST_ENV, REQUIRED_LIST_ENV):
        return _selftest_body(root, cfg, tmp)


def selftest_shape():
    """shape_of and section_shapes, and the THIRD case is the one that earns its keep.

    The sum control - four counts adding to the span - is necessary and NOT sufficient, and
    that is measured rather than asserted. section_shapes borrows its spans from the helper
    section_sizes uses, whose line numbers are ONE-BASED; sliced the obvious way it starts
    one line late and ends one line early, so every section's first line is the previous
    section's last. Planted here, that defect leaves the sum of every MIDDLE section exactly
    right - only the last section, where the slice runs off the end, moves at all. So on a
    charter of seven sections the sum control sees one and misses six, and it is the
    alignment case that catches every one: a section's first line must BE its heading.

    The classifier is proved on a fixture holding one of each kind plus a fenced block, so
    'fenced code counts as prose' is asserted rather than merely intended - and the sum
    catches any future kind that gets counted twice or not at all.
    """
    ok = True
    doc = ["# Title", "", "## 1 - one", "prose line", "| a | b |", "", "```", "# not a heading",
           "```", "", "## 2 - two", "more prose"]
    sh = shape_of(doc)
    cases = [("one of each kind is classified", (sh["heading"], sh["table"], sh["blank"]), (3, 1, 3)),
             ("fenced code counts as prose", sh["prose"], 5),
             ("every line counted exactly once", sum(sh.values()), len(doc))]
    sizes, shapes = section_sizes(doc), section_shapes(doc)
    cases.append(("shape sums to the section span",
                  [sum(shapes[k].values()) for k in sorted(shapes)],
                  [sizes[k] for k in sorted(sizes)]))
    # THE DISCRIMINATING ONE. A shape whose spans are off by one passes every case above.
    cases.append(("a section's shape starts at its heading",
                  shapes["2"], {"blank": 0, "heading": 1, "table": 0, "prose": 1}))
    # SHORT LINES, NO COMMENTS: the wrapped weight IS the physical count, section by section.
    # Section 1 here ends on a blank line, which a weight taken off the joined span dropped -
    # caught only by a real charter weighing LESS wrapped than physical (v31, 2026-10-14).
    cases.append(("short lines: wrapped section == physical",
                  section_wrapped_sizes(doc), sizes))
    for label, got, want in cases:
        good = got == want
        ok &= good
        print(f"  {'OK  ' if good else 'MISS'} {label:<28} -> {got} (want {want})")
    return ok


def selftest_charter_handoff(tmp: Path, cfg) -> bool:
    """THE HAND-OFF TO verify_charter.py, proved both ways off one document.

    Installed, the six charter rows come from there and none of them names a missing file.
    Missing, all six must FAIL and name it - never vanish, because six rows that stopped being
    printed read exactly like six that passed. The arms differ ONLY in whether the module is
    present, so the pair cannot pass while comparing two different documents.
    """
    global verify_charter
    saved, ok = verify_charter, True
    p = tmp / "handoff.md"
    p.write_text(BASE, encoding="utf-8")
    try:
        for label, mod, want_named in (("charter rows when installed", saved, 0),
                                       ("charter rows FAIL if missing", None, len(CHARTER_ROWS))):
            verify_charter = mod
            rep = Report()
            verify_file(rep, p, cfg)
            rows = [r for r in rep.rows if r[1] in CHARTER_ROWS]
            named = [r for r in rows if r[2] == FAIL and any("verify_charter.py is not installed"
                                                             in x for x in r[4])]
            good = len(rows) == len(CHARTER_ROWS) and len(named) == want_named
            ok &= good
            print(f"  {'OK  ' if good else 'MISS'} {label:<28} -> {len(rows)} rows, "
                  f"{len(named)} naming the missing file (want {want_named})")
    finally:
        verify_charter = saved
    return ok


def _selftest_body(root: Path, cfg, tmp: Path) -> int:
    """The suite itself. Split out ONLY so the env isolation can wrap it whole."""
    try:
        ok, paired, unpaired = run_cases(cases(), tmp, width=28)

        # Two cases the table cannot express, run here and declared rather than dropped.
        # An empty file has no non-empty version of itself, and a decodable file produces
        # NO ROW for the readability check at all - its absence is the pass, which is not
        # a status a paired case can compare against.
        p = tmp / "empty.md"
        p.write_text("", encoding="utf-8")
        rep = Report()
        check_placeholders(rep, str(p), [], ["TODO"])
        voided = rep.statuses()[0] == VOID
        ok &= voided
        print(f"  {'OK  ' if voided else 'MISS'} {'empty input reports VOID':<28} -> {rep.statuses()[0]}")
        print(f"       {'':<28}    unpaired: an empty file has no non-empty twin")

        p = tmp / "latin.md"
        p.write_bytes(UNDECODABLE)
        rep = Report()
        try:
            verify_file(rep, p, cfg)
            got = rep.statuses()[0] if rep.rows else "no rows"
        except Exception as e:                                   # noqa: BLE001
            got = f"CRASHED ({type(e).__name__})"
        good = got == FAIL
        ok &= good
        print(f"  {'OK  ' if good else 'MISS'} {'undecodable file fails cleanly':<28} -> {got}")
        print(f"       {'':<28}    unpaired: a decodable file produces no row at all")
        # The cross-document report, proved both ways. It is report-only and can never
        # FAIL, which is exactly why it needs this: its first version matched nothing at all
        # and printed a clean summary. A report that cannot be observed working is a report
        # nobody should believe.
        hits = list_cross_doc_refs(["See `OTHER-DOC.md` " + SECTION_SIGN + "5 for that."])
        miss = list_cross_doc_refs(["See " + SECTION_SIGN + "5 of this file."])
        for label, got, want in (("cross-doc line is listed", len(hits), 1),
                                 ("same-file line is not", len(miss), 0)):
            good = got == want
            ok &= good
            print(f"  {'OK  ' if good else 'MISS'} {label:<28} -> {got} (want {want})")

        report_pairing(paired, unpaired + 2)

        ok &= selftest_charter_handoff(tmp, cfg)
        ok &= selftest_shape()
        ok &= selftest_forbidden(tmp)
        ok &= selftest_added_lines(tmp)
        ok &= selftest_required(tmp)
        ok &= selftest_config(tmp, "md", "files", load_config, width=28)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print("\nSELFTEST: " + ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


# ------------------------------------------------------------------------------ main

def main(argv):
    """The entry point, and the machine-readable arm is applied HERE rather than inside.

    _main() below has SIXTEEN print sites and four early returns. Guarding each one, as the
    smaller checkers do, would mean sixteen chances to miss one - and a missed print in JSON
    mode is not a cosmetic fault: it puts prose on the stream a caller is parsing, and the
    parser fails on a run that is otherwise perfectly fine. Capturing the whole body instead
    is one decision in one place, and it cannot be partially applied.

    THE EXIT CODE STILL COMES FROM _main(), unchanged, including its early returns - so a
    JSON run and a bare run answer identically, which is the property a wrapper depends on.
    """
    quiet = wants_report_json(argv[1:])
    if not quiet:
        return _main(argv, {})
    held = {}
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = _main(argv, held)
    rep = held.get("rep")
    # No report means _main returned before building one - a bad config, an empty target
    # set. There is nothing to serialise, so the code is returned bare rather than an empty
    # rows list being emitted, which would read as "checked everything, found nothing".
    return finish(rep, "verify_md.py", rc, True) if rep is not None else rc


def _main(argv, held):
    root = Path.cwd()
    args = [a for a in argv[1:]]
    if "--write-config" in args:
        write_section(root, "md", DEFAULT_CONFIG, CONFIG_COMMENT)
        return 0
    if "--selftest" in args:
        return selftest(root)

    cfg = load_config(root)
    # --baseline REV OVERRIDES THE CONFIG, AND IT IS THE PRIMARY WAY IN. A baseline is a
    # property of the INVOCATION, not of the repository: the added-lines arm is a
    # pre-commit gate, and on a clean tree there is nothing for it to gate, so a config
    # default of 'origin/main' would make every routine run VOID the moment there is
    # nothing to commit. Left in the config for a project that genuinely always has a
    # baseline; the flag is what a person or a hook uses.
    if "--baseline" in args:
        at = args.index("--baseline")
        if at + 1 >= len(args):
            print("VOID: --baseline needs a revision. Nothing was checked.")
            return 2
        cfg = dict(cfg, diff_baseline=args[at + 1])
        del args[at:at + 2]
    named = [a for a in args if not a.startswith("-")]
    targets, empty_globs = expand_targets(root, named or cfg["files"])
    targets = [p for p in targets if p.exists()]

    if not targets:
        print("VOID: no documents to check. Name files, or list them under 'md.files' "
              "in verify.config.json. A run that checked nothing has not passed.")
        return 2

    # A GLOB THAT MATCHED NOTHING IS REPORTED, NEVER SWALLOWED. The whole reason globs exist
    # here is that a literal list silently omits the NEXT file of a kind; a glob that has
    # stopped matching would reintroduce exactly that, one level up.
    for g in empty_globs:
        print(f"VOID: the pattern {g!r} in 'md.files' matched no file. Either the pattern is "
              f"wrong or the documents it names are gone - both mean this run checked less "
              f"than it was configured to.")
    if empty_globs:
        return 2

    # resolved ONCE, not per document: a missing list is a fact about this run, and
    # re-reading it per file would report the same accident as many separate findings.
    forbidden = resolve_forbidden(root, cfg)
    required = resolve_required(root, cfg)
    baseline = resolve_baseline(root, cfg)

    before = {p: sha256(p.read_bytes()).hexdigest() for p in targets}
    rep = Report()
    held["rep"] = rep
    for p in targets:
        verify_file(rep, p, cfg, forbidden, required, baseline)

    print(rep.render(name_width=28))
    # THE RESOLVED SHA, PRINTED. 'origin/main' names a different commit tomorrow, so a
    # report quoting the spec cannot be re-run and one quoting the SHA can - which only
    # matters on the day somebody disputes a result, which is the day it matters most.
    if baseline[0]:
        print(f"\nADDED-LINE SCAN baseline: {baseline[0]} (from 'diff_baseline' = "
              f"{cfg['diff_baseline']!r})")

    if cfg["report_numeric_claims"]:
        print("\nNUMERIC CLAIMS - re-derive these by LISTING, never by adding to the old figure:")
        total = 0
        for p in targets:
            body, err = read_doc(p)
            if err:
                continue
            claims = list_numeric_claims(str(p), body.splitlines())
            for line, snippet in claims[:15]:
                print(f"  {p}:{line}  {snippet}")
            total += len(claims)
        print(f"  ({total} found; this is a reminder, never a failure)")

    # The cross-document-reference block that stood here until CHECKER VERSION 17 is gone,
    # not dropped: it is now a JUDGE row per document, inside the report. A paragraph under
    # a green verdict was unreachable to run_tests.py and skippable by a reader, which is
    # the whole reason the severity was built.

    if cfg["report_section_sizes"]:
        print("\nSECTION SIZES - lines as LOADED, so you can see WHERE the weight sits:")
        shown = 0
        for p in targets:
            body, err = read_doc(p)
            if err:
                continue
            report = section_size_report(str(p), body, cfg)
            if not report:
                continue
            shown += 1
            for ln in report:
                print(ln)
        if not shown:
            print("  (no document here uses numbered top-level sections)")
        print("  (a breakdown, never a failure - relocation is a judgement)")

    after = {p: sha256(p.read_bytes()).hexdigest() for p in targets}
    if before != after:
        print("\nVOID: a checked file changed during the run - the checker must be "
              "read-only, so this run's results cannot be trusted")
        return 2

    rc = rep.exit_code
    print(f"\n{len(targets)} document(s), {len(rep.rows)} checks")
    # rep.verdict(), NOT a private copy of the same table. This line held its own
    # {0: "PASS", 1: "FAIL", 2: "VOID"} dict until CHECKER VERSION 17 - a second copy of the
    # verdict renderer, which duly did not learn the fifth word when the shared one did.
    # That is the exact drift this module was extracted to end, surviving one line at a time.
    print("OVERALL: " + rep.verdict())
    mark = rep.judge_line()
    if mark:
        print(mark)
    return rc


if __name__ == "__main__":
    sys.exit(main(sys.argv))
