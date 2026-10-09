#!/usr/bin/env python3
"""sibling_dirs.py - WHERE THE SIBLING FOLDERS ARE, from the main checkout or from any git worktree of it.

THE FOLDERS. The private folder, the logs folder, the published skill archives and the test-document
folder all sit OUTSIDE this repository, BESIDE it (CLAUDE.md 6.4), so nothing in them can be committed
by accident. Every tool that reads one used to find it as `ROOT.parent / <name>`.

WHY THAT WAS WRONG (register I-39). From a git WORKTREE - a second working copy under
.claude/worktrees/<name>, where a parallel session works - ROOT.parent is .claude/worktrees, so every
such default pointed nowhere. Tools crashed, or skipped, or answered a different question without
saying so: audit_register read its paths relative to the CURRENT folder, so run from the main
checkout's folder it validated the MAIN checkout's register, and stepb_audit compared against an
empty backup. Each looked like a result.

THE FIX, IN ONE PLACE - decision 6's written rule, "a shared capability lives in one place".
SIBLINGS is the folder that holds the MAIN checkout. In a linked worktree `.git` is not a folder but
a one-line pointer file, `gitdir: <main>/.git/worktrees/<name>`, and that folder's `commondir` file
names the main checkout's `.git`. Both are read as plain files: no git process, so it costs nothing
at import and works where git is not on the PATH. Anywhere else - the main checkout, a fresh clone,
an unpacked archive, a `.git` file with no `commondir` (a separate git folder, not a worktree) -
the answer is ROOT itself, exactly as before.

EACH FOLDER CAN BE NAMED OUTRIGHT, AND THE VARIABLE WINS: LT_PRIVATE_DIR · LT_LOGS_DIR, then the
older LEGAL_TRANSLATION_LOGS that gate_replay and qc_census read · LT_ARCHIVES_DIR. A variable SET
BUT EMPTY COUNTS AS UNSET: `Path("")` is the current folder, so an empty value used to send a tool to
read whatever sat wherever it was started - a well-formed path, merely the wrong one.

NOT HERE, deliberately: LEAKAGE_LIST_PATH, CORPUS_DESCRIPTORS_FILE and LT_CORPUS_DIR. Each names one
FILE or one extra folder, not where a sibling lives, and stays in the tools that read it.

    uv run python tools/sibling_dirs.py      # each folder: where it came from, and whether it exists

The report names each folder by its KIND and the variable that set it, never by its path: a path
carries the machine's username, and the test-document folder's name is not publishable at all.
tests/test_sibling_dirs.py holds the guard that keeps the old shape from coming back.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PRIVATE_NAME = "legal-translation-private"
LOGS_NAME = "legal-translation-logs"
ARCHIVES_PARTS = ("skills", "legal-translation")


def main_checkout(root: Path = ROOT) -> Path:
    """The MAIN checkout's folder: `root` itself, unless `root` is a linked git worktree."""
    dotgit = root / ".git"
    if not dotgit.is_file():
        return root
    first = dotgit.read_text(encoding="utf-8", errors="replace").strip()
    if not first.startswith("gitdir:"):
        return root
    gitdir = Path(first[len("gitdir:"):].strip())
    if not gitdir.is_absolute():
        gitdir = root / gitdir
    commondir = gitdir / "commondir"
    if not commondir.is_file():
        return root
    common = (gitdir / commondir.read_text(encoding="utf-8", errors="replace").strip()).resolve()
    return common.parent if common.name == ".git" else root


SIBLINGS = main_checkout().parent

# Which variables name which folder, first one set wins. One table, so the report and the lookups
# cannot disagree about it.
VARS = {"private": ("LT_PRIVATE_DIR",),
        "logs": ("LT_LOGS_DIR", "LEGAL_TRANSLATION_LOGS"),
        "archives": ("LT_ARCHIVES_DIR",)}


def _from_env(kind: str) -> tuple[Path | None, str | None]:
    for name in VARS[kind]:
        value = os.environ.get(name, "").strip()
        if value:
            return Path(value), name
    return None, None


def private_dir() -> Path:
    """The private folder: the scan lists, the private tools, the A4 set."""
    return _from_env("private")[0] or SIBLINGS / PRIVATE_NAME


def logs_dir() -> Path:
    """The logs folder: the A1 run logs, the grade reports, the frozen intermediates."""
    return _from_env("logs")[0] or SIBLINGS / LOGS_NAME


def archives_dir() -> Path:
    """The archived .skill revisions; the two published ones are in its PUBLICATION VERSIONS."""
    return _from_env("archives")[0] or SIBLINGS.joinpath(*ARCHIVES_PARTS)


def publication_versions() -> Path:
    """The two published rev44 archives - the code baseline and the blind review's reading."""
    return archives_dir() / "PUBLICATION VERSIONS"


def beside(name: str) -> Path:
    """A folder named in .claude/evidence-dirs.local or LT_CORPUS_DIR: absolute as given, and a bare
    name beside the MAIN checkout - where the sibling folders are - rather than beside this one."""
    p = Path(name)
    return p if p.is_absolute() else (SIBLINGS / p).resolve()


def main_temp(*parts: str) -> Path:
    """An INPUT kept in a gitignored temp/ folder - a backup or a pre-overhaul copy. This checkout's
    own temp/ if it has the file, else the main checkout's, which is where such files were made.
    Outputs are NOT routed here: a tool writes into its own checkout's temp/, always."""
    own = ROOT.joinpath("temp", *parts)
    return own if own.exists() else main_checkout().joinpath("temp", *parts)


def _report() -> int:
    where = "a git worktree" if main_checkout() != ROOT else "the main checkout"
    print(f"sibling_dirs: running in {where}")
    for kind, path in (("private", private_dir()), ("logs", logs_dir()),
                       ("archives", archives_dir()), ("published archives", publication_versions())):
        used = _from_env(kind)[1] if kind in VARS else _from_env("archives")[1]
        source = f"set by {used}" if used else "beside the main checkout"
        print(f"  {kind:<19} {source:<32} {'exists' if path.is_dir() else 'MISSING'}")
    return 0


if __name__ == "__main__":
    sys.exit(_report())
