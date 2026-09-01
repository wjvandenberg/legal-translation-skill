# -*- coding: utf-8 -*-
"""THE RENDERED PAGE COMPARISON — CLAUDE.md 5.3's gate, made runnable.

Section 5.3 makes a "rendered PDF visual diff against the source, page by page, BOTH
documents" a condition of done for every branch, and 2.5 item 4 calls the rendered diff the
PRIMARY instrument rather than a final check. No tool existed for it. This is that tool.

ONE CONSTRAINT SHAPES THE WHOLE DESIGN, AND IT IS A CONFIDENTIALITY CONSTRAINT RATHER THAN A
TECHNICAL ONE. A rendered page of a corpus document is client text as an image. CLAUDE.md 6.5
says session metadata is reachable by neither the scanners nor the location rule, so there is
no after-the-fact remedy and it cannot be un-said. THEREFORE CLAUDE MAY NEVER LOOK AT A
RENDER OF A REAL DOCUMENT. The gate splits in two:

  --doc ID       REAL CORPUS. Renders outside the repository, compares pages MECHANICALLY,
                 prints percentages and page counts, then DELETES every image. No page is
                 ever displayed, kept or committed. A human may look; this tool may not show.
  --fixture N    SYNTHETIC FIXTURE. No client text exists in it, so the PNGs are written to
                 gitignored temp/render/ and CAN be looked at. This is where a genuine visual
                 inspection happens.

WHICH COMPARISON ACTUALLY MEANS SOMETHING, because "source against target" cannot be a pixel
diff. The target is TRANSLATED: nearly every glyph differs, so a pixel comparison against the
source measures the translation, not the pipeline. What isolates this branch is:

  OLD vs NEW deliverable   same document, same notes, same language, ONE variable: the code.
                           This is the diff that shows what branch 6 changed on the page.
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
import hashlib
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

from lxml import etree

ROOT = Path(__file__).resolve().parent.parent
W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
LOGS = Path(os.environ.get("LT_LOGS_DIR", ROOT.parent / "legal-translation-logs"))
SCRIPT = "apply_translations_textmatch.py"
REF = os.environ.get("LT_BASELINE_REF", "79a8c14")
DPI = int(os.environ.get("LT_RENDER_DPI", "100"))

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


def corpus_dirs():
    out, cfg = [], ROOT / ".claude" / "evidence-dirs.local"
    names = []
    if cfg.is_file():
        names += [ln.strip() for ln in
                  cfg.read_text(encoding="utf-8", errors="replace").splitlines()
                  if ln.strip() and not ln.strip().startswith("#")]
    if os.environ.get("LT_CORPUS_DIR"):
        names.append(os.environ["LT_CORPUS_DIR"])
    for name in names:
        p = Path(name)
        if not p.is_absolute():
            p = (ROOT.parent / name).resolve()
        if p.is_dir() and any(p.glob("*.docx")):
            out.append(p)
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


def to_pdf(soffice, docx_path, outdir):
    """Convert with a PRIVATE user profile, so this cannot collide with a running Office."""
    prof = (outdir / "loprofile").as_uri()
    r = subprocess.run(
        [soffice, f"-env:UserInstallation={prof}", "--headless", "--norestore",
         "--convert-to", "pdf", "--outdir", str(outdir), str(docx_path)],
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


ap = argparse.ArgumentParser()
ap.add_argument("--doc", action="append", default=[], help="corpus doc-id (real, mechanical)")
ap.add_argument("--fixture", action="append", default=[],
                help="synthetic fixture stem (renders are kept and may be viewed)")
ap.add_argument("--variant", default="uk", choices=("uk", "us"))
ap.add_argument("--keep-into-logs", action="store_true",
                help="write the real-corpus renders into the LOGS folder for a HUMAN to "
                     "open. They are still never displayed here.")
args = ap.parse_args()

SOFFICE = find_soffice()
print("=" * 98)
print("RENDERED PAGE COMPARISON — CLAUDE.md 5.3")
print("=" * 98)
if not SOFFICE:
    print("  VOID — LibreOffice not found. Set LT_SOFFICE. Nothing rendered, nothing proved.")
    sys.exit(1)
print(f"  soffice: {SOFFICE}")
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
    env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1",
               PYTHONDONTWRITEBYTECODE="1")
    p = subprocess.run(
        ["uv", "run", "--with", "lxml", "python", str(scripts_dir / SCRIPT),
         str(src_docx), str(notes_json), str(out_xml)],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        cwd=str(ROOT), env=env, timeout=1800)
    return (out_xml if out_xml.is_file() else None), p


def repack(scripts_dir, src_docx, doc_xml, out_docx, notes_json):
    env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1",
               PYTHONDONTWRITEBYTECODE="1")
    p = subprocess.run(
        ["uv", "run", "--with", "lxml", "python", str(scripts_dir / "repack_docx.py"),
         str(src_docx), str(doc_xml), str(out_docx), "--paragraphs", str(notes_json)],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        cwd=str(ROOT), env=env, timeout=900)
    return (out_docx if out_docx.is_file() else None), p


# =========================================================================================
# SYNTHETIC FIXTURES — renders KEPT, because there is no client text in them.
# =========================================================================================
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
    root = etree.fromstring(src_xml)
    notes = [{"idx": i, "text": t, "en": (t + " EN") if t else t, "style": "Normal"}
             for i, t in enumerate(para_texts(src_xml))]
    nj = outdir / "paragraphs.json"
    nj.write_text(json.dumps(notes, ensure_ascii=False), encoding="utf-8")
    shutil.copyfile(fx, outdir / "source.docx")
    xml, _ = run_apply(ROOT / args.variant / "scripts", outdir / "source.docx", nj,
                       outdir / "document.xml")
    if xml is None:
        ok(f"{stem}: apply produced document.xml", False)
        continue
    deliv, rp = repack(ROOT / args.variant / "scripts", outdir / "source.docx", xml,
                       outdir / "applied.docx", nj)
    if deliv is None:
        ok(f"{stem}: repack produced a .docx", False,
           (rp.stderr or rp.stdout or "")[-200:])
        continue
    pdfs = {}
    for name in ("source", "applied"):
        pdf, r = to_pdf(SOFFICE, outdir / f"{name}.docx", outdir)
        if pdf is None:
            ok(f"{stem}: {name}.docx converted to PDF", False,
               (r.stderr or r.stdout or "")[-200:])
        pdfs[name] = pdf
    if not all(pdfs.values()):
        continue
    for name, pdf in pdfs.items():
        pages = page_hashes(pdf)
        import pymupdf
        with pymupdf.open(pdf) as doc:
            for i, page in enumerate(doc):
                page.get_pixmap(dpi=DPI).save(str(outdir / f"{name}-p{i + 1}.png"))
        print(f"       {name}: {len(pages)} page(s) rendered -> temp/render/{stem}/")
    sp, ap_ = page_hashes(pdfs["source"]), page_hashes(pdfs["applied"])
    ok(f"{stem}: page count unchanged  {len(sp)} -> {len(ap_)}", len(sp) == len(ap_))

# =========================================================================================
# REAL CORPUS — MECHANICAL ONLY. Renders are made outside the repository and DELETED.
# =========================================================================================
if args.doc:
    if not LOGS.exists():
        print(f"\n  logs folder not reachable at {LOGS}. SKIP, not a pass.")
        sys.exit(0 if not FAIL else 1)
    blob = subprocess.run(["git", "show", f"{REF}:{args.variant}/scripts/{SCRIPT}"],
                          capture_output=True, cwd=ROOT)
    if blob.returncode != 0:
        print(f"\n  VOID — cannot read {SCRIPT} at {REF}.")
        sys.exit(1)
    TMP = Path(tempfile.mkdtemp(prefix="b6-render-"))
    OLDTREE = TMP / "old_scripts"
    shutil.copytree(ROOT / args.variant / "scripts", OLDTREE)
    (OLDTREE / SCRIPT).write_bytes(blob.stdout)
    if blob.stdout == (ROOT / args.variant / "scripts" / SCRIPT).read_bytes():
        print(f"\n  VOID — {SCRIPT} is byte-identical to {REF}: old and new would be the")
        print("  same code, so every page would match for that reason alone.")
        shutil.rmtree(TMP, ignore_errors=True)
        sys.exit(1)
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
            for n in ("paragraphs.json", ".validate-state.json",
                      "comments_translations.json", "headers_footers.json",
                      "_boldmap.json"):
                if (wd / n).is_file():
                    shutil.copyfile(wd / n, adir / n)
            xml, _ = run_apply(scripts_dir, adir / "source.docx", adir / "paragraphs.json",
                               adir / "document.xml")
            if xml is None:
                ok(f"{label} {arm}: apply produced document.xml", False)
                break
            deliv, rp = repack(scripts_dir, adir / "source.docx", xml,
                               adir / f"{arm}.docx", adir / "paragraphs.json")
            if deliv is None:
                ok(f"{label} {arm}: repack produced a .docx", False,
                   (rp.stderr or rp.stdout or "")[-160:])
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
        # into the LOGS folder, which is where CLAUDE.md 6.5 already puts renders, and only
        # the pages that actually CHANGED, because those are the ones worth a human's time.
        if args.keep_into_logs:
            dest = LOGS / "branch6-render" / label.replace(" ", "").replace("#", "n")
            dest.mkdir(parents=True, exist_ok=True)
            import pymupdf
            wanted = {pg for pg, _ in changed}
            written = 0
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
            (dest / "READ-ME.txt").write_text(
                "Branch 6 rendered comparison. One PNG per CHANGED page, three arms:\n"
                "  p<NNN>-old.png     the deliverable as the code stood at the pinned\n"
                "                     baseline, i.e. WITHOUT branch 6\n"
                "  p<NNN>-new.png     the deliverable WITH branch 6\n"
                "  p<NNN>-source.png  the original document, for reference\n\n"
                "What to look for, in order:\n"
                "  1. footnote and comment markers PRESENT in -new where they were absent\n"
                "     in -old, with the footnote text at the foot of its page\n"
                "  2. table-of-contents entries: the dot leader and the right-aligned page\n"
                "     number should be back, and each entry should be a working link\n"
                "  3. cross-references should appear ONCE in -new. In -old some appear\n"
                "     twice, and six carry 'Error: Reference source not found'\n"
                "  4. THE KNOWN LIMITATION: where a tab sat between two pieces of text, it\n"
                "     is back in the file but lands AFTER the text, so a hanging-indent\n"
                "     list item still reads glued. That is branch 16's, not branch 6's.\n\n"
                "These are renders of a real client document. They live here, outside the\n"
                "repository, and must never be committed or pasted anywhere.\n",
                encoding="utf-8")
            print(f"       {written} PNG(s) for a HUMAN to read: "
                  f"{LOGS.name}/branch6-render/{dest.name}/  (not displayed here)")
        # NOT AN ASSERTION, AND IT USED TO BE ONE. "At least one page changed" is true of a
        # BRANCH that moves delivered bytes; it is NOT true of every document, and asserting
        # it per document produced a failure that was actually the most useful result of the
        # run. On 2026-09-01 D02 lost 45 stranded tabs and had 14 comment anchors restored,
        # and NOT ONE PIXEL moved on any of its 11 pages — because a stranded tab advances
        # into empty space and a comment anchor is not printed at all. The count said 45
        # destroyed; the page said nothing happened. CLAUDE.md 2.5 item 7: judge a layout
        # device on its RENDERED EFFECT, never on its element count.
        if not changed:
            print("       0 pages re-rendered — every change on this document is "
                  "structural and invisible in print. Not a failure; a result.")
        changed_docs.append(label if changed else None)
    ok(f"at least one document re-rendered ({sum(1 for c in changed_docs if c)} of "
       f"{len(changed_docs)}) \u2014 a branch that moves delivered bytes must change "
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
