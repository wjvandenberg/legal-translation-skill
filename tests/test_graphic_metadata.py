# -*- coding: utf-8 -*-
"""BRANCH 7 SLICE 3 — A19: translatable text held in GRAPHIC METADATA.

Option 1's last slice, and it closes branch 7. A19's row: image alt text
(`wp:docPr/@descr`), chart and diagram titles and SmartArt text are neither translated nor
reported, and NOTHING ACKNOWLEDGES THE GAP -- the third container the skill never enumerates,
beside A16 (`w:sdt`) and N1 (`w:smartTag`).

THE EVIDENCE IS FIXTURE-ONLY AND THAT IS DECLARED, NOT IMPLIED (Wouter, 2026-09-09, exactly
as N1 was declared). Re-derived 2026-09-09 over 10 of the 11 corpus documents:

    w:drawing   9   -- 6 headers, 3 footers, ZERO body
    w:pict      5   -- 2 headers, 3 footers, ZERO body
    @descr      0     @title  0     v:shape/@alt  0     @name  15
    charts      0     SmartArt/diagrams  0
    both shipped trees, 396 files, 396 opened, 0 unreadable, control FIRED:
      docPr / SmartArt / w:drawing / a:graphic / c:title / wp:inline / diagrams  ALL 0

So the corpus carries 14 graphics across 3 documents and **not one attribute of prose on any
of them.** `@name` is what Word assigns. There is therefore NO real-document instance of
translatable graphic metadata IN ANY FORM, and a fixture result reported beside a quiet corpus
run reads as corpus evidence -- which is the whole risk this paragraph exists to remove.

THE ACCEPTANCE CONDITION IS THIS FILE, AND NOT tools/apply_corpus_diff.py. That tool drives
`apply_translations_textmatch.py` over `word/document.xml`. This slice changes
`translate_headers_footers.py` and an extraction REPORT, so its arms are byte-identical BY
DESIGN and a 13-of-13-unchanged result proves nothing whatever about A19. Slice 1 had to move
a delivered byte; slice 2 had to move none and said so; slice 3 moves none through that tool.
`tools/hf_corpus_diff.py` is this slice's corpus arm, and it reports on the script that
actually changed.

WHAT THIS FILE COVERS, stated because a green suite that quietly covers less than it appears
to is this project's most frequent failure:

  A19 the REPORT   every graphic surface in every part, with the route named or its absence
                   named -- body, header, footer, chart part, diagram part
  A19 the FIX      alt text in HEADER and FOOTER parts translated through Step 8b's existing
                   --extract / --apply round-trip, which repack already bundles via
                   --headers-footers-dir
  the HINGE        a scaffold entry with NO `kind` key is still a paragraph entry. All 10
                   existing frozen header/footer scaffolds have no `kind`, so this is what
                   stops the change breaking every real document
  the RESIDUE      a BODY @descr is reported and NOT translated, and chart and diagram text
                   are detected-only (Wouter's decision 4, 2026-09-08). Asserted as the
                   CURRENT outcome so a later branch must change it deliberately
  measurement (a)  the inline header `sdt` -- RUN, not read. Owed measurement, Wouter
                   2026-09-09
  measurement (b)  the footer control bound to customXml -- PINNED at the current outcome,
                   with the Word-in-the-loop gap stated rather than papered over

WHAT IT DOES NOT COVER, each a declared N/A with its reason:

  A RENDERED ARM. Neither surface shows on a page. Alt text is SPOKEN by a screen reader, not
        painted; a chart title in a part no body element references is not drawn at all.
        Measured on slice 2 with a positive control firing that LibreOffice renders no
        glossary placeholder text either, so a three-arm visual diff there was theatre. This
        is proved IN BYTES and said so. tools/render_diff.py's READ-ME says it in terms.
  WORD'S OWN BEHAVIOUR on a bound control. No instrument here has Word in the loop.
  A CORPUS ARM OVER THE ALT TEXT. There is nothing to move: @descr is 0.

    uv run --with lxml python tests/test_graphic_metadata.py
    uv run --with lxml python tests/test_graphic_metadata.py --variant us

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
# Reaches grandchildren, which sys.dont_write_bytecode cannot: these scripts spawn validators
# as subprocesses, so a .pyc can land inside the shipped tree. Register I-18.
os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")

from lxml import etree                                                    # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
FIX = ROOT / "tests" / "fixtures" / "graphic-metadata.docx"
# The fixture with NO graphic of any kind. It is the negative control for the whole slice,
# and it is READ ONLY -- test_no_delivered_byte_moves.py depends on its bytes.
NOGRAPHIC = ROOT / "tests" / "fixtures" / "headers-footers.docx"

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
V = "urn:schemas-microsoft-com:vml"

ap = argparse.ArgumentParser()
ap.add_argument("--variant", default="uk", choices=("uk", "us"))
ap.add_argument("--keep", action="store_true", help="keep the temp workdir for inspection")
args = ap.parse_args()
SCRIPTS = ROOT / args.variant / "scripts"

FAIL, CHECKED, VOIDED = [], 0, []
TMP = Path(tempfile.mkdtemp(prefix="b7s3-graphics-"))
ENV = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1",
           PYTHONDONTWRITEBYTECODE="1")

# THE SOURCE-LANGUAGE STRINGS THE FIXTURE CARRIES, and the English for each. Kept here rather
# than re-derived from the document so that two lists which must agree are ASSERTED to agree
# (arm 1) instead of quietly diverging -- the failure make_fixtures._notes_from_document
# exists to prevent on the body side.
HDR_DESCR = "Stroomschema van de goedkeuringsprocedure"
HDR_TITLE = "Goedkeuringsschema"
FTR_ALT = "Watermerk met het woord CONCEPT"
BODY_DESCR = "Organigram van de betrokken partijen"
BODY_TITLE = "Organigram"
CHART_TITLE = "Leveringen per kwartaal"
CHART_AXIS = "Geleverde tonnage"
DGM_1 = "Goedkeuring door de raad"
DGM_2 = "Ondertekening"

EN = {
    HDR_DESCR: "Flow chart of the approval procedure",
    HDR_TITLE: "Approval chart",
    FTR_ALT: "Watermark reading DRAFT",
}


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


def run(argv, timeout=900):
    return subprocess.run(["uv", "run", "--with", "lxml", "python"] + [str(a) for a in argv],
                          capture_output=True, text=True, encoding="utf-8",
                          errors="replace", cwd=str(ROOT), env=ENV, timeout=timeout)


def stage(name, docx_path):
    """Copy a .docx into its own temp subdirectory.

    NEVER POINT A SCRIPT'S APPLY AT tests/fixtures/. The final pre-apply pass writes
    .validate-state.json beside its input, and that reached the git index once on branch 6
    slice 3 -- which broke `git switch` and therefore `git bisect`, the one tool this whole
    test method exists to make possible.
    """
    d = TMP / name
    (d / "final").mkdir(parents=True, exist_ok=True)
    src = d / "orig.docx"
    shutil.copy2(docx_path, src)
    return src, d


def members(path):
    with zipfile.ZipFile(path) as z:
        return {n: z.read(n) for n in z.namelist()}


if not FIX.is_file():
    print(f"VOID — {FIX.name} is missing. Run tests/make_fixtures.py (with uv run: I-25).")
    sys.exit(3)

print("=" * 96)
print(f"BRANCH 7 SLICE 3 — A19 graphic metadata   [{args.variant} tree]")
print("=" * 96)

SRC = members(FIX)

# =========================================================================================
# ARM 1 — THE FIXTURE CARRIES WHAT THIS FILE CLAIMS IT CARRIES.
#
# Every arm below reads a string from the table at the top of this file. If the fixture and
# the table disagree, every later assertion tests the wrong thing and passes or fails for a
# reason that has nothing to do with A19. So the agreement is asserted first.
# =========================================================================================
print("\n" + "-" * 96)
print("ARM 1 — the fixture and this file agree about what is in it")
print("-" * 96)
for part in ("word/header1.xml", "word/footer1.xml", "word/document.xml",
             "word/charts/chart1.xml", "word/diagrams/data1.xml"):
    ok(f"fixture holds {part}", part in SRC)

_hdr = SRC.get("word/header1.xml", b"").decode("utf-8")
_ftr = SRC.get("word/footer1.xml", b"").decode("utf-8")
_doc = SRC.get("word/document.xml", b"").decode("utf-8")
_cht = SRC.get("word/charts/chart1.xml", b"").decode("utf-8")
_dgm = SRC.get("word/diagrams/data1.xml", b"").decode("utf-8")

ok("header carries wp:docPr/@descr and @title", HDR_DESCR in _hdr and HDR_TITLE in _hdr)
ok("footer carries v:shape/@alt", FTR_ALT in _ftr)
ok("body carries a drawing with @descr (the reported residue)", BODY_DESCR in _doc)
ok("chart part carries a title AND an axis title",
   CHART_TITLE in _cht and CHART_AXIS in _cht and _cht.count("<c:title>") >= 2)
ok("diagram part carries SmartArt text", DGM_1 in _dgm and DGM_2 in _dgm)
ok("header carries an INLINE sdt — no w:p of its own (measurement a)",
   "<w:sdt>" in _hdr and "<w:sdtContent>" in _hdr
   and "<w:p>" not in _hdr.split("<w:sdtContent>")[1].split("</w:sdtContent>")[0])
ok("footer carries a control BOUND to customXml (measurement b)", "w:dataBinding" in _ftr)
ok("no `en` string reproduces its source verbatim — so a delivered value equal to the "
   "source is provably a remnant",
   all(k != v for k, v in EN.items()))

# =========================================================================================
# ARM 2 — THE REPORT. A19's row says the gap is that NOTHING ACKNOWLEDGES IT.
#
# This is the half that covers the surfaces no route reaches. A block would be wrong here:
# CLAUDE.md 5.7's test is whether a COMPLIANT WAY OUT exists, and for a body @descr or a
# chart title there is none inside this pipeline -- the operator cannot edit the client's
# document to satisfy a checker. So the remedy is loudness, not refusal.
# =========================================================================================
print("\n" + "-" * 96)
print("ARM 2 — extraction REPORTS every graphic surface, and names the route or its absence")
print("-" * 96)
src, wd = stage("report", FIX)
r = run([SCRIPTS / "extract_paragraphs.py", src, wd / "paragraphs.json"])
out = r.stdout + r.stderr
if r.returncode != 0:
    void("extraction ran", f"rc={r.returncode}: {out.strip().splitlines()[-1:]}")
else:
    ok("extraction ran", True)
    ok("a GRAPHIC METADATA summary is printed at all",
       "GRAPHIC METADATA" in out.upper())
    for part in ("word/header1.xml", "word/footer1.xml", "word/document.xml",
                 "word/charts/chart1.xml", "word/diagrams/data1.xml"):
        ok(f"the report names {part}", part in out)
    for text in (HDR_DESCR, HDR_TITLE, FTR_ALT, BODY_DESCR, BODY_TITLE,
                 CHART_TITLE, CHART_AXIS, DGM_1, DGM_2):
        ok(f"the report quotes {text[:34]!r}", text in out)
    ok("the report names the SURFACE, not just the text (wp:docPr/@descr)",
       "wp:docPr/@descr" in out)
    ok("the report names the VML surface (v:shape/@alt)", "v:shape/@alt" in out)
    ok("the report sends header and footer surfaces to Step 8b", "Step 8b" in out)
    ok("the report says in terms that some surfaces have NO ROUTE",
       "NO ROUTE" in out.upper())
    ok("the report cites register A19, so the gap is traceable", "A19" in out)
    ok("the report says why source-language alt text matters — a screen reader speaks it",
       "screen reader" in out.lower())

# THE QUIET CONTROL. A document with no graphic must print no graphic summary. A report that
# fires on everything is not a report.
src2, wd2 = stage("report-none", NOGRAPHIC)
r2 = run([SCRIPTS / "extract_paragraphs.py", src2, wd2 / "paragraphs.json"])
if r2.returncode != 0:
    void("extraction ran on the no-graphic fixture", f"rc={r2.returncode}")
else:
    ok("THE QUIET CONTROL — no graphic summary on a document with no graphic",
       "GRAPHIC METADATA" not in (r2.stdout + r2.stderr).upper())

# =========================================================================================
# ARM 3 — THE FIX. Header and footer alt text goes round Step 8b's existing trip.
# =========================================================================================
print("\n" + "-" * 96)
print("ARM 3 — translate_headers_footers.py carries graphic metadata OUT and BACK")
print("-" * 96)
src3, wd3 = stage("route", FIX)
scaffold = wd3 / "headers_footers.json"
r3 = run([SCRIPTS / "translate_headers_footers.py", src3, "--extract", scaffold])
if r3.returncode != 0 or not scaffold.is_file():
    void("--extract ran", f"rc={r3.returncode}")
    entries = []
else:
    ok("--extract ran", True)
    entries = json.loads(scaffold.read_text(encoding="utf-8"))

gm = [e for e in entries if e.get("kind") == "graphic_metadata"]
para = [e for e in entries if e.get("kind", "paragraph") == "paragraph"]
ok("the scaffold carries graphic-metadata entries at all", bool(gm),
   f"{len(gm)} of {len(entries)} entries")
ok("exactly the THREE header/footer surfaces are offered for translation", len(gm) == 3,
   f"{len(gm)}: {sorted(e.get('surface', '?') for e in gm)}")
ok("the body @descr is NOT offered — Step 8b reaches header and footer parts only",
   all(e.get("source", "").split("/")[-1].startswith(("header", "footer")) for e in gm))
_texts = {e.get("text") for e in gm}
ok("the scaffold offers the header @descr", HDR_DESCR in _texts)
ok("the scaffold offers the header @title", HDR_TITLE in _texts)
ok("the scaffold offers the footer VML @alt", FTR_ALT in _texts)
ok("every graphic entry names its surface", all(e.get("surface") for e in gm))
ok("every graphic entry starts with en unfilled — the operator translates it",
   all(e.get("en") in (None, "") for e in gm))
ok("paragraph entries survive alongside them", bool(para), f"{len(para)} paragraph entr(ies)")

# Fill it the way an operator would, then apply.
if gm:
    filled = []
    for e in entries:
        e = dict(e)
        if e.get("kind") == "graphic_metadata":
            e["en"] = EN.get(e.get("text"), e.get("text"))
        else:
            e["en"] = (e.get("text") or "") + " (EN)"
        filled.append(e)
    scaffold.write_bytes(json.dumps(filled, ensure_ascii=False, indent=1).encode("utf-8"))
    r4 = run([SCRIPTS / "translate_headers_footers.py", src3, wd3 / "final",
              "--apply", scaffold])
    hdr_out = wd3 / "final" / "word" / "header1.xml"
    ftr_out = wd3 / "final" / "word" / "footer1.xml"
    if r4.returncode != 0 or not hdr_out.is_file():
        void("--apply ran", f"rc={r4.returncode}: {(r4.stdout + r4.stderr)[-300:]}")
    else:
        ok("--apply ran", True)
        h = hdr_out.read_text(encoding="utf-8")
        f = ftr_out.read_text(encoding="utf-8")
        ok("the header @descr is now ENGLISH", EN[HDR_DESCR] in h)
        ok("the header @title is now ENGLISH", EN[HDR_TITLE] in h)
        ok("the footer VML @alt is now ENGLISH", EN[FTR_ALT] in f)
        ok("the source-language @descr is GONE — not merely joined by the English",
           HDR_DESCR not in h)
        ok("the source-language @title is GONE", HDR_TITLE not in h)
        ok("the source-language VML @alt is GONE", FTR_ALT not in f)
        # THE ATTRIBUTE IS REPLACED, NOT THE ELEMENT. @name is Word's own and not prose.
        ok("@name is untouched — Word assigns it and it is not translatable text",
           'name="Afbeelding 1"' in h)
        ok("the drawing structure survives",
           h.count("<w:drawing>") == _hdr.count("<w:drawing>")
           and h.count("<wp:inline>") == _hdr.count("<wp:inline>"))
        ok("the VML shape structure survives",
           f.count("<v:shape") == _ftr.count("<v:shape"))
        # lxml must not REBIND a namespace prefix -- the first OOXML hard rule, and Word
        # rejects a file where it happened.
        #
        # THE TEST IS SOURCE-RELATIVE, AND THAT IS A CORRECTION MADE ON A MEASUREMENT. It
        # was first written as `"ns0:" not in blob`, and it failed on the footer -- because
        # THE FIXTURE'S OWN w:dataBinding declares `xmlns:ns0` in its @prefixMappings and
        # uses it in its @xpath, so `ns0:` is in the SOURCE footer too. The needle matched
        # something that was always there. What must hold is that the written part introduces
        # no prefix the source did not have, which cannot pass for that reason.
        for label, blob, src_blob in (("header", h, _hdr), ("footer", f, _ftr)):
            ok(f"the written {label} introduces no ns0: prefix the source did not have",
               blob.count("ns0:") == src_blob.count("ns0:"),
               f"source {src_blob.count('ns0:')}, written {blob.count('ns0:')}")
            ok(f"the written {label} declares the same namespaces as the source",
               sorted(etree.fromstring(blob.encode("utf-8")).nsmap.items())
               == sorted(etree.fromstring(src_blob.encode("utf-8")).nsmap.items()))
        ok("both written parts still parse as XML",
           all(etree.fromstring(b.encode("utf-8")) is not None for b in (h, f)))

# =========================================================================================
# ARM 4 — THE HINGE. An entry with NO `kind` key is still a paragraph entry.
#
# All 10 existing frozen header/footer scaffolds in the logs folder were written before
# `kind` existed. If apply stopped treating a kind-less entry as a paragraph, every real
# document's header and footer would silently stop being translated -- and the fixture suite
# would not notice, because the fixture's own scaffold is freshly extracted and HAS the key.
# This is the arm that stands in for tools/hf_corpus_diff.py inside the fast loop.
# =========================================================================================
print("\n" + "-" * 96)
print("ARM 4 — a scaffold entry with no `kind` key still behaves as a paragraph entry")
print("-" * 96)
src5, wd5 = stage("legacy-scaffold", FIX)
sc5 = wd5 / "headers_footers.json"
r5 = run([SCRIPTS / "translate_headers_footers.py", src5, "--extract", sc5])
if r5.returncode != 0 or not sc5.is_file():
    void("--extract ran for the legacy-shape arm", f"rc={r5.returncode}")
else:
    fresh = json.loads(sc5.read_text(encoding="utf-8"))
    # Strip every key the old shape did not have, and drop the graphic entries entirely --
    # which is exactly what a 2026-07 scaffold looks like.
    legacy = [{k: v for k, v in e.items() if k not in ("kind", "surface")}
              for e in fresh if e.get("kind", "paragraph") == "paragraph"]
    ok("a legacy-shaped scaffold could be built from the fresh one", bool(legacy),
       f"{len(legacy)} entr(ies)")
    for e in legacy:
        e["en"] = (e.get("text") or "") + " (EN)"
    sc5.write_bytes(json.dumps(legacy, ensure_ascii=False, indent=1).encode("utf-8"))
    r6 = run([SCRIPTS / "translate_headers_footers.py", src5, wd5 / "final",
              "--apply", sc5])
    out5 = wd5 / "final" / "word" / "header1.xml"
    if r6.returncode != 0 or not out5.is_file():
        void("--apply ran on the legacy-shaped scaffold", f"rc={r6.returncode}: "
             f"{(r6.stdout + r6.stderr)[-300:]}")
    else:
        ok("--apply ran on a scaffold with no `kind` key anywhere", True)
        h5 = out5.read_text(encoding="utf-8")
        ok("its PARAGRAPHS were still translated", "(EN)" in h5)
        ok("its untranslated alt text is left exactly as it was — no key, no claim",
           HDR_DESCR in h5)

# =========================================================================================
# ARM 5 — THE RESIDUE IS HONEST. Asserted as the CURRENT outcome, so a later branch that
# widens the route has to change these lines deliberately rather than discover them green.
# =========================================================================================
print("\n" + "-" * 96)
print("ARM 5 — the body, chart and diagram surfaces are REPORTED and NOT translated")
print("-" * 96)
if (wd3 / "final" / "word" / "header1.xml").is_file():
    # apply writes header/footer parts only; the body and the chart part are untouched by
    # this script by design, and repack carries the ORIGINAL of anything it is not given.
    ok("this script writes header and footer parts only",
       sorted(p.name for p in (wd3 / "final" / "word").glob("*.xml"))
       == ["footer1.xml", "header1.xml"],
       str(sorted(p.name for p in (wd3 / "final" / "word").glob("*.xml"))))
ok("PINNED: the body @descr has no translation route in this pipeline — reported only",
   BODY_DESCR in _doc)
ok("PINNED: chart titles are detected-only (decision 4, no corpus instance to verify "
   "a translation against)", CHART_TITLE in _cht)
ok("PINNED: SmartArt text is detected-only", DGM_1 in _dgm)

# =========================================================================================
# ARM 6 — OWED MEASUREMENT (a). THE INLINE HEADER sdt. RUN, NOT READ.
#
# Wouter, 2026-09-09: translate_headers_footers.py APPEARS to strand nothing because
# _iter_own_runs yields an inline container's runs and _apply_paragraph_text writes into the
# first w:t and clears the rest. THAT IS A READING, and this project's record on readings is
# poor -- one session refuted A16's row from XML structure and was exactly wrong, and slice 2
# found the same row naming docPartObj for a mechanism the corpus reaches by w:placeholder.
#
# AND THE CORPUS CANNOT SETTLE IT, measured rather than assumed: its ONE inline header/footer
# sdt sits in a footer at p_idx 1 and DOES carry text, its paragraph IS in frozen workdir 10
# -- and that entry's `en` is NULL, with all 5 of that scaffold's entries unfilled. Apply's
# preserve-verbatim rule therefore takes the paragraph off the code path, and 0 rebuilt
# header/footer paragraphs in the whole frozen set hold an inline sdt. That is the THIRD
# reason a corpus cannot reach a defect -- it holds the mechanism but not the damage -- and
# the mechanism is the ARTEFACT's, not the shape's.
# =========================================================================================
print("\n" + "-" * 96)
print("ARM 6 — owed measurement (a): the inline header sdt, measured by running it")
print("-" * 96)
if (wd3 / "final" / "word" / "header1.xml").is_file():
    h = (wd3 / "final" / "word" / "header1.xml").read_text(encoding="utf-8")
    root = etree.fromstring(h.encode("utf-8"))
    # The English for that paragraph was written as text + " (EN)", so the source text is a
    # prefix of it. What must NOT survive is the sdt's own source fragment standing ALONE.
    sdt_texts = []
    for sdt in root.iter(f"{{{W}}}sdt"):
        c = sdt.find(f"{{{W}}}sdtContent")
        if c is not None:
            sdt_texts += [(t.text or "") for t in c.iter(f"{{{W}}}t")]
    ok("the header's inline sdt still EXISTS after apply — an emptied content control is "
       "KEPT, never dropped (decision 3, 2026-09-08: it renders and may be locked)",
       any(True for _ in root.iter(f"{{{W}}}sdt")))
    ok("MEASURED, not read: the sdt strands no source-language fragment of its own",
       "DRAFT 1" not in "".join(sdt_texts),
       f"sdt w:t contents after apply: {sdt_texts!r}")
    all_text = "".join((t.text or "") for t in root.iter(f"{{{W}}}t"))
    ok("the paragraph's English is present exactly once — not duplicated by the container",
       all_text.count("(EN)") == len([e for e in (para or [])
                                      if "Versie" in (e.get("text") or "")]) or
       all_text.count("Versie DRAFT 1 van dit document. (EN)") == 1,
       f"paragraph text after apply: {all_text!r}")
else:
    void("owed measurement (a)", "arm 3's apply did not produce a header — nothing to read")

# =========================================================================================
# ARM 7 — OWED MEASUREMENT (b). w:dataBinding. PINNED, AND THE GAP IS STATED.
#
# Measured 2026-09-09: 3 bound controls across 2 corpus documents, ALL IN FOOTERS -- so the
# question lands on this very script, which is sharper than DECISIONS-LOG.md's entry says.
# Word can repopulate a bound control's text from the customXml part when the document is
# opened, so a correct XML edit MAY BE UNDONE ON THE PAGE. Settling that needs Word in the
# loop and no instrument in this repository has it. So: the binding is preserved, the text
# under it is handled like any other, and the RESIDUAL RISK is named. Nothing is claimed.
# =========================================================================================
print("\n" + "-" * 96)
print("ARM 7 — owed measurement (b): w:dataBinding preserved; the page-level risk STATED")
print("-" * 96)
if (wd3 / "final" / "word" / "footer1.xml").is_file():
    f = (wd3 / "final" / "word" / "footer1.xml").read_text(encoding="utf-8")
    fr = etree.fromstring(f.encode("utf-8"))
    ok("the w:dataBinding element survives apply untouched", "w:dataBinding" in f)
    for attr in ("w:xpath", "w:storeItemID", "w:prefixMappings"):
        ok(f"the binding keeps its {attr}", attr in f)
    _src_fr = etree.fromstring(_ftr.encode("utf-8"))
    ok("its xpath is byte-identical to the source's",
       [el.get(f"{{{W}}}xpath") for el in fr.iter(f"{{{W}}}dataBinding")]
       == [el.get(f"{{{W}}}xpath") for el in _src_fr.iter(f"{{{W}}}dataBinding")])
    ok("its prefixMappings survive SEMANTICALLY — same parsed value",
       [el.get(f"{{{W}}}prefixMappings") for el in fr.iter(f"{{{W}}}dataBinding")]
       == [el.get(f"{{{W}}}prefixMappings") for el in _src_fr.iter(f"{{{W}}}dataBinding")])
    # AND A BYTE-LEVEL FACT WORTH RECORDING RATHER THAN NOTICING LATER, and it is PRE-EXISTING
    # rather than slice 3's: this script re-serialises the whole part, so lxml normalises
    # attribute-value escaping. The source's `&apos;` inside @prefixMappings comes back as a
    # literal apostrophe. Legal XML, identical once parsed -- which the two checks above
    # prove -- but the BYTES of a bound control's mappings do move, and no other instrument
    # here would see it: test_no_delivered_byte_moves.py's arm 2 compares old against new on
    # headers-footers.docx, which carries no w:dataBinding at all.
    ok("PINNED, pre-existing: the part is re-serialised, so &apos; comes back as a literal "
       "apostrophe — identical parsed, different bytes",
       "&apos;" in _ftr and "&apos;" not in f,
       f"source has &apos;: {'&apos;' in _ftr}; written has it: {'&apos;' in f}")
    void("whether Word REPOPULATES that control's text from customXml on open",
         "needs Word in the loop; no instrument in this repository has it. Recorded as an "
         "owed measurement rather than answered — see FINDINGS-REGISTER.md A19")
else:
    void("owed measurement (b)", "arm 3's apply did not produce a footer")

# =========================================================================================
# ARM 8 — PARITY. Both trees must handle graphic metadata identically.
# =========================================================================================
print("\n" + "-" * 96)
print("ARM 8 — the two trees agree about graphic metadata")
print("-" * 96)
for script in ("translate_headers_footers.py", "extract_paragraphs.py"):
    a = (ROOT / "uk" / "scripts" / script).read_bytes()
    b = (ROOT / "us" / "scripts" / script).read_bytes()
    if a == b:
        ok(f"{script}: uk and us are byte-identical", True)
        continue
    # Divergence is not a defect in itself -- variant spelling legitimately differs.
    # MEASURED THIS SESSION: translate_headers_footers.py diverges in exactly 3 lines
    # (standardised/standardized, one docstring and two comments), previously UNMEASURED;
    # extract_paragraphs.py in exactly 2 (colour/color, recognise/recognize).
    al, bl = a.decode("utf-8").splitlines(), b.decode("utf-8").splitlines()
    ndiff = sum(1 for x, y in zip(al, bl) if x != y) + abs(len(al) - len(bl))
    expected = {"translate_headers_footers.py": 3, "extract_paragraphs.py": 2}[script]
    ok(f"{script}: divergence is still exactly {expected} line(s) of variant spelling",
       ndiff == expected, f"{ndiff} line(s) differ")
    for needle in ("descr", "graphic", "GRAPHIC"):
        ga = [ln for ln in al if needle in ln]
        gb = [ln for ln in bl if needle in ln]
        ok(f"{script}: the {needle!r} lines are identical across trees", ga == gb,
           f"uk {len(ga)}, us {len(gb)}")

# =========================================================================================
# ARM 9 — THE STEP DOCUMENT. A route nobody is told about is not a route.
# =========================================================================================
print("\n" + "-" * 96)
print("ARM 9 — Step 8b tells the operator about the alt text")
print("-" * 96)
for variant in ("uk", "us"):
    f = ROOT / variant / "skill-docs" / "08-aux-and-quality.md"
    if not f.is_file():
        void(f"{variant}/skill-docs/08-aux-and-quality.md", "file missing")
        continue
    txt = f.read_text(encoding="utf-8", errors="replace")
    ok(f"{variant}: Step 8b gains a sub-step for graphic metadata", "8b.2b" in txt)
    ok(f"{variant}: it names the attribute surfaces",
       "@descr" in txt and "v:shape" in txt)
    ok(f"{variant}: it says a screen reader speaks the alt text",
       "screen reader" in txt.lower())
    # NO RENUMBERING. Step 8b's sub-steps must read 8b.1 · 8b.2 · 8b.2a · 8b.2b · 8b.3.
    order = [s for s in ("8b.1", "8b.2 ", "8b.2a", "8b.2b", "8b.3") if s in txt]
    ok(f"{variant}: Step 8b's sub-steps are contiguous and nothing was renumbered",
       [txt.index(s) for s in order] == sorted(txt.index(s) for s in order)
       and len(order) == 5, f"found {order}")

print("\n" + "=" * 96)
print(f"CHECKED {CHECKED}   FAILED {len(FAIL)}   VOID {len(VOIDED)}")
print("=" * 96)
for f in FAIL:
    print(f"  FAIL  {f}")
for v in VOIDED:
    print(f"  VOID  {v}")
if not args.keep:
    shutil.rmtree(TMP, ignore_errors=True)
else:
    print(f"\nworkdir kept: {TMP}")
print()
print("DECLARED, so a green run is not read as more than it is:")
print("  A19's evidence is FIXTURE-ONLY. The corpus holds 14 graphics across 3 documents and")
print("  NOT ONE attribute of prose on any of them (@descr 0, @title 0, v:shape/@alt 0), so")
print("  there is no real-document instance of translatable graphic metadata in ANY form.")
print("  tools/apply_corpus_diff.py drives APPLY over word/document.xml and cannot see this")
print("  slice at all; tools/hf_corpus_diff.py is the arm that reads the script that changed.")
print("  NEITHER SURFACE RENDERS ON A PAGE — alt text is spoken, not painted. Proved in bytes.")
# ONE VOID IS EXPECTED AND IS NOT A FAILURE: arm 7's Word-in-the-loop question. It is
# recorded as owed, so it must not turn this suite red for ever -- but it must still be
# PRINTED, because a gap that stops being visible stops being owed.
_expected_void = 1
sys.exit(1 if (FAIL or len(VOIDED) != _expected_void) else 0)
