"""Validate translation completeness before applying to the document.

Checks character ratios between source and target for every paragraph of
MIN_IT_LENGTH characters or more. Flags paragraphs where the English
translation is suspiciously short relative to the source — a strong
indicator of truncated translation. The thresholds are scaled by the
source language declared at Step 1c (EXPECTED_RATIO), and on a source
declared English the ratio cannot rule and says NOT APPLICABLE — never
PASS (branch 12 slice 12c, registers H2 and H4).

Also enforces the per-batch translation cap. The skill's Step 4
mandates ≤35 paragraphs per batch with this script run between
batches; bulk translation of more than 35 paragraphs in one go has
been the recurring "operator deviates from skill when task feels
laborious" failure mode. The state file ``<workdir>/.validate-state.json``
tracks which paragraphs have already been validated; on each
invocation, only paragraphs newly translated since the last
validation are checked against the per-batch cap. To override (e.g.,
bulk re-validation after a regex fix that touches all paragraphs),
pass ``--accept-large-batch``.

And it refuses a Step 3b scaffold placeholder (``<<TRANSLATE: …>>``) still
in any paragraph's ``en``, or in an ``en_segments`` entry of a paragraph that
has ``en``: apply writes whatever it finds, so a placeholder left in place
ships as literal text. A paragraph not yet translated keeps its scaffold —
apply skips it, and a later batch fills it.

Usage:
    python validate_translations.py <paragraphs.json> [--accept-large-batch]

Exit codes:
    0 — PASS (all ratios acceptable)
    1 — WARN (some paragraphs flagged but none critical)
    2 — BLOCK (critically short translations, per-batch cap exceeded, OR a
        scaffold placeholder left in place)
"""
import os
import re
import sys
import json
import datetime

def _check_self_integrity():
    """Rev27: detect install-time truncation"""
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


def _sibling_integrity_exit(name, exc):
    """A sibling module this script imports is missing or cut short: a broken install, which SKILL.md rule 6
    answers by re-installing. So the banner and the exit 3 this script prints for its OWN truncation - never a
    raw traceback and exit 1, and never a gate's costume. Only ImportError (deleted, or cut before the names it
    is asked for) and SyntaxError (cut mid-statement) arrive here: a broader class would dress a real defect as
    a broken install - and an ImportError about some OTHER module, raised inside the sibling, is that sibling's
    defect, so it is raised as it is."""
    if isinstance(exc, ImportError) and exc.name not in (None, os.path.splitext(name)[0]):
        raise exc
    bar = "=" * 60
    for line in ("", bar, "[skill] FILE INTEGRITY CHECK FAILED — script truncated.",
                 f"  File: {os.path.join(os.path.dirname(os.path.abspath(__file__)), name)}",
                 f"  Needed by: {os.path.basename(__file__)} ({type(exc).__name__}: {exc})",
                 "  Re-install the skill from the .skill / .zip archive.", bar, ""):
        print(line, file=sys.stderr)
    sys.exit(3)


# NO .pyc INSIDE A SHIPPED TREE (register I-18's family). This script imports its sibling by the route
# Python gives every script - its own folder first on sys.path - so the guard precedes the import here too.
sys.dont_write_bytecode = True
try:
    from source_language_markers import TARGET_LANGUAGE, read_declared_language  # noqa: E402
except (ImportError, SyntaxError) as _exc:  # deleted, or cut short: a broken install, SKILL.md rule 6
    _sibling_integrity_exit('source_language_markers.py', _exc)

# Thresholds
WARN_RATIO = 0.6       # EN/source ratio below this triggers a warning
BLOCK_RATIO = 0.3      # EN/source ratio below this blocks application
# Only check paragraphs whose source text is at least this long. It was 150, which
# left 758 of 1,291 translated paragraphs in the 13 recorded runs unexamined —
# exactly the clause headings, defined terms and labels where a lost word is
# hardest to see (register H4). At 20 the check examines 1,119 of them; under
# 20 characters are numbers and labels, where a ratio is noise.
MIN_IT_LENGTH = 20
# The English a source language USUALLY produces, per source character: both
# thresholds are multiplied by it. Measured over the recorded runs, the median
# EN/source ratio is 0.94-1.33 for every alphabetic source and 2.6-3.2 for
# Japanese, whose characters each carry more — so at an unscaled 0.6 a Japanese
# paragraph had to lose 80% of its English to warn. Chinese is written the same
# way. Any language not listed is 1.0.
EXPECTED_RATIO = {'japanese': 2.0, 'chinese': 2.0}
BATCH_CAP = 35         # Hard cap on newly-translated paragraphs per call
PLACEHOLDER = "<<TRANSLATE:"   # Step 3b's scaffold marker; never allowed to reach apply

# Rev41: quoted-phrase retention thresholds.
# Single quotes (' ' / ' '): typically wrap project names, brand names,
# place designations that are preserved verbatim in legal translation.
# Threshold 2+ words catches "Wind Farm Foo", "Compañía Acme S.A.", etc.
# Double quotes (" " / " " / « »): typically wrap defined terms (1–4 words,
# legitimately replaced by the English equivalent during translation) OR
# statute / treaty / long entity names (5+ words, usually preserved verbatim
# or kept parenthetically). Threshold 5+ words keeps short defined-term
# substitutions out of the warning stream.
QUOTE_SINGLE_MIN_WORDS = 2
QUOTE_DOUBLE_MIN_WORDS = 5

# Quote-pair definitions used by the retention check. Each entry is
# (opener, closer). For ASCII single/double quotes opener == closer; the
# regex uses non-greedy matching scoped by character-class exclusion to
# pick out the shortest enclosed text.
_QUOTE_PAIRS_SINGLE = [
    ("'", "'"),                # ASCII apostrophe (U+0027)
    ('‘', '’'),      # ' ' typographic single
]
_QUOTE_PAIRS_DOUBLE = [
    ('"', '"'),                # ASCII double (U+0022)
    ('“', '”'),      # " " typographic double
    ('«', '»'),      # « » guillemets
]

# Step 14.3, register G1: a straight apostrophe AFTER a letter never opens a
# quotation, and one BEFORE a letter never closes one. So an elision or a
# contraction (dell'articolo, l'Acquirente, don't) is never a quote mark and may
# sit inside one, and a plural possessive (the Parties' rights) may close a
# quotation but never open one. Pairing two elisions declared the text between
# them a missing quoted phrase on most long Italian, French, Spanish or Catalan
# paragraphs. A digit is not a letter: l'80% may close a quotation, not open one.
_LETTER = r'[^\W\d_]'
_APOSTROPHE_OPEN = r'(?<!' + _LETTER + r")'"
_APOSTROPHE_CLOSE = r"'(?!" + _LETTER + r')'
_APOSTROPHE_INNER = r"(?:[^']|'(?=" + _LETTER + r'))'

# Step 14.3, register G7: two shapes in which a quoted span is TRANSLATED by
# design, so its absence from the English is no sign of loss. A defined term
# in its marker — `(il "X")`, `(di seguito, il "X")`, `(the "X")`: the
# parenthesis, an optional lead-in, a definite article, the span, and the
# parenthesis closing straight after it. A lead-in must BEGIN with a marker
# phrase or adverb (di seguito, hereinafter, congiuntamente…); the generic words
# after it (to, as, defined…) may not begin one, or a cross-reference — (as
# defined in the "X") — would pass for a marker. And a title straight after a
# title verb — `recante "X"`, `entitled "X"`. The NAMING verbs (denominato,
# named, called) are deliberately not title verbs: they introduce the names
# this check exists to keep. Italian and English, the shapes measured; another
# language's marker is checked as before.
_MARKER_ADVERBS = (
    'congiuntamente', 'collettivamente', 'singolarmente', 'rispettivamente',
    'ciascuna', 'ciascuno', 'entrambe', 'entrambi', 'insieme', 'together',
    'jointly', 'collectively', 'individually', 'respectively', 'each',
)
_MARKER_LEADIN_START = (
    r'di\s+seguito', r'in\s+seguito', r'nel\s+seguito',
    r"d['’]ora\s+in\s+(?:avanti|poi|innanzi)", 'hereinafter', 'hereafter',
    'breviter',
) + _MARKER_ADVERBS
_MARKER_LEADIN_MORE = (
    'anche', 'denominato', 'denominata', 'denominati', 'denominate', 'definito',
    'definita', 'definiti', 'definite', 'indicato', 'indicata', 'indicati',
    'indicate', 'referred', 'to', 'as', 'also', 'called', 'defined',
) + _MARKER_ADVERBS
_MARKER_BEFORE = re.compile(
    r'\(\s*(?:(?:' + '|'.join(_MARKER_LEADIN_START) + r')\b(?:[\s,:]+(?:'
    + '|'.join(_MARKER_LEADIN_MORE) + r')\b)*[\s,:]*)?'
    r"(?:(?:the|il|lo|la|i|gli|le)\s+|l['’]\s*)\Z", re.IGNORECASE)
_MARKER_AFTER = re.compile(r'\s*\)')
_TITLE_BEFORE = re.compile(
    r'\b(?:recante|recanti|intitolat[oaie]|entitled|titled)\s*[:,]?\s*\Z',
    re.IGNORECASE)


def _quoted_spans(text, opener, closer):
    """Yield the match of every <opener>…<closer> pair in text; group(1) is
    the content. The character-class-excluded inner pattern makes back-to-back
    quotations match independently. The ASCII apostrophe opens only where no
    letter precedes it and closes only where no letter follows it (G1), so an
    elision may sit INSIDE a span — 'Villa dell'Orto' is read whole — and
    never pairs with another."""
    if opener == closer == "'":
        pat = (_APOSTROPHE_OPEN + '(' + _APOSTROPHE_INNER + '+)'
               + _APOSTROPHE_CLOSE)
    else:
        # Escape for regex; if opener == closer this is fine, the pattern
        # `<opener>([^<closer>]+)<closer>` matches the shortest enclosed text.
        pat = (re.escape(opener) + r'([^' + re.escape(closer) + r']+)'
               + re.escape(closer))
    return re.finditer(pat, text)


def _quoted_span_count(s):
    """How many quoted spans of any style and length s holds."""
    return sum(1 for o, c in _QUOTE_PAIRS_SINGLE + _QUOTE_PAIRS_DOUBLE
               for _ in _quoted_spans(s, o, c))


def _translated_by_design(text, m):
    """True where span m sits in a defined-term marker or follows a title verb
    (G7) — see _MARKER_BEFORE and _TITLE_BEFORE. A marker opens at the last
    parenthesis before the span, so the search starts there."""
    k = text.rfind('(', 0, m.start())
    return bool((k >= 0 and _MARKER_BEFORE.match(text, k, m.start())
                 and _MARKER_AFTER.match(text, m.end()))
                or _TITLE_BEFORE.search(text, 0, m.start()))


def _check_quoted_phrase_retention(p):
    """Return list of (style, phrase) for source-quoted phrases that do
    NOT appear in the English translation.

    Rationale: in legal translation, quoted multi-word phrases are
    nearly always preserved verbatim — project names, brand names,
    place designations, statute names, treaty names. A quoted phrase
    in the source `text` that has no matching substring in `en` is a
    HIGH-suspicion missing-content defect (typical case: a quoted
    project name silently dropped from the English).

    Style-aware thresholds (see QUOTE_SINGLE_MIN_WORDS /
    QUOTE_DOUBLE_MIN_WORDS rationale above). Returns:
      [('single', phrase), ('double', phrase), ...]

    Skips paragraphs that are themselves a definition body — detected
    by the `… : significa / means / shall mean / has the meaning…`
    predicate immediately following the quoted term — to avoid warning
    on legitimate defined-term substitutions like
    `"Acuerdo" significa el contrato dated…` → `"Agreement" means the
    agreement dated…` where the source quoted term gets replaced.

    Step 14.3: an elision apostrophe is never a quote mark (G1), and a span in
    a defined-term marker or after a title verb is exempt (G7) — but ONLY while
    the English keeps at least as many quoted spans as the source. A term or a
    title dropped together with its quotes is a real loss, and it is checked
    exactly as before.
    """
    text = (p.get('text') or '').strip()
    en = (p.get('en') or '').strip()
    if not text or not en:
        return []

    # Skip: paragraph is a textbook definition body. Heuristic — text
    # begins with a quoted term (any style) immediately followed by a
    # definitional predicate within the next ~8 chars.
    def_predicates = (
        'significa', 'shall mean', 'means', 'has the meaning',
        'indica', 'signifies', 'indicates', 'tiene el significado',
        'le sens',  # French
        'bedeutet',  # German
        'oznacza',  # Polish
    )
    head = text[:100].lower()
    if any(pred in head for pred in def_predicates):
        # Likely a definition entry — substitution is expected.
        # Run the check anyway for the *trailing* phrases (which may
        # be project/place names inside a definition) but skip the
        # leading quoted defined term.
        # Implementation: extract the leading quoted term and remove
        # it from the candidate set.
        # (`text` is stripped, so a leading span starts at 0.)
        leading_quoted = None
        for opener, closer in _QUOTE_PAIRS_SINGLE + _QUOTE_PAIRS_DOUBLE:
            m = next(_quoted_spans(text, opener, closer), None)
            if m is not None and m.start() == 0:
                leading_quoted = m.group(1)
                break
    else:
        leading_quoted = None

    findings = []
    keeps_quotes = None   # G7's condition, counted once and only if needed
    for style, pairs, min_words in (
            ('single', _QUOTE_PAIRS_SINGLE, QUOTE_SINGLE_MIN_WORDS),
            ('double', _QUOTE_PAIRS_DOUBLE, QUOTE_DOUBLE_MIN_WORDS)):
        for opener, closer in pairs:
            for m in _quoted_spans(text, opener, closer):
                phrase_stripped = m.group(1).strip()
                if leading_quoted is not None and phrase_stripped == leading_quoted:
                    continue
                if len(phrase_stripped.split()) < min_words:
                    continue
                if phrase_stripped in en:
                    continue
                if _translated_by_design(text, m):
                    if keeps_quotes is None:
                        keeps_quotes = (_quoted_span_count(en)
                                        >= _quoted_span_count(text))
                    if keeps_quotes:
                        continue
                findings.append((style, phrase_stripped))
    return findings

def _state_path(json_path):
    """State file lives next to paragraphs.json as
    ``.validate-state.json`` so it sits in the same workdir."""
    return os.path.join(os.path.dirname(os.path.abspath(json_path)),
                        '.validate-state.json')

def _load_state(json_path):
    """Load the per-workdir validation state. Returns the default
    structure if absent."""
    sp = _state_path(json_path)
    if not os.path.isfile(sp):
        return {'validated_indices': [], 'history': []}
    try:
        with open(sp, 'r', encoding='utf-8') as f:
            state = json.load(f)
        # Migrate legacy / partial states.
        state.setdefault('validated_indices', [])
        state.setdefault('history', [])
        return state
    except (OSError, ValueError):
        return {'validated_indices': [], 'history': []}

def _save_state(json_path, state):
    sp = _state_path(json_path)
    with open(sp, 'w', encoding='utf-8') as f:
        json.dump(state, f, indent=2)

def validate(json_path, accept_large_batch=False):
    with open(json_path, 'r', encoding='utf-8') as f:
        paras = json.load(f)

    # Per-batch cap enforcement. Compare the current set of translated
    # paragraphs against the state file's record of paragraphs already
    # validated. Anything new in this invocation is "this batch".
    state = _load_state(json_path)
    already_validated = set(state.get('validated_indices', []))
    newly_translated = []
    for p in paras:
        if not (p.get('text') or '').strip():
            continue
        if not (p.get('en') or '').strip():
            continue
        idx = p.get('idx')
        if idx is None:
            continue
        if idx not in already_validated:
            newly_translated.append(idx)

    if len(newly_translated) > BATCH_CAP and not accept_large_batch:
        print(
            "\n" + "=" * 60 + "\n"
            f"[validate_translations] SKILL GATE FIRED — INTENTIONAL BLOCK,\n"
            f"NOT A SCRIPT ERROR. The script is working as designed.\n"
            + "=" * 60 + "\n"
            f"[validate_translations] BLOCK — per-batch cap exceeded.\n"
            f"\n"
            f"{len(newly_translated)} paragraphs translated since the\n"
            f"last validation; the skill's hard cap is {BATCH_CAP} per\n"
            f"batch. Translation quality degrades with larger batches\n"
            f"because per-paragraph attention drops — this is exactly\n"
            f"the failure mode the skill is structured around.\n"
            f"\n"
            f"Re-author paragraphs.json so only ≤{BATCH_CAP} paragraphs\n"
            f"have new `en` fields beyond what's already validated, run\n"
            f"validate_translations again, then continue with the next\n"
            f"batch of ≤{BATCH_CAP}.\n"
            f"\n"
            f"To override (only when re-validating after a bulk fix that\n"
            f"touches every paragraph at once), pass --accept-large-batch.\n"
            f"Doing so leaves an audit-trail entry in .validate-state.json.\n"
            + "=" * 60 + "\n",
            file=sys.stderr,
        )
        return 2

    # C30: a scaffold placeholder left in `en` or in a segment. Step 3b's
    # coalesce_fragmented_tcs.py writes `<<TRANSLATE: …>>` for the translator to
    # replace, and apply writes whatever it finds, so one left in place ships
    # as literal text. Every paragraph, whatever its source text; the state is
    # left unwritten so the re-run re-validates the same indices.
    #
    # A SEGMENT COUNTS ONLY ONCE ITS PARAGRAPH HAS `en`. Step 3b scaffolds
    # BEFORE translation and this script runs after every batch, so a paragraph
    # due in a later batch legitimately still carries its placeholders — and
    # apply skips a paragraph with no `en`, so none of its segments can reach
    # the document. Refusing it would block the first batch's validation.
    placeholders = []
    for p in paras:
        if not isinstance(p, dict):
            continue
        where = []
        if PLACEHOLDER in (p.get('en') or ''):
            where.append('en')
        segs = p.get('en_segments') if (p.get('en') or '').strip() else None
        for k, s in enumerate(segs if isinstance(segs, list) else []):
            if isinstance(s, dict) and PLACEHOLDER in (s.get('en') or ''):
                where.append(f'en_segments[{k}]')
        if where:
            placeholders.append((p.get('idx', '?'), where))
    if placeholders:
        print(
            "\n" + "=" * 60 + "\n"
            f"[validate_translations] SKILL GATE FIRED — INTENTIONAL BLOCK,\n"
            f"NOT A SCRIPT ERROR. The script is working as designed.\n"
            + "=" * 60 + "\n"
            f"[validate_translations] BLOCK — a `{PLACEHOLDER}…>>` placeholder\n"
            f"is still in paragraphs.json.\n"
            f"\n"
            f"Step 3b's scaffold writes these for you to replace with the final\n"
            f"English. Apply writes whatever it finds, so one left in place ships\n"
            f"into the document as literal text. {len(placeholders)} paragraph(s):\n"
            + "".join(f"  idx {i}: {', '.join(w)}\n" for i, w in placeholders)
            + f"\n"
            f"Replace each one as Step 4 describes, then run\n"
            f"validate_translations again.\n"
            + "=" * 60 + "\n",
            file=sys.stderr,
        )
        return 2

    # 12c: the thresholds follow the language declared at Step 1c. A source
    # declared English is the target itself, so the ratio measures nothing and
    # cannot rule (H2) — it says so rather than PASS; the batch cap, the
    # placeholder refusal and the quoted-phrase check above still run.
    language, lang_state, lang_why = read_declared_language(json_path)
    declared = lang_state in ('supported', 'unsupported')
    ratio_applies = not (declared and language == TARGET_LANGUAGE)
    scale = EXPECTED_RATIO.get(language, 1.0) if declared else 1.0
    warn_at, block_at = WARN_RATIO * scale, BLOCK_RATIO * scale

    warnings = []
    blocks = []
    missing = []
    quoted_phrase_warnings = []  # rev41: quoted-phrase retention
    total = 0
    translated = 0

    for p in paras:
        it_text = (p.get('text') or '').strip()
        en_text = (p.get('en') or '').strip()

        if not it_text:
            continue

        total += 1

        if not en_text:
            missing.append(p.get('idx', '?'))
            continue

        translated += 1

        if it_text == en_text:
            continue

        # rev41: quoted-phrase retention check. Catches missing-content
        # defects where source quoted phrases (project names, place
        # names, statute names) silently fail to appear in the English.
        # See `_check_quoted_phrase_retention` docstring for thresholds
        # and definition-paragraph skipping.
        qp_missing = _check_quoted_phrase_retention(p)
        if qp_missing:
            quoted_phrase_warnings.append({
                'idx': p.get('idx', '?'),
                'phrases': qp_missing,
                'it_preview': it_text[:120],
                'en_preview': en_text[:120],
            })

        it_len = len(it_text)
        en_len = len(en_text)

        if it_len < MIN_IT_LENGTH or not ratio_applies:
            continue

        ratio = en_len / it_len

        if ratio < block_at:
            blocks.append({
                'idx': p.get('idx', '?'),
                'ratio': ratio,
                'it_len': it_len,
                'en_len': en_len,
                'it_preview': it_text[:100],
                'en_preview': en_text[:100],
            })
        elif ratio < warn_at:
            warnings.append({
                'idx': p.get('idx', '?'),
                'ratio': ratio,
                'it_len': it_len,
                'en_len': en_len,
                'it_preview': it_text[:100],
                'en_preview': en_text[:100],
            })

    # Report
    print(f"\nTranslation Validation: {json_path}")
    print("=" * 60)
    print(f"  Total non-empty paragraphs: {total}")
    print(f"  Translated: {translated}")
    print(f"  Missing translation: {len(missing)}")
    if not ratio_applies:
        print(f"  NOT APPLICABLE — the character-ratio check cannot rule: {lang_why}.")
    elif declared:
        print(f"  Ratio check: source language {language}, declared at Step 1c; WARN below {warn_at:.2f}, BLOCK below "
              f"{block_at:.2f}, on paragraphs of {MIN_IT_LENGTH}+ characters")
    else:
        print(f"  Ratio check: {lang_why} — checked against the unscaled thresholds "
              f"(WARN below {warn_at:.2f}, BLOCK below {block_at:.2f}), on paragraphs of "
              f"{MIN_IT_LENGTH}+ characters")

    if missing:
        print(f"\n  MISSING (no 'en' field):")
        for idx in missing[:20]:
            print(f"    -> idx {idx}")
        if len(missing) > 20:
            print(f"    ... and {len(missing) - 20} more")

    if blocks:
        print(f"\n  BLOCK — Critically short translations (ratio < {block_at:.2f}):")
        print(f"  These are almost certainly truncated. Re-translate before proceeding.\n")
        for b in blocks:
            print(f"    idx {b['idx']}: ratio={b['ratio']:.2f} "
                  f"(IT={b['it_len']} chars, EN={b['en_len']} chars)")
            print(f"      IT: {b['it_preview']}...")
            print(f"      EN: {b['en_preview']}...")
            print()

    if warnings:
        print(f"\n  WARN — Possibly incomplete translations (ratio < {warn_at:.2f}):")
        print(f"  Review these paragraphs — they may be truncated.\n")
        for w in warnings:
            print(f"    idx {w['idx']}: ratio={w['ratio']:.2f} "
                  f"(IT={w['it_len']} chars, EN={w['en_len']} chars)")
            print(f"      IT: {w['it_preview']}...")
            print(f"      EN: {w['en_preview']}...")
            print()

    if quoted_phrase_warnings:
        print(f"\n  WARN — Quoted source phrases NOT found in en (rev41):")
        print(f"  These are likely project / place / statute names that")
        print(f"  should be preserved verbatim or with a parenthetical")
        print(f"  retention. Review each finding — silent omission of a")
        print(f"  quoted multi-word phrase is a known missing-content")
        print(f"  defect class. (single-quote threshold ≥{QUOTE_SINGLE_MIN_WORDS} words; "
              f"double-quote threshold ≥{QUOTE_DOUBLE_MIN_WORDS} words.)\n")
        for w in quoted_phrase_warnings:
            print(f"    idx {w['idx']}:")
            for style, phrase in w['phrases']:
                quote_label = 'single' if style == 'single' else 'double/guillemet'
                print(f"      missing ({quote_label}): {phrase!r}")
            print(f"      IT: {w['it_preview']}...")
            print(f"      EN: {w['en_preview']}...")
            print()

    # Verdict
    print("=" * 60)
    if blocks:
        print(f"  *** BLOCK: {len(blocks)} critically short translations. "
              f"Do NOT apply until re-translated. ***")
        # Don't update state on a hard block — operator must fix and
        # re-run, and the re-run should re-validate the same indices.
        return 2

    # Persist state: every paragraph in `newly_translated` is now
    # validated. Append a history entry for audit (also lets the
    # ``apply`` step gate later check that no single batch exceeded
    # the cap, even if ``--accept-large-batch`` was used).
    state['validated_indices'] = sorted(
        set(state.get('validated_indices', [])) | set(newly_translated))
    history_entry = {
        'timestamp': datetime.datetime.now(
            datetime.timezone.utc).isoformat(),
        'count': len(newly_translated),
        'indices': newly_translated,
    }
    if accept_large_batch and len(newly_translated) > BATCH_CAP:
        history_entry['accept_large_batch'] = True
    state.setdefault('history', []).append(history_entry)
    _save_state(json_path, state)

    if warnings:
        print(f"  ** WARN: {len(warnings)} possibly incomplete translations. "
              f"Review before applying. **")
        return 1
    elif quoted_phrase_warnings:
        print(f"  ** WARN: {len(quoted_phrase_warnings)} paragraph(s) with "
              f"quoted source phrases not found in en (rev41 retention check). "
              f"Review before applying. **")
        return 1
    elif missing:
        print(f"  ** WARN: {len(missing)} paragraphs without translations. **")
        return 1
    elif not ratio_applies:
        print(f"  NOT APPLICABLE: the character-ratio check could not rule on {translated} "
              f"translations — the source was declared English. Nothing else was flagged.")
    else:
        unscaled = ("" if declared else
                    " (unscaled: the Step 1c declaration cannot be read)" if lang_state == 'unreadable' else
                    " (unscaled: no source language declared at Step 1c)")
        print(f"  PASS{unscaled}: All {translated} translations have acceptable character ratios.")
        if newly_translated:
            print(f"  Batch state updated: {len(newly_translated)} new indices "
                  f"validated this call ({len(state['validated_indices'])} total).")
        return 0

if __name__ == '__main__':
    _check_self_integrity()
    import argparse
    parser = argparse.ArgumentParser(
        description='Validate translation completeness and enforce per-batch cap.')
    parser.add_argument('paragraphs_json',
                        help='Path to paragraphs.json')
    parser.add_argument('--accept-large-batch', action='store_true',
                        help=('Bypass the per-batch hard cap of 35 paragraphs. '
                              'Use only when re-validating after a bulk fix '
                              'that legitimately touches every paragraph at '
                              'once. Audit trail kept in .validate-state.json.'))
    args = parser.parse_args()
    sys.exit(validate(args.paragraphs_json,
                      accept_large_batch=args.accept_large_batch))

# === SKILL FILE COMPLETE ===
