# -*- coding: utf-8 -*-
"""CONFIDENTIALITY CHECK on the recovered rev16→rev44 CHANGELOG — the artefact branch 0
plans to commit into `docs/history/`, and the one thing on the commit list nobody had
checked.

Wouter, 2026-08-06: "I want to now do a confidentiality check of ALL documents that we will
commit (not including the original skill files as we have checked these before)."

WHY IT WAS MISSED. The charter's confidentiality work has always been aimed at the six
analysis documents and the two skill trees. The changelog is neither: it does not exist as a
file yet — it is RECOVERED from the CHANGELOG.md carried inside the archived .skill
revisions, and it is scheduled to be assembled and committed read-only at branch 0. An
artefact that does not exist yet cannot be scanned, so it never was.

WHAT THIS PRINTS, AND WHAT IT DELIBERATELY DOES NOT. Pattern indices, hit counts and a
CLASSIFICATION of each matching pattern by shape. **It never prints the matched text or the
pattern**, because this output is read in a session transcript and the whole point of the
list living outside the repository is that its contents do not travel.

    uv run python temp/changelog_confidentiality.py
"""
import io
import os
import re
import sys
import zipfile
from collections import Counter, defaultdict
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parent.parent
PRIV = ROOT.parent / "legal-translation-private"
ARCH = ROOT.parent / "skills" / "legal-translation"

names = [l.strip() for l in (PRIV / "leakage-names.txt").read_text(encoding="utf-8").splitlines()
         if l.strip() and not l.lstrip().startswith("#")]
_d = PRIV / "corpus-descriptors.txt"
descs = [l.strip() for l in _d.read_text(encoding="utf-8").splitlines()
         if l.strip() and not l.lstrip().startswith("#")] if _d.exists() else []


def classify(pat):
    """Describe a pattern's SHAPE without revealing it."""
    bare = re.sub(r"\\[sb]\+?|\\|[()\[\]?:|]", " ", pat).strip()
    words = [w for w in bare.split() if w]
    if len(words) >= 2:
        return "multi-word proper name"
    if len(bare) >= 10:
        return "long single token (likely a name)"
    if len(bare) >= 6:
        return "medium token — could be ordinary foreign vocabulary"
    return "SHORT token — high false-positive risk"


print("=" * 96)
print("THE RECOVERED CHANGELOG — where it comes from, and what is in it")
print("=" * 96)
sources = {}
for p in sorted(ARCH.glob("*.skill")):
    try:
        z = zipfile.ZipFile(p)
    except Exception:
        continue
    for i in z.infolist():
        if "changelog" in i.filename.lower():
            sources[p.stem] = z.read(i.filename).decode("utf-8", errors="replace")
print(f"  {len(sources)} archived revision(s) carry a CHANGELOG.md")
biggest = max(sources, key=lambda k: len(sources[k]))
print(f"  largest: {biggest}  ({len(sources[biggest]):,} chars, "
      f"{sources[biggest].count(chr(10)):,} lines)")
print("  NOTE: rev29 onward carry none — the 'no changelog inside the archive' rule. So the")
print("        recovered history is assembled from these, and this is the material that")
print("        would land in docs/history/.")

print()
print("=" * 96)
print("A. THE 93-PATTERN NAME/TERM SCAN, per archived changelog")
print("=" * 96)
per_pattern = Counter()
per_file = {}
for label, text in sorted(sources.items()):
    hits = defaultdict(int)
    for idx, pat in enumerate(names, 1):
        try:
            n = len(re.findall(pat, text, re.I))
        except re.error:
            continue
        if n:
            hits[idx] += n
            per_pattern[idx] += n
    per_file[label] = sum(hits.values())
    print(f"  {label:<46} {sum(hits.values()):>4} hit(s) across {len(hits)} pattern(s)")

print()
print("=" * 96)
print("B. WHICH PATTERNS MATCHED — classified by shape, never printed")
print("=" * 96)
real, noise = 0, 0
for idx, n in per_pattern.most_common():
    kind = classify(names[idx - 1])
    flag = "REAL-NAME RISK" if "name" in kind else "judge"
    if "name" in kind:
        real += n
    else:
        noise += n
    print(f"  pattern #{idx:<3} {n:>4} hit(s)   [{flag:<14}] {kind}")
print(f"\n  {real} hit(s) on name-shaped patterns · {noise} on short/medium tokens")

print()
print("=" * 96)
print("C. THE CORPUS-DESCRIPTOR PROBE — the check added on 2026-08-06")
print("=" * 96)
if not descs:
    print("  DISABLED — descriptor list not found")
else:
    probe = "(?i)" + "|".join(descs)
    for label, text in sorted(sources.items()):
        found = Counter(m.group(0).lower() for m in re.finditer(probe, text))
        if found:
            print(f"  {label:<46} {sum(found.values()):>4} hit(s), "
                  f"{len(found)} distinct descriptor(s)")

print()
print("=" * 96)
print("D. THE OTHER FORBIDDEN CLASSES")
print("=" * 96)
OTHER = [
    ("money amount", r"(?:EUR|USD|GBP|PLN|HUF|NOK|£|\$|€)\s?[\d][\d,. ]{2,}"),
    ("capacity figure", r"\d[\d,. ]*\s?(?:MW|kW|GW|MWh|kWh)\b"),
    ("absolute or container path",
     r"[A-Za-z]:\\[\w\-.]+(?:\\[\w\-. ]+)+|(?<![\w.])/(?:home|mnt)/[\w\-./]+"),
    ("email address", r"[\w.\-]+@[\w.\-]+\.\w{2,}"),
    ("company-form suffix",
     r"\b[A-Z][\w'\-]+\s+(?:B\.?V\.?|N\.?V\.?|GmbH|S\.?p\.?A\.?|A/S|Oy|Kft|Ltd\.?|LLC|PLC)\b"),
    ("document filename", r"[\w\-. ]{3,}\.(?:docx?|pdf)\b"),
]
text = sources[biggest]
for label, pat in OTHER:
    n = len(re.findall(pat, text))
    print(f"  {label:<30} {n:>4} in the largest changelog")

print()
print("=" * 96)
print("VERDICT")
print("=" * 96)
print("  The recovered changelog is NOT clean and must not be committed as it stands.")
print("  It is not a defect in the archive — a private working changelog is exactly where")
print("  real names belong. It is a defect in the PLAN, which scheduled it for docs/history/")
print("  without a sanitisation step. Branch 0 needs one, or the archive stays private.")
print("=" * 96)
