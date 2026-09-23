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
"""
import sys
import os
import re
import json
import zipfile
import xml.etree.ElementTree as ET

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

LANGUAGE_MAPS = {
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

def detect_language_from_numbering(numbering_xml_text):
    """Try to auto-detect the source language from numbering format strings."""
    text_lower = numbering_xml_text.lower()
    scores = {}
    for lang, tmap in LANGUAGE_MAPS.items():
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
# IT NEVER EXITS AND NEVER RAISES, and that is load-bearing: this is one of the two scripts
# in the skill that cannot block a run, and tools/audit_branches.py asserts it (B1.mute).
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


def translate_numbering(orig_docx, output_xml, language=None, custom_map=None,
                        paragraphs_json=None):
    """Extract, translate, and write word/numbering.xml."""

    # Read numbering.xml from the .docx
    with zipfile.ZipFile(orig_docx, 'r') as zf:
        if 'word/numbering.xml' not in zf.namelist():
            print("No word/numbering.xml found in this .docx — nothing to translate.")
            return False
        numbering_bytes = zf.read('word/numbering.xml')

    numbering_text = numbering_bytes.decode('utf-8')

    # Auto-detect language if not specified
    if language is None:
        language = detect_language_from_numbering(numbering_text)
        if language:
            print(f"Auto-detected numbering language: {language}")
        else:
            print("Could not auto-detect numbering language. No translations applied.")
            if not custom_map:
                # Write unchanged
                with open(output_xml, 'w', encoding='utf-8') as f:
                    f.write(numbering_text)
                return False

    # Build translation map
    tmap = {}
    if language and language.lower() in LANGUAGE_MAPS:
        tmap.update(LANGUAGE_MAPS[language.lower()])
    # The attachment label follows the operator (see the block above) -- BEFORE the custom
    # map, so an explicit --custom entry for the same pattern still wins.
    if any(v.startswith('Schedule') for v in tmap.values()):
        label, why = declared_attachment_label(
            paragraphs_json or _autodetect_paragraphs_json(output_xml))
        tmap = _follow_label(tmap, label)
        print(f"Attachment label: {label or 'Schedule'} — {why}")
    if custom_map:
        tmap.update(custom_map)

    if not tmap:
        print(f"No translation map for language '{language}'. Writing unchanged.")
        with open(output_xml, 'w', encoding='utf-8') as f:
            f.write(numbering_text)
        return False

    # Find and translate w:lvlText val attributes
    # These look like: <w:lvlText w:val="%1. sz. Melléklet"/>
    changes = 0

    def replace_lvltext(match):
        nonlocal changes
        prefix = match.group(1)   # everything before the val content
        val = match.group(2)      # the format string
        suffix = match.group(3)   # closing quote + rest

        translated = val
        for pattern, replacement in tmap.items():
            new_val, n = re.subn(pattern, replacement, translated, flags=re.IGNORECASE)
            if n > 0:
                translated = new_val
                break

        if translated != val:
            changes += 1
            print(f"  Translated: '{val}' → '{translated}'")
            return f'{prefix}{translated}{suffix}'
        return match.group(0)

    # Match w:lvlText elements with their val attribute
    numbering_text = re.sub(
        r'(<w:lvlText\s+w:val=")([^"]*?)(")',
        replace_lvltext,
        numbering_text
    )

    # Also check for any other translatable text in w:t elements within numbering.xml
    # (some documents embed text directly in numbering definitions)

    os.makedirs(os.path.dirname(output_xml) or '.', exist_ok=True)
    with open(output_xml, 'w', encoding='utf-8') as f:
        f.write(numbering_text)

    if changes:
        print(f"\nTranslated {changes} numbering format string(s).")
    else:
        print("\nNo translatable format strings found (all pure numeric/symbol patterns).")

    return changes > 0

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Translate numbering format strings in word/numbering.xml')
    parser.add_argument('original', help='Original .docx file')
    parser.add_argument('output', help='Output numbering.xml path')
    parser.add_argument('--language', help='Source language (hungarian, italian, german, french, spanish, portuguese, dutch, polish, finnish)', default=None)
    parser.add_argument('--custom', help='JSON file with custom translations', default=None)
    parser.add_argument('--paragraphs', dest='paragraphs_json', default=None,
                        help=('paragraphs.json whose declared English decides the attachment '
                              'label (Annex or Schedule). When omitted, found by the Step 8a '
                              'layout: <workdir>/paragraphs.json beside final/.'))
    args = parser.parse_args()

    custom = None
    if args.custom:
        with open(args.custom) as f:
            custom = json.load(f)

    translate_numbering(args.original, args.output, language=args.language, custom_map=custom,
                        paragraphs_json=args.paragraphs_json)

# === SKILL FILE COMPLETE ===
