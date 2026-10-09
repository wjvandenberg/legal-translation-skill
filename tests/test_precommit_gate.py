# -*- coding: utf-8 -*-
"""NEGATIVE TESTS FOR THE PRE-COMMIT GATE — it mutates the repository to prove each control
can FAIL, then restores it byte-identically.

WHY THIS EXISTS, and it is the project's most-repeated lesson rather than a convention. A
control that has never been seen to fail is not a control; it is a line in a report. Eleven
checks in this project have passed for the wrong reason, and every one was found by asking
the same question a second way — never by reading. The gate reported CLEAR from the moment
it was written, which is exactly the state in which a passing check tells you nothing.

Each case makes ONE deliberate violation, runs the gate, and asserts the gate NOTICED. The
restore is verified by SHA-256, so a crashed run cannot leave a mutation behind unremarked.

    uv run python tests/test_precommit_gate.py
"""
import hashlib
import io
import os
import shutil
import subprocess
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parent.parent
sys.dont_write_bytecode = True  # importing from tools/ must leave no bytecode there
sys.path.insert(0, str(ROOT / "tools"))
import inplace_guard as guard  # noqa: E402  (register I-37: a repository file changes only through it)
GATE = ROOT / "tools" / "precommit_gate.py"
PRIV = Path(os.environ.get("LT_PRIVATE_DIR", ROOT.parent / "legal-translation-private"))


def gate(env=None):
    e = dict(os.environ)
    e["PRECOMMIT_GATE_EXEMPT_PID"] = str(os.getpid())   # this run's own guard records (I-37)
    if env:
        e.update(env)
    r = subprocess.run([sys.executable, str(GATE)], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", cwd=ROOT, env=e)
    return (r.stdout or "") + (r.stderr or ""), r.returncode


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


results = []


def case(name, expect_rc, expect_text, change):
    """Run one negative test. `change` returns a guard from tools/inplace_guard.py that makes the
    violation inside it and undoes it after - RECORDED FIRST, so a run killed mid-test leaves a
    record the next guarded run settles and this gate refuses, never a planted violation in a
    committable file (register I-37). The gate is told apart from the plant by its text."""
    with change():
        out, rc = gate()
    caught = rc == expect_rc and expect_text.lower() in out.lower()
    results.append((name, caught, rc, expect_rc))
    print(f"  {'PASS' if caught else 'FAIL'}  {name}")
    if not caught:
        print(f"          expected exit {expect_rc} and {expect_text!r}; got exit {rc}")


print("=" * 92)
print("NEGATIVE TESTS — can the pre-commit gate actually fail?")
print("=" * 92)

out, rc = gate()
print(f"\n  baseline: exit {rc}, "
      f"{'CLEAR' if 'CLEAR.' in out else 'NOT CLEAR — fix that before trusting these tests'}")
if rc != 0:
    print("  The gate is not clean to begin with, so a failure below proves nothing.")
    sys.exit(2)

# ---------------------------------------------------------------------------
# 1. A real client document wanders into the tree under an innocent name.
#    This is the case `.gitignore` CANNOT catch, which is why the charter says the scan is
#    the actual control. The file is empty — the check is about place and extension, not
#    content, and putting real content in a test fixture would be its own violation.
# ---------------------------------------------------------------------------
stray = ROOT / "uk" / "meeting-notes.docx"
case("a Word document outside tests/fixtures/ is caught",
     1, "Word document sits outside",
     lambda: guard.planted(stray, b""))

# 1b. A WORKING COPY UNDER .claude/worktrees (a parallel session's git worktree) carries its own tests/fixtures, and
#     those synthetic documents are allowed -- 2026-10-08 (2), when 24 of them blocked a commit here -- while a Word
#     document anywhere else in a working copy is still caught. A planted copy, through the guard (register I-37), so a
#     kill leaves a record the next guarded run settles, never a stray working copy for the next commit to scan.
wcopy = ROOT / ".claude" / "worktrees" / "zz-gate-test"

case("a Word document in a working copy's own tests/fixtures/ is allowed",
     0, "Word documents outside tests/fixtures/: 0",
     lambda: guard.planted(wcopy / "tests" / "fixtures" / "synthetic.docx", b""))
case("a Word document elsewhere in a working copy is caught",
     1, "Word document sits outside",
     lambda: guard.planted(wcopy / "uk" / "meeting-notes.docx", b""))

# ---------------------------------------------------------------------------
# 2. A forbidden corpus descriptor appears in a committable document.
#    The descriptor is NOT written here: it is read from the private list at run time, so
#    this test carries no real string of its own. That is the same rule the scanners follow.
# ---------------------------------------------------------------------------
desc_file = Path(os.environ.get("CORPUS_DESCRIPTORS_FILE", PRIV / "corpus-descriptors.txt"))
target = ROOT / "DECISIONS-LOG.md"
base = target.read_bytes()
base_sha = hashlib.sha256(base).hexdigest()

if desc_file.exists():
    import re as _re
    pats = [l.strip() for l in desc_file.read_text(encoding="utf-8").splitlines()
            if l.strip() and not l.lstrip().startswith("#")]
    # Turn the first pattern back into a literal that will match it.
    probe = _re.sub(r"\\b|\\s\+|[()?:|]", lambda m: " " if m.group(0) == r"\s+" else "",
                    pats[0]).strip()
    case("a forbidden corpus descriptor in a committable document is caught",
         1, "descriptor",
         lambda: guard.mutated(target, base + f"\n\nA {probe} matter.\n".encode("utf-8")))
    assert sha(target) == base_sha, "RESTORE FAILED for DECISIONS-LOG.md"
else:
    print("  SKIP  descriptor case — private list not available")
    results.append(("descriptor case", False, 0, 0))

# ---------------------------------------------------------------------------
# 3. A control cannot load its pattern list.
#    This is the one that matters most, because the failure mode is a FALSE PASS: a scanner
#    with an empty list reports clean on everything. The gate must say CANNOT CERTIFY, not
#    CLEAR, and it must not exit 0.
# ---------------------------------------------------------------------------
out, rc = gate({"LEAKAGE_LIST_PATH": str(ROOT / "temp" / "no-such-list.txt")})
caught = rc == 2 and "cannot certify" in out.lower()
results.append(("a missing pattern list is CANNOT CERTIFY, not CLEAR", caught, rc, 2))
print(f"  {'PASS' if caught else 'FAIL'}  a missing pattern list is CANNOT CERTIFY, not CLEAR")

# ---------------------------------------------------------------------------
# 4. A control runs but reads nothing — the silent false pass this gate was built with.
#    Point the shape sweep at an empty directory: every category reports zero, which without
#    the read-count assertion is indistinguishable from a clean result.
# ---------------------------------------------------------------------------
empty = ROOT / "temp" / "_gate_empty_repo"
empty.mkdir(parents=True, exist_ok=True)
out, rc = gate({"LT_REPO_DIR": str(empty)})
caught = rc == 2 and "nothing opened" in out.lower()
results.append(("a control that reads no files is VOID, not clean", caught, rc, 2))
print(f"  {'PASS' if caught else 'FAIL'}  a control that reads no files is VOID, not clean")
shutil.rmtree(empty, ignore_errors=True)

# ---------------------------------------------------------------------------
# 5. A committed script holds a real string — the rule that decides `tools/`.
# ---------------------------------------------------------------------------
scratch = ROOT / "tools" / "_negative_test_scratch.py"
case("a tools/ script holding an absolute home path is caught",
     1, "hold a real string",
     lambda: guard.planted(scratch, 'P = r"C:\\Users\\someone\\Desktop\\thing"\n'.encode("utf-8")))

# ---------------------------------------------------------------------------
# 6. A development-only file sits inside a SHIPPED tree.
#    Added 2026-08-21 on branch 14, and it is here because the leak came back for the THIRD
#    time through a new caller: fixed in tests/run_tests.py, returned via
#    tools/audit_branches.py, returned again via tools/cycle_evidence.py -- which runs the
#    tests as a subprocess and so passed its own environment, not the test runner's.
#
#    Every one of those fixes was correct and none stopped the next caller, because
#    __pycache__ is gitignored: invisible to a diff, to git status, and until now to this
#    gate, which reported CLEAR with a .pyc sitting in uk/scripts. So the fix is not a
#    fourth patched caller, it is this assertion -- and the assertion has to be seen to
#    fail, or it is one more line in a report.
# ---------------------------------------------------------------------------
pycache = ROOT / "uk" / "scripts" / "__pycache__"
planted_pyc = pycache / "negative_test.cpython-000.pyc"


case("a .pyc inside uk/scripts is caught", 1, "development-only file",
     lambda: guard.planted(planted_pyc, b"\x00not real bytecode\x00"))

# And an editor backup, so the check is not narrowly about Python bytecode.
planted_bak = ROOT / "us" / "scripts" / "quality_check.py.orig"
case("an editor backup inside us/scripts is caught", 1, "development-only file",
     lambda: guard.planted(planted_bak, b"stale copy\n"))

# ---------------------------------------------------------------------------
# 7. A RUN THAT CHANGED A REPOSITORY FILE AND WAS KILLED BEFORE PUTTING IT BACK (register I-37).
#    Every case above runs inside the guard, so a kill there leaves a record, not a planted
#    violation - and this proves the gate then REFUSES. A child enters the guard and ends itself
#    with os._exit, which skips every finally exactly as a kill does. The plant is in gitignored
#    temp/: what is under test is the RECORD, since a content scan reads a planted defect - a
#    dropped id, a wrong count - as ordinary text.
# ---------------------------------------------------------------------------
killed_plant = ROOT / "temp" / "_gate_killed_run_probe.txt"
CHILD = chr(10).join([
    "import os, sys",
    "sys.dont_write_bytecode = True",
    "sys.path.insert(0, sys.argv[1])",
    "import inplace_guard as g",
    "from pathlib import Path",
    "with g.planted(Path(sys.argv[2]), b'left by a killed run'):",
    "    os._exit(137)",
])
k = subprocess.run([sys.executable, "-c", CHILD, str(ROOT / "tools"), str(killed_plant)],
                   capture_output=True)
out, rc = gate()
caught = k.returncode == 137 and rc == 1 and "left a repository file changed" in out
results.append(("a killed run's unfinished change BLOCKS the commit", caught, rc, 1))
print(f"  {'PASS' if caught else 'FAIL'}  a killed run's unfinished change BLOCKS the commit")
if not caught:
    print(f"          child exit {k.returncode} (137 wanted); gate exit {rc} (1 wanted)")
guard.settle_dead(ROOT)
settled = not killed_plant.exists() and not guard.records(ROOT)
results.append(("...and settling it removes the plant and the record", settled, 0, 0))
print(f"  {'PASS' if settled else 'FAIL'}  ...and settling it removes the plant and the record")

# ---------------------------------------------------------------------------
print()
print("=" * 92)
ok = sum(1 for _, c, _, _ in results if c)
print(f"RESULT: {ok} of {len(results)} controls demonstrated able to fail")
for name, c, rc, exp in results:
    if not c:
        print(f"    NOT DEMONSTRATED: {name} (exit {rc}, wanted {exp})")
print("=" * 92)

out, rc = gate()
print(f"  repository restored: gate exit {rc} "
      f"({'CLEAR' if 'CLEAR.' in out else 'NOT CLEAR — INVESTIGATE'})")
if rc != 0:
    sys.exit(2)
sys.exit(0 if ok == len(results) else 1)
