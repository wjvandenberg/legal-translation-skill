# -*- coding: utf-8 -*-
"""G12'S TEXT-FREE INSTRUMENT, PROVED ON SYNTHETIC DOCUMENTS ONLY - sub-step 14.10.

`tools/g12_shapes.py` is run over client documents, and what it prints reaches a transcript no scanner
can reach afterwards. So before it is trusted on one, it is run here over invented documents built in a
temporary folder, and three things are asserted:

  1  A PLANTED SHAPE IT MUST REPORT. Each citation shape the classification depends on - an external
     statute by an instrument word, an undecided `thereof` with a statute a paragraph earlier, a
     defined term after a comma, an internal locator, a document's own heading, a source acronym the
     translation kept, G14's `of the Agreement`, the formatting rule's missing bold, and three spurious
     italics (declared and paired with an italic source; with no note; called plain by its note) - is
     planted once and its shape line asserted label by label; a paragraph that carries a legislation
     keyword is planted beside them and must NOT be reported.
  2  A PLANTED STRING IT MUST NEVER PRINT. Every invented name in those paragraphs - two Latin and one
     non-Latin - is searched for in everything the tool printed. And the guard is made to fire for real:
     the tool is run in-process with one invented name ADDED to its instrument list, so it tries to print
     it; it must refuse the whole buffer, exit 3, and print neither the name nor any shape line. And the
     instrument's copy of the rule is made to disagree with the rule: VOID, exit 1, never a smaller count.
  3  THE GUARD AND THE VOIDS. The guard refuses a foreign word, a non-ASCII character and a grouped
     figure, and reports categories, never the token; a missing or an empty logs folder is VOID, exit 1.

The mutants of every deciding line are temp/s1111_mutants.py's (gitignored), 15 of them.

Run as a top-level command - never from a parent runner (verification rule 1):

    uv run --with lxml python tests/test_g12_shapes.py
"""
import io
import json
import os
import re
import subprocess
import sys
import tempfile
import zipfile
from contextlib import redirect_stdout
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parent.parent
TOOL = ROOT / "tools" / "g12_shapes.py"
FAIL, CHECKED = [], 0
NEEDLES = ("Zanzibarcode", "Quillfeather", "Łódźquill", "ZQXT", "Vermiglione")
# the third is non-Latin by design; the fifth is in the SOURCE text only, which the tool also reads

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


def ok(label, cond):
    global CHECKED
    CHECKED += 1
    print(f"  {'OK  ' if cond else 'XX  '} {label}")
    if not cond:
        FAIL.append(label)


def para(text, bold=False, italic=False, style=None):
    ppr = f'<w:pPr><w:pStyle w:val="{style}"/></w:pPr>' if style else ""
    rpr = "<w:rPr>" + ("<w:b/>" if bold else "") + ("<w:i/>" if italic else "") + "</w:rPr>"
    safe = text.replace("&", "&amp;").replace("<", "&lt;")
    return f'<w:p>{ppr}<w:r>{rpr}<w:t xml:space="preserve">{safe}</w:t></w:r></w:p>'


def body_xml(paragraphs):
    return (f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            f'<w:document xmlns:w="{W}"><w:body>{"".join(paragraphs)}</w:body></w:document>')


def write_doc(folder, paragraphs, notes=(), source=None):
    """A recorded workdir: the delivered body, the notes, and - when `source` is given - a container
    holding the body the run started from, written once and never moved."""
    word = folder / "final" / "word"
    word.mkdir(parents=True)
    (word / "document.xml").write_text(body_xml(paragraphs), encoding="utf-8")
    (folder / "paragraphs.json").write_text(json.dumps(list(notes)), encoding="utf-8")
    if source is not None:
        with zipfile.ZipFile(folder / "source.docx", "w") as z:
            z.writestr("word/document.xml", body_xml(source))


ARTICLE_DOC = [
    para("Article 2 Definitions"),                                               # own heading, a finding
    para('In this deed (the "Quillfeather") the parties agree as follows.'),
    para("The Legislative Decree applies to the transfer."),                    # a keyword: not a finding
    para("The Quillfeather relies on Article 5 thereof."),                      # indeterminate, statute 1 back
    para("Payment is made pursuant to Article 7 of the Civil Procedure Rules."),  # external, instrument
    para("Under Article 3, the Quillfeather shall pay the Łódźquill fee."),  # defined term
    para("As provided in Article 2 above, the term is fixed."),                 # internal, locator
    para("Fees are fixed under Article 6 of the ZQXT Rules."),                  # a kept source acronym
    para("The fee is due under Article 8 of the Agreement."),                   # G14's shape: a document word
    para("Article 9 of the Civil Code governs the Zanzibarcode."),              # keyword in paragraph: quiet
]
ARTICLE_NOTES = [{"idx": 0, "text": "Le tariffe ZQXT del Vermiglione sono fisse.", "en": "unused"}]
ITALIC_PAIRED = "Quillfeather shall remain wholly bound"
ITALIC_PLAIN = "Quillfeather terms stay plain here"
EXEMPT_A, EXEMPT_B = "Zanzibarcode sits wholly apart now", "(Quillfeather Exempt Title Here)"
FORMAT_DOC = [para('"Zanzibarcode" means the Quillfeather plan of the parties.'),  # no bold on the term
              para(ITALIC_PAIRED, italic=True),                                # italic, the source's too
              para("Zanzibarcode remains wholly unpaired here", italic=True),    # italic, no note at all
              para(ITALIC_PLAIN, italic=True),                                 # italic the note calls plain
              '<w:p><w:r><w:rPr><w:i/></w:rPr><w:t>' + EXEMPT_A + '</w:t></w:r>'  # one flagged run, plain by
              '<w:r><w:rPr><w:i/></w:rPr><w:t>' + EXEMPT_B + '</w:t></w:r></w:p>']  # note; one exempt, declared
FORMAT_NOTES = [{"idx": 1, "text": "Vermiglione resta del tutto vincolato", "en": ITALIC_PAIRED,
                 "en_runs": [{"start": 0, "end": len(ITALIC_PAIRED), "italic": True}]},
                {"idx": 3, "text": "Vermiglione senza corsivo", "en": ITALIC_PLAIN,
                 "en_runs": [{"start": 0, "end": len(ITALIC_PLAIN), "italic": False}]},
                {"idx": 4, "text": "Vermiglione a parte", "en": EXEMPT_A + EXEMPT_B,
                 "en_runs": [{"start": 0, "end": len(EXEMPT_A), "italic": False},
                             {"start": len(EXEMPT_A), "end": len(EXEMPT_A + EXEMPT_B), "italic": True}]}]
FORMAT_SOURCE = [para("Vermiglione resta del tutto vincolato", italic=True)]


def run(env_logs):
    env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONDONTWRITEBYTECODE="1", LT_LOGS_DIR=str(env_logs))
    r = subprocess.run(["uv", "run", "--with", "lxml", "python", str(TOOL)], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", env=env, cwd=str(ROOT), timeout=300)
    return r.returncode, r.stdout + r.stderr


def line_for(out, doc, rule, n):
    want = f"  {doc}  {rule} {n:>2}  "
    return next((ln for ln in out.splitlines() if ln.startswith(want)), "")


def has_all(line, *labels):
    """Each label a WHOLE field: fields are two-space separated, so `after=Rules` never passes for
    `after=Rules,more`."""
    return bool(line) and all(f"  {lab}  " in f"  {line}  " for lab in labels)


with tempfile.TemporaryDirectory() as tmp:
    logs = Path(tmp) / "logs"
    write_doc(logs / "run-D05", ARTICLE_DOC, ARTICLE_NOTES)
    write_doc(logs / "run-D03", FORMAT_DOC, FORMAT_NOTES, FORMAT_SOURCE)
    rc, out = run(logs)

    print("1  A PLANTED SHAPE IT MUST REPORT")
    ok("the run exits 0", rc == 0)
    ok("the headings line counts the one Article heading, not the sentence opening on `Article 9`",
       "  D05  headings: Article 1, Clause 0" in out)
    ok("the heading itself: external by the capital after it, at the start, short, its own number",
       has_all(line_for(out, "D05", "article", 1), "form=singular", "post_process=external",
               "decider=capital:other", "at_start=yes", "words=short", "own_heading=yes"))
    ok("`thereof`: undecided, its tail read, the statute one paragraph back",
       has_all(line_for(out, "D05", "article", 2), "post_process=indeterminate", "tail=thereof",
               "leg_before=1", "own_heading=no"))
    ok("an instrument word after `of the`: external, decided by the listed word, connector of,the",
       has_all(line_for(out, "D05", "article", 3), "post_process=external", "decider=instrument:Civil",
               "connector=of,the", "before=word,pursuant,to", "decider_group=2", "keyword_token=yes",
               "with_keyword=yes", "in_source=no", "after=Procedure,Rules"))
    ok("a defined term after a comma: external by post_process, decided by the document's own term",
       has_all(line_for(out, "D05", "article", 4), "post_process=external", "decider=defined:term",
               "connector=comma,the", "before=Cap"))
    ok("a locator: internal, decided by the locator, nothing between",
       has_all(line_for(out, "D05", "article", 5), "post_process=internal", "decider=locator",
               "connector=none"))
    ok("a kept source acronym: its form, a fourth distinct decider, a word of the source, Cap after",
       has_all(line_for(out, "D05", "article", 6), "post_process=external", "decider=capital:other",
               "decider_form=acronym", "decider_group=4", "in_source=yes", "with_keyword=no",
               "keyword_token=no", "after=Rules"))
    ok("`of the Agreement`: external by post_process, and the document word shown as itself",
       has_all(line_for(out, "D05", "article", 7), "post_process=external", "decider=document:Agreement",
               "connector=of,the", "decider_group=5", "after=none"))
    ok("a paragraph carrying a legislation keyword is not reported - seven findings, not eight",
       not line_for(out, "D05", "article", 8))
    ok("the formatting finding: the missing bold, its trigger, a straight quote at the start",
       has_all(line_for(out, "D03", "formatting", 1), "rule=no_bold_definition", "trigger=means",
               "quote=straight", "quote_at=start", "bold_runs=0", "by_means_of=no"))
    ok("a spurious italic whose source paragraph, paired by text, is italic too",
       has_all(line_for(out, "D03", "formatting", 2), "rule=spurious_italic", "italic_runs=1",
               "bold_italic_runs=0", "source_italic=yes:exact", "declared=declared"))
    ok("a spurious italic with no note to pair it: unpaired, and why, never guessed",
       has_all(line_for(out, "D03", "formatting", 3), "rule=spurious_italic", "source_italic=unpaired:notes0",
               "declared=no_note"))
    ok("a spurious italic its note calls plain: undeclared, and its source text absent",
       has_all(line_for(out, "D03", "formatting", 4), "rule=spurious_italic", "source_italic=unpaired:source0",
               "declared=undeclared"))
    ok("an exempt parenthesised run beside a flagged one: only the flagged run's verdict, as the rule reads",
       has_all(line_for(out, "D03", "formatting", 5), "rule=spurious_italic", "italic_runs=2",
               "flagged_runs=1", "declared=undeclared"))
    ok("the denominator: 12 of the 12 the two rules make, over 2 workdirs",
       "findings reported by shape: 12 of 12 the two rules make over 2 workdir(s)" in out)
    ok("the tally names each class", "    1  article  external  instrument:Civil" in out
       and "    1  formatting  no_bold_definition  none" in out
       and "    4  formatting  spurious_italic  none" in out)

    print("2  A PLANTED STRING IT MUST NEVER PRINT")
    for needle in NEEDLES:
        ok(f"invented name {NEEDLES.index(needle) + 1} of {len(NEEDLES)} is nowhere in the output",
           needle not in out and needle.lower() not in out.lower())
    ok("the output is ASCII throughout", all(ord(c) < 128 for c in out))

    sys.path.insert(0, str(ROOT / "tools"))
    import g12_shapes as G
    saved_env = os.environ.get("LT_LOGS_DIR")
    os.environ["LT_LOGS_DIR"] = str(logs)
    saved_words = G.INSTRUMENT_WORDS
    G.INSTRUMENT_WORDS = frozenset(saved_words | {"Quillfeather"})   # the tool now TRIES to print it
    buf = io.StringIO()
    try:
        with redirect_stdout(buf):
            forced = G.main([])
    finally:
        G.INSTRUMENT_WORDS = saved_words
        if saved_env is None:
            os.environ.pop("LT_LOGS_DIR", None)
        else:
            os.environ["LT_LOGS_DIR"] = saved_env
    got = buf.getvalue()
    ok("forced to print an invented name, the guard refuses: exit 3", forced == 3)
    ok("and it prints VOID, the refusal counted by category",
       re.match(r"VOID - the output guard refused \d+ token\(s\) \(\d+ word\); nothing printed\.\n?$", got)
       is not None)
    ok("and neither the name nor any shape line", "Quillfeather" not in got and "post_process=" not in got)

    os.environ["LT_LOGS_DIR"] = str(logs)
    saved_re = G.QC_ARTICLE_RE
    G.QC_ARTICLE_RE = re.compile("(?!)")             # the instrument's copy of the rule now finds nothing
    buf = io.StringIO()
    try:
        with redirect_stdout(buf):
            disagreed = G.main([])
    finally:
        G.QC_ARTICLE_RE = saved_re
        if saved_env is None:
            os.environ.pop("LT_LOGS_DIR", None)
        else:
            os.environ["LT_LOGS_DIR"] = saved_env
    ok("the instrument's copy of the rule disagreeing with the rule is VOID, exit 1, never a smaller count",
       disagreed == 1 and "VOID - the rule and this instrument disagreed" in buf.getvalue())

    print("3  THE GUARD AND THE VOIDS")
    ok("a clean line passes", G.guard(["  D05  article  1  form=singular  post_process=external"]) == [])
    ok("a foreign word is refused, as a category", G.guard(["decider=Zanzibarcode"]) == ["word"])
    ok("a non-ASCII character is refused", "non-ascii" in G.guard(["tail=“thereof"]))
    ok("a grouped figure is refused", "figure" in G.guard(["n=1.500"]))
    ok("a long figure is refused", "figure" in G.guard(["n=2026"]))
    ok("three digits pass", G.guard(["n=999"]) == [])
    rc_missing, out_missing = run(Path(tmp) / "no-such-folder")
    ok("a missing logs folder is VOID, exit 1", rc_missing == 1 and out_missing.startswith("VOID"))
    empty = Path(tmp) / "empty"
    empty.mkdir()
    rc_empty, out_empty = run(empty)
    ok("an empty logs folder is VOID, exit 1", rc_empty == 1 and out_empty.startswith("VOID"))
    broken = Path(tmp) / "broken" / "run-D07-Zanzibarcode"
    write_doc(broken, [para("Article 4 of the Quillfeather Decree applies.")])
    (broken / "final" / "word" / "document.xml").write_text("<w:document><w:body>", encoding="utf-8")
    rc_broken, out_broken = run(Path(tmp) / "broken")
    ok("a body that will not parse is VOID, exit 1, the error named by its type alone",
       rc_broken == 1 and out_broken.startswith("VOID - the run stopped on XMLSyntaxError"))
    ok("and the error's message - which names the file's path - is withheld",
       "Zanzibarcode" not in out_broken and "Traceback" not in out_broken and "document.xml" not in out_broken)

print(f"\nRESULT: {CHECKED - len(FAIL)} of {CHECKED} checks passed")
sys.exit(1 if FAIL else 0)
