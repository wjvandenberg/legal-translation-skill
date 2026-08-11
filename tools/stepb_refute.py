#!/usr/bin/env python3
"""
Step B — measurement pass 3: VERIFICATION PASSES B and C.

  B (adversarial)  — for each proposal, measure the thing that would REFUTE it.
  C (omission hunt) — what does each proposal break, and what does it leave open.

Every question below is phrased so a measurement can answer it. Prints only.
    uv run python tools/stepb_refute.py
"""
import re
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
reg = (ROOT / "FINDINGS-REGISTER.md").read_text(encoding="utf-8")
a3 = (ROOT / "A3-STRUCTURAL-ANALYSIS.md").read_text(encoding="utf-8")
cmd = (ROOT / "CLAUDE.md").read_text(encoding="utf-8")

ID_RE = re.compile(r"^\|\s*(?:\*\*)?([A-Z]{1,2}-?\d{1,2}[a-z]?)(?:\*\*)?\s*\|")
SECT_RE = re.compile(r"^#{2,3}\s+(.*)$")
rows, order, section = {}, [], None
for line in reg.splitlines():
    m = SECT_RE.match(line)
    if m:
        section = m.group(1).strip(); continue
    m = ID_RE.match(line)
    if m:
        rows[m.group(1)] = dict(section=section, text=line,
                                sev=line.strip().strip("|").split("|")[-1].replace("*", "").strip())
        order.append(m.group(1))
SKILL = [f for f in order if not (rows[f]["section"] or "").startswith(("Positives", "Measurement"))]

def hits(pattern, ids=None, flags=re.I):
    p = re.compile(pattern, flags)
    return [f for f in (ids or SKILL) if p.search(rows[f]["text"])]

print("=" * 78)
print("PASS B — ADVERSARIAL. Each heading is an attempt to REFUTE a proposal.")
print("=" * 78)

print("""
B1. REFUTE option 2 ('check the delivered file against the original'):
    a delivered-vs-original TEXT comparison is CROSS-LANGUAGE and therefore
    not decidable as an equality check. If that is right, C28's prescription
    as literally written cannot be built.""")
c28 = rows["C28"]["text"]
print(f"    C28 says the closing comparison is: "
      f"{'delivered text against the ORIGINAL document' if 'delivered text against the **original**' in c28 else '(see row)'}")
print(f"    C28 mentions 'delivered' {c28.lower().count('delivered')}x and 'extraction' {c28.lower().count('extraction')}x")
print("    The class it cites (SKILL.md multi-w:t truncation) is an EXTRACTION-SIDE loss:")
print(f"      quoted in C28: {'45 paragraphs and 1,547 characters' in c28}")
print("    -> VERDICT: the refutation lands on the WORDING, not on the finding.")
print("       The decidable form is SAME-LANGUAGE: original document.xml text")
print("       vs paragraphs.json['text'].  That is exact, cheap and deterministic.")
print("       The delivered file then needs a STRUCTURAL correspondence check, not a text one.")

print("""
B2. REFUTE option 2's C1 fix ('compare sequences, not sets'):
    a character-exact post-apply comparison is impossible while a MANDATORY
    script is licensed to rewrite the text after the last comparison.""")
pp = hits(r"post_process|post-process")
print(f"    rows naming post_process as altering text: {len(hits(r'post_process', SKILL))}")
print(f"    C15 records one validator giving two opinions on one file : {'1296' in rows['C15']['text']}")
print(f"    B6 records the operator shown a DRIFT error, not the cause : {'DRIFT error' in rows['B6']['text']}")
print(f"    F29 records the mandatory rewrite firing the strict gate    : {'SKILL GATE FIRED' in rows['F29']['text']}")
print("    -> VERDICT: NOT refuted, but option 2 and option 6 are COUPLED.")
print("       A3 §2.7 calls KS6 'independent'. It is not, for KS3's strongest check.")

print("""
B3. REFUTE option 1 ('preserve by default'):
    apply MUST delete text-bearing runs or the English is duplicated, and A9's
    own fix is a DELETION. So 'preserve by default' contradicts itself.""")
print(f"    A9's prescribed fix: {'drop the skeleton when its cached-result run is consumed' in rows['A9']['text']}")
print("    -> VERDICT: the SLOGAN is refuted; the proposal survives with two clauses —")
print("       'rebuild only text; preserve every non-text child; delete only what you")
print("        can prove is now redundant.'  A one-clause version breaks apply.")

print("""
B4. REFUTE option 3 ('compute effective formatting'):
    maybe a cheaper partial cascade resolver is enough.""")
print(f"    A17 records an operator BUILDING one and still losing the terms:")
print(f"      'STILL lost the same two terms' present: {'STILL lost the same two terms' in rows['A17']['text']}")
print("    A12 records removing the off-flags without the computation is worse:")
print(f"      'b=0` runs 0 → 694' present: {'b=0` runs 0 → 694' in rows['A12']['text']}")
print("    -> VERDICT: refutation FAILS by experiment. A partial resolver is measured")
print("       insufficient, and the off-flag removal must land WITH the computation.")

print("""
B5. REFUTE option 3's claim on cluster D ('KS1 closes the layout face'):
    cluster D's own prescribed fixes are FORBIDDEN by the golden rule.""")
for d in ["D1", "D3", "D4", "D5"]:
    t = rows[d]["text"]
    print(f"    {d}: golden rule named as the blocker: "
          f"{bool(re.search(r'golden rule|forbidden|forbids|no compliant fix', t, re.I))}"
          f"   detect-and-disclose proposed: {bool(re.search(r'disclos', t, re.I))}")
print("    -> VERDICT: REFUTED. Cluster D has no FIX in any option. It has a")
print("       DETECTION route (option 2) and a DISCLOSURE route (option 5).")
print("       A3 §6 maps D1–D6 to KS1; that is a cause map, not a fix map.")

print("""
B6. REFUTE option 4 ('furniture matters'): criteria 1 and 2 score 9 everywhere,
    so maybe the lexicons are fine.""")
print(f"    CLAUDE.md states quality/terminology 9 on every graded document: "
      f"{'9 on every graded document' in cmd}")
fur = hits(r"furniture", SKILL)
print(f"    rows naming furniture: {fur}")
print(f"    E7 shipped badly on BOTH its documents: {'twice badly and shipped' in reg}")
print(f"    register states no gate can ever catch a furniture CONVENTION question: "
      f"{'no gate reachable from the current design will ever catch a furniture-convention question' in reg}")
print("    -> VERDICT: NOT refuted. The harm is measured by the READER, and the")
print("       register says it is structurally invisible to every instrument we have.")
print("       Consequence: option 4 cannot be verified by the never-regress gate.")

print("""
B7. REFUTE option 5's 'sanctioned way out': a badly written exception channel is
    a licence to bypass gates, which is the one thing the discipline forbids.""")
print(f"    X3 records the absolutism reading as 'mature' to an outside reader: "
      f"{'That is mature' in rows['X3']['text'] or 'mature' in rows['X3']['text']}")
print(f"    CLAUDE.md forbids weakening anti-drift: {'Do not remove or soften any of them' in cmd}")
print("    -> VERDICT: NOT refuted, but it is the HIGHEST-RISK documentation change")
print("       in the plan, and it must be specified, not merely permitted.")

print("""
B8. REFUTE option 8 (truncation): never observed in twelve runs, so maybe moot.""")
w = ["W1", "W2", "W3", "W4"]
print(f"    severities: {[(i, rows[i]['sev']) for i in w]}")
print(f"    W3/W4 are 'Not observed' by their own text: "
      f"{[bool(re.search(r'[Nn]ot observed', rows[i]['text'])) for i in w]}")
print(f"    W1 has an OBSERVED cut position (55,466): {'55,466' in rows['W1']['text']}")
print(f"    charter names it goal (iv): {'(iv) Minimise install-truncation risk' in cmd}")
print("    -> VERDICT: NOT refuted. W1 is observed; W3/W4 are static code facts that")
print("       need no observation. But they are PREDICTIONS as to consequence.")

print("""
B9. REFUTE the rebuild: A3 §2.8 prices 'a rebuild' as replacing the paragraph
    data contract — which is option 3, not a rebuild.""")
m = re.search(r"\*\*What a genuine \"leap\" would replace is (.*?)\*\*", a3, re.S)
print(f"    A3 §2.8's 'genuine leap' = {m.group(1).strip()[:90]!r}..." if m else "    (not found)")
print(f"    A3 says it KEEPS the golden rule, the 11 steps and every gate: "
      f"{'It keeps the golden rule, keeps the 11 steps, keeps every gate' in a3}")
print(f"    A3 says the golden rule 'should not be on the table': "
      f"{'should not be on the table' in a3}")
print("    -> VERDICT: A3 never prices a TRUE rebuild. What it calls a rebuild is")
print("       option 3 at full scope. A true rebuild has to be priced here.")

print("\n" + "=" * 78)
print("PASS C — OMISSION HUNT. What breaks, and what is left open.")
print("=" * 78)

print("""
C1. THE BIG ONE: option 2 makes gates able to FAIL. How many findings have NO
    compliant repair today?  Turning on a discerning gate before the repair
    exists converts a silent defect into an unresolvable BLOCK.""")
noremedy = hits(r"no (?:compliant|sanctioned|non-lossy) (?:fix|repair|route|option|lever|alternative)"
                r"|no remedy (?:exists|available)|NO sanctioned repair|no lever|not fixable from the input"
                r"|cannot work|no compliant path")
print(f"    {len(noremedy)} rows say so in terms: {noremedy}")
loops = hits(r"closed loop", SKILL)
print(f"    plus the closed loops already recorded: {[i for i in loops if i.startswith('F')]}")
print("    -> CONSEQUENCE, and it is a SEQUENCING FACT not a preference:")
print("       option 2 must ship WITH cluster K's scope rule and a sanctioned-exception")
print("       channel (option 5's cheap half), or the pipeline deadlocks on real documents.")

print("""
C2. What does the register itself say NO gate can see?  These are the rows a
    detection-only option converts from invisible to visible — and no further.""")
blind = hits(r"no gate|nothing (?:noticed|looked|compares|checks)|invisible to every gate"
             r"|every gate reported PASS|reported PASS|printed CLEAN|all (?:three|five) reported PASS")
print(f"    {len(blind)} rows name a gate that passed or could not see it")
print(f"    {blind}")

print("""
C3. Which findings does NOTHING in the option list close?  (omission check
    against the nine options — run stepb_verify.py for the assignment proof.)""")
print("    stepb_verify.py asserts 0 unassigned. The residual risk is a row assigned")
print("    to an option that would not actually close it — checked case by case in")
print("    STEP-B-ANALYSIS.md's 'what it does NOT fix' column.")

print("""
C4. Is there a register row for the BLIND REVIEW's packaging findings that never
    became rows — no version identity, no manifest, no dependency declaration?""")
for term in ["manifest", "version identity", "dependency declaration", "VERSION", "CHANGELOG"]:
    ids = hits(re.escape(term))
    print(f"    rows mentioning {term!r}: {ids}")
print("    -> the comparison's §2.3 lists J47/J48/J49/J08/J09/J54 (no version field,")
print("       no manifest, no dependency declaration, missing scope slots) and §8.2 did")
print("       NOT recommend rows for them. So they are in NO register row.")
print("       *** That is an OMISSION in the evidence base, not in this analysis. ***")
print("       They belong to phase 5 packaging, and W2's coverage fix needs the manifest.")

print("""
C5. Runtime: is there a register row for '25 minutes of fixed overhead'?""")
print(f"    rows mentioning 'fixed overhead' or '35 minutes': {hits(r'fixed overhead|35 minutes')}")
print("    -> only H3 carries a measured cost (35 min / 28 commands for 11 paragraphs).")
print("       The decomposition is an A3 measurement, not a register row. Cite A3 §3.4.")

print("""
C6. The positives a fix could regress. How many positives, and which are about
    CONSTRUCTION rather than behaviour?""")
pos = [f for f in order if (rows[f]["section"] or "").startswith("Positives")]
print(f"    {len(pos)} positives; P27 is the only construction row: "
      f"{'thirteen properties' in rows['P27']['text']}")
print(f"    P11 (term-sanity guard) must survive the cluster-L fix: "
      f"{'do not weaken it when cluster L is fixed' in rows['P11']['text']}")
print(f"    P4/P10/P18 all say the 35-paragraph cap must not be raised.")

print("""
C7. Do any two options touch the SAME FILE, so that they cannot be merged
    independently without a conflict?""")
files = {
 "option 1": ["apply_translations_textmatch.py", "repack_docx.py"],
 "option 2": ["validate_apply.py", "quality_check.py", "verify_diligence.py", "repack_docx.py",
              "validate_translations.py", "extract_paragraphs.py", "(new gate script)"],
 "option 3": ["extract_paragraphs.py", "apply_translations_textmatch.py", "04-translate.md"],
 "option 6": ["post_process.py"],
 "option 7": ["post_process.py", "quality_check.py", "lexicon_compliance.py", "SKILL.md",
              "references/general-legal.md", "sub-lexicons/*"],
 "option 8": ["apply_translations_textmatch.py", "quality_check.py", "(all 198 files)"],
}
seen = Counter()
for o, fs in files.items():
    for f in fs:
        seen[f] += 1
for f, n in seen.most_common():
    if n > 1:
        who = [o for o, fs in files.items() if f in fs]
        print(f"    {f:<38} touched by {n}: {who}")
print("    -> apply_translations_textmatch.py is touched by options 1, 3 and 8;")
print("       repack_docx.py by 1 and 2; quality_check.py by 2, 7 and 8.")
print("       Merge order therefore matters even though the changes are logically disjoint.")
print("=" * 78)
