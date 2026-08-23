#!/usr/bin/env python3
"""verify_md.py - the document checker.  CHECKER VERSION 13 (2026-08-21)

If a project's copy says a lower version than this one, it is stale - see the "Checkers"
line for each version in ...\\Coding\\TEMPLATE-CHANGELOG.md and re-copy.

Checks Markdown deliverables: CLAUDE.md, plan documents, registers, READMEs, research
write-ups, guided-build playbooks. Standard library only, so it runs anywhere.

    uv run python tools/verify_md.py                    # check what the config lists
    uv run python tools/verify_md.py FILE [FILE ...]    # check named files instead
    uv run python tools/verify_md.py --selftest         # prove every check can FAIL

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

A SENSITIVE FORBIDDEN LIST NEVER GOES IN THE CONFIG. verify.config.json is committed - a
project's tailoring belongs in its repository. So a forbidden list that is ITSELF the
sensitive material must be read from somewhere else, or the file publishes exactly what it
protects. Point 'forbidden_phrases_file' at a path outside the repository, or set
VERIFY_FORBIDDEN_LIST in the environment so CI can supply its own copy as a secret. The
scanner ships; the list never does. An ordinary list - a retired product name, an old
spelling - is not sensitive and belongs inline in the config, where it is simplest.

AND THE REPORT NEVER PRINTS A FORBIDDEN PHRASE. It prints the phrase's position in the
list. Moving the list out of the repository and then echoing its contents into a terminal,
a CI log or a pasted failure report leaks it by a different route - and that route reaches
places no scanner can clean up afterwards.

CONFIGURE IT, DO NOT FORK IT. Settings live in verify.config.json under the "md" key.
Run --write-config once to get a commented starting point.
"""
from __future__ import annotations

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
    FAIL, NA, PASS, RC_COULD_NOT_RUN, SIZE_CLASS, VOID, Case, Report,
    load_section, loaded_lines, report_pairing, run_cases, selftest_config,
    write_section,
)

# --------------------------------------------------------------------------- config

FORBIDDEN_LIST_ENV = "VERIFY_FORBIDDEN_LIST"

DEFAULT_CONFIG = {
    "files": ["CLAUDE.md", "README.md"],
    "required_sections": [],
    "forbidden_phrases": [],
    "forbidden_phrases_file": "",
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
    "report_numeric_claims": True,
    "report_cross_doc_refs": True,
    "max_line_length": 0,
    "max_lines": 0,
    "section_caps": {},
    "size_scope": ["CLAUDE.md", "*/CLAUDE.md"],
    "report_section_sizes": True,
}

CONFIG_COMMENT = {
    "files": "Documents to check when no filenames are given on the command line.",
    "required_sections": "Headings that must exist, e.g. ['7. Current status']. Empty = do not check.",
    "forbidden_phrases": "Strings that must never appear, listed INLINE. For an ordinary list only - a retired product name, an old spelling. THIS FILE IS COMMITTED.",
    "forbidden_phrases_file": "Path to a list whose CONTENTS are themselves sensitive - one phrase per line, '#' comments ignored. Keep it OUTSIDE the repository, not merely gitignored. " + FORBIDDEN_LIST_ENV + " overrides this path, so CI can supply its own copy as a secret. Declared and not found = VOID, never a silent pass.",
    "placeholder_markers": "Unfilled-template markers. A finished document has none.",
    "check_numbered_headings": "'auto' checks only if the file uses numbered headings; true forces it.",
    "check_internal_refs": "Resolve every S-N.M reference to a real heading in the same file.",
    "check_file_links": "Resolve every relative markdown link to a file on disk.",
    "report_numeric_claims": "List sentences asserting counts, so you can re-derive them. Never fails.",
    "report_cross_doc_refs": "List lines that name another .md AND use a section sign. A sign resolves against ITS OWN file, so such a line is probably pointing at the wrong section - and if the number happens to exist locally it passes SILENTLY. Report-only: the checker cannot know which file was meant.",
    "max_line_length": "0 disables. Set e.g. 110 to keep documents diff-friendly.",
    "max_lines": "0 disables. Either ONE number for every file in size_scope, or a MAP of glob to cap - {\"CLAUDE.md\": 350, \"PLAN-*.md\": 120} - when a project has documents of different size classes. With a map, the LONGEST matching glob wins, a file matching none reports N/A, and two globs of the same length both matching is VOID rather than a silent pick. TWO SIZE CLASSES: M 200 (1-8 sessions, the default) and L 350 (more than 8, a declared exemption). Class S was retired 2026-08-21 because a minimal FILLED charter measures ~200; 120 survives only as the PLAN-*.md cap, which is a different document. Counts what LOADS, not what is in the file - block-level HTML comments are stripped before Claude receives them. Over the cap means RELOCATE, never delete.",
    "size_scope": "Which files the size checks apply to, as filename globs. A cap is a property of a CHARTER - a README has no size class, and a *-TEMPLATE.md contains a template FOR a section and is legitimately long. Anything outside this list reports N/A with that reason.",
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


def cell_count(row: str) -> int:
    """Cells in a table row, counting only UNESCAPED pipes as separators.

    The leading and trailing empty fragments are the table's outer borders, not cells.
    """
    parts = CELL_PIPE.split(row.strip())
    if parts and parts[0] == "":
        parts = parts[1:]
    if parts and parts[-1] == "":
        parts = parts[:-1]
    return len(parts)


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


def collapse(lines):
    """Whole document as one whitespace-collapsed string, plus a line number per character.

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
    for i, ln in enumerate(lines, 1):
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


def read_phrase_list(path: Path):
    """One phrase per line; '#' comments and blanks ignored. Returns None if unreadable."""
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


def resolve_forbidden(root: Path, cfg):
    """Return (phrases, sources, void_reason).

    Inline and external lists are MERGED rather than one overriding the other: a project
    may legitimately have a public list it is happy to commit and a private one it is not,
    and making them exclusive would force the public half out of the repository too.

    A list declared and not found is VOID, never N/A and never a silent pass. That is the
    whole trap an external list opens - the protection quietly stops running on any
    machine that lacks the file, and the report still says PASS.
    """
    phrases = [p for p in cfg.get("forbidden_phrases", []) if p.strip()]
    sources = ["config"] * len(phrases)

    declared = os.environ.get(FORBIDDEN_LIST_ENV, "").strip()
    origin = "env"
    if not declared:
        declared = str(cfg.get("forbidden_phrases_file", "") or "").strip()
        origin = "file"
    if not declared:
        return phrases, sources, None

    path = Path(declared)
    if not path.is_absolute():
        path = root / path
    extra = read_phrase_list(path)
    if extra is None:
        where = FORBIDDEN_LIST_ENV if origin == "env" else "forbidden_phrases_file"
        return [], [], (f"{where} points at {declared!r}, which cannot be read - the list "
                        "this check needs is not here, so it has NOT run")
    phrases += extra
    sources += [origin] * len(extra)
    return phrases, sources, None


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


def verify_file(rep, path, cfg, forbidden=None):
    doc = str(path)
    text, err = read_doc(path)
    if err:
        rep.record(doc, "file is readable UTF-8", 1, [err])
        return
    phrases, sources, void_reason = forbidden if forbidden else ([], [], None)
    lines = text.splitlines()
    check_tables(rep, doc, lines)
    check_headings(rep, doc, lines, cfg["check_numbered_headings"])
    if cfg["check_internal_refs"]:
        check_internal_refs(rep, doc, lines, text)
    if cfg["check_file_links"]:
        check_file_links(rep, doc, path, lines)
    check_placeholders(rep, doc, lines, cfg["placeholder_markers"])
    check_formatter_damage(rep, doc, lines, cfg)
    check_required_sections(rep, doc, lines, cfg["required_sections"])
    if void_reason:
        rep.record(doc, "forbidden phrases absent", 0, [], void_reason=void_reason)
    else:
        check_forbidden(rep, doc, lines, phrases, sources)
    check_line_length(rep, doc, lines, cfg["max_line_length"])
    scoped = in_size_scope(path, cfg["size_scope"])
    check_file_length(rep, doc, text, cfg["max_lines"], scoped, path)
    check_section_caps(rep, doc, lines, cfg["section_caps"], scoped)


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
MARKERS, DAMAGE = "no placeholders left", "no formatter damage"
LENGTH, SECT = "file length", "section length"


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
        Case("link to a file not on disk", checks(LINKS),
             writes(NL + "See [gone](no-such-file-here.md)." + NL),
             writes(NL + "See [here](there.md)." + NL, extra_file="there.md")),
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
    ]


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


def selftest(root: Path) -> int:
    print("SELFTEST - each check must fire on a bad document AND stay quiet on a good one")
    print()
    cfg = SELFTEST_CFG
    tmp = Path(tempfile.mkdtemp(prefix="verify_md_selftest_"))
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
        ok &= selftest_config(tmp, "md", "files", load_config, width=28)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print("\nSELFTEST: " + ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


# ------------------------------------------------------------------------------ main

def main(argv):
    root = Path.cwd()
    args = [a for a in argv[1:]]
    if "--write-config" in args:
        write_section(root, "md", DEFAULT_CONFIG, CONFIG_COMMENT)
        return 0
    if "--selftest" in args:
        return selftest(root)

    cfg = load_config(root)
    named = [a for a in args if not a.startswith("-")]
    targets = [Path(p) for p in (named or cfg["files"])]
    targets = [p for p in targets if p.exists()]

    if not targets:
        print("VOID: no documents to check. Name files, or list them under 'md.files' "
              "in verify.config.json. A run that checked nothing has not passed.")
        return 2

    # resolved ONCE, not per document: a missing list is a fact about this run, and
    # re-reading it per file would report the same accident as many separate findings.
    forbidden = resolve_forbidden(root, cfg)

    before = {p: sha256(p.read_bytes()).hexdigest() for p in targets}
    rep = Report()
    for p in targets:
        verify_file(rep, p, cfg, forbidden)

    print(rep.render(name_width=28))

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

    if cfg["report_cross_doc_refs"]:
        print()
        print("CROSS-DOCUMENT REFERENCES - a section sign resolves against ITS OWN file:")
        total = 0
        for p in targets:
            body, err = read_doc(p)
            if err:
                continue
            hits = list_cross_doc_refs(body.splitlines())
            for line, snippet in hits[:15]:
                print(f"  {p}:{line}  {snippet}")
            total += len(hits)
        print(f"  ({total} line(s) name another .md AND use a sign. Check each BY HAND - any whose")
        print("   number also exists here has already passed against the WRONG section.)")

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
    verdict = {0: "PASS", 1: "FAIL", 2: "VOID - a check could not run"}[rc]
    print(f"\n{len(targets)} document(s), {len(rep.rows)} checks")
    print("OVERALL: " + verdict)
    return rc


if __name__ == "__main__":
    sys.exit(main(sys.argv))
