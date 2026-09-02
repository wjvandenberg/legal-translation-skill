# -*- coding: utf-8 -*-
"""BRANCH 6, FOURTH SLICE — C17 · C16 · F16, the three arms, each with its negative.

THE THREE ROWS HAVE ONE THING IN COMMON AND IT IS NOT WHITESPACE: in every one, apply reaches
a boundary it cannot describe and resolves the ambiguity SILENTLY, in the direction that
destroys something.

  C17  a segment whose declared `en` is one SPACE strips to `""`, is falsy, and lands in the
       branch commented "Explicit empty-string request". It was not a request; it was a space.
       Step 4 rule 9 tells the operator to mirror source whitespace, so the manual instructs
       them to create precisely this input.
  C16  `distribute_text_across_elements` restores the source's ENTIRE boundary-whitespace run
       over whatever the operator authored, so a source run carrying two spaces re-appears as
       two spaces in the English and NO edit to `en` can remove it -- which is what the row
       means by "there is no input-side fix".
  F16  Step 4c tells the operator to shorten `en` and says nothing about `en_runs`, so every
       authored offset shifts. Python's slicing then CLAMPS instead of complaining, and the
       emphasis lands on the wrong words.

WHY EVERY ARM HERE IS SYNTHETIC, STATED ONCE FOR THREE DIFFERENT REASONS. C17 fires three
times in the real corpus, but in all three the whitespace-only segment is the LAST segment of
its paragraph, so nothing follows it to be glued to and the damage is a lost trailing space
that no page can show; the visible mid-paragraph shape is D08's, and D08 does not carry it.
C16 has one recorded instance and its delivered side needs the corpus tool, not this file.
F16 CANNOT appear in the corpus at all -- the frozen intermediates are the post-compliance
artefact and `validate_en_runs.py` is a pre-apply gate, so a run with out-of-range offsets
could never have produced one. Three routes, one remedy, and CLAUDE.md 5.7's rule throughout:
a figure measured on one document is a figure about one document.

OWNERSHIP, SO NEITHER INSTRUMENT DUPLICATES THE OTHER. This file owns the SHAPES.
`tools/apply_corpus_diff.py` owns the real corpus, and its text arm is where C17's three
instances and C16's delivered-versus-declared count are asserted. Neither is the other's
substitute: a green run here says nothing about the corpus, and the corpus says nothing about
the glue.

EVERY EXPECTATION BELOW IS WRITTEN DOWN BEFORE THE RUN, so a surprise is visible rather than
rationalised afterwards. The first run of this file MUST FAIL on all three arms -- a new check
that passes immediately is not built correctly (CLAUDE.md 5.1).

OUTPUT POLICY: synthetic throughout. Every string is invented for this file and its fixtures.

    uv run --with lxml python tests/test_whitespace_and_offsets.py
"""
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tests"))
# IMPORTED BEFORE ANY STDOUT WRAPPING. `make_fixtures` rebinds sys.stdout to a fresh
# TextIOWrapper over sys.stdout.buffer at module level; installing a second wrapper over the
# same buffer means the first is collected and CLOSES it, so the script does its whole job and
# then dies on its closing print. Two runs were lost to that on the previous slice.
from make_fixtures import main as build_fixtures  # noqa: E402,F401
from lxml import etree  # noqa: E402

assert isinstance(sys.stdout, io.TextIOWrapper), "expected make_fixtures to wrap stdout"

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
SCRIPTS = ROOT / "uk" / "scripts"
FIXTURES = ROOT / "tests" / "fixtures"
FAIL = []
ENV = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1",
           PYTHONDONTWRITEBYTECODE="1")


def para_texts(xml_bytes):
    """Per paragraph, the concatenation of its `w:t` -- apply's own notion of paragraph text."""
    root = etree.fromstring(xml_bytes)
    return ["".join(t.text or "" for t in para.iter(f"{{{W}}}t"))
            for para in root.iter(f"{{{W}}}p")]


def bold_spans(xml_bytes, para_index):
    """(text, is_bold) per run in one paragraph, so EMPHASIS can be asserted as well as text.

    F16's damage is mis-slicing, not deletion: with clamped offsets the characters all still
    arrive and the BOLD lands on the wrong ones. A text-only assertion cannot see that at all.
    """
    root = etree.fromstring(xml_bytes)
    paras = list(root.iter(f"{{{W}}}p"))
    if para_index >= len(paras):
        return []
    out = []
    for run in paras[para_index].iter(f"{{{W}}}r"):
        txt = "".join(t.text or "" for t in run.iter(f"{{{W}}}t"))
        if not txt:
            continue
        b = run.find(f"{{{W}}}rPr/{{{W}}}b")
        # `<w:b w:val="0"/>` means bold OFF -- .claude/rules/ooxml.md. A naive presence test
        # reads the off-flag as bold, and apply emits one on every non-emphasised run.
        on = b is not None and (b.get(f"{{{W}}}val") or "true") not in ("0", "false", "off")
        out.append((txt, on))
    return out


def run_apply(src, notes, out, scripts=SCRIPTS):
    """Apply, with the inputs ALREADY copied somewhere disposable. Returns (bytes|None, proc).

    NEVER POINT THIS AT tests/fixtures/. Apply invokes `validate_translations.py` as its final
    pre-apply pass and that writes `<workdir>/.validate-state.json`, where workdir is wherever
    the NOTES file lives. On the previous slice that reached the git index: a dirty tree on
    what reads as a read-only check, `git switch` then refusing, `git bisect` broken, and one
    `git add -A` from committing run state to a public repository.
    """
    proc = subprocess.run(
        ["uv", "run", "--with", "lxml", "python",
         str(scripts / "apply_translations_textmatch.py"), str(src), str(notes), str(out)],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        cwd=str(ROOT), env=ENV, timeout=900)
    return (out.read_bytes() if out.is_file() else None), proc


def stage(stem, tmp, notes_override=None):
    """Copy a fixture and its notes into `tmp`, optionally rewriting the notes."""
    src, side = FIXTURES / f"{stem}.docx", FIXTURES / f"{stem}.notes.json"
    if not src.is_file() or not side.is_file():
        FAIL.append(f"{stem}: fixture or notes missing — run tests/make_fixtures.py")
        return None, None, None
    work = tmp / stem
    work.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, work / "source.docx")
    notes = json.loads(side.read_text(encoding="utf-8"))
    if notes_override is not None:
        notes = notes_override(notes)
    (work / "paragraphs.json").write_bytes(
        (json.dumps(notes, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    return work / "source.docx", work / "paragraphs.json", work / "out.xml"


def ok(label, passed, detail=""):
    print(("  OK   " if passed else "  XX   ") + label)
    if detail:
        print(f"       {detail}")
    if not passed:
        FAIL.append(label)


TMP = Path(tempfile.mkdtemp(prefix="b6-ws-"))
print("=" * 100)
print("BRANCH 6, SLICE 4 — C17 · C16 · F16")
print("=" * 100)

# =========================================================================================
# ARMS 1 AND 2 — C17 and C16, one document, four paragraphs that matter.
#
# THE PARAGRAPH INDICES ARE ASSERTED, NOT ASSUMED. A count of "four rows changed" is satisfied
# by changing the wrong four; reading a verdict off the wrong line prints OK or XX either way.
# =========================================================================================
# (paragraph index, what it must read AFTER the fix, why, what it reads TODAY)
WS_WANT = [
    (2, "The services end. the notice period applies.",
     "C17. A one-space `ins` segment mid-paragraph. `'.' + lower` is NOT one of "
     "fix_spacing's seven seam rules, so nothing downstream repairs this one — the glue "
     "reaches the page.",
     "The services end.the notice period applies."),
    (3, "The obligations of the providers. The Company shall pay the fee.",
     "C17, THE REGISTER'S OWN SHAPE — and the weaker of the two, which the fixture says "
     "rather than hides: `'.' + upper` IS a fix_spacing rule, so this seam would have been "
     "repaired downstream by accident. C15 records what that repair costs when it fires.",
     "The obligations of the providers.The Company shall pay the fee."),
    (5, "Clause 12 applies.",
     "THE NEGATIVE, and without it the fix is a disabled branch. `\"en\": \"\"` is the "
     "documented coalesce device — 04-translate.md Option B: `\"en\": \"\"` CLEARS, no `en` "
     "key PRESERVES. It must go on clearing, and this line must be IDENTICAL in both arms.",
     "Clause 12 applies."),
    (7, " The fee is payable within thirty days.",
     "C16. The source run's LEADING whitespace is a DOUBLE space and the operator authored "
     "none, so restoration generates a double space that is in neither the input nor "
     "anything the operator can edit. The leading edge is the only place it CAN be "
     "provoked — the guard tests a segment's own slice edge, never its neighbour's, so a "
     "mid-paragraph boundary either has an authored space already or is refused as glue by "
     "validate_segment_shapes. Restoring at most ONE character keeps the repair.",
     "  The fee is payable within thirty days."),
    (8, " The term is twelve months.",
     "THE C16 NEGATIVE, and the fix is a deletion without it. A source edge carrying ONE "
     "space must go on being restored — that is the rev42 repair apply's own comment at "
     ":436-457 documents — so this line must be IDENTICAL in both arms.",
     " The term is twelve months."),
]
WANT_WS_PARAS = 9

print("\nARMS 1 AND 2 — whitespace-arms.docx, through the real apply script")
print("-" * 100)
src, notes, out = stage("whitespace-arms", TMP)
if src is None:
    ok("whitespace-arms.docx staged", False)
else:
    xml, proc = run_apply(src, notes, out)
    if xml is None:
        ok("apply produced output for whitespace-arms.docx", False,
           (proc.stderr or proc.stdout or "")[-400:])
    else:
        got = para_texts(xml)
        # POSITIVE CONTROL ON THE FIXTURE ITSELF: if this is not the eight-paragraph document
        # the indices describe, every verdict below is read off the wrong line.
        ok(f"whitespace-arms.docx has {WANT_WS_PARAS} paragraphs "
           f"(got {len(got)}) — the indices below would otherwise read the wrong lines",
           len(got) == WANT_WS_PARAS)
        for idx, want, why, today in WS_WANT:
            actual = got[idx] if idx < len(got) else "<no such paragraph>"
            passed = actual == want
            print(("  OK   " if passed else "  XX   ")
                  + f"paragraph {idx}: {'as required' if passed else 'DOES NOT MATCH'}")
            print(f"       want  {want!r}")
            print(f"       got   {actual!r}")
            if not passed and actual == today:
                print("       ^ this is the DEFECT this arm was built to reproduce, exactly "
                      "as predicted in writing above.")
            print(f"       {why}")
            if not passed:
                FAIL.append(f"whitespace-arms paragraph {idx}: expected {want!r}, "
                            f"got {actual!r}")
            print()
        # AND THE SAME QUESTION ASKED AS A COUNT, because a count is what a reader checks.
        # It cannot drift from the strings above -- both are read off the same output -- but
        # it states the property rather than an example of it.
        if len(got) > 8:
            doubles = {i: t.count("  ") for i, t in enumerate(got) if "  " in t}
            ok("NO paragraph in the document contains a double space",
               not doubles,
               f"paragraphs carrying one: {doubles}" if doubles else "none anywhere")

# =========================================================================================
# ARM 3 — F16. THE GUARD MUST REFUSE, AND IT MUST NOT REFUSE EVERYTHING.
#
# Wouter's scope decision, 2026-09-02: the guard REFUSES an out-of-range offset rather than
# clamping. Clamping is explicitly not a valid repair — the register says it fixes the tail and
# not the interior, which is the bug that then blocked Step 6 (C13).
#
# NOT C13. That row's range assertion belongs to `validate_en_runs.py`, a PRE-APPLY gate over
# the definitions section only, with an `--allow-bold-loss` override — measured 2026-09-02:
# 144 lines, tests PRESENCE only, never reads `start` or `end`. It stays branch 11's. This
# guard is inside apply, covers every paragraph, and fires at the point of use.
# =========================================================================================
print("ARM 3 — en-runs-offsets.docx: the guard fires, and a conforming input stays quiet")
print("-" * 100)


def _conforming(notes):
    """The SAME fixture driven by the corrected spans the fixture itself ships.

    THE CONTROL WITHOUT WHICH THE ARM PROVES NOTHING. A guard that raises on every paragraph
    satisfies "it refused the bad input" perfectly. This is the same document, the same code
    path and the same four spans — only the offsets differ.

    THE FIRST VERSION OF THIS FUNCTION WAS WRONG AND THE RUN SAID SO. It pulled only the LAST
    span's `end` back to `len(en)` and left span 3 starting past the edit point, so the
    "conforming" control reproduced the very mis-slicing it was supposed to rule out — bold on
    `'8.1, as adjusted.'` in both arms. Corrected offsets are arithmetic, and the arithmetic
    belongs with the fixture that generates the broken ones, or the two are free to drift.
    """
    out = json.loads(json.dumps(notes))
    for n in out:
        if n.get("en_runs_conforming"):
            n["en_runs"] = n.pop("en_runs_conforming")
    return out


src, notes, out = stage("en-runs-offsets", TMP)
if src is None:
    ok("en-runs-offsets.docx staged", False)
else:
    declared = json.loads(notes.read_text(encoding="utf-8"))
    bad_ends = [(n.get("idx"), n["en_runs"][-1]["end"], len(n.get("en") or ""))
                for n in declared if n.get("en_runs")]
    # ASSERT THE FIXTURE IS ACTUALLY OUT OF RANGE, or the refusal below would be about
    # something else entirely and a quiet run would read as a passing guard.
    ok("the fixture's notes really are out of range "
       f"(last end vs len(en): {[(e, l) for _, e, l in bad_ends]})",
       bool(bad_ends) and all(e > l for _, e, l in bad_ends))

    xml, proc = run_apply(src, notes, out)
    msg = (proc.stderr or "") + (proc.stdout or "")
    refused = xml is None and proc.returncode != 0
    ok("apply REFUSES the out-of-range offset instead of clamping it",
       refused,
       f"rc={proc.returncode}, output written={xml is not None}")
    if refused:
        named = "en_runs" in msg and "1" in msg
        ok("the refusal NAMES the paragraph and the offending offset",
           named, "a refusal that does not say which paragraph sends the operator "
                  "through every entry by hand")
        # The gate idiom the rest of the tree uses, so an operator meets one message shape.
        ok("the refusal is a GATE message, not a bare traceback",
           "SKILL GATE FIRED" in msg or "BLOCK" in msg)
    else:
        # RED-FIRST EVIDENCE. Before the guard exists apply exits 0 and the emphasis lands on
        # the wrong words, which is the damage — recorded here so the first run of this file
        # documents the defect rather than merely failing.
        if xml is not None:
            spans = bold_spans(xml, 1)
            print(f"       apply exited {proc.returncode} and delivered the paragraph. Runs "
                  f"(text, bold):")
            for txt, b in spans:
                print(f"         bold={str(b):<5} {txt!r}")
            print("       ^ THE DAMAGE: every character arrives, so a text check sees "
                  "nothing wrong,\n         and the emphasis is on the wrong words. This is "
                  "F16 reproduced.")

    # THE CONTROL.
    work = TMP / "conforming"
    work.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(FIXTURES / "en-runs-offsets.docx", work / "source.docx")
    (work / "paragraphs.json").write_bytes(
        (json.dumps(_conforming(declared), ensure_ascii=False, indent=2) + "\n")
        .encode("utf-8"))
    xml2, proc2 = run_apply(work / "source.docx", work / "paragraphs.json", work / "out.xml")
    ok("the SAME document with in-range offsets applies cleanly — the guard is not "
       "refusing everything",
       xml2 is not None and proc2.returncode == 0,
       f"rc={proc2.returncode}, output written={xml2 is not None}"
       + ("" if xml2 is not None else
          f"\n       {(proc2.stderr or proc2.stdout or '')[-300:]}"))
    if xml2 is not None:
        spans = bold_spans(xml2, 1)
        emph = [txt for txt, b in spans if b]
        # WITH THE OFFSETS CORRECTED, the bold must sit on the defined term and the clause
        # reference — the two spans the operator authored as bold — and on nothing else.
        ok("with in-range offsets the emphasis lands where it was authored",
           emph == ['"Delivery Date"', "8.1"],
           f"bold runs: {emph!r}")

print()
print("=" * 100)
shutil.rmtree(TMP, ignore_errors=True)
if FAIL:
    print(f"  FAIL — {len(FAIL)} expectation(s) missed:")
    for f in FAIL:
        print(f"    · {f}")
    print()
    print("  An expectation written down before the run and then missed is the RESULT.")
    print("  Either the code's behaviour changed or the expectation was wrong. Decide which by")
    print("  reading the mechanism, and NEVER by editing the expectation to match the output.")
    print("=" * 100)
    sys.exit(1)
print("  PASS — a whitespace-only segment survives, an explicitly empty one still clears, a")
print("  restored boundary run no longer doubles a space, and an out-of-range offset is")
print("  refused rather than silently clamped onto the wrong characters.")
print("=" * 100)
sys.exit(0)
