# -*- coding: utf-8 -*-
"""WHICH TABLE-OF-CONTENTS SHAPES DOES THE PLACEMENT RULE REACH? — the coverage sweep.

Wouter, 2026-09-02, on being shown the fix: "did you actually make sure that this fix would
also apply to ALL types of TOCs (with tabs and page numbers) and not only the one that the
defects surfaced from?"

THE ANSWER CANNOT COME FROM THE CORPUS, AND THAT IS WHY THIS FILE EXISTS. D06 is the only one
of eleven documents with a table of contents at all, so every real measurement this project
has -- 26 of 26 on three separate tests -- is a measurement of ONE DOCUMENT'S HOUSE STYLE.
CLAUDE.md 5.7 names this case exactly: what the corpus cannot reach needs synthetic fixtures.
A rule measured at 100% on one document is not a rule measured at 100%.

IT FOUND TWO DEFECTS ON ITS FIRST RUN, both invisible to the corpus. A page-number run written
`"5 "` and a number run written `" 5"` -- ordinary authoring whitespace, saying nothing about
whether a boundary is provable -- both DECLINED, because `pre` and `post` came from the source
untrimmed while `en_text` had already been through `_strip_keeping_separators`. D06 carries no
such whitespace on any of its 26 entries, so nothing in the real evidence base could have
shown it.

THAT QUESTION WAS PUT TO WOUTER AND HE ANSWERED IT, 2026-09-02, AND THE FILE GREW FROM TWELVE
SHAPES TO EIGHTEEN. Two shapes stood here DECLINED BY DECISION rather than by defect -- a
ROMAN-NUMERAL page number (front matter) and a PREFIXED one such as `A-3` (schedules) -- on
the reasoning that both translate to themselves, so both were placeable in principle, and that
widening a shipped tree belongs to whoever decides it rather than whoever notices it. He
decided to widen. Both now expect PLACED, and the rows say so in place rather than quietly
reading as though they always had.

AND IT GREW AGAIN TO TWENTY-SIX ON 2026-09-02, BECAUSE HE ASKED THE SAME QUESTION A SECOND
TIME — "did you cover all types of TOCs?" — after branch 6 had closed. **Eighteen of eighteen
agreeing could not answer that, and the reason is this file's own argument turned on itself: a
sweep proves coverage of its POPULATION and of nothing else.** 18 of 18 over a list I wrote is
the same kind of claim as 26 of 26 over D06's house style.

**THE EIGHT NEW SHAPES FOUND FOUR SILENT IMPROVEMENTS AND TWO UNRECORDED OPEN EDGES.** Run
against apply at `79a8c14`, the commit before branch 6 began, **all eight declined and none
placed**; now a roman ENTRY number, a lower-case `a-3` and the five-atom shape **inside a table
cell** all place, and an indented sub-entry keeps a leading tab the old code destroyed. And a
page **range** `4-7` and a trailing full stop `4.` decline **by decision**, which took the
count of open page-number edges from the one `Sch-3` that was recorded to three.

**THE INDENTED SUB-ENTRY ALSO BROKE THE VERDICT TEST, which is the more useful half.** It
declines while PRESERVING its leading tab, so its atoms are `['tab', 'text']` — and
`DECLINED` was tested as `atoms == ['text']`, so the row read `BROKEN`, a verdict that says
damage where the truth is a decline plus a repair. A decline means the English collapsed into
ONE run, whatever structural runs survive beside it. The summary counters had a SECOND copy of
that rule and disagreed with the per-row test: 14 + 10 + 1 against 26 shapes, a sum that does
not add up and that nothing asserted. Both now read one list, and the arithmetic is asserted.

AND THE WIDENING ARRIVED WITH FOUR NEGATIVES, WHICH ARE THE HALF THAT MATTERS. The page-number
test is the only thing between the five-atom shape and any three-part tabbed line whose last
part survives translation, so widening it spends margin. `civil` is the sharpest of the four:
every one of its letters is a roman letter, so the obvious `[ivxlcdm]+` admits it -- and so
would it admit `dill`, `lid` and `mix`. A rule that fires on everything passes every assertion
about the shapes it gets right, which is why these four are here and why the control below
demands that something DECLINE as well as something place.

Each shape runs through THE REAL APPLY SCRIPT, end to end. A predicate tested in isolation can
return the right answer while apply drops the tab anyway, and that would read as a pass.

VERDICTS: PLACED (source atom sequence restored) · DECLINED (fell back to dropping, the
pre-existing behaviour) · SKIPPED (en == text, never rebuilt) · BROKEN (anything else, which
is a defect). Every expectation is written down BEFORE the run, so a surprise is visible
rather than rationalised afterwards.

OUTPUT POLICY: synthetic throughout. Every string is invented for this file.

    uv run --with lxml python tests/test_toc_shapes.py
"""
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tests"))
# IMPORTED BEFORE stdout IS WRAPPED, DELIBERATELY. `make_fixtures` rebinds `sys.stdout` to a
# fresh TextIOWrapper over `sys.stdout.buffer` at module level; wrapping first and importing
# second stacks two wrappers on one buffer, and when the outer one is collected it CLOSES that
# buffer -- so the script does its whole job and then dies on its closing print with
# "I/O operation on closed file". Measured here, first run.
from make_fixtures import docx, p, r  # noqa: E402
from lxml import etree  # noqa: E402

# AND NO WRAPPER OF OUR OWN, WHICH IS THE OTHER HALF OF THE SAME HAZARD. `make_fixtures` has
# already installed a UTF-8 wrapper over the original buffer. Assigning a SECOND one drops the
# last reference to the first, which is then garbage-collected -- closing the buffer BOTH
# share. The script completes its whole job and dies on its closing print. Two runs lost to
# this before the cause was read rather than guessed.
assert isinstance(sys.stdout, io.TextIOWrapper), "expected make_fixtures to wrap stdout"

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
PPR = ('<w:pPr><w:tabs><w:tab w:val="left" w:pos="567"/>'
       '<w:tab w:val="right" w:leader="dot" w:pos="9070"/></w:tabs></w:pPr>')


def t(s):
    return f'<w:t xml:space="preserve">{s}</w:t>'


def entry(num, title, page, wrap=True):
    """The shape the fix was measured on: number, tab, title, tab, page, inside a hyperlink."""
    body = (f'<w:r>{t(num)}</w:r><w:r><w:tab/></w:r><w:r>{t(title)}</w:r>'
            f'<w:r><w:tab/></w:r><w:r>{t(page)}</w:r>')
    return p(f'<w:hyperlink r:id="rId9">{body}</w:hyperlink>' if wrap else body, ppr=PPR)


# ---------------------------------------------------------------------------------------
# THE SHAPES. Each is (label, paragraph XML, source `text`, declared `en`, what SHOULD happen
# and WHY). "should" is my expectation written down BEFORE the run, so a surprise is visible
# rather than rationalised afterwards.
# ---------------------------------------------------------------------------------------
CASES = [
    ("baseline: number/tab/title/tab/page",
     entry("1", "General provisions", "4"),
     "1General provisions4", "1General provisions EN4",
     "PLACED", "the shape the fix was built and measured on"),

    ("sub-numbered 1.2.3",
     entry("1.2.3", "Order of application", "12"),
     "1.2.3Order of application12", "1.2.3Order of application EN12",
     "PLACED", "a multi-level clause number still translates to itself"),

    ("NO leading number (unnumbered heading)",
     p(f'<w:hyperlink r:id="rId9"><w:r>{t("Introduction")}</w:r>'
       f'<w:r><w:tab/></w:r><w:r>{t("2")}</w:r></w:hyperlink>', ppr=PPR),
     "Introduction2", "Introduction EN2",
     "DECLINED", "three atoms, not five -- and the ONE tab's left side is a TRANSLATED title, "
                 "so its position is not provable"),

    ("roman-numeral page (front matter)",
     entry("1", "Preface", "iv"),
     "1Prefaceiv", "1Preface ENiv",
     "PLACED", "WIDENED 2026-09-02, AND THIS ROW READ `DECLINED` UNTIL THEN — by decision, "
               "never by defect. A roman numeral translates to itself exactly as an arabic "
               "one does, so front matter was placeable the whole time and was declined only "
               "because nobody had decided to admit it. Wouter decided to"),

    ("roman-numeral page, UPPER case",
     entry("2", "Foreword", "IV"),
     "2ForewordIV", "2Foreword ENIV",
     "PLACED", "the widening is not lower-case-only. Some front matter is set in capitals, "
               "and a rule that reached only one case would be a half-widening nobody "
               "measured"),

    ("roman-numeral page, multi-character",
     entry("3", "Table of defined terms", "xii"),
     "3Table of defined termsxii", "3Table of defined terms ENxii",
     "PLACED", "nor single-letter-only. Front matter routinely runs past x, and a "
               "well-formedness test has to admit the compound forms to be worth having"),

    ("prefixed page number A-3",
     entry("A.1", "Schedule of works", "A-3"),
     "A.1Schedule of worksA-3", "A.1Schedule of works ENA-3",
     "PLACED", "WIDENED 2026-09-02, and this row read `DECLINED` until then for the same "
               "reason as the roman numeral. Schedules and annexes number their pages this "
               "way, and `A-3` translates to itself"),

    ("`civil` in the page-number position",
     entry("9", "Jurisdiction", "civil"),
     "9Jurisdictioncivil", "9Jurisdiction ENcivil",
     "DECLINED", "THE CHARACTER-CLASS TRAP, and the reason the roman test is a "
                 "WELL-FORMEDNESS test rather than `[ivxlcdm]+`: every letter of `civil` is "
                 "a roman letter, so a character class admits it — and so would it admit "
                 "`mix`, `dill` and `lid`. `IL` is not a legal pair, so a well-formedness "
                 "test does not. This shape is why the pattern is the long one"),

    ("mixed-case roman `Iv`",
     entry("10", "Recitals", "Iv"),
     "10RecitalsIv", "10Recitals ENIv",
     "DECLINED", "uniform case is required, and it is enforced in Python rather than in the "
                 "regex because an inline `(?i:)` cannot express `all one case`. `Iv` is a "
                 "page number in no house style, and admitting it would buy nothing"),

    ("an ordinary WORD that survives translation",
     entry("Party", "Registered office", "Signature"),
     "PartyRegistered officeSignature", "PartyRegistered office ENSignature",
     "DECLINED", "THE FALSE POSITIVE THE PAGE-NUMBER TEST EXISTS TO STOP, and the one this "
                 "widening spends margin against: a three-part tabbed line that is not a "
                 "table of contents at all — a party grid, a cost table, a signature block. "
                 "The atoms are the five, BOTH boundaries survive translation, and the "
                 "page-number test is the only thing that tells it from a TOC entry"),

    ("three-letter prefix `Sch-3`",
     entry("B.1", "Annex of forms", "Sch-3"),
     "B.1Annex of formsSch-3", "B.1Annex of forms ENSch-3",
     "DECLINED", "the widening has a stated edge and stops at it — one or two letters before "
                 "the separator. A longer prefix is prose until somebody measures one, and "
                 "recording the edge here is what makes moving it later a decision"),

    ("literal dot leader inside the title",
     entry("2", "Governing law..........", "31"),
     "2Governing law..........31", "2Governing law EN..........31",
     "PLACED", "the dots ride along in the title; both boundaries are untouched"),

    ("page number inside a PAGEREF field with a cached result",
     p('<w:hyperlink r:id="rId9">'
       f'<w:r>{t("3")}</w:r><w:r><w:tab/></w:r><w:r>{t("Interpretation")}</w:r>'
       '<w:r><w:tab/></w:r>'
       '<w:r><w:fldChar w:fldCharType="begin"/></w:r>'
       '<w:r><w:instrText xml:space="preserve"> PAGEREF _Ref1 \\h </w:instrText></w:r>'
       '<w:r><w:fldChar w:fldCharType="separate"/></w:r>'
       f'<w:r>{t("7")}</w:r>'
       '<w:r><w:fldChar w:fldCharType="end"/></w:r>'
       '</w:hyperlink>', ppr=PPR),
     "3Interpretation7", "3Interpretation EN7",
     "PLACED", "instrText is not a text atom, so the atom sequence is still the five"),

    ("TRAILING SPACE in the page-number run",
     entry("4", "Notices", "5 "),
     "4Notices5", "4Notices EN5",
     "PLACED", "REGRESSION GUARD. This DECLINED on the sweep's first run: `post` came from "
               "the source carrying its trailing space while `en_text` had already been "
               "stripped, so `endswith` failed on whitespace that says nothing about whether "
               "the boundary is provable. D06 has none of it, so the corpus was blind to it"),

    ("LEADING SPACE in the number run",
     entry(" 5", "Counterparts", "9"),
     "5Counterparts9", "5Counterparts EN9",
     "PLACED", "REGRESSION GUARD, the same defect at the other end: `pre` carried its "
               "leading space and `startswith` failed. Only the OUTER edges are trimmed — "
               "whitespace beside a tab is interior to `en_text` and is part of the boundary"),

    ("two tabs between number and title",
     p(f'<w:hyperlink r:id="rId9"><w:r>{t("6")}</w:r><w:r><w:tab/></w:r>'
       f'<w:r><w:tab/></w:r><w:r>{t("Assignment")}</w:r>'
       f'<w:r><w:tab/></w:r><w:r>{t("14")}</w:r></w:hyperlink>', ppr=PPR),
     "6Assignment14", "6Assignment EN14",
     "DECLINED", "six atoms -- the rule cannot know which gap is which"),

    ("no hyperlink wrapper (a plain typed TOC)",
     entry("7", "Termination", "18", wrap=False),
     "7Termination18", "7Termination EN18",
     "PLACED", "the wrapper is irrelevant to the placement; only the atoms matter"),

    ("title that is ALREADY English (apply skips it)",
     entry("8", "Force majeure", "22"),
     "8Force majeure22", "8Force majeure22",
     "SKIPPED", "en == text, so apply never rebuilds it -- and it was already correct"),

    # -----------------------------------------------------------------------------------
    # EIGHT SHAPES ADDED 2026-09-02, AND THEY CAME FROM THE QUESTION BEING ASKED A SECOND
    # TIME. Wouter, on being told branch 6 was closed: "did you cover all types of TOCs?"
    #
    # THE FIRST EIGHTEEN SHAPES COULD NOT ANSWER THAT, and the reason is this file's own
    # argument turned on itself: 18 of 18 agreeing is a statement about a list I wrote, not
    # about the shape space. A sweep proves coverage of its POPULATION and nothing else --
    # exactly as 26 of 26 on D06 proved coverage of one document's house style.
    #
    # So these were measured in a probe first (`temp/probe_toc_gaps.py`), then promoted here.
    # FOUR OF THE EIGHT WERE IMPROVEMENTS BRANCH 6 MADE WITHOUT ANYONE MEASURING THEM:
    # re-run against apply at 79a8c14, the commit before branch 6 began, ALL EIGHT declined
    # and none placed. Three now place and one keeps an indent it used to lose.
    # -----------------------------------------------------------------------------------

    ("number and title in ONE run, then tab, then page",
     p(f'<w:hyperlink r:id="rId9"><w:r>{t("9. General provisions")}</w:r>'
       f'<w:r><w:tab/></w:r><w:r>{t("24")}</w:r></w:hyperlink>', ppr=PPR),
     "9. General provisions24", "9. General provisions EN24",
     "DECLINED", "three atoms, and the ONE tab's left side is a TRANSLATED title, so its "
                 "position cannot be proved. Same shape as the unnumbered heading above -- "
                 "and it is a COMMON house style, which the sweep did not say anywhere until "
                 "this row existed"),

    ("LEADING tab before the number (indented sub-entry)",
     p(f'<w:hyperlink r:id="rId9"><w:r><w:tab/></w:r><w:r>{t("9.1")}</w:r>'
       f'<w:r><w:tab/></w:r><w:r>{t("Scope")}</w:r><w:r><w:tab/></w:r>'
       f'<w:r>{t("25")}</w:r></w:hyperlink>', ppr=PPR),
     "9.1Scope25", "9.1Scope EN25",
     "DECLINED", "SIX atoms, not five, so the rule does not reach it -- an indented "
                 "sub-entry on a multi-level contents page is still glued. BUT IT NOW KEEPS "
                 "ITS LEADING TAB, which branch 6 clause 2 preserves and the old code "
                 "destroyed, so the line is indented-but-glued rather than flush-and-glued. "
                 "That is what forced the DECLINED test below to stop meaning "
                 "`atoms == ['text']`"),

    ("page RANGE `4-7`",
     entry("10", "Payment terms", "4-7"),
     "10Payment terms4-7", "10Payment terms EN4-7",
     "DECLINED", "digits + separator + digits. The prefixed alternative is one-or-two "
                 "LETTERS plus separator plus digits, so a range matches neither. DECLINED "
                 "BY DECISION, not by defect: a range translates to itself and would place "
                 "if admitted"),

    ("page number with a trailing full stop `4.`",
     entry("11", "Notices", "4."),
     "11Notices4.", "11Notices EN4.",
     "DECLINED", "not plain digits. Also DECLINED BY DECISION -- a typed contents page can "
                 "carry one. With `Sch-3` and the range above, that is THREE open edges, "
                 "where CLAUDE.md section 7 recorded one until this file measured them"),

    ("roman numeral as the ENTRY number",
     entry("IV.", "Governing law", "26"),
     "IV.Governing law26", "IV.Governing law EN26",
     "PLACED", "the widening was about the PAGE number; an entry number only has to survive "
               "translation, and `IV.` does. Was DECLINED before branch 6"),

    ("single-letter LOWER-case prefix `a-3`",
     entry("12", "Schedule of rates", "a-3"),
     "12Schedule of ratesa-3", "12Schedule of rates ENa-3",
     "PLACED", "one letter plus separator plus digits is inside the widened pattern, and the "
               "sweep had only ever tested the UPPER-case `A-3`. Was DECLINED before branch 6"),

    ("NO page number at all",
     p(f'<w:hyperlink r:id="rId9"><w:r>{t("13")}</w:r><w:r><w:tab/></w:r>'
       f'<w:r>{t("Confidentiality")}</w:r></w:hyperlink>', ppr=PPR),
     "13Confidentiality", "13Confidentiality EN",
     "DECLINED", "three atoms and the tab's RIGHT side is a translated title. Correct to "
                 "decline, and worth having on the record so nobody reads it as a gap"),

    ("the five-atom shape INSIDE A TABLE CELL",
     '<w:tbl><w:tblPr><w:tblW w:w="9000" w:type="dxa"/></w:tblPr><w:tr>'
     '<w:tc><w:tcPr><w:tcW w:w="9000" w:type="dxa"/></w:tcPr>'
     + entry("14", "Dispute resolution", "27") +
     '</w:tc></w:tr></w:tbl>',
     "14Dispute resolution27", "14Dispute resolution EN27",
     "PLACED", "a contents page laid out as a TABLE is a real house style, and apply is "
               "required to recurse into table cells (.claude/rules/ooxml.md). Was DECLINED "
               "before branch 6, so this is a silent improvement now pinned down"),
]

TMP = Path(tempfile.mkdtemp(prefix="toc-variants-"))
src = TMP / "variants.docx"
rels = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/'
        'relationships/styles" Target="styles.xml"/>'
        '<Relationship Id="rId9" Type="http://schemas.openxmlformats.org/officeDocument/2006/'
        'relationships/hyperlink" Target="https://example.invalid/c" TargetMode="External"/>'
        '</Relationships>')
docx(src, "".join(c[1] for c in CASES), {"word/_rels/document.xml.rels": rels})

notes = [{"idx": i, "text": c[2], "en": c[3], "style": "Normal",
          "runs": [{"start": 0, "end": len(c[2]), "text": c[2],
                    "bold": False, "italic": False}]}
         for i, c in enumerate(CASES)]
nj = TMP / "paragraphs.json"
nj.write_bytes(json.dumps(notes, ensure_ascii=False, indent=2).encode("utf-8"))

env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1",
           PYTHONDONTWRITEBYTECODE="1")
out = TMP / "out.xml"
proc = subprocess.run(
    ["uv", "run", "--with", "lxml", "python",
     str(ROOT / "uk" / "scripts" / "apply_translations_textmatch.py"),
     str(src), str(nj), str(out)],
    capture_output=True, text=True, encoding="utf-8", errors="replace",
    cwd=str(ROOT), env=env, timeout=900)

print("=" * 100)
print("WHICH TABLE-OF-CONTENTS SHAPES THE PLACEMENT RULE REACHES — real apply, synthetic shapes")
print("=" * 100)
# ASSERT THE ARTEFACT, NOT THE EXIT CODE.
if not out.is_file():
    print(f"  VOID — apply wrote no output (rc={proc.returncode}).")
    print("  " + (proc.stderr or proc.stdout or "")[-800:])
    shutil.rmtree(TMP, ignore_errors=True)
    sys.exit(1)
ann = [l.strip() for l in (proc.stdout or "").splitlines()
       if "TOC tab placement" in l or "Skipped (same text)" in l]
for l in ann:
    print(f"  apply says: {l}")


def atoms(el):
    o = []
    for n in el.iter():
        tag = etree.QName(n).localname
        if tag in ("t", "delText"):
            if n.text:
                o.append("text")
        elif tag == "tab":
            par = n.getparent()
            if par is None or etree.QName(par).localname != "tabs":
                o.append("tab")
        elif tag == "br":
            o.append("br")
    return o


src_paras = list(etree.fromstring(
    zipfile.ZipFile(src).read("word/document.xml")).iter(f"{{{W}}}p"))
out_paras = list(etree.fromstring(out.read_bytes()).iter(f"{{{W}}}p"))
print()
FAIL = []
# ONE VERDICT PER SHAPE, COMPUTED ONCE. The summary below used to re-derive its own counts with
# a DIFFERENT definition of "declined" (`atoms == ["text"]`), and on 2026-09-02 the two
# definitions disagreed: the indented sub-entry declined while KEEPING a preserved leading tab,
# so the per-row test called it DECLINED and the summary counted it as neither -- 14 + 10 + 1
# against 26 shapes, a number that does not add up and that nothing asserted. Two copies of one
# rule is the defect; one list read twice is the fix.
VERDICTS = []
for i, (label, _x, _tx, _en, should, why) in enumerate(CASES):
    sa, oa = atoms(src_paras[i]), atoms(out_paras[i])
    # A DECLINE MEANS THE ENGLISH COLLAPSED INTO ONE RUN -- it does NOT mean every tab
    # vanished, and this test said `oa == ["text"]` until 2026-09-02.
    #
    # That was too narrow, and the indented sub-entry above is what exposed it: apply
    # DECLINED it and, correctly, PRESERVED its leading tab as a whitelisted structural run,
    # so the atoms came back `['tab', 'text']`. The old three-way test called that BROKEN --
    # a verdict that reads as damage when the truth is a decline plus a repair.
    #
    # The right question is whether any tab still sits BETWEEN two pieces of text, because
    # that is what placement means. One text atom = the English is one unbroken run = the
    # rule declined, whatever structural runs survive around it.
    if oa == sa:
        got = "SKIPPED" if _tx == _en else "PLACED"
    elif oa.count("text") == 1:
        got = "DECLINED"
    else:
        got = "BROKEN"
    VERDICTS.append(got)
    agree = got == should
    print(("  OK   " if agree else "  XX   ")
          + f"{label:<52} {got:<9} (expected {should})")
    print(f"       source atoms {sa}")
    print(f"       applied      {oa}")
    print(f"       {why}")
    if not agree:
        FAIL.append(f"{label}: expected {should}, got {got}")
    print()

print("=" * 100)
placed = VERDICTS.count("PLACED")
declined = VERDICTS.count("DECLINED")
skipped = VERDICTS.count("SKIPPED")
broken = VERDICTS.count("BROKEN")
print(f"  {len(CASES)} shapes · {placed} PLACED · {declined} DECLINED · {skipped} SKIPPED"
      + (f" · {broken} BROKEN" if broken else ""))
# AND THE ARITHMETIC IS ASSERTED, because a summary that does not add up is exactly what hid
# the two-definitions problem: every shape must land in one bucket and no shape in none.
if len(VERDICTS) != len(CASES) or placed + declined + skipped + broken != len(CASES):
    FAIL.append(f"the summary does not account for every shape: {len(VERDICTS)} verdict(s) "
                f"and {placed}+{declined}+{skipped}+{broken} buckets against "
                f"{len(CASES)} shapes")
# THE POSITIVE CONTROL. Every shape here is TOC-shaped or deliberately not, and if NOTHING
# placed then apply matched nothing, the notes did not line up, or the document did not build
# -- all of which would leave every "DECLINED" above reading as a correct fallback.
control = placed > 0 and declined > 0
print(("  OK   " if control else "  XX   ")
      + f"control: at least one shape placed AND at least one declined "
        f"({placed} / {declined}) — if either were 0 the sweep proves nothing")

# ---------------------------------------------------------------------------------------
# AND THE SAME QUESTION ASKED OF THE COMMITTED FIXTURE, WHICH IS THE ONE THAT GETS RENDERED.
#
# `tests/fixtures/toc-widened.docx` exists so the widening can be SEEN on a page -- no corpus
# document carries a roman or prefixed page number, so that render is the only visual evidence
# this change can ever have. A fixture nothing asserts against DRIFTS: the rule changes, the
# fixture still renders, and the picture somebody looked at once quietly stops matching the
# code. This binds the two together, and it is deliberately a DIFFERENT instrument from the
# shapes above -- those are built in memory here, this one is the bytes that are committed.
# ---------------------------------------------------------------------------------------
print()
FX = ROOT / "tests" / "fixtures" / "toc-widened.docx"
FXN = FX.with_suffix(".notes.json")
FXTMP = Path(tempfile.mkdtemp(prefix="toc-widened-"))
fx_out = FXTMP / "out.xml"
if not FX.is_file() or not FXN.is_file():
    FAIL.append(f"{FX.name} or {FXN.name} not built — run tests/make_fixtures.py")
    print(f"  XX   VOID — {FX.name} missing; the rendered fixture is unasserted")
else:
    # COPY THE INPUTS OUT FIRST -- APPLY WRITES INTO ITS NOTES FILE'S DIRECTORY. It invokes
    # `validate_translations.py` as its final pre-apply pass, and that writes
    # `<workdir>/.validate-state.json`, where workdir is wherever the notes file lives. Point
    # apply straight at `tests/fixtures/` and every run drops a state file into the committed
    # fixture directory: the working tree goes dirty on a read-only operation, `git bisect`
    # breaks because `git switch` refuses a dirty tree, and the next `git add -A` commits run
    # state into a PUBLIC repository. Measured here, first run -- it reached the index before
    # `audit_branches` counted 17 fixtures and refused. `render_diff.py` and
    # `test_stop_deleting.py` both copy for exactly this reason; this block did not, and the
    # instrument caught the caller rather than a reader catching it.
    fx_src_copy, fx_notes_copy = FXTMP / FX.name, FXTMP / FXN.name
    shutil.copyfile(FX, fx_src_copy)
    shutil.copyfile(FXN, fx_notes_copy)
    fxp = subprocess.run(
        ["uv", "run", "--with", "lxml", "python",
         str(ROOT / "uk" / "scripts" / "apply_translations_textmatch.py"),
         str(fx_src_copy), str(fx_notes_copy), str(fx_out)],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        cwd=str(ROOT), env=env, timeout=900)
    if not fx_out.is_file():
        FAIL.append(f"apply wrote nothing for {FX.name} (rc={fxp.returncode})")
        print(f"  XX   VOID — apply wrote no output for {FX.name}")
    else:
        fx_src = list(etree.fromstring(
            zipfile.ZipFile(FX).read("word/document.xml")).iter(f"{{{W}}}p"))
        fx_new = list(etree.fromstring(fx_out.read_bytes()).iter(f"{{{W}}}p"))
        # BY INDEX, AND THE INDICES ARE THE POINT. The fixture carries two LABEL paragraphs
        # so the rendered page explains itself: 0 heading, 1 label, 2-6 the five entries that
        # must PLACE, 7 label, 8-9 the two traps that must DECLINE. Written as the shape each
        # must end in, never as a count -- a count of 5 is satisfied by placing the wrong five.
        want = {2: "PLACED", 3: "PLACED", 4: "PLACED", 5: "PLACED", 6: "PLACED",
                8: "DECLINED", 9: "DECLINED"}
        # POSITIVE CONTROL ON THE FIXTURE ITSELF: if it is not the ten-paragraph document
        # those indices describe, every verdict below is read off the wrong paragraph and
        # would still print OK or XX as though it meant something.
        #
        # THE EXPECTED COUNT IS A NAME, NOT A LITERAL IN THE MESSAGE, and that is a repair
        # rather than a style choice. Proving this control could fire meant flipping the
        # comparison to 11 and re-running -- and it failed with "has 10 paragraphs, expected
        # 10", because the message hardcoded the number the comparison no longer used. A
        # failure that reports two equal numbers and fails anyway sends the reader hunting a
        # phantom. Caught by running the negative, never by reading the line.
        WANT_PARAS = 10
        if len(fx_src) != WANT_PARAS:
            FAIL.append(f"toc-widened.docx has {len(fx_src)} paragraphs, expected "
                        f"{WANT_PARAS} — the indices below would read the wrong lines")
        got = []
        for i in sorted(want):
            g = ("PLACED" if atoms(fx_new[i]) == atoms(fx_src[i])
                 else "DECLINED" if atoms(fx_new[i]) == ["text"] else "BROKEN")
            got.append(g)
            if g != want[i]:
                FAIL.append(f"toc-widened.docx entry {i}: expected {want[i]}, got {g}")
        agree = got == ["PLACED"] * 5 + ["DECLINED"] * 2 and len(fx_src) == 10
        print(("  OK   " if agree else "  XX   ")
              + "the RENDERED fixture toc-widened.docx: entries 1-5 place (arabic, roman "
                "lower, roman upper, roman compound, prefixed) and 6-7 decline")
        print(f"       {got}")
        print("       entries 6 and 7 are the traps the widening spends margin against — an "
              "ordinary word\n       in the page-number position, and `civil`, every letter "
              "of which is a roman letter")
shutil.rmtree(FXTMP, ignore_errors=True)
shutil.rmtree(TMP, ignore_errors=True)
if FAIL or not control:
    print()
    if FAIL:
        print(f"  FAIL — {len(FAIL)} expectation(s) missed:")
        for f in FAIL:
            print(f"    · {f}")
        print("  An expectation written down before the run and then missed is the RESULT.")
        print("  Either the rule's reach changed, or the expectation was wrong. Decide which")
        print("  by reading the shape, and NEVER by editing the expectation to match.")
    print("=" * 100)
    sys.exit(1)
print()
print("  PASS — the rule reaches every shape it claims and declines every shape it cannot")
print("  prove. The two it once declined BY DECISION now place; the six that remain declined")
print("  are refused because the boundary is genuinely not provable, or because admitting")
print("  them would admit an ordinary word in the page-number position.")
print("=" * 100)
sys.exit(0)
