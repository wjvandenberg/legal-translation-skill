# -*- coding: utf-8 -*-
"""BRANCH 12 SLICE 12c's corpus arm: validate_translations' character-ratio check over the 13 recorded runs, each
document's TRUE source language declared at Step 1c, the working tree against a pinned BASELINE revision.

READ-ONLY over the logs folder: each run's paragraphs.json is copied to a temporary folder, and the script's
output - which previews the source and the English of every flagged paragraph - is parsed and never printed.
PRINTS doc-ids, language names, paragraph indices, ratios, counts and exit codes only (CLAUDE.md 5.6).
Each copy is validated with --accept-large-batch, the documented route for re-validating a whole document at once:
a copy carries no batch state, so the 35-paragraph cap would otherwise refuse every one before any ratio.

THE ACCEPTANCE (Wouter, 2026-10-13, section 3.2 of PLAN-2-step-b.md), on translations that shipped:
  1  exactly the measured WARN set - D02 10, D05 4 and 15, D09 21, D11 39 - and 0 BLOCK; the five listed for
     Wouter's page read (temp/s1013_ratio_expect.py measured it before the script was changed)
  2  D07, declared English, says NOT APPLICABLE and never PASS
  3  no document's verdict reads PASS unscaled - every one was declared
  4  the BASELINE (the floor of 150, no scaling) flags none of them - the five are this slice's reach, not a
     regression it hides
THE BASELINE IS A REVISION (house hygiene rule 4): by default the merge-base of HEAD and origin/main, and the
arm is VOID when the baseline's validate_translations.py equals the working tree's.

    uv run python tools/ratio_corpus_arm.py [--variant uk|us] [--ref <rev>]
"""
import argparse
import io
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.dont_write_bytecode = True
os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from sibling_dirs import logs_dir  # noqa: E402  (register I-40)

ap = argparse.ArgumentParser()
ap.add_argument("--variant", default="uk", choices=("uk", "us"))
ap.add_argument("--ref", default=None, help="the baseline revision (default: merge-base of HEAD and origin/main)")
args = ap.parse_args()
DOC_ID = re.compile(r"\bD\d{2}B?\b")
# Each corpus document's TRUE source language, by doc-id and language only (EVIDENCE-measurement.md section 1);
# the same table tools/delivered_corpus_arm.py and tools/numbering_corpus_arm.py carry.
TRUE_LANGUAGE = {"D01": "hungarian", "D02": "dutch", "D03": "norwegian", "D03B": "norwegian", "D04": "spanish",
                 "D05": "italian", "D06": "italian", "D07": "english", "D08": "finnish", "D09": "hungarian",
                 "D10": "polish", "D11": "japanese"}
EXPECTED_WARN = {"D02": [10], "D05": [4, 15], "D09": [21], "D11": [39]}      # measured 2026-10-13
WORKDIRS = 13
ENV = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1", PYTHONDONTWRITEBYTECODE="1")
FLAG = re.compile(r"^\s+idx (\S+): ratio=([\d.]+)", re.M)
FAIL, CHECKED, VOIDED = [], 0, []


def ok(label, cond, detail=""):
    global CHECKED
    CHECKED += 1
    print(f"  {'OK  ' if cond else 'XX  '} {label}" + (f"   ({detail})" if detail and not cond else ""))
    if not cond:
        FAIL.append(label)


def void(label, why):
    VOIDED.append(label)
    print(f"  ??   {label}   VOID — {why}")


def git(*a):
    return subprocess.run(["git", *a], cwd=ROOT, capture_output=True, text=True, encoding="utf-8")


def section(out, head):
    """The `idx N: ratio=R` lines under one of the script's WARN or BLOCK headings, as [(idx, ratio)]."""
    i = out.find(head)
    if i < 0:
        return []
    body = out[i:]
    stop = min([j for j in (body.find("\n  WARN —", 1), body.find("\n  BLOCK —", 1), body.find("\n=====", 1))
                if j > 0] or [len(body)])
    # The script prints `idx ?` for a paragraph with no index: kept as text, so it is counted and never crashes.
    return [(int(m.group(1)) if m.group(1).isdigit() else m.group(1), float(m.group(2)))
            for m in FLAG.finditer(body[:stop])]


def validate(scripts, notes_src, language, tmp, tag):
    """Copy the notes, declare the language, run the check: (rc, warn [(idx, ratio)], block, verdict line)."""
    wd = tmp / tag
    wd.mkdir(parents=True)
    shutil.copyfile(notes_src, wd / "paragraphs.json")
    d = subprocess.run([sys.executable, str(scripts / "source_language_markers.py"), "--declare", language,
                        str(wd)], capture_output=True, text=True, encoding="utf-8", errors="replace", env=ENV)
    if d.returncode != 0:
        return None
    r = subprocess.run([sys.executable, str(scripts / "validate_translations.py"), str(wd / "paragraphs.json"),
                        "--accept-large-batch"], capture_output=True, text=True, encoding="utf-8",
                       errors="replace", env=ENV)
    out = (r.stdout or "") + (r.stderr or "")
    verdict = next((ln.strip() for ln in reversed(out.splitlines())
                    if ln.strip().startswith(("PASS", "NOT APPLICABLE", "** WARN", "*** BLOCK"))), "")
    return (r.returncode, section(out, "WARN — Possibly incomplete"), section(out, "BLOCK — Critically short"),
            verdict, "NOT APPLICABLE" in out)


LOGS = logs_dir()
workdirs = sorted({p.parent for p in LOGS.rglob("paragraphs.json")})
print(f"[{args.variant}] ratio corpus arm · frozen workdirs {len(workdirs)}")
ref = args.ref or git("merge-base", "HEAD", "origin/main").stdout.strip()
SCRIPTS = ROOT / args.variant / "scripts"
with tempfile.TemporaryDirectory(prefix="ratio-arm-", ignore_cleanup_errors=True) as td:
    tmp = Path(td)
    base = tmp / "base_scripts"
    base.mkdir()
    for name in ("validate_translations.py", "source_language_markers.py"):
        blob = subprocess.run(["git", "show", f"{ref}:{args.variant}/scripts/{name}"], cwd=ROOT,
                              capture_output=True)
        (base / name).write_bytes(blob.stdout if blob.returncode == 0 else b"")
    same = (base / "validate_translations.py").read_bytes() == (SCRIPTS / "validate_translations.py").read_bytes()
    print(f"  baseline {ref[:12]}: validate_translations.py {'EQUALS' if same else 'differs from'} the working tree's")
    rows = {}
    if len(workdirs) != WORKDIRS:
        void("the corpus", f"{len(workdirs)} workdirs found, {WORKDIRS} expected")
    elif same:
        void("the baseline comparison", "the baseline's script equals the working tree's - a self-comparison")
    else:
        for n, wd in enumerate(workdirs):
            ids = DOC_ID.findall(str(wd.relative_to(LOGS)))
            did = ids[-1] if ids else "?"
            lang = TRUE_LANGUAGE.get(did)
            if lang is None:
                void(f"workdir {n}", "no doc-id")
                continue
            now = validate(SCRIPTS, wd / "paragraphs.json", lang, tmp, f"now{n}")
            then = validate(base, wd / "paragraphs.json", lang, tmp, f"base{n}")
            if now is None or then is None:
                void(did, "the declaration could not be written")
                continue
            rows.setdefault(did, []).append((lang, now, then))

    print("\n  doc   language    rc  warn (idx:ratio)             block  baseline warn/block  verdict")
    for did, runs in sorted(rows.items()):
        for lang, (rc, warn, block, verdict, na), (_, bwarn, bblock, _, _) in runs:
            w = " ".join(f"{i}:{r:.2f}" for i, r in warn) or "-"
            print(f"  {did:5} {lang:10} {rc:3}  {w:28} {len(block):5}  {len(bwarn):>4}/{len(bblock):<4}           "
                  f"{verdict.split(':')[0][:40]}")

    if rows:
        print("\n  ACCEPTANCE")
        got = {did: sorted({i for _, (_, warn, _, _, _), _ in runs for i, _ in warn}) for did, runs in rows.items()}
        got = {d: v for d, v in got.items() if v}
        ok(f"exactly the measured WARN set: {EXPECTED_WARN}", got == EXPECTED_WARN, f"got {got}")
        ok("0 BLOCK on any document", all(not blk for runs in rows.values() for _, (_, _, blk, _, _), _ in runs))
        d07 = rows.get("D07", [])
        ok("D07, declared English: NOT APPLICABLE, never PASS", bool(d07) and all(
            na and not v.startswith("PASS") for _, (_, _, _, v, na), _ in d07))
        ok("no verdict reads PASS unscaled - every document was declared", all(
            "unscaled" not in v for runs in rows.values() for _, (_, _, _, v, _), _ in runs))
        ok("the baseline flags none of them", all(not bw and not bb for runs in rows.values()
                                                  for _, _, (_, bw, bb, _, _) in runs))
        ok(f"all {WORKDIRS} workdirs validated", sum(len(r) for r in rows.values()) == WORKDIRS)

print(f"\n  {CHECKED} check(s), {len(FAIL)} failure(s), {len(VOIDED)} void")
sys.exit(1 if FAIL or VOIDED else 0)
