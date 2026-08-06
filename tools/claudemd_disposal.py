# -*- coding: utf-8 -*-
"""DISPOSAL CHECK — was anything in the old CLAUDE.md silently dropped?

The audit gate's rule 4: "HUNT OMISSIONS, NOT ONLY ERRORS. Walk the evidence row by row and
confirm each row is either accounted for or explicitly recorded as out of scope. State the
arithmetic; if it does not reconcile, the work is not done."

Built on the pattern of `a4_report_disposal.py`, which walked the blind desk review's four
own lists and found three items that had been disposed of nowhere.

WHAT IT DOES. Every substantive block of `temp/CLAUDE.md.pre-overhaul` is listed below with
a phrase that could only appear if the thing is actually carried, and the check reports which
of the four destinations carries it: the rewritten `CLAUDE.md`, `OPUS-5-MIGRATION.md`,
`DECISIONS-LOG.md`, or the build plan itself. Anything carried nowhere is either a real omission or a deliberate drop,
and a deliberate drop must be declared HERE, with its reason, rather than discovered later.

NEVER A TWO-WORD NEEDLE. Every needle is a phrase. Matching is whitespace- and
emphasis-normalised, because six defects in this project came from comparisons that were not.

    uv run python temp/claudemd_disposal.py
"""
import io
import re
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent


def norm(t):
    t = t.translate(str.maketrans({"’": "'", "‘": "'", "“": '"',
                                   "”": '"', "—": "-", "–": "-"}))
    return re.sub(r"\s+", " ", re.sub(r"[*`_]", "", t)).lower()


OLD = norm((ROOT / "temp" / "CLAUDE.md.pre-overhaul").read_text(encoding="utf-8"))
DEST = {
    "CLAUDE": norm((ROOT / "CLAUDE.md").read_text(encoding="utf-8")),
    "OPUS5": norm((ROOT / "OPUS-5-MIGRATION.md").read_text(encoding="utf-8")),
    "DECIS": norm((ROOT / "DECISIONS-LOG.md").read_text(encoding="utf-8")),
    # STEP-B-ANALYSIS.md is a legitimate destination too: the charter deliberately handed
    # its fix-scoping cautions to the build plan, and stepb_harvest.py proves all eight
    # arrived. Omitting it from this list reported four of them as lost.
    "STEPB": norm((ROOT / "STEP-B-ANALYSIS.md").read_text(encoding="utf-8")),
}

# (old section, what it is, phrase that proves it is carried, expected destination)
ITEMS = [
 # ---- front matter and charter §1 -------------------------------------------------
 ("opening", "the skill's identity and quality target", "magic-circle law firm", "CLAUDE"),
 ("read first", "the register is the evidence base", "the fastest way to understand what the project has learned", "CLAUDE"),
 ("read first", "the private folder must be read before confidentiality work",
  "before anything touching confidentiality, packaging or publication", "CLAUDE"),
 ("read first", "run the register validator before and after editing it",
  "before editing findings-register.md, and after", "CLAUDE"),
 ("talk to me", "plain layman's terms and define each term once",
  "define it in one plain sentence", "CLAUDE"),
 ("talk to me", "number your questions", "number your questions", "CLAUDE"),
 ("§1", "who has the problem", "lawyers and deal teams who receive a legal document", "CLAUDE"),
 ("§1", "what machine translation gets wrong", "settled term of art", "CLAUDE"),
 ("§1", "the eleven-step pipeline and text-matching", "text-matches", "CLAUDE"),
 ("§1", "the published feature list", "tracked changes read correctly when accepted", "CLAUDE"),
 ("§1", "the two measured feature claims", "others translate very well too", "CLAUDE"),
 ("§1", "distribution is public; strangers read every file", "strangers will read every file", "CLAUDE"),
 ("§1", "the reverse skill is out of scope", "do not design for it", "CLAUDE"),
 ("§1", "the four goals", "minimise install-truncation risk", "CLAUDE"),
 # ---- charter §2, the plan --------------------------------------------------------
 ("§2", "the ownership rule between order and scope", "owns the order", "CLAUDE"),
 ("§2", "phase 0's decisions are all closed", "grader validated and frozen", "CLAUDE"),
 ("§2", "the pre-git-init sequence is not negotiable", "not negotiable", "CLAUDE"),
 ("§2", "branch 1 commits both trees unmodified", "both published trees unmodified", "CLAUDE"),
 ("§2", "branch 2 is half the never-regress instrument", "half the never-regress instrument", "CLAUDE"),
 ("§2", "the public flip needs Wouter's OK at the moment of the flip",
  "at the moment of the flip", "CLAUDE"),
 ("§2", "autonomy and the two input points", "exactly two input points", "CLAUDE"),
 ("§2", "autonomy never means self-merging", "autonomy never means self-merging", "CLAUDE"),
 ("§2", "definition of done", "whole-picture review", "CLAUDE"),
 ("§2", "the corpus is probed metadata-only, 3 us / 8 uk", "3 us / 8 uk", "CLAUDE"),
 # ---- charter §3, tech stack ------------------------------------------------------
 ("§3", "anything is acceptable if it works in Cowork", "works well as a skill in claude cowork", "CLAUDE"),
 ("§3", "most users will not be in Claude Code", "most users will not be in claude code", "CLAUDE"),
 ("§3", "no third-party dependencies where avoidable", "no third-party dependencies", "CLAUDE"),
 ("§3", "the dev-host toolchain table", "libreoffice", "CLAUDE"),
 ("§3", "the rendered visual diff is available on this host", "rendered visual diff", "CLAUDE"),
 # ---- charter §4, structure -------------------------------------------------------
 ("§4", "do not reduce the file count for its own sake", "for its own sake", "CLAUDE"),
 ("§4", "the exact byte table for both trees", "3,651,835", "CLAUDE"),
 ("§4", "three files per tree past the observed truncation position", "55,466", "CLAUDE"),
 ("§4", "all eleven structural observations, answered", "host detection enumerates products", "CLAUDE"),
 ("§4", "the runtime and redundancy measurements A3 added", "thirteen", "CLAUDE"),
 # ---- charter §5, method ----------------------------------------------------------
 ("§5", "explore, plan, code, commit for every step", "explore", "CLAUDE"),
 ("§5", "pull requests, not direct merges; squash-and-merge", "squash-and-merge", "CLAUDE"),
 ("§5", "explain git status to Wouter before every commit", "explain it to wouter", "CLAUDE"),
 ("§5", "the only real test is translating; corpus outside the tree", "outside the repo", "CLAUDE"),
 ("§5", "grade every output and work the grade up", "against the frozen v3 baseline", "CLAUDE"),
 ("§5", "the final check is a rendered visual diff of BOTH documents", "both documents must be rendered", "CLAUDE"),
 ("§5", "behavioural-equivalence discipline: sha-256 and byte-compare", "sha-256", "CLAUDE"),
 ("§5", "the smoke suite does not exist on disk", "does not exist", "CLAUDE"),
 ("§5", "a gate firing is the script doing its job", "gate firing is the script doing its job", "CLAUDE"),
 ("§5", "never work around a gate", "never work around a gate", "CLAUDE"),
 ("§5", "fidelity wins over a linter", "fidelity wins", "CLAUDE"),
 ("§5", "a gate can be wrong in scope, and nothing says so", "wrong in scope", "CLAUDE"),
 ("§5", "script-integrity failure means a corrupted install", "corrupted install", "CLAUDE"),
 ("§5", "no changelog inside the archive, ever", "no changelog inside the archive", "CLAUDE"),
 ("§5", "anti-drift safeguards are load-bearing", "anti-drift safeguards are load-bearing", "CLAUDE"),
 ("§5", "keep the eleven-step structure and gate nomenclature", "gate nomenclature", "CLAUDE"),
 # ---- confidentiality -------------------------------------------------------------
 ("confid", "treat every file as world-readable from the moment it is committed",
  "world-readable from the moment it is committed", "CLAUDE"),
 ("confid", "no client or counterparty names, ever", "no client or counterparty names, ever", "CLAUDE"),
 ("confid", "enumerating the names here would publish what the rule protects",
  "would publish exactly what the rule protects", "CLAUDE"),
 ("confid", "no real-document examples; anonymising still leaks the shape",
  "still leaks its shape", "CLAUDE"),
 ("confid", "renaming is not enough", "renaming is not enough", "CLAUDE"),
 ("confid", "the corpus filenames alone carry counterparty names",
  "filenames alone carry counterparty names", "CLAUDE"),
 ("confid", "a name-based scan is not sufficient on its own",
  "not sufficient on its own", "CLAUDE"),
 ("confid", "genericise commercial terms in committable prose",
  "seven-figure guaranteed amount", "CLAUDE"),
 ("confid", "use \\s+ for every space in a multi-word pattern", "never a literal space", "CLAUDE"),
 ("confid", "every pattern must be tested against the string it was written for",
  "tested against the string it was written for", "CLAUDE"),
 ("confid", "which files may never be committed", "as sensitive as the list", "CLAUDE"),
 # SUPERSEDED BY A BETTER MEASUREMENT, 2026-08-06, not lost: July's "seven scripts are clean
 # and therefore publishable" was a judgement over the scripts that existed then. The charter
 # now carries the probe-measured figure across all of them, and the rule that decides it.
 ("confid", "seven of our scripts are clean and publishable",
  "clean and therefore publishable||69 are clean and 21 hold a real\nstring", "CLAUDE"),
 ("confid", "the location rule", "the location rule", "CLAUDE"),
 ("confid", "the raw log can be maximally detailed because it is never published",
  "maximally detailed", "CLAUDE"),
 ("confid", "the shipped run report must be metadata-only by construction",
  "metadata-only by construction", "CLAUDE"),
 ("confid", "there is no history to scan", "there is no history to scan", "CLAUDE"),
 ("confid", "the two published trees are not known-clean", "not known-clean", "CLAUDE"),
 ("confid", "the scan list needs tightening before it is a gate",
  "a control nobody believes is not a control", "CLAUDE"),
 ("confid", "no credentials in the repo, ever", "no credentials", "CLAUDE"),
 ("confid", ".gitignore is not a security control", "not a security control", "CLAUDE"),
 ("confid", "the only response to a committed secret is to rotate it", "rotate", "CLAUDE"),
 ("confid", "history rewriting needs a force-push and is not a remedy after publication",
  "no longer a remedy", "CLAUDE"),
 ("confid", "shared working folders accumulate unrelated matter",
  "accumulates unrelated matter", "CLAUDE"),
 # ---- repo layout and publication -------------------------------------------------
 ("repo", "one private monorepo, both trees, no build step", "no build step", "CLAUDE"),
 ("repo", "the repo name", "legal-translation-skill", "CLAUDE"),
 ("repo", "uk/ IS the publishable tree", "is the publishable tree", "CLAUDE"),
 ("repo", "tools/ and tests/ are siblings, never inside the trees", "are siblings", "CLAUDE"),
 ("repo", "both the US and UK term in every lexicon row", "both the us and the uk term", "CLAUDE"),
 ("repo", "one PR touches both trees", "one pr touches both trees||touches both trees", "CLAUDE"),
 ("repo", "the duplication is not removed, only made hard to forget",
  "makes forgetting hard", "CLAUDE"),
 ("repo", ".gitignore by path, not by extension", "by path, not by file extension||by path, not by", "CLAUDE"),
 ("repo", "package.py excludes README and LICENSE", "excluding", "CLAUDE"),
 ("repo", "publish.py is a plain copy-and-commit, not a subtree", "copy-and-commit", "CLAUDE"),
 ("repo", "three public repos need disambiguating", "which is which", "CLAUDE"),
 ("repo", "branch protection with 0 required approvals", "0 required approvals", "CLAUDE"),
 ("repo", "README from the first commit; it is a product surface", "public front door", "CLAUDE"),
 ("repo", "git bisect needs a cheap deterministic test", "git bisect", "CLAUDE"),
 ("repo", "session restart: read the last commits and the state first", "session restart", "CLAUDE"),
 ("repo", "inherited house rules", "never delete files you didn't create", "CLAUDE"),
 # ---- known defect classes --------------------------------------------------------
 ("defects", "bold reaches a run three ways", "character style", "CLAUDE"),
 ("defects", "the signature block is four mechanisms on eight lines", "eight lines", "CLAUDE"),
 ("defects", "tracked changes in six of eleven documents", "six of eleven", "CLAUDE"),
 ("defects", "truncation detection was never extended past scripts/",
  "never extended past", "CLAUDE"),
 ("defects", "cluster A is two independent failures", "two independent failures", "CLAUDE"),
 ("defects", "form is preserved as counts and flags, never as effects",
  "counts and flags, never as effects", "CLAUDE"),
 ("defects", "the token-set gate sentence", "compares token sets", "CLAUDE"),
 ("defects", "document furniture is a defect class", "document furniture", "CLAUDE"),
 ("defects", "conversion loss at step 1 is invisible to every gate", "conversion", "CLAUDE"),
 ("defects", "convert with Word for evidence and LibreOffice for user reality",
  "the comparison is the test||is the test", "CLAUDE"),
 # ---- OOXML hard rules (all ten) --------------------------------------------------
 ("ooxml", "never use ElementTree to write OOXML", "elementtree", "CLAUDE"),
 ("ooxml", "never let an XML regex cross an element boundary", "cross an element boundary", "CLAUDE"),
 ("ooxml", "the 464-highlight incident", "464", "CLAUDE"),
 ("ooxml", "never match w:t loosely", "w:t(?:", "CLAUDE"),
 ("ooxml", "w:b val=0 means bold OFF", "means bold off", "CLAUDE"),
 ("ooxml", "count tab characters separately from tab stops", "separately from tab stops", "CLAUDE"),
 ("ooxml", "table-nested paragraphs are first-class", "first-class", "CLAUDE"),
 ("ooxml", "text-matching not index-matching; the 577/564 drift", "577", "CLAUDE"),
 ("ooxml", "the ZWSP hybrid for non-Latin tracked changes", "u+200b", "CLAUDE"),
 ("ooxml", "terminology rewrites must protect multi-word defined terms", "annexs", "CLAUDE"),
 ("ooxml", "upstream PDF conversion is lossy and lies about it", "lossy and lies about it", "CLAUDE"),
 # ---- measuring instruments -------------------------------------------------------
 ("instr", "hold the grader, harness, thinking level and batch mode constant",
  "a moving ruler", "CLAUDE"),
 ("instr", "the grader is frozen at v3 until the verification run", "frozen", "CLAUDE"),
 ("instr", "never score a run property from element counts", "from element counts", "CLAUDE"),
 ("instr", "count auxiliary references, not just parts", "not just aux parts||count auxiliary references", "CLAUDE"),
 ("instr", "compare auxiliary part content, not the inventory", "not the inventory", "CLAUDE"),
 ("instr", "reconcile a tracked-change count drop against coalescing", "coalescing", "CLAUDE"),
 ("instr", "identical pPr is not evidence layout survived", "is not evidence layout survived||layout survived", "CLAUDE"),
 ("instr", "never compare by paragraph index across the definitions block",
  "by paragraph index", "CLAUDE"),
 ("instr", "re-measure, do not re-read", "re-measure, do not re-read", "CLAUDE"),
 ("instr", "the two v4 grader candidates", "invisible-character cap", "OPUS5"),
 ("instr", "the grader's bash paths are Cowork-specific", "bash paths are cowork-specific||bash paths are cowork", "CLAUDE"),
 ("instr", "forensic logging is a primary method; a summary is not a log",
  "a summary is not a log", "CLAUDE"),
 ("instr", "take counts from the analyser, not the narrative", "never from the narrative", "CLAUDE"),
 ("instr", "the two open harness gaps", "verifies endpoints, not reading", "CLAUDE"),
 # ---- corpus ----------------------------------------------------------------------
 # the rule TIGHTENED on 2026-08-06: class and language, never subject matter. The old
 # wording ("language and type") is what the new rule replaced, so the pair is the point.
 ("corpus", "documents are referred to by language and type only",
  "by language and type||by instrument class and\nlanguage only", "CLAUDE"),
 ("corpus", "D06 is the only true legacy binary .doc", "legacy binary", "CLAUDE"),
 ("corpus", "no Symbol or Wingdings runs anywhere", "wingdings", "CLAUDE"),
 ("corpus", "D03 is the only language with no sub-lexicon", "no sub-lexicon", "CLAUDE"),
 ("corpus", "the variant-assignment principle", "hard technical paths run on uk", "CLAUDE"),
 # ---- A1/A2 results ---------------------------------------------------------------
 ("a1a2", "the twelve-row grade table", "9.3", "CLAUDE"),
 ("a1a2", "the D01/D10 simplicity caveat", "simplicity caveat", "CLAUDE"),
 ("a1a2", "script time 0-1%, model time 99-100%", "0–1%", "CLAUDE"),
 ("a1a2", "the runtime formula", "2.4 seconds a paragraph", "CLAUDE"),
 ("a1a2", "the batch cap is an attention cap", "attention cap", "CLAUDE"),
 ("a1a2", "translation quality is not the problem", "translation quality is not the problem", "CLAUDE"),
 ("a1a2", "the rendered visual diff is the primary instrument", "primary instrument", "CLAUDE"),
 ("a1a2", "the pipeline has silently destroyed legally material content",
  "silently destroyed legally material content", "CLAUDE"),
 ("a1a2", "the batch arm policed less rather than translating worse",
  "policed the pipeline less||degrades the policing", "CLAUDE"),
 ("a1a2", "mechanically identical, linguistically 40% different", "40%", "CLAUDE"),
 ("a1a2", "the two-tier never-regress plan", "two tiers", "CLAUDE"),
 ("a1a2", "efficiency is subordinate to never-regress", "strictly subordinate", "CLAUDE"),
 # ---- Opus 5 ----------------------------------------------------------------------
 ("opus5", "the platform facts", "128k max output", "OPUS5"),
 ("opus5", "goal (iii)'s observation requirement is already satisfied by A1",
  "already satisfied", "OPUS5"),
 ("opus5", "the batch cap stays", "35-paragraph cap stays||35-paragraph batch cap stays", "OPUS5"),
 ("opus5", "the two branches", "opus5-context-audit", "OPUS5"),
 ("opus5", "per-step effort is probably not worth it", "probably not worth it", "OPUS5"),
 ("opus5", "keep the no-sub-agents rule", "no-sub-agents", "CLAUDE"),
 ("opus5", "do these after the structural fixes; attribution", "attribution impossible", "CLAUDE"),
 ("opus5", "every A1 run was at extra, so the baseline is a lower bound", "lower bound", "OPUS5"),
 ("opus5", "the specification contradicts itself, so judgement is needed",
  "specification contradicts itself", "OPUS5"),
 ("opus5", "the four-point experiment design", "three-point read", "OPUS5"),
 ("opus5", "use D09, avoid D11", "avoid d11", "OPUS5"),
 ("opus5", "score the arms on the judgement calls, not the grade",
  "judgement calls", "OPUS5"),
 ("opus5", "the README will say run at maximum thinking regardless",
  "run at maximum thinking", "OPUS5"),
 ("opus5", "a published skill cannot set its own effort", "cannot set its own effort", "OPUS5"),
 ("opus5", "step C reproduces the configuration", "reproduce the configuration", "OPUS5"),
 ("opus5", "compaction behaviour is host-specific", "host-specific", "OPUS5"),
 # ---- observability ---------------------------------------------------------------
 ("observ", "Sentry and PostHog are not viable and why", "sentry", "DECIS"),
 ("observ", "build a local, opt-in, metadata-only run report", "metadata-only run report", "DECIS"),
 # ---- roadmap scope ---------------------------------------------------------------
 ("roadmap", "the docs/history changelog archive", "docs/history", "CLAUDE"),
 ("roadmap", "synthetic fixtures only, including Symbol and a legacy .doc", "synthetic", "CLAUDE"),
 ("roadmap", "the deterministic fixture byte-comparison", "byte-comparison", "CLAUDE"),
 ("roadmap", "reconciling is an editorial adjudication, not a merge",
  "editorial adjudication", "CLAUDE"),
 ("roadmap", "step B's decision criterion: quality first", "quality is the main driver", "CLAUDE"),
 ("roadmap", "the rebuild default and the decomposition tension", "merge-sized steps", "CLAUDE"),
 ("roadmap", "three verification passes by three different methods", "three different methods", "DECIS"),
 ("roadmap", "cost figures are inferences and must be labelled", "inference", "DECIS"),
 ("roadmap", "group by consequence, not by cluster letter", "consequence", "DECIS"),
 ("roadmap", "four columns per option including what it breaks",
  "what it would break", "DECIS"),
 ("roadmap", "instruments before fixes", "instrument branches and the fix branches follow||instruments come before the fixes", "CLAUDE"),
 ("roadmap", "the frozen-intermediate trick", "freeze the translated intermediate", "CLAUDE"),
 ("roadmap", "two fixture tiers, synthetic committable and real never", "never", "CLAUDE"),
 ("roadmap", "negative fixtures are mandatory",
  "negative fixtures are mandatory||negative test inputs are mandatory", "CLAUDE"),
 ("roadmap", "post_process needs its own branch", "tidy-up script", "CLAUDE"),
 ("roadmap", "do not auto-convert numbers in a script", "auto-convert numbers in a script", "CLAUDE"),
 ("roadmap", "the definitions detector needs replacing, not patching",
  "replacing", "CLAUDE"),
 ("roadmap", "the remnant net degrades to a confident wrong answer",
  "confident wrong answer", "CLAUDE"),
 ("roadmap", "scope the date rule; do not edit another party's redline",
  "except dates inside another party||authored by another party", "STEPB"),
 ("roadmap", "no renumbering of the steps", "sequence it last||no renumbering of the steps", "CLAUDE"),
 ("roadmap", "cluster K is the cheapest fix in the project", "cheapest fix in the project", "CLAUDE"),
 ("roadmap", "step D consolidates before any packaging", "does not open with packaging", "CLAUDE"),
 ("roadmap", "never make a repo public without Wouter's explicit OK",
  "without wouter's explicit ok", "CLAUDE"),
 # ---- review protocol -------------------------------------------------------------
 ("review", "the loop, and opening the next pair immediately", "before analysing anything", "CLAUDE"),
 ("review", "the three-way triage", "structurally could not", "CLAUDE"),
 ("review", "two artefacts, two rules; only sanitised conclusions are committed",
  "sanitised conclusions", "CLAUDE"),
 ("review", "order is ascending complexity", "ascending complexity", "CLAUDE"),
 ("review", "the D03/D03B pair is deliberately not blind", "deliberately not blind", "CLAUDE"),
 ("review", "the blind rule and the tool that inherits it",
  "inherits the blindness requirement", "CLAUDE"),
 ("review", "what Claude must not do", "defend the grade", "CLAUDE"),
 # ---- handoffs: the parts that are not status -------------------------------------
 ("handoff", "never work from a précis", "never work from a précis", "CLAUDE"),
 ("handoff", "a check that passes on a coincidence is worse than no check",
  "passes on a coincidence", "DECIS"),
 ("handoff", "a3_md_tables has caught defects nothing else can see",
  "a3_md_tables", "CLAUDE"),
 ("handoff", "the seven verification suites in temp/", "stepb_metacheck", "CLAUDE"),
 ("handoff", "the five things a new session most needs to know",
  "this is not a formatting project", "CLAUDE"),
 ("handoff", "two more gate mechanisms sit in the same family",
  "discards its own verdict", "CLAUDE"),
 ("handoff", "the blindness lessons: deny stops a call, not a description",
  "not the tool being described", "DECIS"),
 ("handoff", "absence by location beat policing by rule", "absence by location", "DECIS"),
 ("handoff", "what A3 concluded in six lines", "one gear", "CLAUDE"),
 ("handoff", "the six keystones", "keystones", "CLAUDE"),
 ("handoff", "the A4 documents live in the private folder", "nothing about a4 is in this repo||the whole a4 set", "CLAUDE"),
 ("handoff", "the twelve private A4 tools", "twelve", "CLAUDE"),
 ("handoff", "the files-and-locations table", "the 11-document corpus", "CLAUDE"),
 ("handoff", "the latest published version", "rev44", "CLAUDE"),
 ("handoff", "the spot-check failed one of its two pairs", "failed one of its two pairs", "CLAUDE"),
 ("handoff", "the adjudications are still unreviewed by Wouter", "adjudications", "CLAUDE"),
 # ---- the audit gate --------------------------------------------------------------
 ("audit", "Wouter's standing requirement, in his words", "triple check", "CLAUDE"),
 ("audit", "it has found real errors every time", "every time it has been made", "CLAUDE"),
 ("audit", "check every citation against the file it cites", "open that file", "CLAUDE"),
 ("audit", "audit the bookkeeping separately from the prose", "separately from the prose", "CLAUDE"),
 ("audit", "hunt omissions, state the arithmetic", "state the arithmetic", "CLAUDE"),
 ("audit", "state confidence per claim; measured versus inferred", "measured from inferred", "CLAUDE"),
 ("audit", "an audit reporting nothing was too shallow", "too shallow", "CLAUDE"),
 ("audit", "the grep-counts-a-description trap", "merely describes it", "CLAUDE"),
]

# Deliberate drops, declared HERE with a reason rather than discovered later.
DROPPED = [
 ("the phase 0-5 numbering and the DONE/LEFT tables",
  "superseded: §3 is four steps of future work, §2.3 holds what was done"),
 ("the indicative branch list and the six-keystone scoping",
  "superseded by STEP-B-ANALYSIS.md, which the standing prescription check proves carries "
  "every charter hand-off (63 of 63)"),
 ("the fourteen-item 'scoping cautions' list",
  "there were eight, not fourteen, and stepb_harvest.py tracks all eight by id (SC1-SC8)"),
 ("the per-strand A1/A2/A3/A4 status tables",
  "all five strands are complete; §2.3 records what each produced"),
 ("THE AGREED SHAPE OF THE STEP B ANALYSIS (a 140-line brief)",
  "it was a brief for a session that has run; its four decisions are in DECISIONS-LOG.md "
  "and its output is STEP-B-ANALYSIS.md"),
 ("the A4 design narrative and the blindness protocol",
  "the experiment is over and the rules are spent; the two lessons that outlived them are "
  "in DECISIONS-LOG.md"),
 ("the 2026-08-04 handoff",
  "§7 carries one handoff by rule; its non-status content is disposed of above"),
 ("the eight-row 'files and locations' table",
  "replaced by §1.3 (the document set) and §6.5 (what never enters the repo), which "
  "between them name every location without the absolute paths the old table carried"),
]

print("=" * 96)
print("DISPOSAL OF THE OLD CLAUDE.md — every substantive block, and where it went")
print("=" * 96)

nowhere, wrong_home, carried = [], [], 0
by_dest = {k: 0 for k in DEST}
for sec, what, needle, expect in ITEMS:
    old_n, _, new_n = needle.partition("||")
    n, n2 = norm(old_n), norm(new_n or old_n)
    if n not in OLD:
        print(f"  [SKIP] {sec:<8} needle not in the OLD file either: {what}")
        continue
    homes = [k for k, v in DEST.items() if n2 in v]
    if not homes:
        nowhere.append((sec, what, needle))
        print(f"  [LOST] {sec:<8} {what}")
    else:
        carried += 1
        for h in homes:
            by_dest[h] += 1
        if expect not in homes:
            wrong_home.append((sec, what, expect, homes))

print()
print(f"  {len(ITEMS)} substantive items walked")
print(f"  carried: {carried}    carried NOWHERE: {len(nowhere)}")
print(f"  by destination (an item may be carried in more than one): {by_dest}")
if wrong_home:
    print()
    print("  carried, but not where this check expected — read each, they are not failures:")
    for sec, what, expect, homes in wrong_home:
        print(f"    {sec:<8} {what[:58]:<58} expected {expect}, found {homes}")

print()
print("=" * 96)
print("DELIBERATELY DROPPED — declared, not discovered")
print("=" * 96)
for what, why in DROPPED:
    print(f"  - {what}\n      because: {why}")

print()
print("=" * 96)
print(f"RESULT: {len(nowhere)} item(s) carried nowhere, {len(DROPPED)} declared drop(s)")
print("=" * 96)
sys.exit(1 if nowhere else 0)
