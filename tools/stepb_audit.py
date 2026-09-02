#!/usr/bin/env python3
"""
STEP B — THE DEEP AUDIT.  Written fresh, per the audit gate's rule 1.

Wouter, 2026-08-05: "deep audit and verify ... line-by-line, going back to all other
documents including findings register.  The fact that you are now so easily 'finding' a
11th option makes me not feel so comfortable about how well you checked things."

The 11th option was missed by a specific failure mode: a verification pass FOUND the
defect and the document did not ACT on it.  So this audit hunts that shape as well as
ordinary errors.  Fourteen checks, each independent, each re-derived from the sources.

    uv run python tools/stepb_audit.py
"""
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

import os as _os

import sys as _sys
# A committed tool must not depend on the terminal codepage: on Windows a redirected
# stdout defaults to cp1252 and a UnicodeEncodeError reads to the caller as a FAILED
# check rather than a crashed one. See tests/run_tests.py, which pays for this lesson.
# hasattr: this module is IMPORTED by stepb_audit.py under redirect_stdout(StringIO),
# and StringIO has no .reconfigure. The unguarded version crashed the importer -- a
# fix that broke a second caller, which is the shape this project keeps logging.
if hasattr(_sys.stdout, "reconfigure"):
    _sys.stdout.reconfigure(encoding="utf-8", errors="replace")


# THE SEALED A4 JUDGING DIRECTORY IS NOT PUBLIC. CLAUDE.md 1.3 keeps its location in the
# private context.md, so this file must not carry it: set LEGAL_TRANSLATION_A4 to that
# directory to run the A4 arms. Absent, those arms VOID and say so — they never pass quietly.
A4_ROOT = Path(_os.environ.get("LEGAL_TRANSLATION_A4", "")) if _os.environ.get(
    "LEGAL_TRANSLATION_A4") else None


def _a4(*parts):
    """A path inside the sealed A4 directory, or None when it is not configured."""
    return A4_ROOT.joinpath(*parts) if A4_ROOT else None


ROOT = Path(__file__).resolve().parent.parent
DOC = ROOT / "STEP-B-ANALYSIS.md"
doc = DOC.read_text(encoding="utf-8")
reg = (ROOT / "FINDINGS-REGISTER.md").read_text(encoding="utf-8")
a3 = (ROOT / "A3-STRUCTURAL-ANALYSIS.md").read_text(encoding="utf-8")
cmp_ = (ROOT.parent / "legal-translation-private" / "A4-A3-COMPARISON.md").read_text(encoding="utf-8")
cmd = (ROOT / "CLAUDE.md").read_text(encoding="utf-8")
# CHARTER SOURCE, 2026-08-06. `CLAUDE.md` was rewritten on 2026-08-06 and several sentences
# this document quotes verbatim are now superseded wording -- the public-flip gate, the
# old layout-option label, and the charter's own claim about truncation detection that
# section 3.6 exists to CORRECT. A quotation check pointed at a living document breaks every
# time that document is legitimately edited, which is a false alarm, not a finding. So the
# charter source is the live file PLUS the pre-rewrite archive: the quotations were verbatim
# when they were written, and this keeps proving that.
# WIDENED 2026-08-06: most of what moved out of CLAUDE.md is still LIVE, in the two
# documents split out of it. Check those before falling back to the archive, or the
# archive becomes an excuse and the check stops noticing real loss.
for _extra in ("OPUS-5-MIGRATION.md", "DECISIONS-LOG.md",
               "temp/CLAUDE.md.pre-overhaul"):
    _p = ROOT / _extra
    if _p.exists():
        cmd = cmd + "\n" + _p.read_text(encoding="utf-8")
# the A4 REPORT is a FIFTH source, added 2026-08-05: this analysis now quotes it directly,
# after the third audit found it had been working from the comparison (a precis) instead.
RPT = _a4("report", "A4-REPORT.md")
# `RPT` is None when LEGAL_TRANSLATION_A4 is unset, so the existence test must be guarded.
# The first version of this rewrite was not, and the script died with AttributeError instead
# of VOIDing — a tool that CRASHES when an optional input is absent looks exactly like a tool
# that has found something, which is the reading this project keeps having to correct.
rpt = (RPT.read_text(encoding="utf-8", errors="replace")
       if RPT is not None and RPT.exists() else "")
if not rpt:
    print("  NOTE — the sealed A4 report is not configured, so the A4 arms of this audit are"
          "\n         VOID rather than passing. Set LEGAL_TRANSLATION_A4 to run them.")
# the SEALED SKILL TREE is a SIXTH source, added 2026-08-05. Until now every quotation in this
# analysis came from another ANALYSIS document; the disposal audit added quotations from the
# artefact itself, which no earlier source set could verify. The subject is the same 198 files
# the blind judge read, so a quotation checked against it is checked against what actually ships.
SUBJ = _a4("subject")
subj = "\n".join(p.read_text(encoding="utf-8", errors="replace")
                 for p in sorted(SUBJ.rglob("*")) if p.is_file()) \
    if SUBJ is not None and SUBJ.exists() else ""
SOURCES = {"register": reg, "A3": a3, "comparison": cmp_, "CLAUDE.md": cmd, "A4 report": rpt,
           "the sealed skill tree": subj}
ALLSRC = "\n".join(SOURCES.values())

# The deep-audit record quotes superseded figures on purpose. Checks that test what the
# document ASSERTS run against LIVE (the document minus that record); check 10 tests the
# record itself, against the pre-audit backup.
LIVE = doc
if "### The deep audit" in doc and "### Confidence, per claim" in doc:
    LIVE = doc[:doc.index("### The deep audit")] + doc[doc.index("### Confidence, per claim"):]

FAIL, WARN = [], []
def fail(tag, msg):
    print(f"  [FAIL] {tag}: {msg}"); FAIL.append(tag)
def warn(tag, msg):
    print(f"  [warn] {tag}: {msg}"); WARN.append(tag)
def ok(msg):
    print(f"  [OK ] {msg}")

# ---------------------------------------------------------------- register rows
ID_RE = re.compile(r"^\|\s*(?:\*\*)?([A-Z]{1,2}-?\d{1,2}[a-z]?)(?:\*\*)?\s*\|")
SECT_RE = re.compile(r"^#{2,3}\s+(.*)$")
rows, order, section = {}, [], None
for line in reg.splitlines():
    m = SECT_RE.match(line)
    if m:
        section = m.group(1).strip(); continue
    m = ID_RE.match(line)
    if m:
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        rows[m.group(1)] = dict(section=section, text=line, cells=cells,
                                sev=cells[-1].replace("*", "").strip(),
                                docs=cells[-3] if len(cells) >= 3 else "")
        order.append(m.group(1))
POS = {f for f in order if (rows[f]["section"] or "").startswith("Positives")}
INSTR = {f for f in order if (rows[f]["section"] or "").startswith("Measurement")}
SKILL = [f for f in order if f not in POS and f not in INSTR]

# option / group maps, imported from the emitter so they cannot drift
sys.path.insert(0, str(ROOT / "tools"))
import importlib.util
spec = importlib.util.spec_from_file_location("v", ROOT / "tools" / "stepb_verify.py")
V = importlib.util.module_from_spec(spec)
import io, contextlib
with contextlib.redirect_stdout(io.StringIO()):
    try:
        spec.loader.exec_module(V)
    except SystemExit:
        pass
GROUPS = {k: v.split() for k, v in V.GROUPS.items()}
OPTIONS = {k: v.split() for k, v in V.OPTIONS.items()}

print("=" * 80)
print("CHECK 1 — every internal cross-reference in the document resolves")
print("=" * 80)
sections = set(re.findall(r"^##+ (\d+(?:\.\d+)?)\.", doc, re.M))
refs = set(re.findall(r"§(\d+(?:\.\d+)?)", doc))
missing = sorted(r for r in refs if r.split(".")[0] not in {s.split(".")[0] for s in sections}
                 and r not in sections)
# §N.M refs must match a real subsection heading
sub = set(re.findall(r"^### (\d+\.\d+)", doc, re.M))
# a bare "§N.M" must be THIS document's; references to A3's sections must read "A3 §N.M"
bare = set(re.findall(r"(?<!A3 )(?<!A3's )§(\d+\.\d+)", doc))
bad_sub = sorted(r for r in bare if r not in sub and r not in sections)
if missing: fail("1a", f"§ refs with no such section: {missing}")
else: ok(f"all {len(refs)} distinct § refs resolve to a heading")
if bad_sub: warn("1b", f"§N.M refs not matching a ### heading: {bad_sub}")

opts_declared = set(re.findall(r"^### Option (\d+)", doc, re.M))
opts_cited = set(re.findall(r"\(option (\d+)\)|\boption (\d+)\b|\*\*option (\d+)\*\*", doc))
opts_cited = {x for t in opts_cited for x in t if x}
gap = sorted(opts_cited - opts_declared, key=int)
if gap: fail("1c", f"cites option(s) with no heading: {gap}")
else: ok(f"{len(opts_declared)} option headings, every cited option exists: {sorted(opts_declared, key=int)}")

dec_declared = set(re.findall(r"^\*\*(\d+)\.\s", doc, re.M)) | set(re.findall(r"\*\*(\d+)\*\*\s*\|\s*(?:what are|what authority|does the|the layout|it is not)", doc))
dec_cited = set(re.findall(r"decision (\d+)", doc))
if not dec_cited <= {"1", "2", "3", "4", "5", "6"}:
    fail("1d", f"cites decision(s) outside 1-6: {sorted(dec_cited - set('123456'))}")
else: ok(f"decisions cited: {sorted(dec_cited)} — all within 1-6")

br_declared = set(re.findall(r"^\|\s*\*\*(\d+)\*\*\s*\|", doc, re.M))
br_cited = set(re.findall(r"branch(?:es)? (\d+)", doc)) | set(re.findall(r"branches (\d+)[,–-]", doc))
gapb = sorted(br_cited - br_declared, key=int)
if gapb: fail("1e", f"cites branch(es) not in the table: {gapb}")
else: ok(f"branch table rows {min(br_declared, key=int)}–{max(br_declared, key=int)}, all citations resolve")

att = set(re.findall(r"refutation attempt (\d+)", doc))
if not att <= {str(i) for i in range(1, 10)}:
    fail("1f", f"refutation attempt out of range 1-9: {sorted(att)}")
else: ok(f"refutation attempts cited: {sorted(att, key=int)} (table has 9 rows)")

print()
print("=" * 80)
print("CHECK 2 — the branch table: count, behaviour-change tally, dependency order")
print("=" * 80)
brs = re.findall(r"^\|\s*\*\*(\d+)\*\*\s*\|\s*([^|]+)\|([^|]*)\|\s*(\*\*(?:no|yes|doc only)\*\*[^|]*)\|",
                 doc, re.M)
nums = [int(b[0]) for b in brs]
print(f"  branch rows parsed: {len(brs)}  ids {nums}")
claimed = re.search(r"\*\*(\w+) branches(?:, numbered [0-9–-]+)?\.\*\*", LIVE)
print(f"  the document claims: {claimed.group(0)!r}" if claimed else "  (no claim found)")
WORDS = {"nineteen": 19, "twenty": 20, "eighteen": 18}
if claimed and WORDS.get(claimed.group(1).lower()) != len(brs):
    fail("2a", f"claims {claimed.group(1)} branches; the table has {len(brs)} rows (0–{max(nums)})")
else: ok("branch count claim matches the table")
nochange = [b[0] for b in brs if "**no**" in b[3] or "doc only" in b[3]]
print(f"  branches with no observable behaviour change: {nochange}  = {len(nochange)}")
m = re.search(r"\*\*(\w+) branches change nothing (?:a document can see|observable)", LIVE)
if m:
    print(f"  the document claims: {m.group(0)!r}")
    if WORDS.get(m.group(1).lower(), {"eight": 8, "nine": 9}.get(m.group(1).lower())) != len(nochange):
        fail("2b", f"claims {m.group(1)}; actual {len(nochange)}")
    else: ok("behaviour-change tally correct")
m2 = re.findall(r"(\w+) of which change nothing observable", LIVE)
for w in m2:
    n = {"eight": 8, "nine": 9, "ten": 10}.get(w.lower())
    if n != len(nochange):
        fail("2c", f"§11 says '{w} of which change nothing observable'; actual {len(nochange)}")

print()
print("=" * 80)
print("CHECK 3 — 'no compliant repair' : the deadlock count, row by row")
print("=" * 80)
# WIDENED 2026-08-05: the narrow pattern gave 13 and the document claimed 14; neither was measured.
pat = re.compile(r"no (?:compliant|sanctioned|non-lossy|input-side) (?:fix|repair|route|option|lever|alternative|path)"
                 r"|no remedy (?:exists|available)|no operator remedy|NO sanctioned repair"
                 r"|not fixable from the input|there is no third option"
                 r"|the only (?:exit|way to a clean exit) is to (?:disobey|write something)"
                 r"|structurally unable to fix|golden rule forbids|which the golden rule forbids"
                 r"|closed loop|cannot (?:all )?be (?:obeyed|met)|unreachable by construction|unsatisfiable", re.I)
hitrows = []
for f in SKILL:
    m = pat.search(rows[f]["text"])
    if m:
        hitrows.append((f, m.group(0)))
print(f"  rows matching: {len(hitrows)}")
own, xref = [], []
for f, phrase in hitrows:
    # does the row assert it of ITSELF, or cite another row for it?
    ctx = rows[f]["text"][max(0, rows[f]["text"].find(phrase) - 120): rows[f]["text"].find(phrase) + 60]
    is_xref = bool(re.search(r"See ([A-Z]\d+)|see ([A-Z]\d+)", ctx))
    (xref if is_xref else own).append((f, phrase, ctx[-90:] if is_xref else ""))
print(f"  asserted of ITSELF        : {len(own)}  {[f for f, _, _ in own]}")
print(f"  asserted VIA a reference  : {len(xref)} {[f for f, _, _ in xref]}")
for f, ph, ctx in xref:
    print(f"      {f}: '{ph}' appears as -> ...{ctx.strip()}")
# F41 QUOTES the deadlock set in its own text and names the three closed loops, so a pattern
# search counts it as a member. It is the row ABOUT the set, not one of them -- counting it
# would double-count, and it is the error class A3's audit gate names: a grep counts a
# mechanism wherever a MESSAGE merely describes it. Excluded explicitly, with the reason
# stated, rather than by quietly tightening the pattern until the number comes out right.
DESCRIBES_NOT_MEMBER = {"F41"}
own = [x for x in own if x[0] not in DESCRIBES_NOT_MEMBER]

# CLOSED DEADLOCKS LEAVE THE LIVE SET, AND THE EXCLUSION IS POLICED RATHER THAN ASSERTED.
#
# C17 JOINED THIS SET ON 2026-09-02 AND LEFT IT THE SAME DAY, both by measurement. Branch 6's
# fourth slice measured that the mid-paragraph form was never a silent defect at all: Step 4
# rule 9 instructs the operator to mirror source whitespace, apply then cleared it, and
# `validate_apply --strict` REFUSED the result at repack because gluing two words merges token
# types -- so the manual walked them into a block with no legal way out, which is exactly this
# set's shape. The row now says so, which is why the pattern started matching it.
#
# But this count is about deadlocks an operator can still WALK INTO, and that one is fixed. So
# a row is excluded only while its own text declares a closure, and the check FAILS if the
# declaration is absent -- an exclusion that stops being true un-excludes itself instead of
# quietly holding the number down. That is the difference between this and narrowing the
# pattern, which the note above rules out.
CLOSED_DEADLOCK = {"C17"}
for _f in sorted(CLOSED_DEADLOCK):
    if _f not in rows:
        fail("3c", f"{_f} is declared a closed deadlock but is not a register row")
    elif not re.search(r"\bCLOSED\b", rows[_f]["text"]):
        fail("3c", f"{_f} is excluded from the deadlock count as CLOSED, and its row does "
                   f"not say so — the exclusion is no longer true")
    else:
        print(f"  excluded as CLOSED        : {_f} (its row declares the closure)")
own = [x for x in own if x[0] not in CLOSED_DEADLOCK]
loops = sorted({i for i in re.findall(r"\b(F\d+)\b", reg)
                if i in rows and re.search(r"closed loop", rows[i]["text"], re.I)
                and i not in DESCRIBES_NOT_MEMBER})
print(f"  the three closed loops    : {loops}")
true_total = len(own) + len([l for l in loops if l not in [f for f, _, _ in own]])
print(f"  DEFENSIBLE TOTAL          : {len(own)} self-asserting rows + "
      f"{len([l for l in loops if l not in [f for f,_,_ in own]])} closed loops = {true_total}")
claims14 = len(re.findall(r"\bfourteen\b(?=[^.]{0,80}(?:findings|no compliant|currently-silent))", doc, re.I))
print(f"  occurrences of 'fourteen' tied to this count in the document: {claims14}")
EXPECT = 18
claimed = "eighteen" in doc.lower() and "eighteen findings state" in doc.lower()
if true_total != EXPECT:
    fail("3a", f"the wide pattern now gives {true_total}; the document is written against {EXPECT}")
elif not claimed:
    fail("3b", "the document does not state the eighteen-row figure")
else:
    ok(f"the deadlock set is {true_total} rows and the document says so, with the set enumerated")

print()
print("=" * 80)
print("CHECK 4 — §1.1's per-defect document counts, D03/D03B treated as ONE document")
print("=" * 80)
def distinct_docs(fid):
    cell = rows[fid]["docs"]
    ids = set(re.findall(r"D\d{2}B?", cell))
    # D03B is the SAME document as D03, batch position the only variable
    if "D03B" in ids and "D03" in ids:
        ids.discard("D03B")
    return sorted(ids)
tests = [("A1", 2, "footnote anchor"), ("A2", 2, "comment anchors"), ("A16", 1, "source text page one"),
         ("F27", 2, "boundary tabs"), ("A15", 1, "tracked change cost"),
         ("J1", 5, "zero-width characters"), ("C19", 1, "untranslated aux part")]
for fid, claimed_n, label in tests:
    d = distinct_docs(fid)
    flag = "OK " if len(d) == claimed_n else "FAIL"
    print(f"  [{flag}] {fid:<4} {label:<26} doc cell={rows[fid]['docs']:<28} distinct={len(d)} claimed={claimed_n}")
    if len(d) != claimed_n:
        FAIL.append(f"4:{fid}")
# B3 separately: the register's docs cell disagrees with the register's own row text.
b3_cell = distinct_docs("B3")
b3_text = sorted(set(re.findall(r"D\d{2}", rows["B3"]["text"])))
print(f"  B3   docs cell={b3_cell}  but the row TEXT documents {b3_text}")
# Corrected 2026-08-05 on Wouter's approval: the cell read D07 alone. This now asserts the
# correction is in place -- the cell must name every document the row's own text documents.
if set(b3_text) - set(b3_cell):
    fail("4:B3-register", f"the docs cell for B3 omits {sorted(set(b3_text)-set(b3_cell))}, "
                          f"though the row's own text documents them")
else:
    ok(f"B3's docs cell now names every document its text documents: {b3_cell}")

print()
print("=" * 80)
print("CHECK 5 — every 'N findings' claim in the document against the generated maps")
print("=" * 80)
sizes = {k.split()[0]: len(v) for k, v in OPTIONS.items()}
gsizes = {k.split()[0]: len(v) for k, v in GROUPS.items()}
print(f"  option sizes: {sizes}")
print(f"  group sizes : {gsizes}   sum={sum(gsizes.values())}")
TOTAL = len(SKILL)   # derived, never hardcoded
if sum(gsizes.values()) != TOTAL: fail("5a", f"groups sum to {sum(gsizes.values())}, not {TOTAL}")
else: ok(f"consequence groups sum to {TOTAL}")

# AND EACH GROUP'S OWN HEADING, not only the sum. ADDED 2026-08-18, because the sum passing is
# not the same as the parts being right: G10 moved group 3 from 41 to 42 on 2026-08-11 and
# `### 5.3 ... — 41 findings` shipped unchanged, while this check reported the groups summing
# correctly. That is the "N of M" bookkeeping class CLAUDE.md 5.12 says clusters here and that
# prose review does not see -- and it slipped past in one of our own audit tools.
for num in sorted(gsizes, key=int):
    m = re.search(rf"^### 5\.{num} .*?(\d+) findings", LIVE, re.M)
    if not m:
        warn("5d", f"group {num}: its 5.{num} heading states no 'N findings' figure")
    elif int(m.group(1)) != gsizes[num]:
        fail("5d", f"group {num}: heading 5.{num} says {m.group(1)} findings, map says "
                   f"{gsizes[num]}")
    else:
        ok(f"group {num}: heading 5.{num} states {gsizes[num]} findings, matches the map")
# Derived, not hardcoded: for each option, find every "N findings" figure inside that
# option's own section and require it to equal the map's size for that option.
opt_txt = {}
heads = [(m.group(1), m.start()) for m in re.finditer(r"^### Option (\d+)", LIVE, re.M)]
for i, (num, pos) in enumerate(heads):
    endp = heads[i + 1][1] if i + 1 < len(heads) else LIVE.index("## 10. The ranking")
    opt_txt[num] = LIVE[pos:endp]
for num in sorted(sizes, key=int):
    txt = opt_txt.get(num, "")
    figs = {int(x) for x in re.findall(r"\*\*(\d+) findings", txt)} |            {int(x) for x in re.findall(r"(\d+) findings, (?:one file|the largest|documentation|all visible|and it removes)", txt)}
    if not figs:
        warn("5a", f"option {num} states no 'N findings' figure in its own section")
        continue
    if sizes[num] not in figs:
        fail("5b", f"option {num}: its section states {sorted(figs)} and never {sizes[num]}, which the map says")
    else:
        extra = sorted(figs - {sizes[num]})
        ok(f"option {num}: states {sizes[num]} findings, matches the map"
           + (f"  (also cites {extra} — check these are cross-references, not size claims)" if extra else ""))
# the ranking table's per-option figures must agree too
for m in re.finditer(r"\(option (\d+)[^)]*\)\s*\|([^|]*)\|", LIVE):
    num, cell = m.group(1), m.group(2)
    for f in re.findall(r"(\d+) findings", cell):
        if num in sizes and int(f) != sizes[num]:
            fail("5c", f"ranking row for option {num} says {f} findings, map says {sizes[num]}")
crit_by_opt = {k: [i for i in v if rows[i]["sev"].startswith("CRITICAL")] for k, v in OPTIONS.items()}
print("  worst-grade findings per option:")
for k, v in crit_by_opt.items():
    if v: print(f"      {k:<50} {len(v)} {v}")

print()
print("=" * 80)
print("CHECK 6 — the rebuild arithmetic: 'at most 99 of 160'")
print("=" * 80)
subsumed = set()
for k in OPTIONS:
    if k.split()[0] in {"1", "2", "3", "6"}:
        subsumed |= set(OPTIONS[k])
print(f"  union of options 1,2,3,6 = {len(subsumed)} findings")
print(f"  left untouched            = {len(SKILL) - len(subsumed)}")
m = re.search(r"at most (\d+) of\s*\n?the 160 findings", doc) or re.search(r"at most (\d+) of the 160", doc)
print(f"  the document claims: 'at most {m.group(1)} of 160'" if m else "  (claim not found)")
if m and int(m.group(1)) != len(subsumed):
    fail("6a", f"document says {m.group(1)}, union is {len(subsumed)}")
else: ok("rebuild arithmetic reproduces")
m2 = re.search(r"leaves (?:at least )?(\d+) exactly where they are", LIVE)
if m2 and int(m2.group(1)) != len(SKILL) - len(subsumed):
    fail("6b", f"document says leaves {m2.group(1)}, actual {len(SKILL) - len(subsumed)}")
elif m2: ok(f"'leaves at least {m2.group(1)}' reproduces")

print()
print("=" * 80)
print("CHECK 7 — THE 11TH-OPTION FAILURE MODE: did the document ACT on every")
print("           finding its own verification passes produced?")
print("=" * 80)
# each pass finding -> the concrete change it should have produced, and where to look
acted = [
 ("attempt 1 — cross-language comparison not decidable",
  r"decidable form is\s+\*\*same-language\*\*", "option 2 text carries the refinement"),
 ("attempt 2 — tidy-up script coupling",
  r"^\|\s*\*\*9\*\*\s*\|\s*the change journal", "branch 9 exists"),
 ("attempt 3 — 'preserve by default' self-contradictory",
  r"three clauses: \*\*rebuild only text", "option 1 states the three clauses"),
 ("attempt 4 — partial resolver insufficient",
  r"A partial resolver is measured insufficient|partial cascade resolver", "option 3 says why a cheap version fails"),
 ("attempt 5 — layout group has no fix in option 3",
  r"^### Option 11", "OPTION 11 EXISTS  <-- the one that was missing"),
 ("attempt 6 — furniture unverifiable by gate",
  r"cannot be verified by any automatic check|cannot be verified by the never-regress gate",
  "option 4 / ranking states it"),
 ("attempt 7 — exception channel highest-risk",
  r"HIGHEST-RISK documentation change|highest-risk documentation change", "option 5 states it"),
 ("attempt 8 — truncation consequences are predictions",
  r"the \*consequences\* are predictions|PREDICTIONS as to consequence", "option 8 labels them"),
 ("attempt 9 — A3 never priced a true rebuild",
  r"a genuine rebuild has never been priced", "option 10 says so"),
 ("omission 1 — the deadlock",
  r"^\|\s*\*\*4\*\*\s*\|\s*the exception channel", "branch 4 exists and precedes branch 5"),
 ("omission 2 — no manifest / version identity rows",
  r"recorded as rows before that branch starts|needs a manifest", "flagged with an action"),
 ("omission 7 — merge-order file conflicts",
  r"One file-level warning for merge order", "§4 carries the warning"),
]
for label, rx, what in acted:
    hit = bool(re.search(rx, doc, re.M))
    print(f"  [{'OK ' if hit else 'FAIL'}] {label}\n         -> {what}: {hit}")
    if not hit: FAIL.append(f"7:{label}")

print()
print("=" * 80)
print("CHECK 8 — OMISSION HUNT: is every source-document unit owned by something?")
print("=" * 80)
# 8a: A3's six keystones each map to an option
ks_to_opt = {"KS1": "3", "KS2": "1", "KS3": "2", "KS4": "4", "KS5": "5", "KS6": "6"}
print(f"  A3's six keystones -> options {ks_to_opt}  (all six present: "
      f"{set(ks_to_opt.values()) <= {k.split()[0] for k in OPTIONS}})")
# 8b: every register CLUSTER owned
letters = sorted({re.match(r'[A-Z]+', f).group() for f in SKILL})
for L in letters:
    ids = [f for f in SKILL if re.match(r'[A-Z]+', f).group() == L]
    owners = sorted({k.split()[0] for k in OPTIONS for i in ids if i in OPTIONS[k]}, key=int)
    if not owners: fail("8b", f"cluster {L} owned by NO option")
print(f"  every cluster has at least one owning option: {all(any(i in v for v in OPTIONS.values()) for i in SKILL)}")
# 8c: the four OPEN instrument defects
openi = [f for f in INSTR if "open" in rows[f]["text"].lower().split("|")[-1]]
openi = [f for f in INSTR if re.search(r"\|\s*open\s*\|?\s*$", rows[f]["text"])]
print(f"  open instrument defects (our own tooling): {sorted(openi)}")
for i in sorted(openi):
    cited = i in doc
    print(f"      {i} named in STEP-B-ANALYSIS.md: {cited}")
    if not cited: warn("8c", f"{i} (an OPEN defect in our own harness) is not mentioned")
# 8d: positives protection
unprot = [p for p in sorted(POS) if p not in doc]
print(f"  positives never mentioned in the document: {len(unprot)}/{len(POS)}")
if len(unprot) > len(POS) - 4:
    warn("8d", f"only {len(POS)-len(unprot)} of {len(POS)} positives are named: {sorted(set(POS)-set(unprot))}")

print()
print("=" * 80)
print("CHECK 9 — consequence-group MIS-ASSIGNMENT: does each row's consequence")
print("           actually match the group it is filed under?")
print("=" * 80)
# heuristics that should hold per group; every violation is printed for judgement
G1 = set(GROUPS["1 loses content"]); G2 = set(GROUPS["2 looks wrong on the page"])
G3 = set(GROUPS["3 says it worked when it did not"]); G4 = set(GROUPS["4 hard to keep correct"])
G5 = set(GROUPS["5 the manual is wrong"])
suspects = []
for f in G1:
    if not re.search(r"lost|loss|destroy|delet|missing|unreachable|untranslated|remnant|survives|"
                     r"corrupt|drop|no longer|gone|invisible", rows[f]["text"], re.I):
        suspects.append(("1 loses content", f, "no loss/deletion vocabulary in the row"))
for f in G2:
    if not re.search(r"render|page|bold|italic|underline|highlight|smallCaps|indent|tab|layout|"
                     r"align|spacing|font|visible|typograph|capital|spread", rows[f]["text"], re.I):
        suspects.append(("2 looks wrong", f, "no appearance vocabulary in the row"))
for f in G3:
    if not re.search(r"CLEAN|PASS|passed|exit|gate|check|validator|report|false positive|warn|audit|"
                     r"cannot fail|blind|no gate", rows[f]["text"], re.I):
        suspects.append(("3 says it worked", f, "no assurance vocabulary in the row"))
for s in suspects:
    print(f"  [judge] {s[0]:<18} {s[1]:<5} {s[2]}")
if not suspects: print("  (no group violates its own vocabulary test)")
# specific pairs worth a human eye, chosen because the row's stated FIX names other rows
for f in ("T1", "T2", "T3", "T4", "T5", "T6", "Q1", "C2"):
    grp = [k for k in GROUPS if f in GROUPS[k]][0]
    opt = sorted({k.split()[0] for k in OPTIONS if f in OPTIONS[k]}, key=int)
    print(f"  {f:<4} group={grp:<34} options={opt}")
print("  T6's own text names its fix as: ", end="")
print(re.search(r"Fix those and batch position stops mattering", rows["T6"]["text"]) is not None,
      "-> the rows it names are A16, B1, B7, C19 (options 1 and 6), NOT option 5")

print()
print("=" * 80)
print("CHECK 10 — every italic-quoted string in the document appears in a source")
print("=" * 80)
# Two kinds of italic quotation live in this document and BOTH are verified, not excluded:
#   (i)  quotations of a SOURCE          -> must be verbatim in the register / A3 / comparison / CLAUDE.md
#   (ii) quotations of this document's OWN superseded wording, inside the deep-audit record
#        -> must be verbatim in the pre-audit backup, which is where that wording lives
# The refutation table's left column is neither: it holds MY hypotheses, and is excluded by design.
refut = doc[doc.index("### Pass B"):doc.index("### Pass C")] if "### Pass B" in doc else ""
# §11 quotes WOUTER'S OWN VERDICTS, which live in no file. They are real quotations and are
# unverifiable by design -- the same class as his audit instruction. Excluded explicitly.
record = doc[doc.index("## 3. The build brief"):doc.index("## 4. How each branch")] if "## 3. The build brief" in doc else ""
audrec = ""
if "### The deep audit" in doc:
    audrec = doc[doc.index("### The deep audit"):doc.index("### Confidence, per claim")]
body = doc.replace(refut, "").replace(audrec, "").replace(record, "")
def norm(t):
    t = t.replace("*", "").replace(chr(92), "")
    t = re.sub(r"^\s*>\s?", "", t, flags=re.M)   # blockquote markers: a quote inside a
    t = t.replace(" > ", " ")                      # > block must still match its source
    for a_, b_ in [("“", '"'), ("”", '"'), ("‘", "'"), ("’", "'")]:
        t = t.replace(a_, b_)
    return re.sub(r"\s+", " ", t).strip()
BACKUP = ROOT / "temp" / "STEP-B-ANALYSIS.md.pre-deepaudit"
prev = norm(BACKUP.read_text(encoding="utf-8")) if BACKUP.exists() else ""
hay = norm(ALLSRC)
# A quotation ATTRIBUTED to Wouter is his spoken instruction: it lives in no file and is
# unverifiable by design, wherever it appears. Classify by attribution, not by location --
# excluding a whole section would hide real misquotations sitting inside it.
q_src, q_spoken = [], []
for m in re.finditer(r'\*"([^"]{18,400})"\*', body):
    # attribution can PRECEDE or FOLLOW the quotation ("... he was right"), so check both sides
    window = body[max(0, m.start() - 420):m.start()] + " || " + body[m.end():m.end() + 160]
    (q_spoken if re.search(r"Wouter|his words|his question|he challenged|his instruction"
                           r"|[Hh]e was right|he asked", window)
     else q_src).append(m.group(1))
q_aud, q_aud_spoken = [], []
for m in re.finditer(r'\*"([^"]{10,400})"\*', audrec):
    window = audrec[max(0, m.start() - 420):m.start()] + " || " + audrec[m.end():m.end() + 160]
    (q_aud_spoken if re.search(r"Wouter|his words|his question|he challenged|his instruction"
                               r"|[Hh]e was right|he asked|was ordered", window)
     else q_aud).append(m.group(1))
print(f"  (i)  source quotations                       : {len(q_src)}")
print(f"  (iv) quotations attributed to Wouter          : {len(q_spoken)}  (spoken, in no file, unverifiable by design)")
print(f"  (ii) quotations of superseded wording         : {len(q_aud)}  (checked against the pre-audit backup)")
print(f"  (v)  Wouter's instructions in the audit record: {len(q_aud_spoken)}  (spoken, in no file, unverifiable by design)")
print(f"       hypotheses in Pass B's left column       : {refut.count(chr(42)+chr(34))}  (mine, excluded by design)")
print(f"  (iii) Wouter's verdicts quoted in the record  : {record.count(chr(42)+chr(34))//2}  (spoken, in no file, unverifiable by design)")
# A QUOTATION WE CANNOT CHECK IS VOID, NOT FALSE. Two of the six sources -- the sealed A4
# report and the sealed subject tree -- are only readable when LEGAL_TRANSLATION_A4 is set,
# because their location is confidential. When they are absent, a quotation that lives only in
# them is UNVERIFIABLE, and reporting it as "not verbatim in any source" says the document is
# wrong when the truth is that the evidence was out of reach. The first version of this
# promotion did exactly that and produced 8 phantom failures.
# A MISSING SOURCE DOES NOT GET A QUOTATION EXCUSED, and this is the second attempt at it.
#
# Two sources can legitimately be absent on a machine that is not this one: the sealed A4
# directory (confidential, so its location is not committed) and the pre-audit backup in temp/
# (a session artefact, gitignored). The FIRST attempt reasoned that a quotation which could
# only live in an unreadable source is VOID rather than false, and skipped it.
#
# stepb_metacheck.py caught that immediately: detection dropped from 10 of 10 mutations to 9,
# because the "misquote a source" mutation now landed in the excused bucket. **The softening
# blunted the check it was meant to make honest** — which is the exact failure this branch has
# been finding in other people's instruments all day, committed here in my own.
#
# So an unverifiable quotation is still a FAILURE, and the banner says why the audit cannot be
# completed rather than quietly completing it. CLAUDE.md 5.1: a control that opened no files
# says VOID, never CLEAN — and VOID is not a pass, so the non-zero exit is correct. Set
# LEGAL_TRANSLATION_A4 for a clean run.
if not rpt or not prev:
    absent = ", ".join(n for n, v in (("the sealed A4 sources", rpt),
                                      ("the pre-audit backup in temp/", prev)) if not v)
    print(f"  [BANNER] {absent} could not be read, so check 10 CANNOT BE COMPLETED here.")
    print("           Quotations that live only there will be reported as failures below.")
    print("           That is deliberate: excusing them made stepb_metacheck.py drop from")
    print("           10 of 10 mutations detected to 9. An unreadable source is not a pass.")
bad = 0
for q in q_src:
    if norm(q) not in hay:
        bad += 1; print(f"  [FAIL] (i) not verbatim in any source: {norm(q)[:100]!r}")
for q in q_aud:
    n_ = norm(q)
    if n_ not in prev and n_ not in hay:
        bad += 1
        print(f"  [FAIL] (ii) not verbatim in the pre-audit backup OR a source: {n_[:100]!r}")
if bad: FAIL.append(f"10: {bad} unverified quotations")
else: ok("every italic-quoted string traces to a source document verbatim")

print()
print("=" * 80)
print("CHECK 11 — the measured numbers quoted in the document, re-derived")
print("=" * 80)
NUMS = [
 ("694",   "b=0 runs on one document",             lambda: "0 → 694" in rows["A12"]["text"]),
 ("38",    "italic spans destroyed",               lambda: "38 ITALIC SPANS" in rows["B1"]["text"]),
 ("91.8",  "justification word-gap points",        lambda: "91.8" in rows["D2"]["text"]),
 ("31.1",  "source's worst word gap",              lambda: "31.1" in rows["D2"]["text"]),
 ("28 → 14","comment anchors",                     lambda: "28 → 14" in rows["A2"]["text"]),
 ("80",    "tab characters before",                 lambda: "80→10" in rows["A3"]["text"] or "80 → 10" in rows["A3"]["text"]),
 ("34",    "hyperlinks before",                    lambda: "34 → 1" in rows["A8"]["text"]),
 ("42",    "duplicated cross-references",          lambda: "42 paragraphs" in rows["A9"]["text"]),
 ("8813",  "token count the gate reported",        lambda: "8813" in rows["C1"]["text"]),
 ("32",    "issues the quality gate declared",     lambda: "32 issues" in rows["C3"]["text"]),
 ("1,547", "characters lost at extraction",        lambda: "1,547" in rows["C28"]["text"]),
 ("6 of 1,656","Avoid columns in sub-lexicons",    lambda: "6 OF 1,656" in rows["E13"]["text"]),
 ("134",   "sub-lexicon files with no Avoid",      lambda: "134 of 154" in rows["E13"]["text"]),
 ("180 of 184","reference tables carrying Avoid",  lambda: "180 carrying" in rows["E13"]["text"]),
 ("37",    "UK spelling rules",                    lambda: "37 rules" in rows["V1"]["text"]),
 ("60",    "US-tree spelling rules",               lambda: "against 60 in the US package" in rows["V1"]["text"]),
 ("34",    "US_SPELLING in UK tree",               lambda: "34 against 91" in rows["V1"]["text"]),
 ("55,466","only observed truncation position",    lambda: "55,466" in rows["W1"]["text"]),
 ("1,803", "SKILL.md bytes past the cut",          lambda: "1,803" in rows["W2"]["text"]),
 ("178",   "files with no integrity check",        lambda: "178 / 89.9" in rows["W2"]["text"] or "178" in rows["W2"]["text"]),
 ("221",   "furniture phrases in a script",        lambda: "221-ENTRY" in rows["F31"]["text"]),
 ("158",   "missing dual-variant markers",         lambda: "158" in a3),
 ("8,028", "bytes in rule 3",                      lambda: "8,028" in a3),
 ("121",   "lines in rule 3",                      lambda: "121 lines" in a3),
 ("16.8%", "rule 3 share of the step doc",         lambda: "16.8%" in a3),
 ("25 minutes","fixed runtime overhead",           lambda: "about **25 minutes" in a3 or "25 minutes" in a3),
 ("2.4",   "seconds per paragraph",                lambda: "2.4 seconds" in a3),
 ("6.4%",  "context share at peak",                lambda: "6.4%" in a3),
 ("35 minutes","source==target run cost",          lambda: "35 minutes" in rows["H3"]["text"]),
 ("28 commands","source==target commands",         lambda: "28 commands" in rows["H3"]["text"]),
 ("40%",   "paragraphs differing linguistically",  lambda: "10 of 24" in rows["P23"]["text"]),
 ("13",    "construction positives",               lambda: "thirteen properties" in rows["P27"]["text"]),
 ("618",   "unexplained variant line-pairs",       lambda: "618" in a3),
 ("165",   "whole-tree marker delta",              lambda: "165" in a3),
 # ADDED 2026-08-05 with Option 7's rewrite: every argument-carrying figure it introduced.
 # Without these the two-sided guard does not cover the newest option, which is precisely the
 # hole the metacheck found the first time ("falsifying 694 to 690 passed everything").
 ("3,593", "whole-tree changed lines",             lambda: "3,593" in a3),
 ("176",   "files that differ between the trees",  lambda: "176 of 198" in a3),
 ("68.3%", "share the crude fold explains",        lambda: "68.3%" in a3),
 ("1,947", "changed line-pairs",                   lambda: "1,947 changed" in a3),
 ("345",   "residue pairs in six files",           lambda: "345 of the 618" in a3),
 ("31 of 49","SKILL.md variant-selection pairs",   lambda: "31 of its 49" in a3),
 ("158",   "sub-lexicon marker shortfall",         lambda: "shortfall is **158**" in a3),
 ("4 of 11","languages with compliance rules",     lambda: "4 of 11" in rows["V2"]["text"]),
 ("1.9",   "per-language byte spread",             lambda: "1.9" in rows["V2"]["text"]),
 ("8.6",   "per-file byte spread",                 lambda: "8.6" in rows["V2"]["text"]),
 ("fourteen sentences", "prose damaged by an automated pass",
  lambda: "FOURTEEN SENTENCES BROKEN" in rows["F38"]["text"]),
]
for label, what, test in NUMS:
    got = test()
    print(f"  [{'OK ' if got else 'FAIL'}] {label:<12} {what}")
    if not got: FAIL.append(f"11:{label}")
# TWO-SIDED, added 2026-08-05 after a negative test found the hole: verifying that the SOURCE
# contains a figure says nothing about whether the ANALYSIS quotes it correctly. Falsifying
# 694 -> 690 passed every check. These figures carry the argument, so each must appear verbatim
# in the live text; if one is altered, the argument silently changes and nothing else notices.
MUST_CITE = ["694", "38", "91.8", "31.1", "28 → 14", "42", "8813", "32", "1,547", "6 of 1,656",
             "134", "180 of 184", "37", "60", "1,803", "178", "221", "8,028", "121", "16.8%",
             "25 minutes", "2.4", "6.4%", "35 minutes", "28 commands", "40%", "13", "80", "34"]
for fig in MUST_CITE:
    if fig not in LIVE:
        fail("11c", f"the analysis no longer cites the measured figure {fig!r} — either it was "
                    f"altered or the claim it supports was removed")
if not [f for f in FAIL if f.startswith("11c")]:
    ok(f"all {len(MUST_CITE)} argument-carrying figures appear verbatim in the analysis")
for label, _, _ in NUMS:
    key = label.split()[0]
    if key not in doc and label not in doc:
        warn("11b", f"{label!r} is verified in the source but is not quoted in the document")

print()
print("=" * 80)
print("CHECK 12 — claims the document makes that appear in NO source (must be")
print("           labelled as this document's own reasoning)")
print("=" * 80)
novel = [
 ("the deadlock consequence", "converts silent defects into", True),
 ("the change-journal coupling", "cannot be built until", True),
 ("layout has no fix in any option", "no FIX in any option", True),
 ("two instruments, not one", "development instrument", True),
 ("the same-language refinement", "same-language", True),
]
for label, needle, must_be_labelled in novel:
    inreg = needle.lower() in ALLSRC.lower()
    indoc = needle.lower() in doc.lower()
    print(f"  {label:<38} in a source: {str(inreg):<5} in the document: {indoc}")
    if indoc and not inreg:
        # must be attributed to §7 or marked INFERRED
        near = doc.lower().count("inferred") + doc.count("§7")
        print(f"      -> novel to this document. 'INFERRED'/§7 attributions present: {near}")

print()
print("=" * 80)
print("CHECK 13 — the appendix is consistent with the option/group maps")
print("=" * 80)
app_all = doc.split("## 9. Traceability appendix", 1)[1]
app = app_all.split("### 9.2", 1)[1].split("### 9.3", 1)[0]   # option table only
app_g = app_all.split("### 9.1", 1)[1].split("### 9.2", 1)[0]  # group table only
for k, ids in OPTIONS.items():
    n = k.split()[0]
    m = re.search(rf"^\|\s*{n}\s*\|[^|]*\|\s*([^|]+)\|", app, re.M)
    if not m:
        fail("13a", f"option {n} missing from the appendix"); continue
    listed = m.group(1).split()
    if sorted(listed) != sorted(ids):
        fail("13b", f"option {n}: appendix lists {len(listed)}, map has {len(ids)}; "
                    f"diff={set(listed) ^ set(ids)}")
for k, ids in GROUPS.items():
    n = k.split()[0]
    m = re.search(rf"^\|\s*{n}\s*\|[^|]*\|\s*([^|]+)\|", app_g, re.M)
    if m and sorted(m.group(1).split()) != sorted(ids):
        fail("13c", f"group {n}: appendix/map mismatch diff={set(m.group(1).split()) ^ set(ids)}")
if not [f for f in FAIL if f.startswith("13")]:
    ok("appendix matches the generated maps exactly, option by option and group by group")

print()
print("=" * 80)
print("CHECK 14 — the ranking table: one row per option, no gaps, no duplicates")
print("=" * 80)
rank = re.findall(r"^\|\s*(?:\*\*(\d+)\*\*|—)\s*\|\s*\*\*([^|]+?)\*\*\s*\(option (\d+)[^)]*\)", doc, re.M)
rank = [r for r in rank if r[0]]                       # numbered ranks only
rebuild = re.search(r"^\|\s*\*\*—\*\*\s*\|\s*\*\*Rebuild\*\*\s*\(option (\d+)\)", doc, re.M) \
       or re.search(r"^\|\s*—\s*\|\s*\*\*Rebuild\*\*\s*\(option (\d+)\)", doc, re.M)
print(f"  ranking rows: {len(rank)}")
positions = [int(r[0]) for r in rank]; opts = [r[2] for r in rank]
if positions != list(range(1, len(positions) + 1)):
    fail("14a", f"rank positions are {positions}, not 1..{len(positions)}")
else: ok(f"rank positions 1..{len(positions)} with no gaps")
dup = [o for o, c in Counter(opts).items() if c > 1]
if dup: fail("14b", f"option(s) ranked more than once: {dup}")
ranked = set(opts) | ({rebuild.group(1)} if rebuild else set())
missing_from_rank = sorted({k.split()[0] for k in OPTIONS} - ranked, key=int)
print(f"  the rebuild row is present and unranked: {bool(rebuild)}")
if missing_from_rank:
    fail("14c", f"option(s) with no rank: {missing_from_rank}")
else: ok(f"every one of the {len(OPTIONS)} options is ranked exactly once")

print()
print("=" * 80)
print("CHECK 15 — the two RETIRED FORMULATIONS must still be stated as retired")
print("=" * 80)
# Added 2026-08-05 after a negative test found NO check guarded these. Both were one-word
# summaries that did not survive contact with the mechanism; if either is ever restated as
# the recommendation, the plan silently reverts to a scoping error this project already made.
for label, retired, must_say in [
    ("option 1", "preserve by default",
     ['The right formulation is not "preserve by default"', "three clauses"]),
    ("option 6", "optional stylistic half",
     ["CONDITIONAL, not optional", "no operator switch"]),
]:
    said = [x for x in must_say if x.lower() in LIVE.lower()]
    if len(said) == len(must_say):
        ok(f"{label}: '{retired}' is still stated as retired, with its replacement")
    else:
        fail("15", f"{label}: the retired formulation '{retired}' is no longer marked as retired "
                   f"(missing: {[x for x in must_say if x not in said]})")

print()
print("=" * 80)
print(f"RESULT: {len(FAIL)} failures, {len(WARN)} warnings")
if FAIL: print("FAILURES: " + " · ".join(dict.fromkeys(FAIL)))
if WARN: print("WARNINGS: " + " · ".join(dict.fromkeys(WARN)))
print("=" * 80)
sys.exit(1 if FAIL else 0)
