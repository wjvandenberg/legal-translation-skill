# -*- coding: utf-8 -*-
"""BRANCH 9 — C15 and B6: the tidy-up script records every edit it makes.

WHAT THE ROWS SAY. C15: `validate_apply` joins `en_segments` with no separator before
tokenising while `post_process`'s spacing backstop inserts a space at exactly that seam, so
ONE validator invoked THREE times on ONE file gave TWO different opinions about it and the
block arrived at repack having passed at Steps 5 and 6. B6: `post_process` overrode a
lexicon-sanctioned choice and its own drift gate then blocked because `document.xml` no
longer matched `paragraphs.json` — THE OPERATOR IS SHOWN A DRIFT ERROR, NOT A TERMINOLOGY
ERROR, which points at the wrong diagnosis entirely.

WHY A JOURNAL AND NOT A FIX TO EITHER. PLAN-2-step-b.md section 6, Option 6: option 2's
character-exact comparison is IMPOSSIBLE while a mandatory script may rewrite the text after
the last comparison. Either the opinionated passes move upstream of the comparison, or the
stage must journal every change it makes so the comparison can account for exactly those and
nothing else. Branch 11 cannot be built at all until this exists.

AND IT REPLACES A SIMULATION WITH A RECORD. `validate_apply.py` already imports
`will_fix_spacing_fire` from `post_process` and PREDICTS what the spacing pass will do. That
is a correct answer to one pass's question and it does not generalise: there are thirteen
passes plus an auto-invoked strip, and predicting twelve more is twelve more things to drift.

THE TEXT CONTRACT, STATED ONCE AND DELIBERATELY (.claude/rules/verification.md rule 5). The
journal records text borne by `w:t` and `w:delText`, in document order, identified by FLAT
ORDINAL over the whole part and grouped into paragraphs by the skill's own nested-paragraph
rule (`_iter_own_runs` in translate_headers_footers.py). A flat ordinal is used because
`post_process`'s own passes group by `p.iter()`, which reaches INTO a nested paragraph, while
the skill's reading half does not — so a paragraph-keyed identity would have to pick one of
the two and would misattribute under the other. The flat enumeration is the same under both.

IT IS DECLARED BLIND TO NON-TEXT CHANGE, never silently blind: the italic strip removes
`w:i`, the page-break pass adds `pageBreakBefore`, and the spacing pass sets `xml:space`.
None of those is text and none is journalled as an edit. Each pass instead records its
element count before and after, so a structural change is VISIBLE as a count even though its
content is not recorded. Branch 11 diffs READINGS, which are text, so text is the contract it
needs; B1's and B7's formatting rows are branch 10's and are not closed here.

THE SECOND READER IS THE POINT OF THIS FILE. .claude/rules/verification.md rule 3: a reader
that normalises its input cannot see a change in what it normalised away, and the reader is
usually shared between the two sides of the comparison — the fix is a second reader, never a
changed one. `post_process` writes the journal from its OWN snapshot. Arm 3 below reads the
pre- and post- XML with a reader implemented HERE, from the stated contract, importing
nothing from the script it measures, and asserts the journal accounts for every difference.
Arm 4 then plants a defect in the journal and proves arm 3 goes red for it.

WHAT THIS SUITE CANNOT SEE, said before it is run rather than after.
  - tools/apply_corpus_diff.py drives apply and cannot see this branch at all. Worse, at the
    current pin apply is byte-identical to the working tree, so it prints its self-comparison
    notice and an all-quiet run there evidences nothing whatever.
  - ARM 6's PIN IS FIXED AT THE LAST COMMIT BEFORE THE JOURNAL EXISTED, and the block above
    it says why: moved forward at the close, as the other pins correctly are, it reports VOID
    for ever. It was moved once, measured, and moved back in the same session.
  - tools/render_diff.py has NO PAGE for this branch. Nothing delivered changes, so there is
    nothing to render; manufacturing a visual arm would be theatre.
  - The real-corpus completeness answer is tools/postprocess_corpus_arm.py's, not this
    file's. Synthetic inputs cannot prove a journal complete over documents nobody wrote for
    the test.

    uv run --with lxml python tests/test_change_journal.py
    uv run --with lxml python tests/test_change_journal.py --variant us
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

from lxml import etree

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.dont_write_bytecode = True
os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")

ROOT = Path(__file__).resolve().parent.parent
W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"

ap = argparse.ArgumentParser()
ap.add_argument("--variant", default="uk", choices=("uk", "us"))
ap.add_argument("--keep", action="store_true")
args = ap.parse_args()
SCRIPTS = ROOT / args.variant / "scripts"

# A FIXED PIN, NOT A MOVING ONE, AND IT WAS MOVED ONCE BY MISTAKE BEFORE THIS BLOCK EXISTED.
#
# 18a0798 is THE LAST COMMIT BEFORE THE CHANGE JOURNAL EXISTED, and that is the whole point.
# Arm 6 asks one question: does post_process WITH the journal produce a document.xml
# byte-identical to post_process WITHOUT it? That question only exists against a tree that
# predates the journal. Branch 9's close mechanically moved this to its own squash-merge
# along with the three tools that genuinely move, and the result was measured immediately:
# the baseline became this file's own code, the self-comparison guard fired correctly, and
# arm 6 reported `VOID — nothing to compare` on every run, for ever. A check that can only
# report VOID is not a check, and a permanently-void row is one people learn to scroll past.
#
# SO IT FOLLOWS tools/hf_corpus_diff.py's PRECEDENT rather than apply_corpus_diff.py's, and
# it is the FIFTH fixed pin in this repository: test_no_delivered_byte_moves.py,
# test_check_scoping.py and test_check_scoping_properties.py all pin to 2178cce, and
# hf_corpus_diff.py to ae48f6d, every one of them for this same reason.
#
# WHEN TO MOVE IT, AND IT IS NOT AT A CLOSE. Move it only when a future branch LEGITIMATELY
# changes what post_process writes for a real document — branch 10, the tidy-up split, is
# the first such branch, and there the bytes MUST move, so arm 6 goes red and whoever moved
# them records why and re-pins here in the same commit. Until then a close that mechanically
# "moves the pins" must leave this one alone.
REF = os.environ.get("LT_BASELINE_REF", "18a0798")

FAIL, CHECKED, VOIDED = [], 0, []
TMP = Path(tempfile.mkdtemp(prefix="b9-journal-"))
ENV = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1",
           PYTHONDONTWRITEBYTECODE="1")

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
    """A check that could not establish anything is VOID, never a pass. CLAUDE.md 5.3."""
    VOIDED.append(f"{label}: {why}")
    print(f"  ??   {label}   VOID — {why}")


def run(argv, timeout=900, scripts_dir=None):
    return subprocess.run(["uv", "run", "--with", "lxml", "python"]
                          + [str(a) for a in argv],
                          capture_output=True, text=True, encoding="utf-8",
                          errors="replace", cwd=str(scripts_dir or ROOT), env=ENV,
                          timeout=timeout)


# =========================================================================================
# THE SECOND READER. Implemented from the contract in the docstring, importing NOTHING from
# post_process.py. If this file ever imports the script it measures, delete the import: an
# instrument that shares its subject's reader shares its subject's blind spots, which is the
# defect branch 8 spent a whole slice on.
# =========================================================================================
TEXT_TAGS = (f"{{{W}}}t", f"{{{W}}}delText")


def flat_texts(xml_bytes):
    """Every text-bearing element's text, in document order, as a flat list.

    The identity the journal uses. Position in this list IS the element's id.
    """
    root = etree.fromstring(xml_bytes)
    return [(e.tag, e.text or "") for e in root.iter() if e.tag in TEXT_TAGS]


def own_paragraph_texts(xml_bytes):
    """Paragraph text under the skill's own nested-paragraph rule.

    Reimplemented here rather than imported — `_iter_own_runs` lives in
    translate_headers_footers.py and this tool must not share a reader with the tree.
    """
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


# =========================================================================================
# SYNTHETIC INPUTS. Built here rather than added to tests/fixtures/, deliberately: a 26th
# fixture moves tools/audit_branches.py's B1.fixtures count, which reads the INDEX, and this
# branch has no need of a .docx container — post_process takes a raw document.xml path.
# Every string is invented. There is no client text in this file.
# =========================================================================================
def doc(paragraphs):
    """paragraphs :: list of list of (tag, text). Builds one w:p per entry."""
    body = []
    for runs in paragraphs:
        cells = "".join(
            f'<w:r><w:{tag} xml:space="preserve">{text}</w:{tag}></w:r>'
            for tag, text in runs)
        body.append(f"<w:p>{cells}</w:p>")
    return ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
            f'<w:document xmlns:w="{W}"><w:body>'
            + "".join(body) +
            "</w:body></w:document>").encode("utf-8")


# Paragraph 0 trips the Annex rewrite; 3 the double-punctuation collapse; 4 the spacing
# backstop across an element seam, which is C15's own mechanism; 5 is the negative control
# INSIDE the document and no pass in either variant may touch it.
#
# ONE SPELLING PARAGRAPH PER VARIANT, and the second one is here because the first version
# of this input carried only the US-to-UK direction. Under `--variant us` that paragraph is
# already correct, the spelling pass does nothing, and the suite failed for a reason that
# was true of the TEST rather than of the journal — a hardcoded "four passes" asserted
# against a document that trips four in one tree and three in the other. Paragraph 1 moves
# under uk only and paragraph 2 under us only, so the count is four either way.
CONTROL_PARA = 5
PASSES_DOC = doc([
    [("t", "Annex 1 sets out the delivery milestones.")],
    [("t", "The steering committee shall authorize each drawdown.")],
    [("t", "The organisation shall recognise the transfer.")],
    [("t", "Definitions::")],
    [("t", "the"), ("t", "Facility")],
    [("t", "This sentence is already correct and must not move.")],
])

# A tracked-change document whose del/ins pair carries IDENTICAL English — the no-op the
# auto-strip exists to collapse. It is what makes strip_noop run at all.
TC_DOC = doc([
    [("t", "The completion date is fixed.")],
])
TC_DOC = TC_DOC.replace(
    b"<w:p><w:r><w:t xml:space=\"preserve\">The completion date is fixed.</w:t></w:r></w:p>",
    ('<w:p>'
     '<w:r><w:t xml:space="preserve">The completion date </w:t></w:r>'
     '<w:del w:id="1" w:author="A"><w:r><w:delText xml:space="preserve">is fixed</w:delText></w:r></w:del>'
     '<w:ins w:id="2" w:author="A"><w:r><w:t xml:space="preserve">is fixed</w:t></w:r></w:ins>'
     '<w:r><w:t xml:space="preserve">.</w:t></w:r>'
     '</w:p>').encode("utf-8"))


def stage(name, xml_bytes):
    """A workdir laid out the way skill-docs/06 tells the operator to lay one out.

    NEVER writes into tests/fixtures/. post_process writes a journal beside paragraphs.json
    and strip_noop rewrites document.xml in place; pointing either at the fixtures directory
    is how a run-state file reached the git index once and broke `git switch`.
    """
    d = TMP / name
    (d / "final" / "word").mkdir(parents=True, exist_ok=True)
    x = d / "final" / "word" / "document.xml"
    x.write_bytes(xml_bytes)
    return d, x


def journal_of(workdir):
    p = workdir / JOURNAL_NAME
    if not p.is_file():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return None


def owner_map(xml_bytes):
    """Flat ordinal -> index of the paragraph that owns that element, nearest ancestor.

    Reimplemented from the contract, not imported. Walking UP is what makes it nearest:
    iterating paragraphs downwards finds the OUTER one first.
    """
    root = etree.fromstring(xml_bytes)
    p_tag = f"{{{W}}}p"
    paragraphs = list(root.iter(p_tag))
    p_index = {id(p): i for i, p in enumerate(paragraphs)}
    out = []
    for e in root.iter():
        if e.tag not in TEXT_TAGS:
            continue
        a = e.getparent()
        while a is not None and a.tag != p_tag:
            a = a.getparent()
        out.append(None if a is None else p_index.get(id(a)))
    return out


def replay(before_xml, before_paras, jrnl):
    """Apply the journal to the BEFORE state and return the paragraph texts it predicts.

    This is what branch 11 will do: account for exactly the stage's declared changes and
    nothing else. Returns (predicted_paragraphs, error_or_None).

    THE ELEMENT RECORD IS WHAT DRIVES THE PREDICTION, and this is the point. The first
    version of this function replayed the PARAGRAPH record and merely walked the element
    record without using it, so removing an edit changed nothing and the positive control
    below could not fail. It was decorative and read as load-bearing. Now the paragraph
    prediction is DERIVED from the element replay, and the journal's own paragraph record
    is a cross-check against it rather than a substitute for it.
    """
    flat = [t for _tag, t in flat_texts(before_xml)]
    owners = owner_map(before_xml)
    paras = list(before_paras)
    for st in jrnl.get("stages", []):
        if st.get("stage") == "passes":
            for e in st.get("edits", []):
                i = e.get("elem")
                if not isinstance(i, int) or not (0 <= i < len(flat)):
                    return None, f"edit names element {i}, out of range 0..{len(flat) - 1}"
                if flat[i] != e.get("before"):
                    return None, f"element {i} before-text does not match the document"
                if e.get("para") != owners[i]:
                    return None, (f"edit on element {i} says paragraph {e.get('para')}, "
                                  f"the document says {owners[i]}")
                flat[i] = e.get("after")
            # Regroup the replayed elements into paragraphs, using the document's own
            # ownership. This is the prediction.
            rebuilt = {}
            for i, txt in enumerate(flat):
                if owners[i] is not None:
                    rebuilt.setdefault(owners[i], []).append(txt)
            for p_idx, parts in rebuilt.items():
                if 0 <= p_idx < len(paras):
                    paras[p_idx] = "".join(parts)
            # CROSS-CHECK, not a second chance: the journal's paragraph record must AGREE
            # with what its own element record predicts. Two accounts of one stage that
            # disagree mean the journal is internally inconsistent, which is worse than
            # incomplete because it looks complete.
            for pr in st.get("paragraphs", []):
                i = pr.get("para")
                if not isinstance(i, int) or not (0 <= i < len(paras)):
                    return None, f"paragraph record names {i}, out of range"
                if paras[i] != pr.get("after"):
                    return None, (f"paragraph {i}: the element record predicts one text "
                                  f"and the paragraph record claims another")
        else:
            for pr in st.get("paragraphs", []):
                i = pr.get("para")
                if not isinstance(i, int) or not (0 <= i < len(paras)):
                    return None, f"paragraph record names {i}, out of range"
                if paras[i] != pr.get("before"):
                    return None, f"{st.get('stage')} paragraph {i} before-text mismatch"
                paras[i] = pr.get("after")
    return paras, None


# =========================================================================================
# ARM 1 — THE JOURNAL IS WRITTEN, IN THE CONVENTIONAL PLACE, AND NOT WHERE REPACK LOOKS.
# =========================================================================================
print(f"ARM 1 — the journal is written to <workdir>/, never into final/   [{args.variant}]")
d1, x1 = stage("passes", PASSES_DOC)
r1 = run([SCRIPTS / "post_process.py", x1, "--fix", "--variant", args.variant])
j1 = journal_of(d1)
ok("post_process exits 0 on a clean synthetic input", r1.returncode == 0,
   f"rc={r1.returncode} {(r1.stderr or '')[-300:]}")
ok(f"{JOURNAL_NAME} exists at <workdir>/", j1 is not None,
   f"looked in {d1}")
ok("the journal is NOT inside final/word/, where repack substitutes parts",
   not (d1 / "final" / "word" / JOURNAL_NAME).is_file()
   and not (d1 / "final" / JOURNAL_NAME).is_file())

if j1 is None:
    print("\n" + "=" * 92)
    print("  ARMS 2-6 CANNOT RUN — there is no journal to read. That is this suite's RED.")
    print("=" * 92)
    for f in FAIL:
        print(f"    FAIL  {f}")
    shutil.rmtree(TMP, ignore_errors=True)
    sys.exit(1)

# =========================================================================================
# ARM 2 — THE SCHEMA SAYS WHAT IT COVERS AND NAMES A REAL PASS FOR EVERY EDIT.
# A journal whose entries are attributed to nothing is exactly B6's defect in a new file.
# =========================================================================================
print("\nARM 2 — the journal declares its contract and attributes every edit")
ok("it carries a schema id", isinstance(j1.get("schema"), str) and j1["schema"],
   repr(j1.get("schema")))
ok("it states its text contract in the artefact, not only in the source",
   isinstance(j1.get("text_contract"), str) and "delText" in (j1.get("text_contract") or ""),
   repr(j1.get("text_contract"))[:120])
ok("it names the variant it ran as", j1.get("variant") == args.variant,
   repr(j1.get("variant")))

pass_stage = next((s for s in j1.get("stages", []) if s.get("stage") == "passes"), None)
ok("there is a `passes` stage", pass_stage is not None)
edits = (pass_stage or {}).get("edits", [])
ok("it recorded at least one edit on an input built to trip four passes", len(edits) >= 4,
   f"edits={len(edits)}")
named = {e.get("pass") for e in edits}
ok("every edit names a pass", all(isinstance(e.get("pass"), str) and e["pass"]
                                  for e in edits), f"names={sorted(named)}")
ok("every edit locates itself in a PARAGRAPH, not only at a flat ordinal",
   bool(edits) and all(isinstance(e.get("para"), int) for e in edits),
   f"without-para={[e.get('elem') for e in edits if not isinstance(e.get('para'), int)]}")
counts = (pass_stage or {}).get("counts", [])
ok("every pass reports its element count before and after, so non-text change is VISIBLE",
   bool(counts) and all({"pass", "elements_before", "elements_after"} <= set(c)
                        for c in counts), f"counts={len(counts)}")
ok("the passes the edits name are all passes the run actually reported",
   named <= {c.get("pass") for c in counts},
   f"unknown={sorted(named - {c.get('pass') for c in counts})}")

# =========================================================================================
# ARM 3 — COMPLETENESS, READ BY THE SECOND READER. This is the arm branch 11 depends on.
# =========================================================================================
print("\nARM 3 — the journal accounts for EVERY text change, read independently")
before_flat = flat_texts(PASSES_DOC)
before_paras = own_paragraph_texts(PASSES_DOC)
after_paras = own_paragraph_texts(x1.read_bytes())

ok("the pass did change the document, so this arm has something to answer",
   before_paras != after_paras,
   "before and after are identical — the input tripped no pass and the arm is VOID")

moved = {i for i, (b, a) in enumerate(zip(before_paras, after_paras)) if b != a}
claimed = {pr.get("para") for st in j1.get("stages", [])
           for pr in st.get("paragraphs", [])}
ok("the journal claims exactly the paragraphs that moved, no more and no fewer",
   moved == claimed, f"moved={sorted(moved)} claimed={sorted(claimed)}")

predicted, err = replay(PASSES_DOC, before_paras, j1)
ok("replaying the journal onto the BEFORE reproduces the AFTER exactly",
   err is None and predicted == after_paras,
   err or f"first divergence at paragraph "
          f"{next((i for i, (p, a) in enumerate(zip(predicted or [], after_paras)) if p != a), '?')}")

ok("the untouched control paragraph is NOT claimed", CONTROL_PARA not in claimed,
   "the journal claims a paragraph no pass may touch")
ok("post_process's own self-check agrees it accounted for everything",
   (j1.get("self_check") or {}).get("accounted") is True,
   repr(j1.get("self_check")))

# THE DECLARED BLINDNESS MUST BE A FIGURE IN THE ARTEFACT, NOT ONLY A SENTENCE IN THE
# SOURCE — and this arm exists because the real corpus produced the case. On one frozen
# intermediate post_process reported TOTAL 2 fixes, the journal recorded 0 edits, and the
# self-check said `accounted: true`. Every one of those is correct under the text contract
# and together they read as "this stage changed nothing", which is false: two formatting
# changes had been made. `non_text_fixes` is what turns a silent blind spot into a number.
print("\nARM 3b — a change the contract does NOT cover is REPORTED as a figure")
sc = j1.get("self_check") or {}
ok("self_check carries a non_text_fixes list, present even when empty",
   isinstance(sc.get("non_text_fixes"), list), repr(sc.get("non_text_fixes")))
ok("every pass reports its OWN fix count beside the element counts",
   bool(counts) and all(isinstance(c.get("fixes"), int) for c in counts),
   f"without-fixes={[c.get('pass') for c in counts if not isinstance(c.get('fixes'), int)]}")
# The figure must be DERIVED, not decorative: a pass reporting fixes with no text edit
# recorded is exactly what it must name. Synthesised here because this input trips only
# text passes, so the real case cannot be reached from a synthetic document that also
# keeps arm 3 meaningful.
_probe = {"pass_counts": [{"pass": "spurious_italic", "fixes": 2,
                           "elements_before": 10, "elements_after": 8}],
          "pass_edits": []}
_derived = [{"pass": c["pass"], "fixes": c["fixes"]} for c in _probe["pass_counts"]
            if c["fixes"] and not any(e["pass"] == c["pass"] for e in _probe["pass_edits"])]
ok("and the rule that derives it names a fixes-without-text pass",
   _derived == [{"pass": "spurious_italic", "fixes": 2}], repr(_derived))

# =========================================================================================
# ARM 4 — THE POSITIVE CONTROL. Remove one recorded edit and prove ARM 3 goes RED for it.
# A completeness check that has never failed is not known to be able to.
# =========================================================================================
print("\nARM 4 — the positive control: a journal with one entry removed must FAIL arm 3")
if not edits:
    void("positive control", "no edits were recorded, so none can be removed")
else:
    holed = json.loads(json.dumps(j1))
    hole_stage = next(s for s in holed["stages"] if s.get("stage") == "passes")
    dropped = hole_stage["edits"].pop()
    dropped_para = dropped.get("para")
    hole_stage["paragraphs"] = [p for p in hole_stage.get("paragraphs", [])
                                if p.get("para") != dropped_para]
    pred2, err2 = replay(PASSES_DOC, before_paras, holed)
    ok("with one edit removed, the replay NO LONGER reproduces the after",
       err2 is not None or pred2 != after_paras,
       "the holed journal still reproduced the document — arm 3 cannot fail")
    claimed2 = {pr.get("para") for st in holed["stages"]
                for pr in st.get("paragraphs", [])}
    ok("and the moved-versus-claimed comparison also catches it", moved != claimed2,
       f"moved={sorted(moved)} claimed={sorted(claimed2)}")

# =========================================================================================
# ARM 5 — strip_noop IS JOURNALLED. It runs INSIDE post_process and it DELETES content
# (row B3 — bracket-only tracked changes on a real delivered contract), so branch 11 would
# see its deletions as unexplained difference. Wouter, 2026-09-22: cover it.
# =========================================================================================
print("\nARM 5 — the auto-invoked strip pass is journalled too")
d2, x2 = stage("tc", TC_DOC)
r2 = run([SCRIPTS / "post_process.py", x2, "--fix", "--variant", args.variant])
j2 = journal_of(d2)
ok("post_process exits 0 on the tracked-change input", r2.returncode == 0,
   f"rc={r2.returncode} {(r2.stderr or '')[-300:]}")
if j2 is None:
    void("strip journal", "no journal was written for the tracked-change input")
else:
    strip_stage = next((s for s in j2.get("stages", [])
                        if s.get("stage") == "strip_noop_tracked_changes"), None)
    ok("there is a strip stage in the journal", strip_stage is not None,
       f"stages={[s.get('stage') for s in j2.get('stages', [])]}")
    ok("it says whether the strip actually ran",
       isinstance((strip_stage or {}).get("ran"), bool))
    b2 = own_paragraph_texts(TC_DOC)
    a2 = own_paragraph_texts(x2.read_bytes())
    if b2 == a2:
        void("strip completeness", "the strip changed no text on this input")
    else:
        p2, e2 = replay(TC_DOC, b2, j2)
        ok("replaying the journal reproduces the stripped document",
           e2 is None and p2 == a2, e2 or "replay did not reproduce the after")

# =========================================================================================
# ARM 6 — NOT ONE DELIVERED BYTE MOVES. Branch 9 is ADDITIVE (section 2's branch table;
# Wouter 2026-09-22 declined the re-grade on that ground), so the acceptance is the OPPOSITE
# of branch 6's and 7's: document.xml must come out byte-identical to the pinned baseline's.
# =========================================================================================
print(f"\nARM 6 — document.xml is byte-identical to post_process at {REF}")
blob = subprocess.run(["git", "show", f"{REF}:{args.variant}/scripts/post_process.py"],
                      capture_output=True, cwd=str(ROOT))
cur = (SCRIPTS / "post_process.py").read_bytes()
if blob.returncode != 0:
    void("byte identity", f"cannot read post_process.py at {REF}")
elif blob.stdout == cur:
    # rule 1 of .claude/rules/verification.md: a self-comparison is VOID, never a pass.
    void("byte identity", f"post_process.py is BYTE-IDENTICAL to {REF} — nothing to compare")
elif b"\n# === SKILL FILE COMPLETE ===" not in blob.stdout:
    void("byte identity", "the baseline blob has no integrity sentinel; it would exit 3")
else:
    old_dir = TMP / "baseline-scripts"
    old_dir.mkdir(parents=True, exist_ok=True)
    (old_dir / "post_process.py").write_bytes(blob.stdout)
    d3, x3 = stage("new-arm", PASSES_DOC)
    d4, x4 = stage("old-arm", PASSES_DOC)
    rn = run([SCRIPTS / "post_process.py", x3, "--fix", "--variant", args.variant])
    ro = run([old_dir / "post_process.py", x4, "--fix", "--variant", args.variant])
    ok("both arms exit 0", rn.returncode == 0 and ro.returncode == 0,
       f"new={rn.returncode} old={ro.returncode}")
    nb, obb = x3.read_bytes(), x4.read_bytes()
    ok("document.xml is byte-identical between the two arms", nb == obb,
       f"new={hashlib.sha256(nb).hexdigest()[:12]} "
       f"old={hashlib.sha256(obb).hexdigest()[:12]} ({len(nb)} vs {len(obb)} bytes)")
    ok("the baseline arm wrote NO journal, so the arm is measuring a real difference",
       not (d4 / JOURNAL_NAME).is_file())

# =========================================================================================
# ARM 7 — BOTH TREES CARRY IT. A fix that lands in one variant and is forgotten in the other
# has shipped to a client before.
# =========================================================================================
print("\nARM 7 — the journal exists in BOTH trees and its block is byte-identical")
uk_src = (ROOT / "uk" / "scripts" / "post_process.py").read_text(encoding="utf-8")
us_src = (ROOT / "us" / "scripts" / "post_process.py").read_text(encoding="utf-8")
OPEN, CLOSE = "# === CHANGE JOURNAL ===", "# === CHANGE JOURNAL ENDS ==="
ok("uk carries the journal block", OPEN in uk_src and CLOSE in uk_src)
ok("us carries the journal block", OPEN in us_src and CLOSE in us_src)
if OPEN in uk_src and OPEN in us_src and CLOSE in uk_src and CLOSE in us_src:
    ukb = uk_src[uk_src.index(OPEN):uk_src.index(CLOSE)]
    usb = us_src[us_src.index(OPEN):us_src.index(CLOSE)]
    ok("the two copies are byte-identical", ukb == usb,
       f"uk={len(ukb)} us={len(usb)}")

# =========================================================================================
# ARM 8 — B6's OWN SITUATION, END TO END. This is the row's acceptance test and it is the
# reason the journal is written BEFORE the drift gate rather than after it.
#
# B6: post_process overrode a lexicon-sanctioned choice, the post-strip drift gate then
# blocked because document.xml no longer matched paragraphs.json, and THE OPERATOR WAS SHOWN
# A DRIFT ERROR RATHER THAN A TERMINOLOGY ERROR — a diagnosis pointing at the wrong file. The
# gate cannot tell the two apart and says so in its own banner. What was missing was any
# instrument that could.
#
# So: declare text, let a pass rewrite it, let the gate fire, and require that (a) the
# journal is on disk despite the raise, (b) it NAMES the pass that moved the text, and (c)
# the banner sends the operator to it. If the journal were written after the gate, or the
# banner never mentioned it, the operator would be exactly where B6 left them.
# =========================================================================================
print("\nARM 8 — B6: when the drift gate fires, is the right diagnosis available?")
d5, x5 = stage("b6", PASSES_DOC)
r_extract = run([SCRIPTS / "extract_paragraphs.py", x5, d5 / "paragraphs.json"])
if not (d5 / "paragraphs.json").is_file():
    void("B6 end-to-end", f"could not produce notes (rc={r_extract.returncode})")
else:
    notes = json.loads((d5 / "paragraphs.json").read_text(encoding="utf-8"))
    # Declare the English exactly as it stands BEFORE the stage runs. That is what an
    # operator's notes hold, and it is what the rewrite then contradicts.
    for e in notes:
        e["en"] = e.get("text", "")
    (d5 / "paragraphs.json").write_bytes(
        (json.dumps(notes, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    r5 = run([SCRIPTS / "post_process.py", x5, "--fix", "--variant", args.variant])
    blob5 = (r5.stdout or "") + (r5.stderr or "")
    ok("the drift gate FIRES — the declared text and the document now disagree",
       r5.returncode != 0,
       "the gate did not fire, so this arm is not exercising B6's situation")
    j5 = journal_of(d5)
    ok("the journal is on disk ANYWAY, because it is written before the gate raises",
       j5 is not None, "the gate raised first and the operator has no diagnosis")
    if j5 is not None:
        moved_by = {e.get("pass") for st in j5.get("stages", [])
                    for e in st.get("edits", [])}
        ok("and it NAMES the pass that moved the text — the diagnosis B6 says is missing",
           bool(moved_by), f"passes named: {sorted(moved_by)}")
        claimed5 = {r.get("para") for st in j5.get("stages", [])
                    for r in st.get("paragraphs", [])}
        ok("the paragraph the gate is complaining about is one the journal claims",
           bool(claimed5), f"claimed={sorted(claimed5)}")
    ok("the gate's own message sends the operator to the journal by name",
       JOURNAL_NAME in blob5,
       "the banner offers three possibilities and no instrument to tell them apart")
    ok("and it still carries the three-possibility framing the rule-5b probe bought",
       "WORK OUT WHICH OF THREE THINGS IS WRONG" in blob5)

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
