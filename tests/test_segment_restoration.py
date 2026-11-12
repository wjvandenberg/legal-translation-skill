# -*- coding: utf-8 -*-
"""STEP 15, sub-step 15.3 - G9's first half: does the segment check ask APPLY whether it will supply the space?

WHAT WAS WRONG. `validate_segment_shapes.py` reported an `alpha_collision_at_boundary` wherever two segments' English
met letter to letter with no space between - and apply runs it --strict, so the report aborted the run. But apply
puts the source's boundary whitespace back onto a segment whose English dropped it (one character, and only where
the nearest non-empty neighbour supplies none - C16). So a deletion declared WITHOUT the space its source segment
ends on was delivered clean while the check blocked it, and declaring the space to quiet the check could deliver
two: no compliant input (register G9). The row thought the source absent from the notes; it is beside the English,
in `tc_segments`. Sub-step 15.3 puts each join to apply's own restoration - imported, never restated - wherever the
two lists pair one for one; elsewhere the rule runs as before.

EVERY PARAGRAPH HERE IS INVENTED - the English, the source text, the shapes. No corpus, no client text.

  FP   G9's shape: the space the English left off is restored by apply - quiet NOW, and PROVED to have fired at
       the pin, as a list pair, as a join only a view creates, and from the right-hand segment's edge.
  TP   a join apply does NOT fill must still fire: no space in the source; the space on the far edge; apply's
       neighbour test reading LIST order, so a segment the view drops decides it, a cleared one skipped, a kept
       source counted.
  ALIGN  no `tc_segments`, or one that does not pair: the rule exactly as at the pin.
  OTHER  every finding but G9's alpha collision identical to the pin's; the digit rule is not told.
  TRUTH  every FP and TP also put through the tree's real `apply_trackchanges_inplace` on an invented paragraph,
         both views rendered: the check fires exactly where a view glues two words.
  EXIT   --strict, as apply runs it: 0 now and 1 at the pin on the FP paragraphs; 1 on the TP paragraphs; a file
         that does not pair prints the pin's every line.

THE PIN is 8961ec1, main before step 15 - both scripts byte-identical there to the branch's base, and a commit the
squash-merge keeps reachable. Override with LT_G9_PIN; a pin equal to the script under test is VOID.

    uv run --with lxml python tests/test_segment_restoration.py
    uv run --with lxml python tests/test_segment_restoration.py --variant us
    uv run --with lxml python tests/test_segment_restoration.py --script <a copy of validate_segment_shapes.py,
                                                                      apply_translations_textmatch.py beside it>
"""
import argparse
import copy
import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.dont_write_bytecode = True
os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")

ROOT = Path(__file__).resolve().parent.parent
ap = argparse.ArgumentParser()
ap.add_argument("--variant", default="uk", choices=("uk", "us"))
ap.add_argument("--script", default=None, help="run this copy of validate_segment_shapes.py instead of the tree's")
args = ap.parse_args()
TREE_SCRIPTS = ROOT / args.variant / "scripts"
SCRIPT = Path(args.script).resolve() if args.script else TREE_SCRIPTS / "validate_segment_shapes.py"
PIN = os.environ.get("LT_G9_PIN", "8961ec1")
ENV = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1", PYTHONDONTWRITEBYTECODE="1")
TMP = Path(tempfile.mkdtemp(prefix="s15-g9-"))
W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
ALPHA = "alpha_collision_at_boundary"
FAIL, CHECKED = [], 0


def ok(label, cond, detail=""):
    global CHECKED
    CHECKED += 1
    print(("  OK   " if cond else "  XX   ") + label + (f"   {detail}" if detail and not cond else ""))
    if not cond:
        FAIL.append(label)
    return cond


def void(why):
    print(f"VOID - {why}. Nothing was compared, so nothing passed.")
    sys.exit(1)


def git(*argv):
    return subprocess.run(["git", *argv], capture_output=True, cwd=ROOT)


# ------------------------------------------------------------------------------------------------ the pin
if git("rev-parse", "--verify", f"{PIN}^{{commit}}").returncode != 0:
    void(f"the pin {PIN!r} does not resolve in this clone; set LT_G9_PIN")
if git("merge-base", "--is-ancestor", PIN, "HEAD").returncode != 0:
    void(f"the pin {PIN} is not an ancestor of HEAD, so it is not 'the code before this change'")
blob = git("show", f"{PIN}:{args.variant}/scripts/validate_segment_shapes.py")
if blob.returncode != 0:
    void(f"cannot read {args.variant}/scripts/validate_segment_shapes.py at {PIN}")
if blob.stdout == SCRIPT.read_bytes():
    void(f"the script under test is BYTE-IDENTICAL to the pin's, so every before/after below would compare the "
         f"code with itself")
PIN_DIR = TMP / "pin"
PIN_DIR.mkdir()
PIN_SCRIPT = PIN_DIR / "validate_segment_shapes.py"
PIN_SCRIPT.write_bytes(blob.stdout)


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    sys.path.insert(0, str(path.parent))
    try:
        spec.loader.exec_module(mod)
    finally:
        sys.path.remove(str(path.parent))
    return mod


OLD = load("g9_pin_vss", PIN_SCRIPT)
# THE SCRIPT UNDER TEST FIRST: it imports apply from ITS OWN folder - a mutant beside a copy is then the apply it
# asks - and only after that the tree's real apply, under a name of its own, for the ground truth.
NOW = load("g9_now_vss", SCRIPT)
GT = load("g9_truth_apply", TREE_SCRIPTS / "apply_translations_textmatch.py")
# AND THE PIN'S APPLY, so every control also proves the lifted functions deliver what the closure did.
apply_blob = git("show", f"{PIN}:{args.variant}/scripts/apply_translations_textmatch.py")
if apply_blob.returncode != 0:
    void(f"cannot read {args.variant}/scripts/apply_translations_textmatch.py at {PIN}")
(PIN_DIR / "apply_translations_textmatch.py").write_bytes(apply_blob.stdout)
(PIN_DIR / "source_language_markers.py").write_bytes((TREE_SCRIPTS / "source_language_markers.py").read_bytes())
GT_PIN = load("g9_pin_apply", PIN_DIR / "apply_translations_textmatch.py")
print(f"STEP 15.3 - G9's FIRST HALF, BOTH DIRECTIONS   [{args.variant}]")
print(f"  pin {PIN}; under test {SCRIPT}; ground truth {TREE_SCRIPTS / 'apply_translations_textmatch.py'}")
print("=" * 96)


def seg(t, en=None, keep_no_en=False):
    return {"type": t} if keep_no_en else {"type": t, "en": en}


def tc(t, text):
    return {"type": t, "text": text}


# (name, kind, en_segments, tc_segments, alpha joins at the pin, alpha joins now, accept view, reject view,
#  the words a view glues at a join the English supplies - the joins the check must report)
RJ = " across a tracked change (reject-all)"
AJ = " across a tracked change (accept-all)"
CASES = [
    ("FP G9's shape - a deletion declared without the space its source ends on, as a list pair", "FP",
     [seg("regular", "The price includes "), seg("del", "all"), seg("regular", "costs.")],
     [tc("regular", "Il prezzo comprende "), tc("del", "tutte "), tc("regular", "le spese.")],
     ["del→regular"], [],
     "The price includes costs.", "The price includes all costs.", []),
    ("FP G9's shape - the same deletion meeting the text after an insertion, a join only reject-all makes", "FP",
     [seg("regular", "This notice cancels "), seg("del", "every"), seg("ins", "the said "), seg("regular", "prior notice.")],
     [tc("regular", "Questo avviso annulla "), tc("del", "ogni "), tc("ins", "il "), tc("regular", "avviso precedente.")],
     ["del→regular" + RJ], [],
     "This notice cancels the said prior notice.", "This notice cancels every prior notice.", []),
    ("FP the space restored on the RIGHT segment's leading edge - a list pair and an accept-all join", "FP",
     [seg("regular", "The price includes"), seg("del", " all"), seg("regular", "costs.")],
     [tc("regular", "Il prezzo comprende"), tc("del", " tutte"), tc("regular", " le spese.")],
     ["del→regular", "regular→regular" + AJ], [],
     "The price includes costs.", "The price includes all costs.", []),
    ("TP no space in the source at all - a script written without spaces", "TP",
     [seg("regular", "The price includes "), seg("del", "all"), seg("regular", "costs.")],
     [tc("regular", "价格包括"), tc("del", "全部"), tc("regular", "费用。")],
     ["del→regular"], ["del→regular"],
     "The price includes costs.", "The price includes allcosts.", ["allcosts"]),
    ("TP the source's space on the FAR edge of the segment", "TP",
     [seg("regular", "The price includes"), seg("del", " all"), seg("regular", "costs.")],
     [tc("regular", "Il prezzo comprende"), tc("del", " tutte"), tc("regular", "le spese.")],
     ["del→regular", "regular→regular" + AJ], ["del→regular", "regular→regular" + AJ],
     "The price includescosts.", "The price includes allcosts.", ["includescosts", "allcosts"]),
    ("TP apply reads LIST order: the insertion supplies the space, so none is restored, and reject-all glues", "TP",
     [seg("regular", "This notice cancels"), seg("del", " every"), seg("ins", " the said"), seg("regular", "prior notice.")],
     [tc("regular", "Questo avviso annulla "), tc("del", "ogni "), tc("ins", "il "), tc("regular", "avviso precedente.")],
     ["ins→regular", "del→regular" + RJ], ["del→regular" + RJ],
     "This notice cancels the said prior notice.", "This notice cancels everyprior notice.", ["everyprior"]),
    ("TP a cleared segment is skipped: the insertion past it supplies the space, and reject-all glues", "TP",
     [seg("regular", "This notice cancels"), seg("del", ""), seg("ins", " the said"), seg("regular", "prior notice.")],
     [tc("regular", "Questo avviso annulla "), tc("del", "ogni "), tc("ins", "il "), tc("regular", "avviso precedente.")],
     ["ins→regular", "regular→regular" + RJ], ["regular→regular" + RJ],
     "This notice cancels the said prior notice.", "This notice cancelsprior notice.", ["cancelsprior"]),
    ("TP a segment with no English keeps its source, and that source supplies the space", "TP",
     [seg("regular", "The price includes "), seg("del", "all"), seg("ins", keep_no_en=True), seg("regular", "costs.")],
     [tc("regular", "Il prezzo comprende "), tc("del", "tutte "), tc("ins", " ogni"), tc("regular", "le spese.")],
     ["del→regular" + RJ], ["del→regular" + RJ],
     "The price includes  ognicosts.", "The price includes allcosts.", ["allcosts"]),
    ("TP and on the left: the deletion supplies the space, so the text after it gets none, and accept-all glues",
     "TP",
     [seg("regular", "The price includes"), seg("del", "all "), seg("regular", "costs.")],
     [tc("regular", "Il prezzo comprende"), tc("del", "tutte "), tc("regular", " le spese.")],
     ["regular→del", "regular→regular" + AJ], ["regular→del", "regular→regular" + AJ],
     "The price includescosts.", "The price includesall costs.", ["includescosts", "includesall"]),
]
FP_SEGS = CASES[0][2]
FP_TC = CASES[0][3]
NOT_PAIRED = [
    ("no tc_segments at all", None),
    ("tc_segments one entry short", FP_TC[:-1]),
    ("tc_segments with a type that differs", [FP_TC[0], tc("ins", "tutte "), FP_TC[2]]),
    ("tc_segments not a list", "tutte"),
    ("tc_segments entries not objects", ["a", "b", "c"]),
]


def entry(segs, tcs, idx=0):
    e = {"idx": idx, "text": "invented", "en_segments": copy.deepcopy(segs)}
    if tcs is not None:
        e["tc_segments"] = copy.deepcopy(tcs)
    return e


def findings(mod, entries, name):
    p = TMP / f"{name}.json"
    p.write_text(json.dumps(entries, ensure_ascii=False), encoding="utf-8")
    return mod.validate(str(p))[0]


def alpha_joins(hits):
    return sorted(w for e in hits for _o, w, h in e["hits"] if h[0] == ALPHA)


def other_hits(hits):
    return sorted((e["idx"], o, w, h) for e in hits for o, w, h in e["hits"] if h[0] != ALPHA)


def views(segs, tcs, apply_mod=None):
    """The tree's real apply on an invented paragraph built from the source segments; both views read back."""
    p = ET.Element(f"{W}p")
    for s in tcs:
        r = ET.Element(f"{W}r")
        if s["type"] == "del":
            t = ET.SubElement(r, f"{W}delText")
            wrap = ET.SubElement(p, f"{W}del")
            wrap.append(r)
        else:
            t = ET.SubElement(r, f"{W}t")
            if s["type"] == "ins":
                wrap = ET.SubElement(p, f"{W}ins")
                wrap.append(r)
            else:
                p.append(r)
        t.text = s["text"]
    en = "".join(x.get("en") or "" for x in segs)
    applied = (apply_mod or GT).apply_trackchanges_inplace(p, en, None, en_segments=copy.deepcopy(segs))
    parent = {c: q for q in p.iter() for c in q}

    def under(el, tag):
        cur = parent.get(el)
        while cur is not None:
            if cur.tag == f"{W}{tag}":
                return True
            cur = parent.get(cur)
        return False

    texts = [el for el in p.iter() if el.tag in (f"{W}t", f"{W}delText")]
    accept = "".join(el.text or "" for el in texts if el.tag == f"{W}t" and not under(el, "del"))
    reject = "".join(el.text or "" for el in texts if not under(el, "ins"))
    return applied, accept, reject


print("\nEACH CONTROL - the pin, the code under test, and apply's real delivery")
print("-" * 96)
for n, (name, kind, segs, tcs, at_pin, now, want_accept, want_reject, glue) in enumerate(CASES):
    old_h = findings(OLD, [entry(segs, tcs)], f"old-{n}")
    new_h = findings(NOW, [entry(segs, tcs)], f"new-{n}")
    print(f"  {n + 1}. {name}")
    k = f"{kind}{n + 1}"
    ok(f"{k} at the pin: the alpha joins were {at_pin}", alpha_joins(old_h) == sorted(at_pin),
       f"({alpha_joins(old_h)})")
    ok(f"{k} now: the alpha joins are {now}", alpha_joins(new_h) == sorted(now), f"({alpha_joins(new_h)})")
    ok(f"{k} every other finding identical to the pin's", other_hits(new_h) == other_hits(old_h),
       f"({other_hits(new_h)} vs {other_hits(old_h)})")
    applied, accept, reject = views(segs, tcs)
    ok(f"{k} TRUTH apply delivers accept-all {want_accept!r}", applied and accept == want_accept, f"({accept!r})")
    ok(f"{k} TRUTH apply delivers reject-all {want_reject!r}", applied and reject == want_reject, f"({reject!r})")
    ok(f"{k} TRUTH the words glued at a join, {glue}, are in apply's delivery",
       all(g in accept or g in reject for g in glue), f"({accept!r} / {reject!r})")
    reported = alpha_joins(new_h)
    ok(f"{k} TRUTH the check reports a join exactly where a view glues two words",
       bool(reported) == bool(glue), f"(reports {reported}, glued {glue})")
    ok(f"{k} TRUTH the pin's apply delivers the same two views", views(segs, tcs, GT_PIN) == (applied, accept, reject),
       f"({views(segs, tcs, GT_PIN)})")

print("\nWHERE THE TWO LISTS DO NOT PAIR - the rule exactly as at the pin")
print("-" * 96)
for n, (label, tcs) in enumerate(NOT_PAIRED):
    old_h = findings(OLD, [entry(FP_SEGS, tcs)], f"old-np-{n}")
    new_h = findings(NOW, [entry(FP_SEGS, tcs)], f"new-np-{n}")
    ok(f"ALIGN {label}: the alpha join still fires, as at the pin",
       alpha_joins(new_h) == alpha_joins(old_h) == ["del→regular"], f"({alpha_joins(new_h)} vs {alpha_joins(old_h)})")

print("\nANOTHER RULE IS NOT TOLD")
print("-" * 96)
DIGIT = ([seg("regular", "see Clause"), seg("ins", "5")], [tc("regular", "vedi Articolo "), tc("ins", "5")])
names_old = [h[0] for e in findings(OLD, [entry(*DIGIT)], "old-digit") for _o, _w, h in e["hits"]]
names_new = [h[0] for e in findings(NOW, [entry(*DIGIT)], "new-digit") for _o, _w, h in e["hits"]]
ok("OTHER digit_at_tc_boundary fires now as at the pin, though apply restores the space there",
   "digit_at_tc_boundary" in names_new and names_new == names_old, f"({names_new} vs {names_old})")


def strict(script, entries, name):
    p = TMP / f"{name}.json"
    p.write_text(json.dumps(entries, ensure_ascii=False), encoding="utf-8")
    r = subprocess.run([sys.executable, str(script), str(p), "--strict"], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", env=ENV, cwd=str(TMP))
    return r.returncode, r.stdout, r.stderr


print("\n--strict, AS APPLY RUNS IT")
print("-" * 96)
fps = [entry(c[2], c[3], i) for i, c in enumerate(CASES) if c[1] == "FP"]
tps = [entry(c[2], c[3], i) for i, c in enumerate(CASES) if c[1] == "TP"]
rc, out, err = strict(SCRIPT, fps, "strict-fp")
ok(f"EXIT the {len(fps)} FP paragraphs: rc 0 now, no alpha finding, PASS printed",
   rc == 0 and ALPHA not in out and "PASS:" in out and not err.strip(),
   f"(rc={rc}; {[ln.strip() for ln in out.splitlines() if ln.strip().startswith('[')][:4]}; {err.strip()[-200:]})")
rc, out, _err = strict(PIN_SCRIPT, fps, "strict-fp")
ok(f"EXIT the {len(fps)} FP paragraphs: PROVED rc 1 at the pin, on the alpha finding", rc == 1 and ALPHA in out,
   f"(rc={rc})")
rc, out, _err = strict(SCRIPT, tps, "strict-tp")
ok(f"EXIT the {len(tps)} TP paragraphs: rc 1 now, on the alpha finding", rc == 1 and ALPHA in out, f"(rc={rc})")
unpaired = [entry(FP_SEGS, t, i) for i, (_l, t) in enumerate(NOT_PAIRED)]
rc_n, out_n, err_n = strict(SCRIPT, unpaired, "strict-np")
rc_o, out_o, err_o = strict(PIN_SCRIPT, unpaired, "strict-np")
ok("EXIT paragraphs that do not pair: every printed line and the exit code the pin's",
   (rc_n, out_n, err_n) == (rc_o, out_o, err_o) and rc_n == 1, f"(rc {rc_n} vs {rc_o})")

print("\n" + "=" * 96)
print(f"{CHECKED} check(s), {len(FAIL)} failure(s)")
print("=" * 96)
for f in FAIL:
    print(f"  FAIL  {f}")
sys.exit(1 if FAIL else 0)
