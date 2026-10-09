# -*- coding: utf-8 -*-
"""I-39 -- the table checker may never report CLEAN over a file it did not read.

WHAT WENT WRONG. `tools/md_tables.py` summed its per-file verdicts over `sys.argv[1:]`, so a run
that named no file summed over NOTHING and printed CLEAN with exit 0. The session document
runner called it exactly that way, and two table breaks in `evidence/REGISTER-findings.md` --
twenty-one rows rendering as loose text -- went unreported behind a green row. A named file that
could not be opened was the same failure from the other end: a traceback and exit 1, which a
runner reading only the exit code cannot tell from "this file has a broken table".

WHAT THIS FILE ASSERTS, each case run as a TOP-LEVEL command against the real script:

  1  a bare run READS the project's documents -- prints FILES READ with the count and every path
     of the set `tools/publication_check.py` reads, and never says CLEAN without having read one;
  2  a bare run over a tree holding NONE of them is VOID, exit 2;
  3  a bare run with a core document gone is VOID, exit 2, and names it -- a rename is noticed,
     never read as a smaller clean run;
  4  a named file that does not exist is VOID, exit 2, named, and no traceback;
  5  a named file that is not UTF-8 is VOID, exit 2, named;
  6  POSITIVE CONTROL -- an orphan row in a named file still fails, exit 1;
  7  POSITIVE CONTROL -- a width mismatch in a named file still fails, exit 1;
  8  NEGATIVE CONTROL -- a well-formed table in a named file is CLEAN, exit 0;
  9  THE DRIFT GUARD -- the checker's core names and globs equal the publication check's AND the
     shape sweep's, read from every source without running any, so no two of the three copies can
     quietly cover different sets;
 10  a file named twice is read once, so FILES READ stays a true denominator;
 11  on a cp1252 console an orphan row holding a character cp1252 cannot encode is still REPORTED,
     exit 1 -- never a UnicodeEncodeError traceback with the findings lost behind it;
 12  a report capped at eight mismatches and five orphans SAYS it is capped, naming every row it
     did not print by line number -- never a subset that reads as the whole.

Cases 1-5 and 9-12 FAIL against the checker as it stood before I-39; cases 6-8 pass on both,
which is what makes them controls. Cases 2 to 7 are inputs the checker must fail -- VOID or
PROBLEMS, never CLEAN -- so the suite proves failures as well as passes. Every file this test
writes is INVENTED and lives in a temporary folder it creates and removes; nothing in the
repository is touched.

    uv run python tests/test_md_tables.py
    MD_TABLES_UNDER_TEST=<a copy of an older md_tables.py> uv run python tests/test_md_tables.py

The second form points every case at another copy of the checker -- how the red is re-proved
against the pre-I-39 script taken from git, rather than remembered.

Exit 0 = every case passed. 1 = a case failed. 2 = VOID, the test could not set itself up.
"""
import ast
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CHECKER = Path(os.environ.get("MD_TABLES_UNDER_TEST") or ROOT / "tools" / "md_tables.py").resolve()
PUBCHECK = ROOT / "tools" / "publication_check.py"
SWEEP = ROOT / "tools" / "descriptor_shape_sweep.py"
ENV = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1", PYTHONDONTWRITEBYTECODE="1")

results = []


def case(n, name, ok, detail=""):
    results.append((n, name, ok))
    print(f"  [{'PASS' if ok else 'FAIL'}] {n}  {name}" + (f"\n         {detail}" if detail and not ok else ""))


def run(script, args=(), cwd=ROOT, env=None):
    r = subprocess.run([sys.executable, str(script), *args], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", cwd=str(cwd), env=env or ENV, timeout=300)
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def literal_lists(path):
    """The module-level CORE and DISCOVER lists of a script, read from its SOURCE -- never by
    importing it: publication_check.py scans at import time."""
    found = {}
    for node in ast.parse(path.read_text(encoding="utf-8")).body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 \
                and isinstance(node.targets[0], ast.Name) and node.targets[0].id in ("CORE", "DISCOVER"):
            found[node.targets[0].id] = ast.literal_eval(node.value)
    return found


def expected_set(root, lists):
    """The documents a bare run must read: the core names present, then each glob's matches,
    first occurrence kept -- the publication check's own rule."""
    out = [n for n in lists["CORE"] if (root / n).exists()]
    for g in lists["DISCOVER"]:
        for p in sorted(root.glob(g)):
            rel = p.relative_to(root).as_posix()
            if rel not in out:
                out.append(rel)
    return out


def sandbox():
    """A temporary folder holding only a copy of the checker at tools/md_tables.py, so the
    checker's own root is a tree this test controls."""
    d = Path(tempfile.mkdtemp(prefix="md_tables_test_"))
    try:
        (d / "tools").mkdir()
        shutil.copyfile(CHECKER, d / "tools" / "md_tables.py")
    except BaseException:
        shutil.rmtree(d, ignore_errors=True)
        raise
    return d


def files_read(out):
    """The FILES READ block, parsed: (the count it states, the paths listed under it)."""
    lines = out.replace("\\", "/").splitlines()
    at = [i for i, l in enumerate(lines) if l.startswith("FILES READ: ")]
    if len(at) != 1:
        return None, []
    listed = []
    for l in lines[at[0] + 1:]:
        if not l.startswith("    "):
            break
        listed.append(l.strip())
    return int(lines[at[0]].split(": ", 1)[1]), listed


TABLE_OK = "# A\n\n| term | rendering |\n| --- | --- |\n| a | b |\n| c | d |\n"
TABLE_ORPHAN = "# A\n\n| term | rendering |\n| --- | --- |\n| a | b |\n\n| c | d |\n"
TABLE_WIDTH = "# A\n\n| term | rendering |\n| --- | --- |\n| a | b | c |\n"

pub = literal_lists(PUBCHECK)
if set(pub) != {"CORE", "DISCOVER"} or not pub["CORE"] or not pub["DISCOVER"]:
    print(f"VOID -- could not read CORE and DISCOVER from {PUBCHECK.name}; nothing was tested.")
    sys.exit(2)
want = expected_set(ROOT, pub)
if not want:
    print("VOID -- the publication check's set matches no document in this tree; nothing was tested.")
    sys.exit(2)
if not CHECKER.is_file():
    print(f"VOID -- no checker at {CHECKER}; nothing was tested.")
    sys.exit(2)

print("=" * 88)
print(f"I-39 -- md_tables never reports CLEAN over a file it did not read   ({len(want)} documents expected)")
print(f"checker under test: {CHECKER.relative_to(ROOT).as_posix() if CHECKER.is_relative_to(ROOT) else CHECKER}")
print("=" * 88)

# 1 -- a bare run reads the documents
rc, out = run(CHECKER)
count, listed = files_read(out)
ok = count == len(want) and listed == want and rc in (0, 1) and "Traceback" not in out
case(1, f"a bare run reads all {len(want)} documents and lists each, in order", ok,
     f"rc={rc}; FILES READ states {count}, lists {len(listed)}; the list equals the expected set: "
     f"{listed == want}; first absent {[w for w in want if w not in listed][:3]}; tail: {out.strip()[-160:]!r}")

# 2 -- a bare run over a tree holding none of them is VOID
box = None
try:
    box = sandbox()
    rc, out = run(box / "tools" / "md_tables.py", cwd=box)
    case(2, "a bare run with no document present is VOID, exit 2", rc == 2 and "VOID" in out
         and "CLEAN" not in out, f"rc={rc}; tail: {out.strip()[-200:]!r}")

    # 3 -- a core document gone is VOID and named; the ones present are still read
    (box / "README.md").write_text(TABLE_OK, encoding="utf-8")
    (box / "CLAUDE.md").write_text(TABLE_OK, encoding="utf-8")
    rc, out = run(box / "tools" / "md_tables.py", cwd=box)
    gone = [n for n in pub["CORE"] if n != "CLAUDE.md"]
    case(3, "a bare run with a core document gone is VOID, exit 2, and names it",
         rc == 2 and "VOID" in out and all(g in out for g in gone) and "FILES READ: 2" in out,
         f"rc={rc}; tail: {out.strip()[-240:]!r}")

    # 4 -- a named file that does not exist
    rc, out = run(box / "tools" / "md_tables.py", ["no-such-document.md"], cwd=box)
    case(4, "a named file that does not exist is VOID, exit 2, named, no traceback",
         rc == 2 and "VOID" in out and "no-such-document.md" in out and "Traceback" not in out,
         f"rc={rc}; tail: {out.strip()[-240:]!r}")

    # 5 -- a named file that is not UTF-8
    (box / "latin.md").write_bytes(b"| caf\xe9 | x |\n| --- | --- |\n")
    rc, out = run(box / "tools" / "md_tables.py", ["latin.md"], cwd=box)
    case(5, "a named file that is not UTF-8 is VOID, exit 2, named",
         rc == 2 and "VOID" in out and "latin.md" in out and "Traceback" not in out,
         f"rc={rc}; tail: {out.strip()[-240:]!r}")

    # 6, 7, 8 -- the table logic itself, unchanged
    (box / "orphan.md").write_text(TABLE_ORPHAN, encoding="utf-8")
    (box / "width.md").write_text(TABLE_WIDTH, encoding="utf-8")
    (box / "fine.md").write_text(TABLE_OK, encoding="utf-8")
    rc, out = run(box / "tools" / "md_tables.py", ["orphan.md"], cwd=box)
    case(6, "POSITIVE CONTROL: an orphan row still fails, exit 1", rc == 1 and "ORPHAN" in out,
         f"rc={rc}; tail: {out.strip()[-200:]!r}")
    rc, out = run(box / "tools" / "md_tables.py", ["width.md"], cwd=box)
    case(7, "POSITIVE CONTROL: a width mismatch still fails, exit 1",
         rc == 1 and "1 width mismatches" in out, f"rc={rc}; tail: {out.strip()[-200:]!r}")
    rc, out = run(box / "tools" / "md_tables.py", ["fine.md"], cwd=box)
    case(8, "NEGATIVE CONTROL: a well-formed table is CLEAN, exit 0",
         rc == 0 and "CLEAN" in out, f"rc={rc}; tail: {out.strip()[-200:]!r}")

    # 10 -- a file named twice is read once
    rc, out = run(box / "tools" / "md_tables.py", ["fine.md", "./fine.md"], cwd=box)
    count, listed = files_read(out)
    case(10, "a file named twice is read once: FILES READ 1, CLEAN",
         rc == 0 and count == 1 and len(listed) == 1, f"rc={rc}; FILES READ {count}, listed {listed}")

    # 11 -- a cp1252 console and a character it cannot encode in an orphan row
    (box / "arrow.md").write_text(TABLE_ORPHAN.replace("| c | d |", "| c → | d |"), encoding="utf-8")
    cp = {k: v for k, v in ENV.items() if k != "PYTHONUTF8"}
    cp["PYTHONIOENCODING"] = "cp1252"
    rc, out = run(box / "tools" / "md_tables.py", ["arrow.md"], cwd=box, env=cp)
    case(11, "on a cp1252 console an unencodable orphan row is still reported, exit 1",
         rc == 1 and "ORPHAN" in out and "PROBLEMS: 1" in out and "Traceback" not in out,
         f"rc={rc}; tail: {out.strip()[-200:]!r}")

    # 12 -- a capped report says so, and names what it did not print
    rows = ["| term | rendering |", "| --- | --- |"] + [f"| r{k} | x | y |" for k in range(10)]
    orphans = [f"| o{k} | z |" for k in range(7)]
    lines = ["# A", ""] + rows + [""] + orphans + [""]
    body = chr(10).join(lines)
    (box / "many.md").write_text(body, encoding="utf-8")
    w_lines = [n for n, l in enumerate(lines, 1) if l.startswith("| r")][8:]
    o_lines = [n for n, l in enumerate(lines, 1) if l.startswith("| o")][5:]
    rc, out = run(box / "tools" / "md_tables.py", ["many.md"], cwd=box)
    want_w = f"and {len(w_lines)} more width mismatch(es) not shown, at lines {', '.join(map(str, w_lines))}"
    want_o = f"and {len(o_lines)} more ORPHAN row(s) not shown, at lines {', '.join(map(str, o_lines))}"
    case(12, "a capped report names every row it did not print",
         rc == 1 and want_w in out and want_o in out and "10 width mismatches, 7 orphan rows" in out,
         f"rc={rc}; expected {want_w!r} and {want_o!r}; tail: {out.strip()[-260:]!r}")
finally:
    if box is not None:
        shutil.rmtree(box, ignore_errors=True)

# 9 -- the drift guard, over all three copies
mine, sweep = literal_lists(CHECKER), literal_lists(SWEEP)
case(9, "the checker's CORE and DISCOVER equal the publication check's and the shape sweep's",
     mine == pub == sweep,
     f"md_tables has {sorted(mine)}; md_tables = publication_check: {mine == pub}; "
     f"publication_check = descriptor_shape_sweep: {pub == sweep}")

bad = [r for r in results if not r[2]]
print("-" * 88)
print(f"  ran {len(results)} of 12 cases; {len(results) - len(bad)} passed, {len(bad)} failed")
sys.exit(1 if bad or len(results) != 12 else 0)
