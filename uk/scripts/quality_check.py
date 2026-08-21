"""Comprehensive quality check for translated legal documents.

Checks (all must pass zero for delivery):
 1. Missing spaces between adjacent w:t elements
 2. Definition boundary spacing ("Xmeans" etc.)
 3. Double punctuation (::, .., ,,)
 4. Terminology/lexicon violations
 5. Standalone "Financing" (not "Project Financing")
 6. Duplicate words (within and across elements)
 7. Missing/broken quotes on defined terms
 8. Italian remnants (words and full paragraphs)
 9. Title/header issues
10. Word order issues ("X existing and future")
11. UK spelling violations
12. Article vs Clause for internal cross-references
13. "that precedes"/"that follows" remnants (including plural "that precede")
14. Truncation detection (sentences cut mid-thought)
15. Formatting: bold on definitions, spurious italic, line breaks in definitions
16. Numbering: level jumps, orphaned sub-items
17. Definition alphabetical order verification

Usage:
    python quality_check.py <document.xml> [--verbose] [--with-source <paragraphs.json>]

The --with-source flag enables truncation detection by comparing English length
against the Italian source stored in paragraphs.json.
"""
import sys
import os
import json
import re
from collections import Counter
from lxml import etree

# Import the shared per-language marker module from the same scripts/ folder.
_SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)
from source_language_markers import (  # noqa: E402
    scan_remnants,
    detect_language,
    SUPPORTED_LANGUAGES,
)


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
            "  Step 9 is MANDATORY — do not deliver while this script is\n"
            "  truncated. Either re-install or block delivery until\n"
            "  quality_check.py runs cleanly.\n"
            + "=" * 60 + "\n"
        )
        print(msg, file=sys.stderr)
        sys.exit(3)


# Run the integrity check at module-import time so callers (including
# auto-invokers) discover truncation before any work begins.
#
# THIS CALL USED TO SIT AT THE BOTTOM OF THE FILE, BELOW `__main__`, and the
# comment above it made this same claim while the code did the opposite: Python
# executes top to bottom, so the entire quality check ran and printed before the
# guard was reached. It was the only one of the twenty scripts placed that way —
# the other nineteen already call it here, which is why this is a move back to
# the house pattern rather than a new idea.
#
# AND IT REPAIRS THE DOCUMENTED DIAGNOSTIC, WITH ONE MEASURED LIMIT.
# `skill-docs/08-aux-and-quality.md` tells the operator to run this script with
# `--help` to see whether the guard fires. From the bottom of the file that could
# never work: argparse handles `--help` and exits first, so the check looked clean
# however truncated the install was. Measured across every truncation point that
# leaves a file Python can still compile: 0 of 29 fired before this move, 31 of 31
# fire after it.
#
# THE LIMIT IS REAL AND NO PLACEMENT FIXES IT. Python compiles the whole module
# before executing any of it, so where truncation leaves invalid syntax the guard
# is unreachable wherever it sits — the operator gets a SyntaxError traceback
# instead of a diagnosis. Both outcomes are safe, because nothing runs either way;
# they differ only in whether the message names the cause. Deep cuts to this file
# tend not to compile and shallow ones do, which is the OPPOSITE of the pattern
# measured on extract_paragraphs.py — the behaviour is a property of where the cut
# lands in a particular file, not a general rule.
_check_self_integrity()

W = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'

# ======================================================================
# CONFIGURATION
# ======================================================================

TERM_VIOLATIONS = [
    'Financing Agreement', 'Financing Bank', 'Business Register', 'Lien Assets',
    'Partial Invalidity', 'cash line', 'Cash line', 'revolving line', 'credit lines',
    'credit line', 'Domicile Election', 'election of domicile', 'Election of Domicile',
    'which intervenes as', 'who intervenes as', 'intervenes as',
    'by universal or singular title',
    'Deed of Establishment', 'Deed of Creation', 'deed of creation',
    'Deed of Constitution of Pledge', 'deed of constitution',
    'plants and works existing and future',
    'Description of Financing',
    'stipulated',
]

US_SPELLINGS = [
    (r'\bauthorize\b', 'authorise'), (r'\bauthorized\b', 'authorised'),
    (r'\bAuthorization\b', 'Authorisation'), (r'\bAUTHORIZATION\b', 'AUTHORISATION'),
    (r'\bauthorization\b', 'authorisation'),
    (r'\brecognize\b', 'recognise'), (r'\brecognized\b', 'recognised'),
    (r'\borganize\b', 'organise'), (r'\borganized\b', 'organised'),
    (r'\borganization\b', 'organisation'),
    (r'\bfavor\b', 'favour'), (r'\bhonor\b', 'honour'), (r'\bcenter\b', 'centre'),
    (r'\bdefense\b', 'defence'), (r'\bfulfill\b', 'fulfil'),
    (r'\bfulfillment\b', 'fulfilment'),
    (r'\bjudgment\b', 'judgement'), (r'\bjudgments\b', 'judgements'),
    (r'\bJudgment\b', 'Judgement'),
    (r'\backnowledgment\b', 'acknowledgement'),
    (r'\butilize\b', 'utilise'), (r'\butilized\b', 'utilised'),
    (r'\bcanceled\b', 'cancelled'), (r'\banalyze\b', 'analyse'),
]

LEGISLATION_KW = [
    'Civil Code', 'Legislative Decree', 'D.P.R.', 'Law No.', 'Law no.',
    'Royal Decree', 'Ministerial Decree', 'Regulation (EU)', 'Banking Act',
    'decreto legislativo', 'Codice Civile', 'D.Lgs.', 'D.L.',
    'T.U.B.', 'T.U.F.', 'Decree No.', 'Decree no.',
    'Consolidated Banking', 'Consolidated Financial', 'Presidential Decree',
]

# Italian words that should not appear (excluding OK-listed contexts)
ITALIAN_WORDS = [
    r'\bdella\b', r'\bdelle\b', r'\bdello\b', r'\bdegli\b',
    r'\bnella\b', r'\bnelle\b', r'\bnello\b', r'\bnegli\b', r'\bnel\b',
    r'\balla\b', r'\balle\b', r'\ballo\b', r'\bagli\b',
    r'\bsulla\b', r'\bsulle\b', r'\bsullo\b', r'\bsugli\b',
    r'\bche\b', r'\bogni\b', r'\bsuo\b', r'\bsua\b',
    r'\bciascun[oa]?\b', r'\bpresente\b', r'\bsecondo\b',
    r'\bai sensi\b', r'\bfermo restando\b',
    r'\bcontratto\b', r'\bsociet[aà]\b', r'\bgaranzia\b',
    r'\bcessione\b', r'\bipoteca\b', r'\bpegno\b',
    r'\bcrediti\b', r'\bconto\b', r'\bbanca\b',
    r'\bcinquanta per cento\b', r'\bcinquanta\b',
    r'\bprecedente\b', r'\bsuccessivo\b',
    r'\bParti\b', r'\bParte\b',
]

# Contexts that are OK even though they contain Italian-looking words
# NOTE: this constant is currently unused (live whitelist lives in
# source_language_markers.WHITESPACE_OK_CONTEXTS). Kept for reference;
# specific bank/institution names removed to avoid signalling.
OK_CONTEXTS = [
    'S.p.A.', 'S.r.l.', 'per cent', 'per annum', 'inter alia', 'pari passu',
    'pro rata', 'bona fide', 'Gazzetta Ufficiale',
    'D.P.R.', 'Codice Civile',
    'Decreto Legislativo', 'decreto legislativo',
    'Agenzia delle Entrate', 'Conservatoria', 'Camera di Commercio',
    'Comune di', 'Provincia di', 'Tribunale di', 'delle Imprese',
    'della Repubblica', 'del Registro', 'Registro delle Imprese',
    'Notaio', 'notaio', 'Repertorio', 'Raccolta',
    'Contratto di Finanziamento',  # sometimes kept in Italian as proper noun
    'the Parties', 'the Party', 'Counterparty', 'Counterparties',
    'Third Party', 'third party',
]

# Dangling endings that suggest truncation
TRUNCATION_ENDINGS = [
    r'\bthe\s*$', r'\bof\s*$', r'\band\s*$', r'\bin\s*$', r'\bto\s*$',
    r'\bfor\s*$', r'\bwith\s*$', r'\bby\s*$', r'\bfrom\s*$', r'\bor\s*$',
    r'\bas\s*$', r'\bat\s*$', r'\bon\s*$', r'\bthat\s*$', r'\bwhich\s*$',
    r'\bunder\s*$', r'\bpursuant\s*$', r'\bwithout\s*$',
    r'\bany\s*$', r'\beach\s*$', r'\bsuch\s*$', r'\bthis\s*$',
    r'\bshall\s*$', r'\bwill\s*$', r'\bmay\s*$',
    r'\ba\s*$', r'\ban\s*$',
]

# List-connective whitelist: "; and", ", and", "; or", ", or" are legal-English
# list connectives, NOT truncation. Short-circuits the truncation flag without
# weakening detection of genuine truncations (which lack the ;/, prefix).
LIST_CONNECTOR_RE = re.compile(r'(?:[;,]\s*)(?:and|or)\s*$', re.IGNORECASE)

# Terminal punctuation, for the source-side test the dangling-ending rule needs.
# A source paragraph that itself ends mid-sentence cannot have a faithful English
# rendering that ends on a full stop, so the rule must not read the English's
# dangling ending as damage the translator did. Register G11.
TERMINAL_PUNCT = tuple('.!?:;。！？"\')]}”’')

# EXECUTION-BLOCK LEAD-IN. A formulaic opener whose grammatical object IS the
# signature block below it, so it ends on a preposition BY DESIGN. Register G5.
#
# Both conditions are required, and the second is what keeps the exemption narrow:
# an ordinary sentence that merely ends on "of" is untouched unless it also
# carries an execution keyword. The residual cost is stated rather than hidden --
# a real sentence containing "signed" AND ending on "of" is silenced. The
# alternative would key on the paragraph's POSITION inside an execution block,
# which this check cannot see, and G5 is LOW severity precisely because of that
# trade. Measured on the recorded corpus: silences exactly the three findings on
# the one document the register attests, and nothing on the other twelve workdirs.
SIG_LEADIN_RE = re.compile(
    r'\b(?:sign(?:ed|ature)|execut(?:ed|ion)|on\s+behalf|behalf\s+of|'
    r'witness(?:ed|es)?|duly\s+authoris|duly\s+authoriz|as\s+a\s+deed|'
    r'in\s+the\s+presence)\b', re.IGNORECASE)
SIG_TAIL_RE = re.compile(r'\b(?:of|by|for)\s*$', re.IGNORECASE)

# ======================================================================
# CHECK FUNCTIONS
# ======================================================================

# Elements that RENDER a break between two runs, so no space character is needed
# between them. `w:tab` here means a rendered tab CHARACTER; a `w:tab` inside
# `w:pPr/w:tabs` is a tab STOP and is excluded below, which is the distinction the
# OOXML rules draw and the trap a naive iteration falls into.
BREAK_TAGS = frozenset((f'{{{W}}}tab', f'{{{W}}}br', f'{{{W}}}cr'))


def check_spacing(root, verbose):
    """Check 1: Missing spaces between adjacent w:t elements.

    WALKS THE PARAGRAPH IN DOCUMENT ORDER, NOT JUST ITS w:t ELEMENTS. Register G10.
    Collecting only the w:t elements makes what sits BETWEEN two runs invisible, so
    a party grid laid out as `Party A` <w:tab/> `Party B` -- entirely ordinary in a
    signature block -- read as two adjacent runs with nothing between them and was
    reported as a missing space. Branch 5 gave `quality_check` an exit code, so that
    false positive stopped being a wasted glance and started stopping the run.

    THIS IS A CONVERGENCE, NOT A WIDENING. `validate_apply._paragraph_applied_text`
    already treats `w:tab` AND `w:br` as whitespace separators when it joins a
    paragraph, and its docstring documents this very mechanism as a false positive
    it had to fix. One check in the package saw what sits between two runs and
    another did not; they now agree. Restricting the fix to tabs alone would leave
    the identical false positive on a manual line break, which is the same defect
    wearing a different element name.
    """
    issues = []
    for p in root.iter(f'{{{W}}}p'):
        # (element, text) for every w:t, with a None entry marking a rendered break.
        t_elems = []
        for el in p.iter():
            if el.tag in BREAK_TAGS:
                # A tab STOP declares a position in w:pPr/w:tabs and renders nothing.
                parent = el.getparent()
                if el.tag == f'{{{W}}}tab' and parent is not None \
                        and parent.tag == f'{{{W}}}tabs':
                    continue
                t_elems.append((None, None))
            elif el.tag == f'{{{W}}}t' and el.text:
                t_elems.append((el, el.text))
        for i in range(1, len(t_elems)):
            prev = t_elems[i-1][1]
            curr = t_elems[i][1]
            if not prev or not curr:
                continue
            pc, cc = prev[-1], curr[0]
            bad = False
            if pc.isalpha() and cc.isalpha(): bad = True
            elif pc.isalpha() and cc == '(': bad = True
            elif pc == ')' and cc.isalpha(): bad = True
            elif pc == ';' and cc.isalpha(): bad = True
            elif pc == ',' and cc.isalpha(): bad = True
            elif pc == ':' and cc.isalpha(): bad = True
            elif pc.isdigit() and cc.isupper(): bad = True
            elif pc == '.' and cc.isupper():
                if not re.search(r'\b[A-Z]\.$', prev) and not any(
                    prev.endswith(s) for s in ['No.', 'no.', 'etc.', 'S.p.A.', 'S.r.l.', '..', 'seq.']):
                    bad = True
            if bad:
                issues.append(f"'{prev[-20:]}|{curr[:20]}'")
    return issues

def check_definition_boundaries(root, verbose):
    """Check 2: Missing space before definition verbs (Xmeans, Xshall mean, etc.)."""
    issues = []
    for p in root.iter(f'{{{W}}}p'):
        full = ''.join(t.text or '' for t in p.iter(f'{{{W}}}t'))
        for pat in [r'[A-Z\u201d"\)]means\b', r'[A-Z\u201d"\)]shall mean\b',
                    r'[A-Z\u201d"\)]has the meaning\b', r'[A-Z\u201d"\)]indicates\b']:
            for m in re.finditer(pat, full):
                issues.append(f"'{full[max(0,m.start()-10):m.end()+10]}'")
    return issues

def check_double_punctuation(root, verbose):
    """Check 3: Double colons, periods, commas, semicolons."""
    issues = []
    for t in root.iter(f'{{{W}}}t'):
        if t.text:
            if '::' in t.text: issues.append(f"'::' in '{t.text[:50]}'")
            if re.search(r'\.\.(?!\.)', t.text): issues.append(f"'..' in '{t.text[:50]}'")
            if ',,' in t.text: issues.append(f"',,' in '{t.text[:50]}'")
            if ';;' in t.text: issues.append(f"';;' in '{t.text[:50]}'")
    return issues

def check_terminology(root, verbose):
    """Check 4: Terminology/lexicon violations."""
    issues = []
    for t in root.iter(f'{{{W}}}t'):
        if t.text:
            for term in TERM_VIOLATIONS:
                if term in t.text:
                    issues.append(f"'{term}' in '{t.text[:60]}'")
    return issues

def check_standalone_financing(root, verbose):
    """Check 5: Standalone 'Financing' not part of 'Project Financing'."""
    issues = []
    for t in root.iter(f'{{{W}}}t'):
        if t.text and 'Financing' in t.text:
            cleaned = t.text.replace('Project Financing', '')
            if 'Financing' in cleaned:
                issues.append(f"Standalone 'Financing' in '{t.text[:60]}'")
    return issues

def check_duplicates(root, verbose):
    """Check 6: Duplicate words within and across elements."""
    issues = []
    # Within elements
    for t in root.iter(f'{{{W}}}t'):
        if t.text:
            for m in re.finditer(r'\b(\w{3,})\s+\1\b', t.text, re.IGNORECASE):
                if m.group(1).lower() not in ('that', 'had', 'very'):
                    issues.append(f"'{m.group(1)} {m.group(1)}' in '{t.text[:50]}'")
    # Across boundaries
    for p in root.iter(f'{{{W}}}p'):
        t_elems = [(t, t.text) for t in p.iter(f'{{{W}}}t') if t.text and t.text.strip()]
        for i in range(1, len(t_elems)):
            pw = t_elems[i-1][1].split()
            cw = t_elems[i][1].split()
            if pw and cw:
                p_clean = re.sub(r'[,;:."\'\)\]]+$', '', pw[-1])
                c_clean = re.sub(r'^["\'\(\[]+', '', cw[0])
                if (p_clean and c_clean and p_clean.lower() == c_clean.lower()
                        and len(p_clean) > 2 and p_clean.isalpha()):
                    issues.append(f"'{p_clean}' at boundary")
    return issues

def check_quotes(root, verbose):
    """Check 7: Missing/broken quotes on defined terms."""
    issues = []
    OPEN_Q = '\u201c'
    CLOSE_Q = '\u201d'
    for p in root.iter(f'{{{W}}}p'):
        full = ''.join(t.text or '' for t in p.iter(f'{{{W}}}t'))
        if not any(v in full for v in ['means', 'shall mean', 'has the meaning', 'indicates']):
            continue
        # Check for unbalanced smart quotes
        opens = full.count(OPEN_Q) + full.count('\u201e')
        closes = full.count(CLOSE_Q)
        if opens > 0 and opens != closes:
            issues.append(f"Unbalanced quotes ({opens} open, {closes} close): '{full[:80]}'")
        # Check for "Term means" without closing quote
        for m in re.finditer(r'[\u201c"]\s*([^"\u201d\u201c]{2,60}?)\s+(means|shall mean|has the meaning|indicates)\b', full):
            term = m.group(1)
            if not term.rstrip().endswith(CLOSE_Q) and not term.rstrip().endswith('"'):
                issues.append(f"Missing close quote: '{full[m.start():m.end()+5]}'")
    return issues

def check_source_remnants(root, verbose, source_language=None):
    """Check 8: untranslated source-language words and paragraphs.

    Uses the shared `source_language_markers` module so the scanner is specific
    to the actual source language (Dutch, German, French, etc.) — not hardcoded
    to Italian. If `source_language` is None, the check is skipped silently.

    Scans BOTH <w:t> (accept-all view) AND <w:delText> (reject-all / markup
    view). The delText pass catches source-language remnants that live inside
    a tracked-change deletion — including the phantom <w:ins><w:del>SRC</w:del>
    </w:ins> shape that renders as empty under accept-all but is still visible
    with "Show Markup" on. The two views are reported under distinct labels so
    a reviewer knows where to look.
    """
    issues = []
    if not source_language:
        return issues
    lang = source_language.lower()
    if lang not in SUPPORTED_LANGUAGES:
        # Languages outside SUPPORTED_LANGUAGES skip remnant detection;
        # translator fidelity is the primary safeguard.
        return issues

    label = lang.capitalize()
    extra_filter_italian = (lang == 'italian')

    def _filtered_issues(full_text, view_tag):
        out = []
        for _marker, context in scan_remnants(full_text, lang):
            ctx_stripped = context.strip()
            # Italian-specific legacy filters kept for backwards compatibility.
            if extra_filter_italian:
                if re.search(r'\bcome\b|\bCome\b', ctx_stripped):
                    continue
                if re.search(r'non-\w', ctx_stripped):
                    continue
                if any(x in ctx_stripped for x in ('per cent', 'per annum', 'per se')):
                    continue
            out.append(f"{label} remnant ({view_tag}) in '{ctx_stripped[:100]}'")
        return out

    for p in root.iter(f'{{{W}}}p'):
        full_t = ''.join(t.text or '' for t in p.iter(f'{{{W}}}t'))
        full_del = ''.join(dt.text or '' for dt in p.iter(f'{{{W}}}delText'))

        if full_t.strip() and len(full_t.split()) >= 3:
            issues.extend(_filtered_issues(full_t, 'accept-all'))
            # Full source-language paragraphs (high density of source function words)
            dense_hits = len(scan_remnants(full_t, lang))
            if dense_hits >= 3:
                issues.append(f"FULL {label.upper()} PARAGRAPH (accept-all): '{full_t[:100]}'")

        if full_del.strip() and len(full_del.split()) >= 1:
            # delText is almost always a short strike-through fragment, so the
            # 3-word minimum used for accept-all text would filter out most
            # legitimate remnants. Require only one word.
            issues.extend(_filtered_issues(full_del, 'reject-all / markup'))
            dense_hits_del = len(scan_remnants(full_del, lang))
            if dense_hits_del >= 3:
                issues.append(f"FULL {label.upper()} PARAGRAPH (reject-all / markup): '{full_del[:100]}'")

    return issues

def check_italian_remnants(root, verbose):
    """Legacy name kept for backward compatibility with callers that pass
    no source_language. Forwards to check_source_remnants with lang=None,
    which is a no-op. Prefer check_source_remnants(root, verbose, lang)."""
    return check_source_remnants(root, verbose, None)

def check_titles(root, verbose):
    """Check 9: Title/header issues."""
    issues = []
    bad_titles = [
        'Deed of Establishment of Special Lien', 'DEED OF ESTABLISHMENT OF SPECIAL LIEN',
        'Deed of Creation of Mortgage', 'DEED OF CREATION OF MORTGAGE',
        'Deed of Constitution of Pledge', 'DEED OF CONSTITUTION OF PLEDGE',
        'deed of creation of the Pledge', 'deed of creation of the pledge',
        'deed of constitution of the pledge',
    ]
    for t in root.iter(f'{{{W}}}t'):
        if t.text:
            for bt in bad_titles:
                if bt in t.text:
                    issues.append(f"'{bt}' in '{t.text[:60]}'")
    return issues

def check_word_order(root, verbose):
    """Check 10: Word order issues (adjective placement)."""
    issues = []
    pattern = re.compile(r'\b(\w+)\s+existing\s+and\s+future\b', re.IGNORECASE)
    for t in root.iter(f'{{{W}}}t'):
        if t.text:
            for m in pattern.finditer(t.text):
                noun = m.group(1).lower()
                if noun not in ('and', 'the', 'all', 'any', 'of'):
                    issues.append(f"'{m.group()}' should be 'existing and future {m.group(1)}'")
    return issues

def check_us_spelling(root, verbose):
    """Check 11a: US spelling violations (used under UK variant — the default)."""
    issues = []
    for t in root.iter(f'{{{W}}}t'):
        if t.text:
            for pattern, uk in US_SPELLINGS:
                m = re.search(pattern, t.text)
                if m:
                    issues.append(f"'{m.group()}' -> '{uk}'")
    return issues

# Inverse spelling table used ONLY when the caller passes --variant us,
# which itself should only happen when the user's original prompt explicitly
# asked for US English. UK is the hardcoded default variant of this skill.
UK_SPELLINGS_INV = [
    (r'\bauthorise\b', 'authorize'), (r'\bauthorised\b', 'authorized'),
    (r'\bAuthorisation\b', 'Authorization'), (r'\bAUTHORISATION\b', 'AUTHORIZATION'),
    (r'\bauthorisation\b', 'authorization'),
    (r'\brecognise\b', 'recognize'), (r'\brecognised\b', 'recognized'),
    (r'\borganise\b', 'organize'), (r'\borganised\b', 'organized'),
    (r'\borganisation\b', 'organization'),
    (r'\bfavour\b', 'favor'), (r'\bhonour\b', 'honor'), (r'\bcentre\b', 'center'),
    (r'\bdefence\b', 'defense'), (r'\bfulfil\b', 'fulfill'),
    (r'\bfulfilment\b', 'fulfillment'),
    (r'\bjudgement\b', 'judgment'), (r'\bjudgements\b', 'judgments'),
    (r'\bJudgement\b', 'Judgment'),
    (r'\backnowledgement\b', 'acknowledgment'),
    (r'\butilise\b', 'utilize'), (r'\butilised\b', 'utilized'),
    (r'\bcancelled\b', 'canceled'), (r'\banalyse\b', 'analyze'),
]

def check_uk_spelling(root, verbose):
    """Check 11b: UK spelling violations (used under US variant only)."""
    issues = []
    for t in root.iter(f'{{{W}}}t'):
        if t.text:
            for pattern, us in UK_SPELLINGS_INV:
                m = re.search(pattern, t.text)
                if m:
                    issues.append(f"'{m.group()}' -> '{us}'")
    return issues

def check_article_refs(root, verbose):
    """Check 12: Article for internal cross-refs (should be Clause)."""
    issues = []
    for p in root.iter(f'{{{W}}}p'):
        full = ''.join(t.text or '' for t in p.iter(f'{{{W}}}t'))
        is_leg = any(kw in full for kw in LEGISLATION_KW)
        if not is_leg:
            for m in re.finditer(r'\bArticles?\s+\d{1,2}(?:\.\d+)*', full):
                issues.append(f"'{m.group()}' in '{full[:70]}'")
    return issues

def check_that_precedes(root, verbose):
    """Check 13: 'that precedes/precede/follows/follow' remnants."""
    issues = []
    for p in root.iter(f'{{{W}}}p'):
        full = ''.join(t.text or '' for t in p.iter(f'{{{W}}}t'))
        # "that precede" / "that precedes"
        for m in re.finditer(r'\bthat precede[sd]?\b', full, re.IGNORECASE):
            issues.append(f"'{m.group()}' in '{full[:70]}'")
        # "that follow" / "that follows" (but not "that follows from" which is valid English)
        for m in re.finditer(r'\bthat follows?\b', full, re.IGNORECASE):
            if 'that follows from' not in full[m.start():m.start()+25].lower():
                issues.append(f"'{m.group()}' in '{full[:70]}'")
    return issues

def _norm_text(s):
    """Whitespace-normalised text, for pairing a notes entry to a paragraph."""
    return re.sub(r'\s+', ' ', s or '').strip()


def _pair_entries_to_paragraphs(root, source_data):
    """Pair each notes entry to the paragraph that holds the English it declared.

    WHY NOT BY POSITION, WHICH IS WHAT THIS USED TO DO. Step 7 (reorder_definitions)
    permutes document.xml, so `all_p[idx]` and `source_data[i]` stop describing the
    same paragraph the moment a document has a definitions section -- which, per
    Step 7's own rationale, is almost all of them. Measured on the recorded corpus:
    127 entries whose all_p[idx] holds text that is not the English that entry
    declared, and 9 of 9 of this check's method-A findings sat on one of them.
    Register L1.

    SO PAIR THE WAY `apply` ITSELF PAIRS -- on the text. That is not a new idea
    imported into this script; it is the property the whole pipeline rests on
    (text-matching, not index-matching), and index-based application was removed
    from `apply` for exactly this class of corruption.

    Returns {id(entry): paragraph_text}. An entry whose declared English cannot be
    located UNIQUELY is absent from the map, and the caller falls back to the
    entry's own declared English rather than guessing at a paragraph -- a wrong
    unique pairing is worse than none, because it would compare two unrelated
    paragraphs, which is the defect being repaired.
    """
    texts = [''.join(t.text or '' for t in p.iter(f'{{{W}}}t'))
             for p in root.iter(f'{{{W}}}p')]
    by_text = {}
    for i, t in enumerate(texts):
        k = _norm_text(t)
        if k:
            by_text.setdefault(k, []).append(i)

    paired = {}
    for entry in source_data:
        if not isinstance(entry, dict):
            continue
        key = _norm_text(entry.get('en') or '')
        if not key:
            continue
        idx = entry.get('idx', -1)
        # Keep the positional candidate when it is actually right: on a document
        # with no definitions section it always is, so those runs keep the exact
        # findings they had before, which is what makes this change reviewable.
        if 0 <= idx < len(texts) and _norm_text(texts[idx]) == key:
            paired[id(entry)] = texts[idx]
            continue
        hits = by_text.get(key, [])
        if len(hits) == 1:
            paired[id(entry)] = texts[hits[0]]
    return paired


def check_truncation(root, verbose, source_data=None):
    """Check 14: Truncated translations (sentences cut off mid-thought).

    Two methods:
    A) If source_data (paragraphs.json) is provided, compare English vs source length.
       Flag if English is less than 40% the length of the source (suggests truncation).
       The English is read from the paragraph PAIRED BY TEXT -- see
       _pair_entries_to_paragraphs -- and from the entry's own declared `en` where no
       unique pairing exists, so every eligible entry is judged.
    B) Dangling endings (sentences ending with articles/prepositions), EXCEPT where
       the source paragraph also lacks terminal punctuation, or where the paragraph
       is an execution-block lead-in.
    """
    issues = []
    paired = {}
    if source_data:
        paired = _pair_entries_to_paragraphs(root, source_data)

    # Method A: Length comparison with source
    if source_data:
        for entry in source_data:
            if not isinstance(entry, dict):
                continue
            idx = entry.get('idx', -1)
            src_text = entry.get('text', '')
            if not src_text.strip() or len(src_text) < 20:
                continue

            # The English to judge. The paired paragraph where one was found --
            # which also catches an edit made after apply -- otherwise the entry's
            # own declared English, which is what this rule is about: the docstring
            # says "truncated TRANSLATIONS", i.e. damage the translator did. Post-
            # apply loss is branch 8's and branch 11's subject, and validate_apply
            # --strict already re-checks token presence after post-processing.
            en_text = paired.get(id(entry))
            if en_text is None:
                en_text = entry.get('en') or ''

            if not en_text.strip():
                if len(src_text.strip()) > 30:
                    issues.append(f"EMPTY translation for non-empty source (idx={idx}): '{src_text[:60]}'")
                continue

            # Length ratio check (English is typically 0.8-1.2x source length for legal text)
            ratio = len(en_text) / len(src_text) if len(src_text) > 0 else 1
            if ratio < 0.4 and len(src_text) > 50:
                issues.append(f"TRUNCATED? ratio={ratio:.2f} (idx={idx}): EN='{en_text[:50]}' SRC='{src_text[:50]}'")

    # The source text for each paragraph, keyed by the paragraph text, so method B
    # can ask whether the SOURCE dangled too. Built from the same pairing, so the
    # two methods cannot disagree about which source paragraph a paragraph came
    # from -- they did before, which is how L1's mispairing reached a rule that
    # never used source_data at all.
    src_by_para = {}
    if source_data:
        for entry in source_data:
            if not isinstance(entry, dict):
                continue
            pt = paired.get(id(entry))
            if pt is None:
                continue
            k = _norm_text(pt)
            if k in src_by_para and src_by_para[k] != (entry.get('text') or ''):
                src_by_para[k] = None          # ambiguous: refuse to exempt
            else:
                src_by_para.setdefault(k, entry.get('text') or '')

    # Method B: Dangling endings. Skip drafter placeholder tokens
    # (faithful annotations preserved from source, not truncations).
    _PLACEHOLDER_PREFIXES = (
        'PM', '[PM]', 'TBD', '[TBD]', 'TBC', '[TBC]',
        '[...]', '[…]', '[●]', '[•]',
    )
    for p in root.iter(f'{{{W}}}p'):
        full = ''.join(t.text or '' for t in p.iter(f'{{{W}}}t'))
        if not full.strip() or len(full) < 20:
            continue

        # Skip paragraphs that are drafter placeholder notes.
        stripped = full.strip()
        if any(stripped.startswith(pfx) for pfx in _PLACEHOLDER_PREFIXES):
            continue
        # Skip paragraphs that begin with a run of underscores (e.g. "____").
        if stripped and stripped[0] == '_' and stripped.lstrip('_') != stripped:
            continue

        # Rev34 list-connective whitelist (skip "; and", ", and", "; or", ", or").
        if LIST_CONNECTOR_RE.search(full):
            continue
        # Check if paragraph ends with a dangling preposition/article/auxiliary
        for pat in TRUNCATION_ENDINGS:
            if re.search(pat, full):
                # Don't flag if it's clearly a heading or short label
                if len(full.split()) < 5:
                    continue

                # G5. An execution-block lead-in ends on its preposition by design:
                # its object is the signature block that follows it.
                if SIG_TAIL_RE.search(stripped) and SIG_LEADIN_RE.search(stripped):
                    break

                # G11. THE DATA THIS RULE NEEDED WAS ALREADY IN THE FUNCTION'S OWN
                # PARAMETER, UNUSED. The docstring's subject is "truncated
                # TRANSLATIONS", but where the SOURCE paragraph itself ends
                # mid-sentence, a faithful English rendering must also end on a
                # preposition or article -- so this rule was reporting fidelity as
                # damage, and no compliant repair existed: rewriting the English to
                # satisfy it would breach the rule that a faithful translation is
                # never altered to satisfy a linter.
                #
                # Exempt ONLY where the paired source paragraph also lacks terminal
                # punctuation. Over-truncation of a dangling source paragraph stays
                # covered by method A's length ratio, so nothing is left unguarded.
                # No pairing means NO exemption: absence of evidence that the source
                # dangled is not evidence that it did.
                src = src_by_para.get(_norm_text(full))
                if src:
                    s = src.strip()
                    if s and not s.endswith(TERMINAL_PUNCT):
                        break

                issues.append(f"Dangling ending '{full[-20:].strip()}' in '{full[:60]}'")
                break

    return issues

def check_formatting(root, verbose):
    """Check 15: Formatting issues (bold on definitions, spurious italic)."""
    issues = []

    for p in root.iter(f'{{{W}}}p'):
        full = ''.join(t.text or '' for t in p.iter(f'{{{W}}}t'))

        # Check definition paragraphs have bold on the defined term
        if any(v in full for v in ['means', 'shall mean', 'has the meaning']) and \
           ('\u201c' in full or '"' in full):
            has_bold = False
            for r in p.iter(f'{{{W}}}r'):
                rpr = r.find(f'{{{W}}}rPr')
                t = r.find(f'{{{W}}}t')
                if rpr is not None and rpr.find(f'{{{W}}}b') is not None:
                    if t is not None and t.text and len(t.text.strip()) > 2:
                        has_bold = True
                        break
            if not has_bold:
                issues.append(f"No bold term in definition: '{full[:70]}'")

        # Check for line breaks in definition paragraphs (run before heading skip)
        if any(v in full for v in ['means', 'shall mean', 'has the meaning', 'indicates']) and \
           ('\u201c' in full or '"' in full):
            for r in p.iter(f'{{{W}}}r'):
                br = r.find(f'{{{W}}}br')
                if br is not None:
                    issues.append(f"Line break in definition: '{full[:70]}'")
                    break  # One report per paragraph

        # Check for spurious italic on body text — per-run detection
        # Skip headings (all caps + short) for italic check only
        is_heading = full.strip() == full.strip().upper() and len(full.split()) < 10
        if is_heading:
            continue

        # Skip if paragraph-level style sets italic intentionally
        # ST_OnOff falsy set extended to include 'off'.
        _ST_ONOFF_FALSE_QC = {'false', '0', 'off'}

        def _qc_is_off(v):
            return v is not None and v.strip().lower() in _ST_ONOFF_FALSE_QC

        ppr = p.find(f'{{{W}}}pPr')
        p_italic = False
        if ppr is not None:
            p_rpr = ppr.find(f'{{{W}}}rPr')
            if p_rpr is not None:
                i_elem = p_rpr.find(f'{{{W}}}i')
                if i_elem is not None and not _qc_is_off(i_elem.get(f'{{{W}}}val')):
                    p_italic = True

        if not p_italic:
            latin_terms = ['inter alia', 'mutatis mutandis', 'pari passu', 'pro rata',
                           'bona fide', 'de facto', 'de jure', 'prima facie']
            for r in p.iter(f'{{{W}}}r'):
                rpr = r.find(f'{{{W}}}rPr')
                if rpr is None:
                    continue
                i_elem = rpr.find(f'{{{W}}}i')
                if i_elem is None or _qc_is_off(i_elem.get(f'{{{W}}}val')):
                    continue
                t = r.find(f'{{{W}}}t')
                if t is None or not t.text:
                    continue
                text = t.text.strip()
                if not text:
                    continue
                # Allow italic in parentheses (cross-ref headings), Latin terms, numbering labels
                if text.startswith('(') and text.endswith(')'):
                    continue
                if any(lt in text.lower() for lt in latin_terms):
                    continue
                if len(text) <= 5 and re.match(r'^[\d\.\(\)a-z]+$', text):
                    continue
                if len(text.split()) > 2:
                    issues.append(f"Spurious italic run: '{text[:50]}' in para: '{full[:50]}'")

    return issues

def _numbering_anomalies(root):
    """Every numbering anomaly in one body, as (structural_signature, message).

    The signature deliberately excludes the paragraph TEXT, because the same
    anomaly has source-language text on one side and English on the other and
    would never compare equal. What it carries is the numId, the level and the
    level it jumped from -- the structure, which the pipeline does not translate.
    """
    out = []
    current_nums = {}  # numId -> last seen ilvl

    for p in root.iter(f'{{{W}}}p'):
        ppr = p.find(f'{{{W}}}pPr')
        if ppr is None:
            continue
        numpr = ppr.find(f'{{{W}}}numPr')
        if numpr is None:
            continue

        numid_elem = numpr.find(f'{{{W}}}numId')
        ilvl_elem = numpr.find(f'{{{W}}}ilvl')
        if numid_elem is None:
            continue

        numid = numid_elem.get(f'{{{W}}}val')
        ilvl = int(ilvl_elem.get(f'{{{W}}}val', '0')) if ilvl_elem is not None else 0

        full = ''.join(t.text or '' for t in p.iter(f'{{{W}}}t'))

        if numid not in current_nums:
            current_nums[numid] = ilvl
            # First occurrence at level > 0 is suspicious (orphaned sub-item)
            if ilvl > 1:
                out.append((('orphan', numid, ilvl),
                            f"Numbering starts at level {ilvl} (numId={numid}): '{full[:60]}'"))
        else:
            prev = current_nums[numid]
            # Jumping down more than 1 level is suspicious
            if ilvl > prev + 1:
                out.append((('jump', numid, prev, ilvl),
                            f"Numbering level jump {prev}->{ilvl} (numId={numid}): '{full[:60]}'"))
            current_nums[numid] = ilvl

    return out


def check_numbering(root, verbose, source_root=None):
    """Check 16: Numbering/structure validation.

    Detects:
    - Paragraphs with numId references that point to numbering definitions
      where the sequence appears broken (e.g., level 0 jumps from 1 to 3)
    - Orphaned sub-items (level 1+ without a preceding level 0 parent)

    WITH source_root, REPORTS ONLY WHAT THE SOURCE DID NOT ALREADY HAVE.
    Register M1. This rule reads the sequence of numPr references, and the
    pipeline does not translate numbering -- so an anomaly present in the source
    body is INHERITED and reporting it says nothing about the translation. Where
    the source arrived as a legacy binary .doc, the converter rewrote the list
    structure wholesale, and every anomaly it left behind was then reported
    against us. Re-measured on the recorded corpus: on both documents that
    produce numbering findings, a body that differs from the delivered one
    yields the SAME anomaly count -- 8 against 8, and 3 against 3 -- so all
    eleven are inherited and none was introduced here.

    A REAL INTRODUCED DEFECT STILL FIRES, which is the point of differencing
    rather than disabling: Step 7 permutes the definitions block, and a
    permutation that breaks a numbering sequence produces an anomaly present in
    the delivered body and absent from the source.

    Without source_root the behaviour is exactly as before -- and `check` then
    says so out loud, because a comparison that silently did not happen is the
    failure shape this branch is repairing elsewhere (F15, C9).
    """
    delivered = _numbering_anomalies(root)
    if source_root is None:
        return [msg for _sig, msg in delivered]

    # Multiset difference, so three identical jumps in the source cancel three in
    # the delivered body and a fourth is still reported.
    inherited = Counter(sig for sig, _msg in _numbering_anomalies(source_root))
    issues = []
    for sig, msg in delivered:
        if inherited.get(sig):
            inherited[sig] -= 1
            continue
        issues.append(msg)
    return issues

def check_definition_order(root, verbose):
    """Check 17: Definitions are in alphabetical order by the English term.

    Groups consecutive definition paragraphs into blocks and checks each block
    independently. A definition paragraph is one containing a quoted term followed
    by "means"/"shall mean"/"has the meaning"/"indicates". A heading or a non-
    definition paragraph breaks the current block — so definitions in separate
    sections (e.g. "Interpretation" vs "Definitions") are checked independently.
    This prevents false positives when a document has definitions in multiple
    sections that are each internally sorted but not globally sorted.
    """
    issues = []

    # Collect consecutive definition blocks
    blocks = []
    current_block = []

    for p in root.iter(f'{{{W}}}p'):
        full = ''.join(t.text or '' for t in p.iter(f'{{{W}}}t'))

        # Check if this is a definition paragraph
        is_def = False
        term = None
        if any(v in full for v in ['means', 'shall mean', 'has the meaning', 'indicates']):
            m = re.search(r'[\u201c"]\s*(.+?)\s*[\u201d"]', full)
            if m:
                is_def = True
                term = m.group(1).strip()

        if is_def:
            current_block.append(term)
        else:
            # Non-definition paragraph breaks the block
            if len(current_block) >= 3:
                blocks.append(list(current_block))
            current_block = []

    # Don't forget the last block
    if len(current_block) >= 3:
        blocks.append(list(current_block))

    # Check each block independently
    for block in blocks:
        sorted_block = sorted(block, key=lambda t: t.lower())
        for i, (actual, expected) in enumerate(zip(block, sorted_block)):
            if actual != expected:
                issues.append(f"Definition out of order: '{actual}' (expected '{expected}' at position {i})")
                if len(issues) >= 5:
                    issues.append(f"... and potentially more.")
                    break

    return issues

# ======================================================================
# AUXILIARY-FILE SCANS # ======================================================================

def _scan_aux_xml_for_remnants(xml_path, source_language, label):
    """Parse an auxiliary OOXML file and run the source-language-remnant
    scan against every `<w:t>` element it contains. Returns a list of
    issue strings, prefixed with ``label`` (e.g. 'numbering.xml',
    'header1.xml')."""
    issues = []
    if not source_language:
        return issues
    lang = source_language.lower()
    if lang not in SUPPORTED_LANGUAGES:
        return issues
    try:
        tree = etree.parse(xml_path)
    except (OSError, etree.XMLSyntaxError):
        return issues
    root = tree.getroot()
    # numbering.xml uses <w:lvlText w:val="..."/> for level format strings.
    # header/footer/comments use <w:t> for text. Cover both.
    label_capped = source_language.capitalize()
    for t_elem in root.iter(f'{{{W}}}t'):
        text = t_elem.text or ''
        if not text.strip():
            continue
        for _marker, context in scan_remnants(text, lang):
            issues.append(
                f"{label_capped} remnant in {label}: '{context.strip()[:100]}'"
            )
    # Also scan w:lvlText for numbering format strings (scanned as plain
    # text — numbering format strings may legitimately reference
    # placeholder tokens like %1, %2 that scan_remnants ignores).
    for lvl_elem in root.iter(f'{{{W}}}lvlText'):
        val = lvl_elem.get(f'{{{W}}}val')
        if not val or not val.strip():
            continue
        for _marker, context in scan_remnants(val, lang):
            issues.append(
                f"{label_capped} remnant in {label} lvlText: "
                f"'{context.strip()[:100]}'"
            )
    return issues

def check_aux_files(aux_dir, source_language, verbose=False):
    """Scan every auxiliary XML part under ``aux_dir`` (typically the
    workdir's ``final/`` directory containing ``word/``) for source-
    language remnants. Returns a dict mapping aux-file basename to the
    list of issue strings.

    Auxiliary files covered:
      * word/numbering.xml
      * word/headerN.xml (all N)
      * word/footerN.xml (all N)
      * word/comments.xml
      * word/footnotes.xml
      * word/endnotes.xml

    The full quality_check rule set runs only on document.xml because
    most rules (italic, line breaks, definition formatting, truncation)
    are paragraph-shape rules that don't apply to numbering format
    strings or comments. This function adds the source-remnant scan to
    auxiliary files so calques and untranslated source-language text in
    headers / footers / numbering / comments are detected before
    repack rather than after."""
    results = {}
    word_dir = os.path.join(aux_dir, 'word')
    if not os.path.isdir(word_dir):
        # Allow callers to pass either the parent of word/ or word/
        # itself.
        if os.path.basename(aux_dir.rstrip(os.sep)) == 'word':
            word_dir = aux_dir
        else:
            return results
    candidates = [
        ('numbering.xml', 'word/numbering.xml'),
        ('comments.xml', 'word/comments.xml'),
        ('footnotes.xml', 'word/footnotes.xml'),
        ('endnotes.xml', 'word/endnotes.xml'),
    ]
    for label, rel in candidates:
        path = os.path.join(word_dir, os.path.basename(rel))
        if os.path.exists(path):
            issues = _scan_aux_xml_for_remnants(path, source_language, label)
            results[label] = issues
    # Headers and footers: pick up any headerN.xml / footerN.xml
    for fname in sorted(os.listdir(word_dir)):
        if (fname.startswith('header') or fname.startswith('footer')) \
                and fname.endswith('.xml'):
            path = os.path.join(word_dir, fname)
            issues = _scan_aux_xml_for_remnants(path, source_language, fname)
            results[fname] = issues
    return results

# ======================================================================
# MAIN
# ======================================================================

def check(xml_path, verbose=False, source_json=None, variant='uk',
          source_language=None, aux_dir=None, original_xml=None):
    tree = etree.parse(xml_path)
    root = tree.getroot()

    source_data = None
    if source_json:
        with open(source_json, 'r', encoding='utf-8') as f:
            source_data = json.load(f)

    # The UNTRANSLATED body, for the checks that must not report an anomaly the
    # document arrived with. Optional: without it those checks behave exactly as
    # before and say below that they could not tell inherited from introduced.
    source_root = None
    if original_xml:
        source_root = etree.parse(original_xml).getroot()

    # Auto-detect source language from paragraphs.json if not provided.
    if not source_language and source_data:
        sample = ' '.join(
            (p.get('text') or '') for p in source_data[:60]
        )
        source_language = detect_language(sample)

    source_lang_label = (source_language or 'source').lower() + '_remnants'

    checks = [
        ('spacing', check_spacing),
        ('definition_boundaries', check_definition_boundaries),
        ('double_punctuation', check_double_punctuation),
        ('terminology', check_terminology),
        ('standalone_financing', check_standalone_financing),
        ('duplicates', check_duplicates),
        ('missing_quotes', check_quotes),
        (source_lang_label, lambda r, v: check_source_remnants(r, v, source_language)),
        ('titles_headers', check_titles),
        ('word_order', check_word_order),
        ('internal_article_refs', check_article_refs),
        ('that_precedes_follows', check_that_precedes),
        ('formatting', check_formatting),
        ('numbering', lambda r, v: check_numbering(r, v, source_root)),
        ('definition_order', check_definition_order),
    ]

    # Spelling check is variant-dependent (UK is the hardcoded default).
    if variant == 'us':
        checks.append(('uk_spelling', check_uk_spelling))
    else:
        checks.append(('us_spelling', check_us_spelling))

    results = {}
    total = 0
    for name, fn in checks:
        issues = fn(root, verbose)
        results[name] = issues
        total += len(issues)

    # Truncation check (needs different signature)
    trunc_issues = check_truncation(root, verbose, source_data)
    results['truncation'] = trunc_issues
    total += len(trunc_issues)

    # scan auxiliary XML files for source-language remnants if
    # --aux-dir was supplied. The full quality_check rule set runs only
    # on document.xml; this catches calques and untranslated source-
    # language text in headers/footers/numbering/comments that
    # previously slipped past quality_check entirely.
    aux_results = {}
    if aux_dir:
        aux_results = check_aux_files(aux_dir, source_language, verbose)
        for aux_label, aux_issues in aux_results.items():
            key = f'aux_{aux_label}'
            results[key] = aux_issues
            total += len(aux_issues)

    # Print summary
    print(f"\nQuality Check: {xml_path}")
    print(f"{'='*60}")
    for name, issues in results.items():
        status = 'CLEAN' if not issues else f'{len(issues)} issues'
        print(f"  {name:30s} {status}")
        if verbose and issues:
            for iss in issues[:5]:
                print(f"    -> {iss}")
            if len(issues) > 5:
                print(f"    ... and {len(issues)-5} more")
    print(f"{'='*60}")
    print(f"  {'TOTAL':30s} {total} issues")

    # SAY WHEN A COMPARISON DID NOT HAPPEN. The numbering rule reads structure the
    # pipeline never translates, so without the untranslated body it cannot tell an
    # anomaly the document ARRIVED with from one introduced here -- and on the
    # recorded corpus every such anomaly was inherited. A check that silently does
    # nothing is the failure shape this branch repairs twice over (F15, C9), so this
    # one announces the gap instead of leaving the operator to infer it.
    if results.get('numbering') and source_root is None:
        print(f"\n  NOTE: numbering reported {len(results['numbering'])} issue(s) and "
              "--original was not\n        supplied, so it cannot tell an anomaly "
              "INHERITED from the source document\n        from one introduced by the "
              "pipeline. Re-run with --original <original document.xml>\n        before "
              "treating these as ours.")

    if total == 0:
        print("\n  *** PASSED: Document is ready for delivery ***")
    else:
        print(f"\n  *** FAILED: {total} issues must be resolved ***")

    return results

if __name__ == '__main__':
    import argparse
    ap = argparse.ArgumentParser(
        description='Quality check for a translated legal document.xml.',
        epilog=(
            "Note: --variant defaults to 'uk'. Only pass --variant us if the "
            "user's original prompt explicitly requested US English.\n"
            "Note: --language overrides auto-detection from paragraphs.json. "
            f"Supported: {', '.join(sorted(SUPPORTED_LANGUAGES))}"
        ),
    )
    ap.add_argument('xml_path', help='Path to the translated document.xml')
    ap.add_argument('--verbose', action='store_true',
                    help='Print the first few issues per check.')
    ap.add_argument('--with-source', dest='source_json', default=None,
                    help='paragraphs.json (enables truncation check by length comparison).')
    ap.add_argument('--variant', choices=('uk', 'us'), default='uk',
                    help='English variant for the spelling check (default: uk).')
    # --language is the canonical flag name across the skill. --source-language
    # is kept as a backward-compatible alias for older scripts and docs.
    ap.add_argument('--language', '--source-language', dest='source_language',
                    default=None,
                    help='Source language (overrides auto-detection from paragraphs.json).')
    ap.add_argument('--original', dest='original_xml', default=None,
                    help='The UNTRANSLATED word/document.xml. Lets the numbering '
                         'check report only anomalies the source did not already '
                         'have — a legacy .doc conversion rewrites list structure '
                         'wholesale, and those anomalies are not the translation\'s. '
                         'Strongly recommended whenever numbering is reported.')
    ap.add_argument('--aux-dir', dest='aux_dir', default=None,
                    help='Rev12+: directory containing translated auxiliary XML '
                         '(numbering.xml, headerN.xml, footerN.xml, comments.xml, '
                         'footnotes.xml, endnotes.xml). Pass either the parent of '
                         'word/ or word/ itself. Auxiliary files are scanned for '
                         'source-language remnants. Strongly recommended.')
    args = ap.parse_args()

    source_language = args.source_language.lower() if args.source_language else None

    results = check(args.xml_path, verbose=args.verbose,
                    source_json=args.source_json,
                    variant=args.variant, source_language=source_language,
                    aux_dir=args.aux_dir, original_xml=args.original_xml)

    # STEP 9's VERDICT HAS TO BE ABLE TO LEAVE THIS SCRIPT, and until now it
    # could not. There was no sys.exit for the issues case, so this script
    # exited 0 whatever it found — and verify_diligence.check_step_9, which
    # branches on `returncode == 0`, therefore reported PASS on documents
    # carrying 8 and 32 unresolved issues. Its comment said "quality_check
    # exits non-zero when issues are reported", which was the opposite of true.
    #
    # TWO MANDATORY STEPS DEPENDED ON THIS VERDICT AND NEITHER COULD SEE IT.
    # Step 7's only cover anywhere in the tree is the definition_order check
    # above; it reported into a return value nobody read. Step 6 has no check
    # at all. So one missing exit code silently removed two steps from the
    # end-of-pipeline audit.
    #
    # The total is recomputed the way check() computes it, over the same dict.
    # The loop raises rather than asserting, because `assert` is stripped under
    # `python -O` and because a value that is not a list would otherwise be
    # summed by character count — a wrong exit code instead of a loud failure.
    total = 0
    for _name, _issues in results.items():
        if not isinstance(_issues, list):
            raise TypeError(
                f'quality_check: results[{_name!r}] is '
                f'{type(_issues).__name__}, not a list of issues — the exit '
                'code below cannot be trusted'
            )
        total += len(_issues)

    # 2 = FAIL, matching the 0/1/2 contract verify_diligence documents. Nothing
    # is printed here: the summary above already ends with either
    # "*** PASSED: Document is ready for delivery ***" or
    # "*** FAILED: N issues must be resolved ***", and stdout is deliberately
    # left byte-identical so the change is provably an exit code and nothing
    # else. Step 9's own doc routes what happens next — five attempts, then
    # rule 5a if the finding is a false positive, rule 5b if it is real and no
    # compliant repair exists.
    sys.exit(2 if total else 0)

# === SKILL FILE COMPLETE ===
