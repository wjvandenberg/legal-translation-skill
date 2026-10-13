# -*- coding: utf-8 -*-
"""corpus_fingerprint.py - skip a corpus run whose inputs have not moved since one that passed.

WHY (Wouter, 2026-10-12). A VERIFY re-run took 29 minutes, two thirds of it the two delivered-document
corpus runs, and most re-runs follow a change those runs never read - a charter line, a register row, a
review fix in another tool. A corpus arm is a deterministic function of the files it reads, so if not one
of those files has moved since a run that PASSED, running it again can only print the same closing line.

THE SET IS DERIVED FROM WHAT RAN, NEVER TYPED (Wouter, 2026-10-13: trace the real run). `record` runs the
arm itself - the record is the run, never a claim about one - with a `sitecustomize` on PYTHONPATH that
installs an audit hook in the arm and in EVERY Python child it starts (measured: a `uv run --with lxml
python` child loads it too). Each process notes every file it opens, lists, copies or imports - a module
loaded from a path built at run time included, its source being read through an audited open (measured:
a loader hook added for it caught nothing more, and was removed) - every child it starts, and, because
several tree scripts hand lxml a file path, which lxml opens in C where no audit event fires, every path
given to lxml's `parse` and `iterparse`, which the tracer wraps. The inputs are every file so noted inside
the repository or a sibling folder that the run READ BEFORE IT WROTE IT - a probe that puts a file back
leaves it an input; a file the run wrote first is its own output - plus the listing of every folder it
listed and of every input's own folder, so an optional file whose mere EXISTENCE the arm tested (os.stat
raises no audit event) shows up when it appears beside the ones it read.

A CHILD THAT ESCAPES THE TRACE MAKES THE RECORD VOID, NEVER SMALLER. Every Python child seen starting must
come back with its own trace, matched by what it ran (the script's full path, `-c` with a hash of its code,
or `-m`); one started with -I, -E or -S cannot load the tracer and is counted escaped before it runs; and a
process started by any route but subprocess - os.system, os.spawn*, os.startfile, a fork, multiprocessing's
own CreateProcess - is one the trace cannot follow. A run whose children are not all accounted for is not
recorded - its own result still stands, it simply cannot be skipped next time.

`git` children are recorded by command line and RE-RUN by `check` (read-only subcommands only; any other
makes the record VOID), so a mutable reference such as HEAD is compared by what it answers. Any other
child is counted, and an argument naming an existing file inside the watched folders is hashed.

CONFIDENTIALITY. A sibling-folder file or listing is stored by the SHA-256 of its path, never its name, and
`check` finds it again by walking the watched folders and hashing each path. The raw trace lives in a
temporary folder deleted whole. Output prints counts, repository paths and the arm's own lines - nothing
from a sibling folder by name.

WHAT IT CANNOT SEE, SAID PLAINLY. A file whose existence is tested in a folder holding no input and never
listed. An ENVIRONMENT VARIABLE the arm reads - os.environ raises no audit event - so a driver that steers
an arm by one must not use the shortcut for that arm. A non-Python child other than git, beyond the
arguments it is given. A C library other than lxml opening a file by path, and lxml's own `_ElementTree.parse`
METHOD, which cannot be wrapped (its parse, ElementTree, XMLSchema, RelaxNG and DTD are; its iterparse opens
through Python's audited open - measured: a wrapper for it caught nothing more, and was removed). The
interpreter and site-packages, whose VERSIONS are compared instead. And it never decides whether an arm is
RIGHT - only whether its inputs moved since a run that passed and printed the closing line it was asked for.

    uv run python tools/corpus_fingerprint.py record --expect "0 failure(s), 0 void" -- <arm command>
    uv run python tools/corpus_fingerprint.py check [--expect TEXT] -- <arm command>
    uv run python tools/corpus_fingerprint.py run --expect "0 failure(s), 0 void" -- <arm command>

`run` is what a VERIFY driver calls: check, and on anything but PASS, record - which runs the arm.

EXIT. record: 0 the arm passed and is recorded · 1 the arm failed · 2 the arm passed but the record is VOID.
check: 0 PASS · 1 FAIL (an input moved) · 2 VOID (no record, or it cannot be read). run: 0 the arm passed,
skipped or run · 1 the arm ran and failed. The LAST line printed on a pass is the arm's own closing line,
so a driver matches it exactly as it matches the arm's.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from collections import Counter
from pathlib import Path

if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.dont_write_bytecode = True
HERE = Path(__file__).resolve()
ROOT = HERE.parent.parent
SCHEMA = 1
STORE_REL = ("temp", "corpus_fingerprints")
SKIP_PARTS = {"__pycache__", "site-packages", ".venv", ".git"}
GIT_READ_ONLY = {"show", "ls-tree", "merge-base", "rev-parse", "cat-file", "ls-files", "log", "diff",
                 "status", "rev-list", "for-each-ref", "describe", "name-rev", "show-ref", "var", "grep",
                 "blame"}
GIT_VALUE_OPTS = {"-c", "-C", "--git-dir", "--work-tree", "--namespace"}
PY_VALUE_OPTS = {"-X", "-W", "--check-hash-based-pycs"}
UV_VALUE_OPTS = {"--with", "--with-requirements", "--with-editable", "--python", "-p", "--project",
                 "--directory", "--extra", "--group", "--env-file", "--index", "--default-index", "--package"}
PROBE = ("import sys, importlib, importlib.util as u; "
         "e = importlib.import_module('lxml.etree') if u.find_spec('lxml') else None; "
         "print(sys.version.split()[0], '.'.join(map(str, e.LXML_VERSION)) if e else 'none')")

# The tracer, written as `sitecustomize.py` into a temporary folder on PYTHONPATH for the run. A raw string
# with no backslash in it, so nothing inside can be eaten as an escape.
TRACER = r'''
import atexit, json, os, sys, time
_DIR = os.environ.get("LT_FP_TRACE")
if _DIR:
    # path -> the moment it was FIRST read / FIRST written, so a file read before the run wrote it stays an
    # input and one the run wrote before reading is its own output.
    _R, _W, _L, _S, _U = {}, {}, set(), [], []
    _NP = [0, 0]                                   # subprocess.Popen events, _winapi.CreateProcess events
    _busy = [False]
    _WF = os.O_WRONLY | os.O_RDWR | os.O_APPEND | os.O_CREAT | os.O_TRUNC
    _UNWATCHED = frozenset(("os.system", "os.spawn", "os.posix_spawn", "os.exec", "os.startfile", "os.fork",
                            "os.forkpty"))
    _EV = frozenset(("open", "os.listdir", "os.scandir", "shutil.copyfile", "subprocess.Popen",
                     "_winapi.CreateProcess")) | _UNWATCHED
    _CWD0 = os.getcwd()

    def _p(x):
        try:
            if x is None or isinstance(x, int):
                return None
            return os.path.abspath(os.fsdecode(os.fspath(x)))
        except Exception:
            return None

    def _read(p):
        if p:
            _R.setdefault(p, time.time())

    def _wrote(p):
        if p:
            _W.setdefault(p, time.time())

    def _hook(event, args):
        if event not in _EV or _busy[0]:
            return
        try:
            if event == "open":
                p = _p(args[0])
                if p is None:
                    return
                mode = args[1] if len(args) > 1 else None
                flags = args[2] if len(args) > 2 else 0
                if isinstance(mode, str):
                    if "r" in mode or not any(c in mode for c in "wax"):
                        _read(p)
                    if any(c in mode for c in "wax+"):
                        _wrote(p)
                elif isinstance(flags, int) and flags & _WF:
                    if flags & os.O_RDWR:
                        _read(p)
                    _wrote(p)
                else:
                    _read(p)
            elif event in ("os.listdir", "os.scandir"):
                p = _p(args[0]) if args and args[0] is not None else os.getcwd()
                if p:
                    _L.add(p)
            elif event == "shutil.copyfile":
                _read(_p(args[0]))
                _wrote(_p(args[1]))
            elif event == "subprocess.Popen":
                _NP[0] += 1
                a = args[1]
                if isinstance(a, (str, bytes)):
                    argv = os.fsdecode(a).split()
                else:
                    argv = [os.fsdecode(os.fspath(x)) if not isinstance(x, str) else x for x in a]
                cwd = _p(args[2]) if len(args) > 2 and args[2] is not None else os.getcwd()
                _S.append({"argv": argv, "cwd": cwd})
            elif event == "_winapi.CreateProcess":
                _NP[1] += 1
            else:
                _U.append(event)
        except Exception:
            pass

    # lxml opens a file given by PATH in C, where no audit event fires. Functions are wrapped; classes are
    # subclassed, so an isinstance() against the name still holds.
    def _note(*cands):
        if not _busy[0]:
            for s in cands:
                if isinstance(s, (str, bytes, os.PathLike)):
                    _read(_p(s))

    _LX = None
    try:
        import importlib.util as _u
        if _u.find_spec("lxml") is not None:
            import lxml.etree as _et
            _LX = ".".join(str(x) for x in _et.LXML_VERSION)

            def _wrapf(f, positional):
                def w(*a, **k):
                    _note(a[0] if positional and a else None, k.get("source"), k.get("file"))
                    return f(*a, **k)
                return w

            def _subclass(cls, positional):
                def __init__(self, *a, **k):
                    _note(a[0] if positional and a else None, k.get("source"), k.get("file"))
                    cls.__init__(self, *a, **k)
                return type(cls.__name__, (cls,), {"__init__": __init__})

            for _n, _pos in (("parse", True), ("ElementTree", False)):
                setattr(_et, _n, _wrapf(getattr(_et, _n), _pos))
            for _n, _pos in (("XMLSchema", False), ("RelaxNG", False), ("DTD", True)):
                try:
                    setattr(_et, _n, _subclass(getattr(_et, _n), _pos))
                except Exception:
                    pass
    except Exception:
        pass

    def _flush():
        _busy[0] = True
        try:
            for m in list(sys.modules.values()):
                f = getattr(m, "__file__", None)
                if isinstance(f, str):
                    _R.setdefault(os.path.abspath(f), 0.0)       # imported before anything was written
            unwatched = list(_U) + (["_winapi.CreateProcess"] * (_NP[1] - _NP[0]) if _NP[1] > _NP[0] else [])
            rec = {"pid": os.getpid(), "orig_argv": list(getattr(sys, "orig_argv", sys.argv)),
                   "cwd0": _CWD0, "python": sys.version.split()[0], "lxml": _LX,
                   "read": _R, "wrote": _W, "listed": sorted(_L), "spawned": _S, "unwatched": unwatched}
            # A NAME NO OTHER PROCESS CAN TAKE, opened exclusively: a long run reuses process ids, and a trace
            # named by pid alone was overwritten by a later process with the same id - measured on the real
            # delivered-document arm, 18 and 25 traces lost, each turning the record VOID.
            name = "p%d-%s.json" % (os.getpid(), os.urandom(8).hex())
            with open(os.path.join(_DIR, name), "x", encoding="utf-8") as fh:
                json.dump(rec, fh)
        except Exception:
            pass

    atexit.register(_flush)
    sys.addaudithook(_hook)
'''


# ------------------------------------------------------------------------------------------ plumbing
def sha_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def sha_file(p: Path) -> str | None:
    try:
        return sha_bytes(p.read_bytes())
    except OSError:
        return None


def norm(p) -> str:
    return os.path.normcase(os.path.abspath(os.fspath(p)))


def path_key(p) -> str:
    """A sibling-folder path as stored: the hash of its normalised form, never its name."""
    return sha_bytes(norm(p).encode("utf-8"))


def listing_hash(d: Path) -> str | None:
    try:
        return sha_bytes("\n".join(sorted(os.listdir(d))).encode("utf-8"))
    except OSError:
        return None


def stem(tok: str) -> str:
    n = Path(tok).name.lower()
    return n[:-4] if n.endswith(".exe") else n


def is_python(tok: str) -> bool:
    """An interpreter by NAME - python, python3, python3.14, pythonw, py - never a package that starts
    with the word, such as python-docx."""
    return re.fullmatch(r"pyw?|pythonw?(?:\d+(?:\.\d+)?)?", stem(tok)) is not None


def launch(argv: list[str]) -> tuple[str, list[str]]:
    """What a command starts: ('py', args after the interpreter), ('py-any', []) for a `uv run` of something
    else, ('git', args after git) or ('other', argv)."""
    if not argv:
        return "other", []
    if is_python(argv[0]):
        return "py", argv[1:]
    if stem(argv[0]) == "uv" and "run" in argv[1:3]:
        j = argv.index("run") + 1
        while j < len(argv):
            a = argv[j]
            if a in UV_VALUE_OPTS:
                j += 2
                continue
            if a.startswith("-"):
                j += 1
                continue
            return ("py", argv[j + 1:]) if is_python(a) else ("py-any", [])
        return "py-any", []
    if stem(argv[0]) == "git":
        return "git", argv[1:]
    return "other", argv


def py_identity(args: list[str], cwd: str) -> tuple[str, bool]:
    """(what a Python process runs, whether it cannot load the tracer). The script as a normalised full
    path, '-c <hash of the code>', '-m <module>' or '-i'; -I, -E and -S each keep PYTHONPATH's
    sitecustomize out. The code is hashed so one `-c` child cannot stand in for another."""
    escapes = False
    i = 0
    while i < len(args):
        a = args[i]
        if a == "-c" or (a.startswith("-c") and not a.startswith("--")):
            code = a[2:] if a != "-c" else (args[i + 1] if i + 1 < len(args) else "")
            return "-c " + sha_bytes(code.encode("utf-8", "replace"))[:12], escapes
        if a == "-m":
            return "-m " + (args[i + 1] if i + 1 < len(args) else ""), escapes
        if a in PY_VALUE_OPTS:
            i += 2
            continue
        if a.startswith("-") and a != "-":
            if not a.startswith("--") and any(c in a[1:] for c in "IES") and a[1] not in "XW":
                escapes = True
            i += 1
            continue
        return norm(os.path.join(cwd, a)), escapes
    return "-i", escapes


def git_sub(args: list[str]) -> str:
    i = 0
    while i < len(args):
        a = args[i]
        if a in GIT_VALUE_OPTS:
            i += 2
            continue
        if a.startswith("-"):
            i += 1
            continue
        return a
    return ""


def inside(p: str, roots: list[str]) -> str | None:
    """The normalised root `p` sits under, or None."""
    for r in roots:
        if p == r or p.startswith(r + os.sep):
            return r
    return None


def skipped(p: str, store: str) -> bool:
    parts = set(Path(p).parts)
    return bool(parts & SKIP_PARTS) or p == store or p.startswith(store + os.sep)


def run_git(args: list[str], cwd: str) -> tuple[int, str]:
    r = subprocess.run(["git", *args], cwd=cwd, capture_output=True, stdin=subprocess.DEVNULL)
    return r.returncode, sha_bytes(r.stdout)


def probe_versions(argv: list[str], cwd: str) -> tuple[str, str] | None:
    """The interpreter and lxml versions the arm's own launcher gives now."""
    kind, rest = launch(argv)
    if kind != "py":
        return None
    prefix = argv[:len(argv) - len(rest)]
    env = {k: v for k, v in os.environ.items() if k not in ("LT_FP_TRACE",)}
    r = subprocess.run(prefix + ["-c", PROBE], cwd=cwd, capture_output=True, text=True, encoding="utf-8",
                       errors="replace", stdin=subprocess.DEVNULL, env=env)
    bits = (r.stdout or "").split()
    return (bits[0], bits[1]) if r.returncode == 0 and len(bits) >= 2 else None


class Layout:
    """Where things are: the repository root, the watched sibling folders, the record store."""

    def __init__(self, root: Path | None, watch: list[str], store: Path | None):
        self.root = (root or ROOT).resolve()
        dirs = [Path(w) for w in watch]
        if root is None:                                   # the real repository: its sibling folders too
            sys.path.insert(0, str(HERE.parent))
            import sibling_dirs as sd
            dirs += [sd.private_dir(), sd.logs_dir(), sd.archives_dir(), *sd.corpus_dirs()]
        self.watch = sorted({norm(d) for d in dirs if Path(d).is_dir()})
        self.rootn = norm(self.root)
        self.store = (store or self.root.joinpath(*STORE_REL)).resolve()
        self.storen = norm(self.store)

    def record_path(self, argv: list[str]) -> Path:
        return self.store / (sha_bytes(json.dumps(argv).encode("utf-8"))[:24] + ".json")

    def mask(self, argv: list[str]) -> list[str]:
        """The arm's command line as stored: an argument naming a sibling-folder path is stored hashed."""
        out = []
        for a in argv:
            n = norm(a) if a and not a.startswith("-") else ""
            out.append("<sibling:" + path_key(a)[:16] + ">" if n and inside(n, self.watch) else a)
        return out

    def sibling_index(self) -> tuple[dict, dict]:
        """Every file and folder under the watched folders, by path hash - found again without a name."""
        files, dirs = {}, {}
        for w in self.watch:
            dirs[path_key(w)] = w
            for dp, dn, fn in os.walk(w):
                dn[:] = [d for d in dn if d not in SKIP_PARTS]
                for d in dn:
                    dirs[path_key(os.path.join(dp, d))] = os.path.join(dp, d)
                for f in fn:
                    files[path_key(os.path.join(dp, f))] = os.path.join(dp, f)
        return files, dirs


# ------------------------------------------------------------------------------------------ record
def record(lay: Layout, argv: list[str], expect: str) -> tuple[int, str]:
    """Run the arm under the trace. Returns (exit code, closing line or '')."""
    kind, rest = launch(argv)
    if kind != "py":
        print("corpus_fingerprint: REFUSED - the command must start a Python process (python ... or uv run "
              "... python ...), the only kind the trace can follow")
        return 2, ""
    print(f"corpus_fingerprint record: running {Path(py_identity(rest, lay.rootn)[0]).name} under the trace")
    with tempfile.TemporaryDirectory(prefix="lt-fp-", ignore_cleanup_errors=True) as td:
        Path(td, "sitecustomize.py").write_bytes(TRACER.encode("utf-8"))
        env = dict(os.environ, LT_FP_TRACE=td,
                   PYTHONPATH=os.pathsep.join(x for x in (td, os.environ.get("PYTHONPATH", "")) if x))
        t0 = time.time()
        r = subprocess.run(argv, cwd=str(lay.root), env=env, capture_output=True, text=True, encoding="utf-8",
                           errors="replace", stdin=subprocess.DEVNULL)
        took = time.time() - t0
        out = (r.stdout or "") + (r.stderr or "")
        print(out.rstrip("\n"))
        print("--- corpus_fingerprint " + "-" * 60)
        hits = [ln.rstrip() for ln in out.splitlines() if expect in ln]
        if r.returncode != 0 or not hits:
            print(f"  the arm FAILED: rc {r.returncode}, closing line {'present' if hits else 'ABSENT'} "
                  f"({expect!r}) - nothing recorded")
            return 1, ""
        closing = hits[-1]
        traces = []
        for p in sorted(Path(td).glob("p*.json")):
            try:
                traces.append(json.loads(p.read_bytes().decode("utf-8")))
            except (OSError, ValueError):
                print("  a trace file could not be read - VOID")
                return 2, closing
        rec, why = build(lay, argv, traces, t0)
    if rec is None:
        print(f"  NOT RECORDED - VOID: {why}. The arm's own result stands; it cannot be skipped next time.")
        return 2, closing
    rec.update({"closing": closing, "expect": expect, "recorded": time.strftime("%Y-%m-%d %H:%M:%S"),
                "seconds": round(took, 1)})
    lay.store.mkdir(parents=True, exist_ok=True)
    lay.record_path(argv).write_bytes(json.dumps(rec, indent=1, sort_keys=True).encode("utf-8"))
    print(f"  traced {rec['traced']['reported']} process(es); {rec['traced']['python_started']} Python "
          f"child(ren) started, every one accounted for")
    print(f"  inputs: {len(rec['repo'])} repository file(s), {len(rec['sibling'])} sibling-folder file(s), "
          f"{len(rec['listings'])} listing(s), {len(rec['git'])} git command(s), "
          f"{rec['traced']['other_children']} other child(ren)")
    print(f"  recorded as {lay.record_path(argv).name} after a {took:.0f} s run")
    print(f"RECORDED - {closing.strip()}")
    print(closing)
    return 0, closing


def build(lay: Layout, argv: list[str], traces: list[dict], t0: float) -> tuple[dict | None, str]:
    """Turn the traces into a record, or say why it cannot be one."""
    roots = [lay.rootn] + lay.watch
    expected, escaped, any_py, other, gits = Counter(), [], 0, 0, []
    ident, esc = py_identity(launch(argv)[1], lay.rootn)
    expected[ident] += 1
    if esc:
        escaped.append(Path(ident).name)
    # Compared normalised (Windows paths are case-blind), stored and printed as the program wrote them.
    # A path's first read and first write are compared ACROSS processes: read first, it is an input even if
    # the run rewrote it afterwards (a probe that puts a file back, a cache); written first, it is an output.
    read, first_r, first_w, listed, started, unwatched = {}, {}, {}, {}, 0, []
    for t in traces:
        unwatched += t.get("unwatched", [])
        for p, when in t.get("read", {}).items():
            n = norm(p)
            read.setdefault(n, os.path.abspath(p))
            first_r[n] = min(when, first_r.get(n, when))
        for p, when in t.get("wrote", {}).items():
            n = norm(p)
            first_w[n] = min(when, first_w.get(n, when))
        for p in t.get("listed", []):
            listed.setdefault(norm(p), os.path.abspath(p))
        for sp in t.get("spawned", []):
            kind, rest = launch(sp["argv"])
            if kind == "py":
                started += 1
                i, e = py_identity(rest, sp["cwd"])
                expected[i] += 1
                if e:
                    escaped.append(Path(i).name)
            elif kind == "py-any":
                started += 1
                any_py += 1
            elif kind == "git":
                sub = git_sub(rest)
                if sub not in GIT_READ_ONLY:
                    return None, f"a git child ran '{sub}', which may write - only read-only git is re-runnable"
                gits.append({"args": rest, "cwd": os.path.relpath(sp["cwd"], lay.root)
                             if inside(norm(sp["cwd"]), [lay.rootn]) else None})
                if gits[-1]["cwd"] is None:
                    return None, "a git child ran outside the repository"
            else:
                other += 1
                for a in sp["argv"][1:]:
                    full = os.path.abspath(os.path.join(sp["cwd"], a)) if a and not a.startswith("-") else ""
                    if full and inside(norm(full), roots) and os.path.isfile(full):
                        read.setdefault(norm(full), full)
                        first_r.setdefault(norm(full), 0.0)
    if unwatched:
        return None, (f"{len(unwatched)} process(es) started by a route the trace cannot follow "
                      f"({', '.join(sorted(set(unwatched)))}) - only subprocess children are traced")
    if escaped:
        return None, f"{len(escaped)} Python child(ren) started with -I, -E or -S, which cannot load the trace"
    reported = Counter(py_identity(t.get("orig_argv", [])[1:], t.get("cwd0", "")) [0] for t in traces)
    missing = expected - reported
    if missing:
        names = sorted({Path(k).name for k in missing.elements()})
        return None, (f"{sum(missing.values())} Python process(es) started and never reported a trace "
                      f"({', '.join(names)})")
    if sum((reported - expected).values()) < any_py:
        return None, f"{any_py} `uv run` child(ren) of a non-Python command not accounted for"
    def rel(n: str) -> str:
        return Path(os.path.relpath(read.get(n) or listed.get(n) or n, lay.root)).as_posix()

    inputs = sorted(n for n in read if (n not in first_w or first_r[n] <= first_w[n])
                    and inside(n, roots) and not skipped(n, lay.storen) and os.path.isfile(n))
    # A file the run did not write must not have changed while it ran: something else touched an input.
    # No slack before t0: an edit made just BEFORE the run - the ordinary case of editing, then re-running -
    # is not a change during it (measured: a one-second margin turned the suite's edit-then-run case VOID).
    moved = [n for n in inputs if n not in first_w and os.stat(n).st_mtime > t0]
    if moved:
        named = [rel(n) for n in moved if inside(n, [lay.rootn])]
        return None, (f"{len(moved)} input(s) changed DURING the run"
                      + (f": {', '.join(named[:5])}" if named else " (sibling-folder files, not named)"))
    repo, sibling = {}, {}
    for n in inputs:
        h = sha_file(Path(n))
        if h is None:
            return None, "an input could not be read back"
        if inside(n, [lay.rootn]):
            repo[rel(n)] = h
        else:
            sibling[path_key(n)] = h
    # Each input's own folder is listed too: a file whose EXISTENCE the arm tested (os.stat raises no audit
    # event) and found absent - an optional declaration beside the ones it read - appears in that listing.
    for n in inputs:
        d = os.path.dirname(read[n])
        listed.setdefault(norm(d), d)
    listings = {}
    for d in sorted(listed):
        if not inside(d, roots) or skipped(d, lay.storen) or not os.path.isdir(d):
            continue
        key = "repo:" + rel(d) if inside(d, [lay.rootn]) else "sibling:" + path_key(d)
        listings[key] = listing_hash(Path(d))
    for g in gits:
        g["rc"], g["out"] = run_git(g["args"], str(lay.root / g["cwd"]))
    root_trace = next((t for t in traces if py_identity(t.get("orig_argv", [])[1:], t.get("cwd0", ""))[0]
                       == ident), traces[0] if traces else {})
    return {"schema": SCHEMA, "argv": lay.mask(argv), "tool": sha_file(HERE),
            "python": root_trace.get("python"), "lxml": root_trace.get("lxml") or "none",
            "repo": repo, "sibling": sibling, "listings": listings, "git": gits,
            "traced": {"reported": len(traces), "python_started": started, "other_children": other}}, ""


# ------------------------------------------------------------------------------------------ check
def check(lay: Layout, argv: list[str], expect: str | None) -> tuple[int, str]:
    """Re-hash a record's inputs. Returns (exit code, closing line on PASS)."""
    rp = lay.record_path(argv)
    label = Path(py_identity(launch(argv)[1], lay.rootn)[0]).name
    print(f"corpus_fingerprint check: {label}")
    if not rp.is_file():
        print("  VOID - no record for this exact command line; nothing was skipped")
        return 2, ""
    try:
        rec = json.loads(rp.read_bytes().decode("utf-8"))
    except (OSError, ValueError):
        print("  VOID - the record cannot be read")
        return 2, ""
    if rec.get("schema") != SCHEMA:
        print(f"  VOID - record schema {rec.get('schema')}, this tool reads {SCHEMA}")
        return 2, ""
    bad = []
    if rec.get("tool") != sha_file(HERE):
        bad.append("this tool itself has changed since the record")
    if expect is not None and expect not in rec.get("closing", ""):
        bad.append(f"the recorded closing line does not contain {expect!r}")
    changed = [k for k, h in sorted(rec["repo"].items()) if sha_file(lay.root / k) != h]
    files, dirs = lay.sibling_index() if (rec["sibling"] or any(k.startswith("sibling:")
                                                               for k in rec["listings"])) else ({}, {})
    sib_bad = sum(1 for k, h in rec["sibling"].items() if k not in files or sha_file(Path(files[k])) != h)
    list_bad = []
    for k, h in sorted(rec["listings"].items()):
        kind, _, rest = k.partition(":")
        d = (lay.root / rest) if kind == "repo" else (Path(dirs[rest]) if rest in dirs else None)
        if d is None or listing_hash(d) != h:
            list_bad.append(rest if kind == "repo" else "a sibling-folder listing")
    git_bad = [" ".join(g["args"][:3]) for g in rec["git"]
               if run_git(g["args"], str(lay.root / g["cwd"])) != (g["rc"], g["out"])]
    now = probe_versions(argv, str(lay.root))
    if now is None:
        bad.append("the interpreter could not be probed")
    elif now != (rec["python"], rec["lxml"]):
        bad.append(f"the interpreter moved: Python {rec['python']} lxml {rec['lxml']} then, "
                   f"{now[0]} {now[1]} now")
    print(f"  record of {rec.get('recorded')}, a {rec.get('seconds')} s run; inputs: {len(rec['repo'])} "
          f"repository file(s), {len(rec['sibling'])} sibling-folder file(s), {len(rec['listings'])} "
          f"listing(s), {len(rec['git'])} git command(s)")
    for k in changed:
        bad.append(f"changed: {k}")
    if sib_bad:
        bad.append(f"{sib_bad} sibling-folder file(s) changed or gone (not named)")
    for k in list_bad:
        bad.append(f"listing changed: {k}")
    for g in git_bad:
        bad.append(f"git answers differently: git {g} ...")
    if bad:
        for b in bad:
            print(f"  FAIL  {b}")
        print("FAIL - an input moved since the run that passed; run the arm")
        return 1, ""
    print("PASS - every input byte-identical to a run that passed; its closing line:")
    print(rec["closing"])
    return 0, rec["closing"]


# ------------------------------------------------------------------------------------------ main
def main(argv: list[str]) -> int:
    if "--" not in argv:
        print(__doc__)
        return 2
    cut = argv.index("--")
    ap = argparse.ArgumentParser(prog="corpus_fingerprint.py")
    ap.add_argument("mode", choices=("record", "check", "run"))
    ap.add_argument("--expect", help="text the arm's closing line must contain")
    ap.add_argument("--root", help="the repository root (default: this one, with its sibling folders)")
    ap.add_argument("--watch", action="append", default=[], help="a further folder outside the repository")
    ap.add_argument("--store", help="where records live (default: temp/corpus_fingerprints)")
    a = ap.parse_args(argv[:cut])
    cmd = argv[cut + 1:]
    if not cmd or (a.mode in ("record", "run") and not a.expect):
        print("corpus_fingerprint: a command after -- is required, and --expect for record and run")
        return 2
    lay = Layout(Path(a.root) if a.root else None, a.watch, Path(a.store) if a.store else None)
    if a.mode == "record":
        return record(lay, cmd, a.expect)[0]
    if a.mode == "check":
        return check(lay, cmd, a.expect)[0]
    code, _ = check(lay, cmd, a.expect)
    if code == 0:
        return 0
    print("corpus_fingerprint run: not skippable - running the arm")
    _, closing = record(lay, cmd, a.expect)
    return 0 if closing else 1                 # a pass is a closing line from a run, recorded or not


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
