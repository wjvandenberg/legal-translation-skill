"""test_per_span_properties.py - sub-step 16.5: the other properties, per span (PLAN-2-step-b.md section 3.16).

ON INVENTED DOCUMENTS ONLY, built in a temporary directory. Each document is put through the tree's own
extract_paragraphs.py, an operator's English added, the read receipt filed, and the tree's apply run over it; each
delivered run's direct properties are then read, and its bold and italic in force by extraction's resolver over the
document's own styles. What each arm asserts:

  1  TP, the container template: a paragraph whose every text run sits inside a hyperlink and shares a character
     style and small capitals - the English keeps both (before 16.5 it found no template and dropped them)
  2  TP, per declared span: a bold term underlined beside plain text, declared [bold, plain] - the underline on the
     bold span only, never spread over the plain one
  3  TP, A5: a template run in a symbol font - the English carries no symbol font, its other properties kept
  4  FP, a property mixed WITHIN one emphasis state (two plain runs, one highlighted) - as before 16.5: the
     template's value on every span, nothing matched
  5  FP, a uniform paragraph - its shared size and font kept exactly as before
  6  bold and italic in force exactly as declared in every arm (16.5 must not move them), including where a span's
     character style changes what the styles give
  7  A17's shape: a term in a bold character style beside plain text, declared [plain, bold, plain] - the style on
     the term's span only, and no bold flag on any span, since the styles now give each exactly what is declared
  8  a declared state the source never shows (an italic span over a source with no italic) - nothing per span: the
     template on every span, as before
  9  A5 per span: a bold span whose source runs are in a symbol font - no symbol font on it, the plain span's font kept
  10 a whitespace-only declared span in a state the source never shows, among spans that do follow emphasis -
     delivered, that blank span keeping the template's value, the others per span

RED FIRST: against 16.4's scripts (--scripts, the pin) arms 1, 2, 3 and 7 fail. Prints booleans and the invented
documents' own words - never anything from a real document.

    uv run --with lxml python tests/test_per_span_properties.py
    uv run --with lxml python tests/test_per_span_properties.py --variant us
    uv run --with lxml python tests/test_per_span_properties.py --scripts <folder>   # e.g. the pin's, for RED
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
ap.add_argument("--scripts", default=None)
args = ap.parse_args()
SCRIPTS = Path(args.scripts) if args.scripts else ROOT / args.variant / "scripts"
sys.path.insert(0, str(ROOT / "tests"))
from read_receipt import file_receipt  # noqa: E402
sys.path.insert(0, str(ROOT / args.variant / "scripts"))
from lxml import etree  # noqa: E402
import extract_paragraphs as XP  # noqa: E402   (the reader: always today's, so a red is the writer's)

TMP = Path(tempfile.mkdtemp(prefix="s165-span-test-"))
ENV = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1", PYTHONDONTWRITEBYTECODE="1")
W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
RNS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
FAIL, CHECKED = [], 0
NEEDLE = "Numbatia"
STYLES = (f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:styles xmlns:w="{W}">'
          '<w:style w:type="paragraph" w:default="1" w:styleId="Normal"/>'
          '<w:style w:type="character" w:styleId="LinkZq"><w:rPr><w:color w:val="0563C1"/><w:u w:val="single"/>'
          '</w:rPr></w:style>'
          '<w:style w:type="character" w:styleId="TermZq"><w:rPr><w:b/></w:rPr></w:style>'
          '</w:styles>')
RELS = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" '
        'Target="styles.xml"/>'
        '<Relationship Id="rId9" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink" '
        'Target="https://example.invalid/" TargetMode="External"/></Relationships>')


def ok(label, cond, detail=""):
    global CHECKED
    CHECKED += 1
    print(f"  {'OK  ' if cond else 'XX  '} {label}" + (f"   ({detail})" if detail and not cond else ""))
    if not cond:
        FAIL.append(label)


def r(text, rpr=""):
    return f"<w:r>{'<w:rPr>' + rpr + '</w:rPr>' if rpr else ''}<w:t xml:space=\"preserve\">{text}</w:t></w:r>"


def p(*runs):
    return "<w:p>" + "".join(runs) + "</w:p>"


def link(*runs):
    return f'<w:hyperlink r:id="rId9">' + "".join(runs) + "</w:hyperlink>"


def write_docx(path, paras):
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("word/document.xml", f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                                         f'<w:document xmlns:w="{W}" xmlns:r="{RNS}"><w:body>{"".join(paras)}'
                                         f'</w:body></w:document>')
        z.writestr("word/_rels/document.xml.rels", RELS)
        z.writestr("word/styles.xml", STYLES)
    return path


def run_doc(name, paras, en, en_runs=None):
    d = TMP / name
    d.mkdir()
    src = write_docx(d / "src.docx", paras)
    notes_path = d / "paragraphs.json"
    subprocess.run(["uv", "run", "--with", "lxml", "python", str(ROOT / args.variant / "scripts" /
                                                                "extract_paragraphs.py"), str(src), str(notes_path)],
                   capture_output=True, text=True, encoding="utf-8", errors="replace", env=ENV, timeout=600)
    notes = json.loads(notes_path.read_text(encoding="utf-8"))
    for e in notes:
        e["en"] = en[e["idx"]]
        if en_runs and e["idx"] in en_runs:
            e["en_runs"] = en_runs[e["idx"]]
    notes_path.write_bytes(json.dumps(notes, ensure_ascii=False, indent=1).encode("utf-8"))
    file_receipt(notes_path, ROOT / args.variant)
    out = d / "out.xml"
    pr = subprocess.run(["uv", "run", "--with", "lxml", "python", str(SCRIPTS / "apply_translations_textmatch.py"),
                         str(src), str(notes_path), str(out)], capture_output=True, text=True, encoding="utf-8",
                        errors="replace", env=ENV, timeout=900)
    if not out.is_file():
        print(f"  apply wrote nothing for {name} (rc={pr.returncode})")
        return None, src
    return etree.parse(str(out)).getroot(), src


def q(tag):
    return f"{{{W}}}{tag}"


def runs_of(par):
    return [x for x in par.iter(q("r")) if any((t.text or "").strip() for t in x.findall(q("t")))]


def run_text(run):
    return "".join(t.text or "" for t in run.findall(q("t")))


def val(run, tag, attr="val"):
    rpr = run.find(q("rPr"))
    el = rpr.find(q(tag)) if rpr is not None else None
    return None if el is None else (el.get(q(attr)) if el.get(q(attr)) is not None else "on")


def force(cascade, par, run):
    rpr = run.find(q("rPr"))
    rs = rpr.find(q("rStyle")) if rpr is not None else None
    return XP.resolve_run(cascade, None, rs.get(q("val")) if rs is not None else None, rpr)


print("=" * 96)
print(f"SUB-STEP 16.5 - the other properties, per span  [{args.variant}]"
      + (f"  scripts: {args.scripts}" if args.scripts else ""))
print("=" * 96)
LINKR = '<w:rStyle w:val="LinkZq"/><w:smallCaps/>'
root, src = run_doc("main", [
    p(link(r(f"Zie {NEEDLE} ", LINKR), r("hier", LINKR))),                                       # 0 container
    p(r("Term", '<w:b/><w:u w:val="single"/>'), r(f" betekent {NEEDLE} iets.")),                # 1 per span
    p(r(f"Teken {NEEDLE}", '<w:rFonts w:ascii="Symbol" w:hAnsi="Symbol"/><w:sz w:val="20"/>')),  # 2 A5
    p(r(f"Gewoon {NEEDLE} "), r("gemarkeerd", '<w:highlight w:val="yellow"/>')),                 # 3 mixed in state
    p(r(f"Gelijk {NEEDLE}", '<w:sz w:val="22"/><w:rFonts w:ascii="Arial" w:hAnsi="Arial"/>')),   # 4 uniform
    p(r("De "), r("Term", '<w:rStyle w:val="TermZq"/>'), r(f" volgt {NEEDLE}.")),               # 5 A17's shape
    p(r("Kop", '<w:b/><w:u w:val="single"/>'), r(f" tekst {NEEDLE}.")),                         # 6 absent state
    p(r("Pijl", '<w:b/><w:rFonts w:ascii="Wingdings" w:hAnsi="Wingdings"/>'),
      r(f" tekst {NEEDLE}.", '<w:rFonts w:ascii="Arial" w:hAnsi="Arial"/>')),                    # 7 per-span symbol
    p(r("Naam", '<w:b/><w:u w:val="single"/>'), r(f" rest {NEEDLE}.")),                         # 8 a blank span
], {0: "See here", 1: "Term means something.", 2: "Sign text", 3: "Plain highlighted", 4: "Even text",
    5: "The Term follows.", 6: "Head text.", 7: "Arrow text.", 8: "Name rest."},
    en_runs={1: [{"start": 0, "end": 4, "bold": True, "italic": False},
                 {"start": 4, "end": 21, "bold": False, "italic": False}],
             3: [{"start": 0, "end": 17, "bold": False, "italic": False}],
             5: [{"start": 0, "end": 4, "bold": False, "italic": False},
                 {"start": 4, "end": 8, "bold": True, "italic": False},
                 {"start": 8, "end": 17, "bold": False, "italic": False}],
             6: [{"start": 0, "end": 4, "bold": False, "italic": True},
                 {"start": 4, "end": 10, "bold": False, "italic": False}],
             7: [{"start": 0, "end": 5, "bold": True, "italic": False},
                 {"start": 5, "end": 11, "bold": False, "italic": False}],
             8: [{"start": 0, "end": 4, "bold": True, "italic": False},
                 {"start": 4, "end": 5, "bold": False, "italic": True},
                 {"start": 5, "end": 10, "bold": False, "italic": False}]})
if root is None:
    ok("apply delivered the invented document", False)
    print(f"\n  {CHECKED} check(s), {len(FAIL)} failure(s)")
    sys.exit(1)
with zipfile.ZipFile(src) as z:
    cas = XP.read_style_cascade(z)
P = list(root.iter(q("p")))

print("\n1  the container template: every text run inside a hyperlink, sharing a character style and small caps")
ok("the English keeps the character style", [val(x, "rStyle") for x in runs_of(P[0])] == ["LinkZq"],
   str([val(x, "rStyle") for x in runs_of(P[0])]))
ok("... and the small capitals", [val(x, "smallCaps") for x in runs_of(P[0])] == ["on"],
   str([val(x, "smallCaps") for x in runs_of(P[0])]))
ok("... and sits inside the hyperlink still", all(x.getparent().tag == q("hyperlink") for x in runs_of(P[0])))
print("\n2  per declared span: a bold underlined term beside plain text")
spans = [(run_text(x), val(x, "u")) for x in runs_of(P[1])]
ok("the underline on the bold span only", [u for _t, u in spans] == ["single", None] and spans[0][0] == "Term",
   str(spans))
print("\n3  A5: a symbol-font template")
ok("no symbol font on the English", all(val(x, "rFonts", "ascii") not in ("Symbol",) for x in runs_of(P[2])),
   str([val(x, "rFonts", "ascii") for x in runs_of(P[2])]))
ok("... its size kept", [val(x, "sz") for x in runs_of(P[2])] == ["20"], str([val(x, "sz") for x in runs_of(P[2])]))
print("\n4  a property mixed within one emphasis state: as before")
ok("the template's value on the one span (the highlighted run is the first with run properties)",
   [val(x, "highlight") for x in runs_of(P[3])] == ["yellow"], str([val(x, "highlight") for x in runs_of(P[3])]))
print("\n5  a uniform paragraph")
ok("its size and font kept", [(val(x, "sz"), val(x, "rFonts", "ascii")) for x in runs_of(P[4])] == [("22", "Arial")])
print("\n6  bold and italic in force as declared")
ok("the term bold, the rest not", [force(cas, P[1], x)["bold"] for x in runs_of(P[1])] == [True, False],
   str([force(cas, P[1], x)["bold"] for x in runs_of(P[1])]))
ok("nothing else bold or italic", all(not force(cas, P[i], x)["bold"] and not force(cas, P[i], x)["italic"]
                                      for i in (0, 2, 3, 4) for x in runs_of(P[i])))

print("\n7  A17's shape: a bold character style on the term, declared")
t7 = [(run_text(x), val(x, "rStyle"), [c.tag.split("}")[1] for c in (x.find(q("rPr")) if x.find(q("rPr")) is not None
                                                                     else []) if c.tag.split("}")[1] in ("b", "bCs")])
      for x in runs_of(P[5])]
ok("the character style on the term's span only", [st for _t, st, _f in t7] == [None, "TermZq", None], str(t7))
ok("... no bold flag on any span", all(not f for _t, _s, f in t7), str(t7))
ok("... the term bold in force, the rest not", [force(cas, P[5], x)["bold"] for x in runs_of(P[5])] ==
   [False, True, False])
print("\n8  a declared state the source never shows")
ok("the template's underline on every span, as before", [val(x, "u") for x in runs_of(P[6])] == ["single", "single"],
   str([val(x, "u") for x in runs_of(P[6])]))
ok("... italic in force where declared", [force(cas, P[6], x)["italic"] for x in runs_of(P[6])] == [True, False])
print("\n9  a symbol font carried by a span's own state")
ok("the bold span takes no symbol font from its source run", [val(x, "rFonts", "ascii") for x in runs_of(P[7])]
   == [None, "Arial"], str([val(x, "rFonts", "ascii") for x in runs_of(P[7])]))
print("\n10  a blank declared span in a state the source never shows")
ok("delivered, the underline on the term's span only", [val(x, "u") for x in runs_of(P[8])] == ["single", None],
   str([val(x, "u") for x in runs_of(P[8])]))

shutil.rmtree(TMP, ignore_errors=True)
print("\n" + "=" * 96)
print(f"  {CHECKED} check(s), {len(FAIL)} failure(s)")
for f in FAIL:
    print(f"    XX  {f}")
print("=" * 96)
sys.exit(1 if FAIL else 0)
