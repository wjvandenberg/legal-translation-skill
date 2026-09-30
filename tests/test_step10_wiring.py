"""test_step10_wiring.py - branch 11, Step 10's wiring slice, on synthetic input and the step documents.

ONE FAILING INPUT PER CLAIM, AND A CLEAN ONE PROVED QUIET. Nothing is read from the corpus. What each
arm asserts:

  J2  Step 4's Rule 1 gives the TRUE reason for a U+200B-only seam between two tracked segments: the
      markup view does show both, touching, as the source's own redline does, and accepting or
      rejecting reads only one of them. The false premise -- that no rendered reader sits between two
      consecutive tracked segments -- is gone, lines joined, and the prescription is kept word for
      word. Both trees.
  W1  SUB-STEP 2, THE WIRING: a delivery the delivered-document check finds wrong -- a full stop
      lost after apply, which the token check cannot see -- REFUSES repack, exit 1, the gate's
      marker and the finding's class printed, and NOTHING is written at the delivery path.
  W2  the check copy is a create-and-write and a delete: the temporary folder repack uses is
      EMPTY after a refused run and after a delivered one.
  W3  a clean delivery still delivers, byte-identical to the pin's repack (59981dd, before the
      wiring) on the same input.
  W4  Step 10's document and SKILL.md say so, both trees.

RED FIRST: run this file from a clean copy of 59981dd (its tests/ folder), where W1 fails.

    uv run --with lxml python tests/test_step10_wiring.py
    uv run --with lxml python tests/test_step10_wiring.py --variant us
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

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
from make_fixtures import R, W, WP, docx, p, r  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--variant", choices=("uk", "us"), default="uk")
args = ap.parse_args()
SCRIPTS = ROOT / args.variant / "scripts"
TMP = Path(tempfile.mkdtemp(prefix="s10-wiring-test-"))
ENV = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1", PYTHONDONTWRITEBYTECODE="1")
REF = "59981dd"                                   # the pin: the last commit before the wiring
MARKER = "THE DELIVERED-DOCUMENT CHECK REFUSED THIS DELIVERY"
FAIL, CHECKED = [], 0


def ok(label, cond, detail=""):
    global CHECKED
    CHECKED += 1
    print(f"  {'OK  ' if cond else 'XX  '} {label}" + (f"   ({detail})" if detail and not cond else ""))
    if not cond:
        FAIL.append(label)


def joined(path):
    """The document with every whitespace run collapsed to one space: a phrase a line break wraps
    matches nothing line by line, and the zero reads as a clean result."""
    return re.sub(r"\s+", " ", path.read_text(encoding="utf-8"))


print("=" * 88)
print(f"STEP 10's WIRING SLICE — synthetic input and the step documents  [{args.variant}]")
print("=" * 88)

print("\nJ2  Step 4's Rule 1: the true reason for a U+200B-only seam, the prescription kept, both trees")
RECIPE = ("The recipe in one line: **regular sides carry visible-space + ZWSP; ins↔ins or ins↔del seams "
          "carry ZWSP only.**")
for v in ("uk", "us"):
    s4 = joined(ROOT / v / "skill-docs" / "04-translate.md")
    ok(f"[{v}] the false premise is gone — 'no rendered reader between two consecutive' tracked segments",
       "no rendered reader between two consecutive" not in s4)
    ok(f"[{v}] the true reason: the markup view shows both, touching, as the source's own redline does",
       all(x in s4 for x in ("the markup view shows both",
                             "only one of the two is ever read as text",
                             "how the source's own redline shows such a seam",
                             "repack scrubs the ZWSP, so the delivered redline matches the source's")))
    ok(f"[{v}] two insertions in a row are DESCRIBED — both kept on accepting — and nothing new is prescribed",
       "Two insertions in a row are both kept on accepting" in s4)
    ok(f"[{v}] the prescription is kept word for word — the recipe line", RECIPE in s4)

# ---------------------------------------------------------------------------------------------------
# SUB-STEP 2 — THE WIRING. Synthetic documents only: a German source, its English, the notes.
# ---------------------------------------------------------------------------------------------------
SRC = ["Die Parteien vereinbaren Folgendes.", "Jede Mitteilung bedarf der Schriftform."]
EN = ["The Parties agree as follows.", "Each notice shall be in writing."]


def wrap(body):
    return (f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
            f'<w:document {W} {R} {WP}><w:body>{body}'
            f'<w:sectPr><w:pgSz w:w="11906" w:h="16838"/></w:sectPr></w:body></w:document>')


def repack_case(name, delivered_en, scripts=SCRIPTS):
    """The original, a hand-built translated document.xml and the notes, through the REAL repack, run by
    this interpreter so nothing else writes into the temporary folder it is given."""
    d = TMP / name
    (d / "final" / "word").mkdir(parents=True, exist_ok=True)
    orig = d / "orig.docx"
    docx(orig, "".join(p(r(t)) for t in SRC))
    xml = d / "final" / "word" / "document.xml"
    xml.write_bytes(wrap("".join(p(r(t)) for t in delivered_en)).encode("utf-8"))
    notes = [{"idx": i, "text": s, "en": e, "style": "Normal",
              "runs": [{"start": 0, "end": len(s), "text": s, "bold": False, "italic": False}]}
             for i, (s, e) in enumerate(zip(SRC, EN))]
    nj = d / "paragraphs.json"
    nj.write_bytes(json.dumps(notes, ensure_ascii=False, indent=1).encode("utf-8"))
    tmpd = d / "tmp"
    tmpd.mkdir()
    env = dict(ENV, TMP=str(tmpd), TEMP=str(tmpd), TMPDIR=str(tmpd))
    out = d / "out.docx"
    res = subprocess.run([sys.executable, str(scripts / "repack_docx.py"), str(orig), str(xml), str(out),
                          "--paragraphs", str(nj)], capture_output=True, text=True, encoding="utf-8",
                         errors="replace", cwd=str(ROOT), env=env, timeout=600)
    return {"rc": res.returncode, "blob": (res.stdout or "") + (res.stderr or ""),
            "out": out.read_bytes() if out.exists() else None, "left": sorted(x.name for x in tmpd.iterdir())}


def pin_scripts():
    """The pin's own scripts for this variant, from git, into the test's folder -- a create-and-write."""
    dest = TMP / "pin"
    # FROM THE REPOSITORY'S TOP LEVEL: git resolves a pathspec against the directory it runs in, so from a
    # clean copy under temp/ the path matched nothing and the archive came back empty.
    top = subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=str(ROOT), capture_output=True,
                         text=True).stdout.strip()
    blob = subprocess.run(["git", "archive", "--format=zip", REF, f"{args.variant}/scripts"], cwd=top,
                          capture_output=True).stdout
    if not blob:
        print(f"  VOID — git archive of {REF} returned nothing; the pin comparison cannot run")
        sys.exit(3)
    with zipfile.ZipFile(io.BytesIO(blob)) as z:
        for info in z.infolist():
            if not info.is_dir():
                target = dest / info.filename
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(z.read(info))
    return dest / args.variant / "scripts"


print("\nW1  a delivery the check finds wrong REFUSES repack, and nothing is written")
bad = repack_case("refused", [EN[0], EN[1][:-1]])
ok("repack exits 1", bad["rc"] == 1, f"rc={bad['rc']} {bad['blob'][-400:]}")
ok("...with the gate's marker and the finding's class printed",
   MARKER in bad["blob"] and "changed/punctuation" in bad["blob"], bad["blob"][-600:])
ok("...and NOTHING at the delivery path", bad["out"] is None)
ok("...and none of the paragraph's text printed", EN[1][:-1] not in bad["blob"])

print("\nW2  the check copy is created, read and deleted — never left, never renamed")
good = repack_case("delivered", EN)
ok("the temporary folder is EMPTY after the refused run", bad["left"] == [], str(bad["left"]))
ok("...and after the delivered one", good["left"] == [], str(good["left"]))

print("\nW3  a clean delivery still delivers, byte-identical to the pin's repack")
ok("a clean delivery exits 0 with a file at the delivery path", good["rc"] == 0 and good["out"] is not None,
   f"rc={good['rc']} {good['blob'][-400:]}")
pin = repack_case("delivered-pin", EN, scripts=pin_scripts())
ok(f"...byte-identical to {REF}'s repack on the same input", pin["out"] is not None and good["out"] == pin["out"],
   f"pin rc={pin['rc']}")

print("\nW4  Step 10's document and SKILL.md say so, both trees")
for v in ("uk", "us"):
    s10 = joined(ROOT / v / "skill-docs" / "10-repack-and-validate.md")
    sk = joined(ROOT / v / "SKILL.md")
    ok(f"[{v}] Step 10: the delivered-document check runs on a check copy BEFORE the file is written, and refuses",
       all(x in s10 for x in ("validate_apply.py --delivered", "on a check copy", "BEFORE the file is written",
                              "the delivered-document check")))
    ok(f"[{v}] SKILL.md's script table: repack runs validate_apply.py --delivered before it writes",
       re.search(r"\| `repack_docx\.py` \|[^|]*validate_apply\.py --delivered", sk) is not None)

shutil.rmtree(TMP, ignore_errors=True)
print()
print("=" * 88)
if FAIL:
    print(f"FAIL — {len(FAIL)} of {CHECKED} checks:")
    for f in FAIL:
        print(f"  ·  {f}")
    print("=" * 88)
    sys.exit(1)
print(f"PASS — {CHECKED} checks.")
print("=" * 88)
