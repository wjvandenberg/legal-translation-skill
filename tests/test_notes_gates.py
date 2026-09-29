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

  C4, verify_diligence.py - Step 4 + 4b counts what was DECLARED, validate_translations' own population
  13  a declared paragraph kept as the source and missing from the state FAILs
  14  a complete state PASSes and says how many were declared, changed and kept as the source
  15  a changed declared paragraph missing from the state still FAILs                       (unchanged)
  16  English with no source text is outside the validator's population, so it is not counted

  C14, coalesce_fragmented_tcs.py - regular text glued letter to letter counts, a CJK junction does not
  17  the D04-113 shape, its stem AFTER the edit, is scaffolded, the stem's segment its own placeholder
  18  the D04-125 shape, its stem BEFORE the edit, is scaffolded the same way
  19  a whole-word replacement followed by punctuation is not scaffolded                     (unchanged)
  20  a CJK junction is not scaffolded                                                         (unchanged)
  21  regular text glued INSIDE the run counts as a piece
  22  the canonical letter-by-letter cluster is scaffolded as the step document shows       (unchanged)
  23  every run prints tracked-change paragraphs examined against scaffolded, a clean one too
  24  direct fill is unchanged                                                                 (unchanged)

  C30, validate_translations.py - a <<TRANSLATE: placeholder left in en or a segment is refused, exit 2
  25  one left in en is refused, the paragraph named, no text printed, no state written
  26  one left in an en_segments entry is refused, naming the segment
  27  one on a paragraph with no source text is still refused
  28  the same scaffold filled in passes and records its state                               (unchanged)
  29  a scaffolded paragraph not yet translated (no en) is not refused: batch 1 still validates (unchanged)

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
if section("verify_diligence.py", "C4 - verify_diligence.py: Step 4 + 4b counts what was DECLARED"):
    import re as _re
    COVER = _re.compile(r"^\s+(PASS|FAIL|WARN) — (.*(?:translated|declared) paragraphs.*)$", _re.M)

    def audit(rows, validated, name):
        wd = TMP / name
        wd.mkdir(parents=True, exist_ok=True)
        (wd / "paragraphs.json").write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
        (wd / ".validate-state.json").write_text(json.dumps(
            {"validated_indices": validated,
             "history": [{"timestamp": "2020-01-01T00:00:00Z", "count": len(validated),
                          "indices": validated}]}), encoding="utf-8")
        rc, out = run("verify_diligence.py", wd, "--report-only")
        m = COVER.search(out)
        return (m.group(1), m.group(2)) if m else (None, f"no coverage line (rc={rc})")

    # Five declared: 0 and 1 changed, 2 3 4 kept as the source (a party name, a date, a code).
    ROWS = [para(0, "De huurder betaalt.", "The Lessee pays."),
            para(1, "De verhuurder levert.", "The Lessor delivers."),
            para(2, "Acme Holding B.V.", "Acme Holding B.V."),
            para(3, "12.03.2020", "12.03.2020"),
            para(4, "NL-7788", "NL-7788"),
            para(5, "", ""),
            para(6, "Niet vertaald.")]
    sev, line = audit(ROWS, [0, 1, 3, 4], "vd_kept_missing")
    ok(" 13 a declared paragraph KEPT as the source and missing from the state FAILs", sev == "FAIL",
       f"{sev}: {line}")
    sev, line = audit(ROWS, [0, 1, 2, 3, 4], "vd_complete")
    ok(" 14 a complete state PASSes, saying 5 declared, 2 changed, 3 kept as the source",
       sev == "PASS" and "5 declared" in line and "2 changed" in line and "3 kept as the source" in line,
       f"{sev}: {line}")
    sev, line = audit(ROWS, [1, 2, 3, 4], "vd_changed_missing")
    ok(" 15 a CHANGED declared paragraph missing from the state still FAILs", sev == "FAIL", f"{sev}: {line}")
    sev, line = audit(ROWS + [para(7, "", "An inserted English line.")], [0, 1, 2, 3, 4], "vd_no_source")
    ok(" 16 English with no source text is outside the validator's population, so it is not counted",
       sev == "PASS" and "5 declared" in line, f"{sev}: {line}")

# =====================================================================================================
if section("coalesce_fragmented_tcs.py", "C14 - coalesce_fragmented_tcs.py: the glued stem counts, a CJK junction does not"):
    PH = "<<TRANSLATE: "

    def tcp(idx, segs):
        text = "".join(t for k, t in segs if k != "del")
        return {"idx": idx, "text": text, "style": "Normal", "has_track_changes": True,
                "tc_segments": [{"type": k, "text": t} for k, t in segs]}

    def scaffold(rows, name, *flags):
        p = write(name, rows)
        rc, out = run("coalesce_fragmented_tcs.py", p, *flags)
        return rc, out, {e["idx"]: e.get("en_segments") for e in json.loads(p.read_text(encoding="utf-8"))}

    AFTER = [("regular", "Clausula "), ("del", "Duod"), ("ins", "Tr"), ("regular", "ecima.- Datos personales")]
    BEFORE = [("regular", "Seccion Vige"), ("del", "simo"), ("ins", "sima"), ("regular", ". Plazo")]
    WHOLE = [("regular", "Artikel "), ("del", "twee"), ("ins", "drie"), ("regular", ". De partij stemt in")]
    CJK = [("regular", "第十"), ("del", "二"), ("ins", "三"), ("regular", "条 本契約")]
    INRUN = [("regular", "de "), ("del", "ka"), ("regular", "t"), ("ins", "s"), ("regular", " zit hier")]
    CANON = [("ins", "D"), ("del", "Duod"), ("ins", "e"), ("del", "é"), ("regular", "cim"),
             ("ins", "otercera"), ("del", "a"), ("regular", ".- Legislacion y fuero")]
    rc, out, got = scaffold([tcp(1, AFTER), tcp(2, BEFORE), tcp(3, WHOLE), tcp(4, CJK), tcp(5, INRUN),
                             tcp(6, CANON)], "cft_shapes.json")
    a = got.get(1) or []
    ok(" 17 the D04-113 shape - its stem AFTER the edit - is scaffolded, the whole word on the ins and del, "
       "the stem's segment its own placeholder",
       len(a) == 4 and a[1]["en"] == f"{PH}del='Duodecima.-' (rejected)>>"
       and a[2]["en"] == f"{PH}ins='Trecima.-' (accepted)>>" and a[3]["en"].startswith(f"{PH}regular=")
       and "'ecima.-' belongs to the edited word" in a[3]["en"] and a[0]["en"] == "",
       f"en_segments {[s.get('en') for s in a]}")
    b = got.get(2) or []
    ok(" 18 the D04-125 shape - its stem BEFORE the edit - is scaffolded the same way",
       len(b) == 4 and b[1]["en"] == f"{PH}del='Vigesimo' (rejected)>>"
       and b[2]["en"] == f"{PH}ins='Vigesima' (accepted)>>" and b[0]["en"].startswith(f"{PH}regular=")
       and "'Vige' belongs to the edited word" in b[0]["en"] and b[3]["en"] == "",
       f"en_segments {[s.get('en') for s in b]}")
    ok(" 19 a whole-word replacement followed by punctuation is NOT scaffolded", got.get(3) is None,
       f"en_segments {got.get(3)}")
    ok(" 20 a CJK junction is NOT scaffolded", got.get(4) is None, f"en_segments {got.get(4)}")
    c = got.get(5) or []
    ok(" 21 regular text glued inside the run counts as a piece: scaffolded, its own slot left empty",
       len(c) == 5 and c[1]["en"] == f"{PH}del='kat' (rejected)>>" and c[3]["en"] == f"{PH}ins='ts' (accepted)>>"
       and c[2]["en"] == "" and c[0]["en"] == "" and c[4]["en"] == "", f"en_segments {[s.get('en') for s in c]}")
    d = got.get(6) or []
    ok(" 22 the canonical letter-by-letter cluster is scaffolded exactly as the step document shows",
       [s.get("en") for s in d] == [f"{PH}ins='Decimotercera' (accepted)>>", f"{PH}del='Duodécima' (rejected)>>",
                                     "", "", "", "", "", ""], f"en_segments {[s.get('en') for s in d]}")
    ok(" 23 every run prints tracked-change paragraphs examined against scaffolded: 6 and 4 here",
       rc == 0 and "Examined 6 tracked-change paragraph(s); scaffolded 4." in out, f"rc={rc}")
    rc, out, _ = scaffold([tcp(1, WHOLE), tcp(2, CJK), para(3, "Gewone tekst.")], "cft_none.json")
    ok("    ... and on a document with no cluster: 2 and 0, and still nothing to do",
       rc == 0 and "Examined 2 tracked-change paragraph(s); scaffolded 0." in out
       and "Nothing to do." in out, f"rc={rc}")
    rc, out, got = scaffold([tcp(6, CANON)], "cft_direct.json", "--idx", "6", "--ins-en", "Clause 13",
                            "--del-en", "Clause 12")
    ok(" 24 direct fill is unchanged: the English lands on the first ins and del, the rest empty",
       rc == 0 and [s.get("en") for s in got.get(6) or []] == ["Clause 13", "Clause 12", "", "", "", "", "", ""],
       f"rc={rc}, en_segments {[s.get('en') for s in got.get(6) or []]}")

# =====================================================================================================
if section("validate_translations.py", "C30 - validate_translations.py: a leftover <<TRANSLATE: placeholder is refused"):
    PH = "<<TRANSLATE: "
    MARK = "Quillwort"                               # a word that must never be printed

    def validate(rows, name):
        p = write(f"{name}/paragraphs.json", rows)
        rc, out = run("validate_translations.py", p)
        return rc, out, (p.parent / ".validate-state.json").is_file()

    seg_para = {"idx": 2, "text": "Clausula Duodecima", "style": "Normal", "has_track_changes": True,
                "en": "Clause 13", "en_segments": [{"type": "regular", "en": "Clause "},
                                                   {"type": "ins", "en": f"{PH}ins='x' (accepted)>>"},
                                                   {"type": "del", "en": "12"}]}
    base = [para(0, "De huurder betaalt.", "The Lessee pays."), para(1, "Acme B.V.", "Acme B.V.")]
    rc, out, state = validate(base + [para(3, "Een zin.", f"A {MARK} {PH}del='y' (rejected)>> sentence.")],
                              "vt_en")
    ok(" 25 a placeholder left in en is refused, exit 2, the paragraph named, no text printed, no state written",
       rc == 2 and "idx 3: en" in out and MARK not in out and not state, f"rc={rc}, state written={state}")
    rc, out, state = validate(base + [seg_para], "vt_seg")
    ok(" 26 a placeholder left in an en_segments entry is refused, exit 2, naming the segment",
       rc == 2 and "idx 2: en_segments[1]" in out and not state, f"rc={rc}, state written={state}")
    rc, out, state = validate(base + [para(4, "", f"{PH}ins='z' (accepted)>>")], "vt_notext")
    ok(" 27 a placeholder on a paragraph with no source text is still refused", rc == 2, f"rc={rc}")
    filled = dict(seg_para, en_segments=[{"type": "regular", "en": "Clause "}, {"type": "ins", "en": "13"},
                                         {"type": "del", "en": "12"}])
    rc, out, state = validate(base + [filled], "vt_filled")
    ok(" 28 the same scaffold filled in passes and records its state                              (unchanged)",
       rc == 0 and state, f"rc={rc}, state written={state}")
    # Step 3b scaffolds BEFORE translation and this script runs after every batch, so a tracked-change
    # paragraph due in a later batch still carries its placeholders -- and apply skips a paragraph with no
    # `en`, so none of its segments can reach the document. Refusing it would block batch 1's validation.
    pending = dict(seg_para, idx=5)
    del pending["en"]
    rc, out, state = validate(base + [pending], "vt_pending")
    ok(" 29 a scaffolded paragraph NOT YET TRANSLATED - placeholders in its segments, no en - is not refused, "
       "so a mid-translation batch still validates                                              (unchanged)",
       rc != 2 and "is still in paragraphs.json" not in out and state, f"rc={rc}, state written={state}")

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
