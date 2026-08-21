#!/usr/bin/env python3
"""
STEP B — VERIFYING THE CHECKS THEMSELVES.

Wouter, 2026-08-05: "Do a deep analysis and verification of the checks in the analysis."

A check is only worth what its ability to FAIL is worth. This project has logged four
instances of a check that passed for the wrong reason -- a grep counting a mechanism wherever
a word merely appeared, a blindness auditor reading the wrong file and printing "verified: 0
files unchanged", the register validator passing a row that had landed in the wrong table,
and (this session) a prescription check passing on "attention density".

So every check gets a NEGATIVE TEST: mutate the document so the check MUST fail, and assert
that it does. A check that passes the clean file and also passes the mutated file is not a
check. This is the same discipline the analysis prescribes for the skill's own gates -- one
failing input per check -- applied to our own instruments.

    uv run python tools/stepb_metacheck.py
"""
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import sys as _sys
# A committed tool must not depend on the terminal codepage: on Windows a redirected
# stdout defaults to cp1252 and a UnicodeEncodeError reads to the caller as a FAILED
# check rather than a crashed one. See tests/run_tests.py, which pays for this lesson.
# hasattr: this module is IMPORTED by stepb_audit.py under redirect_stdout(StringIO),
# and StringIO has no .reconfigure. The unguarded version crashed the importer -- a
# fix that broke a second caller, which is the shape this project keeps logging.
if hasattr(_sys.stdout, "reconfigure"):
    _sys.stdout.reconfigure(encoding="utf-8", errors="replace")


ROOT = Path(__file__).resolve().parent.parent
DOC = ROOT / "STEP-B-ANALYSIS.md"
# The suites are COMMITTED in tools/ as of 2026-08-11. Pointing this at temp/ would make a
# committed tool depend on a gitignored copy — it would pass here and fail in a fresh clone.
TEMP = ROOT / "tools"
ORIG = DOC.read_text(encoding="utf-8")

SCRIPTS = {
    "harvest (prescriptions)": "stepb_harvest.py",
    "audit  (14 checks)": "stepb_audit.py",
    "verify (84 claims)": "stepb_verify.py",
    "tables (render)": "a3_md_tables.py",
}


def run(script, args=()):
    r = subprocess.run([sys.executable, str(TEMP / script), *args],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    return r.returncode, (r.stdout or "") + (r.stderr or "")


print("=" * 86)
print("PART 1 — do all checks pass on the real document?  (a baseline, not a result)")
print("=" * 86)
base = {}
for label, sc in SCRIPTS.items():
    args = ["STEP-B-ANALYSIS.md"] if sc == "a3_md_tables.py" else ()
    rc, out = run(sc, args)
    base[label] = rc
    print(f"  [{'PASS' if rc == 0 else 'FAIL'}] {label:<26} exit {rc}")
if any(v != 0 for v in base.values()):
    print("\n  Baseline is not clean; fix that before trusting any negative test.")

print()
print("=" * 86)
print("PART 2 — NEGATIVE TESTS. Each mutation MUST make the named check fail.")
print("         A mutation that leaves the check passing is a hole in the check.")
print("=" * 86)

# (label, mutation, which script must fail, why this mutation is the right probe)
MUTATIONS = [
 ("delete a whole prescription block (the definitions-detector story)",
  lambda t: t.replace("**(a) THE DEFINITIONS DETECTOR", "**(a) REMOVED FOR THE NEGATIVE TEST", 1)
             .replace("The detection approach is what is failing", "xx", 1)
             .replace("declared field in the notes", "xx", 1)
             .replace("density of", "xx", 1),
  "stepb_harvest.py",
  "this is the exact failure mode being audited: a prescription silently absent"),

 ("break an option's four-column table",
  lambda t: t.replace("| pros | cons | what it would break | what it does NOT fix |",
                      "| pros | cons | what it would break |", 1),
  "a3_md_tables.py",
  "a column-count change is what caught the misplaced register row; it must catch this too"),

 ("falsify a measured number (694 -> 690 bold-off instructions)",
  lambda t: t.replace("**694** in the delivered version", "**690** in the delivered version", 1),
  "stepb_audit.py",
  "the audit re-derives every quoted figure from the register"),

 ("misquote a source (drop .py from the audit line)",
  lambda t: t.replace("quality_check.py exited 0 (no issues)", "quality_check exited 0 (no issues)", 1),
  "stepb_audit.py",
  "check 10 verifies all source quotations verbatim; this is the misquote it already caught once"),

 ("break the deadlock count back to the invented figure",
  lambda t: re.sub(r"\*\*eighteen findings state, in their own", "**fourteen findings state, in their own", t, 1),
  "stepb_audit.py",
  "the figure that was asserted with the confidence of a measurement and was neither measurement"),

 ("de-rank an option (remove option 11 from the ranking table)",
  lambda t: re.sub(r"\| \*\*7\*\* \| \*\*Layout — see it and say so\*\* \(option 11\)[^\n]*\n", "", t, 1),
  "stepb_audit.py",
  "check 14 asserts every option is ranked exactly once"),

 ("dangle a cross-reference (cite a branch that does not exist)",
  lambda t: t.replace("branch 19, the last of the twenty", "branch 27, the last of the twenty", 1),
  "stepb_audit.py",
  "check 1 asserts every branch citation resolves to a table row"),

 ("break the option/appendix consistency (drop a finding from option 1's appendix row)",
  lambda t: re.sub(r"(\| 1 \| preserve-by-default in apply \| )A1 ", r"\1", t, 1),
  "stepb_audit.py",
  "the appendix is emitted from the map; check 13 must catch a hand-edit"),

 ("claim a finding count that the map contradicts (option 4: 16 -> 19)",
  lambda t: t.replace("Closes **16 findings**", "Closes **19 findings**", 1),
  "stepb_audit.py",
  "check 5 derives each option's size from the map rather than trusting the prose"),

 ("reintroduce the retired slogan as the recommendation",
  lambda t: t.replace("The right formulation is not \"preserve by default\"",
                      "The right formulation is \"preserve by default\"", 1),
  "stepb_audit.py",
  "NEW GUARD: check 15 asserts the analysis still states the retired slogan AS retired"),

 # THIS IS THE MUTATION THAT WOULD HAVE CAUGHT A REAL ERROR, and it is here because it did not
 # exist when the error shipped. G10 moved consequence group 3 from 41 to 42 on 2026-08-11, the
 # heading kept saying 41, and check 5 reported the groups SUMMING correctly while one of the
 # parts was wrong. Found 2026-08-18 by running stepb_audit rather than by reading -- and found
 # late, because it sat behind check 10's expected LEGAL_TRANSLATION_A4 red. A check that is
 # already failing for a declared reason hides every new failure behind it.
 #
 # THE ANCHOR CARRIES A LIVE COUNT, SO IT GOES INERT EVERY TIME THAT COUNT MOVES, and this
 # probe has now been re-anchored twice: 41 -> 42 on branch 5 (G10), 43 -> 44 on branch 14
 # (G12). It reports INERT rather than passing, which is the only reason the drift is visible
 # at all -- a probe whose mutation silently stops applying is a test that has become a
 # decoration. Re-anchor it in the same commit that moves the count.
 ("state a group heading count the map contradicts (group 3: 44 -> 43)",
  lambda t: t.replace("### 5.3 Things that say it worked when it did not — 44 findings",
                      "### 5.3 Things that say it worked when it did not — 43 findings", 1),
  "stepb_audit.py",
  "NEW GUARD: check 5d compares EACH group heading to the map, not only their sum"),
]

holes, fired = [], 0
for label, mutate, script, why in MUTATIONS:
    mutated = mutate(ORIG)
    if mutated == ORIG:
        print(f"  [SETUP] {label}\n          mutation did not apply — the anchor text has moved. NOT a check hole,")
        print(f"          but this negative test is inert until the anchor is updated.")
        holes.append(f"inert probe: {label}")
        continue
    DOC.write_text(mutated, encoding="utf-8")
    try:
        args = ["STEP-B-ANALYSIS.md"] if script == "a3_md_tables.py" else ()
        rc, out = run(script, args)
    finally:
        DOC.write_text(ORIG, encoding="utf-8")
    if rc != 0:
        fired += 1
        first = next((l.strip() for l in out.splitlines()
                      if "FAIL" in l or "MISS" in l or "mismatch" in l or "ORPHAN" in l), "")
        print(f"  [FIRED] {label}\n          -> {script} exit {rc}  {first[:110]}")
    else:
        print(f"  [HOLE ] {label}\n          -> {script} still PASSES the mutated document. {why}")
        holes.append(label)

print()
print("=" * 86)
print(f"PART 3 — result: {fired} of {len(MUTATIONS)} mutations detected")
if holes:
    print(f"\n{len(holes)} problem(s):")
    for h in holes:
        print(f"  · {h}")
else:
    print("\nEvery mutation was caught by the check that should catch it.")
print()
print("  RESTORED: the document on disk is byte-identical to the original —",
      DOC.read_text(encoding="utf-8") == ORIG)
print("=" * 86)
sys.exit(1 if holes else 0)
