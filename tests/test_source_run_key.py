"""test_source_run_key.py - sub-step 17.4: a source run the operator names (PLAN-2-step-b.md section 3.17, 17.4's own
plan; 16.5's (a)).

ON INVENTED DOCUMENTS ONLY, built in a temporary directory. A declared `en_runs` span may name, as `source_run`, the
position counted from 0 of a source run in the entry's `runs`; the span then carries that run's eleven properties
(16.5's `_PER_SPAN_UNITS`), its bold and italic as declared. Each document is put through the tree's own
extract_paragraphs.py, an operator's English added, the read receipt filed, and the tree's apply run over it; each
delivered run's direct properties are then read, and its bold and italic in force by extraction's resolver over the
document's own styles. What each arm asserts:

  1  TP, one paragraph per property kind of the 27 mixed findings 16.5 declared - underline, highlight, size, colour,
     a character style, shading, small capitals: two plain source runs, one carrying the property, declared as two
     plain spans each naming its run - the property on its own span only (at the pin it spread over both, the first
     run carrying properties being the template)
  2  TP, a key naming a run inside a hyperlink - its character style on that span only
  3  TP, a bold span naming a plain source run - bold as declared, the run's underline carried
  4  TP, a span naming a run in a bold character style, declared NOT bold, beside a run whose properties are the
     template - the style carried and the bold switched off, what the styles give recomputed for the span
  5  A5: a span naming a run in a symbol font - no symbol font on it
  6  FP, the same shapes declared WITHOUT the key - as at the pin, the template on every span
  7  FP, a key naming a run whose properties equal the template's - nothing moves
  8  a key whose run no longer holds the text extraction listed - built as at the pin, one line naming its idx
  9  a key on a tracked-change paragraph - not read there, one line naming its idx, the paragraph delivered
  10 validate_en_runs.py refuses a malformed key - true, 1.5, "0", -1, one past the end of `runs` - exit 2, each idx
     named, never waived by --allow-bold-loss; well-formed keys, a null key and no key at all exit 0
  11 the committed fixture tests/fixtures/source-run-key.docx, the rendered diff's page: its notes agree with
     extraction (`en` and `en_runs` set aside), each keyed property on its own span, the unkeyed control as at the pin

RED FIRST: against 17.3's scripts (--scripts, the pin cd452dc) arms 1 to 5, 8, 9, 10 and 11 fail. Prints booleans and the
invented documents' own words - never anything from a real document.

    uv run --with lxml python tests/test_source_run_key.py
    uv run --with lxml python tests/test_source_run_key.py --variant us
    uv run --with lxml python tests/test_source_run_key.py --scripts <folder>   # e.g. the pin's, for RED
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

TMP = Path(tempfile.mkdtemp(prefix="s174-key-test-"))
ENV = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1", PYTHONDONTWRITEBYTECODE="1")
W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
RNS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
FAIL, CHECKED = [], 0
STYLES = (f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:styles xmlns:w="{W}">'
          '<w:style w:type="paragraph" w:default="1" w:styleId="Normal"/>'
          '<w:style w:type="character" w:styleId="LinkZq"><w:rPr><w:color w:val="0563C1"/><w:u w:val="single"/>'
          '</w:rPr></w:style>'
          '<w:style w:type="character" w:styleId="MarkZq"><w:rPr><w:color w:val="7030A0"/></w:rPr></w:style>'
          '<w:style w:type="character" w:styleId="TermZq"><w:rPr><w:b/></w:rPr></w:style>'
          '</w:styles>')
RELS = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" '
        'Target="styles.xml"/>'
        '<Relationship Id="rId9" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink" '
        'Target="https://example.invalid/" TargetMode="External"/></Relationships>')
INS = '<w:ins w:id="%d" w:author="A" w:date="2020-01-01T00:00:00Z">%s</w:ins>'


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
    return '<w:hyperlink r:id="rId9">' + "".join(runs) + "</w:hyperlink>"


def write_docx(path, paras):
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("word/document.xml", f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                                         f'<w:document xmlns:w="{W}" xmlns:r="{RNS}"><w:body>{"".join(paras)}'
                                         f'</w:body></w:document>')
        z.writestr("word/_rels/document.xml.rels", RELS)
        z.writestr("word/styles.xml", STYLES)
    return path


def extract(src, notes_path):
    subprocess.run(["uv", "run", "--with", "lxml", "python", str(ROOT / args.variant / "scripts" /
                                                                "extract_paragraphs.py"), str(src), str(notes_path)],
                   capture_output=True, text=True, encoding="utf-8", errors="replace", env=ENV, timeout=600)
    return json.loads(notes_path.read_text(encoding="utf-8"))


def apply(src, notes, d):
    """(the delivered root or None, apply's printed output)."""
    notes_path = d / "paragraphs.json"
    notes_path.write_bytes(json.dumps(notes, ensure_ascii=False, indent=1).encode("utf-8"))
    file_receipt(notes_path, ROOT / args.variant)
    out = d / "out.xml"
    pr = subprocess.run(["uv", "run", "--with", "lxml", "python", str(SCRIPTS / "apply_translations_textmatch.py"),
                         str(src), str(notes_path), str(out)], capture_output=True, text=True, encoding="utf-8",
                        errors="replace", env=ENV, timeout=900)
    return (etree.parse(str(out)).getroot() if out.is_file() else None), (pr.stdout or "") + (pr.stderr or "")


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


def force(cascade, run):
    rpr = run.find(q("rPr"))
    rs = rpr.find(q("rStyle")) if rpr is not None else None
    return XP.resolve_run(cascade, None, rs.get(q("val")) if rs is not None else None, rpr)


def span(a, b, key=None, bold=False):
    s = {"start": a, "end": b, "bold": bold, "italic": False}
    if key is not None:
        s["source_run"] = key
    return s


print("=" * 96)
print(f"SUB-STEP 17.4 - a source run the operator names  [{args.variant}]"
      + (f"  scripts: {args.scripts}" if args.scripts else ""))
print("=" * 96)

# (label, the source runs, the English, its split point, the property read as (tag, attribute))
KINDS = [
    ("underline", (r("Gewoon "), r("onderstreept", '<w:u w:val="single"/>')), "Plain underlined", 6, ("u", "val"),
     [None, "single"]),
    ("highlight", (r("Gewoon "), r("gemarkeerd", '<w:highlight w:val="yellow"/>')), "Plain marked", 6,
     ("highlight", "val"), [None, "yellow"]),
    ("size", (r("Klein ", '<w:sz w:val="18"/>'), r("groot", '<w:sz w:val="28"/>')), "Small large", 6, ("sz", "val"),
     ["18", "28"]),
    ("colour", (r("Zwart "), r("rood", '<w:color w:val="C00000"/>')), "Black red", 6, ("color", "val"),
     [None, "C00000"]),
    ("character style", (r("Gewoon "), r("stijl", '<w:rStyle w:val="MarkZq"/>')), "Plain style", 6,
     ("rStyle", "val"), [None, "MarkZq"]),
    ("shading", (r("Gewoon "), r("schaduw", '<w:shd w:val="clear" w:color="auto" w:fill="D9D9D9"/>')),
     "Plain shaded", 6, ("shd", "fill"), [None, "D9D9D9"]),
    ("small capitals", (r("Gewoon "), r("klein", "<w:smallCaps/>")), "Plain small", 6, ("smallCaps", "val"),
     [None, "on"]),
]
paras, en, en_runs = [], {}, {}
for k, (_l, runs, eng, cut, _prop, _want) in enumerate(KINDS):                 # 0-6 keyed, 7-13 the same unkeyed
    paras.append(p(*runs))
    en[k] = eng
    en_runs[k] = [span(0, cut, 0), span(cut, len(eng), 1)]
for k, (_l, runs, eng, cut, _prop, _want) in enumerate(KINDS):
    paras.append(p(*runs))
    en[7 + k] = eng
    en_runs[7 + k] = [span(0, cut), span(cut, len(eng))]
paras += [
    p(r("Zie "), link(r("bijlage", '<w:rStyle w:val="LinkZq"/>'))),                                          # 14
    p(r("Naam ", '<w:u w:val="single"/>'), r("rest")),                                                        # 15
    p(r("Gewoon ", '<w:color w:val="000000"/>'), r("Term", '<w:rStyle w:val="TermZq"/>')),                   # 16
    p(r("Pijl", '<w:rFonts w:ascii="Wingdings" w:hAnsi="Wingdings"/><w:sz w:val="24"/>'), r(" tekst")),      # 17
    p(r("Zelfde ", '<w:sz w:val="22"/>'), r("tekst", '<w:sz w:val="22"/>')),                                 # 18
]
en.update({14: "See schedule", 15: "Name rest", 16: "Plain Term", 17: "Arrow text", 18: "Same text"})
en_runs.update({14: [span(0, 4, 0), span(4, 12, 1)],
                15: [span(0, 5, 0, bold=True), span(5, 9, 1)],
                16: [span(0, 6, 0), span(6, 10, 1)],
                17: [span(0, 5, 0), span(5, 10, 1)],
                18: [span(0, 5, 0), span(5, 9, 1)]})

d = TMP / "main"
d.mkdir()
src = write_docx(d / "src.docx", paras)
notes = extract(src, d / "extracted.json")
for e in notes:
    e["en"] = en[e["idx"]]
    e["en_runs"] = en_runs.get(e["idx"])
root, said = apply(src, notes, d)
ok("apply delivered the invented document", root is not None, said[-400:])
if root is None:
    print(f"\n  {CHECKED} check(s), {len(FAIL)} failure(s)")
    sys.exit(1)
with zipfile.ZipFile(src) as z:
    cas = XP.read_style_cascade(z)
P = list(root.iter(q("p")))

print("\n1  one paragraph per property kind, each span naming its source run")
for k, (label, _runs, _eng, _cut, (tag, attr), want) in enumerate(KINDS):
    got = [val(x, tag, attr) for x in runs_of(P[k])]
    ok(f"{label}: on its own span only", got == want, str(got))
ok("... bold and italic in force as declared, plain throughout",
   all(not force(cas, x)["bold"] and not force(cas, x)["italic"] for k in range(7) for x in runs_of(P[k])))

print("\n2  a key naming a run inside a hyperlink")
got = [(run_text(x), val(x, "rStyle")) for x in runs_of(P[14])]
ok("its character style on that span only", [st for _t, st in got] == [None, "LinkZq"], str(got))

print("\n3  a bold span naming a plain source run")
ok("bold as declared", [force(cas, x)["bold"] for x in runs_of(P[15])] == [True, False],
   str([force(cas, x)["bold"] for x in runs_of(P[15])]))
ok("... the run's underline carried onto it alone", [val(x, "u") for x in runs_of(P[15])] == ["single", None],
   str([val(x, "u") for x in runs_of(P[15])]))

print("\n4  a span naming a run in a bold character style, declared not bold")
got = [(val(x, "rStyle"), val(x, "color"), force(cas, x)["bold"]) for x in runs_of(P[16])]
ok("the style carried onto that span only", [g[0] for g in got] == [None, "TermZq"], str(got))
ok("... the colour on the other only", [g[1] for g in got] == ["000000", None], str(got))
ok("... and neither bold in force - the styles recomputed for the span", [g[2] for g in got] == [False, False],
   str(got))

print("\n5  A5: a span naming a run in a symbol font")
got = [(val(x, "rFonts", "ascii"), val(x, "sz")) for x in runs_of(P[17])]
ok("no symbol font on it, its size carried", got == [(None, "24"), (None, None)], str(got))

print("\n6  the same shapes declared WITHOUT the key: as at the pin")
# the template is the first source run carrying properties: the second run's value, but for size the first's
TEMPLATE = ["single", "yellow", "18", "C00000", "MarkZq", "D9D9D9", "on"]
for k, (label, _runs, _eng, _cut, (tag, attr), _want) in enumerate(KINDS):
    got = [val(x, tag, attr) for x in runs_of(P[7 + k])]
    ok(f"{label}: the template's value on every span", got == [TEMPLATE[k]] * 2, str(got))

print("\n7  a key naming a run whose properties equal the template's")
ok("nothing moves", [val(x, "sz") for x in runs_of(P[18])] == ["22", "22"], str([val(x, "sz") for x in runs_of(P[18])]))
ok("no line names an unread key on this document", "NOTE: source_run" not in said,
   [ln for ln in said.splitlines() if "source_run" in ln])

print("\n8  a key whose run no longer holds the text extraction listed")
d8 = TMP / "moved"
d8.mkdir()
src8 = write_docx(d8 / "src.docx", [p(r("Gewoon "), r("onderstreept", '<w:u w:val="single"/>'))])
notes8 = extract(src8, d8 / "extracted.json")
notes8[0]["en"] = "Plain underlined"
notes8[0]["en_runs"] = [span(0, 6, 0), span(6, 16, 1)]
notes8[0]["runs"][0]["text"] = "Anders "                       # the source edited after extraction
root8, said8 = apply(src8, notes8, d8)
ok("apply delivered it", root8 is not None, said8[-300:])
if root8 is not None:
    got = [val(x, "u") for x in runs_of(list(root8.iter(q("p")))[0])]
    ok("its span built as at the pin: the template's underline on both spans", got == ["single", "single"], str(got))
ok("one line names idx 0 and the unread position",
   said8.count("NOTE: source_run [0] not read on paragraph idx 0") == 1,
   [ln for ln in said8.splitlines() if "NOTE" in ln])

print("\n9  a key on a tracked-change paragraph")
d9 = TMP / "tc"
d9.mkdir()
src9 = write_docx(d9 / "src.docx", [p(r("Oud "), INS % (1, r("nieuw", '<w:u w:val="single"/>')))])
notes9 = extract(src9, d9 / "extracted.json")
notes9[0]["en_segments"] = [{"type": s["type"], "en": e} for s, e in zip(notes9[0]["tc_segments"], ["Old ", "new"])]
notes9[0]["en"] = "Old new"
notes9[0]["en_runs"] = [span(0, 4, 0), span(4, 7, 1)]
root9, said9 = apply(src9, notes9, d9)
ok("apply delivered it", root9 is not None, said9[-300:])
if root9 is not None:
    got = [(run_text(x), val(x, "u"), x.getparent().tag == q("ins")) for x in runs_of(list(root9.iter(q("p")))[0])]
    ok("each run keeps its own properties and wrapper", got == [("Old ", None, False), ("new", "single", True)],
       str(got))
ok("one line names idx 0", said9.count("NOTE: source_run not read on tracked-change paragraph idx 0") == 1,
   [ln for ln in said9.splitlines() if "NOTE" in ln])

print("\n10  validate_en_runs.py and a malformed key")


def gate(entries, *flags):
    path = TMP / f"gate-{len(list(TMP.glob('gate-*')))}.json"
    path.write_bytes(json.dumps(entries).encode("utf-8"))
    pr = subprocess.run(["uv", "run", "--with", "lxml", "python", str(SCRIPTS / "validate_en_runs.py"), str(path),
                         *flags], capture_output=True, text=True, encoding="utf-8", errors="replace", env=ENV,
                        timeout=300)
    return pr.returncode, (pr.stdout or "") + (pr.stderr or "")


def entry(i, key):
    two = [{"start": 0, "end": 4, "text": "Alfa", "bold": False, "italic": False},
           {"start": 4, "end": 9, "text": " Beta", "bold": False, "italic": False}]
    s = [{"start": 0, "end": 5, "bold": False, "italic": False}, {"start": 5, "end": 9, "bold": False, "italic": False}]
    if key != "absent":
        s[1]["source_run"] = key
    return {"idx": i, "text": "Alfa Beta", "runs": two, "en": "Alph Beta", "en_runs": s}


BAD = {10: True, 11: 1.5, 12: "0", 13: -1, 14: 2}
rc, out = gate([entry(i, v) for i, v in BAD.items()])
ok("five malformed keys: exit 2", rc == 2, f"rc={rc}")
for i, v in BAD.items():
    ok(f"... idx {i} named ({v!r})", f"idx {i}: span 1 names source_run" in out, out[-300:])
rc, out = gate([entry(i, v) for i, v in BAD.items()], "--allow-bold-loss")
ok("--allow-bold-loss does not waive it", rc == 2, f"rc={rc}")
rc, out = gate([entry(20, 0), entry(21, 1), entry(22, None), entry(23, "absent")])
ok("keys 0 and 1, a null key and no key: exit 0", rc == 0, f"rc={rc} {out[-300:]}")
rc, out = gate([{"idx": 30, "text": "Alfa", "en": "Alph", "en_runs": [{"start": 0, "end": 4, "source_run": 0}]}])
ok("an entry with no runs listed refuses any position", rc == 2 and "idx 30: span 0 names source_run 0" in out,
   f"rc={rc}")

print("\n11  the committed fixture, the rendered diff's page")
FIXTURE = ROOT / "tests" / "fixtures" / "source-run-key.docx"
committed = json.loads(FIXTURE.with_suffix(".notes.json").read_text(encoding="utf-8"))
d11 = TMP / "fixture"
d11.mkdir()
src11 = d11 / "src.docx"
shutil.copyfile(FIXTURE, src11)
fresh = extract(src11, d11 / "extracted.json")
ok("every note as extraction writes it, the English set aside",
   [{k: v for k, v in n.items() if k not in ("en", "en_runs")} for n in committed]
   == [{k: v for k, v in n.items() if k not in ("en", "en_runs")} for n in fresh])
root11, said11 = apply(src11, committed, d11)
ok("apply delivered the fixture", root11 is not None, said11[-300:])
P11 = list(root11.iter(q("p"))) if root11 is not None else []
FIX = [("underline", ("u", "val"), [None, "single"]), ("highlight", ("highlight", "val"), [None, "yellow"]),
       ("size", ("sz", "val"), ["18", "32"]), ("colour", ("color", "val"), [None, "C00000"]),
       ("character style", ("rStyle", "val"), [None, "LinkLike"]), ("shading", ("shd", "fill"), [None, "D9D9D9"]),
       ("small capitals", ("smallCaps", "val"), [None, "on"]), ("the control, no key", ("u", "val"),
                                                                ["single", "single"])]
for i, (label, (tag, attr), want) in enumerate(FIX):
    got = [val(x, tag, attr) for x in runs_of(P11[i])] if i < len(P11) else None
    ok(f"fixture idx {i}, {label}: {want}", got == want, str(got))

shutil.rmtree(TMP, ignore_errors=True)
print("\n" + "=" * 96)
print(f"  {CHECKED} check(s), {len(FAIL)} failure(s)")
for f in FAIL:
    print(f"    XX  {f}")
print("=" * 96)
sys.exit(1 if FAIL else 0)
