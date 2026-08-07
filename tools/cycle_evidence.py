# -*- coding: utf-8 -*-
"""THE CYCLE GATE — evidence that VERIFY and TEST actually ran, bound to what is committed.

§5.1 requires the cycle to produce artefacts rather than intentions. This is the artefact.
It is the only part of that rule that does not depend on anyone remembering it, which is the
point: the rule was read and skipped past three times in one session.

WHAT IT DOES. It records that a verification or test command was RUN, that it EXITED 0, and
WHICH CONTENT it ran against. The pre-commit hook then refuses a commit when the working
tree no longer matches the content that evidence was recorded against.

WHY THE CONTENT HASH MATTERS, AND IT IS THE WHOLE DESIGN. A commit-message trailer saying
"Verified: yes" costs nothing to type and proves nothing. Evidence here is bound to a hash of
the working tree, so editing a file after testing it INVALIDATES the evidence automatically.
You cannot test, then change the code, then commit. That is the failure this is built for --
it is what happened when fixtures were committed without the code that generated them.

WHAT IT DELIBERATELY DOES NOT DO. It does not check that the tests were GOOD. Nothing can.
Two of this project's negative tests passed while failing to make their own violation, and no
gate would have seen it. This proves a command ran against this content and exited 0 -- which
is strictly more than the current state, and strictly less than a guarantee. Say so plainly
rather than let it be read as one.

    uv run python tools/cycle_evidence.py verify -- uv run python tests/run_tests.py
    uv run python tools/cycle_evidence.py test   -- uv run python tools/parity_check.py
    uv run python tools/cycle_evidence.py status
    uv run python tools/cycle_evidence.py check          # what the hook calls
    uv run python tools/cycle_evidence.py na verify "no skill file changes; §4 measurement-only"
"""
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parent.parent
# Gitignored: evidence is local, per-working-tree, and must never be committable -- a
# committed pass is a pass someone else can inherit without earning.
STORE = ROOT / "temp" / ".cycle-evidence.json"
PHASES = ("verify", "test")


def worktree_hash():
    out = subprocess.run(["git", "diff", "HEAD", "--binary"],
                         capture_output=True, cwd=ROOT).stdout
    return hashlib.sha256(out).hexdigest()


def branch():
    return subprocess.run(["git", "branch", "--show-current"], capture_output=True,
                          text=True, cwd=ROOT).stdout.strip()


def load():
    if STORE.exists():
        try:
            return json.loads(STORE.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    return {}


def save(d):
    STORE.parent.mkdir(parents=True, exist_ok=True)
    STORE.write_text(json.dumps(d, indent=1, sort_keys=True), encoding="utf-8")


def record(phase, cmd):
    """Run the command, and record it ONLY if it exits 0."""
    print(f"  [{phase}] {' '.join(cmd)}")
    sys.stdout.flush()
    rc = subprocess.run(cmd, cwd=ROOT).returncode
    d = load()
    b = branch()
    if rc != 0:
        print(f"  [{phase}] exit {rc} — NOT recorded. A failing command is not evidence.")
        return rc
    d.setdefault(b, {})[phase] = {
        "command": " ".join(cmd),
        "exit": rc,
        "content": worktree_hash(),
        "when": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "declared_na": False,
    }
    save(d)
    print(f"  [{phase}] exit 0 — recorded against the current content.")
    return 0


def declare_na(phase, reason):
    """A declared N/A discharges the requirement. Silence does not."""
    if not reason or len(reason) < 15:
        print("  a declared N/A needs a REASON, not a word. Refused.")
        return 1
    d = load()
    d.setdefault(branch(), {})[phase] = {
        "command": None, "exit": None, "content": worktree_hash(),
        "when": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "declared_na": True, "reason": reason,
    }
    save(d)
    print(f"  [{phase}] declared N/A: {reason}")
    return 0


def check():
    b = branch()
    d = load().get(b, {})
    # THE SAME HASH THE EVIDENCE WAS RECORDED AGAINST. The first version recorded against the
    # worktree and checked against the STAGED tree, which differ the moment anything is
    # unstaged — so evidence could never match and the gate refused everything. Found by its
    # own negative test, which is the only reason the test earned its place.
    #
    # The worktree is the right anchor because it is what the commands actually ran against.
    # A partially staged commit is a SUBSET of what was tested, which is safe; the unsafe
    # case is committing something never tested, and that cannot happen while the worktree
    # hash matches.
    h = worktree_hash()
    missing, stale = [], []
    for p in PHASES:
        e = d.get(p)
        if not e:
            missing.append(p)
        elif e["content"] != h:
            stale.append(p)

    print("=" * 88)
    print(f"CYCLE EVIDENCE — branch {b or '(detached)'}")
    print("=" * 88)
    for p in PHASES:
        e = d.get(p)
        if not e:
            state = "MISSING"
        elif e["content"] != h:
            state = "STALE — the content changed after this ran"
        elif e["declared_na"]:
            state = f"declared N/A — {e['reason'][:52]}"
        else:
            state = f"ok — {e['command'][:52]}"
        print(f"  {p.upper():<7} {state}")

    if missing or stale:
        print()
        print("  COMMIT BLOCKED.")
        if missing:
            print(f"    no evidence for: {', '.join(missing)}")
        if stale:
            print(f"    evidence is stale for: {', '.join(stale)} — you changed files after")
            print("    running it, so it no longer describes what you are committing.")
        print()
        print("    uv run python tools/cycle_evidence.py verify -- <your verify command>")
        print("    uv run python tools/cycle_evidence.py test   -- <your test command>")
        print("    uv run python tools/cycle_evidence.py na verify \"<why it does not apply>\"")
        print()
        print("  This proves a command RAN against this content and exited 0. It does not")
        print("  prove the command was a good one — nothing can. Two of this project's own")
        print("  negative tests once passed while failing to make their own violation.")
        print("=" * 88)
        return 1
    print("\n  Both phases have evidence matching the current working tree.")
    print("=" * 88)
    return 0


def main(argv):
    if not argv:
        print(__doc__.strip())
        return 2
    cmd = argv[0]
    if cmd == "check":
        return check()
    if cmd == "status":
        print(json.dumps(load().get(branch(), {}), indent=1))
        return 0
    if cmd == "na":
        return declare_na(argv[1], " ".join(argv[2:]))
    if cmd in PHASES:
        rest = argv[1:]
        if rest and rest[0] == "--":
            rest = rest[1:]
        if not rest:
            print("  give a command to run after --")
            return 2
        return record(cmd, rest)
    print(f"  unknown: {cmd}")
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
