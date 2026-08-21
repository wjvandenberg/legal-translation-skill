# -*- coding: utf-8 -*-
"""THE THREE-COMMAND CONFIRMATION — are the two predicted failure chains CLOSED in execution?

**THIS TOOL'S QUESTION INVERTED AT BRANCH 5, AND THE INVERSION IS THE POINT.** It was built
to prove that two predicted failure chains were real, and it did: branch 5's own work waited
on that confirmation. Branch 5 then fixed both. A tool that asserts a defect exists becomes a
tool that FAILS when the defect is repaired — so it now asserts the repair instead, and keeps
failing if either chain ever reopens. The alternative was to delete it, which would have
thrown away the only standing regression guard on both fixes.

  CHAIN 1  A validator returning exit 3 — the truncated-install sentinel — was outside the
           set of codes the apply step treats as blocking, so apply printed
           "returned WARN (exit 3). Continuing." Must now BLOCK.
  CHAIN 2  In one script the integrity guard was invoked BELOW `if __name__ == "__main__"`,
           so on the only path that exists it fired after the work it protects had run.
           Must now sit ABOVE it, in all twenty scripts.
  CONTROL  The guard itself works when it is reached. UNCHANGED BY BRANCH 5 and deliberately
           left alone: without it the two findings could have been dismissed as "the guard is
           broken anyway", and with the fixes in place it is what proves the repairs did not
           quietly disable the thing they were protecting.

CHAIN 1 IS NOW MEASURED BEHAVIOURALLY RATHER THAN BY PROXY, and that change was forced. The
original test asked whether 3 appeared in the `block_codes` sets — a sound proxy while that
was the only mechanism, and a WRONG one afterwards: branch 5 blocks exit 3 in an explicit
test BEFORE block_codes is consulted, so the sets still omit 3 and the proxy still reported
the defect as live. Running the helper answers the question the tool's own title asks.

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
import tokenize
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# NO BYTECODE INSIDE THE SHIPPED TREES. Chain 1 now IMPORTS a skill module in order to drive
# the real helper, and an import drops a __pycache__ directory into uk/scripts or us/scripts.
# The env var below covers subprocesses and cannot reach an in-process import; this covers the
# import. Both are needed, and the second is the one that keeps getting forgotten — the leak
# has now arrived through three separate callers.
sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parent.parent
VARIANT = "us" if "us" in sys.argv else "uk"
SCRIPTS = ROOT / VARIANT / "scripts"
ENV = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1",
           PYTHONDONTWRITEBYTECODE="1")

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
def strip_comments(text):
    """Remove comment tokens, keeping code and string literals intact.

    A REGEX OVER SOURCE COUNTS A MECHANISM WHEREVER A MESSAGE MERELY DESCRIBES IT, and this
    tool has now been bitten by that twice on the same line. The first pass matched
    `block_codes={set}` in the helper's own DOCSTRING and reported "3 of 3" where the truth
    was 2 of 2; the digit filter below fixed that. Branch 5 then added a COMMENT explaining
    the exit-3 test, which contains the literal `block_codes={2}` -- digits and all -- and
    both this tool and tools/audit_branches.py went straight back to reporting 3 sites.
    Filtering on shape cannot separate code from prose about code; tokenising can.

    BLANK THE COMMENT SPANS IN PLACE; do not rebuild the source from tokens. Joining token
    strings back together destroys the layout the regex depends on -- `block_codes={2}` comes
    back as five tokens on five lines and matches nothing. The first version of this function
    did exactly that and took the count from 3 to ZERO, which is worse than the 3 it was
    fixing: a check reporting on an empty population, passing because it found nothing.
    """
    lines = text.splitlines(keepends=True)
    try:
        toks = list(tokenize.generate_tokens(io.StringIO(text).readline))
    except (tokenize.TokenError, IndentationError):
        return text                      # never silently return LESS than we were given
    for tok in toks:
        if tok.type == tokenize.COMMENT:
            (r1, c1), (r2, c2) = tok.start, tok.end
            if r1 == r2:
                ln = lines[r1 - 1]
                lines[r1 - 1] = ln[:c1] + " " * (c2 - c1) + ln[c2:]
    return "".join(lines)


src_raw = (SCRIPTS / "apply_translations_textmatch.py").read_text(encoding="utf-8")
src = strip_comments(src_raw)
# Only real call sites: comments stripped above, and the digit filter still excludes the
# helper's own docstring, which writes the parameter as `block_codes={set}`.
sites = [s for s in re.findall(r"block_codes=\{([^}]*)\}", src) if re.search(r"\d", s)]
sets = [set(int(x) for x in re.findall(r"\d+", s)) for s in sites]
print(f"  apply invokes its validators through one helper, at {len(sites)} call site(s)")
# ASSERT THE READ COUNT, NOT ONLY THE RESULT. §5.1: a control that opened no files must say
# VOID, never CLEAN. Zero call sites means the scan found nothing to look at -- which is what
# a broken comment-stripper produced here, silently, while the tool still printed 6 of 6.
if not sites:
    print("  VOID FOR THIS ARM — zero call sites found. apply has always had at least two,")
    print("  so this is a defect in the scan and not a finding about the code.")
    results.append(("chain 1 static scan read a non-empty population", False))
print(f"  that restrict which exit codes block: {['{' + s + '}' for s in sites]}")
missing = [s for s in sets if 3 not in s]
print()
print(f"  sites whose blocking set OMITS exit 3: {len(missing)} of {len(sets)}")
print("  (still all of them, and that is now IRRELEVANT rather than damning — exit 3 is")
print("   tested explicitly before block_codes is consulted. Reported because a reader")
print("   who greps for `block_codes` will see the omission and needs to know why it is")
print("   not the defect it used to be.)")

# BEHAVIOURAL, NOT STATIC. Drive the real helper with a probe that exits 3 and see whether it
# raises. This is what makes the tool's title honest: "in execution".
print()
sys.path.insert(0, str(SCRIPTS))
import importlib                                                             # noqa: E402
_ap = importlib.import_module("apply_translations_textmatch")
probe = [sys.executable, "-c", "import sys; sys.exit(3)"]
try:
    _ap._run_validator("PROBE — a validator that exits 3", probe, block_codes={2})
    blocked, why = False, "the helper returned normally"
except RuntimeError as exc:
    blocked, why = True, str(exc)[:70] + "..."
chain1_closed = blocked
print(f"  driving the real helper with an exit-3 probe under block_codes={{2}}:")
print(f"    raised: {blocked}   ({why})")
if chain1_closed:
    print("  CLOSED. A validator that detects a truncated install and exits 3 now stops the")
    print("  apply step. The message names it as an install problem rather than a gate, so")
    print("  the operator is sent to re-install rather than to re-author paragraphs.json.")
else:
    print("  REOPENED — exit 3 no longer blocks. This is register row W3 returning: the")
    print("  detection fires and the caller discards it. Do not ship this.")
results.append(("chain 1 CLOSED: exit 3 stops the apply step", chain1_closed))

# ---------------------------------------------------------------------------
head(2, "is the integrity guard ever invoked after the work it protects?")
rows = []
defined_but_uncalled = []
for p in sorted(SCRIPTS.glob("*.py")):
    text = p.read_text(encoding="utf-8", errors="replace")
    main_ln = next((i for i, l in enumerate(text.splitlines(), 1)
                    if l.startswith("if __name__")), None)
    calls = [i for i, l in enumerate(text.splitlines(), 1)
             if re.match(r"^_?\w*integrity\w*\(\)", l)]
    if main_ln and calls:
        rows.append((p.name, min(calls), main_ln))
    elif "def _check_self_integrity" in text and not calls:
        # A SCRIPT THAT DEFINES THE GUARD AND NEVER CALLS IT AT MODULE LEVEL, which is
        # strictly worse than calling it late and which this check used to WAVE THROUGH.
        # Found by a negative test in tests/test_checks_can_fail.py: the mutation deleted
        # the call rather than moving it, the script then dropped out of `rows` entirely,
        # `late` was empty, and the tool reported the chain CLOSED. A check whose subject
        # can disappear from its own population is the failure class this project logs more
        # than any other.
        defined_but_uncalled.append(p.name)
late = [(n, g, m) for n, g, m in rows if g > m]
print(f"  {len(rows)} script(s) both define __main__ and call the guard at module level.")
for n, g, m in late:
    print(f"  BELOW __main__:  {n}   guard at line {g}, __main__ at line {m}")
for n in defined_but_uncalled:
    print(f"  DEFINES THE GUARD AND NEVER CALLS IT:  {n}")
chain2_closed = len(late) == 0 and len(defined_but_uncalled) == 0
if chain2_closed:
    print(f"  ALL {len(rows)} call the guard ABOVE their __main__.")
    print()
    print("  CLOSED. It was one script — the MANDATORY quality gate, and the only one of the")
    print("  twenty placed that way, which is why the repair was a move back to the house")
    print("  pattern rather than a new idea.")
else:
    print()
    if late:
        print("  REOPENED — a guard sits below its __main__ again. Python executes top to")
        print("  bottom, so that script's work runs and prints before the guard is reached.")
    if defined_but_uncalled:
        print("  WORSE THAN REOPENED — a script defines the guard and never invokes it, so")
        print("  the detection cannot fire at all. Truncating that file is silent.")
    print("  Register row W4. Do not ship this.")
results.append(("chain 2 CLOSED: every guard runs before its __main__", chain2_closed))

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
print(f"RESULT: {ok} of {len(results)} hold")
for name, v in results:
    print(f"  {'HOLDS      ' if v else 'BROKEN     '}  {name}")
print()
print("  Both chains are CLOSED in execution, and the control shows the guard itself still")
print("  works — which is the half that matters after a repair, because a fix that disabled")
print("  the detection would look identical to a fix that made the caller respect it.")
print()
print("  A REFINEMENT, CORRECTED AT BRANCH 5 — the earlier version of this text")
print("  over-generalised from a single file. A truncated script is always caught, but by")
print("  two mechanisms and only one of them explains itself: where the truncated file still")
print("  COMPILES the guard runs and exits 3 with a diagnosis, and where it does not Python")
print("  raises SyntaxError and exits 1 before the guard is reached, wherever the guard sits.")
print("  WHICH OF THE TWO YOU GET DEPENDS ON WHERE THE CUT LANDS IN A PARTICULAR FILE, and")
print("  not on how deep it is. Measured on extract_paragraphs.py above, deep cuts compile")
print("  and shallow ones do not; measured on quality_check.py the pattern is the OPPOSITE.")
print("  Safety is unaffected either way — nothing runs. What differs is whether the message")
print("  names the cause, and tests/test_checks_can_fail.py carries that measurement rather")
print("  than this tool, so the figure lives in one place.")
print("=" * 96)
# EVERY result counts toward the exit code, controls included. The earlier version exited on
# `results[:2]` alone, so a control that started failing -- the guard itself breaking -- would
# have been printed and then ignored.
sys.exit(0 if all(v for _, v in results) else 1)
