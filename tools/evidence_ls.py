# -*- coding: utf-8 -*-
"""LIST AN EVIDENCE FOLDER WITHOUT PRINTING WHAT IS IN IT.

WHY THIS EXISTS. On 2026-08-11 a session ran `ls` and `find` over the sibling logs folder to
work out how it was laid out, and the output printed real corpus filenames carrying
counterparty and personal names straight into the conversation transcript. Nothing was
committed and no scanner could ever have caught it: CLAUDE.md 6.5 says session metadata is
reachable by neither the scanners nor the location rule, so there is no after-the-fact
control at all. Prevention is the only control, and 6.5's rule -- "any glob over an evidence
folder must be explicit about which files it expects" -- had been read that same morning and
broken anyway. That is this project's standing argument that prose is not a control.

So: `tools/hooks/evidence_guard.py` blocks the name-emitting commands, and this is the
sanctioned way to do the thing that was legitimately needed -- understand a folder's SHAPE.
A block with no alternative just gets worked around, and then you have a control nobody
believes, which is the failure mode already diagnosed in the skill's own validators.

WHAT IT PRINTS: counts, extensions, size buckets, depth, and corpus doc-ids (D01..D11), which
name a FILE's place in the corpus and never the instrument or the parties -- the same
distinction CLAUDE.md 5.4 already draws for the technical character of a file.

WHAT IT NEVER PRINTS: a filename, a stem, a directory name below the root you gave it, or any
file content. There is no --show, no --verbose and no --names. Adding one would defeat the
tool; if you need a specific file, name it directly and read it with a script whose own
output policy you have checked.

    uv run python tools/evidence_ls.py ../legal-translation-logs/A1
    uv run python tools/evidence_ls.py ../legal-translation-logs/A1 --depth 2
"""
import argparse
import re
import sys
from collections import Counter
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DOC_ID = re.compile(r"\bD\d{2}B?\b")
BUCKETS = [(1_024, "< 1 KB"), (32_768, "1–32 KB"), (1_048_576, "32 KB – 1 MB"),
           (float("inf"), "> 1 MB")]


def bucket(n):
    for limit, label in BUCKETS:
        if n < limit:
            return label
    return "> 1 MB"


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("path")
    ap.add_argument("--depth", type=int, default=1,
                    help="how many directory levels to summarise separately (default 1)")
    args = ap.parse_args()

    root = Path(args.path)
    if not root.exists():
        print(f"  path does not exist: {root}")
        return 2
    if not root.is_dir():
        print(f"  {root} is a file, {root.stat().st_size} bytes. "
              f"Nothing else is printed by design.")
        return 0

    files = [p for p in root.rglob("*") if p.is_file()]
    if not files:
        # An instrument reporting on an empty set is not a pass (CLAUDE.md 5.1).
        print(f"  VOID — 0 files under {root}. Nothing to describe.")
        return 2

    exts, sizes, docs, groups = Counter(), Counter(), Counter(), Counter()
    for p in files:
        exts[p.suffix.lower() or "(no extension)"] += 1
        sizes[bucket(p.stat().st_size)] += 1
        m = DOC_ID.search(str(p))
        if m:
            docs[m.group(0)] += 1
        rel = p.relative_to(root).parts
        groups["/".join(rel[:args.depth]) if len(rel) > args.depth else "(at this level)"] += 1

    print("=" * 78)
    print(f"  SHAPE OF {root}")
    print("=" * 78)
    print(f"\n  {len(files)} file(s)\n")

    print("  BY EXTENSION")
    for e, n in exts.most_common():
        print(f"    {n:>6}  {e}")

    print("\n  BY SIZE")
    for _, label in BUCKETS:
        if sizes[label]:
            print(f"    {sizes[label]:>6}  {label}")

    if docs:
        print("\n  BY CORPUS DOC-ID  (a file's place in the corpus, never the parties)")
        for d, n in sorted(docs.items(), key=lambda kv: (len(kv[0]), kv[0])):
            print(f"    {n:>6}  {d}")

    named = {k: v for k, v in groups.items() if k != "(at this level)"}
    print(f"\n  BY SUBDIRECTORY, depth {args.depth} — COUNT ONLY, names withheld")
    print(f"    {len(named)} subdirector{'y' if len(named) == 1 else 'ies'}, "
          f"holding {sum(named.values())} file(s)")
    if groups["(at this level)"]:
        print(f"    {groups['(at this level)']} file(s) sit directly in the root")
    if named:
        counts = sorted(named.values(), reverse=True)
        print(f"    files per subdirectory: max {counts[0]}, min {counts[-1]}, "
              f"median {counts[len(counts) // 2]}")

    print()
    print("=" * 78)
    print("  Names are withheld by design. If you need one specific file, name it and read")
    print("  it with a script whose own output policy you have checked — see")
    print("  tools/gate_replay.py, which reads these logs and prints counts only.")
    print("=" * 78)
    return 0


if __name__ == "__main__":
    sys.exit(main())
