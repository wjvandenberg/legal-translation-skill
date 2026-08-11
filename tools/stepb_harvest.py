#!/usr/bin/env python3
"""
STEP B — THE PRESCRIPTION CHECK (permanent).

Wouter, 2026-08-05: "Add the prescription check to the permanent audit."

WHY IT EXISTS. Every earlier completeness test measured ASSIGNMENT -- that each of the 160
findings sits in an option. None measured PRESCRIPTION -- that the analysis says what to DO.
A finding could pass all fourteen checks of the first deep audit and have no fix anywhere.
That is exactly what happened to Option 4's furniture half and to two of Option 5's four gaps.

AND WHY IT MATCHES ON PHRASES, NOT WORDS. The first attempt at this check passed the
definitions-detector item because it searched for the single word "density", which matched
"attention density" and "contract density" -- both unrelated. A keyword check that passes on
a coincidence is worse than none. Every needle below is >= 2 words.

WHERE THE OMISSIONS LIVED. Of 65 row-level "Fix:" clauses in the register, 62 were carried.
The gaps were in material NOT attached to a row: cluster prose, the Clusters table's verdict
column, the charter's scoping cautions, the comparison's commissioned probes, and decisions
recorded in CLAUDE.md that were never assigned to any option.

    uv run python tools/stepb_harvest.py            # check
    uv run python tools/stepb_harvest.py --list      # print the whole harvest
"""
import re
import sys
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
# strip markdown emphasis before flattening: a needle like "auxiliary-part content" must
# match "auxiliary-part *content*" in the source, or the check reports a false MISS.
# NOT underscore in the strip class: it would break identifier needles like definitions_range
FLAT = re.sub(r"\s+", " ", re.sub(r"[*`]", "", doc)).lower()

# (id, source, what the source hands to Step B, [>=2-word needles], owning option)
HARVEST = [
 # ---------------------------------------- CLAUDE.md, Roadmap Phase 3 scoping cautions
 ("SC1", "charter", "post_process needs its own branch",
  ["tidy-up script's authority"], "6"),
 ("SC2", "charter", "do NOT auto-convert numbers in a script - a rule in Step 4 and a report, not a transform",
  ["not a transform", "auto-convert numbers", "blanket regex"], "4"),
 ("SC3", "charter", "the definitions detector needs REPLACING, not patching; and it has TWO consumers",
  ["replacing, not patching", "two consumers"], "3"),
 ("SC4", "charter", "conversion fidelity drops in priority; the probe's own method must compare aux CONTENT",
  ["auxiliary-part content", "aux part content"], "2"),
 ("SC5", "charter", "the remnant net degrades to a confident wrong answer; refuse to print CLEAN",
  ["confident wrong answer", "refuse to print clean", "refuses to print clean"], "2"),
 ("SC6", "charter", "scope the date rule to dates the translation introduces; except another party's tracked insertions",
  ["another party's tracked insertion", "dates the translation introduces"], "5"),
 ("SC7", "charter", "step taxonomy: reassess, sequence LAST, cheap version first",
  ["no renumbering of the steps"], "5"),
 ("SC8", "charter", "cluster K is the cheapest fix in the project",
  ["cheapest fix in the project"], "5"),
 # ---------------------------------------- CLAUDE.md, decided items never assigned to an option
 ("CM1", "charter", "OBSERVABILITY: build a local, opt-in, metadata-only run report in the workdir",
  ["metadata-only run report", "file manifest"], "8"),  # NOT "run report": it coincides with
  # the prose explaining that observability-as-a-service was ruled out. A two-word needle is
  # not automatically safe -- it must be a phrase that can only appear if the item is CARRIED.
 ("CM2", "charter", "CONFIDENTIALITY: a pass to replace real-document-derived examples with synthetic ones "
                    "belongs in the structural review; renaming is not enough",
  ["real-document-derived example", "synthetic example", "renaming is not enough"], "9"),
 ("CM3", "charter", "goal (iii) Opus 5 is phase 4, NOT Step B - the analysis must say it is out of scope",
  ["out of scope", "opus 5"], "-"),
 ("CM4", "charter", "the shipped run report must be metadata-only BY CONSTRUCTION - never document text",
  ["metadata-only by construction"], "8"),
 # ---------------------------------------- A3 hand-offs
 ("A3a", "A3", "'Extract a shared library' is an obvious response and it is a STEP B DECISION",
  ["shared library"], "-"),
 ("A3b", "A3", "the parity check must cover script string literals, function SIGNATURES and rule-table LENGTHS",
  ["function signatures", "rule-table lengths"], "7"),
 ("A3c", "A3", "the file-size work is re-motivated: findability and truncation, NOT tokens",
  ["findability", "not tokens", "context is not a constraint"], "8"),
 ("A3d", "A3", "goal (iv) is TWO different pieces of work: the size discipline, and coverage of the 85%",
  ["size discipline", "coverage of the 85"], "8"),
 ("A3e", "A3", "'give it more than one gear' - the runtime answer is the declared-mode change",
  ["more than one gear"], "5"),
 ("A3f", "A3", "do not cut the final validate (10.6% of time, top finding on every document)",
  ["thinning a check", "highest-yield check"], "-"),
 ("A3g", "A3", "do not cut the lexicon reads (5.7%, measured to pay)",
  ["reading fewer dictionaries", "do not cut the lexicon"], "-"),
 ("A3h", "A3", "fixing the register IS the efficiency work; there is no separate efficiency workstream",
  ["no separate efficiency workstream"], "-"),
 ("A3i", "A3", "host detection enumerates products, not capabilities - a doc-only fix, keep the warning text",
  ["host detection", "products, not capabilities"], "5"),
 ("A3j", "A3", "KS1 also closes cluster L's guessing IF the data contract gains a role/definitions_range field",
  ["definitions_range", "declared roles and ranges", "role or a range"], "3"),
 # ---------------------------------------- the comparison's commissioned probes
 # NEEDLE TIGHTENED 2026-08-05: "whether a dictionary row is" coincidence-passed on Option 2's
 # "what it does NOT fix" column — "It cannot see whether a dictionary row is *wrong*" — which is a
 # LIMITATION statement, not the prescription to commission the spot-check. Seventh coincidence-pass
 # logged in this project, and the second inside this very script. The needle must name the probe.
 ("P1", "comparison", "whether the 30,719 lexicon rows are CORRECT - the largest unexamined surface, 68.5% of bytes",
  ["largest unexamined surface", "50 rows per language", "bilingual spot-check"], "4"),
 ("P2", "comparison", "whether any of the 13 gates can fire - one input per gate",
  ["one failing test input per check"], "2"),
 ("P3", "comparison", "Symbol/Wingdings glyphs and graphic-object text - synthetic fixtures",
  ["chart with a title", "symbol-font"], "1"),
 ("P4", "comparison", "password-protected, .docm and size-limit inputs - three synthetic inputs at the admission gate",
  ["password-protected", "input envelope", "accepted-input envelope"], "5"),
 ("P5", "comparison", "install-time behaviour in the host most users use - belongs to Step C",
  ["install-time behaviour", "the host most users"], "8"),
 ("P6", "comparison", "whether the prose REACHES the agent under pressure - 'the central empirical question'",
  ["central empirical question", "step-file reads enforced"], "5"),
 # NEEDLE TIGHTENED 2026-08-05: "both variants" coincidence-passed on Option 7's own cons column
 # ("7b changes delivered output on both variants, so both need re-grading"), which is about
 # re-grading AFTER a change, not about running one document both ways to measure the difference
 # NOW. Sixth coincidence-pass logged in this project; the needle must name the probe.
 ("P7", "comparison", "cross-variant behaviour under execution - one document, both variants, byte-compare",
  ["one document, both variants", "the same document both ways", "run one document under both variants"], "7"),
 ("P8", "comparison", "ADOPT the 13 construction positives as a regression baseline - the register has none",
  ["construction properties", "construction positives"], "-"),
 ("P9", "comparison", "the six legibility rows need the CLAIM fixed as well as the code",
  ["fix the claim"], "9"),
 # ---------------------------------------- register cluster PROSE (not attached to a row)
 ("R1", "register", "cluster L: the DETECTION APPROACH is what is failing; the detector needs REPLACING",
  ["replacing, not patching", "detection approach"], "3"),
 ("R2", "register", "cluster L alternative 1: anchor on the SECTION - heading, outline level, or the DENSITY "
                    "of 'Term means' predicates in a window",
  ["density of", "anchor on the definitions clause"], "3"),
 ("R3", "register", "cluster L alternative 2: let the OPERATOR DECLARE the definitions range in the notes",
  ["declared field in the notes", "let the operator declare"], "3"),
 ("R4", "register", "cluster L: scan for MULTIPLE candidate sections and report every one",
  ["multiple candidate sections"], "3"),
 ("R5", "register", "cluster A: it is TWO independent failures - children/wrappers vs properties, two files",
  ["disjoint from option 1", "two independent failures"], "1"),
 ("R6", "register", "cluster D's unifying rule: a layout DEVICE must be judged on its RENDERED EFFECT",
  ["rendered effect", "rendered position"], "11"),
 ("R7", "register", "cluster D: D4 shows THREE mechanisms co-acting, so fixing D1 alone under-delivers",
  ["four mechanisms", "three mechanisms"], "11"),
 ("R8", "register", "cluster H: source==target wants its own MODE, on the L5 pattern",
  ["variant conversion", "declared by the operator"], "5"),
 ("R9", "register", "cluster S: every language-dependent check must ANNOUNCE it is guessing",
  ["announces that it is guessing", "announce that it is guessing"], "2"),
 ("R10", "register", "cluster T: fix the defects and batch position stops mattering",
  ["batch position stops mattering"], "1"),
 ("R11", "register", "cluster E: a term->file INDEX or an instructed pre-translation grep closes the coverage half",
  ["term index", "pre-translation grep", "cross-lexicon"], "4"),
 ("R12", "register", "R1: ONE decision covering w:lang, themeFontLang, w:author and people.xml together",
  ["language metadata", "people.xml"], "5"),
 ("R13", "register", "L5 as widened: the accepted-input ENVELOPE is never declared",
  ["input envelope", "accepted-input envelope"], "5"),
 ("R14", "register", "C26: demand something POSITION-DEPENDENT - a quoted line at an unpredictable offset",
  ["position-dependent"], "2"),
 ("R15", "register", "D6: when the source uses fixed line height, refuse to emit a LARGER SIZE than the source carried",
  ["larger size than the source", "fixed line height"], "3"),
 ("R16", "register", "P11: the term-sanity guard must SURVIVE the cluster-L fix",
  ["term-sanity guard"], "3"),
 ("R17", "register", "the Clusters table verdict: cluster B needs PER-PASS decisions",
  ["every pass tests"], "6"),
 ("R18", "register", "F31c: the 221-entry script map is a de facto 13th lexicon domain; promote or point at it",
  ["221-entry script", "script phrase map"], "4"),
 ("R19", "register", "E7/E9: two renderings already DECIDED by Wouter - they are settled instructions, not candidates",
  ["already decided", "signed at"], "4"),
 ("R20", "register", "C20: count the source's effective bold/italic spans and compare against the declared count",
  ["span-count check", "span counts"], "2"),

 # ------------------------------- the A4 REPORT itself (added 2026-08-05: the analysis had
 # worked from the comparison, and the report's recommendations/costs/reasoning are not
 # "claims", so the comparison's claim ledger could not have carried them)
 # RESTATED 2026-08-05: the original wording asserted a divergence with this analysis's
 # ranking. That was retracted -- the two lists are drawn from different candidate pools,
 # because the blind review could not run the pipeline and so never saw any content loss.
 # What must be carried is the top-three list AND the reason its comparison is weak.
 ("A4r1", "A4 report", "its top-three list, and WHY comparing it to this ranking is weak: "
                       "its candidate pool excluded every content loss",
  ["three things I would change first", "candidate pool excluded"], "9"),
 ("A4r2", "A4 report", "independent BUILD COST estimates: under an hour / two to three hours / one to two days",
  ["under an hour", "two to three hours", "one to two days"], "-"),
 ("A4r3", "A4 report", "WARN must be DISTINGUISHABLE from PASS: return 2 if strict else 1",
  ["2 if strict else 1", "distinguishable"], "2"),
 ("A4r4", "A4 report", "the central design bet: an operator must trust the prose; anti-drift cannot itself drift",
  ["central design bet", "cannot afford to be the thing that drifts"], "9"),
 ("A4r5", "A4 report", "five of the eleven scores were set by a claim outrunning its mechanism",
  ["five of its eleven scores", "five of the eleven"], "9"),
 ("A4r6", "A4 report", "a generated manifest is cheap and closes most of the distribution criterion",
  ["generated manifest", "half a day"], "8"),
 ("A4r7", "A4 report", "one version identifier to replace the eighteen revNN tokens",
  ["one version identifier", "18 distinct"], "8"),
 ("A4r8", "A4 report", "either bring the cited private rubric into the tree or stop citing it",
  ["stop citing it"], "9"),
 ("A4r9", "A4 report", "describe the three real guards instead of the false lxml claim",
  ["three real guards"], "9"),
 ("A4r10", "A4 report", "soften the calque claim to what the scan does, do not delete it",
  ["softened to what the scan"], "9"),
 ("A3k", "A3", "FINDABILITY: the Common-Pitfalls catalogue is 32.4% of the always-loaded file",
  ["32.4%", "Common-Pitfalls"], "5"),
 ("A4r11", "A4 report", "the self-check depends on a number with no correct answer",
  ["no correct answer"], "5"),
]

def phrase_hits(needles):
    return [n for n in needles if n.lower() in FLAT]

if "--list" in sys.argv:
    print(f"HARVEST: {len(HARVEST)} prescriptions handed to Step B by the four source documents\n")
    for hid, src, what, needles, opt in HARVEST:
        print(f"  {hid:<5} [{src:<10}] (option {opt})  {what}")
    sys.exit(0)

print("=" * 88)
print(f"PRESCRIPTION CHECK — {len(HARVEST)} hand-offs harvested from the four sources")
print("  every needle is a PHRASE of two or more words: single words produce coincidence passes")
print("=" * 88)
missing = []
for hid, src, what, needles, opt in HARVEST:
    hits = phrase_hits(needles)
    if hits:
        print(f"  [OK  ] {hid:<5} opt {opt:<2} {what[:78]}")
    else:
        print(f"  [MISS] {hid:<5} opt {opt:<2} {what[:78]}")
        print(f"                  source: {src} · searched: {needles}")
        missing.append((hid, opt, what))

print()
print("=" * 88)
by_opt = {}
for hid, opt, what in missing:
    by_opt.setdefault(opt, []).append(hid)
print(f"RESULT: {len(HARVEST) - len(missing)} carried, {len(missing)} MISSING")
if missing:
    print("\nmissing, grouped by the option that should carry it:")
    for opt in sorted(by_opt):
        print(f"  option {opt:<3} {' '.join(by_opt[opt])}")
    print("\ndetail:")
    for hid, opt, what in missing:
        print(f"  · {hid} (option {opt}) — {what}")
print("=" * 88)
sys.exit(1 if missing else 0)
