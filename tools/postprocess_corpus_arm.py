# -*- coding: utf-8 -*-
"""BRANCH 9's CORPUS ARM — is the change journal COMPLETE on the real documents?

WHY THIS TOOL EXISTS RATHER THAN A RUN OF apply_corpus_diff.py, AND IT IS DECLARED HERE
BEFORE ANY RESULT IS READ. `tools/apply_corpus_diff.py` swaps `apply_translations_textmatch.py`
and drives APPLY. Branch 9 changes `post_process.py`, which that tool does not drive at all,
so its result says nothing whatever about this branch. Worse: at the current pin the apply
script is byte-identical to the working tree, so it prints its self-comparison notice and an
all-quiet run there is what a STALE pin also produces.

AND NOTHING IN THIS REPOSITORY RAN post_process OVER A REAL DOCUMENT BEFORE THIS FILE.
Measured: `post_process.py` is executed by `tests/probe-5b/preflight.py` and by one
reachability arm in `tests/test_instruction_rules.py`, and by nothing else; no suite
byte-compares its output. That is the same gap branch 7 found for the header/footer
translator, and the answer is the same — a corpus arm of its own.

WHAT IT ASSERTS, and the second one is the point of the branch:
  1. NOT ONE DELIVERED BYTE MOVES. Branch 9 is additive, so `document.xml` must come out
     byte-identical to the pinned baseline's. This is the OPPOSITE of branch 6's and 7's
     acceptance and it is stated that way on purpose.
  2. THE JOURNAL ACCOUNTS FOR EVERY TEXT CHANGE, read by a SECOND reader. This file
     reimplements the text contract from its statement and imports nothing from the script
     it measures — a reader shared between the two sides of a comparison cannot see what it
     normalised away, and the fix for that is a second reader, never a changed one.

THE INPUT IS NOT UNIFORM AND THE ARM SAYS SO PER DOCUMENT. Two frozen workdirs kept a
PRE-post_process snapshot; for those, running the stage reproduces the whole real change
set. The other eleven offer only the DELIVERED document.xml, and re-running a documented-
idempotent stage over its own output mostly records nothing. A document with no movement is
CALIBRATION — it says the instrument does not cry wolf — and it is counted separately from
a document that had something to account for, because folding the two together would let a
population of zeros read as a population of passes.

THE POSITIVE CONTROL IS NOT OPTIONAL. An arm that reports "accounted" everywhere has to be
shown capable of reporting something else. The last arm removes one entry from a journal and
requires the completeness comparison to name that document.

OUTPUT POLICY, the licence tools/apply_corpus_diff.py and tools/evidence_ls.py operate
under: workdir ORDINALS, counts, pass names and OOXML part names. Never a filename, never a
directory name below the logs root, never a paragraph, never any document text. NOTHING IS
EVER WRITTEN INTO THE LOGS FOLDER — every input is copied into a temporary directory first,
because a baseline the tool measuring it can modify is not a baseline.

    uv run --with lxml python tools/postprocess_corpus_arm.py
    uv run --with lxml python tools/postprocess_corpus_arm.py --variant us
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
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.dont_write_bytecode = True
os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")

from lxml import etree  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
LOGS = Path(os.environ.get("LT_LOGS_DIR", ROOT.parent / "legal-translation-logs"))

# PINNED TO A COMMIT, NEVER TO A BRANCH NAME OR HEAD. A before-and-after check in this
# project once read its "before" from HEAD, which worked only while the change was
# uncommitted and then compared the new file against itself and reported 100% carried.
#
# MOVED TO c803b56 ON 2026-09-22, the squash-merge of branch 9 (PR #93) and the LAST COMMIT
# THAT TOUCHED EITHER TREE — derived, not read off a merge message: `git log --oneline -1 --
# uk us` returns it. It moved as the FIRST act after that merge, never as a closing tidy-up.
# `git grep -F <old sha>` enumerates the carriers and is the only reading of "which pins
# move" that cannot go stale — it found FOUR moving ones at branch 9's close, where the
# session writing them had just said three.
#
# AND AT THIS PIN ARM 0 IS EXPECTED TO REPORT **VOID**, WHICH IS THE CORRECT ANSWER AND NOT
# A FAILURE. Branch 9 merged the very post_process.py this tool swaps, so the baseline is
# now byte-identical to the working tree and arm 1 would be comparing a file against itself.
# Arm 0 says so rather than letting arm 1 report a confident row of `identical` verdicts that
# mean nothing. THE NEXT BRANCH TO EDIT post_process.py — branch 10, the tidy-up split — is
# the one where this pin's reading starts moving again, and where a byte-identical result
# would mean the OPPOSITE of what it means today: branch 10 changes behaviour on every
# document, so its bytes MUST move.
REF = os.environ.get("LT_BASELINE_REF", "c803b56")
SCRIPT = "post_process.py"

# The two snapshot names seen in the frozen set. Named EXPLICITLY rather than globbed:
# CLAUDE.md 6.4 — any glob over an evidence folder must be explicit about what it expects.
PRE_SNAPSHOT_NAMES = (".pre-postprocess-document.xml", "doc_pre_postprocess.xml")

ap = argparse.ArgumentParser()
ap.add_argument("--variant", default="uk", choices=("uk", "us"))
ap.add_argument("--limit", type=int, default=0, help="examine at most N workdirs")
args = ap.parse_args()
SCRIPTS = ROOT / args.variant / "scripts"
ENV = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1",
           PYTHONDONTWRITEBYTECODE="1")

FAIL, VOIDED, CHECKED = [], [], 0
TMP = Path(tempfile.mkdtemp(prefix="b9-corpus-"))
TEXT_TAGS = (f"{{{W}}}t", f"{{{W}}}delText")
JOURNAL_NAME = "post_process_journal.json"


def ok(label, cond, detail=""):
    global CHECKED
    CHECKED += 1
    print(("  OK   " if cond else "  XX   ") + label
          + (f"   {detail}" if detail and not cond else ""))
    if not cond:
        FAIL.append(f"{label} {detail}".strip())
    return cond


def void(label, why):
    VOIDED.append(f"{label}: {why}")
    print(f"  ??   {label}   VOID — {why}")


# =========================================================================================
# THE SECOND READER. Implemented from the contract's statement, importing NOTHING from
# post_process.py. If this file ever grows such an import, delete it: an instrument that
# shares its subject's reader shares its subject's blind spots.
# =========================================================================================
def paragraph_texts(xml_bytes):
    """Paragraph text under the nested-paragraph rule: an element inside a nested w:p
    belongs to the INNER paragraph, which is the reading half's own grouping."""
    root = etree.fromstring(xml_bytes)
    p_tag = f"{{{W}}}p"
    out = []
    for p in root.iter(p_tag):
        parts = []
        for e in p.iter():
            if e.tag not in TEXT_TAGS:
                continue
            a, nested = e.getparent(), False
            while a is not None and a is not p:
                if a.tag == p_tag:
                    nested = True
                    break
                a = a.getparent()
            if not nested:
                parts.append(e.text or "")
        out.append("".join(parts))
    return out


def accounted_for(before_paras, after_paras, jrnl):
    """Does the journal claim exactly the paragraphs that moved? Returns (moved, missing,
    phantom) — missing is what moved and was not claimed, phantom the reverse."""
    moved = {i for i, (b, a) in enumerate(zip(before_paras, after_paras)) if b != a}
    if len(before_paras) != len(after_paras):
        moved |= set(range(min(len(before_paras), len(after_paras)),
                           max(len(before_paras), len(after_paras))))
    claimed = {r.get("para") for st in jrnl.get("stages", [])
               for r in st.get("paragraphs", [])}
    return moved, sorted(moved - claimed), sorted(claimed - moved)


R_TAG = f"{{{W}}}r"
PPR_TAG = f"{{{W}}}pPr"


def _shape(el):
    """Tag plus sorted attributes, no text. FULL {namespace}localname and never the
    localname alone — `t` is w:t, a:t and dgm:t, and a localname match once counted one
    chart part as four surfaces."""
    return el.tag + "".join(f" {k}={v}" for k, v in sorted(el.attrib.items()))


def _subtree(el):
    return " | ".join(_shape(x) for x in el.iter())


def flat_formats(xml_bytes):
    """BRANCH 10 SLICE 1's SECOND READER for the FORMAT contract, written from the
    contract's words and importing nothing from the script it measures. For each
    text-bearing element, the shape of the w:r carrying it, at the same flat ordinal the
    text record uses."""
    root = etree.fromstring(xml_bytes)
    out = []
    for e in root.iter():
        if e.tag not in TEXT_TAGS:
            continue
        a = e.getparent()
        while a is not None and a.tag != R_TAG:
            a = a.getparent()
        out.append(_shape(e) if a is None else _subtree(a))
    return out


def paragraph_formats(xml_bytes):
    """For each paragraph, the shape of its own w:pPr — same index as paragraph_texts."""
    root = etree.fromstring(xml_bytes)
    out = []
    for p in root.iter(f"{{{W}}}p"):
        ppr = p.find(PPR_TAG)
        out.append("" if ppr is None else _subtree(ppr))
    return out


def format_accounted_for(before_bytes, after_bytes, jrnl):
    """Did the journal claim exactly the runs and paragraphs whose SHAPE moved?

    Returns (moved_e, missing_e, elem_void, moved_p, missing_p, para_void, note). The two
    VOID flags are returned explicitly rather than left to be read out of the note: a caller
    that has to pattern-match prose to find out what was measured is one substitution away
    from reporting a void as a clean zero.
    """
    be, ae = flat_formats(before_bytes), flat_formats(after_bytes)
    bp, ap = paragraph_formats(before_bytes), paragraph_formats(after_bytes)
    claimed_e = {e.get("elem") for st in jrnl.get("stages", [])
                 for e in st.get("format_edits", [])}
    claimed_p = {r.get("para") for st in jrnl.get("stages", [])
                 for r in st.get("format_paragraphs", [])}

    # THE TWO LEVELS VOID SEPARATELY, AND THE FIRST VERSION OF THIS FUNCTION VOIDED THEM
    # TOGETHER — which the corpus caught and no fixture could have. This arm compares the
    # ORIGINAL bytes with the FINAL bytes, so it spans BOTH stages; strip_noop DELETES
    # w:ins/w:del wrappers, so on any tracked-change document the element count moves and
    # every flat ordinal after the first deletion shifts. Folding the paragraph level into
    # that void threw away coverage that was never in doubt: the strip does not add or
    # remove PARAGRAPHS, so the paragraph enumeration is stable across the whole run.
    # Reported as `n/a` for the element level alone, with the paragraph level still
    # answering — a void that takes a sound measurement down with it is not caution.
    note = None
    if len(be) != len(ae):
        note = (f"element count moved ({len(be)}->{len(ae)}), which is what strip_noop "
                f"does on a tracked-change document; the format contract does not claim "
                f"an ordinal record across that, and says so")
        moved_e, missing_e = set(), []
    else:
        moved_e = {i for i, (b, a) in enumerate(zip(be, ae)) if b != a}
        missing_e = sorted(moved_e - claimed_e)

    if len(bp) != len(ap):
        note = ((note + " AND ") if note else "") + (
            f"paragraph count moved ({len(bp)}->{len(ap)}), which nothing in this stage is "
            f"documented to do")
        moved_p, missing_p = set(), []
    else:
        moved_p = {i for i, (b, a) in enumerate(zip(bp, ap)) if b != a}
        missing_p = sorted(moved_p - claimed_p)

    return (moved_e, missing_e, len(be) != len(ae),
            moved_p, missing_p, len(bp) != len(ap), note)


def run_post_process(scripts_dir, xml_path, timeout=900):
    return subprocess.run(
        ["uv", "run", "--with", "lxml", "python",
         str(Path(scripts_dir) / SCRIPT), str(xml_path), "--fix",
         "--variant", args.variant],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        cwd=str(ROOT), env=ENV, timeout=timeout)


def stage_input(ordinal, src_xml, label):
    """A fresh <workdir>/final/word/document.xml holding a COPY of the frozen input.

    NO paragraphs.json is placed beside it, deliberately: the post-strip drift gate would
    then run and RAISE on a document whose notes no longer match, which is a different
    question from the one this arm asks and would stop the run before the journal could be
    read. The journal is written BEFORE that gate, but the gate's exit code would still
    mask this arm's result.
    """
    d = TMP / f"{label}{ordinal:02d}" / "final" / "word"
    d.mkdir(parents=True, exist_ok=True)
    dest = d / "document.xml"
    shutil.copy2(src_xml, dest)
    return TMP / f"{label}{ordinal:02d}", dest


print("=" * 96)
print(f"BRANCH 9 CORPUS ARM — is the change journal complete on the real documents?  "
      f"[{args.variant}]")
print("=" * 96)

if not LOGS.is_dir():
    print("\n  VOID — the logs root is not present, so the real arm is unavailable in this")
    print("  clone. This is SAID rather than reported as a smaller clean run.")
    print("=" * 96)
    sys.exit(2)

workdirs = sorted({p.parent for p in LOGS.rglob("paragraphs.json")})
if args.limit:
    workdirs = workdirs[:args.limit]
print(f"\n  frozen workdirs enumerated: {len(workdirs)}")

# =========================================================================================
# ARM 0 — IS THE PIN STILL ANSWERING A QUESTION? A baseline byte-identical to the working
# tree makes arm 1 a self-comparison, which is VOID and never a pass.
# =========================================================================================
print(f"\nARM 0 — is {REF} still a different {SCRIPT}?")
blob = subprocess.run(["git", "show", f"{REF}:{args.variant}/scripts/{SCRIPT}"],
                      capture_output=True, cwd=str(ROOT))
cur = (SCRIPTS / SCRIPT).read_bytes()
BASELINE_DIR = None
if blob.returncode != 0:
    void("baseline readable", f"cannot read {SCRIPT} at {REF}")
elif blob.stdout == cur:
    # A NOTICE, NOT A VOID, AND THE DIFFERENCE IS DELIBERATE. Between branches the pin sits
    # at the merge of the last branch to touch either tree, so the baseline IS the working
    # tree and this is the expected RESTING state — not a defect and not something to fix.
    # Recording it as VOID would make this tool exit non-zero on every run on `main`, and a
    # permanently-failing instrument is one people learn to scroll past. So it is printed
    # loudly instead, exactly as tools/apply_corpus_diff.py prints its self-comparison
    # notice, and the byte column below reads `—` rather than a row of `identical` verdicts
    # that would mean nothing. THE COMPLETENESS ARMS STILL GATE: they need no baseline at
    # all, and they are this tool's primary job.
    print(f"  NOTE  {SCRIPT} is BYTE-IDENTICAL to {REF}, so there is nothing to compare and")
    print(f"        the byte-identity column below is OMITTED rather than filled with a")
    print(f"        verdict that would read as evidence. This is the expected state between")
    print(f"        branches; it starts answering again the moment a branch edits {SCRIPT}.")
elif b"\n# === SKILL FILE COMPLETE ===" not in blob.stdout:
    void("baseline usable", "the baseline blob has no integrity sentinel; it exits 3")
else:
    BASELINE_DIR = TMP / "baseline-scripts"
    BASELINE_DIR.mkdir(parents=True, exist_ok=True)
    (BASELINE_DIR / SCRIPT).write_bytes(blob.stdout)
    # strip_noop is invoked BY post_process as a sibling subprocess, so the baseline copy
    # needs it beside the script or the tracked-change documents take a different path in
    # the two arms and the byte comparison answers the wrong question.
    for sibling in ("strip_noop_tracked_changes.py", "validate_apply.py"):
        s = SCRIPTS / sibling
        if s.is_file():
            shutil.copy2(s, BASELINE_DIR / sibling)
    ok(f"the baseline {SCRIPT} differs from the working tree, so arm 1 has a question",
       True, "")

# =========================================================================================
# ARM 1 — COMPLETENESS, AND BYTE IDENTITY, PER DOCUMENT.
# =========================================================================================
print("\nARM 1 — per document: does the journal account for every text change AND every")
print("        formatting change, and is document.xml still byte-identical to the baseline?")
print(f"  {'wd':>4}  {'input':>9}  {'paras':>6}  {'moved':>5}  {'edits':>5}  "
      f"{'strip':>5}  {'nontext':>7}  {'fmt':>5}  {'fmtP':>4}  {'bytes':>9}  verdict")

examined = with_movement = 0
unreadable = []
fmt_declared = []      # rows where the format contract says it does not claim the case
worst = None           # (moved_count, workdir_path, ordinal) — the positive control's host
worst_fmt = None       # the same, for the FORMATTING control — a different document may win
for i, wd in enumerate(workdirs):
    delivered = wd / "final" / "word" / "document.xml"
    pre = [c for c in (wd / n for n in PRE_SNAPSHOT_NAMES) if c.is_file()]
    if not pre:
        pre = [c for c in wd.rglob("*.xml") if c.name in PRE_SNAPSHOT_NAMES]
    if pre:
        src, kind = pre[0], "pre-snap"
    elif delivered.is_file():
        src, kind = delivered, "delivered"
    else:
        # A path that cannot be read is REPORTED, never skipped. A scan whose denominator
        # can shrink in silence is not a scan.
        unreadable.append(i)
        print(f"  {i:>4}  {'—':>9}  no document.xml under final/word/ — NOT EXAMINED")
        continue

    try:
        before_bytes = src.read_bytes()
    except OSError as exc:
        unreadable.append(i)
        print(f"  {i:>4}  {kind:>9}  unreadable ({type(exc).__name__}) — NOT EXAMINED")
        continue

    work, xml = stage_input(i, src, "new")
    r = run_post_process(SCRIPTS, xml)
    if r.returncode != 0:
        unreadable.append(i)
        print(f"  {i:>4}  {kind:>9}  post_process exited {r.returncode} — NOT EXAMINED")
        continue
    examined += 1

    jpath = work / JOURNAL_NAME
    if not jpath.is_file():
        FAIL.append(f"wd{i}: no journal was written")
        print(f"  {i:>4}  {kind:>9}  NO JOURNAL WRITTEN")
        continue
    jrnl = json.loads(jpath.read_text(encoding="utf-8"))

    before_paras = paragraph_texts(before_bytes)
    after_bytes = xml.read_bytes()
    after_paras = paragraph_texts(after_bytes)
    moved, missing, phantom = accounted_for(before_paras, after_paras, jrnl)

    st = next(s for s in jrnl["stages"] if s["stage"] == "passes")
    strip = next((s for s in jrnl["stages"]
                  if s["stage"] == "strip_noop_tracked_changes"), None)
    nontext = sum(n["fixes"] for n in jrnl["self_check"]["non_text_fixes"])

    byte_note = "—"
    if BASELINE_DIR is not None:
        owork, oxml = stage_input(i, src, "old")
        ro = run_post_process(BASELINE_DIR, oxml)
        if ro.returncode != 0:
            byte_note = f"old rc{ro.returncode}"
        else:
            ob = oxml.read_bytes()
            byte_note = "identical" if ob == after_bytes else "MOVED"
            if ob != after_bytes:
                FAIL.append(
                    f"wd{i}: document.xml MOVED against {REF} — branch 9 is additive and "
                    f"must not change a delivered byte "
                    f"(new={hashlib.sha256(after_bytes).hexdigest()[:12]} "
                    f"old={hashlib.sha256(ob).hexdigest()[:12]})")

    if moved:
        with_movement += 1
        if worst is None or len(moved) > worst[0]:
            worst = (len(moved), src, i)
    # BRANCH 10 SLICE 1 — THE FORMATTING ARM, read by the second reader above. Before this
    # slice the `nontext` column to the left was the END of what could be said: a figure
    # with no location and no pass behind it. These two columns are what turns it into an
    # account, and slice 3 cannot show a CONDITIONAL pass did the right thing without them.
    (moved_fe, missing_fe, elem_void,
     moved_fp, missing_fp, para_void, fnote) = format_accounted_for(
        before_bytes, after_bytes, jrnl)
    fmt_note = "n/a" if elem_void else str(len(moved_fe))
    fmtp_note = "n/a" if para_void else str(len(moved_fp))
    if fnote:
        # DECLARED, NOT SILENT — and counted separately from a failure, because a contract
        # that says in its own words which case it does not claim has not failed to measure
        # it. A run where every such row was folded into `0` would read as full coverage.
        fmt_declared.append(f"wd{i}: {fnote}")
    if missing_fe or missing_fp:
        FAIL.append(
            f"wd{i}: {len(missing_fe)} run(s) and {len(missing_fp)} paragraph(s) "
            f"changed SHAPE with no formatting record claiming them")
    if not elem_void and moved_fe and (
            worst_fmt is None or len(moved_fe) > worst_fmt[0]):
        worst_fmt = (len(moved_fe), src, i)

    verdict = "accounted" if not missing and not phantom else "UNACCOUNTED"
    if missing or phantom:
        FAIL.append(f"wd{i}: {len(missing)} moved-and-unclaimed, "
                    f"{len(phantom)} claimed-and-unmoved")
    if not fnote and (missing_fe or missing_fp):
        verdict = "UNACCOUNTED"
    print(f"  {i:>4}  {kind:>9}  {len(before_paras):>6}  {len(moved):>5}  "
          f"{len(st['edits']):>5}  {len(strip['paragraphs']) if strip else 0:>5}  "
          f"{nontext:>7}  {fmt_note:>5}  {fmtp_note:>4}  {byte_note:>9}  {verdict}")

print(f"\n  examined {examined} of {len(workdirs)} frozen workdirs; "
      f"{len(unreadable)} not examined")
ok("every enumerated workdir was examined or REPORTED as not examined",
   examined + len(unreadable) == len(workdirs),
   f"{examined} + {len(unreadable)} != {len(workdirs)}")
ok("no document had a text change the journal failed to claim",
   not any(f.startswith("wd") and "unclaimed" in f for f in FAIL))
ok("no document had a FORMATTING change the journal failed to claim",
   not any("changed SHAPE" in f for f in FAIL))
print(f"\n  formatting: {examined - len(fmt_declared)} of {examined} document(s) measured "
      f"at BOTH levels; {len(fmt_declared)} carry a DECLARED limitation, named below")
for line in fmt_declared:
    print(f"    {line}")
if BASELINE_DIR is not None:
    ok(f"no document's delivered bytes moved against {REF} — branch 9 is ADDITIVE",
       not any("MOVED against" in f for f in FAIL))

print(f"\n  documents with something to account for: {with_movement} of {examined}")
if with_movement == 0:
    void("completeness over the corpus",
         "no document moved, so every 'accounted' above is the empty case")
else:
    print("  The rest are CALIBRATION, not evidence: they say the instrument does not cry")
    print("  wolf on a stage that has nothing to do. Only the documents above with a")
    print("  non-zero `moved` column tested the journal at all.")

# =========================================================================================
# ARM 2 — THE POSITIVE CONTROL. Remove one entry from a real journal and require the
# completeness comparison to name that document. A check that has never failed is not known
# to be able to.
# =========================================================================================
print("\nARM 2 — the positive control: a journal with one paragraph record removed")
if worst is None:
    void("positive control", "no document moved, so there is no record to remove")
else:
    n_moved, src, ordinal = worst
    work, xml = stage_input(900, src, "ctl")
    r = run_post_process(SCRIPTS, xml)
    jpath = work / JOURNAL_NAME
    if r.returncode != 0 or not jpath.is_file():
        void("positive control", f"the control run did not produce a journal (rc={r.returncode})")
    else:
        jrnl = json.loads(jpath.read_text(encoding="utf-8"))
        before_paras = paragraph_texts(src.read_bytes())
        after_paras = paragraph_texts(xml.read_bytes())
        m0, missing0, phantom0 = accounted_for(before_paras, after_paras, jrnl)
        ok(f"the host document is clean before the control is planted "
           f"(wd{ordinal}, {n_moved} paragraph(s) moved)",
           not missing0 and not phantom0,
           f"missing={len(missing0)} phantom={len(phantom0)}")
        holed = json.loads(json.dumps(jrnl))
        removed = None
        for stg in holed["stages"]:
            if stg.get("paragraphs"):
                removed = stg["paragraphs"].pop()
                break
        if removed is None:
            void("positive control", "the journal carried no paragraph record to remove")
        else:
            _m, missing1, _p = accounted_for(before_paras, after_paras, holed)
            ok("with one record removed the comparison reports that paragraph as "
               "UNACCOUNTED — so the arm above can fail",
               removed["para"] in missing1,
               f"removed para {removed['para']}, missing={missing1[:5]}")

# =========================================================================================
# ARM 3 — THE POSITIVE CONTROL FOR THE FORMATTING RECORD, and it is a SEPARATE control
# rather than a second assertion inside ARM 2. ARM 2's host is chosen by how much TEXT
# moved; the document whose formatting moves most is a different one, and on this corpus it
# is. A control planted in the wrong document proves the arm can fail somewhere it was never
# going to be asked.
# =========================================================================================
print("\nARM 3 — the positive control: a journal with one FORMATTING record removed")
if worst_fmt is None:
    void("formatting positive control",
         "no document's run shapes moved at a measurable level, so there is nothing to "
         "remove — the formatting arm is UNPROVEN on this corpus, not clean")
else:
    n_fmt, fsrc, fordinal = worst_fmt
    fwork, fxml = stage_input(901, fsrc, "fctl")
    rf = run_post_process(SCRIPTS, fxml)
    fjpath = fwork / JOURNAL_NAME
    if rf.returncode != 0 or not fjpath.is_file():
        void("formatting positive control",
             f"the control run produced no journal (rc={rf.returncode})")
    else:
        fj = json.loads(fjpath.read_text(encoding="utf-8"))
        fbefore, fafter = fsrc.read_bytes(), fxml.read_bytes()
        _me, miss0, _ev, _mp, missp0, _pv, _n = format_accounted_for(fbefore, fafter, fj)
        ok(f"the host document is clean before the control is planted "
           f"(wd{fordinal}, {n_fmt} run shape(s) moved)",
           not miss0 and not missp0,
           f"missing elems={len(miss0)} paras={len(missp0)}")
        fholed = json.loads(json.dumps(fj))
        fremoved = None
        for stg in fholed["stages"]:
            if stg.get("format_edits"):
                fremoved = stg["format_edits"].pop()
                break
        if fremoved is None:
            void("formatting positive control",
                 "the journal carried no element-level formatting record to remove")
        else:
            _m1, miss1, _e1, _p1, _mp1, _v1, _n1 = format_accounted_for(
                fbefore, fafter, fholed)
            ok("with one formatting record removed the comparison reports that run as "
               "UNACCOUNTED — so the formatting arm above can fail",
               fremoved["elem"] in miss1,
               f"removed elem {fremoved['elem']}, missing={miss1[:5]}")

print("\n" + "=" * 96)
print(f"  {CHECKED} check(s), {len(FAIL)} failure(s), {len(VOIDED)} void")
for f in FAIL:
    print(f"    FAIL  {f}")
for v in VOIDED:
    print(f"    VOID  {v}")
shutil.rmtree(TMP, ignore_errors=True)
print("=" * 96)
sys.exit(1 if (FAIL or VOIDED) else 0)
