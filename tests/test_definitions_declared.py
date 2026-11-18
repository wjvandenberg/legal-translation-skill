"""test_definitions_declared.py - sub-step 16.6: the definitions range, declared (PLAN-2-step-b.md section 3.16).

ON INVENTED DOCUMENTS ONLY, built in a temporary directory: a document.xml and, where an arm needs one, notes in
the shape extraction writes them, an operator's English and a `"role": "definition"` on each declared paragraph.
The tree's own reorder_definitions.py and validate_en_runs.py run as top-level commands. What each arm asserts:

  1  TP, register L2's shape DECLARED: three bold-colon agenda pointers, narrative, then the real block far later -
     the real block sorted, every paragraph outside it where it was
  2  L2's shape UNDECLARED: the detector's answer, as before, but every candidate section named and the run loud
     where there is more than one; its exit code and its delivery as the pin's
  3  TP, two declared sections - each sorted on its own, the paragraph between them unmoved
  4  FP, a document with no definitions section and nothing declared - said so in words that say what to do, no
     reassurance that it is expected, exit 0, the document byte for byte as it was
  5  FP, P11: a declared section holding a body-text term - still refused by the term-sanity guard, exit 1, the
     document unchanged, the diagnosis no longer the converter and the remedy no longer to accept source order
  6  malformed declarations refused, exit 2, nothing written: a role other than "definition"; a declared idx past
     the document; notes whose count is not the document's paragraph count
  7  notes given and nothing declared - the delivery byte for byte as a run without --notes
  8  the gate, validate_en_runs.py: a declared section missing en_runs, exit 2, though no heading lets the detector
     find it; declared and carrying en_runs, exit 0; a malformed role, exit 2; nothing declared, as before
  9  --dry-run with a declaration: the declared sections and the definitions named, nothing written
  10 --expected-defs counts every declared section's definitions together

RED FIRST: against 16.5's scripts (--scripts, the pin 58ab29b's) arms 1, 3, 4's wording, 5's wording, 6, 8's
declared cases, 9 and 10 fail; 2's counts and 7 are not red there (no --notes). Prints booleans and the invented
documents' own words - never anything from a real document.

    uv run --with lxml python tests/test_definitions_declared.py
    uv run --with lxml python tests/test_definitions_declared.py --variant us
    uv run --with lxml python tests/test_definitions_declared.py --scripts <folder>   # e.g. the pin's, for RED
"""
import argparse
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
ap = argparse.ArgumentParser()
ap.add_argument("--variant", choices=("uk", "us"), default="uk")
ap.add_argument("--scripts", default=None)
args = ap.parse_args()
SCRIPTS = Path(args.scripts) if args.scripts else ROOT / args.variant / "scripts"
TMP = Path(tempfile.mkdtemp(prefix="s166-defs-test-"))
ENV = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1", PYTHONDONTWRITEBYTECODE="1")
W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
FAIL, CHECKED = [], 0
OQ, CQ = "“", "”"
DECL_REFUSED = "The definitions section declared in paragraphs.json is malformed"


def ok(label, cond, detail=""):
    global CHECKED
    CHECKED += 1
    print(f"  {'OK  ' if cond else 'XX  '} {label}" + (f"   ({detail})" if detail and not cond else ""))
    if not cond:
        FAIL.append(label)


def para(text, bold_head=None):
    head = (f'<w:r><w:rPr><w:b/></w:rPr><w:t xml:space="preserve">{bold_head}</w:t></w:r>' if bold_head else "")
    tail = f'<w:r><w:t xml:space="preserve">{text}</w:t></w:r>' if text else ""
    return f"<w:p>{head}{tail}</w:p>"


class Doc:
    """Paragraphs in order, each with its text and whether it is declared."""

    def __init__(self):
        self.rows = []

    def add(self, text, bold_head=None, declared=False):
        self.rows.append((text, bold_head, declared))
        return self

    def xml(self):
        body = "".join(para(t, b) for t, b, _d in self.rows)
        return (f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<w:document xmlns:w="{W}"><w:body>{body}'
                f'</w:body></w:document>').encode("utf-8")

    def notes(self, role="definition"):
        out = []
        for i, (t, b, d) in enumerate(self.rows):
            full = (b or "") + (t or "")
            e = {"idx": i, "text": full, "runs": [], "en": full, "en_runs": None}
            if d:
                e["role"] = role
            out.append(e)
        return out


def texts(xml_bytes):
    from lxml import etree
    root = etree.fromstring(xml_bytes)
    return ["".join(t.text or "" for t in p.iter(f"{{{W}}}t")) for p in root.iter(f"{{{W}}}p")]


def run(name, doc_bytes, notes=None, *flags, script="reorder_definitions.py"):
    d = TMP / name
    d.mkdir(exist_ok=True)
    xml = d / "document.xml"
    xml.write_bytes(doc_bytes)
    cmd = ["uv", "run", "--with", "lxml", "python", str(SCRIPTS / script)]
    if script == "reorder_definitions.py":
        cmd += ["--doc", str(xml)]
        if notes is not None:
            nj = d / "paragraphs.json"
            nj.write_bytes(json.dumps(notes, ensure_ascii=False).encode("utf-8"))
            cmd += ["--notes", str(nj)]
    else:
        nj = d / "paragraphs.json"
        nj.write_bytes(json.dumps(notes, ensure_ascii=False).encode("utf-8"))
        cmd += [str(nj)]
    cmd += list(flags)
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", env=ENV,
                       timeout=600)
    return r.returncode, (r.stdout or "") + (r.stderr or ""), xml.read_bytes()


def defn(term, body="means the invented thing so named in this made-up instrument."):
    return f"{OQ}{term}{CQ} {body}"


def l2(declare):
    doc = Doc()
    for i in range(6):
        doc.add(f"Opening wording number {i} of the invented minutes.")
    for n in range(3):
        doc.add("", bold_head=f"As to item {n + 1} of the order of business:")
        doc.add(f"Narrative sentence about item {n + 1}, plainly not a definition.")
    for i in range(30):
        doc.add(f"Further operative wording number {i} of the invented record.")
    for t in ("Zeta Asset", "Business Day", "Alpha Party", "Mid Point", "Closing Date"):
        doc.add(defn(t), declared=declare)
    for i in range(3):
        doc.add(f"Closing wording number {i}.")
    return doc


print("=" * 96)
print(f"SUB-STEP 16.6 - the definitions range, declared  [{args.variant}]"
      + (f"  scripts: {args.scripts}" if args.scripts else ""))
print("=" * 96)

print("\n1  L2's shape, declared")
doc = l2(True)
before = texts(doc.xml())
rc, out, after_b = run("l2_declared", doc.xml(), doc.notes())
after = texts(after_b)
block = list(range(42, 47))       # 6 opening, 3 pointers each with its narrative, 30 more, then the block
ok("exit 0", rc == 0, f"rc={rc} {out[-300:]}")
ok("the real block sorted alphabetically", [after[i][1:6] for i in block] ==
   ["Alpha", "Busin", "Closi", "Mid P", "Zeta "], str([after[i][1:6] for i in block]))
ok("every paragraph outside the block where it was", all(after[i] == before[i] for i in range(len(before))
                                                         if i not in block))

print("\n2  L2's shape, undeclared: the detector as before, every candidate named")
doc = l2(False)
rc, out, after_b = run("l2_undeclared", doc.xml())
ok("both candidate sections named", "2 candidate" in out, out[-400:])
ok("the run says which one it sorts", "sorting the first" in out.lower() or "sorts the first" in out.lower(),
   out[-400:])
ok("and says how to declare the real one", "role" in out and "--notes" in out, out[-400:])
UNDECLARED_L2 = (rc, after_b)

print("\n3  two declared sections, each sorted on its own")
doc = Doc().add("Preamble of the invented record.")
for t in ("Gamma Term", "Alpha Term", "Beta Term"):
    doc.add(defn(t), declared=True)
doc.add("A body paragraph between the two sections, which must not move.")
for t in ("Yankee Term", "Xray Term", "Whiskey Term"):
    doc.add(defn(t), declared=True)
doc.add("Closing wording of the invented record.")
rc, out, after_b = run("two", doc.xml(), doc.notes())
after = texts(after_b)
ok("exit 0", rc == 0, f"rc={rc} {out[-300:]}")
ok("the first section sorted within itself", [a[1:6] for a in after[1:4]] == ["Alpha", "Beta ", "Gamma"],
   str(after[1:4]))
ok("the paragraph between them unmoved", after[4].startswith("A body paragraph"))
ok("the second section sorted within itself", [a[1:6] for a in after[5:8]] == ["Whisk", "Xray ", "Yanke"],
   str(after[5:8]))

print("\n3b a blank paragraph between declared ones keeps them one section")
doc = Doc().add("Preamble of the invented record.")
doc.add(defn("Gamma Term"), declared=True)
doc.add("")
doc.add(defn("Alpha Term"), declared=True)
doc.add("Closing wording of the invented record.")
rc, out, after_b = run("blank", doc.xml(), doc.notes())
after = texts(after_b)
ok("sorted across the blank: Alpha first", rc == 0 and after[1].startswith(OQ + "Alpha"), f"rc={rc} {after[1:4]}")

print("\n4  no definitions section, nothing declared")
doc = Doc()
for i in range(8):
    doc.add(f"Ordinary operative wording number {i}.")
rc, out, after_b = run("none", doc.xml())
ok("exit 0, the document byte for byte", rc == 0 and after_b == doc.xml(), f"rc={rc}")
ok("it says no definitions section was found", "no definitions section found" in out, out[-300:])
ok("... with no reassurance that it is expected", "expected for many document types" not in out, out[-300:])
ok("... and says what to do if the document has one", "role" in out and "--notes" in out, out[-300:])

print("\n5  P11: a declared section holding a body-text term is still refused")
doc = Doc().add("Preamble of the invented record.")
doc.add(defn("Alpha Term"), declared=True)
doc.add(f"{OQ}Beta Term{CQ} means the {OQ}thing{CQ} that this sentence quotes in its own body text", declared=True)
doc.add(defn("Gamma Term"), declared=True)
doc.add("", bold_head="This whole body line is long and quoted means: more", declared=True)
doc.add("Closing wording.")
rc, out, after_b = run("p11", doc.xml(), doc.notes())
ok("exit 1, refused", rc == 1, f"rc={rc} {out[-300:]}")
ok("the document unchanged", after_b == doc.xml())
ok("it says it refused and left the document unchanged", "Refusing to reorder; document unchanged" in out)
ok("the diagnosis no longer blames the converter", "LibreOffice" not in out, out[-400:])
ok("the remedy no longer accepts source order", "accept the warnings" not in out, out[-400:])

print("\n6  malformed declarations, refused before anything is written")
doc = l2(True)
bad_role = doc.notes(role="definitions")
rc, out, after_b = run("bad_role", doc.xml(), bad_role)
ok("a role other than 'definition': exit 2, nothing written", rc == 2 and after_b == doc.xml() and DECL_REFUSED in out, f"rc={rc}")
past = doc.notes()
past[-1]["idx"] = 999
past[-1]["role"] = "definition"
rc, out, after_b = run("past", doc.xml(), past)
ok("a declared idx past the document: exit 2, nothing written", rc == 2 and after_b == doc.xml() and DECL_REFUSED in out, f"rc={rc}")
neg = doc.notes()
neg[0]["idx"] = -1
neg[0]["role"] = "definition"
rc, out, after_b = run("negative", doc.xml(), neg)
ok("a negative declared idx: exit 2, nothing written", rc == 2 and after_b == doc.xml() and DECL_REFUSED in out, f"rc={rc}")
short = doc.notes()[:-1]
rc, out, after_b = run("short", doc.xml(), short)
ok("notes whose count is not the paragraph count: exit 2, nothing written", rc == 2 and after_b == doc.xml() and DECL_REFUSED in out,
   f"rc={rc}")

print("\n7  notes given and nothing declared: as a run without --notes")
doc = l2(False)
rc7, out7, after7 = run("plain_notes", doc.xml(), doc.notes())
ok("the same exit code and delivery as without --notes", (rc7, after7) == UNDECLARED_L2, f"rc={rc7}")

print("\n8  the gate reads the declaration")
doc = Doc().add("Preamble of the invented record.")
for t in ("Gamma Term", "Alpha Term", "Beta Term"):
    doc.add(defn(t), declared=True)
doc.add("Closing wording of the invented record.")
notes = doc.notes()
rc, out, _ = run("gate_missing", doc.xml(), notes, script="validate_en_runs.py")
ok("a declared section missing en_runs, no heading anywhere: exit 2", rc == 2, f"rc={rc} {out[-300:]}")
for e in notes:
    if e.get("role"):
        e["en_runs"] = [{"start": 0, "end": len(e["en"]), "bold": False, "italic": False}]
rc, out, _ = run("gate_ok", doc.xml(), notes, script="validate_en_runs.py")
ok("declared and carrying en_runs: exit 0", rc == 0, f"rc={rc} {out[-300:]}")
rc, out, _ = run("gate_bad_role", doc.xml(), doc.notes(role="defn"), script="validate_en_runs.py")
ok("a malformed role: exit 2", rc == 2, f"rc={rc}")
far = doc.notes()
far[1]["idx"] = 999
rc, out, _ = run("gate_far", doc.xml(), far, script="validate_en_runs.py")
ok("a declared idx past the notes: exit 2, refused before apply as reorder refuses it", rc == 2
   and "past the notes" in out, f"rc={rc}")
plain_notes = Doc().add("Ordinary wording.").add("More ordinary wording.").notes()
rc, out, _ = run("gate_none", doc.xml(), plain_notes, script="validate_en_runs.py")
ok("nothing declared and nothing detected: exit 0, as before", rc == 0, f"rc={rc}")

print("\n9  --dry-run with a declaration")
doc = l2(True)
rc, out, after_b = run("dry", doc.xml(), doc.notes(), "--dry-run")
ok("exit 0, nothing written", rc == 0 and after_b == doc.xml(), f"rc={rc}")
ok("the declared section and its five definitions named", "declared" in out.lower() and "Found 5 definitions" in out,
   out[-400:])

print("\n10  --expected-defs counts every declared section")
doc = Doc().add("Preamble.")
for t in ("Gamma Term", "Alpha Term"):
    doc.add(defn(t), declared=True)
doc.add("Between the sections.")
for t in ("Yankee Term", "Xray Term"):
    doc.add(defn(t), declared=True)
rc_right, _o, _a = run("exp_right", doc.xml(), doc.notes(), "--dry-run", "--expected-defs", "4")
rc_wrong, _o, _a = run("exp_wrong", doc.xml(), doc.notes(), "--dry-run", "--expected-defs", "2")
ok("4 across two sections passes, 2 is refused", (rc_right, rc_wrong) == (0, 1), f"{(rc_right, rc_wrong)}")

shutil.rmtree(TMP, ignore_errors=True)
print("\n" + "=" * 96)
print(f"  {CHECKED} check(s), {len(FAIL)} failure(s)")
for f in FAIL:
    print(f"    XX  {f}")
print("=" * 96)
sys.exit(1 if FAIL else 0)
