# -*- coding: utf-8 -*-
"""INSTALL THE GIT HOOKS, and check they actually bite.

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
