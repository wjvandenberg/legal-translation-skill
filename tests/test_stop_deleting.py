# -*- coding: utf-8 -*-
"""BRANCH 6 — STOP DELETING WHAT YOU DO NOT RECOGNISE. The synthetic arm.

Option 1's first slice. Seven accountable rows from STEP-B-ANALYSIS.md section 9.3:
A1 A2 A3 A6 A8 A9 F27. C16, C17 and F16 are a declared follow-on slice (2026-09-01) --
they are boundary-whitespace and offset defects in three other functions, not deletions.

THE ACCEPTANCE CONDITION IS THE OPPOSITE OF THE LAST BRANCH'S, AND THAT IS THE POINT.
tests/test_no_delivered_byte_moves.py proves branch 14 moved no delivered byte. This branch
MUST move delivered bytes -- it is the first fix branch that changes a delivered document --
so the condition is not "nothing moved" but "everything that moved is explained by a register
row". This file is the synthetic half of that: it asserts the four structures the fixture
carries survive a rebuild. tools/apply_corpus_diff.py is the other half, over the thirteen
frozen intermediates, where the finding-by-finding explanation actually happens.

WHAT THIS FILE COVERS, AND WITH WHICH FIXTURE. Stated because a green suite that quietly
covers less than it appears to is this project's most frequent failure:

  A1 A2 A3 A8 F27   tests/fixtures/anchors-and-tabs.docx, sections 1 to 3.
  A9                tests/fixtures/cross-reference.docx, section 4. That fixture was BUILT
                    for this branch on 2026-09-01: no existing fixture carried a field
                    skeleton, and STEP-B-ANALYSIS.md section 3.7's own fixture list for
                    branch 6 does not name one either, so until now A9's only instrument was
                    the D06 frozen intermediate.

WHAT IT DOES NOT COVER:

  A6   glued bullets. The same destroyed tab as A3, evidenced on D05, not reproducible from
       either fixture. Real arm only.
  A3's RELOCATION, as opposed to A3's destruction. See section 2: apply rebuilds from one
       unbroken English string, so a tab that sat between two text atoms cannot be put back
       between them. Deferred to branch 16 and ASSERTED as the current outcome, so that
       branch must change this file deliberately rather than silently.

The four mechanisms, measured at HEAD on 2026-09-01 before any fix, all four reproducing:
footnoteReference 1->0, commentReference 1->0 (with both commentRange markers holding at
1->1, D02's signature), hyperlink 1->0, tab characters 2->0, tab STOPS 1->1.

    uv run --with lxml python tests/test_stop_deleting.py
    uv run --with lxml python tests/test_stop_deleting.py --variant us

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
# It is gitignored, invisible to a diff, and precommit_gate correctly fails on it. Register I-18.
os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")

sys.path.insert(0, str(Path(__file__).resolve().parent))
from docx_census import census, content_atoms, run_child_shapes, delta  # noqa: E402
from lxml import etree  # noqa: E402

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
ROOT = Path(__file__).resolve().parent.parent
FIX = ROOT / "tests" / "fixtures" / "anchors-and-tabs.docx"

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
    """A check that could not establish anything is VOID, never a pass. CLAUDE.md 5.16."""
    VOIDED.append(f"{label}: {why}")
    print(f"  ??   {label}   VOID — {why}")


def para_text(p):
    """EXACTLY apply's own get_paragraph_text: w:t only, plain w:br -> newline, then strip.

    IT INSERTS NO SPACE AT A TAB, so the party grid joins to 'Party AParty B'. Copied rather
    than approximated because matching depends on it: get it wrong and apply reports NOT
    FOUND, rebuilds nothing, and every assertion below passes for the wrong reason.
    """
    out = []
    for el in p.iter():
        tag = etree.QName(el).localname
        if tag == "t" and el.text:
            out.append(el.text)
        elif tag == "br" and el.get(f"{{{W}}}type", "") != "page":
            out.append("\n")
    return "".join(out).strip()


def run_apply(work, source_xml, notes, label, fixture=None):
    """Run apply on the fixture with the given notes. Returns the output XML bytes, or None."""
    work.mkdir(parents=True, exist_ok=True)
    orig = work / "orig.docx"
    shutil.copyfile(fixture or FIX, orig)
    pj = work / "paragraphs.json"
    pj.write_text(json.dumps(notes, ensure_ascii=False), encoding="utf-8")
    out = work / "out.xml"
    env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1",
               PYTHONDONTWRITEBYTECODE="1")
    r = subprocess.run(
        ["uv", "run", "--with", "lxml", "python",
         str(ROOT / args.variant / "scripts" / "apply_translations_textmatch.py"),
         str(orig), str(pj), str(out)],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        cwd=str(ROOT), env=env, timeout=600)
    # ASSERT THE ARTEFACT, NOT THE EXIT CODE. A run that skipped every paragraph, matched
    # nothing or died after printing its summary all exit 0. CLAUDE.md 5.16.
    if not out.exists():
        print(f"\n  {label}: apply wrote no output (rc={r.returncode}).")
        print("  " + (r.stderr or r.stdout or "").strip()[-1200:])
        return None, r
    data = out.read_bytes()
    if data == source_xml:
        print(f"\n  {label}: output is byte-identical to input, so apply rebuilt NOTHING.")
        print("  Every assertion below would pass vacuously. This is VOID, not clean.")
        return None, r
    if "Total changes applied: 0" in (r.stdout or ""):
        print(f"\n  {label}: apply reported 0 changes.")
        return None, r
    return data, r


TMP = Path(tempfile.mkdtemp(prefix="b6-stopdel-"))
with zipfile.ZipFile(FIX) as z:
    SRC = z.read("word/document.xml")
src_root = etree.fromstring(SRC)
SRC_PARAS = list(src_root.iter(f"{{{W}}}p"))

print("=" * 98)
print(f"BRANCH 6 — STOP DELETING · synthetic arm · {args.variant}/scripts/"
      "apply_translations_textmatch.py")
print("=" * 98)

# =========================================================================================
# 0. THE POSITIVE CONTROL. Plant nothing, but PROVE the fixture carries each needle: an
#    assertion that a count went 0 -> 0 is the clean-looking zero CLAUDE.md 5.16 rule 6 is
#    about, and it is indistinguishable from a real pass.
# =========================================================================================
print("\n0. THE FIXTURE ACTUALLY CARRIES THE NEEDLES  (else every assertion below is VOID)")
print("-" * 98)
b = census(SRC)
NEEDLES = {"footnoteReference": "A1", "commentReference": "A2",
           "hyperlink": "A8", "tab_chars": "A3"}
controls_ok = True
for tag, row in NEEDLES.items():
    if not ok(f"fixture carries {tag} (row {row}): {b[tag]}", b[tag] > 0,
              "count is 0 — this fixture cannot test that row"):
        controls_ok = False
ok(f"fixture carries a tab STOP as the negative control: {b['tab_stops']}",
   b["tab_stops"] > 0, "no tab stop — the stops-are-not-chars rule is untested")
ok("this fixture carries no fldChar, so A9 is section 4's on its own fixture",
   b["fldChar"] == 0,
   "a field skeleton has appeared here — A9's assertions live in section 4 and would now "
   "be measuring two fixtures at once")

# =========================================================================================
# 1. THE PLAIN REBUILD — nothing authored, so every tab in the output came from the source.
# =========================================================================================
print("\n1. PLAIN REBUILD — the four structures must survive, and stay where they were")
print("-" * 98)
plain_notes = [{"idx": i, "text": para_text(p),
                "en": (para_text(p) + " EN") if para_text(p) else para_text(p),
                "style": "Normal"}
               for i, p in enumerate(SRC_PARAS)]
A, ra = run_apply(TMP / "plain", SRC, plain_notes, "plain rebuild")
if A is None:
    print("\nVOID — the plain rebuild produced nothing comparable.")
    if not args.keep:
        shutil.rmtree(TMP, ignore_errors=True)
    sys.exit(1)
a = census(A)

ok(f"A1  w:footnoteReference survives  {b['footnoteReference']} -> {a['footnoteReference']}",
   a["footnoteReference"] == b["footnoteReference"],
   "the anchor is gone: the footnote text is in the package and on no page")
ok(f"A2  w:commentReference survives   {b['commentReference']} -> {a['commentReference']}",
   a["commentReference"] == b["commentReference"],
   "the anchor is gone: the comment body is in comments.xml and unreachable")
ok(f"A2  w:commentRangeStart/End hold  {b['commentRangeStart']}/{b['commentRangeEnd']} -> "
   f"{a['commentRangeStart']}/{a['commentRangeEnd']}   (the control: these already survive)",
   a["commentRangeStart"] == b["commentRangeStart"]
   and a["commentRangeEnd"] == b["commentRangeEnd"])
ok(f"A8  w:hyperlink survives          {b['hyperlink']} -> {a['hyperlink']}",
   a["hyperlink"] == b["hyperlink"],
   "the wrapper was deleted whole, taking the tab-only run inside it")
# A3 IS NOW A SPLIT VERDICT, AND WOUTER'S RENDER REVIEW IS WHY. A tab whose true position
# survives the collapse is KEPT; one that sat between text is DROPPED, because emitting it at
# the paragraph end glued D06's page numbers exactly as before AND forced a line wrap. A
# misplaced tab is worse than a missing one, measured on the page.
#
# THE COUNT IS DERIVED FROM THE FIXTURE, NOT TYPED: a tab is placeable when it precedes all
# the text in its container or follows all of it.
placeable = 0
for p in SRC_PARAS:
    at = content_atoms(p)
    if "tab" not in at:
        continue
    first_t = at.index("text") if "text" in at else None
    last_t = len(at) - 1 - at[::-1].index("text") if "text" in at else None
    for j, k in enumerate(at):
        if k != "tab":
            continue
        if first_t is None or j < first_t or j > last_t:
            placeable += 1
ok(f"A3  only PLACEABLE tabs survive   {b['tab_chars']} -> {a['tab_chars']}   "
   f"(the fixture has {placeable} placeable of {b['tab_chars']})",
   a["tab_chars"] == placeable,
   "a tab that precedes all the text, or follows all of it, has a knowable position and "
   "must be kept; one between text has none and must be dropped")
ok(f"A3  and at least one tab IS kept  ({a['tab_chars']})", a["tab_chars"] > 0,
   "if every tab is dropped, this suite would pass against code that deleted them all — "
   "which is the defect the branch started from")
ok(f"A3  tab STOPS untouched           {b['tab_stops']} -> {a['tab_stops']}   "
   "(negative control: a stop is not a character)",
   a["tab_stops"] == b["tab_stops"],
   "a fix that moves tab stops is doing something it was not asked to do")
# TRAILING TABS MAY RISE, BUT ONLY BY AN AMOUNT THAT IS EXPLAINED. A paragraph whose source
# holds a tab BETWEEN two text fragments must gain one: the fragments collapse into a single
# English string, so the tab lands after it (Wouter's decision, 2026-09-01). Any rise beyond
# that count is the A3/D01 orphan shape -- tabs preserved at the paragraph end while the
# English is re-inserted in front of them, which on that document took tab characters 18 -> 24
# with the layout still looking right. The first draft of this assertion demanded no rise at
# all, which contradicted the agreed design and failed on the one paragraph built to exercise
# it: an instrument asserting something nobody promised. CLAUDE.md 5.1 -- fix the instrument.
mid_tab = 0
for p in SRC_PARAS:
    at = content_atoms(p)
    if "tab" in at and "text" in at[at.index("tab"):]:
        mid_tab += 1
ok(f"    trailing-tab rise is EXPLAINED   {b['trailing_tabs']} -> {a['trailing_tabs']}   "
   f"(at most +{mid_tab}: the paragraph(s) whose tab sat between two text fragments)",
   a["trailing_tabs"] - b["trailing_tabs"] <= mid_tab,
   "more trailing tabs than the collapse can account for — that is the D01 orphan shape")

# =========================================================================================
# 2. POSITION, NOT JUST SURVIVAL. Counts cannot tell "between the two names" from "at the
#    end of the paragraph", and that distinction IS finding A3.
# =========================================================================================
print("\n2. POSITION — the preserved child came back WHERE IT WAS, not merely came back")
print("-" * 98)
out_root = etree.fromstring(A)
OUT_PARAS = list(out_root.iter(f"{{{W}}}p"))
ok(f"paragraph count unchanged  {len(SRC_PARAS)} -> {len(OUT_PARAS)}",
   len(SRC_PARAS) == len(OUT_PARAS))

# The mixed run: source atoms are [text, tab, text]. Wouter's decision, 2026-09-01: a tab
# keeps its position among the run's parts, and an authored tab wins where there is one.
# With one unbroken English string the two source text atoms collapse into one, so the tab
# must still sit BETWEEN text and not be last -- that is what closes the hanging-indent case.
mixed = [i for i, p in enumerate(SRC_PARAS) if content_atoms(p) == ["text", "tab", "text"]]
if not mixed:
    void("A3/A-ii position", "no [text, tab, text] paragraph in the fixture")
else:
    i = mixed[0]
    src_atoms = content_atoms(SRC_PARAS[i])
    out_atoms = content_atoms(OUT_PARAS[i])
    # A TAB BETWEEN TWO TEXT ATOMS IS DROPPED, AND THAT IS THE CORRECTED RULE. The English is
    # one unbroken string, so where inside it the tab belonged is not knowable. The first
    # version emitted it at the paragraph end and called that "strictly better than deletion";
    # Wouter's render review falsified exactly that phrase — on D06 it left the page numbers
    # glued AND added a forced line wrap. Dropping restores the old, harmless outcome.
    ok(f"A-ii the between-text tab is DROPPED, not stranded   {src_atoms} -> {out_atoms}",
       out_atoms == ["text"],
       "expected ['text']: emitting it at the end glues the page number and forces a wrap")

# =========================================================================================
# D05's SHAPE — AND WHAT IT PROVES THE POSITION CLAUSE CANNOT DO. Measured 2026-09-01.
#
# STEP-B-ANALYSIS.md section 6, Option 1 says branch 6 "closes the case where the tab dies
# inside a text-bearing run, and the RELOCATION case needs the position clause, which is why
# the clause is in the proposal." Built, it does not follow, and the reason is structural
# rather than a coding slip.
#
# D05's source is a marker run '(a)' FOLLOWED BY a run whose children are [rPr, tab, t]. The
# tab therefore sits BETWEEN two text atoms that live in DIFFERENT runs. Apply rebuilds a
# paragraph from ONE unbroken English string, so both text atoms collapse into one block and
# a single block can go before the tab or after it -- never around it. There is no offset in
# `en` that says "the tab belonged here", because `en` has no per-run structure at all.
#
# THAT IS CLUSTER A's OTHER HALF, NOT A BUG IN THIS BRANCH: the apply-side deletion problem
# is fixable here, and the DATA CONTRACT being unable to describe the formatting is branches
# 15-17's (CLAUDE.md 2.5 item 7 -- "two fixes, two files, and neither closes the other's
# rows"). Branch 15 makes extraction emit effective formatting per RUN; only then can the
# English be split at the boundary the tab sat on.
#
# SO WHAT BRANCH 6 DELIVERS ON A3 IS: the tab is no longer DESTROYED -- count restored, and
# correctly placed within a single run's own children. Its position between text atoms in a
# MULTI-RUN paragraph is deferred, declared, and asserted below so that branch 16 must change
# this line deliberately rather than silently.
# =========================================================================================
d05 = [i for i, p in enumerate(SRC_PARAS)
       if p.find(f"{{{W}}}pPr/{{{W}}}ind") is not None
       and "tab" in content_atoms(p)]
if not d05:
    void("A3 hanging-indent shape (D05)",
         "no hanging-indent paragraph carrying a tab in the fixture")
else:
    i = d05[0]
    src_a, out_a = content_atoms(SRC_PARAS[i]), content_atoms(OUT_PARAS[i])
    ok(f"A3  the hanging-indent tab is DEFERRED to branch 16   {src_a} -> {out_a}",
       out_a == ["text"],
       "the outcome changed — if branch 15/16 now supplies per-run English, update this "
       "assertion deliberately; if not, something else moved")

# AND THE OTHER HALF OF THE RULE, WITHOUT WHICH THE ONE ABOVE IS UNFALSIFIABLE. A tab that
# precedes ALL the text in its paragraph HAS a knowable position and must come back in front
# of the rebuilt English. If this fails while the drops above pass, the code is not applying a
# rule — it is deleting every tab, which is the defect the branch began with.
lead = [i for i, p in enumerate(SRC_PARAS) if content_atoms(p) == ["tab", "text"]]
if not lead:
    void("A3 placeable tab (leading)",
         "no [tab, text] paragraph in the fixture — the KEEP half is untested")
else:
    i = lead[0]
    out_a = content_atoms(OUT_PARAS[i])
    ok(f"A3  a tab that precedes all the text IS KEPT, and stays in front   "
       f"{content_atoms(SRC_PARAS[i])} -> {out_a}",
       out_a == ["tab", "text"],
       "expected ['tab', 'text'] — this position is recoverable and must survive")

# The hyperlink: its only child run is tab-only. Rebuilding must happen INSIDE it.
hl = [i for i, p in enumerate(SRC_PARAS) if p.find(f"{{{W}}}hyperlink") is not None]
if not hl:
    void("A8 position", "no hyperlink-bearing paragraph in the fixture")
else:
    i = hl[0]
    out_hl = OUT_PARAS[i].find(f"{{{W}}}hyperlink")
    ok("A8  the hyperlink is still a child of its paragraph", out_hl is not None,
       "deleted whole rather than rebuilt inside")
    if out_hl is not None:
        inner = [etree.QName(el).localname for el in out_hl.iter()
                 if etree.QName(el).localname in ("tab", "t", "r")]
        ok(f"A8  the tab-only run inside it survives   {inner}", "tab" in inner,
           "the wrapper came back empty, which no renderer will show as a tab")

# =========================================================================================
# 3. F27 — AN AUTHORED BOUNDARY TAB. Separate apply, so this cannot mask section 1's counts.
# =========================================================================================
print("\n3. F27 — a leading and a trailing tab the operator AUTHORED must reach the document")
print("-" * 98)
# BOTH OF F27's DOCUMENTS, because they are two different characters. D01 is a leading TAB;
# D10 is a leading and a trailing NEWLINE. One `.strip()` destroyed both, and testing only the
# tab would leave half the row unproved.
plain = [i for i, p in enumerate(SRC_PARAS)
         if para_text(p) and content_atoms(p) == ["text"]]
if len(plain) < 2:
    void("F27", f"need two text-only paragraphs to author into, found {len(plain)}")
else:
    tab_at, br_at = plain[0], plain[1]
    f27_notes = []
    for i, p in enumerate(SRC_PARAS):
        t = para_text(p)
        en = (t + " EN") if t else t
        if i == tab_at:
            en = "\t" + t + " EN\t"          # D01's shape: leading and trailing tab
        elif i == br_at:
            en = "\n" + t + " EN\n"          # D10's shape: leading and trailing newline
        f27_notes.append({"idx": i, "text": t, "en": en, "style": "Normal"})
    B2, rb = run_apply(TMP / "f27", SRC, f27_notes, "F27 rebuild")
    if B2 is None:
        void("F27", "the authored-separator rebuild produced nothing comparable")
    else:
        c2 = census(B2)
        # Baseline is the PLAIN REBUILD's surviving count, not the source's: the placement
        # rule drops the unplaceable source tabs either way, and F27 is about the two the
        # OPERATOR authored. Measuring against the source would conflate the two rows.
        ok(f"F27 authored boundary TABS reach the XML   tab chars "
           f"{a['tab_chars']} -> {c2['tab_chars']} (expect {a['tab_chars'] + 2})",
           c2["tab_chars"] == a["tab_chars"] + 2,
           "en.strip() runs unconditionally BEFORE the \\t -> <w:tab/> conversion, so a "
           "boundary tab is destroyed while an interior one works")
        ok(f"F27 authored boundary NEWLINES reach the XML   plain w:br "
           f"{b['br_plain']} -> {c2['br_plain']} (expect {b['br_plain'] + 2})",
           c2["br_plain"] == b["br_plain"] + 2,
           "D10's half of the row: a trailing newline on one party block and a leading "
           "newline on another, both destroyed by the same one line")
        ok(f"F27 tab STOPS still untouched   {b['tab_stops']} -> {c2['tab_stops']}",
           c2["tab_stops"] == b["tab_stops"])
        # THE NEGATIVE INPUT, which section 4 makes mandatory rather than optional: ordinary
        # leading and trailing SPACES must still be stripped. A fix that simply stopped
        # stripping would pass both assertions above and be wrong -- so prove the thing the
        # strip is FOR still happens.
        sp_notes = [{"idx": i, "text": para_text(p),
                     "en": ("   " + para_text(p) + " EN   ") if para_text(p) else "",
                     "style": "Normal"}
                    for i, p in enumerate(SRC_PARAS)]
        C3, _ = run_apply(TMP / "f27-spaces", SRC, sp_notes, "F27 negative input")
        if C3 is None:
            void("F27 negative input", "the spaces-only rebuild produced nothing comparable")
        else:
            root3 = etree.fromstring(C3)
            bad = [t.text for t in root3.iter(f"{{{W}}}t")
                   if t.text and (t.text.startswith("   ") or t.text.endswith("   "))]
            ok(f"F27 NEGATIVE INPUT: ordinary boundary spaces are still stripped "
               f"({len(bad)} run(s) kept them)", not bad,
               "the fix stopped stripping altogether instead of becoming separator-aware")

# =========================================================================================
# 4. A9 — CLAUSE 3, THE ONLY DELETION. A separate fixture, because a REF field skeleton is a
#    shape no other fixture carries and STEP-B section 3.7's own list for branch 6 omits it.
# =========================================================================================
print("\n4. A9 — a consumed cross-reference skeleton must GO; an unevaluated one must STAY")
print("-" * 98)
XREF = ROOT / "tests" / "fixtures" / "cross-reference.docx"
if not XREF.is_file():
    void("A9", f"{XREF.name} not built — run tests/make_fixtures.py")
else:
    with zipfile.ZipFile(XREF) as z:
        XSRC = z.read("word/document.xml")
    xb = census(XSRC)
    # POSITIVE CONTROL FIRST: 5 fldChar (consumed begin/separate/end + unevaluated
    # begin/end) and 2 instrText. If the fixture does not carry them, everything below is VOID.
    # THREE FIELDS: a REF with a cached result (must go), a PAGE with none (must stay), and a
    # PAGE WITH one (must stay — the keyword decides, not the presence of a result).
    # 3 + 2 + 3 = 8 fldChar, 3 instrText.
    ctl = ok(f"fixture carries three field skeletons: fldChar {xb['fldChar']}, "
             f"instrText {xb['instrText']}",
             xb["fldChar"] == 8 and xb["instrText"] == 3,
             "expected 8 fldChar and 3 instrText — one deletable and two that must survive")
    xroot = etree.fromstring(XSRC)
    XPARAS = list(xroot.iter(f"{{{W}}}p"))
    xnotes = [{"idx": i, "text": para_text(p),
               "en": (para_text(p) + " EN") if para_text(p) else para_text(p),
               "style": "Normal"}
              for i, p in enumerate(XPARAS)]
    X, rx = run_apply(TMP / "xref", XSRC, xnotes, "cross-reference rebuild", fixture=XREF)
    if X is None or not ctl:
        void("A9", "the cross-reference rebuild produced nothing comparable"
             if X is None else "positive control failed")
    else:
        xa = census(X)
        # Only the REF field goes: it loses begin + separate + end and its instruction, so
        # 8 -> 5 fldChar and 3 -> 2 instrText. Both PAGE fields stay whole.
        ok(f"A9  ONLY the consumed REF skeleton is dropped   fldChar {xb['fldChar']} -> "
           f"{xa['fldChar']} (expect 5), instrText {xb['instrText']} -> {xa['instrText']} "
           f"(expect 2)",
           xa["fldChar"] == 5 and xa["instrText"] == 2,
           "left standing, Word re-evaluates the empty skeleton on open and prints the "
           "cross-reference a SECOND time — 42 paragraphs on D06, six of them also "
           "resurrecting 'Error: Reference source not found'. Deleting MORE than the REF "
           "field would freeze a PAGE field at its cached value.")
        # THE TWO NEGATIVES, and they are what stop clause 3 becoming "delete every field".
        xout = etree.fromstring(X)
        instr = [(t.text or "").strip() for t in xout.iter(f"{{{W}}}instrText")]
        ok(f"A9  NEGATIVE 1+2: both PAGE fields survive, no REF remains   instrText {instr}",
           instr.count("PAGE") == 2 and not any("REF" in s for s in instr),
           "the keyword decides, not the presence of a cached result: a PAGE field frozen "
           "at its cached value prints the same page number on every page, and a fix that "
           "deletes both looks identical to the correct one on the corpus, where every "
           "cached-result field happens to be a REF")

# =========================================================================================
# 5. A3, THE TABLE-OF-CONTENTS HALF — PLACEMENT, not survival. Everything above asks whether a
#    structure came BACK; this asks whether it came back IN THE RIGHT PLACE, which is a
#    different question and the one Wouter's render review forced. A misplaced tab is worse
#    than a missing one: on D06 both tabs returned at the paragraph END, so the page number
#    stayed glued to the title exactly as before AND the trailing tabs forced a line wrap.
#
#    THE ASSERTION IS THE SOURCE'S OWN ATOM SEQUENCE, NOT A COUNT. D02 lost 45 tabs and not
#    one pixel moved on any of its 11 pages, so `tab_chars` cannot decide this.
# =========================================================================================
print("\n5. A3/TOC — a table-of-contents entry's two tabs go back where the SOURCE had them")
print("-" * 98)
TOC = ROOT / "tests" / "fixtures" / "toc.docx"
TOCN = TOC.with_suffix(".notes.json")


def atom_split(p):
    """(pre, post) — the w:t text before the first tab atom and after the last, or None if
    the paragraph is not TOC-shaped. The same reading the rule itself makes, so a delivered
    paragraph can be compared against its source on the one thing that matters: WHERE."""
    at = []
    for el in p.iter():
        tag = etree.QName(el).localname
        if tag in ("t", "delText"):
            if el.text:
                at.append(("text", el.text))
        elif tag == "tab":
            parent = el.getparent()
            if parent is None or etree.QName(parent).localname != "tabs":
                at.append(("tab", ""))
        elif tag == "br":
            at.append(("br", ""))
    if [k for k, _ in at] != ["text", "tab", "text", "tab", "text"]:
        return None
    return at[0][1], at[4][1]


if not TOC.is_file() or not TOCN.is_file():
    void("A3/TOC", f"{TOC.name} or {TOCN.name} not built — run tests/make_fixtures.py")
else:
    with zipfile.ZipFile(TOC) as z:
        TSRC = z.read("word/document.xml")
    tb = census(TSRC)
    TPARAS = list(etree.fromstring(TSRC).iter(f"{{{W}}}p"))
    tnotes = json.loads(TOCN.read_text(encoding="utf-8"))
    shaped = [i for i, p in enumerate(TPARAS) if atom_split(p) is not None]
    # POSITIVE CONTROL. Six TOC-shaped paragraphs, twelve tab characters, twelve tab STOPS as
    # the negative control, six hyperlinks, and notes that describe THIS document. Any of
    # these wrong and every assertion below is VOID however it reads.
    tctl = ok(f"fixture carries the TOC shape: {len(shaped)} shaped paragraph(s), "
              f"tab_chars {tb['tab_chars']}, tab_stops {tb['tab_stops']}, "
              f"hyperlink {tb['hyperlink']}",
              len(shaped) == 6 and tb["tab_chars"] == 12 and tb["tab_stops"] == 12
              and tb["hyperlink"] == 6,
              "expected 6 shaped, 12 tab chars, 12 stops, 6 hyperlinks")
    tctl = ok(f"the shipped notes describe THIS document: {len(tnotes)} note(s) "
              f"for {len(TPARAS)} paragraph(s)",
              len(tnotes) == len(TPARAS)
              and all(n["text"] == para_text(TPARAS[n["idx"]]) for n in tnotes),
              "a notes file that does not match the fixture tests a different document") \
        and tctl
    T, rt = run_apply(TMP / "toc", TSRC, tnotes, "table-of-contents rebuild", fixture=TOC)
    if T is None or not tctl:
        void("A3/TOC", "the rebuild produced nothing comparable" if T is None
             else "positive control failed")
    else:
        ta = census(T)
        TOUT = list(etree.fromstring(T).iter(f"{{{W}}}p"))
        # WHICH ENTRIES MUST BE PLACED AND WHICH MUST DECLINE — from make_fixtures' own
        # construction, stated here so the truth table is visible rather than implied.
        PLACE, DECLINE, PROSE = (1, 2, 3, 4), (5, 6), 0
        placed_right = []
        for i in PLACE:
            src, out = atom_split(TPARAS[i]), atom_split(TOUT[i])
            # BOTH boundaries, against the SOURCE's own text. `out is not None` alone would
            # accept two tabs in the wrong places, which is the exact defect being fixed.
            placed_right.append(out is not None and src is not None
                                and out[0] == src[0] and out[1] == src[1])
        ok(f"A3/TOC  all four placeable entries deliver the SOURCE's atom sequence, with the "
           f"number before the first tab and the page number after the last   "
           f"{sum(placed_right)}/4",
           all(placed_right),
           "an entry whose atoms are ['text'] delivered `1General provisions4` — flat, no "
           "dot leader, no right-aligned page number. An entry with the tabs in the WRONG "
           "places is worse: it glues the page number exactly as before AND forces a wrap")
        # THE ENTRY THIS FIXTURE EXISTS FOR. Its first RUN carries text on both sides of the
        # tab, so extraction's runs[0] spans the tab. A rule taking its offset from that
        # fragment places tab 1 AFTER the title while every count and the atom sequence still
        # look right — so this is asserted on the TEXT, separately from the three above.
        inline = atom_split(TOUT[4])
        ok(f"A3/TOC  the inline-tab entry places on the SOURCE's tab position, not on the "
           f"run boundary   pre={inline[0]!r}" if inline else
           "A3/TOC  the inline-tab entry places on the SOURCE's tab position",
           inline is not None and inline[0] == atom_split(TPARAS[4])[0],
           "its runs[0] is number+title, so an offset of len(runs[0]) puts the first tab "
           "after the TITLE — same atom sequence, same tab count, wrong page")
        # THE NEGATIVES. A rule that fires on everything passes every assertion above.
        declined = [content_atoms(TOUT[i]) == ["text"] for i in DECLINE]
        ok(f"A3/TOC  NEGATIVE 1: the two unprovable entries FALL BACK to dropping   "
           f"{sum(declined)}/2",
           all(declined),
           "one has different page digits in `en`, one has a translated number — neither "
           "boundary is proved, so placing a tab would be a guess. Dropping leaves the page "
           "no worse than before, which is the whole fallback")
        ok(f"A3/TOC  NEGATIVE 2: the heading is not TOC-shaped and gains nothing   "
           f"{content_atoms(TOUT[PROSE])}",
           content_atoms(TOUT[PROSE]) == ["text"],
           "ordinary prose must never acquire a tab")
        ok(f"A3/TOC  tab STOPS untouched (the negative control)   {tb['tab_stops']} -> "
           f"{ta['tab_stops']}",
           ta["tab_stops"] == tb["tab_stops"],
           "a w:tab inside pPr/tabs is a ruler position, not a rendered tab; touching one "
           "would move the whole column")
        ok(f"A3/TOC  tab characters rise toward source, by exactly the placed entries   "
           f"{tb['tab_chars']} -> {ta['tab_chars']} (expect 8 of the source's 12)",
           ta["tab_chars"] == 8,
           "8 = four placed entries times two. NOT 12: the two declined entries drop theirs "
           "on purpose, so this row is PARTIAL by design and the atom assertions above are "
           "what decide it")
        ok(f"A3/TOC  A8 not regressed: every hyperlink survives and still covers text   "
           f"hyperlink {tb['hyperlink']} -> {ta['hyperlink']}",
           ta["hyperlink"] == tb["hyperlink"]
           and all(any((t.text or "").strip() for t in h.iter(f"{{{W}}}t"))
                   for h in etree.fromstring(T).iter(f"{{{W}}}hyperlink")),
           "an empty hyperlink beside the words it should cover is not a navigable entry")

# =========================================================================================
print()
print("=" * 98)
if VOIDED:
    print(f"{len(VOIDED)} check(s) VOID — established nothing, and a VOID is not a pass:")
    for v in VOIDED:
        print(f"  ?  {v}")
if not controls_ok:
    print("POSITIVE CONTROL FAILED — the fixture does not carry what this suite tests.")
    print("Every result above is VOID regardless of how it reads.")
    if not args.keep:
        shutil.rmtree(TMP, ignore_errors=True)
    sys.exit(1)
if args.keep:
    print(f"workdir kept: {TMP}")
else:
    shutil.rmtree(TMP, ignore_errors=True)
if FAIL:
    print(f"FAIL — {len(FAIL)} of {CHECKED} assertions:")
    for f in FAIL:
        print(f"  ·  {f}")
    print("=" * 98)
    sys.exit(1)
print(f"PASS — {CHECKED} assertions. Every structure the fixture carries survived the")
print("rebuild, in position, and the tab-stop control did not move.")
print("=" * 98)
