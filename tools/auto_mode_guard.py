#!/usr/bin/env python3
"""auto_mode_guard.py - refuse an unattended session's irreversible acts.  CHECKER VERSION 2 (2026-08-25)

If a project's copy says a lower version than this one, it is stale - see the "Checkers"
line for each version in ...\\Coding\\templates\\TEMPLATE-CHANGELOG.md and re-copy.

WHAT THIS IS. A Claude Code PreToolUse hook. It reads one tool call on stdin, decides, and
either says nothing (exit 0, the call proceeds) or REFUSES it (exit 2, and the reason goes
to the model on stderr). Wire it up with install_hooks.py, which also verifies it afterwards.

WHY IT EXISTS. AUTO MODE runs N sessions unattended. Until now the list of things such a
session may never do was PROSE - in the task prompt and in AUTO-MODE-RUN.md - and prose is
enforced by the very thing it is meant to bind. The first real hop obeyed it perfectly,
which is evidence about one obedient session and no evidence at all about a control.

WHEN IT IS LIVE, AND WHY THAT IS THE OFF SWITCH AND NOT A SEPARATE ONE. It refuses for as
long as AUTO-MODE-RUN.md reads STATUS: RUNNING - in ANY session, attended or not. It cannot
tell an unattended hop from a person, and a guard that had to would be a guard with a hole
in it: a hop that skipped its claim would be unguarded, and nothing would report that. So
the rule is the plain one. TO WORK BY HAND DURING A RUN, STOP THE RUN - one word, one file,
already the documented off switch, and stopping is what a person intervening should do
anyway. With no run live, or none armed, this hook is inert and silent.

THE SCOPE, WRITTEN DOWN, BECAUSE A GATE THAT DOES NOT STATE ITS OWN BOUNDARY HAS A SILENT ONE.

  CHECKED HERE     git push / force-push / merge / PR-open · history rewrite (amend,
                   rebase, filter-repo, reflog expire) · reset --hard and clean · deleting
                   files or branches · gh repo create/edit/delete and release/gist publish
                   · npm publish · creating or changing a scheduled task, by shell command
                   OR by tool name · the obvious MCP send/post tools.
  ALLOWED, NAMED   git commit, but ONLY on the branch AUTO-MODE-RUN.md names. A local
                   commit on a feature branch is reversible, and AUTO MODE's own rule is
                   one commit per step - forbidding it leaves a chain's work unversioned
                   until a person returns.
  NOT CHECKED      a script that deletes, sends or spends without saying so in its command
                   line · the Write and Edit tools overwriting a file · anything reached
                   through an interpreter. Those stay PROSE in AUTO-MODE-RUN.md, and that
                   file marks which rows are which.
  DATA, NOT CODE   the body of a heredoc or a PowerShell here-string is NOT judged as a
                   command UNLESS an interpreter is what reads it. A commit message
                   quoting --amend is a message; `bash <<'EOF'` really does run its body.
                   v1 judged the two alike and refused the commit documenting this guard.

FAILURE DIRECTION, DECLARED. No state file, or no run live -> allow, silently: most
sessions in most projects are not AUTO MODE. A state file that will not parse -> exit 1,
which is LOUD and NON-BLOCKING: the message reaches the transcript and the call proceeds,
because a guard that bricks every tool call on a typo is a guard that gets uninstalled.

    uv run python tools/auto_mode_guard.py --selftest    # every refusal proved BOTH ways
    echo '{"tool_name":"Bash","tool_input":{"command":"git push --force"}}' \\
        | uv run python tools/auto_mode_guard.py --probe  # ask without arming a run

EXIT CODES, AND THEY ARE THE HOOK CONTRACT, NOT THIS HOUSE'S USUAL ONE.
  0 = allow.  2 = REFUSE, stderr goes to the model.  1 = could not decide; not blocking.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from auto_mode import RUNNING, Void, find_state_file, read_state       # noqa: E402

ALLOW, REFUSE, CANNOT_DECIDE = 0, 2, 1

#: (label, pattern, why). Order matters only for which reason is reported first; every one
#: of them refuses. The patterns run against the command string, case-insensitively.
DENY_COMMANDS: list[tuple[str, str, str]] = [
    ("history rewrite", r"\bgit\s+(?:-\S+\s+)*commit\b[^\n]*--amend",
     "rewriting a commit destroys the evidence a later session would need"),
    ("history rewrite", r"\bgit\s+(?:-\S+\s+)*(?:rebase|filter-branch)\b",
     "rewriting history unattended is not reversible by reading the result"),
    ("history rewrite", r"\bgit[\s-]+filter-repo\b",
     "rewriting history unattended is not reversible by reading the result"),
    ("history rewrite", r"\bgit\s+reflog\s+expire\b",
     "the reflog is the last route back from a bad rewrite"),
    ("push", r"\bgit\s+(?:-\S+\s+)*push\b",
     "the branch reaches the remote by Wouter's hand, never unattended"),
    ("merge", r"\bgit\s+(?:-\S+\s+)*merge\b",
     "autonomy never means self-merging"),
    ("merge", r"\bgh\s+pr\s+merge\b",
     "autonomy never means self-merging"),
    ("pull request", r"\bgh\s+pr\s+create\b",
     "a pull request is outward-facing and is Wouter's to open"),
    ("discard changes", r"\bgit\s+(?:-\S+\s+)*reset\b[^\n]*--hard",
     "it throws away work that was never committed and cannot be recovered"),
    ("discard changes", r"\bgit\s+(?:-\S+\s+)*(?:clean|checkout\s+--\s|restore\s+)",
     "it throws away work that was never committed and cannot be recovered"),
    ("delete a branch", r"\bgit\s+branch\b[^\n]*\s-[dD]\b",
     "a deleted branch takes its commits with it"),
    ("delete files", r"\bgit\s+rm\b",
     "a hop may never delete - not even a file it created"),
    ("delete files", r"\b(?:rm|rmdir|unlink|shred)\b",
     "a hop may never delete - not even a file it created"),
    ("delete files", r"\bRemove-Item\b|\bClear-Content\b",
     "a hop may never delete - not even a file it created"),
    ("publish", r"\bgh\s+repo\s+(?:create|edit|delete|rename)\b|--visibility\b",
     "making something public cannot be undone: it has already been served"),
    ("publish", r"\bgh\s+(?:release|gist)\s+create\b|\bnpm\s+publish\b|\btwine\s+upload\b",
     "making something public cannot be undone: it has already been served"),
    # NARROWED AFTER ITS OWN CONFORMING ARM FAILED. The first version was \bschtasks\b, which
    # also refused `schtasks /query` - a READ. A guard that refuses reads is a guard that gets
    # worked around, and the pairing is what surfaced it: the violating arm passed perfectly.
    ("schedule", r"\bschtasks\b[^\n]*\s/(?:create|change|delete|run|end)\b"
                 r"|Register-ScheduledTask|Unregister-ScheduledTask"
                 r"|\bcrontab\s+(?:-[re]\b|[^\s-])",
     "every hop is armed up front, so a hop never needs to create one - and a chain that "
     "can extend itself has no bound"),
]

#: Tool names refused outright, by regex. Full-match against the tool name.
DENY_TOOLS: list[tuple[str, str, str]] = [
    ("schedule", r"mcp__scheduled-tasks__(create|update|delete)_scheduled_task",
     "every hop is armed up front; a chain that can extend itself has no bound"),
    ("schedule", r"Cron(Create|Delete|Update)|ScheduleWakeup",
     "every hop is armed up front; a chain that can extend itself has no bound"),
    ("publish", r"Artifact",
     "an artifact is published to a URL, and a URL that has been served cannot be unserved"),
    ("message", r"mcp__[\w-]+__(send|post)_\w+",
     "a hop may not message anyone. This catches the obvious tools by name and nothing else "
     "- a script that sends is NOT caught, which is why the rule also stands in prose"),
]

#: git commit is the one conditional allowance, so it is matched separately and LAST.
COMMIT = re.compile(r"\bgit\s+(?:-\S+\s+)*commit\b", re.I)

#: Commands that EXECUTE a heredoc or here-string body instead of reading it as data.
#: Everything else has its body treated as text, and a commit message is the common case.
INTERPRETERS = re.compile(
    r"\b(?:sh|bash|zsh|ksh|dash|ash|python[0-9.]*|perl|ruby|node|deno|pwsh|powershell"
    r"|osascript|cmd|uv|uvx|xargs|eval|source)\b", re.I)

_HEREDOC = re.compile(r"<<-?\s*(['\"]?)([A-Za-z_][\w-]*)\1")
_HERESTRING = re.compile(r"@(['\"])[ \t]*$")


def code_lines(command: str) -> list[str]:
    """The lines of a command that are CODE, whitespace-normalised, one per element.

    THIS EXISTS BECAUSE OF A LIVE FALSE REFUSAL, 2026-08-25. The rules were matched
    against `" ".join(command.split())` - one flat string. Flattening collapses newlines,
    so the `[^\\n]*` written into the amend pattern precisely to keep it on ONE line
    spanned the whole command, heredoc body included. A commit whose MESSAGE quoted the
    word --amend was refused as though it had performed one - and a commit message is
    exactly where this house discusses the acts this guard forbids. It refused the commit
    that was documenting the guard, which is the shape a person works around rather than
    reports.

    A BODY IS ONLY DATA WHEN SOMETHING READS IT AS DATA. `bash <<'EOF'` EXECUTES its body,
    so an interpreter's body stays IN. Dropping every body wholesale would be a hole
    dressed as a fix, and it is the direction a fix for a false positive always tempts.
    """
    joined = re.sub(r"\\\r?\n[ \t]*", " ", command)   # a continuation is ONE line, or a
    out: list[str] = []                               # flag on the next line escapes
    delim: str | None = None
    for raw in joined.splitlines():
        line = " ".join(raw.split())
        if delim is not None:
            if raw.strip() == delim:
                delim = None
            continue
        if not line:
            continue
        out.append(line)
        m = _HEREDOC.search(line)
        if m and not INTERPRETERS.search(line[:m.start()]):
            delim = m.group(2)
            continue
        q = _HERESTRING.search(line)
        if q and not INTERPRETERS.search(line[:q.start()]):
            delim = q.group(1) + "@"
    return out

CONFIG_SECTION = "auto_mode_guard"
DEFAULTS = {"extra_deny_commands": [], "extra_deny_tools": [], "commit_any_branch": False}


# ------------------------------------------------------------------------- the decision

def current_branch(cwd: str | None) -> str | None:
    """The branch name, or None if it cannot be read - and None must refuse, never assume.

    `git branch --show-current`, NOT `git rev-parse --abbrev-ref HEAD`. The latter fails on
    a branch with no commits yet, because HEAD is unborn and there is nothing to resolve -
    so a fresh repository on exactly the right branch read as 'cannot tell'. Found by the
    conforming arm of this script's own selftest, which is the arm a one-sided suite skips.
    An empty answer means a detached HEAD, which is also 'cannot tell'.
    """
    try:
        r = subprocess.run(["git", "branch", "--show-current"],
                           capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=15,
                           cwd=cwd or None)
    except (OSError, subprocess.SubprocessError):
        return None
    return (r.stdout.strip() or None) if r.returncode == 0 else None


def decide(tool_name: str, tool_input: dict, branch: str, cfg: dict,
           cwd: str | None = None) -> tuple[bool, str]:
    """Pure, so the selftest exercises the real judgement rather than a stand-in.

    Returns (allowed, reason). The reason is written for the model that is about to be
    refused: it names the rule, says where the rule is written down, and says what to do
    instead - because a refusal with no route forward gets worked around.
    """
    for label, pat, why in DENY_TOOLS + [("configured", p, "refused by this project's "
                                          "verify.config.json")
                                         for p in cfg.get("extra_deny_tools", [])]:
        if re.fullmatch(pat, tool_name or ""):
            return False, _refusal(label, tool_name, why)

    command = ""
    for key in ("command", "script"):
        v = (tool_input or {}).get(key)
        if isinstance(v, str):
            command = v
            break
    if not command:
        return True, ""

    # PER LINE, NOT ON ONE FLATTENED STRING - see code_lines() for the false refusal that
    # bought this. Every pattern here was written to describe a single command.
    lines = code_lines(command)
    rules = DENY_COMMANDS + [("configured", p, "refused by this project's "
                              "verify.config.json")
                             for p in cfg.get("extra_deny_commands", [])]
    for label, pat, why in rules:
        for line in lines:
            if re.search(pat, line, re.I):
                return False, _refusal(label, line[:160], why)

    commit_line = next((line for line in lines if COMMIT.search(line)), None)
    if commit_line:
        if cfg.get("commit_any_branch"):
            return True, ""
        here = current_branch(cwd)
        if here is None:
            return False, _refusal(
                "commit", commit_line[:160],
                "a commit is allowed only on the branch AUTO-MODE-RUN.md names, and the "
                "current branch could not be read - so it cannot be shown to be that one")
        if here != branch:
            return False, _refusal(
                "commit", commit_line[:160],
                f"a commit is allowed only on {branch!r}, the branch AUTO-MODE-RUN.md "
                f"names for this run. You are on {here!r}. One branch for the whole run, "
                f"never a stack")
    return True, ""


def _refusal(label: str, what: str, why: str) -> str:
    return (
        f"\n  REFUSED BY AUTO MODE BOUNDED AUTHORITY - {label}\n"
        f"    {what}\n\n"
        f"  {why}.\n\n"
        f"  This is not a permission prompt and there is no override to find. The rule is\n"
        f"  written in AUTO-MODE-RUN.md under BOUNDED AUTHORITY, and the guard is live for\n"
        f"  as long as that file reads STATUS: RUNNING.\n\n"
        f"  IF THIS ACTION LOOKS NECESSARY, THAT IS THE SIGNAL TO STOP AND HAND BACK - not\n"
        f"  to find another route to it. Record it in the decision record and end the hop.\n"
    )


# -------------------------------------------------------------------------------- driver

def load_cfg(root: Path) -> dict:
    cfg = dict(DEFAULTS)
    f = root / "verify.config.json"
    if f.exists():
        try:
            cfg.update(json.loads(f.read_text(encoding="utf-8-sig")).get(CONFIG_SECTION, {}))
        except (OSError, ValueError):
            pass                       # a broken config must not brick every tool call
    return cfg


def main(argv) -> int:
    probe = "--probe" in argv
    if "--selftest" in argv:
        return selftest()

    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except ValueError as e:
        print(f"auto_mode_guard: stdin is not JSON ({e}); allowing.", file=sys.stderr)
        return CANNOT_DECIDE

    tool_name = payload.get("tool_name", "")
    tool_input = payload.get("tool_input", {}) or {}
    cwd = payload.get("cwd") or os.getcwd()

    f = find_state_file()
    if f is None:
        return ALLOW                                   # no AUTO MODE here. Silent, and fast.
    try:
        fields, _raw, _term = read_state(f)
    except Void as e:
        print(f"auto_mode_guard: {e} - CANNOT tell whether a run is live, so this call is "
              f"NOT being checked.", file=sys.stderr)
        return CANNOT_DECIDE

    live = fields.get("STATUS", "").upper() == RUNNING
    if not live and not probe:
        return ALLOW

    allowed, reason = decide(tool_name, tool_input, fields.get("BRANCH", ""),
                             load_cfg(f.parent), cwd)
    if probe:
        print(("ALLOW" if allowed else "REFUSE") + (reason or ""))
        return ALLOW
    if allowed:
        return ALLOW
    print(reason, file=sys.stderr)
    return REFUSE


# ------------------------------------------------------------------------------ selftest

def selftest() -> int:
    """Every rule proved BOTH ways: it must refuse the act and allow its nearest neighbour.

    THE NEAREST NEIGHBOUR IS THE WHOLE POINT. A guard that refused every git command would
    pass a suite of refusals perfectly and make the mode unusable - so 'git push' is paired
    with 'git status', 'rm' with 'ls', 'gh pr create' with 'gh pr view'.
    """
    import shutil                                                       # noqa: PLC0415
    import tempfile                                                     # noqa: PLC0415

    from house_common import Case, report_pairing, run_cases            # noqa: PLC0415

    print("SELFTEST - the guard must refuse the irreversible acts and NOTHING ELSE\n")
    tmp = Path(tempfile.mkdtemp(prefix="auto_mode_guard_selftest_"))
    branch = "session/the-run"
    cfg = dict(DEFAULTS)

    # THE SHARED PROBE NEEDS A REAL REPOSITORY ON THE RIGHT BRANCH, or every conforming arm
    # containing `git commit` is refused for the wrong reason and reads as a guard defect.
    home = _repo(tmp / "on-the-run-branch", branch)

    def bash(cmd):
        def build(_d, cmd=cmd):
            return ("Bash", {"command": cmd})
        return build

    def tool(name):
        def build(_d, name=name):
            return (name, {})
        return build

    def probe(pair) -> str:
        name, inp = pair
        allowed, _why = decide(name, inp, branch, cfg, cwd=str(home))
        return "ALLOW" if allowed else "REFUSE"

    pairs = [
        ("push is refused",            "git push -u origin HEAD",      "git status --short"),
        ("force-push is refused",      "git push --force origin main", "git log --oneline -3"),
        ("merge is refused",           "git merge main",               "git diff --stat"),
        ("gh pr merge is refused",     "gh pr merge 5 --squash",       "gh pr view 5"),
        ("gh pr create is refused",    "gh pr create --fill",          "gh pr list"),
        ("amend is refused",           "git commit --amend --no-edit", "git commit -m 'ok'"),
        ("rebase is refused",          "git rebase -i HEAD~3",         "git log --graph -5"),
        ("filter-repo is refused",     "git filter-repo --email-callback x", "git shortlog -s"),
        ("reset --hard is refused",    "git reset --hard HEAD~1",      "git reset HEAD file"),
        ("git clean is refused",       "git clean -fd",                "git check-ignore -v x"),
        ("branch delete is refused",   "git branch -D old/thing",      "git branch --show-current"),
        ("rm is refused",              "rm -rf temp/scratch",          "ls -la temp"),
        ("Remove-Item is refused",     "Remove-Item -Recurse temp",    "Get-ChildItem temp"),
        ("making it public is refused", "gh repo edit --visibility public", "gh repo view"),
        ("a release is refused",       "gh release create v1",         "gh release list"),
        ("schtasks is refused",        "schtasks /create /tn hop2",    "schtasks /query /tn hop2"),
        # THE v1 FALSE REFUSAL, REPRODUCED AS A PAIR. The conforming arm is the one that
        # failed live: a commit whose MESSAGE quoted a forbidden flag was refused as if it
        # had performed it, because the command was flattened before matching.
        ("a heredoc body is data",     "bash <<'EOF'\nrm -rf temp/x\nEOF",
                                       "git commit -F - <<'EOF'\nrm -rf temp/x\nEOF"),
        ("a quoted flag is not an act", "git commit --amend --no-edit",
                                        "git commit -F - <<'EOF'\nnever use --amend\nEOF"),
        ("a continuation is one line",  "git commit \\\n--amend",
                                        "git commit \\\n-m ok"),
        ("a here-string body is data",  "pwsh -c @'\nRemove-Item temp\n'@",
                                        "git commit -F - @'\nRemove-Item is refused\n'@"),
    ]
    cases = [Case(name, probe, bad=bash(bad), good=bash(good),
                  want="REFUSE", good_want="ALLOW") for name, bad, good in pairs]

    cases += [
        Case("a scheduling TOOL is refused", probe,
             bad=tool("mcp__scheduled-tasks__create_scheduled_task"),
             good=tool("mcp__scheduled-tasks__list_scheduled_tasks"),
             want="REFUSE", good_want="ALLOW"),
        Case("publishing an artifact is refused", probe,
             bad=tool("Artifact"), good=tool("Read"),
             want="REFUSE", good_want="ALLOW"),
        Case("an MCP send tool is refused", probe,
             bad=tool("mcp__some-server__send_message"),
             good=tool("mcp__some-server__get_message"),
             want="REFUSE", good_want="ALLOW"),
        Case("a commit on ANOTHER branch is refused", _commit_elsewhere,
             bad=lambda d: _repo(d, "some/other-branch"),
             good=lambda d: _repo(d, branch),
             want="REFUSE", good_want="ALLOW"),
        Case("a commit with NO git at all is refused", _commit_nowhere,
             bad=lambda d: d,
             good=None,
             want="REFUSE",
             unpaired_reason="the conforming twin is the case above - a real repository on "
                             "the right branch. Here the point is that an UNREADABLE branch "
                             "refuses rather than assuming it is the right one"),
    ]

    ok, paired, unpaired = run_cases(cases, tmp, width=38)

    # ---- the assertion a case table cannot make: the guard is INERT when no run is live.
    print()
    inert = _live_probe(tmp, "COMPLETE", "git push --force")
    live = _live_probe(tmp, "RUNNING", "git push --force")
    good = inert == ALLOW and live == REFUSE
    ok &= good
    print(f"  {'OK  ' if good else 'MISS'} live only while STATUS is RUNNING     -> "
          f"COMPLETE: exit {inert} (allow), RUNNING: exit {live} (refuse)")

    print()
    report_pairing(paired, unpaired)
    shutil.rmtree(tmp, ignore_errors=True)
    print("\nSELFTEST: " + ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


def _repo(d: Path, branch: str) -> Path:
    """A real git repository on a named branch. Nothing is committed to it - deliberately:
    an unborn branch is the case that broke the first version of current_branch()."""
    d.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q", "-b", branch, str(d)], capture_output=True)
    return d


def _commit_elsewhere(d: Path) -> str:
    allowed, _ = decide("Bash", {"command": "git commit -m x"}, "session/the-run",
                        dict(DEFAULTS), cwd=str(d))
    return "ALLOW" if allowed else "REFUSE"


def _commit_nowhere(d: Path) -> str:
    """A directory that is not a repository: the branch cannot be read, so it must refuse."""
    allowed, _ = decide("Bash", {"command": "git commit -m x"}, "session/the-run",
                        dict(DEFAULTS), cwd=str(d / "not-a-repo"))
    return "ALLOW" if allowed else "REFUSE"


def _live_probe(tmp: Path, status: str, command: str) -> int:
    """Run the REAL entry point end to end, against a state file in the given status."""
    d = tmp / f"live-{status}"
    d.mkdir(parents=True, exist_ok=True)
    (d / "AUTO-MODE-RUN.md").write_bytes(
        ("```auto-mode\nRUN_ID: r\nN: 1\nK: 0\nSTATUS: " + status +
         "\nBRANCH: session/the-run\nHOP_ACTIVE: no\nWOKE: -\n```\n").encode("utf-8"))
    env = dict(os.environ, AUTO_MODE_RUN_FILE=str(d / "AUTO-MODE-RUN.md"))
    payload = json.dumps({"tool_name": "Bash", "tool_input": {"command": command},
                          "cwd": str(d)})
    r = subprocess.run([sys.executable, str(Path(__file__).resolve())],
                       input=payload, capture_output=True, text=True, encoding="utf-8", errors="replace", env=env)
    return r.returncode


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
