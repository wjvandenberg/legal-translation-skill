# -*- coding: utf-8 -*-
"""BUILD THE SYNTHETIC TEST DOCUMENTS.

Every fixture here is INVENTED. No fixture derives from a real document, and none may:
anonymising a real example still leaks its shape, its clause structure and its commercial
terms, and renaming is not enough. Where a real document was the source of a lesson, the
lesson is kept and the document discarded. The text is deliberately bland and obviously
fictional.

WHY SYNTHETIC FIXTURES ARE NOT MERELY THE SAFE OPTION -- they are the only way to test four
things at all. The eleven-document corpus contains NO `Symbol` or `Wingdings` run anywhere,
and no content control, smart tag, image with alt text or chart with title. Those defects
cannot be reproduced from a real document however many you have, which is exactly why they
have to be built.

Fixtures are written as OOXML by hand rather than through a library, for the same reason the
skill does: an XML object model rebinds namespace prefixes on serialisation and Word rejects
the file.

    uv run python tests/make_fixtures.py
    uv run python tests/make_fixtures.py --list
"""
import io
import json
import shutil
import sys
import zipfile
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "tests" / "fixtures"

W = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'
R = 'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"'
WP = ('xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"'
      ' xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"')

CONTENT_TYPES = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Default Extension="png" ContentType="image/png"/>
<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
<Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>
{extra}</Types>"""

RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>"""

STYLES = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:styles {W}>
<w:style w:type="paragraph" w:styleId="Normal"><w:name w:val="Normal"/></w:style>
<w:style w:type="paragraph" w:styleId="BoldClause"><w:name w:val="Bold Clause"/>
  <w:rPr><w:b/></w:rPr></w:style>
<w:style w:type="character" w:styleId="StrongEmph"><w:name w:val="Strong Emph"/>
  <w:rPr><w:b/><w:i/></w:rPr></w:style>
</w:styles>"""

# A 1x1 fully transparent PNG, built here rather than copied from anywhere: signature,
# IHDR, a single-pixel IDAT, IEND.
PNG = bytes.fromhex(
    "89504e470d0a1a0a"                          # signature
    "0000000d4948445200000001000000010806000000" "1f15c489"    # IHDR
    "0000000a49444154" "789c6300010000050001" "0d0a2db4"       # IDAT
    "0000000049454e44" "ae426082"               # IEND
)


# A .docx is a ZIP, and a ZIP records the clock time at which each member was added. Writing
# a fixture with `writestr(name, data)` therefore produces DIFFERENT BYTES on every build even
# though the content is identical -- and that is not cosmetic:
#
#   * running the suite left every committed fixture "modified", so the working tree went
#     dirty on a read-only operation;
#   * a dirty tree makes `git switch` refuse, and `git bisect` works by switching commits
#     repeatedly -- so the suite broke the one tool it exists to enable;
#   * and fixtures that cannot be byte-compared are a strange thing for a project whose whole
#     test method is byte comparison.
#
# Found on 2026-08-06 by a verification pass, not by the suite itself. Fixed by stamping every
# member with the ZIP epoch (1980-01-01, the earliest a ZIP can express) so a build is a pure
# function of its input.
FIXED_TIME = (1980, 1, 1, 0, 0, 0)


def _member(name):
    zi = zipfile.ZipInfo(name, date_time=FIXED_TIME)
    zi.compress_type = zipfile.ZIP_DEFLATED
    zi.external_attr = 0o600 << 16      # fixed permissions; the default varies by platform
    zi.create_system = 0                # always report MS-DOS, never the building OS
    return zi


def docx(path, body, extra_parts=None, extra_ct=""):
    """Write a minimal but genuinely valid .docx, byte-identically on every run."""
    doc = (f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
           f'<w:document {W} {R} {WP}><w:body>{body}'
           f'<w:sectPr><w:pgSz w:w="11906" w:h="16838"/></w:sectPr>'
           f'</w:body></w:document>')
    path.parent.mkdir(parents=True, exist_ok=True)
    parts = [("[Content_Types].xml", CONTENT_TYPES.format(extra=extra_ct)),
             ("_rels/.rels", RELS),
             ("word/document.xml", doc),
             ("word/styles.xml", STYLES)]
    parts += sorted((extra_parts or {}).items())   # sorted: dict order must not decide bytes
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        for name, data in parts:
            z.writestr(_member(name), data)


def p(*runs, ppr=""):
    return f"<w:p>{ppr}{''.join(runs)}</w:p>"


def r(text, rpr="", preserve=True):
    sp = ' xml:space="preserve"' if preserve else ""
    return f"<w:r>{rpr}<w:t{sp}>{text}</w:t></w:r>"


FIXTURES = {}


def fixture(name, why):
    def deco(fn):
        FIXTURES[name] = (why, fn)
        return fn
    return deco


# ---------------------------------------------------------------------------
# Branch 6 — things the writing-back step deletes because it does not recognise them.
# Three of these four reproduce from the corpus; they are built anyway so the suite is
# self-contained and runnable by someone with no access to the corpus at all.
# ---------------------------------------------------------------------------
@fixture("anchors-and-tabs.docx",
         "footnote anchor, comment anchor, hyperlink wrapping a tab-only run, a run carrying "
         "text THEN a tab, and a hanging-indent item whose tab PRECEDES its text — the five "
         "shapes branch 6 must preserve, plus a tab STOP as the negative control")
def _anchors(path):
    footnotes = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:footnotes {W}><w:footnote w:id="1"><w:p>{r("A note on the preceding clause.")}</w:p>
</w:footnote></w:footnotes>"""
    comments = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:comments {W}><w:comment w:id="1" w:author="Reviewer" w:date="2020-01-01T00:00:00Z">
<w:p>{r("Please confirm this figure.")}</w:p></w:comment></w:comments>"""
    body = (
        p(r("The first clause states a plain obligation."),
          '<w:r><w:footnoteReference w:id="1"/></w:r>') +
        '<w:p><w:commentRangeStart w:id="1"/>' + r("The second clause is under review.") +
        '<w:commentRangeEnd w:id="1"/><w:r><w:commentReference w:id="1"/></w:r></w:p>' +
        # A hyperlink whose only child run contains nothing but a tab. Rebuilding "only text"
        # deletes the run, and the empty hyperlink goes with it.
        p('<w:hyperlink r:id="rId9"><w:r><w:tab/></w:r></w:hyperlink>',
          r("Schedule 1")) +
        # A single run holding text, then a tab, then more text.
        p('<w:r><w:t xml:space="preserve">Party A</w:t><w:tab/>'
          '<w:t xml:space="preserve">Party B</w:t></w:r>') +
        # A HANGING-INDENT LIST ITEM WHOSE TAB PRECEDES ITS TEXT. Added 2026-09-01 for
        # branch 6: the four shapes above are all "tab after text or tab alone", and the
        # register's clearest visible consequence of mechanism A-ii is the opposite order.
        #
        # It is Wouter's D05 notices clause, reproduced as STRUCTURE with invented words
        # (CLAUDE.md 5.4 -- a fixture example must be synthetic, because anonymising a real
        # one still leaks its shape). A marker run, then a run whose children are
        # [rPr, tab, t]. With hanging=709 against left=1418 the tab is the ONLY thing
        # pushing the text out to the indent, so when apply destroyed it the line rendered
        # about 1.25 cm too far left -- while ind left/hanging and all 144 of numbering.xml's
        # w:ind elements stayed BYTE-IDENTICAL, which is why the paragraph properties looked
        # innocent and nothing pointed at the tab.
        #
        # This is the case that distinguishes "the preserved child came back" from "the
        # preserved child came back WHERE IT WAS", and no other fixture paragraph does.
        p(r("(a)"),
          '<w:r><w:rPr><w:sz w:val="20"/></w:rPr><w:tab/>'
          '<w:t xml:space="preserve">If to the first party:</w:t></w:r>',
          ppr='<w:pPr><w:ind w:left="1418" w:hanging="709"/></w:pPr>') +
        # A TAB THAT PRECEDES ALL THE TEXT IN ITS PARAGRAPH — the case where the true
        # position IS recoverable, and therefore the case that keeps the placement rule
        # honest. Added 2026-09-01 after Wouter's render review showed a misplaced tab does
        # visible harm and the rule became "keep it only where it can be placed truly".
        #
        # WITHOUT THIS PARAGRAPH THE RULE COULD NOT BE TESTED, only its negative half: a
        # suite that only ever asserts tabs are DROPPED would pass just as well against code
        # that deleted every tab unconditionally, which is the old defect. One run, the tab
        # before its text, no other text in the paragraph, so the tab belongs in front of the
        # rebuilt English and must still be there afterwards.
        p('<w:r><w:rPr><w:sz w:val="20"/></w:rPr><w:tab/>'
          '<w:t xml:space="preserve">Indented by a leading tab.</w:t></w:r>') +
        # A tab STOP in paragraph properties, which carries the same tag name as a rendered
        # tab and must never be counted with it.
        p(r("Indented line."),
          ppr='<w:pPr><w:tabs><w:tab w:val="left" w:pos="2268"/></w:tabs></w:pPr>')
    )
    ct = ('<Override PartName="/word/footnotes.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.footnotes+xml"/>\n'
          '<Override PartName="/word/comments.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.comments+xml"/>\n')
    # A RELATIONSHIP PART, WITHOUT WHICH NO RENDERER WILL OPEN THIS FILE AT ALL. Register
    # I-17, found 2026-08-21 while running branch 14's rendered comparison: LibreOffice
    # refused this fixture outright -- "source file could not be loaded" -- and refused the
    # ORIGINAL, so the cause was the fixture and not the branch. 8 of the 9 valid fixtures
    # rendered; this one did not.
    #
    # TWO CAUSES, AND BOTH HAD TO GO. The container held word/footnotes.xml and
    # word/comments.xml with nothing pointing at them, and the body already carried
    # `<w:hyperlink r:id="rId9">` referring to a relationship that did not exist. Either is
    # enough for a consumer to reject the package.
    #
    # WHY IT MATTERED ENOUGH TO FIX RATHER THAN NOTE. §4 puts BRANCH 18 on a rendered
    # comparison and says in terms that it cannot be byte-compared, so a fixture the renderer
    # will not open is a fixture branch 18 cannot use -- and this is the only fixture carrying
    # a footnote anchor and a comment anchor, which is precisely what a layout check needs to
    # see. Leaving it unrenderable meant no render-based test could ever reach the shapes this
    # fixture exists to carry.
    #
    # AND THE IRONY IS THE LESSON, KEPT RATHER THAN SMOOTHED AWAY: the fixture was unreadable
    # for exactly cluster A's reason. The content was in the container and the POINTER was not.
    rels = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/'
            '2006/relationships/styles" Target="styles.xml"/>'
            '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/'
            '2006/relationships/footnotes" Target="footnotes.xml"/>'
            '<Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/'
            '2006/relationships/comments" Target="comments.xml"/>'
            # The hyperlink the body already referenced. External, TargetMode="External", and
            # deliberately example.invalid: RFC 2606 reserves it, so nothing here can resolve
            # to a real host if a renderer ever tries.
            '<Relationship Id="rId9" Type="http://schemas.openxmlformats.org/officeDocument/'
            '2006/relationships/hyperlink" Target="https://example.invalid/schedule-1" '
            'TargetMode="External"/></Relationships>')
    docx(path, body, {"word/footnotes.xml": footnotes, "word/comments.xml": comments,
                      "word/_rels/document.xml.rels": rels}, ct)


# ---------------------------------------------------------------------------
# Branch 6 — A TABLE OF CONTENTS, because the real one cannot be looked at.
#
# Wouter read D06's rendered page 2 on 2026-09-01 and reported the table of contents coming
# out "terribly, with all page numbers not outlined to the right" plus a stray indent. That
# page is a client document: CLAUDE.md 6.5 means Claude may never view it, so the defect could
# be measured but not SEEN from this side. This fixture reproduces the SHAPE with invented
# words so it can be.
#
# The shape, from the register's own reading of D06 entry idx 21: a hyperlink containing
# number, tab, title, tab, page number — with real tab STOPS at the indent and at the right
# margin, which is what makes a dot leader and a right-aligned number possible at all. One
# entry's title is deliberately long enough to reach the margin, because that is the row where
# a stray trailing tab forces a WRAP rather than merely being invisible.
# ---------------------------------------------------------------------------
#
# SIX ENTRIES SINCE 2026-09-02, AND THEY ARE A TRUTH TABLE RATHER THAN A LONGER LIST. The tab
# placement rule reads two boundaries off the SOURCE paragraph -- the text before its first tab
# and the text after its last -- and requires both to survive into `en` unchanged. Four entries
# must therefore be PLACED and two must be DECLINED, and a fixture carrying only the placeable
# ones cannot tell a working rule from one that fires on everything.
#
#   1, 21, 22   plain: number, tab, title, tab, page, each tab in its own run.
#   23          THE REGRESSION TEST, and the reason this entry exists. Its FIRST RUN carries
#               text on BOTH SIDES of the tab -- children [t, tab, t] -- so extraction's
#               `runs[0]["text"]` is number+title while the tab sits after the number. An
#               earlier formulation of the rule used exactly that fragment for its offset and
#               would have placed the tab AFTER THE TITLE. The atom shape is identical, so no
#               shape test catches it; only this entry does.
#   24          DECLINE: the page digits differ between `text` and `en`, so the second
#               boundary is not proved. Must fall back to dropping.
#   25          DECLINE: the number is translated, so the first boundary is not proved. This is
#               D01's outcome -- three TOC-SHAPED paragraphs that are ordinary numbered prose,
#               where the real corpus measures 0 of 3 on every test.
# ---------------------------------------------------------------------------
@fixture("toc.docx",
         "a six-entry table of contents inside hyperlinks with real tab stops — four the "
         "placement rule must PLACE (one with its tab inside a text-bearing run) and two it "
         "must DECLINE — reproducing D06 page 2's shape so a rendered check can SEE what a "
         "client page may not show. Ships its own toc.notes.json")
def _toc(path):
    # Right-aligned stop at the text margin, with a dot leader: this is what a table of
    # contents uses, and it is why the page number lands at the right edge.
    ppr = ('<w:pPr><w:tabs>'
           '<w:tab w:val="left" w:pos="567"/>'
           '<w:tab w:val="right" w:leader="dot" w:pos="9070"/>'
           '</w:tabs></w:pPr>')

    # (number, title, page, kind). The XML AND the notes are both generated from this, so
    # `text` cannot disagree with the document -- it is not hand-typed anywhere.
    entries = [
        ("1", "General provisions", "4", "plain"),
        # LONG ENOUGH TO REACH THE MARGIN. This is the row that shows whether a stray tab
        # forces a wrap, which no count can see.
        ("21", "Project finance, security and the order of application of proceeds",
         "15", "plain"),
        ("22", "Governing law", "31", "plain"),
        ("23", "Interpretation and defined terms", "38", "inline-tab"),
        ("24", "Notices and service of process", "42", "decline-digits"),
        ("25", "Counterparts", "47", "decline-prefix"),
    ]

    def entry_xml(num, title, page, kind):
        if kind == "inline-tab":
            # ONE run carrying number, tab and title. Same atoms, different run boundaries.
            head = (f'<w:r><w:t xml:space="preserve">{num}</w:t><w:tab/>'
                    f'<w:t xml:space="preserve">{title}</w:t></w:r>')
        else:
            head = (f'<w:r><w:t xml:space="preserve">{num}</w:t></w:r>'
                    f'<w:r><w:tab/></w:r>'
                    f'<w:r><w:t xml:space="preserve">{title}</w:t></w:r>')
        return p(f'<w:hyperlink r:id="rId9">{head}'
                 f'<w:r><w:tab/></w:r>'
                 f'<w:r><w:t xml:space="preserve">{page}</w:t></w:r>'
                 f'</w:hyperlink>', ppr=ppr)

    heading = "Table of contents"
    body = p(r(heading)) + "".join(entry_xml(*e) for e in entries)
    rels = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/'
            'relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/'
            '2006/relationships/styles" Target="styles.xml"/>'
            '<Relationship Id="rId9" Type="http://schemas.openxmlformats.org/officeDocument/'
            '2006/relationships/hyperlink" Target="https://example.invalid/clause" '
            'TargetMode="External"/></Relationships>')
    docx(path, body, {"word/_rels/document.xml.rels": rels})

    # --- THE NOTES, generated from the same data ------------------------------------------
    # `runs` mirrors what extraction really emits, measured on D06's 26 entries: TWO
    # fragments, never three, carrying start/end offsets into `text`. For the inline-tab
    # entry the fragments follow the RUN boundaries instead, which is what makes it the
    # regression test.
    notes = [_note(0, heading, heading + " EN", [(0, len(heading))])]
    for i, (num, title, page, kind) in enumerate(entries, start=1):
        text = num + title + page
        if kind == "decline-digits":
            en = num + title + " EN" + str(int(page) + 57)
        elif kind == "decline-prefix":
            en = "Clause " + num + title + " EN" + page
        else:
            en = num + title + " EN" + page
        if kind == "inline-tab":
            spans = [(0, len(num) + len(title)), (len(num) + len(title), len(text))]
        else:
            spans = [(0, len(num)), (len(num), len(text))]
        notes.append(_note(i, text, en, spans))
    _write_notes(path, notes)


def _note(idx, text, en, spans):
    return {"idx": idx, "text": text, "en": en, "style": "Normal",
            "runs": [{"start": s, "end": e, "text": text[s:e],
                      "bold": False, "italic": False} for s, e in spans]}


def _write_notes(docx_path, notes):
    """Write `<stem>.notes.json` beside the fixture, and PROVE it agrees with the document.

    A fixture's notes are its INPUT, so they belong with it rather than being invented by
    whichever tool happens to drive it -- which is what `render_diff.py` did, synthesising
    `en = text + " EN"` and no `runs` at all, so a rule keyed on either could not fire on a
    fixture at all.

    Written as BYTES with explicit \\n. `Path.write_text()` opens in text mode, so on Windows
    every \\n becomes \\r\\n and an LF file silently turns CRLF with its content perfectly
    intact -- every content check passes and only a line-endings check sees it.
    """
    import xml.etree.ElementTree as ET      # READING only; never used to write OOXML
    out = docx_path.with_suffix(".notes.json")
    payload = json.dumps(notes, ensure_ascii=False, indent=2) + "\n"
    out.write_bytes(payload.encode("utf-8"))

    # ASSERT THE ARTEFACT. The notes are generated from the same data as the XML, so they
    # agree by construction -- but "by construction" is an argument, and this is a check.
    # `text` must equal what apply's own get_paragraph_text() computes: w:t only, no space
    # at a tab.
    wns = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
    with zipfile.ZipFile(docx_path) as z:
        root = ET.fromstring(z.read("word/document.xml"))
    actual = ["".join(t.text or "" for t in para.iter(f"{wns}t"))
              for para in root.iter(f"{wns}p")]
    declared = [n["text"] for n in notes]
    if actual != declared:
        raise AssertionError(
            f"{out.name}: `text` disagrees with the document it describes — "
            f"{len(actual)} paragraph(s) in the XML, {len(declared)} note(s); "
            f"first mismatch at index "
            f"{next((i for i, (x, y) in enumerate(zip(actual, declared)) if x != y), 'length')}")
    for n in notes:
        for run in n["runs"]:
            if n["text"][run["start"]:run["end"]] != run["text"]:
                raise AssertionError(f"{out.name}: idx {n['idx']} run offsets do not slice "
                                     f"`text` back to the fragment they declare")


# ---------------------------------------------------------------------------
# Branch 6, clause 3 — the ONE case in option 1 that is a DELETION rather than a
# preservation. Added 2026-09-01, and it had to be built: anchors-and-tabs.docx carries no
# field skeleton, and STEP-B-ANALYSIS.md section 3.7's own fixture list for branch 6 does not
# name one either, so finding A9's only instrument was the D06 frozen intermediate.
# ---------------------------------------------------------------------------
@fixture("toc-widened.docx",
         "the three page-number forms the placement rule admits after the 2026-09-02 "
         "widening — arabic, roman (both cases, and compound) and prefixed A-3 — beside the "
         "TWO it must still refuse. Built so the widening can be SEEN on a page: no corpus "
         "document carries a roman or prefixed page number, so this is the only render there "
         "can ever be. Ships its own toc-widened.notes.json")
def _toc_widened(path):
    """A contents page exercising every branch of `_is_page_number`, placed beside its traps.

    WHY A SECOND TOC FIXTURE RATHER THAN SIX MORE ROWS IN `toc.docx`. That one is the
    instrument `tests/test_stop_deleting.py` section 5 counts against -- four placeable, two
    declining, twelve tab characters, twelve tab stops, six hyperlinks. Adding rows would move
    every one of those numbers and force an edit to a suite this branch must not touch. A new
    fixture costs two committed files and breaks nothing.

    AND THE LAST TWO ENTRIES ARE THE POINT OF IT. A fixture carrying only the shapes a rule
    places cannot tell a working rule from one that fires on everything -- the same argument
    that put two declining entries in `toc.docx`. Here they are sharper, because the widening
    is what spends the margin: `Signature` is an ordinary word in the page-number position on
    a line that is not a contents entry at all, and `civil` is the word every letter of which
    is a roman letter. Both must render FLAT while the five above them render with a leader.
    """
    ppr = ('<w:pPr><w:tabs>'
           '<w:tab w:val="left" w:pos="567"/>'
           '<w:tab w:val="right" w:leader="dot" w:pos="9070"/>'
           '</w:tabs></w:pPr>')

    # (number, title, page, must-place). The XML AND the notes are generated from this, so
    # `text` cannot disagree with the document -- it is not hand-typed anywhere.
    entries = [
        ("1", "General provisions", "4", True),            # arabic: unchanged by the widening
        ("2", "Preface", "iv", True),                       # roman, lower
        ("3", "Foreword", "IV", True),                      # roman, upper
        ("4", "Table of defined terms", "xii", True),       # roman, compound
        ("A.1", "Schedule of works", "A-3", True),          # prefixed
        ("Party", "Registered office", "Signature", False),  # the false positive
        ("5", "Jurisdiction", "civil", False),              # the character-class trap
    ]

    def entry_xml(num, title, page, _place):
        return p(f'<w:hyperlink r:id="rId9">'
                 f'<w:r><w:t xml:space="preserve">{num}</w:t></w:r>'
                 f'<w:r><w:tab/></w:r>'
                 f'<w:r><w:t xml:space="preserve">{title}</w:t></w:r>'
                 f'<w:r><w:tab/></w:r>'
                 f'<w:r><w:t xml:space="preserve">{page}</w:t></w:r>'
                 f'</w:hyperlink>', ppr=ppr)

    heading = "Contents"
    body = p(r(heading)) + "".join(entry_xml(*e) for e in entries)
    rels = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/'
            'relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/'
            '2006/relationships/styles" Target="styles.xml"/>'
            '<Relationship Id="rId9" Type="http://schemas.openxmlformats.org/officeDocument/'
            '2006/relationships/hyperlink" Target="https://example.invalid/clause" '
            'TargetMode="External"/></Relationships>')
    docx(path, body, {"word/_rels/document.xml.rels": rels})

    notes = [_note(0, heading, heading + " EN", [(0, len(heading))])]
    for i, (num, title, page, _place) in enumerate(entries, start=1):
        text = num + title + page
        en = num + title + " EN" + page
        spans = [(0, len(num)), (len(num), len(text))]
        notes.append(_note(i, text, en, spans))
    _write_notes(path, notes)


@fixture("cross-reference.docx",
         "a REF field whose cached result IS consumed — clause 3 must drop the whole "
         "skeleton or the number prints twice — and a PAGE field with no cached result, "
         "which must be preserved untouched: the positive and the negative in one document")
def _crossref(path):
    # THE POSITIVE. A field is a SEQUENCE of runs, not one element: begin, the instruction,
    # separate, the CACHED RESULT, end. Extraction folds the cached result into `text`, so the
    # operator's English legitimately contains the number -- and apply then deletes the
    # cached-result run (text-bearing) while PRESERVING the skeleton (fldChar and instrText
    # are both whitelisted). Word and LibreOffice re-evaluate the now-empty skeleton when the
    # file is opened and print the value a second time.
    #
    # On D06 that was 42 paragraphs, six of which also resurrected the literal string
    # "Error: Reference source not found". Caught ONLY by rendering: validate_apply polices
    # MISSING tokens and never EXTRA ones, the remnant scan looks for source language, and
    # quality_check has no duplicated-cross-reference rule. verify_diligence reported
    # OVERALL PASS.
    consumed = (
        '<w:r><w:fldChar w:fldCharType="begin"/></w:r>'
        '<w:r><w:instrText xml:space="preserve"> REF _Ref100 \\h </w:instrText></w:r>'
        '<w:r><w:fldChar w:fldCharType="separate"/></w:r>'
        + r("3.2") +
        '<w:r><w:fldChar w:fldCharType="end"/></w:r>'
    )
    # THE NEGATIVE, and it is what stops clause 3 becoming "delete every field". This one has
    # NO separate and NO cached result, so nothing of it is consumed into the English: the
    # skeleton is the only copy of the instruction and must survive. A fix that drops both is
    # indistinguishable from the correct fix if only the positive is tested.
    unevaluated = (
        '<w:r><w:fldChar w:fldCharType="begin"/></w:r>'
        '<w:r><w:instrText xml:space="preserve"> PAGE </w:instrText></w:r>'
        '<w:r><w:fldChar w:fldCharType="end"/></w:r>'
    )
    # THE SECOND NEGATIVE, AND IT IS THE ONE THAT NEARLY GOT MISSED. This field DOES have a
    # cached result, so the rule "delete the skeleton once its cached result is consumed"
    # would delete it -- and a PAGE field frozen at whatever number happened to be cached
    # prints the same page number on every page. A9's evidence is REF fields; every other
    # field type must survive even when its result IS consumed, which is why clause 3 tests
    # the instruction KEYWORD and not merely the presence of a result.
    #
    # Measured 2026-09-01 across the whole corpus: the only cached-result fields in the
    # eleven documents are D06's 45 REF fields, so no corpus document can exercise this. It
    # had to be built, exactly like branch 7's four containers.
    cached_non_ref = (
        '<w:r><w:fldChar w:fldCharType="begin"/></w:r>'
        '<w:r><w:instrText xml:space="preserve"> PAGE </w:instrText></w:r>'
        '<w:r><w:fldChar w:fldCharType="separate"/></w:r>'
        + r("7") +
        '<w:r><w:fldChar w:fldCharType="end"/></w:r>'
    )
    body = (
        p(r("Cross-reference to "), consumed, r(" of this agreement.")) +
        p(r("Page "), unevaluated, r(" of the schedule.")) +
        p(r("See page "), cached_non_ref, r(" for the notices clause.")) +
        p(r("A clause with no field at all, as the quiet control."))
    )
    docx(path, body)


# ---------------------------------------------------------------------------
# Branch 7 — the container inventory. NONE of these four is reproducible from any corpus
# document, which is the entire reason they exist.
# ---------------------------------------------------------------------------
@fixture("containers.docx",
         "content control, smart tag, image with alt text, chart with a title — four "
         "containers holding translatable text, NONE reproducible from the corpus")
def _containers(path):
    body = (
        # A content control (structured document tag) wrapping a paragraph.
        '<w:sdt><w:sdtPr><w:alias w:val="Party name"/></w:sdtPr><w:sdtContent>' +
        p(r("The Supplier shall deliver the goods.")) +
        '</w:sdtContent></w:sdt>' +
        # A smart tag wrapping a run.
        p('<w:smartTag w:element="place">' + r("Rotterdam") + '</w:smartTag>',
          r(" is the place of delivery.")) +
        # An inline image whose alt text is translatable and lives in graphic metadata.
        p('<w:r><w:drawing><wp:inline><wp:docPr id="1" name="Diagram"'
          ' descr="Flow chart showing the approval sequence"/>'
          '<a:graphic><a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/picture"/>'
          '</a:graphic></wp:inline></w:drawing></w:r>') +
        # A chart title, in its own part, reachable only through the relationship.
        p(r("The figures are set out in the chart below."))
    )
    chart = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
             '<c:chartSpace xmlns:c="http://schemas.openxmlformats.org/drawingml/2006/chart"'
             ' xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"><c:chart>'
             '<c:title><c:tx><c:rich><a:p><a:r><a:t>Deliveries by quarter</a:t></a:r>'
             '</a:p></c:rich></c:tx></c:title></c:chart></c:chartSpace>')
    docx(path, body, {"word/charts/chart1.xml": chart, "word/media/image1.png": PNG})


@fixture("symbol-font.docx",
         "runs in Symbol and Wingdings. The corpus has NO such run anywhere, so the "
         "Greek-glyph defect cannot be reproduced from a real document at all")
def _symbol(path):
    body = (
        p(r("The threshold is "),
          '<w:r><w:rPr><w:rFonts w:ascii="Symbol" w:hAnsi="Symbol"/></w:rPr>'
          '<w:t>a</w:t></w:r>',
          r(" per cent.")) +
        p('<w:r><w:rPr><w:rFonts w:ascii="Wingdings" w:hAnsi="Wingdings"/></w:rPr>'
          '<w:t>ü</w:t></w:r>',
          r(" Completed."))
    )
    docx(path, body)


# ---------------------------------------------------------------------------
# The formatting class — the largest group of findings, and the one the data contract
# cannot currently describe.
# ---------------------------------------------------------------------------
@fixture("emphasis-three-ways.docx",
         "bold reaching a run three ways — run flag, character style, paragraph style — "
         "plus an explicit bold-OFF flag, which means NOT bold and is read as bold by a "
         "naive check")
def _emphasis(path):
    body = (
        p('<w:r><w:rPr><w:b/></w:rPr><w:t>Bold by a run flag.</w:t></w:r>') +
        p('<w:r><w:rPr><w:rStyle w:val="StrongEmph"/></w:rPr>'
          '<w:t>Bold by a character style.</w:t></w:r>') +
        p(r("Bold by a paragraph style."),
          ppr='<w:pPr><w:pStyle w:val="BoldClause"/></w:pPr>') +
        # w:val="0" means bold OFF. Any check reading the presence of <w:b> and not its
        # value gets this exactly backwards.
        p('<w:r><w:rPr><w:b w:val="0"/></w:rPr><w:t>Explicitly NOT bold.</w:t></w:r>') +
        p('<w:r><w:rPr><w:b w:val="false"/><w:i w:val="off"/></w:rPr>'
          '<w:t>Neither bold nor italic, spelled two other ways.</w:t></w:r>')
    )
    docx(path, body)


@fixture("tracked-changes.docx",
         "an insertion, a deletion, and a deletion whose text is in the source language — "
         "the document must read correctly both when accepted and when rejected")
def _tracked(path):
    body = (
        p(r("The term is "),
          '<w:ins w:id="1" w:author="A" w:date="2020-01-01T00:00:00Z">'
          '<w:r><w:t xml:space="preserve">five</w:t></w:r></w:ins>',
          '<w:del w:id="2" w:author="A" w:date="2020-01-01T00:00:00Z">'
          '<w:r><w:delText xml:space="preserve">three</w:delText></w:r></w:del>',
          r(" years.")) +
        p(r("De overeenkomst "),
          '<w:del w:id="3" w:author="B" w:date="2020-01-01T00:00:00Z">'
          '<w:r><w:delText xml:space="preserve">eindigt van rechtswege</w:delText>'
          '</w:r></w:del>',
          r(" on the final date."))
    )
    docx(path, body)


@fixture("table-nested.docx",
         "a signature block inside a table — paragraphs that extraction and apply must "
         "BOTH recurse into, or they ship untranslated")
def _table(path):
    cell = ('<w:tc><w:tcPr><w:tcW w:w="4500" w:type="dxa"/></w:tcPr>{}</w:tc>')
    body = (
        p(r("Signed for and on behalf of the parties:")) +
        '<w:tbl><w:tblPr><w:tblW w:w="9000" w:type="dxa"/></w:tblPr><w:tr>' +
        cell.format(p(r("For the Supplier"))) +
        cell.format(p(r("For the Customer"))) +
        '</w:tr><w:tr>' +
        cell.format(p(r("Name: ____________"))) +
        cell.format(p(r("Name: ____________"))) +
        '</w:tr></w:tbl>'
    )
    docx(path, body)


@fixture("definitions.docx",
         "a definitions block whose source-language alphabetical order is NOT English "
         "alphabetical order — and properties must be matched BY TERM, never by index, "
         "because this step permutes the block")
def _definitions(path):
    body = (
        p(r("1. Definitions")) +
        p(r('"Overeenkomst" means the agreement between the parties.')) +
        p(r('"Aanvangsdatum" means the date on which the term begins.')) +
        p(r('"Zekerheid" means any security given under this agreement.')) +
        p(r('"Betaling" means a payment due under clause 4.'))
    )
    docx(path, body)


@fixture("headers-footers.docx",
         "a header and a footer carrying translatable text — the auxiliary parts whose "
         "English is produced perfectly and whose POINTER is what gets destroyed")
def _hf(path):
    hdr = (f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
           f'<w:hdr {W}>{p(r("Vertrouwelijk — conceptversie"))}</w:hdr>')
    ftr = (f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
           f'<w:ftr {W}>{p(r("Pagina 1 van 1"))}</w:ftr>')
    rels = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId10" Type="http://schemas.openxmlformats.org/officeDocument/'
            '2006/relationships/header" Target="header1.xml"/>'
            '<Relationship Id="rId11" Type="http://schemas.openxmlformats.org/officeDocument/'
            '2006/relationships/footer" Target="footer1.xml"/></Relationships>')
    body = p(r("The body text of the instrument."))
    ct = ('<Override PartName="/word/header1.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.header+xml"/>\n'
          '<Override PartName="/word/footer1.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.footer+xml"/>\n')
    docx(path, body, {"word/header1.xml": hdr, "word/footer1.xml": ftr,
                      "word/_rels/document.xml.rels": rels}, ct)


@fixture("empty.docx", "a valid document with no paragraphs at all — the degenerate input")
def _empty(path):
    docx(path, "")


@fixture("not-a-zip.docx",
         "a file with a .docx name that is not a ZIP — the delivered-document integrity "
         "test must FAIL on this, and today a failed integrity test exits 0")
def _notzip(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"This is not a ZIP container.\n")


@fixture("truncated.docx",
         "a real .docx cut off mid-file — a corrupt container that still looks plausible")
def _truncated(path):
    src = OUT / "anchors-and-tabs.docx"
    data = src.read_bytes()
    path.write_bytes(data[:int(len(data) * 0.6)])


def main():
    if "--list" in sys.argv:
        for name, (why, _) in FIXTURES.items():
            print(f"  {name:<26} {why}")
        return 0

    # OVERWRITE IN PLACE, THEN PRUNE — never rmtree first. This used to be
    #
    #     if OUT.exists(): shutil.rmtree(OUT)
    #     OUT.mkdir(parents=True)
    #
    # which opens a window in which the fixture set does not exist, and EVERY suite in this
    # project needs it. An interrupted build therefore does not merely fail: it leaves the
    # harness unable to run at all, and the failure that follows looks like a corrupt fixture
    # rather than a missing one.
    #
    # THAT IS NOT HYPOTHETICAL. On 2026-08-21 a build was killed partway and left 3 of 11
    # fixtures on disk; the next suite to run died with BadZipFile, which reads exactly like a
    # damaged document. Recovery was only possible because the fixtures are committed. The
    # killed build reported exit 0, so nothing announced it.
    #
    # Overwriting is safe precisely BECAUSE a build is byte-reproducible (see FIXED_TIME):
    # rewriting a fixture with identical bytes is a no-op, so there is no reason to clear the
    # directory first. Anything stale is removed afterwards, once the replacements exist.
    OUT.mkdir(parents=True, exist_ok=True)
    _expected = set(FIXTURES)

    print("=" * 96)
    print("SYNTHETIC FIXTURES — every one invented; none derived from a real document")
    print("=" * 96)
    for name, (why, fn) in FIXTURES.items():
        path = OUT / name
        fn(path)
        size = path.stat().st_size
        ok = ""
        if name not in ("not-a-zip.docx", "truncated.docx"):
            try:
                with zipfile.ZipFile(path) as z:
                    bad = z.testzip()
                ok = "valid ZIP" if bad is None else f"CORRUPT at {bad}"
            except zipfile.BadZipFile:
                ok = "NOT A ZIP — unexpected"
        else:
            ok = "deliberately invalid"
        print(f"  {name:<26} {size:>7,} B  {ok}")
        # A FIXTURE MAY SHIP ITS OWN NOTES, and if it does, say so: the notes are the input
        # a driving tool would otherwise invent, so which one was used is not a detail.
        side = path.with_suffix(".notes.json")
        if side.is_file():
            n = len(json.loads(side.read_text(encoding="utf-8")))
            print(f"  {'':<26} + {side.name}  ({n} note(s), agreement with the document "
                  f"asserted)")
        print(f"  {'':<26} {why}")
    # PRUNE ONLY NOW, once every replacement is on disk. A fixture that is no longer declared
    # is removed; nothing is removed before its successor exists.
    stale = sorted(p for p in OUT.glob("*.docx") if p.name not in _expected)
    for p in stale:
        p.unlink()
        print(f"  removed stale fixture: {p.name}")

    print("=" * 96)
    # ASSERT THE ARTEFACT, NOT THE EXIT CODE. A killed build reports 0, so the count of files
    # actually on disk is the only trustworthy statement that this finished — and it is
    # returned as a non-zero exit if it disagrees, so a caller reading only the code still
    # learns something true.
    on_disk = sorted(p.name for p in OUT.glob("*.docx"))
    if set(on_disk) != _expected:
        print(f"  INCOMPLETE — {len(on_disk)} of {len(FIXTURES)} fixtures on disk")
        for miss in sorted(_expected - set(on_disk)):
            print(f"    MISSING {miss}")
        return 1
    print(f"  {len(FIXTURES)} fixtures in {OUT.relative_to(ROOT)}, all present on disk")
    return 0


if __name__ == "__main__":
    sys.exit(main())
