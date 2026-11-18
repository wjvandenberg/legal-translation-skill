# -*- coding: utf-8 -*-
"""test_authored_tabs.py - sub-step 16.7: tab positions per run (PLAN-2-step-b.md section 3.16).

WHAT 16.7 FOUND, MEASURED FIRST (temp/, counts only): over the 13 frozen workdirs, 97 notes entries sit on a source
paragraph with a tab BETWEEN two pieces of text. 25 are placed by step 6's table-of-contents rule; 23 are placed by
a tab the operator AUTHORED in `en` - apply's existing device, `\\t` written as a tab run and clause 3 dropping the
source's own tabs from the runs it rebuilds, so nothing is doubled (D01) - every one of the 23 placed; 10 are
skipped (`en` equal to the source); 39 carry no authored tab and are delivered glued. So the separator already has
a place to go back to wherever the English says where it is: what is missing is the operator being told to say it,
which is an instruction (step 17's rewrite) and a detection (step 18's row), not apply.

This suite proves that device on the shapes register A3's remainder and A6 name, invented, through the tree's own
apply, and pins the two declared remainders at their current outcome so a later step must change them on purpose:

  1  TP, A3's party grid: name, tab, share - authored, the tab between the two
  2  TP, A3's cost line: item, two tabs, amount - both tabs between, in order
  3  TP, A3's notices marker (D05's shape): `(a)`, then ONE run holding a tab and text, under a hanging indent -
     the tab between marker and text, the indent untouched
  4  TP, A6's glued bullet: ONE run holding bullet, tab and text - the tab between
  5  TP, A3's mid-phrase tabs (D11's shape): three words, two tabs - both between
  6  D01's shape: two source tabs, one authored - one tab, between, no orphan at the paragraph end
  7  no doubling, every authored case: the delivered tab count is the authored count, never authored + source
  10 clause 3's own shapes: a source tab in the FIRST text run before its text, or in the LAST after it, sits
     outside the text span, so only clause 3 keeps it from doubling an authored one (cases 1 to 6 sit inside the
     span, where clause 2's limit drops the source tab whatever clause 3 does)
  8  DECLARED REMAINDER, pinned: the party grid with no authored tab - delivered glued, as today (A3/A6 close
     when skill Step 4 tells the operator to author the tab: step 17's rewrite, step 18's rule)
  9  DECLARED REMAINDER, pinned: a source tab carrying underline - the authored tab run carries no run properties
     (measured: 12 underlined and 17 shaded tab runs in the corpus's between-text paragraphs, 0 of them under an
     authored entry; placed at step 18's plan)

A21 (ruby) is pinned in tests/test_container_inventory.py and declared there; no corpus document holds one.

RED FIRST is not applicable: 16.7 changes no shipped byte, and the device predates step 16. The mutants stand in
for it - each of the device's two deciding lines broken in a copy of the tree must turn this suite red
(temp/s1118b_mutants167.py). Invented words only, never anything from a real document.

    uv run --with lxml python tests/test_authored_tabs.py
    uv run --with lxml python tests/test_authored_tabs.py --variant us
    uv run --with lxml python tests/test_authored_tabs.py --scripts <folder>   # a mutated copy's scripts
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tests"))
# Imported before anything touches stdout: make_fixtures wraps it once, and a second wrapper closes the buffer.
from make_fixtures import docx, p, r  # noqa: E402
from read_receipt import file_receipt  # noqa: E402  (apply refuses to start without skill Step 3's receipt, C26)
from lxml import etree  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--variant", choices=("uk", "us"), default="uk")
ap.add_argument("--scripts", default=None)
args = ap.parse_args()
SCRIPTS = Path(args.scripts) if args.scripts else ROOT / args.variant / "scripts"
TMP = Path(tempfile.mkdtemp(prefix="s167-tabs-test-"))
ENV = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1", PYTHONDONTWRITEBYTECODE="1")
W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
TAB = chr(9)
FAIL, CHECKED = [], 0


def ok(label, cond, detail=""):
    global CHECKED
    CHECKED += 1
    print(f"  {'OK  ' if cond else 'XX  '} {label}" + (f"   ({detail})" if detail and not cond else ""))
    if not cond:
        FAIL.append(label)


TABRUN = "<w:r><w:tab/></w:r>"
HANG = '<w:pPr><w:ind w:left="1418" w:hanging="709"/></w:pPr>'

# (key, paragraph XML, source text as extraction writes it, the operator's en, authored tab count)
CASES = [
    ("grid", p(r("pars alpha"), TABRUN, r("33.33%")), "pars alpha33.33%",
     "party alpha" + TAB + "33.33%", 1),
    ("cost", p(r("res beta"), TABRUN, TABRUN, r("100")), "res beta100",
     "item beta" + TAB + TAB + "100", 2),
    ("marker", p(r("(a)"), '<w:r><w:tab/><w:t xml:space="preserve">si ad concedentem:</w:t></w:r>', ppr=HANG),
     "(a)si ad concedentem:", "(a)" + TAB + "if to the grantor:", 1),
    ("bullet", p('<w:r><w:t>' + chr(0x2022) + '</w:t><w:tab/><w:t xml:space="preserve">verbum primum</w:t></w:r>'),
     chr(0x2022) + "verbum primum", chr(0x2022) + TAB + "first word", 1),
    ("midphrase", p(r("unus"), TABRUN, r("duo"), TABRUN, r("tres")), "unusduotres",
     "one" + TAB + "two" + TAB + "three", 2),
    ("fewer", p(r("gamma"), TABRUN, TABRUN, r("delta")), "gammadelta",
     "gamma en" + TAB + "delta en", 1),
    ("leading", p('<w:r><w:tab/><w:t xml:space="preserve">textus primus</w:t></w:r>'), "textus primus",
     TAB + "first text", 1),
    ("trailing", p('<w:r><w:t xml:space="preserve">nomen ultimum</w:t><w:tab/></w:r>'), "nomen ultimum",
     "last name" + TAB, 1),
    ("unauthored", p(r("pars epsilon"), TABRUN, r("50%")), "pars epsilon50%",
     "party epsilon 50%", 0),
    ("underline", p(r("nomen"), '<w:r><w:rPr><w:u w:val="single"/></w:rPr><w:tab/></w:r>', r("datum")),
     "nomendatum", "name" + TAB + "date", 1),
]


def atoms(el):
    out = []
    for n in el.iter():
        tag = etree.QName(n).localname
        if tag == "t" and n.text:
            out.append("text")
        elif tag == "tab":
            par = n.getparent()
            if par is None or etree.QName(par).localname != "tabs":
                out.append("tab")
    return out


def between(at):
    """The tabs with text before and after them."""
    n = 0
    for i, a in enumerate(at):
        if a == "tab" and "text" in at[:i] and "text" in at[i + 1:]:
            n += 1
    return n


src = TMP / "src.docx"
docx(src, "".join(c[1] for c in CASES))
notes = [{"idx": i, "text": c[2], "en": c[3], "style": "Normal",
          "runs": [{"start": 0, "end": len(c[2]), "text": c[2], "bold": False, "italic": False}]}
         for i, c in enumerate(CASES)]
nj = TMP / "paragraphs.json"
nj.write_bytes(json.dumps(notes, ensure_ascii=False, indent=2).encode("utf-8"))
file_receipt(nj, SCRIPTS.parent)
out = TMP / "out.xml"
proc = subprocess.run(["uv", "run", "--with", "lxml", "python", str(SCRIPTS / "apply_translations_textmatch.py"),
                       str(src), str(nj), str(out)],
                      capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=str(ROOT), env=ENV,
                      timeout=900)

print("=" * 96)
print(f"  16.7 - an authored tab placed where the English says, real apply, {SCRIPTS.parent.name} tree, invented")
print("=" * 96)
if not out.is_file():   # assert the artefact, not the exit code
    print(f"  VOID - apply wrote no output (rc={proc.returncode})")
    print("  " + (proc.stderr or proc.stdout or "")[-800:])
    shutil.rmtree(TMP, ignore_errors=True)
    sys.exit(1)

src_ps = list(etree.fromstring(zipfile.ZipFile(src).read("word/document.xml")).iter(f"{{{W}}}p"))
out_ps = list(etree.fromstring(out.read_bytes()).iter(f"{{{W}}}p"))
ok("every invented paragraph delivered", len(out_ps) == len(CASES) == len(src_ps), f"{len(out_ps)} of {len(CASES)}")
by = {c[0]: (src_ps[i], out_ps[i], c) for i, c in enumerate(CASES)} if len(out_ps) == len(CASES) else {}


def got(key):
    s, o, c = by[key]
    return atoms(o), c


if by:
    print("\n1 to 5  TP - each named shape, the authored tabs between the text")
    for key, label in (("grid", "1 A3's party grid"), ("cost", "2 A3's cost line"),
                       ("marker", "3 A3's notices marker, tab and text in one run"),
                       ("bullet", "4 A6's glued bullet, bullet, tab and text in one run"),
                       ("midphrase", "5 A3's mid-phrase tabs")):
        at, c = got(key)
        ok(f"{label}: {c[4]} tab(s) between the text", between(at) == c[4] and at.count("tab") == c[4], f"{at}")
    mo = by["marker"][1]
    ind = mo.find(f"{{{W}}}pPr/{{{W}}}ind")
    ok("3 the hanging indent untouched", ind is not None and ind.get(f"{{{W}}}left") == "1418"
       and ind.get(f"{{{W}}}hanging") == "709")
    ot = "".join(t.text or "" for t in by["bullet"][1].iter(f"{{{W}}}t"))
    ok("4 the bullet and the English both delivered", ot == chr(0x2022) + "first word", "text differs")

    print("\n6  D01's shape - two source tabs, one authored")
    at, c = got("fewer")
    ok("one tab, between, none orphaned at the paragraph end", at == ["text", "tab", "text"], f"{at}")

    print("\n7  no doubling - the delivered tab count is the authored count")
    for key in ("grid", "cost", "marker", "bullet", "midphrase", "fewer", "leading", "trailing", "underline"):
        at, c = got(key)
        ok(f"{key}: {c[4]} delivered, never authored plus source", at.count("tab") == c[4], f"{at.count('tab')}")

    print("\n10  clause 3's own shapes - the source's tab inside the first or last text run, outside the text span")
    ok("a leading tab authored: one tab, before the text", got("leading")[0] == ["tab", "text"],
       f"{got('leading')[0]}")
    ok("a trailing tab authored: one tab, after the text", got("trailing")[0] == ["text", "tab"],
       f"{got('trailing')[0]}")

    print("\n8  DECLARED REMAINDER, pinned - no authored tab: delivered glued, as today")
    at, c = got("unauthored")
    ok("no tab between the text (step 17's instruction and step 18's rule change this on purpose)",
       between(at) == 0, f"{at}")
    ok("the English itself delivered, so the pin is not passing on a lost paragraph",
       "".join(t.text or "" for t in by["unauthored"][1].iter(f"{{{W}}}t")) == "party epsilon 50%", "text differs")

    print("\n9  DECLARED REMAINDER, pinned - the authored tab run carries no run properties")
    tab_runs = [t.getparent() for t in by["underline"][1].iter(f"{{{W}}}tab")
                if etree.QName(t.getparent()).localname == "r"]
    ok("one tab run, between the text", between(got("underline")[0]) == 1 and len(tab_runs) == 1)
    ok("the English either side delivered",
       "".join(t.text or "" for t in by["underline"][1].iter(f"{{{W}}}t")) == "namedate", "text differs")
    ok("its underline not carried (step 18's plan carries it on purpose)",
       all(tr.find(f"{{{W}}}rPr/{{{W}}}u") is None for tr in tab_runs))

shutil.rmtree(TMP, ignore_errors=True)
print("\n" + "=" * 96)
print(f"  {CHECKED} check(s), {len(FAIL)} failure(s)")
for f in FAIL:
    print(f"    XX  {f}")
print("=" * 96)
sys.exit(1 if FAIL else 0)
