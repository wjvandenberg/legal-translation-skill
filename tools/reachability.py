# -*- coding: utf-8 -*-
"""STATIC REACHABILITY OF THE INSTRUCTION LAYER — STEP-B-ANALYSIS.md §4.1, half one.

§4.1 splits the prose-reachability probe in two and assigns the halves to different places.
Half two is behavioural, needs a run, and belongs at Step C. **Half one is this: static,
no run, and §4.1 calls it "the more actionable half" and puts it in branch 3.**

THE QUESTION IT ANSWERS. Not "does the operator obey the rule" but the prior one: **could the
operator have READ the rule at the moment it had to decide?** The skill's Mandatory Reading
Order forbids reading a step document before arriving at that step. So a rule that governs a
Step 3 decision but is stated only in the Step 4 document is unreachable BY CONSTRUCTION --
the operator meets it after deciding. That is a reachability defect, not a compliance defect,
and no behavioural experiment is needed to find it. The register holds a worked instance that
produced a real wrong decision, later reversed.

    uv run python tools/reachability.py            # both trees
    uv run python tools/reachability.py --tree uk
    uv run python tools/reachability.py --json     # machine-readable, for the tests

Exit codes:  0 = no reachability failure · 1 = a rule is unreachable where it is needed
             · 2 = the instrument could not run (see VOID below)

WHY IT REPORTS A READ COUNT. §5.1: an instrument reporting on an empty set is not a pass.
"0 statements examined" is VOID, never CLEAN, and this exits 2 rather than 0 if it read
nothing -- a control that opened no files must say so.
"""
import io
import json
import re
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parent.parent
TREES = ("uk", "us")

# A normative statement: one the operator is not free to disregard. Deliberately narrow --
# a wide net here produces a candidate list nobody reads, which is the failure mode this
# project has already diagnosed in the skill's own validators.
#
# CASE-INSENSITIVE, and the first version was not. The entry file shouts its rules in caps
# ("You MUST not skim") but the reference layer states them in ordinary prose -- "All dates
# in the English translation must be in full Gregorian form". A case-sensitive needle saw
# the first and was blind to the second, so both arms below ran under-powered and reported
# the shortfall as a clean result. Measured when the convention arm returned 0 homes across
# 177 files for four conventions that are demonstrably in the tree.
NORMATIVE = re.compile(
    r"\b(?:must|never|always|required|mandatory|shall|do not|may not)\b", re.I)

# Step ids in this package are 1..11 with optional letter suffixes: 3b, 4b, 4c, 4d, 1a, 11a.
STEP_REF = re.compile(r"\bStep\s+(\d{1,2}[a-z]?)\b")


def step_key(s):
    """Order step ids: 3 < 3b < 4 < 4b < 4c < 4d < 5 ... < 11 < 11a."""
    m = re.match(r"(\d{1,2})([a-z]?)$", s)
    if not m:
        return (99, "z")
    return (int(m.group(1)), m.group(2))


def reading_order(skill_md):
    """file -> the steps it covers, parsed from the package's OWN Mandatory Reading Order.

    Parsed rather than hardcoded on purpose: a hardcoded map is a second copy of the
    package's claim, and the two would drift. If the package changes its reading order this
    tool must move with it or say it cannot read it.
    """
    out = {}
    block = re.search(r"## Mandatory reading order(.*?)^## ", skill_md,
                      re.S | re.M)
    if not block:
        return out
    for line in block.group(1).splitlines():
        # The dash is NOT always followed directly by "Steps": entry 8 reads
        # "— Pre-repack hooks + Steps 10+11:". The first version of this regex demanded
        # "Steps" immediately and therefore silently dropped the FINAL step document --
        # the one covering repack, validate and delivery, which is precisely where this
        # branch's delivery-notes work lands. It reported "7 files" for a list of 8 and
        # nothing said so. Hence the count assertion in reading_order's caller.
        m = re.match(r"\s*\d+\.\s+`(skill-docs/[^`]+)`\s*[—-]\s*.*?\bSteps?\s+([0-9a-z+ ]+):",
                     line.strip())
        if m:
            out[m.group(1)] = [s.strip() for s in m.group(2).split("+") if s.strip()]
    return out


def pipeline_steps(skill_md):
    """step -> the file that documents it, from the Pipeline overview table."""
    out = {}
    block = re.search(r"## Pipeline overview(.*?)^## ", skill_md, re.S | re.M)
    if not block:
        return out
    for line in block.group(1).splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) >= 4 and re.match(r"^\d{1,2}[a-z]?$", cells[0]):
            f = re.search(r"`(skill-docs/[^`]+)`", cells[-1])
            if f:
                out[cells[0]] = f.group(1)
    return out


def sentences(text):
    """Split on sentence ends and on list-item starts; keep it crude but stable."""
    for para in re.split(r"\n\s*\n", text):
        flat = " ".join(para.split())
        for s in re.split(r"(?<=[.!?])\s+(?=[A-Z*`\[])", flat):
            s = s.strip()
            if s:
                yield s


def analyse(tree):
    root = ROOT / tree
    skill_md = (root / "SKILL.md").read_text(encoding="utf-8")
    order = reading_order(skill_md)
    pipe = pipeline_steps(skill_md)

    findings = []
    read_count = 0

    # THE PARSE MUST COVER EVERY STEP DOCUMENT ON DISK. A regex that quietly matches 7 of 8
    # entries produces an analysis that is wrong in a way no output reveals -- which is what
    # happened, and the missing one was the final step document. Assert the count rather
    # than trust the regex.
    on_disk = {f"skill-docs/{p.name}" for p in (root / "skill-docs").glob("*.md")}
    unparsed = on_disk - set(order)
    if unparsed:
        findings.append({
            "arm": "parse-shortfall", "certain": True, "tree": tree,
            "detail": f"the Mandatory Reading Order parse covered {len(order)} of "
                      f"{len(on_disk)} step documents; missed {', '.join(sorted(unparsed))}"
                      " — the analysis below is INCOMPLETE, not clean",
        })

    # ---- ARM 0: the package states the step->file map TWICE. They must agree. -------
    # Two statements of one map is exactly the "no single authority" shape Option 5 names,
    # so disagreement between them is itself a finding rather than a parsing nuisance.
    for step, doc in sorted(pipe.items(), key=lambda kv: step_key(kv[0])):
        covered = order.get(doc, [])
        if covered and step not in covered:
            findings.append({
                "arm": "map-disagreement", "certain": True, "tree": tree,
                "detail": f"Pipeline overview puts Step {step} in {doc}; the Mandatory "
                          f"Reading Order says that file covers Steps {'+'.join(covered)}",
            })

    # First step at which each file may legitimately be read.
    first_readable = {f: min(steps, key=step_key) for f, steps in order.items() if steps}

    # ---- ARM 1: normative statements that govern a step earlier than their own. -----
    # HEURISTIC. Announces itself as one: many backward references are legitimate
    # remediation ("fix and re-run from Step 5"), so these are CANDIDATES for judgement.
    for doc, first in sorted(first_readable.items(), key=lambda kv: step_key(kv[1])):
        p = root / doc
        if not p.exists():
            continue
        body = p.read_text(encoding="utf-8")
        for s in sentences(body):
            read_count += 1
            if not NORMATIVE.search(s):
                continue
            refs = {r for r in STEP_REF.findall(s)}
            earlier = sorted((r for r in refs if step_key(r) < step_key(first)),
                             key=step_key)
            if earlier:
                # A statement that CITES where the governing rule lives is a pointer, not
                # the rule's home -- the operator reaching it has already met the rule at
                # the earlier step. Learned from the one candidate the first run produced:
                # 06-postprocess cites the Step 4 rule and the rule really is in the Step 4
                # document, so flagging it was a false positive.
                #
                # SUPPRESSED, NOT DROPPED. §5.1: a bounded instrument must say what it set
                # aside, or the reader takes silence for coverage. These are counted and
                # printed, and --show-pointers lists them.
                pointer = bool(POINTER.search(s))
                findings.append({
                    "arm": "pointer" if pointer else "backward-governing",
                    "certain": False, "tree": tree,
                    "doc": doc, "first_readable": first, "governs": earlier,
                    "detail": f"{doc} is first readable at Step {first} but carries a "
                              f"normative statement about Step {', '.join(earlier)}",
                    "text": s[:240],
                })

    # ---- ARM 1b: conventions with more than one home, at different steps. ----------
    # ARM 1 STRUCTURALLY CANNOT FIND THE REGISTER'S OWN WORKED INSTANCE, and saying so is
    # the point of having this arm. The date rule's defect is not a backward reference: the
    # operator meets two misleading statements at Step 3, decides, and meets the governing
    # statement afterwards in the Step 4 document. Nothing in that shape names an earlier
    # step, so Arm 1 is blind to it by construction.
    #
    # The convention list is SOURCED, not invented -- these are the four that
    # STEP-B-ANALYSIS.md §6, Option 5 gap 1 and prescriptions (i) and (ii) name.
    # The reference and sub-lexicon layers are read at Step 3 -- SKILL.md: "You MUST read
    # both at Step 3". They are IN SCOPE for this arm and the first version left them out,
    # which made its silence meaningless: three of the four named conventions live there and
    # nowhere else, so an arm that only read skill-docs/ was guaranteed to find nothing and
    # would have reported that as a clean result.
    layers = dict(first_readable)
    for folder in ("references", "sub-lexicons"):
        for p in sorted((root / folder).glob("*.md")):
            layers[f"{folder}/{p.name}"] = "3"
    coverage = []

    for conv, (pat, _vector) in CONVENTIONS.items():
        homes = {}
        for doc, first in layers.items():
            p = root / doc
            if not p.exists():
                continue
            hits = [s for s in sentences(p.read_text(encoding="utf-8"))
                    if pat.search(s) and NORMATIVE.search(s)]
            if hits:
                homes[doc] = (first, len(hits))
        # SKILL.md is always loaded, so a statement there is reachable everywhere; it is
        # recorded but never makes a convention unreachable.
        sk_hits = [s for s in sentences(skill_md)
                   if pat.search(s) and NORMATIVE.search(s)]
        steps_spread = {v[0] for v in homes.values()}
        # Record the arm's COVERAGE whether or not it found a spread. An arm that ran and
        # found nothing must be distinguishable in the output from an arm that did not run.
        coverage.append((conv, len(homes), sorted(steps_spread, key=step_key), len(sk_hits)))
        if len(homes) > 1 and len(steps_spread) > 1:
            findings.append({
                "arm": "multi-home-convention", "certain": False, "tree": tree,
                "doc": ", ".join(sorted(homes)), "first_readable":
                    min(steps_spread, key=step_key),
                "governs": sorted(steps_spread, key=step_key),
                "detail": f"'{conv}' is stated normatively in {len(homes)} step documents "
                          f"that become readable at different steps "
                          f"({', '.join(sorted(steps_spread, key=step_key))})"
                          f"{f', plus {len(sk_hits)} statement(s) in SKILL.md' if sk_hits else ''}"
                          f" — the operator meets one before the other",
                "text": "; ".join(f"{d} (Step {v[0]}, {v[1]} statement(s))"
                                  for d, v in sorted(homes.items()))[:240],
            })

    # ---- ARM 2: where can a check BLOCK, and is the gate-scope rule readable there? --
    # DECIDABLE, not heuristic. Measure the steps at which a script runs; a script that can
    # exit non-zero can stop the operator there. The rule that says a check can be wrong IN
    # SCOPE has to be readable at every such step -- which only the always-loaded file is.
    blocking_steps = []
    for step, doc in sorted(pipe.items(), key=lambda kv: step_key(kv[0])):
        p = root / doc
        if not p.exists():
            continue
        invoked = set(re.findall(r"\b([a-z_]+\.py)\b", p.read_text(encoding="utf-8")))
        can_block = [s for s in sorted(invoked)
                     if (root / "scripts" / s).exists()
                     and re.search(r"sys\.exit\((?:1|2|3)\)",
                                   (root / "scripts" / s).read_text(encoding="utf-8"))]
        if can_block:
            blocking_steps.append(step)

    # BOTH gate rules are measured, not just the scope rule. Branch 3 added 5a (the check is
    # wrong -- fix it); branch 4 adds 5b (the check is right and no compliant repair exists).
    # They answer different questions at the same moment, so an operator who can reach only
    # one of them is still stuck at a gate, and the arm would have reported PASS.
    rule_homes = {}
    for label, needle in RULES:
        homes = [f for f in ["SKILL.md"] + sorted(order)
                 if (root / f).exists() and needle.search(
                     (root / f).read_text(encoding="utf-8"))]
        rule_homes[label] = homes
        if not homes:
            findings.append({
                "arm": "gate-rule", "certain": True, "tree": tree,
                "blocking_steps": blocking_steps,
                "detail": f"NO file states {label}. A check can block at "
                          f"{len(blocking_steps)} of {len(pipe)} steps and the operator has "
                          "no rule to reach at any of them.",
            })
        elif "SKILL.md" not in homes:
            findings.append({
                "arm": "gate-rule", "certain": True, "tree": tree,
                "blocking_steps": blocking_steps,
                "detail": f"{label} is stated only in {', '.join(homes)}, which is not "
                          f"always loaded. A check can block at {len(blocking_steps)} of "
                          f"{len(pipe)} steps; the rule is unreachable at any step whose "
                          "document has not been read.",
            })

    # The BOUND is reachability of a different kind: the two instructions that tell the
    # operator to keep repairing must each carry it, or the loop is unbounded exactly where
    # the operator meets it. Register row F41 measured ZERO files bounding a repair loop.
    for rel, line in unbounded_repair_sites(root):
        findings.append({
            "arm": "repair-bound", "certain": True, "tree": tree,
            "blocking_steps": blocking_steps,
            "detail": f"{rel}:{line} tells the operator to repeat a repair and never bounds "
                      "it (register F41). The bound must be stated where the loop is, not "
                      "only in the always-loaded file.",
        })

    return findings, read_count, blocking_steps, len(pipe), rule_homes, coverage


# The needle is a PHRASE, not two words. §5.12 rule 6: eleven checks in this project have
# passed for the wrong reason, and every one used a needle short enough to appear by
# accident. "in scope" alone matches ordinary prose about scoping; this cannot.
# Case-insensitive, because the rule is written as a heading ("A check can be wrong IN
# SCOPE") and a substring test against the lower-case form missed it. The tool reported NO
# FILE on a tree that carried the rule -- it failed SAFE, which is the right direction, but
# a needle that only matches one capitalisation is a needle waiting to go quiet.
SCOPE_NEEDLE = re.compile(r"a check can be wrong IN SCOPE", re.I)

# Branch 4's channel. Same needle discipline: a phrase that cannot occur unless the rule is
# actually carried. "no compliant repair" alone appears in the register and in analysis prose,
# so the needle binds it to the instruction that acts on it.
CHANNEL_NEEDLE = re.compile(
    r"the only sanctioned way a repair loop may end other than the check passing", re.I)

RULES = [
    ("that a check can be wrong IN SCOPE (rule 5a)", SCOPE_NEEDLE),
    ("the sanctioned way out when no compliant repair exists (rule 5b)", CHANNEL_NEEDLE),
]

# WHERE THE REPAIR LOOP IS AUTHORED, swept rather than listed.
#
# F41 says "measured across all 198 files: TWO such instructions". Re-derived on branch 4:
# there are FOUR in the shipped prose, not two -- the two F41 names plus a repeat-until-exit-0
# in the always-loaded file's calque pitfall and a re-run-everything remediation at Step 10.
# A hardcoded list of sites would have shipped the same blind spot F41 had, so this SWEEPS:
# every repair-repeat instruction in the tree's prose must carry the bound. A new one added
# later arrives unbounded and fails here.
#
# TWO EXCLUSIONS, DECLARED RATHER THAN SILENT:
#   * `.py` files. Two match -- a docstring describing a script's own internal fixpoint loop
#     ("iterates until a pass produces no change"), which is an algorithm and not an
#     instruction to anyone; and an apply-gate message saying "fix the underlying issue, then
#     re-run", which is a single remediation rather than a loop. Bounding the second is a
#     SCRIPT edit and branch 4 is doc-only; it belongs with branch 5.
#   * The bound text itself quotes "re-run until it passes" to explain what it forbids, so
#     the window below is searched on BOTH sides of a match, not only after it.
REPEAT_UNTIL = re.compile(
    r"(?:re-?run|repeat|iterate|loop)[^.\n]{0,80}?until[^.\n]{0,60}"
    r"(?:exits?\s*0|passe?s?|clean|0\s+issues|green)", re.I)
RERUN_ONCE = re.compile(
    r"fix[^.\n]{0,60},?\s*then re-?run|re-?run\s+Steps?\s+\d[^.\n]{0,40}in order|"
    r"re-?run\s+every\s+mandatory", re.I)
BOUND_NEEDLE = re.compile(
    r"bounded at five attempts|at most five times|five attempts, then stop", re.I)
BOUND_WINDOW = 1500


def unbounded_repair_sites(root):
    """Every repair-repeat instruction in the tree's PROSE that does not carry the bound."""
    out = []
    for p in sorted(root.rglob("*.md")):
        body = p.read_text(encoding="utf-8", errors="replace")
        for pat in (REPEAT_UNTIL, RERUN_ONCE):
            for m in pat.finditer(body):
                lo = max(0, m.start() - BOUND_WINDOW)
                if not BOUND_NEEDLE.search(body, lo, m.end() + BOUND_WINDOW):
                    out.append((p.relative_to(root).as_posix(),
                                body[:m.start()].count("\n") + 1))
    return out

# "(see X in Step 4)" / "as described in Step 4" -- the statement is pointing at the rule's
# home rather than being it.
POINTER = re.compile(r"\b(?:see|described in|set out in|per|under)\b[^.]{0,80}\bStep\s+\d",
                     re.I)

# The four conventions STEP-B-ANALYSIS.md §6 Option 5 names as lacking a single authority:
# gap 1 (statute citation, the date rule, the priority rule) and prescription (ii)
# (language metadata). Sourced from the build plan so the list is auditable rather than
# a set of words somebody thought of.
# EVERY PATTERN CARRIES THE REAL STATEMENT IT WAS WRITTEN FOR, and the self-test below
# asserts it still matches. §5.4 learned this on the leakage scan: a pattern that silently
# stops matching reports CLEAN, and a missed hit is invisible. The first version of this
# table matched NOTHING across 177 files -- four conventions that are all demonstrably in
# the tree -- and printed that as a result. Test vectors are why that cannot recur.
CONVENTIONS = {
    "statute-citation form": (
        re.compile(r"\b(?:statut\w+|legislat\w+|enactment)\b[^.]{0,90}\bcit|"
                   r"\bcit\w+\b[^.]{0,90}\b(?:statute|statutory|legislation|act)\b", re.I),
        "Statutory citations must give the official English translation first."),
    "the date rule": (
        re.compile(r"\bdates?\b[^.]{0,90}\bGregorian\b|\bGregorian\b[^.]{0,90}\bdates?\b|"
                   r"\bdate\s+format\b", re.I),
        "All dates in the English translation must be in full Gregorian (Western) form:"),
    "the lexicon priority rule": (
        re.compile(r"\b(?:cross-language\s+reference|sub-lexicon|lexicon)\b[^.]{0,90}"
                   r"\b(?:wins|overrides?|takes\s+precedence|has\s+priority)\b|"
                   r"\b(?:priority|precedence)\b[^.]{0,90}"
                   r"\b(?:lexicon|sub-lexicon|reference)\b", re.I),
        "When the two appear to disagree, the cross-language reference wins."),
    "language metadata": (
        re.compile(r"\bw:lang\b|\bthemeFontLang\b|"
                   r"\blang(?:uage)?[- ]?(?:attribute|annotation|metadata|tag)s?\b", re.I),
        "The delivered file must carry no w:lang annotations."),
}


def selftest_patterns():
    """Each convention pattern must match the statement it was written for.

    A pattern that matches nothing is not a convention that is absent -- it is a needle
    that is wrong, and the two are indistinguishable from the output. This tells them apart.
    """
    bad = [name for name, (pat, vector) in CONVENTIONS.items() if not pat.search(vector)]
    if bad:
        print("  PATTERN SELF-TEST FAILED — these needles no longer match their own "
              "test vector, so any zero they report is meaningless:")
        for n in bad:
            print(f"    {n}")
        return False
    return True


def main():
    tree_arg = None
    if "--tree" in sys.argv:
        tree_arg = sys.argv[sys.argv.index("--tree") + 1]
    trees = (tree_arg,) if tree_arg else TREES

    all_findings, total_read = [], 0
    summary = {}
    for t in trees:
        f, n, blocking, nsteps, where, cov = analyse(t)
        all_findings += f
        total_read += n
        summary[t] = {"read": n, "blocking_steps": blocking, "steps": nsteps,
                      "rule_homes": where, "coverage": cov}

    if "--json" in sys.argv:
        print(json.dumps({"findings": all_findings, "summary": summary}, indent=1))
        return 1 if any(x["certain"] for x in all_findings) else 0

    print("=" * 100)
    print("STATIC REACHABILITY — could the operator have READ the rule when it had to decide?")
    print("=" * 100)

    if not selftest_patterns():
        return 2

    if total_read == 0:
        print("\n  VOID — 0 normative statements examined. This is not a pass; the "
              "instrument could not read the instruction layer.")
        return 2

    for t in trees:
        s = summary[t]
        print(f"\n  {t}/  {s['read']:>5} statements examined · "
              f"a check can block at {len(s['blocking_steps'])} of {s['steps']} steps "
              f"({', '.join(s['blocking_steps'])})")
        for label, homes in s["rule_homes"].items():
            print(f"        {label}")
            print(f"          stated in: {', '.join(homes) or 'NO FILE'}")
        unb = unbounded_repair_sites(ROOT / t)
        print(f"        repair-repeat instructions still UNBOUNDED in prose: "
              f"{len(unb) or 'none'}")
        # Print coverage even when nothing was found. "The arm ran and found no spread" and
        # "the arm did not run" look identical in a report that only prints findings.
        for conv, homes, steps, sk in s["coverage"]:
            spread = "SPREAD" if len(steps) > 1 else "one step" if steps else "not found"
            print(f"          {conv:<28} {homes} home(s) at step "
                  f"{', '.join(steps) or '-':<6} "
                  f"{f'+{sk} in SKILL.md ' if sk else ''}[{spread}]")

    certain = [f for f in all_findings if f["certain"]]

    # The same statement in both trees is ONE finding, not two. The first version of this
    # reporter counted the raw list and printed the deduped one, so it said "2 candidates"
    # above a list of one. A tool whose headline disagrees with its own body is the failure
    # class this project keeps logging -- fixed here rather than noted.
    def dedup(items):
        out, seen = [], set()
        for f in items:
            k = (f["doc"], tuple(f["governs"]), f["text"][:80])
            if k not in seen:
                seen.add(k)
                out.append(f)
        return out

    cand = dedup([f for f in all_findings if f["arm"] == "backward-governing"])
    ptr = dedup([f for f in all_findings if f["arm"] == "pointer"])

    if certain:
        print(f"\n  {len(certain)} DECIDABLE failure(s):\n")
        for f in certain:
            print(f"    [{f['tree']}/{f['arm']}] {f['detail']}")

    print(f"\n  {len(cand)} candidate(s) for judgement — THIS ARM IS A HEURISTIC and says so.")
    print("  A backward reference is often legitimate remediation ('fix and re-run from")
    print("  Step 5'). Each needs a human decision; none is a verdict.\n")
    for f in cand:
        print(f"    {f['doc']}  (readable at Step {f['first_readable']}) "
              f"-> governs Step {', '.join(f['governs'])}")
        print(f"      {f['text'][:200]}")

    print(f"\n  {len(ptr)} suppressed as POINTERS — they cite where the governing rule "
          f"lives, so the")
    print("  operator met the rule at the earlier step. Listed with --show-pointers; "
          "counted here")
    print("  rather than dropped, because a bounded instrument that stays silent about "
          "what it set")
    print("  aside reads as coverage it does not have.")
    if "--show-pointers" in sys.argv:
        for f in ptr:
            print(f"\n    {f['doc']} -> Step {', '.join(f['governs'])}\n"
                  f"      {f['text'][:200]}")

    print("\n" + "=" * 100)
    if certain:
        print(f"  FAIL — {len(certain)} rule(s) cannot be read where they are needed.")
        print("=" * 100)
        return 1
    print(f"  PASS — every decidable rule is readable at the step that needs it. "
          f"{len(cand)} candidate(s) recorded for judgement, {len(ptr)} pointer(s) "
          f"suppressed.")
    print("=" * 100)
    return 0


if __name__ == "__main__":
    sys.exit(main())
