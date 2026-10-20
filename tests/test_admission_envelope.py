# -*- coding: utf-8 -*-
"""STEP 13, SUB-STEP 13.3 (register L5) — THE ACCEPTED-INPUT ENVELOPE, REFUSED AT ADMISSION, BEFORE EXTRACTION.

L5: the skill never declared what it accepts, and the one input outside the envelope observed in production — a
scanned deed with no text layer — went through extraction with nothing to extract, so every gate after it passed
on nothing. extract_paragraphs.py, the first script that reads the original on every run, now refuses five classes
before a paragraph is read, each saying what to do, with exit 2 — the shape of the skill's one earlier admission
gate, clean_conversion_artifacts.py:
  not a Word document · password-protected · macro-enabled · image-only · over 1,000 body paragraphs (Wouter)

WHAT IS ASSERTED, per tree, through each tree's own script on SYNTHETIC inputs built here from
tests/fixtures/anchors-and-tabs.docx:
  * NINE REFUSALS covering the five classes — a PDF, a legacy binary .doc, a spreadsheet package and a Word package
    saved as .zip (not a Word document); an encrypted package named .docx (password-protected); a .docm and the
    same package renamed .docx (macro-enabled: decided on the bytes, never the name); a body with a picture and no
    text (image-only); a body of 1,001 paragraphs (over the size limit). Each: exit 2, the banner, its class
    named, a "What to do" line carrying that class's own instruction, no traceback, and NO paragraphs.json written.
  * FOUR ADMISSIONS, so a gate that refuses everything is caught too: the clean fixture; a body of exactly 1,000
    paragraphs, the boundary; a picture WITH text; and a raw document.xml, the script's other route. Each: exit 0,
    a non-empty paragraphs.json, no banner.

RED FIRST: --ref REF runs both trees' scripts as they stood at REF. Against the pin before 13.3 every refusal case
fails and every admission passes (measured 2026-10-20).

    uv run --with lxml python tests/test_admission_envelope.py
    uv run --with lxml python tests/test_admission_envelope.py --ref 33bf4b9

Synthetic only. No client text.
"""
import argparse
import json
import os
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
CLEAN = ROOT / "tests" / "fixtures" / "anchors-and-tabs.docx"
W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
CFB = bytes.fromhex("d0cf11e0a1b11ae1")
FAIL, CHECKED = [], 0


def ok(label, cond, detail=""):
    global CHECKED
    CHECKED += 1
    print(f"  {'ok  ' if cond else 'FAIL'} {label}" + ("" if cond else f"   {detail}"))
    if not cond:
        FAIL.append(label)
    return cond


def members():
    with zipfile.ZipFile(CLEAN) as z:
        return {n: z.read(n) for n in z.namelist()}


def write_zip(path: Path, m: dict) -> Path:
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        for n, b in m.items():
            z.writestr(n, b)
    return path


def body(paras: str) -> bytes:
    return (f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<w:document xmlns:w="{W_NS}"><w:body>'
            f"{paras}</w:body></w:document>").encode("utf-8")


def text_paras(n: int) -> str:
    return "".join(f"<w:p><w:r><w:t>Clause {i}.</w:t></w:r></w:p>" for i in range(1, n + 1))


PICTURE = "<w:p><w:r><w:drawing/></w:r></w:p><w:p><w:r><w:t xml:space=\"preserve\">   </w:t></w:r></w:p>"


def build(d: Path):
    """[(label, path, class or None for an admission, the instruction its 'What to do' must carry)]"""
    m = members()
    with_body = lambda b: dict(m, **{"word/document.xml": b})  # noqa: E731
    macro = dict(m)
    macro["[Content_Types].xml"] = m["[Content_Types].xml"].replace(
        b"application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml",
        b"application/vnd.ms-word.document.macroEnabled.main+xml")
    assert macro["[Content_Types].xml"] != m["[Content_Types].xml"], "the fixture's main content type was not found"
    macro["word/vbaProject.bin"] = CFB + bytes(56)
    # each macro signal ALONE, so a check that drops either one is caught (review, 2026-10-20)
    macro_type_only = {k: v for k, v in macro.items() if k != "word/vbaProject.bin"}
    macro_bin_only = dict(m, **{"word/vbaProject.bin": CFB + bytes(56)})
    # Strict Open XML: the same body in the namespace a Strict save writes, which this script cannot read
    strict = with_body(m["word/document.xml"].replace(W_NS.encode(), b"http://purl.oclc.org/ooxml/wordprocessingml/main"))
    # a body member flagged ENCRYPTED in the zip's central directory: zipfile refuses to read it
    zenc = write_zip(d / "p.docx", m).read_bytes()
    at = [i for i in range(len(zenc)) if zenc.startswith(b"PK\x01\x02", i) and zenc[i + 46:i + 46 + 17] == b"word/document.xml"]
    assert len(at) == 1, "the body's central-directory entry was not found once"
    zenc = zenc[:at[0] + 8] + bytes([zenc[at[0] + 8] | 1]) + zenc[at[0] + 9:]
    (d / "p.docx").write_bytes(zenc)
    raw = d / "document.xml"
    raw.write_bytes(m["word/document.xml"])
    (d / "a.pdf").write_bytes(b"%PDF-1.4\n% a synthetic file, not a Word document\n%%EOF\n")
    (d / "b.doc").write_bytes(CFB + bytes(504) + "WordDocument".encode("utf-16-le") + bytes(64))
    (d / "e.docx").write_bytes(CFB + bytes(504) + "EncryptionInfo".encode("utf-16-le") + bytes(16)
                               + "EncryptedPackage".encode("utf-16-le") + bytes(64))
    # ONE of the two stream names, as a .doc's own text could hold it: not enough to be called encrypted
    (d / "t.doc").write_bytes(CFB + bytes(504) + "WordDocument".encode("utf-16-le") + bytes(64)
                              + "EncryptedPackage".encode("utf-16-le") + bytes(64))
    return [
        ("a PDF", d / "a.pdf", "not a Word document", "OCR"),
        ("a legacy binary .doc", d / "b.doc", "not a Word document", "Step 1b"),
        ("a spreadsheet package", write_zip(d / "c.xlsx", {"[Content_Types].xml": b"<Types/>",
                                                           "xl/workbook.xml": b"<workbook/>"}),
         "not a Word document", "save it as a .docx"),
        ("a Word package saved as .zip", write_zip(d / "f.zip", m), "not a Word document", "save it as a .docx"),
        ("an encrypted package named .docx", d / "e.docx", "password-protected", "remove the password"),
        ("a .docm", write_zip(d / "g.docm", macro), "macro-enabled", "leaves the macros"),
        ("the same macro package renamed .docx", write_zip(d / "h.docx", macro), "macro-enabled", "leaves the macros"),
        ("a body with a picture and no text", write_zip(d / "i.docx", with_body(body(PICTURE))), "image-only", "OCR"),
        ("a body of 1,001 paragraphs", write_zip(d / "j.docx", with_body(body(text_paras(1001)))),
         "over the size limit", "split it"),
        ("a macro content type alone, named .docx", write_zip(d / "q.docx", macro_type_only), "macro-enabled",
         "leaves the macros"),
        ("a macro project alone, named .docx", write_zip(d / "r.docx", macro_bin_only), "macro-enabled",
         "leaves the macros"),
        ("a .docx saved as Strict Open XML", write_zip(d / "s.docx", strict), "not a Word document", "Strict Open XML"),
        ("a body member the zip encrypts", d / "p.docx", "not a Word document", "save it as a .docx"),
        ("a legacy .doc whose text holds one encryption stream name", d / "t.doc", "not a Word document",
         "its password removed"),
        ("the clean fixture", write_zip(d / "k.docx", m), None, None),
        ("a body of exactly 1,000 paragraphs", write_zip(d / "l.docx", with_body(body(text_paras(1000)))), None, None),
        ("a picture WITH text", write_zip(d / "n.docx", with_body(body(PICTURE + text_paras(2)))), None, None),
        ("a raw document.xml", raw, None, None),
    ]


def script_for(tree: str, ref, d: Path) -> Path:
    rel = f"{tree}/scripts/extract_paragraphs.py"
    if ref is None:
        return ROOT / rel
    out = d / f"ref-{tree}" / "extract_paragraphs.py"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(subprocess.run(["git", "show", f"{ref}:{rel}"], cwd=ROOT, capture_output=True, check=True).stdout)
    return out


def run_tree(tree: str, ref, d: Path):
    script = script_for(tree, ref, d)
    print(f"\n[{tree}] {script.relative_to(ROOT).as_posix() if ref is None else f'{ref}:{tree}/scripts/extract_paragraphs.py'}")
    met = {"refusal": [0, 0], "admission": [0, 0]}
    for label, path, cls, todo in build(d / tree):
        js = d / tree / f"{path.stem}.json"
        if js.exists():
            js.unlink()
        r = subprocess.run([sys.executable, str(script), str(path), str(js)], capture_output=True, text=True,
                           encoding="utf-8", errors="replace", cwd=d / tree)
        out = (r.stdout or "") + (r.stderr or "")
        kind = "refusal" if cls else "admission"
        met[kind][1] += 1
        if cls:
            conds = [ok(f"{tree} REFUSED {label}: exit 2", r.returncode == 2, f"exit {r.returncode}"),
                     ok(f"{tree} REFUSED {label}: the banner, and the class '{cls}' named",
                        "REFUSED AT ADMISSION" in r.stderr and f"outside what the skill accepts: {cls}." in r.stderr,
                        (out.strip().splitlines() or ["(no output)"])[-1][:120]),
                     ok(f"{tree} REFUSED {label}: what to do, carrying '{todo}'",
                        any(l.strip().startswith("What to do:") and todo in l for l in r.stderr.splitlines())),
                     ok(f"{tree} REFUSED {label}: no traceback, and no paragraphs.json written",
                        "Traceback" not in out and not js.exists())]
        else:
            got = json.loads(js.read_text(encoding="utf-8")) if js.is_file() else None
            conds = [ok(f"{tree} ADMITTED {label}: exit 0 and a non-empty paragraphs.json",
                        r.returncode == 0 and isinstance(got, list) and len(got) > 0,
                        f"exit {r.returncode}; " + (out.strip().splitlines() or ["(no output)"])[-1][:120]),
                     ok(f"{tree} ADMITTED {label}: no refusal banner", "REFUSED AT ADMISSION" not in out)]
        met[kind][0] += all(conds)
    # A paragraphs.json an EARLIER run left at the output path is kept, and the refusal says it is not this
    # document's - "no paragraphs.json was written" alone would read as if the workdir held none (review).
    pdf, stale = d / tree / "a.pdf", d / tree / "stale.json"
    stale.write_text("[]", encoding="utf-8")
    r = subprocess.run([sys.executable, str(script), str(pdf), str(stale)], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", cwd=d / tree)
    ok(f"{tree} REFUSED with an earlier run's paragraphs.json in place: kept, and said not to be this document's",
       r.returncode == 2 and stale.read_text(encoding="utf-8") == "[]" and "from an earlier run" in r.stderr
       and "NOT this document's" in r.stderr, f"exit {r.returncode}")
    print(f"[{tree}] refusal cases met: {met['refusal'][0]} of {met['refusal'][1]}; "
          f"admission cases met: {met['admission'][0]} of {met['admission'][1]}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ref", default=None, help="run both trees' scripts as they stood at this commit (red first)")
    args = ap.parse_args()
    d = Path(tempfile.mkdtemp(prefix="lt-envelope-"))
    try:
        for tree in ("uk", "us"):
            (d / tree).mkdir()
            run_tree(tree, args.ref, d)
    finally:
        shutil.rmtree(d, ignore_errors=True)
    print(f"\nENVELOPE: {CHECKED} check(s), {len(FAIL)} failure(s)")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
