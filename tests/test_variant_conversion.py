# -*- coding: utf-8 -*-
"""STEP 13, SUB-STEP 13.4 (registers H1 and H3) — A SOURCE ALREADY IN ENGLISH IS A DECLARED MODE, NOT A GUESS.

H3, Wouter's finding on D07: a document already in English met the full translation pipeline, every language
check inert and printing CLEAN, 35 minutes and 28 commands to change 11 paragraphs; the job is legitimate - "give
me the US version of this English contract" - and it deserves a mode of its own. Declaring `english` at skill
Step 1c now OPENS the variant-conversion mode, recorded in source_language.json beside the language; only that
declaration opens it; the diligence audit reads it; every gate still runs.

WHAT IS ASSERTED, per tree, through the tree's own scripts:
  D  the declaration: `--declare english` records the mode and says so; any other language records none, and a
     second declaration replaces the first - mode and all;
  M  the reader, declared_mode(): the mode only where the file names English AND carries the key - a file
     written by hand or before 13.4 (English, no key), a key beside another language, nothing declared and an
     unreadable file all open NO mode; read_declared_language() is unchanged by the key, so every language-
     dependent check still says NOT SUPPORTED on English;
  V  the diligence audit's Step 1c: PASS on the mode, naming it; WARN on English without it, saying to declare
     again; PASS on a supported language; FAIL with nothing declared;
  S  a SYNTHETIC English source (UK spelling) through the operator's path - extract, the English written as the
     source in the delivered variant, apply, post_process, repack: the delivered text is the declared English
     paragraph for paragraph; where the English IS the source (every paragraph in the uk tree's own variant)
     the delivered paragraph's XML is the source's, byte for byte; and the audit's Step 1c reads the mode.

RED FIRST: against the scripts before 13.4 (--scripts, a copy of main's), D, M and V fail - no mode is recorded,
there is no reader, and the audit WARNs on English (measured 2026-10-20 (2)).

    uv run --with lxml python tests/test_variant_conversion.py
    uv run --with lxml python tests/test_variant_conversion.py --variant us
    uv run --with lxml python tests/test_variant_conversion.py --scripts <dir>    # RED

Synthetic only. No client text.
"""
import argparse
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.dont_write_bytecode = True
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tests"))
from make_fixtures import docx, p, r  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--variant", default="uk", choices=("uk", "us"))
ap.add_argument("--scripts", default=None, help="another scripts directory, e.g. main's, for RED")
args = ap.parse_args()
SCRIPTS = Path(args.scripts) if args.scripts else ROOT / args.variant / "scripts"
ENV = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1", PYTHONDONTWRITEBYTECODE="1")
TMP = Path(tempfile.mkdtemp(prefix="b13-4-"))
FAIL, CHECKED = [], 0


def ok(label, cond, detail=""):
    global CHECKED
    CHECKED += 1
    print(f"  {'ok  ' if cond else 'FAIL'} {label}" + ("" if cond else f"   {detail}"))
    if not cond:
        FAIL.append(label)


def run(script, *a):
    r_ = subprocess.run([sys.executable, str(SCRIPTS / script), *map(str, a)], capture_output=True, text=True,
                        encoding="utf-8", errors="replace", env=ENV, timeout=300)
    return r_.returncode, (r_.stdout or "") + (r_.stderr or "")


def load_markers():
    spec = importlib.util.spec_from_file_location(f"slm_{args.variant}_{id(SCRIPTS)}",
                                                  SCRIPTS / "source_language_markers.py")
    mod = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(SCRIPTS))
    try:
        spec.loader.exec_module(mod)
    finally:
        sys.path.remove(str(SCRIPTS))
    return mod


def workdir(name, declaration=None):
    d = TMP / name
    d.mkdir()
    if declaration is not None:
        (d / "source_language.json").write_text(declaration, encoding="utf-8")
    return d


def step_1c(d):
    rc, out = run("verify_diligence.py", d, "--report-only", "--variant", args.variant)
    m = re.search(r"\[(PASS|WARN|FAIL|N/A) *\] Step 1c[^\n]*\n((?:\s{4,}.*\n?)*)", out)
    return (m.group(1), m.group(0)) if m else (None, out[-400:])


print(f"{args.variant}: {SCRIPTS}")
M = load_markers()
reader = getattr(M, "declared_mode", None)
MODE = getattr(M, "VARIANT_CONVERSION", "variant-conversion")

print("\nARM D - the declaration")
d = workdir("d-english")
rc, out = run("source_language_markers.py", "--declare", "english", d)
rec = json.loads((d / "source_language.json").read_text(encoding="utf-8")) if (d / "source_language.json").is_file() else {}
ok("D1: --declare english exits 0 and records the language", rc == 0 and rec.get("source_language") == "english", out)
ok("D2: ...and the variant-conversion mode beside it", rec.get("mode") == "variant-conversion", str(rec))
ok("D3: ...and SAYS the mode is open", "VARIANT-CONVERSION MODE" in out, out[:300])
d = workdir("d-dutch")
rc, out = run("source_language_markers.py", "--declare", "dutch", d)
rec = json.loads((d / "source_language.json").read_text(encoding="utf-8"))
ok("D4: --declare dutch records no mode", rc == 0 and rec == {"source_language": "dutch"}, str(rec))
ok("D5: ...and says nothing of one", "VARIANT-CONVERSION" not in out.upper(), out[:300])
d = workdir("d-replace")
run("source_language_markers.py", "--declare", "english", d)
run("source_language_markers.py", "--declare", "dutch", d)
rec = json.loads((d / "source_language.json").read_text(encoding="utf-8"))
ok("D6: declaring dutch after english replaces the mode with it", rec == {"source_language": "dutch"}, str(rec))

print("\nARM M - the reader, declared_mode()")
ok("M0: the reader exists", callable(reader))
if callable(reader):
    cases = [
        ("the mode recorded", '{"source_language": "english", "mode": "variant-conversion"}', MODE),
        ("English with no key (by hand, or before 13.4)", '{"source_language": "english"}', None),
        ("the key beside another language", '{"source_language": "dutch", "mode": "variant-conversion"}', None),
        ("another mode name", '{"source_language": "english", "mode": "translate"}', None),
        ("nothing declared", None, None),
        ("an unreadable file", "{not json", None),
    ]
    for i, (label, decl, want) in enumerate(cases, 1):
        got = reader(str(workdir(f"m{i}", decl)))
        ok(f"M{i}: {label} -> {want}", got == want, f"got {got!r}")
    lang, state, _why = M.read_declared_language(str(workdir("m-lang", '{"source_language": "english", "mode": "variant-conversion"}')))
    ok("M7: read_declared_language is unchanged by the key: english, unsupported", (lang, state) == ("english", "unsupported"))

print("\nARM V - the diligence audit's Step 1c")
for label, decl, sev, needle in [
        ("the mode", '{"source_language": "english", "mode": "variant-conversion"}', "PASS", "variant-conversion"),
        ("English without the mode", '{"source_language": "english"}', "WARN", "--declare english"),
        ("a supported language", '{"source_language": "dutch"}', "PASS", "declared: dutch"),
        ("nothing declared", None, "FAIL", "skipped")]:
    got, text = step_1c(workdir("v-" + re.sub(r"\W+", "-", label), decl))
    ok(f"V: {label} -> {sev}, saying so", got == sev and needle in text, f"{got}: {text[:300]!r}")

print("\nARM S - a synthetic English source through the operator's path")
SRC_TEXT = ["The Parties shall use reasonable endeavours to organise the programme.",
            "This Agreement is governed by the laws of England.",
            "Signed on 15 April 2026."]
US_TEXT = ["The Parties shall use reasonable efforts to organize the program.",
           "This Agreement is governed by the laws of England.",
           "Signed on April 15, 2026."]
EN = SRC_TEXT if args.variant == "uk" else US_TEXT
w = workdir("s")
src = w / "orig.docx"
docx(src, "".join(p(r(t)) for t in SRC_TEXT))
rc, out = run("source_language_markers.py", "--declare", "english", w)
ok("S1: the mode is declared before anything reads the source", rc == 0, out)
rc, out = run("extract_paragraphs.py", src, w / "paragraphs.json")
notes = json.loads((w / "paragraphs.json").read_text(encoding="utf-8")) if rc == 0 else []
ok("S2: extract admits the English source and reads its three paragraphs",
   rc == 0 and [n["text"] for n in notes] == SRC_TEXT, out[-300:])
for n in notes:
    n["en"] = EN[SRC_TEXT.index(n["text"])]
(w / "paragraphs.json").write_text(json.dumps(notes, ensure_ascii=False, indent=1), encoding="utf-8")
(w / "final" / "word").mkdir(parents=True)
xml = w / "final" / "word" / "document.xml"
rc, out = run("apply_translations_textmatch.py", src, w / "paragraphs.json", xml)
ok("S3: apply exits 0", rc == 0 and xml.is_file(), out[-300:])
rc, out = run("post_process.py", xml, "--fix", "--variant", args.variant)
ok("S4: post_process exits 0", rc == 0, out[-300:])
dlv = w / "delivered.docx"
rc, out = run("repack_docx.py", src, xml, dlv, "--paragraphs", w / "paragraphs.json", "--variant", args.variant)
ok("S5: repack exits 0 and delivers", rc == 0 and dlv.is_file(), out[-300:])
PARA = re.compile(rb"<w:p[ >].*?</w:p>", re.S)
TEXT = re.compile(rb"<w:t(?:\s[^>]*)?>([^<]*)</w:t>")
if dlv.is_file():
    with zipfile.ZipFile(src) as z:
        sp = PARA.findall(z.read("word/document.xml"))
    with zipfile.ZipFile(dlv) as z:
        dp = PARA.findall(z.read("word/document.xml"))
    texts = [b"".join(TEXT.findall(x)).decode("utf-8") for x in dp]
    ok("S6: the delivered text is the declared English, paragraph for paragraph", texts == EN, str(texts))
    same = [i for i, (a, b) in enumerate(zip(SRC_TEXT, EN)) if a == b]
    ok(f"S7: where the English IS the source ({len(same)} of {len(EN)}), the delivered paragraph is the source's, "
       "byte for byte", len(sp) == len(dp) and all(sp[i] == dp[i] for i in same),
       f"source {len(sp)} paragraph(s), delivered {len(dp)}; differing: {[i for i in same if i < len(dp) and sp[i] != dp[i]]}")
got, text = step_1c(w)
ok("S8: the audit's Step 1c reads the mode on the run's own workdir", got == "PASS" and "variant-conversion" in text,
   f"{got}: {text[:200]!r}")

shutil.rmtree(TMP, ignore_errors=True)
print("\n" + "=" * 96)
print(f"  VARIANT CONVERSION: {CHECKED} check(s), {len(FAIL)} failure(s)   [{args.variant}]")
for f in FAIL:
    print(f"    FAIL  {f}")
print("=" * 96)
sys.exit(1 if FAIL else 0)
