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


# THE DOUBLED-SEPARATOR ARM -- the hole the single-backslash probe could not see, closed
# 2026-09-09 as its own probe. A path written inside a NON-raw Python literal has every
# separator doubled, and the arm above requires exactly one.
#
# IT IS A SEPARATE PROBE RATHER THAN A WIDER FIRST ONE, AND THAT IS THE WHOLE DESIGN: measured
# before it was adopted, widening the FIRST arm turns 12 committable files red, and none of the
# 17 new hits across tools/, tests/ and temp/ carries a forbidden phrase -- checked against the
# list with a positive control firing. So this one REPORTS for judgement in tools/ and BLOCKS
# in the shipped trees, where the same widening finds zero files and any absolute path is a
# defect by definition.
DOUBLED_LABEL = "absolute or home path, doubled-separator form"
BS2 = chr(92) * 2

DOUBLED_MUST_FIRE = [
    ('a drive path as a non-raw literal writes it',
     'run = "C:' + BS2 + 'Invented' + BS2 + 'Folder"'),
    ('the same, deeper', '"D:' + BS2 + 'Invented' + BS2 + 'Folder' + BS2 + 'thing.py"'),
]

DOUBLED_MUST_NOT_FIRE = [
    # The single-separator forms belong to the OTHER arm; this one must not double-report them.
    ('a single-separator drive path', r'C:\Invented\Folder'),
    ('a YAML fixture string, doubled', '"---' + BS2 + 'npaths:' + BS2 + 'n"'),
    ('ordinary prose', 'The rule says: never bypass a gate.'),
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

    # ---- the doubled-separator arm, its own probe ----
    dbl = re.compile(probe_pattern(DOUBLED_LABEL))
    print(f"\n  THE DOUBLED-SEPARATOR ARM ({len(dbl.pattern)} chars, also from the AST)")
    for label, vector in DOUBLED_MUST_FIRE:
        hit = bool(dbl.search(vector))
        ok &= hit
        print(f"    {'OK  ' if hit else 'MISS'} fires on {label}")
    for label, vector in DOUBLED_MUST_NOT_FIRE:
        quiet = not dbl.search(vector)
        ok &= quiet
        print(f"    {'OK  ' if quiet else 'MISS'} quiet on {label}")

    # THE ARM THAT PROVES THE TIER, NOT JUST THE PATTERN. A probe that blocks would undo the
    # measurement this design rests on, so the tier is asserted rather than trusted.
    src = (ROOT / "tools" / "script_committability.py").read_text(encoding="utf-8")
    tiered = re.search(r"NOTE_ONLY\s*=\s*\{([^}]*)\}", src)
    in_tier = bool(tiered and DOUBLED_LABEL in tiered.group(1))
    ok &= in_tier
    print(f"    {'OK  ' if in_tier else 'MISS'} it is in NOTE_ONLY, so it reports and never blocks")

    # And the twin: the shipped-tree scanner must carry the doubled form as a BLOCKING arm.
    trees = (ROOT / "tools" / "scan_trees.py").read_text(encoding="utf-8")
    blocks = r"\\{1,2}" in trees
    ok &= blocks
    print(f"    {'OK  ' if blocks else 'MISS'} scan_trees.py carries the doubled form, blocking")

    print("\n" + "=" * 92)
    print("PASS -- the probe still catches a path and no longer catches an escape sequence."
          if ok else "FAIL")
    print("=" * 92)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
