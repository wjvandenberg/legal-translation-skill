# -*- coding: utf-8 -*-
"""THE SIBLING FOLDERS ARE FOUND IN ONE PLACE, AND FROM A WORKTREE TOO - register I-39.

Twenty-three tools and tests found the private folder, the logs folder or the published archives as
`ROOT.parent / <name>`, or by a path relative to the CURRENT folder. From a git worktree
(.claude/worktrees/<name>) ROOT.parent is .claude/worktrees, so each crashed, skipped, or answered
about the wrong file. tools/sibling_dirs.py now owns the lookup. This test keeps it that way.

  1  THE SHAPE. Every .py under tools/ and tests/ is PARSED - never grepped: the evidence guard's
     tests carry these folder names inside COMMAND STRINGS, which are not paths - and three shapes
     fail wherever they appear:
       a. `ROOT.parent` - the repository's parent, which from a worktree is .claude/worktrees
       b. a sibling folder's NAME used to build a path: `X / "<name>"`, `Path(.., "<name>")`,
          `os.path.join(.., "<name>")`, and `X / "skills" / "legal-translation"`
       c. a path that climbs out of the current folder: a literal starting "../" handed to a path
          call, ANY literal starting "../<sibling name>" - kept in a variable first, it is the same
          path (audit_register's LOG was, and the first version of this test missed it) - or two
          ".." in one os.path.join
     Each shape is planted in a synthetic source first and must fire; a clean source must not.
     The denominator is printed against the files listed, and a file that will not parse FAILS.
  2  THE LOOKUP, on synthetic layouts in a temporary folder - a main checkout, a linked worktree
     with an absolute and with a relative pointer, a separate git folder, no git at all, a pointer
     file that is not one - and the variables: set wins, empty counts as unset, unset falls back.
  3  THIS CHECKOUT: the helper's answer about where it is running agrees with git's own `.git`.

    uv run python tests/test_sibling_dirs.py
"""
import ast
import io
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parent.parent
FAIL, CHECKED = [], 0

NAMES = {"legal-translation-private", "legal-translation-logs", "PUBLICATION VERSIONS"}
CLIMBS = tuple(f"..{sep}{name}" for sep in "/\\" for name in
               ("legal-translation-private", "legal-translation-logs", "skills"))
PATH_CALLS = {"open", "Path", "PurePath", "join", "joinpath", "exists", "isfile", "isdir",
              "listdir", "scandir", "walk"}


def ok(label, cond, detail=""):
    global CHECKED
    CHECKED += 1
    print(f"  {'OK  ' if cond else 'XX  '} {label}" + (f"   ({detail})" if detail and not cond else ""))
    if not cond:
        FAIL.append(label)


def _s(node):
    return node.value if isinstance(node, ast.Constant) and isinstance(node.value, str) else None


def _callname(func):
    return func.id if isinstance(func, ast.Name) else (func.attr if isinstance(func, ast.Attribute) else "")


def offences(source):
    """(line, shape) for every sibling-folder lookup that does not go through the helper."""
    out = set()
    for n in ast.walk(ast.parse(source)):
        if _s(n) and _s(n).lstrip().startswith(CLIMBS):
            out.add((n.lineno, 'c: "../<sibling name>"'))
        if isinstance(n, ast.Attribute) and n.attr == "parent" \
                and isinstance(n.value, ast.Name) and n.value.id == "ROOT":
            out.add((n.lineno, "a: ROOT.parent"))
        elif isinstance(n, ast.BinOp) and isinstance(n.op, ast.Div):
            right = _s(n.right)
            if right in NAMES:
                out.add((n.lineno, f'b: / "{right}"'))
            elif right == "legal-translation" and isinstance(n.left, ast.BinOp) \
                    and _s(n.left.right) == "skills":
                out.add((n.lineno, 'b: / "skills" / "legal-translation"'))
        elif isinstance(n, ast.Call) and _callname(n.func) in PATH_CALLS:
            strs = [_s(a) for a in n.args]
            if any(s in NAMES for s in strs):
                out.add((n.lineno, f"b: {_callname(n.func)}(.., <sibling name>)"))
            if strs and strs[0] and strs[0].replace("\\", "/").startswith("../"):
                out.add((n.lineno, f'c: {_callname(n.func)}("../..")'))
            if _callname(n.func) == "join" and any(a == b == ".." for a, b in zip(strs, strs[1:])):
                out.add((n.lineno, 'c: join(.., "..", "..")'))
    return sorted(out)


print("=" * 88)
print("I-39 — the sibling folders are found in one place, and from a worktree too")
print("=" * 88)

# ------------------------------------------------------------------------------------------ 1
print("\n1   THE SHAPE — its controls first, then every .py under tools/ and tests/")
PLANTS = [
    ("a", 'PRIV = ROOT.parent / "anything"\n'),
    ("b", 'P = Q / "legal-translation-private"\n'),
    ("b", 'P = Path(os.environ.get("X") or "") / "legal-translation-logs"\n'),
    ("b", 'A = Q / "skills" / "legal-translation" / "PUBLICATION VERSIONS"\n'),
    ("b", 'P = os.path.join(HERE, "..", "..", "legal-translation-private")\n'),
    ("c", 'f = open("../legal-translation-private/leakage-names.txt")\n'),
    ("c", 'p = os.path.join(HERE, "..", "..")\n'),
    ("c", "LOG = '../legal-translation-logs/A1'\n"),
]
for shape, src in PLANTS:
    got = offences(src)
    ok(f"control: shape {shape} fires on {src.strip()!r}", any(g[1].startswith(shape) for g in got),
       f"got {got}")
CLEAN = ('CMDS = [("ls", "ls ../legal-translation-logs/A1")]\n'
         'print("  ls ../legal-translation-logs/NO-SUCH-DIRECTORY-PROBE")\n'
         'DEFAULT_DIRS = ["legal-translation-logs", "legal-translation-private"]\n'
         'q = ROOT / ".claude" / "skills"\n'
         'p = SIBLINGS / PRIVATE_NAME\n'
         'r = ROOT / "temp" / "x"\n')
ok("control: a clean source — names inside command strings, .claude/skills — fires nothing",
   offences(CLEAN) == [], f"got {offences(CLEAN)}")

listed = sorted({*ROOT.glob("tools/**/*.py"), *ROOT.glob("tests/**/*.py")})
parsed, unreadable, hits = 0, [], {}
for f in listed:
    try:
        found = offences(f.read_text(encoding="utf-8"))
    except (OSError, SyntaxError, UnicodeDecodeError) as e:
        unreadable.append(f"{f.relative_to(ROOT).as_posix()}: {type(e).__name__}")
        continue
    parsed += 1
    if found and f != ROOT / "tools" / "sibling_dirs.py":       # the owner: parsed and counted, exempt
        hits[f.relative_to(ROOT).as_posix()] = found
print(f"  parsed {parsed} of {len(listed)} listed .py files under tools/ and tests/")
ok("every listed file parsed", not unreadable, "; ".join(unreadable))
ok("no file finds a sibling folder except through tools/sibling_dirs.py", not hits,
   f"{sum(len(v) for v in hits.values())} site(s) in {len(hits)} file(s)")
for name, found in hits.items():
    for line, shape in found:
        print(f"         {name}:{line}  {shape}")

# ------------------------------------------------------------------------------------------ 2
print("\n2   THE LOOKUP — synthetic layouts, then the variables")
sys.path.insert(0, str(ROOT / "tools"))
try:
    import sibling_dirs as sd
except ImportError as e:
    sd = None
    ok("tools/sibling_dirs.py imports", False, f"{type(e).__name__}: {e}")

if sd is not None:
    tmp = Path(tempfile.mkdtemp(prefix="sibling-dirs-"))
    try:
        main = tmp / "repo"
        (main / ".git" / "worktrees" / "wt").mkdir(parents=True)
        (main / ".git" / "worktrees" / "wt2").mkdir(parents=True)
        for w in ("wt", "wt2"):
            (main / ".git" / "worktrees" / w / "commondir").write_text("../..\n", encoding="utf-8")
        wt = main / ".claude" / "worktrees" / "wt"
        wt2 = main / ".claude" / "worktrees" / "wt2"
        for w in (wt, wt2):
            w.mkdir(parents=True)
        (wt / ".git").write_text(f"gitdir: {(main / '.git' / 'worktrees' / 'wt').as_posix()}\n",
                                 encoding="utf-8")
        (wt2 / ".git").write_text("gitdir: ../../../.git/worktrees/wt2\n", encoding="utf-8")
        sep = tmp / "separate"
        sep.mkdir()
        (sep / ".git").write_text(f"gitdir: {(tmp / 'elsewhere.git').as_posix()}\n", encoding="utf-8")
        (tmp / "elsewhere.git").mkdir()
        bare = tmp / "nogit"
        bare.mkdir()
        junk = tmp / "junk"
        junk.mkdir()
        (junk / ".git").write_text("not a pointer\n", encoding="utf-8")
        for label, root, want in (("the main checkout is itself", main, main),
                                  ("a worktree, absolute pointer, finds the main checkout", wt, main),
                                  ("a worktree, relative pointer, finds the main checkout", wt2, main),
                                  ("a separate git folder (no commondir) is itself", sep, sep),
                                  ("no .git at all is itself", bare, bare),
                                  (".git that is not a pointer is itself", junk, junk)):
            got = sd.main_checkout(root)
            ok(label, got.resolve() == want.resolve(), f"got {got}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    saved = {k: os.environ.get(k) for k in
             ("LT_PRIVATE_DIR", "LT_LOGS_DIR", "LEGAL_TRANSLATION_LOGS", "LT_ARCHIVES_DIR")}
    try:
        for k in saved:
            os.environ.pop(k, None)
        there = Path(tempfile.gettempdir()) / "named-outright"
        ok("unset: private beside the main checkout", sd.private_dir() == sd.SIBLINGS / sd.PRIVATE_NAME)
        ok("unset: logs beside the main checkout", sd.logs_dir() == sd.SIBLINGS / sd.LOGS_NAME)
        ok("unset: archives beside the main checkout",
           sd.archives_dir() == sd.SIBLINGS.joinpath(*sd.ARCHIVES_PARTS))
        os.environ["LT_PRIVATE_DIR"] = str(there)
        ok("set: LT_PRIVATE_DIR wins", sd.private_dir() == there)
        for empty in ("", "   "):
            os.environ["LT_PRIVATE_DIR"] = empty
            ok(f"set but empty ({empty!r}): counts as unset, never the current folder",
               sd.private_dir() == sd.SIBLINGS / sd.PRIVATE_NAME, f"got {sd.private_dir()}")
        os.environ["LEGAL_TRANSLATION_LOGS"] = str(there / "old")
        ok("the older LEGAL_TRANSLATION_LOGS is still read", sd.logs_dir() == there / "old")
        os.environ["LT_LOGS_DIR"] = str(there / "new")
        ok("LT_LOGS_DIR wins over LEGAL_TRANSLATION_LOGS", sd.logs_dir() == there / "new")
        os.environ["LT_ARCHIVES_DIR"] = str(there)
        pv = sd.publication_versions()
        ok("LT_ARCHIVES_DIR names the archives, and the published ones sit inside",
           pv.parent == there and pv.name == "PUBLICATION VERSIONS")
        ok("beside(): an absolute name is kept", sd.beside(str(there)) == there)
        ok("beside(): a bare name sits beside the main checkout",
           sd.beside("some-folder") == (sd.SIBLINGS / "some-folder").resolve())
        ok("main_temp(): a file this checkout lacks is looked for in the main checkout's temp/",
           sd.main_temp("no-such-file.xyz") == sd.main_checkout() / "temp" / "no-such-file.xyz")
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

# ------------------------------------------------------------------------------------------ 3
print("\n3   THIS CHECKOUT")
if sd is not None:
    is_worktree = (ROOT / ".git").is_file()
    mc = sd.main_checkout()
    print(f"  running in {'a git worktree' if is_worktree else 'the main checkout or a clone'}")
    if is_worktree:
        ok("from a worktree the main checkout is ANOTHER folder holding a real .git",
           mc != ROOT and (mc / ".git").is_dir())
    else:
        ok("outside a worktree the main checkout is this one", mc == ROOT)
    ok("the sibling folders sit beside the main checkout", sd.SIBLINGS == mc.parent)
    env = {k: v for k, v in os.environ.items() if k not in
           ("LT_PRIVATE_DIR", "LT_LOGS_DIR", "LEGAL_TRANSLATION_LOGS", "LT_ARCHIVES_DIR")}
    env.update(PYTHONIOENCODING="utf-8", PYTHONDONTWRITEBYTECODE="1")
    r = subprocess.run([sys.executable, str(ROOT / "tools" / "sibling_dirs.py")], capture_output=True,
                       text=True, encoding="utf-8", errors="replace", env=env)
    rows = [ln for ln in r.stdout.splitlines() if ln.startswith("  ")]
    ok("the report runs and names four folders, by kind", r.returncode == 0 and len(rows) == 4,
       f"rc={r.returncode}, {len(rows)} rows")
    ok("the report prints no path", str(sd.SIBLINGS) not in r.stdout and "\\" not in r.stdout)

print("\n" + "=" * 88)
print(f"  {CHECKED} checks, {len(FAIL)} failed")
sys.exit(1 if FAIL else 0)
