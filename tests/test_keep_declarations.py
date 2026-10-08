"""test_keep_declarations.py - branch 11's follow-up, item 1 (register I-34) and review finding 6: the ONE helper
that writes what a compliant KEEP-AS-IS run declares beside the notes, tools/keep_declarations.py, judged by the
REAL delivered-document check. Synthetic input only; nothing is read from the corpus.

The original carries every side part the check reads: a header with a PAGE field, a footer whose text holds an
escaped ampersand, a comment of two paragraphs and a comment of one text paragraph beside a whitespace-only one,
a footnote holding a tracked deletion and a letter-free text, an endnote, and a glossary building block.

  D1  the declarations written, file by file, each in Step 8's form: 8b the script's own --extract scaffold with
      en equal to text, the field placeholder kept; 8c a comment's text paragraphs joined by a line break, a
      one-paragraph comment as every w:t of it; 8d/8e every letter-bearing w:t AND w:delText text as the raw XML
      holds it (`&amp;` stays escaped) mapped to itself, a letter-free text absent.
  D2  the original delivered as itself with the declarations beside the notes: the REAL check (validate_apply.py
      --delivered --original --strict) blocks NOTHING, and its own tally reads every side part as kept.
  D3  CONTROL, the same delivery with NO declaration: the check blocks, in every one of the five side-part kinds.
  D4  a declaration is not a blanket pass: a delivery that CHANGED a kept footnote and a kept comment reads
      side-footnote/moved and side-comment/moved, blocking.
  D5  kinds= narrows what is written; an unknown kind is refused, never ignored.
  D6  an original with no letter-bearing side text gets no file at all.

RED FIRST: at fa0a110 tools/keep_declarations.py does not exist, so D1, D2, D4, D5 and D6 fail; D3 is a PIN of
the check and is green there as here.

    uv run --with lxml python tests/test_keep_declarations.py
    uv run --with lxml python tests/test_keep_declarations.py --variant us
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
os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(ROOT / "tools"))
from make_fixtures import R, W, docx, p, r  # noqa: E402

try:
    from keep_declarations import write_keep_declarations  # noqa: E402
except ImportError as exc:                          # the RED-FIRST state: reported as a failure, never a crash
    write_keep_declarations, IMPORT_ERROR = None, exc
else:
    IMPORT_ERROR = None

ap = argparse.ArgumentParser()
ap.add_argument("--variant", choices=("uk", "us"), default="uk")
args = ap.parse_args()
SCRIPTS = ROOT / args.variant / "scripts"
TMP = Path(tempfile.mkdtemp(prefix="keep-decl-test-"))
ENV = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1", PYTHONDONTWRITEBYTECODE="1")
FAIL, CHECKED = [], 0


def ok(label, cond, detail=""):
    global CHECKED
    CHECKED += 1
    print(f"  {'OK  ' if cond else 'XX  '} {label}" + (f"   ({detail})" if detail and not cond else ""))
    if not cond:
        FAIL.append(label)


# ---------------------------------------------------------------------------------------------------------
# THE ORIGINAL — every side part the check reads, each with letter-bearing text. German, invented.
# ---------------------------------------------------------------------------------------------------------
BODY = (p(r("Die Parteien vereinbaren Folgendes."), '<w:r><w:footnoteReference w:id="1"/></w:r>')
        + '<w:p><w:commentRangeStart w:id="1"/>' + r("Jede Mitteilung bedarf der Schriftform.")
        + '<w:commentRangeEnd w:id="1"/><w:r><w:commentReference w:id="1"/></w:r></w:p>'
        + '<w:p><w:commentRangeStart w:id="2"/>' + r("Dieser Vertrag tritt in Kraft.")
        + '<w:commentRangeEnd w:id="2"/><w:r><w:commentReference w:id="2"/></w:r>'
        + '<w:r><w:endnoteReference w:id="1"/></w:r></w:p>')
XMLDECL = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
HEADER = (f'{XMLDECL}<w:hdr {W} {R}>' + p(r("Vertraulich"))
          + '<w:p>' + r("Seite ") + '<w:r><w:fldChar w:fldCharType="begin"/></w:r>'
          '<w:r><w:instrText xml:space="preserve"> PAGE </w:instrText></w:r>'
          '<w:r><w:fldChar w:fldCharType="separate"/></w:r>' + r("1")
          + '<w:r><w:fldChar w:fldCharType="end"/></w:r></w:p></w:hdr>')
FOOTER = f'{XMLDECL}<w:ftr {W} {R}>' + p(r("Entwurf &amp; Fassung")) + '</w:ftr>'
COMMENTS = (f'{XMLDECL}<w:comments {W}>'
            '<w:comment w:id="1" w:author="Pruefer" w:date="2020-01-01T00:00:00Z">'
            + p(r("Bitte prüfen.")) + p(r("Zweite Zeile.")) + '</w:comment>'
            '<w:comment w:id="2" w:author="Pruefer" w:date="2020-01-01T00:00:00Z">'
            + p(r("Nur eine Anmerkung.")) + p(r(" ")) + '</w:comment></w:comments>')
SEPARATORS = ('<w:{k} w:type="separator" w:id="-1"><w:p><w:r><w:separator/></w:r></w:p></w:{k}>'
              '<w:{k} w:type="continuationSeparator" w:id="0"><w:p><w:r><w:continuationSeparator/></w:r></w:p></w:{k}>')
FOOTNOTES = (f'{XMLDECL}<w:footnotes {W}>' + SEPARATORS.format(k="footnote")
             + '<w:footnote w:id="1"><w:p>' + r("Fußnote mit Text &amp; mehr ")
             + '<w:del w:id="9" w:author="Pruefer" w:date="2020-01-01T00:00:00Z"><w:r>'
               '<w:delText xml:space="preserve">gestrichen</w:delText></w:r></w:del>'
             + r(" 1.") + '</w:p></w:footnote></w:footnotes>')
ENDNOTES = (f'{XMLDECL}<w:endnotes {W}>' + SEPARATORS.format(k="endnote")
            + '<w:endnote w:id="1">' + p(r("Endnotentext.")) + '</w:endnote></w:endnotes>')
GLOSSARY = (f'{XMLDECL}<w:glossaryDocument {W}><w:docParts><w:docPart><w:docPartPr>'
            '<w:name w:val="Platzhalter"/></w:docPartPr><w:docPartBody>' + p(r("Klicken Sie hier."))
            + '</w:docPartBody></w:docPart></w:docParts></w:glossaryDocument>')
CT = "".join(f'<Override PartName="/word/{n}" ContentType="application/vnd.openxmlformats-officedocument.'
             f'wordprocessingml.{t}+xml"/>\n'
             for n, t in (("header1.xml", "header"), ("footer1.xml", "footer"), ("comments.xml", "comments"),
                          ("footnotes.xml", "footnotes"), ("endnotes.xml", "endnotes"),
                          ("glossary/document.xml", "document.glossary")))
SIDE = {"word/header1.xml": HEADER, "word/footer1.xml": FOOTER, "word/comments.xml": COMMENTS,
        "word/footnotes.xml": FOOTNOTES, "word/endnotes.xml": ENDNOTES, "word/glossary/document.xml": GLOSSARY}


def stage(name, side=SIDE):
    """The original and its notes in a folder of their own: extraction's own text, `en` equal to it."""
    d = TMP / name
    d.mkdir()
    orig = d / "orig.docx"
    docx(orig, BODY, side, CT)
    ext = d / "extracted.json"
    x = subprocess.run([sys.executable, str(SCRIPTS / "extract_paragraphs.py"), str(orig), str(ext)],
                       capture_output=True, env=ENV)
    if x.returncode != 0 or not ext.is_file():
        print(f"VOID — extraction failed on the synthetic original (exit {x.returncode}). Nothing judged.")
        shutil.rmtree(TMP, ignore_errors=True)
        sys.exit(3)
    notes = [dict(n, en=n["text"]) for n in json.loads(ext.read_text(encoding="utf-8"))]
    (d / "paragraphs.json").write_bytes(json.dumps(notes, ensure_ascii=False).encode("utf-8"))
    return d, orig


def check(d, delivered, orig):
    """The REAL delivered-document check, as repack runs it: (rc, report or None)."""
    rep = d / "report.json"
    if rep.exists():
        rep.unlink()
    res = subprocess.run([sys.executable, str(SCRIPTS / "validate_apply.py"), str(d / "paragraphs.json"),
                          "--delivered", str(delivered), "--original", str(orig), "--strict",
                          "--report-json", str(rep)],
                         capture_output=True, text=True, encoding="utf-8", errors="replace", env=ENV)
    return res.returncode, (json.loads(rep.read_text(encoding="utf-8")) if rep.is_file() else None)


def side_blocking(report):
    return sorted({(f["class"], f["shape"]) for f in (report or {}).get("findings", [])
                   if f.get("blocking", True) and str(f.get("class", "")).startswith("side-")})


def changed_copy(orig, out, edits):
    """A delivery that is the original with `edits` {member: (old bytes, new bytes)} applied -- a
    create-and-write of a new file, never a rename."""
    with zipfile.ZipFile(orig) as zin, zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            data = zin.read(item.filename)
            if item.filename in edits:
                old, new = edits[item.filename]
                assert data.count(old) == 1, f"{item.filename}: the edit's anchor is not there exactly once"
                data = data.replace(old, new)
            zout.writestr(item, data)
    return out


def read(d, name):
    f = d / name
    return json.loads(f.read_text(encoding="utf-8")) if f.is_file() else None


print("=" * 92)
print(f"KEEP DECLARATIONS — tools/keep_declarations.py, judged by the real delivered check  [{args.variant}]")
print("=" * 92)
ok("tools/keep_declarations.py imports and offers write_keep_declarations",
   write_keep_declarations is not None, repr(IMPORT_ERROR))

print("\nD1  the declarations written, each in Step 8's form")
d1, o1 = stage("d1")
wrote = write_keep_declarations(o1, d1, SCRIPTS) if write_keep_declarations else {}
ok("five files written, one per side-part kind the original carries",
   sorted(wrote) == sorted(["headers_footers.json", "comments_translations.json", "footnotes_translations.json",
                            "endnotes_translations.json", "glossary_translations.json"]), str(wrote))
hf = read(d1, "headers_footers.json") or []
ok("8b: the script's own scaffold, every entry with en equal to text",
   bool(hf) and all(e.get("en") == e.get("text") for e in hf), str(hf)[:300])
ok("8b: ...the header's field kept as its placeholder, the footer's ampersand as Word shows it",
   {e.get("text") for e in hf} == {"Vertraulich", "Seite <<PAGE>>", "Entwurf & Fassung"},
   str([e.get("text") for e in hf]))
cm = read(d1, "comments_translations.json") or {}
ok("8c: a two-paragraph comment declared as its paragraphs joined by a line break",
   cm.get("1") == "Bitte prüfen.\nZweite Zeile.", repr(cm.get("1")))
ok("8c: a one-text-paragraph comment declared as every w:t of it, the whitespace paragraph included",
   cm.get("2") == "Nur eine Anmerkung. ", repr(cm.get("2")))
fn = read(d1, "footnotes_translations.json") or {}
ok("8d: every letter-bearing w:t AND w:delText, escaped as the raw XML holds it, mapped to itself",
   fn == {"Fußnote mit Text &amp; mehr ": "Fußnote mit Text &amp; mehr ", "gestrichen": "gestrichen"},
   str(fn))
ok("8d: the endnote the same way", read(d1, "endnotes_translations.json") == {"Endnotentext.": "Endnotentext."})
ok("8e: the glossary the same way", read(d1, "glossary_translations.json") == {"Klicken Sie hier.": "Klicken Sie hier."})
ok("the returned counts are the entries written",
   wrote.get("headers_footers.json") == len(hf) and wrote.get("comments_translations.json") == len(cm)
   and wrote.get("footnotes_translations.json") == len(fn), str(wrote))

print("\nD2  delivered as itself, the declarations beside the notes: the real check blocks nothing")
rc2, rep2 = check(d1, o1, o1)
ok("the check exits 0 and blocks no side part", rc2 == 0 and rep2 is not None and not side_blocking(rep2),
   f"rc={rc2} {side_blocking(rep2)}")
counts = ((rep2 or {}).get("sides") or {}).get("counts") or {}
ok("...and its own tally reads every kind as KEPT: headers/footers 3 verbatim, comments 2, footnote 1, "
   "endnote 1, glossary 1",
   counts.get("hf", {}).get("verbatim kept") == 3 and counts.get("comments", {}).get("declared kept") == 2
   and counts.get("footnotes", {}).get("declared kept") == 1
   and counts.get("endnotes", {}).get("declared kept") == 1
   and counts.get("glossary", {}).get("declared kept") == 1, str(counts))

print("\nD3  CONTROL: the same delivery with no declaration blocks, in all five kinds")
d3, o3 = stage("d3")
rc3, rep3 = check(d3, o3, o3)
kinds3 = {c for c, _s in side_blocking(rep3)}
ok("the check exits 1", rc3 == 1, f"rc={rc3}")
ok("...blocking in side-hf, side-comment, side-footnote, side-endnote and side-glossary",
   {"side-hf", "side-comment", "side-footnote", "side-endnote", "side-glossary"} <= kinds3, str(sorted(kinds3)))

print("\nD4  a declaration is not a blanket pass: a CHANGED kept text reads moved")
moved = changed_copy(o1, d1 / "moved.docx", {
    "word/footnotes.xml": ("Fußnote mit Text".encode("utf-8"), "Fußnote geändert".encode("utf-8")),
    "word/comments.xml": (b"Zweite Zeile.", b"Andere Zeile.")})
rc4, rep4 = check(d1, moved, o1)
ok("the check exits 1 with side-footnote/moved and side-comment/moved",
   rc4 == 1 and {("side-footnote", "moved"), ("side-comment", "moved")} <= set(side_blocking(rep4)),
   f"rc={rc4} {side_blocking(rep4)}")

print("\nD5  kinds= narrows what is written, and an unknown kind is refused")
d5, o5 = stage("d5")
got5 = write_keep_declarations(o5, d5, SCRIPTS, kinds={"glossary"}) if write_keep_declarations else None
ok("kinds={'glossary'} writes the glossary's file and nothing else",
   got5 == {"glossary_translations.json": 1}
   and sorted(x.name for x in d5.glob("*_translations.json")) == ["glossary_translations.json"]
   and not (d5 / "headers_footers.json").exists(), str(got5))
refused = False
if write_keep_declarations is not None:
    try:
        write_keep_declarations(o5, d5, SCRIPTS, kinds={"glossaries"})
    except ValueError:
        refused = True
ok("an unknown kind raises ValueError", refused)

print("\nD6  no letter-bearing side text, no file")
d6, o6 = stage("d6", side={"word/comments.xml": COMMENTS.replace("Bitte prüfen.", "1.")
                           .replace("Zweite Zeile.", "2.").replace("Nur eine Anmerkung.", "3.")})
got6 = write_keep_declarations(o6, d6, SCRIPTS) if write_keep_declarations else None
ok("an original whose only side part carries no letter gets no declaration file",
   got6 == {} and not list(d6.glob("*_translations.json")) and not (d6 / "headers_footers.json").exists(),
   str(got6))

shutil.rmtree(TMP, ignore_errors=True)
print()
print("=" * 92)
if FAIL:
    print(f"FAIL — {len(FAIL)} of {CHECKED} checks:")
    for f in FAIL:
        print(f"  ·  {f}")
    print("=" * 92)
    sys.exit(1)
print(f"PASS — {CHECKED} checks.")
print("=" * 92)
