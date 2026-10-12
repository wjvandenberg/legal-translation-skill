"""Translate numbering format strings in word/numbering.xml.

OOXML stores list/heading numbering definitions in word/numbering.xml.
Each numbering level has a w:lvlText element whose w:val attribute defines
the format string displayed as the list prefix — e.g. "%1. sz. Melléklet"
produces "1. sz. Melléklet", "2. sz. Melléklet", etc.

If these format strings contain source-language text, the translated document
will show mixed-language numbering (e.g. "Schedule 1. sz. Melléklet" or just
"1. sz. Melléklet" when only the paragraph body is translated). This script
extracts those format strings, applies a translation map, and writes the
modified numbering.xml.

Usage:
    python translate_numbering.py <original.docx> <output_numbering.xml> [--language <lang>]

The script also accepts a JSON file with custom translations:
    python translate_numbering.py <original.docx> <output_numbering.xml> --custom <translations.json>

The JSON format is: {"source pattern": "target pattern", ...}
where patterns can use %1, %2, etc. as numbering placeholders.

An auto-numbered attachment label follows the operator's declared English in
paragraphs.json: "Annex %1" where the notes label attachments Annex and never
Schedule, "Schedule %1" otherwise (--paragraphs, or found beside final/).

The source language is the one declared at Step 1c (source_language.json beside
paragraphs.json); --language overrides it. A language with no built-in map says
NOT SUPPORTED and applies none. Every format string still carrying a word after
the maps is listed NOT TRANSLATED. Exit 1 when the language was declared (or
given with --language) and supported, and such a string is in numbering the
document uses: render it with --custom, or keep it by mapping it to itself.
Exit 0 otherwise.
"""
import sys
import os
import re
import html
import json
import zipfile
import xml.etree.ElementTree as ET
from xml.sax.saxutils import escape as xml_escape

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

# THE DECLARED SOURCE LANGUAGE (branch 12 slice 12b) is read through the one shared policy
# in source_language_markers.py, beside this script.
# NO .pyc INSIDE A SHIPPED TREE: the guard must precede the sibling import (register
# I-18's family; tests/test_no_bytecode_in_tree.py discovers the importers).
sys.dont_write_bytecode = True
_SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)
from source_language_markers import not_supported, resolve_source_language  # noqa: E402


W = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'

# Built-in translation maps per source language.
# Keys are lowercase source patterns (with %N placeholders preserved).
# Values are English replacements.
#
# The matching is case-insensitive on the source side but preserves the
# exact replacement string on the target side.

HUNGARIAN_MAP = {
    # Schedules / Annexes
    r'%(\d+)\.\s*sz\.\s*melléklet':  r'Schedule %\1',
    r'%(\d+)\.\s*melléklet':         r'Schedule %\1',
    r'melléklet\s*%(\d+)':           r'Schedule %\1',
    # Appendix
    r'%(\d+)\.\s*sz\.\s*függelék':   r'Appendix %\1',
    r'%(\d+)\.\s*függelék':          r'Appendix %\1',
    # Chapter
    r'%(\d+)\.\s*fejezet':           r'Chapter %\1',
    # Part
    r'%(\d+)\.\s*rész':              r'Part %\1',
    # Article (internal)
    r'%(\d+)\.\s*cikk':              r'Clause %\1',
    # Section
    r'%(\d+)\.\s*szakasz':           r'Section %\1',
    # Simple "sz." (abbreviation for "számú" = "numbered")
    r'%(\d+)\.\s*sz\.':              r'%\1.',
}

ITALIAN_MAP = {
    r'%(\d+)\.\s*allegato':          r'Schedule %\1',
    r'allegato\s*%(\d+)':            r'Schedule %\1',
    r'%(\d+)\.\s*appendice':         r'Appendix %\1',
    r'%(\d+)\.\s*capitolo':          r'Chapter %\1',
    r'%(\d+)\.\s*articolo':          r'Article %\1',
    r'%(\d+)\.\s*sezione':           r'Section %\1',
    r'%(\d+)\.\s*parte':             r'Part %\1',
}

GERMAN_MAP = {
    r'%(\d+)\.\s*anlage':            r'Schedule %\1',
    r'anlage\s*%(\d+)':              r'Schedule %\1',
    r'%(\d+)\.\s*anhang':            r'Appendix %\1',
    r'%(\d+)\.\s*abschnitt':         r'Section %\1',
    r'%(\d+)\.\s*teil':              r'Part %\1',
    r'%(\d+)\.\s*kapitel':           r'Chapter %\1',
    r'%(\d+)\.\s*artikel':           r'Article %\1',
}

FRENCH_MAP = {
    r'%(\d+)\.\s*annexe':            r'Schedule %\1',
    r'annexe\s*%(\d+)':              r'Schedule %\1',
    r'%(\d+)\.\s*appendice':         r'Appendix %\1',
    r'%(\d+)\.\s*chapitre':          r'Chapter %\1',
    r'%(\d+)\.\s*article':           r'Article %\1',
    r'%(\d+)\.\s*section':           r'Section %\1',
    r'%(\d+)\.\s*partie':            r'Part %\1',
}

SPANISH_MAP = {
    r'%(\d+)\.\s*anexo':             r'Schedule %\1',
    r'anexo\s*%(\d+)':               r'Schedule %\1',
    r'%(\d+)\.\s*apéndice':          r'Appendix %\1',
    r'%(\d+)\.\s*capítulo':          r'Chapter %\1',
    r'%(\d+)\.\s*artículo':          r'Article %\1',
    r'%(\d+)\.\s*sección':           r'Section %\1',
    r'%(\d+)\.\s*parte':             r'Part %\1',
}

PORTUGUESE_MAP = {
    r'%(\d+)\.\s*anexo':             r'Schedule %\1',
    r'anexo\s*%(\d+)':               r'Schedule %\1',
    r'%(\d+)\.\s*apêndice':          r'Appendix %\1',
    r'%(\d+)\.\s*capítulo':          r'Chapter %\1',
    r'%(\d+)\.\s*artigo':            r'Article %\1',
    r'%(\d+)\.\s*secção':            r'Section %\1',
    r'%(\d+)\.\s*parte':             r'Part %\1',
}

DUTCH_MAP = {
    r'%(\d+)\.\s*bijlage':           r'Schedule %\1',
    r'bijlage\s*%(\d+)':             r'Schedule %\1',
    r'%(\d+)\.\s*aanhangsel':        r'Appendix %\1',
    r'%(\d+)\.\s*hoofdstuk':         r'Chapter %\1',
    r'%(\d+)\.\s*artikel':           r'Article %\1',
    r'%(\d+)\.\s*afdeling':          r'Section %\1',
    r'%(\d+)\.\s*deel':              r'Part %\1',
}

POLISH_MAP = {
    r'%(\d+)\.\s*załącznik':         r'Schedule %\1',
    r'załącznik\s*%(\d+)':           r'Schedule %\1',
    r'%(\d+)\.\s*dodatek':           r'Appendix %\1',
    r'%(\d+)\.\s*rozdział':          r'Chapter %\1',
    r'%(\d+)\.\s*artykuł':           r'Article %\1',
    r'%(\d+)\.\s*sekcja':            r'Section %\1',
    r'%(\d+)\.\s*część':             r'Part %\1',
}

FINNISH_MAP = {
    r'%(\d+)\.\s*liite':             r'Schedule %\1',
    r'liite\s*%(\d+)':               r'Schedule %\1',
    r'%(\d+)\.\s*lisäys':            r'Appendix %\1',
    r'%(\d+)\.\s*luku':              r'Chapter %\1',
    r'%(\d+)\.\s*artikla':           r'Article %\1',
    r'%(\d+)\.\s*jakso':             r'Section %\1',
    r'%(\d+)\.\s*osa':               r'Part %\1',
}

# CHINESE AND JAPANESE (register E4, branch 12 slice 12b). Each entry renders a label the way
# the skill's own lexicon does, and LEXICON_ROWS below cites the row, so the numbering never
# disagrees with the body text. A label no lexicon row sanctions (Chinese 附件 or 节, for
# example) is deliberately absent: the run lists it NOT TRANSLATED and the operator renders it
# with --custom, which is better than a rendering nobody chose.
CHINESE_MAP = {
    r'第\s*%(\d+)\s*条':              r'Article %\1',
    r'第\s*%(\d+)\s*章':              r'Chapter %\1',
    r'第\s*%(\d+)\s*款':              r'Paragraph %\1',
    r'第\s*%(\d+)\s*项':              r'Item %\1',
}

JAPANESE_MAP = {
    r'第\s*%(\d+)\s*条':              r'Article %\1',
    r'第\s*%(\d+)\s*章':              r'Chapter %\1',
    r'第\s*%(\d+)\s*節':              r'Section %\1',
    r'第\s*%(\d+)\s*項':              r'Paragraph %\1',
    r'第\s*%(\d+)\s*号':              r'Item %\1',
    r'別紙\s*%(\d+)':                 r'Schedule %\1',
    r'別表\s*%(\d+)':                 r'Appended Table %\1',
}

LEXICON_ROWS = {
    ('chinese', r'第\s*%(\d+)\s*条'): 'sub-lexicons/chinese-general-legal.md, the 条 row (article / section)',
    ('chinese', r'第\s*%(\d+)\s*章'): ('sub-lexicons/chinese-corporate-ma-jv.md, the Civil Code '
                                       'agency-chapter row (Chapter)'),
    ('chinese', r'第\s*%(\d+)\s*款'): 'sub-lexicons/chinese-general-legal.md, the 款 row (paragraph)',
    ('chinese', r'第\s*%(\d+)\s*项'): 'sub-lexicons/chinese-general-legal.md, the 项 row (item)',
    ('japanese', r'第\s*%(\d+)\s*条'): ('sub-lexicons/japanese-general-legal.md, the numbering-'
                                        'convention note (条 article)'),
    ('japanese', r'第\s*%(\d+)\s*章'): 'sub-lexicons/japanese-general-legal.md, the 章 row (Chapter)',
    ('japanese', r'第\s*%(\d+)\s*節'): 'sub-lexicons/japanese-general-legal.md, the 節 row (Section)',
    ('japanese', r'第\s*%(\d+)\s*項'): 'sub-lexicons/japanese-general-legal.md, the 項 row (paragraph)',
    ('japanese', r'第\s*%(\d+)\s*号'): 'sub-lexicons/japanese-general-legal.md, the 号 row (item)',
    ('japanese', r'別紙\s*%(\d+)'): ('sub-lexicons/japanese-corporate-ma-jv.md, the 開示別紙 row '
                                     '(disclosure schedules); the label follows the operator'),
    ('japanese', r'別表\s*%(\d+)'): 'sub-lexicons/japanese-general-legal.md, the 別表 row (appended table)',
}

# The nine maps the GUESS reads. Chinese and Japanese are applied when declared, never guessed:
# detect_language_from_numbering below scores Latin words, so its answers stay what they were.
_GUESSABLE_MAPS = {
    'hungarian': HUNGARIAN_MAP,
    'italian': ITALIAN_MAP,
    'german': GERMAN_MAP,
    'french': FRENCH_MAP,
    'spanish': SPANISH_MAP,
    'portuguese': PORTUGUESE_MAP,
    'dutch': DUTCH_MAP,
    'polish': POLISH_MAP,
    'finnish': FINNISH_MAP,
}

LANGUAGE_MAPS = dict(_GUESSABLE_MAPS, chinese=CHINESE_MAP, japanese=JAPANESE_MAP)

# THE KEYWORD BEFORE THE NUMBER (branch 12 slice 12b). Measured over the 13 recorded runs: of
# the 25 word-bearing format strings no map matched, 12 put the keyword BEFORE the number
# ("Capitolo %1") -- an order the maps carried only for the attachment keyword -- and on one
# Italian document such a string, in numbering the document uses, shipped untranslated while
# the run printed "Translated 2". So every keyword a map holds after the number is matched
# before it too, DERIVED here rather than typed, so a keyword added later gets both orders.
# Applied after the map's own entries, which keep their priority.
_AFTER_NUMBER = re.compile(r'%\(\\d\+\)\\\.\\s\*([^\W\d_]+)')


def full_map(language):
    """The map a run applies for `language`: its own entries, then the keyword-before-number
    order for each keyword it holds after the number. {} for a language with no map."""
    base = LANGUAGE_MAPS.get((language or '').lower(), {})
    out = dict(base)
    for pattern, replacement in base.items():
        m = _AFTER_NUMBER.fullmatch(pattern)
        if m:
            out.setdefault(r'(?<!\w)' + m.group(1) + r'\s*%(\d+)', replacement)
    return out


def detect_language_from_numbering(numbering_xml_text):
    """Try to auto-detect the source language from numbering format strings."""
    text_lower = numbering_xml_text.lower()
    scores = {}
    for lang, tmap in _GUESSABLE_MAPS.items():
        score = 0
        for pattern in tmap:
            # Convert regex pattern to a simpler search
            simple = re.sub(r'%\(\\d\+\)', '%', pattern)
            simple = re.sub(r'\\[sd.]', '.', simple)
            # Extract just the word parts
            words = re.findall(r'[a-záéíóöőúüűàèìòùâêîôûäëïöüçñãõżźćśłńęąščřžďťňůĺĽ]+', pattern)
            for word in words:
                if len(word) > 2 and word in text_lower:
                    score += 1
        if score > 0:
            scores[lang] = score
    if scores:
        return max(scores, key=scores.get)
    return None

# === ATTACHMENT LABEL FOLLOWS THE OPERATOR ===
#
# BRANCH 10 SLICE 3b. The built-in maps render an auto-numbered attachment label --
# Allegato, Annexe, Anlage, Anexo, Melléklet and the rest -- as `Schedule %N` whatever the
# operator chose. The reference lexicon's Attachments row offers "Schedule (UK) or Annex
# (EU/international)" as a FREE CHOICE, and post_process stopped overriding that choice in
# the body text in the same slice (register F29, B6). Leaving this map unconditional would
# ship an operator's "Annex 1" in the text beside a "Schedule 1" heading -- and it is not
# hypothetical: measured on the corpus, the document whose Annex rewrite B6 records
# auto-numbers its attachments through two paragraph styles.
#
# So the label follows the operator's DECLARED English, read from the same paragraphs.json
# post_process reads: `Annex %N` where the notes label attachments Annex and never Schedule;
# `Schedule %N` otherwise, which is today's behaviour and the lexicon's UK-first rendering.
# A MIX is reported and keeps Schedule; so is having no notes. An operator's own --custom map
# is applied after this and still wins.
#
# THIS BLOCK NEVER EXITS AND NEVER RAISES: a label choice is never a reason to stop a run. The
# script as a whole stops on one thing only, since branch 12 slice 12b -- a word left untranslated
# in numbering the document uses, on a declared language (see WHAT THE MAPS LEFT below).
_ANNEX_LABEL_RE = re.compile(r'\bAnnex(?:es)?\s+(?:\d+|[IVXLC]+\b|[A-Z]\b)')
_SCHEDULE_LABEL_RE = re.compile(r'\bSchedules?\s+(?:\d+|[IVXLC]+\b|[A-Z]\b)')
# A legislation reference is not a label choice. The SAME keywords as post_process's
# ANNEX_EXCLUDE, so the two scripts agree on what counts; tests/test_lexicon_choice.py
# asserts the two lists are equal.
_LABEL_EXCLUDE = ('Regulation', 'Directive', 'Law', 'Decree', 'Regolamento')


def _autodetect_paragraphs_json(output_xml):
    """<workdir>/final/word/numbering.xml -> <workdir>/paragraphs.json, the layout
    skill-docs/08 gives for Step 8a. None when that file is not there."""
    try:
        workdir = os.path.dirname(os.path.dirname(os.path.dirname(
            os.path.abspath(output_xml))))
        candidate = os.path.join(workdir, 'paragraphs.json')
        return candidate if os.path.isfile(candidate) else None
    except (OSError, ValueError):
        return None


def declared_attachment_label(paragraphs_json_path):
    """('Annex' | 'Schedule' | None, why) from the operator's declared English.

    None means "keep today's default"; `why` says which of the four cases it was, so the
    run can print it rather than leave the operator to infer it."""
    if not paragraphs_json_path or not os.path.isfile(paragraphs_json_path):
        return None, 'no notes'
    try:
        with open(paragraphs_json_path, 'r', encoding='utf-8') as f:
            entries = json.load(f)
    except (OSError, ValueError):
        return None, 'notes unreadable'
    if not isinstance(entries, list):
        return None, 'notes unreadable'
    annex = schedule = 0
    for e in entries:
        en = e.get('en') if isinstance(e, dict) else None
        if not isinstance(en, str) or not en:
            continue
        if any(kw in en for kw in _LABEL_EXCLUDE):
            continue
        annex += len(_ANNEX_LABEL_RE.findall(en))
        schedule += len(_SCHEDULE_LABEL_RE.findall(en))
    if annex and not schedule:
        return 'Annex', f'{annex} Annex label(s) declared and no Schedule label'
    if schedule and not annex:
        return 'Schedule', f'{schedule} Schedule label(s) declared and no Annex label'
    if annex and schedule:
        return None, (f'MIXED — {annex} Annex and {schedule} Schedule label(s) declared; '
                      f'the default is kept, and the text should use one of the two')
    return None, 'no attachment label declared'


def _follow_label(tmap, label):
    """The map with every replacement that begins `Schedule` rendered as `label` instead."""
    if label != 'Annex':
        return dict(tmap)
    return {k: (('Annex' + v[len('Schedule'):]) if v.startswith('Schedule') else v)
            for k, v in tmap.items()}
# === ATTACHMENT LABEL FOLLOWS THE OPERATOR ENDS ===


# === WHAT THE MAPS LEFT, AND THE STOP ===
#
# BRANCH 12 SLICE 12b, register S3: this script reported the absence of DICTIONARY MATCHES as
# the absence of CONTENT. On a Norwegian document it guessed french, matched nothing, and said
# "No translatable format strings found (all pure numeric/symbol patterns)" while ten format
# strings carrying words sat in numbering the document uses -- and the strings ship inside the
# delivered file, where no later gate reads them: a format string is an attribute, and
# numbering.xml is not a prose part repack's remnant block scans.
#
# So after the maps every format string still carrying a WORD is listed, marked by whether
# numbering the document uses holds it. A one-letter bullet ('o') is a glyph, not a word, and a
# string of English numbering words alone (Article, Section) has nothing to translate.
#
# AND IT STOPS (Wouter, 2026-10-12) only where it can tell: the language was DECLARED at
# Step 1c, or given with --language, and is one this skill supports, and the string is in
# numbering the document uses. On a guess, or on a language with no map, a word left may be
# English already, so it is listed and the run goes on.
_EN_NUMBERING_WORDS = frozenset((
    'schedule schedules annex annexes annexure appendix appendices article articles clause '
    'clauses section sections part parts chapter chapters exhibit exhibits recital recitals '
    'attachment attachments art sec no para paragraph paragraphs item items step page sub rule '
    'rules title book volume tranche lot table appended figure point').split())
_WORD = re.compile(r'[^\W\d_]+')
_NUM_ID = re.compile(r'<w:numId\s[^>]*?w:val="(\d+)"')
_LVLTEXT = re.compile(r'(<w:lvlText\s+w:val=")([^"]*?)(")')


def _carries_word(val):
    """Two or more letters once the %N placeholders are gone, and a word that is not English
    numbering vocabulary."""
    words = _WORD.findall(re.sub(r'%\d', '', val))
    if len(''.join(words)) < 2:
        return False
    return not all(w.lower() in _EN_NUMBERING_WORDS for w in words)


def _values_in_use(orig_docx, numbering_bytes):
    """{format string: True when numbering the document uses holds it}, or None when the
    numbering part cannot be read as XML. A numId the body or a style cites marks its num -- and
    the abstractNum behind it -- as used. READ only: this script never writes through ElementTree."""
    with zipfile.ZipFile(orig_docx, 'r') as zf:
        cited = set()
        for part in ('word/document.xml', 'word/styles.xml'):
            if part in zf.namelist():
                cited.update(_NUM_ID.findall(zf.read(part).decode('utf-8', errors='ignore')))
    cited.discard('0')
    try:
        root = ET.fromstring(numbering_bytes)
    except ET.ParseError:
        return None
    used_abstract = set()
    for num in root.iter(f'{W}num'):
        abstract = num.find(f'{W}abstractNumId')
        if num.get(f'{W}numId') in cited and abstract is not None:
            used_abstract.add(abstract.get(f'{W}val'))
    out = {}
    owners = ([(an, an.get(f'{W}abstractNumId') in used_abstract) for an in root.iter(f'{W}abstractNum')]
              + [(num, num.get(f'{W}numId') in cited) for num in root.iter(f'{W}num')])
    for owner, used in owners:
        for lt in owner.iter(f'{W}lvlText'):
            val = lt.get(f'{W}val') or ''
            out[val] = out.get(val, False) or used
    return out


def _translate_value(val, tmap, custom_map):
    """(translated, matched) for a format string as Word shows it (unescaped): an exact --custom
    entry first, as the operator wrote it; then the first map entry that matches. A --custom key
    is also tried as a pattern, as it always was -- but a key that is no valid pattern, a literal
    string with a bracket in it, is skipped there rather than ending the run."""
    if custom_map and val in custom_map:
        return custom_map[val], True
    for pattern, replacement in tmap.items():
        try:
            new_val, n = re.subn(pattern, replacement, val, flags=re.IGNORECASE)
        except re.error:
            continue
        if n > 0:
            return new_val, True
    return val, False


def _attr(text):
    """A format string escaped for the w:val attribute it is written back into."""
    return xml_escape(text, {'"': '&quot;'})
# === WHAT THE MAPS LEFT, AND THE STOP ENDS ===


def _layout_workdir(output_xml):
    """<workdir> when output_xml is <workdir>/final/word/numbering.xml, Step 8a's layout; else
    None -- never a folder that merely happens to sit three levels up."""
    word = os.path.dirname(os.path.abspath(output_xml))
    final = os.path.dirname(word)
    if os.path.basename(word) == 'word' and os.path.basename(final) == 'final':
        return os.path.dirname(final)
    return None


def translate_numbering(orig_docx, output_xml, language=None, custom_map=None,
                        paragraphs_json=None):
    """Extract, translate, and write word/numbering.xml. Returns True when the run must STOP
    (see WHAT THE MAPS LEFT above), False otherwise."""

    # Read numbering.xml from the .docx
    with zipfile.ZipFile(orig_docx, 'r') as zf:
        if 'word/numbering.xml' not in zf.namelist():
            print("No word/numbering.xml found in this .docx — nothing to translate.")
            return False
        numbering_bytes = zf.read('word/numbering.xml')

    numbering_text = numbering_bytes.decode('utf-8')

    # The language: --language, else the Step 1c declaration, else a guess that is acted on
    # but never settles anything -- source_language_markers' one policy.
    resolved = resolve_source_language(
        paragraphs_json or _layout_workdir(output_xml), explicit=language,
        guess=lambda: detect_language_from_numbering(numbering_text))
    if resolved.warning:
        print(f"WARNING — {resolved.warning}")
    language = resolved.language
    settled = resolved.cannot_rule is None
    if not settled:
        has_map = (language or '').lower() in LANGUAGE_MAPS
        print(not_supported("the numbering translation", resolved.cannot_rule)
              + (" Its map is applied, and nothing it leaves stops the run." if has_map
                 else " No built-in map is applied, and nothing it leaves stops the run."))

    # Build translation map
    tmap = full_map(language)
    # The attachment label follows the operator (see the block above) -- BEFORE the custom
    # map, so an explicit --custom entry for the same pattern still wins.
    if any(v.startswith('Schedule') for v in tmap.values()):
        label, why = declared_attachment_label(
            paragraphs_json or _autodetect_paragraphs_json(output_xml))
        tmap = _follow_label(tmap, label)
        print(f"Attachment label: {label or 'Schedule'} — {why}")
    if custom_map:
        tmap.update(custom_map)

    # Find and translate w:lvlText val attributes
    # These look like: <w:lvlText w:val="%1. sz. Melléklet"/>
    changes = 0
    left = []

    def replace_lvltext(match):
        nonlocal changes
        prefix = match.group(1)   # everything before the val content
        # The format string as Word shows it: matched, listed and compared UNESCAPED, so a
        # --custom key the operator copies from the list matches, and written back ESCAPED, so
        # a rendering holding & or " still makes a valid attribute.
        val = html.unescape(match.group(2))
        suffix = match.group(3)   # closing quote + rest

        translated, matched = _translate_value(val, tmap, custom_map)
        if not matched and _carries_word(val):
            left.append(val)

        if translated != val:
            changes += 1
            print(f"  Translated: '{val}' → '{translated}'")
            return f'{prefix}{_attr(translated)}{suffix}'
        return match.group(0)

    # Match w:lvlText elements with their val attribute
    numbering_text = _LVLTEXT.sub(replace_lvltext, numbering_text)

    # Also check for any other translatable text in w:t elements within numbering.xml
    # (some documents embed text directly in numbering definitions)

    os.makedirs(os.path.dirname(output_xml) or '.', exist_ok=True)
    with open(output_xml, 'w', encoding='utf-8') as f:
        f.write(numbering_text)

    if changes:
        print(f"\nTranslated {changes} numbering format string(s).")
    if not left:
        if not changes:
            print("\nNo translatable format strings found (all pure numeric/symbol patterns).")
        return False

    in_use = _values_in_use(orig_docx, numbering_bytes)
    if in_use is None:
        print("\nThe numbering part could not be read as XML, so which numbering the document uses "
              "is unknown: every string below is treated as in use.")
        rows = [(val, True) for val in dict.fromkeys(left)]
    else:
        rows = [(val, in_use.get(val, False)) for val in dict.fromkeys(left)]
    used = sum(1 for _v, u in rows if u)
    print(f"\nNOT TRANSLATED — {len(rows)} numbering format string(s) still carry words no map "
          f"translated ({used} in numbering the document uses):")
    for val, u in rows:
        print(f"  [{'in use' if u else 'not in use'}] '{val}'")
    print('  Render each with --custom <file.json> ({"<format string>": "<English>"}); a string '
          'that is right as it stands is kept by mapping it to itself.')
    if settled and used:
        print(f"\nSKILL GATE FIRED — INTENTIONAL BLOCK, NOT A SCRIPT ERROR. {used} format string(s) in "
              f"numbering the document uses still carry {language} words, so the delivered document "
              "would number its headings in the source language. numbering.xml was written with "
              "every other translation applied; render them with --custom and re-run Step 8a.")
        return True
    return False

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Translate numbering format strings in word/numbering.xml')
    parser.add_argument('original', help='Original .docx file')
    parser.add_argument('output', help='Output numbering.xml path')
    parser.add_argument('--language', help=('Source language, overriding the one declared at Step 1c '
                                            '(chinese, dutch, finnish, french, german, hungarian, '
                                            'italian, japanese, polish, portuguese, spanish)'),
                        default=None)
    parser.add_argument('--custom', help='JSON file with custom translations', default=None)
    parser.add_argument('--paragraphs', dest='paragraphs_json', default=None,
                        help=('paragraphs.json whose declared English decides the attachment '
                              'label (Annex or Schedule). When omitted, found by the Step 8a '
                              'layout: <workdir>/paragraphs.json beside final/.'))
    args = parser.parse_args()

    custom = None
    if args.custom:
        # utf-8, never the platform's code page: --custom is the way out of the stop above, and
        # a format string to render is rarely ASCII.
        with open(args.custom, encoding='utf-8-sig') as f:
            custom = json.load(f)

    stop = translate_numbering(args.original, args.output, language=args.language,
                               custom_map=custom, paragraphs_json=args.paragraphs_json)
    sys.exit(1 if stop else 0)

# === SKILL FILE COMPLETE ===
