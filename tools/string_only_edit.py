# -*- coding: utf-8 -*-
"""PROVE A SCRIPT EDIT CHANGED ONLY TEXT — no control flow, no logic, no behaviour.

CLAUDE.md §5.8: "for any change claimed to be non-behavioural, prove it". Branch 3 claims
exactly that about one script edit -- it rewords the Step 6 gate's remedy message and touches
nothing else. A diff cannot prove it; a reader saying "looks like only a string" is the kind
of assurance this project has already been bitten by.

WHAT IT PROVES. Both versions are parsed, every string literal is emptied, and the two
syntax trees are compared. If they match, the ONLY difference between the two files is the
text inside quotes: same statements, same branches, same conditions, same calls, same
arguments, same exit codes.

WHAT IT DELIBERATELY DOES NOT PROVE. That the new text is BETTER, or even sensible. A
message can be rewritten into nonsense and still pass this. It answers one question only --
"did anything except the words change?" -- and that is worth saying out loud, because a
green check is read as broader than it is.

    uv run python tools/string_only_edit.py origin/main uk/scripts/post_process.py
    uv run python tools/string_only_edit.py origin/main uk/... us/...      # several at once

Exit codes:  0 = only string literals changed · 1 = something else changed
             · 2 = could not compare (file missing at the ref, or a syntax error)
"""
import ast
import io
import subprocess
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parent.parent


class Blank(ast.NodeTransformer):
    """Empty every string literal, and collapse f-strings to their expressions only.

    THE F-STRING CASE IS THE WHOLE REASON THIS NEEDS A TRANSFORMER RATHER THAN A REGEX.
    Python merges adjacent literals at parse time, so replacing one f-string with eight
    concatenated ones yields the same single JoinedStr node with a different number of
    literal chunks inside it. Blanking each chunk in place would still leave the COUNTS
    different and report a false positive. So: drop the literal chunks entirely and keep
    only the interpolated expressions, in order. A change to any {expression} is still
    caught -- which is the part that could actually alter behaviour.
    """

    def visit_Constant(self, node):
        if isinstance(node.value, str):
            return ast.copy_location(ast.Constant(value=""), node)
        return node

    def visit_JoinedStr(self, node):
        self.generic_visit(node)
        node.values = [v for v in node.values if not isinstance(v, ast.Constant)]
        return node


def normalise(src, label):
    try:
        tree = ast.parse(src)
    except SyntaxError as e:
        print(f"  CANNOT COMPARE — {label} does not parse: {e}")
        return None
    # Docstrings are string literals too, so they are blanked with everything else. That is
    # correct for this question: a docstring change is a text change.
    return ast.dump(Blank().visit(tree), include_attributes=False)


def at_ref(ref, path):
    rel = Path(path).as_posix()
    r = subprocess.run(["git", "show", f"{ref}:{rel}"], cwd=ROOT,
                       capture_output=True)
    if r.returncode != 0:
        return None
    return r.stdout.decode("utf-8", errors="replace")


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        return 2
    ref, paths = sys.argv[1], sys.argv[2:]

    print("=" * 100)
    print(f"STRING-ONLY EDIT — is anything but the words different from {ref}?")
    print("=" * 100)

    bad = missing = 0
    for p in paths:
        old = at_ref(ref, p)
        if old is None:
            print(f"\n  {p}\n    CANNOT COMPARE — not present at {ref}")
            missing += 1
            continue
        new = (ROOT / p).read_text(encoding="utf-8")
        a, b = normalise(old, f"{ref}:{p}"), normalise(new, p)
        if a is None or b is None:
            missing += 1
            continue
        if a == b:
            same = "identical" if old == new else "differs in string literals only"
            print(f"\n  {p}\n    OK — {same}")
        else:
            print(f"\n  {p}\n    CHANGED BEYOND TEXT — the syntax trees differ once every "
                  f"string literal is emptied.\n    This edit is NOT non-behavioural.")
            bad += 1

    print("\n" + "=" * 100)
    if missing:
        print(f"  VOID — {missing} file(s) could not be compared. Not a pass.")
        print("=" * 100)
        return 2
    if bad:
        print(f"  FAIL — {bad} of {len(paths)} file(s) changed beyond their text.")
        print("=" * 100)
        return 1
    print(f"  PASS — {len(paths)} file(s) differ from {ref} in string literals and "
          f"nothing else.")
    print("  This says the PROGRAM is unchanged. It says nothing about whether the new "
          "wording is good.")
    print("=" * 100)
    return 0


if __name__ == "__main__":
    sys.exit(main())
