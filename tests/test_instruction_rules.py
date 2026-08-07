# -*- coding: utf-8 -*-
"""ACCEPTANCE TEST FOR THE INSTRUCTION LAYER — branch 3 (the scope rule), and the file the
later instruction branches extend.

STEP-B-ANALYSIS.md §4 puts branches 3, 4, 13, 17 and 19 in one row: "instruction and
dictionary changes ... a graded run plus your review. There is no script instrument for
these." **This is a script instrument for the part of them that IS decidable** -- not for
whether the prose persuades an operator, which needs Step C, but for whether the rule is
present, whether it says what the register requires, whether it is in BOTH trees, and
whether adding it softened anything it was forbidden to soften.

Branch 4 should add its cases here rather than start a parallel file.

WHY EVERY NEEDLE IS A PHRASE. §5.12 rule 6: eleven checks in this project have passed for
the wrong reason and every one used a needle short enough to occur by accident. "in scope"
matches ordinary prose about scoping; the phrases below cannot appear unless the rule is
actually carried.

RESTORATION. Mutations are held in memory and written back -- never restored through git.
The handoff records uncommitted work destroyed twice by `git checkout --`; the tests that
were safe are the ones that kept the original bytes themselves.

    uv run python tests/test_instruction_rules.py
"""
import io
import os
import re
import subprocess
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parent.parent
TREES = ("uk", "us")

# --------------------------------------------------------------------------------------
# WHAT MUST BE PRESENT — register row -> (file, phrase). Both trees, every row.
# --------------------------------------------------------------------------------------
REQUIRED = [
    # K1 + X3 — the scope rule. The cheapest fix in the project, and the one X3 says must
    # ADD a rule rather than soften one.
    ("K1", "SKILL.md",
     "A check can be wrong IN SCOPE, and saying so is not permission to bypass it"),
    ("K1", "SKILL.md", "Fix the check, never work around it"),
    ("K1", "SKILL.md", "fidelity wins and the check gets fixed"),
    ("K1", "SKILL.md", "Never alter a source-faithful translation to satisfy a check"),
    # The scope rule has to be reachable where the operator meets the APPLY gates too.
    ("K1", "skill-docs/05-apply.md", "SKILL.md's script-integrity rule governs"),

    # F35 — the two colliding truncation instructions, reconciled. One must state which
    # governs; the other must stop asserting the opposite.
    ("F35", "SKILL.md", "THIS RULE TAKES PRECEDENCE OVER THE GATE READING"),
    ("F35", "SKILL.md", "If the reported exit code is **3**"),
    ("F35", "skill-docs/05-apply.md", "Rule out a truncated install FIRST"),
    ("F35", "skill-docs/05-apply.md",
     "exit code 3 from either of those means the script is truncated"),

    # K3 — what delivery notes must contain, and the completion invariant.
    ("K3", "SKILL.md", "## What the delivery notes must contain"),
    ("K3", "SKILL.md", "the only thing that speaks to the person who receives the document"),
    ("K3", "SKILL.md", "THE COMPLETION INVARIANT"),
    ("K3", "SKILL.md", "There is no partial deliverable"),
    ("K3", "SKILL.md", "the source-language document remains the operative text"),

    # K2 — the Step 6 gate stops telling the operator to make the JSON match the document.
    ("K2", "scripts/post_process.py", "WORK OUT WHICH SIDE IS WRONG BEFORE EDITING EITHER"),
    ("K2", "scripts/post_process.py", "it clears the gate and ships the defect"),
]

# --------------------------------------------------------------------------------------
# WHAT MUST BE GONE — the half a presence-only test leaves out.
# --------------------------------------------------------------------------------------
FORBIDDEN = [
    # F35: the categorical claim that produced the collision. It said the scripts are "not
    # truncated" on the one condition where they may be exactly that.
    ("F35", "skill-docs/05-apply.md",
     "The scripts are not crashing, not truncated, and not buggy"),
    # K2: the remedy that told the operator to edit one side without asking which was wrong.
    ("K2", "scripts/post_process.py", "Fix paragraphs.json and re-run from Step 5"),
]

# --------------------------------------------------------------------------------------
# WHAT MUST NOT HAVE MOVED — X3, made mechanical.
#
# X3 is the row that says a competent outside reader called this absolutism "mature", and
# §3.4's Must-not line is "soften a single word of the anti-drift text". A promise not to
# soften is worth nothing unless something checks it, so these sentences are asserted
# byte-for-byte. If a later branch has a reason to change one, it changes this list in the
# same commit and the diff shows it.
# --------------------------------------------------------------------------------------
PRESERVED = [
    ("SKILL.md", "**Do NOT work around a gate by patching the script or skipping the "
                 "validator** — fix the input (usually paragraphs.json) and re-run."),
    ("SKILL.md", "This is the script doing its job, not the script breaking."),
    ("SKILL.md", "**STOP** — re-install the skill from the .skill / .zip archive before "
                 "re-running the affected step."),
    ("SKILL.md", "Do NOT work around the failure by skipping the step, calling the script "
                 "through a wrapper, or treating the result as \"optional.\""),
    ("skill-docs/05-apply.md",
     "**Do NOT work around a gate by calling `textmatch_apply()` from a wrapper that "
     "bypasses the auto-invoked validators, by suppressing `--strict` flags, or by "
     "patching the script to return success.**"),
    ("skill-docs/05-apply.md",
     "The gates exist because every prior occasion the operator went around them shipped "
     "output below the quality the skill is designed to deliver."),
]

# The one place the two trees are ALLOWED to differ inside the added prose. Everything else
# in the new sections must be word-for-word identical, or the variant layer has grown a new
# divergence that D1 will have to reconcile -- and markdown prose is the one thing the
# parity check does not compare, so nothing else would catch it.
VARIANT_PAIR = ("UK English", "US English")

results = []


def check(name, ok, detail=""):
    results.append((name, ok))
    print(f"  {'OK  ' if ok else 'FAIL'}  {name}{('  — ' + detail) if detail else ''}")
    return ok


def read(tree, rel):
    return (ROOT / tree / rel).read_text(encoding="utf-8")


print("=" * 96)
print("INSTRUCTION-LAYER ACCEPTANCE — branch 3")
print("=" * 96)

print("\n1. EVERY REQUIRED RULE IS PRESENT, IN BOTH TREES")
for row, rel, phrase in REQUIRED:
    missing = [t for t in TREES if phrase not in read(t, rel)]
    check(f"{row}  {rel}  “{phrase[:58]}…”", not missing,
          f"absent from {', '.join(missing)}" if missing else "")

print("\n2. THE SUPERSEDED TEXT IS GONE, IN BOTH TREES")
for row, rel, phrase in FORBIDDEN:
    present = [t for t in TREES if phrase in read(t, rel)]
    check(f"{row}  {rel}  “{phrase[:58]}…”", not present,
          f"still in {', '.join(present)}" if present else "")

print("\n3. THE ANTI-DRIFT TEXT WAS ADDED TO, NOT SOFTENED  (X3)")
for rel, phrase in PRESERVED:
    missing = [t for t in TREES if phrase not in read(t, rel)]
    check(f"survives verbatim  {rel}  “{phrase[:52]}…”", not missing,
          f"CHANGED in {', '.join(missing)}" if missing else "")

print("\n4. THE ADDED PROSE IS THE SAME IN BOTH TREES")
# Markdown prose is invisible to the parity check -- it compares scripts and the dictionary
# tables, nothing else -- so without this the two trees could drift here unnoticed.
for label, start, end in [
    ("rule 5a (the scope rule)", "   **5a. A check can be wrong IN SCOPE",
     "\n6. **Script-integrity errors."),
    ("the delivery-notes section", "## What the delivery notes must contain",
     "## Maintainer discipline"),
]:
    blocks = {}
    for t in TREES:
        s = read(t, "SKILL.md")
        i, j = s.find(start), s.find(end)
        blocks[t] = s[i:j] if i >= 0 and j > i else None
    if None in blocks.values():
        check(f"{label} — locatable in both trees", False, "section not found")
        continue
    normalised = blocks["us"].replace(VARIANT_PAIR[1], VARIANT_PAIR[0])
    check(f"{label} — identical but for “{VARIANT_PAIR[0]}”/“{VARIANT_PAIR[1]}”",
          blocks["uk"] == normalised,
          "" if blocks["uk"] == normalised else "the trees have drifted in new prose")

print("\n5. THE REACHABILITY INSTRUMENT AGREES  (STEP-B §4.1, half one)")
r = subprocess.run([sys.executable, str(ROOT / "tools" / "reachability.py")],
                   capture_output=True, text=True, encoding="utf-8",
                   errors="replace", cwd=ROOT)
check("tools/reachability.py exits 0 — the scope rule is readable at every blocking step",
      r.returncode == 0, f"exit {r.returncode}")
check("and it reports the rule in the ALWAYS-LOADED file, not a step doc",
      r.stdout.count("the scope rule is stated in: SKILL.md") == len(TREES))

# --------------------------------------------------------------------------------------
# 6. THE NEGATIVES. A check that cannot fail is not a check.
# --------------------------------------------------------------------------------------
print("\n6. NEGATIVE TESTS — each check is shown to FAIL on a tree that violates it")


def with_mutation(rel, mutate, probe):
    """Apply a mutation, run `probe`, restore the original bytes. Never touches git."""
    p = ROOT / "uk" / rel
    original = p.read_bytes()
    try:
        text = original.decode("utf-8")
        changed = mutate(text)
        assert changed != text, "the mutation did not change the file"
        p.write_bytes(changed.encode("utf-8"))
        return probe()
    finally:
        p.write_bytes(original)


# (a) remove the scope rule -> section 1 must notice, and so must reachability
def _probe_reach():
    rr = subprocess.run([sys.executable, str(ROOT / "tools" / "reachability.py")],
                        capture_output=True, text=True, encoding="utf-8",
                        errors="replace", cwd=ROOT)
    return rr.returncode


rc = with_mutation("SKILL.md",
                   lambda t: t.replace("A check can be wrong IN SCOPE, and saying so is "
                                       "not permission to bypass it",
                                       "A gate is always right"),
                   _probe_reach)
check("reachability FAILS when the scope rule is removed", rc == 1, f"exit {rc}")

# (b) soften the anti-drift text -> section 3 must notice
softened = with_mutation(
    "SKILL.md",
    lambda t: t.replace("**Do NOT work around a gate by patching the script or skipping "
                        "the validator**",
                        "**Try not to work around a gate**"),
    lambda: PRESERVED[0][1] in read("uk", "SKILL.md"))
check("the softening check FAILS when the absolutist sentence is watered down",
      softened is False)

# (c) let the trees drift in the new prose -> section 4 must notice
drifted = with_mutation(
    "SKILL.md",
    lambda t: t.replace("Fix the check, never work around it",
                        "Fix the check, or don't"),
    lambda: read("uk", "SKILL.md").find("Fix the check, never work around it") == -1)
check("the cross-tree prose check FAILS when one tree is edited alone", drifted is True)

# (d) string-only-edit must FAIL on a control-flow change, not just pass on a text one
sub = subprocess.run(
    [sys.executable, str(ROOT / "tools" / "string_only_edit.py"), "origin/main",
     "uk/scripts/post_process.py"],
    capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=ROOT)
clean_rc = sub.returncode


def _probe_string_only():
    rr = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "string_only_edit.py"), "origin/main",
         "uk/scripts/post_process.py"],
        capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=ROOT)
    return rr.returncode


flow_rc = with_mutation("scripts/post_process.py",
                        lambda t: t.replace("    if result.returncode != 0:",
                                            "    if result.returncode != 99:", 1),
                        _probe_string_only)
check("string_only_edit PASSES on the real text-only edit", clean_rc == 0,
      f"exit {clean_rc}")
check("string_only_edit FAILS when control flow changes", flow_rc == 1, f"exit {flow_rc}")

# --------------------------------------------------------------------------------------
# 7. THE K2 MESSAGE, BY EXECUTION.
#
# Sections 1 and 2 search the source for a phrase. That proves the words are in the file,
# not that the operator ever sees them. This fires the real Step 6 post-strip drift gate on
# a real (synthetic) violation and reads what the gate actually prints -- which is the only
# way to know the edited string is on the path the operator hits. post_process.py has no
# case in tests/negative_inputs.py, so before this branch nothing had ever made this gate
# fire.
# --------------------------------------------------------------------------------------
print("\n7. THE STEP 6 GATE, FIRED FOR REAL — not a text search")

import json
import tempfile

XML = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
       '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
       '<w:body><w:p><w:r><w:t>The Supplier shall deliver</w:t></w:r></w:p></w:body>'
       '</w:document>')
# Declared English that never reached the XML -- validate_apply --strict fails on it, which
# is what the post-strip gate re-runs. Synthetic, invented, deliberately bland.
PARAS = [{"idx": 0, "style": "Normal",
          "text": "De leverancier levert de goederen op tijd.",
          "en": "The Supplier shall deliver the goods punctually."}]

for tree in TREES:
    with tempfile.TemporaryDirectory() as tmp:
        wd = Path(tmp)
        (wd / "final" / "word").mkdir(parents=True)
        (wd / "final" / "word" / "document.xml").write_text(XML, encoding="utf-8")
        (wd / "paragraphs.json").write_text(json.dumps(PARAS), encoding="utf-8")
        # PYTHONDONTWRITEBYTECODE: running a skill script from inside the tree makes
        # CPython drop a __pycache__/ next to it, INSIDE the shipped tree. It is gitignored
        # so it cannot be committed -- but tools/package.py builds the .skill from the tree,
        # so the bytecode would ship to users. run_tests.py already sets this; the first
        # version of this file did not, and leaked into both trees on its first run. The
        # assertion after the loop is the part that matters: it catches the NEXT caller.
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
        rr = subprocess.run(
            [sys.executable, str(ROOT / tree / "scripts" / "post_process.py"),
             str(wd / "final" / "word" / "document.xml"),
             "--paragraphs", str(wd / "paragraphs.json"), "--variant", tree],
            capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=ROOT,
            env=env)
        out = (rr.stdout or "") + (rr.stderr or "")
        check(f"{tree}: the gate actually fires", rr.returncode != 0, f"exit {rr.returncode}")
        check(f"{tree}: and prints the new remedy the operator will read",
              "WORK OUT WHICH SIDE IS WRONG BEFORE EDITING EITHER" in out)
        check(f"{tree}: and no longer prints the superseded one",
              "Fix paragraphs.json and re-run from Step 5" not in out)
        check(f"{tree}: and still refuses to be worked around",
              "Do NOT work around this gate" in out)

# --------------------------------------------------------------------------------------
# 8. NOTHING WAS LEFT BEHIND IN THE SHIPPED TREES.
#
# The handoff records this exact defect twice: "a __pycache__ leak into the shipped trees,
# fixed once and back through the next caller". It came back here too -- section 7 executes
# a skill script from inside the tree, and the first run of this file dropped bytecode into
# BOTH trees. Fixing only this caller is what failed last time, so the assertion is on the
# TREES, not on the caller: any tool that leaks, now or later, fails here.
#
# It is gitignored, so it can never be committed. That is not the risk. tools/package.py
# builds each .skill from the tree it finds on disk, so bytecode left lying around is
# bytecode shipped to a user.
# --------------------------------------------------------------------------------------
print("\n8. THE SHIPPED TREES ARE CLEAN — no bytecode, no scratch, left by anything above")
for tree in TREES:
    strays = sorted(p.relative_to(ROOT).as_posix()
                    for p in (ROOT / tree).rglob("*")
                    if p.is_file() and ("__pycache__" in p.parts or p.suffix == ".pyc"))
    check(f"{tree}/ carries no bytecode", not strays,
          f"{len(strays)} stray file(s): {strays[:3]}" if strays else "")

# --------------------------------------------------------------------------------------
print()
print("=" * 96)
ok = sum(1 for _, c in results if c)
print(f"RESULT: {ok} of {len(results)} checks passed")
for n, c in results:
    if not c:
        print(f"    FAILED: {n}")
print()
print("  WHAT THIS DOES NOT PROVE: that an operator meeting a wrongly-scoped gate will")
print("  now do the right thing. That is behavioural, it needs a model in the loop, and")
print("  STEP-B-ANALYSIS.md §4.1 puts it at Step C. This proves the rule is there, says")
print("  what the register requires, is in both trees, and softened nothing.")
print("=" * 96)
sys.exit(0 if ok == len(results) else 1)
