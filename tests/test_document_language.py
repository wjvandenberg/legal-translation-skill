# -*- coding: utf-8 -*-
"""STEP 13, SUB-STEP 13.2 (register R1) — THE DELIVERED DOCUMENT'S LANGUAGE IS THE VARIANT'S, AND NOTHING ELSE MOVES.

R1: every remnant scanner reads `<w:t>`, so nothing ever looked at the DOCUMENT's language. Apply strips the
source-language `w:lang` from the body's runs, which leaves styles.xml's defaults and settings.xml's theme
language deciding what Word spell-checks the delivery against — the source language, on three documents from
three, so Word flagged nearly every English word. repack_docx.py now sets, before its one write, every
`w:lang` `w:val` in word/styles.xml and the `w:themeFontLang` `w:val` in word/settings.xml to en-GB (uk) or
en-US (us), and nothing else.

WHAT IS ASSERTED, per tree and through each tree's own repack, on a synthetic NON-ENGLISH source built here
from tests/fixtures/definitions.docx:
  * every `w:val` of those two elements in those two parts reads the variant's tag — a value in single
    quotes as well;
  * `w:eastAsia` and `w:bidi` are untouched (they choose fonts for East Asian and right-to-left text: layout),
    and a `w:lang` with no `w:val` gets none added;
  * THE INVERSE: each delivered part with its new values put back, in order, to the source's IS the source part,
    byte for byte — so nothing else in either part moved;
  * every other member is the source's, byte for byte: the body's own run-level `w:lang` and the Word 2010
    copy stylesWithEffects.xml are NOT touched (the brief's "any part but the two");
  * THE COMMAND LINE, the operator's path, defaults to the tree's own variant: each tree run with no flag
    delivers its own tag, and the uk tree with --variant us delivers en-US. repack()'s own default is the
    same in both trees, so the two stay one program for tools/parity_check.py; a caller names the variant.

RED FIRST: run against repack_docx.py before 13.2, the value assertions fail (measured 2026-10-19 (2)).

    uv run --with lxml python tests/test_document_language.py

Synthetic only. No client text.
"""
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
STYLES_DEFAULTS = (
    b'<w:docDefaults><w:rPrDefault><w:rPr><w:lang w:val="hu-HU" w:eastAsia="ja-JP" w:bidi="ar-SA"/>'
    b'</w:rPr></w:rPrDefault></w:docDefaults>')
STYLE_NO_VAL = (b'<w:style w:type="character" w:styleId="EastOnly"><w:name w:val="East Only"/>'
                b"<w:rPr><w:lang w:eastAsia='zh-CN'/></w:rPr></w:style>")
STYLE_QUOTED = (b'<w:style w:type="character" w:styleId="Quoted"><w:name w:val="Quoted"/>'
                b"<w:rPr><w:lang w:val='de-DE' w:bidi='he-IL'/></w:rPr></w:style>")
SETTINGS = (f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<w:settings {W}>'
            '<w:zoom w:percent="100"/><w:themeFontLang w:val="hu-HU" w:eastAsia="ja-JP"/></w:settings>').encode()
SWE = (f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<w:styles {W}><w:docDefaults><w:rPrDefault>'
       '<w:rPr><w:lang w:val="hu-HU" w:eastAsia="ja-JP" w:bidi="ar-SA"/></w:rPr></w:rPrDefault></w:docDefaults>'
       '</w:styles>').encode()
RELS = (b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<Relationships xmlns="http://schemas.'
        b'openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.'
        b'openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/><Relationship '
        b'Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/settings" '
        b'Target="settings.xml"/><Relationship Id="rId3" Type="http://schemas.microsoft.com/office/2007/'
        b'relationships/stylesWithEffects" Target="stylesWithEffects.xml"/></Relationships>')
CT_ADD = (b'<Override PartName="/word/settings.xml" ContentType="application/vnd.openxmlformats-officedocument.'
          b'wordprocessingml.settings+xml"/><Override PartName="/word/stylesWithEffects.xml" ContentType="'
          b'application/vnd.ms-word.stylesWithEffects+xml"/></Types>')


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


TMP = Path(tempfile.mkdtemp(prefix="doc-language-"))
try:
    for tree in ("uk", "us"):
        print(f"\n{tree} — the tree's own repack_docx.py, repack(variant={tree!r})")
        print("-" * 96)
        W_ = TMP / tree
        W_.mkdir()
        src = W_ / "orig.docx"
        members = build_source(src)
        (W_ / "document.xml").write_bytes(members["word/document.xml"])
        ext = W_ / "extracted.json"
        xr = subprocess.run([sys.executable, str(ROOT / tree / "scripts" / "extract_paragraphs.py"), str(src),
                             str(ext)], capture_output=True)
        if xr.returncode != 0 or not ext.is_file():
            print(f"VOID — extraction failed on the synthetic source (exit {xr.returncode}). Nothing passed.")
            sys.exit(1)
        paras = [dict(n, en=n["text"]) for n in json.loads(ext.read_text(encoding="utf-8"))]
        (W_ / "paragraphs.json").write_text(json.dumps(paras), encoding="utf-8")
        write_keep_declarations(src, W_, ROOT / tree / "scripts")
        rpk = load(ROOT / tree / "scripts" / "repack_docx.py", f"rpk_lang_{tree}")
        out = W_ / "delivered.docx"
        try:
            rpk.repack(str(src), str(W_ / "document.xml"), str(out), paragraphs_json=str(W_ / "paragraphs.json"),
                       variant=tree)
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
        for part in ("word/styles.xml", "word/settings.xml"):
            sv, dv = vals(members[part]), vals(got[part])
            want = [(e, (tag if v is not None else None)) for e, v in sv]
            ok(f"{tree} {part}: every w:val reads {tag}, a val-less element still has none ({len(sv)} element(s))",
               dv == want, f"delivered {dv}")
            ok(f"{tree} {part}: w:eastAsia and w:bidi untouched", attrs_but_val(members[part]) ==
               attrs_but_val(got[part]))
            ok(f"{tree} {part}: THE INVERSE — the values put back, the part IS the source's, byte for byte",
               put_back(got[part], members[part]) == members[part])
        # REVIEW FIX: a part whose root is not w:-prefixed cannot be read, and repack SAYS so (found None)
        alien = (b'<x:styles xmlns:x="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
                 b'<x:docDefaults><x:rPrDefault><x:rPr><x:lang x:val="hu-HU"/></x:rPr></x:rPrDefault>'
                 b'</x:docDefaults></x:styles>')
        setter = getattr(rpk, "_set_document_language", None)   # absent before 13.2: a FAIL, never a traceback
        ok(f"{tree}: a part not w:-prefixed is returned untouched and reported unreadable (found None)",
           setter is not None and setter("word/styles.xml", alien, TAG[tree]) == (alien, None, 0))
        others = sorted(set(members) - {"word/styles.xml", "word/settings.xml"})
        moved = [n for n in others if got.get(n) != members[n]]
        ok(f"{tree}: every other member the source's, byte for byte ({len(others)}: the body's run-level w:lang "
           f"and stylesWithEffects.xml among them)", not moved and set(got) == set(members), f"moved {moved}")
    # THE COMMAND LINE: each tree with no flag gets its own variant; the uk tree asked for the US one gets it
    for tree, flag, want in (("uk", None, "en-GB"), ("us", None, "en-US"), ("uk", "us", "en-US")):
        label = f"{tree} command line, " + (f"--variant {flag}" if flag else "no --variant")
        print(f"\n{label}")
        print("-" * 96)
        W_ = TMP / tree
        out = W_ / f"cli-{flag or 'default'}.docx"
        cmd = [sys.executable, str(ROOT / tree / "scripts" / "repack_docx.py"), str(W_ / "orig.docx"),
               str(W_ / "document.xml"), str(out), "--paragraphs", str(W_ / "paragraphs.json")]
        r = subprocess.run(cmd + (["--variant", flag] if flag else []), capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
        ok(f"{label}: exit 0 and a .docx", r.returncode == 0 and out.is_file(), f"exit {r.returncode}")
        if out.is_file():
            with zipfile.ZipFile(out) as z:
                cli_vals = vals(z.read("word/styles.xml")) + vals(z.read("word/settings.xml"))
            ok(f"{label}: every value set reads {want}",
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
print(f"PASS — {CHECKED} assertions: the delivered document's language is the variant's, on the two values the "
      f"brief names, and no other byte of the package moved.")
