# -*- coding: utf-8 -*-
"""SHAPE-BASED SWEEP for corpus descriptors — list-free, so it can find qualifiers nobody
thought to put on a list.

The targeted scan (`corpus_descriptor_scan.py`) hunts terms I already knew about, which means
it can only confirm my own assumptions. This one looks for the SHAPE instead:

  (a) any instrument noun preceded by a qualifier  -- of the shape "<subject> lease",
      "<subject> concession". The examples here are INVENTED on purpose: quoting the real
      qualifiers would put them back into a file meant to be publishable.
  (b) any language adjective within a few words of an instrument noun, reporting whatever
      sits between them -- which is exactly where a subject-matter qualifier hides

Everything it prints is a CANDIDATE for judgement, not a hit. That is deliberate: the
project's own lesson is that a list-based control cannot see the class of leak it was not
written for, and the shape-based sweep is what caught the commercial-terms leak in July.

    uv run python tools/descriptor_shape_sweep.py                 # every committable markdown
    uv run python tools/descriptor_shape_sweep.py EVIDENCE-x.md   # or just these

THE FILE LIST USED TO BE SIX HARD-CODED NAMES AND IT SILENTLY IGNORED ITS ARGUMENTS -- found
2026-08-24, when it was pointed at a new `.claude/skills/*/SKILL.md` and cheerfully reported on
CLAUDE.md instead. **A control that cannot reach the file you asked it about is worse than one
that refuses**, because its output looks exactly like coverage. The six names were written before
`.claude/rules/` and `.claude/skills/` existed, and phase 3c is about to add an EVIDENCE- document
whose whole subject is past leaks -- the single likeliest place in the repository for one.

So: it now DISCOVERS the committable markdown, takes an explicit list when given one, and PRINTS
WHAT IT READ. A sweep that opened no files exits 2 as VOID rather than reporting clean.
"""
import io
import re
import sys
from collections import Counter
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parent.parent

# The six that were hard-coded, kept as names so a rename is noticed rather than silently dropped.
CORE = ["CLAUDE.md", "FINDINGS-REGISTER.md", "A3-STRUCTURAL-ANALYSIS.md",
        "STEP-B-ANALYSIS.md", "DECISIONS-LOG.md", "OPUS-5-MIGRATION.md"]
# Everything else committable that carries prose. Globs, so a document added later is swept
# without anybody remembering to add it here.
DISCOVER = ["README.md", "EVIDENCE-*.md", "REGISTER-*.md", "PLAN-*.md",
            ".claude/rules/*.md", ".claude/skills/*/SKILL.md", "tests/README.md"]


def targets(argv):
    if argv:
        return [Path(a) for a in argv]
    out = [ROOT / n for n in CORE if (ROOT / n).exists()]
    for g in DISCOVER:
        out.extend(sorted(ROOT.glob(g)))
    seen, uniq = set(), []
    for p in out:
        if p.resolve() not in seen:
            seen.add(p.resolve())
            uniq.append(p)
    return uniq


PATHS = targets(sys.argv[1:])
missing = [n for n in CORE if not (ROOT / n).exists()] if not sys.argv[1:] else []
print("=" * 96)
# FINDING I-22, fixed 2026-09-02: THIS SAID "FILES READ" BEFORE OPENING ANYTHING.
#
# It was a statement of INTENT printed at the top, and the sweep then died on the first
# undecodable file -- `read_text(encoding="utf-8")` raising UnicodeDecodeError on a `.docx`
# byte -- after candidates had already been printed for the files ahead of it. The result read
# as a partial success: a plausible report, a traceback, and every file behind the crash
# silently unswept. A control that announces what it was ASKED to do rather than what it DID
# is the fourth instance of that shape in this project (I-19's `$?`, I-20's exit 0 on a killed
# build, C29's crash announced as an intentional block).
#
# So the count is now REQUESTED at the top and READ at the bottom, and every file is decoded
# ONCE, here, with an undecodable one recorded as a DECLARED SKIP rather than an exception.
print(f"FILES REQUESTED: {len(PATHS)}")
for p in PATHS:
    try:
        rel = p.resolve().relative_to(ROOT)
    except ValueError:
        rel = p
    print(f"    {rel}")
if missing:
    print(f"  MISSING from the core list, so NOT swept: {missing}")
if not PATHS:
    print("VOID -- no file was opened, so nothing has been established. This is not a clean run.")
    sys.exit(2)

FILES = [str(p.resolve().relative_to(ROOT)) if p.resolve().is_relative_to(ROOT) else str(p)
         for p in PATHS]

# DECODE ONCE, HERE, AND DECLARE WHAT COULD NOT BE READ -- finding I-22.
#
# This sweep is a PROSE instrument: it looks for a subject-matter qualifier sitting in front of
# an instrument noun, and those leak in sentences, not in a compressed container. So refusing a
# binary is CORRECT BEHAVIOUR and the scope is not the defect. What was wrong is that it
# refused by CRASHING, mid-run, having already printed a count and some findings.
#
# A skip is therefore a RESULT, printed and counted -- never an exception and never silence.
# The confidentiality control that DOES have to see inside a container is `leakage_scan.py`,
# which reads a ZIP's members as of the same day (I-21); this one deliberately does not.
TEXTS, SKIPPED = {}, []
for _name in FILES:
    try:
        TEXTS[_name] = (ROOT / _name).read_text(encoding="utf-8")
    except UnicodeDecodeError as _e:
        SKIPPED.append((_name, f"not UTF-8 text ({_e.reason})"))
    except OSError as _e:
        SKIPPED.append((_name, f"unreadable ({_e.__class__.__name__})"))
FILES = [f for f in FILES if f in TEXTS]
if SKIPPED:
    print()
    print(f"  {len(SKIPPED)} file(s) DECLARED SKIPPED -- not prose, so this sweep cannot rule "
          f"on them:")
    for _n, _why in SKIPPED:
        print(f"      SKIP  {_n}  ({_why})")
    print("  A skip is reported, never silent. For a container's CONTENTS use "
          "tools/leakage_scan.py,")
    print("  which reads a ZIP's members; this sweep is a prose instrument by design.")
if not FILES:
    print()
    print("VOID -- every requested file was skipped, so nothing has been established.")
    sys.exit(2)

INSTRUMENT = r"(?:agreement|contract|deed|guarantee|MOU|memorandum|novation|power of attorney|" \
             r"instrument|lease|licence|license|charter|mandate|undertaking|indenture|covenant)"
LANGUAGE = r"(?:Norwegian|Dutch|Hungarian|Italian|Spanish|Finnish|Polish|Japanese|English|" \
           r"German|French|Portuguese|Swedish|Danish)"

# Words that may legitimately sit in front of an instrument noun: they describe the FILE,
# the project's own vocabulary, or a generic legal concept -- never the deal.
BENIGN = {
    "the", "a", "an", "one", "each", "every", "this", "that", "any", "no", "same", "other",
    "another", "second", "third", "fourth", "first", "real", "client", "corpus", "test",
    "source", "target", "delivered", "translated", "original", "legal", "published",
    "confidentiality", "non-disclosure", "of", "and", "or", "in", "on", "per", "its",
    "their", "our", "his", "whose", "such", "single", "eleven", "twelve", "two", "three",
    "distinct", "further", "later", "earlier", "given", "whole", "entire", "underlying",
    "stand-alone", "standalone", "signed", "unsigned", "draft", "final", "governing",
    "counterparty's", "drafter's", "party", "parties", "sample", "example", "synthetic",
    "hypothetical", "illustrative", "notional", "generic", "class", "kind", "type",
    "polish", "norwegian", "dutch", "hungarian", "italian", "spanish", "finnish",
    "japanese", "english", "german", "french",
}

flagged = Counter()
print("=" * 96)
print("A. QUALIFIER IMMEDIATELY BEFORE AN INSTRUMENT NOUN")
print("=" * 96)
for name in FILES:
    text = TEXTS[name]          # decoded once above; skips already declared
    out = []
    for m in re.finditer(r"([A-Za-z][\w'’-]*)\s+" + INSTRUMENT + r"\b", text, re.I):
        q = m.group(1).lower().strip("*`")
        if q in BENIGN:
            continue
        line = text[:m.start()].count("\n") + 1
        out.append((q, line, m.group(0)))
        flagged[q] += 1
    print(f"\n{name}: {len(out)} candidate(s)")
    for q, line, got in out[:25]:
        print(f"    L{line:<6} {got!r}")
    if len(out) > 25:
        print(f"    ... and {len(out) - 25} more")

print()
print("=" * 96)
print("B. A LANGUAGE AND AN INSTRUMENT NOUN WITHIN A FEW WORDS — what sits between them?")
print("=" * 96)
for name in FILES:
    text = TEXTS[name]          # decoded once above; skips already declared
    out = []
    for m in re.finditer(LANGUAGE + r"\)?\W{1,4}(?:\w+\W+){0,3}?" + INSTRUMENT + r"\b",
                         text, re.I):
        line = text[:m.start()].count("\n") + 1
        out.append((line, re.sub(r"\s+", " ", m.group(0))))
    print(f"\n{name}: {len(out)} pairing(s)")
    for line, got in out[:25]:
        print(f"    L{line:<6} {got!r}")
    if len(out) > 25:
        print(f"    ... and {len(out) - 25} more")

print()
print("=" * 96)
print("CANDIDATE QUALIFIERS, most frequent first — judge each; none is automatically a hit")
print("=" * 96)
for q, n in flagged.most_common(40):
    print(f"  {q:<28} {n}")
print("=" * 96)
# THE COUNT THAT MEANS SOMETHING, printed LAST -- finding I-22. Reaching this line is itself
# the evidence: every file in FILES was decoded before the first section ran, so a crash can no
# longer sit between a printed count and the work it claims to describe.
print(f"FILES READ: {len(FILES)} of {len(PATHS)} requested"
      + (f" · {len(SKIPPED)} DECLARED SKIP(S), listed above" if SKIPPED else ""))
print("=" * 96)
