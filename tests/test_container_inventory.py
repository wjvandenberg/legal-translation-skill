# -*- coding: utf-8 -*-
"""BRANCH 7 — THE CONTAINER INVENTORY. The synthetic arm.

Option 1's second and last branch. Four accountable rows from PLAN-2-step-b.md section 9.3:
A16 A19 N1 C19. This file covers the APPLY side -- A16 and N1 -- plus the two shapes measured
in the same sweep that no register row names.

WHY THE FIXTURE HAD TO BE REBUILT BEFORE THIS SUITE COULD EXIST. containers.docx carried four
shapes taken from the four rows' TITLES, and measured through the real apply on 2026-09-08 its
`w:sdt` shape was CORRECT: it wrapped a whole PARAGRAPH, whose runs are direct children of
their own w:p, so apply rebuilds them normally. A16's measured defect is the INLINE MIXED case
-- an sdt beside ordinary runs -- and the fixture built from the row's title carried the one
shape the row itself says is fine. Read the ROW, not its title.

THE INVENTORY'S POPULATION IS MEASURED, NOT ENUMERATED FROM A SCHEMA. Across all 52
WordprocessingML parts of 10 of the 11 corpus documents (the eleventh is a legacy binary .doc
and was not opened, so every zero is a zero over 10 of 11), the complete set of non-run
children of `w:p` is: pPr, ins, del, proofErr, commentRangeStart, commentRangeEnd,
bookmarkStart, bookmarkEnd, sdt, smartTag. THREE of them carry text -- ins (188), sdt (6),
smartTag (1). There is no math anywhere, which is the shape that would otherwise make the
refusal below fire on input the operator cannot change.

WHAT THIS FILE COVERS, stated because a green suite that quietly covers less than it appears
to is this project's most frequent failure:

  A16   the five inline w:sdt shapes -- mixed, alone, with a footnote anchor, with a tab, and
        the block shapes as the POSITIVE CONTROLS they always were
  N1    w:smartTag mixed, and nested
  --    w:customXml, w:dir and w:bdo, which strand text identically and are named in NO row
  --    w:ruby, DESTROYED outright (ruby/rubyBase/rt 1->0), asserted as the CURRENT outcome
        so a later branch must change it deliberately

WHAT IT DOES NOT COVER, each a declared N/A with its reason rather than an omission:

  A22   w:fldSimple's duplicated cached result. It HAD a shape here and it was taken out on
        measurement: the field renders its number straight after the collapsed English, and
        gluing two atoms merges token types, so `validate_apply --strict` REFUSES THE REPACK.
        A22 is therefore a DEADLOCK rather than a cosmetic duplication -- a sharper statement
        of its severity than a pin -- and a fixture carrying it can never be repacked, so
        every other shape would lose its rendered page. See A22_FIXTURE_OWED below.
  A19   the graphic-metadata surface is slice 3's, and the fixture carries its alt text and
        chart title so this suite asserts only that apply leaves them alone
  C19   the glossary part is slice 2's -- repack, not apply
  a VML TEXT BOX. Measured CLEAN in temp/probe_container_gaps.py, and the corpus's 8
        txbxContent all sit in headers and footers, which translate_headers_footers.py owns
        and handles correctly through _iter_own_runs. Adding it here would need the VML
        namespace on docx(), rewriting every fixture's bytes for a shape that is not broken.
  a HEADER/FOOTER inline sdt. 1 of the corpus's such sdt is a child of a w:p. Measured: that
        translator writes into the first w:t and clears the rest, so it strands nothing.

    uv run --with lxml python tests/test_container_inventory.py
    uv run --with lxml python tests/test_container_inventory.py --variant us

Synthetic fixture only. No client text.
"""
import argparse
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.dont_write_bytecode = True
# Reaches grandchildren, which sys.dont_write_bytecode cannot: apply spawns validators as
# subprocesses and one of them imports post_process, so a .pyc lands inside the shipped tree.
# Gitignored, invisible to a diff, and precommit_gate correctly fails on it. Register I-18.
os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")

sys.path.insert(0, str(Path(__file__).resolve().parent))
from make_fixtures import CONTAINER_SHAPES, CONTAINER_EN  # noqa: E402
from lxml import etree  # noqa: E402

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
ROOT = Path(__file__).resolve().parent.parent
FIX = ROOT / "tests" / "fixtures" / "containers.docx"
NOTES = ROOT / "tests" / "fixtures" / "containers.notes.json"

ap = argparse.ArgumentParser()
ap.add_argument("--variant", default="uk", choices=("uk", "us"))
ap.add_argument("--keep", action="store_true", help="keep the temp workdir for inspection")
args = ap.parse_args()

FAIL, CHECKED, VOIDED = [], 0, []


def ok(label, cond, detail=""):
    global CHECKED
    CHECKED += 1
    print(("  OK   " if cond else "  XX   ") + label
          + (f"   {detail}" if detail and not cond else ""))
    if not cond:
        FAIL.append(f"{label} {detail}".strip())
    return cond


def void(label, why):
    """A check that could not establish anything is VOID, never a pass. CLAUDE.md 5.3."""
    VOIDED.append(f"{label}: {why}")
    print(f"  ??   {label}   VOID — {why}")


# =========================================================================================
# ONE LIST, READ EVERYWHERE.
#
# The probe this suite grew out of had a SECOND copy of the container set inside its verdict
# function, and that copy omitted `ruby` -- which the shapes list sweeps. So a container
# DELETED OUTRIGHT came back CLEAN, because the verdict could not see the loss of a tag it
# did not know about. That is PR #64's finding arriving from a new direction: two definitions
# of one rule in one file will disagree, and the one that loses is silent.
#
# So: every tag whose survival is scored lives here, once, and the shape table lives in
# make_fixtures.py, once, and this file imports it rather than restating it.
# =========================================================================================
SCORED = ("sdt", "smartTag", "customXml", "dir", "bdo", "fldSimple", "hyperlink",
          "subDoc", "ins", "del", "ruby", "rubyBase", "rt")

# THE ANNOTATION WRAPPERS, whose disappearance once emptied is the DECIDED OUTCOME rather
# than a loss — Wouter, 2026-09-08. They are separated from `LOST` because the first version
# of this file used one word for both, and that is exactly register row I-21's defect: one
# word covering a file that was read and a file that was not. A deliberate drop and a
# destroyed annotation are not the same event, and a suite that calls them the same thing
# cannot tell the next reader which happened.
DROPPABLE = ("smartTag", "customXml", "dir", "bdo")


def containers_in(el):
    """Every scored container tag anywhere inside `el`, with counts.

    RECURSIVE ON PURPOSE. `w:ruby` sits INSIDE a run, so a direct-children-only test cannot
    see it at all -- and it is the one shape that is destroyed rather than merely stranded.
    """
    got = {}
    for x in el.iter():
        tag = etree.QName(x).localname
        if tag in SCORED:
            got[tag] = got.get(tag, 0) + 1
    return got


def para_text(p):
    """EXACTLY apply's own get_paragraph_text: w:t only, plain w:br -> newline, then strip.

    Copied rather than approximated because MATCHING depends on it: get it wrong and apply
    reports NOT FOUND, rebuilds nothing, and every assertion below passes for the wrong
    reason.
    """
    out = []
    for el in p.iter():
        tag = etree.QName(el).localname
        if tag == "t" and el.text:
            out.append(el.text)
        elif tag == "br" and el.get(f"{{{W}}}type", "") != "page":
            out.append("\n")
    return "".join(out).strip()


def run_apply(work, source_xml, notes, label, fixture=None, expect_block=False):
    """Run apply on the fixture with the given notes. Returns (xml bytes | None, result).

    THE INPUT IS COPIED INTO A TEMP DIRECTORY, NEVER READ FROM tests/fixtures/. apply's final
    pre-apply pass is validate_translations.py, which writes .validate-state.json beside the
    NOTES file -- so pointing it at the fixtures directory puts run state into the git index.
    That happened once, on branch 6 slice 3, and it broke `git switch` and therefore
    `git bisect`, which is the one tool the whole test method exists to enable.
    """
    work.mkdir(parents=True, exist_ok=True)
    orig = work / "orig.docx"
    shutil.copyfile(fixture or FIX, orig)
    pj = work / "paragraphs.json"
    pj.write_text(json.dumps(notes, ensure_ascii=False), encoding="utf-8")
    out = work / "out.xml"
    env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1",
               PYTHONDONTWRITEBYTECODE="1")
    res = subprocess.run(
        ["uv", "run", "--with", "lxml", "python",
         str(ROOT / args.variant / "scripts" / "apply_translations_textmatch.py"),
         str(orig), str(pj), str(out)],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        cwd=str(ROOT), env=env, timeout=600)
    if expect_block:
        return (out.read_bytes() if out.exists() else None), res
    # ASSERT THE ARTEFACT, NOT THE EXIT CODE. A run that skipped every paragraph, matched
    # nothing, or died after printing its summary all exit 0. CLAUDE.md 5.3.
    if not out.exists():
        print(f"\n  {label}: apply wrote no output (rc={res.returncode}).")
        print("  " + (res.stderr or res.stdout or "").strip()[-1200:])
        return None, res
    data = out.read_bytes()
    if data == source_xml:
        print(f"\n  {label}: output is byte-identical to input, so apply rebuilt NOTHING.")
        print("  Every assertion below would pass vacuously. This is VOID, not clean.")
        return None, res
    if "Total changes applied: 0" in (res.stdout or ""):
        print(f"\n  {label}: apply reported 0 changes.")
        return None, res
    return data, res


TMP = Path(tempfile.mkdtemp(prefix="b7-containers-"))
with zipfile.ZipFile(FIX) as z:
    SRC = z.read("word/document.xml")
src_root = etree.fromstring(SRC)
SRC_PARAS = list(src_root.iter(f"{{{W}}}p"))
FIXTURE_NOTES = json.loads(NOTES.read_text(encoding="utf-8"))

# THE SHAPE OF EACH ROW, and which paragraph indices it owns. One shape may contribute more
# than one paragraph, because a block container wraps one.
SHAPE_AT = []
_i = 0
for _lbl, _remnant, _why, _xml in CONTAINER_SHAPES:
    _n = _xml.count("<w:p>")
    SHAPE_AT.append((_lbl, _remnant, _why, list(range(_i, _i + _n))))
    _i += _n

print("=" * 106)
print(f"BRANCH 7 — THE CONTAINER INVENTORY · synthetic arm · {args.variant}/scripts/"
      "apply_translations_textmatch.py")
print("=" * 106)

# =========================================================================================
# 0. THE POSITIVE CONTROL. Plant nothing, but PROVE the fixture carries every needle. An
#    assertion that a count went 0 -> 0 is the clean-looking zero CLAUDE.md 5.3 rule 6 is
#    about, and it is indistinguishable from a real pass.
# =========================================================================================
# =========================================================================================
# 0a. THE INVENTORY IS ACTUALLY SHARED. This is the check that makes the word "shared" mean
#     something: option 1 requires ONE inventory across the reading and the writing halves,
#     the 2026-08-05 decision rules out a shared library, so the tuples are stated four times
#     — extract and apply, in each of two trees — and their equality is asserted here.
#
#     WITHOUT THIS CHECK THE RULE IS UNENFORCEABLE, AND THAT IS THE WHOLE POINT OF THE ROW.
#     A16 and N1 exist because extraction descended into a container and apply did not: the
#     defect was the ASYMMETRY, not either half. A widening applied to one side and forgotten
#     on the other recreates exactly that, and nothing else in the project would report it.
# =========================================================================================
print("\n0a. ONE INVENTORY, STATED FOUR TIMES, AND THE FOUR MUST BE EQUAL")
_TUPLES = ("_CONTAINER_RECURSE", "_CONTAINER_DECLINED", "_CONTAINER_TC",
           "_PARA_CHILD_INERT")


def _read_tuples(path):
    """Pull the four tuples out of a script's SOURCE by literal evaluation.

    Read rather than imported: importing a shipped script runs its integrity check and its
    argparse, and one of them exits. `ast.literal_eval` cannot execute anything, so a
    malformed source fails loudly here instead of running.
    """
    import ast
    src = path.read_text(encoding="utf-8")
    got = {}
    tree = ast.parse(src)
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        for tgt in node.targets:
            if isinstance(tgt, ast.Name) and tgt.id in _TUPLES:
                try:
                    got[tgt.id] = ast.literal_eval(node.value)
                except ValueError:
                    got[tgt.id] = "NOT A LITERAL"
    return got


_INV = {}
for _tree in ("uk", "us"):
    for _script in ("extract_paragraphs.py", "apply_translations_textmatch.py"):
        _INV[f"{_tree}/{_script}"] = _read_tuples(
            ROOT / _tree / "scripts" / _script)
for _name in _TUPLES:
    _vals = {k: v.get(_name) for k, v in _INV.items()}
    ok(f"{_name} is present in all four files",
       all(v is not None for v in _vals.values()),
       "missing from: " + ", ".join(k for k, v in _vals.items() if v is None))
    _distinct = {tuple(v) for v in _vals.values() if v is not None}
    ok(f"{_name} is IDENTICAL across extract and apply, in both trees",
       len(_distinct) == 1,
       f"{len(_distinct)} different values across the four files")
_rec = _INV["uk/apply_translations_textmatch.py"].get("_CONTAINER_RECURSE") or ()
ok("the recursed set is the six containers measured to need it",
   set(_rec) == {"hyperlink", "sdt", "smartTag", "customXml", "dir", "bdo"},
   f"is {sorted(_rec)}")
_dec = _INV["uk/apply_translations_textmatch.py"].get("_CONTAINER_DECLINED") or ()
ok("w:fldSimple is DECLARED as declined rather than left unknown — so a document carrying "
   "one gets the pinned duplication, not a block",
   "fldSimple" in _dec)
_inert = _INV["uk/apply_translations_textmatch.py"].get("_PARA_CHILD_INERT") or ()
ok("math is DECLARED inert — m:oMath is in EG_PContent and can hold runs, so leaving it "
   "unknown would refuse an inline equation the operator cannot remove",
   "oMath" in _inert and "oMathPara" in _inert)
# Every non-run child of w:p the corpus actually contains, measured across all 52 WML parts
# of 10 of the 11 documents. A gate whose known-set does not cover the measured population
# would fire on real input.
for _m in ("pPr", "ins", "del", "proofErr", "commentRangeStart", "commentRangeEnd",
           "bookmarkStart", "bookmarkEnd", "sdt", "smartTag"):
    ok(f"the measured corpus child <w:{_m}> is in the known set",
       _m in (_INV["uk/apply_translations_textmatch.py"].get("_CONTAINER_RECURSE", ())
              + _INV["uk/apply_translations_textmatch.py"].get("_CONTAINER_DECLINED", ())
              + _INV["uk/apply_translations_textmatch.py"].get("_CONTAINER_TC", ())
              + _INV["uk/apply_translations_textmatch.py"].get("_PARA_CHILD_INERT", ())))

print("\n0. THE FIXTURE CARRIES THE NEEDLES  (a 0 -> 0 assertion proves nothing)")
ok(f"the fixture has {_i} paragraphs, one per declared shape row",
   len(SRC_PARAS) == _i, f"has {len(SRC_PARAS)}, the shape table declares {_i}")
ok("its notes sidecar has one entry per paragraph",
   len(FIXTURE_NOTES) == len(SRC_PARAS),
   f"{len(FIXTURE_NOTES)} note(s) against {len(SRC_PARAS)} paragraph(s)")
WHOLE = containers_in(src_root)
for tag, least in (("sdt", 6), ("smartTag", 3), ("customXml", 1), ("dir", 1), ("bdo", 1),
                   ("hyperlink", 1), ("subDoc", 1), ("ins", 1),
                   ("ruby", 1), ("rubyBase", 1), ("rt", 1)):
    ok(f"fixture carries <w:{tag}>", WHOLE.get(tag, 0) >= least,
       f"found {WHOLE.get(tag, 0)}, expected at least {least}")
# A19's two surfaces are attributes and a separate part, so they are proved differently.
ok("fixture carries alt text in wp:docPr/@descr",
   any(el.get("descr") for el in src_root.iter()))
ok("fixture carries a @title beside the alt text",
   any(el.get("title") for el in src_root.iter()))
with zipfile.ZipFile(FIX) as z:
    _chart = z.read("word/charts/chart1.xml").decode("utf-8") \
        if "word/charts/chart1.xml" in z.namelist() else ""
ok("fixture carries a chart part with a title AND an axis title",
   _chart.count("<c:title>") >= 2, f"{_chart.count('<c:title>')} c:title element(s)")

# =========================================================================================
# 1. THE VERDICT PER SHAPE. Computed ONCE by `verdict()`, then read for the per-row
#    assertion AND for the summary, with the arithmetic asserted.
#
#    PR #64's finding, and it is why this is structured this way: a suite's per-row test and
#    its summary counters each held a copy of one rule, the two disagreed, and 14 + 10 + 1
#    did not add up to 26 with nothing asserting that it should.
# =========================================================================================
OUT, res = run_apply(TMP / "main", SRC, FIXTURE_NOTES, "main arm")
if OUT is None:
    print("\nThe main arm produced nothing usable. Everything below is VOID, not clean.")
    print(f"FAILURES: {len(FAIL)}   CHECKED: {CHECKED}   VOID: 1")
    sys.exit(1)
out_root = etree.fromstring(OUT)
OUT_PARAS = list(out_root.iter(f"{{{W}}}p"))


def verdict(idxs):
    """(verdict, detail) for one shape. THE ONLY DEFINITION.

    A delivered `w:t` is source language iff its text equals one of the SOURCE paragraph's
    own `w:t` strings. THREE WEAKER TESTS WERE TRIED AND EACH FAILED SILENTLY:

      a sentinel prefix on `en`    -- the tracked-change path distributes ONE English string
                                      across several w:t, so only the first fragment carried
                                      the marker and all-English output read as REMNANT;
      "is it a substring of `en`"  -- a surviving one-character field result `7` is a
                                      substring of the token `z7`, so a real remnant read
                                      CLEAN;
      a direct-children container scan -- w:ruby sits inside a run, so its destruction was
                                      invisible.

    make_fixtures._notes_from_document asserts that no `en` reproduces a source `w:t`
    verbatim, which is what makes the equality test above sound.

    w:delText is a TRACKED DELETION and stays in the source language legitimately, so only
    w:t is scored.
    """
    if any(i >= len(OUT_PARAS) for i in idxs):
        return "MISSING", "the delivered document has fewer paragraphs than the source"
    src_c, out_c = {}, {}
    src_texts, out_texts = set(), []
    for i in idxs:
        for k, v in containers_in(SRC_PARAS[i]).items():
            src_c[k] = src_c.get(k, 0) + v
        for k, v in containers_in(OUT_PARAS[i]).items():
            out_c[k] = out_c.get(k, 0) + v
        for t in SRC_PARAS[i].iter(f"{{{W}}}t"):
            if (t.text or "").strip():
                src_texts.add(t.text.strip())
        for t in OUT_PARAS[i].iter(f"{{{W}}}t"):
            if (t.text or "").strip():
                out_texts.append(t.text.strip())
    lost = {k: (src_c[k], out_c.get(k, 0)) for k in src_c if out_c.get(k, 0) < src_c[k]}
    source = [t for t in out_texts if t in src_texts]
    english = [t for t in out_texts if t not in src_texts]
    if not english:
        return "SKIPPED", "no English reached the delivered paragraph"
    if source:
        return "REMNANT", (f"{len(source)} source-language w:t survive(s)"
                           + (" and " + ",".join(f"{k} {a}->{b}"
                                                 for k, (a, b) in sorted(lost.items()))
                              if lost else ""))
    if lost:
        # A DROPPED ANNOTATION IS NOT A LOSS, AND THE TWO GET DIFFERENT WORDS. Everything
        # gone is a droppable wrapper -> DROPPED, the decided outcome. Anything else gone --
        # a content control, a hyperlink, a ruby annotation -- is LOST.
        gone = ",".join(f"{k} {a}->{b}" for k, (a, b) in sorted(lost.items()))
        if all(k in DROPPABLE for k in lost):
            return "DROPPED", gone
        return "LOST", gone
    return "CLEAN", ""


VERDICTS = {lbl: verdict(idxs) for lbl, _, _, idxs in SHAPE_AT}

# THE TARGET STATE. Every shape must come back CLEAN except these two, whose current outcome
# is PINNED so that a later branch has to change this line deliberately rather than silently
# — the same device tests/test_stop_deleting.py uses for A3's relocation case.
#
# THE SHAPE TABLE'S OWN SECOND FIELD IS NOT USED HERE, AND THAT IS DELIBERATE. It is a DATED
# record of what apply did before this branch; this is the assertion. A suite that asserted
# the pre-fix measurement would go red on the commit that fixed it, which is the opposite of
# what a regression test is for.
PINNED = {
    "smarttag-trailing": ("DROPPED",
                          "the decided outcome, not a pin on a defect: an annotation over "
                          "text that no longer exists is provably redundant, which is clause "
                          "3's own test and the only licence this branch has to delete "
                          "anything"),
    "ruby-in-run": ("LOST",
                    "apply destroys the annotation outright, and putting it back needs the "
                    "per-run English branch 15 emits — not a container inventory"),
}

# A DECLARED N/A WITH ITS REASON, NEVER AN OMISSION. Register row A22 -- a `w:fldSimple`
# whose consumed cached result prints the number twice -- HAS NO COMMITTED FIXTURE, and that
# is a measurement rather than a shortfall:
#
#   the field renders its number immediately after the collapsed English, so the delivered
#   text reads `...instrument.4.2` -- and gluing two atoms MERGES TOKEN TYPES, so
#   `validate_apply --strict` REFUSES THE REPACK. Measured on this branch: A22 is a DEADLOCK,
#   not a cosmetic duplication, which is a sharper statement of its severity than a pin.
#
#   A fixture carrying that shape therefore cannot be repacked at all, so every other shape
#   in it loses its rendered page -- and bypassing the gate for the NEW arm is exactly what
#   CLAUDE.md 5.7 forbids. render_diff byte-substitutes a refused OLD arm legitimately,
#   because that arm is a picture of a defect rather than a deliverable.
#
# So A22's evidence is its register row plus temp/probe_container_gaps.py's 20-shape run, and
# the fixture is OWED BY WHICHEVER BRANCH FIXES IT -- which must settle clause 3's keyword
# question first, since that clause was narrowed to the REF family on a corpus measurement.
A22_FIXTURE_OWED = ("a w:fldSimple whose consumed cached result makes validate_apply --strict "
                    "refuse the repack; needs its own fixture and --expect-block")

print("\n1. WHAT APPLY DOES TO EACH SHAPE")
print(f"     {'shape':<22} {'target':<9} {'measured':<9}")
for lbl, was_red, why, idxs in SHAPE_AT:
    v, detail = VERDICTS[lbl]
    want = PINNED.get(lbl, ("CLEAN", ""))[0]
    print(f"     {lbl:<22} {want:<9} {v:<9} {detail}"
          + ("   [PINNED]" if lbl in PINNED else ""))
    ok(f"{lbl} -> {want}", v == want, f"measured {v}: {detail}")

TALLY = {}
for v, _ in VERDICTS.values():
    TALLY[v] = TALLY.get(v, 0) + 1
print("\n     verdicts: " + "  ".join(f"{k}={v}" for k, v in sorted(TALLY.items())))
ok("the verdict tally accounts for every shape, with nothing double-counted",
   sum(TALLY.values()) == len(SHAPE_AT) == len(CONTAINER_SHAPES),
   f"tally {sum(TALLY.values())}, shapes {len(SHAPE_AT)}, "
   f"table {len(CONTAINER_SHAPES)}")
ok("every shape label has an English string",
   all(lbl in CONTAINER_EN for lbl, _, _, _ in SHAPE_AT))
ok("every PINNED label is a shape that exists — a pin on a label nobody builds is a check "
   "that cannot fail",
   all(any(lbl == s[0] for s in SHAPE_AT) for lbl in PINNED),
   "PINNED names a label the shape table does not carry")
ok(f"the target is CLEAN for {len(SHAPE_AT) - len(PINNED)} shapes and PINNED for "
   f"{len(PINNED)}, and those two add up to the table",
   (len(SHAPE_AT) - len(PINNED)) + len(PINNED) == len(CONTAINER_SHAPES))

# =========================================================================================
# 2. READING ORDER — the second consequence, and it is not the remnant.
#
#    `_first_text_container` looks only at direct-child w:r and at w:hyperlink, so text
#    inside any other container is INVISIBLE to it. Where the container holds the
#    paragraph's FIRST text, the English is therefore placed AFTER it: the delivered
#    paragraph's reading order is wrong before anything is deleted. Measured on 6 of the 20
#    swept shapes.
# =========================================================================================
print("\n2. READING ORDER — where the source's FIRST text sits inside the container")


def first_text_is_english(i):
    src_texts = {(t.text or "").strip() for t in SRC_PARAS[i].iter(f"{{{W}}}t")
                 if (t.text or "").strip()}
    for child in OUT_PARAS[i]:
        if etree.QName(child).localname == "pPr":
            continue
        got = [(t.text or "").strip() for t in child.iter(f"{{{W}}}t")
               if (t.text or "").strip()]
        if got:
            return any(g not in src_texts for g in got)
    return None


def source_first_text_in_container(i):
    for child in SRC_PARAS[i]:
        tag = etree.QName(child).localname
        if tag == "pPr":
            continue
        if any((t.text or "").strip() for t in child.iter(f"{{{W}}}t")):
            return tag != "r"
    return False


_order_rows = [(lbl, idxs[0]) for lbl, _, _, idxs in SHAPE_AT
               if source_first_text_in_container(idxs[0])]
ok("the fixture actually contains the order shape at all",
   len(_order_rows) >= 5, f"{len(_order_rows)} paragraph(s) start with a container")
for lbl, i in _order_rows:
    ok(f"{lbl}: the English is the paragraph's FIRST text, as in the source",
       first_text_is_english(i) is True,
       "the source's first text sits in the container and the English follows it")

# =========================================================================================
# 3. THE SHAPES THAT ARE PINNED RATHER THAN FIXED — declared, so a later branch has to change
#    this file deliberately instead of silently.
# =========================================================================================
print("\n3. PINNED, NOT FIXED — the current outcome asserted so it cannot move in silence")
_ruby = next(i for lbl, _, _, idxs in SHAPE_AT if lbl == "ruby-in-run" for i in idxs)
_rv, _rd = VERDICTS["ruby-in-run"]
ok("ruby-in-run: apply still DESTROYS the annotation (ruby/rubyBase/rt), pinned for a "
   "later branch", _rv == "LOST" and "ruby" in _rd, f"measured {_rv}: {_rd}")
ok("ruby-in-run: and no text is lost with it — extraction glued the reading to its base, "
   "so the words are in the English",
   "yomi" in (FIXTURE_NOTES[_ruby]["text"]) and "kanji" in FIXTURE_NOTES[_ruby]["text"])
ok("A22 has no committed fixture, and the reason is DECLARED rather than silent — "
   f"owed: {A22_FIXTURE_OWED}",
   not any(lbl == "fldsimple-ref" for lbl, _, _, _ in SHAPE_AT),
   "the shape is back in the fixture; if it is, the whole fixture stops repacking")
ok("and w:fldSimple is still in the inventory's DECLINED set, so a document carrying one "
   "gets the pinned duplication rather than a block",
   "fldSimple" in (_INV["uk/apply_translations_textmatch.py"].get(
       "_CONTAINER_DECLINED") or ()))

# =========================================================================================
# 4. THE POINTERS AND THE POSITION-CRITICAL CHILDREN INSIDE A CONTAINER.
#
#    A16's row is a content-loss row, so the fix must not close it by creating another one.
#    A footnote anchor works from anywhere in its paragraph and must survive the container
#    being emptied; a tab is position-critical and clause 2's limit governs it.
# =========================================================================================
print("\n4. WHAT WAS INSIDE THE CONTAINER BESIDES ITS TEXT")
_anchor_i = next(i for lbl, _, _, idxs in SHAPE_AT if lbl == "sdt-inline-anchor"
                 for i in idxs)
ok("the source's control really does hold a footnote anchor",
   len(SRC_PARAS[_anchor_i].findall(f".//{{{W}}}footnoteReference")) == 1)
ok("sdt-inline-anchor: the footnote anchor SURVIVES — a pointer is never dropped, wherever "
   "it sat",
   len(OUT_PARAS[_anchor_i].findall(f".//{{{W}}}footnoteReference")) == 1,
   f"{len(OUT_PARAS[_anchor_i].findall(f'.//{{{W}}}footnoteReference'))} anchor(s) survive")
_tab_i = next(i for lbl, _, _, idxs in SHAPE_AT if lbl == "sdt-inline-tab" for i in idxs)
ok("the source's control really does hold a tab character",
   len(SRC_PARAS[_tab_i].findall(f".//{{{W}}}tab")) >= 1)

# THE EMPTIED-WRAPPER DECISION, BOTH HALVES. Wouter, 2026-09-08: keep an emptied w:sdt
# because it renders and may be locked or data-bound; drop an emptied annotation, because a
# smart tag over text that no longer exists is provably redundant, which is clause 3's test.
#
# THE DROP HALF NEEDS ITS OWN SHAPE OR IT IS A LINE OF CODE NO TEST REACHES. Every other
# container row either keeps its text (so the wrapper is not empty) or is the paragraph's
# first text (so the wrapper receives the English). Only a container whose text sits LATER in
# the paragraph is genuinely emptied and abandoned.
print("\n4b. THE EMPTIED WRAPPER — kept for a control, dropped for an annotation")
_trail_i = next(i for lbl, _, _, idxs in SHAPE_AT if lbl == "smarttag-trailing"
                for i in idxs)
ok("the source really does hold a smart tag whose text is not the paragraph's first",
   len(SRC_PARAS[_trail_i].findall(f"{{{W}}}smartTag")) == 1
   and not source_first_text_in_container(_trail_i))
ok("smarttag-trailing: the emptied annotation wrapper is DROPPED",
   len(OUT_PARAS[_trail_i].findall(f"{{{W}}}smartTag")) == 0,
   f"{len(OUT_PARAS[_trail_i].findall(f'{{{W}}}smartTag'))} smart tag(s) survive empty")
_alone_i = next(i for lbl, _, _, idxs in SHAPE_AT if lbl == "sdt-inline-alone" for i in idxs)
ok("sdt-inline-alone: the content control is KEPT and now holds the English, so the control "
   "still governs its own content",
   len(OUT_PARAS[_alone_i].findall(f"{{{W}}}sdt")) == 1
   and any((t.text or "").strip() for t in
           OUT_PARAS[_alone_i].find(f"{{{W}}}sdt").iter(f"{{{W}}}t")),
   "the control was dropped, or it survived with no text in it")
_mixed_i = next(i for lbl, _, _, idxs in SHAPE_AT if lbl == "sdt-inline-mixed" for i in idxs)
ok("sdt-inline-mixed: the content control is KEPT even though it is now empty — it renders, "
   "and it may be locked or data-bound",
   len(OUT_PARAS[_mixed_i].findall(f"{{{W}}}sdt")) == 1,
   "the control was dropped, which is a structural edit to the client's document")

# =========================================================================================
# 5. THE CONTROLS DID NOT MOVE. A fix that reaches a paragraph it has no business in is a
#    regression this branch would otherwise ship, and the block-sdt rows are the corpus's
#    own positive control -- 5 of the sdt document's 10 take exactly that shape.
# =========================================================================================
print("\n5. THE CONTROLS — every one must be CLEAN and must keep its structure")
for lbl in ("sdt-block-para", "sdt-block-row", "hyperlink-mixed", "ins-mixed", "subdoc",
            "plain"):
    v, detail = VERDICTS[lbl]
    ok(f"control {lbl} is CLEAN", v == "CLEAN", f"measured {v}: {detail}")
_ins_i = next(i for lbl, _, _, idxs in SHAPE_AT if lbl == "ins-mixed" for i in idxs)
ok("ins-mixed keeps its w:ins wrapper with its author and date — the tracked-change fast "
   "path owns this family and an inventory must not double-handle it",
   len(OUT_PARAS[_ins_i].findall(f"{{{W}}}ins")) == 1
   and OUT_PARAS[_ins_i].find(f"{{{W}}}ins").get(f"{{{W}}}author") == "Reviewer")
_sub_i = next(i for lbl, _, _, idxs in SHAPE_AT if lbl == "subdoc" for i in idxs)
ok("subdoc keeps its w:subDoc — it carries no text, so a gate firing here would be firing "
   "on correct input",
   len(OUT_PARAS[_sub_i].findall(f"{{{W}}}subDoc")) == 1)

# =========================================================================================
# 6. A19 — apply must LEAVE THE GRAPHIC METADATA ALONE. Translating it is slice 3's, and the
#    surfaces are an attribute and a separate part, so apply touching either would be a
#    defect rather than progress.
# =========================================================================================
print("\n6. A19's SURFACES — apply must not touch them, in either direction")
_src_descr = [el.get("descr") for el in src_root.iter() if el.get("descr")]
_out_descr = [el.get("descr") for el in out_root.iter() if el.get("descr")]
ok("the alt text survives apply unchanged (slice 3 owns translating it)",
   _src_descr == _out_descr and len(_out_descr) == 1,
   f"source {len(_src_descr)}, delivered {len(_out_descr)}")
ok("the drawing itself survives",
   len(out_root.findall(f".//{{{W}}}drawing")) == len(src_root.findall(f".//{{{W}}}drawing")))

# =========================================================================================
# 7. THE LOUD REFUSAL. An unlisted container carrying text must stop the run rather than
#    ship silently -- option 1's rule in as many words.
#
#    AND THE NEGATIVE IS THE HALF THAT MATTERS, because section 5.7's test is whether a
#    compliant way out exists: the refusal must NOT fire on an unlisted element carrying no
#    text, nor on any of the ten non-run children of w:p the corpus actually contains.
# =========================================================================================
print("\n7. THE LOUD REFUSAL on a container nothing has listed")
NSDECL = ('xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'
          ' xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"'
          ' xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"'
          ' xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"')


def one_para_docx(path, inner):
    doc = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
           f'<w:document {NSDECL}><w:body><w:p>{inner}</w:p>'
           '<w:sectPr><w:pgSz w:w="11906" w:h="16838"/></w:sectPr></w:body></w:document>')
    ct = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
          '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
          '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.'
          'relationships+xml"/><Default Extension="xml" ContentType="application/xml"/>'
          '<Override PartName="/word/document.xml" ContentType="application/vnd.'
          'openxmlformats-officedocument.wordprocessingml.document.main+xml"/></Types>')
    rl = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
          '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/'
          'relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/'
          'officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>'
          '</Relationships>')
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        for n, d in (("[Content_Types].xml", ct), ("_rels/.rels", rl),
                     ("word/document.xml", doc)):
            zi = zipfile.ZipInfo(n, date_time=(1980, 1, 1, 0, 0, 0))
            zi.compress_type = zipfile.ZIP_DEFLATED
            zi.external_attr = 0o600 << 16
            zi.create_system = 0
            z.writestr(zi, d)


RUN = '<w:r><w:t xml:space="preserve">source words</w:t></w:r>'
CASES = [
    ("unlisted container HOLDING TEXT must REFUSE", True,
     '<w:r><w:t xml:space="preserve">A clause with </w:t></w:r>'
     '<w:futureThing>' + RUN + '</w:futureThing>'),
    ("unlisted element holding NO text must NOT refuse", False,
     '<w:r><w:t xml:space="preserve">A clause with a marker.</w:t></w:r>'
     '<w:futureThing/>'),
    ("unlisted element holding an EMPTY run must NOT refuse", False,
     '<w:r><w:t xml:space="preserve">A clause with an empty wrapper.</w:t></w:r>'
     '<w:futureThing><w:r/></w:futureThing>'),
]
for label, want_block, inner in CASES:
    wd = TMP / ("refuse-" + label.split()[0] + str(len(label)))
    wd.mkdir(parents=True, exist_ok=True)
    fx = wd / "neg.docx"
    one_para_docx(fx, inner)
    with zipfile.ZipFile(fx) as z:
        nsrc = z.read("word/document.xml")
    ntext = para_text(etree.fromstring(nsrc).find(f".//{{{W}}}p"))
    nnotes = [{"idx": 0, "text": ntext,
               "en": "A wholly rewritten provision in the target tongue.",
               "runs": [{"start": 0, "end": len(ntext), "text": ntext,
                         "bold": False, "italic": False}]}]
    data, res = run_apply(wd, nsrc, nnotes, label, fixture=fx, expect_block=True)
    blocked = data is None and res.returncode != 0
    fired = "SKILL GATE FIRED" in ((res.stderr or "") + (res.stdout or ""))
    if want_block:
        ok(label, blocked and fired,
           f"rc={res.returncode}, output written={data is not None}, gate text={fired}")
        if blocked and fired:
            msg = [ln for ln in ((res.stderr or "") + (res.stdout or "")).splitlines()
                   if "futureThing" in ln]
            ok("and the refusal NAMES the element it could not place",
               bool(msg), "the message does not name <w:futureThing>")
    else:
        ok(label, not blocked, f"rc={res.returncode} — the gate fired on correct input, "
                               f"which is a scope defect, not a stricter check")

# =========================================================================================
print("\n" + "=" * 106)
print(f"CHECKED: {CHECKED}    FAILURES: {len(FAIL)}    VOID: {len(VOIDED)}")
for f in FAIL:
    print(f"  FAIL  {f}")
for v in VOIDED:
    print(f"  VOID  {v}")
if not args.keep:
    shutil.rmtree(TMP, ignore_errors=True)
else:
    print(f"workdir kept: {TMP}")
print("=" * 106)
sys.exit(1 if (FAIL or VOIDED) else 0)
