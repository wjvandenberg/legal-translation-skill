# -*- coding: utf-8 -*-
"""BRANCH 14 — PROVE THE DELIVERED DOCUMENT DOES NOT MOVE.

The branch's claim is that it changes what the checks REPORT and nothing a reader of the
delivered document could see. §5.3 requires a rendered page-by-page comparison of both
documents; a byte-identical deliverable is strictly stronger evidence than rendering two
files that are the same file, so this is the proof that discharges it — and a proof, not
an assertion, because "no behaviour change" has been claimed wrongly in this project
before.

FOUR SCRIPTS CHANGED AND THEY ARE NOT THE SAME KIND OF THING, so each gets the proof its
own risk needs:

  quality_check.py            REPORTS ONLY. Asserted by SHA-256 over every file in a
  validate_segment_shapes.py  workdir before and after a run: a reporter that writes
                              anything at all has exceeded its brief.

  translate_headers_footers.py  WRITES the auxiliary XML. Old and new code are run on the
                                same input and the written bytes compared.

  repack_docx.py                WRITES the deliverable. Old and new code are run on the
                                same input and every member of the resulting .docx is
                                compared by content — not by zip bytes, which carry
                                timestamps and would differ for no reason that matters.

    uv run --with lxml python tests/test_no_delivered_byte_moves.py

Synthetic fixtures only. No client text.
"""
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parent.parent
# PINNED TO A COMMIT, NOT A BRANCH NAME — and this file is the reason to state the rule as
# "ask what else does the same thing" rather than as three separate fixes. The pin was
# corrected in test_check_scoping.py and test_check_scoping_properties.py and MISSED HERE,
# so once branch 14 merged this suite compared the current code against ITSELF and reported
# twelve green assertions for a comparison it was no longer making. Byte-identity is the
# worst place for that to happen: comparing a thing with itself is trivially identical, so
# the vacuous case looks exactly like the passing case. §5.1's second failure shape, in the
# same session that recorded it twice.
REF = os.environ.get("LT_BASELINE_REF", "2178cce")
W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
FIX = ROOT / "tests" / "fixtures"
FAIL, CHECKED = [], 0


def ok(label, cond, detail=""):
    global CHECKED
    CHECKED += 1
    print(("  OK   " if cond else "  XX   ") + label + (f"   {detail}" if detail and not cond else ""))
    if not cond:
        FAIL.append(f"{label} {detail}".strip())


r = subprocess.run(["git", "rev-parse", "--verify", REF], capture_output=True,
                   text=True, cwd=ROOT)
if r.returncode != 0:
    print(f"VOID — baseline ref {REF} does not resolve. Nothing compared, nothing passed.")
    sys.exit(1)
SHA = r.stdout.strip()
print("BRANCH 14 — NO DELIVERED BYTE MOVES")
print(f"baseline: {REF} = {SHA[:12]}")
print("=" * 96)

TMP = Path(tempfile.mkdtemp(prefix="b14-bytes-"))
OLD = TMP / "old_scripts"
OLD.mkdir(parents=True)
for f in sorted((ROOT / "uk" / "scripts").glob("*.py")):
    shutil.copyfile(f, OLD / f.name)
_identical = []
for name in ("quality_check.py", "validate_segment_shapes.py",
             "translate_headers_footers.py", "repack_docx.py"):
    blob = subprocess.run(["git", "show", f"{REF}:uk/scripts/{name}"],
                          capture_output=True, cwd=ROOT)
    if blob.returncode != 0:
        print(f"VOID — cannot read {name} at {REF}")
        sys.exit(1)
    if blob.stdout == (ROOT / "uk" / "scripts" / name).read_bytes():
        _identical.append(name)
    (OLD / name).write_bytes(blob.stdout)

# A comparison that established nothing has not passed — and here the vacuous case is
# INVISIBLE without this guard, because comparing a file with itself produces identical
# bytes, which is exactly the result the suite is looking for.
if len(_identical) == 4:
    print(f"VOID — all four scripts at {REF} are BYTE-IDENTICAL to the working tree, so")
    print("every comparison below would be a file against itself and would pass for that")
    print("reason alone. Point LT_BASELINE_REF at a commit that predates the change.")
    sys.exit(1)
if _identical:
    print(f"  NOTE: {len(_identical)} of 4 scripts are unchanged since {REF} "
          f"({', '.join(_identical)}) —\n  their comparisons below are trivially "
          "identical and prove nothing about those files.")


def load(path, modname):
    d = str(Path(path).parent)
    sys.path.insert(0, d)
    try:
        spec = importlib.util.spec_from_file_location(modname, path)
        m = importlib.util.module_from_spec(spec)
        sys.modules[modname] = m
        spec.loader.exec_module(m)
    finally:
        sys.path.remove(d)
    return m


def tree_hashes(root):
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(root.rglob("*")) if p.is_file()}


def members(docx):
    with zipfile.ZipFile(docx) as z:
        return {n: hashlib.sha256(z.read(n)).hexdigest() for n in sorted(z.namelist())}


# =====================================================================================
print("\n1. THE REPORTERS MUST WRITE NOTHING")
print("-" * 96)
WORK = TMP / "reporter"
WORK.mkdir()
with zipfile.ZipFile(FIX / "definitions.docx") as z:
    z.extractall(WORK)
notes = [{"idx": 0, "text": "Bron.", "en": "Source."}]
(WORK / "paragraphs.json").write_text(json.dumps(notes), encoding="utf-8")
ENV = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1",
           PYTHONDONTWRITEBYTECODE="1")
for script, args in (("quality_check.py",
                      [str(WORK / "word" / "document.xml"), "--with-source",
                       str(WORK / "paragraphs.json"), "--verbose"]),
                     ("validate_segment_shapes.py", [str(WORK / "paragraphs.json")])):
    before = tree_hashes(WORK)
    subprocess.run(["uv", "run", "--with", "lxml", "python",
                    str(ROOT / "uk" / "scripts" / script), *args],
                   capture_output=True, cwd=str(ROOT), env=ENV, timeout=300)
    after = tree_hashes(WORK)
    ok(f"{script}: workdir byte-identical after running it "
       f"({len(before)} files)", before == after,
       f"changed: {sorted(set(before) ^ set(after)) or [k for k in before if before[k] != after.get(k)]}")

# =====================================================================================
print("\n2. translate_headers_footers — THE WRITTEN AUXILIARY XML IS UNCHANGED")
print("-" * 96)
OLD_THF = load(OLD / "translate_headers_footers.py", "old_thf_b")
NEW_THF = load(ROOT / "uk" / "scripts" / "translate_headers_footers.py", "new_thf_b")

HFW = TMP / "hf"
HFW.mkdir()
src = HFW / "src.docx"
shutil.copyfile(FIX / "headers-footers.docx", src)
scaffold = HFW / "scaffold.json"
r = subprocess.run(["uv", "run", "--with", "lxml", "python",
                    str(ROOT / "uk" / "scripts" / "translate_headers_footers.py"),
                    str(src), "--extract", str(scaffold)],
                   capture_output=True, text=True, encoding="utf-8", errors="replace",
                   cwd=str(ROOT), env=ENV, timeout=300)
entries = json.loads(scaffold.read_text(encoding="utf-8")) if scaffold.exists() else []
ok(f"scaffold extracted from the fixture ({len(entries)} entr(y/ies))", bool(entries),
   f"(rc={r.returncode})")

# THREE SHAPES, because F15's change is about which of them counts as handled:
#   every entry translated · every entry verbatim · a mix.
SHAPES = {
    "all translated": [dict(e, en=(e.get("text") or "") + " (EN)") for e in entries],
    "all verbatim": [dict(e, en=e.get("text")) for e in entries],
    "mixed": [dict(e, en=(e.get("text") if i % 2 else (e.get("text") or "") + " (EN)"))
              for i, e in enumerate(entries)],
}
for name, ents in SHAPES.items():
    sj = HFW / f"s-{name.replace(' ', '-')}.json"
    sj.write_text(json.dumps(ents), encoding="utf-8")
    o, n = HFW / f"o-{name}", HFW / f"n-{name}"
    OLD_THF.apply_from_scaffold(str(src), str(sj), str(o))
    NEW_THF.apply_from_scaffold(str(src), str(sj), str(n))
    ok(f"translate_headers_footers, {name}: written XML byte-identical",
       tree_hashes(o) == tree_hashes(n),
       f"old={sorted(tree_hashes(o))} new={sorted(tree_hashes(n))}")

# =====================================================================================
print("\n3. repack_docx — EVERY MEMBER OF THE DELIVERED .docx IS UNCHANGED")
print("-" * 96)
OLD_RPK = load(OLD / "repack_docx.py", "old_rpk_b")
NEW_RPK = load(ROOT / "uk" / "scripts" / "repack_docx.py", "new_rpk_b")

from lxml import etree  # noqa: E402


def declared_text(p):
    """The paragraph's text the way validate_apply joins it: a rendered w:tab or w:br
    contributes a SPACE.

    THIS HARNESS HAD THE SAME BLINDNESS THE BRANCH IS FIXING IN THE SKILL, and it is
    recorded rather than quietly corrected. The first version concatenated w:t only, so
    on the tab-separated party grid it declared "Party AParty B" while validate_apply's
    own joiner (which does insert the space) read "Party A Party B" -- and the gate
    correctly reported a missing token. A test harness reproducing the very defect under
    repair is §5.1's second failure shape: a shared hazard fixed in one caller and left
    in another. Ask what else does the same thing.
    """
    out = []
    for el in p.iter():
        tag = etree.QName(el).localname
        if tag in ("t", "delText") and el.text:
            out.append(el.text)
        elif tag in ("tab", "br", "cr"):
            parent = el.getparent()
            if tag == "tab" and parent is not None \
                    and etree.QName(parent).localname == "tabs":
                continue
            out.append(" ")
    return "".join(out)


outs = {}
for fixture in ("definitions.docx", "anchors-and-tabs.docx"):
    RW = TMP / ("repack-" + fixture.replace(".docx", ""))
    RW.mkdir()
    orig = RW / "orig.docx"
    shutil.copyfile(FIX / fixture, orig)
    with zipfile.ZipFile(orig) as z:
        doc_xml = z.read("word/document.xml")
    (RW / "document.xml").write_bytes(doc_xml)

    # A paragraphs.json that matches the body, so validate_apply --strict is satisfied:
    # every declared token is present because `en` IS the body text.
    root = etree.fromstring(doc_xml)
    paras = [{"idx": i, "text": declared_text(p), "en": declared_text(p),
              "style": "Normal"}
             for i, p in enumerate(root.iter(f"{{{W}}}p"))]
    (RW / "paragraphs.json").write_text(json.dumps(paras), encoding="utf-8")

    produced = {}
    for label, mod in (("old", OLD_RPK), ("new", NEW_RPK)):
        out = RW / f"{label}.docx"
        try:
            mod.repack(str(orig), str(RW / "document.xml"), str(out),
                       paragraphs_json=str(RW / "paragraphs.json"))
            produced[label] = out if out.exists() else None
        except Exception as exc:
            produced[label] = None
            print(f"       {fixture} {label} repack raised {type(exc).__name__}: {exc}")
    ok(f"{fixture}: both repacks produced a .docx",
       produced.get("old") is not None and produced.get("new") is not None,
       f"(old={produced.get('old') is not None}, new={produced.get('new') is not None})")
    if produced.get("old") and produced.get("new"):
        mo, mn = members(produced["old"]), members(produced["new"])
        ok(f"{fixture}: same member list ({len(mo)} parts)", set(mo) == set(mn),
           f"only in old: {sorted(set(mo) - set(mn))}  "
           f"only in new: {sorted(set(mn) - set(mo))}")
        differing = [k for k in mo if k in mn and mo[k] != mn[k]]
        ok(f"{fixture}: EVERY member of the delivered .docx byte-identical",
           not differing, f"differing: {differing}")

shutil.rmtree(TMP, ignore_errors=True)
print()
print("=" * 96)
if FAIL:
    print(f"FAIL — {len(FAIL)} of {CHECKED} assertions:")
    for f in FAIL:
        print(f"  · {f}")
    print("=" * 96)
    sys.exit(1)
print(f"PASS — {CHECKED} assertions. Nothing this branch changed reaches a delivered byte:")
print("the two reporters write nothing at all, and the two scripts that DO write produce")
print(f"byte-identical output against {REF} = {SHA[:12]}.")
print("=" * 96)
