# -*- coding: utf-8 -*-
"""DOES THE PRE-PUSH HOOK STILL REFUSE? The real tools/hooks/pre-push, run over invented ref lines.

Since #173 (2026-10-22) the hook holds two checks: this project's guard, which refuses a direct push to
`main`, and the house's full-run block, which refuses any push no recorded full run vouches for. Git writes
the pushed refs to standard input ONCE, so the hook saves them (`refs=$(cat)`) and feeds each check the saved
copy; and the guard runs in its own group, so its refusal reaches the hook's exit only through the `|| exit 1`
after that group. No suite ran the hook, so an edit that broke either property passed every suite: drop the
`|| exit 1` and a direct push to `main` goes through whenever a full run vouches for its commit; let the guard
read standard input itself and one of the two checks sees no refs at all, and passes everything (#173's
`/code-review`, DECISIONS-LOG.md 2026-10-22).

HOW. The hook is run as Git runs it - by Git's own `sh`, with the remote as its first argument and the ref
lines on standard input - from inside a scratch repository made by `git init` in a temporary folder, never
this one. That repository holds a stub `tools/cycle_evidence.py`, which the hook finds exactly where it finds
the real one: the stub writes down every commit it is asked about and answers `check-push` with 0 only for the
commits a case says a full run vouches for. `house.python` is set there to this interpreter, so the hook calls
the stub directly. The refs are invented: the hook reads only their text, so no commit has to exist. Every
inherited GIT_* variable and both override variables are cleared, so the case sets them, nothing else.

Each case keeps ONE check the only one that can refuse: the case that expects the guard to refuse `main`
vouches for the commit, so a hook whose guard stopped refusing would push it - and it asserts the stub was
never asked, which a guard that refused too late would not satisfy.

AND IT PROVES IT CAN FAIL. Three mutants are built from the real hook's text, each by an exact replacement
that must match once, and run through every case: M1 drops the `|| exit 1`; M2 lets the guard read standard
input before the save, so the full-run block sees nothing; M3 lets it read standard input after the save, so
the guard sees nothing. Each must fail at least one case. A mutant that cannot be built means the hook's shape
moved under this suite, and the run is VOID until the suite is moved with it.

    uv run python tests/test_pre_push_hook.py
    exit 0 every case passed and every mutant failed one · 1 a case failed or a mutant passed · 2 VOID
"""
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parent.parent
HOOK = ROOT / "tools" / "hooks" / "pre-push"

# What the hook calls in place of tools/cycle_evidence.py. It prints the real one's ALLOWED/REFUSED line,
# because the hook quotes the text after "PUSH ALLOWED" into its own message.
STUB = """import os
import sys
from pathlib import Path

with open(Path(__file__).resolve().parent / "asked.log", "a", encoding="utf-8") as log:
    print(" ".join(sys.argv[1:]), file=log)
vouched = os.environ.get("PRE_PUSH_TEST_VOUCHED", "").split()
if len(sys.argv) == 3 and sys.argv[1] == "check-push" and sys.argv[2] in vouched:
    print("  PUSH ALLOWED - the stub vouches for this commit")
    sys.exit(0)
print("  PUSH REFUSED - the stub vouches for nothing else")
sys.exit(1)
"""

MAIN, BRANCH, OTHER = "refs/heads/main", "refs/heads/feature/one", "refs/heads/feature/two"
A, B, ZERO = "a1" * 20, "b2" * 20, "0" * 40
SHORT, ENOUGH = "fourteen chars", "fifteen letters"    # the override's reason: 14 characters, then 15
assert (len(SHORT), len(ENOUGH)) == (14, 15), "the two reasons must sit either side of the hook's 15"


def push(ref, sha):
    """One ref line as Git writes it for a push of `ref` to the same name, new on the remote."""
    return f"{ref} {sha} {ref} {ZERO}"


# (name, ref lines, the environment it sets, the commits a full run vouches for,
#  the exit it wants, the commits the stub must have been asked about in order, text the hook must print)
CASES = [
    ("main is refused, although a full run vouches for its commit",
     [push(MAIN, A)], {}, [A], 1, [], "BLOCKED: direct push to main"),
    ("LT_ALLOW_MAIN_PUSH=1 passes the guard, and a vouched commit is pushed",
     [push(MAIN, A)], {"LT_ALLOW_MAIN_PUSH": "1"}, [A], 0, [A], "LT_ALLOW_MAIN_PUSH=1"),
    ("LT_ALLOW_MAIN_PUSH=1 passes the guard only: an unvouched commit is still refused",
     [push(MAIN, A)], {"LT_ALLOW_MAIN_PUSH": "1"}, [], 1, [A], "no full run vouches for"),
    ("LT_ALLOW_MAIN_PUSH set to anything but 1 overrides nothing",
     [push(MAIN, A)], {"LT_ALLOW_MAIN_PUSH": "yes"}, [A], 1, [], "BLOCKED: direct push to main"),
    ("a branch a full run vouches for is pushed",
     [push(BRANCH, A)], {}, [A], 0, [A], f"{BRANCH} ALLOWED"),
    ("a branch no full run vouches for is refused",
     [push(BRANCH, A)], {}, [], 1, [A], f"no full run vouches for {BRANCH}"),
    ("HOUSE_PUSH_WITHOUT_FULL_RUN with a 14-character reason is refused as too short",
     [push(BRANCH, A)], {"HOUSE_PUSH_WITHOUT_FULL_RUN": SHORT}, [], 1, [A], "too short to be a reason"),
    ("HOUSE_PUSH_WITHOUT_FULL_RUN with a 15-character reason pushes without a full run",
     [push(BRANCH, A)], {"HOUSE_PUSH_WITHOUT_FULL_RUN": ENOUGH}, [], 0, [A], "WITHOUT a full run"),
    ("main on the SECOND ref line is refused, every commit vouched for",
     [push(BRANCH, A), push(MAIN, B)], {}, [A, B], 1, [], "BLOCKED: direct push to main"),
    ("every saved line reaches the full-run block: an unvouched second branch refuses the push",
     [push(BRANCH, A), push(OTHER, B)], {}, [A], 1, [A, B], f"no full run vouches for {OTHER}"),
    ("a deletion carries no commit, so it is pushed without asking",
     [f"(delete) {ZERO} {BRANCH} {A}"], {}, [], 0, [], ""),
]

# The three mutants, each a list of (exact text, its replacement) that must each match the hook ONCE.
SAVE = "\nrefs=$(cat)\n"
GUARD_FEED = r"""printf '%s\n' "$refs" | {"""
GUARD_END = "\n} || exit 1\n"
MUTANTS = [
    ("M1: the guard's `|| exit 1` dropped", [(GUARD_END, "\n}\n")]),
    ("M2: the guard reads standard input before the save",
     [(SAVE, "\n"), (GUARD_FEED, "{"), (GUARD_END, GUARD_END + "refs=$(cat)\n")]),
    ("M3: the guard reads standard input after the save", [(GUARD_FEED, "{")]),
]


def git_sh():
    """The `sh` Git itself runs a hook with. NEVER the first `sh` or `bash` on the PATH: on Windows that
    `bash` can be WSL's, which sees neither this Git nor these paths."""
    if os.name != "nt":
        return shutil.which("sh")
    r = subprocess.run(["git", "--exec-path"], capture_output=True, text=True)
    if r.returncode != 0:
        return None
    here = Path(r.stdout.strip())
    for d in (here, *here.parents):
        if (d / "bin" / "sh.exe").is_file():
            return str(d / "bin" / "sh.exe")
    return None


def mutate(text, edits):
    """The mutant's text, or None when an edit does not match exactly once."""
    for old, new in edits:
        if text.count(old) != 1:
            return None
        text = text.replace(old, new)
    return text


def run_case(sh, hook, repo, case):
    """None when the case behaved as it should; otherwise what it did instead."""
    name, lines, env_set, vouched, want_rc, want_asked, want_text = case
    log = repo / "tools" / "asked.log"
    if log.exists():
        log.unlink()
    env = {k: v for k, v in os.environ.items()
           if not k.upper().startswith("GIT_")
           and k not in ("LT_ALLOW_MAIN_PUSH", "HOUSE_PUSH_WITHOUT_FULL_RUN")}
    env.update(env_set)
    env["PRE_PUSH_TEST_VOUCHED"] = " ".join(vouched)
    try:
        r = subprocess.run([sh, hook.as_posix(), "origin", "https://example.invalid/scratch.git"],
                           input=("\n".join(lines) + "\n").encode("utf-8"), capture_output=True,
                           cwd=repo, env=env, timeout=120)
    except subprocess.TimeoutExpired:
        return "the hook did not finish in 120 s"
    out = (r.stdout + r.stderr).decode("utf-8", "replace")
    asked = [ln.split()[-1] for ln in log.read_text(encoding="utf-8").splitlines()] if log.exists() else []
    wrong = []
    if r.returncode != want_rc:
        wrong.append(f"exit {r.returncode}, wanted {want_rc}")
    if asked != want_asked:
        wrong.append(f"the full-run check was asked about {asked or 'nothing'}, wanted {want_asked or 'nothing'}")
    if want_text not in out:
        wrong.append(f"no {want_text!r} in what it printed")
    if not wrong:
        return None
    shown = "\n".join("            | " + ln for ln in out.strip().splitlines()[:12])
    return "; ".join(wrong) + ("\n" + shown if shown else "")


def main():
    print("=" * 92)
    print("THE PRE-PUSH HOOK - the guard for main and the full-run block, run as Git runs them")
    print("=" * 92)
    try:
        sh = git_sh()
    except OSError:
        sh = None                                   # no git to ask: nothing could be run
    if not sh:
        print("  VOID: Git's own sh was not found, so the hook could not be run at all")
        return 2
    real = HOOK.read_text(encoding="utf-8")
    print(f"  hook  {HOOK.relative_to(ROOT).as_posix()}  ({len(real.splitlines())} lines)")
    print(f"  shell {sh}")
    checked, failed, void = 0, [], []
    with tempfile.TemporaryDirectory(prefix="pre-push-hook-") as tmp:
        repo = Path(tmp) / "repo"
        made = subprocess.run(["git", "init", "-q", str(repo)], capture_output=True, text=True)
        if made.returncode != 0:
            print(f"  VOID: git init failed in the temporary folder: {made.stderr.strip()}")
            return 2
        conf = subprocess.run(["git", "-C", str(repo), "config", "house.python", Path(sys.executable).as_posix()],
                              capture_output=True, text=True)
        if conf.returncode != 0:
            print(f"  VOID: git config failed in the scratch repository: {conf.stderr.strip()}")
            return 2
        (repo / "tools").mkdir()
        (repo / "tools" / "cycle_evidence.py").write_bytes(STUB.encode("utf-8"))

        print()
        print(f"  THE REAL HOOK, {len(CASES)} cases:")
        for case in CASES:
            checked += 1
            why = run_case(sh, HOOK, repo, case)
            print(f"  {'PASS' if why is None else 'FAIL'}  {case[0]}")
            if why is not None:
                failed.append(case[0])
                print(f"          {why}")

        print()
        print("  THE MUTANTS - each must fail at least one case:")
        for label, edits in MUTANTS:
            checked += 1
            text = mutate(real, edits)
            if text is None:
                void.append(label)
                print(f"  VOID  {label}: an edit no longer matches the hook exactly once")
                continue
            path = Path(tmp) / "pre-push-mutant"
            path.write_bytes(text.encode("utf-8"))
            killer = next((c[0] for c in CASES if run_case(sh, path, repo, c) is not None), None)
            if killer:
                print(f"  PASS  {label} - failed: {killer}")
            else:
                failed.append(label)
                print(f"  FAIL  {label} - passed every case, so this suite cannot see that edit")

    print()
    print("=" * 92)
    print(f"PRE-PUSH HOOK: {checked - len(failed) - len(void)} of {checked} checks passed"
          + (f", {len(void)} VOID" if void else ""))
    for f in failed:
        print(f"    FAILED: {f}")
    print("  What this does NOT prove: that a hook is installed, or that Git runs it - install_project_hooks.py")
    print("  --check answers that. It proves the hook's text refuses what it should, run as Git runs it.")
    print("=" * 92)
    return 1 if failed else 2 if void else 0


if __name__ == "__main__":
    sys.exit(main())
