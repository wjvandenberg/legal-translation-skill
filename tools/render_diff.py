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
import time
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
# PINNED TO A COMMIT, NEVER TO A BRANCH NAME OR HEAD -- CLAUDE.md 5.16. Moved to 049484e on
# 2026-09-02, the squash-merge of branch 6 slice 2 (PR #59), which `git log -- uk us` confirms
# is the last commit to touch either tree. Kept in step with the same pin in
# tools/apply_corpus_diff.py: the two tools answer the same before-and-after question, one in
# bytes and one in pixels, and a disagreement between their baselines would be invisible.
REF = os.environ.get("LT_BASELINE_REF", "2a71e71")
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
ap.add_argument("--expect-block", action="append", default=[],
                help="fixture stem whose NEW arm is EXPECTED to be refused by a gate. Its "
                     "old arm still renders, so the page shows what used to ship; a run "
                     "that produced output anyway is the FAILURE for such a fixture")
ap.add_argument("--variant", default="uk", choices=("uk", "us"))
ap.add_argument("--pages", type=int, action="append", default=[],
                help="force these page numbers to be written even if they did not change "
                     "— the page a reviewer wants is often the one that stopped changing")
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

    WHY THIS EXISTS, AND WHY IT IS NOT A WAY ROUND A GATE. Branch 6's fourth slice found that
    the PRE-FIX code cannot be repacked at all on the whitespace fixture: clearing a
    whitespace-only segment glues two words into one, `validate_apply --strict` compares token
    SETS, and a merged token is a token set that no longer matches -- so repack refuses. That
    is a real finding (the operator who follows Step 4 rule 9 is deadlocked, F41's family) and
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
# A PINNED-BASELINE ARM FOR FIXTURES, BUILT ONCE. Added for branch 6's fourth slice.
#
# WITHOUT IT A FIXTURE RENDER SHOWS `source` VERSUS `applied-with-whatever-is-in-the-tree`, so
# the DEFECT is not on any page and the reviewer is asked to take the improvement on trust.
# Slice 3 hit exactly this and worked around it by hand -- "rendering a third arm from the
# pre-widening script" -- which is a step nobody can repeat and nothing records. The real
# corpus path has had this arm since it was written; the fixture path did not, and the
# asymmetry was invisible because only the corpus path was ever red.
FX_OLDTREE = None
if args.fixture:
    _blob = subprocess.run(["git", "show", f"{REF}:{args.variant}/scripts/{SCRIPT}"],
                           capture_output=True, cwd=ROOT)
    if _blob.returncode != 0:
        print(f"\n  VOID — cannot read {SCRIPT} at {REF}; no baseline arm for the fixtures.")
        sys.exit(1)
    _fxtmp = Path(tempfile.mkdtemp(prefix="fx-oldtree-"))
    FX_OLDTREE = _fxtmp / "old_scripts"
    shutil.copytree(ROOT / args.variant / "scripts", FX_OLDTREE)
    (FX_OLDTREE / SCRIPT).write_bytes(_blob.stdout)
    # The sentinel is a plain string at the file's end, so a copied script still passes its own
    # integrity check -- proved rather than assumed, because failing it would exit 3 and the
    # arm would silently not exist.
    if b"\n# === SKILL FILE COMPLETE ===" not in (FX_OLDTREE / SCRIPT).read_bytes():
        print("  VOID — the baseline copy has no integrity sentinel; it would exit 3.")
        sys.exit(1)
    _same = _blob.stdout == (ROOT / args.variant / "scripts" / SCRIPT).read_bytes()
    print(f"  fixture baseline arm: {REF}"
          + ("   NOTE: BYTE-IDENTICAL to the working tree, so old and new are the same code "
             "and an all-quiet render proves nothing" if _same else ""))

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
        xml, p_ = run_apply(scripts_dir, adir / "source.docx", adir / "paragraphs.json",
                            adir / "document.xml")
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
            ok(f"{stem}: repack produced a .docx ({arm} arm)", False,
               (rp.stderr or rp.stdout or "")[-200:])
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
        "improvement rather than see it, which is what happened on the previous slice.",
        "",
        "WHAT THIS SLICE CHANGED — C17, C16 and F16, all three about a boundary apply could",
        "not describe and resolved silently, in the direction that destroyed something.",
        "",
        "  whitespace-arms.docx — the document LABELS ITS OWN ROWS, so nothing here has to",
        "  be taken on trust. Read the labels, then the line under each:",
        "    ARM 1 (two lines)  a one-space tracked insertion between two sentences. In",
        "                       `old` the two sentences are GLUED together; in `new` there",
        "                       is a space. The second of the two is the register's own",
        "                       example, and post_process would have masked it by accident.",
        "    NEGATIVE (one line) an explicitly empty segment. MUST look identical in both",
        "                       arms — if it changed, the fix broke the documented device",
        "                       that clears a run.",
        "    ARM 2 (two lines)  the first must begin with ONE leading space in `new` and TWO",
        "                       in `old`. The second must be IDENTICAL in both — a single",
        "                       source space is still restored, and that repair had to",
        "                       survive.",
        "",
        "  en-runs-offsets.docx — THERE IS NO `new` PAGE, AND THAT IS THE RESULT. The",
        "  offsets point past the end of the string, and apply now REFUSES rather than",
        "  slicing the wrong characters. Compare `old`: every character is present and the",
        "  BOLD is on the wrong words — `8.1, as adjusted.` instead of `8.1`. That is the",
        "  defect, and it exited 0.",
        "",
        "WHAT THESE PAGES ARE NOT. They come from apply + repack only, never the",
        "eleven-step pipeline: no definitions reorder, no tidy-up pass, no post_process. So",
        "post_process's seam repair has NOT run — which is deliberate, because it would",
        "have masked one of the two ARM 1 lines and hidden what apply actually delivered.",
        "",
    ]) + "\n").encode("utf-8"))

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
        # into the LOGS folder, which is where CLAUDE.md 6.5 already puts renders, and only
        # the pages that actually CHANGED, because those are the ones worth a human's time.
        if args.keep_into_logs:
            dest = LOGS / "branch6-render" / label.replace(" ", "").replace("#", "n")
            # CLEAR FIRST. THIS WAS THE DEFECT, and Wouter hit it within the hour: the
            # directory was reused, so PNGs from an earlier run survived beside new ones and
            # nothing on screen said which was which. He opened D06 page 2 written at 15:52
            # by the REGRESSION run while the current run had written pages 4-32 at 16:21 --
            # and reasonably read the stale page as the fix's output. A stale artefact
            # indistinguishable from a fresh one is exactly what CLAUDE.md 5.16 is about, and
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
                f"  p<NNN>-old.png     the deliverable as the code stood at {REF}, the\n"
                "                     PINNED BASELINE. Read that literally: the baseline\n"
                "                     moves as each slice merges, so -old is NOT 'before\n"
                "                     branch 6'. It is 'before the change under review'.\n"
                "  p<NNN>-new.png     the deliverable with the working tree's code\n"
                "  p<NNN>-source.png  the original document, for reference\n\n"
                "THE CHANGE UNDER REVIEW IS WHITESPACE AT A SEGMENT BOUNDARY -- C17, C16 and\n"
                "the F16 offset guard. Rewritten 2026-09-02, for the third slice in a row.\n"
                "The text here described the PREVIOUS change (the table-of-contents\n"
                "page-number widening) and would now send you looking for something already\n"
                "in -old, the same way a stale pinned-baseline comment misdirects. It is\n"
                "rewritten on every change to what is under review, and that is not optional.\n\n"
                "EXPECT EXACTLY THREE PARAGRAPHS TO CHANGE, ON TWO DOCUMENTS, AND NOTHING\n"
                "ELSE. Measured across all thirteen frozen intermediates: D02 two paragraphs\n"
                "and D07 one, ten documents byte-identical, no unexplained movement.\n\n"
                "C17 -- a tracked-change segment whose declared English is a single SPACE was\n"
                "read as a request to clear the run, because the code tested the string for\n"
                "truthiness after stripping it. Step 4 rule 9 tells the operator to mirror\n"
                "source whitespace, so the manual instructed them into the one input the code\n"
                "could not read. Three real instances, and in EVERY ONE the space sits at the\n"
                "END of its paragraph -- so THERE IS NOTHING TO SEE ON THESE PAGES, and that\n"
                "is not a failed run. A trailing space renders as nothing. The visible form\n"
                "of this defect -- two sentences glued together mid-paragraph -- exists only\n"
                "on the synthetic fixture, because no corpus document carries that shape.\n\n"
                "What to look for, in order:\n"
                "  1. -old AND -new SHOULD BE INDISTINGUISHABLE ON EVERY PAGE. All three\n"
                "     changed paragraphs gained a trailing space, which no renderer shows.\n"
                "     Any VISIBLE difference is therefore a finding, not the fix working.\n"
                "  2. NO WORD GLUED TO ITS NEIGHBOUR that was separate in -old, and no new\n"
                "     double space between words. The fix changes whitespace, so a whitespace\n"
                "     regression is the failure mode with the shortest path from this change.\n"
                "  3. NO WRAPPED LINE that did not wrap in -old.\n"
                "  4. THE TABLE OF CONTENTS SHOULD BE UNTOUCHED -- number, gap, title, dot\n"
                "     leader, page number at the right margin, exactly as the previous two\n"
                "     slices left it. It should NOT have changed at all.\n"
                "  5. THE KNOWN LIMITATION, AND THIS SLICE DID NOT CLOSE IT. C16 -- a double\n"
                "     space apply CREATES -- is only PARTIALLY fixed. Two mechanisms were\n"
                "     found and repaired, both proved on the synthetic fixture, but on the\n"
                "     real corpus no attributable double space was removed: D07 still carries\n"
                "     three that exceed both its source's own count and the operator's\n"
                "     declared ones. If you see a double space between words, it was there in\n"
                "     -old too. Check that it was.\n\n"
                "A LINE THAT LOOKS UNCHANGED IS NOT AUTOMATICALLY A FAILED RUN, AND THIS NOTE\n"
                "IS HERE BECAUSE THE PREVIOUS SLICE'S FIRST REVIEW READ FLAT LINES AS DAMAGE.\n"
                "The synthetic fixtures LABEL THEIR OWN ROWS on the page\n"
                # NOT `labels read:\\n\\n` -- a colon followed by two escapes reads as the
                # Windows path `d:\\n\\n` to the committed-script scan, which blocked the
                # commit. The pattern is right to be broad: narrowing it would miss a real
                # `C:\\network\\...`, and a leaked path cannot be rotated. Reworded instead.
                "itself so nobody has to take that on trust. For this slice the fixture is\n"
                "tests/fixtures/whitespace-arms.docx, rendered to temp/render/, and its three\n"
                "labels are\n\n"
                "  'ARM 1 - C17. The two below MUST read as two sentences with a space\n"
                "   between them. Glued together is the defect:'\n"
                "  'NEGATIVE CONTROL. The line below MUST look the same in both arms - an\n"
                "   explicitly empty segment goes on being cleared:'\n"
                "  'ARM 2 - C16. The FIRST line below MUST begin with ONE leading space, not\n"
                "   two. The SECOND MUST look identical in both arms ...'\n\n"
                "THAT FIXTURE IS WHERE THIS CHANGE IS VISIBLE AND THESE PAGES ARE NOT. The\n"
                "three real instances are trailing spaces at a paragraph end; the glued-\n"
                "sentence form the register describes appears on no corpus document, which is\n"
                "why the fixture had to be built. A second fixture, en-runs-offsets.docx,\n"
                "carries F16 -- and the corpus CANNOT carry that one at all, because the\n"
                "frozen intermediates are the post-compliance artefact and the offsets are\n"
                "checked before apply runs, so a run with bad offsets never produced one.\n\n"
                "These are renders of a real client document. They live here, outside the\n"
                "repository, and must never be committed or pasted anywhere.\n\n"
                "WHAT THESE PAGES ARE, AND WHAT THEY ARE NOT. They come from apply + repack\n"
                "ONLY -- not the eleven-step pipeline. So the definitions are NOT reordered,\n"
                "the tidy-up pass has not run, and headers, footers, comments and footnotes\n"
                "are still in the source language. That is deliberate: it isolates the one\n"
                "code change under review. Do not read a missing definitions reorder, or an\n"
                "untranslated footnote, as a defect -- neither step was run.\n",
                encoding="utf-8")
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
                   f"written pages: {sorted(wanted) or 'NONE'}"]
            (dest / "MANIFEST.txt").write_text("\n".join(man) + "\n", encoding="utf-8")
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
