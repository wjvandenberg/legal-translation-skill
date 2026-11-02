# -*- coding: utf-8 -*-
"""STEP 14, HEAVY: the PROPERTIES the fixes claim, over many generated inputs.

WHY THIS EXISTS SEPARATELY FROM tests/test_check_scoping.py. That file tests specific
CASES — this input must fire, that one must not — and cases only ever prove what the author
thought to write down. The fixes here claim something stronger and more useful:

    L1 / G11 / G5   the truncation verdict does not depend on WHERE a paragraph sits.
                    That is the whole content of L1's repair, and two hand-built documents
                    cannot establish it. Here it is asserted over hundreds of random
                    permutations of generated documents, INCLUDING documents with duplicate
                    paragraph text, which is the case the pairing has to refuse.
    G10             a rendered break between two runs suppresses the adjacency finding
                    wherever it sits, and a tab STOP never does.
    M1              the anomaly comparison is a MULTISET difference, over random multisets.
    F10             the alpha-collision verdict moves ONLY on a del<->ins pair, over
                    thousands of generated pairs -- and the old code fired on some.
    G1 / G7         the retention verdict moves ONLY where an elision, a marker or a title
                    sits, in every language, and a span in the low opening quote is read
                    exactly as its typographic twin.
    G2 / G8 / G14   'Article N' warns on every internal tail and on no legislation tail,
                    whatever sits between the number and the tail -- both ways moved.
    all             none of them crashes on malformed, empty, or extreme input, and all of
                    them are deterministic.

AND EVERY PROPERTY IS CHECKED AGAINST THE PRE-BRANCH CODE TOO. A property that already held
proves nothing about the fix, so the permutation-invariance property asserts that the OLD
code VIOLATES it. That is the same discipline as the case tests: a control that was already
green is not a control.

Deterministic: one fixed seed, so a failure is reproducible and reportable rather than a
story about a random run. All content invented — no client text.

    uv run --with lxml python tests/test_check_scoping_properties.py
"""
import importlib.util
import io
import os
import random
import re
import shutil
import subprocess
import sys
import tempfile
import time
import zipfile
from collections import Counter
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

# PINNED TO A COMMIT, NOT A BRANCH NAME — see the same note in test_check_scoping.py.
# `origin/main` stopped being the pre-branch code the moment the branch merged, which turned
# the "OLD code VIOLATES it" half of every property into a comparison of the fix with
# itself. 2178cce is the commit before step 14 and does not move.
REF = os.environ.get("LT_BASELINE_REF", "2178cce")
W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
SEED = 20260821
FAIL, CHECKED = [], 0


def ok(label, cond, detail=""):
    global CHECKED
    CHECKED += 1
    print(("  OK   " if cond else "  XX   ") + label
          + (f"   {detail}" if detail and not cond else ""))
    if not cond:
        FAIL.append(f"{label} {detail}".strip())


r = subprocess.run(["git", "rev-parse", "--verify", REF], capture_output=True,
                   text=True, cwd=ROOT)
if r.returncode != 0:
    print(f"VOID — baseline ref {REF} does not resolve. The 'old code violates it' half")
    print("of every property below could not be checked, so nothing here passed.")
    sys.exit(1)
SHA = r.stdout.strip()

TMP = Path(tempfile.mkdtemp(prefix="b14-props-"))
OLD = TMP / "old"
OLD.mkdir(parents=True)
shutil.copyfile(ROOT / "uk" / "scripts" / "source_language_markers.py",
                OLD / "source_language_markers.py")
blob = subprocess.run(["git", "show", f"{REF}:uk/scripts/quality_check.py"],
                      capture_output=True, cwd=ROOT)
if blob.returncode != 0:
    print(f"VOID — cannot read quality_check.py at {REF}")
    sys.exit(1)
# A comparison that established nothing has not passed: if the baseline copy IS the
# working-tree copy, the "OLD code violates it" half of every property below is a
# tautology and this suite must say so rather than go green.
if blob.stdout == (ROOT / "uk" / "scripts" / "quality_check.py").read_bytes():
    print(f"VOID — quality_check.py at {REF} is BYTE-IDENTICAL to the working tree, so")
    print("the 'old code violates it' half of every property would compare the fix with")
    print("itself. Point LT_BASELINE_REF at a commit that predates the change.")
    sys.exit(1)
(OLD / "quality_check.py").write_bytes(blob.stdout)


def load(path, name):
    d = str(Path(path).parent)
    sys.path.insert(0, d)
    try:
        spec = importlib.util.spec_from_file_location(name, path)
        m = importlib.util.module_from_spec(spec)
        sys.modules[name] = m
        spec.loader.exec_module(m)
    finally:
        sys.path.remove(d)
    return m


from lxml import etree  # noqa: E402

OLDQC = load(OLD / "quality_check.py", "p_old_qc")
QC = load(ROOT / "uk" / "scripts" / "quality_check.py", "p_new_qc")

print("STEP 14 — PROPERTY TESTS")
print(f"baseline: {REF} = {SHA[:12]}   seed: {SEED}")
print("=" * 96)

# ---------------------------------------------------------------------------- generators
WORDS = ("agreement schedule clause party supplier customer obligation payment notice "
         "term condition warranty indemnity liability covenant premises goods services "
         "delivery acceptance termination renewal").split()
SRC_WORDS = ("overeenkomst bijlage bepaling partij leverancier afnemer verplichting "
             "betaling kennisgeving termijn voorwaarde garantie vrijwaring "
             "aansprakelijkheid").split()
DANGLERS = ("of", "to", "the", "by", "for", "and", "under", "with")


def sentence(rng, words, n, end):
    return " ".join(rng.choice(words) for _ in range(n)) + end


def make_case(rng, n_paras, dup_rate=0.0, dangle_rate=0.0, trunc_rate=0.0):
    """A document plus a matching notes list, with controllable awkwardness."""
    entries, bodies = [], []
    for i in range(n_paras):
        src_end = " " + rng.choice(DANGLERS) if rng.random() < dangle_rate else "."
        src = sentence(rng, SRC_WORDS, rng.randint(6, 18), src_end)
        if rng.random() < trunc_rate:
            en = " ".join(rng.choice(WORDS) for _ in range(2))       # far too short
        else:
            en_end = " " + rng.choice(DANGLERS) if src_end != "." else "."
            en = sentence(rng, WORDS, rng.randint(6, 18), en_end)
        if bodies and rng.random() < dup_rate:
            en = bodies[rng.randrange(len(bodies))]                  # duplicate text
        entries.append({"idx": i, "text": src, "en": en, "style": "Normal"})
        bodies.append(en)
    return entries, bodies


def doc_from(bodies):
    body = "".join(
        '<w:p><w:r><w:t xml:space="preserve">'
        + b.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        + "</w:t></w:r></w:p>" for b in bodies)
    return etree.fromstring(
        ('<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/'
         '2006/main"><w:body>' + body + "</w:body></w:document>").encode("utf-8"))


# ============================================================================
print("\nPROPERTY 1 — the truncation verdict is INVARIANT under permutation")
print("-" * 96)
print("  This is L1's repair stated as a property. skill Step 7 permutes the document; the")
print("  finding set must not care. Checked over generated documents and, for each, many")
print("  random permutations of its paragraphs.")

rng = random.Random(SEED)
new_stable = old_stable = 0
new_checked = old_checked = 0
worst_new = None
for trial in range(40):
    n = rng.randint(4, 22)
    entries, bodies = make_case(rng, n, dup_rate=0.15, dangle_rate=0.35,
                                trunc_rate=0.2)
    base_new = sorted(QC.check_truncation(doc_from(bodies), False, entries))
    base_old = sorted(OLDQC.check_truncation(doc_from(bodies), False, entries))
    for _ in range(8):
        perm = bodies[:]
        rng.shuffle(perm)
        got_new = sorted(QC.check_truncation(doc_from(perm), False, entries))
        got_old = sorted(OLDQC.check_truncation(doc_from(perm), False, entries))
        new_checked += 1
        old_checked += 1
        if got_new == base_new:
            new_stable += 1
        elif worst_new is None:
            worst_new = (trial, len(base_new), len(got_new))
        if got_old == base_old:
            old_stable += 1

ok(f"NEW code: invariant on {new_stable} of {new_checked} permutations",
   new_stable == new_checked,
   f"first divergence at trial {worst_new}" if worst_new else "")
ok(f"OLD code VIOLATES it — invariant on only {old_stable} of {old_checked}, so the "
   f"property is meaningful", old_stable < old_checked,
   "the old code was already invariant, so this property tests nothing")

# ============================================================================
print("\nPROPERTY 2 — determinism and idempotence")
print("-" * 96)
rng = random.Random(SEED + 1)
det = 0
for _ in range(30):
    entries, bodies = make_case(rng, rng.randint(3, 20), dup_rate=0.2,
                               dangle_rate=0.4, trunc_rate=0.25)
    d = doc_from(bodies)
    a = QC.check_truncation(d, False, entries)
    b = QC.check_truncation(d, False, entries)
    c = QC.check_truncation(doc_from(bodies), False, entries)
    det += (a == b == c)
ok(f"same input, same verdict, 30 of 30 (including a re-parsed tree)", det == 30,
   f"only {det}")

# ============================================================================
print("\nPROPERTY 3 — nothing crashes on malformed, empty or extreme input")
print("-" * 96)
HOSTILE = [
    ("no source data at all", None),
    ("empty notes list", []),
    ("entry missing every key", [{}]),
    ("entry that is not a dict", ["nonsense", 42, None]),
    ("idx negative", [{"idx": -5, "text": "x" * 60, "en": "y"}]),
    ("idx beyond the document", [{"idx": 9999, "text": "x" * 60, "en": "y"}]),
    ("idx not an integer", [{"idx": "three", "text": "x" * 60, "en": "y"}]),
    ("en is None", [{"idx": 0, "text": "x" * 60, "en": None}]),
    ("en is a number", [{"idx": 0, "text": "x" * 60, "en": 12345}]),
    ("text is None", [{"idx": 0, "text": None, "en": "y"}]),
    ("whitespace-only text", [{"idx": 0, "text": "   \t \n ", "en": "y"}]),
    ("CJK source, no spaces", [{"idx": 0, "text": "契約書" * 40, "en": "The agreement of"}]),
    ("very long paragraph", [{"idx": 0, "text": "woord " * 4000,
                             "en": "word " * 4000}]),
    ("control characters", [{"idx": 0, "text": "a\x0b\x0c" * 30, "en": "b\x0b\x0c" * 30}]),
]
DOCS = {
    "empty body": doc_from([]),
    "one empty paragraph": etree.fromstring(
        ('<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/'
         '2006/main"><w:body><w:p/></w:body></w:document>').encode()),
    "self-closing and text mixed": etree.fromstring(
        ('<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/'
         '2006/main"><w:body><w:p/><w:p><w:r><w:t>The parties agree that payment '
         'falls due to</w:t></w:r></w:p><w:p/></w:body></w:document>').encode()),
    "normal": doc_from(["The Supplier shall deliver the goods to the premises of"]),
}
crashes = []
runs = 0
for dname, d in DOCS.items():
    for hname, notes in HOSTILE:
        runs += 1
        try:
            QC.check_truncation(d, False, notes)
            QC.check_spacing(d, False)
            QC.check_numbering(d, False)
            QC.check_numbering(d, False, d)
        except Exception as exc:
            crashes.append(f"{dname} + {hname}: {type(exc).__name__}: {exc}")
ok(f"{runs} hostile document/notes combinations, no exception", not crashes,
   f"{len(crashes)} crash(es): {crashes[:3]}")

# ============================================================================
print("\nPROPERTY 4 — G10: a rendered break suppresses wherever it sits; a tab STOP never")
print("-" * 96)
COLLIDE = ("the Supplier", "shall deliver")
BREAKS = ("<w:tab/>", "<w:br/>", "<w:cr/>")
rng = random.Random(SEED + 2)
suppressed = fired = 0
for brk in BREAKS:
    for placement in range(4):
        if placement == 0:      # break in its own run, between the two runs
            body = (f'<w:p><w:r><w:t xml:space="preserve">{COLLIDE[0]}</w:t></w:r>'
                    f'<w:r>{brk}</w:r>'
                    f'<w:r><w:t xml:space="preserve">{COLLIDE[1]}</w:t></w:r></w:p>')
        elif placement == 1:    # break inside the FIRST run, after its text
            body = (f'<w:p><w:r><w:t xml:space="preserve">{COLLIDE[0]}</w:t>{brk}</w:r>'
                    f'<w:r><w:t xml:space="preserve">{COLLIDE[1]}</w:t></w:r></w:p>')
        elif placement == 2:    # break inside the SECOND run, before its text
            body = (f'<w:p><w:r><w:t xml:space="preserve">{COLLIDE[0]}</w:t></w:r>'
                    f'<w:r>{brk}<w:t xml:space="preserve">{COLLIDE[1]}</w:t></w:r></w:p>')
        else:                   # both w:t in ONE run with the break between them
            body = (f'<w:p><w:r><w:t xml:space="preserve">{COLLIDE[0]}</w:t>{brk}'
                    f'<w:t xml:space="preserve">{COLLIDE[1]}</w:t></w:r></w:p>')
        n = len(QC.check_spacing(doc_from([]) if False else etree.fromstring(
            ('<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/'
             '2006/main"><w:body>' + body + '</w:body></w:document>').encode()), False))
        suppressed += (n == 0)
        if n:
            fired += 1
ok(f"a rendered break suppresses the finding in all {len(BREAKS) * 4} placements",
   fired == 0, f"{fired} placement(s) still fired")

# A tab STOP, at every count, must never suppress — and must not crash.
stop_fires = 0
for k in (1, 2, 5, 20):
    stops = "".join(f'<w:tab w:val="left" w:pos="{720 * (i + 1)}"/>' for i in range(k))
    body = (f'<w:p><w:pPr><w:tabs>{stops}</w:tabs></w:pPr>'
            f'<w:r><w:t xml:space="preserve">{COLLIDE[0]}</w:t></w:r>'
            f'<w:r><w:t xml:space="preserve">{COLLIDE[1]}</w:t></w:r></w:p>')
    d = etree.fromstring(
        ('<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/'
         '2006/main"><w:body>' + body + '</w:body></w:document>').encode())
    stop_fires += bool(QC.check_spacing(d, False))
ok("a declared tab STOP never suppresses a real finding, at 1/2/5/20 stops",
   stop_fires == 4, f"only {stop_fires} of 4 fired")

# ============================================================================
print("\nPROPERTY 5 — M1: the numbering comparison is a MULTISET difference")
print("-" * 96)


def numbered_doc(seq):
    body = "".join(
        f'<w:p><w:pPr><w:numPr><w:ilvl w:val="{lv}"/><w:numId w:val="{nid}"/>'
        f'</w:numPr></w:pPr><w:r><w:t>item</w:t></w:r></w:p>' for nid, lv in seq)
    return etree.fromstring(
        ('<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/'
         '2006/main"><w:body>' + body + "</w:body></w:document>").encode())


rng = random.Random(SEED + 3)
good = 0
trials = 60
for _ in range(trials):
    # A source sequence, then the SAME sequence with extra anomalies appended.
    src_seq, extra_seq = [], []
    for nid in range(1, rng.randint(2, 5)):
        src_seq.append((nid, 0))
        for _ in range(rng.randint(0, 3)):
            src_seq.append((nid, rng.choice([0, 2, 3])))       # may or may not jump
    delivered_seq = src_seq[:]
    n_extra = rng.randint(0, 3)
    for _ in range(n_extra):
        nid = rng.randint(90, 95)                              # ids not in the source
        extra_seq += [(nid, 0), (nid, 2)]                      # a guaranteed jump each
    delivered_seq += extra_seq
    src, delivered = numbered_doc(src_seq), numbered_doc(delivered_seq)
    base = len(QC.check_numbering(src, False))
    full = len(QC.check_numbering(delivered, False))
    diffed = len(QC.check_numbering(delivered, False, src))
    # Every anomaly the source already had must cancel; the appended ones must survive.
    if diffed == full - base == n_extra:
        good += 1
ok(f"multiset difference exact on {good} of {trials} random sequences", good == trials,
   f"only {good}")

# Identical bodies must always difference to zero.
rng = random.Random(SEED + 4)
zeroes = 0
for _ in range(30):
    seq = [(rng.randint(1, 6), rng.choice([0, 1, 2, 3])) for _ in range(rng.randint(2, 25))]
    d = numbered_doc(seq)
    zeroes += (len(QC.check_numbering(d, False, numbered_doc(seq))) == 0)
ok("a body compared against an identical body always reports zero, 30 of 30",
   zeroes == 30, f"only {zeroes}")

# ============================================================================
print("\nPROPERTY 6 — G5 and G11 exemptions never depend on paragraph position either")
print("-" * 96)
rng = random.Random(SEED + 5)
SIG = ["SIGNED for and on behalf of the Seller acting by",
       "EXECUTED as a deed by the Buyer in the presence of"]
inv = 0
trials = 30
for _ in range(trials):
    entries, bodies = make_case(rng, rng.randint(3, 12), dangle_rate=0.5)
    bodies = bodies + SIG
    entries = entries + [{"idx": len(entries) + i, "text": s, "en": s}
                         for i, s in enumerate(SIG)]
    base = sorted(QC.check_truncation(doc_from(bodies), False, entries))
    perm = bodies[:]
    rng.shuffle(perm)
    inv += (sorted(QC.check_truncation(doc_from(perm), False, entries)) == base)
ok(f"execution-block exemption invariant under permutation, {inv} of {trials}",
   inv == trials, f"only {inv}")

# The exemption must not leak into an ordinary dangling sentence, at any length.
leaks = 0
for n in (5, 10, 40, 120):
    text = " ".join(["payment"] * n) + " falls due to the premises of"
    if not QC.check_truncation(doc_from([text]), False, None):
        leaks += 1
ok("an ordinary sentence ending on 'of' still fires at 4 different lengths",
   leaks == 0, f"{leaks} length(s) wrongly silenced")

# ============================================================================
print("\nPROPERTY 7 — C9: detection never raises, whatever the container")
print("-" * 96)
RPK = load(ROOT / "uk" / "scripts" / "repack_docx.py", "p_new_rpk")
CW = TMP / "c9"
CW.mkdir()


def container(name, writer):
    p = CW / name
    writer(p)
    return p


cases = []
cases.append(("missing file", CW / "nope.docx"))
p = container("not-a-zip.docx", lambda q: q.write_bytes(b"this is not a zip at all"))
cases.append(("not a zip", p))
p = container("no-body.docx",
              lambda q: zipfile.ZipFile(q, "w").writestr("other.xml", "<x/>"))
cases.append(("zip without word/document.xml", p))
p = container("empty-body.docx", lambda q: zipfile.ZipFile(q, "w").writestr(
    "word/document.xml", ""))
cases.append(("empty document.xml", p))
p = container("binary-body.docx", lambda q: zipfile.ZipFile(q, "w").writestr(
    "word/document.xml", bytes(range(256)) * 40))
cases.append(("non-UTF8 bytes in the body", p))
p = container("tags-only.docx", lambda q: zipfile.ZipFile(q, "w").writestr(
    "word/document.xml", "<w:document><w:body>" + "<w:p/>" * 500 + "</w:body></w:document>"))
cases.append(("tags but no text", p))
p = container("huge.docx", lambda q: zipfile.ZipFile(q, "w").writestr(
    "word/document.xml",
    "<w:document><w:body><w:p><w:t>" + ("de overeenkomst tussen partijen " * 30000)
    + "</w:t></w:p></w:body></w:document>"))
cases.append(("very large body", p))

raised = []
for name, path in cases:
    try:
        got = RPK._detect_source_language(str(path))
        if got is not None and not isinstance(got, str):
            raised.append(f"{name}: returned {type(got).__name__}, not str/None")
    except Exception as exc:
        raised.append(f"{name}: {type(exc).__name__}: {exc}")
ok(f"{len(cases)} hostile containers: never raises, always str or None", not raised,
   f"{raised[:3]}")

# ============================================================================
print("\nPROPERTY 8 — F10: the alpha-collision verdict moves ONLY on a del<->ins pair")
print("-" * 96)
# 14.2's fix is a scoping: across a del<->ins pair the rule returns nothing, and everywhere
# else it must return EXACTLY what the old code returned -- a regular<->tracked-change
# boundary, an ins_then_del, two dels, two regulars. Two hand-built pairs cannot show the
# narrowing stopped there; thousands of generated ones can.
blob = subprocess.run(["git", "show", f"{REF}:uk/scripts/validate_segment_shapes.py"],
                      capture_output=True, cwd=ROOT)
if blob.returncode != 0 or blob.stdout == (ROOT / "uk" / "scripts"
                                           / "validate_segment_shapes.py").read_bytes():
    print(f"VOID — validate_segment_shapes.py at {REF} is unreadable or BYTE-IDENTICAL to the")
    print("working tree, so the 'old code fired' half of this property compares nothing.")
    sys.exit(1)
(OLD / "validate_segment_shapes.py").write_bytes(blob.stdout)
OLDVSS = load(OLD / "validate_segment_shapes.py", "p_old_vss")
VSS = load(ROOT / "uk" / "scripts" / "validate_segment_shapes.py", "p_new_vss")

TYPES = ("regular", "ins", "del", "ins_then_del")
FRAGS = WORDS + ["Agreement", "5", "B.V", "agreement-", "", "契約",
                 "договор"]


def frag(rng):
    w = rng.choice(FRAGS)
    if rng.random() < 0.25:
        w = " " + w
    if rng.random() < 0.25:
        w = w + " "
    return w


rng = random.Random(SEED + 8)
moved_elsewhere, del_ins_firing, fired_before, n_del_ins = [], 0, 0, 0
for _ in range(4000):
    left = {"type": rng.choice(TYPES), "en": frag(rng)}
    right = {"type": rng.choice(TYPES), "en": frag(rng)}
    if rng.random() < 0.3:                      # the byte-identical pair skill Step 4 mandates
        right["en"] = left["en"]
    o = OLDVSS._rule_alpha_collision_no_space(left, right)
    n = VSS._rule_alpha_collision_no_space(left, right)
    if {left["type"], right["type"]} == {"del", "ins"}:
        n_del_ins += 1
        fired_before += o is not None
        del_ins_firing += n is not None
    elif n != o:
        moved_elsewhere.append((left["type"], right["type"]))
ok(f"F10 every other pairing of types: verdict identical to {REF[:12]} (4000 pairs)",
   not moved_elsewhere, f"{len(moved_elsewhere)} moved, e.g. {moved_elsewhere[:3]}")
ok(f"F10 {n_del_ins} del<->ins pairs: silent now", del_ins_firing == 0,
   f"{del_ins_firing} still fire")
ok(f"F10 the old code fired on {fired_before} of them (the property is not vacuous)",
   fired_before > 0)

# THE VIEWS F10's JOIN SCAN READS ARE THE VIEWS validate_reject_all RECONSTRUCTS. The scan keeps
# its own reader, because it needs to know WHICH segments meet and _reconstruct returns only the
# joined text; two readers of one contract must be asserted to agree, or one drifts unseen.
VRA = load(ROOT / "uk" / "scripts" / "validate_reject_all.py", "p_new_vra")
disagree, n_lists = [], 0
for _ in range(2000):
    segs = []
    for _ in range(rng.randint(1, 7)):
        roll = rng.random()
        if roll < 0.05:
            segs.append(rng.choice((None, "loose text", 7)))            # malformed items
        elif roll < 0.1:
            segs.append({"type": rng.choice(TYPES), "en": None})
        else:
            segs.append({"type": rng.choice(TYPES + ("unknown",)), "en": frag(rng)})
    n_lists += 1
    for view, kept in VSS._VIEWS:
        mine = "".join(VSS._seg_text(segs[i]) for i in VSS._view_indices(segs, kept))
        theirs = VRA._reconstruct(segs, view.split("-")[0])
        if mine != theirs:
            disagree.append((view, [s.get("type") if isinstance(s, dict) else s for s in segs]))
ok(f"F10 the join scan's two views equal validate_reject_all's reconstruction ({n_lists} lists)",
   not disagree, f"{len(disagree)} disagree, e.g. {disagree[:2]}")

# ============================================================================
print("\nPROPERTY 9 — G1 and G7: the retention verdict moves ONLY where an elision, a marker or a title sits")
print("-" * 96)
# 14.3's fix re-reads the straight apostrophe and adds two exemptions. Away from those shapes
# the check must return EXACTLY what the old code returned -- a naming verb and a parenthesis
# with no article included; and where the English keeps FEWER quoted spans than the source the
# exemptions must not apply at all, so a term or a title dropped with its quotes is never
# silenced. Thousands of generated paragraphs, not a handful of hand-built ones. Invented words.
blob = subprocess.run(["git", "show", f"{REF}:uk/scripts/validate_translations.py"],
                      capture_output=True, cwd=ROOT)
if blob.returncode != 0 or blob.stdout == (ROOT / "uk" / "scripts"
                                           / "validate_translations.py").read_bytes():
    print(f"VOID — validate_translations.py at {REF} is unreadable or BYTE-IDENTICAL to the")
    print("working tree, so the 'old code fired' half of this property compares nothing.")
    sys.exit(1)
(OLD / "validate_translations.py").write_bytes(blob.stdout)
OLDVT = load(OLD / "validate_translations.py", "p_old_vt")
VT = load(ROOT / "uk" / "scripts" / "validate_translations.py", "p_new_vt")

QWORDS = ["contratto", "Cliente", "Centro", "Servizi", "Delta", "Nord", "delle", "Mense",
          "agreement", "Contractor", "Office", "Lift", "5", "2030"]
# The plural possessives: an English holding them must never seem to keep its quotes.
ENWORDS = ["the", "Seller", "shall", "deliver", "plant", "works", "Buyer", "terms", "Parties'", "Sellers'"]
ELISIONS = ["dell'Accordo", "l'impianto", "all'Acquirente", "nell'ambito"]
QUOTES = (("'", "'"), ("‘", "’"), ('"', '"'), ("“", "”"), ("«", "»"),
          # 14.5: the low opening quote, closed as Polish (”) or as German (“) closes it
          ("„", "”"), ("„", "“"))
# prefix, whether the shape is one 14.3 or 14.5 exempts, and what follows the closing quote
PREFIXES = (("", False, ""), ("(il ", True, ""), ("(di seguito, il ", True, ""), ("(the ", True, ""),
            ("recante ", True, ""), ("entitled ", True, ""), ("denominato ", False, ""), ("(see ", False, ""),
            # 14.5, every language: markers, a participle closing one, titles before and after
            ("(di seguito ", True, ""), ("(hereinafter ", True, ""), ("(each a ", True, ""),
            ("(ci-après dénommé le ", True, ""), ("(en adelante, el ", True, ""), ("(doravante designado ", True, ""),
            ("(nachfolgend ", True, " genannt"), ("(im Folgenden ", True, ""), ("(hierna te noemen: ", True, ""),
            ("(zwaną dalej ", True, ""), ("(dalej: ", True, ""), ("(a továbbiakban: ", True, ""),
            ("(jäljempänä ", True, ""), ("(heretter kalt ", True, ""),
            ("intitulée ", True, ""), ("titulado ", True, ""), ("intitulado ", True, ""), ("mit dem Titel ", True, ""),
            ("getiteld ", True, ""), ("pod tytułem ", True, ""), ("otsikolla ", True, ""), ("", True, " című"),
            # ... and what they must NOT exempt: naming words, cross-references, a bare bracket
            ("dénommé ", False, ""), ("denominado ", False, ""), ("namens ", False, ""), ("genaamd ", False, ""),
            ("zwany ", False, ""), ("", False, " nevű"), ("nimeltään ", False, ""), ("kalt ", False, ""),
            ("(telle que définie dans le ", False, ""), ("(según se define en el ", False, ""),
            ("(wie definiert in der ", False, ""), ("(zgodnie z definicją w ", False, ""), ("(", False, ""),
            ("(der Vertrag ", False, ""))


def low9_twin(s):
    """The same text with each low-opening-quote span in typographic quotes."""
    return re.sub("„([^„”“]+)[”“]", lambda m: "“" + m.group(1) + "”", s)


def gen_case(rng, elide):
    src, en, n_quoted_en, shaped = [], [], 0, False
    n_src = rng.randint(1, 3)
    for _ in range(n_src):
        o, c = rng.choice(QUOTES)
        pre, exempt, post = rng.choice(PREFIXES)
        words = [rng.choice(QWORDS) for _ in range(rng.randint(1, 7))]
        if elide and rng.random() < 0.3:
            words.insert(rng.randrange(len(words) + 1), rng.choice(ELISIONS))
        close = (post + ")" if pre.startswith("(") and rng.random() < 0.8
                 else " e altro)" if pre.startswith("(") else post)
        shaped |= exempt
        src += [rng.choice(QWORDS), pre + o + " ".join(words) + c + close]
        if elide and rng.random() < 0.4:
            src.append(rng.choice(ELISIONS))
        roll = rng.random()
        if roll < 0.3:                                   # kept verbatim, quotes and all
            en.append(o + " ".join(words) + c)
            n_quoted_en += 1
        elif roll < 0.65:                                # translated, inside quotes
            en.append('"' + " ".join(rng.choice(ENWORDS) for _ in words) + '"')
            n_quoted_en += 1
        else:                                            # dropped, quotes and all
            en.append(rng.choice(ENWORDS))
        en.append(rng.choice(ENWORDS))
    return " ".join(src), " ".join(en), n_quoted_en, n_src, shaped


rng = random.Random(SEED + 9)
moved_plain, moved_short, n_plain, n_short, silenced_g7, silenced_g1 = [], [], 0, 0, 0, 0
fired_plain = fired_short = 0     # an "identical" verdict proves nothing where both are silent
moved_twin, n_twin, fired_twin, unread_low9 = [], 0, 0, 0
for k in range(12000):
    elide = k % 3 == 0
    # The spans this case WROTE, counted by the generator: never by the code under test.
    src, en, n_quoted_en, n_spans, shaped = gen_case(rng, elide)
    has_elision = re.search(r"[^\W\d_]'[^\W\d_]", src) is not None
    # 14.5 reads the low opening quote, which the old code never did: those paragraphs are judged
    # against their typographic twin instead.
    low9 = "„" in src
    o = OLDVT._check_quoted_phrase_retention({"text": src, "en": en})
    n = VT._check_quoted_phrase_retention({"text": src, "en": en})
    if not has_elision and not shaped and not low9:
        n_plain += 1
        fired_plain += bool(o)
        if n != o:
            moved_plain.append((src, en))
    if not has_elision and n_quoted_en < n_spans and not low9:
        n_short += 1
        fired_short += bool(o)
        if n != o:
            moved_short.append((src, en))
    # A German closer (“) can open the typographic pair across the paragraph when another typographic span
    # follows, in the old code and the new alike, so the twin is compared wherever no typographic mark
    # stands outside the low-opening-quote spans -- German-closed ones included (the review, 2026-11-02).
    rest = re.sub("„[^„”“]+[”“]", "", src)
    if low9 and "“" not in rest and "”" not in rest:
        n_twin += 1
        t = VT._check_quoted_phrase_retention({"text": low9_twin(src), "en": low9_twin(en)})
        fired_twin += bool(t)
        # The findings come out style by style, so a twin moves a finding's PLACE in the list: compared as a
        # multiset, reordered is not changed.
        if Counter(n) != Counter(t):
            moved_twin.append((src, en))
        unread_low9 += bool(n) and not o and not shaped and not has_elision
    if o and not n:
        silenced_g1 += has_elision and not shaped
        silenced_g7 += shaped and not has_elision
ok(f"G1/G7 no elision, no marker, no title: verdict identical to {REF[:12]} ({n_plain} paragraphs, "
   f"{fired_plain} firing)", fired_plain > 0 and not moved_plain,
   f"{len(moved_plain)} moved, e.g. {moved_plain[:1]}")
ok(f"G1/G7 English keeping fewer quoted spans than the source: verdict identical ({n_short} "
   f"paragraphs, {fired_short} firing)", fired_short > 0 and not moved_short,
   f"{len(moved_short)} moved, e.g. {moved_short[:1]}")
ok(f"G1/G7 the old code fired where the new is silent: {silenced_g1} elision and {silenced_g7} "
   f"marker or title paragraphs (the property is not vacuous)", silenced_g1 > 0 and silenced_g7 > 0)
ok(f"G7 a span in the low opening quote is read exactly as its typographic twin ({n_twin} paragraphs, "
   f"{fired_twin} firing)", n_twin > 0 and fired_twin > 0 and not moved_twin,
   f"{len(moved_twin)} moved, e.g. {moved_twin[:1]}")
ok(f"G7 the old code never read the low opening quote: {unread_low9} plain paragraphs fire now and did not "
   f"before (the widening is real)", unread_low9 > 0)
# A hostile bracket -- a lead-in followed by thousands of follow-on words and no closing quote -- must not
# make the marker search crawl.
hostile = ("Le parti (di seguito " + "anche denominato " * 1500 + " , :" * 3000 + "x il "
           + '"Servizio di Pulizia degli Uffici Centrali" ' + "e " * 2000 + ").")
t0 = time.time()
VT._check_quoted_phrase_retention({"text": hostile, "en": "The parties."})
ok(f"G7 a hostile bracket of {len(hostile)} characters is judged in {time.time() - t0:.2f} s (under 2 s)",
   time.time() - t0 < 2.0)

# ============================================================================
print("\nPROPERTY 10 — G2, G8 and G14: 'Article N' warns on every internal tail and on no legislation tail")
print("-" * 96)
# 14.4's fix moves the warning both ways: quiet on a citation of legislation whatever sits between the number and
# the code (G2, G8), firing on an internal reference the bare 'of the' hid (G14). So over thousands of generated
# references -- a number, a GAP, a TAIL, each drawn and RECORDED by the generator, never read back from the code
# under test -- an internal tail always warns, a listed legislation tail never does, and every other tail keeps the
# old verdict exactly. Invented words.
blob = subprocess.run(["git", "show", f"{REF}:uk/scripts/lexicon_compliance.py"], capture_output=True, cwd=ROOT)
if blob.returncode != 0 or blob.stdout == (ROOT / "uk" / "scripts" / "lexicon_compliance.py").read_bytes():
    print(f"VOID — lexicon_compliance.py at {REF} is unreadable or BYTE-IDENTICAL to the")
    print("working tree, so the 'old code fired' half of this property compares nothing.")
    sys.exit(1)
(OLD / "lexicon_compliance.py").write_bytes(blob.stdout)
OLDLC = load(OLD / "lexicon_compliance.py", "p_old_lc")
LC = load(ROOT / "uk" / "scripts" / "lexicon_compliance.py", "p_new_lc")

# (text, kind): none -- straight to the tail; suffix -- a -bis; sub -- a paragraph or letter; list -- more articles
GAPS = (("", "none"), ("-bis", "suffix"), (" ter", "suffix"), (", paragraph 2,", "sub"), (", paragraph 2", "sub"),
        (", second paragraph,", "sub"), (", letter a),", "sub"), (", letters a) and b)", "sub"),
        (", paragraph 1, and Article 9, paragraph 2,", "list"), (" and Article 9", "list"), (" and 8", "list"),
        (", second paragraph, or Articles 8 and 9", "list"))
# (text, kind): leg -- a listed legislation tail; int -- an internal 'of the' tail; kept -- an alternative the old
# look-ahead named and the new keeps verbatim; other -- no legislation tail at all
TAILS = (("of the Civil Code", "leg"), ("of the Italian Civil Code", "leg"), ("of Legislative Decree No. 9", "leg"),
         ("of Presidential Decree No. 7", "leg"), ("of the Catering Decree", "leg"), ("of that Presidential Decree", "leg"),
         ("of the Authority Resolution", "leg"), ("of the Companies Act", "leg"), ("of the Treaty", "leg"),
         ("of the Data Regulation", "leg"), ("of the Services Directive", "leg"), ("of the Constitution", "leg"),
         ("of the said Decree", "leg"), ("of the Decree-Law", "leg"), ("of the Arbitration Rules", "leg"),
         ("of the Articles of Association", "leg"), ("of the GDPR", "leg"),
         ("of the Agreement", "int"), ("of the Deed", "int"), ("of the Cleaning Contract", "int"),
         ("of the Caterers' Agreement", "int"), ("of the Lease", "int"), ("of the Agreement and the Code", "int"),
         ("of the Agreement that Regulation 5 mentions", "int"), ("of the Agreement and Regulation 5", "int"),
         # The bare 'of the' had no word boundary, so it matched 'of these' and 'of their' as a prefix -- found by
         # this property on 2026-10-30, when 'of these Rules' sat in 'other' and the verdict moved.
         ("of these Rules", "int"), ("of their Agreement", "int"),
         ("of Book 6", "kept"), ("BW", "kept"), ("of Directive 2019/1", "kept"), ("of the EU", "kept"),
         ("of the European Union", "kept"), ("of Law No. 9", "kept"),
         ("above", "other"), ("below", "other"), ("hereof", "other"), ("of this Agreement", "other"),
         ("of Schedule 2", "other"), ("of Annex 1", "other"), ("of those parties", "other"), ("", "other"))
LEADS = ("", "Under ", "The Client relies on ", "Subject to ")
ENDS = (" applies.", ", and the Contractor pays.", "; the canteen stays open.", ".")


def art_fires(mod, text):
    _b, warns = mod.scan([("en", 0, text)], "*")
    return any("'Article N'" in w for w in warns)


rng = random.Random(SEED + 10)
moved_other, int_quiet, leg_firing = [], [], []
n = Counter()
for _ in range(6000):
    gap, gk = rng.choice(GAPS)
    tail, tk = rng.choice(TAILS)
    if gk == "suffix" and tk == "other" and not tail:
        continue                        # 'Article 5-bis.' -- no tail at all, the suffix alone; not a shape here
    text = rng.choice(LEADS) + f"Article {rng.randint(1, 2999)}" + gap + (" " + tail if tail else "") + rng.choice(ENDS)
    o, w = art_fires(OLDLC, text), art_fires(LC, text)
    if tk == "other" or (tk == "kept" and gk == "none"):
        n["same"] += 1
        n["same_fire"] += o
        if o != w:
            moved_other.append(text)
    elif tk == "int":
        n["int"] += 1
        n["int_old_quiet"] += not o
        if not w:
            int_quiet.append(text)
    elif tk == "leg" or tk == "kept":
        n["leg"] += 1
        n["leg_old_fire"] += o
        if w:
            leg_firing.append(text)
ok(f"G2/G8/G14 no legislation tail and no internal 'of the': verdict identical to {REF[:12]} ({n['same']} references, "
   f"{n['same_fire']} firing)", n["same_fire"] > 0 and n["same"] > n["same_fire"] and not moved_other,
   f"{len(moved_other)} moved, e.g. {moved_other[:2]}")
ok(f"G14 an internal tail the bare 'of the' could hide, after any gap: warns every time ({n['int']} references; "
   f"the old code was "
   f"silent on {n['int_old_quiet']})", n["int_old_quiet"] > 0 and not int_quiet,
   f"{len(int_quiet)} quiet, e.g. {int_quiet[:2]}")
ok(f"G2/G8 a listed legislation tail after any gap: never warns ({n['leg']} references; the old code fired on "
   f"{n['leg_old_fire']})", n["leg_old_fire"] > 0 and not leg_firing,
   f"{len(leg_firing)} warn, e.g. {leg_firing[:2]}")
# A long list must not cost the scan its time: each pattern part consumes text, so the work stays polynomial.
hostile = ("Article 1" + ", paragraph 1, and Article 2, letters a) and b)" * 400 + " of the Agreement.",
           "Article 1 and Articles " + ", ".join(str(i) for i in range(2, 3000)) + " of the Deed.",
           "Article 1" + ", second paragraph" * 2000 + " above.")
t0 = time.perf_counter()
fired = [art_fires(LC, h) for h in hostile]
took = time.perf_counter() - t0
ok(f"G2/G8/G14 three hostile lists scanned in {took:.2f}s, each still warning on its internal tail",
   took < 5 and all(fired), f"(fired {fired})")

# =============================================================================
print("\nPROPERTY 11 — G3 and G13: `; and/or` ends a list item; a name the lexicon keeps is no remnant")
print("-" * 96)
# Against main as 14.6 found it -- 13f52a7, pinned, the commit before that sub-step -- because quality_check
# moved between 2178cce and there for reasons that are not 14.6's. Each population is chosen by the generator's
# own record: the ending it wrote, the kept names and the marker words it planted -- never by the code under
# test. Invented words.
PRE = "13f52a7"
blob = subprocess.run(["git", "show", f"{PRE}:uk/scripts/quality_check.py"], capture_output=True, cwd=ROOT)
if blob.returncode != 0 or blob.stdout == (ROOT / "uk" / "scripts" / "quality_check.py").read_bytes():
    print(f"VOID — quality_check.py at {PRE} is unreadable or BYTE-IDENTICAL to the working")
    print("tree, so this property would compare the fix with itself.")
    sys.exit(1)
(OLD / "pre146_quality_check.py").write_bytes(blob.stdout)
PREQC = load(OLD / "pre146_quality_check.py", "p_pre146_qc")
SLM = load(ROOT / "uk" / "scripts" / "source_language_markers.py", "p_slm")

# (ending, kind): list -- a `;` or `,` then `and/or`; bare -- `and/or` with neither; other -- anything else
ENDINGS = (("; and/or", "list"), (", and/or", "list"), ("; and / or", "list"), (";and/or", "list"),
           (",  and/or ", "list"), (" and/or", "bare"), (" and / or", "bare"), ("; and/or the", "other"),
           ("; and", "other"), (", or", "other"), (" at the", "other"), (" of", "other"), (".", "other"),
           ("; and/", "other"), (" and/or.", "other"), ("", "other"))
rng = random.Random(SEED + 11)
n = Counter()
listed, bare_quiet, moved3 = [], [], []
for _ in range(3000):
    end, kind = rng.choice(ENDINGS)
    text = "the " + " ".join(rng.choice(WORDS) for _ in range(rng.randint(4, 12))) + end
    o = [i for i in PREQC.check_truncation(doc_from([text]), False, None) if i.startswith("Dangling ending")]
    w = [i for i in QC.check_truncation(doc_from([text]), False, None) if i.startswith("Dangling ending")]
    n[kind] += 1
    if kind == "list":
        n["list_pre"] += bool(o)
        if w:
            listed.append(text)
    elif kind == "bare":
        if not w:
            bare_quiet.append(text)
    else:
        n["other_fire"] += bool(o)
        if o != w:
            moved3.append(text)
ok(f"G3 a list-connective `and/or` ending never flags ({n['list']} paragraphs; {PRE} flagged {n['list_pre']})",
   n["list_pre"] > 0 and not listed, f"{len(listed)} flag, e.g. {listed[:2]}")
ok(f"G3 a bare `and/or` ending always flags ({n['bare']} paragraphs)", n["bare"] > 0 and not bare_quiet,
   f"{len(bare_quiet)} quiet, e.g. {bare_quiet[:2]}")
ok(f"G3 every other ending: verdict identical to {PRE} ({n['other']} paragraphs, {n['other_fire']} firing)",
   n["other_fire"] > 0 and n["other"] > n["other_fire"] and not moved3, f"{len(moved3)} moved, e.g. {moved3[:2]}")

# the ten names LEXICON_KEPT_NAMES declares, typed with their lexicon's language; marker words that are one hit each
KEPT_GEN = (("Agenzia delle Entrate", "italian"), ("Società Italiana degli Autori ed Editori", "italian"),
            ("Mercato Elettronico della Pubblica Amministrazione", "italian"),
            ("Codice della Crisi d'Impresa e dell'Insolvenza", "italian"),
            ("Codice delle Assicurazioni Private", "italian"), ("dupla conforme", "portuguese"),
            ("Loi du 25 juin 2008", "french"), ("Loi du 6 juillet 1989", "french"),
            ("Loi du 23 décembre 1986", "french"), ("Loi du 10 juillet 1965", "french"))
OUTSIDE = {"italian": ("della", "nonché", "qualora", "pertanto"), "french": ("toutefois", "néanmoins", "ledit"),
           "portuguese": ("outrossim", "mediante")}
alone = {k: len(SLM.scan_remnants(f"the {k} the", lang, bare_months=False)) for k, lang in KEPT_GEN}
ok("PROPERTY 11's generator: every kept name is at least one hit alone, every planted marker word exactly one",
   all(alone.values()) and all(len(SLM.scan_remnants(f"the {m} the", lang, bare_months=False)) == 1
                               for lang, ms in OUTSIDE.items() for m in ms), f"({alone})")
ok("PROPERTY 11's generator covers exactly the names LEXICON_KEPT_NAMES declares",
   [k for k, _l in KEPT_GEN] == list(SLM.LEXICON_KEPT_NAMES))
USQC = load(ROOT / "us" / "scripts" / "quality_check.py", "p_us_qc")


def del_doc(text):
    return etree.fromstring(
        (f'<w:document xmlns:w="{W}"><w:body><w:p><w:del w:id="1" w:author="A"><w:r><w:delText xml:space="preserve">'
         + text + "</w:delText></w:r></w:del></w:p></w:body></w:document>").encode("utf-8"))


moved13, wrong, gen_off, wrong_del, us_apart = [], [], [], [], []
for _ in range(3000):
    lang = rng.choice(("italian", "french", "portuguese"))
    words = [rng.choice(WORDS) for _ in range(rng.randint(3, 14))]
    kept = [rng.choice([k for k, kl in KEPT_GEN if kl == lang]) for _ in range(rng.choice((0, 0, 1, 1, 2, 3)))]
    marks = [rng.choice(OUTSIDE[lang]) for _ in range(rng.choice((0, 1, 2, 3)))]
    for tok in kept + marks:
        words.insert(rng.randint(0, len(words)), tok)
    text = "The " + " ".join(words) + "."
    o = PREQC.check_source_remnants(doc_from([text]), False, lang)
    w = QC.check_source_remnants(doc_from([text]), False, lang)
    o_hits = [i for i in o if not i.startswith("FULL")]
    w_hits = [i for i in w if not i.startswith("FULL")]
    if len(o_hits) != len(marks) + sum(alone[k] for k in kept):
        gen_off.append(text)
    # the same paragraph struck through: the deletion view reads the one list; and the us tree agrees
    wd = QC.check_source_remnants(del_doc(text), False, lang)
    if (sum(1 for i in wd if not i.startswith("FULL")) != len(marks)
            or any(i.startswith("FULL") for i in wd) != (len(marks) >= 3)):
        wrong_del.append(text)
    if USQC.check_source_remnants(doc_from([text]), False, lang) != w:
        us_apart.append(text)
    if not kept:
        n["none"] += 1
        n["none_fire"] += bool(o)
        if o != w:
            moved13.append(text)
    else:
        n["kept"] += 1
        n["kept_pre_fire"] += bool(o)
        n["kept_full_pre"] += any(i.startswith("FULL") for i in o)
        if (len(w_hits) != len(marks) or Counter(w_hits) - Counter(o_hits)
                or any(i.startswith("FULL") for i in w) != (len(marks) >= 3)):
            wrong.append(text)
ok(f"PROPERTY 11's generator record matches {PRE}'s count on every paragraph ({n['none'] + n['kept']} paragraphs)",
   not gen_off, f"{len(gen_off)} off, e.g. {gen_off[:2]}")
ok(f"G13 no kept name: findings identical to {PRE}, in their order ({n['none']} paragraphs, {n['none_fire']} firing)",
   n["none_fire"] > 0 and n["none"] > n["none_fire"] and not moved13, f"{len(moved13)} moved, e.g. {moved13[:2]}")
ok(f"G13 each planted kept name removes exactly the hits it carries alone, the rest kept as a multiset, the FULL "
   f"finding on the rest alone ({n['kept']} paragraphs; {PRE} fired on {n['kept_pre_fire']}, FULL on "
   f"{n['kept_full_pre']})", n["kept_pre_fire"] > 0 and n["kept_full_pre"] > 0 and not wrong,
   f"{len(wrong)} wrong, e.g. {wrong[:2]}")
ok(f"G13 the same paragraphs in a deletion: only the planted marker words count, the FULL finding on them alone "
   f"({n['none'] + n['kept']} paragraphs)", not wrong_del, f"{len(wrong_del)} wrong, e.g. {wrong_del[:2]}")
ok(f"G13 the us tree's findings identical to the uk tree's on every paragraph ({n['none'] + n['kept']})",
   not us_apart, f"{len(us_apart)} apart, e.g. {us_apart[:2]}")

# =============================================================================
print("\nPROPERTY 12 — G4: a dot inside a dotted form is no missing space; every run-in still is")
print("-" * 96)
# The rule did not move between 2178cce and the commit before 14.7, so the pinned REF is its true "before". Each
# population is chosen by the generator's own record: the dotted forms it wrote and the dots inside them, the run-ins
# it wrote -- never by the code under test. Each sentence is split at a random point across a tracked change, so the
# accept-all and reject-all views both read it across a segment join; both trees. Invented words.
blob = subprocess.run(["git", "show", f"{REF}:uk/scripts/validate_reject_all.py"], capture_output=True, cwd=ROOT)
if blob.returncode != 0 or blob.stdout == (ROOT / "uk" / "scripts" / "validate_reject_all.py").read_bytes():
    print(f"VOID — validate_reject_all.py at {REF} is unreadable or BYTE-IDENTICAL to the working")
    print("tree, so this property would compare the fix with itself.")
    sys.exit(1)
(OLD / "validate_reject_all.py").write_bytes(blob.stdout)
OLDVRA = load(OLD / "validate_reject_all.py", "p_old_vra")
USVRA = load(ROOT / "us" / "scripts" / "validate_reject_all.py", "p_us_vra")
LETTERS = "ABCDEGKLMNPRSTVabcdeglmnprstv"
RUNIN_WORDS = ["Buyer", "tenant", "office", "invoice", "Seller", "3", "2026", "(a)"]


def ms(mod, text):
    return sum(1 for nm, _s in mod._scan_view(text, []) if nm == "missing_space_between_words")


rng = random.Random(SEED + 12)
n = Counter()
moved4, wrong4, off4, view4, us4 = [], [], [], [], []
for _ in range(3000):
    toks, inside, runins = [], 0, 0
    for _w in range(rng.randint(4, 12)):
        r = rng.random()
        if r < 0.2:                                  # a dotted form, 2 to 4 lone letters, each with its dot
            k = rng.randint(2, 4)
            form = "".join(rng.choice(LETTERS) + "." for _ in range(k))
            inside += k - 1
            if rng.random() < 0.3:                   # run straight into a word: its last dot is a real missing space
                form += rng.choice(WORDS)
                runins += 1
            toks.append(form)
        elif r < 0.35:                               # a run-in: a word, a punctuation mark, a word, no space
            toks.append(rng.choice(RUNIN_WORDS) + rng.choice(".,;:") + rng.choice(WORDS))
            runins += 1
        elif r < 0.4:                                # an initial before a surname: a run-in too
            toks.append(rng.choice("JKMR") + "." + rng.choice(("Smith", "Brown", "Rossi")))
            runins += 1
        else:
            toks.append(rng.choice(WORDS))
    text = "The " + " ".join(toks) + " ends here."
    o, w = ms(OLDVRA, text), ms(VRA, text)
    if o != inside + runins:
        off4.append(text)
    if not inside:
        n["plain"] += 1
        n["plain_fire"] += bool(o)
        if o != w:
            moved4.append(text)
    else:
        n["dotted"] += 1
        n["dotted_old"] += o
        if w != runins:
            wrong4.append(text)
    cut = rng.randint(0, len(text))
    acc = [{"type": "regular", "en": text[:cut]}, {"type": "ins", "en": text[cut:]}, {"type": "del", "en": " old."}]
    rej = [{"type": "regular", "en": text[:cut]}, {"type": "del", "en": text[cut:]}, {"type": "ins", "en": " new."}]
    if ms(VRA, VRA._reconstruct(acc, "accept")) != runins or ms(VRA, VRA._reconstruct(rej, "reject")) != runins:
        view4.append(text)
    if ms(USVRA, text) != w:
        us4.append(text)
ok(f"PROPERTY 12's generator record matches {REF[:12]}'s count on every sentence ({n['plain'] + n['dotted']})",
   not off4, f"{len(off4)} off, e.g. {off4[:2]}")
ok(f"G4 no dotted form: findings identical to {REF[:12]} ({n['plain']} sentences, {n['plain_fire']} firing)",
   n["plain_fire"] > 0 and n["plain"] > n["plain_fire"] and not moved4,
   f"{len(moved4)} moved, e.g. {moved4[:2]}")
ok(f"G4 every dot inside a dotted form quiet and every run-in firing ({n['dotted']} sentences; {REF[:12]} found "
   f"{n['dotted_old']})", n["dotted_old"] > 0 and not wrong4, f"{len(wrong4)} wrong, e.g. {wrong4[:2]}")
ok(f"G4 both views, each read across a segment join, find exactly the run-ins ({n['plain'] + n['dotted']})",
   not view4, f"{len(view4)} wrong, e.g. {view4[:2]}")
ok(f"G4 the us tree identical to the uk tree on every sentence", not us4, f"{len(us4)} apart, e.g. {us4[:2]}")

# =============================================================================
print("\nPROPERTY 13 — C10: a part with no copy is required exactly when it carries text")
print("-" * 96)
# check_step_8 did not move between 2178cce and the commit before 14.8. Generated header, footer and footnotes parts,
# built from pieces the generator records -- empty paragraphs, spaces, separators, a field's instruction, a tab, and
# now and then a visible text in a run, a deletion, a text box or a table cell -- each with no copy in final/word.
# Required (FAIL) exactly when the generator wrote a visible text; the old code FAILED on every one; both trees.
import zipfile as _zf  # noqa: E402
blob = subprocess.run(["git", "show", f"{REF}:uk/scripts/verify_diligence.py"], capture_output=True, cwd=ROOT)
if blob.returncode != 0 or blob.stdout == (ROOT / "uk" / "scripts" / "verify_diligence.py").read_bytes():
    print(f"VOID — verify_diligence.py at {REF} is unreadable or BYTE-IDENTICAL to the working tree.")
    sys.exit(1)
(OLD / "verify_diligence.py").write_bytes(blob.stdout)
OLDVD = load(OLD / "verify_diligence.py", "p_old_vd")
VD = load(ROOT / "uk" / "scripts" / "verify_diligence.py", "p_new_vd")
USVD = load(ROOT / "us" / "scripts" / "verify_diligence.py", "p_us_vd")
NSW = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'
QUIET = ("<w:p/>", "<w:p><w:r><w:t> </w:t></w:r></w:p>", "<w:p><w:r><w:separator/></w:r></w:p>",
         "<w:p><w:r><w:instrText> PAGE </w:instrText></w:r></w:p>", "<w:p><w:r><w:tab/></w:r></w:p>",
         '<w:p><w:r><w:t xml:space="preserve">   </w:t></w:r></w:p>')
VISIBLE = ("<w:p><w:r><w:t>Room {}</w:t></w:r></w:p>",
           '<w:p><w:del w:id="1" w:author="A"><w:r><w:delText>Draft {}</w:delText></w:r></w:del></w:p>',
           "<w:p><w:r><w:txbxContent><w:p><w:r><w:t>Desk {}</w:t></w:r></w:p></w:txbxContent></w:r></w:p>",
           "<w:tbl><w:tr><w:tc><w:p><w:r><w:t>Floor {}</w:t></w:r></w:p></w:tc></w:tr></w:tbl>")
PARTS = (("word/header1.xml", "w:hdr"), ("word/footer2.xml", "w:ftr"), ("word/footnotes.xml", "w:footnotes"))
rng = random.Random(SEED + 13)
n = Counter()
wrong13, old13, us13 = [], [], []
for i in range(400):
    part, root = rng.choice(PARTS)
    body = [rng.choice(QUIET) for _ in range(rng.randint(1, 5))]
    visible = rng.random() < 0.5
    if visible:
        body.insert(rng.randint(0, len(body)), rng.choice(VISIBLE).format(rng.randint(1, 99)))
    xml = f"<{root} {NSW}>" + "".join(body) + f"</{root}>"
    d = TMP / f"c10p{i}"
    (d / "final" / "word").mkdir(parents=True)
    (d / "final" / "word" / "document.xml").write_text(f"<w:document {NSW}><w:body/></w:document>", encoding="utf-8")
    with _zf.ZipFile(d / "o.docx", "w") as z:
        z.writestr("word/document.xml", f"<w:document {NSW}><w:body/></w:document>")
        z.writestr(part, xml)

    def verdict(mod):
        rep = mod.Report()
        mod.check_step_8(rep, str(d), str(d / "o.docx"))
        return [s for _a, s, _b, _c in rep.findings]

    v, o = verdict(VD), verdict(OLDVD)
    n["visible" if visible else "empty"] += 1
    if v != (["FAIL"] if visible else ["PASS"]):
        wrong13.append(xml)
    if o != ["FAIL"]:
        old13.append(xml)
    if verdict(USVD) != v:
        us13.append(xml)
ok(f"C10 a part with no copy FAILS exactly when the generator wrote a visible text ({n['visible']} with, "
   f"{n['empty']} without)", n["visible"] > 0 and n["empty"] > 0 and not wrong13,
   f"{len(wrong13)} wrong, e.g. {wrong13[:2]}")
ok(f"C10 the old code FAILED on every one of the {n['visible'] + n['empty']}", not old13, f"{len(old13)} passed")
ok("C10 the us tree identical to the uk tree on every part", not us13, f"{len(us13)} apart")

shutil.rmtree(TMP, ignore_errors=True)
print()
print("=" * 96)
if FAIL:
    print(f"FAIL — {len(FAIL)} of {CHECKED} properties:")
    for f in FAIL:
        print(f"  · {f}")
    print("=" * 96)
    sys.exit(1)
print(f"PASS — {CHECKED} properties, seed {SEED}. The truncation verdict is invariant under")
print(f"permutation where the pre-branch code at {REF[:16]} is not; the checks are")
print("deterministic; and nothing crashes on any of the hostile inputs above.")
print("=" * 96)
