# -*- coding: utf-8 -*-
"""notes_corpus_arm.py - branch 11 slice 4b's corpus acceptance: the four notes-side gates, RUN over the
13 frozen workdirs (PLAN-2-step-b.md section 3.2, block "4b - C13, C4, C14", its CHECKED AGAINST line).

Each workdir's paragraphs.json and .validate-state.json are COPIED into a temporary folder and the
variant's real scripts run there, so nothing is ever written into the logs folder. PRINTS NO DOCUMENT
TEXT AND NO FILENAME: doc-ids, counts and exit codes only (CLAUDE.md 5.6) -- every script's own output,
which quotes the document, is parsed and discarded.

  C13  validate_en_runs.py over each copy: every paragraph carrying en_runs TILES en -- pinned 729 of
       729, none refused -- and a second, independent reader of the same JSON must agree with it
  C4   verify_diligence.py over each copy: Step 4 + 4b PASSes on 13 of 13 by declaration, D07 reading
       52 declared, 11 changed, 41 kept as the source
  C14  coalesce_fragmented_tcs.py --dry-run over each copy: clusters D04 3, D02 2, D11 1, every other 0,
       and the examined-against-scaffolded line on every run
  C30  validate_translations.py over each copy: no workdir carries a <<TRANSLATE: placeholder, so none
       is refused -- and an independent count of the JSON agrees

With --ref <commit> the scripts come from that commit and NOTHING IS ASSERTED: the same measures are
printed, which is how the start of the branch is read against the pins.

    uv run --with lxml python tools/notes_corpus_arm.py
    uv run --with lxml python tools/notes_corpus_arm.py --variant us
    uv run --with lxml python tools/notes_corpus_arm.py --ref 0bacc51      # measure only
"""
import argparse
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.dont_write_bytecode = True
os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")

ROOT = Path(__file__).resolve().parent.parent
LOGS = Path(os.environ.get("LT_LOGS_DIR", ROOT.parent / "legal-translation-logs"))
DOC_ID = re.compile(r"\bD\d{2}B?\b")
ENV = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1", PYTHONDONTWRITEBYTECODE="1")
ap = argparse.ArgumentParser()
ap.add_argument("--variant", choices=("uk", "us"), default="uk")
ap.add_argument("--ref", default=None, help="take the scripts from this commit and assert nothing")
args = ap.parse_args()
TMP = Path(tempfile.mkdtemp(prefix="b11s4b-notes-corpus-"))
FAIL, VOID, CHECKED = [], [], 0

if args.ref:
    SCRIPTS = TMP / "scripts"
    SCRIPTS.mkdir()
    for n in subprocess.run(["git", "ls-tree", "-r", "--name-only", args.ref, "--", f"{args.variant}/scripts"],
                            capture_output=True, text=True, check=True, cwd=str(ROOT)).stdout.split():
        (SCRIPTS / Path(n).name).write_bytes(subprocess.run(["git", "show", f"{args.ref}:{n}"],
                                                            capture_output=True, check=True, cwd=str(ROOT)).stdout)
else:
    SCRIPTS = ROOT / args.variant / "scripts"


def ok(label, cond, detail=""):
    global CHECKED
    CHECKED += 1
    print(f"  {'OK  ' if cond else 'XX  '} {label}" + (f"   ({detail})" if detail and not cond else ""))
    if not cond:
        FAIL.append(label)


def run(script, *argv):
    r = subprocess.run([sys.executable, str(SCRIPTS / script), *map(str, argv)], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", env=ENV, cwd=str(TMP), timeout=900)
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def tiles(p):
    """The second reader: does this paragraph's en_runs tile its raw en? Written apart from the script."""
    runs, en = p["en_runs"], p.get("en") if isinstance(p.get("en"), str) else ""
    if not isinstance(runs, list) or not all(isinstance(s, dict) for s in runs):
        return False
    sp = [(s.get("start"), s.get("end")) for s in runs]
    if not all(type(a) is int and type(b) is int for a, b in sp):
        return False
    edges = [0] + [b for _, b in sp]
    return all(a == edges[k] and a <= b for k, (a, b) in enumerate(sp)) and sp[-1][1] == len(en)


def placeholders(paras):
    n = 0
    for p in paras:
        if not isinstance(p, dict):
            continue
        n += "<<TRANSLATE:" in (p.get("en") or "")
        n += sum(1 for s in (p.get("en_segments") or []) if isinstance(s, dict)
                 and "<<TRANSLATE:" in (s.get("en") or ""))
    return n


if not LOGS.is_dir():
    print("  VOID - the logs root is not present; nothing was measured")
    sys.exit(2)
workdirs = sorted({p.parent for p in LOGS.rglob("paragraphs.json")})
keys, seen = [], Counter()
for wd in workdirs:
    ids = DOC_ID.findall(str(wd.relative_to(LOGS)))
    did = ids[-1] if ids else "D??"
    seen[did] += 1
    keys.append((f"{did}#{seen[did]}" if seen[did] > 1 else did, wd))
print(f"  frozen workdirs enumerated: {len(workdirs)} · scripts: {args.ref or 'working tree'} {args.variant}")

COVER = re.compile(r"^\s+(PASS|FAIL|WARN) — (.*(?:translated|declared) paragraphs.*)$", re.M)
EXAMINED = re.compile(r"Examined (\d+) tracked-change paragraph\(s\); scaffolded (\d+)\.")
rows, not_read = {}, []
for key, wd in keys:
    here = TMP / key
    here.mkdir()
    try:
        shutil.copyfile(wd / "paragraphs.json", here / "paragraphs.json")
        if (wd / ".validate-state.json").is_file():
            shutil.copyfile(wd / ".validate-state.json", here / ".validate-state.json")
        paras = json.loads((here / "paragraphs.json").read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        not_read.append((key, type(e).__name__))
        continue
    r = {"carrying": sum(1 for p in paras if isinstance(p, dict) and p.get("en_runs"))}
    r["tile_second_reader"] = sum(1 for p in paras if isinstance(p, dict) and p.get("en_runs") and tiles(p))
    rc, out = run("validate_en_runs.py", here / "paragraphs.json")
    r["ver_rc"] = rc
    r["ver_refused"] = len(re.findall(r"^  idx \S+: ", out, re.M)) if "do not tile en" in out else 0
    vd = here / "vd"
    vd.mkdir()
    shutil.copyfile(here / "paragraphs.json", vd / "paragraphs.json")
    if (here / ".validate-state.json").is_file():
        shutil.copyfile(here / ".validate-state.json", vd / ".validate-state.json")
    rc, out = run("verify_diligence.py", vd, "--report-only")
    m = COVER.search(out)
    r["c4_sev"] = m.group(1) if m else None
    nums = {w: int(n) for n, w in re.findall(r"(\d+) (declared|changed|kept as the source|translated)", m.group(2))} \
        if m else {}
    r["c4"] = nums
    shutil.copyfile(wd / "paragraphs.json", here / "coalesce.json")
    rc, out = run("coalesce_fragmented_tcs.py", here / "coalesce.json", "--dry-run")
    r["cft_rc"] = rc
    r["clusters"] = len(re.findall(r"fragmented cluster segments\[", out))
    m = EXAMINED.search(out)
    r["examined"] = (int(m.group(1)), int(m.group(2))) if m else None
    r["tc_paras"] = sum(1 for p in paras if isinstance(p, dict) and p.get("has_track_changes")
                        and isinstance(p.get("tc_segments"), list) and p.get("tc_segments"))
    r["ph_json"] = placeholders(paras)
    rc, out = run("validate_translations.py", here / "paragraphs.json")
    r["vt_rc"] = rc
    r["vt_ph_refused"] = "placeholder\nis still in paragraphs.json" in out or "is still in paragraphs.json" in out
    rows[key] = r

print(f"  workdirs read: {len(rows)} of {len(keys)}" + (f" · NOT READ: {not_read}" if not_read else ""))
print("\n   key      en_runs  tile(2nd)  refused  ver_rc | C4 sev  declared changed kept | tc-paras clusters "
      "examined | placeholders refused vt_rc")
for key, r in rows.items():
    c4 = r["c4"]
    print(f"   {key:7} {r['carrying']:8} {r['tile_second_reader']:9} {r['ver_refused']:8} {r['ver_rc']:6} | "
          f"{str(r['c4_sev']):6} {c4.get('declared', c4.get('translated', '-')):>8} {c4.get('changed', '-'):>7} "
          f"{c4.get('kept as the source', '-'):>4} | {r['tc_paras']:8} {r['clusters']:8} {str(r['examined']):>9} | "
          f"{r['ph_json']:12} {str(r['vt_ph_refused']):7} {r['vt_rc']}")
tot = sum(r["carrying"] for r in rows.values())
tot2 = sum(r["tile_second_reader"] for r in rows.values())
refused = sum(r["ver_refused"] for r in rows.values())
print(f"   TOTAL   en_runs {tot}, tiling by the second reader {tot2}, refused by validate_en_runs {refused}")

if args.ref:
    print("\n  --ref: measured only, nothing asserted")
else:
    print()
    whole = len(rows) == len(keys) == 13 and not not_read
    ok(f"the denominator: 13 frozen workdirs, every one read ({len(rows)} of {len(keys)})", whole)
    ok(f"C13: 729 of 729 paragraphs carrying en_runs tile en, none refused (carrying {tot}, refused {refused})",
       tot == 729 and refused == 0 and all(r["ver_rc"] in (0, 1) for r in rows.values()))
    ok(f"C13: the second reader agrees, {tot2} of {tot}", tot2 == tot)
    passes = [k for k, r in rows.items() if r["c4_sev"] == "PASS" and "declared" in r["c4"]]
    ok(f"C4: Step 4 + 4b PASSes by declaration on 13 of 13 ({len(passes)})", len(passes) == 13,
       f"not: {[k for k in rows if k not in passes]}")
    d07 = rows.get("D07", {}).get("c4", {})
    ok("C4: D07 reads 52 declared, 11 changed, 41 kept as the source",
       (d07.get("declared"), d07.get("changed"), d07.get("kept as the source")) == (52, 11, 41), f"{d07}")
    want = {"D04": 3, "D02": 2, "D11": 1}
    got = {k: r["clusters"] for k, r in rows.items()}
    ok("C14: clusters D04 3, D02 2, D11 1, every other workdir 0",
       all(got.get(k, 0) == want.get(k.split("#")[0], 0) for k in got) and all(k in got for k in want), f"{got}")
    ok("C14: every run prints examined against scaffolded, examined = the tracked-change paragraphs",
       all(r["examined"] is not None and r["examined"][0] == r["tc_paras"] for r in rows.values()),
       f"{ {k: (r['examined'], r['tc_paras']) for k, r in rows.items()} }")
    ok("C30: no workdir carries a <<TRANSLATE: placeholder, and none is refused",
       all(r["ph_json"] == 0 and not r["vt_ph_refused"] for r in rows.values()))

shutil.rmtree(TMP, ignore_errors=True)
print("\n" + "=" * 96)
print(f"  notes_corpus_arm: {CHECKED} check(s), {len(FAIL)} failure(s), {len(VOID)} void")
for f in FAIL:
    print(f"    XX  {f}")
print("=" * 96)
sys.exit(1 if FAIL else 0)
