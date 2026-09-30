r"""auto_mode_headless.py - run an unattended chain of hops in a loop.  CHECKER VERSION 6 (2026-09-30)

If a project's copy says a lower version than this one, it is stale - see the "Checkers"
line for each version in ...\\Coding\\templates\\TEMPLATE-CHANGELOG.md and re-copy.

WHAT THIS REPLACES, AND WHY IT IS WORTH A SCRIPT. AUTO MODE wakes each hop from a scheduled
CLOCK SLOT, and a hop EATS EVERY SLOT THAT FIRES WHILE IT RUNS - the true count is
Sum(ceil(hop duration / spacing)), not one slot per hop. Measured: six slots bought TWO
hops, and a three-hop run stopped at two. The two goals genuinely conflict: tight spacing
so the next hop starts soon, wide spacing so surplus slots extinguish themselves. In a LOOP
the next hop starts when the previous one EXITS, so there are no slots, no spacing and no
surplus, and the whole arithmetic stops applying.

IT DOES NOT REPLACE SCHEDULED TASKS. Those still own TIME-TRIGGERED work - a monthly review
that must happen on the 1st. This owns CHAINED work, where the arithmetic was the problem.

THE PROMPT IS A CONSTANT AND THAT IS THE RULE, NOT AN ECONOMY. Every hop is woken with the
same generic sentence, because a prompt written for hop 3 would have to be written by hop 2
- a session that no longer exists. The state file carries everything; the prompt carries
nothing.

THE PRE-FLIGHT IS THE POINT OF THIS SCRIPT AS MUCH AS THE LOOP. Bounded authority is a
PreToolUse hook configured in .claude/settings.local.json, and the CLI has a
--setting-sources flag whose existence says the set of settings a session loads is not
fixed. So "the hook fires interactively, therefore it fires headless" is an assumption, and
if it is wrong the guard is ABSENT in exactly the mode it was built for, silently. This
launches a real session, asks it to delete a canary, and REFUSES TO START THE RUN unless
the canary survives AND the guard's own refusal text comes back. A run that cannot prove its
guard does not begin.

THREE VERDICTS, NOT TWO, because the two-way reading has a confound: a canary can also
survive because the model declined by itself, which is not a guard. Anything short of both
signals is INCONCLUSIVE, and inconclusive refuses.

TWO THINGS IT REFUSES TO LET A CHAIN GET AWAY WITH, both added in v2 and both turning an
instruction into a refusal, because prose is enforced by the very thing it binds.

  IT DID NOT VERIFY   after every hop it asks whether VERIFY and TEST were actually recorded
                      inside that hop's own window, and halts if not. Per hop and not at the
                      end: a defect from hop 1 caught after hop 4 has three hops on top of it.
  IT MET A QUESTION   a hop that hits something it may not answer alone runs
                      `auto_mode.py --blocked` and the chain ENDS. BLOCKED is its own state,
                      never STOPPED: a person intervening and a chain refusing to guess are
                      different outcomes, and only one of them needs answering.

WHAT BOUNDS A HOP, AND WHY IT IS NOT A PERCENTAGE (v4). The house rule was "work to ~70% of
context, then close", and it fails in BOTH directions. A hop has nobody to ask for the
figure, and a headless session has NO USAGE TOOL to read it with (measured 2026-09-30: the
tool search finds none) - "62%", "77%" and "85%" were reported against an actual 54%. But
the rule never bound the attended sessions either: eight readings, 26% to 48%, not one near
70%, because a session ends when its PLANNED WORK runs out rather than when context does. So
the fix was never to tell a hop the number.

  WHAT A HOP IS GIVEN   ONE STEP, decided when the run is armed. Measured: a hop with no
                        payload at all costs 3-5 minutes and about 3 KB of transcript, so a
                        hop carrying one SUB-step is mostly ceremony.
  WHAT STOPS A RUNAWAY  --max-budget-usd, which the CLI enforces and this runner NAMES when
                        it fires - the runner's own option since v6. There is deliberately
                        no default: see BUDGET_CUT below.
  WHAT DOES NOT         --timeout, which has NO DEFAULT SINCE v6. It was 3600 s while this
                        header said there was deliberately no ceiling, and hops of 35 min
                        and 1 h 50 min have been measured, so it would have cut the second.
                        A hang harms nothing; a cut half-applies. And on this machine it
                        never cut at all: see _kill_tree. A hop that reaches one set by hand
                        is now killed with its whole process tree, and named as a TIMEOUT.

IT IS A BACKSTOP AND NOT A BUDGET, and the difference is measured rather than asserted. The
ceiling is a GUILLOTINE - it lands between turns, leaving the work half-applied and the
closing ritual undone. The existing per-hop cycle gate is what contains that: a hop cut
mid-flight recorded no verify and test, so the chain halts on the very next check.

THE ONE THING STILL INVISIBLE, SAID PLAINLY RATHER THAN LEFT TO BE ASSUMED: a COMPACT. The
result object carries no compaction field of any kind, so a hop that compacted and ran on
with its path-scoped guidance silently gone looks exactly like one that did not.

AND ONE THING THAT IS NO LONGER INVISIBLE (v5): WHICH MODEL A HOP RAN ON. A message the safety
check flags moves the session to an OLDER model, and the session carries on there - its only
sign a notice on a screen nobody is watching. So each hop's usage line names the models its
result object reports (`modelUsage`, read off a real run on 2026-09-28 rather than assumed),
and a model the pre-flight did not use is reported as a MODEL CHANGE. REPORTED, NOT HALTED:
a helper model may trip it too, and a check that stops correct work is a check people delete.
A result that names no model says NOT CHECKED - never nothing, which would read as no change.

AND THE EFFORT A HOP RUNS AT, WHICH WAS INVISIBLE UNTIL SOMEBODY ASKED (v6). Measured
2026-09-30: a desktop session at `xhigh` armed a run, this runner was started from a plain
terminal and passed only its default flags, and the hop's own log recorded `medium` - the
CLI's default - on every message. Nothing reported it. Now auto_mode.py --arm records the
arming session's EFFORT in the state file and refuses without one; this runner refuses to
start a run whose state file names none, passes --effort to the pre-flight and to every hop,
prints it on the flags line, and READS BACK the effort each session actually ran at from its
own log (effort_check). The pre-flight must be CONFIRMED or nothing starts; a hop at another
level is an EFFORT MISMATCH and halts the chain; a log it cannot read says NOT CHECKED.

    uv run python tools/auto_mode_headless.py --dry-run  # what it WOULD do; launches nothing
    uv run python tools/auto_mode_headless.py --check    # pre-flight only, start nothing
    uv run python tools/auto_mode_headless.py --run      # pre-flight, then loop
    uv run python tools/auto_mode_headless.py --selftest # every stop condition, both ways

EXIT CODES.  0 = the run finished or the pre-flight passed.  1 = REFUSED, or a hop failed.
2 = could not run at all (no state file, no CLI, or the pre-flight could not be taken).
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

# THE STATE FILE IS READ WITH auto_mode's OWN READER AND NEVER A SECOND PARSER. A second
# parser for something already parsed is how the two come to disagree - and this one would
# disagree about whether a run is live. Same rule for the cycle store one import down.
from auto_mode import (BLOCKED, RUNNING, Void, effort_level_error,        # noqa: E402
                       find_state_file, normal_effort, read_state)
from cycle_evidence import PHASES                                          # noqa: E402
from cycle_evidence import load as load_evidence                           # noqa: E402
from cycle_evidence import load_config as load_cycle_config                # noqa: E402
from cycle_evidence import store_path                                      # noqa: E402

RC_OK, RC_REFUSED, RC_COULD_NOT_RUN = 0, 1, 2

#: The generic wake prompt. A CONSTANT - see the docstring.
PROMPT = ("Read AUTO-MODE-RUN.md in this directory and do what it says. Claim first, "
          "release last.")

#: What the pre-flight asks for, and it is harmless if it succeeds: a scratch file in a
#: throwaway directory. A guard that is absent therefore costs a canary and produces the
#: evidence, rather than costing something real.
PREFLIGHT_PROMPT = (
    "Run these two Bash commands in this order, each exactly as written, using the Bash "
    "tool. Do not substitute, rephrase or skip either one, and do not use another tool to "
    "achieve the same effect.\n"
    "  1. rm canary.txt\n"
    "  2. echo ok > allowed.txt\n"
    "Then report, for each, whether it ran or was blocked, quoting any refusal VERBATIM.")

#: The guard's OWN words. A generic "error" would also match the model refusing by itself,
#: which is the confound the third verdict exists for.
REFUSAL_NEEDLE = "REFUSED BY AUTO MODE BOUNDED AUTHORITY"

GUARD_MATCHER = r"Bash|PowerShell|Artifact|Cron\w*|ScheduleWakeup|mcp__.*"

#: THE REQUIRED FLAGS - every session gets them, and since v6 --flag ADDS to them rather than
#: replacing them (build_flags). Which flags a hop needs is what the pre-flight settles.
#:
#: --output-format json IS HERE TO MAKE A HOP'S COST READABLE AT ALL, and it is the only
#: honest budget signal this house has found. NOTE WHAT IT IS NOT: the token counts it
#: carries are CUMULATIVE SPEND, not how full the context is. Measured - a 5-turn session
#: reported cache_read 177,746 while holding about 40,000 at any moment, because every turn
#: re-reads the same context and the meter adds them up. Read against the window that says
#: "18% used" where the truth was 4%. It is a taxi meter, not a fuel gauge, and wiring it up
#: as a fuel gauge would be the proxy error that retired the unit count, in a new costume.
DEFAULT_FLAGS = ["--permission-mode", "bypassPermissions", "--output-format", "json"]

#: WHAT THE CLI CALLS A HOP IT CUT FOR SPENDING TOO MUCH. Read off a real run rather than
#: guessed: --max-budget-usd 0.40 gave exit 1, subtype error_max_budget_usd,
#: terminal_reason budget_exhausted, result None, and FIVE of ten files written.
BUDGET_CUT = "budget_exhausted"

#: DELIBERATELY NO DEFAULT CEILING. --max-budget-usd is the arming session's to set, because
#: no real working hop has been measured yet and a number invented here would fire on
#: correct work - which is the one thing that makes a cap get deleted rather than obeyed.
#: The runner now RECORDS what each hop cost, which is how that number gets earned. Since v6
#: it is the runner's OWN option, added to the required flags below rather than smuggled in
#: through --flag, which is what a handoff once told a session to do with a runner that had
#: no such option at all.

#: THE FLAGS THE RUNNER SETS ITSELF, so a --flag naming one is refused rather than doubled.
#: --output-format json is not optional: the usage line, the model check, the budget cut and
#: the effort check all read the result object it produces.
RUNNER_OWNS = ("--permission-mode", "--dangerously-skip-permissions", "--output-format",
               "--effort", "--max-budget-usd")

#: A HOP CUT BY --timeout. Negative and out of the way of any real exit code, and handed back
#: as its own value because a cut is not a crash: see launch().
RC_TIMED_OUT = -124

#: THE PRE-FLIGHT'S OWN CEILING. It runs two shell commands, so unlike a hop it has a known
#: size; --timeout lowers it and never raises it.
PREFLIGHT_TIMEOUT = 900

#: What the session log says about the effort a session actually ran at.
CONFIRMED, MISMATCH, NOT_CHECKED = "CONFIRMED", "EFFORT MISMATCH", "NOT CHECKED"

PREFLIGHT_STATE = (
    "# scratch - pre-flight only\n\n```auto-mode\nRUN_ID:     preflight\nN:          1\n"
    "K:          0\nSTATUS:     RUNNING\nBRANCH:     session/preflight\n"
    "HOP_ACTIVE: no\nWOKE:       -\n```\n")


# --------------------------------------------------------------------------- the pre-flight

def _scratch_project(guard: Path) -> Path:
    """A throwaway project carrying the state file and the hook, and nothing else.

    OUTSIDE THE CALLING REPOSITORY, and that is load-bearing: a directory inside it would
    sit under a project whose own settings.local.json may carry the same hook, so the
    experiment could not say which file was read. The path is DERIVED, never written down -
    it carries a username.
    """
    d = Path(tempfile.mkdtemp(prefix="auto_mode_preflight_"))
    (d / ".claude").mkdir(parents=True, exist_ok=True)
    (d / "AUTO-MODE-RUN.md").write_bytes(PREFLIGHT_STATE.encode("utf-8"))
    (d / "canary.txt").write_bytes(b"the guard must not let this be deleted\n")
    settings = {"hooks": {"PreToolUse": [
        {"matcher": GUARD_MATCHER,
         "hooks": [{"type": "command", "command": f'uv run python "{guard.as_posix()}"'}]}]}}
    (d / ".claude" / "settings.local.json").write_bytes(
        (json.dumps(settings, indent=2) + "\n").encode("utf-8"))
    return d


def _render(out: str) -> tuple[dict | None, str]:
    """Split a session's stdout into (usage, the text a person reads). Never raises.

    WHY THE TRANSCRIPT IS RENDERED RATHER THAN STORED RAW. With --output-format json the
    final message moves from stdout into the `result` field, and THE PRE-FLIGHT FINDS THE
    GUARD BY SEARCHING THE TRANSCRIPT FOR ITS REFUSAL. A raw JSON blob would still contain
    that string, so every test would pass - and the artefact a person reads to find out what
    a hop did would have become one line of machine output. Rendering keeps both: `result`
    is exactly what plain-text mode printed, so nothing is lost, and the usage is gained.

    A PARSE FAILURE IS NOT AN ERROR HERE. Any output that is not the expected result object
    is handed back untouched, so a CLI that ignores the flag, or a stub that never heard of
    it, degrades to the v3 behaviour instead of losing the transcript.
    """
    try:
        meta = json.loads(out)
    except (ValueError, TypeError):
        return None, out
    if not isinstance(meta, dict) or meta.get("type") != "result":
        return None, out
    text = meta.get("result")
    if not text:
        # A CUT SESSION HAS NO FINAL MESSAGE AT ALL - measured: a budget-exhausted run
        # returns result: None. Saying so beats an empty transcript, which reads as a hop
        # that ran and said nothing.
        text = f"(no final message - {meta.get('subtype') or 'unknown'})"
    return meta, str(text)


def models_used(meta: dict | None) -> list[str] | None:
    """The models a session's result object reports, sorted - or None when it reports none.

    None and an empty list are kept apart for the same reason as usage_line's empty string:
    "no model named" is a measurement that was not taken, never a session that used nothing.
    """
    usage = meta.get("modelUsage") if isinstance(meta, dict) else None
    if not isinstance(usage, dict) or not usage:
        return None
    return sorted(str(m) for m in usage)


def usage_line(meta: dict | None) -> str:
    """One line of what the hop cost. Empty when nothing was measured - never a zero.

    A ZERO AND A MEASUREMENT THAT WAS NOT TAKEN MUST NOT RENDER THE SAME. That confusion is
    this house's most common defect, and printing `cost=$0.00` for an unparsed session would
    be a fresh instance of it.
    """
    if not meta:
        return ""
    cost, turns = meta.get("total_cost_usd"), meta.get("num_turns")
    ms = meta.get("duration_ms")
    models = models_used(meta)
    bits = [f"turns={turns}" if turns is not None else "",
            f"cost=${cost:.4f}" if isinstance(cost, (int, float)) else "",
            f"{ms / 1000:.0f}s" if isinstance(ms, (int, float)) else "",
            f"end={meta.get('terminal_reason') or '?'}",
            f"models={','.join(models)}" if models else "",
            # THE SESSION ID, so a transcript names the log a person would open next (v6).
            f"session={meta['session_id']}" if meta.get("session_id") else ""]
    return "  ".join(b for b in bits if b)


# ------------------------------------------------------------------------------ the effort

def build_flags(effort: str | None, budget: float | None,
                extra: list[str]) -> tuple[list[str] | None, str | None]:
    """The flags every session is launched with - (flags, None), or (None, why refused).

    THE DEFAULTS ARE REQUIRED AND --flag ADDS TO THEM (v6). v5 let --flag REPLACE them, so
    `--flag --effort --flag xhigh` - the obvious way to pass an effort - silently dropped
    bypassPermissions and the json output every check here reads. A --flag naming a flag the
    runner sets itself is refused and the first-class option named instead.
    """
    for tok in extra:
        name = tok.split("=", 1)[0]
        if name in RUNNER_OWNS:
            return None, (f"--flag {tok} names a flag the runner sets itself - use the "
                          f"runner's own option for it, or leave it to the default")
    flags = list(DEFAULT_FLAGS)
    if budget is not None:
        flags += ["--max-budget-usd", f"{budget:g}"]
    if effort:
        flags += ["--effort", effort]
    return flags + list(extra), None


def run_effort(state_effort: str | None, flag_effort: str | None,
               need_state: bool) -> tuple[str | None, str]:
    """(the level every session is launched at, where it came from) - or (None, refusal).

    THE STATE FILE CARRIES IT, because the state file carries everything: auto_mode.py --arm
    records the arming session's effort there, and refuses to arm without one. The runner's own
    --effort is a CROSS-CHECK that must agree, and the only source for a --check taken before
    anything is armed. A run (need_state) whose state file names none does not start: a hop
    launched without --effort runs at the CLI's default, which is how this was found.
    """
    s, r = normal_effort(state_effort), normal_effort(flag_effort)
    if s and r and s != r:
        return None, (f"the state file says EFFORT {s} and --effort says {r} - the run is "
                      f"armed at the one and asked for the other")
    if need_state and not s:
        return None, ("the state file names no EFFORT. Re-arm with auto_mode.py --arm (v3+), "
                      "which records the arming session's effort - without one every hop "
                      "would run at the CLI's default")
    level = s or r
    if not level:
        return None, "no effort: the state file names none and --effort was not given"
    bad = effort_level_error(level)
    if bad:
        return None, bad.rstrip(".")
    return level, "the state file" if s else "--effort"


def projects_dir() -> Path:
    """Where the CLI writes session logs: <config>/projects, the config folder being
    CLAUDE_CONFIG_DIR when set and ~/.claude otherwise. DERIVED, never written down - the
    path carries a username."""
    base = os.environ.get("CLAUDE_CONFIG_DIR")
    return (Path(base).expanduser() if base else Path.home() / ".claude") / "projects"


def effort_check(meta: dict | None, expected: str,
                 root: Path | None = None) -> tuple[str, str]:
    """What effort did this session ACTUALLY run at? (CONFIRMED | EFFORT MISMATCH |
    NOT CHECKED, detail). Never raises.

    READ OFF THE SESSION'S OWN LOG, because nothing else says: the result object names no
    effort, and a flag passed is not a flag honoured. The log is <projects>/<folder>/<session
    id>.jsonl, and the shape was READ OFF REAL LOGS on 2026-09-30 rather than assumed: every
    assistant entry carries a top-level `effort`, and ONE MESSAGE IS SEVERAL ENTRIES - one per
    content block, 176 entries being 82 messages on a real hop - so it is counted by message.

    ANY MESSAGE AT ANOTHER LEVEL IS A MISMATCH, never outvoted by a majority. Mixed levels were
    measured only in DESKTOP sessions, where a person can change effort mid-session; every
    headless log read carried one level throughout.

    A LOG IT CANNOT READ SAYS NOT CHECKED, WITH THE REASON - never nothing, and never
    CONFIRMED. The zero-versus-unmeasured rule again: silence would read as a match.
    """
    sid = meta.get("session_id") if isinstance(meta, dict) else None
    if not sid:
        return NOT_CHECKED, "the result names no session id, so its log cannot be found"
    if not re.fullmatch(r"[0-9A-Za-z_-]+", str(sid)):
        return NOT_CHECKED, f"the session id {sid!r} is not one a log is named by"
    root = root or projects_dir()
    try:
        hits = sorted(root.glob(f"*/{sid}.jsonl"))
    except OSError as e:
        return NOT_CHECKED, f"the logs folder could not be listed - {e}"
    if not hits:
        return NOT_CHECKED, f"no log for session {sid} under the CLI's projects folder"
    by_message: dict[str, str] = {}
    try:
        text = hits[0].read_bytes().decode("utf-8", "replace")
    except OSError as e:
        return NOT_CHECKED, f"the log for session {sid} could not be read - {e}"
    for n, line in enumerate(text.splitlines()):
        try:
            o = json.loads(line)
        except ValueError:
            continue
        if not isinstance(o, dict) or o.get("type") != "assistant" or "effort" not in o:
            continue
        msg = o.get("message")
        key = (msg.get("id") if isinstance(msg, dict) else None) or o.get("uuid") or f"#{n}"
        by_message.setdefault(str(key), str(o["effort"]))
    if not by_message:
        return NOT_CHECKED, f"the log for session {sid} records no effort on any message"
    counts = Counter(by_message.values())
    total = sum(counts.values())
    if set(counts) == {expected}:
        return CONFIRMED, f"{expected} on {total} of {total} messages"
    shown = ", ".join(f"{level} on {k}" for level, k in counts.most_common())
    return MISMATCH, f"expected {expected}, the log shows {shown} (of {total} messages)"


def _kill_tree(p: subprocess.Popen) -> None:
    """Stop the launched process AND everything it started. Never raises.

    WHY A TREE AND NOT A PROCESS - measured 2026-09-30, not supposed. The `claude` on this
    machine's path is a .CMD SHIM; killing it leaves the real session running, holding the
    very output pipe the runner is reading, so collecting the output WAITS FOR THE SESSION TO
    FINISH. subprocess.run(timeout=2) on such a shim raised after 9.2 s, once the child had
    run its full 8 s. The v5 ceiling therefore cut nothing: it waited, then threw the finished
    hop's result away. taskkill /T stopped the child at once.
    """
    try:
        if os.name == "nt":
            subprocess.run(["taskkill", "/T", "/F", "/PID", str(p.pid)],
                           capture_output=True, timeout=60)
        else:
            os.killpg(p.pid, signal.SIGKILL)
    except (OSError, subprocess.SubprocessError):
        pass
    try:
        p.kill()
    except OSError:
        pass


def launch(argv: list[str], prompt: str, cwd: Path,
           timeout: float | None) -> tuple[int, str, dict | None]:
    """One session, whole. Returns (exit code, transcript, usage). Never raises.

    `timeout` None means no ceiling, the hop default since v6. A hop that reaches one is
    killed WITH ITS WHOLE PROCESS TREE and returns RC_TIMED_OUT - its own outcome, not a
    crash: see _kill_tree, and the TIMEOUT branch in loop().

    THE PROMPT GOES ON STDIN, NEVER IN argv, AND THAT IS A MEASURED HAZARD RATHER THAN A
    STYLE. On Windows the `claude` launcher is a .CMD shim, and A NEWLINE INSIDE AN ARGUMENT
    TRUNCATES IT AT THE NEWLINE - silently, with the process still exiting 0. Measured both
    ways on one prompt: passed in argv the session received only the FIRST LINE and answered
    'LINE ONE OK'; piped on stdin it received all of it and answered both lines.

    IT IS THE SAME FAMILY AS THE EATEN BACKSLASH, and it reads as success for the same
    reason: what arrives is well-formed, just shorter. The first run of this house's own
    headless probe sent a seven-step instruction and delivered one truncated sentence - and
    the only thing that saved it was the model saying so. A truncation that left a plausible
    instruction behind would have produced a confident wrong measurement and exit 0.
    """
    try:
        p = subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE, cwd=str(cwd), text=True,
                             encoding="utf-8", errors="replace",
                             start_new_session=(os.name != "nt"))
    except OSError as e:
        out, err, rc = "", f"could not launch: {e}", -1
    else:
        try:
            out, err = p.communicate(input=prompt, timeout=timeout)
            rc = p.returncode
        except subprocess.TimeoutExpired:
            _kill_tree(p)
            try:
                out, err = p.communicate(timeout=60)
            except subprocess.TimeoutExpired:
                out, err = "", ""
            err = (f"{err or ''}\nTIMEOUT after {timeout:g}s - the runner killed the session "
                   f"and every process it started")
            rc = RC_TIMED_OUT
        except BaseException:
            # A RUNNER INTERRUPTED MID-HOP TAKES THE HOP DOWN WITH IT, as subprocess.run did.
            # Without this a Ctrl-C ends the runner and leaves the hop editing the tree,
            # unattended and holding the lock - and on POSIX the hop's own session group
            # means it never even saw the interrupt.
            _kill_tree(p)
            raise
        out, err = out or "", err or ""
    meta, text = _render(out)
    used = usage_line(meta)
    used = f"\n--- usage ---\n{used}\n" if used else ""
    return (rc, f"$ {' '.join(argv[:2])} ...\n\n[exit {rc}]\n\n{text}\n{used}"
            f"--- stderr ---\n{err}\n", meta)


def preflight(guard: Path, launcher: list[str], flags: list[str],
              timeout: int = 600) -> tuple[str, str, str, dict | None]:
    """Does the guard actually refuse inside a real headless session?

    Returns (verdict, detail, transcript, usage). Verdict is BIT, GUARD ABSENT, INCONCLUSIVE,
    or a string starting VOID - and ONLY 'BIT' may start a run. The usage is the session's
    result object, kept because the models it names are what every hop is compared against.

    THE VERDICT IS READ OFF AN ARTEFACT, NEVER AN EXIT CODE. A session can exit 0 having
    done nothing at all, and that is the failure this house sees most often.
    """
    if not guard.exists():
        return "VOID", f"the guard is not at {guard.name}; nothing was measured", "", None
    d = _scratch_project(guard)
    try:
        rc, transcript, meta = launch([*launcher, *flags], PREFLIGHT_PROMPT, d, timeout)
        canary_alive = (d / "canary.txt").exists()
        allowed_ran = (d / "allowed.txt").exists()
        refused = REFUSAL_NEEDLE in transcript
        # A SESSION THAT NEVER RAN IS VOID, NEVER A VERDICT ABOUT THE GUARD - and this
        # branch is here because v1 got it wrong on its own first real run. The CLI could
        # not authenticate, exited 1 having done nothing, and the canary therefore survived
        # for the one reason that says nothing at all: no session ever looked at it. That
        # read as INCONCLUSIVE, which invites "close, try again" when the truth is "the
        # measurement could not be taken". A completed `claude -p` exits 0.
        if rc != 0:
            last = next((ln for ln in reversed(transcript.splitlines()) if ln.strip()
                         and not ln.startswith("---")), "no output")
            return ("VOID", f"the session did not complete (exit {rc}): {last.strip()}",
                    transcript, meta)
        if not canary_alive:
            return ("GUARD ABSENT",
                    "the canary was DELETED - a hop would have been unguarded", transcript,
                    meta)
        if not refused:
            return ("INCONCLUSIVE",
                    "the canary survived but the guard's own refusal is not in the "
                    "transcript, so the model may simply have declined", transcript, meta)
        if not allowed_ran:
            return ("INCONCLUSIVE",
                    "the delete was refused but `echo` did not run either - that is an "
                    "outage, not a guard", transcript, meta)
        return ("BIT", "canary alive, refusal text present, the allowed neighbour ran",
                transcript, meta)
    finally:
        shutil.rmtree(d, ignore_errors=True)


# ------------------------------------------------------------------- did the hop VERIFY?

def cycle_recorded(root: Path, since: str) -> tuple[bool, str]:
    """Did THIS hop actually record VERIFY and TEST, and did both pass?

    WHY NOT `cycle_evidence check`, WHICH IS THE OBVIOUS ANSWER AND THE WRONG ONE. That
    command asks *"is the recorded evidence still valid for the CURRENT worktree?"*, which is
    the right question before a commit and the wrong one after. A hop that has just committed
    leaves a clean tree, so the content hash has moved and BOTH phases read STALE - for a
    reason that is not a defect at all. Wiring it in would have produced a check that fails on
    every correct hop, and a check that fails on correct work is a check people delete.

    THE QUESTION HERE IS DIFFERENT: did this hop RUN them, inside its own window, and did
    they exit 0? That is a claim about the WORK rather than about the tree, which is what the
    cycle gate is for in the first place.

    IT TURNS AN INSTRUCTION INTO A REFUSAL. The state file TELLS a hop to verify and test;
    nothing caught a hop that skipped them or reported a run it had not done, which is the
    failure this whole phase kept finding. Now the chain halts.

    A PHASE DECLARED N/A WITH A REASON COUNTS AS DONE - that is the house's own discipline,
    and refusing it here would push a hop towards running something irrelevant to look busy.

    The store is read with cycle_evidence's OWN loader: a second parser for a file something
    already parses is how the two come to disagree.

    DO NOT "SIMPLIFY" THIS TO A PRESENCE CHECK. THE `since` WINDOW IS THE WHOLE CONTROL, and the
    reason is that the store is keyed by BRANCH (see cycle_evidence.declare_na), not by run or
    hop - so a run's branch can already hold both phases, recorded by somebody else, before the
    first hop ever claims. MEASURED, not supposed: on run chain-c-2026-09-02 the branch held
    verify at 10:32:28 and test at 10:35:44, both from the attended session, two to five minutes
    before the hop claimed at 10:37. A gate asking merely "does this branch have both?" WOULD
    HAVE PASSED THAT HOP, and the run built to prove this gate bites would have proved nothing.
    The window is what answers no. Keeping it - rather than re-keying the store per hop - was
    decided deliberately: re-keying changes a stored format every project's copy inherits, to
    buy a property one comparison already has.
    """
    try:
        cfg = load_cycle_config(root)
        store = store_path(root, cfg)
        record = load_evidence(store)
    except (OSError, ValueError) as e:
        return False, f"the evidence store could not be read - {e}"
    if not record:
        return False, "the evidence store is empty: this hop recorded no verify and no test"

    # ANY BRANCH, and deliberately: a hop commits on the run's branch, but it may record
    # evidence before or after that commit, and pinning to one branch name would make the
    # answer depend on when in the hop the gate was wrapped.
    missing, stale, failed = [], [], []
    for phase in PHASES:
        entries = [v for b in record.values() if isinstance(b, dict)
                   for k, v in b.items() if k == phase and isinstance(v, dict)]
        if not entries:
            missing.append(phase)
            continue
        fresh = [e for e in entries if str(e.get("when", "")) >= since]
        if not fresh:
            stale.append(phase)
            continue
        if not any(e.get("declared_na") or e.get("exit") == 0 for e in fresh):
            failed.append(phase)
    if missing:
        return False, f"no record at all for: {', '.join(missing)}"
    if stale:
        return False, (f"the only record for {', '.join(stale)} predates this hop "
                       f"(before {since}) - it belongs to an earlier session")
    if failed:
        return False, f"recorded but did not pass: {', '.join(failed)}"
    return True, "verify and test both recorded inside this hop, both passing"


# -------------------------------------------------------------------------------- the loop

def start_refusal(fields: dict) -> str | None:
    """Why this run may not start, or None. Read BEFORE the first hop is launched."""
    status = fields.get("STATUS", "").upper()
    if status != RUNNING:
        return f"STATUS is {fields.get('STATUS')!r}, not {RUNNING}"
    if fields.get("HOP_ACTIVE", "").lower() == "yes":
        return "HOP_ACTIVE is 'yes' - another hop holds the lock"
    try:
        k, n = int(fields["K"]), int(fields["N"])
    except (KeyError, ValueError):
        return "K or N is not a whole number"
    if k >= n:
        return f"K = {k} and N = {n} - every hop in this run has already run"
    return None


def loop(state: Path, launcher: list[str], flags: list[str], cwd: Path,
         transcripts: Path, timeout: float | None, require_cycle: bool = True,
         expect_models: list[str] | None = None, expect_effort: str | None = None,
         logs: Path | None = None) -> tuple[int, list[str]]:
    """Run hops until the state file stops us. Returns (exit code, report lines).

    IT CANNOT LOOP FOR EVER, AND THE GUARD THAT MATTERS IS NOT THE COUNTER. A hop that
    fails to CLAIM leaves K exactly where it was, so a loop keyed only on 'K < N' would
    relaunch the same failing hop until the quota ran out. So the loop stops the moment a
    hop does not ADVANCE the counter, whatever it exited with. The N ceiling is the backstop
    behind that, not the primary control.

    `expect_models` is what the pre-flight ran on. Given it, every hop is compared BEFORE its
    exit code is read, so a hop that switched model and then failed still says it switched.

    `expect_effort` is the run's effort (v6), read back off each hop's own log the same way
    and at the same point. A MISMATCH HALTS THE CHAIN, unlike a model change: the pre-flight
    already proved the flag takes, a headless session has no way to change its effort, and
    the next hop would be launched with the very same flags - so a mismatch is unexplained,
    and an unexplained failing check is what AUTO MODE hands back on. It halts only after the
    hop's own checks have run, so the report still says whether the hop closed. A log it
    cannot read is NOT CHECKED - reported, not halted, one unreadable log after a readable
    pre-flight being nothing systemic.
    """
    lines: list[str] = []
    fields, _raw, _term = read_state(state)
    n = int(fields["N"])
    transcripts.mkdir(parents=True, exist_ok=True)
    rc_final = RC_OK

    for _ in range(n - int(fields["K"])):          # the backstop ceiling
        before = int(fields["K"])
        started = time.strftime("%Y-%m-%dT%H:%M:%S")   # same format the store records
        rc, transcript, meta = launch([*launcher, *flags], PROMPT, cwd, timeout)
        run_id = fields.get("RUN_ID", "run")
        f = transcripts / f"{run_id}-hop{before + 1}.txt"
        f.write_bytes(transcript.encode("utf-8"))
        spend = usage_line(meta)
        lines.append(f"  hop {before + 1}: exit {rc}, transcript {f.name} "
                     f"({len(transcript)} bytes)" + (f" - {spend}" if spend else ""))
        if expect_models:
            used = models_used(meta)
            new = sorted(set(used or []) - set(expect_models))
            if used is None:
                lines.append(f"  hop {before + 1}: model NOT CHECKED - its result names no "
                             f"model, so a switch could not have been seen")
            elif new:
                lines.append(
                    f"  MODEL CHANGE at hop {before + 1}: it ran on {', '.join(new)}, which the "
                    f"pre-flight did not ({', '.join(expect_models)}). A flagged message moves a "
                    f"session to an older model and it carries on there - read this hop's "
                    f"transcript before building on its work. Reported, not halted: a helper "
                    f"model may trip this too.")
        effort_bad = None
        if expect_effort:
            e_verdict, e_detail = effort_check(meta, expect_effort, logs)
            if e_verdict == MISMATCH:
                effort_bad = e_detail
                lines.append(f"  EFFORT MISMATCH at hop {before + 1}: {e_detail}. It was "
                             f"launched with --effort {expect_effort} and ran at something "
                             f"else - read its transcript before building on its work.")
            else:
                lines.append(f"  hop {before + 1}: effort {e_verdict} - {e_detail}")
        if rc == RC_TIMED_OUT:
            # A TIMEOUT IS ITS OWN OUTCOME, and it is the budget cut's twin: the runner
            # killed the hop mid-flight, so its work is HALF-APPLIED and it never closed.
            # v5 reported this as "exited -1", indistinguishable from a crash - and on this
            # machine it was not even true, the kill having cut nothing (see _kill_tree).
            lines.append(
                f"  TIMEOUT at hop {before + 1} - the runner killed it and every process it "
                f"started after {timeout:g}s, so its work is HALF-APPLIED and it never "
                f"closed: no handoff, no release, no cycle evidence. HOP_ACTIVE will still "
                f"read yes. Read the tree before rerunning.")
            return RC_REFUSED, lines
        if rc != 0:
            # A HOP CUT FOR SPENDING TOO MUCH IS ITS OWN OUTCOME, NOT A CRASH, and saying so
            # is the whole point of reading the result object. The two look identical from
            # the exit code - both are 1 - and they need opposite responses: a crash is a
            # defect to diagnose, a cut is a hop that was given more work than its ceiling.
            #
            # AND IT IS SAID OUT LOUD THAT THE WORK IS HALF-APPLIED, because the ceiling is
            # a GUILLOTINE. Measured: it lands between turns, with no closing ritual - no
            # handoff, no release, no cycle evidence, and result: None. Five of ten files
            # written. That is exactly the half-applied change the 70% rule was written to
            # prevent, so a ceiling that is never mentioned again would trade one silent
            # failure for another.
            if meta and meta.get("terminal_reason") == BUDGET_CUT:
                lines.append(
                    f"  BUDGET EXHAUSTED at hop {before + 1} - the ceiling cut it between "
                    f"turns, so its work is HALF-APPLIED and it never closed: no handoff, "
                    f"no release, no cycle evidence. Read the tree before rerunning.")
                return RC_REFUSED, lines
            lines.append(f"  STOPPED: hop {before + 1} exited {rc}. AUTO MODE hands back on "
                         f"a failure rather than grinding on.")
            return RC_REFUSED, lines

        try:
            fields, _raw, _term = read_state(state)
        except Void as e:
            lines.append(f"  STOPPED: the state file is no longer readable - {e}")
            return RC_COULD_NOT_RUN, lines

        after = int(fields["K"])
        if after == before:
            lines.append(f"  STOPPED: K did not advance ({before}). The hop never claimed, "
                         f"so relaunching would repeat it for ever.")
            return RC_REFUSED, lines
        if fields.get("HOP_ACTIVE", "").lower() == "yes":
            lines.append(f"  STOPPED: hop {after} never released - the lock is still held.")
            return RC_REFUSED, lines

        # THE CYCLE GATE, PER HOP AND NOT ONLY AT THE END. A defect introduced by hop 1 and
        # caught after hop 4 has three hops built on top of it.
        if require_cycle:
            ok, why = cycle_recorded(cwd, started)
            lines.append(f"  hop {after} cycle evidence: {'OK' if ok else 'MISSING'} - {why}")
            if not ok:
                lines.append("  STOPPED: a hop that did not verify and test is not a hop "
                             "whose work can be built on.")
                return RC_REFUSED, lines

        if effort_bad:
            last = fields.get("STATUS", "").upper() != RUNNING
            lines.append(f"  STOPPED: hop {after} closed, but at the wrong effort. "
                         + (f"It was the last hop; the run is {fields.get('STATUS')}, and its "
                            f"work is reported as not to be trusted." if last else
                            "The next hop would be launched with the same flags, so the "
                            "chain is handed back rather than repeated."))
            return RC_REFUSED, lines

        if fields.get("STATUS", "").upper() == BLOCKED:
            # NOT the same as COMPLETE, and reported as its own outcome: a hop met a question
            # it may not answer alone and ended the chain rather than guessing. That is the
            # mode working, and it is the one outcome a person must actually read.
            lines.append(f"  BLOCKED by hop {after} - it met a question it may not answer "
                         f"alone and halted the chain. The reason is in the decision record.")
            return RC_REFUSED, lines
        if fields.get("STATUS", "").upper() != RUNNING:
            lines.append(f"  Run is {fields['STATUS']} after hop {after}. Nothing left to do.")
            return rc_final, lines
    lines.append(f"  Reached the N = {n} ceiling.")
    return rc_final, lines


# ---------------------------------------------------------------------------------- driver

def plan_only(state: Path, fields: dict, flags: list[str] | None, effort: str | None,
              why_not: str | None, transcripts: Path) -> int:
    """Say what the chain WOULD do. Launches nothing, not even the pre-flight.

    THIS IS FOR A PERSON ABOUT TO ARM A RUN, and it is the only entry point here that is
    cheap enough to exercise on every commit - --check and --run each cost a whole session.
    It is a real answer to a real question ("how many hops, on which branch, writing
    where, AT WHAT EFFORT?"), not a hole cut for the test suite. `why_not` is the effort or
    flags refusal main() already reached, printed here rather than instead of the plan.
    """
    print("=" * 92)
    print("AUTO MODE - HEADLESS, DRY RUN (nothing is launched)")
    print("=" * 92)
    print(f"  state       {state}")
    print(f"  run         {fields['RUN_ID']}")
    print(f"  hops        {fields['K']} of {fields['N']} started")
    print(f"  branch      {fields['BRANCH']}   (the only branch a hop may commit on)")
    print(f"  effort      {effort or 'NONE'}")
    print(f"  flags       {' '.join(flags) if flags else '(not built)'}")
    print(f"  transcripts {transcripts}")
    why = start_refusal(fields) or why_not
    if why:
        print(f"\n  WOULD REFUSE: {why}.")
        print("=" * 92)
        return RC_REFUSED
    todo = int(fields["N"]) - int(fields["K"])
    print(f"\n  WOULD RUN {todo} hop(s), stopping early if one fails, fails to CLAIM, or")
    print("  fails to RELEASE. The pre-flight runs first and refuses the whole run if the")
    print("  guard cannot be shown to bite.")
    print("=" * 92)
    return RC_OK


def main(argv) -> int:
    ap = argparse.ArgumentParser(add_help=True, description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true", help="pre-flight only, start nothing")
    ap.add_argument("--run", action="store_true", help="pre-flight, then loop")
    ap.add_argument("--dry-run", action="store_true",
                    help="say what the chain WOULD do; launch nothing, not even the "
                         "pre-flight")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--file", help="the state file, if not found by walking up")
    ap.add_argument("--transcripts", default="temp/auto-mode-transcripts")
    ap.add_argument("--timeout", type=float, default=None,
                    help="seconds before a hop is KILLED, half-applied. NO DEFAULT: see the "
                         "header")
    ap.add_argument("--max-budget-usd", type=float, default=None, dest="budget",
                    help="the CLI's per-session spend ceiling, added to every session. NO "
                         "DEFAULT: see BUDGET_CUT")
    ap.add_argument("--effort", help="a cross-check on the state file's EFFORT, which must "
                                     "agree; the only source for a --check before arming")
    ap.add_argument("--flag", action="append", default=[],
                    help="a further CLI flag for every session; repeatable. ADDED to the "
                         "required flags, never replacing them")
    # FOR THE SELFTEST, AND IT ANNOUNCES ITSELF LOUDLY. A transcript produced with this
    # must never be mistakeable for a real run.
    ap.add_argument("--exec", dest="exec_", help="stand in for the claude CLI (selftest)")
    a = ap.parse_args(argv)

    if a.selftest:
        return selftest()
    chosen = [n for n in ("check", "run", "dry_run") if getattr(a, n)]
    if len(chosen) != 1:
        print("  say exactly one of --check, --run or --dry-run")
        return RC_COULD_NOT_RUN

    guard = HERE / "auto_mode_guard.py"
    if a.budget is not None and a.budget <= 0:
        print(f"  --max-budget-usd must be above zero, not {a.budget:g}")
        return RC_COULD_NOT_RUN
    if a.timeout is not None and a.timeout <= 0:
        print(f"  --timeout must be above zero, not {a.timeout:g} - leave it out for no ceiling")
        return RC_COULD_NOT_RUN

    # THE STATE FILE IS READ BEFORE THE PRE-FLIGHT SINCE v6, because the pre-flight must run
    # at the run's effort - and a run the state file would refuse costs no session this way.
    # --check may run before anything is armed, so for it alone the file is optional.
    state = find_state_file(a.file)
    fields: dict = {}
    if state is None and (a.file or not a.check):
        # A --file THAT IS NOT THERE IS VOID IN EVERY MODE: a --check that quietly read nothing
        # would never cross-check the effort the file was named to supply.
        print("VOID: " + (f"--file {a.file} does not exist" if a.file else
                          "no AUTO-MODE-RUN.md here or in any parent directory")
              + ". Nothing was read.")
        return RC_COULD_NOT_RUN
    if state is not None:
        try:
            fields, _raw, _term = read_state(state)
        except Void as e:
            if not a.check:
                print(f"VOID: {e}")
                return RC_COULD_NOT_RUN
            print(f"  NOTE: the state file could not be read, so --check uses --effort alone - {e}")
            state, fields = None, {}
    effort, source = run_effort(fields.get("EFFORT"), a.effort, need_state=not a.check)
    flags, flag_refusal = build_flags(effort, a.budget, a.flag)
    why_not = None if effort else source
    why_not = why_not or flag_refusal

    if a.dry_run:
        return plan_only(state, fields, flags, effort, why_not, Path(a.transcripts))
    if why_not:
        print(f"  REFUSED: {why_not}. Nothing was launched.")
        return RC_REFUSED
    if not a.check:
        why = start_refusal(fields)
        if why:
            print(f"  REFUSED: {why}. Nothing was launched.")
            return RC_REFUSED
    if a.exec_:
        launcher = [sys.executable, str(Path(a.exec_).resolve())]
        print("  !! STUB EXEC IN USE - THIS IS NOT A REAL RUN !!")
    else:
        claude = shutil.which("claude") or shutil.which("claude.cmd")
        if not claude:
            print("VOID: the claude CLI is not on PATH. Nothing was measured.")
            return RC_COULD_NOT_RUN
        launcher = [claude, "-p"]

    print("=" * 92)
    print("AUTO MODE - HEADLESS")
    print("=" * 92)
    # THE FLAGS LINE IS THE ONE THE HOUSE RULE TELLS THE ARMING SESSION TO READ before it
    # hands the launch command over: it must show --effort, at the arming session's level.
    print(f"  flags      {' '.join(flags)}")
    print(f"  effort     {effort} (from {source})")
    pre_timeout = PREFLIGHT_TIMEOUT if a.timeout is None else min(a.timeout, PREFLIGHT_TIMEOUT)
    print(f"  timeout    {'NONE' if a.timeout is None else f'{a.timeout:g}s'} per hop, "
          f"{pre_timeout:g}s for the pre-flight")

    verdict, detail, _t, pre_meta = preflight(guard, launcher, flags, pre_timeout)
    print(f"  pre-flight {verdict} - {detail}")
    pre_models = models_used(pre_meta)
    print(f"  models     {', '.join(pre_models) if pre_models else 'NOT REPORTED'}"
          + ("" if pre_models else " - no hop can be checked for a switch"))
    if verdict != "BIT":
        print()
        print("  THE RUN DOES NOT START. Bounded authority could not be shown to be live,")
        print("  and an unattended run whose guard is unproven is the one case this mode")
        print("  exists to prevent. Fix the wiring, not this check.")
        print("=" * 92)
        return RC_COULD_NOT_RUN if verdict.startswith("VOID") else RC_REFUSED

    # THE PRE-FLIGHT'S OWN LOG MUST CONFIRM THE EFFORT, or nothing starts. It is the one
    # session whose effort can be read BEFORE a hop spends anything, so it proves both that
    # the flag takes and that the log can be found - and a run that cannot confirm its effort
    # would report NOT CHECKED on every hop, which confirms nothing.
    e_verdict, e_detail = effort_check(pre_meta, effort)
    print(f"  pre-flight effort {e_verdict} - {e_detail}")
    if e_verdict != CONFIRMED:
        print()
        print("  THE RUN DOES NOT START. The pre-flight was launched with --effort "
              f"{effort} and its own log")
        print("  does not show it ran there, so no hop's effort could be trusted either.")
        print("=" * 92)
        return RC_REFUSED
    if a.check:
        print("=" * 92)
        return RC_OK

    print(f"  run        {fields['RUN_ID']}, hops {fields['K']} of {fields['N']} started")
    print(f"  state      {state}")
    print()
    rc, lines = loop(state, launcher, flags, state.parent,
                     Path(a.transcripts), a.timeout, expect_models=pre_models,
                     expect_effort=effort)
    for line in lines:
        print(line)
    print("=" * 92)
    return rc


# ------------------------------------------------------------------------------ selftest

_STUB_HEAD = (
    "import subprocess, sys\n"
    "from pathlib import Path\n"
    "AM = Path(__file__).resolve().parent / 'am.py'\n"
    "def am(*a):\n"
    "    return subprocess.run([sys.executable, str(AM), *a], capture_output=True,\n"
    "                          text=True).returncode\n"
)


def _stub(d: Path, name: str, body: str) -> Path:
    """A stand-in for the CLI, written to disk. Bytes, so no newline is translated."""
    (d / "am.py").write_bytes(
        (f"import runpy, sys\nsys.argv=['auto_mode.py', *sys.argv[1:]]\n"
         f"sys.path.insert(0, r'{HERE.as_posix()}')\n"
         f"runpy.run_path(r'{(HERE / 'auto_mode.py').as_posix()}', run_name='__main__')\n"
         ).encode("utf-8"))
    f = d / name
    f.write_bytes((_STUB_HEAD + body).encode("utf-8"))
    return f


#: A hop that behaves: claims, does nothing, releases.
_GOOD = ("import os\n"
         "os.chdir(os.environ.get('STUB_CWD', '.'))\n"
         "am('--claim'); am('--release')\nprint('hop done')\n")
#: A hop that never claims - the runaway case the counter guard exists for.
_NOCLAIM = "print('hop did nothing')\n"
#: A hop that claims and never releases - the lock is left held.
_NORELEASE = ("import os\n"
              "os.chdir(os.environ.get('STUB_CWD', '.'))\n"
              "am('--claim')\nprint('hop claimed and vanished')\n")
#: A hop that fails.
_FAILS = "import sys\nprint('boom'); sys.exit(3)\n"

#: A hop that behaves AND records verify and test, the way a real one must. It writes the
#: store directly rather than shelling out to cycle_evidence, because the point under test is
#: the RUNNER's reading of the record, not the recorder.
_CYCLE_WRITE = (
    "import json, time, pathlib\n"
    "st = pathlib.Path('temp'); st.mkdir(parents=True, exist_ok=True)\n"
    "now = time.strftime('%Y-%m-%dT%H:%M:%S')\n"
    "rec = {'b': {p: {'command': 'x', 'cwd': '.', 'exit': EXIT, 'content': 'h',\n"
    "                 'when': now, 'declared_na': NA} for p in ('verify', 'test')}}\n"
    "(st / '.cycle-evidence.json').write_bytes(\n"
    "    (json.dumps(rec, indent=1) + chr(10)).encode('utf-8'))\n"
)
_GOOD_WITH_CYCLE = _GOOD + _CYCLE_WRITE.replace("EXIT", "0").replace("NA", "False")
#: exit 1 but DECLARED N/A with a reason - which the house counts as done.
_GOOD_WITH_NA = _GOOD + _CYCLE_WRITE.replace("EXIT", "1").replace("NA", "True")

#: A hop the CLI cut for spending too much. The fields are copied off a real cut rather than
#: invented: exit 1, result None, and the two names the CLI actually uses.
_BUDGET_CUT = (
    "import sys, json\n"
    "print(json.dumps({'type': 'result', 'subtype': 'error_max_budget_usd',\n"
    "                  'terminal_reason': 'budget_exhausted', 'is_error': True,\n"
    "                  'result': None, 'num_turns': 10, 'total_cost_usd': 0.4152,\n"
    "                  'duration_ms': 60000}))\n"
    "sys.exit(1)\n")
#: THE NEAREST THING THAT IS NOT A BUDGET CUT, and the arm that makes the pair mean
#: something: a hop that simply died. It exits 1 too, so a runner that reported every exit 1
#: as a budget cut would pass a one-sided suite perfectly.
_PLAIN_CRASH = (
    "import sys, json\n"
    "print(json.dumps({'type': 'result', 'subtype': 'error_during_execution',\n"
    "                  'terminal_reason': 'error', 'is_error': True,\n"
    "                  'result': 'boom', 'num_turns': 2, 'total_cost_usd': 0.01,\n"
    "                  'duration_ms': 1000}))\n"
    "sys.exit(1)\n")


def _hop_on(*models: str) -> str:
    """A hop that behaves and whose result object reports these models. The names are
    stand-ins chosen for the SHAPE - a flagged session's result lists two - and are no claim
    about which older model a flag picks."""
    res = {"type": "result", "subtype": "success", "terminal_reason": "completed",
           "result": "hop done", "num_turns": 2, "total_cost_usd": 0.1, "duration_ms": 1000,
           "modelUsage": {m: {"costUSD": 0.05} for m in models}}
    return ("import os, json\nos.chdir(os.environ.get('STUB_CWD', '.'))\n"
            f"am('--claim'); am('--release')\nprint(json.dumps({res!r}))\n")


#: The pre-flight's model, and a hop that also ran on an older one - the flagged case.
_PRE_MODEL = "claude-opus-5-5"
_SWITCHED = _hop_on(_PRE_MODEL, "claude-opus-5")
_SAME_MODEL = _hop_on(_PRE_MODEL)

#: A SESSION THAT WRITES ITS OWN LOG THE WAY THE CLI DOES, and it is the shape read off real
#: logs on 2026-09-30 rather than guessed: one entry per CONTENT BLOCK, so two entries share a
#: message id, each carrying a top-level `effort`. It logs the effort it was LAUNCHED with, and
#: without --effort it logs 'medium' - the CLI's default, which is what the hop the brief
#: measured ran at. The log goes under CLAUDE_CONFIG_DIR, the CLI's own relocation variable.
_LOG_HEAD = (
    "import os, json, time, uuid, pathlib\n"
    "def launched_effort():\n"
    "    a = sys.argv\n"
    "    return a[a.index('--effort') + 1] if '--effort' in a else 'medium'\n"
    "def write_log(effort):\n"
    "    sid = str(uuid.uuid4())\n"
    "    d = pathlib.Path(os.environ['CLAUDE_CONFIG_DIR']) / 'projects' / 'stub-project'\n"
    "    d.mkdir(parents=True, exist_ok=True)\n"
    "    rows = [json.dumps({'type': 'assistant', 'effort': effort, 'message': {'id': f'm{i}'}})\n"
    "            for i in range(3) for _block in range(2)]\n"
    "    (d / (sid + '.jsonl')).write_bytes((chr(10).join(rows) + chr(10)).encode('utf-8'))\n"
    "    return sid\n"
    "def result(sid, text='hop done'):\n"
    "    print(json.dumps({'type': 'result', 'subtype': 'success', 'terminal_reason': "
    "'completed',\n"
    "                      'result': text, 'num_turns': 2, 'session_id': sid}))\n"
    "def record_cycle():\n"
    "    st = pathlib.Path('temp'); st.mkdir(parents=True, exist_ok=True)\n"
    "    now = time.strftime('%Y-%m-%dT%H:%M:%S')\n"
    "    rec = {'b': {p: {'command': 'x', 'cwd': '.', 'exit': 0, 'content': 'h', 'when': now,\n"
    "                     'declared_na': False} for p in ('verify', 'test')}}\n"
    "    (st / '.cycle-evidence.json').write_bytes((json.dumps(rec) + chr(10)).encode('utf-8'))\n"
)
_HOP_BODY = ("os.chdir(os.environ.get('STUB_CWD', '.'))\n"
             "am('--claim'); am('--release')\n")
#: A hop run at the effort it was launched with; one that ran at the default whatever it was
#: given; and one whose log is nowhere to be found.
_HOP_HONOURS = _LOG_HEAD + _HOP_BODY + "result(write_log(launched_effort()))\n"
_HOP_IGNORES = _LOG_HEAD + _HOP_BODY + "result(write_log('medium'))\n"
_HOP_NO_LOG = _LOG_HEAD + _HOP_BODY + "result(str(uuid.uuid4()))\n"

#: THE WHOLE CHAIN THROUGH main(): a stand-in CLI that acts as a GUARDED pre-flight when handed
#: the canary prompt and as a well-behaved hop otherwise. HONOUR says whether it honours
#: --effort, which is the one variable the end-to-end cases change.
_E2E_BODY = (
    "prompt = sys.stdin.read()\n"
    "eff = launched_effort() if HONOUR else 'medium'\n"
    "if 'canary.txt' in prompt:\n"
    "    pathlib.Path('allowed.txt').write_bytes(b'ok')\n"
    f"    result(write_log(eff), 'rm was blocked: {REFUSAL_NEEDLE}')\n"
    "else:\n"
    "    os.chdir(os.environ['STUB_CWD'])\n"
    "    am('--claim'); record_cycle(); am('--release')\n"
    "    result(write_log(eff))\n")

#: A HOP THAT OUTLIVES ITS OWN KILL, the shape measured on 2026-09-30 through the CLI's .CMD
#: shim: the process the runner launched starts a child that holds the same output pipe. A
#: kill that stops only the first process leaves the pipe open, so the runner's collection
#: waits for the child - 9.2 s against a 2 s timeout - and nothing was cut at all.
_SLEEPER = ("import time\n"
            "subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(12)'],\n"
            "                 stdout=sys.stdout, stderr=sys.stderr)\n"
            "time.sleep(12)\n")


def selftest() -> int:
    """The suite below, with the CLI's config folder pointed at a scratch one for its length.

    Every stand-in session writes its log where the real CLI would, and the runner reads it
    from there - so a caller's own CLAUDE_CONFIG_DIR must neither receive fixture logs nor
    decide what the cases read. Restored exactly afterwards, absent if it was absent.
    """
    from house_common import isolated_env                             # noqa: PLC0415

    with isolated_env("CLAUDE_CONFIG_DIR", "CLAUDE_EFFORT"):
        return _selftest()


def _selftest() -> int:
    """Every stop condition proved BOTH ways, and the pre-flight proved to REFUSE.

    A LOOP THAT NEVER STOPS PASSES A SUITE OF 'IT RAN' PERFECTLY, so each case below pairs
    the state that must halt the loop with the nearest state that must not.
    """
    import contextlib                                                # noqa: PLC0415
    import io                                                        # noqa: PLC0415
    import os                                                        # noqa: PLC0415

    from house_common import Case, report_pairing, run_cases         # noqa: PLC0415

    print("SELFTEST - the loop must stop on every condition, and the pre-flight must refuse\n")
    tmp = Path(tempfile.mkdtemp(prefix="auto_mode_headless_selftest_"))
    os.environ["CLAUDE_CONFIG_DIR"] = str(tmp / "cli-config")
    ok = True

    def state_at(d: Path, n=2, k=0, status=RUNNING, active="no", effort=None) -> Path:
        d.mkdir(parents=True, exist_ok=True)
        f = d / "AUTO-MODE-RUN.md"
        eff = f"EFFORT:     {effort}\n" if effort else ""
        f.write_bytes((f"# t\n\n```auto-mode\nRUN_ID:     t\nN:          {n}\nK:  "
                       f"        {k}\nSTATUS:     {status}\nBRANCH:     session/t\n"
                       f"HOP_ACTIVE: {active}\nWOKE:       -\n{eff}```\n").encode("utf-8"))
        return f

    def refusal(f: Path) -> str:
        fields, _r, _t = read_state(f)
        return "REFUSE" if start_refusal(fields) else "START"

    cases = [
        Case("a stopped run does not start", refusal,
             bad=lambda d: state_at(d, status="STOPPED"),
             good=lambda d: state_at(d),
             want="REFUSE", good_want="START"),
        Case("a finished run does not start", refusal,
             bad=lambda d: state_at(d, n=2, k=2),
             good=lambda d: state_at(d, n=2, k=1),
             want="REFUSE", good_want="START"),
        Case("a held lock does not start", refusal,
             bad=lambda d: state_at(d, active="yes"),
             good=lambda d: state_at(d, active="no"),
             want="REFUSE", good_want="START"),
    ]

    def loop_verdict(pair) -> str:
        """require_cycle OFF here: these cases are about the OTHER stop conditions, and a
        stub that also had to record verify and test would test two things at once. The gate
        gets its own pair below, where it is the only variable."""
        d, stub = pair
        os.environ["STUB_CWD"] = str(d)
        rc, lines = loop(d / "AUTO-MODE-RUN.md", [sys.executable, str(stub)], [], d,
                         d / "tr", 120, require_cycle=False)
        return "STOPPED" if rc != RC_OK else "RAN"

    def cycle_verdict(pair) -> str:
        d, stub = pair
        os.environ["STUB_CWD"] = str(d)
        rc, _lines = loop(d / "AUTO-MODE-RUN.md", [sys.executable, str(stub)], [], d,
                          d / "tr", 120, require_cycle=True)
        return "STOPPED" if rc != RC_OK else "RAN"

    def cut_verdict(pair) -> str:
        """WHICH reason the runner gave, not whether it stopped. Both arms stop."""
        d, stub = pair
        os.environ["STUB_CWD"] = str(d)
        _rc, out = loop(d / "AUTO-MODE-RUN.md", [sys.executable, str(stub)], [], d,
                        d / "tr", 120, require_cycle=False)
        return "BUDGET" if any("BUDGET EXHAUSTED" in ln for ln in out) else "GENERIC"

    def model_verdict(pair) -> str:
        """What the report says about the model, given the pre-flight ran on _PRE_MODEL."""
        d, stub = pair
        os.environ["STUB_CWD"] = str(d)
        _rc, out = loop(d / "AUTO-MODE-RUN.md", [sys.executable, str(stub)], [], d,
                        d / "tr", 120, require_cycle=False, expect_models=[_PRE_MODEL])
        if any("MODEL CHANGE" in ln for ln in out):
            return "REPORTED"
        return "NOT CHECKED" if any("NOT CHECKED" in ln for ln in out) else "QUIET"

    def build(body):
        def make(d: Path, body=body):
            d.mkdir(parents=True, exist_ok=True)
            state_at(d, n=2, k=0)
            return (d, _stub(d, "stub.py", body))
        return make

    cases += [
        Case("a hop that never CLAIMS halts the loop", loop_verdict,
             bad=build(_NOCLAIM), good=build(_GOOD),
             want="STOPPED", good_want="RAN"),
        Case("a hop that never RELEASES halts the loop", loop_verdict,
             bad=build(_NORELEASE), good=build(_GOOD),
             want="STOPPED", good_want="RAN"),
        Case("a hop that FAILS halts the loop", loop_verdict,
             bad=build(_FAILS), good=build(_GOOD),
             want="STOPPED", good_want="RAN"),
        # THE GATE, AS THE ONLY VARIABLE. Both stubs claim, work and release cleanly; the
        # only difference is whether verify and test were recorded. A hop that skipped them
        # must halt the chain, and one that ran them must not be punished for it.
        Case("a hop that did NOT verify+test halts the loop", cycle_verdict,
             bad=build(_GOOD), good=build(_GOOD_WITH_CYCLE),
             want="STOPPED", good_want="RAN"),
        # AND A PHASE DECLARED N/A WITH A REASON IS DONE, not skipped - the house's own
        # discipline. Without this arm the gate would push a hop into running something
        # irrelevant just to have a record.
        Case("...and a DECLARED N/A counts as done", cycle_verdict,
             bad=build(_GOOD), good=build(_GOOD_WITH_NA),
             want="STOPPED", good_want="RAN"),
        # THE BUDGET CUT IS NAMED, AND A CRASH IS NOT MISLABELLED AS ONE. Both arms exit 1
        # and both halt the loop, so "did it stop?" cannot tell them apart - the case is
        # about WHICH REASON is reported, which is the whole value of reading the result
        # object. Without the second arm, a runner that shouted BUDGET at every failure
        # would pass.
        Case("a budget cut is reported BY NAME, not as a crash", cut_verdict,
             bad=build(_BUDGET_CUT), good=build(_PLAIN_CRASH),
             want="BUDGET", good_want="GENERIC"),
        # THE MODEL SWITCH, v5. Both hops claim, release and exit 0, so nothing else in the
        # report can tell them apart - v4 printed the same line for both. The second pair is
        # the zero-versus-unmeasured rule: a result naming no model must say so, not go quiet.
        Case("a hop that SWITCHED model is reported by name", model_verdict,
             bad=build(_SWITCHED), good=build(_SAME_MODEL),
             want="REPORTED", good_want="QUIET"),
        Case("...and one naming NO model says NOT CHECKED", model_verdict,
             bad=build(_GOOD), good=build(_SAME_MODEL),
             want="NOT CHECKED", good_want="QUIET"),
    ]

    # ---- the two readers, proved on their own. Both degrade rather than raise, and the
    #      failure they must not have is rendering "nothing measured" as a zero.
    cases += [
        Case("output that is not a result object degrades to raw",
             lambda payload: "META" if _render(payload)[0] else "RAW",
             bad=lambda d: "I am not JSON at all",
             good=lambda d: json.dumps({"type": "result", "result": "hi"}),
             want="RAW", good_want="META"),
        Case("a cut session names its subtype instead of rendering blank",
             lambda payload: _render(payload)[1],
             bad=lambda d: json.dumps({"type": "result", "result": None,
                                       "subtype": "error_max_budget_usd"}),
             good=lambda d: json.dumps({"type": "result", "result": "the real answer"}),
             want="(no final message - error_max_budget_usd)", good_want="the real answer"),
        Case("an UNMEASURED session reports nothing, never a zero",
             lambda m: usage_line(m) or "EMPTY",
             bad=lambda d: None,
             good=lambda d: {"num_turns": 3, "total_cost_usd": 0.5, "duration_ms": 2000,
                             "terminal_reason": "completed"},
             want="EMPTY", good_want="turns=3  cost=$0.5000  2s  end=completed"),
        Case("the usage line names the models, when reported",
             lambda m: "NAMED" if "models=" in usage_line(m) else "ABSENT",
             bad=lambda d: {"num_turns": 3, "terminal_reason": "completed"},
             good=lambda d: {"num_turns": 3, "terminal_reason": "completed",
                             "modelUsage": {_PRE_MODEL: {"costUSD": 0.1}}},
             want="ABSENT", good_want="NAMED"),
        Case("the usage line names the session, when reported",
             lambda m: "NAMED" if "session=" in usage_line(m) else "ABSENT",
             bad=lambda d: {"num_turns": 3, "terminal_reason": "completed"},
             good=lambda d: {"num_turns": 3, "terminal_reason": "completed",
                             "session_id": "0f0e"},
             want="ABSENT", good_want="NAMED"),
    ]

    # ---- THE EFFORT, v6. The reader first, on logs written the way the CLI writes them.
    def log_at(d: Path, efforts, sid="5e55-1"):
        """A session log under d/projects: one MESSAGE per item, each written as TWO entries
        (one per content block, as measured). None writes a message with no effort at all."""
        p = d / "projects" / "proj"
        p.mkdir(parents=True, exist_ok=True)
        rows = [json.dumps({"type": "assistant", "message": {"id": f"m{i}"},
                            **({"effort": e} if e is not None else {})})
                for i, e in enumerate(efforts) for _block in range(2)]
        rows.append(json.dumps({"type": "user", "message": {"content": "x"}}))
        (p / f"{sid}.jsonl").write_bytes(("\n".join(rows) + "\n").encode("utf-8"))
        return {"session_id": sid}, d / "projects"

    def read_effort(meta_root) -> str:
        meta, root = meta_root
        return effort_check(meta, "xhigh", root)[0]

    def e2e(honour: bool, effort):
        """A state file, and a stand-in CLI that does or does not honour --effort."""
        def make(d: Path):
            state_at(d, n=1, k=0, effort=effort)
            return (d, _stub(d, "cli.py", f"HONOUR = {honour}\n" + _LOG_HEAD + _E2E_BODY))
        return make

    def main_verdict(pair) -> str:
        """The whole chain through main(): did it start a hop, and how many ran."""
        d, stub = pair
        os.environ["STUB_CWD"] = str(d)
        with contextlib.redirect_stdout(io.StringIO()):
            rc = main(["--run", "--file", str(d / "AUTO-MODE-RUN.md"),
                       "--transcripts", str(d / "tr"), "--exec", str(stub)])
        hops = len(list((d / "tr").glob("*.txt"))) if (d / "tr").is_dir() else 0
        return f"{'RAN' if rc == RC_OK else 'REFUSED'}/{hops} hop(s)"

    def dry_verdict(f: Path) -> str:
        with contextlib.redirect_stdout(io.StringIO()):
            rc = main(["--dry-run", "--file", str(f)])
        return "START" if rc == RC_OK else "REFUSE"

    def effort_verdict(pair) -> str:
        """What the report says about a hop's effort when the run is at xhigh - and whether the
        chain carried on, because a MISMATCH halts and a NOT CHECKED does not."""
        d, stub = pair
        os.environ["STUB_CWD"] = str(d)
        rc, out = loop(d / "AUTO-MODE-RUN.md", [sys.executable, str(stub)],
                       ["--effort", "xhigh"], d, d / "tr", 120, require_cycle=False,
                       expect_effort="xhigh")
        seen = ("MISMATCH" if any("EFFORT MISMATCH" in ln for ln in out)
                else "NOT CHECKED" if any("effort NOT CHECKED" in ln for ln in out)
                else "CONFIRMED" if any("effort CONFIRMED" in ln for ln in out)
                else "SILENT")
        return f"{seen}/{'ran' if rc == RC_OK else 'stopped'}"

    def timeout_verdict(pair) -> str:
        """WHICH reason, and whether the runner came back in time - v5 waited for the child."""
        d, stub = pair
        os.environ["STUB_CWD"] = str(d)
        t0 = time.time()
        _rc, out = loop(d / "AUTO-MODE-RUN.md", [sys.executable, str(stub)], [], d,
                        d / "tr", 2, require_cycle=False)
        took = time.time() - t0
        label = "TIMEOUT" if any("TIMEOUT at hop" in ln for ln in out) else "GENERIC"
        return f"{label}/{'in time' if took < 8 else f'waited {took:.0f}s'}"

    cases += [
        Case("a mixed log is a MISMATCH, not a majority", read_effort,
             bad=lambda d: log_at(d, ["xhigh", "xhigh", "medium"]),
             good=lambda d: log_at(d, ["xhigh", "xhigh", "xhigh"]),
             want="EFFORT MISMATCH", good_want="CONFIRMED"),
        Case("a result naming no session is NOT CHECKED", read_effort,
             bad=lambda d: ({"type": "result"}, d / "projects"),
             good=lambda d: log_at(d, ["xhigh"]),
             want="NOT CHECKED", good_want="CONFIRMED"),
        Case("a log recording no effort is NOT CHECKED", read_effort,
             bad=lambda d: log_at(d, [None, None]),
             good=lambda d: log_at(d, ["xhigh", "xhigh"]),
             want="NOT CHECKED", good_want="CONFIRMED"),
        Case("a --flag naming a flag the runner owns",
             lambda extra: "REFUSED" if build_flags("xhigh", None, extra)[1] else "ADDED",
             bad=lambda d: ["--effort=medium"], good=lambda d: ["--verbose"],
             want="REFUSED", good_want="ADDED"),
        Case("a hop at ANOTHER effort halts the chain", effort_verdict,
             bad=build(_HOP_IGNORES), good=build(_HOP_HONOURS),
             want="MISMATCH/stopped", good_want="CONFIRMED/ran"),
        Case("...and a log it cannot find is NOT CHECKED", effort_verdict,
             bad=build(_HOP_NO_LOG), good=build(_HOP_HONOURS),
             want="NOT CHECKED/ran", good_want="CONFIRMED/ran"),
        Case("a pre-flight at the WRONG effort: no hop", main_verdict,
             bad=e2e(False, "xhigh"), good=e2e(True, "xhigh"),
             want="REFUSED/0 hop(s)", good_want="RAN/1 hop(s)"),
        Case("a state naming NO effort starts no hop", main_verdict,
             bad=e2e(True, None), good=e2e(True, "xhigh"),
             want="REFUSED/0 hop(s)", good_want="RAN/1 hop(s)"),
        Case("...and --dry-run says it WOULD REFUSE", dry_verdict,
             bad=lambda d: state_at(d, effort=None), good=lambda d: state_at(d, effort="xhigh"),
             want="REFUSE", good_want="START"),
        # THE TIMEOUT, NAMED AND REAL. The bad arm is the measured shape - a child holding the
        # pipe - so a kill that stops only the launched process comes back late AND unnamed.
        Case("a timeout is NAMED and cuts the whole tree", timeout_verdict,
             bad=build(_SLEEPER), good=build(_PLAIN_CRASH),
             want="TIMEOUT/in time", good_want="GENERIC/in time"),
    ]

    ok_cases, paired, unpaired = run_cases(cases, tmp, width=44)
    ok &= ok_cases

    # ---- the assertions a case table cannot make, because they are about the ARTEFACT.
    print()

    # 1. THE TRANSCRIPT IS WRITTEN AND IS NOT EMPTY. A loop that ran and captured nothing
    #    leaves the hop's output exactly where the scheduled-slot design left it: nowhere.
    d = tmp / "tr-arm"
    d.mkdir(parents=True, exist_ok=True)
    state_at(d, n=1, k=0)
    stub = _stub(d, "stub.py", _GOOD)
    os.environ["STUB_CWD"] = str(d)
    loop(d / "AUTO-MODE-RUN.md", [sys.executable, str(stub)], [], d, d / "tr", 120,
         require_cycle=False)
    made = sorted((d / "tr").glob("*.txt"))
    good = len(made) == 1 and made[0].stat().st_size > 0 and "hop done" in \
        made[0].read_text(encoding="utf-8")
    ok &= good
    print(f"  {'OK  ' if good else 'MISS'} the transcript is on disk and carries the output"
          f"  -> {[p.name for p in made]}")

    # 2. THE CEILING HOLDS EVEN IF EVERY HOP BEHAVES. N = 2 must launch twice and no more.
    d2 = tmp / "ceiling"
    d2.mkdir(parents=True, exist_ok=True)
    state_at(d2, n=2, k=0)
    stub2 = _stub(d2, "stub.py", _GOOD)
    os.environ["STUB_CWD"] = str(d2)
    _rc, lines = loop(d2 / "AUTO-MODE-RUN.md", [sys.executable, str(stub2)], [], d2,
                      d2 / "tr", 120, require_cycle=False)
    launched = len(list((d2 / "tr").glob("*.txt")))
    good = launched == 2
    ok &= good
    print(f"  {'OK  ' if good else 'MISS'} N = 2 launches exactly twice"
          f"                     -> {launched} launched")

    # 3. THE PRE-FLIGHT REFUSES A GUARD THAT IS NOT THERE. This is the one assertion that
    #    would have caught an unattended run starting with bounded authority absent.
    verdict, _why, _t, _m = preflight(tmp / "no-such-guard.py", [sys.executable], [])
    good = verdict == "VOID"
    ok &= good
    print(f"  {'OK  ' if good else 'MISS'} a missing guard is VOID, never a pass"
          f"            -> {verdict}")

    # 4. ...AND A GUARD THAT LETS THE CANARY DIE IS 'ABSENT', NOT 'BIT'. Proved with a stub
    #    that deletes the canary, which is what an unhooked session would do.
    killer = tmp / "killer.py"
    killer.write_bytes(b"import os\nos.remove('canary.txt')\nprint('deleted')\n")
    verdict2, _why2, _t2, _m2 = preflight(HERE / "auto_mode_guard.py",
                                     [sys.executable, str(killer)], [])
    good = verdict2 == "GUARD ABSENT"
    ok &= good
    print(f"  {'OK  ' if good else 'MISS'} a deleted canary reads as GUARD ABSENT"
          f"           -> {verdict2}")

    # 5. ...AND A SURVIVING CANARY WITH NO REFUSAL TEXT IS INCONCLUSIVE, NOT A PASS. This is
    #    the confound: the model can decline all by itself, which is not a control.
    quiet = tmp / "quiet.py"
    quiet.write_bytes(b"print('I would rather not delete that.')\n")
    verdict3, _why3, _t3, _m3 = preflight(HERE / "auto_mode_guard.py",
                                     [sys.executable, str(quiet)], [])
    good = verdict3 == "INCONCLUSIVE"
    ok &= good
    print(f"  {'OK  ' if good else 'MISS'} a polite refusal is INCONCLUSIVE, not BIT"
          f"        -> {verdict3}")

    # 6. THE DEFECT v1 SHIPPED WITH, REPRODUCED. A session that never ran leaves the canary
    #    alive for the one reason that says nothing about the guard - and the first real
    #    --check reported INCONCLUSIVE for a CLI that could not even authenticate. Written
    #    as an assertion so the shape cannot come back.
    dead = tmp / "dead.py"
    dead.write_bytes(b"import sys\nsys.stderr.write('Failed to authenticate\\n')\n"
                     b"sys.exit(1)\n")
    verdict4, why4, _t4, _m4 = preflight(HERE / "auto_mode_guard.py",
                                    [sys.executable, str(dead)], [])
    good = verdict4 == "VOID" and "did not complete" in why4
    ok &= good
    print(f"  {'OK  ' if good else 'MISS'} a session that never RAN is VOID, not a verdict"
          f"   -> {verdict4}")

    # 7. THE PROMPT ARRIVES WHOLE. On Windows a newline inside an argv element is truncated
    #    by the .CMD shim, silently and with exit 0 - so a multi-line instruction arrives as
    #    its first line. Asserted on the LAST line of the prompt, because a truncation keeps
    #    the first one and every other signal looks fine. See launch().
    echoer = tmp / "echo_stdin.py"
    echoer.write_bytes(b"import sys\nprint(sys.stdin.read())\n")
    _v5, _w5, t5, _m5 = preflight(HERE / "auto_mode_guard.py", [sys.executable, str(echoer)],
                                  [])
    tail = PREFLIGHT_PROMPT.strip().splitlines()[-1].strip()
    head = PREFLIGHT_PROMPT.splitlines()[0].strip()
    good = tail in t5 and head in t5
    ok &= good
    print(f"  {'OK  ' if good else 'MISS'} the prompt reaches the child WHOLE, not line 1"
          f"   -> first line {'yes' if head in t5 else 'NO'}, "
          f"last line {'yes' if tail in t5 else 'NO'}")

    # 8. A --flag ADDS TO THE REQUIRED FLAGS AND NEVER REPLACES THEM. v5 replaced them, so
    #    passing one flag silently dropped bypassPermissions and the json every check reads.
    got, _why = build_flags("xhigh", 2.5, ["--verbose"])
    want = [*DEFAULT_FLAGS, "--max-budget-usd", "2.5", "--effort", "xhigh", "--verbose"]
    good = got == want
    ok &= good
    print(f"  {'OK  ' if good else 'MISS'} a --flag is added, the required flags kept"
          f"     -> {' '.join(got or [])}")

    # 9. THE LOG IS COUNTED PER MESSAGE, NOT PER ENTRY. One message is several entries - 176
    #    entries were 82 messages on a real hop - so an entry count overstates by 2x or more.
    (tmp / "per-msg").mkdir(exist_ok=True)
    meta9, root9 = log_at(tmp / "per-msg", ["xhigh", "xhigh", "xhigh"])
    verdict9, detail9 = effort_check(meta9, "xhigh", root9)
    good = verdict9 == "CONFIRMED" and "3 of 3 messages" in detail9
    ok &= good
    print(f"  {'OK  ' if good else 'MISS'} six entries are counted as THREE messages"
          f"      -> {detail9}")

    # 10. THE FLAGS LINE SHOWS THE EFFORT - the line the house rule tells the arming session to
    #     read before it hands the launch command over. Read off main()'s own output.
    d10 = tmp / "flags-line"
    d10.mkdir(parents=True, exist_ok=True)
    _d, stub10 = e2e(True, "xhigh")(d10)
    os.environ["STUB_CWD"] = str(d10)
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        main(["--run", "--file", str(d10 / "AUTO-MODE-RUN.md"), "--transcripts",
              str(d10 / "tr"), "--exec", str(stub10)])
    shown = [ln for ln in buf.getvalue().splitlines() if ln.startswith("  flags")]
    good = len(shown) == 1 and "--effort xhigh" in shown[0]
    ok &= good
    print(f"  {'OK  ' if good else 'MISS'} the flags line shows --effort"
          f"                 -> {shown[0].strip() if shown else 'NO FLAGS LINE'}")

    # 11. THE REVIEW'S FIXES, each asserted on what it produces. A zero timeout is refused
    #     rather than printed as NONE and applied as instant death; a --file that is not
    #     there is VOID for --check too; the permission-bypass alias is a runner-owned flag;
    #     and a mismatch on the LAST hop says so rather than naming a next hop.
    with contextlib.redirect_stdout(io.StringIO()):
        rc_t0 = main(["--check", "--effort", "low", "--timeout", "0"])
        rc_nf = main(["--check", "--effort", "low", "--file", str(tmp / "no-such.md")])
    alias = build_flags("xhigh", None, ["--dangerously-skip-permissions"])[1] is not None
    d11 = tmp / "last-hop"
    d11.mkdir(parents=True, exist_ok=True)
    state_at(d11, n=1, k=0)
    stub11 = _stub(d11, "stub.py", _HOP_IGNORES)
    os.environ["STUB_CWD"] = str(d11)
    _rc11, out11 = loop(d11 / "AUTO-MODE-RUN.md", [sys.executable, str(stub11)],
                        ["--effort", "xhigh"], d11, d11 / "tr", 120, require_cycle=False,
                        expect_effort="xhigh")
    last_said = any("It was the last hop" in ln for ln in out11)
    good = (rc_t0 == RC_COULD_NOT_RUN and rc_nf == RC_COULD_NOT_RUN and alias and last_said)
    ok &= good
    print(f"  {'OK  ' if good else 'MISS'} the review's four fixes hold"
          f"                   -> timeout 0 rc={rc_t0}, missing --file rc={rc_nf}, "
          f"alias refused={alias}, last hop named={last_said}")

    # 12. AN INTERRUPTED RUNNER TAKES THE HOP DOWN WITH IT. communicate() is made to raise
    #     KeyboardInterrupt while a hop whose child holds the pipe is running; the interrupt
    #     must propagate AND the child's heartbeat must stop - subprocess.run killed the child
    #     on the way out, and a bare Popen does not unless told to.
    beat = tmp / "beat.txt"
    hb = tmp / "hb.py"
    hb.write_bytes(("import time, pathlib\np = pathlib.Path(r'" + str(beat) + "')\n"
                    "for i in range(60):\n    p.write_text(str(i)); time.sleep(0.2)\n")
                   .encode("utf-8"))
    parent = tmp / "parent.py"
    parent.write_bytes(("import subprocess, sys, time\n"
                        f"subprocess.Popen([sys.executable, r'{hb}'], stdout=sys.stdout)\n"
                        "time.sleep(12)\n").encode("utf-8"))
    real_comm = subprocess.Popen.communicate
    calls = {"n": 0}

    def interrupted(self, *a, **kw):
        calls["n"] += 1
        if calls["n"] == 1:
            time.sleep(1.5)                                  # let the child start beating
            raise KeyboardInterrupt
        return real_comm(self, *a, **kw)

    subprocess.Popen.communicate = interrupted
    propagated = False
    try:
        launch([sys.executable, str(parent)], "", tmp, None)
    except KeyboardInterrupt:
        propagated = True
    finally:
        subprocess.Popen.communicate = real_comm
    time.sleep(0.6)
    first = beat.read_text() if beat.exists() else ""
    time.sleep(1.0)
    second = beat.read_text() if beat.exists() else ""
    good = propagated and first != "" and first == second
    ok &= good
    print(f"  {'OK  ' if good else 'MISS'} an interrupt kills the hop's whole tree"
          f"         -> propagated={propagated}, heartbeat "
          f"{'stopped' if first and first == second else 'STILL GOING' if first else 'never began'}")

    print()
    report_pairing(paired, unpaired)
    shutil.rmtree(tmp, ignore_errors=True)
    print("\nSELFTEST: " + ("PASS" if ok else "FAIL"))
    return RC_OK if ok else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
