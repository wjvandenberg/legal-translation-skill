"""Repack a translated document.xml back into the original .docx.

Uses Python's zipfile to copy the original ZIP structure byte-for-byte,
replacing only word/document.xml (and optionally word/numbering.xml,
word/settings.xml, word/headerN.xml, word/footerN.xml, word/comments.xml,
word/footnotes.xml, word/endnotes.xml, word/glossary/document.xml). This avoids
the case-sensitivity and directory-entry issues that arise when using
shell unzip + zip, which can produce files that Word on Windows refuses
to open.

The U+200B scrub and the remnant block
--------------------------------------
Every prose part (body, comments, footnotes, endnotes, glossary, headers,
footers) has every U+200B removed from its character data as it is written,
whatever the part's source: the operator's zero-width scaffolding is right
while the pipeline runs and a defect in the deliverable (register J1). The
archive is then read back BEFORE it is moved into place: a U+200B that
survived refuses delivery, and so does a positive source-language remnant in
any prose part (register C22) — the language auto-detected from the ORIGINAL's
word/document.xml, the verdict source_language_markers.remnant_verdict's.
Marker classes the scan cannot rule on only WARN; with no language detected
the block says so and does not run.

Exit codes:
  0 — the .docx was written to the delivery path
  1 — a gate blocked; NOTHING was written to the delivery path. Either a
      mandatory pre-bundle validator failed, or --paragraphs was not supplied
      so one could not run, or the ORIGINAL carries a text-bearing
      word/glossary/document.xml and --glossary was not supplied, or the
      finished archive failed its own ZIP integrity or case-conflict check,
      kept a U+200B, or carried a blocking source-language remnant, and was
      deleted.
  3 — script-integrity check failed (re-install the skill)

The archive is built under `<output>.docx.tmp` and moved into place only after
both post-write checks pass, so a failure never leaves a partial or unopenable
file where a deliverable should be.

Usage:
    python repack_docx.py <original.docx> <translated_document.xml> <output.docx> [--numbering <translated_numbering.xml>] [--headers-footers-dir <dir>] [--clean-track-revisions]
"""
import sys
import os
import re
import tempfile
import zipfile
import shutil

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



# Make scripts/ importable so we can reach source_language_markers when
# repack_docx.py is invoked from an arbitrary working directory.
# NO .pyc INSIDE A SHIPPED TREE. Python writes bytecode beside the module it imported,
# so the sibling import below would put `scripts/__pycache__/` into the operator's
# INSTALLED skill -- and the release packager zips this tree. The guard must precede the
# import: set afterwards it has already missed its moment. Register I-18's family, found
# on branch 7 slice 3 when a fifth script gained a sibling import and
# tools/precommit_gate.py check 6 caught the .pyc on that very commit. Four other
# scripts had been doing it unguarded for months, which is why the check that guards
# this is tests/test_no_bytecode_in_tree.py -- it DISCOVERS the importers by reading the
# tree, so caller N+1 is covered without anybody adding a row.
sys.dont_write_bytecode = True
_SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)
try:
    from source_language_markers import detect_language as _detect_lang
    from source_language_markers import remnant_verdict as _remnant_verdict
except Exception:  # pragma: no cover — the remnant block then REFUSES, below.
    _detect_lang = None
    _remnant_verdict = None
try:
    from lexicon_compliance import _guess_language as _guess_lang
except Exception:  # pragma: no cover — the agreement control is best-effort.
    _guess_lang = None

_TAG_STRIP_RE = re.compile(r'<[^>]+>')

# THE GLOSSARY PART, BY ITS FULL ZIP PATH AND NEVER BY A BASENAME. Register C19.
#
# `word/glossary/document.xml` and `word/document.xml` share the basename `document.xml`, so
# any inventory keyed on basenames collapses the two and a whole glossary directory vanishes
# from the listing. That is not hypothetical: it produced a written "C19 did not recur" that
# re-measuring on full paths refuted, finding six `word/glossary/` entries and the part
# untranslated. Every comparison below matches the full path.
#
# `<w:t(?:\s[^>]*)?>` and NOT `<w:t[^>]*>`: the loose form also matches `<w:tcPr>`, `<w:tbl>`
# and `<w:tab/>`. `w:delText` is included because a docPart may carry tracked changes.
_GLOSSARY_PART = 'word/glossary/document.xml'
_GLOSSARY_TEXT_RE = re.compile(
    r'<w:(?:t|delText)(?:\s[^>]*)?>([^<]*)</w:(?:t|delText)>')

# THE PROSE PARTS — one definition, read by the U+200B scrub and the remnant
# block alike. Settings, styles, fontTable, theme and the like are structural.
# The glossary by its FULL path: its basename is 'document.xml' (register C19).
_PROSE_PARTS = {'word/document.xml', 'word/comments.xml', 'word/footnotes.xml',
                'word/endnotes.xml', _GLOSSARY_PART}


def _is_prose_part(name):
    base = os.path.basename(name)
    return name.startswith('word/') and name.lower().endswith('.xml') and (
        name in _PROSE_PARTS or base.startswith('header') or base.startswith('footer'))


# THE U+200B SCRUB — register J1: "always a defect, Latin and non-Latin alike",
# and the fix "must be a PRE-REPACK SCRUB and must NOT be a prohibition on the
# device", which on two documents was the only compliant way past a script
# defect. The character has no width, so removing it moves nothing on the page.
# CHARACTER DATA ONLY: an attribute value is in no reading, and a bookmark or
# style name must still match what refers to it. Both character references count.
_ZWSP = '​'.encode('utf-8')
_ZWSP_REF_RE = re.compile(rb'&#(?:0*8203|[xX]0*200[bB]);')
_CHARDATA_RE = re.compile(rb'>([^<]+)<')


def _zwsp_count(chunk):
    return chunk.count(_ZWSP) + len(_ZWSP_REF_RE.findall(chunk))


def _scrub_zwsp(data):
    """(data with every U+200B gone from its character data, how many went)."""
    n = 0

    def one(m):
        nonlocal n
        k = _zwsp_count(m.group(1))
        if not k:
            return m.group(0)
        n += k
        return b'>' + _ZWSP_REF_RE.sub(b'', m.group(1).replace(_ZWSP, b'')) + b'<'
    return _CHARDATA_RE.sub(one, data), n


def _remnant_gate(orig_docx, tmp_docx):
    """THE REMNANT BLOCK — register C22: the one check that reads the finished
    archive with the original in hand was advisory by design. Every prose part
    of the archive ABOUT TO BE DELIVERED is scanned; a BLOCKING hit deletes it
    and refuses, an advisory one warns (the classes are source_language_markers'
    REMNANT_ADVISORY and LEXICON_KEPT_NAMES, each with its reason). The language
    comes from the ORIGINAL, C9's source of truth; making that detection SAY it
    is guessing, and reusing it for C9, are branch 12's."""
    if _detect_lang is None or _remnant_verdict is None:
        os.remove(tmp_docx)
        raise RuntimeError(
            "SKILL GATE FIRED — INTENTIONAL BLOCK, NOT A SCRIPT ERROR. "
            "source_language_markers.py could not be imported, so the remnant "
            "block cannot run. Nothing was written to the delivery path. "
            "Re-install the skill from the .skill / .zip archive.")
    try:
        src_lang = _detect_lang(_original_body_text(orig_docx))
    except Exception:
        src_lang = None
    if not src_lang:
        print("  Remnant block skipped: source language could not be "
              "auto-detected from the original .docx.")
        return
    print(f"  Remnant block: language={src_lang}, reading every prose part of "
          "the archive BEFORE it is delivered...")
    blocking, advisory = [], []
    with zipfile.ZipFile(tmp_docx) as z:
        for part in z.namelist():
            if _is_prose_part(part):
                # Tags stripped so only reader-visible text is scanned, never
                # attribute names, rsids or style ids.
                text = _TAG_STRIP_RE.sub(' ', z.read(part).decode('utf-8', errors='ignore'))
                b, a = _remnant_verdict(text, src_lang)
                blocking += [(part,) + h for h in b]
                advisory += [(part,) + h for h in a]
    for part, pat, ctx, why in advisory[:10]:
        print(f"  WARNING (ADVISORY, not blocking): {part}: {pat} — {why}: "
              f"...{' '.join(ctx.split())[:100]}...")
    if len(advisory) > 10:
        print(f"  ... {len(advisory) - 10} more advisory hit(s) (suppressed)")
    if not blocking:
        if not advisory:
            print(f"  Remnant block clean: no {src_lang} remnants in any prose part.")
        return
    os.remove(tmp_docx)
    shown = "\n".join(f"  - {part}: {pat}: ...{' '.join(ctx.split())[:100]}..."
                      for part, pat, ctx in blocking[:10])
    raise RuntimeError(
        "SKILL GATE FIRED — INTENTIONAL BLOCK, NOT A SCRIPT ERROR. SOURCE-LANGUAGE "
        f"REMNANT: {len(blocking)} {src_lang} remnant(s) in the repacked archive, "
        f"so it was DELETED instead of delivered:\n{shown}\n"
        "Nothing was written to the delivery path. Translate the text and re-run. "
        "A remnant in a part you did not pass (comments, footnotes, a header) means "
        "that part was not wired into this repack: pass its flag. If the text is "
        "faithful and the check wrongly scoped, SKILL.md rule 5a governs — never "
        "alter a faithful translation to satisfy it.")


def _glossary_text_in(orig_docx):
    """The ORIGINAL's glossary prompts: every non-whitespace <w:t>/<w:delText> string.

    Returns [] when the document carries no glossary part at all — which is 9 of the 10
    reachable corpus documents.

    WHY TEXT-BEARING AND NOT MERELY PRESENT. Word writes an empty glossary part for AutoText,
    and nothing in it can be translated, so a gate keyed on PRESENCE would fire on input
    nobody can change. That is Wouter's decision of 2026-09-08 applied one part outward — "an
    unlisted element carrying no text is left alone … a gate firing there would fire on
    correct input, which is what branch 6's first offset guard did".

    AND IT RAISES RATHER THAN RETURNING [] WHEN THE PART CANNOT BE READ. A gate that answers
    "nothing to see" when it could not look is CLAUDE.md 5.16's VOID reported as CLEAN, and
    this one guards a part that has already shipped untranslated twice.
    """
    try:
        with zipfile.ZipFile(orig_docx) as zin:
            if _GLOSSARY_PART not in zin.namelist():
                return []
            raw = zin.read(_GLOSSARY_PART).decode('utf-8', errors='ignore')
    except Exception as exc:
        raise RuntimeError(
            "SKILL GATE FIRED — INTENTIONAL BLOCK, NOT A SCRIPT ERROR. The original .docx "
            f"could not be read to check for {_GLOSSARY_PART}: {exc}. Repack aborted; no "
            ".docx written. This check is not skippable on failure: a glossary part has "
            "shipped untranslated twice, and a gate that reports 'nothing to see' when it "
            "could not look is worse than one that stops."
        ) from exc
    return [t for t in _GLOSSARY_TEXT_RE.findall(raw) if t.strip()]


def _original_body_text(orig_docx):
    """The ORIGINAL .docx's body text, tags stripped, or '' if unreadable.

    Tags are stripped BEFORE any detector sees it. Otherwise single-letter
    function-word markers (Polish `\\bw\\b`, `\\bz\\b`, `\\bi\\b`; Dutch `\\bde\\b`)
    false-match against `<w:r>`, `<w:p>` and attribute names like `w:rsidR` and
    dominate the score.
    """
    try:
        with zipfile.ZipFile(orig_docx) as zin:
            if 'word/document.xml' not in zin.namelist():
                return ''
            raw = zin.read('word/document.xml').decode('utf-8', errors='ignore')
    except Exception:
        return ''
    return _TAG_STRIP_RE.sub(' ', raw)


def _detect_source_language(orig_docx):
    """Detect the source language from the ORIGINAL, and only when two
    independent detectors agree. Returns a language name, or None.

    WHY THE ORIGINAL AND NOT THE TRANSLATION. Register C9. The pre-repack
    lexicon scan below is handed the TRANSLATED document.xml with no --language,
    so its own auto-detection reads English prose and guesses the source language
    from it. Measured over the recorded corpus: reading the translated body gets
    the source language right 2 times in 13; reading the original gets it right 9
    in 13. The detector was never the defect — its input was. The eight lines
    that already read the original for the post-repack remnant scan are the
    source of truth, and now both use them.

    WHY TWO DETECTORS AND NOT ONE, WHICH IS THE HALF THE ROW DOES NOT STATE.
    Reading the original still gets it wrong 4 times in 13, and a wrong SPECIFIC
    language is not a milder version of "unknown" — it silently SKIPS the correct
    language's rules, whereas unknown runs them all. So the answer is only used
    where two independently-written detectors agree: `source_language_markers`
    scores marker frequencies, `lexicon_compliance` matches token markers and
    counts diacritics. Measured: 9 agreements (8 of them correct) and 4 honest
    disagreements, in place of 4 confident wrong answers. On disagreement this
    returns None and the scan keeps today's behaviour, which errs towards running
    every language's rules rather than towards silence.

    Norwegian is in neither detector's vocabulary, so D03-class documents cannot
    be detected by anything and correctly reach the disagreement branch. Making
    the check SAY it is guessing is branch 12's, not this one's.
    """
    if _detect_lang is None:
        return None
    text = _original_body_text(orig_docx)
    if not text.strip():
        return None
    try:
        primary = _detect_lang(text)
    except Exception:
        return None
    if not primary:
        return None
    if _guess_lang is None:
        return None
    # The second detector reads a path, not a string, so give it the original's
    # body in a temporary .xml rather than reimplementing its marker tables here.
    second = None
    tmp_path = None
    try:
        fd, tmp_path = tempfile.mkstemp(suffix='.xml')
        with os.fdopen(fd, 'w', encoding='utf-8') as fh:
            fh.write('<w:document xmlns:w="x"><w:body><w:p><w:r><w:t>')
            fh.write(text[:200000].replace('&', ' ').replace('<', ' ').replace('>', ' '))
            fh.write('</w:t></w:r></w:p></w:body></w:document>')
        second = _guess_lang(tmp_path)
    except Exception:
        second = None
    finally:
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
    if second == primary:
        return primary
    print(
        f"  [repack] source-language detectors DISAGREE on the original "
        f"({primary} vs {second}); passing no --language to the pre-repack "
        f"lexicon scan, so it applies every language's rules rather than one "
        f"chosen wrongly."
    )
    return None


def _run_pre_repack_validator(label, args):
    """Auto-invoke a validator script as a subprocess before bundling.
    Mandatory pre-repack gate — refuses to bundle on non-zero exit."""
    import subprocess
    print(f"\n{'=' * 60}\n[repack] auto-running {label}\n{'=' * 60}")
    result = subprocess.run(args, capture_output=False)
    if result.returncode != 0:
        raise RuntimeError(
            f"{label} returned exit code {result.returncode}. Repack "
            f"aborted; no .docx written. Fix the issues above and re-run."
        )

def repack(orig_docx, translated_doc_xml, output_docx,
           translated_numbering_xml=None, headers_footers_dir=None,
           translated_comments_xml=None,
           translated_footnotes_xml=None, translated_endnotes_xml=None,
           translated_glossary_xml=None,
           clean_track_revisions=True,
           paragraphs_json=None):
    """Copy orig_docx to output_docx, replacing word/document.xml and any
    optionally-supplied auxiliary XML parts (numbering, headers/footers,
    comments, footnotes, endnotes, glossary).

    THE GLOSSARY IS THE ONE THAT BLOCKS WHEN ITS FLAG IS MISSING, and it is the only
    auxiliary part whose check reads the ORIGINAL rather than the workdir. See the gate
    below for why the trigger and the severity both differ from the other four.

    CRITICAL: every auxiliary XML passed in MUST have been produced by a
    namespace-safe translator (translate_comments.py, translate_headers_footers.py,
    translate_numbering.py). Do NOT hand this function XML that was round-tripped
    through ElementTree — it will have mangled namespace prefixes (ns1:, ns2:, etc.)
    and Word will refuse to open the .docx.

    Rev11 (final): auto-runs two MANDATORY pre-bundle validators:

    * ``lexicon_compliance.py --stage pre-repack`` on the translated
      document.xml — catches calque-drift introduced after apply by
      post_process / strip_noop / reorder_definitions.
    * ``validate_apply.py --strict`` if ``paragraphs_json`` is supplied
      — re-checks token presence in the post-modification document.xml.

    Both used to be separate operator-invoked steps (Step 8d, Step 8e);
     folds them into repack so the operator runs ONE command and
    cannot accidentally skip either gate.
    """
    scripts_dir = os.path.dirname(os.path.abspath(__file__))

    # --- PRE-REPACK MANDATORY GATES ------------------------------------
    # Run before any byte is written to output_docx so failures abort
    # cleanly without producing a half-baked .docx.
    #
    # The source language comes from the ORIGINAL, not from the translation the
    # scan is about to read. Register C9 — see _detect_source_language.
    _lex_args = [sys.executable,
                 os.path.join(scripts_dir, 'lexicon_compliance.py'),
                 translated_doc_xml,
                 '--stage', 'pre-repack']
    _src_lang_for_scan = _detect_source_language(orig_docx)
    if _src_lang_for_scan:
        print(f"  [repack] source language from the ORIGINAL: {_src_lang_for_scan} "
              "(two detectors agree) — passing it to the pre-repack lexicon scan")
        _lex_args += ['--language', _src_lang_for_scan]
    _run_pre_repack_validator(
        'lexicon_compliance.py --stage pre-repack',
        _lex_args,
    )
    if paragraphs_json:
        _run_pre_repack_validator(
            'validate_apply.py --strict (post-modification check)',
            [sys.executable,
             os.path.join(scripts_dir, 'validate_apply.py'),
             paragraphs_json,
             translated_doc_xml,
             '--strict'],
        )
    else:
        # REFUSE, rather than warn and bundle anyway.
        #
        # Three passages in the skill disagreed about whether this gate is
        # required, and the code settled it by skipping: `10-repack-and-validate.md`
        # lists this invocation among the UNCONDITIONAL mandatory items, `SKILL.md`
        # calls validate_apply "MANDATORY pre-apply AND pre-repack", and the same
        # step doc twice describes the flag as only "strongly recommended". A
        # reader could not determine whether it was mandatory — so omitting one
        # optional-looking flag silently removed a mandatory check.
        #
        # Nothing legitimate is lost by refusing. paragraphs.json is written at
        # Step 2 and is mandatory throughout the pipeline, so a repack that cannot
        # name it is a repack running outside the pipeline.
        raise RuntimeError(
            "SKILL GATE FIRED — INTENTIONAL BLOCK, NOT A SCRIPT ERROR. "
            "--paragraphs was not supplied, so the MANDATORY pre-bundle "
            "validate_apply.py --strict check cannot run. Repack aborted; no "
            ".docx written. This gate is unconditional — pass "
            "--paragraphs <workdir>/paragraphs.json and re-run. Do NOT work "
            "around it by bundling without the check: that is the path which "
            "silently ships token drift introduced after apply by "
            "post_process / strip_noop / reorder_definitions, which is the "
            "entire reason this pre-bundle re-check exists."
        )

    # --- THE GLOSSARY GATE — register C19 -------------------------------
    #
    # NOTE THE TRIGGER, BECAUSE IT IS NOT THE ONE THE OTHER AUXILIARY CHECKS USE. The warning
    # block further down fires on a file in the WORKDIR that looks translated: the operator
    # did the work and lost the flag, so the evidence is sitting in their own directory and a
    # warning has something to point at. THIS ONE FIRES ON THE ORIGINAL CARRYING THE PART,
    # because for the glossary nobody has done any work and nothing anywhere says so — on the
    # batch arm of C19's document, neither the forensic log nor the run narrative mentioned
    # the glossary once. There is no second signal to fall back on.
    #
    # AND IT BLOCKS RATHER THAN WARNS, WHICH IS A DELIBERATE DIFFERENCE FROM THOSE FOUR.
    # Measured 2026-09-09 (temp/probe_repack_refusal_shape.py, both positive controls
    # firing): numbering, comments, footnotes and endnotes each print a WARNING and BUNDLE
    # ANYWAY at exit 0. So "the pattern repack already uses" is a warn-and-bundle, and a
    # warning is precisely the control that failed here — the part shipped byte-identical and
    # untranslated with nothing objecting. Wouter was shown that measurement and confirmed
    # the block. The shape copied is the --paragraphs gate immediately above.
    #
    # THE COMPLIANT WAY OUT EXISTS AND IS ALWAYS AVAILABLE (CLAUDE.md 5.9): pass --glossary.
    # Either the part translated per Step 8e, or — if the operator judges it needs no
    # translation — the original part unchanged. The second route is not a bypass: it makes
    # the decision explicit and recorded, and the remnant block reads the part before
    # delivery, so a wrong judgement is refused rather than shipped.
    _glossary_prompts = _glossary_text_in(orig_docx)
    if _glossary_prompts and not translated_glossary_xml:
        raise RuntimeError(
            "SKILL GATE FIRED — INTENTIONAL BLOCK, NOT A SCRIPT ERROR. The ORIGINAL .docx "
            f"carries {_GLOSSARY_PART} holding {len(_glossary_prompts)} translatable "
            "string(s), and --glossary was not supplied. Repack aborted; no .docx written.\n"
            "  Every part this script is not explicitly given is copied BYTE-FOR-BYTE from "
            "the original, so bundling now would ship that part in the source language.\n"
            "  It is not dormant metadata: a glossary docPart supplies the placeholder text "
            "a content control DISPLAYS while it is empty, so the source language can appear "
            "on the page — and no remnant check in this skill used to read the part at all.\n"
            "  Translate it per Step 8e and pass --glossary "
            "<workdir>/final/word/glossary-document.xml. If you have read it and judged that "
            "it needs no translation, pass the ORIGINAL part to the same flag: that is a "
            "recorded decision rather than a silent default, and the remnant block will "
            "still refuse any source-language text left in it. Do NOT work around this gate."
        )

    with open(translated_doc_xml, 'rb') as f:
        new_doc_xml = f.read()

    # Clean empty rPr elements that Word flags as errors
    new_doc_xml = re.sub(rb'<w:rPr/>', b'', new_doc_xml)
    new_doc_xml = re.sub(rb'<w:rPr></w:rPr>', b'', new_doc_xml)

    # --- Silent-regression guard ---
    # If the directory containing the translated document.xml also holds
    # auxiliary translated parts (numbering.xml / comments.xml / headerN.xml /
    # footerN.xml / footnotes.xml / endnotes.xml) but the corresponding flag
    # was not passed, the delivered .docx will silently keep the original
    # (untranslated) part. Warn loudly so the operator can re-run.
    _doc_dir = os.path.dirname(os.path.abspath(translated_doc_xml))
    _warn_lines = []
    if _doc_dir:
        # numbering.xml
        if (not translated_numbering_xml and
                os.path.exists(os.path.join(_doc_dir, 'numbering.xml'))):
            _warn_lines.append(
                f"{os.path.join(_doc_dir, 'numbering.xml')} appears translated "
                "but --numbering was not passed."
            )
        # comments.xml
        if (not translated_comments_xml and
                os.path.exists(os.path.join(_doc_dir, 'comments.xml'))):
            _warn_lines.append(
                f"{os.path.join(_doc_dir, 'comments.xml')} appears translated "
                "but --comments was not passed."
            )
        # footnotes.xml
        if (not translated_footnotes_xml and
                os.path.exists(os.path.join(_doc_dir, 'footnotes.xml'))):
            _warn_lines.append(
                f"{os.path.join(_doc_dir, 'footnotes.xml')} appears translated "
                "but --footnotes was not passed."
            )
        # endnotes.xml
        if (not translated_endnotes_xml and
                os.path.exists(os.path.join(_doc_dir, 'endnotes.xml'))):
            _warn_lines.append(
                f"{os.path.join(_doc_dir, 'endnotes.xml')} appears translated "
                "but --endnotes was not passed."
            )
        # headerN.xml / footerN.xml — the translate_headers_footers.py script
        # writes them next to document.xml, so checking _doc_dir catches them
        # when --headers-footers-dir wasn't passed (which would have pointed at
        # the parent of _doc_dir, i.e. the 'final' folder).
        if not headers_footers_dir:
            for hf_name in ('header1', 'header2', 'header3', 'header4',
                            'footer1', 'footer2', 'footer3', 'footer4'):
                hf_path = os.path.join(_doc_dir, f'{hf_name}.xml')
                if os.path.exists(hf_path):
                    _warn_lines.append(
                        f"{hf_path} appears translated but --headers-footers-dir "
                        "was not passed."
                    )
    if _warn_lines:
        print("WARNING: auxiliary translated XML detected but not wired into repack:")
        for _w in _warn_lines:
            print(f"  - {_w}")
        print(
            "         The delivered .docx will contain the original "
            "(untranslated) part(s). Re-run with the appropriate flag(s) if "
            "that is not intentional."
        )

    new_numbering_xml = None
    if translated_numbering_xml and os.path.exists(translated_numbering_xml):
        with open(translated_numbering_xml, 'rb') as f:
            new_numbering_xml = f.read()

    # --- Optional replacements for comments / footnotes / endnotes ---
    aux_replacements = {}  # zip path -> bytes
    for zip_path, src_path in [
        ('word/comments.xml', translated_comments_xml),
        ('word/footnotes.xml', translated_footnotes_xml),
        ('word/endnotes.xml', translated_endnotes_xml),
        # THE FULL PATH IS THE KEY, and that is what makes this safe to add here. The write
        # loop below compares `norm_filename` against 'word/document.xml' FIRST; a glossary
        # part keyed by basename would have been captured by that branch and overwritten with
        # the translated BODY. Matching on the full path, the two never collide. Register C19.
        (_GLOSSARY_PART, translated_glossary_xml),
    ]:
        if src_path and os.path.exists(src_path):
            with open(src_path, 'rb') as f:
                aux_replacements[zip_path] = f.read()
            print(f"  Will replace {zip_path} with translated version")

    # --- Load translated header/footer XML files ---
    # headers_footers_dir should contain word/headerN.xml and word/footerN.xml
    # for any headers/footers that were translated. Files not present in the
    # directory will use the original from the source .docx.
    hf_replacements = {}  # normalized zip path -> bytes
    if headers_footers_dir:
        for hf_name in ['header1', 'header2', 'header3', 'header4',
                         'footer1', 'footer2', 'footer3', 'footer4']:
            hf_path = os.path.join(headers_footers_dir, 'word', f'{hf_name}.xml')
            if os.path.exists(hf_path):
                with open(hf_path, 'rb') as f:
                    hf_replacements[f'word/{hf_name}.xml'] = f.read()
                print(f"  Will replace word/{hf_name}.xml with translated version")

        # --- Loud failure if the flag was passed but nothing was found ---
        # The user's workflow is: --headers-footers-dir <dir> means "replace
        # my translated header/footer XML files into the output docx". If we
        # silently find zero files, the delivered docx keeps the original
        # (untranslated) source-language headers — exactly the defect the
        # post-repack remnant scanner had to chase down. Fail loud.
        if not hf_replacements:
            # Look for the common misconfig: user pointed at word/ instead
            # of its parent. The loop above expects <dir>/word/headerN.xml.
            # If the supplied dir is itself named 'word/' OR already contains
            # headerN.xml at its top level, the likely fix is to pass its
            # parent directory.
            likely_misconfig = False
            suggested = None
            if os.path.isdir(headers_footers_dir):
                dir_base = os.path.basename(os.path.abspath(headers_footers_dir.rstrip('/\\')))
                own_entries = set(os.listdir(headers_footers_dir))
                own_has_hf = any(
                    f'{hf}.xml' in own_entries
                    for hf in ('header1', 'header2', 'header3', 'header4',
                               'footer1', 'footer2', 'footer3', 'footer4')
                )
                if dir_base.lower() == 'word' or own_has_hf:
                    likely_misconfig = True
                    suggested = os.path.dirname(
                        os.path.abspath(headers_footers_dir.rstrip('/\\')))

            msg_lines = [
                f"--headers-footers-dir was passed but no "
                f"word/headerN.xml or word/footerN.xml files were found "
                f"under {headers_footers_dir!r}.",
                "",
                "The script expects the layout:",
                f"    {headers_footers_dir}/word/header1.xml",
                f"    {headers_footers_dir}/word/footer1.xml",
                "    ... etc",
            ]
            if likely_misconfig and suggested:
                msg_lines += [
                    "",
                    "It looks like you passed the inner word/ directory. "
                    f"Try passing its parent instead:",
                    f"    --headers-footers-dir {suggested!r}",
                ]
            msg_lines += [
                "",
                "Refusing to repack: the delivered .docx would contain the "
                "original (untranslated) headers/footers and the defect "
                "would only surface at the remnant block.",
            ]
            raise RuntimeError('\n'.join(msg_lines))

    # --- Normalize case-inconsistent paths ---
    # Some .docx files (especially from older Word versions) contain paths
    # like customXML/ alongside customXml/. Word tolerates this in its own
    # files but flags it as "unreadable content" after a Python repack.
    # We normalize all paths to the canonical lowercase form.
    CASE_NORMALIZATIONS = {
        'customxml/': 'customXml/',  # customXML/ → customXml/
    }

    def normalize_path(path):
        """Normalize known case-inconsistent directory prefixes."""
        lower = path.lower()
        for pattern, replacement in CASE_NORMALIZATIONS.items():
            if lower.startswith(pattern) and not path.startswith(replacement):
                return replacement + path[len(pattern):]
        return path

    with zipfile.ZipFile(orig_docx, 'r') as zin:
        # --- Identify orphaned customXml items (no itemProps/rels) ---
        # These are third-party metadata (e.g. iManage) that were injected
        # without proper OOXML companion files.  Rather than trying to
        # generate companions (which Word still rejects for UTF-16 items
        # and non-standard encodings), we strip them entirely — item file,
        # relationship entries, and Content_Types entries.
        all_names = set(zin.namelist())
        all_names_lower = {n.lower() for n in all_names}
        orphan_items = set()          # normalized paths to skip
        orphan_nums = set()           # item numbers that are orphaned
        item_pat = re.compile(r'^customXml/item(\d+)\.xml$', re.IGNORECASE)
        for name in all_names:
            norm = normalize_path(name)
            m = item_pat.match(norm)
            if m:
                num = m.group(1)
                props_exists = f'customxml/itemprops{num}.xml' in all_names_lower
                rels_exists = f'customxml/_rels/item{num}.xml.rels' in all_names_lower
                if not props_exists or not rels_exists:
                    orphan_items.add(norm.lower())
                    orphan_nums.add(num)
                    print(f"  Stripping orphaned customXml item{num} "
                          f"(props={props_exists}, rels={rels_exists})")

        # Also fix relationships and Content_Types that reference wrong-case paths
        rels_fixups = {}  # filename -> fixed content bytes
        for item in zin.infolist():
            if item.filename.endswith('.rels') or item.filename == '[Content_Types].xml':
                content = zin.read(item.filename).decode('utf-8')
                new_content = content
                for pattern, replacement in CASE_NORMALIZATIONS.items():
                    for variant in re.findall(r'(?<=/)(customXML|CUSTOMXML|CustomXml|CustomXML)(?=/)', new_content, re.IGNORECASE):
                        canonical = replacement.rstrip('/')
                        if variant != canonical:
                            new_content = new_content.replace('/' + variant + '/', '/' + canonical + '/')
                            new_content = new_content.replace('/' + variant + '"', '/' + canonical + '"')

                # --- Remove relationship entries for orphaned customXml items ---
                for num in orphan_nums:
                    # Remove <Relationship ... Target="...itemN.xml" .../>
                    new_content = re.sub(
                        r'<Relationship[^>]*Target="[^"]*item' + num + r'\.xml"[^/]*/>\s*',
                        '', new_content)

                # --- Fix absolute Target paths in word/_rels/document.xml.rels ---
                if item.filename.startswith('word/_rels/'):
                    new_content = re.sub(
                        r'Target="/customXml/',
                        'Target="../customXml/',
                        new_content,
                        flags=re.IGNORECASE
                    )

                # --- Fix non-standard relationship IDs ---
                if item.filename.endswith('.rels') and item.filename != '[Content_Types].xml':
                    existing_rids = set(re.findall(r'Id="(rId\d+)"', new_content))
                    max_rid = 0
                    for rid in existing_rids:
                        num_r = int(rid[3:])
                        if num_r > max_rid:
                            max_rid = num_r
                    all_ids = re.findall(r'Id="([^"]+)"', new_content)
                    for old_id in all_ids:
                        if not re.match(r'^rId\d+$', old_id):
                            max_rid += 1
                            new_id = f'rId{max_rid}'
                            new_content = new_content.replace(
                                f'Id="{old_id}"', f'Id="{new_id}"')
                            print(f"  Fixed non-standard rel Id: {old_id} → {new_id}")

                if new_content != content:
                    rels_fixups[item.filename] = new_content.encode('utf-8')

        # WRITE TO A TEMPORARY NAME, NEVER STRAIGHT TO THE DELIVERY PATH.
        # This loop used to write output_docx in place, so an exception part-way
        # through left a partial .docx exactly where a good one should be — while
        # the completion invariant in SKILL.md says a delivered file exists only if
        # all 11 steps completed, and a reader cannot tell a finished document from
        # an unfinished one by looking at it. The temp-then-move idiom is already
        # used in this tree by clean_conversion_artifacts.py; this is that pattern.
        tmp_docx = output_docx + '.tmp'
        scrubbed = {}
        with zipfile.ZipFile(tmp_docx, 'w', zipfile.ZIP_DEFLATED) as zout:
            seen_normalized = set()  # track normalized paths to skip duplicates
            for item in zin.infolist():
                if item.is_dir():
                    continue

                norm_filename = normalize_path(item.filename)
                if norm_filename != item.filename:
                    print(f"  Normalized path: {item.filename} → {norm_filename}")

                # Skip orphaned customXml items
                if norm_filename.lower() in orphan_items:
                    print(f"  Skipped orphan: {norm_filename}")
                    continue

                # Skip duplicates after normalization
                if norm_filename.lower() in seen_normalized:
                    print(f"  Skipped duplicate: {item.filename}")
                    continue
                seen_normalized.add(norm_filename.lower())

                new_item = zipfile.ZipInfo(norm_filename)
                new_item.compress_type = item.compress_type

                if norm_filename == 'word/document.xml':
                    data = new_doc_xml

                elif norm_filename == 'word/numbering.xml' and new_numbering_xml:
                    data = new_numbering_xml

                elif norm_filename in hf_replacements:
                    data = hf_replacements[norm_filename]

                elif norm_filename in aux_replacements:
                    data = aux_replacements[norm_filename]

                elif norm_filename == 'word/settings.xml' and clean_track_revisions:
                    content = zin.read(item.filename).decode('utf-8')
                    content = re.sub(r'<w:trackRevisions[^/]*/>', '', content)
                    content = re.sub(r'<w:trackRevisions[^>]*>[^<]*</w:trackRevisions>', '', content)
                    data = content.encode('utf-8')

                elif item.filename in rels_fixups:
                    data = rels_fixups[item.filename]

                else:
                    data = zin.read(item.filename)

                # THE U+200B SCRUB (J1), on every prose part whatever its source —
                # a part copied from the original carries the defect as surely.
                if _is_prose_part(norm_filename):
                    data, n_zw = _scrub_zwsp(data)
                    if n_zw:
                        scrubbed[norm_filename] = n_zw
                zout.writestr(new_item, data)
        for _part, _n in sorted(scrubbed.items()):
            print(f"  U+200B scrubbed: {_n} from {_part}")

    # --- VERIFY THE TEMPORARY FILE, AND PROMOTE IT ONLY IF BOTH CHECKS PASS ---
    #
    # BOTH CONDITIONS NOW BLOCK. Each used to print a WARNING and continue;
    # repack() returned None, and __main__ set no exit code at all — so a run that
    # produced a file Word cannot open reported success and left that file at the
    # delivery path. Together with quality_check's missing exit code that was the
    # worst delivery path in the skill: an unopenable deliverable, a failed
    # mandatory quality check, and a final audit printing "OVERALL: PASS /
    # Deliver with confidence".
    #
    # NEITHER CONDITION WAS EVER OBSERVED, and that is the argument FOR blocking
    # rather than against it: 60 archives from the twelve recorded runs were opened
    # and every one passed both checks, so a gate that never fires is
    # indistinguishable from a gate that passed. Making it block costs nothing the
    # corpus ever did and closes the one path that ships a broken file silently.
    problems = []
    with zipfile.ZipFile(tmp_docx) as z:
        bad = z.testzip()
        if bad:
            problems.append(f"ZIP integrity check failed on: {bad}")
        else:
            print(f"  ZIP OK ({len(z.namelist())} files)")

        # Check for case conflicts
        lower_map = {}
        for name in z.namelist():
            ln = name.lower()
            if ln in lower_map and lower_map[ln] != name:
                problems.append(f"case conflict: {lower_map[ln]} vs {name}")
            lower_map[ln] = name

    if problems:
        os.remove(tmp_docx)
        raise RuntimeError(
            "SKILL GATE FIRED — INTENTIONAL BLOCK, NOT A SCRIPT ERROR. "
            "The repacked archive failed its own integrity checks, so it was "
            "DELETED instead of delivered:\n  - "
            + "\n  - ".join(problems)
            + "\nNothing was written to the delivery path. A file Word cannot "
              "open is not a deliverable, and shipping one silently is worse "
              "than stopping. Re-run the repack; if it fails again, the "
              "translated document.xml or one of the auxiliary parts is "
              "malformed — fix that, do not work around this gate."
        )

    # --- READ THE ARCHIVE BACK: NO U+200B MAY SURVIVE THE SCRUB (J1) ---
    # Asserted on the archive itself, never on the scrub's own count: a count
    # proves the pattern matched, not what was written.
    with zipfile.ZipFile(tmp_docx) as z:
        survived = {n: k for n in z.namelist() if _is_prose_part(n)
                    for k in [sum(_zwsp_count(c) for c in _CHARDATA_RE.findall(z.read(n)))] if k}
    if survived:
        os.remove(tmp_docx)
        raise RuntimeError(
            "SKILL GATE FIRED — INTENTIONAL BLOCK, NOT A SCRIPT ERROR. U+200B SURVIVED "
            "THE SCRUB in " + ", ".join(f"{n} ({k})" for n, k in sorted(survived.items()))
            + ", so the archive was DELETED instead of delivered. Nothing was written "
            "to the delivery path. This is a defect in repack itself: re-install the "
            "skill from the .skill / .zip archive.")

    # --- THE REMNANT BLOCK (C22), on the archive BEFORE it is moved into place ---
    _remnant_gate(orig_docx, tmp_docx)

    shutil.move(tmp_docx, output_docx)
    print(f"Repacked: {output_docx}")

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(
        description='Repack translated document.xml (and optional auxiliary XML parts) '
                    'into a .docx')
    parser.add_argument('original', help='Original .docx file')
    parser.add_argument('translated_xml', help='Translated word/document.xml')
    parser.add_argument('output', help='Output .docx file path')
    parser.add_argument('--numbering', default=None,
                        help='Translated word/numbering.xml')
    parser.add_argument('--headers-footers-dir', default=None,
                        help='Directory containing translated word/headerN.xml '
                             'and word/footerN.xml (produced by translate_headers_footers.py)')
    parser.add_argument('--comments', default=None,
                        help='Translated word/comments.xml '
                             '(produced by translate_comments.py)')
    parser.add_argument('--footnotes', default=None,
                        help='Translated word/footnotes.xml '
                             '(produced via the regex-only approach — NOT ElementTree)')
    parser.add_argument('--endnotes', default=None,
                        help='Translated word/endnotes.xml '
                             '(produced via the regex-only approach — NOT ElementTree)')
    parser.add_argument('--glossary', default=None,
                        help='Translated word/glossary/document.xml, holding the '
                             'placeholder building blocks a content control DISPLAYS while '
                             'it is empty (Step 8e; regex-only — NOT ElementTree). The '
                             'repack REFUSES when the ORIGINAL carries a text-bearing '
                             'glossary part and this flag is absent, because every part not '
                             'named here is copied byte-for-byte from the original and the '
                             'part would ship in the source language. To keep it as it is, '
                             'pass the original part: an explicit decision, not a bypass.')
    parser.add_argument('--no-clean-track-revisions', action='store_true',
                        help='Do not remove trackRevisions from settings.xml')
    parser.add_argument('--paragraphs', default=None,
                        help='REQUIRED. Path to paragraphs.json. Enables the '
                             'auto-run of validate_apply.py --strict pre-bundle '
                             'that catches token drift introduced by post_process '
                             '/ strip_noop / reorder_definitions. The repack '
                             'REFUSES to bundle without it — the gate is '
                             'unconditional, not advisory.')
    args = parser.parse_args()
    repack(args.original, args.translated_xml, args.output,
           translated_numbering_xml=args.numbering,
           headers_footers_dir=args.headers_footers_dir,
           translated_comments_xml=args.comments,
           translated_footnotes_xml=args.footnotes,
           translated_endnotes_xml=args.endnotes,
           translated_glossary_xml=args.glossary,
           clean_track_revisions=not args.no_clean_track_revisions,
           paragraphs_json=args.paragraphs)

    # SET SUCCESS EXPLICITLY, rather than merely avoiding a failure code.
    # This block set no exit code at all, so a 0 from repack was only Python's
    # default for "the interpreter reached the end of the file" — which a script
    # that fell off the bottom having done nothing produces just as well. A caller
    # could not distinguish a completed bundle from a no-op. The gates above block
    # by raising, which exits 1; this makes the success path equally deliberate.
    sys.exit(0)

# === SKILL FILE COMPLETE ===
