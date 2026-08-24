# -*- coding: utf-8 -*-
"""CAN `claudemd_claims.py`'s CHECK 3 STILL FAIL, now that the counts it checked have moved?

Check 3 asserts every register count `CLAUDE.md` states against the register's own rows. Phase 3a
step 3 removed the count blockquote from 2.3 -- `audit_register.py` prints those figures, and 1.5
records the one time a session reasoned from this file's summary of the register instead of the
register and was wrong.

**THAT LEFT THE CHECK WITH ALMOST NOTHING TO ASSERT, AND ITS OWN COMMENT NAMES THE DANGER:** a
needle reporting "no occurrence" is *"the quiet way for a check to stop checking"*. So the check now
reads a DECLARATION in the charter and branches on it. Three arms, three mutations:

  1. **the declaration is deleted** while the counts are still absent -> every missing count must
     FAIL, because that is exactly the quiet stop;
  2. **a WRONG count is reintroduced** -> the assertion must still fire, so moving the figures out
     has not made the check blind to a figure coming back wrong;
  3. **the RIGHT count is reintroduced** -> must NOT fail. A check that cannot tell a correct
     restatement from an incorrect one would make the charter unmaintainable.

Arm 3 is the one that matters: a mutation required to be MISSED is the only kind that catches a
check which has started failing indiscriminately.

`CLAUDE.md` is mutated in BYTES and restored from the bytes read first, with the restoration
asserted. `.gitattributes` forbids translating line endings and `Path.write_text` does exactly
that here, so nothing in this file goes near it.

    uv run python tests/test_claims_counts_moved.py
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

DECLARATION = "THE EVIDENCE-BASE COUNTS ARE NO LONGER TYPED HERE"
ANCHOR = "## 7. Current status"

# The register's real figures, so arm 3 plants a CORRECT one. Taken from the checker's own
# derivation line rather than typed: if the register changes, this test must not go stale.
def truth(key):
    r = subprocess.run(["uv", "run", "python", str(ROOT / "tools" / "claudemd_claims.py")],
                       capture_output=True, text=True, encoding="utf-8", errors="replace",
                       cwd=str(ROOT), env=ENV, timeout=600)
    for line in (r.stdout + r.stderr).splitlines():
        if "derived from FINDINGS-REGISTER.md" in line:
            for part in line.split():
                if part.startswith(key + "="):
                    return part.split("=", 1)[1]
    return None


CLUSTERS = truth("clusters")
if not CLUSTERS:
    print("  VOID — could not read the register's cluster count from the checker's own output,")
    print("  so arm 3 cannot plant a correct figure. An unreadable source is not a pass.")
    sys.exit(2)
print(f"  the register has {CLUSTERS} clusters, read from the checker, not typed")

# (label, needle to REPLACE, replacement, must check 3 FAIL?)
MUTATIONS = [
    ("1  the declaration is DELETED, counts still absent",
     DECLARATION, "The counts live somewhere, probably", True),
    ("2  a WRONG cluster count is reintroduced",
     ANCHOR, "The register has 99 clusters.\n\n" + ANCHOR, True),
    ("3  the RIGHT cluster count is reintroduced - must be MISSED",
     ANCHOR, f"The register has {CLUSTERS} clusters.\n\n" + ANCHOR, False),
]


def run_claims():
    r = subprocess.run(["uv", "run", "python", str(ROOT / "tools" / "claudemd_claims.py")],
                       capture_output=True, text=True, encoding="utf-8", errors="replace",
                       cwd=str(ROOT), env=ENV, timeout=600)
    return r.returncode, r.stdout + r.stderr


def check3_failed(out):
    return any("[FAIL] 3:" in line for line in out.splitlines())


original = CMD.read_bytes()
for _, needle, _, _ in MUTATIONS:
    assert original.count(needle.encode("utf-8")) == 1, \
        f"needle {needle!r} is not present exactly once; fix this test, do not skip it"

print("=" * 100)
print("BASELINE — check 3 must PASS on the unmutated charter")
print("=" * 100)
rc, out = run_claims()
print(f"  exit {rc} · check 3 failed: {check3_failed(out)}")
if check3_failed(out):
    print("  VOID — check 3 is already failing, so a mutation proving it can fail establishes")
    print("  nothing. Fix the charter or the tool first.")
    sys.exit(1)

results = []
try:
    for label, needle, replacement, must_fail in MUTATIONS:
        print("\n" + "=" * 100)
        print(f"MUTATION {label}")
        print("=" * 100)
        eol = b"\r\n" if original.count(b"\r\n") else b"\n"
        was = needle.encode("utf-8")
        now = replacement.replace("\n", eol.decode("ascii")).encode("utf-8")
        mutated = original.replace(was, now, 1)
        assert mutated != original, "mutation changed nothing"
        CMD.write_bytes(mutated)
        rc, out = run_claims()
        detected = check3_failed(out)
        print(f"  exit {rc} · check 3 failed: {detected} · required: {must_fail}")
        for line in out.splitlines():
            if "[FAIL] 3:" in line:
                print(f"    {line.strip()[:150]}")
        results.append((label, detected, must_fail))
finally:
    CMD.write_bytes(original)
    assert CMD.read_bytes() == original, "RESTORATION FAILED — CLAUDE.md is not as it was"

print("\n" + "=" * 100)
print("VERDICT")
print("=" * 100)
for label, detected, must_fail in results:
    correct = detected == must_fail
    if must_fail:
        word = "DETECTED           " if correct else "MISSED             "
    else:
        word = "CORRECTLY IGNORED  " if correct else "FALSE POSITIVE     "
    print(f"  {word}{label}")
good = sum(1 for _, d, m in results if d == m)
print(f"\n  {good} of {len(results)} arms behaved as required "
      f"({sum(1 for _, _, m in results if m)} must fail, "
      f"{sum(1 for _, _, m in results if not m)} must not).")
print("  CLAUDE.md restored byte-for-byte, asserted rather than assumed.")
sys.exit(0 if good == len(results) else 1)
