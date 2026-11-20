# -*- coding: utf-8 -*-
"""test_layout_mode.py - step 18.2 (PLAN-2-step-b.md 3.18): tools/render_diff.py's layout mode, on SYNTHETIC
documents only -- every word below is invented, so the PDFs may be looked at; they are deleted all the same.

Each pair is a source and a hand-made "delivery" that either keeps the device's place on the page or loses it.
The layout functions are loaded from render_diff.py's own syntax tree (the script runs its comparison at import),
the device found in the source's XML, bookmarks set on COPIES, both exported by LibreOffice headless with the
bookmark-destination option, the destinations read back with re and zlib alone, then judged.

  L1  bucket 1 (D1): a leading-tab paragraph whose delivery lost a tab is MOVED; one whose tabs survive, its tab
      and text in ONE run (the split path), is same; the positive control -- the shape with a stop of its own --
      is found as the control, never as D1, and is same.
  L2  bucket 2 (D5): an empty run standing in for a page break -- the delivery's shorter text pulls the device
      paragraph back onto page 1 -- is MOVED; the identical delivery is same.
  L3  bucket 3 (D3): a cantSplit table the delivery's longer text pushes across a page boundary is MOVED; the
      identical delivery is same.
  L4  D2 and D4 are found and judged n/a, never moved; every bookmark set comes back as a destination.
  L5  the tool: --layout without --doc refuses (exit 2, nothing rendered); skill Step 7's --notes and --styles
      are passed to the reorder where the arm's reorder accepts them.

RED FIRST: LT_LAYOUT_TOOL=<e36b753's render_diff.py> -- the pin has no layout mode, so every arm fails; and the
mutant LAY_X_TOL = 1000.0 leaves L1's moved device unfound.

    uv run --with lxml python tests/test_layout_mode.py
"""
import ast
import io
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
import zlib
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.dont_write_bytecode = True
from lxml import etree  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
TOOL = Path(os.environ.get("LT_LAYOUT_TOOL") or ROOT / "tools" / "render_diff.py")
W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
FAIL, CHECKED = [], 0


def ok(label, cond, detail=""):
    global CHECKED
    CHECKED += 1
    print(f"  {'OK  ' if cond else 'XX  '} {label}" + (f"   ({detail})" if detail and not cond else ""))
    if not cond:
        FAIL.append(label)


def load():
    """render_diff.py's lay_* functions, LAY_* constants and to_pdf, compiled on their own."""
    tree = ast.parse(TOOL.read_text(encoding="utf-8"))
    keep = [n for n in tree.body if (isinstance(n, ast.FunctionDef) and (n.name.startswith("lay_") or n.name == "to_pdf"))
            or (isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id.startswith("LAY_") for t in n.targets))]
    ns = {"Path": Path, "re": re, "zlib": zlib, "zipfile": zipfile, "etree": etree, "subprocess": subprocess}
    exec(compile(ast.Module(body=keep, type_ignores=[]), str(TOOL), "exec"), ns)
    return ns


CT = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
      '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
      '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
      '<Default Extension="xml" ContentType="application/xml"/>'
      '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.'
      'wordprocessingml.document.main+xml"/></Types>')
RELS = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/'
        'officeDocument" Target="word/document.xml"/></Relationships>')
FILLER = "Lorem ipsum dolor sit amet consectetur adipiscing elit sed do eiusmod tempor incididunt ut labore."
TAB = "<w:r><w:tab/></w:r>"
EMPTY = "<w:p/>"


def para(text, ppr=""):
    return "<w:p>" + (f"<w:pPr>{ppr}</w:pPr>" if ppr else "") + f'<w:r><w:t xml:space="preserve">{text}</w:t></w:r></w:p>'


def docx(path, body):
    doc = (f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:document xmlns:w="{W}"><w:body>{body}'
           '<w:sectPr><w:pgSz w:w="11906" w:h="16838"/><w:pgMar w:top="1440" w:right="1440" w:bottom="1440" '
           'w:left="1440" w:header="708" w:footer="708" w:gutter="0"/></w:sectPr></w:body></w:document>')
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", CT)
        z.writestr("_rels/.rels", RELS)
        z.writestr("word/document.xml", doc)
    return path


def table(rows_text):
    cell = "".join(para(t) for t in rows_text)
    return ('<w:tbl><w:tblPr><w:tblW w:w="5000" w:type="pct"/></w:tblPr><w:tblGrid><w:gridCol w:w="9000"/></w:tblGrid>'
            '<w:tr><w:trPr><w:cantSplit/></w:trPr><w:tc><w:tcPr><w:tcW w:w="9000" w:type="dxa"/></w:tcPr>'
            + cell + '</w:tc></w:tr></w:tbl>')


def bucket1(lost):
    a = "<w:p>" + TAB + ("" if lost else TAB) + '<w:r><w:t>Signed for the first party</w:t></w:r></w:p>'
    b = '<w:p><w:r><w:tab/><w:tab/><w:t>Signed for the second party</w:t></w:r></w:p>'
    ctl = ('<w:p><w:pPr><w:tabs><w:tab w:val="left" w:pos="5040"/></w:tabs></w:pPr>' + TAB
           + '<w:r><w:t>Name of the witness</w:t></w:r></w:p>')
    return para(FILLER) + a + para(FILLER) + b + para(FILLER) + ctl


SHORT = "Lorem ipsum."
LONG = FILLER + " " + FILLER   # two lines: one FILLER is one 13.45 pt line, about 51 to a page


def bucket2(short):
    """The same paragraphs either way, as apply keeps them: two-line paragraphs leave the empty run to push the
    heading onto page 2; one-line paragraphs, the delivery that lost it, leave the heading on page 1."""
    return para(SHORT if short else LONG) * 20 + EMPTY * 12 + para("Heading after the empty run") + para(FILLER)


def bucket3(long):
    """One-line paragraphs leave room for the twelve-line row on page 1; two-line ones push it to page 2."""
    return (para(LONG if long else SHORT) * 22 + table([f"Row line {i}" for i in range(1, 13)])
            + para(FILLER))


def xml_only():
    br = '<w:r><w:br/></w:r>'
    return ('<w:p><w:pPr><w:jc w:val="both"/></w:pPr><w:r><w:t xml:space="preserve">Alpha beta gamma</w:t></w:r>'
            + br + '<w:r><w:t>delta</w:t></w:r></w:p>' + para("Name" + chr(0x3000) * 3 + "Title"))


def classify(ns, soffice, work, name, src_body, del_body):
    d = work / name
    d.mkdir()
    src, dlv = docx(d / "src.docx", src_body), docx(d / "del.docx", del_body)
    with zipfile.ZipFile(src) as z:
        sroot = etree.fromstring(z.read("word/document.xml"))
    devs = ns["lay_devices"](sroot, ns["lay_styles"](None))
    wanted = ns["lay_wanted"](devs)
    dests = {}
    for side, f in (("source", src), ("delivery", dlv)):
        out = d / side
        out.mkdir()
        mk = out / f"{side}.docx"
        ns["lay_marked_copy"](f, mk, wanted)
        pdf, _ = ns["to_pdf"](soffice, mk, out, ns["LAY_PDF_FILTER"])
        if pdf is None:
            return devs, None, 0, len(wanted)
        got, _ = ns["lay_destinations"](pdf)
        dests[side] = {k: v for k, v in got.items() if k.startswith(ns["LAY_PREFIX"])}
    back = min(len(dests["source"]), len(dests["delivery"]))
    return devs, ns["lay_judge"](devs, dests["source"], dests["delivery"]), back, len(wanted)


def verdicts(devs, judged, mech):
    return [m for dv, (_, m) in zip(devs, judged) if dv["mech"] == mech]


def main():
    print("STEP 18.2 - render_diff's layout mode, on synthetic documents")
    soffice = os.environ.get("LT_SOFFICE") or str(Path(os.environ.get("LOCALAPPDATA", "")) / "Programs"
                                                  / "LibreOffice" / "program" / "soffice.exe")
    if not Path(soffice).is_file():
        print("VOID - LibreOffice not found (set LT_SOFFICE). Nothing rendered, nothing proved.")
        return 1
    try:
        ns = load()
        need = ["lay_devices", "lay_styles", "lay_wanted", "lay_marked_copy", "lay_destinations", "lay_judge",
                "to_pdf", "LAY_PDF_FILTER", "LAY_PREFIX"]
        missing = [n for n in need if n not in ns]
    except Exception as exc:                                    # noqa: BLE001 -- reported as the arm's failure
        missing = [f"load failed: {type(exc).__name__}"]
    ok("the layout functions exist in render_diff.py", not missing, ", ".join(missing))
    if missing:
        print(f"\nFAIL - {len(FAIL)} of {CHECKED} checks")
        return 1
    work = Path(tempfile.mkdtemp(prefix="l18-test-"))
    try:
        devs, j, back, want = classify(ns, soffice, work, "b1", bucket1(False), bucket1(True))
        ok("L1 rendered, every bookmark back", j is not None and back == want, f"{back} of {want}")
        if j:
            ok("L1 the lost-tab device is D1 and MOVED, the kept one same", verdicts(devs, j, "D1") == [True, False],
               str(verdicts(devs, j, "D1")))
            ok("L1 the positive control is found as the control and stays same",
               verdicts(devs, j, "D1-control") == [False], str(verdicts(devs, j, "D1-control")))
            ok("L1 the control is bucket 'control', D1 bucket 1",
               {(dv["mech"], dv["bucket"]) for dv in devs} == {("D1", 1), ("D1-control", "control")})
        devs, j, back, want = classify(ns, soffice, work, "b1s", bucket1(False), bucket1(False))
        ok("L1 an unchanged delivery: nothing moved", j is not None and not any(m is True for _, m in j), str(j))
        for nm, mech, src, moved_del in (("b2", "D5", bucket2(False), bucket2(True)),
                                         ("b3", "D3", bucket3(False), bucket3(True))):
            devs, j, back, want = classify(ns, soffice, work, nm, src, moved_del)
            ok(f"{nm} rendered, every bookmark back", j is not None and back == want, f"{back} of {want}")
            ok(f"{nm} the device found is {mech}, once", [dv["mech"] for dv in devs] == [mech],
               str([dv["mech"] for dv in devs]))
            ok(f"{nm} the delivery that lost the device's page: MOVED", bool(j) and verdicts(devs, j, mech) == [True],
               str(j))
            devs, j, back, want = classify(ns, soffice, work, nm + "s", src, src)
            ok(f"{nm} the identical delivery: same", bool(j) and verdicts(devs, j, mech) == [False], str(j))
        devs, j, back, want = classify(ns, soffice, work, "x", xml_only(), xml_only())
        ok("L4 D2 and D4 found, D4 counting its three characters",
           sorted((dv["mech"], dv["n"]) for dv in devs) == [("D2", 1), ("D4", 3)], str(devs))
        ok("L4 both judged n/a, every bookmark back", bool(j) and [m for _, m in j] == ["n/a", "n/a"]
           and back == want, str(j))
    finally:
        shutil.rmtree(work, ignore_errors=True)
    lr = ns.get("lay_reordered")
    ok("L6 the reorder's moves are named, an in-place edit is not, a count change is unpairable",
       lr is not None and lr(["a", "b", "c", "d"], ["a", "c", "b", "d"]) == {1, 2}
       and lr(["a", "b"], ["a", "B"]) == set() and lr(["a"], ["a", "b"]) is None)
    lt = ns.get("lay_lead_tabs")
    two = etree.fromstring(f'<w:p xmlns:w="{W}"><w:r><w:tab/><w:t xml:space="preserve"> </w:t><w:tab/>'
                           '<w:t>a</w:t><w:tab/></w:r></w:p>')
    ok("L7 the leading tabs are counted up to the first non-blank text, not after it", lt is not None and lt(two) == 2)
    lb = ns.get("lay_lead_blanks")
    ok("L7 the blanks before the first text are counted, tabs not", lb is not None and lb(two) == 1)
    src = TOOL.read_text(encoding="utf-8")
    fn = re.search(r"def run_post_process_doc\(.*?\n(?=def )", src, re.S)
    ok("L5 the reorder gets skill Step 7's --notes and --styles",
       bool(fn) and '"--notes"' in fn.group(0) and '"--styles"' in fn.group(0))
    r = subprocess.run([sys.executable, str(TOOL), "--layout"], capture_output=True, text=True, encoding="utf-8",
                       errors="replace", cwd=str(ROOT), env=dict(os.environ, LT_SOFFICE=soffice))
    ok("L5 --layout without --doc refuses, exit 2", r.returncode == 2 and "REFUSED: --layout needs --doc" in r.stdout,
       f"exit {r.returncode}")
    print(f"\n{'PASS' if not FAIL else 'FAIL'} - {CHECKED - len(FAIL)} of {CHECKED} checks")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
