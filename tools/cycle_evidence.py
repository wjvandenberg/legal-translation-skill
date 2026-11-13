#!/usr/bin/env python3
"""cycle_evidence.py - did VERIFY and TEST actually run, against the content being committed?
CHECKER VERSION 4 (2026-11-12)

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
    uv run python tools/cycle_evidence.py full -- <the full test command>   # v4: clean or FULLY STAGED
    uv run python tools/cycle_evidence.py check-push <commit>   # v2: what a pre-push hook calls
    uv run python tools/cycle_evidence.py status
    uv run python tools/cycle_evidence.py status --passes [--since 2026-11-12T09:30]   # v4
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

THE PUSH RECORD, v2 - THE FULL SUITE ONCE BEFORE A PUSH, NEVER ONCE PER COMMIT. A commit's own
evidence is the test groups covering what it changed; the whole suite is what a PUSH must carry,
because a push is where work leaves the machine. Measured before this existed: a gate that wanted
the full suite as each code commit's test made a session run it once per commit, against the
house rule that it runs once. `full` records a full run, and `check-push` answers for a commit:
  * A FULL RUN IS RECORDED ONLY ON A CLEAN OR FULLY STAGED TREE, AND ONLY IF NOTHING MOVED WHILE
    IT RAN. The record vouches for a commit, so it must be taken on exactly that commit's
    content: a run over unstaged edits - or one that edited the tree while it ran - vouches for
    something no commit holds. FULLY STAGED means nothing unstaged and nothing untracked outside
    the ignore rules (v4; v2 to v3 refused anything staged too), so the index IS the next commit.
  * IT IS KEYED BY THE TREE, NOT THE COMMIT - the tree `git write-tree` names, which on a clean
    tree is HEAD's. A reworded or rebased commit with the same content is the same thing to a
    test; a commit id would make a message edit cost a whole run, and a staged tree has none.
  * A PUSH PASSES ON ITS OWN TREE'S RECORD, OR ON THE NEAREST ANCESTOR'S WHEN EVERY PATH CHANGED
    SINCE ENDS IN .md - documents cannot break a script except by crashing a checker the
    commit's own evidence already ran. The suffix is FIXED, for the reason PHASES is.
  * THE RECORDS SIT IN THE SAME UNCOMMITTABLE STORE, under a key git refuses as a branch name,
    so they can never be mistaken for a branch's verify and test.

ONE RUN FOR TEST AND FULL, v4. A session that pushes ran TEST before its commit and the whole
suite after it, on one tree, because TEST binds the worktree before a commit and `full` took
only a clean tree after one - measured, about ten minutes a pushing session, and the house rule
asks for the full run ONCE. So a full run on a FULLY STAGED tree records TEST too, bound to the
worktree hash like any record - the whole suite being a superset of any covering group, run on
exactly what the commit carries - and its full record under the staged tree, which the commit
made next carries unchanged, so the push finds it. An edit after it goes STALE for both. Not on
a clean tree, which has nothing to commit. VERIFY is untouched: a different question, still run.

THE PASS LEDGER, v4. The records above keep the LAST run per phase, and full runs only when they
passed - so no command could say how many times a session ran its checks. The before-figure that
asked for this took a transcript to count it: 39 runs, ten of them whole repeats, a third of the
session's wall. Every run this script wraps - verify, test, full; red or green; recorded or not -
is appended under a key git refuses as a branch, with its phase, start, seconds, exit code,
whether it was recorded and the content hash's first 12, LEDGER_CAP per branch. `status --passes`
prints them and, per phase, runs and WHOLE REPEATS - every run of a phase after its first -
`--since` counting one session on a branch that outlives it. A declared N/A and a refused full
run ran nothing, so neither is a pass. It COUNTS and never refuses: a second whole pass is
sometimes what a real red needs, so a hook refusing it was declined, and the count is the control.

  CHECKED HERE    that a command was recorded for verify and for test, or one of them
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
check-push: 0 = the push may go, 1 = refused, 2 = not a commit, so nothing was decided.
full: 0 = recorded; the command's own exit code if it failed; 2 = nothing recorded though the
command may have passed - the tree was not clean or fully staged before, or the run changed it.
status --passes: 0 = printed; 2 = an argument it does not take, or a --since that is no date.
"""
from __future__ import annotations

import atexit
import hashlib
import json
import os
import re
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

#: v2. The store key for full runs - one git refuses as a branch name, ':' being barred from a
#: ref, so the push records can never collide with a branch's verify and test.
FULL_KEY = "full-runs:"

#: v2. What counts as a document for a push after the last full run. FIXED, for the reason
#: PHASES is: a project able to widen it would widen it to whatever was failing.
DOC_SUFFIXES = (".md",)

#: v2. How far back a push looks for the nearest full run before it refuses.
SEARCH_DEPTH = 200

#: v4. The store key for the pass ledger - like FULL_KEY, a name git refuses as a branch, so the
#: ledger can never collide with a branch's verify and test.
LEDGER_KEY = "passes:"

#: v4. How many runs the ledger keeps PER BRANCH, oldest dropped first. The session whose count
#: asked for the ledger ran 39 checks in four and a half hours, so this keeps several sessions
#: and still leaves the store a small file read on every commit.
LEDGER_CAP = 200

#: v4. The phases the ledger counts - the two of PHASES and the push record's full run.
LEDGER_PHASES = PHASES + ("full",)

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


def ledger_entry(phase: str, start: str, seconds: float, rc: int, recorded: bool, content: str):
    """One run as the ledger keeps it: no command text and no path, so it can never carry a name."""
    return {"phase": phase, "start": start, "seconds": round(seconds, 1), "exit": rc,
            "recorded": recorded, "hash": (content or "")[:12]}


def ledger_append(d, name: str, entry) -> None:
    """v4. Append one run to branch `name`'s ledger in the loaded store `d`, keeping the last
    LEDGER_CAP - THE PASS LEDGER, in the module docstring.

    A RUN THAT FAILED GOES IN TOO, and that is the half the phase records could never show: they
    keep a phase's LAST passing run, so a gate run five times to get one green left one record."""
    runs = d.setdefault(LEDGER_KEY, {}).setdefault(name, [])
    runs.append(entry)
    del runs[:-LEDGER_CAP]


def record(root: Path, store: Path, phase: str, cmd, cwd: Path | None = None) -> int:
    """Run the command, and record it ONLY if it exits 0.

    A FAILING COMMAND IS NOT EVIDENCE, and saying so is half of what this file is for. The
    record is written after the run, from the exit code, so there is no path on which a
    failure leaves something behind that a later `check` would accept. (v4: it leaves a LEDGER
    line - a pass counted, never a pass vouched for - and `check` does not read the ledger.)

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
    start, t0 = time.strftime("%Y-%m-%dT%H:%M:%S"), time.monotonic()
    rc = subprocess.run(cmd, cwd=str(where), env=env, stdin=subprocess.DEVNULL).returncode
    seconds, content, name = time.monotonic() - t0, worktree_hash(root), branch(root)
    d = load(store)
    if rc != 0:
        # v4: the LEDGER keeps the run; the phase record does not, so `check` still sees nothing.
        ledger_append(d, name, ledger_entry(phase, start, seconds, rc, False, content))
        save(store, d)
        print(f"  [{phase}] exit {rc} - NOT recorded. A failing command is not evidence.")
        return rc
    d.setdefault(name, {})[phase] = {
        "command": " ".join(cmd),
        # THE DIRECTORY IS PART OF THE RECORD. The same command name means different things
        # in two folders, and `status` is read by whoever has to believe the evidence.
        "cwd": str(where),
        "exit": rc,
        "content": content,
        "when": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "declared_na": False,
    }
    ledger_append(d, name, ledger_entry(phase, start, seconds, rc, True, content))
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


# --------------------------------------------------------------------------- the push record, v2

def tree_of(root: Path, rev: str):
    """The tree id of the commit `rev` names, or None if it names no commit. A name beginning
    with '-' is refused rather than handed to git, which would read it as an option."""
    if not rev or rev.startswith("-"):
        return None
    rc, out = git_text(root, "rev-parse", "--verify", "--quiet", f"{rev}^{{commit}}")
    if rc != 0 or not out:
        return None
    rc, tree = git_text(root, "rev-parse", f"{out}^{{tree}}")
    return tree if rc == 0 and tree else None


def not_fully_staged(root: Path):
    """v4. None if the worktree equals the INDEX and nothing is untracked outside the ignore
    rules - a clean tree, or one whose every change is staged - else why not, as a count.

    PORCELAIN READ AS BYTES, NEVER THROUGH git_text: that strips the output, and the leading
    space of the first line IS the answer - ' M' is unstaged, 'M ' staged. Column two names the
    worktree against the index, so anything there but a space, or an untracked '??', means the
    index - what a commit would carry - is not what the run would test."""
    r = git_bytes(root, "status", "--porcelain")
    if r.returncode != 0:
        return f"git status exited {r.returncode}, so the tree could not be read"
    lines = [ln for ln in r.stdout.decode("utf-8", "replace").splitlines() if ln.strip()]
    loose = [ln for ln in lines if ln.startswith("??") or ln[1:2] != " "]
    return (f"{len(loose)} path(s) unstaged, partly staged or untracked - a full run tests what a "
            f"commit would carry, so stage everything or stash it") if loose else None


def staged_tree(root: Path):
    """v4. The tree the next commit would carry - `git write-tree` of the index - or None.
    On a clean tree it is HEAD's own tree, so one name serves both."""
    rc, out = git_text(root, "write-tree")
    return out if rc == 0 and out else None


def record_full(root: Path, store: Path, cmd, cwd: Path | None = None) -> int:
    """Run the FULL suite and record it against the TREE THE NEXT COMMIT WOULD CARRY - only on a
    FULLY STAGED tree, only on exit 0, and only if the index, the worktree and HEAD are all
    unmoved afterwards (THE PUSH RECORD and ONE RUN FOR TEST AND FULL, above).

    THE AFTER-CHECK IS NOT BELT-AND-BRACES. A suite that writes a tracked file while it runs - a
    regenerated fixture, a rewritten config - passes against content that is in no commit, and
    a record taken then would vouch for a tree it never saw. v4 adds the index to it: a run that
    STAGES something leaves nothing unstaged, and only the tree id shows that it moved.
    """
    why = not_fully_staged(root)
    if why:
        print(f"  [full] REFUSED - {why}. A full run vouches for a commit, so it runs on exactly "
              f"a commit's content. Nothing was run or recorded.")
        return RC_COULD_NOT_RUN
    if not tree_of(root, "HEAD"):
        print("  [full] REFUSED - there is no commit yet, so there is no tree to vouch for.")
        return RC_COULD_NOT_RUN
    tree = staged_tree(root)
    if not tree:
        print("  [full] REFUSED - git write-tree named no tree, so there is nothing to vouch for.")
        return RC_COULD_NOT_RUN
    head = git_text(root, "rev-parse", "HEAD")[1]
    staged = tree != tree_of(root, "HEAD")
    where = Path(cwd) if cwd else root
    print(f"  [full] {' '.join(cmd)}")
    print(f"  [full] in {where}, on tree {tree[:12]}")
    sys.stdout.flush()
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    start, t0 = time.strftime("%Y-%m-%dT%H:%M:%S"), time.monotonic()
    rc = subprocess.run(cmd, cwd=str(where), env=env, stdin=subprocess.DEVNULL).returncode
    seconds, name = time.monotonic() - t0, branch(root)
    d = load(store)
    if rc != 0:
        ledger_append(d, name, ledger_entry("full", start, seconds, rc, False, tree))
        save(store, d)
        print(f"  [full] exit {rc} - NOT recorded. A failing command is not evidence.")
        return rc
    after = not_fully_staged(root)
    moved = ("HEAD moved" if git_text(root, "rev-parse", "HEAD")[1] != head else
             "the index moved" if staged_tree(root) != tree else None)
    if after or moved:
        ledger_append(d, name, ledger_entry("full", start, seconds, rc, False, tree))
        save(store, d)
        # 2, NOT 1: the suite PASSED, and an exit 1 would read as a failing suite and send
        # someone hunting a red test that does not exist.
        print(f"  [full] exit 0 but NOT recorded - the run changed what it was testing "
              f"({after or moved}), so it vouches for no commit.")
        return RC_COULD_NOT_RUN
    now = time.strftime("%Y-%m-%dT%H:%M:%S")
    d.setdefault(FULL_KEY, {})[tree] = {
        # A STAGED run has no commit yet: it names the one it was staged on, and the TREE is
        # the key a push is checked by, so the commit made next finds this record unchanged.
        "commit": None if staged else head, "staged_on": head if staged else None,
        "command": " ".join(cmd), "cwd": str(where), "exit": rc, "when": now,
    }
    if staged:
        # ONE RUN FOR TEST AND FULL. The whole suite is a superset of any covering group, run
        # on exactly the content the commit carries, so it IS the commit's TEST - bound to the
        # worktree hash like every other record, so an edit after it goes STALE as any would.
        # NOT on a clean tree: there is nothing to commit, and a TEST for it would only replace
        # the record a branch already has.
        d.setdefault(name, {})["test"] = {
            "command": " ".join(cmd), "cwd": str(where), "exit": rc,
            "content": worktree_hash(root), "when": now, "declared_na": False,
            "from_full": tree,
        }
    ledger_append(d, name, ledger_entry("full", start, seconds, rc, True, tree))
    save(store, d)
    print(f"  [full] exit 0 - recorded for tree {tree[:12]} "
          + (f"(staged on {head[:12]}) - and as TEST for this content, so the commit needs no "
             f"separate TEST run." if staged else f"(commit {head[:12]})."))
    return RC_OK


def check_push(root: Path, store: Path, rev: str):
    """(True, why) the push may go · (False, why) it is refused · (None, why) no commit named.

    THE NEAREST RECORDED ANCESTOR, NOT ANY ONE: the question is what changed since the content a
    full run last saw, and an older run saw less of it. The NET diff from there to the pushed
    commit decides, because that is exactly what the push carries beyond what was tested.
    """
    tree = tree_of(root, rev)
    if not tree:
        return None, f"'{rev}' names no commit here, so nothing was decided"
    runs = load(store).get(FULL_KEY, {})
    if tree in runs:
        return True, f"a full run passed on exactly this content ({runs[tree]['when']})"
    # ONE git call for the whole walk, commit and tree per line - not one process per ancestor.
    rc, out = git_text(root, "log", f"--max-count={SEARCH_DEPTH}", "--format=%H %T", rev)
    if rc != 0:
        return False, f"git could not walk the history (exit {rc}), so no earlier full run can be found"
    for c, t in (ln.split() for ln in out.splitlines()[1:] if ln.strip()):
        if t not in runs:
            continue
        # --no-renames: with rename detection a script renamed to a .md path lists only the new
        # name, and the deletion of the script would pass as a documents-only change.
        rc2, changed = git_text(root, "-c", "core.quotePath=false", "diff", "--no-renames",
                                "--name-only", c, rev)
        if rc2 != 0:
            return False, f"git diff exited {rc2}, so what changed since the last full run is unknown"
        paths = [p for p in changed.splitlines() if p]
        code = [p for p in paths if not p.lower().endswith(DOC_SUFFIXES)]
        if not code:
            return True, (f"the last full run passed at {c[:12]}; since then only {len(paths)} "
                          f"document(s) changed")
        return False, (f"the last full run passed at {c[:12]}, and {len(code)} non-document "
                       f"path(s) changed since - run the full suite on this commit")
    return False, (f"no full run is recorded on this commit or its last {SEARCH_DEPTH} "
                   f"ancestors - run the full suite on this commit")


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


#: v4. What `status --passes --since` accepts: an ISO date, to the second at most. Compared as
#: TEXT against each run's start, which is the same format, so a prefix such as a bare date works.
SINCE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}(T\d{2}(:\d{2}(:\d{2})?)?)?$")


def _plural(n: int, word: str) -> str:
    return f"{n} {word}{'' if n == 1 else 's'}"


def tally(runs, repeats: int) -> str:
    """One phase's line: runs, whole repeats, red, recorded, seconds."""
    red = sum(1 for e in runs if e.get("exit") != 0)
    kept = sum(1 for e in runs if e.get("recorded"))
    secs = sum(e.get("seconds", 0) for e in runs)
    return (f"{_plural(len(runs), 'run')}, {_plural(repeats, 'repeat')}, {red} red, "
            f"{kept} recorded, {secs:.1f} s")


def print_passes(root: Path, store: Path, since: str | None) -> None:
    """v4. `status --passes`: every run the ledger kept for this branch, then each phase's tally.

    A REPEAT IS EVERY WHOLE RUN OF A PHASE AFTER ITS FIRST, red or green, on any content - the
    measure the before-figure used, and the one HEAVY CHECKS ONCE A SESSION is about. Whether a
    repeat was NEEDED is a judgement this cannot make; it makes the count impossible to miss.
    `n of N` is printed against everything kept, so a --since filter never hides runs silently."""
    name = branch(root)
    kept = load(store).get(LEDGER_KEY, {}).get(name, [])
    shown = [e for e in kept if not since or e.get("start", "") >= since]
    print(f"PASSES - branch {name or '(detached)'} - store {store}")
    print(f"  {len(shown)} of {len(kept)} runs in the ledger for this branch"
          f"{f' since {since}' if since else ''} - it keeps the last {LEDGER_CAP}")
    for e in shown:
        print(f"  {e.get('start', '?'):<19}  {e.get('phase', '?').upper():<6} "
              f"{e.get('seconds', 0):>8.1f} s  exit {e.get('exit', '?')!s:<4} "
              f"{'recorded' if e.get('recorded') else 'NOT recorded':<13} {e.get('hash', '')}")
    print("  per phase - a REPEAT is every whole run of a phase after its first:")
    total = 0
    for p in LEDGER_PHASES:
        mine = [e for e in shown if e.get("phase") == p]
        total += max(0, len(mine) - 1)
        print(f"  {p.upper():<7} {tally(mine, max(0, len(mine) - 1))}")
    print(f"  {'ALL':<7} {tally(shown, total)}")


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
        if rest and rest[0] == "--passes":
            since = None
            if len(rest) == 3 and rest[1] == "--since" and SINCE_RE.match(rest[2]):
                since = rest[2]
            elif len(rest) != 1:
                print("  status --passes takes nothing, or --since YYYY-MM-DD[THH[:MM[:SS]]]")
                return RC_COULD_NOT_RUN
            print_passes(root, store, since)
            return RC_OK
        print(f"root  {root}")
        print(f"store {store}")
        print(json.dumps(load(store).get(branch(root), {}), indent=1))
        print(f"full runs recorded: {len(load(store).get(FULL_KEY, {}))}")
        print(f"runs in the pass ledger on this branch: "
              f"{len(load(store).get(LEDGER_KEY, {}).get(branch(root), []))} - status --passes lists them")
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

    if cmd == "full":
        if rest and rest[0] == "--":
            rest = rest[1:]
        if not rest:
            print("  give the full test command after --")
            return RC_COULD_NOT_RUN
        return record_full(root, store, rest, cwd=Path.cwd())

    if cmd == "check-push":
        if len(rest) != 1:
            print("  check-push needs exactly one commit")
            return RC_COULD_NOT_RUN
        ok, why = check_push(root, store, rest[0])
        print(f"  PUSH {'ALLOWED' if ok else 'REFUSED' if ok is False else 'VOID'} - {why}")
        return RC_OK if ok else RC_FAILED if ok is False else RC_COULD_NOT_RUN

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

def _fixture_config(git_dir: Path, settings: dict) -> None:
    """Write ONE FIXTURE repository's settings into its own config FILE, without a git process.

    Each `git config` call is a process of its own - measured, three per fixture, 123 in this
    selftest - and after every commit git starts `git maintenance run --auto`, which in a
    throwaway repository of a few objects finds nothing to do - 48. So both go into the config
    file init made, and the repository ends as the calls left it, which is all a check reads.
    NOT BY ENVIRONMENT: git_bytes is shared with the checks under test, whose own git calls must
    not change, and a case commits again later, so the identity has to live in the repository.
    Every value is quoted, so a space, `#` or `;` in it stays part of it. Raises if init made no
    config, so a fixture that did not set up is named rather than every case after it failing
    for a reason nobody gave."""
    cfg = git_dir / "config"
    if not cfg.is_file():
        raise FileNotFoundError(f"no git config at {cfg} - the fixture's init did not make one")
    sections: dict = {}
    for key, value in settings.items():
        section, name = key.split(".")
        quoted = value.replace("\\", "\\\\").replace('"', '\\"')
        sections.setdefault(section, []).append(f'\t{name} = "{quoted}"\n')
    block = "".join(f"[{s}]\n" + "".join(lines) for s, lines in sections.items())
    body = cfg.read_bytes()
    cfg.write_bytes(body + (b"" if body.endswith(b"\n") else b"\n") + block.encode("utf-8"))


_BASE: list = []          # the base repository's .git, once _base_git() has built it


def _base_git() -> Path:
    """THE ONE `git init` A SELFTEST RUN MAKES: a base repository, initialised and configured
    once, whose `.git` every fixture copies. Measured, each of 41 fixtures here started its own
    `init` for an empty repository that is the same every time. Built on first use in a folder
    of its own, OUTSIDE the selftest's, so no case sees it, and removed at exit. A copy is what
    `init` gave - the same files, config and branch, made on the same filesystem - and each
    fixture still runs its own `add` and `commit`, so every commit is made as before."""
    if not _BASE:
        home = Path(tempfile.mkdtemp(prefix="cycle_evidence_base_"))
        atexit.register(shutil.rmtree, home, True)
        git_bytes(home, "init", "-q")
        _fixture_config(home / ".git", {"maintenance.auto": "false", "user.email": "noreply@example.invalid",
                                        "user.name": "selftest", "commit.gpgsign": "false"})
        _BASE.append(home / ".git")
    return _BASE[0]


def _repo(tmp: Path, name: str, ignore: str = "temp/\n") -> Path:
    """A real, tiny git repository. REAL because every claim here is about git's answers -
    a stub would test the stub. Identity is set locally so a machine with no global config
    can still commit, and it is a noreply address for the reason this house always gives.
    Automatic housekeeping is off, and both go in by file - _fixture_config says why. The
    empty repository is a copy of one built once - _base_git says why."""
    d = tmp / name
    d.mkdir(parents=True, exist_ok=True)
    shutil.copytree(_base_git(), d / ".git")
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


def _full_count(d: Path) -> int:
    return len(load(_store(d)).get(FULL_KEY, {}))


def _has_full(d: Path) -> str:
    """PASS if a full run was recorded, FAIL if not - read off the store, for _has_record's reason."""
    return PASS if _full_count(d) else FAIL


def _push(d: Path, rev: str = "HEAD") -> str:
    ok, _why = check_push(d, _store(d), rev)
    return PASS if ok else FAIL if ok is False else VOID


def _commit(d: Path, name: str, body: bytes, *extra: str) -> None:
    (d / name).write_bytes(body)
    git_bytes(d, "add", "-A")
    git_bytes(d, "commit", "-q", *extra, "-m", "next")


#: v4. The file the CLI cases run - this one, unless a red-first or mutant harness points it at
#: a copy, which is the only reason it is a name rather than __file__ inline.
_SCRIPT = Path(__file__).resolve()


def _cli(d: Path, *a):
    """v4. THIS SCRIPT RUN AS A PERSON OR A HOOK RUNS IT - its own process, in the fixture - so a
    case reads what `status --passes` PRINTS, the only thing anyone counting passes ever sees."""
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    r = subprocess.run([sys.executable, str(_SCRIPT), *a], cwd=str(d), capture_output=True,
                       stdin=subprocess.DEVNULL, env=env, timeout=120)
    return r.returncode, r.stdout.decode("utf-8", "replace")


_SUMMARY_RE = re.compile(r"^\s*(VERIFY|TEST|FULL|ALL)\s+(\d+ runs?, \d+ repeats?, \d+ red, \d+ recorded)",
                         re.M)
_KEPT_RE = re.compile(r"(\d+ of \d+) runs in the ledger")


def _passes_arg(arg):
    """A builder returns the fixture, or (fixture, the extra arguments `status --passes` takes)."""
    return arg if isinstance(arg, tuple) else (arg, [])


def _summary(phase: str):
    """v4. The per-phase line `status --passes` prints for `phase`: runs, repeats, red, recorded."""
    def probe(arg):
        d, extra = _passes_arg(arg)
        rc, out = _cli(d, "status", "--passes", *extra)
        for m in _SUMMARY_RE.finditer(out):
            if m.group(1) == phase.upper():
                return m.group(2)
        return f"no {phase.upper()} summary line (exit {rc})"
    return probe


def _kept(arg) -> str:
    """v4. The `n of N` `status --passes` prints - shown against kept, so a filter is never silent."""
    d, extra = _passes_arg(arg)
    rc, out = _cli(d, "status", "--passes", *extra)
    m = _KEPT_RE.search(out)
    return m.group(1) if m else f"no 'n of N' line (exit {rc})"


def _passes_exit(arg) -> str:
    d, extra = _passes_arg(arg)
    return f"exit {_cli(d, 'status', '--passes', *extra)[0]}"


def _staged(d: Path, name: str = "tracked.txt", body: bytes = b"content S, staged\n") -> Path:
    """v4. A change written and STAGED, not committed - the state a pre-commit gate sees."""
    (d / name).write_bytes(body)
    git_bytes(d, "add", "--", name)
    return d


def _recorded_one(d: Path, phase: str) -> None:
    """Evidence for ONE phase against the content now - _recorded's twin, for a case that must
    leave the other phase to the run under test."""
    s = _store(d)
    rec = load(s)
    rec.setdefault(branch(d), {})[phase] = {
        "command": f"echo {phase}", "exit": 0, "content": worktree_hash(d),
        "when": "2026-01-01T00:00:00", "declared_na": False}
    save(s, rec)


def _phase_state(d: Path, phase: str) -> str:
    """MISSING, STALE or ok - print_phases' three words, off the store, for one phase."""
    e = load(_store(d)).get(branch(d), {}).get(phase)
    if not e:
        return "MISSING"
    return "ok" if e["content"] == worktree_hash(d) else "STALE"


def _ledger_span(d) -> str:
    """v4. How many runs one branch's ledger kept, and which is the oldest - read off a store dict."""
    runs = d.get(LEDGER_KEY, {}).get("b", [])
    return f"{len(runs)} kept, oldest {runs[0].get('start', '?') if runs else '-'}"


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

    # ---- v2: the push record. Every "records nothing" case is PAIRED with one that records,
    #      because a version that records nothing passes each of them by doing nothing.
    ok_cmd = [sys.executable, "-c", "pass"]

    def full_clean(_):
        d = fresh()
        record_full(d, _store(d), ok_cmd)
        return d

    def full_dirty(_):
        d = fresh()
        (d / "tracked.txt").write_bytes(b"edited, not committed\n")
        record_full(d, _store(d), ok_cmd)
        return d

    # THE BEFORE-CHECK HAS A CASE OF ITS OWN because the after-check alone also refuses to RECORD
    # on a dirty tree - measured by a mutant that removed it and stayed green. What only the
    # before-check buys is that the suite never STARTS, so the case reads a marker the command
    # leaves in an ignored folder: absent on a dirty tree, present on a clean one.
    marker_cmd = [sys.executable, "-c",
                  "import pathlib; p = pathlib.Path('temp'); p.mkdir(exist_ok=True); "
                  "(p / 'ran').write_bytes(b'1')"]

    def marker_dirty(_):
        d = fresh()
        (d / "tracked.txt").write_bytes(b"edited, not committed\n")
        record_full(d, _store(d), marker_cmd)
        return d

    def marker_clean(_):
        d = fresh()
        record_full(d, _store(d), marker_cmd)
        return d

    def full_untracked(_):
        d = fresh()
        (d / "new.txt").write_bytes(b"never added\n")
        record_full(d, _store(d), ok_cmd)
        return d

    def full_failing(_):
        d = fresh()
        record_full(d, _store(d), [sys.executable, "-c", "raise SystemExit(3)"])
        return d

    def full_edits_tree(_):
        d = fresh()
        record_full(d, _store(d), [sys.executable, "-c",
                                   "open('tracked.txt', 'wb').write(b'written by the run\\n')"])
        return d

    def push_code_after(_):
        d = full_clean(_)
        _commit(d, "tracked.txt", b"content B\n")
        return d

    def push_docs_after(_):
        d = full_clean(_)
        _commit(d, "notes.md", b"# notes\n")
        return d

    def push_renamed_to_md(_):
        """A non-document RENAMED to a .md name: with rename detection only the new name is
        listed, and the deletion would pass as documents-only - the code review's catch."""
        d = full_clean(_)
        git_bytes(d, "mv", "tracked.txt", "tracked.md")
        git_bytes(d, "commit", "-q", "-m", "renamed")
        return d

    def push_content_amend(_):
        d = full_clean(_)
        _commit(d, "tracked.txt", b"amended content\n", "--amend")
        return d

    def push_message_amend(_):
        d = full_clean(_)
        git_bytes(d, "commit", "-q", "--amend", "-m", "reworded only")
        return d

    # ---- v4: the pass ledger. Every run goes through the REAL entry point, _cli, because what
    #      is under test is what a person reads, and a case reading the store would test the store.
    pass_cmd = ("--", sys.executable, "-c", "pass")
    red_cmd = ("--", sys.executable, "-c", "raise SystemExit(1)")

    def ledger_two(_):
        """THE CASE THE PLAN NAMES: two runs of one phase, one red - 2 runs, 1 repeat."""
        d = fresh()
        _cli(d, "verify", *red_cmd)
        _cli(d, "verify", *pass_cmd)
        return d

    def ledger_one(_):
        d = fresh()
        _cli(d, "verify", *pass_cmd)
        return d

    def ledger_since(_):
        """Three runs, the first moved into the past, counted from a time after it - a SESSION
        on a branch that outlives it, which is every session that commits straight to main."""
        d = fresh()
        for _n in range(3):
            _cli(d, "test", *pass_cmd)
        s = _store(d)
        rec = load(s)
        runs = rec.get(LEDGER_KEY, {}).get(branch(d), [])
        if runs:
            runs[0]["start"] = "2000-01-01T00:00:00"
            save(s, rec)
        return d, ["--since", "2001-01-01"]

    def ledger_all(_):
        d = fresh()
        for _n in range(3):
            _cli(d, "test", *pass_cmd)
        return d, []

    def since_malformed(_):
        return fresh(), ["--since", "yesterday"]

    def since_iso(_):
        return fresh(), ["--since", "2026-01-01T09:30"]

    def ledger_over_cap(_):
        d: dict = {}
        for n in range(1, LEDGER_CAP + 6):
            ledger_append(d, "b", ledger_entry("test", f"#{n}", 0.1, 0, True, "0" * 64))
        return d

    def ledger_under_cap(_):
        d: dict = {}
        for n in range(1, 4):
            ledger_append(d, "b", ledger_entry("test", f"#{n}", 0.1, 0, True, "0" * 64))
        return d

    def ledger_full_refused(_):
        """A refused full run never starts, so it is no run - only what RAN is a pass."""
        d = fresh()
        (d / "tracked.txt").write_bytes(b"edited, not committed\n")
        _cli(d, "full", *pass_cmd)
        return d

    def ledger_full_ran(_):
        d = fresh()
        _cli(d, "full", *pass_cmd)
        return d

    # ---- v4: ONE RUN FOR TEST AND FULL - a full run on a FULLY STAGED tree carries the commit's
    #      TEST and the push's full record. Each "refused" arm is PAIRED with staged_full, which
    #      records, because a version that refuses every staged tree passes each of them alone.
    def staged_full(_):
        d = _staged(fresh())
        record_full(d, _store(d), ok_cmd)
        return d

    def staged_full_fails(_):
        d = _staged(fresh())
        record_full(d, _store(d), [sys.executable, "-c", "raise SystemExit(3)"])
        return d

    def staged_verify_only(_):
        d = _staged(fresh())
        _recorded_one(d, "verify")
        return d

    def staged_verify_full(_):
        d = staged_full(_)
        _recorded_one(d, "verify")
        return d

    def staged_full_commit(_):
        d = staged_full(_)
        git_bytes(d, "commit", "-q", "-m", "next")
        return d

    def staged_full_edit_commit(_):
        """Edited AND staged after the run, then committed - the push carries a tree no run saw."""
        d = staged_full(_)
        _staged(d, body=b"edited after the run\n")
        git_bytes(d, "commit", "-q", "-m", "next")
        return d

    def staged_full_then_edit(_):
        d = staged_full(_)
        (d / "tracked.txt").write_bytes(b"edited after the run\n")
        return d

    def staged_untracked(_):
        d = _staged(fresh())
        (d / "new.txt").write_bytes(b"never added\n")
        record_full(d, _store(d), ok_cmd)
        return d

    def staged_then_edited(_):
        """Staged, then edited again - partly staged, so the index is not what was tested."""
        d = _staged(fresh())
        (d / "tracked.txt").write_bytes(b"edited again, not staged\n")
        record_full(d, _store(d), ok_cmd)
        return d

    def staged_run_stages(_):
        """A run that stages more while it runs: nothing unstaged after, but the index moved."""
        d = _staged(fresh())
        record_full(d, _store(d), [sys.executable, "-c",
                                   "import pathlib, subprocess; pathlib.Path('more.txt').write_bytes(b'x\\n'); "
                                   "subprocess.run(['git', 'add', 'more.txt'])"])
        return d

    return [
        Case("v2: full on a MODIFIED tree", _has_full, full_dirty, full_clean,
             want=FAIL, good_want=PASS),
        Case("v2: a dirty tree never STARTS the run",
             lambda d: PASS if (d / "temp" / "ran").exists() else FAIL, marker_dirty, marker_clean,
             want=FAIL, good_want=PASS),
        Case("v2: full with an UNTRACKED file", _has_full, full_untracked, full_clean,
             want=FAIL, good_want=PASS),
        Case("v2: a FAILING full run", _has_full, full_failing, full_clean,
             want=FAIL, good_want=PASS),
        Case("v2: a run that EDITS the tree", _has_full, full_edits_tree, full_clean,
             want=FAIL, good_want=PASS),
        Case("v2: a push with no full run", _push, nothing, full_clean,
             want=FAIL, good_want=PASS),
        Case("v2: CODE after the run, not DOCS", _push, push_code_after, push_docs_after,
             want=FAIL, good_want=PASS),
        Case("v2: a RENAME to .md is not docs-only", _push, push_renamed_to_md, push_docs_after,
             want=FAIL, good_want=PASS),
        Case("v2: by TREE - content, not message", _push, push_content_amend, push_message_amend,
             want=FAIL, good_want=PASS),
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
        Case("v4: two runs, one red -> 2 runs, 1 repeat", _summary("verify"), ledger_two, ledger_one,
             want="2 runs, 1 repeat, 1 red, 1 recorded", good_want="1 run, 0 repeats, 0 red, 1 recorded"),
        Case("v4: --since counts a session, n of N", _kept, ledger_since, ledger_all,
             want="2 of 3", good_want="3 of 3"),
        Case("v4: a malformed --since is refused", _passes_exit, since_malformed, since_iso,
             want="exit 2", good_want="exit 0"),
        Case("v4: the ledger keeps the last CAP", _ledger_span, ledger_over_cap, ledger_under_cap,
             want=f"{LEDGER_CAP} kept, oldest #6", good_want="3 kept, oldest #1"),
        Case("v4: a full run is a pass, a refusal not", _summary("full"),
             ledger_full_refused, ledger_full_ran,
             want="0 runs, 0 repeats, 0 red, 0 recorded", good_want="1 run, 0 repeats, 0 red, 1 recorded"),
        Case("v4: a STAGED tree's full run records TEST", lambda d: _has_record(d, "test"),
             staged_full_fails, staged_full, want=FAIL, good_want=PASS),
        Case("v4: ...its commit needs no TEST run", lambda d: check(d, _store(d)).verdict(),
             staged_verify_only, staged_verify_full, want=FAIL, good_want=PASS),
        Case("v4: ...its push passes on the same record", _push,
             staged_full_edit_commit, staged_full_commit, want=FAIL, good_want=PASS),
        Case("v4: ...an edit after it is STALE", lambda d: _phase_state(d, "test"),
             staged_full_then_edit, staged_full, want="STALE", good_want="ok"),
        Case("v4: staged, an UNTRACKED file refuses", _has_full, staged_untracked, staged_full,
             want=FAIL, good_want=PASS),
        Case("v4: staged, an UNSTAGED edit refuses", _has_full, staged_then_edited, staged_full,
             want=FAIL, good_want=PASS),
        Case("v4: a run that STAGES more is no record", _has_full, staged_run_stages, staged_full,
             want=FAIL, good_want=PASS),
        Case("v4: a CLEAN tree's full run is no TEST", lambda d: _has_record(d, "test"),
             full_clean, staged_full, want=FAIL, good_want=PASS),
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


def _assert_full_key_is_no_branch(tmp: Path) -> bool:
    """THE RESERVED KEY'S CLAIM, ASKED OF GIT rather than asserted in a comment: git must refuse
    it as a branch name, and accept an ordinary one - the control that the question works."""
    d = _repo(tmp, "refname")
    bad = git_bytes(d, "check-ref-format", "--branch", FULL_KEY).returncode
    ctl = git_bytes(d, "check-ref-format", "--branch", "main").returncode
    good = bad != 0 and ctl == 0
    print(f"  {'OK  ' if good else 'MISS'} {'v2: the full-run key is no branch name':<42} -> "
          f"git refuses it: exit {bad}; control 'main': exit {ctl}")
    return good


def _assert_push_cli(tmp: Path) -> bool:
    """THE ENTRY POINT A HOOK CALLS, run as a hook runs it: 1 for a commit with no full run, 0
    once one is recorded, 2 for a name that is no commit - three codes a shell can branch on."""
    d = _repo(tmp, "pushcli")
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")

    def run(*a):
        return subprocess.run([sys.executable, str(Path(__file__).resolve()), *a], cwd=str(d),
                              capture_output=True, stdin=subprocess.DEVNULL, env=env,
                              timeout=120).returncode
    got = (run("check-push", "HEAD"), run("full", "--", sys.executable, "-c", "pass"),
           run("check-push", "HEAD"), run("check-push", "no-such-commit"))
    good = got == (1, 0, 0, 2)
    print(f"  {'OK  ' if good else 'MISS'} {'v2: check-push exit codes, real entry':<42} -> "
          f"none, full, recorded, bogus: {got} (want (1, 0, 0, 2))")
    return good


def _assert_full_runs_leave_check_alone(tmp: Path) -> bool:
    """A FULL-RUN RECORD CHANGES NOTHING THE PRE-COMMIT CHECK SAYS - v2's must-not, measured."""
    d = _repo(tmp, "coexist")
    _recorded(d)
    before = check(d, _store(d)).verdict()
    record_full(d, _store(d), [sys.executable, "-c", "pass"])
    after = check(d, _store(d)).verdict()
    good = before == after == PASS and _full_count(d) == 1
    print(f"  {'OK  ' if good else 'MISS'} {'v2: a full record leaves check alone':<42} -> "
          f"check {before} before, {after} after, {_full_count(d)} full record(s)")
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
        ok &= _assert_full_key_is_no_branch(tmp)
        ok &= _assert_push_cli(tmp)
        ok &= _assert_full_runs_leave_check_alone(tmp)
        ok &= selftest_config(tmp, "cycle", "store", load_config, width=42)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print()
    print("SELFTEST: " + ("PASS" if ok else "FAIL"))
    return RC_OK if ok else RC_FAILED


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
