# -*- coding: utf-8 -*-
"""STEP 14, SUB-STEP 14.9.5 (register C26) — SKILL STEP 3'S LEXICON READ LEAVES A RECEIPT, AND STEP 5 CHECKS IT.

C26: the mandatory end-to-end lexicon read left no trace, and 03 calls partial reading "the single most common
failure mode of this skill". No mechanism can prove a file was read rather than skimmed; Wouter's design
(DECISIONS-LOG.md, 2026-11-02 (7)) asks for something position-dependent the operator cannot predict: after the
read, `lexicon_compliance.py --read-receipt` names two random lines in each lexicon read, one in each half; the
operator copies each into `lexicon_read_receipt.json`; and apply's FIRST check, `--check-read-receipt`, refuses
to start without a match. It proves the files were opened at those lines, not that every line was read.

WHAT IS ASSERTED, per tree, through the tree's own scripts, on a synthetic Italian document:
  R  the receipt is issued: the file beside paragraphs.json, two lines a file, one in each half of the lines
     holding three letters or more, every quote empty, each file's hash its bytes', the lines printed; issued
     again, it is replaced;
  S  the set is policed at issue: no `references/general-legal.md`, no declared language's general sub-lexicon,
     a file outside the lexicons, one escaping the skill folder or one missing, each refused; English declared,
     or nothing, general-legal alone accepted;
  N  the draw: a fixed seed through the function reproduces it, the system source varies it, and no option in
     either script's help could set it;
  C  the check: no receipt, unquoted lines, a wrong quote (its line's text never printed), a neighbouring line,
     an edited line number, a lexicon changed or deleted (in a copy of the tree), another language declared and
     an unreadable receipt each refused, exit 1; right quotes accepted, whitespace runs aside, saying what it
     proves and no more;
  A  apply: refuses without a receipt and on a wrong quote, writing nothing, under the gate's banner; runs the
     check FIRST; with right quotes writes its output and prints the check's verdict; `--allow-bold-loss` does
     not skip it, and its help offers no option that could; a truncated `lexicon_compliance` reads as the install.

RED FIRST: against a tree exported from 285f83f (--tree), every behaviour fails - there is no receipt.

    uv run --with lxml python tests/test_read_receipt.py
    uv run --with lxml python tests/test_read_receipt.py --variant us
    uv run --with lxml python tests/test_read_receipt.py --tree <dir>      # RED: a whole exported tree

Synthetic only. No client text.
"""
import argparse
import hashlib
import importlib.util
import json
import os
import random
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.dont_write_bytecode = True
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tests"))
from make_fixtures import docx, p, r  # noqa: E402
import read_receipt as RR  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--variant", default="uk", choices=("uk", "us"))
ap.add_argument("--tree", default=None, help="another whole tree (scripts and lexicons), e.g. main's, for RED")
args = ap.parse_args()
TREE = Path(args.tree) if args.tree else ROOT / args.variant
SCRIPTS = TREE / "scripts"
ENV = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1", PYTHONDONTWRITEBYTECODE="1")
TMP = Path(tempfile.mkdtemp(prefix="b14-9-5-"))
FAIL, CHECKED = [], 0
GL, IT, PL = "references/general-legal.md", "sub-lexicons/italian-general-legal.md", "sub-lexicons/polish-general-legal.md"
SRC = ["Le parti convengono quanto segue.", "Il presente contratto è regolato dalla legge italiana."]
EN = ["The parties agree as follows.", "This agreement is governed by Italian law."]
GATE, INSTALL = "SKILL GATE FIRED", "FILE INTEGRITY — THE INSTALL IS TRUNCATED"
PROVES = "proves the files were opened at those lines, not that every line was read"


def ok(label, cond, detail=""):
    global CHECKED
    CHECKED += 1
    print(f"  {'ok  ' if cond else 'FAIL'} {label}" + ("" if cond else f"   {detail}"))
    if not cond:
        FAIL.append(label)


def run(script, *a, scripts=None):
    r_ = subprocess.run([sys.executable, str((scripts or SCRIPTS) / script), *map(str, a)], capture_output=True,
                        text=True, encoding="utf-8", errors="replace", env=ENV, timeout=600)
    return r_.returncode, (r_.stdout or "") + (r_.stderr or "")


def workdir(name, lang="italian", scripts=None):
    """A synthetic Italian document, declared at Step 1c, extracted and translated: (folder, source, notes)."""
    w = TMP / name
    w.mkdir(parents=True)
    src = w / "orig.docx"
    docx(src, "".join(p(r(t)) for t in SRC))
    if lang:
        run("source_language_markers.py", "--declare", lang, w, scripts=scripts)
    nj = w / "paragraphs.json"
    run("extract_paragraphs.py", src, nj, scripts=scripts)
    notes = json.loads(nj.read_text(encoding="utf-8")) if nj.is_file() else []
    for n in notes:
        if n.get("text") in SRC:
            n["en"] = EN[SRC.index(n["text"])]
    nj.write_bytes(json.dumps(notes, ensure_ascii=False, indent=1).encode("utf-8"))
    return w, src, nj


def receipt(w):
    rp = w / RR.RECEIPT
    try:
        return json.loads(rp.read_bytes().decode("utf-8"))
    except (OSError, ValueError):
        return None


def write_receipt(w, data):
    (w / RR.RECEIPT).write_bytes(json.dumps(data, ensure_ascii=False, indent=1).encode("utf-8"))


def content_lines(lines):
    """Lines holding three letters or more, 1-based - computed here, independently of the script."""
    return [i + 1 for i, s in enumerate(lines) if sum(c.isalpha() for c in s) >= 3]


def apply(w, src, nj, *extra, scripts=None):
    out = w / "final" / "word" / "document.xml"
    out.unlink(missing_ok=True)  # an earlier run's output must never read as this run's
    rc, text = run("apply_translations_textmatch.py", src, nj, out, *extra, scripts=scripts)
    return rc, text, out.is_file()


# ============================================================================================================ R
print(f"R — the receipt is issued   [{args.variant}{', tree ' + str(TREE) if args.tree else ''}]")
w, src, nj = workdir("r")
rc, out = RR.issue(nj, TREE, [GL, IT])
data = receipt(w)
ok("R1: --read-receipt exits 0 and writes lexicon_read_receipt.json beside paragraphs.json",
   rc == 0 and data is not None, f"exit {rc}: {out.strip()[-300:]}")
lines = (data or {}).get("lines") or []
per = {f: [e["line"] for e in lines if e.get("file") == f] for f in (GL, IT)}
ok("R2: two lines named in each file read, four in all, each quote empty",
   len(lines) == 4 and all(len(v) == 2 for v in per.values()) and all(e.get("quote") == "" for e in lines),
   f"{per}")
halves_ok = letters_ok = bool(lines)
for f, named in per.items():
    text = RR.lines_of(TREE / f)
    c = content_lines(text)
    h = len(c) // 2
    halves_ok &= len(named) == 2 and named[0] in c[:h] and named[1] in c[h:]
    letters_ok &= all(1 <= n <= len(text) and sum(ch.isalpha() for ch in text[n - 1]) >= 3 for n in named)
ok("R3: in each file the first line lies in the first half of its lines with three letters, the second in the second",
   halves_ok, f"{per}")
ok("R4: every named line holds three letters or more", letters_ok, f"{per}")
ok("R5: each file's recorded hash is the SHA-256 of its bytes",
   (data or {}).get("files") == {f: hashlib.sha256((TREE / f).read_bytes()).hexdigest() for f in (GL, IT)},
   str((data or {}).get("files"))[:200])
ok("R6: the output names every file and line to quote, and what the receipt proves",
   all(f"{e['file']}  line {e['line']}" in out for e in lines) and PROVES in out and bool(lines), out[-400:])
before = (w / RR.RECEIPT).read_bytes() if data else b""
rc2, _o = RR.issue(nj, TREE, [GL, IT])
ok("R7: issuing again replaces the receipt", rc2 == 0 and receipt(w) is not None
   and (w / RR.RECEIPT).read_bytes() != before, f"exit {rc2}")

# ============================================================================================================ S
print("\nS — the set is policed at issue")
for label, files, why in (("S1: a set without references/general-legal.md", [IT], "general-legal.md"),
                          ("S2: Italian declared, a set without italian-general-legal.md", [GL], "italian-general-legal"),
                          ("S3: a file outside the lexicons", [GL, IT, "scripts/apply_translations_textmatch.py"],
                           "apply_translations_textmatch"),
                          ("S4: a path escaping the skill folder", [GL, IT, "references/../../README.md"], "README"),
                          ("S5: a lexicon the skill does not have", [GL, IT, "references/no-such-lexicon.md"],
                           "no-such-lexicon")):
    ws, _s, njs = workdir("s" + label[1])
    rc, out = RR.issue(njs, TREE, files)
    ok(f"{label} is refused, exit 1, naming it, and no receipt is written",
       rc == 1 and why in out and receipt(ws) is None, f"exit {rc}: {out.strip()[-300:]}")
for label, lang in (("S6: English declared (the variant-conversion mode)", "english"), ("S7: nothing declared", None)):
    ws, _s, njs = workdir("s" + label[1], lang=lang)
    rc, out = RR.issue(njs, TREE, [GL])
    ok(f"{label}: general-legal.md alone is accepted", rc == 0 and receipt(ws) is not None, f"exit {rc}: {out[-300:]}")

# ============================================================================================================ N
print("\nN — the draw")
draws = []
try:
    spec = importlib.util.spec_from_file_location(f"lc_{args.variant}_{id(TREE)}", SCRIPTS / "lexicon_compliance.py")
    LC = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(SCRIPTS))
    spec.loader.exec_module(LC)
    wn, _s, njn = workdir("n")
    for _ in range(2):
        LC.issue_read_receipt(str(njn), [GL, IT], rng=random.Random(7))
        draws.append([(e["file"], e["line"]) for e in receipt(wn)["lines"]])
except Exception as exc:  # the RED tree has no such function
    draws.append(f"{type(exc).__name__}: {exc}")
ok("N1: a fixed seed, passed to the function by a test, draws the same lines twice",
   len(draws) == 2 and draws[0] == draws[1] and isinstance(draws[0], list) and len(draws[0]) == 4, str(draws)[:300])
seen, drawn = set(), []
wv, _s, njv = workdir("v")
for _ in range(12):
    rc, _o = RR.issue(njv, TREE, [GL, IT])
    drawn.append([(e["file"], e["line"]) for e in (receipt(wv) or {}).get("lines", [])])
    seen.add(tuple(drawn[-1]))
ok("N2: the system's random source varies the draw (12 issues, more than one set of lines)",
   len(seen) > 1 and () not in seen, f"{len(seen)} distinct")
# R3 and R4 asked of ONE draw; asked of all twelve, 48 lines, a rule broken by chance cannot pass by chance.
cl = {f: content_lines(RR.lines_of(TREE / f)) for f in (GL, IT)}
held = all(len(d) == 4 and all([n for g, n in d if g == f][0] in cl[f][:len(cl[f]) // 2]
                                and [n for g, n in d if g == f][1] in cl[f][len(cl[f]) // 2:] for f in (GL, IT))
           for d in drawn)
ok("N4: across the 12 issues every line drawn holds three letters, the first of each file in its first half, the "
   "second in its second", bool(drawn) and held, str(drawn[:2])[:200])
_rc, help_lc = run("lexicon_compliance.py", "--help")
_rc, help_ap = run("apply_translations_textmatch.py", "--help")
ok("N3: neither script's help offers an option that could set the draw",
   "seed" not in help_lc.lower() and "seed" not in help_ap.lower() and "--read-receipt" in help_lc,
   help_lc[-300:])

# ============================================================================================================ C
print("\nC — the check")


def check(w, nj, scripts=None):
    return run("lexicon_compliance.py", nj, "--check-read-receipt", scripts=scripts)


wc, srcc, njc = workdir("c")
rc, out = check(wc, njc)
ok("C1: no receipt is refused, exit 1, naming the receipt and the command that issues it",
   rc == 1 and RR.RECEIPT in out and "--read-receipt" in out, f"exit {rc}: {out[-300:]}")
RR.issue(njc, TREE, [GL, IT])
rc, out = check(wc, njc)
ok("C2: a receipt with its lines unquoted is refused, exit 1, naming each line", rc == 1 and receipt(wc) is not None
   and all(f"line {e['line']}" in out for e in (receipt(wc) or {}).get("lines", [])), f"exit {rc}: {out[-300:]}")
if receipt(wc) is not None:  # the RED tree writes none
    RR.quote_all(njc, TREE)
good = receipt(wc)
rc, out = check(wc, njc)
ok("C3: right quotes are accepted, exit 0, saying what the receipt proves and no more",
   rc == 0 and PROVES in out and "every line was read" not in out.replace(PROVES, ""), f"exit {rc}: {out[-300:]}")
if good:
    loose = json.loads(json.dumps(good))
    for e in loose["lines"]:
        e["quote"] = "  " + "   ".join(e["quote"].split()) + "  "
    write_receipt(wc, loose)
rc, out = check(wc, njc)
ok("C4: a quote differing only in runs of whitespace is accepted", rc == 0, f"exit {rc}: {out[-300:]}")
if good:
    bad = json.loads(json.dumps(good))
    true_line = bad["lines"][1]["quote"]
    bad["lines"][1]["quote"] = "The parties agree as follows."
    write_receipt(wc, bad)
else:
    true_line = ""
rc, out = check(wc, njc)
named = (good or {"lines": [{}, {"file": "?", "line": "?"}]})["lines"][1]
ok("C5: a wrong quote is refused, exit 1, naming its file and line",
   rc == 1 and f"{named['file']} line {named['line']}" in out, f"exit {rc}: {out[-300:]}")
ok("C6: ...and the line's own text is never printed", bool(true_line) and true_line.strip() not in out,
   "the expected text was printed")
if good:
    nb = json.loads(json.dumps(good))
    e = nb["lines"][0]
    text = RR.lines_of(TREE / e["file"])
    other = next(i for i in content_lines(text) if text[i - 1].strip() != text[e["line"] - 1].strip())
    e["quote"] = text[other - 1]
    write_receipt(wc, nb)
rc, out = check(wc, njc)
ok("C7: a quote of another line of the same file is refused", rc == 1, f"exit {rc}")
if good:
    ed = json.loads(json.dumps(good))
    ed["lines"][0]["line"] = 1
    ed["lines"][0]["quote"] = RR.lines_of(TREE / ed["lines"][0]["file"])[0]
    write_receipt(wc, ed)
rc, out = check(wc, njc)
ok("C8: a line number edited after issue is refused, exit 1, saying to issue it again",
   rc == 1 and "--read-receipt" in out, f"exit {rc}: {out[-300:]}")
(wc / RR.RECEIPT).write_bytes(b"{not json")
rc, out = check(wc, njc)
ok("C9: an unreadable receipt is refused, exit 1", rc == 1, f"exit {rc}: {out[-300:]}")
if good:
    write_receipt(wc, good)
run("source_language_markers.py", "--declare", "polish", wc)
rc, out = check(wc, njc)
ok("C10: another language declared after issue is refused, exit 1, naming its general sub-lexicon",
   rc == 1 and "polish-general-legal.md" in out, f"exit {rc}: {out[-300:]}")
run("source_language_markers.py", "--declare", "italian", wc)
rc, out = check(wc, njc)
ok("C11: declared back, the same receipt matches again", rc == 0, f"exit {rc}: {out[-300:]}")

# A COPY OF THE TREE, never the tree: a lexicon changed and a lexicon deleted after issue.
COPY = TMP / "tree"
shutil.copytree(TREE, COPY, ignore=shutil.ignore_patterns("__pycache__"))
wt, _s, njt = workdir("t", scripts=COPY / "scripts")
RR.file_receipt(njt, COPY, [GL, IT]) if RR.has_receipt(COPY) else None
rc0, _o = check(wt, njt, scripts=COPY / "scripts")
lex = COPY / IT
lex.write_bytes(lex.read_bytes() + b"\n| invented | row |\n")
rc, out = check(wt, njt, scripts=COPY / "scripts")
ok("C12: a lexicon changed after issue is refused, exit 1, naming it as changed",
   rc0 == 0 and rc == 1 and IT in out and "changed" in out, f"before {rc0}, after {rc}: {out[-300:]}")
(COPY / GL).unlink()
rc, out = check(wt, njt, scripts=COPY / "scripts")
ok("C13: a lexicon deleted after issue is refused, exit 1, naming it", rc == 1 and GL in out, f"exit {rc}: {out[-300:]}")

# ============================================================================================================ A
print("\nA — apply")
wa, srca, nja = workdir("a")
rc, out, wrote = apply(wa, srca, nja)
ok("A1: apply without a receipt exits 1 under the gate's banner, naming the read receipt, writing nothing",
   rc == 1 and GATE in out and "--check-read-receipt" in out and RR.RECEIPT in out and not wrote,
   f"exit {rc}, wrote {wrote}: {out[-400:]}")
rc, out, wrote = apply(wa, srca, nja, "--allow-bold-loss")
ok("A2: --allow-bold-loss does not skip it", rc == 1 and GATE in out and not wrote, f"exit {rc}, wrote {wrote}")
opts = set(re.findall(r"(?<![\w-])--[a-z][a-z-]+", help_ap))
ok("A3: apply's help offers no option but --allow-bold-loss, so none could skip it",
   opts == {"--help", "--allow-bold-loss"}, str(sorted(opts)))
RR.issue(nja, TREE, [GL, IT])
gw = receipt(wa)
if gw:  # every line quoted, then ONE quote wrong - so the refusal can only be for that quote
    RR.quote_all(nja, TREE)
    gw = receipt(wa)
    gw["lines"][0]["quote"] = "The parties agree as follows."
    write_receipt(wa, gw)
rc, out, wrote = apply(wa, srca, nja)
ok("A4: apply on a wrong quote exits 1 under the gate's banner, writing nothing", rc == 1 and GATE in out
   and not wrote, f"exit {rc}, wrote {wrote}: {out[-300:]}")
RR.quote_all(nja, TREE) if gw else None
rc, out, wrote = apply(wa, srca, nja)
i_rr, i_en = out.find("auto-running lexicon_compliance.py --check-read-receipt"), out.find("auto-running validate_en_runs")
ok("A5: with right quotes apply exits 0, writes its output and prints the check's verdict",
   rc == 0 and wrote and PROVES in out, f"exit {rc}, wrote {wrote}: {out[-300:]}")
ok("A6: the receipt is apply's FIRST check, before validate_en_runs", 0 <= i_rr < i_en, f"{i_rr}, {i_en}")
run("source_language_markers.py", "--declare", "polish", wa)
rc, out, wrote = apply(wa, srca, nja)
ok("A7: another language declared after the receipt, apply refuses", rc == 1 and GATE in out and PL in out,
   f"exit {rc}: {out[-300:]}")
# A truncated lexicon_compliance in a fresh copy of the tree: the install's banner, never the gate's.
CUT = TMP / "cut"
shutil.copytree(TREE, CUT, ignore=shutil.ignore_patterns("__pycache__"))
lc = CUT / "scripts" / "lexicon_compliance.py"
body = lc.read_bytes()  # cut before the closing sentinel, as an install cuts a file: the check's own literal stays
lc.write_bytes(body[:body.rindex(b"# === SKILL FILE COMPLETE ===")])
wx, srcx, njx = workdir("x", scripts=CUT / "scripts")
rc, out, wrote = apply(wx, srcx, njx, scripts=CUT / "scripts")
ok("A8: a truncated lexicon_compliance reads as a truncated install, not as a gate",
   rc == 1 and INSTALL in out and GATE not in out and not wrote, f"exit {rc}: {out[-300:]}")

shutil.rmtree(TMP, ignore_errors=True)
print("\n" + "=" * 96)
print(f"  READ RECEIPT: {CHECKED} check(s), {len(FAIL)} failure(s)   [{args.variant}]")
for f in FAIL:
    print(f"    FAIL  {f}")
print("=" * 96)
sys.exit(1 if FAIL else 0)
