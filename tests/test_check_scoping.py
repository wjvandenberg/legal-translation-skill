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
import json
import os
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
    "of the European Union", "of Book 6 of the Civil Code", "of Law No. 9"))
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
