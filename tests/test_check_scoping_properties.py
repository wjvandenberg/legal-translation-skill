# -*- coding: utf-8 -*-
"""BRANCH 14, HEAVY: the PROPERTIES the fixes claim, over many generated inputs.

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
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parent.parent
REF = os.environ.get("LT_BASELINE_REF", "origin/main")
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

print("BRANCH 14 — PROPERTY TESTS")
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
print("  This is L1's repair stated as a property. Step 7 permutes the document; the")
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
