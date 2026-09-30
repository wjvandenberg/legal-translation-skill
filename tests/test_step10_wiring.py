"""test_step10_wiring.py - branch 11, Step 10's wiring slice, on synthetic input and the step documents.

ONE FAILING INPUT PER CLAIM, AND A CLEAN ONE PROVED QUIET. Nothing is read from the corpus. What each
arm asserts:

  J2  Step 4's Rule 1 gives the TRUE reason for a U+200B-only seam between two tracked segments: the
      markup view does show both, touching, as the source's own redline does, and accepting or
      rejecting reads only one of them. The false premise -- that no rendered reader sits between two
      consecutive tracked segments -- is gone, lines joined, and the prescription is kept word for
      word. Both trees.

    uv run --with lxml python tests/test_step10_wiring.py
    uv run --with lxml python tests/test_step10_wiring.py --variant us
"""
import argparse
import io
import re
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parent.parent
ap = argparse.ArgumentParser()
ap.add_argument("--variant", choices=("uk", "us"), default="uk")
args = ap.parse_args()
FAIL, CHECKED = [], 0


def ok(label, cond, detail=""):
    global CHECKED
    CHECKED += 1
    print(f"  {'OK  ' if cond else 'XX  '} {label}" + (f"   ({detail})" if detail and not cond else ""))
    if not cond:
        FAIL.append(label)


def joined(path):
    """The document with every whitespace run collapsed to one space: a phrase a line break wraps
    matches nothing line by line, and the zero reads as a clean result."""
    return re.sub(r"\s+", " ", path.read_text(encoding="utf-8"))


print("=" * 88)
print(f"STEP 10's WIRING SLICE — synthetic input and the step documents  [{args.variant}]")
print("=" * 88)

print("\nJ2  Step 4's Rule 1: the true reason for a U+200B-only seam, the prescription kept, both trees")
RECIPE = ("The recipe in one line: **regular sides carry visible-space + ZWSP; ins↔ins or ins↔del seams "
          "carry ZWSP only.**")
for v in ("uk", "us"):
    s4 = joined(ROOT / v / "skill-docs" / "04-translate.md")
    ok(f"[{v}] the false premise is gone — 'no rendered reader between two consecutive' tracked segments",
       "no rendered reader between two consecutive" not in s4)
    ok(f"[{v}] the true reason: the markup view shows both, touching, as the source's own redline does",
       all(x in s4 for x in ("the markup view shows both",
                             "only one of the two is ever read as text",
                             "how the source's own redline shows such a seam",
                             "repack scrubs the ZWSP, so the delivered redline matches the source's")))
    ok(f"[{v}] two insertions in a row are DESCRIBED — both kept on accepting — and nothing new is prescribed",
       "Two insertions in a row are both kept on accepting" in s4)
    ok(f"[{v}] the prescription is kept word for word — the recipe line", RECIPE in s4)

print()
print("=" * 88)
if FAIL:
    print(f"FAIL — {len(FAIL)} of {CHECKED} checks:")
    for f in FAIL:
        print(f"  ·  {f}")
    print("=" * 88)
    sys.exit(1)
print(f"PASS — {CHECKED} checks.")
print("=" * 88)
