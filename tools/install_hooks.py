#!/usr/bin/env python3
"""install_hooks.py - install the hooks, and check they actually bite.  CHECKER VERSION 11 (2026-10-22)

If a project's copy says a lower version than this one, it is stale - see the "Checkers"
line for each version in ...\\Coding\\templates\\TEMPLATE-CHANGELOG.md and re-copy.

TWO KINDS OF HOOK, AND THEY FAIL DIFFERENTLY.

GIT HOOKS LIVE IN .git/hooks, WHICH IS NOT TRACKED, so they do not travel with a clone. That
makes them easy to believe in and easy to not have - and the failure is silent in two
separate ways. A hook that was never installed does nothing and says nothing. A hook that
is installed but NOT EXECUTABLE is ignored by Git without a warning, which is the worst
behaviour a control can have: every signal says the guard is there.

THE CLAUDE CODE HOOK lives in .claude/settings.local.json, which is GITIGNORED - so it does
not travel either, for two stated reasons in guard_command() below. Its silent failure is a
different one: an entry that is present and correct-looking while the script it names is
missing, broken, or has stopped refusing anything. A configured guard that cannot bite is
worse than an absent one, because the configuration reads as proof.

AND IT HAS A THIRD FAILURE THE GIT HOOKS DO NOT, which cost a session its tools before it
was understood: A GUARD THAT CANNOT START BLOCKS EVERYTHING. The hook contract reads exit 2
as "refuse this call", and a Python interpreter that cannot open its script file exits 2 as
well - so a wrong path is indistinguishable from a refusal, on every tool at once. Two
things follow, and both are asserted in the selftest: the path is ABSOLUTE, and the matcher
is NARROW enough that Read, Edit and Write are never hooked, so the repair stays reachable.

So this installs both AND verifies each one afterwards, and the verification is the point.
For the Claude hook that means firing a real forbidden call at it and requiring a refusal -
not reading the settings file back and agreeing with itself.

    uv run python tools/install_hooks.py
    uv run python tools/install_hooks.py --check     # verify only, install nothing
    uv run python tools/install_hooks.py --selftest  # prove the verification can FAIL
    uv run python tools/install_hooks.py --only purpose                    # one kind only
    uv run python tools/install_hooks.py --only purpose --guard-dir <dir>  # ...from <dir>

v4 (2026-09-24) ADDED --only AND --guard-dir, because v3 installed every kind it knew and so
could not be used by a project that keeps git hooks of its own or has declared a guard
absent - see parse_selection() below. With neither flag, behaviour is exactly v3's.

v5 (2026-09-28) FIXED THE SELFTEST IN EXACTLY THOSE PROJECTS: its cases 8 and 10 need purpose_guard.py
beside this copy, so where the guard is declared absent v4 reported case 8 as a MISS and crashed in case 10
- the selftest could never pass there. Both now print a DECLARED SKIP with the reason. Installing is unchanged.

v7 (2026-10-09) - EVERY BITE SENDS WHAT CLAUDE CODE SENDS: raw UTF-8, carrying a name no code-page read survives -
see fire(). Until then each bite sent json.dumps's ASCII escapes, the one input a hook reading its stdin as TEXT
survives, and every hook in the house read it that way. v6 was issued and withdrawn on 2026-09-30, so that number
already names other content.

v8 (2026-10-21) - THE SELFTEST RUNS THE REAL pre-push, THROUGH REAL PUSHES. hooks/pre-push now also refuses a push
no full run vouches for - cycle_evidence.py check-push, with HOUSE_PUSH_WITHOUT_FULL_RUN as its override - and
until v8 nothing here ever ran the hook it installs: cases 1-4 prove the verification on a one-line dummy. Case 12
drives the real one through push_arms(), both arms. RE-COPY hooks/pre-push WITH THIS FILE: beside cycle_evidence.py,
an older pre-push fails case 12, which is the case working.

v9 (2026-10-22) - CASE 13 SKIPS WHERE CASE 12 SKIPS. Case 12 declares a skip when no hooks/pre-push sits beside this
copy; case 13, the next one, read that same file with no existence check, so in such a copy the selftest died with
FileNotFoundError - a traceback where a DECLARED SKIP was meant. Found in a project that holds the scripts and no hooks.

v10 (2026-10-22) - ARM (e) USES THE HOOK'S OWN MAIN OVERRIDE. hooks/pre-push's full-run block invites a project to
carry it beside its own guard, and that guard keeps its own override; arm (e) pushed to main with HOUSE_ALLOW_MAIN_PUSH
only, so such a hook failed it and the project's full run went red. main_overrides() reads the names from the hook's
text, and case 14 proves arm (e) on the real hook with its override renamed - red against v9.

v11 (2026-10-22) - THREE ARMS FOR TWO FIXES TO hooks/pre-push, both red against the hook before them. (i) with no
house.python and no uv the hook ran a bare `python` - whatever the PATH holds - and now refuses, naming the fix. (j) a
tag on a commit the remote already has was refused for want of a record, though it carries nothing; it now goes. (k)
is the other direction, green both sides: a tag carrying a new commit is still checked. An arm may DECLARE A SKIP
now, printed N/A with its reason. And interpreter_missing() joins checker_missing(): an install that would refuse
every push for want of a Python says so at install time - case 15. RE-COPY hooks/pre-push WITH THIS FILE, as for v8.

WHERE THE SOURCES COME FROM. A directory named 'hooks' beside this file. In a project that
is tools/hooks/; in the shared folder it is standard-scripts/hooks/. Discovered rather
than hard-coded, so the same file works in both places without a fork.

EXIT CODES.  0 = every hook present, executable, and biting.  1 = at least one is not.
2 = could not run at all (not a git repository, or no hooks directory to install from).
"""
from __future__ import annotations

import datetime as _dt
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE / "hooks"
GUARD = HERE / "auto_mode_guard.py"


def hook_state(src: Path, dst: Path) -> tuple[str, str | None]:
    """The verdict for one hook. Returns (state, problem-or-None).

    THE THREE FAILURES ARE KEPT APART ON PURPOSE. 'missing', 'differs from source' and
    'not executable' need different fixes, and a check that collapses them into "bad"
    sends the reader looking in the wrong place.
    """
    if not dst.exists():
        return "MISSING", f"{src.name}: not installed"
    if dst.read_bytes() != src.read_bytes():
        return "STALE - differs from source", f"{src.name}: installed copy differs from the source"
    if not os.access(dst, os.X_OK):
        return "NOT EXECUTABLE", f"{src.name}: not executable, so Git will SILENTLY ignore it"
    return "installed, executable", None


def install_one(src: Path, dst_dir: Path) -> None:
    dst_dir.mkdir(parents=True, exist_ok=True)
    dst = dst_dir / src.name
    shutil.copyfile(src, dst)
    os.chmod(dst, os.stat(dst).st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


# ------------------------------------------------- the Claude Code hook, in settings.json

#: THE FILE THE ENTRY GOES IN, and it is the LOCAL one on purpose - see guard_command().
SETTINGS_REL = (".claude", "settings.local.json")

#: The tools the guard is asked about. NOT "*", and the reason is an incident rather than a
#: preference: the first version matched every tool, and when the guard could not be found
#: PYTHON EXITED 2 - which is the hook contract's BLOCK code - so every tool call was refused,
#: INCLUDING the ones needed to repair it. Bash, Edit, PowerShell and even ToolSearch were all
#: dead, and the session had to be rescued from outside. A guard that can lock a session out
#: of fixing the guard is not a guard. These are the tools that can actually perform anything
#: on the deny list; Read, Edit and Write always get through, so the repair is always reachable.
GUARD_MATCHER = r"Bash|PowerShell|Artifact|Cron\w*|ScheduleWakeup|mcp__.*"

#: THE SECOND HOOK, 2026-09-11: purpose_guard.py, which refuses an EDIT until the session has
#: recorded what it is FOR. It matches exactly the tools the comment above says must always
#: get through, so the conflict is faced here rather than discovered later.
#:
#: WHY IT IS SURVIVABLE WHERE THE 2026-08-25 LOCKOUT WAS NOT, and the difference is the whole
#: argument: that incident was fatal because the guard matched "*" - when it failed to start,
#: Python's exit 2 IS the block code, so Bash died with everything else and the session could
#: not reach the file that configured it. THIS matcher names four EDITING tools and nothing
#: else, so Bash, PowerShell, Read and ToolSearch stay open. The repair route is therefore
#: always reachable: open .claude/settings.local.json through Bash and delete the entry.
#: STATED HERE BECAUSE AN UNWRITTEN ESCAPE ROUTE IS THE SAME AS NONE - the last session that
#: needed one had to be rescued from outside.
#:
#: AND install_hooks REFUSES TO LEAVE IT INSTALLED UNLESS IT BITES, both ways, exactly as the
#: other guard is treated: it must refuse an edit with no purpose recorded AND allow one with,
#: because a hook proved only to refuse has not been shown to be anything but an outage.
PURPOSE = HERE / "purpose_guard.py"
PURPOSE_MATCHER = r"Write|Edit|NotebookEdit|MultiEdit"

#: v7: A NAME NO CODE-PAGE READ SURVIVES - cp1252 mangles the 'é', and cannot decode the second
#: byte of the 'Ł' at all. Every bite's folder or command carries it.
NON_ASCII = "Łódź-café"

#: v7: the stdin read every hook here uses - the selftest's case 11 swaps it back to text mode.
FIXED_READ = b'sys.stdin.buffer.read().decode("utf-8", errors="replace")'


def fire(script: Path, payload: dict, env: dict) -> subprocess.CompletedProcess:
    """RUN A HOOK THE WAY CLAUDE CODE RUNS IT - v7, because every hook in the house failed this.

    Claude Code writes the payload as raw UTF-8 and escapes nothing, and Python reads a PIPE in
    the machine's code page - cp1252 here, measured 2026-10-08. Until v7 each bite sent
    json.dumps's ASCII escapes, the one input a hook reading its stdin as TEXT survives, so every
    hook read it that way and every bite passed. So the payload goes raw, and the child is GIVEN
    cp1252, so the bite reproduces the defect on any machine. A bite written on this helper
    catches the NEXT hook with the defect - the reason it is a helper, not only a fix per hook."""
    env = {k: v for k, v in env.items() if k not in ("PYTHONUTF8", "PYTHONIOENCODING")}
    env["PYTHONIOENCODING"] = "cp1252"
    return subprocess.run([sys.executable, str(script)],
                          input=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                          capture_output=True, env=env, timeout=60)


def guard_command(root: Path, script: Path = None) -> str:
    """The command string the settings entry runs. AN ABSOLUTE PATH, and both halves of that
    are decisions taken after being bitten, not defaults.

    ABSOLUTE, BECAUSE A RELATIVE PATH IS RESOLVED AGAINST THE SESSION'S WORKING DIRECTORY,
    NOT AGAINST THE PROJECT ROOT - and that directory persists across calls and moves when
    anything cd's. Measured here: with the session sitting in standard-scripts/, the command
    'uv run python standard-scripts/auto_mode_guard.py' resolved to
    standard-scripts/standard-scripts/... and the hook died on every call.
    $CLAUDE_PROJECT_DIR is no fix either: cmd.exe leaves $VAR as literal text.

    AND THEREFORE IT GOES IN THE GITIGNORED settings.local.json, NEVER THE COMMITTED
    settings.json. An absolute path carries a username and a directory layout, and these
    files are copied into repositories that may become public - the tool ships, the location
    never does. It also answers the hazard the ignore rule already names in its own comment:
    a hook committed into a repository installs itself silently in whatever copies that repo.

    THE COST, STATED: the entry does not travel with a clone. Neither do the git hooks above,
    and that is what this script is for - run it once per machine, and --check reports the
    absence rather than leaving it silent.

    `script` defaults to auto_mode_guard for every existing caller; purpose_guard passes its
    own. The parameter exists rather than a second near-identical function because the two
    hooks differ ONLY in which file runs and which tools it is asked about.
    """
    script = script or GUARD
    return f'uv run python "{script.as_posix()}"'


def settings_path(root: Path) -> Path:
    return root.joinpath(*SETTINGS_REL)


def settings_entry(root: Path, script: Path = None, matcher: str = None) -> dict:
    return {"matcher": matcher or GUARD_MATCHER,
            "hooks": [{"type": "command",
                       "command": guard_command(root, script or GUARD)}]}


def settings_has_guard(settings: dict, root: Path, script: Path = None) -> bool:
    want = guard_command(root, script or GUARD)
    for group in settings.get("hooks", {}).get("PreToolUse", []) or []:
        for h in group.get("hooks", []) or []:
            if h.get("command") == want:
                return True
    return False


def install_settings_hook(root: Path, script: Path = None, matcher: str = None) -> None:
    """Merge the entry in WITHOUT disturbing anything else in the file.

    Read-modify-write, never write-fresh: this file also carries permissions and whatever
    else a project has put there, and a generator that overwrites it takes those with it.
    """
    f = settings_path(root)
    f.parent.mkdir(parents=True, exist_ok=True)
    settings = {}
    if f.exists():
        try:
            settings = json.loads(f.read_text(encoding="utf-8-sig"))
        except ValueError:
            print(f"  {f.name} is not valid JSON - not touching it")
            return
    if settings_has_guard(settings, root, script):
        return
    settings.setdefault("hooks", {}).setdefault("PreToolUse", []).append(
        settings_entry(root, script, matcher))
    f.write_bytes((json.dumps(settings, indent=2) + "\n").encode("utf-8"))


def purpose_bites(root: Path) -> tuple[bool, str]:
    """FIRE A REAL EDIT AT IT AND REQUIRE A REFUSAL - then require it to ALLOW one.

    Both arms, and the second is not a formality: a hook matching the editing tools that
    refused unconditionally would be the 2026-08-25 lockout again in a narrower form. The
    plan file is planted in a temp directory, so nothing about the real project is read.
    """
    if not PURPOSE.exists():
        return False, f"{PURPOSE.name}: the settings entry names it and it is not there"
    tmp = Path(tempfile.mkdtemp(prefix=f"purpose_bite_{NON_ASCII}_"))
    try:
        plan = tmp / "PLAN-0-bite.md"
        plan.write_bytes(b"# PLAN\n\nno purpose recorded here\n")
        env = dict(os.environ, CLAUDE_PROJECT_DIR=str(tmp))
        edit = {"tool_name": "Edit", "tool_input": {"file_path": str(tmp / "src.py")}}
        r = fire(PURPOSE, edit, env)
        if r.returncode != 2:
            return False, (f"{PURPOSE.name}: an edit with NO purpose recorded was not "
                           f"refused (exit {r.returncode}, expected 2)")
        # v7: THE BOOTSTRAP, the arm a MANGLED path breaks - a path that cannot be decoded at all
        # already failed the arm above. Writing the plan file itself must be allowed, and is
        # only if its path arrived intact.
        r0 = fire(PURPOSE, {"tool_name": "Edit", "tool_input": {"file_path": str(plan)}}, env)
        if r0.returncode != 0:
            return False, (f"{PURPOSE.name}: writing the plan file itself was not allowed (exit "
                           f"{r0.returncode}, expected 0) - its path, sent as Claude Code sends "
                           f"it, did not arrive intact")
        today = _dt.date.today().isoformat()
        plan.write_bytes(
            f"# PLAN\n\n**SESSION PURPOSE {today}** - WHAT: bite - HOW: bite - "
            f"PURPOSE: bite\n".encode("utf-8"))
        r2 = fire(PURPOSE, edit, env)
        if r2.returncode != 0:
            return False, (f"{PURPOSE.name}: it refused an edit even WITH the purpose "
                           f"recorded (exit {r2.returncode}). That is an outage, not a guard")
    except (OSError, subprocess.SubprocessError) as e:
        return False, f"{PURPOSE.name}: could not be run at all - {e}"
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return True, ""


def guard_bites(root: Path) -> tuple[bool, str]:
    """FIRE A REAL FORBIDDEN CALL AT IT AND REQUIRE A REFUSAL.

    This is the only assertion here that is about the ARTEFACT rather than the paperwork.
    Everything else - the entry is present, the file exists - is satisfied by a guard that
    has stopped working. A state file is planted in a temp directory and pointed at with
    AUTO_MODE_RUN_FILE, so nothing about the real run is read or written.
    """
    if not GUARD.exists():
        return False, f"{GUARD.name}: the settings entry names it and it is not there"
    tmp = Path(tempfile.mkdtemp(prefix=f"guard_bite_{NON_ASCII}_"))
    try:
        (tmp / "AUTO-MODE-RUN.md").write_bytes(
            b"```auto-mode\nRUN_ID: bite\nN: 1\nK: 0\nSTATUS: RUNNING\n"
            b"BRANCH: session/nowhere\nHOP_ACTIVE: no\nWOKE: -\n```\n")
        env = dict(os.environ, AUTO_MODE_RUN_FILE=str(tmp / "AUTO-MODE-RUN.md"))
        # v7: the push carries NON_ASCII, so a guard that cannot decode it exits 1 - which the
        # hook contract reads as NOT blocking, and the push goes through.
        r = fire(GUARD, {"tool_name": "Bash",
                         "tool_input": {"command": f"git push --force origin main  # {NON_ASCII}"},
                         "cwd": str(root)}, env)
        if r.returncode != 2:
            return False, (f"{GUARD.name}: a forced push was NOT refused "
                           f"(exit {r.returncode}, expected 2). The entry is configured and "
                           f"the guard does not bite")
        # ...and it must NOT refuse everything, or it is not a guard, it is an outage.
        r2 = fire(GUARD, {"tool_name": "Bash", "tool_input": {"command": "git status"},
                          "cwd": str(root)}, env)
        if r2.returncode != 0:
            return False, (f"{GUARD.name}: it refused `git status` too (exit "
                           f"{r2.returncode}). A guard that refuses everything is an outage")
        # v7: ...and a commit ON THE RUN'S BRANCH, from a folder carrying NON_ASCII, must be
        # ALLOWED - the arm a mangled-but-decodable read breaks, the branch then unreadable. The
        # push above catches only a read that cannot decode at all.
        repo = tmp / "repo"
        subprocess.run(["git", "init", "-q", "-b", "session/nowhere", str(repo)], capture_output=True,
                       stdin=subprocess.DEVNULL, timeout=60)
        r3 = fire(GUARD, {"tool_name": "Bash", "tool_input": {"command": "git commit -m bite"},
                          "cwd": str(repo)}, env)
        if r3.returncode != 0:
            return False, (f"{GUARD.name}: a commit on the run's branch was refused (exit "
                           f"{r3.returncode}, expected 0) - its folder's path, sent as Claude "
                           f"Code sends it, did not arrive intact")
    except (OSError, subprocess.SubprocessError) as e:
        return False, f"{GUARD.name}: could not be run at all - {e}"
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return True, ""


#: v8: the two overrides hooks/pre-push reads - the branch guard's, and the full-run check's.
MAIN_OVERRIDE = "HOUSE_ALLOW_MAIN_PUSH"
FULL_RUN_OVERRIDE = "HOUSE_PUSH_WITHOUT_FULL_RUN"

#: v8: what push_arms() proves, one line per arm, in the order it runs them.
PUSH_ARMS = {
    "a": "a push no full run vouches for is refused",
    "c": "an override of '1' is refused as no reason",
    "f": "a checker that cannot start refuses, never passes",
    "b": "the same push, after a full run, goes",
    "d": "an override with a reason lets it go, and prints the reason",
    "e": "main stays guarded with a record, and goes with its own override",
    "h": "a deletion carries nothing, so it is not checked",
    "i": "with no configured Python and no uv, a push refuses and names the fix",
    "j": "a tag on a commit the remote already has carries nothing, so it is not checked",
    "k": "a tag that carries a new commit is still checked",
    "g": "with no checker in the project, a push refuses",
}


def main_overrides(hook: Path) -> list:
    """v10: THE NAMES A HOOK'S OWN MAIN GUARD ANSWERS TO, read from its text - the house's always, and every
    other *_ALLOW_MAIN_PUSH it carries. hooks/pre-push's block invites a project to carry it beside its OWN
    guard, and that guard keeps its own override; arm (e) asked only for the house's, so such a hook could
    never pass it - a project adopting this file beside its own guard had a red full run for doing as invited."""
    text = hook.read_bytes().decode("utf-8", errors="replace")
    return sorted(set(re.findall(r"\b[A-Z][A-Z0-9_]*_ALLOW_MAIN_PUSH\b", text)) | {MAIN_OVERRIDE})


def _git(cwd: Path, *args, env=None) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True, encoding="utf-8",
                          errors="replace", stdin=subprocess.DEVNULL, env=env, timeout=120)


def _setup(cwd: Path, *args) -> None:
    """A SETUP step must succeed, or the arms after it fail for a reason nobody named: raised, so the
    caller prints the git command that failed rather than seven arms that 'could not push'."""
    r = _git(cwd, *args)
    if r.returncode != 0:
        raise subprocess.CalledProcessError(r.returncode, ["git", *args], r.stdout, r.stderr)


def checker_missing(root: Path, src: Path) -> str | None:
    """v8: why an installed pre-push would refuse EVERY push, or None. A pre-push that calls
    `check-push` with no cycle_evidence.py in tools/ or standard-scripts/ refuses each push for want
    of a checker - correct at push time, and only found out then unless the install says so."""
    if src.name != "pre-push" or b"check-push" not in src.read_bytes():
        return None
    if any((root / d / "cycle_evidence.py").exists() for d in ("tools", "standard-scripts")):
        return None
    return ("pre-push: it calls cycle_evidence.py check-push and there is none in tools/ or "
            "standard-scripts/, so it will refuse every push - copy the checker, or keep the old hook")


def interpreter_missing(root: Path, src: Path) -> str | None:
    """v11: the other way an installed pre-push refuses EVERY push - nothing to run its checker with. It runs
    house.python, else `uv run python`, and since v11 never a bare `python`. Read from THIS process's PATH,
    which is the install's and may not be the push's: a warning at install time, not a guarantee."""
    if src.name != "pre-push" or b"check-push" not in src.read_bytes():
        return None
    r = _git(root, "config", "--get", "house.python")
    py = r.stdout.strip() if r.returncode == 0 else ""
    if py:
        if shutil.which(py) or Path(py).is_file():
            return None
        return ("pre-push: house.python names a Python that is not there, so it will refuse every push - "
                "point git config house.python at one")
    if shutil.which("uv"):
        return None
    return ("pre-push: no house.python and no uv on this PATH, so it will refuse every push - "
            "git config house.python <path to python>")


def push_arms(hook: Path, work: Path, checker_dir: Path = HERE, only=None) -> dict:
    """v8: DRIVE A pre-push THROUGH REAL PUSHES TO A BARE REMOTE, and say per arm whether it behaved.

    REAL BECAUSE EVERY CLAIM IS ABOUT GIT: what reaches the hook's stdin, what an exit code does to
    the push, what the remote holds afterwards. Each arm is asserted on THE REMOTE - is the branch
    there, at which commit - and never on the exit code alone, which a hook that refused for the
    wrong reason would satisfy. The scratch repository holds the checker in tools/, as a project
    does, and names this interpreter in house.python, so the arms do not depend on uv being found.
    Every override is stripped from the environment - the full-run one, and each main override
    main_overrides() reads from the hook (v10) - so a developer's own setting cannot pass an arm.
    Returns {arm: (ok, what happened)} in PUSH_ARMS' order - an arm that never ran is absent.
    v10: `only` runs the named arms alone, for a case proving one - each arm sets up what it needs.
    """
    def want(arm):
        return only is None or arm in only

    remote, repo = work / "remote.git", work / "repo"
    _setup(work, "init", "-q", "--bare", str(remote))
    _setup(work, "init", "-q", "-b", "work", str(repo))
    for k, v in (("user.email", "noreply@example.invalid"), ("user.name", "selftest"),
                 ("commit.gpgsign", "false"), ("house.python", Path(sys.executable).as_posix())):
        _setup(repo, "config", k, v)
    _setup(repo, "remote", "add", "origin", str(remote))
    (repo / "tools").mkdir()
    for name in ("cycle_evidence.py", "house_common.py"):
        shutil.copyfile(checker_dir / name, repo / "tools" / name)
    (repo / ".gitignore").write_bytes(b"temp/\n__pycache__/\n")
    (repo / "a.py").write_bytes(b"print('one')\n")
    _setup(repo, "add", "-A")
    _setup(repo, "commit", "-q", "-m", "one")
    install_one(hook, repo / ".git" / "hooks")
    overrides = main_overrides(hook)
    base = {k: v for k, v in os.environ.items() if k not in (*overrides, FULL_RUN_OVERRIDE)}
    base["PYTHONDONTWRITEBYTECODE"] = "1"

    def push(*refspec, extra=None, pre=()):
        r = _git(repo, *pre, "push", "-q", "origin", *refspec, env=dict(base, **(extra or {})))
        return r.returncode, r.stdout + r.stderr

    def on_remote(branch, kind="heads"):
        r = _git(remote, "rev-parse", "--verify", "--quiet", f"refs/{kind}/{branch}")
        return r.stdout.strip() if r.returncode == 0 else None

    def commit(name, body):
        (repo / name).write_bytes(body)
        _setup(repo, "add", "-A")
        _setup(repo, "commit", "-q", "-m", name)

    def head():
        return _git(repo, "rev-parse", "HEAD").stdout.strip()

    def full():
        r = subprocess.run([sys.executable, str(repo / "tools" / "cycle_evidence.py"), "full", "--",
                            sys.executable, "-c", "pass"], cwd=str(repo), capture_output=True,
                           stdin=subprocess.DEVNULL, env=base, timeout=120)
        return r.returncode == 0

    arms = {}
    if want("a"):
        rc, _ = push("work")
        arms["a"] = (rc != 0 and on_remote("work") is None, f"exit {rc}, on the remote: {bool(on_remote('work'))}")
    if want("c"):
        rc, _ = push("work", extra={FULL_RUN_OVERRIDE: "1"})
        arms["c"] = (rc != 0 and on_remote("work") is None, f"exit {rc}, on the remote: {bool(on_remote('work'))}")
    if want("f"):
        rc, _ = push("work", pre=("-c", f"house.python={(work / 'no-such-python').as_posix()}"))
        arms["f"] = (rc != 0 and on_remote("work") is None, f"exit {rc}, on the remote: {bool(on_remote('work'))}")
    if want("b"):
        recorded = full()
        rc, _ = push("work")
        arms["b"] = (recorded and rc == 0 and on_remote("work") == head(),
                     f"recorded {recorded}, exit {rc}, the remote at HEAD: {on_remote('work') == head()}")
    if want("d"):
        (repo / "b.py").write_bytes(b"print('two')\n")
        _setup(repo, "add", "-A")
        _setup(repo, "commit", "-q", "-m", "two")
        why = "selftest: a reason of real length"
        rc, out = push("work", extra={FULL_RUN_OVERRIDE: why})
        arms["d"] = (rc == 0 and on_remote("work") == head() and why in out,
                     f"exit {rc}, the remote at HEAD: {on_remote('work') == head()}, reason printed: {why in out}")
    if want("e"):
        recorded = full()
        rc, _ = push("HEAD:refs/heads/main")
        guarded = rc != 0 and on_remote("main") is None
        rc2, _ = push("HEAD:refs/heads/main", extra={name: "1" for name in overrides})
        arms["e"] = (recorded and guarded and rc2 == 0 and on_remote("main") == head(),
                     f"recorded {recorded}, refused without its override: {guarded}, with it exit {rc2}")
    if want("h"):
        rc, _ = push(":work")
        arms["h"] = (rc == 0 and on_remote("work") is None,
                     f"exit {rc}, still on the remote: {bool(on_remote('work'))}")
    if want("i"):
        # v11: A BARE `python` IS WHATEVER THE PATH HOLDS - another interpreter, a stub that hangs, or nothing. HEAD
        # gets a record first, so a hook that falls back to one finds the push vouched for and lets it go; a stub
        # put first on the PATH answers ALLOWED for the same reason. Every folder holding uv is dropped from it.
        commit("i.py", b"print('three')\n")
        recorded = full()
        stub = work / "stub-bin"
        stub.mkdir()
        (stub / "python").write_bytes(b"#!/bin/sh\necho 'PUSH ALLOWED - a bare python stub ran'\n")
        os.chmod(stub / "python", 0o755)
        kept = [d for d in base.get("PATH", "").split(os.pathsep)
                if d and not any((Path(d) / n).exists() for n in ("uv", "uv.exe"))]
        path = os.pathsep.join([str(stub), *kept])
        if shutil.which("uv", path=path) or not shutil.which("git", path=path):
            arms["i"] = (None, "DECLARED SKIP: uv cannot be hidden from this PATH without hiding git")
        else:
            rc, out = push("HEAD:refs/heads/arm-i", extra={"PATH": path}, pre=("-c", "house.python="))
            named = "house.python" in out
            # and it does not send the reader to run the full suite, which cannot cure a missing interpreter
            misled = "Run the full suite" in out
            arms["i"] = (recorded and rc != 0 and on_remote("arm-i") is None and named and not misled,
                         f"recorded {recorded}, exit {rc}, on the remote: {bool(on_remote('arm-i'))}, "
                         f"names house.python: {named}, full-run advice: {misled}")
    if want("j"):
        # v11: the commit goes up first, with the override and no record; a tag on it then carries nothing. Each
        # new arm pushes a branch of its own, so arm (g) still finds 'work' off the remote whatever these did.
        commit("j.py", b"print('four')\n")
        rc0, _ = push("HEAD:refs/heads/arm-j", extra={FULL_RUN_OVERRIDE: "selftest: the commit goes first, unvouched"})
        _setup(repo, "tag", "-a", "-m", "selftest", "arm-j")
        rc, _ = push("refs/tags/arm-j")
        arms["j"] = (rc0 == 0 and rc == 0 and on_remote("arm-j", "tags") is not None,
                     f"commit pushed: exit {rc0}; tag exit {rc}, on the remote: {bool(on_remote('arm-j', 'tags'))}")
    if want("k"):
        # v11: the other direction - a tag on a commit the remote lacks pushes that commit, so it is checked.
        commit("k.py", b"print('five')\n")
        _setup(repo, "tag", "arm-k")
        rc, _ = push("refs/tags/arm-k")
        arms["k"] = (rc != 0 and on_remote("arm-k", "tags") is None,
                     f"exit {rc}, on the remote: {bool(on_remote('arm-k', 'tags'))}")
    if want("g"):
        # (g) LAST, because it takes the checker away. v11: HEAD is recorded here, since arm (k) leaves it unvouched -
        # so only the missing checker can refuse.
        recorded = full()
        (repo / "tools").rename(repo / "tools-away")
        rc, out = push("work")
        (repo / "tools-away").rename(repo / "tools")
        arms["g"] = (recorded and rc != 0 and on_remote("work") is None and "no cycle_evidence.py" in out,
                     f"recorded {recorded}, exit {rc}, on the remote: {bool(on_remote('work'))}, "
                     f"names the missing checker: {'no cycle_evidence.py' in out}")
    return arms


#: THE THREE KINDS --only can select, in the order they are reported. v4, 2026-09-24.
KINDS = ("git", "auto", "purpose")


def parse_selection(argv) -> tuple:
    """(kinds, guard directory, error-or-None). WHY THIS EXISTS - v4, 2026-09-24.

    v3 INSTALLED EVERY KIND IT KNEW, ALWAYS: the git hooks from hooks/, the AUTO MODE guard and
    the purpose guard. So a project that keeps GIT HOOKS OF ITS OWN, or that has DECLARED one of
    the guards absent with a reason, could not use this file at all. Measured on the first
    project to try: run as documented it would have copied the house pre-push over that
    project's own - a different file - and wired auto_mode_guard into a live PreToolUse chain
    the project had declined in its verify.config.json. NOTHING WOULD HAVE REPORTED EITHER: the
    run ends "All hooks present and executable" and exits 0, which is the answer hoped for.

    --guard-dir IS THE SAME PROJECT'S OTHER HALF. The guards are wired from BESIDE THIS FILE, so
    a project that cannot host this file in its own tools/ - it had a different installer of the
    same name - could only wire the SHARED copy, and a shared copy is one check_checkers can
    never report as stale in that project. With --guard-dir the entry names the project's copy.

    AN UNKNOWN KIND IS REFUSED, NEVER IGNORED: '--only purpse' quietly installing nothing and
    exiting 0 is exactly the silent success this file exists to stop.
    """
    only = set(KINDS)
    if "--only" in argv:
        i = argv.index("--only")
        val = argv[i + 1] if i + 1 < len(argv) else ""
        only = {k.strip() for k in val.split(",") if k.strip()}
        unknown = sorted(only - set(KINDS))
        if not only or unknown:
            return None, None, (
                f"--only takes a comma-separated list drawn from {', '.join(KINDS)}; "
                f"got {val!r}" + (f" (unknown: {', '.join(unknown)})" if unknown else ""))
    guard_dir = None
    if "--guard-dir" in argv:
        i = argv.index("--guard-dir")
        if i + 1 >= len(argv):
            return None, None, "--guard-dir needs a directory"
        guard_dir = Path(argv[i + 1]).resolve()
        if not guard_dir.is_dir():
            return None, None, f"--guard-dir: {guard_dir} is not a directory"
    return only, guard_dir, None


def main(argv) -> int:
    global GUARD, PURPOSE
    if "--selftest" in argv:
        return selftest()

    only, guard_dir, err = parse_selection(argv)
    if err:
        print(f"  {err}")
        return 2
    if guard_dir is not None:
        GUARD = guard_dir / GUARD.name
        PURPOSE = guard_dir / PURPOSE.name

    check_only = "--check" in argv
    if "git" in only and not SRC.is_dir():
        print(f"  no hooks directory at {SRC} - nothing to install")
        return 2

    root = Path.cwd()
    r = subprocess.run(["git", "rev-parse", "--git-path", "hooks"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=root)
    if r.returncode != 0:
        print("  not a git repository")
        return 2
    dst_dir = (root / r.stdout.strip()).resolve()

    problems = []
    if len(only) < len(KINDS):
        # SAID, NOT IMPLIED. A partial run that printed only the sections it ran would read
        # exactly like a full run on a project that simply has fewer hooks.
        print(f"  --only {','.join(k for k in KINDS if k in only)}: NOT CHECKED "
              f"{', '.join(k for k in KINDS if k not in only)} - this run says nothing "
              f"about them")

    if "git" in only:
        print("=" * 92)
        print("GIT HOOKS")
        print("=" * 92)
        print(f"  from {SRC}  ->  {dst_dir}")

        for src in sorted(SRC.iterdir()):
            if src.name.startswith(".") or not src.is_file():
                continue
            if not check_only:
                install_one(src, dst_dir)
            state, problem = hook_state(src, dst_dir / src.name)
            if problem:
                problems.append(problem)
            missing = checker_missing(root, src)
            if missing:
                problems.append(missing)
                state += " - BUT NO CHECKER: every push will be refused"
            no_python = interpreter_missing(root, src)
            if no_python:
                problems.append(no_python)
                state += " - BUT NO PYTHON FOR ITS CHECKER: every push will be refused"
            print(f"  {src.name:<14} {state}")

        print()
        print("  WHAT THESE ARE AND ARE NOT. They are LOCAL accident guards. They do not travel")
        print("  with a clone, they do not apply to a push from another machine or from CI, and")
        print("  either can be bypassed with --no-verify. Server-side branch protection is the")
        print("  real control - see the note at the top of hooks/pre-push for why it may not be")
        print("  available on this repository.")
        print()

    if "auto" in only:
        print("=" * 92)
        print("CLAUDE CODE HOOK - AUTO MODE bounded authority")
        print("=" * 92)
        if not GUARD.exists():
            print(f"  {GUARD.name:<22} ABSENT - nothing to install, and nothing guards a hop")
            problems.append(f"{GUARD.name}: not present in {GUARD.parent}")
        else:
            if not check_only:
                install_settings_hook(root)
            sf = settings_path(root)
            settings = {}
            if sf.exists():
                try:
                    settings = json.loads(sf.read_text(encoding="utf-8-sig"))
                except ValueError:
                    settings = {}
            wired = settings_has_guard(settings, root)
            print(f"  entry in {sf.name:<22} {'present' if wired else 'MISSING'}"
                  f"   (matcher: {GUARD_MATCHER})")
            if not wired:
                problems.append(f"auto_mode_guard: no PreToolUse entry in {sf.name}")
            bites, why = guard_bites(root)
            print(f"  it actually refuses    {'yes' if bites else 'NO'}"
                  f"   (a forced push is refused, `git status` is not)")
            if not bites:
                problems.append(why)
            print()
            print("  IT IS LIVE ONLY WHILE AUTO-MODE-RUN.md READS 'STATUS: RUNNING', in any")
            print("  session. With no run armed it is inert and silent. To work by hand during a")
            print("  run, stop the run - that is the same one-word off switch, not a second one.")
            print("  A CHANGED HOOK IS READ AT SESSION START: install it, then restart Claude.")
        print()

    if "purpose" in only:
        print("=" * 92)
        print("CLAUDE CODE HOOK - the session must record what it is FOR")
        print("=" * 92)
        if not PURPOSE.exists():
            print(f"  {PURPOSE.name:<22} ABSENT - the purpose statement stays prose, enforced")
            print(f"  {'':<22} by the very thing it binds")
            problems.append(f"{PURPOSE.name}: not present in {PURPOSE.parent}")
        else:
            if not check_only:
                install_settings_hook(root, PURPOSE, PURPOSE_MATCHER)
            sf = settings_path(root)
            settings = {}
            if sf.exists():
                try:
                    settings = json.loads(sf.read_text(encoding="utf-8-sig"))
                except ValueError:
                    settings = {}
            wired = settings_has_guard(settings, root, PURPOSE)
            print(f"  entry in {sf.name:<22} {'present' if wired else 'MISSING'}"
                  f"   (matcher: {PURPOSE_MATCHER})")
            if not wired:
                problems.append(f"purpose_guard: no PreToolUse entry in {sf.name}")
            bites, why = purpose_bites(root)
            print(f"  it actually refuses    {'yes' if bites else 'NO'}"
                  f"   (an edit with no purpose recorded; NOT one with)")
            if not bites:
                problems.append(why)
            print()
            print("  IT IS LIVE ONLY WHERE A LIVE PLAN-*.md SITS IN THE ROOT. With none, it is")
            print("  inert and silent, because most projects have no plan file and a guard that")
            print("  bricks them is one somebody uninstalls.")
            print("  IF IT EVER LOCKS YOU OUT: it matches only the four EDITING tools, so Bash,")
            print("  PowerShell and Read stay open - delete its entry from settings.local.json")
            print("  through one of those. That escape route is the reason for the narrow matcher.")
    print("=" * 92)
    if problems:
        for p in problems:
            print(f"  PROBLEM: {p}")
        return 1
    print("  All hooks present and executable." if len(only) == len(KINDS)
          else "  Every SELECTED hook present and biting - and only those were checked.")
    return 0


# -------------------------------------------------------------------------- selftest

def selftest() -> int:
    """Prove the VERIFICATION can fail - the install is not the part that can lie.

    Each case plants one of the three states and asserts the verdict. A check that has
    only ever been run against a correct installation is a check nobody has seen fail.
    """
    print("SELFTEST - the verification must catch each way a hook is silently absent\n")
    tmp = Path(tempfile.mkdtemp(prefix="install_hooks_selftest_"))
    src = tmp / "src"
    src.mkdir()
    hook = src / "pre-push"
    hook.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")

    ok = True
    dst = tmp / "hooks"
    dst.mkdir()

    # 1. missing
    state, problem = hook_state(hook, dst / "pre-push")
    good = state == "MISSING" and problem is not None
    ok &= good
    print(f"    {'OK  ' if good else 'MISS'} not installed at all        -> {state}")

    # 2. present but different
    (dst / "pre-push").write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
    state, problem = hook_state(hook, dst / "pre-push")
    good = state.startswith("STALE") and problem is not None
    ok &= good
    print(f"    {'OK  ' if good else 'MISS'} installed but differs       -> {state}")

    # 3. identical and executable - the conforming case, which a one-sided suite skips
    install_one(hook, dst)
    state, problem = hook_state(hook, dst / "pre-push")
    good = state == "installed, executable" and problem is None
    ok &= good
    print(f"    {'OK  ' if good else 'MISS'} ...and a correct install     -> {state}")

    # 4. not executable. POSIX only: on Windows os.access(X_OK) is True for any existing
    #    file, so the case cannot be planted and is DECLARED skipped rather than faked.
    if os.name == "posix":
        os.chmod(dst / "pre-push", 0o644)
        state, problem = hook_state(hook, dst / "pre-push")
        good = state == "NOT EXECUTABLE" and problem is not None
        ok &= good
        print(f"    {'OK  ' if good else 'MISS'} installed, not executable   -> {state}")
    else:
        print("    N/A  installed, not executable   -> DECLARED SKIP: os.access(X_OK) is")
        print("         always true on this platform, so the state cannot be planted here")

    # 5. THE SETTINGS ENTRY: seen when present, and NOT seen when it names something else.
    #    The second half is the one that matters - a reader that answers 'present' to any
    #    PreToolUse entry at all would call a project wired up because it has some other hook.
    root = tmp / "proj"
    (root / ".claude").mkdir(parents=True)
    empty = not settings_has_guard({}, root)
    other = not settings_has_guard(
        {"hooks": {"PreToolUse": [{"matcher": "*", "hooks": [
            {"type": "command", "command": "uv run python tools/something_else.py"}]}]}}, root)
    install_settings_hook(root)
    now_there = settings_has_guard(
        json.loads(settings_path(root).read_text(encoding="utf-8")), root)
    good = empty and other and now_there
    ok &= good
    print(f"    {'OK  ' if good else 'MISS'} settings entry seen only when it is really there"
          f" -> empty:{not empty and 'WRONG' or 'no'}, "
          f"another hook:{not other and 'WRONG' or 'no'}, after install:{now_there}")

    # 6. AND IT MUST NOT CLOBBER WHAT IS ALREADY IN THE FILE. A guard installed by deleting
    #    a project's permissions is a guard that gets removed the day it is noticed.
    root2 = tmp / "proj2"
    (root2 / ".claude").mkdir(parents=True)
    settings_path(root2).write_text(
        json.dumps({"permissions": {"defaultMode": "bypassPermissions"},
                    "hooks": {"PreToolUse": [{"matcher": "Bash", "hooks": [
                        {"type": "command", "command": "echo keep-me"}]}]}}, indent=2),
        encoding="utf-8")
    install_settings_hook(root2)
    after = json.loads(settings_path(root2).read_text(encoding="utf-8"))
    kept = (after.get("permissions", {}).get("defaultMode") == "bypassPermissions"
            and any(h.get("command") == "echo keep-me"
                    for g in after["hooks"]["PreToolUse"] for h in g["hooks"]))
    good = kept and settings_has_guard(after, root2)
    ok &= good
    print(f"    {'OK  ' if good else 'MISS'} an existing settings file survives the install"
          f" -> permissions and the other hook {'kept' if kept else 'LOST'}")

    # 7. THE TWO PROPERTIES THAT COST A SESSION ITS TOOLS. Asserted rather than remembered,
    #    because both were 'obviously fine' until the guard refused every call including the
    #    ones that could have repaired it.
    cmd = guard_command(root2)
    absolute = Path(cmd.split('"')[1]).is_absolute()
    narrow = GUARD_MATCHER != "*" and re.fullmatch(GUARD_MATCHER, "Edit") is None
    local = settings_path(root2).name.endswith(".local.json")
    good = absolute and narrow and local
    ok &= good
    print(f"    {'OK  ' if good else 'MISS'} absolute path, narrow matcher, local file"
          f" -> path {'absolute' if absolute else 'RELATIVE'}, "
          f"Edit {'exempt' if narrow else 'MATCHED'}, "
          f"{'gitignored' if local else 'COMMITTED'} file")

    # 8. v4 --only: A PROJECT WITH GIT HOOKS OF ITS OWN, AND ONE GUARD DECLARED ABSENT, MUST BE
    #    ABLE TO INSTALL THE PURPOSE GUARD ALONE. Planted in a scratch git repository holding a
    #    pre-push of its OWN: after '--only purpose' that pre-push must be byte-identical, the
    #    auto guard unwired, and the purpose guard wired and biting. RED against v3, which has
    #    no --only, overwrites the pre-push and wires both guards.
    import contextlib
    import io
    global GUARD, PURPOSE
    saved_guard, saved_purpose, saved_cwd = GUARD, PURPOSE, Path.cwd()

    def _repo(name):
        repo = tmp / name
        repo.mkdir()
        subprocess.run(["git", "init", "-q", str(repo)], capture_output=True)
        (repo / ".git" / "hooks").mkdir(parents=True, exist_ok=True)
        return repo

    def _run(repo, args):
        try:
            os.chdir(repo)
            with contextlib.redirect_stdout(io.StringIO()):
                code = main(args)
        finally:
            os.chdir(saved_cwd)
        sp = settings_path(repo)
        cfg = json.loads(sp.read_text(encoding="utf-8")) if sp.exists() else {}
        return code, cfg

    # v5: cases 8 and 10 install the PURPOSE GUARD, so they need purpose_guard.py beside this copy. A
    # project that DECLARED that guard absent does not have it - and v4 then reported case 8 as a MISS
    # and CRASHED in case 10, so the selftest could never pass there. Declared skip, as in case 4; the
    # shared copy, which has the guard, still runs both.
    no_purpose = (f"DECLARED SKIP: {saved_purpose.name} is not beside this copy (a project that declared"
                  f" it absent); the shared copy runs this case")
    if not saved_purpose.exists():
        print(f"    N/A  --only purpose leaves the project's own git hooks -> {no_purpose}")
    else:
        repo = _repo("own-hooks")
        own = b"#!/bin/sh\n# this project's OWN pre-push, not the house one\nexit 0\n"
        (repo / ".git" / "hooks" / "pre-push").write_bytes(own)
        code, cfg = _run(repo, ["--only", "purpose"])
        kept = (repo / ".git" / "hooks" / "pre-push").read_bytes() == own
        good = (code == 0 and kept and settings_has_guard(cfg, repo, PURPOSE)
                and not settings_has_guard(cfg, repo, GUARD))
        ok &= good
        print(f"    {'OK  ' if good else 'MISS'} --only purpose leaves the project's own git hooks"
              f" and the other guard alone -> exit {code}, pre-push {'kept' if kept else 'OVERWRITTEN'}")

    # 9. AN UNKNOWN KIND IS REFUSED, NEVER IGNORED. A typo that installed nothing and exited 0
    #    would be the silent success this whole file exists to stop. RUN INSIDE A GIT REPOSITORY
    #    AND ASSERTED ON WHAT WAS INSTALLED, NOT ON THE EXIT CODE ALONE: the first version of this
    #    case ran wherever the selftest happened to be, and against v3 in a folder that is not a
    #    repository it passed - v3 returned 2 for "not a git repository", the same code as a
    #    refusal. A check that passes for the wrong reason, caught by running it against the
    #    code it was written to reject.
    repo9 = _repo("unknown-kind")
    bad, cfg9 = _run(repo9, ["--only", "purpse"])
    untouched = not cfg9 and not (repo9 / ".git" / "hooks" / "pre-push").exists()
    good = bad == 2 and untouched
    ok &= good
    print(f"    {'OK  ' if good else 'MISS'} an unknown --only kind is refused and installs"
          f" nothing -> exit {bad}, {'nothing installed' if untouched else 'INSTALLED ANYWAY'}")

    # 10. --guard-dir: the entry names the copy IN THAT DIRECTORY, not the one beside this file;
    #     and a directory lacking the guard is reported ABSENT, never wired to a missing file.
    if not saved_purpose.exists():
        print(f"    N/A  --guard-dir wires THAT copy -> {no_purpose}")
    else:
        gd = tmp / "project-tools"
        gd.mkdir()
        shutil.copyfile(saved_purpose, gd / saved_purpose.name)
        repo2 = _repo("guard-dir")
        code2, cfg2 = _run(repo2, ["--only", "purpose", "--guard-dir", str(gd)])
        named = settings_has_guard(cfg2, repo2, (gd / saved_purpose.name).resolve())
        GUARD, PURPOSE = saved_guard, saved_purpose
        empty = tmp / "no-guard-here"
        empty.mkdir()
        repo3 = _repo("guard-dir-empty")
        code3, cfg3 = _run(repo3, ["--only", "purpose", "--guard-dir", str(empty)])
        GUARD, PURPOSE = saved_guard, saved_purpose
        unwired = not cfg3.get("hooks")
        good = code2 == 0 and named and code3 == 1 and unwired
        ok &= good
        print(f"    {'OK  ' if good else 'MISS'} --guard-dir wires THAT copy, and reports a missing one"
              f" -> named:{named}, empty dir exit {code3}, wired anyway:{not unwired}")

    # 11. v7: THE BITES SEND WHAT CLAUDE CODE SENDS, so they must FAIL a hook reading its stdin
    #     as text - the defect every hook in the house had until 2026-10-09. Two copies of each
    #     real guard sit side by side with the module it imports: one untouched, which must
    #     PASS (else the bite is an outage, or the copy cannot start), and one with its read
    #     swapped back to text mode, which must FAIL. That line is the only difference between
    #     them, so a failure can have no other cause. TWO text-mode shapes: STRICT, which cannot
    #     decode a 'Ł' at all, and the code page with errors REPLACED, which decodes everything
    #     wrongly - the shape only an arm judging a PATH can catch.
    text_modes = {"strict": b"sys.stdin.read()",
                  "replaced": b'(sys.stdin.reconfigure(errors="replace") or sys.stdin.read())'}
    for real, bite in ((saved_purpose, purpose_bites), (saved_guard, guard_bites)):
        if not real.exists():
            print(f"    N/A  the {real.stem} bite fails a text-mode reader -> DECLARED SKIP:"
                  f" {real.name} is not beside this copy")
            continue
        src_bytes = real.read_bytes()
        if FIXED_READ not in src_bytes:
            ok = False
            print(f"    MISS the {real.stem} bite fails a text-mode reader -> VOID: no UTF-8 read"
                  f" in it to swap")
            continue
        verdicts = {}
        bodies = {"as-is": src_bytes, **{k: src_bytes.replace(FIXED_READ, v) for k, v in text_modes.items()}}
        for kind, body in bodies.items():
            d = tmp / f"bite-{kind}-{real.stem}"
            d.mkdir()
            if (real.parent / "auto_mode.py").exists():
                shutil.copyfile(real.parent / "auto_mode.py", d / "auto_mode.py")
            (d / real.name).write_bytes(body)
            if real == saved_purpose:
                PURPOSE = d / real.name
            else:
                GUARD = d / real.name
            verdicts[kind] = bite(tmp)[0]
            GUARD, PURPOSE = saved_guard, saved_purpose
        good = verdicts["as-is"] and not any(verdicts[k] for k in text_modes)
        ok &= good
        print(f"    {'OK  ' if good else 'MISS'} the {real.stem} bite fails a text-mode reader"
              f" -> as-is {'bites' if verdicts['as-is'] else 'DOES NOT BITE'}, "
              + ", ".join(f"{k} {'CAUGHT' if not verdicts[k] else 'PASSED'}" for k in text_modes))

    # 12. v8: THE REAL pre-push, BOTH ARMS, THROUGH REAL PUSHES - push_arms() above. Every case before
    #     this one runs a one-line dummy, so nothing here had ever run the hook it installs. RED
    #     against v7's pre-push, which lets arm (a)'s push through: it guards main and nothing else.
    #     Needs cycle_evidence.py beside this copy, for the hook to call - DECLARED SKIP without it.
    real_hook = SRC / "pre-push"
    if not ((HERE / "cycle_evidence.py").exists() and (HERE / "house_common.py").exists()
            and real_hook.exists()):
        print(f"    N/A  the real pre-push, through real pushes -> DECLARED SKIP: cycle_evidence.py,"
              f" house_common.py or hooks/pre-push is not beside this copy")
    else:
        work = tmp / "push-arms"
        work.mkdir()
        try:
            arms = push_arms(real_hook, work)
        except (OSError, subprocess.SubprocessError) as e:
            arms = {}
            print(f"    MISS the real pre-push could not be driven at all - {e}")
        for arm, claim in PUSH_ARMS.items():
            good, what = arms.get(arm, (False, "NEVER RAN"))
            if good is None:                    # v11: a declared skip, with its reason
                print(f"    N/A  pre-push ({arm}) {claim} -> {what}")
                continue
            ok &= good
            print(f"    {'OK  ' if good else 'MISS'} pre-push ({arm}) {claim} -> {what}")

    # 13. v8: AN INSTALL THAT WOULD REFUSE EVERY PUSH SAYS SO AT INSTALL TIME. The real hooks go into a scratch
    #     repository with no checker - exit 1, the problem named - then a checker is planted, and the same
    #     install exits 0. Both ways, so a check that always complained would fail the second half.
    #     v9: SKIPS WHERE CASE 12 SKIPS - with no hooks/pre-push beside this copy it read a missing file and crashed.
    if not (SRC / "pre-push").exists():
        print("    N/A  an install with no checker is reported -> DECLARED SKIP: no hooks/pre-push beside this copy")
    elif b"check-push" not in (SRC / "pre-push").read_bytes():
        print("    N/A  an install with no checker is reported -> DECLARED SKIP: the pre-push beside this copy"
              " does not call check-push")
    else:
        repo13 = _repo("no-checker")
        # v11: an interpreter named, so the only thing this case varies is the checker - see case 15
        subprocess.run(["git", "-C", str(repo13), "config", "house.python", Path(sys.executable).as_posix()],
                       capture_output=True)
        bare13, _ = _run(repo13, ["--only", "git"])
        (repo13 / "tools").mkdir()
        (repo13 / "tools" / "cycle_evidence.py").write_bytes(b"# planted: its existence is what is read\n")
        with_checker, _ = _run(repo13, ["--only", "git"])
        good = bare13 == 1 and with_checker == 0
        ok &= good
        print(f"    {'OK  ' if good else 'MISS'} an install with no checker is reported -> no checker exit {bare13}"
              f" (want 1), with one exit {with_checker} (want 0)")

    # 14. v10: A PROJECT'S OWN GUARD BESIDE THE HOUSE BLOCK KEEPS ITS OWN OVERRIDE - the shape the block's own
    #     comment in hooks/pre-push invites - and main must still go with THAT one. Arm (e) alone, against the
    #     real hook with its guard's override renamed. RED against v9, whose arm (e) set HOUSE_ALLOW_MAIN_PUSH
    #     only, so the renamed guard refused the push it was meant to let through. Skips as case 12 does.
    if not ((HERE / "cycle_evidence.py").exists() and (HERE / "house_common.py").exists()
            and real_hook.exists()):
        print(f"    N/A  pre-push (e) with a project's own main override -> DECLARED SKIP: cycle_evidence.py,"
              f" house_common.py or hooks/pre-push is not beside this copy")
    else:
        own = tmp / "own-guard" / "pre-push"
        own.parent.mkdir()
        own.write_bytes(real_hook.read_bytes().replace(MAIN_OVERRIDE.encode(), b"PROJECT_ALLOW_MAIN_PUSH"))
        work14 = tmp / "push-arms-own"
        work14.mkdir()
        try:
            good, what = push_arms(own, work14, only=("e",)).get("e", (False, "NEVER RAN"))
        except (OSError, subprocess.SubprocessError) as e:
            good, what = False, f"could not be driven at all - {e}"
        ok &= good
        print(f"    {'OK  ' if good else 'MISS'} pre-push (e) with a project's own main override -> {what}")

    # 15. v11: THE OTHER WAY AN INSTALL REFUSES EVERY PUSH - nothing to run the checker with, since the hook no longer
    #     falls back to a bare `python`. A checker planted, house.python unset with the global and system config shut
    #     out, every folder holding uv off the PATH: the install exits 1 naming house.python; with house.python set
    #     to this interpreter, 0. Both ways, as case 13. RED against v10, which never asked.
    if not (SRC / "pre-push").exists() or b"check-push" not in (SRC / "pre-push").read_bytes():
        print("    N/A  an install with no Python for its checker is reported -> DECLARED SKIP: no pre-push beside"
              " this copy that calls check-push")
    else:
        repo15 = _repo("no-python")
        (repo15 / "tools").mkdir()
        (repo15 / "tools" / "cycle_evidence.py").write_bytes(b"# planted: its existence is what is read\n")
        empty_cfg = tmp / "empty.gitconfig"
        empty_cfg.write_bytes(b"")
        names = ("PATH", "GIT_CONFIG_GLOBAL", "GIT_CONFIG_NOSYSTEM")
        saved_env = {k: os.environ.get(k) for k in names}
        try:
            os.environ["PATH"] = os.pathsep.join(
                d for d in (saved_env["PATH"] or "").split(os.pathsep)
                if d and not any((Path(d) / n).exists() for n in ("uv", "uv.exe")))
            os.environ["GIT_CONFIG_GLOBAL"] = str(empty_cfg)
            os.environ["GIT_CONFIG_NOSYSTEM"] = "1"
            if shutil.which("uv") or not shutil.which("git"):
                print("    N/A  an install with no Python for its checker is reported -> DECLARED SKIP: uv cannot be"
                      " hidden from this PATH without hiding git")
            else:
                buf = io.StringIO()
                try:
                    os.chdir(repo15)
                    with contextlib.redirect_stdout(buf):
                        bare15 = main(["--only", "git"])
                finally:
                    os.chdir(saved_cwd)
                named = "house.python" in buf.getvalue()
                subprocess.run(["git", "-C", str(repo15), "config", "house.python", Path(sys.executable).as_posix()],
                               capture_output=True)
                with_python, _ = _run(repo15, ["--only", "git"])
                good = bare15 == 1 and named and with_python == 0
                ok &= good
                print(f"    {'OK  ' if good else 'MISS'} an install with no Python for its checker is reported -> none"
                      f" exit {bare15} (want 1), names house.python: {named}, with one exit {with_python} (want 0)")
        finally:
            for k, v in saved_env.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v

    shutil.rmtree(tmp, ignore_errors=True)
    print("\nSELFTEST: " + ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
