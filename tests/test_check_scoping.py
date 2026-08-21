# -*- coding: utf-8 -*-
"""BRANCH 14 — every narrowed check must still catch its true positive.

WHY THIS FILE EXISTS AND WHAT IT IS GUARDING AGAINST. Branch 14 makes eight checks
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

All test content is INVENTED. No client text, no corpus material -- CLAUDE.md 5.4.
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
# 2178cce is the commit before branch 14. It is a historical fact and it does not move.
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


def assert_baseline_differs(script):
    """The baseline copy of `script` must NOT be the working-tree copy.

    A comparison that established nothing has not passed. If a rebase, a squash or a moved
    pin makes the two identical, this suite must say VOID and exit non-zero rather than
    report a green before/after it never made.
    """
    b = subprocess.run(["git", "show", f"{REF}:uk/scripts/{script}"],
                       capture_output=True, cwd=ROOT)
    if b.returncode != 0:
        print(f"VOID — cannot read {script} at {REF}. Nothing compared, nothing passed.")
        sys.exit(1)
    if b.stdout == (ROOT / "uk" / "scripts" / script).read_bytes():
        print(f"VOID — {script} at {REF} is BYTE-IDENTICAL to the working tree, so every")
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


def load_old(script):
    """Import the pre-branch version of a uk/scripts file under its own name."""
    blob = subprocess.run(["git", "show", f"{REF}:uk/scripts/{script}"],
                          capture_output=True, cwd=ROOT)
    if blob.returncode != 0:
        print(f"VOID — cannot read {script} at {REF}")
        sys.exit(1)
    path = OLD_DIR / script
    path.write_bytes(blob.stdout)
    modname = "old_" + script[:-3]
    spec = importlib.util.spec_from_file_location(modname, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[modname] = mod
    sys.path.insert(0, str(OLD_DIR))
    try:
        spec.loader.exec_module(mod)
    finally:
        sys.path.remove(str(OLD_DIR))
    return mod


def load_new(script):
    sys.path.insert(0, str(ROOT / "uk" / "scripts"))
    try:
        spec = importlib.util.spec_from_file_location(
            "new_" + script[:-3], ROOT / "uk" / "scripts" / script)
        mod = importlib.util.module_from_spec(spec)
        sys.modules["new_" + script[:-3]] = mod
        spec.loader.exec_module(mod)
    finally:
        sys.path.remove(str(ROOT / "uk" / "scripts"))
    return mod


print(f"BRANCH 14 — CHECK SCOPING, BOTH DIRECTIONS")
print(f"baseline: {REF} = {SHA[:12]}")
print("=" * 96)

from lxml import etree  # noqa: E402

for _s in ("quality_check.py", "validate_segment_shapes.py",
           "translate_headers_footers.py"):
    assert_baseline_differs(_s)

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
# but Step 7 has swapped the two paragraphs. Positionally, entry 0's long source is
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
# a Step 7 permutation breaking a numbered block would look like.
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
ok("C9 --language IS passed, from the original",
   "--language" in got_args and "dutch" in got_args,
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
ok("C9 on detector disagreement, no --language is passed",
   "--language" not in got_args, f"(args tail: {got_args[-4:] if got_args else []})")

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
