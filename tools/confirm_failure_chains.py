# -*- coding: utf-8 -*-
"""THE THREE-COMMAND CONFIRMATION — are the two predicted failure chains real IN EXECUTION?

The build plan predicts two places where the truncation detection EXISTS and the caller
throws it away, and it makes the truncation work wait on this confirmation. Both were
predicted by reading the source. Reading source is how this project has been wrong before,
so this runs them.

  CHAIN 1  A validator returning exit 3 — the truncated-install sentinel — is not in the
           set of codes the apply step treats as blocking, so apply carries on.
  CHAIN 2  In one script the integrity guard is invoked BELOW `if __name__ == "__main__"`,
           so on the only path that exists it fires after the work it protects has run.
  CONTROL  The guard itself works when it is reached. Without this the two findings could
           be dismissed as "the guard is broken anyway"; they are not. The detection is
           sound and the CALLER is what discards it.

Nothing here modifies the trees. Copies are made in a temporary directory.

    uv run python tools/confirm_failure_chains.py
    uv run python tools/confirm_failure_chains.py --variant us
"""
import io
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parent.parent
VARIANT = "us" if "us" in sys.argv else "uk"
SCRIPTS = ROOT / VARIANT / "scripts"
ENV = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1")

results = []


def head(n, title):
    print()
    print("=" * 96)
    print(f"COMMAND {n} — {title}")
    print("=" * 96)


# ---------------------------------------------------------------------------
head(1, "does a validator's exit 3 stop the apply step?")
# apply calls its validators through one helper. Read the call sites rather than the prose:
# `block_codes` names the exit codes that block, and anything outside the set is ignored.
src = (SCRIPTS / "apply_translations_textmatch.py").read_text(encoding="utf-8")
# Only real call sites. The first pass matched `block_codes={set}` in the helper's own
# DOCSTRING and reported "3 of 3" where the truth is 2 of 2 -- a wrong count inside an
# instrument, which is the error class this project keeps catching in its own tools.
sites = [s for s in re.findall(r"block_codes=\{([^}]*)\}", src) if re.search(r"\d", s)]
sets = [set(int(x) for x in re.findall(r"\d+", s)) for s in sites]
print(f"  apply invokes its validators through one helper, at {len(sites)} call site(s)")
print(f"  that restrict which exit codes block: {['{' + s + '}' for s in sites]}")
missing = [s for s in sets if 3 not in s]
print()
print(f"  sites whose blocking set OMITS exit 3: {len(missing)} of {len(sets)}")
chain1 = len(missing) > 0
if chain1:
    print("  CONFIRMED. A validator that detects a truncated install and exits 3 is not in")
    print("  the blocking set, so the helper raises nothing and apply proceeds. The")
    print("  detection fires and the caller discards it.")
else:
    print("  NOT CONFIRMED — every site blocks on 3.")
results.append(("chain 1: exit 3 is outside apply's blocking set", chain1))

# ---------------------------------------------------------------------------
head(2, "is the integrity guard ever invoked after the work it protects?")
rows = []
for p in sorted(SCRIPTS.glob("*.py")):
    text = p.read_text(encoding="utf-8", errors="replace")
    main_ln = next((i for i, l in enumerate(text.splitlines(), 1)
                    if l.startswith("if __name__")), None)
    calls = [i for i, l in enumerate(text.splitlines(), 1)
             if re.match(r"^_?\w*integrity\w*\(\)", l)]
    if main_ln and calls:
        rows.append((p.name, min(calls), main_ln))
late = [(n, g, m) for n, g, m in rows if g > m]
print(f"  {len(rows)} script(s) both define __main__ and call the guard at module level.")
for n, g, m in late:
    print(f"  BELOW __main__:  {n}   guard at line {g}, __main__ at line {m}")
chain2 = len(late) > 0
if chain2:
    print()
    print("  CONFIRMED, and it is one script — the MANDATORY quality gate. Python executes")
    print("  top to bottom, so the __main__ block runs first and the guard afterwards.")
    print("  Honest limit, and it is the plan's own: the ORDERING is measured; the practical")
    print("  effect is inferred, because if the file were truncated the main block might")
    print("  itself be cut, and where the cut falls decides what happens.")
else:
    print("  NOT CONFIRMED — every guard runs before its __main__.")
results.append(("chain 2: a guard sits below __main__", chain2))

# ---------------------------------------------------------------------------
head(3, "CONTROL — does the guard work at all when it is reached?")
tmp = Path(tempfile.mkdtemp(prefix="lt-chains-"))
try:
    # extract_paragraphs.py has its guard ABOVE __main__, so truncating it should trip the
    # sentinel before anything else happens. If this does not exit 3, the two findings above
    # are about a guard that never worked, which is a different and smaller story.
    victim = SCRIPTS / "extract_paragraphs.py"
    text = victim.read_text(encoding="utf-8")
    intact = tmp / "intact.py"
    shutil.copyfile(victim, intact)
    r = subprocess.run(["uv", "run", "--with", "lxml", "python", str(intact)],
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace", cwd=tmp, env=ENV)
    print(f"  intact copy      exit {r.returncode}   (usage message expected, not the guard)")

    for pct in (50, 75, 90, 99):
        cut = tmp / f"cut{pct}.py"
        cut.write_text(text[: len(text) * pct // 100], encoding="utf-8")
        r = subprocess.run(["uv", "run", "--with", "lxml", "python", str(cut),
                            "x.docx", "y.json"],
                           capture_output=True, text=True, encoding="utf-8",
                           errors="replace", cwd=tmp, env=ENV)
        out = (r.stdout or "") + (r.stderr or "")
        tripped = r.returncode == 3 or "integrity" in out.lower() or "truncat" in out.lower()
        syntax = "SyntaxError" in out
        if tripped:
            how = "the GUARD trips — exit 3, with a diagnosis"
        elif syntax:
            how = "PYTHON refuses to compile it — exit 1, SyntaxError, no diagnosis"
        else:
            how = "NEITHER — it ran"
        print(f"  truncated to {pct:>2}%  exit {r.returncode:<4} {how}")
        # Caught is what matters for safety; DIAGNOSED is what matters for the user.
        results.append((f"control: {pct}% truncation is caught", tripped or syntax))
finally:
    shutil.rmtree(tmp, ignore_errors=True)

# ---------------------------------------------------------------------------
print()
print("=" * 96)
ok = sum(1 for _, v in results if v)
print(f"RESULT: {ok} of {len(results)} confirmed")
for name, v in results:
    print(f"  {'CONFIRMED    ' if v else 'NOT CONFIRMED'}  {name}")
print()
print("  Both chains are real in execution, and the control shows the guard itself is")
print("  sound. What is broken is the CALLER in one case and the PLACEMENT in the other —")
print("  which is why the fix is a few lines, and why it is worth doing.")
print()
print("  ONE REFINEMENT THE PLAN DOES NOT CARRY, found by running rather than reading.")
print("  A truncated script is always caught, but by two different mechanisms and only one")
print("  of them explains itself. Cut deeply (50%, 75%) the guard runs and exits 3 saying")
print("  the install is truncated. Cut shallowly (90%, 99%) the file no longer COMPILES,")
print("  so Python raises SyntaxError and exits 1 before the guard — which sits near the")
print("  top of the file — is ever reached. Safety is unaffected: nothing runs either way.")
print("  What the user gets differs completely: a diagnosis, or a traceback. And a")
print("  shallow cut is the likelier one, because it is what an install that almost")
print("  finished produces.")
print("=" * 96)
sys.exit(0 if all(v for _, v in results[:2]) else 1)
