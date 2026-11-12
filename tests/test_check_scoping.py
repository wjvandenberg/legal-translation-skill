# -*- coding: utf-8 -*-
"""STEP 14 — every narrowed check must still catch its true positive.

WHY THIS FILE EXISTS AND WHAT IT IS GUARDING AGAINST. Step 14 makes eight checks
report less. That is the entire change, and it is also the entire risk: a pattern
narrowed until it fires on nothing is not a fix, it is a bypass with extra steps, and
nothing in a green test run would tell the difference. So every fix here is tested in
BOTH directions --

    FALSE POSITIVE control : an input the check should NOT flag. It must be silent now.
    TRUE POSITIVE control  : an input the check MUST flag. It must still fire.

AND EVERY FALSE-POSITIVE CONTROL IS PROVED TO HAVE FIRED BEFORE, AGAINST THE REAL
PRE-BRANCH CODE. A control that was already silent proves nothing -- it is the
"check that passes for the wrong reason" this project has now logged eleven times. So
this file does not hand-copy the old logic (which could drift from what the old logic
actually was); it reads the previous version of each script out of git and imports it
alongside the current one. The assertion is then:

    old(false_positive) fires   AND   new(false_positive) is silent
    old(true_positive)  fires   AND   new(true_positive)  fires

If the baseline ref cannot be resolved, this reports VOID and exits non-zero. A
comparison that established nothing has not passed.

    uv run --with lxml python tests/test_check_scoping.py
    LT_BASELINE_REF=<ref> uv run --with lxml python tests/test_check_scoping.py

All test content is INVENTED. No client text, no corpus material -- CLAUDE.md 5.6.
"""
import importlib.util
import inspect
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.dont_write_bytecode = True
# AND THE SAME GUARD FOR EVERY CHILD PROCESS, which the line above cannot give.
# `sys.dont_write_bytecode` is a runtime flag: it governs this interpreter's imports and
# is not inherited. A suite here calls skill code that spawns validators as subprocesses,
# and one of those imports post_process -- so a .pyc appeared inside uk/scripts every run.
# It is gitignored, invisible to a diff, and the release packager zips that tree. Setting
# the ENV VAR is the only form of this guard that reaches a grandchild. Register I-18.
os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")
ROOT = Path(__file__).resolve().parent.parent

# THE BASELINE IS PINNED TO A COMMIT, NOT TO A BRANCH NAME, AND THAT IS THE WHOLE POINT.
#
# The first version of this file used `origin/main`. That WAS the pre-branch code while the
# branch was in flight, and it STOPPED BEING IT the moment the branch merged: `origin/main`
# then resolved to the fixed code, so every "PROVED it fired before" assertion was comparing
# the fix against itself. Nine of them went red within seconds of the merge, which is the
# good outcome — a self-invalidating test that went GREEN instead would have been the
# eleventh logged case of a check passing for the wrong reason, and this file exists to
# argue against exactly that.
#
# 2178cce is the commit before step 14. It is a historical fact and it does not move.
# Override with LT_BASELINE_REF when re-pointing this suite at a different comparison.
BASELINE = os.environ.get("LT_BASELINE_REF", "2178cce")
W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"

FAIL = []
CHECKED = 0


def ok(label, condition, detail=""):
    global CHECKED
    CHECKED += 1
    if condition:
        print(f"  OK   {label}")
    else:
        print(f"  XX   {label}   {detail}")
        FAIL.append(f"{label} {detail}".strip())


# ---------------------------------------------------------------- baseline loading
def resolve_baseline():
    """The commit this branch is measured against. VOID rather than a guess.

    Only the PINNED ref is tried. The earlier version fell back to `main` and then `HEAD~1`,
    which sounds defensive and is the opposite: a fallback that silently lands on the fixed
    code turns every before/after assertion into a comparison of the fix with itself. If the
    pin does not resolve, say so and stop.
    """
    r = subprocess.run(["git", "rev-parse", "--verify", BASELINE],
                       capture_output=True, text=True, cwd=ROOT)
    return (BASELINE, r.stdout.strip()) if r.returncode == 0 else (None, None)


def assert_baseline_differs(script, tree="uk"):
    """The baseline copy of `script` must NOT be the working-tree copy.

    A comparison that established nothing has not passed. If a rebase, a squash or a moved
    pin makes the two identical, this suite must say VOID and exit non-zero rather than
    report a green before/after it never made.
    """
    b = subprocess.run(["git", "show", f"{REF}:{tree}/scripts/{script}"],
                       capture_output=True, cwd=ROOT)
    if b.returncode != 0:
        print(f"VOID — cannot read {tree}/{script} at {REF}. Nothing compared, nothing passed.")
        sys.exit(1)
    if b.stdout == (ROOT / tree / "scripts" / script).read_bytes():
        print(f"VOID — {tree}/{script} at {REF} is BYTE-IDENTICAL to the working tree, so every")
        print("before/after assertion below would compare the fix against itself. That is")
        print("not a pass. Point LT_BASELINE_REF at a commit that predates the change.")
        sys.exit(1)


REF, SHA = resolve_baseline()
if REF is None:
    print(f"VOID — the pinned baseline {BASELINE!r} does not resolve in this clone.")
    print("Nothing was compared, so nothing passed. Set LT_BASELINE_REF.")
    sys.exit(1)

TMP = Path(tempfile.mkdtemp(prefix="b14-baseline-"))
OLD_DIR = TMP / "old_scripts"
OLD_DIR.mkdir(parents=True)
# source_language_markers is unchanged by this branch and is imported by the scripts
# below, so the baseline copies need it beside them.
for name in ("source_language_markers.py", "lexicon_compliance.py"):
    shutil.copyfile(ROOT / "uk" / "scripts" / name, OLD_DIR / name)


def tag(tree):
    """'' for uk, 'us_' for us -- keeps a us module and file from shadowing the uk one."""
    return "" if tree == "uk" else f"{tree}_"


def load_old(script, tree="uk"):
    """Import the pre-branch version of a <tree>/scripts file under its own name."""
    blob = subprocess.run(["git", "show", f"{REF}:{tree}/scripts/{script}"],
                          capture_output=True, cwd=ROOT)
    if blob.returncode != 0:
        print(f"VOID — cannot read {tree}/{script} at {REF}")
        sys.exit(1)
    path = OLD_DIR / (tag(tree) + script)
    path.write_bytes(blob.stdout)
    modname = "old_" + tag(tree) + script[:-3]
    spec = importlib.util.spec_from_file_location(modname, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[modname] = mod
    sys.path.insert(0, str(OLD_DIR))
    try:
        spec.loader.exec_module(mod)
    finally:
        sys.path.remove(str(OLD_DIR))
    return mod


def load_new(script, tree="uk"):
    sys.path.insert(0, str(ROOT / tree / "scripts"))
    try:
        spec = importlib.util.spec_from_file_location(
            "new_" + tag(tree) + script[:-3], ROOT / tree / "scripts" / script)
        mod = importlib.util.module_from_spec(spec)
        sys.modules["new_" + tag(tree) + script[:-3]] = mod
        spec.loader.exec_module(mod)
    finally:
        sys.path.remove(str(ROOT / tree / "scripts"))
    return mod


print(f"STEP 14 — CHECK SCOPING, BOTH DIRECTIONS")
print(f"baseline: {REF} = {SHA[:12]}")
print("=" * 96)

from lxml import etree  # noqa: E402

for _s in ("quality_check.py", "validate_segment_shapes.py",
           "translate_headers_footers.py"):
    assert_baseline_differs(_s)
# 14.2 runs its F10 controls over the us tree as well, so its baseline must differ there too.
assert_baseline_differs("validate_segment_shapes.py", "us")
# And 14.3 its G1 and G7 controls, over both trees; and 14.4 its G2, G8 and G14 controls.
for _t in ("uk", "us"):
    assert_baseline_differs("validate_translations.py", _t)
    assert_baseline_differs("lexicon_compliance.py", _t)

OLD_QC = load_old("quality_check.py")
NEW_QC = load_new("quality_check.py")
OLD_VSS = load_old("validate_segment_shapes.py")
NEW_VSS = load_new("validate_segment_shapes.py")
OLD_THF = load_old("translate_headers_footers.py")
NEW_THF = load_new("translate_headers_footers.py")
NEW_RPK = load_new("repack_docx.py")


def doc(body):
    return etree.fromstring(
        ('<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/'
         '2006/main"><w:body>' + body + '</w:body></w:document>').encode("utf-8"))


def para(text, **kw):
    ppr = kw.get("ppr", "")
    return f'<w:p>{ppr}<w:r><w:t xml:space="preserve">{text}</w:t></w:r></w:p>'


# =============================================================================
print("\nG10 — the missing-space rule must not fire across a rendered break")
print("-" * 96)

G10_CASES = [
    ("tab-separated party grid",
     '<w:p><w:r><w:t xml:space="preserve">Party A</w:t></w:r><w:r><w:tab/></w:r>'
     '<w:r><w:t xml:space="preserve">Party B</w:t></w:r></w:p>', False),
    ("tab between two w:t inside ONE run",
     '<w:p><w:r><w:t xml:space="preserve">Name</w:t><w:tab/>'
     '<w:t xml:space="preserve">Signature</w:t></w:r></w:p>', False),
    ("manual line break between two runs",
     '<w:p><w:r><w:t xml:space="preserve">First line</w:t></w:r><w:r><w:br/></w:r>'
     '<w:r><w:t xml:space="preserve">Second line</w:t></w:r></w:p>', False),
    ("TRUE POSITIVE: a real missing space, nothing between the runs",
     '<w:p><w:r><w:t xml:space="preserve">the Supplier</w:t></w:r>'
     '<w:r><w:t xml:space="preserve">shall deliver</w:t></w:r></w:p>', True),
    ("TRUE POSITIVE: a tab STOP in w:pPr must not suppress a real finding",
     '<w:p><w:pPr><w:tabs><w:tab w:val="left" w:pos="2880"/></w:tabs></w:pPr>'
     '<w:r><w:t xml:space="preserve">the Supplier</w:t></w:r>'
     '<w:r><w:t xml:space="preserve">shall deliver</w:t></w:r></w:p>', True),
]
for label, body, want_fire in G10_CASES:
    root = doc(body)
    old_n = len(OLD_QC.check_spacing(doc(body), False))
    new_n = len(NEW_QC.check_spacing(root, False))
    if want_fire:
        ok(f"G10 {label}: still fires", new_n > 0, f"(new={new_n})")
        ok(f"G10 {label}: fired before too", old_n > 0, f"(old={old_n})")
    else:
        ok(f"G10 {label}: silent now", new_n == 0, f"(new={new_n})")
        ok(f"G10 {label}: PROVED it fired before", old_n > 0,
           f"(old={old_n} — control tests nothing if this is 0)")

# =============================================================================
print("\nL1 — method A must pair by text, not by position")
print("-" * 96)

# A permuted document: the notes declare entry idx=0 -> LONG_EN and idx=1 -> SHORT_EN,
# but skill Step 7 has swapped the two paragraphs. Positionally, entry 0's long source is
# compared against the SHORT paragraph, so the ratio collapses and the rule fires on a
# translation that is complete. Paired by text, entry 0 finds its own long English.
LONG_SRC = ("Die Verkoper verbindt zich om alle rechten en verplichtingen uit hoofde "
            "van deze overeenkomst tijdig over te dragen aan de Koper.")
LONG_EN = ("The Seller undertakes to transfer all rights and obligations under this "
           "Agreement to the Buyer in a timely manner.")
SHORT_SRC = "Bijlage een."
SHORT_EN = "Schedule 1."

PERMUTED = doc(para(SHORT_EN) + para(LONG_EN))
NOTES_OK = [{"idx": 0, "text": LONG_SRC, "en": LONG_EN},
            {"idx": 1, "text": SHORT_SRC, "en": SHORT_EN}]
old_n = len(OLD_QC.check_truncation(doc(para(SHORT_EN) + para(LONG_EN)), False, NOTES_OK))
new_n = len(NEW_QC.check_truncation(PERMUTED, False, NOTES_OK))
ok("L1 permuted document: silent now", new_n == 0, f"(new={new_n})")
ok("L1 permuted document: PROVED it fired before", old_n > 0, f"(old={old_n})")

# TRUE POSITIVE: a genuine truncation. The English really is a fraction of the source,
# and the paragraph is where the notes say it is, so there is nothing to un-pair.
TRUNC_EN = "The Seller undertakes to"
GENUINE = doc(para(TRUNC_EN))
NOTES_TRUNC = [{"idx": 0, "text": LONG_SRC, "en": TRUNC_EN}]
old_n = len(OLD_QC.check_truncation(doc(para(TRUNC_EN)), False, NOTES_TRUNC))
new_n = len(NEW_QC.check_truncation(GENUINE, False, NOTES_TRUNC))
ok("L1 TRUE POSITIVE genuine truncation: still fires", new_n > 0, f"(new={new_n})")
ok("L1 TRUE POSITIVE genuine truncation: fired before too", old_n > 0, f"(old={old_n})")

# AND a genuine truncation that is ALSO permuted: the fix must not let a real defect
# hide behind the reordering it was built to survive.
PERM_TRUNC = doc(para(SHORT_EN) + para(TRUNC_EN))
NOTES_PT = [{"idx": 0, "text": LONG_SRC, "en": TRUNC_EN},
            {"idx": 1, "text": SHORT_SRC, "en": SHORT_EN}]
new_n = len(NEW_QC.check_truncation(PERM_TRUNC, False, NOTES_PT))
ok("L1 TRUE POSITIVE truncation in a PERMUTED document: still fires", new_n > 0,
   f"(new={new_n})")

# =============================================================================
print("\nG11 — a dangling ending is not damage when the SOURCE dangles too")
print("-" * 96)

DANGLE_SRC = ("Il Venditore si impegna a trasferire tutti i diritti derivanti dal "
              "presente contratto al")
DANGLE_EN = ("The Seller undertakes to transfer all rights arising under this "
             "Agreement to the")
COMPLETE_SRC = ("Il Venditore si impegna a trasferire tutti i diritti derivanti dal "
                "presente contratto all'Acquirente.")

d = doc(para(DANGLE_EN))
notes = [{"idx": 0, "text": DANGLE_SRC, "en": DANGLE_EN}]
old_n = len(OLD_QC.check_truncation(doc(para(DANGLE_EN)), False, notes))
new_n = len(NEW_QC.check_truncation(d, False, notes))
ok("G11 source also dangles: silent now", new_n == 0, f"(new={new_n})")
ok("G11 source also dangles: PROVED it fired before", old_n > 0, f"(old={old_n})")

d = doc(para(DANGLE_EN))
notes = [{"idx": 0, "text": COMPLETE_SRC, "en": DANGLE_EN}]
new_n = len(NEW_QC.check_truncation(d, False, notes))
ok("G11 TRUE POSITIVE complete source, English cut short: still fires", new_n > 0,
   f"(new={new_n})")

# No notes at all means no evidence about the source, and no exemption.
d = doc(para(DANGLE_EN))
new_n = len(NEW_QC.check_truncation(d, False, None))
ok("G11 no source data: still fires (absence of evidence is not evidence)", new_n > 0,
   f"(new={new_n})")

# =============================================================================
print("\nG5 — an execution-block lead-in ends on its preposition by design")
print("-" * 96)

G5_CASES = [
    ("SIGNED for and on behalf of the Seller acting by", False),
    ("EXECUTED as a deed by the Buyer in the presence of", False),
    ("TRUE POSITIVE: the Supplier shall deliver the goods to the premises of", True),
    ("TRUE POSITIVE: payment falls due on the first Business Day of", True),
]
for text, want_fire in G5_CASES:
    d = doc(para(text))
    old_n = len(OLD_QC.check_truncation(doc(para(text)), False, None))
    new_n = len(NEW_QC.check_truncation(d, False, None))
    short = text[:46]
    if want_fire:
        ok(f"G5 '{short}...': still fires", new_n > 0, f"(new={new_n})")
        ok(f"G5 '{short}...': fired before too", old_n > 0, f"(old={old_n})")
    else:
        ok(f"G5 '{short}...': silent now", new_n == 0, f"(new={new_n})")
        ok(f"G5 '{short}...': PROVED it fired before", old_n > 0, f"(old={old_n})")

# =============================================================================
print("\nM1 — a numbering anomaly the document ARRIVED with is not ours")
print("-" * 96)


def numbered(numid, ilvl, text):
    return (f'<w:p><w:pPr><w:numPr><w:ilvl w:val="{ilvl}"/>'
            f'<w:numId w:val="{numid}"/></w:numPr></w:pPr>'
            f'<w:r><w:t xml:space="preserve">{text}</w:t></w:r></w:p>')


# A level jump of 0 -> 2, present identically in the source and in the delivered body.
JUMP_SRC = doc(numbered(3, 0, "Articolo 1") + numbered(3, 2, "Articolo 1.1.1"))
JUMP_DEL = doc(numbered(3, 0, "Clause 1") + numbered(3, 2, "Clause 1.1.1"))

old_n = len(OLD_QC.check_numbering(doc(numbered(3, 0, "Clause 1")
                                       + numbered(3, 2, "Clause 1.1.1")), False))
new_no_src = len(NEW_QC.check_numbering(JUMP_DEL, False))
new_with_src = len(NEW_QC.check_numbering(JUMP_DEL, False, JUMP_SRC))
ok("M1 inherited jump, --original supplied: silent now", new_with_src == 0,
   f"(new={new_with_src})")
ok("M1 inherited jump: PROVED it fired before", old_n > 0, f"(old={old_n})")
ok("M1 without --original: behaviour UNCHANGED, still fires", new_no_src == old_n,
   f"(new={new_no_src}, old={old_n})")

# TRUE POSITIVE: an anomaly in the delivered body that the source did not have -- what
# a skill Step 7 permutation breaking a numbered block would look like.
CLEAN_SRC = doc(numbered(3, 0, "Articolo 1") + numbered(3, 1, "Articolo 1.1"))
new_n = len(NEW_QC.check_numbering(JUMP_DEL, False, CLEAN_SRC))
ok("M1 TRUE POSITIVE jump absent from the source: still fires", new_n > 0,
   f"(new={new_n})")

# And the multiset really is a multiset: two jumps delivered, one in the source, one
# must survive. A set difference would wrongly silence both.
TWO_JUMPS = doc(numbered(3, 0, "a") + numbered(3, 2, "b")
                + numbered(4, 0, "c") + numbered(4, 2, "d"))
ONE_JUMP = doc(numbered(3, 0, "a") + numbered(3, 2, "b"))
new_n = len(NEW_QC.check_numbering(TWO_JUMPS, False, ONE_JUMP))
ok("M1 two delivered jumps against one inherited: exactly one survives", new_n == 1,
   f"(new={new_n})")

# =============================================================================
print("\nG9 — a del/ins boundary cannot produce a double space in either reading")
print("-" * 96)

L_DEL = {"type": "del", "en": "the earlier agreement "}
R_INS = {"type": "ins", "en": " the amended agreement"}
L_REG = {"type": "regular", "en": "subject to "}
R_INS2 = {"type": "ins", "en": " the amended agreement"}

old_h = OLD_VSS._rule_double_space_across_boundary(L_DEL, R_INS)
new_h = NEW_VSS._rule_double_space_across_boundary(L_DEL, R_INS)
ok("G9 del->ins double space: silent now", new_h is None, f"({new_h})")
ok("G9 del->ins double space: PROVED it fired before", old_h is not None)

# THE REVERSE ORDER NEEDS ITS OWN SEGMENTS, AND THE FIRST VERSION OF THIS CONTROL DID
# NOT. It reused the pair above with the arguments swapped -- but this rule keys on
# WHERE THE SPACES ARE, not on the segment types, so the swapped pair had no trailing
# space on the left and could never fire. It read as "the fix works" when the input
# was incapable of triggering the defect. Caught by the PROVED-it-fired-before
# assertion, which is exactly what that assertion is for.
L_INS = {"type": "ins", "en": "the amended agreement "}
R_DEL = {"type": "del", "en": " the earlier agreement"}
old_h = OLD_VSS._rule_double_space_across_boundary(L_INS, R_DEL)
new_h = NEW_VSS._rule_double_space_across_boundary(L_INS, R_DEL)
ok("G9 ins->del double space: silent now", new_h is None, f"({new_h})")
ok("G9 ins->del double space: PROVED it fired before", old_h is not None)

old_h = OLD_VSS._rule_double_space_across_boundary(L_REG, R_INS2)
new_h = NEW_VSS._rule_double_space_across_boundary(L_REG, R_INS2)
ok("G9 TRUE POSITIVE regular->ins double space: still fires", new_h is not None)
ok("G9 TRUE POSITIVE regular->ins double space: fired before too", old_h is not None)

for pair, label in ((({"type": "del", "en": "a "}, {"type": "del", "en": " b"}),
                     "del->del"),
                    (({"type": "ins", "en": "a "}, {"type": "ins", "en": " b"}),
                     "ins->ins")):
    new_h = NEW_VSS._rule_double_space_across_boundary(*pair)
    ok(f"G9 TRUE POSITIVE {label} double space: still fires", new_h is not None)

# =============================================================================
print("\nF10 — a del/ins pair cannot run two words together in either reading")
print("-" * 96)

# skill Step 4 MANDATES byte-identical English on both sides of an orthographic-only
# change, so the del ends with a letter and the ins begins with one -- and apply runs this
# scanner --strict, so the pair was a hard block on a translation that obeyed the rule.
# Accept-all renders the ins and drops the del, reject-all the reverse: no reading ever
# shows the two side by side. Register F10; 14.2 of PLAN-2-step-b.md section 3.14.
F10_DEL = {"type": "del", "en": "Agreement"}
F10_INS = {"type": "ins", "en": "Agreement"}
F10_TP = (
    ("regular 'the' before an ins 'Agreement', no space",
     {"type": "regular", "en": "the"}, {"type": "ins", "en": "Agreement"}),
    ("del->regular collision, G9's open half",
     {"type": "del", "en": "Agreement"}, {"type": "regular", "en": "shall"}),
)
# A whole paragraph as apply hands it over: the del->ins pair is its ONLY finding, so the
# --strict exit apply reads moves on F10 alone.
F10_PARA = [{"idx": 0, "text": "invented", "en": "the Agreement shall",
             "en_segments": [{"type": "regular", "en": "the "}, F10_DEL, F10_INS,
                             {"type": "regular", "en": " shall"}]}]
F10_JSON = TMP / "f10-paragraphs.json"
F10_JSON.write_text(json.dumps(F10_PARA), encoding="utf-8")
F10_ENV = dict(os.environ, PYTHONIOENCODING="utf-8")
# THE JOINS A VIEW RENDERS ACROSS A TRACKED CHANGE -- true positives the del<->ins exemption
# must not take with it, found by 14.2's review. With the del dropped, accept-all reads
# "theAgreement"; with the ins dropped, reject-all does. The old code caught each only by
# accident, firing on the del<->ins pair beside it; the new code must catch it as the join.
F10_JOINS = (
    ("accept-all", [{"type": "regular", "en": "the"}, {"type": "del", "en": " old"},
                    {"type": "ins", "en": "Agreement"}]),
    ("reject-all", [{"type": "regular", "en": "the"}, {"type": "ins", "en": " new"},
                    {"type": "del", "en": "Agreement"}]),
)
# And a del/ins pair that is NOT byte-identical, both views clean ("the Agreement", "the old"):
# the old code fired on the pair all the same.
F10_CLEAN = [{"type": "regular", "en": "the "}, {"type": "del", "en": "old"},
             {"type": "ins", "en": "Agreement"}]


def alpha_where(mod, segs, name):
    """Where validate() reports an alpha collision for one invented paragraph."""
    p = TMP / f"f10-{name}.json"
    p.write_text(json.dumps([{"idx": 0, "en_segments": segs}]), encoding="utf-8")
    return [w for e in mod.validate(str(p))[0] for _k, w, h in e["hits"]
            if h[0] == "alpha_collision_at_boundary"]


def strict_run(script_path):
    """rc and stdout of the scanner run as apply runs it: --strict, on the paragraph above."""
    r = subprocess.run([sys.executable, str(script_path), str(F10_JSON), "--strict"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace",
                       env=F10_ENV, cwd=TMP)
    return r.returncode, r.stdout + r.stderr


for tree in ("uk", "us"):
    old_vss = OLD_VSS if tree == "uk" else load_old("validate_segment_shapes.py", tree)
    new_vss = NEW_VSS if tree == "uk" else load_new("validate_segment_shapes.py", tree)
    for left, right, label in ((F10_DEL, F10_INS, "del->ins"), (F10_INS, F10_DEL, "ins->del")):
        old_h = old_vss._rule_alpha_collision_no_space(left, right)
        new_h = new_vss._rule_alpha_collision_no_space(left, right)
        ok(f"F10 {tree} byte-identical {label}: silent now", new_h is None, f"({new_h})")
        ok(f"F10 {tree} byte-identical {label}: PROVED it fired before",
           old_h is not None and old_h[0] == "alpha_collision_at_boundary", f"({old_h})")
    for label, left, right in F10_TP:
        old_h = old_vss._rule_alpha_collision_no_space(left, right)
        new_h = new_vss._rule_alpha_collision_no_space(left, right)
        ok(f"F10 {tree} TRUE POSITIVE {label}: still fires",
           new_h is not None and new_h[0] == "alpha_collision_at_boundary", f"({new_h})")
        ok(f"F10 {tree} TRUE POSITIVE {label}: fired before too",
           old_h is not None and old_h[0] == "alpha_collision_at_boundary", f"({old_h})")
    # THE EXIT APPLY READS, judged by CONTENT as well as rc: a run that crashed would also
    # exit 1, and would then read as "it blocked before" for the wrong reason.
    old_rc, old_out = strict_run(OLD_DIR / (tag(tree) + "validate_segment_shapes.py"))
    new_rc, new_out = strict_run(ROOT / tree / "scripts" / "validate_segment_shapes.py")
    ok(f"F10 {tree} --strict on the obeying paragraph: exits 0 now",
       new_rc == 0 and "alpha_collision_at_boundary" not in new_out, f"(rc={new_rc})")
    ok(f"F10 {tree} --strict on the obeying paragraph: PROVED it blocked before",
       old_rc == 1 and "alpha_collision_at_boundary" in old_out, f"(rc={old_rc})")
    for view, segs in F10_JOINS:
        old_w = alpha_where(old_vss, segs, f"old-{tree}-{view}")
        new_w = alpha_where(new_vss, segs, f"new-{tree}-{view}")
        ok(f"F10 {tree} TRUE POSITIVE run-together join in the {view} view: still fires, "
           f"as that join", any(f"({view})" in w for w in new_w), f"({new_w})")
        ok(f"F10 {tree} TRUE POSITIVE run-together join in the {view} view: fired before too",
           bool(old_w), f"({old_w})")
    old_w = alpha_where(old_vss, F10_CLEAN, f"old-{tree}-clean")
    new_w = alpha_where(new_vss, F10_CLEAN, f"new-{tree}-clean")
    ok(f"F10 {tree} differing del/ins pair, both views clean: silent now", not new_w,
       f"({new_w})")
    ok(f"F10 {tree} differing del/ins pair, both views clean: PROVED it fired before",
       bool(old_w), f"({old_w})")

# =============================================================================
print("\nG1 and G7 — an elision is no quote mark; a defined term or a title is translated by design")
print("-" * 96)

# skill Step 4's validate_translations warns when a quoted source span (2+ words in single
# quotes, 5+ in double) is not found verbatim in the English. G1: a straight apostrophe
# between two letters -- dell'articolo -- was paired as a quote mark, and the text between
# two of them read as a missing phrase. G7: a defined term in its (il "X") marker and a
# title after recante are translated by design, so they warned on every well-drafted
# contract. EACH EXEMPTION HOLDS ONLY WHILE THE ENGLISH KEEPS AS MANY QUOTED SPANS AS THE
# SOURCE: a term or a title dropped together with its quotes is the true positive a bare
# exemption would silence -- 14.2's review lesson, asked of every exemption here. Register G1
# and G7; 14.3 of PLAN-2-step-b.md section 3.14. Every string INVENTED.
# --- 14.3 cases: begin
G1G7_FP = (
    ("G1 two elisions paired as a quote",
     "Ai fini dell'articolo 5 e nel rispetto delle condizioni dell'Accordo, il Venditore consegna i beni.",
     "For the purposes of clause 5 and subject to the conditions of the Agreement, the Seller delivers the goods."),
    ("G7 a defined term in its (il \"X\") marker",
     "Il Cliente e l'Appaltatore stipulano il presente contratto (il \"Contratto Quadro per i Servizi di Pulizia\").",
     "The Client and the Contractor enter into this contract (the \"Cleaning Services Framework Contract\")."),
    ("G7 a marker with a lead-in, (di seguito, congiuntamente, gli \"X\")",
     "Le parti hanno sottoscritto due accordi (di seguito, congiuntamente, gli \"Accordi Quadro per la Manutenzione "
     "degli Uffici\").",
     "The parties have signed two agreements (hereinafter, together, the \"Office Upkeep Framework Arrangements\")."),
    ("G7 an English (the \"X\") marker",
     "The Contractor shall perform the services (the \"Long Term Office Cleaning and Catering Works\").",
     "The Contractor shall perform the services (the \"Long-Term Office Cleaning and Catering Works\")."),
    ("G7 a title after recante",
     "Si applica il Decreto Legislativo n. 99 del 2001, recante \"Disposizioni per la tutela dei giardini storici "
     "urbani\", come modificato.",
     "Legislative Decree No. 99 of 2001, laying down \"Provisions for the protection of historic urban gardens\", as "
     "amended, applies."),
    ("G7 a title after entitled",
     "The parties shall follow the procedure entitled \"Inspection of Office Lifts and Escalators Each Month\".",
     "The parties shall follow the procedure entitled \"Monthly Inspection of Lifts and Escalators in Offices\"."),
    # An apostrophe after a letter never OPENS a quotation -- the review's finding, 2026-10-30.
    ("G1 two plural possessives paired as a quote",
     "The Parties' rights under clause 5 and the Sellers' duties remain in force.",
     "The rights of the Parties under clause 5 and the duties of the Sellers remain in force."),
)
# (label, source, English, the phrase the new code must report)
G1G7_TP = (
    ("a quoted project name dropped",
     "Il Cliente realizza il progetto 'Centro Servizi Delta Nord' entro il 2030.",
     "The Client builds the service centre project by 2030.", "Centro Servizi Delta Nord"),
    ("a third-party title with no marker",
     "L'Appaltatore rispetta il documento \"Linee Guida per la Gestione delle Mense Aziendali\" del Cliente.",
     "The Contractor complies with the canteen guidelines of the Client.",
     "Linee Guida per la Gestione delle Mense Aziendali"),
    ("a name holding an elision, dropped: now read WHOLE",
     "Il sito del progetto 'Residenza dell'Orto Fiorito' resta invariato.",
     "The project site remains unchanged.", "Residenza dell'Orto Fiorito"),
    ("a name after an elision, dropped: now checked ITSELF",
     "Ai fini dell'immobile il progetto 'Centro Servizi Delta Sud' resta invariato.",
     "For the purposes of the building the project remains unchanged.", "Centro Servizi Delta Sud"),
    ("a marker dropped with its quotes",
     "Il Cliente e l'Appaltatore stipulano il presente contratto (il \"Contratto Quadro per i Servizi di Pulizia\").",
     "The Client and the Contractor enter into this cleaning contract.", "Contratto Quadro per i Servizi di Pulizia"),
    ("a title dropped with its quotes",
     "Si applica il Decreto Legislativo n. 99 del 2001, recante \"Disposizioni per la tutela dei giardini storici "
     "urbani\", come modificato.",
     "Legislative Decree No. 99 of 2001, as amended, applies.",
     "Disposizioni per la tutela dei giardini storici urbani"),
    ("a name beside a kept marker, the name dropped with its quotes",
     "Il Cliente noleggia l'attrezzatura 'Centro Servizi Delta Nord' (il \"Contratto di Noleggio dell'Attrezzatura "
     "da Ufficio\").",
     "The Client hires the equipment (the \"Office Equipment Hire Contract\").", "Centro Servizi Delta Nord"),
    # The English keeps a quoted span, so the quote-count condition holds and only the verb
    # decides: with the English unquoted, the condition alone re-checks the span, and a naming
    # verb wrongly made a title verb went unseen -- caught by mutation on 2026-10-30.
    ("a NAMING verb is not a title verb",
     "Il progetto denominato \"Centro Servizi del Quartiere Alto Verde\" è autorizzato.",
     "The project \"Upper Green District Service Centre\" is authorised.",
     "Centro Servizi del Quartiere Alto Verde"),
    ("a marker left open is no marker",
     "Le opere comprendono (il \"Contratto Quadro per i Servizi di Pulizia\" e i relativi allegati).",
     "The works include (the \"Cleaning Services Framework Contract\" and its annexes).",
     "Contratto Quadro per i Servizi di Pulizia"),
    ("G7's DECLARED RESIDUAL, a quoted contractual phrase",
     "Le opere sono eseguite \"secondo le migliori pratiche del settore\" dall'Appaltatore.",
     "The works are performed in line with \"industry best practice\" by the Contractor.",
     "secondo le migliori pratiche del settore"),
    # The review's two findings, 2026-10-30: possessives once counted as a quoted span in the
    # English, so the quote-count condition held over a marker dropped with its quotes; and a
    # lead-in could BEGIN with a generic word, so a cross-reference passed for a marker.
    ("a marker dropped, the English holding plural possessives",
     "Il Cliente e l'Appaltatore stipulano il presente contratto (il \"Contratto Quadro per i Servizi di Pulizia\").",
     "The Parties' rights and the Sellers' duties are set out in this cleaning contract.",
     "Contratto Quadro per i Servizi di Pulizia"),
    ("a cross-reference is no marker",
     "The works follow the procedure (as defined in the \"Regional Rules for Public Works Tenders\").",
     "The works follow the procedure (as defined in the \"Regional Public Works Tendering Rules\").",
     "Regional Rules for Public Works Tenders"),
)
# --- 14.3 cases: end


def vt_run(script_dir, name, case):
    """rc and output of validate_translations run as skill Step 4 runs it, on one paragraph alone,
    in a workdir of its own (the script writes its batch state beside the notes)."""
    wd = TMP / f"vt-{name}"
    wd.mkdir()
    pj = wd / "paragraphs.json"
    pj.write_text(json.dumps([{"idx": 0, "text": case[1], "en": case[2]}]), encoding="utf-8")
    r = subprocess.run([sys.executable, str(script_dir / "validate_translations.py"), str(pj)],
                       capture_output=True, text=True, encoding="utf-8", errors="replace",
                       env=F10_ENV, cwd=wd)
    return r.returncode, r.stdout + r.stderr


for tree in ("uk", "us"):
    old_vt = load_old("validate_translations.py", tree)
    new_vt = load_new("validate_translations.py", tree)
    for label, src, en in G1G7_FP:
        old_f = old_vt._check_quoted_phrase_retention({"text": src, "en": en})
        new_f = new_vt._check_quoted_phrase_retention({"text": src, "en": en})
        ok(f"{label} ({tree}): silent now", not new_f, f"({new_f})")
        ok(f"{label} ({tree}): PROVED it fired before", bool(old_f), f"({old_f})")
    for label, src, en, phrase in G1G7_TP:
        old_f = old_vt._check_quoted_phrase_retention({"text": src, "en": en})
        new_f = new_vt._check_quoted_phrase_retention({"text": src, "en": en})
        ok(f"G1/G7 {tree} TRUE POSITIVE {label}: still fires, on that phrase",
           phrase in [p for _s, p in new_f], f"({new_f})")
        ok(f"G1/G7 {tree} TRUE POSITIVE {label}: fired before too", bool(old_f), f"({old_f})")
    # The elision TP pair shows what the old pairing did to a real name: it was never read as itself.
    for label, src, en, phrase in G1G7_TP[2:4]:
        old_f = old_vt._check_quoted_phrase_retention({"text": src, "en": en})
        ok(f"G1/G7 {tree} {label}: the old code never read that phrase",
           phrase not in [p for _s, p in old_f], f"({old_f})")
    # THE EXIT skill Step 4 reads, judged by CONTENT as well as rc: a crash also exits non-zero.
    old_dir = TMP / f"old_vt_{tree}"
    old_dir.mkdir()
    for name in ("validate_translations.py", "source_language_markers.py"):
        (old_dir / name).write_bytes(subprocess.run(["git", "show", f"{REF}:{tree}/scripts/{name}"],
                                                    capture_output=True, cwd=ROOT, check=True).stdout)
    for row, case in (("G1", G1G7_FP[0]), ("G7", G1G7_FP[1])):
        old_rc, old_out = vt_run(old_dir, f"old-{tree}-{row}", case)
        new_rc, new_out = vt_run(ROOT / tree / "scripts", f"new-{tree}-{row}", case)
        ok(f"{row} {tree} {case[0]}, the whole script: exits 0 now, PASS and no quoted-phrase WARN",
           new_rc == 0 and "PASS" in new_out and "Quoted source phrases" not in new_out, f"(rc={new_rc})")
        ok(f"{row} {tree} {case[0]}, the whole script: PROVED it warned before",
           old_rc == 1 and "Quoted source phrases NOT found" in old_out, f"(rc={old_rc})")

# =============================================================================
print("\nG2, G8 and G14 — 'Article N' warns on an internal reference, never on a citation of legislation")
print("-" * 96)

# lexicon_compliance's WARN that 'Article N' for an internal reference should read 'Clause N'.
# G2 and G8: it fired on nearly every civil-law statute -- a decree with no 'the' before it, and
# a citation with a paragraph, a letter or a list between the number and the code. G14, the
# missed alarm, runs the OTHER way: a bare 'of the' read as legislation, so 'Article 7 of the
# Agreement' was silent where 'of this Agreement' warned. So this section asserts four sets:
# the measured false positives silent now and PROVED to have fired; every legislation form the
# bare 'of the' silenced, quiet then and quiet now; the true positives firing then and now; and
# the missed alarm firing now and PROVED silent then. Register G2, G8 and G14; 14.4 of
# PLAN-2-step-b.md section 3.14. Every string INVENTED.
# --- 14.4 cases: begin
LC_FP = (
    ("G2 a decree with no 'the'", "Article 5 of Legislative Decree No. 9 of 2001 governs the office lease."),
    ("G2 a -bis article of a decree", "Article 5-bis of Legislative Decree No. 9 of 2001 governs the office lease."),
    ("G8 ', <ordinal> paragraph,' before the Civil Code",
     "Article 1600, second paragraph, of the Civil Code applies to the cleaning terms."),
    ("G8 ', paragraph N,' before a named Decree", "Article 5, paragraph 2, of the Catering Decree applies."),
    ("G8 ', paragraph N' with no second comma", "Article 5, paragraph 2 of the Catering Decree applies."),
    ("G8 a paragraph before a decree with no 'the'",
     "Article 5, second paragraph, of Presidential Decree No. 7 applies."),
    ("G8 'that' pointing back to a decree", "Article 5, second paragraph, of that Presidential Decree applies."),
    ("G8 a paragraph and a letter", "Article 5, paragraph 1, letter a), of Legislative Decree No. 9 applies."),
    ("G8 two letters", "Article 5, letters a) and b) of the Catering Decree apply."),
    ("G8 a list running on to a further article",
     "Article 5, paragraph 1, and Article 9, paragraph 2, of the Catering Decree apply."),
    ("G8 a list of further articles",
     "Article 1600, second paragraph, or Articles 1601 and 1602 of the Civil Code apply."),
    # The review's finding, 2026-10-30: an abbreviated decree is a decree.
    ("G2 an abbreviated decree with no 'the'", "Article 5 of D.Lgs. 9/2001 governs the office lease."),
)
# Quiet BEFORE as well: the legislation forms the bare 'of the' silenced, which the narrowing must not bring back --
# the brief's seven, the three measured on the corpus, and the outside instruments that number by Article.
LC_KEPT = tuple("Article 5 " + tail + " applies to the canteen." for tail in (
    "of the Civil Code", "of the Italian Civil Code", "of the Italian Code of Civil Procedure",
    "of the Legislative Decree No. 9", "of the Catering Decree", "of the said Decree", "of the Decree-Law",
    "of the Authority Resolution", "of the Companies Act 2006", "of the Treaty on the Functioning of the European Union",
    "of the Data Regulation", "of the Services Directive", "of the Constitution", "of the Law", "of the Statute",
    "of the Vienna Convention", "of the Charter", "of the Ordinance", "of the Arbitration Rules",
    "of the Articles of Association", "of the By-laws", "of the GDPR", "of the TFEU", "of the TEU",
    "of the European Union", "of Book 6 of the Civil Code", "of Law No. 9",
    # The review's findings, 2026-10-30: a year or an abbreviation before the instrument is still legislation.
    "of the 1998 Act", "of the 2016 Regulation", "of the U.K. Companies Act", "of the D.Lgs. 9/2001",
    "of the D.P.R. No. 7"))
# Firing before AND after: an internal reference, with or without something between the number and its tail.
LC_TP = (
    ("an internal locator", "Article 7 above applies to the Client."),
    ("an inward 'this'", "Article 7 of this Agreement applies to the Client."),
    ("a paragraph before an inward 'this'", "Article 7, paragraph 2, of this Agreement applies to the Client."),
    ("a list before an inward 'this'", "Article 7 and Article 9 of this Agreement apply to the Client."),
    ("a -bis article of the contract", "Article 7-bis of the Contract applies to the Client."),
    ("a paragraph before the agreement", "Article 7, paragraph 2, of the Agreement applies to the Client."),
    ("a list before the agreement", "Article 7 and Article 9 of the Agreement apply to the Client."),
)
# G14, THE MISSED ALARM: silent before, firing now -- and the bridges a looser tail would have let through.
LC_ALARM = (
    ("G14 'of the Agreement'", "The Contractor acts under Article 7 of the Agreement."),
    ("G14 a possessive before the agreement", "The Contractor acts under Article 7 of the Caterers' Agreement."),
    ("G14 'of the Deed'", "The Contractor acts under Article 7 of the Deed."),
    ("G14 a named contract", "The Contractor acts under Article 7 of the Cleaning Contract."),
    ("G14 no bridge across 'and' to a code", "Article 7 of the Agreement and the Code apply to the Client."),
    # With no 'the' after the connective, so the stop on 'the' cannot hide the stop on 'and' -- the case above
    # passed against a mutant that let 'and' and 'or' through, caught by mutation on 2026-10-30.
    ("G14 no bridge across 'and' to a regulation", "Under Article 7 of the Agreement and Regulation 5, the Client pays."),
    ("G14 no bridge across 'or' to a regulation", "Under Article 7 of the Agreement or Regulation 5, the Client pays."),
    ("G14 no bridge across 'that' to a regulation",
     "Under Article 7 of the Agreement that Regulation 5 mentions, the Client pays."),
    # The bare 'of the' had no word boundary: it read 'of these' and 'of their' as legislation too.
    ("G14 'of these', which the bare 'of the' matched as a prefix",
     "The Contractor acts under Article 7 of these Rules."),
    ("G14 'of their', which it matched the same way", "The Parties act under Article 7 of their Agreement."),
    # The review's findings, 2026-10-30: a naming word ending on a full stop let the tail cross a sentence, and the
    # head 'Charter' read a charterparty -- the parties' own contract -- as an outside instrument.
    ("G14 no bridge across a full stop", "The Buyer pays under Article 7 of the Agreement. Law 9 applies too."),
    ("G14 a charterparty is a contract", "The Owner acts under Article 7 of the Charter Party."),
)
# --- 14.4 cases: end


def art_warns(mod, text):
    """The 'Article N' warnings the module's own scan() makes on one English paragraph."""
    _blocks, warns = mod.scan([("en", 0, text)], "*")
    return [w for w in warns if "'Article N'" in w]


def lc_run(script_dir, name, text, *flags):
    """rc and output of lexicon_compliance run as skill Step 4 runs it, on one paragraph, in a workdir of its own."""
    wd = TMP / f"lc-{name}"
    wd.mkdir()
    pj = wd / "paragraphs.json"
    pj.write_text(json.dumps([{"idx": 0, "text": "Testo.", "en": text}]), encoding="utf-8")
    r = subprocess.run([sys.executable, str(script_dir / "lexicon_compliance.py"), str(pj), "--stage", "pre-apply",
                        "--language", "none", *flags],
                       capture_output=True, text=True, encoding="utf-8", errors="replace", env=F10_ENV, cwd=wd)
    return r.returncode, r.stdout + r.stderr


for tree in ("uk", "us"):
    old_lc = load_old("lexicon_compliance.py", tree)
    new_lc = load_new("lexicon_compliance.py", tree)
    # load_old wrote the pinned uk copy over the WORKING-TREE copy placed in OLD_DIR above for the old modules to
    # import; put that back, so what a later section imports never depends on where this one sits (the review, 2026-10-30).
    shutil.copyfile(ROOT / "uk" / "scripts" / "lexicon_compliance.py", OLD_DIR / "lexicon_compliance.py")
    for label, text in LC_FP:
        ok(f"{label} ({tree}): silent now", not art_warns(new_lc, text), f"({art_warns(new_lc, text)})")
        ok(f"{label} ({tree}): PROVED it fired before", bool(art_warns(old_lc, text)))
    quiet_new = [t for t in LC_KEPT if art_warns(new_lc, t)]
    quiet_old = [t for t in LC_KEPT if art_warns(old_lc, t)]
    ok(f"G14 {tree} {len(LC_KEPT)} legislation forms the bare 'of the' silenced: every one quiet now",
       not quiet_new, f"({quiet_new})")
    ok(f"G14 {tree} the same {len(LC_KEPT)}: every one PROVED quiet before (the set is the one it silenced)",
       not quiet_old, f"({quiet_old})")
    for label, text in LC_TP:
        ok(f"G2/G8 {tree} TRUE POSITIVE {label}: still fires", bool(art_warns(new_lc, text)))
        ok(f"G2/G8 {tree} TRUE POSITIVE {label}: fired before too", bool(art_warns(old_lc, text)))
    for label, text in LC_ALARM:
        ok(f"{label} ({tree}): fires now", bool(art_warns(new_lc, text)))
        ok(f"{label} ({tree}): PROVED silent before -- the alarm that was missed", not art_warns(old_lc, text))
    # THE EXIT skill Step 4 reads, judged by CONTENT as well as rc: a WARN stays a WARN, so rc 0 both ways, and only
    # --warnings-are-errors turns the warning into the exit -- 1 then 0 on G2, 0 then 1 on the alarm.
    old_dir = TMP / f"old_lc_{tree}"
    old_dir.mkdir()
    for name in ("lexicon_compliance.py", "source_language_markers.py"):
        (old_dir / name).write_bytes(subprocess.run(["git", "show", f"{REF}:{tree}/scripts/{name}"],
                                                    capture_output=True, cwd=ROOT, check=True).stdout)
    for row, text, before, after in (("G2", LC_FP[0][1], 1, 0), ("G14", LC_ALARM[0][1], 0, 1)):
        o_rc, o_out = lc_run(old_dir, f"old-{tree}-{row}", text)
        n_rc, n_out = lc_run(ROOT / tree / "scripts", f"new-{tree}-{row}", text)
        ok(f"{row} {tree} the whole script, as run: rc 0 before and after, {before} then {after} warning, PASSED",
           o_rc == 0 and n_rc == 0 and f"warnings:            {before}" in o_out
           and f"warnings:            {after}" in n_out and "PASSED" in o_out and "PASSED" in n_out,
           f"(rc {o_rc}/{n_rc})")
        o_rc, o_out = lc_run(old_dir, f"old-{tree}-{row}-wae", text, "--warnings-are-errors")
        n_rc, n_out = lc_run(ROOT / tree / "scripts", f"new-{tree}-{row}-wae", text, "--warnings-are-errors")
        ok(f"{row} {tree} the whole script under --warnings-are-errors: rc {before} then {after}, by content",
           (o_rc, n_rc) == (before, after)
           and ("'Article N'" in o_out and "BLOCKED" in o_out) == bool(before)
           and ("'Article N'" in n_out and "BLOCKED" in n_out) == bool(after), f"(rc {o_rc}/{n_rc})")

# =============================================================================
print("\nF15 — a scaffold preserved verbatim IS filled in")
print("-" * 96)

WORK = TMP / "thf"
WORK.mkdir()


def build_hf_docx(path):
    """A .docx with one footer holding a single page-number placeholder paragraph."""
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("[Content_Types].xml",
                   '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                   '<Types xmlns="http://schemas.openxmlformats.org/package/2006/'
                   'content-types"><Default Extension="xml" ContentType="application/'
                   'xml"/></Types>')
        z.writestr("word/document.xml",
                   '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                   f'<w:document xmlns:w="{W}"><w:body>'
                   '<w:p><w:r><w:t>Body.</w:t></w:r></w:p></w:body></w:document>')
        z.writestr("word/footer1.xml",
                   '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                   f'<w:ftr xmlns:w="{W}"><w:p><w:r>'
                   '<w:t xml:space="preserve">Page 1 of 3</w:t></w:r></w:p></w:ftr>')
    return path


HF = build_hf_docx(WORK / "src.docx")
VERBATIM = [{"source": "word/footer1.xml", "p_idx": 0,
             "text": "Page 1 of 3", "en": "Page 1 of 3"}]
UNFILLED = [{"source": "word/footer1.xml", "p_idx": 0,
             "text": "Page 1 of 3", "en": None}]

for name, entries, want_ok in (("verbatim (en == text)", VERBATIM, True),
                               ("TRUE POSITIVE unfilled (en == null)", UNFILLED, False)):
    sj = WORK / f"scaffold-{abs(hash(name))}.json"
    sj.write_text(json.dumps(entries), encoding="utf-8")
    outs = [WORK / f"out-old-{abs(hash(name))}", WORK / f"out-new-{abs(hash(name))}"]
    old_r = OLD_THF.apply_from_scaffold(str(HF), str(sj), str(outs[0]))
    new_r = NEW_THF.apply_from_scaffold(str(HF), str(sj), str(outs[1]))
    if want_ok:
        ok(f"F15 {name}: exits clean now", bool(new_r) is True, f"(new={new_r})")
        ok(f"F15 {name}: PROVED it failed before", bool(old_r) is False,
           f"(old={old_r})")
    else:
        ok(f"F15 {name}: still refuses", bool(new_r) is False, f"(new={new_r})")
        ok(f"F15 {name}: refused before too", bool(old_r) is False, f"(old={old_r})")

# =============================================================================
print("\nC9 — the source language comes from the ORIGINAL, and only on agreement")
print("-" * 96)


def build_docx_with_body(path, text):
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("word/document.xml",
                   '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                   f'<w:document xmlns:w="{W}"><w:body><w:p><w:r>'
                   f'<w:t xml:space="preserve">{text}</w:t></w:r></w:p>'
                   '</w:body></w:document>')
    return path


DUTCH = (" De partijen bij deze overeenkomst komen het volgende overeen. "
         " De bijlage bij deze overeenkomst maakt daarvan integraal deel uit. "
         " De partijen verklaren dat de onderhavige overeenkomst volledig is. "
         " De wederpartij zal de bijlage ondertekenen. ") * 6
ENGLISH_ONLY = ("The parties to this agreement hereby agree as follows. " * 20)

d_docx = build_docx_with_body(WORK / "orig-nl.docx", DUTCH)
e_docx = build_docx_with_body(WORK / "orig-en.docx", ENGLISH_ONLY)

got_nl = NEW_RPK._detect_source_language(str(d_docx))
ok("C9 unambiguous Dutch original: both detectors agree on 'dutch'", got_nl == "dutch",
   f"(got {got_nl!r})")

got_en = NEW_RPK._detect_source_language(str(e_docx))
ok("C9 no agreement: returns None rather than a confident wrong answer",
   got_en is None, f"(got {got_en!r})")

ok("C9 unreadable original: returns None, never raises",
   NEW_RPK._detect_source_language(str(WORK / "does-not-exist.docx")) is None)

# THE BEHAVIOURAL HALF. The point of C9 is not the detector, it is that the language
# REACHES the pre-repack scan -- which is what was missing. Record the argv the gate
# would be invoked with, rather than asserting on the source text of the caller.
recorded = []
_real = NEW_RPK._run_pre_repack_validator


def _recorder(label, args):
    recorded.append((label, list(args)))
    raise SystemExit(0)      # stop before anything is written


NEW_RPK._run_pre_repack_validator = _recorder
try:
    try:
        NEW_RPK.repack(str(d_docx), str(WORK / "nope.xml"), str(WORK / "out.docx"),
                       paragraphs_json=str(WORK / "nope.json"))
    except SystemExit:
        pass
finally:
    NEW_RPK._run_pre_repack_validator = _real

got_args = recorded[0][1] if recorded else []
ok("C9 the pre-repack lexicon scan is the FIRST gate invoked",
   bool(recorded) and "lexicon_compliance" in recorded[0][0],
   f"({recorded[0][0] if recorded else 'nothing recorded'})")
# BRANCH 12 SLICE 12a (2026-10-09): the language is now the one DECLARED at Step 1c, read by the scan
# through --notes; this fixture declares nothing, so the original's agreement still REACHES the scan --
# as --guessed, which the scan reports as a guess rather than PASSED. Same language, same rules.
ok("C9 the original's agreement IS passed, from the original — as --guessed, nothing being declared",
   "--guessed" in got_args and got_args[got_args.index("--guessed") + 1] == "dutch",
   f"(args tail: {got_args[-4:] if got_args else []})")
ok("C9 and the scan is told where the notes are, so it can read a declaration",
   "--notes" in got_args and got_args[got_args.index("--notes") + 1] == str(WORK / "nope.json"),
   f"(args tail: {got_args[-4:] if got_args else []})")
ok("C9 the scan still reads the TRANSLATED document, not the original",
   any(str(WORK / "nope.xml") == a for a in got_args))

# And with no agreement, no --language: today's behaviour, not a wrong one.
recorded.clear()
NEW_RPK._run_pre_repack_validator = _recorder
try:
    try:
        NEW_RPK.repack(str(e_docx), str(WORK / "nope.xml"), str(WORK / "out.docx"),
                       paragraphs_json=str(WORK / "nope.json"))
    except SystemExit:
        pass
finally:
    NEW_RPK._run_pre_repack_validator = _real
got_args = recorded[0][1] if recorded else []
ok("C9 on detector disagreement, no --language and no --guessed is passed",
   "--language" not in got_args and "--guessed" not in got_args,
   f"(args tail: {got_args[-4:] if got_args else []})")

# =============================================================================
print("\nG7 in every language — each language's marker and title translated by design; the low opening quote read")
print("-" * 96)

# 14.3 exempted a defined term in its marker and a title after a title word in Italian and English
# only. Wouter, 2026-10-30: "for all languages we should do this". So each language's marker and
# title form is silent now and PROVED to have fired at the pinned baseline; the same term or title
# dropped with its quotes, a naming verb and a cross-reference still fire, now and before. The
# low opening quote (Polish, Hungarian, Dutch; German) was never read, so a marker in it is proved
# through its typographic twin, and a name dropped in it fires now and was PROVED silent before.
# Japanese and Chinese spans held no space, so were one word under every threshold: their marker was
# moot, and a name dropped in them was not seen -- a blind spot 14.9.7 read, its own section below
# proving the name dropped now fires; the markers stay silent here. Every exemption still holds only while the
# English keeps as many quoted spans as the source. 14.5 of PLAN-2-step-b.md section 3.14; every
# string INVENTED, on office services.
# --- 14.5 cases: begin
KEEP = 'The parties enter into this contract (the "Office Cleaning Services Contract").'
DROP = "The parties enter into this office cleaning contract."
TKEEP = 'The Contractor follows the procedure entitled "Monthly inspection of lifts and escalators".'
TDROP = "The Contractor follows the monthly lift inspection procedure."
# (language, shape, source, the span) -- each FP silent with KEEP/TKEEP, each span firing with DROP/TDROP
G7L = (
    ("Italian", "a lead-in, no article",
     'Le parti stipulano il contratto (di seguito "Contratto Quadro per i Servizi di Pulizia").',
     "Contratto Quadro per i Servizi di Pulizia"),
    ("English", "a lead-in, no article",
     'The parties enter into a contract (hereinafter "Long Term Office Cleaning and Catering Contract").',
     "Long Term Office Cleaning and Catering Contract"),
    ("English", "an indefinite article",
     'The parties enter into a contract (each a "Party to the Office Upkeep Arrangement").',
     "Party to the Office Upkeep Arrangement"),
    ("French", "marker",
     "Les parties concluent le présent contrat (ci-après dénommé le « Contrat de Services de Nettoyage des "
     "Bureaux »).", "Contrat de Services de Nettoyage des Bureaux"),
    ("French", "marker with an adverb",
     "Les sociétés signent le contrat (ci-après ensemble les « Parties au Contrat de Nettoyage des Bureaux »).",
     "Parties au Contrat de Nettoyage des Bureaux"),
    ("French", "title",
     "Le Prestataire applique la procédure intitulée « Contrôle mensuel des ascenseurs et des escaliers "
     "mécaniques ».", "Contrôle mensuel des ascenseurs et des escaliers mécaniques"),
    ("Spanish", "marker",
     "Las partes celebran el presente contrato (en adelante, el “Contrato de Servicios de Limpieza de "
     "Oficinas”).", "Contrato de Servicios de Limpieza de Oficinas"),
    ("Spanish", "title",
     "El Contratista sigue el procedimiento titulado “Inspección mensual de ascensores y escaleras "
     "mecánicas”.", "Inspección mensual de ascensores y escaleras mecánicas"),
    ("Portuguese", "marker",
     "As partes celebram o presente contrato (doravante designado “Contrato de Serviços de Limpeza de "
     "Escritórios”).", "Contrato de Serviços de Limpeza de Escritórios"),
    ("Portuguese", "title",
     "O Prestador segue o procedimento intitulado “Inspeção mensal de elevadores e escadas rolantes”.",
     "Inspeção mensal de elevadores e escadas rolantes"),
    ("German", "marker, a participle closing it",
     'Die Parteien schließen den Vertrag (nachfolgend "Vertrag über die Reinigung der Büroräume" genannt).',
     "Vertrag über die Reinigung der Büroräume"),
    ("German", "marker in the low opening quote",
     "Die Parteien schließen den Vertrag (im Folgenden „Vertrag über die Reinigung der Büroräume“).",
     "Vertrag über die Reinigung der Büroräume"),
    ("German", "title",
     'Der Auftragnehmer befolgt das Verfahren mit dem Titel "Monatliche Prüfung der Aufzüge und Fahrtreppen".',
     "Monatliche Prüfung der Aufzüge und Fahrtreppen"),
    ("Dutch", "marker",
     "Partijen sluiten de overeenkomst (hierna te noemen: “Overeenkomst inzake de Schoonmaak van "
     "Kantoren”).", "Overeenkomst inzake de Schoonmaak van Kantoren"),
    ("Dutch", "title",
     "De Opdrachtnemer volgt de procedure getiteld “Maandelijkse keuring van liften en roltrappen”.",
     "Maandelijkse keuring van liften en roltrappen"),
    ("Polish", "marker",
     'Strony zawierają umowę (zwaną dalej "Umową o Świadczenie Usług Sprzątania Biur").',
     "Umową o Świadczenie Usług Sprzątania Biur"),
    ("Polish", "marker in the low opening quote",
     "Strony zawierają umowę (dalej: „Umowa o Świadczenie Usług Sprzątania Biur”).",
     "Umowa o Świadczenie Usług Sprzątania Biur"),
    ("Polish", "title",
     'Wykonawca stosuje procedurę pod tytułem "Comiesięczny przegląd wind i schodów ruchomych".',
     "Comiesięczny przegląd wind i schodów ruchomych"),
    ("Hungarian", "marker",
     'A Felek megkötik a szerződést (a továbbiakban: "Irodatakarítási Szolgáltatási Szerződés a Központi '
     'Épületre").', "Irodatakarítási Szolgáltatási Szerződés a Központi Épületre"),
    ("Hungarian", "marker in the low opening quote",
     "A Felek megkötik a szerződést (a továbbiakban: „Irodatakarítási Szolgáltatási Szerződés a Központi "
     "Épületre”).", "Irodatakarítási Szolgáltatási Szerződés a Központi Épületre"),
    ("Hungarian", "title, the title word after it",
     'A Vállalkozó a "Liftek és mozgólépcsők havi ellenőrzésének eljárása" című eljárást követi.',
     "Liftek és mozgólépcsők havi ellenőrzésének eljárása"),
    ("Finnish", "marker",
     'Osapuolet tekevät sopimuksen (jäljempänä "Toimistojen Siivouspalveluja Koskeva Sopimus '
     'Keskusrakennuksessa").', "Toimistojen Siivouspalveluja Koskeva Sopimus Keskusrakennuksessa"),
    ("Finnish", "title",
     'Toimittaja noudattaa menettelyä otsikolla "Hissien ja liukuportaiden kuukausittainen tarkastus '
     'toimistoissa".', "Hissien ja liukuportaiden kuukausittainen tarkastus toimistoissa"),
    ("Norwegian", "marker",
     'Partene inngår avtalen (heretter kalt "Avtale om Renhold av Kontorlokaler i Sentrum").',
     "Avtale om Renhold av Kontorlokaler i Sentrum"),
    # The review's findings, 2026-11-02: the measured Dutch article after a lead-in, the other two
    # participles, and the other Hungarian title word, each had no control.
    ("Dutch", "marker, an article after the lead-in (measured)",
     "Partijen sluiten de overeenkomst (hierna: de “Overeenkomst inzake de Schoonmaak van Kantoren”).",
     "Overeenkomst inzake de Schoonmaak van Kantoren"),
    ("Dutch", "marker, a participle closing it",
     "Partijen sluiten de overeenkomst (hierna “Overeenkomst inzake de Schoonmaak van Kantoren” genoemd).",
     "Overeenkomst inzake de Schoonmaak van Kantoren"),
    ("German", "marker, an article and another participle",
     'Die Parteien schließen den Vertrag (nachstehend der "Vertrag über die Reinigung der Büroräume" bezeichnet).',
     "Vertrag über die Reinigung der Büroräume"),
    ("Hungarian", "title, the other title word after it",
     'A Vállalkozó a "Liftek és mozgólépcsők havi ellenőrzésének eljárása" címmel kiadott eljárást követi.',
     "Liftek és mozgólépcsők havi ellenőrzésének eljárása"),
)
# AN ARTICLE ALONE is the DECLARED language's: one language's article is another's preposition, and
# "(de X)" in Spanish is a reference -- the review's finding, 2026-11-02. (declared language, source,
# the span, whether it must be quiet with that language declared)
G7L_ALONE = (
    ("dutch", "Partijen sluiten de overeenkomst (de “Overeenkomst inzake de Schoonmaak van Kantoren”).",
     "Overeenkomst inzake de Schoonmaak van Kantoren", True),
    ("hungarian", 'A Felek megkötik a szerződést (a "Irodatakarítási Szolgáltatási Szerződés a Központi Épületre").',
     "Irodatakarítási Szolgáltatási Szerződés a Központi Épületre", True),
    ("german", 'Die Parteien schließen den Vertrag (der "Vertrag über die Reinigung der Büroräume").',
     "Vertrag über die Reinigung der Büroräume", True),
    ("portuguese", "As partes celebram o contrato (o “Contrato de Serviços de Limpeza de Escritórios”).",
     "Contrato de Serviços de Limpeza de Escritórios", True),
    ("english", 'The parties enter into a contract (a "Party to the Office Upkeep Arrangement").',
     "Party to the Office Upkeep Arrangement", True),
    ("spanish", "Se aplica el Real Decreto 5/2020 (de “Medidas urgentes para la limpieza de oficinas públicas”).",
     "Medidas urgentes para la limpieza de oficinas públicas", False),
    ("italian", 'Come previsto dal capitolato (a "Specifiche Tecniche dei Servizi di Pulizia").',
     "Specifiche Tecniche dei Servizi di Pulizia", False),
    (None, "Se aplica el Real Decreto 5/2020 (de “Medidas urgentes para la limpieza de oficinas públicas”).",
     "Medidas urgentes para la limpieza de oficinas públicas", False),
)
# A German closer is the English opener: in "„A“ … „B”" the old typographic pair read a phantom span
# from A's closer to B's closer -- found by the twin property at the review, 2026-11-02. Both
# quoted spans kept in the English, the phantom alone fired.
G7L_PHANTOM = ("Die Parteien vereinbaren „Büroreinigung im Gebäude Nord Eins“ und danach „Kantinenbetrieb "
               "im Gebäude Süd Zwei”.",
               "The parties agree „Büroreinigung im Gebäude Nord Eins“ and then „Kantinenbetrieb im Gebäude "
               "Süd Zwei”.")
# An abbreviation is no title word -- the review's finding: 'Pt.' once read as the Polish 'pt.'.
G7L_PT = ('The rates are set out in Pt. "Schedule of Office Cleaning Services Rates".',
          'The rates are set out in Part "Office Cleaning Rates Schedule".', "Schedule of Office Cleaning Services Rates")
# (language, shape, source, English keeping a quoted span, the span the new code must still report)
G7L_TP = (
    ("French", "a naming verb", "Le projet dénommé « Centre de Services du Quartier Haut Vert » est autorisé.",
     'The project "Upper Green District Service Centre" is authorised.', "Centre de Services du Quartier Haut Vert"),
    ("French", "a cross-reference",
     "Les travaux suivent la procédure (telle que définie dans le « Règlement Régional des Marchés de Travaux "
     "Publics »).", 'The works follow the procedure (as defined in the "Regional Public Works Procurement Rules").',
     "Règlement Régional des Marchés de Travaux Publics"),
    ("Spanish", "a naming verb", "El proyecto denominado “Centro de Servicios del Barrio Alto Verde” queda autorizado.",
     'The project "Upper Green District Service Centre" is authorised.', "Centro de Servicios del Barrio Alto Verde"),
    ("Spanish", "a cross-reference",
     "Las obras siguen el procedimiento (según se define en el “Reglamento Regional de Contratos de Obras "
     "Públicas”).", 'The works follow the procedure (as defined in the "Regional Public Works Contract Rules").',
     "Reglamento Regional de Contratos de Obras Públicas"),
    ("Portuguese", "a naming verb", "O projeto denominado “Centro de Serviços do Bairro Alto Verde” fica autorizado.",
     'The project "Upper Green District Service Centre" is authorised.', "Centro de Serviços do Bairro Alto Verde"),
    ("Portuguese", "a cross-reference",
     "As obras seguem o procedimento (conforme definido no “Regulamento Regional de Contratos de Obras "
     "Públicas”).", 'The works follow the procedure (as defined in the "Regional Public Works Contract Rules").',
     "Regulamento Regional de Contratos de Obras Públicas"),
    ("German", "a naming verb", 'Das Projekt namens "Servicezentrum im oberen grünen Viertel Nord" ist genehmigt.',
     'The project "Upper Green District Service Centre" is authorised.', "Servicezentrum im oberen grünen Viertel Nord"),
    ("German", "a cross-reference",
     'Die Arbeiten folgen dem Verfahren (wie definiert in der "Regionalen Ordnung für öffentliche Bauaufträge").',
     'The works follow the procedure (as defined in the "Regional Public Works Contract Rules").',
     "Regionalen Ordnung für öffentliche Bauaufträge"),
    ("Dutch", "a naming verb", "Het project genaamd “Dienstencentrum van de Hoge Groene Wijk” is goedgekeurd.",
     'The project "Upper Green District Service Centre" is authorised.', "Dienstencentrum van de Hoge Groene Wijk"),
    ("Dutch", "a cross-reference",
     "De werken volgen de procedure (zoals gedefinieerd in de “Regionale Regeling voor Openbare Aanbesteding van "
     "Werken”).", 'The works follow the procedure (as defined in the "Regional Public Works Contract Rules").',
     "Regionale Regeling voor Openbare Aanbesteding van Werken"),
    ("Polish", "a naming verb", 'Projekt zwany "Centrum Usług Biurowych Górnej Zielonej Dzielnicy" jest zatwierdzony.',
     'The project "Upper Green District Service Centre" is authorised.',
     "Centrum Usług Biurowych Górnej Zielonej Dzielnicy"),
    ("Polish", "a cross-reference",
     'Prace przebiegają według procedury (zgodnie z definicją w "Regionalnym Regulaminie Zamówień na Roboty '
     'Publiczne").', 'The works follow the procedure (as defined in the "Regional Public Works Contract Rules").',
     "Regionalnym Regulaminie Zamówień na Roboty Publiczne"),
    ("Hungarian", "a naming word after the name",
     'A "Felső Zöld Negyed Szolgáltató Központja Projekt" nevű projektet jóváhagyták.',
     'The "Upper Green District Service Centre" project has been approved.',
     "Felső Zöld Negyed Szolgáltató Központja Projekt"),
    ("Hungarian", "a cross-reference",
     'Az eljárás (a "Regionális Szabályzat a Középítési Munkák Megrendeléséről" szerint) zajlik.',
     'The procedure runs (under the "Regional Public Works Contract Rules").',
     "Regionális Szabályzat a Középítési Munkák Megrendeléséről"),
    ("Finnish", "a naming verb", 'Hanke nimeltään "Ylemmän Vihreän Kaupunginosan Palvelukeskus Uusi" on hyväksytty.',
     'The project "Upper Green District Service Centre" is approved.',
     "Ylemmän Vihreän Kaupunginosan Palvelukeskus Uusi"),
    ("Finnish", "a cross-reference",
     'Työt noudattavat menettelyä (kuten määritelty "Alueellisessa Julkisten Rakennusurakoiden Hankintaohjeessa '
     'Nykyisin").', 'The works follow the procedure (as defined in the "Regional Public Works Contract Rules").',
     "Alueellisessa Julkisten Rakennusurakoiden Hankintaohjeessa Nykyisin"),
    ("Norwegian", "a naming verb", 'Prosjektet kalt "Servicesenter for Det Øvre Grønne Strøket" er godkjent.',
     'The project "Upper Green District Service Centre" is approved.', "Servicesenter for Det Øvre Grønne Strøket"),
    ("Norwegian", "a cross-reference",
     'Arbeidet følger prosedyren (som definert i "Regionalt Regelverk for Offentlige Byggekontrakter i Fylket").',
     'The works follow the procedure (as defined in the "Regional Public Works Contract Rules").',
     "Regionalt Regelverk for Offentlige Byggekontrakter i Fylket"),
    # A follow-on word (par, por) may come after a lead-in but never begin one: "(by the X)" is a reference.
    ("French", "a follow-on word is no lead-in",
     "Les travaux sont régis (par le « Règlement Régional des Marchés de Travaux Publics »).",
     'The works are governed (by the "Regional Public Works Procurement Rules").',
     "Règlement Régional des Marchés de Travaux Publics"),
    ("Spanish", "a follow-on word is no lead-in",
     "Las obras se rigen (por el “Reglamento Regional de Contratos de Obras Públicas”).",
     'The works are governed (by the "Regional Public Works Contract Rules").',
     "Reglamento Regional de Contratos de Obras Públicas"),
    # A bare bracket is no marker: a quoted name in brackets takes that shape too.
    ("English", "a bare bracket",
     'The parties signed the contract ("Long Term Office Cleaning and Catering Contract").',
     'The parties signed the contract ("Long-Term Office Cleaning and Catering Contract").',
     "Long Term Office Cleaning and Catering Contract"),
)
# The widening's own true positive: a name dropped in the low opening quote, never read before.
G7L_WIDE = (
    ("Polish", "Strony realizują projekt „Centrum Usług Biurowych Delta Północ Nowa” w terminie.",
     "The parties carry out the project on time.", "Centrum Usług Biurowych Delta Północ Nowa"),
    ("German", "Die Parteien verwirklichen das Projekt „Bürozentrum am Alten Markt Nummer Eins“ fristgerecht.",
     "The parties carry out the project on time.", "Bürozentrum am Alten Markt Nummer Eins"),
)
# Moot at 14.5: a span with no space was one word. The marker is silent then and now; the name dropped
# in it, DECLARED BLIND here until 14.9.7, fires now -- that section's W97_TP.
G7L_MOOT = (
    ("Japanese marker", "当事者は本契約（以下「事務所清掃業務委託契約」という。）を締結する。", KEEP),
    ("Chinese marker", "双方签订本合同（以下简称“办公室清洁服务合同”）。", KEEP),
)
# --- 14.5 cases: end


def low9_twin(s):
    """The same paragraph with each low-opening-quote span in typographic quotes, which the old code read."""
    return re.sub("„([^„”“]+)[”“]", lambda m: "“" + m.group(1) + "”", s)


for tree in ("uk", "us"):
    old_vt = load_old("validate_translations.py", tree)
    new_vt = load_new("validate_translations.py", tree)

    def fired(mod, src, en):
        return [p for _s, p in mod._check_quoted_phrase_retention({"text": src, "en": en})]

    for lang, shape, src, span in G7L:
        keep, drop = (TKEEP, TDROP) if "title" in shape else (KEEP, DROP)
        twin = low9_twin(src)
        new_f, old_f = fired(new_vt, src, keep), fired(old_vt, twin, keep)
        ok(f"G7 {tree} {lang} {shape}: silent now", not new_f, f"({new_f})")
        ok(f"G7 {tree} {lang} {shape}: PROVED it fired before" + (" (its typographic twin)" if twin != src else ""),
           span in old_f, f"({old_f})")
        new_f, old_f = fired(new_vt, src, drop), fired(old_vt, twin, drop)
        ok(f"G7 {tree} {lang} {shape} dropped with its quotes: still fires, on that span", span in new_f, f"({new_f})")
        ok(f"G7 {tree} {lang} {shape} dropped with its quotes: fired before too", span in old_f, f"({old_f})")
    for lang, shape, src, en, span in G7L_TP:
        new_f, old_f = fired(new_vt, src, en), fired(old_vt, src, en)
        ok(f"G7 {tree} {lang} TRUE POSITIVE {shape}: still fires, on that span", span in new_f, f"({new_f})")
        ok(f"G7 {tree} {lang} TRUE POSITIVE {shape}: fired before too", span in old_f, f"({old_f})")
    for lang, src, en, span in G7L_WIDE:
        new_f, old_f = fired(new_vt, src, en), fired(old_vt, src, en)
        ok(f"G7 {tree} {lang} a name dropped in the low opening quote: fires now", span in new_f, f"({new_f})")
        ok(f"G7 {tree} {lang} a name dropped in the low opening quote: PROVED unread before", not old_f, f"({old_f})")
    for label, src, en in G7L_MOOT:
        new_f, old_f = fired(new_vt, src, en), fired(old_vt, src, en)
        ok(f"G7 {tree} {label}: silent now and before (moot)", not new_f and not old_f, f"({new_f}, {old_f})")
    for lang, src, span, quiet in G7L_ALONE:
        new_f = [p for _s, p in new_vt._check_quoted_phrase_retention({"text": src, "en": KEEP}, lang)]
        old_f = fired(old_vt, src, KEEP)
        if quiet:
            ok(f"G7 {tree} an article alone, {lang} declared: silent now", not new_f, f"({new_f})")
        else:
            ok(f"G7 {tree} TRUE POSITIVE an article alone, {lang} declared: still fires", span in new_f, f"({new_f})")
        ok(f"G7 {tree} an article alone, {lang} declared: fired before", span in old_f, f"({old_f})")
    new_f, old_f = fired(new_vt, *G7L_PHANTOM), fired(old_vt, *G7L_PHANTOM)
    ok(f"G7 {tree} a German closer opens no phantom span: silent now", not new_f, f"({new_f})")
    ok(f"G7 {tree} a German closer opens no phantom span: PROVED it fired before", bool(old_f), f"({old_f})")
    new_f, old_f = fired(new_vt, G7L_PT[0], G7L_PT[1]), fired(old_vt, G7L_PT[0], G7L_PT[1])
    ok(f"G7 {tree} TRUE POSITIVE an abbreviation is no title word: fires now and before",
       G7L_PT[2] in new_f and G7L_PT[2] in old_f, f"({new_f}, {old_f})")
    # THE DECLARATION REACHES THE CHECK: the whole script on a Dutch "(de X)", declared Dutch at Step 1c
    # and undeclared -- quiet the first way, warning the second.
    for decl, want_quiet in (("dutch", True), (None, False)):
        wd = TMP / f"vt-decl-{tree}-{decl}"
        wd.mkdir()
        (wd / "paragraphs.json").write_text(json.dumps([{"idx": 0, "text": G7L_ALONE[0][1], "en": KEEP}]),
                                            encoding="utf-8")
        if decl:
            (wd / "source_language.json").write_text(json.dumps({"source_language": decl}), encoding="utf-8")
        r = subprocess.run([sys.executable, str(ROOT / tree / "scripts" / "validate_translations.py"),
                            str(wd / "paragraphs.json")], capture_output=True, text=True, encoding="utf-8",
                           errors="replace", env=F10_ENV, cwd=wd)
        warned = "Quoted source phrases NOT found" in r.stdout + r.stderr
        ok(f"G7 {tree} the whole script, a Dutch article alone, {decl or 'nothing'} declared: "
           f"{'no' if want_quiet else 'a'} quoted-phrase WARN", warned != want_quiet, f"(rc={r.returncode})")
    # THE EXIT skill Step 4 reads, by content: a French marker exits 0 now and PROVED it warned before;
    # a Polish name dropped in the low opening quote warns now and PROVED it passed before.
    old_dir = TMP / f"old_vt_{tree}"     # written by the G1/G7 section above
    for row, case, now_warns in (("G7-fr", (None, G7L[3][2], KEEP), False), ("G7-pl", G7L_WIDE[0][:3], True)):
        old_rc, old_out = vt_run(old_dir, f"old-{tree}-{row}", case)
        new_rc, new_out = vt_run(ROOT / tree / "scripts", f"new-{tree}-{row}", case)
        warned_now = new_rc == 1 and "Quoted source phrases NOT found" in new_out
        passed_now = new_rc == 0 and "PASS" in new_out and "Quoted source phrases" not in new_out
        warned_old = old_rc == 1 and "Quoted source phrases NOT found" in old_out
        passed_old = old_rc == 0 and "PASS" in old_out and "Quoted source phrases" not in old_out
        ok(f"{row} {tree}, the whole script: {'warns' if now_warns else 'exits 0 and PASS'} now",
           warned_now if now_warns else passed_now, f"(rc={new_rc})")
        ok(f"{row} {tree}, the whole script: PROVED it {'passed' if now_warns else 'warned'} before",
           passed_old if now_warns else warned_old, f"(rc={old_rc})")

# =============================================================================
print("\nG3 and G13 — quality_check: `; and/or` is a list connective; a name the lexicon keeps is no remnant")
print("-" * 96)

# G3: the list-connective whitelist stopped one character short of `and/or`, so a list item ending
# `; and/or` read as a sentence cut off on `or`. G13: the remnant check failed skill Step 9 on the
# names the skill's own lexicons tell the operator to keep in the source language -- repack's block
# already read them from source_language_markers.LEXICON_KEPT_NAMES, and now this check does too,
# through the same call. Each false positive is silent now and PROVED to have fired at the pinned
# baseline (main's proof is temp/s1102c_red_first.py's); each true positive beside it -- the defect
# a bare exemption would also silence -- fires now and before. 14.6 of PLAN-2-step-b.md section
# 3.14; every string INVENTED, on office services.
# --- 14.6 cases: begin
G3_FP = (
    ("`; and/or`", "the Contractor shall clean the offices every week; and/or"),
    ("`, and/or`", "the Contractor shall clean the meeting rooms every day, and/or"),
    ("`; and / or`, spaced", "the Contractor shall replace the light bulbs promptly; and / or"),
)
G3_TP = (
    ("`and/or` with no `;` or `,` before it", "the Contractor shall clean the windows and the doors and/or"),
    ("`; and/or the`", "the Contractor shall clean the offices every week; and/or the"),
    ("a dangling `at the`", "the Contractor shall deliver the cleaning products at the"),
)
# the ten names LEXICON_KEPT_NAMES declares, typed here with the language of the lexicon each cites
G13_KEPT = (
    ("Agenzia delle Entrate", "italian"),
    ("Società Italiana degli Autori ed Editori", "italian"),
    ("Mercato Elettronico della Pubblica Amministrazione", "italian"),
    ("Codice della Crisi d'Impresa e dell'Insolvenza", "italian"),
    ("Codice delle Assicurazioni Private", "italian"),
    ("dupla conforme", "portuguese"),
    ("Loi du 25 juin 2008", "french"),
    ("Loi du 6 juillet 1989", "french"),
    ("Loi du 23 décembre 1986", "french"),
    ("Loi du 10 juillet 1965", "french"),
)
G13_SENT = "The office manager writes to the {} about the cleaning invoice each month."
G13_DENSE = ("The office manager writes to the Agenzia delle Entrate, the Mercato Elettronico della Pubblica "
             "Amministrazione and the Codice delle Assicurazioni Private each month.")
# (label, language, paragraph, what must hold now): "one fewer" -- the old count less the one hit inside
# the name, at least one left; "full" -- the dense FULL paragraph finding; "fires" -- any finding
G13_TP = (
    ("the same marker word just outside a kept name", "italian",
     "The office manager writes to the Agenzia delle Entrate and delle Dogane each month.", "one fewer"),
    ("a kept name cut short", "italian",
     "The office manager writes to the Agenzia delle office about the cleaning invoice each month.", "fires"),
    ("a whole Italian paragraph holding a kept name", "italian",
     "Il Committente versa all'Agenzia delle Entrate le imposte della società e delle sue controllate, "
     "nonché quelle sulla sede, ai sensi della legge.", "full"),
    ("a French company form, an advisory in repack and a finding here", "french",
     "The office manager writes to the Société about the cleaning invoice each month.", "fires"),
    ("a Japanese word, an advisory in repack and a finding here", "japanese",
     "The office manager signs the 契約 for the cleaning invoice each month.", "fires"),
)
G13_BARE = ("french", "The office manager closes the office for the whole of juillet each year.")
# --- 14.6 cases: end
_G13_N = iter(range(10 ** 6))


def g13_del(text):
    return (f'<w:p><w:del w:id="1" w:author="A"><w:r><w:delText xml:space="preserve">{text}</w:delText>'
            '</w:r></w:del></w:p>')


def g13_aux(mod, text, lang, part="header"):
    d = TMP / f"g13-aux-{next(_G13_N)}"
    (d / "word").mkdir(parents=True)
    if part == "header":
        (d / "word" / "header1.xml").write_text(
            f'<w:hdr xmlns:w="{W}"><w:p><w:r><w:t xml:space="preserve">{text}</w:t></w:r></w:p></w:hdr>',
            encoding="utf-8")
    else:                                          # a numbering level's own text, read from its w:val
        (d / "word" / "numbering.xml").write_text(
            f'<w:numbering xmlns:w="{W}"><w:abstractNum w:abstractNumId="0"><w:lvl w:ilvl="0">'
            f'<w:lvlText w:val="{text} %1"/></w:lvl></w:abstractNum></w:numbering>', encoding="utf-8")
    return [i for v in mod.check_aux_files(str(d), lang).values() for i in v]


def qc_run(script, text, lang):
    wd = TMP / f"qc-run-{next(_G13_N)}"
    wd.mkdir()
    (wd / "document.xml").write_text(
        f'<w:document xmlns:w="{W}"><w:body>{para(text)}</w:body></w:document>', encoding="utf-8")
    r = subprocess.run([sys.executable, str(script), str(wd / "document.xml"), "--language", lang],
                       capture_output=True, text=True, encoding="utf-8", errors="replace", env=F10_ENV, cwd=wd)
    return r.returncode, r.stdout + r.stderr


for tree in ("uk", "us"):
    assert_baseline_differs("quality_check.py", tree)
    old_qc = OLD_QC if tree == "uk" else load_old("quality_check.py", "us")
    new_qc = NEW_QC if tree == "uk" else load_new("quality_check.py", "us")

    def trunc(mod, text):
        return [i for i in mod.check_truncation(doc(para(text)), False, None) if i.startswith("Dangling ending")]

    for label, text in G3_FP:
        n, o = trunc(new_qc, text), trunc(old_qc, text)
        ok(f"G3 {tree} {label}: silent now", not n, f"({n})")
        ok(f"G3 {tree} {label}: PROVED it fired before", bool(o), f"({o})")
    for label, text in G3_TP:
        n, o = trunc(new_qc, text), trunc(old_qc, text)
        ok(f"G3 {tree} TRUE POSITIVE {label}: still fires", bool(n), f"({n})")
        ok(f"G3 {tree} TRUE POSITIVE {label}: fired before too", bool(o), f"({o})")

    # THE POPULATION IS THE TABLE ITSELF: a name added to LEXICON_KEPT_NAMES without a control here turns this red.
    slm = load_new("source_language_markers.py", tree)
    ok(f"G13 {tree} the controls cover exactly the names LEXICON_KEPT_NAMES declares",
       [n for n, _l in G13_KEPT] == list(slm.LEXICON_KEPT_NAMES), f"({list(slm.LEXICON_KEPT_NAMES)})")

    def rem(mod, body, lang):
        return mod.check_source_remnants(doc(body), False, lang)

    for name, lang in G13_KEPT:
        s = G13_SENT.format(name)
        for view, n, o in (("the body", rem(new_qc, para(s), lang), rem(old_qc, para(s), lang)),
                           ("a deletion", rem(new_qc, g13_del(s), lang), rem(old_qc, g13_del(s), lang)),
                           ("a header", g13_aux(new_qc, s, lang), g13_aux(old_qc, s, lang))):
            ok(f"G13 {tree} {name}, {lang}, in {view}: silent now", not n, f"({n})")
            ok(f"G13 {tree} {name}, {lang}, in {view}: PROVED it fired before", bool(o), f"({o})")
    s = G13_SENT.format(G13_KEPT[0][0])
    n, o = g13_aux(new_qc, s, "italian", "numbering"), g13_aux(old_qc, s, "italian", "numbering")
    ok(f"G13 {tree} a kept name in a numbering level's text: silent now", not n, f"({n})")
    ok(f"G13 {tree} a kept name in a numbering level's text: PROVED it fired before", bool(o), f"({o})")
    for view, body in (("the body", para(G13_DENSE)), ("a deletion", g13_del(G13_DENSE))):
        n, o = rem(new_qc, body, "italian"), rem(old_qc, body, "italian")
        ok(f"G13 {tree} three kept names in one sentence, in {view}: silent now", not n, f"({n})")
        ok(f"G13 {tree} three kept names in one sentence, in {view}: PROVED the dense count read a FULL "
           f"paragraph before", any(i.startswith("FULL") for i in o), f"({o})")
    for label, lang, text, want in G13_TP:
        n, o = rem(new_qc, para(text), lang), rem(old_qc, para(text), lang)
        if want == "one fewer":
            now = bool(n) and len(n) == len(o) - 1
        elif want == "full":
            now = any(i.startswith("FULL") for i in n)
        else:
            now = bool(n)
        before = any(i.startswith("FULL") for i in o) if want == "full" else bool(o)
        ok(f"G13 {tree} TRUE POSITIVE {label}: still fires"
           + (", only the hit inside the name removed" if want == "one fewer" else ""),
           now, f"({len(n)} now, {len(o)} before)")
        ok(f"G13 {tree} TRUE POSITIVE {label}: fired before too", before, f"({len(o)} before)")
    sink = []
    n = new_qc.check_source_remnants(doc(para(G13_BARE[1])), False, G13_BARE[0], sink)
    ok(f"G13 {tree} a bare month name: still a warning and never an issue", bool(sink) and not n,
       f"({len(sink)} warnings, {len(n)} issues)")

    # THE EXIT skill Step 9 reads, by content: rc 2 and FAILED before, rc 0 and PASSED now.
    for row, text, lang in (("G3", G3_FP[0][1], "italian"), ("G13", G13_SENT.format(G13_KEPT[0][0]), "italian")):
        new_rc, new_out = qc_run(ROOT / tree / "scripts" / "quality_check.py", text, lang)
        old_rc, old_out = qc_run(OLD_DIR / (tag(tree) + "quality_check.py"), text, lang)
        ok(f"{row} {tree}, the whole script: exits 0 and PASSED now",
           new_rc == 0 and "*** PASSED" in new_out and "*** FAILED" not in new_out, f"(rc={new_rc})")
        ok(f"{row} {tree}, the whole script: PROVED it exited 2 and FAILED before",
           old_rc == 2 and "*** FAILED" in old_out, f"(rc={old_rc})")

# =============================================================================
print()
print("G12 — quality_check: a citation of legislation is no internal reference; a declared italic is no finding")
print("-" * 96)

# G12: the internal-reference rule flagged `Article N` wherever its paragraph held none of a 20-entry keyword
# list, so a citation naming its instrument in the same sentence - `of the <Name> Decree`, a code of procedure, a
# regulator's resolution - read as a cross-reference to rewrite as `Clause N`, and a three-digit article was cut
# inside its number. Now the number is read whole and lexicon_compliance's own legislation tail is asked where it
# ends - ONE test, lifted into a named constant there, proved unchanged byte for byte. The spurious-italic rule
# flagged a long italic run the operator's notes DECLARE, which post_process's pass keeps (register B1); given the
# notes, it now asks them the same question. Each false positive silent now and PROVED to have fired at the pinned
# baseline; each true positive beside it firing now and before. 14.11 of PLAN-2-step-b.md section 3.14; every
# string INVENTED, on office services.
# --- 14.11 cases: begin
G12_FP = (
    ("a decree named after `of the`", "The cleaning fee is set out in Article 7 of the Sample Decree."),
    ("a paragraph between the number and the decree",
     "The cleaning fee is provided for by Article 7, paragraph 2, of the Sample Decree."),
    ("a three-digit article of a code of procedure",
     "The unpaid cleaning invoice is enforced under Article 321 of the Sample Code of Civil Procedure."),
    ("two three-digit articles, each with a paragraph, before the decree",
     "The cleaning fee is set out in Article 123, paragraph 2, and Article 124, paragraph 1, of the Sample Decree."),
    ("a regulator's resolution and its date",
     "The cleaning tariff follows Article 5 of the XYZ Resolution of 1 March 2020."),
    ("two articles in the plural, before the decree",
     "The cleaning fee is set out in Articles 3 and 4 of the Sample Decree."),
)
G12_TP = (
    ("`Article 7 above`", "The cleaner shall comply with Article 7 above."),
    ("`Article 7 of the Agreement`", "The tenant may end the cleaning contract under Article 7 of the Agreement."),
    ("a three-digit internal reference", "The cleaner shall comply with Article 120 above."),
    ("the tail may not bridge from the Agreement to a decree",
     "The tenant may end the cleaning contract under Article 7 of the Agreement and the Sample Decree."),
    ("the tail may not cross into the next sentence",
     "The cleaner shall comply with Article 7. The Sample Decree sets the fee."),
)
G12_KEYWORD = "The cleaner shall comply with Article 7 above and with the Civil Code."
G12_WHOLE = "The cleaner shall comply with Article 2024 above."
G12_ITALIC = "Office Cleaning Services Agreement"
G12_LEAD, G12_END = "The parties sign the ", " today."
G12_FULL = G12_LEAD + G12_ITALIC + G12_END
G12_SPAN = {"start": len(G12_LEAD), "end": len(G12_LEAD + G12_ITALIC)}
# (label, the notes) - None is no notes at all
G12_ITALIC_FP = (
    ("a run the note DECLARES italic", [{"idx": 0, "text": "x", "en": G12_FULL,
                                         "en_runs": [dict(G12_SPAN, italic=True)]}]),
    ("a run carried unchanged from an italic source run", [{"idx": 0, "text": "x", "en": G12_FULL,
                                                            "runs": [{"text": G12_ITALIC, "italic": True}]}]),
)
G12_ITALIC_TP = (
    ("a run the note calls plain", [{"idx": 0, "text": "x", "en": G12_FULL,
                                     "en_runs": [dict(G12_SPAN, italic=False)]}]),
    ("a run its note does not cover", [{"idx": 0, "text": "x", "en": G12_FULL}]),
    ("a paragraph its notes do not reach", [{"idx": 0, "text": "x", "en": "The tenant pays the cleaner."}]),
    ("no notes at all", None),
)
G12_LIFT_REF = "c33f001"     # main, #194: lexicon_compliance as 14.4 left it, before the lift
# --- 14.11 cases: end


def g12_italic_para():
    return (f'<w:p><w:r><w:t xml:space="preserve">{G12_LEAD}</w:t></w:r>'
            f'<w:r><w:rPr><w:i/></w:rPr><w:t xml:space="preserve">{G12_ITALIC}</w:t></w:r>'
            f'<w:r><w:t xml:space="preserve">{G12_END}</w:t></w:r></w:p>')


def g12_notes(pp, entries):
    """The notes as post_process's own loader reads them - the reader the rule is handed at skill Step 9."""
    if entries is None:
        return None
    path = TMP / f"g12-notes-{next(_G13_N)}.json"
    path.write_text(json.dumps(entries), encoding="utf-8")
    return pp.load_declared_notes(str(path))


def g12_fmt(mod, notes):
    """The rule's italic findings, handed the notes where it takes them. Asked of the code BEFORE the change it
    cannot take them - so every control here still runs, and a false positive reads as a finding, not a crash."""
    if "notes" in inspect.signature(mod.check_formatting).parameters:
        return g12_italics(mod.check_formatting(doc(g12_italic_para()), False, notes))
    return g12_italics(mod.check_formatting(doc(g12_italic_para()), False))


def g12_italics(issues):
    return [i for i in issues if i.startswith("Spurious italic")]


def g12_run(script, body, entries):
    wd = TMP / f"g12-run-{next(_G13_N)}"
    wd.mkdir()
    (wd / "document.xml").write_text(f'<w:document xmlns:w="{W}"><w:body>{body}</w:body></w:document>',
                                     encoding="utf-8")
    (wd / "paragraphs.json").write_text(json.dumps(entries), encoding="utf-8")
    r = subprocess.run([sys.executable, str(script), str(wd / "document.xml"), "--with-source",
                        str(wd / "paragraphs.json"), "--language", "italian"], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", env=F10_ENV, cwd=wd)
    return r.returncode, r.stdout + r.stderr


def g12_article_rule(mod):
    return next(r[1] for r in mod.RULES if r[2].startswith("'Article N'"))


for tree in ("uk", "us"):
    # the us script must ask the us tree's siblings, not the uk copies an earlier load left cached
    for _m in ("lexicon_compliance", "post_process"):
        sys.modules.pop(_m, None)
    old_qc = OLD_QC if tree == "uk" else load_old("quality_check.py", "us")
    new_qc = load_new("quality_check.py", tree)
    ok(f"G12 {tree} the rule asks its OWN tree's legislation tail and notes reader",
       all(getattr(sys.modules.get(m), "__file__", None)
           and Path(sys.modules[m].__file__).parent.parent.name == tree for m in ("lexicon_compliance", "post_process")))
    ok(f"G12 {tree} the italic rule takes the notes",
       "notes" in inspect.signature(new_qc.check_formatting).parameters)
    g12_pp = sys.modules.get("post_process") or load_new("post_process.py", tree)

    # THE LIFT: lexicon_compliance's own warning pattern unchanged, byte for byte, against main before it
    blob = subprocess.run(["git", "show", f"{G12_LIFT_REF}:{tree}/scripts/lexicon_compliance.py"],
                          capture_output=True, cwd=ROOT)
    lift = OLD_DIR / f"lift_{tree}_lexicon_compliance.py"
    lift.write_bytes(blob.stdout)
    spec = importlib.util.spec_from_file_location(f"lift_{tree}_lexicon_compliance", lift)
    lift_lc = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(OLD_DIR))
    try:
        spec.loader.exec_module(lift_lc)
    finally:
        sys.path.remove(str(OLD_DIR))
    new_lc = sys.modules.get("lexicon_compliance") or load_new("lexicon_compliance.py", tree)
    before, after = g12_article_rule(lift_lc), g12_article_rule(new_lc)
    ok(f"G12 {tree} lexicon_compliance's 'Article N' warning: the same pattern and flags as at {G12_LIFT_REF}",
       blob.returncode == 0 and before.pattern == after.pattern and before.flags == after.flags)
    ahead = getattr(new_lc, "ART_LEGISLATION_AHEAD", "")
    follows = getattr(new_qc, "ART_LEGISLATION_FOLLOWS", None)
    ok(f"G12 {tree} and the shared constant is exactly the look-ahead inside it, the one the rule asks",
       bool(ahead) and "(?!" + ahead + ")" in after.pattern and follows is not None and follows.pattern == ahead)

    def arts(mod, text):
        return mod.check_article_refs(doc(para(text)), False)

    for label, text in G12_FP:
        n, o = arts(new_qc, text), arts(old_qc, text)
        ok(f"G12 {tree} {label}: silent now", not n, f"({n})")
        ok(f"G12 {tree} {label}: PROVED it fired before", bool(o), f"({o})")
    for label, text in G12_TP:
        n, o = arts(new_qc, text), arts(old_qc, text)
        ok(f"G12 {tree} TRUE POSITIVE {label}: still fires", bool(n), f"({n})")
        ok(f"G12 {tree} TRUE POSITIVE {label}: fired before too", bool(o), f"({o})")
    n, o = arts(new_qc, G12_KEYWORD), arts(old_qc, G12_KEYWORD)
    ok(f"G12 {tree} the keyword exemption is untouched: silent then and now (the 11 are a follow-up)",
       not n and not o, f"({n}, {o})")
    n, o = arts(new_qc, G12_WHOLE), arts(old_qc, G12_WHOLE)
    ok(f"G12 {tree} the number is read whole: one finding then and now, naming all four digits now",
       len(n) == 1 == len(o) and "'Article 2024'" in n[0] and "'Article 20'" in o[0], f"({n}, {o})")

    for label, entries in G12_ITALIC_FP:
        n, o = g12_fmt(new_qc, g12_notes(g12_pp, entries)), g12_fmt(old_qc, None)
        ok(f"G12 {tree} {label}: silent now", not n, f"({n})")
        ok(f"G12 {tree} {label}: PROVED it fired before", bool(o), f"({o})")
    for label, entries in G12_ITALIC_TP:
        n, o = g12_fmt(new_qc, g12_notes(g12_pp, entries)), g12_fmt(old_qc, None)
        ok(f"G12 {tree} TRUE POSITIVE {label}: still fires", bool(n), f"({n})")
        ok(f"G12 {tree} TRUE POSITIVE {label}: fired before too", bool(o), f"({o})")
    n = g12_italics(new_qc.check_formatting(doc(g12_italic_para()), False))
    ok(f"G12 {tree} TRUE POSITIVE the rule called with no notes argument: still fires", bool(n), f"({n})")

    # THE EXIT skill Step 9 reads, run as Step 9 runs it, with --with-source: rc 0 and PASSED now, rc 2 and
    # FAILED before - each tree's script as a process of its own, so its own siblings are the ones asked.
    for row, body, entries in (
            ("G12 article", para(G12_FP[0][1]), [{"idx": 0, "text": G12_FP[0][1], "en": G12_FP[0][1]}]),
            ("G12 italic", g12_italic_para(), [{"idx": 0, "text": G12_FULL, "en": G12_FULL,
                                                "en_runs": [dict(G12_SPAN, italic=True)]}])):
        new_rc, new_out = g12_run(ROOT / tree / "scripts" / "quality_check.py", body, entries)
        old_rc, old_out = g12_run(OLD_DIR / (tag(tree) + "quality_check.py"), body, entries)
        ok(f"{row} {tree}, the whole script: exits 0 and PASSED now",
           new_rc == 0 and "*** PASSED" in new_out and "*** FAILED" not in new_out, f"(rc={new_rc})")
        ok(f"{row} {tree}, the whole script: PROVED it exited 2 and FAILED before",
           old_rc == 2 and "*** FAILED" in old_out, f"(rc={old_rc})")

# =============================================================================
print("\nG4 — validate_reject_all: a dot inside a dotted form is no missing space")
print("-" * 96)

# The missing-space rule -- punctuation after a non-space, a letter straight after it -- fired INSIDE a dotted
# form, on `B.V`, `S.p` and `p.A`, whatever followed. So a dot between two lone letters each followed by a dot
# is skipped; the dot AFTER the form, and punctuation after a word, a digit or a bracket, still fires. Each false
# positive silent now and PROVED to have fired at the pinned baseline; each true positive beside it firing now
# and before. 14.7 of PLAN-2-step-b.md section 3.14; every string INVENTED, on office services.
# --- 14.7 cases: begin
G4_FP = (
    ("`B.V.`", "The cleaning contract binds a local B.V. and its staff."),
    ("`S.p.A.`", "The canteen is run by a catering S.p.A. under the lease."),
    ("`S.à r.l.`", "The lifts are kept by a small S.à r.l. on weekdays."),
    ("`S.r.l.`", "The invoices go to the cleaning S.r.l. every month."),
    ("`N.V.`", "The cleaning staff work for a local N.V. from Monday."),
    ("`U.S.A.`", "The office printers come from the U.S.A. in spring."),
    ("`e.g.`", "Small repairs, e.g. a broken handle, are paid by the tenant."),
)
G4_TP = (
    ("a word run into the next sentence", "The keys stay with the Buyer.The office opens at nine."),
    ("the dot AFTER a dotted form", "The contract binds a local B.V.The staff sign it."),
    ("the dot after `e.g.`", "Small repairs, e.g.The broken handle, are paid by the tenant."),
    ("a dotted form run into a word", "The canteen is run by a catering S.p.A.and the tenant pays."),
    ("a section number run into a word", "The tenant reads clause 3.2.The office closes at six."),
    ("a comma with no space", "The keys stay with the Seller,the office opens at nine."),
    ("an initial run into a surname", "The office manager J.Smith signs the cleaning invoice."),
    ("a word run into an initial", "The keys stay with the Buyer.A. Smith collects them on Monday."),
    ("a numbered annex run into an initial", "The tenant reads Annex 3A.B. Smith signs it on Monday."),
)
# --- 14.7 cases: end


def g4_fires(mod, text):
    return [s for n, s in mod._scan_view(text, []) if n == "missing_space_between_words"]


def g4_run(script, text, *flags):
    wd = TMP / f"g4-run-{next(_G13_N)}"
    wd.mkdir()
    (wd / "paragraphs.json").write_text(json.dumps([{"idx": 0, "text": "x", "en_segments": [
        {"type": "regular", "en": text + " "}, {"type": "ins", "en": "The tenant agrees."}]}]), encoding="utf-8")
    r = subprocess.run([sys.executable, str(script), str(wd / "paragraphs.json"), *flags], capture_output=True,
                       text=True, encoding="utf-8", errors="replace", env=F10_ENV, cwd=wd)
    return r.returncode, r.stdout + r.stderr


for tree in ("uk", "us"):
    assert_baseline_differs("validate_reject_all.py", tree)
    old_vra = load_old("validate_reject_all.py", tree)
    new_vra = load_new("validate_reject_all.py", tree)
    for label, text in G4_FP:
        n, o = g4_fires(new_vra, text), g4_fires(old_vra, text)
        ok(f"G4 {tree} {label}: silent now", not n, f"({n})")
        ok(f"G4 {tree} {label}: PROVED it fired before", bool(o), f"({o})")
    for label, text in G4_TP:
        n, o = g4_fires(new_vra, text), g4_fires(old_vra, text)
        ok(f"G4 {tree} TRUE POSITIVE {label}: still fires", bool(n), f"({n})")
        ok(f"G4 {tree} TRUE POSITIVE {label}: fired before too", bool(o), f"({o})")
    # THE EXIT a --strict run reads, by content, on a tracked-change paragraph: a dotted form 1 then 0; a run-in 1, 1.
    old_file = OLD_DIR / (tag(tree) + "validate_reject_all.py")
    for row, text, quiet_now in (("G4", G4_FP[1][1], True), ("G4-TP", G4_TP[0][1], False)):
        new_rc, new_out = g4_run(ROOT / tree / "scripts" / "validate_reject_all.py", text, "--strict")
        old_rc, old_out = g4_run(old_file, text, "--strict")
        if quiet_now:
            ok(f"{row} {tree}, the whole script --strict: exits 0 and PASS now",
               new_rc == 0 and "PASS: all 1 tracked-change paragraphs" in new_out, f"(rc={new_rc})")
        else:
            ok(f"{row} {tree}, the whole script --strict: exits 1 on the missing space now",
               new_rc == 1 and "[missing_space_between_words]" in new_out, f"(rc={new_rc})")
        ok(f"{row} {tree}, the whole script --strict: PROVED it exited 1 on the missing space before",
           old_rc == 1 and "[missing_space_between_words]" in old_out, f"(rc={old_rc})")

# =============================================================================
print("\nC10 — verify_diligence: skill Step 8 asks for a copy only of a part that carries text")
print("-" * 96)

# The Step 8 audit FAILED whenever a source auxiliary part had no copy in final/word, whatever the part held, while
# skill Step 8 has asked since C7 closed for a copy only of a part that carries text. So a header, footer, comments,
# footnotes or endnotes part with no text anywhere is not required; numbering stays required whenever it exists.
# Each false positive PASSES now and is PROVED to have FAILED at the pinned baseline; each part that carries text --
# however little, wherever it sits -- or will not parse still FAILS without a copy, now and before. 14.8 of
# PLAN-2-step-b.md section 3.14; every string INVENTED.
# --- 14.8 cases: begin
_NS = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'
C10_FP = (
    ("an empty header", "word/header1.xml", f"<w:hdr {_NS}><w:p/></w:hdr>"),
    ("a footnotes part holding only Word's separators", "word/footnotes.xml",
     f'<w:footnotes {_NS}><w:footnote w:type="separator" w:id="-1"><w:p><w:r><w:separator/></w:r></w:p></w:footnote>'
     f'<w:footnote w:type="continuationSeparator" w:id="0"><w:p><w:r><w:continuationSeparator/></w:r></w:p>'
     "</w:footnote></w:footnotes>"),
)
C10_TP = (
    ("a header that carries text", "word/header1.xml",
     f"<w:hdr {_NS}><w:p><w:r><w:t>Office cleaning schedule</w:t></w:r></w:p></w:hdr>"),
    ("a footer whose only text is a page-number field's result", "word/footer1.xml",
     f'<w:ftr {_NS}><w:p><w:r><w:fldChar w:fldCharType="begin"/></w:r><w:r><w:instrText> PAGE </w:instrText></w:r>'
     '<w:r><w:fldChar w:fldCharType="separate"/></w:r><w:r><w:t>1</w:t></w:r><w:r><w:fldChar w:fldCharType="end"/>'
     "</w:r></w:p></w:ftr>"),
    ("a header whose only text is a deletion", "word/header2.xml",
     f'<w:hdr {_NS}><w:p><w:del w:id="1" w:author="A"><w:r><w:delText>Draft</w:delText></w:r></w:del></w:p></w:hdr>'),
    ("a header whose only text sits in a text box", "word/header3.xml",
     f"<w:hdr {_NS}><w:p><w:r><w:txbxContent><w:p><w:r><w:t>Room 4</w:t></w:r></w:p></w:txbxContent></w:r></w:p>"
     "</w:hdr>"),
    ("a numbering part with no words", "word/numbering.xml",
     f'<w:numbering {_NS}><w:abstractNum w:abstractNumId="0"><w:lvl w:ilvl="0"><w:lvlText w:val="%1."/></w:lvl>'
     "</w:abstractNum></w:numbering>"),
    ("a header that will not parse", "word/header4.xml", f"<w:hdr {_NS}><w:p>"),
    ("a footer whose only words are a picture's alt text", "word/footer2.xml",
     f'<w:ftr {_NS} xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"><w:p><w:r>'
     '<w:drawing><wp:inline><wp:docPr id="1" name="Picture 1" descr="Office floor plan"/></wp:inline></w:drawing>'
     "</w:r></w:p></w:ftr>"),
)
# --- 14.8 cases: end


def c10_case(name, part, xml, copied=False):
    d = TMP / f"c10-{next(_G13_N)}"
    (d / "final" / "word").mkdir(parents=True)
    (d / "final" / "word" / "document.xml").write_text(f"<w:document {_NS}><w:body/></w:document>", encoding="utf-8")
    if copied:
        (d / "final" / part).write_text(xml, encoding="utf-8")
    orig = d / "orig.docx"
    with zipfile.ZipFile(orig, "w") as z:
        z.writestr("word/document.xml", f"<w:document {_NS}><w:body/></w:document>")
        z.writestr(part, xml)
    return d, orig


def c10_verdict(mod, d, orig):
    rep = mod.Report()
    mod.check_step_8(rep, str(d), str(orig))
    return [sev for _s, sev, _m, _d in rep.findings]


for tree in ("uk", "us"):
    assert_baseline_differs("verify_diligence.py", tree)
    old_vd = load_old("verify_diligence.py", tree)
    new_vd = load_new("verify_diligence.py", tree)
    for label, part, xml in C10_FP:
        d, orig = c10_case(label, part, xml)
        n, o = c10_verdict(new_vd, d, orig), c10_verdict(old_vd, d, orig)
        ok(f"C10 {tree} {label}, no copy: PASSES now", n == ["PASS"], f"({n})")
        ok(f"C10 {tree} {label}, no copy: PROVED it FAILED before", o == ["FAIL"], f"({o})")
    for label, part, xml in C10_TP:
        d, orig = c10_case(label, part, xml)
        n, o = c10_verdict(new_vd, d, orig), c10_verdict(old_vd, d, orig)
        ok(f"C10 {tree} TRUE POSITIVE {label}, no copy: still FAILS", n == ["FAIL"], f"({n})")
        ok(f"C10 {tree} TRUE POSITIVE {label}, no copy: FAILED before too", o == ["FAIL"], f"({o})")
    d, orig = c10_case("copied", *C10_TP[0][1:], copied=True)
    n, o = c10_verdict(new_vd, d, orig), c10_verdict(old_vd, d, orig)
    ok(f"C10 {tree} a header that carries text, copied: passes now and before", n == o == ["PASS"], f"({n}, {o})")
    # THE WHOLE SCRIPT, by content: the rendered Step 8 group reads PASS with the empty header named as needing no
    # copy, where it read FAIL before.
    d, orig = c10_case("whole", *C10_FP[0][1:])
    for which, script in (("now", ROOT / tree / "scripts" / "verify_diligence.py"),
                          ("before", OLD_DIR / (tag(tree) + "verify_diligence.py"))):
        r = subprocess.run([sys.executable, str(script), str(d), "--orig-docx", str(orig), "--report-only"],
                           capture_output=True, text=True, encoding="utf-8", errors="replace", env=F10_ENV, cwd=d)
        line = next((ln for ln in r.stdout.splitlines() if ln.strip().endswith("Step 8: aux-file translation")), "")
        if which == "now":
            ok(f"C10 {tree}, the whole script: Step 8 reads PASS and names the empty header",
               "[PASS]" in line and "need no copy: word/header1.xml" in r.stdout, f"(rc={r.returncode}) {line!r}")
        else:
            ok(f"C10 {tree}, the whole script: PROVED Step 8 read FAIL before", "[FAIL]" in line,
               f"(rc={r.returncode}) {line!r}")

# =============================================================================
print("\nC29 — a checker prints its finding on any console, and apply tells a crash from a gate")
print("-" * 96)

# A Windows console whose output is captured -- Claude Code's, any pipe -- writes cp1252, and Python raises on
# a character cp1252 cannot hold: an arrow in a finding's own words, a Polish letter echoed from the document.
# The checker died mid-message on exit 1, and apply called the crash a deliberate block -- or, under
# block_codes={2}, a WARN, carrying on past a check that never finished. Register C29; 14.9.1 of
# PLAN-2-step-b.md section 3.14. THE CONSOLE IS SET IN THE CHILD'S ENVIRONMENT: this interpreter's own stdout
# is reconfigured above, and nothing done to it reaches a child. Each case runs in a workdir of its own and
# names its files by RELATIVE path, so a UTF-8 run and a cp1252 run print the same words.
import ast  # noqa: E402

# --- 14.9.1 cases: begin
C29_DOC = ('<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>'
           '<w:p><w:r><w:t>The room opens at nine.</w:t></w:r></w:p></w:body></w:document>')
C29_FINDINGS = (
    # (label, script, paragraphs, its flags as apply passes them, PROVED to crash on cp1252 before)
    ("the scanner's finding, an arrow in its own words", "validate_segment_shapes.py",
     [{"idx": 0, "text": "invented", "en": "theAgreement applies.", "en_segments": [
         {"type": "regular", "en": "the"}, {"type": "ins", "en": "Agreement applies."}]}], ["--strict"], True),
    ("reject-all's finding, an arrow in its own words", "validate_reject_all.py",
     [{"idx": 0, "text": "x", "en_segments": [
         {"type": "regular", "en": "The keys stay with the Buyer.The office opens at nine. "},
         {"type": "ins", "en": "The tenant agrees."}]}], [], True),
    ("the retention WARN, a sign in its own words", "validate_translations.py",
     [{"idx": 0, "text": 'Il servizio "Pulizia Uffici Centro Nord Est" inizia ogni lunedi mattina alle nove.',
       "en": "The cleaning service starts every Monday morning at nine."}], [], True),
    ("a token finding, a Polish letter echoed from the declared English alone", "validate_apply.py",
     [{"idx": 0, "text": "invented", "en": "The Wa" + chr(0x142) + "ek office opens at nine."}],
     ["document.xml", "--strict"], True),
    ("the en_runs block, on the error stream, which Python always escapes", "validate_en_runs.py",
     [{"idx": 0, "text": "x", "en": "The office opens.", "en_runs": [{"start": 0, "end": 5, "bold": True}]}],
     [], False),
)
C29_CRASH = "print('[probe] checking the batch'); raise ValueError('invented')"
C29_ARROW = "print(chr(0x2192))"
C29_GATE2 = "import sys; print('[probe] invented finding', file=sys.stderr); sys.exit(2)"
C29_TB0 = ("import traceback" + chr(10) + "try:" + chr(10) + "    raise ValueError('invented')" + chr(10)
           + "except ValueError:" + chr(10) + "    traceback.print_exc()")
C29_COLOURS = {"PYTHON_COLORS": "1", "FORCE_COLOR": "1"}
# --- 14.9.1 cases: end
C29_GUARD = ast.parse("for _stream in (sys.stdout, sys.stderr):" + chr(10)
                      + "    try:" + chr(10)
                      + "        _stream.reconfigure(errors='backslashreplace')" + chr(10)
                      + "    except (AttributeError, ValueError):" + chr(10)
                      + "        pass" + chr(10)).body[0]
C29_DRIVER = TMP / "c29_driver.py"
# apply's own _run_validator, driven from a process whose OWN console writes cp1252, as apply's is under a
# captured Windows console: it prints the banner's kind and nothing of the banner's text.
C29_DRIVER.write_text(
    "import importlib.util, json, os, sys" + chr(10)
    + "path, codes, argv = sys.argv[1], json.loads(sys.argv[2]), json.loads(sys.argv[3])" + chr(10)
    + "sys.path.insert(0, os.path.dirname(path))" + chr(10)
    + "spec = importlib.util.spec_from_file_location('c29_apply', path)" + chr(10)
    + "ap = importlib.util.module_from_spec(spec)" + chr(10)
    + "spec.loader.exec_module(ap)" + chr(10)
    + "try:" + chr(10)
    + "    ap._run_validator('probe', argv, block_codes=None if codes is None else set(codes))" + chr(10)
    + "    print('@@ continued', flush=True)" + chr(10)
    + "except RuntimeError as e:" + chr(10)
    + "    m = str(e)" + chr(10)
    + "    print('@@ ' + ('crash' if 'VALIDATOR CRASHED' in m else 'install' if 'FILE INTEGRITY' in m" + chr(10)
    + "                   else 'gate' if 'SKILL GATE FIRED' in m else 'other'), flush=True)" + chr(10)
    + "    print('@@ banner-clean ' + str('BLOCK' not in m and 'GATE FIRED' not in m and 'rule 6' in m" + chr(10)
    + "                                    and 're-install' in m), flush=True)" + chr(10),
    encoding="utf-8")


def c29_old_tree(tree):
    """Every script of <tree>/scripts at the pin, side by side, so an old checker imports its own siblings."""
    d = TMP / f"c29-old-{tree}"
    d.mkdir()
    names = subprocess.run(["git", "ls-tree", "--name-only", f"{REF}:{tree}/scripts/"], capture_output=True,
                           text=True, cwd=ROOT, check=True).stdout.split()
    for n in names:
        if n.endswith(".py"):
            (d / n).write_bytes(subprocess.run(["git", "show", f"{REF}:{tree}/scripts/{n}"], capture_output=True,
                                               cwd=ROOT, check=True).stdout)
    return d


C29_BEFORE = "95b865c"   # the commit before 14.9.1: section (4)'s runners are measured against it
_c29_trees = {}


def c29_tree(tree, ref):
    """Every script of <tree>/scripts at `ref`, built once."""
    if (tree, ref) not in _c29_trees:
        d = TMP / f"c29-at-{ref}-{tree}"
        d.mkdir()
        names = subprocess.run(["git", "ls-tree", "--name-only", f"{ref}:{tree}/scripts/"], capture_output=True,
                               text=True, cwd=ROOT, check=True).stdout.split()
        for n in names:
            if n.endswith(".py"):
                (d / n).write_bytes(subprocess.run(["git", "show", f"{ref}:{tree}/scripts/{n}"],
                                                   capture_output=True, cwd=ROOT, check=True).stdout)
        for n in ("post_process.py", "repack_docx.py"):
            if (d / n).read_bytes() == (ROOT / tree / "scripts" / n).read_bytes():
                print(f"VOID — {tree}/{n} at {ref} is the working tree's: section (4)'s 'before' would be the fix.")
                sys.exit(1)
        _c29_trees[(tree, ref)] = d
    return _c29_trees[(tree, ref)]


C29_DRIVER2 = TMP / "c29_driver2.py"
# One function of a module, called from a process whose own console is cp1252; '@archive' is an in-memory
# archive, '@dir' the module's folder. It prints the raised banner's kind and nothing of its text.
C29_DRIVER2.write_text(
    "import importlib.util, io, json, os, sys" + chr(10)
    + "path, func, args = sys.argv[1], sys.argv[2], json.loads(sys.argv[3])" + chr(10)
    + "d = os.path.dirname(path)" + chr(10)
    + "sys.path.insert(0, d)" + chr(10)
    + "args = [io.BytesIO(b'x') if a == '@archive' else d if a == '@dir' else a for a in args]" + chr(10)
    + "spec = importlib.util.spec_from_file_location('c29_mod', path)" + chr(10)
    + "m = importlib.util.module_from_spec(spec)" + chr(10)
    + "spec.loader.exec_module(m)" + chr(10)
    + "try:" + chr(10)
    + "    getattr(m, func)(*args)" + chr(10)
    + "    print('@@ continued', flush=True)" + chr(10)
    + "except BaseException as e:" + chr(10)
    + "    s = str(e)" + chr(10)
    + "    print('@@ ' + ('crash' if 'VALIDATOR CRASHED' in s else 'install' if 'FILE INTEGRITY' in s" + chr(10)
    + "                   else 'gate' if 'SKILL GATE FIRED' in s else 'other'), flush=True)" + chr(10),
    encoding="utf-8")


def c29_call(module_path, func, args, cwd):
    r = subprocess.run([sys.executable, str(C29_DRIVER2), str(module_path), func, json.dumps(args)],
                       capture_output=True, env=dict(os.environ, PYTHONIOENCODING="cp1252"), cwd=cwd)
    marks = [ln[3:].strip() for ln in r.stdout.decode("cp1252", "replace").splitlines() if ln.startswith("@@ ")]
    return marks[0] if marks else f"none, rc {r.returncode}"


def c29_child(script_path, case, enc):
    """rc, stdout bytes and stderr text of one checker run as apply runs it, on a console writing `enc`."""
    wd = TMP / f"c29-{next(_G13_N)}"
    wd.mkdir()
    (wd / "paragraphs.json").write_text(json.dumps(case[2]), encoding="utf-8")
    (wd / "document.xml").write_text(C29_DOC, encoding="utf-8")
    r = subprocess.run([sys.executable, str(script_path), "paragraphs.json"] + case[3], capture_output=True,
                       env=dict(os.environ, PYTHONIOENCODING=enc), cwd=wd)
    return r.returncode, r.stdout, r.stderr.decode(enc, errors="replace")


def c29_drive(apply_path, argv, codes, extra=None):
    """The banner's kind apply raised, its banner-clean flag, and the driver's stdout and stderr as text."""
    r = subprocess.run([sys.executable, str(C29_DRIVER), str(apply_path),
                        json.dumps(None if codes is None else sorted(codes)), json.dumps(argv)],
                       capture_output=True, env=dict(os.environ, PYTHONIOENCODING="cp1252", **(extra or {})),
                       cwd=TMP)
    out = r.stdout.decode("cp1252", errors="replace")
    marks = [ln[3:].strip() for ln in out.splitlines() if ln.startswith("@@ ")]
    return (marks[0] if marks else f"none, rc {r.returncode}"), marks[1:], out, r.stderr.decode("cp1252", "replace")


C29_TB = "Traceback (most recent call last)"
for tree in ("uk", "us"):
    s_dir = ROOT / tree / "scripts"
    old_dir = c29_old_tree(tree)
    for _s in ("apply_translations_textmatch.py",) + tuple(c[1] for c in C29_FINDINGS):
        assert_baseline_differs(_s, tree)
    # (1) EACH CHECKER, A CHILD ON A cp1252 CONSOLE: the whole finding printed now, every byte a UTF-8 run gives save
    # what cp1252 cannot hold, which arrives as an escape; and the same exit.
    for case in C29_FINDINGS:
        label, script, _d, _f, crashed_before = case
        u_rc, u_out, u_err = c29_child(s_dir / script, case, "utf-8")
        n_rc, n_out, n_err = c29_child(s_dir / script, case, "cp1252")
        o_rc, _o_out, o_err = c29_child(old_dir / script, case, "cp1252")
        ok(f"C29 {tree} {label}: no crash on cp1252 now, the exit a UTF-8 run gives",
           C29_TB not in n_err and n_rc == u_rc, f"(rc {n_rc}, on UTF-8 {u_rc})")
        ok(f"C29 {tree} {label}: every line printed on cp1252, what it cannot hold as an escape",
           n_out == u_out.decode("utf-8").encode("cp1252", "backslashreplace") and n_err == u_err,
           f"({len(n_out)} bytes, {len(u_out)} on UTF-8)")
        if crashed_before:
            ok(f"C29 {tree} {label}: PROVED it crashed on cp1252 before",
               C29_TB in o_err and "UnicodeEncodeError" in o_err, f"(rc {o_rc})")
        else:
            # Its exit moved since the pin for a reason of its own -- the tiling rule, C13, came later.
            ok(f"C29 {tree} {label}: no crash on cp1252 before either", C29_TB not in o_err, f"(rc {o_rc})")
    # (2) APPLY'S _run_validator, DRIVEN FROM A cp1252 CONSOLE, the pinned apply beside today's.
    pj = TMP / f"c29-scan-{tree}.json"
    pj.write_text(json.dumps(C29_FINDINGS[0][2]), encoding="utf-8")
    cut = TMP / f"c29-cut-{tree}.py"
    vss = (s_dir / "validate_segment_shapes.py").read_text(encoding="utf-8")
    cut_at = "ap.add_argument('paragraphs_json',"
    cut.write_text(vss[:vss.index(cut_at) + len(cut_at)], encoding="utf-8")
    py = sys.executable
    new_ap, old_ap = s_dir / "apply_translations_textmatch.py", old_dir / "apply_translations_textmatch.py"
    for label, argv, codes, extra, before, now in (
            ("a crash", [py, "-c", C29_CRASH], None, None, "gate", "crash"),
            ("a crash under block_codes={2}", [py, "-c", C29_CRASH], {2}, None, "continued", "crash"),
            ("a script too damaged to start", [py, str(cut), str(pj)], None, None, "gate", "crash"),
            ("a script too damaged to start, under block_codes={2}", [py, str(cut), str(pj)], {2}, None,
             "continued", "crash"),
            # NOT a runtime crash: its Traceback header is never coloured, so it would read as a crash with the
            # colour stripping gone. A script that cannot start prints no header and only a coloured File line.
            ("a script too damaged to start, in forced colours", [py, str(cut), str(pj)], None, C29_COLOURS, "gate",
             "crash"),
            ("a child with no guard printing an arrow", [py, "-c", C29_ARROW], None, None, "gate", "continued")):
        n_kind, n_flags, _n_out, n_err = c29_drive(new_ap, argv, codes, extra)
        o_kind, _o_flags, _o_out, o_err = c29_drive(old_ap, argv, codes, extra)
        ok(f"C29 {tree} apply, {label}: reads as {now} now", n_kind == now, f"({n_kind})")
        ok(f"C29 {tree} apply, {label}: PROVED it read as {before} before", o_kind == before, f"({o_kind})")
        if now == "crash":
            ok(f"C29 {tree} apply, {label}: the crash banner is no gate's, names rule 6 and the re-install",
               n_flags == ["banner-clean True"], f"({n_flags})")
            mark = "SyntaxError" if argv[1] == str(cut) else C29_TB
            ok(f"C29 {tree} apply, {label}: the crash report reaches the operator once", n_err.count(mark) == 1,
               f"({mark}: {n_err.count(mark)}x)")
    # THE TRUE POSITIVES: a real gate still reads as a block, every clean exit as it did, before and now alike.
    n_kind, _f, n_out, n_err = c29_drive(new_ap, [py, str(s_dir / "validate_segment_shapes.py"), str(pj), "--strict"],
                                         None)
    o_kind, _f, _o, o_err = c29_drive(old_ap, [py, str(old_dir / "validate_segment_shapes.py"), str(pj), "--strict"],
                                      None)
    ok(f"C29 {tree} apply, the scanner's real finding on cp1252: a gate now, its FIX line printed, no crash",
       n_kind == "gate" and (chr(92) + "u2192 FIX:") in n_out and C29_TB not in n_err, f"({n_kind})")
    ok(f"C29 {tree} apply, the scanner's real finding on cp1252: PROVED a crash read as a gate before",
       o_kind == "gate" and C29_TB in o_err, f"({o_kind})")
    for label, argv, codes, want in (
            ("exit 0", [py, "-c", "import sys; sys.exit(0)"], None, "continued"),
            ("exit 1", [py, "-c", "import sys; sys.exit(1)"], None, "gate"),
            ("exit 2 with its message, under block_codes={2}", [py, "-c", C29_GATE2], {2}, "gate"),
            ("exit 1 under block_codes={2}, a WARN", [py, "-c", "import sys; sys.exit(1)"], {2}, "continued"),
            ("exit 3, a truncated install", [py, "-c", "import sys; sys.exit(3)"], {2}, "install"),
            ("a crash report on exit 0", [py, "-c", C29_TB0], None, "continued")):
        n_kind, _f, _n_out, n_err = c29_drive(new_ap, argv, codes)
        o_kind, _f, _o_out, _o_err = c29_drive(old_ap, argv, codes)
        ok(f"C29 {tree} apply, TRUE POSITIVE {label}: reads as {want} now and before", n_kind == o_kind == want,
           f"(now {n_kind}, before {o_kind})")
        if argv[-1] == C29_GATE2:
            ok(f"C29 {tree} apply, {label}: the gate's own message reaches the operator once",
               n_err.count("[probe] invented finding") == 1, f"({n_err.count('[probe] invented finding')}x)")
    # (3) THE GUARD, BY SOURCE AND BY RUN: the first statement of every script's __main__ block, one text, and
    # nowhere else; each file's own guard, run in a child on cp1252, printing what it cannot hold as an escape.
    files = sorted(s_dir.glob("*.py"))
    ok(f"C29 {tree}: all {len(files)} shipped scripts read, the census's population", len(files) == 20)
    want = (chr(92) + "u2192" + chr(92) + "u0142" + os.linesep).encode("ascii")
    for f in files:
        src = f.read_text(encoding="utf-8")
        mains = [s for s in ast.parse(src).body if isinstance(s, ast.If) and isinstance(s.test, ast.Compare)
                 and getattr(s.test.left, "id", None) == "__name__"]
        first = mains[0].body[0] if len(mains) == 1 else None
        ok(f"C29 {tree} {f.name}: the guard is its __main__ block's first statement, and nowhere else",
           first is not None and ast.dump(first) == ast.dump(C29_GUARD)
           and src.count("reconfigure(errors='backslashreplace')") == 1, "")
        old_src = (old_dir / f.name).read_text(encoding="utf-8") if (old_dir / f.name).exists() else ""
        ok(f"C29 {tree} {f.name}: PROVED no guard before", "reconfigure(errors='backslashreplace')" not in old_src, "")
        if first is not None:
            r = subprocess.run([py, "-c", "import sys" + chr(10) + ast.unparse(first) + chr(10)
                                + "print(chr(0x2192) + chr(0x142))"], capture_output=True,
                               env=dict(os.environ, PYTHONIOENCODING="cp1252"))
            ok(f"C29 {tree} {f.name}: its own guard, run on cp1252, prints the escapes", r.returncode == 0
               and r.stdout == want, f"(rc {r.returncode}, {r.stdout[:20]!r})")
    # (4) THE OTHER RUNNERS OF THE SAME SHAPE, found by the review: post_process's two and repack's two, each run
    # from a cp1252 console on a copy of the tree whose child is replaced -- a crash, a clean refusal, exit 3. Their
    # "before" is the commit before this sub-step: the pin predates the delivered-document gate.
    for label, module, func, child, body, args, before, now in (
            ("post_process's post-strip gate, its child crashing", "post_process.py",
             "_run_validate_apply_post_strip", "validate_apply.py", C29_CRASH, ["doc.xml", "p.json"], "gate", "crash"),
            ("post_process's post-strip gate, a truncated child (exit 3)", "post_process.py",
             "_run_validate_apply_post_strip", "validate_apply.py", "import sys; sys.exit(3)", ["doc.xml", "p.json"],
             "gate", "install"),
            ("post_process's post-strip gate, TRUE POSITIVE a clean refusal (exit 1)", "post_process.py",
             "_run_validate_apply_post_strip", "validate_apply.py", "import sys; sys.exit(1)", ["doc.xml", "p.json"],
             "gate", "gate"),
            ("post_process's strip_noop runner, its child crashing", "post_process.py",
             "_run_strip_noop_subprocess", "strip_noop_tracked_changes.py", C29_CRASH, ["doc.xml"], "other", "crash"),
            ("post_process's strip_noop runner, TRUE POSITIVE a clean failure (exit 2)", "post_process.py",
             "_run_strip_noop_subprocess", "strip_noop_tracked_changes.py", "import sys; sys.exit(2)", ["doc.xml"],
             "other", "other"),
            ("repack's pre-repack runner, its child crashing", "repack_docx.py", "_run_pre_repack_validator",
             None, None, ["probe", [py, "-c", C29_CRASH]], "other", "crash"),
            ("repack's pre-repack runner, TRUE POSITIVE a clean refusal (exit 1)", "repack_docx.py",
             "_run_pre_repack_validator", None, None, ["probe", [py, "-c", "import sys; sys.exit(1)"]], "other",
             "other"),
            ("repack's delivered-document gate, its child crashing", "repack_docx.py", "_delivered_gate",
             # Measured: before, its refusal banner read the crash as a fired gate -- C29's own lie, a fourth time.
             "validate_apply.py", C29_CRASH, ["o.docx", "@archive", "p.json", "@dir"], "gate", "crash")):
        kinds = {}
        for when, src in (("now", s_dir), ("before", c29_tree(tree, C29_BEFORE))):
            d = TMP / f"c29-run-{next(_G13_N)}"
            shutil.copytree(src, d)
            if child:
                (d / child).write_text(body, encoding="utf-8")
            kinds[when] = c29_call(d / module, func, args, d)
        ok(f"C29 {tree} {label}: reads as {now} now", kinds["now"] == now, f"({kinds['now']})")
        ok(f"C29 {tree} {label}: read as {before} before", kinds["before"] == before, f"({kinds['before']})")

# =============================================================================
# THE DANGLING-ENDING RULE READ CAPITALS AS NOTHING (sub-step 14.9.6, found at 14.6 beside G3). Its endings
# were matched in lower case only, so a paragraph written in capitals and cut off mid-sentence was never
# flagged. An ending in capitals now counts where every cased letter of the paragraph is a capital, never the
# lone `A`, which in capitals reads as a label. Invented sentences.
# =============================================================================
print("\n14.9.6 — the dangling-ending rule reads a paragraph written in capitals")
print("-" * 96)
CAPS_TP = (("cut off on FOR", "THE SUPPLIER SHALL NOT BE LIABLE TO THE PURCHASER FOR"),
           ("cut off on THE", "NOTHING IN THIS AGREEMENT SHALL LIMIT OR EXCLUDE THE"),
           ("cut off on AND", "EACH PARTY SHALL BEAR ITS OWN COSTS AND EXPENSES AND"),
           ("cut off on SHALL, digits beside it", "THE 2026 PRICE OF 500 UNITS PAYABLE BY THE BUYER SHALL"))
CAPS_QUIET = (("a label in capitals, SCHEDULE A", "THE SERVICES ARE DESCRIBED IN FULL IN SCHEDULE A"),
              ("a label in capitals, PART A", "THE PRICE IS PAYABLE IN THE MANNER SET OUT IN PART A"),
              ("mixed case, a capitalised Will", "The executor shall act strictly in accordance with the Will"),
              ("mixed case, Schedule A", "The services are described in full in Schedule A"),
              ("capitals, a list connective ; AND/OR", "THE SUPPLIER SHALL MAINTAIN INSURANCE COVER; AND/OR"),
              ("capitals, a list connective ; AND", "THE SUPPLIER SHALL MAINTAIN INSURANCE COVER; AND"),
              ("capitals, a signing lead-in", "SIGNED AS A DEED FOR AND ON BEHALF OF"),
              ("capitals, a heading under five words", "PAYMENT SUBJECT TO THE"),
              ("capitals, a full stop", "THE SUPPLIER SHALL NOT BE LIABLE FOR ANY INDIRECT LOSS."),
              # At review, 2026-11-10: in capitals the month MAY and the noun WILL lose the capital letter that
              # tells them from the auxiliary in mixed case, so like the lone A they are never an ending there.
              ("capitals, the month MAY", "THIS DEED IS MADE ON THE FIRST DAY OF MAY"),
              ("capitals, the noun WILL", "THIS CODICIL IS SUPPLEMENTAL TO MY LAST WILL"),
              ("one lower-case letter", "THE SUPPLIER SHALL NOT BE LIABLE TO THE PURCHASEr FOR"))
for tree in ("uk", "us"):
    old_qc = OLD_QC if tree == "uk" else load_old("quality_check.py", "us")
    new_qc = NEW_QC if tree == "uk" else load_new("quality_check.py", "us")

    def trunc(mod, text):
        return [i for i in mod.check_truncation(doc(para(text)), False, None) if i.startswith("Dangling ending")]

    for label, text in CAPS_TP:
        n, o = trunc(new_qc, text), trunc(old_qc, text)
        ok(f"CAPS {tree} TRUE POSITIVE {label}: fires now", bool(n), f"({n})")
        ok(f"CAPS {tree} TRUE POSITIVE {label}: PROVED silent before", not o, f"({o})")
    for label, text in CAPS_QUIET:
        n, o = trunc(new_qc, text), trunc(old_qc, text)
        ok(f"CAPS {tree} {label}: quiet now", not n, f"({n})")
        ok(f"CAPS {tree} {label}: quiet before", not o, f"({o})")

# =============================================================================
# THE LANGUAGE WIDENINGS (sub-step 14.9.7): G7's three items 14.5 declared and did not build. Finnish's own
# marks, ”…” and ’…’, read when Finnish is declared, each opening only where no letter precedes it and
# closing only where none follows; the comma-set marker, Finnish law's only form, in every language; two
# lead-ins published law writes; and a Japanese or Chinese span counted in words, 0.6 a CJK letter, and
# checked by the quote-count condition alone, being never verbatim in English. "Before" is W97_BEFORE, the
# code before this sub-step; a Finnish marker the old code exempted in its typographic twin is proved at the
# suite's pinned baseline instead. Every string INVENTED, on office services.
# =============================================================================
print("\n14.9.7 — the language widenings: Finnish's marks, the comma-set marker, two lead-ins, the CJK word count")
print("-" * 96)
W97_BEFORE = os.environ.get("LT_W97_BEFORE", "b39f438")   # main before 14.9.7
FI = "finnish"
NO_SPAN = "The parties carry out the project on time."
_w97 = {}


def w97_old(tree):
    """<tree>'s validate_translations at W97_BEFORE -- VOID if that is the working tree's."""
    if tree not in _w97:
        d = TMP / f"w97-at-{W97_BEFORE}-{tree}"
        d.mkdir()
        for n in ("validate_translations.py", "source_language_markers.py"):
            (d / n).write_bytes(subprocess.run(["git", "show", f"{W97_BEFORE}:{tree}/scripts/{n}"],
                                               capture_output=True, cwd=ROOT, check=True).stdout)
        if (d / "validate_translations.py").read_bytes() == \
                (ROOT / tree / "scripts" / "validate_translations.py").read_bytes():
            print(f"VOID — {tree}/validate_translations.py at {W97_BEFORE} is the working tree's: "
                  f"every 'before' below would be the fix itself.")
            sys.exit(1)
        name = f"w97old_{tree}_validate_translations"
        spec = importlib.util.spec_from_file_location(name, d / "validate_translations.py")
        mod = importlib.util.module_from_spec(spec)
        sys.modules[name] = mod
        sys.path.insert(0, str(d))
        try:
            spec.loader.exec_module(mod)
        finally:
            sys.path.remove(str(d))
        _w97[tree] = mod
    return _w97[tree]


def w97_twin(s):
    """The paragraph with its first Finnish opening mark typographic, as the old code read it."""
    i = min((k for k in (s.find("”"), s.find("’")) if k >= 0), default=-1)
    return s if i < 0 else s[:i] + ("“" if s[i] == "”" else "‘") + s[i + 1:]


# Finnish declared: (label, source, the span) -- silent with KEEP, firing with DROP, PROVED unread before
W97_FI_MARKS = (
    ("a bracket marker in ”…”",
     "Osapuolet tekevät sopimuksen (jäljempänä ”Toimistojen siivouspalvelujen puitesopimus vuosille 2026–2030”).",
     "Toimistojen siivouspalvelujen puitesopimus vuosille 2026–2030"),
    ("a bracket marker in ’…’", "Osapuolet tekevät sopimuksen (jäljempänä ’Siivouspalvelujen Puitesopimus’).",
     "Siivouspalvelujen Puitesopimus"),
)
# The comma-set marker: (label, language, source, the span) -- silent with KEEP and firing with DROP now,
# PROVED to fire before with KEEP (a Finnish mark through its typographic twin)
W97_COMMA = (
    ("Finnish, ’…’", FI, "Palveluntarjoaja, jäljempänä ’Siivouspalvelujen Toimittaja’, sitoutuu sopimukseen.",
     "Siivouspalvelujen Toimittaja"),
    ("Finnish, ”…”", FI, "Palveluntarjoaja, jäljempänä ”Toimistojen siivouspalvelujen pääasiallinen toimittaja "
                         "Helsingissä”, sitoutuu sopimukseen.",
     "Toimistojen siivouspalvelujen pääasiallinen toimittaja Helsingissä"),
    ("Italian", "italian", 'Il Cliente affida i servizi alla Società, di seguito "Fornitore dei Servizi di Pulizia '
                           'degli Uffici", che accetta.', "Fornitore dei Servizi di Pulizia degli Uffici"),
    ("Italian, closing the paragraph", "italian", 'Il Cliente affida i servizi alla Società, di seguito "Fornitore '
                                                  'dei Servizi di Pulizia degli Uffici".',
     "Fornitore dei Servizi di Pulizia degli Uffici"),
    ("Dutch", "dutch", 'De opdrachtgever sluit een overeenkomst met de leverancier, hierna "Leverancier van '
                       'Schoonmaakdiensten voor Kantoren", die aanvaardt.',
     "Leverancier van Schoonmaakdiensten voor Kantoren"),
    ("Dutch, a participle closing it", "dutch", 'De opdrachtgever sluit een overeenkomst met de leverancier, hierna '
                                                'de "Leverancier van Schoonmaakdiensten voor Kantoren" genoemd, die '
                                                'aanvaardt.', "Leverancier van Schoonmaakdiensten voor Kantoren"),
)
# Lead-ins published law writes: (label, language, source, the span) -- as W97_COMMA
W97_LEADS = (
    ("Italian `in prosieguo`", "italian",
     'Le parti stipulano il contratto (in prosieguo "Contratto Quadro per i Servizi di Pulizia").',
     "Contratto Quadro per i Servizi di Pulizia"),
    ("Spanish `cada una`, then a second lead-in", "spanish",
     'Las partes firman el contrato (cada una denominada en lo sucesivo "Parte del Contrato de Servicios de '
     'Limpieza").', "Parte del Contrato de Servicios de Limpieza"),
    ("Italian, an adverb before the lead-in", "italian",
     'Le parti (congiuntamente, di seguito, le "Parti del Contratto di Servizi di Pulizia") firmano.',
     "Parti del Contratto di Servizi di Pulizia"),
)
# (label, language, source, English, the span, before) -- fires now; before: "fired" or "silent"
W97_TP = (
    ("an adverb after a comma is no formula", "italian",
     'Le parti, insieme "Gruppo dei Servizi di Pulizia degli Uffici", firmano.', KEEP,
     "Gruppo dei Servizi di Pulizia degli Uffici", "fired"),
    ("a comma-set span with words after it", "italian",
     'Il Cliente affida i servizi alla Società, di seguito "Fornitore dei Servizi di Pulizia degli Uffici" e alla '
     'sua controllata.', KEEP, "Fornitore dei Servizi di Pulizia degli Uffici", "fired"),
    ("a Finnish name dropped in ”…”", FI,
     "Osapuolet toteuttavat hankkeen ”Toimistokeskus Pohjoinen Yksi Kaksi Kolme” määräajassa.", NO_SPAN,
     "Toimistokeskus Pohjoinen Yksi Kaksi Kolme", "silent"),
    ("a Finnish name dropped in ’…’", FI, "Osapuolet toteuttavat hankkeen ’Toimistokeskus Pohjoinen’ määräajassa.",
     NO_SPAN, "Toimistokeskus Pohjoinen", "silent"),
    ("a Finnish name holding an apostrophe", FI, "Osapuolet toteuttavat hankkeen ’Vaa’an Toimistokeskus’ määräajassa.",
     NO_SPAN, "Vaa’an Toimistokeskus", "silent"),
    ("a Finnish name after an inch mark", FI,
     "Näytön koko on 24” ja hanke on ”Toimistokeskus Pohjoinen Yksi Kaksi Kolme”.", NO_SPAN,
     "Toimistokeskus Pohjoinen Yksi Kaksi Kolme", "silent"),
    ("a Japanese name dropped, DECLARED BLIND until now", "japanese",
     "当事者は「事務所清掃センター北棟」の業務を実施する。", "The parties carry out the services.",
     "事務所清掃センター北棟", "silent"),
    ("a Japanese marker dropped with its quotes", "japanese",
     "当事者は本契約（以下「事務所清掃業務委託契約」という。）を締結する。", DROP, "事務所清掃業務委託契約", "silent"),
    ("a Japanese name dropped beside a short term rendered unquoted", "japanese",
     "当事者は「本契約」に基づき「北区事務所清掃サービス契約」を履行する。",
     "Under this Agreement the parties perform the contract.", "北区事務所清掃サービス契約", "silent"),
    ("a Finnish marker dropped, two apostrophes in the English", FI,
     "Osapuolet tekevät sopimuksen (jäljempänä ”Toimistojen siivouspalvelujen puitesopimus vuosille 2026–2030”).",
     "The parties renew the ’90 contract for 2026 and 2030’ s terms.",
     "Toimistojen siivouspalvelujen puitesopimus vuosille 2026–2030", "silent"),
    ("a Chinese name dropped in “…”", "chinese", "双方共同实施“北区办公楼清洁服务中心项目”。",
     "The parties jointly carry out the project.", "北区办公楼清洁服务中心项目", "silent"),
    ("a Latin name in 「…」 dropped", "japanese", "当事者は「North Office Cleaning Services Centre」の業務を実施する。",
     "The parties carry out the services.", "North Office Cleaning Services Centre", "silent"),
)
# (label, language, source, English) -- silent now
W97_QUIET = (
    ("Finnish apostrophes inside words never pair", FI,
     "Sopimus koskee vaa’an ja raa’an mittalaitteiden kalibrointia.", "The contract covers calibration."),
    ("a Finnish apostrophe inside a word opens no span before a ’…’ name", FI,
     "Sopimus koskee vaa’an ja ’Toimistokeskus Pohjoinen’ kalibrointia.",
     "The contract covers the scales of Toimistokeskus Pohjoinen."),
    ("Finnish ”…” never runs across “…”", FI,
     "Sopimus koskee “Toimisto Pohjoinen 1” sekä Helsingin keskustassa sijaitsevaa uutta “Toimisto Etelä 2” "
     "rakennusta.", "The contract covers the two office buildings."),
    ("Finnish marks unread when Finnish is not declared", None,
     "Osapuolet toteuttavat hankkeen ”Toimistokeskus Pohjoinen Yksi Kaksi Kolme” määräajassa.", NO_SPAN),
    ("a Japanese marker, the English keeping its quotes", "japanese",
     "当事者は本契約（以下「事務所清掃業務委託契約」という。）を締結する。", KEEP),
    ("a Chinese name kept with its quotes", "chinese", "双方共同实施“北区办公楼清洁服务中心项目”。",
     'The parties jointly carry out the "North District Office Cleaning Service Centre Project".'),
    ("a short Japanese term, under the threshold", "japanese", "当事者は「清掃契約書」に署名する。",
     "The parties sign the contract."),
    ("a Japanese name kept with its quotes beside a short term rendered unquoted", "japanese",
     "当事者は「本契約」に基づき「北区事務所清掃サービス契約」を履行する。",
     'Under this Agreement the parties perform the "North District Office Cleaning Services Contract".'),
    ("a Japanese title in 『…』 is not read", "japanese", "当事者は『事務所清掃業務標準手順書第二版』に従う。",
     "The parties follow the Standard Office Cleaning Procedures Manual, Second Edition."),
    ("a Japanese name kept in its own script", "japanese", "当事者は「事務所清掃センター北棟」の業務を実施する。",
     "The parties carry out the services of 事務所清掃センター北棟."),
)
for tree in ("uk", "us"):
    new_vt, old_vt, b_vt = load_new("validate_translations.py", tree), load_old("validate_translations.py", tree), \
        w97_old(tree)

    def spans(mod, src, en, lang):
        return [p for _s, p in mod._check_quoted_phrase_retention({"text": src, "en": en}, lang)]

    for label, src, span in W97_FI_MARKS:
        ok(f"W97 {tree} Finnish {label}: silent now", not spans(new_vt, src, KEEP, FI))
        ok(f"W97 {tree} Finnish {label} dropped with its quotes: fires now", span in spans(new_vt, src, DROP, FI))
        ok(f"W97 {tree} Finnish {label} dropped with its quotes: PROVED unread before",
           not spans(b_vt, src, DROP, FI))
        tw = w97_twin(src)
        ok(f"W97 {tree} Finnish {label}: its twin PROVED to fire at {REF}",
           span in [p for _s, p in old_vt._check_quoted_phrase_retention({"text": tw, "en": KEEP})])
    for group, rows in (("comma-set", W97_COMMA), ("lead-in", W97_LEADS)):
        for label, lang, src, span in rows:
            ok(f"W97 {tree} {group} {label}: silent now", not spans(new_vt, src, KEEP, lang),
               f"({spans(new_vt, src, KEEP, lang)})")
            ok(f"W97 {tree} {group} {label} dropped with its quotes: fires now", span in spans(new_vt, src, DROP, lang))
            ok(f"W97 {tree} {group} {label}: PROVED to fire before" + (" (its twin)" if lang == FI else ""),
               span in spans(b_vt, w97_twin(src) if lang == FI else src, KEEP, lang))
    for label, lang, src, en, span, before in W97_TP:
        n, b = spans(new_vt, src, en, lang), spans(b_vt, src, en, lang)
        ok(f"W97 {tree} TRUE POSITIVE {label}: fires now, on that span", span in n, f"({n})")
        ok(f"W97 {tree} TRUE POSITIVE {label}: {'fired' if before == 'fired' else 'PROVED silent'} before",
           (span in b) if before == "fired" else not b, f"({b})")
    for label, lang, src, en in W97_QUIET:
        n = spans(new_vt, src, en, lang)
        ok(f"W97 {tree} {label}: silent now", not n, f"({n})")
    # THE COUNT ITSELF: a span holding no CJK letter counts exactly its words, as before; CJK at 0.6 a letter.
    sw = getattr(new_vt, "_span_words", None)
    latin = [s for row in G7L + W97_COMMA + W97_LEADS for s in row if isinstance(s, str)] + \
            [s for row in G7L_TP for s in row[2:4]]
    ok(f"W97 {tree} a span with no CJK letter counts its words exactly as before ({len(latin)} strings)",
       sw is not None and all(sw(s) == len(s.split()) for s in latin))
    ok(f"W97 {tree} nine CJK letters reach the double threshold and eight do not",
       sw is not None and sw("一" * 9) >= new_vt.QUOTE_DOUBLE_MIN_WORDS > sw("一" * 8))
    ok(f"W97 {tree} four CJK letters reach the single threshold and three do not",
       sw is not None and sw("一" * 4) >= new_vt.QUOTE_SINGLE_MIN_WORDS > sw("一" * 3))
    # THE WHOLE SCRIPT, as skill Step 4 runs it: a CJK finding carries its note, a Latin one does not.
    jp = next(r for r in W97_TP if r[0].startswith("a Japanese name dropped, DECLARED"))
    for row, case, note in (("CJK", (None, jp[2], jp[3]), True),
                            ("Latin", (None, G7L_WIDE[0][1], G7L_WIDE[0][2]), False)):
        rc, out = vt_run(ROOT / tree / "scripts", f"w97-{row}-{tree}", case)
        ok(f"W97 {tree} the whole script, a {row} finding: warns {'with' if note else 'without'} the CJK note",
           rc == 1 and "Quoted source phrases NOT found" in out and ("never verbatim in English" in out) == note,
           f"(rc={rc})")

# =============================================================================
shutil.rmtree(TMP, ignore_errors=True)
print()
print("=" * 96)
if FAIL:
    print(f"FAIL — {len(FAIL)} of {CHECKED} assertions:")
    for f in FAIL:
        print(f"  · {f}")
    print("=" * 96)
    sys.exit(1)
print(f"PASS — {CHECKED} assertions. Every narrowed check is silent on its false")
print(f"positive, still fires on its true positive, and every false-positive control")
print(f"is PROVED to have fired against {REF} = {SHA[:12]}.")
print("=" * 96)
