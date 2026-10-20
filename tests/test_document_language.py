# -*- coding: utf-8 -*-
"""STEP 13, SUB-STEPS 13.2 AND 13.5 (registers R1 and R2) — EVERY PART OF THE DELIVERY SAYS THE VARIANT'S ENGLISH,
AND NOTHING ELSE MOVES.

R1: every remnant scanner reads `<w:t>`, so nothing ever looked at the DOCUMENT's language. Apply strips the
source-language `w:lang` from the body's runs, which leaves styles.xml's defaults and settings.xml's theme
language deciding what Word spell-checks the delivery against — the source language, on three documents from
three, so Word flagged nearly every English word. 13.2 made repack_docx.py set, before its one write, every
`w:lang` `w:val` in word/styles.xml and the `w:themeFontLang` `w:val` in word/settings.xml to en-GB (uk) or
en-US (us). R2, 13.2's residue: a `w:lang` anywhere else still carried the source's language — 23 values not
English in the headers, footers, footnotes and comments of the July deliveries, more in numbering.xml, the
glossary and Word 2010's copy stylesWithEffects.xml. 13.5 carries 13.2's rule to every part the delivery holds:
the headers, footers, footnotes, endnotes, comments, numbering.xml and stylesWithEffects.xml, and the glossary's
own document, styles, settings and the rest of its parts.

WHAT IS ASSERTED, per tree and through each tree's own repack, on a synthetic NON-ENGLISH source built here
from tests/fixtures/definitions.docx, with every part type planted — a non-English value, one in single quotes,
an English one and one with no `w:val`; three parts handed to repack by the translated-part routes (a header
through --headers-footers-dir, the footnotes through --footnotes, numbering.xml through --numbering) and the
rest copied from the original, so both of repack's routes are read:
  * every `w:val` of every language element in every language part reads the variant's tag;
  * `w:eastAsia` and `w:bidi` are untouched (they choose fonts for East Asian and right-to-left text: layout),
    and a `w:lang` with no `w:val` gets none added;
  * THE INVERSE: each delivered part with its new values put back, in order, to the source's IS the source part,
    byte for byte — so nothing else in it moved (a comment's `w:author` among what did not);
  * every other member is the source's, byte for byte: the body's own run-level `w:lang` (apply's, never
    repack's) and people.xml among them;
  * a part whose root is not w:-prefixed is returned untouched and said to be unreadable (found None), for a
    13.2 part and a 13.5 part alike;
  * THE COMMAND LINE, the operator's path, defaults to the tree's own variant: each tree run with no flag
    delivers its own tag in every part, and the uk tree with --variant us delivers en-US. repack()'s own default
    is the same in both trees, so the two stay one program for tools/parity_check.py; a caller names the variant.

RED FIRST: before 13.2 the styles and settings assertions fail (measured 2026-10-19 (2)); before 13.5 every side
part's do (`--trees` names a folder holding another build's uk/ and us/ trees — temp/s1020d_red135.py points it at
main's).

    uv run --with lxml python tests/test_document_language.py [--trees DIR]

Synthetic only. No client text.
"""
import argparse
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.dont_write_bytecode = True
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
from keep_declarations import write_keep_declarations  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--trees", default=str(ROOT), help="a folder holding the uk/ and us/ trees to test (default: this one)")
TREES = Path(ap.parse_args().trees)

FIX = ROOT / "tests" / "fixtures" / "definitions.docx"
TAG = {"uk": "en-GB", "us": "en-US"}
ELEM = re.compile(rb"<w:(lang|themeFontLang)(?=[\s/>])[^>]*>")
VAL = re.compile(rb"(\sw:val=)([\"'])([^\"']*)\2")
FAIL, CHECKED = [], 0


def ok(label, cond, detail=""):
    global CHECKED
    CHECKED += 1
    print(f"  {'ok  ' if cond else 'FAIL'} {label}" + ("" if cond else f"   {detail}"))
    if not cond:
        FAIL.append(label)


W = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'
DECL = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
STYLES_DEFAULTS = (
    b'<w:docDefaults><w:rPrDefault><w:rPr><w:lang w:val="hu-HU" w:eastAsia="ja-JP" w:bidi="ar-SA"/>'
    b'</w:rPr></w:rPrDefault></w:docDefaults>')
STYLE_NO_VAL = (b'<w:style w:type="character" w:styleId="EastOnly"><w:name w:val="East Only"/>'
                b"<w:rPr><w:lang w:eastAsia='zh-CN'/></w:rPr></w:style>")
STYLE_QUOTED = (b'<w:style w:type="character" w:styleId="Quoted"><w:name w:val="Quoted"/>'
                b"<w:rPr><w:lang w:val='de-DE' w:bidi='he-IL'/></w:rPr></w:style>")
SETTINGS = (f'{DECL}<w:settings {W}>'
            '<w:zoom w:percent="100"/><w:themeFontLang w:val="hu-HU" w:eastAsia="ja-JP"/></w:settings>').encode()
DEFAULTS = ('<w:docDefaults><w:rPrDefault><w:rPr><w:lang w:val="hu-HU" w:eastAsia="ja-JP" w:bidi="ar-SA"/></w:rPr>'
            '</w:rPrDefault></w:docDefaults>')
SWE = f'{DECL}<w:styles {W}>{DEFAULTS}</w:styles>'.encode()
# 13.5: the four shapes a language element takes, as runs - a non-English value beside a font choice, one in single
# quotes beside a right-to-left one, an English value that need not be the variant's, and a font choice alone
MIX = ('<w:r><w:rPr><w:lang w:val="fr-FR" w:eastAsia="zh-CN"/></w:rPr></w:r>'
       "<w:r><w:rPr><w:lang w:val='pl-PL' w:bidi='he-IL'/></w:rPr></w:r>"
       '<w:r><w:rPr><w:lang w:val="en-AU"/></w:rPr></w:r>'
       '<w:r><w:rPr><w:lang w:eastAsia="ja-JP"/></w:rPr></w:r>')
SIDE = {
    "word/header1.xml": f'{DECL}<w:hdr {W}><w:p><w:pPr><w:rPr><w:lang w:val="it-IT"/></w:rPr></w:pPr>{MIX}</w:p></w:hdr>',
    "word/footer1.xml": f"{DECL}<w:ftr {W}><w:p>{MIX}</w:p></w:ftr>",
    "word/footnotes.xml": f'{DECL}<w:footnotes {W}><w:footnote w:id="1"><w:p>{MIX}</w:p></w:footnote></w:footnotes>',
    "word/endnotes.xml": f'{DECL}<w:endnotes {W}><w:endnote w:id="1"><w:p>{MIX}</w:p></w:endnote></w:endnotes>',
    "word/comments.xml": (f'{DECL}<w:comments {W}><w:comment w:id="0" w:author="Ada Example" w:initials="AE">'
                          f"<w:p>{MIX}</w:p></w:comment></w:comments>"),
    "word/numbering.xml": (f'{DECL}<w:numbering {W}><w:abstractNum w:abstractNumId="0">'
                           '<w:lvl w:ilvl="0"><w:rPr><w:lang w:val="nl-NL" w:eastAsia="ko-KR"/></w:rPr></w:lvl>'
                           "<w:lvl w:ilvl=\"1\"><w:rPr><w:lang w:val='sv-SE'/></w:rPr></w:lvl>"
                           '<w:lvl w:ilvl="2"><w:rPr><w:lang w:bidi="fa-IR"/></w:rPr></w:lvl>'
                           "</w:abstractNum></w:numbering>"),
    "word/glossary/document.xml": (f"{DECL}<w:glossaryDocument {W}><w:docParts><w:docPart><w:docPartBody>"
                                   f"<w:p>{MIX}</w:p></w:docPartBody></w:docPart></w:docParts></w:glossaryDocument>"),
    "word/glossary/styles.xml": f"{DECL}<w:styles {W}>{DEFAULTS}</w:styles>",
    "word/glossary/settings.xml": f'{DECL}<w:settings {W}><w:themeFontLang w:val="hu-HU" w:bidi="ar-SA"/></w:settings>',
}
SIDE = {k: v.encode() for k, v in SIDE.items()}
# parts repack must NEVER touch: people.xml holds people's names, not a language (Wouter, 2026-10-16 (2))
PEOPLE = (b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<w15:people xmlns:w15="http://schemas.'
          b'microsoft.com/office/word/2012/wordml"><w15:person w15:author="Ada Example"/></w15:people>')
# the parts whose language values repack sets: 13.2's two, and 13.5's
LANGUAGE_PARTS = ("word/styles.xml", "word/settings.xml", "word/stylesWithEffects.xml", *SIDE)
# three routes in: a part handed to repack as its translated version (the bytes are the source's - what a run that
# translated no text in them hands it), the rest copied from the original
ROUTED = {"word/header1.xml": "hf", "word/footnotes.xml": "footnotes", "word/numbering.xml": "numbering"}

REL = ('<Relationship Id="{i}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/{t}" '
       'Target="{p}"/>')
RELS = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<Relationships xmlns="http://schemas.'
        'openxmlformats.org/package/2006/relationships">'
        + "".join(REL.format(i=f"rId{n}", t=t, p=p) for n, (t, p) in enumerate(
            [("styles", "styles.xml"), ("settings", "settings.xml"), ("header", "header1.xml"),
             ("footer", "footer1.xml"), ("footnotes", "footnotes.xml"), ("endnotes", "endnotes.xml"),
             ("comments", "comments.xml"), ("numbering", "numbering.xml"),
             ("glossaryDocument", "glossary/document.xml")], 1))
        + '<Relationship Id="rId10" Type="http://schemas.microsoft.com/office/2007/relationships/stylesWithEffects" '
          'Target="stylesWithEffects.xml"/></Relationships>').encode()
CT = "application/vnd.openxmlformats-officedocument.wordprocessingml."
CT_ADD = ("".join(f'<Override PartName="/{p}" ContentType="{CT}{t}+xml"/>' for p, t in [
    ("word/settings.xml", "settings"), ("word/header1.xml", "header"), ("word/footer1.xml", "footer"),
    ("word/footnotes.xml", "footnotes"), ("word/endnotes.xml", "endnotes"), ("word/comments.xml", "comments"),
    ("word/numbering.xml", "numbering"), ("word/glossary/document.xml", "document.glossary"),
    ("word/glossary/styles.xml", "styles"), ("word/glossary/settings.xml", "settings")])
    + '<Override PartName="/word/stylesWithEffects.xml" ContentType="application/vnd.ms-word.stylesWithEffects+xml"/>'
    + '<Override PartName="/word/people.xml" ContentType="application/vnd.openxmlformats-officedocument.'
      'wordprocessingml.people+xml"/></Types>').encode()


def build_source(dest: Path) -> dict:
    """The synthetic non-English source: definitions.docx with planted language values. Returns its members."""
    with zipfile.ZipFile(FIX) as z:
        m = {n: z.read(n) for n in z.namelist()}
    st = m["word/styles.xml"]
    i = st.index(b">", st.index(b"<w:styles")) + 1
    st = st[:i] + STYLES_DEFAULTS + st[i:]
    st = st.replace(b"</w:styles>", STYLE_NO_VAL + STYLE_QUOTED + b"</w:styles>")
    m["word/styles.xml"] = st
    m["word/settings.xml"] = SETTINGS
    m["word/stylesWithEffects.xml"] = SWE
    m.update(SIDE)
    m["word/people.xml"] = PEOPLE
    m["word/_rels/document.xml.rels"] = RELS
    m["[Content_Types].xml"] = m["[Content_Types].xml"].replace(b"</Types>", CT_ADD)
    # a run-level w:lang in the BODY, which repack must leave alone (apply strips these, upstream)
    body = m["word/document.xml"]
    k = body.index(b"<w:r>")
    m["word/document.xml"] = body[:k] + b'<w:r><w:rPr><w:lang w:val="hu-HU"/></w:rPr></w:r>' + body[k:]
    with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as z:
        for n, b in m.items():
            z.writestr(n, b)
    return m


def vals(data: bytes):
    """[(element, w:val or None)] for every w:lang / w:themeFontLang start tag, in order."""
    out = []
    for e in ELEM.finditer(data):
        v = VAL.search(e.group(0))
        out.append((e.group(1).decode(), v.group(3).decode() if v else None))
    return out


def attrs_but_val(data: bytes):
    return [VAL.sub(b"", e.group(0)) for e in ELEM.finditer(data)]


def put_back(delivered: bytes, source: bytes) -> bytes:
    """THE INVERSE: the delivered part with each element's w:val restored, in order, to the source's."""
    src = [VAL.search(e.group(0)) for e in ELEM.finditer(source)]
    it = iter(src)

    def one(e):
        s = next(it)
        if s is None:
            return e.group(0)
        return VAL.sub(lambda v: v.group(1) + v.group(2) + s.group(3) + v.group(2), e.group(0), count=1)

    return ELEM.sub(one, delivered)


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# the planted shapes are really there - a part that planted nothing would pass every assertion below vacuously
for _p in SIDE:
    _v = vals(SIDE[_p])
    assert any(v and not v.startswith("en") for _e, v in _v), f"{_p}: no non-English value planted"

TMP = Path(tempfile.mkdtemp(prefix="doc-language-"))
try:
    print(f"trees under test: {'this checkout' if TREES == ROOT else 'another build, by --trees'}")
    for tree in ("uk", "us"):
        print(f"\n{tree} — the tree's own repack_docx.py, repack(variant={tree!r})")
        print("-" * 96)
        scripts = TREES / tree / "scripts"
        W_ = TMP / tree
        W_.mkdir()
        src = W_ / "orig.docx"
        members = build_source(src)
        (W_ / "document.xml").write_bytes(members["word/document.xml"])
        ext = W_ / "extracted.json"
        xr = subprocess.run([sys.executable, str(scripts / "extract_paragraphs.py"), str(src),
                             str(ext)], capture_output=True)
        if xr.returncode != 0 or not ext.is_file():
            print(f"VOID — extraction failed on the synthetic source (exit {xr.returncode}). Nothing passed.")
            sys.exit(1)
        paras = [dict(n, en=n["text"]) for n in json.loads(ext.read_text(encoding="utf-8"))]
        (W_ / "paragraphs.json").write_text(json.dumps(paras), encoding="utf-8")
        write_keep_declarations(src, W_, scripts)
        # the translated-part routes: kept OUTSIDE the folder of document.xml, where repack would warn of an unwired part
        tr = W_ / "tr"
        (tr / "word").mkdir(parents=True)
        (tr / "word" / "header1.xml").write_bytes(members["word/header1.xml"])
        (tr / "footnotes.xml").write_bytes(members["word/footnotes.xml"])
        (tr / "numbering.xml").write_bytes(members["word/numbering.xml"])
        rpk = load(scripts / "repack_docx.py", f"rpk_lang_{tree}")
        out = W_ / "delivered.docx"
        try:
            rpk.repack(str(src), str(W_ / "document.xml"), str(out), paragraphs_json=str(W_ / "paragraphs.json"),
                       headers_footers_dir=str(tr), translated_footnotes_xml=str(tr / "footnotes.xml"),
                       translated_numbering_xml=str(tr / "numbering.xml"), variant=tree)
        except SystemExit as exc:
            print(f"       repack exited {exc.code}")
        except Exception as exc:  # a crash is a named failure, never a traceback that reads as a pass
            print(f"       repack raised {type(exc).__name__}: {exc}")
        ok(f"{tree}: repack produced a .docx", out.is_file())
        if not out.is_file():
            continue
        with zipfile.ZipFile(out) as z:
            got = {n: z.read(n) for n in z.namelist()}
        tag = TAG[tree]
        for part in LANGUAGE_PARTS:
            sv, dv = vals(members[part]), vals(got.get(part, b""))
            want = [(e, (tag if v is not None else None)) for e, v in sv]
            how = ("13.2" if part in ("word/styles.xml", "word/settings.xml") else "13.5") + (
                f", handed in by the {ROUTED[part]} route" if part in ROUTED else "")
            ok(f"{tree} {part} ({how}): every w:val reads {tag}, a val-less element still has none "
               f"({len(sv)} element(s))", dv == want, f"delivered {dv}")
            ok(f"{tree} {part}: w:eastAsia and w:bidi untouched", attrs_but_val(members[part]) ==
               attrs_but_val(got.get(part, b"")))
            ok(f"{tree} {part}: THE INVERSE — the values put back, the part IS the source's, byte for byte",
               put_back(got.get(part, b""), members[part]) == members[part])
        # REVIEW FIX (13.2): a part whose root is not w:-prefixed cannot be read, and repack SAYS so (found None)
        setter = getattr(rpk, "_set_document_language", None)   # absent before 13.2: a FAIL, never a traceback
        for part, alien in (
                ("word/styles.xml", b'<x:styles xmlns:x="http://schemas.openxmlformats.org/wordprocessingml/2006/'
                                    b'main"><x:docDefaults><x:rPrDefault><x:rPr><x:lang x:val="hu-HU"/></x:rPr>'
                                    b"</x:rPrDefault></x:docDefaults></x:styles>"),
                ("word/footer2.xml", b'<x:ftr xmlns:x="http://schemas.openxmlformats.org/wordprocessingml/2006/'
                                     b'main"><x:p><x:r><x:rPr><x:lang x:val="hu-HU"/></x:rPr></x:r></x:p></x:ftr>')):
            ok(f"{tree}: {part} not w:-prefixed is returned untouched and reported unreadable (found None)",
               setter is not None and setter(part, alien, TAG[tree]) == (alien, None, 0))
        others = sorted(set(members) - set(LANGUAGE_PARTS))
        moved = [n for n in others if got.get(n) != members[n]]
        ok(f"{tree}: every other member the source's, byte for byte ({len(others)}: the body's run-level w:lang "
           f"and people.xml among them)", not moved and set(got) == set(members), f"moved {moved}")
    # THE COMMAND LINE: each tree with no flag gets its own variant; the uk tree asked for the US one gets it
    for tree, flag, want in (("uk", None, "en-GB"), ("us", None, "en-US"), ("uk", "us", "en-US")):
        label = f"{tree} command line, " + (f"--variant {flag}" if flag else "no --variant")
        print(f"\n{label}")
        print("-" * 96)
        W_ = TMP / tree
        out = W_ / f"cli-{flag or 'default'}.docx"
        cmd = [sys.executable, str(TREES / tree / "scripts" / "repack_docx.py"), str(W_ / "orig.docx"),
               str(W_ / "document.xml"), str(out), "--paragraphs", str(W_ / "paragraphs.json")]
        r = subprocess.run(cmd + (["--variant", flag] if flag else []), capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
        ok(f"{label}: exit 0 and a .docx", r.returncode == 0 and out.is_file(), f"exit {r.returncode}")
        if out.is_file():
            with zipfile.ZipFile(out) as z:
                cli_vals = [v for p in LANGUAGE_PARTS for v in vals(z.read(p))]
            ok(f"{label}: every value set reads {want}, in all {len(LANGUAGE_PARTS)} language parts",
               {v for _e, v in cli_vals if v is not None} == {want}, f"{cli_vals}")
            ok(f"{label}: the run says what it set", f"read {want}" in r.stdout, r.stdout[-400:])
finally:
    shutil.rmtree(TMP, ignore_errors=True)

print("\n" + "=" * 96)
if FAIL:
    print(f"FAIL — {len(FAIL)} of {CHECKED} assertion(s):")
    for f in FAIL:
        print(f"  · {f}")
    sys.exit(1)
print(f"PASS — {CHECKED} assertions: every part of the delivery says the variant's English, a val-less element "
      f"gains none, and no other byte of the package moved.")
