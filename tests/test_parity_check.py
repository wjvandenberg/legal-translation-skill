# -*- coding: utf-8 -*-
"""NEGATIVE TESTS FOR THE PARITY CHECK — mutate the trees to prove each arm can FAIL,
then restore them byte-identically.

The parity check reports 391 divergences on the day it is written, so it is tempting to call
it obviously working. It is not: what has to be proved is that it fires on a divergence that
is NOT already in the baseline, because catching new drift is its entire job. Every case here
therefore mutates a tree AFTER the baseline is recorded, and asserts the check notices.

Restoration is verified by SHA-256 against the git object store, not against a copy held in
memory — the trees are the baseline of the whole project and a test that damaged one would be
worse than no test.

    uv run python tests/test_parity_check.py
"""
import hashlib
import io
import subprocess
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parent.parent
CHECK = ROOT / "tools" / "parity_check.py"


def run():
    r = subprocess.run([sys.executable, str(CHECK)], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", cwd=ROOT)
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def write(p, text):
    with open(p, "w", encoding="utf-8", newline="") as fh:
        fh.write(text)


results = []
print("=" * 96)
print("NEGATIVE TESTS — can the parity check catch drift that is not already baselined?")
print("=" * 96)

rc, out = run()
print(f"\n  baseline state: exit {rc} "
      f"({'PASS — no divergence outside the baseline' if rc == 0 else 'NOT CLEAN'})")
if rc != 0:
    print("  Record the baseline first:  uv run python tools/parity_check.py --write-baseline")
    sys.exit(2)


def case(name, path, mutate, needle):
    p = ROOT / path
    before = p.read_bytes()
    want = hashlib.sha256(before).hexdigest()
    try:
        write(p, mutate(before.decode("utf-8")))
        rc, out = run()
        caught = rc == 1 and needle.lower() in out.lower()
        results.append((name, caught))
        print(f"  {'PASS' if caught else 'FAIL'}  {name}")
        if not caught:
            print(f"          exit {rc}; expected 1 and {needle!r} in the output")
    finally:
        p.write_bytes(before)
        got = sha(p)
        assert got == want, f"RESTORE FAILED for {path}"


# 1. A function gains a parameter in one tree only — the shape of the drift that is already
#    measured in the tidy-up script, reproduced somewhere the baseline does not cover.
case("a signature that changes in one tree only",
     "us/scripts/validate_en_runs.py",
     lambda t: t.replace("def main():", "def main(extra_argument=None):", 1),
     "signature")

# 2. A rule table gains an entry in one tree — the 37-versus-60 shape.
#    US_SPELLING is a LIST, not a dict. The first version of this case inserted a dict entry
#    after "US_SPELLING = {", which does not appear in the file at all, so it mutated nothing
#    and reported the CHECK as broken. A negative test that fails to make its own violation
#    is indistinguishable from a check that cannot see one.
case("a rule table whose length changes in one tree",
     "us/scripts/post_process.py",
     lambda t: t.replace("US_SPELLING = [",
                         "US_SPELLING = [\n    ('zzzprobe', 'zzzprobe'),", 1),
     "rule-table-length")

# 3. A dictionary row present in one tree only.
#    ADDING a row, not deleting one. That variant table has its columns reversed between the
#    two trees, so every row in it is ALREADY a baselined divergence — deleting one REMOVES a
#    known divergence rather than creating a new one, and the check was right to stay quiet.
case("a dictionary row added to one tree only",
     "us/references/general-legal.md",
     lambda t: t.replace("| favor, honor, color |",
                         "| zzzprobe term | zzzprobe gloss |\n| favor, honor, color |", 1),
     "dictionary-row")

# 4. WITHIN-TREE: a row rendering a variant-controlled term in one form only. This is the
#    arm that matters — the instance that reached a client was identically wrong in BOTH
#    trees, so no cross-tree comparison could ever have seen it.
def add_single_variant_row(t):
    lines = t.splitlines()
    for i, l in enumerate(lines):
        if l.startswith("|") and "|" in l[1:] and not set(l) <= set("|-: "):
            lines.insert(i + 2, "| zzz_probe_term | indemnity | probe row |")
            break
    return "\n".join(lines) + "\n"


case("a row rendering a variant-controlled term in ONE form only (within-tree)",
     "uk/sub-lexicons/dutch-general-legal.md",
     add_single_variant_row,
     "single-variant-row")

# 5. THE BASELINE MUST NOT SWALLOW A NEW DIVERGENCE. Mutating a file that already has
#    baselined divergences must still surface the NEW one rather than hide behind them.
case("a new divergence in a file that already has baselined ones",
     "us/scripts/quality_check.py",
     lambda t: t.replace("def check(", "def check_renamed_probe(", 1),
     "function-missing")

print()
print("=" * 96)
ok = sum(1 for _, c in results if c)
print(f"RESULT: {ok} of {len(results)} arms demonstrated able to catch new drift")
for name, c in results:
    if not c:
        print(f"    NOT DEMONSTRATED: {name}")

rc, out = run()
print(f"  trees restored: parity check exit {rc} "
      f"({'PASS' if rc == 0 else 'NOT CLEAN — INVESTIGATE'})")
print("=" * 96)
if rc != 0:
    sys.exit(2)
sys.exit(0 if ok == len(results) else 1)
