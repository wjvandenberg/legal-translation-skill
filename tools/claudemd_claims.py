# -*- coding: utf-8 -*-
"""CLAIMS CHECK over CLAUDE.md — every factual claim re-derived from the source that
should support it.

Wouter, 2026-08-06: "Run a claims check over this file BEFORE restructuring it, not after
— the same typed-prose drift that put three stale counts into the Step B analysis is here
at larger scale. Restructuring first would carry the errors into the new structure."

Built on the pattern of `temp/stepb_audit3.py`, with the three lessons that pattern taught:

  * RE-MEASURE, DO NOT RE-READ. Every figure is derived from the artefact — the register's
    own rows, the two publication archives read as zips, the filesystem — never copied out
    of the file being checked.
  * NEVER A TWO-WORD NEEDLE. Each claim is anchored on a phrase that could only appear if
    the claim is actually being made. Two false passes in this project came from short
    needles matching prose that said the opposite.
  * A KNOWN FAILURE IS STILL A HYPOTHESIS. The two failures handed to this session were
    themselves pre-registered and are tested here rather than assumed.

Three kinds of check, so that the same script serves before and after the rewrite:

  A. FORBIDDEN   — a stale string that must not survive the overhaul.
  B. REQUIRED    — a fact that must be present and stated correctly.
  C. DERIVED     — a figure CLAUDE.md states, compared against the measurement.

    uv run python temp/claudemd_claims.py
"""
import io
import re
import sys
import zipfile
from collections import Counter
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
PRIV = ROOT.parent / "legal-translation-private"
PUB = ROOT.parent / "skills" / "legal-translation" / "PUBLICATION VERSIONS"

CMD = (ROOT / "CLAUDE.md").read_text(encoding="utf-8")
REG = (ROOT / "FINDINGS-REGISTER.md").read_text(encoding="utf-8")
A3 = (ROOT / "A3-STRUCTURAL-ANALYSIS.md").read_text(encoding="utf-8")
SB = (ROOT / "STEP-B-ANALYSIS.md").read_text(encoding="utf-8")

FLAT = re.sub(r"\s+", " ", CMD)

FAIL, WARN, JUDGE = [], [], []


def fail(tag, msg):
    print(f"  [FAIL] {tag}: {msg}")
    FAIL.append(tag)


def warn(tag, msg):
    print(f"  [warn] {tag}: {msg}")
    WARN.append(tag)


def judge(tag, msg):
    print(f"  [JUDGE] {tag}: {msg}")
    JUDGE.append(tag)


def ok(msg):
    print(f"  [OK  ] {msg}")


def head(n, title):
    print()
    print("=" * 92)
    print(f"{n}. {title}")
    print("=" * 92)


def present(needle):
    """True if the needle appears in CLAUDE.md, whitespace-insensitively."""
    return re.sub(r"\s+", " ", needle) in FLAT


# ---------------------------------------------------------------------------
# GROUND TRUTH — derived once, from the artefacts, before any claim is looked at
# ---------------------------------------------------------------------------
ROW_ID = re.compile(r"^\|\s*(?:\*\*)?([A-Z]{1,2}-?\d{1,2}[a-z]?)(?:\*\*)?\s*\|")
reg_rows, _sec = {}, None
for _line in REG.split("\n"):
    _m = re.match(r"^#{2,3}\s+(.*)$", _line)
    if _m:
        _sec = _m.group(1)
        continue
    _m = ROW_ID.match(_line)
    if _m:
        reg_rows.setdefault(_m.group(1), dict(text=_line, sec=_sec))

_letters = Counter()
for _rid in reg_rows:
    if _rid.startswith("I-"):
        _letters["I-"] += 1
    else:
        _letters[re.match(r"[A-Z]+", _rid).group(0)] += 1

CLUSTER_LETTERS = [c for c in "ABCDEFGHJKLSTXY"]
SINGLE_LETTERS = [c for c in ("M", "N", "O", "Q", "R", "U", "V", "W")]

TRUTH = {
    "rows": len(reg_rows),
    "positives": _letters["P"],
    "instrument": _letters["I-"],
    "clusters": len(CLUSTER_LETTERS),
    "clustered": sum(_letters[c] for c in CLUSTER_LETTERS),
    "single": sum(_letters[c] for c in SINGLE_LETTERS),
    "clusterF": _letters["F"],
}
TRUTH["skill_findings"] = TRUTH["clustered"] + TRUTH["single"]

ARCH = {}
for _label, _name in [("UK", "legal-translation (UK English).skill"),
                      ("US", "legal-translation (US English).skill")]:
    _z = zipfile.ZipFile(PUB / _name)
    _infos = [i for i in _z.infolist() if not i.is_dir()]
    ARCH[_label] = dict(
        zip=_z,
        files={i.filename: i.file_size for i in _infos},
        count=len(_infos),
        total=sum(i.file_size for i in _infos),
        dirs=Counter(),
    )
    for _i in _infos:
        _top = _i.filename.split("/")[0] if "/" in _i.filename else "(root)"
        ARCH[_label]["dirs"][_top] += _i.file_size
    ARCH[_label]["dircount"] = Counter(
        (n.split("/")[0] if "/" in n else "(root)") for n in ARCH[_label]["files"])


head(1, "PATHS — the second pre-registered failure, re-derived WITHOUT the "
        "suppressor that hides one of them")
# publication_check.py drops any candidate containing a regex metacharacter pair, to
# suppress quoted regexes from the skill's own code. A home-relative path whose first
# segment begins with a capital D contains "\D", so that filter silently ate a real hit
# until 2026-08-06. Re-derived here with no filter at all.
PATH_PROBES = [
    ("absolute Windows path", r"[A-Za-z]:\\[\w\-.]+(?:\\[\w\-. ]+)+"),
    ("home-relative path", r"~[\\/][\w\-.]+(?:[\\/][\w\-. ]+)+"),
    ("container path", r"(?<![\w.])/(?:home|mnt)/[\w\-./]*"),
]
found_paths = []
for label, pat in PATH_PROBES:
    for h in sorted(set(re.findall(pat, CMD))):
        found_paths.append((label, h))
        print(f"  [FAIL] path: {label:<22} {h!r}")
if found_paths:
    FAIL.append("1")
    n_abs = sum(1 for l, _ in found_paths if l != "container path")
    n_con = sum(1 for l, _ in found_paths if l == "container path")
    print(f"  -> {n_abs} absolute path(s) and {n_con} container path(s). The handoff "
          f"predicted 2 and 3.")
else:
    ok("no absolute, home-relative or container paths in CLAUDE.md")
print("  NOTE on the instrument itself: publication_check.py reports only 4 of these 5, "
      "because\n        its regex-metacharacter filter treats the backslash-D in "
      "'~\\Downloads' as a quoted regex.\n        A check that suppresses a real hit for "
      "the wrong reason is the failure class this\n        project keeps logging. Fix the "
      "filter or the finding stays invisible next time.")

head(2, "THE FIRST PRE-REGISTERED FAILURE — does charter observation 8 still claim the "
        "dual-variant design 'holds in references/'?")
obs8 = re.search(r"\|\s*8\s*\|([^|]*)\|([^|]*)\|", CMD)
if not obs8:
    fail("2", "charter observation 8's row could not be located at all")
else:
    body = re.sub(r"\s+", " ", obs8.group(1) + " " + obs8.group(2))
    print(f"  row 8 reads: {body.strip()[:220]}")
    claims_holds = "holds in `references/`" in body or "holds in references/" in body
    carries_correction = ("has eroded too" in body or "also diverged" in body
                          or "reference layer has eroded" in body)
    if claims_holds:
        fail("2", "observation 8 still makes the falsified claim")
    elif carries_correction:
        ok("the falsified claim is ABSENT and the row already carries A3's correction — "
           "so this pre-registered failure DOES NOT REPRODUCE")
        judge("2", "The instruction to this session named this as a known, confirmed "
                   "failure. It is not one: the 2026-07-31 rewrite already shortened the "
                   "observation and moved A3's correction into the verdict column. A3 was "
                   "quoting the PRE-REWRITE file. THIRD time in this project that a claim "
                   "about the evidence, made from a précis, did not survive measurement — "
                   "after the predicted blind-only cell (2026-08-04) and Step B working "
                   "from the comparison instead of the report (2026-08-05).")
    else:
        warn("2", "neither the falsified claim nor the correction is present — check by hand")
if not re.search(r"reference layer has eroded|`references/` has eroded too", CMD):
    warn("2", "the correction text itself is not where it was expected")

head(3, "REGISTER ARITHMETIC — every count CLAUDE.md states about the register")
print(f"  derived from FINDINGS-REGISTER.md: rows={TRUTH['rows']} clusters="
      f"{TRUTH['clusters']} skill findings={TRUTH['skill_findings']} "
      f"(clustered {TRUTH['clustered']} + single {TRUTH['single']}) "
      f"positives={TRUTH['positives']} instrument={TRUTH['instrument']} "
      f"clusterF={TRUTH['clusterF']}")
print()
# NEEDLES RE-ANCHORED 2026-08-06 on the rewritten file. The ASSERTIONS are unchanged --
# each figure is still compared against the register's own rows. Only the phrases that
# locate them moved, because the prose around them was rewritten.
COUNT_CLAIMS = [
    ("rows", r"(\d{3}) rows", "rows"),
    ("clusters", r"(\d{2}) clusters", "clusters"),
    ("skill findings", r"(\d{3}) skill\s+findings", "skill_findings"),
    ("positives", r"(\d+) positives to preserve", "positives"),
    ("instrument defects", r"(\d+) defects in our own measuring instruments", "instrument"),
    ("cluster F size", r"largest\s+cluster is the instruction contradictions, at \*\*(\d+)\*\*",
     "clusterF"),
]
# Count claims are searched against a flattened copy with blockquote markers stripped.
# Searching the raw text missed a figure that had wrapped across a "> " line: a needle
# reading `largest\s+cluster` cannot match "largest\n> cluster", because ">" is not
# whitespace. It reported "no occurrence" rather than a failure, which is the quiet way
# for a check to stop checking.
UNQUOTED = re.sub(r"\s+", " ", re.sub(r"(?m)^>\s?", "", CMD))
for label, pat, key in COUNT_CLAIMS:
    hits = Counter(int(h) for h in re.findall(pat, UNQUOTED))
    if not hits:
        warn("3", f"{label}: no occurrence — the needle {pat!r} matched nothing")
        continue
    wrong = {v: c for v, c in hits.items() if v != TRUTH[key]}
    if wrong:
        fail("3", f"{label}: CLAUDE.md states {dict(hits)}; the register has "
                  f"{TRUTH[key]}. Wrong in {sum(wrong.values())} place(s)")
    else:
        ok(f"{label}: consistently {TRUTH[key]} ({sum(hits.values())} mentions)")

# the composite line that appears verbatim in three places
STALE_COMPOSITES = [
    "198 rows: 14 clusters · 160 skill findings · 27 positives · 11 instrument defects",
    "198 rows / 14 clusters / 160 findings",
    "198 rows / 160 skill findings / 14 clusters / 27 positives",
    "135 findings, clustered by root cause",
    "all 135 register rows mapped",
    "cluster F is now 29 findings",
    "at most 94 of 166 findings",
    # a superseded count left anywhere in the prose is the next session's error, even when
    # the sentence around it is reporting the error rather than making it
    "198 rows",
    "14 clusters",
    "160 skill findings",
]
for s in STALE_COMPOSITES:
    if present(s):
        fail("3", f"stale composite still present: {s!r}")
if not [f for f in FAIL if f == "3"]:
    ok("no stale composite count lines")

head(4, "CROSS-DOCUMENT SECTION REFERENCES — does the cited section exist, and is it "
        "about what CLAUDE.md says it is about?")
sb_heads = {m.group(1): m.group(2).strip()
            for m in re.finditer(r"^#{2,3}\s+(\d+(?:\.\d+)?)\.?\s+(.*)$", SB, re.M)}
a3_heads = {m.group(1): m.group(2).strip()
            for m in re.finditer(r"^#{2,3}\s+(\d+(?:\.\d+)?)\.?\s+(.*)$", A3, re.M)}
REFS = [
    # (claim as CLAUDE.md makes it, doc, section, a word the heading must contain)
    ("STEP-B-ANALYSIS.md §3 is the build brief", SB, sb_heads, "3", "build brief", False),
    ("STEP-B-ANALYSIS.md §2 is the plan of work", SB, sb_heads, "2", "plan of work", False),
    ("STEP-B-ANALYSIS.md §4 owns the test method", SB, sb_heads, "4", "tested", False),
    ("A3 §2 is the six keystones", A3, a3_heads, "2", "keystones", False),
    ("A3 §6 is the findings map", A3, a3_heads, "6", "structural map", False),
    ("A3 §5 answers the eleven observations", A3, a3_heads, "5", "observations", False),
    ("A3 §0 is the summary", A3, a3_heads, "0", "Summary", False),
    ("A3 §3 measures context/runtime/redundancy", A3, a3_heads, "3", "COSTS", False),
]
for claim, _doc, heads, sec, word, is_stale in REFS:
    title = heads.get(sec, "<<MISSING>>")
    good = word.lower() in title.lower()
    if is_stale:
        if good:
            fail("4", f"{claim}: unexpectedly TRUE — re-check, the handoff says it moved")
        else:
            print(f"  [note] {claim}: §{sec} is now {title[:70]!r} — the reference IS stale")
    elif good:
        ok(f"{claim} — §{sec} = {title[:64]!r}")
    else:
        fail("4", f"{claim}: §{sec} is actually {title[:70]!r}")

# §11 needs its SUBSTANCE tested, not its heading word. Its title still contains
# "decisions", so a word-match reports it as the decision record and passes — the exact
# false pass this project keeps logging. What actually changed is that §11 became a
# POINTER and §3 became the record.
s11 = SB[SB.index("## 11."):SB.index("## 12.")]
if "POINTER" in s11 and "the answers — they live in §3" in SB:
    ok("§11 declares itself a POINTER and §3 owns the answers — so any CLAUDE.md text "
       "calling §11 the decision record is stale")
else:
    warn("4", "could not confirm §11's pointer status from the analysis itself")
for s in ["`STEP-B-ANALYSIS.md` §11 rather than a summary",
          "Its §11 is the decision record"]:
    if present(s):
        fail("4", f"stale §11 citation still present: {s!r}")

head(5, "THE PUBLISHED TREE — §4's byte table re-derived from the two rev44 archives")
for label in ("UK", "US"):
    a = ARCH[label]
    print(f"  {label}: {a['count']} files, {a['total']:,} bytes, "
          f"dirs={dict(a['dircount'])}")
TREE_CLAIMS = [
    ("198 files per variant", ARCH["UK"]["count"] == 198 and ARCH["US"]["count"] == 198),
    ("SKILL.md 57,269 UK / 57,532 US",
     ARCH["UK"]["files"]["SKILL.md"] == 57269 and ARCH["US"]["files"]["SKILL.md"] == 57532),
    ("04-translate.md 47,707 UK / 50,463 US",
     ARCH["UK"]["files"]["skill-docs/04-translate.md"] == 47707
     and ARCH["US"]["files"]["skill-docs/04-translate.md"] == 50463),
    ("TOTAL 3,651,835 UK / 3,667,750 US",
     ARCH["UK"]["total"] == 3651835 and ARCH["US"]["total"] == 3667750),
    ("8 step docs", ARCH["UK"]["dircount"]["skill-docs"] == 8),
    ("15 cross-language references", ARCH["UK"]["dircount"]["references"] == 15),
    ("20 Python scripts", ARCH["UK"]["dircount"]["scripts"] == 20),
    ("154 sub-lexicons = 11 languages x 14 domains",
     ARCH["UK"]["dircount"]["sub-lexicons"] == 154 and 11 * 14 == 154),
]
for label, truth in TREE_CLAIMS:
    (ok if truth else lambda m: fail("5", m))(f"{label}: {'reproduces' if truth else 'DOES NOT reproduce'}")

# every per-file byte figure in the code block, checked against the archive
block = re.search(r"```\n(\s+UK bytes.*?)```", CMD, re.S)
if not block:
    warn("5", "the §4 byte table could not be located")
else:
    checked = 0
    for line in block.group(1).split("\n"):
        m = re.match(r"\s*([\w\-./]+\.md|SKILL\.md)\s+([\d,]+)\s+([\d,]+)", line)
        if not m:
            continue
        name = m.group(1)
        key = name if name == "SKILL.md" else f"skill-docs/{name}"
        if key not in ARCH["UK"]["files"]:
            continue
        uk, us = int(m.group(2).replace(",", "")), int(m.group(3).replace(",", ""))
        checked += 1
        if (ARCH["UK"]["files"][key], ARCH["US"]["files"][key]) != (uk, us):
            fail("5", f"{key}: table says {uk:,}/{us:,}, archive has "
                      f"{ARCH['UK']['files'][key]:,}/{ARCH['US']['files'][key]:,}")
    ok(f"{checked} per-file byte figures re-measured from the archives")

# the truncation claim
over = [n for n, s in ARCH["UK"]["files"].items() if s > 55466]
if present("Three files per tree sit past the only install-truncation position ever OBSERVED"):
    if len(over) == 3:
        ok(f"three files per tree past byte 55,466: {sorted(over)}")
    else:
        fail("5", f"the claim says three files past 55,466; the archive has {len(over)}: {over}")

# lxml
lxml_scripts = [n for n in ARCH["UK"]["files"]
                if n.startswith("scripts/") and b"lxml" in ARCH["UK"]["zip"].read(n)]
m = re.search(r"only third-party\s+import, in (\d+) of the (\d+) scripts", FLAT)
if m:
    claimed, total = int(m.group(1)), int(m.group(2))
    (ok if (claimed, total) == (len(lxml_scripts), ARCH["UK"]["dircount"]["scripts"])
     else lambda mm: fail("5", mm))(
        f"lxml in {len(lxml_scripts)} of {ARCH['UK']['dircount']['scripts']} scripts "
        f"(claim: {claimed} of {total})")
else:
    warn("5", "the lxml claim could not be located")

head(6, "FILESYSTEM STATE — every claim about what does and does not exist")
# UPDATED 2026-08-06, AND THE OLD VERSION IS THE POINT. This list used to assert the
# PRE-REPOSITORY world -- no `.git`, no `tools/`, no `uk/` or `us/`, no `README.md` -- because
# that is what the charter claimed when the check was written. Branch 0 then created every one
# of them, deliberately, and the instrument was never updated: it reported seven failures
# against a charter that had stopped making those claims at all (verified: the string "no
# `.git`" now appears zero times in CLAUDE.md).
#
# Seven confident failures, none of them real, is worse than no check. A reviewer learns to
# skim it, which is the exact failure mode this project has diagnosed in the skill's own
# validators. So the assertions now describe the state the charter CURRENTLY claims, and the
# two rules that genuinely survive the change are kept and marked.
FS = [
    ("`.git` exists — the repository was created at branch 0", (ROOT / ".git").exists()),
    ("`.gitignore` exists", (ROOT / ".gitignore").exists()),
    ("`.gitattributes` exists — it is what stops line-ending translation",
     (ROOT / ".gitattributes").exists()),
    ("`tools/` exists", (ROOT / "tools").exists()),
    ("`tests/` exists", (ROOT / "tests").exists()),
    ("both variant trees exist", (ROOT / "uk").exists() and (ROOT / "us").exists()),
    ("`README.md` exists — the public front door, from commit one",
     (ROOT / "README.md").exists()),
    # STILL A LIVE RULE, not a leftover: docs/history/ was decided against on 2026-08-06 and
    # the recovered changelog stays outside the repository.
    ("no `docs/` — §5.4(c)", not (ROOT / "docs").exists()),
    ("no rev*_smoke.py anywhere", not list(ROOT.rglob("rev*_smoke.py"))),
]
for label, truth in FS:
    (ok if truth else lambda m: fail("6", m))(f"{label}: {truth}")

mds = sorted(p.name for p in ROOT.glob("*.md"))
if present("The project folder contains **only** `CLAUDE.md`, `FINDINGS-REGISTER.md` and `temp/`"):
    fail("6", f"the folder-contents claim is stale: it now holds {mds}")
if present("the project folder contains `CLAUDE.md`, `FINDINGS-REGISTER.md`, "
           "`A3-STRUCTURAL-ANALYSIS.md` and `temp/`"):
    fail("6", f"a second, differently-worded folder-contents claim is also stale: {mds}")

# No client artefact may sit anywhere the first commit could reach. temp/ is gitignored
# scratch and is reported separately rather than silently excused.
#
# UPDATED 2026-08-06: `tests/fixtures/` is now a SANCTIONED home for document-shaped files.
# §5.8 makes synthetic fixtures committable by design -- they are what runs on every change
# and what `git bisect` uses -- and the pre-commit gate already encodes the same rule from
# the other side, blocking any Word document OUTSIDE that folder. This check predated the
# folder existing and fired on all eleven the moment branch 1 was merged.
#
# Allowing the folder is not a weakening, because it is not taken on trust: every fixture is
# scanned against the full name and descriptor lists by the pre-commit gate and again by
# tools/audit_branches.py, and must hit zero. The claim being made here is about PLACE; the
# claim about CONTENT is made, and enforced, elsewhere.
ALLOWED_DOC_DIRS = ("temp/", "tests/fixtures/")
junk = sorted(p.relative_to(ROOT).as_posix() for ext in
              ("docx", "doc", "pdf", "png", "xml", "jsonl")
              for p in ROOT.rglob(f"*.{ext}"))
stray = [j for j in junk if not j.startswith(ALLOWED_DOC_DIRS)]
if stray:
    fail("6", f"document-shaped file(s) outside {' and '.join(ALLOWED_DOC_DIRS)}: {stray}")
else:
    n_fx = sum(1 for j in junk if j.startswith("tests/fixtures/"))
    ok(f"no document-shaped file outside the two sanctioned places "
       f"({len(junk) - n_fx} in temp/ scratch, {n_fx} synthetic fixtures in tests/fixtures/)")

# every temp/ script and private tool CLAUDE.md names by filename must exist
# A named .py is legitimate if it is ours (temp/ or the private tools/) OR one of the
# skill's own twenty scripts. The first version of this check knew nothing about the
# archive and reported five shipped pipeline scripts as missing files.
skill_scripts = {n.split("/")[-1] for n in ARCH["UK"]["files"] if n.startswith("scripts/")}

# TWO DEFECTS IN THIS CHECK, BOTH FOUND 2026-08-11 AND BOTH FIXED HERE.
#
# (1) IT COULD NOT SEE tools/ OR tests/. It searched temp/, the private tools/ and the skill
#     archive -- and tools/ did not exist when it was written. So ANY repository tool the
#     charter names was reported as existing nowhere. There are 23 of them now.
#
# (2) THE REGEX ONLY UNDERSTOOD A `temp/` PREFIX, so `tools/gate_replay.py` in backticks
#     matched NOTHING and was silently never checked, while the bare `gate_replay.py`
#     matched and then failed to resolve. The check's verdict therefore depended on how the
#     author happened to punctuate the reference -- one spelling failed loudly, the other was
#     not checked at all. That is worse than either alone, and it is why the prefix is now
#     part of the pattern and the search covers every folder we actually keep scripts in.
# AND THE SAME DEFECT AGAIN, ONE DIRECTORY DEEPER, 2026-08-18. Both fixes above enumerated the
# directories that existed when they were written -- `tools/hooks/` was named explicitly and
# `tests/` was named as a flat folder. `tests/probe-5b/` then landed on branch 5, and the check
# reproduced defect (2) exactly: `tests/probe-5b/preflight.py` in backticks matched NOTHING and
# was silently never checked, while the bare `preflight.py` matched and failed to resolve. The
# verdict again depended on punctuation.
#
# SO THE FIX IS NOT ANOTHER DIRECTORY IN THE LIST. Adding `tests/probe-5b` would leave the next
# subdirectory to rediscover this a fourth time, which is the "fix scoped to one caller of a
# shared hazard" failure §5.1 names. Instead: search each root RECURSIVELY, and let the pattern
# understand ANY relative path prefix -- more than one segment, and hyphens, which `probe-5b`
# has and which is precisely why the old pattern skipped it.
SEARCH_ROOTS = [ROOT / "temp", ROOT / "tools", ROOT / "tests", PRIV / "tools"]
scripts_on_disk = set()
for _root in SEARCH_ROOTS:
    if _root.exists():
        scripts_on_disk |= {p.name for p in _root.rglob("*.py")}
named = set(re.findall(r"`(?:[A-Za-z0-9_.\-]+[\\/])*([a-z0-9_]+\.py)`", CMD))

# DECLARED FUTURE, not missing. Widening the pattern above immediately surfaced these two,
# which the old regex had been skipping because they are written with a `tools/` prefix. They
# are real absences and the check is right to see them -- but the charter describes them as
# work to be built at release time, not as tools that exist. Naming them here keeps the check
# strict (anything NOT listed is still an unexplained absence) while recording why these two
# are allowed to be absent. Delete an entry the moment its script lands.
PLANNED = {
    "package.py": "§6.6 — builds one .skill archive per variant, at release time",
    "publish.py": "§6.6 — copies each tree into its public repo, at release time",
}
absent = {n for n in named
          if n not in scripts_on_disk and n not in skill_scripts}
missing = sorted(absent - set(PLANNED))
planned_absent = sorted(absent & set(PLANNED))
if missing:
    fail("6", f"script(s) named in CLAUDE.md that exist nowhere — not in temp/, tools/, "
              f"tests/, the private tools/, or the skill: {missing}")
else:
    ok(f"all {len(named)} named .py files exist "
       f"({len(named & skill_scripts)} of them the skill's own"
       + (f"; {len(planned_absent)} declared future: "
          + ", ".join(f"{n} ({PLANNED[n]})" for n in planned_absent) if planned_absent
          else "") + ")")

named_private = set(re.findall(r"`(A4-[A-Z\-]+\.md)`", CMD))
missing_p = sorted(n for n in named_private if not (PRIV / n).exists())
if missing_p:
    fail("6", f"A4 document(s) named in CLAUDE.md that do not exist: {missing_p}")
else:
    ok(f"all {len(named_private)} named A4 documents exist in the private folder")

# the twelve private tools
a4_tools = sorted(p.name for p in (PRIV / "tools").glob("a4_*.py"))
if present("twelve** tools in the private `tools\\`") or present("**twelve** tools"):
    total = len(a4_tools) + (1 if (PRIV / "tools" / "leakage_scan.py").exists() else 0)
    (ok if total == 12 else lambda m: fail("6", m))(
        f"private tools: {len(a4_tools)} a4_* + leakage_scan = {total} (claim: twelve)")

head(7, "STATUS CLAIMS — statements about where the project is, against the record")
STATUS = [
    # (needle, is it still true?, why)
    ("A4-iii NOT RUN", False,
     "A4-iii ran on 2026-08-04; the decisions log and both handoffs record its score vector"),
    ("Steps 1–3 of thirteen are done", False,
     "all thirteen comparison steps completed 2026-08-04"),
    ("Step A: the structural review · IN PROGRESS", False,
     "Step A is COMPLETE — stated three times elsewhere in the same file"),
    ("Phase 3 — Step B and defect closure · BLOCKED ON A4", False,
     "Step B is complete; the analysis exists"),
    ("**A4** | the **BLIND** desk review", None, "check the row's status cell by hand"),
    ("Step A is one session from complete", False,
     "§6 Current status is two milestones behind"),
    ("EXPLORATION ALL BUT COMPLETE", False, "option 7 was decided 2026-08-05"),
    ("option 7 alone outstanding", False, "decided 2026-08-05"),
    ("**A4 — the BLIND desk review — is the remaining strand**", False,
     "Roadmap Phase 2 still describes A4 as unrun"),
    ("Its sealed brief must live outside `CLAUDE.md`", False,
     "the blindness rules are spent — stated in the same file"),
    ("ten decided (all GO)", False, "eleven decided: ten GO, the rebuild declined"),
]
for needle, still_true, why in STATUS:
    if not present(needle):
        print(f"  [note] not present (already removed?): {needle!r}")
        continue
    if still_true is False:
        fail("7", f"stale status claim present: {needle!r} — {why}")
    else:
        judge("7", f"{needle!r} — {why}")

head(8, "SCOPING CAUTIONS — the overhaul brief said 'eleven of the fourteen' had been "
        "absorbed. How many were there, and is dropping them safe?")
old = (ROOT / "temp" / "CLAUDE.md.pre-overhaul")
if old.exists():
    m = re.search(r"\*\*Scoping cautions that survive whatever the branch list becomes:\*\*(.*?)\n## ",
                  old.read_text(encoding="utf-8"), re.S)
    n = len(re.findall(r"^- \*\*", m.group(1), re.M)) if m else 0
    print(f"  the pre-overhaul list held {n} bullets, not fourteen")
    if present("eleven of the fourteen scoping cautions"):
        fail("8", "CLAUDE.md still says 'eleven of the fourteen scoping cautions'")
# dropping them is only safe if the standing prescription check proves the analysis carries
# them. It reports 63 carried / 0 missing, and eight of the 63 are these cautions.
harv = (ROOT / "temp" / "stepb_harvest.py").read_text(encoding="utf-8")
sc = len(re.findall(r'\("SC\d+", "charter"', harv))
if sc >= 8:
    ok(f"the standing prescription check carries {sc} charter scoping cautions into the "
       f"build plan by id — which is what makes removing them from the charter safe")
else:
    fail("8", f"only {sc} cautions are tracked by the prescription check; removing the "
              f"list from the charter would lose the rest")

head(9, "STEP B FACTS — what CLAUDE.md says about the analysis, against the analysis")
sb_branch_table = SB[SB.index("## 2. The plan of work"):SB.index("## 3. The build brief")]
n_branches = len(re.findall(r"^\| \*\*(\d+)\*\* \|", sb_branch_table, re.M))
n_deferred = len(re.findall(r"^\| \*\*D(\d)\*\* \|", sb_branch_table, re.M))
sb_subs = re.findall(r"^### 3\.(\d+) .*?— option (\d+)", SB, re.M)
sb_go = len(re.findall(r"\|\s*\*\*3\.\d+\*\*\s*\|\s*\*\*\d+ — [^|]+\|\s*\*\*GO", SB))
print(f"  the analysis: {n_branches} numbered branches + {n_deferred} deferred = "
      f"{n_branches + n_deferred} pieces of work; {len(sb_subs)} option records; "
      f"{sb_go} marked GO")
SBC = [
    ("twenty branches plus three deferred items", n_branches == 20 and n_deferred == 3),
    ("eleven options", len(sb_subs) == 11),
    ("ten options approved, the rebuild declined", sb_go == 10),
    ("in four parts", SB.count("## PART ") == 4),
    # "changes nothing a document can see" is every branch row whose LAST cell is not
    # "yes" -- three plain "no", three "doc only", and three qualified "no -- ...".
    # Counting only the plain "no" cells gave 3 and reported a true claim as false.
    ("Nine of the twenty branches change nothing a document can see",
     len([r for r in re.findall(r"^\| \*\*\d+\*\* \|.*$", sb_branch_table, re.M)
          if "yes" not in r.rsplit("|", 2)[-2].lower()]) == 9),
    ("only Part One is needed to build", "only Part One is needed to build" in SB),
]
for label, truth in SBC:
    if present(label) or present(label.lower()):
        (ok if truth else lambda mm: fail("9", mm))(f"{label}: {truth}")
    else:
        print(f"  [note] claim not present in CLAUDE.md: {label!r}")

# the rebuild arithmetic, which CLAUDE.md restates
m = re.search(r"addresses at\s+most (\d+) of (\d+) findings", FLAT)
if m:
    a, b = int(m.group(1)), int(m.group(2))
    sb_pairs = set(re.findall(r"at most (\d+) of (?:the )?(\d+)", SB))
    print(f"  CLAUDE.md: 'at most {a} of {b} findings'. The analysis states: {sorted(sb_pairs)}")
    if b != TRUTH["skill_findings"]:
        fail("9", f"the denominator {b} is neither the register's {TRUTH['skill_findings']} "
                  f"nor stable inside the analysis itself")
    judge("9", "the analysis states this arithmetic against two different denominators "
               "(§3.1 uses 160, §2 and §6 use 168). Whichever CLAUDE.md carries, it should "
               "carry the same one — and the analysis should be corrected, not this file.")

head(10, "INTERNAL CONSISTENCY — any figure CLAUDE.md states twice must agree with itself")
def consistent(label, pattern):
    vals = Counter(v.lower() for v in re.findall(pattern, FLAT))
    if len(vals) > 1:
        fail("10", f"{label}: states {dict(vals)} — inconsistent")
    elif vals:
        ok(f"{label}: consistently {list(vals)[0]} ({sum(vals.values())} mentions)")
    else:
        warn("10", f"{label}: no occurrence — check the pattern")


consistent("register row total", r"(\d{3}) rows")
consistent("skill-finding total", r"(\d{3}) skill\s+findings")
consistent("cluster total", r"(\d{2}) clusters")
consistent("sentinel coverage", r"(\d{3}) of 198 files (?:are )?(?:un)?protected")
consistent("dual-variant shortfall", r"shortfall is \*\*(\d+)\*\*")
consistent("fixed runtime overhead", r"(?:about |~)?(\d+) minutes of fixed overhead")
consistent("per-paragraph cost", r"(\d\.\d) seconds a paragraph")
consistent("context share", r"(\d\.\d)% of the 1M window")
consistent("A4 report line count", r"([\d,]+)-line report")
consistent("blind-review citations", r"\*\*(\d+) `file:line` citations\*\*")
consistent("rebuild arithmetic", r"at most 94 of the (\d+) recorded findings")
consistent("marker shortfall, whole tree", r"\*\*(\d+)\*\* whole-tree")
consistent("published file count", r"(\d{3}) files per variant")

head(11, "QUOTATIONS ATTRIBUTED TO ANOTHER FILE — checked verbatim against that file")
QUOTES = [
    ("a grep over source counts a mechanism wherever a message merely describes it", A3, "A3"),
    ("The fold is a filter, not a verdict", A3, "A3"),
    ("the package does not describe itself to the person who installs it", REG, "the register"),
    ("Re-run the compliance scan until it exits 0", REG, "the register (quoting the skill)"),
    ("Hard rules. Non-negotiable. Enforced by the skill's gates.", REG, "the register (quoting SKILL.md)"),
]
for q, src, name in QUOTES:
    if not present(q):
        print(f"  [note] CLAUDE.md does not (yet) carry: {q[:60]!r}")
        continue
    if re.sub(r"\s+", " ", q).lower() in re.sub(r"\s+", " ", src).lower():
        ok(f"verbatim in {name}: {q[:64]!r}")
    else:
        fail("11", f"attributed to {name} but not found there: {q[:70]!r}")

head(12, "GRADES — the A1/A2 table against the register's own list")
tbl = dict(re.findall(r"^\| \*?\*?(D\d\d\w?)\*?\*? \|[^|]*\|[^|]*\| \*\*(\d\.\d)\*\*", CMD, re.M))
regline = dict(re.findall(r"(D\d\d\w?) (\d\.\d)", REG[:REG.index("## How to read this")]))
common = sorted(set(tbl) & set(regline))
bad = [d for d in common if tbl[d] != regline[d]]
if bad:
    fail("12", f"grade mismatch on {bad}: CLAUDE.md {[tbl[d] for d in bad]} vs "
               f"register {[regline[d] for d in bad]}")
else:
    ok(f"all {len(common)} grades agree with the register: "
       + " ".join(f"{d}={tbl[d]}" for d in common))

head(13, "TWO SMALLER FIGURES, and the runtime range against the A1 table")
active = [float(x) for x in re.findall(r"\| \*?\*?\d\.\d\*?\*? \| ([\d.]+) min", CMD)]
if active:
    lo, hi = min(active), max(active)
    print(f"  the A1 table's ACTIVE column runs {lo} to {hi} minutes over {len(active)} runs")
    if present("18–50 minutes") or present("18-50 minutes"):
        if lo < 18:
            judge("13", f"'18–50 minutes' rounds the low end up: the fastest recorded run "
                        f"is {lo} min. Harmless as a published expectation, but it is a "
                        f"rounded figure sitting beside exact ones — say 'about 18 to 50'.")
        else:
            ok("the 18–50 minute range matches the table")
else:
    warn("13", "could not read the ACTIVE column")

if present("has 17 criteria"):
    if present("excludes one criterion that cannot be compared across runs"):
        ok("the 17-criteria / sixteen-compared discrepancy is reconciled in the text")
    else:
        judge("13", "the file says the grader has 17 criteria; the register's pairwise "
                    "comparison uses 16. Both are true, but nothing reconciles them.")

head(14, "SELF-DESCRIPTION — claims CLAUDE.md makes about its own structure")
charter = re.findall(r"^## (\d)\. (.+)$", CMD, re.M)
print(f"  sections: {[f'{a}. {b[:44]}' for a, b in charter]}")
if [a for a, _ in charter] != list("1234567"):
    fail("14", f"the file does not run 1-7: {[a for a, _ in charter]}")
else:
    ok("the file runs 1-7, as §1.6 says it does")
# §1.6's contents table must list every section that exists, and no others.
#
# SCOPED TO §1.6, and it was not before. The needle `^| **N** | ` matches ANY table row
# beginning with a bolded single digit, anywhere in the file — so §3.1's four-step table and
# §7's branch-state table were both being read as if they were the contents. It went unnoticed
# only because those tables happened to use 1-7 too; the moment a handoff table gained a row
# for BRANCH 0, the check reported that §1.6 lists a section 0. §1.6 was correct throughout.
# A needle that matches the right thing by coincidence is not a needle.
_toc_block = re.search(r"^### 1\.6 [^\n]*\n(.*?)(?=^## |\Z)", CMD, re.S | re.M)
toc = set(re.findall(r"^\| \*\*(\d)\*\* \| ", _toc_block.group(1), re.M)) if _toc_block else set()
if not _toc_block:
    fail("14", "§1.6 could not be located, so its contents table was never checked")
elif toc != set("1234567"):
    fail("14", f"§1.6's contents table lists {sorted(toc)}, not 1-7")
else:
    ok("§1.6's contents table matches the sections that exist")
# every subsection referenced as §N.M must exist
# strip references that name another document first -- "`STEP-B-ANALYSIS.md` §9.3" is not
# an internal reference, and treating it as one reported a false dangling link.
_internal = re.sub(r"`[A-Z0-9\-]+\.md`[^.\n]{0,40}?§\d[\d.]*", " ", CMD)
_internal = re.sub(r"(?:its|Its|that document's|the plan's|§\d of `[^`]+`)\s+§\d[\d.]*", " ", _internal)
refs = set(re.findall(r"§(\d\.\d+)", _internal))
subs = set(re.findall(r"^### (\d\.\d+) ", CMD, re.M))
dangling = sorted(r for r in refs if r not in subs)
if dangling:
    fail("14", f"§N.M reference(s) with no such subsection: {dangling}")
else:
    ok(f"all {len(refs)} internal subsection references resolve ({len(subs)} subsections)")
# the two split-out documents must exist and be referenced
for name in ("OPUS-5-MIGRATION.md", "DECISIONS-LOG.md"):
    exists, cited = (ROOT / name).exists(), f"`{name}`" in CMD
    (ok if (exists and cited) else lambda m: fail("14", m))(
        f"{name}: exists={exists} referenced={cited}")
size = (ROOT / "CLAUDE.md").stat().st_size
print(f"  CLAUDE.md is {size:,} bytes ({size / 1000:.0f} KB)")
arch_dir = PRIV / "claude-md-archive"
if arch_dir.exists():
    for p in sorted(arch_dir.iterdir()):
        print(f"    archive: {p.name} {p.stat().st_size:,} bytes")
    pre = arch_dir / "CLAUDE-2026-07-31-pre-rewrite.md"
    if present("216 KB → this"):
        if pre.exists():
            kb = pre.stat().st_size / 1000
            (ok if 210 <= kb <= 222 else lambda m: fail("14", m))(
                f"the pre-rewrite archive is {kb:.0f} KB (claim: 216 KB)")
        else:
            fail("13", "the named pre-rewrite archive does not exist")
else:
    warn("13", "the claude-md-archive folder was not found")

head(15, "THE NEW CONTENT — §6.3's envisaged tree, and §3's step/branch mapping")
# §6.3 projects what the build does to the tree. Each row must trace to a branch that
# exists in the plan, and the two numbers it states must be defensible.
if present("198 files becomes roughly 200 to 205 per variant"):
    manifest_rows = len(re.findall(r"\*\*A manifest per tree\*\*", CMD))
    if manifest_rows and present("the plan does not say how many"):
        ok("§6.3 states the file-count projection AND labels the part the plan leaves open "
           "— the manifest is the only committed +1")
    else:
        fail("15", "§6.3 gives a file-count projection without saying which part is a guess")
# the branch numbers §3 names must exist in the plan's own table
named_branches = set(int(x) for x in re.findall(r"\*\*(\d+) — ", CMD))
plan_branches = set(int(x) for x in re.findall(r"^\| \*\*(\d+)\*\* \|", sb_branch_table, re.M))
if named_branches - plan_branches:
    fail("15", f"CLAUDE.md names branch(es) the plan does not have: "
               f"{sorted(named_branches - plan_branches)}")
else:
    ok(f"every branch CLAUDE.md names ({sorted(named_branches)}) exists in the plan's table")
# the old charter names must map onto the plan's numbering exactly as §3.1 claims
for old_name, new_no, needle in [
        ("feature/baseline-and-inventory", 0, "baseline"),
        ("feature/test-harness", 1, "the harness"),
        ("feature/variant-parity-and-reconcile", 2, "the parity check")]:
    row = re.search(rf"^\| \*\*{new_no}\*\* \| ([^|]+)\|", sb_branch_table, re.M)
    got = row.group(1).strip() if row else "<<missing>>"
    (ok if needle in got else lambda m: fail("15", m))(
        f"{old_name} -> plan branch {new_no} ({got!r})")
# and the three sequencing facts §3.3 summarises must be the plan's three
if present("Three sequencing facts are absolute") or present("Three sequencing facts, not preferences"):
    ok("the sequencing facts are carried")
elif "Three sequencing facts" in SB:
    fail("15", "the plan states three absolute sequencing facts and CLAUDE.md carries none")

print()
print("=" * 92)
print(f"RESULT: {len(FAIL)} failure(s), {len(WARN)} warning(s), "
      f"{len(JUDGE)} judgement item(s)")
if FAIL:
    print("  FAILING CHECKS: " + " · ".join(dict.fromkeys(FAIL)))
if WARN:
    print("  WARNINGS IN:    " + " · ".join(dict.fromkeys(WARN)))
if JUDGE:
    print("  JUDGEMENT IN:   " + " · ".join(dict.fromkeys(JUDGE)))
print("=" * 92)
sys.exit(1 if FAIL else 0)
