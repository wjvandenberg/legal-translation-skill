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

head("7. THE PUBLISHED TREES — ADDED LINES ONLY, AGAINST THE BASELINE")
# WHY THIS SECTION EXISTS, AND WHY IT DIFFS RATHER THAN SCANS.
#
# Controls 1 to 6 cover the six analysis documents and tools/. THEY DO NOT SCAN uk/ OR us/ AT
# ALL -- the gate counts their files and stops there. That was defensible while no branch
# changed them; branch 4 changes eight files, and branches 6, 7, 16 and 17 will change far
# more. A confidentiality gate blind to the two directories that actually ship is the wrong
# blind spot to keep.
#
# It was left blind for a real reason, recorded in CLAUDE.md 5.4(b): scanning a WHOLE tree
# returns 46 hits per tree, overwhelmingly ordinary Dutch, Polish, Hungarian, Finnish, French
# and German legal vocabulary matching short patterns. A reviewer facing 46 known-benign hits
# starts skimming, which is the exact failure this project diagnoses in the skill's own
# validators -- a control nobody believes.
#
# DIFFING TO ADDED LINES DISSOLVES THAT. The pre-existing false positives are in the baseline
# and cancel out; only what a branch INTRODUCES is judged. Measured on branch 4: the eight
# whole files give 6 hits, the 102 added lines give 0. Same evidence, readable.
#
# It reports VOID rather than CLEAN when it cannot establish a baseline (CLAUDE.md 5.1: a
# control that opened no files says VOID, never CLEAN).
BASE = os.environ.get("LT_TREE_BASELINE", "origin/main")


def git_out(*args):
    r = subprocess.run(["git", *args], capture_output=True, cwd=ROOT)
    return r.stdout.decode("utf-8", "replace"), r.returncode


_, rc_base = git_out("rev-parse", "--verify", "--quiet", BASE)
if rc_base != 0:
    print(f"  CONTROL VOID — no baseline to diff against ({BASE} does not resolve).")
    VOID.append(f"tree diff (baseline {BASE} unresolvable)")
else:
    diff, rc_diff = git_out("diff", "--unified=0", BASE, "--", "uk/", "us/")
    if rc_diff != 0:
        print("  CONTROL VOID — git diff failed.")
        VOID.append("tree diff (git diff failed)")
    else:
        added = [l[1:] for l in diff.splitlines()
                 if l.startswith("+") and not l.startswith("+++")]
        changed, _ = git_out("diff", "--name-only", BASE, "--", "uk/", "us/")
        n_files = len([f for f in changed.splitlines() if f.strip()])
        print(f"  baseline {BASE} · {n_files} tree file(s) changed · "
              f"{len(added)} line(s) added")
        if not added:
            print("  nothing added to either tree — nothing for this control to judge.")
        else:
            blob = "\n".join(added)
            tmp = ROOT / "temp"
            tmp.mkdir(exist_ok=True)
            probe_file = tmp / ".gate-tree-added.txt"
            probe_file.write_text(blob, encoding="utf-8")
            try:
                # (a) the 93-pattern name list, via the scanner that owns it
                sc = need("leakage_scan.py") or (ROOT / "tools" / "leakage_scan.py")
                out, rc = run(sc, probe_file)
                if rc == 2:
                    print("  name scan (93 patterns)   CONTROL VOID — list not readable")
                    VOID.append("tree name scan (list unreadable)")
                else:
                    hits = re.search(r"(\d+) hit\(s\)", out)
                    n = int(hits.group(1)) if hits else (0 if "CLEAN" in out else -1)
                    print(f"  name scan (93 patterns)   {'CLEAN' if n == 0 else f'{n} hit(s)'}")
                    if n != 0:
                        FAIL.append(f"tree added lines: {n} name-scan hit(s)")
                # (b) the corpus descriptors, applied AS REGEX -- never re.escape'd. Nine of
                #     the thirteen contain \s+ by design (5.4), and escaping them is exactly
                #     the bug that made a promotion gate report CLEAN on a file holding two.
                if _d.exists():
                    dp = [l.strip() for l in _d.read_text(encoding="utf-8").splitlines()
                          if l.strip() and not l.lstrip().startswith("#")]
                    dh = [p for p in dp if re.search(p, blob, re.I)]
                    print(f"  corpus descriptors        "
                          f"{'CLEAN' if not dh else f'{len(dh)} PATTERN(S) MATCHED'}"
                          f"   ({len(dp)} pattern(s), applied as regex)")
                    if dh:
                        FAIL.append(f"tree added lines: {len(dh)} corpus descriptor(s)")
                else:
                    print("  corpus descriptors        CONTROL VOID — list not found")
                    VOID.append("tree descriptor scan (list not found)")
                # (c) the forbidden classes the publication check applies to prose
                CLASSES = [
                    ("absolute or home path",
                     r"[A-Za-z]:[\\/][\w\-.]+(?:[\\/][\w\-. ]+)+|~[\\/][\w\-.]+"),
                    ("container path", r"(?<![\w.])/(?:home|mnt)/[\w\-./]+"),
                    ("money or currency", r"(?:EUR|USD|GBP|€|\$|£)\s?[\d.,]{4,}"),
                    ("capacity figure", r"\b\d[\d.,]*\s?(?:MW|kW|GW|MWh|kWh|MVA)\b"),
                    ("email or phone", r"[\w.\-]+@[\w.\-]+\.\w+"),
                    ("three-part personal name",
                     r"\b[A-Z][a-z]{2,}\s+[A-Z][a-z]{2,}\s+[A-Z][a-z]{2,}\b"),
                    # NARROWED AT BRANCH 5, and the narrowing is a fix to the check rather
                    # than a concession. The pattern was `[\w\-. ()]{3,}\.(?:docx?|pdf)\b`,
                    # which fires on ANY prose mentioning a bare extension: branch 5's added
                    # lines gave " the .docx" and " through left a partial .docx", neither of
                    # which contains a filename. Section 4 already labels that class benign in
                    # its own legend ("bare .docx extension mentions, no filenames") — but
                    # section 7 BLOCKS, so the same class stopped the gate.
                    #
                    # What the class exists to catch is a real corpus filename, and §5.4 says
                    # what makes those dangerous: "the test corpus filenames alone carry
                    # counterparty names". A counterparty name is a proper noun, so the stem
                    # must contain a capital. Vectors for both directions live in
                    # tests/test_gate_tree_scan.py and run in this same commit, per §5.4's
                    # rule that a pattern is tested against the string it was written for.
                    #
                    # THE CAPITAL MUST BE IN THE TOKEN THAT ABUTS THE EXTENSION, not merely
                    # somewhere earlier in the line — and the first attempt at this narrowing
                    # got that wrong. It allowed the capital anywhere in a run that included
                    # spaces, so any SENTENCE beginning with a capital still matched: "The
                    # repack writes a partial .docx" fired on the "T" of "The". It passed the
                    # vectors chosen by hand, because those all began lowercase, and was caught
                    # by the benign plants in tests/test_gate_tree_scan.py, which are whole
                    # sentences. Hand-picked vectors that share a shape test the shape, not the
                    # pattern.
                    #
                    # So the stem must be one or more CAPITALISED tokens ending at the
                    # extension, which is what a filename carrying proper nouns looks like and
                    # what running prose does not.
                    #
                    # THE RESIDUAL GAP, STATED: an all-lowercase real filename would now pass
                    # this pattern. It would not pass the 93-pattern NAME scan, which runs over
                    # the same added lines two controls above and is the primary defence
                    # against names; this is a shape backstop, not the name check.
                    ("corpus filename shape",
                     r"\b[A-Z][\w\-()]*(?:[ _\-][A-Z0-9][\w\-()]*)*\.(?:docx?|pdf)\b"),
                ]
                worst = []
                for label, pat in CLASSES:
                    k = len(set(re.findall(pat, blob)))
                    if k:
                        worst.append(f"{label} x{k}")
                print(f"  forbidden classes         "
                      f"{'CLEAN' if not worst else '; '.join(worst)}")
                if worst:
                    FAIL.append(f"tree added lines: {'; '.join(worst)}")
            finally:
                probe_file.unlink(missing_ok=True)

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
