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

AND THE GATE'S `--skip-scratch` CALL (2026-10-22), run on a copy of the live scanner in an invented layout: see
`scratch_arms`.
"""
import ast
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile

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


# --skip-scratch, THE GATE'S CALL (2026-10-22, Wouter: "Gate skips temp/"). The scanner's temp/ arm never blocks and
# the gate never printed it, yet it was about 9 of the scanner's 11 s on each of the 26 gate runs a full run makes.
# These arms run a BYTE-IDENTICAL COPY of the live scanner in an invented layout - its own tools/, temp/ and private
# folder, two invented one-pattern lists - so they are fast and touch nothing real. A copy that differed from the
# live file would guard nothing, so that is asserted first. Red on the scanner before the flag existed: it read
# temp/ whatever it was passed, and the gate's call carried no flag.
def scratch_arms() -> bool:
    live = ROOT / "tools" / "script_committability.py"
    shape = str(100 + 23) + " " + "M" + "W"      # a capacity figure, built here so this file holds none
    ok = True
    print("\n  --skip-scratch -- the gate's call leaves out temp/, and only temp/")

    def arm(label, cond):
        print(f"    {'OK  ' if cond else 'MISS'} {label}")
        return cond

    with tempfile.TemporaryDirectory(prefix="committability-") as td:
        root = pathlib.Path(td)
        for d in ("tools", "temp", "private/tools"):
            (root / d).mkdir(parents=True)
        shutil.copyfile(live, root / "tools" / "script_committability.py")
        shutil.copyfile(ROOT / "tools" / "sibling_dirs.py", root / "tools" / "sibling_dirs.py")
        (root / "tools" / "clean.py").write_text("X = 1\n", encoding="utf-8")
        (root / "temp" / "scratch.py").write_text(f"NOTE = '{shape}'\n", encoding="utf-8")
        (root / "private" / "names.txt").write_text("zzinventedname\n", encoding="utf-8")
        (root / "private" / "descriptors.txt").write_text("zzinventeddescriptor\n", encoding="utf-8")
        env = dict(os.environ, LT_PRIVATE_DIR=str(root / "private"), PYTHONDONTWRITEBYTECODE="1",
                   LEAKAGE_LIST_PATH=str(root / "private" / "names.txt"),
                   CORPUS_DESCRIPTORS_FILE=str(root / "private" / "descriptors.txt"), PYTHONIOENCODING="utf-8")

        def scan(*flags):
            r = subprocess.run([sys.executable, str(root / "tools" / "script_committability.py"), *flags],
                               cwd=root, env=env, capture_output=True, text=True, encoding="utf-8",
                               errors="replace", stdin=subprocess.DEVNULL)
            return r.returncode, r.stdout + r.stderr

        copy = (root / "tools" / "script_committability.py").read_bytes()
        ok &= arm("the copy is byte-identical to the live scanner", copy == live.read_bytes())
        rc, out = scan()
        if rc == 2:
            print("    VOID  the copy could not load its invented lists -- these arms proved nothing")
            return False
        ok &= arm("without the flag, temp/ is read: its planted shape is seen, and blocks nothing",
                  rc == 0 and bool(re.search(r"^temp/\s+0 clean\s+\|\s+1 hold a real string", out, re.M)))
        rc, out = scan("--skip-scratch")
        ok &= arm("with --skip-scratch, temp/ is not read",
                  rc == 0 and not re.search(r"^temp/", out, re.M))
        ok &= arm("...and the output SAYS so, never silently",
                  bool(re.search(r"^\s+temp/\s+not read", out, re.M)))
        ok &= arm("...while tools/ and the private tools are still read",
                  bool(re.search(r"^tools/\s+\d+ clean", out, re.M))
                  and bool(re.search(r"^private/tools/\s+\d+ clean", out, re.M)))
        (root / "tools" / "leak.py").write_text(f"CAP = '{shape}'\n", encoding="utf-8")
        rc, out = scan("--skip-scratch")
        ok &= arm("...and a planted shape in tools/ still blocks with the flag, exit 1",
                  rc == 1 and "RESULT: 1 COMMITTABLE" in out)
    gate = (ROOT / "tools" / "precommit_gate.py").read_text(encoding="utf-8")
    ok &= arm("the gate's section 5 calls the scanner with --skip-scratch",
              bool(re.search(r'run\(ROOT / "tools" / "script_committability\.py", "--skip-scratch"\)', gate)))
    return ok


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

    ok &= scratch_arms()

    print("\n" + "=" * 92)
    print("PASS -- the probe still catches a path and no longer catches an escape sequence, and the gate's "
          "call leaves out temp/ alone." if ok else "FAIL")
    print("=" * 92)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
