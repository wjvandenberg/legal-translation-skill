# -*- coding: utf-8 -*-
"""CAN `claudemd_claims.py`'s CHECK 6 STILL FAIL? Two mutations, and the second is the point.

Check 6 asks whether every `.py` file `CLAUDE.md` names actually exists. It has now been widened
three times, and each widening was the same defect one directory further out:

  * it could not see `tools/` or `tests/` at all (fixed 2026-08-11);
  * its pattern understood only a `temp/` prefix, so `tools/gate_replay.py` in backticks matched
    NOTHING and was silently never checked, while the bare `gate_replay.py` matched and failed to
    resolve -- so the verdict depended on how the author punctuated the reference (same day);
  * and `tests/probe-5b/preflight.py` reproduced that exactly, because the pattern could not cross
    a second path segment or a hyphen (fixed 2026-08-18).

**A SILENTLY-SKIPPED REFERENCE IS THE FAILURE MODE, NOT A MISSING ONE.** A missing file is
reported loudly. A reference the pattern cannot parse is reported as nothing at all, and the check
prints a clean count that is clean because it looked at less than it claimed. So mutation 2 below
plants an absent script behind a DEEP, HYPHENATED path prefix -- the exact spelling that used to
be invisible -- and requires check 6 to fail on it.

`CLAUDE.md` is mutated in BYTES and restored from the bytes read first, with the restoration
asserted. `.gitattributes` forbids translating line endings and `Path.write_text` does exactly
that here, so nothing in this file goes near it.

    uv run python tests/test_claims_script_names.py
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

# An anchor that appears exactly once and is not itself a claim, so planting text after it
# cannot change any other check's answer.
ANCHOR = "## 7. Current status"

MUTATIONS = [
    ("1  a bare name that exists nowhere",
     "`no_such_script_bare.py`"),
    ("2  the same absence behind a DEEP, HYPHENATED prefix — the spelling that was skipped",
     "`tests/probe-5b/no_such_script_prefixed.py`"),
]


def run_claims():
    r = subprocess.run(["uv", "run", "python", str(ROOT / "tools" / "claudemd_claims.py")],
                       capture_output=True, text=True, encoding="utf-8", errors="replace",
                       cwd=str(ROOT), env=ENV, timeout=600)
    return r.returncode, r.stdout + r.stderr


def check6_failed(out):
    return any("[FAIL] 6:" in line for line in out.splitlines())


original = CMD.read_bytes()
assert ANCHOR.encode("utf-8") in original, "anchor not found; fix this test, do not skip it"

print("=" * 96)
print("BASELINE — check 6 must PASS on the unmutated charter")
print("=" * 96)
rc, out = run_claims()
named = next((l.strip() for l in out.splitlines() if "named .py files exist" in l), "")
print(f"  exit {rc} · check 6 failed: {check6_failed(out)}")
print(f"  {named}")
if check6_failed(out):
    print("  VOID — check 6 is already failing, so a mutation proving it can fail establishes")
    print("  nothing. Fix the charter or the tool first.")
    sys.exit(1)

results = []
try:
    for label, planted in MUTATIONS:
        print("\n" + "=" * 96)
        print(f"MUTATION {label}")
        print("=" * 96)
        eol = b"\r\n" if original.count(b"\r\n") else b"\n"
        marker = ANCHOR.encode("utf-8")
        mutated = original.replace(
            marker, marker + eol + eol + planted.encode("utf-8"), 1)
        assert mutated != original, "mutation planted nothing"
        CMD.write_bytes(mutated)
        rc, out = run_claims()
        detected = check6_failed(out)
        print(f"  planted {planted}")
        print(f"  exit {rc} · check 6 failed: {detected}")
        for line in out.splitlines():
            if "[FAIL] 6:" in line:
                print(f"    {line.strip()}")
        results.append((label, detected))
finally:
    CMD.write_bytes(original)
    assert CMD.read_bytes() == original, "RESTORATION FAILED — CLAUDE.md is not as it was"

print("\n" + "=" * 96)
print("VERDICT")
print("=" * 96)
for label, detected in results:
    print(f"  {'DETECTED    ' if detected else 'MISSED      '}{label}")
print()
print(f"  {sum(1 for _, d in results if d)} of {len(results)} mutations detected.")
print("  CLAUDE.md restored byte-for-byte, asserted rather than assumed.")
sys.exit(0 if all(d for _, d in results) else 1)
