# -*- coding: utf-8 -*-
"""THE SECTION SIGNS THAT PASS AGAINST THE WRONG DOCUMENT.

CHECKER VERSION 1 (2026-08-24)

A `§` RESOLVES AGAINST THE FILE IT APPEARS IN. So `§4` written on a line about
`STEP-B-ANALYSIS.md` points at section 4 of THE CHARTER, not of the build plan -- and because
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

DOC_RE = re.compile(r"`([A-Za-z0-9_.\-]+\.md)`")
SIGN_RE = re.compile(r"§\s*([0-9]+(?:\.[0-9]+)*)")

# (fragment that identifies the line, why the sign on it really does mean THIS file)
# Judged by reading, phase 3b step 8, 2026-08-24. Add a row only after reading the line.
DECLARED_BENIGN = [
    ("how the work is done",
     "'§5 here' -- the word 'here' is the disambiguator, and FINDINGS-REGISTER.md has no "
     "numbered sections at all"),
    ("rests on **D03 alone**",
     "§5.7 is this charter's test corpus; A3 is cited on the same line as 'section 11' in words"),
    ("all eleven structural questions settled",
     "§6.1 is this charter's own answer table -- and this is the cell that said §6.2 until "
     "step 8 read it"),
    ("turned out to be classes rather than defects",
     "§2.5 is this charter's evidence section"),
    ("**Step 1** is the git history",
     "§6.4 is this charter's repository section"),
    ("This file rewritten to seven sections",
     "§5.4 is this charter's confidentiality section"),
    ("Never work from a précis",
     "§1.5 is this charter's reading rule; the same line's other signs were rewritten in words"),
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
