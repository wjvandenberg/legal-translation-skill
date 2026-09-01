# -*- coding: utf-8 -*-
"""ONE DEFINITION OF WHAT COUNTS, SHARED BY BRANCH 6's TWO ARMS.

Branch 6 is measured two ways -- a synthetic fixture in the repository
(tests/test_stop_deleting.py) and the thirteen frozen intermediates outside it
(tools/apply_corpus_diff.py). THE COUNTING RULES LIVE HERE RATHER THAN IN BOTH, because
this project has already been bitten by a hazard fixed in one caller and left in another:
tests/test_no_delivered_byte_moves.py records its own harness reproducing the very defect
the branch was repairing, in a joiner that had been fixed elsewhere. A second copy of the
tab rule would be that again.

THE TWO RULES A COPY WOULD GET WRONG:

  1. A TAB STOP IS NOT A TAB CHARACTER. `w:tab` inside `pPr/tabs` is a STOP -- a ruler
     position -- and carries the same tag name as a rendered tab. .claude/rules/ooxml.md
     states it; the register turns it into the reason no count-based check has ever seen
     A3: on D06 tab CHARACTERS went 80 -> 10 while tab STOPS went 248 -> 248, and on D05
     5 -> 2 against 95 -> 95.

  2. A REFERENCE IS NOT A RANGE. A2's signature is `commentReference` falling while
     `commentRangeStart`/`commentRangeEnd` hold -- on D02, 28 -> 14 against 28 -> 28, with
     all 28 bodies still in comments.xml. Counting "comments" as one number hides exactly
     the defect: the bodies are in the package and unreachable.

This module counts. It never decides whether a movement is acceptable -- that is the
caller's job, and for branch 6 the answer must come from a register row.

No client text is read here, and nothing is printed. Callers own their output policy.
"""
from lxml import etree

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"

# Counted by tag name anywhere in the body. `tab` is handled separately -- see rule 1.
TAGS = (
    # The anchors A1 and A2 are about. A pointer, not a payload: destroy it and the
    # translated auxiliary part is still in the package and reachable from nothing.
    "footnoteReference", "endnoteReference", "commentReference",
    # The ranges that SURVIVE while the references die. The control for A2.
    "commentRangeStart", "commentRangeEnd",
    # A8: the wrapper deleted whole, taking its subtree with it.
    "hyperlink",
    # A9: the field skeleton that re-evaluates and prints a second time once its
    # cached-result run has been consumed.
    "fldChar", "instrText",
    # Already whitelisted today; counted so a fix cannot quietly regress them.
    "drawing", "pict", "lastRenderedPageBreak",
    # Branch 7's containers. Counted, NOT asserted here -- naming them keeps branch 6
    # honest about what it is not fixing (A16, A19, N1).
    "sdt", "smartTag", "object", "sym",
    # Structure.
    "p", "r", "t", "delText", "ins", "del",
)


def census(xml_bytes):
    """Count the structures branch 6 must preserve, plus the order-sensitive ones.

    Returns a plain dict of int. Order-sensitive entries:

      tab_chars       rendered tabs -- EXCLUDES tab stops (rule 1)
      tab_stops       ruler positions -- the negative control
      trailing_tabs   paragraphs whose LAST content atom is a tab. This is A3/D01's
                      orphan signature: the source's own tab-only runs are whitelisted,
                      preserved, and left behind at the paragraph end while the rebuilt
                      English is re-inserted before them. On that document tab characters
                      went 18 -> 24, UP, and the layout still looked right -- so a bare
                      count cannot tell a repair from an orphan and this can.
      br_page         page breaks (preserved today)
      br_plain        plain line breaks (recreated from \\n, deliberately not preserved)
    """
    root = etree.fromstring(xml_bytes)
    c = {k: 0 for k in TAGS}
    c.update(tab_chars=0, tab_stops=0, trailing_tabs=0, br_page=0, br_plain=0)

    for el in root.iter():
        tag = etree.QName(el).localname
        if tag == "tab":
            parent = el.getparent()
            if parent is not None and etree.QName(parent).localname == "tabs":
                c["tab_stops"] += 1
            else:
                c["tab_chars"] += 1
        elif tag == "br":
            if el.get(f"{{{W}}}type", "") == "page":
                c["br_page"] += 1
            else:
                c["br_plain"] += 1
        elif tag in c:
            c[tag] += 1

    for p in root.iter(f"{{{W}}}p"):
        atoms = content_atoms(p)
        if atoms and atoms[-1] == "tab":
            c["trailing_tabs"] += 1
    return c


def content_atoms(p):
    """The paragraph's content in document order, as coarse kinds: 'text' | 'tab' | 'br'.

    This is what makes a POSITION claim testable. Counts alone cannot distinguish "the tab
    is between the two party names" from "the tab is at the end of the paragraph", and that
    distinction IS finding A3: on D05 a run whose children are [rPr, tab, t] delivers its
    text 709 twips too far left when the tab dies, because with a hanging indent the tab is
    the only thing pushing the line out to the indent position.

    Tab STOPS are skipped here for the same reason as in census().
    """
    out = []
    for el in p.iter():
        tag = etree.QName(el).localname
        if tag in ("t", "delText"):
            if el.text:
                out.append("text")
        elif tag == "tab":
            parent = el.getparent()
            if parent is None or etree.QName(parent).localname != "tabs":
                out.append("tab")
        elif tag == "br":
            out.append("br")
    return out


def run_child_shapes(p):
    """Per run in the paragraph, the ordered tag names of its children.

    Cluster A is decomposed on exactly this: mechanism A-ii is a run whose children are
    ['rPr','t','tab','t'] -- text AND a whitelisted structural child -- being removed whole
    because `_run_is_text_bearing` is tested before the whitelist is ever consulted.
    Asserting on the shape rather than on a count is what proves the child came back IN
    POSITION rather than merely came back.
    """
    shapes = []
    for r in p.iter(f"{{{W}}}r"):
        shapes.append([etree.QName(ch).localname for ch in r])
    return shapes


def delta(before, after):
    """Only the keys that moved, as {key: (before, after)}. Empty dict means nothing moved."""
    return {k: (before[k], after[k]) for k in before if before[k] != after.get(k)}
