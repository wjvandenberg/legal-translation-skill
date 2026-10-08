"""test_render_keep.py - branch 11, Step 10's wiring slice, sub-step 4: register I-33 in tools/render_diff.py.

What each arm asserts, on synthetic facts only -- nothing is rendered and no page is read:

  K1  --keep-into-logs without --under-review REFUSES, exit 2, a fixed marker, before anything is rendered
      or written; LT_LOGS_DIR points at an empty temporary folder, which stays empty.
  K2  the note beside the kept pages is GENERATED: keep_note, loaded from the file's own syntax tree and
      called on synthetic facts, names the change under review, the pin, the chain actually run -- both
      chains -- and the variant; the hand-written branch-7 body is gone from the file.
  K3  keep_dir names the document AND the variant: a uk and a us run of one document land in two folders.
  K4  REGISTER I-34 (branch 11's follow-up, 2026-10-08): a refused repack is reported from its FIXED text alone --
      refusal() names the gate by its own marker and, for the delivered check, the blocking classes, and never
      prints the context snippet repack's output can carry; repack() declares every side part KEPT through
      tools/keep_declarations.py before it runs repack; the --doc arm no longer copies July's
      comments_translations.json and headers_footers.json beside the notes; and no raw tail of repack's output
      is printed anywhere in the tool. And the code review's fixes: a real document's failed post_process or
      reorder is reported by exit code and gate marker, never a line of its output; a keep declaration that
      cannot be written is the arm's reported refusal, never a crash; and the --doc arm's temporary folder of
      real-document files is removed at exit whatever ends the run.

RED FIRST: run this file from a clean copy of 59981dd (temp/red_wiring), where every arm fails; K4 is red at
fa0a110, the last commit before it.

    uv run --with lxml python tests/test_render_keep.py
"""
import ast
import io
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parent.parent
TOOL = ROOT / "tools" / "render_diff.py"
MARKER = "REFUSED: --keep-into-logs needs --under-review"
FAIL, CHECKED = [], 0


def ok(label, cond, detail=""):
    global CHECKED
    CHECKED += 1
    print(f"  {'OK  ' if cond else 'XX  '} {label}" + (f"   ({detail})" if detail and not cond else ""))
    if not cond:
        FAIL.append(label)


def load(names):
    """The named top-level functions of render_diff.py, compiled on their own: the script runs its whole
    comparison at import, so it is never imported."""
    tree = ast.parse(TOOL.read_text(encoding="utf-8"))
    keep = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in names]
    ns = {"Path": Path}
    exec(compile(ast.Module(body=keep, type_ignores=[]), str(TOOL), "exec"), ns)
    return {n: ns.get(n) for n in names}


print("=" * 88)
print("SUB-STEP 4 — I-33: render_diff's kept pages, their note and their folder")
print("=" * 88)

print("\nK1  --keep-into-logs without --under-review refuses, and nothing is written")
logs = Path(tempfile.mkdtemp(prefix="render-keep-logs-"))
env = dict(os.environ, LT_LOGS_DIR=str(logs), PYTHONIOENCODING="utf-8", PYTHONDONTWRITEBYTECODE="1")
for extra, what in (([], "absent"), (["--under-review", "  "], "blank")):
    r = subprocess.run([sys.executable, str(TOOL), "--doc", "D00", "--keep-into-logs"] + extra,
                       capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=str(ROOT),
                       env=env, timeout=600)
    blob = (r.stdout or "") + (r.stderr or "")
    ok(f"--under-review {what}: exit 2 with the refusal marker", r.returncode == 2 and MARKER in blob,
       f"rc={r.returncode} {blob[-300:]}")
    ok(f"--under-review {what}: ...before anything rendered", "RENDERED PAGE COMPARISON" not in blob)
ok("the logs folder is still empty", list(logs.iterdir()) == [], str(list(logs.iterdir())))
shutil.rmtree(logs, ignore_errors=True)             # REVIEW FIX 8: holds on the failing path too

print("\nK2  the note is generated from the run's facts plus the --under-review line")
fn = load({"keep_note", "keep_dir", "keep_chain"})
if fn["keep_note"] is None:
    ok("keep_note exists in render_diff.py", False)
else:
    # REVIEW FIX 5 (2026-09-30 (3)): the pages WRITTEN, per arm -- the source here renders one page fewer, so
    # its page 5 was never written and the note must not say it was.
    wrote = {"old": [2, 5], "new": [2, 5], "source": [2]}
    for pp, chain in ((False, "apply -> repack"), (True, "apply -> post_process -> reorder -> repack")):
        for v in ("uk", "us"):
            note = fn["keep_note"]("2026-09-30 12:00:00", "D99", v, "abc1234", pp,
                                   "  sub-step 4 of the wiring slice  ", wrote, [5])
            ok(f"[{v}, post_process={pp}] the note names the change, the pin, the chain and the variant",
               all(x in note for x in ("under review:  sub-step 4 of the wiring slice", "pin (-old):    abc1234",
                                       f"chain run:     {chain}  ", f"variant:       {v}",
                                       "document:      D99", "pages changed: [5]")),
               note[:400])
            ok(f"[{v}, post_process={pp}] ...and the pages ACTUALLY written, per arm  the source's missing page 5 "
               "not claimed", "pages written: old [2, 5]  new [2, 5]  source [2]" in note, note[:600])
    ok("an arm that wrote nothing says NONE",
       "source NONE" in fn["keep_note"]("s", "D99", "uk", "abc1234", False, "x",
                                        {"old": [3], "new": [3], "source": []}, [3]))
    ok("...and says it is generated", "GENERATED by tools/render_diff.py" in note)
src = TOOL.read_text(encoding="utf-8")
ok("the hand-written branch-7 body is gone", "Branch 7 rendered comparison" not in src
   and "THE CHANGE UNDER REVIEW IS THE CONTAINER INVENTORY" not in src)
ok("the READ-ME is written from keep_note", 'write_bytes(keep_note(' in src)

print("\nK3  a uk and a us run land in two folders, each naming the document and the variant")
if fn["keep_dir"] is None:
    ok("keep_dir exists in render_diff.py", False)
else:
    a, b = fn["keep_dir"]("L", "D08 #2", "uk"), fn["keep_dir"]("L", "D08 #2", "us")
    ok("two different folders", a != b, f"{a} {b}")
    ok("each names the document and the variant", a.name == "D08n2-uk" and b.name == "D08n2-us", f"{a.name} {b.name}")
    ok("the folders are made by keep_dir where the pages are written", "dest = keep_dir(LOGS, label, args.variant)" in src)

print("\nK4  register I-34: a refusal reported from its fixed text, the side parts declared kept")
tree = ast.parse(src)
nodes = [n for n in tree.body
         if (isinstance(n, ast.FunctionDef) and n.name in ("refusal", "step_failure", "repack"))
         or (isinstance(n, ast.Assign) and any(isinstance(t, ast.Name)
                                               and t.id in ("_REPACK_GATES", "_CLASS_LINE", "_KEEP_FAILED")
                                               for t in n.targets))]


def _declare_fails(*_a, **_k):
    raise UnicodeDecodeError("utf-8", b"\xff", 0, 1, "a side part that is not UTF-8")


ns4 = {"re": __import__("re"), "subprocess": subprocess, "os": os, "Path": Path, "ROOT": ROOT,
       "args": type("Args", (), {"variant": "uk"})(), "write_keep_declarations": _declare_fails}
exec(compile(ast.Module(body=nodes, type_ignores=[]), str(TOOL), "exec"), ns4)
refusal = ns4.get("refusal")
SNIPPET = "Die geheime Klausel zur Vertragsstrafe"         # invented; stands in for a quoted line of a document


class Proc:
    def __init__(self, rc, out, err):
        self.returncode, self.stdout, self.stderr = rc, out, err


if refusal is None:
    ok("render_diff.py defines refusal()", False)
else:
    delivered = Proc(1, f"  WARNING (ADVISORY, not blocking): word/document.xml: x — '{SNIPPET}'\n"
                        "  side parts: read against the original - 2 text-bearing comments 1 header 1\n",
                     "RuntimeError: SKILL GATE FIRED — INTENTIONAL BLOCK, NOT A SCRIPT ERROR. THE DELIVERED-DOCUMENT "
                     "CHECK REFUSED THIS DELIVERY: 3 blocking finding(s), so the archive was NEVER WRITTEN.\n"
                     "  side-comment/undeclared-kept: 2\n  side-hf/declared-source: 1\n  What repairs each:\n")
    said = refusal(delivered)
    ok("the delivered gate named, with its blocking classes",
       said == "refused by the delivered gate - side-comment/undeclared-kept 2, side-hf/declared-source 1", said)
    ok("...and the snippet repack's output carried is NOT in what is printed", SNIPPET not in said, said)
    remnant = Proc(1, f"  remnant: '{SNIPPET}'\n", "SOURCE-LANGUAGE REMNANT: 1 de remnant(s) in the repacked archive")
    ok("the remnant gate named by its marker, no class lines, no snippet",
       refusal(remnant) == "refused by the remnant gate", refusal(remnant))
    bare = Proc(1, f"some output\n{SNIPPET}", "")
    ok("no marker and an EMPTY stderr: the exit code, never the tail of stdout -- the shape that leaked",
       refusal(bare) == "exit 1, no gate marker recognised", refusal(bare))
rp = next((n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "repack"), None)
calls = [c.func.id for c in ast.walk(rp) if isinstance(c, ast.Call) and isinstance(c.func, ast.Name)] if rp else []
ok("repack() declares the side parts kept through tools/keep_declarations.py BEFORE it runs repack",
   "write_keep_declarations" in calls and rp is not None
   and ast.get_source_segment(src, rp).index("write_keep_declarations(")
   < ast.get_source_segment(src, rp).index("subprocess.run("), str(calls))
ok("...imported from the shared helper, never a copy of its own",
   "from keep_declarations import write_keep_declarations" in src and "def write_keep_declarations" not in src)
ok("the --doc arm no longer copies July's comments_translations.json and headers_footers.json",
   'for n in ("paragraphs.json", ".validate-state.json", "_boldmap.json"):' in src
   and '"comments_translations.json", "headers_footers.json",\n                      "_boldmap.json"' not in src)
ok("no raw tail of repack's output is printed anywhere in the tool",
   "(rp.stderr or rp.stdout" not in src, "a slice of rp.stderr/rp.stdout is still printed")
# REVIEW FIXES, 2026-10-08: the same leak class one call earlier, and a new step's crash path.
step_failure = ns4.get("step_failure")
ok("a real document's failed post_process or reorder is reported by exit code and gate marker, never a line "
   "of its output",
   step_failure is not None
   and step_failure(Proc(1, f"x\n{SNIPPET}", "")) == "exit 1"
   and step_failure(Proc(1, SNIPPET, "SKILL GATE FIRED")) == "exit 1, a SKILL GATE fired"
   and "step_failure(pp)" in src and "_gate_line(pp)" not in src)
repack_fn = ns4.get("repack")
try:
    got = repack_fn(Path("s"), Path("src.docx"), Path("d.xml"), Path("o.docx"), Path("n/paragraphs.json")) \
        if repack_fn else None
except Exception as exc:                            # noqa: BLE001 -- a raise IS the failure asserted against
    got = exc
ok("a keep declaration that cannot be written is THIS ARM's reported refusal, by type, never a crash",
   isinstance(got, tuple) and got[0] is None and refusal is not None
   and refusal(got[1]) == "refused by the keep declarations gate"
   and "UnicodeDecodeError" in got[1].stderr and "not UTF-8" not in got[1].stderr, repr(got)[:300])
ok("the --doc arm's temporary folder of real-document files is removed at interpreter exit, whatever ends the run",
   "atexit.register(shutil.rmtree, TMP, ignore_errors=True)" in src)

print()
print("=" * 88)
if FAIL:
    print(f"FAIL — {len(FAIL)} of {CHECKED} checks:")
    for f in FAIL:
        print(f"  ·  {f}")
    print("=" * 88)
    sys.exit(1)
print(f"PASS — {CHECKED} checks.")
print("=" * 88)
