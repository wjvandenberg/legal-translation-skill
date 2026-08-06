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

    uv run python temp/descriptor_shape_sweep.py
"""
import io
import re
import sys
from collections import Counter
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parent.parent
FILES = ["CLAUDE.md", "FINDINGS-REGISTER.md", "A3-STRUCTURAL-ANALYSIS.md",
         "STEP-B-ANALYSIS.md", "DECISIONS-LOG.md", "OPUS-5-MIGRATION.md"]

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
    text = (ROOT / name).read_text(encoding="utf-8")
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
    text = (ROOT / name).read_text(encoding="utf-8")
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
