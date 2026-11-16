"""test_minimal_flags.py - sub-step 16.3: bold and italic written only where needed, the off-flags removed
(PLAN-2-step-b.md section 3.16).

ON INVENTED DOCUMENTS ONLY, built in a temporary directory. Each document is put through the tree's own
extract_paragraphs.py - so its notes carry `resolved` exactly as today's extraction writes it - an operator's
English added, the read receipt filed, and the tree's apply run over it. Each delivered run is then read IN FORCE
by extraction's resolver over the document's own styles. What each arm asserts:

  1  TP, A12's shape: a heading bold by its paragraph STYLE, nothing declared - delivered bold, with no flag; the
     same heading long, past the sub-heading test's ten words - bold too; and one whose whitespace-only run is
     switched off - bold, a blank run having no vote
  2  TP, italic: a paragraph the source shows uniformly italic, nothing declared - delivered italic
  3  TP, A17's shape: a term bold by a CHARACTER style, declared bold, beside plain declared text - each span as
     declared, in force
  4  FP, the bold-document control: a body style that gives bold, switched off run by run in the source - delivered
     NOT bold, the off-flag kept because it does work; a span declared false over a bold style - not bold
  5  FP, the redundant flags: a plain paragraph in a plain style - delivered with no b, bCs, i or iCs at all, and
     no empty run properties
  5b the sub-heading test, read IN FORCE since sub-step 16.4: a short paragraph bold by its paragraph mark alone -
     a mark's bold formats the mark, so the test no longer fires and the paragraph is delivered NOT bold
  6  a mixed source, nothing declared: today's rule - the defined term bold, written as the pair b and bCs with no
     value, the rest not bold and carrying no flag
  7  the tracked-change path: in a plain style no off-flag is written, and a direct bold is dropped; in a style that
     gives bold, `w:b w:val="0"` - on a paragraph one run of which the source switches off, since one bold in force
     throughout skips the override from sub-step 16.4; italic not touched; in force not bold either way
  8  WITH NO STYLES KNOWN - the styles part named and absent - apply writes today's explicit flags on every run
  9  A PARTIAL INSTALL - extract_paragraphs.py missing beside apply - today's explicit flags, said in one line

RED FIRST: against the pin c9b7d90's scripts (--scripts) arms 1, 2, 5, 6's flags and 7's no-off-flag fail: every
run carries a flag, the style-bold heading is stripped, the uniformly italic paragraph is written plain.
Prints flags, booleans and the invented documents' own words - never anything from a real document.

    uv run --with lxml python tests/test_minimal_flags.py
    uv run --with lxml python tests/test_minimal_flags.py --variant us
    uv run --with lxml python tests/test_minimal_flags.py --scripts <folder>   # e.g. the pin's, for RED
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

TMP = Path(tempfile.mkdtemp(prefix="s163-flags-test-"))
ENV = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1", PYTHONDONTWRITEBYTECODE="1")
W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
FAIL, CHECKED = [], 0
NEEDLE = "Quokkaland"
MISSING_LINE = "extract_paragraphs.py is missing beside this script"
STYLES = (f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:styles xmlns:w="{W}">'
          '<w:style w:type="paragraph" w:default="1" w:styleId="Normal"/>'
          '<w:style w:type="paragraph" w:styleId="HeadZq"><w:basedOn w:val="Normal"/><w:rPr><w:b/></w:rPr></w:style>'
          '<w:style w:type="paragraph" w:styleId="BodyBoldZq"><w:basedOn w:val="Normal"/><w:rPr><w:b/></w:rPr>'
          '</w:style>'
          '<w:style w:type="character" w:styleId="TermZq"><w:rPr><w:b/></w:rPr></w:style>'
          '</w:styles>')
RELS = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" '
        'Target="styles.xml"/></Relationships>')


def ok(label, cond, detail=""):
    global CHECKED
    CHECKED += 1
    print(f"  {'OK  ' if cond else 'XX  '} {label}" + (f"   ({detail})" if detail and not cond else ""))
    if not cond:
        FAIL.append(label)


def r(text, rpr=""):
    return f"<w:r>{'<w:rPr>' + rpr + '</w:rPr>' if rpr else ''}<w:t xml:space=\"preserve\">{text}</w:t></w:r>"


def p(*runs, style=None):
    ppr = f'<w:pPr><w:pStyle w:val="{style}"/></w:pPr>' if style else ""
    return "<w:p>" + ppr + "".join(runs) + "</w:p>"


def ins(*runs):
    return '<w:ins w:id="1" w:author="x" w:date="2026-01-01T00:00:00Z">' + "".join(runs) + "</w:ins>"


def write_docx(path, paras, styles=STYLES):
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("word/document.xml", f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                                         f'<w:document xmlns:w="{W}"><w:body>{"".join(paras)}</w:body></w:document>')
        z.writestr("word/_rels/document.xml.rels", RELS)
        if styles is not None:
            z.writestr("word/styles.xml", styles)
    return path


def run_doc(name, paras, en, en_runs=None, styles=STYLES, scripts=None):
    """(the delivered root, apply's stdout, the source path): extraction, the operator's English, apply."""
    d = TMP / name
    d.mkdir()
    src = write_docx(d / "src.docx", paras, styles)
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
    pr = subprocess.run(["uv", "run", "--with", "lxml", "python", str((scripts or SCRIPTS) /
                                                                     "apply_translations_textmatch.py"),
                         str(src), str(notes_path), str(out)], capture_output=True, text=True, encoding="utf-8",
                        errors="replace", env=ENV, timeout=900)
    if not out.is_file():
        print(f"  apply wrote nothing for {name} (rc={pr.returncode})")
        return None, pr.stdout + pr.stderr, src
    return etree.parse(str(out)).getroot(), pr.stdout + pr.stderr, src


def q(tag):
    return f"{{{W}}}{tag}"


def paras_of(root):
    return [x for x in root.iter(q("p"))] if root is not None else []


def runs_of(par):
    return [x for x in par.iter(q("r")) if any((t.text or "").strip() for t in x.findall(q("t")))]


def run_text(run):
    return "".join(t.text or "" for t in run.findall(q("t")))


def cascade_of(src):
    with zipfile.ZipFile(src) as z:
        return XP.read_style_cascade(z)


def force(cascade, par, run):
    ppr = par.find(q("pPr"))
    ps = ppr.find(q("pStyle")) if ppr is not None else None
    rpr = run.find(q("rPr"))
    rs = rpr.find(q("rStyle")) if rpr is not None else None
    return XP.resolve_run(cascade, ps.get(q("val")) if ps is not None else None,
                          rs.get(q("val")) if rs is not None else None, rpr)


def flags(run):
    rpr = run.find(q("rPr"))
    return sorted(c.tag.split("}")[1] for c in (rpr if rpr is not None else []) if c.tag.split("}")[1] in
                  ("b", "bCs", "i", "iCs"))


def flag_values(run, names=("b", "bCs")):
    rpr = run.find(q("rPr"))
    return [(c.tag.split("}")[1], c.get(q("val"))) for c in (rpr if rpr is not None else [])
            if c.tag.split("}")[1] in names]


print("=" * 96)
print(f"SUB-STEP 16.3 - bold and italic written only where needed  [{args.variant}]"
      + (f"  scripts: {args.scripts}" if args.scripts else ""))
print("=" * 96)
LONG = "Clause one sets out the governing terms of the whole arrangement between the two parties here"
root, said, src = run_doc("main", [
    p(r(f"Head {NEEDLE}"), style="HeadZq"),                                          # 0 A12: bold by style
    p(r(f"Lange {NEEDLE} kop met veel woorden die samen een lange titel vormen"), style="HeadZq"),  # 1 long
    p(r(f"Schuin {NEEDLE} geheel", "<w:i/>")),                                       # 2 uniformly italic
    p(r("De "), r("Term", '<w:rStyle w:val="TermZq"/>'), r(f" volgt {NEEDLE}.")),   # 3 A17's shape, declared
    p(r(f"Romp {NEEDLE}", '<w:b w:val="0"/>'), r(" vervolg", '<w:b w:val="0"/>'), style="BodyBoldZq"),  # 4 control
    p(r(f"Verklaard {NEEDLE}"), style="HeadZq"),                                     # 5 declared false
    p(r(f"Gewoon {NEEDLE} tekst.")),                                                 # 6 plain
    p(r("“Begrip”", "<w:b/>"), r(f" betekent {NEEDLE}.")),                 # 7 mixed, undeclared
    p(r(f"Kop{NEEDLE}"), r(" ", '<w:b w:val="0"/>'), r("tekst"), style="HeadZq"),   # 8 a blank run, no vote
    f'<w:p><w:pPr><w:rPr><w:b/></w:rPr></w:pPr>{r(f"Korte {NEEDLE}")}</w:p>',       # 9 the sub-heading test
], {0: "Head", 1: LONG, 2: "Wholly italic", 3: "The Term follows.", 4: "Body text throughout",
    5: "Declared plain", 6: "Plain text.", 7: "“Term” means the thing.", 8: "Heading words",
    9: "Short title"},
    en_runs={3: [{"start": 0, "end": 4, "bold": False, "italic": False},
                 {"start": 4, "end": 8, "bold": True, "italic": False},
                 {"start": 8, "end": 17, "bold": False, "italic": False}],
             5: [{"start": 0, "end": 14, "bold": False, "italic": False}]})
if root is None:
    ok("apply delivered the invented document", False)
    print(f"\n  {CHECKED} check(s), {len(FAIL)} failure(s)")
    sys.exit(1)
cas = cascade_of(src)
P = paras_of(root)


def all_force(i, name):
    return {force(cas, P[i], x)[name] for x in runs_of(P[i])}


print("\n1  A12's shape: bold by the paragraph's style, nothing declared")
ok("the short heading delivered bold in force", all_force(0, "bold") == {True}, str(all_force(0, "bold")))
ok("... with no bold flag on its runs", all("b" not in flags(x) for x in runs_of(P[0])),
   str([flags(x) for x in runs_of(P[0])]))
ok("the long heading, past the sub-heading test, delivered bold in force", all_force(1, "bold") == {True})
ok("a heading whose blank run is switched off: the blank run has no vote, delivered bold in force",
   all_force(8, "bold") == {True}, str(all_force(8, "bold")))
print("\n2  a source uniformly italic, nothing declared")
ok("delivered italic in force", all_force(2, "italic") == {True}, str(all_force(2, "italic")))
print("\n3  A17's shape: a term bold by a character style, declared bold")
spans = [(run_text(x), force(cas, P[3], x)["bold"]) for x in runs_of(P[3])]
ok("each declared span in force as declared: only the term bold",
   [b for _t, b in spans] == [False, True, False] and spans[1][0] == "Term", str([b for _t, b in spans]))
print("\n4  the bold-document control and a declared false")
ok("a bold body style switched off run by run: delivered NOT bold", all_force(4, "bold") == {False})
ok("... the off-flag kept, since it does work", all("b" in flags(x) for x in runs_of(P[4])))
ok("a span declared false over a bold style: NOT bold", all_force(5, "bold") == {False})
print("\n5  the redundant flags")
ok("a plain paragraph in a plain style: no b, bCs, i or iCs on any run", all(not flags(x) for x in runs_of(P[6])),
   str([flags(x) for x in runs_of(P[6])]))
ok("... and no empty run properties left behind", all(x.find(q("rPr")) is None for x in runs_of(P[6])))
print("\n5b  the sub-heading test, read in force since sub-step 16.4")
ok("bold by the paragraph mark alone, short: the test does not fire and the paragraph is delivered NOT bold",
   all_force(9, "bold") == {False}, str(all_force(9, "bold")))
print("\n6  a mixed source, nothing declared: today's rule")
m = [(run_text(x), force(cas, P[7], x)["bold"]) for x in runs_of(P[7])]
ok("the defined term bold, the rest not", [b for _t, b in m] == [False, True, False] or
   [b for _t, b in m] == [True, False], str(m))
term = [x for x in runs_of(P[7]) if run_text(x) == "Term"]
ok("... the term written as the pair b and bCs, turned on", len(term) == 1 and
   flag_values(term[0]) == [("b", None), ("bCs", None)], str([flag_values(x) for x in term]))
ok("... the rest carrying no flag at all, nor an emptied template's run properties",
   all(x.find(q("rPr")) is None for x in runs_of(P[7]) if run_text(x) != "Term"),
   str([flags(x) for x in runs_of(P[7])]))

print("\n7  the tracked-change path")
troot, _s, tsrc = run_doc("tc", [
    p(r(f"Eerst {NEEDLE} "), ins(r("ingevoegd"))),
    p(r(f"Kop {NEEDLE} "), ins(r("erbij")), r(" los", '<w:b w:val="0"/>'), style="BodyBoldZq"),
    p(r(f"Vet {NEEDLE} ", "<w:b/>"), r("schuin ", "<w:i/>"), ins(r("nieuw"))),
], {0: "First inserted", 1: "Head added", 2: "Bold slanted new"})
tcas = cascade_of(tsrc)
TP = paras_of(troot)
ok("in a plain style: no off-flag written on any run", len(TP) == 3 and all("b" not in flags(x) for x in
                                                                          runs_of(TP[0])))
ok("in a style that gives bold: w:b w:val=\"0\" on every run", len(TP) == 3 and all(
    ("b", "0") in flag_values(x, ("b",)) for x in runs_of(TP[1])))
ok("a direct bold in a plain style: dropped, not turned off", len(TP) == 3 and all(
    "b" not in flags(x) for x in runs_of(TP[2])), str([flags(x) for x in runs_of(TP[2])] if len(TP) == 3 else ""))
ok("italic not touched: the italic run keeps its flag", len(TP) == 3 and
   [flags(x).count("i") for x in runs_of(TP[2])] == [0, 1, 0],
   str([flags(x) for x in runs_of(TP[2])] if len(TP) == 3 else ""))
ok("not bold in force anywhere", len(TP) == 3 and all(not force(tcas, TP[i], x)["bold"] for i in (0, 1, 2)
                                                      for x in runs_of(TP[i])))

print("\n8  with no styles known, today's explicit flags")
nroot, _s2, nsrc = run_doc("nostyles", [p(r(f"Alleen {NEEDLE}.")), p(r("Ook dit."), style="HeadZq")],
                           {0: "Only this.", 1: "Also this."}, styles=None)
NP = paras_of(nroot)
ok("every run carries b, bCs, i and iCs, as before 16.3", len(NP) == 2 and all(
    flags(x) == ["b", "bCs", "i", "iCs"] for par in NP for x in runs_of(par)),
   str([[flags(x) for x in runs_of(par)] for par in NP]))

print("\n9  a partial install: extract_paragraphs.py missing beside apply")
partial = TMP / "partial"
shutil.copytree(SCRIPTS.parent, partial / SCRIPTS.parent.name)
(partial / SCRIPTS.parent.name / "scripts" / "extract_paragraphs.py").unlink()
proot, psaid, _psrc = run_doc("partialdoc", [p(r(f"Gewoon {NEEDLE}."), style="HeadZq")], {0: "Plain only."},
                              scripts=partial / SCRIPTS.parent.name / "scripts")
PP = paras_of(proot)
ok("apply delivered, every run carrying b, bCs, i and iCs, as before 16.3", len(PP) == 1 and all(
    flags(x) == ["b", "bCs", "i", "iCs"] for x in runs_of(PP[0])), str([flags(x) for x in runs_of(PP[0])]
                                                                       if PP else "nothing delivered"))
ok("... and said so in one line", psaid.count(MISSING_LINE) == 1 and "Traceback" not in psaid,
   f"said {psaid.count(MISSING_LINE)} time(s)")

shutil.rmtree(TMP, ignore_errors=True)
print("\n" + "=" * 96)
print(f"  {CHECKED} check(s), {len(FAIL)} failure(s)")
for f in FAIL:
    print(f"    XX  {f}")
print("=" * 96)
sys.exit(1 if FAIL else 0)
