# -*- coding: utf-8 -*-
"""SCAN THE TWO PUBLISHED TREES -- charter §5.4(a), the step that must be READ.

The trees are already public, so this is cleanup rather than containment. But committing
them unexamined would be the project asserting a check it had not made.

OUTPUT POLICY. Pattern INDEX and line number, never the matched text -- `leakage_scan.py`'s
policy, for its reason. `--show` reveals, and prints a warning that it has.

    uv run python temp/scan_trees.py
    uv run python temp/scan_trees.py --show
"""
import io
import os
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parent.parent
PRIV = ROOT.parent / "legal-translation-private"
SHOW = "--show" in sys.argv

TEXT_EXT = {".md", ".py", ".txt", ".json", ".yaml", ".yml"}


def load(env, default):
    p = Path(os.environ.get(env, default))
    return ([l.strip() for l in p.read_text(encoding="utf-8").splitlines()
             if l.strip() and not l.lstrip().startswith("#")] if p.exists() else None)


NAMES = load("LEAKAGE_LIST_PATH", PRIV / "leakage-names.txt")
DESC = load("CORPUS_DESCRIPTORS_FILE", PRIV / "corpus-descriptors.txt")
if NAMES is None or DESC is None:
    print("CONTROL VOID: a pattern list is missing. This scan has NOT run.")
    sys.exit(2)

NAME_RX = [(i, re.compile(p, re.I)) for i, p in enumerate(NAMES)]
DESC_RX = [(i, re.compile(p, re.I)) for i, p in enumerate(DESC)]

# The shape probes that found the two genuine artefacts in July, plus the ones that would
# find a real-document example: a titled personal name, a firm's template style name, an
# absolute path, an email.
SHAPES = [
    ("titled personal name",
     r"\b(?:Mr|Ms|Mrs|Dr|Prof|Sig|Sig\.ra|Sr|Sra|Herr|Frau|Dhr|Mevr)\.?\s+[A-Z][a-z]+"),
    ("email address", r"[\w.\-]+@[\w.\-]+\.\w{2,}"),
    ("absolute or home path",
     r"[A-Za-z]:\\[\w\-.]+(?:\\[\w\-. ]+)+|~[\\/][\w\-.]+(?:[\\/][\w\-. ]+)+"),
    # NARROWED after its first run. The original required only a capitalised sequence ending
    # in LLP/LLC, which fired three times on ordinary lexicon rows explaining what a US LLC
    # is -- a control with a visible false positive is one a reviewer starts skimming, which
    # is the failure mode §5.4(b) already names. A firm name needs a partner-name shape or an
    # explicit firm suffix, not a company-form abbreviation appearing in a definition.
    ("law-firm name shape",
     r"\b[A-Z][a-z]{2,}(?:\s+[A-Z][a-z]{2,}){0,2}\s+(?:&|and)\s+[A-Z][a-z]{2,}\s+"
     r"(?:LLP|Partners|Associates|Advocaten|Rechtsanwälte|Avvocati)\b"
     r"|\b[A-Z][a-z]{2,}\s+(?:LLP|Advocaten|Rechtsanwälte|Avvocati)\b"),
    # NO INLINE FIRM OR STYLE NAMES HERE, and the omission is the point. The first draft of
    # this probe hardcoded the firm template style names it was looking for -- which would
    # have put them into a committable file, the exact defect fixed in three scripts on
    # 2026-08-06, each of which had quoted a real string inside an explanatory comment.
    # It was also redundant: the 93-pattern name list already matches all of them, on one
    # pattern. A scanner carries no needle it can read from the list.
]
SHAPE_RX = [(lab, re.compile(p)) for lab, p in SHAPES]

per_tree = {}
for variant in ("uk", "us"):
    files = sorted(p for p in (ROOT / variant).rglob("*")
                   if p.is_file() and p.suffix.lower() in TEXT_EXT)
    hits = defaultdict(list)          # relpath -> [(kind, idx/label, line)]
    for p in files:
        rel = p.relative_to(ROOT / variant).as_posix()
        for n, line in enumerate(p.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            for i, rx in NAME_RX:
                if rx.search(line):
                    hits[rel].append(("name", f"#{i}", n))
            for i, rx in DESC_RX:
                if rx.search(line):
                    hits[rel].append(("descriptor", f"#{i}", n))
            for lab, rx in SHAPE_RX:
                if rx.search(line):
                    hits[rel].append(("shape", lab, n))
    per_tree[variant] = (len(files), hits)

for variant, (nfiles, hits) in per_tree.items():
    print()
    print("=" * 96)
    print(f"{variant}/   {nfiles} text files scanned   |   {len(hits)} file(s) with at least one hit")
    print("=" * 96)
    for rel in sorted(hits, key=lambda r: -len(hits[r])):
        kinds = Counter(k for k, _, _ in hits[rel])
        detail = ", ".join(f"{k} x{v}" for k, v in kinds.most_common())
        folder = rel.split("/")[0] if "/" in rel else "(root)"
        print(f"  {rel:<62} {detail}")
        if SHOW:
            for k, lab, n in hits[rel][:12]:
                print(f"        L{n} [{k} {lab}]")

print()
print("=" * 96)
print("WHERE THE HITS ARE -- by folder, because that is what decides whether it matters")
print("=" * 96)
for variant, (_, hits) in per_tree.items():
    by_folder = Counter()
    by_kind = Counter()
    for rel, hs in hits.items():
        by_folder[rel.split("/")[0] if "/" in rel else "(root)"] += 1
        for k, _, _ in hs:
            by_kind[k] += 1
    print(f"  {variant}: files by folder {dict(by_folder)} | hits by kind {dict(by_kind)}")
print("=" * 96)
if SHOW:
    print("  !! --show was used: matched positions are above. Do not paste this into a")
    print("     committable file.")
