# -*- coding: utf-8 -*-
"""BRANCH 12 SLICE 12b's corpus arm: translate_numbering over the 13 recorded runs, the working tree against a
pinned BASELINE revision, with each document's TRUE source language declared at Step 1c -- and again with nothing
declared, so the guess the skill still acts on is measured too.

Nothing in this repository had ever run translate_numbering over a real document: the delivered-document arm
reuses July's numbering.xml as it stands. So this is new for the same reason tools/postprocess_corpus_arm.py was.

READ-ONLY over the logs and corpus folders: every original is copied to a temporary folder, and the run's own
output -- which quotes format strings -- is parsed and never printed. PRINTS doc-ids, language names, counts and
exit codes only (CLAUDE.md 5.6).

THE BASELINE RUN is the revision's script as Step 8a documented it, with --language TRUE (its scripts read no
declaration); the undeclared arm's baseline passes nothing, the guess both versions act on.

THE ACCEPTANCE (Wouter, 2026-10-12, section 3.2 of PLAN-2-step-b.md), DECLARED arm:
  1  D03, D03B and D07 say NOT SUPPORTED and never "pure numeric/symbol"; D03 and D03B list their 8 distinct
     strings (10 occurrences)
  2  no run says "pure numeric/symbol" while it lists a string NOT TRANSLATED
  3  no supported document stops (exit 1) -- the stop fires on nothing the corpus holds
  4  every numbering.xml byte-identical to the baseline's, except D05 and D06, where exactly ONE format string
     each differs: the keyword-before-number string the maps did not hold, now translated
UNDECLARED arm: every run says NOT SUPPORTED and exits 0; its byte differences are counted and printed.

THE BASELINE IS A REVISION, never HEAD or "the current file" (house hygiene rule 4): by default the merge-base
of HEAD and origin/main, and the arm is VOID when the baseline's translate_numbering.py equals the working
tree's -- a self-comparison reports 100% carried.

    uv run --with lxml python tools/numbering_corpus_arm.py [--variant uk|us] [--ref <rev>]
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
import zipfile
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.dont_write_bytecode = True
os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from lxml import etree  # noqa: E402
from sibling_dirs import corpus_dirs, logs_dir  # noqa: E402  (register I-40)

ap = argparse.ArgumentParser()
ap.add_argument("--variant", default="uk", choices=("uk", "us"))
ap.add_argument("--ref", default=None, help="the baseline revision (default: merge-base of HEAD and origin/main)")
args = ap.parse_args()
WNS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
W = f"{{{WNS}}}"
DOC_ID = re.compile(r"\bD\d{2}B?\b")
# Each corpus document's TRUE source language, by doc-id and language only (EVIDENCE-measurement.md section 1);
# the same table tools/delivered_corpus_arm.py carries. D07 is already English, the target.
TRUE_LANGUAGE = {"D01": "hungarian", "D02": "dutch", "D03": "norwegian", "D03B": "norwegian", "D04": "spanish",
                 "D05": "italian", "D06": "italian", "D07": "english", "D08": "finnish", "D09": "hungarian",
                 "D10": "polish", "D11": "japanese"}
UNSUPPORTED = {"D03", "D03B", "D07"}
# Measured 2026-10-12 (temp/s1012_probe_12b4.py): 10 word-bearing occurrences each, 8 DISTINCT strings -- the
# run lists distinct strings. This arm's first run pinned 10 and was refuted by its own output.
LISTED = {"D03": 8, "D03B": 8}
PARTS = 11                                # originals carrying a numbering part, measured the same day
MOVES = {"D05": 1, "D06": 1}              # the keyword-before-number string each, measured the same day
ENV = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1", PYTHONDONTWRITEBYTECODE="1")
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


def source_paragraphs(cand):
    try:
        with zipfile.ZipFile(cand) as z:
            root = etree.fromstring(z.read("word/document.xml"))
    except Exception:  # noqa: BLE001 -- an unreadable candidate is simply not a match
        return None
    out = []
    for p in root.iter(f"{W}p"):
        pieces = [el.text if el.tag == f"{W}t" else "\n" for el in p.iter()
                  if (el.tag == f"{W}t" and el.text) or (el.tag == f"{W}br" and el.get(f"{W}type", "") != "page")]
        out.append("".join(pieces).strip())
    return out


def match_source(wd, notes, corpus, cache):
    wanted = {(e.get("text") or "").strip() for e in notes if isinstance(e, dict) and (e.get("text") or "").strip()}
    best, frac = None, 0.0
    for group in [sorted(wd.glob("*.docx"))] + [sorted(d.glob("*.docx")) for d in corpus]:
        for cand in group:
            key = str(cand)
            if key not in cache:
                cache[key] = source_paragraphs(cand)
            t = cache[key]
            if not t or not wanted:
                continue
            f = len(wanted & set(t)) / len(wanted)
            if f > frac:
                best, frac = cand, f
        if frac >= 0.9:
            break
    return best if best is not None and frac >= 0.5 else None


def lvltexts(path):
    return re.findall(r'<w:lvlText\s+w:val="([^"]*?)"', path.read_text(encoding="utf-8")) if path.is_file() else []


def run_tn(scripts, orig, notes_src, declared, tmp, tag, explicit=None):
    """One run. `declared` writes the Step 1c declaration; `explicit` passes --language instead -- the
    baseline's form of the same run, its scripts predating the declaration."""
    wd = tmp / tag
    (wd / "final" / "word").mkdir(parents=True)
    shutil.copyfile(notes_src, wd / "paragraphs.json")
    if declared:
        (wd / "source_language.json").write_bytes(json.dumps({"source_language": declared}).encode() + b"\n")
    out = wd / "final" / "word" / "numbering.xml"
    lang = ["--language", explicit] if explicit else []
    r = subprocess.run(["uv", "run", "--with", "lxml", "python", str(scripts / "translate_numbering.py"),
                        str(orig), str(out)] + lang, capture_output=True, text=True, encoding="utf-8",
                       errors="replace", cwd=str(ROOT), env=ENV, timeout=900)
    listed = re.search(r"NOT TRANSLATED — (\d+) numbering format string", r.stdout)
    return {"rc": r.returncode, "out": out, "vals": lvltexts(out), "bytes": out.read_bytes() if out.is_file() else b"",
            "ns": "NOT SUPPORTED" in r.stdout, "pure": "pure numeric/symbol" in r.stdout,
            "listed": int(listed.group(1)) if listed else 0, "gate": "SKILL GATE FIRED" in r.stdout}


def main():
    ref = args.ref
    if not ref:
        mb = git("merge-base", "HEAD", "origin/main")
        ref = mb.stdout.strip()
        if mb.returncode or not ref:
            void("the baseline", "no merge-base of HEAD and origin/main; pass --ref")
            return finish()
    rel = f"{args.variant}/scripts/translate_numbering.py"
    base_src = git("show", f"{ref}:{rel}")
    now_src = (ROOT / rel).read_text(encoding="utf-8")
    print(f"[{args.variant}] baseline {ref[:12]} · working tree")
    if base_src.returncode:
        void("the baseline", f"{rel} is not at {ref[:12]}")
        return finish()
    if base_src.stdout == now_src:
        void("the baseline", "its translate_numbering.py equals the working tree's: a self-comparison")
        return finish()
    tmp = Path(tempfile.mkdtemp(prefix="b12b-numarm-"))
    try:
        base_dir = tmp / "base"
        base_dir.mkdir()
        arc = subprocess.run(["git", "archive", ref, f"{args.variant}/scripts"], cwd=ROOT, capture_output=True)
        subprocess.run(["tar", "-x", "-C", str(base_dir)], input=arc.stdout, check=True)
        base_scripts = base_dir / args.variant / "scripts"
        now_scripts = ROOT / args.variant / "scripts"
        logs = logs_dir()
        workdirs = sorted({p.parent for p in logs.rglob("paragraphs.json")})
        corpus = corpus_dirs(ROOT)
        cache, seen = {}, 0
        print(f"  frozen workdirs {len(workdirs)} · corpus folders {len(corpus)}")
        for n, wd in enumerate(workdirs, 1):
            ids = DOC_ID.findall(str(wd.relative_to(logs)))
            did = ids[-1] if ids else f"D??{n}"
            notes_path = wd / "paragraphs.json"
            notes = json.loads(notes_path.read_text(encoding="utf-8"))
            src = match_source(wd, notes, corpus, cache)
            if src is None:
                void(f"{did}", "no original matched")
                continue
            orig = tmp / f"orig-{n}.docx"
            orig.write_bytes(src.read_bytes())
            with zipfile.ZipFile(orig) as z:
                has_part = "word/numbering.xml" in z.namelist()
            if not has_part:
                print(f"  {did:5} no numbering part — nothing to translate, nothing measured")
                continue
            seen += 1
            true = TRUE_LANGUAGE.get(did)
            for arm, declared in (("declared", true), ("undeclared", None)):
                # The baseline is TODAY'S DOCUMENTED RUN: Step 8a passed --language, the baseline's scripts
                # reading no declaration -- so the declared arm is compared with that, never with a guess.
                b = run_tn(base_scripts, orig, notes_path, None, tmp, f"{n}-{arm}-base", explicit=declared)
                w = run_tn(now_scripts, orig, notes_path, declared, tmp, f"{n}-{arm}-now")
                moved = sum(1 for x, y in zip(b["vals"], w["vals"]) if x != y) + abs(len(b["vals"]) - len(w["vals"]))
                print(f"  {did:5} {arm:10} {true:10} rc {b['rc']}->{w['rc']}  NOT SUPPORTED {w['ns']!s:5} "
                      f"listed {w['listed']:>2}  pure {w['pure']!s:5}  format strings moved {moved}")
                ok(f"{did} {arm}: never 'pure numeric/symbol' while a string is listed",
                   not (w["pure"] and w["listed"]))
                want = MOVES.get(did, 0)
                if arm == "declared":
                    if did in UNSUPPORTED:
                        ok(f"{did} declared {true}: NOT SUPPORTED, never 'pure numeric/symbol'",
                           w["ns"] and not w["pure"])
                    if did in LISTED:
                        ok(f"{did} declared: lists its {LISTED[did]} strings", w["listed"] == LISTED[did],
                           f"listed {w['listed']}")
                    ok(f"{did} declared: no stop on the corpus (exit 0)", w["rc"] == 0 and not w["gate"],
                       f"rc {w['rc']}")
                    blank = re.compile(rb'(<w:lvlText\s+w:val=")[^"]*(")')
                    ok(f"{did} declared: exactly {want} format string(s) moved against the baseline, "
                       "every other byte identical",
                       moved == want and blank.sub(rb"\1\2", w["bytes"]) == blank.sub(rb"\1\2", b["bytes"]),
                       f"moved {moved}")
                else:
                    ok(f"{did} undeclared: says NOT SUPPORTED — it ran on a guess", w["ns"])
                    ok(f"{did} undeclared: a guess never stops (exit 0)", w["rc"] == 0, f"rc {w['rc']}")
        ok(f"every document with a numbering part was measured ({seen} of {PARTS})", seen == PARTS, f"{seen}")
    finally:
        # The arm's own temporary tree, and nothing else: the one deletion
        # tests/test_no_unguarded_restore.py allows in a finally.
        shutil.rmtree(tmp, ignore_errors=True)
    return finish()


def finish():
    print("\n" + "=" * 92)
    print(f"  {CHECKED} check(s), {len(FAIL)} failure(s), {len(VOIDED)} void   [{args.variant}]")
    for f in FAIL:
        print(f"    FAIL  {f}")
    return 2 if VOIDED else (1 if FAIL else 0)


if __name__ == "__main__":
    sys.exit(main())
