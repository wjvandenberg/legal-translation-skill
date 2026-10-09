# -*- coding: utf-8 -*-
"""BRANCH 12 SLICE 12a — the declared source language, and every check that reads it.

WHAT THE ROWS SAY. S1: on a language the skill does not support, four scripts guessed, three wrong
answers, and every one printed CLEAN or PASSED. S2: the lexicon check applied the wrong language's rules
and passed. C9: its guess is wrong and prints PASSED. H1: five components, four answers, every one CLEAN.
C22's detection half: the remnant block scanned the language one detector guessed.

WOUTER'S CHOICES (2026-10-08 (2), section 3.2 of PLAN-2-step-b.md): the operator DECLARES the source
language once at Step 1; every language-dependent check reads that declaration; repack's two-detector
agreement on the original cross-checks it, a mismatch reported; a language the skill does not support,
or one not settled, makes every such check say NOT SUPPORTED — never CLEAN or PASSED — the run going on.

  R  THE READER AND THE WRITER — source_language_markers.read_declared_language, not_supported, and the
     --declare command that writes source_language.json beside the notes.
  L  lexicon_compliance — the declaration beside the notes (Step 4d) or given by --notes (pre-repack);
     an unsupported language runs only the language-agnostic rules, which still block; a guess never
     says PASSED.
  A  apply's source-language scan.
  Q  quality_check's remnant rows and its closing line; an aux part that will not parse is an issue.
  P  repack — the cross-check, the pre-repack lexicon scan and the remnant block; nothing that blocks
     today stops blocking when nothing was declared.
  T  THE TWO TREES and the words: repack identical; Step 1c written in both.

RED FIRST: run before 12a's code exists, every arm must fail.

    uv run --with lxml python tests/test_declared_language.py
    uv run --with lxml python tests/test_declared_language.py --variant us

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
from make_fixtures import R, W, WP, docx, p, r  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
ap = argparse.ArgumentParser()
ap.add_argument("--variant", default="uk", choices=("uk", "us"))
ap.add_argument("--keep", action="store_true")
args = ap.parse_args()
TREE = ROOT / args.variant
SCRIPTS = TREE / "scripts"
TMP = Path(tempfile.mkdtemp(prefix="b12a-test-"))
ENV = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1", PYTHONDONTWRITEBYTECODE="1")
PY = ["uv", "run", "--with", "lxml", "python"]
DECL = "source_language.json"
FAIL, CHECKED, VOIDED = [], 0, []


def ok(label, cond, detail=""):
    global CHECKED
    CHECKED += 1
    print(("  OK   " if cond else "  XX   ") + label + (f"   ({detail})" if detail and not cond else ""))
    if not cond:
        FAIL.append(label)
    return cond


def run(script, *argv, timeout=600):
    res = subprocess.run(PY + [str(SCRIPTS / script)] + [str(a) for a in argv], capture_output=True, text=True,
                         encoding="utf-8", errors="replace", cwd=str(ROOT), env=ENV, timeout=timeout)
    return res.returncode, (res.stdout or "") + (res.stderr or "")


def declare(d, language):
    (d / DECL).write_bytes(json.dumps({"source_language": language}).encode("utf-8"))


def section(title):
    print("\n" + "-" * 96 + "\n" + title + "\n" + "-" * 96)


# Synthetic sources, each written so the ORIGINAL's own detectors name its language (Italian, French), or
# so that none of them can (Norwegian — no detector in the skill knows it).
SRC = {
    "italian": ["Il presente contratto è stipulato tra le parti per la fornitura della turbina.",
                "Ogni parte deve rispettare gli obblighi che sono previsti nel presente contratto.",
                "Le parti sono tenute alla riservatezza delle informazioni per tutta la durata."],
    "norwegian": ["Denne avtalen er inngått mellom partene om levering av turbinen til prosjektet.",
                  "Hver part skal overholde forpliktelsene som er fastsatt i denne avtalen her.",
                  "Partene skal holde informasjonen fortrolig i hele avtalens løpetid og etterpå."],
    "english": ["This agreement is entered into between the parties for the supply of the turbine.",
                "Each party shall comply with the obligations provided for in this agreement.",
                "The parties shall keep the information confidential for the whole term."],
}
CLEAN = ["This agreement is entered into between the parties for the supply of the turbine.",
         "Each party shall comply with the obligations provided for in this agreement.",
         "The parties shall keep the information confidential for the whole term."]
DELLA = CLEAN[:2] + ["The parties shall keep the information della confidential for the whole term."]


def notes_for(src, en):
    return [{"idx": i, "text": s, "en": e, "style": "Normal",
             "runs": [{"start": 0, "end": len(s), "text": s, "bold": False, "italic": False}]}
            for i, (s, e) in enumerate(zip(src, en))]


def workdir(name, lang, en, declared=None):
    d = TMP / name
    (d / "final" / "word").mkdir(parents=True, exist_ok=True)
    nj = d / "paragraphs.json"
    nj.write_bytes(json.dumps(notes_for(SRC[lang], en), ensure_ascii=False, indent=1).encode("utf-8"))
    if declared is not None:
        declare(d, declared)
    return d, nj


def wrap(body):
    return (f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
            f'<w:document {W} {R} {WP}><w:body>{body}'
            f'<w:sectPr><w:pgSz w:w="11906" w:h="16838"/></w:sectPr></w:body></w:document>')


print("=" * 96)
print(f"BRANCH 12 SLICE 12a — the declared source language   variant={args.variant}")
print(f"scripts {SCRIPTS}")
print("=" * 96)

# =============================================================================================
# ARM R — the reader and the writer
# =============================================================================================
section("ARM R — read_declared_language, not_supported, and --declare")
spec = importlib.util.spec_from_file_location("slm_under_test", SCRIPTS / "source_language_markers.py")
slm = importlib.util.module_from_spec(spec)
spec.loader.exec_module(slm)
reader = getattr(slm, "read_declared_language", None)
ns = getattr(slm, "not_supported", None)
ok("R1: the module declares read_declared_language, not_supported and DECLARATION_FILE = source_language.json",
   callable(reader) and callable(ns) and getattr(slm, "DECLARATION_FILE", None) == DECL)
if callable(reader):
    d, nj = workdir("r-supported", "italian", CLEAN, declared="Spanish")
    got = reader(str(nj))
    ok("R2: a supported language, case folded, read from the NOTES path", got[:2] == ("spanish", "supported"), got)
    got = reader(str(d))
    ok("R3: and from the FOLDER the notes sit in", got[:2] == ("spanish", "supported"), got)
    d, nj = workdir("r-norwegian", "norwegian", CLEAN, declared="norwegian")
    got = reader(str(nj))
    ok("R4: a declared language the skill does not support is 'unsupported', its reason naming it",
       got[:2] == ("norwegian", "unsupported") and "norwegian" in got[2].lower(), got)
    d, nj = workdir("r-english", "english", CLEAN, declared="english")
    got = reader(str(nj))
    ok("R5: English is 'unsupported' and its reason says it is the TARGET language",
       got[:2] == ("english", "unsupported") and "target" in got[2].lower(), got)
    d, nj = workdir("r-none", "italian", CLEAN)
    got = reader(str(nj))
    ok("R6: no declaration is 'undeclared', its reason naming Step 1c and the file",
       got[:2] == (None, "undeclared") and "1c" in got[2] and DECL in got[2], got)
    for label, raw in (("not JSON", b"{not json"), ("an empty name", b'{"source_language": ""}'),
                       ("a name that is not letters", b'{"source_language": "nor-wegian 2"}'),
                       ("not an object", b'["italian"]'), ("no key", b'{"language": "italian"}')):
        d, nj = workdir("r-bad-" + re.sub(r"\W+", "-", label), "italian", CLEAN)
        (d / DECL).write_bytes(raw)
        got = reader(str(nj))
        ok(f"R7: a declaration that is {label} is 'unreadable', never a language",
           got[0] is None and got[1] == "unreadable", got)
    ok("R8: no notes at all reads 'undeclared'", reader(None)[:2] == (None, "undeclared"))
    d, nj = workdir("r-bom", "italian", CLEAN)
    (d / DECL).write_bytes(b"\xef\xbb\xbf" + json.dumps({"source_language": "dutch"}).encode("utf-8"))
    got = reader(str(nj))
    ok("R14: a declaration written with a UTF-8 BOM (Windows, by hand) still reads", got[:2] == ("dutch", "supported"),
       got)
    got = reader(str(d / "no-such-workdir"))
    ok("R15: a folder that does not exist reads 'undeclared' — never its PARENT's declaration",
       got[:2] == (None, "undeclared"), got)
resolver = getattr(slm, "resolve_source_language", None)
ok("R16: the module declares resolve_source_language, the one policy", callable(resolver))
if callable(resolver):
    d, nj = workdir("r-resolve", "italian", CLEAN)
    got = resolver(str(nj), guess=lambda: "italian")
    ok("R16: nothing declared, a guess is ACTED on but cannot rule",
       got.language == "italian" and got.cannot_rule and "guess" in got.cannot_rule, got)
    declare(d, "norwegian")
    got = resolver(str(nj), guess=lambda: "italian")
    ok("R16: a declaration beats a guess; unsupported, it cannot rule", got.language == "norwegian" and got.cannot_rule,
       got)
    got = resolver(str(nj), explicit="Dutch")
    ok("R16: an explicit supported language rules, and warns against the declaration",
       got.language == "dutch" and got.cannot_rule is None and got.warning and "norwegian" in got.warning, got)
if callable(ns):
    line = ns("the remnant scan", "a reason")
    ok("R9: not_supported() says NOT SUPPORTED, names the check and the reason, and never CLEAN or PASSED",
       line.startswith("NOT SUPPORTED") and "the remnant scan" in line and "a reason" in line
       and "CLEAN" not in line and "PASSED" not in line, line)

dw = TMP / "r-cli"
dw.mkdir(parents=True, exist_ok=True)
rc, out = run("source_language_markers.py", "--declare", "Spanish", dw)
data = json.loads((dw / DECL).read_text(encoding="utf-8")) if (dw / DECL).is_file() else None
ok("R10: --declare writes source_language.json, the name lowercased, and exits 0",
   rc == 0 and data == {"source_language": "spanish"}, f"rc={rc} data={data}")
ok("R10: and says the language is supported", "supported" in out.lower() and "NOT SUPPORTED" not in out, out[-300:])
rc, out = run("source_language_markers.py", "--declare", "norwegian", dw)
data = json.loads((dw / DECL).read_text(encoding="utf-8")) if (dw / DECL).is_file() else None
ok("R11: --declare of a language the skill does not support writes it, exits 0, and says NOT SUPPORTED",
   rc == 0 and data == {"source_language": "norwegian"} and "NOT SUPPORTED" in out, f"rc={rc} data={data}")
ok("R11: and says it REPLACED the earlier declaration", "spanish" in out.lower() and "replac" in out.lower(), out[-300:])
before = (dw / DECL).read_bytes() if (dw / DECL).is_file() else None
rc, out = run("source_language_markers.py", "--declare", "no-way 2", dw)
ok("R12: a name that is not letters is refused, exit 2, the file untouched",
   rc == 2 and (dw / DECL).is_file() and (dw / DECL).read_bytes() == before, f"rc={rc}")
rc, out = run("source_language_markers.py", "--declare", "italian", TMP / "no-such-folder")
ok("R13: a workdir that does not exist is refused, exit 2, nothing created",
   rc == 2 and not (TMP / "no-such-folder").exists(), f"rc={rc}")

# =============================================================================================
# ARM L — lexicon_compliance
# =============================================================================================
section("ARM L — lexicon_compliance reads the declaration")
WIND = CLEAN[:2] + ["The wind park shall keep the information confidential for the whole term."]
PRESENT = CLEAN[:2] + ["The parties shall keep the present agreement confidential for the whole term."]


def lex(nj_or_xml, *extra):
    rc, out = run("lexicon_compliance.py", nj_or_xml, *extra)
    m = re.search(r"language=([^,\s]+)", out)
    return rc, out, (m.group(1) if m else None)


d, nj = workdir("l-dutch", "italian", WIND, declared="dutch")
rc, out, lang = lex(nj, "--stage", "pre-apply")
ok("L1: declared dutch — the Dutch calque rule fires (exit 1), read as dutch", rc == 1 and lang == "dutch",
   f"rc={rc} lang={lang}")
d, nj = workdir("l-spanish", "italian", WIND, declared="spanish")
rc, out, lang = lex(nj, "--stage", "pre-apply")
ok("L2: declared spanish — the Dutch rule does not apply; PASSED, read as spanish",
   rc == 0 and lang == "spanish" and "PASSED" in out, f"rc={rc} lang={lang}")
d, nj = workdir("l-norwegian", "norwegian", CLEAN, declared="norwegian")
rc, out, lang = lex(nj, "--stage", "pre-apply")
ok("L3: declared norwegian — NOT SUPPORTED, exit 0, and never PASSED",
   rc == 0 and "NOT SUPPORTED" in out and "PASSED" not in out, f"rc={rc} lang={lang}")
d, nj = workdir("l-norwegian-every", "norwegian", WIND, declared="norwegian")
rc, out, lang = lex(nj, "--stage", "pre-apply")
ok("L3b: declared norwegian — EVERY language's rules run, as for an unknown language: the Dutch calque still "
   "blocks, so the scan is never narrower than a guess (CLAUDE.md 2.4 item 5)", rc == 1 and lang == "*",
   f"rc={rc} lang={lang}")
d, nj = workdir("l-norwegian-agnostic", "norwegian", PRESENT, declared="norwegian")
rc, out, lang = lex(nj, "--stage", "pre-apply")
ok("L4: declared norwegian — a language-AGNOSTIC rule still blocks (exit 1)", rc == 1, f"rc={rc}")
d, nj = workdir("l-english", "english", CLEAN, declared="english")
rc, out, lang = lex(nj, "--stage", "pre-apply")
ok("L5: declared english — NOT SUPPORTED naming the target language, never PASSED",
   rc == 0 and "NOT SUPPORTED" in out and "target" in out.lower() and "PASSED" not in out, f"rc={rc}")
d, nj = workdir("l-undeclared", "italian", CLEAN)
rc, out, lang = lex(nj, "--stage", "pre-apply")
ok("L6: nothing declared — it still runs on its guess, but says NOT SUPPORTED and never PASSED",
   rc == 0 and lang == "italian" and "NOT SUPPORTED" in out and "PASSED" not in out and "guess" in out.lower(),
   f"rc={rc} lang={lang}")
d, nj = workdir("l-undeclared-block", "italian", PRESENT)
rc, out, lang = lex(nj, "--stage", "pre-apply")
ok("L7: nothing declared — what blocks today still blocks (exit 1)", rc == 1, f"rc={rc}")
xml = TMP / "l-xml.xml"
xml.write_bytes(wrap("".join(p(r(t)) for t in WIND)).encode("utf-8"))
d, nj = workdir("l-notes-dutch", "italian", CLEAN, declared="dutch")
rc, out, lang = lex(xml, "--stage", "pre-repack", "--notes", nj)
ok("L8: pre-repack on the XML, --notes beside a dutch declaration — read as dutch, the rule fires",
   rc == 1 and lang == "dutch", f"rc={rc} lang={lang}")
xml_clean = TMP / "l-xml-clean.xml"
xml_clean.write_bytes(wrap("".join(p(r(t)) for t in CLEAN)).encode("utf-8"))
d, nj = workdir("l-notes-norwegian", "norwegian", CLEAN, declared="norwegian")
rc, out, lang = lex(xml_clean, "--stage", "pre-repack", "--notes", nj)
ok("L9: pre-repack, --notes beside a norwegian declaration — NOT SUPPORTED, exit 0, never PASSED",
   rc == 0 and "NOT SUPPORTED" in out and "PASSED" not in out, f"rc={rc} lang={lang}")
d, nj = workdir("l-notes-none", "italian", CLEAN)
rc, out, lang = lex(xml, "--stage", "pre-repack", "--notes", nj, "--guessed", "italian")
ok("L10: pre-repack, nothing declared, repack's guess given — read as that guess, NOT SUPPORTED, never PASSED",
   rc == 0 and lang == "italian" and "NOT SUPPORTED" in out and "PASSED" not in out, f"rc={rc} lang={lang}")
d, nj = workdir("l-none-case", "italian", CLEAN)
rc, out, lang = lex(nj, "--stage", "pre-apply", "--language", "None")
ok("L11: --language None, in any case, is the language-agnostic run the operator asked for: PASSED",
   rc == 0 and lang == "none" and "PASSED" in out and "NOT SUPPORTED" not in out, f"rc={rc} lang={lang}")
d, nj = workdir("l-star", "italian", WIND)
rc, out, lang = lex(nj, "--stage", "pre-apply", "--language", "*")
ok("L12: --language * still runs every language's rules (the Dutch calque blocks), and names no language",
   rc == 1 and lang == "*", f"rc={rc} lang={lang}")
d, nj = workdir("l-override", "italian", CLEAN, declared="spanish")
rc, out, lang = lex(nj, "--stage", "pre-apply", "--language", "italian")
ok("L13: an explicit --language that contradicts the declaration is used, and WARNED, naming both",
   lang == "italian" and bool(re.search(r"WARNING.*--language italian.*spanish", out)), f"rc={rc} lang={lang}")

# =============================================================================================
# ARM A — apply's source-language scan
# =============================================================================================
section("ARM A — apply's source-language scan reads the declaration")


def apply_case(name, lang, en, declared):
    d, nj = workdir(name, lang, en, declared=declared)
    orig = d / "orig.docx"
    docx(orig, "".join(p(r(t)) for t in SRC[lang]))
    rc, out = run("apply_translations_textmatch.py", orig, nj, d / "out.xml")
    scan = [ln.strip() for ln in out.splitlines() if "Source-language scan" in ln or "remnant(s) detected" in ln]
    return rc, out, scan, (d / "out.xml").is_file()


rc, out, scan, wrote = apply_case("a-italian", "italian", CLEAN, "italian")
ok("A1: declared italian, a clean translation — CLEAN, as today", wrote and any("CLEAN" in s for s in scan), scan)
rc, out, scan, wrote = apply_case("a-italian-della", "italian", DELLA, "italian")
ok("A2: declared italian, an Italian remnant — reported, as today",
   wrote and any("Italian remnant" in s for s in scan), scan)
rc, out, scan, wrote = apply_case("a-norwegian", "norwegian", CLEAN, "norwegian")
ok("A3: declared norwegian — NOT SUPPORTED, never CLEAN",
   wrote and any("NOT SUPPORTED" in s for s in scan) and not any("CLEAN" in s for s in scan), scan)
rc, out, scan, wrote = apply_case("a-english", "english", CLEAN, "english")
ok("A4: declared english — NOT SUPPORTED, naming the target language",
   wrote and any("NOT SUPPORTED" in s and "target" in s.lower() for s in scan), scan)
rc, out, scan, wrote = apply_case("a-undeclared", "italian", CLEAN, None)
ok("A5: nothing declared — it scans its guess but says NOT SUPPORTED, never CLEAN",
   wrote and any("NOT SUPPORTED" in s and "guess" in s.lower() for s in scan)
   and not any("CLEAN" in s for s in scan), scan)
rc, out, scan, wrote = apply_case("a-undeclared-della", "italian", DELLA, None)
ok("A6: nothing declared — a remnant of its guess is still reported", wrote and any("Italian remnant" in s for s in scan),
   scan)
ok("A6b: and the warnings say they rest on a guess — NOT SUPPORTED is said whether or not it found anything",
   any("NOT SUPPORTED" in s and "guess" in s.lower() for s in scan), scan)
ok("A7: apply no longer tells the operator to pass a flag it does not have",
   "pass --source-language" not in (SCRIPTS / "apply_translations_textmatch.py").read_text(encoding="utf-8"))

# =============================================================================================
# ARM Q — quality_check
# =============================================================================================
section("ARM Q — quality_check's remnant rows and its closing line")


def qc_case(name, lang, en, declared, header=None, extra=()):
    d, nj = workdir(name, lang, en, declared=declared)
    xml = d / "final" / "word" / "document.xml"
    xml.write_bytes(wrap("".join(p(r(t)) for t in en)).encode("utf-8"))
    if header is not None:
        (d / "final" / "word" / "header1.xml").write_bytes(header.encode("utf-8"))
    rc, out = run("quality_check.py", xml, "--with-source", nj, "--variant", args.variant,
                  "--aux-dir", d / "final", *extra)
    rows = dict((m.group(1), m.group(2).strip()) for m in re.finditer(r"(?m)^\s+(\S+_remnants|aux_\S+)\s+(.+)$", out))
    return rc, out, rows


HDR = (f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<w:hdr {W}>{p(r("Confidential draft"))}</w:hdr>')
rc, out, rows = qc_case("q-italian", "italian", CLEAN, "italian", header=HDR)
ok("Q1: declared italian, clean — the italian_remnants row CLEAN and the run PASSED, as today",
   rows.get("italian_remnants") == "CLEAN" and "*** PASSED" in out and rc == 0, f"rc={rc} rows={rows}")
rc, out, rows = qc_case("q-italian-della", "italian", DELLA, "italian")
ok("Q2: declared italian, an Italian remnant — counted as an issue, as today",
   rows.get("italian_remnants", "").endswith("issues") and rc == 2, f"rc={rc} rows={rows}")
rc, out, rows = qc_case("q-norwegian", "norwegian", CLEAN, "norwegian", header=HDR)
ok("Q3: declared norwegian — the remnant row says NOT SUPPORTED, never CLEAN",
   rows.get("norwegian_remnants", "").startswith("NOT SUPPORTED"), rows)
ok("Q3: and so does the aux header row", rows.get("aux_header1.xml", "").startswith("NOT SUPPORTED"), rows)
ok("Q3: the closing line never says PASSED, it says NOT SUPPORTED, and the run goes on (exit 0)",
   "*** PASSED" not in out and "NOT SUPPORTED" in out.split("TOTAL")[-1] and rc == 0, f"rc={rc}")
rc, out, rows = qc_case("q-undeclared", "italian", CLEAN, None)
ok("Q4: nothing declared — the guessed row says NOT SUPPORTED, never CLEAN, and no PASSED",
   rows.get("italian_remnants", "").startswith("NOT SUPPORTED") and "*** PASSED" not in out and rc == 0,
   f"rc={rc} rows={rows}")
rc, out, rows = qc_case("q-undeclared-della", "italian", DELLA, None)
ok("Q5: nothing declared — a remnant of its guess is still an issue (exit 2)",
   rows.get("italian_remnants", "").endswith("issues") and rc == 2, f"rc={rc} rows={rows}")
rc, out, rows = qc_case("q-explicit", "italian", CLEAN, None, extra=("--language", "italian"))
ok("Q6: nothing declared but --language given — the operator's statement rules: CLEAN and PASSED",
   rows.get("italian_remnants") == "CLEAN" and "*** PASSED" in out, f"rows={rows}")
rc, out, rows = qc_case("q-override", "italian", CLEAN, "norwegian", extra=("--language", "italian"))
ok("Q6b: an explicit --language that contradicts the declaration is used, and WARNED, naming both",
   rows.get("italian_remnants") == "CLEAN" and bool(re.search(r"WARNING.*--language italian.*norwegian", out)),
   f"rows={rows}")
rc, out, rows = qc_case("q-unparseable", "italian", CLEAN, "italian", header="<w:hdr this is not xml")
ok("Q7: an aux part that will not PARSE is an issue, never CLEAN (S1's wider trigger)",
   rows.get("aux_header1.xml", "CLEAN") != "CLEAN" and rc == 2, f"rc={rc} rows={rows}")

# =============================================================================================
# ARM P — repack: the cross-check, the pre-repack lexicon scan and the remnant block
# =============================================================================================
section("ARM P — repack reads the declaration")
GATE = "SKILL GATE FIRED"


def repack_case(name, lang, en, declared):
    d, nj = workdir(name, lang, en, declared=declared)
    orig = d / "orig.docx"
    docx(orig, "".join(p(r(t)) for t in SRC[lang]))
    xml = d / "final" / "word" / "document.xml"
    xml.write_bytes(wrap("".join(p(r(t)) for t in en)).encode("utf-8"))
    out = d / "out.docx"
    rc, blob = run("repack_docx.py", orig, xml, out, "--paragraphs", nj)
    (d / "repack_output.txt").write_bytes(blob.encode("utf-8"))      # kept with --keep, for a failure
    lexline = next((ln for ln in blob.splitlines() if "Lexicon compliance scan" in ln and "pre-repack" in ln), "")
    return rc, blob, out.is_file(), lexline, lex_block(blob)


def lex_block(blob):
    """The pre-repack lexicon scan's OWN lines, from its header to its own closing line. Not a split on
    repack's labels: repack's prints are buffered while its validators write straight through, so the
    labels arrive out of order — measured on this suite's first run, where validate_apply's
    'PASSED: all declared tokens found' landed before repack's label and read as the lexicon's."""
    lines = blob.splitlines()
    i = next((k for k, ln in enumerate(lines) if "Lexicon compliance scan" in ln), None)
    if i is None:
        return ""
    out = []
    for ln in lines[i:]:
        out.append(ln)
        if "lexicon violations detected" in ln or "NO BLOCKING VIOLATION FOUND" in ln or "*** BLOCKED" in ln:
            break
    return "\n".join(out)


rc, blob, wrote, lexline, lexpart = repack_case("p-italian", "italian", CLEAN, "italian")
ok("P1: declared italian, clean — delivered", rc == 0 and wrote, f"rc={rc}")
ok("P1: the remnant block ran in the DECLARED language and was clean",
   bool(re.search(r"Remnant block: language=italian\b.*declared", blob)) and "Remnant block clean" in blob)
ok("P1: the cross-check agrees, in one line", bool(re.search(r"(?i)cross-check.*italian.*as declared", blob)))
ok("P1: the pre-repack lexicon scan read the declaration", "language=italian" in lexline, lexline)
rc, blob, wrote, lexline, lexpart = repack_case("p-italian-della", "italian", DELLA, "italian")
ok("P2: declared italian, an Italian remnant — REFUSED, as today", rc != 0 and not wrote and GATE in blob, f"rc={rc}")
rc, blob, wrote, lexline, lexpart = repack_case("p-norwegian", "norwegian", DELLA, "norwegian")
ok("P3: declared norwegian — delivered: the block cannot rule on a language it has no markers for",
   rc == 0 and wrote, f"rc={rc}")
ok("P3: the remnant block says NOT SUPPORTED, never clean",
   bool(re.search(r"Remnant block: NOT SUPPORTED", blob)) and "Remnant block clean" not in blob)
ok("P3: the pre-repack lexicon scan says NOT SUPPORTED and never PASSED",
   "NOT SUPPORTED" in lexpart and "PASSED" not in lexpart)
rc, blob, wrote, lexline, lexpart = repack_case("p-mismatch", "italian", CLEAN, "french")
ok("P4: declared french on an Italian original — a MISMATCH reported, naming both, and still delivered",
   rc == 0 and wrote and bool(re.search(r"(?i)mismatch.*french.*italian|mismatch.*italian.*french", blob)),
   f"rc={rc}")
ok("P4: and the declaration is what every check used", "language=french" in lexline
   and bool(re.search(r"Remnant block: language=french\b", blob)), lexline)
rc, blob, wrote, lexline, lexpart = repack_case("p-undeclared", "italian", CLEAN, None)
ok("P5: nothing declared, clean — delivered, the block ran on its guess", rc == 0 and wrote
   and bool(re.search(r"Remnant block: language=italian\b", blob)), f"rc={rc}")
ok("P5: and says NOT SUPPORTED rather than clean", "NOT SUPPORTED" in blob and "Remnant block clean" not in blob)
ok("P5: the pre-repack lexicon scan ran on repack's guess and never said PASSED",
   "language=italian" in lexline and "PASSED" not in lexpart, lexline)
rc, blob, wrote, lexline, lexpart = repack_case("p-undeclared-della", "italian", DELLA, None)
ok("P6: nothing declared, an Italian remnant — still REFUSED: no gate softened", rc != 0 and not wrote and GATE in blob,
   f"rc={rc}")

# =============================================================================================
# ARM T — the two trees and the words
# =============================================================================================
section("ARM T — both trees, and Step 1c")
ok("T1: repack_docx.py is byte-identical in uk/ and us/",
   (ROOT / "uk" / "scripts" / "repack_docx.py").read_bytes() == (ROOT / "us" / "scripts" / "repack_docx.py").read_bytes())
for t in ("uk", "us"):
    doc = (ROOT / t / "skill-docs" / "01-setup-and-extract.md").read_text(encoding="utf-8")
    ok(f"T2: {t}'s Step 1 carries Step 1c and its --declare command",
       "Step 1c" in doc and "source_language_markers.py --declare" in doc)

if not args.keep:
    shutil.rmtree(TMP, ignore_errors=True)
print("\n" + "=" * 96)
print(f"  {CHECKED} check(s), {len(FAIL)} failure(s), {len(VOIDED)} void")
for f in FAIL:
    print(f"    FAIL  {f}")
print("=" * 96)
sys.exit(1 if FAIL or VOIDED else 0)
