"""test_declarations_win.py - sub-step 16.4: the readers, declarations win (PLAN-2-step-b.md section 3.16).

ON INVENTED DOCUMENTS ONLY, built in a temporary directory. Each document is put through the tree's own
extract_paragraphs.py - so its notes carry `resolved` exactly as today's extraction writes it - an operator's
English added, the read receipt filed, and the tree's apply run over it. Each delivered run is then read IN FORCE
by extraction's resolver over the document's own styles. What each arm asserts:

  1  TP, A11's shape: a short paragraph its runs show bold, declared one upright-italic span not bold - delivered
     as declared, never replaced by the sub-heading test's one bold upright span
  2  TP, a declared bold pattern on a short bold paragraph - only the declared term bold; and a span declared
     false over a short paragraph its runs show bold - delivered not bold
  3  FP, a declaration that agrees with the test - a short bold paragraph declared bold throughout - delivered bold
  4  TP, the test read IN FORCE: a short paragraph bold by its paragraph mark alone (a mark's bold formats the mark,
     not the text) - delivered NOT bold, as the page shows it; a short heading bold by its style alone - bold
  5  TP, italic where the test fires: a short paragraph bold and italic, nothing declared - delivered bold AND
     italic, the test no longer forcing italic off
  6  FP, an undeclared short paragraph bold in force - still bold
  7  TP, the tracked-change bypass read IN FORCE: a tracked-change paragraph bold by its style throughout -
     delivered bold, no off-flag written; a mixed one still has the override (the bold leak defended)
  8  post_process's untranslated-term arm: a source run italic by its STYLE (`resolved`) accounts for an italic
     delivered run of the same text; a run whose `resolved` says not italic does not; one with no `resolved` as
     before
  9  where apply cannot read the styles (extract_paragraphs.py missing beside it) but the notes carry `resolved`:
     the sub-heading test itself reads in force - the one place its reading still decides, since wherever styles
     are known 16.3's source-in-force rule has the last word - so a mark-only bold paragraph is delivered NOT bold

RED FIRST: against 16.3's scripts (--scripts, the pin 921ec66) arms 1, 2, 4's mark case, 5, 7's style case, 8's
style case and 9 fail. Prints booleans and the invented documents' own words - never anything from a real document.

    uv run --with lxml python tests/test_declarations_win.py
    uv run --with lxml python tests/test_declarations_win.py --variant us
    uv run --with lxml python tests/test_declarations_win.py --scripts <folder>   # e.g. the pin's, for RED
"""
import argparse
import contextlib
import importlib.util
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

TMP = Path(tempfile.mkdtemp(prefix="s164-decl-test-"))
ENV = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1", PYTHONDONTWRITEBYTECODE="1")
W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
FAIL, CHECKED = [], 0
NEEDLE = "Wombatia"
STYLES = (f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:styles xmlns:w="{W}">'
          '<w:style w:type="paragraph" w:default="1" w:styleId="Normal"/>'
          '<w:style w:type="paragraph" w:styleId="HeadZq"><w:basedOn w:val="Normal"/><w:rPr><w:b/></w:rPr></w:style>'
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


def p(*runs, style=None, mark=""):
    inner = (f'<w:pStyle w:val="{style}"/>' if style else "") + (f"<w:rPr>{mark}</w:rPr>" if mark else "")
    return "<w:p>" + (f"<w:pPr>{inner}</w:pPr>" if inner else "") + "".join(runs) + "</w:p>"


def ins(*runs):
    return '<w:ins w:id="1" w:author="x" w:date="2026-01-01T00:00:00Z">' + "".join(runs) + "</w:ins>"


def write_docx(path, paras):
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("word/document.xml", f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                                         f'<w:document xmlns:w="{W}"><w:body>{"".join(paras)}</w:body></w:document>')
        z.writestr("word/_rels/document.xml.rels", RELS)
        z.writestr("word/styles.xml", STYLES)
    return path


def run_doc(name, paras, en, en_runs=None, scripts=None):
    """(the delivered root, the source path, the notes): extraction, the operator's English, apply."""
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
    pr = subprocess.run(["uv", "run", "--with", "lxml", "python", str((scripts or SCRIPTS) /
                                                                     "apply_translations_textmatch.py"),
                         str(src), str(notes_path), str(out)], capture_output=True, text=True, encoding="utf-8",
                        errors="replace", env=ENV, timeout=900)
    if not out.is_file():
        print(f"  apply wrote nothing for {name} (rc={pr.returncode})")
        return None, src, notes
    return etree.parse(str(out)).getroot(), src, notes


def q(tag):
    return f"{{{W}}}{tag}"


def runs_of(par):
    return [x for x in par.iter(q("r")) if any((t.text or "").strip() for t in x.findall(q("t")))]


def run_text(run):
    return "".join(t.text or "" for t in run.findall(q("t")))


def force(cascade, par, run):
    ppr = par.find(q("pPr"))
    ps = ppr.find(q("pStyle")) if ppr is not None else None
    rpr = run.find(q("rPr"))
    rs = rpr.find(q("rStyle")) if rpr is not None else None
    return XP.resolve_run(cascade, ps.get(q("val")) if ps is not None else None,
                          rs.get(q("val")) if rs is not None else None, rpr)


def flag_values(run, names=("b",)):
    rpr = run.find(q("rPr"))
    return [(c.tag.split("}")[1], c.get(q("val"))) for c in (rpr if rpr is not None else [])
            if c.tag.split("}")[1] in names]


print("=" * 96)
print(f"SUB-STEP 16.4 - the readers: declarations win  [{args.variant}]"
      + (f"  scripts: {args.scripts}" if args.scripts else ""))
print("=" * 96)
B = "<w:b/>"
root, src, notes = run_doc("main", [
    p(r(f"Cel {NEEDLE}", B)),                                                        # 0 A11: declared italic
    p(r(f"Artikel {NEEDLE}", B), r(" kop", B)),                                     # 1 a declared bold pattern
    p(r(f"Vet {NEEDLE}", B)),                                                        # 2 declared false
    p(r(f"Kop {NEEDLE}", B)),                                                        # 3 declared, agreeing
    p(r(f"Merk {NEEDLE}"), mark=B),                                                  # 4 bold by the mark alone
    p(r(f"Stijl {NEEDLE}"), style="HeadZq"),                                         # 5 bold by its style alone
    p(r(f"Schuin {NEEDLE}", "<w:b/><w:i/>")),                                        # 6 bold and italic, undeclared
    p(r(f"Vast {NEEDLE}", B)),                                                       # 7 bold, undeclared
], {0: "Cell value", 1: "Article heading", 2: "Plain words", 3: "Heading words", 4: "Mark only",
    5: "Style only", 6: "Bold slanted", 7: "Firm heading"},
    en_runs={0: [{"start": 0, "end": 10, "bold": False, "italic": True}],
             1: [{"start": 0, "end": 7, "bold": True, "italic": False},
                 {"start": 7, "end": 15, "bold": False, "italic": False}],
             2: [{"start": 0, "end": 11, "bold": False, "italic": False}],
             3: [{"start": 0, "end": 13, "bold": True, "italic": False}]})
if root is None:
    ok("apply delivered the invented document", False)
    print(f"\n  {CHECKED} check(s), {len(FAIL)} failure(s)")
    sys.exit(1)
with zipfile.ZipFile(src) as z:
    cas = XP.read_style_cascade(z)
P = list(root.iter(q("p")))


def col(i, name):
    return [force(cas, P[i], x)[name] for x in runs_of(P[i])]


ok("the invented notes carry what the arms need: the mark-only run `bold` but `resolved` not",
   notes[4]["runs"][0].get("bold") is True and notes[4]["runs"][0].get("resolved") == {"bold": False},
   str(notes[4]["runs"]))
print("\n1  A11's shape: a short bold paragraph declared italic and not bold")
ok("delivered italic in force, as declared", col(0, "italic") == [True], str(col(0, "italic")))
ok("... and not bold, as declared", col(0, "bold") == [False], str(col(0, "bold")))
print("\n2  a declared bold pattern, and a span declared false, on short bold paragraphs")
spans = [(run_text(x), force(cas, P[1], x)["bold"]) for x in runs_of(P[1])]
ok("only the declared term bold", [b for _t, b in spans] == [True, False] and spans[0][0] == "Article",
   str(spans))
ok("a span declared false over runs the source shows bold: NOT bold", col(2, "bold") == [False], str(col(2, "bold")))
print("\n3  a declaration that agrees with the test")
ok("declared bold throughout: delivered bold", col(3, "bold") == [True], str(col(3, "bold")))
print("\n4  the sub-heading test read IN FORCE")
ok("bold by its paragraph mark alone: delivered NOT bold, as the page shows it", col(4, "bold") == [False],
   str(col(4, "bold")))
ok("bold by its style alone: delivered bold", col(5, "bold") == [True], str(col(5, "bold")))
print("\n5  italic where the test fires, nothing declared")
ok("bold and italic in the source: delivered bold", col(6, "bold") == [True], str(col(6, "bold")))
ok("... AND italic, no longer forced off", col(6, "italic") == [True], str(col(6, "italic")))
print("\n6  an undeclared short paragraph bold in force")
ok("still bold", col(7, "bold") == [True], str(col(7, "bold")))

print("\n7  the tracked-change bypass, read IN FORCE")
troot, tsrc, _tn = run_doc("tc", [
    p(r(f"Kop {NEEDLE} "), ins(r("erbij")), style="HeadZq"),                         # bold by style throughout
    p(r(f"Romp {NEEDLE} "), ins(r("erbij")), r(" los", '<w:b w:val="0"/>'), style="HeadZq"),  # mixed in force
], {0: "Head added", 1: "Body added loose"})
with zipfile.ZipFile(tsrc) as z:
    tcas = XP.read_style_cascade(z)
TP = list(troot.iter(q("p"))) if troot is not None else []
ok("bold by its style throughout: delivered bold in force", len(TP) == 2 and all(
    force(tcas, TP[0], x)["bold"] for x in runs_of(TP[0])),
   str([force(tcas, TP[0], x)["bold"] for x in runs_of(TP[0])] if TP else "nothing delivered"))
ok("... and no off-flag written on it", len(TP) == 2 and all(("b", "0") not in flag_values(x)
                                                            for x in runs_of(TP[0])))
ok("a paragraph mixed in force: the override still runs, an off-flag on every run", len(TP) == 2 and all(
    ("b", "0") in flag_values(x) for x in runs_of(TP[1])),
   str([flag_values(x) for x in runs_of(TP[1])] if TP else ""))

print("\n8  post_process's untranslated-term arm reads the source run's italic in force")
spec = importlib.util.spec_from_file_location("pp_under_test", SCRIPTS / "post_process.py")
PP = importlib.util.module_from_spec(spec)
sys.path.insert(0, str(SCRIPTS))
with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
    spec.loader.exec_module(PP)
term = f"Lex {NEEDLE}"
by_style = {"en": f"Under {term} law.", "runs": [{"text": term, "bold": False, "italic": False,
                                                   "resolved": {"italic": True}}]}
off_style = {"en": f"Under {term} law.", "runs": [{"text": term, "bold": False, "italic": True,
                                                    "resolved": {"italic": False}}]}
plain = {"en": f"Under {term} law.", "runs": [{"text": term, "bold": False, "italic": False}]}
ok("italic by its style (`resolved`): accounted for, KEEP", PP._declared_italic(by_style, term) is True,
   str(PP._declared_italic(by_style, term)))
ok("written italic but not italic in force: covered, not italic - STRIP", PP._declared_italic(off_style, term) is False,
   str(PP._declared_italic(off_style, term)))
ok("no `resolved`: as before, covered and not italic", PP._declared_italic(plain, term) is False)

print("\n9  apply cannot read styles (extract_paragraphs.py missing beside it) but the notes carry `resolved`")
partial = TMP / "partial"
shutil.copytree(SCRIPTS.parent, partial / SCRIPTS.parent.name)
(partial / SCRIPTS.parent.name / "scripts" / "extract_paragraphs.py").unlink()
proot, _ps, pnotes = run_doc("partialdoc", [p(r(f"Merk {NEEDLE}"), mark=B)], {0: "Mark only"},
                             scripts=partial / SCRIPTS.parent.name / "scripts")
PPAR = list(proot.iter(q("p"))) if proot is not None else []
ok("the sub-heading test reads the notes in force: a mark-only bold paragraph delivered NOT bold", len(PPAR) == 1
   and pnotes[0]["runs"][0].get("resolved") == {"bold": False}
   and [force(cas, PPAR[0], x)["bold"] for x in runs_of(PPAR[0])] == [False],
   str([force(cas, PPAR[0], x)["bold"] for x in runs_of(PPAR[0])] if PPAR else "nothing delivered"))

shutil.rmtree(TMP, ignore_errors=True)
print("\n" + "=" * 96)
print(f"  {CHECKED} check(s), {len(FAIL)} failure(s)")
for f in FAIL:
    print(f"    XX  {f}")
print("=" * 96)
sys.exit(1 if FAIL else 0)
