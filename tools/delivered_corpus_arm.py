"""delivered_corpus_arm.py - branch 11 slice 1's acceptance, over the real corpus, both arms.

WHY THIS TOOL EXISTS. `validate_apply.py --delivered` compares the DELIVERED document against
what the notes declared, and nothing already in tools/ can drive it: apply_corpus_diff swaps
apply, postprocess_corpus_arm's arm 0 compares post_process.py ALONE (so a change to
validate_apply.py leaves its self-comparison notice in place), and hf_corpus_diff reads headers
and footers. PLAN-2-step-b.md section 3.2 says so before this was run, not after.

TWO ARMS, STATED BEFORE MEASURING (Wouter, 2026-09-24):

  (a) IT MUST SEE. The 13 frozen workdirs kept the run's own final/word/document.xml -- what
      the July runs delivered, defects and all. The check must report every NAMED defect:
        B3   lost punctuation            D07 D08     class changed, shape punctuation
        C17  cleared whitespace          D02 D07     class edge-space or changed/space
        A15  destroyed tracked change    D08         class readings, or changed
        A1   footnote anchors lost       D05 D09     anchor-lost footnoteReference
        A2   comment anchors lost        D02 D08     anchor-lost commentReference
      A named defect not found means the check is not built correctly. These runs predate
      the journal, so post_process's legitimate edits appear as findings too and are
      REPORTED, never counted as a pass or a failure.

  (b) IT MUST NOT CRY WOLF. The same 13 rebuilt through TODAY's pipeline -- apply over the
      matched source and the frozen notes, post_process with its journal, then the reorder --
      and every finding printed for a person to explain against a register row.

WHAT IT NEVER PRINTS: a filename, a path below the logs root, or any document text. Doc-ids,
paragraph indices, classes and lengths only (CLAUDE.md 5.6). Nothing is written into the logs
folder: every input is copied into a temporary directory first.

    uv run --with lxml python tools/delivered_corpus_arm.py              # both arms, uk
    uv run --with lxml python tools/delivered_corpus_arm.py --variant us
    uv run --with lxml python tools/delivered_corpus_arm.py --arm a      # one arm
"""
import argparse
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from collections import Counter, defaultdict
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.dont_write_bytecode = True
os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")

from lxml import etree  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
LOGS = Path(os.environ.get("LT_LOGS_DIR", ROOT.parent / "legal-translation-logs"))
DOC_ID = re.compile(r"\bD\d{2}B?\b")
ENV = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1", PYTHONDONTWRITEBYTECODE="1")

ap = argparse.ArgumentParser()
ap.add_argument("--variant", choices=("uk", "us"), default="uk")
ap.add_argument("--arm", choices=("a", "b", "both"), default="both")
args = ap.parse_args()
SCRIPTS = ROOT / args.variant / "scripts"
TMP = Path(tempfile.mkdtemp(prefix="b11-delivered-"))
FAIL, CHECKED, VOIDED = [], 0, []


def ok(label, cond, detail=""):
    global CHECKED
    CHECKED += 1
    print(f"  {'OK  ' if cond else 'XX  '} {label}" + (f"   ({detail})" if detail and not cond else ""))
    if not cond:
        FAIL.append(label)


def void(label, why):
    VOIDED.append(label)
    print(f"  ??   {label}   VOID — {why}")


# THE NAMED DEFECTS, PINNED TO PARAGRAPHS DERIVED FROM THE NOTES -- never "any finding of the
# right class". The first version asked exactly that, and A15 on D08 "passed" on an unrelated
# whitespace finding while C17 on D02 passed on any of forty: a check passing for the wrong
# reason. So each expectation is DERIVED, independently of the check, from the notes:
#   C17  every entry with a whitespace-only declared segment (the shape apply used to clear)
#   B3   every entry whose SOURCE tc_segments hold a punctuation-only ins or del
# and the anchor rows compare counts. The register rows supply what the measurement cannot:
# A1 says D09 "was caught by rendering and repaired, so the deliverable is intact", which makes
# D09 a TRUE NEGATIVE; and A15 says D08's repair moved the brackets out of the tracked change
# IN THE NOTES, so declared and delivered agree and no declared-versus-delivered check can see
# it -- slice 2's bracket inventory against the SOURCE is what can.
SPACE = ("edge-space", "inner-space")


def idx_of(rep, pred):
    return {f["idx"] for f in rep["findings"] if f["idx"] is not None and pred(f)}


def anchor(rep, name):
    for a in rep["anchors"]:
        if a["anchor"] == name:
            return a["original"], a["delivered"]
    return None


def derived(notes):
    ws, punct = set(), set()
    for e in notes:
        if not isinstance(e, dict):
            continue
        for s in e.get("en_segments") or []:
            if isinstance(s, dict) and s.get("en") and not s["en"].strip():
                ws.add(e.get("idx"))
        for s in e.get("tc_segments") or []:
            t = (s.get("text") or "") if isinstance(s, dict) else ""
            if s.get("type") in ("ins", "del") and t.strip() and not any(c.isalnum() for c in t):
                punct.add(e.get("idx"))
    return ws, punct


def need_idx(rep, want, pred):
    got = idx_of(rep, pred)
    return bool(want) and want <= got, f"expected {sorted(want)}, flagged {sorted(got & want)}"


NAMED = [
    ("B3", "D07", "lost punctuation at every source punctuation-only tracked change",
     lambda r: need_idx(r, r["_punct"], lambda f: f["class"] == "changed" and f["shape"] == "punctuation")),
    ("C17", "D02", "a whitespace finding at every whitespace-only declared segment",
     lambda r: need_idx(r, r["_ws"], lambda f: f["class"] in SPACE or f["shape"] == "space")),
    ("C17", "D07", "a whitespace finding at every whitespace-only declared segment",
     lambda r: need_idx(r, r["_ws"], lambda f: f["class"] in SPACE or f["shape"] == "space")),
    ("A1", "D05", "footnote anchors below the original",
     lambda r: ((anchor(r, "footnoteReference") or (0, 0))[1] < (anchor(r, "footnoteReference") or (0, 0))[0],
                f"original/delivered {anchor(r, 'footnoteReference')}")),
    ("A2", "D02", "comment anchors below the original",
     lambda r: ((anchor(r, "commentReference") or (0, 0))[1] < (anchor(r, "commentReference") or (0, 0))[0],
                f"original/delivered {anchor(r, 'commentReference')}")),
    ("A2", "D08", "comment anchors below the original",
     lambda r: ((anchor(r, "commentReference") or (0, 0))[1] < (anchor(r, "commentReference") or (0, 0))[0],
                f"original/delivered {anchor(r, 'commentReference')}")),
    ("A1", "D09", "TRUE NEGATIVE: repaired before delivery, so footnote anchors EQUAL the original's",
     lambda r: ((anchor(r, "footnoteReference") or (0, -1))[0] > 0
                and (anchor(r, "footnoteReference") or (0, -1))[0] == (anchor(r, "footnoteReference") or (0, -1))[1],
                f"original/delivered {anchor(r, 'footnoteReference')}")),
]
OUT_OF_REACH = [("B3 and A15", "D08", "repaired before delivery by moving the brackets out of the "
                 "tracked change IN THE NOTES, so declared and delivered agree; slice 2's bracket "
                 "inventory against the SOURCE owns it")]


def corpus_dirs():
    out, cfg = [], ROOT / ".claude" / "evidence-dirs.local"
    names = []
    if cfg.is_file():
        names += [ln.strip() for ln in cfg.read_text(encoding="utf-8", errors="replace").splitlines()
                  if ln.strip() and not ln.strip().startswith("#")]
    if os.environ.get("LT_CORPUS_DIR"):
        names.append(os.environ["LT_CORPUS_DIR"])
    for name in names:
        p = Path(name) if Path(name).is_absolute() else (ROOT.parent / name).resolve()
        if p.is_dir() and any(p.glob("*.docx")):
            out.append(p)
    return out


_TEXTS = {}


def source_paragraphs(cand):
    """Paragraph texts under extraction's contract, cached. Never returned to a printer."""
    k = str(cand)
    if k not in _TEXTS:
        try:
            with zipfile.ZipFile(cand) as z:
                root = etree.fromstring(z.read("word/document.xml"))
            texts = set()
            for p in root.iter(f"{{{W}}}p"):
                pieces = []
                for el in p.iter():
                    if el.tag == f"{{{W}}}t" and el.text:
                        pieces.append(el.text)
                    elif el.tag == f"{{{W}}}br" and el.get(f"{{{W}}}type", "") != "page":
                        pieces.append("\n")
                texts.add("".join(pieces).strip())
            _TEXTS[k] = texts
        except Exception:
            _TEXTS[k] = None
    return _TEXTS[k]


def match_source(wd, notes, corpus):
    """The SOURCE .docx, chosen by which candidate reproduces the notes' `text` -- never by name."""
    wanted = {(e.get("text") or "").strip() for e in notes
              if isinstance(e, dict) and (e.get("text") or "").strip()}
    best, frac = None, 0.0
    for group in [sorted(wd.glob("*.docx"))] + [sorted(d.glob("*.docx")) for d in corpus]:
        for cand in group:
            t = source_paragraphs(cand)
            if not t or not wanted:
                continue
            f = len(wanted & t) / len(wanted)
            if f > frac:
                best, frac = cand, f
        if frac >= 0.9:
            break
    return (best, frac) if best is not None and frac >= 0.5 else (None, frac)


def run(cmd, timeout=1800):
    return subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                          errors="replace", cwd=str(ROOT), env=ENV, timeout=timeout)


def delivered_check(notes_path, xml_path, original, journal, label):
    rj = TMP / f"{label}.report.json"
    cmd = ["uv", "run", "--with", "lxml", "python", str(SCRIPTS / "validate_apply.py"),
           str(notes_path), "--delivered", str(xml_path), "--report-json", str(rj)]
    if original is not None:
        cmd += ["--original", str(original)]
    if journal is not None:
        cmd += ["--journal", str(journal)]
    r = run(cmd, timeout=900)
    if not rj.is_file():
        return None, r.returncode
    return json.loads(rj.read_text(encoding="utf-8")), r.returncode


def edge_vs_source(rep, notes):
    """For each edge-space finding: does the SOURCE paragraph carry whitespace on that same
    edge? Counts only. 'source has it' means the delivery dropped what the original has."""
    by_idx = {e.get("idx"): e for e in notes if isinstance(e, dict)}
    tally = Counter()
    for f in rep["findings"]:
        if f["class"] != "edge-space" or f["idx"] not in by_idx:
            continue
        src = by_idx[f["idx"]].get("text") or ""
        for part in f["shape"].split("+"):
            edge, way = part.split("-") if "-" in part else (part, "?")
            has = (src[:1].isspace() if edge == "lead" else src[-1:].isspace()) if src else False
            tally[f"{part} ({'source has it' if has else 'source has none'})"] += 1
    return tally


def summarise(did, rep, rc):
    c = Counter(rep["counts"])
    shapes = Counter(f"{f['class']}/{f['shape']}" if f["shape"] else f["class"]
                     for f in rep["findings"])
    print(f"  {did:5} examined {rep['examined']:4d}  exact {c['exact']:4d}  rc={rc}  "
          f"unclaimed-delivered {rep['unclaimed_delivered']:3d}  journal: {rep['journal']}")
    if shapes:
        print("        " + "  ".join(f"{k}={v}" for k, v in sorted(shapes.items())))
    for a in rep.get("anchors", []):
        if a["original"] != a["delivered"]:
            print(f"        anchor {a['anchor']}: original {a['original']}, delivered {a['delivered']}")
    idx = defaultdict(list)
    for f in rep["findings"]:
        if f["idx"] is not None:
            idx[f"{f['class']}/{f['shape']}" if f["shape"] else f["class"]].append(f["idx"])
    for k in sorted(idx):
        print(f"        {k} at idx {sorted(idx[k])[:24]}"
              + (f" ... +{len(idx[k]) - 24}" if len(idx[k]) > 24 else ""))


print("=" * 96)
print(f"BRANCH 11 SLICE 1 — the delivered-document check over the real corpus  [{args.variant}]")
print("=" * 96)
if not LOGS.is_dir():
    print("  VOID — the logs root is not present in this clone; said rather than reported clean.")
    sys.exit(2)
workdirs = sorted({p.parent for p in LOGS.rglob("paragraphs.json")})
CORPUS = corpus_dirs()
print(f"  frozen workdirs enumerated: {len(workdirs)} · corpus folder(s) reachable: {len(CORPUS)}")

reports_a, reports_b = {}, {}
for n, wd in enumerate(workdirs, 1):
    ids = DOC_ID.findall(str(wd.relative_to(LOGS)))
    did = ids[-1] if ids else f"D??{n}"
    key = did if did not in reports_a and did not in reports_b else f"{did}#{n}"
    try:
        notes = json.loads((wd / "paragraphs.json").read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        void(f"{key} notes", type(exc).__name__)
        continue
    src, frac = match_source(wd, notes, CORPUS)
    if args.arm in ("a", "both"):
        final_xml = wd / "final" / "word" / "document.xml"
        if not final_xml.is_file():
            void(f"(a) {key}", "no final/word/document.xml kept")
        else:
            w = TMP / f"a{n:02d}"
            w.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(wd / "paragraphs.json", w / "paragraphs.json")
            shutil.copyfile(final_xml, w / "document.xml")
            rep, rc = delivered_check(w / "paragraphs.json", w / "document.xml", src, None, f"a{n:02d}")
            if rep is None:
                void(f"(a) {key}", f"the check wrote no report (rc={rc})")
            else:
                rep["_src"] = frac
                rep["_ws"], rep["_punct"] = derived(notes)
                reports_a[key] = (rep, rc)
    if args.arm in ("b", "both"):
        if src is None:
            void(f"(b) {key}", f"no source matched (best {frac:.0%})")
            continue
        b = TMP / f"b{n:02d}"
        (b / "final" / "word").mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, b / "src.docx")
        for name in ("paragraphs.json", ".validate-state.json", "comments_translations.json",
                     "headers_footers.json", "_boldmap.json"):
            if (wd / name).is_file():
                shutil.copyfile(wd / name, b / name)
        xml = b / "final" / "word" / "document.xml"
        r = run(["uv", "run", "--with", "lxml", "python", str(SCRIPTS / "apply_translations_textmatch.py"),
                 str(b / "src.docx"), str(b / "paragraphs.json"), str(xml)])
        if not xml.is_file():
            void(f"(b) {key}", f"apply produced no output (rc={r.returncode})")
            continue
        pp = run(["uv", "run", "--with", "lxml", "python", str(SCRIPTS / "post_process.py"),
                  str(xml), "--fix", "--variant", args.variant], timeout=900)
        gate = pp.returncode != 0 and "SKILL GATE FIRED" in (pp.stdout or "") + (pp.stderr or "")
        ro = run(["uv", "run", "--with", "lxml", "python", str(SCRIPTS / "reorder_definitions.py"),
                  "--doc", str(xml)], timeout=900)
        journal = b / "post_process_journal.json"
        rep, rc = delivered_check(b / "paragraphs.json", xml, b / "src.docx",
                                  journal if journal.is_file() else None, f"b{n:02d}")
        if rep is None:
            void(f"(b) {key}", f"the check wrote no report (rc={rc})")
        else:
            rep["_steps"] = (f"post_process rc={pp.returncode}{' (drift gate fired)' if gate else ''}, "
                             f"reorder rc={ro.returncode}")
            rep["_edges"] = edge_vs_source(rep, notes)
            reports_b[key] = (rep, rc)

if args.arm in ("a", "both"):
    print("\nARM (a) — THE 13 HISTORICAL DELIVERABLES: IT MUST SEE")
    for key, (rep, rc) in reports_a.items():
        summarise(key, rep, rc)
        if rep.get("_src", 0) < 0.9:
            print(f"        original matched at {rep.get('_src', 0):.0%} — anchors counted against "
                  f"{'no original' if rep.get('_src', 0) < 0.5 else 'a partial match'}")
    print("\n  THE NAMED DEFECTS — pinned to paragraphs derived from the notes:")
    for row, did, what, test in NAMED:
        rep = reports_a.get(did, (None, None))[0]
        if rep is None:
            void(f"{row} on {did}", "that document's report is not available")
            continue
        passed, detail = test(rep)
        ok(f"{row} on {did}: {what}", bool(passed), detail)
        if passed:
            print(f"        {detail}")
    for row, did, why in OUT_OF_REACH:
        print(f"  N/A  {row} on {did}: NOT VISIBLE TO SLICE 1 BY CONSTRUCTION — {why}")
    print(f"\n  examined {len(reports_a)} of {len(workdirs)} workdirs")

if args.arm in ("b", "both"):
    print("\nARM (b) — THE SAME 13 REBUILT THROUGH TODAY'S PIPELINE: IT MUST NOT CRY WOLF")
    for key, (rep, rc) in reports_b.items():
        summarise(key, rep, rc)
        print(f"        {rep['_steps']}")
    classes, edges = Counter(), Counter()
    for rep, _ in reports_b.values():
        classes.update(f"{f['class']}/{f['shape']}" if f["shape"] and f["class"] != "edge-space"
                       else f["class"] for f in rep["findings"])
        edges.update(rep["_edges"])
    print("\n  ALL FINDINGS BY CLASS: " + "  ".join(f"{k}={v}" for k, v in sorted(classes.items())))
    print("  EDGE WHITESPACE AGAINST THE SOURCE: " + "  ".join(f"{k}={v}" for k, v in sorted(edges.items())))
    total = sum(len(rep["findings"]) for rep, _ in reports_b.values())
    print(f"\n  examined {len(reports_b)} of {len(workdirs)} workdirs; findings in all: {total} — "
          f"each must be explained by a register row before the check may block")

shutil.rmtree(TMP, ignore_errors=True)
print("\n" + "=" * 96)
print(f"  {CHECKED} check(s), {len(FAIL)} failure(s), {len(VOIDED)} void")
for v in VOIDED:
    print(f"    VOID  {v}")
print("=" * 96)
sys.exit(1 if FAIL or VOIDED else 0)
