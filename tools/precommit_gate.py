# -*- coding: utf-8 -*-
"""PRE-COMMIT CONFIDENTIALITY GATE -- every control, over everything that will be committed,
in one run with one verdict.

This is the script the charter's §3.2 step 3 asks for. It exists because the controls each
answer a different question and nobody should have to remember to run all of them in the
right order on the right file set.

WHAT IS ON THE COMMIT LIST, and the list is the point -- the recovered changelog sat on it
unscanned for weeks because nobody had written the list down:

    committed, and checked here    the six analysis documents
                                   tools/ -- every script in it
                                   uk/ and us/ -- the two published trees
    committed, do not exist yet    tests/fixtures/ (synthetic only)
    NEVER committed                the private folder · the logs · the corpus ·
                                   the archived .skill revisions and their changelog
                                   temp/ (gitignored scratch)

TWO CONTROLS LIVE OUTSIDE THE REPOSITORY AND ARE CALLED BY PATH. That is not an accident of
history; it is the same pattern as the pattern lists themselves, for the same reason:

  * the corpus-descriptor scan holds every real subject-matter qualifier inline, so it is as
    sensitive as the list it embodies;
  * the confidentiality review sets out which candidate shapes we ACCEPT, which is a map of
    what gets waved through -- probe-clean, and withheld by judgement (Wouter, 2026-08-06).

Point LT_PRIVATE_DIR at them, or let it default to the sibling folder. In CI, supply the two
pattern lists as secrets via LEAKAGE_LIST_PATH and CORPUS_DESCRIPTORS_FILE.

Exit codes:  0 = CLEAR · 1 = a control is failing · 2 = a control could not run at all,
which is NOT a pass.

    uv run python tools/precommit_gate.py
"""
import io
import os
import re
import subprocess
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parent.parent
PRIV = Path(os.environ.get("LT_PRIVATE_DIR", ROOT.parent / "legal-translation-private"))

DOCS = ["CLAUDE.md", "FINDINGS-REGISTER.md", "A3-STRUCTURAL-ANALYSIS.md",
        "STEP-B-ANALYSIS.md", "DECISIONS-LOG.md", "OPUS-5-MIGRATION.md"]

FAIL, VOID = [], []


def run(*args):
    r = subprocess.run([sys.executable, *[str(a) for a in args]], capture_output=True,
                       text=True, encoding="utf-8", errors="replace", cwd=ROOT)
    return (r.stdout or "") + (r.stderr or ""), r.returncode


def need(rel):
    """A control that is absent has not passed. Say so, loudly, and remember it."""
    p = PRIV / "tools" / rel
    if not p.exists():
        VOID.append(rel)
        return None
    return p


def head(t):
    print()
    print("=" * 92)
    print(t)
    print("=" * 92)


head("WHAT IS ON THE COMMIT LIST")
missing = [d for d in DOCS if not (ROOT / d).exists()]
print(f"  analysis documents        {len(DOCS)} " + ("— all present" if not missing else f"— MISSING {missing}"))
if missing:
    FAIL.append("commit list")
n_tools = len(list((ROOT / "tools").glob("*.py"))) if (ROOT / "tools").exists() else 0
print(f"  tools/                    {n_tools} script(s)")
for n in ("README.md", ".gitignore"):
    print(f"  {n:<25} {'present' if (ROOT / n).exists() else 'does not exist yet — check it when written'}")
for v in ("uk", "us"):
    d = ROOT / v
    print(f"  {v}/{' ' * 23}"
          f"{sum(1 for p in d.rglob('*') if p.is_file()) if d.exists() else 'not created yet'} files")
print(f"  docs/history/             {'PRESENT — IT SHOULD NOT BE' if (ROOT / 'docs').exists() else 'absent, as decided 2026-08-06'}")
if (ROOT / "docs").exists():
    FAIL.append("docs/history exists")

head("1. PUBLICATION CHECK — the forbidden classes, blocking")
out, rc = run(ROOT / "tools" / "publication_check.py")
probe = re.search(r"descriptor probe: (.*)", out)
res = re.search(r"RESULT: (.*)", out)
print(f"  descriptor probe: {probe.group(1) if probe else 'NOT REPORTED'}")
print(f"  {res.group(1) if res else out[-200:]}")
if rc != 0:
    FAIL.append("publication check")
if probe and "DISABLED" in probe.group(1):
    FAIL.append("descriptor probe disabled")

head("2. NAME SCAN — 93 patterns, list held outside the repository")
tool_files = sorted(str(p.relative_to(ROOT)) for p in (ROOT / "tools").glob("*.py"))
for label, files in [("analysis documents", DOCS), ("tools/ scripts", tool_files)]:
    out, rc = run(ROOT / "tools" / "leakage_scan.py", *files)
    if rc == 2:
        VOID.append("leakage_scan (list unreadable)")
        print(f"  {label:<26} CONTROL VOID — list not readable")
        continue
    verdict = "CLEAN" if "CLEAN --" in out else "HITS — judge each"
    n = re.search(r"(\d+) hit\(s\)", out)
    print(f"  {label:<26} {verdict}" + (f"  ({n.group(1)} hits)" if n and verdict != "CLEAN" else ""))
    if verdict != "CLEAN":
        FAIL.append(f"name scan: {label}")

head("3. CORPUS DESCRIPTORS — instrument class + language only")
p = need("corpus_descriptor_scan.py")
if p is None:
    print("  targeted term list        CONTROL VOID — scanner not found in the private folder")
else:
    out, rc = run(p)
    t = re.search(r"TOTAL: (\d+) hit\(s\) across (\d+) files", out)
    read = int(t.group(2)) if t else 0
    print(f"  targeted term list        {t.group(1) if t else '?'} hit(s) across "
          f"{read} of {len(DOCS)} documents")
    if read != len(DOCS):
        VOID.append(f"descriptor scan read {read} of {len(DOCS)} documents")
    elif t.group(1) != "0":
        FAIL.append("descriptor scan")

_d = Path(os.environ.get("CORPUS_DESCRIPTORS_FILE", PRIV / "corpus-descriptors.txt"))
if not _d.exists():
    print("  list-free shape sweep     CONTROL VOID — descriptor list not found")
    VOID.append("corpus-descriptors.txt")
else:
    pats = [l.strip() for l in _d.read_text(encoding="utf-8").splitlines()
            if l.strip() and not l.lstrip().startswith("#")]
    out, rc = run(ROOT / "tools" / "descriptor_shape_sweep.py")
    cands = re.findall(r"^  ([a-z][\w'’-]*)\s+\d+$", out, re.M)
    forbidden = [c for c in cands
                 if any(re.fullmatch(pt, c, re.I) or re.fullmatch(pt, c + " x", re.I)
                        for pt in pats)
                 or any(re.search(pt, c, re.I) and len(c) > 4 for pt in pats)]
    print(f"  list-free shape sweep     {len(cands)} candidate qualifier(s), "
          f"{len(forbidden)} matching the forbidden list")
    if forbidden:
        FAIL.append(f"descriptor sweep: {forbidden}")

head("4. SHAPE SWEEP — money · capacity · dates · identifiers · names · paths · filenames")
p = need("confidentiality_review.py")
if p is None:
    print("  CONTROL VOID — the judgement pass is not in the private folder")
else:
    out, rc = run(p)
    # DID IT ACTUALLY READ THE DOCUMENTS? When this script was moved into the private folder
    # its idea of the repository root moved with it, so it scanned nothing and reported zero
    # in every category -- a clean bill of health from a control that had opened no files.
    # Counting the per-file banners is what distinguishes "nothing found" from "nothing read".
    scanned = len(re.findall(r"^\S+\.md  \(\d[\d,]* bytes\)$", out, re.M))
    if scanned != len(DOCS):
        VOID.append(f"shape sweep read {scanned} of {len(DOCS)} documents")
        print(f"  CONTROL VOID — it read {scanned} of the {len(DOCS)} documents, so its")
        print("  zeros mean 'nothing opened', not 'nothing found'.")
    for cat in ["money or currency amount", "capacity, power or physical quantity",
                "registration / identifier shape", "personal name shape", "email or phone",
                "absolute or home path"]:
        n = len(re.findall(re.escape(cat) + r": (\d+)", out))
        print(f"  {cat:<44} {'0' if n == 0 else 'HITS — read them'}")
        if n:
            FAIL.append(f"shape sweep: {cat}")
    for cat, why in [("date that could pin a transaction",
                      "the project's own dates — rev44 publication, the post-mortem, the vendor docs"),
                     ("corpus filename shape", "bare .docx extension mentions, no filenames")]:
        tot = re.search(re.escape(cat) + r"\s+(\d+)$", out, re.M)
        print(f"  {cat:<44} {tot.group(1) if tot else '0'}  ({why})")

head("5. COMMITTABILITY OF THE CODE — does a file hold one real string per pattern?")
out, rc = run(ROOT / "tools" / "script_committability.py")
if rc == 2:
    VOID.append("script_committability (list unreadable)")
    print("  CONTROL VOID — a pattern list could not be read")
else:
    for line in out.splitlines():
        if line.startswith("tools/") or line.startswith("RESULT:") or "BLOCKER" in line:
            print(f"  {line}")
    if rc != 0:
        FAIL.append("a committed script holds a real string")

head("6. NO REAL DOCUMENT HAS WANDERED IN")
# The .gitignore is deliberately BY PATH, so it cannot catch a renamed client document. The
# charter says the scan is the actual control -- this is that control. Any Word document
# outside the synthetic fixture folder is reported, whatever it is called.
allowed = ROOT / "tests" / "fixtures"
strays = [p for p in ROOT.rglob("*")
          if p.is_file() and p.suffix.lower() in {".docx", ".doc", ".dotx", ".rtf"}
          and "temp" not in p.relative_to(ROOT).parts
          and allowed not in p.parents]
print(f"  Word documents outside tests/fixtures/: {len(strays)}")
for s in strays[:10]:
    print(f"      {s.relative_to(ROOT)}")
if strays:
    FAIL.append("a Word document sits outside tests/fixtures/")

head("VERDICT")
if VOID:
    print(f"  CANNOT CERTIFY — {len(VOID)} control(s) did not run:")
    for v in dict.fromkeys(VOID):
        print(f"    · {v}")
    print("  A control that could not run has NOT passed. Do not read this as clean.")
if FAIL:
    print(f"  BLOCKED — {len(FAIL)} control(s) failing:")
    for f in dict.fromkeys(FAIL):
        print(f"    · {f}")
if not FAIL and not VOID:
    print("  CLEAR. Every control passes over everything on the commit list that exists today.")
    print("  Re-run this before `git init`, and again before the public flip.")
print("=" * 92)
sys.exit(2 if VOID else (1 if FAIL else 0))
