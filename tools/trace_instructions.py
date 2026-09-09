#!/usr/bin/env python3
"""trace_instructions.py - what instruction files actually loaded, and when.
CHECKER VERSION 6 (2026-09-09)

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
    #
    # THE PATH MUST BE ABSOLUTE, AND A RELATIVE ONE FAILS SILENTLY HERE. A hook command
    # resolves against the SESSION's working directory, not the project root, so
    # "tools/trace_instructions.py" writes no log whenever a session starts anywhere else -
    # and the only symptom is this script's own VOID message, which looks exactly like a
    # hook that has simply not fired yet. An absolute path belongs in this layer anyway,
    # because it is the gitignored one: the path names a user, and a committed hook path
    # that names a user fails a confidentiality scan.
    { "hooks": { "InstructionsLoaded": [ { "hooks": [ { "type": "command",
        "command": "uv run python <ABSOLUTE-PATH-TO-PROJECT>/tools/trace_instructions.py --hook" } ] } ] } }
    # ^ WRITTEN AS A BRACKETED PLACEHOLDER, NOT AS A DRIVE LETTER, AND THE PARAGRAPH ABOVE IS
    # WHY (v6, 2026-09-09). This docstring states that a committed path naming a user fails a
    # confidentiality scan, and then carried a drive-letter example -- a placeholder with no
    # real name in it, but the SHAPE such a scan matches on. A scan cannot tell a placeholder
    # from a real path and must not try, so it blocked a real project's commit on this file.
    # The script demonstrated the hazard it documents.
    #
    # AND THE FIRST ATTEMPT AT THIS COMMENT REINTRODUCED IT, by quoting the old example in
    # order to explain it -- the gate fired again, on the fix. Describe a forbidden pattern;
    # never reproduce it. The house already says a report must print a phrase's POSITION and
    # never its text; the same applies to a comment, and nothing had written that down.

    uv run python tools/trace_instructions.py             # the latest session
    uv run python tools/trace_instructions.py --all       # every session
    uv run python tools/trace_instructions.py --rule ooxml
    uv run python tools/trace_instructions.py --audit     # STATIC: read the frontmatter
    uv run python tools/trace_instructions.py --selftest

TWO ARMS, AND THEY ANSWER DIFFERENT HALVES BECAUSE ONE HALF IS UNOBSERVABLE. The log arm
sees a rule that ALWAYS loads - the file really does appear at session start. It can NEVER
see a rule that NEVER loads, because "no match in this session" and "nobody read a matching
file" are the same observation, and no amount of logging separates them. So --audit reads
the frontmatter instead. Neither arm is a lesser version of the other; the runtime one
cannot answer the second question at any length of run.

--audit IS NOT IN THE JUDGED GATE, and deliberately, for the reason this whole script is
outside check_checkers' TRACKED list: it exits 2 - VOID - in any project that has no
path-scoped rules at all, which is most of them. A gate that is VOID by default is a gate
somebody switches off. It is an instrument a person runs, and it prints how many files it
examined so a small clean run cannot be mistaken for a clean one.

IT READS WHAT IS ON DISK, INCLUDING GITIGNORED SCRATCH - honest, not a defect, and the same
property every checker in this house has. A tree holding generated sample projects will
report dozens of files; the COUNT is printed for exactly that reason. Judge the run by the
findings, never by the denominator.

THE LOG IS GITIGNORED, AND THAT IS NOT TIDINESS. Every entry carries absolute paths, so it
names a user and a directory layout. It defaults into temp/, which the house .gitignore
already covers. The instrument ships; the log never does.

STANDALONE ON PURPOSE - it does not import the shared helper. This runs as a HOOK, in a
subprocess spawned around every instruction load, where an ImportError is not a stack trace
someone reads: it is a hook that fails on every event. A diagnostic that can break the tool
it is diagnosing gets switched off, and then there is no diagnostic.

THE WAYS THE READER HAS BEEN WRONG - no count in this heading, deliberately, because a
heading that states one goes stale the next time the list grows. Every one printed a
confident false verdict. They are kept because each was bought with real time, and because a
reader that can print a false verdict will print one again:
  1. It asked only "was there a second match?" and printed SURVIVED when there was not - but
     a compact emits load_reason 'compact' listing what it PUT BACK, and absence from that
     list is itself the measurement.
  2. It counted BASENAMES, and one basename can belong to three files that all load at
     session start, so it reported a re-injection that never happened.
  3. It measured against the FIRST compact in a session. A rule firing between compact 1 and
     compact 2 then reads as never-fired, and a conclusive run gets reported INCONCLUSIVE.
  4. Its fallback branch printed the strongest verdict - gone for the rest of the session -
     for a session in which the rule had never fired at all, which measures nothing.
  5. Bug 2 again, at the one caller the fix missed. verdict() and reinjections() were both
     moved to full-path matching; the EVENT LISTING kept printing Path(...).name, so the
     three instruction files that load at every session start - user, house and project, all
     called CLAUDE.md - rendered as three identical rows. Fix the CLASS, not the caller: two
     of three callers is how the same defect comes back wearing different clothes.
Every branch is proved BOTH ways by --selftest.

THE ONE THING THIS CANNOT SEE, said out loud rather than guessed at. It records LOADS, not
READS. So "no match after the compact" is equally consistent with "the rule was dropped and
did not come back" and with "no matching file was ever read after the compact". The verdict
names that ambiguity instead of resolving it in whichever direction is more interesting.
"""
from __future__ import annotations

import argparse
import contextlib
import io
import json
import os
import re
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


def canon(fp: str) -> str:
    """The IDENTITY of a logged path. TWO SPELLINGS OF ONE FILE ARE ONE FILE.

    MEASURED, NOT TIDINESS. On Windows a directory reached through TEMP can be the 8.3 SHORT
    name while the same file reached another way is the long one, so ONE file is logged
    TWICE - and everything here that keyed on the raw string then counted it twice, listed it
    as two rows, and could not see a re-injection that crossed the two spellings. Measured on
    a real headless session: the user-global instructions appeared as
    ...\\<short>\\.claude\\CLAUDE.md and ...\\<long>\\.claude\\CLAUDE.md, and os.path.samefile
    says they are one directory.

    SAME CLASS AS v3, ONE STEP FURTHER, AND THAT IS WHY IT IS A CLASS FIX RATHER THAN A
    PATCH. v3 stopped printing basenames because three DISTINCT files called CLAUDE.md
    rendered as three identical rows. This is the same confusion from the other side: ONE
    file rendering as two distinct rows. Both come from letting a report LABEL serve as an
    IDENTITY, which this house's verification-hygiene rule 8 already names - fix it at the
    boundary, once, rather than at each site that compares.

    DISPLAY STAYS RAW. The log records what the session actually said, and rewriting that in
    the listing would hide the very duplication this exists to reconcile.

    Falls back to the string it was given: a path that no longer exists still has an
    identity, and a log is read long after the session that wrote it.
    """
    if not fp:
        return ""
    try:
        return os.path.normcase(str(Path(fp).resolve()))
    except (OSError, ValueError):
        return os.path.normcase(fp)


def logged_path(record) -> str:
    """The raw logged path of one event, for display."""
    return str(record["payload"].get("file_path", ""))


def scoped_rules(events):
    """Every distinct file that ever loaded by glob match, newest last.

    Discovering these from the log is what makes the instrument general: the earlier version
    hardcoded one probe filename, so it could only ever judge the rule it was written for.
    """
    out, seen = [], set()
    for r in events:
        if r["payload"].get("load_reason") == MATCH:
            fp = logged_path(r)
            if fp and canon(fp) not in seen:
                seen.add(canon(fp))
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
               and canon(logged_path(r)) == canon(rule)]
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
    # DEDUPED BY IDENTITY, DISPLAYED AS LOGGED. Without canon() one file put back under two
    # spellings inflates "put N file(s) back" and reads as a busier compact than happened.
    _by_id: dict[str, str] = {}
    for _, r in last:
        _by_id.setdefault(canon(logged_path(r)), logged_path(r))
    back = sorted(_by_id.values())
    scoped_back = canon(rule) in _by_id              # exact identity, never substring
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
            if canon(logged_path(r)) == canon(rule)
            and r["payload"].get("load_reason") in (START, COMPACT)]


def reinjections(events):
    """Files loaded more than once in one session, BY FULL PATH.

    By full path, not basename: several distinct files can share a basename and all load at
    session start, which reads as a re-injection that never happened.
    """
    seen, out = {}, []
    for r in events:
        fp, key = logged_path(r), canon(logged_path(r))
        # BY IDENTITY, NOT BY SPELLING. A file put back under the 8.3 short name after
        # loading under the long one IS a re-injection, and keying on the raw string made
        # exactly that case invisible - the quietest direction for this check to fail in.
        if key in seen and r["at"] != seen[key][1]:
            out.append((fp, seen[key][1], r["at"]))
        seen.setdefault(key, (fp, r["at"]))
    return out


# -------------------------------------------------------------------------- static audit
#
# WHY A STATIC ARM EXISTS AT ALL, AND WHY IT IS NOT A SECOND-BEST VERSION OF THE LOG. The
# reader above records LOADS, never READS. So of route 4's two silent failures it can see
# exactly one:
#
#   * ALWAYS LOADS - a rules file with no paths: block loads at launch. The log SEES this,
#     and always_loaded() reports it, because the file really does appear at session start.
#   * NEVER LOADS - a rule whose glob only ever matches CLAUDE.md never fires. The log
#     CANNOT see it, now or ever: "no match" is indistinguishable from "nobody read a
#     matching file". The reader is right to call that VOID, and VOID is where it stops.
#
# The second one is therefore undetectable at runtime BY CONSTRUCTION, and it is the more
# expensive of the two: the block left the charter and loads nowhere. Only reading the
# frontmatter answers it. Added 2026-09-01 on that reasoning, before the checkers travel to
# projects that use route 4 - afterwards would need a second propagation pass.

# Probe paths, and the SECOND LIST IS THE FALSE-POSITIVE GUARD. A glob like "*.md" matches
# CLAUDE.md and also every other markdown file, so it fires on ordinary reads and is NOT the
# defect. Only a rule that matches the charter and NOTHING ELSE never fires.
CHARTER_PROBES = ("CLAUDE.md", "sub/CLAUDE.md", "a/b/CLAUDE.md")
OTHER_PROBES = ("notes.md", "tools/x.py", "tests/test_x.py", "uk/a.txt", "src/main.js",
                "docs/guide.md", "data/x.csv")


def _glob_to_re(glob: str):
    """A glob as a regex. '**' spans separators, '*' and '?' do not.

    HAND-ROLLED BECAUSE fnmatch IS WRONG FOR THIS. fnmatch's '*' matches '/' too, so
    "CLAUDE.md" and "**/CLAUDE.md" would score identically against every probe and the
    charter-only test would report nothing. A matcher that cannot tell two globs apart is
    the silent zero this whole file exists to catch, so it is built explicitly and proved
    in --selftest rather than borrowed.
    """
    out, i = [], 0
    while i < len(glob):
        c = glob[i]
        if c == "*":
            if glob[i:i + 3] == "**/":                # '**/' may also match NOTHING, so
                out.append("(?:.*/)?")                # tools/** covers tools/x directly
                i += 3
                continue
            if glob[i:i + 2] == "**":
                out.append(".*")
                i += 2
                continue
            out.append("[^/]*")
        elif c == "?":
            out.append("[^/]")
        else:
            out.append(re.escape(c))
        i += 1
    return re.compile("^" + "".join(out) + "$")


def glob_matches(glob: str, path: str) -> bool:
    return bool(_glob_to_re(glob).match(path))


def read_rule_frontmatter(text: str):
    """(has_frontmatter, globs) for one rules file.

    FRONTMATTER IS LINE 1 OR IT IS NOT FRONTMATTER. A paths: block further down - inside a
    fenced example, or under a heading explaining the notation - is prose, and a file whose
    only paths: block sits there loads at launch exactly as if it had none. That is a
    recorded house hazard, so the position is asserted rather than searched for.
    """
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return False, []
    globs, in_paths = [], False
    for line in lines[1:]:
        if line.strip() == "---":
            break
        if re.match(r"^\s*paths\s*:", line):
            in_paths = True
            continue
        if in_paths:
            m = re.match(r"""^\s*-\s*["']?([^"'\s]+)["']?\s*$""", line)
            if m:
                globs.append(m.group(1))
                continue
            if line.strip() and not line.startswith((" ", "\t")):
                in_paths = False            # a new top-level key ended the list
    return True, globs


def audit_rule(text: str) -> str:
    """One status per rules file, so every wrong answer is its own string.

    Pure, so --selftest drives it directly rather than through a directory of fixtures.
    """
    has_fm, globs = read_rule_frontmatter(text)
    if not has_fm:
        return "NO FRONTMATTER"                       # loads at launch - the lines moved
    if not globs:                                     # and nothing was saved
        return "NO PATHS"
    hits_charter = any(glob_matches(g, p) for g in globs for p in CHARTER_PROBES)
    hits_other = any(glob_matches(g, p) for g in globs for p in OTHER_PROBES)
    if hits_charter and not hits_other:
        return "CHARTER ONLY"                         # never fires - the expensive one
    return "SCOPED"


def audit(root: Path) -> int:
    """Read every .claude/rules/*.md under root and judge its frontmatter."""
    files = sorted(root.rglob(".claude/rules/*.md"))
    print(f"STATIC AUDIT of route 4 under {root}\n")
    if not files:
        print("VOID: no .claude/rules/*.md found, so nothing was judged. That is NOT a")
        print("  pass - a project with no path-scoped rules and a project whose rules")
        print("  directory is somewhere else look identical from here.")
        return 2
    bad = 0
    for f in files:
        try:
            status = audit_rule(f.read_text(encoding="utf-8", errors="replace"))
        except OSError as e:
            status = f"UNREADABLE ({type(e).__name__})"
        flag = "OK  " if status == "SCOPED" else "!   "
        if status != "SCOPED":
            bad += 1
        print(f"  {flag} {status:<16} {f}")
        if status == "NO FRONTMATTER":
            print("       no '---' on line 1, so it LOADS AT LAUNCH at charter priority -")
            print("       the lines moved out and nothing was saved. A paths: block lower")
            print("       down is prose, not frontmatter.")
        elif status == "NO PATHS":
            print("       frontmatter with no paths: globs - same effect as none at all.")
        elif status == "CHARTER ONLY":
            print("       every glob matches the charter and NOTHING else, so this rule")
            print("       NEVER FIRES. The log cannot see this one: 'never loaded' and")
            print("       'nobody read a matching file' are the same observation.")
    print(f"\n{len(files)} rules file(s) examined, {bad} finding(s)")
    return 1 if bad else 0


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
                # The TRIGGER in full too. Which directory the matching file sat in is the
                # whole question route 4 asks - a glob meant for uk/ that is in fact firing
                # on us/ is the failure this instrument exists to expose, and two files
                # called thing.py in different trees are identical once you print the name.
                extra = f"   <- triggered by {p.get('trigger_file_path', '?')}"
            # NAME **AND** FULL PATH, the same pair the compact and re-injection listings
            # print. The name alone cannot separate the three CLAUDE.md files that load at
            # every session start, which is the one comparison this report exists to make.
            fp = str(p.get("file_path", "?"))
            print(f"  {r['at'][11:19]}  {p.get('memory_type', '?'):<8} "
                  f"{p.get('load_reason', '?'):<16} "
                  f"{Path(fp).name:<22} {fp}{extra}")
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

    # ONE FILE UNDER TWO SPELLINGS IS ONE FILE - v5, and it is the v3 confusion from the
    # other side. Measured on a real headless session: the user-global instructions were
    # logged under the Windows 8.3 SHORT path AND under the long one, and every raw-string
    # comparison here read them as two separate files - so a re-injection that crossed the
    # two spellings was invisible, which is the quietest direction for this check to fail in.
    # THE 8.3 FORM CANNOT BE PLANTED PORTABLY, so this exercises the same normalisation
    # (resolve + normcase) through a redundant path component, and DECLARES that substitution
    # rather than implying the exact case was reproduced.
    _d = Path(tempfile.mkdtemp(prefix="trace_instructions_selftest_"))
    (_d / "sub").mkdir()
    (_d / "CLAUDE.md").write_bytes(b"x")
    (_d / "sub" / "CLAUDE.md").write_bytes(b"y")

    def _pair(p0, p1):
        evs = [_ev(START, "CLAUDE.md"), _ev(COMPACT, "CLAUDE.md", "c1")]
        evs[0]["payload"]["file_path"] = str(p0)
        evs[1]["payload"]["file_path"] = str(p1)
        evs[1]["at"] = "2026-08-19T09:00:00+00:00"
        return evs

    spelt = _pair(_d / "CLAUDE.md", _d / "sub" / ".." / "CLAUDE.md")
    check("two spellings of ONE path IS a reload", len(reinjections(spelt)) == 1,
          len(reinjections(spelt)))
    # ...and the arm that stops the fix from being a blanket 'everything is one file'.
    twofiles = _pair(_d / "CLAUDE.md", _d / "sub" / "CLAUDE.md")
    check("...and two REAL files are still two", reinjections(twofiles) == [],
          len(reinjections(twofiles)))
    shutil.rmtree(_d, ignore_errors=True)

    # THE EVENT LISTING MUST DISTINGUISH FILES THAT SHARE A BASENAME - bug 2 above, one level
    # out. verdict() and reinjections() were both moved to full-path matching and the LISTING
    # was left printing Path(...).name, so the class fix stopped at two of three callers. It
    # is not a hypothetical shape: a project under a house-rules layer loads a USER, a HOUSE
    # and a PROJECT instruction file at session start and all three are called CLAUDE.md, so
    # the listing rendered them as three identical rows - indistinguishable from one file
    # loaded three times, which is the very thing this instrument exists to tell apart.
    TRIO = ["C:\\user\\CLAUDE.md", "C:\\house\\CLAUDE.md", "C:\\proj\\CLAUDE.md"]
    trio = [_ev(START, "CLAUDE.md") for _ in TRIO]
    for _r, _fp in zip(trio, TRIO):
        _r["payload"]["file_path"] = _fp
    # The same claim for the TRIGGER path: a glob firing on us/ when it was written for uk/
    # is route 4's whole failure mode, and both trigger files are called thing.py.
    TRIGGER = "C:\\x\\us\\thing.py"
    trio = trio + [_ev(MATCH, "r.md", "m", trigger_file_path=TRIGGER)]
    tmp2 = Path(tempfile.mkdtemp(prefix="trace_instructions_selftest_"))
    try:
        _f = tmp2 / "l.log"
        _f.write_text("".join(json.dumps(r) + "\n" for r in trio), encoding="utf-8")
        _buf = io.StringIO()
        with contextlib.redirect_stdout(_buf):
            report(_f, False, None)
        out = _buf.getvalue()
        listing = [ln for ln in out.splitlines() if START in ln]
        check("3 files sharing a basename -> 3 DISTINCT lines", len(set(listing)) == 3,
              f"{len(set(listing))} distinct of {len(listing)} rows")
        check("...and each full path is printed", all(fp in out for fp in TRIO),
              f"{sum(fp in out for fp in TRIO)} of 3")
        check("the TRIGGER path prints in full too", TRIGGER in out,
              "present" if TRIGGER in out else "name only")
        # The negative arm: without it the two checks above would also pass on a listing that
        # printed the whole log verbatim, or on any output containing the strings by accident.
        check("a path NOT in the events is not printed", "C:\\nowhere\\CLAUDE.md" not in out,
              "absent")
    finally:
        shutil.rmtree(tmp2, ignore_errors=True)

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

    # ---- THE STATIC ARM. The glob matcher goes first, because every judgement below rests
    # on it and a matcher that cannot tell "CLAUDE.md" from "**/CLAUDE.md" would make the
    # charter-only test report nothing at all while every row still printed.
    for g, path, want in (("CLAUDE.md", "CLAUDE.md", True),
                          ("CLAUDE.md", "sub/CLAUDE.md", False),      # '*' must not span '/'
                          ("**/CLAUDE.md", "sub/CLAUDE.md", True),
                          ("**/CLAUDE.md", "CLAUDE.md", True),        # '**/' may match empty
                          ("*.md", "notes.md", True),
                          ("*.md", "docs/guide.md", False),
                          ("tools/**", "tools/x.py", True),
                          ("tools/**", "tests/x.py", False),
                          ("tests/**/*.py", "tests/a/b/x.py", True),
                          ("tests/**/*.py", "tests/x.txt", False)):
        got = glob_matches(g, path)
        check(f"glob {g!r} vs {path!r}", got == want, got)

    FM = "---\npaths:\n  - \"tools/**\"\n---\n\n# A rule\n"
    for label, text, want in (
        # the mode the LOG can also see
        ("no '---' on line 1 -> NO FRONTMATTER", "# A rule\n\npaths:\n  - \"tools/**\"\n",
         "NO FRONTMATTER"),
        ("frontmatter with no globs -> NO PATHS", "---\npaths:\n---\n\n# A rule\n",
         "NO PATHS"),
        ("no paths: key at all -> NO PATHS", "---\ntitle: x\n---\n\n# A rule\n", "NO PATHS"),
        # THE MODE THE LOG CAN NEVER SEE, in both shapes it arrives in
        ("scoped to CLAUDE.md -> CHARTER ONLY",
         "---\npaths:\n  - \"CLAUDE.md\"\n---\n", "CHARTER ONLY"),
        ("scoped to **/CLAUDE.md -> CHARTER ONLY",
         "---\npaths:\n  - \"CLAUDE.md\"\n  - \"**/CLAUDE.md\"\n---\n", "CHARTER ONLY"),
        # THE FALSE-POSITIVE GUARD, and it is the arm that makes the two above mean
        # something: '*.md' matches CLAUDE.md and fires on every other markdown read, so it
        # is NOT the defect. Without this, flagging anything that touches the charter would
        # pass all the cases above and condemn a perfectly good glob.
        ("'*.md' also fires elsewhere -> SCOPED",
         "---\npaths:\n  - \"*.md\"\n---\n", "SCOPED"),
        ("a charter glob BESIDE a real one -> SCOPED",
         "---\npaths:\n  - \"CLAUDE.md\"\n  - \"tools/**\"\n---\n", "SCOPED"),
        ("an ordinary scoped rule -> SCOPED", FM, "SCOPED"),
        # the recorded hazard: a paths: block inside a fenced example is PROSE
        ("paths: only inside a fence -> NO FRONTMATTER",
         "# A rule\n\n```yaml\npaths:\n  - \"tools/**\"\n```\n", "NO FRONTMATTER"),
    ):
        got = audit_rule(text)
        check(label, got == want, got)

    # the audit's exit codes, and an EMPTY tree is VOID rather than clean
    tmp3 = Path(tempfile.mkdtemp(prefix="trace_instructions_selftest_"))
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            rc = audit(tmp3)
        check("no rules file anywhere is VOID", rc == 2, f"rc={rc}")
        rules = tmp3 / "p" / ".claude" / "rules"
        rules.mkdir(parents=True)
        (rules / "good.md").write_bytes(FM.encode("utf-8"))
        with contextlib.redirect_stdout(io.StringIO()):
            rc = audit(tmp3)
        check("a well-scoped rule audits clean", rc == 0, f"rc={rc}")
        (rules / "bad.md").write_bytes(b"---\npaths:\n  - \"CLAUDE.md\"\n---\n")
        with contextlib.redirect_stdout(io.StringIO()) as buf3:
            rc = audit(tmp3)
        out3 = buf3.getvalue()
        check("a charter-only rule is a FINDING", rc == 1, f"rc={rc}")
        check("...and the report names the file", "bad.md" in out3, "named")
        check("...and does not condemn the good one",
              out3.count("CHARTER ONLY") == 1, out3.count("CHARTER ONLY"))
    finally:
        shutil.rmtree(tmp3, ignore_errors=True)

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
    p.add_argument("--audit", nargs="?", const=".", default=None, metavar="DIR",
                   help="STATIC pass over .claude/rules/ frontmatter (default: here). It "
                        "answers the one failure the log can NEVER see: a rule whose glob "
                        "only matches CLAUDE.md never fires, and 'never loaded' is "
                        "indistinguishable from 'nobody read a matching file'")
    p.add_argument("--selftest", action="store_true")
    args = p.parse_args(argv)
    if args.selftest:
        return selftest()
    if args.hook:
        return hook(Path(args.log))
    if args.audit is not None:
        return audit(Path(args.audit))
    return report(Path(args.log), args.all, args.rule)


if __name__ == "__main__":
    sys.exit(main())
