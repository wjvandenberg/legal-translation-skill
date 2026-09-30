#!/usr/bin/env python3
"""auto_mode.py - the counter an unattended chain of sessions runs on.  CHECKER VERSION 3 (2026-09-30)

If a project's copy says a lower version than this one, it is stale - see the "Checkers"
line for each version in ...\\Coding\\templates\\TEMPLATE-CHANGELOG.md and re-copy.

WHAT THIS IS FOR. AUTO MODE runs N sessions unattended. Each one starts with NO MEMORY of
the last, so everything it needs about the run as a whole has to be readable from a file on
disk. That file is AUTO-MODE-RUN.md, and this script is the only thing that writes the
fields inside it.

THE DEFECT THAT PRODUCED THIS SCRIPT, measured on the first real hop. The counter recorded
WHO WROTE THE FILE, not who was running. A woken session read K = 1, which was true of the
session that had armed it hours earlier, and had to work out that it was really hop 1 by
reading a job-description table instead. That is unambiguous with one hop and AMBIGUOUS
WITH FOUR: every hop would read the same number, and nothing would tell hop 3 from hop 4.

So the field has to be advanced BY THE ARRIVING SESSION, AS ITS FIRST ACT - and "as its
first act" has to be a mechanism, not an instruction, because an instruction is enforced by
the very thing it is meant to bind.

WHY THE FIELDS LIVE IN A FENCED BLOCK AND NOT IN THE PROSE TABLE THEY REPLACED. A field a
script rewrites must not share a cell with a sentence a person wrote: one of the two gets
destroyed, and it is never the one you were watching. The prose stays in the document
around the block, where nothing overwrites it.

THE LOCK, AND WHY A COUNTER IS THE RIGHT PLACE FOR IT. If every hop is armed up front - the
decided design, because it means a hop may never create a scheduled task and that rule needs
no exception - then a slow hop can still be running when the next one fires. Two sessions in
one working tree consume and overwrite each other's files, and the failure is intermittent,
which is worse than reproducible. HOP_ACTIVE is claimed and released here, so an overlapping
hop halts on arrival and says so instead of racing.

    uv run python tools/auto_mode.py --status     # what a hop needs to know, read-only
    uv run python tools/auto_mode.py --claim      # THE HOP'S FIRST ACT: take the next number
    uv run python tools/auto_mode.py --release    # the hop's last act: let the next one in
    uv run python tools/auto_mode.py --arm --run-id X --hops 4 --branch session/y --effort xhigh
    uv run python tools/auto_mode.py --stop       # the off switch, same as editing the file
    uv run python tools/auto_mode.py --blocked    # THE HOP'S own halt: a question it may
                                                 # not answer alone. STOPPED is a person
                                                 # intervening; BLOCKED is the chain saying
                                                 # it will not guess. Kept apart on purpose.
    uv run python tools/auto_mode.py --selftest   # every refusal proved BOTH ways

THE EFFORT A HOP RUNS AT (v3), AND WHY ARMING REFUSES WITHOUT IT. Measured 2026-09-30: a
desktop session at `xhigh` armed a run, the runner was started from a plain terminal, and the
hop's own log recorded `medium` - the CLI's default - on every message. Nothing reported it;
it was found because somebody asked. So --arm records EFFORT in the block, from --effort or
CLAUDE_EFFORT, and REFUSES when neither is there, when the two disagree, or when the runner
beside it is too old to pass it on. EFFORT is an OPTIONAL field - a block without it still
reads - and the runner is what refuses to START a run that names none.

K COUNTS HOPS AND SO DOES N. The attended session that sets the run up is not a hop and is
not counted; K = 0 means no hop has run yet, K = 2 means hop 2 is the one now running. The
file used to count sessions in one field and hops in another, which is how "N = 1 means two
sessions" came to need a paragraph of explanation.

EXIT CODES.  0 = done.  1 = REFUSED, and the refusal is the answer: halt.
2 = could not run at all (no state file, no fenced block, or a field that will not parse).
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

RC_OK, RC_REFUSED, RC_COULD_NOT_RUN = 0, 1, 2

STATE_NAME = "AUTO-MODE-RUN.md"
FENCE_INFO = "auto-mode"

#: The fields the block carries, in the order they are written back. A fixed order means
#: two runs of this script produce byte-identical blocks, so a diff shows the change and
#: nothing else.
FIELDS = ("RUN_ID", "N", "K", "STATUS", "BRANCH", "HOP_ACTIVE", "WOKE")

#: FIELDS A BLOCK MAY LACK, written back only when present. EFFORT is here and not in FIELDS
#: for the reason BLOCKED is a status value: read_state refuses a block missing any REQUIRED
#: field, so a new required one would make every state file armed before v3 VOID. It is
#: required where it matters instead - the runner refuses to START a run that names none.
OPTIONAL_FIELDS = ("EFFORT",)

#: WHAT `claude --effort` ACCEPTS, copied off CLI 2.1.283's own help rather than typed from
#: memory: "(low, medium, high, xhigh, max)". A level outside it is refused at --arm, where a
#: person is still there to correct it, instead of at a hop's launch, where nobody is.
EFFORT_LEVELS = ("low", "medium", "high", "xhigh", "max")

#: THE FIRST RUNNER THAT PASSES EFFORT ON. auto_mode_headless.py is not in check_checkers'
#: tracked list, so a project re-copying this counter is told nothing about the runner beside
#: it - and a v5 runner ignores EFFORT, launching every hop at the CLI default. --arm is the
#: one place that sees both files, so it refuses there. The fix for caller N+1, not a note.
RUNNER_NAME = "auto_mode_headless.py"
RUNNER_MIN_VERSION = 6

RUNNING, STOPPED, COMPLETE = "RUNNING", "STOPPED", "COMPLETE"

#: BLOCKED is the hop's OWN off switch, and it is a fourth value rather than a reuse of
#: STOPPED because the two mean different things to whoever reads the file afterwards:
#: STOPPED is a person intervening, BLOCKED is a hop that met a question it may not answer.
#: Collapsing them would make an unattended chain's most important outcome unreadable.
#:
#: WHY A STATUS VALUE AND NOT A NEW FIELD. read_state refuses a block that is missing any
#: declared field, so adding one would make every existing state file VOID - a migration
#: cost paid by every project, to carry a string the decision record already holds. The
#: reason belongs in DECISIONS-LOG.md, which a hop must write to anyway; this field only has
#: to carry the fact.
BLOCKED = "BLOCKED"

_FENCE = re.compile(
    r"(?P<open>^```" + FENCE_INFO + r"[ \t]*\r?\n)(?P<body>.*?)(?P<close>^```[ \t]*$)",
    re.M | re.S,
)


# ------------------------------------------------------------------ finding the state file

def find_state_file(explicit: str | None = None) -> Path | None:
    """--file, then AUTO_MODE_RUN_FILE, then walk up from the working directory.

    WALKING UP IS NOT A CONVENIENCE. A hop is woken with whatever working directory the
    scheduler happened to give it, and a state file found relative to the wrong folder is
    a state file that reads as absent - which this script would answer by allowing
    everything, silently.
    """
    if explicit:
        p = Path(explicit).expanduser()
        return p if p.exists() else None
    env = os.environ.get("AUTO_MODE_RUN_FILE")
    if env:
        p = Path(env).expanduser()
        return p if p.exists() else None
    here = Path.cwd().resolve()
    for d in (here, *here.parents):
        cand = d / STATE_NAME
        if cand.exists():
            return cand
    return None


# ------------------------------------------------------------------- reading and writing

class Void(Exception):
    """The state could not be read. Never the same thing as a clean answer."""


def read_state(f: Path) -> tuple[dict, bytes, str]:
    """Return (fields, original-bytes, line-terminator).

    Bytes, not text. Python's text mode turns \\n into \\r\\n on Windows on the way out,
    and this repository's .gitattributes says line endings are never translated - so a
    round trip through text mode rewrites every line of a file it was asked to change one
    field of. The terminator is taken from the file itself and handed back unchanged.
    """
    try:
        raw = f.read_bytes()
    except OSError as e:
        raise Void(f"cannot read {f} - {e}") from e
    text = raw.decode("utf-8-sig")
    m = _FENCE.search(text)
    if not m:
        raise Void(f"{f} has no ```{FENCE_INFO} block. Nothing was read.")
    term = "\r\n" if "\r\n" in m.group("open") else "\n"
    fields: dict[str, str] = {}
    for line in m.group("body").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            raise Void(f"{f}: line {line!r} in the {FENCE_INFO} block is not KEY: value")
        k, _, v = line.partition(":")
        fields[k.strip().upper()] = v.strip()
    missing = [k for k in FIELDS if k not in fields]
    if missing:
        raise Void(f"{f}: the {FENCE_INFO} block is missing {', '.join(missing)}")
    return fields, raw, term


def write_state(f: Path, fields: dict, raw: bytes, term: str) -> None:
    """Rewrite the block body and NOTHING else. Bytes in, bytes out.

    An optional field is written only when the fields carry it, so a claim on a state file
    armed before v3 changes exactly what a v2 claim changed and adds no line.
    """
    text = raw.decode("utf-8-sig")
    width = max(len(k) for k in (*FIELDS, *OPTIONAL_FIELDS)) + 1
    keys = [*FIELDS, *(k for k in OPTIONAL_FIELDS if fields.get(k))]
    body = "".join(f"{k + ':':<{width}} {fields[k]}{term}" for k in keys)
    new = _FENCE.sub(lambda m: m.group("open") + body + m.group("close"), text, count=1)
    f.write_bytes(new.encode("utf-8"))


def as_int(fields: dict, key: str) -> int:
    try:
        return int(str(fields[key]).strip())
    except (KeyError, ValueError) as e:
        raise Void(f"{key} is {fields.get(key)!r}, which is not a whole number") from e


def now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M local")


# --------------------------------------------------------------------------- the actions

def act_status(fields: dict) -> tuple[int, list[str]]:
    """Read-only. Says what a hop needs, and says it in words as well as fields."""
    k, n = as_int(fields, "K"), as_int(fields, "N")
    out = [f"  RUN ID     {fields['RUN_ID']}",
           f"  STATUS     {fields['STATUS']}",
           f"  HOPS       {k} of {n} have started",
           f"  HOP_ACTIVE {fields['HOP_ACTIVE']}   (woke: {fields['WOKE']})",
           f"  BRANCH     {fields['BRANCH']}",
           f"  EFFORT     {fields.get('EFFORT') or 'NOT RECORDED - armed before v3, so the runner will refuse it'}"]
    if fields["STATUS"] != RUNNING:
        out.append(f"  -> the run is {fields['STATUS']}. A hop waking now must halt.")
    elif fields["HOP_ACTIVE"].lower() == "yes":
        out.append(f"  -> hop {k} is ALREADY ACTIVE. A hop waking now must halt.")
    elif k >= n:
        out.append("  -> every hop has run. A hop waking now must halt.")
    else:
        out.append(f"  -> the next hop to claim will be hop {k + 1} of {n}.")
    return RC_OK, out


def act_claim(fields: dict) -> tuple[int, list[str], bool]:
    """THE HOP'S FIRST ACT. Returns (exit code, lines, whether to write).

    Every refusal here is a REFUSAL, not an error: the run is over, or stopped, or another
    hop holds the lock. The hop halts and hands back. That is a normal outcome and it is
    reported as one.
    """
    k, n = as_int(fields, "K"), as_int(fields, "N")
    status = fields["STATUS"].upper()

    if status == STOPPED:
        return RC_REFUSED, ["REFUSED: STATUS is STOPPED - a person pulled the off switch.",
                            "         Halt and hand back. Do no work."], False
    if status == COMPLETE:
        return RC_REFUSED, ["REFUSED: STATUS is COMPLETE - this run has already finished.",
                            "         Halt and hand back. Do no work."], False
    if status == BLOCKED:
        return RC_REFUSED, ["REFUSED: STATUS is BLOCKED - a previous hop met a question it",
                            "         may not answer alone, and ended the chain rather than",
                            "         guessing. The reason is in the decision record.",
                            "         Halt and hand back. Do no work."], False
    if status != RUNNING:
        return RC_REFUSED, [f"REFUSED: STATUS is {fields['STATUS']!r}, which is not one of "
                            f"{RUNNING} / {STOPPED} / {COMPLETE}.",
                            "         Halt and hand back. Do no work."], False
    if fields["HOP_ACTIVE"].lower() == "yes":
        return RC_REFUSED, [f"REFUSED: hop {k} is already active (woke {fields['WOKE']}).",
                            "         Two hops in one working tree overwrite each other's",
                            "         files, and the damage is intermittent. Halt."], False
    if k >= n:
        # THE RUN IS OVER AND NOTHING HAD RECORDED IT. Refuse, and close the run in the same
        # breath - otherwise every later hop refuses forever against a file that still says
        # RUNNING, and the off switch never gets thrown.
        fields["STATUS"] = COMPLETE
        return RC_REFUSED, [f"REFUSED: K = {k} and N = {n} - every hop in this run has run.",
                            "         STATUS set to COMPLETE. Halt and hand back."], True

    fields["K"] = str(k + 1)
    fields["HOP_ACTIVE"] = "yes"
    fields["WOKE"] = now()
    return RC_OK, [f"  CLAIMED: you are hop {k + 1} of {n} in run {fields['RUN_ID']}.",
                   f"  BRANCH:  {fields['BRANCH']} - one branch for the whole run.",
                   f"  WOKE:    {fields['WOKE']}",
                   "",
                   "  Read the rest of " + STATE_NAME + " before doing anything else: the",
                   "  bounded-authority list there says what you may never do, and the",
                   "  decision record is where every judgement you take alone goes.",
                   "  Run --release as your LAST act."], True


def act_release(fields: dict) -> tuple[int, list[str], bool]:
    """The hop's last act. Also closes the run when the last hop finishes."""
    k, n = as_int(fields, "K"), as_int(fields, "N")
    if fields["HOP_ACTIVE"].lower() != "yes":
        return RC_REFUSED, ["REFUSED: nothing to release - HOP_ACTIVE is already 'no'.",
                            "         Either --claim never ran, or this is a second release.",
                            "         Both mean the counter no longer describes reality."], False
    fields["HOP_ACTIVE"] = "no"
    lines = [f"  RELEASED: hop {k} of {n} is finished."]
    if k >= n:
        fields["STATUS"] = COMPLETE
        lines.append("  STATUS set to COMPLETE - that was the last hop of the run.")
    else:
        lines.append(f"  The next hop to fire will claim hop {k + 1}.")
    return RC_OK, lines, True


def act_stop(fields: dict) -> tuple[int, list[str], bool]:
    if fields["STATUS"].upper() == STOPPED:
        return RC_OK, ["  Already STOPPED. Nothing changed."], False
    fields["STATUS"] = STOPPED
    return RC_OK, ["  STATUS set to STOPPED. The next hop that wakes will halt and hand back.",
                   "  Nothing running right now is interrupted by this."], True


def act_blocked(fields: dict) -> tuple[int, list[str], bool]:
    """THE HOP'S OWN OFF SWITCH, and the point of it is that it is MECHANICAL.

    The rule was already written down - a hop that meets a genuinely blocking question stops
    and hands back - and it was enforced by nothing but the hop's own judgement, which is the
    shape this house distrusts everywhere else. A run in which prose held is evidence about
    one obedient session.

    IT RELEASES THE LOCK IN THE SAME BREATH, deliberately. A hop that blocks and leaves
    HOP_ACTIVE at 'yes' looks identical to a hop that died mid-flight, and the next reader
    cannot tell a deliberate halt from a crash.
    """
    if fields["STATUS"].upper() != RUNNING:
        return RC_REFUSED, [f"REFUSED: STATUS is {fields['STATUS']!r}, not {RUNNING} - there "
                            f"is no live run to block."], False
    fields["STATUS"] = BLOCKED
    fields["HOP_ACTIVE"] = "no"
    return RC_OK, ["  STATUS set to BLOCKED. The chain ends here and hands back.",
                   "  WRITE THE QUESTION DOWN before you exit - the decision record is the",
                   "  only place it survives, and this field carries the fact, not the",
                   "  reason. Any hop waking after this is refused."], True


def normal_effort(value: str | None) -> str:
    """An effort as both scripts compare it: stripped and lower-cased, '' for none."""
    return (value or "").strip().lower()


def effort_level_error(level: str) -> str | None:
    """Why `level` is not one the CLI accepts, or None. THE ONE VALIDATOR: the counter and the
    runner both call it, so the two cannot come to disagree about what a level is."""
    if level not in EFFORT_LEVELS:
        return f"{level!r} is not a level the CLI accepts ({', '.join(EFFORT_LEVELS)})."
    return None


def resolve_effort(explicit: str | None, env: str | None) -> tuple[str | None, str]:
    """(level, where it came from) - or (None, why the arm is refused). Never a default.

    TWO SOURCES AND NEITHER IS TRUSTED ALONE. CLAUDE_EFFORT is what the desktop app sets for
    its own sessions, and it is a SOMETIMES-source: measured 2026-09-30, one desktop session
    showed `xhigh` to its Bash tool and NOTHING to its PowerShell tool. An explicit --effort is
    what a person states. Either will do; both must agree, because the whole point is that
    the hops run at THE SAME effort as the session arming them, and two sources that disagree
    is exactly the mistake to catch while somebody is still there to read it.
    """
    e, v = normal_effort(explicit), normal_effort(env)
    if e and v and e != v:
        return None, (f"--effort says {e!r} but CLAUDE_EFFORT says {v!r}. The hops are meant "
                      f"to run at the arming session's effort, and the two disagree.")
    level = e or v
    if not level:
        return None, ("no effort stated. Pass --effort <level> - the level THIS session runs "
                      "at (the desktop app shows it; in its Bash tool `echo $CLAUDE_EFFORT`). "
                      "A hop launched without one runs at the CLI's default, and nothing says so.")
    bad = effort_level_error(level)
    if bad:
        return None, bad
    return level, ("--effort and CLAUDE_EFFORT, agreeing" if e and v
                   else "--effort" if e else "CLAUDE_EFFORT")


def runner_version(folder: Path = HERE) -> int | None:
    """The CHECKER VERSION of the runner beside this counter, None when there is none, 0 when
    it names none. Read off its header, the same line check_checkers compares."""
    f = folder / RUNNER_NAME
    if not f.is_file():
        return None
    m = re.search(rb"CHECKER VERSION (\d+)", f.read_bytes()[:600])
    return int(m.group(1)) if m else 0


def act_arm(fields: dict, run_id: str, hops: int, branch: str, effort: str | None = None,
            env_effort: str | None = None,
            runner: int | None = None) -> tuple[int, list[str], bool]:
    """Set the run up. THE ATTENDED SESSION'S LAST ACT, and the order matters.

    Commit first, create the scheduled tasks second, arm third. The guard that refuses an
    unattended session's irreversible acts is live from the moment STATUS reads RUNNING, so
    arming before committing locks the arming session out of its own commit.

    AND IT RECORDS THE EFFORT (v3), refusing to arm without one - see resolve_effort. `runner`
    is the version of the runner beside this file (runner_version), None when there is none.
    """
    if hops < 1:
        return RC_REFUSED, [f"REFUSED: --hops is {hops}. A run with no hops is not a run."], False
    level, source = resolve_effort(effort, env_effort)
    if level is None:
        return RC_REFUSED, [f"REFUSED: {source}"], False
    if runner is not None and runner < RUNNER_MIN_VERSION:
        return RC_REFUSED, [f"REFUSED: the {RUNNER_NAME} beside this counter is v{runner}, and "
                            f"only v{RUNNER_MIN_VERSION}+ passes the effort to its hops - a",
                            "         stale one would launch every hop at the CLI default. "
                            "Re-copy it from the shared folder."], False
    fields.update({"RUN_ID": run_id, "N": str(hops), "K": "0", "STATUS": RUNNING,
                   "BRANCH": branch, "HOP_ACTIVE": "no", "WOKE": "-", "EFFORT": level})
    return RC_OK, [f"  ARMED: run {run_id}, {hops} hop(s), on branch {branch}.",
                   f"  EFFORT: {level} (from {source}) - every hop is launched at it, and the "
                   "runner reads back what each one ran at.",
                   f"  BEFORE HANDING OVER THE LAUNCH COMMAND: confirm the runner's flags line "
                   f"shows --effort {level}.",
                   "  K = 0: no hop has run yet. The first to claim becomes hop 1.",
                   "  Every hop must be scheduled ALREADY - a hop may not create a task."], True


# -------------------------------------------------------------------------------- driver

def main(argv) -> int:
    ap = argparse.ArgumentParser(add_help=True, description=__doc__.splitlines()[0])
    ap.add_argument("--file")
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--claim", action="store_true")
    ap.add_argument("--release", action="store_true")
    ap.add_argument("--stop", action="store_true")
    ap.add_argument("--blocked", action="store_true",
                    help="THE HOP'S OWN halt: a question it may not answer alone")
    ap.add_argument("--arm", action="store_true")
    ap.add_argument("--run-id")
    ap.add_argument("--hops", type=int)
    ap.add_argument("--branch")
    ap.add_argument("--effort", help="--arm: the effort THIS session runs at; else "
                                     "CLAUDE_EFFORT; refused when neither")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)

    if a.selftest:
        return selftest()

    chosen = [n for n in ("status", "claim", "release", "stop", "blocked", "arm")
              if getattr(a, n)]
    if len(chosen) != 1:
        print("  say exactly one of --status --claim --release --stop --blocked --arm")
        return RC_COULD_NOT_RUN

    f = find_state_file(a.file)
    if f is None:
        print(f"VOID: no {STATE_NAME} found here or in any parent directory, and no "
              f"AUTO_MODE_RUN_FILE set. Nothing was read.")
        return RC_COULD_NOT_RUN
    try:
        fields, raw, term = read_state(f)
    except Void as e:
        print(f"VOID: {e}")
        return RC_COULD_NOT_RUN

    print("=" * 92)
    print(f"AUTO MODE - {chosen[0].upper()}   ({f})")
    print("=" * 92)

    try:
        if a.arm:
            if not (a.run_id and a.hops is not None and a.branch):
                print("  --arm needs --run-id, --hops and --branch")
                return RC_COULD_NOT_RUN
            rc, lines, dirty = act_arm(fields, a.run_id, a.hops, a.branch, a.effort,
                                       os.environ.get("CLAUDE_EFFORT"), runner_version())
        elif a.claim:
            rc, lines, dirty = act_claim(fields)
        elif a.release:
            rc, lines, dirty = act_release(fields)
        elif a.stop:
            rc, lines, dirty = act_stop(fields)
        elif a.blocked:
            rc, lines, dirty = act_blocked(fields)
        else:
            rc, lines = act_status(fields)
            dirty = False
    except Void as e:
        print(f"VOID: {e}")
        return RC_COULD_NOT_RUN

    if dirty:
        write_state(f, fields, raw, term)
    for line in lines:
        print(line)
    print("=" * 92)
    return rc


# ------------------------------------------------------------------------------ selftest

BLOCK = """# AUTO-MODE-RUN

prose above the block, which must survive untouched

```auto-mode
RUN_ID:     r-test
N:          {n}
K:          {k}
STATUS:     {status}
BRANCH:     {branch}
HOP_ACTIVE: {active}
WOKE:       -
```

prose below the block, which must also survive untouched
"""


def _state(d: Path, n=3, k=0, status=RUNNING, active="no", branch="session/x") -> Path:
    f = d / STATE_NAME
    f.write_bytes(BLOCK.format(n=n, k=k, status=status, active=active,
                               branch=branch).encode("utf-8"))
    return f


def selftest() -> int:
    """Every refusal proved BOTH ways: it must fire on the bad state and stay quiet on the good.

    A CHECK THAT CANNOT TELL GOOD FROM BAD IS NOT A CHECK. A claim guard that refused every
    state would pass a suite of refusals perfectly and be useless, so each case below is a
    pair: the state that must be refused, and the nearest state that must be allowed.
    """
    import shutil
    import tempfile

    from house_common import Case, report_pairing, run_cases  # noqa: PLC0415

    print("SELFTEST - the counter must record who is RUNNING, and refuse when it cannot\n")
    tmp = Path(tempfile.mkdtemp(prefix="auto_mode_selftest_"))
    ok = True

    def claim(f: Path) -> str:
        fields, raw, term = read_state(f)
        rc, _lines, dirty = act_claim(fields)
        if dirty:
            write_state(f, fields, raw, term)
        return "REFUSED" if rc == RC_REFUSED else "CLAIMED"

    def release(f: Path) -> str:
        fields, raw, term = read_state(f)
        rc, _lines, dirty = act_release(fields)
        if dirty:
            write_state(f, fields, raw, term)
        return "REFUSED" if rc == RC_REFUSED else "RELEASED"

    cases = [
        Case("a stopped run refuses a hop", claim,
             bad=lambda d: _state(d, status=STOPPED),
             good=lambda d: _state(d, status=RUNNING),
             want="REFUSED", good_want="CLAIMED"),
        Case("a finished run refuses a hop", claim,
             bad=lambda d: _state(d, n=3, k=3),
             good=lambda d: _state(d, n=3, k=2),
             want="REFUSED", good_want="CLAIMED"),
        Case("the lock refuses an overlapping hop", claim,
             bad=lambda d: _state(d, k=1, active="yes"),
             good=lambda d: _state(d, k=1, active="no"),
             want="REFUSED", good_want="CLAIMED"),
        # BLOCKED MUST REFUSE THE NEXT HOP, or it is a status word and not an off switch.
        Case("a BLOCKED run refuses the next hop", claim,
             bad=lambda d: _state(d, status=BLOCKED),
             good=lambda d: _state(d, status=RUNNING),
             want="REFUSED", good_want="CLAIMED"),
        # ...and blocking is only meaningful on a LIVE run. Blocking a finished one would
        # rewrite the outcome of a run that already ended, which is the direction that
        # quietly falsifies a record.
        Case("only a LIVE run can be blocked", _probe_block,
             bad=lambda d: _state(d, status=COMPLETE),
             good=lambda d: _state(d, status=RUNNING),
             want="REFUSED", good_want="BLOCKED"),
        Case("release without a claim is refused", release,
             bad=lambda d: _state(d, k=1, active="no"),
             good=lambda d: _state(d, k=1, active="yes"),
             want="REFUSED", good_want="RELEASED"),
        Case("a block that will not parse is VOID", _probe_void,
             bad=lambda d: _bad_block(d, "RUN_ID r-test\n"),
             good=lambda d: _state(d),
             want="VOID", good_want="READ"),
        Case("a file with no block at all is VOID", _probe_void,
             bad=lambda d: _no_block(d),
             good=lambda d: _state(d),
             want="VOID", good_want="READ"),
        Case("a missing field is VOID, not a default", _probe_void,
             bad=lambda d: _bad_block(d, "RUN_ID: r\nN: 1\nK: 0\nSTATUS: RUNNING\n"),
             good=lambda d: _state(d),
             want="VOID", good_want="READ"),
        # EFFORT IS OPTIONAL, AND THE PAIR IS WHAT PROVES IT: a block missing a REQUIRED field
        # is still VOID, and one missing only EFFORT - every state file armed before v3 - reads.
        Case("a missing OPTIONAL field still reads", _probe_void,
             bad=lambda d: _bad_block(d, _ALL_BUT("BRANCH")),
             good=lambda d: _bad_block(d, _ALL_BUT("EFFORT")),
             want="VOID", good_want="READ"),
        # THE EFFORT, v3. Each refusal is paired with the nearest arm that must go through.
        Case("an arm with NO effort stated is refused", _probe_arm,
             bad=lambda d: (_state(d), None, None, 6),
             good=lambda d: (_state(d), None, "xhigh", 6),
             want="REFUSED", good_want="ARMED xhigh"),
        Case("...and an explicit --effort alone arms", _probe_arm,
             bad=lambda d: (_state(d), "", "", 6),
             good=lambda d: (_state(d), "high", None, 6),
             want="REFUSED", good_want="ARMED high"),
        Case("an arm whose two sources DISAGREE is refused", _probe_arm,
             bad=lambda d: (_state(d), "medium", "xhigh", 6),
             good=lambda d: (_state(d), "xhigh", "XHIGH", 6),
             want="REFUSED", good_want="ARMED xhigh"),
        Case("a level the CLI does not list is refused", _probe_arm,
             bad=lambda d: (_state(d), "xhig", None, 6),
             good=lambda d: (_state(d), "max", None, 6),
             want="REFUSED", good_want="ARMED max"),
        # THE RUNNER BESIDE THE COUNTER IS UNTRACKED BY check_checkers, so a stale one is
        # reported here or nowhere - and a v5 runner silently ignores the field.
        Case("a STALE runner beside the counter refuses", _probe_arm,
             bad=lambda d: (_state(d), "xhigh", None, 5),
             good=lambda d: (_state(d), "xhigh", None, None),
             want="REFUSED", good_want="ARMED xhigh"),
    ]
    ok_cases, paired, unpaired = run_cases(cases, tmp)
    ok &= ok_cases

    # ---- the three assertions a case table cannot make, because they are about the ARTEFACT
    print()

    # 1. THE COUNTER ADVANCES, AND IT IS THE POINT OF THE WHOLE SCRIPT. Exit code 0 would be
    #    returned by a claim that wrote nothing at all.
    (tmp / "adv").mkdir(exist_ok=True)
    f = _state(tmp / "adv", n=3, k=0)
    got = claim(f)
    k_after = read_state(f)[0]["K"]
    good = got == "CLAIMED" and k_after == "1"
    ok &= good
    print(f"  {'OK  ' if good else 'MISS'} K advances 0 -> 1 on a claim   -> K = {k_after}")

    # 2. THREE HOPS IN A ROW GET THREE DIFFERENT NUMBERS. This is the defect the script was
    #    built for: four hops all reading K = 1 is what the first real run produced.
    seen = []
    for _ in range(3):
        fields, raw, term = read_state(f)
        act_release(fields)
        write_state(f, fields, raw, term)
        fields, raw, term = read_state(f)
        rc, _l, dirty = act_claim(fields)
        if dirty:
            write_state(f, fields, raw, term)
        seen.append(read_state(f)[0]["K"] if rc == RC_OK else f"refused@{fields['K']}")
    good = seen == ["2", "3", "refused@3"]
    ok &= good
    print(f"  {'OK  ' if good else 'MISS'} consecutive hops differ        -> {seen}")

    # 2b. THE DEFECT ITSELF, REPRODUCED, because a fix nobody has seen fail is a fix nobody
    #     has seen. This is what the field did before --claim existed: three hops READ the
    #     counter and all three got the same number. Written as an assertion rather than a
    #     comment so it fails if the shape ever comes back.
    (tmp / "old").mkdir(exist_ok=True)
    f3 = _state(tmp / "old", n=3, k=1)
    old = [read_state(f3)[0]["K"] for _ in range(3)]
    good = old == ["1", "1", "1"] and old != seen
    ok &= good
    print(f"  {'OK  ' if good else 'MISS'} the OLD shape, reproduced      -> {old}"
          f"  (reading, not claiming: every hop is hop 1)")

    # 3. THE PROSE AROUND THE BLOCK IS NOT TOUCHED. A writer that rewrites the file instead
    #    of the block destroys the bounded-authority list, and nothing would report it.
    (tmp / "pres").mkdir(exist_ok=True)
    f2 = _state(tmp / "pres")
    before = f2.read_bytes()
    claim(f2)
    after = f2.read_bytes()
    kept = (b"prose above the block, which must survive untouched" in after
            and b"prose below the block, which must also survive untouched" in after)
    lf_only = b"\r\n" not in after and b"\r\n" not in before
    good = kept and lf_only and before != after
    ok &= good
    print(f"  {'OK  ' if good else 'MISS'} prose kept, LF kept, block changed"
          f" -> prose {'kept' if kept else 'LOST'}, "
          f"{'LF' if lf_only else 'CRLF INTRODUCED'}, "
          f"{len(before)} -> {len(after)} bytes")

    # 4. THE ARM WRITES THE EFFORT INTO THE BLOCK, AND A CLAIM KEEPS IT. A field an arm prints
    #    and never writes is a field the runner reads as absent - and refuses on, correctly,
    #    for the wrong reason.
    (tmp / "eff").mkdir(exist_ok=True)
    f4 = _state(tmp / "eff")
    fields, raw, term = read_state(f4)
    act_arm(fields, "r-eff", 2, "session/e", None, "xhigh", None)
    write_state(f4, fields, raw, term)
    claim(f4)
    kept = read_state(f4)[0].get("EFFORT")
    good = kept == "xhigh" and b"EFFORT:     xhigh" in f4.read_bytes()
    ok &= good
    print(f"  {'OK  ' if good else 'MISS'} the arm writes EFFORT, a claim keeps it -> {kept!r}")

    # 4b. main() READS CLAUDE_EFFORT, the wiring the cases above bypass by calling act_arm
    #     directly: armed from the variable when it is set, refused when it is not.
    import contextlib                                               # noqa: PLC0415
    import io                                                       # noqa: PLC0415

    from house_common import isolated_env                           # noqa: PLC0415
    seen4 = []
    for env in ("high", None):
        (tmp / f"main-{env}").mkdir(exist_ok=True)
        f6 = _state(tmp / f"main-{env}")
        with isolated_env("CLAUDE_EFFORT"), contextlib.redirect_stdout(io.StringIO()):
            if env:
                os.environ["CLAUDE_EFFORT"] = env
            rc6 = main(["--file", str(f6), "--arm", "--run-id", "r", "--hops", "1",
                        "--branch", "session/m"])
        seen4.append(read_state(f6)[0].get("EFFORT") if rc6 == RC_OK else "REFUSED")
    good = seen4 == ["high", "REFUSED"]
    ok &= good
    print(f"  {'OK  ' if good else 'MISS'} main() arms from CLAUDE_EFFORT, else refuses -> {seen4}")

    # 5. ...AND AN OLD FILE STAYS OLD. A claim on a state file armed before v3 changes the
    #    fields a claim changes and adds nothing, so its diff is exactly what v2's was.
    (tmp / "oldfile").mkdir(exist_ok=True)
    f5 = _state(tmp / "oldfile")
    claim(f5)
    good = b"EFFORT" not in f5.read_bytes() and read_state(f5)[0]["K"] == "1"
    ok &= good
    print(f"  {'OK  ' if good else 'MISS'} a pre-v3 file is claimed and gains no field"
          f" -> {'no EFFORT line' if b'EFFORT' not in f5.read_bytes() else 'EFFORT ADDED'}")

    print()
    report_pairing(paired, unpaired)
    shutil.rmtree(tmp, ignore_errors=True)
    print("\nSELFTEST: " + ("PASS" if ok else "FAIL"))
    return RC_OK if ok else 1


def _bad_block(d: Path, body: str) -> Path:
    f = d / STATE_NAME
    f.write_bytes(("prose\n\n```auto-mode\n" + body + "```\n\nprose\n").encode("utf-8"))
    return f


def _no_block(d: Path) -> Path:
    f = d / STATE_NAME
    f.write_bytes(b"# no fenced block anywhere in this file\n")
    return f


def _ALL_BUT(name: str) -> str:
    """A block body carrying every field, required and optional, except one."""
    vals = {"RUN_ID": "r", "N": "1", "K": "0", "STATUS": RUNNING, "BRANCH": "session/x",
            "HOP_ACTIVE": "no", "WOKE": "-", "EFFORT": "xhigh"}
    return "".join(f"{k}: {v}\n" for k, v in vals.items() if k != name)


def _probe_arm(args) -> str:
    """--arm driven through the real action: (state file, --effort, CLAUDE_EFFORT, runner
    version). Reads the EFFORT back off the FILE, never off the returned fields."""
    f, effort, env, runner = args
    fields, raw, term = read_state(f)
    rc, _lines, dirty = act_arm(fields, "r-test", 2, "session/x", effort, env, runner)
    if dirty:
        write_state(f, fields, raw, term)
    if rc == RC_REFUSED:
        return "REFUSED"
    return f"ARMED {read_state(f)[0].get('EFFORT')}"


def _probe_block(f: Path) -> str:
    """--blocked, driven through the real action. Also asserts it RELEASES THE LOCK: a hop
    that blocks and leaves HOP_ACTIVE at 'yes' is indistinguishable from one that died."""
    fields, raw, term = read_state(f)
    fields["HOP_ACTIVE"] = "yes"
    rc, _lines, dirty = act_blocked(fields)
    if dirty:
        write_state(f, fields, raw, term)
    if rc == RC_REFUSED:
        return "REFUSED"
    after = read_state(f)[0]
    return ("BLOCKED" if after["STATUS"] == BLOCKED and after["HOP_ACTIVE"] == "no"
            else f"lock left {after['HOP_ACTIVE']!r}")


def _probe_void(f: Path) -> str:
    try:
        read_state(f)
    except Void:
        return "VOID"
    return "READ"


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
