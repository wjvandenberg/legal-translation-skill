"""test_notes_gates.py - branch 11 slice 4b: the four notes-side gates (PLAN-2-step-b.md section 3.2,
blocks "4b - C13, C4, C14" and "SLICE 4b's WRITTEN PLAN"). Every input here is invented and built in
a temporary directory; nothing is read from the corpus, and no document text is printed.

RED FIRST: `--ref 0bacc51` takes the variant's whole scripts folder from that commit. The arms that
state a NEW claim must fail there and pass here; the arms that pin what must NOT move pass in both,
which is what proves each change is no wider than its rule. A script whose copy at the ref equals the
working tree's has its arms reported VOID, never passed: that is a self-comparison.

  C13, validate_en_runs.py - every paragraph carrying en_runs must TILE en, exit 2, no flag waiving it
   1  a tiling paragraph outside any definitions section passes                          (unchanged)
   2  an out-of-range span is refused
   3  a gap is refused
   4  an overlap is refused
   5  a short tail is refused
   6  an `en` lengthened after its spans were authored is refused
   7  spans out of list order are refused
   8  a string offset and a boolean offset are each refused
   9  --allow-bold-loss does not waive a gap
  10  every violating paragraph is named at once, the tiling ones are not, and no text is printed
  11  the definitions presence test: missing en_runs 2, with the flag 1, with tiling runs 0  (unchanged)
  12  a definitions section missing en_runs AND a gap elsewhere, with the flag: still 2

    uv run --with lxml python tests/test_notes_gates.py
    uv run --with lxml python tests/test_notes_gates.py --variant us
    uv run --with lxml python tests/test_notes_gates.py --ref 0bacc51    # RED
"""
import argparse
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.dont_write_bytecode = True
os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")

ROOT = Path(__file__).resolve().parent.parent
ap = argparse.ArgumentParser()
ap.add_argument("--variant", choices=("uk", "us"), default="uk")
ap.add_argument("--ref", default=None, help="take the scripts from this commit instead (RED)")
args = ap.parse_args()
TREE = ROOT / args.variant / "scripts"
TMP = Path(tempfile.mkdtemp(prefix="b11s4b-notes-gates-"))
ENV = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1", PYTHONDONTWRITEBYTECODE="1")
FAIL, VOID, CHECKED = [], [], 0
UNDER_TEST = ("validate_en_runs.py", "verify_diligence.py", "coalesce_fragmented_tcs.py",
              "validate_translations.py")

if args.ref:
    SCRIPTS = TMP / "scripts"
    SCRIPTS.mkdir()
    names = subprocess.run(["git", "ls-tree", "-r", "--name-only", args.ref, "--", f"{args.variant}/scripts"],
                           capture_output=True, text=True, check=True, cwd=str(ROOT)).stdout.split()
    for n in names:
        (SCRIPTS / Path(n).name).write_bytes(
            subprocess.run(["git", "show", f"{args.ref}:{n}"], capture_output=True, check=True,
                           cwd=str(ROOT)).stdout)
    SAME = {s for s in UNDER_TEST if (SCRIPTS / s).read_bytes() == (TREE / s).read_bytes()}
else:
    SCRIPTS, SAME = TREE, set()


def ok(label, cond, detail=""):
    global CHECKED
    CHECKED += 1
    print(f"  {'OK  ' if cond else 'XX  '} {label}" + (f"   ({detail})" if detail and not cond else ""))
    if not cond:
        FAIL.append(label)


def section(script, title):
    """False, with the section's arms VOID, when the ref's copy of `script` is the working tree's."""
    print("\n" + title)
    print("-" * 96)
    if script in SAME:
        VOID.append(script)
        print(f"  ??   VOID - {args.ref}'s {script} equals the working tree's: a self-comparison")
        return False
    return True


def run(script, *argv):
    r = subprocess.run([sys.executable, str(SCRIPTS / script), *map(str, argv)], capture_output=True,
                       text=True, encoding="utf-8", errors="replace", env=ENV, cwd=str(TMP))
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def write(name, obj):
    p = TMP / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")
    return p


def para(idx, text, en=None, **kw):
    d = {"idx": idx, "text": text, "style": "Normal"}
    if en is not None:
        d["en"] = en
    d.update(kw)
    return d


def spans(*pairs):
    return [{"start": a, "end": b, "bold": False, "italic": False} for a, b in pairs]


# =====================================================================================================
if section("validate_en_runs.py", "C13 - validate_en_runs.py: the spans must TILE en, on every paragraph"):
    EN = "The Lessee shall pay the rent."          # 30 characters, invented
    assert len(EN) == 30
    SRC = "De huurder betaalt de huur."

    def one(runs, en=EN, *flags):
        p = write("ver_one.json", [para(0, SRC, en, en_runs=runs)])
        return run("validate_en_runs.py", p, *flags)

    rc, _ = one(spans((0, 4), (4, 10), (10, 30)))
    ok("  1 a tiling paragraph outside any definitions section passes", rc == 0, f"rc={rc}")
    for n, label, runs, en in (
            (2, "an out-of-range span (end 34 of 30)", spans((0, 4), (4, 34)), EN),
            (3, "a gap (4 to 6 uncovered)", spans((0, 4), (6, 30)), EN),
            (4, "an overlap (4 to 6 covered twice)", spans((0, 6), (4, 30)), EN),
            (5, "a short tail (26 to 30 uncovered)", spans((0, 4), (4, 26)), EN),
            (6, "an en lengthened after its spans were authored", spans((0, 4), (4, 30)),
             "The Lessee shall promptly pay the rent."),
            (7, "spans out of list order", spans((4, 30), (0, 4)), EN)):
        rc, out = one(runs, en)
        ok(f"  {n} {label} is refused, exit 2", rc == 2, f"rc={rc}")
    rc_s, _ = one([{"start": 0, "end": "30"}])
    rc_b, _ = one([{"start": False, "end": 30}])
    ok("  8 a string offset and a boolean offset are each refused, exit 2", rc_s == 2 and rc_b == 2,
       f"string rc={rc_s}, boolean rc={rc_b}")
    rc, _ = one(spans((0, 4), (6, 30)), EN, "--allow-bold-loss")
    ok("  9 --allow-bold-loss does not waive a gap, exit 2", rc == 2, f"rc={rc}")

    MARK = "Zephyrine"                               # a word that must never be printed
    many = [para(10, SRC, EN, en_runs=spans((0, 4), (4, 30))),
            para(11, SRC, f"The {MARK} shall pay.", en_runs=spans((0, 4), (6, 22))),
            para(12, SRC, EN, en_runs=spans((0, 30))),
            para(13, SRC, EN, en_runs=spans((0, 10), (5, 30))),
            para(14, SRC, EN),
            para(15, SRC, EN, en_runs=spans((0, 29)))]
    rc, out = run("validate_en_runs.py", write("ver_many.json", many))
    named = {i for i in range(10, 16) if f"idx {i}:" in out}
    ok(" 10 every violating paragraph is named at once (11 13 15), the others are not, no text printed",
       rc == 2 and named == {11, 13, 15} and MARK not in out and "SKILL GATE FIRED" in out,
       f"rc={rc}, named {sorted(named)}, text printed: {MARK in out}")

    DEFS = [('"Aanvangsdatum" betekent de begindatum.', '"Commencement Date" means the start date.'),
            ('"Overeenkomst" betekent deze overeenkomst.', '"Agreement" means this agreement.'),
            ('"Partij" betekent een partij bij deze overeenkomst.', '"Party" means a party to this agreement.'),
            ('"Zekerheid" betekent enige zekerheid.', '"Security" means any security given under this agreement.')]

    def defs(with_runs, extra=()):
        rows = [para(0, "1. Definities", "1. Definitions")]
        for i, (src, en) in enumerate(DEFS, start=1):
            p = para(i, src, en)
            if with_runs:
                p["en_runs"] = spans((0, len(en)))
            rows.append(p)
        rows.append(para(5, "2. Betaling", "2. Payment"))
        rows.extend(extra)
        return rows

    rc_m, _ = run("validate_en_runs.py", write("ver_defs_missing.json", defs(False)))
    rc_f, _ = run("validate_en_runs.py", write("ver_defs_missing.json", defs(False)), "--allow-bold-loss")
    rc_t, _ = run("validate_en_runs.py", write("ver_defs_tiling.json", defs(True)))
    ok(" 11 the definitions presence test: missing en_runs 2, with the flag 1, with tiling runs 0",
       (rc_m, rc_f, rc_t) == (2, 1, 0), f"got {(rc_m, rc_f, rc_t)}")
    gap = [para(6, SRC, EN, en_runs=spans((0, 4), (6, 30)))]
    rc, _ = run("validate_en_runs.py", write("ver_defs_gap.json", defs(False, gap)), "--allow-bold-loss")
    ok(" 12 a definitions section missing en_runs AND a gap elsewhere, with the flag: still exit 2",
       rc == 2, f"rc={rc}")

# =====================================================================================================
shutil.rmtree(TMP, ignore_errors=True)
print("\n" + "=" * 96)
print(f"  {CHECKED} check(s), {len(FAIL)} failure(s), {len(VOID)} section(s) VOID"
      + (f" ({', '.join(VOID)})" if VOID else ""))
for f in FAIL:
    print(f"    XX  {f}")
print("=" * 96)
if CHECKED == 0:
    print("  VOID - no section ran")
    sys.exit(2)
print("test_notes_gates: done")
sys.exit(1 if FAIL else 0)
