# -*- coding: utf-8 -*-
"""EVERY QUOTED CROSS-REFERENCE MUST RESOLVE TO A HEADING THAT EXISTS.

The instruction layer sends the operator from one section to another by quoting the target's
title: *see "Collapsing orthographic-only TC edits — MANDATORY" in Step 4*. When the quoted
title does not match any real heading, a reader who searches for it finds nothing, and the
always-loaded file is precisely where an operator goes to resolve doubt.

REGISTER ROW F40 -- "a mandatory rule points at the wrong rule" -- is this class. It was
recorded from ONE instance found by the blind desk review. This check exists because a second
instance turned up nine months later in a different pair of files, which means the class
needs an instrument rather than another pair of eyes.

WHY IT MUST HANDLE WRAPPED QUOTES, and this is not a detail. Both instances of the real
defect span a line break -- the step documents are hard-wrapped at about 78 columns, so a
quoted title routinely straddles two lines. A single-line regex finds 7 cross-references in
the UK tree and MISSES BOTH DEFECTS. A check that cannot see the thing it was written for is
the failure this project has logged eleven times, so the newline handling is the check.

MATCHING IS DELIBERATELY LENIENT ON DECORATION, STRICT ON WORDS. Headings carry `####`,
bold markers and trailing punctuation that a citation reasonably drops. Comparison is on the
lower-cased word sequence, so "Do not ask" resolves to "## Do not ask the user — these are
absolute defaults" by prefix. What it will not forgive is a word the heading does not have,
which is exactly how both real instances fail.

    uv run python tools/xref_check.py
    uv run python tools/xref_check.py --tree uk

Exit codes:  0 = every quoted cross-reference resolves · 1 = one or more dangle
             · 2 = the instrument could not run (nothing read -- VOID, not a pass)
"""
import io
import re
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parent.parent
TREES = ("uk", "us")

# A citation: see / See, then a double-quoted span that may run across a line break.
# [^"]{8,140} with DOTALL is what lets a hard-wrapped title match.
CITATION = re.compile(r'\bsee\s+"([^"]{8,140})"', re.I | re.S)


def words(s):
    """Lower-cased word sequence, with markdown decoration and heading marks removed."""
    s = re.sub(r"[`*_#]", " ", s)
    return [w for w in re.split(r"[^0-9a-z]+", s.lower()) if w]


# A target is not always a `#` heading. The package also labels numbered anti-drift items
# and pitfalls with a leading bold run -- `7. **Chat-mode discipline.**` -- and cites them
# the same way it cites headings. The first version of this check collected `#` lines only
# and reported that citation as dangling; it resolves perfectly well for a human, who finds
# the bold label by searching. That was a false positive in the CHECK, found by running it,
# and narrowing the check is the fix rather than editing a citation that was never wrong.
BOLD_LABEL = re.compile(r"^\s*(?:\d+\.|[-*])?\s*\*\*([^*]{4,90}?)\*\*")


def headings(tree):
    out = []
    root = ROOT / tree
    files = [root / "SKILL.md"] + sorted((root / "skill-docs").glob("*.md"))
    for f in files:
        rel = f.relative_to(root).as_posix()
        for line in f.read_text(encoding="utf-8").splitlines():
            if line.lstrip().startswith("#"):
                out.append((rel, line.strip(), words(line)))
                continue
            m = BOLD_LABEL.match(line)
            if m:
                out.append((rel, m.group(1).strip(), words(m.group(1))))
    return out


def resolves(cited, heads):
    """A citation resolves if its words are a PREFIX of some heading's words.

    Prefix, not equality: a citation may reasonably shorten a long heading, and several in
    this package do. It may not INVENT a word, and it may not omit one from the middle --
    both real defects quote a title whose words are not a prefix of any heading.
    """
    for rel, raw, hw in heads:
        if hw[:len(cited)] == cited:
            return rel, raw
    return None


def main():
    tree_arg = sys.argv[sys.argv.index("--tree") + 1] if "--tree" in sys.argv else None
    trees = (tree_arg,) if tree_arg else TREES

    print("=" * 100)
    print("CROSS-REFERENCE CHECK — does every quoted section title point at a real heading?")
    print("=" * 100)

    total = 0
    dangling = []
    for tree in trees:
        root = ROOT / tree
        heads = headings(tree)
        files = [root / "SKILL.md"] + sorted((root / "skill-docs").glob("*.md"))
        n = 0
        for f in files:
            body = f.read_text(encoding="utf-8")
            for m in CITATION.finditer(body):
                n += 1
                total += 1
                cited = words(m.group(1))
                if not cited:
                    continue
                if not resolves(cited, heads):
                    line = body[:m.start()].count("\n") + 1
                    dangling.append((tree, f.relative_to(root).as_posix(), line,
                                     " ".join(m.group(1).split())))
        print(f"\n  {tree}/   {len(heads):>4} heading(s) · {n:>3} quoted cross-reference(s)")

    # §5.1 — an instrument reporting on an empty set is not a pass.
    if total == 0:
        print("\n  VOID — 0 cross-references examined. The instrument read nothing.")
        return 2

    if dangling:
        print(f"\n  {len(dangling)} DANGLING — the quoted title matches no heading:\n")
        for tree, rel, line, txt in dangling:
            print(f"    {tree}/{rel}:{line}")
            print(f"      quotes: \"{txt}\"")
    print("\n" + "=" * 100)
    if dangling:
        print(f"  FAIL — {len(dangling)} of {total} cross-reference(s) point at nothing.")
        print("  A reader who searches the quoted string finds zero hits. Register row F40.")
        print("=" * 100)
        return 1
    print(f"  PASS — all {total} quoted cross-reference(s) resolve to a real heading.")
    print("=" * 100)
    return 0


if __name__ == "__main__":
    sys.exit(main())
