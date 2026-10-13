# -*- coding: utf-8 -*-
"""THE CORPUS FINGERPRINT SKIPS A RUN ONLY WHEN NOTHING IT READ HAS MOVED - tools/corpus_fingerprint.py.

Everything runs on a SYNTHETIC repository in a temporary folder - a stand-in arm that reads its inputs every
way the real arms do - so no real corpus file, and no tracked file of this repository, is ever touched.

  0  PARSING: an interpreter is known by name, never by a package that starts with the word; `uv run`
     option values are skipped; -I, -E and -S are escapes and -X is not; two `-c` codes are two identities.
  1  RECORD. The stand-in arm imports a module, loads one from a path built at run time, reads a file in a
     sibling folder, lists a folder, reads a file and puts it back, tests whether an optional file exists,
     starts a Python child that opens a data file and a `uv run --with lxml python` child that hands lxml
     paths through parse, ElementTree(file=) and XMLSchema(file=), asks git for HEAD, and writes then reads a file
     of its own. The record must hold EXACTLY the eleven repository inputs - never the file the run wrote -
     and the one sibling-folder file, and print every child accounted for.
  2  CHECK, untouched: PASS, and the last line printed is the arm's own closing line.
  3  RED FIRST: a one-byte edit to each of the eleven repository inputs and to the sibling-folder file turns
     the check FAIL - each of these checks must fail, and is asserted to; put back, PASS. A file in the listed folder, the optional file appearing, a new commit,
     and a change to the tool itself each FAIL too. The run's own output file does not.
  4  VOID: no record for a command line; and a record is REFUSED, nothing written, when a Python child
     escapes the trace - started with -I, or with PYTHONPATH stripped and no flag at all, or a stripped `-c`
     child masked by another `-c` child that did report - when a process is started by os.system, when an
     input is changed during the run by a child the trace cannot see, or when the arm fails.
  5  RUN: skips the arm on a PASS, runs and re-records it after an edit.
  6  CONFIDENTIALITY: no output, of any case, names the sibling folder.

FP_TEST_TOOL names another copy of the tool to test - how a deliberately broken copy is shown to turn this
suite red, so the suite is known to catch what each part of the tool exists for.

    uv run --with lxml python tests/test_corpus_fingerprint.py
"""
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
ROOT = Path(__file__).resolve().parent.parent
TOOL = Path(os.environ.get("FP_TEST_TOOL") or ROOT / "tools" / "corpus_fingerprint.py")
FAIL, CHECKED = [], 0
EXPECT = "0 failure(s), 0 void"
CLOSING = "  7 check(s), 0 failure(s), 0 void"
INPUTS = {"arm.py", "lib/helper.py", "plugins/plug.py", "child.py", "child_lx.py", "data.txt", "doc.xml",
          "doc2.xml", "doc3.xml", "state.txt", "decl/a.txt"}

ARM = '''import importlib.util, os, subprocess, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "lib"))
import helper
spec = importlib.util.spec_from_file_location("plug", HERE / "plugins" / ("pl" + "ug.py"))
plug = importlib.util.module_from_spec(spec)
spec.loader.exec_module(plug)
corpus = (Path(os.environ["FP_TEST_SIBLING"]) / "corpus.txt").read_text(encoding="utf-8")
names = sorted(os.listdir(HERE / "inputs"))
state = (HERE / "state.txt").read_bytes()
(HERE / "state.txt").write_bytes(state)
decl = (HERE / "decl" / "a.txt").read_text(encoding="utf-8")
optional = (HERE / "decl" / "opt.txt").is_file()
flags = ["-I"] if "--escape" in sys.argv else []
env = None
stripped = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
if "--strip-env" in sys.argv:
    env = stripped
r1 = subprocess.run([sys.executable, *flags, str(HERE / "child.py"), str(HERE / "data.txt")],
                    capture_output=True, text=True, env=env)
r2 = subprocess.run(["uv", "run", "--with", "lxml", "python", str(HERE / "child_lx.py"), str(HERE / "doc.xml"),
                     str(HERE / "doc2.xml"), str(HERE / "doc3.xml")],
                    capture_output=True, text=True, cwd=os.environ["FP_TEST_UVCWD"])
if "--os-system" in sys.argv:
    os.system('"' + sys.executable + '" -c "pass"')
if "--external-touch" in sys.argv:
    (HERE / "ext.txt").read_text(encoding="utf-8")
    subprocess.run(["cmd", "/c", "echo touched>>" + str(HERE / "ext.txt")])
if "--masked-escape" in sys.argv:
    subprocess.run([sys.executable, "-c", "x = 1"], env=stripped)
    subprocess.run(["cmd", "/c", sys.executable, "-c", "x = 2"])
g = subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(HERE), capture_output=True, text=True)
(HERE / "out.txt").write_text("written by the run", encoding="utf-8")
own = (HERE / "out.txt").read_text(encoding="utf-8")
ok = (helper.VALUE == 1 and plug.VALUE == 2 and bool(corpus) and names == ["one.txt"] and bool(decl)
      and r1.returncode == 0 and r2.returncode == 0 and g.returncode == 0 and bool(own) and bool(state))
print("optional declaration present" if optional else "no optional declaration")
if "--fail" in sys.argv:
    ok = False
print("  7 check(s), %d failure(s), 0 void" % (0 if ok else 1))
sys.exit(0 if ok else 1)
'''
CHILD = "import sys\nopen(sys.argv[1], encoding='utf-8').read()\n"
CHILD_LX = ("import sys\nfrom lxml import etree\netree.parse(sys.argv[1])\netree.ElementTree(file=sys.argv[2])\n"
            "etree.XMLSchema(file=sys.argv[3])\n")
XSD = '<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema"><xs:element name="c"/></xs:schema>\n'


def ok(label, cond, detail=""):
    global CHECKED
    CHECKED += 1
    print(f"  {'ok  ' if cond else 'FAIL'}  {label}" + (f"  [{detail}]" if detail and not cond else ""))
    if not cond:
        FAIL.append(label)


def git(repo, *args):
    return subprocess.run(["git", "-c", "user.name=fp-test", "-c", "user.email=fp-test@example.invalid",
                           *args], cwd=str(repo), capture_output=True, text=True)


# ------------------------------------------------------------------------------------------ 0
print("\n0   PARSING")
_spec = importlib.util.spec_from_file_location("_fp_under_test", TOOL)
fp = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(fp)
ok("python, python3.14, pythonw and py are interpreters",
   all(fp.is_python(t) for t in ("python", "python3.14", "C:/x/pythonw.exe", "py")))
ok("python-docx and pytest are not", not fp.is_python("python-docx") and not fp.is_python("pytest"))
ok("`uv run --with python-docx python x.py` runs x.py",
   fp.launch(["uv", "run", "--with", "python-docx", "python", "x.py"]) == ("py", ["x.py"]))
ok("`uv run --python python3.14 python x.py` runs x.py",
   fp.launch(["uv", "run", "--python", "python3.14", "python", "x.py"]) == ("py", ["x.py"]))
ok("`uv run pytest` is a uv run of something else", fp.launch(["uv", "run", "pytest"]) == ("py-any", []))
ok("-I, -E, -S and -IB escape the trace; -X utf8, -Xdev, -B and -u do not",
   all(fp.py_identity([f, "x.py"], "/")[1] for f in ("-I", "-E", "-S", "-IB"))
   and not any(fp.py_identity(a + ["x.py"], "/")[1] for a in (["-X", "utf8"], ["-Xdev"], ["-B"], ["-u"])))
ok("two -c codes are two identities, one code is one",
   fp.py_identity(["-c", "x = 1"], "/")[0] != fp.py_identity(["-c", "x = 2"], "/")[0]
   == fp.py_identity(["-cx = 2"], "/")[0])

with tempfile.TemporaryDirectory(prefix="fp-test-", ignore_cleanup_errors=True) as td:
    td = Path(td)
    repo, sib, store = td / "repo", td / "sibling", td / "store"
    for rel, text in [("arm.py", ARM), ("lib/helper.py", "VALUE = 1\n"), ("plugins/plug.py", "VALUE = 2\n"),
                      ("child.py", CHILD), ("child_lx.py", CHILD_LX), ("data.txt", "data\n"),
                      ("doc.xml", "<a/>\n"), ("doc2.xml", "<b/>\n"), ("doc3.xml", XSD),
                      ("state.txt", "state\n"), ("decl/a.txt", "a\n"), ("inputs/one.txt", "one\n"),
                      ("ext.txt", "ext\n")]:
        (repo / rel).parent.mkdir(parents=True, exist_ok=True)
        (repo / rel).write_bytes(text.encode("utf-8"))
    sib.mkdir()
    (sib / "corpus.txt").write_bytes(b"corpus\n")
    git(repo, "init", "-q")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "fixture")
    env = dict(os.environ, FP_TEST_SIBLING=str(sib), FP_TEST_UVCWD=str(ROOT), PYTHONIOENCODING="utf-8",
               PYTHONDONTWRITEBYTECODE="1")
    outputs = []

    def tool(mode, *arm_flags, tool_path=TOOL, expect=EXPECT):
        cmd = [sys.executable, str(tool_path), mode, "--root", str(repo), "--watch", str(sib),
               "--store", str(store)] + (["--expect", expect] if expect else []) + \
              ["--", sys.executable, "arm.py", *arm_flags]
        r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", env=env,
                           stdin=subprocess.DEVNULL)
        out = (r.stdout or "") + (r.stderr or "")
        outputs.append(out)
        return r.returncode, out

    def last(out):
        lines = [ln for ln in out.splitlines() if ln.strip()]
        return lines[-1] if lines else ""

    def records():
        return sorted(store.glob("*.json")) if store.is_dir() else []

    # ------------------------------------------------------------------------------------------ 1
    print("\n1   RECORD")
    rc, out = tool("record")
    ok("record exits 0 on a passing arm", rc == 0, f"rc={rc}; {out[-600:]}")
    ok("every Python child is accounted for", "every one accounted for" in out, out[-600:])
    recs = records()
    ok("exactly one record written", len(recs) == 1, f"{len(recs)}")
    rec = json.loads(recs[0].read_bytes().decode("utf-8")) if recs else {}
    ok("the record holds EXACTLY the eleven repository inputs", set(rec.get("repo", {})) == INPUTS,
       f"extra {sorted(set(rec.get('repo', {})) - INPUTS)}, missing {sorted(INPUTS - set(rec.get('repo', {})))}")
    ok("...and not the file the run wrote", "out.txt" not in rec.get("repo", {}))
    ok("the one sibling-folder file, stored by path hash", len(rec.get("sibling", {})) == 1
       and all(len(k) == 64 for k in rec.get("sibling", {})))
    ok("the listed folder is recorded", "repo:inputs" in rec.get("listings", {}), sorted(rec.get("listings", {})))
    ok("the git command is recorded", [g["args"] for g in rec.get("git", [])] == [["rev-parse", "HEAD"]],
       rec.get("git"))
    ok("the record carries the arm's closing line", rec.get("closing") == CLOSING, rec.get("closing"))

    # ------------------------------------------------------------------------------------------ 2
    print("\n2   CHECK, UNTOUCHED")
    rc, out = tool("check", expect=None)
    ok("check PASSes on an untouched tree", rc == 0 and "PASS" in out, f"rc={rc}; {out[-400:]}")
    ok("its last line is the arm's own closing line", last(out) == CLOSING, last(out))
    ok("check does not run the arm", "under the trace" not in out)

    # ------------------------------------------------------------------------------------------ 3
    print("\n3   RED FIRST - each input, one byte")
    for rel in sorted(INPUTS):
        p = repo / rel
        before = p.read_bytes()
        p.write_bytes(before + (b"#" if rel.endswith(".py") else b" "))
        rc, out = tool("check", expect=None)
        ok(f"a one-byte edit to {rel} FAILs, naming it", rc == 1 and f"changed: {rel}" in out, f"rc={rc}")
        p.write_bytes(before)
        rc, out = tool("check", expect=None)
        ok(f"...and put back, PASS", rc == 0, f"rc={rc}")
    before = (sib / "corpus.txt").read_bytes()
    (sib / "corpus.txt").write_bytes(before + b" ")
    rc, out = tool("check", expect=None)
    ok("a one-byte edit to the sibling-folder file FAILs, unnamed", rc == 1
       and "1 sibling-folder file(s) changed or gone" in out, f"rc={rc}")
    (sib / "corpus.txt").write_bytes(before)
    rc, _ = tool("check", expect=None)
    ok("...and put back, PASS", rc == 0, f"rc={rc}")

    (repo / "inputs" / "two.txt").write_bytes(b"two\n")
    rc, out = tool("check", expect=None)
    ok("a new file in the listed folder FAILs", rc == 1 and "listing changed: inputs" in out, f"rc={rc}")
    (repo / "inputs" / "two.txt").unlink()
    rc, _ = tool("check", expect=None)
    ok("...and removed, PASS", rc == 0, f"rc={rc}")

    (repo / "decl" / "opt.txt").write_bytes(b"an optional declaration\n")
    rc, out = tool("check", expect=None)
    ok("an optional file appearing beside a read input FAILs - its folder's listing",
       rc == 1 and "listing changed: decl" in out, f"rc={rc}")
    (repo / "decl" / "opt.txt").unlink()
    rc, _ = tool("check", expect=None)
    ok("...and removed, PASS", rc == 0, f"rc={rc}")

    (repo / "out.txt").write_bytes(b"edited after the run\n")
    rc, _ = tool("check", expect=None)
    ok("the run's own output file is not an input: editing it still PASSes", rc == 0, f"rc={rc}")

    git(repo, "commit", "-q", "--allow-empty", "-m", "moves HEAD")
    rc, out = tool("check", expect=None)
    ok("a new commit FAILs - git rev-parse HEAD answers differently", rc == 1 and "git answers differently" in out,
       f"rc={rc}")
    git(repo, "reset", "-q", "--soft", "HEAD~1")
    rc, _ = tool("check", expect=None)
    ok("...and reset, PASS", rc == 0, f"rc={rc}")

    rc, out = tool("check", expect="12 failure(s)")
    ok("a closing line not containing what the driver expects FAILs", rc == 1, f"rc={rc}")

    copy = td / "toolcopy" / "corpus_fingerprint.py"
    copy.parent.mkdir()
    copy.write_bytes(TOOL.read_bytes())
    shutil.rmtree(store)
    rc, _ = tool("record", tool_path=copy)
    ok("a copy of the tool records", rc == 0, f"rc={rc}")
    copy.write_bytes(copy.read_bytes() + b"#")
    rc, out = tool("check", tool_path=copy, expect=None)
    ok("a change to the tool itself FAILs", rc == 1 and "this tool itself has changed" in out, f"rc={rc}")

    # ------------------------------------------------------------------------------------------ 4
    print("\n4   VOID AND REFUSED")
    rc, out = tool("check", "--never-recorded", expect=None)
    ok("no record for a command line: VOID, exit 2", rc == 2 and "VOID" in out, f"rc={rc}")
    n0 = len(records())
    rc, out = tool("record", "--escape")
    ok("a child started with -I: the record is VOID, exit 2", rc == 2 and "-I, -E or -S" in out, f"rc={rc}")
    rc, out = tool("record", "--strip-env")
    ok("a child with PYTHONPATH stripped and no flag: VOID, never reported", rc == 2
       and "never reported a trace" in out and "child.py" in out, f"rc={rc}; {out[-300:]}")
    rc, out = tool("record", "--masked-escape")
    ok("a stripped `-c` child masked by another `-c` child that reported: VOID", rc == 2
       and "never reported a trace" in out, f"rc={rc}; {out[-300:]}")
    rc, out = tool("record", "--os-system")
    ok("a process started by os.system: VOID, a route the trace cannot follow", rc == 2
       and "os.system" in out, f"rc={rc}; {out[-300:]}")
    rc, out = tool("record", "--external-touch")
    ok("an input changed during the run by a child the trace cannot see: VOID", rc == 2
       and "changed DURING the run" in out, f"rc={rc}; {out[-300:]}")
    rc, out = tool("record", "--fail")
    ok("a failing arm: exit 1, nothing recorded", rc == 1 and "FAILED" in out, f"rc={rc}")
    ok("...none of the six wrote a record", len(records()) == n0, f"{n0} -> {len(records())}")

    # ------------------------------------------------------------------------------------------ 5
    print("\n5   RUN")
    rc, out = tool("record")
    ok("the real tool records again", rc == 0, f"rc={rc}")
    rc, out = tool("run")
    ok("run on an untouched tree skips the arm and passes", rc == 0 and "PASS" in out
       and "under the trace" not in out and last(out) == CLOSING, f"rc={rc}")
    p = repo / "data.txt"
    before = p.read_bytes()
    p.write_bytes(before + b" ")
    rc, out = tool("run")
    ok("run after an edit runs the arm and re-records", rc == 0 and "under the trace" in out and "RECORDED" in out
       and last(out) == CLOSING, f"rc={rc}")
    rc, out = tool("check", expect=None)
    ok("...and the new record PASSes with the edit in place", rc == 0, f"rc={rc}")
    p.write_bytes(before)
    rc, out = tool("run", "--fail")
    ok("run on a failing arm with no record exits 1", rc == 1, f"rc={rc}")

    # ------------------------------------------------------------------------------------------ 6
    print("\n6   CONFIDENTIALITY")
    named = [i for i, o in enumerate(outputs) if str(sib) in o or "corpus.txt" in o]
    ok(f"no output of {len(outputs)} names the sibling folder or its file", not named, f"outputs {named}")

print("\n" + "=" * 88)
print(f"  {CHECKED} check(s), {len(FAIL)} failure(s)")
sys.exit(1 if FAIL else 0)
