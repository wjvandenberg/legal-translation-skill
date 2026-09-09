# -*- coding: utf-8 -*-
"""THE 'absolute or home path' PROBE, PROVED BOTH WAYS.

Section 5.6 requires a test vector beside every confidentiality pattern, in the same commit
as the pattern. This is that vector for the drive-letter arm of
`tools/script_committability.py`, tightened on 2026-09-09 with a word-boundary guard.

WHY A ONE-SIDED TEST WOULD BE WORTHLESS HERE. "It no longer fires on the fixture" is passed
perfectly by deleting the pattern. So every negative case sits beside a positive one, and the
suite fails if the probe stops catching a real path just as loudly as if it starts catching a
Python escape sequence again.

THE PATTERN IS READ OUT OF THE TOOL'S OWN AST, never retyped. A retyped pattern is a
different pattern, and a test that guards a copy guards nothing -- which is the defect this
project has already paid for twice, once from a hand-counted list and once from a copied
regex.

NOTHING HERE IS A REAL PATH. Every vector is invented for the purpose, per section 5.6.
"""
import ast
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]


def probe_pattern(label="absolute or home path"):
    """The live pattern, taken from the tool's source rather than copied into this file."""
    tree = ast.parse((ROOT / "tools" / "script_committability.py").read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == "PROBES" for t in node.targets
        ):
            for elt in node.value.elts:
                head = elt.elts[0]
                body = elt.elts[1]
                if isinstance(head, ast.Constant) and head.value == label:
                    if not isinstance(body, ast.Constant):
                        raise SystemExit(f"VOID: {label!r} is no longer a literal pattern")
                    return body.value
    raise SystemExit(f"VOID: probe {label!r} not found -- do not fall back to a retyped one")


# MUST FIRE. Invented paths, in the shapes a real one actually arrives in.
MUST_FIRE = [
    ('a quoted drive path', r'run = r"C:\Invented\Folder\thing.py"'),
    ('a bare drive path at line start', r'D:\Invented\Folder\thing.py'),
    ('a drive path after whitespace', r'    see E:\Invented\Folder\notes.md'),
    ('a home path', r'log lives at ~/invented/folder/trace.log'),
    ('a home path, backslash form', r'~\invented\folder\trace.log'),
]

# MUST STAY QUIET. Escape sequences inside ordinary Python string literals.
MUST_NOT_FIRE = [
    ('a YAML fixture string', '"---\\npaths:\\n  - \\"tools/**\\"\\n"'),
    ('a two-key fixture string', '"title:\\nsummary:\\nbody\\n"'),
    ('a tab escape after a word', '"columns:\\tone\\ttwo\\n"'),
    ('a plain sentence with a colon', 'The rule says: never bypass a gate.'),
    ('a relative path, which is not this probe\'s subject', 'tools/hooks/evidence_guard.py'),
]


# A DECLARED, MEASURED GAP -- REPORTED, NOT ASSERTED, AND RAISED TO WOUTER RATHER THAN
# QUIETLY CLOSED. The drive arm requires ONE backslash after the colon, so a path written in a
# NON-raw Python literal -- where every separator is doubled -- is not matched. That predates
# the 2026-09-09 word-boundary guard and is unaffected by it: the original pattern misses it
# too, verified by running both. It is NOT fixed here because widening a confidentiality
# pattern is a decision about a control, not a cleanup, and section 5.6 requires a test vector
# per pattern in the same commit as the pattern. Listing it as MUST_FIRE would fail the suite
# and invite somebody to weaken the test instead; leaving it out entirely would make an
# unexamined hole indistinguishable from an examined one. So it is a printed observation.
KNOWN_GAP = [
    ('a doubled-backslash path, as a non-raw literal writes it',
     'run = "C:' + chr(92) * 2 + 'Invented' + chr(92) * 2 + 'Folder"'),
]


def main() -> int:
    pat = re.compile(probe_pattern())
    print("=" * 92)
    print("THE 'absolute or home path' PROBE -- both arms")
    print("=" * 92)
    print(f"  pattern read from the tool's AST, {len(pat.pattern)} chars\n")

    ok = True
    print("  MUST FIRE -- a real path shape, invented for the purpose")
    for label, vector in MUST_FIRE:
        hit = bool(pat.search(vector))
        ok &= hit
        print(f"    {'OK  ' if hit else 'MISS'} {label}")

    print("\n  MUST STAY QUIET -- escape sequences and ordinary prose")
    for label, vector in MUST_NOT_FIRE:
        quiet = not pat.search(vector)
        ok &= quiet
        print(f"    {'OK  ' if quiet else 'MISS'} {label}")

    # THE ARM THAT MAKES THIS A REGRESSION TEST RATHER THAN A UNIT TEST: the real file that
    # blocked a real commit must now be clean, and the tools/ folder must stay scanned.
    target = ROOT / "tools" / "trace_instructions.py"
    if target.exists():
        n = len(pat.findall(target.read_text(encoding="utf-8", errors="replace")))
        ok &= (n == 0)
        print(f"\n    {'OK  ' if n == 0 else 'MISS'} tools/trace_instructions.py is clean "
              f"({n} hit(s)) -- the file the false positive blocked")
    else:
        print("\n    VOID  tools/trace_instructions.py absent -- this arm proved nothing")
        ok = False

    print("\n  DECLARED GAP -- reported, never asserted, and open for Wouter")
    for label, vector in KNOWN_GAP:
        print(f"    {'still missed' if not pat.search(vector) else 'NOW CAUGHT'}  {label}")

    print("\n" + "=" * 92)
    print("PASS -- the probe still catches a path and no longer catches an escape sequence."
          if ok else "FAIL")
    print("=" * 92)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
