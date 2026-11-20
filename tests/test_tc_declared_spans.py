"""test_tc_declared_spans.py - sub-step 17.3: declared spans placed on a tracked-change paragraph (register A10), and
A20's re-base (PLAN-2-step-b.md section 3.17, 17.3's own plan).

ON INVENTED DOCUMENTS ONLY, every paragraph built by tests/make_fixtures.py - its committed tc-declared-spans.docx
and, in a temporary directory, documents written with its own helpers. Each is put through the tree's own
extract_paragraphs.py, an operator's English added, the read receipt filed, and the tree's apply run over it. Every
delivered character is then read IN FORCE through extraction's resolver over the document's own styles, with the
wrapper it sits in. What each arm asserts:

  1  the committed fixture's notes agree with extraction (`en`, `en_runs` and `en_segments` set aside)
  2  TP, the fixture page: a bold term inside the kept text, inside an insertion after a deletion, and across the
     seam between kept and inserted text - bold exactly on the declared characters; no character moved (the
     accepted text is `en`, each insertion's text its segment's); each inserted character still inside its own
     w:ins, author and date kept; the deletion's run untouched
  3  TP, an italic span beside a bold one - each on its own characters, neither on the other's
  4  TP, the bold-off pass yields to a placed paragraph: a span whose bold is 1 (read bold, as the regular path
     reads it; the rev38 bypass reads only `true`) stays bold
  5  TP, 16.3's writer: in a paragraph bold by its style, the declared bold term carries no flag of its own and the
     declared plain text an off-flag - each in force as declared
  6  negative input, a misaligned `en` (its accepted segments carry zero-width spaces it does not): nothing placed,
     the source's formatting delivered, and one line naming the entry's idx
  7  A20, the tracked-change path: an `en` beginning with a space, a tab and a line break, the bold term placed
  8  A20, the regular path: the same three - the space is stripped and the offsets re-based; tab and line break kept
  9  TP, the cursor: two adjacent insertions, merged into one segment, get a zero-width space at their seam; a
     declared edge between the two equal letters just after it lands where declared - a cursor that counted the
     zero-width space as a character of `en` would move it by one
 10  the bold-off pass yields to the runs placement set and to nothing else: where no span says bold it still runs,
     and a deletion's directly bold run loses its bold as at the pin - placement never touches a rejected run
 11  a kept run holding text, a tab, then text: split around the tab, which stays between the two pieces
 12  negative input, a span past the end of `en`: F16's refusal unchanged, nothing delivered

RED FIRST: against the scripts at the pin e5db826 (--scripts) arms 2 to 5, 6's line, 7, 8's space case, 9, 10's
italic and 11's bold fail - 17 checks of 39, on both trees.
Prints booleans and the invented documents' own words - never anything from a real document.

    uv run --with lxml python tests/test_tc_declared_spans.py
    uv run --with lxml python tests/test_tc_declared_spans.py --variant us
    uv run --with lxml python tests/test_tc_declared_spans.py --scripts <folder>   # e.g. the pin's, for RED
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
ap.add_argument("--scripts", default=None)
args = ap.parse_args()
SCRIPTS = Path(args.scripts) if args.scripts else ROOT / args.variant / "scripts"
sys.path.insert(0, str(ROOT / "tests"))
from read_receipt import file_receipt  # noqa: E402
import make_fixtures as MF  # noqa: E402
sys.path.insert(0, str(ROOT / args.variant / "scripts"))
from lxml import etree  # noqa: E402
import extract_paragraphs as XP  # noqa: E402   (the reader: always today's, so a red is the writer's)

TMP = Path(tempfile.mkdtemp(prefix="s173-tc-spans-"))
ENV = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1", PYTHONDONTWRITEBYTECODE="1")
W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
ZWSP = chr(0x200B)
TAB, NL = chr(9), chr(10)
FAIL, CHECKED = [], 0
FIXTURE = ROOT / "tests" / "fixtures" / "tc-declared-spans.docx"
STRIP = ("en", "en_runs", "en_segments")


def ok(label, cond, detail=""):
    global CHECKED
    CHECKED += 1
    print(f"  {'OK  ' if cond else 'XX  '} {label}" + (f"   ({detail})" if detail and not cond else ""))
    if not cond:
        FAIL.append(label)


def q(tag):
    return f"{{{W}}}{tag}"


def extract(src, notes_path):
    subprocess.run(["uv", "run", "--with", "lxml", "python", str(ROOT / args.variant / "scripts" /
                                                                "extract_paragraphs.py"), str(src), str(notes_path)],
                   capture_output=True, text=True, encoding="utf-8", errors="replace", env=ENV, timeout=600)
    return json.loads(notes_path.read_text(encoding="utf-8"))


def apply(src, notes, d):
    """(the delivered root or None, apply's printed output)."""
    notes_path = d / "paragraphs.json"
    notes_path.write_bytes(json.dumps(notes, ensure_ascii=False, indent=1).encode("utf-8"))
    file_receipt(notes_path, ROOT / args.variant)
    out = d / "out.xml"
    pr = subprocess.run(["uv", "run", "--with", "lxml", "python", str(SCRIPTS / "apply_translations_textmatch.py"),
                         str(src), str(notes_path), str(out)], capture_output=True, text=True, encoding="utf-8",
                        errors="replace", env=ENV, timeout=900)
    said = (pr.stdout or "") + (pr.stderr or "")
    return (etree.parse(str(out)).getroot() if out.is_file() else None), said


def cascade_of(src):
    with zipfile.ZipFile(src) as z:
        return XP.read_style_cascade(z)


def wrapper(el, par):
    """The w:ins or w:del an element sits in, or None."""
    node = el.getparent()
    while node is not None and node is not par:
        if node.tag in (q("ins"), q("del")):
            return node
        node = node.getparent()
    return None


def chars(cas, par):
    """Every accepted character (w:t outside any w:del), zero-width spaces skipped: (char, bold, italic, the w:ins
    it sits in or None, its run)."""
    ppr = par.find(q("pPr"))
    ps = ppr.find(q("pStyle")) if ppr is not None else None
    out = []
    for t in par.iter(q("t")):
        wr = wrapper(t, par)
        if wr is not None and wr.tag == q("del"):
            continue
        run = t.getparent()
        rpr = run.find(q("rPr"))
        rs = rpr.find(q("rStyle")) if rpr is not None else None
        f = XP.resolve_run(cas, ps.get(q("val")) if ps is not None else None,
                           rs.get(q("val")) if rs is not None else None, rpr)
        for ch in t.text or "":
            if ch != ZWSP:
                out.append((ch, f["bold"], f["italic"], wr, run))
    return out


def mask(en, spans, key):
    m = [False] * len(en)
    for s in spans:
        for k in range(s["start"], s["end"]):
            m[k] = bool(s.get(key, False))
    return m


def visible(seq):
    """The non-whitespace members of a (char, value) sequence - what a page shows, compared across paths that
    keep or strip a leading separator."""
    return [(c, v) for c, v in seq if not c.isspace()]


print("=" * 96)
print(f"SUB-STEP 17.3 - declared spans on a tracked-change paragraph (A10), and A20  [{args.variant}]"
      + (f"  scripts: {args.scripts}" if args.scripts else ""))
print("=" * 96)

# ---------------------------------------------------------------------------------------------- 1 and 2
print("\n1  the committed fixture's notes agree with extraction")
committed = json.loads(FIXTURE.with_suffix(".notes.json").read_text(encoding="utf-8"))
d = TMP / "fixture"
d.mkdir()
src = d / "src.docx"
shutil.copyfile(FIXTURE, src)
fresh = extract(src, d / "extracted.json")
ok("every note as extraction writes it, the English set aside",
   [{k: v for k, v in n.items() if k not in STRIP} for n in committed]
   == [{k: v for k, v in n.items() if k not in STRIP} for n in fresh])
root, said = apply(src, committed, d)
cas = cascade_of(src)
print("\n2  the fixture page: kept text, an insertion after a deletion, across a seam")
ok("apply delivered the fixture", root is not None, said[-300:])
P = list(root.iter(q("p"))) if root is not None else []
for n in committed:
    i = n["idx"]
    got = chars(cas, P[i]) if i < len(P) else []
    word = n["en"][n["en_runs"][1]["start"]:n["en_runs"][1]["end"]] if len(n["en_runs"]) > 1 else n["en"]
    ok(f"idx {i}: no character moved - the accepted text is `en`", "".join(c for c, *_ in got) == n["en"],
       "".join(c for c, *_ in got))
    ok(f"idx {i}: bold in force exactly on '{word}'", [b for _c, b, *_ in got] == mask(n["en"], n["en_runs"], "bold"),
       "".join(c.upper() if b else c for c, b, *_ in got))
    ins_en = "".join(s["en"] for s in n["en_segments"] if s["type"] == "ins")
    ins_got = "".join(c for c, _b, _i, wr, _r in got if wr is not None)
    ok(f"idx {i}: every inserted character still inside a w:ins, and only those", ins_got == ins_en, ins_got)
    authors = {(wr.get(q("author")), wr.get(q("date"))) for _c, _b, _i, wr, _r in got if wr is not None}
    ok(f"idx {i}: each w:ins keeps its author and date", authors == {("A", "2020-01-01T00:00:00Z")}, str(authors))
dels = [x for x in P[1].iter(q("del"))] if len(P) > 1 else []
ok("idx 1: the deletion is untouched - its text the segment's, its run carrying no emphasis flag",
   len(dels) == 1 and "".join(t.text or "" for t in dels[0].iter(q("delText"))) == "the Sum"
   and all(r.find(q("rPr")) is None or r.find(q("rPr")).find(q("b")) is None for r in dels[0].iter(q("r")))
   and dels[0].get(q("author")) == "A")
ok("no line names an unplaced declaration on an aligned page", "NOTE: en_runs not placed" not in said)

# ---------------------------------------------------------------------------------------------- 3 to 8
INS = '<w:ins w:id="%d" w:author="A" w:date="2020-01-01T00:00:00Z">%s</w:ins>'
BOLDCLAUSE = '<w:pPr><w:pStyle w:val="BoldClause"/></w:pPr>'
ARMS = [
    # (source XML, en_segments or None, en_runs)
    (MF.p(MF.r("Partij A "), INS % (1, MF.r("en Partij B"))), ["Party A ", "and Party B"],
     [{"start": 0, "end": 7, "bold": True, "italic": False}, {"start": 7, "end": 12, "bold": False, "italic": False},
      {"start": 12, "end": 19, "bold": False, "italic": True}]),
    (MF.p(MF.r("Een "), INS % (2, MF.r("Woord"))), ["One ", "Word"],
     [{"start": 0, "end": 4, "bold": False, "italic": False}, {"start": 4, "end": 8, "bold": 1, "italic": False}]),
    (MF.p(MF.r("Kop "), INS % (3, MF.r("tekst")), ppr=BOLDCLAUSE), ["Head ", "text"],
     [{"start": 0, "end": 4, "bold": True, "italic": False}, {"start": 4, "end": 9, "bold": False, "italic": False}]),
    (MF.p(MF.r("Alfa "), INS % (4, MF.r("Beta"))), ["Alpha ", ZWSP + "Beta"],
     [{"start": 0, "end": 6, "bold": False, "italic": False}, {"start": 6, "end": 10, "bold": True, "italic": False}]),
] + [
    (MF.p(MF.r("Voor "), INS % (5 + k, MF.r("Termijn" + "abc"[k]))), [lead + "Lead ", "Term"],
     [{"start": 0, "end": 6, "bold": False, "italic": False}, {"start": 6, "end": 10, "bold": True, "italic": False}])
    for k, lead in enumerate((" ", TAB, NL))
] + [
    (MF.p(MF.r("Voor Termijn " + str(k))), None,
     [{"start": 0, "end": 6, "bold": False, "italic": False}, {"start": 6, "end": 10, "bold": True, "italic": False}])
    for k, lead in enumerate((" ", TAB, NL))
] + [
    # two adjacent insertions merge into one segment, and apply puts a zero-width space at their seam where both
    # sides are letters: "Bo" | U+200B "ss". The declared edge falls between the two equal letters after it.
    (MF.p(MF.r("Zie "), INS % (11, MF.r("ab")), INS % (12, MF.r("cd")), MF.r(" nu")), ["See ", "Boss", " now"],
     [{"start": 0, "end": 4, "bold": False, "italic": False}, {"start": 4, "end": 7, "bold": True, "italic": False},
      {"start": 7, "end": 12, "bold": False, "italic": False}]),
    # no span says bold, so the bold-off pass runs: it yields to the runs placement set, and a deletion's directly
    # bold run is still decided by it, as at the pin
    (MF.p(MF.r("Een woord", "<w:rPr><w:b/></w:rPr>"),
          '<w:del w:id="13" w:author="A" w:date="2020-01-01T00:00:00Z"><w:r><w:rPr><w:b/></w:rPr>'
          '<w:delText xml:space="preserve">oud</w:delText></w:r></w:del>', INS % (15, MF.r(" erbij"))),
     ["One word", " old", " added"],
     [{"start": 0, "end": 3, "bold": False, "italic": True}, {"start": 3, "end": 14, "bold": False, "italic": False}]),
    # one kept run holding text, a tab, then text: split around the tab, which stays between them
    ('<w:p><w:r><w:t xml:space="preserve">Kop</w:t><w:tab/><w:t xml:space="preserve">Tekst </w:t></w:r>'
     + INS % (14, MF.r("erbij")) + "</w:p>", ["Head Text ", "added"],
     [{"start": 0, "end": 4, "bold": True, "italic": False}, {"start": 4, "end": 15, "bold": False, "italic": False}]),
]
LEADS = (" ", TAB, NL)
d = TMP / "arms"
d.mkdir()
src = d / "src.docx"
MF.docx(src, "".join(x for x, _s, _r in ARMS), extra_parts={"word/_rels/document.xml.rels": MF.STYLE_LINK_RELS})
notes = extract(src, d / "extracted.json")
for k, (_x, segs, spans) in enumerate(ARMS):
    e = notes[k]
    if segs is not None:
        e["en_segments"] = [{"type": s["type"], "en": en} for s, en in zip(e["tc_segments"], segs)]
        e["en"] = "".join(en for s, en in zip(e["tc_segments"], segs) if s["type"] != "del").replace(ZWSP, "")
    else:
        e["en"] = LEADS[k - 7] + "Lead Term"
    e["en_runs"] = spans
root, said = apply(src, notes, d)
cas = cascade_of(src)
ok("apply delivered the arms document", root is not None, said[-400:])
P = list(root.iter(q("p"))) if root is not None else []


def col(i, key):
    got = chars(cas, P[i]) if i < len(P) else []
    return [(c, b if key == "bold" else it) for c, b, it, _w, _r in got]


def want(i, key):
    e = notes[i]
    return list(zip(e["en"], mask(e["en"], e["en_runs"], key)))


print("\n3  an italic span beside a bold one")
ok("bold exactly on 'Party A'", col(0, "bold") == want(0, "bold"), str(col(0, "bold")))
ok("italic exactly on 'Party B'", col(0, "italic") == want(0, "italic"), str(col(0, "italic")))
print("\n4  the bold-off pass yields to a placed paragraph")
ok("a span whose bold is 1: 'Word' bold, 'One' not", col(1, "bold") == want(1, "bold"), str(col(1, "bold")))
print("\n5  16.3's writer, in a paragraph bold by its style")
ok("bold exactly on 'Head', in force", col(2, "bold") == want(2, "bold"), str(col(2, "bold")))
runs2 = [(r_, "".join(t.text or "" for t in r_.findall(q("t")))) for r_ in P[2].iter(q("r"))] if len(P) > 2 else []
flags = [(txt, [(c.tag.split("}")[1], c.get(q("val"))) for c in (r_.find(q("rPr")) if r_.find(q("rPr")) is not None
                                                                     else []) if c.tag.split("}")[1] in ("b", "bCs")])
         for r_, txt in runs2 if txt.strip()]
ok("the bold term carries no flag of its own (its style gives it); the plain text an off-pair",
   [f for t, f in flags if "Head" in t] == [[]] and all(f == [("b", "0"), ("bCs", "0")] for t, f in flags
                                                        if "Head" not in t), str(flags))
print("\n6  a misaligned `en`: nothing placed, one line naming its idx")
ok("nothing bold - the source's formatting delivered", not any(b for _c, b in col(3, "bold")), str(col(3, "bold")))
ok("one line names idx 3", said.count("NOTE: en_runs not placed on tracked-change paragraph idx 3") == 1,
   [ln for ln in said.splitlines() if "NOTE" in ln])
ok("... and only idx 3", said.count("NOTE: en_runs not placed") == 1)
print("\n7  A20 on the tracked-change path: the offsets index the raw `en`")
for k, name in enumerate(("a space", "a tab", "a line break")):
    i = 4 + k
    ok(f"`en` beginning with {name}: bold exactly on 'Term'", visible(col(i, "bold")) == visible(want(i, "bold")),
       str(visible(col(i, "bold"))))
print("\n8  A20 on the regular path: the offsets re-based by what the strip removed")
for k, name in enumerate(("a space", "a tab", "a line break")):
    i = 7 + k
    ok(f"`en` beginning with {name}: bold exactly on 'Term'", visible(col(i, "bold")) == visible(want(i, "bold")),
       str(visible(col(i, "bold"))))
print("\n9  a span edge just after a wrapper seam's zero-width space")
seam_text = "".join(t.text or "" for t in P[10].iter(q("t"))) if len(P) > 10 else ""
ok("the premise holds: apply put a zero-width space at the seam", ZWSP + "ss" in seam_text)
ok("bold exactly on 'Bos', the second 's' not", col(10, "bold") == want(10, "bold"), str(col(10, "bold")))
print("\n10  the bold-off pass yields to the runs placement set, and to nothing else")
ok("italic exactly on 'One', and nothing accepted bold", col(11, "italic") == want(11, "italic")
   and not any(v for _c, v in col(11, "bold")), str(col(11, "italic")) + str(col(11, "bold")))
del_runs = [r_ for d_ in P[11].iter(q("del")) for r_ in d_.iter(q("r"))] if len(P) > 11 else []
ok("the deletion's directly bold run: its bold removed by the pass, as at the pin", len(del_runs) == 1 and (
   del_runs[0].find(q("rPr")) is None or del_runs[0].find(q("rPr")).find(q("b")) is None
   or del_runs[0].find(q("rPr")).find(q("b")).get(q("val")) in ("0", "false", "off")),
   str([etree.tostring(x)[:200] for x in del_runs]))
print("\n11  a run split around a tab")
ok("a run holding text, a tab, then text: bold exactly on 'Head'", col(12, "bold") == want(12, "bold"),
   str(col(12, "bold")))
order = "".join((t.text or "") if t.tag == q("t") else TAB for t in P[12].iter(q("t"), q("tab"))
                if wrapper(t, P[12]) is None or wrapper(t, P[12]).tag != q("del")) if len(P) > 12 else ""
ok("... the tab kept, still between the two pieces of text", order == "Head " + TAB + "Text added", repr(order))

# ---------------------------------------------------------------------------------------------- 12
print("\n12  a span past the end of `en`: F16's refusal unchanged")
d = TMP / "past"
d.mkdir()
src = d / "src.docx"
MF.docx(src, MF.p(MF.r("Alfa "), INS % (9, MF.r("Beta"))), extra_parts={"word/_rels/document.xml.rels":
                                                                         MF.STYLE_LINK_RELS})
notes = extract(src, d / "extracted.json")
notes[0]["en_segments"] = [{"type": s["type"], "en": en} for s, en in zip(notes[0]["tc_segments"], ["Alpha ", "Beta"])]
notes[0]["en"] = "Alpha Beta"
notes[0]["en_runs"] = [{"start": 0, "end": 6, "bold": False, "italic": False},
                       {"start": 6, "end": 14, "bold": True, "italic": False}]
root, said = apply(src, notes, d)
ok("refused, nothing delivered", root is None)
ok("... by a gate naming the offset", "offset" in said and "out of range" in said, said[-300:])

shutil.rmtree(TMP, ignore_errors=True)
print("\n" + "=" * 96)
print(f"  {CHECKED} check(s), {len(FAIL)} failure(s)")
for f in FAIL:
    print(f"    XX  {f}")
print("=" * 96)
sys.exit(1 if FAIL else 0)
