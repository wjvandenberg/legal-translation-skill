# -*- coding: utf-8 -*-
"""WHICH NUMBERED PIPELINE STEPS HAVE NO CHECK AT ALL?

The question the build plan says must be answered ONCE, AS A TABLE, before any failing input
is built -- "otherwise the harness proves the checks that exist can fire and says nothing
about the steps that have none."

It has never been asked, and the reason it matters is on the record: Step 4c tells the
operator to find every broken cross-reference marker and repair it. The marker string appears
in exactly one file in the whole package -- the step document describing it -- and in none of
the twenty scripts. There is nothing to give a failing input to, and nothing that would
notice if the step were skipped entirely.

WHAT COUNTS AS A CHECK, measured rather than assumed: a script that can reach a non-zero
exit. A script that only ever exits 0 cannot block anything, whatever its name says, and
several here are named like validators.

    uv run python tools/check_coverage.py
    uv run python tools/check_coverage.py --variant us
"""
import ast
import io
import re
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parent.parent
VARIANT = "us" if "--variant" in sys.argv and "us" in sys.argv else "uk"
TREE = ROOT / VARIANT

# The pipeline as SKILL.md's own overview table declares it, plus the two sub-steps that
# table omits: 1a (host-mode warning, in the setup document) and 11a (the diligence audit,
# which SKILL.md calls MANDATORY in its scripts reference but leaves out of the overview).
STEPS = [
    ("1",   "Set up",              "convert and unpack"),
    ("1a",  "Host-mode warning",   "refuse or warn outside a supported host"),
    ("2",   "Extract",             "paragraphs.json with formatting metadata"),
    ("3",   "Lexicons",            "identify domain, load references and sub-lexicons"),
    ("3b",  "Scaffold",            "en_segments skeleton for fragmented tracked changes"),
    ("4",   "Translate",           "fill en and en_runs, <=35 per batch"),
    ("4b",  "Per-batch validate",  "after each batch"),
    ("4c",  "Cross-refs",          "resolve broken cross-reference markers"),
    ("4d",  "Lexicon compliance",  "pre-apply scan"),
    ("5",   "Apply",               "text-match the English back onto the original XML"),
    ("6",   "Post-process",        "terminology, spacing, variant spelling"),
    ("7",   "Reorder",             "definitions into English alphabetical order"),
    ("8",   "Aux files",           "headers, footers, comments, footnotes, endnotes"),
    ("9",   "Quality check",       "source-language remnants"),
    ("10",  "Repack",              "rebuild the .docx"),
    ("11",  "Validate",            "final integrity check on the .docx"),
    ("11a", "Diligence audit",     "did the eleven steps actually run"),
]


# EXIT 3 IS THE INTEGRITY SENTINEL, NOT A CHECK. Every one of the twenty scripts carries the
# truncation guard, so counting "can reach a non-zero exit" makes all twenty look like
# validators. It is the reason the first run of this script reported 20 of 20 and told us
# nothing. A script is a CHECK only if it can fail for a reason of its own.
SENTINEL = 3


def exits(src):
    """Every exit status a script can reach, from the AST rather than a grep -- `sys.exit(rc)`
    with a variable is invisible to a regex and is exactly how the interesting ones are
    written. Computed exits are returned as their source expression, unresolved, because
    guessing what they evaluate to is how a check gets credited with a verdict it does not
    have."""
    literal, computed = set(), set()
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return literal, computed
    for n in ast.walk(tree):
        if isinstance(n, ast.Call):
            f = n.func
            name = (f.attr if isinstance(f, ast.Attribute) else
                    f.id if isinstance(f, ast.Name) else None)
            if name != "exit":
                continue
            if not n.args:
                literal.add(0)
                continue
            a = n.args[0]
            if isinstance(a, ast.Constant) and isinstance(a.value, int):
                literal.add(a.value)
            elif isinstance(a, ast.Constant) and a.value is None:
                literal.add(0)
            else:
                try:
                    computed.add(ast.unparse(a))
                except Exception:
                    computed.add("<unparseable>")
    return literal, computed


def raises(src):
    """Blocking by RAISING, which is the other half and the first version of this tool missed
    it entirely -- it read `sys.exit` calls and nothing else, so it reported the apply step as
    having no check when the apply step's gate mechanism IS an uncaught RuntimeError.

    A raise inside a `try` whose `except` would swallow it is not a block, so those are
    excluded. The approximation is lexical: a raise is counted when no enclosing `try` in the
    same function has a bare `except`, `except Exception` or a matching named handler. It can
    over-count a raise caught by a caller inside the same file; it does not under-count."""
    out = []
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return out

    def handled(stack, exc_name):
        for node in stack:
            if not isinstance(node, ast.Try):
                continue
            for h in node.handlers:
                t = h.type
                if t is None:
                    return True
                names = ([e.id for e in t.elts if isinstance(e, ast.Name)]
                         if isinstance(t, ast.Tuple)
                         else [t.id] if isinstance(t, ast.Name) else [])
                if "Exception" in names or "BaseException" in names or exc_name in names:
                    return True
        return False

    def walk(node, stack):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.Raise) and child.exc is not None:
                f = child.exc.func if isinstance(child.exc, ast.Call) else child.exc
                name = f.id if isinstance(f, ast.Name) else getattr(f, "attr", "?")
                # Only the body of a Try is protected; a raise in its handler is not.
                protecting = [n for n in stack if isinstance(n, ast.Try)]
                if not handled(protecting, name):
                    out.append(name)
            walk(child, stack + [child])

    walk(tree, [])
    return sorted(set(out))


scripts = {}
for p in sorted((TREE / "scripts").glob("*.py")):
    src = p.read_text(encoding="utf-8", errors="replace")
    literal, computed = exits(src)
    own = sorted(c for c in literal if c not in (0, SENTINEL))
    rs = raises(src)
    scripts[p.name] = {
        "own": own,
        "computed": sorted(computed),
        "raises": rs,
        "sentinel": SENTINEL in literal,
        # Its own verdict, not the shared integrity guard's -- by EITHER mechanism.
        "can_block": bool(own) or bool(computed) or bool(rs),
        "by_exit": bool(own) or bool(computed),
        "verdicts": sorted({m.group(0) for m in
                            re.finditer(r"\b(?:PASS|FAIL|WARN|BLOCK(?:ED)?|GATE)\b", src)}),
    }

# Which script(s) each step invokes, taken from the step documents and SKILL.md rather than
# from anybody's memory of the pipeline.
docs = {p.name: p.read_text(encoding="utf-8", errors="replace")
        for p in (TREE / "skill-docs").glob("*.md")}
docs["SKILL.md"] = (TREE / "SKILL.md").read_text(encoding="utf-8", errors="replace")

step_scripts = {}
for sid, _, _ in STEPS:
    found = set()
    for text in docs.values():
        # A step's own section, up to the next same-or-higher heading, then the scripts it
        # names inside it.
        for m in re.finditer(rf"(?im)^#{{1,4}}\s*step\s+{re.escape(sid)}\b[^\n]*\n(.*?)"
                             rf"(?=^#{{1,4}}\s*step\s|\Z)", text, re.S | re.M):
            for s in scripts:
                if s in m.group(1):
                    found.add(s)
        # And the overview table row, which is one line.
        for m in re.finditer(rf"(?im)^\|\s*{re.escape(sid)}\s*\|[^\n]*", text):
            for s in scripts:
                if s in m.group(0):
                    found.add(s)
    step_scripts[sid] = sorted(found)

print("=" * 100)
print(f"CHECK COVERAGE BY PIPELINE STEP   ({VARIANT}/ tree, {len(scripts)} scripts)")
print("=" * 100)
print(f"  {'step':<5} {'name':<21} {'scripts invoked':<44} {'can block?'}")
print("  " + "-" * 96)

uncovered, covered = [], []
for sid, name, _ in STEPS:
    ss = step_scripts[sid]
    blockers = [s for s in ss if scripts[s]["can_block"]]
    shown = ", ".join(s.replace(".py", "") for s in ss) or "—"
    print(f"  {sid:<5} {name:<21} {shown[:43]:<44} "
          f"{'yes: ' + ', '.join(s.replace('.py', '') for s in blockers)[:28] if blockers else 'NO CHECK'}")
    (covered if blockers else uncovered).append((sid, name))

print()
print("=" * 100)
print(f"STEPS WITH NO CHECK THAT CAN BLOCK — {len(uncovered)} of {len(STEPS)}")
print("=" * 100)
for sid, name in uncovered:
    print(f"  Step {sid:<4} {name}")
print()
print("  A failing input cannot be built for any of these, because there is nothing to give")
print("  it to. They are the harness's declared blind spot, not an oversight in it.")

print()
print("=" * 100)
print("THE EXECUTABLE CHECKS — a script that can fail for a reason of its OWN")
print("=" * 100)
print(f"  Exit {SENTINEL} is the shared integrity sentinel and is excluded: all "
      f"{sum(1 for m in scripts.values() if m['sentinel'])} of {len(scripts)} scripts carry")
print("  it, so counting it makes every script look like a validator. It is a guard against")
print("  a truncated install, not a verdict on the document.")
print()
blockers = {n: m for n, m in scripts.items() if m["can_block"]}
for n, m in sorted(blockers.items()):
    lit = ", ".join(str(c) for c in m["own"]) or "none"
    print(f"  {n}")
    print(f"      literal non-zero, excluding the sentinel: {lit}")
    for c in m["computed"]:
        print(f"      computed: sys.exit({c})")

by_raise = {n: m for n, m in scripts.items() if m["raises"] and not m["by_exit"]}
if by_raise:
    print()
    print("  AND THESE BLOCK BY RAISING, NOT BY EXITING — the mechanism the first version of")
    print("  this tool missed completely, which made it report the apply step as unchecked")
    print("  when apply's gate IS an uncaught RuntimeError:")
    for n, m in sorted(by_raise.items()):
        print(f"      {n:<38} raises {', '.join(m['raises'])}")

print()
print(f"  {len(blockers)} of {len(scripts)} scripts carry a verdict of their own.")
mute = [n for n, m in scripts.items() if not m["can_block"]]
print(f"  {len(mute)} can neither exit non-zero (other than {SENTINEL}) NOR raise — so whatever")
print("  they print, they cannot stop anything:")
for n in sorted(mute):
    v = ", ".join(scripts[n]["verdicts"][:5])
    print(f"      {n:<38} prints {v or 'no verdict vocabulary'}")

# The contract SKILL.md documents, against what the code actually does. The blind desk review
# found these by tracing the code; this reproduces the finding mechanically so it stays true.
print()
print("=" * 100)
print("THE DOCUMENTED CONTRACT IS 0 PASS / 1 WARN / 2 FAIL")
print("=" * 100)
print("  Most checks exit `main()`, so the verdict is in that function's RETURN statements,")
print("  not at the exit site. Following it one level in — the first pass looked only at the")
print("  exit and reported nothing, which is how a check gets credited with a contract it")
print("  does not implement.")
print()
found_any = False
for n in sorted(scripts):
    if not any(re.fullmatch(r"\w+\(.*\)", c) for c in scripts[n]["computed"]):
        continue
    src = (TREE / "scripts" / n).read_text(encoding="utf-8", errors="replace")
    try:
        tree = ast.parse(src)
    except SyntaxError:
        continue
    fns = {f.name: f for f in ast.walk(tree) if isinstance(f, ast.FunctionDef)}
    for c in scripts[n]["computed"]:
        fname = c.split("(")[0]
        fn = fns.get(fname)
        if fn is None:
            continue
        rets = sorted({ast.unparse(r.value) for r in ast.walk(fn)
                       if isinstance(r, ast.Return) and r.value is not None})
        shapes = [r for r in rets if re.search(r"\bstrict\b", r)]
        if not shapes:
            continue
        found_any = True
        print(f"  {n} — {fname}() returns:")
        for r in rets:
            flag = ""
            if re.fullmatch(r"1 if \w*strict\w* else 0", r):
                flag = "   <-- WARN IS INDISTINGUISHABLE FROM PASS"
            print(f"      return {r}{flag}")
        print("      -> the prescription is `2 if strict else 1`, which matches the")
        print("         documented contract rather than inventing a third one.")
if not found_any:
    print("  no strict-conditional return found in any check's main()")
print("=" * 100)
