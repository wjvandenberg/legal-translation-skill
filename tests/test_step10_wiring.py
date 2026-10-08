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
  W5  SUB-STEP 3, RULE 5b's WAY OUT: a blocked finding with a matching `accepted_consequences.json`
      entry beside the notes DELIVERS, and repack prints its ACCEPTED CONSEQUENCE block, all five
      lines, for the delivery notes -- accepted, never silent.
  W6  a STALE entry refuses: one on a clean delivery, and one naming the right idx with the wrong
      class; nothing is written.
  W7  a second, UNDECLARED finding still blocks when the first is declared; nothing is written.
  W8  a malformed entry refuses: attempts 6 (rule 5b's bound is five), and an empty line.
  W9  Step 10's document and SKILL.md rule 5b name the file and say repack prints the block.
  W10 a report the check wrote but that cannot be read refuses with the gate's marker, never a traceback.
  REVIEW FINDING 2 (branch 11's follow-up, 2026-10-08) -- rule 5b's two other identities, through repack:
  W11 a SIDE-PART finding, named by PART AND ID: an undeclared comment kept in its own words is one blocking
      side-comment/undeclared-kept finding of word/comments.xml, id 1; an entry naming it by part and id
      DELIVERS and prints its block, an id given as a number delivers too, and an entry naming id 2 is STALE.
  W12 an ANCHOR finding, named by PART "document": the comment's reference lost from the body is
      anchor-lost/commentReference with no part and no id, beside side-ref/comment:orphaned, id 1, with no part;
      two entries naming them as "document" -- the second with its id -- DELIVER with two blocks, and an anchor
      entry naming footnoteReference is STALE.
  W13 a declaration beside a check that examined NOTHING (exit 3, VOID) is refused for the VOID, neither
      STALE nor ACCEPTED, and nothing is written.

RED FIRST: run this file from a clean copy of 59981dd (its tests/ folder), where W1 fails -- and W5's
block, W6, W7, W8 and W9, the pin having no gate at all. W11-W13 are red there too, and each against its
own planted mutant of repack -- the identity ignoring the id, the anchor's label changed, VOID matched
against the entries -- in a clean copy (temp/s1008_w11_mutants.py).

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


def repack_case(name, delivered_en, scripts=SCRIPTS, accepted=None):
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
    if accepted is not None:
        (d / "accepted_consequences.json").write_bytes(
            json.dumps({"accepted": accepted}, ensure_ascii=False, indent=1).encode("utf-8"))
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
        shutil.rmtree(TMP, ignore_errors=True)      # REVIEW FIX 8: the failing path cleans up too
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



def entry(idx, cls="changed", shape="punctuation", **over):
    e = {"idx": idx, "class": cls, "shape": shape, "attempts": 5,
         "check": "repack_docx.py (validate_apply.py --delivered --strict)",
         "consequence": "a full stop is missing at the end of a paragraph",
         "where": "the second paragraph of the body",
         "reader must": "read the paragraph against the source before relying on it"}
    e.update(over)
    return e


BLOCK_LINES = ("ACCEPTED CONSEQUENCE (SKILL.md rule 5b)", "  check:        repack_docx.py",
               "  attempts:     5", "  consequence:  a full stop is missing",
               "  where:        the second paragraph", "  reader must:  read the paragraph")
DECL_MARKER = "THE RULE 5b DECLARATION WAS REFUSED"

print("\nW5  a blocked finding with a matching entry DELIVERS, and its block is printed")
acc = repack_case("accepted", [EN[0], EN[1][:-1]], accepted=[entry(1)])
ok("repack exits 0 with a file at the delivery path", acc["rc"] == 0 and acc["out"] is not None,
   f"rc={acc['rc']} {acc['blob'][-500:]}")
ok("...and prints the ACCEPTED CONSEQUENCE block, all five lines, verbatim keys",
   all(x in acc["blob"] for x in BLOCK_LINES), acc["blob"][-700:])
ok("...and says it is ACCEPTED, NOT SATISFIED, with the count",
   "ACCEPTED, NOT SATISFIED" in acc["blob"] and "ACCEPTED under rule 5b: 1" in acc["blob"])
ok("...and the check copy's folder is empty", acc["left"] == [], str(acc["left"]))

print("\nW6  a STALE entry refuses, and nothing is written")
st1 = repack_case("stale-clean", EN, accepted=[entry(1)])
ok("an entry on a CLEAN delivery refuses — exit 1, the declaration marker, STALE, nothing written",
   st1["rc"] == 1 and DECL_MARKER in st1["blob"] and "STALE" in st1["blob"] and st1["out"] is None,
   f"rc={st1['rc']} {st1['blob'][-400:]}")
st2 = repack_case("stale-class", [EN[0], EN[1][:-1]], accepted=[entry(1, cls="missing")])
ok("an entry with the right idx and the WRONG class refuses the same way",
   st2["rc"] == 1 and DECL_MARKER in st2["blob"] and "STALE" in st2["blob"] and st2["out"] is None,
   f"rc={st2['rc']} {st2['blob'][-400:]}")
ok("...naming the entry by its identity, never by text", "idx=1 missing/punctuation" in st2["blob"]
   and EN[1][:-1] not in st2["blob"])

print("\nW7  a second, UNDECLARED finding still blocks")
two = repack_case("undeclared", [EN[0][:-1], EN[1][:-1]], accepted=[entry(1)])
ok("repack exits 1 with the gate's marker, nothing written",
   two["rc"] == 1 and MARKER in two["blob"] and two["out"] is None, f"rc={two['rc']} {two['blob'][-400:]}")
ok("...counting the one no entry names, and the one accepted",
   "1 blocking finding(s) no rule 5b entry names (1 accepted)" in two["blob"], two["blob"][-600:])

print("\nW8  a malformed entry refuses")
for name, bad_e in (("attempts 6", entry(1, attempts=6)), ("an empty line", entry(1, **{"reader must": " "}))):
    mal = repack_case("malformed-" + name.replace(" ", "-"), [EN[0], EN[1][:-1]], accepted=[bad_e])
    ok(f"{name}: exit 1, the declaration marker, 'malformed', nothing written",
       mal["rc"] == 1 and DECL_MARKER in mal["blob"] and "malformed" in mal["blob"] and mal["out"] is None,
       f"rc={mal['rc']} {mal['blob'][-400:]}")

print("\nW9  Step 10's document and SKILL.md rule 5b name the file and the printed block, both trees")
for v in ("uk", "us"):
    s10 = joined(ROOT / v / "skill-docs" / "10-repack-and-validate.md")
    sk = joined(ROOT / v / "SKILL.md")
    ok(f"[{v}] Step 10: accepted_consequences.json beside the notes, a stale entry refused, the block printed",
       all(x in s10 for x in ("accepted_consequences.json", "beside the notes", "stale",
                              "prints its ACCEPTED CONSEQUENCE block")))
    ok(f"[{v}] SKILL.md rule 5b names accepted_consequences.json",
       re.search(r"\*\*5b\..{0,6000}accepted_consequences\.json", sk) is not None)
    # REVIEW FIX 4 (2026-09-30 (3)): rule 5b (b) asks that repair was ATTEMPTED, bounded at five, and repack
    # accepts attempts 1 to 5 -- so Step 10 must not say five attempts are required.
    ok(f"[{v}] Step 10 states rule 5b's attempts as SKILL.md and repack do  attempted, at most five",
       "five attempts have found no compliant repair" not in s10
       and "your attempts at repair, at most five, have found no compliant one" in s10)

print("\nW10 a report the check wrote but that cannot be read REFUSES with the gate's marker, never a traceback")
# REVIEW FIX 3 (2026-09-30 (3)): a stub validate_apply.py that writes a truncated report and exits 1, called
# through repack's own _delivered_gate -- loaded from the tree, not run as repack, so nothing else fires first.
import importlib.util  # noqa: E402
stub = TMP / "stub-scripts"
stub.mkdir()
(stub / "validate_apply.py").write_bytes(
    b"import sys\nout = sys.argv[sys.argv.index('--report-json') + 1]\n"
    b"open(out, 'w', encoding='utf-8').write('{')\nsys.exit(1)\n")
spec = importlib.util.spec_from_file_location("s10_repack_under_test", SCRIPTS / "repack_docx.py")
rpk = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rpk)
w10 = TMP / "w10"
w10.mkdir()
docx(w10 / "orig.docx", "".join(p(r(t)) for t in SRC))
(w10 / "paragraphs.json").write_bytes(b"[]")
try:
    rpk._delivered_gate(str(w10 / "orig.docx"), io.BytesIO(b"not a docx"), str(w10 / "paragraphs.json"),
                        str(stub))
    raised = None
except Exception as exc:                            # noqa: BLE001 -- the TYPE is what is asserted
    raised = exc
ok("an unreadable report raises the gate's own refusal, not a parse error",
   isinstance(raised, RuntimeError) and MARKER in str(raised), repr(raised)[:300])
ok("...saying the report could not be read", raised is not None and "report unreadable" in str(raised),
   repr(raised)[:300])

# ---------------------------------------------------------------------------------------------------
# REVIEW FINDING 2 -- rule 5b's side-part and anchor identities, and VOID, through the REAL repack.
# The original carries one comment on its first paragraph. Its text has letters and no German marker -- a
# reference and a name, the kind of text an operator keeps in its own words -- so the remnant block, which
# runs first and reads comments too, passes it and the delivered check is the one that judges it.
# ---------------------------------------------------------------------------------------------------
sys.path.insert(0, str(ROOT / "tools"))
from keep_declarations import write_keep_declarations  # noqa: E402

COMMENT = "Ref. XQ-2020 Halvorsen Trust"                     # invented
C_CT = ('<Override PartName="/word/comments.xml" ContentType="application/vnd.openxmlformats-officedocument.'
        'wordprocessingml.comments+xml"/>\n')
C_RELS = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
          '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
          '<Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/'
          'comments" Target="comments.xml"/></Relationships>')
C_XML = (f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<w:comments {W}>'
         f'<w:comment w:id="1" w:author="Reviewer" w:date="2020-01-01T00:00:00Z">{p(r(COMMENT))}</w:comment>'
         '</w:comments>')
COMMENT_REF_RUN = '<w:r><w:commentReference w:id="1"/></w:r>'     # never `REF`: that name is the pin


def anchored(text, ref=True):
    return (f'<w:p><w:commentRangeStart w:id="1"/>{r(text)}<w:commentRangeEnd w:id="1"/>'
            + (COMMENT_REF_RUN if ref else "") + '</w:p>')


def side_case(name, *, ref=True, keep_comment=False, accepted=None, notes=None):
    """The original with its comment, the body delivered in English -- the comment's reference kept or lost
    -- and the comments part delivered as the original's, through the REAL repack, as repack_case."""
    d = TMP / name
    (d / "final" / "word").mkdir(parents=True, exist_ok=True)
    orig = d / "orig.docx"
    docx(orig, anchored(SRC[0]) + p(r(SRC[1])), {"word/comments.xml": C_XML, "word/_rels/document.xml.rels": C_RELS},
         C_CT)
    xml = d / "final" / "word" / "document.xml"
    xml.write_bytes(wrap(anchored(EN[0], ref) + p(r(EN[1]))).encode("utf-8"))
    if notes is None:
        notes = [{"idx": i, "text": s, "en": e, "style": "Normal",
                  "runs": [{"start": 0, "end": len(s), "text": s, "bold": False, "italic": False}]}
                 for i, (s, e) in enumerate(zip(SRC, EN))]
    nj = d / "paragraphs.json"
    nj.write_bytes(json.dumps(notes, ensure_ascii=False, indent=1).encode("utf-8"))
    if keep_comment:
        write_keep_declarations(orig, d, SCRIPTS, kinds={"comments"})
    if accepted is not None:
        (d / "accepted_consequences.json").write_bytes(
            json.dumps({"accepted": accepted}, ensure_ascii=False, indent=1).encode("utf-8"))
    tmpd = d / "tmp"
    tmpd.mkdir()
    env = dict(ENV, TMP=str(tmpd), TEMP=str(tmpd), TMPDIR=str(tmpd))
    out = d / "out.docx"
    res = subprocess.run([sys.executable, str(SCRIPTS / "repack_docx.py"), str(orig), str(xml), str(out),
                          "--paragraphs", str(nj)], capture_output=True, text=True, encoding="utf-8",
                         errors="replace", cwd=str(ROOT), env=env, timeout=600)
    return {"rc": res.returncode, "blob": (res.stdout or "") + (res.stderr or ""),
            "out": out.read_bytes() if out.exists() else None, "left": sorted(x.name for x in tmpd.iterdir())}


def side_entry(**ident):
    e = dict(ident, attempts=2, check="repack_docx.py (validate_apply.py --delivered --strict)",
             consequence="a reviewer's note is delivered in its own words", where="the first paragraph's note",
             **{"reader must": "read the note as the source's, not as a translation"})
    return e


def refused_as(case, marker):
    return case["rc"] == 1 and marker in case["blob"] and case["out"] is None


print("\nW11 a SIDE-PART finding, named by part and id, through repack")
w11 = side_case("side-none")
ok("the original's comment delivered undeclared refuses -- exactly one finding, side-comment/undeclared-kept",
   refused_as(w11, MARKER) and "1 blocking finding(s)" in w11["blob"]
   and "side-comment/undeclared-kept: 1" in w11["blob"], f"rc={w11['rc']} {w11['blob'][-500:]}")
W11_ID = dict(part="word/comments.xml", id="1", **{"class": "side-comment"}, shape="undeclared-kept")
acc11 = side_case("side-accepted", accepted=[side_entry(**W11_ID)])
ok("an entry naming it by PART AND ID delivers, its block printed",
   acc11["rc"] == 0 and acc11["out"] is not None and "ACCEPTED under rule 5b: 1" in acc11["blob"]
   and "ACCEPTED CONSEQUENCE (SKILL.md rule 5b)" in acc11["blob"], f"rc={acc11['rc']} {acc11['blob'][-500:]}")
ok("...and the comment's text is never printed", COMMENT not in acc11["blob"] and COMMENT not in w11["blob"])
num11 = side_case("side-number", accepted=[side_entry(**dict(W11_ID, id=1))])
ok("an id given as a NUMBER names the same finding -- repack compares it as text",
   num11["rc"] == 0 and num11["out"] is not None, f"rc={num11['rc']} {num11['blob'][-400:]}")
st11 = side_case("side-stale", accepted=[side_entry(**dict(W11_ID, id="2"))])
ok("an entry naming id 2 is STALE and refused, nothing written",
   refused_as(st11, DECL_MARKER) and "STALE" in st11["blob"], f"rc={st11['rc']} {st11['blob'][-400:]}")
ok("...naming the entry by part and id", "word/comments.xml#2 side-comment/undeclared-kept" in st11["blob"],
   st11["blob"][-400:])

print("\nW12 an ANCHOR finding, named by part \"document\", through repack")
w12 = side_case("anchor-none", ref=False, keep_comment=True)
ok("the comment's reference lost, the comment declared kept: refused on exactly two findings -- "
   "anchor-lost/commentReference and side-ref/comment:orphaned",
   refused_as(w12, MARKER) and "2 blocking finding(s)" in w12["blob"]
   and "anchor-lost/commentReference: 1" in w12["blob"] and "side-ref/comment:orphaned: 1" in w12["blob"],
   f"rc={w12['rc']} {w12['blob'][-600:]}")
ANCHOR = dict(part="document", **{"class": "anchor-lost"}, shape="commentReference")
ORPHAN = dict(part="document", id="1", **{"class": "side-ref"}, shape="comment:orphaned")
acc12 = side_case("anchor-accepted", ref=False, keep_comment=True,
                  accepted=[side_entry(**ANCHOR), side_entry(**ORPHAN)])
ok("two entries naming them as \"document\" -- the orphan with its id -- deliver with two blocks",
   acc12["rc"] == 0 and acc12["out"] is not None and "ACCEPTED under rule 5b: 2" in acc12["blob"]
   and acc12["blob"].count("ACCEPTED CONSEQUENCE (SKILL.md rule 5b)") == 2, f"rc={acc12['rc']} {acc12['blob'][-600:]}")
st12 = side_case("anchor-stale", ref=False, keep_comment=True,
                 accepted=[side_entry(**dict(ANCHOR, shape="footnoteReference")), side_entry(**ORPHAN)])
ok("an anchor entry naming footnoteReference is STALE and refused, nothing written",
   refused_as(st12, DECL_MARKER) and "document anchor-lost/footnoteReference" in st12["blob"],
   f"rc={st12['rc']} {st12['blob'][-400:]}")

print("\nW13 a declaration beside a check that examined NOTHING (VOID) is refused for the VOID")
w13 = side_case("void", notes=[], keep_comment=True, accepted=[side_entry(**W11_ID)])
ok("refused with the gate's marker and the VOID reason, nothing written",
   refused_as(w13, MARKER) and "examined NOTHING (exit 3, VOID)" in w13["blob"], f"rc={w13['rc']} {w13['blob'][-500:]}")
ok("...neither STALE nor ACCEPTED", "STALE" not in w13["blob"] and "ACCEPTED under rule 5b" not in w13["blob"])
ok("...and every check copy's folder empty after W11-W13",
   all(c["left"] == [] for c in (w11, acc11, num11, st11, w12, acc12, st12, w13)))

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
