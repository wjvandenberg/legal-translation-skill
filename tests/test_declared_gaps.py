# -*- coding: utf-8 -*-
"""SUB-STEP 12.2 — the gaps the declared language exposes.

WHAT THE ROWS SAY. S3: translate_numbering reported the absence of DICTIONARY MATCHES as the absence of
CONTENT — on a Norwegian document it guessed french, then said there were no translatable format strings
while ten sat in numbering the document uses. E4: no numbering map for Chinese or Japanese, exit 0 with
"Writing unchanged". C2: no remnant marker list carries a month name, so a surviving source-language date
scans CLEAN. S1 and H1: translate_numbering's guess is the one 12a left. And the end-of-run diligence audit
never asks whether skill Step 1c was done (Wouter, 2026-10-09).

WOUTER'S CHOICES (2026-10-12, section 3.2 of PLAN-2-step-b.md):
  N  translate_numbering reads the skill Step 1c declaration through the one policy; a language with no map says
     NOT SUPPORTED and applies none; every format string still carrying a word is listed NOT TRANSLATED;
     it STOPS (exit 1) only on a DECLARED or explicit supported language with such a string in numbering
     the document uses — --custom the way out, mapping a string to itself to keep it. Chinese and Japanese
     maps, each entry citing its lexicon row; the keyword-before-number order for every keyword the nine
     maps hold. The guess itself is unchanged.
  M  a month name BESIDE A NUMBER is a blocking remnant; a BARE one only warns — in repack's block and in
     quality_check alike; English-identical month words are no marker; four French statute names the
     lexicons keep are declared kept names.
  H  translate_headers_footers' legacy mode: no guess, NOT SUPPORTED for a language it has no list for,
     and it counts the text it left instead of claiming "all numeric/symbol content".
  D  verify_diligence has a skill Step 1c row: supported PASS, declared-unsupported WARN, missing or unreadable
     FAIL.

RED FIRST: run before 12b's code exists, every arm must fail.

    uv run --with lxml python tests/test_declared_gaps.py
    uv run --with lxml python tests/test_declared_gaps.py --variant us

Synthetic text only. No client text.
"""
import argparse
import importlib.util
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.dont_write_bytecode = True
os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")

sys.path.insert(0, str(Path(__file__).resolve().parent))
from make_fixtures import W, docx, p, r  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
ap = argparse.ArgumentParser()
ap.add_argument("--variant", default="uk", choices=("uk", "us"))
ap.add_argument("--keep", action="store_true")
ap.add_argument("--scripts", default=None,
                help="another scripts folder (the red-first proof against HEAD's); lexicons stay the tree's")
args = ap.parse_args()
TREE = ROOT / args.variant
SCRIPTS = Path(args.scripts).resolve() if args.scripts else TREE / "scripts"
TMP = Path(tempfile.mkdtemp(prefix="b12b-test-"))
ENV = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1", PYTHONDONTWRITEBYTECODE="1")
PY = ["uv", "run", "--with", "lxml", "python"]
FAIL, CHECKED = [], 0
WNS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


def ok(label, cond, detail=""):
    global CHECKED
    CHECKED += 1
    print(("  OK   " if cond else "  XX   ") + label + (f"   ({detail})" if detail and not cond else ""))
    if not cond:
        FAIL.append(label)
    return cond


def run(script, *argv, timeout=600):
    return subprocess.run(PY + [str(SCRIPTS / script)] + [str(a) for a in argv], capture_output=True,
                          text=True, encoding="utf-8", errors="replace", cwd=str(ROOT), env=ENV,
                          timeout=timeout)


def load(name):
    """The tree's own module, imported in-process with its prints swallowed."""
    if str(SCRIPTS) not in sys.path:
        sys.path.insert(0, str(SCRIPTS))
    spec = importlib.util.spec_from_file_location(f"b12b_{args.variant}_{name}", SCRIPTS / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    saved = sys.stdout
    sys.stdout = io.StringIO()
    try:
        spec.loader.exec_module(mod)
    finally:
        sys.stdout = saved
    return mod


def declare(wd, language):
    (wd / "source_language.json").write_bytes(json.dumps({"source_language": language}).encode("utf-8") + b"\n")


# =========================================================================================
# ARM N — translate_numbering
# =========================================================================================
print(f"\nARM N — translate_numbering reads the declaration and says what it left   [{args.variant}]")


def numbering_xml(used, unused=()):
    """abstractNum 0 is used by numId 1, which the body's paragraph cites; abstractNum 1 is not."""
    def lvls(vals):
        return "".join(f'<w:lvl w:ilvl="{i}"><w:lvlText w:val="{v}"/></w:lvl>' for i, v in enumerate(vals))
    return (f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
            f'<w:numbering {W}><w:abstractNum w:abstractNumId="0">{lvls(used)}</w:abstractNum>'
            f'<w:abstractNum w:abstractNumId="1">{lvls(unused or ["%1."])}</w:abstractNum>'
            f'<w:num w:numId="1"><w:abstractNumId w:val="0"/></w:num>'
            f'<w:num w:numId="2"><w:abstractNumId w:val="1"/></w:num></w:numbering>')


def tn_case(name, used, unused=(), *, lang=None, explicit=None, custom=None):
    wd = TMP / f"n-{name}"
    (wd / "final" / "word").mkdir(parents=True)
    src = wd / "source.docx"
    body = p(r("Body text."), ppr='<w:pPr><w:numPr><w:ilvl w:val="0"/><w:numId w:val="1"/></w:numPr></w:pPr>')
    docx(src, body, extra_parts={"word/numbering.xml": numbering_xml(used, unused)})
    (wd / "paragraphs.json").write_bytes(b"[]")
    if lang:
        declare(wd, lang)
    out = wd / "final" / "word" / "numbering.xml"
    argv = [src, out]
    if explicit:
        argv += ["--language", explicit]
    if custom is not None:
        cj = wd / "custom.json"
        cj.write_bytes(json.dumps(custom, ensure_ascii=False).encode("utf-8"))
        argv += ["--custom", cj]
    res = run("translate_numbering.py", *argv)
    vals = re.findall(r'w:lvlText w:val="([^"]*)"', out.read_text(encoding="utf-8")) if out.is_file() else []
    return res, vals


PURE = "pure numeric/symbol"

res, vals = tn_case("it-all", ["%1. Allegato", "Parte %1", "o", "%1."], ["Capitolo %1"], lang="italian")
ok("N1 declared italian: a keyword AFTER the number still translates", "Schedule %1" in vals, f"{vals}")
ok("N1 a keyword BEFORE the number now translates (Parte %1 -> Part %1)", "Part %1" in vals, f"{vals}")
ok("N1 ... in an unused numbering too (Capitolo %1 -> Chapter %1)", "Chapter %1" in vals, f"{vals}")
ok("N1 a one-letter bullet and a pure pattern are untouched", "o" in vals and "%1." in vals, f"{vals}")
ok("N1 nothing left, so it exits 0 and lists nothing NOT TRANSLATED",
   res.returncode == 0 and "NOT TRANSLATED" not in res.stdout, f"rc={res.returncode} {res.stdout[-300:]}")

res, vals = tn_case("it-left-used", ["Premessa %1", "Parte %1"], lang="italian")
ok("N2 declared italian, a word no map holds in a USED numbering: it STOPS (exit 1)",
   res.returncode == 1, f"rc={res.returncode} {res.stdout[-300:]}")
ok("N2 ... saying NOT TRANSLATED, the string marked in use", "NOT TRANSLATED" in res.stdout
   and "Premessa %1" in res.stdout and "in use" in res.stdout, res.stdout[-400:])
ok("N2 ... naming the --custom way out", "--custom" in res.stdout, res.stdout[-400:])
ok("N2 ... never claiming the strings are pure numeric/symbol", PURE not in res.stdout, res.stdout[-300:])
ok("N2 ... and the file is still written with every other translation", "Part %1" in vals, f"{vals}")

res, vals = tn_case("it-custom", ["Premessa %1"], lang="italian", custom={"Premessa %1": "Recital %1"})
ok("N3 --custom translates the string and the run exits 0",
   res.returncode == 0 and "Recital %1" in vals, f"rc={res.returncode} {vals} {res.stdout[-200:]}")

res, vals = tn_case("it-keep", ["Premessa %1"], lang="italian", custom={"Premessa %1": "Premessa %1"})
ok("N4 --custom mapping a string to ITSELF declares it kept: exit 0, not listed NOT TRANSLATED",
   res.returncode == 0 and "NOT TRANSLATED" not in res.stdout and "Premessa %1" in vals,
   f"rc={res.returncode} {res.stdout[-300:]}")

res, vals = tn_case("it-left-unused", ["%1."], ["Premessa %1"], lang="italian")
ok("N5 a word left only in an UNUSED numbering: listed, marked not in use, exit 0",
   res.returncode == 0 and "NOT TRANSLATED" in res.stdout and "not in use" in res.stdout,
   f"rc={res.returncode} {res.stdout[-300:]}")

res, vals = tn_case("no", ["Artikkel %1", "Vedlegg %1"], lang="norwegian")
ok("N6 declared norwegian: NOT SUPPORTED naming it, and nothing guessed (no french)",
   "NOT SUPPORTED" in res.stdout and "norwegian" in res.stdout and "guess" not in res.stdout
   and "Auto-detected" not in res.stdout, res.stdout[-400:])
ok("N6 ... both strings listed NOT TRANSLATED, never pure numeric/symbol",
   "NOT TRANSLATED" in res.stdout and "Artikkel %1" in res.stdout and PURE not in res.stdout, res.stdout[-400:])
ok("N6 ... and no stop: it cannot tell a source word from an English one (exit 0)", res.returncode == 0,
   f"rc={res.returncode}")

res, vals = tn_case("it-guess", ["%1. Allegato", "Premessa %1"])
ok("N7 nothing declared: the guess is acted on as before (Allegato translated)",
   "Schedule %1" in vals, f"{vals}")
ok("N7 ... but it says NOT SUPPORTED — it ran on a guess", "NOT SUPPORTED" in res.stdout, res.stdout[-300:])
ok("N7 ... and a guess never stops the run (exit 0) though a used word is left",
   res.returncode == 0 and "NOT TRANSLATED" in res.stdout, f"rc={res.returncode} {res.stdout[-300:]}")

res, vals = tn_case("en", ["Article %1", "Annex %1", "Definitions %1"], lang="english")
ok("N8 declared english (already the target): NOT SUPPORTED, no map applied, exit 0",
   "NOT SUPPORTED" in res.stdout and res.returncode == 0 and "Annex %1" in vals,
   f"rc={res.returncode} {vals} {res.stdout[-300:]}")

JA = {"第%1条": "Article %1", "第%1章": "Chapter %1", "第%1節": "Section %1", "第%1項": "Paragraph %1",
      "第%1号": "Item %1", "別紙%1": "Schedule %1", "別表%1": "Appended Table %1"}
res, vals = tn_case("ja", list(JA), lang="japanese")
ok("N9 declared japanese: every Japanese format string translated (E4)",
   all(v in vals for v in JA.values()), f"{vals}")
ok("N9 ... and it exits 0 with nothing left", res.returncode == 0 and "NOT TRANSLATED" not in res.stdout,
   f"rc={res.returncode} {res.stdout[-300:]}")
ZH = {"第%1条": "Article %1", "第%1章": "Chapter %1", "第%1款": "Paragraph %1", "第%1项": "Item %1"}
res, vals = tn_case("zh", list(ZH), lang="chinese")
ok("N10 declared chinese: every Chinese format string translated (E4)",
   all(v in vals for v in ZH.values()), f"{vals}")
res, vals = tn_case("zh-left", ["附件%1"], lang="chinese")
ok("N10 ... a Chinese label no lexicon row sanctions is LISTED and stops, never 'Writing unchanged'",
   res.returncode == 1 and "NOT TRANSLATED" in res.stdout and "Writing unchanged" not in res.stdout,
   f"rc={res.returncode} {res.stdout[-300:]}")

res, vals = tn_case("it-explicit", ["Premessa %1"], explicit="italian")
ok("N11 an explicit --language italian is settled too: it stops on a used word left",
   res.returncode == 1, f"rc={res.returncode} {res.stdout[-200:]}")

# The code review's findings, 2026-10-12: escaping, a literal --custom key, an unreadable numbering part.
res, vals = tn_case("it-escape", ["Premessa %1", "Termini &amp; Condizioni %1"], lang="italian",
                    custom={"Premessa %1": 'Recital "A" & B %1', "Termini & Condizioni %1": "Terms & Conditions %1"})
out_xml = TMP / "n-it-escape" / "final" / "word" / "numbering.xml"
try:
    import xml.etree.ElementTree as _ET
    parsed = [lt.get(f"{{{WNS}}}val") for lt in _ET.parse(out_xml).iter(f"{{{WNS}}}lvlText")]
except Exception as exc:  # noqa: BLE001 -- a file Word would reject is the result
    parsed = [f"<{type(exc).__name__}>"]
ok("N14 a --custom rendering holding & and \" is written ESCAPED: the part still parses, the text is as written",
   res.returncode == 0 and 'Recital "A" & B %1' in parsed, f"rc={res.returncode} {parsed}")
ok("N14 ... and a source string Word stores escaped matches the --custom key the operator copied from the list",
   "Terms & Conditions %1" in parsed, f"{parsed}")

res, vals = tn_case("it-literal", ["Premessa (A %1", "Parte %1"], lang="italian",
                    custom={"Premessa (A %1": "Recital (A %1"})
ok("N15 a literal --custom key with an unbalanced bracket ends nothing: exit 0, no traceback, both translated",
   res.returncode == 0 and "Traceback" not in res.stderr and "Recital (A %1" in vals and "Part %1" in vals,
   f"rc={res.returncode} {vals} {res.stderr[-200:]}")

wd_bad = TMP / "n-unreadable"
(wd_bad / "final" / "word").mkdir(parents=True)
src_bad = wd_bad / "source.docx"
bad_numbering = numbering_xml(["Premessa %1"]).replace('w:abstractNumId="1">', 'w:abstractNumId="1" w:x="&nbsp;">')
docx(src_bad, p(r("Body."), ppr='<w:pPr><w:numPr><w:ilvl w:val="0"/><w:numId w:val="1"/></w:numPr></w:pPr>'),
     extra_parts={"word/numbering.xml": bad_numbering})
(wd_bad / "paragraphs.json").write_bytes(b"[]")
declare(wd_bad, "italian")
res = run("translate_numbering.py", src_bad, wd_bad / "final" / "word" / "numbering.xml")
ok("N16 a numbering part ElementTree cannot read: no traceback, every string treated as in use, and it stops",
   res.returncode == 1 and "Traceback" not in res.stderr and "could not be read as XML" in res.stdout,
   f"rc={res.returncode} {res.stdout[-200:]} {res.stderr[-200:]}")

# The text-mode write (the code review of 2026-10-12, built after 12b at Wouter's word): the part goes back with
# exactly the line breaks it came in with. Word writes CRLF after the declaration; text mode on Windows made it CR CR LF.
for name, used, want_same in (("nl-untouched", ["%1.", "o"], True), ("nl-translated", ["Parte %1", "%1."], False)):
    wd_n = TMP / f"n-{name}"
    (wd_n / "final" / "word").mkdir(parents=True)
    src_n = wd_n / "source.docx"
    part = numbering_xml(used).replace("standalone=\"yes\"?>\n", "standalone=\"yes\"?>\r\n")
    docx(src_n, p(r("Body."), ppr='<w:pPr><w:numPr><w:ilvl w:val="0"/><w:numId w:val="1"/></w:numPr></w:pPr>'),
         extra_parts={"word/numbering.xml": part})
    (wd_n / "paragraphs.json").write_bytes(b"[]")
    declare(wd_n, "italian")
    run("translate_numbering.py", src_n, wd_n / "final" / "word" / "numbering.xml")
    with zipfile.ZipFile(src_n) as z:
        orig_b = z.read("word/numbering.xml")
    got_b = (wd_n / "final" / "word" / "numbering.xml").read_bytes()
    if want_same:
        ok("N17 an untouched numbering part is written back BYTE-IDENTICAL, its CRLF kept", got_b == orig_b,
           f"crlf {orig_b.count(b'\r\n')}->{got_b.count(b'\r\n')}, cr {orig_b.count(b'\r')}->{got_b.count(b'\r')}")
    else:
        ok("N17 a translated part differs from the original only in the format string it translated",
           got_b == orig_b.replace(b"Parte %1", b"Part %1"), f"{len(orig_b)} -> {len(got_b)} bytes")

res, vals = tn_case("pure", ["%1.", "o", "(%1)"], lang="italian")
ok("N12 the pure numeric/symbol line is printed exactly when nothing word-bearing is left",
   PURE in res.stdout and res.returncode == 0, f"rc={res.returncode} {res.stdout[-200:]}")

TN = load("translate_numbering")
full = getattr(TN, "full_map", None)
ok("N13 the module exposes full_map(language), the map a run applies", callable(full))
if callable(full):
    missing = []
    for lang, base in TN.LANGUAGE_MAPS.items():
        for pat, rep in base.items():
            m = re.fullmatch(r"%\(\\d\+\)\\\.\\s\*([^\W\d_]+)", pat)
            if not m:
                continue
            kw = m.group(1)
            sample = kw[0].upper() + kw[1:] + " %1"
            want = re.sub(r"%\\(\d)", r"%\1", rep).replace("\\1", "1")
            got = sample
            for pp, rr in full(lang).items():
                new, n = re.subn(pp, rr, sample, flags=re.IGNORECASE)
                if n:
                    got = new
                    break
            if got != want:
                missing.append(f"{lang}:{kw}->{got}")
    ok("N13 EVERY keyword of the nine maps translates before the number as it does after it",
       not missing, f"{missing[:6]}")
    ok("N13 Chinese and Japanese are in LANGUAGE_MAPS", {"chinese", "japanese"} <= set(TN.LANGUAGE_MAPS))
    cites = getattr(TN, "LEXICON_ROWS", {})
    lex_missing = []
    for lang in ("chinese", "japanese"):
        for pat in TN.LANGUAGE_MAPS.get(lang, {}):
            cite = cites.get((lang, pat), "")
            fn = re.search(r"[\w-]+\.md", cite)
            f = TREE / "sub-lexicons" / fn.group(0) if fn else None
            if not f or not f.is_file():
                lex_missing.append(pat)
    ok("N13 every Chinese and Japanese entry cites a lexicon file that exists", not lex_missing,
       f"{lex_missing}")
    ok("N13 the GUESS is unchanged: it still reads only the nine Latin maps",
       TN.detect_language_from_numbering('<w:lvlText w:val="%1. sz. Melléklet"/>') == "hungarian"
       and TN.detect_language_from_numbering('<w:lvlText w:val="%1."/>') is None)

# =========================================================================================
# ARM M — month names in the remnant lists
# =========================================================================================
print(f"\nARM M — a month name beside a number is a remnant, a bare one only warns   [{args.variant}]")
SLM = load("source_language_markers")
DATED = {
    "italian": "signed on 15 settembre 2021 by both",
    "dutch": "signed on 15 maart 2021 by both",
    "german": "signed on 15. März 2021 by both",
    "french": "signed on 15 juillet 2021 by both",
    "spanish": "signed on 15 de marzo de 2021 by both",
    "portuguese": "signed on 15 de março de 2021 by both",
    "polish": "signed on 15 marca 2021 by both",
    "finnish": "signed on 15. maaliskuuta 2021 by both",
    "hungarian": "signed on 2021. március 15. by both",
}
BARE = {
    "italian": "the office on Via Settembre", "dutch": "the Maart committee", "german": "the Mai Group",
    "french": "the Juillet brand", "spanish": "the Marzo fund", "portuguese": "the Março fund",
    "polish": "the Marzec fund", "finnish": "the Maaliskuu fund", "hungarian": "the Március fund",
}
for lang, text in DATED.items():
    b, a = SLM.remnant_verdict(text, lang)
    ok(f"M1 {lang}: a dated month name BLOCKS", len(b) >= 1, f"blocking={len(b)} advisory={len(a)}")
for lang, text in BARE.items():
    b, a = SLM.remnant_verdict(text, lang)
    ok(f"M2 {lang}: a bare month name only WARNS", not b and len(a) >= 1, f"blocking={len(b)} advisory={len(a)}")
en_hits = [(lang, w) for lang in DATED for w in ("April", "August", "September", "November", "December")
           if SLM.scan_remnants(f"signed on 15 {w} 2021", lang)]
ok("M3 an English-identical month word is no marker in any language", not en_hits, f"{en_hits[:6]}")
for name in ("Loi du 25 juin 2008", "Loi du 6 juillet 1989", "Loi du 23 décembre 1986", "Loi du 10 juillet 1965"):
    b, a = SLM.remnant_verdict(f"governed by the {name} as amended", "french")
    ok(f"M4 the kept statute name '{name}' does not block", not b and a, f"blocking={len(b)}")
for lang, text in (("polish", "signed w marcu 2021 by both"), ("hungarian", "paid in márciusban 2021 in full"),
                   ("italian", "signed on 15&#160;settembre&#160;2021 by both")):
    b, a = SLM.remnant_verdict(text, lang)
    ok(f"M4b {lang}: an inflected month, or one beside a number through &#160;, still BLOCKS", len(b) >= 1,
       f"blocking={len(b)} advisory={len(a)}")
fn = getattr(SLM, "bare_month_hits", None)
ok("M5 the module exposes bare_month_hits for quality_check's warning tier", callable(fn))
ok("M5 scan_remnants can leave bare months out (bare_months=False) and keeps them by default",
   callable(fn) and SLM.scan_remnants(BARE["italian"], "italian")
   and not SLM.scan_remnants(BARE["italian"], "italian", bare_months=False))


def qc_case(name, text, lang):
    wd = TMP / f"q-{name}"
    wd.mkdir(parents=True)
    xml = wd / "document.xml"
    xml.write_text(f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<w:document {W}><w:body>'
                   f'{p(r(text))}<w:sectPr/></w:body></w:document>', encoding="utf-8")
    return run("quality_check.py", xml, "--language", lang)


q = qc_case("dated", "The Parties signed the Agreement on 15 settembre 2021.", "italian")
ok("M6 quality_check counts a dated month as an issue (exit 2)", q.returncode == 2,
   f"rc={q.returncode} {q.stdout[-300:]}")
q = qc_case("bare", "The office is on Via Settembre in Rome.", "italian")
ok("M7 quality_check prints a bare month as a WARNING and does not count it (exit 0)",
   q.returncode == 0 and "WARNING" in q.stdout and "Settembre" in q.stdout, f"rc={q.returncode} {q.stdout[-400:]}")

# =========================================================================================
# ARM H — translate_headers_footers' legacy dictionary mode
# =========================================================================================
print(f"\nARM H — the legacy dictionary mode guesses nothing and counts what it left   [{args.variant}]")


def hf_case(name, header_paras, lang):
    wd = TMP / f"h-{name}"
    wd.mkdir(parents=True)
    src = wd / "source.docx"
    paras = "".join(p(r(t)) for t in header_paras)
    hdr = (f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<w:hdr {W}>{paras}</w:hdr>')
    docx(src, p(r("Body.")), extra_parts={"word/header1.xml": hdr})
    return run("translate_headers_footers.py", src, wd / "final", "--language", lang)


h = hf_case("de-left", ["Schuldner", "Vertraulichkeitsvermerk"], "german")
ok("H1 german: a header word the dictionary lacks is COUNTED as left, never 'all numeric/symbol'",
   "numeric/symbol" not in h.stdout and re.search(r"\b1 text run", h.stdout) is not None,
   h.stdout[-400:])
wd_m = TMP / "h-merged"
wd_m.mkdir(parents=True)
src_m = wd_m / "source.docx"
docx(src_m, p(r("Body.")), extra_parts={"word/header1.xml": (
    f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<w:hdr {W}>{p(r("Schuld"), r("ner"))}</w:hdr>')})
h = run("translate_headers_footers.py", src_m, wd_m / "final", "--language", "german")
ok("H1b a word split across two runs, merged AND translated by the dictionary, is not counted as left",
   "Obligor" in (wd_m / "final" / "word" / "header1.xml").read_text(encoding="utf-8")
   and "LEFT AS THEY WERE" not in h.stdout, h.stdout[-300:])
h = hf_case("no", ["Skyldner"], "norwegian")
ok("H2 a language with no legacy dictionary says NOT SUPPORTED", "NOT SUPPORTED" in h.stdout, h.stdout[-300:])
h = hf_case("digits", ["12 / 2021"], "german")
ok("H3 a header with no letters says so, honestly", "numeric/symbol" not in h.stdout
   and "no text with letters" in h.stdout.lower(), h.stdout[-300:])
THF = load("translate_headers_footers")
out = io.StringIO()
saved = sys.stdout
sys.stdout = out
try:
    wd = TMP / "h-none"
    wd.mkdir(parents=True)
    src = wd / "source.docx"
    docx(src, p(r("Body.")), extra_parts={"word/header1.xml": (
        f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<w:hdr {W}>{p(r("Schuldner"))}</w:hdr>')})
    THF.translate_headers_footers_legacy(str(src), str(wd / "final"), language=None)
finally:
    sys.stdout = saved
ok("H4 called with no language it GUESSES NOTHING and says NOT SUPPORTED",
   "Auto-detected" not in out.getvalue() and "NOT SUPPORTED" in out.getvalue(), out.getvalue()[-300:])

# =========================================================================================
# ARM D — the diligence audit's skill Step 1c row
# =========================================================================================
print(f"\nARM D — verify_diligence asks whether skill Step 1c was done   [{args.variant}]")


def dil_case(name, decl):
    wd = TMP / f"d-{name}"
    wd.mkdir(parents=True)
    (wd / "paragraphs.json").write_bytes(b"[]")
    if decl is not None:
        (wd / "source_language.json").write_bytes(decl)
    res = run("verify_diligence.py", wd, "--report-only")
    row = next((ln for ln in res.stdout.splitlines() if "Step 1c" in ln and ln.strip().startswith("[")), "")
    return res, row


for name, decl, want in (("supported", b'{"source_language": "dutch"}\n', "PASS"),
                         ("unsupported", b'{"source_language": "norwegian"}\n', "WARN"),
                         ("missing", None, "FAIL"),
                         ("unreadable", b"{not json", "FAIL")):
    res, row = dil_case(name, decl)
    ok(f"D1 {name} declaration: the skill Step 1c row reads {want}", f"[{want}" in row, f"row={row!r} rc={res.returncode}")

# =========================================================================================
print("\n" + "=" * 92)
print(f"  {CHECKED} check(s), {len(FAIL)} failure(s)   [{args.variant}]")
for f in FAIL:
    print(f"    FAIL  {f}")
if not args.keep:
    shutil.rmtree(TMP, ignore_errors=True)
sys.exit(1 if FAIL else 0)
