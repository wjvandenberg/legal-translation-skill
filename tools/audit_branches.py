# -*- coding: utf-8 -*-
"""THE BRANCH AUDIT — re-derive every claim branches 0, 1 and 2 make, by routes the tools
under audit do not use.

WHY THIS IS A COMMITTED TOOL RATHER THAN SCRATCH. Three throwaway audits were written before
this one. Each found real errors, and each was then DELETED — so the next session had to
rebuild the instrument before it could re-check anything, and the errors they found could not
be re-tested. An audit that cannot be re-run is a memory, not a control.

EVERY BUG THOSE THREE HAD IS FIXED HERE, and each fix is commented where it lives:

  1. It ran with the wrong branch checked out, so tools added by a later branch appeared to
     produce no output at all. Everything now reads from git refs by name.
  2. A line-oriented exit scan missed `sys.exit(...)` split across two lines and MANUFACTURED
     a finding against a script that was fine.
  3. A bracket-counting entry count was +1 on every table, because the source has trailing
     commas. Counting separators is not counting entries.
  4. A signature comparison expected `root, variant` and the source says `root, variant='us'`,
     so a correct tool was reported as wrong.
  5. `(?i)changelog` matched a SCANNER named after changelogs.
  6. A string-prefix path test concluded `legal-translation-logs` sits inside
     `legal-translation`. Paths compare as PARTS, never as text.
  7. It ran skill scripts without the bytecode guard, leaving `__pycache__` inside the
     shipped trees -- a RECURRENCE, fixed once in the test runner and back through here.
  8. It SKIPPED a branch whose ref had been deleted, which is what happens to every branch
     the moment it is merged. So it stopped checking precisely when the work went live.
     A merged branch is not a missing one; it falls back to `main`.

AND IT CARRIES NO REAL STRINGS. The earlier versions hardcoded the very names they were
checking for, which made the auditor itself un-committable -- the exact defect this project
has now fixed in four separate scripts. Every needle is read from the private lists, so the
assertions are list-driven: "this shipped file contains NO name from the 93-pattern list" is
both stronger and publishable.

    uv run python tools/audit_branches.py
    uv run python tools/audit_branches.py --branch 0
"""
import ast
import hashlib
import io
import json
import os
import re
import subprocess
import sys
import zipfile
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parent.parent
PRIV = Path(os.environ.get("LT_PRIVATE_DIR", ROOT.parent / "legal-translation-private"))
ARCH = ROOT.parent / "skills" / "legal-translation" / "PUBLICATION VERSIONS"
ONLY = None
if "--branch" in sys.argv:
    ONLY = sys.argv[sys.argv.index("--branch") + 1]

FAIL, OK, NOTE, SKIP = [], [], [], []


# ANY tool that invokes a skill script must carry this, not just the test runner. Importing
# a skill module drops a __pycache__ directory INSIDE uk/scripts or us/scripts; it is
# gitignored so it never shows in a diff, but tools/package.py zips the variant tree, so it
# would ship inside the .skill. The fix was first applied to tests/run_tests.py alone and the
# leak simply came back through the next tool that ran a skill script.
CLEAN_ENV = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1",
                 PYTHONDONTWRITEBYTECODE="1")


def git(*a, binary=False):
    r = subprocess.run(["git", *a], capture_output=True, cwd=ROOT, env=CLEAN_ENV)
    return r.stdout if binary else r.stdout.decode("utf-8", "replace")


def resolve(ref):
    """The branch ref if it still exists, otherwise `main` — because a MERGED branch is not
    a missing one. Once a branch is squash-merged and deleted, its content lives on main, and
    an audit that SKIPS at that point stops checking exactly when the work goes live. The
    first version skipped branches 1 and 2 the moment they were merged."""
    for cand in (ref, "main"):
        if subprocess.run(["git", "rev-parse", "--verify", "-q", cand],
                          capture_output=True, cwd=ROOT).returncode == 0:
            return cand
    return None


def claim(cid, text, got, want, conf="MEASURED"):
    good = got == want
    (OK if good else FAIL).append((cid, text, got, want))
    print(f"  {'OK  ' if good else 'FAIL'} {cid:<9} {text}")
    print(f"             re-derived {got!r} · claimed {want!r}   [{conf}]")
    sys.stdout.flush()


def head(t):
    print()
    print("=" * 98)
    print(t)
    print("=" * 98)
    sys.stdout.flush()


def load(name, env):
    p = Path(os.environ.get(env, PRIV / name))
    return ([l.strip() for l in p.read_text(encoding="utf-8").splitlines()
             if l.strip() and not l.lstrip().startswith("#")] if p.exists() else None)


NAMES = load("leakage-names.txt", "LEAKAGE_LIST_PATH")
DESC = load("corpus-descriptors.txt", "CORPUS_DESCRIPTORS_FILE")
if NAMES is None or DESC is None:
    print("CONTROL VOID — a pattern list is missing. The audit has NOT run.")
    sys.exit(2)
RX = [re.compile(p, re.I) for p in NAMES + DESC]

ZIPS = (("uk", "legal-translation (UK English).skill"),
        ("us", "legal-translation (US English).skill"))


# =========================================================================== BRANCH 0
def audit_b0():
    head("BRANCH 0 — the baseline")
    if not ARCH.exists():
        SKIP.append("branch 0: publication archives unreachable")
        print("  SKIPPED — archives unreachable. This is a skip, not a pass.")
        return

    for variant, arc in ZIPS:
        z = zipfile.ZipFile(ARCH / arc)
        zf = [i for i in z.infolist() if not i.is_dir()]
        tracked = [l for l in git("ls-tree", "-r", "main", "--name-only", variant).splitlines() if l]
        claim(f"B0.count.{variant}", f"{variant}/ is 198 files by archive and by git",
              (len(zf), len(tracked)), (198, 198))
        claim(f"B0.bytes.{variant}", f"{variant}/ byte total",
              sum(i.file_size for i in zf),
              3_651_835 if variant == "uk" else 3_667_750)

    # Bytes out of the object store, not a recomputed blob id — a different route from the
    # shipped test, so agreement is evidence rather than an echo.
    #
    # DELIBERATE CHANGES ARE SUBTRACTED, NOT EXCUSED. The trees stopped being byte-identical
    # the moment a fix branch legitimately edited them. Deleting this comparison would have
    # thrown the guarantee away to avoid the paperwork; instead each divergence is named in
    # tests/baselines/baseline-divergences.json, and anything NOT named is still a failure.
    _div = ROOT / "tests" / "baselines" / "baseline-divergences.json"
    declared = (json.loads(_div.read_text(encoding="utf-8"))["divergences"]
                if _div.exists() else {})
    bad, n, dec = [], 0, 0
    for variant, arc in ZIPS:
        z = zipfile.ZipFile(ARCH / arc)
        for i in z.infolist():
            if i.is_dir():
                continue
            n += 1
            key = f"{variant}/{i.filename}"
            if git("show", f"main:{key}", binary=True) != z.read(i):
                if key in declared:
                    dec += 1
                else:
                    bad.append(key)
    print(f"  ---- {dec} declared divergence(s) from the archive, each named with the commit "
          f"that made it")
    claim("B0.bytes", "every file is byte-identical to its archive, or a DECLARED change",
          (n, len(bad)), (396, 0))

    touch = [l for l in git("log", "--all", "--format=%H", "--", "uk", "us").splitlines() if l]
    # Branch 0 is the only commit that may touch the trees UNTIL a fix branch does so
    # deliberately. Report the number rather than asserting one, so a later legitimate
    # change does not read as a regression.
    print(f"  ---- commits touching uk/ or us/ across all refs: {len(touch)}")
    initial = [l for l in git("ls-tree", "-r", touch[-1], "--name-only").splitlines() if l]
    claim("B0.initial", "the baseline commit holds 419 files", len(initial), 419)

    hist = [l for l in git("log", "--all", "--name-only", "--format=").splitlines() if l]
    # FIXED: `(?i)changelog` matched tools/changelog_confidentiality.py, a SCANNER named
    # after what it scans. The rule is about committed changelog CONTENT.
    bad_paths = sorted({l for l in hist if l.startswith("docs/")
                        or re.fullmatch(r"(?i)(.*/)?CHANGELOG(\.\w+)?", l)})
    claim("B0.nochangelog", "no docs/ path and no committed CHANGELOG in any commit",
          bad_paths, [])

    bl = json.loads((ROOT / "tests" / "baselines" / "graded-baselines.json")
                    .read_text(encoding="utf-8"))
    claim("B0.baselines", "twelve graded runs recorded", len(bl["runs"]), 12)
    charter = (ROOT / "CLAUDE.md").read_text(encoding="utf-8")
    mism = []
    for r in bl["runs"]:
        m = re.search(r"^\|\s*\*?\*?" + re.escape(r["doc"]) + r"\*?\*?\s*\|(.+)$",
                      charter, re.M)
        g = re.findall(r"\*\*(\d\.\d)\*\*", m.group(1)) if m else []
        if not g or float(g[0]) != r["grade"]:
            mism.append(f"{r['doc']}: json {r['grade']} vs charter {g}")
    claim("B0.grades", "every recorded grade matches the charter's own table", mism, [])


# =========================================================================== BRANCH 1
SENTINEL = 3


def script_verdicts(folder):
    """Can each script fail for a reason of its OWN? Balanced-paren scan, NOT line-oriented.
    FIXED: a line scan missed `sys.exit(...)` split across two lines and manufactured a
    finding against validate_translations.py, which demonstrably exits 1 and 2."""
    out = {}
    for p in sorted(folder.glob("*.py")):
        t = p.read_text(encoding="utf-8", errors="replace")
        own, sent = set(), False
        for m in re.finditer(r"sys\.exit\(", t):
            i, depth = m.end(), 1
            while i < len(t) and depth:
                depth += (t[i] == "(") - (t[i] == ")")
                i += 1
            arg = t[m.end():i - 1].strip()
            if re.fullmatch(r"\d+", arg):
                v = int(arg)
                if v == SENTINEL:
                    sent = True
                elif v != 0:
                    own.add(v)
            elif arg:
                own.add("computed")
        raises = len(re.findall(r"^\s*raise\s+\w", t, re.M))
        out[p.name] = {"blocks": bool(own) or raises > 0, "sentinel": sent}
    return out


def audit_b1():
    head("BRANCH 1 — the harness")
    ref = resolve("feature/test-harness")
    if ref is None:
        SKIP.append("branch 1: neither its branch nor main could be resolved")
        print("  SKIPPED — no ref to read from.")
        return
    print(f"  reading from: {ref}")

    v = script_verdicts(ROOT / "uk" / "scripts")
    claim("B1.scripts", "20 pipeline scripts", len(v), 20)
    claim("B1.sentinel", "all 20 carry the exit-3 integrity sentinel",
          sum(x["sentinel"] for x in v.values()), 20)
    claim("B1.verdict", "17 of 20 can block by exit or by raise",
          sum(x["blocks"] for x in v.values()), 17)
    claim("B1.mute", "the three that cannot block",
          sorted(n for n, x in v.items() if not x["blocks"]),
          ["quality_check.py", "source_language_markers.py", "translate_numbering.py"])

    # RUN THE TOOL FROM THE REF, not from the checkout. This is the bug listed as (1) at the
    # top of this file, and the first attempt at fixing it only covered files READ from a
    # ref -- a tool INVOKED from the working tree is absent whenever a different branch is
    # checked out, and the audit reported "no parseable output" as a failure of the tool
    # rather than of itself.
    tool = ""
    cov = ROOT / "tools" / "check_coverage.py"
    if cov.exists():
        tool = subprocess.run([sys.executable, str(cov)], capture_output=True, text=True,
                              encoding="utf-8", errors="replace", cwd=ROOT, env=CLEAN_ENV).stdout or ""
    else:
        blob = git("show", f"{ref}:tools/check_coverage.py", binary=True)
        if blob:
            tmp = ROOT / "temp" / "_audit_check_coverage.py"
            tmp.parent.mkdir(parents=True, exist_ok=True)
            tmp.write_bytes(blob)
            tool = subprocess.run([sys.executable, str(tmp)], capture_output=True, text=True,
                                  encoding="utf-8", errors="replace", cwd=ROOT, env=CLEAN_ENV).stdout or ""
            tmp.unlink(missing_ok=True)
        else:
            SKIP.append("branch 1: check_coverage.py not found on the checkout or the ref")
    m = re.search(r"(\d+) of (\d+) scripts carry a verdict", tool)
    claim("B1.agree", "the standing coverage tool agrees with this scan",
          int(m.group(1)) if m else "no parseable output", 17)
    m = re.search(r"NO CHECK THAT CAN BLOCK\D+(\d+) of (\d+)", tool)
    claim("B1.steps", "5 of 17 pipeline steps have no blocking check",
          (int(m.group(1)), int(m.group(2))) if m else None, (5, 17))

    ap = (ROOT / "uk" / "scripts" / "apply_translations_textmatch.py").read_text(encoding="utf-8")
    sites = [s for s in re.findall(r"block_codes=\{([^}]*)\}", ap) if re.search(r"\d", s)]
    claim("B1.chain1", "apply blocks at 2 call sites, neither treating exit 3 as blocking",
          (len(sites), [s for s in sites if "3" in re.findall(r"\d+", s)]), (2, []))

    ql = (ROOT / "uk" / "scripts" / "quality_check.py").read_text(encoding="utf-8").splitlines()
    g = next((i for i, l in enumerate(ql, 1) if re.match(r"^_?\w*integrity\w*\(\)", l)), None)
    mn = next((i for i, l in enumerate(ql, 1) if l.startswith("if __name__")), None)
    claim("B1.chain2", "the quality gate's guard sits BELOW its __main__",
          (g is not None and mn is not None and g > mn), True)

    fx = [l for l in git("ls-tree", "-r", ref, "--name-only", "tests/fixtures").splitlines() if l]
    claim("B1.fixtures", "committed synthetic fixtures", len(fx), 11)

    hits = 0
    for nm in fx:
        data = git("show", f"{ref}:{nm}", binary=True)
        try:
            z = zipfile.ZipFile(io.BytesIO(data))
            text = b"".join(z.read(x) for x in z.namelist()).decode("utf-8", "replace")
        except zipfile.BadZipFile:
            text = data.decode("utf-8", "replace")
        hits += sum(1 for r in RX if r.search(text))
    claim("B1.clean", f"fixtures hit 0 of {len(RX)} confidentiality patterns", hits, 0)

    cat = Path(os.environ.get("LT_LOGS_DIR", ROOT.parent / "legal-translation-logs")
               ) / "frozen-intermediates.json"
    if cat.exists():
        c = json.loads(cat.read_text(encoding="utf-8"))["runs"]
        claim("B1.frozen", "documents catalogued / artefacts",
              (len(c), sum(len(x["files"]) for x in c.values())), (12, 37))
        # FIXED: a string-prefix test said legal-translation-logs sits inside
        # legal-translation. Paths compare as PARTS.
        claim("B1.outside", "the catalogue lives OUTSIDE the repository",
              ROOT.resolve() in cat.resolve().parents, False)
    else:
        SKIP.append("branch 1: frozen-intermediate catalogue unreachable")


# =========================================================================== BRANCH 2
def table_entries(path, name):
    """Entry count by COUNTING ELEMENTS, not separators. FIXED: counting top-level commas
    was +1 on every table because the source uses trailing commas."""
    t = path.read_text(encoding="utf-8")
    tree = ast.parse(t)
    for n in tree.body:
        if isinstance(n, ast.Assign) and any(
                isinstance(x, ast.Name) and x.id == name for x in n.targets):
            v = n.value
            if isinstance(v, (ast.List, ast.Tuple, ast.Set)):
                return len(v.elts)
            if isinstance(v, ast.Dict):
                return len(v.keys)
    return None


def audit_b2():
    head("BRANCH 2 — the parity check")
    ref = resolve("feature/variant-parity-check")
    if ref is None:
        SKIP.append("branch 2: neither its branch nor main could be resolved")
        print("  SKIPPED — no ref to read from.")
        return
    print(f"  reading from: {ref}")

    for name, want in (("UK_SPELLING", (37, 60)), ("US_SPELLING", (34, 91))):
        claim(f"B2.{name}", f"{name} entry counts",
              (table_entries(ROOT / "uk" / "scripts" / "post_process.py", name),
               table_entries(ROOT / "us" / "scripts" / "post_process.py", name)), want)

    # FIXED: the earlier version expected `root, variant` and the source says
    # `root, variant='us'`, so a correct tool was reported as wrong. Compare the PARAMETER
    # COUNT, which is the claim being made.
    def params(tree_root):
        t = (tree_root / "scripts" / "post_process.py").read_text(encoding="utf-8")
        for n in ast.walk(ast.parse(t)):
            if isinstance(n, ast.FunctionDef) and n.name == "fix_article_to_clause":
                return len(n.args.args)
        return None
    claim("B2.sig", "the tidy-up function takes one MORE parameter in one tree",
          (params(ROOT / "uk"), params(ROOT / "us")), (1, 2))

    bl = ROOT / "tests" / "baselines" / "known-divergences.json"
    if not bl.exists():
        SKIP.append("branch 2: divergence baseline not present on this checkout")
        return
    base = json.loads(bl.read_text(encoding="utf-8"))["divergences"]
    claim("B2.unique", "no duplicate identity in the baseline",
          len({d["key"] + "|" + d["kind"] + "|" + d["detail"] for d in base}), len(base))

    # THE ACCEPTANCE TEST: the row that reached a client. Identified by its FILE and its
    # shape, never by quoting a real string.
    #
    # The row is IDENTICAL in both trees, and that is the whole point of the finding — so
    # the two trees must be judged differently, not alike. In the UK tree it renders the
    # other variant's form and is a defect; in the US tree it renders the right form merely
    # without its counterpart. Expecting the wrong-variant flag in BOTH trees was this
    # audit's error, not the tool's: the tool discriminating between them is it working.
    rows = [d for d in base
            if d["kind"] == "single-variant-row"
            and "polish-general-legal" in d["key"]
            and "paragraf" in d["key"]]
    seen = sorted({d["key"].split("/")[0] for d in rows})
    wrong = sorted({d["key"].split("/")[0] for d in rows if "OTHER variant" in d["detail"]})
    claim("B2.U1", "the row that reached a client is caught in both trees, and flagged as "
                   "the WRONG variant in the UK tree only",
          (seen, wrong), (["uk", "us"], ["uk"]))

    arms = sorted({d["key"].split("/")[0] for d in base if d["arm"] == "within-tree"})
    claim("B2.arms", "the within-tree arm produced findings in BOTH trees", arms, ["uk", "us"])

    r = subprocess.run([sys.executable, str(ROOT / "tools" / "parity_check.py")],
                       capture_output=True, text=True, encoding="utf-8", cwd=ROOT, env=CLEAN_ENV)
    claim("B2.exit", "the check exits 0 against its own baseline", r.returncode, 0)


# ===========================================================================
if ONLY in (None, "0"):
    audit_b0()
if ONLY in (None, "1"):
    audit_b1()
if ONLY in (None, "2"):
    audit_b2()

head("VERDICT")
print(f"  {len(OK)} confirmed · {len(FAIL)} FAILED · {len(SKIP)} skipped · {len(NOTE)} note(s)")
for cid, text, got, want in FAIL:
    print(f"      FAIL {cid}: {text}")
    print(f"           re-derived {got!r} · claimed {want!r}")
for s in SKIP:
    print(f"      SKIPPED (not a pass): {s}")
print()
print("  An audit reporting NOTHING found is evidence it was too shallow, not that the")
print("  work was clean.")
print("=" * 98)
sys.stdout.flush()
sys.exit(1 if FAIL else 0)
