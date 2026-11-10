#!/usr/bin/env python3
"""board_guard.py - refuse a nested session's tools until it has printed its brief's status board.

CHECKER VERSION 2 (2026-11-05)

If a project's copy says a lower version than this one, it is stale - see the "Checkers"
line for each version in ...\\Coding\\templates\\TEMPLATE-CHANGELOG.md and re-copy.

v2 (2026-11-05, the same day) - THE TRANSCRIPT LAGS THE SCREEN. v1's first live run refused a session that had
printed its board FIRST: the board's row was stamped 1.3 s before the call and was not yet on disk when the hook
read it, though it was 2 s later. A MISSING board is now re-read for up to GRACE_SECONDS before a refusal, and
FIRST is judged by the file's own order - the board's text ahead of every tool call - never by "never refused",
which logged that session LATE. A refusal now costs up to three seconds; an allow costs nothing more.

WHAT THIS IS. A Claude Code PreToolUse hook. It reads one tool call on stdin and either says
nothing (exit 0, the call proceeds) or REFUSES it (exit 2, and the reason goes to the model on
stderr). Wire it up with install_hooks.py, which also fires a real call at it to prove it bites.

WHY IT EXISTS. The house rule says a session another session started prints its brief's
opening block - the board, purpose and next step - as its FIRST text, before any tool call, and
as its LAST. Prose alone did not hold it: nested sessions stopped showing the board, and only a
board placed first or last reached the person's screen (2 tries of 2; the three placements in
between, 0 of 3). The brief supplies the board; this hook makes dropping it impossible to do
silently.

ITS SCOPE, DECIDED BY ITSELF. Only a session whose FIRST user message carries a board TABLE - a
markdown table whose header row names "#" and "phase". A session a person typed carries none, so
it is never checked. Measured before building: 2 of 7 briefs carried the board with no dash
lines around it, so the TABLE is the key, not the dashes - a dash-keyed hook would have left
those sessions unchecked and said nothing.

WHAT ALLOWS. A TEXT block of the session's own, written before this call, holding every row of
the brief's table - whitespace collapsed, separator rows ignored. Logged FIRST when that text
came before the session's first tool call, LATE otherwise: a board printed mid-turn reaches no
screen, so a late one is recorded rather than hidden.

FAILURE DIRECTION, DECLARED.
  no board in the brief        -> ALLOW, the verdict NONE remembered for the session.
  the board printed            -> ALLOW, logged FIRST or LATE, remembered.
  not printed                  -> REFUSE, exit 2, with the instruction.
  refused twice already        -> ALLOW, logged ESCAPED. Chat text is sometimes stored only as a
                                  reworded THINKING block (measured: 6 of 15 texts in one
                                  session), which this hook cannot read - without the escape
                                  such a session would be refused for ever.
  no transcript, unreadable,
  malformed, any exception     -> ALLOW, logged FAIL-OPEN. A broken board check must never stop
                                  every session in every project.

WHERE THE TRANSCRIPT IS. The payload's transcript_path when it names a file; else the session
id's own file, <session_id>.jsonl, under ~/.claude/projects/. The first call of each session
logs the payload's KEY NAMES - never a value - so whether transcript_path is sent is measured by
the first real run rather than assumed.

ITS TOOLS. install_hooks.py wires it to the AUTO MODE guard's matcher - Bash, PowerShell, the
scheduling tools and every mcp__ tool. 7 of 7 sessions briefed with a board made their first
call with one of those; and Read, Edit and Write stay unhooked, so a hook that cannot START -
Python's exit 2 IS the block code - can always be removed through them. A hook call costs about
a second on the machine this was built on, and Claude Code runs matching hooks side by side, so
where the AUTO MODE guard is already wired this adds no wait.

WHAT IT DOES NOT CATCH, SAID PLAINLY. The close: the house rule chose the opening, and a board
in the last text is asked for by the refusal and by the rule, never checked here. A session
whose calls are all to unhooked tools is checked only at its first hooked call.

STATE AND LOG. temp/board_guard_state.json remembers each session's verdict, so a decided
session costs one small read per call and never re-reads its transcript; temp/board_guard.log
gets one line per verdict - time, the session id's first 8 characters, the event. Neither ever
holds a line of a transcript.

    uv run python tools/board_guard.py --selftest   # every arm proved both ways
    uv run python tools/board_guard.py --probe      # report this project's state, exit 0

EXIT CODES - THE HOOK CONTRACT. 0 = allow. 2 = REFUSE, stderr goes to the model. Nothing else:
an error ALLOWS, logged, rather than exiting 1.
"""
from __future__ import annotations

import datetime as _dt
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ALLOW, REFUSE = 0, 2
MAX_REFUSALS = 2
#: v2: how long a MISSING board is re-read before a refusal, and how often. Measured on v1's first live run: a
#: board row stamped 1.3 s before the call was not yet on disk when the hook read, and was 2 s later.
GRACE_SECONDS = 3.0
POLL_SECONDS = 0.25
HEADER_CELLS = ("#", "phase")
STATE_REL = ("temp", "board_guard_state.json")
LOG_REL = ("temp", "board_guard.log")
DECIDED = {"NONE", "FIRST", "LATE", "ESCAPED"}
KEEP_SESSIONS = 500
SESSION_ID = re.compile(r"[0-9A-Za-z-]{8,80}")


def _now() -> str:
    return _dt.datetime.now().isoformat(timespec="seconds")


def _norm(line: str) -> str:
    return " ".join(line.split())


def _cells(row: str) -> list[str]:
    return [c.strip().lower() for c in row.strip().strip("|").split("|")]


def _is_separator(row: str) -> bool:
    cells = [c.strip() for c in row.strip().strip("|").split("|")]
    return bool(cells) and all(c and set(c) <= set("-: ") for c in cells)


def board_rows(text: str) -> list[str]:
    """The rows of the FIRST board table in `text` - normalised, separator rows dropped - or []."""
    lines = text.splitlines()
    for i, line in enumerate(lines):
        s = line.strip()
        if s.startswith("|") and all(h in _cells(s) for h in HEADER_CELLS):
            rows = []
            for row in lines[i:]:
                r = row.strip()
                if not r.startswith("|"):
                    break
                if not _is_separator(r):
                    rows.append(_norm(r))
            return rows
    return []


def _blocks(row: dict) -> list[dict]:
    content = (row.get("message") or {}).get("content")
    if isinstance(content, str):
        return [{"type": "text", "text": content}]
    return [b for b in (content or []) if isinstance(b, dict)]


def read_rows(path: Path) -> list[dict]:
    """Every JSON row; a malformed line is skipped - the file is appended to while it is read."""
    rows = []
    with open(path, "rb") as fh:
        for raw in fh:
            try:
                o = json.loads(raw.decode("utf-8", errors="replace"))
            except ValueError:
                continue
            if isinstance(o, dict):
                rows.append(o)
    return rows


def judge(rows: list[dict]) -> tuple[str, bool]:
    """(kind, first). kind: NOBRIEF - no user text yet · NONE - the brief holds no board ·
    PRINTED - a text block of the session's own holds every row · MISSING - none does.
    `first` is True when the printing text came before the session's first tool call."""
    start = None
    brief = ""
    for k, o in enumerate(rows):
        if o.get("type") == "user" and not o.get("isMeta"):
            texts = [b.get("text") or "" for b in _blocks(o) if b.get("type") == "text"]
            if any(t.strip() for t in texts):
                start, brief = k, "\n".join(texts)
                break
    if start is None:
        return "NOBRIEF", False
    want = set(board_rows(brief))
    if not want:
        return "NONE", False
    tool_seen = False
    for o in rows[start + 1:]:
        if o.get("type") != "assistant":
            continue
        for b in _blocks(o):
            kind = b.get("type")
            if kind == "tool_use":
                tool_seen = True
            elif kind == "text":
                have = {_norm(x) for x in (b.get("text") or "").splitlines()}
                if want <= have:
                    return "PRINTED", not tool_seen
    return "MISSING", False


def transcript_of(payload: dict, home: Path | None = None) -> Path | None:
    tp = payload.get("transcript_path")
    if isinstance(tp, str) and tp:
        p = Path(tp).expanduser()
        if p.is_file():
            return p
    sid = payload.get("session_id")
    if isinstance(sid, str) and SESSION_ID.fullmatch(sid):
        base = (home or Path.home()) / ".claude" / "projects"
        try:
            for d in base.iterdir():
                p = d / f"{sid}.jsonl"
                if p.is_file():
                    return p
        except OSError:
            return None
    return None


def project_root(payload: dict) -> Path:
    env = os.environ.get("CLAUDE_PROJECT_DIR")
    if env:
        return Path(env)
    cwd = payload.get("cwd")
    return Path(cwd) if isinstance(cwd, str) and cwd else Path.cwd()


def read_state(root: Path) -> dict:
    try:
        st = json.loads(root.joinpath(*STATE_REL).read_text(encoding="utf-8-sig"))
        return st if isinstance(st, dict) and isinstance(st.get("sessions"), dict) else {"sessions": {}}
    except Exception:
        return {"sessions": {}}


def write_state(root: Path, state: dict) -> None:
    """Best effort, never raising: a guard that cannot write its note must still decide."""
    try:
        sessions = state.get("sessions", {})
        if len(sessions) > KEEP_SESSIONS:
            keep = sorted(sessions.items(), key=lambda kv: kv[1].get("at", ""))[-KEEP_SESSIONS:]
            state["sessions"] = dict(keep)
        sp = root.joinpath(*STATE_REL)
        sp.parent.mkdir(parents=True, exist_ok=True)
        sp.write_bytes(json.dumps(state, indent=1).encode("utf-8"))
    except Exception:
        pass


def log(root: Path, key: str, event: str, detail: str = "") -> None:
    try:
        lp = root.joinpath(*LOG_REL)
        lp.parent.mkdir(parents=True, exist_ok=True)
        with open(lp, "ab") as fh:
            fh.write(f"{_now()}\t{key[:8]}\t{event}\t{detail}\n".encode("utf-8"))
    except Exception:
        pass


def refusal(n: int) -> str:
    return (
        f"REFUSED by board_guard.py: your first message carries a status board, and no chat text "
        f"of yours has printed it yet.\n"
        f"Print your brief's opening block as chat text NOW - every row of the board verbatim, then "
        f"the purpose and next step - and then retry this call.\n"
        f"Print it again as your LAST text: a board shown mid-turn does not reach the person's "
        f"screen, so the first and the last are the two that count.\n"
        f"Refusal {n} of {MAX_REFUSALS}: after that this hook lets the session go on, and logs it."
    )


def decide(payload: dict, root: Path, home: Path | None = None) -> tuple[int, str]:
    """(exit code, message). Every path that cannot judge ALLOWS and says so in the log."""
    path = transcript_of(payload, home)
    key = str(payload.get("session_id") or "") or (str(path) if path else "")
    state = read_state(root)
    sessions = state["sessions"]
    entry = sessions.get(key) if key else None
    if entry and entry.get("verdict") in DECIDED:
        return ALLOW, ""                         # decided: the transcript is never re-read
    if entry is None:
        entry = {"refusals": 0}
        log(root, key, "SEEN", "keys " + ",".join(sorted(str(k) for k in payload)))
    entry["at"] = _now()
    if path is None:
        log(root, key, "FAIL-OPEN", "no transcript found")
        return ALLOW, ""
    try:
        kind, first = judge(read_rows(path))
        # v2: THE FILE LAGS THE SCREEN - re-read for a short window before refusing, never after allowing.
        waited, grace = 0.0, float(globals().get("GRACE_SECONDS", 0.0))
        while kind == "MISSING" and waited < grace:
            time.sleep(POLL_SECONDS)
            waited += POLL_SECONDS
            kind, first = judge(read_rows(path))
    except OSError as e:
        log(root, key, "FAIL-OPEN", f"transcript unreadable: {type(e).__name__}")
        return ALLOW, ""
    if kind == "NOBRIEF":
        log(root, key, "FAIL-OPEN", "no user text in the transcript yet")
        return ALLOW, ""
    if kind in ("NONE", "PRINTED"):
        # v2: FIRST BY THE FILE'S OWN ORDER - the board's text ahead of every tool call - whatever was refused
        # while the file lagged. v1 read "never refused" instead, and so logged LATE for a board printed first.
        entry["verdict"] = "NONE" if kind == "NONE" else ("FIRST" if first else "LATE")
    elif entry["refusals"] >= MAX_REFUSALS:
        entry["verdict"] = "ESCAPED"
    if entry.get("verdict"):
        log(root, key, entry["verdict"])
        if key:
            sessions[key] = entry
            write_state(root, state)
        return ALLOW, ""
    entry["refusals"] += 1
    log(root, key, "REFUSED", f"{entry['refusals']} of {MAX_REFUSALS}")
    if key:
        sessions[key] = entry
        write_state(root, state)
    return REFUSE, refusal(entry["refusals"])


def read_payload() -> dict:
    # RAW BYTES, DECODED AS UTF-8 - Claude Code writes the payload in UTF-8 and escapes nothing,
    # and Python reads a PIPE in the machine's code page. install_hooks.py's case 11 finds this
    # read by its EXACT text - keep it whole and spelled so.
    raw = sys.stdin.buffer.read().decode("utf-8", errors="replace")
    if not raw.strip():
        return {}
    try:
        o = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return o if isinstance(o, dict) else {}


def main(argv) -> int:
    if "--selftest" in argv:
        return selftest()
    if "--probe" in argv:
        # REPORTS, NEVER GATES, NEVER READS STDIN - run_tests runs this as the entry point, and an
        # entry point blocked on stdin would HANG the suite rather than fail it.
        root = project_root({})
        st = read_state(root)["sessions"]
        counts = {}
        for e in st.values():
            v = e.get("verdict") or f"open ({e.get('refusals', 0)} refused)"
            counts[v] = counts.get(v, 0) + 1
        lp = root.joinpath(*LOG_REL)
        try:
            n_log = len(lp.read_bytes().splitlines())
        except OSError:
            n_log = 0
        summary = ", ".join(f"{k} {v}" for k, v in sorted(counts.items())) or "none yet"
        print(f"board_guard: {len(st)} session(s) seen in {root.name} - {summary}; "
              f"{n_log} log line(s)")
        return 0
    try:
        payload = read_payload()
        code, msg = decide(payload, project_root(payload))
    except Exception as e:          # FAIL-OPEN, declared: an error never blocks
        log(project_root({}), "", "FAIL-OPEN", f"error {type(e).__name__}")
        return ALLOW
    if msg:
        print(msg, file=sys.stderr)
    return code


# --------------------------------------------------------------------- selftest
BOARD = ("| # | phase | state |\n|---|---|---|\n| ~~1~~ | ~~THE FIRST~~ | closed |\n"
         "| **2** | **THE SECOND** | sub-step 3 this session |")
BRIEF_DASHES = f"The task.\n\n-----\n{BOARD}\n\n**Purpose:** x. **Next step:** y.\n-----\n\nDo it."
BRIEF_PLAIN = f"Print this board as your FIRST text:\n\n{BOARD}\n\n**Purpose:** x. **Next step:** y."
ATTENDED = "Please continue with step 5, sub-step 3."


def _u(text):
    return {"type": "user", "message": {"role": "user", "content": text}}


def _text(text):
    return {"type": "assistant", "message": {"content": [{"type": "text", "text": text}]}}


def _think(text):
    return {"type": "assistant", "message": {"content": [{"type": "thinking", "thinking": text}]}}


def _tool(name="Bash"):
    return {"type": "assistant", "message": {"content": [{"type": "tool_use", "name": name, "input": {}}]}}


def _write(path: Path, rows, junk: bool = False) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [json.dumps(r, ensure_ascii=False) for r in rows]
    if junk:
        lines.insert(1, "{not json")
    path.write_bytes(("\n".join(lines) + "\n").encode("utf-8"))
    return path


def selftest() -> int:
    """EVERY REFUSAL PROVED BOTH WAYS: a guard proved only to refuse has not been shown to stay
    quiet, and one proved only to stay quiet has not been shown to bite."""
    cases = []
    saved_grace = globals().get("GRACE_SECONDS")
    globals()["GRACE_SECONDS"] = 0.0      # in-process cases judge at once; the lag case sets its own window
    td = Path(tempfile.mkdtemp(prefix="board_guard_selftest_"))
    try:
        root, home = td / "project", td / "home"
        root.mkdir()
        n = [0]

        def ask(rows, sid=None, junk=False, **extra):
            n[0] += 1
            sid = sid or f"session-{n[0]:04d}"
            tp = _write(td / "t" / f"{sid}.jsonl", rows, junk)
            p = {"tool_name": "Bash", "session_id": sid, "transcript_path": str(tp)}
            p.update(extra)
            return decide(p, root, home), sid

        def verdict(sid):
            return read_state(root)["sessions"].get(sid, {}).get("verdict")

        def log_text():
            lp = root.joinpath(*LOG_REL)
            return lp.read_text(encoding="utf-8") if lp.exists() else ""

        (c, _), sid = ask([_u(ATTENDED), _tool()])
        cases.append(("no board in the brief (a person's session, the control) -> ALLOW", c == ALLOW))
        cases.append(("...remembered as NONE", verdict(sid) == "NONE"))
        (c, msg), _ = ask([_u(BRIEF_PLAIN), _tool()])
        cases.append(("a board with NO dash lines, a tool call before any text -> REFUSE", c == REFUSE))
        cases.append(("...the refusal asks for the board now AND as the LAST text",
                      "NOW" in msg and "LAST" in msg))
        cases.append(("...and says how many refusals before it lets go", f"1 of {MAX_REFUSALS}" in msg))
        (c, _), _ = ask([_u(BRIEF_DASHES), _tool()])
        cases.append(("a board between dash lines, tool first -> REFUSE", c == REFUSE))
        (c, _), sid = ask([_u(BRIEF_PLAIN), _text(BOARD + "\n\n**Purpose:** x"), _tool()])
        cases.append(("the board printed as the first text -> ALLOW", c == ALLOW))
        cases.append(("...logged FIRST", verdict(sid) == "FIRST"))
        spaced = BOARD.replace("| # | phase |", "|  #  |   phase |").replace("|---|---|---|", "| --- | :-- | --- |")
        (c, _), _ = ask([_u(BRIEF_PLAIN), _text(spaced), _tool()])
        cases.append(("the board reprinted with other spacing and separators -> ALLOW", c == ALLOW))
        (c, _), _ = ask([_u(BRIEF_PLAIN), _text("| # | phase | state |\n| ~~1~~ | ~~THE FIRST~~ | closed |"), _tool()])
        cases.append(("only some of the board's rows printed -> REFUSE", c == REFUSE))
        (c, _), _ = ask([_u(BRIEF_PLAIN), _tool("Read"), _text(BOARD), _tool()])
        sid_late = f"session-{n[0]:04d}"
        cases.append(("printed after an earlier tool call -> ALLOW", c == ALLOW))
        cases.append(("...logged LATE, not FIRST", verdict(sid_late) == "LATE"))

        # A REFUSAL, THEN THE BOARD: the same session goes on, LATE.
        rows = [_u(BRIEF_PLAIN), _tool()]
        (c1, _), sid = ask(rows, sid="session-refused-then-printed")
        (c2, _), _ = ask(rows + [_text(BOARD), _tool()], sid=sid)
        cases.append(("refused, then the board printed -> REFUSE then ALLOW",
                      (c1, c2) == (REFUSE, ALLOW)))
        cases.append(("...logged LATE", verdict(sid) == "LATE"))

        # THE BOARD STORED ONLY AS THINKING: refused twice, then let go and logged ESCAPED.
        rows = [_u(BRIEF_PLAIN), _think(BOARD), _tool()]
        got = [ask(rows, sid="session-thinking")[0][0] for _ in range(MAX_REFUSALS + 1)]
        cases.append((f"the board only as THINKING -> REFUSE x{MAX_REFUSALS}, then ALLOW",
                      got == [REFUSE] * MAX_REFUSALS + [ALLOW]))
        cases.append(("...logged ESCAPED", verdict("session-thinking") == "ESCAPED"))

        # v2: THE TRANSCRIPT LAGS THE SCREEN. Measured live on v1's first real run: the board printed first, its
        # row stamped 1.3 s before the call, and still not on disk when the hook read - so v1 refused, and then
        # logged LATE, because it took "first" from "never refused" rather than from the file's own order.
        # Both cases below are RED against v1.
        import threading
        late = td / "t" / "session-lagging.jsonl"
        _write(late, [_u(BRIEF_PLAIN)])
        writer = threading.Timer(0.6, lambda: _write(late, [_u(BRIEF_PLAIN), _text(BOARD), _tool()]))
        writer.start()
        globals()["GRACE_SECONDS"] = 3.0
        try:
            c = decide({"tool_name": "Bash", "session_id": "session-lagging",
                        "transcript_path": str(late)}, root, home)[0]
        finally:
            writer.join()
            globals()["GRACE_SECONDS"] = 0.0
        cases.append(("the board written to disk 0.6 s late, inside the grace window -> ALLOW, never refused",
                      c == ALLOW))
        cases.append(("...logged FIRST", verdict("session-lagging") == "FIRST"))
        lag2 = td / "t" / "session-refused-first.jsonl"
        _write(lag2, [_u(BRIEF_PLAIN)])
        c1 = decide({"tool_name": "Bash", "session_id": "session-refused-first",
                     "transcript_path": str(lag2)}, root, home)[0]
        _write(lag2, [_u(BRIEF_PLAIN), _text(BOARD), _tool(), _tool()])
        c2 = decide({"tool_name": "Bash", "session_id": "session-refused-first",
                     "transcript_path": str(lag2)}, root, home)[0]
        cases.append(("refused while the file lagged, the board then found BEFORE the first tool call -> FIRST",
                      (c1, c2) == (REFUSE, ALLOW) and verdict("session-refused-first") == "FIRST"))

        # A DECIDED SESSION NEVER RE-READS ITS TRANSCRIPT.
        (c, _), sid = ask([_u(BRIEF_PLAIN), _text(BOARD), _tool()], sid="session-cached")
        (td / "t" / "session-cached.jsonl").unlink()
        before = log_text().count("FAIL-OPEN")
        c2 = decide({"tool_name": "Bash", "session_id": sid,
                     "transcript_path": str(td / "t" / "session-cached.jsonl")}, root, home)[0]
        cases.append(("a decided session, its transcript gone -> still ALLOW, from the state",
                      (c, c2) == (ALLOW, ALLOW) and verdict(sid) == "FIRST"
                      and log_text().count("FAIL-OPEN") == before))

        # FAIL-OPEN, DECLARED.
        c = decide({"tool_name": "Bash", "session_id": "session-nowhere",
                    "transcript_path": str(td / "absent.jsonl")}, root, home)[0]
        cases.append(("no transcript anywhere -> ALLOW, logged FAIL-OPEN",
                      c == ALLOW and log_text().count("FAIL-OPEN") == before + 1))
        c = decide({"tool_name": "Bash", "session_id": "../../etc/passwd"}, root, home)[0]
        cases.append(("a session id shaped like a path is never used as one -> ALLOW", c == ALLOW))
        (c, _), _ = ask([_u(BRIEF_PLAIN), _tool()], junk=True)
        cases.append(("a malformed line is skipped, the rest still judged -> REFUSE", c == REFUSE))

        # FOUND BY THE SESSION ID when the payload names no transcript.
        _write(home / ".claude" / "projects" / "C--some-project" / "session-by-id-0001.jsonl",
               [_u(BRIEF_PLAIN), _tool()])
        c = decide({"tool_name": "Bash", "session_id": "session-by-id-0001"}, root, home)[0]
        cases.append(("no transcript_path: found as <session_id>.jsonl under ~/.claude/projects -> REFUSE",
                      c == REFUSE))

        # THE FIRST CALL LOGS KEY NAMES, NEVER A VALUE.
        ask([_u(ATTENDED), _tool()], sid="session-keys", planted="value-never-logged-q9")
        cases.append(("the first call logs the payload's KEY names", "planted" in log_text()))
        cases.append(("...and never a value", "value-never-logged-q9" not in log_text()
                      and str(td) not in log_text()))

        # THE REAL ENTRY POINT, PIPED AS CLAUDE CODE PIPES IT: raw UTF-8, the child given cp1252.
        for label, folder in (("an ASCII folder (the control)", "plain"),
                              ("a folder cp1252 MANGLES", "café"),
                              ("a folder cp1252 cannot decode at all", "Łódź")):
            tp = _write(td / f"bg-{folder}" / "s.jsonl", [_u(BRIEF_PLAIN), _tool()])
            r = _pipe({"tool_name": "Bash", "session_id": f"piped-{len(folder)}-x-0000",
                       "transcript_path": str(tp)}, root)
            cases.append((f"piped raw UTF-8, {label}: the transcript is found, so it REFUSES",
                          r.returncode == REFUSE))
        r = _pipe(None, root, raw=b"[1, 2, 3]")
        cases.append(("piped: a payload that is not an object -> exit 0", r.returncode == ALLOW))
        r = _pipe(None, root, raw=b"")
        cases.append(("piped: an empty payload -> exit 0", r.returncode == ALLOW))
    finally:
        shutil.rmtree(td, ignore_errors=True)
        if saved_grace is None:
            globals().pop("GRACE_SECONDS", None)
        else:
            globals()["GRACE_SECONDS"] = saved_grace

    print("board_guard selftest")
    ok = True
    for name, good in cases:
        ok &= good
        print(f"  {'OK  ' if good else 'MISS'} {name}")
    print(f"\n  {len(cases)} cases, {sum(1 for _, g in cases if g)} passed")
    print("SELFTEST: " + ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


def _pipe(payload, root: Path, raw: bytes | None = None) -> subprocess.CompletedProcess:
    env = {k: v for k, v in os.environ.items() if k not in ("PYTHONUTF8", "PYTHONIOENCODING")}
    env.update(PYTHONIOENCODING="cp1252", CLAUDE_PROJECT_DIR=str(root))
    data = raw if raw is not None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
    return subprocess.run([sys.executable, str(Path(__file__).resolve())], input=data,
                          capture_output=True, env=env, timeout=60)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
