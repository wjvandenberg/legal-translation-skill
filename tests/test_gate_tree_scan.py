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

# Snapshot the bytes of every file this test plants into, BEFORE anything is written. Section
# 5 compares against these rather than against `git diff`, which answers a different question
# — see the comment there.
PLANT_TARGETS = [TARGET]
BEFORE_BYTES = {p: p.read_bytes() for p in PLANT_TARGETS}


# ---------------------------------------------------------------------------------------
# THE ENTRY GUARD, AND IT EXISTS BECAUSE THIS TEST LEFT A PLANT IN A SHIPPED FILE (2026-08-24).
#
# WHAT HAPPENED. This suite was run inside a batch that hit a two-minute timeout and was KILLED
# mid-run, leaving `Pass the delivered .docx to the reviewer, not the intermediate one.` appended
# to uk/SKILL.md. It was then re-run on its own — and PASSED, exit 0, section 5 reporting "no
# planted line survived". It was telling the truth about the wrong question: BEFORE_BYTES is read
# FROM THE WORKING TREE at import, so the orphaned plant had become the new baseline. The test
# faithfully restored the file to its contaminated state and certified it unchanged.
#
# THAT IS §5.16 RULE 4 IN A TEST THAT WRITES TO A PUBLISHED TREE: a baseline pinned to "the
# current file" instead of to a revision, where the vacuous case is indistinguishable from the
# passing case. Here the cost is not a wrong number — it is a line of invented prose shipping
# inside a public skill, and only `git status` at the very end of the session caught it.
#
# THE FIX IS TO PIN THE BASELINE TO A COMMIT and refuse to run when the working file already
# differs from it in a way this test could have caused. It reports VOID rather than failing a
# check, because an orphaned plant is a finding about a PREVIOUS run, not about this one.
def _committed_bytes(path):
    rel = str(path.relative_to(ROOT)).replace(os.sep, "/")
    r = subprocess.run(["git", "show", f"HEAD:{rel}"], cwd=str(ROOT), capture_output=True)
    return r.stdout if r.returncode == 0 else None


# IT IS DELIBERATELY SHAPE-BASED, NOT A LIST OF THE PLANT STRINGS. A list would have to be kept
# in step with every plant this suite ever adds, and the one thing measured here is that such a
# list goes stale silently. `with_planted` leaves exactly one shape: the committed bytes followed
# by a short appended fragment. So that shape is what is refused.
#
# AND IT ERRS TOWARD VOID. A legitimate branch edit that happens to be a pure short append will
# stop this suite until a person looks — recoverable in ten seconds. The other error ships
# invented prose inside a public skill and is not recoverable at all.
_APPEND_LIMIT = 600


def _entry_guard():
    dirty = []
    for p in PLANT_TARGETS:
        committed = _committed_bytes(p)
        if committed is None or BEFORE_BYTES[p] == committed:
            continue                      # untracked, or clean — the normal case
        if not BEFORE_BYTES[p].startswith(committed):
            continue                      # a real edit in the body; not this suite's shape
        extra = BEFORE_BYTES[p][len(committed):]
        if 0 < len(extra) <= _APPEND_LIMIT:
            dirty.append((p, extra.decode("utf-8", "replace").strip()[:120]))
    if dirty:
        print("=" * 92)
        print("VOID — A PUBLISHED TREE FILE CARRIES A SHORT APPENDED FRAGMENT.")
        print("This is the exact shape this suite leaves when it is killed before it restores,")
        print("and if it is one, snapshotting it now would make it the baseline FOREVER — which")
        print("is how it survived once already. Nothing below has run. This is NOT a pass.")
        for p, what in dirty:
            print(f"    {p.relative_to(ROOT)}  trailing: {what!r}")
        print("If it is a leftover: `git checkout -- <path>` (confirm nothing of yours is staged")
        print("there first), then re-run. If it is a real edit your branch made, commit it and")
        print("re-run — the guard compares against HEAD, so a committed edit is invisible to it.")
        print("=" * 92)
        sys.exit(2)


_entry_guard()

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

# THE OTHER DIRECTION OF THE FILENAME-SHAPE NARROWING, and it is required rather than nice:
# §5.4 says every pattern must be tested against the string it was written for, in the same
# commit. The plant above proves the class still catches a filename carrying proper nouns.
# These prove it no longer fires on prose that merely names the extension — which is what the
# unnarrowed pattern did to branch 5's own added lines (" the .docx", " a partial .docx"),
# blocking the gate on text containing no filename at all.
BENIGN = [
    "The repack writes a partial .docx only under a temporary name.",
    "Pass the delivered .docx to the reviewer, not the intermediate one.",
    "Build under <output>.docx.tmp and move it into place afterwards.",
]
for benign in BENIGN:
    def _b():
        s, rc_, _o = gate()
        return s, rc_
    secb, rcb = with_planted(benign, _b)
    check(f"stays quiet on a bare extension mention: {benign[:38]!r}...", rcb == 0,
          f"exit {rcb}")

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
# THIS ASSERTED THE WRONG THING UNTIL BRANCH 5, and branch 5 is the first branch to expose
# it. It ran `git diff --name-only -- uk/ us/` and required the result to be EMPTY — which
# is not "this test changed nothing", it is "the working tree matches HEAD". Every branch
# from 6 onward legitimately modifies the published trees, so on exactly the branches this
# test exists to protect it reported a false failure and named the branch's own edits as
# surviving plants. It passed on the branch that introduced it only because that branch
# touched tools/ and tests/ and nothing under uk/ or us/.
#
# What it must compare is the bytes of the files this test PLANTS INTO, snapshotted before
# and after. That is independent of what else the branch has changed.
after = {p: p.read_bytes() for p in PLANT_TARGETS}
changed = [str(p.relative_to(ROOT)) for p in PLANT_TARGETS
           if after[p] != BEFORE_BYTES[p]]
check("no planted line survived — every file this test wrote to is byte-identical",
      not changed, f"{changed[:3]}" if changed else f"{len(PLANT_TARGETS)} file(s) verified")

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
