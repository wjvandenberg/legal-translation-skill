#!/usr/bin/env python3
"""purpose_guard.py - refuse a session's edits until it has written down what it is FOR.

CHECKER VERSION 2 (2026-09-22)

If a project's copy says a lower version than this one, it is stale - see the "Checkers"
line for each version in ...\\Coding\\templates\\TEMPLATE-CHANGELOG.md and re-copy.

WHAT THIS IS. A Claude Code PreToolUse hook on Write / Edit / NotebookEdit. It reads one
tool call on stdin and either says nothing (exit 0, the call proceeds) or REFUSES it
(exit 2, and the reason goes to the model on stderr). Wire it up with install_hooks.py.

WHY IT EXISTS, AND IT IS THE THIRD HALF OF A RULE THAT HAD ONLY TWO. The house rule
(Opening, rule 4) is: say what you are about to do, HOW, and WHICH PURPOSE it serves.
On 2026-09-11 a session skipped it, and NOTHING COULD HAVE REPORTED THAT, because the
rule said only "say" - it left no artefact. Its own pair, the closing ritual, had been
given section 7 for exactly this reason, with the argument written down beside it: a
report that exists only in chat dies with the transcript. The opening ritual was given
nothing, so it was a rule built unable to fail loudly, and it duly failed silently.

Three things were wrong and this hook answers the third:
  1 THE TRIGGER LISTS HAD DRIFTED - the status board fired at four triggers and the
    purpose statement at one, so a mid-session instruction produced a board with no
    purpose beside it, BOTH RULES OBEYED AS WRITTEN. Fixed in prose; the lists now
    declare each other.
  2 THE ANCHOR WAS A NEGATIVE CONDITION - "before the first edit" is detectable only
    once crossed. Fixed in prose: immediately after the rollback tag, nothing between.
  3 THERE WAS NO ARTEFACT. That is this file. Prose enforced by the very thing it binds
    is not enforcement, which is route 1's own wording.

WHAT IT LOOKS FOR. One line in the LIVE plan file - PLAN-*.md in the repository root, the
house naming convention - carrying the marker SESSION PURPOSE and TODAY's date. Content
beyond that is not judged: whether a purpose is any GOOD is a judgement no script can
make, and pretending otherwise is how a gate becomes a form to be filled in.

THE BOOTSTRAP, AND IT IS THE ONE HOLE THAT HAD TO BE CUT ON PURPOSE. The purpose line is
itself written with Edit or Write. A guard refusing every edit until the line exists would
deadlock the session that is trying to comply. SO A WRITE TO THE PLAN FILE ITSELF IS
ALWAYS ALLOWED - narrowly, by exact path, and never by a name the caller supplies. It is
declared here rather than discovered later, because an undocumented hole is indistinguish-
able from a bug.

FAILURE DIRECTION, DECLARED, AND IT IS THE SAME AS auto_mode_guard's FOR THE SAME REASON.
  no live plan file            -> ALLOW, silently. Most projects have none, and a guard
                                  that bricks them is a guard somebody uninstalls.
  a plan file that will not
  read                         -> exit 1: LOUD and NON-BLOCKING. The message reaches the
                                  transcript and the call proceeds.
  purpose line present         -> ALLOW, silently, for the rest of the session.
  purpose line absent          -> REFUSE with the exact line to write.

WHAT IT DOES NOT CATCH, SAID PLAINLY. A file written through Bash, through an interpreter,
or by any tool other than the three matched here. This gate raises the cost of skipping
the ritual; it does not make it impossible, and a session determined to route around it
can. That is a boundary, not a defect - but an unstated boundary is a silent one.

    uv run python tools/purpose_guard.py --selftest   # both arms proved
    uv run python tools/purpose_guard.py --probe      # report this project's state, exit 0
    echo '{"tool_name":"Edit","tool_input":{"file_path":"x.py"}}' \\
        | uv run python tools/purpose_guard.py        # ask it as the hook does

EXIT CODES - THE HOOK CONTRACT, NOT THIS HOUSE'S USUAL ONE.
  0 = allow.  2 = REFUSE, stderr goes to the model.  1 = could not decide; not blocking.
"""
from __future__ import annotations

import datetime as _dt
import json
import os
import sys
import tempfile
from pathlib import Path

MARKER = "SESSION PURPOSE"
WATCHED_TOOLS = {"Write", "Edit", "NotebookEdit", "MultiEdit"}
PLAN_GLOB = "PLAN-*.md"

ALLOW, REFUSE, UNDECIDED = 0, 2, 1


def today() -> str:
    """From the CLOCK, never inferred from a file's modification time - house rule: a
    date read off an artefact put thirteen stamps into a document nine days early."""
    return _dt.date.today().isoformat()


def live_plans(root: Path) -> list[Path]:
    """The LIVE plan files: PLAN-*.md in the ROOT only.

    archive/ is deliberately not searched - a closed plan file is finished, and finding a
    purpose line in one would let last month's work discharge this session's rule.
    """
    try:
        return sorted(p for p in root.glob(PLAN_GLOB) if p.is_file())
    except OSError:
        return []


def purpose_recorded(root: Path, when: str | None = None) -> tuple[bool, str | None]:
    """(is it there, error). A read that FAILS is an error, never a quiet False - a scan
    whose denominator can shrink in silence is not a scan."""
    when = when or today()
    plans = live_plans(root)
    if not plans:
        return False, None                      # no plan file: caller allows
    for p in plans:
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except OSError as e:
            return False, f"could not read {p.name}: {e}"
        for line in text.splitlines():
            if MARKER in line and when in line:
                return True, None
    return False, None


def target_of(payload: dict) -> Path | None:
    ti = payload.get("tool_input") or {}
    for key in ("file_path", "notebook_path", "path"):
        v = ti.get(key)
        if isinstance(v, str) and v:
            try:
                return Path(v)
            except (ValueError, OSError):
                return None
    return None


def is_plan_file(target: Path | None, root: Path) -> bool:
    """THE DECLARED BOOTSTRAP HOLE. True only for a path that IS one of the live plan
    files, resolved and compared as a path - never by matching the caller's string, which
    a caller controls."""
    if target is None:
        return False
    try:
        resolved = (root / target).resolve() if not target.is_absolute() else target.resolve()
    except (OSError, RuntimeError):
        return False
    return any(resolved == p.resolve() for p in live_plans(root))


STATE_REL = ("temp", "purpose_guard_state.json")


def purpose_fingerprint(root: Path, when: str) -> str:
    """A hash of TODAY's purpose line(s), so a second session on the same day can be told
    from the first. Empty string when there is none to hash."""
    import hashlib
    found = []
    for pf in live_plans(root):
        try:
            text = pf.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        found += [ln.strip() for ln in text.splitlines() if MARKER in ln and when in ln]
    if not found:
        return ""
    return hashlib.sha256("\n".join(sorted(found)).encode("utf-8")).hexdigest()


def _state_path(root: Path) -> Path:
    return root.joinpath(*STATE_REL)


def read_state(root: Path) -> dict:
    try:
        return json.loads(_state_path(root).read_text(encoding="utf-8-sig"))
    except Exception:
        return {}


def write_state(root: Path, session: str, fingerprint: str) -> None:
    """Best effort. A guard that cannot write its own note must still allow the call -
    a script that fails to start exits like a refusal and blocks every tool."""
    try:
        sp = _state_path(root)
        sp.parent.mkdir(parents=True, exist_ok=True)
        sp.write_text(json.dumps({"session": session, "purpose": fingerprint}),
                      encoding="utf-8", newline="")
    except OSError:
        pass


def inherited_purpose(root: Path, session: str, when: str) -> bool:
    """TRUE when the purpose line present is the one a DIFFERENT session left behind.

    GAP 87. v1 asked only for the MARKER and TODAY's date, so on any day carrying more
    than one session every session after the first inherited the previous one's line and
    the hook read as satisfied - measured on the fourth session of a single day, whose
    first write landed before it had stated a purpose at all. A control that fires on the
    first session of a day and sleeps for the rest of it is a control whose coverage
    nobody has measured.

    DEGRADES TO v1 BEHAVIOUR WHEN THERE IS NO SESSION ID, AND SAYS SO RATHER THAN
    GUESSING: without one the two sessions are genuinely indistinguishable from in here,
    and refusing every call would brick a harness that does not send it.
    """
    if not session:
        return False
    fp = purpose_fingerprint(root, when)
    if not fp:
        return False
    st = read_state(root)
    return bool(st.get("session")) and st["session"] != session and st.get("purpose") == fp


def decide(payload: dict, root: Path, when: str | None = None) -> tuple[int, str]:
    # DEFAULTED HERE AS WELL AS IN purpose_recorded, and the omission is why: v1's first
    # BITE TEST against a real repository printed "SESSION PURPOSE None" as the line to
    # write. purpose_recorded defaulted its own copy, so the DECISION was right and only
    # the instruction was wrong - a refusal telling the reader to write a line that would
    # never satisfy it. The selftest missed it by asserting the MARKER was in the message
    # and never the date, which is the assertion that now exists.
    when = when or today()
    tool = payload.get("tool_name") or ""
    if tool not in WATCHED_TOOLS:
        return ALLOW, ""
    target = target_of(payload)
    if is_plan_file(target, root):
        return ALLOW, ""                        # writing the purpose line itself
    ok, err = purpose_recorded(root, when)
    if err:
        return UNDECIDED, f"purpose_guard could not read the plan file: {err}"
    session = str(payload.get("session_id") or "")
    if ok and not inherited_purpose(root, session, when):
        write_state(root, session, purpose_fingerprint(root, when))
        return ALLOW, ""
    if ok:
        # The line is there and dated today, and it belongs to an EARLIER session.
        plan0 = live_plans(root)[0].name
        return REFUSE, (
            f"REFUSED: the {MARKER} line in {plan0} was written by a DIFFERENT session "
            f"earlier today, so it does not say what THIS session is for.\n"
            f"A date cannot tell two sessions of one day apart - that is gap 87, and it "
            f"is why this guard keys on the session and not the calendar.\n"
            f"REPLACE the line (do not append one) before editing anything else:\n"
            f"  **{MARKER} {when}** - WHAT: <what you are about to do> - HOW: <how> - "
            f"PURPOSE: <which purpose it serves>\n"
            f"Writing {plan0} is always allowed."
        )
    if not live_plans(root):
        return ALLOW, ""                        # no live plan file: inert by design
    plan = live_plans(root)[0].name
    return REFUSE, (
        f"REFUSED: this session has not recorded what it is FOR.\n"
        f"The house rule (Opening, rule 4) says the purpose statement lands IMMEDIATELY "
        f"after the rollback tag, nothing in between - and leaves a line behind, because "
        f"a rule with no artefact cannot be reported missing.\n"
        f"Add one line to {plan} before editing anything else:\n"
        f"  **{MARKER} {when}** - WHAT: <what you are about to do> - HOW: <how> - "
        f"PURPOSE: <which purpose it serves>\n"
        f"Then say the same thing in the conversation. Writing {plan} is always allowed."
    )


def read_payload() -> dict:
    raw = sys.stdin.read()
    if not raw.strip():
        return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {}


def main(argv) -> int:
    if "--selftest" in argv:
        return selftest()
    root = Path(os.environ.get("CLAUDE_PROJECT_DIR") or Path.cwd())
    if "--probe" in argv:
        # REPORTS, NEVER GATES, AND NEVER READS STDIN. This is the entry point run_tests
        # exercises, and an entry point that blocked on stdin would HANG the suite rather
        # than fail it - the worst failure shape there is, because a hung run and a slow
        # one look identical from outside. It always exits 0: the entry-point arm asserts
        # the checker STARTED and deliberately ignores what it found.
        plans = live_plans(root)
        if not plans:
            print(f"purpose_guard: no live {PLAN_GLOB} in {root} - INERT here")
            return 0
        ok, err = purpose_recorded(root)
        names = ", ".join(p.name for p in plans)
        if err:
            print(f"purpose_guard: {err}")
        print(f"purpose_guard: live plan file(s) {names}; purpose for {today()} "
              f"{'RECORDED - edits allowed' if ok else 'NOT recorded - edits would be REFUSED'}")
        return 0
    code, msg = decide(read_payload(), root)
    if msg:
        print(msg, file=sys.stderr)
    return code


# --------------------------------------------------------------------- selftest
def selftest() -> int:
    """EVERY REFUSAL PROVED BOTH WAYS. A guard proved only to refuse has not been shown
    to stay quiet, and one proved only to stay quiet has not been shown to bite."""
    cases, ok = [], True
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        edit = {"tool_name": "Edit", "tool_input": {"file_path": "src/thing.py"}}

        # 1. NO PLAN FILE -> inert. Most projects have none.
        cases.append(("no live plan file -> ALLOW", decide(edit, root)[0] == ALLOW))

        plan = root / "PLAN-5-propagation.md"
        plan.write_bytes(b"# PLAN\n\n| status | open |\n")

        # 2. A plan file with NO purpose line -> REFUSE, and the reason names the file.
        code, msg = decide(edit, root)
        cases.append(("plan file, no purpose line -> REFUSE", code == REFUSE))
        cases.append(("...and the refusal names the plan file",
                      "PLAN-5-propagation.md" in msg))
        cases.append(("...and it quotes the exact line to write", MARKER in msg))
        # THE ASSERTION THAT WOULD HAVE CAUGHT v1's BITE-TEST BUG. Asserting the MARKER is
        # present passes on "SESSION PURPOSE None" - a refusal instructing the reader to
        # write a line that can never satisfy it. Assert the LINE IS USABLE, not that it
        # merely mentions the marker.
        cases.append(("...with TODAY's date in it, not None", today() in msg))
        cases.append(("...and no literal None anywhere in the refusal", "None" not in msg))

        # 3. THE BOOTSTRAP: writing the plan file itself is allowed even while refusing.
        to_plan = {"tool_name": "Edit",
                   "tool_input": {"file_path": str(plan)}}
        cases.append(("writing the plan file itself -> ALLOW",
                      decide(to_plan, root)[0] == ALLOW))
        rel_plan = {"tool_name": "Edit",
                    "tool_input": {"file_path": "PLAN-5-propagation.md"}}
        cases.append(("...by RELATIVE path too", decide(rel_plan, root)[0] == ALLOW))

        # 4. Purpose line present -> quiet.
        plan.write_bytes(
            f"# PLAN\n\n**{MARKER} {today()}** - WHAT: x - HOW: y - PURPOSE: z\n"
            .encode("utf-8"))
        cases.append(("purpose line for TODAY -> ALLOW", decide(edit, root)[0] == ALLOW))

        # 5. YESTERDAY'S line does not discharge today. This is the arm that matters:
        #    a stale purpose is exactly what a plan file accumulates.
        stale = (_dt.date.today() - _dt.timedelta(days=1)).isoformat()
        plan.write_bytes(
            f"# PLAN\n\n**{MARKER} {stale}** - WHAT: x - HOW: y - PURPOSE: z\n"
            .encode("utf-8"))
        cases.append(("YESTERDAY's purpose line -> REFUSE", decide(edit, root)[0] == REFUSE))

        # 5b. GAP 87 - THE SAME DAY, A DIFFERENT SESSION. v1 asked only for the MARKER
        #     and TODAY's date, so every session after the first on any given day
        #     inherited the previous one's line and the hook read as satisfied. These
        #     four cases are the whole of the fix: the middle one is RED against v1.
        (root / "temp").mkdir(exist_ok=True)
        line_a = f"# PLAN\n\n**{MARKER} {today()}** - WHAT: a - HOW: y - PURPOSE: z\n"
        plan.write_bytes(line_a.encode("utf-8"))
        s1 = dict(edit, session_id="session-one")
        cases.append(("session 1 writes its own purpose -> ALLOW",
                      decide(s1, root)[0] == ALLOW))
        s2 = dict(edit, session_id="session-two")
        code2, msg2 = decide(s2, root)
        cases.append(("GAP 87: session 2, SAME day, INHERITED line -> REFUSE",
                      code2 == REFUSE))
        cases.append(("...and the refusal says to REPLACE, not to append",
                      "REPLACE" in msg2))
        plan.write_bytes(
            f"# PLAN\n\n**{MARKER} {today()}** - WHAT: b - HOW: y - PURPOSE: z\n"
            .encode("utf-8"))
        cases.append(("...session 2 writes its OWN line -> ALLOW",
                      decide(s2, root)[0] == ALLOW))
        # DEGRADATION IS DECLARED, NOT ASSUMED: with no session id the two are genuinely
        # indistinguishable from in here, so the guard falls back to v1 rather than
        # refusing every call and bricking a harness that does not send one.
        plan.write_bytes(line_a.encode("utf-8"))
        cases.append(("no session_id -> v1 behaviour, ALLOW",
                      decide(edit, root)[0] == ALLOW))
        try:
            (root / "temp" / "purpose_guard_state.json").unlink()
        except OSError:
            pass
        plan.write_bytes(
            f"# PLAN\n\n**{MARKER} {today()}** - WHAT: x - HOW: y - PURPOSE: z\n"
            .encode("utf-8"))

        # 6. An unwatched tool is never judged.
        cases.append(("Bash is not watched -> ALLOW",
                      decide({"tool_name": "Bash",
                              "tool_input": {"command": "ls"}}, root)[0] == ALLOW))
        cases.append(("Read is not watched -> ALLOW",
                      decide({"tool_name": "Read",
                              "tool_input": {"file_path": "x"}}, root)[0] == ALLOW))

        # 7. An ARCHIVED plan file must not discharge the rule.
        (root / "archive").mkdir()
        (root / "archive" / "PLAN-1-old.md").write_bytes(
            f"**{MARKER} {today()}**\n".encode("utf-8"))
        plan.write_bytes(b"# PLAN\n\nno purpose here\n")
        cases.append(("a purpose line in archive/ -> still REFUSE",
                      decide(edit, root)[0] == REFUSE))

        # 8. Malformed stdin is not a pass and not a brick.
        cases.append(("empty payload -> ALLOW (no tool named)",
                      decide({}, root)[0] == ALLOW))

    print("purpose_guard selftest")
    for name, good in cases:
        ok &= good
        print(f"  {'OK  ' if good else 'MISS'} {name}")
    print(f"\n  {len(cases)} cases, {sum(1 for _, g in cases if g)} passed")
    print("SELFTEST: " + ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
