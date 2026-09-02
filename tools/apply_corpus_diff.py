# -*- coding: utf-8 -*-
"""BRANCH 6's ACCEPTANCE INSTRUMENT — what apply does DIFFERENTLY, on the real corpus.

THIS BRANCH'S ACCEPTANCE CONDITION IS THE OPPOSITE OF EVERY BRANCH BEFORE IT. Branches 0-5
and branch 14's slice each proved that no delivered byte moved. Branch 6 is the first fix
branch that CHANGES a delivered document, so "nothing moved" would mean it had failed. The
condition is instead:

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
# MOVED TO d3c7f19 2026-09-02, the squash-merge of branch 6 slice 4 (PR #62) and the LAST
# COMMIT THAT TOUCHED EITHER TREE -- verified by `git log --oneline -1 -- uk us` returning it
# and by `git diff d3c7f19 -- uk us` coming back empty, not by reading the merge message. A pin
# left at the previous baseline would report the merged slice's own work as movement belonging
# to whatever branch ran next, which is the failure this pin exists to prevent.
#
# IT HAS NOW MOVED FOUR TIMES IN THREE DAYS -- 4a1c452, 049484e, 2a71e71, here -- and that
# cadence IS the argument for the rule: moving it is the FIRST act after a merge, never a
# closing tidy-up.
#
# AND THE PROSE ABOVE THE PIN GOES STALE TOO, WHICH IS WHY IT IS REWRITTEN RATHER THAN APPENDED
# TO. This has now happened twice and been caught twice. The first time it still named 79a8c14
# as "the merge-base of this branch". The second time -- found on this very commit -- the same
# comment block in tools/render_diff.py read "Moved to 049484e" while its pin one line below
# said 2a71e71, so the two disagreed with each other inside five lines. NOTHING CHECKS A
# COMMENT. Re-derive both claims on the commit that moves the pin.
REF = os.environ.get("LT_BASELINE_REF", "d3c7f19")

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
HOLD = ("tab_stops", "sdt", "smartTag", "lastRenderedPageBreak")
REPORT = ("r", "p", "t", "delText", "ins", "del", "trailing_tabs", "br_plain")

ap = argparse.ArgumentParser()
ap.add_argument("--variant", default="uk", choices=("uk", "us"))
ap.add_argument("--doc", action="append", help="limit to these corpus doc-ids")
ap.add_argument("--ref", default=REF, help="baseline commit to compare against")
args = ap.parse_args()

print("=" * 100)
print(f"BRANCH 6 — APPLY, BEFORE AND AFTER, ON THE FROZEN INTERMEDIATES  ({args.variant})")
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

docs_done, rows, unexplained, voided, text_rows = [], [], [], [], []
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
        di_src, _ = _doubles(para_texts_raw(z.read("word/document.xml")))
    n_moved = len([i for i in changed if i >= 0])
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
        if n_moved and not c17_idx and di_old == di_new:
            unexplained.append(
                f"{label}/TEXT: {n_moved} paragraph(s) changed text with no C17 instance in "
                f"the notes and no change in interior double count — nothing predicts this")
        # AND THE OPPOSITE DIRECTION, WHICH A "did anything move" CHECK CANNOT ASK: a document
        # the notes say carries C17 whose text did NOT move means the fix did not fire where
        # the evidence says it should. That reads as a clean run and is the more expensive
        # failure, because it is indistinguishable from success.
        if c17_idx and not n_moved:
            unexplained.append(
                f"{label}/TEXT: the notes carry {len(c17_idx)} C17 instance(s) at "
                f"{c17_idx} and NOT ONE paragraph's text moved — the fix did not fire where "
                f"the measurement says it must")
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
print(f"  {len(docs_done)} document(s) compared")
print(f"      {len(moved_docs):>3} moved a counted STRUCTURE   (the census arm)")
print(f"      {len(text_moved):>3} moved a paragraph's TEXT    (the text arm — C16, C17)")
print(f"      {len(byte_identical):>3} byte-identical old vs new  (nothing changed at all, "
      f"and this is the only one of the three that means that)")
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
