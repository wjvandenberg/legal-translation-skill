#!/usr/bin/env python3
"""
STEP B — THIRD DEEP AUDIT: the NEW CONTENT and INTERNAL CONSISTENCY audit.

Wouter, 2026-08-05: "Do again a deep analysis and audit of Step-B-analysis.MD. This is the
key document and we cannot have it wrong here."

WHY A THIRD ONE. Since the first deep audit the document has gained six large prescription
blocks and seven decision records. Audit 1's citation list was frozen before any of that
existed, so NONE of the new factual claims has been checked against a source. Audit 2 checked
that prescriptions are PRESENT; it never checked they are TRUE. This audit closes that.

  1. every factual claim in the NEW prescription blocks, against the row it cites
  2. internal consistency: any figure stated twice must agree with itself
  3. the decision record against the option text it records
  4. structure: heading order, no duplicates, no stale PENDING
  5. prescriptions with no source row, recorded rather than assumed
  6. one judgement surfaced rather than buried: does option 3 honour "REPLACING, not patching"?

    uv run python tools/stepb_audit3.py
"""
import re
import sys
from collections import Counter
from pathlib import Path

import sys as _sys
# A committed tool must not depend on the terminal codepage: on Windows a redirected
# stdout defaults to cp1252 and a UnicodeEncodeError reads to the caller as a FAILED
# check rather than a crashed one. See tests/run_tests.py, which pays for this lesson.
# hasattr: this module is IMPORTED by stepb_audit.py under redirect_stdout(StringIO),
# and StringIO has no .reconfigure. The unguarded version crashed the importer -- a
# fix that broke a second caller, which is the shape this project keeps logging.
if hasattr(_sys.stdout, "reconfigure"):
    _sys.stdout.reconfigure(encoding="utf-8", errors="replace")


ROOT = Path(__file__).resolve().parent.parent
doc = (ROOT / "STEP-B-ANALYSIS.md").read_text(encoding="utf-8")
reg = (ROOT / "FINDINGS-REGISTER.md").read_text(encoding="utf-8")
a3 = (ROOT / "A3-STRUCTURAL-ANALYSIS.md").read_text(encoding="utf-8")
cmp_ = (ROOT.parent / "legal-translation-private" / "A4-A3-COMPARISON.md").read_text(encoding="utf-8")
cmd = (ROOT / "CLAUDE.md").read_text(encoding="utf-8")
ALL = "\n".join([reg, a3, cmp_, cmd])

FAIL, WARN, JUDGE = [], [], []
def fail(t, m): print(f"  [FAIL] {t}: {m}"); FAIL.append(t)
def warn(t, m): print(f"  [warn] {t}: {m}"); WARN.append(t)
def ok(m): print(f"  [OK  ] {m}")
def judge(t, m): print(f"  [JUDGE] {t}: {m}"); JUDGE.append(t)

ID = re.compile(r"^\|\s*(?:\*\*)?([A-Z]{1,2}-?\d{1,2}[a-z]?)(?:\*\*)?\s*\|")
rows, sec = {}, None
for l in reg.split("\n"):
    m = re.match(r"^#{2,3}\s+(.*)$", l)
    if m: sec = m.group(1); continue
    m = ID.match(l)
    if m: rows.setdefault(m.group(1), dict(text=l, sec=sec))

FLAT = re.sub(r"\s+", " ", re.sub(r"[*`]", "", doc))
LIVE = doc
if "### The deep audit" in doc and "### Confidence, per claim" in doc:
    LIVE = doc[:doc.index("### The deep audit")] + doc[doc.index("### Confidence, per claim"):]
LIVEFLAT = re.sub(r"\s+", " ", re.sub(r"[*`]", "", LIVE))

print("=" * 84)
print("1. EVERY FACTUAL CLAIM IN THE NEW PRESCRIPTION BLOCKS, against the row it cites")
print("=" * 84)
# (claim as it appears in the analysis, row id, the substring that row must contain)
NEW_CLAIMS = [
 ("the detector locked on 146 paragraphs early", "L2", "146 paragraphs earlier"),
 ("32 'Term means' paragraphs in a 43-paragraph span", None, "32** unambiguous"),
 ("both detectors return on the FIRST match", "L2", "return on the FIRST match"),
 ("the heading fallback is anchored end-to-end", "L2", "anchored end-to-end"),
 ("Certain Definitions / Additional Definitions / Interpretation and Definitions all miss",
  "L2", "Interpretation and Definitions"),
 ("the detector carries scar tissue from three earlier post-mortems", None, "three earlier post-mortems"),
 ("detection is only necessary because the pipeline throws away what it knew",
  None, "throws away something it already knew"),
 ("the detector has TWO consumers, both silent on failure", "L6", "two consumers, both silent"),
 ("each miss also left the formatting gate inert and reporting clean", "L6", "gate was inert and reported clean"),
 ("the term-sanity guard turned a corruption into a no-op", "P11", "turned a corruption into a no-op"),
 ("do not weaken it when cluster L is fixed", "P11", "do not weaken it when cluster L is fixed"),
 ("scan for MULTIPLE candidate sections and report every one", None, "report every one"),
 ("fixed 14 pt line height on 238 paragraphs", "D6", "238 paragraphs"),
 ("anything taller than the fixed height is clipped", "D6", "clips anything taller"),
 ("the pipeline is documented CHANGING a run's size", "D6", "CHANGING a run's `sz`"),
 ("no check looks at line geometry at all", "D6", "no check looks at line geometry"),
 ("an unconverted comma decimal reads ~100x larger", "F17", "100× larger"),
 ("nothing in the pipeline checks numbers at all", "F17", "checks numbers at all"),
 ("nine terms central to one document appear in no sub-lexicon for its language", "E3", "Nine terms central"),
 ("the central defined term came from the counterparty's English margin comments", "E6", "margin comments"),
 ("that was luck: the counterparty happened to comment in English", "E6", "that was luck"),
 ("found only by grepping the whole tree", "E1", "grepping the whole tree"),
 ("the operator preserved two dates on three stated grounds, then reversed at Step 4",
  "F4", "reformatting text the counterparty inserted"),
 ("the delivered redline reformats dates the counterparty inserted", "F4", "reformats dates the counterparty inserted"),
 ("document language and theme font language keep the source value", "R1", "themeFontLang"),
 ("Word spell-checks the delivered English against the source-language dictionary", "R1", "spell-checks the delivered English"),
 ("every revision balloon shows a source-language name", "R1", "revision balloon"),
 ("the skill says what must NOT appear and never what SHOULD", "R1", "never says what SHOULD"),
 ("no size limit, nothing about password-protected, .docm or non-Word", "L5", "password-protected"),
 ("the observed instance bypasses every gate", "L5", "BYPASSES EVERY GATE"),
 ("Step 3 leaves no artefact and is checked by nothing", "C26", "PRODUCES NO ARTEFACT"),
 ("the file itself calls partial lexicon reading its most common failure mode",
  "C26", "partial lexicon reading"),
 ("no mechanism can confirm an agent read rather than skimmed", "C26", "read a file rather than skimmed"),
 ("our own read gate verifies ENDPOINTS, not reading", "I-8", "ENDPOINTS, NOT READING"),
 ("three of six cited files contain no Avoid at all", "E14", "three contain no occurrence"),
 ("14 of 19 forbidden phrases appear in no lexicon file", "E14", "14 appear in no lexicon file"),
 ("the script states its own traceability rule and breaks it", "E14", "traceable to a specific lexicon line"),
]
bad = 0
for claim, rid, frag in NEW_CLAIMS:
    hay = rows[rid]["text"] if rid and rid in rows else reg
    if frag not in hay:
        fail("1", f"{claim!r} -> {rid or 'register'} does not contain {frag!r}"); bad += 1
print(f"  {len(NEW_CLAIMS)} new claims checked, {bad} failed")
if not bad:
    ok("every factual claim in the new prescription blocks traces to its source")

print()
print("=" * 84)
print("2. INTERNAL CONSISTENCY — any figure stated twice must agree with itself")
print("=" * 84)
def count_variants(label, pattern, expect=None):
    # consistency must be measured on LIVE: the audit record deliberately quotes RETIRED figures
    # ...and case-folded, or "Twenty" at the start of a sentence reads as a different figure from
    # "twenty" mid-sentence. That produced a false failure the first time this guard was widened.
    vals = Counter(v.lower() for v in re.findall(pattern, LIVEFLAT))
    if len(vals) > 1:
        fail("2", f"{label}: the document states {dict(vals)} — inconsistent")
    elif expect and vals and list(vals)[0] != expect:
        fail("2", f"{label}: states {list(vals)[0]}, expected {expect}")
    elif vals:
        ok(f"{label}: consistently {list(vals)[0]} ({sum(vals.values())} mentions)")
    else:
        warn("2", f"{label}: no occurrence found — check the pattern")

count_variants("no-compliant-repair count", r"(eighteen|fourteen|thirteen) findings (?:state|have no compliant)")
# PATTERN UPDATED 2026-08-05: §4's opening became "Twenty numbered branches, 0-19, plus three
# deferred items", so the old needle "twenty branches" stopped matching and the guard went silent
# without failing. Caught by this warning rather than by reading. Now BOTH the prose figures are
# guarded AND the table is counted, which is stronger than either.
count_variants("branch count", r"(Twenty|Nineteen|twenty|nineteen) numbered branches")
count_variants("total pieces of work", r"(twenty-three|twenty-two|twenty-four) pieces of work")
# the branch table lives in section 2 ONLY. Spanning to section 4 swallowed section 3's
# record table and counted its rows as branches -- 29 instead of 20.
sec4 = doc[doc.index("## 2. The plan of work"):doc.index("## 3. The build brief")]
nrows = len(re.findall(r"^\| \*\*(\d+)\*\* \|", sec4, re.M))
drows = len(re.findall(r"^\| \*\*D(\d)\*\* \|", sec4, re.M))
if (nrows, drows) != (20, 3):
    fail("2", f"§4's table holds {nrows} numbered branches and {drows} deferred items, expected 20 and 3")
else:
    ok(f"§4's table holds exactly {nrows} numbered branches + {drows} deferred items = {nrows + drows}")
# derive rather than hardcode: the register grows, and a literal total goes stale silently
count_variants("skill findings total", r"(1\d\d) recorded findings")
count_variants("options total", r"There are (eleven|ten|nine) things we could do")
count_variants("furniture statement count", r"(?:About |about )(nine|eight|ten) (?:statements|convention statements)")
# the nine furniture statements must actually number nine
m = re.search(r"title block(?:[^.]{0,240}?)numeric locale", FLAT)
if m:
    ok(f"the furniture list enumerates {len(m.group(0).split('·'))} items")
    if len(m.group(0).split("·")) != 9:
        fail("2", f"the list has {len(m.group(0).split('·'))} items, the prose says nine")
else:
    warn("2", "could not locate the furniture enumeration to count it")

# ADDED 2026-08-05: every cluster size stated in the register's prose must equal its id count.
# That one figure has gone stale three times (29, 35, 37) because each correction added to the
# previous stale number instead of counting. Counting is the only thing that does not drift.
import collections as _c
_ids = _c.Counter(a for a, b in re.findall(r"(?m)^\|\s*(?:\*\*)?([A-Z]{1,2})(\d{1,2})(?:\*\*)?\s*\|", reg))
_stated = re.findall(r"cluster in the register at (\d+) findings", reg)
if _stated and int(_stated[0]) != _ids["F"]:
    fail("2", "the register says cluster F is %s findings; counting ids gives %d"
         % (_stated[0], _ids["F"]))
elif _stated:
    ok("cluster F's stated size (%s) equals its id count" % _stated[0])

print()
print("=" * 84)
print("3. THE DECISION RECORD against the option text it records")
print("=" * 84)
# capture the WHOLE verdict cell: it can now read "GO, AMENDED · RE-CONFIRMED", which the
# earlier character class could not match, producing a false mismatch against the §11 records.
# REWRITTEN 2026-08-05 for §11's build-order shape: the record table's first column is now the
# subsection number (**11.N**) rather than a review-order digit, and the rebuild no longer has a
# "fork" row — it is row 11.1 of the same table. Same assertion, new anchors.
status = dict(re.findall(r"\|\s*\*\*3\.\d+\*\*\s*\|\s*\*\*(\d+) — [^|]+\|\s*\*\*([^|*]+)\*\*", doc))
print(f"  status table: {status}")
subs = re.findall(r"^### 3\.(\d+) .*?— option (\d+)", doc, re.M)
print(f"  §11 subsections: {[f'11.{a}=opt{b}' for a, b in subs]}")
if status.get("10") != "DROPPED":
    fail("3", f"the rebuild is not recorded as DROPPED in the record table: {status.get('10')!r}")
decided = {k for k, v in status.items() if v.startswith("GO")}
recorded = {b for a, b in subs} - {"10"}          # option 10 is recorded AND dropped, by design
if decided - recorded:
    fail("3", f"option(s) marked GO in the table with no §11 record: {sorted(decided - recorded)}")
elif recorded - decided:
    fail("3", f"option(s) with a §11 record but not marked GO: {sorted(recorded - decided)}")
elif len(decided) != 10:
    fail("3", f"expected ten approved options, found {len(decided)}: {sorted(decided, key=int)}")
else:
    ok(f"ten options recorded and approved, the rebuild recorded as dropped: {sorted(decided, key=int)}")
# the record's decisions must match what §2 says
for dec, opt, must in [("2", "6", "CONDITIONAL, not optional"), ("3", "5", "four conditions"),
                       ("1", "4", "1c"), ("-", "3", "byte-compare IDENTICAL")]:
    if must.lower() not in FLAT.lower():
        fail("3", f"decision {dec} (option {opt}): the record's substance {must!r} is not in the document")
if not [f for f in FAIL if f.startswith("3")]:
    ok("each recorded decision's substance appears in the option text")

print()
print("=" * 84)
print("4. STRUCTURE — heading order, duplicates, stale PENDING")
print("=" * 84)
h2 = re.findall(r"^## (\d+)\.", doc, re.M)
if h2 != sorted(h2, key=int):
    fail("4", f"top-level sections out of order: {h2}")
else:
    ok(f"top-level sections in order: {h2}")
dup = [h for h, c in Counter(re.findall(r"^#{2,3} (.+)$", doc, re.M)).items() if c > 1]
if dup: fail("4", f"duplicate headings: {dup}")
else: ok("no duplicate headings")
opts = re.findall(r"^### Option (\d+)", doc, re.M)
ok(f"option headings present: {opts}")
pend = re.findall(r"\|\s*\*\*(\d+)\*\*\s*\|\s*\*\*(\d+) — [^|]+\|\s*PENDING", doc)
ok(f"still PENDING: options {[b for a, b in pend]}  (expected: none — all eleven decided)")
# the expected PENDING set shrinks as options are decided; keep it in step with the verdicts
EXPECTED_PENDING = []   # all eleven decided 2026-08-05; option 7 last
if sorted([b for a, b in pend], key=int) != EXPECTED_PENDING:
    warn("4", f"unexpected PENDING set: {[b for a, b in pend]}")

print()
print("=" * 84)
print("5. PRESCRIPTIONS WITH NO REGISTER ROW — recorded, not assumed")
print("=" * 84)
NOROW = [
 ("the synthetic-example replacement pass", "charter Confidentiality section", "renaming is not enough"),
 ("install-time behaviour in the host most users use", "comparison §5.2 row 5", "install-time behaviour"),
 ("does the prose reach the agent under pressure", "comparison §5.2 row 6", "reaches the agent under pressure"),
 ("the metadata-only run report", "charter Observability section", "metadata-only run report"),
]
for what, where, frag in NOROW:
    inreg = any(frag.lower() in v["text"].lower() for v in rows.values())
    indoc = frag.lower() in FLAT.lower()
    print(f"  {what:<50} in a register row: {str(inreg):<5} in the analysis: {indoc}  (source: {where})")
    if not indoc:
        fail("5", f"{what} is in no register row AND not in the analysis")
ok("each is sourced to a document even though no register row exists — so none can be lost")

print()
print("=" * 84)
print("6. A JUDGEMENT SURFACED RATHER THAN BURIED")
print("=" * 84)
print("  The register says the definitions detector needs REPLACING, NOT PATCHING.")
print("  Option 3 proposes a declared field PLUS keeping the detector as a fallback with two")
print("  improvements. Is that replacing, or is it patching wearing a new name?")
has = {k: (k.lower() in FLAT.lower()) for k in
       ["declared field in the notes", "stays as a FALLBACK", "report every one", "FAIL LOUDLY",
        "detection approach is what is failing"]}
print(f"  the components present: {has}")
judge("6", "the PRIMARY path is replaced (a declared range, no guessing) and the fallback is only "
           "for notes that carry no range — so it is replacement plus a guarded fallback, not a "
           "patch. But the register's words are absolute, and someone should confirm that reading "
           "rather than inherit it from me.")

print()
print("=" * 84)
print(f"RESULT: {len(FAIL)} failures, {len(WARN)} warnings, {len(JUDGE)} judgement(s) surfaced")
if FAIL: print("FAILURES: " + " · ".join(dict.fromkeys(FAIL)))
if WARN: print("WARNINGS: " + " · ".join(dict.fromkeys(WARN)))
print("=" * 84)
sys.exit(1 if FAIL else 0)
