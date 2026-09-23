# -*- coding: utf-8 -*-
"""BRANCH 10 SLICE 3b — does a mandatory rewrite still overrule the LEXICON?

Register rows B5, B6(a) and F29 are one defect three times: `post_process` overwrote a
string that a lexicon in the skill tells the operator to write, and the drift gate then
blocked the operator with an error naming neither cause. The fix is ONE mechanism -- the
declared `LEXICON_SANCTIONED` table in post_process.py -- and `translate_numbering.py`
following the operator's attachment label so the two scripts cannot disagree on a page.

WHAT THIS SUITE PROVES, AND WHY THE FIRST TWO ARMS ARE THE ONES THAT MATTER MOST. The table
is declared rather than parsed from the lexicons at runtime (Wouter, 2026-09-23), so the
lexicon stays the authority ONLY IF something forbids the two from disagreeing. That is
arms 1 and 2, and both carry a positive control, because a coverage check that has never
gone red is not known to be able to:

  ARM 1  COVERAGE — every rewrite rule's left-hand side that a lexicon's ENGLISH column
         presents as a rendering is shielded by the table, or is a DECLARED exception.
  ARM 2  CITATIONS — every table entry's quote is still in the file it cites, in BOTH
         trees, and still shields at least one rule. A stale entry is a shield for nothing.
  ARM 3  THE EXCEPTIONS HOLD — each is under Avoid in a REFERENCE lexicon and in
         quality_check's violation list, which is the claim that three authorities agree.
  ARM 4  BEHAVIOUR, through the real script in a real workdir: sanctioned strings survive,
         unsanctioned rewrites still fire, the reasons are reported, the journal agrees.
  ARM 5  translate_numbering FOLLOWS THE OPERATOR, in every case, and never blocks.
  ARM 6  BOTH TREES carry the same blocks, and the two exclusion lists agree.

Every input is synthetic and built in a temporary directory. Nothing is written into
tests/fixtures/ or into either tree.

    uv run --with lxml python tests/test_lexicon_choice.py
    uv run --with lxml python tests/test_lexicon_choice.py --variant us
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
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"

from lxml import etree  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
ap = argparse.ArgumentParser()
ap.add_argument("--variant", default="uk", choices=("uk", "us"))
args = ap.parse_args()
TREES = ("uk", "us")
ENV = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1", PYTHONDONTWRITEBYTECODE="1")
TMP = Path(tempfile.mkdtemp(prefix="lexchoice-"))
FAIL, VOIDED, CHECKED = [], [], 0


def ok(label, cond, detail=""):
    global CHECKED
    CHECKED += 1
    print(("  OK   " if cond else "  XX   ") + label
          + (f"   {detail}" if detail and not cond else ""))
    if not cond:
        FAIL.append(f"{label} {detail}".strip())
    return cond


def void(label, why):
    VOIDED.append(f"{label}: {why}")
    print(f"  ??   {label}   VOID — {why}")


def load(tree, name):
    """Import a shipped script BY PATH, with bytecode writing off -- a .pyc beside a shipped
    source embeds an absolute path, which is a username."""
    spec = importlib.util.spec_from_file_location(f"{tree}_{name}",
                                                  ROOT / tree / "scripts" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    saved = sys.argv
    sys.argv = [name]
    try:
        spec.loader.exec_module(mod)
    finally:
        sys.argv = saved
    return mod


PP = {t: load(t, "post_process") for t in TREES}
TN = {t: load(t, "translate_numbering") for t in TREES}
QC = {t: load(t, "quality_check") for t in TREES}


# =========================================================================================
# THE LEXICON READER — table rows only, cells mapped to their header. An ENGLISH column is
# one whose header names English or Correct and does not name Avoid: that is where a lexicon
# tells the operator what to WRITE. Prose lines and description columns (usage, notes,
# context) are not read, because a mention is not an instruction.
# =========================================================================================
def lexicon_files(tree_root):
    return sorted([*(tree_root / "references").glob("*.md"),
                   *(tree_root / "sub-lexicons").glob("*.md")])


def table_cells(path):
    """Yield (line_no, header_cell, cell_text) for every data cell of every table."""
    lines = path.read_bytes().decode("utf-8").splitlines()
    header = None
    for i, ln in enumerate(lines):
        s = ln.strip()
        if not s.startswith("|"):
            header = None
            continue
        if re.match(r"^\|\s*:?-{2,}", s):
            continue
        cells = [c.strip() for c in s.strip("|").split("|")]
        nxt = lines[i + 1].strip() if i + 1 < len(lines) else ""
        if re.match(r"^\|\s*:?-{2,}", nxt):
            header = cells
            continue
        if header is None:
            continue
        for k, c in enumerate(cells):
            h = header[k] if k < len(header) else ""
            yield i + 1, h, c


def is_english(h):
    return bool(re.search(r"english|correct", h, re.I)) and not re.search(r"avoid", h, re.I)


def is_avoid(h):
    return bool(re.search(r"avoid", h, re.I))


def rules_of(pp):
    """(label, compiled) for every rewrite the two passes make, CASE-SENSITIVE as they are.
    Built from the script's own tables, never retyped."""
    out = []
    for old, _new, is_regex in pp.TERM_REPLACEMENTS:
        out.append((old, re.compile(old if is_regex else re.escape(old))))
    for pat, _rep in pp.TERM_REGEX_REPLACEMENTS:
        out.append((pat, re.compile(pat)))
    for pat in (r"\bAnnex\b", r"\bANNEX\b", r"\bAnnexes\b"):
        out.append((pat, re.compile(pat)))
    return out


def shielded(sanctioned_res, text, m):
    return any(s.start() < m.end() and m.start() < s.end()
               for crx in sanctioned_res for s in crx.finditer(text))


# THE DECLARED EXCEPTIONS, each with the REFERENCE lexicon's Avoid cell that makes it one.
# A string a sub-lexicon offers and the reference lexicon lists under Avoid is a
# contradiction INSIDE the lexicons; post_process agreeing with the reference is not the
# defect, and quality_check agrees too (arm 3 asserts both).
NOT_SANCTIONED = {
    "credit line": ("references/finance-banking.md", '"credit line" (acceptable'),
    "election of domicile": ("references/general-legal.md", '"election of domicile"'),
}


def uncovered(tree_root, pp, sanctioned_res, stats=None):
    """Every English-column occurrence of a rule's left-hand side that nothing shields and
    no exception declares. The shape a RED run reports, and the thing arm 1's control plants.

    `stats`, when given, is filled with the DENOMINATOR -- English cells read, rule matches
    found, how many were shielded and how many excepted -- because a clean result over zero
    cells reads exactly like a clean result over thousands."""
    out = []
    rules = rules_of(pp)
    st = {"cells": 0, "matches": 0, "shielded": 0, "excepted": 0}
    for f in lexicon_files(tree_root):
        for line_no, h, cell in table_cells(f):
            if not is_english(h):
                continue
            st["cells"] += 1
            for label, rx in rules:
                for m in rx.finditer(cell):
                    st["matches"] += 1
                    if shielded(sanctioned_res, cell, m):
                        st["shielded"] += 1
                        continue
                    key = " ".join(m.group(0).lower().split())
                    if key in NOT_SANCTIONED:
                        st["excepted"] += 1
                        continue
                    out.append(f"{f.relative_to(tree_root).as_posix()}:{line_no} "
                               f"rule {label!r} matched {m.group(0)!r}")
    if stats is not None:
        stats.update(st)
    return out


def stale_citations(tree_root, pp, table):
    """Entries whose fragment no longer locates a row in the cited file, whose pattern no
    longer matches THE ROW the fragment locates, or which shield NO rule on that row -- a
    shield for nothing.

    THE FRAGMENT LOCATES; THE ROW IS WHAT IS CHECKED. The table carries a short fragment
    rather than the name itself, because a name quoted in full is three capitalised words
    and the pre-commit gate's personal-name shape read three of them as people. So the whole
    LINE the fragment sits on is read here, and every condition is asserted against it."""
    out = []
    rules = rules_of(pp)
    for label, pat, rel, quote in table:
        f = tree_root / rel
        if not f.is_file():
            out.append(f"{label}: cited file {rel} does not exist")
            continue
        rows = [ln for ln in f.read_bytes().decode("utf-8").splitlines() if quote in ln]
        if not rows:
            out.append(f"{label}: quote not found in {rel}")
            continue
        crx = re.compile(pat, re.IGNORECASE)
        live = [ln for ln in rows if crx.search(ln)]
        if not live:
            out.append(f"{label}: its own pattern does not match the row its quote locates")
            continue
        if not any(shielded([crx], ln, m) for ln in live
                   for _l, rx in rules for m in rx.finditer(ln)):
            out.append(f"{label}: shields no rewrite rule on the row its quote locates")
    return out


# =========================================================================================
# ARM 1 — COVERAGE, over both trees, with a positive control planted in a COPY.
# =========================================================================================
print(f"ARM 1 — every lexicon-sanctioned rewrite is shielded or declared   [{args.variant}]")
# A TREE WITHOUT THE TABLE IS A FAILURE NAMED AS SUCH, NEVER A CRASH. The red-first harness
# runs this suite against the code BEFORE this slice, and a traceback there would hide every
# behaviour arm below it -- the arms that most need to be seen going red.
HAS_TABLE = {t: hasattr(PP[t], "LEXICON_SANCTIONED") and hasattr(PP[t], "_LEXICON_SANCTIONED_RE")
             for t in TREES}
for t in TREES:
    ok(f"{t}: post_process carries the LEXICON_SANCTIONED table", HAS_TABLE[t])
for t in TREES:
    pp = PP[t]
    if not HAS_TABLE[t]:
        continue
    n_files = len(lexicon_files(ROOT / t))
    ok(f"{t}: the lexicons were READ ({n_files} files) — a coverage check over nothing is "
       f"VOID, never clean", n_files > 100, f"only {n_files}")
    st = {}
    bad = uncovered(ROOT / t, pp, pp._LEXICON_SANCTIONED_RE, st)
    print(f"       {t}: {st['cells']} English cell(s) read, {st['matches']} rule match(es) "
          f"found — {st['shielded']} shielded, {st['excepted']} declared exceptions, "
          f"{len(bad)} uncovered")
    ok(f"{t}: the reader reached real cells and found real matches — zero of either would "
       f"make the next row a clean zero over nothing",
       st["cells"] > 1000 and st["shielded"] > 0 and st["excepted"] > 0, repr(st))
    ok(f"{t}: no rewrite rule overwrites a string a lexicon's English column sanctions, "
       f"unless it is a declared exception", not bad, "; ".join(bad[:4]))

# THE CONTROL. A copy of one sub-lexicon gains a row whose English column is a string a
# rule rewrites and nothing shields. The same function must now name it.
ctl_root = TMP / "ctl-tree"
shutil.copytree(ROOT / args.variant / "references", ctl_root / "references")
shutil.copytree(ROOT / args.variant / "sub-lexicons", ctl_root / "sub-lexicons")
planted = ctl_root / "sub-lexicons" / "italian-finance-banking.md"
planted.write_bytes(planted.read_bytes()
                    + "\n\n| Italian | English |\n|---|---|\n"
                      "| contratto di finanziamento | Financing Agreement |\n".encode("utf-8"))
if HAS_TABLE[args.variant]:
    bad_ctl = uncovered(ctl_root, PP[args.variant], PP[args.variant]._LEXICON_SANCTIONED_RE)
    ok("CONTROL: a planted lexicon row sanctioning a rewritten string is REPORTED",
       any("Financing Agreement" in b for b in bad_ctl), f"reported: {bad_ctl[:3]}")
else:
    void("coverage CONTROL", f"{args.variant} has no table to test the control against")

# =========================================================================================
# ARM 2 — CITATIONS, over both trees, with a positive control on a corrupted copy of the table.
# =========================================================================================
print("\nARM 2 — every table entry still cites a row that says what it claims")
for t in TREES:
    pp = PP[t]
    if not HAS_TABLE[t]:
        continue
    ok(f"{t}: the table is not empty ({len(pp.LEXICON_SANCTIONED)} entries)",
       len(pp.LEXICON_SANCTIONED) >= 1)
    stale = stale_citations(ROOT / t, pp, pp.LEXICON_SANCTIONED)
    ok(f"{t}: every entry's quote is in its cited file and shields a rule", not stale,
       "; ".join(stale))
if HAS_TABLE[args.variant]:
    corrupt = [(l, p, f, q + " (altered)") if i == 0 else (l, p, f, q)
               for i, (l, p, f, q) in enumerate(PP[args.variant].LEXICON_SANCTIONED)]
    st_ctl = stale_citations(ROOT / args.variant, PP[args.variant], corrupt)
    ok("CONTROL: an entry whose quote no longer matches its row is REPORTED",
       len(st_ctl) == 1 and "quote not found" in st_ctl[0], f"reported: {st_ctl}")
else:
    void("citation CONTROL", f"{args.variant} has no table to test the control against")

# =========================================================================================
# ARM 3 — THE EXCEPTIONS ARE WHAT THEY CLAIM: under Avoid in a REFERENCE lexicon, and in
# quality_check's violation list, in both trees.
# =========================================================================================
print("\nARM 3 — each declared exception is one three authorities agree on")
for t in TREES:
    for phrase, (rel, quote) in NOT_SANCTIONED.items():
        f = ROOT / t / rel
        in_avoid = f.is_file() and any(
            quote in cell for _n, h, cell in table_cells(f) if is_avoid(h))
        ok(f"{t}: {phrase!r} is under Avoid in {rel}", in_avoid)
        ok(f"{t}: {phrase!r} is in quality_check's TERM_VIOLATIONS",
           phrase in QC[t].TERM_VIOLATIONS)

# =========================================================================================
# ARM 4 — BEHAVIOUR, through the real script in the conventional workdir layout.
# =========================================================================================
print(f"\nARM 4 — the passes keep what the lexicon sanctions and still fix the rest   "
      f"[{args.variant}]")
KEPT = [
    ["KEPT — The milestones are set out in Annex 1 and Annex 2."],
    ["KEPT — BANKING TRANSPARENCY"],
    ["KEPT — The registration and publicity formalities are complete."],
    ["KEPT — Interest accrues at the Secured Overnight ", "Financing Rate plus the margin."],
    ["KEPT — The Credit Support Annex governs the collateral."],
]
CONTROL = [
    (["CONTROL — The Financing Agreement is signed today."],
     "CONTROL — The Facility Agreement is signed today."),
    (["CONTROL — Each credit line remains available."],
     "CONTROL — Each credit facility remains available."),
]


def build_doc():
    body = []
    for frags in KEPT + [c[0] for c in CONTROL]:
        body.append("<w:p>" + "".join(
            f'<w:r><w:t xml:space="preserve">{fr}</w:t></w:r>' for fr in frags) + "</w:p>")
    return ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
            f'<w:document xmlns:w="{W}"><w:body>' + "".join(body)
            + "</w:body></w:document>").encode("utf-8")


def para_texts(xml_bytes):
    root = etree.fromstring(xml_bytes)
    return ["".join(t.text or "" for t in p.iter(f"{{{W}}}t")) for p in root.iter(f"{{{W}}}p")]


def run_pp(name, with_notes):
    wd = TMP / name
    (wd / "final" / "word").mkdir(parents=True)
    x = wd / "final" / "word" / "document.xml"
    x.write_bytes(build_doc())
    if with_notes:
        # `text` is a stand-in SOURCE string, distinct from `en`, so the detector's
        # "declared" reason is reachable -- the shipped fixture cannot reach it, its `text`
        # having to equal its own document. The CONTROL rows declare the English AFTER the
        # rewrite, which is what an operator who has seen the gate would write; declaring
        # the pre-rewrite text would fire the drift gate, which arm 8 of
        # tests/test_change_journal.py already owns.
        notes = []
        for i, frags in enumerate(KEPT):
            en = "".join(frags)
            notes.append({"idx": i, "text": "[source] " + en, "en": en, "style": "Normal"})
        for j, (_frags, after) in enumerate(CONTROL):
            notes.append({"idx": len(KEPT) + j, "text": "[source] " + after, "en": after,
                          "style": "Normal"})
        (wd / "paragraphs.json").write_bytes(
            (json.dumps(notes, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    r = subprocess.run(["uv", "run", "--with", "lxml", "python",
                        str(ROOT / args.variant / "scripts" / "post_process.py"), str(x),
                        "--fix", "--variant", args.variant],
                       capture_output=True, text=True, encoding="utf-8", errors="replace",
                       cwd=str(ROOT), env=ENV, timeout=600)
    j = wd / "post_process_journal.json"
    return r, para_texts(x.read_bytes()), (json.loads(j.read_text(encoding="utf-8"))
                                           if j.is_file() else None)


for mode, with_notes, reason in (("declared", True, "declared"),
                                 ("no-notes", False, "no notes")):
    r, after, jr = run_pp(f"pp-{mode}", with_notes)
    ok(f"[{mode}] post_process exits 0", r.returncode == 0,
       f"rc={r.returncode} {(r.stderr or r.stdout or '')[-240:]}")
    for i, frags in enumerate(KEPT):
        ok(f"[{mode}] kept row {i} survives exactly as written",
           i < len(after) and after[i] == "".join(frags),
           f"now {after[i] if i < len(after) else None!r}")
    for j, (frags, want) in enumerate(CONTROL):
        k = len(KEPT) + j
        ok(f"[{mode}] control row {j} is STILL rewritten — no lexicon sanctions it",
           k < len(after) and after[k] == want, f"now {after[k] if k < len(after) else None!r}")
    out = r.stdout or ""
    ok(f"[{mode}] the terminology detector line names the reason `{reason}`",
       re.search(r"\[detector\] terminology left \d+ lexicon-sanctioned.*" + re.escape(reason),
                 out) is not None, out[-400:])
    ok(f"[{mode}] the Annex detector line names the reason `{reason}`",
       re.search(r"\[detector\] annex_to_schedule left 3 lexicon-sanctioned.*"
                 + re.escape(reason), out) is not None, out[-400:])
    if jr is None:
        void(f"[{mode}] journal", "no journal was written")
        continue
    st = next(s for s in jr["stages"] if s["stage"] == "passes")
    edited = {e["para"] for e in st["edits"] if e["pass"] in ("terminology",
                                                              "annex_to_schedule")}
    ok(f"[{mode}] the journal records terminology edits on the CONTROL rows and nowhere else",
       edited == {len(KEPT), len(KEPT) + 1}, f"edited paragraphs {sorted(edited)}")
    ok(f"[{mode}] and no edit at all by the Annex pass",
       not any(e["pass"] == "annex_to_schedule" for e in st["edits"]))

# =========================================================================================
# ARM 5 — translate_numbering: the attachment label follows the declared English.
# =========================================================================================
print(f"\nARM 5 — an auto-numbered attachment label follows the operator   [{args.variant}]")
NUMBERING = (f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
             f'<w:numbering xmlns:w="{W}"><w:abstractNum w:abstractNumId="0">'
             f'<w:lvl w:ilvl="0"><w:lvlText w:val="Allegato %1"/></w:lvl>'
             f'<w:lvl w:ilvl="1"><w:lvlText w:val="%2."/></w:lvl>'
             f'</w:abstractNum><w:num w:numId="1"><w:abstractNumId w:val="0"/></w:num>'
             f'</w:numbering>')


def run_tn(name, en_lines, custom=None, explicit=False):
    wd = TMP / f"tn-{name}"
    (wd / "final" / "word").mkdir(parents=True)
    src = wd / "source.docx"
    with zipfile.ZipFile(src, "w") as z:
        z.writestr("word/numbering.xml", NUMBERING)
    notes_at = wd / ("elsewhere.json" if explicit else "paragraphs.json")
    if en_lines is not None:
        notes_at.write_bytes(json.dumps([{"idx": i, "text": "x", "en": e}
                                         for i, e in enumerate(en_lines)]).encode("utf-8"))
    cmd = ["uv", "run", "python", str(ROOT / args.variant / "scripts" /
                                      "translate_numbering.py"),
           str(src), str(wd / "final" / "word" / "numbering.xml"), "--language", "italian"]
    if custom is not None:
        cj = wd / "custom.json"
        cj.write_bytes(json.dumps(custom).encode("utf-8"))
        cmd += ["--custom", str(cj)]
    if explicit:
        cmd += ["--paragraphs", str(notes_at)]
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                       errors="replace", cwd=str(ROOT), env=ENV, timeout=300)
    out_xml = wd / "final" / "word" / "numbering.xml"
    vals = re.findall(r'w:lvlText w:val="([^"]*)"',
                      out_xml.read_text(encoding="utf-8")) if out_xml.is_file() else []
    return r, vals


CASES = [
    ("annex", ["The goods are listed in Annex 1.", "See Annexes 2 and 3."], None, False,
     "Annex %1", "2 Annex label"),
    ("schedule", ["The goods are listed in Schedule 1."], None, False, "Schedule %1",
     "Schedule label(s) declared"),
    ("mixed", ["Annex 1 applies.", "Schedule 2 applies."], None, False, "Schedule %1",
     "MIXED"),
    ("no-notes", None, None, False, "Schedule %1", "no notes"),
    ("legislation-only", ["Annex III of the Directive applies."], None, False, "Schedule %1",
     "no attachment label declared"),
    ("custom-wins", ["See Annex 1."], {r"allegato\s*%(\d+)": r"Exhibit %\1"}, False,
     "Exhibit %1", "Annex label"),
    ("explicit-path", ["See Annex A."], None, True, "Annex %1", "Annex label"),
]
for name, en, custom, explicit, want, said in CASES:
    r, vals = run_tn(name, en, custom, explicit)
    ok(f"[{name}] exits 0 — this script cannot block a run, and B1.mute asserts it",
       r.returncode == 0, f"rc={r.returncode} {(r.stderr or '')[-200:]}")
    ok(f"[{name}] the label is {want!r}", want in vals, f"got {vals}")
    ok(f"[{name}] the non-attachment level is untouched", "%2." in vals, f"got {vals}")
    ok(f"[{name}] and the run SAYS why ({said!r})", said in (r.stdout or ""),
       (r.stdout or "")[-300:])

# =========================================================================================
# ARM 6 — BOTH TREES, and the one list the two scripts must share.
# =========================================================================================
print("\nARM 6 — both trees carry the same blocks, and the exclusion lists agree")


def block(path, open_, close):
    s = path.read_text(encoding="utf-8")
    return s[s.index(open_):s.index(close)] if open_ in s and close in s else None


for fname, o, c in (("post_process.py", "# === LEXICON-SANCTIONED RENDERINGS ===",
                     "# === LEXICON-SANCTIONED RENDERINGS ENDS ==="),
                    ("translate_numbering.py", "# === ATTACHMENT LABEL FOLLOWS THE OPERATOR ===",
                     "# === ATTACHMENT LABEL FOLLOWS THE OPERATOR ENDS ===")):
    bu = block(ROOT / "uk" / "scripts" / fname, o, c)
    bs = block(ROOT / "us" / "scripts" / fname, o, c)
    ok(f"{fname}: both trees carry the block", bu is not None and bs is not None)
    ok(f"{fname}: and the two copies are byte-identical", bu == bs,
       f"uk={len(bu or '')} us={len(bs or '')}")
for t in TREES:
    tn_list = getattr(TN[t], "_LABEL_EXCLUDE", None)
    ok(f"{t}: translate_numbering's _LABEL_EXCLUDE equals post_process's ANNEX_EXCLUDE",
       tn_list is not None and list(tn_list) == list(PP[t].ANNEX_EXCLUDE),
       f"{tn_list} vs {PP[t].ANNEX_EXCLUDE}")

print("\n" + "=" * 92)
print(f"  {CHECKED} check(s), {len(FAIL)} failure(s), {len(VOIDED)} void   [{args.variant}]")
for f in FAIL:
    print(f"    FAIL  {f}")
for v in VOIDED:
    print(f"    VOID  {v}")
print("=" * 92)
shutil.rmtree(TMP, ignore_errors=True)
sys.exit(1 if (FAIL or VOIDED) else 0)
