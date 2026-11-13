"""test_delivered_formatting.py - sub-step 16.1: the FORMATTING ARM of `validate_apply.py --delivered --original`.

REPORT ONLY, ON INVENTED DOCUMENTS. Step 11's check compares text; this arm compares each paired paragraph's
formatting with its source paragraph's (PLAN-2-step-b.md section 3.16). Every document here is invented and built in
a temporary directory; nothing is read from the corpus. What each arm asserts:

  1  THE THREE FP CONTROLS, each quiet: a paragraph bold by its STYLE delivered with no flag; a source switching its
     style's bold OFF, delivered with the flag; a uniform paragraph kept (a highlight, counted uniform-kept)
  2  bold and italic IN FORCE, a uniform source compared exactly: A12's shape (bold by style, delivered with an
     explicit off) uniform-lost; A11's (bold and italic, delivered bold) italic uniform-lost and bold quiet; a plain
     source delivered bold uniform-gained
  3  a mixed source by its count of spans (register C20): mixed-lost, mixed-spread, mixed-spans with both counts;
     the same count quiet
  4  the eleven direct properties: underline mixed-lost (A13, A14), highlight mixed-spread (A18), small capitals
     mixed-spread (A18), shading mixed-lost (A4), size uniform-changed, both sides mixed a count only
  5  A17's shape: a term bold by a CHARACTER STYLE, the style lost - rStyle mixed-lost and bold mixed-spans, the
     term bold by w:b beside it kept
  6  the PATH: rebuilt, tc (a tracked change on either side), same-text
  7  a delivery given as document.xml is read with the ORIGINAL's styles, and says so; a .docx delivery with its
     OWN styles part
  8  PAIRED AS THE TEXT ARM PAIRS: a permuted delivery attaches each finding to its own entry, and one whose every
     paragraph kept its formatting is quiet, as a positional pairing would not be; the arm pairs exactly the
     entries the text arm paired; a text naming two paragraphs formatted differently is AMBIGUOUS, never judged,
     and two formatted alike are judged
  9  REPORT ONLY: formatting findings never enter `findings`, the blocking or counted totals, or the exit code -
     with --strict a document with only formatting findings exits 0; one with a text finding exits 1 as it would
 10  NOT RUN, and said: no original given; extract_paragraphs.py missing (a partial install), the exit code the
     whole install's
 11  nothing printed or reported is a word of text, a style id or a property value
 12  the arm's block is byte-identical in both trees
 13  a run belongs to its NEAREST paragraph, as the journal's text contract says: a text box's runs are its own

    uv run --with lxml python tests/test_delivered_formatting.py
    uv run --with lxml python tests/test_delivered_formatting.py --variant us
    uv run --with lxml python tests/test_delivered_formatting.py --script <path>   # e.g. the pin's copy, for RED
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

ROOT = Path(__file__).resolve().parent.parent
ap = argparse.ArgumentParser()
ap.add_argument("--variant", choices=("uk", "us"), default="uk")
ap.add_argument("--script", default=None)
args = ap.parse_args()
SCRIPT = Path(args.script) if args.script else ROOT / args.variant / "scripts" / "validate_apply.py"
TMP = Path(tempfile.mkdtemp(prefix="s161-formatting-test-"))
ENV = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1", PYTHONDONTWRITEBYTECODE="1")
W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
FAIL, CHECKED = [], 0
# Needles nothing may print: a style id, a colour value, a word of the source and one of the English.
STYLE_NEEDLE, VALUE_NEEDLE, SRC_NEEDLE, EN_NEEDLE = "ZqHeadStyle", "C0FFEE", "Vorstrekking", "Undertaking"
STYLES = (f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:styles xmlns:w="{W}">'
          '<w:style w:type="paragraph" w:default="1" w:styleId="Normal"/>'
          f'<w:style w:type="paragraph" w:styleId="{STYLE_NEEDLE}"><w:basedOn w:val="Normal"/>'
          '<w:rPr><w:b/></w:rPr></w:style>'
          '<w:style w:type="character" w:styleId="BoldTerm"><w:rPr><w:b/></w:rPr></w:style>'
          '</w:styles>')


def ok(label, cond, detail=""):
    global CHECKED
    CHECKED += 1
    print(f"  {'OK  ' if cond else 'XX  '} {label}" + (f"   ({detail})" if detail and not cond else ""))
    if not cond:
        FAIL.append(label)


B, I, B0, I0 = "<w:b/>", "<w:i/>", '<w:b w:val="0"/>', '<w:i w:val="0"/>'
U, HL, SC = '<w:u w:val="single"/>', '<w:highlight w:val="yellow"/>', "<w:smallCaps/>"
SHD, CS = f'<w:shd w:val="clear" w:color="auto" w:fill="{VALUE_NEEDLE}"/>', '<w:rStyle w:val="BoldTerm"/>'


def r(text, rpr=""):
    return (f"<w:r>{'<w:rPr>' + rpr + '</w:rPr>' if rpr else ''}"
            f"<w:t xml:space=\"preserve\">{text}</w:t></w:r>")


def p(*runs, style=None):
    ppr = f'<w:pPr><w:pStyle w:val="{style}"/></w:pPr>' if style else ""
    return "<w:p>" + ppr + "".join(runs) + "</w:p>"


def ins(*runs):
    return '<w:ins w:id="1" w:author="x">' + "".join(runs) + "</w:ins>"


def doc(paras):
    return (f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            f'<w:document xmlns:w="{W}"><w:body>{"".join(paras)}</w:body></w:document>')


def text_of(par):
    """The paragraph's text as extraction reads it: every w:t, in order."""
    import re
    return "".join(re.findall(r'<w:t xml:space="preserve">([^<]*)</w:t>', par))


def write_docx(path, paras, styles=STYLES):
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("word/document.xml", doc(paras))
        z.writestr("word/styles.xml", styles)


def textbox(*runs):
    """A run holding a VML text box whose one paragraph holds `runs` - a paragraph inside a paragraph."""
    return ('<w:r><w:pict><v:shape xmlns:v="urn:schemas-microsoft-com:vml"><v:textbox><w:txbxContent>'
            + p(*runs) + "</w:txbxContent></v:textbox></v:shape></w:pict></w:r>")


def case(name, pairs, strict=False, deliv_xml=False, original=True, script=None, extra_src=(), extra_del=(),
         notes=None, deliv_styles=STYLES):
    """pairs: [(source paragraph, delivered paragraph)], one notes entry each - its text the source's, its en the
    delivery's. extra_src / extra_del: paragraphs on one side only."""
    d = TMP / name
    d.mkdir(parents=True, exist_ok=True)
    if notes is None:
        notes = [{"idx": i, "text": text_of(s), "en": text_of(t)} for i, (s, t) in enumerate(pairs)]
    (d / "paragraphs.json").write_bytes(json.dumps(notes).encode("utf-8"))
    src = [s for s, _ in pairs] + list(extra_src)
    dlv = [t for _, t in pairs] + list(extra_del)
    write_docx(d / "orig.docx", src)
    if deliv_xml:
        target = d / "document.xml"
        target.write_bytes(doc(dlv).encode("utf-8"))
    else:
        target = d / "delivered.docx"
        write_docx(target, dlv, deliv_styles)
    cmd = ["uv", "run", "--with", "lxml", "python", str(script or SCRIPT), str(d / "paragraphs.json"),
           "--delivered", str(target), "--report-json", str(d / "r.json")]
    if original:
        cmd += ["--original", str(d / "orig.docx")]
    if strict:
        cmd.append("--strict")
    res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", env=ENV,
                         cwd=str(ROOT))
    rep = json.loads((d / "r.json").read_text(encoding="utf-8")) if (d / "r.json").is_file() else None
    return res, rep


def fm(rep):
    return (rep or {}).get("formatting") or {}


def found(rep, prop=None, cls=None, path=None):
    return sorted((f["idx"], f["property"], f["class"], f["path"]) for f in fm(rep).get("findings") or []
                  if (prop is None or f["property"] == prop) and (cls is None or f["class"] == cls)
                  and (path is None or f["path"] == path))


def tally(rep, prop):
    return (fm(rep).get("tallies") or {}).get(prop) or {}


print("=" * 88)
print(f"SUB-STEP 16.1 — the formatting arm, on invented documents  [{SCRIPT.parent.parent.name}]")
print("=" * 88)

print("\n1  the three FP controls, each quiet")
res, rep = case("fp", [
    (p(r("Artikel een"), style=STYLE_NEEDLE), p(r("Article one"), style=STYLE_NEEDLE)),
    (p(r("Niet vet", B0), style=STYLE_NEEDLE), p(r("Not bold", B0), style=STYLE_NEEDLE)),
    (p(r("Gemarkeerd geheel", HL)), p(r("Highlighted whole", HL))),
])
ok("the arm ran, 3 paired and 3 compared", fm(rep).get("ran") is True and fm(rep).get("compared") == 3,
   f"{fm(rep)} {(res.stderr or res.stdout)[-300:]}")
ok("bold by its style, delivered with no flag: quiet at idx 0", not [f for f in found(rep) if f[0] == 0],
   str(found(rep)))
ok("a style's bold switched off, delivered with the flag: quiet at idx 1", not [f for f in found(rep) if f[0] == 1],
   str(found(rep)))
ok("a uniform highlight kept: quiet at idx 2, and counted uniform-kept", not [f for f in found(rep) if f[0] == 2]
   and tally(rep, "highlight") == {"uniform-kept": 1}, f"{found(rep)} {tally(rep, 'highlight')}")

print("\n2  bold and italic in force, a uniform source compared exactly")
res, rep = case("uniform", [
    (p(r("Kop twee"), style=STYLE_NEEDLE), p(r("Heading two", B0), style=STYLE_NEEDLE)),
    (p(r("Cel", B + I)), p(r("Cell", B + I0))),
    (p(r("Gewoon")), p(r("Plain", B))),
])
ok("A12's shape — bold by its style, delivered with an explicit off: bold uniform-lost at idx 0",
   found(rep, "bold", "uniform-lost") == [(0, "bold", "uniform-lost", "rebuilt")], str(found(rep)))
ok("A11's shape — bold and italic, delivered bold: italic uniform-lost at idx 1, its bold quiet",
   found(rep, "italic") == [(1, "italic", "uniform-lost", "rebuilt")]
   and not [f for f in found(rep, "bold") if f[0] == 1], str(found(rep)))
ok("a plain source delivered bold: bold uniform-gained at idx 2",
   found(rep, "bold", "uniform-gained") == [(2, "bold", "uniform-gained", "rebuilt")], str(found(rep)))

print("\n3  a mixed source by its count of spans (C20)")
res, rep = case("mixed", [
    (p(r("Term", B), r(" betekent")), p(r("Term means"))),
    (p(r("Term", B), r(" betekent")), p(r("Term means all", B))),
    (p(r("Alfa", B), r(" en "), r("Beta", B), r(" rest")), p(r("Alpha", B), r(" and Beta rest"))),
    (p(r("Gamma", B), r(" en "), r("Delta", B)), p(r("Gamma", B), r(" and "), r("Delta", B))),
    (p(r("Een", B), r(" "), r("Twee", B)), p(r("One Two", B))),
    (p(r("Aa", B), r("Bb", B), r(" rest")), p(r("AaBb", B), r(" remainder"))),
])
fs = {f["idx"]: f for f in fm(rep).get("findings") or [] if f["property"] == "bold"}
ok("delivered all off: bold mixed-lost at idx 0", (fs.get(0) or {}).get("class") == "mixed-lost", str(fs))
ok("delivered all on: bold mixed-spread at idx 1", (fs.get(1) or {}).get("class") == "mixed-spread", str(fs))
ok("two spans delivered as one: bold mixed-spans at idx 2, spans 2 -> 1",
   (fs.get(2) or {}).get("class") == "mixed-spans" and (fs[2]["source_spans"], fs[2]["delivered_spans"]) == (2, 1),
   str(fs))
ok("the same count of spans: quiet at idx 3", 3 not in fs, str(fs))
ok("a whitespace-only run is no run: bold either side of one space is uniform, quiet at idx 4", 4 not in fs,
   str(fs))
ok("a span is a maximal stretch: two bold runs side by side are ONE span, quiet at idx 5", 5 not in fs, str(fs))

print("\n4  the eleven direct properties")
res, rep = case("props", [
    (p(r("1.- "), r("Voorwerp", U)), p(r("1.- Subject"))),
    (p(r("Gewone kop "), r("staart", HL)), p(r("Plain heading tail", HL))),
    (p(r("PARTIJ", B + SC), r(" in haar hoedanigheid")), p(r("PARTY", B + SC), r(" in its capacity", SC))),
    (p(r("wit", SHD), r(" zwart")), p(r("white black"))),
    (p(r("Klein", '<w:sz w:val="20"/>')), p(r("Small", '<w:sz w:val="28"/>'))),
    (p(r("een", U), r(" twee"), r(" drie", U)), p(r("one", U), r(" two"), r(" three", U))),
    (p(r("Tint", SHD)), p(r("Tinted", '<w:shd w:val="clear" w:color="auto" w:fill="FFFFFF"/>'))),
    (p(r("Lettertype", '<w:rFonts w:ascii="Arial" w:hAnsi="Times"/>')),
     p(r("Typeface", '<w:rFonts w:ascii="Calibri" w:hAnsi="Times"/>'))),
])
ok("underline, an ordinal plain and a heading underlined, delivered plain: u mixed-lost (A13, A14)",
   found(rep, "u", "mixed-lost") == [(0, "u", "mixed-lost", "rebuilt")], str(found(rep)))
ok("a highlight on a tail phrase, delivered over the whole: highlight mixed-spread (A18)",
   found(rep, "highlight") == [(1, "highlight", "mixed-spread", "rebuilt")], str(found(rep)))
ok("small capitals on a name, delivered over the capacity phrase too: smallCaps mixed-spread (A18)",
   found(rep, "smallCaps") == [(2, "smallCaps", "mixed-spread", "rebuilt")], str(found(rep)))
ok("shading on one run, delivered on none: shd mixed-lost (A4); a fill changed, the pattern kept: uniform-changed",
   found(rep, "shd") == [(3, "shd", "mixed-lost", "rebuilt"), (6, "shd", "uniform-changed", "rebuilt")],
   str(found(rep)))
ok("fonts are their ascii face: one changed, the other face kept, rFonts uniform-changed at idx 7",
   found(rep, "rFonts") == [(7, "rFonts", "uniform-changed", "rebuilt")], str(found(rep)))
ok("one size everywhere, delivered at another: sz uniform-changed", found(rep, "sz") ==
   [(4, "sz", "uniform-changed", "rebuilt")], str(found(rep)))
ok("both sides mixed: a count only, never a finding",
   not [f for f in found(rep, "u") if f[0] == 5] and tally(rep, "u").get("mixed-other") == 1,
   f"{found(rep, 'u')} {tally(rep, 'u')}")

print("\n5  A17's shape: a term bold by a character style, the style lost")
res, rep = case("a17", [(p(r("Koper", B), r(" en de "), r("Verkoper", CS)), p(r("Buyer", B), r(" and the Seller")))])
ok("rStyle mixed-lost and bold mixed-spans at idx 0, the term bold by w:b kept",
   found(rep, "rStyle") == [(0, "rStyle", "mixed-lost", "rebuilt")]
   and found(rep, "bold") == [(0, "bold", "mixed-spans", "rebuilt")], str(found(rep)))

print("\n6  the path")
res, rep = case("path", [
    (p(r("Kop drie"), style=STYLE_NEEDLE), p(ins(r("Heading three", B0)), style=STYLE_NEEDLE)),
    (p(r("Zelfde", B)), p(r("Zelfde"))),
    (p(r("Kop vier"), style=STYLE_NEEDLE), p(r("Heading four", B0), style=STYLE_NEEDLE)),
])
ok("a tracked change on either side: tc; the text unchanged: same-text; otherwise rebuilt",
   found(rep, "bold") == [(0, "bold", "uniform-lost", "tc"), (1, "bold", "uniform-lost", "same-text"),
                          (2, "bold", "uniform-lost", "rebuilt")], str(found(rep)))

print("\n7  a delivery given as document.xml")
res, rep = case("xml", [(p(r("Kop vijf"), style=STYLE_NEEDLE), p(r("Heading five", B0), style=STYLE_NEEDLE)),
                        (p(r("Kop zes"), style=STYLE_NEEDLE), p(r("Heading six"), style=STYLE_NEEDLE))],
                deliv_xml=True)
ok("read with the original's styles, and the report says so; A12's shape still found, the kept one quiet",
   "original" in str(fm(rep).get("styles")) and found(rep, "bold") == [(0, "bold", "uniform-lost", "rebuilt")],
   f"{fm(rep).get('styles')} {found(rep)}")
plain_styles = STYLES.replace("<w:rPr><w:b/></w:rPr></w:style><w:style w:type=\"character\"",
                              "</w:style><w:style w:type=\"character\"", 1)
res, rep = case("own-styles", [(p(r("Kop zeven"), style=STYLE_NEEDLE), p(r("Heading seven"), style=STYLE_NEEDLE))],
                deliv_styles=plain_styles)
ok("a .docx delivery is read with ITS OWN styles part: its heading style made plain there, bold uniform-lost",
   plain_styles != STYLES and fm(rep).get("styles") == "each side its own"
   and found(rep, "bold") == [(0, "bold", "uniform-lost", "rebuilt")], f"{fm(rep).get('styles')} {found(rep)}")

print("\n8  paired as the text arm pairs")
pairs8 = [(p(r("Kop zeven"), style=STYLE_NEEDLE), p(r("Heading seven", B0), style=STYLE_NEEDLE)),
          (p(r("Gewoon acht")), p(r("Plain eight")))]
res, rep = case("permuted", [(pairs8[0][0], pairs8[1][1]), (pairs8[1][0], pairs8[0][1])],
                notes=[{"idx": 0, "text": "Kop zeven", "en": "Heading seven"},
                       {"idx": 1, "text": "Gewoon acht", "en": "Plain eight"}])
ok("a permuted delivery: the finding attaches to its own entry, idx 0, and idx 1 is quiet",
   found(rep) == [(0, "bold", "uniform-lost", "rebuilt")], str(found(rep)))
text_paired = sum((rep or {}).get("counts", {}).get(k, 0) for k in
                  ("exact", "collapsed", "edge-space", "inner-space", "readings", "changed"))
ok("the arm pairs exactly the entries the text arm paired", fm(rep).get("paired") == text_paired == 2,
   f"formatting {fm(rep).get('paired')}, text {text_paired}")
res, rep = case("permuted-quiet", [(p(r("Gewoon acht")), p(r("Heading seven"), style=STYLE_NEEDLE)),
                                   (p(r("Kop zeven"), style=STYLE_NEEDLE), p(r("Plain eight")))],
                notes=[{"idx": 0, "text": "Gewoon acht", "en": "Plain eight"},
                       {"idx": 1, "text": "Kop zeven", "en": "Heading seven"}])
ok("a permuted delivery whose every paragraph kept its formatting is quiet - paired by position it would not be",
   fm(rep).get("compared") == 2 and found(rep) == [], f"{fm(rep).get('compared')} {found(rep)}")
res, rep = case("missing", [(p(r("Gewoon negen")), p(r("Plain nine")))],
                notes=[{"idx": 0, "text": "Gewoon negen", "en": "Plain nine"},
                       {"idx": 1, "text": "Niet geleverd", "en": "Never delivered"}])
ok("an entry the text arm could not pair is not paired here either", fm(rep).get("paired") == 1
   and (rep or {}).get("counts", {}).get("missing") == 1, f"{fm(rep)} {(rep or {}).get('counts')}")
twin = p(r("Tweeling"))
res, rep = case("ambiguous", [(twin, p(r("Twin"))), (p(r("Tweeling", B)), p(r("Twin")))],
                notes=[{"idx": 0, "text": "Tweeling", "en": "Twin"}, {"idx": 1, "text": "Tweeling", "en": "Twin"}])
ok("one text naming two source paragraphs formatted differently: AMBIGUOUS, never judged",
   fm(rep).get("ambiguous") == 2 and not found(rep), f"{fm(rep)}")
res, rep = case("twins-alike", [(p(r("Tweeling", B)), p(r("Twin"))), (p(r("Tweeling", B)), p(r("Twin")))],
                notes=[{"idx": 0, "text": "Tweeling", "en": "Twin"}, {"idx": 1, "text": "Tweeling", "en": "Twin"}])
ok("two formatted alike: judged, both found", fm(rep).get("ambiguous") == 0
   and found(rep) == [(0, "bold", "uniform-lost", "rebuilt"), (1, "bold", "uniform-lost", "rebuilt")],
   f"{fm(rep).get('ambiguous')} {found(rep)}")

print("\n9  report only")
res, rep = case("strict-format-only", [(p(r("Kop tien"), style=STYLE_NEEDLE),
                                        p(r("Heading ten", B0), style=STYLE_NEEDLE))], strict=True)
ok("with --strict, formatting findings alone exit 0, and none enters findings, blocking or counted",
   res.returncode == 0 and found(rep) and rep["findings"] == [] and rep["blocking"] == 0 and rep["counted"] == 0,
   f"rc={res.returncode} {rep and (rep['findings'], rep['blocking'], rep['counted'])}")
ok("...and the closing line is the text arm's PASSED", "PASSED: every declared paragraph" in res.stdout,
   res.stdout[-300:])
res, rep = case("strict-text", [(p(r("Kop elf"), style=STYLE_NEEDLE), p(r("Heading 11", B0), style=STYLE_NEEDLE))],
                strict=True, notes=[{"idx": 0, "text": "Kop elf", "en": "Heading eleven"}])
ok("a text finding beside it: exit 1, blocking 1 - as without the arm",
   res.returncode == 1 and rep is not None and rep["blocking"] == 1, f"rc={res.returncode}")

print("\n10  NOT RUN, and said")
res, rep = case("no-original", [(p(r("Kop twaalf"), style=STYLE_NEEDLE),
                                 p(r("Heading twelve", B0), style=STYLE_NEEDLE))], original=False)
ok("no original: NOT RUN, the reason in the report and on the page",
   fm(rep).get("ran") is False and "no original" in str(fm(rep).get("why")) and "NOT RUN" in res.stdout,
   f"{fm(rep)} {res.stdout[-200:]}")
partial = TMP / "partial"               # the whole scripts folder but extract_paragraphs.py: that one sibling missing
shutil.copytree(SCRIPT.parent, partial, ignore=shutil.ignore_patterns("__pycache__"))
(partial / "extract_paragraphs.py").unlink()
shutil.copyfile(SCRIPT, partial / "validate_apply.py")
pair10 = [(p(r("Kop dertien"), style=STYLE_NEEDLE), p(r("Heading thirteen", B0), style=STYLE_NEEDLE))]
whole, _rw = case("whole-install", pair10, strict=True)
res, rep = case("partial-install", pair10, strict=True, script=partial / "validate_apply.py")
ok("extract_paragraphs.py missing: NOT RUN and named, no traceback",
   fm(rep).get("ran") is False and "extract_paragraphs.py" in str(fm(rep).get("why"))
   and "Traceback" not in res.stdout + res.stderr, f"{fm(rep)} {(res.stderr or '')[-200:]}")
ok("...and the exit code is the whole install's", res.returncode == whole.returncode,
   f"partial {res.returncode}, whole {whole.returncode}")

print("\n11  nothing printed or reported is text, a style id or a value")
res, rep = case("needles", [(p(r(SRC_NEEDLE + " een", SHD), r(" twee"), style=STYLE_NEEDLE),
                             p(r(EN_NEEDLE + " one two", B0), style=STYLE_NEEDLE))])
blob = res.stdout + res.stderr + json.dumps(fm(rep))
ok("the planted control: the arm found something to report here", bool(found(rep)), str(found(rep)))
ok("no word of the source or the English, no style id, no property value",
   not any(n in blob for n in (SRC_NEEDLE, EN_NEEDLE, STYLE_NEEDLE, VALUE_NEEDLE)),
   str([n for n in (SRC_NEEDLE, EN_NEEDLE, STYLE_NEEDLE, VALUE_NEEDLE) if n in blob]))

print("\n13  a run belongs to its NEAREST paragraph - a text box's runs are the text box's")
res, rep = case("textbox", [(p(r("Buiten"), textbox(r("Doos", B))), p(r("Outside"), textbox(r("Box"))))],
                notes=[{"idx": 0, "text": "BuitenDoos", "en": "Outside"}, {"idx": 1, "text": "Doos", "en": "Box"}])
ok("the text box's bold lost is found at ITS paragraph, idx 1, and the outer paragraph is quiet",
   fm(rep).get("compared") == 2 and found(rep) == [(1, "bold", "uniform-lost", "rebuilt")],
   f"{fm(rep).get('compared')} {found(rep)}")

print("\n12  the arm's block is byte-identical in both trees")
blocks = []
for tree in ("uk", "us"):
    t = (ROOT / tree / "scripts" / "validate_apply.py").read_bytes().decode("utf-8")
    a, b = t.find("# THE FORMATTING ARM"), t.find("def check_delivered(")
    blocks.append(t[a:b] if 0 <= a < b else None)
ok("uk and us carry the same formatting arm", blocks[0] is not None and blocks[0] == blocks[1],
   "missing or different")

shutil.rmtree(TMP, ignore_errors=True)
print("\n" + "=" * 88)
print(f"  {CHECKED} check(s), {len(FAIL)} failure(s)")
print("=" * 88)
sys.exit(1 if FAIL else 0)
