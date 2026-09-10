# -*- coding: utf-8 -*-
"""THE SECTION SIGNS THAT PASS AGAINST THE WRONG DOCUMENT.

CHECKER VERSION 1 (2026-08-24)

A `§` RESOLVES AGAINST THE FILE IT APPEARS IN. So `§4` written on a line about
`PLAN-2-step-b.md` points at section 4 of THE CHARTER, not of the build plan -- and because
the charter has a section 4, it resolves. Nothing fails. `verify_md.py`'s internal-refs check
reports PASS, because the checker cannot know which file a sign was meant for.

WHY THIS IS AN INSTRUMENT AND NOT A GREP. Phase 3b step 8 read all of them by hand: 19
candidates, of which **11 were genuinely misdirected, 1 was a wrong section of the RIGHT file
(the eleven structural questions are at 6.1, and a cell said 6.2), and 7 were false positives**
-- lines where the sign really does mean this charter and merely sits beside another document's
name. That reading cost a session. Without a record of WHICH were judged benign, the next
session re-reads all of them from zero, and the count moves every time a pointer is written.

So the judgement is recorded HERE, keyed on a distinctive fragment rather than a line number:
line numbers are perishable and were measured wrong in this project once already, sending a
session to edit the wrong lines.

  declared benign -> reported, not failed
  undeclared      -> FAILS. A new one is a new pointer somebody wrote without the rule in mind
  inside §7       -> reported and NEVER declarable. Section 7 is replaced every session, so a
                     declaration about it is stale by design. Read them each session instead

    uv run python tools/xdoc_signs.py
    uv run python tools/xdoc_signs.py --selftest
"""
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parent.parent

# `/` IS IN THE CLASS SINCE 2026-09-10, AND IT WAS A MEASURED COVERAGE LOSS, NOT A TIDY-UP. The
# layout convention moved four documents into `evidence/`, so the charter began citing them as
# `evidence/EVIDENCE-confidentiality.md`. Without the slash this pattern stopped recognising them
# as documents at all: the candidate count fell from 10 to 8, the two lines carrying a
# cross-document section sign went UNEXAMINED, and their DECLARED_BENIGN rows quietly became
# unused -- an undeclared coverage loss and a stale declaration at the same time, from one
# character. Nothing failed; the report simply got shorter, which is the shape that never gets
# questioned. A REPORT LABEL IS AN IDENTIFIER, and a basename stops being one the moment a
# document sits in a folder.
DOC_RE = re.compile(r"`([A-Za-z0-9_.\-/]+\.md)`")
SIGN_RE = re.compile(r"§\s*([0-9]+(?:\.[0-9]+)*)")

# (fragment that identifies the line, why the sign on it really does mean THIS file)
# Judged by reading, phase 3b step 8, 2026-08-24. Add a row only after reading the line.
DECLARED_BENIGN = [
    ("how the work is done",
     "'§5 here' -- the word 'here' is the disambiguator, and REGISTER-findings.md has no "
     "numbered sections at all"),
    ("the 199-file install ceiling",
     "§6.3 is this charter's envisaged-tree subsection, where the file ceiling is recorded. "
     "The SAME cell carried a bare §4 meaning PLAN-2-step-b.md's test-method section, which "
     "this check caught on the commit that wrote it -- it is now 'that document's section 4' "
     "in words, and it is the exact silent misdirection the rule exists to prevent: §4 of "
     "THIS file is the tech stack, so the sign would have resolved, against the wrong section"),
    ("D03 alone",
     "§5.5 is this charter's test corpus; section 11 of A3 is cited in words on the same line"),
    ("all eleven structural questions settled",
     "§6.1 is this charter's own answer table -- and this is the cell that said §6.2 until "
     "step 8 read it"),
    ("turned out to be classes rather than defects",
     "§2.4 is this charter's evidence section"),
    ("produced register cluster X",
     "§2.4 is this charter's evidence section; PLAN-2-step-b.md is named on the same line as "
     "Step B, and §6.4 sits on the next line without a filename"),
    ("This file rewritten to seven sections",
     "§5.6 is this charter's confidentiality section"),
    # REMOVED 2026-08-25 BY PHASE 12, and the tool is what noticed. The declared line lived in
    # §5.1's Explore row; that row now carries only what THIS project adds, because "never work
    # from a précis" is the auto-loaded house file's rule and was counted 2 -> 1. The sign went
    # with the sentence, so the declaration became stale -- and a stale declaration is a FAIL
    # here by design, since it would otherwise sit forever vouching for text nobody can find.
    # ADDED BY PHASE 3c STEP 9, WHICH IS THE MECHANISM STEP 8 RUNS LAST TO AVOID -- and it still
    # produced two, because step 9 came after step 8 in the same session. Both are §1.3 rows
    # saying what an evidence document received FROM this charter, so the sign names the SOURCE
    # section here, not a section of the document being described.
    ("the dated evidence behind",
     "§5.6 names the charter section this evidence document was split OUT of — the source, not a "
     "section of `EVIDENCE-confidentiality.md`, which has numbered sections of its own"),
    ("the twelve-row test-corpus listing",
     "BOTH signs now read §5.5 and that is not a typo: the test corpus and the measuring "
     "instruments were separate subsections until 2026-09-09 and are now two `####` blocks of "
     "one, so the row names the same charter section twice. Its own sections are cited "
     "elsewhere in words as 'section 1' and 'section 3'"),
    # ADDED 2026-09-09 BY THE SECTION MAPPING, AND THE TOOL IS WHAT NOTICED. Section 6.5 was
    # WRITTEN this session -- the template's 6.5 was the one subsection this charter had never
    # had -- and its table names each rule file beside the charter subsection it was relocated
    # FROM. That is a filename and a sign on one line, which is exactly the candidate shape, and
    # it went from 0 undeclared to 2 on the commit that added the table.
    ("the ten OOXML hard rules, each a production incident",
     "§5.7 is THIS charter's artefact subsection, which carries the pointer stub the rule file "
     "was relocated OUT of — the sign names the source, not a section of `ooxml.md`, which has "
     "ZERO numbered headings (measured, not assumed)"),
    ("of the seven skill-authoring conventions",
     "§5.7 is the same charter subsection, for the same reason: `skill-authoring.md` carries "
     "FIVE of its rules and likewise has ZERO numbered headings"),
    # ADDED 2026-09-10 BY THE CHARTER REDUCTION, and the tool is what noticed. Each is a
    # relocation pointer written this session: a rule file or companion document named beside a
    # sign that means THIS charter's own subsection, the source the block was relocated from.
    ("the seven measurement rules, forensic logging",
     "§5.5 is this charter's instruments subsection; `instruments.md` carries the rules "
     "relocated out of it — the twin column names the source, not a section of `instruments.md`"),
    ("the general lesson is §5.1's",
     "§5.1 is this charter's cycle-and-method section; `instruments.md` is named as the "
     "destination the corpus-blind-spot reasons moved to, not a section that owns §5.1"),
    ("the flip measurement is in",
     "§5.6 is this charter's confidentiality section; `DECISIONS-LOG.md` holds the public-flip "
     "measurement by date, not a section 5.6 of its own"),
]


def section_7_span(lines):
    """The line numbers occupied by section 7, which is exempt from declaration."""
    start = None
    for i, l in enumerate(lines, 1):
        if re.match(r"^## 7[. ]", l):
            start = i
            break
    return (start, len(lines)) if start else (None, None)


def candidates(text, self_name):
    lines = text.splitlines()
    own = {m.group(1) for m in
           (re.match(r"^#{2,4}\s+([0-9]+(?:\.[0-9]+)*)", l) for l in lines) if m}
    s7_start, s7_end = section_7_span(lines)
    out = []
    for i, line in enumerate(lines, 1):
        docs = [d for d in DOC_RE.findall(line) if d != self_name]
        signs = SIGN_RE.findall(line)
        if docs and signs:
            in_s7 = s7_start is not None and s7_start <= i <= s7_end
            out.append({"line": i, "docs": docs, "signs": signs, "text": line,
                        "in_section_7": in_s7,
                        "own": [s for s in signs if s in own]})
    return out


def run(target=None):
    path = Path(target) if target else ROOT / "CLAUDE.md"
    text = path.read_text(encoding="utf-8")
    cands = candidates(text, path.name)
    print("=" * 100)
    print(f"CROSS-DOCUMENT SECTION SIGNS in {path.name} — {len(cands)} candidate line(s)")
    print("=" * 100)
    undeclared, declared, in_s7 = [], [], []
    for c in cands:
        if c["in_section_7"]:
            in_s7.append(c)
            continue
        hit = next((why for frag, why in DECLARED_BENIGN if frag in c["text"]), None)
        (declared if hit else undeclared).append((c, hit))

    for c, why in declared:
        print(f"  [DECLARED] L{c['line']:<5} §{'/§'.join(c['signs'])}  beside {c['docs']}")
        print(f"             {why}")
    for c in in_s7:
        print(f"  [SECTION 7] L{c['line']:<5} §{'/§'.join(c['signs'])}  beside {c['docs']}")
        print(f"             replaced every session, so NOT declarable — read it now:")
        print(f"             {c['text'][:150]}")
    for c, _ in undeclared:
        print(f"  [FAIL] L{c['line']:<5} §{'/§'.join(c['signs'])}  beside {c['docs']}")
        print(f"         {c['text'][:160]}")
        print(f"         Read it. If the sign means ANOTHER document, rewrite it as "
              f'"section N of `that.md`" in words. If it means THIS file, add it to '
              f"DECLARED_BENIGN with the reason.")

    # THE DECLARATIONS ARE ABOUT THE CHARTER, so they are only stale-checked against it. Pointed
    # at another file, every one of them would report as stale and bury the real finding -- noise
    # that trains a reader to skim, which is this project's own objection to a bad control.
    stale = ([frag for frag, _ in DECLARED_BENIGN if frag not in text]
             if path.name == "CLAUDE.md" else [])
    print("-" * 100)
    print(f"  declared benign : {len(declared)}")
    print(f"  inside §7       : {len(in_s7)}  (read every session; a declaration would be stale)")
    print(f"  UNDECLARED      : {len(undeclared)}")
    if stale:
        print(f"  STALE DECLARATIONS, no longer in the file: {stale}")
    if not cands:
        print("  VOID — no candidate line was found at all. Either the file has none, or the "
              "pattern has drifted. Do not read this as a pass without checking which.")
        return 2
    ok = not undeclared and not stale
    print(f"\n{'PASS' if ok else 'FAIL'} — and this proves only that each sign was JUDGED, "
          f"never that the judgement was right.")
    return 0 if ok else 1


def selftest():
    ok = True

    def case(name, got, want):
        nonlocal ok
        good = got == want
        ok &= good
        print(f"  [{'OK  ' if good else 'FAIL'}] {name}: got {got!r}, want {want!r}")

    doc = (
        "## 1. A\n"
        "See `OTHER.md` §2 for the order.\n"
        "Plain prose with no sign at all.\n"
        "A §3 with no document named.\n"
        "## 7. Current status\n"
        "The handoff cites `OTHER.md` §1 today.\n"
    )
    c = candidates(doc, "CLAUDE.md")
    case("finds only lines with BOTH a document and a sign", [x["line"] for x in c], [2, 6])
    case("a sign with no document named is not a candidate",
         any(x["line"] == 4 for x in c), False)
    case("the §7 line is flagged as section 7",
         [x["in_section_7"] for x in c], [False, True])
    case("a self-reference does not count as another document",
         [x["line"] for x in candidates("See `CLAUDE.md` §2.\n", "CLAUDE.md")], [])
    case("section 7's span is found", section_7_span(doc.splitlines()), (5, 6))
    case("no span when there is no section 7",
         section_7_span(["## 1. A", "text"]), (None, None))
    case("every declared row carries a reason",
         all(len(w) > 20 for _, w in DECLARED_BENIGN), True)
    print(f"\nselftest {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        sys.exit(selftest())
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    sys.exit(run(args[0] if args else None))
