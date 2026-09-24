"""test_delivered_check.py - branch 11 slice 1: `validate_apply.py --delivered`, on synthetic input.

ONE FAILING INPUT PER CLAIM, AND A CLEAN ONE PROVED QUIET. Every document here is invented and
built in a temporary directory; nothing is read from the corpus. What each arm asserts:

  1  a clean document reports every declared paragraph EXACT and exits 0
  2  PERMUTED paragraphs are still exact -- matching is by text, never by position (L1)
  3  a deleted word is CHANGED / word                          -- C1's "that that" -> "that"
  4  a lost full stop is CHANGED / punctuation                 -- B3
  5  a lost space between two words is CHANGED / space         -- C17's shape
  6  a lost trailing space is EDGE-SPACE / trail-lost
  7  a declared insertion delivered as plain text is READINGS  -- same text, other tracked changes
  8  a declared paragraph absent from the delivery is MISSING
  9  a journalled edit is applied to the declared side: EXACT with the journal, CHANGED without
 10  a comment anchor the original has and the delivery lacks is ANCHOR-LOST; equal is quiet
 11  --strict turns a finding into exit 1; without it the run is advisory and exits 0
 12  notes declaring nothing are VOID, exit 3 -- never clean
 13  the report prints no document text, only indices, classes and lengths
 14  the block is byte-identical in both trees
 15  WOUTER'S RULING, 2026-09-24: a trailing-whitespace loss at a paragraph's end -- the SOURCE
     paragraph ends in whitespace, the declaration mirrors it, the delivery drops it -- is
     COUNTED and reported, never a blocking finding, because it renders nothing. And the four
     shapes just outside it still block: a source with no trailing whitespace, a leading loss
     beside the trailing one, readings that differ by more than the trailing whitespace, and a
     lost space BETWEEN words.

    uv run --with lxml python tests/test_delivered_check.py
    uv run --with lxml python tests/test_delivered_check.py --variant us
    uv run --with lxml python tests/test_delivered_check.py --script <path>   # e.g. the pre-branch copy, for RED
"""
import argparse
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parent.parent
ap = argparse.ArgumentParser()
ap.add_argument("--variant", choices=("uk", "us"), default="uk")
ap.add_argument("--script", default=None)
args = ap.parse_args()
SCRIPT = Path(args.script) if args.script else ROOT / args.variant / "scripts" / "validate_apply.py"
TMP = Path(tempfile.mkdtemp(prefix="b11-delivered-test-"))
ENV = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1", PYTHONDONTWRITEBYTECODE="1")
W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
FAIL, CHECKED = [], 0


def ok(label, cond, detail=""):
    global CHECKED
    CHECKED += 1
    print(f"  {'OK  ' if cond else 'XX  '} {label}" + (f"   ({detail})" if detail and not cond else ""))
    if not cond:
        FAIL.append(label)


def run_(r):
    return f"<w:r><w:t xml:space=\"preserve\">{r}</w:t></w:r>"


def para(*parts):
    """A paragraph from parts: a str is a run; ('ins', s) / ('del', s) is a tracked change;
    ('cref',) a comment reference run."""
    out = []
    for p in parts:
        if isinstance(p, str):
            out.append(run_(p))
        elif p[0] == "ins":
            out.append(f"<w:ins w:id=\"1\" w:author=\"x\">{run_(p[1])}</w:ins>")
        elif p[0] == "del":
            out.append(f"<w:del w:id=\"2\" w:author=\"x\"><w:r><w:delText xml:space=\"preserve\">"
                       f"{p[1]}</w:delText></w:r></w:del>")
        elif p[0] == "cref":
            out.append("<w:r><w:commentReference w:id=\"0\"/></w:r>")
    return "<w:p>" + "".join(out) + "</w:p>"


def doc(paras):
    return (f"<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>"
            f"<w:document xmlns:w=\"{W}\"><w:body>{''.join(paras)}</w:body></w:document>")


def case(name, notes, delivered, original=None, journal=None, strict=False):
    d = TMP / name
    d.mkdir(parents=True, exist_ok=True)
    (d / "paragraphs.json").write_bytes(json.dumps(notes).encode("utf-8"))
    (d / "document.xml").write_bytes(doc(delivered).encode("utf-8"))
    cmd = ["uv", "run", "--with", "lxml", "python", str(SCRIPT), str(d / "paragraphs.json"),
           "--delivered", str(d / "document.xml"), "--report-json", str(d / "r.json")]
    if original is not None:
        with zipfile.ZipFile(d / "orig.docx", "w") as z:
            z.writestr("word/document.xml", doc(original))
        cmd += ["--original", str(d / "orig.docx")]
    if journal is not None:
        (d / "j.json").write_bytes(json.dumps(journal).encode("utf-8"))
        cmd += ["--journal", str(d / "j.json")]
    if strict:
        cmd.append("--strict")
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace",
                       env=ENV, cwd=str(ROOT))
    rep = json.loads((d / "r.json").read_text(encoding="utf-8")) if (d / "r.json").is_file() else None
    return r, rep


def findings(rep, cls=None, shape=None):
    if rep is None:
        return []
    return [f for f in rep["findings"] if (cls is None or f["class"] == cls)
            and (shape is None or f["shape"] == shape)]


def en(i, s):
    return {"idx": i, "text": f"source {i}", "en": s}


A, B, C = "The Parties agree as follows.", "Each notice shall be in writing.", "That that is so."
print("=" * 88)
print(f"BRANCH 11 SLICE 1 — validate_apply --delivered on synthetic input  [{SCRIPT.parent.parent.name}]")
print("=" * 88)

print("\n1  clean")
r, rep = case("clean", [en(0, A), en(1, B)], [para(A), para(B)])
ok("the report was written", rep is not None, (r.stderr or r.stdout)[-200:])
ok("both declared paragraphs EXACT, no finding, exit 0",
   rep is not None and rep["counts"].get("exact") == 2 and not rep["findings"] and r.returncode == 0,
   f"rc={r.returncode} {rep and rep['counts']}")

print("\n2  permuted — matching is by text, never by position")
r, rep = case("permuted", [en(0, A), en(1, B), en(2, C)], [para(C), para(A), para(B)])
ok("three paragraphs in another order are all EXACT", rep is not None and rep["counts"].get("exact") == 3,
   str(rep and rep["counts"]))

print("\n3  a deleted word")
r, rep = case("word", [en(0, A), en(1, C)], [para(A), para("That is so.")])
ok("CHANGED / word at idx 1", [f["idx"] for f in findings(rep, "changed", "word")] == [1], str(rep and rep["findings"]))

print("\n4  a lost full stop")
r, rep = case("punct", [en(0, A), en(1, B)], [para(A), para(B[:-1])])
ok("CHANGED / punctuation at idx 1", [f["idx"] for f in findings(rep, "changed", "punctuation")] == [1],
   str(rep and rep["findings"]))

print("\n5  a lost space between two words")
r, rep = case("space", [en(0, A), en(1, B)], [para(A), para(B.replace("shall be", "shallbe"))])
ok("CHANGED / space at idx 1", [f["idx"] for f in findings(rep, "changed", "space")] == [1],
   str(rep and rep["findings"]))

print("\n6  a lost trailing space")
r, rep = case("trail", [en(0, A + " "), en(1, B)], [para(A), para(B)])
ok("EDGE-SPACE / trail-lost at idx 0", [f["idx"] for f in findings(rep, "edge-space", "trail-lost")] == [0],
   str(rep and rep["findings"]))

print("\n7  a declared insertion delivered as plain text")
tc = {"idx": 0, "text": "source 0", "en": "Sign here now.",
      "en_segments": [{"type": "regular", "en": "Sign here"}, {"type": "ins", "en": " now"},
                      {"type": "regular", "en": "."}]}
r, rep = case("readings", [tc, en(1, B)], [para("Sign here", " now", "."), para(B)])
ok("READINGS at idx 0 — the text is all there, the tracked change is not",
   [f["idx"] for f in findings(rep, "readings")] == [0], str(rep and rep["findings"]))
r, rep = case("readings-ok", [tc, en(1, B)], [para("Sign here", ("ins", " now"), "."), para(B)])
ok("and the same paragraph WITH its insertion is EXACT", rep is not None and not rep["findings"],
   str(rep and rep["findings"]))

print("\n8  a declared paragraph absent from the delivery")
r, rep = case("missing", [en(0, A), en(1, B)], [para(A)])
ok("MISSING at idx 1", [f["idx"] for f in findings(rep, "missing")] == [1], str(rep and rep["findings"]))

print("\n9  the journal is applied to the declared side")
fixed = "The Parties agree as follows:"
j = {"schema": "post-process-journal/3",
     "stages": [{"stage": "passes", "paragraphs": [{"para": 0, "before": A, "after": fixed}]}]}
r, rep = case("journal", [en(0, A), en(1, B)], [para(fixed), para(B)], journal=j)
ok("with the journal the edited paragraph is EXACT", rep is not None and not rep["findings"],
   str(rep and rep["findings"]))
r, rep = case("nojournal", [en(0, A), en(1, B)], [para(fixed), para(B)])
ok("without it the same paragraph is CHANGED / punctuation — so the journal arm can fail",
   [f["idx"] for f in findings(rep, "changed", "punctuation")] == [0], str(rep and rep["findings"]))

print("\n10  anchors against the original")
orig = [para(A, ("cref",)), para(B, ("cref",))]
r, rep = case("anchor", [en(0, A), en(1, B)], [para(A, ("cref",)), para(B)], original=orig)
ok("a lost comment anchor is ANCHOR-LOST / commentReference",
   len(findings(rep, "anchor-lost", "commentReference")) == 1, str(rep and rep["findings"]))
r, rep = case("anchor-ok", [en(0, A), en(1, B)], [para(A, ("cref",)), para(B, ("cref",))], original=orig)
ok("equal anchors are quiet", rep is not None and not rep["findings"], str(rep and rep["findings"]))

print("\n11  --strict")
r, rep = case("strict", [en(0, A), en(1, B)], [para(A)], strict=True)
ok("a finding under --strict exits 1", r.returncode == 1, f"rc={r.returncode}")
r, rep = case("advisory", [en(0, A), en(1, B)], [para(A)])
ok("the same finding without --strict exits 0", r.returncode == 0, f"rc={r.returncode}")

print("\n12  nothing declared")
r, rep = case("void", [{"idx": 0, "text": "source 0", "en": ""}], [para(A)])
ok("notes declaring nothing exit 3, VOID", r.returncode == 3, f"rc={r.returncode}")

print("\n13  no document text in the report")
canary = "Zanzibarquux clause"
r, rep = case("canary", [en(0, canary + " one."), en(1, B)], [para(canary + " one"), para(B)])
ok("the run found the planted difference", len(findings(rep)) == 1, str(rep and rep["findings"]))
ok("and printed none of the paragraph's text", canary not in (r.stdout + r.stderr))

print("\n14  both trees")
blocks = []
for v in ("uk", "us"):
    t = (ROOT / v / "scripts" / "validate_apply.py").read_text(encoding="utf-8")
    s = t.find("# DELIVERED-DOCUMENT CHECK")
    blocks.append(t[s:t.find("def main():", s)] if s >= 0 else "")
ok("the --delivered block exists in both trees and is byte-identical",
   bool(blocks[0]) and blocks[0] == blocks[1], f"uk={len(blocks[0])} us={len(blocks[1])}")

print("\n15  Wouter's ruling: a trailing-whitespace loss is COUNTED, never blocking")


def blocking(rep):
    return [f for f in (rep or {}).get("findings", []) if f.get("blocking", True)]


ruled = {"idx": 0, "text": "source 0 ", "en": A + " "}
r, rep = case("ruled", [ruled, en(1, B)], [para(A), para(B)], strict=True)
ok("the loss is still REPORTED — edge-space / trail-lost at idx 0",
   [f["idx"] for f in findings(rep, "edge-space", "trail-lost")] == [0], str(rep and rep["findings"]))
ok("...marked not blocking, and counted as such in the report",
   rep is not None and blocking(rep) == [] and rep.get("counted") == 1 and rep.get("blocking") == 0,
   str(rep and {k: rep.get(k) for k in ("counted", "blocking")}))
ok("...so --strict exits 0", r.returncode == 0, f"rc={r.returncode}")
ok("...and the line says COUNTED, never FINDING",
   "COUNTED" in r.stdout and "FINDING" not in r.stdout, r.stdout[-300:])

r, rep = case("ruled-nosrc", [en(0, A + " "), en(1, B)], [para(A), para(B)], strict=True)
ok("a source with NO trailing whitespace still BLOCKS — the ruling's population, not a wider one",
   len(blocking(rep)) == 1 and r.returncode == 1, f"rc={r.returncode} {rep and rep['findings']}")

r, rep = case("ruled-lead", [{"idx": 0, "text": " source 0 ", "en": " " + A + " "}, en(1, B)],
              [para(A), para(B)], strict=True)
ok("a LEADING loss beside the trailing one still BLOCKS",
   len(blocking(rep)) == 1 and r.returncode == 1, f"rc={r.returncode} {rep and rep['findings']}")

tc_ws = {"idx": 0, "text": "source 0 ", "en": "Sign here now ",
         "en_segments": [{"type": "regular", "en": "Sign here"}, {"type": "ins", "en": " now "}]}
r, rep = case("ruled-readings", [tc_ws, en(1, B)], [para("Sign here", " now"), para(B)], strict=True)
ok("readings that differ by MORE than the trailing whitespace still BLOCK",
   len(blocking(rep)) == 1 and r.returncode == 1, f"rc={r.returncode} {rep and rep['findings']}")

r, rep = case("ruled-inner", [{"idx": 0, "text": "source 0 ", "en": B}, en(1, A)],
              [para(B.replace("shall be", "shallbe")), para(A)], strict=True)
ok("a lost space BETWEEN words still BLOCKS",
   len(blocking(rep)) == 1 and r.returncode == 1, f"rc={r.returncode} {rep and rep['findings']}")

shutil.rmtree(TMP, ignore_errors=True)
print("\n" + "=" * 88)
print(f"  {CHECKED} check(s), {len(FAIL)} failure(s)")
print("=" * 88)
sys.exit(1 if FAIL else 0)
