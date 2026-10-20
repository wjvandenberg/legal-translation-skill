# -*- coding: utf-8 -*-
"""EVERY POINTER INTO THE CHARTER STILL LANDS WHERE IT MEANT TO — register I-43's class, made a gate.

Code comments, docstrings, tests, the skills under .claude/skills/, the rules under .claude/rules/ and the example
config cite the charter, CLAUDE.md, by section NUMBER. When the charter's subsections are renumbered those pointers go
stale IN SILENCE: on 2026-09-09 one renumbering left eight stale numbers in seven places, found six weeks later only
by a review of an unrelated row (register I-43), and measuring for this test found two more. Only two of the eight
pointed at a number that no longer existed; the other six pointed at a number that still did, holding a different
section. So existence alone would have caught a quarter of the class. This test asks three questions of every pointer:

  1. EXISTS - the number is a `### N.N` heading of the charter today;
  2. SAME SECTION - the heading at that number is the title PINNED below for it. A renumbering, or a retitling, moves
     the title at a number, and every pointer to that number then fails with the old and new titles side by side:
     re-check each one, then re-pin. A cited number with no pin fails too, so a new pointer is checked once by a person;
  3. QUOTES WHAT IT CITES - where a pointer is followed by a quotation, the cited section holds those words
     (whitespace and emphasis normalised).

TWO SHAPES OF POINTER. ANCHORED: "CLAUDE.md 5.4", "`CLAUDE.md` §5.3", "CLAUDE.md section 6.4", "section 5.6 of
CLAUDE.md", "charter §5.6", "the charter's 5.3". BARE: a number on the same line as, or within three lines after, a
line naming CLAUDE.md or the charter - "6.4's rule", "5.12 prescribes" - which is how two of I-43's eight were
written; a bare number is held to questions 1 and 2. A bare number that is not a pointer at all (fixture text, an
XML version, another document's section) is a DECLARED exemption, with its reason, printed on every run - never a
silent skip; an exemption with no reason fails.

WHAT IT READS: every TRACKED file under tools/, tests/ and .claude/ (git ls-files, quotePath off), each file listed
and either read as text or counted as not text by extension - a denominator that cannot shrink in silence. It is VOID
(exit 2) if it read no file or the charter has no numbered heading.

WHAT IT CANNOT SEE: a pointer already wrong on the day its number was pinned - the pin records what a person checked,
so the pins were set only after the hand check that mended I-43's eight and two more this test found (2026-10-20 (3)).

RED FIRST: eleven built cases run before the real tree, each rule seen to fail on one and a clean case seen to pass;
and on every run the renumbering arm swaps the titles of the two most-cited sections in a copy of the charter and
requires every real pointer to either to fail as moved. --charter reads another copy of the charter instead.

    uv run --with lxml python tests/test_charter_pointers.py [--charter PATH]

Synthetic cases only; the real run reads this repository's own tracked files.
"""
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parent.parent
SCOPE = ["tools", "tests", ".claude"]
WINDOW = 3
_DOC = "CLAUDE" + ".md"   # built, so this file's own source holds no pointer of the shapes below
ANCHORED = [
    re.compile(re.escape(_DOC) + r"`?\s*§?\s*(\d\.\d{1,2})(?![\d.]*\d)"),
    re.compile(re.escape(_DOC) + r"`?\s+section\s+§?(\d\.\d{1,2})(?![\d.]*\d)"),
    re.compile(r"section\s+§?(\d\.\d{1,2})\s+of\s+(?:the\s+)?`?" + re.escape(_DOC)),
    re.compile(r"\bcharter(?:'s)?\s+§?\s*(\d\.\d{1,2})(?![\d.]*\d)"),
]
ANCHOR_LINE = re.compile(re.escape(_DOC) + r"|\bcharter\b")   # a word: never inside verify_charter_continuity
BARE = re.compile(r"(?<![\w./-])(?<!v)§?(\d\.\d{1,2})(?![\d.]*\d)\b")   # "§6.5" as much as "6.5"
# a quotation opens after a space, colon, dash or bracket - never straight after the number, which is how the end of
# one code string and the start of the next read as a quote on this test's first run (test_declared_language.py:250)
QUOTE = re.compile(r"""^(?:[^"“\n]{0,12}?[\s:(—-])["“]([^"”\n]{20,})["”]""")

# THE TITLE AT EACH CITED NUMBER, as it stood when every pointer to it was last checked by hand (2026-10-20 (3), after
# #163 mended I-43's eight). A failure here is the instruction: re-read each pointer it lists, fix the ones that moved,
# and only then change the pin.
PINNED = {
    "1.3": "The document set — what to read for what",
    "1.4": "Reading order for a new session",
    "1.5": "Two rules about reading, both bought with real time",
    "1.6": "Contents",
    "1.7": "The size class, and the cap this charter is held to",
    "2.1": "What the skill is, and who needs it",
    "2.2": "What this project is — the four goals",
    "2.3": "What has been done",
    "2.4": "What the evidence says — the seven things a new session must know",
    "2.5": "Decisions that still bind",
    "3.1": "The five phases",
    "3.2": "The phases in detail — phase 2 is the live one",
    "5.1": "The cycle — Explore → Plan → Code → Verify → Test → Commit",
    "5.2": "Branches, pull requests, and what \"done\" means",
    "5.3": "VERIFY — proving this change did what it claimed",
    "5.4": "TEST — proving nothing else broke",
    "5.5": "The instruments",
    "5.6": "Confidentiality",
    "5.7": "The artefact — domain rules and deliverable conventions",
    "5.8": "Working with this charter, and the session",
    "6.1": "The design principle, and what it is not",
    "6.2": "The skill tree today",
    "6.3": "What the build changes — the envisaged tree",
    "6.4": "The repository — what it holds, what never enters it, and what ships from it",
    "6.5": "`.claude/rules/` — the path-scoped rules this project has",
}
FILE_EXEMPT = {
    "tests/test_charter_pointers.py": "this test: its docstring, built cases and exemption list carry stale and "
                                      "non-section numbers ON PURPOSE, and its eleven built cases are what check it",
    "tools/verify_charter.py": "a house copy that checks a charter AGAINST THE HOUSE TEMPLATE, so every section number "
                               "it carries is the template's, never this charter's",
}
HIST = "a historical map: where each pre-2026-09-09 subsection went, keyed by its OLD number on purpose"
# Each exemption excuses ONE number: its text must contain it, and only a pointer inside that text is excused - a
# real pointer elsewhere on the same line is still judged. An exemption that matches nothing fails: it is dead.
LINE_EXEMPT = [
    ("tests/make_fixtures.py", "Clause 4.2", "fixture text: a clause number inside a synthetic document"),
    ("tests/test_checks_can_fail.py", 'xml version="1.0"', "an XML declaration's version, not a section"),
    ("tools/stepb_audit.py", "section 3.6 exists to CORRECT", "the build plan's section 3.6 (truncation), named in "
                                                              "the sentence before"),
    ("tools/vocabulary_census.py", "9.3's rows", "the build plan's section 9.3, the document this tool reads"),
    ("tools/verify_charter_continuity.py", '"5.14": "demoted', HIST),
    ("tools/verify_charter_continuity.py", '"5.15": "demoted', HIST),
    ("tools/verify_charter_continuity.py", '"5.16": "demoted', HIST),
    ("tools/verify_charter_continuity.py", '"6.6": "demoted', HIST),
    ("tools/verify_charter_continuity.py", '"3.4": ("Phase 4', "the same historical map, a pre-mapping number"),
    ("tools/verify_charter_continuity.py", "measured * 0.25", "a ratio, not a section"),
    ("tools/verify_md.py", "Round 0.5", "a house copy naming the charter interview's Round 0.5, not a section"),
]


def headings(charter):
    return {m.group(1): m.group(2).strip() for m in re.finditer(r"(?m)^### (\d\.\d{1,2}) (.+)$", charter)}


def section_text(charter, num):
    m = re.search(r"(?ms)^### " + re.escape(num) + r" .*?(?=^#{2,3} |\Z)", charter)
    return norm(m.group(0)) if m else ""


def norm(s):
    return " ".join(s.replace("*", "").replace("`", "").split())


def scan(charter, files, pinned, file_exempt, line_exempt):
    """(pointers, exempted, failures) over {path: text}. Pure: the built cases call it on synthetic input."""
    heads = headings(charter)
    pointers, exempted, failures, used = [], [], [], set()
    for path, reason in file_exempt.items():
        if not reason.strip():
            failures.append(f"{path}: a file exemption with no reason")
    for path, sub, reason in line_exempt:
        if not reason.strip():
            failures.append(f"{path}: the exemption for {sub!r} has no reason")
    for path, text in sorted(files.items()):
        if path in file_exempt:
            continue
        last = -99
        for n, line in enumerate(text.splitlines(), 1):
            if ANCHOR_LINE.search(line):
                last = n
            spans = []
            found = []
            for rx in ANCHORED:
                for m in rx.finditer(line):
                    spans.append(m.span())
                    found.append((m.group(1), "anchored", m.start(1), m.end()))
            if 0 <= n - last <= WINDOW:
                for m in BARE.finditer(line):
                    if not any(a <= m.start(1) < b for a, b in spans):
                        found.append((m.group(1), "bare", m.start(1), m.end()))
            for num, kind, start, end in found:
                ex = next(((i, r) for i, (p, s, r) in enumerate(line_exempt) if p == path and num in s
                           and any(o <= start < o + len(s) for o in _occurrences(line, s))), None)
                if ex is not None:
                    used.add(ex[0])
                    exempted.append((path, n, num, ex[1]))
                    continue
                pointers.append((path, n, num, kind))
                where = f"{path}:{n} cites {num} ({kind})"
                if num not in heads:
                    failures.append(f"{where}: the charter has no section {num}")
                    continue
                if num not in pinned:
                    failures.append(f"{where}: section {num} ('{heads[num]}') is cited but not pinned - check the "
                                    f"pointer, then pin it")
                elif heads[num] != pinned[num]:
                    failures.append(f"{where}: section {num} is now '{heads[num]}', pinned as '{pinned[num]}' - "
                                    f"re-check every pointer to it, then re-pin")
                q = QUOTE.match(line[end:]) if kind == "anchored" else None
                if q and norm(q.group(1)) not in section_text(charter, num):
                    failures.append(f"{where}: quotes words section {num} does not hold: {q.group(1)[:60]!r}")
    for i, (path, sub, _r) in enumerate(line_exempt):
        if i not in used:
            failures.append(f"{path}: the exemption for {sub!r} matches no pointer - it is dead; delete it")
    for path in file_exempt:
        if path not in files:
            failures.append(f"{path}: a file exemption for a file this run did not list - it is dead; delete it")
    return pointers, exempted, failures


def _occurrences(line, sub):
    i = line.find(sub)
    while i >= 0:
        yield i
        i = line.find(sub, i + 1)


# ---- RED FIRST: eleven built cases, each rule seen to fail on one, a clean case seen to pass --------------------------
CH = "# x\n\n### 5.4 Foo bar\n\nThe rule is: keep the list outside the repo.\n\n### 6.4 Baz\n\nText.\n"
PIN = {"5.4": "Foo bar", "6.4": "Baz"}
CASES = [
    ("clean: an anchored pointer, pinned, quoting what its section holds",
     CH, {"a.py": f'# see {_DOC} 5.4: "keep the list outside the repo" and so on'}, PIN, {}, [], 0),
    ("a section that does not exist", CH, {"a.py": f"# {_DOC} 5.12 keeps the trigger"}, PIN, {}, [], 1),
    ("a renumbered or retitled section", CH.replace("Foo bar", "Something else"),
     {"a.py": f"# {_DOC} 5.4 keeps the rules"}, PIN, {}, [], 1),
    ("a quotation its section does not hold", CH,
     {"a.py": f'# {_DOC} 5.4 says "words that appear nowhere in that section"'}, PIN, {}, [], 1),
    ("a BARE number after a charter line, naming a missing section", CH,
     {"a.py": f"# the gate, per {_DOC}\n# 5.12 prescribes a command"}, PIN, {}, [], 1),
    ("a cited number nobody pinned", CH, {"a.py": f"# {_DOC} 6.4 holds it"}, {"5.4": "Foo bar"}, {}, [], 1),
    ("an exemption with no reason", CH, {"a.py": f"# per {_DOC}\n# Clause 4.2 x"}, PIN, {},
     [("a.py", "Clause 4.2", "  ")], 1),
    ("a declared exemption is honoured, and printed", CH, {"a.py": f"# per {_DOC}\n# Clause 4.2 of a fixture"}, PIN,
     {}, [("a.py", "Clause 4.2", "fixture text")], 0),
    ("a dead exemption, matching no pointer", CH, {"a.py": f"# {_DOC} 5.4 x"}, PIN, {},
     [("a.py", "Clause 4.2", "fixture text")], 1),
    ("a stale pointer on a line with exempted text is still judged", CH,
     {"a.py": f"# per {_DOC}\n# Clause 4.2 here, and 5.12 beside it"}, PIN, {}, [("a.py", "Clause 4.2", "fixture")], 1),
    ("a bare pointer written with a section sign", CH, {"a.py": f"# per the charter\n# see §5.12 there"}, PIN, {}, [],
     1),
]
print("BUILT CASES (each must behave as stated before the real tree is read)")
built_bad = 0
for label, ch, files, pin, fex, lex, want in CASES:
    _p, _e, f = scan(ch, files, pin, fex, lex)
    good = len(f) == want
    built_bad += not good
    print(f"  {'ok  ' if good else 'FAIL'} {label}: {len(f)} failure(s), {want} wanted" + ("" if good else f"  {f}"))

# ---- THE REAL TREE ------------------------------------------------------------------------------------------------------
_cli = sys.argv[1:]
charter = (Path(_cli[1]) if _cli[:1] == ["--charter"] and len(_cli) == 2 else ROOT / _DOC).read_text(encoding="utf-8")
if _cli and not (_cli[:1] == ["--charter"] and len(_cli) == 2):
    print("usage: test_charter_pointers.py [--charter PATH]")
    sys.exit(2)
listed = subprocess.run(["git", "-c", "core.quotePath=false", "ls-files", "--", *SCOPE], cwd=str(ROOT),
                        capture_output=True, text=True, encoding="utf-8", check=True).stdout.splitlines()
files, not_text, unreadable = {}, Counter(), []
for rel in listed:
    try:
        files[rel] = (ROOT / rel).read_text(encoding="utf-8")
    except UnicodeDecodeError:
        not_text[Path(rel).suffix or "(none)"] += 1
    except OSError as exc:   # listed and not openable: said and failed, never folded into "not text"
        unreadable.append(f"{rel}: listed by git but could not be opened ({type(exc).__name__})")
print(f"\nREAL TREE: {len(listed)} tracked file(s) listed under {', '.join(SCOPE)}; {len(files)} read as text, "
      f"{sum(not_text.values())} not text ({dict(sorted(not_text.items()))}); {len(headings(charter))} numbered "
      f"heading(s) in the charter")
if not files or not headings(charter):
    print("VOID: nothing read, or the charter has no numbered heading - said rather than reported clean")
    sys.exit(2)
pointers, exempted, failures = scan(charter, files, PINNED, FILE_EXEMPT, LINE_EXEMPT)
failures = unreadable + failures
# finding 3: THE RENUMBERING, ON THE REAL POINTERS, EVERY RUN - the two most-cited numbers have their titles swapped in
# a copy of the charter, and every real pointer to either must then fail as moved, and nothing else.
top = [n for n, _c in Counter(num for _p, _n, num, _k in pointers).most_common(2)]
if len(top) == 2:
    a, b = (f"\n### {t} " for t in top)
    swapped = charter.replace(a, "\n### X.X ").replace(b, a).replace("\n### X.X ", b)
    _sp, _se, sf = scan(swapped, files, PINNED, FILE_EXEMPT, LINE_EXEMPT)
    want = sum(1 for _p, _n, num, _k in pointers if num in top)
    moved = [f for f in sf if " is now " in f and any(f" cites {t} (" in f for t in top)]
    good = len(moved) == want and len(sf) == len(failures) - len(unreadable) + want and want > 0
    print(f"  RENUMBERING ARM: {top[0]} and {top[1]} swapped in a copy - {len(moved)} of {want} pointer(s) to them "
          f"fail as moved, {len(sf) - len(moved)} other failure(s) {'(as on the real charter)' if good else ''}")
    if not good:
        failures.append("the renumbering arm: a swap of the two most-cited sections did not fail exactly their pointers")
else:
    failures.append("the renumbering arm could not run: fewer than two cited sections")
kinds = Counter(k for *_x, k in pointers)
print(f"  {len(pointers)} pointer(s) judged ({kinds['anchored']} anchored, {kinds['bare']} bare) in "
      f"{len({p for p, *_x in pointers})} file(s); {len(exempted)} exempted:")
for path, reason in FILE_EXEMPT.items():
    print(f"    file  {path}: {reason}")
for path, n, num, reason in exempted:
    print(f"    line  {path}:{n} {num}: {reason}")
for f in failures:
    print(f"  FAIL {f}")
print("\n" + "=" * 96)
total_bad = built_bad + len(failures)
print(f"CHARTER POINTERS: {len(pointers)} pointer(s), {total_bad} failure(s) - "
      + ("every pointer lands on the section it was checked against" if not total_bad else "see the lines above"))
print("=" * 96)
sys.exit(1 if total_bad else 0)
