"""test_delivered_sides.py - branch 11 slices 3a and 3b: the SIDE-PART arm of `validate_apply.py
--delivered --original`, and slice 3b's declaration route for footnotes, endnotes and the glossary, on
synthetic input. Every document here is invented and built in a temporary directory; nothing is read
from the corpus.

ONE FAILING INPUT PER ARM, RED FIRST, AND A CLEAN DOCUMENT PROVED QUIET. What each arm asserts
(PLAN-2-step-b.md section 3.2, block "SLICE 3's WRITTEN PLAN", acceptance (d)):

   1  a clean document -- header, page-number footer, two comments, a footnote, an endnote, the
      glossary, every reference intact -- is READ and carries no side finding, --strict exit 0
   2  headers and footers with NO scaffold: a letter-bearing header kept as the source's is a
      finding, undeclared-kept; a page-number-only footer is NOT, because <<PAGE>> is a field
      placeholder and not prose; a footer with prose beside its field IS
   3  a filled scaffold entry delivered as the source's is declared-source
   4  an entry declared KEPT -- en null, or en == text -- delivered as the source's is quiet; a
      kept entry that CHANGED is moved
   5  matched at p_idx AND by text, reported apart: an English found in another paragraph of the
      part is elsewhere; found nowhere is other
   6  an entry whose text is not the source's at its p_idx is misaligned
   7  THE HEADER/FOOTER SCRIPT'S LATENT HANDLING OF A TRACKED DELETION, PROVED WITH THE REAL SCRIPT:
      --extract never offers the deleted text, --apply leaves it in the source's words, and the
      check reports deleted-kept; a delivery with the deleted text emptied is deleted-emptied
   8  THE COMMENT SCRIPT'S, PROVED WITH THE REAL SCRIPT: it empties a comment's deleted text, and
      the check reports deleted-emptied -- a comment declared kept included, since the script
      rewrites it too
   9  A MULTI-PARAGRAPH COMMENT, THROUGH THE REAL SCRIPT, ARRIVES AS ONE PARAGRAPH: COUNTED, never
      blocking (Wouter, 2026-09-25 (4)), so --strict still exits 0
  10  comments with no declaration kept as the source's are undeclared-kept, one per id
  11  a declared comment delivered as the source's is declared-source; one declared kept is quiet
  12  a comment absent from the delivery is lost, and the reference left behind is dangling
  13  footnotes and endnotes kept as the source's are kept-source; the separators are not examined
  14  glossary paragraphs kept as the source's are kept-source, one per paragraph
  15  references BY ID in every part: an orphaned footnote, a dangling comment; an orphan the
      ORIGINAL already has is inherited, a count and never a finding
  16  a text-bearing part the delivery lacks is missing, and is not reported a second time
  17  a text-bearing part outside Step 8's six kinds delivered byte-identical is kept-source
  18  NOT READ, never a pass: a delivery given as document.xml, and no original
  19  a partial install -- the header/footer script's reader absent -- is a NAMED gap and a
      finding, never a silent skip
 19b  THE COMMENT SCRIPT'S OWN READER RETURNS ESCAPED TEXT, PROVED WITH THE REAL SCRIPT: --list
      shows '&amp;' where Word shows '&', the verbatim copy Step 8c asks for is escaped a second
      time, and the check -- reading the comment as Word does -- reports it as moved; the same
      comment declared as Word shows it is quiet
  20  a declaration file that will not parse, or is the wrong JSON shape, is a finding, never read
      as no declaration; a scaffold entry that matches no paragraph is unmatched, never dropped
  21  --strict turns a side finding into exit 1; without it the run exits 0

SLICE 3b (PLAN-2-step-b.md section 3.2, block "SLICE 3b's WRITTEN PLAN"): Step 8d and 8e save
footnotes_translations.json, endnotes_translations.json and glossary_translations.json beside the
notes -- source w:t text to English, a text mapped to itself kept (Wouter, 2026-09-28 (2)):
  22  footnotes and endnotes DECLARED KEPT -- every letter-bearing text mapped to itself -- delivered
      as the source's are quiet, --strict exit 0
  23  an UNDECLARED note is still kept-source, whatever else the file declares; a note with only one
      of its two runs declared kept is too
  24  a note declared with English and delivered as the source's is declared-source; delivered in
      that English it is quiet
  25  a note declared KEPT that changed in the delivery is moved
  26  the glossary, paragraph by paragraph: declared kept quiet, undeclared kept-source, declared
      with English and delivered as the source's declared-source, declared kept and changed moved
  27  a key matches as the template's regex sees it -- ESCAPED -- and as Word shows it
  28  both readings: a note's deleted text must be declared kept too, or the note is kept-source
  29  a notes declaration that will not parse, or is not an object of strings, is side-decl, and is
      never read as a declaration
  30  a U+200B in the SOURCE, which repack's scrub removes from every side part, hides nothing: a
      footnote, header, comment and glossary paragraph kept as the source's less it are still
      findings, and declared kept each is quiet -- never moved (register I-32)
  31  STEP 8d's AND 8e's OWN TEMPLATES, run from the step document on a synthetic document, write
      what the check reads: the declared English and the declared keep quiet, a text left out of
      the file shipped in the source's words and reported
  32  Step 8's wording in both trees: 8b and 8d are MANDATORY whenever the part carries text, no
      step document gates on source-language text (C7), and the three files are named

  33  the check READS ONLY: every input file hashes the same before and after
  34  no document text is printed, only part names, ids, classes and lengths
  35  the side block is byte-identical in both trees

    uv run --with lxml python tests/test_delivered_sides.py
    uv run --with lxml python tests/test_delivered_sides.py --variant us
    uv run --with lxml python tests/test_delivered_sides.py --script <path>   # the pre-slice copy, for RED
"""
import argparse
import hashlib
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
os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")

ROOT = Path(__file__).resolve().parent.parent
ap = argparse.ArgumentParser()
ap.add_argument("--variant", choices=("uk", "us"), default="uk")
ap.add_argument("--script", default=None)
args = ap.parse_args()
SCRIPTS = ROOT / args.variant / "scripts"
SCRIPT = Path(args.script) if args.script else SCRIPTS / "validate_apply.py"
TMP = Path(tempfile.mkdtemp(prefix="b11s3a-sides-test-"))
ENV = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1", PYTHONDONTWRITEBYTECODE="1")
W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
PY = ["uv", "run", "--with", "lxml", "python"]
FAIL, CHECKED = [], 0


def ok(label, cond, detail=""):
    global CHECKED
    CHECKED += 1
    print(f"  {'OK  ' if cond else 'XX  '} {label}" + (f"   ({detail})" if detail and not cond else ""))
    if not cond:
        FAIL.append(label)


# ---------------------------------------------------------------------------------------------
# BUILDERS. A paragraph from parts: a str is a run; ('ins', s) / ('del', s) a tracked change;
# ('cref', i) / ('fref', i) / ('eref', i) a comment, footnote or endnote reference; ('page',) a
# PAGE field whose cached result is 1.
# ---------------------------------------------------------------------------------------------
def run_(s):
    return f'<w:r><w:t xml:space="preserve">{s}</w:t></w:r>'


def P(*parts):
    out = []
    for p in parts:
        if isinstance(p, str):
            out.append(run_(p))
        elif p[0] == "ins":
            out.append(f'<w:ins w:id="91" w:author="x">{run_(p[1])}</w:ins>')
        elif p[0] == "del":
            out.append(f'<w:del w:id="92" w:author="x"><w:r><w:delText xml:space="preserve">{p[1]}'
                       f'</w:delText></w:r></w:del>')
        elif p[0] in ("cref", "fref", "eref"):
            tag = {"cref": "commentReference", "fref": "footnoteReference", "eref": "endnoteReference"}[p[0]]
            out.append(f'<w:r><w:{tag} w:id="{p[1]}"/></w:r>')
        elif p[0] == "page":
            out.append('<w:r><w:fldChar w:fldCharType="begin"/></w:r>'
                       '<w:r><w:instrText xml:space="preserve"> PAGE </w:instrText></w:r>'
                       '<w:r><w:fldChar w:fldCharType="separate"/></w:r>'
                       '<w:r><w:t>1</w:t></w:r><w:r><w:fldChar w:fldCharType="end"/></w:r>')
    return "<w:p>" + "".join(out) + "</w:p>"


def xml(root, inner):
    return f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:{root} xmlns:w="{W}">{inner}</w:{root}>'


def body(*paras):
    return xml("document", "<w:body>" + "".join(paras) + "</w:body>")


def hdr(*paras):
    return xml("hdr", "".join(paras))


def ftr(*paras):
    return xml("ftr", "".join(paras))


def comments(cm):
    return xml("comments", "".join(f'<w:comment w:id="{i}" w:author="x" w:initials="x">{"".join(ps)}</w:comment>'
                                   for i, ps in cm.items()))


def notes(kind, nt):
    sep = (f'<w:{kind} w:type="separator" w:id="-1"><w:p><w:r><w:separator/></w:r></w:p></w:{kind}>'
           f'<w:{kind} w:type="continuationSeparator" w:id="0"><w:p><w:r><w:continuationSeparator/></w:r>'
           f'</w:p></w:{kind}>')
    return xml(kind + "s", sep + "".join(f'<w:{kind} w:id="{i}">{"".join(ps)}</w:{kind}>' for i, ps in nt.items()))


def glossary(*paras):
    return xml("glossaryDocument", "<w:docParts><w:docPart><w:docPartBody>" + "".join(paras)
               + "</w:docPartBody></w:docPart></w:docParts>")


CHART = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?><c:chartSpace '
         'xmlns:c="http://schemas.openxmlformats.org/drawingml/2006/chart" '
         'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"><c:chart><c:title><c:tx><c:rich>'
         '<a:p><a:r><a:t>Wykres roczny</a:t></a:r></a:p></c:rich></c:tx></c:title></c:chart></c:chartSpace>')

REFS = (("cref", 0), ("cref", 1), ("fref", 1), ("eref", 1))
NOTES = [{"idx": 0, "text": "Zdroj jedna", "en": "Source one"}]
ORIG = {
    "word/document.xml": body(P("Zdroj jedna", *REFS)),
    "word/header1.xml": hdr(P("Nagłówek umowy")),
    "word/footer1.xml": ftr(P(("page",))),
    "word/comments.xml": comments({0: [P("Uwaga pierwsza")], 1: [P("Keep this note")]}),
    "word/footnotes.xml": notes("footnote", {1: [P("Przypis jeden")]}),
    "word/endnotes.xml": notes("endnote", {1: [P("Uwaga końcowa")]}),
    "word/glossary/document.xml": glossary(P("Blok tekstu")),
}
DELIV = {
    "word/document.xml": body(P("Source one", *REFS)),
    "word/header1.xml": hdr(P("Agreement header")),
    "word/footer1.xml": ftr(P(("page",))),
    "word/comments.xml": comments({0: [P("First remark")], 1: [P("Keep this note")]}),
    "word/footnotes.xml": notes("footnote", {1: [P("Footnote one")]}),
    "word/endnotes.xml": notes("endnote", {1: [P("Final remark")]}),
    "word/glossary/document.xml": glossary(P("Text block")),
}
HF = [{"idx": 0, "source": "word/header1.xml", "p_idx": 0, "text": "Nagłówek umowy", "en": "Agreement header"},
      {"idx": 1, "source": "word/footer1.xml", "p_idx": 0, "text": "<<PAGE>>", "en": None,
       "fields": [{"type": "PAGE", "cached_result": "1"}]}]
CM = {"0": "First remark", "1": "Keep this note"}
ABSENT = object()
UNCHANGED = []                      # (case, every input hashing the same after the run as before)


def write_docx(path, members):
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        for name, text in members.items():
            z.writestr(name, text.encode("utf-8") if isinstance(text, str) else text)


def case(name, orig=None, deliv=None, hf=ABSENT, cm=ABSENT, strict=False, deliv_xml=False,
         original=True, script=None, raw_hf=None, extra=None):
    """Build the case in its own directory and run the check. hf / cm: ABSENT writes the clean
    declaration, None writes none at all, anything else is written as given. extra: more files
    beside the notes, {name: bytes written as they are, or anything else written as JSON}."""
    d = TMP / name
    d.mkdir(parents=True, exist_ok=True)
    (d / "paragraphs.json").write_bytes(json.dumps(NOTES).encode("utf-8"))
    hf = HF if hf is ABSENT else hf
    cm = CM if cm is ABSENT else cm
    if raw_hf is not None:
        (d / "headers_footers.json").write_bytes(raw_hf)
    elif hf is not None:
        (d / "headers_footers.json").write_bytes(json.dumps(hf, ensure_ascii=False).encode("utf-8"))
    if cm is not None:
        (d / "comments_translations.json").write_bytes(json.dumps(cm, ensure_ascii=False).encode("utf-8"))
    for fname, content in (extra or {}).items():
        (d / fname).write_bytes(content if isinstance(content, bytes)
                                else json.dumps(content, ensure_ascii=False).encode("utf-8"))
    write_docx(d / "orig.docx", ORIG if orig is None else orig)
    dm = DELIV if deliv is None else deliv
    if deliv_xml:
        (d / "delivered.xml").write_bytes(dm["word/document.xml"].encode("utf-8"))
        target = d / "delivered.xml"
    else:
        write_docx(d / "delivered.docx", dm)
        target = d / "delivered.docx"
    before = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in d.iterdir() if p.is_file()}
    cmd = PY + [str(script or SCRIPT), str(d / "paragraphs.json"), "--delivered", str(target),
                "--report-json", str(d / "r.json")]
    if original:
        cmd += ["--original", str(d / "orig.docx")]
    if strict:
        cmd.append("--strict")
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace",
                       env=ENV, cwd=str(ROOT))
    after = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in d.iterdir()
             if p.is_file() and p.name != "r.json"}
    rep = json.loads((d / "r.json").read_text(encoding="utf-8")) if (d / "r.json").is_file() else None
    UNCHANGED.append((name, before == after))
    return r, rep


def sides(rep):
    return (rep or {}).get("sides") or {}


def read(rep):
    return sides(rep).get("read") is True


def sf(rep, blocking=None):
    """The side findings as sorted (class, shape, part, id) tuples."""
    out = []
    for f in (rep or {}).get("findings", []):
        if str(f.get("class", "")).startswith("side-") and (blocking is None or f.get("blocking") == blocking):
            out.append((f["class"], f["shape"], f.get("part"), f.get("id")))
    return sorted(out, key=lambda t: tuple(str(x) for x in t))


def tally(rep, arm):
    return (sides(rep).get("counts") or {}).get(arm) or {}


def rc_of(r):
    return r.returncode


def swap(base, **changes):
    out = dict(base)
    for k, v in changes.items():
        name = k.replace("__", "/").replace("_xml", ".xml")
        if v is None:
            out.pop(name, None)
        else:
            out[name] = v
    return out


def with_members(base, members):
    out = dict(base)
    out.update(members)
    return out


def script_run(label, cmd):
    r = subprocess.run(PY + cmd, capture_output=True, text=True, encoding="utf-8", errors="replace",
                       env=ENV, cwd=str(ROOT))
    ok(f"{label} ran (rc={r.returncode})", r.returncode in (0, 1), (r.stdout + r.stderr)[-300:])
    return r


H1, F1, CMX, FNX, ENX, GLX = ("word/header1.xml", "word/footer1.xml", "word/comments.xml",
                              "word/footnotes.xml", "word/endnotes.xml", "word/glossary/document.xml")
FN_DECL, EN_DECL, GL_DECL = ("footnotes_translations.json", "endnotes_translations.json",
                             "glossary_translations.json")

print("=" * 96)
print(f"BRANCH 11 SLICES 3a AND 3b — the side-part arm of validate_apply --delivered --original  "
      f"[{SCRIPT.parent.parent.name}]")
print("=" * 96)

print("\n1  a clean document")
r, rep = case("clean", strict=True)
ok("the report was written", rep is not None, (r.stderr or r.stdout)[-300:])
ok("the side parts were READ", read(rep), str(sides(rep))[:300])
ok("five text-bearing side parts in the original — the page-number footer carries no letters — none missing",
   sorted(sides(rep).get("parts") or {}) == sorted([H1, CMX, FNX, ENX, GLX]) and not sides(rep).get("missing"),
   str(sides(rep).get("parts")))
ok("no finding of any kind, and --strict exits 0", rep is not None and not rep["findings"] and rc_of(r) == 0,
   f"rc={rc_of(r)} {rep and rep['findings']}")
ok("headers/footers: one filled entry exact, one null entry kept (the page-number footer)",
   tally(rep, "hf").get("filled exact") == 1 and tally(rep, "hf").get("null kept") == 1, str(tally(rep, "hf")))
ok("comments: one declared exact, one declared kept",
   tally(rep, "comments").get("declared exact") == 1 and tally(rep, "comments").get("declared kept") == 1,
   str(tally(rep, "comments")))
ok("footnote, endnote and glossary each changed from the source",
   all(tally(rep, k).get("changed") == 1 for k in ("footnotes", "endnotes", "glossary")),
   str({k: tally(rep, k) for k in ("footnotes", "endnotes", "glossary")}))

print("\n2  headers and footers with NO scaffold — a field placeholder is not prose")
r, rep = case("hf-undeclared", deliv=swap(DELIV, word__header1_xml=ORIG[H1]), hf=None)
ok("the header kept as the source's is ONE finding, undeclared-kept at its paragraph 0; the page-number "
   "footer is none", sf(rep) == [("side-hf", "undeclared-kept", H1, 0)], str(sf(rep)))
ok("...and the page-number footer is counted as carrying no letters",
   tally(rep, "hf").get("undeclared, no letters") == 1, str(tally(rep, "hf")))
prose_footer = ftr(P("Strona ", ("page",)))
r, rep = case("hf-footer-prose", orig=swap(ORIG, word__footer1_xml=prose_footer),
              deliv=swap(DELIV, word__header1_xml=ORIG[H1], word__footer1_xml=prose_footer), hf=None)
ok("a footer with PROSE beside its field, kept as the source's, IS a finding",
   sf(rep) == [("side-hf", "undeclared-kept", F1, 0), ("side-hf", "undeclared-kept", H1, 0)], str(sf(rep)))

print("\n3  a filled entry delivered as the source's")
r, rep = case("hf-declared-source", deliv=swap(DELIV, word__header1_xml=ORIG[H1]))
ok("declared-source at the header's paragraph 0", sf(rep) == [("side-hf", "declared-source", H1, 0)], str(sf(rep)))

print("\n4  entries declared KEPT")
kept_null = [dict(HF[0], en=None), HF[1]]
kept_same = [dict(HF[0], en=HF[0]["text"]), HF[1]]
r, rep = case("hf-null", deliv=swap(DELIV, word__header1_xml=ORIG[H1]), hf=kept_null)
ok("en null, delivered as the source's: quiet", sf(rep) == [] and tally(rep, "hf").get("null kept") == 2,
   f"{sf(rep)} {tally(rep, 'hf')}")
r, rep = case("hf-verbatim", deliv=swap(DELIV, word__header1_xml=ORIG[H1]), hf=kept_same)
ok("en == text, delivered as the source's: quiet", sf(rep) == [] and tally(rep, "hf").get("verbatim kept") == 1,
   f"{sf(rep)} {tally(rep, 'hf')}")
r, rep = case("hf-moved", hf=kept_null)
ok("a KEPT entry that changed in the delivery is moved", sf(rep) == [("side-hf", "moved", H1, 0)], str(sf(rep)))

print("\n5  at p_idx AND by text, reported apart")
two = hdr(P("Nagłówek umowy"), P("Druga linia"))
two_hf = [HF[0], {"idx": 2, "source": H1, "p_idx": 1, "text": "Druga linia", "en": "Second line"}, HF[1]]
r, rep = case("hf-elsewhere", orig=swap(ORIG, word__header1_xml=two),
              deliv=swap(DELIV, word__header1_xml=hdr(P("Second line"), P("Agreement header"))), hf=two_hf)
ok("each English found in the OTHER paragraph of the part is elsewhere",
   sf(rep) == [("side-hf", "elsewhere", H1, 0), ("side-hf", "elsewhere", H1, 1)], str(sf(rep)))
r, rep = case("hf-other", deliv=swap(DELIV, word__header1_xml=hdr(P("Something else entirely"))))
ok("an English found nowhere, the source not delivered either, is other",
   sf(rep) == [("side-hf", "other", H1, 0)], str(sf(rep)))

print("\n6  a scaffold entry that does not match the source at its p_idx")
r, rep = case("hf-misaligned", hf=[dict(HF[0], text="Inny tekst"), HF[1]])
ok("misaligned at the header's paragraph 0", sf(rep) == [("side-hf", "misaligned", H1, 0)], str(sf(rep)))

print("\n7  the header/footer script and a TRACKED DELETION — proved with the real script")
d7 = TMP / "hf-tc-real"
d7.mkdir(parents=True, exist_ok=True)
tc_hdr = hdr(P("Umowa ", ("del", "stara")))
write_docx(d7 / "orig.docx", swap(ORIG, word__header1_xml=tc_hdr))
script_run("--extract", [str(SCRIPTS / "translate_headers_footers.py"), str(d7 / "orig.docx"),
                         "--extract", str(d7 / "hf.json")])
scaffold = json.loads((d7 / "hf.json").read_text(encoding="utf-8")) if (d7 / "hf.json").is_file() else []
entry = next((e for e in scaffold if e.get("source") == H1), None)
ok("--extract offers the header paragraph WITHOUT its deleted text — the script never offers it",
   entry is not None and entry.get("text") == "Umowa " and "stara" not in json.dumps(scaffold, ensure_ascii=False),
   str(entry))
for e in scaffold:
    e["en"] = "Agreement " if e.get("source") == H1 else None
(d7 / "hf.json").write_bytes(json.dumps(scaffold, ensure_ascii=False).encode("utf-8"))
script_run("--apply", [str(SCRIPTS / "translate_headers_footers.py"), str(d7 / "orig.docx"), str(d7 / "out"),
                       "--apply", str(d7 / "hf.json")])
applied = (d7 / "out" / "word" / "header1.xml").read_bytes() if (d7 / "out" / "word" / "header1.xml").is_file() else b""
ok("--apply wrote the header, and its deleted text is still the SOURCE's", b"stara" in applied and b"Agreement" in applied,
   applied[:200])
r, rep = case("hf-tc-kept", orig=swap(ORIG, word__header1_xml=tc_hdr),
              deliv=with_members(DELIV, {H1: applied}), hf=scaffold)
ok("the check reports it: deleted-kept at the header's paragraph 0, and nothing else",
   sf(rep) == [("side-hf", "deleted-kept", H1, 0)], str(sf(rep)))
r, rep = case("hf-tc-emptied", orig=swap(ORIG, word__header1_xml=tc_hdr),
              deliv=swap(DELIV, word__header1_xml=hdr(P("Agreement "))), hf=scaffold)
ok("a delivery that EMPTIED the deleted text is deleted-emptied", sf(rep) == [("side-hf", "deleted-emptied", H1, 0)],
   str(sf(rep)))

print("\n8  the comment script and a TRACKED DELETION — proved with the real script")
d8 = TMP / "cm-tc-real"
d8.mkdir(parents=True, exist_ok=True)
tc_cm = comments({0: [P("Uwaga ", ("del", "usunięta"))], 1: [P("Keep this note")]})
write_docx(d8 / "orig.docx", swap(ORIG, word__comments_xml=tc_cm))
for label, decl in (("translated", {"0": "Remark ", "1": "Keep this note"}),
                    ("kept", {"0": "Uwaga ", "1": "Keep this note"})):
    (d8 / f"{label}.json").write_bytes(json.dumps(decl, ensure_ascii=False).encode("utf-8"))
    script_run(f"translate_comments ({label})", [str(SCRIPTS / "translate_comments.py"), str(d8 / "orig.docx"),
                                                str(d8 / label), "--translations", str(d8 / f"{label}.json")])
    out = (d8 / label / "word" / "comments.xml").read_bytes() if (d8 / label / "word" / "comments.xml").is_file() else b""
    ok(f"the script's output ({label}) no longer carries the deleted text", out and "usunięta".encode() not in out,
       out[:200])
    r, rep = case(f"cm-tc-{label}", orig=swap(ORIG, word__comments_xml=tc_cm), deliv=with_members(DELIV, {CMX: out}),
                  cm=decl)
    ok(f"the check reports deleted-emptied on comment 0, declared {label}, and nothing else",
       sf(rep) == [("side-comment", "deleted-emptied", CMX, "0")], str(sf(rep)))

print("\n9  a multi-paragraph comment through the real script — COUNTED, never blocking")
d9 = TMP / "cm-flat-real"
d9.mkdir(parents=True, exist_ok=True)
multi = comments({0: [P("Akapit pierwszy"), P("Akapit drugi")], 1: [P("Keep this note")]})
write_docx(d9 / "orig.docx", swap(ORIG, word__comments_xml=multi))
flat_decl = {"0": "Paragraph one\nParagraph two", "1": "Keep this note"}
(d9 / "t.json").write_bytes(json.dumps(flat_decl).encode("utf-8"))
script_run("translate_comments (two paragraphs)", [str(SCRIPTS / "translate_comments.py"), str(d9 / "orig.docx"),
                                                  str(d9 / "out"), "--translations", str(d9 / "t.json")])
flat = (d9 / "out" / "word" / "comments.xml").read_bytes() if (d9 / "out" / "word" / "comments.xml").is_file() else b""
r, rep = case("cm-flat", orig=swap(ORIG, word__comments_xml=multi), deliv=with_members(DELIV, {CMX: flat}),
              cm=flat_decl, strict=True)
ok("flattened on comment 0 is reported, NOT blocking, and nothing blocks",
   sf(rep, blocking=False) == [("side-comment", "flattened", CMX, "0")] and sf(rep, blocking=True) == [],
   str(sf(rep)))
ok("...its ruling is named, the report counts it, and --strict exits 0",
   rep is not None and [f.get("ruling") for f in rep["findings"] if f["class"] == "side-comment"] == ["flattened-comment"]
   and rep.get("counted") == 1 and rep.get("blocking") == 0 and rc_of(r) == 0,
   f"rc={rc_of(r)} {rep and (rep.get('counted'), rep.get('blocking'))}")
ok("...and the declared English itself arrived exact", tally(rep, "comments").get("declared exact") == 1,
   str(tally(rep, "comments")))

print("\n10  comments with no declaration")
r, rep = case("cm-undeclared", deliv=swap(DELIV, word__comments_xml=ORIG[CMX]), cm=None)
ok("both kept as the source's are undeclared-kept, one per id",
   sf(rep) == [("side-comment", "undeclared-kept", CMX, "0"), ("side-comment", "undeclared-kept", CMX, "1")],
   str(sf(rep)))

print("\n11  declared comments")
r, rep = case("cm-declared-source", deliv=swap(DELIV, word__comments_xml=ORIG[CMX]))
ok("declared translated and delivered as the source's is declared-source; the one declared kept is quiet",
   sf(rep) == [("side-comment", "declared-source", CMX, "0")], str(sf(rep)))

print("\n12  a comment absent from the delivery")
r, rep = case("cm-lost", deliv=swap(DELIV, word__comments_xml=comments({0: [P("First remark")]})))
ok("comment 1 is lost, and the body's reference to it is dangling",
   sf(rep) == [("side-comment", "lost", CMX, "1"), ("side-ref", "comment:dangling", None, "1")], str(sf(rep)))

print("\n13  footnotes and endnotes kept as the source's")
r, rep = case("notes-kept", deliv=swap(DELIV, word__footnotes_xml=ORIG[FNX], word__endnotes_xml=ORIG[ENX]))
ok("footnote 1 and endnote 1 are kept-source, and neither separator is examined",
   sf(rep) == [("side-endnote", "kept-source", ENX, "1"), ("side-footnote", "kept-source", FNX, "1")], str(sf(rep)))

print("\n14  glossary paragraphs kept as the source's")
g2 = glossary(P("Blok tekstu"), P("Drugi blok"))
r, rep = case("gl-kept", orig=swap(ORIG, word__glossary__document_xml=g2),
              deliv=swap(DELIV, word__glossary__document_xml=g2))
ok("kept-source on each of its two paragraphs",
   sf(rep) == [("side-glossary", "kept-source", GLX, 0), ("side-glossary", "kept-source", GLX, 1)], str(sf(rep)))

print("\n15  references by id in every part")
r, rep = case("ref-orphan", deliv=swap(DELIV, word__document_xml=body(P("Source one", ("cref", 0), ("cref", 1),
                                                                         ("eref", 1)))))
ok("a footnote the delivery holds and nothing points at is footnote:orphaned",
   sf(rep) == [("side-ref", "footnote:orphaned", None, "1")], str(sf(rep)))
r, rep = case("ref-dangling", deliv=swap(DELIV, word__document_xml=body(P("Source one", *REFS, ("cref", 7)))))
ok("a comment reference to an id nothing holds is comment:dangling",
   sf(rep) == [("side-ref", "comment:dangling", None, "7")], str(sf(rep)))
cm3 = comments({0: [P("Uwaga pierwsza")], 1: [P("Keep this note")], 2: [P("Sierota")]})
cm3d = comments({0: [P("First remark")], 1: [P("Keep this note")], 2: [P("Orphan")]})
r, rep = case("ref-inherited", orig=swap(ORIG, word__comments_xml=cm3), deliv=swap(DELIV, word__comments_xml=cm3d),
              cm=dict(CM, **{"2": "Orphan"}))
ok("an orphan the ORIGINAL already has is inherited: no finding",
   sf(rep) == [], str(sf(rep)))
ref_c = (sides(rep).get("refs") or {}).get("comment") or {}
ok("...and the report shows it on both sides", ref_c.get("orphaned") == [["2"], ["2"]], str(ref_c))

print("\n16  a text-bearing part the delivery lacks")
r, rep = case("part-missing", deliv=swap(DELIV, word__endnotes_xml=None))
ok("word/endnotes.xml is missing, reported ONCE, beside the reference it leaves dangling",
   sf(rep) == [("side-part", "missing", ENX, None), ("side-ref", "endnote:dangling", None, "1")], str(sf(rep)))

print("\n17  a text-bearing part outside Step 8's six kinds")
r, rep = case("part-outside", orig=with_members(ORIG, {"word/charts/chart1.xml": CHART}),
              deliv=with_members(DELIV, {"word/charts/chart1.xml": CHART}))
ok("a chart part delivered byte-identical is kept-source",
   sf(rep) == [("side-part", "kept-source", "word/charts/chart1.xml", None)], str(sf(rep)))

print("\n18  NOT READ is never a pass")
r, rep = case("not-read-xml", deliv_xml=True)
ok("a delivery given as document.xml: the side parts are NOT read, and the report says why",
   rep is not None and sides(rep).get("read") is False and "document.xml" in str(sides(rep).get("why")),
   str(sides(rep)))
r, rep = case("not-read-orig", original=False)
ok("no original: NOT read, and the report says so", rep is not None and sides(rep).get("read") is False
   and "original" in str(sides(rep).get("why")), str(sides(rep)))
ok("...and the printed report says NOT READ", "side parts: NOT READ" in r.stdout, r.stdout[-400:])

print("\n19  a partial install — the header/footer script's reader absent")
partial = TMP / "partial"
partial.mkdir(parents=True, exist_ok=True)
shutil.copyfile(SCRIPT, partial / "validate_apply.py")
r, rep = case("partial", script=partial / "validate_apply.py", strict=True)
ok("the missing reader is a NAMED finding, and the run exits 1 under --strict",
   sf(rep) == [("side-reader", "unavailable", None, "headers/footers")] and rc_of(r) == 1,
   f"rc={rc_of(r)} {sf(rep)}")
ok("...while the arms that need no reader still ran", all(tally(rep, k).get("changed") == 1
                                                          for k in ("footnotes", "endnotes", "glossary"))
   and tally(rep, "comments").get("declared exact") == 1,
   str({k: tally(rep, k) for k in ("comments", "footnotes", "endnotes", "glossary")}))

print("\n19b  the comment script's own reader returns ESCAPED text — proved with the real script")
d19 = TMP / "cm-escape-real"
d19.mkdir(parents=True, exist_ok=True)
amp = comments({0: [P("Uwaga pierwsza")], 1: [P("Terms &amp; conditions")]})
write_docx(d19 / "orig.docx", swap(ORIG, word__comments_xml=amp))
lst = script_run("translate_comments --list", [str(SCRIPTS / "translate_comments.py"), str(d19 / "orig.docx"),
                                               "--list"])
ok("--list shows the operator the comment ESCAPED — '&amp;', not the '&' Word displays",
   "[1] Terms &amp; conditions" in lst.stdout, lst.stdout[-200:])
esc = {"0": "First remark", "1": "Terms &amp; conditions"}          # copied from --list, as Step 8c says
(d19 / "t.json").write_bytes(json.dumps(esc).encode("utf-8"))
script_run("translate_comments (the copy)", [str(SCRIPTS / "translate_comments.py"), str(d19 / "orig.docx"),
                                            str(d19 / "out"), "--translations", str(d19 / "t.json")])
dbl = (d19 / "out" / "word" / "comments.xml").read_bytes() if (d19 / "out" / "word" / "comments.xml").is_file() else b""
ok("...and the script escapes that copy AGAIN", b"&amp;amp;" in dbl, dbl[:200])
r, rep = case("cm-escape", orig=swap(ORIG, word__comments_xml=amp), deliv=with_members(DELIV, {CMX: dbl}), cm=esc)
ok("the check reads the copy as a KEEP and reports the double escape as moved on comment 1, and nothing else",
   sf(rep) == [("side-comment", "moved", CMX, "1")], str(sf(rep)))
good = comments({0: [P("First remark")], 1: [P("Terms &amp; conditions")]})
r, rep = case("cm-amp-ok", orig=swap(ORIG, word__comments_xml=amp), deliv=swap(DELIV, word__comments_xml=good),
              cm={"0": "First remark", "1": "Terms & conditions"})
ok("while the same comment declared as Word shows it, and delivered once-escaped, is quiet — kept",
   sf(rep) == [] and tally(rep, "comments").get("declared kept") == 1, f"{sf(rep)} {tally(rep, 'comments')}")

print("\n20  a declaration that will not parse, or is the wrong shape; an entry that matches nothing")
r, rep = case("decl-unreadable", raw_hf=b"{not json")
ok("headers_footers.json unreadable is a finding, never read as no declaration",
   ("side-decl", "unreadable", None, "headers_footers.json") in sf(rep), str(sf(rep)))
r, rep = case("decl-shape", hf={"word/header1.xml": "Agreement header"}, cm=["First remark"])
ok("each declaration of the wrong JSON shape is a finding, wrong-shape, never read as no declaration",
   ("side-decl", "wrong-shape", None, "headers_footers.json") in sf(rep)
   and ("side-decl", "wrong-shape", None, "comments_translations.json") in sf(rep), str(sf(rep)))
stale = HF + [{"idx": 5, "source": H1, "p_idx": 7, "text": "Nic", "en": "Nothing"},
              {"idx": 6, "source": "word/header9.xml", "p_idx": 0, "text": "Nic", "en": "Nothing"}]
r, rep = case("hf-unmatched", hf=stale)
ok("an entry past the end of its part, and one naming a part neither file holds, are each unmatched",
   sf(rep) == [("side-hf", "unmatched", H1, 7), ("side-hf", "unmatched", "word/header9.xml", 0)], str(sf(rep)))

print("\n21  --strict")
r, rep = case("strict", deliv=swap(DELIV, word__header1_xml=ORIG[H1]), strict=True)
ok("a side finding under --strict exits 1", rc_of(r) == 1 and len(sf(rep)) == 1, f"rc={rc_of(r)} {sf(rep)}")
r, rep = case("advisory", deliv=swap(DELIV, word__header1_xml=ORIG[H1]))
ok("the same finding without --strict exits 0", rc_of(r) == 0 and len(sf(rep)) == 1, f"rc={rc_of(r)} {sf(rep)}")


def srt(xs):
    return sorted(xs, key=lambda t: tuple(str(x) for x in t))


KEPT_FN_EN = swap(DELIV, word__footnotes_xml=ORIG[FNX], word__endnotes_xml=ORIG[ENX])

print("\n22  SLICE 3b — footnotes and endnotes DECLARED KEPT are quiet")
r, rep = case("notes-declared-kept", deliv=KEPT_FN_EN, strict=True,
              extra={FN_DECL: {"Przypis jeden": "Przypis jeden"}, EN_DECL: {"Uwaga końcowa": "Uwaga końcowa"}})
ok("footnote 1 and endnote 1, every letter-bearing text mapped to itself, delivered as the source's: no "
   "finding, --strict exits 0", sf(rep) == [] and rc_of(r) == 0, f"rc={rc_of(r)} {sf(rep)}")
ok("...each counted as declared kept",
   tally(rep, "footnotes").get("declared kept") == 1 and tally(rep, "endnotes").get("declared kept") == 1,
   str({k: tally(rep, k) for k in ("footnotes", "endnotes")}))
decls = sides(rep).get("declarations") or {}
ok("...and the report says which declarations it read: the two notes files, one entry each, no glossary file",
   decls.get(FN_DECL) == 1 and decls.get(EN_DECL) == 1 and GL_DECL in decls and decls[GL_DECL] is None, str(decls))

print("\n23  an UNDECLARED note is still a finding, whatever else the file declares")
r, rep = case("notes-partly-declared", deliv=KEPT_FN_EN,
              extra={FN_DECL: {"Przypis jeden": "Przypis jeden"}, EN_DECL: {"Inny tekst": "Inny tekst"}})
ok("the footnote declared kept is quiet; the endnote, its text in no key, is kept-source",
   sf(rep) == [("side-endnote", "kept-source", ENX, "1")], str(sf(rep)))
two_runs = notes("footnote", {1: [P("Przypis ", "jeden")]})
r, rep = case("notes-one-run-declared", orig=swap(ORIG, word__footnotes_xml=two_runs),
              deliv=swap(DELIV, word__footnotes_xml=two_runs), extra={FN_DECL: {"Przypis ": "Przypis "}})
ok("a note of two runs with only one declared kept is kept-source — EVERY letter-bearing text must be",
   sf(rep) == [("side-footnote", "kept-source", FNX, "1")], str(sf(rep)))

print("\n24  a note DECLARED with English")
r, rep = case("notes-declared-source", deliv=swap(DELIV, word__footnotes_xml=ORIG[FNX]),
              extra={FN_DECL: {"Przypis jeden": "Footnote one"}})
ok("delivered as the source's, it is declared-source — the file was saved and the rewrite never ran",
   sf(rep) == [("side-footnote", "declared-source", FNX, "1")], str(sf(rep)))
r, rep = case("notes-declared-exact",
              extra={FN_DECL: {"Przypis jeden": "Footnote one"}, EN_DECL: {"Uwaga końcowa": "Final remark"}})
ok("delivered in that English, it is quiet", sf(rep) == [] and tally(rep, "footnotes").get("changed") == 1,
   f"{sf(rep)} {tally(rep, 'footnotes')}")

print("\n25  a note declared KEPT that changed")
r, rep = case("notes-moved", extra={FN_DECL: {"Przypis jeden": "Przypis jeden"}})
ok("is moved", sf(rep) == [("side-footnote", "moved", FNX, "1")], str(sf(rep)))

print("\n26  the glossary, paragraph by paragraph")
r, rep = case("gl-declared", orig=swap(ORIG, word__glossary__document_xml=g2),
              deliv=swap(DELIV, word__glossary__document_xml=g2), extra={GL_DECL: {"Blok tekstu": "Blok tekstu"}})
ok("paragraph 0 declared kept is quiet; paragraph 1, undeclared, is still kept-source",
   sf(rep) == [("side-glossary", "kept-source", GLX, 1)] and tally(rep, "glossary").get("declared kept") == 1,
   f"{sf(rep)} {tally(rep, 'glossary')}")
r, rep = case("gl-declared-source", orig=swap(ORIG, word__glossary__document_xml=g2),
              deliv=swap(DELIV, word__glossary__document_xml=g2),
              extra={GL_DECL: {"Blok tekstu": "Text block", "Drugi blok": "Second block"}})
ok("each declared with English and delivered as the source's is declared-source",
   sf(rep) == [("side-glossary", "declared-source", GLX, 0), ("side-glossary", "declared-source", GLX, 1)],
   str(sf(rep)))
r, rep = case("gl-moved", extra={GL_DECL: {"Blok tekstu": "Blok tekstu"}})
ok("a glossary paragraph declared kept that changed is moved", sf(rep) == [("side-glossary", "moved", GLX, 0)],
   str(sf(rep)))

print("\n27  a key as the template's regex sees it — ESCAPED — and as Word shows it")
amp_fn = notes("footnote", {1: [P("Warunki &amp; zasady")]})
for label, key in (("escaped", "Warunki &amp; zasady"), ("as-shown", "Warunki & zasady")):
    r, rep = case(f"notes-key-{label}", orig=swap(ORIG, word__footnotes_xml=amp_fn),
                  deliv=swap(DELIV, word__footnotes_xml=amp_fn), extra={FN_DECL: {key: key}})
    ok(f"declared kept with the key {label}: quiet",
       sf(rep) == [] and tally(rep, "footnotes").get("declared kept") == 1, f"{sf(rep)} {tally(rep, 'footnotes')}")

print("\n28  both readings: a note's DELETED text must be declared too")
tc_fn = notes("footnote", {1: [P("Przypis ", ("del", "stary"))]})
r, rep = case("notes-tc-declared", orig=swap(ORIG, word__footnotes_xml=tc_fn),
              deliv=swap(DELIV, word__footnotes_xml=tc_fn), extra={FN_DECL: {"Przypis ": "Przypis ", "stary": "stary"}})
ok("its text and its deleted text both declared kept: quiet", sf(rep) == [], str(sf(rep)))
r, rep = case("notes-tc-half", orig=swap(ORIG, word__footnotes_xml=tc_fn),
              deliv=swap(DELIV, word__footnotes_xml=tc_fn), extra={FN_DECL: {"Przypis ": "Przypis "}})
ok("its deleted text undeclared: kept-source", sf(rep) == [("side-footnote", "kept-source", FNX, "1")], str(sf(rep)))

print("\n29  a notes declaration that will not parse, or is not an object of strings")
r, rep = case("notes-decl-shape", deliv=swap(KEPT_FN_EN, word__glossary__document_xml=ORIG[GLX]),
              extra={FN_DECL: ["Przypis jeden"], EN_DECL: {"Uwaga końcowa": None}, GL_DECL: b"{not json"})
ok("a list and an object holding a null are wrong-shape, a file that will not parse is unreadable — and none "
   "is read as a declaration, so all three parts kept as the source's are still findings",
   sf(rep) == srt([("side-decl", "unreadable", None, GL_DECL), ("side-decl", "wrong-shape", None, EN_DECL),
                   ("side-decl", "wrong-shape", None, FN_DECL), ("side-endnote", "kept-source", ENX, "1"),
                   ("side-footnote", "kept-source", FNX, "1"), ("side-glossary", "kept-source", GLX, 0)]),
   str(sf(rep)))

print("\n30  a U+200B in the SOURCE, which repack's scrub removes from every side part, hides nothing")
Z = "\u200b"
z_orig = swap(ORIG, word__footnotes_xml=notes("footnote", {1: [P(f"Przypis{Z}jeden")]}),
              word__header1_xml=hdr(P(f"Nagłówek{Z}umowy")),
              word__comments_xml=comments({0: [P(f"Uwaga{Z}pierwsza")], 1: [P("Keep this note")]}),
              word__glossary__document_xml=glossary(P(f"Blok{Z}tekstu")))
z_deliv = swap(DELIV, word__footnotes_xml=notes("footnote", {1: [P("Przypisjeden")]}),
               word__header1_xml=hdr(P("Nagłówekumowy")),
               word__comments_xml=comments({0: [P("Uwagapierwsza")], 1: [P("Keep this note")]}),
               word__glossary__document_xml=glossary(P("Bloktekstu")))
r, rep = case("zwsp-undeclared", orig=z_orig, deliv=z_deliv, hf=None, cm=None)
ok("the footnote, header, comment and glossary paragraph, each the source's less its U+200B, are each "
   "reported as kept in the source's words",
   sf(rep) == srt([("side-comment", "undeclared-kept", CMX, "0"), ("side-comment", "undeclared-kept", CMX, "1"),
                   ("side-footnote", "kept-source", FNX, "1"), ("side-glossary", "kept-source", GLX, 0),
                   ("side-hf", "undeclared-kept", H1, 0)]), str(sf(rep)))
r, rep = case("zwsp-declared", orig=z_orig, deliv=z_deliv,
              hf=[dict(HF[0], text=f"Nagłówek{Z}umowy", en=None), HF[1]],
              cm={"0": f"Uwaga{Z}pierwsza", "1": "Keep this note"},
              extra={FN_DECL: {f"Przypis{Z}jeden": f"Przypis{Z}jeden"}, GL_DECL: {f"Blok{Z}tekstu": f"Blok{Z}tekstu"}})
ok("...and each, declared kept, is quiet — never moved", sf(rep) == [], str(sf(rep)))

print("\n31  Step 8d's and 8e's OWN TEMPLATES, run from the step document, write what the check reads")
doc8 = (ROOT / args.variant / "skill-docs" / "08-aux-and-quality.md").read_text(encoding="utf-8")


def template(heading):
    s = doc8.find(heading)
    a = doc8.find("```python\n", s) if s >= 0 else -1
    e = doc8.find("\n```", a + 1) if a >= 0 else -1
    return doc8[a + len("```python\n"):e + 1] if s >= 0 and a >= 0 and e > a else ""


t8d, t8e = template("#### Step 8d"), template("#### Step 8e")
ok("Step 8d's template loads its part's translations file, and Step 8e's the glossary's",
   "PART = 'footnotes'" in t8d and "_translations.json" in t8d and "glossary_translations.json" in t8e,
   f"8d={len(t8d)} 8e={len(t8e)}")
d31 = TMP / "templates-real"
(d31 / "final" / "word").mkdir(parents=True, exist_ok=True)
orig31 = swap(ORIG, word__document_xml=body(P("Zdroj jedna", *REFS, ("fref", 2))),
              word__footnotes_xml=notes("footnote", {1: [P("Przypis jeden")], 2: [P("Keep as is")]}))
write_docx(d31 / "orig.docx", orig31)
decl31 = {FN_DECL: {"Przypis jeden": "Footnote one", "Keep as is": "Keep as is"},
          EN_DECL: {"Inny tekst": "Other text"},                   # the endnote's own text LEFT OUT
          GL_DECL: {"Blok tekstu": "Text block"}}
for fname, content in decl31.items():
    (d31 / fname).write_bytes(json.dumps(content, ensure_ascii=False).encode("utf-8"))
for label, code in (("footnotes", t8d), ("endnotes", t8d.replace("PART = 'footnotes'", "PART = 'endnotes'")),
                    ("glossary", t8e)):
    src = code.replace("<original>.docx", (d31 / "orig.docx").as_posix()).replace("<workdir>", d31.as_posix())
    (d31 / f"run_{label}.py").write_bytes(src.encode("utf-8"))
    rr = script_run(f"the {label} template", [str(d31 / f"run_{label}.py")])
    ok(f"...and exited 0 — a template that raised is not one that ran", rr.returncode == 0,
       (rr.stdout + rr.stderr)[-300:])
wrote = {n: (d31 / "final" / "word" / f).read_bytes() if (d31 / "final" / "word" / f).is_file() else b""
         for n, f in ((FNX, "footnotes.xml"), (ENX, "endnotes.xml"), (GLX, "glossary-document.xml"))}
ok("...each wrote its part", all(wrote.values()), str({k: len(v) for k, v in wrote.items()}))
r, rep = case("templates", orig=orig31, extra=decl31,
              deliv=with_members(swap(DELIV, word__document_xml=body(P("Source one", *REFS, ("fref", 2)))), wrote))
ok("the declared English and the declared keep are quiet; the endnote whose text the file LEFT OUT shipped in "
   "the source's words and is reported, kept-source, and nothing else",
   sf(rep) == [("side-endnote", "kept-source", ENX, "1")], str(sf(rep)))
ok("...footnote 1 changed, footnote 2 declared kept, the glossary changed",
   tally(rep, "footnotes").get("changed") == 1 and tally(rep, "footnotes").get("declared kept") == 1
   and tally(rep, "glossary").get("changed") == 1, str({k: tally(rep, k) for k in ("footnotes", "glossary")}))

print("\n32  Step 8's wording, both trees")
for v in ("uk", "us"):
    s8 = (ROOT / v / "skill-docs" / "08-aux-and-quality.md").read_text(encoding="utf-8")
    s10 = (ROOT / v / "skill-docs" / "10-repack-and-validate.md").read_text(encoding="utf-8")
    ok(f"[{v}] 8b and 8d are MANDATORY whenever the part carries text, and no step document gates on "
       "source-language text any more (C7)",
       "#### Step 8b: Translate headers and footers — MANDATORY (whenever the part carries text)" in s8
       and "#### Step 8d: Translate footnotes / endnotes — MANDATORY (whenever the part carries text)" in s8
       and "if any source-language text" not in s8 and "contain source-language text)" not in s10)
    ok(f"[{v}] Step 8 names the three translations files", all(n in s8 for n in (FN_DECL, EN_DECL, GL_DECL)))

print("\n33  the check READS ONLY")
ok(f"every input file hashes the same after the run as before it, on every one of the {len(UNCHANGED)} cases above",
   len(UNCHANGED) >= 30 and all(same for _c, same in UNCHANGED),
   str([c for c, same in UNCHANGED if not same]))

print("\n34  no document text in the report")
canary_h, canary_c = "Zanzibarquux", "Quuxbarzan"
r, rep = case("canary", orig=swap(ORIG, word__header1_xml=hdr(P(canary_h + " nagłówek")),
                                  word__comments_xml=comments({0: [P(canary_c + " uwaga")], 1: [P("Keep this note")]})),
              deliv=swap(DELIV, word__header1_xml=hdr(P(canary_h + " nagłówek")),
                         word__comments_xml=comments({0: [P(canary_c + " uwaga")], 1: [P("Keep this note")]})),
              hf=None, cm=None)
ok("the run found both planted findings", len(sf(rep)) == 3, str(sf(rep)))
ok("...and printed neither canary", canary_h not in (r.stdout + r.stderr) and canary_c not in (r.stdout + r.stderr),
   r.stdout[-300:])

print("\n35  both trees")
blocks = []
for v in ("uk", "us"):
    t = (ROOT / v / "scripts" / "validate_apply.py").read_text(encoding="utf-8")
    s = t.find("# SLICE 3a, 2026-09-28")
    blocks.append(t[s:t.find("def check_delivered(", s)] if s >= 0 else "")
ok("the side block exists in both trees and is byte-identical",
   bool(blocks[0]) and blocks[0] == blocks[1], f"uk={len(blocks[0])} us={len(blocks[1])}")

shutil.rmtree(TMP, ignore_errors=True)
print("\n" + "=" * 96)
print(f"  {CHECKED} check(s), {len(FAIL)} failure(s)")
print("=" * 96)
sys.exit(1 if FAIL else 0)
