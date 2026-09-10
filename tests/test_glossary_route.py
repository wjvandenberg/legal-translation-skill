# -*- coding: utf-8 -*-
"""BRANCH 7 SLICE 2 — C19: the glossary part's route IN and route OUT.

WHAT THE ROW SAYS AND WHAT WAS MEASURED. C19 says `word/glossary/document.xml` is an aux
surface the skill does not list and `repack_docx.py` cannot carry, so a translated glossary
has no route into the deliverable; on D03 an operator substituted it by hand, and on the batch
arm D03B it shipped BYTE-IDENTICAL AND UNTRANSLATED with neither the log nor the narrative
mentioning it once. Proved end to end 2026-09-08 (temp/probe_glossary_c19.py).

THREE THINGS THE EXPLORE FOUND THAT THE RECORD DID NOT HAVE, all in temp/probe_*.py:

  1  THE GAP IS ON BOTH SIDES. The row frames it as repack's. Extraction never reads the part
     either -- it captured 2 paragraphs of a 3-paragraph fixture, the third being the
     glossary's. So this suite tests a route IN as well as a route OUT.

  2  THE REFERENCE ELEMENT IS NOT THE ONE THE ROW NAMES. Measured on the one corpus carrier:
     docPartObj 0, docPartGallery 0; `docPart` 10, `placeholder` 20, `w:sdt` 10, and 10 of 10
     glossary docPart names appearing verbatim in document.xml. The mechanism is
     <w:placeholder><w:docPart w:val="..."/></w:placeholder> -- the greyed-out prompt text
     Word shows while a control is EMPTY. See make_fixtures.py's glossary section.

  3  REPACK'S FOUR EXISTING AUX CHECKS WARN; THEY DO NOT REFUSE. Measured with both positive
     controls firing (temp/probe_repack_refusal_shape.py): numbering and comments each bundled
     at rc=0 with a WARNING. Only --paragraphs and an empty --headers-footers-dir refuse. So
     Wouter's decision of 2026-09-08 -- "the --glossary flag PLUS repack's own refusal
     pattern" -- was taken on a false premise, was RE-PUT to him on 2026-09-09 with the
     measurement, and he confirmed REFUSE: the shape copied is the --paragraphs gate's.

WHY THE ASYMMETRY IS PRINCIPLED rather than an inconsistency to tidy away. The four warn-only
checks fire when a translated file sits in the operator's own WORKDIR: they did the work and
lost the flag, so another signal exists. This one fires on the ORIGINAL carrying the part --
nobody did any work, and on D03B nothing anywhere said so. A warning is what already failed.

THE ACCEPTANCE CONDITION IS NOT SLICE 1's. Slice 1 had to move a delivered byte, and
tools/apply_corpus_diff.py measured it. That tool drives APPLY, not repack, and this slice
changes repack plus an extraction REPORT -- so the corpus arm should report 13 byte-identical
and 0 unexplained, and THAT ALL-QUIET RESULT PROVES NOTHING WHATEVER ABOUT SLICE 2. The
acceptance is this file.

    uv run --with lxml python tests/test_glossary_route.py
    uv run --with lxml python tests/test_glossary_route.py --variant us
"""
import argparse
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.dont_write_bytecode = True
# Reaches grandchildren, which sys.dont_write_bytecode cannot: repack spawns validators as
# subprocesses, so a .pyc can land inside the shipped tree. Register I-18.
os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")

sys.path.insert(0, str(Path(__file__).resolve().parent))
from make_fixtures import (                                          # noqa: E402
    GLOSSARY_CT, GLOSSARY_DATE_PART, GLOSSARY_PARTY_PART, GLOSSARY_PROMPTS,
    GLOSSARY_RELS, GLOSSARY_SHAPES, _glossary_part, docx)

ROOT = Path(__file__).resolve().parent.parent
FIX = ROOT / "tests" / "fixtures" / "glossary.docx"
NOTES = ROOT / "tests" / "fixtures" / "glossary.notes.json"
GLOSSARY_ZIP_PATH = "word/glossary/document.xml"

ap = argparse.ArgumentParser()
ap.add_argument("--variant", default="uk", choices=("uk", "us"))
ap.add_argument("--keep", action="store_true", help="keep the temp workdir for inspection")
args = ap.parse_args()
SCRIPTS = ROOT / args.variant / "scripts"

FAIL, CHECKED, VOIDED = [], 0, []
TMP = Path(tempfile.mkdtemp(prefix="b7s2-glossary-"))
ENV = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1",
           PYTHONDONTWRITEBYTECODE="1")


def ok(label, cond, detail=""):
    global CHECKED
    CHECKED += 1
    print(("  OK   " if cond else "  XX   ") + label
          + (f"   {detail}" if detail and not cond else ""))
    if not cond:
        FAIL.append(f"{label} {detail}".strip())
    return cond


def void(label, why):
    """A check that could not establish anything is VOID, never a pass. CLAUDE.md 5.3."""
    VOIDED.append(f"{label}: {why}")
    print(f"  ??   {label}   VOID — {why}")


def run(argv, timeout=900):
    return subprocess.run(["uv", "run", "--with", "lxml", "python"] + [str(a) for a in argv],
                          capture_output=True, text=True, encoding="utf-8",
                          errors="replace", cwd=str(ROOT), env=ENV, timeout=timeout)


# =========================================================================================
# INPUTS. COPIED INTO A TEMP DIRECTORY, NEVER READ FROM tests/fixtures/.
#
# apply's final pre-apply pass is validate_translations.py, which writes .validate-state.json
# beside the NOTES file -- so pointing it at the fixtures directory puts run state into the
# git index. That happened once, on branch 6 slice 3, and it broke `git switch` and therefore
# `git bisect`, the one tool the whole test method exists to enable.
# =========================================================================================
def stage(name, docx_path, notes_path=None):
    """Copy a .docx (and its notes) into their own temp subdirectory. Returns (docx, notes)."""
    d = TMP / name
    (d / "final" / "word").mkdir(parents=True, exist_ok=True)
    src = d / "orig.docx"
    shutil.copy2(docx_path, src)
    nt = None
    if notes_path is not None:
        nt = d / "paragraphs.json"
        shutil.copy2(notes_path, nt)
    return src, nt


def apply_and_get_xml(name, src, notes):
    """Run the real apply; return the translated document.xml path, or None."""
    out = TMP / name / "final" / "word" / "document.xml"
    r = run([SCRIPTS / "apply_translations_textmatch.py", src, notes, out])
    if not out.exists():
        tail = (r.stderr or r.stdout or "").strip().splitlines()
        void(f"{name}: apply produced no document.xml",
             (tail[-1][:160] if tail else f"rc={r.returncode}"))
        return None
    return out


def repack(name, src, out_xml, notes, extra=(), out_name="out.docx"):
    """Run the real repack. Returns (returncode, combined output, artefact path or None).

    ASSERT THE ARTEFACT, NOT THE EXIT CODE -- so both are returned and both are read.
    """
    out = TMP / name / out_name
    r = run([SCRIPTS / "repack_docx.py", src, out_xml, out,
             "--paragraphs", notes] + list(extra))
    blob = (r.stdout or "") + (r.stderr or "")
    return r.returncode, blob, (out if out.exists() else None)


def members(path):
    with zipfile.ZipFile(path) as z:
        return {n: z.read(n) for n in z.namelist()}


print("=" * 96)
print(f"C19 — THE GLOSSARY ROUTE   variant={args.variant}")
print("=" * 96)
print(f"workdir {TMP}")

if not FIX.is_file() or not NOTES.is_file():
    print("\nVOID — the fixture is missing. Run: uv run python tests/make_fixtures.py")
    sys.exit(1)

# =========================================================================================
# ARM 0 — THE FIXTURE ITSELF, and the basename trap it exists to catch.
#
# NEVER LIST AUX PARTS BY BASENAME. REGISTER-findings.md's own instrument note records what
# this cost: "my first aux listing showed no glossary part and I wrote 'C19 did not recur';
# re-measuring on full paths found six word/glossary/ entries and the part untranslated."
# word/glossary/document.xml and word/document.xml collapse to the same basename, so an
# implementation keyed on basenames is silently blind to the part. This asserts the fixture
# can catch that, which is a property of the fixture and not of the fix.
# =========================================================================================
print("\n" + "-" * 96)
print("ARM 0 — the fixture carries the measured mechanism, and can catch the basename trap")
print("-" * 96)
fx = members(FIX)
ok("the fixture carries word/glossary/document.xml at its FULL path",
   GLOSSARY_ZIP_PATH in fx)
basenames = [n.rsplit("/", 1)[-1] for n in fx]
ok("basename 'document.xml' occurs more than once — a basename-keyed impl would be blind",
   basenames.count("document.xml") > 1, f"count={basenames.count('document.xml')}")
doc = fx["word/document.xml"].decode("utf-8")
gloss = fx[GLOSSARY_ZIP_PATH].decode("utf-8")
ok("document.xml uses the MEASURED reference element w:placeholder/w:docPart",
   "<w:placeholder>" in doc and "<w:docPart " in doc)
ok("document.xml does NOT use docPartObj/docPartGallery — the shape the row names and the "
   "corpus does not have",
   "docPartObj" not in doc and "docPartGallery" not in doc)
ok("every glossary docPart name appears verbatim in document.xml",
   all(nm in doc for nm in GLOSSARY_PROMPTS),
   f"missing={[nm for nm in GLOSSARY_PROMPTS if nm not in doc]}")
ok("the content-type override for the glossary part is present",
   "wordprocessingml.document.glossary+xml" in fx["[Content_Types].xml"].decode("utf-8"))
ok("the glossaryDocument relationship is present",
   "relationships/glossaryDocument" in
   fx["word/_rels/document.xml.rels"].decode("utf-8"))
ok("the glossary part carries translatable text",
   len([t for t in re.findall(r"<w:t(?:\s[^>]*)?>([^<]*)</w:t>", gloss) if t.strip()]) >= 2)

# =========================================================================================
# ARM 1 — THE ROUTE IN. Extraction must SAY the glossary has translatable content.
#
# This is the point at which an operator learns there is anything to translate at all, and
# its absence is why D03B shipped untranslated with nothing objecting. extract_paragraphs.py
# already has the mechanism: _summarise_aux_xml feeding an "AUX-FILE CONTENT SUMMARY (Step 2)"
# over footnotes, endnotes and comments, described in its own comment as "the primary
# mechanism that surfaces aux content for translation".
# =========================================================================================
print("\n" + "-" * 96)
print("ARM 1 — ROUTE IN: extraction reports the glossary's translatable entries")
print("-" * 96)
ex_src, _ = stage("extract", FIX)
ex_json = TMP / "extract" / "extracted.json"
r = run([SCRIPTS / "extract_paragraphs.py", ex_src, ex_json])
ex_blob = (r.stdout or "") + (r.stderr or "")
if not ex_json.exists():
    void("extraction produced no JSON", f"rc={r.returncode}")
else:
    ed = json.loads(ex_json.read_text(encoding="utf-8"))
    eps = ed["paragraphs"] if isinstance(ed, dict) else ed
    ok("extraction still captures every body paragraph (no regression)",
       len(eps) == len(GLOSSARY_SHAPES), f"got {len(eps)}, want {len(GLOSSARY_SHAPES)}")
    ok("the aux summary NAMES the glossary part by its full path",
       GLOSSARY_ZIP_PATH in ex_blob)
    ok("the aux summary reports BOTH of the glossary's translatable entries",
       all(v in ex_blob for v in GLOSSARY_PROMPTS.values()),
       "the operator is told what to translate, not merely that a part exists")

# =========================================================================================
# ARM 2 — THE REFUSAL. An original carrying a TEXT-BEARING glossary and no --glossary.
# =========================================================================================
print("\n" + "-" * 96)
print("ARM 2 — THE REFUSAL: text-bearing glossary in the ORIGINAL, flag absent")
print("-" * 96)
src, notes = stage("refuse", FIX, NOTES)
xml = apply_and_get_xml("refuse", src, notes)
if xml is None:
    void("ARM 2", "apply produced nothing, so the refusal cannot be tested")
else:
    rc, blob, art = repack("refuse", src, xml, notes)
    ok("repack REFUSES (non-zero exit)", rc != 0, f"rc={rc}")
    ok("NOTHING was written to the delivery path", art is None,
       "assert the artefact, not the exit code")
    ok("the refusal NAMES the part it is about", GLOSSARY_ZIP_PATH in blob)
    ok("it is announced as an intentional gate, not a crash",
       "SKILL GATE FIRED" in blob)
    ok("it names the flag that satisfies it — a compliant way out must exist (5.9)",
       "--glossary" in blob)

# =========================================================================================
# ARM 3 — THE CONFORMING PAIR. A check that fires on everything is not a check.
#
# negative_inputs.py's own rule: "passes writes a CONFORMING input, so a check that fires on
# everything is caught too. A check that cannot tell good from bad is not a check, and only
# the pair shows it."
#
# (a) an EMPTY glossary part -- Word writes one for AutoText, and nothing in it can be
#     translated, so a gate firing here fires on input nobody can change. That is Wouter's
#     decision 2 of 2026-09-08 applied one part outward, and it is why the gate is
#     TEXT-BEARING rather than merely PRESENT.
# (b) NO glossary part at all -- every other document in the corpus.
#
# BOTH ARE GREEN TODAY and must STAY green. They are the arms that would catch an
# over-broad gate, so they are not evidence the fix works.
# =========================================================================================
print("\n" + "-" * 96)
print("ARM 3 — THE CONFORMING PAIR: an EMPTY glossary, and NO glossary. Must NOT refuse")
print("-" * 96)
body = "".join(s[3] for s in GLOSSARY_SHAPES)

empty_fx = TMP / "empty-gloss.docx"
docx(empty_fx, body,
     {GLOSSARY_ZIP_PATH: _glossary_part({}),        # structurally valid, no translatable text
      "word/_rels/document.xml.rels": GLOSSARY_RELS}, GLOSSARY_CT)
none_fx = TMP / "no-gloss.docx"
docx(none_fx, body)

for label, fixture in (("an EMPTY glossary part", empty_fx), ("NO glossary part", none_fx)):
    nm = "conform-" + ("empty" if "EMPTY" in label else "none")
    s, n = stage(nm, fixture, NOTES)
    x = apply_and_get_xml(nm, s, n)
    if x is None:
        void(f"ARM 3 ({label})", "apply produced nothing")
        continue
    rc, blob, art = repack(nm, s, x, n)
    ok(f"{label}: repack does NOT refuse", rc == 0, f"rc={rc}")
    ok(f"{label}: the deliverable exists", art is not None)

# =========================================================================================
# ARM 4 — THE ROUTE OUT. --glossary carries a translated part into the deliverable.
#
# The translated part is produced HERE BY THE STEP 8e TEMPLATE ITSELF -- pure regex over
# <w:t>, no ElementTree -- so the test exercises the route the step doc tells operators to
# use, rather than a route only the test knows about.
# =========================================================================================
print("\n" + "-" * 96)
print("ARM 4 — ROUTE OUT: --glossary carries the translated part, byte-exactly")
print("-" * 96)
GLOSS_EN = {GLOSSARY_PROMPTS[GLOSSARY_DATE_PART]: "Enter the date",
            GLOSSARY_PROMPTS[GLOSSARY_PARTY_PART]: "Name of the party"}
_WT = re.compile(r"(<w:t(?:\s[^>]*)?>)([^<]*)(</w:t>)")
translated = _WT.sub(lambda m: m.group(1) + GLOSS_EN.get(m.group(2), m.group(2)) + m.group(3),
                     gloss)
ok("the Step 8e template actually changed the glossary's text",
   translated != gloss and all(v in translated for v in GLOSS_EN.values()))

src4, notes4 = stage("carry", FIX, NOTES)
gpath = TMP / "carry" / "final" / "word" / "glossary-document.xml"
gpath.write_bytes(translated.encode("utf-8"))
xml4 = apply_and_get_xml("carry", src4, notes4)
if xml4 is None:
    void("ARM 4", "apply produced nothing")
else:
    rc, blob, art = repack("carry", src4, xml4, notes4, extra=["--glossary", gpath])
    if not ok("repack succeeds when the flag is passed", rc == 0, f"rc={rc}") or art is None:
        ok("the deliverable exists", art is not None, "so nothing below can be checked")
    else:
        got = members(art)
        ok("the delivered glossary part IS the translated one, byte-for-byte",
           got.get(GLOSSARY_ZIP_PATH) == translated.encode("utf-8"))
        ok("no source-language prompt survives in the delivered glossary",
           not any(v.encode("utf-8") in got.get(GLOSSARY_ZIP_PATH, b"")
                   for v in GLOSSARY_PROMPTS.values()))
        ok("the glossary's docPart NAMES are untouched — the body still resolves them",
           all(nm.encode("utf-8") in got.get(GLOSSARY_ZIP_PATH, b"")
               for nm in GLOSSARY_PROMPTS))
        ok("repack says which part it replaced", GLOSSARY_ZIP_PATH in blob)
        # EVERY OTHER MEMBER MUST BE UNTOUCHED. The one part named by the flag is the only
        # thing that may move; a fix that rewrote the package would pass the assertion above
        # and still be wrong.
        moved = sorted(n for n in set(fx) | set(got)
                       if n not in (GLOSSARY_ZIP_PATH, "word/document.xml",
                                    "word/settings.xml")
                       and fx.get(n) != got.get(n))
        ok("every other ZIP member is byte-identical to the original", not moved,
           f"moved={moved}")

# =========================================================================================
# ARM 5 — DETECTION. The post-repack remnant scan must READ the delivered glossary.
#
# This is the arm that would have caught D03B. It is reached by the second compliant route
# out: an operator who judges the part needs no translation passes the ORIGINAL part to
# --glossary, which is an explicit recorded decision rather than a silent default. The scan
# must then say the delivered package still holds source-language text in that part.
#
# repack's own filter is why it is blind today: _PROSE_PARTS holds four fixed paths plus
# headerN/footerN, and word/glossary/document.xml is in neither set. Note the basename trap
# sitting in that same function -- `base = os.path.basename(part_name)` is 'document.xml'.
# =========================================================================================
print("\n" + "-" * 96)
print("ARM 5 — DETECTION: the post-repack scan reads the DELIVERED glossary part")
print("-" * 96)
src5, notes5 = stage("scan", FIX, NOTES)
orig_gloss = TMP / "scan" / "final" / "word" / "glossary-original.xml"
orig_gloss.write_bytes(gloss.encode("utf-8"))          # deliberately NOT translated
xml5 = apply_and_get_xml("scan", src5, notes5)
if xml5 is None:
    void("ARM 5", "apply produced nothing")
else:
    rc, blob, art = repack("scan", src5, xml5, notes5, extra=["--glossary", orig_gloss])
    ok("repack accepts the declared no-translation-needed route", rc == 0, f"rc={rc}")
    scanned = "Post-repack remnant scan" in blob or "Post-repack scan" in blob
    if not scanned:
        # A SCAN THAT DID NOT RUN IS VOID, NEVER CLEAN. It is skipped silently when the
        # source language cannot be detected from the original, which is a property of the
        # fixture's prose and not of this slice.
        void("the post-repack scan", "it did not run at all — language undetected, so a "
                                     "quiet result here says nothing about _PROSE_PARTS")
    else:
        ok("the scan NAMES the delivered glossary part", GLOSSARY_ZIP_PATH in blob,
           "_PROSE_PARTS excludes it, so the part ships unread — this is D03B's arm")

# =========================================================================================
# ARM 6 — CROSS-TREE EQUALITY. `shared` has to mean something.
#
# The 2026-08-05 decision rules out a shared library, so the two trees each carry their own
# copy and the only thing that makes them one implementation is an assertion. Slice 1 stated
# its inventory in four files and asserted their equality for exactly this reason.
# =========================================================================================
print("\n" + "-" * 96)
print("ARM 6 — the two trees agree")
print("-" * 96)
for script in ("repack_docx.py", "extract_paragraphs.py"):
    a = (ROOT / "uk" / "scripts" / script).read_bytes()
    b = (ROOT / "us" / "scripts" / script).read_bytes()
    if a == b:
        ok(f"{script}: uk and us are byte-identical", True)
        continue
    # Not a defect in itself -- variant spelling legitimately diverges. What must hold is
    # that the GLOSSARY handling is the same in both.
    ga = [ln for ln in a.decode("utf-8").splitlines() if "glossary" in ln.lower()]
    gb = [ln for ln in b.decode("utf-8").splitlines() if "glossary" in ln.lower()]
    ok(f"{script}: the glossary lines are identical across trees", ga == gb,
       f"uk has {len(ga)}, us has {len(gb)}")
    ok(f"{script}: both trees mention the glossary at all", bool(ga) and bool(gb))

# =========================================================================================
# ARM 7 — THE STEP DOCS. A route nobody is told about is not a route.
# =========================================================================================
print("\n" + "-" * 96)
print("ARM 7 — the step documents name the part and the flag")
print("-" * 96)
for rel in ("skill-docs/08-aux-and-quality.md", "skill-docs/10-repack-and-validate.md"):
    for variant in ("uk", "us"):
        f = ROOT / variant / rel
        if not f.is_file():
            void(f"{variant}/{rel}", "file missing")
            continue
        txt = f.read_text(encoding="utf-8", errors="replace")
        ok(f"{variant}/{rel} names the glossary part", "glossary" in txt.lower())
        if "10-repack" in rel:
            ok(f"{variant}/{rel} documents the --glossary flag", "--glossary" in txt)

print("\n" + "=" * 96)
print(f"CHECKED {CHECKED}   FAILED {len(FAIL)}   VOID {len(VOIDED)}")
print("=" * 96)
for f in FAIL:
    print(f"  FAIL  {f}")
for v in VOIDED:
    print(f"  VOID  {v}")
if not args.keep:
    shutil.rmtree(TMP, ignore_errors=True)
else:
    print(f"\nworkdir kept: {TMP}")
print()
print("REMINDER, so a green run is not read as more than it is: tools/apply_corpus_diff.py")
print("drives APPLY and this slice changes REPACK, so its 13-byte-identical result is a")
print("REGRESSION check and proves nothing about C19. THIS FILE is the acceptance.")
sys.exit(1 if (FAIL or VOIDED) else 0)
