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

EVERY MUTATION IS PLANTED IN A COPY, NEVER IN THE TRACKED FILE (register I-37, 2026-10-08).
Until then each probe wrote its defect into PLAN-2-step-b.md itself and put the original back
in a `finally` - which a killed process never reaches. Twice in one day a planted defect was
found sitting in the real plan, a commit away from being carried. Now the plan is read once,
as bytes, and copied into a temporary folder outside the repository; every probe rewrites the
copy and points the checks at it through STEPB_PLAN_DOC (md_tables.py takes it as its
argument). A run killed mid-probe leaves its damage in that folder. The real plan's hash is
printed before and after, and the two must agree.

AND A PROBE FIRES ON WHAT THE CHECK SAID, NOT ON ITS EXIT CODE (register I-38, 2026-10-08).
stepb_audit.py fails on the clean document for a declared reason (its unverified A4
quotations), so an exit code of 1 after a mutation proved nothing - every probe aimed at it
"fired" whatever it saw. The same exit code came from a script that did not exist
(a3_md_tables.py, committed as md_tables.py) and from a crash before the plan was read. So:
  FIRED  the mutated run prints a failure row the unmutated copy's run did not (or, where the
         unmutated run is green, it goes red);
  HOLE   it does not;
  VOID   the check crashed, could not start, or said nothing - it measured nothing;
  INERT  the mutation's anchor text has moved, so the probe planted nothing.
A NULL CONTROL - a change no check reads - is run against every check and must FIRE NONE of
them: under the exit-code comparison it "fired" against two of the four, which is the defect
reproduced. And the copy's unmutated verdict must equal the real document's, row for row, or
the copy is not the plan and its probes are VOID.

    uv run python tools/stepb_metacheck.py
    (from a git worktree, set LT_PRIVATE_DIR to the private folder, or the audit is VOID)
"""
import hashlib
import os
import re
import shutil
import subprocess
import sys
import tempfile
from collections import Counter
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
DOC = ROOT / "PLAN-2-step-b.md"
# The suites are COMMITTED in tools/ as of 2026-08-11. Pointing this at temp/ would make a
# committed tool depend on a gitignored copy — it would pass here and fail in a fresh clone.
TOOLS = ROOT / "tools"
# READ ONCE, AS BYTES, AND NEVER OPENED FOR WRITING. The mutations operate on the text with
# its line endings folded to "\n", as they always have; a probe's copy is written back with
# the plan's own ending, so the copy differs from the plan by the mutation and nothing else.
ORIG_BYTES = DOC.read_bytes()
EOL = "\r\n" if b"\r\n" in ORIG_BYTES else "\n"
ORIG = ORIG_BYTES.decode("utf-8").replace("\r\n", "\n")
H0 = hashlib.sha256(ORIG_BYTES).hexdigest()

SCRIPTS = {
    "harvest (prescriptions)": "stepb_harvest.py",
    "audit  (the deep audit)": "stepb_audit.py",
    "verify (the claims)": "stepb_verify.py",
    # md_tables.py, the committed name. This said a3_md_tables.py, which exists only in a
    # gitignored temp/, so the probe "fired" on Python's file-not-found (register I-38).
    "tables (render)": "md_tables.py",
}
# A FAILURE ROW: a line in which a check states a failure, or its verdict line. Compared as a
# multiset against the same check's run on the unmutated copy, so a standing red cancels out
# and only what the mutation ADDED is left.
FAIL_ROW = re.compile(r"\[FAIL\]|\[MISS\]|^\s*FAIL\b|FAILURES:|RESULT:|MISSING|ORPHAN|"
                      r"width \d+ vs header|delimiter|PROBLEMS:|^CLEAN$|tables, \d+ width")
VOID_MARKS = ("Traceback (most recent call last)", "can't open file")


def run(script, doc):
    """One check against `doc`. STEPB_PLAN_DOC is set for a copy and REMOVED for the real
    plan, so a value inherited from the caller can never redirect the baseline."""
    env = {k: v for k, v in os.environ.items() if k != "STEPB_PLAN_DOC"}
    env["PYTHONIOENCODING"] = "utf-8"
    if doc != DOC:
        env["STEPB_PLAN_DOC"] = str(doc)
    args = [str(doc)] if script == "md_tables.py" else []
    r = subprocess.run([sys.executable, str(TOOLS / script), *args], capture_output=True,
                       text=True, encoding="utf-8", errors="replace", cwd=str(ROOT), env=env)
    out = (r.stdout or "") + (r.stderr or "")
    return r.returncode, out.replace(str(doc), "<PLAN>")


def rows(out):
    return Counter(l.strip() for l in out.splitlines() if FAIL_ROW.search(l))


def void_reason(out):
    if not out.strip():
        return "it printed nothing"
    for m in VOID_MARKS:
        if m in out:
            return f"it crashed or could not start ({m!r})"
    return ""


print("=" * 86)
print("PART 1 — the checks on the real document, read only  (a baseline, not a result)")
print("=" * 86)
real = {}
for label, sc in SCRIPTS.items():
    rc, out = run(sc, DOC)
    real[sc] = (rc, out)
    why = void_reason(out)
    n = sum(rows(out).values())
    print(f"  [{'VOID' if why else 'PASS' if rc == 0 else 'RED '}] {label:<26} exit {rc}"
          + (f"  — {why}" if why else "" if rc == 0
             else f"  — red on the clean document: a probe must ADD a failure row to its {n}"))

TMP = Path(tempfile.mkdtemp(prefix="stepb-metacheck-"))
COPY = TMP / DOC.name
problems, fired = [], 0
print()
print("=" * 86)
print("PART 2 — NEGATIVE TESTS, each planted in a COPY of the plan, never in the plan itself.")
print("         Each mutation MUST make the named check report a failure it did not report")
print("         before. A mutation that leaves it saying the same thing is a hole in the check.")
print(f"         copy: {COPY}")
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
  "md_tables.py",
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
  lambda t: re.sub(r"TWENTY findings state, in their own", "FOURTEEN findings state, in their own", t, 1),
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

 # THE FIGURE IS READ, NOT TYPED (2026-10-09). This probe anchored on a literal count, so it went
 # INERT every time a finding joined option 4 -- it did at 16 -> 17, inside the change that moved
 # it. Reading the current figure and adding 3 keeps it a real mutation whatever the count is.
 ("claim a finding count that the map contradicts (option 4: N -> N + 3)",
  lambda t: re.sub(r"Closes \*\*(\d+) findings\*\*",
                   lambda m: f"Closes **{int(m.group(1)) + 3} findings**", t, count=1),
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
 # probe has now been re-anchored three times: 41 -> 42 on branch 5 (G10), 43 -> 44 on branch 14
 # (G12), 44 -> 45 on branch 11 slice 2b (G13), 46 -> 47 on branch 11 slice 4b (C30). It reports INERT rather than passing, which is the only reason the drift is visible
 # at all -- a probe whose mutation silently stops applying is a test that has become a
 # decoration. Re-anchor it in the same commit that moves the count.
 ("state a group heading count the map contradicts (group 3: 47 -> 46)",
  lambda t: t.replace("### 5.3 Things that say it worked when it did not — 47 findings",
                      "### 5.3 Things that say it worked when it did not — 46 findings", 1),
  "stepb_audit.py",
  "NEW GUARD: check 5d compares EACH group heading to the map, not only their sum"),
]

# THE NULL CONTROL: a change no check reads, run against EVERY check, and it must fire none.
# Under the old exit-code comparison it "fired" against the audit (red on the clean plan) and
# the tables check (a script that did not exist) - a negative test that cannot tell a defect
# from no defect is the thing this file exists to catch, aimed at itself.
NULL_CONTROLS = [
 ("one more line ending at the very end of the plan", lambda t: t + "\n"),
]


def plant(text):
    """Rewrite the COPY - and only the copy - with `text`. No restore is needed: every probe
    writes its own whole copy, and each check's baseline was taken before any was planted."""
    COPY.write_bytes(text.replace("\n", EOL).encode("utf-8"))


try:
    # FIDELITY. The copy is the plan only if (a) folding and unfolding the line endings gives
    # back the plan's bytes exactly, and (b) every check says the same thing about the copy as
    # about the plan. A check that fails (b) has VOID probes: they would be measuring a
    # different document.
    plant(ORIG)
    if COPY.read_bytes() != ORIG_BYTES:
        problems.append("the copy is not byte-identical to the plan (mixed line endings?) - "
                        "every probe would differ from it by more than its mutation")
    base, unusable = {}, {}
    for label, sc in SCRIPTS.items():
        rc, out = run(sc, COPY)
        base[sc] = (rc, out)
        why = void_reason(out) or void_reason(real[sc][1])
        if not why and (rc != real[sc][0] or rows(out) != rows(real[sc][1])):
            why = "its verdict on the unmutated copy differs from its verdict on the plan"
        if why:
            unusable[sc] = why
            print(f"  [VOID ] baseline for {sc}: {why}")

    def verdict(script, text):
        """FIRED / HOLE / VOID for one planted text, and the first row it added."""
        if script in unusable:
            return "VOID", unusable[script]
        plant(text)
        rc, out = run(script, COPY)
        why = void_reason(out)
        if why:
            return "VOID", why
        brc, bout = base[script]
        added = rows(out) - rows(bout)
        first = next(iter(added), "")
        if rc != 0 and (brc == 0 or added):
            return "FIRED", first
        return "HOLE", first

    for label, mutate, script, why in MUTATIONS:
        mutated = mutate(ORIG)
        if mutated == ORIG:
            print(f"  [INERT] {label}\n          mutation did not apply — the anchor text has moved. NOT a check hole,")
            print(f"          but this negative test is inert until the anchor is updated.")
            problems.append(f"inert probe: {label}")
            continue
        v, detail = verdict(script, mutated)
        if v == "FIRED":
            fired += 1
            print(f"  [FIRED] {label}\n          -> {script} added: {detail[:110]}")
        elif v == "VOID":
            print(f"  [VOID ] {label}\n          -> {script}: {detail}")
            problems.append(f"void probe: {label} ({detail})")
        else:
            print(f"  [HOLE ] {label}\n          -> {script} reports nothing it did not report on the clean copy. {why}")
            problems.append(f"hole: {label}")

    print()
    for label, mutate in NULL_CONTROLS:
        for sc in SCRIPTS.values():
            v, detail = verdict(sc, mutate(ORIG))
            ok = v == "HOLE"
            print(f"  [{'QUIET' if ok else v + '!' if v == 'FIRED' else v}] null control vs {sc}: {label}"
                  + ("" if ok else f" -> {detail[:90]}"))
            if not ok:
                problems.append(f"null control {v} against {sc}: {label}")
finally:
    shutil.rmtree(TMP, ignore_errors=True)

H1 = hashlib.sha256(DOC.read_bytes()).hexdigest()
if H1 != H0:
    problems.append("the REAL plan changed during this run - not by this script, which never "
                    "writes it; another process is editing it")

print()
print("=" * 86)
print(f"PART 3 — result: {fired} of {len(MUTATIONS)} mutations detected")
if problems:
    print(f"\n{len(problems)} problem(s):")
    for h in problems:
        print(f"  · {h}")
else:
    print("\nEvery mutation was caught by the check that should catch it, and the null control by none.")
print()
print(f"  THE REAL PLAN WAS NEVER WRITTEN: sha256 {H0[:16]} before, {H1[:16]} after —",
      "identical" if H1 == H0 else "DIFFERENT")
print("=" * 86)
sys.exit(1 if problems else 0)
