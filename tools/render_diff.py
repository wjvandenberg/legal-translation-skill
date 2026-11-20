# -*- coding: utf-8 -*-
"""THE RENDERED PAGE COMPARISON — CLAUDE.md 5.2's gate, made runnable.

Section 5.2 makes a "rendered PDF visual diff against the source, page by page, BOTH
documents" a condition of done for every step, and 2.4 item 4 calls the rendered diff the
PRIMARY instrument rather than a final check. No tool existed for it. This is that tool.
(Those two numbers read 5.3 and 2.5 until 2026-09-10: the 2026-09-09 charter mapping moved
them, and a stale section sign resolves against a real but WRONG section, silently.)

ONE CONSTRAINT SHAPES THE WHOLE DESIGN, AND IT IS A CONFIDENTIALITY CONSTRAINT RATHER THAN A
TECHNICAL ONE. A rendered page of a corpus document is client text as an image, and CLAUDE.md
6.4 says session metadata is reachable by neither the scanners nor the location rule, so there
is no after-the-fact remedy and it cannot be un-said. THEREFORE CLAUDE MAY NEVER LOOK AT A
RENDER OF A REAL DOCUMENT.

  THE RULE ITSELF NOW LIVES IN CLAUDE.md 5.6, WHICH IS ROUTE 1 AND ALWAYS LOADS. Until
  2026-09-10 this docstring was its ONLY tracked home, and a docstring loads only if somebody
  opens this one file -- weaker than a path-scoped rule, for a confidentiality rule whose
  failure cannot be undone. This paragraph is the pointer that relocation leaves behind; it
  is not the copy of record. If the two ever disagree, 5.6 wins.

The gate splits in two:

  --doc ID       REAL CORPUS. Renders outside the repository, compares pages MECHANICALLY,
                 prints percentages and page counts, then DELETES every image. No page is
                 ever displayed, kept or committed. A human may look; this tool may not show.
  --fixture N    SYNTHETIC FIXTURE. No client text exists in it, so the PNGs are written to
                 gitignored temp/render/ and CAN be looked at. This is where a genuine visual
                 inspection happens.

WHICH COMPARISON ACTUALLY MEANS SOMETHING, because "source against target" cannot be a pixel
diff. The target is TRANSLATED: nearly every glyph differs, so a pixel comparison against the
source measures the translation, not the pipeline. What isolates this step is:

  OLD vs NEW deliverable   same document, same notes, same language, ONE variable: the code.
                           This is the diff that shows what step 6 changed on the page.
  source vs NEW page count a page count that moves is a layout red flag and needs no pixels.

DUPLICATION DECLARED RATHER THAN HIDDEN: the source-matching helpers below are copied from
tools/apply_corpus_diff.py, because that file does its work at module level and so cannot be
imported without running a full 13-document comparison. Consolidating both into one module is
a real improvement and is recorded as an open item rather than done here, where it would mean
re-verifying a committed and green instrument.

    uv run --with pymupdf --with lxml python tools/render_diff.py --fixture anchors-and-tabs
    uv run --with pymupdf --with lxml python tools/render_diff.py --doc D06 --doc D05
"""
import argparse
import atexit
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import zipfile
import zlib
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.dont_write_bytecode = True
os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")

from lxml import etree

from keep_declarations import write_keep_declarations

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tests"))
from read_receipt import file_receipt, lexicons_beside  # noqa: E402  (apply refuses to start without skill Step 3's receipt, C26)
W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
from sibling_dirs import corpus_dirs, logs_dir  # noqa: E402  (register I-40)
LOGS = logs_dir()
SCRIPT = "apply_translations_textmatch.py"
# PINNED TO A COMMIT, NEVER TO A BRANCH NAME OR HEAD -- CLAUDE.md 5.3.
#
# MOVED TO b47603d ON 2026-09-24, the squash-merge of branch 10 slice 4 -- the page-break
# pass inserts nothing, the principle every pass obeys, and the detections in the journal
# (PR #105) -- and the LAST COMMIT THAT TOUCHED EITHER TREE. It is also the merge that CLOSES
# BRANCH 10, so this is the baseline branch 11 inherits. DERIVED, NOT READ OFF THE MERGE
# MESSAGE: `git log --oneline -1 -- uk us` returns it. A pin left at the previous baseline
# reports the merged branch's own work as movement belonging to whatever branch runs next,
# and the branch that inherits it cannot tell.
#
# AND SINCE SLICE 3a THE FIXTURE PATH CAN DRIVE post_process DIRECTLY, via
# --post-process. In that mode the baseline arm swaps post_process.py and its siblings
# rather than the apply script: swapping a script the run never executes made both arms
# identical and reported the page UNCHANGED, which is indistinguishable from a fix that
# worked. WHICH SCRIPT THE BASELINE SWAPS FOLLOWS WHICH SCRIPT THE RUN DRIVES.
#
# AT THIS PIN ALL THREE post_process FIXTURES READ THE SAME ON BOTH ARMS --
# italic-declared, lexicon-choice and schedule-breaks -- because 3a's, 3b's and 4's code is
# now the baseline. That is correct, not a regression. For the DEFAULT fixture path the
# all-quiet notice is still expected: no slice of branch 10 touched apply.
#
# AND ONE FLAG'S PREMISE DIED WITH THIS MOVE: --expect-pages-move INVERTS the old -> new
# page-count assertion and requires the counts to DIFFER, which is true only while the old
# arm still imposes B7's page. Against b47603d it no longer does, so `--post-process
# --fixture schedule-breaks --expect-pages-move schedule-breaks` now FAILS by design, 3 -> 3,
# its line reading as though the fix did nothing. The byte-identity NOTE printed above it
# says why, so this is loud and explained rather than silent, which is what verification
# rule 4 (.claude/rules/verification.md) asks of a check whose premise has died. The READ-ME
# below therefore names the baseline that still has the defect: LT_BASELINE_REF=6d8bbab,
# the last merge before slice 4, which renders 4 -> 3 and passes. Without the flag,
# schedule-breaks passes at this pin, 3 -> 3, like the other two fixtures. All three runs
# were measured at slice 4's close and are recorded in its commit.
#
# THE CARRIERS ARE ENUMERATED, NEVER COUNTED FROM MEMORY. `git grep -F <old sha>` found
# THREE PINS at this close, as at slices 3a's and 3b's, and more MENTIONS than that -- the
# charter and the plan name the old sha as history, and so does THIS FILE's READ-ME text,
# twice now: once for where slice 4's suite was proved red, once for the baseline that
# still shows the defect. A close that "moves every match" would have rewritten both. The
# instruction is still not "move them all": tools/hf_corpus_diff.py is FIXED at ae48f6d and
# three suites at 2178cce, each for a reason in its own block; and
# tests/test_change_journal.py's arm 6 is NEITHER -- it stays at 5107aaf, a decision
# RE-TAKEN at this close on a measurement and recorded in its own block rather than here.
#
# THIS BLOCK IS REWRITTEN ON EVERY MOVE RATHER THAN APPENDED TO, because it has gone stale
# before and been caught -- once naming a commit as "the merge-base of this branch" long after
# it was not, once reading "Moved to 049484e" five lines above a pin that said 2a71e71, and at
# slice 3a claiming that arm 0 "reports VOID" where the code beside it prints a NOTICE.
# NOTHING CHECKS A COMMENT, so a stale one is indistinguishable from a current one. Re-derive
# every claim in it on the commit that moves the pin.
REF = os.environ.get("LT_BASELINE_REF", "b47603d")
DPI = int(os.environ.get("LT_RENDER_DPI", "100"))
# Stamped ONCE per run and written into every manifest, so a reviewer can tell at a
# glance whether the pages in front of them belong to the run being discussed.
STAMP = time.strftime("%Y-%m-%d %H:%M:%S")

SOFFICE_CANDIDATES = [
    os.environ.get("LT_SOFFICE", ""),
    r"C:\Program Files\LibreOffice\program\soffice.exe",
    r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
    "soffice",
]


def find_soffice():
    for c in SOFFICE_CANDIDATES:
        if not c:
            continue
        if c == "soffice":
            w = shutil.which("soffice")
            if w:
                return w
        elif Path(c).is_file():
            return c
    return None


def para_texts(xml_bytes):
    """apply's own get_paragraph_text, per paragraph. w:t only; NO space at a tab."""
    root = etree.fromstring(xml_bytes)
    out = []
    for p in root.iter(f"{{{W}}}p"):
        pieces = []
        for el in p.iter():
            tag = etree.QName(el).localname
            if tag == "t" and el.text:
                pieces.append(el.text)
            elif tag == "br" and el.get(f"{{{W}}}type", "") != "page":
                pieces.append("\n")
        out.append("".join(pieces).strip())
    return out


_CACHE = {}


def pick_source_docx(wd, notes, extra_dirs):
    wanted = {(e.get("text") or "").strip() for e in notes if (e.get("text") or "").strip()}
    if not wanted:
        return None, 0.0
    best, frac = None, 0.0
    for group in [sorted(wd.glob("*.docx"))] + [sorted(d.glob("*.docx")) for d in extra_dirs]:
        for cand in group:
            key = str(cand)
            if key not in _CACHE:
                try:
                    with zipfile.ZipFile(cand) as z:
                        _CACHE[key] = set(para_texts(z.read("word/document.xml"))) \
                            if "word/document.xml" in z.namelist() else None
                except Exception:
                    _CACHE[key] = None
            if not _CACHE[key]:
                continue
            f = len(wanted & _CACHE[key]) / len(wanted)
            if f > frac:
                best, frac = cand, f
        if frac >= 0.9:
            break
    return best, frac


def to_pdf(soffice, docx_path, outdir, flt="pdf"):
    """Convert with a PRIVATE user profile, so this cannot collide with a running Office. flt is the
    --convert-to argument: the layout mode passes LAY_PDF_FILTER, which keeps bookmark destinations (18.2)."""
    prof = (outdir / "loprofile").as_uri()
    r = subprocess.run(
        [soffice, f"-env:UserInstallation={prof}", "--headless", "--norestore",
         "--convert-to", flt, "--outdir", str(outdir), str(docx_path)],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=900)
    pdf = outdir / (docx_path.stem + ".pdf")
    return (pdf if pdf.is_file() else None), r


def page_hashes(pdf_path):
    """Render every page and return (hash, raw bytes, width, height) per page."""
    import pymupdf
    out = []
    with pymupdf.open(pdf_path) as doc:
        for page in doc:
            pm = page.get_pixmap(dpi=DPI)
            raw = pm.samples
            out.append((hashlib.sha256(raw).hexdigest(), raw, pm.width, pm.height, pm.n))
    return out


def pixel_delta(a, b):
    """Fraction of differing bytes between two same-size pixmaps, or None if incomparable."""
    if a[2] != b[2] or a[3] != b[3] or a[4] != b[4]:
        return None
    ra, rb = a[1], b[1]
    if len(ra) != len(rb):
        return None
    diff = sum(1 for x, y in zip(ra, rb) if x != y)
    return diff / len(ra) if ra else 0.0


# =========================================================================================
# STEP 18.2 -- THE LAYOUT MODE (PLAN-2-step-b.md 3.18). Each layout device 18.1's inventory counts, found in the
# SOURCE's XML, then placed on the page in the source's render and in the delivery's: a bookmark is set on the
# device's paragraph in a COPY of each document -- never the delivered file -- the copy is exported by LibreOffice
# headless with ExportBookmarksToPDFDestination (a plain export carries no destination, 18.1 (b)), and each
# destination's page and position is read back with re and zlib alone. Numbers only; every PDF is deleted.
#
# WHAT "MOVED" MEANS, PER MECHANISM -- a translation reflows every page, so a raw position always moves; each test
# below asks the one question the device exists to answer, and a "moved" is a page a reader must look at, never a
# defect proved:
#   D1  (bucket 1) a paragraph whose first text follows tabs, no tab stop of its own: the x where its text starts,
#       source against delivery, more than LAY_X_TOL points apart. D1-control, the same shape WITH a stop of its
#       own (D01's blocks), is measured the same way and must stay silent.
#   D5  (bucket 2) two or more empty paragraphs before a non-empty one, no page break: whether a page boundary
#       falls between the paragraph before the run and the run's last empty paragraph, and between that and the
#       device paragraph -- the pair of answers, source against delivery.
#   D3  (bucket 3) a table with a cantSplit row: whether a page boundary falls between the paragraph before the
#       first such row and the row's first paragraph, source against delivery.
#   D2, D4 (bucket 3) decided by the XML (18.3's shapes), so placed on the page and never judged "moved".
#   D6  (bucket 3) an exact-line-height paragraph whose largest direct run grew -- XML only, counted here.
# =========================================================================================
LAY_PREFIX = "lt18d"  # letters and digits only: LibreOffice writes "_" in a destination name as #5F
LAY_X_TOL = 1.0
LAY_PDF_FILTER = 'pdf:writer_pdf_Export:{"ExportBookmarksToPDFDestination":{"type":"boolean","value":"true"}}'
LAY_PAD = (chr(0x3000), chr(0xFF3F))
LAY_JUST = {"both", "distribute", "thaiDistribute", "lowKashida", "mediumKashida", "highKashida"}
LAY_BUCKET = {"D1": 1, "D1-control": "control", "D5": 2, "D3": 3, "D2": 3, "D4": 3, "D6": 3}


def lay_q(tag):
    return "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}" + tag


def lay_val(el):
    return el.get(lay_q("val")) if el is not None else None


def lay_styles(styles_xml):
    """(style element by id, the default paragraph style's id) -- for alignment and line rule only."""
    by, default_p = {}, None
    if styles_xml:
        for s in etree.fromstring(styles_xml).iter(lay_q("style")):
            by[s.get(lay_q("styleId"))] = s
            if s.get(lay_q("type")) == "paragraph" and s.get(lay_q("default")) in ("1", "true"):
                default_p = s.get(lay_q("styleId"))
    return by, default_p


def lay_resolved(p, styles, child, attr):
    """The paragraph's own pPr/child@attr, else its style chain's (basedOn), else the default paragraph style's."""
    by, default_p = styles
    ppr = p.find(lay_q("pPr"))
    if ppr is not None:
        c = ppr.find(lay_q(child))
        if c is not None and c.get(lay_q(attr)) is not None:
            return c.get(lay_q(attr))
    sid = lay_val(ppr.find(lay_q("pStyle"))) if ppr is not None else None
    sid, seen = sid or default_p, []
    while sid and sid in by and sid not in seen:
        seen.append(sid)
        sp = by[sid].find(lay_q("pPr"))
        c = sp.find(lay_q(child)) if sp is not None else None
        if c is not None and c.get(lay_q(attr)) is not None:
            return c.get(lay_q(attr))
        sid = lay_val(by[sid].find(lay_q("basedOn")))
    return None


def lay_atoms(p):
    """(kind, text) in order: text, tab (a rendered tab, never a stop), br (a manual line break)."""
    out = []
    for el in p.iter():
        if el.tag == lay_q("t") and el.text:
            out.append(("text", el.text))
        elif el.tag == lay_q("tab") and el.getparent() is not None and el.getparent().tag == lay_q("r"):
            out.append(("tab", "\t"))
        elif el.tag == lay_q("br") and el.get(lay_q("type"), "textWrapping") == "textWrapping":
            out.append(("br", ""))
    return out


def lay_leading_tab(p):
    for kind, s in lay_atoms(p):
        if kind == "tab":
            return True
        if kind == "text" and s.strip():
            return False
    return False


def lay_own_stops(p):
    ppr = p.find(lay_q("pPr"))
    tabs = ppr.find(lay_q("tabs")) if ppr is not None else None
    return tabs is not None and len(tabs.findall(lay_q("tab"))) > 0


def lay_text(p):
    return "".join(t.text or "" for t in p.iter(lay_q("t")))


def lay_is_empty(p):
    if lay_text(p).strip():
        return False
    return not any(next(p.iter(lay_q(tag)), None) is not None for tag in ("drawing", "pict", "object"))


def lay_has_break(p):
    if p is None or p.tag != lay_q("p"):
        return False
    if any(br.get(lay_q("type")) == "page" for br in p.iter(lay_q("br"))):
        return True
    ppr = p.find(lay_q("pPr"))
    if ppr is None:
        return False
    pbb = ppr.find(lay_q("pageBreakBefore"))
    return (pbb is not None and lay_val(pbb) not in ("0", "false")) or ppr.find(lay_q("sectPr")) is not None


def lay_lead_tabs(p):
    """How many tabs come before a paragraph's first non-blank text -- a number, never the text."""
    n = 0
    for kind, s in lay_atoms(p):
        if kind == "tab":
            n += 1
        elif kind == "text" and s.strip():
            break
    return n


def lay_lead_blanks(p):
    """How many blank characters (spaces and the like, never a tab) come before a paragraph's first non-blank text --
    a number, never the text: what else, beside the tab count, moves where the text starts."""
    n = 0
    for kind, s in lay_atoms(p):
        if kind == "text":
            if s.strip():
                return n + len(s) - len(s.lstrip())
            n += len(s)
    return n


def lay_max_sz(p):
    v = [int(s.get(lay_q("val"))) for s in p.iter(lay_q("sz")) if s.getparent().tag == lay_q("rPr")
         and s.getparent().getparent().tag == lay_q("r") and (s.get(lay_q("val")) or "").isdigit()]
    return max(v) if v else None


def lay_devices(root, styles):
    """Every layout device in a document, from its XML alone, as 18.1's inventory reads them. Each is a dict:
    mech, bucket, and marks -- {role: paragraph index in document order}, roles 'dev' (and 'prev', 'last' where
    the question is a page boundary); 'n' is the instance count it stands for (D4: padding characters)."""
    paras = list(root.iter(lay_q("p")))
    at = {id(p): i for i, p in enumerate(paras)}
    devs = []
    for i, p in enumerate(paras):
        if lay_leading_tab(p):
            devs.append({"mech": "D1-control" if lay_own_stops(p) else "D1", "marks": {"dev": i}, "n": 1})
        if lay_resolved(p, styles, "jc", "val") in LAY_JUST and any(k == "br" for k, _ in lay_atoms(p)):
            devs.append({"mech": "D2", "marks": {"dev": i}, "n": 1})
        pads = sum(lay_text(p).count(ch) for ch in LAY_PAD)
        if pads:
            devs.append({"mech": "D4", "marks": {"dev": i}, "n": pads})
    body = root.find(lay_q("body"))
    kids = [k for k in body if k.tag in (lay_q("p"), lay_q("tbl"))] if body is not None else []
    i = 0
    while i < len(kids):
        if kids[i].tag == lay_q("p") and lay_is_empty(kids[i]):
            j = i
            while j < len(kids) and kids[j].tag == lay_q("p") and lay_is_empty(kids[j]):
                j += 1
            run, nxt = kids[i:j], (kids[j] if j < len(kids) else None)
            prev = kids[i - 1] if i > 0 else None
            if (len(run) >= 2 and nxt is not None and nxt.tag == lay_q("p") and not any(map(lay_has_break, run))
                    and not lay_has_break(prev) and not lay_has_break(nxt)):
                first = at[id(run[0])]
                devs.append({"mech": "D5", "n": 1, "marks": {"prev": first - 1 if first else None,
                                                            "last": at[id(run[-1])], "dev": at[id(nxt)]}})
            i = j
        else:
            i += 1
    for t in root.iter(lay_q("tbl")):
        rows = [tr for tr in t.findall(lay_q("tr")) if tr.find(lay_q("trPr")) is not None
                and tr.find(lay_q("trPr")).find(lay_q("cantSplit")) is not None
                and lay_val(tr.find(lay_q("trPr")).find(lay_q("cantSplit"))) not in ("0", "false")]
        first = next(rows[0].iter(lay_q("p")), None) if rows else None
        if first is not None:
            k = at[id(first)]
            devs.append({"mech": "D3", "n": 1, "marks": {"prev": k - 1 if k else None, "dev": k}})
    for d in devs:
        d["bucket"] = LAY_BUCKET[d["mech"]]
    return devs


def lay_mark(root, wanted):
    """Set a bookmark on each wanted paragraph of a COPY's tree: wanted is [(paragraph index, name, after_tabs)].
    after_tabs puts it before the first run carrying non-blank text, splitting that run where tabs precede its
    text in the same run, so the destination's x is where the text starts; otherwise it opens the paragraph.
    Rendering is unchanged by either. Returns the number set."""
    paras = list(root.iter(lay_q("p")))
    ids = [int(b.get(lay_q("id"))) for b in root.iter(lay_q("bookmarkStart")) if (b.get(lay_q("id")) or "").isdigit()]
    nid, done = max(ids + [0]) + 1000, 0
    for idx, name, after_tabs in wanted:
        if idx is None or not 0 <= idx < len(paras):
            continue
        p = paras[idx]
        start = etree.Element(lay_q("bookmarkStart"))
        start.set(lay_q("id"), str(nid))
        start.set(lay_q("name"), name)
        end = etree.Element(lay_q("bookmarkEnd"))
        end.set(lay_q("id"), str(nid))
        nid += 1
        run = None
        if after_tabs:
            # the paragraph's OWN runs: a text box anchored in it holds paragraphs of its own (review fix)
            run = next((r for r in p.iter(lay_q("r")) if next(r.iterancestors(lay_q("p")), None) is p
                        and any((t.text or "").strip() for t in r.iter(lay_q("t")))), None)
        if run is not None:
            kids = list(run)
            first_t = next(k for k in kids if k.tag == lay_q("t") and (k.text or "").strip())
            lead = [k for k in kids[:kids.index(first_t)] if k.tag == lay_q("tab")]
            if lead:
                head = etree.Element(lay_q("r"))
                rpr = run.find(lay_q("rPr"))
                if rpr is not None:
                    head.append(etree.fromstring(etree.tostring(rpr)))
                for k in kids[:kids.index(first_t)]:
                    if k.tag != lay_q("rPr"):
                        head.append(k)
                run.addprevious(head)
            run.addprevious(start)
            run.addnext(end)
        else:
            ppr = p.find(lay_q("pPr"))
            pos = 1 if ppr is not None and len(p) and p[0] is ppr else 0
            p.insert(pos, start)
            p.insert(pos + 1, end)
        done += 1
    return done


def lay_marked_copy(src_docx, out_docx, wanted):
    """A copy of src_docx whose document.xml carries the bookmarks; every other part copied byte for byte. Written
    once, to a new path beside nothing that ships -- never a delivered file changed."""
    with zipfile.ZipFile(src_docx) as z:
        root = etree.fromstring(z.read("word/document.xml"))
        n = lay_mark(root, wanted)
        payload = etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True)
        with zipfile.ZipFile(out_docx, "w", zipfile.ZIP_DEFLATED) as zout:
            for item in z.infolist():
                zout.writestr(item, payload if item.filename == "word/document.xml" else z.read(item.filename))
    return n


def lay_pdf_objects(data):
    """{object number: bytes}, from plain objects and from FlateDecode object streams -- the standard library only."""
    objs = {}
    for m in re.finditer(rb"(\d+)\s+0\s+obj(.*?)endobj", data, re.S):
        objs[int(m.group(1))] = m.group(2)
    for body in list(objs.values()):
        if b"/ObjStm" not in body:
            continue
        s = lay_pdf_stream(body)
        fm = re.search(rb"/First\s+(\d+)", body)
        if s is None or fm is None:
            continue
        first = int(fm.group(1))
        head = s[:first].split()
        pairs = [(int(head[i]), int(head[i + 1])) for i in range(0, len(head) - 1, 2)]
        for k, (on, off) in enumerate(pairs):
            end = pairs[k + 1][1] if k + 1 < len(pairs) else len(s) - first
            objs[on] = s[first + off:first + end]
    return objs


def lay_pdf_stream(body):
    m = re.search(rb"stream\r?\n(.*?)\r?\nendstream", body, re.S)
    if not m:
        return None
    if b"/FlateDecode" in body:
        try:
            return zlib.decompress(m.group(1))
        except zlib.error:
            return None
    return m.group(1)


def lay_destinations(pdf_path):
    """{destination name: (page number from 1, x, y)} read with re and zlib alone, and the page count; the names a
    named-destination array or a /Dests dictionary carries, each resolved through the page tree's order."""
    objs = lay_pdf_objects(Path(pdf_path).read_bytes())
    cat = next((b for b in objs.values() if re.search(rb"/Type\s*/Catalog", b)), None)
    pm = re.search(rb"/Pages\s+(\d+)\s+0\s+R", cat or b"")
    if pm is None:
        return {}, 0
    order, stack = [], [int(pm.group(1))]
    while stack:
        n = stack.pop(0)
        b = objs.get(n, b"")
        if re.search(rb"/Type\s*/Pages", b):
            km = re.search(rb"/Kids\s*\[(.*?)\]", b, re.S)
            stack = [int(k) for k in re.findall(rb"(\d+)\s+0\s+R", km.group(1) if km else b"")] + stack
        else:
            order.append(n)
    xyz = rb"\[\s*(\d+)\s+0\s+R\s*/XYZ\s+([-\d.]+)\s+([-\d.]+)"
    found = {}
    for b in objs.values():
        for nm, pg, x, y in re.findall(rb"\(([^)]*)\)\s*" + xyz, b):
            found[nm.decode("latin-1")] = (int(pg), float(x), float(y))
        for nm, pg, x, y in re.findall(rb"/([A-Za-z0-9_#.]+)\s*" + xyz, b):
            found.setdefault(re.sub(r"#([0-9A-Fa-f]{2})", lambda h: chr(int(h.group(1), 16)), nm.decode("latin-1")),
                             (int(pg), float(x), float(y)))
    for b in objs.values():
        for nm, ref in re.findall(rb"\(([^)]*)\)\s*(\d+)\s+0\s+R", b):
            m = re.search(xyz, objs.get(int(ref), b""))
            if m:
                found.setdefault(nm.decode("latin-1"), (int(m.group(1)), float(m.group(2)), float(m.group(3))))
    return ({k: (order.index(v[0]) + 1, v[1], v[2]) for k, v in found.items() if v[0] in order}, len(order))


def lay_wanted(devs):
    """The bookmarks one document needs: one per (device, role), named by device number and role."""
    return [(d["marks"][role], f"{LAY_PREFIX}{k}r{role}", role == "dev" and d["mech"] in ("D1", "D1-control"))
            for k, d in enumerate(devs) for role in sorted(d["marks"]) if d["marks"][role] is not None]


def lay_judge(devs, src_dest, del_dest):
    """Per device: (pages source -> delivery of its 'dev' paragraph, moved) -- moved True, False, 'n/a' for an
    XML-decided device, or 'unread' where a destination it needs did not come back on either side."""
    out = []
    for k, d in enumerate(devs):
        def get(dest, role):
            return dest.get(f"{LAY_PREFIX}{k}r{role}") if d["marks"].get(role) is not None else None
        sd, dd = get(src_dest, "dev"), get(del_dest, "dev")
        pages = (sd[0] if sd else None, dd[0] if dd else None)
        if d["mech"] in ("D2", "D4"):
            out.append((pages, "n/a" if sd and dd else "unread"))
            continue
        if not (sd and dd):
            out.append((pages, "unread"))
            continue
        if d["mech"] in ("D1", "D1-control"):
            out.append((pages, abs(sd[1] - dd[1]) > LAY_X_TOL))
            continue
        roles = ["prev", "last", "dev"] if d["mech"] == "D5" else ["prev", "dev"]
        roles = [r for r in roles if d["marks"].get(r) is not None]
        sides = []
        for dest in (src_dest, del_dest):
            got = [get(dest, r) for r in roles]
            sides.append(None if None in got else tuple(b[0] > a[0] for a, b in zip(got, got[1:])))
        out.append((pages, "unread" if None in sides else sides[0] != sides[1]))
    return out


def lay_reordered(applied_texts, final_texts):
    """The paragraph positions the definitions reorder moved: where apply's output and the delivery differ in text
    AND apply's text sits at another position of the delivery. A text post_process changed in place stays paired;
    a moved paragraph cannot be paired by position, so a device on it is reported 'unpaired', never judged."""
    if len(applied_texts) != len(final_texts):
        return None
    where = {}
    for j, t in enumerate(final_texts):
        where.setdefault(t, set()).add(j)
    return {i for i, (a, f) in enumerate(zip(applied_texts, final_texts)) if a != f and where.get(a, set()) - {i}}


def lay_d6_grown(src_root, del_root, styles, skip=frozenset()):
    """D6's hazard, XML only: exact-line-height paragraphs, paired by position (the reordered ones skipped), whose
    largest direct run grew."""
    sps, dps = list(src_root.iter(lay_q("p"))), list(del_root.iter(lay_q("p")))
    if len(sps) != len(dps):
        return None
    n = 0
    for i, (sp, dp) in enumerate(zip(sps, dps)):
        if i not in skip and lay_resolved(sp, styles, "spacing", "lineRule") == "exact":
            a, b = lay_max_sz(sp), lay_max_sz(dp)
            n += a is not None and b is not None and b > a
    return n


def keep_dir(logs, label, variant):
    """Where --keep-into-logs writes one document's pages: named by the document AND the variant, so a uk
    and a us run of the same document land in two folders (register I-33 -- one folder for both meant
    the second run cleared the first's pages)."""
    return Path(logs) / "branch6-render" / (label.replace(" ", "").replace("#", "n") + "-" + variant)


def keep_chain(post_process):
    return "apply -> " + ("post_process -> reorder -> " if post_process else "") + "repack"


def keep_note(stamp, label, variant, ref, post_process, under_review, written, changed):
    """READ-ME.txt beside the kept pages, GENERATED from the run's own facts plus the one line the
    operator gives with --under-review. Register I-33: the note was hand-written, described the change
    under review four changes in a row, and nothing checked it -- so it said what a PREVIOUS change was
    and sent the reader looking for something already in -old. A fact the run knows is never typed."""
    chain = keep_chain(post_process)
    return "\n".join([
        "RENDERED COMPARISON -- this note is GENERATED by tools/render_diff.py; do not edit it.",
        "",
        f"under review:  {under_review.strip()}",
        f"document:      {label}",
        f"variant:       {variant}",
        f"pin (-old):    {ref}  -- the scripts tree at that commit; -old is 'before the change under",
        "               review', never 'before the step'",
        f"chain run:     {chain}  (each arm, the same chain)",
        f"written:       {stamp}",
        # PER ARM, THE PAGES ACTUALLY WRITTEN -- never the pages asked for: an arm that renders fewer pages
        # writes fewer, and a note naming a page that is not there sends the reader after nothing (review
        # fix, 2026-09-30).
        "pages written: " + "  ".join(f"{arm} {sorted(pages) or 'NONE'}" for arm, pages in written.items()),
        f"pages changed: {sorted(changed) or 'NONE'}  (old against new)",
        "",
        "One PNG per page written, three arms:",
        "  p<NNN>-old.png     the deliverable with the pin's scripts",
        "  p<NNN>-new.png     the deliverable with the working tree's scripts",
        "  p<NNN>-source.png  the original document, for reference",
        "",
        "WHAT THE CHAIN IS NOT: only the steps named above ran"
        + ("" if post_process else " -- post_process and the definitions reorder did NOT")
        + ", and headers, footers, comments, footnotes and the glossary were not translated by this run:",
        "they are delivered as the original's, DECLARED KEPT beside the notes as a compliant keep-as-is run",
        "declares them (tools/keep_declarations.py). Do not read an effect of a step that did not run as a",
        "defect.",
        "",
        "These are renders of a real client document. They live here, outside the repository, and must",
        "never be committed or pasted anywhere.",
    ]) + "\n"


ap = argparse.ArgumentParser()
ap.add_argument("--doc", action="append", default=[], help="corpus doc-id (real, mechanical)")
ap.add_argument("--fixture", action="append", default=[],
                help="synthetic fixture stem (renders are kept and may be viewed)")
ap.add_argument("--expect-block", action="append", default=[],
                help="fixture stem whose NEW arm is EXPECTED to be refused by a gate. Its "
                     "old arm still renders, so the page shows what used to ship; a run "
                     "that produced output anyway is the FAILURE for such a fixture")
ap.add_argument("--expect-pages-move", action="append", default=[],
                help="SUB-STEP 10.4: fixture stem whose OLD arm is EXPECTED to have a "
                     "different page count from the new one, the defect BEING pages the "
                     "source never had. For such a fixture the old->new assertion inverts: "
                     "the counts must DIFFER, and source->new must still match")
ap.add_argument("--post-process", action="store_true",
                help="STEP 10: drive post_process.py over the fixture instead of apply + "
                     "repack. Step 10 changes post_process and nothing else, so without "
                     "this the fixture arms render the SAME apply code twice and an "
                     "all-quiet page is guaranteed — which is a limit of the instrument, "
                     "not evidence about the step. Section 5.2's gate needs this arm. "
                     "STEP 11's SUB-STEP 4a: with --doc, each arm runs apply, post_process, the "
                     "reorder and repack, where without it the --doc arm skips post_process")
ap.add_argument("--layout", action="store_true",
                help="STEP 18.2: with --doc, the classification run -- each layout device in the source placed by "
                     "page and position in the source's render and in the delivery's (apply, post_process, the "
                     "reorder with skill Step 7's flags, repack), read from bookmark destinations set on COPIES; "
                     "numbers by doc-id only, every PDF deleted. Every workdir of each named doc-id, repeats too")
ap.add_argument("--variant", default="uk", choices=("uk", "us"))
ap.add_argument("--pages", type=int, action="append", default=[],
                help="force these page numbers to be written even if they did not change "
                     "— the page a reviewer wants is often the one that stopped changing")
ap.add_argument("--keep-into-logs", action="store_true",
                help="write the real-corpus renders into the LOGS folder for a HUMAN to "
                     "open. They are still never displayed here. Needs --under-review")
ap.add_argument("--under-review", default="",
                help="with --keep-into-logs, REQUIRED: one line saying what change the kept pages "
                     "are for; it heads the generated note beside them (register I-33)")
args = ap.parse_args()
if args.keep_into_logs and not args.under_review.strip():
    print("REFUSED: --keep-into-logs needs --under-review \"<what change>\" -- the note beside the "
          "kept pages is generated from the run's own facts plus that line, and a page kept with no "
          "statement of what it is for is what register I-33 is about. Nothing rendered or written.")
    sys.exit(2)

SOFFICE = find_soffice()
print("=" * 98)
print("RENDERED PAGE COMPARISON — CLAUDE.md 5.2")
print("=" * 98)
if not SOFFICE:
    print("  VOID — LibreOffice not found. Set LT_SOFFICE. Nothing rendered, nothing proved.")
    sys.exit(1)
# NO PATH UNDER THE USER FOLDER IS PRINTED (2026-11-18): LibreOffice re-installed for the user lives there, so its
# path carries the machine's username - the leakage scan caught it in every report on the first run, and the
# publication check refuses the home-relative form too. Such a location is said in words.
_HOME = str(Path.home())
print(f"  soffice: {'found under the user folder (a per-user install)' if SOFFICE.lower().startswith(_HOME.lower()) else SOFFICE}")
print(f"  dpi: {DPI}")

FAIL, CHECKED = [], 0


def ok(label, cond, detail=""):
    global CHECKED
    CHECKED += 1
    print(("  OK   " if cond else "  XX   ") + label + (f"   {detail}" if detail and not cond
                                                        else ""))
    if not cond:
        FAIL.append(f"{label} {detail}".strip())


def run_apply(scripts_dir, src_docx, notes_json, out_xml):
    file_receipt(notes_json, ROOT / args.variant)
    env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1",
               PYTHONDONTWRITEBYTECODE="1")
    p = subprocess.run(
        ["uv", "run", "--with", "lxml", "python", str(scripts_dir / SCRIPT),
         str(src_docx), str(notes_json), str(out_xml)],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        cwd=str(ROOT), env=env, timeout=1800)
    return (out_xml if out_xml.is_file() else None), p


def run_post_process_arm(scripts_dir, adir):
    """Run post_process over the fixture's own document.xml, in a real workdir layout.

    Returns (document.xml path, completed process) or (None, process).

    THE LAYOUT MATTERS AND IS NOT DECORATION. `post_process` finds the notes by walking up
    from <workdir>/final/word/document.xml, and since step 10's sub-step 3a the italic pass READS them.
    Staged anywhere else the pass would find nothing, decline to decide, and render a page
    on which the condition was never evaluated -- an all-quiet render that looks exactly
    like a working fix.

    A fired drift gate is NOT a failure here. The fixture's notes declare the pre-pass
    English, so a pass that legitimately rewrites text makes the document disagree with
    them -- B6's situation, not this arm's. post_process writes the document before the
    gate raises, so the page is on disk either way. Compared by the gate's own words rather
    than by rc, because a toleration pinned to an exit code removes the one signal a
    regression would have used.
    """
    wd = adir / "wd"
    (wd / "final" / "word").mkdir(parents=True, exist_ok=True)
    dest = wd / "final" / "word" / "document.xml"
    with zipfile.ZipFile(adir / "source.docx") as z:
        dest.write_bytes(z.read("word/document.xml"))
    shutil.copyfile(adir / "paragraphs.json", wd / "paragraphs.json")
    proc = subprocess.run(
        [sys.executable, str(Path(scripts_dir) / "post_process.py"), str(dest),
         "--fix", "--variant", args.variant],
        capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=str(ROOT))
    blob = (proc.stdout or "") + (proc.stderr or "")
    if proc.returncode != 0 and "SKILL GATE FIRED" not in blob:
        return None, proc
    return (dest, proc) if dest.is_file() else (None, proc)


def _gate_line(proc):
    """The line a HUMAN needs from a refusal, not the first line of a traceback.

    `stderr[0]` is `Traceback (most recent call last):` on every gate this tree has, because
    the gates raise. Prefer the line that names the block; fall back to the LAST non-empty
    line, which is where a RuntimeError's message lands.
    """
    lines = [ln.strip() for ln in ((proc.stderr or "") + (proc.stdout or "")).splitlines()
             if ln.strip() and set(ln.strip()) - set("=-_ ")]   # a rule line is not a message
    for ln in lines:
        if "SKILL GATE FIRED" in ln or "BLOCK" in ln or "returned exit code" in ln:
            return ln[:160]
    return lines[-1][:160] if lines else "no output"


def _repack_bypass(src_docx, doc_xml, out_docx):
    """A .docx built by BYTE-SUBSTITUTING document.xml, used ONLY to render a blocked arm.

    WHY THIS EXISTS, AND WHY IT IS NOT A WAY ROUND A GATE. Sub-step 6.4 found that
    the PRE-FIX code cannot be repacked at all on the whitespace fixture: clearing a
    whitespace-only segment glues two words into one, `validate_apply --strict` compares token
    SETS, and a merged token is a token set that no longer matches -- so repack refuses. That
    is a real finding (the operator who follows skill Step 4 rule 9 is deadlocked, F41's family) and
    it is reported as one.

    But it also means the DEFECT has no page, and a fix nobody can see is a fix taken on
    trust. So the OLD arm -- and only the old arm, of a SYNTHETIC fixture -- is assembled here
    without the gates, purely to be looked at.

    NO XML IS PARSED OR REWRITTEN: `document.xml` is copied in as BYTES, so nothing here can
    rebind a namespace prefix (.claude/rules/ooxml.md's first rule). Every other part is
    copied verbatim from the source. It is not a deliverable and must never be used as one.
    """
    payload = Path(doc_xml).read_bytes()
    with zipfile.ZipFile(src_docx) as zin, \
            zipfile.ZipFile(out_docx, "w", zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            data = payload if item.filename == "word/document.xml" else zin.read(item.filename)
            zout.writestr(item, data)
    return out_docx if Path(out_docx).is_file() else None


_GLOSSARY_PART = "word/glossary/document.xml"
_GLOSSARY_TEXT_RE = re.compile(
    r"<w:(?:t|delText)(?:\s[^>]*)?>([^<]*)</w:(?:t|delText)>")


def _glossary_passthrough(src_docx, workdir):
    """['--glossary', <path>] when the source carries a text-bearing glossary part, else [].

    ADDED FOR SUB-STEP 7.2, and without it this tool simply FAILS on any document that
    has one: repack now REFUSES when the original carries a text-bearing
    word/glossary/document.xml and --glossary is absent (register C19). A renderer that dies
    on a new fixture is the shape "fix the class, not the caller" warns about — so the
    pass-through lives here, in the one place both arms go through, rather than being
    remembered at each call site.

    IT PASSES THE ORIGINAL PART, UNCHANGED, AND THAT IS DELIBERATE. That is repack's second
    compliant route — the operator who has read the part and judged it needs no translation
    records the decision by passing it. This tool renders; it does not translate, and
    inventing a translation here would put text on a page that no pipeline produced.

    THE CONSEQUENCE FOR WHAT THE RENDER SHOWS IS STATED IN THE READ-ME rather than left to be
    inferred: measured 2026-09-09 with a positive control firing
    (temp/probe_glossary_visible.py), LibreOffice renders NO glossary placeholder text at
    all — a translated and an untranslated glossary produce byte-identical page text. So this
    part of C19 has no page in this renderer, and a three-arm visual diff of it would be
    false coverage. Its proof is the byte comparison in tests/test_glossary_route.py.
    """
    try:
        with zipfile.ZipFile(src_docx) as z:
            if _GLOSSARY_PART not in z.namelist():
                return []
            raw = z.read(_GLOSSARY_PART)
    except Exception:                                   # noqa: BLE001
        return []
    text = raw.decode("utf-8", errors="ignore")
    if not any(t.strip() for t in _GLOSSARY_TEXT_RE.findall(text)):
        return []                                       # empty part: repack does not refuse
    out = Path(workdir) / "glossary-passthrough.xml"
    out.write_bytes(raw)
    return ["--glossary", str(out)]


# WHICH GATE REFUSED A REPACK, by the FIXED text of its own refusal, and for the delivered-document check its
# blocking findings by class -- the class lines it prints between its marker and its repairs. A COPY of
# tools/delivered_corpus_arm.py's REPACK_GATES, which runs its work at import and so cannot be imported --
# change one, change both; this one adds the rule 5b refusal and this tool's own keep-declaration failure,
# and leaves out --headers-footers-dir's misconfiguration, a flag this tool never passes.
_KEEP_FAILED = "KEEP DECLARATIONS COULD NOT BE WRITTEN"
_REPACK_GATES = (("keep declarations", _KEEP_FAILED),
                 ("lexicon", "lexicon_compliance.py --stage pre-repack returned exit code"),
                 ("validate_apply", "validate_apply.py --strict (post-modification check) returned exit code"),
                 ("glossary", "and --glossary was not supplied"),
                 ("integrity", "failed its own integrity checks"),
                 ("zwsp-survived", "U+200B SURVIVED THE SCRUB"),
                 ("remnant", "SOURCE-LANGUAGE REMNANT"),
                 ("delivered", "THE DELIVERED-DOCUMENT CHECK REFUSED THIS DELIVERY"),
                 ("rule 5b declaration", "THE RULE 5b DECLARATION WAS REFUSED"))
_CLASS_LINE = re.compile(r"^  ((?:side-[a-z]+|changed|missing|readings|edge-space|inner-space|collapsed|"
                         r"anchor-lost|anchor-gained|bracket|zwsp)(?:/[A-Za-z:-]+)?): (\d+)$")


def refusal(proc):
    """What a refused repack says, from its FIXED text alone: the gate, named by its own refusal marker, and
    the delivered check's blocking findings by class.

    REGISTER I-34. This tool printed the last 160 characters of repack's raw output -- stderr's, or stdout's
    where stderr was empty -- and repack's lexicon pass and remnant block quote the document in context
    snippets, so on a real document that tail could carry client text. It also hid what this tool most needs
    to say: WHICH check refused and on what. Both are answered here, and nothing else is printed."""
    blob = (proc.stdout or "") + (proc.stderr or "")
    gate = next((g for g, m in _REPACK_GATES if m in blob), None)
    classes = [m.groups() for m in map(_CLASS_LINE.match, blob.splitlines()) if m] if gate == "delivered" else []
    return (f"refused by the {gate} gate" if gate else f"exit {proc.returncode}, no gate marker recognised") + (
        " - " + ", ".join(f"{k} {n}" for k, n in classes) if classes else "")


def step_failure(proc):
    """A real document's post_process or reorder that failed, from its FIXED text alone: whether a skill gate
    fired, and the exit code -- never a line of its output, which can carry the document's text (review fix,
    2026-10-08: _gate_line's fallback, the LAST line of the output, was printed here for a real document)."""
    blob = (proc.stdout or "") + (proc.stderr or "")
    return f"exit {proc.returncode}" + (", a SKILL GATE fired" if "SKILL GATE FIRED" in blob else "")


def run_post_process_doc(scripts_dir, adir, xml):
    """--doc WITH --post-process (step 11's sub-step 4a): the applied XML through post_process and
    the definitions reorder before repack, as the pipeline runs them.

    Without it the --doc arm runs apply and repack ONLY, so a change inside post_process --
    strip_noop is one -- runs the same code on both arms and every page matches for that reason
    alone: a check passing for the wrong reason. Staged in a real workdir layout for
    run_post_process_arm's reason: post_process finds the notes by walking up from
    <workdir>/final/word/document.xml. A fired drift gate is tolerated and the arm goes on, as the
    corpus chain does; any other non-zero exit stops the arm.

    Returns (document.xml path, completed post_process) or (None, process).
    """
    env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1",
               PYTHONDONTWRITEBYTECODE="1")
    wd = adir / "wd"
    dest = wd / "final" / "word" / "document.xml"
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(xml, dest)
    for n in ("paragraphs.json", ".validate-state.json", "comments_translations.json",
              "headers_footers.json", "_boldmap.json"):
        if (adir / n).is_file():
            shutil.copyfile(adir / n, wd / n)
    py = ["uv", "run", "--with", "lxml", "python"]
    proc = subprocess.run(py + [str(scripts_dir / "post_process.py"), str(dest), "--fix",
                                "--variant", args.variant],
                          capture_output=True, text=True, encoding="utf-8", errors="replace",
                          cwd=str(ROOT), env=env, timeout=900)
    if proc.returncode != 0 and "SKILL GATE FIRED" not in (proc.stdout or "") + (proc.stderr or ""):
        return None, proc
    # SKILL STEP 7's OWN FLAGS (18.2): since 16.6 and 17.2 the step passes --notes and --styles, so a reorder run
    # without them sorts by the detector's guess and sees only direct bold -- not the step a delivery goes through
    # (17.5). Passed where the arm's reorder accepts them; a pinned tree older than both runs without, as it shipped.
    ro_cmd = py + [str(scripts_dir / "reorder_definitions.py"), "--doc", str(dest)]
    ro_src = (scripts_dir / "reorder_definitions.py").read_text(encoding="utf-8", errors="replace")
    if "'--notes'" in ro_src and "'--styles'" in ro_src:
        ro_cmd += ["--notes", str(wd / "paragraphs.json"), "--styles", str(adir / "source.docx")]
    ro = subprocess.run(ro_cmd,
                        capture_output=True, text=True, encoding="utf-8", errors="replace",
                        cwd=str(ROOT), env=env, timeout=900)
    if ro.returncode != 0:
        return None, ro
    return (dest if dest.is_file() else None), proc


def repack(scripts_dir, src_docx, doc_xml, out_docx, notes_json):
    """repack, with every side part the ORIGINAL carries DECLARED KEPT beside the notes first.

    REGISTER I-34. Since skill Step 10's wiring (step 11, 2026-09-30) repack runs the delivered-document check,
    which reads each text-bearing header, footer, comment, footnote, endnote and glossary part of the original
    against a declaration beside the notes. This tool renders the BODY: every side part is delivered as the
    original's. With no declaration the check rightly refused the NEW arm -- measured 2026-10-08 on 5 of 12 real
    documents, uk and us alike, while the OLD arm, whose repack predates the check, delivered: a render with
    no new arm. So the side parts are declared KEPT, as a compliant keep-as-is run declares them under skill Step 8,
    by tools/keep_declarations.py -- the one helper every harness uses -- here, in the one place both arms and
    both paths go through, as _glossary_passthrough is. From the WORKING TREE's variant scripts on both arms,
    so the two arms get the same input and the code stays the one variable; the old arm's repack never reads
    them.

    A FAILURE TO DECLARE IS THIS ARM'S FAILURE, NEVER A CRASH: it is returned as a refusal carrying a fixed
    marker and the exception's TYPE only, so the run reports it and goes on to the next document."""
    try:
        write_keep_declarations(src_docx, Path(notes_json).parent, ROOT / args.variant / "scripts")
    except Exception as exc:                            # noqa: BLE001 -- reported, by type, as a refusal
        return None, subprocess.CompletedProcess([], 1, "", f"{_KEEP_FAILED} ({type(exc).__name__})")
    env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1",
               PYTHONDONTWRITEBYTECODE="1")
    p = subprocess.run(
        ["uv", "run", "--with", "lxml", "python", str(scripts_dir / "repack_docx.py"),
         str(src_docx), str(doc_xml), str(out_docx), "--paragraphs", str(notes_json)]
        + _glossary_passthrough(src_docx, out_docx.parent),
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        cwd=str(ROOT), env=env, timeout=900)
    return (out_docx if out_docx.is_file() else None), p


# =========================================================================================
# SYNTHETIC FIXTURES — renders KEPT, because there is no client text in them.
# =========================================================================================
# A PINNED-BASELINE ARM FOR FIXTURES, BUILT ONCE. Added for sub-step 6.4.
#
# WITHOUT IT A FIXTURE RENDER SHOWS `source` VERSUS `applied-with-whatever-is-in-the-tree`, so
# the DEFECT is not on any page and the reviewer is asked to take the improvement on trust.
# Sub-step 6.3 hit exactly this and worked around it by hand -- "rendering a third arm from the
# pre-widening script" -- which is a step nobody can repeat and nothing records. The real
# corpus path has had this arm since it was written; the fixture path did not, and the
# asymmetry was invisible because only the corpus path was ever red.
FX_OLDTREE = None
if args.fixture:
    # WHICH SCRIPT THE BASELINE ARM SWAPS IS DECIDED BY WHICH SCRIPT THE RUN DRIVES.
    # It was hardwired to apply, which was right while the fixture path only ever ran
    # apply + repack. In --post-process mode that hardwiring is the defect: the arm would
    # swap a script the run never executes, report the two arms as the same code, and
    # render an all-quiet page — indistinguishable from a fix that worked.
    #
    # AND THE LIST WAS THE DEFECT, NOT ITS CONTENTS (branch 11 slice 2b, 2026-09-25). The fixture
    # path runs apply AND repack, and repack runs lexicon_compliance, validate_apply and the
    # marker module; a hand-kept list of "the scripts the run drives" named apply alone, so when
    # repack changed, both arms ran the NEW repack and the render compared it with itself -- an
    # all-quiet page, caught only because the old arm's .docx held no U+200B either. So the arm
    # is now REF's WHOLE scripts tree: every script a run can execute is the baseline's, and no
    # list has to be kept in step with what a run happens to call.
    _names = subprocess.run(["git", "ls-tree", "--name-only", REF, f"{args.variant}/scripts/"],
                            capture_output=True, text=True, cwd=ROOT).stdout.split()
    FX_SCRIPTS = sorted(n.rsplit("/", 1)[-1] for n in _names if n.endswith(".py"))
    if not FX_SCRIPTS:
        print(f"\n  VOID — no scripts at {REF}; no baseline arm for the fixtures.")
        sys.exit(1)
    _fxtmp = Path(tempfile.mkdtemp(prefix="fx-oldtree-"))
    FX_OLDTREE = _fxtmp / "old_scripts"
    shutil.copytree(ROOT / args.variant / "scripts", FX_OLDTREE)
    lexicons_beside(FX_OLDTREE, ROOT / args.variant)
    _any_diff = False
    _differ = []
    for _name in FX_SCRIPTS:
        _blob = subprocess.run(["git", "show", f"{REF}:{args.variant}/scripts/{_name}"],
                               capture_output=True, cwd=ROOT)
        if _blob.returncode != 0:
            print(f"\n  VOID — cannot read {_name} at {REF}; no baseline arm for the "
                  f"fixtures.")
            sys.exit(1)
        (FX_OLDTREE / _name).write_bytes(_blob.stdout)
        # The sentinel is a plain string at the file's end, so a copied script still passes
        # its own integrity check -- proved rather than assumed, because failing it would
        # exit 3 and the arm would silently not exist.
        if b"\n# === SKILL FILE COMPLETE ===" not in (FX_OLDTREE / _name).read_bytes():
            print(f"  VOID — the baseline copy of {_name} has no integrity sentinel; it "
                  f"would exit 3.")
            sys.exit(1)
        _here = ROOT / args.variant / "scripts" / _name
        if not _here.is_file() or _blob.stdout != _here.read_bytes():
            _any_diff = True
            _differ.append(_name)
    print(f"  fixture baseline arm: {REF}'s whole scripts tree ({len(FX_SCRIPTS)} scripts; "
          f"differing from the working tree: {', '.join(_differ) or 'none'})"
          + ("" if _any_diff else
             "   NOTE: BYTE-IDENTICAL to the working tree, so old and new are the same code "
             "and an all-quiet render proves nothing"))

for stem in args.fixture:
    fx = ROOT / "tests" / "fixtures" / f"{stem}.docx"
    print(f"\n{stem}.docx  — SYNTHETIC, renders kept for inspection")
    print("-" * 98)
    if not fx.is_file():
        ok(f"{stem}: fixture exists", False, "not found")
        continue
    outdir = ROOT / "temp" / "render" / stem
    if outdir.exists():
        shutil.rmtree(outdir, ignore_errors=True)
    outdir.mkdir(parents=True)
    with zipfile.ZipFile(fx) as z:
        src_xml = z.read("word/document.xml")
    # A FIXTURE MAY SHIP ITS OWN NOTES, AND WHERE IT DOES THEY WIN.
    #
    # The synthesised notes below are `en = text + " EN"` with NO `runs` array, which is fine
    # for a fixture testing whether a structure SURVIVES and useless for one testing where a
    # structure is PLACED: any rule keyed on `runs`, or on the English keeping the source's
    # trailing digits, cannot fire on them at all. Measured 2026-09-02 on toc.docx, where
    # `en` ended in " EN" rather than a page number, so the placement rule declined every
    # entry and the render showed a flat page that looked like the unfixed defect.
    #
    # A fixture's notes are its INPUT. Shipping them beside it means the suite and this tool
    # drive the fixture with the SAME input -- so what is asserted mechanically is what gets
    # looked at, rather than two different documents wearing one name.
    side = fx.with_suffix(".notes.json")
    if side.is_file():
        notes = json.loads(side.read_text(encoding="utf-8"))
        print(f"       notes: {side.name} (shipped with the fixture, {len(notes)} entries)")
    else:
        notes = [{"idx": i, "text": t, "en": (t + " EN") if t else t, "style": "Normal"}
                 for i, t in enumerate(para_texts(src_xml))]
        print(f"       notes: SYNTHESISED, {len(notes)} entries — en = text + \" EN\", no "
              f"`runs`. A placement rule cannot be tested on these.")
    nj = outdir / "paragraphs.json"
    nj.write_text(json.dumps(notes, ensure_ascii=False), encoding="utf-8")
    shutil.copyfile(fx, outdir / "source.docx")

    # THREE ARMS: the source, the deliverable at the PINNED BASELINE, and the deliverable with
    # the working tree. `old` is what the defect looks like on a page; without it a reviewer is
    # asked to believe the improvement rather than see it.
    #
    # ONE INPUT COPY PER ARM. Apply invokes validate_translations as its final pre-apply pass
    # and that writes `.validate-state.json` beside the NOTES file, so two arms sharing a
    # directory would have each arm reading the other's batch state.
    expect_block = stem in args.expect_block
    built = {}
    for arm, scripts_dir in (("old", FX_OLDTREE),
                             ("new", ROOT / args.variant / "scripts")):
        adir = outdir / arm
        adir.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(fx, adir / "source.docx")
        shutil.copyfile(nj, adir / "paragraphs.json")
        if args.post_process:
            # STEP 10's SUB-STEP 3a — THE ARM THAT CLOSES SECTION 5.2's GATE FOR THIS STEP.
            #
            # Sub-steps 10.1 and 10.2 left the rendered diff undischarged and said why in terms: this
            # tool's fixture path drives apply and repack and NEVER post_process, so no
            # sub-step of step 10 could reach a page. That was a limit of the instrument and
            # was recorded as a gap rather than waved through as an N/A. This is the arm the
            # previous READ-ME named as what would close it.
            #
            # It runs post_process over the fixture's OWN document.xml -- the fixture is
            # already the English here, which is what makes B1's condition testable -- with
            # the notes beside it, because the pass is now conditional on them and an arm
            # that withheld them would render a document the condition never touched.
            xml, p_ = run_post_process_arm(scripts_dir, adir)
        else:
            xml, p_ = run_apply(scripts_dir, adir / "source.docx",
                                adir / "paragraphs.json", adir / "document.xml")
        if xml is None:
            # A REFUSAL IS A RESULT FOR A FIXTURE THAT DECLARES ONE, AND A FAILURE OTHERWISE.
            # en-runs-offsets.docx exists so a gate REFUSES it; reporting that as a broken
            # fixture would train a reader to ignore the one arm that is working.
            if expect_block and arm == "new":
                ok(f"{stem}: the NEW arm is REFUSED by a gate, as this fixture declares",
                   True)
                print(f"       rc={p_.returncode}, and the refusal is the point: there is no "
                      f"page to render because the run correctly did not produce one.")
                print(f"       gate said: {_gate_line(p_)}")
                continue
            ok(f"{stem}: apply produced document.xml ({arm} arm)", False,
               (p_.stderr or p_.stdout or "")[-200:])
            continue
        deliv, rp = repack(scripts_dir, adir / "source.docx", xml,
                           adir / "applied.docx", adir / "paragraphs.json")
        if deliv is None and args.post_process:
            # IN post_process MODE A REFUSED REPACK IS EXPECTED ON EITHER ARM, AND IT IS
            # SYMMETRIC. The notes declare the pre-pass English, so any pass that rewrites
            # text makes the repack-time validator disagree with them — the same B6
            # situation the stage's own gate reports. The pages are assembled by byte
            # substitution purely to be LOOKED AT, on BOTH arms or neither: assembling one
            # arm differently from the other is how a rendering difference stops being
            # about the code under test.
            print(f"       the {arm.upper()} arm's repack was refused; the page is "
                  f"assembled by byte substitution, symmetrically with the other arm. "
                  f"It is not a deliverable.")
            print(f"         {_gate_line(rp)}")
            deliv = _repack_bypass(adir / "source.docx", xml, adir / "bypassed.docx")
            if deliv is None:
                ok(f"{stem}: {arm} arm assembled for rendering", False)
                continue
            built[arm] = deliv
            continue
        if deliv is None and arm == "old":
            # THE PRE-FIX CODE FAILING ITS OWN REPACK GATE IS A RESULT, NOT A BROKEN FIXTURE.
            # Reported as the finding it is, and then the arm is assembled without the gates
            # so the defect still has a page. Synthetic fixture, old arm, render only.
            print(f"       the OLD arm's repack was REFUSED by a gate — which is a FINDING, "
                  f"not a fixture defect:")
            print(f"         {_gate_line(rp)}")
            print(f"       so the old arm is assembled by byte-substituting document.xml, "
                  f"purely to be LOOKED AT. It is not a deliverable.")
            deliv = _repack_bypass(adir / "source.docx", xml, adir / "bypassed.docx")
            if deliv is None:
                ok(f"{stem}: old arm assembled for rendering", False)
                continue
        elif deliv is None:
            # A SYNTHETIC fixture holds no client text, so its refusal also shows the line that names it --
            # for a crash rather than a gate, the only diagnostic there is. Never on the --doc path.
            ok(f"{stem}: repack produced a .docx ({arm} arm)", False, f"{refusal(rp)} | {_gate_line(rp)}")
            continue
        built[arm] = deliv
    if expect_block and "new" in built:
        ok(f"{stem}: declared --expect-block, yet the NEW arm produced a deliverable",
           False, "the gate did not fire — that is the failure for this fixture")

    pdfs = {}
    for name, docx_path in (("source", outdir / "source.docx"),
                            ("old", built.get("old")), ("new", built.get("new"))):
        if docx_path is None:
            continue
        pdf, r = to_pdf(SOFFICE, docx_path, outdir / name if name != "source" else outdir)
        if pdf is None:
            ok(f"{stem}: {name} converted to PDF", False, (r.stderr or r.stdout or "")[-200:])
            continue
        pdfs[name] = pdf
    import pymupdf
    for name, pdf in pdfs.items():
        with pymupdf.open(pdf) as doc:
            for i, page in enumerate(doc):
                page.get_pixmap(dpi=DPI).save(str(outdir / f"{name}-p{i + 1}.png"))
        print(f"       {name}: {len(page_hashes(pdf))} page(s) -> temp/render/{stem}/"
              f"{name}-p1.png ...")
    if "old" in pdfs and "new" in pdfs:
        po, pn = page_hashes(pdfs["old"]), page_hashes(pdfs["new"])
        if stem in args.expect_pages_move:
            # INVERTED FOR A FIXTURE THAT DECLARES IT, AND ONLY FOR ONE. B7's defect IS a
            # page the source never had, so an unchanged count old -> new would mean the
            # fix did nothing -- the assertion every other fixture needs is exactly wrong
            # here. The source -> new check below still has to hold.
            ok(f"{stem}: the OLD arm's page count DIFFERS from the new one, as this fixture "
               f"declares  {len(po)} -> {len(pn)}", len(po) != len(pn))
        else:
            ok(f"{stem}: page count unchanged old -> new  {len(po)} -> {len(pn)}",
               len(po) == len(pn))
        moved = [i + 1 for i, (a, b) in enumerate(zip(po, pn)) if a != b]
        # NOT AN ASSERTION EITHER WAY. Some fixtures must change on the page and some must
        # not; the manifest says which pages moved and the suite owns the expectation.
        print(f"       pages whose RENDERING changed old -> new: {moved or 'NONE'}")
    if "source" in pdfs and "new" in pdfs:
        ok(f"{stem}: page count unchanged source -> new  "
           f"{len(page_hashes(pdfs['source']))} -> {len(page_hashes(pdfs['new']))}",
           len(page_hashes(pdfs["source"])) == len(page_hashes(pdfs["new"])))

    # A READ-ME PER FIXTURE, and it is written as BYTES with explicit \n. `write_text` opens
    # in text mode, so on Windows every \n becomes \r\n -- harmless in a scratch directory,
    # but the habit is what matters and the real-corpus block below has the same defect.
    (outdir / "READ-ME.txt").write_bytes(("\n".join([
        f"SYNTHETIC FIXTURE RENDER — {stem}.docx",
        "",
        "Every string in this document is invented. It is NOT a client document, so these",
        "pages may be looked at, kept and pasted anywhere.",
        "",
        "THREE ARMS:",
        f"  source-pN.png   the fixture itself, untranslated",
        f"  old-pN.png      the deliverable as the code stood at {REF} — THE DEFECT",
        "  new-pN.png       the deliverable with the working tree's code — THE FIX",
        "",
        "The `old` arm is the point. Without it you would be asked to believe the",
        "improvement rather than see it, which is what happened on the previous sub-step.",
        "",
        # THIS BLOCK IS REWRITTEN ON EVERY BRANCH, NEVER APPENDED TO, AND IT STATES NO COUNT OF
        # HOW OFTEN: it said "each of the last eight" and went stale the sub-step after, which is
        # every count's fate here. Nothing checks it. Left describing the previous change it
        # sends a reviewer hunting for something that is already in the `old` arm, and a
        # reviewer who cannot find what the text promises reads a correct page as a defect --
        # which happened on the table-of-contents sub-step, where two deliberate refusals were read
        # as damage because nothing on the page said they were deliberate.
        #
        # THE REWRITES ARE NO LONGER A CADENCE, THEY ARE A DESIGN FACT: this text is a
        # per-step artefact living in a permanent file, and the only thing keeping it true is
        # that somebody remembers. Every other per-step claim in this repository that nothing
        # checks has gone stale at least once.
        "WHAT THIS STEP CHANGED — SUB-STEP 10.4, THE PAGE-BREAK PASS INSERTS NOTHING (B7).",
        "Render schedule-breaks.docx with --post-process --expect-pages-move schedule-breaks",
        "AND LT_BASELINE_REF=6d8bbab, the last merge before this sub-step -- at the default pin",
        "both arms carry the fix and that flag fails by design -- then compare old-pN.png",
        "against new-pN.png, and new-pN.png against source-pN.png.",
        "",
        "WHAT IS ON THE PAGES. EVERY HEADING LABELS WHAT ITS SOURCE DOES:",
        "  SCHEDULE 1   the source runs it on under the body text.  OLD: forced onto a page",
        "               of its own the source never gave it.  NEW: where the source put it.",
        "               B7's own case -- on real documents, a blank page, or a listing split",
        "               from its heading.",
        "  SCHEDULE 2   the source starts this page with a break at the head of the heading.",
        "               OLD: the pass adds a SECOND break.  NEW: one break, the source's.",
        "               THIS ROW LOOKS THE SAME ON BOTH ARMS HERE, AND THE PAGES ARE NOT",
        "               TELLING THE WHOLE TRUTH: LibreOffice, which renders them, lays the two",
        "               breaks out as one. WORD DOES NOT -- counted in Word, a copy carrying",
        "               only this doubled break is 4 pages against a control's 3, and the old",
        "               arm is 5 where LibreOffice says 4. It is a blank page in the program a",
        "               reviewer opens, and this tool cannot see it: register row I-26.",
        "  ANNEX A      CONTROL -- the source gives it its own page break. The same on both",
        "               arms: the old pass skipped a heading that already had one, and the",
        "               new one removes nothing.",
        "",
        "THE NEW ARM MUST HAVE THE SOURCE'S PAGE COUNT AND THE OLD ONE MUST NOT, and this tool",
        "asserts both for this fixture. The corpus's third shape -- a break the heading's STYLE",
        "already carries, where the old pass's break was redundant and moved no page -- is not",
        "on these pages: every fixture shares one styles part, so it is proved in bytes by",
        "tests/test_pass_conditions.py instead.",
        "",
        "  WHERE THE REST OF THIS SUB-STEP'S PROOF IS:",
        "    tests/test_pass_conditions.py   71 checks on each variant, 0 failures, 0 void, and",
        "      PROVED RED against 6d8bbab on both. It also enforces the PRINCIPLE: a pass",
        "      post_process runs without a PASS_CONDITIONS row turns it red, and its planted",
        "      controls prove it can.",
        "    tools/postprocess_corpus_arm.py --from-apply   13 of 13 real inputs, rebuilt",
        "      through apply where no snapshot was kept. The bytes MOVED on exactly 6, the page-",
        "      break pass's count going N -> 0 on each, 11 breaks in all, both variants, and",
        "      0 unexplained.",
        "",
        "PREVIOUS SUB-STEPS, FOR ORIENTATION ONLY — 3b, a mandatory rewrite no longer overrules the",
        "lexicon (B5, B6(a), F29, B9, F45); and 3a, the italic strip made conditional on what",
        "the operator declared (B1). Both are in the pinned baseline, so neither is a difference",
        "here. Render lexicon-choice.docx or italic-declared.docx to see their pages.",
        "",
        "PREVIOUS STEP, FOR ORIENTATION ONLY — STEP 8, extraction completeness (C28,",
        "C12, M1): the one check that reads the ORIGINAL document. That is now in the pinned",
        "baseline, so it is no longer visible as a difference here. It had no page either —",
        "what it reports is an ABSENCE from a JSON file, not a mark on a document.",
        "",
        "THE SUB-STEP BEFORE THAT, FOR ORIENTATION ONLY — A19, translatable text held in GRAPHIC",
        "METADATA. That is now in the pinned baseline, so it is no longer visible as a",
        "difference here. Neither of its surfaces ever had a page in any renderer: alt text",
        "is an XML attribute a SCREEN READER SPEAKS, never painted in any viewer, and a",
        "chart title lives in its own part — which is most of why the defect survived, a",
        "surface no page shows being invisible to every instrument a reviewer reaches for.",
        "Its proof is tests/test_graphic_metadata.py, 95 checks per variant, and",
        "graphic-metadata.docx is deliberately NOT rendered by this tool.",
        "",
        "THE SUB-STEP BEFORE THAT, FOR ORIENTATION ONLY — C19, the glossary part's route in and out.",
        "That is now in the pinned baseline, so it is no longer visible as a difference",
        "here. glossary.docx labels its own three rows; its proof was never visual either.",
        "",
        "AND THE ONE BEFORE THAT, FOR ORIENTATION ONLY — A16 and N1, the container inventory: a",
        "container's text stayed in the SOURCE LANGUAGE on the delivered page while every",
        "gate reported the document clean. That is now in the pinned baseline, so it is no",
        "longer visible as a difference here. Render containers.docx to see it.",
        "",
        "  containers.docx — the document LABELS ITS OWN ROWS, so nothing here has to be",
        "  taken on trust. Read each label, then the line under it. Twenty rows:",
        "    the CONTROL rows      must look IDENTICAL in `old` and `new`. Two of them are a",
        "                          BLOCK content control, which was always correct, and they",
        "                          are the real corpus's own positive control — 5 of the sdt",
        "                          document's 10 take exactly that shape.",
        "    the sdt and smartTag  in `old` the source-language fragment stands beside the",
        "    rows                  English, often BEFORE it. In `new` there is one English",
        "                          sentence and the fragment is gone.",
        "    smarttag-trailing     in `new` the annotation wrapper is GONE. That is the",
        "                          decided outcome, not damage: a smart tag over text that no",
        "                          longer exists is provably redundant. A content control is",
        "                          KEPT even when empty, because it renders.",
        "    ruby-in-run           looks the SAME in both arms and is still wrong in both.",
        "                          apply destroys the ruby annotation, and putting it back",
        "                          needs the per-run English step 15 emits. Pinned, not",
        "                          fixed — see tests/test_container_inventory.py.",
        "    fldsimple-ref         the clause number appears TWICE in both arms. A9's",
        "                          duplication in the one field form clause 3 cannot see.",
        "                          Also pinned.",
        "",
        "  THE ALT TEXT AND THE CHART TITLE DO NOT SHOW ON ANY PAGE, and that is A19 rather",
        "  than a rendering problem: alt text is an attribute a screen reader speaks, and the",
        "  chart title lives in its own part. SUB-STEP 7.3 HAS NOW CLOSED A19, and apply must",
        "  still leave both alone — the translation route is skill Step 8b's, which writes header",
        "  and footer parts only, so this fixture's BODY alt text is reported and NOT",
        "  translated. test_container_inventory.py asserts apply's hands-off in both",
        "  directions; test_graphic_metadata.py owns the fix.",
        "",
    ] + ([
        # THIS PARAGRAPH SAID "NO post_process" ON EVERY RENDER, INCLUDING THE --post-process
        # RENDERS THAT ARE NOTHING BUT post_process, for the whole of sub-step 3a. A sentence
        # true of one mode and printed in both is a claim nothing checks, so it follows the
        # mode now rather than being rewritten for whichever one ran last.
        "WHAT THESE PAGES ARE NOT. They come from post_process ALONE, run over the fixture's",
        "own document.xml in a real workdir with its notes beside it: no apply, no",
        "definitions reorder, and repack's gates bypassed by byte substitution on BOTH arms",
        "when they refuse. Anything apply does to a real document is not on these pages.",
        "",
    ] if args.post_process else [
        "WHAT THESE PAGES ARE NOT. They come from apply + repack only, never the",
        "eleven-step pipeline: no definitions reorder, no tidy-up pass, no post_process. So",
        "post_process's seam repair has NOT run — which is deliberate, because it would",
        "have masked one of the two ARM 1 lines and hidden what apply actually delivered.",
        "",
    ]) + [
        "AND NO SIDE PART IS TRANSLATED: headers, footers, comments, footnotes and the glossary are",
        "the fixture's own, DECLARED KEPT beside the notes as a compliant keep-as-is run declares them",
        "(tools/keep_declarations.py), so the delivered check inside repack reads them as kept.",
        "",
    ]) + "\n").encode("utf-8"))

# =========================================================================================
# STEP 18.2 — THE LAYOUT MODE over the real corpus. MECHANICAL ONLY: numbers by doc-id, no page shown or kept.
# =========================================================================================
if args.layout:
    if not args.doc:
        print("  REFUSED: --layout needs --doc (the synthetic proof is tests/test_layout_mode.py). Nothing rendered.")
        sys.exit(2)
    if not LOGS.exists():
        print("\n  logs folder not reachable. VOID, not a pass.")
        sys.exit(1)
    TMP = Path(tempfile.mkdtemp(prefix="l18-render-"))
    atexit.register(shutil.rmtree, TMP, ignore_errors=True)
    SCRIPTS = ROOT / args.variant / "scripts"
    CORPUS = corpus_dirs()
    print(f"\n  LAYOUT MODE, variant {args.variant}: each arm runs apply -> post_process -> reorder "
          "(--notes, --styles) -> repack; bookmarks on copies; destinations read with re and zlib alone")
    print(f"  corpus folder(s) reachable: {len(CORPUS)}")
    wds = [w for w in (sorted(LOGS.rglob("wd")) + sorted(LOGS.rglob("wd-*"))) if w.is_dir()]
    seen, table, docs_done, considered, bodies = {}, [], 0, [], []
    for wd in wds:
        doc = wd.name[3:] if wd.name.startswith("wd-") else wd.parent.name
        seen[doc] = seen.get(doc, 0) + 1
        label = doc if seen[doc] == 1 else f"{doc}#{seen[doc]}"
        if doc not in args.doc or not (wd / "paragraphs.json").is_file():
            continue
        considered.append(doc)
        notes = json.loads((wd / "paragraphs.json").read_text(encoding="utf-8"))
        src, frac = pick_source_docx(wd, notes, CORPUS)
        if src is None or frac < 0.5:
            ok(f"{label}: source matched", False, f"best {frac:.0%}")
            continue
        adir = TMP / label.replace("#", "n")
        adir.mkdir(parents=True)
        shutil.copyfile(src, adir / "source.docx")
        for n in ("paragraphs.json", ".validate-state.json", "_boldmap.json"):
            if (wd / n).is_file():
                shutil.copyfile(wd / n, adir / n)
        xml, _ = run_apply(SCRIPTS, adir / "source.docx", adir / "paragraphs.json", adir / "document.xml")
        if xml is None:
            ok(f"{label}: apply produced document.xml", False)
            continue
        xml, pp = run_post_process_doc(SCRIPTS, adir, xml)
        if xml is None:
            ok(f"{label}: post_process and the reorder ran", False, step_failure(pp))
            continue
        deliv, rp = repack(SCRIPTS, adir / "source.docx", xml, adir / "delivery.docx", adir / "paragraphs.json")
        if deliv is None:
            # A REFUSED REPACK IS THE FROZEN NOTES MEETING TODAY'S GATES, NOT THIS INSTRUMENT'S FAILURE (18.2): July's
            # notes predate checks steps 4 to 17 added. The layout question is about the BODY as applied, post-processed
            # and reordered, so it is classified on that body, byte-substituted into a copy of the source as the fixture
            # path does for a blocked arm -- never a deliverable, deleted with the rest -- and the gate is named.
            why = refusal(rp)
            deliv = _repack_bypass(adir / "source.docx", xml, adir / "delivery-body.docx")
            if deliv is None:
                ok(f"{label}: repack refused and the body could not be built", False, why)
                continue
            bodies.append(label)
            print(f"  {label}: repack {why}; classified on the body as applied")
        with zipfile.ZipFile(adir / "source.docx") as z:
            sroot = etree.fromstring(z.read("word/document.xml"))
            sty = lay_styles(z.read("word/styles.xml") if "word/styles.xml" in z.namelist() else None)
        with zipfile.ZipFile(deliv) as z:
            droot = etree.fromstring(z.read("word/document.xml"))
        devs = lay_devices(sroot, sty)
        npar_s, npar_d = len(list(sroot.iter(lay_q("p")))), len(list(droot.iter(lay_q("p"))))
        # THE REORDER PERMUTES PARAGRAPHS AND KEEPS THEIR COUNT (review fix): apply keeps every paragraph in place,
        # so apply's output against the delivery names the positions the reorder moved.
        moved_by_reorder = lay_reordered(para_texts((adir / "document.xml").read_bytes()), para_texts(
            etree.tostring(droot)))
        grown = lay_d6_grown(sroot, droot, sty, moved_by_reorder or frozenset())
        print(f"\n  {label}: {len(devs)} device(s) in the source; paragraphs {npar_s} -> {npar_d}; "
              f"D6 exact-height paragraphs whose run grew: {grown if grown is not None else 'unpaired'}")
        if grown:
            table.append((label, "D6", 3, grown, (None, None), "n/a", ""))
        if not devs:
            docs_done += 1
            continue
        if npar_s != npar_d:
            ok(f"{label}: source and delivery pair paragraph for paragraph", False, f"{npar_s} -> {npar_d}")
            for d in devs:
                table.append((label, d["mech"], d["bucket"], d["n"], (None, None), "unpaired", ""))
            continue
        if moved_by_reorder:
            print(f"       the reorder moved {len(moved_by_reorder)} paragraph(s): a device on one is 'unpaired'")
            keep = []
            for d in devs:
                if any(v in moved_by_reorder for v in d["marks"].values() if v is not None):
                    table.append((label, d["mech"], d["bucket"], d["n"], (None, None), "unpaired", ""))
                else:
                    keep.append(d)
            devs = keep
        wanted = lay_wanted(devs)
        dests = {}
        for side, docx_in in (("source", adir / "source.docx"), ("delivery", deliv)):
            mdir = adir / f"marked-{side}"
            mdir.mkdir()
            mk = mdir / f"{side}.docx"
            set_n = lay_marked_copy(docx_in, mk, wanted)
            pdf, r = to_pdf(SOFFICE, mk, mdir, LAY_PDF_FILTER)
            if pdf is None:
                ok(f"{label} {side}: rendered to PDF", False, f"exit {r.returncode}")
                break
            got, pages = lay_destinations(pdf)
            got = {k: v for k, v in got.items() if k.startswith(LAY_PREFIX)}
            print(f"       {side}: {pages} page(s); {set_n} of {len(wanted)} bookmarks set, {len(got)} came back")
            dests[side] = got
            pdf.unlink()
        if len(dests) != 2:
            continue
        docs_done += 1
        sps, dps = list(sroot.iter(lay_q("p"))), list(droot.iter(lay_q("p")))
        for k, (d, (pages, moved)) in enumerate(zip(devs, lay_judge(devs, dests["source"], dests["delivery"]))):
            detail = ""
            if d["mech"] in ("D1", "D1-control"):
                i, sx, dx = d["marks"]["dev"], dests["source"].get(f"{LAY_PREFIX}{k}rdev"),                     dests["delivery"].get(f"{LAY_PREFIX}{k}rdev")
                detail = (f"x {sx[1]:.1f} -> {dx[1]:.1f}, " if sx and dx else "") +                     f"leading tabs {lay_lead_tabs(sps[i])} -> {lay_lead_tabs(dps[i])}, " +                     f"blanks {lay_lead_blanks(sps[i])} -> {lay_lead_blanks(dps[i])}"
            table.append((label, d["mech"], d["bucket"], d["n"], pages, moved, detail))
    shutil.rmtree(TMP, ignore_errors=True)
    print("\n  THE CLASSIFICATION — one line per flagged instance group: doc-id, mechanism, bucket, instances, "
          "page source -> delivery, moved")
    for label, mech, bucket, n, pages, moved, detail in table:
        mv = "MOVED" if moved is True else "same" if moved is False else moved
        print(f"    {label:<7} {mech:<11} bucket {str(bucket):<8} n {n:<3} p {pages[0]} -> {pages[1]}   {mv}" + (f"   {detail}" if detail else ""))
    flagged = [t for t in table if t[1] != "D1-control"]
    inst = sum(t[3] for t in flagged)
    b12 = sum(t[3] for t in flagged if t[2] in (1, 2))
    by = {}
    for t in table:
        k = (t[1], t[2])
        c = by.setdefault(k, [0, 0, 0, 0, set()])
        c[0] += t[3]
        c[1] += t[3] if t[5] is True else 0
        c[2] += t[3] if t[5] is False else 0
        c[3] += t[3] if t[5] in ("unread", "unpaired") else 0
        c[4].add(t[0].split("#")[0])
    print("\n  BY MECHANISM — instances, moved, same, unread or unpaired, doc-ids")
    for (mech, bucket), (n, mv, same, unread, ids) in sorted(by.items(), key=lambda kv: str(kv[0])):
        print(f"    {mech:<11} bucket {str(bucket):<8} {n:>4}  moved {mv:>3}  same {same:>3}  unread {unread:>3}  "
              f"{', '.join(sorted(ids))}")
    print(f"\n  FLAGGED INSTANCES (the control excluded): {inst}; in buckets 1 and 2: {b12}"
          + (f" ({b12 / inst:.0%})" if inst else ""))
    ctl_moved = sum(t[3] for t in table if t[1] == "D1-control" and t[5] is True)
    print(f"  THE POSITIVE CONTROL (D1 with a stop of its own): "
          f"{sum(t[3] for t in table if t[1] == 'D1-control')} instance(s), moved {ctl_moved}")
    # EVERY WORKDIR OF EVERY DOC-ID ASKED, never "at least one" (review fix): a skipped workdir is a hole in the table.
    print(f"  classified on the body as applied, repack having refused: {len(bodies)} of {docs_done}"
          + (f" ({', '.join(bodies)})" if bodies else ""))
    ok(f"layout: {docs_done} of {len(considered)} workdir(s) classified", considered and docs_done == len(considered))
    ok("layout: every doc-id asked has a workdir", not set(args.doc) - set(considered),
       ", ".join(sorted(set(args.doc) - set(considered))))
    print(f"\n{'=' * 98}\n" + (f"FAIL — {len(FAIL)} of {CHECKED} assertions" if FAIL else
                                f"PASS — {CHECKED} assertions. No page of a real document was displayed or kept."))
    print("=" * 98)
    sys.exit(1 if FAIL else 0)

# =========================================================================================
# REAL CORPUS — MECHANICAL ONLY. Renders are made outside the repository and DELETED.
# =========================================================================================
if args.doc:
    if not LOGS.exists():
        print(f"\n  logs folder not reachable at {LOGS}. SKIP, not a pass.")
        sys.exit(0 if not FAIL else 1)
    # REF's WHOLE scripts tree, as the fixture arm above and for the same reason (step 11's
    # sub-step 2b): this arm runs apply AND repack, and a baseline that swapped apply alone ran the
    # working tree's repack on both sides -- VOID for a repack change, never a comparison.
    TMP = Path(tempfile.mkdtemp(prefix="b6-render-"))
    # WHATEVER ENDS THE RUN, the converted .docx and .pdf files of a real document go with it: the rmtree at
    # the end is never reached on a crash, so the folder is also removed at interpreter exit (review fix,
    # 2026-10-08 -- a new step in the loop, the keep declarations, was a new way to crash).
    atexit.register(shutil.rmtree, TMP, ignore_errors=True)
    OLDTREE = TMP / "old_scripts"
    shutil.copytree(ROOT / args.variant / "scripts", OLDTREE)
    lexicons_beside(OLDTREE, ROOT / args.variant)
    _differ = []
    for _n in subprocess.run(["git", "ls-tree", "--name-only", REF, f"{args.variant}/scripts/"],
                             capture_output=True, text=True, cwd=ROOT).stdout.split():
        if not _n.endswith(".py"):
            continue
        blob = subprocess.run(["git", "show", f"{REF}:{_n}"], capture_output=True, cwd=ROOT)
        if blob.returncode != 0:
            print(f"\n  VOID — cannot read {_n} at {REF}.")
            sys.exit(1)
        _name = _n.rsplit("/", 1)[-1]
        if blob.stdout != (ROOT / args.variant / "scripts" / _name).read_bytes():
            _differ.append(_name)
        (OLDTREE / _name).write_bytes(blob.stdout)
    if not _differ:
        print(f"\n  VOID — every script is byte-identical to {REF}: old and new would be the")
        print("  same code, so every page would match for that reason alone.")
        shutil.rmtree(TMP, ignore_errors=True)
        sys.exit(1)
    print(f"\n  baseline arm: {REF}'s whole scripts tree; differing: {', '.join(_differ)}")
    print("  each arm runs: apply -> " + ("post_process -> reorder -> " if args.post_process else "")
          + "repack" + ("" if args.post_process else
                        "  (NO post_process: a change inside it cannot show here; pass --post-process)"))
    CORPUS = corpus_dirs()
    print(f"\n  corpus folder(s) reachable: {len(CORPUS)}")
    wds = [w for w in (sorted(LOGS.rglob("wd")) + sorted(LOGS.rglob("wd-*"))) if w.is_dir()]
    seen, rendered, changed_docs = {}, 0, []
    for wd in wds:
        doc = wd.name[3:] if wd.name.startswith("wd-") else wd.parent.name
        seen[doc] = seen.get(doc, 0) + 1
        label = doc if seen[doc] == 1 else f"{doc} #{seen[doc]}"
        if doc not in args.doc or seen[doc] > 1:
            continue
        nj_src = wd / "paragraphs.json"
        if not nj_src.is_file():
            continue
        notes = json.loads(nj_src.read_text(encoding="utf-8"))
        src, frac = pick_source_docx(wd, notes, CORPUS)
        print(f"\n  {label}  ({len(notes)} notes entries, source matched {frac:.0%})"
              "  — MECHANICAL ONLY, no page displayed or kept")
        print("-" * 98)
        if src is None or frac < 0.5:
            ok(f"{label}: source matched", False, f"best {frac:.0%}")
            continue
        work = TMP / label.replace(" ", "").replace("#", "n")
        work.mkdir(parents=True)
        shutil.copyfile(src, work / "source.docx")
        made = {}
        for arm, scripts_dir in (("old", OLDTREE),
                                 ("new", ROOT / args.variant / "scripts")):
            adir = work / arm
            adir.mkdir()
            shutil.copyfile(src, adir / "source.docx")
            # NOT July's comments_translations.json and headers_footers.json (register I-34): beside the notes
            # they declare ENGLISH for side parts this run delivers in the source's words, which the delivered
            # check inside repack rightly reads as declared-source. No step before repack reads either file;
            # repack() declares every side part KEPT instead, as this run delivers it.
            for n in ("paragraphs.json", ".validate-state.json", "_boldmap.json"):
                if (wd / n).is_file():
                    shutil.copyfile(wd / n, adir / n)
            xml, _ = run_apply(scripts_dir, adir / "source.docx", adir / "paragraphs.json",
                               adir / "document.xml")
            if xml is None:
                ok(f"{label} {arm}: apply produced document.xml", False)
                break
            if args.post_process:
                xml, pp = run_post_process_doc(scripts_dir, adir, xml)
                if xml is None:
                    ok(f"{label} {arm}: post_process and the reorder ran", False, step_failure(pp))
                    break
            deliv, rp = repack(scripts_dir, adir / "source.docx", xml,
                               adir / f"{arm}.docx", adir / "paragraphs.json")
            if deliv is None:
                ok(f"{label} {arm}: repack produced a .docx", False, refusal(rp))
                break
            made[arm] = deliv
        if len(made) != 2:
            continue
        pdfs = {}
        for arm, d in made.items():
            pdf, r = to_pdf(SOFFICE, d, work / arm)
            if pdf is None:
                ok(f"{label} {arm}: converted to PDF", False,
                   (r.stderr or r.stdout or "")[-160:])
            pdfs[arm] = pdf
        ps = None
        spdf, sr = to_pdf(SOFFICE, work / "source.docx", work)
        if not all(pdfs.values()):
            continue
        po, pn = page_hashes(pdfs["old"]), page_hashes(pdfs["new"])
        rendered += 1
        ok(f"{label}: OLD and NEW have the same page count  {len(po)} -> {len(pn)}",
           len(po) == len(pn),
           "a page count that moves on a preservation fix is a layout red flag")
        if spdf is not None:
            ps = page_hashes(spdf)
            print(f"       source renders {len(ps)} page(s); "
                  f"old {len(po)}, new {len(pn)}")
            ok(f"{label}: NEW is no further from the source page count than OLD "
               f"(|{len(pn)}-{len(ps)}| vs |{len(po)}-{len(ps)}|)",
               abs(len(pn) - len(ps)) <= abs(len(po) - len(ps)))
        n = min(len(po), len(pn))
        changed, worst = [], (0.0, None)
        for i in range(n):
            if po[i][0] == pn[i][0]:
                continue
            d = pixel_delta(po[i], pn[i])
            changed.append((i + 1, d))
            if d is not None and d > worst[0]:
                worst = (d, i + 1)
        print(f"       pages whose rendering CHANGED: {len(changed)} of {n}")
        for pg, d in changed[:12]:
            print(f"           page {pg:>3}  {('%.2f%%' % (d * 100)) if d is not None else 'size differs'} of pixels differ")
        if len(changed) > 12:
            print(f"           … and {len(changed) - 12} more")
        if worst[1]:
            print(f"       largest change: page {worst[1]} at {worst[0] * 100:.2f}%")

        # THE HALF THIS TOOL CANNOT DO. Section 5.3 wants a page-by-page READ, and Claude may
        # not perform it on a real document — so hand the pages to someone who may. They go
        # into the LOGS folder, which is where CLAUDE.md 6.4 already puts renders, and only
        # the pages that actually CHANGED, because those are the ones worth a human's time.
        if args.keep_into_logs:
            dest = keep_dir(LOGS, label, args.variant)
            # CLEAR FIRST. THIS WAS THE DEFECT, and Wouter hit it within the hour: the
            # directory was reused, so PNGs from an earlier run survived beside new ones and
            # nothing on screen said which was which. He opened D06 page 2 written at 15:52
            # by the REGRESSION run while the current run had written pages 4-32 at 16:21 --
            # and reasonably read the stale page as the fix's output. A stale artefact
            # indistinguishable from a fresh one is exactly what CLAUDE.md 5.3 is about, and
            # here the artefact was being handed to a reviewer as evidence.
            if dest.exists():
                shutil.rmtree(dest, ignore_errors=True)
            dest.mkdir(parents=True, exist_ok=True)
            import pymupdf
            # AND WRITE THE PAGES A REVIEWER ASKED FOR, CHANGED OR NOT. Writing only changed
            # pages makes ABSENCE ambiguous -- it can mean "identical in both arms" or "this
            # document was never run" -- and the page someone wants to check is often the one
            # that stopped changing, which is the good news. --pages makes that explicit and
            # the manifest below removes the ambiguity either way.
            wanted = {pg for pg, _ in changed} | {
                p for p in args.pages if 1 <= p <= max(len(po), len(pn))}
            written = 0
            by_arm = {"old": [], "new": [], "source": []}
            for arm, pdf in (("old", pdfs["old"]), ("new", pdfs["new"]),
                             ("source", spdf)):
                if pdf is None:
                    continue
                with pymupdf.open(pdf) as doc:
                    for i, page in enumerate(doc):
                        if (i + 1) not in wanted:
                            continue
                        page.get_pixmap(dpi=150).save(
                            str(dest / f"p{i + 1:03d}-{arm}.png"))
                        written += 1
                        by_arm[arm].append(i + 1)
            (dest / "READ-ME.txt").write_bytes(keep_note(
                STAMP, label, args.variant, REF, args.post_process, args.under_review,
                by_arm, [pg for pg, _ in changed]).encode("utf-8"))
            # A MANIFEST, SO ABSENCE IS NEVER AMBIGUOUS. Without it, "no page 2 here" reads
            # identically as "page 2 is unchanged" and "this document was never rendered".
            man = [f"run written: {STAMP}",
                   f"document: {label}",
                   f"pages in old / new / source: {len(po)} / {len(pn)} / "
                   f"{len(ps) if spdf is not None else 'n/a'}",
                   f"pages whose rendering CHANGED between old and new: "
                   f"{sorted(pg for pg, _ in changed) or 'NONE'}",
                   f"pages forced by --pages: {sorted(set(args.pages)) or 'none'}",
                   f"PNGs written: {written}",
                   "",
                   "A page number absent below is a page this run did NOT write. The",
                   "directory was CLEARED before writing, so nothing here is from an",
                   "earlier run.",
                   "written pages, per arm: " + "  ".join(
                       f"{arm} {pages or 'NONE'}" for arm, pages in by_arm.items())]
            (dest / "MANIFEST.txt").write_text("\n".join(man) + "\n", encoding="utf-8")
            print(f"       {written} PNG(s) for a HUMAN to read: "
                  f"{LOGS.name}/branch6-render/{dest.name}/  (not displayed here)")
        # NOT AN ASSERTION, AND IT USED TO BE ONE. "At least one page changed" is true of a
        # BRANCH that moves delivered bytes; it is NOT true of every document, and asserting
        # it per document produced a failure that was actually the most useful result of the
        # run. On 2026-09-01 D02 lost 45 stranded tabs and had 14 comment anchors restored,
        # and NOT ONE PIXEL moved on any of its 11 pages — because a stranded tab advances
        # into empty space and a comment anchor is not printed at all. The count said 45
        # destroyed; the page said nothing happened. CLAUDE.md 2.4 item 7: judge a layout
        # device on its RENDERED EFFECT, never on its element count.
        if not changed:
            print("       0 pages re-rendered — every change on this document is "
                  "structural and invisible in print. Not a failure; a result.")
        changed_docs.append(label if changed else None)
    ok(f"at least one document re-rendered ({sum(1 for c in changed_docs if c)} of "
       f"{len(changed_docs)}) \u2014 a step that moves delivered bytes must change "
       "SOME page, though not every document need change one",
       any(changed_docs))
    shutil.rmtree(TMP, ignore_errors=True)
    if not rendered:
        print("\n  VOID — no document was rendered. Not a clean run.")
        sys.exit(1)

print()
print("=" * 98)
if FAIL:
    print(f"FAIL — {len(FAIL)} of {CHECKED} assertions:")
    for f in FAIL:
        print(f"  ·  {f}")
    print("=" * 98)
    sys.exit(1)
print(f"PASS — {CHECKED} assertions. No page of a real document was displayed or kept.")
print("=" * 98)
