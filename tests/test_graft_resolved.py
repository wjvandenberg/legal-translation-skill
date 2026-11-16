"""test_graft_resolved.py - sub-step 16.2: tools/graft_resolved.py, the frozen notes given today's `resolved` at load
time, in memory (PLAN-2-step-b.md section 3.16).

ON INVENTED DOCUMENTS ONLY, built in a temporary directory; nothing is read from the corpus. The frozen notes are
the tree's own extraction of the invented document with `resolved` taken out and an operator's fields added, as a
July file is. What each arm asserts:

  1  TP: the key restored on exactly the runs today's extraction gives it - a paragraph bold by its STYLE, a run
     italic by its CHARACTER STYLE - and on no other; every entry aligned; the operator's fields untouched; the
     list it was given not mutated
  2  the bytes handed over: extraction's own format, a non-ASCII letter written as itself; where nothing is
     grafted, the notes file's OWN bytes, unchanged
  3  FP, THE PLANTED MISALIGNMENT, each VOID and never a pass: one run's text changed (the plan's control); a run's
     bold flipped, its key named; an entry's text changed; an idx missing, an idx extra, an idx twice; a run
     missing; a frozen run carrying a resolved that is not today's - and one carrying today's counted, not VOID
  4  today's extraction failing - a source that is no package - is VOID, never a pass
  5  NOTHING WRITTEN: the folder holding the notes and the source byte-identical after a graft
  6  nothing a refusal says is a word of the document (a needle planted in every invented text)
  7  the three corpus arms carry `--graft` and refuse it where it cannot run; `carried` counts what was handed over

RED FIRST: at the pin c9b7d90 tools/graft_resolved.py does not exist - every arm fails, said by the import.

    uv run --with lxml python tests/test_graft_resolved.py
    uv run --with lxml python tests/test_graft_resolved.py --variant us
    uv run --with lxml python tests/test_graft_resolved.py --helper <path>   # e.g. a mutant's copy
"""
import argparse
import copy
import hashlib
import importlib.util
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parent.parent
ap = argparse.ArgumentParser()
ap.add_argument("--variant", choices=("uk", "us"), default="uk")
ap.add_argument("--helper", default=None)
args = ap.parse_args()
SCRIPTS = ROOT / args.variant / "scripts"
HELPER = Path(args.helper) if args.helper else ROOT / "tools" / "graft_resolved.py"
TMP = Path(tempfile.mkdtemp(prefix="s162-graft-test-"))
ENV = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1", PYTHONDONTWRITEBYTECODE="1")
W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
FAIL, CHECKED = [], 0
NEEDLE = "Zebrafinch"           # in every invented text; no refusal may print it
ARING, OUML = chr(0xE5), chr(0xF6)   # built at runtime: the file stays ASCII
STYLES = (f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:styles xmlns:w="{W}">'
          '<w:style w:type="paragraph" w:default="1" w:styleId="Normal"/>'
          '<w:style w:type="paragraph" w:styleId="HeadZq"><w:basedOn w:val="Normal"/><w:rPr><w:b/></w:rPr></w:style>'
          '<w:style w:type="character" w:styleId="EmphZq"><w:rPr><w:i/></w:rPr></w:style>'
          '</w:styles>')


def ok(label, cond, detail=""):
    global CHECKED
    CHECKED += 1
    print(f"  {'OK  ' if cond else 'XX  '} {label}" + (f"   ({detail})" if detail and not cond else ""))
    if not cond:
        FAIL.append(label)


try:
    spec = importlib.util.spec_from_file_location("graft_resolved_under_test", HELPER)
    G = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(G)
    IMPORT_ERROR = None
except Exception as exc:          # the pin has no helper: every arm below fails, said once here
    G, IMPORT_ERROR = None, exc


def r(text, rpr=""):
    return f"<w:r>{'<w:rPr>' + rpr + '</w:rPr>' if rpr else ''}<w:t xml:space=\"preserve\">{text}</w:t></w:r>"


def p(*runs, style=None):
    ppr = f'<w:pPr><w:pStyle w:val="{style}"/></w:pPr>' if style else ""
    return "<w:p>" + ppr + "".join(runs) + "</w:p>"


def write_docx(path, paras, styles=STYLES):
    body = "".join(paras)
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("word/document.xml", f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                                         f'<w:document xmlns:w="{W}"><w:body>{body}</w:body></w:document>')
        z.writestr("word/styles.xml", styles)
    return path


def extract(src):
    out = TMP / f"x{len(list(TMP.iterdir()))}.json"
    subprocess.run(["uv", "run", "--with", "lxml", "python", str(SCRIPTS / "extract_paragraphs.py"), str(src),
                    str(out)], capture_output=True, text=True, encoding="utf-8", errors="replace", env=ENV,
                   timeout=600)
    return json.loads(out.read_text(encoding="utf-8"))


def frozen_from(fresh):
    """A July-shaped notes list: `resolved` taken out, an operator's fields added."""
    notes = copy.deepcopy(fresh)
    for e in notes:
        for run in e.get("runs") or []:
            run.pop("resolved", None)
        e["en"] = f"English {NEEDLE} {e.get('idx')}"
        e["en_runs"] = [{"start": 0, "end": len(e["en"]), "bold": False, "italic": False}]
    return notes


def voids(fn):
    """(True, message) where fn raised GraftVoid; (False, what happened) otherwise."""
    try:
        fn()
    except G.GraftVoid as exc:
        return True, str(exc)
    except Exception as exc:
        return False, f"raised {type(exc).__name__}, not GraftVoid"
    return False, "no refusal"


def tree_state(folder):
    return sorted((str(f.relative_to(folder)), hashlib.sha256(f.read_bytes()).hexdigest())
                  for f in folder.rglob("*") if f.is_file())


print("=" * 96)
print(f"SUB-STEP 16.2 - the graft, on invented documents  [{args.variant}]")
print("=" * 96)
if IMPORT_ERROR is not None:
    print(f"  the helper could not be loaded: {type(IMPORT_ERROR).__name__} - every arm fails")
    ok("the helper loads", False, type(IMPORT_ERROR).__name__)
    print(f"\n  {CHECKED} check(s), {len(FAIL)} failure(s)")
    shutil.rmtree(TMP, ignore_errors=True)
    sys.exit(1)

# The invented document: a heading bold by its paragraph STYLE (no direct formatting), a term italic by its CHARACTER
# style, a plain paragraph with a non-ASCII letter, and a run whose direct bold-off defeats the style.
src = write_docx(TMP / "src.docx", [
    p(r(f"Heading {NEEDLE}"), style="HeadZq"),
    p(r(f"The {NEEDLE} "), r("term", '<w:rStyle w:val="EmphZq"/>'), r(" follows.")),
    p(r(f"Plain {NEEDLE} {ARING}ngstr{OUML}m text.")),
    p(r(f"Defeated {NEEDLE}", '<w:b w:val="0"/>'), style="HeadZq"),
])
fresh = extract(src)
want = sorted((e["idx"], n) for e in fresh for n, x in enumerate(e.get("runs") or []) if "resolved" in x)
print(f"  the invented document: {len(fresh)} entries, today's extraction gives `resolved` on {len(want)} run(s)")
ok("the control: today's extraction gives the key on exactly the two styled runs", len(want) == 2, str(want))

# 1 - TP
print("\n1  the key restored where today's extraction gives it, and nowhere else")
notes = frozen_from(fresh)
before = copy.deepcopy(notes)
out, stats = G.graft(notes, fresh)
got = sorted((e["idx"], n) for e in out for n, x in enumerate(e.get("runs") or []) if "resolved" in x)
ok("resolved on exactly today's runs", got == want, f"{got} != {want}")
fo, oo = {e["idx"]: e for e in fresh}, {e["idx"]: e for e in out}
ok("each value today's", bool(got) and all(oo[i]["runs"][n]["resolved"] == fo[i]["runs"][n]["resolved"]
                                           for i, n in got))
ok(f"every entry aligned: {stats['aligned']} of {stats['entries']}", stats["aligned"] == stats["entries"] == len(fresh))
ok("the counts: 2 given, 0 already", (stats["grafted"], stats["already"]) == (2, 0), str(stats))
ok("the operator's fields untouched", all(out[i]["en"] == before[i]["en"] and out[i]["en_runs"] == before[i]["en_runs"]
                                          for i in range(len(out))))
ok("the list it was given is not mutated", notes == before)
ok("outside `resolved`, the copy is the frozen notes exactly",
   [{**e, "runs": [{k: v for k, v in x.items() if k != "resolved"} for x in e["runs"]]} for e in out] == before)

# 2 - the bytes handed over
print("\n2  the bytes handed over")
npath = TMP / "notes" / "paragraphs.json"
npath.parent.mkdir()
raw = json.dumps(notes, ensure_ascii=False, indent=2).encode("utf-8")   # deliberately NOT extraction's format
npath.write_bytes(raw)
data, s2 = G.graft_notes_bytes(npath, src, SCRIPTS)
ok("grafted: the bytes parse to the grafted list", json.loads(data.decode("utf-8")) == out)
ok("grafted: extraction's own format (indent 1), a non-ASCII letter written as itself",
   data == json.dumps(out, ensure_ascii=False, indent=1).encode("utf-8") and ARING.encode("utf-8") in data)
plain = write_docx(TMP / "plain.docx", [p(r(f"Only {NEEDLE} plain.")), p(r("Second plain."))])
pfresh = extract(plain)
ppath = TMP / "notes" / "plain.json"
praw = (json.dumps(frozen_from(pfresh), ensure_ascii=False) + "\n").encode("utf-8")
ppath.write_bytes(praw)
pdata, s3 = G.graft_notes_bytes(ppath, plain, SCRIPTS)
ok("nothing to graft: the notes file's OWN bytes come back, unchanged", pdata == praw and s3["grafted"] == 0,
   f"{s3}")

# 3 - FP, the planted misalignment
print("\n3  a planted misalignment is VOID, never a pass")
msgs = []


def planted(edit):
    n = frozen_from(fresh)
    edit(n)
    hit, msg = voids(lambda: G.graft(n, fresh))
    msgs.append(msg)
    return hit, msg


hit, msg = planted(lambda n: n[1]["runs"][0].__setitem__("text", "The Zebrafinch, "))
ok("one run's text changed (the plan's control): VOID", hit, msg)
hit, msg = planted(lambda n: n[2]["runs"][0].__setitem__("bold", True))
ok("one run's bold flipped: VOID, the key named", hit and "bold" in msg, msg)
hit, msg = planted(lambda n: n[2].__setitem__("text", n[2]["text"] + " x"))
ok("an entry's text changed: VOID", hit and "text" in msg, msg)
hit, msg = planted(lambda n: n.pop(3))
ok("an idx missing from the frozen notes: VOID", hit, msg)
hit, msg = planted(lambda n: n.append({**copy.deepcopy(n[0]), "idx": 99}))
ok("an idx only in the frozen notes: VOID", hit, msg)
hit, msg = planted(lambda n: n.append(copy.deepcopy(n[0])))
ok("an idx twice: VOID", hit and "more than once" in msg, msg)
hit, msg = planted(lambda n: n[1]["runs"].pop())
ok("a run missing: VOID", hit, msg)
hit, msg = planted(lambda n: n[0]["runs"][0].__setitem__("resolved", {"bold": False}))
ok("a frozen run carrying a resolved that is not today's: VOID", hit, msg)
same = frozen_from(fresh)
same[0]["runs"][0]["resolved"] = copy.deepcopy(fresh[0]["runs"][0]["resolved"])
o4, s4 = G.graft(same, fresh)
ok("one carrying today's: counted already, 1 given, not VOID", (s4["already"], s4["grafted"]) == (1, 1), str(s4))
extra = copy.deepcopy(fresh) + [{**copy.deepcopy(fresh[0]), "idx": 77}]
hit, msg = voids(lambda: G.graft(frozen_from(fresh), extra))
msgs.append(msg)
ok("an idx only in today's extraction: VOID", hit, msg)
hit, msg = voids(lambda: G.graft(None, fresh))
msgs.append(msg)
ok("frozen notes that are not a list (a json null): VOID", hit, msg)

# 4 - extraction failing
print("\n4  today's extraction failing is VOID")
bad = TMP / "notapackage.docx"
bad.write_bytes(f"not a package {NEEDLE}".encode("utf-8"))
hit, msg = voids(lambda: G.graft_notes_bytes(npath, bad, SCRIPTS))
msgs.append(msg)
ok("a source that is no package: VOID, never a pass", hit, msg)
hit, msg = voids(lambda: G.fresh_notes(src, SCRIPTS, timeout=0.001))
msgs.append(msg)
ok("an extraction cut off by its time limit: VOID, never a crash", hit, msg)

# 5 - nothing written
print("\n5  nothing written beside the notes or the source")
held = TMP / "held"
held.mkdir()
shutil.copyfile(npath, held / "paragraphs.json")
shutil.copyfile(src, held / "src.docx")
was = tree_state(held)
G.graft_notes_bytes(held / "paragraphs.json", held / "src.docx", SCRIPTS)
ok("the folder holding the notes and the source is byte-identical after a graft", tree_state(held) == was)

# 6 - nothing printed
print("\n6  no refusal says a word of the document")
leaked = [m for m in msgs if NEEDLE in m]
ok(f"{len(msgs)} refusal message(s), none carrying the planted needle", len(msgs) == 12 and not leaked,
   f"{len(msgs)} messages, {len(leaked)} leaking")

# 7 - the arms and the read-back
print("\n7  the three corpus arms, and the read-back")
for tool in ("delivered_corpus_arm.py", "apply_corpus_diff.py", "postprocess_corpus_arm.py"):
    h = subprocess.run(["uv", "run", "--with", "lxml", "python", str(ROOT / "tools" / tool), "--help"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace", env=ENV, timeout=300)
    ok(f"{tool} offers --graft", h.returncode == 0 and "--graft" in h.stdout, f"rc={h.returncode}")
for extra_args in (["--arm", "a"], ["--sides"]):
    e = subprocess.run(["uv", "run", "--with", "lxml", "python", str(ROOT / "tools" / "delivered_corpus_arm.py"),
                        "--graft"] + extra_args, capture_output=True, text=True, encoding="utf-8", errors="replace",
                       env=ENV, timeout=300)
    ok(f"delivered_corpus_arm.py refuses --graft with {' '.join(extra_args)}",
       e.returncode == 2 and "drives arm (b) only" in e.stderr, f"rc={e.returncode}")
cpath = TMP / "notes" / "carried.json"
cpath.write_bytes(data)
ok("carried counts the runs the grafted notes carry the key on: 2", G.carried(cpath) == 2, str(G.carried(cpath)))
ok("carried says None for notes that are absent", G.carried(TMP / "absent.json") is None)

shutil.rmtree(TMP, ignore_errors=True)
print("\n" + "=" * 96)
print(f"  {CHECKED} check(s), {len(FAIL)} failure(s)")
for f in FAIL:
    print(f"    XX  {f}")
print("=" * 96)
sys.exit(1 if FAIL else 0)
