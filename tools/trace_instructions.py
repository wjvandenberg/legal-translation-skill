#!/usr/bin/env python3
"""trace_instructions.py - what instruction files actually loaded, and when.
CHECKER VERSION 1 (2026-08-21)

TWO FAILURE MODES, BOTH SILENT, WHICH IS WHY THIS EXISTS. A rule scoped to a file glob is
supposed to load only when a matching file is read. It can fail in two directions and neither
one reports anything:

    * the rule NEVER LOADS - the glob does not match what you think it matches, so the
      guidance is simply absent. Every other signal says it worked: the pointer resolves,
      the file is there, its frontmatter is correct.
    * the rule ALWAYS LOADS - a rules file whose frontmatter has lost its paths: block loads
      at launch at full priority, so the lines moved and nothing was saved.

Both look like success from outside. This writes down what happened instead.

WHY A HOOK AND NOT AN INTERACTIVE PANEL. The question is a PATTERN across a session, not a
snapshot: does the rule come back after a compact, and does it load a second time. A panel
shows a person one moment and cannot be read by a script, quoted in a commit, or re-run
tomorrow to check the answer still holds. A hook writes a file. A judgement that is not
repeatable cannot be a gate.

    # .claude/settings.local.json - the PERSONAL layer, never committed: a hook committed
    # into a repo that gets copied elsewhere installs itself silently in other projects.
    { "hooks": { "InstructionsLoaded": [ { "hooks": [ { "type": "command",
        "command": "uv run python tools/trace_instructions.py --hook" } ] } ] } }

    uv run python tools/trace_instructions.py             # the latest session
    uv run python tools/trace_instructions.py --all       # every session
    uv run python tools/trace_instructions.py --rule ooxml
    uv run python tools/trace_instructions.py --selftest

THE LOG IS GITIGNORED, AND THAT IS NOT TIDINESS. Every entry carries absolute paths, so it
names a user and a directory layout. It defaults into temp/, which the house .gitignore
already covers. The instrument ships; the log never does.

STANDALONE ON PURPOSE - it does not import the shared helper. This runs as a HOOK, in a
subprocess spawned around every instruction load, where an ImportError is not a stack trace
someone reads: it is a hook that fails on every event. A diagnostic that can break the tool
it is diagnosing gets switched off, and then there is no diagnostic.

FOUR WAYS THE READER HAS BEEN WRONG, every one printing a confident false verdict. They are
kept here because each was bought with real time, and because a reader that can print a false
verdict will print one again:
  1. It asked only "was there a second match?" and printed SURVIVED when there was not - but
     a compact emits load_reason 'compact' listing what it PUT BACK, and absence from that
     list is itself the measurement.
  2. It counted BASENAMES, and one basename can belong to three files that all load at
     session start, so it reported a re-injection that never happened.
  3. It measured against the FIRST compact in a session. A rule firing between compact 1 and
     compact 2 then reads as never-fired, and a conclusive run gets reported INCONCLUSIVE.
  4. Its fallback branch printed the strongest verdict - gone for the rest of the session -
     for a session in which the rule had never fired at all, which measures nothing.
Every branch is proved BOTH ways by --selftest.

THE ONE THING THIS CANNOT SEE, said out loud rather than guessed at. It records LOADS, not
READS. So "no match after the compact" is equally consistent with "the rule was dropped and
did not come back" and with "no matching file was ever read after the compact". The verdict
names that ambiguity instead of resolving it in whichever direction is more interesting.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

# Duplicated deliberately, for the same reason check_checkers.py duplicates it: a report that
# crashes on a character the terminal codepage cannot encode reports nothing at all.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DEFAULT_LOG = Path("temp") / "instructions-loaded.log"

MATCH, COMPACT, START = "path_glob_match", "compact", "session_start"


# -------------------------------------------------------------------------- hook mode

def hook(log: Path) -> int:
    """Append one event. NEVER fails the tool call - always exit 0.

    A hook that can block work gets removed, and then there is no instrument. Every error
    here is swallowed on purpose; the cost of a lost line is one missing event, and the cost
    of raising is that someone disables the hook.
    """
    try:
        raw = sys.stdin.read()
    except Exception:                                            # noqa: BLE001
        raw = ""
    try:
        payload = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError:
        payload = {"unparsed_stdin": raw[:4000]}
    entry = {"at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
             "cwd": os.getcwd(), "payload": payload}
    try:
        log.parent.mkdir(parents=True, exist_ok=True)
        with log.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:                                            # noqa: BLE001
        pass
    return 0


# -------------------------------------------------------------------------- analysis

def _compact_bursts(events):
    """The compact events of one session, grouped one list per compact.

    GROUPED BY prompt_id, NOT BY TIMESTAMP. One compact emits several events at once; they
    share a prompt_id exactly, whereas a time window is a guess that splits one burst
    straddling a second boundary and merges two compacts a second apart.

    Each entry is (position, row): "before" and "after" are decided by POSITION in an
    append-ordered log, because second-resolution timestamps cannot separate two events
    inside the same second.
    """
    bursts, order = {}, []
    for i, r in enumerate(events):
        if r["payload"].get("load_reason") != COMPACT:
            continue
        key = r["payload"].get("prompt_id") or r["at"]
        if key not in bursts:
            bursts[key] = []
            order.append(key)
        bursts[key].append((i, r))
    return [bursts[k] for k in order]


def scoped_rules(events):
    """Every distinct file that ever loaded by glob match, newest last.

    Discovering these from the log is what makes the instrument general: the earlier version
    hardcoded one probe filename, so it could only ever judge the rule it was written for.
    """
    out = []
    for r in events:
        if r["payload"].get("load_reason") == MATCH:
            fp = str(r["payload"].get("file_path", ""))
            if fp and fp not in out:
                out.append(fp)
    return out


def verdict(events, rule):
    """(code, evidence lines) for one session and one scoped rule, matched by FULL PATH.

    BY EXACT PATH, NOT SUBSTRING, and this is a fix rather than a preference. Matching a rule
    name as a substring means any rule whose filename is contained in another loaded file's
    name inherits that file's fate: 'scoped.md' is a substring of 'unscoped.md', so an
    unscoped file being put back by a compact reported the scoped rule as SURVIVED - the most
    reassuring verdict this instrument has, produced for a rule that was in fact dropped.
    Caught by --selftest at promotion, having never bitten only because of how two probe
    files happened to be named.

    Pure, so --selftest drives it directly rather than through a log file.
    """
    matches = [(i, r) for i, r in enumerate(events)
               if r["payload"].get("load_reason") == MATCH
               and str(r["payload"].get("file_path", "")) == rule]
    bursts = _compact_bursts(events)

    if not bursts:
        if not matches:
            return "NO_COMPACT_NO_MATCH", [
                "INCONCLUSIVE - no compact in this session, and the rule never fired.",
                "    Did you read a file matching its glob?"]
        return "NO_COMPACT", [
            f"INCONCLUSIVE - the rule fired {len(matches)} time(s), but there was no compact",
            "    in this session, so this run says nothing about surviving one."]

    last = bursts[-1]
    last_idx = last[-1][0]
    back = sorted({str(r["payload"].get("file_path", "")) for _, r in last})
    scoped_back = rule in back                       # exact membership, never substring
    before = [m for m in matches if m[0] < last_idx]
    after = [m for m in matches if m[0] > last_idx]

    lines = [f"{len(bursts)} compact(s) in this session. Reading the LAST one, at "
             f"{last[-1][1]['at'][11:19]}, which put {len(back)} file(s) back:"]
    lines += [f"      put back: {Path(f).name:<22} {f}" for f in back]
    lines.append("")

    if scoped_back:
        code = "SURVIVED"
        lines += ["the rule WAS re-injected by the compact. It survives, and a path-scoped",
                  "    rule is safer than the documentation says."]
    elif before and after:
        code = "DROPPED_RELOADED"
        lines += ["the rule HAD fired before this compact, was not put back, and a later",
                  "    matching read RELOADED it - the documented behaviour."]
    elif before:
        code = "DROPPED_GONE"
        lines += ["the rule HAD fired before this compact and was not put back, and no later",
                  "    match appears. WORSE THAN DOCUMENTED if - and only if - a matching file",
                  "    was actually read after the compact.",
                  "    THIS VERDICT RESTS ON SOMETHING THE LOG CANNOT SEE. Confirm you read a",
                  "    matching file after the compact; if you did not, this run is",
                  "    inconclusive."]
    elif after:
        code = "NEVER_FIRED_FIRST_LOAD"
        lines += ["the rule had NEVER fired before this compact, so nothing could be dropped",
                  "    and this later match is its FIRST load. INCONCLUSIVE about the drop."]
    else:
        code = "NEVER_FIRED_AT_ALL"
        lines += ["INCONCLUSIVE - the rule never fired in this session, before or after the",
                  "    compact. There was nothing to drop and nothing to reload."]
    return code, lines


def always_loaded(events, rule):
    """True when a supposedly scoped rule loaded at session start or in a compact.

    THE SECOND SILENT FAILURE, and the cheaper one to detect. A rules file that has lost its
    paths: frontmatter loads unconditionally - so the lines moved out of the charter and
    nothing was saved. It looks exactly like a working relocation from every other angle.
    """
    return [r for r in events
            if str(r["payload"].get("file_path", "")) == rule
            and r["payload"].get("load_reason") in (START, COMPACT)]


def reinjections(events):
    """Files loaded more than once in one session, BY FULL PATH.

    By full path, not basename: several distinct files can share a basename and all load at
    session start, which reads as a re-injection that never happened.
    """
    seen, out = {}, []
    for r in events:
        fp = str(r["payload"].get("file_path", ""))
        if fp in seen and r["at"] != seen[fp]:
            out.append((fp, seen[fp], r["at"]))
        seen.setdefault(fp, r["at"])
    return out


# -------------------------------------------------------------------------- reporting

def load_rows(log: Path):
    rows = []
    for line in log.open(encoding="utf-8"):
        line = line.strip()
        if line:
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return rows


def report(log: Path, want_all: bool, only_rule) -> int:
    if not log.exists():
        print(f"VOID: no log at {log}. The hook has not fired - it is wired in "
              f".claude/settings.local.json and only takes effect at session start.")
        return 2
    rows = load_rows(log)
    if not rows:
        print(f"VOID: {log} is empty - 0 events read.")
        return 2

    sessions = {}
    for r in rows:
        sessions.setdefault(r["payload"].get("session_id", "(none)"), []).append(r)
    # A clean report must say how much it read, or a silent nothing reads as a pass.
    print(f"read {len(rows)} event(s) across {len(sessions)} session(s) from {log}\n")

    # Two outcomes that are NOT the same fact, kept apart the way check_checkers.py keeps
    # them: `finding` is "measured, and something is wrong" (exit 1); `void` is "the
    # measurement could not be taken at all" (exit 2). Collapsing them is how a run that
    # measured nothing gets read as a run that found nothing.
    finding = void = False
    for sid in (list(sessions) if want_all else [list(sessions)[-1]]):
        ev = sessions[sid]
        print(f"=== session {sid}  ({len(ev)} events) ===")
        for r in ev:
            p = r["payload"]
            extra = ""
            if p.get("load_reason") == MATCH:
                extra = (f"   <- triggered by "
                         f"{Path(str(p.get('trigger_file_path', '?'))).name}")
            print(f"  {r['at'][11:19]}  {p.get('memory_type', '?'):<8} "
                  f"{p.get('load_reason', '?'):<16} "
                  f"{Path(str(p.get('file_path', '?'))).name}{extra}")
        print()

        # --rule FILTERS the discovered rules; it never becomes the match key itself, so the
        # judging below stays exact-path even when the user types a fragment.
        found = scoped_rules(ev)
        rules = [f for f in found if only_rule in f] if only_rule else found
        if not found:
            print("  No file loaded by GLOB MATCH in this session, so there is no scoped")
            print("  rule to judge. That is NOT a pass: it is equally consistent with a")
            print("  rule whose glob never matches. Read a file the rule should cover.")
            # Under --all this is a history review and most sessions legitimately have no
            # scoped rule, so it is a note. On a single session it is the whole measurement
            # failing to happen, which is VOID.
            void = void or not want_all
        elif not rules:
            print(f"  VOID: {len(found)} rule(s) loaded by glob match, but none matches "
                  f"--rule {only_rule!r}.")
            print("  Nothing was judged. This is not a clean run - check the spelling.")
            void = True
        for rule in rules:
            print(f"  --- rule: {Path(rule).name} ---")
            code, lines = verdict(ev, rule)
            for ln in lines:
                print(f"  {ln}" if ln else "")
            print(f"\n  VERDICT: {code}")
            bad = always_loaded(ev, rule)
            if bad:
                reasons = sorted({r["payload"].get("load_reason") for r in bad})
                print(f"  ! ALWAYS-LOADED: it also loaded as {', '.join(reasons)} - so it is "
                      f"NOT path-scoped.\n    Check its frontmatter still has a paths: block. "
                      f"Without one it loads at launch\n    and the relocation saved nothing.")
                finding = True
            print()

        rl = reinjections(ev)
        if rl:
            print("  Files RE-loaded later in the same session:")
            for fp, first, again in rl:
                print(f"    {Path(fp).name:<22} {first[11:19]} then {again[11:19]}  {fp}")
        else:
            print("  No file was re-loaded later in this session.")
        print()
    if finding:
        return 1                      # measured, and something is wrong
    return 2 if void else 0           # 2 = could not measure, which is not "nothing wrong"


# -------------------------------------------------------------------------- selftest

def _ev(reason, name, prompt="p0", **extra):
    p = {"session_id": "s", "prompt_id": prompt, "load_reason": reason,
         "file_path": "C:\\x\\" + name, "memory_type": "Project"}
    p.update(extra)
    return {"at": "2026-08-19T08:00:00+00:00", "payload": p}


# DELIBERATELY NAMED SO ONE CONTAINS THE OTHER. 'scoped.md' is a substring of 'unscoped.md',
# which is exactly the collision that made substring matching report a false SURVIVED. The
# fixture keeps the trap armed so the fix cannot silently regress.
SCOPED_NAME = "scoped.md"
SCOPED = "C:\\x\\" + SCOPED_NAME
BOOT = [_ev(START, "CLAUDE.md"), _ev(START, "unscoped.md")]
C1 = [_ev(COMPACT, "CLAUDE.md", "c1"), _ev(COMPACT, "unscoped.md", "c1")]
C2 = [_ev(COMPACT, "CLAUDE.md", "c2"), _ev(COMPACT, "unscoped.md", "c2")]
HIT = [_ev(MATCH, SCOPED_NAME, "m", trigger_file_path="a.py")]


def selftest() -> int:
    print("SELFTEST - a reader that can print a false verdict will print one again\n")
    ok = True
    cases = [
        ("compact puts the rule back         -> SURVIVED", "SURVIVED",
         BOOT + HIT + C1 + [_ev(COMPACT, SCOPED_NAME, "c1")]),
        ("fired, not put back, matched again -> DROPPED_RELOADED", "DROPPED_RELOADED",
         BOOT + HIT + C1 + HIT),
        ("fired, not put back, no match after-> DROPPED_GONE", "DROPPED_GONE", BOOT + HIT + C1),
        ("never fired, then matched after    -> NEVER_FIRED_FIRST_LOAD",
         "NEVER_FIRED_FIRST_LOAD", BOOT + C1 + HIT),
        ("never fired at all, with a compact -> NEVER_FIRED_AT_ALL", "NEVER_FIRED_AT_ALL",
         BOOT + C1),
        ("no compact, rule fired             -> NO_COMPACT", "NO_COMPACT", BOOT + HIT),
        ("no compact, rule never fired       -> NO_COMPACT_NO_MATCH", "NO_COMPACT_NO_MATCH",
         BOOT),
        # BUG 3: measured against the FIRST compact, a rule firing between two compacts reads
        # as never-fired and a conclusive run is called inconclusive.
        ("TWO compacts, fired between them   -> DROPPED_GONE", "DROPPED_GONE",
         BOOT + C1 + HIT + C2),
        ("TWO compacts, fired then matched   -> DROPPED_RELOADED", "DROPPED_RELOADED",
         BOOT + C1 + HIT + C2 + HIT),
    ]
    for label, want, ev in cases:
        got, _ = verdict(ev, SCOPED)
        good = got == want
        ok &= good
        print(f"  {'OK  ' if good else 'MISS'} {label:<52} -> {got}")

    def check(label, good, detail):
        nonlocal ok
        ok &= good
        print(f"  {'OK  ' if good else 'MISS'} {label:<52} -> {detail}")

    # one compact's events group as ONE compact, not as len(events) compacts
    n = len(_compact_bursts(BOOT + C1 + HIT + C2))
    check("two compacts group as 2, not 4", n == 2, n)

    # a shared basename must not read as a re-injection ...
    same = [_ev(START, "CLAUDE.md"), _ev(START, "CLAUDE.md")]
    same[1]["payload"]["file_path"] = "C:\\other\\CLAUDE.md"
    check("same basename, different path: not a reload", reinjections(same) == [],
          len(reinjections(same)))
    # ... and a genuine one must still be caught, or the check above proves nothing
    real = [_ev(START, "CLAUDE.md"), _ev(COMPACT, "CLAUDE.md", "c1")]
    real[1]["at"] = "2026-08-19T09:00:00+00:00"
    check("same path twice IS a reload", len(reinjections(real)) == 1, len(reinjections(real)))

    # the always-loaded detector, proved BOTH ways
    check("a rule that only glob-matches is scoped", always_loaded(BOOT + HIT, SCOPED) == [],
          len(always_loaded(BOOT + HIT, SCOPED)))
    lost = BOOT + [_ev(START, SCOPED_NAME)] + HIT
    check("a rule loading at session_start is NOT scoped", len(always_loaded(lost, SCOPED)) == 1,
          len(always_loaded(lost, SCOPED)))

    # rule discovery replaces the hardcoded probe name, and must find only glob-matched files
    found = scoped_rules(BOOT + HIT + C1)
    check("scoped_rules finds the matched file only", found == [SCOPED], found)
    check("scoped_rules finds none when nothing matched", scoped_rules(BOOT) == [],
          scoped_rules(BOOT))

    # a missing log is VOID (exit 2), which is not the same fact as a clean run
    rc = report(Path("no") / "such" / "file.log", False, None)
    check("a missing log is VOID, not a pass", rc == 2, f"rc={rc}")

    # THE EXIT CODES, PROVED RATHER THAN OBSERVED, because 0 / 1 / 2 are three different
    # claims and the whole point of the split is that they must not collapse into each other.
    tmp = Path(tempfile.mkdtemp(prefix="trace_instructions_selftest_"))
    try:
        def write(rows):
            f = tmp / "l.log"
            f.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
            return f

        rc = report(write(BOOT), False, None)
        check("events but no glob match: VOID", rc == 2, f"rc={rc}")
        rc = report(write(BOOT + HIT), False, None)
        check("a scoped rule that behaved: clean", rc == 0, f"rc={rc}")
        rc = report(write(BOOT + [_ev(START, SCOPED_NAME)] + HIT), False, None)
        check("a rule loading at launch: a FINDING", rc == 1, f"rc={rc}")
        rc = report(write(BOOT + HIT), False, "nosuchrule")
        check("--rule matching nothing: VOID", rc == 2, f"rc={rc}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print("\nSELFTEST: " + ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


def main(argv=None) -> int:
    p = argparse.ArgumentParser(
        description="Report what instruction files actually loaded, and when.")
    p.add_argument("--hook", action="store_true",
                   help="hook mode: append one event from stdin, always exit 0")
    p.add_argument("--log", default=str(DEFAULT_LOG),
                   help="log file (default temp/, which is gitignored - it holds "
                        "absolute paths)")
    p.add_argument("--all", action="store_true", help="every session, not just the latest")
    p.add_argument("--rule", default=None,
                   help="judge only rules whose path contains this substring")
    p.add_argument("--selftest", action="store_true")
    args = p.parse_args(argv)
    if args.selftest:
        return selftest()
    if args.hook:
        return hook(Path(args.log))
    return report(Path(args.log), args.all, args.rule)


if __name__ == "__main__":
    sys.exit(main())
