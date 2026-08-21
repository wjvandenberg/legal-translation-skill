"""Repack a translated document.xml back into the original .docx.

Uses Python's zipfile to copy the original ZIP structure byte-for-byte,
replacing only word/document.xml (and optionally word/numbering.xml,
word/settings.xml, word/headerN.xml, word/footerN.xml). This avoids
the case-sensitivity and directory-entry issues that arise when using
shell unzip + zip, which can produce files that Word on Windows refuses
to open.

Post-repack scan
----------------
After writing the final .docx, the script re-opens it and runs
``source_language_markers.scan_remnants`` over every XML part. The source
language is auto-detected from the ORIGINAL .docx's word/document.xml.
Any source-language remnants surviving in the delivered .docx are
printed as WARNING lines with their XML-file location so the operator
can decide whether to re-run translation on the affected part. The scan
is additive — the repack still exits 0 regardless of hits.

Exit codes:
  0 — the .docx was written to the delivery path
  1 — a gate blocked; NOTHING was written to the delivery path. Either a
      mandatory pre-bundle validator failed, or --paragraphs was not supplied
      so one could not run, or the finished archive failed its own ZIP
      integrity or case-conflict check and was deleted.
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
_SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)
try:
    from source_language_markers import detect_language as _detect_lang
    from source_language_markers import scan_remnants as _scan_remnants
except Exception:  # pragma: no cover — scan is best-effort.
    _detect_lang = None
    _scan_remnants = None
try:
    from lexicon_compliance import _guess_language as _guess_lang
except Exception:  # pragma: no cover — the agreement control is best-effort.
    _guess_lang = None

_TAG_STRIP_RE = re.compile(r'<[^>]+>')


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
           clean_track_revisions=True,
           paragraphs_json=None):
    """Copy orig_docx to output_docx, replacing word/document.xml and any
    optionally-supplied auxiliary XML parts (numbering, headers/footers,
    comments, footnotes, endnotes).

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
                "would only surface via the post-repack remnant scan.",
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
                    zout.writestr(new_item, new_doc_xml)

                elif norm_filename == 'word/numbering.xml' and new_numbering_xml:
                    zout.writestr(new_item, new_numbering_xml)

                elif norm_filename in hf_replacements:
                    zout.writestr(new_item, hf_replacements[norm_filename])

                elif norm_filename in aux_replacements:
                    zout.writestr(new_item, aux_replacements[norm_filename])

                elif norm_filename == 'word/settings.xml' and clean_track_revisions:
                    content = zin.read(item.filename).decode('utf-8')
                    content = re.sub(r'<w:trackRevisions[^/]*/>', '', content)
                    content = re.sub(r'<w:trackRevisions[^>]*>[^<]*</w:trackRevisions>', '', content)
                    zout.writestr(new_item, content.encode('utf-8'))

                elif item.filename in rels_fixups:
                    zout.writestr(new_item, rels_fixups[item.filename])

                else:
                    data = zin.read(item.filename)
                    zout.writestr(new_item, data)

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

    shutil.move(tmp_docx, output_docx)
    print(f"Repacked: {output_docx}")

    # --- Post-repack source-language remnant scan ---
    # Re-open the delivered .docx and scan every XML part for source-language
    # remnants using the same marker lists the apply step already uses. This
    # catches untranslated parts (comments.xml, footnotes.xml, headerN.xml,
    # text boxes inside document.xml, etc.) that would otherwise ship silently.
    #
    # Source language is auto-detected from the ORIGINAL .docx's
    # word/document.xml. If detection fails (too little body text, unsupported
    # language, or source_language_markers not importable), the scan is
    # skipped silently — the repack itself is not affected.
    if _detect_lang is not None and _scan_remnants is not None:
        # ONE PLACE READS THE ORIGINAL'S BODY TEXT. This block used to carry its
        # own copy of the zip-read and the tag strip, which is how the pre-repack
        # gate came to be missing a language the post-repack scan already had
        # (register C9): the capability existed eight lines away and was not
        # reachable. `_original_body_text` is now that one place.
        try:
            src_lang = _detect_lang(_original_body_text(orig_docx))
        except Exception:
            src_lang = None

        if src_lang:
            print(
                f"  Post-repack remnant scan: language={src_lang}, "
                "scanning every XML part in the delivered .docx..."
            )
            total_hits = 0
            per_part_hits = []
            with zipfile.ZipFile(output_docx) as zout_check:
                xml_parts = [
                    n for n in zout_check.namelist()
                    if n.lower().endswith('.xml')
                    and (n.startswith('word/') or n == 'word/document.xml')
                ]
                # Narrow to the parts that actually carry user-visible prose.
                # Settings/styles/fontTable/theme etc. are structural and can
                # contain source-language strings that are never shown.
                _PROSE_PARTS = {
                    'word/document.xml',
                    'word/comments.xml',
                    'word/footnotes.xml',
                    'word/endnotes.xml',
                }
                for part_name in xml_parts:
                    # Include headerN.xml, footerN.xml, and the fixed list above.
                    base = os.path.basename(part_name)
                    is_header_footer = (
                        base.startswith('header') and base.endswith('.xml')
                    ) or (
                        base.startswith('footer') and base.endswith('.xml')
                    )
                    if part_name not in _PROSE_PARTS and not is_header_footer:
                        continue
                    try:
                        part_bytes = zout_check.read(part_name)
                        part_text = part_bytes.decode('utf-8', errors='ignore')
                    except Exception:
                        continue
                    # Strip XML tags so we scan only the text that the reader sees,
                    # not attribute names / rsid values / style IDs.
                    text_only = _TAG_STRIP_RE.sub(' ', part_text)
                    hits = _scan_remnants(text_only, src_lang)
                    if hits:
                        per_part_hits.append((part_name, hits))
                        total_hits += len(hits)

            if total_hits:
                print(
                    f"  WARNING: post-repack scan found {total_hits} "
                    f"{src_lang} remnant(s) in the delivered .docx:"
                )
                for part_name, hits in per_part_hits:
                    print(f"    {part_name}: {len(hits)} hit(s)")
                    for pat, ctx in hits[:5]:
                        snippet = ' '.join(ctx.split())[:120]
                        print(f"      {pat}: ...{snippet}...")
                    if len(hits) > 5:
                        print(f"      ... {len(hits) - 5} more (suppressed)")
                print(
                    "           Some hits may be verbatim-preserved content "
                    "(project names, entity names, reference codes) — review\n"
                    "           before delivering. Hits inside comments.xml, "
                    "footnotes.xml, or headerN.xml typically indicate the\n"
                    "           corresponding auxiliary part was not wired "
                    "into this repack. Re-run with the right flag."
                )
            else:
                print(
                    f"  Post-repack scan clean: no {src_lang} remnants "
                    "detected in the delivered .docx's prose parts."
                )
        else:
            print(
                "  Post-repack scan skipped: source language could not be "
                "auto-detected from the original .docx."
            )

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
