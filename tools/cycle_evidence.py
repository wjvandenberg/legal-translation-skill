#!/usr/bin/env python3
"""cycle_evidence.py - did VERIFY and TEST actually run, against the content being committed?
CHECKER VERSION 1 (2026-08-27)

If a project's copy says a lower version than this one, it is stale - see the "Checkers"
line for each version in ...\\Coding\\templates\\TEMPLATE-CHANGELOG.md and re-copy.

THE GAP THIS FILLS. The house cycle requires VERIFY and TEST to produce artefacts rather
than intentions, and until now that requirement was carried entirely by prose. Every other
checker here answers "is this thing sound?"; none of them answers "was it checked, and was
it checked in the state you are about to commit?" That question cannot be answered by
reading the tree, only by recording something at the moment a command runs.

    uv run python tools/cycle_evidence.py verify -- <the verify command>
    uv run python tools/cycle_evidence.py test   -- <the test command>
    uv run python tools/cycle_evidence.py na verify "<why it does not apply, 15+ chars>"
    uv run python tools/cycle_evidence.py check          # what a pre-commit hook calls
    uv run python tools/cycle_evidence.py status
    uv run python tools/cycle_evidence.py --selftest     # prove every check can FAIL
    uv run python tools/cycle_evidence.py --write-config

WHY THE CONTENT HASH IS THE WHOLE DESIGN. A commit-message trailer saying "Verified: yes"
costs nothing to type and proves nothing. Evidence here is bound to a hash of the working
tree, so EDITING A FILE AFTER TESTING IT INVALIDATES THE EVIDENCE AUTOMATICALLY. A record
that cannot be typed is the only kind worth keeping.

AND BOTH READINGS ARE PRINTED, WHICH IS THE CAPABILITY RATHER THAN A COURTESY. The weaker
reading - "a command ran and exited 0" - is a row of its own, beside the content-bound one.
It has to be, because those two rows disagreeing IS the finding: a run that passes the first
and fails the second says you tested something, just not this. One row saying FAIL cannot
tell you that, and the pair is also what shows the new check is not decoration on the old.

THE HASH IS THE WORKTREE'S, NOT THE INDEX'S, and the reason is a repair this design already
needed once. Recording against the worktree while checking against the staged tree makes the
two differ the moment anything is unstaged, so evidence can never match and the gate refuses
everything - found only by a negative test. The worktree is the right anchor because it is
what the commands actually ran against: A PARTIALLY STAGED COMMIT IS A SUBSET OF WHAT WAS
TESTED, which is safe, and the unsafe case - committing something never tested - cannot
happen while the worktree hash matches.

  CHECKED HERE     that a command was recorded for verify and for test, or one of them
                   declared N/A with a reason of real length - the weaker reading, reported
                   as its own row * that every record's content hash still equals the
                   current worktree hash, so nothing was edited after being checked * that
                   the evidence store is BOTH covered by an ignore rule AND untracked.
  ALLOWED, NAMED   a declared N/A, which discharges a phase - with a reason of 15 characters
                   or more, because a one-word excuse reads as a decision nobody made * the
                   command running in the directory it was TYPED in rather than at the
                   repository root, with that directory written into the record: the store
                   and the hash are repository-scoped, a command is not * a
                   partially staged commit, for the reason above * evidence going stale on a
                   declared N/A too: if the change grew, the judgement that it did not apply
                   has to be made again * an UNTRACKED file being invisible to the hash when
                   a command is recorded. It becomes visible the moment it is staged, so the
                   hash then differs and the gate says STALE - it errs closed, which is the
                   safe direction, and the selftest asserts it.
  NOT CHECKED      WHETHER THE COMMAND WAS ANY GOOD. Nothing can check that, and it is the
                   one thing a reader is most likely to assume: a negative test can pass
                   while failing to make its own violation, and no gate would see it. This
                   proves a command ran against this content and exited 0 - strictly more
                   than nothing, strictly less than a guarantee, and the blocking message
                   says which * whether the command was the RIGHT one for the change * the
                   evidence of any branch but the current one * anything at all outside a
                   git repository, which is VOID rather than a pass.

EXIT CODES.  0 = both phases have evidence matching this content.  1 = blocked.
2 = could not run at all (not a git repository, or the store is unreadable).
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from house_common import (                                          # noqa: E402
    FAIL, PASS, RC_COULD_NOT_RUN, RC_FAILED, RC_OK, VOID, Case, Report,
    load_section, report_pairing, run_cases, safe_stdout, selftest_config, write_section,
)

#: The two stages of the cycle that produce evidence. NOT CONFIGURABLE, deliberately: the
#: pair is the house rule, and a project able to drop one would drop the one that was
#: failing. The done-when for this script is that ONLY the store path is parameterised.
PHASES = ("verify", "test")

MIN_REASON = 15

DEFAULT_CONFIG = {
    "store": "temp/.cycle-evidence.json",
}

CONFIG_COMMENT = {
    "store": ("Where the evidence lives, RELATIVE TO THE REPOSITORY ROOT. It must be "
              "gitignored and untracked - checked, not assumed: a committed pass is a pass "
              "someone else inherits without earning. This is the ONLY project-specific "
              "setting; everything else about the gate is the house rule."),
}


# --------------------------------------------------------------------------- git plumbing

def git_bytes(root: Path, *args):
    """git, returning RAW BYTES, with stdin closed.

    IT CANNOT USE house_common.git, AND THE REASON IS THE HASH. That helper decodes to text,
    which on this platform also normalises line endings - so the same tree would hash
    differently depending on how a file happened to be written, and an evidence record would
    go stale for a reason nobody changed. A hash has to be taken over bytes.

    stdin=DEVNULL for the reason the shared helper gives: git will open a pager or prompt for
    credentials against an inherited terminal, and a gate that stops to ask a question inside
    an unattended run hangs it rather than failing it.
    """
    return subprocess.run(["git", *args], cwd=str(root), capture_output=True,
                          stdin=subprocess.DEVNULL)


def git_text(root: Path, *args):
    """The same call where the answer is a name rather than content."""
    r = git_bytes(root, *args)
    return r.returncode, r.stdout.decode("utf-8", "replace").strip()


def repo_root(start: Path):
    """(root, error) - the repository top level, or why there is none.

    RESOLVED ONCE AND PASSED IN, never read from the working directory inside a function.
    Two separate reasons, and the second is why this script differs from its siblings:

      * cwd bit an earlier checker in this set - it read the repository root from wherever it
        happened to be invoked, so calling it from another directory reported on the wrong
        tree WITHOUT FAILING, which is the shape of defect this house treats as worst.
      * the evidence store and the worktree hash are intrinsically REPOSITORY-scoped. One
        repository has one worktree and therefore one hash; a store resolved per directory
        would record two answers for one tree. So the config is read from the repository
        root as well, which is a DECLARED divergence from the other checkers here - they
        read it from the current directory - and the resolved paths are printed on every run
        rather than left to be inferred.
    """
    rc, out = git_text(start, "rev-parse", "--show-toplevel")
    if rc != 0 or not out:
        return None, (f"{start} is not inside a git repository, so there is no worktree to "
                      f"hash and nothing to bind evidence to - not every project is a repo")
    return Path(out).resolve(), None


def worktree_hash(root: Path):
    """A hash of everything this change has done to tracked content.

    `git diff HEAD --binary` covers modifications AND anything already staged, including a
    new file once it is added - which is the state a pre-commit hook actually sees.
    """
    return hashlib.sha256(git_bytes(root, "diff", "HEAD", "--binary").stdout).hexdigest()


def branch(root: Path):
    return git_text(root, "branch", "--show-current")[1]


# --------------------------------------------------------------------------- the store

def store_path(root: Path, cfg) -> Path:
    return root / cfg["store"]


def load(store: Path):
    """The record, or an empty one. A corrupt store is EMPTY, never half-read: a partial
    record would silently discharge a phase nobody checked."""
    if store.exists():
        try:
            return json.loads(store.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def save(store: Path, d) -> None:
    store.parent.mkdir(parents=True, exist_ok=True)
    # BYTES, and newline="" would do as well - what must not happen is write_text() on this
    # platform, which opens in text mode and turns every \n into \r\n. Here that is only
    # untidy; the same call on a document silently rewrites every line in the file.
    store.write_bytes((json.dumps(d, indent=1, sort_keys=True) + "\n").encode("utf-8"))


def record(root: Path, store: Path, phase: str, cmd, cwd: Path | None = None) -> int:
    """Run the command, and record it ONLY if it exits 0.

    A FAILING COMMAND IS NOT EVIDENCE, and saying so is half of what this file is for. The
    record is written after the run, from the exit code, so there is no path on which a
    failure leaves something behind that a later `check` would accept.

    THE COMMAND RUNS WHERE IT WAS TYPED, NOT AT THE REPOSITORY ROOT, and that split was found
    by wiring this into a real project rather than by reasoning about it. The store and the
    hash are repository-scoped because a repository has one worktree; a COMMAND is not.
    Forcing the root on it silently breaks every project whose test runner lives in a
    subdirectory and expects to be run from there - measured here, where the suite reads its
    config from the directory it sits in and reports VOID from anywhere else. So cwd defaults
    to root only when a caller gives none.

    PYTHONDONTWRITEBYTECODE, because a wrapped command inherits THIS process's environment
    rather than the environment whoever wrote the command chose. Importing a module drops a
    __pycache__ beside it; those are gitignored, so they never appear in a diff, and a
    packaging step that zips a directory ships them. The general form of the hazard: a
    wrapper changes the environment its payload runs in, and the difference is invisible
    exactly where it does damage.

    stdin=DEVNULL for the reason a sibling script bought at 900 seconds: an inherited stdin
    let a payload that reads one block the whole run instead of failing it. A verify or test
    command that genuinely needs a human at the keyboard is not evidence anybody can re-run.
    """
    where = Path(cwd) if cwd else root
    print(f"  [{phase}] {' '.join(cmd)}")
    print(f"  [{phase}] in {where}")
    sys.stdout.flush()
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    rc = subprocess.run(cmd, cwd=str(where), env=env, stdin=subprocess.DEVNULL).returncode
    if rc != 0:
        print(f"  [{phase}] exit {rc} - NOT recorded. A failing command is not evidence.")
        return rc
    d = load(store)
    d.setdefault(branch(root), {})[phase] = {
        "command": " ".join(cmd),
        # THE DIRECTORY IS PART OF THE RECORD. The same command name means different things
        # in two folders, and `status` is read by whoever has to believe the evidence.
        "cwd": str(where),
        "exit": rc,
        "content": worktree_hash(root),
        "when": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "declared_na": False,
    }
    save(store, d)
    print(f"  [{phase}] exit 0 - recorded against the current content.")
    return RC_OK


def declare_na(root: Path, store: Path, phase: str, reason: str) -> int:
    """A declared N/A discharges the requirement. Silence does not.

    THE LENGTH FLOOR IS THE POINT. "n/a", "-", "later" all read on a report as a decision
    somebody made, and none of them is one. Refusing a one-word excuse is the template's
    declared-N/A rule made mechanical instead of hoped for.
    """
    reason = (reason or "").strip()
    if len(reason) < MIN_REASON:
        print(f"  a declared N/A needs a REASON, not a word - {MIN_REASON} characters or "
              f"more, and this was {len(reason)}. Refused, and nothing was recorded.")
        return RC_FAILED
    d = load(store)
    d.setdefault(branch(root), {})[phase] = {
        "command": None, "exit": None, "content": worktree_hash(root),
        "when": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "declared_na": True, "reason": reason,
    }
    save(store, d)
    print(f"  [{phase}] declared N/A: {reason}")
    return RC_OK


# --------------------------------------------------------------------------- the checks

def check_ran(rep, records) -> None:
    """THE WEAKER READING, reported as its own row: is there a record at all?

    This is the whole of what a "Verified: yes" trailer or a checklist tick can ever assert,
    and it is here so that the pair of rows can disagree. A run that passes this and fails
    the next one is telling you something neither row says alone.
    """
    absent = [p for p in PHASES if not records.get(p)]
    rep.record("a command ran and exited 0", len(PHASES),
               [f"nothing recorded for {p} on this branch" for p in absent])


def check_matches(rep, records, current: str) -> None:
    """THE CONTENT-BOUND READING, and the capability this script exists for."""
    present = [p for p in PHASES if records.get(p)]
    stale = [p for p in present if records[p]["content"] != current]
    rep.record(
        "evidence matches the current content", len(present),
        [f"{p} ran against different content - it was checked, but not in this state"
         for p in stale],
        # A DENOMINATOR OF ZERO IS VOID AND MUST NOT BE MISTAKEN FOR THE OTHER ROW'S FAIL.
        # With nothing recorded there is nothing to compare, and "no stale evidence found"
        # over 0 records is not a result. The row above already blocks, so nothing is lost.
        void_reason=None if present else
        "no evidence at all, so no hash was compared - the row above is the finding")


def check_store_safe(rep, root: Path, store: Path) -> None:
    """THE STORE MUST BE UNCOMMITTABLE, AND THAT IS A GUARD RATHER THAN A COMMENT.

    A committed pass is a pass someone else inherits without earning - and the version of
    this idea worth having is not a note beside the path saying "gitignored". A project
    adopting this points the store wherever it likes, and both ways of getting it wrong are
    silent: an ignore rule that does not cover it, and a file already tracked from before the
    rule existed. So both are tested, and the row names whichever it was.
    """
    rel = store.relative_to(root).as_posix() if store.is_relative_to(root) else None
    if rel is None:
        rep.record("the evidence store is uncommittable", 0, [],
                   void_reason=(f"the store {store} is outside the repository, so no ignore "
                                f"rule can be tested - it is also unreachable by a commit"))
        return
    problems = []
    rc, _ = git_text(root, "check-ignore", "-q", "--", rel)
    if rc == 1:
        problems.append(f"{rel} is not covered by any ignore rule - one `git add` and the "
                        f"evidence becomes committable")
    elif rc not in (0, 1):
        rep.record("the evidence store is uncommittable", 0, [],
                   void_reason=f"git check-ignore exited {rc} for {rel} - nothing was tested")
        return
    if git_text(root, "ls-files", "--error-unmatch", "--", rel)[0] == 0:
        problems.append(f"{rel} is already TRACKED - an ignore rule does not untrack a file "
                        f"that was added before it")
    rep.record("the evidence store is uncommittable", 1, problems)


def check(root: Path, store: Path) -> Report:
    """The three rows a pre-commit hook reads. Building the Report is all this does."""
    rep = Report()
    records = load(store).get(branch(root), {})
    current = worktree_hash(root)
    check_ran(rep, records)
    check_matches(rep, records, current)
    check_store_safe(rep, root, store)
    return rep


# --------------------------------------------------------------------------- the report

def print_phases(root: Path, records, current: str) -> None:
    """One line per phase, in a reader's words rather than the report's."""
    for p in PHASES:
        e = records.get(p)
        if not e:
            state = "MISSING - nothing has been recorded"
        elif e["content"] != current:
            state = "STALE - the content changed after this ran"
        elif e["declared_na"]:
            state = f"declared N/A - {e['reason'][:52]}"
        else:
            state = f"ok - {e['command'][:52]}"
        print(f"  {p.upper():<7} {state}")


def print_blocked(store_hint: str) -> None:
    """The blocking message, WITH THE LIMITS OF THE GATE INSIDE IT.

    Stating what this does not prove belongs here and nowhere else: a docstring is read by
    whoever maintains the script, and this text by whoever is being stopped by it. The second
    reader is the one who might otherwise take a green gate for a guarantee.
    """
    print()
    print("  COMMIT BLOCKED.")
    print()
    print(f"    {store_hint} verify -- <your verify command>")
    print(f"    {store_hint} test   -- <your test command>")
    print(f"    {store_hint} na verify \"<why it does not apply>\"")
    print()
    print("  This proves a command RAN against this content and exited 0. It does NOT prove")
    print("  the command was a good one - nothing can. A negative test can pass while")
    print("  failing to make its own violation, and no gate would see it.")


def load_config(root: Path):
    return load_section(root, "cycle", DEFAULT_CONFIG)


def main(argv):
    """A FLAG IS ONLY A FLAG IN FIRST POSITION, and that is a fix rather than a style.

    This script's other subcommands take a whole command line after `--`, so the usual house
    idiom - `if "--selftest" in argv` - scans the PAYLOAD as well as the wrapper. Measured on
    the first real use: recording `test -- ... run_tests.py --selftest` ran THIS script's own
    selftest, printed PASS, exited 0, and recorded nothing. Every signal said it had worked.
    The defect is general to any wrapper whose arguments include another program's.
    """
    safe_stdout()
    flag = argv[0] if argv else ""
    if flag == "--selftest":
        return selftest()

    root, err = repo_root(Path.cwd())
    if err:
        print(f"VOID: {err}. Nothing was checked.")
        return RC_COULD_NOT_RUN

    if flag == "--write-config":
        write_section(root, "cycle", DEFAULT_CONFIG, CONFIG_COMMENT)
        return RC_OK

    cfg = load_config(root)
    store = store_path(root, cfg)
    hint = "uv run python <path to>/cycle_evidence.py"

    if not argv:
        print(__doc__.strip())
        return RC_COULD_NOT_RUN

    cmd, rest = argv[0], argv[1:]

    if cmd == "status":
        print(f"root  {root}")
        print(f"store {store}")
        print(json.dumps(load(store).get(branch(root), {}), indent=1))
        return RC_OK

    if cmd == "na":
        if len(rest) < 1 or rest[0] not in PHASES:
            print(f"  na needs a phase: {' or '.join(PHASES)}")
            return RC_COULD_NOT_RUN
        return declare_na(root, store, rest[0], " ".join(rest[1:]))

    if cmd in PHASES:
        if rest and rest[0] == "--":
            rest = rest[1:]
        if not rest:
            print("  give a command to run after --")
            return RC_COULD_NOT_RUN
        return record(root, store, cmd, rest, cwd=Path.cwd())

    if cmd != "check":
        print(f"  unknown: {cmd}")
        return RC_COULD_NOT_RUN

    rep = check(root, store)
    print("=" * 88)
    print(f"CYCLE EVIDENCE - branch {branch(root) or '(detached)'}")
    print(f"  root  {root}")
    print(f"  store {store}")
    print("=" * 88)
    print_phases(root, load(store).get(branch(root), {}), worktree_hash(root))
    print()
    print(rep.render(name_width=38))
    if rep.failed:
        print_blocked(hint)
    else:
        print("\n  Both phases have evidence matching the current working tree.")
    print("=" * 88)
    print(f"VERDICT: {rep.verdict()}")
    line = rep.judge_line()
    if line:
        print(line)
    return rep.exit_code


# ------------------------------------------------------------------------------ selftest

def _repo(tmp: Path, name: str, ignore: str = "temp/\n") -> Path:
    """A real, tiny git repository. REAL because every claim here is about git's answers -
    a stub would test the stub. Identity is set locally so a machine with no global config
    can still commit, and it is a noreply address for the reason this house always gives."""
    d = tmp / name
    d.mkdir(parents=True, exist_ok=True)
    for args in (("init", "-q"), ("config", "user.email", "noreply@example.invalid"),
                 ("config", "user.name", "selftest"), ("config", "commit.gpgsign", "false")):
        git_bytes(d, *args)
    (d / ".gitignore").write_bytes(ignore.encode("utf-8"))
    (d / "tracked.txt").write_bytes(b"content A\n")
    git_bytes(d, "add", "-A")
    git_bytes(d, "commit", "-q", "-m", "base")
    return d


def _store(d: Path) -> Path:
    return store_path(d, DEFAULT_CONFIG)


def _recorded(d: Path) -> None:
    """Evidence for both phases, against whatever the content is NOW."""
    for p in PHASES:
        h = worktree_hash(d)
        s = _store(d)
        rec = load(s)
        rec.setdefault(branch(d), {})[p] = {
            "command": f"echo {p}", "exit": 0, "content": h,
            "when": "2026-01-01T00:00:00", "declared_na": False}
        save(s, rec)


def _status(d: Path, row: str) -> str:
    return check(d, _store(d)).status_of(row)


def _has_record(d: Path, phase: str) -> str:
    """PASS if something was recorded for this phase, FAIL if not.

    A ROW STATUS WOULD NOT DO HERE, and that is not fussiness. "Nothing was recorded" and
    "the wrong thing was recorded" both surface as one FAIL on the report, so a case reading
    the row cannot show which of the two it caught - and both arms of the pair would read
    FAIL, which is precisely the one-sided case this house refuses.
    """
    return PASS if load(_store(d)).get(branch(d), {}).get(phase) else FAIL


RAN = "a command ran and exited 0"
MATCHES = "evidence matches the current content"
SAFE = "the evidence store is uncommittable"


def _stale(tmp: Path, name: str) -> Path:
    """Recorded, THEN the content changed. THE ONE FIXTURE THE WHOLE SCRIPT IS FOR, and it
    is a named function rather than a closure because the acceptance assertion needs the
    same fixture the case table uses - two builders that agree today are two builders."""
    d = _repo(tmp, name)
    _recorded(d)
    (d / "tracked.txt").write_bytes(b"content B\n")
    return d


def cases(tmp: Path):
    seq = iter(range(1, 999))

    def fresh(**kw):
        return _repo(tmp, f"r{next(seq):03d}", **kw)

    def stale(_):
        return _stale(tmp, f"r{next(seq):03d}")

    def matching(_):
        d = fresh()
        _recorded(d)
        return d

    def nothing(_):
        return fresh()

    def na_short(_):
        d = fresh()
        declare_na(d, _store(d), "verify", "n/a")
        return d

    def na_real(_):
        d = fresh()
        declare_na(d, _store(d), "verify", "documentation only, no code path touched")
        return d

    def failing(_):
        """A command that exits non-zero must leave NOTHING behind."""
        d = fresh()
        record(d, _store(d), "verify", [sys.executable, "-c", "raise SystemExit(3)"])
        return d

    def passing(_):
        d = fresh()
        record(d, _store(d), "verify", [sys.executable, "-c", "pass"])
        return d

    def store_tracked(_):
        """Ignored AND tracked - the failure an ignore rule alone does not prevent, because
        a rule added after the file does not untrack it."""
        d = fresh()
        save(_store(d), {})
        git_bytes(d, "add", "-f", "--", DEFAULT_CONFIG["store"])
        git_bytes(d, "commit", "-q", "-m", "oops")
        return d

    def store_unignored(_):
        """Untracked, but no rule covers it - one `git add` from being committable."""
        d = fresh(ignore="\n")
        save(_store(d), {})
        return d

    def store_ignored(_):
        d = fresh()
        save(_store(d), {})
        return d

    return [
        Case("stale content -> the hash row FAILS", lambda d: _status(d, MATCHES),
             stale, matching, want=FAIL, good_want=PASS),
        Case("no record -> the ran row FAILS", lambda d: _status(d, RAN),
             nothing, matching, want=FAIL, good_want=PASS),
        Case("nothing recorded -> hash row is VOID", lambda d: _status(d, MATCHES),
             nothing, matching, want=VOID, good_want=PASS),
        Case("a failing command records nothing", lambda d: _has_record(d, "verify"),
             failing, passing, want=FAIL, good_want=PASS),
        Case("a one-word N/A is refused", lambda d: _has_record(d, "verify"),
             na_short, na_real, want=FAIL, good_want=PASS),
        Case("a TRACKED store -> FAIL", lambda d: _status(d, SAFE),
             store_tracked, store_ignored, want=FAIL, good_want=PASS),
        Case("an UNIGNORED store -> FAIL", lambda d: _status(d, SAFE),
             store_unignored, store_ignored, want=FAIL, good_want=PASS),
    ]


def _assert_acceptance_pair(tmp: Path) -> bool:
    """THE ACCEPTANCE CONDITION, AND A CASE ROW CANNOT STATE IT.

    The claim this capability rests on is not "the new row fires" - a check the old path
    already caught is decoration. It is that the new row fires WHERE THE OLD READING PASSES
    AS CLEAN. That is a relation between two rows off ONE fixture, and a case table reports
    one row per case, so it goes here. Third time this shape has been needed in this set.

    The fixture: evidence recorded against content A, then the file becomes content B. The
    old reading - a command ran and exited 0 - is still perfectly true, and still passes.
    """
    d = _stale(tmp, "acceptance")
    rep = check(d, _store(d))
    ran, matches = rep.status_of(RAN), rep.status_of(MATCHES)
    good = ran == PASS and matches == FAIL
    print(f"  {'OK  ' if good else 'MISS'} {'ACCEPTANCE: old PASS, new FAIL':<42} -> "
          f"ran {ran}, matches {matches} (want {PASS} then {FAIL})")
    return good


def _assert_command_runs_where_typed(tmp: Path) -> bool:
    """THE COMMAND'S DIRECTORY IS THE CALLER'S, THE STORE'S IS THE REPOSITORY'S.

    Both halves in one assertion, because getting either alone right is what made this wrong
    in the first version: the repository root is correct for the hash and wrong for the
    command. The probe is a command that can only succeed in a subdirectory, run twice.
    """
    d = _repo(tmp, "cwd")
    sub = d / "runner"
    sub.mkdir(parents=True, exist_ok=True)
    (sub / "marker.txt").write_bytes(b"here\n")
    probe = [sys.executable, "-c",
             "import os,sys; sys.exit(0 if os.path.exists('marker.txt') else 7)"]
    at_root = record(d, _store(d), "verify", probe)
    from_sub = record(d, _store(d), "verify", probe, cwd=sub)
    good = at_root != 0 and from_sub == RC_OK and _has_record(d, "verify") == PASS
    print(f"  {'OK  ' if good else 'MISS'} {'the command runs where it was typed':<42} -> "
          f"root exit {at_root}, subdir exit {from_sub} (want non-zero then 0)")
    return good


def _assert_payload_flags_do_not_hijack(tmp: Path) -> bool:
    """A FLAG IN THE WRAPPED COMMAND MUST NOT BE READ AS THE WRAPPER'S OWN.

    Reproduced before the fix and kept afterwards, because this is the failure mode with the
    least visible symptom in the whole script: recording a command whose own arguments
    include `--selftest` ran this file's selftest, printed SELFTEST: PASS, exited 0, and
    wrote no evidence at all. A caller reading the exit code learns nothing.

    main() is called directly rather than through a subprocess so the assertion tests the
    dispatch, which is where the defect was, and not a shell's word-splitting.
    """
    d = _repo(tmp, "hijack")
    cwd = Path.cwd()
    try:
        os.chdir(d)
        # `--selftest` is genuinely IN the wrapper's argv here - as the payload's own
        # argument, which is exactly how it arrived in the real invocation that failed.
        rc = main(["verify", "--", sys.executable, "-c", "pass", "--selftest"])
    finally:
        os.chdir(cwd)
    good = rc == RC_OK and _has_record(d, "verify") == PASS
    print(f"  {'OK  ' if good else 'MISS'} {'a payload flag does not hijack':<42} -> "
          f"exit {rc}, recorded {_has_record(d, 'verify')} (want 0 and {PASS})")
    return good


def _assert_untracked_errs_closed(tmp: Path) -> bool:
    """A NEW FILE IS INVISIBLE UNTIL STAGED, AND THE GATE MUST ERR CLOSED ON IT.

    `git diff HEAD` cannot see an untracked file, so a command recorded while one exists is
    recorded against a hash that ignores it. Asserted rather than assumed, because the whole
    claim in the docstring rests on which DIRECTION the error goes: staging the file changes
    the hash, so the gate says STALE. Erring closed is the safe direction; if this ever
    reversed, the gate would pass a file nothing had run against.
    """
    d = _repo(tmp, "untracked")
    (d / "new.txt").write_bytes(b"never tested\n")
    _recorded(d)
    before = _status(d, MATCHES)
    git_bytes(d, "add", "new.txt")
    after = _status(d, MATCHES)
    good = before == PASS and after == FAIL
    print(f"  {'OK  ' if good else 'MISS'} {'staging a new file goes STALE':<42} -> "
          f"unstaged {before}, staged {after} (want {PASS} then {FAIL})")
    return good


def _assert_na_can_go_stale(tmp: Path) -> bool:
    """A DECLARED N/A IS A JUDGEMENT ABOUT A CHANGE, so it expires with the change.

    Without this, "verify does not apply" declared over a one-line edit would still stand
    after the branch grew a thousand lines - which is the one route by which a declared N/A
    becomes the silence the rule exists to forbid.
    """
    d = _repo(tmp, "nastale")
    for p in PHASES:
        declare_na(d, _store(d), p, "nothing in this change touches a code path")
    before = _status(d, MATCHES)
    (d / "tracked.txt").write_bytes(b"much more content\n")
    after = _status(d, MATCHES)
    good = before == PASS and after == FAIL
    print(f"  {'OK  ' if good else 'MISS'} {'a declared N/A expires with the change':<42} -> "
          f"{before} then {after} (want {PASS} then {FAIL})")
    return good


def _assert_not_a_repo_is_void(tmp: Path) -> bool:
    """OUTSIDE A REPOSITORY THERE IS NOTHING TO BIND TO, and not every project is a repo.

    VOID with its reason rather than a crash or a pass: a gate that reports clean where it
    cannot look at all is the failure this house names most often.
    """
    d = tmp / "norepo"
    d.mkdir(parents=True, exist_ok=True)
    root, err = repo_root(d)
    good = root is None and bool(err)
    print(f"  {'OK  ' if good else 'MISS'} {'outside a repo -> a reason, not a pass':<42} -> "
          f"{err if err else root}")
    return good


def _assert_store_is_repo_scoped(tmp: Path) -> bool:
    """RESOLVED FROM THE REPOSITORY ROOT, NOT FROM WHEREVER IT WAS INVOKED.

    The defect this forecloses was measured on a sibling checker: the root read from the
    working directory, so a call from another folder reported on a different tree and said
    nothing about it. One repository has one worktree and therefore one evidence store.
    """
    d = _repo(tmp, "scoped")
    sub = d / "deep" / "deeper"
    sub.mkdir(parents=True, exist_ok=True)
    root, err = repo_root(sub)
    good = err is None and root == d.resolve() and _store(root) == _store(d.resolve())
    print(f"  {'OK  ' if good else 'MISS'} {'the store is per REPOSITORY':<42} -> "
          f"{'same root from a subdirectory' if good else f'{root} vs {d}'}")
    return good


def selftest() -> int:
    safe_stdout()
    print("SELFTEST - each check must fire on a bad input AND stay quiet on a good one")
    print()
    tmp = Path(tempfile.mkdtemp(prefix="cycle_evidence_selftest_"))
    try:
        ok, paired, unpaired = run_cases(cases(tmp), tmp, width=42)
        report_pairing(paired, unpaired)
        print()
        ok &= _assert_acceptance_pair(tmp)
        ok &= _assert_command_runs_where_typed(tmp)
        ok &= _assert_payload_flags_do_not_hijack(tmp)
        ok &= _assert_untracked_errs_closed(tmp)
        ok &= _assert_na_can_go_stale(tmp)
        ok &= _assert_not_a_repo_is_void(tmp)
        ok &= _assert_store_is_repo_scoped(tmp)
        ok &= selftest_config(tmp, "cycle", "store", load_config, width=42)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print()
    print("SELFTEST: " + ("PASS" if ok else "FAIL"))
    return RC_OK if ok else RC_FAILED


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
