"""test_no_document_moves.py - NO PYTHON PROCESS IN THIS PROJECT MOVES OR RENAMES A FILE (CLAUDE.md section 4,
Wouter 2026-09-28 (4)).

WHY. This machine's security agent silently ends an unsigned process that moves or renames a Word, email or
PDF file, and a run it ends can still look finished -- measured the day this was written: a verify runner cut
short at its second of four renders exited 0 after printing one line. repack_docx.py renamed its checked temp
archive into the delivery path and clean_conversion_artifacts.py renamed its cleaned copy over the user's
input; both now build the archive in memory and write the final file once.

WHAT IT REFUSES, AND WHY IT IS WIDER THAN THE RULE. Code cannot show what kind of file a path names, so the
scan refuses a move or rename of ANY file: os.rename, os.renames, os.replace, shutil.move, the same names
imported with `from ... import`, and a one-argument .rename(x) or .replace(x) with no keywords -- which is
Path.rename and Path.replace, where str.replace takes two arguments and datetime.replace takes keywords. A
genuine need to move a file that is not a document goes in ALLOW below, with its reason; the list is empty.

THE POPULATION IS THE TRACKED SET, enumerated by git with core.quotePath=false (a path git quotes is not a
path), and every listed file that cannot be read or parsed is REPORTED, never skipped. Untracked scratch in
temp/ is not the project's code and is not scanned. It uses Python's own parser, so a line that QUOTES a call
-- tests/test_checks_can_fail.py holds one as a marker -- is text, not a call.

CONTROLS, both ways, on planted source held in memory: every refused shape is found, and a two-argument
str.replace and a keyword datetime.replace are not. A run whose control did not fire is VOID.

    uv run python tests/test_no_document_moves.py
"""
import ast
import io
import subprocess
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parent.parent
ALLOW = {}          # {"path/to/file.py:LINE": "why this move of a non-document file is needed"}
MODULE_CALLS = {("os", "rename"), ("os", "renames"), ("os", "replace"), ("shutil", "move")}


def moves(source, label):
    """Every move or rename call in `source`, as (line, what)."""
    tree = ast.parse(source, filename=label)
    imported = {}                                        # local name -> "module.name"
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module in ("os", "shutil"):
            for a in node.names:
                if (node.module, a.name) in MODULE_CALLS:
                    imported[a.asname or a.name] = f"{node.module}.{a.name}"
    found = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        f = node.func
        if isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name) and (f.value.id, f.attr) in MODULE_CALLS:
            found.append((node.lineno, f"{f.value.id}.{f.attr}"))
        elif isinstance(f, ast.Name) and f.id in imported:
            found.append((node.lineno, imported[f.id]))
        elif (isinstance(f, ast.Attribute) and f.attr in ("rename", "replace") and len(node.args) == 1
              and not node.keywords and not (isinstance(f.value, ast.Name) and f.value.id in ("os", "shutil"))):
            found.append((node.lineno, f".{f.attr}(x)"))
    return sorted(found)


# ------------------------------------------------------------------ controls, both ways
PLANTED = """
import os, shutil
from pathlib import Path
from shutil import move as mv
os.replace('a.docx', 'b.docx')
os.rename('a.msg', 'b.msg')
shutil.move('a.pdf', 'b.pdf')
mv('a.docx', 'b.docx')
Path('a.docx').rename('b.docx')
p = Path('x'); p.replace(Path('y'))
"""
QUIET = """
import datetime
s = 'abc'.replace('a', 'b')
d = datetime.date(2020, 1, 1).replace(year=2021)
q = s.replace('b', 'c', 1)
"""
got_planted, got_quiet = moves(PLANTED, "<planted>"), moves(QUIET, "<quiet>")
print(f"  control: the planted source's 6 moves found {len(got_planted)}; the quiet source's 0 found {len(got_quiet)}")
if len(got_planted) != 6 or got_quiet:
    print(f"  VOID — a control did not behave: planted {got_planted}, quiet {got_quiet}")
    sys.exit(2)

# ------------------------------------------------------------------ the tracked set
ls = subprocess.run(["git", "-c", "core.quotePath=false", "ls-files", "-z", "--", "*.py"], cwd=str(ROOT),
                    capture_output=True, check=True).stdout.decode("utf-8")
listed = sorted(n for n in ls.split("\0") if n)
unread, findings = [], []
for rel in listed:
    try:
        src = (ROOT / rel).read_text(encoding="utf-8")
        for line, what in moves(src, rel):
            if f"{rel}:{line}" not in ALLOW:
                findings.append(f"{rel}:{line}  {what}")
    except (OSError, UnicodeDecodeError, SyntaxError) as exc:
        unread.append(f"{rel}  ({type(exc).__name__})")
print(f"  tracked .py files listed {len(listed)} · read and parsed {len(listed) - len(unread)} · "
      f"not read {len(unread)} · allowed moves declared {len(ALLOW)}")
for u in unread:
    print(f"  NOT READ  {u}")
for f in findings:
    print(f"  XX  a Python process moves or renames a file: {f}")
if not listed:
    print("  VOID — git listed no .py file")
    sys.exit(2)
print("=" * 96)
print(f"  {len(findings)} move(s) found; {len(unread)} file(s) not read")
print("=" * 96)
sys.exit(1 if findings or unread else 0)
