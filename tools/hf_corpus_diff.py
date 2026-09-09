# -*- coding: utf-8 -*-
"""THE CORPUS ARM FOR translate_headers_footers.py — what Step 8b does DIFFERENTLY, on the
real corpus. Branch 7 slice 3, register A19.

WHY THIS TOOL EXISTS, AND IT IS NOT ABOUT A19's OWN SURFACE. tools/apply_corpus_diff.py
drives `apply_translations_textmatch.py` over `word/document.xml`. Slice 3 changes
`translate_headers_footers.py` and an extraction REPORT, so that tool's two arms are
byte-identical BY DESIGN and its all-quiet result proves nothing here -- the same shape slice
2 met and declared. Until this file existed, NOTHING in this repository measured the
header/footer translator against a real document at all.

AND THE THING IT ACTUALLY GUARDS IS THE SCAFFOLD SHAPE, NOT THE ALT TEXT. Slice 3 adds a new
kind of entry to `headers_footers.json`. Every one of the frozen scaffolds was written before
that key existed, so `apply_from_scaffold` must go on treating a `kind`-less entry as a
paragraph entry -- and if it stopped, every real document's headers and footers would
silently stop being translated while the fixture suite went on passing, because a
freshly-extracted fixture scaffold HAS the key. That is the regression this measures.

    ARM 1  APPLY, OLD vs NEW, over the frozen scaffolds. The written header/footer XMLs must
           be BYTE-IDENTICAL: the frozen scaffolds carry no graphic-metadata entry, so there
           is nothing for the new code to do and any movement at all is a defect.
    ARM 2  EXTRACT, over the corpus. How many graphic-metadata surfaces does the new
           --extract offer? The expected answer is ZERO, because the corpus carries 14
           graphics and not one attribute of prose -- and a bare zero is worth nothing, so
    ARM 3  THE POSITIVE CONTROL. A `@descr` is PLANTED into a temporary copy of a real
           document's header and the same code path must offer it. A run whose control did
           not fire is VOID, never clean.

OUTPUT POLICY, copied in effect from tools/apply_corpus_diff.py's. Corpus doc ORDINALS, part
KINDS, and counts. It never prints a filename, a directory name below either root, a
paragraph, any document text, or any attribute VALUE -- an `@descr` or an `@name` on a real
document could carry a project or a party name. The only string it ever echoes is the needle
it planted itself.

NOTHING IS EVER WRITTEN INTO THE LOGS OR THE CORPUS FOLDER. Both are BASELINES; every input
is copied into a temporary directory first, and a baseline the tool measuring it can modify
is not a baseline.

    uv run --with lxml python tools/hf_corpus_diff.py
    uv run --with lxml python tools/hf_corpus_diff.py --variant us
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

from lxml import etree                                                    # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
LOGS = Path(os.environ.get("LT_LOGS_DIR", ROOT.parent / "legal-translation-logs"))

SCRIPT = "translate_headers_footers.py"
# THE SECOND SCRIPT IS NOT OPTIONAL AND IT IS EASY TO MISS. Since slice 3 the translator
# IMPORTS the graphic-metadata inventory from extract_paragraphs.py. tools/apply_corpus_diff.py
# builds its old arm by copying the CURRENT scripts directory and overwriting one file -- so
# pinning only the translator would leave the OLD translator sitting beside the NEW inventory.
# Both are pinned here, and this comment is the reason.
PINNED = (SCRIPT, "extract_paragraphs.py")

# A FIXED PIN, NOT A MOVING ONE, AND THAT IS THE OPPOSITE OF apply_corpus_diff.py's RULE --
# decided on a measurement at branch 7's close, 2026-09-09.
#
# ae48f6d is the squash-merge of branch 7 slice 2: THE LAST COMMIT BEFORE THE `kind` KEY
# EXISTED. That is the whole point. What arm 1 proves is that a scaffold entry with NO `kind`
# key is still treated as a paragraph entry -- and every one of the 10 frozen header/footer
# scaffolds predates that key, so if it ever stopped holding, real documents would silently
# stop having their headers and footers translated while the fixture suite went on passing.
#
# THAT QUESTION ONLY EXISTS AGAINST A TREE THAT PREDATES THE KEY. Measured before deciding:
# with the pin moved to 010c34f (branch 7 slice 3's merge, the normal thing to do at a close)
# both arms carry the new code, the VOID guard below fires correctly, and this tool reports
# `VOID -- every pinned script is BYTE-IDENTICAL` on EVERY RUN, for ever, until the
# translator next changes. A check that can only report VOID is not a check, and a
# permanently-red row in the sweep is one people learn to scroll past -- CLAUDE.md 5.3's
# fourth rule, from the other side.
#
# SO IT FOLLOWS tests/test_no_delivered_byte_moves.py's PRECEDENT rather than
# apply_corpus_diff.py's: that suite, test_check_scoping.py and
# test_check_scoping_properties.py all pin to a FIXED pre-change revision (2178cce) for the
# same reason. Three suites already do this; this is the fourth.
#
# WHEN TO MOVE IT, AND IT IS NOT AT A CLOSE. Move it only when a future branch LEGITIMATELY
# changes what this script writes for real header/footer paragraphs -- at which point arm 1
# goes red, which is correct, and whoever moved the bytes records why and re-pins here in the
# same commit. Until then it stays where it is, and a close that mechanically "moves both
# pins" must leave this one alone.
REF = os.environ.get("LT_BASELINE_REF", "ae48f6d")

ap = argparse.ArgumentParser()
ap.add_argument("--variant", default="uk", choices=("uk", "us"))
ap.add_argument("--ref", default=REF)
ap.add_argument("--keep", action="store_true")
args = ap.parse_args()

PLANTED = "ZZ_A19_PLANTED_CONTROL_alt_text_ZZ"
FAIL, VOIDED, NOTES = [], [], []


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


def part_kind(name):
    base = name.rsplit("/", 1)[-1]
    if base.startswith("header"):
        return "header"
    if base.startswith("footer"):
        return "footer"
    return "other"


def own_runs(p_elem):
    """_iter_own_runs' rule, reimplemented so this tool does not import the script it
    measures -- an instrument that imports its subject cannot see the subject change."""
    p_tag = f"{{{W}}}p"
    for r in p_elem.iter(f"{{{W}}}r"):
        a, nested = r.getparent(), False
        while a is not None and a is not p_elem:
            if a.tag == p_tag:
                nested = True
                break
            a = a.getparent()
        if not nested:
            yield r


def hf_texts(docx_path):
    """Every non-empty header/footer paragraph text in a document. Used ONLY to match a
    frozen scaffold to its document -- by TEXT, never by index."""
    out = set()
    with zipfile.ZipFile(docx_path) as zf:
        for n in zf.namelist():
            if not (n.startswith("word/") and n.endswith(".xml")):
                continue
            if part_kind(n) == "other":
                continue
            root = etree.fromstring(zf.read(n))
            for p in root.iter(f"{{{W}}}p"):
                t = "".join(x.text for r in own_runs(p)
                            for x in r.findall(f"{{{W}}}t") if x.text)
                if t.strip():
                    out.add(t)
    return out


def run_script(scripts_dir, argv, timeout=600):
    return subprocess.run(
        ["uv", "run", "--with", "lxml", "python", str(scripts_dir / SCRIPT)]
        + [str(a) for a in argv],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        cwd=str(ROOT),
        env=dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1",
                 PYTHONDONTWRITEBYTECODE="1"),
        timeout=timeout)


print("=" * 96)
print(f"HEADER/FOOTER CORPUS ARM — translate_headers_footers.py   [{args.variant} tree]")
print("=" * 96)

# ---- GUARDS. Each of these is a run that would otherwise report clean over nothing. ----
CORPUS = corpus_dirs()
if not CORPUS:
    print("  SKIP — no corpus directory discovered. Set LT_CORPUS_DIR or write")
    print("  .claude/evidence-dirs.local. This is a SKIP, not a pass.")
    sys.exit(0)
if not LOGS.is_dir():
    print(f"  SKIP — logs root not present at {LOGS.name}. Set LT_LOGS_DIR.")
    print("  This is a SKIP, not a pass.")
    sys.exit(0)

r = subprocess.run(["git", "rev-parse", "--verify", args.ref],
                   capture_output=True, text=True, cwd=ROOT)
if r.returncode != 0:
    print(f"  VOID — baseline ref {args.ref} does not resolve. Nothing compared.")
    sys.exit(1)
SHA = r.stdout.strip()
print(f"  baseline: {args.ref} = {SHA[:12]}")

TMP = Path(tempfile.mkdtemp(prefix="b7s3-hf-"))
OLDTREE = TMP / "old_scripts"
shutil.copytree(ROOT / args.variant / "scripts", OLDTREE)
identical = []
for name in PINNED:
    blob = subprocess.run(["git", "show", f"{args.ref}:{args.variant}/scripts/{name}"],
                          capture_output=True, cwd=ROOT)
    if blob.returncode != 0:
        print(f"  VOID — cannot read {name} at {args.ref}.")
        sys.exit(1)
    if blob.stdout == (ROOT / args.variant / "scripts" / name).read_bytes():
        identical.append(name)
    (OLDTREE / name).write_bytes(blob.stdout)
    print(f"  pinned into the old arm: {name}")

# A COMPARISON OF A FILE WITH ITSELF IS TRIVIALLY IDENTICAL, WHICH IS EXACTLY THE RESULT A
# "nothing moved" READING WANTS. CLAUDE.md 5.3's rule with no house twin.
if len(identical) == len(PINNED):
    print(f"  VOID — every pinned script is BYTE-IDENTICAL to {args.ref}, so arm 1 is the")
    print("  same code against itself. That is not a clean run; it is no run. Point")
    print("  LT_BASELINE_REF at a commit that predates the change.")
    VOIDED.append("arm 1: baseline byte-identical to the working tree")
elif identical:
    print(f"  NOTE: {len(identical)} of {len(PINNED)} pinned script(s) unchanged since "
          f"{args.ref}: {identical}")

docs = sorted(p for d in CORPUS for p in d.glob("*.docx"))
legacy = sorted(p for d in CORPUS for p in d.glob("*.doc"))
wds = sorted(p.parent for p in LOGS.rglob("paragraphs.json"))
with_hf = [d for d in wds if (d / "headers_footers.json").is_file()]
print(f"\n  POPULATION, enumerated by listing rather than assumed:")
print(f"    corpus .docx opened                : {len(docs)}")
print(f"    corpus legacy .doc NOT opened      : {len(legacy)} (binary, no zip)")
print(f"    frozen workdirs                    : {len(wds)}")
print(f"    ... carrying a headers_footers.json: {len(with_hf)}")

# ---- Match each scaffold to its document, by TEXT. ----
doc_texts = {}
unreadable = []
for i, p in enumerate(docs, 1):
    try:
        doc_texts[i] = hf_texts(p)
    except Exception as exc:
        unreadable.append((i, type(exc).__name__))
if unreadable:
    print(f"    COULD NOT READ {len(unreadable)} document(s) — reported, never skipped:")
    for i, why in unreadable:
        print(f"      ordinal {i}: {why}")
    VOIDED.append(f"{len(unreadable)} corpus document(s) unreadable")

matched = []
for wi, wd in enumerate(wds, 1):
    hf = wd / "headers_footers.json"
    if not hf.is_file():
        continue
    try:
        entries = json.loads(hf.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"    workdir {wi}: headers_footers.json unreadable ({type(exc).__name__})")
        VOIDED.append(f"workdir {wi} scaffold unreadable")
        continue
    texts = {e.get("text") for e in entries
             if isinstance(e, dict) and (e.get("text") or "").strip()}
    if not texts:
        continue
    best, frac = None, 0.0
    for i, have in doc_texts.items():
        f = len(texts & have) / len(texts)
        if f > frac:
            best, frac = i, f
    if best is not None and frac >= 0.5:
        matched.append((wi, best, wd, entries, frac))

print(f"    scaffolds matched to a document at >=50% of their texts: "
      f"{len(matched)} of {len(with_hf)}")
if not matched:
    print("\n  VOID — no frozen scaffold could be matched to a corpus document, so arm 1")
    print("  compared nothing. A zero over an empty set is not a zero.")
    VOIDED.append("arm 1: no scaffold matched a document")

# =========================================================================================
# ARM 1 — APPLY, OLD vs NEW. The written header/footer XMLs must be BYTE-IDENTICAL.
# =========================================================================================
print("\n" + "-" * 96)
print("ARM 1 — apply over the frozen scaffolds: OLD vs NEW, byte comparison")
print("-" * 96)
print("  The frozen scaffolds carry NO graphic-metadata entry — every one predates the key —")
print("  so there is nothing for the new code to do and ANY movement is a defect.")
arm1_docs, arm1_moved = 0, []
for wi, di, wd, entries, frac in matched:
    src = docs[di - 1]
    kinds = sorted({e.get("kind", "paragraph") for e in entries if isinstance(e, dict)})
    filled = sum(1 for e in entries if isinstance(e, dict) and e.get("en")
                 and e["en"] != e.get("text"))
    work = TMP / f"w{wi}"
    outs = {}
    broke = None
    for arm, sdir in (("old", OLDTREE), ("new", ROOT / args.variant / "scripts")):
        adir = work / arm
        adir.mkdir(parents=True)
        shutil.copyfile(src, adir / "src.docx")
        shutil.copyfile(wd / "headers_footers.json", adir / "hf.json")
        rr = run_script(sdir, [adir / "src.docx", adir / "final",
                               "--apply", adir / "hf.json"])
        got = {}
        fin = adir / "final" / "word"
        if fin.is_dir():
            for f in sorted(fin.glob("*.xml")):
                got[part_kind(f"word/{f.name}") + ":" + str(len(got))] = f.read_bytes()
        if not got:
            broke = f"{arm} arm wrote nothing (rc={rr.returncode})"
        outs[arm] = got
    if broke:
        print(f"    doc {di:2d} (scaffold {wi:2d}): VOID — {broke}")
        VOIDED.append(f"doc {di}: {broke}")
        continue
    arm1_docs += 1
    same = outs["old"] == outs["new"]
    moved = 0 if same else sum(1 for k in outs["new"]
                               if outs["old"].get(k) != outs["new"].get(k))
    if not same:
        arm1_moved.append((di, moved))
    print(f"    doc {di:2d} (scaffold {wi:2d}, match {frac:.0%}): "
          f"{len(outs['new'])} part(s) written, entry kinds {kinds}, "
          f"{filled} filled — {'IDENTICAL' if same else f'{moved} PART(S) MOVED'}")
print(f"\n  documents compared: {arm1_docs} of {len(matched)} matched")
if arm1_moved:
    print("  DEFECT — the new code changed a written part where nothing should have moved:")
    for di, n in arm1_moved:
        print(f"    doc {di}: {n} part(s)")
    FAIL.append(f"arm 1: {len(arm1_moved)} document(s) moved")
elif arm1_docs:
    print("  no movement, over a real population, with the baseline genuinely different —")
    print("  which is what a kind-less entry still being a paragraph entry looks like.")

# =========================================================================================
# ARM 2 — EXTRACT over the corpus. How many graphic surfaces does the NEW code offer?
# =========================================================================================
print("\n" + "-" * 96)
print("ARM 2 — the new --extract over every corpus document: how many graphic surfaces?")
print("-" * 96)
total_graphic, per_doc, arm2_docs = 0, [], 0
for di, src in enumerate(docs, 1):
    adir = TMP / f"x{di}"
    adir.mkdir(parents=True)
    shutil.copyfile(src, adir / "src.docx")
    rr = run_script(ROOT / args.variant / "scripts",
                    [adir / "src.docx", "--extract", adir / "hf.json"])
    if not (adir / "hf.json").is_file():
        # A document with no header or footer at all exits non-zero by design.
        note = (rr.stdout + rr.stderr).strip().splitlines()[-1:] or [""]
        print(f"    doc {di:2d}: no scaffold written — {note[0][:70]}")
        continue
    arm2_docs += 1
    es = json.loads((adir / "hf.json").read_text(encoding="utf-8"))
    g = [e for e in es if e.get("kind") == "graphic_metadata"]
    total_graphic += len(g)
    per_doc.append((di, len(es), len(g)))
for di, n, g in per_doc:
    print(f"    doc {di:2d}: {n:3d} scaffold entr(ies), {g} graphic-metadata surface(s)")
print(f"\n  documents extracted: {arm2_docs} of {len(docs)}")
print(f"  graphic-metadata surfaces offered across the whole corpus: {total_graphic}")
if total_graphic == 0:
    print("  EXPECTED, and it is the DECLARATION rather than a disappointment: the corpus")
    print("  holds 14 graphics across 3 documents and not one attribute of prose on any of")
    print("  them. A19's evidence is the synthetic fixture, and this arm is what entitles")
    print("  anyone to say so. Arm 3 proves the zero is a real zero.")

# =========================================================================================
# ARM 3 — THE POSITIVE CONTROL. Plant a @descr in a COPY and prove the same path offers it.
# =========================================================================================
print("\n" + "-" * 96)
print("ARM 3 — positive control: a planted @descr must be offered by the same code path")
print("-" * 96)
control_fired = False
carrier = None
for di, src in enumerate(docs, 1):
    with zipfile.ZipFile(src) as zf:
        hdrs = [n for n in zf.namelist() if part_kind(n) in ("header", "footer")
                and n.endswith(".xml")]
        if any(b"<w:drawing" in zf.read(n) or b"<w:pict" in zf.read(n) for n in hdrs):
            carrier = (di, src)
            break
if carrier is None:
    print("    VOID — no corpus document has a graphic in a header or footer, so no")
    print("    control could be planted. Arm 2's zero is therefore UNPROVEN.")
    VOIDED.append("arm 3: no carrier document for the control")
else:
    di, src = carrier
    cdir = TMP / "control"
    cdir.mkdir(parents=True)
    victim = cdir / "src.docx"
    # THE CORPUS IS A BASELINE. Hash it before and after and ASSERT, rather than reasoning
    # that nothing here opens it for writing -- that reasoning is what "it cannot have
    # happened" always looks like just before it has.
    import hashlib
    before_sha = hashlib.sha256(src.read_bytes()).hexdigest()
    # REBUILD THE ZIP RATHER THAN EDIT IN PLACE, and only in the temp copy. The corpus is a
    # baseline; nothing here may reach it.
    with zipfile.ZipFile(src) as zin, zipfile.ZipFile(victim, "w",
                                                      zipfile.ZIP_DEFLATED) as zout:
        planted = 0
        for item in zin.infolist():
            data = zin.read(item.filename)
            if part_kind(item.filename) in ("header", "footer") and not planted:
                if b"<wp:docPr " in data:
                    data = data.replace(
                        b"<wp:docPr ",
                        b'<wp:docPr descr="' + PLANTED.encode() + b'" ', 1)
                    planted = 1
                elif b"<v:shape " in data:
                    data = data.replace(
                        b"<v:shape ", b'<v:shape alt="' + PLANTED.encode() + b'" ', 1)
                    planted = 1
            zout.writestr(item, data)
    if not planted:
        print(f"    VOID — could not plant a control in doc {di}: no wp:docPr or v:shape")
        print("    element in a header or footer part. Arm 2's zero is UNPROVEN.")
        VOIDED.append("arm 3: control could not be planted")
    else:
        rr = run_script(ROOT / args.variant / "scripts",
                        [victim, "--extract", cdir / "hf.json"])
        if (cdir / "hf.json").is_file():
            es = json.loads((cdir / "hf.json").read_text(encoding="utf-8"))
            hits = [e for e in es if e.get("text") == PLANTED]
            control_fired = len(hits) == 1
            print(f"    control planted in doc {di}'s header/footer and re-extracted: "
                  f"{'FIRED' if control_fired else 'DID NOT FIRE'}")
            if control_fired:
                print(f"    surface reported: {hits[0].get('surface')}")
        else:
            print(f"    VOID — --extract wrote nothing on the planted copy "
                  f"(rc={rr.returncode})")
        if not control_fired:
            VOIDED.append("arm 3: the positive control did not fire")
    after_sha = hashlib.sha256(src.read_bytes()).hexdigest()
    untouched = after_sha == before_sha
    print(f"    the corpus document is byte-identical after the run: "
          f"{'yes' if untouched else 'NO — THE BASELINE WAS MODIFIED'}")
    if not untouched:
        FAIL.append("arm 3: the corpus document was modified — the baseline is compromised")

print("\n" + "=" * 96)
print(f"FAILED {len(FAIL)}   VOID {len(VOIDED)}")
print("=" * 96)
for f in FAIL:
    print(f"  FAIL  {f}")
for v in VOIDED:
    print(f"  VOID  {v}")
print()
print("WHAT THIS TOOL DOES AND DOES NOT SETTLE, so a green run is not read as more than it is:")
print("  IT SETTLES that the new scaffold shape did not break header/footer translation on")
print("  real documents — the frozen scaffolds have no `kind` key and must go on working.")
print("  IT DOES NOT SETTLE A19's own fix. The corpus has no translatable graphic metadata")
print("  at all, so there is nothing for the fix to move; arm 2 measures that and arm 3")
print("  proves the measurement is a real zero. A19's acceptance is")
print("  tests/test_graphic_metadata.py.")
if not args.keep:
    shutil.rmtree(TMP, ignore_errors=True)
else:
    print(f"\nworkdir kept: {TMP}")
sys.exit(1 if (FAIL or VOIDED) else 0)
