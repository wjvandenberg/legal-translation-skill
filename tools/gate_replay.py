# -*- coding: utf-8 -*-
"""RETROSPECTIVE REPLAY — does the scope rule address what operators were actually stuck on,
and how deep did a repair loop really go?

Branch 3 added a rule for a situation the register says arises: a check fires, the operator
cannot tell whether the check or the input is wrong, and nothing in the package says a check
CAN be wrong. Branch 4 adds the other half -- the check is RIGHT and no compliant repair
exists -- and it must state a BOUND on repair attempts. Both are behavioural in the end and
belong at Step C. **What can be settled now, from evidence already in hand, is whether they
are aimed at the right thing and whether the bound's number is defensible.**

WHAT IT CANNOT DO, stated first. It cannot show a future operator will apply either rule. It
counts recorded situations and asks whether the rules speak to them. A high count is evidence
a rule is aimed correctly; it is not evidence it works.

OUTPUT POLICY -- the same one `leakage_scan.py` uses, for the same reason. **This reads the
raw forensic logs, which quote real client text, real party names and real filenames.** It
therefore prints COUNTS AND CLASSIFICATIONS ONLY: a document id, a signature name, a number.
It never prints a matched line, a heading, a filename, a path or an argv. There is no
`--show`. The logs stay outside the repository and nothing derived from them enters it except
the numbers below.

TWO DEFECTS IN THIS TOOL, FOUND ON BRANCH 4 BY RUNNING IT AND FIXED HERE:

  (1) IT WAS COUNTING THE WRONG POPULATION. It globbed `A1/**/*.md`, and each run workspace
      holds a COPY OF THE SKILL TREE -- 462 sub-lexicons, 45 references, 24 step docs. So 536
      of the 593 "log documents" were dictionaries, and **63 of the 210 reported instances
      (30%) came from lexicon prose rather than operator behaviour.** Branch 3's headline
      figure was inflated by that much. Scoped to the six real log artefacts, the true
      figure is **147**. The one signature branch 4 depends on -- "found NO compliant repair"
      -- measured 7 in BOTH populations, so the premise was never affected, only the
      headline. `--strict-population` re-runs the old wide glob and prints the delta, so the
      correction stays checkable rather than becoming folklore.

  (2) IT COULD NOT MEASURE DEPTH AT ALL, which is what branch 4 needed. Prose cannot carry
      it: two probes over the narratives produced a false ceiling of 3 because the 3 sat on
      the noun "pass" and 43 higher ordinals existed elsewhere in unrelated senses. The
      `run-D*.jsonl` forensic logs can -- every `type=step` record carries `step_id`,
      `invocation` and `rc`, so a repair sequence is a measurable object.

    LEGAL_TRANSLATION_LOGS=../legal-translation-logs uv run python tools/gate_replay.py

Exit codes:  0 = the replay ran · 2 = the logs are not reachable, or the population is
empty, or the reconciliation below fails (all three are VOID, never a pass)
"""
import io
import json
import os
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parent.parent
LOGS = Path(os.environ.get("LEGAL_TRANSLATION_LOGS",
                           str(ROOT.parent / "legal-translation-logs")))

# The five artefact kinds that are actually LOGS. Everything else under A1 is the skill tree
# copied into a run workspace, or the source/deliverable itself. Being explicit about which
# files we expect is CLAUDE.md 6.5's rule, and defect (1) above is what it protects against.
# DELIVERY-NOTES belongs here too, and its absence was a defect this scoping introduced: the
# first version of the fix narrowed to the four narrative kinds, and the delivery-notes arm
# silently went from 1 artefact to 0 -- a check reporting on an empty set, which CLAUDE.md
# 5.1 says must read VOID and never CLEAN. Caught by running it; the assertion below now
# makes it impossible to reintroduce.
LOG_STEMS = ("NARRATIVE-", "SUMMARY-", "GRADE-", "REVIEW-", "COWORK-RUN-PROTOCOL",
             "DELIVERY-NOTES")

# What an operator meeting a gate did next. Signatures, not a taxonomy invented here: each
# is a phrase the runs actually used, and the classifier reports UNCLASSIFIED rather than
# forcing a match, because a bucket that always fills is not a measurement.
SIGNATURES = {
    "diagnosed the check as wrongly scoped":
        re.compile(r"false positive|over-?fir|wrongly scoped|scoping (?:fault|error|issue)",
                   re.I),
    "kept the faithful translation anyway":
        re.compile(r"faithful translation|keep the faithful|fidelity wins", re.I),
    "found NO compliant repair":
        re.compile(r"no compliant|no non-lossy|there is no third option|"
                   r"no way to (?:comply|satisfy)", re.I),
    "narrowed or whitelisted the check":
        re.compile(r"whitelist|narrow(?:ed)? the (?:pattern|check|rule)", re.I),
}

# The six items branch 3 now requires of delivery notes, in the entry file's own words.
SPEC_ITEMS = [
    ("what the file is", re.compile(r"\bsource\b|\bvariant\b|\bdeliverable\b", re.I)),
    ("what the run did beyond translating", re.compile(r"substantive change|what this run",
                                                       re.I)),
    ("choices a reviewing lawyer should see", re.compile(r"deliberate decision|"
                                                         r"decisions? not to change", re.I)),
    ("known defects in the output", re.compile(r"known defect|manual correction", re.I)),
    ("checks resolved as false positives", re.compile(r"false positive", re.I)),
    ("what was verified", re.compile(r"verification performed|verified", re.I)),
]

# THE RECONCILIATION, and the graded-log selection it depends on.
#
# CLAUDE.md's baseline table publishes commands, gates and re-runs per document, produced by
# the private analyse_log.py, which defines a re-run as an invocation of a step beyond its
# first: max(invocation) - 1, summed over steps. This tool reaches the same records by a
# different parser, so it must reproduce those numbers exactly or one of the two is wrong --
# CLAUDE.md 5.12 rule 1. It is ASSERTED, not printed as a curiosity, because a silent drift
# would quietly invalidate the bound derived below.
#
# SELECTING THE GRADED LOG. There are 14 forensic logs for 12 graded runs: one document has a
# second, ungraded run and one has an empty log file. Merging them double-counts, which is
# how the first version of this reconciliation failed. The discriminator is the COMMAND count,
# which is itself published -- a log is the graded one when its command count matches. Any
# document where that fails to select exactly one log is REPORTED, never guessed.
#
# D03's re-run cell was published as 40 and is 41. Found on branch 4 by this assertion
# failing, confirmed by running analyse_log.py itself, and corrected in CLAUDE.md in the same
# commit. All 35 other machine-produced cells in that table reproduce exactly.
PUBLISHED = {
    "D03": (56, 1, 41), "D01": (29, 0, 15), "D09": (41, 1, 27), "D10": (37, 0, 23),
    "D04": (75, 1, 60), "D11": (41, 1, 25), "D06": (84, 4, 69), "D07": (28, 2, 13),
    "D03B": (42, 1, 27), "D08": (43, 2, 28), "D02": (59, 5, 43), "D05": (41, 2, 29),
}
PUBLISHED_RERUNS = sum(v[2] for v in PUBLISHED.values())   # 400


def docid(p):
    m = re.search(r"\bD\d{2}B?\b", str(p))
    return m.group(0) if m else "—"


def load_logs(files):
    """Return doc -> list of {step_id: [records]}, one entry per LOG (never merged)."""
    out = defaultdict(list)
    for f in files:
        doc, steps = None, defaultdict(list)
        for line in f.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            if r.get("doc_id"):
                doc = str(r["doc_id"])
            if r.get("type") == "step" and r.get("step_id") is not None:
                steps[str(r["step_id"])].append(r)
        if doc is None:
            m = re.search(r"\bD\d{2}B?\b", f.stem)
            doc = m.group(0) if m else "?"
        out[doc].append(steps)
    return out


def select_graded(by_doc):
    """Pick the graded log per document by its published COMMAND count. Report, never guess.

    Returns (selected, skipped) where skipped is a list of (doc, commands, why).
    """
    selected, skipped = {}, []
    for doc, logs in sorted(by_doc.items()):
        want = PUBLISHED.get(doc, (None,))[0]
        for steps in logs:
            cmds = sum(len(v) for v in steps.values())
            if want is not None and cmds == want and doc not in selected:
                selected[doc] = steps
            else:
                skipped.append((doc, cmds,
                                "empty log" if cmds == 0 else
                                "second, ungraded run" if want is not None else
                                "not in the published table"))
    return selected, skipped


def repair_depth(selected):
    """Walk the selected logs and return the repair-sequence distribution.

    A SEQUENCE is consecutive invocations of one step_id within one document. It OPENS on a
    non-zero rc; its DEPTH is how many further invocations of that step followed; it CLOSES
    SUCCESSFULLY if a later invocation of that step returns 0. An UNCLOSED sequence is a step
    that never went green -- the deadlock shape branch 4 exists for.
    """
    runs = defaultdict(lambda: defaultdict(list))
    for doc, steps in selected.items():
        for sid, recs in steps.items():
            for r in sorted(recs, key=lambda x: (x.get("epoch") or 0,
                                                 x.get("invocation") or 0)):
                runs[doc][sid].append(r.get("rc"))

    # Re-runs by analyse_log.py's EXACT definition: max(invocation, default 1) - 1, summed
    # over steps. Not count-1 -- a step record with no `invocation` key counts as invocation
    # 1, not as another invocation, and the two definitions disagree on 13 (document, step)
    # pairs across the corpus.
    invocations = derived_reruns = 0
    for doc, steps in selected.items():
        for sid, recs in steps.items():
            invocations += len(recs)
            derived_reruns += max([r.get("invocation", 1) or 1 for r in recs]) - 1

    closed, unclosed = Counter(), Counter()
    closed_where, unclosed_where = defaultdict(set), defaultdict(set)
    for doc, steps in runs.items():
        for step, rcs in steps.items():
            i = 0
            while i < len(rcs):
                if rcs[i] not in (0, None):
                    depth, j, ok = 0, i + 1, False
                    while j < len(rcs):
                        depth += 1
                        if rcs[j] == 0:
                            ok = True
                            break
                        j += 1
                    (closed if ok else unclosed)[depth] += 1
                    (closed_where if ok else unclosed_where)[depth].add(doc)
                    i = j + 1
                else:
                    i += 1
    return closed, unclosed, closed_where, unclosed_where, invocations, derived_reruns


def main():
    if not LOGS.exists():
        print(f"  VOID — the forensic logs are not reachable at {LOGS}.")
        print("  This is not a pass. Set LEGAL_TRANSLATION_LOGS to the sibling logs folder.")
        return 2

    a1 = LOGS / "A1"
    everything = sorted(a1.rglob("*.md")) if a1.exists() else []
    files = [p for p in everything if p.name.startswith(LOG_STEMS)]
    if not files:
        print(f"  VOID — 0 LOG documents under {a1} (saw {len(everything)} .md files, none "
              f"of them a log artefact). Not a pass.")
        return 2

    print("=" * 96)
    print("GATE REPLAY — what operators actually did when a check fired")
    print("=" * 96)
    print(f"\n  {len(files)} log document(s) read, selected by artefact kind from "
          f"{len(everything)} .md files")
    print("  under A1. The rest are the skill tree copied into each run workspace and are")
    print("  NOT evidence of operator behaviour. Counts only; no log text is printed.\n")

    per_doc, totals, gate_docs = {}, Counter(), set()
    for f in files:
        doc = docid(f)
        try:
            body = f.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if re.search(r"SKILL GATE FIRED|gate fired", body, re.I):
            gate_docs.add(doc)
        for name, pat in SIGNATURES.items():
            n = len(pat.findall(body))
            if n:
                per_doc.setdefault(doc, Counter())[name] += n
                totals[name] += n

    print(f"  a gate firing is recorded in {len(gate_docs)} document(s)\n")
    print(f"  {'situation the scope rule speaks to':<44} {'instances':>9}  documents")
    print("  " + "-" * 74)
    for name in SIGNATURES:
        docs = sorted(d for d, c in per_doc.items() if c.get(name))
        print(f"  {name:<44} {totals[name]:>9}  {len(docs)}")

    addressed = sum(totals.values())
    print("  " + "-" * 74)
    print(f"  {'TOTAL recorded instances':<44} {addressed:>9}")

    if "--strict-population" in sys.argv:
        wide = Counter()
        for p in everything:
            body = p.read_text(encoding="utf-8", errors="replace")
            for name, pat in SIGNATURES.items():
                wide[name] += len(pat.findall(body))
        print(f"\n  POPULATION CHECK — the pre-branch-4 glob counted {sum(wide.values())}, "
              f"this counts {addressed}.")
        print(f"  {sum(wide.values()) - addressed} match(es) came from the skill's own "
              f"dictionaries, not from operator behaviour.")

    # ---- THE BOUND, MEASURED -----------------------------------------------------------
    jsonl = sorted(LOGS.rglob("run-D*.jsonl"))
    print(f"\n\n  REPAIR DEPTH — from {len(jsonl)} forensic step log(s), not from prose.")
    if not jsonl:
        print("  VOID for this arm — no run-D*.jsonl found. The bound cannot be derived.")
        return 2

    selected, skipped = select_graded(load_logs(jsonl))
    missing = sorted(set(PUBLISHED) - set(selected))
    if missing:
        print(f"  VOID — no log matched the published command count for {missing}. "
              f"Not a pass.")
        return 2
    # No silent caps (CLAUDE.md 5.1): say what was set aside and why.
    for doc, cmds, why in skipped:
        print(f"    set aside: a {doc} log with {cmds} command(s) — {why}")

    closed, unclosed, cwhere, uwhere, invocations, derived = repair_depth(selected)
    print(f"  {len(selected)} graded log(s) selected · {invocations} step invocation(s).")
    if derived != PUBLISHED_RERUNS:
        print(f"\n  VOID — RECONCILIATION FAILED. This parser derives {derived} re-runs; "
              f"CLAUDE.md's")
        print(f"  baseline table publishes {PUBLISHED_RERUNS}. One of the two is wrong and "
              f"no number below")
        print("  can be trusted until that is settled. This is not a pass.")
        return 2
    print(f"  Re-runs derived: {derived} — reconciles EXACTLY with the {PUBLISHED_RERUNS} "
          f"published in")
    print("  CLAUDE.md's baseline table, reached by a different parser.\n")

    print("  (A) repair sequences that CLOSED — the check went green after N more attempts")
    print(f"      {'N':<5} {'sequences':>10}  documents")
    print("      " + "-" * 34)
    for n in sorted(closed):
        print(f"      {n:<5} {closed[n]:>10}  {len(cwhere[n])}")
    deepest = max(closed) if closed else 0
    tot = sum(closed.values())
    print("      " + "-" * 34)
    print(f"      DEEPEST SUCCESSFUL REPAIR: {deepest}")

    print("\n  (B) repair sequences that NEVER CLOSED — the deadlock shape, and F41's harm")
    if unclosed:
        print(f"      {'N':<5} {'sequences':>10}  documents")
        print("      " + "-" * 34)
        for n in sorted(unclosed):
            print(f"      {n:<5} {unclosed[n]:>10}  {len(uwhere[n])}")
        print(f"      DEEPEST LOOP THAT NEVER WENT GREEN: {max(unclosed)}")
    else:
        print("      none")

    if tot:
        print(f"\n  {tot} successful repair sequence(s). Coverage by candidate bound:")
        cum = 0
        for n in sorted(closed):
            cum += closed[n]
            print(f"    a bound of {n:<2} would have allowed {cum:>3} of {tot} "
                  f"({100 * cum / tot:5.1f}%) to finish")
        print(f"\n  THE BOUND IS {deepest}: the smallest number that truncates NOTHING the "
              f"corpus")
        print(f"  ever repaired successfully. {deepest - 1} would have cut short "
              f"{closed[deepest]} real repair(s).")

    # ---- the delivery-notes specification, against the one real artefact ---------------
    notes = [f for f in files if f.name.upper().startswith("DELIVERY-NOTES")]
    print(f"\n  DELIVERY NOTES — {len(notes)} artefact(s) exist across twelve runs.")
    if not notes:
        print("  VOID for this arm — the one known delivery-notes artefact was not reached,")
        print("  which means the population filter has excluded it. Not a pass.")
        return 2
    if notes:
        body = notes[0].read_text(encoding="utf-8", errors="replace")
        have = [(n, bool(p.search(body))) for n, p in SPEC_ITEMS]
        print("  Branch 3's six required items, checked against what a real run produced:")
        for n, ok in have:
            print(f"    {'present ' if ok else 'ABSENT  '} {n}")
        print(f"\n  {sum(1 for _, o in have if o)} of {len(SPEC_ITEMS)} specification items "
              f"were already produced voluntarily by the best run.")

    print("\n" + "=" * 96)
    print(f"  {addressed} recorded instances across {len(gate_docs)} documents sit in the")
    print("  situation rule 5a addresses. That is evidence the rule is AIMED correctly.")
    if unclosed:
        print(f"  {sum(unclosed.values())} loop(s) never went green, the deepest running to "
              f"{max(unclosed)} attempts —")
        print("  which is F41's unbounded repair, observed rather than argued.")
    print("  Whether an operator applies either rule is behavioural — §4.1 puts that at "
          "Step C.")
    print("=" * 96)
    return 0


if __name__ == "__main__":
    sys.exit(main())
