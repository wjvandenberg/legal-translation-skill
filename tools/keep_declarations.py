# -*- coding: utf-8 -*-
"""KEEP DECLARATIONS — what a compliant KEEP-AS-IS run writes beside the notes for each side part, in ONE place.

WHY ONE PLACE. Step 10's wiring (branch 11, 2026-09-30) put the delivered-document check inside repack, and the
check reads every side part the ORIGINAL carries against a declaration beside the notes: a part delivered in
the source's own words with no declaration keeping it is a blocking finding. Every harness that delivers a side
part as the original's therefore has to declare it kept, as a compliant run does -- and three of them built that
declaration by hand, three different ways (the glossary in tools/delivered_corpus_arm.py and in
tests/test_glossary_route.py, the comment and the footnote in tests/test_no_delivered_byte_moves.py), while
tools/render_diff.py had none at all, so the wired check refused its NEW arm on 5 of 12 real documents, uk and
us alike, while its OLD arm delivered (register I-34). Review finding 6 of the wiring slice: a declaration built
differently in each harness is a harness that can disagree with the check about what "kept" means, and nobody
would see which.

WHAT IT WRITES, PER STEP 8 (skill-docs/08-aux-and-quality.md), for each side part the ORIGINAL carries with
letter-bearing text -- and nothing for a part without:
  headers_footers.json        8b: the script's own `translate_headers_footers.py --extract` scaffold, run from
                              the scripts folder given, with `en` set equal to `text` on every entry -- "for a
                              preserved entry, set en == text".
  comments_translations.json  8c: per comment id, Word's text: a comment of several TEXT PARAGRAPHS (a w:p of
                              the comment whose own w:t text holds anything but whitespace) as those paragraphs
                              joined by a line break, as --list shows them and Step 8c says to declare; a comment
                              of one as every w:t of it -- the two readings the check compares a keep against.
  footnotes_translations.json,
  endnotes_translations.json,
  glossary_translations.json  8d and 8e: every letter-bearing w:t and w:delText text, exactly as the template's
                              regex reads it from the raw XML (so `&amp;` stays `&amp;`), mapped to itself.
The letter test is validate_apply.py's own (_COMPLETENESS_LETTER), so the helper never declares fewer texts than
the check looks for.

WHAT IT IS NOT: a way to make the check quiet. It declares what a run that KEEPS the side parts delivers, and is
right only where that is what was delivered. A delivery that CHANGED a kept text reads `moved` and blocks; an
anchor lost in the body is a finding whatever is declared. render_diff renders the body alone and delivers every
side part as the original's, which is exactly the case this describes.

No work at import. Writes BYTES, so nothing is re-encoded on the way out.

    from keep_declarations import write_keep_declarations
    write_keep_declarations(original_docx, notes_dir, scripts_dir)                     # every kind
    write_keep_declarations(original_docx, notes_dir, scripts_dir, kinds={"glossary"})
"""
import json
import os
import re
import subprocess
import sys
import zipfile
from pathlib import Path

from lxml import etree

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
KINDS = ("headers_footers", "comments", "footnotes", "endnotes", "glossary")
LETTER = re.compile(r"[^\W\d_]")                                     # validate_apply.py's _COMPLETENESS_LETTER
TEXT_NODE = re.compile(r"<w:(t|delText)(?:\s[^>]*)?>([^<]*)</w:\1>")  # Step 8d's two regexes, as one
HF_PART = re.compile(r"word/(?:header|footer)\d*\.xml$")
NOTE_PARTS = (("footnotes", "word/footnotes.xml", "footnotes_translations.json"),
              ("endnotes", "word/endnotes.xml", "endnotes_translations.json"),
              ("glossary", "word/glossary/document.xml", "glossary_translations.json"))


def _letter_texts(xml_bytes):
    """Every letter-bearing w:t and w:delText text as the raw XML holds it, escaped."""
    return [m.group(2) for m in TEXT_NODE.finditer(xml_bytes.decode("utf-8")) if LETTER.search(m.group(2))]


def _comment_declaration(comment):
    """Word's text for one comment, in the form the check compares a keep against (see the docstring)."""
    p_tag, t_tag = f"{{{W}}}p", f"{{{W}}}t"
    paras = []
    for p in comment.iter(p_tag):
        own = "".join(t.text or "" for t in p.iter(t_tag) if next(t.iterancestors(p_tag), None) is p)
        if own.strip():
            paras.append(own)
    if len(paras) > 1:
        return "\n".join(paras)
    return "".join(t.text or "" for t in comment.iter(t_tag))


def _write(path, data):
    Path(path).write_bytes(json.dumps(data, ensure_ascii=False).encode("utf-8"))


def write_keep_declarations(original_docx, notes_dir, scripts_dir, kinds=KINDS):
    """Write beside the notes the keep declaration of every side part of `original_docx` that carries letter-
    bearing text, for the `kinds` asked (any of KINDS). Returns {file name: entries written}; a kind with
    nothing to declare writes no file and is absent from the result. A file this call WRITES replaces any of
    the same name; a file it does not write is LEFT AS IT IS -- a caller who wants the keep set alone starts
    from a folder holding no declaration (render_diff copies none beside the notes). Raises ValueError on an
    unknown kind, RuntimeError if Step 8b's --extract fails."""
    unknown = set(kinds) - set(KINDS)
    if unknown:
        raise ValueError(f"unknown kind(s) {sorted(unknown)}; the kinds are {', '.join(KINDS)}")
    notes_dir = Path(notes_dir)
    with zipfile.ZipFile(original_docx) as z:
        parts = {n: z.read(n) for n in z.namelist() if n.startswith("word/") and n.endswith(".xml")}
    out = {}

    if "headers_footers" in kinds and any(HF_PART.match(n) and _letter_texts(b) for n, b in parts.items()):
        scaffold = notes_dir / "headers_footers.json"
        res = subprocess.run([sys.executable, str(Path(scripts_dir) / "translate_headers_footers.py"),
                              str(original_docx), "--extract", str(scaffold)],
                             capture_output=True, text=True, encoding="utf-8", errors="replace",
                             env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONIOENCODING="utf-8"))
        if res.returncode != 0 or not scaffold.is_file():
            # The script's output is NOT quoted: its warnings can name the document's text.
            raise RuntimeError(f"Step 8b's translate_headers_footers.py --extract failed (exit {res.returncode})")
        entries = json.loads(scaffold.read_text(encoding="utf-8"))
        for e in entries:
            e["en"] = e.get("text")
        if entries:
            _write(scaffold, entries)
            out[scaffold.name] = len(entries)
        else:
            scaffold.unlink()

    if "comments" in kinds and "word/comments.xml" in parts:
        decl = {}
        for c in etree.fromstring(parts["word/comments.xml"]).iter(f"{{{W}}}comment"):
            letters = "".join(x.text or "" for x in c.iter(f"{{{W}}}t", f"{{{W}}}delText"))
            if LETTER.search(letters):
                decl[c.get(f"{{{W}}}id")] = _comment_declaration(c)
        if decl:
            _write(notes_dir / "comments_translations.json", decl)
            out["comments_translations.json"] = len(decl)

    for kind, part, name in NOTE_PARTS:
        if kind in kinds and part in parts:
            texts = sorted(set(_letter_texts(parts[part])))
            if texts:
                _write(notes_dir / name, {t: t for t in texts})
                out[name] = len(texts)
    return out
