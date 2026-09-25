# -*- coding: utf-8 -*-
"""BRANCH 11 SLICE 2b — repack's pre-repack U+200B scrub (J1) and its remnant block (C22).

WHAT THE ROWS SAY. J1: U+200B is operator scaffolding that survives into the deliverable, and
"the fix must be a PRE-REPACK SCRUB and must NOT be a prohibition on the device". C22: the one
check that reads the delivered .docx with the original in hand is advisory by design, and a
positive source-language hit should BLOCK, "advisory for marker classes it cannot rule on".
Wouter's plan of 2026-09-25 (section 3.2 of PLAN-2-step-b.md) put both in repack_docx.py.

TWO THINGS THE PLAN'S EXPLORATION DID NOT HAVE, measured at this slice's open and put to Wouter
before building (both answered on the recommended option):
  1  THE SKILL'S OWN LEXICONS SANCTION SIX RENDERINGS THE BLOCK WOULD REFUSE — "Italian Revenue
     Agency (Agenzia delle Entrate)", "dupla conforme" and four more. So a declared kept-names
     table, each entry citing its lexicon row, and ARM 4 below reads every lexicon rendering
     column in both trees and fails on any collision nobody declared.
  2  "Capitalised entity nouns that can sit inside a kept name" needed a list: five.

  1  THE SCRUB: every U+200B leaves every prose part's CHARACTER DATA — literal, &#8203;,
     &#x200B; — from the body, a translated header, the comments, and an original part copied
     unchanged; and NOTHING ELSE moves: an attribute value and a non-prose part are untouched,
     and a clean input is byte-identical.
  2  THE SURVIVAL ASSERTION CAN FIRE: with the scrub disabled in-process, repack refuses.
  3  THE REMNANT BLOCK: a function-word remnant refuses delivery — in the body, in a header, in
     deleted text, and one sitting BESIDE a kept name; an entity noun, `convention`, a
     lexicon-sanctioned kept name and a CJK marker only warn; the era-name-plus-digit pattern,
     being Latin text, still blocks; a clean translation is quiet; an undetected language says
     the block did not run.
  4  THE VERDICT: blocking + advisory is exactly scan_remnants' hits; every advisory entry is a
     real marker; every kept name is in the lexicon it cites; and every rendering-column hit in
     this tree's lexicons is covered or declared here.
  5  THE TWO TREES carry the same two files.

RED FIRST: `--scripts DIR` runs arms 1–4 against another copy of the scripts, e.g. HEAD's.

    uv run --with lxml python tests/test_repack_scrub_and_block.py
    uv run --with lxml python tests/test_repack_scrub_and_block.py --variant us
    uv run --with lxml python tests/test_repack_scrub_and_block.py --scripts <dir>   # RED

Synthetic text only. No client text.
"""
import argparse
import importlib.util
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.dont_write_bytecode = True
os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")     # reaches repack's validators (I-18)

sys.path.insert(0, str(Path(__file__).resolve().parent))
from make_fixtures import R, W, WP, docx, p, r  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
ap = argparse.ArgumentParser()
ap.add_argument("--variant", default="uk", choices=("uk", "us"))
ap.add_argument("--scripts", default=None, help="another scripts directory, e.g. HEAD's, for RED")
ap.add_argument("--keep", action="store_true")
args = ap.parse_args()
SCRIPTS = Path(args.scripts).resolve() if args.scripts else ROOT / args.variant / "scripts"
TREE = ROOT / args.variant                     # the lexicons are read from the variant tree
TMP = Path(tempfile.mkdtemp(prefix="b11s2b-test-"))
ENV = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1", PYTHONDONTWRITEBYTECODE="1")
ZW = "\u200b"
FAIL, CHECKED, VOIDED = [], 0, []


def ok(label, cond, detail=""):
    global CHECKED
    CHECKED += 1
    print(("  OK   " if cond else "  XX   ") + label + (f"   ({detail})" if detail and not cond else ""))
    if not cond:
        FAIL.append(label)
    return cond


def void(label, why):
    VOIDED.append(f"{label}: {why}")
    print(f"  ??   {label}   VOID — {why}")


# ---------------------------------------------------------------------------------------------
# SOURCES, one per language the block is exercised in. Each is written so the ORIGINAL's own
# detector names its language (at least five of its function-word markers, and none of the
# words another language counts); every case ASSERTS that precondition from repack's output
# rather than trusting it, because a block that ran in the wrong language proves nothing.
# ---------------------------------------------------------------------------------------------
SRC = {
    "italian": ["Il presente contratto è stipulato tra le parti per la fornitura della turbina.",
                "Ogni parte deve rispettare gli obblighi che sono previsti nel presente contratto.",
                "Le parti sono tenute alla riservatezza delle informazioni per tutta la durata."],
    "french": ["Le présent contrat est conclu entre les parties pour la fourniture des turbines.",
               "Chacune des parties doit respecter les obligations que le contrat prévoit par écrit.",
               "Les parties sont tenues à la confidentialité des informations dans une durée fixe."],
    "japanese": ["本契約は、甲と乙の間で締結される。", "甲は乙に対して本件の業務を委託する。",
                 "乙はその業務を誠実に遂行するものとする。"],
    None: ["Schedule 1.", "Annex.", "Page."],
}
CLEAN = ["This agreement is entered into between the parties for the supply of the turbine.",
         "Each party shall comply with the obligations provided for in this agreement.",
         "The parties shall keep the information confidential for the whole term."]


def wrap(body):
    return (f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
            f'<w:document {W} {R} {WP}><w:body>{body}'
            f'<w:sectPr><w:pgSz w:w="11906" w:h="16838"/></w:sectPr></w:body></w:document>')


def part_xml(root_tag, body):
    return (f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
            f'<w:{root_tag} {W}>{body}</w:{root_tag}>')


CT_EXTRA = ('<Override PartName="/word/header1.xml" ContentType="application/vnd.openxmlformats-'
            'officedocument.wordprocessingml.header+xml"/>'
            '<Override PartName="/word/comments.xml" ContentType="application/vnd.openxmlformats-'
            'officedocument.wordprocessingml.comments+xml"/>'
            '<Override PartName="/word/footnotes.xml" ContentType="application/vnd.openxmlformats-'
            'officedocument.wordprocessingml.footnotes+xml"/>')


def case(name, lang, en, *, body_xml=None, orig_parts=None, hf=None, comments=None, glossary=None):
    """Build the original, a hand-built translated document.xml and notes, and run the REAL
    repack from SCRIPTS. Returns a dict: rc, blob, out (members or None), tmp_left, xml_in."""
    d = TMP / name
    (d / "final" / "word").mkdir(parents=True, exist_ok=True)
    src = SRC[lang]
    orig = d / "orig.docx"
    docx(orig, "".join(p(r(t)) for t in src), extra_parts=orig_parts or {}, extra_ct=CT_EXTRA)
    xml_in = wrap(body_xml if body_xml is not None else "".join(p(r(t)) for t in en)).encode("utf-8")
    xml = d / "final" / "word" / "document.xml"
    xml.write_bytes(xml_in)
    notes = [{"idx": i, "text": s, "en": e.replace(ZW, "").replace("&#8203;", "").replace("&#x200B;", ""),
              "style": "Normal",
              "runs": [{"start": 0, "end": len(s), "text": s, "bold": False, "italic": False}]}
             for i, (s, e) in enumerate(zip(src, en))]
    nj = d / "paragraphs.json"
    nj.write_bytes(json.dumps(notes, ensure_ascii=False, indent=1).encode("utf-8"))
    flags = []
    if hf is not None:
        (d / "hf" / "word").mkdir(parents=True, exist_ok=True)
        (d / "hf" / "word" / "header1.xml").write_bytes(hf.encode("utf-8"))
        flags += ["--headers-footers-dir", str(d / "hf")]
    if comments is not None:
        (d / "comments.xml").write_bytes(comments.encode("utf-8"))
        flags += ["--comments", str(d / "comments.xml")]
    if glossary is not None:
        (d / "glossary.xml").write_bytes(glossary.encode("utf-8"))
        flags += ["--glossary", str(d / "glossary.xml")]
    out = d / "out.docx"
    res = subprocess.run(["uv", "run", "--with", "lxml", "python", str(SCRIPTS / "repack_docx.py"),
                          str(orig), str(xml), str(out), "--paragraphs", str(nj)] + flags,
                         capture_output=True, text=True, encoding="utf-8", errors="replace",
                         cwd=str(ROOT), env=ENV, timeout=600)
    members = None
    if out.exists():
        with zipfile.ZipFile(out) as z:
            members = {n: z.read(n) for n in z.namelist()}
    with zipfile.ZipFile(orig) as z:
        orig_members = {n: z.read(n) for n in z.namelist()}
    return {"rc": res.returncode, "blob": (res.stdout or "") + (res.stderr or ""), "out": members,
            "tmp_left": Path(str(out) + ".tmp").exists(), "xml_in": xml_in, "orig": orig_members}


def lang_ran(c, lang):
    """The block's precondition, read from the BLOCK's own line — never the lexicon scan's, which
    names a language too and would let this pass for the wrong reason."""
    return bool(re.search(rf"Remnant block: language={lang}\b", c["blob"]))


def refused(c, label, *needles):
    ok(f"{label}: repack REFUSES (non-zero exit)", c["rc"] != 0, f"rc={c['rc']}")
    ok(f"{label}: NOTHING at the delivery path, and no .tmp left behind", c["out"] is None and not c["tmp_left"],
       f"out={'present' if c['out'] is not None else 'absent'} tmp={c['tmp_left']}")
    ok(f"{label}: announced as an intentional gate, naming what it found",
       "SKILL GATE FIRED" in c["blob"] and all(n in c["blob"] for n in needles),
       f"missing {[n for n in ('SKILL GATE FIRED',) + needles if n not in c['blob']]}")


def delivered(c, label):
    ok(f"{label}: delivered (exit 0, a .docx at the delivery path)", c["rc"] == 0 and c["out"] is not None,
       f"rc={c['rc']}")


def zw_in_chardata(data):
    s = data.decode("utf-8", errors="replace")
    chunks = re.findall(r">([^<]+)<", s)
    return sum(ch.count(ZW) + len(re.findall(r"&#(?:0*8203|[xX]0*200[bB]);", ch)) for ch in chunks)


print("=" * 96)
print(f"BRANCH 11 SLICE 2b — the U+200B scrub and the remnant block   variant={args.variant}")
print(f"scripts {SCRIPTS}")
print("=" * 96)

# =============================================================================================
# ARM 1 — THE SCRUB (J1). Every prose part, character data only, every form of the character.
# =============================================================================================
print("\n" + "-" * 96 + "\nARM 1 — THE SCRUB: every U+200B leaves every prose part, and nothing else moves\n" + "-" * 96)
EN_ZW = ["This agreement is entered into" + ZW + " between the parties for the supply of the turbine.",
         "Each party" + ZW + " shall comply with the obligations provided for in this agreement.",
         "The parties shall keep the information confidential" + ZW + " for the whole term."]
c = case("1a-body", "italian", EN_ZW)
delivered(c, "1a body")
if c["out"] is not None:
    d = c["out"]["word/document.xml"]
    ok("1a: 0 U+200B in the delivered body (3 planted)", d.count(ZW.encode("utf-8")) == 0 and c["xml_in"].count(ZW.encode("utf-8")) == 3)
    ok("1a: the body is the input with every U+200B removed — and NOTHING ELSE changed",
       d == c["xml_in"].replace(ZW.encode("utf-8"), b""))
    ok("1a: every other member is the original's, byte for byte",
       all(c["out"][n] == c["orig"][n] for n in c["orig"] if n != "word/document.xml"))
    ok("1a: repack SAYS how many it removed, and where (a count, never text)",
       bool(re.search(r"U\+200B scrubbed: 3 from word/document\.xml", c["blob"])))

EN_REF = ["This agreement is entered into&#8203; between the parties for the supply of the turbine.",
          "Each party&#x200B; shall comply with the obligations provided for in this agreement.",
          "The parties shall keep the information confidential for the whole term."]
c = case("1b-refs", "italian", EN_REF)
delivered(c, "1b character references")
if c["out"] is not None:
    d = c["out"]["word/document.xml"]
    ok("1b: &#8203; and &#x200B; are removed too (2 planted, 0 left)",
       zw_in_chardata(d) == 0 and zw_in_chardata(c["xml_in"]) == 2)
    ok("1b: and nothing else changed",
       d == c["xml_in"].replace(b"&#8203;", b"").replace(b"&#x200B;", b""))

HDR_ZW = part_xml("hdr", p(r("Confidential" + ZW + " draft")))
COM_ZW = part_xml("comments", f'<w:comment w:id="0" w:author="A">{p(r("Check" + ZW + " this"))}</w:comment>')
FN_ZW = part_xml("footnotes", f'<w:footnote w:id="1">{p(r("A" + ZW + " note"))}</w:footnote>')
CORE_ZW = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<cp:coreProperties '
           'xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" '
           'xmlns:dc="http://purl.org/dc/elements/1.1/"><dc:title>Title' + ZW + 'here</dc:title></cp:coreProperties>')
c = case("1c-parts", "italian", CLEAN,
         orig_parts={"word/header1.xml": part_xml("hdr", p(r("Riservato"))),
                     "word/comments.xml": part_xml("comments", f'<w:comment w:id="0" w:author="A">{p(r("Verifica"))}</w:comment>'),
                     "word/footnotes.xml": FN_ZW, "docProps/core.xml": CORE_ZW},
         hf=HDR_ZW, comments=COM_ZW)
delivered(c, "1c side parts")
if c["out"] is not None:
    for part, why in (("word/header1.xml", "a TRANSLATED header"), ("word/comments.xml", "the translated comments"),
                      ("word/footnotes.xml", "an ORIGINAL part copied unchanged")):
        ok(f"1c: 0 U+200B in {part} — {why}", zw_in_chardata(c["out"][part]) == 0)
    ok("1c: the copied footnotes are the original's with U+200B removed and nothing else",
       c["out"]["word/footnotes.xml"] == FN_ZW.encode("utf-8").replace(ZW.encode("utf-8"), b""))
    ok("1c: a NON-PROSE part is untouched, U+200B and all (docProps/core.xml)",
       c["out"]["docProps/core.xml"] == CORE_ZW.encode("utf-8"))

ATTR_BODY = (p('<w:bookmarkStart w:id="0" w:name="k' + ZW + 'ey"/>', r(CLEAN[0]), '<w:bookmarkEnd w:id="0"/>')
             + p(r(CLEAN[1])) + p(r(CLEAN[2])))
c = case("1d-attr", "italian", CLEAN, body_xml=ATTR_BODY)
delivered(c, "1d attribute value")
if c["out"] is not None:
    ok("1d: a U+200B inside an ATTRIBUTE is left alone — it is in no reading (declared boundary)",
       c["out"]["word/document.xml"] == c["xml_in"])

c = case("1e-clean", "italian", CLEAN)
delivered(c, "1e clean control")
if c["out"] is not None:
    ok("1e CONTROL: a clean input's body is byte-identical to the input", c["out"]["word/document.xml"] == c["xml_in"])
    ok("1e CONTROL: and repack reports no scrub", "U+200B scrubbed" not in c["blob"])

# =============================================================================================
# ARM 2 — THE SURVIVAL ASSERTION CAN FIRE. A check never seen to fail is not a check: disable
# the scrub in-process and the archive-level assertion must refuse, read from the archive.
# =============================================================================================
print("\n" + "-" * 96 + "\nARM 2 — the survival assertion refuses when the scrub is disabled\n" + "-" * 96)
d2 = TMP / "2-survive"
src2 = TMP / "1a-body"
if not (src2 / "orig.docx").is_file():
    void("ARM 2", "arm 1a's inputs are missing")
else:
    driver = d2 / "driver.py"
    d2.mkdir(parents=True, exist_ok=True)
    driver.write_bytes((
        "import sys\nsys.dont_write_bytecode = True\n"
        f"sys.path.insert(0, {str(SCRIPTS)!r})\n"
        "import repack_docx as R\n"
        "R._scrub_zwsp = lambda data: (data, 0)\n"
        "try:\n"
        f"    R.repack({str(src2 / 'orig.docx')!r}, {str(src2 / 'final' / 'word' / 'document.xml')!r}, "
        f"{str(d2 / 'out.docx')!r}, paragraphs_json={str(src2 / 'paragraphs.json')!r})\n"
        "    print('NO-REFUSAL')\n"
        "except RuntimeError as e:\n"
        "    print('REFUSED:', e)\n").encode("utf-8"))
    res = subprocess.run(["uv", "run", "--with", "lxml", "python", str(driver)], capture_output=True, text=True,
                         encoding="utf-8", errors="replace", cwd=str(ROOT), env=ENV, timeout=600)
    blob = (res.stdout or "") + (res.stderr or "")
    ok("2: with the scrub disabled, repack REFUSES on the surviving U+200B",
       "REFUSED:" in blob and "U+200B SURVIVED" in blob, blob.strip().splitlines()[-1][:120] if blob.strip() else "")
    ok("2: and nothing reaches the delivery path, no .tmp left",
       not (d2 / "out.docx").exists() and not (d2 / "out.docx.tmp").exists())

# =============================================================================================
# ARM 3 — THE REMNANT BLOCK (C22). A hit refuses delivery unless its class is declared advisory.
# =============================================================================================
print("\n" + "-" * 96 + "\nARM 3 — THE REMNANT BLOCK: a function word refuses; the declared classes only warn\n" + "-" * 96)


def en_with(line):
    return [CLEAN[0], line, CLEAN[2]]


GATE = "SOURCE-LANGUAGE REMNANT"
c = case("3a-function-word", "italian", en_with("Each party shall comply with the obligations della contract."))
ok("3a precondition: the block ran in italian", lang_ran(c, "italian"))
refused(c, "3a a function-word remnant in the body", GATE, "word/document.xml", "della")

c = case("3b-entity", "french", en_with("The Seller is the Alpha Société, a company of good standing."))
ok("3b precondition: the block ran in french", lang_ran(c, "french"))
delivered(c, "3b an entity noun inside a kept name (Société)")
ok("3b: and it WARNS, naming the advisory class", "ADVISORY" in c["blob"] and "Société" in c["blob"])

c = case("3c-convention", "french", en_with("The parties shall comply with the Aarhus Convention in all respects."))
ok("3c precondition: the block ran in french", lang_ran(c, "french"))
delivered(c, "3c `convention`, an English word")
ok("3c: and it WARNS", "ADVISORY" in c["blob"] and "convention" in c["blob"])

c = case("3d-kept-name", "italian", en_with("The tax is assessed by the Italian Revenue Agency (Agenzia delle Entrate)."))
ok("3d precondition: the block ran in italian", lang_ran(c, "italian"))
delivered(c, "3d a kept name the lexicon sanctions (Agenzia delle Entrate)")
ok("3d: and it WARNS, citing the lexicon", "ADVISORY" in c["blob"] and "italian-taxes.md" in c["blob"])

c = case("3e-beside-kept", "italian", en_with("The tax is assessed by the Agenzia delle Entrate della Repubblica."))
refused(c, "3e a function word BESIDE a kept name — the name covers its own span only", GATE, "della")

c = case("3f-cjk", "japanese", en_with("This Agreement (契約) is made between the two parties named above."))
ok("3f precondition: the block ran in japanese", lang_ran(c, "japanese"))
delivered(c, "3f CJK characters (a kept name in its own script)")
ok("3f: and it WARNS", "ADVISORY" in c["blob"])

c = case("3g-era", "japanese", en_with("This Agreement is dated Reiwa 5, on the first day of April."))
refused(c, "3g an era name with a year — Latin text, the Gregorian-only rule", GATE, "Reiwa")

HDR_REM = part_xml("hdr", p(r("Page header della company")))
c = case("3h-header", "italian", CLEAN, orig_parts={"word/header1.xml": part_xml("hdr", p(r("Riservato")))}, hf=HDR_REM)
refused(c, "3h a remnant in a translated HEADER, the body clean", GATE, "word/header1.xml")

DEL_BODY = (p(r(CLEAN[0])) + p(r("Each party shall comply "),
            '<w:del w:id="1" w:author="A" w:date="2026-01-01T00:00:00Z"><w:r><w:delText>della</w:delText></w:r></w:del>',
            r(" with this agreement.")) + p(r(CLEAN[2])))
c = case("3i-deleted", "italian", [CLEAN[0], "Each party shall comply  with this agreement.", CLEAN[2]], body_xml=DEL_BODY)
refused(c, "3i a remnant in DELETED text only (the reject reading)", GATE, "della")

# THE GLOSSARY PART, BY ITS FULL PATH (C19). Moved here from tests/test_glossary_route.py's arm 5,
# which could never run it: that fixture's language is undetectable, the old scan was skipped, and
# the arm passed on an unrelated line naming the path (register I-30). Here the language is Italian.
def gloss(text):
    return part_xml("glossaryDocument", '<w:docParts><w:docPart><w:docPartPr><w:name w:val="P1"/>'
                    f'</w:docPartPr><w:docPartBody>{p(r(text))}</w:docPartBody></w:docPart></w:docParts>')


GL_IT = gloss("Fare clic qui per immettere il nome della parte")
c = case("3l-glossary", "italian", CLEAN, orig_parts={"word/glossary/document.xml": GL_IT},
         glossary=gloss("Click here to enter the name della party"))
refused(c, "3l a remnant in the translated GLOSSARY part, named by its full path", GATE,
        "word/glossary/document.xml")
c = case("3m-glossary-kept", "italian", CLEAN, orig_parts={"word/glossary/document.xml": GL_IT}, glossary=GL_IT)
refused(c, "3m the keep-as-is route: the ORIGINAL glossary passed unchanged still carries the source "
        "language, so it no longer ships", GATE, "word/glossary/document.xml")

c = case("3j-clean", "italian", CLEAN)
ok("3j precondition: the block ran in italian", lang_ran(c, "italian"))
delivered(c, "3j CONTROL: a clean translation")
ok("3j CONTROL: no remnant warning and no refusal", "remnant(s)" not in c["blob"] and GATE not in c["blob"])

c = case("3k-undetected", None, en_with("Each party shall comply with the obligations della contract."))
delivered(c, "3k BOUNDARY: no language detected from the original")
ok("3k: and it SAYS the block did not run — branch 12 owns saying it is guessing",
   "Remnant block skipped" in c["blob"])

# =============================================================================================
# ARM 4 — THE VERDICT, read in-process from the marker module the scripts import.
# =============================================================================================
print("\n" + "-" * 96 + "\nARM 4 — the verdict, its tables, and the lexicons they must agree with\n" + "-" * 96)
spec = importlib.util.spec_from_file_location("slm_under_test", SCRIPTS / "source_language_markers.py")
slm = importlib.util.module_from_spec(spec)
spec.loader.exec_module(slm)
verdict = getattr(slm, "remnant_verdict", None)
ADV = getattr(slm, "REMNANT_ADVISORY", None)
KEPT = getattr(slm, "LEXICON_KEPT_NAMES", None)
ok("4: the module declares remnant_verdict, REMNANT_ADVISORY and LEXICON_KEPT_NAMES",
   verdict is not None and isinstance(ADV, dict) and isinstance(KEPT, dict))

RENDER = re.compile(r"english", re.IGNORECASE)
BT = re.compile(r"`([^`]*)`")


def rendering_cells(tree):
    """(file, language, cell) for every cell of a column whose header names English, or is
    'Output' — backticked spans only where a cell has them, because the lexicon marks literal
    output with backticks and explains it outside them."""
    for f in sorted((tree / "sub-lexicons").glob("*.md")) + sorted((tree / "references").glob("*.md")):
        lf = f.name.split("-")[0] if f.parent.name == "sub-lexicons" else None
        langs = [lf] if lf in slm.LANGUAGE_MARKERS else (sorted(slm.LANGUAGE_MARKERS) if lf is None else [])
        hdr = None
        for ln in f.read_text(encoding="utf-8").splitlines():
            s = ln.strip()
            if not s.startswith("|"):
                hdr = None
                continue
            if set(s) <= set("|-: "):
                continue
            cols = [x.strip() for x in s.strip("|").split("|")]
            if hdr is None:
                hdr = cols
                continue
            for ci, cell in enumerate(cols):
                h = hdr[ci] if ci < len(hdr) else ""
                if RENDERING(h):
                    for sp in (BT.findall(cell) or [cell]):
                        for L in langs:
                            yield f.name, L, sp


def RENDERING(h):
    return bool(RENDER.search(h)) or h == "Output"


# Two cells in an English column that EXPLAIN rather than render, declared here with the reason —
# test data, not skill data, so the shipped table holds only names an operator is told to write.
EXPLANATORY = {
    ("italian-employment.md", r"\bCommittente\b"):
        "the English cell's own rendering is 'quasi-dependent work'; the Italian is the statute's name in a note",
    ("italian-general-legal.md", r"\bCorrispettivo\b"):
        "usage guidance inside the English cell, quoting the Italian word it explains",
}

if verdict is None:
    for claim in ("parity with scan_remnants", "advisory entries are real markers", "kept names are in their lexicon",
                  "every lexicon rendering hit covered or declared", "kept-name matching folds case, spaces, apostrophes"):
        ok(f"4: {claim}", False, "remnant_verdict is not in this module")
else:
    battery = [t for t in (CLEAN + EN_ZW + [
        "Each party shall comply with the obligations della contract.",
        "The Seller is the Alpha Société, a company of good standing.",
        "The tax is assessed by the Agenzia delle Entrate della Repubblica.",
        "This Agreement (契約) is made between 甲 and 乙.", "dated Reiwa 5 and Heisei 29",
        "the Windpark Noord project, the Beta Spółka, the Gamma Sociedade and the Unternehmen",
        "hierbij verklaren de Partijen dat de Overeenkomst"])]
    battery += [cell for _f, _L, cell in rendering_cells(TREE)]
    bad = []
    for t in battery:
        for L in slm.LANGUAGE_MARKERS:
            b, a = verdict(t, L)
            if len(b) + len(a) != len(slm.scan_remnants(t, L)):
                bad.append((L, t[:40]))
    ok(f"4: blocking + advisory == scan_remnants' hits, on {len(battery)} texts x {len(slm.LANGUAGE_MARKERS)} languages",
       not bad, f"{len(bad)} disagree, e.g. {bad[:2]}")
    allpats = {q for ps in slm.LANGUAGE_MARKERS.values() for q in ps}
    ok(f"4: every REMNANT_ADVISORY key ({len(ADV)}) is a real marker, with a reason",
       all(k in allpats and str(v).strip() for k, v in ADV.items()), f"{[k for k in ADV if k not in allpats]}")
    ok("4: the advisory markers are exactly the ones Wouter approved: convention + the five entity nouns",
       {k.replace(chr(92) + "b", "") for k in ADV} == {"convention", "Société", "Sociedade", "Spółka", "Unternehmen", "Windpark"})
    missing = []
    for name, cite in KEPT.items():
        fn = re.search(r"[\w-]+\.md", str(cite))
        path = TREE / "sub-lexicons" / fn.group(0) if fn else None
        if not path or not path.is_file() or name not in path.read_text(encoding="utf-8"):
            missing.append(name)
    ok(f"4: every kept name ({len(KEPT)}) is present in the lexicon file it cites — the pointer probed",
       not missing, f"{missing}")
    uncovered, used = [], set()
    for f, L, cell in rendering_cells(TREE):
        b, _a = verdict(cell, L)
        for pat, _ctx in b:
            if (f, pat) in EXPLANATORY:
                used.add((f, pat))
            else:
                uncovered.append((f, L, pat))
    ok("4: EVERY lexicon rendering-column hit is advisory, a kept name, or declared explanatory here",
       not uncovered, f"{uncovered[:4]}")
    ok("4: and no explanatory declaration is stale", used == set(EXPLANATORY), f"unused {set(EXPLANATORY) - used}")
    folds = [("AGENZIA DELLE  ENTRATE", "italian"), ("Codice della Crisi d\u2019Impresa e dell\u2019Insolvenza", "italian"),
             ("the Agenzia delle\nEntrate", "italian")]
    ok("4: kept-name matching folds case, runs of whitespace and both apostrophes",
       all(not verdict(t, L)[0] and verdict(t, L)[1] for t, L in folds),
       f"{[(t, len(verdict(t, L)[0])) for t, L in folds]}")

# =============================================================================================
# ARM 5 — THE TWO TREES carry the same two files (only when run against the working tree).
# =============================================================================================
print("\n" + "-" * 96 + "\nARM 5 — the two trees\n" + "-" * 96)
if args.scripts:
    void("ARM 5", "run against another scripts directory; the trees are the working tree's")
else:
    ok("5: repack_docx.py is byte-identical in uk/ and us/",
       (ROOT / "uk" / "scripts" / "repack_docx.py").read_bytes()
       == (ROOT / "us" / "scripts" / "repack_docx.py").read_bytes())
    # ONE DIFFERENCE PREDATES THIS SLICE AND IS THE VARIANTS' OWN: a docstring's "minimise" /
    # "minimize". Asserted as exactly that, so any other difference — this slice's included — fails.
    uk_m = (ROOT / "uk" / "scripts" / "source_language_markers.py").read_bytes()
    ok("5: source_language_markers.py differs between the trees ONLY by HEAD's one variant spelling",
       uk_m.replace(b"to minimise false", b"to minimize false")
       == (ROOT / "us" / "scripts" / "source_language_markers.py").read_bytes())

if not args.keep:
    shutil.rmtree(TMP, ignore_errors=True)
print("\n" + "=" * 96)
print(f"  {CHECKED} check(s), {len(FAIL)} failure(s), {len(VOIDED)} void")
for f in FAIL:
    print(f"    FAIL  {f}")
for v in VOIDED:
    print(f"    VOID  {v}")
print("=" * 96)
sys.exit(1 if FAIL or VOIDED else 0)
