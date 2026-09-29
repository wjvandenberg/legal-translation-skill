# -*- coding: utf-8 -*-
"""INSTALL THE GIT HOOKS, and check they actually bite.

NOT THE HOUSE `standard-scripts/install_hooks.py`, AND NOT A FORK OF IT (declared 2026-09-09).
The house script installs the HOUSE hooks -- the `pre-push` accident guard and the AUTO MODE
guard. This one installs THIS project's git hooks from `tools/hooks/`: the pre-commit
confidentiality gate and the cycle gate, and this project's own `pre-push`.

RENAMED FROM `install_hooks.py` ON 2026-09-29 (Wouter). It shared the house script's name and
nothing else, and `check_checkers.py` v18 began tracking that name, so it read this file as an
UNKNOWN copy of the house installer -- a comparison of two different programs. The rename
removes the clash itself; `verify.config.json` declares the house installer absent, with why.

ONLY GIT HOOKS ARE INSTALLED. `tools/hooks/` also holds `evidence_guard.py`, a Claude Code
PreToolUse hook wired through `.claude/settings.json`, which Git never runs. A hook Git runs is
named for its event and has no extension, so a file WITH one is skipped and said so -- until
2026-09-29 it was swept in, and `--check` reported it "not installed" on every correctly
installed repository, a red nobody could clear.

Hooks live in `.git/hooks/`, which is not tracked, so they do not travel with a clone. That
makes them easy to believe in and easy to not have. This installer copies them from
`tools/hooks/` and then VERIFIES each one is present and executable, because an
un-executable hook is silently ignored by Git -- it does not warn, it just does nothing,
which is the worst behaviour a control can have.

    uv run python tools/install_project_hooks.py
    uv run python tools/install_project_hooks.py --check    # verify only, install nothing
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
    if src.suffix:                      # not a git hook -- see the docstring
        print(f"  {src.name:<14} skipped: not a git hook (Git runs none with an extension)")
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
