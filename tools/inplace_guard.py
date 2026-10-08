#!/usr/bin/env python3
"""inplace_guard.py - the one sanctioned way for a tool or a test to change a file in the
repository and put it back (register I-37, 2026-10-08).

WHY IT EXISTS. Eleven tools and tests proved a check could fail by writing a planted defect
into a REAL tracked file - the build plan, the charter, a shipped skill file, the decisions log
with a real corpus descriptor appended - and restoring it in a `finally`. A killed process
never reaches its `finally`: a run ended between the write and the restore leaves the defect
on disk, silently, a commit away from being carried. Twice in one day a planted defect was
found sitting in PLAN-2-step-b.md. And a second run started while the first held its defect
read the defect AS THE ORIGINAL and "restored" it, printing that the file was byte-identical
- no kill needed at all.

WHAT IT DOES. Before it touches the file it writes a RECORD - what is about to change, the
original's bytes and hash, the bytes it will plant, and its own process id - into gitignored
temp/.inplace-journal/. Then it plants, the caller probes, and it puts the original back and
CHECKS the hash before deleting the record. A run killed in between leaves the record, and:
  * the next guarded change settles it - putting the original back ONLY if the file still
    holds exactly the planted bytes, and REFUSING, naming the saved original, if anything else
    has changed it since: a human edit is never clobbered;
  * a record whose process is still ALIVE is never settled - two runs changing one file at
    once is refused, which is the overlap that baked a defect in without any kill;
  * tools/precommit_gate.py refuses a commit while any record exists.

    with mutated(path, new_bytes): ...   # the file holds new_bytes inside the block
    with planted(path, data): ...        # a file that must NOT exist before; removed after
    with staged(path): ...               # git add -f inside the block; unstaged after
    with protecting(path): ...           # something you run may change it; it ends as it began

    uv run python tools/inplace_guard.py --status      # unfinished records; exit 1 if any
    uv run python tools/inplace_guard.py --recover     # settle every SAFE one; exit 1 if any remain
    uv run python tools/inplace_guard.py --restore ID  # a decision: put that original back
    uv run python tools/inplace_guard.py --discard ID  # a decision: drop the record, touch nothing
    uv run python tools/inplace_guard.py --selftest

WHAT IT DOES NOT DO, SAID PLAINLY. It protects only what goes through it; a new site written
the old way is caught by tests/test_no_unguarded_restore.py, which refuses a write, a copy, a
delete or a git call inside a `finally` anywhere in tools/ or tests/ but here. A protecting()
record cannot tell the probed tool's change from a person's, so it is settled only by
--restore or --discard. A process id can be reused, so a dead run's record can look alive;
that fails towards REFUSING, the safe direction, and --status names the id.
"""
from __future__ import annotations

import contextlib
import datetime as _dt
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
JOURNAL_REL = ("temp", ".inplace-journal")
sys.path.insert(0, str(Path(__file__).resolve().parent))
from house_common import git_bytes  # noqa: E402  (stdin closed, paths unquoted, raw bytes)

# The records THIS process wrote and has not yet settled. Nesting is told from overlap by THIS,
# never by the process id alone: a dead run's record can carry an id the system has since given
# to this process, and treating it as our own would read its planted bytes as the original.
_OWN = set()


class GuardRefused(RuntimeError):
    """An unfinished record cannot be settled safely. Its message says what to do."""


def _sha(b):
    return None if b is None else hashlib.sha256(b).hexdigest()


def _read(p: Path):
    try:
        return p.read_bytes()
    except FileNotFoundError:
        return None


def _journal(root: Path) -> Path:
    return root.joinpath(*JOURNAL_REL)


def _rel(path, root: Path) -> str:
    # realpath, not abspath: Windows hands out short 8.3 names (WB24B~1.VAN) for the same folder,
    # and relative_to compares strings.
    return Path(os.path.realpath(path)).relative_to(Path(os.path.realpath(root))).as_posix()


def pid_alive(pid: int) -> bool:
    """True when a process with this id is running. NEVER os.kill(pid, 0) on Windows: there it
    TERMINATES the process."""
    if pid <= 0:
        return False
    if pid == os.getpid():
        return True
    if os.name == "nt":
        import ctypes
        k32 = ctypes.windll.kernel32
        h = k32.OpenProcess(0x1000, False, pid)        # PROCESS_QUERY_LIMITED_INFORMATION
        if not h:
            return False
        try:
            code = ctypes.c_ulong()
            ok = k32.GetExitCodeProcess(h, ctypes.byref(code))
            return bool(ok) and code.value == 259      # STILL_ACTIVE
        finally:
            k32.CloseHandle(h)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


NL = chr(10)


def records(root: Path = ROOT) -> list:
    """Every unfinished record, oldest first. A record that will not parse is returned with
    kind UNREADABLE, never skipped: a scan whose denominator can shrink is not a scan."""
    d = _journal(root)
    out = []
    for f in (sorted(d.glob("*.json")) if d.is_dir() else []):
        try:
            r = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, ValueError) as e:
            r = {"kind": "UNREADABLE", "path": f.name, "error": str(e)}
        r["id"] = f.stem
        out.append(r)
    return out


def _record(root: Path, rid: str) -> dict:
    return next(r for r in records(root) if r["id"] == rid)


def _drop(root: Path, rid: str) -> None:
    _OWN.discard(rid)
    d = _journal(root)
    (d / f"{rid}.json").unlink(missing_ok=True)
    (d / f"{rid}.orig").unlink(missing_ok=True)


def _git(root: Path, *args):
    return git_bytes(root, list(args))


def _how_to_decide(root: Path, rid: str) -> str:
    orig = _journal(root) / (rid + ".orig")
    where = (f"The original is saved at {orig}." if orig.exists() else
             "It did NOT EXIST before that run, so --restore removes it.")
    return NL.join([
        f"  {where} Compare, then either",
        f"    uv run python tools/inplace_guard.py --restore {rid}   (put the original back)",
        f"    uv run python tools/inplace_guard.py --discard {rid}   (keep the file as it is now)"])


def _settle(root: Path, r: dict, decided: bool = False) -> str:
    """Put back what a run left. `decided` is True only for the run's OWN exit and for --restore:
    then the original goes back whatever the file holds. Otherwise only what is SAFE is done,
    and GuardRefused is raised for the rest."""
    rid, kind = r["id"], r.get("kind")
    if kind == "UNREADABLE":
        raise GuardRefused(f"record {rid} will not parse ({r.get('error')}); inspect "
                           f"{_journal(root) / (rid + '.json')} and --discard it")
    p = root / r["path"]
    cur = _read(p)
    if kind == "staged":
        if _git(root, "cat-file", "-e", f"HEAD:{r['path']}").returncode != 0:
            _git(root, "reset", "-q", "--", r["path"])
        _drop(root, rid)
        return f"unstaged {r['path']}"
    if kind == "planted":
        if cur is None:
            _drop(root, rid)
            return f"{r['path']} was already gone"
        if not decided and _sha(cur) != r["planted_sha"]:
            raise GuardRefused(f"{r['path']} was planted by a run that did not finish and has been "
                               f"changed since - remove it yourself, then --discard {rid}")
        p.unlink()
        for dname in reversed(r.get("created_dirs", [])):
            with contextlib.suppress(OSError):
                (root / dname).rmdir()
        _drop(root, rid)
        return f"removed the planted {r['path']}"
    orig = _read(_journal(root) / f"{rid}.orig")
    if r.get("existed") and orig is None:
        raise GuardRefused(f"record {rid}: the saved original is missing - check {r['path']} by "
                           f"hand, then --discard {rid}")
    if _sha(cur) == r["orig_sha"]:
        _drop(root, rid)
        return f"{r['path']} was already as it began"
    if not decided and not (kind == "mutated" and _sha(cur) == r.get("planted_sha")):
        why = ("it was being protected, and a protected file's change cannot be told from a person's"
               if kind == "protected" else "it has been CHANGED SINCE, by a person or another tool")
        raise GuardRefused(f"{r['path']} was left changed by a run that did not finish, and {why}."
                           + NL + _how_to_decide(root, rid))
    if r.get("existed"):
        p.write_bytes(orig)
        if _sha(_read(p)) != r["orig_sha"]:
            raise GuardRefused(f"RESTORE FAILED for {r['path']}." + NL + _how_to_decide(root, rid))
    else:
        p.unlink(missing_ok=True)
        _drop(root, rid)
        return f"removed {r['path']}, which did not exist before"
    _drop(root, rid)
    return f"put {r['path']} back byte-exact"


def settle_dead(root: Path = ROOT, path=None) -> list:
    """Settle every record whose process is dead, newest first (so a planted-and-staged file is
    unstaged before it is removed). For `path` itself, a LIVE record or one that cannot be
    settled safely is REFUSED. For any other file a live record is left to its run, and an
    unsafe one is reported and left for a decision - it blocks commits, through
    tools/precommit_gate.py, but not a probe of an unrelated file."""
    done = []
    want = _rel(path, root) if path is not None else None
    for r in reversed(records(root)):
        mine = want is None or r.get("path") == want
        if r["id"] in _OWN:
            continue               # this run's own record: nesting (plant, then stage), not overlap
        if r.get("kind") != "UNREADABLE" and pid_alive(int(r.get("pid") or 0)):
            if want is not None and mine:
                raise GuardRefused(f"{want} is already being changed by process {r.get('pid')}, "
                                   f"which is still running. Two runs changing one file at once is "
                                   f"the overlap that baked a defect in: wait for it to finish")
            continue
        try:
            msg = _settle(root, r)
        except GuardRefused as e:
            if mine:
                raise
            print(f"inplace_guard: LEFT FOR A DECISION, and commits are refused until it is made - {e}",
                  file=sys.stderr)
            continue
        print(f"inplace_guard: RECOVERED - {msg} (left by process {r.get('pid')}, started "
              f"{r.get('started')}, which did not finish)", file=sys.stderr)
        done.append(msg)
    return done


def _write_record(root: Path, kind: str, path: Path, orig, planted, extra=None) -> str:
    d = _journal(root)
    d.mkdir(parents=True, exist_ok=True)
    rel = _rel(path, root)
    stamp = _dt.datetime.now().strftime("%Y%m%dT%H%M%S%f")
    rid = f"{stamp}-{os.getpid()}-{rel.replace('/', '_')[-60:]}"
    if orig is not None:
        (d / f"{rid}.orig").write_bytes(orig)
    rec = {"kind": kind, "path": rel, "existed": orig is not None, "orig_sha": _sha(orig),
           "planted_sha": _sha(planted), "pid": os.getpid(),
           "started": _dt.datetime.now().isoformat(timespec="seconds"), **(extra or {})}
    # WRITTEN LAST, AND THE FILE IS TOUCHED ONLY AFTER IT: a kill before this line has changed
    # nothing, and a kill after it leaves a record naming the change.
    (d / f"{rid}.json").write_bytes(json.dumps(rec, indent=1).encode("utf-8"))
    _OWN.add(rid)
    return rid


@contextlib.contextmanager
def mutated(path, new: bytes, root: Path = ROOT):
    """The file holds `new` inside the block, and its original bytes after it."""
    path = Path(path)
    settle_dead(root, path)
    orig = _read(path)
    if orig is None:
        raise GuardRefused(f"mutated(): {path} does not exist - use planted() for a new file")
    rid = _write_record(root, "mutated", path, orig, new)
    try:                           # the write is INSIDE: a write that fails half-way is undone too
        path.write_bytes(new)
        yield path
    finally:
        _settle(root, _record(root, rid), decided=True)


@contextlib.contextmanager
def protecting(path, root: Path = ROOT):
    """Something run inside the block may change, create or delete the file; it ends as it
    began - absent if it was absent."""
    path = Path(path)
    settle_dead(root, path)
    rid = _write_record(root, "protected", path, _read(path), None)
    try:
        yield path
    finally:
        _settle(root, _record(root, rid), decided=True)


@contextlib.contextmanager
def planted(path, data: bytes, root: Path = ROOT):
    """A file that must not exist before the block exists inside it, and is removed after,
    with any directory this created for it."""
    path = Path(path)
    settle_dead(root, path)
    if path.exists():
        raise GuardRefused(f"planted(): {path} already exists - refusing to overwrite it")
    created, q = [], path.parent
    while not q.exists():
        created.append(_rel(q, root))
        q = q.parent
    rid = _write_record(root, "planted", path, None, data, {"created_dirs": list(reversed(created))})
    try:                           # inside, so a failed write still removes what it made
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        yield path
    finally:
        _settle(root, _record(root, rid), decided=True)


@contextlib.contextmanager
def staged(path, root: Path = ROOT):
    """git add -f inside the block; unstaged after. For a path that is not in HEAD."""
    path = Path(path)
    settle_dead(root, path)
    rid = _write_record(root, "staged", path, None, None)
    added = _git(root, "add", "-f", "--", _rel(path, root))
    if added.returncode != 0:
        _drop(root, rid)
        raise GuardRefused(f"staged(): git add -f failed for {path}: "
                           f"{added.stderr.decode('utf-8', 'replace').strip()}")
    try:
        yield path
    finally:
        _settle(root, _record(root, rid), decided=True)


# ----------------------------------------------------------------------------------- CLI
def _alive(r: dict) -> bool:
    return r.get("kind") != "UNREADABLE" and pid_alive(int(r.get("pid") or 0))


def status(root: Path = ROOT) -> int:
    rs = records(root)
    print(f"inplace_guard: {len(rs)} unfinished record(s) in {'/'.join(JOURNAL_REL)}")
    for r in rs:
        state = "STILL RUNNING" if _alive(r) else "gone"
        print(f"  {r['id']}  {r.get('kind'):<10} {r.get('path')}  process {r.get('pid')} {state}"
              f"  started {r.get('started')}")
    return 1 if rs else 0


def recover(root: Path = ROOT) -> int:
    left = 0
    for r in reversed(records(root)):
        if _alive(r):
            print(f"  LEFT    {r['path']}: process {r.get('pid')} is still running")
            left += 1
            continue
        try:
            print(f"  SETTLED {_settle(root, r)}")
        except GuardRefused as e:
            print(f"  REFUSED {e}")
            left += 1
    print(f"inplace_guard: {left} record(s) still need a decision")
    return 1 if left else 0


def decide(root: Path, rid: str, restore: bool) -> int:
    r = next((x for x in records(root) if x["id"] == rid), None)
    if r is None:
        print(f"inplace_guard: no record {rid}")
        return 2
    if _alive(r):
        print(f"inplace_guard: process {r.get('pid')} is still running - refusing")
        return 1
    if restore:
        print(f"inplace_guard: {_settle(root, r, decided=True)}")
    else:
        _drop(root, rid)
        print(f"inplace_guard: dropped {rid}; {r.get('path')} left exactly as it is")
    return 0


# ------------------------------------------------------------------------------ selftest
# The child that dies inside a guard. os._exit skips every finally block, which is exactly what
# a killed process does - so each outcome below is reached by a REAL kill, not a simulation.
CHILD = NL.join([
    "import os, sys",
    "sys.dont_write_bytecode = True",
    "sys.path.insert(0, sys.argv[1])",
    "import inplace_guard as g",
    "from pathlib import Path",
    "root, kind = Path(sys.argv[2]), sys.argv[3]",
    "p = root / sys.argv[4]",
    "if kind == 'mutated':",
    "    cm = g.mutated(p, b'PLANTED', root)",
    "elif kind == 'planted':",
    "    cm = g.planted(p, b'PLANTED', root)",
    "elif kind == 'staged':",
    "    cm = g.staged(p, root)",
    "else:",
    "    cm = g.protecting(p, root)",
    "with cm:",
    "    if kind == 'protected':",
    "        p.write_bytes(b'CHANGED BY THE TOOL')",
    "    os._exit(137)",
])


def _refuses(fn) -> bool:
    try:
        fn()
    except GuardRefused:
        return True
    return False


def selftest() -> int:
    """EVERY OUTCOME REACHED, each by a real kill of a child process inside a guard."""
    results = []

    def check(label, good):
        results.append(bool(good))
        print(f"  {'OK  ' if good else 'MISS'} {label}")

    here = str(Path(__file__).resolve().parent)
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")

    def killed(root, kind, rel):
        return subprocess.run([sys.executable, "-c", CHILD, here, str(root), kind, rel],
                              capture_output=True, env=env).returncode

    print("SELFTEST - inplace_guard: every outcome reached, by a real kill")
    with tempfile.TemporaryDirectory(prefix="inplace_guard_selftest_") as td:
        root = Path(td)
        _git(root, "init", "-q")
        f = root / "doc.md"
        f.write_bytes(b"ORIGINAL")

        with mutated(f, b"PLANTED", root):
            inside = f.read_bytes()
        check("mutated(): the planted bytes inside, the original after, no record left",
              inside == b"PLANTED" and f.read_bytes() == b"ORIGINAL" and not records(root))

        rc = killed(root, "mutated", "doc.md")
        check("a KILLED mutated() leaves the planted bytes AND a record naming them",
              rc == 137 and f.read_bytes() == b"PLANTED" and len(records(root)) == 1)
        done = settle_dead(root)
        check("the next settle puts the original back byte-exact and clears the record",
              f.read_bytes() == b"ORIGINAL" and not records(root) and len(done) == 1)

        killed(root, "mutated", "doc.md")
        f.write_bytes(b"A PERSON EDITED THIS")
        check("a file CHANGED SINCE the kill is refused, never clobbered",
              _refuses(lambda: settle_dead(root)) and f.read_bytes() == b"A PERSON EDITED THIS"
              and len(records(root)) == 1)
        check("--restore, a decision, puts the original back",
              decide(root, records(root)[0]["id"], restore=True) == 0
              and f.read_bytes() == b"ORIGINAL" and not records(root))

        sleeper = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
        try:
            rid = _write_record(root, "mutated", f, b"ORIGINAL", b"PLANTED")
            jf = _journal(root) / f"{rid}.json"
            jf.write_bytes(json.dumps({**json.loads(jf.read_bytes()), "pid": sleeper.pid}).encode("utf-8"))
            _OWN.discard(rid)              # it now stands for ANOTHER run's record
            f.write_bytes(b"PLANTED")
            check("a record whose process is STILL RUNNING is refused for its own file",
                  _refuses(lambda: settle_dead(root, f)) and f.read_bytes() == b"PLANTED")
            check("and left alone when another file is changed",
                  settle_dead(root, root / "other.md") == [] and len(records(root)) == 1)
        finally:
            sleeper.kill()
            sleeper.wait()
        settle_dead(root)
        check("once that process is gone, the record settles",
              f.read_bytes() == b"ORIGINAL" and not records(root))

        reused = _write_record(root, "mutated", f, b"ORIGINAL", b"PLANTED")
        _OWN.discard(reused)               # a dead run's record whose id the system reused for us
        f.write_bytes(b"PLANTED")
        check("a record carrying THIS process's id that this process did not write is REFUSED, "
              "never taken for nesting", _refuses(lambda: settle_dead(root, f)))
        decide_ok = _settle(root, _record(root, reused), decided=True)
        check("...and settles by decision", f.read_bytes() == b"ORIGINAL" and not records(root) and bool(decide_ok))

        rc = killed(root, "planted", "sub/dir/plant.txt")
        check("a KILLED planted() leaves the file and a record",
              rc == 137 and (root / "sub" / "dir" / "plant.txt").exists() and len(records(root)) == 1)
        settle_dead(root)
        check("settling removes the plant AND the directories it created",
              not (root / "sub").exists() and not records(root))

        nested = root / "nested.txt"
        with planted(nested, b"N", root), staged(nested, root):
            inside = _git(root, "ls-files", "--cached", "--", "nested.txt").stdout.strip()
        check("one run may plant a file and then stage it: its own record is nesting, not overlap",
              inside == b"nested.txt" and not nested.exists() and not records(root)
              and _git(root, "ls-files", "--cached", "--", "nested.txt").stdout.strip() == b"")

        (root / "probe.txt").write_bytes(b"x")
        rc = killed(root, "staged", "probe.txt")
        cached = _git(root, "ls-files", "--cached", "--", "probe.txt").stdout.strip()
        check("a KILLED staged() leaves the path in the index", rc == 137 and cached == b"probe.txt")
        settle_dead(root)
        cached = _git(root, "ls-files", "--cached", "--", "probe.txt").stdout.strip()
        check("settling unstages it", cached == b"" and not records(root))
        (root / "probe.txt").unlink()

        rc = killed(root, "protected", "doc.md")
        check("a KILLED protecting() is REFUSED at settle - its change cannot be told from a person's",
              rc == 137 and _refuses(lambda: settle_dead(root))
              and f.read_bytes() == b"CHANGED BY THE TOOL")
        (root / "other.md").write_bytes(b"OTHER")
        with mutated(root / "other.md", b"PROBE", root):
            pass
        check("but that refusal does not block a probe of an UNRELATED file",
              (root / "other.md").read_bytes() == b"OTHER" and len(records(root)) == 1)
        check("--status names it and exits 1", status(root) == 1)
        check("--recover leaves it for a decision and exits 1", recover(root) == 1)
        decide(root, records(root)[0]["id"], restore=True)
        check("--restore settles it", f.read_bytes() == b"ORIGINAL" and status(root) == 0)

        (_journal(root) / "broken.json").write_bytes(b"{ not json")
        rs = records(root)
        check("an unreadable record is REPORTED, never skipped",
              len(rs) == 1 and rs[0]["kind"] == "UNREADABLE" and recover(root) == 1)
        decide(root, "broken", restore=False)
        check("--discard drops it and touches nothing", status(root) == 0 and f.read_bytes() == b"ORIGINAL")

        def plant_existing():
            with planted(f, b"x", root):
                pass
        check("planted() refuses a path that already exists",
              _refuses(plant_existing) and f.read_bytes() == b"ORIGINAL")
    good = all(results)
    print(f"SELFTEST: {'PASS' if good else 'FAIL'} - {sum(results)} of {len(results)} checks")
    return 0 if good else 1


def main(argv) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if "--selftest" in argv:
        return selftest()
    if "--status" in argv:
        return status()
    if "--recover" in argv:
        return recover()
    for flag, restore in (("--restore", True), ("--discard", False)):
        if flag in argv:
            i = argv.index(flag)
            if i + 1 >= len(argv):
                print(f"usage: {flag} ID")
                return 2
            return decide(ROOT, argv[i + 1], restore)
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
