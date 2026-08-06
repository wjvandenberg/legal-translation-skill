# -*- coding: utf-8 -*-
"""THE SUITE. Run this on every change.

Three things, in order:

  1. FIXTURES        the synthetic documents build, and every one that should be a valid
                     .docx is one.
  2. NEGATIVE INPUTS every executable check is given an input built to violate its own
                     stated pass condition, AND a conforming one. A check has to fire on
                     the first and stay quiet on the second. One-sided testing would pass a
                     check that fires on everything, which is not a check.
  3. BYTE COMPARISON the pipeline's mechanical half is a deterministic function, so the
                     same input twice must produce identical bytes. This is what makes
                     `git bisect` possible: it is cheap, it is deterministic, and
                     "translate a document and grade it" is neither.

WHAT IT DELIBERATELY DOES NOT DO. It makes no quality judgement. No check here asks whether
the English reads well. The moment it does, it stops being repeatable and cannot serve as
the never-regress gate, which is the whole reason for building it.

Exit 0 = every check demonstrated able to fail and able to pass.

    uv run python tests/run_tests.py
    uv run python tests/run_tests.py --variant us
    uv run python tests/run_tests.py --quiet        # for git bisect
"""
import io
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import negative_inputs as NI  # noqa: E402

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parent.parent
VARIANT = "us" if "us" in sys.argv else "uk"
SCRIPTS = ROOT / VARIANT / "scripts"
QUIET = "--quiet" in sys.argv
FIXTURES = ROOT / "tests" / "fixtures"

failures, notes = [], []


def say(*a):
    if not QUIET:
        print(*a)


def run(script, args, cwd):
    """Run a skill script. `uv run --with lxml` because 7 of the 20 import lxml and the
    skill's own runtime supplies it.

    PYTHONIOENCODING IS NOT OPTIONAL HERE, and finding out why cost an hour. On Windows a
    redirected stdout defaults to cp1252, so any script printing a character outside it dies
    with UnicodeEncodeError before it can return its verdict. The harness then reads a
    non-zero exit and reports the check as firing -- on a clean input. It looked exactly
    like a check that cannot tell good from bad.

    The skill runs on Linux under UTF-8 in its real host, so this is the harness's problem
    to solve, not the skill's. But it surfaced a genuine portability defect on the way and
    that is recorded rather than papered over: see tests/README.md."""
    env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
    cmd = ["uv", "run", "--with", "lxml", "python", str(SCRIPTS / script), *args]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                           errors="replace", cwd=cwd, timeout=180, env=env)
        return r.returncode, (r.stdout or "") + (r.stderr or "")
    except subprocess.TimeoutExpired:
        return -1, "TIMED OUT"


# ===========================================================================
say("=" * 100)
say("1. FIXTURES")
say("=" * 100)
r = subprocess.run([sys.executable, str(ROOT / "tests" / "make_fixtures.py")],
                   capture_output=True, text=True, encoding="utf-8", cwd=ROOT)
if r.returncode != 0:
    failures.append("fixtures failed to build")
    say(r.stdout, r.stderr)
else:
    built = sorted(FIXTURES.glob("*.docx"))
    deliberately_bad = {"not-a-zip.docx", "truncated.docx"}
    ok = bad = 0
    for f in built:
        try:
            with zipfile.ZipFile(f):
                valid = True
        except zipfile.BadZipFile:
            valid = False
        want = f.name not in deliberately_bad
        if valid == want:
            ok += 1
        else:
            bad += 1
            failures.append(f"fixture {f.name}: validity {valid}, wanted {want}")
    say(f"  {len(built)} fixtures built · {ok} with the validity they should have"
        + (f" · {bad} WRONG" if bad else ""))

# ===========================================================================
say()
say("=" * 100)
say("2. NEGATIVE INPUTS — can each check fail, and does it still pass a clean input?")
say("=" * 100)

tmp = Path(tempfile.mkdtemp(prefix="lt-tests-"))
fired = mute = 0
try:
    for c in NI.CASES:
        script = c["check"]
        if not (SCRIPTS / script).exists():
            notes.append(f"{script}: not in the {VARIANT} tree")
            continue
        work = tmp / script.replace(".py", "") / str(len([1]))
        work = tmp / (script.replace(".py", "") + "-" + str(NI.CASES.index(c)))
        work.mkdir(parents=True, exist_ok=True)
        bad, good = c["build"](work)

        def invoke(target):
            args = []
            for tok in c["args"].split():
                if tok == "{in}":
                    args.append(str(target))
                elif tok == "{xml}":
                    args.append(str(work / "document.xml"))
                elif tok == "{out}":
                    args.append(str(work / "out.json"))
                else:
                    args.append(tok)
            return run(script, args, work)

        rc_bad, out_bad = invoke(bad)
        rc_good, out_good = invoke(good)

        caught = rc_bad != 0
        clean = rc_good == 0
        verdict = ("fires on the violation, quiet on the clean input" if caught and clean
                   else "DID NOT FIRE on the violation" if not caught
                   else "fires on the CLEAN input too — it cannot tell good from bad")
        if caught and clean:
            fired += 1
        else:
            mute += 1
            failures.append(f"{script} ({c['why']}): {verdict}")
        say(f"  {'OK ' if caught and clean else 'XX '} {script:<34} "
            f"bad→{rc_bad:<4} good→{rc_good:<4} {c['why']}")
        if not (caught and clean) and not QUIET:
            say(f"       {verdict}")
            say(f"       invoked    : {script} {' '.join(c['args'].split())}")
            say(f"       cwd        : {work}")
            for label, out in (("bad ", out_bad), ("good", out_good)):
                tail = [l for l in out.strip().splitlines()
                        if l.strip()][-4:] if out.strip() else ["(no output)"]
                for l in tail:
                    say(f"       {label} | {l[:110]}")

    say()
    say(f"  {fired} of {fired + mute} cases behave correctly")

    # =======================================================================
    say()
    say("=" * 100)
    say("3. BYTE COMPARISON — the mechanical half is a deterministic function")
    say("=" * 100)
    det_ok = det_bad = 0
    for fx in sorted(FIXTURES.glob("*.docx")):
        if fx.name in ("not-a-zip.docx", "truncated.docx"):
            continue
        w = tmp / ("det-" + fx.stem)
        w.mkdir(parents=True, exist_ok=True)
        a, b = w / "a.json", w / "b.json"
        rc1, _ = run("extract_paragraphs.py", [str(fx), str(a)], w)
        rc2, _ = run("extract_paragraphs.py", [str(fx), str(b)], w)
        if rc1 != 0 or rc2 != 0:
            det_bad += 1
            failures.append(f"byte comparison: extraction failed on {fx.name}")
            continue
        if a.read_bytes() == b.read_bytes():
            det_ok += 1
        else:
            det_bad += 1
            failures.append(f"byte comparison: {fx.name} extracted differently twice")
    say(f"  {det_ok} fixture(s) extract byte-identically twice"
        + (f" · {det_bad} DO NOT" if det_bad else ""))
    say("  This is the property `git bisect` rides on: cheap, deterministic, no model.")
finally:
    shutil.rmtree(tmp, ignore_errors=True)

# ===========================================================================
print()
print("=" * 100)
if notes:
    print("NOTES")
    for n in notes:
        print(f"  · {n}")
if failures:
    print(f"FAIL — {len(failures)} problem(s):")
    for f in failures:
        print(f"  · {f}")
    print("=" * 100)
    sys.exit(1)
print("PASS — every check fires on its violation and stays quiet on a clean input.")
print("=" * 100)
