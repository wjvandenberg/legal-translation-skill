# -*- coding: utf-8 -*-
"""BRANCH 8 — C28, C12 and M1: does the reading-apart step capture everything?

WHAT THE ROWS SAY. C28: nothing compares the delivered text inventory against the ORIGINAL
document's, so a defect introduced at extraction passes every gate — every post-production
check baselines against paragraphs.json, WHICH THE RUN ITSELF WROTE AT STEP 2. C12: Step 2's
mandatory footnote/endnote/comment check is a `zipfile.namelist()` membership test against
the CONVERTED file, so it asks "does this file have footnotes?" when the question is "did
the source have footnotes the conversion dropped?". M1: the probes behind it counted aux
INVENTORY rather than aux CONTENT and overstated the loss by about an order of magnitude.

WHAT THE CORPUS ALREADY PROVES, MEASURED BEFORE THIS SUITE WAS WRITTEN (temp/probe_b8_*.py).
Over every reachable frozen intermediate the BODY arm reports ZERO uncaptured paragraphs —
which is what PLAN-2-step-b.md section 4 predicted and is the calibration, not the test. The
AUX arm reports 40 paragraphs across 6 documents that no capture accounts for, including
`word/footnotes.xml` on two documents where no footnote capture exists in any form.

SO THE FAILING INPUTS HAD TO BE BUILT, and one of them is the reason this file exists at all.

THE READER CONTRACT IS THE DEFECT THIS SUITE PINS, and it was found by running rather than
reading. extract_paragraphs.py walks a paragraph in document order emitting a newline at
every PLAIN <w:br/> and nothing at a PAGE break. That contract is stated in a comment and
was asserted by NOTHING: no fixture in tests/fixtures/ contained a `<w:br/>` before this
branch. The first version of the completeness check collected w:t elements and nothing else,
and reported FOUR paragraphs lost on real corpus documents that were not lost at all — it
had reproduced its own reader as a finding. A check that cries wolf on correct work is the
gate this project measured firing six times out of six on nothing.

The check therefore reads the original INDEPENDENTLY — importing extract_paragraphs' reader
would share extract_paragraphs' blind spots, which is C28's whole complaint — while
honouring the SAME contract. Arm 2 below is what asserts the two agree, and it does it the
only way that cannot be faked: the conforming notes are produced by running the REAL
extractor, so any disagreement fails arm 1.

WHAT THIS SUITE CANNOT DO, said plainly. It cannot reach across the .doc -> .docx conversion,
because no script in this skill can read a legacy .doc. C12's and M1's conversion half stays
open; what closes here is the aux comparison BY CONTENT and the declaration that the answer
speaks only for the file it was given. tools/apply_corpus_diff.py cannot see this branch at
all — it drives apply, and nothing here changes apply or any delivered byte, so its
byte-identical result is a regression check and proves nothing about this work.

    uv run --with lxml python tests/test_extraction_completeness.py
    uv run --with lxml python tests/test_extraction_completeness.py --variant us
"""
import argparse
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.dont_write_bytecode = True
os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")

ROOT = Path(__file__).resolve().parent.parent
FIX = ROOT / "tests" / "fixtures" / "extraction-completeness.docx"
EMPTY = ROOT / "tests" / "fixtures" / "empty.docx"
NOTZIP = ROOT / "tests" / "fixtures" / "not-a-zip.docx"

ap = argparse.ArgumentParser()
ap.add_argument("--variant", default="uk", choices=("uk", "us"))
ap.add_argument("--keep", action="store_true")
args = ap.parse_args()
SCRIPTS = ROOT / args.variant / "scripts"

FAIL, CHECKED, VOIDED = [], 0, []
TMP = Path(tempfile.mkdtemp(prefix="b8-completeness-"))
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
    return subprocess.run(["uv", "run", "--with", "lxml", "python"]
                          + [str(a) for a in argv],
                          capture_output=True, text=True, encoding="utf-8",
                          errors="replace", cwd=str(ROOT), env=ENV, timeout=timeout)


def check(workdir, original, strict=False):
    """Run the mode under test. Returns (returncode, stdout+stderr)."""
    argv = [SCRIPTS / "validate_apply.py", workdir / "paragraphs.json",
            "--extraction-completeness", original]
    if strict:
        argv.append("--strict")
    r = run(argv)
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def stage(name):
    """A fresh workdir with its own copy of the fixture and freshly extracted notes.

    NEVER POINTS A SCRIPT AT tests/fixtures/. The pre-apply pass writes run state beside the
    notes file; that reached the git index once and broke `git switch`, and therefore
    `git bisect`, which is the one tool this whole test method exists to enable.
    """
    d = TMP / name
    d.mkdir(parents=True, exist_ok=True)
    src = d / "orig.docx"
    shutil.copy2(FIX, src)
    r = run([SCRIPTS / "extract_paragraphs.py", src, d / "paragraphs.json"])
    if not (d / "paragraphs.json").is_file():
        return None, None, r
    return d, src, r


def notes_of(d):
    return json.loads((d / "paragraphs.json").read_text(encoding="utf-8"))


def write_notes(d, notes):
    (d / "paragraphs.json").write_text(
        json.dumps(notes, ensure_ascii=False, indent=1), encoding="utf-8")


def body_not_captured(out):
    """The figure the check prints, read back rather than inferred from the exit code."""
    for line in out.splitlines():
        if "NOT captured" in line and ":" in line:
            try:
                return int(line.rsplit(":", 1)[1].strip())
            except ValueError:
                return None
    return None


print("=" * 92)
print(f"BRANCH 8 — EXTRACTION COMPLETENESS   ({args.variant})")
print("=" * 92)

# =========================================================================================
# ARM 1 — THE CONFORMING PAIR. Every failing arm below is meaningless without it: a check
# that reports a loss on everything reports nothing.
# =========================================================================================
print("\nARM 1 — the conforming pair: the REAL extractor's own output must satisfy the check")
base, base_src, extract_run = stage("conforming")
if base is None:
    void("arm 1", f"extract_paragraphs did not produce notes (rc={extract_run.returncode})")
else:
    rc, out = check(base, base_src)
    ok("conforming pair exits 0", rc == 0, f"rc={rc}")
    ok("body reports 0 uncaptured", body_not_captured(out) == 0,
       f"got {body_not_captured(out)}")
    ok("it names what it read", "capture files read" in out
       and "paragraphs.json" in out)
    ok("it states the conversion limit it cannot measure",
       "output of a .doc conversion" in out)

# =========================================================================================
# ARM 2 — THE READER CONTRACT. THE DEFECT THIS BRANCH FOUND, AND THE ONLY ARM WHOSE FIXTURE
# SHAPE DID NOT EXIST ANYWHERE IN THIS DIRECTORY BEFORE IT.
# =========================================================================================
print("\nARM 2 — the w:br contract: a PLAIN break is a newline, a PAGE break is not")
if base is None:
    void("arm 2", "no conforming notes")
else:
    notes = notes_of(base)
    with_nl = [n for n in notes if "\n" in (n.get("text") or "")]
    ok("the real extractor emitted a newline for the plain w:br", len(with_nl) == 1,
       f"{len(with_nl)} paragraph(s) carry a newline; the fixture has exactly one plain break")
    page_para = [n for n in notes
                 if "End of part one." in (n.get("text") or "")]
    ok("a PAGE break emits no newline — the negative control",
       len(page_para) == 1 and "\n" not in (page_para[0].get("text") or ""),
       f"page-break paragraph: {[repr(x.get('text')) for x in page_para]}")

    # THE RED. Strip the newline from the captured text, exactly as a w:t-only reader would
    # have produced it, and the check must refuse. Without this arm the contract is a
    # comment; with it, a future reader that drops the newline fails here instead of
    # reporting four real documents as damaged.
    d2 = TMP / "reader-contract"
    shutil.copytree(base, d2)
    broken = notes_of(d2)
    hits = 0
    for n in broken:
        if "\n" in (n.get("text") or ""):
            n["text"] = n["text"].replace("\n", "")
            hits += 1
    write_notes(d2, broken)
    if hits != 1:
        void("arm 2 RED", f"expected exactly 1 newline-bearing entry to mutate, got {hits}")
    else:
        rc, out = check(d2, base_src)
        ok("a w:t-only capture of that paragraph FAILS", rc == 1, f"rc={rc}")
        ok("and exactly one body paragraph is named", body_not_captured(out) == 1,
           f"got {body_not_captured(out)}")

# =========================================================================================
# ARM 3 — BODY LOSS. C28's core: a paragraph the capture simply does not have.
# =========================================================================================
print("\nARM 3 — a body paragraph missing from the capture must FAIL")
if base is None:
    void("arm 3", "no conforming notes")
else:
    d3 = TMP / "body-loss"
    shutil.copytree(base, d3)
    notes = notes_of(d3)
    keep = [n for n in notes if (n.get("text") or "").strip()]
    dropped = keep[len(keep) // 2]
    write_notes(d3, [n for n in notes if n is not dropped])
    rc, out = check(d3, base_src)
    ok("a deleted capture entry FAILS", rc == 1, f"rc={rc}")
    ok("exactly one body paragraph is reported", body_not_captured(out) == 1,
       f"got {body_not_captured(out)}")
    ok("the report names a paragraph INDEX and never its text",
       "paragraph index" in out and (dropped.get("text") or "")[:20] not in out)

# =========================================================================================
# ARM 4 — THE MULTI-w:t TRUNCATION CLASS, which register C28 names from the skill's own
# documentation: reading only the first w:t of a run "affected 45 paragraphs and 1,547
# characters — including payment milestone clauses and finance-party consent provisions".
# =========================================================================================
print("\nARM 4 — a paragraph captured only as far as its first w:t must FAIL")
if base is None:
    void("arm 4", "no conforming notes")
else:
    d4 = TMP / "truncated-capture"
    shutil.copytree(base, d4)
    notes = notes_of(d4)
    target = [n for n in notes if "Clause 4.2" in (n.get("text") or "")]
    if len(target) != 1:
        void("arm 4", f"expected exactly one two-w:t paragraph, found {len(target)}")
    else:
        full = target[0]["text"]
        target[0]["text"] = "Clause 4.2"
        ok("the fixture's two-w:t run really does hold more than its first w:t",
           len(full) > len("Clause 4.2"), f"full={len(full)} chars")
        write_notes(d4, notes)
        rc, out = check(d4, base_src)
        ok("a capture truncated at the first w:t FAILS", rc == 1, f"rc={rc}")
        ok("exactly one body paragraph is reported", body_not_captured(out) == 1,
           f"got {body_not_captured(out)}")

# =========================================================================================
# ARM 5 — AUXILIARY PARTS BY CONTENT. C12. And the STEP matters: at Step 2 the auxiliary
# translators have not run, so an uncaptured aux part is work to do and not yet a defect.
# Building a blocking default here would repeat the false refusal this project measured
# firing on three of nine real documents.
# =========================================================================================
print("\nARM 5 — auxiliary text with no capture is REPORTED at Step 2, not refused")
if base is None:
    void("arm 5", "no conforming notes")
else:
    rc, out = check(base, base_src)
    ok("the footnote part is named", "word/footnotes.xml" in out)
    ok("the header part is named", "word/header1.xml" in out)
    ok("both are reported unaccounted", out.count("NOT ACCOUNTED FOR") == 2,
       f"count={out.count('NOT ACCOUNTED FOR')}")
    ok("it is a work list, not a verdict, at Step 2", rc == 0, f"rc={rc}")
    ok("and it says which it is", "WORK LIST, not a verdict" in out)

    print("\nARM 5b — --strict turns the same report into a verdict, for pre-repack")
    rc, out = check(base, base_src, strict=True)
    ok("--strict FAILS while auxiliary text is uncaptured", rc == 1, f"rc={rc}")

# =========================================================================================
# ARM 6 — A CAPTURE UNDER A NAME NOBODY PREDICTED IS STILL A CAPTURE. The parts and the
# captures are both DISCOVERED, never listed: a check that demanded 'footnotes.json' would
# report a loss wherever the operator chose another name, and 0 of the 13 frozen corpus runs
# produced a file by that name.
# =========================================================================================
print("\nARM 6 — captures are discovered by glob, so an unpredicted filename still counts")
if base is None:
    void("arm 6", "no conforming notes")
else:
    d6 = TMP / "odd-capture-name"
    shutil.copytree(base, d6)
    (d6 / "whatever-the-operator-called-it.json").write_text(
        json.dumps({"notes": [{"src": "Subject to the qualification in the recitals."}]},
                   ensure_ascii=False), encoding="utf-8")
    rc, out = check(d6, base_src)
    ok("the footnote is now accounted for", out.count("NOT ACCOUNTED FOR") == 1,
       f"count={out.count('NOT ACCOUNTED FOR')}")
    ok("the header still is not — the arm can still fail", "word/header1.xml" in out)

    print("\nARM 6b — with every aux part captured, --strict passes")
    (d6 / "another-one.json").write_text(
        json.dumps(["Draft for discussion purposes only"], ensure_ascii=False),
        encoding="utf-8")
    rc, out = check(d6, base_src, strict=True)
    ok("--strict exits 0 once nothing is unaccounted for", rc == 0, f"rc={rc}")
    ok("and it says so", "AUXILIARY COMPLETE" in out)

# =========================================================================================
# ARM 7 — THE DENOMINATOR. A capture file that will not parse must be REPORTED, never
# silently skipped: a scan whose denominator can shrink in silence is not a scan.
# =========================================================================================
print("\nARM 7 — an unreadable capture is reported, not skipped")
if base is None:
    void("arm 7", "no conforming notes")
else:
    d7 = TMP / "bad-capture"
    shutil.copytree(base, d7)
    (d7 / "corrupt.json").write_text("{not json at all", encoding="utf-8")
    rc, out = check(d7, base_src)
    ok("the unparseable capture is named in the output",
       "would NOT parse" in out and "corrupt.json" in out)
    ok("and the result is marked provisional", "provisional" in out)

# =========================================================================================
# ARM 8 — THE DEGENERATE INPUTS. VOID is not clean, and a broken container is not empty.
# =========================================================================================
print("\nARM 8 — degenerate inputs: VOID and IO error are distinct from a pass")
if base is None:
    void("arm 8", "no conforming notes")
else:
    d8 = TMP / "degenerate"
    shutil.copytree(base, d8)
    rc, out = check(d8, EMPTY)
    ok("a document with no paragraph text exits 3 (VOID), not 0", rc == 3, f"rc={rc}")
    ok("and says nothing was compared", "VOID" in out)
    rc, out = check(d8, NOTZIP)
    ok("a file that is not a ZIP exits 2 (IO error), not 0", rc == 2, f"rc={rc}")

# =========================================================================================
# ARM 9 — THE TWO TREES CARRY THE SAME CHECK. A fix that lands in one variant and is
# forgotten in the other has shipped to a client before.
# =========================================================================================
print("\nARM 9 — the mode exists in BOTH trees and its code is byte-identical")
uk_src = (ROOT / "uk" / "scripts" / "validate_apply.py").read_text(encoding="utf-8")
us_src = (ROOT / "us" / "scripts" / "validate_apply.py").read_text(encoding="utf-8")
marker = "def check_extraction_completeness("
ok("uk carries the mode", marker in uk_src)
ok("us carries the mode", marker in us_src)
if marker in uk_src and marker in us_src:
    uk_block = uk_src[uk_src.index("# EXTRACTION COMPLETENESS"):uk_src.index("def main():")]
    us_block = us_src[us_src.index("# EXTRACTION COMPLETENESS"):us_src.index("def main():")]
    ok("the two copies are byte-identical", uk_block == us_block,
       f"uk={len(uk_block)} us={len(us_block)}")

print("\n" + "=" * 92)
print(f"  {CHECKED} check(s), {len(FAIL)} failure(s), {len(VOIDED)} void")
for f in FAIL:
    print(f"    FAIL  {f}")
for v in VOIDED:
    print(f"    VOID  {v}")
if not args.keep:
    shutil.rmtree(TMP, ignore_errors=True)
else:
    print(f"  workdir kept: {TMP}")
print("=" * 92)
sys.exit(1 if (FAIL or VOIDED) else 0)
