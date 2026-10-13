# -*- coding: utf-8 -*-
"""A MISSING OR HALF-CUT LANGUAGE MODULE EXITS AS A BROKEN INSTALL - NEVER AS A TRACEBACK, NEVER AS A GATE.

`source_language_markers.py` is imported by eight scripts in each tree (branch 12 onward). Every script checks
ITSELF for truncation and exits 3 with the FILE INTEGRITY banner SKILL.md rule 6 answers by re-installing - but
the module it imports was nobody's to check. Deleted, cut mid-statement, or cut cleanly before its own check
runs, it gave a raw traceback and exit 1; and repack_docx.py carried the failure down to its remnant block and
raised "SKILL GATE FIRED - INTENTIONAL BLOCK", the gate's costume rule 6 warns an operator about. The scenario
the review finding gave - apply's final pass running on past a validator's exit 1 - does NOT happen: apply
imports the module itself, first, so a broken module stops apply before any validator runs.

On a COPY of the tree, with the module damaged four ways:

  1  DELETED                        every importer exits 3, prints the banner and names the module; no traceback
  2  CUT MID-STATEMENT              the same - a SyntaxError, which the module's own check never gets to see
  3  CUT CLEANLY BEFORE ITS CHECK   the same - the module loads and the names asked of it are missing
  4  CUT CLEANLY AFTER ITS CHECK    the module's OWN check exits 3: green before the fix and after it, the
                                    control that this harness can see an exit 3 at all

and three arms that must NOT move: the UNDAMAGED copy, where no importer exits 3, prints the banner or a
traceback; the header-footer round-trip - its --extract still runs with the module deleted, that script's
partial-install pattern, only its legacy mode needing the module; and a module that is WHOLE but itself
imports something missing - a defect in the module, not a broken install - where no importer may print the
banner, the traceback naming what is missing being the truth (the narrowing the code review asked for).

The importers are DISCOVERED by reading the tree - any script that imports the module, at any depth - never
listed here, and the count is printed against the floor of eight measured on 2026-10-13. Each damage is proved
to be the damage it claims (a mid-statement cut must not compile; a clean cut must) before any verdict is read.

    uv run python tests/test_language_module_integrity.py [--variant us]

Reads a temporary copy of one shipped tree and one synthetic fixture. No client text, no corpus, no logs.
"""
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
VARIANT = sys.argv[sys.argv.index("--variant") + 1] if "--variant" in sys.argv else "uk"
TREE = ROOT / VARIANT
MODULE = "source_language_markers.py"
FIXTURE = ROOT / "tests" / "fixtures" / "headers-footers.docx"
BANNER = "FILE INTEGRITY CHECK FAILED"
FLOOR = 8  # importers per tree on 2026-10-13; fewer found means the discovery broke, not that the tree is clean
IMPORT_RE = re.compile(r"^\s*(?:from\s+source_language_markers\s+import\b|import\s+source_language_markers\b)",
                       re.M)
ENV = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1", PYTHONDONTWRITEBYTECODE="1")
FAIL, CHECKED, VOIDED = [], 0, []


def ok(label, cond, detail=""):
    global CHECKED
    CHECKED += 1
    print(("  OK   " if cond else "  XX   ") + label + (f"   {detail}" if detail and not cond else ""))
    if not cond:
        FAIL.append(f"{label} {detail}".strip())
    return cond


def void(label, why):
    VOIDED.append(f"{label}: {why}")
    print(f"  ??   {label}   VOID - {why}")


def importers(scripts):
    return sorted(p.name for p in scripts.glob("*.py")
                  if p.name != MODULE and IMPORT_RE.search(p.read_bytes().decode("utf-8")))


def argv_for(name, work):
    """How each importer reaches its import of the module. The header-footer script imports it LAZILY, in its
    legacy mode only; every other one imports at load, before it reads an argument - so a new importer that
    imports lazily fails case 1 here until somebody gives it its route, rather than passing unexamined."""
    if name == "translate_headers_footers.py":
        return [str(FIXTURE), str(work / "hf-out"), "--language", "italian"]
    return []


def run(scripts, name, work, extra=None):
    r = subprocess.run([sys.executable, str(scripts / name)] + (extra if extra is not None else argv_for(name, work)),
                       capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=str(work), env=ENV,
                       timeout=300)
    return r.returncode, (r.stdout or "") + (r.stderr or "")


class AnchorDrift(Exception):
    """An anchor the damage is cut at no longer occurs exactly once: the damage cannot be made, so the run is VOID."""


def line_index(lines, prefix):
    hits = [i for i, line in enumerate(lines) if line.startswith(prefix)]
    if len(hits) != 1:
        raise AnchorDrift(f"the anchor {prefix!r} occurs {len(hits)} times in {MODULE} - re-derive the damage")
    return hits[0]


def damaged(text, shape):
    """The module's text after the damage, or None for a deleted file. Pure LF, as the trees are."""
    lines = text.split("\n")
    call = line_index(lines, "_check_self_integrity()")
    if shape == "deleted":
        return None
    if shape == "cut mid-statement":
        i = line_index(lines, "LANGUAGE_MARKERS = {")   # the dict opened and never closed
        assert i > call, "a mid-statement cut must sit after the module's own check, or it proves nothing new"
        return "\n".join(lines[:i + 1]) + "\n"
    if shape == "cut before its check":
        return "\n".join(lines[:line_index(lines, "def _check_self_integrity")]) + "\n"
    if shape == "cut after its check":
        return "\n".join(lines[:line_index(lines, "def detect_language(")]) + "\n"
    if shape == "whole, importing a missing module":
        i = line_index(lines, "from collections import namedtuple")
        return "\n".join(lines[:i + 1] + ["import zz_no_such_module_here  # planted by the test"] + lines[i + 1:])
    raise ValueError(shape)


print("=" * 96)
print(f"A MISSING OR HALF-CUT {MODULE} EXITS AS A BROKEN INSTALL   [{VARIANT}]")
print("=" * 96)
found = importers(TREE / "scripts")
print(f"  importers discovered: {len(found)} (floor {FLOOR}): {', '.join(found)}")
if not ok(f"at least {FLOOR} importers discovered", len(found) >= FLOOR, f"found {len(found)}"):
    void("discovery", "fewer importers than measured - the pattern no longer matches the tree")
original = (TREE / "scripts" / MODULE).read_bytes().decode("utf-8")
SHAPES = ["deleted", "cut mid-statement", "cut before its check", "cut after its check"]
NOT_INSTALL = "whole, importing a missing module"
try:
    DAMAGE = {shape: damaged(original, shape) for shape in SHAPES + [NOT_INSTALL]}
except AnchorDrift as exc:
    DAMAGE = None
    void("the damage", str(exc))

with tempfile.TemporaryDirectory(prefix="langmod-") as td:
    td = Path(td)
    if DAMAGE is not None:
        # ---- the damage is the damage it claims, before any verdict is read
        print("\n  the damage, proved before it is used:")
        for shape in SHAPES[1:] + [NOT_INSTALL]:
            try:
                compile(DAMAGE[shape], MODULE, "exec")
                compiles = True
            except SyntaxError:
                compiles = False
            ok(f"{shape}: {'does not compile' if shape == 'cut mid-statement' else 'compiles'}",
               compiles == (shape != "cut mid-statement"))
        ok("cut before its check: none of the names the importers ask for survives",
           "def read_declared_language" not in DAMAGE["cut before its check"])

    # ---- the undamaged copy: nothing moves
    print("\n  UNDAMAGED - no importer exits 3, prints the banner or a traceback:")
    work = td / "whole"
    shutil.copytree(TREE, work / VARIANT)
    for name in found:
        rc, out = run(work / VARIANT / "scripts", name, work)
        ok(f"{name}: rc={rc}, no banner, no traceback",
           rc != 3 and BANNER not in out and "Traceback" not in out, out[-300:])

    # ---- the four shapes of a broken install, then the one that is NOT a broken install
    for shape in (SHAPES + [NOT_INSTALL]) if DAMAGE is not None else []:
        work = td / shape.replace(" ", "-").replace(",", "")
        shutil.copytree(TREE, work / VARIANT)
        target = work / VARIANT / "scripts" / MODULE
        if DAMAGE[shape] is None:
            target.unlink()
        else:
            target.write_bytes(DAMAGE[shape].encode("utf-8"))
        if shape == NOT_INSTALL:
            print(f"\n  {shape.upper()} - a defect in the module, not an install: NO banner, the missing module named:")
            for name in found:
                rc, out = run(work / VARIANT / "scripts", name, work)
                ok(f"{name}: rc={rc}", rc != 3 and BANNER not in out and "zz_no_such_module_here" in out,
                   out.strip()[-240:])
            continue
        print(f"\n  {shape.upper()} - every importer exits 3, the banner naming {MODULE}, no traceback:")
        for name in found:
            rc, out = run(work / VARIANT / "scripts", name, work)
            good = rc == 3 and BANNER in out and MODULE in out and "Traceback" not in out
            ok(f"{name}: rc={rc}", good, ("traceback; " if "Traceback" in out else "") + out.strip()[-240:])
        if shape == "deleted":
            # the partial-install pattern holds: the recommended round-trip never needed the module
            rc, out = run(work / VARIANT / "scripts", "translate_headers_footers.py", work,
                          [str(FIXTURE), "--extract", str(work / "scaffold.json")])
            ok("translate_headers_footers.py --extract still runs without the module (rc 0, scaffold written)",
               rc == 0 and (work / "scaffold.json").is_file(), out.strip()[-240:])

print("\n" + "=" * 96)
print(f"{CHECKED} check(s), {len(FAIL)} failure(s), {len(VOIDED)} void")
print("=" * 96)
for f in FAIL:
    print(f"  FAIL  {f}")
for v in VOIDED:
    print(f"  VOID  {v}")
sys.exit(1 if (FAIL or VOIDED) else 0)
