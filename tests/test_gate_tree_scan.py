# -*- coding: utf-8 -*-
"""ACCEPTANCE TEST for precommit_gate.py section 7 — the published trees, added lines only.

Sections 1 to 6 of the gate never looked at uk/ or us/ at all: they scanned the six analysis
documents and tools/, and merely COUNTED the tree files. That was deliberate — CLAUDE.md
5.4(b) records that scanning a whole tree returns 46 hits per tree, almost all ordinary
Dutch, Polish, Hungarian, Finnish, French and German legal vocabulary matching short
patterns, and a reviewer facing 46 known-benign hits starts skimming. Section 7 dissolves
that by diffing: the pre-existing false positives sit in the baseline and cancel, so only
what a branch INTRODUCES is judged.

THE FAILURE THIS FILE IS BUILT AGAINST is a confidentiality control that reports CLEAN
because it looked at nothing. A gate whose diff silently returns empty, or whose baseline
does not resolve, would print a reassuring line and block nothing — and this project has
already logged a promotion gate that passed a file holding two corpus descriptors.

So: prove it FIRES on planted leaks of each class, prove it stays quiet on real added prose,
and prove it says VOID rather than CLEAN when it cannot establish a baseline.

RESTORATION: mutations are held in memory and written back. Never through git — the working
tree here may hold staged content that `git checkout --` would destroy.

    uv run python tests/test_gate_tree_scan.py
"""
import os
import re
import subprocess
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parent.parent
GATE = ROOT / "tools" / "precommit_gate.py"
TARGET = ROOT / "uk" / "SKILL.md"

results = []


def check(name, ok, detail=""):
    results.append((name, ok))
    print(f"  {'OK  ' if ok else 'FAIL'}  {name}{('  — ' + detail) if detail else ''}")
    return ok


def gate(env_extra=None):
    """Run the gate and return (section-7 text, exit code)."""
    env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
    env.update(env_extra or {})
    r = subprocess.run([sys.executable, str(GATE)], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", cwd=ROOT, env=env)
    out = (r.stdout or "") + (r.stderr or "")
    m = re.search(r"7\. THE PUBLISHED TREES.*?(?=\nVERDICT|\n=+\nVERDICT)", out, re.S)
    return (m.group(0) if m else ""), r.returncode, out


def with_planted(text_to_add, probe):
    """Append a line to a tree file, run probe, restore the exact original bytes."""
    original = TARGET.read_bytes()
    try:
        TARGET.write_bytes(original + ("\n" + text_to_add + "\n").encode("utf-8"))
        return probe()
    finally:
        TARGET.write_bytes(original)


print("=" * 92)
print("GATE SECTION 7 — does the tree scan actually bite?")
print("=" * 92)

# --------------------------------------------------------------------------------------
print("\n1. IT RUNS AT ALL, AND REPORTS WHAT IT LOOKED AT")
sec, rc, _ = gate()
check("section 7 is present in the gate's output", bool(sec))
check("and it names its baseline and what it read",
      "baseline" in sec and "line(s) added" in sec,
      sec.splitlines()[2].strip() if len(sec.splitlines()) > 2 else "")

# --------------------------------------------------------------------------------------
# 2. THE NEGATIVES. One planted leak per class the section claims to catch.
# Each string is INVENTED for this test — no real name, no real filename, no real figure.
print("\n2. NEGATIVE TESTS — a planted leak of each class must BLOCK")

PLANTS = [
    ("a three-part personal name",
     "Signed for and on behalf of Quintus Aurelius Fabricius."),
    ("a corpus filename shape",
     "See the attached Imaginary Placeholder Agreement.docx for details."),
    ("a money figure",
     "The guaranteed sum is EUR 4,500,000 under this clause."),
    ("a capacity figure",
     "The facility has a nameplate capacity of 123 MW."),
    ("an email address",
     "Queries go to not.a.real.person@example-invented.test for triage."),
    ("an absolute Windows path",
     r"Read it from Z:\Invented\Folder\somewhere for the run."),
]
for label, plant in PLANTS:
    def _p():
        s, rc_, _o = gate()
        return s, rc_
    sec2, rc2 = with_planted(plant, _p)
    fired = rc2 == 1 and "CLEAN" not in sec2.split("forbidden classes")[-1]
    check(f"blocks: {label}", rc2 == 1, f"exit {rc2}")

# --------------------------------------------------------------------------------------
print("\n3. AND IT STAYS QUIET ON REAL ADDED PROSE")
sec3, rc3, _ = gate()
check("with nothing planted, the gate is not blocked by section 7",
      "name scan" not in sec3 or "CLEAN" in sec3, "")
check("the gate's own exit is 0 on the unmodified tree", rc3 == 0, f"exit {rc3}")

# --------------------------------------------------------------------------------------
# 4. VOID, NOT CLEAN. A control that could not establish a baseline has not passed.
print("\n4. IT SAYS VOID — NOT CLEAN — WHEN IT CANNOT ESTABLISH A BASELINE")
sec4, rc4, out4 = gate({"LT_TREE_BASELINE": "no-such-ref-exists-anywhere"})
check("an unresolvable baseline reports CONTROL VOID", "CONTROL VOID" in sec4)
check("and the gate refuses to certify (exit 2, not 0)", rc4 == 2, f"exit {rc4}")
check("and the verdict says so in words",
      "CANNOT CERTIFY" in out4 and "has NOT passed" in out4)

# --------------------------------------------------------------------------------------
print("\n5. THE TREE IS EXACTLY AS IT WAS")
r = subprocess.run(["git", "diff", "--name-only", "--", "uk/", "us/"],
                   capture_output=True, cwd=ROOT)
dirty = [f for f in r.stdout.decode().splitlines() if f.strip()]
check("no planted line survived — the working tree is unchanged by this test",
      not dirty, f"{dirty[:3]}" if dirty else "")

print()
print("=" * 92)
ok = sum(1 for _, c in results if c)
print(f"RESULT: {ok} of {len(results)} checks passed")
for n, c in results:
    if not c:
        print(f"    FAILED: {n}")
print()
print("  WHAT THIS DOES NOT PROVE: that a leak of a shape none of these patterns describes")
print("  would be caught. The list-free shape sweep and human judgement remain the answer")
print("  to that, exactly as CLAUDE.md 5.4 says — the probes are a floor, not a ceiling.")
print("=" * 92)
sys.exit(0 if ok == len(results) else 1)
