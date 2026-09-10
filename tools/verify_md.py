#!/usr/bin/env python3
"""verify_md.py - the document checker.  CHECKER VERSION 27 (2026-09-10)

If a project's copy says a lower version than this one, it is stale - see the "Checkers"
line for each version in ...\\Coding\\templates\\TEMPLATE-CHANGELOG.md and re-copy.

Checks Markdown deliverables: CLAUDE.md, plan documents, registers, READMEs, research
write-ups, guided-build playbooks. Standard library only, so it runs anywhere.

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
    FAIL, JUDGE, NA, PASS, RC_COULD_NOT_RUN, VOID, Case, Report,
    added_line_runs, baseline_guard, finish, git, isolated_env, load_section,
    loaded_lines, read_phrase_list, report_pairing, resolve_list, resolve_revision,
    run_cases, selftest_config, wants_report_json, write_section,
)

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
    "charter_structure": {},
    "archetype_absent": None,
    "core_sections": {},
    "sections_agreed_out": {},
    "pointers": {},
    "size_scope": ["CLAUDE.md", "*/CLAUDE.md"],
    "plan_scope": [],
    "report_section_sizes": True,
}

#: THE TEMPLATE'S OWN SUBSECTION COUNTS, section 1 to 7, and they live HERE rather than in
#: config for a measured reason: CLAUDE-TEMPLATE.md is copied into NO project. Every
#: propagated project holds a charter GENERATED FROM the template, never the template - so a
#: check that read the file at run time would work only in the house repository, which is the
#: one place the answer does not matter. The checker is the one artefact that actually
#: travels, and check_checkers.py already reports when a copy falls behind, so a stale
#: constant is visible as a VERSION difference instead of being silent.
#:
#: Sections 4 and 7 carry no numbered subsections at all. Section 7's headings are unnumbered
#: BY DESIGN - it is replaced every session, and a number there would be a stable identifier
#: for something that is deliberately not stable.
TEMPLATE_SUBSECTIONS = {1: 7, 2: 5, 3: 2, 4: 0, 5: 8, 6: 5, 7: 0}

#: THE FLOOR, and it is the half TEMPLATE_SUBSECTIONS could never see. That map is a CEILING -
#: never MORE subsections than the template. Nothing checked that a CORE one was PRESENT, so
#: the one instrument pointed at charter shape could only see EXCESS, and a charter missing
#: 5.4 (TEST) passed it perfectly. Measured 2026-09-10 across all six house charters: THREE
#: are missing at least one, INCLUDING THE HOUSE REPOSITORY'S OWN.
#:
#: LISTED from CLAUDE-TEMPLATE.md's tier table rather than counted - the tier table marks
#: these fourteen rows CORE, which it defines as "in every charter, however small the project.
#: Never negotiated away". A DEFAULT or OPTIONAL row is deliberately absent: a missing 1.4 or
#: 5.6 is a decision, and only CORE is never a decision.
#:
#: It lives here for the same reason TEMPLATE_SUBSECTIONS does, and the reason is not
#: convenience: CLAUDE-TEMPLATE.md is copied into NO project, so a check that read the file at
#: run time would work only in the house repository - the one place the answer does not
#: matter. A stale constant surfaces as a VERSION difference, which check_checkers.py reports.
TEMPLATE_CORE = ("1.1", "1.2", "1.3", "1.5", "2.1", "2.2", "3", "4",
                 "5.1", "5.3", "5.4", "5.8", "6", "7")

#: DEVICE 4 - the NEGOTIABLE subsections: everything the tier table marks DEFAULT, OPTIONAL or
#: mixed. These are exactly the rows Round 0.5 walks one at a time with its trigger question,
#: and therefore exactly the rows a project may legitimately leave out.
#:
#: THE SET IS THE COMPLEMENT OF TEMPLATE_CORE, and stating it separately rather than deriving
#: it is deliberate: sections 5.2 and 5.7 are MIXED - part CORE, part not - so a derived
#: complement would either admit them wrongly or exclude them wrongly, and the tier table is
#: the authority on which. Listed, not computed.
TEMPLATE_NEGOTIABLE = ("1.4", "1.6", "2.3", "2.4", "2.5", "3.1", "3.2",
                       "5.2", "5.5", "5.6", "5.7")

#: DEVICE 3 - the eleven archetypes, row for row from CLAUDE-TEMPLATE.md's archetype-defaults
#: table. Round 0.2's list and that table MUST match row for row; the template says so in
#: terms, having once offered nine against eleven for five days.
#:
#: WHY A LABELLED DECLARATION AND NOT A PHRASE SEARCH, and it was measured both ways before
#: this check was written. Searching for these NAMES in a charter returns FALSE POSITIVES from
#: ordinary prose - two house charters "name" *Claude skill* in passing while declaring
#: nothing. Searching for the WORD *archetype* passes a charter whose only hit is a sentence
#: about emit sizes. Only a LABELLED declaration tells a decision from a mention, which is why
#: the check asks for one shape and the template emits that shape.
ARCHETYPES = (
    "Claude skill",
    "Word / Excel add-in",
    "JavaScript / web",
    "API tool / library",
    "Guided build / playbook",
    "Research / analysis",
    "Docs / Markdown only",
    "Analysis + rebuild of an existing artefact",
    "Automation 1 - file and data",
    "Automation 2 - workflow orchestration",
    "Automation 3 - autonomous agent",
)

#: The declaration the charter must carry, in section 1.7 beside the size class (Wouter,
#: 2026-09-10). Bold, colon, then one of the eleven. The name is matched with punctuation and
#: case folded away, so an em dash, a slash or a stray article does not turn a correct
#: declaration into a failure - the check is about WHETHER the decision was recorded, never
#: about typography.
ARCHETYPE_LABEL = re.compile(r"ARCHETYPE\s*[:—-]\s*(.+)", re.I)

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
    "max_lines": "0 disables. Either ONE number for every file in size_scope, or a MAP of glob to cap - {\"CLAUDE.md\": 350, \"PLAN-*.md\": 120} - when a project has documents of different size classes. With a map, the LONGEST matching glob wins, a file matching none reports N/A, and two globs of the same length both matching is VOID rather than a silent pick. TWO SIZE CLASSES: M 200 (1-8 sessions, the default) and L 350 (more than 8, a declared exemption). Class S was retired 2026-08-21 because a minimal FILLED charter measures ~200; 120 survives only as the PLAN-*.md cap, which is a different document. Counts what LOADS, not what is in the file - block-level HTML comments are stripped before Claude receives them. Over the cap means RELOCATE, never delete.",
    "size_scope": "Which files the size checks apply to, as filename globs. A cap is a property of a CHARTER - a README has no size class, and a *-TEMPLATE.md contains a template FOR a section and is legitimately long. Anything outside this list reports N/A with that reason.",
    "archetype_absent": "DEVICE 3's declaration slot. Section 1.7 must NAME one of CLAUDE-TEMPLATE.md's eleven archetypes, because every optional-block lookup in the archetype table (11 rows x 10 columns at in/ask/out) starts by knowing which row this project is - a charter recording none makes the whole table unreadable, which is how a reduction came to be planned on 'these blocks are OPTIONAL, so they can be dropped' when the archetype's own row marked every one of them IN. Set this to a REASON STRING only for a project that genuinely fits none of the eleven; a blank reason is REFUSED, and a declaration standing over a charter that DOES name one FAILS as stale. It asks for a LABELLED line and not a phrase search, and that was measured both ways over six charters: searching for the eleven NAMES returns false positives from ordinary prose, and searching for the word 'archetype' passes a charter whose only hit is a sentence about emitted line counts - two naive needles answering wrongly in OPPOSITE directions. Punctuation and case are folded, so an em dash or a stray article never fails you.",
    "core_sections": "DEVICE 1's FLOOR - a map of CORE subsection -> reason, for a CORE subsection that genuinely cannot be written. Empty is the normal state. The check asserts every one of the tier table's fourteen CORE rows is PRESENT, which is the OPPOSITE question from 'charter structure': that one is a CEILING (never MORE than the template) and a subset is exactly what MAPPING produces, so it can never see an absence. Measured 2026-09-10 over six house charters: THREE were missing at least one CORE subsection including the house repository's own, and one was missing 5.4 - TEST - in a project already closed as fully propagated. ONLY CORE IS CHECKED, and that is the discriminator: a missing DEFAULT or OPTIONAL subsection is a decision Round 0.5 took, while CORE is 'never negotiated away' in the tier table's own words. So the honest remedy is almost always to WRITE the subsection. Blank reason REFUSED; a declaration for a subsection that IS present FAILS as stale.",
    "plan_scope": "Which files the 'plan purpose' check applies to, as filename globs - the LIVE plan file(s), and nothing else. EMPTY BY DEFAULT, reporting N/A with that reason rather than passing silently. IT IS DECLARED AND NOT INFERRED, on a measurement: of 15 plan files in the house repository the 14 CLOSED ones never used strikethrough - they recorded completion in a 'status' COLUMN - so 44 finished rows read as OPEN and a 'every PLAN-*.md' default reddens twelve finished records. And the next discriminator that suggests itself is worse: the LIVE file's status row contains the word CLOSED (naming which steps are), so prose-matching it marks the one live plan finished and the check passes over the very file it exists to read. Name the live plan file here; updating this glob is the same act as renaming the file when the phase turns over. A CLOSED plan file is left out - it is a finished record, and rewriting one to satisfy a convention it predates destroys evidence.",
    "section_caps": "Per-section caps, e.g. {\"7\": 60}, keyed by top-level section number. A capped section that is ABSENT is a finding, not a silent pass. Empty = do not check.",
    "report_section_sizes": "List each top-level section's loaded line count, so you can see WHERE the weight sits. Never fails.",
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

HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*$")
NUMBERED_RE = re.compile(r"^(\d+)(?:\.(\d+))?[.)]?\s+(.*)$")
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


def headings(lines):
    """Yield (lineno, level, text, number_key_or_None)."""
    in_fence = False
    for i, ln in enumerate(lines, 1):
        if ln.lstrip().startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        m = HEADING_RE.match(ln)
        if not m:
            continue
        text = m.group(2)
        nm = NUMBERED_RE.match(text)
        key = None
        if nm:
            key = nm.group(1) if nm.group(2) is None else f"{nm.group(1)}.{nm.group(2)}"
        yield i, len(m.group(1)), text, key


def code_fence_mask(lines):
    """True for lines inside a fenced code block - those are examples, not prose."""
    mask, in_fence = [], False
    for ln in lines:
        if ln.lstrip().startswith("```"):
            in_fence = not in_fence
            mask.append(True)
        else:
            mask.append(in_fence)
    return mask


# ---------------------------------------------------------------------------- checks

# An ESCAPED pipe is a literal '|' inside a cell, not a column separator. Splitting on
# every '|' makes a valid table look ragged - a false alarm on correct markdown, which is
# how a check stops being believed.
CELL_PIPE = re.compile(r"(?<!\\)\|")
# A delimiter row must contain at least one hyphen. Without that, '| | |' - a legitimate
# header row of empty cells - passes as a divider, and a table with no divider at all
# renders as one run-on line while this check calls it well-formed.
DELIM_RE = re.compile(r"^\s*\|[\s:|-]*-[\s:|-]*\|\s*$")


def row_cells(row: str):
    """The cells of a table row, splitting on UNESCAPED pipes only.

    The leading and trailing empty fragments are the table's outer borders, not cells.

    EXTRACTED 2026-09-10 so that cell_count and check_plan_purpose share ONE parser. Two
    splitters for one syntax is how the two come to disagree about an escaped pipe, and the
    disagreement would show up as a check that silently reads the wrong column.
    """
    parts = CELL_PIPE.split(row.strip())
    if parts and parts[0] == "":
        parts = parts[1:]
    if parts and parts[-1] == "":
        parts = parts[:-1]
    return [p.strip() for p in parts]


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
INLINE_CODE = re.compile(r"`[^`\n]*`")


def strip_inline_code(line):
    """Blank out inline code spans before scanning prose.

    A document that DOCUMENTS these constructs shows them inside backticks - and that is a
    quotation, not damage. Without this, a file explaining what formatter damage looks like
    is flagged as damaged: the scanner matching itself, which is how a check stops being
    believed. Whole fenced blocks are already excluded by the caller's mask.
    """
    return INLINE_CODE.sub(lambda m: " " * len(m.group(0)), line)


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


def collapse(lines, numbers=None):
    """Whole document as one whitespace-collapsed string, plus a line number per character.

    'numbers' supplies the real line number of each entry, for a caller handing over a
    SUBSET of a file - the added-lines arm does. One matcher for both arms rather than a
    second copy: the wrap-tolerant matching below is the whole reason this function exists,
    and a diff-scoped copy of it is where the two would quietly stop agreeing.

    A hard-wrapped document breaks a phrase across a line ending, and a line-by-line
    search then reports CLEAN on a document that plainly contains it. That is the worst
    direction for this check to be wrong in: a confidentiality scan saying nothing is
    there. Collapsing first means the wrap cannot hide anything.

    THE ACCEPTED COST, stated rather than discovered later: this also matches across a
    paragraph break, so two unrelated sentences can join into a phrase that was never
    written. For a FORBIDDEN list that is the right way to be wrong - a false alarm costs
    a minute of reading, and a missed confidential phrase cannot be recalled once shipped.
    """
    out, where, prev_space = [], [], True
    for idx, ln in enumerate(lines):
        i = numbers[idx] if numbers else idx + 1
        for ch in ln:
            if ch.isspace():
                if not prev_space:
                    out.append(" ")
                    where.append(i)
                prev_space = True
            else:
                out.append(ch)
                where.append(i)
                prev_space = False
        if not prev_space:          # the line ending is whitespace too
            out.append(" ")
            where.append(i)
            prev_space = True
    return "".join(out).lower(), where


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
        out[key] = end - i
    return out


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


def check_file_length(rep, doc, text, limit, in_scope=True, path=None):
    """THE ONE DEFECT WITH NO ERROR MESSAGE. A charter over its cap is never truncated - it
    is loaded in full and simply followed less well, so nothing ever tells you it happened
    and you cannot tell the result from a session that was going badly anyway. Which is why
    it needs a check rather than a habit.

    Over the cap means RELOCATE, not delete. Length is not the defect; content that is not
    needed in every session being loaded in every session is the defect.
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
    got = loaded_lines(text)
    over = []
    if got > cap:
        via = f" (via {glob!r})" if glob else ""
        over.append(f"{got} lines loaded against a cap of {cap}{via} - {got - cap} over. "
                    f"RELOCATE, do not delete: a path-scoped rule, a companion document, "
                    f"a plan document, or a hook")
    rep.record(doc, "file length", got, over)


def check_section_caps(rep, doc, lines, caps, in_scope=True):
    """A cap on ONE section, because the section that is replaced every session bloats
    fastest and a whole-file cap hides that inside a number that looks fine.

    A capped section that is ABSENT is a finding rather than a silent pass - but only in a
    document that uses numbered sections at all, or every README in the run would fail for
    not having a section 7.
    """
    if not caps:
        rep.record(doc, "section length", 0, [], na_reason="section_caps is empty (disabled)")
        return
    if not in_scope:
        rep.record(doc, "section length", 0, [], na_reason="not in size_scope - a cap is a charter's")
        return
    sizes = section_sizes(lines)
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
            problems.append(f"section {key}: {sizes[key]} lines against a cap of {cap} "
                            f"- {sizes[key] - cap} over")
    rep.record(doc, "section length", len(caps), problems)


def check_charter_structure(rep, doc, lines, declared, in_scope=True):
    """A charter's section N may have FEWER subsections than the template's, NEVER MORE.

    A SUBSET IS MAPPING. A project takes the subsections of a house section it actually
    needs, which is why one charter legitimately carries 3 where the template carries 8.
    MORE is the opposite act: the section grew its own structure instead of being mapped
    onto one, and nothing in this house could see it.

    WHY THE GAPLESS CHECK CONFIRMS THE DEFECT INSTEAD OF CATCHING IT. check_headings
    requires subsections to run 1..n with no gaps, and '1..16' satisfies that perfectly. So
    the one instrument pointed at subsection numbering reports PASS over the exact shape
    this check exists to find - measured on two charters at sixteen and fourteen against
    eight, both of which had answered "already house-shaped, so the work is numbering, not
    mapping" and been believed.

    AN EXCESS IS DECLARED, NEVER SILENTLY TOLERATED, and the declaration is held to the same
    two rules a declared checker absence is: a BLANK reason is REFUSED, because a command
    line cannot carry a reason and the reason is the whole distinction between a decision and
    an oversight; and a declaration for a section that is NOT in excess FAILS as stale, so
    the config cannot outlive its own facts.
    """
    if not in_scope:
        rep.record(doc, "charter structure", 0, [],
                   na_reason="not in size_scope - a charter's structure is a charter's")
        return
    numbered = [k for _, _, _, k in headings(lines) if k]
    if not numbered:
        rep.record(doc, "charter structure", 0, [],
                   na_reason="document uses no numbered headings")
        return
    got = {}
    for key in numbered:
        top, _, sub = key.partition(".")
        try:
            n = int(top)
        except ValueError:
            continue
        got.setdefault(n, set())
        if sub:
            try:
                got[n].add(int(sub))
            except ValueError:
                pass
    declared = {str(k): v for k, v in (declared or {}).items()}
    problems, examined = [], 0
    for n in sorted(TEMPLATE_SUBSECTIONS):
        if n not in got:
            # A section the charter does not have is not an excess. A MISSING section is
            # check_required_sections' subject, and two checks failing on one fact is how a
            # reader learns to stop reading one of them.
            if str(n) in declared:
                problems.append(
                    f"section {n} has a declared excess and no heading here - stale")
            continue
        examined += 1
        have, cap = len(got[n]), TEMPLATE_SUBSECTIONS[n]
        if have > cap:
            reason = declared.get(str(n))
            if str(n) not in declared:
                problems.append(
                    f"section {n}: {have} subsections against the template's {cap} "
                    f"- {have - cap} more. A SUBSET is mapping; an EXCESS means the section "
                    f"grew its own structure instead of mapping onto one. Map it, or declare "
                    f"it in md.charter_structure with a reason")
            elif not str(reason).strip():
                problems.append(
                    f"section {n}: excess declared with a BLANK reason - REFUSED. The reason "
                    f"is the whole distinction between a decision and an oversight")
        elif str(n) in declared:
            problems.append(
                f"section {n}: excess declared, but {have} subsections against the "
                f"template's {cap} is not an excess - the declaration is stale")
    rep.record(doc, "charter structure", examined, problems)


def _fold(s: str) -> str:
    """Punctuation and case folded away, so an em dash and a hyphen are one name.

    The check is about whether a DECISION was recorded, never about typography. A charter
    that writes 'Automation 1 — file and data' has named the archetype exactly as well as one
    writing 'Automation 1 - file and data', and a check that told them apart would be
    teaching people to copy a dash rather than to make a choice.
    """
    return re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).strip()


def check_charter_archetype(rep, doc, lines, declared, in_scope=True):
    """DEVICE 3. Does the charter NAME one of the template's eleven archetypes?

    IT IS THE CHEAPEST OF THE FIVE DEVICES AND IT UNLOCKS THE OTHER TWO. The archetype table
    is 11 rows x 10 optional-block columns at (in) / (ask) / (out); EVERY ONE of those lookups
    starts by knowing which row this project is. A charter that records no archetype makes the
    whole table unreadable, so this arm lands before the ones that depend on it.

    WHAT IT ASKS FOR IS A LABELLED DECLARATION, AND THE ALTERNATIVE WAS MEASURED. Searching a
    charter for the eleven NAMES returns false positives from ordinary prose - two house
    charters mention *Claude skill* while being neither. Searching for the WORD *archetype*
    passes a charter whose only occurrence is a sentence about emitted line counts. Both naive
    needles answer wrongly, in OPPOSITE directions, over the same six documents. So the check
    asks for one shape, the template emits that shape, and new_charter.py fills it from the
    flag it was already given.

    THE ROOT CAUSE THIS ARM EXISTS FOR SITS IN THE GENERATOR, NOT IN THE CHARTERS.
    new_charter.py REQUIRES --archetype, uses it to pre-select the optional blocks that
    archetype needs, and until 2026-09-10 never wrote it into the charter it emitted - so
    every generated charter recorded none, and the single house charter that did record one
    had it added by hand. A device only the generator consumes leaves no trace; here the
    generator did not even leave the trace it was handed.

    A DECLARED ABSENCE carries its reason, and the reason is the whole distinction between a
    decision and an oversight. A declaration standing over a charter that DOES name its
    archetype fails as stale, so the config cannot outlive its own facts.
    """
    if not in_scope:
        rep.record(doc, "charter archetype", 0, [],
                   na_reason="not in size_scope - an archetype is a charter's")
        return
    named, unknown = None, None
    for raw in lines:
        m = ARCHETYPE_LABEL.search(strip_inline_code(raw))
        if not m:
            continue
        # The rest of the line may carry bold markers, a parenthetical attribution or an
        # article. Fold it and ask whether any of the eleven names is IN it, longest first so
        # 'Automation 1 - file and data' is not shadowed by a shorter neighbour.
        tail = _fold(m.group(1))
        for a in sorted(ARCHETYPES, key=len, reverse=True):
            if _fold(a) in tail:
                named = a
                break
        if named:
            break
        unknown = m.group(1).strip()[:60]
    reason = (declared or "") if isinstance(declared, str) else ""
    problems = []
    if named and str(reason).strip():
        problems.append(
            f"an absent archetype is declared, but the charter names '{named}' "
            f"- the declaration is stale")
    elif not named:
        if declared is None or declared == "":
            near = f" The line found reads '{unknown}'." if unknown else ""
            problems.append(
                "no archetype declared. Section 1.7 must carry a line naming ONE of the "
                "template's eleven archetypes, e.g. '**ARCHETYPE: Research / analysis**' - "
                "every optional-block lookup in the archetype table starts from it." + near)
        elif not str(reason).strip():
            problems.append(
                "an absent archetype is declared with a BLANK reason - REFUSED. The reason "
                "is the whole distinction between a decision and an oversight")
    rep.record(doc, "charter archetype", 1, problems)


def check_core_sections(rep, doc, lines, declared, in_scope=True):
    """DEVICE 1's FLOOR. Is every CORE subsection PRESENT?

    THE HALF charter structure COULD NEVER SEE. That check is a CEILING - never MORE
    subsections than the template - and a subset is legitimate, being what MAPPING produces.
    So nothing in this house asked the opposite question, and a charter missing 5.4 (TEST)
    passed every structural check it had. Measured 2026-09-10 over all six house charters:
    three are missing at least one CORE subsection, THE HOUSE REPOSITORY'S OWN INCLUDED.

    ONLY CORE IS CHECKED, AND THAT IS THE WHOLE DISCRIMINATOR. The tier table defines CORE as
    'in every charter, however small the project. Never negotiated away'. A missing DEFAULT or
    OPTIONAL subsection is a decision Round 0.5 took; a missing CORE one is not a decision
    anybody is allowed to take, which is why this arm can fail on absence where no other can.

    IT CANNOT REDDEN A NEW PROJECT, and that was measured before it was built: a charter
    emitted by new_charter.py carries every CORE heading, 1.5 included. The defect is confined
    to hand-maintained charters, which is the difference between a check that gets used and
    one somebody switches off.

    A GENUINELY IMPOSSIBLE CORE SUBSECTION IS DECLARED WITH ITS REASON - blank REFUSED, and a
    declaration for a subsection that is present FAILS as stale. But the tier table's own
    wording means the honest answer is almost always to WRITE the subsection.
    """
    if not in_scope:
        rep.record(doc, "core sections present", 0, [],
                   na_reason="not in size_scope - a CORE floor is a charter's")
        return
    keys = {k for _, _, _, k in headings(lines) if k}
    if not keys:
        rep.record(doc, "core sections present", 0, [],
                   na_reason="document uses no numbered headings")
        return
    declared = {str(k): v for k, v in (declared or {}).items()}
    problems, examined = [], 0
    for key in TEMPLATE_CORE:
        examined += 1
        present = key in keys
        if not present and key not in declared:
            problems.append(
                f"CORE subsection {key} is MISSING. The tier table marks it CORE - 'in every "
                f"charter, however small the project. Never negotiated away'. Write it, or "
                f"declare it in md.core_sections with a reason")
        elif not present and not str(declared[key]).strip():
            problems.append(
                f"CORE subsection {key} is absent and declared with a BLANK reason - REFUSED. "
                f"The reason is the whole distinction between a decision and an oversight")
        elif present and key in declared:
            problems.append(
                f"CORE subsection {key} is declared absent, but the charter has it "
                f"- the declaration is stale")
    rep.record(doc, "core sections present", examined, problems)


def _section_body(lines, key):
    """The lines of one section or subsection, its heading included, or None if absent.

    Spans to the next heading of the SAME OR HIGHER level, the same rule section_sizes uses -
    never to the next heading of ANY level, which measures the gap to the first subsection
    rather than the section.
    """
    # headings() reports ONE-BASED line numbers, which is what the report prints. Slicing
    # with them directly starts a line late and swallows the NEXT section's heading - caught
    # here because the good arm of every pointer case failed while the bad arm passed.
    hs = [(i - 1, lvl, k) for i, lvl, _, k in headings(lines)]
    for at, (i, lvl, k) in enumerate(hs):
        if k != key:
            continue
        end = len(lines)
        for j, lvl2, _ in hs[at + 1:]:
            if lvl2 <= lvl:
                end = j
                break
        return lines[i:end]
    return None


def check_pointers(rep, doc, lines, pointers, in_scope=True):
    """DEVICE 5. Every relocation leaves a POINTER, and the pointer is still there.

    THE HOUSE RULE IS 'EVERY RELOCATION LEAVES A ONE-LINE POINTER BEHIND', and its reason is
    that a rule which simply VANISHES is indistinguishable from a rule that was REPEALED.
    Nothing checked it. A relocation is invisible to every other arm here: the charter gets
    shorter, which is what a relocation is supposed to look like, and so does a deletion.

    IT IS DECLARED, NOT INFERRED, AND THAT WAS MEASURED. The obvious alternative - detect
    relocation CLAIMS in prose and require a destination near each - was built and measured
    over the six house charters before this arm was written: 33 claims, 6 flagged, and at
    least FOUR of the six were false positives. Three came from HARD WRAPPING, the claim and
    its destination landing three lines apart; one from a destination that is a config key
    rather than a .md file. A needle with that error rate reddens three charters on bad
    grounds, which is precisely how this house has twice lost a control.

    So the project names what moved and what must still be findable, and the arm asserts the
    RETURN PATH survives - the same question verify_charter_continuity's check 5 asks for one
    project, generalised. A phrase that stops appearing in its section is a pointer that has
    gone, reported by name.

    EMPTY IS N/A WITH ITS REASON, never a silent pass: a project that has relocated nothing
    has nothing to assert, and a project that has relocated something and declared nothing
    should see a row saying so rather than a row saying PASS.
    """
    if not in_scope:
        rep.record(doc, "relocation pointers", 0, [],
                   na_reason="not in size_scope - a relocation pointer is a charter's")
        return
    pointers = {str(k): v for k, v in (pointers or {}).items()}
    if not pointers:
        rep.record(doc, "relocation pointers", 0, [],
                   na_reason="md.pointers is empty (disabled) - name each relocated block's "
                             "section and the phrase its pointer must still carry. A "
                             "relocation and a deletion look identical from here otherwise")
        return
    problems, examined = [], 0
    for key in sorted(pointers):
        phrases = pointers[key]
        if isinstance(phrases, str):
            phrases = [phrases]
        body = _section_body(lines, key)
        if body is None:
            examined += len(phrases)
            problems.append(
                f"section {key} is declared to carry a pointer and has no heading here at "
                f"all - the return path a pointer resolves against is GONE, which is the "
                f"one shape this check exists to catch")
            continue
        # The SAME wrap-tolerant matcher check_required uses, not a second copy: a pointer is
        # one line of prose in a hard-wrapped charter, so a line-by-line search would report
        # a missing pointer over a document that plainly carries it. That was measured on
        # this very population - three of six candidate findings were wrap artefacts.
        blob = collapse(body)[0].lower()
        for phrase in phrases:
            examined += 1
            if not str(phrase).strip():
                problems.append(
                    f"section {key}: a BLANK pointer phrase - REFUSED. It would assert "
                    f"nothing while reading exactly like an assertion")
            # STRIPPED, because collapse() appends a trailing space per line - an unstripped
            # needle only ever matched a phrase at the very end of a sentence, so 'see the
            # house file' failed against '...see the house file, and not restated.'
            elif collapse([str(phrase)])[0].lower().strip() not in blob:
                problems.append(
                    f"section {key} no longer carries its pointer '{phrase}'. A relocated "
                    f"block whose pointer has gone is indistinguishable from one that was "
                    f"REPEALED - restore the pointer, or remove this declaration if the "
                    f"rule really was repealed")
    rep.record(doc, "relocation pointers", examined, problems)


def check_sections_agreed_out(rep, doc, lines, agreed, in_scope=True):
    """DEVICE 4. Round 0.5's decisions, checked through their ARTEFACT.

    ROUND 0.5 IS A CONVERSATION AND A CONVERSATION CANNOT BE CHECKED. The template asks that
    the section set be PROPOSED and agreed one optional block at a time, each with its trigger
    question - and the output of that conversation has never been written anywhere. So a
    charter missing 5.6 is indistinguishable from a charter whose owner was never asked about
    5.6, and the second is the failure mode the whole round exists to prevent.

    THE ARTEFACT IS THE SAME SHAPE checkers.declared_absent ALREADY USES: subsection -> reason.
    A reader can then tell a decision from an oversight, which is the only thing that
    distinguishes them once the conversation is over.

    IT IS OPT-IN, AND THE COST IS DECLARED RATHER THAN HIDDEN (Wouter, 2026-09-10). An empty
    map reports N/A with its reason instead of failing, following md.plan_scope's precedent -
    so it CANNOT redden six charters at once, which is how this house has twice lost a
    control. The price, stated because it is real: nothing sets it on the day it ships, so
    device 4 begins DISABLED everywhere, and *a control that is always exempt is not a
    control*. Setting it per project is the sweep's work, not the checker's.

    ONLY NEGOTIABLE SUBSECTIONS MAY APPEAR. A CORE row is 'never negotiated away', so naming
    one here is a category error rather than a decision - and it would let a charter buy its
    way out of the FLOOR by writing a reason, which is the one thing that must not be
    purchasable.
    """
    if not in_scope:
        rep.record(doc, "sections agreed out", 0, [],
                   na_reason="not in size_scope - Round 0.5's decisions are a charter's")
        return
    agreed = {str(k): v for k, v in (agreed or {}).items()}
    if not agreed:
        rep.record(doc, "sections agreed out", 0, [],
                   na_reason="md.sections_agreed_out is empty (disabled) - record Round 0.5's "
                             "agreed-out set to enable. An empty map cannot tell a section "
                             "nobody wanted from a section nobody was asked about")
        return
    keys = {k for _, _, _, k in headings(lines) if k}
    problems = []
    for key in sorted(agreed):
        reason = agreed[key]
        if key in TEMPLATE_CORE:
            problems.append(
                f"{key} is marked CORE by the tier table - 'never negotiated away'. It "
                f"cannot be agreed out, and a reason here would buy a way past the CORE "
                f"floor. Write the subsection")
        elif key not in TEMPLATE_NEGOTIABLE:
            problems.append(
                f"{key} is not a subsection the template offers, so agreeing it out records "
                f"a decision about nothing. The negotiable set is "
                f"{', '.join(TEMPLATE_NEGOTIABLE)}")
        elif not str(reason).strip():
            problems.append(
                f"{key} is agreed out with a BLANK reason - REFUSED. Round 0.5's whole "
                f"output is the REASON; without it this records only that somebody typed "
                f"a number")
        elif key in keys:
            problems.append(
                f"{key} is recorded as agreed out, but the charter HAS it - the record is "
                f"stale, and a stale one reads exactly like a decision somebody took")
    rep.record(doc, "sections agreed out", len(agreed), problems)


PLAN_TRIPLE = ("purpose", "serves", "deliverable")


def _norm_head(cell: str) -> str:
    """A table heading reduced to its letters, so '**sub-step**' and 'Sub-Step' are one key."""
    return re.sub(r"[^a-z]", "", cell.lower())


def _row_is_closed(cell: str) -> bool:
    """A CLOSED row is struck through in its NAME cell - the house's own convention.

    Leading emphasis is stripped first: the cell is written '~~**NAME**~~' about as often as
    '**~~NAME~~**', and reading only the first two characters would call one of those open.
    """
    return cell.lstrip("* \t").startswith("~~")


def check_plan_purpose(rep, doc, lines, in_scope=True):
    """Every OPEN row of a plan file states its PURPOSE, what parent purpose it SERVES, and
    its DELIVERABLE - at phase, step and sub-step alike.

    WHY THIS EXISTS. A plan that names what will be done, without naming what it is FOR,
    cannot be checked by the person it is written for. Measured on the template that governs
    every plan file in this house: it asked a PHASE for 'produces', a STEP for 'documents
    produced', the CURRENT step for a 'what it is for' paragraph - and a SUB-STEP for nothing
    at all. The level where the work actually happens was the level with no statement of
    intent.

    WHY A SEPARATE SCOPE KEY AND NOT size_scope, AND IT IS THE MEASUREMENT THAT DECIDED IT.
    size_scope means 'is this a charter'. This asks 'is this a LIVE plan file', which is a
    different population and a moving one - a plan file is live until its phase closes and is
    a finished record for ever after.

    WHY NOT SIMPLY 'EVERY PLAN-*.md', WHICH IS THE OBVIOUS DESIGN AND IS WRONG. Measured over
    15 plan files in the house repository: the 14 CLOSED ones never used strikethrough at all
    - they recorded completion in a 'status' COLUMN instead - so 44 finished rows read as
    OPEN and a strikethrough-only arm reddens twelve finished records. And the discriminator
    that suggests itself next is worse: the LIVE file's own status row contains the word
    CLOSED (it says which steps are closed), so prose-matching the status row marks the one
    live plan finished and the check passes over the very file it exists to read. A check
    that goes green on its whole subject is indistinguishable from a check that ran.

    SO THE SCOPE IS DECLARED, NOT INFERRED - md.plan_scope, defaulting to EMPTY. A project
    names its live plan file, exactly as it names the live plan file in its charter's section
    3, and updating the glob is the same act as renaming the file when the phase turns over.
    An empty list reports N/A WITH THAT REASON on every run rather than passing silently,
    which is the difference between a disabled check and an invisible one.

    WHAT IS CHECKED AND WHAT IS DELIBERATELY NOT. That the three are WRITTEN DOWN is
    mechanical. Whether a purpose was MET is a judgement no script can make, and it is stated
    in prose at the close instead of being faked here.
    """
    if not in_scope:
        rep.record(doc, "plan purpose", 0, [],
                   na_reason="not in plan_scope - a purpose column is a live plan file's")
        return

    mask = code_fence_mask(lines)
    problems, examined = [], 0

    # ---- the PHASE level: the header key-value table's own 'purpose' row
    header_purpose = None
    for i, ln in enumerate(lines):
        if mask[i] or not ln.lstrip().startswith("|"):
            continue
        c = row_cells(ln)
        if len(c) == 2 and _norm_head(c[0]) == "purpose":
            header_purpose = c[1].strip()
            break
    examined += 1
    if header_purpose is None:
        problems.append(
            "the phase itself states no purpose - the header table has no 'purpose' row. "
            "'produces' is the DELIVERABLE and 'serves' is the parent; neither says what "
            "this phase is FOR")
    elif not header_purpose:
        problems.append("the phase's 'purpose' row is BLANK - a declared NONE with its "
                        "reason, never an empty cell")

    # ---- the STEP and SUB-STEP levels: every table whose header names one of them
    i, tables = 0, 0
    while i < len(lines):
        if (not mask[i] and lines[i].lstrip().startswith("|")
                and i + 1 < len(lines) and DELIM_RE.match(lines[i + 1])):
            head = [_norm_head(c) for c in row_cells(lines[i])]
            namecol = next((k for k, h in enumerate(head)
                            if h in ("step", "substep", "steps", "substeps")), None)
            if namecol is None:
                i += 1
                continue
            tables += 1
            level = "sub-step" if head[namecol].startswith("sub") else "step"
            where = {t: head.index(t) for t in PLAN_TRIPLE if t in head}
            j = i + 2
            while j < len(lines) and not mask[j] and lines[j].lstrip().startswith("|"):
                c = row_cells(lines[j])
                if namecol < len(c) and not _row_is_closed(c[namecol]):
                    examined += 1
                    ident = c[0].strip("* ") or c[namecol][:30]
                    missing = [t for t in PLAN_TRIPLE
                               if t not in where or where[t] >= len(c)
                               or not c[where[t]].strip()]
                    if missing:
                        absent = [t for t in PLAN_TRIPLE if t not in where]
                        why = (f"the table has no {', '.join(absent)} column"
                               if absent else "left blank")
                        problems.append(
                            f"line {j + 1}: OPEN {level} {ident} states no "
                            f"{', '.join(missing)} - {why}. An open row answers all three, "
                            f"and a deliverable that does not exist is a declared NONE with "
                            f"its reason")
                j += 1
            i = j
            continue
        i += 1

    if not tables:
        problems.append(
            "no step or sub-step table found - a plan file in plan_scope with no table of "
            "steps is either misfiled or unplanned, and either is a finding")
    rep.record(doc, "plan purpose", examined, problems)


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
    """
    sizes = section_sizes(body.splitlines())
    if not sizes:
        return []
    scoped = in_size_scope(path, cfg["size_scope"])
    cap, glob, void = cap_for(path, cfg["max_lines"], scoped)
    if void:
        against = "  (no cap applies - max_lines is ambiguous for this file)"
    elif cap:
        against = f" against a cap of {cap}" + (f" (via {glob!r})" if glob else "")
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
    out = [f"  {path}: {loaded_lines(body)} loaded{against}"]
    for key in sorted(sizes, key=lambda k: (len(str(k)), str(k))):
        mark = ""
        sc = cfg["section_caps"].get(key)
        if sc and scoped:
            over = sizes[key] - sc
            mark = f"  <- cap {sc}" + (f", OVER by {over}" if over > 0 else ", ok")
        elif sc:
            mark = "  <- capped elsewhere, not here"
        out.append(f"      section {key:<4} {sizes[key]:>5} lines{mark}")
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
    check_file_length(rep, doc, text, cfg["max_lines"], scoped, path)
    check_section_caps(rep, doc, lines, cfg["section_caps"], scoped)
    check_charter_structure(rep, doc, lines, cfg.get("charter_structure"), scoped)
    # THE FLOOR AND THE ARCHETYPE, both scoped exactly as charter structure is: the question
    # 'is this a charter' is one question, asked once, and three arms read the answer.
    check_charter_archetype(rep, doc, lines, cfg.get("archetype_absent"), scoped)
    check_core_sections(rep, doc, lines, cfg.get("core_sections"), scoped)
    check_sections_agreed_out(rep, doc, lines, cfg.get("sections_agreed_out"), scoped)
    check_pointers(rep, doc, lines, cfg.get("pointers"), scoped)
    # A SEPARATE SCOPE, not size_scope: 'is this a charter' and 'is this a LIVE plan file'
    # are different populations, and the second one moves as phases close.
    plan_globs = cfg.get("plan_scope") or []
    if not plan_globs:
        rep.record(doc, "plan purpose", 0, [],
                   na_reason="plan_scope is empty (disabled) - name the live plan file to enable")
    else:
        check_plan_purpose(rep, doc, lines, in_size_scope(path, plan_globs))


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


def writes_subsections(top, n, declared=None):
    """A charter with ONE top-level section `top` carrying `n` gapless subsections.

    It carries its own `charter_structure` map where one is given, for the same reason
    writes_body_under carries max_lines: the declared and undeclared arms differ only in the
    CONFIG, so a builder that dropped it would let the pair pass while comparing two
    different documents.

    The subsections are always 1..n, which is the whole point: they satisfy the gapless
    check perfectly, so only the new check can tell 9 from 8.
    """
    def build(tmp):
        out = ["# Doc", "", f"## {top} - Section {top}", ""]
        for i in range(1, n + 1):
            out += [f"### {top}.{i} Sub {i}", "", "Body.", ""]
        q = tmp / "case.md"
        q.write_text(NL.join(out) + NL, encoding="utf-8")
        return (q, declared) if declared is not None else q
    return build


def checks_struct_under(spec):
    """The charter-structure verdict for one document under one declared-excess map."""
    path, declared = spec
    rep = Report()
    verify_file(rep, path, dict(SELFTEST_CFG, charter_structure=declared))
    return rep.by_name().get(STRUCT)


#: A sentinel, because None is a MEANINGFUL declaration value for the archetype arm - it is
#: 'nothing declared', which is the case that must FAIL. Using None to mean 'no map given'
#: as well would make the one case the arm exists for unwritable, and the first attempt
#: crashed on exactly that.
NO_DECL = object()


def writes_charter(omit=(), archetype=None, declared=NO_DECL, key=None, extra=()):
    """A charter carrying every CORE heading except those in `omit`.

    THE FIXTURE IS BUILT FROM TEMPLATE_CORE ITSELF, not from a hand-typed list. A second copy
    of the fourteen keys would let the constant and its own test drift apart silently, which
    is the one failure a selftest must never be capable of - the test would keep passing
    against the list it shipped with.

    Subsections are emitted under their own top-level parent so the gapless check has no
    opinion: this fixture exists to exercise the FLOOR, and a case that failed for a
    numbering reason would prove nothing about presence.
    """
    def build(tmp):
        out = ["# Charter", ""]
        if archetype is not None:
            out += [f"**ARCHETYPE: {archetype}.**", ""]
        tops, subs = [], {}
        # `extra` carries NEGOTIABLE subsections. The CORE set alone cannot express 'the
        # charter HAS a subsection somebody recorded as agreed out', because a CORE row can
        # never legitimately be agreed out - the category-error arm fires first and the stale
        # arm is unreachable. Measured: the first version of that case silently PASSED.
        for k in tuple(TEMPLATE_CORE) + tuple(extra):
            if k in omit:
                continue
            top, _, sub = k.partition(".")
            if top not in tops:
                tops.append(top)
            if sub:
                subs.setdefault(top, []).append(sub)
        for top in sorted(tops, key=int):
            out += [f"## {top} - Section {top}", "", "Body.", ""]
            for sub in sorted(subs.get(top, []), key=int):
                out += [f"### {top}.{sub} Sub {sub}", "", "Body.", ""]
        q = tmp / (key or "charter.md")
        q.write_text(NL.join(out) + NL, encoding="utf-8")
        return q if declared is NO_DECL else (q, declared)
    return build


def checks_core_under(spec):
    """The CORE-floor verdict for one document under one declared-absence map."""
    path, declared = spec
    rep = Report()
    verify_file(rep, path, dict(SELFTEST_CFG, core_sections=declared))
    return rep.by_name().get(CORE)


def checks_arch_under(spec):
    """The archetype verdict for one document under one declared-absence reason."""
    path, declared = spec
    rep = Report()
    verify_file(rep, path, dict(SELFTEST_CFG, archetype_absent=declared))
    return rep.by_name().get(ARCH)


def checks_agreed_under(spec):
    """The agreed-out verdict for one document under one agreed-out map."""
    path, agreed = spec
    rep = Report()
    verify_file(rep, path, dict(SELFTEST_CFG, sections_agreed_out=agreed))
    return rep.by_name().get(AGREED)


def writes_pointer_charter(body, declared=NO_DECL, wrap=False):
    """A charter whose section 5 carries `body` as its pointer text.

    `wrap` hard-wraps the pointer across a line ending, which is the case a line-by-line
    matcher gets WRONG - and getting it wrong is what killed the first design of this arm.
    """
    def build(tmp):
        text = body
        if wrap and " " in body:
            cut = body.rfind(" ", 0, max(len(body) // 2, 1))
            text = body[:cut] + NL + body[cut + 1:]
        # THE PARENTS ARE DERIVED, NOT LISTED. Sections 1, 2 and 5 appear in TEMPLATE_CORE
        # only as SUBSECTIONS, so a loop that emits a heading per CORE entry produces no
        # '## 5' at all - and the arm then reported the section missing on both arms, which
        # read as the check firing correctly on the bad one.
        out = ["# Charter", "", "**ARCHETYPE: Research / analysis.**", ""]
        tops, subs = [], {}
        for k in TEMPLATE_CORE:
            top, _, sub = k.partition(".")
            if top not in tops:
                tops.append(top)
            if sub:
                subs.setdefault(top, []).append(sub)
        for top in sorted(tops, key=int):
            out += [f"## {top} - Section {top}", ""]
            out += ([text, ""] if top == "5" else ["Body.", ""])
            for sub in sorted(subs.get(top, []), key=int):
                out += [f"### {top}.{sub} Sub {sub}", "", "Body.", ""]
        q = tmp / "pointer.md"
        q.write_text(NL.join(out) + NL, encoding="utf-8")
        return q if declared is NO_DECL else (q, declared)
    return build


def checks_pointers_under(spec):
    """The relocation-pointer verdict for one document under one pointer map."""
    path, pointers = spec
    rep = Report()
    verify_file(rep, path, dict(SELFTEST_CFG, pointers=pointers,
                                check_numbered_headings="off"))
    return rep.by_name().get(PTR)


def _selftest_ceiling_confirms_the_floor(tmp):
    """THE CROSS-CHECK NO CASE ROW CAN MAKE: the ceiling PASSES what the floor FAILS.

    The defect the floor exists for was not merely unreported - it was CONFIRMED by the one
    instrument already pointed at charter shape. `charter structure` asks for never MORE than
    the template, and a charter missing 5.4 has fewer, which is exactly what MAPPING produces
    and therefore a PASS. So the check that looked like it covered charter shape said the
    charter was fine while TEST was missing from it.

    Without this assertion the two arms could drift into agreeing, and a case table can only
    show the new arm fires - never that nothing else would have.
    """
    d = tmp / "ceiling-confirms"
    d.mkdir(parents=True, exist_ok=True)
    path = writes_charter(omit=("5.4",), archetype="Research / analysis")(d)
    rep = Report()
    verify_file(rep, path, SELFTEST_CFG)
    by = rep.by_name()
    struct, core = by.get(STRUCT), by.get(CORE)
    if struct != PASS:
        return f"FAIL - expected the CEILING check to PASS on a charter missing 5.4, got {struct!r}"
    if core != FAIL:
        return f"FAIL - expected the FLOOR check to FAIL on a charter missing 5.4, got {core!r}"
    return PASS


def _selftest_archetype_needles_disagree(tmp):
    """THE MEASUREMENT THAT DECIDED THE SHAPE, kept as an assertion so it cannot be undone.

    Two naive needles were tried over the six house charters before this arm was written, and
    they answered WRONGLY IN OPPOSITE DIRECTIONS. Searching for the eleven NAMES matches
    ordinary prose - a charter discussing another project's archetype "declares" one. Searching
    for the WORD 'archetype' matches a sentence about emitted line counts.

    So the arm requires a LABELLED declaration, and this asserts both failure modes stay
    rejected. Without it, a later 'helpful' loosening would silently restore the false
    positives that made the original measurement wrong.
    """
    d = tmp / "archetype-needles"
    d.mkdir(parents=True, exist_ok=True)
    prose = writes_charter(archetype=None, key="prose.md")(d)
    body = prose.read_text(encoding="utf-8")
    # Both traps in one document: an archetype NAME in prose, and the WORD archetype.
    prose.write_text(body + NL.join([
        "", "This project is not a Claude skill, though it borrows from one.",
        "The archetype table has eleven rows; 20 of 22 archetype emits meet the cap.", "",
    ]), encoding="utf-8")
    rep = Report()
    verify_file(rep, prose, SELFTEST_CFG)
    if rep.by_name().get(ARCH) != FAIL:
        return ("FAIL - a charter merely MENTIONING an archetype name and the word "
                "'archetype' was accepted as declaring one")
    return PASS


def _selftest_gapless_confirms_the_defect(tmp):
    """THE ASSERTION NO CASE ROW CAN MAKE: the OLD instrument passes what the new one fails.

    The defect this check exists for was not merely unreported - it was CONFIRMED. A section
    numbered 1..16 satisfies check_headings' gapless rule perfectly, so the one instrument
    already pointed at subsection numbering said PASS. A case table can show the new check
    fires; only this can show that nothing else would have.

    It is a cross-CHECK assertion off ONE fixture, the same shape verify_confidential's
    cross-arm assertion uses, and without it the pair of checks could drift into agreeing.
    """
    d = tmp / "gapless-confirms"
    d.mkdir(parents=True, exist_ok=True)
    path = writes_subsections(5, 16)(d)
    rep = Report()
    verify_file(rep, path, SELFTEST_CFG)
    by = rep.by_name()
    heads, struct = by.get(HEADS), by.get(STRUCT)
    if heads != PASS:
        return f"FAIL - expected the gapless check to PASS on 1..16, got {heads!r}"
    if struct != FAIL:
        return f"FAIL - expected the structure check to FAIL on 16-vs-8, got {struct!r}"
    return PASS


def writes_plan(rows, triple=True, header_purpose=True):
    """A PLAN FILE: a header key-value table, then a sub-step table.

    `rows` is a list of (name, closed, filled) - `filled` being the text put in all three
    of purpose/serves/deliverable, or None/"" for the blank case.

    THE ARMS DIFFER IN ONE THING EACH, deliberately. `triple` toggles whether the three
    COLUMNS exist at all; `filled` toggles whether they are ANSWERED; `closed` toggles
    whether the row is a finished record. Those are three different defects and a builder
    that could only produce one of them would let the check pass while proving one third of
    what it claims.
    """
    def build(tmp):
        out = ["# PLAN - a phase", "",
               "| | |", "| --- | --- |",
               "| **status** | IN PROGRESS |"]
        if header_purpose:
            out.append("| **purpose** | so that the phase is for something nameable |")
        out += ["", "## 1 - The sub-steps", ""]
        if triple:
            out += ["| # | sub-step | purpose | serves | deliverable |",
                    "| --- | --- | --- | --- | --- |"]
        else:
            out += ["| # | sub-step | done when |", "| --- | --- | --- |"]
        for i, (name, closed, filled) in enumerate(rows, 1):
            nm = "~~**" + name + "**~~" if closed else "**" + name + "**"
            if triple:
                v = filled or ""
                out.append(f"| **{i}** | {nm} | {v} | {v} | {v} |")
            else:
                out.append(f"| **{i}** | {nm} | it is done |")
        q = tmp / "case.md"
        q.write_text(NL.join(out) + NL, encoding="utf-8")
        return q
    return build


def _selftest_plan_purpose_is_the_only_witness(tmp):
    """THE ASSERTION NO CASE ROW CAN MAKE: every OTHER check passes the document this one
    fails.

    The defect was not merely unreported - it was CONFIRMED by everything pointed at a plan
    file. A sub-step table with no purpose column is a perfectly well-formed table with
    perfectly gapless headings, so `tables well-formed` and `heading numbering` both say
    PASS over the exact shape this check exists to find. A case row can show the new check
    fires; only this can show that nothing already in the checker would have.
    """
    d = tmp / "plan-only-witness"
    d.mkdir(parents=True, exist_ok=True)
    path = writes_plan([("A STEP WITH NO STATED PURPOSE", False, None)], triple=False)(d)
    rep = Report()
    verify_file(rep, path, dict(SELFTEST_CFG, plan_scope=["*.md"]))
    by = rep.by_name()
    for name in (TABLES, HEADS):
        if by.get(name) != PASS:
            return f"FAIL - expected {name!r} to PASS on the purposeless plan, got {by.get(name)!r}"
    if by.get(PLANP) != FAIL:
        return f"FAIL - expected {PLANP!r} to FAIL on the purposeless plan, got {by.get(PLANP)!r}"
    return PASS


def checks_length_under(spec):
    """The file-length verdict for one document under one max_lines map."""
    path, max_lines = spec
    rep = Report()
    verify_file(rep, path, dict(SELFTEST_CFG, max_lines=max_lines))
    return rep.by_name().get(LENGTH)


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
STRUCT = "charter structure"
ARCH, CORE = "charter archetype", "core sections present"
AGREED = "sections agreed out"
PTR = "relocation pointers"
PLANP = "plan purpose"

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
        # THE CHARTER-STRUCTURE PAIR. Both arms are gapless 1..n, so check_headings PASSES
        # on BOTH - which is the defect, and why the twin is 8 rather than something ragged.
        # A twin with a gap would fail for the wrong reason and prove nothing about excess.
        Case("section with MORE subsections than the template", checks(STRUCT),
             writes_subsections(5, 9), writes_subsections(5, 8)),
        # A SUBSET IS MAPPING, and this is the arm that stops the check being "must equal 8".
        # Without it, a check that fired on any count != 8 would pass the row above and
        # condemn three of the five charters this house has already closed as correct.
        Case("FEWER subsections than the template is mapping, not a finding", checks(STRUCT),
             writes_subsections(5, 9), writes_subsections(5, 3)),
        # THE DECLARATION, proved on ONE document: the same excess fails undeclared and
        # passes declared. Two documents would let the pair pass while comparing two things.
        Case("a DECLARED excess passes", checks_struct_under,
             writes_subsections(5, 9, {}),
             writes_subsections(5, 9, {"5": "this section owns the domain rules"})),
        # A BLANK REASON IS REFUSED - the same rule check_checkers v13 applies one level up,
        # because a command line cannot carry a reason and the reason IS the distinction.
        Case("a declared excess with a BLANK reason is refused", checks_struct_under,
             writes_subsections(5, 9, {"5": "   "}),
             writes_subsections(5, 9, {"5": "declared, with an actual reason"})),
        # AND THE DECLARATION CANNOT OUTLIVE ITS FACTS. Once the section is mapped back down
        # the declaration must go red, or a config records an exemption for a defect that no
        # longer exists - the DECL-STALE shape, one level down.
        Case("a declaration for a section that is NOT in excess is stale",
             checks_struct_under,
             writes_subsections(5, 8, {"5": "was an excess once"}),
             writes_subsections(5, 8, {})),
        # THE SCOPE, proved on one input: a non-charter is not judged against a charter's
        # shape. Without it the check would condemn every README and plan file in a run.
        Case("out of size_scope reports N/A, not a failure (structure)",
             checks_cfg(STRUCT, size_scope=["nothing-matches-this"]),
             writes_subsections(5, 9), writes_subsections(5, 9),
             want=NA, good_want=NA),
        # ---------------------------------------------------------------- DEVICE 1: the FLOOR
        # THE PAIR IS ONE KEY APART. Both arms are gapless and both are a SUBSET of the
        # template, so charter structure PASSES on both - which is the whole point, and why
        # the twin omits nothing rather than omitting something else.
        Case("a MISSING CORE subsection is a finding", checks(CORE),
             writes_charter(omit=("5.4",), archetype="Research / analysis"),
             writes_charter(archetype="Research / analysis")),
        # THE DISCRIMINATOR, and without it the arm would be 'every subsection must exist'.
        # A DEFAULT or OPTIONAL subsection is Round 0.5's decision to take; only CORE is
        # "never negotiated away". 1.4 is DEFAULT and 1.6 OPTIONAL, so neither may fire.
        Case("a missing DEFAULT or OPTIONAL subsection is NOT a finding", checks(CORE),
             writes_charter(omit=("1.5",), archetype="Research / analysis"),
             writes_charter(archetype="Research / analysis")),
        Case("a DECLARED absent CORE subsection passes", checks_core_under,
             writes_charter(omit=("5.8",), archetype="Research / analysis", declared={}),
             writes_charter(omit=("5.8",), archetype="Research / analysis",
                            declared={"5.8": "no charter-writing rules yet; see the plan"})),
        Case("a declared CORE absence with a BLANK reason is refused", checks_core_under,
             writes_charter(omit=("5.8",), archetype="Research / analysis",
                            declared={"5.8": "   "}),
             writes_charter(omit=("5.8",), archetype="Research / analysis",
                            declared={"5.8": "declared, with an actual reason"})),
        # AND IT CANNOT OUTLIVE ITS FACTS - the DECL-STALE shape, exactly as the ceiling and
        # check_checkers apply it. Once 5.8 is written the declaration must go red.
        Case("a declaration for a CORE subsection that IS present is stale", checks_core_under,
             writes_charter(archetype="Research / analysis",
                            declared={"5.8": "was absent once"}),
             writes_charter(archetype="Research / analysis", declared={})),
        Case("out of size_scope reports N/A, not a failure (CORE floor)",
             checks_cfg(CORE, size_scope=["nothing-matches-this"]),
             writes_charter(omit=("5.4",), archetype="Research / analysis"),
             writes_charter(omit=("5.4",), archetype="Research / analysis"),
             want=NA, good_want=NA),
        Case("the CEILING check PASSES the charter the FLOOR fails",
             _selftest_ceiling_confirms_the_floor, lambda tmp: tmp, want=PASS,
             unpaired_reason="this is a CROSS-CHECK invariant off one fixture, not a "
                             "fire-on-bad check - it asserts that the OLD instrument passes "
                             "the very document the new one fails, which is what makes the "
                             "floor a new question rather than a second opinion"),
        # ---------------------------------------------------------------- DEVICE 3: archetype
        Case("a charter naming NO archetype is a finding", checks(ARCH),
             writes_charter(archetype=None),
             writes_charter(archetype="Analysis + rebuild of an existing artefact")),
        # PUNCTUATION AND CASE ARE FOLDED AWAY ON PURPOSE. The check is about whether the
        # DECISION was recorded, never about typography - a charter written with an em dash
        # has named its archetype exactly as well as one written with a hyphen, and an arm
        # that told them apart would teach people to copy a dash rather than make a choice.
        Case("an archetype written with different punctuation still counts", checks(ARCH),
             writes_charter(archetype="Automation 4 - telepathy"),
             writes_charter(archetype="automation 1 — FILE and Data")),
        Case("a DECLARED absent archetype passes", checks_arch_under,
             writes_charter(archetype=None, declared=None),
             writes_charter(archetype=None,
                            declared="a house-tooling repo, not one of the eleven")),
        Case("a declared absent archetype with a BLANK reason is refused", checks_arch_under,
             writes_charter(archetype=None, declared="   "),
             writes_charter(archetype=None, declared="declared, with an actual reason")),
        Case("a declaration over a charter that DOES name one is stale", checks_arch_under,
             writes_charter(archetype="Claude skill", declared="fits none of the eleven"),
             writes_charter(archetype="Claude skill", declared=None)),
        Case("out of size_scope reports N/A, not a failure (archetype)",
             checks_cfg(ARCH, size_scope=["nothing-matches-this"]),
             writes_charter(archetype=None), writes_charter(archetype=None),
             want=NA, good_want=NA),
        Case("a MENTION is not a DECLARATION",
             _selftest_archetype_needles_disagree, lambda tmp: tmp, want=PASS,
             unpaired_reason="it asserts that two NAIVE needles stay rejected - the pair "
                             "that answered wrongly in OPPOSITE directions over the six "
                             "house charters before this arm was written. There is no "
                             "'good' arm: the good arm is every other archetype case"),
        # ------------------------------------------------------------- DEVICE 4: agreed out
        # THE CATEGORY ERROR, and it is the one that matters: naming a CORE row here would
        # buy a way past the FLOOR by writing a sentence. 5.4 is CORE, 5.6 is OPTIONAL.
        Case("a CORE subsection cannot be agreed out", checks_agreed_under,
             writes_charter(omit=("5.4",), archetype="Research / analysis",
                            declared={"5.4": "we do not test"}),
             writes_charter(omit=("5.4",), archetype="Research / analysis",
                            declared={"5.6": "publication is genuinely off the table"})),
        Case("agreeing out a subsection the template does not offer", checks_agreed_under,
             writes_charter(archetype="Research / analysis",
                            declared={"9.9": "a section that does not exist"}),
             writes_charter(archetype="Research / analysis",
                            declared={"1.6": "under 250 lines; no index needed"})),
        Case("an agreed-out entry with a BLANK reason is refused", checks_agreed_under,
             writes_charter(archetype="Research / analysis", declared={"1.6": "  "}),
             writes_charter(archetype="Research / analysis",
                            declared={"1.6": "under 250 lines; no index needed"})),
        # AND IT CANNOT OUTLIVE ITS FACTS. 1.5 is CORE and always emitted by the fixture, so
        # a record saying it was agreed out is stale by construction; the twin names a row
        # the fixture genuinely omits.
        Case("a record for a subsection the charter HAS is stale", checks_agreed_under,
             writes_charter(archetype="Research / analysis", extra=("5.2",),
                            declared={"5.2": "not a git repository"}),
             writes_charter(archetype="Research / analysis", extra=("5.2",),
                            declared={"1.6": "under 250 lines; no index needed"})),
        # THE OPT-IN, proved on one input. Wouter's ruling: an empty map is N/A with its
        # reason, never a silent pass - the md.plan_scope precedent. It ships DISABLED, and
        # this row is what stops that being mistaken for a pass.
        Case("an EMPTY agreed-out map reports N/A with its reason, not a pass",
             checks_cfg(AGREED, sections_agreed_out={}),
             writes_charter(archetype="Research / analysis"),
             writes_charter(archetype="Research / analysis"),
             want=NA, good_want=NA),
        Case("out of size_scope reports N/A, not a failure (agreed out)",
             checks_cfg(AGREED, size_scope=["nothing-matches-this"],
                        sections_agreed_out={"5.4": "we do not test"}),
             writes_charter(archetype="Research / analysis"),
             writes_charter(archetype="Research / analysis"),
             want=NA, good_want=NA),
        # -------------------------------------------------------- DEVICE 5: relocation pointers
        # THE PAIR IS ONE SENTENCE APART, and both documents are otherwise identical: the
        # relocation is invisible to every other arm, which is the whole reason this exists.
        Case("a relocated block whose POINTER has gone", checks_pointers_under,
             writes_pointer_charter("This section was reorganised.",
                                    declared={"5": ["see the house file"]}),
             writes_pointer_charter("Relocated - see the house file, and not restated.",
                                    declared={"5": ["see the house file"]})),
        # THE WRAP CASE, and it is the one that decided the design. The first version of this
        # device searched prose LINE BY LINE and produced four false positives in six over the
        # real charters, three of them purely because a claim and its destination landed on
        # different lines. Both arms here declare the same phrase; only the wrapping differs.
        Case("a pointer HARD-WRAPPED across a line ending still counts", checks_pointers_under,
             writes_pointer_charter("This section was reorganised.",
                                    declared={"5": ["see the house file"]}),
             writes_pointer_charter("Relocated - see the house file, and not restated.",
                                    declared={"5": ["see the house file"]}, wrap=True)),
        # A SECTION THAT IS GONE ENTIRELY is the shape a pointer's return path disappearing
        # takes, and the house rule it enforces - never delete a heading, it is the return
        # path a pointer resolves against - had no check at all before this.
        Case("a declared pointer whose SECTION has gone", checks_pointers_under,
             writes_pointer_charter("Relocated - see the house file.",
                                    declared={"9": ["see the house file"]}),
             writes_pointer_charter("Relocated - see the house file.",
                                    declared={"5": ["see the house file"]})),
        Case("a BLANK pointer phrase is refused", checks_pointers_under,
             writes_pointer_charter("Relocated - see the house file.",
                                    declared={"5": ["  "]}),
             writes_pointer_charter("Relocated - see the house file.",
                                    declared={"5": ["see the house file"]})),
        Case("an EMPTY pointer map reports N/A with its reason, not a pass",
             checks_cfg(PTR, pointers={}, check_numbered_headings="off"),
             writes_pointer_charter("Relocated - see the house file."),
             writes_pointer_charter("Relocated - see the house file."),
             want=NA, good_want=NA),
        Case("out of size_scope reports N/A, not a failure (pointers)",
             checks_cfg(PTR, size_scope=["nothing-matches-this"],
                        pointers={"5": ["a phrase that is absent"]},
                        check_numbered_headings="off"),
             writes_pointer_charter("Relocated."), writes_pointer_charter("Relocated."),
             want=NA, good_want=NA),
        Case("the gapless check CONFIRMS what the structure check catches",
             _selftest_gapless_confirms_the_defect, lambda tmp: tmp, want=PASS,
             unpaired_reason="this is a CROSS-CHECK invariant off one fixture, not a "
                             "fire-on-bad check - it asserts that the OLD instrument passes "
                             "the very document the new one fails, which is the fact that "
                             "made the defect invisible. Both arms would want PASS"),
        # THE PLAN-PURPOSE PAIR. The bad arm is the shape every plan file in this house had
        # on 2026-09-10: a sub-step table with no purpose column at all.
        Case("an OPEN sub-step row with no purpose/serves/deliverable column",
             checks_cfg(PLANP, plan_scope=["*.md"]),
             writes_plan([("A", False, None)], triple=False),
             writes_plan([("A", False, "so that the drift cannot come back unnamed")])),
        # A CLOSED ROW IS A FINISHED RECORD. This is the arm that stops the check being
        # "every row": without it, enabling the check on a repository would redden 44 rows
        # across 12 archived plan files, and a check that reddens finished work is one
        # somebody switches off. The two arms differ ONLY in the strikethrough.
        Case("a CLOSED row is not judged - it is a finished record",
             checks_cfg(PLANP, plan_scope=["*.md"]),
             writes_plan([("A", False, None)], triple=False),
             writes_plan([("A", True, None)], triple=False)),
        # A BLANK CELL IS REFUSED even where the column exists - the same rule a declared
        # checker absence is held to. An empty cell reads the same whether somebody decided
        # or nobody looked, which is exactly what a declared NONE prevents.
        Case("a column that exists but is left BLANK is refused",
             checks_cfg(PLANP, plan_scope=["*.md"]),
             writes_plan([("A", False, "")]),
             writes_plan([("A", False, "NONE - this sub-step leaves only edits behind")])),
        # THE PHASE LEVEL, which is the one the retrofit is likeliest to skip: the rows get
        # filled in and the header table keeps only 'produces' and 'serves', neither of
        # which says what the phase is FOR.
        Case("the phase itself must state a purpose, not only its rows",
             checks_cfg(PLANP, plan_scope=["*.md"]),
             writes_plan([("A", False, "so that X")], header_purpose=False),
             writes_plan([("A", False, "so that X")], header_purpose=True)),
        # THE SCOPE, both ways. Out of plan_scope a charter or a README is not judged
        # against a plan file's shape; and an EMPTY plan_scope is a DISABLED check that says
        # so, never a silent pass.
        Case("out of plan_scope reports N/A, not a failure",
             checks_cfg(PLANP, plan_scope=["nothing-matches-this"]),
             writes_plan([("A", False, None)], triple=False),
             writes_plan([("A", False, None)], triple=False),
             want=NA, good_want=NA),
        Case("an EMPTY plan_scope reports N/A with its reason, not a pass",
             checks_cfg(PLANP, plan_scope=[]),
             writes_plan([("A", False, None)], triple=False),
             writes_plan([("A", False, None)], triple=False),
             want=NA, good_want=NA),
        Case("nothing else in the checker catches a purposeless plan row",
             _selftest_plan_purpose_is_the_only_witness, lambda tmp: tmp, want=PASS,
             unpaired_reason="a CROSS-CHECK invariant off one fixture, the same shape as "
                             "the gapless one above: it asserts that the checks ALREADY "
                             "pointed at a plan file pass the document this one fails. "
                             "Both arms would want PASS"),
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
