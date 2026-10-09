# -*- coding: utf-8 -*-
"""NEGATIVE TESTS FOR THE CYCLE GATE — prove it can refuse, and refuse for the right reasons.

The gate exists because §5.1 was read and skipped past three times in one session. A gate
that has never been seen to refuse is worth exactly as much as the prose it replaced, so
every case here makes the violation and asserts the refusal.

It runs against the REAL evidence store, which it empties first and puts back byte-exact after,
through tools/inplace_guard.py. (This said "a THROWAWAY evidence store, never the real one" until
2026-10-08, which was never true.) A run killed half-way used to leave this test's own evidence -
a "verify" for `python -c pass`, bound to the current tree - where the commit gate would accept
it; now it leaves a guard record, and tools/precommit_gate.py refuses every commit until it is
settled (register I-37).

    uv run python tests/test_cycle_gate.py
"""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parent.parent
sys.dont_write_bytecode = True  # importing from tools/ must leave no bytecode there
sys.path.insert(0, str(ROOT / "tools"))
import inplace_guard as guard  # noqa: E402  (register I-37: a repository file changes only through it)
GATE = ROOT / "tools" / "cycle_evidence.py"
STORE = ROOT / "temp" / ".cycle-evidence.json"

results = []


def run(*args):
    r = subprocess.run([sys.executable, str(GATE), *args], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", cwd=ROOT)
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def case(name, got, want):
    ok = got == want
    results.append((name, ok))
    print(f"  {'PASS' if ok else 'FAIL'}  {name}")
    if not ok:
        print(f"          got {got!r}, wanted {want!r}")


print("=" * 92)
print("NEGATIVE TESTS — can the cycle gate actually refuse?")
print("=" * 92)

# Preserve the real store; these tests must never leave evidence behind - through the guard, so a
# kill cannot either (register I-37). protecting() records the store before anything touches it.
with guard.protecting(STORE):
    if STORE.exists():
        STORE.unlink()

    rc, out = run("check")
    case("with no evidence at all, check REFUSES", (rc, "no evidence for" in out), (1, True))

    rc, out = run("verify", "--", sys.executable, "-c", "import sys; sys.exit(1)")
    case("a command that exits non-zero is NOT recorded",
         (rc, "NOT recorded" in out), (1, True))
    case("...and leaves no evidence behind", STORE.exists(), False)

    rc, out = run("na", "verify", "short")
    case("a declared N/A with no real reason is REFUSED", rc, 1)

    rc, out = run("verify", "--", sys.executable, "-c", "pass")
    case("a command that exits 0 IS recorded", (rc, "recorded" in out), (0, True))

    rc, out = run("na", "test", "this branch changes no skill file, so §4 makes it "
                                "measurement-only and no graded run applies")
    case("a declared N/A WITH a reason is accepted", rc, 0)

    rc, out = run("check")
    case("with both phases satisfied, check PASSES", rc, 0)

    # THE ONE THAT MATTERS: evidence must die when the content moves under it. Without this
    # the gate is a trailer you type, and a trailer proves nothing.
    probe = ROOT / "temp" / "_cycle_probe.txt"
    with guard.planted(probe, b"changed after the evidence was recorded\n"), guard.staged(probe):
        rc, out = run("check")
        case("evidence goes STALE when content changes after it was recorded",
             (rc, "STALE" in out), (1, True))

print()
print("=" * 92)
ok = sum(1 for _, c in results if c)
print(f"RESULT: {ok} of {len(results)} behaviours demonstrated")
for name, c in results:
    if not c:
        print(f"    NOT DEMONSTRATED: {name}")
print()
print("  What this does NOT prove: that the recorded command was a GOOD one. Nothing can.")
print("  Two of this project's negative tests once passed while failing to make their own")
print("  violation. The gate proves a command ran against this content and exited zero.")
print("=" * 92)
sys.exit(0 if ok == len(results) else 1)
