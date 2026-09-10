# -*- coding: utf-8 -*-
"""BRANCH 8's CORPUS ARM — the extraction-completeness check over the real documents.

WHY THIS TOOL EXISTS RATHER THAN A RUN OF apply_corpus_diff.py, AND IT IS DECLARED HERE
BEFORE ANY RESULT IS READ. `tools/apply_corpus_diff.py` drives APPLY. Branch 8 changes
neither apply nor any delivered byte -- it adds a read-only mode to validate_apply and a
step-document instruction -- so that tool's two arms are byte-identical BY DESIGN and its
"13 byte-identical, 0 unexplained" is a REGRESSION CHECK that proves nothing whatever about
this branch. An all-quiet run there would be exactly what a stale pin produces. This file is
the acceptance instrument; that one is the guard that nothing else moved.

WHAT PLAN-2-step-b.md SECTION 4 PREDICTS, quoted so the result is judged against a
condition written before it was measured: "Branch 8 is self-verifying against the corpus:
run it over all eleven frozen intermediates and it must report zero loss on every one,
since the deliverables were graded complete. Any hit is either a real historical loss or a
bug in the check -- and either result is worth having."

THAT PREDICTION IS RIGHT ABOUT THE BODY AND WRONG ABOUT THE AUXILIARY PARTS, measured
before the check was written (temp/probe_b8_*.py):

    BODY  zero uncaptured paragraphs on every reachable frozen intermediate. This is the
          CALIBRATION, not the test -- it says the instrument does not cry wolf, and it is
          what makes any future non-zero a real regression.
    AUX   40 paragraphs across 6 documents that no capture accounts for, including
          word/footnotes.xml on two documents where NO footnote capture exists in any form
          and footnotes.json appears in 0 of the 13 frozen runs.

The auxiliary figure is a real historical gap and is register C12's defect stated as a
measurement. It is REPORTED here, not failed on: these runs froze at different steps, and a
workdir that never reached Step 8 legitimately has no header/footer capture.

THE POSITIVE CONTROL IS NOT OPTIONAL. A body arm that reports zero everywhere has to be
shown capable of reporting something else, or its zeros are void rather than clean. The
last arm truncates one paragraph in a COPY of one workdir's notes and requires the check to
catch it.

OUTPUT POLICY, the same licence tools/apply_corpus_diff.py and evidence_ls.py operate under:
corpus doc-ids, OOXML part names, and counts. Never a filename, never a directory name below
the logs root, never a paragraph, never any document text. NOTHING IS EVER WRITTEN INTO THE
LOGS FOLDER -- every input is copied into a temporary directory first, because a baseline
the tool measuring it can modify is not a baseline.

    uv run --with lxml python tools/extraction_corpus_arm.py
    uv run --with lxml python tools/extraction_corpus_arm.py --variant us
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

from lxml import etree  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
LOGS = Path(os.environ.get("LT_LOGS_DIR", ROOT.parent / "legal-translation-logs"))
DOC_ID = re.compile(r"\bD\d{2}B?\b")

ap = argparse.ArgumentParser()
ap.add_argument("--variant", default="uk", choices=("uk", "us"))
ap.add_argument("--doc", action="append", help="limit to these corpus doc-ids")
args = ap.parse_args()
SCRIPT = ROOT / args.variant / "scripts" / "validate_apply.py"
ENV = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1",
           PYTHONDONTWRITEBYTECODE="1")


def corpus_dirs():
    """Read from gitignored config, never hardcoded, never printed. In a fresh clone the
    file does not exist and the real arm is simply unavailable -- which this tool SAYS,
    rather than reporting a smaller clean run."""
    out, cfg = [], ROOT / ".claude" / "evidence-dirs.local"
    names = []
    if cfg.is_file():
        names += [ln.strip() for ln in
                  cfg.read_text(encoding="utf-8", errors="replace").splitlines()
                  if ln.strip() and not ln.strip().startswith("#")]
    if os.environ.get("LT_CORPUS_DIR"):
        names.append(os.environ["LT_CORPUS_DIR"])
    for name in names:
        p = Path(name)
        if not p.is_absolute():
            p = (ROOT.parent / name).resolve()
        if p.is_dir() and any(p.glob("*.docx")):
            out.append(p)
    return out


_CACHE = {}


def body_texts(path):
    """extract_paragraphs.py's own full_text contract: w:t text, plus a newline at every
    PLAIN w:br and nothing at a page break. Approximating it here would make this arm
    disagree with the thing it is driving."""
    key = str(path)
    if key in _CACHE:
        return _CACHE[key]
    try:
        with zipfile.ZipFile(path) as z:
            if "word/document.xml" not in z.namelist():
                _CACHE[key] = None
                return None
            root = etree.fromstring(z.read("word/document.xml"))
    except Exception:
        _CACHE[key] = None
        return None
    out = set()
    for p in root.iter(f"{{{W}}}p"):
        pieces = []
        for el in p.iter():
            if el.tag == f"{{{W}}}t" and el.text:
                pieces.append(el.text)
            elif el.tag == f"{{{W}}}br" and el.get(f"{{{W}}}type", "") != "page":
                pieces.append("\n")
        t = "".join(pieces).strip()
        if t:
            out.add(t)
    _CACHE[key] = out
    return out


def run_check(notes_path, original, strict=False):
    argv = ["uv", "run", "--with", "lxml", "python", str(SCRIPT), str(notes_path),
            "--extraction-completeness", str(original)]
    if strict:
        argv.append("--strict")
    r = subprocess.run(argv, capture_output=True, text=True, encoding="utf-8",
                       errors="replace", cwd=str(ROOT), env=ENV, timeout=900)
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def parse(out):
    """Read the figures back out of the report rather than recomputing them: the number
    that matters is the one the check PRINTS, not one this tool derives a second way."""
    body = None
    aux = 0
    parts = []
    for line in out.splitlines():
        s = line.strip()
        if s.startswith("NOT captured"):
            try:
                body = int(s.rsplit(":", 1)[1].strip())
            except ValueError:
                pass
        m = re.match(r"^(word/\S+\.xml)\s+(\d+) text para\(s\),\s+(\d+) carrying letters,"
                     r"\s+(\d+) unaccounted", s)
        if m:
            parts.append((m.group(1), int(m.group(2)), int(m.group(3)), int(m.group(4))))
            aux += int(m.group(4))
    return body, aux, parts


print("=" * 96)
print(f"BRANCH 8 CORPUS ARM — extraction completeness over the frozen intermediates "
      f"({args.variant})")
print("=" * 96)
print("  apply_corpus_diff.py CANNOT SEE THIS BRANCH: it drives apply, and nothing here")
print("  changes apply or any delivered byte. Its byte-identical result is a regression")
print("  check. THIS is the acceptance instrument.")

CORPUS = corpus_dirs()
if not CORPUS or not LOGS.is_dir():
    print("\n  UNAVAILABLE — corpus folder or logs folder not reachable.")
    print("  This is a SKIP, not a pass. Set LT_CORPUS_DIR / LT_LOGS_DIR, or create")
    print("  .claude/evidence-dirs.local. Nothing was examined.")
    sys.exit(0)

docx = sorted(p for d in CORPUS for p in d.glob("*.docx"))
legacy = sorted(p for d in CORPUS for p in d.glob("*.doc"))
wds = sorted({p.parent for p in LOGS.rglob("paragraphs.json")})
print(f"\n  corpus .docx reachable: {len(docx)}   legacy .doc (no script here can read "
      f"one): {len(legacy)}")
print(f"  frozen workdirs: {len(wds)}")

TMP = Path(tempfile.mkdtemp(prefix="b8-corpus-"))
rows, voided = [], []
control_target = None

for wd in wds:
    rel = wd.relative_to(LOGS).as_posix()
    ids = DOC_ID.findall(rel)
    pid = ids[-1] if ids else "?"
    if args.doc and pid not in args.doc:
        continue
    try:
        notes = json.loads((wd / "paragraphs.json").read_text(encoding="utf-8"))
    except Exception as exc:
        voided.append(f"{pid}: paragraphs.json unreadable ({type(exc).__name__})")
        continue
    want = {(e.get("text") or "").strip() for e in notes
            if isinstance(e, dict) and (e.get("text") or "").strip()}
    best, frac = None, 0.0
    for cand in docx:
        texts = body_texts(cand)
        if not texts or not want:
            continue
        f = len(want & texts) / len(want)
        if f > frac:
            best, frac = cand, f
    if best is None or frac < 0.5:
        voided.append(f"{pid}: no corpus .docx matched the notes (best {frac:.0%}) — "
                      f"NOT examined")
        continue

    # COPY IN, NEVER WORK IN PLACE.
    work = TMP / f"{pid}-{len(rows)}"
    work.mkdir(parents=True)
    shutil.copyfile(best, work / "orig.docx")
    for f in list(wd.glob("*.json")) + list(wd.glob(".*.json")):
        try:
            shutil.copyfile(f, work / f.name)
        except OSError as exc:
            voided.append(f"{pid}: could not copy a capture ({type(exc).__name__})")
    rc, out = run_check(work / "paragraphs.json", work / "orig.docx")
    body, aux, parts = parse(out)
    rows.append((pid, frac, rc, body, aux, parts, work))
    if control_target is None and body == 0:
        control_target = (pid, work)

print("\n" + "-" * 96)
print("  BODY — this is the calibration. PLAN-2-step-b.md section 4 predicts zero.")
print("-" * 96)
for pid, frac, rc, body, aux, parts, _w in rows:
    flag = "" if body == 0 else "   <-- UNCAPTURED BODY TEXT"
    print(f"  {pid:>5s}  source matched {frac:5.0%}   rc={rc}   "
          f"body uncaptured = {body}{flag}")

print("\n" + "-" * 96)
print("  AUXILIARY — register C12, reported and not failed on: these runs froze at")
print("  different steps, and a workdir that never reached Step 8 legitimately has no")
print("  header/footer capture.")
print("-" * 96)
part_tally = {}
for pid, frac, rc, body, aux, parts, _w in rows:
    named = [f"{re.sub(r'[0-9]+', '#', p[0]).replace('word/', '')}:{p[3]}"
             for p in parts if p[3]]
    print(f"  {pid:>5s}  {aux:3d} unaccounted   {named if named else ''}")
    for p in parts:
        if p[3]:
            key = re.sub(r"[0-9]+", "#", p[0])
            part_tally[key] = part_tally.get(key, 0) + p[3]

print("\n  BY PART KIND:")
for k in sorted(part_tally, key=lambda x: -part_tally[x]):
    print(f"    {part_tally[k]:4d}  {k}")

# =========================================================================================
# THE POSITIVE CONTROL. A body arm that reports zero everywhere must be shown able to
# report something else, or its zeros are VOID rather than clean.
# =========================================================================================
print("\n" + "-" * 96)
print("  POSITIVE CONTROL — truncate one paragraph in a COPY of one workdir's notes")
print("-" * 96)
control_fired = False
if control_target is None:
    print("  VOID — no document reported a clean body, so there is nothing to plant into.")
else:
    pid, work = control_target
    ctl = TMP / "control"
    shutil.copytree(work, ctl)
    notes = json.loads((ctl / "paragraphs.json").read_text(encoding="utf-8"))
    victim = max((n for n in notes if isinstance(n, dict) and (n.get("text") or "")),
                 key=lambda n: len(n["text"]), default=None)
    if victim is None:
        print("  VOID — that workdir's notes carry no text to truncate.")
    else:
        before = len(victim["text"])
        victim["text"] = victim["text"][:max(3, before // 3)]
        # The runs array repeats the paragraph text, and the body arm is strict against the
        # `text` field alone -- but truncate them too, so the control models the real defect
        # (an extractor that read too little) rather than only the strictness rule.
        for r_ in victim.get("runs") or []:
            if isinstance(r_, dict) and isinstance(r_.get("text"), str):
                r_["text"] = r_["text"][:max(3, len(r_["text"]) // 3)]
        (ctl / "paragraphs.json").write_text(
            json.dumps(notes, ensure_ascii=False, indent=1), encoding="utf-8")
        rc, out = run_check(ctl / "paragraphs.json", ctl / "orig.docx")
        body, _aux, _p = parse(out)
        control_fired = rc == 1 and body == 1
        print(f"  planted on {pid}: one paragraph cut from {before} to "
              f"{len(victim['text'])} chars")
        print(f"  check returned rc={rc}, body uncaptured = {body}   "
              f"{'CONTROL FIRED' if control_fired else 'CONTROL DID NOT FIRE'}")

print("\n" + "=" * 96)
examined = len(rows)
bad_body = [r for r in rows if r[3] != 0]
total_aux = sum(r[4] for r in rows)
print(f"  documents examined: {examined} of {len(wds)} frozen workdirs")
for v in voided:
    print(f"    VOID  {v}")
print(f"  body uncaptured, total: {sum(r[3] or 0 for r in rows)} "
      f"across {len(bad_body)} document(s)")
print(f"  auxiliary unaccounted, total: {total_aux}")
if not control_fired:
    print("\n  VERDICT: VOID. The control did not fire, so a body count of zero is not")
    print("  evidence of anything. Fix the instrument before reading the numbers above.")
    shutil.rmtree(TMP, ignore_errors=True)
    sys.exit(1)
if bad_body:
    print("\n  VERDICT: FAIL — the body arm found uncaptured text on a real document.")
    print("  Section 4 says that is either a real historical loss or a bug in the check.")
    shutil.rmtree(TMP, ignore_errors=True)
    sys.exit(1)
print("\n  VERDICT: PASS — every reachable frozen intermediate has a complete BODY")
print("  capture, and the control proves the arm can say otherwise.")
shutil.rmtree(TMP, ignore_errors=True)
sys.exit(0)
