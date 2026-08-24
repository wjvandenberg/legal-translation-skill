# -*- coding: utf-8 -*-
"""CAN `claudemd_claims.py`'s CHECK 14 STILL FAIL? Three mutations, and the third is the point.

Check 14 used to assert that `CLAUDE.md`'s section 1.6 held a contents table listing sections
1-7. Phase 3a step 1 CUT that table on 2026-08-24 as derivable -- the headings are the contents
-- so the check was rewritten into its own inverse: the table must not COME BACK, and the pointer
explaining its absence must still be there.

**A REWRITTEN CHECK IS A NEW CHECK AND HAS NEVER BEEN PROVED ABLE TO FAIL.** The old one was
demonstrated against a table that disagreed with the file; nothing carries over, because the new
one fails on the opposite condition. So each arm is planted here separately:

  1. the table comes back -- the regression the rewrite exists to catch;
  2. the table is gone and so is the pointer -- a rule that vanished, which a later session
     cannot tell apart from a rule that was repealed;
  3. A TABLE IN THE NEIGHBOURING 1.7, WHICH MUST **NOT** BE BLAMED ON 1.6. This is the arm that
     matters. Section 1.7 was added in the same pass, and the old block boundary ran to the next
     `##` -- so it swallowed 1.7 whole and would have read a neighbour's table as 1.6's own. The
     boundary is now the next `##` OR `###`. Mutation 3 must therefore be **MISSED**, and a
     mutation that is supposed to be missed is the only kind that can catch an over-wide needle.

`CLAUDE.md` is mutated in BYTES and restored from the bytes read first, with the restoration
asserted. `.gitattributes` forbids translating line endings and `Path.write_text` does exactly
that here, so nothing in this file goes near it.

    uv run python tests/test_claims_contents_cut.py
"""
import os
import subprocess
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parent.parent
CMD = ROOT / "CLAUDE.md"
ENV = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1",
           PYTHONDONTWRITEBYTECODE="1")

HEADING_16 = "### 1.6 Contents"
HEADING_17 = "### 1.7 The size class, and the cap this charter is held to"
POINTER_16 = "**CUT 2026-08-24 AND MUST NOT COME BACK**"

TABLE = ("| § | section | what it covers |\n"
         "|---|---|---|\n"
         "| **1** | How to read this document | navigation |\n"
         "| **7** | Current status | the handoff |")

# (label, needle to REPLACE, what to replace it with, must the check FAIL?)
#
# EACH MUTATION IS A REPLACEMENT, NOT AN INSERTION, and mutation 2 is why. Written first as
# "plant text after the 1.6 heading", it was MISSED -- correctly, because appending prose does
# not remove the pointer that was already there, so nothing was actually broken. The mutation
# was wrong, not the check. A mutation that does not create the condition it names proves the
# check blind when the check was right, which is the same false alarm this project keeps logging
# in its own instruments, one level up.
MUTATIONS = [
    ("1  the contents table is BACK in 1.6",
     HEADING_16, HEADING_16 + "\n\n" + TABLE, True),
    ("2  the POINTER is deleted, so nothing explains the absence",
     POINTER_16, "**There used to be something here**", True),
    ("3  a table in the NEIGHBOURING 1.7 - must be MISSED",
     HEADING_17, HEADING_17 + "\n\n" + TABLE, False),
]


def run_claims():
    r = subprocess.run(["uv", "run", "python", str(ROOT / "tools" / "claudemd_claims.py")],
                       capture_output=True, text=True, encoding="utf-8", errors="replace",
                       cwd=str(ROOT), env=ENV, timeout=600)
    return r.returncode, r.stdout + r.stderr


def check14_failed(out):
    return any("[FAIL] 14:" in line for line in out.splitlines())


original = CMD.read_bytes()
for _, needle, _, _ in MUTATIONS:
    assert original.count(needle.encode("utf-8")) == 1, \
        f"needle {needle!r} is not present exactly once; fix this test, do not skip it"

print("=" * 96)
print("BASELINE — check 14 must PASS on the unmutated charter")
print("=" * 96)
rc, out = run_claims()
verdict_line = next((l.strip() for l in out.splitlines() if "§1.6 carries the pointer" in l), "")
print(f"  exit {rc} · check 14 failed: {check14_failed(out)}")
print(f"  {verdict_line}")
if check14_failed(out):
    print("  VOID — check 14 is already failing, so a mutation proving it can fail establishes")
    print("  nothing. Fix the charter or the tool first. An unreadable baseline is not a pass.")
    sys.exit(1)

results = []
try:
    for label, needle, replacement, must_fail in MUTATIONS:
        print("\n" + "=" * 96)
        print(f"MUTATION {label}")
        print("=" * 96)
        eol = b"\r\n" if original.count(b"\r\n") else b"\n"
        was = needle.encode("utf-8")
        now = replacement.replace("\n", eol.decode("ascii")).encode("utf-8")
        mutated = original.replace(was, now, 1)
        assert mutated != original, "mutation changed nothing"
        CMD.write_bytes(mutated)
        rc, out = run_claims()
        detected = check14_failed(out)
        print(f"  replaced {needle!r}")
        print(f"  exit {rc} · check 14 failed: {detected} · required: {must_fail}")
        for line in out.splitlines():
            if "[FAIL] 14:" in line:
                print(f"    {line.strip()}")
        results.append((label, detected, must_fail))
finally:
    CMD.write_bytes(original)
    assert CMD.read_bytes() == original, "RESTORATION FAILED — CLAUDE.md is not as it was"

print("\n" + "=" * 96)
print("VERDICT")
print("=" * 96)
for label, detected, must_fail in results:
    correct = detected == must_fail
    if must_fail:
        word = "DETECTED    " if correct else "MISSED      "
    else:
        word = "CORRECTLY IGNORED  " if correct else "FALSE POSITIVE     "
    print(f"  {word}{label}")
print()
good = sum(1 for _, d, m in results if d == m)
print(f"  {good} of {len(results)} arms behaved as required "
      f"({sum(1 for _, _, m in results if m)} must fail, "
      f"{sum(1 for _, _, m in results if not m)} must not).")
print("  CLAUDE.md restored byte-for-byte, asserted rather than assumed.")
sys.exit(0 if good == len(results) else 1)
