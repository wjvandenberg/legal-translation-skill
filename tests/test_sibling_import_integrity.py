# -*- coding: utf-8 -*-
"""A CUT-SHORT SIBLING EXITS AS A BROKEN INSTALL; A MISSING ONE STAYS TOLERATED WHERE THAT WAS DESIGNED.

Five shipped scripts import a sibling script and, by design, carry on without it when it is MISSING - a partial
install: validate_apply -> post_process (an inlined copy of the spacing rule), validate_apply ->
translate_headers_footers (the side-part arm's reader, lazily), translate_headers_footers -> extract_paragraphs
(graphic metadata), repack_docx -> lexicon_compliance (a best-effort language agreement). The fifth,
validate_en_runs -> reorder_definitions, has no fallback at all. None of them could tell a sibling that is
ABSENT from one that is PRESENT BUT CUT SHORT, which is the broken install SKILL.md rule 6 answers by
re-installing: a cut mid-statement gave a raw traceback, or - where the handler was broad - a control that
silently went dark; a clean cut before the sibling's own check left its names missing, and the fallback ran as
if the file had never been shipped. tests/test_language_module_integrity.py did the same for the language module.

On a COPY of the tree, each route's sibling damaged five ways:

  DELETED                           the designed fallback runs - no exit 3, no banner, no traceback - on the
                                    four routes that tolerate it; on validate_en_runs, which never did, exit 3
  CUT MID-STATEMENT                 every importer exits 3, the banner naming the sibling, no traceback
  CUT CLEANLY BEFORE ITS CHECK      the same - the sibling loads and the names asked of it are missing
  CUT CLEANLY AFTER ITS CHECK       the sibling's OWN check exits 3: green before the fix and after it, the
                                    control that this harness can see an exit 3 at all
  WHOLE, IMPORTING A MISSING MODULE a defect in the sibling, not an install: NO banner

and the UNDAMAGED copy, where no importer prints the banner or a traceback. Where a run is NOT a broken install the
BANNER is the signal and not the exit code: validate_apply's delivered check exits 3 for its own VOID. Each damage is proved to be
the damage it claims (a mid-statement cut must not compile; every other cut must) before any verdict is read.

THE CLASS, NOT THE CALLER: every import of one shipped script by another is DISCOVERED by reading the tree, and
each must be the language module (the other suite's) or one of the five routes here - a sixth turns this red.

    uv run python tests/test_sibling_import_integrity.py [--variant us]

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
FIXTURE = ROOT / "tests" / "fixtures" / "headers-footers.docx"
BANNER = "FILE INTEGRITY CHECK FAILED"
LANGUAGE_MODULE = "source_language_markers"     # tests/test_language_module_integrity.py owns its importers
# (importer, sibling, how the importer reaches its import, whether a DELETED sibling is tolerated by design)
ROUTES = [
    ("validate_apply.py", "post_process.py", "load", True),
    ("validate_apply.py", "translate_headers_footers.py", "sides", True),
    ("translate_headers_footers.py", "extract_paragraphs.py", "load", True),
    ("repack_docx.py", "lexicon_compliance.py", "load", True),
    ("validate_en_runs.py", "reorder_definitions.py", "en_runs", False),
]
# the names each importer asks of its sibling: a clean cut before the sibling's own check must remove every one
NAMES = {"post_process.py": ["will_fix_spacing_fire"],
         "translate_headers_footers.py": ["_field_aware_text_and_fields", "_para_text"],
         "extract_paragraphs.py": ["_GRAPHIC_ATTR_SURFACES", "graphic_metadata_surfaces"],
         "lexicon_compliance.py": ["_guess_language"],
         "reorder_definitions.py": ["find_definitions_section_in_texts"]}
FROM_RE = re.compile(r"^[ \t]*from[ \t]+([A-Za-z_]\w*)[ \t]+import[ \t(]", re.M)
# `import a, b as c` names every module in the list, not only the first
IMPORT_RE = re.compile(r"^[ \t]*import[ \t]+([A-Za-z_][\w.]*(?:[ \t]+as[ \t]+\w+)?(?:[ \t]*,[ \t]*[A-Za-z_][\w.]*"
                       r"(?:[ \t]+as[ \t]+\w+)?)*)", re.M)
DYNAMIC_RE = re.compile(r"\bimport_module\(|\b__import__\(")
# THE TWO HELPERS ARE COPIED, NOT SHARED (no shared library, 2026-08-05): every copy must stay byte-identical
HELPERS = ("_sibling_integrity_exit", "_sibling_cut_short")
ENV = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1", PYTHONDONTWRITEBYTECODE="1")
PLANTED = "zz_no_such_module_here"
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


def sibling_imports(scripts):
    """Every (importer, sibling) pair in the tree: a script importing another script of the same folder."""
    stems = {p.stem for p in scripts.glob("*.py")}
    pairs = set()
    for p in sorted(scripts.glob("*.py")):
        text = p.read_bytes().decode("utf-8")
        mods = [m.group(1) for m in FROM_RE.finditer(text)]
        for m in IMPORT_RE.finditer(text):
            mods += [part.split()[0] for part in m.group(1).split(",") if part.strip()]
        for mod in mods:
            if mod in stems and mod != p.stem:
                pairs.add((p.name, mod + ".py"))
    return pairs


def dynamic_imports(scripts):
    """Scripts that load a module by name at run time - a route no import statement shows."""
    return sorted(p.name for p in scripts.glob("*.py") if DYNAMIC_RE.search(p.read_bytes().decode("utf-8")))


def helper_copies(scripts, name):
    """Every copy of a top-level helper: from its def line up to the next line that starts a new top-level
    statement, trailing blank lines dropped - keyed by the script that holds it."""
    out = {}
    for p in sorted(scripts.glob("*.py")):
        lines = p.read_bytes().decode("utf-8").split("\n")
        starts = [i for i, ln in enumerate(lines) if ln.startswith(f"def {name}(")]
        for s in starts:
            e = next((k for k in range(s + 1, len(lines)) if lines[k] and not lines[k][0].isspace()), len(lines))
            out[p.name] = "\n".join(lines[s:e]).rstrip("\n")
    return out


def argv_for(reach, work):
    """How each importer reaches its import. The three at load import before they read an argument; the side-part
    arm imports its reader only inside the delivered check against an original; validate_en_runs imports inside
    main, after its one argument is parsed."""
    if reach == "load":
        return []
    paragraphs = work / "paragraphs.json"
    paragraphs.write_bytes(b"[]")
    if reach == "sides":
        return [str(paragraphs), "--delivered", str(FIXTURE), "--original", str(FIXTURE)]
    if reach == "en_runs":
        return [str(paragraphs)]
    raise ValueError(reach)


def run(scripts, name, work, reach):
    r = subprocess.run([sys.executable, str(scripts / name)] + argv_for(reach, work), capture_output=True, text=True,
                       encoding="utf-8", errors="replace", cwd=str(work), env=ENV, timeout=300)
    return r.returncode, (r.stdout or "") + (r.stderr or "")


class AnchorDrift(Exception):
    """An anchor the damage is cut at no longer occurs exactly once: the damage cannot be made, so the run is VOID."""


def line_index(lines, prefix, module):
    hits = [i for i, line in enumerate(lines) if line.startswith(prefix)]
    if len(hits) != 1:
        raise AnchorDrift(f"the anchor {prefix!r} occurs {len(hits)} times in {module} - re-derive the damage")
    return hits[0]


def damaged(text, shape, module):
    """The sibling's text after the damage, or None for a deleted file. Pure LF, as the trees are."""
    lines = text.split("\n")
    call = line_index(lines, "_check_self_integrity()", module)
    if shape == "deleted":
        return None
    if shape == "cut mid-statement":
        # the first line after the sibling's own check that OPENS a bracket and ends there: cut just after it, the
        # bracket never closes and the file cannot compile - so the check never runs either
        opener = next((i for i in range(call + 1, len(lines)) if lines[i].rstrip().endswith(("(", "[", "{"))), None)
        if opener is None:
            raise AnchorDrift(f"no line after {module}'s own check opens a bracket - re-derive the damage")
        return "\n".join(lines[:opener + 1]) + "\n"
    if shape == "cut before its check":
        return "\n".join(lines[:line_index(lines, "def _check_self_integrity", module)]) + "\n"
    if shape == "cut after its check":
        return "\n".join(lines[:call + 1]) + "\n"
    if shape == "whole, importing a missing module":
        i = next((k for k, line in enumerate(lines) if re.match(r"import (os|sys|re)\b", line)), None)
        if i is None:
            raise AnchorDrift(f"no top-level 'import os|sys|re' line in {module} - re-derive the damage")
        return "\n".join(lines[:i + 1] + [f"import {PLANTED}  # planted by the test"] + lines[i + 1:])
    raise ValueError(shape)


SHAPES = ["deleted", "cut mid-statement", "cut before its check", "cut after its check"]
NOT_INSTALL = "whole, importing a missing module"

print("=" * 96)
print(f"A CUT-SHORT SIBLING EXITS AS A BROKEN INSTALL; A MISSING ONE STAYS TOLERATED WHERE DESIGNED   [{VARIANT}]")
print("=" * 96)
scripts_dir = TREE / "scripts"
found = sibling_imports(scripts_dir)
others = sorted(p for p in found if p[1] != LANGUAGE_MODULE + ".py")
declared = sorted((i, s) for i, s, _r, _t in ROUTES)
print(f"  sibling imports discovered: {len(found)} - {len(found) - len(others)} of the language module "
      f"(the other suite's), {len(others)} others")
ok("the other sibling imports are exactly the five routes here", others == declared,
   f"undeclared {sorted(set(others) - set(declared))}, declared but absent {sorted(set(declared) - set(others))}")
dyn = dynamic_imports(scripts_dir)
ok("no shipped script loads a module by name at run time (importlib.import_module, __import__)", not dyn,
   f"found in {dyn} - a sibling route no import statement shows; give it its route here")
for helper in HELPERS:
    copies = helper_copies(scripts_dir, helper)
    variants = sorted(set(copies.values()))
    print(f"  {helper}: {len(copies)} cop{'y' if len(copies) == 1 else 'ies'} in {', '.join(copies)}")
    ok(f"every copy of {helper} is byte-identical", len(copies) >= 1 and len(variants) == 1,
       f"{len(variants)} different versions among {len(copies)} copies")
DAMAGE = {}
try:
    for _imp, sib, _r, _t in ROUTES:
        if sib not in DAMAGE:
            text = (scripts_dir / sib).read_bytes().decode("utf-8")
            DAMAGE[sib] = {shape: damaged(text, shape, sib) for shape in SHAPES + [NOT_INSTALL]}
except AnchorDrift as exc:
    DAMAGE = None
    void("the damage", str(exc))

with tempfile.TemporaryDirectory(prefix="sibling-") as td:
    td = Path(td)
    if DAMAGE is not None:
        print("\n  the damage, proved before it is used:")
        for sib, shapes in DAMAGE.items():
            for shape in SHAPES[1:] + [NOT_INSTALL]:
                try:
                    compile(shapes[shape], sib, "exec")
                    compiles = True
                except SyntaxError:
                    compiles = False
                ok(f"{sib} {shape}: {'does not compile' if shape == 'cut mid-statement' else 'compiles'}",
                   compiles == (shape != "cut mid-statement"))
            left = [n for n in NAMES[sib]
                    if re.search(rf"^(?:def {n}\(|{n}\s*=)", shapes["cut before its check"], re.M)]
            ok(f"{sib} cut before its check: none of the names its importer asks for survives", not left,
               f"still defined: {left}")

    # THE BANNER IS THE SIGNAL, NOT THE EXIT CODE, wherever a run is NOT a broken install: validate_apply's delivered
    # check exits 3 for its own VOID ("nothing was examined") - the side-part route's empty paragraphs list gives one -
    # so an exit 3 there is that script's verdict, and only the FILE INTEGRITY banner says the install is broken.
    print("\n  UNDAMAGED - no importer prints the banner or a traceback:")
    work = td / "whole"
    shutil.copytree(TREE, work / VARIANT)
    for imp, sib, reach, _t in ROUTES:
        rc, out = run(work / VARIANT / "scripts", imp, work, reach)
        ok(f"{imp} ({reach}): rc={rc}, no banner, no traceback",
           BANNER not in out and "Traceback" not in out, out.strip()[-300:])

    for n, (imp, sib, reach, tolerated) in enumerate(ROUTES if DAMAGE is not None else []):
        print(f"\n  ROUTE {n + 1}: {imp} -> {sib} ({reach})")
        for shape in SHAPES + [NOT_INSTALL]:
            work = td / f"r{n + 1}-{shape.replace(' ', '-').replace(',', '')}"
            shutil.copytree(TREE, work / VARIANT)
            target = work / VARIANT / "scripts" / sib
            if DAMAGE[sib][shape] is None:
                target.unlink()
            else:
                target.write_bytes(DAMAGE[sib][shape].encode("utf-8"))
            rc, out = run(work / VARIANT / "scripts", imp, work, reach)
            tail = ("traceback; " if "Traceback" in out else "") + out.strip()[-240:]
            if shape == NOT_INSTALL:
                ok(f"{shape}: rc={rc}, NO banner - a defect in the sibling, not an install", BANNER not in out, tail)
            elif shape == "deleted" and tolerated:
                ok(f"{shape}: the designed fallback runs - rc={rc}, no banner, no traceback",
                   BANNER not in out and "Traceback" not in out, tail)
            else:
                ok(f"{shape}: rc={rc}, the banner naming {sib}, no traceback",
                   rc == 3 and BANNER in out and sib in out and "Traceback" not in out, tail)

print("\n" + "=" * 96)
print(f"{CHECKED} check(s), {len(FAIL)} failure(s), {len(VOIDED)} void")
print("=" * 96)
for f in FAIL:
    print(f"  FAIL  {f}")
for v in VOIDED:
    print(f"  VOID  {v}")
sys.exit(1 if (FAIL or VOIDED) else 0)
