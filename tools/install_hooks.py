# -*- coding: utf-8 -*-
"""INSTALL THE GIT HOOKS, and check they actually bite.

NOT THE HOUSE SCRIPT OF THE SAME NAME, AND NOT A FORK OF IT (declared 2026-09-09). The house
`standard-scripts/install_hooks.py` installs the HOUSE hooks -- the `pre-push` accident guard
and the AUTO MODE guard. This one installs THIS project's hooks from `tools/hooks/`: the
pre-commit confidentiality gate and the cycle gate. They share a name and nothing else, so a
byte comparison against the shared folder reports a difference that is not drift.

WHY THAT MATTERS RATHER THAN BEING A CURIOSITY. `check_checkers.py` tracks THIRTEEN scripts
and this is not one of them, so its `0 needing a decision` is true of the thirteen and silent
about this file. Anyone diffing `tools/` against `standard-scripts/` will find two mismatches
-- this and nothing else, since `trace_instructions.py` was brought to house v5 on the same
day -- and both of them should stop at this paragraph rather than turn into a repair.

Hooks live in `.git/hooks/`, which is not tracked, so they do not travel with a clone. That
makes them easy to believe in and easy to not have. This installer copies them from
`tools/hooks/` and then VERIFIES each one is present and executable, because an
un-executable hook is silently ignored by Git -- it does not warn, it just does nothing,
which is the worst behaviour a control can have.

    uv run python tools/install_hooks.py
    uv run python tools/install_hooks.py --check    # verify only, install nothing
"""
import io
import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "tools" / "hooks"
CHECK = "--check" in sys.argv

r = subprocess.run(["git", "rev-parse", "--git-path", "hooks"], capture_output=True,
                   text=True, cwd=ROOT)
if r.returncode != 0:
    print("  not a git repository")
    sys.exit(2)
DST = (ROOT / r.stdout.strip()).resolve()

print("=" * 92)
print("GIT HOOKS")
print("=" * 92)
print(f"  from {SRC.relative_to(ROOT)}  ->  {DST}")

problems = []
for src in sorted(SRC.iterdir()):
    if src.name.startswith("."):
        continue
    dst = DST / src.name
    if not CHECK:
        DST.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dst)
        os.chmod(dst, os.stat(dst).st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    if not dst.exists():
        problems.append(f"{src.name}: not installed")
        state = "MISSING"
    elif dst.read_bytes() != src.read_bytes():
        problems.append(f"{src.name}: installed copy differs from tools/hooks/")
        state = "STALE — differs from source"
    elif not os.access(dst, os.X_OK):
        problems.append(f"{src.name}: not executable, so Git will silently ignore it")
        state = "NOT EXECUTABLE"
    else:
        state = "installed, executable"
    print(f"  {src.name:<14} {state}")

print()
print("  What these are and are not:")
print("    pre-commit  runs the confidentiality gate and blocks on failure OR on a control")
print("                that could not run at all.")
print("    pre-push    refuses a direct push to main, because every branch goes through a")
print("                reviewed pull request.")
print("    Both are LOCAL accident guards. They do not travel with a clone and either can")
print("    be bypassed. Server-side branch protection is the real control and is currently")
print("    unavailable on this repository — see the note in tools/hooks/pre-push.")
print("=" * 92)
if problems:
    for p in problems:
        print(f"  PROBLEM: {p}")
    sys.exit(1)
print("  All hooks present and executable.")
