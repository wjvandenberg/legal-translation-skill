"""Translate text inside word/comments.xml while preserving namespace declarations.

OOXML stores Word comments (margin annotations) in word/comments.xml. Because
the main translation pipeline only processes document.xml, comment text is
silently left in the source language. This is a HIGH severity defect — comments
are highly visible to anyone reviewing the document.

============================================================================
WHY THIS SCRIPT EXISTS — DO NOT RE-INVENT WITH ElementTree
============================================================================

Earlier versions of the skill told the user to translate comments.xml with
ElementTree and graft the original root-element opening tag back on. That
approach is WRONG and produces .docx files that Word refuses to open with an
"unreadable content" error.

ElementTree renames namespace prefixes during serialisation:
  * `w14:paraId`  -> `ns2:paraId`
  * `mc:Ignorable`-> `ns1:Ignorable`
  * ... and so on, deep inside the body of the XML.

Grafting the original root tag back restores the namespace *declarations* at
the top, but the body still uses `ns1:`, `ns2:`, etc. — prefixes that are no
longer declared anywhere. Word reads the file, finds unbound prefixes, and
refuses to open it.

The only reliable fix is to avoid XML parsing altogether for this file:
match the text inside <w:t> and <w:delText> nodes with a regex and replace
just that text. Everything else in the file passes through byte-for-byte.

============================================================================

Usage
-----
    # Step 1 — list source comments so you can draft the translations
    python translate_comments.py <original.docx> --list

    # Step 2 — supply translations via a JSON file (comment-id -> English)
    python translate_comments.py <original.docx> <output_dir> --translations comments.json

Inputs
------
    <original.docx>     The source-language .docx
    <output_dir>        The skill work directory (e.g. workdir/final).
                        The translated file is written to
                        <output_dir>/word/comments.xml.

Translations JSON format
------------------------
    {
      "19": "To be named as \"the Plots\"?",
      "29": "To be discussed with Acme",
      "31": "Possibly include a definition",
      ...
    }

    Keys are comment IDs as strings (use quotes even if the ID is numeric).
    Values are the English translation of the full comment body. One entry
    per comment — any cross-run formatting inside the comment is flattened.

    A COMMENT OF SEVERAL PARAGRAPHS is declared with ONE LINE BREAK between
    its paragraphs' English — one piece per TEXT PARAGRAPH, in order. A text
    paragraph is a paragraph of the comment whose own text holds anything but
    whitespace; an empty paragraph is not counted and is left as it is.
    --list prints each comment's text paragraphs one per line, with their
    count, so the pieces can be written against it.

How text replacement works
--------------------------
    A declaration with NO line break: for each <w:comment w:id="N"> block,
    the script finds the first <w:t> inside it and puts the full English
    translation there. Every other <w:t> and every <w:delText> inside the
    same block is emptied, so a comment of several paragraphs arrives as one
    (Step 10's check counts it as flattened, never blocking).

    A declaration WITH a line break is split on it. With as many pieces as
    the source comment has text paragraphs, piece k goes into the first <w:t>
    of text paragraph k and every other <w:t> of that paragraph is emptied; a
    paragraph with no text is left as it is, and every <w:delText> is emptied
    as above. ANY OTHER COUNT IS REFUSED: the script names every such comment
    with both counts, exits 2 and writes nothing. So is a comment one of whose
    paragraphs holds a nested paragraph (a text box), whose text paragraphs
    cannot be counted by this regex — declare that one with no line break.

    The text is read and shown AS WORD SHOWS IT: character data is unescaped
    ('&amp;' is shown as '&'), so a comment already in English is copied into
    the JSON exactly as --list prints it, and escaped once on the way back.
    (Until 2026-09-29 --list printed the escaped form, so a verbatim copy was
    escaped twice and Word showed '&amp;' — register F47.)

Output
------
    <output_dir>/word/comments.xml

    The repack script handles comments.xml automatically if you pass
    --comments-dir. If your repack command does not support that flag, add
    comments.xml manually after repacking:

        with zipfile.ZipFile(output_docx, 'a') as zout:
            zout.writestr('word/comments.xml', open(translated_comments_path,'rb').read())
"""
import sys
import os
import re
import json
import zipfile
import argparse

def _check_self_integrity():
    """Detect install-time truncation. Whole-file scan tolerates null-padding."""
    try:
        with open(os.path.abspath(__file__), 'r', encoding='utf-8') as f:
            content = f.read()
    except OSError:
        return
    if '\n# === SKILL FILE COMPLETE ===' not in content:
        msg = (
            "\n" + "=" * 60 + "\n"
            "[skill] FILE INTEGRITY CHECK FAILED — script truncated.\n"
            f"  File: {os.path.abspath(__file__)}\n"
            f"  Size: {len(content):,} bytes (sentinel marker missing).\n"
            "  Re-install the skill from the .skill / .zip archive.\n"
            + "=" * 60 + "\n"
        )
        print(msg, file=sys.stderr)
        sys.exit(3)


_check_self_integrity()



# Match <w:t ...>TEXT</w:t>.  Captures: opening tag, text, closing tag.
_WT_RE = re.compile(r'(<w:t(?:\s[^>]*)?>)([^<]*)(</w:t>)')
# Match <w:delText ...>TEXT</w:delText>
_WDELTEXT_RE = re.compile(r'(<w:delText(?:\s[^>]*)?>)([^<]*)(</w:delText>)')
# Match a whole <w:comment ... w:id="X" ...> ... </w:comment> block
_COMMENT_RE = re.compile(
    r'(<w:comment\b[^>]*?\sw:id="([^"]+)"[^>]*>)(.*?)(</w:comment>)',
    re.DOTALL,
)

# Match a whole <w:p ...>...</w:p> paragraph, never crossing its own end tag. <w:p/>, an empty
# paragraph, is not matched; neither is <w:pPr>, whose name runs on past the 'p'.
_WP_RE = re.compile(r'<w:p(?:\s[^>]*)?>(?:(?!</w:p>).)*?</w:p>', re.DOTALL)
# A paragraph's opening tag, the self-closing form included -- found INSIDE a matched paragraph,
# it means a nested paragraph (a text box), so the bounded match cannot say where the outer ends.
_WP_OPEN_RE = re.compile(r'<w:p(?:\s[^>]*)?/?>')
_ENTITY_RE = re.compile(r'&(amp|lt|gt|quot|apos|#[0-9]+|#x[0-9a-fA-F]+);')
_NAMED = {'amp': '&', 'lt': '<', 'gt': '>', 'quot': '"', 'apos': "'"}
_BREAK = chr(10)          # the declared line break -- built, never typed as an escape


def _xml_unescape(s):
    """Character data as Word shows it -- the regex over the raw XML leaves it escaped (F47)."""
    def one(m):
        e = m.group(1)
        if e in _NAMED:
            return _NAMED[e]
        try:
            return chr(int(e[2:], 16) if e[1] in 'xX' else int(e[1:]))
        except (ValueError, OverflowError):
            return m.group(0)
    return _ENTITY_RE.sub(one, s)


def _wt_text(block):
    """The text of every <w:t> in a block, in order, as Word shows it."""
    return ''.join(_xml_unescape(mm.group(2)) for mm in _WT_RE.finditer(block))


def _paragraphs(body):
    """(the paragraph matches of one comment body, whether any of them holds a nested paragraph)."""
    paras = list(_WP_RE.finditer(body))
    nested = any(_WP_OPEN_RE.search(pm.group(0), _WP_OPEN_RE.match(pm.group(0)).end()) for pm in paras)
    return paras, nested


def _text_paragraphs(body):
    """(the text of each TEXT paragraph of one comment body, in order -- a paragraph whose own
    <w:t> text holds anything but whitespace -- and whether any paragraph is nested)."""
    paras, nested = _paragraphs(body)
    return [t for t in (_wt_text(pm.group(0)) for pm in paras) if t.strip()], nested


def parse_source_comments(xml_text):
    """Return [(comment_id, concatenated_source_text), ...] in document order, as Word shows it."""
    return [(m.group(2), _wt_text(m.group(3))) for m in _COMMENT_RE.finditer(xml_text)]


def source_comment_paragraphs(xml_text):
    """Return [(comment_id, [text of each text paragraph], nested), ...] in document order."""
    out = []
    for m in _COMMENT_RE.finditer(xml_text):
        texts, nested = _text_paragraphs(m.group(3))
        out.append((m.group(2), texts, nested))
    return out

def _xml_escape(s):
    return s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

def _ensure_xml_space_preserve(opening_tag):
    """Insert xml:space="preserve" into a <w:t ...> opening tag if missing."""
    if 'xml:space' in opening_tag:
        return opening_tag
    # opening_tag is e.g. '<w:t>' or '<w:t rsidR="..">'
    return opening_tag[:-1] + ' xml:space="preserve">'

def translate_comments_xml(xml_text, translations):
    """Replace the text in each <w:comment> whose id is in translations.

    Returns (new_xml_text, translated_ids, untranslated_ids, split_ids, refused): split_ids are the
    comments written paragraph by paragraph, and refused is [(comment_id, pieces, text paragraphs)]
    for every declaration with a line break that cannot be split -- text paragraphs None where a
    paragraph is nested. WHEN refused IS NOT EMPTY THE CALLER MUST WRITE NOTHING.
    """
    translated = []
    untranslated = []
    split = []
    refused = []

    def fill(block, text):
        """text into the block's first <w:t>, every other <w:t> in the block emptied."""
        first = {'done': False}

        def wt(mm):
            op, _txt, cl = mm.group(1), mm.group(2), mm.group(3)
            if not first['done']:
                first['done'] = True
                return _ensure_xml_space_preserve(op) + _xml_escape(text) + cl
            # Empty out subsequent <w:t> runs in this block.
            return op + cl

        return _WT_RE.sub(wt, block), first['done']

    def dt(mm):
        op, _txt, cl = mm.group(1), mm.group(2), mm.group(3)
        return op + cl

    def rewrite_comment(m):
        opening, cid, body, closing = m.group(1), m.group(2), m.group(3), m.group(4)
        if cid not in translations:
            # Leave comments without a translation alone so the reviewer can
            # see which ones still need work. parse_source_comments will
            # report them in untranslated_ids.
            if _wt_text(body).strip():
                untranslated.append(cid)
            return m.group(0)

        new_text = translations[cid]
        if _BREAK in new_text:
            # One piece per TEXT paragraph, in order; an empty paragraph left as it is.
            pieces = new_text.split(_BREAK)
            paras, nested = _paragraphs(body)
            text_at = [i for i, pm in enumerate(paras) if _wt_text(pm.group(0)).strip()]
            if nested or len(pieces) != len(text_at):
                refused.append((cid, len(pieces), None if nested else len(text_at)))
                return m.group(0)
            parts, pos, k = [], 0, 0
            for i, pm in enumerate(paras):
                parts.append(body[pos:pm.start()])
                block = pm.group(0)
                if k < len(text_at) and i == text_at[k]:
                    block, _done = fill(block, pieces[k])
                    k += 1
                parts.append(block)
                pos = pm.end()
            parts.append(body[pos:])
            translated.append(cid)
            split.append(cid)
            return opening + _WDELTEXT_RE.sub(dt, ''.join(parts)) + closing

        new_body, done = fill(body, new_text)
        new_body = _WDELTEXT_RE.sub(dt, new_body)
        if not done:
            # The comment had no <w:t> at all (unusual) — skip silently.
            return m.group(0)
        translated.append(cid)
        return opening + new_body + closing

    new_xml = _COMMENT_RE.sub(rewrite_comment, xml_text)
    return new_xml, translated, untranslated, split, refused

def main():
    p = argparse.ArgumentParser(
        description='Translate text inside word/comments.xml without mangling namespaces.'
    )
    p.add_argument('original', help='Original .docx file')
    p.add_argument(
        'output_dir',
        nargs='?',
        help='Output directory — translated file written to <dir>/word/comments.xml',
    )
    p.add_argument(
        '--translations',
        help='JSON file mapping comment IDs (strings) to English translations',
    )
    p.add_argument(
        '--list',
        action='store_true',
        help='List source comments and exit (to help draft the translations JSON)',
    )
    args = p.parse_args()

    with zipfile.ZipFile(args.original, 'r') as zf:
        if 'word/comments.xml' not in zf.namelist():
            print('No word/comments.xml found in this .docx — nothing to translate.')
            return 0
        xml_text = zf.read('word/comments.xml').decode('utf-8')

    if args.list:
        # Surface the same English-passthrough rule the body translator
        # already follows, at the moment the operator is about to decide
        # what to write into the translations JSON. No detection, no
        # tagging — just a reminder. If a comment below is already in
        # English, copy it verbatim into "en"; do not rewrite or polish.
        print(
            'REMINDER: If a comment below is already in English, copy the source\n'
            "into 'en' verbatim. Do not rewrite or polish — the parties wrote those\n"
            'words and will read them back.\n'
        )
        print(
            'Each comment is listed with its count of text paragraphs, then each on its own line,'
            ' as Word shows it. Declare a comment of several paragraphs with one line break between'
            " its paragraphs' English (written " + chr(92) + "n in the JSON), one piece per text"
            ' paragraph; an empty paragraph is not counted.' + _BREAK
        )
        for (cid, texts, nested), (_cid, whole) in zip(source_comment_paragraphs(xml_text),
                                                        parse_source_comments(xml_text)):
            if nested:
                print(f'[{cid}] holds a nested paragraph (a text box) - declare it with no line break')
                print(f'    {whole}')
            elif texts:
                n = len(texts)
                print(f'[{cid}] {n} text paragraph{"" if n == 1 else "s"}')
                for t in texts:
                    print(f'    {t}')
        return 0

    if not args.output_dir:
        p.error('output_dir is required (unless --list is used)')
    if not args.translations:
        p.error('--translations is required (unless --list is used)')

    with open(args.translations, 'r', encoding='utf-8') as f:
        translations = {str(k): v for k, v in json.load(f).items()}

    new_xml, translated, untranslated, split, refused = translate_comments_xml(xml_text, translations)
    if refused:
        for cid, k, n in refused:
            if n is None:
                print(f'  REFUSED: comment {cid}: a paragraph of the source comment holds a nested '
                      'paragraph (a text box), so its text paragraphs cannot be counted - declare it '
                      'with no line break.')
            else:
                print(f'  REFUSED: comment {cid}: the declaration has {k} piece(s) - {k - 1} line '
                      f'break(s) - and the source comment has {n} text paragraph(s).')
        print(f'  {len(refused)} comment(s) refused; comments.xml NOT written. Declare one piece per '
              'text paragraph, as --list prints them, and re-run.')
        return 2

    out_path = os.path.join(args.output_dir, 'word', 'comments.xml')
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, 'wb') as f:
        f.write(new_xml.encode('utf-8'))

    total_with_text = sum(
        1 for _, t in parse_source_comments(xml_text) if t.strip()
    )
    print(f'Wrote translated comments.xml -> {out_path}')
    print(f'  {len(translated)} of {total_with_text} source comments translated.')
    if split:
        print(f'  {len(split)} written paragraph by paragraph, one piece per text paragraph.')
    if untranslated:
        print(
            f'  WARNING: {len(untranslated)} comment(s) without a translation: '
            f'{untranslated[:20]}'
        )
        print(
            '           Add entries for these IDs to the translations JSON and re-run.'
        )

    # Quick self-check: make sure no unbound prefixes ended up in the output.
    # Find the root element (first `<w:comments ...>` or similar) and inspect
    # only its namespace declarations.
    root_match = re.search(r'<w:comments\b[^>]*>', new_xml)
    declared = set()
    if root_match:
        declared = set(re.findall(r'xmlns:(\w+)=', root_match.group(0)))
    used = set(re.findall(r'<(\w+):', new_xml)) | set(
        re.findall(r'\s(\w+):[A-Za-z]', new_xml)
    )
    unbound = used - declared - {'xml', 'xmlns'}
    if unbound:
        print(f'  ERROR: unbound namespace prefix(es) in output: {sorted(unbound)}')
        print('         This .docx will not open in Word. Re-run or file a bug.')
        return 2

    return 0

if __name__ == '__main__':
    sys.exit(main())

# === SKILL FILE COMPLETE ===
