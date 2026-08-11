# -*- coding: utf-8 -*-
"""ACCEPTANCE TEST — does the evidence guard block the leak, and let the work through?

THE FAILURE THIS IS BUILT AGAINST is not "the guard returns the wrong code". It is "the guard
is never invoked at all". tools/install_hooks.py already records the git-hook version of that
trap in as many words: an un-executable hook is silently ignored, it does not warn, it just
does nothing. A PreToolUse hook has the identical failure mode plus one more -- it can be
wired in settings.json under a path or a matcher that never matches, and nothing says so.

So this file checks THREE separate things, and the third is the one that matters:
  1. the guard's DECISIONS      -- blocks the leak, allows the work (with negatives both ways)
  2. the guard's WIRING         -- settings.json exists, is valid JSON, matches the Bash tool,
                                   and points at a file that is actually there
  3. the guard's INVOCABILITY   -- the exact command string in settings.json is executed, with
                                   a real hook payload on stdin, and must exit 2

    uv run python tests/test_evidence_guard.py
"""
import json
import os
import subprocess
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parent.parent
GUARD = ROOT / "tools" / "hooks" / "evidence_guard.py"
SETTINGS = ROOT / ".claude" / "settings.json"

results = []


def check(name, ok, detail=""):
    results.append((name, ok))
    print(f"  {'OK  ' if ok else 'FAIL'}  {name}{('  — ' + detail) if detail else ''}")
    return ok


def ask(command, tool="Bash", argv=None):
    """Run the guard with a real hook payload and return (exit code, stderr)."""
    payload = json.dumps({"tool_name": tool, "tool_input": {"command": command}})
    r = subprocess.run(argv or [sys.executable, str(GUARD)], input=payload,
                       capture_output=True, text=True, encoding="utf-8", errors="replace",
                       cwd=ROOT, env=dict(os.environ, CLAUDE_PROJECT_DIR=str(ROOT)))
    return r.returncode, (r.stderr or "")


# --------------------------------------------------------------------------------------
# 1. MUST BLOCK — every one of these is a real command shape that leaked, or would have.
# --------------------------------------------------------------------------------------
print("=" * 92)
print("EVIDENCE GUARD — 1. COMMANDS THAT MUST BE BLOCKED")
print("=" * 92)

MUST_BLOCK = [
    ("the exact `ls` that leaked on 2026-08-11",
     "ls ../legal-translation-logs/A1/D01/"),
    ("the exact `find -printf` that leaked",
     "find ../legal-translation-logs/A1 -maxdepth 2 -type f -printf '%f\\n'"),
    ("find piped into something else — the utility is not the first word overall",
     "cd /x && find ../legal-translation-logs -name '*.md' | sort | head -20"),
    ("tree over the private folder",
     "tree ../legal-translation-private"),
    ("cat of a file inside an evidence folder — content is worse than a name",
     "cat ../legal-translation-logs/A1/SUMMARY-D01.md"),
    ("head of the private scan list",
     "head -5 ../legal-translation-private/leakage-names.txt"),
    ("PowerShell Get-ChildItem",
     "Get-ChildItem ../legal-translation-logs -Recurse"),
    ("inline python that enumerates the directory",
     "uv run python -c \"import os; print(os.listdir('../legal-translation-logs'))\""),
    ("inline python using rglob",
     "python -c \"from pathlib import Path; print(list(Path('../legal-translation-logs')"
     ".rglob('*')))\""),
    ("an absolute path rather than a relative one",
     "ls /c/Users/x/Desktop/Personal/Coding/legal-translation-logs/A1"),
]
for label, cmd in MUST_BLOCK:
    rc, err = ask(cmd)
    check(f"blocks: {label}", rc == 2, f"exit {rc}")

check("and the refusal names the safe alternative",
      "tools/evidence_ls.py" in ask(MUST_BLOCK[0][1])[1])
check("and cites the rule it is enforcing",
      "6.5" in ask(MUST_BLOCK[0][1])[1])

# --------------------------------------------------------------------------------------
# 2. MUST ALLOW — a guard that blocks the work is a guard that gets removed.
# --------------------------------------------------------------------------------------
print("\n" + "=" * 92)
print("EVIDENCE GUARD — 2. COMMANDS THAT MUST STILL WORK")
print("=" * 92)

MUST_ALLOW = [
    ("gate_replay.py, which READS those logs and prints counts only",
     "uv run python tools/gate_replay.py"),
    ("the register validator CLAUDE.md 5.12 prescribes by path",
     "uv run python ../legal-translation-private/tools/audit_register.py"),
    ("the sanctioned lister itself — it must not block its own alternative",
     "uv run python tools/evidence_ls.py ../legal-translation-logs/A1"),
    ("an unrelated command that happens to mention nothing",
     "git status --short"),
    ("ls inside the REPOSITORY, which is not an evidence folder",
     "ls tools/"),
    ("a normal test run",
     "uv run python tests/run_tests.py"),
    ("reading a repo file whose name merely resembles the folder",
     "cat tools/gate_replay.py"),
]
for label, cmd in MUST_ALLOW:
    rc, _ = ask(cmd)
    check(f"allows: {label}", rc == 0, f"exit {rc}")

# --------------------------------------------------------------------------------------
# 3. THE WIRING — the failure mode that produces a control nobody notices is missing.
# --------------------------------------------------------------------------------------
print("\n" + "=" * 92)
print("EVIDENCE GUARD — 3. IS IT ACTUALLY WIRED IN?")
print("=" * 92)

check("the guard script exists", GUARD.exists())
check(".claude/settings.json exists", SETTINGS.exists())

cfg, entry = None, None
if SETTINGS.exists():
    try:
        cfg = json.loads(SETTINGS.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        check("settings.json is valid JSON", False, str(e))
if cfg is not None:
    check("settings.json is valid JSON", True)
    pre = cfg.get("hooks", {}).get("PreToolUse", [])
    entry = next((h for grp in pre for h in grp.get("hooks", [])
                  if "evidence_guard" in h.get("command", "")), None)
    check("a PreToolUse hook references evidence_guard", entry is not None)
    # BOTH shell tools, each as its own group with a plain single-token matcher. The first
    # version used one group with "Bash|PowerShell"; matcher syntax varies between harness
    # versions and a matcher that silently never matches is precisely the shape that produces
    # a control nobody notices is absent. Two plain entries cannot be misread.
    matched = {g.get("matcher") for g in pre
               if any("evidence_guard" in h.get("command", "") for h in g.get("hooks", []))}
    for tool in ("Bash", "PowerShell"):
        check(f"and a plain matcher covers the {tool} tool", tool in matched,
              f"matchers present: {sorted(matched)}")

# 3c. THE ONE THAT MATTERS: run the configured command string, not our own guess at it.
if entry:
    configured = entry["command"].replace("$CLAUDE_PROJECT_DIR", str(ROOT))
    referenced = None
    for tok in configured.replace('"', " ").split():
        if tok.endswith(".py"):
            referenced = Path(tok)
    check("the path in settings.json points at a file that exists",
          bool(referenced) and referenced.exists(),
          f"{referenced}" if referenced else "no .py path found in the command")

    # Execute EXACTLY what the harness would, through the shell, with a real payload.
    payload = json.dumps({"tool_name": "Bash",
                          "tool_input": {"command": "ls ../legal-translation-logs/A1"}})
    r = subprocess.run(configured, input=payload, shell=True, capture_output=True,
                       text=True, encoding="utf-8", errors="replace", cwd=ROOT,
                       env=dict(os.environ, CLAUDE_PROJECT_DIR=str(ROOT)))
    check("THE CONFIGURED COMMAND ITSELF BLOCKS THE LEAK (exit 2)", r.returncode == 2,
          f"exit {r.returncode} — {(r.stderr or '')[:120]}")

# --------------------------------------------------------------------------------------
print()
print("=" * 92)
ok = sum(1 for _, c in results if c)
print(f"RESULT: {ok} of {len(results)} checks passed")
for n, c in results:
    if not c:
        print(f"    FAILED: {n}")
print()
print("  TWO THINGS THIS DOES NOT PROVE, both stated rather than implied:")
print()
print("  1. THAT THE HOOK IS LIVE IN THE CURRENT SESSION. Settings are read at session")
print("     start, so a hook added mid-session does not fire until the next one. Measured,")
print("     not assumed: after writing settings.json, a probe command against a")
print("     NON-EXISTENT path under an evidence folder still executed. Safe probe to")
print("     repeat at the start of any session — if the hook is live it is BLOCKED, and if")
print("     it is not, `ls` merely reports a missing directory and leaks nothing:")
print("         ls ../legal-translation-logs/NO-SUCH-DIRECTORY-PROBE")
print()
print("  2. THAT THE THIRD EVIDENCE FOLDER IS COVERED. Its name is not committable, so it")
print("     is read from .claude/evidence-dirs.local — absent in a fresh clone, and")
print("     unguarded there. Said in the guard's own docstring too.")
print("=" * 92)
sys.exit(0 if ok == len(results) else 1)
