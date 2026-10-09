"""Every Markdown table in the two SHIPPED trees renders as its header says: each row has the
header's column count, and no row stands loose of a header and its delimiter.

WHY THIS EXISTS (register E15, 2026-10-09). Two shipped sub-lexicons had carried, since the
rev44 baseline, rows whose width did not match their header -- nine three-cell rows under a
two-column header and four two-cell rows under three-column ones, the same thirteen lines in
both trees. A renderer silently DROPS a cell beyond the header and blanks a missing one, and
every script here that reads a lexicon maps a cell to its header by position. Nothing reported
it, because `tools/md_tables.py` checks the files it is NAMED, or the project's own documents
when named none, and never the Markdown files of the two trees. This suite names all of them.

THE RULE IS md_tables's OWN, NOT A SECOND COPY OF IT. The cell rule (PIPE) and the delimiter
rule (DELIM) are imported from tools/md_tables.py by name, and every file is ALSO run through
md_tables.check() itself, whose count must equal the number of rows this suite lists -- the
same question asked two ways, so the two walks cannot drift apart unnoticed. Only the per-row
listing is this file's own, because check() prints an excerpt and this suite names every row.

AND EVERY ARM CAN FAIL, PROVED ON EACH RUN: a copy of a real lexicon with a too-wide, a
too-narrow and a loose row planted at its end must be reported at exactly those three lines,
and a clean synthetic table -- including a row whose last cell is EMPTY, the form the E15 fix
wrote -- must not be.

    uv run python tests/test_shipped_tables.py

EXIT: 0 every file read, every table well-formed, every control fired . 1 a row is wrong (each
named) or a control failed . 2 VOID -- a tree is missing, a file could not be read or decoded,
or a tracked file is not among the files read.
"""
import contextlib
import io
import subprocess
import sys
import tempfile
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import md_tables  # noqa: E402

PIPE, DELIM = md_tables.PIPE, md_tables.DELIM
TREES = ("uk", "us")
FAIL, VOID = [], []


def ok(label, cond, detail=""):
    print(f"  [{'OK  ' if cond else 'FAIL'}] {label}" + (f" -- {detail}" if detail and not cond else ""))
    if not cond:
        FAIL.append(label)


def problems(text):
    """(line, what, excerpt) for every row that does not fit -- md_tables's walk, listed whole."""
    lines = text.split("\n")
    out, hdr_width, prev_row = [], None, None
    for i, raw in enumerate(lines, 1):
        st = raw.strip()
        if st.startswith("|") and st.endswith("|"):
            if DELIM.match(st):
                if prev_row is None:
                    out.append((i, "delimiter with no header above", st[:70]))
                    continue
                hdr_width = len(PIPE.findall(prev_row))
                if len(PIPE.findall(st)) != hdr_width:
                    out.append((i, "delimiter width differs from its header", st[:70]))
                prev_row = st
                continue
            if hdr_width is None:
                nxt = lines[i].strip() if i < len(lines) else ""
                if not DELIM.match(nxt):
                    out.append((i, "row outside any table", st[:70]))
            elif len(PIPE.findall(st)) != hdr_width:
                out.append((i, f"{len(PIPE.findall(st)) - 1} cells under a "
                               f"{hdr_width - 1}-column header", st[:70]))
            prev_row = st
        else:
            if not st:
                hdr_width = None
            prev_row = None
    return out


def md_tables_count(path):
    """md_tables.check()'s own count for one file, its printing discarded."""
    with contextlib.redirect_stdout(io.StringIO()):
        return md_tables.check(str(path))


# ------------------------------------------------------------------ the population
print("THE SHIPPED TREES -- every Markdown table row matches its header")
for t in TREES:
    if not (ROOT / t).is_dir():
        VOID.append(f"tree {t}/ is missing")
on_disk = sorted({p.relative_to(ROOT).as_posix() for t in TREES if (ROOT / t).is_dir()
                  for p in (ROOT / t).rglob("*.md")})
r = subprocess.run(["git", "-c", "core.quotePath=false", "ls-files", "-z", "--",
                    *[f"{t}/*.md" for t in TREES]], capture_output=True, cwd=ROOT)
tracked = sorted(x for x in r.stdout.decode("utf-8").split("\0") if x) if r.returncode == 0 else None
if tracked is None:
    VOID.append("git ls-files failed, so the tracked set cannot be compared")
else:
    unread = sorted(set(tracked) - set(on_disk))
    if unread:
        VOID.append(f"{len(unread)} tracked file(s) not on disk, so not read: {unread[:5]}")

texts = {}
for rel in on_disk:
    try:
        texts[rel] = (ROOT / rel).read_bytes().decode("utf-8")
    except (OSError, UnicodeDecodeError) as e:
        VOID.append(f"could not read {rel}: {type(e).__name__}")
per_tree = {t: sum(1 for rel in texts if rel.startswith(t + "/")) for t in TREES}
print(f"  FILES READ: {len(texts)} ({', '.join(f'{t} {n}' for t, n in per_tree.items())}); "
      f"tracked: {len(tracked) if tracked is not None else '?'}; on disk: {len(on_disk)}")
for t in TREES:
    if per_tree[t] == 0:
        VOID.append(f"no Markdown file read in {t}/")

found = 0
disagree = []
for rel, text in texts.items():
    rows = problems(text)
    for ln, what, ex in rows:
        print(f"    {rel}:{ln}  {what}  {ex}")
    found += len(rows)
    theirs = md_tables_count(ROOT / rel)
    if theirs != len(rows):
        disagree.append(f"{rel}: this suite {len(rows)}, md_tables.check {theirs}")
ok(f"every table row in the {len(texts)} files matches its header", found == 0,
   f"{found} row(s) do not, each listed above")
ok("md_tables.check() counts the same rows in every file", not disagree, "; ".join(disagree[:5]))

# ------------------------------------------------------------------ the controls
print("\nCONTROLS -- the check can fail, and does not fire on a sound table")
base_rel = "uk/sub-lexicons/italian-finance-banking.md"
base = texts.get(base_rel)
if base is None:
    VOID.append(f"control base {base_rel} was not read")
else:
    base_rows = len(problems(base))
    planted = base.rstrip("\n") + ("\n\n| Planted | Header |\n|---|---|\n| one | two | three |\n"
                                   "| lonely |\n\n| loose | row |\n")
    n0 = planted.count("\n", 0, planted.index("| one | two | three |")) + 1
    want = {n0, n0 + 1, n0 + 3}
    got = {ln for ln, _, _ in problems(planted)[base_rows:]}
    ok("CONTROL: the check must fail on a too-wide, a too-narrow and a loose row planted in a copy "
       "of a real lexicon, at exactly their lines", got == want, f"wanted {sorted(want)}, got {sorted(got)}")
    with tempfile.TemporaryDirectory() as td:
        pf = Path(td) / "planted.md"
        pf.write_bytes(planted.encode("utf-8"))
        theirs = md_tables_count(pf)
        ok("CONTROL: md_tables.check() must fail on the same three planted rows",
           theirs == base_rows + 3, f"md_tables.check {theirs}, expected {base_rows + 3}")
clean = ("| A | B | C |\n|---|---|---|\n| a | b | c |\n| a | b | |\n| a | `x \\| y` | c |\n\n"
         "| One | Two |\n|:--|--:|\n| 1 | 2 |\n")
ok("CONTROL: a sound table -- an empty last cell and an escaped pipe included -- is not reported",
   problems(clean) == [], f"reported {problems(clean)}")

print()
if VOID:
    for v in VOID:
        print(f"  VOID: {v}")
    print(f"VOID -- not every shipped file was read; this is not a pass. {len(FAIL)} failure(s) "
          f"among what was read.")
    sys.exit(2)
print(f"{'PASS' if not FAIL else 'FAIL'} -- {len(FAIL)} failure(s); {len(texts)} files read, "
      f"{found} mismatched row(s)")
sys.exit(1 if FAIL else 0)
