# -*- coding: utf-8 -*-
"""NO SCRIPT MAY LEAVE A .pyc INSIDE A SHIPPED TREE. Register I-18's family, as a check.

THE DEFECT. Python writes bytecode beside the module it imported, so a script that imports a
SIBLING script puts `scripts/__pycache__/` into whatever directory it was run from -- which,
for this skill, is the operator's installed copy. The release packager zips that tree.

HOW IT SURFACED, and it is the argument for a check rather than a habit. Branch 7 slice 3
made translate_headers_footers.py import the graphic-metadata inventory from
extract_paragraphs.py, and `tools/precommit_gate.py` check 6 caught a
`uk/scripts/__pycache__/extract_paragraphs.cpython-312.pyc` on the very commit that added the
import. That gate catches the ARTEFACT -- a .pyc that happens to be sitting there when it
runs. This file catches the CAUSE.

AND IT IS DELIBERATELY A CHECK OVER THE WHOLE TREE RATHER THAN A TEST OF FOUR FILES.
CLAUDE.md: *prefer an assertion that catches caller N+1 to a patch on caller N.* When slice 3
found the defect, FIVE tree scripts imported a sibling and exactly one of them guarded -- the
one just written. Patching the four would have covered the callers that exist today and none
of the ones that do not. So arm 1 DISCOVERS the population by reading the tree, and a script
added tomorrow with an unguarded sibling import fails this suite without anybody adding a row.

    ARM 1  STATIC. Every script that imports a sibling sets `sys.dont_write_bytecode = True`
           BEFORE the import. Ordering matters: setting it afterwards is too late.
    ARM 2  BEHAVIOURAL, and it is the one that cannot pass for the wrong reason. Each such
           script is run in a COPY of the tree with PYTHONDONTWRITEBYTECODE REMOVED from the
           environment, and no __pycache__ may appear. Every suite in this repository sets
           that variable, so a static arm alone would be green on a tree that still writes
           bytecode the moment a real operator runs it.
    ARM 3  THE NEGATIVE INPUT. An unguarded sibling import is PLANTED in the copy and both
           arms must FAIL on it. A check that cannot fail is not a check.

    uv run python tests/test_no_bytecode_in_tree.py
    uv run python tests/test_no_bytecode_in_tree.py --variant us

Reads the shipped trees and a temporary copy of one. No client text, no corpus, no logs.
"""
import argparse
import io
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parent.parent

ap = argparse.ArgumentParser()
ap.add_argument("--variant", default="uk", choices=("uk", "us"))
ap.add_argument("--keep", action="store_true")
args = ap.parse_args()
SCRIPTS = ROOT / args.variant / "scripts"

FAIL, CHECKED, VOIDED = [], 0, []
TMP = Path(tempfile.mkdtemp(prefix="nobytecode-"))

# The sibling-import shape, as it is actually written in this tree: the scripts directory is
# put on sys.path and then a bare module name is imported. Matched on the sys.path line
# rather than on a list of module names, so a NEW sibling module is covered too.
PATH_INSERT = re.compile(r"^\s*sys\.path\.insert\(0,\s*_SCRIPTS_DIR\)", re.M)
GUARD = re.compile(r"^\s*sys\.dont_write_bytecode\s*=\s*True", re.M)


def ok(label, cond, detail=""):
    global CHECKED
    CHECKED += 1
    print(("  OK   " if cond else "  XX   ") + label
          + (f"   {detail}" if detail and not cond else ""))
    if not cond:
        FAIL.append(f"{label} {detail}".strip())
    return cond


def void(label, why):
    VOIDED.append(f"{label}: {why}")
    print(f"  ??   {label}   VOID — {why}")


def importers(scripts_dir):
    """Every script in the directory that puts the scripts dir on sys.path. DISCOVERED by
    reading the tree, never enumerated in a list here -- a list is the thing that goes stale
    when caller N+1 arrives."""
    out = []
    for p in sorted(scripts_dir.glob("*.py")):
        text = p.read_text(encoding="utf-8", errors="replace")
        if PATH_INSERT.search(text):
            out.append((p, text))
    return out


def guarded_before_import(text):
    """True when the guard appears BEFORE the sys.path.insert. Order is the whole point:
    `sys.dont_write_bytecode` set after the import has already missed its moment."""
    g = GUARD.search(text)
    i = PATH_INSERT.search(text)
    if i is None:
        return True          # nothing to guard
    return g is not None and g.start() < i.start()


print("=" * 96)
print(f"NO .pyc INSIDE A SHIPPED TREE — register I-18's family   [{args.variant}]")
print("=" * 96)

# =========================================================================================
# ARM 1 — STATIC. The population is DISCOVERED, and the denominator is printed.
# =========================================================================================
print("\n" + "-" * 96)
print("ARM 1 — every sibling-importing script sets the guard BEFORE the import")
print("-" * 96)
pop = importers(SCRIPTS)
total_scripts = len(list(SCRIPTS.glob("*.py")))
print(f"  scripts in {args.variant}/scripts/ : {total_scripts}")
print(f"  of those, importing a sibling     : {len(pop)}")
if not pop:
    void("arm 1", "no script imports a sibling, so this suite examined nothing. That is a "
                  "changed tree, not a clean one — re-derive the shape.")
for p, text in pop:
    ok(f"{p.name}: guard set before the sibling import", guarded_before_import(text))

# =========================================================================================
# ARM 2 — BEHAVIOURAL. Run each one with PYTHONDONTWRITEBYTECODE REMOVED.
#
# THIS IS THE ARM THAT CANNOT PASS FOR THE WRONG REASON. Every suite and tool in this
# repository sets PYTHONDONTWRITEBYTECODE, so a tree that still writes bytecode would look
# clean under all of them and only bite a real operator. So the variable is stripped here on
# purpose -- and `-B` is NOT passed either, for the same reason.
# =========================================================================================
print("\n" + "-" * 96)
print("ARM 2 — run each in a COPY of the tree, with PYTHONDONTWRITEBYTECODE REMOVED")
print("-" * 96)
COPY = TMP / "tree"
shutil.copytree(SCRIPTS, COPY / "scripts")
env = {k: v for k, v in os.environ.items() if k != "PYTHONDONTWRITEBYTECODE"}
env["PYTHONIOENCODING"] = "utf-8"
env["PYTHONUTF8"] = "1"
print(f"  PYTHONDONTWRITEBYTECODE in the child env: "
      f"{'PRESENT — arm is void' if 'PYTHONDONTWRITEBYTECODE' in env else 'removed'}")
if "PYTHONDONTWRITEBYTECODE" in env:
    void("arm 2", "the variable could not be removed from the environment")
else:
    for p, _ in pop:
        target = COPY / "scripts" / p.name
        # Run with no arguments. Every one of these scripts prints its usage and exits
        # non-zero -- which is fine and is the point: the IMPORTS have already executed by
        # then, which is when the bytecode would be written.
        subprocess.run(["uv", "run", "--with", "lxml", "python", str(target)],
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace", cwd=str(COPY), env=env, timeout=300)
    caches = sorted(q for q in (COPY / "scripts").rglob("__pycache__"))
    pycs = sorted(q for q in (COPY / "scripts").rglob("*.pyc"))
    ok(f"no __pycache__ appeared in the copied tree after running all {len(pop)}",
       not caches, f"{[str(c.relative_to(COPY)) for c in caches]}")
    ok("no .pyc appeared either", not pycs,
       f"{[str(q.relative_to(COPY)) for q in pycs]}")

# =========================================================================================
# ARM 3 — THE NEGATIVE INPUT. Plant an unguarded sibling import and prove BOTH arms fail.
# =========================================================================================
print("\n" + "-" * 96)
print("ARM 3 — the negative input: an UNGUARDED sibling import must fail both arms")
print("-" * 96)
BAD = TMP / "bad"
shutil.copytree(SCRIPTS, BAD / "scripts")
victim = BAD / "scripts" / "zz_unguarded_probe.py"
# Written as BYTES with explicit \n: the trees are pure LF, and write_text opens in text mode.
victim.write_bytes(
    b"import os\nimport sys\n"
    b"_SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))\n"
    b"if _SCRIPTS_DIR not in sys.path:\n"
    b"    sys.path.insert(0, _SCRIPTS_DIR)\n"
    b"from source_language_markers import detect_language  # noqa: E402\n"
    b"print('probe imported', bool(detect_language))\n")

bad_pop = importers(BAD / "scripts")
planted = [(p, t) for p, t in bad_pop if p.name == victim.name]
ok("arm 1's discovery FINDS the planted script", len(planted) == 1,
   f"found {len(planted)}")
if planted:
    ok("arm 1 REFUSES it — the guard is absent",
       not guarded_before_import(planted[0][1]))
    # And the ordering half, which a naive "is the guard present anywhere" check would miss.
    reordered = planted[0][1].replace(
        "print('probe imported'", "sys.dont_write_bytecode = True\nprint('probe imported'")
    ok("arm 1 REFUSES it even with the guard set AFTER the import — ordering is the point",
       not guarded_before_import(reordered))

if "PYTHONDONTWRITEBYTECODE" not in env:
    subprocess.run(["uv", "run", "--with", "lxml", "python", str(victim)],
                   capture_output=True, text=True, encoding="utf-8", errors="replace",
                   cwd=str(BAD), env=env, timeout=300)
    bad_caches = sorted(q for q in (BAD / "scripts").rglob("__pycache__"))
    ok("arm 2 REFUSES it — running the unguarded script DOES write bytecode",
       bool(bad_caches),
       "no __pycache__ appeared, so arm 2 cannot fail and proves nothing")
else:
    void("arm 3's behavioural half", "PYTHONDONTWRITEBYTECODE could not be removed")

print("\n" + "=" * 96)
print(f"CHECKED {CHECKED}   FAILED {len(FAIL)}   VOID {len(VOIDED)}")
print("=" * 96)
for f in FAIL:
    print(f"  FAIL  {f}")
for v in VOIDED:
    print(f"  VOID  {v}")
print()
print("WHAT THIS DOES NOT COVER, stated so a green run is not read as more than it is:")
print("  a script that imports a sibling by some OTHER route — importlib, an absolute path,")
print("  a package-relative import. Arm 1 matches the shape this tree actually uses")
print("  (sys.path.insert(0, _SCRIPTS_DIR)); a new route needs a new pattern here, and")
print("  tools/precommit_gate.py check 6 remains the backstop that reads the ARTEFACT.")
if not args.keep:
    shutil.rmtree(TMP, ignore_errors=True)
else:
    print(f"\nworkdir kept: {TMP}")
sys.exit(1 if (FAIL or VOIDED) else 0)
