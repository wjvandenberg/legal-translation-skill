# -*- coding: utf-8 -*-
"""DOES THE FULL RUNNER RUN EVERY SUITE THIS PROJECT HAS? Every tests/test_*.py, on every tree it can test.

Until 2026-10-20 the full runner, `tools/run_tests.py`, named ONE of the 47 `tests/test_*.py` - the shipped
tables, through `tests/run_tests.py` - and every TEST had to list the other 46 by hand. A suite nobody listed
was a suite nobody ran: measured that day, four of them had gone red in silence, each a check whose needle the
work had moved under it. Wouter wired all of them in (`DECISIONS-LOG.md`, 2026-10-20 and 2026-10-20 (2)). THIS
SUITE KEEPS IT THAT WAY: the forty-eighth file fails the run on the day it is added, not on the day somebody
notices it never ran.

WHAT IT ASSERTS, against `verify.config.json`'s `tests.suites` and the files on DISK (a new file is untracked
until it is staged, and it must fail here before it is committed, not after):

  1. every tests/test_*.py is named by a configured suite, or run by tests/run_tests.py (read off that file);
  2. every one that parses --variant is ALSO named with `--variant us`, and tests/run_tests.py too, which reads
     it - a suite that can test the US tree and is only ever run on the UK one has tested half of what it says;
  3. every configured suite names a file that exists, and no two suites share a name or a command;
  4. every configured suite RUNS ITS FILE AS THE TOP-LEVEL COMMAND - `uv run [--with lxml] python tests/<file>`,
     nothing wrapped around it - because a suite invoked through a wrapper reports the wrapper's exit code
     (`.claude/rules/verification.md`, the first of the five);
  5. every configured suite declares a 'count', the pattern that reads its own total - without one the runner
     prints "1 examined" over a suite of a hundred checks, the denominator run_tests v6 exists to keep.

AND IT PROVES IT CAN FAIL, first: each rule is given a config built to break it, and a clean one, before the
real config is read. A rule that has never been seen to fail is not a rule.

    uv run python tests/test_runner_names_every_suite.py
"""
import json
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parent.parent
TESTS = ROOT / "tests"
CONFIG = ROOT / "verify.config.json"

# A suite parses the flag itself - argparse, or an argv read - in either quote. Mentioning it is not
# enough: two suites pass --variant to a skill script and test both trees on their own.
PARSES_VARIANT = re.compile(r"""add_argument\(\s*["']--variant["']|["']--variant["'] in (?:sys\.)?argv""")
# The one form a suite's command may take: the file run directly, its variant the only argument.
COMMAND = re.compile(r"^uv run (?:--with lxml )?python (tests/[A-Za-z0-9_]+\.py)( --variant us)?$")
# tests/run_tests.py runs suites of its own; a file counts as run there only where it is built into a PATH
# (ROOT / "tests" / "<file>"), never where it is merely quoted - a message naming a file does not run it.
RUN_BY_SMOKE = re.compile(r'ROOT / "tests" / "(test_[A-Za-z0-9_]+\.py)"')

CHECKED, FAIL = 0, []


def ok(label, cond, detail=""):
    global CHECKED
    CHECKED += 1
    print(f"  {'PASS' if cond else 'FAIL'}  {label}")
    if not cond:
        FAIL.append(label)
        if detail:
            print(f"          {detail}")


def findings(files, suites, smoke_runs):
    """Every rule's breaches, as sentences. `files` maps a test file's name to whether it parses --variant;
    `suites` is tests.suites; `smoke_runs` the files tests/run_tests.py runs itself."""
    out = []
    named = {}                                      # file -> set of variants it is run on
    names, commands = set(), set()
    for s in suites:
        name, cmd = s.get("name", ""), s.get("command", "")
        if name in names:
            out.append(f"two suites are named {name!r}")
        if cmd in commands:
            out.append(f"two suites run {cmd!r}")
        names.add(name)
        commands.add(cmd)
        if not isinstance(s.get("count"), str) or not s.get("count"):
            out.append(f"suite {name!r} declares no 'count', so the runner cannot keep its total")
        m = COMMAND.match(cmd)
        if not m:
            out.append(f"suite {name!r} does not run its file as the top-level command: {cmd!r}")
            continue
        f = m.group(1).split("/", 1)[1]
        if f not in files and f != "run_tests.py":
            out.append(f"suite {name!r} names {f}, which is not on disk")
        named.setdefault(f, set()).add("us" if m.group(2) else "uk")
    for f in smoke_runs:
        named.setdefault(f, set()).add("uk")
    for f, variant in sorted(files.items()):
        if "uk" not in named.get(f, set()):
            out.append(f"{f} is run by no suite")
        if variant and "us" not in named.get(f, set()):
            out.append(f"{f} parses --variant and is never run with --variant us")
    if "uk" not in named.get("run_tests.py", set()) or "us" not in named.get("run_tests.py", set()):
        out.append("tests/run_tests.py is not run on both trees")
    return out


def on_disk():
    return {p.name: bool(PARSES_VARIANT.search(p.read_text(encoding="utf-8", errors="replace")))
            for p in sorted(TESTS.glob("test_*.py"))}


def smoke_runs():
    return sorted(set(RUN_BY_SMOKE.findall((TESTS / "run_tests.py").read_text(encoding="utf-8"))))


# ---------------------------------------------------------------------------------------------------------
print("=" * 96 + "\nNEGATIVE INPUTS - each rule given a config built to break it\n" + "=" * 96)
F = {"test_a.py": False, "test_b.py": True}
UV = "uv run --with lxml python tests/"
N = r"([0-9]+) check\(s\)"
CLEAN = [{"name": "smoke", "command": "uv run python tests/run_tests.py", "count": N},
         {"name": "smoke [us]", "command": "uv run python tests/run_tests.py --variant us", "count": N},
         {"name": "a", "command": UV + "test_a.py", "count": N},
         {"name": "b", "command": UV + "test_b.py", "count": N},
         {"name": "b [us]", "command": UV + "test_b.py --variant us", "count": N}]
ok("N0: a clean config has no finding", findings(F, CLEAN, []) == [], str(findings(F, CLEAN, [])))
cases = [
    ("N1: a file run by no suite", [s for s in CLEAN if s["name"] != "a"], "test_a.py is run by no suite"),
    ("N2: a --variant suite never run on us", [s for s in CLEAN if s["name"] != "b [us]"],
     "test_b.py parses --variant and is never run with --variant us"),
    ("N3: a suite naming a file not on disk", CLEAN + [{"name": "c", "command": UV + "test_c.py"}],
     "suite 'c' names test_c.py, which is not on disk"),
    ("N4: two suites of one name", CLEAN + [{"name": "a", "command": UV + "test_a.py --variant us"}],
     "two suites are named 'a'"),
    ("N5: one command twice", CLEAN + [{"name": "a2", "command": UV + "test_a.py"}],
     "two suites run 'uv run --with lxml python tests/test_a.py'"),
    ("N6: a suite run through a wrapper", CLEAN + [{"name": "w", "command": "uv run python temp/wrap.py tests/test_a.py"}],
     "suite 'w' does not run its file as the top-level command"),
    ("N7: tests/run_tests.py on one tree only", [s for s in CLEAN if s["name"] != "smoke [us]"],
     "tests/run_tests.py is not run on both trees"),
    ("N9: a suite that declares no count", [s if s["name"] != "a" else {k: v for k, v in s.items() if k != "count"}
                                            for s in CLEAN],
     "suite 'a' declares no 'count'"),
]
for label, cfg, needle in cases:
    got = findings(F, cfg, [])
    ok(label, any(g.startswith(needle) for g in got), f"wanted {needle!r}, got {got}")
ok("N8: a file tests/run_tests.py runs itself needs no suite of its own",
   findings({**F, "test_s.py": False}, CLEAN, ["test_s.py"]) == [])
# Each sample is built from two pieces, so THIS file's source never holds the pattern whole and this suite is
# not itself read as one that parses the flag (it would then demand a us twin of itself).
ok("N10: the flag is seen parsed in either quote and either argv spelling, and not where only mentioned",
   all(PARSES_VARIANT.search(a + b) for a, b in (("ap.add_argument(", '"--variant", default="uk")'),
                                                 ("ap.add_argument(", "'--variant', default='uk')"),
                                                 ('V = "us" if "--variant" ', "in sys.argv else 'uk'"),
                                                 ("if '--variant' ", "in argv:")))
   and not PARSES_VARIANT.search('run(script, ["--variant", "us"])  # passes it on, parses nothing'))
ok("N11: a file tests/run_tests.py only QUOTES is not run by it; one it builds into a path is",
   RUN_BY_SMOKE.findall('failures.append("see test_quoted.py")\nr = run([sys.executable, '
                        'str(ROOT / "tests" / "test_run.py")])') == ["test_run.py"])

# ---------------------------------------------------------------------------------------------------------
print("\n" + "=" * 96 + "\nTHE REAL CONFIG against the files on disk\n" + "=" * 96)
files = on_disk()
suites = json.loads(CONFIG.read_text(encoding="utf-8"))["tests"]["suites"]
runs = smoke_runs()
print(f"  {len(files)} tests/test_*.py on disk, {sum(files.values())} of them parse --variant; "
      f"{len(suites)} configured suite(s); tests/run_tests.py runs {len(runs)} itself: {', '.join(runs)}")
ok("R0: the population is not empty - files on disk, suites configured", bool(files) and bool(suites))
ok("R0: tests/run_tests.py names at least one suite of its own (the reader still reads it)", bool(runs))
got = findings(files, suites, runs)
# MISS, because the full runner shows a failed suite's lines that carry a failure mark and hides the rest: an
# unmarked finding left its row saying R1 failed without saying which file (measured on a planted one).
for g in got:
    print(f"    MISS  {g}")
ok("R1: every suite on disk is run by the full runner, on every tree it can test", not got,
   f"{len(got)} finding(s), listed above")

print("\n" + "=" * 96)
print(f"  RUNNER COVERAGE: {CHECKED} check(s), {len(FAIL)} failure(s)")
for f in FAIL:
    print(f"    FAIL  {f}")
print("=" * 96)
sys.exit(1 if FAIL else 0)
