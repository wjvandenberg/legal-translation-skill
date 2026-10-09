"""A3 final check: every Markdown table row in the committable files is contiguous
with a header + delimiter row, and every row has the header's column count.

This is the check that would have caught the eleven non-rendering register rows.

WHAT IT READS. The files named on the command line, opened as given. NAMED NONE, it reads the
project's documents -- the same set `tools/publication_check.py` reads: the six core names, kept
BY NAME so a rename is noticed, then the globs, so a document added later is checked without
anybody remembering to add it here. `tests/test_md_tables.py` fails if the two lists drift apart.
It prints FILES READ with the count and every path before any verdict.

WHY A BARE RUN NO LONGER PASSES (register I-39, 2026-10-09). It summed its verdicts over the
arguments, so a run naming no file summed over nothing and printed CLEAN with exit 0 -- and the
session document runner called it exactly that way, so two breaks in the register, twenty-one rows
rendering as loose text, went unreported behind a green row. A named file it could not open was
the same failure from the other end: a traceback and exit 1, indistinguishable by exit code from a
broken table. A check that opened no file has established nothing, and says so.

    uv run python tools/md_tables.py                      # the project's documents
    uv run python tools/md_tables.py <file> [<file> ...]  # exactly these

EXIT CODES. 0 = every file read, no problem found. 1 = every file read, problems found.
2 = VOID: no file was read, a core document is gone, or a file could not be opened or decoded --
each named, never skipped. Problems in the files that WERE read are still printed.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# THE SAME TWO LISTS AS tools/publication_check.py, COPIED BECAUSE THAT SCRIPT SCANS AT IMPORT
# TIME AND CANNOT BE IMPORTED. tests/test_md_tables.py reads both from source and fails on any
# difference, so a document added to one is never silently missing from the other.
CORE = ["CLAUDE.md", "evidence/REGISTER-findings.md", "evidence/EVIDENCE-a3-structure.md", "PLAN-2-step-b.md",
        "DECISIONS-LOG.md", "PLAN-3-opus5-migration.md"]
DISCOVER = ["README.md", "EVIDENCE-*.md", "REGISTER-*.md", "PLAN-*.md",
            "evidence/EVIDENCE-*.md", "evidence/REGISTER-*.md", "evidence/PLAN-*.md",
            ".claude/rules/*.md", ".claude/skills/*/SKILL.md", "tests/README.md"]

PIPE = re.compile(r"(?<!\\)\|")
# A delimiter must contain at least one hyphen. Without that requirement the pattern also
# matched `| | |` -- a legitimate header row whose cells are empty -- so the header was read
# as a second delimiter and the whole table reported as four orphan rows under a delimiter
# with no header. Every renderer treats `| | |` as a header; so does this now.
DELIM = re.compile(r"^\|[\s:|-]*-[\s:|-]*\|$")


def check(path: str, text: str | None = None) -> int:
    lines = (open(path, encoding="utf-8").read() if text is None else text).split("\n")
    hdr_width = None
    prev_row = None
    bad = orphan = tables = 0
    # A CAPPED REPORT MUST SAY IT IS CAPPED. Only the first five orphans and eight mismatches are
    # printed in full, and until 2026-10-09 the rest were simply dropped while the summary counted
    # them: twelve mismatches in one lexicon printed eight, and the four unshown were a SECOND,
    # unrelated fault under another header. The rest are now named by line number.
    hidden_orphan, hidden_width = [], []
    for i, raw in enumerate(lines, 1):
        st = raw.strip()
        if st.startswith("|") and st.endswith("|"):
            if DELIM.match(st):
                if prev_row is None:
                    print(f"  {path}:{i} delimiter with no header above")
                    bad += 1
                    continue
                hdr_width = len(PIPE.findall(prev_row))
                if len(PIPE.findall(st)) != hdr_width:
                    print(f"  {path}:{i} delimiter width mismatch")
                    bad += 1
                tables += 1
                prev_row = st
                continue
            if hdr_width is None:
                # could be the header line itself; only a problem if no delimiter follows
                nxt = lines[i].strip() if i < len(lines) else ""
                if not DELIM.match(nxt):
                    orphan += 1
                    if orphan <= 5:
                        print(f"  {path}:{i} ORPHAN row (no header/delimiter): {st[:70]}")
                    else:
                        hidden_orphan.append(i)
            elif len(PIPE.findall(st)) != hdr_width:
                bad += 1
                if bad <= 8:
                    print(f"  {path}:{i} width {len(PIPE.findall(st))} vs header "
                          f"{hdr_width}: {st[:70]}")
                else:
                    hidden_width.append(i)
            prev_row = st
        else:
            if not st:
                hdr_width = None
                prev_row = None
            else:
                prev_row = None
    if hidden_orphan:
        print(f"  {path}: ... and {len(hidden_orphan)} more ORPHAN row(s) not shown, at lines "
              f"{', '.join(map(str, hidden_orphan))}")
    if hidden_width:
        print(f"  {path}: ... and {len(hidden_width)} more width mismatch(es) not shown, at lines "
              f"{', '.join(map(str, hidden_width))}")
    print(f"{path}: {tables} tables, {bad} width mismatches, {orphan} orphan rows")
    return bad + orphan


def targets(argv):
    """(label, path to open) for every file to read, and the core names that are gone. Named
    files are opened as given and labelled as given; discovered ones are labelled from the
    root, so a label never depends on the folder the command was typed in."""
    if argv:
        # A file named twice is read once: the count printed is a denominator, and a doubled
        # one disagrees with any population enumerated beside it.
        named, seen = [], set()
        for a in argv:
            key = Path(a).resolve()
            if key not in seen:
                seen.add(key)
                named.append((a, Path(a)))
        return named, []
    gone = [n for n in CORE if not (ROOT / n).exists()]
    out = [n for n in CORE if (ROOT / n).exists()]
    for g in DISCOVER:
        for p in sorted(ROOT.glob(g)):
            rel = p.relative_to(ROOT).as_posix()
            if rel not in out:
                out.append(rel)
    return [(n, ROOT / n) for n in out], gone


if __name__ == "__main__":
    # A row snippet holding a character the console cannot encode must not kill the report: on a
    # cp1252 stdout one arrow in an orphan row raised UnicodeEncodeError, exit 1, and the
    # findings were lost behind a traceback. Replace the character; never the verdict.
    sys.stdout.reconfigure(errors="replace")
    todo, gone = targets(sys.argv[1:])
    texts, unreadable = [], []
    for label, path in todo:
        try:
            texts.append((label, path.read_text(encoding="utf-8")))
        except (OSError, UnicodeDecodeError) as e:
            unreadable.append((label, f"{type(e).__name__}: {e}"))
    print(f"FILES READ: {len(texts)}")
    for label, _ in texts:
        print(f"    {label}")
    if gone:
        print(f"CORE DOCUMENT(S) NAMED HERE BUT NOT ON DISK -- renamed or moved? {gone}")
    for label, why in unreadable:
        print(f"COULD NOT READ: {label} -- {why}")
    total = sum(check(label, text) for label, text in texts)
    if not texts or gone or unreadable:
        print(f"\nVOID -- {'no file was read' if not texts else 'not every file was read'}; "
              f"this is not a pass. {total} problem(s) in the {len(texts)} file(s) that were read.")
        sys.exit(2)
    print(f"\n{'CLEAN' if total == 0 else 'PROBLEMS: %d' % total}")
    sys.exit(1 if total else 0)
