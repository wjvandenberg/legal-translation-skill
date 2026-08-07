# -*- coding: utf-8 -*-
"""RETROSPECTIVE REPLAY — does the scope rule address what operators were actually stuck on?

Branch 3 adds a rule for a situation the register says arises: a check fires, the operator
cannot tell whether the check or the input is wrong, and nothing in the package says a check
CAN be wrong. Whether that rule helps a future operator is behavioural and belongs at Step C.
**What can be settled now, from evidence already in hand, is whether it is aimed at the right
thing** -- and the twelve A1 runs recorded every gate an operator met and what it did next.

WHAT IT CANNOT DO, stated first. It cannot show a future operator will apply the rule. It
counts recorded situations and asks whether the rule speaks to them. A high count is evidence
the rule is aimed correctly; it is not evidence it works.

OUTPUT POLICY -- the same one `leakage_scan.py` uses, for the same reason. **This reads the
raw forensic logs, which quote real client text, real party names and real filenames.** It
therefore prints COUNTS AND CLASSIFICATIONS ONLY: a document id, a signature name, a number.
It never prints a matched line, a heading, a filename or any span of the logs. There is no
`--show`. The logs stay outside the repository and nothing derived from them enters it except
the numbers below.

    LEGAL_TRANSLATION_LOGS=../legal-translation-logs uv run python tools/gate_replay.py

Exit codes:  0 = the replay ran · 2 = the logs are not reachable (VOID, not a pass)
"""
import io
import os
import re
import sys
from collections import Counter
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parent.parent
LOGS = Path(os.environ.get("LEGAL_TRANSLATION_LOGS",
                           str(ROOT.parent / "legal-translation-logs")))

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


def main():
    if not LOGS.exists():
        print(f"  VOID — the forensic logs are not reachable at {LOGS}.")
        print("  This is not a pass. Set LEGAL_TRANSLATION_LOGS to the sibling logs folder.")
        return 2

    a1 = LOGS / "A1"
    files = sorted(a1.rglob("*.md")) if a1.exists() else []
    if not files:
        print(f"  VOID — 0 log documents found under {a1}. Not a pass.")
        return 2

    print("=" * 96)
    print("GATE REPLAY — what operators actually did when a check fired")
    print("=" * 96)
    print(f"\n  {len(files)} log document(s) read. Counts only; no log text is printed.\n")

    per_doc, totals, gate_docs = {}, Counter(), set()
    for f in files:
        # The document id is the register's own scheme (D01..D11), which is safe: it names
        # the FILE's place in the corpus, never the instrument or the parties.
        m = re.search(r"\bD\d{2}B?\b", str(f))
        doc = m.group(0) if m else "—"
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

    # ---- the delivery-notes specification, against the one real artefact ---------------
    notes = [f for f in files if f.name.upper().startswith("DELIVERY-NOTES")]
    print(f"\n  DELIVERY NOTES — {len(notes)} artefact(s) exist across twelve runs.")
    if notes:
        body = notes[0].read_text(encoding="utf-8", errors="replace")
        have = [(n, bool(p.search(body))) for n, p in SPEC_ITEMS]
        print("  Branch 3's six required items, checked against what a real run produced:")
        for n, ok in have:
            print(f"    {'present ' if ok else 'ABSENT  '} {n}")
        print(f"\n  {sum(1 for _, o in have if o)} of {len(SPEC_ITEMS)} specification items "
              f"were already produced voluntarily by the best run.")
        print("  The specification was widened to match it: a spec NARROWER than what a good")
        print("  run already does would have made future notes worse, not better.")

    print("\n" + "=" * 96)
    print(f"  {addressed} recorded instances across {len(gate_docs)} documents sit in the")
    print("  situation rule 5a addresses. That is evidence the rule is AIMED correctly.")
    print("  Whether an operator applies it is behavioural — STEP-B §4.1 puts that at Step C.")
    print("=" * 96)
    return 0


if __name__ == "__main__":
    sys.exit(main())
