# -*- coding: utf-8 -*-
"""BRANCH 10 SLICE 4 — the principle every tidy-up pass obeys, the page-break pass that now
obeys it, and the detector reports that now reach the journal.

WHY THIS SUITE EXISTS. Decision 2c revised says every pass in `post_process` tests the
condition it assumes, and where it cannot tell, reports and changes nothing. Branch 10 made
eight passes obey that one at a time; nothing stopped pass thirteen from ignoring it. The
declared `PASS_CONDITIONS` table in post_process.py is the rule made checkable, and this
suite is what makes it bind: a pass added without a row turns it RED.

  ARM 1  EVERY JOURNALLED PASS HAS A ROW, AND EVERY ROW NAMES A PASS — read from the
         `_journalled(...)` calls in post_process()'s own source, never from a list here.
  ARM 2  EVERY ROW IS WELL-FORMED, its status one of the four declared.
  ARM 3  BOTH TREES carry the same table.
  ARM 4  POSITIVE CONTROLS — arm 1's comparison, fed a planted extra pass and a planted
         missing row, must name each. A coverage check never seen to go red is not known
         to be able to.
  ARM 5  B7 IN-PROCESS: on every page-start shape the pass REPORTS how the heading starts
         and changes not one byte; its candidacy rule is unchanged.
  ARM 6  B7 THROUGH THE REAL SCRIPT in a real workdir: the detector line, journal schema 3,
         a `detections` record per heading, a fix count of 0, no page break arriving.
  ARM 7  THE OTHER DETECTORS' records carry the paragraph index too.
  ARM 8  NO DOCUMENT TEXT IN `detections`, on every record this suite produced.
  ARM 9  THE PARAGRAPH FORMAT RECORD can still catch a w:pPr change -- proved on the
         recorder, because slice 4 removed the only pass that ever made one.

Every input is synthetic and built in a temporary directory. Nothing is written into
tests/fixtures/ or into either tree.

    uv run --with lxml python tests/test_pass_conditions.py
    uv run --with lxml python tests/test_pass_conditions.py --variant us
"""
import argparse
import ast
import importlib.util
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
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
TMP = Path(tempfile.mkdtemp(prefix="passcond-"))
FAIL, VOIDED, CHECKED = [], [], 0
SCRIPT = ROOT / args.variant / "scripts" / "post_process.py"


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


def load(tree):
    """Import a shipped script BY PATH, bytecode off -- a .pyc embeds an absolute path."""
    spec = importlib.util.spec_from_file_location(f"{tree}_pp_passcond",
                                                  ROOT / tree / "scripts" / "post_process.py")
    mod = importlib.util.module_from_spec(spec)
    saved = sys.argv
    sys.argv = ["post_process.py"]
    try:
        spec.loader.exec_module(mod)
    finally:
        sys.argv = saved
    return mod


PP = {t: load(t) for t in TREES}
pp = PP[args.variant]


def journalled_names(source):
    """The pass names post_process() hands to `_journalled`, read from the SOURCE by ast --
    the first positional argument of every call to that name, inside post_process()."""
    tree = ast.parse(source)
    fn = next((n for n in tree.body if isinstance(n, ast.FunctionDef)
               and n.name == "post_process"), None)
    if fn is None:
        return None
    names = []
    for node in ast.walk(fn):
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                and node.func.id == "_journalled" and node.args
                and isinstance(node.args[0], ast.Constant)
                and isinstance(node.args[0].value, str)):
            names.append(node.args[0].value)
    return names


def coverage_gaps(names, table):
    """(journalled with no row, rows naming no journalled pass)."""
    return sorted(set(names) - set(table)), sorted(set(table) - set(names))


# =========================================================================================
print(f"ARM 1 — every pass post_process() runs has a PASS_CONDITIONS row   [{args.variant}]")
# =========================================================================================
table = getattr(pp, "PASS_CONDITIONS", None)
statuses = getattr(pp, "PASS_STATUSES", None)
src = SCRIPT.read_text(encoding="utf-8")
names = journalled_names(src)
if not ok("post_process.py declares PASS_CONDITIONS and PASS_STATUSES",
          isinstance(table, dict) and isinstance(statuses, tuple),
          "the principle is not written down where the next pass will be added"):
    table, statuses = table or {}, statuses or ()
if not names:
    void("the journalled passes", "no `_journalled('<name>', ...)` call found in post_process()")
    names = []
else:
    ok(f"post_process() journals {len(names)} passes, each once", len(names) == len(set(names)),
       f"names {names}")
missing_row, orphan_row = coverage_gaps(names, table)
ok("every journalled pass has a row", not missing_row, f"no row for {missing_row}")
ok("every row names a pass post_process() actually runs", not orphan_row,
   f"rows for no pass: {orphan_row}")

# =========================================================================================
print("\nARM 2 — every row is well-formed, and its status is one of the four declared")
# =========================================================================================
ok("the four statuses are exactly the ones the header defines",
   tuple(statuses) == ("CONDITIONAL", "DETECTOR", "MECHANICAL", "NOT YET TESTED"),
   f"{statuses}")
for name, row in sorted(table.items()):
    shape = isinstance(row, tuple) and len(row) == 4
    ok(f"{name}: (status, condition, reads, when it cannot tell), none blank",
       shape and all(isinstance(x, str) and x.strip() for x in row), f"{row!r}")
    ok(f"{name}: status {row[0] if shape else '?'!r} is a declared status",
       shape and row[0] in statuses)
# The three DETECTOR rows are the ones this branch turned into detectors -- if a row says
# DETECTOR, the pass must return 0 fixes on the input the pass exists for. Proved per pass in
# arms 5 and 7; here only that the set is what branch 10 left.
ok("the passes declared DETECTOR are exactly the three branch 10 turned into detectors",
   sorted(n for n, r in table.items() if r[0] == "DETECTOR")
   == ["annex_to_schedule", "double_punctuation", "schedule_page_breaks"],
   f"{sorted(n for n, r in table.items() if r[0] == 'DETECTOR')}")

# =========================================================================================
print("\nARM 3 — both trees carry the same principle")
# =========================================================================================
tu, ts = (getattr(PP[t], "PASS_CONDITIONS", None) for t in TREES)
ok("PASS_CONDITIONS is identical in uk and us", tu is not None and tu == ts)
ok("PASS_STATUSES is identical in uk and us",
   getattr(PP["uk"], "PASS_STATUSES", None) == getattr(PP["us"], "PASS_STATUSES", 1))

# =========================================================================================
print("\nARM 4 — POSITIVE CONTROLS: arm 1's comparison can go red, both ways")
# =========================================================================================
ANCHOR = "    results['spacing'] = _journalled('spacing', fix_spacing)\n"
if src.count(ANCHOR) != 1:
    void("planted extra pass", "the anchor line for the plant is not in post_process() once")
else:
    planted = src.replace(ANCHOR, ANCHOR + "    results['ghost'] = _journalled('ghost', "
                                          "fix_spacing)\n", 1)
    m, o = coverage_gaps(journalled_names(planted) or [], table)
    ok("a planted pass with no row is NAMED as missing a row", m == ["ghost"], f"got {m}")
if table:
    short = {k: v for k, v in table.items() if k != "quotes"}
    m, o = coverage_gaps(names, short)
    ok("a planted missing row is NAMED", m == ["quotes"], f"got {m}")
    extra = dict(table, retired_pass=("DETECTOR", "x", "y", "z"))
    m, o = coverage_gaps(names, extra)
    ok("a planted row for no pass is NAMED", o == ["retired_pass"], f"got {o}")


# =========================================================================================
print(f"\nARM 5 — B7 in-process: the page-break pass reports, and changes nothing   "
      f"[{args.variant}]")
# =========================================================================================
def P(inner, ppr=""):
    return f"<w:p>{ppr}{inner}</w:p>"


def R(text):
    return f'<w:r><w:t xml:space="preserve">{text}</w:t></w:r>'


BRP = '<w:r><w:br w:type="page"/></w:r>'
SHAPES = [
    P(R("Body text before the schedules.")),                                     # 0
    P(R("SCHEDULE 1")),                                                          # 1 none
    P(R("Text of schedule one.")),                                               # 2
    P('<w:r><w:br w:type="page"/><w:t>SCHEDULE 2</w:t></w:r>'),                  # 3 brLead
    P('<w:r><w:t>Text ending with a break.</w:t><w:br w:type="page"/></w:r>'),   # 4
    P(R("ANNEX A")),                                                             # 5 brTail
    P(R("Text of annex A.")),                                                    # 6
    P(BRP),                                                                      # 7
    P(R("Schedule 3")),                                                          # 8 brEmp
    P("", "<w:pPr><w:sectPr/></w:pPr>"),                                         # 9
    P(R("SCHEDULE 4")),                                                          # 10 sect
    P(R("SCHEDULE 5"), "<w:pPr><w:pageBreakBefore/></w:pPr>"),                   # 11 pBB
    P(R("SCHEDULE 6"), '<w:pPr><w:pStyle w:val="SchedHead"/></w:pPr>'),          # 12 unknown
    P(R("SCHEDULE 7"), '<w:pPr><w:pStyle w:val="TOC1"/></w:pPr>'),               # 13 not one
    P(R("Schedule for Performance of the Works")),                               # 14 not one
    P(R("SCHEDULE 8"), '<w:pPr><w:pageBreakBefore w:val="0"/></w:pPr>'),         # 15 none
]
EXPECTED = [(1, False, []), (3, True, ["brLead"]), (5, True, ["brTail"]),
            (8, True, ["brEmp"]), (10, True, ["sect"]), (11, True, ["pBB"]),
            (12, None, []), (15, False, [])]
TEXTS = ["Body text before the schedules.", "SCHEDULE 1", "Text of schedule one.",
         "SCHEDULE 2", "Text ending with a break.", "ANNEX A", "Text of annex A.",
         "Schedule 3", "SCHEDULE 4", "SCHEDULE 5", "SCHEDULE 6", "SCHEDULE 7",
         "Schedule for Performance of the Works", "SCHEDULE 8"]


def document(paras):
    return ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
            f'<w:document xmlns:w="{W}"><w:body>' + "".join(paras)
            + "</w:body></w:document>").encode("utf-8")


root = etree.fromstring(document(SHAPES))
before = etree.tostring(root)
try:
    rc5 = pp.fix_schedule_page_breaks(root)
except Exception as exc:  # noqa: BLE001 -- the arm reports rather than dies
    rc5 = f"raised {type(exc).__name__}: {exc}"
ok("the pass returns 0 fixes — a detection is not a fix", rc5 == 0, f"returned {rc5!r}")
ok("and the document is BYTE-IDENTICAL after it — nothing inserted, nothing removed",
   etree.tostring(root) == before,
   "the pass changed the document: a break was imposed, doubled or taken away")
found = getattr(pp, "SCHEDULE_HEADINGS_FOUND", None)
if found is None:
    ok("the pass records what it found in SCHEDULE_HEADINGS_FOUND", False,
       "no such list: the pass still acts instead of reporting")
    found = []
got = [(h.get("para"), h.get("starts_new_page"), h.get("device")) for h in found]
ok(f"it found exactly the {len(EXPECTED)} candidates the unchanged candidacy rule admits",
   [g[0] for g in got] == [e[0] for e in EXPECTED], f"found paragraphs {[g[0] for g in got]}")
for e in EXPECTED:
    g = next((x for x in got if x[0] == e[0]), None)
    ok(f"paragraph {e[0]}: starts_new_page={e[1]!r}, device={e[2]}", g == e, f"got {g}")
ok("the TOC entry and the 'Schedule for ...' clause heading are still NOT candidates",
   not any(g[0] in (13, 14) for g in got))
ok("the heading that already had its own break KEEPS it — the pass removes nothing either",
   b'<w:pageBreakBefore/>' in etree.tostring(root))


# =========================================================================================
print(f"\nARM 6 — B7 through the real script in a real workdir   [{args.variant}]")
# =========================================================================================
def run_pp(name, paras):
    wd = TMP / name
    (wd / "final" / "word").mkdir(parents=True)
    x = wd / "final" / "word" / "document.xml"
    x.write_bytes(document(paras))
    r = subprocess.run(["uv", "run", "--with", "lxml", "python", str(SCRIPT), str(x),
                        "--fix", "--variant", args.variant],
                       capture_output=True, text=True, encoding="utf-8", errors="replace",
                       cwd=str(ROOT), env=ENV, timeout=600)
    j = wd / "post_process_journal.json"
    return r, x.read_bytes(), (json.loads(j.read_text(encoding="utf-8"))
                               if j.is_file() else None)


r6, after6, j6 = run_pp("b7", SHAPES)
ok("post_process exits 0", r6.returncode == 0, (r6.stderr or r6.stdout or "")[-300:])
out6 = r6.stdout or ""
ok("the detector line reports 8 headings and NO break inserted",
   "[detector] schedule_page_breaks found 8 schedule heading(s) and INSERTED NO page break"
   in out6, out6[-500:])
ok("and says which devices it saw and how many headings do not start a new page",
   "5 already start a new page (brEmp 1, brLead 1, brTail 1, pBB 1, sect 1), 2 do not, "
   "1 unknown" in out6, out6[-500:])
ok("the document keeps exactly the page breaks it arrived with",
   after6.count(b"pageBreakBefore") == document(SHAPES).count(b"pageBreakBefore")
   and after6.count(b'w:type="page"') == document(SHAPES).count(b'w:type="page"'))
DETS = []
if j6 is None:
    void("journal", "no journal was written")
else:
    ok("the journal is schema post-process-journal/3", j6.get("schema")
       == "post-process-journal/3", repr(j6.get("schema")))
    ok("it states its detection contract", bool(j6.get("detection_contract")))
    passes = next((s for s in j6.get("stages", []) if s.get("stage") == "passes"), {})
    cnt = next((c for c in passes.get("counts", []) if c["pass"] == "schedule_page_breaks"),
               None)
    ok("the page-break pass is journalled with 0 fixes", cnt is not None and cnt["fixes"] == 0,
       f"{cnt}")
    ok("and no paragraph-format record names it — no break arrived anywhere",
       not any(f["pass"] == "schedule_page_breaks"
               for f in passes.get("format_paragraphs", [])))
    sp = [d for d in j6.get("detections", []) if d.get("pass") == "schedule_page_breaks"]
    DETS += j6.get("detections", [])
    ok("one detection per heading, at the heading's paragraph index",
       [d.get("para") for d in sp] == [e[0] for e in EXPECTED],
       f"{[d.get('para') for d in sp]}")
    want_reason = {True: "starts a new page", False: "does not start a new page",
                   None: "unknown: styled, and a style is not visible in document.xml"}
    ok("each carries the reason and the device codes the in-process record gives",
       [(d.get("reason"), d.get("device"), d.get("count")) for d in sp]
       == [(want_reason[e[1]], e[2], 1) for e in EXPECTED],
       f"{[(d.get('reason'), d.get('device')) for d in sp]}")


# =========================================================================================
print(f"\nARM 7 — the other detectors' records carry the paragraph index   [{args.variant}]")
# =========================================================================================
OTHER = [
    P(R("Definitions::")),                                                       # 0
    P(R("The parties waive Article 1341 thereof.")),                             # 1
    P('<w:r><w:rPr><w:i/></w:rPr><w:t xml:space="preserve">the borrower shall '
      'notify</w:t></w:r>'),                                                     # 2
    P(R("The milestones are set out in Annex 1.")),                              # 3
]
r7, _after7, j7 = run_pp("others", OTHER)
ok("post_process exits 0", r7.returncode == 0, (r7.stderr or r7.stdout or "")[-300:])
if j7 is None:
    void("journal", "no journal was written")
else:
    DETS += j7.get("detections", [])
    by = {}
    for d in j7.get("detections", []):
        by.setdefault(d["pass"], []).append(d)
    for pname, para, reason in (("double_punctuation", 0, "double colon"),
                                ("article_to_clause", 1, "indeterminate"),
                                ("spurious_italic", 2, "no notes"),
                                ("annex_to_schedule", 3, "no notes")):
        recs = by.get(pname, [])
        ok(f"{pname}: a record at paragraph {para}, reason {reason!r}",
           any(d.get("para") == para and d.get("reason") == reason for d in recs),
           f"{recs}")
    ann = by.get("annex_to_schedule", [])
    ok("the kept Annex is named by its LEXICON_SANCTIONED index, never by its text",
       ann and all(isinstance(d.get("entry"), int)
                   and 0 <= d["entry"] < len(pp.LEXICON_SANCTIONED) for d in ann), f"{ann}")
    ok("no detection is counted as a fix",
       sum(c["fixes"] for c in next(s for s in j7["stages"]
                                    if s["stage"] == "passes")["counts"]
           if c["pass"] in ("double_punctuation", "annex_to_schedule")) == 0)

# =========================================================================================
print("\nARM 8 — no document text in `detections`, on every record this suite produced")
# =========================================================================================
texts = TEXTS + ["Definitions::", "The parties waive Article 1341 thereof.",
                 "the borrower shall notify", "The milestones are set out in Annex 1.",
                 "Article 1341", "Annex 1"]


def strings(v):
    if isinstance(v, str):
        yield v
    elif isinstance(v, dict):
        for x in v.values():
            yield from strings(x)
    elif isinstance(v, (list, tuple)):
        for x in v:
            yield from strings(x)


if not DETS:
    void("no-text check", "no detection records were produced to check")
else:
    leaked = [s for d in DETS for s in strings(d) for t in texts if t in s]
    ok(f"{len(DETS)} record(s), and not one carries a string of the document", not leaked,
       f"{leaked[:3]}")
    keys = sorted({k for d in DETS for k in d})
    ok("records use only the contract's keys",
       set(keys) <= {"pass", "reason", "para", "count", "entry", "device"}, f"{keys}")

# =========================================================================================
print("\nARM 9 — the paragraph FORMAT record can still catch a w:pPr change")
# =========================================================================================
# WHY THIS ARM EXISTS. Until slice 4 the page-break pass was the one pass that changed a
# w:pPr, so tests/test_change_journal.py arm 9 proved the paragraph-level recorder by catching
# its imposed break. Slice 4 removed the only subject that arm had, and a recorder nobody has
# seen record is an instrument that may have stopped working. So it is proved here on the
# recorder itself: the reading sees a planted pageBreakBefore, and record_pass files it at the
# right paragraph under the pass that made it.
root9 = etree.fromstring(document([P(R("One.")), P(R("Two.")), P(R("Three."))]))
pf_before = pp.journal_paragraph_formats(root9)
p1 = list(root9.iter(f"{{{W}}}p"))[1]
ppr1 = etree.SubElement(p1, f"{{{W}}}pPr")
p1.remove(ppr1)
p1.insert(0, ppr1)
etree.SubElement(ppr1, f"{{{W}}}pageBreakBefore")
pf_after = pp.journal_paragraph_formats(root9)
ok("the paragraph reading sees the planted break, and only on paragraph 1",
   [i for i, (a, b) in enumerate(zip(pf_before, pf_after)) if a != b] == [1],
   f"{pf_before} -> {pf_after}")
jr9 = pp.ChangeJournal(args.variant)
jr9.record_pass("planted", [], [], [], [], 0, 0, [], 1, [], [], pf_before, pf_after)
ok("record_pass files it once, at paragraph 1, under the pass that made it",
   [(r["pass"], r["para"]) for r in jr9.pass_format_paragraphs] == [("planted", 1)],
   f"{jr9.pass_format_paragraphs}")

print("\n" + "=" * 92)
print(f"  {CHECKED} check(s), {len(FAIL)} failure(s), {len(VOIDED)} void   [{args.variant}]")
for f in FAIL:
    print(f"    FAIL  {f}")
for v in VOIDED:
    print(f"    VOID  {v}")
print("=" * 92)
shutil.rmtree(TMP, ignore_errors=True)
sys.exit(1 if (FAIL or VOIDED) else 0)
