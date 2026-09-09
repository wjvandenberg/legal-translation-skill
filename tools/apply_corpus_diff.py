# -*- coding: utf-8 -*-
"""THE ACCEPTANCE INSTRUMENT FOR EVERY FIX BRANCH — what apply does DIFFERENTLY, on the real corpus.

THE ACCEPTANCE CONDITION OF A FIX BRANCH IS THE OPPOSITE OF EVERY BRANCH BEFORE BRANCH 6.
Branches 0-5 and branch 14's slice each proved that no delivered byte moved. Branch 6 was the
first fix branch that CHANGES a delivered document, so "nothing moved" would mean it had
failed, and branch 7 is the same. The condition is instead:

    THE BYTES MUST MOVE, AND EVERY MOVEMENT MUST BE EXPLAINED BY A REGISTER ROW.
    Anything that moves which no row predicted is a DEFECT until shown otherwise.

So this tool does not pass or fail on movement. It runs the mechanical half twice over the
same frozen intermediate -- once with apply as it stands at a PINNED COMMIT, once with the
working tree -- and reports, per document, which structures moved and whether a row for that
document predicted it.

WHY A FROZEN INTERMEDIATE. The expensive half of a run is the translation: a model, 20-50
minutes, and about 40% of paragraphs differing between two runs of one document. Mechanically
two runs are IDENTICAL -- measured, on the project's only same-document repeat (P23). With the
translated notes frozen the mechanical half is a deterministic function, so this is seconds
and repeatable with no model in the loop.

OUTPUT POLICY, because this reads the logs folder. It prints corpus doc-ids (a file's place
in the corpus, never the instrument or the parties), structure COUNTS, and register row ids.
It never prints a filename, a directory name below the logs root, a paragraph, or any
document text. Same licence tools/evidence_ls.py and tools/gate_replay.py operate under.

NOTHING IS EVER WRITTEN INTO THE LOGS FOLDER. The frozen intermediates are a BASELINE; apply
writes a batch-state file beside its input, so every input is copied into a temporary
directory first. A baseline that the tool measuring it can modify is not a baseline.

    uv run --with lxml python tools/apply_corpus_diff.py
    uv run --with lxml python tools/apply_corpus_diff.py --variant us
    uv run --with lxml python tools/apply_corpus_diff.py --doc D06
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
os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tests"))
from docx_census import census, delta  # noqa: E402
from lxml import etree  # noqa: E402

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
LOGS = Path(os.environ.get("LT_LOGS_DIR", ROOT.parent / "legal-translation-logs"))
SCRIPT = "apply_translations_textmatch.py"

# PINNED TO A COMMIT, NEVER TO A BRANCH NAME OR HEAD. CLAUDE.md 5.16: a before-and-after check
# once read its "before" from HEAD, which worked only while the change was uncommitted and then
# compared the new file against itself and reported 100% carried.
#
# MOVED TO 010c34f ON 2026-09-09, the squash-merge of branch 7 slice 3 (PR #69), which CLOSED
# branch 7, and the LAST COMMIT THAT TOUCHED EITHER TREE. DERIVED, NOT READ OFF THE MERGE
# MESSAGE: `git log --oneline -1 -- uk us` returns it, and `git diff 010c34f -- uk us` comes
# back empty. A pin left at the previous baseline reports the merged slice's own work as
# movement belonging to whatever branch runs next, and the branch that inherits it cannot
# tell.
#
# IT HAS NOW MOVED SEVEN TIMES IN FIVE DAYS -- 4a1c452, 049484e, 2a71e71, d3c7f19, 544f908,
# ae48f6d, here -- and that cadence IS the argument for the rule rather than a complaint
# about it: moving it is the FIRST act after a merge, never a closing tidy-up.
#
# AND THE HABIT ITSELF WENT STALE THIS SESSION, WHICH IS THE MORE USEFUL LESSON THAN THE
# CADENCE. Every close for five days moved "BOTH pins". Slice 3 added a THIRD tool carrying
# one -- tools/hf_corpus_diff.py -- so "both" was already wrong on the commit that introduced
# it, and a phrase that names a COUNT is wrong the moment the thing it counts changes.
# `git grep -F <old sha>` enumerates the carriers and is the only reading that cannot go
# stale. It found three, and one of them then turned out to need a FIXED pin rather than this
# moving one -- see hf_corpus_diff.py's own block for the measurement.
#
# AND SLICE 2 REMAINS THE CASE WHERE FORGETTING WOULD HAVE BEEN HARDEST TO SEE, and slice 3
# is a second of the same kind. Both changed scripts this tool does not drive -- repack and
# extraction, then the header/footer translator and extraction -- so its two arms were
# byte-identical BY DESIGN and it reported 13 of 13 unchanged. A stale pin would have gone on
# reporting exactly that, a correct-looking all-quiet run, over a baseline silently lacking
# the merged slice's change. The reading that catches a stale pin is the one that MOVES, and
# neither slice produced one.
#
# AND THE PROSE ABOVE THE PIN GOES STALE AS READILY AS THE PIN, WHICH IS WHY THIS BLOCK IS
# REWRITTEN EACH TIME RATHER THAN APPENDED TO. It has gone stale twice and been caught twice:
# once still naming 79a8c14 as "the merge-base of this branch", and once with the same block
# in tools/render_diff.py reading "Moved to 049484e" while its pin one line below said
# 2a71e71 -- two claims disagreeing inside five lines, both true once. NOTHING CHECKS A
# COMMENT. Re-derive both claims on the commit that moves the pin.
REF = os.environ.get("LT_BASELINE_REF", "010c34f")

# WHICH DIRECTIONAL CHECK BELONGS TO WHICH MERGED FIX — added 2026-09-08, on a measured false
# alarm that would have recurred for ever.
#
# A "DID THE FIX FIRE?" CHECK IS MEANINGLESS ONCE ITS FIX IS IN THE PINNED BASELINE, AND IT
# DOES NOT GO QUIET — IT FAILS. The C17 arm asks whether a document whose notes carry a
# whitespace-only segment had its text move between the two arms. That is the right question
# while C17's fix is under review. The moment branch 6 slice 4 merged and the pin moved to it,
# BOTH arms carry the fix, so nothing can move and the check reports two defects on every run:
# "the fix did not fire where the measurement says it must", on D02 and D07, for ever, with
# nobody able to act on it.
#
# Same family as CLAUDE.md 5.16's second rule -- ask of every claim whether it asserts a
# HISTORICAL DELIVERY or a LIVE INVENTORY -- and it is the third member of that family found
# in this one file. `git merge-base --is-ancestor` settles it exactly: if the fix's commit is
# an ancestor of the baseline, the baseline already has it and the question is answered, not
# open. Forgetting to add a row here produces a LOUD false defect rather than a silent pass,
# which is the right way round.
FIX_LANDED = {
    "C17": "d3c7f19",      # branch 6 slice 4
    # A16/N1 added the moment slice 1 merged, 2026-09-08, and adding it HERE is the whole
    # point of the table: the container arm's "the fix did not fire" check is now in the
    # baseline exactly as C17's was, so leaving this row out would make it the next
    # guaranteed false defect -- register I-24, for the second time, on the branch that
    # filed it.
    "CONTAINER": "544f908",   # branch 7 slice 1
}


def fix_in_baseline(key):
    """True if the named fix is already an ancestor of the baseline, so its directional
    check can no longer be asked. Unknown key -> False: the fix is not merged yet."""
    sha = FIX_LANDED.get(key)
    if not sha:
        return False
    r = subprocess.run(["git", "merge-base", "--is-ancestor", sha, REF],
                       capture_output=True, cwd=ROOT)
    return r.returncode == 0

# WHICH ROW OWNS WHICH STRUCTURE — taken from FINDINGS-REGISTER.md's `docs` column, used as
# a LABEL rather than as the gate. The documents named are the ones that were MEASURED, not
# the extent of the mechanism: A3's whitelist bug is in one branch of one classifier and
# applies to every document, so a tab restored on a document nobody measured is A3's evidence
# widening, not an unexplained movement.
ROW = {
    "footnoteReference": "A1 (D05, D09 measured)",
    "endnoteReference": "A1's structure, no instance recorded",
    "commentReference": "A2 (D02, D08 measured)",
    "commentRangeStart": "A2's control",
    "commentRangeEnd": "A2 (D08 lost ranges too, 13 -> 11)",
    "hyperlink": "A8 (D06 measured)",
    "tab_chars": "A3 (D01 D02 D05 D06 D07 D11 measured)",
    "fldChar": "A9 (D06 measured)",
    "instrText": "A9 (D06 measured)",
    "br_plain": "F27's newline half (D01, D10 named; the boundary newlines are on D06, D09)",
}

# THREE CLASSES, AND THE DISTINCTION IS WHAT MAKES THIS TOOL READABLE. The first version
# flagged every moved key against a document list and produced 25 "unexplained" movements, of
# which 20 were a run count rising -- which CLAUDE.md 5.6's first measurement rule says must
# never be scored at all: "Never score ANY run property from element counts -- translation
# consolidates runs, so nearly every count falls even when nothing is lost."
#
# RESTORE   must move TOWARD the SOURCE document's count. That is the fix. Moving AWAY is a
#           defect, and it is the only direction that can be one.
# HOLD      must not move at all: the negative control (tab stops are not tab characters), the
#           containers another branch owns, and the rendering cache this branch deliberately
#           does not carry forward.
# REPORT    printed and never flagged. Run, paragraph and text-element counts change whenever
#           runs are split or consolidated, which this branch does by design.
RESTORE = ("footnoteReference", "endnoteReference", "commentReference",
           "commentRangeStart", "commentRangeEnd", "hyperlink",
           "drawing", "pict", "object", "sym", "br_page",
           # br_plain WAS IN 'REPORT' UNTIL 2026-09-01, AND THAT HID F27's ONLY REAL-CORPUS
           # EVIDENCE. Measured across all 1,891 frozen notes entries: ZERO boundary tabs
           # anywhere -- so F27's tab half is testable only on the synthetic fixture -- and
           # exactly FIVE boundary newlines, four on D06 and one on D09. Those five are
           # precisely D06's br_plain 7 -> 11 and D09's 4 -> 5. Filed as "structural, not
           # scored", a restoration that lands exactly on the source count was reading as
           # noise.
           "br_plain")
# CLAUSE 3's KEYS, AND THEY RUN THE OTHER WAY. A9 DELETES a field skeleton once its cached
# result has been consumed into the English, so here a count BELOW the source is the fix and a
# count above it is the defect. Putting these in RESTORE was wrong and the corpus run would
# have reported the A9 fix as "AWAY FROM SOURCE — DEFECT": the instrument would have called
# its own branch's intended behaviour a regression.
DELETE = ("fldChar", "instrText")
# tab_chars WAS IN 'RESTORE' UNTIL WOUTER READ THE PAGES ON 2026-09-01, and that was wrong in
# BOTH directions. A3 is a PARTIAL row: a tab whose true position survives the collapse is
# restored, and one that sat BETWEEN text is DROPPED, because emitting it at the paragraph end
# glued D06's page numbers exactly as before AND forced a line wrap. So a count BELOW source is
# the intended outcome here, and only a count ABOVE source could be a defect.
#
# THE COUNT IS NOT THE CRITERION AND THIS IS THE MEASUREMENT THAT PROVES IT: D02 went 61 -> 16
# tab characters, 45 fewer than the OLD code kept, and NOT ONE PIXEL moved on any of its 11
# pages. A stranded tab advances into empty space. CLAUDE.md 2.5 item 7 -- judge a layout
# device on its RENDERED EFFECT, never on its element count -- so the verdict for this key
# points at tools/render_diff.py rather than pretending a number settles it.
PARTIAL = ("tab_chars",)
# sdt AND smartTag LEFT 'HOLD' ON 2026-09-08, ON BRANCH 7, AND THE MOVE IS DELIBERATE. They
# sat there labelled "the containers another branch owns" — and branch 7 is that branch. But
# they do NOT belong in RESTORE either, and getting that wrong would have made this harness
# report the fix as having done nothing: the fix removes the source-language TEXT from inside
# a container and leaves the container itself exactly where it was, so the COUNT is expected
# to hold at the same time as the contents change.
#
# THIS IS THE THIRD BRANCH RUNNING WHERE THE ACCEPTANCE INSTRUMENT COULD NOT EXPRESS THE
# CONDITION UNTIL IT WAS EXTENDED. The census counts structures; C16 and C17 changed text
# inside an element that already existed, and so does this. A class whose verdict is "must
# not move" would have been satisfied by a fix that did nothing at all.
CONTAINED = ("sdt", "smartTag")
HOLD = ("tab_stops", "lastRenderedPageBreak")
REPORT = ("r", "p", "t", "delText", "ins", "del", "trailing_tabs", "br_plain")

ap = argparse.ArgumentParser()
ap.add_argument("--variant", default="uk", choices=("uk", "us"))
ap.add_argument("--doc", action="append", help="limit to these corpus doc-ids")
ap.add_argument("--ref", default=REF, help="baseline commit to compare against")
args = ap.parse_args()

print("=" * 100)
print(f"APPLY, BEFORE AND AFTER, ON THE FROZEN INTERMEDIATES  ({args.variant})")
print("=" * 100)

if not LOGS.exists():
    print(f"  logs folder not reachable at {LOGS}")
    print("  This is a SKIP, not a pass. Set LT_LOGS_DIR.")
    sys.exit(0)

r = subprocess.run(["git", "rev-parse", "--verify", args.ref],
                   capture_output=True, text=True, cwd=ROOT)
if r.returncode != 0:
    print(f"  VOID — baseline ref {args.ref} does not resolve. Nothing compared.")
    sys.exit(1)
SHA = r.stdout.strip()
blob = subprocess.run(["git", "show", f"{args.ref}:{args.variant}/scripts/{SCRIPT}"],
                      capture_output=True, cwd=ROOT)
if blob.returncode != 0:
    print(f"  VOID — cannot read {SCRIPT} at {args.ref}.")
    sys.exit(1)
CUR = (ROOT / args.variant / "scripts" / SCRIPT).read_bytes()
print(f"  baseline: {args.ref} = {SHA[:12]}")

# A COMPARISON OF A FILE WITH ITSELF IS TRIVIALLY IDENTICAL, WHICH IS EXACTLY THE RESULT A
# "nothing moved" READING WANTS. Say so instead of reporting it as a clean run.
SAME = blob.stdout == CUR
if SAME:
    print(f"  NOTE: {SCRIPT} is BYTE-IDENTICAL to {args.ref}. Every comparison below is the")
    print("  same code against itself, so an all-quiet result proves NOTHING about the fix.")
    print("  Useful for exactly one thing: showing this harness reports no movement when")
    print("  there is none. Treat any movement at all as a harness defect.")

TMP = Path(tempfile.mkdtemp(prefix="b6-corpus-"))
OLDTREE = TMP / "old_scripts"
shutil.copytree(ROOT / args.variant / "scripts", OLDTREE)
(OLDTREE / SCRIPT).write_bytes(blob.stdout)
# The sentinel is a plain string at the file's end, not a hash, so a copied script still
# passes its own integrity check. Prove it rather than assume it.
if b"\n# === SKILL FILE COMPLETE ===" not in (OLDTREE / SCRIPT).read_bytes():
    print("  VOID — the baseline copy has no integrity sentinel; it would exit 3 on import.")
    sys.exit(1)


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


# A RUN OF TWO OR MORE SPACES OR TABS, counted as ONE occurrence rather than as n-1 pairs, so
# three spaces is one defect and not two. Newlines excluded: `br_plain` owns those.
DOUBLE = re.compile(r"[^\S\r\n]{2,}")


def para_texts_raw(xml_bytes):
    """`para_texts` WITHOUT the trailing `.strip()`, and the difference is a whole finding.

    `para_texts` strips, correctly: it exists to match a delivered paragraph against the
    notes' `text` field, and those are stripped. But the FIRST version of the text arm below
    reused it, and C17's three real corpus instances are every one of them the LAST segment of
    their paragraph -- so the space the fix restores is a TRAILING space, and `.strip()`
    deleted it before the comparison could see it. The arm reported `0 paragraph(s) changed`
    on D02 and D07 while the census showed their `ins` and `t` counts had moved.

    That is the same shape as the mislabel it was written to correct, one level down: the thing
    measured was not the thing under review. Two readers, two purposes, two functions.
    """
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
        out.append("".join(pieces))
    return out


def _doubles(texts):
    """(interior runs, trailing-whitespace paragraphs) -- and they are NOT one number.

    MEASURED, AND IT IS WHY THIS IS SPLIT: of the 13 double-space runs on D07's delivered text,
    most sit at the very END of a paragraph, after a full stop, where nothing can render them.
    Totalling them with the interior ones produces a figure that moves for reasons a reader
    cannot see, and C16 is a claim about a double space BETWEEN WORDS.
    """
    interior = 0
    trailing = 0
    for t in texts:
        for m in DOUBLE.finditer(t):
            if m.end() < len(t):
                interior += 1
        if t and t[-1].isspace():
            trailing += 1
    return interior, trailing


def text_delta(old_bytes, new_bytes):
    """What the CENSUS CANNOT SEE, and this arm exists because it could not.

    THE CENSUS COUNTS STRUCTURES. C16 and C17 change TEXT INSIDE AN ELEMENT THAT ALREADY
    EXISTS -- a space restored into a `<w:t>` that was there either way -- so a fully working
    fix produces an EMPTY census delta. Before this arm existed the summary below derived its
    counts from that delta while printing the word "byte-quiet", so branch 6's fourth slice
    would have reported `13 byte-quiet` on a run where two documents' bytes had changed.
    CLAUDE.md 5.16's shape exactly: the thing measured was not the thing under review.

    Indices are paragraph POSITIONS, never text -- nothing here can print a document's
    content.
    """
    o, n = para_texts_raw(old_bytes), para_texts_raw(new_bytes)
    changed = [i for i, (a, b) in enumerate(zip(o, n)) if a != b]
    if len(o) != len(n):
        changed.append(-1)          # -1 means the paragraph COUNT moved, which is not a text
                                    # change at all and must not be silently averaged into one
    return changed, _doubles(o), _doubles(n)


# THE CONTAINERS THIS BRANCH NEWLY REACHES, and the two exclusions are the whole reason this
# is a separate tuple from the shipped inventory. Deliberately NOT imported from the shipped
# script either: this tool must be able to report on a tree whose inventory has changed, and
# tests/test_container_inventory.py is what asserts the shipped copies agree with each other.
#
#   w:hyperlink  EXCLUDED, and leaving it in produced a MEASURED FALSE ALARM on the first
#                acceptance run. Branch 6 already made apply recurse into it, so a
#                hyperlink's text is translated and its stranded-fragment count CANNOT fall.
#                On the table-of-contents document that is 34 predicted containers and 53
#                fragments stable in both arms, which the "did the fix fire?" check read as
#                "A16/N1's fix did not fire here" -- a defect report on a document where
#                there was never anything to fix. An instrument that predicts a change it
#                has no reason to expect reports its own scope error as a finding.
#   w:fldSimple  EXCLUDED because it is PINNED. Its cached result is deliberately still
#                duplicated -- A9's defect in the one field form clause 3 cannot see -- so
#                counting it would make every document carrying one look unfixed for ever.
_CONTAINERS = ("sdt", "smartTag", "customXml", "dir", "bdo")


def container_source_text(xml_bytes, src_texts):
    """How many `w:t` INSIDE a container still carry text the SOURCE document had.

    THE CENSUS CANNOT ASK THIS, AND NEITHER CAN THE TEXT ARM. The census counts elements, and
    branch 7 changes neither the number of containers nor the number of w:t. The text arm
    compares a paragraph's whole text old against new, which does see the change — but it
    cannot say WHERE, and "some text moved" is not the same claim as "the source-language
    fragment that was stranded inside a content control is gone".

    THE ABSOLUTE NUMBER IS NOT THE MEASUREMENT; THE DELTA IS. A fragment inside a container
    can legitimately stay in the source language -- a defined term, a party name the operator
    chose not to translate, or a paragraph where `en == text` so apply skipped it entirely
    (11 such entries on the sdt document's own notes). Those are in both arms, so they cancel.
    Same attribution principle as C16's interior doubles: only the excess is anybody's fault.
    """
    root = etree.fromstring(xml_bytes)
    n = 0
    for p in root.iter(f"{{{W}}}p"):
        for child in p:
            if etree.QName(child).localname not in _CONTAINERS:
                continue
            for t in child.iter(f"{{{W}}}t"):
                if (t.text or "").strip() and (t.text or "").strip() in src_texts:
                    n += 1
    return n


def container_predictor(src_xml_bytes):
    """How many text-carrying INLINE containers the SOURCE document holds — computed, never
    read off a document list.

    Stronger than naming D03 and D05, for the reason the C17 predictor gives: it says WHERE
    as well as whether, and it keeps working on a document nobody has measured. A16's row
    names one document and one batch arm; the mechanism is in one branch of one classifier
    and applies to every document, so a container fixed on a document nobody measured is the
    row's evidence widening rather than an unexplained movement.

    Block containers are excluded, and that is the row's own measurement: 5 of the sdt
    document's 10 w:sdt wrap a whole paragraph, whose runs are direct children of their own
    w:p, so apply always rebuilt them correctly. They are the positive control, not the
    defect.
    """
    root = etree.fromstring(src_xml_bytes)
    hits = []
    for i, p in enumerate(root.iter(f"{{{W}}}p")):
        for child in p:
            if etree.QName(child).localname not in _CONTAINERS:
                continue
            if any((t.text or "").strip() for t in child.iter(f"{{{W}}}t")):
                hits.append(i)
                break
    return hits


def predictors(notes):
    """How many C17 instances this document's own notes predict, and C16's DECLARED baseline.

    A movement is only EXPLAINED if a row predicted it, and for C17 the prediction is
    computable from the notes rather than read off a document list -- which is stronger,
    because it says WHERE as well as whether.

      c17       a segment whose declared `en` is non-empty and all whitespace: the exact input
                `.strip()` truthiness could not tell from an explicit empty-string request.
      declared  interior double-space runs the operator AUTHORED in `en`. C16 is a claim that
                apply CREATES one, so a delivered double space the operator declared, or one
                the SOURCE already carried, is not C16's -- measured on D07, four of its
                delivered doubles are inherited from the source paragraph and three were
                declared. Attribution, not a total.
    """
    c17 = []
    for e in notes:
        for s in (e.get("en_segments") or []):
            v = s.get("en")
            if isinstance(v, str) and v != "" and v.strip() == "":
                c17.append(e.get("idx"))
                break
    declared = 0
    for e in notes:
        t = e.get("en") or ""
        for m in DOUBLE.finditer(t):
            if m.end() < len(t):
                declared += 1
    return c17, declared


def corpus_dirs():
    """WHERE THE PRISTINE SOURCES LIVE — read from config, never hardcoded, never printed.

    The run directories under the logs folder hold DELIVERABLES; CLAUDE.md 6.5 puts the
    11-document corpus in a separate sibling folder whose NAME is not committable. Measured
    2026-09-01: matching only inside the run directories reached 3 of 13 frozen intermediates,
    and the ten it missed include BOTH documents for A2 -- the fourteen unreachable comment
    anchors, a CRITICAL row. So the search is widened to the configured folders, and the
    folder name is read from gitignored .claude/evidence-dirs.local (plus LT_CORPUS_DIR) and
    used without ever being echoed.

    IN A FRESH CLONE THAT FILE DOES NOT EXIST, exactly as CLAUDE.md 5.4 says of the evidence
    guard. The real arm is then unavailable and this tool says so rather than reporting a
    smaller clean run.
    """
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
        # Only a directory that actually holds Word documents is a corpus candidate.
        if p.is_dir() and any(p.glob("*.docx")):
            out.append(p)
    return out


_TEXT_CACHE = {}


def _doc_texts(cand):
    """Paragraph texts of a .docx, cached. Never returned to a printer."""
    key = str(cand)
    if key not in _TEXT_CACHE:
        try:
            with zipfile.ZipFile(cand) as z:
                if "word/document.xml" not in z.namelist():
                    _TEXT_CACHE[key] = None
                else:
                    _TEXT_CACHE[key] = set(para_texts(z.read("word/document.xml")))
        except Exception:
            _TEXT_CACHE[key] = None
    return _TEXT_CACHE[key]


def pick_source_docx(wd, notes, extra_dirs):
    """WHICH .docx IS THIS RUN'S SOURCE — decided by measurement, not by name.

    Filenames in both the run directories and the corpus folder carry counterparty names, so
    they can never be read, printed or pattern-matched. But the SOURCE is the document whose
    paragraph text matches the notes' `text` field (source language) rather than its `en`
    field, and that IS measurable. Returns (path, matched_fraction); the fraction is printed
    so a poor match surfaces as VOID rather than passing as a comparison.

    The run directory is searched first: where a run kept its own copy of the source, that is
    the highest-fidelity input, and it cannot be confused with another document's.
    """
    wanted = {(e.get("text") or "").strip() for e in notes if (e.get("text") or "").strip()}
    if not wanted:
        return None, 0.0
    best, best_frac = None, 0.0
    for group in ([sorted(wd.glob("*.docx"))]
                  + [sorted(d.glob("*.docx")) for d in extra_dirs]):
        for cand in group:
            texts = _doc_texts(cand)
            if not texts:
                continue
            frac = len(wanted & texts) / len(wanted)
            if frac > best_frac:
                best, best_frac = cand, frac
        # A run-directory copy at a convincing match wins outright; do not widen the search
        # to eleven other documents when this run's own source is sitting right there.
        if best_frac >= 0.9:
            break
    return best, best_frac


def run_arm(scripts_dir, src_docx, notes_path, out_xml, label):
    """Run apply from the given scripts directory. Returns (xml_bytes | None, note)."""
    env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1",
               PYTHONDONTWRITEBYTECODE="1")
    p = subprocess.run(
        ["uv", "run", "--with", "lxml", "python", str(scripts_dir / SCRIPT),
         str(src_docx), str(notes_path), str(out_xml)],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        cwd=str(ROOT), env=env, timeout=1800)
    if not out_xml.exists():
        tail = (p.stderr or p.stdout or "").strip().splitlines()
        # Print only the LAST line, and only if it names a gate. Validator output on real
        # corpus data can quote document text.
        why = tail[-1][:120] if tail else "no output"
        return None, f"{label}: no output (rc={p.returncode}) — {why}"
    return out_xml.read_bytes(), f"{label}: rc={p.returncode}"


CORPUS = corpus_dirs()
# SAY WHAT WAS SEARCHED, WITHOUT SAYING WHERE. A control must report what it read, and a
# reachable-corpus count of 0 is the difference between "ten documents are clean" and "ten
# documents were never opened".
print(f"  corpus folder(s) reachable: {len(CORPUS)} · "
      f"{sum(len(list(d.glob('*.docx'))) for d in CORPUS)} .docx candidate(s), "
      f"{sum(len(list(d.glob('*.doc'))) for d in CORPUS)} legacy .doc (needs conversion, "
      f"not compared)")

docs_done, rows, unexplained, voided, text_rows, container_rows = [], [], [], [], [], []
wds = [w for w in (sorted(LOGS.rglob("wd")) + sorted(LOGS.rglob("wd-*"))) if w.is_dir()]
seen = {}
for wd in wds:
    doc = wd.name[3:] if wd.name.startswith("wd-") else wd.parent.name
    seen[doc] = seen.get(doc, 0) + 1
    label = doc if seen[doc] == 1 else f"{doc} #{seen[doc]}"
    if args.doc and doc not in args.doc:
        continue
    notes_src = wd / "paragraphs.json"
    if not notes_src.is_file():
        continue

    try:
        notes = json.loads(notes_src.read_text(encoding="utf-8"))
    except Exception as exc:
        voided.append(f"{label}: paragraphs.json unreadable ({type(exc).__name__})")
        continue
    src_docx, frac = pick_source_docx(wd, notes, CORPUS)
    if src_docx is None or frac < 0.5:
        voided.append(f"{label}: no source .docx matched the notes "
                      f"(best {frac:.0%} of {len(notes)} entries) — not compared")
        continue

    # COPY IN, NEVER WORK IN PLACE. apply writes .validate-state.json beside its input.
    work = TMP / label.replace(" ", "").replace("#", "n")
    (work / "in").mkdir(parents=True)
    shutil.copyfile(src_docx, work / "in" / "src.docx")
    for name in ("paragraphs.json", ".validate-state.json", "comments_translations.json",
                 "headers_footers.json", "_boldmap.json"):
        if (wd / name).is_file():
            shutil.copyfile(wd / name, work / "in" / name)
    # One independent copy per arm, so neither arm's state file can reach the other.
    arms = {}
    for arm, scripts_dir in (("old", OLDTREE),
                             ("new", ROOT / args.variant / "scripts")):
        adir = work / arm
        shutil.copytree(work / "in", adir)
        xml, note = run_arm(scripts_dir, adir / "src.docx", adir / "paragraphs.json",
                            adir / "out.xml", arm)
        arms[arm] = (xml, note)

    if arms["old"][0] is None or arms["new"][0] is None:
        voided.append(f"{label}: {arms['old'][1]} | {arms['new'][1]}")
        continue

    docs_done.append(label)
    # THE GROUND TRUTH IS THE SOURCE DOCUMENT, not the old output. Old-versus-new alone can
    # only say something changed; old-versus-new-versus-SOURCE says whether it changed in the
    # right direction, which is the whole question for a preservation fix.
    with zipfile.ZipFile(src_docx) as z:
        s = census(z.read("word/document.xml"))
    b, a = census(arms["old"][0]), census(arms["new"][0])
    moved = delta(b, a)
    ident = arms["old"][0] == arms["new"][0]
    print(f"\n  {label}  ({len(notes)} notes entries, source matched {frac:.0%})"
          f"{'   BYTE-IDENTICAL' if ident else ''}")
    if not moved:
        print("      no counted structure moved")
    for k, (bv, av) in sorted(moved.items()):
        row = ROW.get(k, "")
        sv = s.get(k, 0)
        if k in RESTORE:
            was, now = abs(bv - sv), abs(av - sv)
            if now == 0 and was != 0:
                verdict = f"RESTORED to source ({sv}) — {row or 'no row'}"
            elif now < was:
                verdict = f"closer to source ({sv}) — {row or 'no row'}"
            elif now > was:
                verdict = (f"AWAY FROM SOURCE ({sv}) — DEFECT until shown otherwise")
                unexplained.append(f"{label}/{k}: {bv} -> {av}, source {sv} ({verdict})")
            else:
                verdict = f"same distance from source ({sv}) — EXPLAIN"
                unexplained.append(f"{label}/{k}: {bv} -> {av}, source {sv} ({verdict})")
        elif k in PARTIAL:
            if av > sv:
                verdict = (f"ABOVE the source count ({sv}) — DEFECT until shown otherwise: "
                           "this branch never adds a tab")
                unexplained.append(f"{label}/{k}: {bv} -> {av}, source {sv} ({verdict})")
            elif av == sv:
                verdict = f"every tab placeable, and all {sv} restored — A3, in full here"
            else:
                verdict = (f"{sv - av} of {sv} not placeable, so DROPPED rather than stranded "
                           "— A3's deferral to branch 16; judge it on render_diff, not here")
        elif k in DELETE:
            if av < bv:
                verdict = (f"DELETED as redundant (source {sv}) — {row or 'no row'}; "
                           "clause 3: the number is already in the English")
            else:
                verdict = "MORE field structure than before — DEFECT until shown otherwise"
                unexplained.append(f"{label}/{k}: {bv} -> {av}, source {sv} ({verdict})")
        elif k in CONTAINED:
            # THE COUNT MUST HOLD AND THE CONTENTS MUST CHANGE. Branch 7 empties a container
            # of its source-language text; it never adds or removes one. So a moved COUNT is
            # a defect here exactly as it was under HOLD, and the contents are scored by the
            # CONTAINER arm below rather than by this number.
            verdict = ("COUNT MUST NOT MOVE — the fix empties a container, it never adds or "
                       "removes one; contents are the CONTAINER arm's")
            unexplained.append(f"{label}/{k}: {bv} -> {av}, source {sv} ({verdict})")
        elif k in HOLD:
            verdict = "MUST NOT MOVE — defect until shown otherwise"
            unexplained.append(f"{label}/{k}: {bv} -> {av}, source {sv} ({verdict})")
        elif k == "trailing_tabs" and av > bv:
            # NOT SCORED, BUT NOT DISMISSED EITHER. A rise here means tabs that were
            # DESTROYED are now preserved but sitting after the collapsed English rather
            # than between the fragments they separated -- the declared branch-16 deferral,
            # because one unbroken `en` string carries no offset saying where the tab
            # belonged. On D06 that is the 40 table-of-contents entries: the links work
            # again and every tab is back, and the entry text and its page number are still
            # not separated on the page. Say it, rather than let "not scored" hide it.
            verdict = (f"+{av - bv} tab(s) preserved-but-after-the-text (source {sv}) — "
                       "the DECLARED branch-16 deferral, not a loss")
        else:
            verdict = (f"structural, not scored (source {sv}) — CLAUDE.md 5.6: never score "
                       "a run property from element counts")
        print(f"      {k:<20} {bv:>6} -> {av:<6} src {sv:<6} {verdict}")

    # ---- THE TEXT ARM. Added for branch 6's fourth slice, because the census above is
    # structurally incapable of seeing what C16 and C17 change. ------------------------------
    changed, (di_old, dt_old), (di_new, dt_new) = text_delta(arms["old"][0], arms["new"][0])
    c17_idx, c16_declared = predictors(notes)
    # THE SOURCE'S OWN INTERIOR DOUBLES, because "apply CREATED it" is only true of a double
    # space the source did not already have. Measured on D07: four of its delivered doubles
    # sit in paragraphs whose SOURCE paragraph carried one, so they are INHERITED. Scoring
    # those against apply would credit this branch with a defect it never had and, worse,
    # would report a fix as having failed to remove something that was never its to remove.
    with zipfile.ZipFile(src_docx) as z:
        _src_doc_xml = z.read("word/document.xml")
    di_src, _ = _doubles(para_texts_raw(_src_doc_xml))
    n_moved = len([i for i in changed if i >= 0])

    # ---- THE CONTAINER ARM. Branch 7. --------------------------------------------------
    _src_texts = {t.strip() for t in
                  (x.text for x in etree.fromstring(_src_doc_xml).iter(f"{{{W}}}t"))
                  if t and t.strip()}
    cs_old = container_source_text(arms["old"][0], _src_texts)
    cs_new = container_source_text(arms["new"][0], _src_texts)
    cont_pred = container_predictor(_src_doc_xml)
    container_rows.append((label, len(cont_pred), cs_old, cs_new, ident))
    if cont_pred or cs_old or cs_new:
        print(f"      {'CONTAINER':<20} {cs_old:>6} -> {cs_new:<6} "
              f"source-language w:t inside a container; "
              f"{len(cont_pred)} text-carrying inline container(s) in the source"
              + (f" at idx {cont_pred[:8]}" if cont_pred else ""))
        if cs_new > cs_old:
            unexplained.append(
                f"{label}/CONTAINER: {cs_old} -> {cs_new} source-language fragments inside a "
                f"container — this branch only ever removes them, so a RISE is a defect")
        # AND THE OPPOSITE DIRECTION, WHICH "did anything move" CANNOT ASK. A document whose
        # SOURCE carries a text-carrying inline container, and whose stranded fragments did
        # NOT fall, means the fix did not fire where the measurement says it must — which
        # reads exactly like a clean run.
        #
        # `not SAME` GUARDS IT, AND THAT GUARD IS A DEFECT THIS RUN FOUND IN THIS FILE. On a
        # self-comparison old and new ARE the same code, so nothing can move and this check
        # was GUARANTEED to fire: the before-branch-7 baseline run printed the note saying an
        # all-quiet result proves nothing and then reported 2 MOVEMENTS NO REGISTER ROW
        # PREDICTS, from the C17 arm below, for exactly that reason. A harness that reports
        # two defects whenever it is asked to prove it reports none is not usable as evidence.
        if (cont_pred and cs_new >= cs_old and not SAME
                and not fix_in_baseline("CONTAINER")):
            unexplained.append(
                f"{label}/CONTAINER: the source carries {len(cont_pred)} text-carrying "
                f"inline container(s) at idx {cont_pred[:8]} and the stranded fragment count "
                f"did not fall ({cs_old} -> {cs_new}) — A16/N1's fix did not fire here")
    text_rows.append((label, n_moved, len(c17_idx), di_src, c16_declared,
                      di_old, di_new, dt_old, dt_new, ident))
    if -1 in changed:
        unexplained.append(f"{label}/paragraph count: old and new produced different numbers "
                           f"of paragraphs — this branch changes text, never structure count")
    if n_moved or c17_idx or di_old != di_new or dt_old != dt_new:
        pred = (f"{len(c17_idx)} C17 instance(s) predicted at idx {c17_idx}"
                if c17_idx else "no C17 instance predicted")
        print(f"      {'TEXT':<20} {n_moved:>6} paragraph(s) changed        {pred}")
        # ATTRIBUTED, NEVER TOTALLED. Only the excess over BOTH the source's own doubles and
        # the operator's declared ones can be attributed to apply.
        acct = max(0, di_old - max(di_src, c16_declared))
        acct_new = max(0, di_new - max(di_src, c16_declared))
        print(f"      {'interior doubles':<20} {di_old:>6} -> {di_new:<6} "
              f"src {di_src:<4} declared {c16_declared:<4} "
              + (f"C16: {acct} attributable to apply, now {acct_new}" if acct
                 else "none attributable to apply — inherited or declared, so not C16's"))
        print(f"      {'trailing ws paras':<20} {dt_old:>6} -> {dt_new:<6} "
              "(invisible on a page; counted so it cannot masquerade as an interior double)")
        # A MOVEMENT NO ROW PREDICTS IS A DEFECT — the same rule the census arm applies, and
        # it has to be applied here too or the text arm is a printout rather than a check.
        # AND THE PREDICTOR HAS TO KNOW ABOUT THE BRANCH THAT IS RUNNING, which the first
        # acceptance run of branch 7 proved by flagging the fix's own two documents. The text
        # arm was written for C16 and C17, so a paragraph whose text changed because a
        # stranded container fragment was FREED matched no predictor and was reported as
        # "nothing predicts this". It was predicted -- by the arm three lines below this one.
        # A per-branch arm added beside an older one has to be wired into the verdict too,
        # or every branch's acceptance run reports its own work as unexplained.
        if n_moved and not c17_idx and di_old == di_new and cs_new >= cs_old:
            unexplained.append(
                f"{label}/TEXT: {n_moved} paragraph(s) changed text with no C17 instance in "
                f"the notes, no change in interior double count and no container fragment "
                f"freed — nothing predicts this")
        # AND THE OPPOSITE DIRECTION, WHICH A "did anything move" CHECK CANNOT ASK: a document
        # the notes say carries C17 whose text did NOT move means the fix did not fire where
        # the evidence says it should. That reads as a clean run and is the more expensive
        # failure, because it is indistinguishable from success.
        # `not SAME` ADDED 2026-09-08, ON A MEASURED FALSE POSITIVE IN THIS VERY FILE. With
        # old and new the same code nothing CAN move, so this check fired on both C17
        # documents every time the harness was asked to demonstrate that it reports no
        # movement when there is none — the run printed its own NOTE saying an all-quiet
        # result proves nothing, and then two lines of "MOVEMENTS NO REGISTER ROW PREDICTS".
        # Two guaranteed defects, reading exactly like real ones. Same family as every other
        # entry in CLAUDE.md 5.16: the thing measured was not the thing under review.
        if c17_idx and not n_moved and not SAME and not fix_in_baseline("C17"):
            unexplained.append(
                f"{label}/TEXT: the notes carry {len(c17_idx)} C17 instance(s) at "
                f"{c17_idx} and NOT ONE paragraph's text moved — the fix did not fire where "
                f"the measurement says it must")
        elif c17_idx and not n_moved:
            print(f"      {'':<20} {'':>6} C17's fix is in the baseline "
                  f"({FIX_LANDED['C17']}), so both arms carry it and no movement is "
                  f"possible — the check is ANSWERED, not open")
    rows.append((label, moved))

print()
print("=" * 100)
# A CONTROL THAT OPENED NO FILES IS VOID, NEVER CLEAN.
if not docs_done:
    print("  VOID — not one document was compared. This is not a clean run.")
    for v in voided:
        print(f"      {v}")
    shutil.rmtree(TMP, ignore_errors=True)
    sys.exit(1)
moved_docs = [d for d, m in rows if m]
# THREE NUMBERS, NOT ONE, AND THE WORD "byte-quiet" NO LONGER MEANS "the census was quiet".
#
# THIS LINE USED TO READ `{n} moved · {m} byte-quiet` WITH BOTH DERIVED FROM THE CENSUS DELTA,
# and that is a mislabel with teeth: the census cannot see text, so a document whose delivered
# bytes had changed was counted and printed as byte-quiet. Branch 6's fourth slice would have
# reported 13 byte-quiet on a run that moved two documents. A number is only as good as the
# noun attached to it, and nothing checks a noun.
text_moved = [t[0] for t in text_rows if t[1]]
byte_identical = [t[0] for t in text_rows if t[9]]
# FOUR NUMBERS NOW, because the third arm answers a question the first two structurally
# cannot. Branch 7 changes neither an element count nor, on most documents, a paragraph's
# whole text — it removes a source-language fragment from inside a container. Counting the
# fragments is the only arm that can say it happened.
cont_freed = [c[0] for c in container_rows if c[3] < c[2]]
print(f"  {len(docs_done)} document(s) compared")
print(f"      {len(moved_docs):>3} moved a counted STRUCTURE   (the census arm)")
print(f"      {len(text_moved):>3} moved a paragraph's TEXT    (the text arm — C16, C17)")
print(f"      {len(cont_freed):>3} freed a stranded fragment  (the container arm — A16, N1)")
print(f"      {len(byte_identical):>3} byte-identical old vs new  (nothing changed at all, "
      f"and this is the only one of the four that means that)")
if text_rows:
    print()
    print(f"      {'doc':<10}{'txt moved':>10}{'C17':>5}{'int src':>9}{'int decl':>10}"
          f"{'int old':>9}{'int new':>9}{'trail old':>11}{'trail new':>11}")
    print("      " + "-" * 84)
    for t in text_rows:
        print(f"      {t[0]:<10}{t[1]:>10}{t[2]:>5}{t[3]:>9}{t[4]:>10}"
              f"{t[5]:>9}{t[6]:>9}{t[7]:>11}{t[8]:>11}")
    print("      " + "-" * 84)
    print("      int = INTERIOR double-space runs, the only kind a page can show. `src` is the")
    print("      SOURCE document's own; `decl` is what the operator authored in `en`. Only the")
    print("      excess over both is attributable to apply, which is what C16 claims.")
if container_rows:
    print()
    print(f"      {'doc':<10}{'inline containers':>19}{'stranded old':>14}"
          f"{'stranded new':>14}{'freed':>7}")
    print("      " + "-" * 64)
    for c in container_rows:
        print(f"      {c[0]:<10}{c[1]:>19}{c[2]:>14}{c[3]:>14}{c[2] - c[3]:>7}")
    print("      " + "-" * 64)
    print("      `inline containers` counts TEXT-CARRYING containers inside a w:p in the")
    print("      SOURCE — the prediction, computed rather than read off a document list. A")
    print("      BLOCK container is excluded and is the positive control: 5 of the sdt")
    print("      document's 10 wrap a whole paragraph and were always rebuilt correctly.")
    print("      `stranded` counts delivered w:t inside a container whose text the source")
    print("      also had. The ABSOLUTE number includes fragments that legitimately stay in")
    print("      the source language, so only the DELTA is attributable to this branch.")
if voided:
    print(f"  {len(voided)} NOT compared — VOID, not clean:")
    for v in voided:
        print(f"      {v}")
if SAME and moved_docs:
    print("  HARNESS DEFECT — the two arms are the same code and yet something moved.")
if unexplained:
    print(f"\n  {len(unexplained)} MOVEMENT(S) NO REGISTER ROW PREDICTS — each is a defect")
    print("  until shown otherwise, which is this branch's acceptance condition:")
    for u in unexplained:
        print(f"      {u}")
print("=" * 100)
shutil.rmtree(TMP, ignore_errors=True)
sys.exit(1 if (unexplained or (SAME and moved_docs)) else 0)
