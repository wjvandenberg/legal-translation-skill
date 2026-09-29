"""test_strip_noop_guard.py - branch 11 slice 4a, register B10: none of
`strip_noop_tracked_changes.py`'s three removing passes removes a wrapper WHOLE while it holds
anything besides runs, run properties and text, the phantom pass's own nested wrappers excepted
(PLAN-2-step-b.md section 3.2, block "4a - B10"). Every document here is invented and built in a
temporary directory; nothing is read from the corpus.

RED FIRST: `--ref bc9c5d8` takes the script from the branch's start. The KEPT arms and the script's
own account must fail there -- today each pass removes the wrapper and what it holds -- while the
REMOVED and UNCHANGED arms pass there and here, which is what proves the guard is no wider than the
rule. A ref whose script equals the working tree's is a self-comparison and VOID, never a pass.

  KEPT WHOLE, each holding something besides runs, run properties and text:
   1  an empty insertion holding a comment reference
   2  an empty insertion holding a comment range end, a comment reference and Word's _GoBack
      bookmark -- D08's shape
   3  an empty deletion holding a footnote reference
   4  a whitespace-only deletion holding a comment range start
   5  a no-op pair whose DELETION holds a comment range end: the pair is left as it is
   6  a phantom whose nested deletion holds a comment reference
   7  a phantom holding a bookmark beside its nested deletion
   8  an empty insertion holding only a tab, and one holding only a line break: the rule is
      anything besides text, not only the anchors the register row names
  REMOVED, as before the guard:
   9  an empty insertion whose run carries run properties with children
  10  a whitespace-only deletion and a punctuation-only deletion
  11  a no-op pair holding only text: the deletion removed, the insertion unwrapped
  12  a phantom holding only runs, run properties, text and its nested deletion
  13  a no-op pair whose INSERTION holds the anchor: it collapses, the anchor staying in place
  14  a no-op pair with a comment range between the two, as siblings: it collapses
  15  an empty insertion wrapping only an empty deletion: the empty-wrapper pass keeps it, the
      phantom pass may take its nested wrapper and does, and it is not counted as kept
  UNCHANGED:
  16  B3: a punctuation-only insertion is preserved
  THE SCRIPT'S OWN ACCOUNT, over one document holding every arm:
  17  the printed count of wrappers kept whole equals the wrappers kept
  18  every anchor in the input is in the output, by kind and id
  19  a second run changes nothing
  20  the output parses, keeps the document's own root element, and carries no ns0: prefix

    uv run --with lxml python tests/test_strip_noop_guard.py
    uv run --with lxml python tests/test_strip_noop_guard.py --variant us
    uv run --with lxml python tests/test_strip_noop_guard.py --ref bc9c5d8    # RED
"""
import argparse
import io
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

from lxml import etree  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
ap = argparse.ArgumentParser()
ap.add_argument("--variant", choices=("uk", "us"), default="uk")
ap.add_argument("--ref", default=None, help="take the script from this commit instead (RED)")
args = ap.parse_args()
NAME = "strip_noop_tracked_changes.py"
TREE_SCRIPT = ROOT / args.variant / "scripts" / NAME
TMP = Path(tempfile.mkdtemp(prefix="b11s4a-guard-test-"))
ENV = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1", PYTHONDONTWRITEBYTECODE="1")
W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
FAIL, CHECKED = [], 0

if args.ref:
    SCRIPT = TMP / NAME
    SCRIPT.write_bytes(subprocess.run(["git", "show", f"{args.ref}:{args.variant}/scripts/{NAME}"],
                                      capture_output=True, check=True, cwd=str(ROOT)).stdout)
    if SCRIPT.read_bytes() == TREE_SCRIPT.read_bytes():
        print(f"  VOID — {args.ref}'s {NAME} equals the working tree's: a self-comparison")
        shutil.rmtree(TMP, ignore_errors=True)
        sys.exit(2)
else:
    SCRIPT = TREE_SCRIPT
print(f"[{args.variant}] B10 guard — {NAME} from {args.ref or 'the working tree'}")


def ok(label, cond, detail=""):
    global CHECKED
    CHECKED += 1
    print(f"  {'OK  ' if cond else 'XX  '} {label}" + (f"   ({detail})" if detail and not cond else ""))
    if not cond:
        FAIL.append(label)


# ---------------------------------------------------------------------------------------------
# BUILDERS. Invented text only.
# ---------------------------------------------------------------------------------------------
def r(s):
    return f'<w:r><w:t xml:space="preserve">{s}</w:t></w:r>'


def dr(s):
    return f'<w:r><w:delText xml:space="preserve">{s}</w:delText></w:r>'


def ins(inner, i):
    return f'<w:ins w:id="{i}" w:author="A" w:date="2020-01-01T00:00:00Z">{inner}</w:ins>'


def dele(inner, i):
    return f'<w:del w:id="{i}" w:author="B" w:date="2020-01-02T00:00:00Z">{inner}</w:del>'


HEAD = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        f'<w:document xmlns:w="{W}" xmlns:x="urn:invented"><w:body>')
TAIL = '<w:sectPr/></w:body></w:document>'
CREF = '<w:r><w:rPr><w:rStyle w:val="CommentReference"/></w:rPr><w:commentReference w:id="{}"/></w:r>'

# (arm, label, input paragraph body, expected paragraph body -- None means kept as it came)
KEPT = [
    ("1", "an empty insertion holding a comment reference",
     r("Before") + ins(CREF.format(1), 31), None),
    ("2", "an empty insertion holding a range end, a comment reference and _GoBack (D08's shape)",
     '<w:commentRangeStart w:id="2"/>' + r("Text")
     + ins('<w:commentRangeEnd w:id="2"/>' + CREF.format(2)
           + '<w:bookmarkStart w:id="0" w:name="_GoBack"/><w:bookmarkEnd w:id="0"/>', 32), None),
    ("3", "an empty deletion holding a footnote reference",
     r("Clause") + dele('<w:r><w:rPr><w:rStyle w:val="FootnoteReference"/></w:rPr>'
                        '<w:footnoteReference w:id="1"/></w:r>', 33), None),
    ("4", "a whitespace-only deletion holding a comment range start",
     r("A") + dele('<w:commentRangeStart w:id="3"/>' + dr(" "), 34) + r("B")
     + '<w:commentRangeEnd w:id="3"/>' + CREF.format(3), None),
    ("5", "a no-op pair whose deletion holds a comment range end — the pair left as it is",
     '<w:commentRangeStart w:id="4"/>' + dele(dr("solar energy") + '<w:commentRangeEnd w:id="4"/>', 35)
     + ins(r("solar energy"), 36) + CREF.format(4), None),
    ("6", "a phantom whose nested deletion holds a comment reference",
     ins(dele(CREF.format(5) + dr("gone"), 38), 37) + r("tail"), None),
    ("7", "a phantom holding a bookmark beside its nested deletion",
     ins('<w:bookmarkStart w:id="1" w:name="mark"/>' + dele(dr("gone"), 40)
         + '<w:bookmarkEnd w:id="1"/>', 39) + r("tail"), None),
    ("8", "an empty insertion holding only a tab",
     r("Name") + ins('<w:r><w:tab/></w:r>', 41) + r("Value"), None),
    ("8b", "an empty insertion holding only a line break",
     r("Line one") + ins('<w:r><w:br/></w:r>', 42) + r("Line two"), None),
]
REMOVED = [
    ("9", "an empty insertion whose run carries run properties with children",
     r("Before") + ins('<w:r><w:rPr><w:b/><w:i/><w:color w:val="FF0000"/></w:rPr><w:t></w:t></w:r>', 51),
     r("Before")),
    ("10", "a whitespace-only deletion and a punctuation-only deletion",
     r("A") + dele(dr(" "), 52) + r("B") + dele(dr("."), 53), r("A") + r("B")),
    ("11", "a no-op pair holding only text — the deletion removed, the insertion unwrapped",
     dele(dr("solar energy"), 54) + ins(r("solar energy"), 55), r("solar energy")),
    ("12", "a phantom holding only runs, run properties, text and its nested deletion",
     ins(dele('<w:r><w:rPr><w:b/></w:rPr><w:delText>gone</w:delText></w:r>', 57), 56) + r("tail"),
     r("tail")),
    ("13", "a no-op pair whose INSERTION holds the anchor — it collapses, the anchor in place",
     '<w:commentRangeStart w:id="7"/>' + dele(dr("solar energy"), 58)
     + ins(r("solar energy") + '<w:commentRangeEnd w:id="7"/>', 59) + CREF.format(7),
     '<w:commentRangeStart w:id="7"/>' + r("solar energy") + '<w:commentRangeEnd w:id="7"/>'
     + CREF.format(7)),
    ("14", "a no-op pair with a comment range between the two, as siblings — it collapses",
     dele(dr("solar energy"), 60) + '<w:commentRangeStart w:id="8"/>' + ins(r("solar energy"), 61)
     + '<w:commentRangeEnd w:id="8"/>' + CREF.format(8),
     '<w:commentRangeStart w:id="8"/>' + r("solar energy") + '<w:commentRangeEnd w:id="8"/>'
     + CREF.format(8)),
    ("15", "an empty insertion wrapping only an empty deletion — the phantom pass takes it",
     r("A") + ins(dele(dr(""), 63), 62), r("A")),
]
UNCHANGED = [
    ("16", "B3: a punctuation-only insertion is preserved",
     r("A") + ins(r("-"), 64) + r("B"), None),
]
ALL = KEPT + REMOVED + UNCHANGED
ANCHORS = ("commentReference", "commentRangeStart", "commentRangeEnd", "bookmarkStart", "bookmarkEnd",
           "footnoteReference")


def doc(bodies):
    return HEAD + "".join(f"<w:p>{b}</w:p>" for b in bodies) + TAIL


def c14n(el):
    return etree.tostring(el, method="c14n", exclusive=True)


def paragraphs(xml_bytes):
    return etree.fromstring(xml_bytes).findall(f".//{{{W}}}p")


def strip(path):
    p = subprocess.run([sys.executable, str(SCRIPT), str(path)], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", env=ENV, cwd=str(TMP))
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def anchors(xml_bytes):
    root = etree.fromstring(xml_bytes)
    return Counter((a, el.get(f"{{{W}}}id")) for a in ANCHORS for el in root.iter(f"{{{W}}}{a}"))


def wrappers(xml_bytes):
    root = etree.fromstring(xml_bytes)
    return sum(1 for el in root.iter(f"{{{W}}}ins", f"{{{W}}}del"))


# ---------------------------------------------------------------------------------------------
# ARMS 1-16, one document each, so a failure names its own shape.
# ---------------------------------------------------------------------------------------------
print("\n  ONE DOCUMENT PER ARM:")
for group, rows in (("KEPT WHOLE", KEPT), ("REMOVED", REMOVED), ("UNCHANGED", UNCHANGED)):
    for arm, label, body, want in rows:
        path = TMP / f"arm{arm}.xml"
        path.write_bytes(doc([body]).encode("utf-8"))
        rc, out = strip(path)
        got = paragraphs(path.read_bytes())
        exp = paragraphs(doc([want if want is not None else body]).encode("utf-8"))
        same = rc == 0 and len(got) == 1 and c14n(got[0]) == c14n(exp[0])
        ok(f"{arm:>3} {group}: {label}", same,
           f"rc={rc}; wrappers in {wrappers(doc([body]).encode('utf-8'))}, out "
           f"{wrappers(path.read_bytes()) if rc == 0 else '-'}")
        if arm == "15":
            m = re.search(r"kept (\d+) wrapper\(s\) whole", out)
            ok(" 15b the wrapper the phantom pass then took is not counted as kept (kept 0)",
               bool(m) and m.group(1) == "0", f"printed: {m.group(0) if m else 'no kept count'}")

# ---------------------------------------------------------------------------------------------
# ARMS 17-20, over one document holding every arm.
# ---------------------------------------------------------------------------------------------
print("\n  ONE DOCUMENT HOLDING EVERY ARM:")
whole = TMP / "all.xml"
src = doc([b for _, _, b, _ in ALL]).encode("utf-8")
whole.write_bytes(src)
rc, out = strip(whole)
first = whole.read_bytes()
m = re.search(r"kept (\d+) wrapper\(s\) whole", out)
kept_arms = [a for a, _, _, _ in KEPT]
got = paragraphs(first)
exp = paragraphs(src)
held = sum(1 for k, (arm, _, _, _) in enumerate(ALL) if arm in kept_arms and c14n(got[k]) == c14n(exp[k]))
ok(f" 17 the printed count of wrappers kept whole equals the wrappers kept ({len(KEPT)} arms, each one "
   f"wrapper; {held} held)", bool(m) and int(m.group(1)) == len(KEPT) == held,
   f"printed: {m.group(0) if m else 'no kept count'}; held {held} of {len(KEPT)}")
lost = anchors(src) - anchors(first)
ok(f" 18 every anchor in the input is in the output, by kind and id ({sum(anchors(src).values())} in)",
   rc == 0 and not lost and anchors(src) == anchors(first), f"lost {dict(lost)}")
rc2, _ = strip(whole)
ok(" 19 a second run changes nothing", rc2 == 0 and whole.read_bytes() == first)
text = first.decode("utf-8")
ok(" 20 the output parses, keeps the document's own root element, and carries no ns0: prefix",
   rc == 0 and "ns0:" not in text and text.split("<w:body>", 1)[0] == src.decode("utf-8").split("<w:body>", 1)[0],
   "root element or prefixes changed")

shutil.rmtree(TMP, ignore_errors=True)
print("\n" + "=" * 96)
print(f"  {CHECKED} check(s), {len(FAIL)} failure(s)")
for f in FAIL:
    print(f"    XX  {f}")
print("=" * 96)
sys.exit(1 if FAIL else 0)
