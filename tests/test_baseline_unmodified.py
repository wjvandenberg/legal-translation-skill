# -*- coding: utf-8 -*-
"""BRANCH 0's ACCEPTANCE TEST — are the two committed trees byte-identical to the published
archives they came from?

"Commit both published trees unmodified" is branch 0's entire content, so it is worth proving
rather than asserting. This does not compare the working tree: it asks GIT what it is holding,
because the working tree is what was written and the object store is what will be cloned.
Those are the same thing only if line-ending translation is off, and on Windows it is on by
default -- which is what `.gitattributes` exists to prevent.

The archives live outside the repository. Where they are unavailable this test SKIPS and says
so; it never reports success for a comparison it did not make.

    uv run python tests/test_baseline_unmodified.py
"""
import hashlib
import io
import json
import subprocess
import sys
import zipfile
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parent.parent

# DELIBERATE divergences from the archive, named one by one. The trees stopped being
# byte-identical the moment a fix branch legitimately edited them, and the choice then was
# to delete this comparison or to keep it and declare what changed. Deleting it would have
# discarded the guarantee to avoid the paperwork: anything NOT named here is still an
# unexplained change and still fails.
_DIV = ROOT / "tests" / "baselines" / "baseline-divergences.json"
DIVERGENCES = (json.loads(_DIV.read_text(encoding="utf-8"))["divergences"]
               if _DIV.exists() else {})
ARCHIVES = ROOT.parent / "skills" / "legal-translation" / "PUBLICATION VERSIONS"
PAIRS = [("uk", "legal-translation (UK English).skill"),
         ("us", "legal-translation (US English).skill")]


def git(*args):
    r = subprocess.run(["git", *args], capture_output=True, cwd=ROOT)
    return r.stdout, r.returncode


print("=" * 92)
print("BRANCH 0 — are the committed trees byte-identical to the published archives?")
print("=" * 92)

missing = [a for _, a in PAIRS if not (ARCHIVES / a).exists()]
if missing:
    print(f"  SKIPPED — {len(missing)} archive(s) not reachable from this machine.")
    print("  This is a skip, not a pass. The comparison was not made.")
    sys.exit(0)

# What Git is actually holding, staged or committed.
out, rc = git("ls-files", "-s", "uk", "us")
if rc != 0 or not out.strip():
    print("  SKIPPED — nothing staged or committed under uk/ or us/ yet.")
    sys.exit(0)

blobs = {}
for line in out.decode("utf-8", "replace").splitlines():
    meta, path = line.split("\t", 1)
    blobs[path] = meta.split()[1]

total = bad = 0
for variant, archive in PAIRS:
    z = zipfile.ZipFile(ARCHIVES / archive)
    entries = {i.filename: z.read(i) for i in z.infolist() if not i.is_dir()}
    tracked = {p: h for p, h in blobs.items() if p.startswith(f"{variant}/")}

    only_git = sorted(set(tracked) - {f"{variant}/{n}" for n in entries})
    only_zip = sorted({n for n in entries} - {p[len(variant) + 1:] for p in tracked})

    mismatch, declared = [], []
    for name, data in entries.items():
        key = f"{variant}/{name}"
        if key not in tracked:
            continue
        total += 1
        # Git's blob id is sha1 over "blob <len>\0<content>". Recompute it from the archive
        # bytes: if the two agree, what Git holds IS the archive, byte for byte.
        want = hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()
        if want != tracked[key]:
            (declared if key in DIVERGENCES else mismatch).append(name)

    bad += len(mismatch) + len(only_git) + len(only_zip)
    print(f"\n  {variant}/   {len(tracked)} tracked · {len(entries)} in archive")
    print(f"      byte-identical : {len(tracked) - len(mismatch) - len(declared)}")
    if declared:
        print(f"      declared change: {len(declared)}  (recorded in "
              f"tests/baselines/baseline-divergences.json)")
        for d in declared:
            print(f"          {d}  — {DIVERGENCES[f'{variant}/{d}']['commit_subject'][:52]}")
    if mismatch:
        print(f"      UNDECLARED     : {len(mismatch)}")
        for m in mismatch[:8]:
            print(f"          {m}")
    if only_git:
        print(f"      IN GIT, NOT IN THE ARCHIVE: {len(only_git)}")
        for m in only_git[:8]:
            print(f"          {m}")
    if only_zip:
        print(f"      IN THE ARCHIVE, NOT IN GIT: {len(only_zip)}")
        for m in only_zip[:8]:
            print(f"          {m}")

print()
print("=" * 92)
if bad:
    print(f"FAIL — {bad} UNDECLARED discrepancy(ies). A tree changed without being recorded")
    print("       in tests/baselines/baseline-divergences.json. Declare it in the commit that")
    print("       MAKES it, with the reason — adding it afterwards to make this pass is how")
    print("       the guarantee is lost one file at a time.")
    sys.exit(1)
n_dec = len(DIVERGENCES)
print(f"PASS — {total - n_dec} of {total} files byte-identical to the published archives;")
print(f"       the other {n_dec} differ by DECLARED, recorded change.")
print("=" * 92)
