"""Apply translations from paragraphs.json onto original document.xml using TEXT MATCHING.

Instead of mapping by idx (which is wrong for this document due to extraction artifacts),
this script matches each paragraphs.json entry to the original paragraph whose Italian
text matches the entry's 'text' field. This handles any offset or misalignment.

For duplicate Italian texts (e.g., "[●]", "PEC: [●]"), it uses positional order:
first occurrence matches first duplicate, second matches second, etc.
"""
import sys
import os
import re
import io
import json
import zipfile
import copy
import xml.etree.ElementTree as ET

# Import the shared per-language marker module. It lives in the same scripts/
# directory, so we extend sys.path before importing.
_SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)
from source_language_markers import (  # noqa: E402
    scan_remnants,
    detect_language,
    SUPPORTED_LANGUAGES,
)

def _check_self_integrity():
    """Rev27: detect install-time truncation by reading the script's own
    source and checking for the sentinel at the bottom. Marketplace
    install pipelines have been observed cutting files mid-content; the
    sentinel + check turn that into a clear RE-INSTALL message before
    any work is done."""
    try:
        with open(os.path.abspath(__file__), 'r', encoding='utf-8') as f:
            content = f.read()
    except OSError:
        return  # Can't check; proceed
    if '\n# === SKILL FILE COMPLETE ===' not in content:
        msg = (
            "\n" + "=" * 60 + "\n"
            "[skill] FILE INTEGRITY CHECK FAILED — script truncated.\n"
            f"  File: {os.path.abspath(__file__)}\n"
            f"  Size: {len(content):,} bytes (sentinel marker missing).\n"
            "\n"
            "  The skill install copy is incomplete. The .skill / .zip\n"
            "  archive is intact; only the local install was truncated\n"
            "  during marketplace transfer. Re-install the skill from\n"
            "  the archive. If the problem persists across re-installs,\n"
            "  contact support.\n"
            + "=" * 60 + "\n"
        )
        print(msg, file=sys.stderr)
        sys.exit(3)


_check_self_integrity()

W = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
# Markup-compatibility namespace. `mc:AlternateContent` is a run child that can carry the
# only copy of a drawing's fallback content, and it is NOT in the w: namespace -- so a
# preserved-tag list written with W-prefixed names alone can never match it.
MC = '{http://schemas.openxmlformats.org/markup-compatibility/2006}'

# Static namespace list (safety net). Primary mechanism is
# register_document_namespaces() — dynamically registers what's on the
# source document's root. w16* family added for Word 2023 compat.
NAMESPACES = {
    'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main',
    'r': 'http://schemas.openxmlformats.org/officeDocument/2006/relationships',
    'o': 'urn:schemas-microsoft-com:office:office',
    'v': 'urn:schemas-microsoft-com:vml',
    'w10': 'urn:schemas-microsoft-com:office:word',
    'wp': 'http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing',
    'pic': 'http://schemas.openxmlformats.org/drawingml/2006/picture',
    'wps': 'http://schemas.microsoft.com/office/word/2010/wordprocessingShape',
    'wpg': 'http://schemas.microsoft.com/office/word/2010/wordprocessingGroup',
    'mc': 'http://schemas.openxmlformats.org/markup-compatibility/2006',
    'wp14': 'http://schemas.microsoft.com/office/word/2010/wordprocessingDrawing',
    'w14': 'http://schemas.microsoft.com/office/word/2010/wordml',
    'w15': 'http://schemas.microsoft.com/office/word/2012/wordml',
    'a': 'http://schemas.openxmlformats.org/drawingml/2006/main',
    'wne': 'http://schemas.microsoft.com/office/word/2006/wordml',
    # Word 2015-2024 TC / content-control metadata (w16* family).
    'w16': 'http://schemas.microsoft.com/office/word/2018/wordml',
    'w16cex': 'http://schemas.microsoft.com/office/word/2018/wordml/cex',
    'w16cid': 'http://schemas.microsoft.com/office/word/2016/wordml/cid',
    'w16du': 'http://schemas.microsoft.com/office/word/2023/wordml/word16du',
    'w16sdtdh': 'http://schemas.microsoft.com/office/word/2020/wordml/sdtdatahash',
    'w16sdtfl': 'http://schemas.microsoft.com/office/word/2024/wordml/sdtformatlock',
    'w16se': 'http://schemas.microsoft.com/office/word/2015/wordml/symex',
}
for prefix, uri in NAMESPACES.items():
    ET.register_namespace(prefix, uri)


def register_document_namespaces(orig_xml_bytes):
    """Register xmlns:PREFIX declarations from the source document's root
    so ET doesn't synthesize incompatible ns3:/ns4: prefixes at write time.
    Covers namespaces beyond the static NAMESPACES list."""
    try:
        head = orig_xml_bytes[:8000].decode('utf-8', errors='replace')
    except Exception:
        return
    m = re.search(r'<w:document\b([^>]*)>', head, re.DOTALL)
    if not m:
        return
    attrs = m.group(1)
    registered = []
    for pm in re.finditer(r'xmlns:([A-Za-z_][\w.-]*)\s*=\s*"([^"]+)"', attrs):
        prefix, uri = pm.group(1), pm.group(2)
        try:
            ET.register_namespace(prefix, uri)
            registered.append(prefix)
        except Exception:
            pass
    if registered:
        print(f"  Registered {len(registered)} namespace prefix(es) from source: {registered}")

def get_paragraph_text(p_elem):
    """Get plain text from a paragraph. emits \\n at plain
    <w:br/> (mirrors extract_paragraphs.py for matching). Page breaks
    emit no \\n"""
    pieces = []
    for child in p_elem.iter():
        tag = child.tag
        if tag == f'{W}t' and child.text:
            pieces.append(child.text)
        elif tag == f'{W}br':
            br_type = child.get(f'{W}type', '')
            if br_type != 'page':
                pieces.append('\n')
    return ''.join(pieces).strip()

def normalize_text(t):
    """Normalize text for matching: collapse whitespace, strip."""
    return re.sub(r'\s+', ' ', t).strip()

# The two characters that are whitespace to Python and STRUCTURE to Word: this script turns
# them into <w:tab/> and <w:br/> further down.
_BOUNDARY_SEPARATORS = ('\t', '\n')

def _strip_keeping_separators(s):
    """strip(), except a leading or trailing tab or newline SURVIVES.

    FINDING F27 — ONE LINE OF CODE, THREE KINDS OF BOUNDARY STRUCTURE DESTROYED, ACROSS TWO
    DOCUMENTS. `en` was stripped unconditionally, so any tab or newline the operator authored
    at the START or END of the string was destroyed before the code that converts \\t and \\n
    into <w:tab/> and <w:br/> ever ran. INTERIOR separators worked; BOUNDARY separators
    silently vanished -- which is the worst shape a defect can take, because the feature
    demonstrably works when you test it in the middle.

    D01: a leading tab, twice. The visible consequence was a two-column signature block whose
    rows 1 and 4 started at the left margin while rows 2 and 3 kept their leading tab (that
    one happened to sit in its own preserved run), so the block was misaligned against the two
    lines directly above it.
    D10: a trailing newline on one party block and a leading newline on another.

    NO GATE NOTICED, and could not: `validate_apply --strict` compares TOKENS, and a lost tab
    or line break destroys no tokens. Both documents were caught only because the operator had
    adopted diffing declared `en` against the applied document.xml as a habit -- a check no
    step document asks for.

    A ZWSP (U+200B) survives this untouched, as it must: it is Unicode category Cf, so
    `isspace()` is False. That is the property the non-Latin tracked-change hybrid depends on.
    """
    if not s:
        return s
    i, j = 0, len(s)
    while i < j and s[i].isspace() and s[i] not in _BOUNDARY_SEPARATORS:
        i += 1
    while j > i and s[j - 1].isspace() and s[j - 1] not in _BOUNDARY_SEPARATORS:
        j -= 1
    return s[i:j]

def get_default_rpr_et(p_elem):
    """Get run properties from the first text-bearing run."""
    for r in p_elem.findall(f'{W}r'):
        t = r.find(f'{W}t')
        if t is not None and t.text and t.text.strip():
            rpr = r.find(f'{W}rPr')
            if rpr is not None:
                return copy.deepcopy(rpr)
    return None

def is_subheader_paragraph(en_text, original_runs):
    """Detect if a paragraph is a sub-header that should preserve bold."""
    if not original_runs:
        return False
    word_count = len(en_text.split())
    if word_count > 10:
        return False
    has_bold = False
    has_non_bold_text = False
    for run in original_runs:
        text = run.get("text", "").strip()
        if not text:
            continue
        if run.get("bold"):
            has_bold = True
        else:
            has_non_bold_text = True
    return has_bold and not has_non_bold_text

def has_track_changes(p_elem):
    """True if paragraph contains <w:ins>/<w:del>/<w:moveFrom>/<w:moveTo>.
    TC paragraphs take a separate apply path (apply_trackchanges_inplace)
    so the wrapper structure is preserved."""
    for tag in ('ins', 'del', 'moveFrom', 'moveTo'):
        if p_elem.find(f'.//{W}{tag}') is not None:
            return True
    return False

def snap_to_whitespace(pos, text, window=20):
    """Move pos to the nearest whitespace within +/- window characters,
    preferring positions AFTER whitespace so the next segment starts
    with a full word. Returns the original pos if no whitespace is
    nearby."""
    if pos <= 0 or pos >= len(text):
        return max(0, min(pos, len(text)))
    for off in range(0, window + 1):
        for candidate in (pos - off, pos + off):
            if 0 < candidate <= len(text) and text[candidate - 1] == ' ':
                return candidate
    return pos

def distribute_text_across_elements(elements, text, preserve_source_boundary_whitespace=True):
    """Distribute text proportionally across w:t/w:delText elements,
    snapping boundaries to whitespace. Restores source-side leading/
    trailing whitespace on first/last elements if upstream .strip()
    lost it"""
    if not elements or not text:
        return

    # Capture boundary whitespace from the source BEFORE we overwrite .text.
    first_src = elements[0].text or ''
    last_src = elements[-1].text or ''
    src_leading_ws = ''
    src_trailing_ws = ''
    if preserve_source_boundary_whitespace:
        # Only preserve spaces/tabs (not newlines) that were actually in the source.
        m_lead = re.match(r'^[ \t]+', first_src)
        if m_lead:
            src_leading_ws = m_lead.group(0)
        m_trail = re.search(r'[ \t]+$', last_src)
        if m_trail:
            src_trailing_ws = m_trail.group(0)

    src_lengths = [len(e.text or '') for e in elements]
    total_src = sum(src_lengths)
    if total_src == 0:
        # All elements empty — put everything in the first one
        elements[0].text = text
        if text and (text[0] == ' ' or text[-1] == ' '):
            elements[0].set('{http://www.w3.org/XML/1998/namespace}space', 'preserve')
        return

    text_len = len(text)
    boundaries = [0]
    cum = 0
    for length in src_lengths[:-1]:
        cum += length
        ideal = round(cum / total_src * text_len)
        boundaries.append(snap_to_whitespace(ideal, text))
    boundaries.append(text_len)

    # Ensure monotonic
    for i in range(1, len(boundaries)):
        if boundaries[i] < boundaries[i - 1]:
            boundaries[i] = boundaries[i - 1]

    for i, elem in enumerate(elements):
        slice_text = text[boundaries[i]:boundaries[i + 1]]
        # Restore source boundary whitespace if upstream .strip() removed it.
        if preserve_source_boundary_whitespace:
            if i == 0 and src_leading_ws and not slice_text.startswith((' ', '\t')):
                slice_text = src_leading_ws + slice_text
            if i == len(elements) - 1 and src_trailing_ws and not slice_text.endswith((' ', '\t')):
                slice_text = slice_text + src_trailing_ws
        elem.text = slice_text
        if slice_text and (slice_text[0] == ' ' or slice_text[-1] == ' '):
            elem.set('{http://www.w3.org/XML/1998/namespace}space', 'preserve')

def apply_trackchanges_inplace(orig_p, en_text, it_text,
                               en_deleted=None, it_deleted=None,
                               en_segments=None,
                               en_runs_spec=None,
                               original_runs=None):
    """Apply English translation to a tracked-change paragraph in place.
    Segment-aware (en_segments) or legacy proportional fallback. Returns
    True on success, False if the paragraph has no text content.

    rev38: en_runs_spec and original_runs are read by the bold-off-override
    decision below. The override unconditionally applied <w:b w:val="0"/>
    on every run of any non-heading-styled TC paragraph, which strips
    intentional bold from heading paragraphs that get their bold from
    run-level <w:b/> rather than from a Heading-N pStyle (the Japanese-MOU
    Clause 3 pattern in the rev38 post-mortem). Two new bypasses:

    1. If the translator emitted en_runs_spec with at least one entry
       whose `bold: True`, the operator has explicitly authored bold for
       this paragraph — respect that authorial intent and skip the
       blanket bold-off.
    2. If every source run in `original_runs` (the JSON `runs` array)
       has `bold: True`, the source paragraph is *uniformly* bold — a
       strong signal that bold is the genuine paragraph formatting (not
       a TC-styling leak), so skip the blanket bold-off.

    These bypasses are conservative: paragraphs with NO en_runs and a
    mix of bold and non-bold source runs (the original Italian-body-text
    case the override was written for) still get the blanket bold-off,
    so the original defect class — bold leak from <w:ins> styling into
    body text — remains defended.
    """
    # Build parent map for is_inside_del
    parent_map = {c: p for p in orig_p.iter() for c in p}

    def is_inside_del(elem):
        current = elem
        while current is not None and current is not orig_p:
            if current.tag == f'{W}del':
                return True
            current = parent_map.get(current)
        return False

    # Heading detection: only truly short heading-style paragraphs keep bold
    ppr = orig_p.find(f'{W}pPr')
    is_heading = False
    full_text = ''.join(t.text or '' for t in orig_p.iter(f'{W}t'))
    if ppr is not None:
        style_elem = ppr.find(f'{W}pStyle')
        if style_elem is not None:
            sv = (style_elem.get(f'{W}val') or '').lower()
            if any(h in sv for h in ('heading', 'cmsor', 'title', 'titre')):
                if len(full_text.strip()) < 120:
                    is_heading = True

    # rev38: two additional bypasses for the bold-off-override.
    # If neither pStyle-based heading detection fires AND the paragraph is
    # genuinely bold (operator-authored or uniformly source-bold), skip the
    # bold-off. See docstring above + rev38 post-mortem / Defect 4.
    skip_bold_override = False
    if en_runs_spec:
        # Operator authored at least one run with bold=True → respect intent.
        try:
            for seg in en_runs_spec:
                if isinstance(seg, dict) and seg.get('bold') is True:
                    skip_bold_override = True
                    break
        except (TypeError, AttributeError):
            pass
    if not skip_bold_override and original_runs:
        # Every source run is bold → genuine paragraph-bold. Filter out
        # zero-text runs (e.g. structural runs) before checking — only
        # text-bearing runs vote.
        try:
            text_runs = [r for r in original_runs
                         if isinstance(r, dict) and r.get('text')]
            if text_runs and all(
                    r.get('bold') is True for r in text_runs):
                skip_bold_override = True
        except (TypeError, AttributeError):
            pass

    # ---- Segment-aware mode ----
    if en_segments:
        # Build XML segments parallel to en_segments: regular/ins/del/
        # ins_then_del. The phantom ins_then_del case (ins wrapping
        # delText) is emitted by extract as a distinct segment so the
        # translator's en lands in the nested delText.
        xml_segs = []  # list of {'type': str, 'elements': [ET.Element]}
        for child in orig_p:
            ctag = child.tag.split('}')[1] if '}' in child.tag else child.tag
            if ctag == 'pPr':
                continue
            if ctag == 'del':
                dts = list(child.iter(f'{W}delText'))
                seg_text = ''.join(dt.text or '' for dt in dts)
                if seg_text or dts:
                    xml_segs.append({'type': 'del', 'elements': dts})
            elif ctag == 'ins':
                ts = list(child.iter(f'{W}t'))
                seg_text = ''.join(t.text or '' for t in ts)
                if seg_text or ts:
                    xml_segs.append({'type': 'ins', 'elements': ts})
                else:
                    # No top-level <w:t> under this <w:ins>. Check for
                    # a nested <w:del> — the phantom ins_then_del shape.
                    nested_dts = list(child.iter(f'{W}delText'))
                    nested_text = ''.join(dt.text or '' for dt in nested_dts)
                    if nested_text:
                        xml_segs.append({
                            'type': 'ins_then_del',
                            'elements': nested_dts,
                        })
            elif ctag == 'r':
                ts = list(child.iter(f'{W}t'))
                seg_text = ''.join(t.text or '' for t in ts)
                if seg_text or ts:
                    xml_segs.append({'type': 'regular', 'elements': ts})

        # Merge consecutive XML segments of the same type, recording
        # wrapper boundaries for ZWSP injection. See `skill-docs/04-translate.md`
        # "Scrambled / character-fragmented whole-word edits".
        merged_xml = []
        for xs in xml_segs:
            if merged_xml and merged_xml[-1]['type'] == xs['type']:
                # Record the wrapper-boundary element index so we can
                # inject a ZWSP there after distribute.
                merged_xml[-1]['wrapper_boundaries'].append(
                    len(merged_xml[-1]['elements'])
                )
                merged_xml[-1]['elements'].extend(xs['elements'])
            else:
                merged_xml.append({
                    'type': xs['type'],
                    'elements': list(xs['elements']),
                    'wrapper_boundaries': [],
                })

        # Match en_segments to xml segments by type sequence.
        # Both should have the same type pattern; if not, fall through to legacy.
        en_types = [s['type'] for s in en_segments]
        xml_types = [s['type'] for s in merged_xml]

        if en_types == xml_types:
            applied = False
            for en_seg, xml_seg in zip(en_segments, merged_xml):
                # 'en' missing/None: leave source text. '' or whitespace:
                # clear run (coalesce-to-first-segment trick — see
                # `skill-docs/04-translate.md` "Scrambled edits"). Else: distribute.
                if 'en' not in en_seg or en_seg.get('en') is None:
                    continue
                # rev42: keep the operator's boundary whitespace alive into
                # the rendered document. `en_seg_stripped` is used ONLY for
                # the "is the segment empty?" branch (en="" / en="  " both
                # mean clear-this-segment). When non-empty, distribute the
                # UNSTRIPPED text so leading/trailing spaces the operator
                # authored as element-boundary separators survive into the
                # `<w:t>` / `<w:delText>` content. This eliminates the
                # rev41 structural conflict where:
                #   (a) apply.strip removed operator boundary whitespace,
                #   (b) source-restoration only worked for European scripts
                #       (non-Latin <w:t> has no inter-word whitespace),
                #   (c) fix_spacing later inserted spaces at element
                #       boundaries to repair the visible glue, and
                #   (d) the post-strip drift gate failed because declared
                #       and applied tokenisations diverged.
                # By preserving operator whitespace here, applied text
                # matches declared at apply time AND fix_spacing rarely
                # needs to fire (operator's separators are already in
                # the document). When fix_spacing DOES fire on a boundary
                # the operator left glued, validate_apply's --post-
                # spacing-fix simulation (rev42) keeps the post-strip
                # drift gate symmetric.
                en_seg_stripped = (en_seg['en'] or '').strip()
                if not xml_seg['elements']:
                    continue
                if en_seg_stripped:
                    en_seg_text = en_seg['en']
                    distribute_text_across_elements(xml_seg['elements'], en_seg_text)
                    # Inject ZWSP at wrapper boundaries inside cluster-
                    # merged xml_segs to defeat fix_spacing's alpha+alpha
                    # rule. Skip if edges already have non-alpha chars.
                    boundaries = xml_seg.get('wrapper_boundaries') or []
                    for boundary_idx in boundaries:
                        if boundary_idx <= 0 or boundary_idx >= len(xml_seg['elements']):
                            continue
                        prev_elem = xml_seg['elements'][boundary_idx - 1]
                        curr_elem = xml_seg['elements'][boundary_idx]
                        prev_text = prev_elem.text or ''
                        curr_text = curr_elem.text or ''
                        if not prev_text or not curr_text:
                            continue
                        pc = prev_text[-1]
                        cc = curr_text[0]
                        if pc.isalpha() and cc.isalpha():
                            curr_elem.text = '\u200b' + curr_text
                            curr_elem.set(
                                '{http://www.w3.org/XML/1998/namespace}space',
                                'preserve')
                else:
                    # Explicit empty-string request: clear every element in this
                    # XML segment. Preserves the w:t / w:delText element itself
                    # (so the w:ins / w:del wrapper survives for subsequent
                    # strip_noop / coalesce passes) but drops the source text.
                    for el in xml_seg['elements']:
                        el.text = ''
                applied = True
            if not applied:
                return False
        else:
            print(f"    WARNING: segment type mismatch: en={en_types} vs xml={xml_types}")
            print(f"    Falling back to legacy proportional distribution.")
            # Fall through to legacy mode below
            en_segments = None

    # ---- Legacy proportional mode (fallback) ----
    if not en_segments:
        active_ts = []
        for t in orig_p.iter(f'{W}t'):
            if not is_inside_del(t):
                active_ts.append(t)
        deleted_dts = list(orig_p.iter(f'{W}delText'))

        if not active_ts and not deleted_dts:
            return False

        if active_ts and en_text:
            distribute_text_across_elements(active_ts, en_text)
        if deleted_dts and en_deleted:
            distribute_text_across_elements(deleted_dts, en_deleted)
        elif deleted_dts and not en_deleted:
            del_src = ''.join(dt.text or '' for dt in deleted_dts)
            if del_src.strip():
                print(f"    WARNING: TC paragraph has untranslated deleted text: {del_src[:80]}...")

    # --- Fix bold leak ---
    RPR_ORDER = [
        'rStyle', 'rFonts', 'b', 'bCs', 'i', 'iCs', 'caps', 'smallCaps',
        'strike', 'dstrike', 'outline', 'shadow', 'emboss', 'imprint',
        'noProof', 'snapToGrid', 'vanish', 'webHidden', 'color', 'spacing',
        'w', 'kern', 'position', 'sz', 'szCs', 'highlight', 'u', 'effect',
        'bdr', 'shd', 'fitText', 'vertAlign', 'rtl', 'cs', 'em', 'lang',
    ]
    if not is_heading and not skip_bold_override:
        val_attr = f'{W}val'
        for r_elem in orig_p.iter(f'{W}r'):
            rpr = r_elem.find(f'{W}rPr')
            if rpr is None:
                rpr = ET.Element(f'{W}rPr')
                r_elem.insert(0, rpr)
            b_elem = rpr.find(f'{W}b')
            if b_elem is None:
                b_elem = ET.Element(f'{W}b')
                b_order = RPR_ORDER.index('b')
                inserted = False
                for i, existing in enumerate(rpr):
                    ex_tag = existing.tag.split('}')[1] if '}' in existing.tag else existing.tag
                    ex_order = RPR_ORDER.index(ex_tag) if ex_tag in RPR_ORDER else len(RPR_ORDER)
                    if ex_order > b_order:
                        rpr.insert(i, b_elem)
                        inserted = True
                        break
                if not inserted:
                    rpr.append(b_elem)
            b_elem.set(val_attr, '0')

    # post-pass — collapse adjacent ins+del with identical English
    # text (source-language-only orthographic edits) and absorb pure-
    # whitespace ins/del wrappers into adjacent regulars. Both patterns
    # have no English meaning and produce validate_apply false-positives
    # when left as TC structure.
    _collapse_orthographic_tc_pairs(orig_p)
    _absorb_whitespace_only_tc_wrappers(orig_p)

    return True

def auto_detect_formatting(en_text, original_runs):
    """Auto-detect which parts of the English text should be bold/italic."""
    if is_subheader_paragraph(en_text, original_runs):
        return [{"start": 0, "end": len(en_text), "bold": True, "italic": False}]

    def_pattern = re.compile(
        r'([\u201c"\u201e])'
        r'([^"\u201d\u201c]+?)'
        r'([\u201d"])'
        r'(\s*)'
        r'(means|shall mean|has the meaning|indicates)',
        re.IGNORECASE
    )

    bold_ranges = []
    for m in def_pattern.finditer(en_text):
        bold_ranges.append((m.start(2), m.end(2)))

    if not bold_ranges:
        return [{"start": 0, "end": len(en_text), "bold": False, "italic": False}]

    segments = []
    pos = 0
    for b_start, b_end in sorted(bold_ranges):
        if pos < b_start:
            segments.append({"start": pos, "end": b_start, "bold": False, "italic": False})
        segments.append({"start": b_start, "end": b_end, "bold": True, "italic": False})
        pos = b_end
    if pos < len(en_text):
        segments.append({"start": pos, "end": len(en_text), "bold": False, "italic": False})

    return segments

def make_run_et(text, template_rpr, bold=False, italic=False):
    """Create a new w:r element with the given text and formatting."""
    r = ET.Element(f'{W}r')

    if template_rpr is not None:
        rpr = copy.deepcopy(template_rpr)
        # Strip w:lang elements — these carry the source-language tag (e.g. it-IT)
        # and cause Word to show "Changed to English (UK)" tracked changes on every run.
        # Removing them lets Word auto-detect the language from the English text.
        for lang_elem in list(rpr.findall(f'{W}lang')):
            rpr.remove(lang_elem)
    else:
        rpr = ET.SubElement(r, f'{W}rPr')

    # OOXML schema ordering for w:rPr children (ISO 29500-1 §17.3.2.28).
    # Word validates this ordering and shows "unreadable content" if violated.
    RPR_ORDER = [
        'rStyle', 'rFonts', 'b', 'bCs', 'i', 'iCs', 'caps', 'smallCaps',
        'strike', 'dstrike', 'outline', 'shadow', 'emboss', 'imprint',
        'noProof', 'snapToGrid', 'vanish', 'webHidden', 'color', 'spacing',
        'w', 'kern', 'position', 'sz', 'szCs', 'highlight', 'u', 'effect',
        'bdr', 'shd', 'fitText', 'vertAlign', 'rtl', 'cs', 'em', 'lang',
        'eastAsianLayout', 'specVanish', 'oMath',
    ]

    def insert_rpr_child(rpr_elem, new_child):
        """Insert a child element into rPr at the correct schema-ordered position."""
        new_tag = new_child.tag.split('}')[1] if '}' in new_child.tag else new_child.tag
        new_order = RPR_ORDER.index(new_tag) if new_tag in RPR_ORDER else len(RPR_ORDER)
        for i, existing in enumerate(rpr_elem):
            ex_tag = existing.tag.split('}')[1] if '}' in existing.tag else existing.tag
            ex_order = RPR_ORDER.index(ex_tag) if ex_tag in RPR_ORDER else len(RPR_ORDER)
            if ex_order > new_order:
                rpr_elem.insert(i, new_child)
                return
        rpr_elem.append(new_child)

    val_attr = f'{W}val'

    # Explicit bold override:
    #   bold=True  → emit <w:b/>             (turns bold ON, overriding any style that turns it off)
    #   bold=False → emit <w:b w:val="0"/>   (turns bold OFF, overriding any style that turns it on)
    #
    # We MUST emit the explicit off-override rather than simply omitting <w:b>, because paragraph
    # styles can inherit bold from basedOn parents (e.g. Cmsor2 → Cmsor1 → bold=1). If we omit <w:b>
    # in that case, the style's inherited bold shows through and the entire body renders bold.
    b_elem = rpr.find(f'{W}b')
    if b_elem is None:
        b_elem = ET.Element(f'{W}b')
        insert_rpr_child(rpr, b_elem)
    if bold:
        if val_attr in b_elem.attrib:
            del b_elem.attrib[val_attr]
    else:
        b_elem.set(val_attr, '0')

    # keep <w:bCs> paired with <w:b>. Bare <w:bCs/> defaults
    # to ON per ECMA-376; without this the rPr emits a contradiction
    # that get_bold_term reads as bold-on
    bcs_elem = rpr.find(f'{W}bCs')
    if bcs_elem is None:
        bcs_elem = ET.Element(f'{W}bCs')
        insert_rpr_child(rpr, bcs_elem)
    if bold:
        if val_attr in bcs_elem.attrib:
            del bcs_elem.attrib[val_attr]
    else:
        bcs_elem.set(val_attr, '0')

    # Same logic for italic — styles can inherit italic from basedOn parents, so omitting <w:i>
    # lets style italic leak through. Always emit an explicit override.
    i_elem = rpr.find(f'{W}i')
    if i_elem is None:
        i_elem = ET.Element(f'{W}i')
        insert_rpr_child(rpr, i_elem)
    if italic:
        if val_attr in i_elem.attrib:
            del i_elem.attrib[val_attr]
    else:
        i_elem.set(val_attr, '0')

    # same paired-off treatment for <w:iCs>.
    ics_elem = rpr.find(f'{W}iCs')
    if ics_elem is None:
        ics_elem = ET.Element(f'{W}iCs')
        insert_rpr_child(rpr, ics_elem)
    if italic:
        if val_attr in ics_elem.attrib:
            del ics_elem.attrib[val_attr]
    else:
        ics_elem.set(val_attr, '0')

    if template_rpr is not None:
        r.insert(0, rpr)

    t = ET.SubElement(r, f'{W}t')
    t.text = text
    if text and (text[0] == ' ' or text[-1] == ' '):
        t.set('{http://www.w3.org/XML/1998/namespace}space', 'preserve')

    return r

def _run_is_text_bearing(r):
    """Rev26: True if <w:r> has <w:t> or <w:delText> with text."""
    for child in r:
        tag = child.tag
        if tag in (f'{W}t', f'{W}delText') and child.text:
            return True
    return False

def _norm_ortho_text(s):
    """Rev28: strip ZWSP + surrounding whitespace for ortho-pair compare.
    Handles  hybrid bookends correctly"""
    if not s:
        return ''
    return s.replace('​', '').strip()

def _tc_text(elem):
    """Rev28: concatenate <w:t> + <w:delText> content inside elem (any
    depth). Used by the ortho-pair collapse to compare ins/del payload."""
    pieces = []
    for child in elem.iter():
        tag = child.tag
        if tag in (f'{W}t', f'{W}delText') and child.text:
            pieces.append(child.text)
    return ''.join(pieces)

def _is_orthographic_xml_pair(elem_a, elem_b):
    """Rev28: True if a/b are adjacent <w:ins>+<w:del> with identical
    normalised English text — source-language-only ortho edits."""
    tag_a = elem_a.tag.split('}')[-1] if '}' in elem_a.tag else elem_a.tag
    tag_b = elem_b.tag.split('}')[-1] if '}' in elem_b.tag else elem_b.tag
    if {tag_a, tag_b} != {'ins', 'del'}:
        return False
    norm_a = _norm_ortho_text(_tc_text(elem_a))
    norm_b = _norm_ortho_text(_tc_text(elem_b))
    return bool(norm_a) and norm_a == norm_b

def _collapse_orthographic_tc_pairs(orig_p):
    """Rev28: collapse adjacent ins+del pairs with identical English
    text into a single regular <w:r>. Eliminates the
    proactivelyproactively false positive in validate_apply"""
    children = list(orig_p)
    new_children = []
    i = 0
    while i < len(children):
        cur = children[i]
        nxt = children[i + 1] if i + 1 < len(children) else None
        if nxt is not None and _is_orthographic_xml_pair(cur, nxt):
            # Build replacement: a regular <w:r> with the merged text.
            merged_text = _norm_ortho_text(_tc_text(cur))
            new_r = ET.Element(f'{W}r')
            t = ET.SubElement(new_r, f'{W}t')
            t.text = merged_text
            if merged_text and (merged_text[0] == ' '
                                or merged_text[-1] == ' '):
                t.set('{http://www.w3.org/XML/1998/namespace}space',
                      'preserve')
            new_children.append(new_r)
            i += 2
        else:
            new_children.append(cur)
            i += 1
    if len(new_children) == len(children):
        return  # No collapse needed.
    for child in children:
        orig_p.remove(child)
    for child in new_children:
        orig_p.append(child)

def _absorb_whitespace_only_tc_wrappers(orig_p):
    """Rev28: absorb pure-whitespace ins/del into adjacent regular run.
    ZWSP-only/ZWSP-bearing wrappers are preserved (boundary
    scaffolding)"""
    children = list(orig_p)
    to_remove = []
    for i, child in enumerate(children):
        tag = child.tag.split('}')[-1] if '}' in child.tag else child.tag
        if tag not in ('ins', 'del'):
            continue
        text = _tc_text(child)
        if not text:
            continue
        if '​' in text:
            continue  # ZWSP-only or ZWSP-bearing — leave alone
        if text.strip():
            continue  # Has non-whitespace content — leave alone
        # Pure whitespace; absorb into adjacent regular run.
        absorbed = False
        # Prefer preceding regular w:r.
        for j in range(i - 1, -1, -1):
            prev = children[j]
            ptag = prev.tag.split('}')[-1] if '}' in prev.tag else prev.tag
            if ptag == 'r':
                # Append whitespace to the LAST <w:t> in this run.
                ts = list(prev.iter(f'{W}t'))
                if ts:
                    last_t = ts[-1]
                    last_t.text = (last_t.text or '') + text
                    last_t.set(
                        '{http://www.w3.org/XML/1998/namespace}space',
                        'preserve')
                    absorbed = True
                break
        if not absorbed:
            # Try following regular w:r.
            for j in range(i + 1, len(children)):
                nxt = children[j]
                ntag = nxt.tag.split('}')[-1] if '}' in nxt.tag else nxt.tag
                if ntag == 'r':
                    ts = list(nxt.iter(f'{W}t'))
                    if ts:
                        first_t = ts[0]
                        first_t.text = text + (first_t.text or '')
                        first_t.set(
                            '{http://www.w3.org/XML/1998/namespace}space',
                            'preserve')
                        absorbed = True
                    break
        if absorbed:
            to_remove.append(child)
    for child in to_remove:
        orig_p.remove(child)

_PRESERVED_RUN_CHILDREN = (
    # --- present since rev26 ---
    f'{W}drawing', f'{W}pict',
    f'{W}fldChar', f'{W}instrText',
    f'{W}lastRenderedPageBreak',
    f'{W}tab',
    # --- BRANCH 6, option 1, clause 1. Every one of these is a POINTER: destroy it and the
    # thing it points at is still in the package and reachable from nothing. That asymmetry
    # is why they were invisible -- the auxiliary part is translated, intact and perfect, so
    # every content check passes while the footnote appears on no page.
    f'{W}footnoteReference',   # A1. D05 1->0, D09 2->0. Five gates blind to it by
                               # construction, then Step 11a printed "Deliver with
                               # confidence". Nothing anywhere checked referential
                               # integrity between document.xml and the aux parts.
    f'{W}endnoteReference',    # the same structure with no recorded instance yet. Added
                               # because leaving it out would be a fourth special case
                               # waiting to become a fifth finding.
    f'{W}commentReference',    # A2. D02 28->14, D08 13->9, all bodies still in
                               # comments.xml. Two of D08's four lost comments were
                               # substantive; Wouter found this unaided from the page.
    f'{W}object',              # embedded OLE object.
    f'{W}sym',                 # a symbol-font character. Related to A5, which is not
                               # reproducible from the corpus at all.
    f'{MC}AlternateContent',   # mc:, not w: -- see the MC constant above.
)


def _run_should_be_preserved(r):
    """True if this run carries a non-text child that must survive the rebuild.

    Rev26 preserved page breaks, drawings, fields and tabs and dropped everything else,
    including plain <w:br/> (recreated from \\n in en) and genuinely empty runs.

    BRANCH 6 WIDENED THE SET RATHER THAN THE PRINCIPLE. The seven-item list was not wrong
    about what it named; it was wrong that a list of seven could be complete. Appending the
    obvious tag closed D05, D09 and D02 and left D06 and D11 untouched -- which is why the
    register decomposes cluster A into three mechanisms and this fix addresses all three.

    NOTE WHAT THIS FUNCTION STILL CANNOT DO, because branch 7 owns it: it is a list, not one
    explicit inventory SHARED with extraction, and it stays silent rather than failing loudly
    on a tag nobody listed. Content controls (A16), smart tags (N1) and text in graphic
    metadata (A19) are that branch's, not this one's.
    """
    for child in r:
        tag = child.tag
        if tag == f'{W}br':
            if child.get(f'{W}type', '') == 'page':
                return True
            # plain line break — not preserved, it is recreated from \n in en
        elif tag in _PRESERVED_RUN_CHILDREN:
            return True
    return False


def _split_run_non_text(r):
    """Split a TEXT-BEARING run's children into what precedes its text and what follows it.

    THIS IS MECHANISM A-ii, AND IT IS THE HALF A WHITELIST CANNOT FIX. `_run_is_text_bearing`
    was tested before `_run_should_be_preserved`, so a run carrying text AND a protected child
    was removed whole and the child died even though it WAS on the list. The whitelist was
    never consulted, so widening it changes nothing here.

    WHY THE SPLIT IS BY SIDE RATHER THAN BY EXACT OFFSET (Wouter's decision, 2026-09-01). The
    English arrives as ONE unbroken string, so where inside it a tab belonged is not knowable.
    What IS knowable is which side of the run's text the child sat on, and that is the half
    that carries the layout:

      [rPr, tab, t]        the tab PRECEDES the text. With a hanging indent the tab is the
                           only thing pushing the line out to the indent position, so
                           returning it in front restores the layout with no operator action.
                           That is Wouter's D05 notices clause: `ind left=1418 hanging=709`
                           byte-identical in source and deliverable, and the text sitting
                           709 twips -- about 1.25 cm -- too far left because the tab died.

      [rPr, t, tab, t]     the tab sat BETWEEN two text fragments. The two fragments collapse
                           into one English string, so the tab returns after it. Imperfect --
                           on a party grid the tab lands after both names rather than between
                           them -- and strictly better than deletion, which is what happens
                           today. Declared rather than hidden.

    THREE BUCKETS, NOT TWO, AND THE THIRD IS THE ONE THAT MATTERED. A run's children can be
    `[t, tab, t]` — the tab sits BETWEEN two text children of the SAME run. A two-bucket split
    put it in `after`, and since such a run is often the paragraph's only text-bearing run it
    then counted as "follows all the text" and was kept. Rendered, that is D06's table of
    contents: the tab emitted at the end, the page number glued to the title, and a forced
    line wrap. Caught by the fixture on 2026-09-01, having been missed by every count.

    Returns (before, between, after) as lists of the original child elements. `between` can
    never be placed truly, because the text on both sides of it has collapsed into one string.
    `rPr` is never salvaged: it is run PROPERTIES, and properties are branches 15-17's
    problem, not this branch's.
    """
    before, mid, after, seen_text = [], [], [], False
    for child in r:
        tag = child.tag
        if tag in (f'{W}t', f'{W}delText'):
            if seen_text:
                # More text after things we had provisionally called trailing: everything
                # banked so far sat BETWEEN text and cannot be placed.
                mid.extend(after)
                after = []
            seen_text = True
            continue
        if tag == f'{W}rPr':
            continue
        if tag == f'{W}br' and child.get(f'{W}type', '') != 'page':
            continue          # recreated from \n in en, exactly as before
        if tag == f'{W}lastRenderedPageBreak':
            # CLAUSE 3 AGAIN, AND THE INSTRUMENT FOUND IT. This tag is a CACHE, not
            # content: Word writes it to record where it last laid the page out, and
            # regenerates it on open. Salvaging it from a run whose text we are
            # REPLACING carries forward a break position measured against text that no
            # longer exists -- provably redundant, which is exactly what clause 3
            # licenses deleting.
            #
            # Measured 2026-09-01 by tools/apply_corpus_diff.py, which flagged it on
            # TEN of the thirteen frozen intermediates -- D05 alone went 1 -> 20 -- as
            # movement no register row predicted. It stays in the structural-only
            # whitelist, so a run we are NOT rebuilding keeps its cache untouched and
            # existing behaviour is unchanged there.
            continue
        (after if seen_text else before).append(child)
    return before, mid, after


# WHITESPACE WITH A POSITION, versus a POINTER that has none. The distinction was missing
# until Wouter read the rendered pages on 2026-09-01, and it is the whole reason clause 2 had
# to be narrowed.
#
# A `w:footnoteReference` works wherever in the paragraph it lands: it is a POINTER, and the
# footnote appears at the foot of the page regardless. A `w:tab` does not — it is whitespace
# whose entire meaning is WHERE it sits. Put it back in the wrong place and it does visible
# harm rather than none:
#
#   D06's table of contents: source runs are number, tab, title, tab, page number. Both tabs
#   returned at the paragraph END, so the page number stayed glued to the title exactly as
#   before AND two trailing tabs advanced past the right margin, forcing a line wrap. The
#   register had predicted precisely this and called it latent -- "on a row whose text already
#   reaches the right margin a trailing tab forces a wrap" -- and it was quoted in this file's
#   own comments while nothing tested for it.
#
#   D05: the same shape broke the line carrying the restored footnote anchor.
#
# SO A MISPLACED TAB IS WORSE THAN A MISSING ONE, measured on the page rather than argued.
# Wouter's decision, 2026-09-01: keep a tab only where its TRUE position survives the
# collapse; where it does not, DROP it, which is what the old code did, so the page is no
# worse than before. A3 and A6 are therefore NOT closed by this branch and belong to branch
# 16, where per-run English makes the position knowable.
#
# AN EXACT PREFIX/SUFFIX SPLIT WAS CONSIDERED AND MEASURED FIRST, not dismissed: if a source
# fragment is still an exact affix of `en` the boundary is proved, not guessed. It fires on
# 4 of D06's 231 multi-fragment paragraphs and 12% corpus-wide, so it would not have fixed
# the page in question. Recorded so nobody rediscovers it as an idea.
_POSITION_CRITICAL = (f'{W}tab', f'{W}br')


def _is_position_critical(child):
    """True if this run child's meaning depends on WHERE it sits, not merely on being present."""
    return child.tag in _POSITION_CRITICAL


def _run_is_only_position_critical(r):
    """True if everything this structural-only run carries is position-critical.

    A run holding a tab AND a drawing is not dropped: the drawing must survive. Only a run
    whose entire content is positional whitespace can be dropped for being unplaceable.
    """
    kids = [c for c in r if c.tag != f'{W}rPr']
    return bool(kids) and all(_is_position_critical(c) for c in kids)


def _text_span(container):
    """(first, last) child index of this container's text-bearing runs, or (None, None).

    All of a container's text collapses into ONE rebuilt block at the first of these, so these
    two indices are what decide whether a positional child can still be put on the correct
    side of the text.
    """
    first = last = None
    for i, child in enumerate(container):
        if child.tag == f'{W}r' and _run_is_text_bearing(child):
            if first is None:
                first = i
            last = i
    return first, last


def _wrap_salvaged(children, template_rpr):
    """Wrap salvaged non-text children in fresh runs so the XML stays valid.

    A <w:tab/> or a <w:footnoteReference/> is only legal inside a <w:r>. The run's OWN rPr is
    copied where it had one -- not the paragraph template's. That distinction matters: A18
    records that borrowing whichever run happens to carry an explicit rPr systematically
    selects the run that DIFFERS from the paragraph default, and can make a property SPREAD
    across a whole clause. Copying a child's own run properties cannot do that.
    """
    out = []
    for child in children:
        run = ET.Element(f'{W}r')
        if template_rpr is not None:
            run.append(copy.deepcopy(template_rpr))
        run.append(copy.deepcopy(child))
        out.append(run)
    return out


# CLAUSE 3 IS RESTRICTED TO THE CROSS-REFERENCE FAMILY, AND THE RESTRICTION IS THE POINT.
# A9's evidence is REF-FIELD skeletons on D06, and "drop the skeleton when its cached result
# is consumed" applied to EVERY field type would freeze a `PAGE`, `NUMPAGES`, `DATE`, `TIME`
# or `SEQ` field at whatever value happened to be cached -- a regression the evidence never
# licensed, on a defect nobody reported.
#
# MEASURED ACROSS THE WHOLE CORPUS BEFORE NARROWING IT (2026-09-01): the only fields carrying
# a cached result anywhere in the eleven documents are D06's 45 REF fields. So this guard
# changes nothing measurable today -- it exists for the document that is not in the corpus,
# which is the difference between fixing the caller that bit you and fixing the class.
_DELETABLE_FIELD_KEYWORDS = ('REF', 'PAGEREF', 'NOTEREF')
_FIELD_KEYWORD_RX = re.compile(r'^\s*([A-Za-z]+)')


def _consumed_field_runs(container):
    """Runs of a `fldChar` field whose CACHED RESULT is text-bearing — finding A9.

    CLAUSE 3, AND THE ONLY DELETION IN OPTION 1. A field is a SEQUENCE of runs, not one
    element: `begin`, the `instrText` instruction, `separate`, the cached result, `end`.
    Extraction folds the cached result into `text`, so the operator's English legitimately
    contains the number; apply then consumed that run and PRESERVED the skeleton, because
    `fldChar` and `instrText` are both whitelisted. Word and LibreOffice re-evaluate the
    now-empty skeleton on open and print the value a SECOND time.

    D06: 42 paragraphs, six of which also resurrected the literal string "Error: Reference
    source not found". Caught only by rendering -- `validate_apply` polices MISSING tokens and
    never EXTRA ones, the remnant scan looks for source language, `quality_check` has no
    duplicated-cross-reference rule, and `verify_diligence` reported OVERALL PASS. And no
    lever in paragraphs.json could fix it, because the offending runs are precisely the ones
    apply is designed to preserve -- so the step documents' prescribed remedy ("fix the JSON
    and re-run Step 5") could not work.

    WHAT THE DELETION COSTS, stated rather than buried: the cross-reference stops being a
    LIVE field and becomes static text, so it no longer auto-updates. That is the trade the
    register prescribes, and it is the right way round -- a number printed twice is a defect
    a reader sees, and a number that does not auto-update in a translated deliverable is not.

    ONLY WHERE THE RESULT IS ACTUALLY CONSUMED. A field with no cached result -- a bare
    `PAGE`, a field never evaluated -- has nothing folded into `text`, so its skeleton is the
    only copy of the instruction and is preserved untouched. Nesting is tracked by depth, and
    an unterminated field is preserved rather than guessed at.
    """
    out, current, depth, has_result, kw = set(), [], 0, False, None
    for child in container:
        if child.tag != f'{W}r':
            continue
        kinds = [c.get(f'{W}fldCharType', '') for c in child if c.tag == f'{W}fldChar']
        if 'begin' in kinds:
            if depth == 0:
                current, has_result, kw = [], False, None
            depth += 1
            current.append(child)
        elif depth > 0:
            current.append(child)
            if kw is None:
                for c in child:
                    if c.tag == f'{W}instrText' and c.text:
                        m = _FIELD_KEYWORD_RX.match(c.text)
                        if m:
                            kw = m.group(1).upper()
                        break
            if 'end' in kinds:
                depth -= 1
                if depth == 0:
                    if has_result and kw in _DELETABLE_FIELD_KEYWORDS:
                        out.update(current)
                    current, has_result, kw = [], False, None
            elif _run_is_text_bearing(child):
                has_result = True
    return out

def extract_header(xml_text):
    """Extract XML declaration and root element opening tag from raw XML text."""
    m = re.match(r'(<\?xml[^?]*\?>\s*<w:document[^>]*>)', xml_text, re.DOTALL)
    return m.group(1) if m else None

def build_text_index(orig_paras):
    """Build a mapping from normalized Italian text to list of (paragraph_index) in order."""
    text_to_indices = {}
    for i, p in enumerate(orig_paras):
        text = normalize_text(get_paragraph_text(p))
        if text:
            if text not in text_to_indices:
                text_to_indices[text] = []
            text_to_indices[text].append(i)
    return text_to_indices

def find_match(entry_text, text_to_indices, used_indices, entry_idx):
    """Find the best matching original paragraph for a given Italian text.

    Strategy:
    1. Exact match on normalized text
    2. Prefix match (first 30 chars) for texts that might have been truncated
    3. For duplicate texts, use positional order (closest to expected idx)
    """
    norm = normalize_text(entry_text)

    if not norm:
        return None

    # Try exact match
    if norm in text_to_indices:
        candidates = [i for i in text_to_indices[norm] if i not in used_indices]
        if candidates:
            # Pick the one closest to expected position
            return min(candidates, key=lambda x: abs(x - entry_idx))

    # Try prefix match (first 30 chars)
    prefix = norm[:30]
    if len(prefix) >= 10:
        for text, indices in text_to_indices.items():
            if text.startswith(prefix):
                candidates = [i for i in indices if i not in used_indices]
                if candidates:
                    return min(candidates, key=lambda x: abs(x - entry_idx))

    return None

def _doc_has_tracked_changes(paragraphs_json_path):
    """Return True if any paragraph entry in paragraphs.json carries
    tracked-change metadata (has_track_changes, tc_segments, or
    en_segments). Used to gate the TC-only pre-apply validators."""
    try:
        with open(paragraphs_json_path, 'r', encoding='utf-8') as f:
            entries = json.load(f)
    except (OSError, json.JSONDecodeError):
        return False
    for e in entries:
        if not isinstance(e, dict):
            continue
        if e.get('has_track_changes'):
            return True
        if e.get('tc_segments') or e.get('en_segments'):
            return True
    return False

# The truncated-install sentinel. All twenty scripts in the tree exit 3 when their
# own integrity check fires, and that is the one condition SKILL.md rule 6 says must
# STOP the run. It is a shared constant rather than a literal at each test, because
# the defect below was a magic number in one place disagreeing with a magic number in
# another.
_INTEGRITY_EXIT = 3


def _run_validator(label, args, block_codes=None):
    """Invoke a validator subprocess; raise RuntimeError on block.
    block_codes={set} or None (any non-zero blocks).
    Exit 3 — a truncated install — blocks unconditionally, whatever block_codes says."""
    import subprocess
    print(f"\n{'=' * 60}\n[apply] auto-running {label}\n{'=' * 60}")
    result = subprocess.run(args, capture_output=False)
    rc = result.returncode

    # EXIT 3 BLOCKS UNCONDITIONALLY, AND IS TESTED BEFORE ANYTHING ELSE.
    #
    # This is the one condition SKILL.md says must stop the run, and it was the one
    # being waved through. Both of the calls below pass block_codes={2}, while
    # validate_en_runs.py and validate_translations.py each exit 3 when their OWN
    # integrity check fires — so a sub-validator that had detected its own
    # truncation fell into the `elif rc != 0` branch and printed
    # "returned WARN (exit 3). Continuing." Detection worked perfectly; the caller
    # threw it away. That is goal (iv) failing at the point of USE rather than at
    # install, and it is why this test is first rather than folded into block_codes.
    #
    # THE MESSAGE IS DELIBERATELY NOT THE GATE MESSAGE. SKILL.md rule 6 records that
    # a truncated install arrives "wearing the costume of an intentional gate", and
    # the remedy is the opposite of a gate's: re-install. Telling the operator to fix
    # the input here would send them to re-author paragraphs.json, which cannot help
    # and which rule 6 forbids — the input is not the problem.
    if rc == _INTEGRITY_EXIT:
        raise RuntimeError(
            f"FILE INTEGRITY — THE INSTALL IS TRUNCATED. This is NOT a gate and "
            f"NOT an input problem. {label} exited {rc}, the sentinel a script "
            f"returns when its own integrity check fires. Apply aborted. SKILL.md "
            f"rule 6 governs and rule 5 does not: STOP and re-install the skill "
            f"from the .skill / .zip archive, then re-run the affected step. Do "
            f"NOT edit paragraphs.json, do NOT pass an override flag, and do not "
            f"treat this as a gate to be satisfied — no change to the input can "
            f"repair a truncated script."
        )

    if block_codes is None:
        if rc != 0:
            raise RuntimeError(
                f"SKILL GATE FIRED — INTENTIONAL BLOCK, NOT A SCRIPT ERROR. "
                f"{label} returned exit code {rc}. Apply aborted by design; "
                f"the script is working as intended. Read the gate's "
                f"explanation above (printed by {label}), fix paragraphs.json "
                f"or run with the gate's documented override flag, then re-run "
                f"apply. Do NOT work around this by calling textmatch_apply() "
                f"from a wrapper that skips gates — doing so silently ships "
                f"output below the quality the skill is designed to deliver."
            )
    else:
        if rc in block_codes:
            raise RuntimeError(
                f"SKILL GATE FIRED — INTENTIONAL BLOCK, NOT A SCRIPT ERROR. "
                f"{label} returned exit code {rc} (BLOCK). Apply aborted by "
                f"design. Read the gate's explanation above (printed by "
                f"{label}), fix the underlying issue, then re-run."
            )
        elif rc != 0:
            print(f"\n[apply] {label} returned WARN (exit {rc}). Continuing.")

def textmatch_apply(orig_docx_path, paragraphs_json_path, output_xml_path,
                    allow_bold_loss=False):
    """Apply translations using text matching. Auto-invokes mandatory
    validators (segment_shapes, reject_all, validate_apply) the full gate sequence."""
    scripts_dir = os.path.dirname(os.path.abspath(__file__))

    # Pre-apply: en_runs gate (extracted to validate_en_runs.py).
    en_runs_args = [sys.executable,
                    os.path.join(scripts_dir, 'validate_en_runs.py'),
                    paragraphs_json_path]
    if allow_bold_loss:
        en_runs_args.append('--allow-bold-loss')
    _run_validator(
        'validate_en_runs.py (pre-apply en_runs gate)',
        en_runs_args,
        block_codes={2},
    )

    # Pre-apply: validate_translations (final pass; also enforces the
    #  per-batch cap if the operator skipped batching).
    _run_validator(
        'validate_translations.py (final pre-apply pass)',
        [sys.executable,
         os.path.join(scripts_dir, 'validate_translations.py'),
         paragraphs_json_path],
        block_codes={2},
    )

    # Pre-apply (TC docs only): segment_shapes + reject_all.
    if _doc_has_tracked_changes(paragraphs_json_path):
        _run_validator(
            'validate_segment_shapes.py (pre-apply, TC docs)',
            [sys.executable,
             os.path.join(scripts_dir, 'validate_segment_shapes.py'),
             paragraphs_json_path,
             '--strict'],
        )
        _run_validator(
            'validate_reject_all.py (pre-apply, TC docs)',
            [sys.executable,
             os.path.join(scripts_dir, 'validate_reject_all.py'),
             paragraphs_json_path],
        )

    # Read original document.xml
    with zipfile.ZipFile(orig_docx_path) as zf:
        orig_bytes = zf.read('word/document.xml')

    # Dynamically register whatever xmlns prefixes the source document actually
    # uses. This MUST happen before ET.fromstring, or ET will assign synthetic
    # prefixes like ns3:/ns4: at serialization time for namespaces it doesn't
    # know, and those end up undeclared once we restore the original header.
    register_document_namespaces(orig_bytes)

    orig_header = extract_header(orig_bytes.decode('utf-8'))
    orig_root = ET.fromstring(orig_bytes)
    orig_body = orig_root.find(f'{W}body')
    # IMPORTANT: use recursive search to include paragraphs nested inside tables,
    # text boxes, and other container elements — not just direct children of w:body.
    # The extraction script (extract_paragraphs.py) uses root.iter() which is recursive,
    # so the apply script must search the same way to find all paragraphs.
    orig_paras = list(orig_body.findall(f'.//{W}p'))

    print(f"Original document has {len(orig_paras)} paragraphs (including table cells)")

    # Read translations
    with open(paragraphs_json_path, 'r', encoding='utf-8') as f:
        translations = json.load(f)

    print(f"paragraphs.json has {len(translations)} entries")

    # Build text index from original
    text_to_indices = build_text_index(orig_paras)

    # Match and apply translations
    used_indices = set()
    changes = 0
    matched_exact = 0
    matched_offset = 0
    not_found = 0
    skipped_same = 0
    skipped_empty = 0

    # Sort entries by idx to process in order (helps with duplicate disambiguation)
    entries_sorted = sorted(translations, key=lambda e: e.get('idx', 0))

    for entry in entries_sorted:
        idx = entry.get('idx', 0)
        it_text = (entry.get('text') or '').strip()
        # F27: boundary-aware. `it_text` above is stripped normally because it is only ever
        # used for MATCHING; `en_text` is what gets written, so its boundary tabs and
        # newlines are structure and must survive. `en_deleted` is left on plain .strip()
        # deliberately: F27's evidence is `en` on D01 and D10, and widening a fix past its
        # evidence is how a branch stops being reviewable.
        en_text = _strip_keeping_separators(entry.get('en') or '')
        en_deleted = (entry.get('en_deleted') or '').strip()
        en_runs_spec = entry.get('en_runs')
        original_runs = entry.get('runs', [])

        if not it_text or not en_text:
            skipped_empty += 1
            continue

        # skip-same-text only if no en_segments (TC paragraphs
        # may have segment-level work even when flat text matches).
        if it_text == en_text and not entry.get('en_segments'):
            skipped_same += 1
            continue

        # Find matching original paragraph
        match_idx = find_match(it_text, text_to_indices, used_indices, idx)

        if match_idx is None:
            not_found += 1
            if not_found <= 10:
                print(f"  NOT FOUND idx={idx}: {it_text[:60]}")
            continue

        used_indices.add(match_idx)
        offset = match_idx - idx

        if offset == 0:
            matched_exact += 1
        else:
            matched_offset += 1

        # Apply translation to the matched original paragraph
        orig_p = orig_paras[match_idx]

        # Tracked-change fast path: if the paragraph contains <w:ins>/<w:del>
        # markup, use the in-place text-distribution strategy so we preserve
        # the tracked-change wrappers and their author/date metadata. The
        # standard rebuild path below would wipe <w:r> direct children (and
        # so leave the runs nested inside <w:ins>/<w:del> unchanged, i.e.
        # still in the source language) while discarding the rest of the
        # paragraph's text — a silent data-loss bug.
        if has_track_changes(orig_p):
            en_segs = entry.get('en_segments')
            if apply_trackchanges_inplace(orig_p, en_text, it_text,
                                          en_deleted=en_deleted,
                                          en_segments=en_segs,
                                          en_runs_spec=en_runs_spec,
                                          original_runs=original_runs):
                changes += 1
            continue

        default_rpr = get_default_rpr_et(orig_p)

        # Determine formatting
        if en_runs_spec:
            if is_subheader_paragraph(en_text, original_runs):
                segments = [{"start": 0, "end": len(en_text), "bold": True, "italic": False}]
            else:
                segments = en_runs_spec
        else:
            segments = auto_detect_formatting(en_text, original_runs)

        # =====================================================================
        # BRANCH 6 (option 1) — THE THREE CLAUSES:
        #
        #   1  REBUILD ONLY TEXT
        #   2  PRESERVE EVERY NON-TEXT RUN CHILD IN ITS ORIGINAL RELATIVE POSITION
        #   3  DELETE ONLY WHAT CAN BE PROVED REDUNDANT
        #
        # The slogan this replaces was "preserve by default", and it was retired
        # for being self-contradictory: text-bearing runs MUST be removed and
        # rebuilt, so a one-clause version breaks the pipeline. Three clauses.
        #
        # WHAT THE OLD CLASSIFIER GOT WRONG — four separable ways, and appending
        # one tag to the whitelist fixes only the first of them:
        #
        #   A-i    a structural-ONLY run whose child was not one of seven listed
        #          tags was read as an empty run and deleted. D05's only footnote
        #          anchor 1->0, D09's 2->0, D02's comment anchors 28->14, D08's
        #          13->9. In every case the auxiliary part was translated and
        #          perfect and the POINTER was destroyed, so the content shipped
        #          inside the package and appeared on no page -- which is exactly
        #          why five gates reported clean and Step 11a printed "Deliver
        #          with confidence".
        #   A-ii   `_run_is_text_bearing` was tested FIRST, so a run carrying text
        #          AND a protected child lost the child without the whitelist ever
        #          being consulted. Widening the list cannot reach this.
        #   A-iii  `w:hyperlink` was removed wholesale with its whole subtree,
        #          including tab-only runs the whitelist WOULD have protected.
        #          D06: hyperlinks 34->1, tab characters 80->10, a 40-entry table
        #          of contents flattened to "1.General Provisions4" and no longer
        #          navigable -- while tab STOPS stayed 248->248, which is why no
        #          count-based check ever saw it.
        #   pos    every rebuilt run was inserted at ONE index while preserved
        #          children kept their old ones, so relative order was not
        #          preserved even when nothing was deleted.
        #
        # THIS BRANCH DELIBERATELY DOES NOT FIX: any formatting property (A4, A5,
        # A7, A10-A14, A17, A18 — branches 15-17), the container inventory shared
        # with extraction (A16, A19, N1 — branch 7), or any gate's blindness.
        # =====================================================================

        # Build the English runs FIRST. Clause 3 cannot decide which source tabs
        # are redundant until it knows whether the operator authored any.
        new_runs = []
        authored_tab = False
        for seg in segments:
            start = seg.get('start', 0)
            end = seg.get('end', len(en_text))
            seg_text = en_text[start:end]
            if not seg_text:
                continue
            bold = seg.get('bold', False)
            italic = seg.get('italic', False)
            # \t in en → <w:tab/>; \n → <w:br/>.
            if '\t' in seg_text or '\n' in seg_text:
                parts = re.split(r'([\t\n])', seg_text)
                for part in parts:
                    if part == '\t':
                        tab_run = ET.Element(f'{W}r')
                        ET.SubElement(tab_run, f'{W}tab')
                        new_runs.append(tab_run)
                        authored_tab = True
                    elif part == '\n':
                        br_run = ET.Element(f'{W}r')
                        ET.SubElement(br_run, f'{W}br')
                        new_runs.append(br_run)
                    elif part:
                        new_runs.append(make_run_et(
                            part, default_rpr, bold=bold, italic=italic))
            else:
                new_runs.append(make_run_et(
                    seg_text, default_rpr, bold=bold, italic=italic))

        def _first_text_container(container):
            """The container holding the paragraph's FIRST text-bearing run, in
            document order — which may be a `w:hyperlink`, in which case the
            English belongs INSIDE it so the link still covers the translated
            words rather than becoming an empty wrapper beside them."""
            for child in container:
                if child.tag == f'{W}r' and _run_is_text_bearing(child):
                    return container
                if child.tag == f'{W}hyperlink':
                    found = _first_text_container(child)
                    if found is not None:
                        return found
            return None

        target = _first_text_container(orig_p)
        nested = []

        def _rebuild_container(container):
            """Clauses 1 and 2 over one run-bearing container, in place.

            Returns the index at which the English belongs if the paragraph's
            first text-bearing run lives in THIS container, else None. The child
            list is rebuilt in document order rather than patched by index, which
            is what makes clause 2 true by construction instead of by arithmetic.
            """
            kept, slot = [], None
            # CLAUSE 3, computed per container before anything is touched: the runs of any
            # field whose cached result we are about to consume. A9.
            dead_field = _consumed_field_runs(container)
            # CLAUSE 2's LIMIT, computed before anything is emitted. All of this container's
            # text collapses into one block at `first_txt`, so a positional child is keepable
            # only if it sat outside that span — and only if the rebuilt English lands in THIS
            # container at all.
            first_txt, last_txt = _text_span(container)
            is_target = container is target
            for i, child in enumerate(list(container)):
                tag = child.tag
                if tag == f'{W}r':
                    if child in dead_field:
                        # The whole skeleton goes, instruction and all. The number it held is
                        # already inside en_text, so leaving the skeleton makes Word print it
                        # twice. Still let the cached-result run mark the insertion point, so
                        # a paragraph that BEGINS with a cross-reference keeps the English
                        # where the field was rather than pushing it to the end.
                        if (_run_is_text_bearing(child) and slot is None
                                and container is target):
                            slot = len(kept)
                        continue
                    if _run_is_text_bearing(child):
                        rpr = child.find(f'{W}rPr')
                        before, mid, after = _split_run_non_text(child)
                        if authored_tab:
                            # CLAUSE 3 — the only deletion in this step, and it is
                            # the one A3/D01 demands. That document's operator read
                            # the apply source and authored literal `\t` to work
                            # around the relocation; tab characters went 18 -> 24,
                            # UP, because the authored tabs landed in the right
                            # places and the source's own tabs were preserved at
                            # the paragraph end as orphans. The layout looked
                            # correct over a doubled tab structure, and a bare
                            # count cannot tell a repair from an orphan.
                            #
                            # Wouter's decision, 2026-09-01: the AUTHORED tab wins.
                            # Where `en` carries a tab, the operator has stated the
                            # positions, so a source tab from a run whose text we
                            # are replacing is provably redundant. Narrow on
                            # purpose: it fires only when a tab was authored, and
                            # only for runs being rebuilt.
                            before = [c for c in before if c.tag != f'{W}tab']
                            mid = [c for c in mid if c.tag != f'{W}tab']
                            after = [c for c in after if c.tag != f'{W}tab']
                        # A POINTER IS NEVER DROPPED, WHEREVER IT SAT. A footnoteReference or
                        # a commentReference in `mid` still belongs in the paragraph, because
                        # it works from anywhere in it — so only POSITION-CRITICAL children
                        # are filtered below. That distinction is what separates the CRITICAL
                        # rows this branch closes from the layout row it defers.
                        mid = [c for c in mid if not _is_position_critical(c)]
                        # CLAUSE 2's LIMIT. A positional child is emitted only where its
                        # true side of the text survives: `before` needs this to be the
                        # FIRST text-bearing run, `after` the LAST. Anywhere else the
                        # child sat BETWEEN text that has now collapsed, so there is no
                        # correct place for it and a wrong one does visible harm.
                        before = [c for c in before if not _is_position_critical(c)
                                  or (is_target and i == first_txt)]
                        after = [c for c in after if not _is_position_critical(c)
                                 or (is_target and i == last_txt)]
                        kept.extend(_wrap_salvaged(before, rpr))
                        if slot is None and container is target:
                            slot = len(kept)
                        # `mid` holds only pointers by now, and a pointer works from anywhere
                        # in the paragraph — so it is emitted straight after the English
                        # rather than thrown away.
                        kept.extend(_wrap_salvaged(mid, rpr))
                        kept.extend(_wrap_salvaged(after, rpr))
                    elif _run_should_be_preserved(child):
                        # THE SAME LIMIT FOR A PRESERVED TAB-ONLY RUN, and it reaches a
                        # defect older than this branch. Such a run was always kept at its
                        # own index while the English moved to the first text position, so
                        # one sitting BETWEEN text-bearing runs was already stranded — that
                        # is A3/D01's orphan shape, where tab characters went 18 -> 24 and
                        # the layout still looked right. Where the English is not in this
                        # container at all, no position in it is the correct one.
                        if (_run_is_only_position_critical(child)
                                and first_txt is not None
                                and not (is_target
                                         and (i < first_txt or i > last_txt))):
                            continue
                        kept.append(child)
                    # else: an empty run or a plain <w:br/> line break — dropped,
                    # exactly as before. The break is recreated from \n in en.
                elif tag == f'{W}hyperlink':
                    # A-iii: THE WRAPPER IS NEVER DELETED. Rebuild inside it.
                    inner_slot = _rebuild_container(child)
                    if inner_slot is not None:
                        nested.append((child, inner_slot))
                    kept.append(child)
                else:
                    # pPr, bookmarkStart/End, commentRangeStart/End, proofErr and
                    # anything else at paragraph level: carried through untouched.
                    kept.append(child)
            for child in list(container):
                container.remove(child)
            for child in kept:
                container.append(child)
            return slot

        para_slot = _rebuild_container(orig_p)

        # Where the English goes: inside the hyperlink that held the first text,
        # or at the first text position in the paragraph, or — for a paragraph
        # with no text-bearing run at all — appended at the end, which is the
        # pre-existing fallback and is kept deliberately.
        if nested:
            holder, at = nested[0]
        elif para_slot is not None:
            holder, at = orig_p, para_slot
        else:
            holder, at = orig_p, len(orig_p)
        for offset, new_run in enumerate(new_runs):
            holder.insert(at + offset, new_run)

        changes += 1

    print(f"\nResults:")
    print(f"  Matched at correct idx: {matched_exact}")
    print(f"  Matched with offset: {matched_offset}")
    print(f"  Not found: {not_found}")
    print(f"  Skipped (same text): {skipped_same}")
    print(f"  Skipped (empty): {skipped_empty}")
    print(f"  Total changes applied: {changes}")

    # Serialize
    buf = io.BytesIO()
    tree = ET.ElementTree(orig_root)
    tree.write(buf, xml_declaration=True, encoding='UTF-8')
    rebuilt_xml = buf.getvalue().decode('utf-8')

    # Restore namespace declarations
    if orig_header:
        rebuilt_xml = re.sub(
            r'^<\?xml[^?]*\?>\s*<w:document[^>]*>',
            orig_header,
            rebuilt_xml,
            count=1,
            flags=re.DOTALL
        )

    # --- Namespace validation ---
    # Scan body for used-but-undeclared namespace prefixes; inject their
    # xmlns declarations into the root. Catches prefixes (a:, pic:, etc.)
    # that ET would otherwise emit without declaration.
    KNOWN_NS = {
        'a': 'http://schemas.openxmlformats.org/drawingml/2006/main',
        'pic': 'http://schemas.openxmlformats.org/drawingml/2006/picture',
        'r': 'http://schemas.openxmlformats.org/officeDocument/2006/relationships',
        'o': 'urn:schemas-microsoft-com:office:office',
        'v': 'urn:schemas-microsoft-com:vml',
        'w10': 'urn:schemas-microsoft-com:office:word',
        'wp': 'http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing',
        'wps': 'http://schemas.microsoft.com/office/word/2010/wordprocessingShape',
        'wpg': 'http://schemas.microsoft.com/office/word/2010/wordprocessingGroup',
        'mc': 'http://schemas.openxmlformats.org/markup-compatibility/2006',
        'wp14': 'http://schemas.microsoft.com/office/word/2010/wordprocessingDrawing',
        'w14': 'http://schemas.microsoft.com/office/word/2010/wordml',
        'w15': 'http://schemas.microsoft.com/office/word/2012/wordml',
        'wne': 'http://schemas.microsoft.com/office/word/2006/wordml',
        # w16* family — must mirror NAMESPACES above.
        'w16': 'http://schemas.microsoft.com/office/word/2018/wordml',
        'w16cex': 'http://schemas.microsoft.com/office/word/2018/wordml/cex',
        'w16cid': 'http://schemas.microsoft.com/office/word/2016/wordml/cid',
        'w16du': 'http://schemas.microsoft.com/office/word/2023/wordml/word16du',
        'w16sdtdh': 'http://schemas.microsoft.com/office/word/2020/wordml/sdtdatahash',
        'w16sdtfl': 'http://schemas.microsoft.com/office/word/2024/wordml/sdtformatlock',
        'w16se': 'http://schemas.microsoft.com/office/word/2015/wordml/symex',
    }
    declared = set(re.findall(r'xmlns:([\w.-]+)=', rebuilt_xml[:5000]))
    # Prefixes used on element tags or attribute names. Allow digits and the
    # w16* family (which contains no digits but has letters only, so the
    # original \w{1,5} matches; we widen to \w{1,8} to cover w16sdtdh etc.).
    used_in_tags = set(re.findall(r'<(\w{1,8}):', rebuilt_xml))
    used_in_attrs = set(re.findall(r'[\s"](\w{1,8}):[A-Za-z_]', rebuilt_xml[:200000]))
    real_prefixes = {p for p in (used_in_tags | used_in_attrs) if p in KNOWN_NS}
    missing = real_prefixes - declared
    if missing:
        inject = ' '.join(f'xmlns:{p}="{KNOWN_NS[p]}"' for p in sorted(missing))
        rebuilt_xml = rebuilt_xml.replace(
            '<w:document ',
            f'<w:document {inject} ',
            1
        )
        print(f"  Injected missing namespace declarations: {sorted(missing)}")

    # --- Synthetic-prefix leak detection ---
    # If, despite everything above, any `nsN:` prefix (ElementTree's synthetic
    # fallback) leaked into the output, fail loudly rather than silently
    # producing a Word-incompatible file. LibreOffice will happily open such
    # files — Word will not — so this is the last defence against regressions.
    synthetic = sorted(set(re.findall(r'[\s"<](ns\d+):[A-Za-z_]', rebuilt_xml)))
    if synthetic:
        raise RuntimeError(
            "Namespace corruption: ElementTree assigned synthetic prefixes "
            f"{synthetic} to namespaces it did not recognise. The resulting "
            ".docx will not open in Microsoft Word. This usually means a new "
            "OOXML namespace appeared in the source document that is not yet "
            "covered by NAMESPACES / register_document_namespaces(). Inspect "
            "the original word/document.xml root element for the offending "
            "xmlns:* declarations and add them to NAMESPACES."
        )

    # --- Strip revision tracking attributes ---
    # These cause Word to show tracked changes (formatting changes, rsid markers).
    # Remove w:rsidR, w:rsidRDefault, w:rsidRPr, w:rsidP, w:rsidDel, w:rsidSect
    # from all elements. This is safe because revision tracking is not needed in
    # the translated output.
    rebuilt_xml = re.sub(r' w:rsid\w+="[^"]*"', '', rebuilt_xml)
    print("  Stripped revision tracking attributes (rsid*)")

    # --- Strip w:lang from paragraph-level rPr as well ---
    # The make_run_et function strips w:lang from run-level rPr, but paragraph-
    # level rPr can also carry language tags that trigger tracked changes.
    rebuilt_xml = re.sub(
        r'<w:lang[^/]*/>', '', rebuilt_xml
    )
    print("  Stripped language tags (w:lang)")

    # --- Source-language remnant scan ---
    # Scan translated text for source-language marker words via
    # source_language_markers. Whole-word matching avoids false
    # positives like "allocated"/"already".
    source_lang = None
    # Prefer the language stored on paragraphs.json, if the caller set one.
    if hasattr(textmatch_apply, '_source_language_override'):
        source_lang = textmatch_apply._source_language_override
    if not source_lang:
        # Auto-detect from the source-language text in paragraphs.json.
        try:
            with open(paragraphs_json_path, 'r', encoding='utf-8') as _f:
                _data = json.load(_f)
            sample = ' '.join(
                (p.get('text') or '') for p in _data[:60]
            )
            source_lang = detect_language(sample)
        except Exception:
            source_lang = None

    # Scan both the accept-all view (<w:t>) and the reject-all / markup view
    # (<w:delText>). A nested <w:ins><w:del>SOURCE</w:del></w:ins> phantom
    # renders as empty under accept-all, so scanning only <w:t> misses the
    # source-language strike-through that a reviewer with "Show Markup" on
    # still sees. Reporting the two views separately tells the translator
    # exactly which view to inspect.
    remnants_accept = []
    remnants_reject = []
    if source_lang:
        accept_text = ' '.join(
            m.group(1) for m in re.finditer(r'<w:t[^>]*>([^<]+)</w:t>', rebuilt_xml)
        )
        del_text = ' '.join(
            m.group(1) for m in re.finditer(r'<w:delText[^>]*>([^<]+)</w:delText>', rebuilt_xml)
        )
        remnants_accept = scan_remnants(accept_text, source_lang)
        # Reject-all view is the union of w:t outside w:ins and w:delText
        # content. Rather than re-walk the XML we approximate by scanning the
        # union of accept_text + del_text — any source-language hit in either
        # bucket is a real remnant. This over-reports slightly for an ins
        # whose source was already translated, but in practice the translator
        # will have filled that in so both views are clean.
        remnants_reject = scan_remnants(del_text, source_lang)

    if source_lang:
        label = source_lang.capitalize()
    else:
        label = 'source-language'

    def _print_hits(view_label, hits):
        print(f"\n  WARNING: {len(hits)} possible {label} remnant(s) detected ({view_label}):")
        seen = set()
        for marker, ctx in hits[:15]:
            key = ctx[:60]
            if key not in seen:
                seen.add(key)
                print(f"    -> '{marker}' in: {ctx}...")
        if len(hits) > 15:
            print(f"    ... and {len(hits) - 15} more")
        print(f"  Review these and fix manually if they are genuine {label} remnants.")

    if not source_lang:
        # Unknown source language — we cannot scan reliably. Announce, don't fail.
        print("  Source-language scan: SKIPPED "
              "(could not auto-detect source language — pass --source-language)")
    else:
        any_hit = False
        if remnants_accept:
            _print_hits('accept-all view', remnants_accept)
            any_hit = True
        if remnants_reject:
            _print_hits('reject-all / markup view', remnants_reject)
            any_hit = True
        if not any_hit:
            print(
                f"  Source-language scan: CLEAN (no {label} remnants in "
                f"accept-all or reject-all view)"
            )

    os.makedirs(os.path.dirname(output_xml_path) or '.', exist_ok=True)
    with open(output_xml_path, 'wb') as f:
        f.write(rebuilt_xml.encode('utf-8'))

    print(f"\nOutput written to {output_xml_path}")

    # --- POST-APPLY MANDATORY GATE -------------------------------------
    # validate_apply.py confirms every declared token from paragraphs.json
    # landed in the produced document.xml. MANDATORY for every document.
    _run_validator(
        'validate_apply.py --strict (post-apply)',
        [sys.executable,
         os.path.join(scripts_dir, 'validate_apply.py'),
         paragraphs_json_path,
         output_xml_path,
         '--strict'],
    )

    return changes

if __name__ == '__main__':
    _check_self_integrity()
    import argparse
    parser = argparse.ArgumentParser(
        description='Apply translations from paragraphs.json onto original document.xml.')
    parser.add_argument('original_docx', help='Path to original .docx')
    parser.add_argument('paragraphs_json', help='Path to paragraphs.json')
    parser.add_argument('output_xml', help='Path to write output document.xml')
    parser.add_argument('--allow-bold-loss', action='store_true',
                        help=('Bypass the en_runs gate on detected definitions '
                              'sections. Use only when bold loss is genuinely '
                              'acceptable (e.g., simple drafts where the '
                              'defined-term bold-italic is not needed).'))
    args = parser.parse_args()
    textmatch_apply(args.original_docx, args.paragraphs_json, args.output_xml,
                    allow_bold_loss=args.allow_bold_loss)

# === SKILL FILE COMPLETE ===
