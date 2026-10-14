# -*- coding: utf-8 -*-
"""vocabulary_census.py - the house's words, held: no OLD word left in a swept document's living text.

Wouter, 2026-10-13 (DECISIONS-LOG.md (5)): this project's "step" became PHASE, its "branch" STEP, a "slice" a
SUB-STEP; living text takes the new words, dated records keep theirs. Each rename commit adds the document it swept
to SWEPT, with every record span it leaves alone and why. This is that commit's acceptance, and every later
commit's guard: an old word put back into living text turns it red.

WHAT IT COUNTS, in living text only: a project branch with its number (`branch 7`, `BRANCHES 15`, `branch D2`),
any `slice`, and the dropped Step C (`Step C`, `the verification run`). WHAT IT CANNOT COUNT, said so a green run is
not read as more: an old `step 3` meaning phase 3 - `step 3` is legitimate new text - so that half of a sweep is
proved by the sweep reversing itself byte-identical, never by this count; and a bare `branch` with no number, which
is also git's word (branch protection, a PR per branch) and is judged by reading.

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
# 'line' (any line matching the anchor as a regex).
SWEPT = {
    "CLAUDE.md": [
        ("paragraph", "**THE HOUSE'S WORDS, SINCE 2026-10-13**", "the mapping must name the old words it maps"),
        ("section", "### 2.3 What has been done", "the strands' dated record (ruling 3: records keep their words)"),
        ("line", r"^\| 20\d\d-\d\d-\d\d \|", "section 2.5's dated decisions keep the words they were taken in"),
        ("line", r"^\| \*\*`PLAN-3-opus5-migration\.md`\*\*", "names what the superseded Opus 5 plan holds"),
    ],
}


def exempt_lines(lines, spans):
    out = set()
    for kind, anchor, _ in spans:
        if kind == "line":
            hits = [i for i, l in enumerate(lines) if re.search(anchor, l)]
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
    skip = exempt_lines(lines, spans)
    living = [(n + 1, l) for n, l in enumerate(lines) if n not in skip]
    hits = [(n, label, m.group(0)) for n, l in living for label, rx in SHAPES for m in rx.finditer(l)]
    return len(lines), len(living), hits


def run(docs):
    bad, examined = 0, 0
    for name, (text, spans) in docs.items():
        total, living, hits = census(name, text, spans)
        examined += 1
        print(f"  {name}: {living} living line(s) of {total}, {len(spans)} record span(s) declared, "
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
    stale = [("section", "### 9.9 No such heading", "a stale span")]
    try:
        census("CLAUDE.md", text, stale)
        checks.append(("a record span that matches nothing is refused", False))
    except LookupError:
        checks.append(("a record span that matches nothing is refused", True))
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
