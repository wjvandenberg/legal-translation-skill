#!/usr/bin/env python3
"""
Step B — measurement pass 2: VERIFICATION PASS A of the brief's three passes.

"does every proposal cite recorded failures that exist and say what is claimed"

For every claim STEP-B-ANALYSIS.md will make, this asserts:
  - the register row exists
  - the row's own text contains the substring the claim rests on
It also holds the consequence-group and option assignment maps, and proves
every one of the 160 skill findings is assigned exactly once to a consequence
group and to at least one option — the traceability appendix is EMITTED from
here rather than typed, so it cannot drift from the register.

Run:  uv run python tools/stepb_verify.py            (checks)
      uv run python tools/stepb_verify.py --appendix  (emit the appendix tables)
"""
import re
import sys
from collections import Counter, defaultdict
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
reg = (ROOT / "FINDINGS-REGISTER.md").read_text(encoding="utf-8")
a3 = (ROOT / "A3-STRUCTURAL-ANALYSIS.md").read_text(encoding="utf-8")

FAIL = []

# ------------------------------------------------------------------ row parse
ID_RE = re.compile(r"^\|\s*(?:\*\*)?([A-Z]{1,2}-?\d{1,2}[a-z]?)(?:\*\*)?\s*\|")
SECT_RE = re.compile(r"^#{2,3}\s+(.*)$")
rows, order, section = {}, [], None
for ln, line in enumerate(reg.splitlines(), 1):
    m = SECT_RE.match(line)
    if m:
        section = m.group(1).strip(); continue
    m = ID_RE.match(line)
    if not m:
        continue
    fid = m.group(1)
    rows[fid] = dict(section=section, text=line, line=ln,
                     sev=line.strip().strip("|").split("|")[-1].replace("*", "").strip())
    order.append(fid)

def sect(frag):
    return [f for f in order if rows[f]["section"] and frag.lower() in rows[f]["section"].lower()]

POSITIVES = set(sect("Positives to preserve"))
INSTR = set(sect("Measurement-instrument defects"))
SINGLE = set(sect("Unclustered / single-instance"))
SKILL = [f for f in order if f not in POSITIVES and f not in INSTR]      # 160

# --------------------------------------------------- the stale-cell check, fixed
print("=== A0. The Clusters table's cluster-A verdict cell (4-column table only) ===")
clu = re.search(r"^## Clusters \(root causes\)\s*$(.*?)^\*\*Cluster A is", reg, re.S | re.M)
arow = re.search(r"^\|\s*\*\*A\*\*\s*\|(.*)$", clu.group(1), re.M) if clu else None
if arow:
    cells = [c.strip() for c in arow.group(1).strip().strip("|").split("|")]
    print(f"  cells: {len(cells)} -> verdict = {cells[-1]!r}")
    # Corrected 2026-08-05 under decision 5: the cell used to assert the fix A3 retired.
    # This now asserts the CORRECTION is in place, and that the retired wording is quoted
    # inside it so the record of what it used to say survives.
    fixed = cells[-1].startswith("**NO — TWO fixes") and "matched source run" in cells[-1]
    print(f"  [{'OK ' if fixed else 'FAIL'}] the corrected verdict is in place, with the retired "
          f"wording quoted inside it: {fixed}")
    if not fixed:
        FAIL.append("cluster-A verdict cell is not in its corrected state")
else:
    print("  [FAIL] could not isolate the Clusters table"); FAIL.append("clusters table")

# ------------------------------------------------------------------ CLAIMS
# (row id, substring that must be present in that row, what the analysis says)
CLAIMS = [
 ("C1",  "compares TOKEN SETS",                    "the strictest gate compares sets of words"),
 ("C1",  "polices only MISSING tokens",            "it never polices extra tokens"),
 ("C3",  "no `sys.exit`",                          "the mandatory quality gate cannot fail the run"),
 ("C3",  "OVERALL: PASS",                          "the audit certified a document with QC issues"),
 ("C5",  "does not exist",                         "Hard Rule 3 describes a gate that is not there"),
 ("C18", "from the FINAL `document.xml`",          "the proposed gate reads the delivered file"),
 ("C18", "THIS ROW'S FIX DOES NOT CLOSE THAT ONE", "C18's fix leaves the extraction half open"),
 ("C28", "AT EXTRACTION",                          "loss introduced at extraction is invisible"),
 ("C28", "1,547 characters",                       "the skill documents this class costing real content"),
 ("C23", "A CORRUPT DELIVERABLE EXITS 0",                                "a corrupt deliverable exits 0"),
 ("C23", "no temp-then-rename",                    "the deliverable is written in place"),
 ("C27", "no test file",                           "nothing exists to make a check fail"),
 ("C19", "CANNOT CARRY",                           "repack has no route for the glossary part"),
 ("C12", "namelist()",                             "the Step 2 aux check is an inventory test"),
 ("A1",  "the pointer is gone",                    "footnote anchors deleted, aux part intact"),
 ("A2",  "28 → 14",                           "half the comment anchors destroyed on one document"),
 ("A16", "UNTRANSLATED SOURCE TEXT ON PAGE ONE",   "a content control stranded source text on page 1"),
 ("A19", "THIRD container",                        "graphic metadata is the third unenumerated container"),
 ("A3",  "80→10 tab characters",              "a 40-entry table of contents flattened"),
 ("A8",  "34 → 1",                            "33 hyperlinks destroyed in the same paragraphs"),
 ("A9",  "TWICE",                                  "cross-reference fields print twice"),
 ("A12", "b=0` runs 0 → 694",                 "apply switches style-borne bold off"),
 ("A17", "`w:rStyle`",                             "character-style bold is invisible to the data contract"),
 ("A18", "FIRST TEXT-BEARING RUN THAT HAS AN EXPLICIT `rPr`", "the template is the deviant run"),
 ("A18", "SPREAD",                                 "a property can spread, not only vanish"),
 ("A14", "MORE THAN ONE property state",           "mixed-state paragraphs are the predicate"),
 ("A11", "hardcoded",                              "apply discards authored spans on subheaders"),
 ("A10", "ONE BOOLEAN",                            "en_runs is read for one boolean on TC paragraphs"),
 ("B1",  "38 ITALIC SPANS",                        "post_process destroyed 38 italic spans, isolated"),
 ("B2",  "statutory",                              "a statutory citation rewritten to an internal one"),
 ("B3",  "content-bearing",                        "punctuation-only edits deleted as noise"),
 ("B7",  "BLANK PAGE",                             "a page break imposed where the source had none"),
 ("D1",  "leading tab runs",                        "signature blocks positioned by tab runs collapse"),
 ("D4",  "11 ideographic spaces",                  "width-bearing padding preserved by count"),
 ("D5",  "three consecutive empty paragraphs",     "a hand-made page break rendered inert"),
 ("D2",  "91.8",                                   "justification stretched a line to 91.8pt gaps"),
 ("E7",  "NO LEXICON ROW EXISTS",                          "the execution line has no row in any language"),
 ("E7",  "Signed at",                              "the rendering is decided"),
 ("E8",  "zero hits",                              "the section symbol is addressed nowhere"),
 ("E13", "6 OF 1,656",                             "Avoid exists in 6 of 1,656 sub-lexicon tables"),
 ("E13", "FIVE SEPARATE MANDATORY INSTRUCTIONS",   "five instructions depend on that field"),
 ("E14", "POINTS AT ROWS THAT DO NOT EXIST",                           "the remediation route points at absent rows"),
 ("F22", "CONTRADICTS ITSELF",                     "rule 3 contradicts itself"),
 ("F23", "FIVE",                                   "the validator count is stated five ways"),
 ("F28", "THE STEP 9 CLOSED LOOP",                            "Step 9's requirement cannot be met"),
 ("F35", "CANNOT BOTH BE OBEYED",                  "two mandatory rules collide on one observable"),
 ("F36", "unreachable",                            "documented exit codes are wrong in both directions"),
 ("F37", "xml.etree.ElementTree",                  "the always-loaded file misdescribes the parser"),
 ("F38", "is and strongly recommended",            "an automated edit broke fourteen sentences"),
 ("F12", "CIRCULAR",                               "the admission gate cannot be operated as written"),
 ("F17", "decimal separator",                      "no rule for numeric locale"),
 ("F20", "TELLS THE OPERATOR TO DESTROY THE WORK",                       "Step 11b tells the operator to strip the revisions"),
 ("F27", "en.strip()",                             "one line destroys boundary tabs and breaks"),
 ("F31", "221-ENTRY",                              "221 furniture phrases are locked in a script"),
 ("G6",  "9 warnings, 9 false positives",          "nine warnings, none real, on one document"),
 ("G7",  "zero true positives",                    "the retention check has no true positives"),
 ("H1",  "four different answers",                 "five components give four answers"),
 ("H4",  "150",                                    "the ratio check skips paragraphs under 150 chars"),
 ("J1",  "unsearchable",                           "ZWSP made a defined term unsearchable"),
 ("K1",  "actively discourages",                   "the wording discourages doubting a gate"),
 ("K3",  "RECEIVES THE DOCUMENT",                  "no failure path addresses the recipient"),
 ("L2",  "146 paragraphs earlier",                 "the detector locked on 146 paragraphs early"),
 ("L4",  "NO STEP 7 CHECK",                        "the diligence audit has no Step 7 check"),
 ("L6",  "SILENTLY DISABLES",                      "the detector disables the only formatting gate"),
 ("L1",  "unreachable by construction",            "Step 7 breaks Step 9"),
 ("S1",  "THREE different wrong answers",          "four scripts, three wrong languages, all CLEAN"),
 ("M1",  "structural blindness entirely intact",   "conversion loss is invisible to every later step"),
 ("N1",  "smartTag",                               "smartTag is a second unenumerated container"),
 ("U1",  "FOURTH INSTANCE",                        "variant drift reached a function signature"),
 ("V1",  "37 rules",                               "the default tree runs the smaller spelling tables"),
 ("V2",  "NOTHING ANYWHERE STATES",                "no parity mechanism is claimed anywhere"),
 ("W1",  "55,466",                                 "the only observed truncation position"),
 ("W2",  "177 OF 198",                             "the row's own headline figure (corrected in-text to 178)"),
 ("W3",  "DOWNGRADED TO A PRINTED WARNING",        "exit 3 is downgraded inside apply"),
 ("W4",  "AFTER THE WORK",                         "the truncation guard runs after the work"),
 ("X1",  "UNARGUABLE and DISCERNING",              "unarguable is not discerning"),
 ("X5",  "CANNOT BE OPERATED AS DOCUMENTED",                     "the praised gate cannot be operated as documented"),
 ("T6",  "stops mattering",                        "fix the defects and batch position stops mattering"),
 ("P4",  "35-paragraph cap is correctly calibrated","the cap must not be raised"),
 ("P11", "refused to reorder",                     "the term-sanity guard turned corruption into a no-op"),
 ("P23", "deterministic",                          "the pipeline is mechanically deterministic"),
 ("P27", "thirteen properties",                    "thirteen construction positives to regress against"),
 ("P16", "zero calques",                           "the no-sub-lexicon document scored 9 with no calques"),
 ("I-8", "ENDPOINTS, NOT READING",                 "our own read gate verifies endpoints"),
]
print("\n=== A1. CLAIM VERIFICATION — every claim against the row it cites ===")
bad = 0
for fid, frag, claim in CLAIMS:
    if fid not in rows:
        print(f"  [FAIL] {fid} is not a register row  ({claim})"); FAIL.append(fid); bad += 1; continue
    if frag not in rows[fid]["text"]:
        print(f"  [FAIL] {fid} does not contain {frag!r}  ({claim})")
        FAIL.append(f"{fid}:{frag}"); bad += 1
print(f"  {len(CLAIMS)} claims checked, {bad} failed, "
      f"{len({c[0] for c in CLAIMS})} distinct rows cited")

# -------------------------------------------- consequence groups (the deliverable's spine)
# Exactly one group per skill finding.  Groups are by CONSEQUENCE, deliberately
# cutting across the register's root-cause clusters.
GROUPS = {
 "1 loses content": """
   A1 A2 A3 A6 A8 A9 A16 A19 N1 C19 C17 C23 C28 C12 M1 B3 B8 A15 J1 C16 C13 C14 F16 F27 E4 S3 C2
   """,
 "2 looks wrong on the page": """
   A4 A5 A7 A10 A11 A12 A13 A14 A17 A18 O1 D1 D2 D3 D4 D5 D6 B1 B7 F7 F13 F19 F22 C20 E9 E12 R1
   """,
 # G10 added 2026-08-12 (branch 5). THIS LIST IS THE SOURCE and §9.1's table is generated
 # from it — a hand-edit to the document alone leaves the two disagreeing, which is exactly
 # how this tool caught the omission.
 "3 says it worked when it did not": """
   C1 C3 C4 C5 C6 C7 C8 C9 C10 C11 C15 C18 C21 C22 C24 C25 C26 C27 G1 G2 G3 G4 G5 G6 G7 G8 G9
   G10 G11 S1 S2 H1 H2 H4 L1 L4 L6 W3 W4 X1 X2 X4 X6
   """,
 "4 hard to keep correct": """
   U1 V1 V2 W1 W2 T1 T2 T3 T4 T5 T6 F21 F23 F32 F36 F37 F38 L2 L3 E1 E2 E3 E5 E6 E10 E11 E13 E14 Q1 Y1
   """,
 "5 the manual is wrong": """
   F1 F2 F3 F4 F5 F6 F8 F9 F10 F11 F12 F14 F15 F17 F18 F20 F28 F29 F30 F31 F33 F34 F35 F39 F40
   E7 E8 K1 K2 K3 H3 L5 B2 B4 B5 B6 X3 X5 Y2 Y3 Y4 F41 F42
   """,
}
# -------------------------------------------- options (a row may need more than one)
OPTIONS = {
 "1 preserve-by-default in apply": """
   A1 A2 A3 A6 A8 A9 A16 A19 N1 C16 C17 C19 F16 F27 D4 T1 T6
   """,
 # G10 added 2026-08-12 (branch 5) — see the note on group 3 above.
 "2 check against the original": """
   C1 C2 C3 C4 C5 C6 C7 C8 C9 C10 C11 C12 C13 C14 C15 C18 C20 C21 C22 C23 C24 C25 C26 C27 C28
   G1 G2 G3 G4 G5 G6 G7 G8 G9 G10 G11 S1 S2 S3 H1 H2 H4 L1 L4 L6 E4 J1 M1 B8 D2 D5 U1 V1
   """,
 "3 say what the formatting is": """
   A4 A5 A7 A10 A11 A12 A13 A14 A17 A18 O1 C13 C20 D6 F7 F13 F19 F22 L2 L3
   """,
 "4 a home for document furniture": """
   E1 E2 E3 E5 E6 E7 E8 E9 E10 E11 E12 E13 E14 F17 F31 F33
   """,
 "5 one authority, one way out, more than one gear": """
   A15 C5 C7 C26 E5 E10 F1 F2 F3 F4 F5 F6 F8 F9 F10 F11 F12 F14 F15 F18 F20 F21 F23 F28 F29 F30
   F31 F32 F33 F34 F35 F36 F37 F38 F41 H1 H2 H3 K1 K2 K3 L5 R1 D3 D5
   """,
 "6 take post_process's authority away": """
   B1 B2 B3 B4 B5 B6 B7 B8 F29 D5 T1 T6
   """,
 "7 one tree instead of two": """
   U1 V1 V2 C21 F34 F8 Q1
   """,
 "8 protect the whole package": """
   W1 W2 W3 W4 F35 Y1 Q1
   """,
 "9 fix the claim, not only the code": """
   X1 X2 X3 X4 X5 X6 C5 C11 K1 J1 L6 F12 C10 F39 F40 F42 Y1 Y2 Y3 Y4
   """,
 # Added 2026-08-05: pass B refuted option 3's claim to FIX the layout findings, so the
 # layout group needs an option of its own -- it is where decision 4 lives.
 "11 layout: see it and say so": """
   D1 D2 D3 D4 D5 D6
   """,
}

# Findings that NO option closes, declared rather than forced into one. A3 used the same
# convention for its seven non-structural rows. T2 technique bleed, T3 attention density,
# T4 state contamination, T5 five refuted batch predictions: all observations about how a
# multi-document session behaves. They are WHY T1 and T6 route to options 1 and 6, and no
# code change closes them.
EVIDENCE_ONLY = "T2 T3 T4 T5".split()

def parse(m):
    out = {}
    for k, v in m.items():
        ids = v.split()
        for i in ids:
            out.setdefault(k, []).append(i)
    return out

def audit(name, mapping, exclusive):
    print(f"\n=== A2. {name} ===")
    seen = Counter()
    for k, ids in mapping.items():
        for i in ids:
            seen[i] += 1
            if i not in rows:
                print(f"  [FAIL] {k}: {i} is not a register row"); FAIL.append(f"{name}:{i}")
            elif i in POSITIVES or i in INSTR:
                print(f"  [FAIL] {k}: {i} is a positive/instrument row, not a finding")
                FAIL.append(f"{name}:{i}")
    for k in mapping:
        print(f"  {k:<52} {len(mapping[k]):>3}")
    print(f"  {'assignments':<52} {sum(len(v) for v in mapping.values()):>3}")
    if not exclusive:
        for i in EVIDENCE_ONLY:
            seen.setdefault(i, 0)
    missing = [f for f in SKILL if f not in seen]
    tail = "" if exclusive else f"  (of which {len(EVIDENCE_ONLY)} are EVIDENCE-ONLY, closed by no option: {' '.join(EVIDENCE_ONLY)})"
    print(f"  [{'FAIL' if missing else 'OK '}] every one of the {len(SKILL)} skill findings accounted for: "
          f"{len(missing)} missing{tail}")
    if missing:
        print(f"        {missing}"); FAIL.append(f"{name}: {len(missing)} unassigned")
    if exclusive:
        dupes = {i: n for i, n in seen.items() if n > 1}
        print(f"  [{'FAIL' if dupes else 'OK '}] exactly one group each: {len(dupes)} duplicated")
        if dupes:
            print(f"        {dupes}"); FAIL.append(f"{name}: {len(dupes)} duplicated")
    else:
        multi = {i: n for i, n in seen.items() if n > 1}
        print(f"  (informational) findings needing more than one option: {len(multi)}")
    return seen

G = parse(GROUPS); O = parse(OPTIONS)
gseen = audit("CONSEQUENCE GROUPS (must be exclusive and complete)", G, True)
oseen = audit("OPTIONS (complete; overlap allowed and expected)", O, False)

# severity per group / per option — the value column the row counts cannot give
def sevmix(ids):
    c = Counter(rows[i]["sev"].split(" ")[0] for i in ids if i in rows)
    return " ".join(f"{k}:{v}" for k, v in
                    sorted(c.items(), key=lambda kv: ["CRITICAL","HIGH","MED","LOW","POS"].index(kv[0])
                           if kv[0] in ["CRITICAL","HIGH","MED","LOW","POS"] else 9))

print("\n=== A3. SEVERITY MIX per consequence group and per option ===")
for k in GROUPS:
    print(f"  {k:<52} {sevmix(G[k])}")
print()
for k in OPTIONS:
    print(f"  {k:<52} {sevmix(O[k])}")

print("\n=== A4. Which options carry the 11 CRITICAL findings ===")
crit = [f for f in SKILL if rows[f]["sev"].startswith("CRITICAL")]
for c in crit:
    owners = [k for k in OPTIONS if c in O[k]]
    print(f"  {c:<5} {rows[c]['sev']:<9} -> {owners}")

# ------------------------------------------------------------------- appendix
if "--appendix" in sys.argv:
    print("\n\n>>>>>>>>>>>>>>> TRACEABILITY APPENDIX (paste target) <<<<<<<<<<<<<<<\n")
    print("| # | consequence group | findings | severity mix |")
    print("|---|---|---|---|")
    for k in GROUPS:
        ids = sorted(G[k], key=lambda f: (re.match(r'[A-Z]+', f).group(), int(re.sub(r'\D', '', f))))
        n, _, rest = k.partition(" ")
        print(f"| {n} | {rest} | {' '.join(ids)} | {sevmix(ids)} |")
    print()
    print("| option | what it is | findings it closes or detects | severity mix |")
    print("|---|---|---|---|")
    for k in OPTIONS:
        ids = sorted(O[k], key=lambda f: (re.match(r'[A-Z]+', f).group(), int(re.sub(r'\D', '', f))))
        n, _, rest = k.partition(" ")
        print(f"| {n} | {rest} | {' '.join(ids)} | {sevmix(ids)} |")

print("\n" + "=" * 72)
print(f"FAILURES: {len(FAIL)}" + (f" -> {FAIL}" if FAIL else "  — PASS"))
sys.exit(1 if FAIL else 0)
