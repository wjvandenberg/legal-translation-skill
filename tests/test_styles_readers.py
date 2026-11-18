# -*- coding: utf-8 -*-
"""test_styles_readers.py - sub-step 17.2: the two w:b readers reach a styles part; check 15 reads w:val
(PLAN-2-step-b.md section 3.17).

Since sub-step 16.3 apply writes a run's bold as a flag only where the styles do not already give it, so two
readers downstream of apply that read a run's OWN w:b - quality_check's check 15 (a definition with no bold term)
and reorder_definitions' get_bold_term (a "Term: meaning" definition) - could not see bold a paragraph or character
style gives. 17.2 gives each an optional --styles (a .docx or a styles.xml), read through extraction's resolver.
And check 15 counted a run carrying <w:b w:val="0"/> as bold: it now reads w:val, 0, false and off meaning NOT bold.
17.1 measured the corpus movement at 0 (check 15 flags 0 of 97 definition paragraphs before and after), so the true
positives here are invented:

  1  check 15, w:val: a term run carrying w:b off (0, false, off) is flagged; <w:b/> and w:val="1" are not
  2  check 15, --styles: a term bold by its CHARACTER style, and one bold by its PARAGRAPH style, are flagged
     without --styles (as before) and not with it, in both forms (styles.xml, .docx)
  3  check 15, the run's own w:b still decides: w:b off in a bold paragraph style is flagged even with --styles
  4  get_bold_term, --styles: a "Term: meaning" paragraph bold by its character style, and one by its paragraph
     style, found only with --styles, in both forms; a run's own w:b off in a bold style still not bold
  5  without --styles neither script prints a "Styles:" line; with it each says the styles were read
  6  --styles naming no file: a usage error, exit 2, from each script
  7  extract_paragraphs.py MISSING (a partial install) with --styles: each says so and reads as without

Invented words only, never anything from a real document.

    uv run --with lxml python tests/test_styles_readers.py
    uv run --with lxml python tests/test_styles_readers.py --variant us
    uv run --with lxml python tests/test_styles_readers.py --scripts <folder>   # a mutated or pinned copy's scripts
"""
import importlib.util
import io
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
VARIANT = sys.argv[sys.argv.index("--variant") + 1] if "--variant" in sys.argv else "uk"
SCRIPTS = (Path(sys.argv[sys.argv.index("--scripts") + 1]) if "--scripts" in sys.argv
           else ROOT / VARIANT / "scripts")
ENV = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1", PYTHONDONTWRITEBYTECODE="1")
WNS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
FAIL, CHECKED = [], 0


def ok(label, cond, detail=""):
    global CHECKED
    CHECKED += 1
    print(("  OK   " if cond else "  XX   ") + label + (f"   {detail}" if detail and not cond else ""))
    if not cond:
        FAIL.append(label)
    return cond


STYLES = (f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
          f'<w:styles xmlns:w="{WNS}">'
          '<w:docDefaults><w:rPrDefault><w:rPr/></w:rPrDefault></w:docDefaults>'
          '<w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/></w:style>'
          '<w:style w:type="paragraph" w:styleId="DefPara"><w:name w:val="Def Para"/><w:basedOn w:val="Normal"/>'
          '<w:rPr><w:b/></w:rPr></w:style>'
          '<w:style w:type="character" w:styleId="TermBold"><w:name w:val="Term Bold"/><w:rPr><w:b/></w:rPr>'
          '</w:style></w:styles>')


def run_xml(text, rpr="", ppr=""):
    return f'<w:r>{rpr}<w:t xml:space="preserve">{text}</w:t></w:r>'


def para(runs, pstyle=None):
    ppr = f'<w:pPr><w:pStyle w:val="{pstyle}"/></w:pPr>' if pstyle else ""
    return f"<w:p>{ppr}{''.join(runs)}</w:p>"


def document(paras):
    return (f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:document xmlns:w="{WNS}"><w:body>'
            + "".join(paras) + "</w:body></w:document>")


# check 15's definitions: the quoted term in its own run, 'means' after it
def qc_def(term, rpr="", pstyle=None):
    # in a bold paragraph style the quotes and the rest switch bold off, so only the term's run can carry it
    rest = '<w:rPr><w:b w:val="0"/></w:rPr>' if pstyle else ""
    return para([run_xml("“", rest), run_xml(term, f"<w:rPr>{rpr}</w:rPr>" if rpr else ""),
                 run_xml(f"” means the invented {term.lower()} thing.", rest)], pstyle)


QC_CASES = [  # term, rpr, pstyle, flagged without --styles, flagged with --styles
    ("Quobble", '<w:b w:val="0"/>', None, True, True),
    ("Frandle", '<w:b w:val="false"/>', None, True, True),
    ("Plimset", '<w:b w:val="off"/>', None, True, True),
    ("Grommick", "<w:b/>", None, False, False),
    ("Tarvelle", '<w:b w:val="1"/>', None, False, False),
    ("Zinnober", '<w:rStyle w:val="TermBold"/>', None, True, False),
    ("Huskaran", "", "DefPara", True, False),
    ("Morvetta", '<w:b w:val="0"/>', "DefPara", True, True),
]


def rd_para(term, rpr="", pstyle=None):
    # in a bold paragraph style the colon and the rest switch bold off, so the term ends at the colon
    rest = '<w:rPr><w:b w:val="0"/></w:rPr>' if pstyle else ""
    return para([run_xml(term, f"<w:rPr>{rpr}</w:rPr>" if rpr else ""), run_xml(":", rest),
                 run_xml(" the invented thing, as defined.", rest)], pstyle)


RD_CASES = [  # term, rpr, pstyle, found without --styles, found with --styles
    ("Zinnober", '<w:rStyle w:val="TermBold"/>', None, False, True),
    ("Huskaran", "", "DefPara", False, True),
    ("Morvetta", '<w:b w:val="0"/>', "DefPara", False, False),
    ("Grommick", "<w:b/>", None, True, True),
    ("Plimset", "", None, False, False),
]


def qc(scripts, doc, extra):
    r = subprocess.run([sys.executable, str(scripts / "quality_check.py"), str(doc), "--verbose"] + extra,
                       capture_output=True, text=True, encoding="utf-8", errors="replace", env=ENV, timeout=300)
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def rd(scripts, doc, extra):
    r = subprocess.run([sys.executable, str(scripts / "reorder_definitions.py"), str(doc), "--dry-run"] + extra,
                       capture_output=True, text=True, encoding="utf-8", errors="replace", env=ENV, timeout=300)
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def flagged(out, term):
    return any("No bold term in definition" in ln and term in ln for ln in out.splitlines())


def load_reorder(scripts):
    spec = importlib.util.spec_from_file_location("rd_under_test", str(scripts / "reorder_definitions.py"))
    mod = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(scripts))
    try:
        spec.loader.exec_module(mod)
    finally:
        sys.path.remove(str(scripts))
    return mod


print("=" * 96)
print(f"17.2: THE TWO w:b READERS REACH A STYLES PART; CHECK 15 READS w:val   [{VARIANT}]   scripts: "
      f"{'the tree' if '--scripts' not in sys.argv else 'a copy'}")
print("=" * 96)
from lxml import etree  # noqa: E402

with tempfile.TemporaryDirectory(prefix="styles-readers-") as td:
    td = Path(td)
    styles_xml = td / "styles.xml"
    styles_xml.write_bytes(STYLES.encode("utf-8"))
    docx = td / "styled.docx"
    with zipfile.ZipFile(docx, "w") as zf:
        zf.writestr("word/styles.xml", STYLES)
        zf.writestr("word/document.xml", document([para([run_xml("x")])]))
    # one document per case: quality_check prints at most five issues a check, so a shared document hides the sixth
    qc_docs = {}
    for t, r, s, _a, _b in QC_CASES:
        qc_docs[t] = td / f"qc-{t}.xml"
        qc_docs[t].write_bytes(document([qc_def(t, r, s)]).encode("utf-8"))
    qc_doc = qc_docs["Zinnober"]

    print("\n  check 15 (quality_check.py), cases 1 to 3:")
    for term, rpr, pstyle, without, with_ in QC_CASES:
        rc0, out0 = qc(SCRIPTS, qc_docs[term], [])
        rc1, out1 = qc(SCRIPTS, qc_docs[term], ["--styles", str(styles_xml)])
        rc2, out2 = qc(SCRIPTS, qc_docs[term], ["--styles", str(docx)])
        ok(f"{term}: three runs, no traceback", all("Traceback" not in o for o in (out0, out1, out2)),
           out0.strip()[-300:])
        shape = (rpr or "no run properties") + (f" in paragraph style {pstyle}" if pstyle else "")
        ok(f"{term} ({shape}): {'flagged' if without else 'not flagged'} without --styles",
           flagged(out0, term) == without)
        ok(f"{term}: {'flagged' if with_ else 'not flagged'} with --styles styles.xml", flagged(out1, term) == with_)
        ok(f"{term}: {'flagged' if with_ else 'not flagged'} with --styles .docx", flagged(out2, term) == with_)

    print("\n  get_bold_term (reorder_definitions.py), case 4:")
    mod = load_reorder(SCRIPTS)
    root = etree.fromstring(document([rd_para(t, r, s) for t, r, s, _a, _b in RD_CASES]).encode("utf-8"))
    ps = list(root.iter(f"{{{WNS}}}p"))
    has_styles = hasattr(mod, "use_styles")
    ok("reorder_definitions offers use_styles (the --styles reader)", has_styles)
    for form, path in (("none", None), ("styles.xml", styles_xml), (".docx", docx)):
        if path is not None:
            if not has_styles:
                continue
            mod.use_styles(str(path))
        elif has_styles:
            mod._STYLES_CASCADE = None
        for p, (term, rpr, pstyle, without, with_) in zip(ps, RD_CASES):
            want = without if path is None else with_
            got = mod.get_bold_term(p)
            ok(f"{term} ({rpr or 'no run properties'}{', ' + pstyle if pstyle else ''}), --styles {form}: "
               f"{'found' if want else 'not a bold term'}", (got == term) if want else (got is None), f"got {got!r}")
    if has_styles:
        mod._STYLES_CASCADE = None

    print("\n  what each script says, case 5:")
    rd_doc = td / "rd.xml"
    rd_doc.write_bytes(document([rd_para(t, r, s) for t, r, s, _a, _b in RD_CASES]).encode("utf-8"))
    rrc0, rout0 = rd(SCRIPTS, rd_doc, [])
    rrc1, rout1 = rd(SCRIPTS, rd_doc, ["--styles", str(styles_xml)])
    ok("reorder_definitions without --styles prints no 'Styles:' line", "Styles:" not in rout0)
    ok("reorder_definitions with --styles says the styles were read", "Styles: read from --styles" in rout1,
       rout1[-300:])
    rc0, out0 = qc(SCRIPTS, qc_doc, [])
    rc1, out1 = qc(SCRIPTS, qc_doc, ["--styles", str(styles_xml)])
    ok("quality_check without --styles prints no 'Styles:' line", "Styles:" not in out0)
    ok("quality_check with --styles says the styles were read", "Styles: read from --styles" in out1, out1[-300:])
    ok("quality_check's exit code is its verdict's: 2 with the finding, 0 once --styles clears it",
       rc0 == 2 and rc1 == 0, f"rc {rc0}, {rc1}")

    print("\n  --styles naming no file, case 6:")
    missing = str(td / "no-such-styles.xml")
    mrc, mout = qc(SCRIPTS, qc_doc, ["--styles", missing])
    ok("quality_check: exit 2, 'no such file'", mrc == 2 and "no such file" in mout, f"rc={mrc} {mout[-200:]}")
    mrc, mout = rd(SCRIPTS, rd_doc, ["--styles", missing])
    ok("reorder_definitions: exit 2, 'no such file'", mrc == 2 and "no such file" in mout, f"rc={mrc} {mout[-200:]}")

    print("\n  extract_paragraphs.py missing, case 7:")
    partial = td / "partial"
    shutil.copytree(SCRIPTS, partial)
    (partial / "extract_paragraphs.py").unlink()
    prc, pout = qc(partial, qc_doc, ["--styles", str(styles_xml)])
    ok("quality_check: says the sibling is missing, no traceback", "extract_paragraphs.py is missing" in pout
       and "Traceback" not in pout, pout[-300:])
    ok("quality_check: check 15 reads as without --styles", flagged(pout, "Zinnober"))
    prc, pout = rd(partial, rd_doc, ["--styles", str(styles_xml)])
    ok("reorder_definitions: says the sibling is missing, no traceback", "extract_paragraphs.py is missing" in pout
       and "Traceback" not in pout, pout[-300:])

print("\n" + "=" * 96)
print(f"{CHECKED} check(s), {len(FAIL)} failure(s)")
print("=" * 96)
for f in FAIL:
    print(f"  FAIL  {f}")
sys.exit(1 if FAIL else 0)
