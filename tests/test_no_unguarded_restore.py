"""NO TOOL OR TEST PUTS A FILE BACK BY HAND (register I-37, 2026-10-08).

A write, copy, rename, delete or git call inside a `finally:` is the signature of
mutate-then-restore - and a `finally` is exactly what a killed process never reaches. Eleven
files had that shape; a run ended between a write and its restore left a planted defect in the
build plan, twice in one day, a commit away from being carried. Every one now goes through
tools/inplace_guard.py, which writes a record BEFORE the change so a killed run can be settled.

This reads every Python file under tools/ and tests/ - tracked AND untracked-but-not-ignored,
because a new file is exactly where the next one will appear - and refuses, outside the guard
itself and the declarations below:
  * a call that writes, copies, moves or deletes a file inside a `finally:` - write_text,
    write_bytes, unlink, rmdir, copyfile, copytree, copy2, shutil.copy, shutil.move, os.remove,
    and a path's replace() or rename() with one argument (str.replace, list.remove and
    dict.copy share those names and are told apart by receiver and arity);
  * open(...) for writing inside a `finally:`;
  * a subprocess call naming git inside a `finally:`;
  * a `finally:` that calls a function PASSED IN - the restore callback, which is how one of the
    eleven hid its restore from a search for writes.

NOT REFUSED, ON PURPOSE: shutil.rmtree of a whole directory inside a `finally:`. That removes a
temporary tree the same code created, which is cleanup, not restoration - and seventeen
selftests do it. A kill leaves an orphaned temporary folder, never a changed repository file.

    uv run python tests/test_no_unguarded_restore.py              # the files on disk
    uv run python tests/test_no_unguarded_restore.py --ref HEAD   # the files as at a commit
"""
import ast
import subprocess
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parent.parent
NUL = chr(0)
ALWAYS = {"write_text", "write_bytes", "unlink", "rmdir", "copyfile", "copytree", "copy2"}
SUBPROCESS = {"run", "call", "check_call", "check_output", "Popen"}
EXEMPT = {"tools/inplace_guard.py": "the guard itself: restoring is its whole job, and its own "
                                    "--selftest proves every outcome by a real kill"}
# (file, the exact call as ast.unparse prints it) -> why it is not a restore of a repository file.
DECLARED = {
    ("tools/precommit_gate.py", "probe_file.unlink(missing_ok=True)"):
        "deletes a scratch file this gate wrote moments earlier under gitignored temp/; a "
        "leftover is ignored by git and overwritten by the next run, so a kill leaves nothing "
        "committable",
}


sys.dont_write_bytecode = True  # importing from tools/ must leave no bytecode there
sys.path.insert(0, str(ROOT / "tools"))
from house_common import git_bytes  # noqa: E402  (stdin closed, paths unquoted, raw bytes)


def git(*args) -> bytes:
    r = git_bytes(ROOT, list(args))
    if r.returncode != 0:
        raise subprocess.CalledProcessError(r.returncode, ["git", *args], r.stdout, r.stderr)
    return r.stdout


def _changes_a_file(call) -> bool:
    """A call that writes, copies, moves or deletes a file. The names list.remove, str.replace
    and dict.copy share are told apart by receiver and arity: os.remove, a path's
    .replace(target) or .rename(target) with ONE argument, shutil.copy and shutil.move."""
    f = call.func
    if isinstance(f, ast.Name):
        return f.id in ALWAYS | {"move"}
    if not isinstance(f, ast.Attribute):
        return False
    recv = f.value.id if isinstance(f.value, ast.Name) else ""
    n, k = f.attr, len(call.args)
    if n in ALWAYS:
        return True
    if n in ("copy", "move"):
        return recv == "shutil"
    if n in ("replace", "rename"):
        return recv == "os" or k == 1
    return n == "remove" and recv == "os"


def _writes_mode(call) -> bool:
    mode = call.args[1] if len(call.args) > 1 else next(
        (k.value for k in call.keywords if k.arg == "mode"), None)
    if isinstance(mode, ast.Constant) and isinstance(mode.value, str):
        return any(c in mode.value for c in "wax+")
    return False


def findings(source: bytes) -> list:
    """Every refused call in one file's source, as (line, call). Raises SyntaxError."""
    tree = ast.parse(source)
    params_of = {}
    for fn in ast.walk(tree):
        if isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            names = {a.arg for a in fn.args.args + fn.args.kwonlyargs + fn.args.posonlyargs}
            for node in ast.walk(fn):
                params_of.setdefault(id(node), set()).update(names)
    out = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Try) and node.finalbody):
            continue
        for stmt in node.finalbody:
            for c in ast.walk(stmt):
                if not isinstance(c, ast.Call):
                    continue
                f = c.func
                name = f.attr if isinstance(f, ast.Attribute) else (f.id if isinstance(f, ast.Name) else "")
                text = ast.unparse(c)
                if (_changes_a_file(c)
                        or (name == "open" and _writes_mode(c))
                        or (name in SUBPROCESS and "git" in text)
                        or (isinstance(f, ast.Name) and f.id in params_of.get(id(node), set()))):
                    out.append((c.lineno, text))
    return out


def population(ref):
    """(path, bytes) for every .py under tools/ and tests/, and the paths that could not be read."""
    if ref:
        raw = git("ls-tree", "-r", "-z", "--name-only", ref, "--", "tools", "tests")
    else:
        raw = git("ls-files", "-z", "--cached", "--others", "--exclude-standard", "--", "tools", "tests")
    files, unread = [], []
    for n in sorted({n for n in raw.decode("utf-8").split(NUL) if n.endswith(".py")}):
        try:
            files.append((n, git("show", f"{ref}:{n}") if ref else (ROOT / n).read_bytes()))
        except (OSError, subprocess.CalledProcessError) as e:
            unread.append((n, type(e).__name__))
    return files, unread


# THE CONTROLS: the detector must fire on each shape and stay quiet on cleanup. Built from
# lines joined here, so no shape sits in this file where the scan would read it as code.
def _src(*lines) -> bytes:
    return chr(10).join(lines).encode("utf-8")


MUST_FIRE = {
    "a write in finally": _src("try:", "    p.write_bytes(b'x')", "finally:", "    p.write_bytes(orig)"),
    "open for writing in finally": _src("try:", "    pass", "finally:", "    open(p, 'w').write(s)"),
    "git in finally": _src("try:", "    pass", "finally:", "    subprocess.run(['git', 'reset', p])"),
    "os.remove and a path's replace in finally": _src("try:", "    pass", "finally:", "    os.remove(p)",
                                                      "    tmp.replace(p)"),
    "a restore callback in finally": _src("def case(mutate, restore):", "    try:", "        mutate()",
                                          "    finally:", "        restore()"),
}
MUST_NOT_FIRE = {
    "rmtree of a temporary tree": _src("try:", "    pass", "finally:", "    shutil.rmtree(tmp, ignore_errors=True)"),
    "list.remove and str.replace": _src("try:", "    pass", "finally:", "    sys.path.remove(d)",
                                        "    t = t.replace('a', 'b')", "    d2 = d.copy()"),
    "a write outside finally": _src("p.write_bytes(b'x')"),
    "open for reading in finally": _src("try:", "    pass", "finally:", "    open(p).read()"),
}


def main() -> int:
    ref = sys.argv[sys.argv.index("--ref") + 1] if "--ref" in sys.argv else None
    problems = []
    print("CONTROLS")
    for label, src in MUST_FIRE.items():
        ok = bool(findings(src))
        print(f"  {'OK  ' if ok else 'MISS'} must fail the scan: {label}")
        problems += [] if ok else [f"control: {label}"]
    for label, src in MUST_NOT_FIRE.items():
        ok = not findings(src)
        print(f"  {'OK  ' if ok else 'MISS'} quiet on {label}")
        problems += [] if ok else [f"control: {label}"]

    files, unread = population(ref)
    print(f"{chr(10)}THE TREE {'AT ' + ref if ref else 'ON DISK'}: examined {len(files)} of "
          f"{len(files) + len(unread)} Python file(s) under tools/ and tests/")
    for n, why in unread:
        print(f"  UNREAD    {n}: {why}")
        problems.append(f"unread: {n}")
    used, refused = set(), []
    for n, src in files:
        if n in EXEMPT:
            print(f"  exempt    {n}")
            continue
        try:
            hits = findings(src)
        except SyntaxError as e:
            print(f"  UNPARSED  {n}: {e}")
            problems.append(f"unparsed: {n}")
            continue
        for line, text in hits:
            if (n, text) in DECLARED:
                used.add((n, text))
                print(f"  declared  {n}:{line}  {text[:90]}")
            else:
                refused.append(n)
                print(f"  REFUSED   {n}:{line}  {text[:90]}")
    for key in DECLARED:
        if key not in used:
            print(f"  STALE DECLARATION - no longer found: {key[0]}  {key[1]}")
            problems.append(f"stale declaration: {key[0]}")
    print()
    if refused or problems:
        print(f"FAIL - {len(refused)} unguarded restore(s) in {len(set(refused))} file(s), "
              f"{len(problems)} other problem(s). Change a repository file only through "
              f"tools/inplace_guard.py.")
        return 1
    print(f"PASS - {len(files)} file(s) examined, 0 unguarded restores, {len(EXEMPT)} exempt, "
          f"{len(DECLARED)} declared")
    return 0


if __name__ == "__main__":
    sys.exit(main())
