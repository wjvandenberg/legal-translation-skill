# -*- coding: utf-8 -*-
"""STEP 15, sub-step 15.1 - does extraction say what formatting is IN FORCE on a run?

WHAT WAS WRONG. `extract_paragraphs.py` writes a run's `bold` and `italic` from the run's OWN properties, falling
back to the paragraph mark's, and never reads the styles part - so a run made bold by its paragraph style or its
character style is written plain. Measured before this suite was written (PLAN-2-step-b.md section 3.15): 132 of
3,996 corpus runs, 130 bold and 2 italic, in 4 of 10 documents. Sub-step 15.1 resolves the cascade and writes ONE
sparse key, `resolved`, holding only the properties whose value in force differs from what is written today -
every existing key untouched. Nothing reads the key yet; step 16 will.

THE RULE IT PINS, as Word applies it (section 3.15 of the build plan has the sources): document defaults first;
each style's `basedOn` chain rolled up, the nearest level naming a property winning; the paragraph style SETS the
value; the character style's true FLIPS it and its false leaves it; the run's own properties absolute; the
paragraph mark's properties no level at all. A run takes its nearest paragraph's style; an unknown or wrong-type
id falls to its type's default; a `basedOn` cycle is cut. Where the cascade cannot be known - a raw .xml input,
an unreadable styles part - no key is written.

EVERY DOCUMENT HERE IS INVENTED, built in a temporary folder; no text, style id or shape comes from the corpus.

  TP  each must carry `resolved` with the value stated - red against the code before 15.1, which writes no key.
  FP  each must carry NO `resolved` - including the shapes a wrong resolver would report: the paragraph mark
      taken as a level, the toggle pair added up instead of cancelled, a style of the wrong type obeyed.
  KEYS  on every case, `bold` and `italic` are what extraction wrote before 15.1 - the existing keys untouched.

    uv run --with lxml python tests/test_style_cascade.py
    uv run --with lxml python tests/test_style_cascade.py --variant us
    uv run --with lxml python tests/test_style_cascade.py --script <a copy of extract_paragraphs.py>
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
ap = argparse.ArgumentParser()
ap.add_argument("--variant", default="uk", choices=("uk", "us"))
ap.add_argument("--script", default=None, help="run this copy of extract_paragraphs.py instead of the tree's")
args = ap.parse_args()
SCRIPT = Path(args.script) if args.script else ROOT / args.variant / "scripts" / "extract_paragraphs.py"
ENV = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1", PYTHONDONTWRITEBYTECODE="1")
TMP = Path(tempfile.mkdtemp(prefix="s15-cascade-"))
FAIL, CHECKED = [], 0

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
TYPES = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
         '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
         '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
         '<Default Extension="xml" ContentType="application/xml"/>'
         '<Override PartName="/word/document.xml" '
         'ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
         '</Types>')


def ok(label, cond, detail=""):
    global CHECKED
    CHECKED += 1
    print(("  OK   " if cond else "  XX   ") + label + (f"   {detail}" if detail and not cond else ""))
    if not cond:
        FAIL.append(label)
    return cond


def document(body):
    return (f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:document xmlns:w="{W}"><w:body>'
            f'{body}</w:body></w:document>')


def styles(inner, doc_defaults=""):
    dd = f"<w:docDefaults><w:rPrDefault><w:rPr>{doc_defaults}</w:rPr></w:rPrDefault></w:docDefaults>"
    return f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:styles xmlns:w="{W}">{dd}{inner}</w:styles>'


def style(kind, sid, rpr="", based=None, default=False):
    return (f'<w:style w:type="{kind}" w:styleId="{sid}"' + (' w:default="1"' if default else "") + ">"
            + (f'<w:basedOn w:val="{based}"/>' if based else "") + (f"<w:rPr>{rpr}</w:rPr>" if rpr else "")
            + "</w:style>")


def para(runs, pstyle=None, mark=None):
    ppr = ((f'<w:pStyle w:val="{pstyle}"/>' if pstyle else "") + (f"<w:rPr>{mark}</w:rPr>" if mark else ""))
    return "<w:p>" + (f"<w:pPr>{ppr}</w:pPr>" if ppr else "") + "".join(runs) + "</w:p>"


def run(text, rpr=None):
    """rpr None: no rPr at all; "" an empty one; else its children."""
    return "<w:r>" + ("" if rpr is None else f"<w:rPr>{rpr}</w:rPr>") + f'<w:t xml:space="preserve">{text}</w:t></w:r>'


RELS_ELSEWHERE = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                  '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                  '<Relationship Id="rId1" Target="elsewhere.xml" '
                  'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles"/>'
                  '</Relationships>')


def extract(name, body, styles_xml=None, as_xml=False, rels=None):
    """Build the invented package (or a raw document.xml), run the script under test, return (rc, notes)."""
    d = TMP / name
    d.mkdir(parents=True, exist_ok=True)
    if as_xml:
        src = d / "document.xml"
        src.write_bytes(document(body).encode("utf-8"))
    else:
        src = d / "in.docx"
        with zipfile.ZipFile(src, "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr("[Content_Types].xml", TYPES)
            z.writestr("word/document.xml", document(body))
            if styles_xml is not None:
                z.writestr("word/styles.xml", styles_xml)
            if rels is not None:
                z.writestr("word/_rels/document.xml.rels", rels)
    r = subprocess.run(["uv", "run", "--with", "lxml", "python", str(SCRIPT), str(src), str(d / "out.json")],
                       capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=str(ROOT), env=ENV,
                       timeout=300)
    notes = json.loads((d / "out.json").read_text(encoding="utf-8")) if (d / "out.json").is_file() else None
    return r.returncode, notes


def the_run(notes, text):
    for entry in notes or []:
        for r in entry.get("runs") or []:
            if r.get("text") == text:
                return r
    return None


# Each case: (label, kind, body, styles part or None, the run's text, expected `resolved` or None,
#             (bold, italic) as extraction wrote them before 15.1, raw .xml input?)
B, I, B0 = "<w:b/>", "<w:i/>", '<w:b w:val="0"/>'
SZ = '<w:sz w:val="22"/>'
PLAIN_DEFAULT = style("paragraph", "Body", default=True)
CASES = [
    # ---------------------------------------------------------------- TP: each reported
    ("TP the document defaults make the run bold", "TP",
     para([run("sample one", SZ)]), styles(PLAIN_DEFAULT, doc_defaults=B), "sample one", {"bold": True},
     (False, False), False),
    ("TP a basedOn chain: the parent style is bold, the child names nothing", "TP",
     para([run("sample two", SZ)], pstyle="Child"),
     styles(PLAIN_DEFAULT + style("paragraph", "Parent", B) + style("paragraph", "Child", based="Parent")),
     "sample two", {"bold": True}, (False, False), False),
    ("TP the default paragraph style, where the paragraph names none, makes it italic", "TP",
     para([run("sample three", SZ)]), styles(style("paragraph", "Body", I, default=True)), "sample three",
     {"italic": True}, (False, False), False),
    ("TP a character-style chain: the parent character style is bold", "TP",
     para([run("sample four", '<w:rStyle w:val="EmphChild"/>')]),
     styles(PLAIN_DEFAULT + style("character", "EmphParent", B)
            + style("character", "EmphChild", based="EmphParent")), "sample four", {"bold": True},
     (False, False), False),
    ("TP the character style flips: bold in a plain paragraph", "TP",
     para([run("sample five", '<w:rStyle w:val="Strong1"/>')]),
     styles(PLAIN_DEFAULT + style("character", "Strong1", B)), "sample five", {"bold": True}, (False, False), False),
    ("TP the paragraph style SETS, not flips: a bold style over bold document defaults stays bold", "TP",
     para([run("sample six", SZ)], pstyle="Head1"),
     styles(PLAIN_DEFAULT + style("paragraph", "Head1", B), doc_defaults=B), "sample six", {"bold": True},
     (False, False), False),
    ("TP a chain repeating a value is rolled up, not flipped twice: still bold", "TP",
     para([run("sample seven", SZ)], pstyle="Head2"),
     styles(PLAIN_DEFAULT + style("paragraph", "Head1", B) + style("paragraph", "Head2", B, based="Head1")),
     "sample seven", {"bold": True}, (False, False), False),
    ("TP the paragraph mark is no level: a run with no rPr in a bold-mark paragraph is plain", "TP",
     para([run("sample eight")], mark=B), styles(PLAIN_DEFAULT), "sample eight", {"bold": False},
     (True, False), False),
    ("TP an unknown paragraph style falls to the default paragraph style, which is bold", "TP",
     para([run("sample nine", SZ)], pstyle="NoSuchStyle"), styles(style("paragraph", "Body", B, default=True)),
     "sample nine", {"bold": True}, (False, False), False),
    ("TP a basedOn cycle is cut, the bold it reaches kept, and the run finishes", "TP",
     para([run("sample ten", SZ)], pstyle="LoopA"),
     styles(PLAIN_DEFAULT + style("paragraph", "LoopA", based="LoopB") + style("paragraph", "LoopB", B, "LoopA")),
     "sample ten", {"bold": True}, (False, False), False),
    ("TP both at once: a bold italic style, both reported in one key", "TP",
     para([run("sample eleven", SZ)], pstyle="Both"), styles(PLAIN_DEFAULT + style("paragraph", "Both", B + I)),
     "sample eleven", {"bold": True, "italic": True}, (False, False), False),
    ("TP a character style's false LEAVES a bold paragraph style bold - it does not set it plain", "TP",
     para([run("sample sixteen", '<w:rStyle w:val="Unbold"/>')], pstyle="Head1"),
     styles(PLAIN_DEFAULT + style("paragraph", "Head1", B) + style("character", "Unbold", B0)),
     "sample sixteen", {"bold": True}, (False, False), False),
    ("TP a run in a text box takes its OWN paragraph's style, not the outer one's", "TP",
     para([run("outer words", SZ),
           '<w:r><w:pict><w:txbxContent>' + para([run("boxed words", SZ)], pstyle="Head1")
           + '</w:txbxContent></w:pict></w:r>']),
     styles(PLAIN_DEFAULT + style("paragraph", "Head1", B)), "boxed words", {"bold": True}, (False, False), False),
    # ---------------------------------------------------------------- FP: none reported
    ("FP a direct w:b w:val=0 defeats a bold paragraph style", "FP",
     para([run("sample twelve", B0)], pstyle="Head1"), styles(PLAIN_DEFAULT + style("paragraph", "Head1", B)),
     "sample twelve", None, (False, False), False),
    ("FP a run already bold, in a bold style", "FP",
     para([run("sample thirteen", B)], pstyle="Head1"), styles(PLAIN_DEFAULT + style("paragraph", "Head1", B)),
     "sample thirteen", None, (True, False), False),
    ("FP the paragraph mark's own rPr: a bold mark, a run with its own rPr, no style", "FP",
     para([run("sample fourteen", SZ)], mark=B), styles(PLAIN_DEFAULT), "sample fourteen", None,
     (False, False), False),
    ("FP the toggle pair cancels: a bold paragraph style and a bold character style", "FP",
     para([run("sample fifteen", '<w:rStyle w:val="Strong1"/>')], pstyle="Head1"),
     styles(PLAIN_DEFAULT + style("paragraph", "Head1", B) + style("character", "Strong1", B)),
     "sample fifteen", None, (False, False), False),
    ("FP a pStyle naming a CHARACTER style is ignored: the default paragraph style is plain", "FP",
     para([run("sample seventeen", SZ)], pstyle="Strong1"),
     styles(PLAIN_DEFAULT + style("character", "Strong1", B)), "sample seventeen", None, (False, False), False),
    # The next two carry a bold paragraph mark over a run with no rPr: any resolver that RAN would report it
    # (the mark is no level - the eighth TP), so their silence proves the resolver did not run.
    ("FP a raw .xml input: the cascade cannot be known, so no key", "FP",
     para([run("sample eighteen")], pstyle="Head1", mark=B), None, "sample eighteen", None, (True, False), True),
    ("FP an unreadable styles part: no key, never a guess", "FP",
     para([run("sample nineteen")], pstyle="Head1", mark=B), "<w:styles><w:style", "sample nineteen", None,
     (True, False), False),
    ("FP no styles part at all: the run's own properties, nothing differs", "FP",
     para([run("sample twenty", SZ)], pstyle="Head1"), None, "sample twenty", None, (False, False), False),
    ("FP a styles part the relationships name ELSEWHERE: unknown here, so no key", "FP",
     para([run("sample twenty-one")], pstyle="Head1", mark=B), None, "sample twenty-one", None, (True, False),
     False, RELS_ELSEWHERE),
    ("FP a basedOn naming a style of ANOTHER type is not followed", "FP",
     para([run("sample twenty-two", SZ)], pstyle="Odd"),
     styles(PLAIN_DEFAULT + style("character", "Strong1", B) + style("paragraph", "Odd", based="Strong1")),
     "sample twenty-two", None, (False, False), False),
    ("TP an unknown character style falls to the default character style, which is italic", "TP",
     para([run("sample twenty-three", '<w:rStyle w:val="NoSuchChar"/>')]),
     styles(PLAIN_DEFAULT + style("character", "DefChar", I, default=True)), "sample twenty-three",
     {"italic": True}, (False, False), False),
    ("TP where two paragraph styles claim to be the default, the last one wins", "TP",
     para([run("sample twenty-four", SZ)]),
     styles(style("paragraph", "First", default=True) + style("paragraph", "Second", B, default=True)),
     "sample twenty-four", {"bold": True}, (False, False), False),
]

print(f"  the script under test: {SCRIPT.relative_to(ROOT) if SCRIPT.is_relative_to(ROOT) else SCRIPT.name}")
try:
    for n, (label, kind, body, sx, text, want, emitted, as_xml, *rels) in enumerate(CASES, 1):
        rc, notes = extract(f"c{n:02d}", body, sx, as_xml, rels[0] if rels else None)
        r = the_run(notes, text)
        if not ok(f"{label} - extraction ran (rc 0) and wrote the run", rc == 0 and r is not None, f"rc={rc}"):
            continue
        got = r.get("resolved")
        ok(f"{label} - resolved {want if want is not None else 'ABSENT'}", got == want, f"got {got}")
        ok(f"{label} - KEYS bold/italic as before 15.1, {emitted}", (r.get("bold"), r.get("italic")) == emitted,
           f"got {(r.get('bold'), r.get('italic'))}")
        if got is not None:
            ok(f"{label} - KEYS resolved is the run's LAST key, so removing it leaves the old bytes",
               list(r)[-1] == "resolved", f"keys {list(r)}")

    # The positive control for the FP arm: the same unknowable inputs, given a readable styles part, DO report -
    # so an FP's silence is the rule, not a resolver that never fires.
    rc, notes = extract("control", para([run("sample control", SZ)], pstyle="Head1"),
                        styles(PLAIN_DEFAULT + style("paragraph", "Head1", B)))
    r = the_run(notes, "sample control")
    ok("CONTROL the FP inputs' paragraph, given its styles part, IS reported bold",
       r is not None and r.get("resolved") == {"bold": True}, f"got {r and r.get('resolved')}")
finally:
    shutil.rmtree(TMP, ignore_errors=True)
tp = sum(1 for c in CASES if c[1] == "TP")
print(f"\n  {len(CASES)} invented documents ({tp} TP, {len(CASES) - tp} FP) and 1 control, {args.variant} tree")
print(f"  {CHECKED} check(s), {len(FAIL)} failure(s)")
sys.exit(1 if FAIL else 0)
