# -*- coding: utf-8 -*-
"""G12'S TEXT-FREE ROUTE - each unaccounted `quality_check` finding reported by the SHAPE of its
citation, never a word of its text. Register G12; sub-step 14.10 *(Wouter, 2026-10-26 (3))*.

THE QUESTION. Over the recorded corpus, `quality_check` still makes findings no register row accounts
for: `internal_article_refs` (an `Article N` in a paragraph with no legislation keyword, which the rule
says should read `Clause N`) and one `formatting`. Whether each is a real finding or the rule misreading
a citation cannot be decided from a count, and every finding string embeds 50-70 characters of a real
instrument - which charter section 5.6 says can never be un-said once it is in a transcript. So this
instrument reads the findings and reports only their SHAPE, and the classifying is done on the shape.

HOW A FINDING IS FOUND. Never by parsing the script's printed output. Each paragraph element is handed
to the rule function itself - `check_article_refs(p)` and `check_formatting(p)` iterate `w:p` from the
element they are given, and an element's iteration includes itself - so the attribution is the rule's
own, paragraph by paragraph, and the per-document total is checked against the rule run over the whole
body. Two statements of the same rule that disagree make the run VOID, never a smaller number.

WHAT A SHAPE IS, for an `Article N` finding - each a label, a count or a word from a closed list
written in this file:
  post_process   the skill's OWN discriminator, `_classify_article_ref`, asked about the same match:
                 external (keep Article), internal (rewrite to Clause) or indeterminate (report,
                 change nothing). quality_check keeps the keyword list post_process replaced.
  decider        the token that decided it, read by watching the classifier's two word lists while
                 it runs - so the classifier is asked, never re-implemented: a locator, an anchor, a
                 determiner, or a capitalised word: an instrument word from INSTRUMENT_WORDS below or
                 a private instrument's word from DOCUMENT_WORDS (each printed as itself), a term
                 this document defines in quotes, or another capital
  connector      the tokens between the number and the decider, and `before` the three ahead of
                 `Article`: a word in CONNECTOR_WORDS, INSTRUMENT_WORDS or DOCUMENT_WORDS is printed
                 as itself, any other word as `word` or `Cap`, a number as `num`, a mark by its name
  decider_form   for a capitalised decider, never printed itself: acronym, hyphenated or capitalised;
                 decider_group, which distinct decider of the document it is; in_source, whether it is
                 a word of the SOURCE text, so a name the translation kept; with_keyword, whether it
                 is a word of a paragraph that carries a legislation keyword; keyword_token, whether it
                 is a word of that keyword list; and `after`, the tokens that follow it
  tail           for an indeterminate reference, the tokens up to the sentence's end, the same way
  leg_before     paragraphs back, and leg_after forward, to the nearest one carrying a legislation
                 keyword of the rule's own list - G12's hypothesis, the statute named a paragraph
                 earlier
  own_heading    whether the cited number is one of this document's own `Article N` headings
and for a `formatting` finding: which of the rule's three sub-rules fired, and the run, style and
quote structure of its paragraph - and for a spurious italic, whether the SOURCE paragraph it
translates carries italic too, paired by text through the notes, never by position: `yes` or `no`
with the tier that paired it (exact, or loose - letters and digits only), else `unpaired` and why;
and `declared`, register B1's own question put to post_process's `_declared_italic`: do the
operator's notes account for that italic?

THE OUTPUT GUARD, and it is the reason this file may be run over client documents at all. Every
line is built into a buffer first. Before ONE byte is printed the buffer must pass three tests:
every character ASCII; every word a word of THIS FILE'S OWN SOURCE; every number at most three
digits and never a grouped figure. A word of client text is in no source file here, so it cannot
pass - and nor can a word of a language the source is not written in. On any refusal NOTHING of the
buffer is printed: the run reports VOID and how many tokens were refused, never which. The residual
is stated rather than hidden: a client word that happens also to be a word of this file passes - and
it is then a word already published in this file.

    uv run --with lxml python tools/g12_shapes.py [--variant uk|us]

Exit 0 a report; 1 VOID, nothing measured; 3 VOID, the guard refused the buffer. Logs from
tools/sibling_dirs.py (LT_LOGS_DIR wins). No verbose flag, and none may be added.
"""
import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
from sibling_dirs import logs_dir  # noqa: E402

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
DOC_ID = re.compile(r"\b(D0[1-9]|D1[01])(B?)\b")
# quality_check's own pattern, inline in `check_article_refs` and so copied here; the per-paragraph
# count below is checked against the rule's, so a drift between the two is a VOID, never silent. Since
# 14.11 the number is whole and the rule skips a reference its legislation tail follows - that tail is
# ASKED of quality_check's own import, `qc.ART_LEGISLATION_FOLLOWS`, never copied.
QC_ARTICLE_RE = re.compile(r"\bArticles?\s+\d+(?:\.\d+)*")
# post_process's own pattern, inline in `fix_article_to_clause`, copied for the same reason.
PP_ARTICLE_RE = re.compile(r"\bArticles?\s+\d[\d.:]*(?:-[A-Za-z]{1,15})*")
HEADING_RE = re.compile(r"^\s*(Article|Clause)s?\s+(\d{1,3})\b")
TOKEN_RE = re.compile(r"[A-Za-z]+|\d+|\S")
LDQ, LSQ = chr(0x201C), chr(0x2018)       # built, so this file stays ASCII
# A capitalised word straight after an opening quote anywhere in the document: a term it defines.
QUOTED_WORD_RE = re.compile("[\"" + LDQ + LSQ + "]([A-Za-z][A-Za-z0-9'-]*)")

INSTRUMENT_WORDS = frozenset((
    "Code", "Codes", "Law", "Laws", "Decree", "Decrees", "Regulation", "Regulations", "Directive",
    "Directives", "Act", "Acts", "Treaty", "Constitution", "Convention", "Statute", "Statutes",
    "Ordinance", "Rules", "Procedure", "Civil", "Criminal", "Commercial", "Legislative", "Presidential",
    "Ministerial", "Royal", "Banking", "Consolidated", "Bankruptcy", "Insolvency", "Tax", "Gazette",
    "Italian", "European", "EU", "Republic", "Council", "Commission", "Parliament", "Resolution",
    "Legislation", "Constitutional", "Financial", "Companies", "Company", "Securities",
))
# The words that name a PRIVATE instrument - a contract, the company's own rules. A decider among them
# is the G14 shape: `Article N of the Agreement` read as external only because `the` is not one of
# post_process's internal determiners. Printed as themselves, like the instrument words.
DOCUMENT_WORDS = frozenset((
    "Agreement", "Agreements", "Contract", "Contracts", "Deed", "Deeds", "Guarantee", "Pledge",
    "Mortgage", "Facility", "Loan", "Lease", "Bylaws", "Memorandum", "Charter", "Plan", "Policy",
    "Terms", "Conditions", "Instrument", "Indenture", "Note", "Notes", "Bond", "Bonds", "Warrant",
    "Offer", "Proposal", "Protocol", "Undertaking", "Letter", "Power", "Attorney", "Mandate",
))
CONNECTOR_WORDS = frozenset((
    "of", "the", "and", "or", "to", "et", "seq", "ff", "paragraph", "paragraphs", "letter", "letters",
    "point", "points", "item", "items", "sub", "subparagraph", "comma", "first", "second", "third",
    "fourth", "fifth", "last", "no", "n", "bis", "ter", "quater", "in", "under", "as", "per", "with",
    "by", "a", "an", "its", "said", "same", "above", "below", "hereof", "thereof", "therein",
    "thereto", "thereunder", "which", "that", "this", "present", "provided", "for", "referred",
    "mentioned", "cited", "sentence", "part", "section", "line", "clause", "article", "number",
    "pursuant", "accordance", "set", "out", "laid", "down", "within", "meaning", "sense", "terms",
    "virtue", "subject", "is", "are", "be", "shall", "may", "not", "on", "at", "from", "also",
))
MARKS = {",": "comma", ".": "dot", ";": "semicolon", ":": "colon", "(": "open", ")": "close",
         "-": "dash", '"': "quote", "'": "apostrophe", "/": "slash"}
LONG_DIGITS = re.compile(r"\d{4,}|\d[.,]\d")
NON_ASCII = re.compile(r"[^\x00-\x7f]")
GUARD_WORD = re.compile(r"[A-Za-z]+")


def _own_words():
    return set(GUARD_WORD.findall(Path(__file__).read_text(encoding="utf-8")))


def guard(lines, allowed=None):
    """The tokens of `lines` that may not be printed - an empty list means the buffer may go out.

    Each refusal is returned as a CATEGORY, never as the token, so a caller that prints the list
    prints nothing of what it caught."""
    allowed = _own_words() if allowed is None else allowed
    refused = []
    for line in lines:
        if NON_ASCII.search(line):
            refused.append("non-ascii")
        if LONG_DIGITS.search(line):
            refused.append("figure")
        refused.extend("word" for w in GUARD_WORD.findall(line) if w not in allowed)
    return refused


def shape_tokens(segment, limit=10):
    """A text segment as a closed-vocabulary token list: a listed word as itself, any other word as
    `word` (lower case) or `Cap`, a number as `num`, a mark by its name."""
    out = []
    for tok in TOKEN_RE.findall(segment):
        if tok.isdigit():
            out.append("num")
        elif tok.isalpha():
            if tok.lower() in CONNECTOR_WORDS and tok == tok.lower():
                out.append(tok)
            elif tok in ("Article", "Articles"):
                out.append("Article")
            elif tok in INSTRUMENT_WORDS or tok in DOCUMENT_WORDS:
                out.append(tok)
            else:
                out.append("Cap" if tok[0].isupper() else "word")
        else:
            out.append(MARKS.get(tok, "mark"))
        if len(out) >= limit:
            out.append("more")
            break
    return ",".join(out) or "none"


class _Watch(tuple):
    """A word list that remembers what it was asked - so the classifier's decider is READ from the
    classifier while it runs, never re-derived by a second walk that could disagree with it."""

    def __new__(cls, items):
        obj = super().__new__(cls, items)
        obj.asked = []
        return obj

    def __contains__(self, word):
        self.asked.append(word)
        return tuple.__contains__(self, word)


def classify(pp, text, end):
    """post_process's verdict on the match ending at `end`, and the word that decided it."""
    loc, anc = _Watch(pp._INTERNAL_LOCATORS), _Watch(pp._INTERNAL_ANCHOR_WORDS)
    saved = pp._INTERNAL_LOCATORS, pp._INTERNAL_ANCHOR_WORDS
    pp._INTERNAL_LOCATORS, pp._INTERNAL_ANCHOR_WORDS = loc, anc
    try:
        verdict = pp._classify_article_ref(text, end)
    finally:
        pp._INTERNAL_LOCATORS, pp._INTERNAL_ANCHOR_WORDS = saved
    if verdict == pp.ARTICLE_INDETERMINATE:
        return verdict, None, None
    if loc.asked and loc.asked[-1] in saved[0]:
        return verdict, "locator", loc.asked[-1]
    if anc.asked and anc.asked[-1] in saved[1]:
        return verdict, "anchor", anc.asked[-1]
    if verdict == pp.ARTICLE_INTERNAL:
        return verdict, "determiner", anc.asked[-1] if anc.asked else None
    return verdict, "capital", anc.asked[-1] if anc.asked else None


def sentence_tail(text, end):
    """The text after `end` up to the sentence's end, by post_process's own rule (a full stop ends a
    sentence before a capital or the end of the text, never inside a number or before lower case)."""
    tail = text[end:end + 250]
    i = 0
    while i < len(tail):
        ch = tail[i]
        if ch in "!?\n":
            return tail[:i]
        if ch == ".":
            if i + 1 >= len(tail):
                return tail[:i]
            if tail[i + 1].isdigit():
                i += 1
                continue
            j = i + 1
            while j < len(tail) and tail[j] == " ":
                j += 1
            if j < len(tail) and tail[j].isupper():
                return tail[:i]
        i += 1
    return tail


def _ptext(p):
    return "".join(t.text or "" for t in p.iter(f"{{{W}}}t"))


def _bucket(n, edges=((0, "0"), (1, "1"), (2, "2"), (3, "3"), (9, "4to9"))):
    for top, label in edges:
        if n <= top:
            return label
    return "over9"


def decider_shape(word, tail_after, ctx):
    """What kind of name the capitalised decider is - asked of the document, never printed: its
    form, which distinct decider of this document it is (numbered in order of first appearance), and
    whether it is a word of the SOURCE text (a name the translation kept), a word of a paragraph that
    carries a legislation keyword, or a word of the keyword list itself; and the tokens after it."""
    groups = ctx["groups"]
    groups.setdefault(word, len(groups) + 1)
    form = ("acronym" if len(word) > 1 and word.isupper() else
            "hyphenated" if "-" in word else "capitalised")
    # The word sets hold letter runs, so a hyphenated or possessive decider is asked part by part.
    parts = GUARD_WORD.findall(word)

    def among(words):
        return "yes" if parts and all(p in words for p in parts) else "no"

    return {"decider_form": form,
            "decider_group": str(groups[word]),
            "in_source": among(ctx["source_words"]),
            "with_keyword": among(ctx["leg_words"]),
            "keyword_token": among(ctx["kw_tokens"]),
            "after": shape_tokens(tail_after, limit=4)}


def article_shapes(qc, pp, paras, texts, legal, headings, ctx):
    """One shape line per `Article N` finding, attributed paragraph by paragraph by the rule itself."""
    rows, mismatch = [], 0
    for i, p in enumerate(paras):
        found = len(qc.check_article_refs(p, False))
        if not found:
            continue
        full = texts[i]
        matches = [m for m in QC_ARTICLE_RE.finditer(full)
                   if not qc.ART_LEGISLATION_FOLLOWS.match(full, m.end())] if not legal[i] else []
        if len(matches) != found:
            mismatch += 1
            continue
        for m in matches:
            ppm = PP_ARTICLE_RE.match(full, m.start())
            end = ppm.end() if ppm else m.end()
            verdict, kind, word = classify(pp, full, end)
            shape = {"form": "plural" if m.group().startswith("Articles") else "singular",
                     "post_process": verdict}
            tail = sentence_tail(full, end)
            if verdict == pp.ARTICLE_INDETERMINATE:
                shape["tail"] = shape_tokens(tail)
            else:
                capital = kind == "capital" and word
                if capital:
                    if word in INSTRUMENT_WORDS:
                        kind, shown = "instrument", word
                    elif word in DOCUMENT_WORDS:
                        kind, shown = "document", word
                    elif word in ctx["defined"]:
                        kind, shown = "defined", "term"
                    else:
                        shown = "other"
                    shape["decider"] = f"{kind}:{shown}"
                else:
                    shape["decider"] = kind
                where = re.search(r"\b" + re.escape(word) + r"\b", tail,
                                  0 if kind != "locator" else re.IGNORECASE) if word else None
                shape["connector"] = shape_tokens(tail[:where.start()]) if where else "unread"
                if capital and where:
                    shape.update(decider_shape(word, tail[where.end():], ctx))
            shape["before"] = shape_tokens(" ".join(TOKEN_RE.findall(full[:m.start()])[-3:]))
            back = next((k for k in range(1, 10) if i - k >= 0 and legal[i - k]), None)
            ahead = next((k for k in range(1, 10) if i + k < len(paras) and legal[i + k]), None)
            shape["leg_before"] = _bucket(back) if back else "none"
            shape["leg_after"] = _bucket(ahead) if ahead else "none"
            # The whole number, read from the text (the rule's own match stopped at two digits until 14.11).
            number = re.compile(r"\d+").match(full, m.start() + re.match(r"Articles?\s+", m.group()).end()).group()
            shape["own_heading"] = "yes" if number in headings["Article"] else "no"
            shape["at_start"] = "yes" if not full[:m.start()].strip() else "no"
            shape["words"] = "short" if len(full.split()) <= 8 else "body"
            shape["table"] = "yes" if any(a.tag == f"{{{W}}}tc" for a in p.iterancestors()) else "no"
            rows.append(shape)
    return rows, mismatch


FORMATTING_RULES = (("No bold term in definition", "no_bold_definition"),
                    ("Line break in definition", "line_break_definition"),
                    ("Spurious italic run", "spurious_italic"))


def _norm(s):
    return re.sub(r"\s+", " ", s or "").strip().lower()


def _loose(s):
    """The second pairing tier: letters and digits only, so a space or a mark the tidy-up step moved
    cannot hide the pair. Still text, never position."""
    return re.sub(r"\W+", "", s or "").lower()


def _italic_on(el):
    """Direct italic on a run, or on a paragraph's mark, read with the off-values (OOXML rule)."""
    rpr = el.find(f"{{{W}}}rPr")
    i = rpr.find(f"{{{W}}}i") if rpr is not None else None
    return i is not None and (i.get(f"{{{W}}}val") or "true").strip().lower() not in ("false", "0", "off")


def source_bodies(workdir, delivered, etree):
    """Every container in the workdir whose body DIFFERS from the delivered one - what the run started
    from - parsed, and never named: a corpus filename carries a counterparty's name."""
    import zipfile
    roots, unread = [], 0
    for container in sorted(workdir.glob("*.docx")) + sorted(workdir.glob("*/*.docx")):
        try:
            with zipfile.ZipFile(container) as z:
                raw = z.read("word/document.xml")
            if raw != delivered:
                roots.append(etree.fromstring(raw))
        except Exception:                             # noqa: BLE001 - counted and reported, never named
            unread += 1
    return roots, unread


def source_italic(en_text, entries, bodies):
    """Whether the source paragraph this delivered one translates carries DIRECT italic: yes or no.
    Paired by TEXT through the notes - the entry whose English is this paragraph, then the source
    paragraph holding that entry's text - and never by position (OOXML rule: text-matching, not
    index-matching). `unpaired` where no single source text is found; `no_source` where the workdir
    holds no differing container. Italic from a STYLE is not seen, so `no` does not exclude it."""
    if not bodies:
        return "no_source"
    for tier, key in (("exact", _norm), ("loose", _loose)):
        want = key(en_text)
        sources = {key(e.get("text")) for e in entries
                   if isinstance(e, dict) and key(e.get("en")) == want and key(e.get("text"))}
        if len(sources) == 1:
            break
    else:
        return f"unpaired:notes{_bucket(len(sources))}"
    src = sources.pop()
    hits = [p for root in bodies for p in root.iter(f"{{{W}}}p") if key(_ptext(p)) == src]
    if not hits and key is _norm:                     # the source side gets the loose tier too
        tier, src = "loose", _loose(src)
        hits = [p for root in bodies for p in root.iter(f"{{{W}}}p") if _loose(_ptext(p)) == src]
    if not hits:
        return "unpaired:source0"

    def italic(p):
        ppr = p.find(f"{{{W}}}pPr")
        return (ppr is not None and _italic_on(ppr)) or any(_italic_on(r) for r in p.iter(f"{{{W}}}r"))

    return f"{'yes' if any(italic(p) for p in hits) else 'no'}:{tier}"


def declared_italic(pp, notes, full, runs):
    """B1's own question, asked of post_process: do the operator's notes ACCOUNT for the long italic
    runs of this paragraph? `_declared_italic` answers per run - declared, undeclared (the notes
    cover the run and neither side calls it italic) or uncovered - and `no_note` is a paragraph the
    notes' paragraph-level join does not reach. Asked, never re-implemented."""
    entry = notes.get(pp._notes_norm(full)) if notes else None
    if entry is None:
        return "no_note"
    names = {True: "declared", False: "undeclared", None: "uncovered"}
    verdicts = set()
    for text in flagged_italic_runs(runs):
        verdicts.add(names[pp._declared_italic(entry, text)])
    return ",".join(sorted(verdicts)) or "none"


LATIN_TERMS = ("inter alia", "mutatis mutandis", "pari passu", "pro rata", "bona fide", "de facto", "de jure",
               "prima facie")


def flagged_italic_runs(runs):
    """The run texts quality_check's spurious-italic rule FLAGS in a paragraph it does not exempt - its
    own run conditions, copied from `check_formatting`: italic on, not parenthesised, no listed Latin
    term, not a short numbering label, more than two words. The paragraph-level exemptions (a heading,
    italic set on the paragraph) are the rule's and were passed before a finding exists."""
    out = []
    for r in runs:
        t = r.find(f"{{{W}}}t")
        if not _italic_on(r) or t is None or not t.text or not t.text.strip():
            continue
        text = t.text.strip()
        if (text.startswith("(") and text.endswith(")")) or any(lt in text.lower() for lt in LATIN_TERMS):
            continue
        if len(text) <= 5 and re.match(r"^[\d\.\(\)a-z]+$", text):
            continue
        if len(text.split()) > 2:
            out.append(t.text)
    return out


def formatting_shapes(qc, paras, texts, entries=(), bodies=(), pp=None, notes=None):
    rows, mismatch = [], 0
    for i, p in enumerate(paras):
        issues = qc.check_formatting(p, False, notes)
        for issue in issues:
            rule = next((lab for pre, lab in FORMATTING_RULES if issue.startswith(pre)), None)
            if rule is None:
                mismatch += 1
                continue
            full = texts[i]
            runs = list(p.iter(f"{{{W}}}r"))

            def has(r, tag):
                rpr = r.find(f"{{{W}}}rPr")
                return rpr is not None and rpr.find(f"{{{W}}}{tag}") is not None

            first_q = min([k for k in (full.find('"'), full.find(LDQ)) if k >= 0] or [-1])
            ppr = p.find(f"{{{W}}}pPr")
            shape = {"rule": rule,
                     "trigger": ",".join(v.replace(" ", "_") for v in
                                         ("shall mean", "has the meaning", "means", "indicates")
                                         if v in full) or "none",
                     "by_means_of": "yes" if "by means of" in full else "no",
                     "quote": "curly" if LDQ in full else "straight" if '"' in full else "none",
                     "quote_at": "none" if first_q < 0 else "start" if first_q <= 3 else "mid",
                     "runs": _bucket(len(runs)),
                     "bold_runs": _bucket(sum(1 for r in runs if has(r, "b"))),
                     "styled_runs": _bucket(sum(1 for r in runs if has(r, "rStyle"))),
                     "para_style": "yes" if ppr is not None and ppr.find(f"{{{W}}}pStyle") is not None
                     else "no",
                     "breaks": _bucket(sum(1 for r in runs if r.find(f"{{{W}}}br") is not None)),
                     "words": "short" if len(full.split()) <= 8 else "body",
                     "table": "yes" if any(a.tag == f"{{{W}}}tc" for a in p.iterancestors()) else "no"}
            if rule == "spurious_italic":
                shape["italic_runs"] = _bucket(sum(1 for r in runs if _italic_on(r)))
                shape["flagged_runs"] = _bucket(len(flagged_italic_runs(runs)))
                shape["bold_italic_runs"] = _bucket(sum(1 for r in runs if _italic_on(r) and has(r, "b")))
                shape["source_italic"] = source_italic(full, entries, bodies)
                shape["declared"] = declared_italic(pp, notes, full, runs) if pp else "unread"
            rows.append(shape)
    return rows, mismatch


def main(argv=None):
    ap = argparse.ArgumentParser(description="G12's findings by shape, never by text.")
    ap.add_argument("--variant", choices=("uk", "us"), default="uk")
    args = ap.parse_args(argv)
    scripts = ROOT / args.variant / "scripts"
    sys.path.insert(0, str(scripts))
    try:
        from lxml import etree
        import quality_check as qc
        import post_process as pp
    finally:
        sys.path.remove(str(scripts))

    logs = logs_dir()
    if not logs.is_dir():
        print("VOID - the logs folder is unreachable. Nothing measured, so nothing passed.")
        return 1
    workdirs = [pj.parent / "final" / "word" / "document.xml" for pj in sorted(logs.rglob("paragraphs.json"))]
    workdirs = [dx for dx in workdirs if dx.is_file()]
    if not workdirs:
        print("VOID - no workdir holds a delivered body. Not a clean result.")
        return 1

    out, tally, totals, mismatches = [], Counter(), Counter(), 0
    for dx in workdirs:
        m = DOC_ID.search(str(dx))
        doc = (m.group(1) + m.group(2)) if m else "unattributed"
        root = etree.parse(str(dx)).getroot()
        # the notes as skill Step 9 hands them to the rule, through --with-source (sub-step 14.11)
        notes_by_en = pp.load_declared_notes(str(dx.parents[2] / "paragraphs.json"))
        whole_art = len(qc.check_article_refs(root, False))
        whole_fmt = len(qc.check_formatting(root, False, notes_by_en))
        totals["article"] += whole_art
        totals["formatting"] += whole_fmt
        if not (whole_art or whole_fmt):
            continue
        paras = list(root.iter(f"{{{W}}}p"))
        texts = [_ptext(p) for p in paras]
        legal = [any(kw in t for kw in qc.LEGISLATION_KW) for t in texts]
        headings = {"Article": set(), "Clause": set()}
        for t in texts:
            h = HEADING_RE.match(t)
            if h and len(t.split()) <= 8:            # a heading is short; a sentence opening on it is not
                headings[h.group(1)].add(h.group(2))
        joined = "\n".join(texts)
        notes = json.loads((dx.parents[2] / "paragraphs.json").read_text(encoding="utf-8", errors="replace"))
        entries = notes.get("paragraphs", []) if isinstance(notes, dict) else notes
        ctx = {"defined": {w for w in QUOTED_WORD_RE.findall(joined) if w[:1].isupper()},
               "source_words": {w for e in entries if isinstance(e, dict)
                                for w in GUARD_WORD.findall(e.get("text") or "")},
               "leg_words": {w for t, is_leg in zip(texts, legal) if is_leg for w in GUARD_WORD.findall(t)},
               "kw_tokens": {w for kw in qc.LEGISLATION_KW for w in GUARD_WORD.findall(kw)},
               "groups": {}}
        arts, miss_a = article_shapes(qc, pp, paras, texts, legal, headings, ctx)
        bodies, unread = source_bodies(dx.parents[2], dx.read_bytes(), etree) if whole_fmt else ([], 0)
        if unread:
            out.append(f"  {doc}  containers that could not be read: {_bucket(unread)} - "
                       "source_italic below is measured without them")
        fmts, miss_f = formatting_shapes(qc, paras, texts, entries, bodies, pp, notes_by_en)
        mismatches += miss_a + miss_f
        if len(arts) != whole_art or len(fmts) != whole_fmt:
            mismatches += 1
        out.append(f"  {doc}  headings: Article {_bucket(len(headings['Article']))}, "
                   f"Clause {_bucket(len(headings['Clause']))}")
        for n, shape in enumerate(arts, 1):
            out.append(f"  {doc}  article {n:>2}  " + "  ".join(f"{k}={v}" for k, v in shape.items()))
            tally[("article", shape["post_process"], shape.get("decider", "none"))] += 1
        for n, shape in enumerate(fmts, 1):
            out.append(f"  {doc}  formatting {n:>2}  " + "  ".join(f"{k}={v}" for k, v in shape.items()))
            tally[("formatting", shape["rule"], "none")] += 1

    reported = sum(tally.values())
    out.append("")
    out.append(f"  findings reported by shape: {reported} of {totals['article'] + totals['formatting']}"
               f" the two rules make over {len(workdirs)} workdir(s)")
    for (rule, verdict, decider), n in sorted(tally.items()):
        out.append(f"    {n:>3}  {rule}  {verdict}  {decider}")
    if mismatches:
        out.append(f"  VOID - the rule and this instrument disagreed {mismatches} time(s); "
                   "fix the instrument rather than reading the rest.")

    refused = guard(out)
    if refused:
        print(f"VOID - the output guard refused {len(refused)} token(s) "
              f"({', '.join(f'{n} {k}' for k, n in sorted(Counter(refused).items()))}); nothing printed.")
        return 3
    sys.stdout.write("\n".join(out) + "\n")
    return 1 if mismatches else 0


def guarded_main(argv=None):
    """main(), with every exception reduced to its TYPE. A traceback is printed past the guard, and an
    lxml or file error's message carries a corpus path - so none is ever printed."""
    try:
        return main(argv)
    except Exception as exc:                          # noqa: BLE001 - the message is the hazard
        print(f"VOID - the run stopped on {type(exc).__name__}; its message is withheld, being unguarded.")
        return 1


if __name__ == "__main__":
    sys.exit(guarded_main())
