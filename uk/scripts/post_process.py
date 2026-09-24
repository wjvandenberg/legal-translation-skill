"""Post-processing script for translated legal documents.

Runs all quality fixes in a single pass:
1. Spacing fixes (cross-element gaps)
2. Definition boundary fixes ("Xmeans" -> "X means")
3. Double punctuation fixes (::, .., ,,, ;;)
4. Terminology/lexicon fixes (including standalone "Financing", Italian remnants, word order)
   -- never where a lexicon in this skill sanctions the string (LEXICON_SANCTIONED)
5. UK spelling
6. Annex -> Schedule -- a DETECTOR since branch 10 slice 3b: the lexicon offers Annex as a
   free choice, so the pass reports what it finds and rewrites nothing
7. Article -> Clause for internal cross-references
8. Double-word deduplication (within and across elements)
9. Quote balancing on defined terms
10. Definition line-break removal (w:br in definition paragraphs)
11. Spurious italic removal (italic on substantive body text)
12. Schedule page breaks -- a DETECTOR since branch 10 slice 4: it reports how each
    Schedule/Annex heading starts its page and inserts nothing, so the source's pagination
    is kept

EVERY PASS ABOVE HAS A ROW IN `PASS_CONDITIONS`, BELOW THE IMPORTS -- the condition it
assumes, what it reads to test it, and what it does when it cannot tell. A pass added
without one turns tests/test_pass_conditions.py red. Read it before adding a pass.

Usage:
    python post_process.py <document.xml> [--fix] [--report-only]

Without --fix, prints a report of issues found.
With --fix, applies all fixes and saves.
"""
import json
import os
import sys
import re
from lxml import etree

# === THE PRINCIPLE EVERY PASS OBEYS — branch 10 slice 4, and read it before adding one ===
#
# THIS STAGE RUNS DOWNSTREAM OF EVERY CONTENT CHECK, so a pass that acts on a guess ships the
# guess. Branch 10 measured that eight times: the italic strip, the page breaks, Annex ->
# Schedule, Article -> Clause, the punctuation collapse, the spacing repair, the terminology
# rewrite and the empty-wrapper strip each acted on an assumption it NEVER TESTED, and each
# damaged a real document. So the rule, decision 2c revised:
#
#   1  EVERY PASS NAMES THE CONDITION IT ASSUMES AND TESTS IT, from an input it can actually
#      read -- the document, the declared notes, or a table in this file.
#   2  WHERE THE CONDITION CANNOT BE DETERMINED, THE PASS REPORTS AND CHANGES NOTHING.
#   3  A PASS LEFT WITH NOTHING TO REWRITE BECOMES A DETECTOR AND IS KEPT, NOT DELETED: what
#      it finds goes into the journal's `detections`, where the checking work can read it.
#   4  NO FLAG, NO USER QUESTION, NO OPERATOR SWITCH. A pass that declines to act is the pass
#      working; a switch to turn it off is the override flag decision 3 rejected, renamed.
#
# THE TABLE BELOW IS THE RULE MADE CHECKABLE. One row per journalled pass: STATUS, the
# condition it assumes, what it reads, and what it does when it cannot tell.
# tests/test_pass_conditions.py goes RED on a pass run by post_process() that has no row, on a
# row naming no pass, and on a status outside the four below -- so the next pass anyone adds
# arrives here or fails.
#
#   CONDITIONAL      tests the condition it assumes and acts only where it holds
#   DETECTOR         its condition is not in its input, so it reports and changes nothing
#   MECHANICAL       its condition is decidable from the document alone and is decided there
#   NOT YET TESTED   it acts on an assumption it does NOT test. DECLARED, NOT IMPLIED
#                    COMPLIANT: no register row records one of these misfiring, and none was
#                    branch 10's to fix, so each is a known gap rather than a hidden one
PASS_STATUSES = ('CONDITIONAL', 'DETECTOR', 'MECHANICAL', 'NOT YET TESTED')
PASS_CONDITIONS = {
    'spacing': (
        'CONDITIONAL',
        'two text elements whose texts would glue need a separating space',
        'document.xml: whether a RENDERED w:tab or w:br already sits between them (a w:tab '
        'inside w:pPr/w:tabs is a tab stop and does not count)',
        'decidable from the document; a seam already separated is left alone (B4)'),
    'definition_boundaries': (
        'NOT YET TESTED',
        'a capital, closing quote or bracket glued to "means", "shall mean", "has the '
        'meaning" or "indicates" is a missing space, never the source\'s own string',
        'document.xml only',
        'does not test it; no register row records a misfire'),
    'double_punctuation': (
        'DETECTOR',
        'a doubled . , ; or : is ours to collapse -- which nothing in document.xml can say',
        'document.xml, which cannot answer it',
        'reports each occurrence and changes nothing (B8)'),
    'terminology': (
        'CONDITIONAL',
        'a listed term is a calque or a variant to standardise',
        'document.xml and the LEXICON_SANCTIONED table; the declared notes only to say why '
        'a kept match was kept',
        'a match inside a lexicon-sanctioned span is left as written and reported (B5, B9)'),
    'uk_spelling': (
        'NOT YET TESTED',
        'every listed spelling is the variant\'s to change, never a proper name, a '
        'quotation or a retained source-language term',
        'the requested variant, which it does test; nothing that could tell a name apart',
        'does not test it; no register row records a misfire'),
    'us_spelling': (
        'NOT YET TESTED',
        'every listed spelling is the variant\'s to change, never a proper name, a '
        'quotation or a retained source-language term',
        'the requested variant, which it does test; nothing that could tell a name apart',
        'does not test it; no register row records a misfire'),
    'annex_to_schedule': (
        'DETECTOR',
        'Annex should read Schedule -- which the lexicon offers as a FREE choice, matched '
        'to the source',
        'document.xml, LEXICON_SANCTIONED and the declared notes',
        'reports every Annex it finds and rewrites nothing (F29)'),
    'article_to_clause': (
        'CONDITIONAL',
        '"Article N" is an internal cross-reference rather than a statutory citation',
        'document.xml: what follows the number in the same sentence',
        'an indeterminate reference keeps "Article" and is reported (B2)'),
    'duplicates': (
        'NOT YET TESTED',
        'a word of three or more letters said twice is an error, never the source\'s own '
        '("had had", "that that")',
        'document.xml only',
        'does not test it; no register row records a misfire'),
    'quotes': (
        'NOT YET TESTED',
        'an unmatched opening quote before a definition verb is a missing closing quote',
        'document.xml only',
        'does not test it; no register row records a misfire'),
    'definition_line_breaks': (
        'NOT YET TESTED',
        'every w:br in a paragraph holding a definition verb and a quote mark is a '
        'translation artefact, never the source\'s own line break',
        'document.xml only',
        'does not test it; no register row records a misfire'),
    'spurious_italic': (
        'CONDITIONAL',
        'an italic run of three or more words is ours, not the drafter\'s',
        'the declared notes: en_runs in its own offsets, and the source runs by exact '
        'equality',
        'no notes, no paragraph match or a run not covered: the italic is kept and '
        'reported (B1)'),
    'schedule_page_breaks': (
        'DETECTOR',
        'every Schedule/Annex heading starts on a new page -- a house convention, never a '
        'property of the source',
        'document.xml, which carries every page-start device apply copied across from the '
        'source (11 of 11 measured)',
        'reports how each heading starts its page and inserts nothing (B7)'),
}
# === THE PRINCIPLE ENDS ===

# === CHANGE JOURNAL ===
#
# WHY THIS EXISTS, AND IT IS NOT FOR THIS SCRIPT'S BENEFIT. This stage rewrites text
# DOWNSTREAM of every content check, so a character-exact comparison of the delivered
# document against what was declared is impossible unless the stage says what it changed.
# Either the opinionated passes move upstream of that comparison, or the stage journals
# every change it makes so the comparison can account for exactly those and nothing else.
# This is the second answer. Two findings say it is real rather than theoretical: one
# validator invoked three times on one file gave two different opinions about it, and on
# another document the operator was shown a DRIFT error where the cause was a TERMINOLOGY
# override — a diagnosis pointing at the wrong file entirely.
#
# THE TEXT CONTRACT, STATED ONCE. The journal records text borne by `w:t` and `w:delText`,
# in document order, identified by FLAT ORDINAL over the whole part. A flat ordinal is used
# rather than a paragraph-and-run pair because the passes below group by `p.iter()`, which
# reaches INTO a nested paragraph, while the skill's reading half deliberately does not —
# a paragraph-keyed identity would have to pick one of the two and would misattribute under
# the other. The flat enumeration is the same under both.
#
# IT WAS DECLARED BLIND TO NON-TEXT CHANGE, AND SINCE BRANCH 10 SLICE 1 IT IS NOT. Branch 9
# declared the blind spot rather than hiding it and reported it as a bare figure. Branch 10
# is the branch that makes it matter: slice 3 turns the italic strip into a CONDITIONAL
# pass, and there is no way to show a conditional pass did the right thing from a count.
#
# FOUR NON-TEXT SHAPES, COUNTED FROM THE CODE RATHER THAN ASSUMED. The spacing and
# definition-boundary passes set `xml:space` on a `w:t`; the line-break pass removes a
# `w:br` from a run; the italic strip removes `w:i` from a `w:rPr`; the page-break pass
# created a `w:pPr` and inserted `w:pageBreakBefore` -- until slice 4 made it a detector that
# inserts nothing, so three shapes remain and the record's paragraph arm now proves an absence.
# Not one is text.
#
# SO THERE IS A SECOND CONTRACT, AND IT SITS ON THE FIRST ONE'S COORDINATES. The formatting
# record uses the SAME flat ordinal and the SAME paragraph index as the text record, so a
# text edit and a formatting change at one place are readable as one place and a consumer
# needs no second coordinate system. What it holds is every tag and attribute of the `w:r`
# that carries the element, and of the paragraph's `w:pPr` — descendants included, TEXT
# EXCLUDED, because the text contract already owns text and a record holding both would
# report every text edit twice.
#
# WHAT IT STILL DOES NOT CLAIM. Where a pass changes the NUMBER of text-bearing elements or
# of paragraphs, every ordinal after the change shifts and neither record can describe it by
# ordinal; that case is reported as a note, exactly as the text record reports it. The
# per-pass element counts remain, because they are the only thing that survives that case.
#
# AND IT REPORTS, IT DOES NOT REFUSE. An un-journalled change is a defect in THIS script,
# not in the operator's document — so a gate here would fire on something nobody running
# the skill could repair, which is exactly the shape the project has measured firing on
# nothing six times out of six. The self-check prints loudly and the run continues; the
# hard assertion lives in tests/test_change_journal.py and tools/postprocess_corpus_arm.py,
# where whoever trips it can fix it.
# SCHEMA 2 IS BRANCH 10 SLICE 1's FORMATTING RECORD. The version moves because the artefact
# now describes something it did not before; a version string that never moves is one
# nobody can key on. Nothing is REMOVED at 2 — `non_text_fixes` in particular stays, because
# tools/postprocess_corpus_arm.py, tests/test_change_journal.py and both skill-docs/06 read
# it, and a field with live consumers is not quietly repurposed.
#
# SCHEMA 3 IS BRANCH 10 SLICE 4's DETECTION RECORD. Decision 2c's second limb says a pass that
# cannot decide REPORTS, and until slice 4 the report was a line on screen -- which dies with
# the run and which nothing downstream can read. `detections` is that report as data: what
# the stage FOUND and deliberately did not change, one record per finding. Again nothing is
# removed, so every schema-2 consumer reads schema 3 unchanged.
JOURNAL_SCHEMA = 'post-process-journal/3'
JOURNAL_NAME = 'post_process_journal.json'
JOURNAL_TEXT_CONTRACT = (
    'w:t and w:delText, in document order, identified by flat ordinal over the part; '
    'paragraphs grouped by the nested-paragraph rule (runs inside a nested w:p belong to '
    'that w:p). TEXT ONLY: formatting and structure belong to the format contract, which '
    'uses these same ordinals.'
)
JOURNAL_FORMAT_CONTRACT = (
    'for each text-bearing element, every tag and attribute of the w:r that carries it, '
    'descendants included and text excluded, at the SAME flat ordinal as the text record; '
    'for each paragraph, the same reading of its w:pPr, at the same paragraph index. '
    'Recorded only where the count of text-bearing elements, or of paragraphs, did not '
    'move; where it moved, the note says so and the per-pass element counts are the '
    'only account.'
)
JOURNAL_DETECTION_CONTRACT = (
    'one record per thing a pass FOUND and deliberately did NOT change: the pass, a reason '
    'from that pass\'s fixed vocabulary, the paragraph index (the same index the text and '
    'format records use; null where the pass cannot locate it) and a count. NO DOCUMENT '
    'TEXT: a lexicon-sanctioned rendering is named by its index into LEXICON_SANCTIONED and '
    'a page-start device by its code. A detection is NOT a fix and is never in `counts`.'
)

_JT = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t'
_JDT = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}delText'
_JP = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}p'
_JR = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}r'
_JPPR = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}pPr'


def journal_flat_texts(root):
    """Every text-bearing element's text, document order. Position IS the element's id."""
    return [e.text or '' for e in root.iter() if e.tag in (_JT, _JDT)]


def journal_paragraph_texts(root):
    """Paragraph text under the nested-paragraph rule — the reading half's own grouping."""
    out = []
    for p in root.iter(_JP):
        parts = []
        for e in p.iter():
            if e.tag not in (_JT, _JDT):
                continue
            a, nested = e.getparent(), False
            while a is not None and a is not p:
                if a.tag == _JP:
                    nested = True
                    break
                a = a.getparent()
            if not nested:
                parts.append(e.text or '')
        out.append(''.join(parts))
    return out


def journal_flat_paragraph_map(root):
    """For each flat ordinal, the index of the paragraph that OWNS that element.

    Ownership is the NEAREST ancestor w:p, which is the same rule
    `journal_paragraph_texts` applies from the other direction: an element inside a nested
    paragraph belongs to the inner one. Without this an edit could be located in the
    document but not in a READING, and a reading is what the downstream check compares.
    """
    # The list is bound to a name and KEPT so the lxml proxies stay alive: lxml recreates a
    # proxy on demand and a freed one's id() can be handed to a different element, which
    # would silently mis-key the map. Walking UP from the element is what makes this the
    # NEAREST ancestor — iterating paragraphs downwards finds the OUTER one first and would
    # give a nested element to the paragraph that merely contains its container.
    paragraphs = list(root.iter(_JP))
    p_index = {id(p): i for i, p in enumerate(paragraphs)}
    out = []
    for e in root.iter():
        if e.tag not in (_JT, _JDT):
            continue
        a = e.getparent()
        while a is not None and a.tag != _JP:
            a = a.getparent()
        out.append(None if a is None else p_index.get(id(a)))
    return out


def journal_element_count(root):
    """Every element, not only the text-bearing ones. This is what makes a structural
    change visible even though the journal does not record its content."""
    return sum(1 for _ in root.iter())


def _journal_shape(el):
    """One element as tag plus sorted attributes. NO TEXT, deliberately.

    The tag is the FULL `{namespace}localname` and not the localname alone. `t` is one of
    the most reused names in OOXML — `w:t` is a text run, `a:t` a DrawingML one — and a
    report written on localnames counted one chart part as four surfaces on branch 7.
    Attributes are sorted because lxml preserves source order and a re-serialisation that
    reorders them is not a formatting change.
    """
    return el.tag + ''.join(f' {k}={v}' for k, v in sorted(el.attrib.items()))


def _journal_subtree_shape(el):
    """An element and every descendant, as shapes. This is what makes `w:i` disappearing
    from a `w:rPr`, and a `w:br` disappearing from a run, both visible as one string."""
    return ' | '.join(_journal_shape(x) for x in el.iter())


def journal_flat_formats(root):
    """For each text-bearing element, the shape of the `w:r` that carries it.

    SAME ORDINAL AS `journal_flat_texts`, which is the whole point: the two records index
    one enumeration, so a consumer reading both does not have to reconcile two coordinate
    systems. An element with no `w:r` ancestor falls back to its own shape rather than to
    None, because `None` would be indistinguishable from "this run has no properties".
    """
    # The list is bound to a name and KEPT so the lxml proxies stay alive, for the reason
    # journal_flat_paragraph_map states: lxml recreates a proxy on demand and a freed one's
    # id() can be handed to a different element, which would silently mis-key the map.
    runs = list(root.iter(_JR))
    by_run = {id(r): _journal_subtree_shape(r) for r in runs}
    out = []
    for e in root.iter():
        if e.tag not in (_JT, _JDT):
            continue
        a = e.getparent()
        while a is not None and a.tag != _JR:
            a = a.getparent()
        if a is None:
            out.append(_journal_shape(e))
        else:
            cached = by_run.get(id(a))
            out.append(_journal_subtree_shape(a) if cached is None else cached)
    return out


def journal_paragraph_formats(root):
    """For each paragraph, the shape of its `w:pPr` — the empty string where it has none.

    `find` and not `iter`: a paragraph's OWN properties are a direct child, and a nested
    paragraph's `w:pPr` belongs to the nested paragraph. Same index as
    `journal_paragraph_texts`, which enumerates paragraphs the same way.
    """
    out = []
    for p in root.iter(_JP):
        ppr = p.find(_JPPR)
        out.append('' if ppr is None else _journal_subtree_shape(ppr))
    return out


class ChangeJournal:
    """Accumulates what this invocation changed. Holds no document, only what moved."""

    def __init__(self, variant):
        self.variant = variant
        self.pass_edits = []
        self.pass_paragraphs = []
        self.pass_format_edits = []
        self.pass_format_paragraphs = []
        self.pass_counts = []
        self.strip = None
        self.unaccounted = []
        self.notes = []
        # SCHEMA 3. Filled once, after every pass has run, by collect_detections() -- never
        # by the passes themselves, which is what keeps the fix counts and the findings two
        # different numbers.
        self.detections = []

    def record_pass(self, name, before_flat, after_flat,
                    before_paras, after_paras, before_n, after_n, owner_map, fixes,
                    before_fmt, after_fmt, before_pfmt, after_pfmt):
        """One pass's contribution. Called with snapshots taken either side of it.

        `fixes` is the pass's OWN return value, and it is recorded beside the text edits
        because the two can disagree and the disagreement is the interesting number. A pass
        that reports fixes while this journal records no text edit has changed something
        that is NOT text — an italic run stripped, a page break inserted, an xml:space set.
        MEASURED ON THE REAL CORPUS BEFORE THIS ARGUMENT EXISTED: one frozen intermediate
        reported TOTAL 2 fixes against 0 journalled edits and a self-check of `accounted`,
        which is true under the text contract and reads to any human as "this stage changed
        nothing". It did not. The figure below is what stops that reading.
        """
        self.pass_counts.append({
            'pass': name,
            'fixes': fixes,
            'elements_before': before_n,
            'elements_after': after_n,
        })
        if len(before_flat) == len(after_flat):
            for i, (b, a) in enumerate(zip(before_flat, after_flat)):
                if b != a:
                    self.pass_edits.append({
                        'pass': name, 'elem': i,
                        'para': owner_map[i] if i < len(owner_map) else None,
                        'before': b, 'after': a,
                    })
        elif before_flat != after_flat:
            # A pass that adds or removes a text-bearing element cannot be recorded by
            # ordinal, because every ordinal after it shifts. None does so today; say so
            # rather than record something false, and let the self-check fail on it.
            self.notes.append(
                f'{name} changed the number of text-bearing elements '
                f'({len(before_flat)} -> {len(after_flat)}); its edits are NOT recorded '
                f'by ordinal and the paragraph record below is the only account of it')
        for i, (b, a) in enumerate(zip(before_paras, after_paras)):
            if b != a:
                self.pass_paragraphs.append({'para': i, 'before': b, 'after': a})
        # THE FORMATTING RECORD, on the two enumerations above and not on a third. The
        # length guards are the text record's own, for the text record's own reason: a pass
        # that adds or removes a text-bearing element or a paragraph shifts every ordinal
        # after it, so a record written by ordinal would be false rather than incomplete.
        if len(before_fmt) == len(after_fmt):
            for i, (b, a) in enumerate(zip(before_fmt, after_fmt)):
                if b != a:
                    self.pass_format_edits.append({
                        'pass': name, 'elem': i,
                        'para': owner_map[i] if i < len(owner_map) else None,
                        'before': b, 'after': a,
                    })
        elif before_fmt != after_fmt:
            self.notes.append(
                f'{name} changed the number of text-bearing elements, so its FORMATTING '
                f'change is not recorded by ordinal either')
        if len(before_pfmt) == len(after_pfmt):
            for i, (b, a) in enumerate(zip(before_pfmt, after_pfmt)):
                if b != a:
                    self.pass_format_paragraphs.append({
                        'pass': name, 'para': i, 'before': b, 'after': a,
                    })
        elif before_pfmt != after_pfmt:
            self.notes.append(
                f'{name} changed the number of paragraphs ({len(before_pfmt)} -> '
                f'{len(after_pfmt)}); its paragraph FORMATTING change is not recorded')

    def record_strip(self, ran, before_paras, after_paras,
                     before_pfmt, after_pfmt):
        entry = {'stage': 'strip_noop_tracked_changes', 'ran': bool(ran),
                 'paragraphs': [], 'format_paragraphs': []}
        # THE STRIP GETS THE FORMAT CONTRACT TOO, AT PARAGRAPH LEVEL ONLY. It DELETES
        # w:ins/w:del wrappers, so every text-bearing element's flat ordinal after one
        # shifts and the element-level record cannot describe it — the same reason its text
        # is recorded per paragraph. Leaving the stage out entirely would have been the
        # cheaper thing and the wrong one: a contract with one stage silently exempt reads
        # as coverage, and B3 is a defect in exactly this stage.
        if ran and len(before_pfmt) == len(after_pfmt):
            for i, (b, a) in enumerate(zip(before_pfmt, after_pfmt)):
                if b != a:
                    entry['format_paragraphs'].append(
                        {'para': i, 'before': b, 'after': a})
        if ran and len(before_paras) == len(after_paras):
            for i, (b, a) in enumerate(zip(before_paras, after_paras)):
                if b != a:
                    entry['paragraphs'].append({'para': i, 'before': b, 'after': a})
        elif ran:
            entry['paragraph_count_changed'] = [len(before_paras), len(after_paras)]
            self.notes.append(
                'the strip pass changed the paragraph COUNT, which it is not documented '
                'to do; its text change is not accounted for')
        self.strip = entry

    def _collapse(self, records):
        """Several passes may move one paragraph. Keep the first `before` and the last
        `after`, so replaying the list in order reproduces the document exactly once."""
        merged = {}
        for r in records:
            i = r['para']
            if i in merged:
                merged[i]['after'] = r['after']
            else:
                merged[i] = dict(r)
        return [merged[k] for k in sorted(merged)]

    def to_dict(self, doc_basename):
        stages = [{
            'stage': 'passes',
            'edits': self.pass_edits,
            'paragraphs': self._collapse(self.pass_paragraphs),
            # NOT collapsed, and the difference from `paragraphs` above is deliberate. The
            # text record collapses so that replaying it reproduces the document exactly
            # once. A formatting record is read to answer WHICH PASS changed this run, and
            # collapsing two passes' changes into one entry destroys exactly that — which
            # is the question branch 10 slice 3 has to answer about a conditional pass.
            'format_edits': self.pass_format_edits,
            'format_paragraphs': self.pass_format_paragraphs,
            'counts': self.pass_counts,
        }]
        if self.strip is not None:
            stages.append(self.strip)
        return {
            'schema': JOURNAL_SCHEMA,
            'script': 'post_process.py',
            'variant': self.variant,
            # BASENAME ONLY, NEVER A PATH. A workdir path can carry a client or matter name
            # and this file is written next to the operator's notes, not inside the
            # deliverable — but a filename is the one thing a log has repeatedly leaked.
            'document': doc_basename,
            'text_contract': JOURNAL_TEXT_CONTRACT,
            'format_contract': JOURNAL_FORMAT_CONTRACT,
            'detection_contract': JOURNAL_DETECTION_CONTRACT,
            'stages': stages,
            'detections': self.detections,
            'self_check': {
                'accounted': not self.unaccounted and not self.notes,
                'unaccounted_paragraphs': self.unaccounted,
                'notes': self.notes,
                # WHAT `accounted` DOES NOT COVER, STATED IN THE ARTEFACT RATHER THAN ONLY
                # IN THE SOURCE. `accounted` answers "was every TEXT change recorded". These
                # passes reported a fix and produced no text edit, so they changed something
                # the text contract does not describe — formatting, a page break, an
                # attribute. A reader who takes `accounted: true` to mean "nothing else
                # happened" is wrong, and this is the figure that tells them so.
                #
                # KEPT UNCHANGED AT SCHEMA 2 THOUGH THE FORMAT RECORD NOW EXPLAINS MOST OF
                # IT. It has live consumers — the corpus arm, the suite and both
                # skill-docs/06 — and a field whose MEANING changes under a name that does
                # not is worse than a new field. What answers it is `unexplained_fixes`.
                'non_text_fixes': [
                    {'pass': c['pass'], 'fixes': c['fixes']}
                    for c in self.pass_counts
                    if c['fixes'] and not any(e['pass'] == c['pass']
                                              for e in self.pass_edits)
                ],
                # THE FIGURE THAT SHOULD BE EMPTY, and the one to read first. A pass that
                # reported a fix while NEITHER record shows anything changed at any ordinal
                # has done something both contracts are blind to. Before slice 1 every
                # non-text fix was in this position and there was no way to tell them apart;
                # now the italic strip and the page-break pass explain themselves and what
                # is left here is a genuine gap rather than a known one.
                'unexplained_fixes': [
                    {'pass': c['pass'], 'fixes': c['fixes']}
                    for c in self.pass_counts
                    if c['fixes']
                    and not any(e['pass'] == c['pass'] for e in self.pass_edits)
                    and not any(e['pass'] == c['pass'] for e in self.pass_format_edits)
                    and not any(e['pass'] == c['pass']
                                for e in self.pass_format_paragraphs)
                ],
            },
        }


def journal_workdir(xml_path):
    """<workdir>/final/word/document.xml -> <workdir>. The convention skill-docs/06 states.

    Returns None when the layout is not the conventional one, and the journal is then NOT
    written. It is deliberately never written beside the XML: `final/` is the directory
    repack reads parts out of, and a file that cannot be there cannot be bundled by mistake.
    """
    try:
        xml_abs = os.path.abspath(xml_path)
        parent = os.path.dirname(xml_abs)
        if os.path.basename(parent).lower() != 'word':
            return None
        final = os.path.dirname(parent)
        if os.path.basename(final).lower() != 'final':
            return None
        workdir = os.path.dirname(final)
        return workdir if os.path.isdir(workdir) else None
    except (OSError, ValueError):
        return None


def journal_write(journal, xml_path, final_paras, original_paras):
    """Write the journal, after checking it can reproduce the document it describes.

    THE SELF-CHECK IS NOT THE PROOF. It shares this module's reader with the thing it
    checks, so it can be self-consistently wrong; that is why the real assertion is made by
    a SECOND reader in tests/test_change_journal.py. What it does catch is the gross case —
    a pass that moved text no snapshot saw — and it says so where the operator will read it.
    """
    workdir = journal_workdir(xml_path)
    if workdir is None:
        print('  [journal] NOT WRITTEN — this document.xml is not at '
              '<workdir>/final/word/, so there is no conventional place to put it. '
              'Nothing is written beside the XML, because that directory is bundled.')
        return None

    replayed = list(original_paras)
    for stage in journal.to_dict('x')['stages']:
        for rec in stage.get('paragraphs', []):
            i = rec['para']
            if 0 <= i < len(replayed):
                replayed[i] = rec['after']
    if len(replayed) != len(final_paras):
        journal.notes.append(
            f'paragraph count moved during post-processing '
            f'({len(replayed)} -> {len(final_paras)})')
    else:
        journal.unaccounted = [i for i, (r, f) in enumerate(zip(replayed, final_paras))
                               if r != f]

    data = journal.to_dict(os.path.basename(os.path.abspath(xml_path)))
    out = os.path.join(workdir, JOURNAL_NAME)
    # Written as BYTES with an explicit newline. `write_text`/text mode turns every \n into
    # \r\n on Windows, which changes a file every byte-comparison in this project reads.
    with open(out, 'wb') as fh:
        fh.write((json.dumps(data, ensure_ascii=False, indent=2) + '\n')
                 .encode('utf-8'))

    n_edits = len(data['stages'][0]['edits'])
    n_paras = sum(len(s.get('paragraphs', [])) for s in data['stages'])
    n_fmt = sum(len(s.get('format_edits', [])) for s in data['stages'])
    n_fmt_p = sum(len(s.get('format_paragraphs', [])) for s in data['stages'])
    print(f'  [journal] {n_edits} edit(s) across {n_paras} paragraph(s) -> {JOURNAL_NAME}')
    if n_fmt or n_fmt_p:
        print(f'  [journal] and {n_fmt} formatting change(s) on {n_fmt_p} paragraph(s) '
              f'— run properties and paragraph properties, not text')
    if data['detections']:
        print(f"  [journal] and {len(data['detections'])} detection(s) — what the stage "
              f"FOUND and deliberately did not change, one record each, no document text")
    nontext = data['self_check']['non_text_fixes']
    unexplained = data['self_check']['unexplained_fixes']
    if nontext:
        # SAID ON SCREEN, not only in the file. "0 edits" beside "TOTAL: 2 fixes" reads as
        # a contradiction and sends the reader looking for a bug. Since schema 2 the honest
        # line is narrower than it was: those fixes are not TEXT, and most of them are now
        # described after all — by the formatting record, one line up.
        which = ', '.join(f"{n['pass']} ({n['fixes']})" for n in nontext)
        print(f'  [journal] {sum(n["fixes"] for n in nontext)} of those fix(es) changed no '
              f'text: {which}')
    if unexplained:
        which = ', '.join(f"{n['pass']} ({n['fixes']})" for n in unexplained)
        print(f'  [journal] and {sum(n["fixes"] for n in unexplained)} fix(es) that NEITHER '
              f'record describes — a genuine gap, not a known one: {which}')
    if not data['self_check']['accounted']:
        print('  ' + '!' * 58)
        print('  [journal] SELF-CHECK DID NOT ACCOUNT FOR EVERY CHANGE. This is a defect '
              'in post_process.py, not in your document — the translation is unaffected '
              'and the run continues. Report it; do NOT edit the document to suit it.')
        for i in data['self_check']['unaccounted_paragraphs'][:10]:
            print(f'    unaccounted paragraph index: {i}')
        for note in data['self_check']['notes']:
            print(f'    note: {note}')
        print('  ' + '!' * 58)
    return out
# === CHANGE JOURNAL ENDS ===


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



W = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'

# ============================================================
# TERMINOLOGY REPLACEMENTS  (order matters: longer matches first)
# ============================================================
TERM_REPLACEMENTS = [
    # (pattern, replacement, is_regex)

    # --- Financing / Facility ---
    ('Financing Agreement', 'Facility Agreement', False),
    ('Financing Bank', 'Lender', False),
    ('Description of Financing', 'Description of the Facility', False),
    ('Description of the Financing', 'Description of the Facility', False),

    # --- Banking Transparency -> Transparency of Banking Conditions ---
    ('BANKING TRANSPARENCY', 'TRANSPARENCY OF BANKING CONDITIONS', False),
    ('Banking Transparency', 'Transparency of Banking Conditions', False),
    ('banking transparency', 'transparency of banking conditions', False),

    # --- Structural / cross-ref ---
    ('Domicile Election', 'Service of Process', False),
    ('DOMICILE ELECTION', 'SERVICE OF PROCESS', False),
    ('Election of Domicile', 'Service of Process', False),
    ('ELECTION OF DOMICILE', 'SERVICE OF PROCESS', False),
    ('election of domicile', 'service of process', False),
    ('Partial Invalidity', 'Severability', False),
    ('PARTIAL INVALIDITY', 'SEVERABILITY', False),
    ('which intervenes as', 'acting as', False),
    ('who intervenes as', 'acting as', False),
    ('intervenes as', 'acts as', False),
    ('Business Register', 'Companies Register', False),
    ('Lien Assets', 'Secured Assets', False),

    # --- "that precedes/follows" (singular AND plural) ---
    ('that precedes', 'above', False),
    ('that precede,', 'above,', False),
    ('that precede ', 'above ', False),
    ('that follows', 'below', False),
    ('that follow,', 'below,', False),
    ('that follow ', 'below ', False),

    # --- Publicity -> Perfection (project finance term) ---
    ('REGISTRATION AND PUBLICITY', 'REGISTRATION AND PERFECTION', False),
    ('Registration and Publicity', 'Registration and Perfection', False),
    ('registration and publicity', 'registration and perfection', False),
    ('TRANSCRIPTION AND PUBLICITY', 'REGISTRATION AND PERFECTION', False),
    ('Transcription and Publicity', 'Registration and Perfection', False),
    ('transcription and publicity', 'registration and perfection', False),

    # --- Literal translation patterns ---
    ('by universal or singular title', 'whether by way of universal or individual succession', False),
    # 'stipulated' is calque ONLY in verb-of-contracting context.
    # The  blanket replacement broke legitimate adjective use
    # ("in the proportions stipulated in the Memorandum" = "set out
    # in the Memorandum"). Narrow patterns capture only the calque
    # ("hereby stipulate", "to stipulate", "the parties stipulate")
    # and leave the adjective alone. Preserves correctness on every
    # document that uses "stipulated" in its non-calque sense — which
    # is most of them.
    ('hereby stipulate', 'hereby agree', False),
    ('hereby Stipulate', 'hereby agree', False),
    ('the parties stipulate', 'the parties agree', False),
    ('the Parties stipulate', 'the Parties agree', False),
    ('to stipulate', 'to enter into', False),
    ('to Stipulate', 'to enter into', False),

    # --- Finance / LMA ---
    ('cash line', 'term facility', False),
    ('Cash line', 'Term facility', False),
    ('revolving line', 'revolving facility', False),
    ('Revolving line', 'Revolving facility', False),
    ('credit lines', 'credit facilities', False),
    ('Credit lines', 'Credit facilities', False),
    ('credit line', 'credit facility', False),
    ('Credit line', 'Credit facility', False),

    # --- Title/header fixes ---
    ('DEED OF CONSTITUTION OF PLEDGE', 'DEED OF PLEDGE', False),
    ('Deed of Constitution of Pledge', 'Deed of Pledge', False),
    ('deed of constitution of pledge', 'deed of pledge', False),
    ('deed of constitution of the pledge', 'deed of pledge', False),
    ('Deed of constitution of the Pledge', 'Deed of Pledge', False),
    ('deed of creation of the pledge', 'deed of pledge of quotas', False),
    ('deed of creation of the Pledge', 'Deed of Pledge of Quotas', False),
    ('Deed of Establishment of Special Lien', 'Deed of Special Lien', False),
    ('DEED OF ESTABLISHMENT OF SPECIAL LIEN', 'DEED OF SPECIAL LIEN', False),
    ('Deed of establishment of special lien', 'Deed of Special Lien', False),
    ('Deed of Creation of Mortgage', 'Deed of Mortgage', False),
    ('DEED OF CREATION OF MORTGAGE', 'DEED OF MORTGAGE', False),
    ('deed of creation of mortgage', 'deed of mortgage', False),
    ('Deed of Establishment of Mortgage', 'Deed of Mortgage', False),
    ('DEED OF ESTABLISHMENT OF MORTGAGE', 'DEED OF MORTGAGE', False),

    # --- Italian remnant defined terms ---
    # These are common Italian terms that sometimes survive translation
    ('\u201cParti\u201d', '\u201cParties\u201d', False),
    ('"Parti"', '"Parties"', False),
    ('\u201cParte\u201d', '\u201cParty\u201d', False),
    ('"Parte"', '"Party"', False),
    ('cinquanta per cento', 'fifty per cent', False),
]

# Regex-based replacements (applied after literal ones)
TERM_REGEX_REPLACEMENTS = [
    # Standalone "Financing" -> "Facility" (but NOT "Project Financing")
    (r'(?<!Project )\bFinancing\b(?! Bank)', 'Facility'),

    # Word order: "X existing and future" -> "existing and future X"
    (r'\b(plants?\s+and\s+works?)\s+existing\s+and\s+future\b', r'existing and future \1'),
    (r'\b(assets?)\s+existing\s+and\s+future\b', r'existing and future \1'),
    (r'\b(receivables?)\s+existing\s+and\s+future\b', r'existing and future \1'),
    (r'\b(goods?)\s+existing\s+and\s+future\b', r'existing and future \1'),
    (r'\b(works?)\s+existing\s+and\s+future\b', r'existing and future \1'),
    (r'\b(rights?)\s+existing\s+and\s+future\b', r'existing and future \1'),
    (r'\b(obligations?)\s+existing\s+and\s+future\b', r'existing and future \1'),
    (r'\b(claims?)\s+existing\s+and\s+future\b', r'existing and future \1'),
    (r'\b(credits?)\s+existing\s+and\s+future\b', r'existing and future \1'),
    (r'\b(sums?)\s+existing\s+and\s+future\b', r'existing and future \1'),

    # "ciascuna" -> "each" (common Italian remnant)
    (r'\bciascuna\b', 'each'),
    (r'\bciascuno\b', 'each'),
    (r'\bciascun\b', 'each'),
]

# UK SPELLING
UK_SPELLING = [
    (r'\bauthorize\b', 'authorise'),
    (r'\bauthorized\b', 'authorised'),
    (r'\bAuthorized\b', 'Authorised'),
    (r'\bAUTHORIZATION\b', 'AUTHORISATION'),
    (r'\bAuthorization\b', 'Authorisation'),
    (r'\bauthorization\b', 'authorisation'),
    (r'\brecognize\b', 'recognise'),
    (r'\brecognized\b', 'recognised'),
    (r'\brecognition\b', 'recognition'),  # no change — same in UK
    (r'\borganize\b', 'organise'),
    (r'\borganized\b', 'organised'),
    (r'\borganization\b', 'organisation'),
    (r'\bfavor\b', 'favour'),
    (r'\bfavored\b', 'favoured'),
    (r'\bfavorable\b', 'favourable'),
    (r'\bhonor\b', 'honour'),
    (r'\bhonored\b', 'honoured'),
    (r'\bcenter\b', 'centre'),
    (r'\bdefense\b', 'defence'),
    (r'\boffense\b', 'offence'),
    (r'\bfulfill\b', 'fulfil'),
    (r'\bfulfillment\b', 'fulfilment'),
    (r'\bjudgment\b', 'judgement'),
    (r'\bjudgments\b', 'judgements'),
    (r'\bJudgment\b', 'Judgement'),
    (r'\backnowledgment\b', 'acknowledgement'),
    (r'\backnowledgments\b', 'acknowledgements'),
    (r'\butilize\b', 'utilise'),
    (r'\butilized\b', 'utilised'),
    (r'\butilization\b', 'utilisation'),
    (r'\bcanceled\b', 'cancelled'),
    (r'\bcanceling\b', 'cancelling'),
    (r'\blabor\b', 'labour'),
    (r'\bpractice\b(?=\s+(?:of|the|in|by))', 'practice'),  # noun OK in UK
    (r'\bpractise\b', 'practise'),  # verb form
    (r'\banalyze\b', 'analyse'),
    (r'\banalyzed\b', 'analysed'),
]

# Legislation references fix_annex never considers. Since branch 10 slice 3b that pass rewrites
# nothing (see its docstring); translate_numbering's _LABEL_EXCLUDE must equal this list, and
# tests/test_lexicon_choice.py asserts it.
ANNEX_EXCLUDE = ['Regulation', 'Directive', 'Law', 'Decree', 'Regolamento']

# LEGISLATION KEYWORDS (paragraphs containing these keep "Article")
# replaced the LEGISLATION_KW hardcoded list (which had to
# enumerate "Civil Code", "Royal Decree", "T.U.B.", etc. and missed
# "Code of Civil Procedure", "Resolution of the CICR", etc.) with a
# language-agnostic structural detector. See _is_external_article_ref().
#
# The discriminator is the linguistic shape of what follows "Article N":
#
#   "Article N of <Capitalized Proper Noun>"     → external (keep)
#   "Article N of this/the present/the said X"   → internal (rewrite)
#   "Article N of <internal anchor>"             → internal (rewrite)
#       internal anchors: Schedule, Annex, Section, Paragraph, Clause,
#       Article, Chapter, Exhibit, Appendix, Attachment, Annexure
#   bare "Article N." or "(Article N)"           → internal (rewrite,
#                                                    matches v5 default)
#
# No keyword list; works for any source-language legislation reference
# the LLM rendered into English in the conventional "of <Capitalized
# Act Name>" shape.

# Internal-reference determiners (lowercase). When "Article N" is
# followed by " of <one of these>", it is an internal cross-reference.
_INTERNAL_DETERMINERS = (
    'this ', 'the present ', 'the said ', 'this same ',
    'that precedes ', 'that follows ', 'the foregoing ',
    'the preceding ', 'the following ',
)

# Internal anchor words. When "Article N" is followed by
# " of [the/a] <one of these>", it is an internal cross-reference
# (e.g. "Article 5 of Schedule B" → "Clause 5 of Schedule B").
_INTERNAL_ANCHOR_WORDS = (
    'Schedule', 'Schedules', 'Annex', 'Annexes', 'Annexure', 'Annexures',
    'Attachment', 'Attachments', 'Appendix', 'Appendices', 'Appendixes',
    'Exhibit', 'Exhibits', 'Section', 'Sections', 'Paragraph', 'Paragraphs',
    'Subparagraph', 'Subparagraphs', 'Clause', 'Clauses',
    'Article', 'Articles', 'Chapter', 'Chapters', 'Part', 'Parts',
)

# Internal locator words that follow "Article N" without "of":
# "Article N above", "Article N hereof", "Article N below", etc.
_INTERNAL_LOCATORS = (
    'above', 'below', 'hereof', 'hereto', 'herein',
    'hereinafter', 'hereinabove', 'hereinbelow', 'hereunder',
    'foregoing', 'preceding', 'following', 'said',
)

def _skip_noise_after_article(text):
    """Given text starting right after "Article N", skip past optional
    sub-numbering (".M.K"), parenthetical letters/numbers ("(b)",
    "(i)"), and number-list conjunctions (" and 6", ", 7"). Return the
    position in ``text`` where the next content word starts, or -1 if
    we hit a sentence boundary first."""
    pos = 0
    while pos < len(text):
        ch = text[pos]
        # Whitespace
        if ch.isspace():
            pos += 1
            continue
        # Sub-numbering ".M" / ".M.K"
        if ch == '.' and pos + 1 < len(text) and text[pos + 1].isdigit():
            pos += 1
            while pos < len(text) and (
                    text[pos].isdigit() or text[pos] == '.'):
                pos += 1
            continue
        # Sentence-ending punctuation
        if ch in '.!?;':
            return -1
        # Parenthetical letter / roman / short number ("(a)", "(iii)", "(2)")
        if ch == '(':
            close = text.find(')', pos)
            if 0 < close - pos <= 6:
                pos = close + 1
                continue
        # "and N(-bis)?", "or N", "to N" — conjunction with another
        # number. Also consumes hyphenated alpha suffix on the trailing
        # number ("Articles 2482-bis and 2482-ter").
        m = re.match(
            r'(?:and|or|to)\s+\d+(?:[.:]\d+)*(?:-[A-Za-z]{1,15})*',
            text[pos:])
        if m:
            pos += m.end()
            continue
        # ", N" / ", N.M" — comma-separated number list (also hyphen-
        # suffix-aware).
        m2 = re.match(
            r',\s*\d+(?:[.:]\d+)*(?:-[A-Za-z]{1,15})*',
            text[pos:])
        if m2:
            pos += m2.end()
            continue
        # Anything else — start of the next content word
        return pos
    return -1

ARTICLE_EXTERNAL = 'external'
ARTICLE_INTERNAL = 'internal'
ARTICLE_INDETERMINATE = 'indeterminate'

# B2's detector output: the "Article N" references this run declined to
# classify, and therefore declined to rewrite -- one {'para': index} each since
# slice 4, the reference's text deliberately not kept. Read by the caller after
# `fix_article_to_clause` returns and printed with the pass summary, because a
# pass that silently stops rewriting reads as a pass that found nothing to do.
ARTICLE_UNDECIDED = []

# B8's detector output: the doubled punctuation marks this run FOUND and
# deliberately did not collapse. Same reason as above, and the same shape: the
# pass's return value is journalled as a fix count, so a detection cannot ride
# on it without making "changed nothing" and "found nothing" the same number.
DOUBLE_PUNCTUATION_FOUND = []


def _classify_article_ref(joined_text, match_end):
    """Classify the "Article N" / "Articles N" match ending at ``match_end`` in
    ``joined_text`` as an EXTERNAL legislation / regulatory reference (keep as
    Article), an INTERNAL cross-reference (rewrite to Clause), or
    INDETERMINATE.

    **B2 — THE THIRD ANSWER IS THE FIX, AND IT USED TO BE SPELT "INTERNAL".**
    This walk reads FORWARD from the number, and where the sentence runs out
    with no decisive token it used to answer *internal* and the caller rewrote.
    That is a guess presented as a decision, and on D05 it turned a STATUTORY
    citation into an internal "Section N" that does not exist in the deed — a
    substantive legal error, surfaced only because a declared token went
    missing. The shape that defeats the walk is ordinary: in "Article 1341
    thereof", `thereof` points BACKWARD at an instrument already named, and it
    is not in `_INTERNAL_LOCATORS` — which holds only the HERE- family, words
    that genuinely mean *this document* — so the walk skips it as lowercase
    noise and reaches the end of the sentence having learnt nothing.

    Decision 2c revised: a pass that cannot determine its condition REPORTS AND
    CHANGES NOTHING. So the terminal answer is now INDETERMINATE and the caller
    leaves the text alone.

    WHAT IT COSTS, AND THE FIRST MEASUREMENT OF IT WAS TAKEN IN THE WRONG PLACE.
    Over the APPLIED `document.xml` of all 13 frozen workdirs, joining each
    paragraph exactly as the pass does: **58 references — 57 external, 0
    decided internal by a token, and 1 INDETERMINATE.** That one is on the
    corpus, not only in a fixture: running the stage over it, this pass
    reported 1 fix before the change and 0 after, so a real document was having
    a reference rewritten on a guess.

    The figure was first taken from the `en` field of the frozen NOTES and came
    back 0 indeterminate and 1 internal — from which it followed, wrongly, that
    the change was free and that only a synthetic fixture could evidence it.
    The notes and the document are different strings, assembled differently,
    and this pass reads the document. A claim about BEHAVIOUR measured anywhere
    but where the behaviour happens is a claim about something else.

    Returns one of ARTICLE_EXTERNAL / ARTICLE_INTERNAL / ARTICLE_INDETERMINATE.

    **Rev16 — pure structural walk.** Instead of enumerating the
    civil-law citation modifiers that can appear between an article
    number and the named act ("et seq.", "ff.", ", first paragraph",
    ", letter X", ", comma N", ", second sub-paragraph", ...), this
    function walks the entire sentence after "Article N" word by word
    and classifies based on the FIRST decisive token:

      * an internal locator ("above", "below", "hereof", ...)
        → internal (rewrite to Clause)
      * an internal anchor word ("Schedule", "Annex", "Section",
        "Paragraph", "Clause", "Chapter", "Part", ...)
        → internal cross-reference (rewrite)
      * a Capitalised Proper Noun preceded by an internal determiner
        ("this", "the said", "the present", ...)
        → internal (e.g. "this Agreement")
      * a Capitalised Proper Noun NOT preceded by an internal
        determiner → EXTERNAL (keep Article)
      * end of sentence reached without any decisive token
        → INDETERMINATE (report, change nothing) — was "internal default"
          until B2

    Lowercase noise words (et, seq, of, the, paragraph, first, second,
    letter, comma, etc.) are simply skipped — no need to enumerate
    them. Chained "Article(s) N" references in the same sentence are
    skipped past as continuations of the same citation chain.

    Works for any source language (the rewrite operates on translated
    English, where capitalisation conventions are uniform). Length
    cap of 250 characters on the tail is structural protection
    against runaway scanning.
    """
    tail = joined_text[match_end:match_end + 250]
    # Smart sentence-end truncation: a "." is a sentence end only if
    # followed by whitespace + Uppercase (start of new sentence) or
    # end-of-text. "." inside a number or before a lowercase word
    # (like "et seq. of") is NOT a sentence end.
    end = len(tail)
    i = 0
    while i < len(tail):
        ch = tail[i]
        if ch in '!?\n':
            end = i
            break
        if ch == '.':
            if i + 1 >= len(tail):
                end = i
                break
            nxt = tail[i + 1]
            if nxt.isdigit():
                i += 1
                continue
            # Period followed by space + uppercase = sentence end.
            j = i + 1
            while j < len(tail) and tail[j] == ' ':
                j += 1
            if j < len(tail) and tail[j].isupper():
                end = i
                break
            # Otherwise (period before lowercase) — abbreviation, keep
        i += 1
    tail = tail[:end]

    # Walk word by word.
    word_re = re.compile(r"[A-Za-z][A-Za-z0-9\'\-]*")
    chain_re = re.compile(
        r"\bArticles?\s+\d[\d.:]*(?:-[A-Za-z]{1,15})*")
    pos = 0
    while pos < len(tail):
        # Skip whitespace
        if tail[pos].isspace():
            pos += 1
            continue
        # Skip past chained "Article(s) N" — it's a continuation of
        # the same citation, not a target anchor.
        cm = chain_re.match(tail, pos)
        if cm:
            pos = cm.end()
            continue
        # Try to read a word at pos
        wm = word_re.match(tail, pos)
        if not wm:
            # Not a word — punctuation, digit, parenthesis, comma, etc.
            # Just advance one character.
            pos += 1
            continue
        word = wm.group(0)
        word_start = wm.start()
        # Internal locator? ("above", "below", "hereof", etc.)
        if word.lower() in _INTERNAL_LOCATORS:
            return ARTICLE_INTERNAL
        # Lowercase word — pure noise; skip.
        if not word[0].isupper():
            pos = wm.end()
            continue
        # Internal anchor? ("Schedule", "Annex", "Section", ...)
        if word in _INTERNAL_ANCHOR_WORDS:
            return ARTICLE_INTERNAL  # internal cross-reference
        # Capitalised non-anchor — check for an internal-determiner
        # immediately preceding ("this", "the said", "the present",
        # etc.). Strip trailing whitespace from the prefix and look
        # for an exact-determiner ending.
        before = tail[:word_start].rstrip()
        before_lower = before.lower()
        for det in _INTERNAL_DETERMINERS:
            det = det.rstrip()  # _INTERNAL_DETERMINERS includes trailing space
            if (before_lower == det or
                    before_lower.endswith(' ' + det)):
                # "this Agreement", "the said Deed", etc.
                return ARTICLE_INTERNAL
        # Capitalised, not an anchor, not preceded by internal
        # determiner → external Proper Noun (Civil Code, Italian Code
        # of Civil Procedure, Resolution of the CICR, EU Regulation,
        # Presidential Decree, BGB, T.U.B., etc.)
        return ARTICLE_EXTERNAL
    # NO DECISIVE TOKEN IN THE SENTENCE. This used to answer "internal", and
    # answering was the defect — see `_is_external_article_ref` below.
    return ARTICLE_INDETERMINATE


def _is_external_article_ref(joined_text, match_end):
    """Back-compatible boolean wrapper: True iff the reference is decided
    EXTERNAL. An indeterminate reference is not external, so it reads False
    here — which is why callers must use `_classify_article_ref` instead when
    the difference matters, and `fix_article_to_clause` does.
    """
    return _classify_article_ref(joined_text, match_end) == ARTICLE_EXTERNAL

# rev42: Predicate for fix_spacing's space-insertion rules. Extracted to
# module level so apply_translations_textmatch.py can import it for the
# rev42 auto-ZWSP injection on non-Latin source paragraphs. The two
# scripts MUST use the same predicate so that auto-ZWSP fires at every
# boundary fix_spacing would otherwise space. Any change to a rule below
# changes the auto-ZWSP scope automatically — single source of truth.
_DOT_UPPER_ABBREVIATION_EXCEPTIONS = (
    'No.', 'no.', 'etc.', 'art.', 'S.p.A.', 'S.r.l.', '..', 'seq.',
)
_DOT_SINGLE_LETTER_ABBR_RE = re.compile(r'\b[A-Z]\.$')


def will_fix_spacing_fire(prev_text, curr_text):
    """Return True iff fix_spacing would insert a space between
    `prev_text` (last char) and `curr_text` (first char) at a
    text-bearing element boundary. Mirrors the 7 rules used inside
    fix_spacing below (alpha+alpha, alpha+'(', ')'+alpha, ';'+alpha,
    ','+alpha, ':'+alpha, '.'+upper-with-abbreviation-exceptions,
    digit+upper). Cheap: 1 char lookup + ≤2 string-end checks for the
    abbreviation exceptions when the dot-upper rule is candidate.
    """
    if not prev_text or not curr_text:
        return False
    pc = prev_text[-1]
    cc = curr_text[0]
    if pc.isalpha() and cc.isalpha():
        return True
    if pc.isalpha() and cc == '(':
        return True
    if pc == ')' and cc.isalpha():
        return True
    if pc == ';' and cc.isalpha():
        return True
    if pc == ',' and cc.isalpha():
        return True
    if pc == ':' and cc.isalpha():
        return True
    if pc == '.' and cc.isupper():
        if (not _DOT_SINGLE_LETTER_ABBR_RE.search(prev_text)
                and not any(prev_text.endswith(s)
                            for s in _DOT_UPPER_ABBREVIATION_EXCEPTIONS)):
            return True
    if pc.isdigit() and cc.isupper():
        return True
    return False


def _is_rendered_separator(el):
    """Return True if `el` renders as horizontal or line separation between the
    text on either side of it — a tab CHARACTER or a break.

    A ``w:tab`` INSIDE ``w:pPr/w:tabs`` IS A TAB STOP AND IS NOT ONE. It carries
    the same tag name as a rendered tab and is a layout declaration, not content,
    so a walk that sums the two treats a paragraph's tab-stop table as separation
    that is not there and skips seams that should fire. That is the OOXML rule
    "count tab CHARACTERS separately from tab STOPS", and it is why this function
    tests ancestry rather than the tag alone.
    """
    tag = el.tag
    if tag == f'{{{W}}}br':
        return True
    if tag != f'{{{W}}}tab':
        return False
    for anc in el.iterancestors():
        if anc.tag == f'{{{W}}}tabs':
            return False
    return True


def fix_spacing(root):
    """Insert a missing space between adjacent text elements within a paragraph
    — but ONLY where nothing between them already supplies the separation.

    now iterates ``<w:t>`` AND ``<w:delText>`` together in
    document order. The  version only walked ``<w:t>``, so the
    seam between an inserted run and a struck-through deletion was
    never inspected — the reject-all view of paragraphs with
    del-then-regular structure showed cosmetic glue
    (``"theInvestment Insurance"`` instead of
    ``"the Investment Insurance"``) that survived every gate. The
    fix preserves accept-all readability because the inserted space
    is prepended to the second element's text only — when one of
    the two elements is a delText, the fix-up applies inside the
    deletion side, so the accept-all view (which strips deleted
    text) is unaffected.

    rev42: the per-boundary rule check is now ``will_fix_spacing_fire``
    (module-level), a single source of truth for the per-boundary CHARACTER
    rule. That predicate is unchanged by the fix below, deliberately: what
    was wrong was never which character pairs need a space, but whether this
    walk could see what sat between them.

    **B4 — THE PASS NOW TESTS THE CONDITION IT ALWAYS ASSUMED.** It compared the
    last character of one text element against the first of the next and
    inserted a separator that the intervening element ALREADY PROVIDED, because
    it collected text-bearing elements and threw everything else away. A tab or a
    break between two runs renders as separation; adding a space to it puts a
    spurious space at the head of the second column of a signature block, or
    after every tab in a schedule. Measured over the frozen corpus: **25 such
    seams across 7 of 13 documents**, against 91 seams with genuinely nothing
    between them, which are untouched. The register's control is unusually good
    — two runs of one document, one with the spurious spaces and one without,
    same script — so the diagnosis was never inferred.

    The condition is now read from the document: a seam bridged by a RENDERED
    separator is skipped. Nothing else changes, and a seam with no element
    between it behaves exactly as before.
    """
    fixes = 0
    text_tag = f'{{{W}}}t'
    deltext_tag = f'{{{W}}}delText'
    for p in root.iter(f'{{{W}}}p'):
        # ONE walk in document order, keeping what sits BETWEEN the text-bearing
        # elements rather than discarding it. The previous version built a list of
        # text elements only, which is precisely why it could not see a tab.
        prev_elem = None
        bridged = False
        for e in p.iter():
            if (e.tag == text_tag or e.tag == deltext_tag) and e.text:
                if prev_elem is not None and not bridged:
                    if will_fix_spacing_fire(prev_elem.text, e.text):
                        e.text = ' ' + e.text
                        e.set('{http://www.w3.org/XML/1998/namespace}space',
                              'preserve')
                        fixes += 1
                prev_elem = e
                bridged = False
            elif prev_elem is not None and _is_rendered_separator(e):
                bridged = True
    return fixes

def fix_definition_boundaries(root):
    """Fix missing spaces before 'means', 'shall mean', 'has the meaning', 'indicates'.

    Catches patterns like:
      - 'Termmeans' -> 'Term means'
      - 'Termshall mean' -> 'Term shall mean'
      - 'Termhas the meaning' -> 'Term has the meaning'
      - 'Termindicates' -> 'Term indicates'
    Both within single elements and across element boundaries.
    """
    fixes = 0

    # Within single elements
    for t in root.iter(f'{{{W}}}t'):
        if t.text is None:
            continue
        orig = t.text
        # "Xmeans" -> "X means" (but not "it means", "which means" etc.)
        t.text = re.sub(r'([A-Z\u201d"\)])means\b', r'\1 means', t.text)
        t.text = re.sub(r'([A-Z\u201d"\)])shall mean\b', r'\1 shall mean', t.text)
        t.text = re.sub(r'([A-Z\u201d"\)])has the meaning\b', r'\1 has the meaning', t.text)
        t.text = re.sub(r'([A-Z\u201d"\)])indicates\b', r'\1 indicates', t.text)
        if t.text != orig:
            fixes += 1

    # Across element boundaries: prev ends with term, curr starts with "means"
    for p in root.iter(f'{{{W}}}p'):
        t_elems = [(t, t.text) for t in p.iter(f'{{{W}}}t') if t.text]
        for i in range(1, len(t_elems)):
            prev = t_elems[i-1][1]
            curr_elem, curr = t_elems[i]
            if not prev or not curr:
                continue
            # Check if curr starts with definition verb and prev doesn't end with space
            if prev[-1] != ' ' and re.match(r'^(means|shall mean|has the meaning|indicates)\b', curr):
                curr_elem.text = ' ' + curr_elem.text
                curr_elem.set('{http://www.w3.org/XML/1998/namespace}space', 'preserve')
                fixes += 1

    return fixes

def fix_double_punctuation(root):
    """REPORT double colons, double periods (not ellipsis), double commas and
    double semicolons. **This pass no longer rewrites anything.**

    **B8 — THE CONDITION IT ASSUMED CANNOT BE TESTED FROM THE DOCUMENT, SO IT
    REPORTS.** The rule assumed a doubled mark was an artefact of translation,
    something this pipeline introduced and should tidy away. It is not
    necessarily: the doubling is often PRE-EXISTING, and `document.xml` carries
    nothing that says who wrote it. On D01 the hand-typed signature rule was a
    dot leader of 36 ellipses containing `..`, and this pass collapsed it to
    `.` — a character of SOURCE CONTENT deleted, invisibly, because
    ``validate_apply --strict`` compares token SETS and a lone full stop is not
    a token (C1). Severity is genuinely LOW — a decorative rule, no legal
    content — but it is the fifth pass documented as altering faithful text
    unasked, and it is the one where the operator saw the defect, found a cure
    and rightly declined to use it.

    Under decision 2c revised, a pass that cannot determine its condition
    reports and changes nothing; a pass left with nothing to rewrite becomes a
    DETECTOR and is not deleted. Answering "was this doubling mine or the
    source's?" needs the declared notes, which is slice 3's input — so the
    detector is what slice 2 can honestly build, and it stops the loss on every
    document now rather than a slice later.

    Returns 0 always: no fix is made, so no fix is counted. What it FOUND is in
    ``DOUBLE_PUNCTUATION_FOUND``, a module-level list the caller reads, because
    a return value journalled as a fix count must not carry a detection.
    """
    found = DOUBLE_PUNCTUATION_FOUND
    del found[:]
    # Anchored on the same four patterns the rewrite used, so the detector's
    # population is EXACTLY what the pass would have changed — a detector built
    # from a different rule would report a different document.
    doubles = (('::', 'double colon'),
               (',,', 'double comma'),
               (';;', 'double semicolon'))
    period_re = re.compile(r'\.\.(?!\.)')
    # SLICE 4: each finding carries its PARAGRAPH INDEX, the journal's own, so it can be
    # located by whatever reads `detections`. The list is KEPT so the proxies stay alive --
    # see journal_flat_paragraph_map for why an id() of a freed proxy is not an identity.
    paras = list(root.iter(f'{{{W}}}p'))
    p_index = {id(x): i for i, x in enumerate(paras)}
    for t in root.iter(f'{{{W}}}t'):
        if t.text is None:
            continue
        own = _own_paragraph(t)
        para = p_index.get(id(own)) if own is not None else None
        for mark, label in doubles:
            n = t.text.count(mark)
            if n:
                found.append({'mark': label, 'count': n, 'para': para})
        n = len(period_re.findall(t.text))
        if n:
            found.append({'mark': 'double period', 'count': n, 'para': para})
    return 0

# === LEXICON-SANCTIONED RENDERINGS ===
#
# B5, B6(a) AND F29 ARE ONE DEFECT THREE TIMES, AND THIS BLOCK IS THE ONE MECHANISM FOR ALL
# OF THEM. A mandatory rewrite in this script overwrote a string that a LEXICON in this skill
# tells the operator to write: `Annex`, which the reference lexicon's Attachments row offers
# as a free choice against `Schedule`; a section heading that an Italian sub-lexicon
# instructs verbatim; `registration and publicity`, which the finance reference names as the
# CORRECT term. Each time, the operator followed the lexicon, this pass overrode them, and the
# post-strip drift gate then blocked with an error naming neither cause.
#
# THE CONDITION THESE PASSES ALWAYS ASSUMED, NOW TESTED: does a lexicon present this string
# as a correct rendering? A match lying inside a sanctioned span is LEFT EXACTLY AS WRITTEN
# and reported (decision 2c revised). The span is read over the WHOLE PARAGRAPH rather than
# the one w:t, so a lexicon-listed name split across two runs is still seen as a name.
#
# AND "DID THE OPERATOR DECLARE IT?" IS ANSWERED FROM THE NOTES -- AND IT CANNOT, BY
# CONSTRUCTION, TURN A KEPT MATCH INTO A REWRITE. A paragraph the notes find is one whose
# declared English equals its own text, so a sanctioned match in it IS the operator's; a
# paragraph they do not find is undecidable, and under 2c an undecidable case changes
# nothing. So the notes decide what the REPORT says -- declared, the source's own wording, or
# undecidable -- and never what happens to the text. Said here so that nobody later reads
# the classification as a second gate and "tightens" it into one.
#
# THE TABLE IS DECLARED, NOT PARSED FROM THE LEXICONS AT RUNTIME (Wouter, 2026-09-23), AND
# THE LEXICON STAYS THE AUTHORITY ANYWAY. Every entry cites the row that sanctions it, and
# tests/test_lexicon_choice.py reads every lexicon in both trees and goes RED on a rewritten
# string a lexicon sanctions that this table does not cover, or on a citation that no longer
# says what its entry claims. A Markdown parse inside the shipped pipeline would be a
# heuristic in the one place where a wrong answer is silent.
#
# WHAT IS DELIBERATELY NOT HERE: a string the REFERENCE lexicon lists under Avoid, even where
# a sub-lexicon offers it -- `credit line`, `election of domicile`. Three authorities agree
# with the rewrite there (the reference's Avoid column, this script's table and
# quality_check's violation list); a sub-lexicon contradicting its own reference is a defect
# in the lexicons, and not a reason for this script to stop.
#
# Each entry: (label, pattern matched case-insensitively, lexicon file relative to the skill
# root, a verbatim FRAGMENT that locates the row sanctioning it). The test reads the whole
# line the fragment locates and checks that the pattern still matches there and still shields
# a rewrite rule; the fragment itself need not contain the name. That is deliberate, and it
# was measured before it was chosen: this slice's first version quoted the three names in
# full, and the pre-commit gate's publication check -- whose shape for a personal name is
# three capitalised words in a row -- read a benchmark, a regulation and a statute as three
# people. The control was right about the shape and wrong about these strings; the answer was
# to stop writing a person-shaped string where nothing needs one, not to loosen a
# confidentiality check. The labels are lowercase for the same reason.
LEXICON_SANCTIONED = (
    ('Annex', r'\bAnnex(?:es)?\b',
     'references/general-legal.md',
     'Schedule (UK) or Annex (EU/international)'),
    ('banking transparency', r'\bbanking\s+transparency\b',
     'sub-lexicons/italian-finance-banking.md',
     '| TRASPARENZA BANCARIA | BANKING TRANSPARENCY |'),
    ('registration and publicity', r'\bregistration\s+and\s+publicity\b',
     'references/finance-banking.md',
     '| registration and publicity | The process of recording security interests'),
    ('SOFR, the overnight financing benchmark', r'\bSecured\s+Overnight\s+Financing\s+Rate\b',
     'references/trading-capital-markets.md',
     '| SOFR |'),
    ('SFTR, the securities financing regulation',
     r'\bSecurities\s+Financing\s+Transactions\s+Regulation\b',
     'sub-lexicons/french-finance-banking.md',
     '| règlement SFTR |'),
    ('the anti-terrorism financing act', r'\bAnti-Terrorism\s+Financing\s+Act\b',
     'sub-lexicons/dutch-general-legal.md',
     '(Wwft) |'),
)
_LEXICON_SANCTIONED_RE = tuple(re.compile(pat, re.IGNORECASE)
                               for _label, pat, _file, _quote in LEXICON_SANCTIONED)

# What the two passes below LEFT ALONE, for the detector line: one dict per kept match,
# {'pass', 'entry' (index into LEXICON_SANCTIONED), 'reason'}. Each pass clears only its own
# records, so running one pass on its own never erases the other's.
LEXICON_CHOICE_KEPT = []


def _own_paragraph(el):
    """Nearest ancestor w:p -- the reading half's own grouping, so a nested paragraph's
    text is never read as its outer paragraph's."""
    a = el.getparent()
    while a is not None and a.tag != f'{{{W}}}p':
        a = a.getparent()
    return a


def _paragraph_context(t):
    """A callable returning (prefix, suffix): the text of the rest of t's own paragraph on
    either side of it. Computed at most once per element, and only when a rule matches."""
    cache = []

    def get():
        if not cache:
            p = _own_paragraph(t)
            if p is None:
                cache.append(('', ''))
            else:
                own = [x for x in p.iter(f'{{{W}}}t') if _own_paragraph(x) is p]
                i = next((k for k, x in enumerate(own) if x is t), None)
                if i is None:
                    cache.append(('', ''))
                else:
                    cache.append((''.join(x.text or '' for x in own[:i]),
                                  ''.join(x.text or '' for x in own[i + 1:])))
        return cache[0]
    return get


def _sub_unless_sanctioned(rx, render, text, context, kept):
    """`rx.sub(render, text)`, except that a match overlapping a LEXICON_SANCTIONED span --
    read over the whole paragraph -- is left exactly as written and its entry index
    appended to `kept`. Every other match is replaced exactly as re.sub would replace it:
    same matches, same order, same replacement."""
    out, last, spans, prefix = [], 0, None, ''
    for m in rx.finditer(text):
        if spans is None:
            prefix, suffix = context()
            whole = prefix + text + suffix
            spans = [(s.start(), s.end(), i)
                     for i, crx in enumerate(_LEXICON_SANCTIONED_RE)
                     for s in crx.finditer(whole)]
        a, b = len(prefix) + m.start(), len(prefix) + m.end()
        hit = next((i for s0, s1, i in spans if s0 < b and a < s1), None)
        if hit is not None:
            kept.append(hit)
            continue
        out.append(text[last:m.start()])
        out.append(render(m))
        last = m.end()
    if not out:
        return text
    out.append(text[last:])
    return ''.join(out)


def _record_kept(pass_name, t, kept, notes):
    """Say WHY each kept match was kept. This changes nothing about the text -- see the
    block comment above -- it decides what the detector line tells the operator."""
    if not kept:
        return
    if notes is None:
        reason = 'no notes'
    else:
        p = _own_paragraph(t)
        full = ''.join(x.text or '' for x in p.iter(f'{{{W}}}t')) if p is not None else ''
        entry = notes.get(_notes_norm(full))
        if entry is None:
            reason = 'no paragraph match'
        elif _notes_norm(entry.get('text')) == _notes_norm(entry.get('en')):
            reason = 'source wording'
        else:
            reason = 'declared'
    # SLICE 4: the paragraph index, the journal's own, so `detections` can locate the kept
    # match. Found by IDENTITY while `own` holds the proxy alive, and only on this path --
    # a kept match is rare, so the walk costs nothing on a document that has none.
    own = _own_paragraph(t)
    para = None
    if own is not None:
        root = t.getroottree().getroot()
        para = next((i for i, x in enumerate(root.iter(f'{{{W}}}p')) if x is own), None)
    for idx in kept:
        LEXICON_CHOICE_KEPT.append({'pass': pass_name, 'entry': idx, 'reason': reason,
                                    'para': para})
# === LEXICON-SANCTIONED RENDERINGS ENDS ===


def fix_terminology(root, notes=None):
    """Apply terminology replacements to all w:t elements -- EXCEPT where a lexicon in this
    skill sanctions the string being replaced (B5, B6(a), F29; see LEXICON_SANCTIONED).

    Every other replacement is applied exactly as before: the literal rules in table order,
    then the regex rules, each match replaced as re.sub would replace it."""
    fixes = 0
    LEXICON_CHOICE_KEPT[:] = [k for k in LEXICON_CHOICE_KEPT if k['pass'] != 'terminology']
    rules = ([(re.compile(old) if is_regex else re.compile(re.escape(old)),
               (lambda m, n=new: m.expand(n)) if is_regex else (lambda m, n=new: n))
              for old, new, is_regex in TERM_REPLACEMENTS]
             + [(re.compile(pattern), lambda m, r=replacement: m.expand(r))
                for pattern, replacement in TERM_REGEX_REPLACEMENTS])
    for t in root.iter(f'{{{W}}}t'):
        if t.text is None:
            continue
        orig = t.text
        context = _paragraph_context(t)
        kept = []
        for rx, render in rules:
            t.text = _sub_unless_sanctioned(rx, render, t.text, context, kept)
        _record_kept('terminology', t, kept, notes)
        if t.text != orig:
            fixes += 1
    return fixes

def fix_uk_spelling(root):
    """Replace US spellings with UK equivalents (UK is the hardcoded default variant)."""
    fixes = 0
    for t in root.iter(f'{{{W}}}t'):
        if t.text is None:
            continue
        orig = t.text
        for pattern, replacement in UK_SPELLING:
            t.text = re.sub(pattern, replacement, t.text)
        if t.text != orig:
            fixes += 1
    return fixes

# US_SPELLING is the inverse mapping, used ONLY when the user has explicitly
# requested US English in their original prompt. UK is the hardcoded default;
# never fall back to this list on ambiguity.
US_SPELLING = [
    (r'\bauthorise\b', 'authorize'),
    (r'\bauthorised\b', 'authorized'),
    (r'\bAuthorised\b', 'Authorized'),
    (r'\bAUTHORISATION\b', 'AUTHORIZATION'),
    (r'\bAuthorisation\b', 'Authorization'),
    (r'\bauthorisation\b', 'authorization'),
    (r'\brecognise\b', 'recognize'),
    (r'\brecognised\b', 'recognized'),
    (r'\borganise\b', 'organize'),
    (r'\borganised\b', 'organized'),
    (r'\borganisation\b', 'organization'),
    (r'\bfavour\b', 'favor'),
    (r'\bfavoured\b', 'favored'),
    (r'\bfavourable\b', 'favorable'),
    (r'\bhonour\b', 'honor'),
    (r'\bhonoured\b', 'honored'),
    (r'\bcentre\b', 'center'),
    (r'\bdefence\b', 'defense'),
    (r'\boffence\b', 'offense'),
    (r'\bfulfil\b', 'fulfill'),
    (r'\bfulfilment\b', 'fulfillment'),
    (r'\bjudgement\b', 'judgment'),
    (r'\bjudgements\b', 'judgments'),
    (r'\bJudgement\b', 'Judgment'),
    (r'\backnowledgement\b', 'acknowledgment'),
    (r'\backnowledgements\b', 'acknowledgments'),
    (r'\butilise\b', 'utilize'),
    (r'\butilised\b', 'utilized'),
    (r'\butilisation\b', 'utilization'),
    (r'\bcancelled\b', 'canceled'),
    (r'\bcancelling\b', 'canceling'),
    (r'\blabour\b', 'labor'),
    (r'\banalyse\b', 'analyze'),
    (r'\banalysed\b', 'analyzed'),
]

def fix_us_spelling(root):
    """Replace UK spellings with US equivalents. Only invoked when --variant us
    is explicitly passed. Do NOT call this on ambiguity — UK is the default."""
    fixes = 0
    for t in root.iter(f'{{{W}}}t'):
        if t.text is None:
            continue
        orig = t.text
        for pattern, replacement in US_SPELLING:
            t.text = re.sub(pattern, replacement, t.text)
        if t.text != orig:
            fixes += 1
    return fixes

def fix_annex(root, notes=None):
    """Replace 'Annex' with 'Schedule' except in legislation references -- and, since branch
    10 slice 3b, except where a lexicon sanctions it, which for this pass is EVERY match.

    F29 and B6(a): the reference lexicon's Attachments row reads "Schedule (UK) or Annex
    (EU/international)" and says to match the source document's convention, and five
    sub-lexicons repeat the choice. The operator is the one who can see the source; this pass
    cannot. So every match lies inside the `Annex` entry of LEXICON_SANCTIONED, the pass
    rewrites nothing, and it is kept as a DETECTOR rather than deleted (decision 2c revised):
    what it would have rewritten is exactly what the detector line reports.

    The shape of the loop is unchanged ON PURPOSE, including the case-sensitive 'Annex'
    pre-check that means the all-caps rule only ever ran beside a mixed-case 'Annex' in the
    same element. Keeping it makes "kept now" equal "rewritten before", match for match,
    which is what lets a before-and-after run explain every moved byte by this row."""
    fixes = 0
    LEXICON_CHOICE_KEPT[:] = [k for k in LEXICON_CHOICE_KEPT
                              if k['pass'] != 'annex_to_schedule']
    rules = ((re.compile(r'\bAnnex\b'), lambda m: 'Schedule'),
             (re.compile(r'\bANNEX\b'), lambda m: 'SCHEDULE'),
             (re.compile(r'\bAnnexes\b'), lambda m: 'Schedules'))
    for t in root.iter(f'{{{W}}}t'):
        if t.text is None or 'Annex' not in t.text:
            continue
        if any(kw in t.text for kw in ANNEX_EXCLUDE):
            continue
        orig = t.text
        context = _paragraph_context(t)
        kept = []
        for rx, render in rules:
            t.text = _sub_unless_sanctioned(rx, render, t.text, context, kept)
        _record_kept('annex_to_schedule', t, kept, notes)
        if t.text != orig:
            fixes += 1
    return fixes

def fix_article_to_clause(root):
    """Replace 'Article X' with 'Clause X' for INTERNAL cross-references
    only. EXTERNAL references to legislation, codes, regulatory acts,
    or other authoritative sources keep 'Article'.

    per-match decision via the structural detector
    ``_classify_article_ref`` (no hardcoded keyword list). The
    detector looks at what follows "Article N" within the same
    sentence:

      * " of <Capitalized Proper Noun>" → external (keep Article)
      * " of this/the present/the said X" → internal (rewrite to Clause)
      * " of <internal anchor>" (Schedule, Annex, ...) → internal
      * bare "Article N." or "(Article N)" → INDETERMINATE: keep Article
        and REPORT. B2 — this used to rewrite, and on D05 it turned a
        statutory citation into an internal "Section N" that does not
        exist in the deed. See `_classify_article_ref`.

    The decision is per-match, so a single paragraph can contain a
    mix of internal and external references and each will be handled
    correctly.

    Returns the fix count. The indeterminate references are reported through
    ``ARTICLE_UNDECIDED``, a module-level list the caller reads after the pass,
    because this function's return value is journalled as a fix COUNT and a
    reference left alone is not a fix.
    """
    fixes = 0
    # Reset per run: a detector report that accumulates across invocations
    # would report the previous document's references as this one's.
    undecided = ARTICLE_UNDECIDED
    del undecided[:]
    article_re = re.compile(r'\bArticles?\s+\d[\d.:]*(?:-[A-Za-z]{1,15})*')
    # SLICE 4: enumerated so a reference left alone carries its paragraph index -- the
    # journal's own, root.iter over w:p being the journal's enumeration.
    for p_i, p in enumerate(root.iter(f'{{{W}}}p')):
        # Build the joined paragraph text once for context lookup.
        t_elems = list(p.iter(f'{{{W}}}t'))
        joined = ''.join((t.text or '') for t in t_elems)
        if not article_re.search(joined):
            continue
        # Find absolute start positions in `joined` of all "Article N"
        # matches that must KEEP Article. TWO reasons now reach that set and
        # they are counted apart: the reference is decided EXTERNAL, or it is
        # INDETERMINATE and B2 says report rather than guess. Folding the two
        # together would make the indeterminate ones invisible, which is the
        # state this fix exists to leave.
        external_starts = set()
        for m in article_re.finditer(joined):
            verdict = _classify_article_ref(joined, m.end())
            if verdict == ARTICLE_EXTERNAL:
                external_starts.add(m.start())
            elif verdict == ARTICLE_INDETERMINATE:
                external_starts.add(m.start())
                undecided.append({'para': p_i})
        # Walk t_elems and rewrite per-element. Only rewrite matches
        # whose absolute start position is NOT in external_starts.
        running = 0
        local_re = re.compile(r'\b(Articles?)\s+(\d[\d.:]*(?:-[A-Za-z]{1,15})*)')
        for t in t_elems:
            txt = t.text or ''
            if not txt:
                running += len(txt)
                continue
            new_pieces = []
            last = 0
            for m in local_re.finditer(txt):
                abs_start = running + m.start()
                new_pieces.append(txt[last:m.start()])
                if abs_start in external_starts:
                    # External — keep Article(s)
                    new_pieces.append(m.group(0))
                else:
                    # Internal — rewrite Article→Clause / Articles→Clauses
                    word = ('Clauses' if m.group(1) == 'Articles'
                            else 'Clause')
                    new_pieces.append(f'{word} {m.group(2)}')
                last = m.end()
            new_pieces.append(txt[last:])
            new_txt = ''.join(new_pieces)
            if new_txt != txt:
                t.text = new_txt
                fixes += 1
            running += len(txt)
    return fixes

def fix_duplicates(root):
    """Fix duplicate words both within elements and across element boundaries."""
    fixes = 0

    # Within elements — catch any word duplicated (not just a fixed list)
    for t in root.iter(f'{{{W}}}t'):
        if t.text is None:
            continue
        orig = t.text
        # Generic: any word of 3+ chars duplicated with space
        t.text = re.sub(r'\b(\w{3,})\s+\1\b', r'\1', t.text, flags=re.IGNORECASE)
        if t.text != orig:
            fixes += 1

    # Across element boundaries
    for p in root.iter(f'{{{W}}}p'):
        t_elems = [(t, t.text) for t in p.iter(f'{{{W}}}t') if t.text and t.text.strip()]
        for i in range(1, len(t_elems)):
            prev_elem, prev = t_elems[i-1]
            curr_elem, curr = t_elems[i]
            prev_words = prev.split()
            curr_words = curr.split()
            if prev_words and curr_words:
                pw = re.sub(r'[,;:."\'\)\]]+$', '', prev_words[-1])
                cw = re.sub(r'^["\'\(\[]+', '', curr_words[0])
                if pw and cw and pw.lower() == cw.lower() and len(pw) > 2 and pw.isalpha():
                    # Remove the duplicate from the current element
                    curr_elem.text = re.sub(r'^\s*' + re.escape(curr_words[0]) + r'\s*', ' ', curr)
                    fixes += 1

    return fixes

def fix_quotes(root):
    """Fix missing closing quotes on defined terms before definition verbs.

    Finds patterns like:
      "Security Period has the meaning...
    and adds the missing closing quote:
      "Security Period" has the meaning...
    """
    fixes = 0
    OPEN_Q = '\u201c'
    CLOSE_Q = '\u201d'

    for p in root.iter(f'{{{W}}}p'):
        full = ''.join(t.text or '' for t in p.iter(f'{{{W}}}t'))

        # Only process paragraphs with definition verbs
        if not any(v in full for v in ['means', 'shall mean', 'has the meaning', 'indicates']):
            continue

        # Work element by element to find open-quote elements that need closing
        t_elems = list(p.iter(f'{{{W}}}t'))
        for i, t in enumerate(t_elems):
            if t.text is None:
                continue

            # Check for pattern: element ends with term text and next element starts
            # with "means"/"shall mean"/"has the meaning" but no close quote between
            if t.text.rstrip().endswith(CLOSE_Q) or t.text.rstrip().endswith('"'):
                continue  # Already has closing quote

            # Look ahead: does next text element start with a definition verb?
            for j in range(i + 1, min(i + 3, len(t_elems))):
                if t_elems[j].text is None:
                    continue
                next_text = t_elems[j].text.lstrip()
                if re.match(r'^(means|shall mean|has the meaning|indicates)\b', next_text):
                    # Check if there's an open quote earlier that's unmatched
                    preceding = ''.join(te.text or '' for te in t_elems[:i+1])
                    open_count = preceding.count(OPEN_Q) + preceding.count('\u201e')
                    close_count = preceding.count(CLOSE_Q)
                    if open_count > close_count:
                        # Add closing quote to the end of this element
                        t.text = t.text.rstrip() + CLOSE_Q
                        fixes += 1
                break  # Only check the next non-empty element

    return fixes

def fix_definition_line_breaks(root):
    """Remove unwanted line breaks (w:br) within definition paragraphs.

    In Italian documents, a definition often has the term on one line and the meaning
    on the next. After translation, this creates an ugly break:
        "Potential Event of Default"
        means any event which...

    This should be a single flowing line:
        "Potential Event of Default" means any event which...

    We detect definition paragraphs (containing "means"/"shall mean"/"has the meaning"
    plus a quote character) and remove any w:br elements found within them.
    """
    fixes = 0
    for p in root.iter(f'{{{W}}}p'):
        full = ''.join(t.text or '' for t in p.iter(f'{{{W}}}t'))

        # Only process definition paragraphs
        if not any(v in full for v in ['means', 'shall mean', 'has the meaning', 'indicates']):
            continue
        if not any(q in full for q in ['\u201c', '"', '\u201e']):
            continue

        # Find and remove w:br elements in runs
        for r in p.iter(f'{{{W}}}r'):
            br = r.find(f'{{{W}}}br')
            if br is not None:
                r.remove(br)
                fixes += 1

    return fixes

# === THE DECLARED NOTES — slice 3a's input, and the first DECISION taken from them ===
#
# `post_process` has located `paragraphs.json` since rev18, but only ever to hand the
# PATH to a subprocess (the post-strip drift gate). This is the first place the stage
# READS the operator's notes to decide what to do, which is the seam branch 10's slices
# were cut on: slice 2's passes needed no new input, these need the declaration.
#
# THE JOIN IS BY TEXT AND BY THE DECLARED OFFSETS — NEVER BY INDEX. One real document
# produced 577 JSON entries for 564 XML paragraphs, a 6-13 position drift that under
# index-matching corrupted styles, numbering and indentation and left the last ~60
# paragraphs in the source language. Measured on the 13 frozen workdirs: the paragraph
# join resolves 37 of 37 of the runs this pass touches, and the offset join covers all
# 37 with nothing indeterminate, so nothing here needs a positional fallback.
#
# AND THE SOURCE ARM IS EXACT EQUALITY, NOT CONTAINMENT, BECAUSE `runs` HOLDS
# SOURCE-LANGUAGE TEXT. An English run's text cannot match a source run's except where
# the term was not translated. A containment join was measured first and looked better --
# it kept 34 rather than 28, reproducing a figure register row B1 records from a wholly
# separate measurement -- and that agreement was a COINCIDENCE, not corroboration: the
# same join returned 7 verdicts that could only be accidental. Exact equality reaches the
# case the row actually names, a deliberately RETAINED source-language term, and reaches
# nothing by luck.
#
# One {'reason', 'para'} per run the pass left alone -- a bare reason string until slice 4,
# which added the paragraph index so the journal's `detections` can locate each one.
DECLARED_ITALIC_UNDECIDED = []


def _notes_norm(s):
    """Whitespace-folded text, for the PARAGRAPH-level join only.

    Deliberately NOT used to compare against `en_runs` offsets: those index the raw
    `en` string, so folding before slicing would shift every boundary.
    """
    return ' '.join((s or '').split())


def load_declared_notes(paragraphs_json_path):
    """Read paragraphs.json into {folded `en` text: entry}, or None if unreadable.

    Returns None -- never an empty dict -- when there are no notes to consult, because
    the two mean opposite things to the caller: None is "the condition cannot be
    determined, change nothing", while an empty dict would read as "nothing is declared,
    strip everything". That distinction is the whole of decision 2c revised here.
    """
    if not paragraphs_json_path or not os.path.isfile(paragraphs_json_path):
        return None
    try:
        with open(paragraphs_json_path, 'r', encoding='utf-8') as f:
            entries = json.load(f)
    except (OSError, ValueError):
        return None
    if not isinstance(entries, list):
        return None
    by_en = {}
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        if entry.get('en'):
            by_en.setdefault(_notes_norm(entry['en']), entry)
    return by_en or None


def _declared_italic(entry, run_text):
    """Do the operator's notes ACCOUNT for this run being italic?

    True  -- declared italic, or carried unchanged from an italic source run: KEEP.
    False -- the notes cover this run and neither side calls it italic: STRIP.
    None  -- nothing in the notes covers this run at all: INDETERMINATE, change nothing.

    Two arms, and they are asymmetric on purpose.

    `en_runs` is the operator's explicit statement about the ENGLISH, and its spans are
    offsets into `en`, so it is read in its own coordinates: locate the run's raw text
    inside `en` and consult every segment whose span overlaps it.

    `runs` is the SOURCE, in the source language, so it is matched by EXACT equality of
    the folded text. That succeeds only where the term was never translated -- a retained
    source-language title, a party or facility name, a statutory citation -- which is
    exactly the sub-case this function's own docstring carve-out claims to protect and
    which register row B1's third instance, D03B, is entirely about.
    """
    covered = False

    en = entry.get('en') or ''
    segments = entry.get('en_runs') or []
    if run_text and segments:
        start = en.find(run_text)
        while start != -1:
            end = start + len(run_text)
            for seg in segments:
                if not isinstance(seg, dict):
                    continue
                try:
                    a, b = int(seg['start']), int(seg['end'])
                except (KeyError, TypeError, ValueError):
                    continue
                if a < end and start < b:
                    covered = True
                    if seg.get('italic') is True:
                        return True
            start = en.find(run_text, start + 1)

    folded = _notes_norm(run_text)
    if folded:
        for seg in (entry.get('runs') or []):
            if not isinstance(seg, dict):
                continue
            if _notes_norm(seg.get('text')) == folded:
                covered = True
                if seg.get('italic') is True:
                    return True

    return False if covered else None


def fix_spurious_italic_runs(root, notes=None):
    """Remove italic from runs in body paragraphs where italic is not appropriate.

    In Italian legal documents, defined terms are sometimes italic in the source, and
    after translation the italic sticks to runs that should be normal weight in English.

    Rules:
    - In definition paragraphs: only the cross-reference heading in parentheses should
      be italic (e.g., "(Preservation of the Security)"). The defined term should be
      bold, the meaning should be normal.
    - In body paragraphs: italic is appropriate only for cross-reference headings in
      parentheses and for Latin terms. All other text should be normal.
    - Headings: italic is OK if the paragraph style says so (inherited from pPr).

    This function removes italic from runs that contain substantive English text (more
    than 3 words, not in parentheses, not a Latin term) in non-heading paragraphs.

    **B1 — THE RULE ABOVE IS NOT A TEST OF WHETHER THE ITALIC WAS THE OPERATOR'S, AND
    THAT IS THE DEFECT.** A run of more than two unparenthesised words that is not a
    listed Latin term is *unsatisfiable by faithful work*: an italicised cross-reference
    title cannot be written so as to pass it. On one real document the pass destroyed
    an entire drafting convention document-wide -- roughly twenty italicised
    cross-reference titles, six defined facility terms, a statute name, two notice-block
    address labels -- and the operator had declared every one of them correctly. Three
    of those classes were named unprompted, with matching counts, by a reading lawyer.

    Under decision 2c revised the pass now tests the condition it always assumed: the
    word-count rule decides only whether a run is a CANDIDATE, and `_declared_italic`
    then decides whether the notes account for it. Where they do, the italic stays.
    Where they cover the run and account for nothing, it goes, exactly as before. Where
    nothing covers it -- and where there are no notes at all -- the pass CHANGES NOTHING
    and says so through ``DECLARED_ITALIC_UNDECIDED``.

    `notes` is the mapping from `load_declared_notes`, or None. **None is not "strip
    nothing is declared": it is "this cannot be decided", and the pass reports instead
    of guessing.** Measured across the 13 frozen workdirs: of the 37 runs this pass
    strips today, 28 are accounted for by the notes and 9 are not, with none left
    undecided.
    """
    fixes = 0
    del DECLARED_ITALIC_UNDECIDED[:]
    latin_terms = {
        'inter alia', 'mutatis mutandis', 'pari passu', 'pro rata', 'bona fide',
        'vis-à-vis', 'de facto', 'de jure', 'prima facie', 'sui generis', 'et seq.',
        'ad hoc', 'ab initio', 'ultra vires', 'per se', 'in rem',
    }

    for p_i, p in enumerate(root.iter(f'{{{W}}}p')):
        full = ''.join(t.text or '' for t in p.iter(f'{{{W}}}t'))
        if not full.strip():
            continue

        # Skip headings (all caps or very short)
        if full.strip() == full.strip().upper() and len(full.split()) < 10:
            continue

        # Check if paragraph-level properties set italic (then it's intentional)
        # ST_OnOff falsy set extended to include 'off'
        # (case-insensitive) per ECMA-376.
        _ST_ONOFF_FALSE_PP = {'false', '0', 'off'}

        def _is_off(val):
            return val is not None and val.strip().lower() in _ST_ONOFF_FALSE_PP

        ppr = p.find(f'{{{W}}}pPr')
        if ppr is not None:
            p_rpr = ppr.find(f'{{{W}}}rPr')
            if p_rpr is not None:
                i_elem = p_rpr.find(f'{{{W}}}i')
                if i_elem is not None:
                    val = i_elem.get(f'{{{W}}}val')
                    if not _is_off(val):
                        continue  # Paragraph style is italic — leave it

        for r in p.iter(f'{{{W}}}r'):
            rpr = r.find(f'{{{W}}}rPr')
            if rpr is None:
                continue
            i_elem = rpr.find(f'{{{W}}}i')
            if i_elem is None:
                continue
            val = i_elem.get(f'{{{W}}}val')
            if _is_off(val):
                continue

            t = r.find(f'{{{W}}}t')
            if t is None or not t.text:
                continue

            text = t.text.strip()
            # Keep italic if: in parentheses, a Latin term, a short cross-ref heading,
            # or a numbering label (e.g., "1.1", "(a)")
            if not text:
                continue
            if text.startswith('(') and text.endswith(')'):
                continue  # Cross-ref heading in parentheses
            if any(lt in text.lower() for lt in latin_terms):
                continue
            if len(text) <= 5 and re.match(r'^[\d\.\(\)a-z]+$', text):
                continue  # Numbering label like "1.1" or "(a)"

            # If it's substantive text (more than 2 words) and italic, the run is a
            # CANDIDATE. Whether it is actually spurious is decided by the notes.
            if len(text.split()) > 2:
                if notes is None:
                    # No declaration to consult. B1: the pass cannot tell an italic it
                    # introduced from one the operator authored, and guessing destroyed
                    # a drafting convention on a real document. Report, change nothing.
                    DECLARED_ITALIC_UNDECIDED.append({'reason': 'no notes',
                                                      'para': p_i})
                    continue
                entry = notes.get(_notes_norm(full))
                if entry is None:
                    DECLARED_ITALIC_UNDECIDED.append({'reason': 'no paragraph match',
                                                      'para': p_i})
                    continue
                verdict = _declared_italic(entry, t.text)
                if verdict is True:
                    continue          # declared, or carried from an italic source run
                if verdict is None:
                    DECLARED_ITALIC_UNDECIDED.append({'reason': 'run not covered',
                                                      'para': p_i})
                    continue
                rpr.remove(i_elem)
                fixes += 1

    return fixes

# B7's detector output: one record per schedule-shaped heading this run FOUND and how it
# starts its page -- {'para', 'starts_new_page', 'device', 'styled'}. Reset per run, and read
# by the caller for the detector line and the journal's `detections`.
SCHEDULE_HEADINGS_FOUND = []

# THE PAGE-START DEVICES VISIBLE IN document.xml, AND THE ONE THIS STAGE CANNOT SEE. The codes
# are slice 4's probe's, so a record here reads directly against that measurement.
#   pBB     the heading's own w:pageBreakBefore (not val=0/false/off)
#   brLead  a w:br type=page inside the heading BEFORE its first text
#   brTail  a w:br type=page after the last text of the previous text-bearing paragraph
#   brEmp   a w:br type=page in an EMPTY paragraph between the two
#   pBBEmp  w:pageBreakBefore on such an empty paragraph
#   sect    a section break (nextPage, oddPage, evenPage -- or no type, which MEANS
#           nextPage) ending a paragraph between the previous text and the heading
# NOT VISIBLE HERE: a pageBreakBefore carried by the heading's STYLE. Styles live in
# styles.xml, a part this stage is never handed, so a STYLED heading with no visible device is
# reported as UNKNOWN -- never as "does not start a new page", which would be a guess. An
# UNSTYLED heading takes the document's default paragraph style, and a default style carrying
# pageBreakBefore would start EVERY paragraph on its own page; that is assumed away, and said.
_PAGE_BREAK_OFF = {'0', 'false', 'off'}


def _page_start_devices(paras, k):
    """The device codes by which paragraph k starts on a new page, from document.xml alone.
    Walks back over at most twelve EMPTY paragraphs to the previous text or section break."""
    dev = set()

    def _pbb_on(ppr):
        pb = ppr.find(f'{{{W}}}pageBreakBefore') if ppr is not None else None
        return pb is not None and (
            (pb.get(f'{{{W}}}val', 'true') or 'true').lower() not in _PAGE_BREAK_OFF)

    def _page_br(el):
        return el.tag == f'{{{W}}}br' and el.get(f'{{{W}}}type') == 'page'

    p = paras[k]
    if _pbb_on(p.find(f'{{{W}}}pPr')):
        dev.add('pBB')
    for el in p.iter():
        if el.tag == f'{{{W}}}t' and (el.text or '').strip():
            break
        if _page_br(el):
            dev.add('brLead')
    j, walked = k - 1, 0
    while j >= 0 and walked < 12:
        q = paras[j]
        qppr = q.find(f'{{{W}}}pPr')
        sp = qppr.find(f'{{{W}}}sectPr') if qppr is not None else None
        if sp is not None:
            ty = sp.find(f'{{{W}}}type')
            tv = ty.get(f'{{{W}}}val') if ty is not None else 'nextPage'
            if tv in ('nextPage', 'oddPage', 'evenPage'):
                dev.add('sect')
            break
        texts = [el for el in q.iter(f'{{{W}}}t') if (el.text or '').strip()]
        if texts:
            after = False
            for el in q.iter():
                if el is texts[-1]:
                    after = True
                elif after and _page_br(el):
                    dev.add('brTail')
            break
        if any(_page_br(el) for el in q.iter()):
            dev.add('brEmp')
        if _pbb_on(qppr):
            dev.add('pBBEmp')
        j -= 1
        walked += 1
    return dev


def fix_schedule_page_breaks(root):
    """Find Schedule/Annex headings and REPORT how each starts its page. INSERTS NOTHING.

    B7, BRANCH 10 SLICE 4. Until slice 4 this pass gave every such heading a
    w:pageBreakBefore, on two premises its docstring stated: that each schedule starts on a
    new page, and that after translation these page breaks may be lost. Measured on all 13
    frozen workdirs rebuilt through apply, in both trees, it fired 11 times and was needed on
    none of them:
      3  the source does NOT start the heading on a new page, and the imposed break made a
         blank page or split a listing from its own heading -- B7's own three documents;
      4  the source ALREADY starts it on a new page, by a page break at the head of the
         heading or in an empty paragraph before it, and the added break DOUBLED it;
      4  the heading's STYLE already carries pageBreakBefore, so the added one was redundant.
    And on all 11 the document this pass receives carries the same page-start device as the
    source, because apply copies every one of them across. So both premises are false: the
    convention is the house's rather than the source's, and the breaks are not lost.

    THE CANDIDACY RULE IS UNCHANGED, so what this reports is exactly what it used to act on:
    the heading pattern, the length cap, the label-token check and the style skip-list below.
    What changed is the action. Each candidate is recorded in SCHEDULE_HEADINGS_FOUND with how
    it starts its page, and the document is left exactly as it arrived. Restoring a break apply
    LOST would be repairing apply from downstream; comparing the delivery against the original
    is the delivered-document check's work (branch 11). Neither is a guess for this stage.

    Returns 0, always: a detection is not a fix.
    """
    del SCHEDULE_HEADINGS_FOUND[:]
    schedule_pattern = re.compile(
        r'^\s*(SCHEDULE|Schedule|ANNEX|Annex|ALLEGATO|Allegato)\s+[\dA-Za-z]',
        re.IGNORECASE
    )

    # Styles that should NEVER receive schedule page breaks:
    # - TOC styles: these are table-of-contents entries
    # - Body-content styles: these are in-text references to schedules
    SKIP_STYLES = {
        'TOC1', 'TOC2', 'TOC3', 'TOC4', 'TOC5', 'TOC6', 'TOC7', 'TOC8', 'TOC9',
        'FWBL2', 'FWBL3', 'FWBL4', 'FWBL5',
        'FWBCont1', 'FWBCont2', 'FWBCont3',
        'Normal',
    }

    # KEPT as a list for the walk-back in _page_start_devices, and because a kept list keeps
    # the proxies alive -- see journal_flat_paragraph_map. The index is the journal's own.
    paras = list(root.iter(f'{{{W}}}p'))
    for k, p in enumerate(paras):
        full = ''.join(t.text or '' for t in p.iter(f'{{{W}}}t')).strip()
        if not full:
            continue

        if not schedule_pattern.match(full):
            continue

        # language-agnostic length cap. Schedule headings are short
        # labels — the longest legitimate heading observed in real legal
        # docs ("Schedule 4 — Form of Notice of Drawdown and Form of Notice
        # of Conversion", "SCHEDULE 7 — REPRESENTATIONS, WARRANTIES,
        # COVENANTS, AND OTHER UNDERTAKINGS") sits under ~90 chars; the
        # 120-char threshold gives generous headroom while still catching
        # body prose that begins with a schedule reference and continues
        # into a sentence ("Schedule G (Construction Budget) sets out the
        # schedule of costs of the works approved by the Parties..." is
        # 100+ chars on the first sentence alone). The cap is target-
        # language-only — it depends on English heading conventions, not
        # on source-language style names — so it works equally well on
        # Polish, Hungarian, Italian or any other source.
        if len(full) > 120:
            continue

        # label-token check. A real schedule heading's second
        # token is the schedule's label — "G", "5", "III", "1.A", "12" —
        # all-uppercase letters, digits, or roman numerals; never a
        # lowercase preposition. A clause heading whose English
        # rendering happens to start with the word "Schedule" has a
        # lowercase preposition or proper noun there (e.g. "Schedule
        # for Performance of the Works" — "for" is a lowercase
        # preposition, not a label). The  length cap doesn't
        # catch the short variant of this defect (the offending para
        # is 36 chars, well under 120). Strip trailing punctuation
        # from the label token before the lowercase check so dash- or
        # colon-suffixed labels ("G-", "5:", "III—") aren't false-
        # negatived. Leaves real headings untouched, eliminates the
        # "Schedule for X" / "Schedule of Y" / "Schedule by Z" body-
        # prose class.
        m_label = re.match(
            r'^\s*(?:SCHEDULE|ANNEX|ALLEGATO)\s+(\S+)',
            full, re.IGNORECASE)
        if m_label and any(
                c.islower()
                for c in m_label.group(1).rstrip(':,;.-—–')):
            continue

        # Check paragraph style — skip TOC entries and body-content references
        ppr = p.find(f'{{{W}}}pPr')
        style = None
        if ppr is not None:
            style_elem = ppr.find(f'{{{W}}}pStyle')
            if style_elem is not None:
                style = style_elem.get(f'{{{W}}}val', '')

        if style and (style in SKIP_STYLES or style.upper().startswith('TOC')):
            continue

        # THE ACTION, AND THE ONLY LINES OF THIS PASS THAT CHANGED. Where the old code
        # created a w:pPr and inserted w:pageBreakBefore, the candidate is now RECORDED.
        dev = _page_start_devices(paras, k)
        SCHEDULE_HEADINGS_FOUND.append({
            'para': k,
            'starts_new_page': True if dev else (None if style else False),
            'device': sorted(dev),
            'styled': bool(style),
        })

    return 0


def collect_detections():
    """The journal's `detections`: every detector list the passes filled, as one record per
    finding under JOURNAL_DETECTION_CONTRACT. Read AFTER every pass has run.

    THE REASONS ARE EACH PASS'S OWN VOCABULARY, NOT A NEW ONE. A consumer reading "no notes"
    here and "no notes" in a detector line on screen must be reading the same fact, or the
    two reports of one run will disagree about it.
    """
    out = []
    for d in DOUBLE_PUNCTUATION_FOUND:
        out.append({'pass': 'double_punctuation', 'reason': d['mark'],
                    'para': d.get('para'), 'count': d['count']})
    for a in ARTICLE_UNDECIDED:
        out.append({'pass': 'article_to_clause', 'reason': 'indeterminate',
                    'para': a.get('para'), 'count': 1})
    for it in DECLARED_ITALIC_UNDECIDED:
        out.append({'pass': 'spurious_italic', 'reason': it['reason'],
                    'para': it.get('para'), 'count': 1})
    for k in LEXICON_CHOICE_KEPT:
        out.append({'pass': k['pass'], 'reason': k['reason'], 'para': k.get('para'),
                    'count': 1, 'entry': k['entry']})
    for h in SCHEDULE_HEADINGS_FOUND:
        if h['starts_new_page']:
            reason = 'starts a new page'
        elif h['starts_new_page'] is False:
            reason = 'does not start a new page'
        else:
            reason = 'unknown: styled, and a style is not visible in document.xml'
        out.append({'pass': 'schedule_page_breaks', 'reason': reason, 'para': h['para'],
                    'count': 1, 'device': h['device']})
    return out

def extract_header(xml_text):
    """Extract XML declaration and root element opening tag from raw XML text."""
    m = re.match(r'(<\?xml[^?]*\?>\s*<w:document[^>]*>)', xml_text, re.DOTALL)
    return m.group(1) if m else None

def _xml_has_tracked_changes(xml_path):
    """Cheap check: does document.xml contain any <w:ins>, <w:del>, or
    <w:delText> elements? Used to gate the auto-invoke of
    strip_noop_tracked_changes.py at the end of post_process."""
    try:
        with open(xml_path, 'rb') as f:
            content = f.read()
    except OSError:
        return False
    return (b'<w:ins ' in content or b'<w:ins>' in content or
            b'<w:del ' in content or b'<w:del>' in content or
            b'<w:delText' in content)

def _run_strip_noop_subprocess(xml_path):
    """Auto-invoke strip_noop_tracked_changes.py as a subprocess.
    Mandatory for TC documents — refuses to leave post_process if the
    strip step fails."""
    import subprocess
    scripts_dir = os.path.dirname(os.path.abspath(__file__))
    print(f"\n{'=' * 60}\n[post_process] auto-running "
          f"strip_noop_tracked_changes.py (TC document)\n{'=' * 60}")
    result = subprocess.run(
        [sys.executable,
         os.path.join(scripts_dir, 'strip_noop_tracked_changes.py'),
         xml_path],
        capture_output=False)
    if result.returncode != 0:
        raise RuntimeError(
            f"strip_noop_tracked_changes.py returned exit code "
            f"{result.returncode}. post_process aborted; document may be "
            f"in an inconsistent state."
        )

def _autodetect_paragraphs_json(xml_path):
    """Rev18: locate the paragraphs.json that produced this document.xml.

    Convention from `skill-docs/06-postprocess-and-reorder.md`:
        ``python post_process.py <workdir>/final/word/document.xml ...``
    so paragraphs.json is at ``<workdir>/paragraphs.json``. Walk up two
    parents from the xml file (``word`` → ``final`` → ``workdir``) and
    look for ``paragraphs.json`` next to the ``final/`` directory.
    Returns the path if found, else None.
    """
    try:
        xml_abs = os.path.abspath(xml_path)
        # <workdir>/final/word/document.xml — walk up 3 parents to <workdir>
        workdir = os.path.dirname(os.path.dirname(os.path.dirname(xml_abs)))
        candidate = os.path.join(workdir, 'paragraphs.json')
        if os.path.isfile(candidate):
            return candidate
    except (OSError, ValueError):
        pass
    return None

def _run_validate_apply_post_strip(xml_path, paragraphs_json_path):
    """Rev18: run validate_apply.py --strict at the end of post_process,
    AFTER strip_noop_tracked_changes has already run.

    Why this exists: ``apply_translations_textmatch.py`` already runs
    ``validate_apply --strict`` at end-of-apply, but at that point the
    XML still contains phantom (``ins_then_del``) wrappers and any
    placeholder symbols (``○``, ``□``) that ``strip_noop`` will later
    remove during post_process. Those wrappers/symbols are still
    declared in paragraphs.json. So a doc that drifts during strip_noop
    passes the apply-time gate and only fails at repack-time
    ``validate_apply``, after Steps 6→9 have burned wall-clock.

    Adding a second invocation here means strip_noop-induced drift
    surfaces at the END of Step 6, not at Step 10. Step 9 (quality
    check) and the repack itself are skipped on a doomed doc, saving
    15-60 seconds per failed iteration on top of the diagnostic time
    already saved by surfacing the failure immediately.

    Same script, same flag, same exit semantics — ``_run_validator``-
    style block on exit code != 0.
    """
    import subprocess
    scripts_dir = os.path.dirname(os.path.abspath(__file__))
    print(f"\n{'=' * 60}\n[post_process] auto-running "
          f"validate_apply.py --strict (post-strip drift gate)\n"
          f"{'=' * 60}")
    result = subprocess.run(
        [sys.executable,
         os.path.join(scripts_dir, 'validate_apply.py'),
         paragraphs_json_path,
         xml_path,
         '--strict',
         # rev42: fix_spacing has already inserted spaces at
         # element boundaries by this point. Tell validate_apply
         # to simulate the same insertion on the declared side
         # so tokenisation is symmetric and the gate doesn't
         # false-fire on the post-mortem digit→upper class.
         '--post-spacing-fix'],
        capture_output=False)
    if result.returncode != 0:
        raise RuntimeError(
            f"SKILL GATE FIRED — INTENTIONAL BLOCK, NOT A SCRIPT ERROR. "
            f"validate_apply.py --strict returned exit code "
            f"{result.returncode} after post_process / strip_noop. "
            f"The document drifted from paragraphs.json during Step 6 "
            f"(typically: phantom segment glued to next regular by "
            f"period-lowercase, or symbol placeholder stripped as noise). "
            f"WORK OUT WHICH OF THREE THINGS IS WRONG BEFORE EDITING ANY OF "
            f"THEM. (1) The document drifted. (2) paragraphs.json is the "
            f"inaccurate record. (3) THIS CHECK IS WRONGLY SCOPED — it is "
            f"requiring text that another mandatory step removed by design, "
            f"so both the document and paragraphs.json are correct and the "
            f"check is miscounting. This gate cannot tell you which, and it "
            f"cannot detect (3) about itself. "
            f"BUT YOU ARE NO LONGER GUESSING BETWEEN THE THREE: "
            f"`{JOURNAL_NAME}`, written beside paragraphs.json a moment ago, "
            f"lists every piece of text THIS STEP changed and which pass "
            f"changed it. READ IT FIRST. If the flagged text is in there, the "
            f"document moved and this step moved it — that is (1), and the "
            f"pass is named, so the diagnosis is not 'drift' but whatever that "
            f"pass does. If the flagged text is NOT in there, this step did "
            f"not touch it and the fault is upstream or in the check itself. "
            f"A terminology override has already been diagnosed as drift once "
            f"on a real document, and the repair went to the wrong file. "
            f"For (3), SKILL.md rule 5a "
            f"governs: show the wrong scope from the check's own source or "
            f"stated contract, correct the check, keep the faithful "
            f"translation, and record it in the delivery notes. "
            f"Editing paragraphs.json to match the document is the fast "
            f"repair and it is the WRONG one whenever the document is what "
            f"changed: it clears the gate and ships the defect. Compare the "
            f"flagged text against the SOURCE document to decide. Then fix "
            f"whichever of the three is wrong and re-run from Step 5 "
            f"(apply). "
            f"Do NOT work around this gate by skipping the post-strip "
            f"validate_apply check — doing so silently ships output below "
            f"the quality the skill is designed to deliver. Surfaces the "
            f"failure ~4 minutes earlier than the repack-time gate would."
        )

def post_process(xml_path, fix=True, variant='uk', paragraphs_json=None):
    """Run all post-processing fixes on a document.xml file.

    Rev11 (final): auto-invokes strip_noop_tracked_changes.py at the end
    when the document contains tracked changes. The previous Step 6b is
    folded into Step 6 — operator runs ONE command and gets both passes
    on TC documents.

    also auto-invokes ``validate_apply.py --strict`` after the
    strip pass, so any drift between paragraphs.json and the post-
    stripped document.xml (phantom-segment glue, symbol-placeholder
    strips) is caught at end of Step 6 instead of at repack time. The
    paragraphs.json path is auto-detected from the conventional layout
    (``<workdir>/final/word/document.xml`` → ``<workdir>/paragraphs.json``);
    the explicit ``paragraphs_json`` argument overrides auto-detection.
    Skips silently if no paragraphs.json is found (post_process is also
    used standalone for non-TC documents and ad-hoc XML).
    """

    # Capture original header before parsing
    with open(xml_path, 'r', encoding='utf-8') as f:
        raw_xml = f.read()
    orig_header = extract_header(raw_xml)

    tree = etree.parse(xml_path)
    root = tree.getroot()

    results = {}
    journal = ChangeJournal(variant)
    original_paragraphs = journal_paragraph_texts(root)

    # THE NOTES ARE RESOLVED ONCE, HERE, AND THE SAME PATH FEEDS BOTH CONSUMERS.
    # rev18 resolved it at the very end, for the drift gate alone; slice 3a needs it
    # BEFORE the passes run. One resolution rather than two means the pass and the gate
    # can never disagree about which notes describe this document -- a disagreement that
    # would be invisible, both halves reporting normally against different files.
    declared_json = paragraphs_json or _autodetect_paragraphs_json(xml_path)
    declared_notes = load_declared_notes(declared_json)

    def _journalled(name, fn, **kwargs):
        """Run one pass between two snapshots. THE PASS ITSELF IS NOT TOUCHED — no
        fix_* function knows this exists, which is what makes the journal provably
        non-behavioural and what keeps a future pass from having to remember to record.

        `kwargs` is forwarded because the two variant trees do NOT call every pass the
        same way — one of them passes `variant=` to the Article-to-Clause detector — and a
        wrapper that flattened that difference would silently change behaviour in one tree
        while every test in the other went on passing."""
        before_flat = journal_flat_texts(root)
        before_paras = journal_paragraph_texts(root)
        before_n = journal_element_count(root)
        before_fmt = journal_flat_formats(root)
        before_pfmt = journal_paragraph_formats(root)
        owner_map = journal_flat_paragraph_map(root)
        count = fn(root, **kwargs)
        journal.record_pass(name, before_flat, journal_flat_texts(root),
                            before_paras, journal_paragraph_texts(root),
                            before_n, journal_element_count(root), owner_map, count,
                            before_fmt, journal_flat_formats(root),
                            before_pfmt, journal_paragraph_formats(root))
        return count

    results['spacing'] = _journalled('spacing', fix_spacing)
    results['definition_boundaries'] = _journalled(
        'definition_boundaries', fix_definition_boundaries)
    results['double_punctuation'] = _journalled(
        'double_punctuation', fix_double_punctuation)
    results['terminology'] = _journalled('terminology', fix_terminology,
                                         notes=declared_notes)
    if variant == 'uk':
        results['uk_spelling'] = _journalled('uk_spelling', fix_uk_spelling)
    elif variant == 'us':
        results['us_spelling'] = _journalled('us_spelling', fix_us_spelling)
    results['annex_to_schedule'] = _journalled('annex_to_schedule', fix_annex,
                                               notes=declared_notes)
    results['article_to_clause'] = _journalled(
        'article_to_clause', fix_article_to_clause)
    results['duplicates'] = _journalled('duplicates', fix_duplicates)
    results['quotes'] = _journalled('quotes', fix_quotes)
    results['definition_line_breaks'] = _journalled(
        'definition_line_breaks', fix_definition_line_breaks)
    results['spurious_italic'] = _journalled(
        'spurious_italic', fix_spurious_italic_runs, notes=declared_notes)
    results['schedule_page_breaks'] = _journalled(
        'schedule_page_breaks', fix_schedule_page_breaks)

    total = sum(results.values())

    # SCHEMA 3: what every pass FOUND and left alone, taken once, after the last pass and
    # before anything is printed or written, so the screen and the journal report one run.
    journal.detections = collect_detections()

    for name, count in results.items():
        if count:
            print(f"  {name}: {count} fixes")
    print(f"  TOTAL: {total} fixes")

    # THE DETECTOR REPORTS — decision 2c's other limb, and they are printed
    # SEPARATELY FROM THE FIX COUNTS ON PURPOSE. A detection is not a fix, and
    # adding it to `total` would make "this stage changed nothing" and "this
    # stage found nothing" the same number, which is the reading branch 9's
    # `non_text_fixes` figure exists to prevent one level down.
    if DOUBLE_PUNCTUATION_FOUND:
        n = sum(d['count'] for d in DOUBLE_PUNCTUATION_FOUND)
        kinds = sorted({d['mark'] for d in DOUBLE_PUNCTUATION_FOUND})
        print(f"  [detector] double_punctuation FOUND {n} occurrence(s) "
              f"({', '.join(kinds)}) and CHANGED NOTHING — B8: nothing in "
              f"document.xml says whether a doubled mark is the source's or "
              f"ours, and one was a character of source content on a real "
              f"document. Deciding it needs the declared notes.")
    if ARTICLE_UNDECIDED:
        print(f"  [detector] article_to_clause could not classify "
              f"{len(ARTICLE_UNDECIDED)} reference(s) and LEFT THEM AS "
              f"'Article' — B2: the sentence after the number carries no "
              f"decisive token, and guessing 'internal' once rewrote a "
              f"statutory citation into a clause that does not exist.")
    if DECLARED_ITALIC_UNDECIDED:
        # THE REASONS ARE COUNTED SEPARATELY BECAUSE THEY MEAN DIFFERENT THINGS.
        # "no notes" is a whole document the pass declined to touch; the other two are
        # individual runs the declaration did not reach. Folding them into one number
        # would make a run standalone on ad-hoc XML look like a document with 200
        # unmatched paragraphs, and only the second is a reason to look at anything.
        why = {}
        for rec in DECLARED_ITALIC_UNDECIDED:
            why[rec['reason']] = why.get(rec['reason'], 0) + 1
        detail = ', '.join(f"{k}: {n}" for k, n in sorted(why.items()))
        print(f"  [detector] spurious_italic left "
              f"{len(DECLARED_ITALIC_UNDECIDED)} italic run(s) ALONE because the "
              f"declared notes do not settle them ({detail}) — B1: the word-count "
              f"rule cannot tell an italic this pipeline introduced from one the "
              f"operator authored, and on a real document guessing destroyed an "
              f"entire drafting convention the operator had declared correctly.")
    if LEXICON_CHOICE_KEPT:
        # ONE LINE PER PASS, THE STRINGS NAMED BY THE TABLE'S OWN LABELS AND THE REASONS
        # COUNTED APART. "declared" is the operator's choice and needs nothing; "no paragraph
        # match" and "no notes" are the cases nobody decided -- the text is kept either way,
        # and only the second kind is a reason to look at anything.
        for pass_name in ('terminology', 'annex_to_schedule'):
            mine = [k for k in LEXICON_CHOICE_KEPT if k['pass'] == pass_name]
            if not mine:
                continue
            what, why = {}, {}
            for k in mine:
                label = LEXICON_SANCTIONED[k['entry']][0]
                what[label] = what.get(label, 0) + 1
                why[k['reason']] = why.get(k['reason'], 0) + 1
            strings = ', '.join(f"{w} x{n}" for w, n in sorted(what.items()))
            reasons = ', '.join(f"{r}: {n}" for r, n in sorted(why.items()))
            print(f"  [detector] {pass_name} left {len(mine)} lexicon-sanctioned "
                  f"rendering(s) AS WRITTEN ({strings}; {reasons}) — B5/B6/F29: a "
                  f"lexicon in this skill presents the string as correct, and overwriting "
                  f"it once overruled an operator who had followed the lexicon and then "
                  f"blocked them with a drift error naming neither cause.")
    if SCHEDULE_HEADINGS_FOUND:
        on = [h for h in SCHEDULE_HEADINGS_FOUND if h['starts_new_page']]
        off = [h for h in SCHEDULE_HEADINGS_FOUND if h['starts_new_page'] is False]
        unknown = len(SCHEDULE_HEADINGS_FOUND) - len(on) - len(off)
        by_device = {}
        for h in on:
            for code in h['device']:
                by_device[code] = by_device.get(code, 0) + 1
        how = ', '.join(f"{c} {n}" for c, n in sorted(by_device.items()))
        print(f"  [detector] schedule_page_breaks found {len(SCHEDULE_HEADINGS_FOUND)} "
              f"schedule heading(s) and INSERTED NO page break: {len(on)} already start a "
              f"new page{f' ({how})' if how else ''}, {len(off)} do not, {unknown} unknown "
              f"(styled, and a style's page break is not visible in document.xml) — B7: "
              f"the break was a house convention imposed whatever the source did, and on "
              f"real documents it made blank pages and doubled breaks the source already "
              f"had. The source's pagination is kept.")

    if fix and total > 0:
        tree.write(xml_path, xml_declaration=True, encoding='UTF-8',
                   standalone=True)

        # Restore original header (lxml's write changes quotes/namespaces)
        if orig_header:
            with open(xml_path, 'r', encoding='utf-8') as f:
                written = f.read()
            written = re.sub(
                r'^<\?xml[^?]*\?>\s*<w:document[^>]*>',
                orig_header,
                written,
                count=1,
                flags=re.DOTALL
            )
            with open(xml_path, 'wb') as f:
                f.write(written.encode('utf-8'))

        print(f"  Saved to {xml_path}")

    # Rev11 (final): auto-run strip_noop_tracked_changes.py for TC docs.
    # Replaces the previous Step 6b as a separate operator command —
    # post_process now does both passes in one invocation.
    if fix and _xml_has_tracked_changes(xml_path):
        # JOURNALLED TOO, AND IT IS A SEPARATE STAGE BECAUSE IT DELETES. The strip removes
        # w:ins/w:del wrappers, so every text-bearing element's ordinal after one shifts
        # and the element-level record the passes use cannot describe it. It is recorded
        # at PARAGRAPH level instead, which is the level the downstream comparison reads.
        _pre_strip_root = etree.parse(xml_path).getroot()
        before_strip = journal_paragraph_texts(_pre_strip_root)
        before_strip_fmt = journal_paragraph_formats(_pre_strip_root)
        _run_strip_noop_subprocess(xml_path)
        _post_strip_root = etree.parse(xml_path).getroot()
        journal.record_strip(
            True, before_strip,
            journal_paragraph_texts(_post_strip_root),
            before_strip_fmt,
            journal_paragraph_formats(_post_strip_root))

    # THE JOURNAL IS WRITTEN BEFORE THE DRIFT GATE, ON PURPOSE. When that gate fires the
    # operator is shown a DRIFT error whatever the real cause was — the register's own
    # instance is a terminology override diagnosed as drift, which sent the repair at the
    # wrong file. The journal is the answer to "what moved, and which pass moved it", so it
    # has to be on disk before the thing that raises, not after it.
    if fix:
        journal_write(journal, xml_path,
                      journal_paragraph_texts(etree.parse(xml_path).getroot()),
                      original_paragraphs)

    # post-strip drift gate. Auto-detect paragraphs.json by
    # convention if not supplied explicitly. Surfaces phantom-glue and
    # placeholder-strip failures at end of Step 6 rather than at Step 10.
    if fix:
        # `declared_json` was resolved at the top of this function and is the SAME path
        # the conditional passes consulted. It is reused rather than re-derived: two
        # resolutions of one path is a place for the pass and the gate to disagree
        # silently about which notes describe this document.
        if declared_json:
            _run_validate_apply_post_strip(xml_path, declared_json)

    return results

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Post-process translated legal document XML')
    parser.add_argument('xml_path', help='Path to document.xml')
    parser.add_argument('--fix', action='store_true', default=True,
                        help='Apply fixes (default: True)')
    parser.add_argument('--report-only', action='store_true',
                        help='Only report issues, do not fix')
    parser.add_argument('--variant', choices=['uk', 'us'], default='uk',
                        help='English variant (default: uk)')
    parser.add_argument('--paragraphs', dest='paragraphs_json', default=None,
                        help=('Rev18: explicit paragraphs.json path for the '
                              'post-strip validate_apply --strict drift gate. '
                              'When omitted, auto-detected from the convention '
                              '<workdir>/paragraphs.json; if neither is found '
                              'the post-strip gate is skipped.'))
    args = parser.parse_args()

    if args.report_only:
        args.fix = False

    post_process(args.xml_path, fix=args.fix, variant=args.variant,
                 paragraphs_json=args.paragraphs_json)

# === SKILL FILE COMPLETE ===
