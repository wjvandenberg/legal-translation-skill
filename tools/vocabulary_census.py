# -*- coding: utf-8 -*-
"""vocabulary_census.py - the house's words, held: no OLD word left in a swept document's living text.

Wouter, 2026-10-13 (DECISIONS-LOG.md (5)): this project's "step" became PHASE, its "branch" STEP, a "slice" a
SUB-STEP; living text takes the new words, dated records keep theirs. Each rename commit adds the document it swept
to SWEPT, with every record span it leaves alone and why. This is that commit's acceptance, and every later
commit's guard: an old word put back into living text turns it red.

WHAT IT COUNTS, in living text only: a project branch with its number (`branch 7`, `BRANCHES 15`, `branch D2`),
any `slice`, and the dropped Step C (`Step C`, `the verification run`). WHAT IT CANNOT COUNT, said so a green run is
not read as more: an old `step 3` meaning phase 3 - `step 3` is legitimate new text - so that half of a sweep is
proved by the sweep reversing itself byte-identical, never by this count; a bare `branch` with no number, which
is also git's word (branch protection, a PR per branch) and is judged by reading; and the skill's own `Step 5` left
unprefixed - once the project's steps are `step N`, a capitalised `Step 14` at a sentence's start is the project's,
so the two cannot be told apart by pattern, and `skill Step N` is held by reading.

SWEPT so far: CLAUDE.md, rename commit (b1), 2026-10-14; PLAN-2-step-b.md, rename commit (b2), 2026-10-19 - its split
Wouter's of that day: Part One's live text and Part Three's look-up are living; each option's verdict and build
record after its FOR THE BUILD brief, 9.3's rows and Parts Two and Four keep their words, the document's own front
matter declaring Parts Two to Four the record. evidence/REGISTER-findings.md, rename (c), 2026-10-21 - its split
Wouter's of that day: the header, the open rows and the clusters' live prose are living; THE ROW IS THE UNIT, so a
skill-finding row whose own text records its closure is a record whole, and so is an instrument row whose status
cell says fixed; a row still open, partly closed, deferred or standing, and a positive, are living whole. A span that
matches nothing, or a heading prefix that matches more than one heading, is refused as stale: a declaration that
quietly covers nothing would read as a clean census. So is a declared phrase that occurs nowhere in living text.

    uv run python tools/vocabulary_census.py             # every swept document; exit 0 clean, 1 an old word, 3 VOID
    uv run python tools/vocabulary_census.py --selftest  # red on a planted old word, green on one planted in a record
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SHAPES = [
    ("branch N", re.compile(r"\b(?:[Bb]ranch(?:es)?|BRANCH(?:ES)?)\s+(?:\d+|D[1-3])\b")),
    ("slice", re.compile(r"\b(?:[Ss]lices?|SLICES?)\b")),
    ("Step C", re.compile(r"\bStep C\b|\bverification run\b")),
]
# document -> record spans: (kind, anchor, why). kind: 'paragraph' (the block of non-blank lines that holds the
# anchor), 'section' (from the heading that IS the anchor to the next heading of the same or a higher level),
# 'line' (any line matching the anchor as a regex), 'heading' (as 'section', the ONE heading that starts with the
# anchor), 'brief-tail' (anchor (heading prefix, brief prefix): that section after the paragraph opening with the
# brief prefix - the brief itself stays living) and 'range' (anchor (start prefix, end prefix or None): from the ONE
# heading starting with the first up to the ONE starting with the second, or to the end). And 'phrase' (anchor an
# exact phrase): NOT a record - the line stays living and only that phrase is masked, for a word used in its own
# sense rather than the project's (a string "slice", a run that verifies), so a project word beside it still counts.
BRIEF = "> **FOR THE BUILD"
# the register's skill-finding rows whose own text records their closure, judged row by row by reading each status
# phrase (rename (c), 2026-10-21); a row that closes later is written in the new words and need not join this list
REGISTER_CLOSED = """A2 A16 A23 B1 B2 B3 B4 B5 B6 B7 B8 B9 B10 C1 C2 C4 C6 C7 C8 C9 C13 C14 C15 C17 C18 C19 C22 C28
C30 D3 E4 E15 E16 F6 F15 F16 F29 F43 F45 F47 F48 G5 G10 G11 H1 H2 H3 H4 J1 J2 L1 L5 S1 S2 S3 R1 R2 N1""".split()
SWEPT = {
    "CLAUDE.md": [
        ("paragraph", "**THE HOUSE'S WORDS, SINCE 2026-10-13**", "the mapping must name the old words it maps"),
        ("section", "### 2.3 What has been done", "the strands' dated record (ruling 3: records keep their words)"),
        ("line", r"^\| 20\d\d-\d\d-\d\d \|", "section 2.5's dated decisions keep the words they were taken in"),
        ("line", r"^\| \*\*`PLAN-3-opus5-migration\.md`\*\*", "names what the superseded Opus 5 plan holds"),
    ],
    "PLAN-2-step-b.md": [
        ("line", r"^\*\*SESSION PURPOSE — 20", "earlier sessions' purpose lines, each dated"),
        ("paragraph", "> **THIS DOCUMENT IS STEP 2'S PLAN FILE", "the 2026-09-10 rename and over-cap record"),
        ("paragraph", "> **Phase 3, Step B. THE EXPLORATION IS COMPLETE", "the 2026-08-05 preface: how it was made"),
        ("paragraph", "> **CORRECTED 2026-08-05, and the correction matters", "a dated correction"),
        ("paragraph", "> **AND A FOURTH, ADDED 2026-08-19", "a dated addition to the order, since discharged"),
        ("paragraph", "> **THIS GATE IS DISCHARGED, 2026-08-20", "the discharged gate, preserved as written"),
        ("paragraph", "**The four open defects in our own tooling belong to branch 1",
         "step 1's added scope, the deep audit's of 2026-08-05; step 1 is closed"),
        ("heading", "### The record, option by option", "the verdict record, option by option"),
        ("heading", "### 3.1 ", "the dropped fork's record: no brief"),
    ] + [("brief-tail", (f"### 3.{n} ", BRIEF), "the verdict and build record after the brief") for n in range(2, 12)] + [
        ("heading", "### 3.12 ", "a standing rule's record: no brief"),
        ("heading", "### 3.13 ", "a procedural record: no brief"),
        ("line", (r"^\| (?:\d|deferred: |standalone )", "### 9.3 "),
         "9.3's rows: their cells carry dated closure notes"),
        ("paragraph", "> **THIS LINE WAS STALE BY TWO", "a dated correction"),
        ("paragraph", "> **Regenerated 2026-08-05 by the deep audit", "a dated regeneration note"),
        ("range", ("## PART TWO ", "## PART THREE "), "Part Two, the case: the front matter declares it the record"),
        ("range", ("## PART FOUR ", None), "Part Four, the record"),
    ],
    "evidence/REGISTER-findings.md": [
        ("line", (r"^\| (?:" + "|".join(REGISTER_CLOSED) + r") \|", "## Register"),
         "skill-finding rows whose own text records their closure: the row is the unit"),
        ("line", (r"^\| I-\d+ \|.*\| fixed[^|]*\|\s*$", "## Measurement-instrument defects"),
         "instrument rows whose status cell says fixed"),
        ("phrase", "APPLY SLICES THE STRIPPED", "A20: string slicing, the defect's own mechanism"),
        ("phrase", "then slices *that*", "A20: string slicing"),
        ("phrase", "each span slices its neighbour", "A20: string slicing"),
        ("phrase", "the string apply slices", "A20: string slicing"),
        ("phrase", "OWN slice edge", "C16: a segment's slice of the string"),
        ("phrase", "onto the translated slice", "G9: a segment's slice of the string"),
        ("phrase", "*read-only* verification run", "I-7: a run that verifies, not the dropped Step C"),
    ],
}


def _level(line):
    return len(line) - len(line.lstrip("#"))


def _one_heading(lines, prefix):
    hits = [i for i, l in enumerate(lines) if l.startswith("#") and l.strip().startswith(prefix)]
    if len(hits) != 1:
        raise LookupError(f"heading prefix {prefix!r} matched {len(hits)} headings - it must match exactly one")
    return hits[0]


def _section_end(lines, i):
    j = i + 1
    while j < len(lines) and not (lines[j].startswith("#") and _level(lines[j]) <= _level(lines[i])):
        j += 1
    return j


def exempt_lines(lines, spans):
    out = set()
    for kind, anchor, _ in spans:
        if kind == "heading":
            i = _one_heading(lines, anchor)
            hits = list(range(i, _section_end(lines, i)))
            out |= set(hits)
        elif kind == "brief-tail":
            head, brief = anchor
            i = _one_heading(lines, head)
            j = _section_end(lines, i)
            k = next((x for x in range(i + 1, j) if lines[x].startswith(brief)), None)
            if k is None:
                raise LookupError(f"brief-tail {head!r} holds no paragraph opening {brief!r} - the declaration is stale")
            while k + 1 < j and lines[k + 1].strip():
                k += 1
            hits = list(range(k + 1, j))
            out |= set(hits)
        elif kind == "range":
            start, end = anchor
            a = _one_heading(lines, start)
            b = _one_heading(lines, end) if end else len(lines)
            hits = list(range(a, b))
            out |= set(hits)
        elif kind == "line":
            # a bare regex reads the whole document; (regex, heading prefix) only the ONE section under that heading
            # (code review, 2026-10-19: a document-wide row pattern also exempted rows of unrelated tables)
            rx, scope = anchor if isinstance(anchor, tuple) else (anchor, None)
            if scope is None:
                where = range(len(lines))
            else:
                i = _one_heading(lines, scope)
                where = range(i, _section_end(lines, i))
            hits = [i for i in where if re.search(rx, lines[i])]
            out |= set(hits)
        elif kind == "paragraph":
            # the paragraph must OPEN with the anchor: one that merely quotes it is living text (code review)
            hits = [i for i, l in enumerate(lines) if l.startswith(anchor) and (i == 0 or not lines[i - 1].strip())]
            for i in hits:
                a = i
                while a > 0 and lines[a - 1].strip():
                    a -= 1
                b = i
                while b + 1 < len(lines) and lines[b + 1].strip():
                    b += 1
                out |= set(range(a, b + 1))
        elif kind == "section":
            hits = [i for i, l in enumerate(lines) if l.strip() == anchor]
            level = len(anchor) - len(anchor.lstrip("#"))
            for i in hits:
                j = i + 1
                while j < len(lines) and not (lines[j].startswith("#") and
                                              len(lines[j]) - len(lines[j].lstrip("#")) <= level):
                    j += 1
                out |= set(range(i, j))
        if not hits:
            raise LookupError(f"record span {kind} {anchor!r} matched nothing - the declaration is stale")
    return out


def census(name, text, spans):
    lines = text.replace("\r\n", "\n").split("\n")
    skip = exempt_lines(lines, [s for s in spans if s[0] != "phrase"])
    living = [(n + 1, l) for n, l in enumerate(lines) if n not in skip]
    phrases = [anchor for kind, anchor, _ in spans if kind == "phrase"]
    seen = dict.fromkeys(phrases, 0)
    masked = []
    for n, l in living:
        for p in phrases:
            seen[p] += l.count(p)
            l = l.replace(p, " " * len(p))
        masked.append((n, l))
    stale = [p for p, c in seen.items() if not c]
    if stale:
        raise LookupError(f"phrase {stale[0]!r} occurs nowhere in living text - the declaration is stale")
    hits = [(n, label, m.group(0)) for n, l in masked for label, rx in SHAPES for m in rx.finditer(l)]
    return len(lines), len(living), hits


def closed_ids_stale(text):
    """REGISTER_CLOSED ids that do not start exactly one register row: the alternation's span is refused only when it
    matches nothing at all, so a single mistyped or renumbered id would otherwise cover nothing in silence."""
    lines = text.replace("\r\n", "\n").split("\n")
    return [i for i in REGISTER_CLOSED if sum(1 for l in lines if l.startswith(f"| {i} |")) != 1]


def run(docs):
    bad, examined = 0, 0
    for name, (text, spans) in docs.items():
        stale = closed_ids_stale(text) if name == "evidence/REGISTER-findings.md" else []
        if stale:
            raise LookupError(f"closed row id(s) {stale} start no row, or more than one - the declaration is stale")
        total, living, hits = census(name, text, spans)
        examined += 1
        nphrase = sum(1 for s in spans if s[0] == "phrase")
        kept = f", {nphrase} phrase(s) kept in their own sense" if nphrase else ""
        print(f"  {name}: {living} living line(s) of {total}, {len(spans) - nphrase} record span(s) declared{kept}, "
              f"{len(hits)} old word(s)")
        for n, label, word in hits:
            print(f"    line {n}: {label} - {word!r}")
        bad += len(hits)
    return examined, bad


def selftest():
    text = (ROOT / "CLAUDE.md").read_bytes().decode("utf-8")
    spans = SWEPT["CLAUDE.md"]
    lines = text.replace("\r\n", "\n").split("\n")
    living_at = next(i for i, l in enumerate(lines) if l.startswith("### 3.2 "))
    record_at = next(i for i, l in enumerate(lines) if l.strip() == "### 2.3 What has been done") + 2
    checks = []
    for where, at, want, word in (("living", living_at, 1, "a planted branch 7 line"),
                                  ("living", living_at, 1, "a planted slice line"),
                                  ("living", living_at, 1, "a planted Step C line"),
                                  ("record", record_at, 0, "a planted branch 7 line")):
        planted = list(lines)
        planted.insert(at + 1, word)
        _, _, hits = census("CLAUDE.md", "\n".join(planted), spans)
        base = census("CLAUDE.md", text, spans)[2]
        checks.append((f"{word!r} planted in {where} text is {'counted' if want else 'left alone'}",
                       len(hits) - len(base) == want))
    # the build plan, rename (b2): counted in a brief and in section 2; left alone in a brief's record tail, in Part
    # Two and in a 9.3 row; and each new span kind refused when its declaration has gone stale
    ptext = (ROOT / "PLAN-2-step-b.md").read_bytes().decode("utf-8")
    pspans = SWEPT["PLAN-2-step-b.md"]
    plines = ptext.replace("\r\n", "\n").split("\n")
    pbase = len(census("PLAN-2-step-b.md", ptext, pspans)[2])

    def at(pred):
        return next(i for i, l in enumerate(plines) if pred(l))
    head_32 = at(lambda l: l.startswith("### 3.2 "))
    brief_32 = next(i for i in range(head_32, len(plines)) if plines[i].startswith(BRIEF))
    order = at(lambda l: l.startswith("### The order, and what owns it"))
    tail_32 = at(lambda l: l.startswith("**Wouter's verdict, in his words:**") and "four slices" in l)
    part_two = at(lambda l: l.startswith("## PART TWO ")) + 2
    row_93 = at(lambda l: l.startswith("| 13 declared modes |"))
    for where, i, want, word in (("a brief", brief_32, 1, "> a planted branch 7 line"),
                                 ("section 2", order, 1, "a planted slice line"),
                                 ("a brief's record tail", tail_32, 0, "a planted branch 7 line"),
                                 ("Part Two", part_two, 0, "a planted slice line")):
        planted = list(plines)
        planted.insert(i + 1, word)
        got = len(census("PLAN-2-step-b.md", "\n".join(planted), pspans)[2]) - pbase
        checks.append((f"the plan: {word!r} planted in {where} is {'counted' if want else 'left alone'}", got == want))
    planted = list(plines)
    planted[row_93] += " branch 7"
    got = len(census("PLAN-2-step-b.md", "\n".join(planted), pspans)[2]) - pbase
    checks.append(("the plan: an old word added to a 9.3 row is left alone", got == 0))
    planted = list(plines)
    planted.insert(order + 1, "| 3 the planted row | branch 7 |")
    got = len(census("PLAN-2-step-b.md", "\n".join(planted), pspans)[2]) - pbase
    checks.append(("the plan: a 9.3-shaped row OUTSIDE 9.3 is counted (the row span is scoped)", got == 1))
    for label, bad_span in (("a brief-tail whose section has no brief", ("brief-tail", ("### 3.1 ", BRIEF), "x")),
                            ("a heading prefix that matches many headings", ("heading", "### 3.", "x")),
                            ("a range whose first heading is absent", ("range", ("## PART NINE ", None), "x"))):
        try:
            census("PLAN-2-step-b.md", ptext, [bad_span])
            checks.append((f"the plan: refused - {label}", False))
        except LookupError:
            checks.append((f"the plan: refused - {label}", True))
    stale = [("section", "### 9.9 No such heading", "a stale span")]
    try:
        census("CLAUDE.md", text, stale)
        checks.append(("a record span that matches nothing is refused", False))
    except LookupError:
        checks.append(("a record span that matches nothing is refused", True))
    # the register, rename (c): the row is the unit - an old word counted in an open row, an open instrument row and
    # a cluster cell; left alone in a closed row and a fixed instrument row; counted beside a declared phrase; and a
    # phrase that occurs nowhere refused
    rname = "evidence/REGISTER-findings.md"
    rtext = (ROOT / rname).read_bytes().decode("utf-8")
    rspans = SWEPT[rname]
    rlines = rtext.replace("\r\n", "\n").split("\n")
    rbase = len(census(rname, rtext, rspans)[2])

    def row(rid):
        return next(i for i, l in enumerate(rlines) if l.startswith(f"| {rid} |"))
    for where, i, want in (("an open row (A1)", row("A1"), 1), ("a closed row (A2)", row("A2"), 0),
                           ("an open instrument row (I-26)", row("I-26"), 1),
                           ("a fixed instrument row (I-2)", row("I-2"), 0),
                           ("a clusters-table cell (G)", next(i for i, l in enumerate(rlines)
                                                             if l.startswith("| **G** |")), 1),
                           ("the row beside a declared phrase (A20)", row("A20"), 1)):
        planted = list(rlines)
        head, sep, tail = planted[i].partition(" | ")
        planted[i] = head + sep + "a planted branch 7 " + tail
        got = len(census(rname, "\n".join(planted), rspans)[2]) - rbase
        checks.append((f"the register: an old word planted in {where} is {'counted' if want else 'left alone'}",
                       got == want))
    try:
        census(rname, rtext, rspans + [("phrase", "a phrase that occurs nowhere", "x")])
        checks.append(("the register: a declared phrase that occurs nowhere is refused", False))
    except LookupError:
        checks.append(("the register: a declared phrase that occurs nowhere is refused", True))
    nphrase = sum(1 for s in rspans if s[0] == "phrase")
    unmasked = len(census(rname, rtext, [s for s in rspans if s[0] != "phrase"])[2]) - rbase
    checks.append((f"the register: without its {nphrase} phrase declarations, exactly {nphrase} own-sense words count",
                   unmasked == nphrase))
    checks.append(("the register: every closed-row id starts exactly one row", closed_ids_stale(rtext) == []))
    checks.append(("the register: a mistyped closed-row id is refused",
                   closed_ids_stale(rtext.replace("| C30 |", "| C31 |", 1)) == ["C30"]))
    for label, good in checks:
        print(("  OK   " if good else "  XX   ") + label)
    ok = all(g for _, g in checks)
    print("selftest PASS" if ok else "selftest FAIL")
    return 0 if ok else 1


def main():
    if "--selftest" in sys.argv:
        return selftest()
    docs = {}
    for name, spans in SWEPT.items():
        p = ROOT / name
        try:
            docs[name] = (p.read_bytes().decode("utf-8"), spans)
        except (OSError, UnicodeDecodeError) as exc:
            print(f"  VOID  {name} could not be read ({type(exc).__name__})")
            return 3
    print("vocabulary census - the house's words in living text")
    try:
        examined, bad = run(docs)
    except LookupError as exc:
        print(f"  VOID  {exc}")
        return 3
    if examined == 0:
        print("VOID: no swept document examined")
        return 3
    print(f"{examined} document(s) examined, {bad} old word(s) in living text")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
