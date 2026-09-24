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
import re
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
#
# THAT BRANCH HAS NOW ARRIVED, AND THE PIN MOVED ONCE, IN THE COMMIT THAT MOVED THE BYTES.
# Slice 2 makes four passes conditional (B4, B3, B2, B8), so `post_process` deliberately
# writes a DIFFERENT document.xml than it did before. The prediction above was measured
# exactly right: arm 6 went red on the first run, at 790 bytes against 789.
#
# **AND THE ARM'S QUESTION CHANGED WITH IT, WHICH MATTERS MORE THAN THE SHA.** Re-pinning
# alone would have left an arm asserting BYTE IDENTITY across a branch whose whole purpose is
# to break it — a check that can only fail is worth no more than one that can only pass. So
# the assertion below is INVERTED: the bytes must MOVE, and every movement must be claimed by
# the journal. Arm 3 already proves the claim is complete; this arm proves there was
# something to claim. Nothing is weakened — the two together are strictly stronger than byte
# identity, which could be satisfied by a pass that did nothing at all.
#
# 5107aaf is the squash-merge of slice 1 and the last commit before slice 2 to touch either
# tree — `git log --oneline -1 -- uk us` at that point returns it.
#
# AND IT DID NOT MOVE AGAIN AT SLICE 2's CLOSE, WHICH IS A DIFFERENT ANSWER FROM "IT IS A
# FIXED PIN" AND IS MEASURED RATHER THAN ARGUED. The three tool pins move to the merge of
# whatever last touched the tree, so they sit on their own baseline between branches and
# report a self-comparison notice. THIS ARM CANNOT DO THAT: a self-comparison here is VOID,
# and this suite exits non-zero on a void. Measured on the merge commit, both ways —
#
#     pin left at 5107aaf   rc=0, 72 checks, arm 6 green
#     pin moved to fd98ec2  rc=1, 69 checks + 1 VOID, and red on every run on `main`
#                           until slice 3 lands
#
# — so moving it mechanically would have made the suite permanently red for a reason that is
# not a defect, which is the exact failure this block already records from branch 9's close.
#
# THE RULE, STATED SO THE NEXT CLOSE DOES NOT HAVE TO RE-DERIVE IT: this pin moves in the
# COMMIT THAT MOVES THE BYTES, never at the close that merges it. At 5107aaf the arm keeps
# asking a live question — did the conditional passes change what post_process writes? — and
# would go red if slice 3 reverted them. Move it only when a later slice needs the comparison
# to start from a tree that already has slice 2's conditions in it.
#
# RE-TAKEN AT SLICE 3b, 2026-09-23, AND LEFT AT 5107aaf FOR A REASON THAT IS NOT HABIT. This
# slice changed paragraph 0 of the input, so the movement here is now slice 2's AND 3b's
# together -- and the arm does not need to tell them apart, because it asserts only that the
# bytes moved and the journal accounts for it, which holds against any earlier tree. 3b's own
# isolation is proved where it is claimed: tests/test_lexicon_choice.py's behaviour arms,
# proved RED against d3efa24 on both variants at the slice (PLAN-2-step-b.md section 3.8
# records it). A pin moved to d3efa24 here would add nothing that suite does not already
# assert, and would lose slice 2's coverage.
REF = os.environ.get("LT_BASELINE_REF", "5107aaf")

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
#: Tags that carry no text and must be emitted as EMPTY elements. `<w:tab></w:tab>` parses,
#: but a rendered tab is written `<w:tab/>` everywhere else in this repository and a fixture
#: that differs from the shape under test is a fixture that can pass for the wrong reason.
_EMPTY_TAGS = ("tab", "br")


def doc(paragraphs):
    """paragraphs :: list of list of (tag, text). Builds one w:p per entry.

    A tag in `_EMPTY_TAGS` ignores its text and emits a self-closing element, so a
    paragraph can carry a rendered tab or break between two runs — which is what
    slice 2's B4 arm needs and what no earlier fixture in this suite had.
    """
    body = []
    for runs in paragraphs:
        cells = "".join(
            f'<w:r><w:{tag}/></w:r>' if tag in _EMPTY_TAGS
            else f'<w:r><w:{tag} xml:space="preserve">{text}</w:{tag}></w:r>'
            for tag, text in runs)
        body.append(f"<w:p>{cells}</w:p>")
    return ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
            f'<w:document xmlns:w="{W}"><w:body>'
            + "".join(body) +
            "</w:body></w:document>").encode("utf-8")


# Paragraph 0 trips the TERMINOLOGY rewrite; 4 the spacing backstop across an element seam,
# which is C15's own mechanism; 5 is the negative control INSIDE the document and no pass in
# either variant may touch it.
#
# PARAGRAPH 0 USED TO TRIP THE ANNEX REWRITE, AND SINCE SLICE 3b THAT PASS REWRITES NOTHING.
# The lexicon offers Annex as a free choice, so `annex_to_schedule` is a detector and the
# input would have tripped two rewriting passes where arm 2 asks for three. The paragraph
# keeps its `Annex 1` -- now a string that must SURVIVE, which arm 8 asserts -- and gains a
# `Financing Agreement`, which no lexicon sanctions and the terminology pass still rewrites.
# Changing the input rather than lowering arm 2's threshold is deliberate: a count lowered to
# meet the code is a count that stopped measuring anything.
#
# PARAGRAPH 3 USED TO TRIP THE DOUBLE-PUNCTUATION COLLAPSE AND NOW TRIPS ITS DETECTOR.
# Since B8 the pass reports `Definitions::` and changes nothing, so this input trips THREE
# rewriting passes rather than four. The paragraph stays exactly as it was, deliberately: it
# is now the detector's input, and arm 12 asserts the colon survived and was reported.
#
# ONE SPELLING PARAGRAPH PER VARIANT, and the second one is here because the first version
# of this input carried only the US-to-UK direction. Under `--variant us` that paragraph is
# already correct, the spelling pass does nothing, and the suite failed for a reason that
# was true of the TEST rather than of the journal — a hardcoded "four passes" asserted
# against a document that trips four in one tree and three in the other. Paragraph 1 moves
# under uk only and paragraph 2 under us only, so the count is four either way.
CONTROL_PARA = 5
PASSES_DOC = doc([
    [("t", "Annex 1 to the Financing Agreement sets out the delivery milestones.")],
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
# THREE, NOT FOUR, SINCE SLICE 2 — AND THE MISSING ONE IS THE POINT RATHER THAN A REGRESSION.
# This input trips terminology (annex_to_schedule until slice 3b), a spelling pass,
# fix_spacing and, until B8,
# fix_double_punctuation on `Definitions::`. That fourth pass is now a DETECTOR: it reports
# the doubled colon and changes nothing, so it contributes no edit and must not. Arm 9 asserts
# the other half — that the colon SURVIVED and was REPORTED — so the number below going from
# four to three is covered by a check rather than merely tolerated.
ok("it recorded at least one edit on an input built to trip three rewriting passes",
   len(edits) >= 3,
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
# ARM 6 — THE DELIVERED BYTES MOVED, AND THE JOURNAL CLAIMS THE MOVEMENT. Branch 9 and slice
# 1 were ADDITIVE and this arm asserted the opposite of what it asserts now: not one byte may
# move. Slice 2 changes behaviour on every document by design, so byte identity would be a
# FAILURE and is asserted as such. The pin block above says why the question changed rather
# than only the sha.
# =========================================================================================
print(f"\nARM 6 — the delivered bytes MOVED against post_process at {REF}, and the "
      f"journal claims it")
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
    ok("the delivered bytes MOVED — slice 2 changes behaviour, so identity is a failure",
       nb != obb,
       f"new={hashlib.sha256(nb).hexdigest()[:12]} "
       f"old={hashlib.sha256(obb).hexdigest()[:12]} ({len(nb)} vs {len(obb)} bytes) "
       f"— identical means no conditional pass fired on an input built to trip four")
    # AND THE MOVEMENT IS EXPLAINED, NOT MERELY PRESENT. A pass that broke the document
    # would also move the bytes, so "they moved" on its own is not an acceptance. The
    # journal's own self-check is the other half, and arm 3 proves the claim is complete.
    jn = json.loads((d3 / JOURNAL_NAME).read_text(encoding="utf-8"))
    ok("the new arm's journal accounts for what it changed",
       bool(jn.get("self_check", {}).get("accounted", False)),
       f"self_check={jn.get('self_check')}")

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
#
# SINCE SLICE 3b THE PASS THAT FIRES THE GATE HERE IS NO LONGER THE ONE B6 NAMES. The Annex
# rewrite is a detector now, so the text is moved by the terminology and spelling passes --
# rewrites no lexicon sanctions, which the gate is RIGHT to stop. What this arm proves about
# the diagnosis is unchanged; the two B6(a) limbs below prove the override itself is gone.
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
        # B6's OTHER HALF, CLOSED AT SLICE 3b, AND ASSERTED ON THE SAME RUN. The gate still
        # fires here -- the terminology and spelling passes legitimately rewrite declared
        # text -- but the lexicon-sanctioned choice B6 is about is no longer among what
        # moved. A run that shows the diagnosis while the override still happens would be
        # half a fix reported as a whole one.
        ok("B6(a): the Annex pass moved NOTHING, though the operator declared `Annex 1`",
           "annex_to_schedule" not in moved_by, f"passes named: {sorted(moved_by)}")
        ok("B6(a): and `Annex 1` is still in the document the gate complained about",
           "Annex 1" in "".join(own_paragraph_texts(x5.read_bytes())),
           "the lexicon-sanctioned label was rewritten")
        claimed5 = {r.get("para") for st in j5.get("stages", [])
                    for r in st.get("paragraphs", [])}
        ok("the paragraph the gate is complaining about is one the journal claims",
           bool(claimed5), f"claimed={sorted(claimed5)}")
    ok("the gate's own message sends the operator to the journal by name",
       JOURNAL_NAME in blob5,
       "the banner offers three possibilities and no instrument to tell them apart")
    ok("and it still carries the three-possibility framing the rule-5b probe bought",
       "WORK OUT WHICH OF THREE THINGS IS WRONG" in blob5)

# =========================================================================================
# BRANCH 10 SLICE 1 — THE FORMATTING CONTRACT.
#
# Branch 9 DECLARED the journal blind to non-text change and reported it as a bare figure.
# That was honest and it was not enough, because branch 10 slice 3 turns the italic strip
# into a CONDITIONAL pass and no count can show a conditional pass did the right thing.
#
# The two shapes below are B1's and B7's, and they are the register's own: on the one frozen
# document that keeps a pre-post_process snapshot, `spurious_italic` reports 36 fixes against
# an element delta of exactly -36, and `schedule_page_breaks` reports 3 against +3 — which
# matches B7's measured `pageBreakBefore` 0 -> 3 on that document exactly. Neither moved a
# single character of text, which is why branch 9's journal recorded nothing for either.
#
# THE READERS BELOW ARE REIMPLEMENTED FROM THE CONTRACT AND IMPORT NOTHING FROM THE SCRIPT.
# A reader shared between the two sides of a comparison cannot see what it normalised away,
# and the fix for that is a second reader, never a changed one.
# =========================================================================================
R_TAG = f"{{{W}}}r"
PPR_TAG = f"{{{W}}}pPr"
P_TAG = f"{{{W}}}p"


def _shape(el):
    """Tag plus sorted attributes, no text. FULL {namespace}localname, never the localname
    alone: `t` is w:t, a:t and dgm:t, and a localname match once counted one chart part as
    four surfaces."""
    return el.tag + "".join(f" {k}={v}" for k, v in sorted(el.attrib.items()))


def _subtree(el):
    return " | ".join(_shape(x) for x in el.iter())


def flat_formats(xml_bytes):
    """For each text-bearing element, the shape of the w:r carrying it — same ordinal as
    flat_texts. Written from the contract's words, not from the script's code."""
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
    """For each paragraph, the shape of its own w:pPr — same index as own_paragraph_texts."""
    root = etree.fromstring(xml_bytes)
    out = []
    for p in root.iter(P_TAG):
        ppr = p.find(PPR_TAG)
        out.append("" if ppr is None else _subtree(ppr))
    return out


def format_replay(before_xml, after_xml, jrnl):
    """Apply the journal's FORMATTING record to the before-shapes and return what it
    predicts. This is what branch 11 will have to do for a conditional pass: account for
    exactly the declared changes and nothing else."""
    before = flat_formats(before_xml)
    after = flat_formats(after_xml)
    if len(before) != len(after):
        return None, None, "the element count moved; the contract does not claim that case"
    owners = owner_map(before_xml)
    for st in jrnl.get("stages", []):
        for e in st.get("format_edits", []):
            i = e.get("elem")
            if not isinstance(i, int) or not (0 <= i < len(before)):
                return None, None, f"format edit names element {i}, out of range"
            if before[i] != e.get("before"):
                return None, None, f"format edit {i}: before-shape is not the document's"
            if e.get("para") != owners[i]:
                return None, None, (f"format edit {i} says paragraph {e.get('para')}, "
                                    f"the document says {owners[i]}")
            before[i] = e.get("after")
    return before, after, None


def paragraph_format_replay(before_xml, after_xml, jrnl):
    before = paragraph_formats(before_xml)
    after = paragraph_formats(after_xml)
    if len(before) != len(after):
        return None, None, "the paragraph count moved; the contract does not claim that"
    for st in jrnl.get("stages", []):
        for r in st.get("format_paragraphs", []):
            i = r.get("para")
            if not isinstance(i, int) or not (0 <= i < len(before)):
                return None, None, f"format paragraph record names {i}, out of range"
            if before[i] != r.get("before"):
                return None, None, f"paragraph {i}: before-shape is not the document's"
            before[i] = r.get("after")
    return before, after, None


# Paragraph 0 is B1's shape: an italic run of more than two words, unparenthesised, not a
# Latin term, in a paragraph whose own properties do not set italic. Paragraph 1 is B7's: a
# schedule heading short enough and labelled well enough for the page-break pass to impose a
# break the source never asked for. Paragraph 2 is the negative control INSIDE the document
# — no pass may touch it and no record may name it.
FORMAT_CONTROL_PARA = 2
FORMAT_DOC = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
    f'<w:document xmlns:w="{W}"><w:body>'
    '<w:p><w:r><w:rPr><w:i/></w:rPr>'
    '<w:t xml:space="preserve">the italicised cross reference title</w:t>'
    '</w:r></w:p>'
    '<w:p><w:r><w:t xml:space="preserve">Schedule 1</w:t></w:r></w:p>'
    '<w:p><w:r><w:rPr><w:b/></w:rPr>'
    '<w:t xml:space="preserve">This bold sentence must not move.</w:t>'
    '</w:r></w:p>'
    '</w:body></w:document>').encode("utf-8")

print("\nARM 9 — the FORMATTING record: is branch 9's declared blind spot closed?")
d9, x9 = stage("format", FORMAT_DOC)
before9 = x9.read_bytes()
# SINCE SLICE 3a THIS FIXTURE NEEDS NOTES, AND THAT IS NOT A CONVENIENCE. The italic strip
# is now conditional on the declaration, so without one it changes nothing and this arm
# would VOID on an empty record — a formatting arm reporting nothing to record, on a run
# where the deliverable was working correctly. The notes declare the italic run as NOT
# italic, which is the case where the pass must STILL fire; arm 14 owns the opposite limb.
_fmt_notes = run([SCRIPTS / "extract_paragraphs.py", x9, d9 / "paragraphs.json"])
if (d9 / "paragraphs.json").is_file():
    _fn = json.loads((d9 / "paragraphs.json").read_text(encoding="utf-8"))
    for e in _fn:
        e["en"] = e.get("text", "")
        e["en_runs"] = [{"start": 0, "end": len(e["en"]),
                         "bold": False, "italic": False}]
        # The SOURCE side must not answer for this arm: in a synthetic fixture the
        # extractor reads the very runs under test, so `runs` would carry the English
        # text AND its italic flag and the source arm would keep everything.
        for _r in (e.get("runs") or []):
            _r["italic"] = False
    (d9 / "paragraphs.json").write_bytes(
        (json.dumps(_fn, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
r9 = run([SCRIPTS / "post_process.py", x9, "--fix", "--variant", args.variant])
after9 = x9.read_bytes()
j9 = journal_of(d9)
if j9 is None:
    void("the formatting record", f"no journal was written (rc={r9.returncode})")
else:
    counts9 = {c["pass"]: c["fixes"] for c in j9["stages"][0].get("counts", [])}
    # ASSERT THE ARTEFACT FIRST. If neither pass fired, every check below would pass by
    # describing an empty record, which is the shape of a check that tests nothing.
    fired = counts9.get("spurious_italic", 0), counts9.get("schedule_page_breaks", 0)
    if not any(fired):
        void("the formatting record",
             f"neither pass fired on the fixture (italic={fired[0]}, "
             f"page_breaks={fired[1]}), so there is nothing to record")
    else:
        ok("the journal declares a FORMAT contract beside the text one",
           isinstance(j9.get("format_contract"), str)
           and "w:pPr" in (j9.get("format_contract") or ""),
           repr(j9.get("format_contract"))[:120])
        # /3 SINCE SLICE 4, which added `detections`. The claim is unchanged -- the version
        # moves whenever the artefact describes something new -- and it moved again.
        ok("the schema version moved, because the artefact describes something new",
           j9.get("schema") == "post-process-journal/3", repr(j9.get("schema")))

        fmt_edits = [e for st in j9["stages"] for e in st.get("format_edits", [])]
        fmt_paras = [r for st in j9["stages"] for r in st.get("format_paragraphs", [])]

        # B1 — the italic strip, recorded at element level and NAMING the pass.
        italic = [e for e in fmt_edits if e.get("pass") == "spurious_italic"]
        ok("B1's italic strip is RECORDED, and the record names the pass",
           len(italic) == counts9.get("spurious_italic", 0) and len(italic) > 0,
           f"{len(italic)} record(s) against {counts9.get('spurious_italic', 0)} fix(es)")
        ok("and what it records is the w:i LEAVING the run, not merely that something moved",
           all(f"{{{W}}}i" in (e.get("before") or "")
               and f"{{{W}}}i" not in (e.get("after") or "") for e in italic),
           "a record whose before/after do not show the italic going is not evidence")

        # B7 — INVERTED AT SLICE 4, AND THE INVERSION IS RECORDED RATHER THAN MADE QUIETLY.
        # Until slice 4 this limb asserted the imposed break was RECORDED, because the page-
        # break pass imposed one on paragraph 1 and the record had to catch it. Slice 4 made
        # that pass a detector, so the same paragraph must now gain NOTHING and no record may
        # name the pass. What the paragraph-level recorder can still do once a pass changes a
        # w:pPr -- none does any more -- is proved on the recorder itself, in-process, by
        # tests/test_pass_conditions.py arm 9.
        pbreak = [r for r in fmt_paras if r.get("pass") == "schedule_page_breaks"]
        ok("B7 FIXED: the schedule heading gains NO page break, and no record claims one",
           counts9.get("schedule_page_breaks", 0) == 0 and not pbreak
           and b"pageBreakBefore" not in after9,
           f"{len(pbreak)} record(s), {counts9.get('schedule_page_breaks', 0)} fix(es)")
        ok("and the journal REPORTS the heading it found instead",
           any(d.get("pass") == "schedule_page_breaks" and d.get("para") == 1
               for d in j9.get("detections", [])),
           repr([d for d in j9.get("detections", [])
                 if d.get("pass") == "schedule_page_breaks"])[:200])

        # THE SECOND READER. Replay the record over the before-document and require it to
        # reproduce the after-document's shapes exactly.
        pred, actual, err = format_replay(before9, after9, j9)
        ok("the element-level record REPLAYS onto the finished document", err is None, err)
        if err is None:
            missed = [i for i, (p, a) in enumerate(zip(pred, actual)) if p != a]
            ok("and it accounts for every run whose shape moved — no formatting change "
               "the journal does not claim", not missed, f"unaccounted ordinals: {missed}")
        ppred, pactual, perr = paragraph_format_replay(before9, after9, j9)
        ok("the paragraph-level record replays too", perr is None, perr)
        if perr is None:
            pmissed = [i for i, (p, a) in enumerate(zip(ppred, pactual)) if p != a]
            ok("and accounts for every paragraph whose properties moved",
               not pmissed, f"unaccounted paragraphs: {pmissed}")

        # THE NEGATIVE CONTROL INSIDE THE DOCUMENT.
        named = {e.get("para") for e in fmt_edits} | {r.get("para") for r in fmt_paras}
        ok("the control paragraph is named by NO formatting record",
           FORMAT_CONTROL_PARA not in named, f"records name paragraphs {sorted(named)}")

        # THE FIGURE THAT SHOULD NOW BE EMPTY.
        ok("nothing is left UNEXPLAINED — every fix is a text edit or a formatting one",
           j9["self_check"].get("unexplained_fixes") == [],
           repr(j9["self_check"].get("unexplained_fixes")))
        ok("and non_text_fixes SURVIVES at schemas 2 and 3, because it has live consumers",
           isinstance(j9["self_check"].get("non_text_fixes"), list),
           repr(j9["self_check"].get("non_text_fixes")))

# =========================================================================================
# ARM 10 — THE POSITIVE CONTROL FOR THE FORMATTING ARM. Remove one recorded formatting edit
# and require ARM 9's replay to go RED for it. Branch 9's own control caught two real
# defects in the check on its first run — an element record that was walked but never used,
# so deleting an entry changed nothing, and entries carrying no paragraph id. Both read as
# working. An arm that reports "accounted" everywhere must be shown able to say otherwise.
# =========================================================================================
print("\nARM 10 — the positive control: drop one formatting record and prove ARM 9 fails")
if j9 is None:
    void("formatting positive control", "no journal to plant a defect in")
else:
    planted = json.loads(json.dumps(j9))
    victim = None
    for st in planted.get("stages", []):
        if st.get("format_edits"):
            victim = st["format_edits"].pop(0)
            break
    if victim is None:
        void("formatting positive control",
             "the fixture produced no element-level formatting record to remove")
    else:
        pred2, actual2, err2 = format_replay(before9, after9, planted)
        caught = err2 is not None or (
            pred2 is not None
            and any(p != a for p, a in zip(pred2, actual2)))
        ok("with one formatting record removed the replay reports the run as UNACCOUNTED, "
           "so ARM 9 can fail", caught,
           "the replay still reported everything accounted for — it is not load-bearing")

# =========================================================================================
# ARM 11 — THE STRIP STAGE CARRIES THE FORMAT CONTRACT TOO. It is the one stage that
# DELETES, so its ordinals shift and only the paragraph level can describe it. Leaving it
# out would have been cheaper and wrong: a contract with one stage silently exempt reads as
# coverage, and B3 — slice 2's — is a defect in exactly this stage.
# =========================================================================================
print("\nARM 11 — the strip stage is inside the formatting contract, not exempt from it")
d11, x11 = stage("format_strip", TC_DOC)
r11 = run([SCRIPTS / "post_process.py", x11, "--fix", "--variant", args.variant])
j11 = journal_of(d11)
if j11 is None:
    void("strip formatting record", f"no journal written (rc={r11.returncode})")
else:
    strip11 = [st for st in j11.get("stages", [])
               if st.get("stage") == "strip_noop_tracked_changes"]
    if not strip11:
        void("strip formatting record", "the strip stage did not run on this fixture")
    else:
        ok("the strip stage carries a format_paragraphs key, present even when empty",
           isinstance(strip11[0].get("format_paragraphs"), list),
           repr(strip11[0].get("format_paragraphs"))[:120])

# =========================================================================================
# ARM 12 — SLICE 2: EVERY PASS TESTS THE CONDITION IT ASSUMES. Four conditions, each with
# BOTH limbs asserted — the case the pass must now skip AND the case it must still take.
# One limb alone is half a check: a pass that stopped firing entirely would satisfy every
# "must skip" and break the pipeline, and a pass that never changed would satisfy every
# "must still fire".
# =========================================================================================
print("\nARM 12 — slice 2: each pass tests the condition it assumes (B4, B3, B2, B8)")

# ---- B4: a seam bridged by a RENDERED tab or break already has its separator.
B4_DOC = doc([
    # 0: bridged by a rendered tab — must NOT gain a space.
    [("t", "Signed"), ("tab", ""), ("t", "Dated")],
    # 1: bridged by a break — must NOT gain a space.
    [("t", "Address"), ("br", ""), ("t", "London")],
    # 2: nothing between — must STILL gain one. This is the limb that catches a pass
    #    which stopped working rather than became conditional.
    [("t", "the"), ("t", "Facility")],
])
d12, x12 = stage("b4", B4_DOC)
r12 = run([SCRIPTS / "post_process.py", x12, "--fix", "--variant", args.variant])
ok("B4 fixture: post_process exits 0", r12.returncode == 0, r12.stderr[-400:])
b4_after = x12.read_bytes().decode("utf-8")
ok("B4: a seam bridged by a RENDERED TAB is left alone",
   "Signed" in b4_after and "> Dated<" not in b4_after,
   f"a space was inserted across a tab: {b4_after[:400]}")
ok("B4: a seam bridged by a BREAK is left alone",
   "> London<" not in b4_after,
   f"a space was inserted across a break: {b4_after[:400]}")
ok("B4: a seam with NOTHING between it still gains its space",
   "> Facility<" in b4_after,
   f"the pass stopped firing altogether: {b4_after[:400]}")

# ---- B4b: a w:tab inside w:pPr/w:tabs is a tab STOP and must not bridge anything.
B4_STOP_DOC = doc([[("t", "the"), ("t", "Facility")]]).replace(
    b"<w:p><w:r>",
    b'<w:p><w:pPr><w:tabs><w:tab w:val="left" w:pos="720"/></w:tabs></w:pPr><w:r>', 1)
d12b, x12b = stage("b4stop", B4_STOP_DOC)
r12b = run([SCRIPTS / "post_process.py", x12b, "--fix", "--variant", args.variant])
ok("B4: a tab STOP in pPr/tabs does NOT bridge the seam — it is not a rendered tab",
   "> Facility<" in x12b.read_bytes().decode("utf-8"),
   "a tab stop was mistaken for a rendered tab and suppressed a real fix")

# ---- B3: an insertion wrapper still carrying text is part of the DELIVERED document.
B3_DOC = doc([[("t", "The completion date is fixed.")]]).replace(
    b"<w:p><w:r><w:t xml:space=\"preserve\">The completion date is fixed.</w:t></w:r></w:p>",
    ('<w:p>'
     '<w:r><w:t xml:space="preserve">payable on </w:t></w:r>'
     '<w:ins w:id="9" w:author="A"><w:r><w:t xml:space="preserve">[</w:t></w:r></w:ins>'
     '<w:r><w:t xml:space="preserve">1 March 2026</w:t></w:r>'
     '<w:ins w:id="10" w:author="A"><w:r><w:t xml:space="preserve">]</w:t></w:r></w:ins>'
     '<w:del w:id="11" w:author="A">'
     '<w:r><w:delText xml:space="preserve">,</w:delText></w:r></w:del>'
     '<w:r><w:t xml:space="preserve"> in full.</w:t></w:r>'
     '</w:p>').encode("utf-8"))
d13, x13 = stage("b3", B3_DOC)
r13 = run([SCRIPTS / "post_process.py", x13, "--fix", "--variant", args.variant])
ok("B3 fixture: post_process exits 0", r13.returncode == 0, r13.stderr[-400:])
b3_after = x13.read_bytes().decode("utf-8")
# THE EXACT D08 SHAPE: the edit IS the brackets, and the old carve-out could not see it
# because the only neighbours are REGULAR runs.
ok("B3: a bracket-only INSERTION survives — removing it would delete a delivered character",
   b3_after.count("<w:ins") == 2,
   f"an insertion wrapper was stripped: {b3_after.count('<w:ins')} of 2 left")
ok("B3: a punctuation-only DELETION is still stripped — it touches the reject view only",
   "<w:del" not in b3_after,
   "the del wrapper survived, so the pass lost work it should have kept doing")

# ---- B2: an indeterminate Article reference is left alone and reported.
B2_DOC = doc([
    # 0: "thereof" points BACKWARD — the forward walk learns nothing. Must NOT be rewritten.
    [("t", "The parties waive Article 1341 thereof.")],
    # 1: decided internal by a determiner — must STILL be rewritten.
    [("t", "Article 4 of this Agreement shall apply.")],
])
d14, x14 = stage("b2", B2_DOC)
r14 = run([SCRIPTS / "post_process.py", x14, "--fix", "--variant", args.variant])
ok("B2 fixture: post_process exits 0", r14.returncode == 0, r14.stderr[-400:])
b2_after = x14.read_bytes().decode("utf-8")
_internal = "Clause" if args.variant == "uk" else "Section"
ok("B2: an INDETERMINATE reference keeps the word 'Article'",
   "Article 1341 thereof" in b2_after,
   "a statutory citation was rewritten on a guess — this is D05's defect")
ok("B2: a reference decided INTERNAL is still rewritten",
   f"{_internal} 4 of this Agreement" in b2_after,
   f"the pass stopped rewriting altogether; expected '{_internal} 4'")
ok("B2: the run REPORTS what it declined to classify",
   "[detector] article_to_clause" in (r14.stdout or ""),
   "the pass changed nothing and said nothing, which reads as nothing to do")

# ---- B8: a doubled mark is reported, never collapsed.
B8_DOC = doc([[("t", "Definitions::")]])
d15, x15 = stage("b8", B8_DOC)
r15 = run([SCRIPTS / "post_process.py", x15, "--fix", "--variant", args.variant])
ok("B8: the doubled mark SURVIVES — nothing says whose it is",
   "Definitions::" in x15.read_bytes().decode("utf-8"),
   "a character of possible source content was deleted")
ok("B8: and the run REPORTS it rather than staying silent",
   "[detector] double_punctuation" in (r15.stdout or ""),
   "the detector found nothing to say, so the loss is now silent instead of silent-and-real")

# =========================================================================================
# ARM 13 — THE VALIDATOR READS THE RECORD INSTEAD OF PREDICTING IT (C15). The prediction
# could not see a tab, so the moment B4 landed it would have fired on exactly B4's seams.
# =========================================================================================
print("\nARM 13 — validate_apply's post-strip gate reads the journal, not a prediction")
_va = SCRIPTS / "validate_apply.py"
_va_src = _va.read_text(encoding="utf-8")
ok("validate_apply can load the spacing record from the journal",
   "def load_spacing_record(" in _va_src)
ok("it names the journal by the same filename post_process writes",
   f"'{JOURNAL_NAME}'" in _va_src or f'"{JOURNAL_NAME}"' in _va_src)
ok("it still FALLS BACK to the prediction when no journal is beside the notes",
   "will_fix_spacing_fire(prev_text, en)" in _va_src,
   "the fallback was removed, so a caller with no journal now gets no mirror at all")
ok("and it SAYS which of the two routes it took",
   "PREDICTING fix_spacing rather than reading it" in _va_src
   and "text(s) the pass recorded moving" in _va_src,
   "a gate that reads on one run and guesses on the next must say which")
# BOTH TREES, because a fix that lands in one variant and is forgotten in the other has
# shipped to a client before — arm 7's rule, applied to this change.
_other = "us" if args.variant == "uk" else "uk"
_va_other = (ROOT / _other / "scripts" / "validate_apply.py").read_text(encoding="utf-8")
ok(f"and the {_other} tree carries it too",
   "def load_spacing_record(" in _va_other)

# =========================================================================================
# ARM 14 — SLICE 3a: THE ITALIC STRIP TESTS THE CONDITION IT ASSUMES (B1).
#
# The old rule — more than two unparenthesised words, not a listed Latin term — is not a
# test of whether the italic was the operator's. It is UNSATISFIABLE BY FAITHFUL WORK: an
# italicised cross-reference title cannot be written so as to pass it. On one real document
# the pass destroyed a drafting convention document-wide and the operator had declared
# every instance correctly.
#
# FOUR LIMBS, AND THE LAST ONE IS THE REASON THIS ARM EXISTS RATHER THAN A SIMPLER ONE.
# Arm 6 already runs post_process on a fixture with NO notes beside it, so after slice 3a
# the italic pass changes nothing there — and arm 6 still passes, because the other passes
# move bytes. A suite could therefore go green over a condition it never evaluated once.
# Limb (d) is what makes that impossible to miss: it asserts the no-notes case REPORTS.
#
# The notes are produced by the real `extract_paragraphs.py` and then have `en` / `en_runs`
# authored on top, exactly as arm 8 does. Offsets are COMPUTED from the strings, never
# typed: a hand-typed offset is a second place for this arm to be wrong.
# =========================================================================================
print("\nARM 14 — slice 3a: the italic strip consults the declared notes (B1)")

_I = '<w:r><w:rPr><w:i/></w:rPr><w:t xml:space="preserve">%s</w:t></w:r>'
_P = '<w:r><w:t xml:space="preserve">%s</w:t></w:r>'

# Every italic string below is >2 words, unparenthesised, and free of any listed Latin
# term as a SUBSTRING — the pass tests `lt in text.lower()`, so "in rem" would match
# "in remuneration". Checked against the shipped list rather than assumed.
B1_DECLARED = "Preservation of the Security"      # en_runs says italic -> must SURVIVE
B1_UNDECLARED = "the borrower shall notify"       # en_runs says NOT italic -> must GO
B1_RETAINED = "Ejemplo de Ley Sintetica"          # invented, untranslated -> must SURVIVE
B1_SHORT = "Force Majeure"                        # 2 words: never a candidate at all

B1_DOC = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
          f'<w:document xmlns:w="{W}"><w:body>'
          f'<w:p>{_I % B1_DECLARED}</w:p>'
          f'<w:p>{_I % B1_UNDECLARED}</w:p>'
          f'<w:p>{_P % "under "}{_I % B1_RETAINED}</w:p>'
          f'<w:p>{_I % B1_SHORT}</w:p>'
          '</w:body></w:document>').encode("utf-8")


def _b1_notes(workdir, xml_path):
    """Generate notes with the real extractor, then author the declaration on top.

    Returns the notes list, or None if the extractor could not run — reported as VOID
    rather than quietly skipped.
    """
    rx = run([SCRIPTS / "extract_paragraphs.py", xml_path, workdir / "paragraphs.json"])
    if not (workdir / "paragraphs.json").is_file():
        return None, rx
    notes = json.loads((workdir / "paragraphs.json").read_text(encoding="utf-8"))
    for e in notes:
        txt = e.get("text", "")
        e["en"] = txt
        # THE SOURCE SIDE HAS TO BE MADE REALISTIC OR THIS ARM TESTS NOTHING. In a real
        # run `runs` comes from the SOURCE-LANGUAGE document, so an English run's text
        # matches one only where the term was never translated. In a synthetic fixture
        # the extractor reads the very runs under test, so every source run would carry
        # the English text AND its italic flag — and the source arm would keep
        # everything, including limb (b). Found by this arm failing on its first run.
        for _r in (e.get("runs") or []):
            if _r.get("text") == B1_RETAINED:
                _r["italic"] = True          # untranslated, italic in the source
            else:
                _r["text"] = "kildetekst %d" % len(_r.get("text") or "")
                _r["italic"] = False
        if B1_DECLARED in txt:
            e["en_runs"] = [{"start": txt.index(B1_DECLARED),
                             "end": txt.index(B1_DECLARED) + len(B1_DECLARED),
                             "bold": False, "italic": True}]
        elif B1_UNDECLARED in txt:
            e["en_runs"] = [{"start": txt.index(B1_UNDECLARED),
                             "end": txt.index(B1_UNDECLARED) + len(B1_UNDECLARED),
                             "bold": False, "italic": False}]
        else:
            # No English declaration at all. The RETAINED paragraph must therefore be
            # decided by the SOURCE arm, which is the whole point of limb (c).
            e["en_runs"] = None
    (workdir / "paragraphs.json").write_bytes(
        (json.dumps(notes, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    return notes, rx


def _italic_texts(xml_bytes):
    """The texts of every run still carrying an ON w:i. Reads w:val and treats
    0/false/off as OFF, per .claude/rules/ooxml.md."""
    root = etree.fromstring(xml_bytes)
    out = []
    for r in root.iter(f"{{{W}}}r"):
        rpr = r.find(f"{{{W}}}rPr")
        if rpr is None:
            continue
        ie = rpr.find(f"{{{W}}}i")
        if ie is None:
            continue
        v = ie.get(f"{{{W}}}val")
        if v is not None and v.strip().lower() in ("false", "0", "off"):
            continue
        t = r.find(f"{{{W}}}t")
        if t is not None and t.text:
            out.append(t.text)
    return out

# Sanity: the strings really are candidates under the SHIPPED Latin list, not under a
# retyped copy of it. A limb that silently stopped being a candidate would pass every
# "must survive" assertion for the wrong reason.
_pp_src = (SCRIPTS / "post_process.py").read_text(encoding="utf-8")
_latin = re.findall(r"'([a-zà-ÿ .]+)',", _pp_src[_pp_src.index("latin_terms = {"):
                                                 _pp_src.index("latin_terms = {") + 700])
ok("ARM 14's fixture strings are not accidentally exempt as Latin terms",
   _latin and not any(lt in s.lower() for lt in _latin
                      for s in (B1_DECLARED, B1_UNDECLARED, B1_RETAINED)),
   f"a fixture string matches the shipped Latin list ({len(_latin)} terms read)")

d14, x14 = stage("b1-notes", B1_DOC)
_notes14, _rx14 = _b1_notes(d14, x14)
if _notes14 is None:
    void("B1 conditional strip", f"could not produce notes (rc={_rx14.returncode})")
else:
    r14 = run([SCRIPTS / "post_process.py", x14, "--fix", "--variant", args.variant])
    after14 = _italic_texts(x14.read_bytes())
    # The drift gate may fire — the notes declare the pre-pass English and other passes
    # move text. That is B6's situation, not this arm's, and the document is written
    # before the gate raises. Compared by the gate's own words, never by rc alone.
    ok("B1 fixture: post_process either exits 0 or fires the DRIFT GATE, not a crash",
       r14.returncode == 0 or "SKILL GATE FIRED" in ((r14.stdout or "") + (r14.stderr or "")),
       f"rc={r14.returncode}: {(r14.stderr or '')[-400:]}")
    ok("B1 (a): italic the operator DECLARED in en_runs SURVIVES",
       B1_DECLARED in after14,
       "the pass stripped formatting the notes explicitly authorise — this is the defect")
    ok("B1 (b): italic the notes cover and do NOT declare is STILL STRIPPED",
       B1_UNDECLARED not in after14,
       "the pass stopped firing altogether rather than becoming conditional")
    ok("B1 (c): an untranslated term carried from an ITALIC SOURCE RUN survives",
       B1_RETAINED in after14,
       "the source arm did not fire — this is D03B, the case the function's own "
       "docstring carve-out claims to protect")
    ok("B1 (d): a two-word run was never a candidate and is untouched either way",
       B1_SHORT in after14,
       "the candidacy rule changed, which slice 3a must not do")

# ---- limb (e): NO NOTES AT ALL -> change nothing, and SAY SO.
d14b, x14b = stage("b1-nonotes", B1_DOC)
r14b = run([SCRIPTS / "post_process.py", x14b, "--fix", "--variant", args.variant])
after14b = _italic_texts(x14b.read_bytes())
blob14b = (r14b.stdout or "") + (r14b.stderr or "")
ok("B1 (e): with NO notes the pass changes NOTHING — it cannot determine its condition",
   B1_UNDECLARED in after14b and B1_DECLARED in after14b,
   "the pass stripped on a document where nothing said whether the italic was the "
   "operator's — decision 2c revised says report and change nothing")
ok("B1 (e): and it REPORTS that it declined, rather than reading as 'found nothing'",
   "spurious_italic left" in blob14b and "no notes" in blob14b,
   "a pass that silently stops rewriting is indistinguishable from one with no work "
   "to do — which is how arm 6 could go green over a condition never evaluated")

# BOTH TREES — arm 7's rule applied to this change.
_pp_other = (ROOT / ("us" if args.variant == "uk" else "uk")
             / "scripts" / "post_process.py").read_text(encoding="utf-8")
ok(f"and the {'us' if args.variant == 'uk' else 'uk'} tree carries the conditional pass too",
   "def _declared_italic(" in _pp_other
   and "def fix_spurious_italic_runs(root, notes=None):" in _pp_other,
   "a fix that lands in one variant and is forgotten in the other has shipped before")

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
