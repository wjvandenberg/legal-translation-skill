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

SLICE 2a (2026-09-25) ADDS, STATED BEFORE MEASURING (PLAN-2-step-b.md section 3.2):
  (a) J1's U+200B at the register's own counts, in the ACCEPT reading -- D01 7, D02 5, D10 11,
      D11 48, D03B 1 -- and none on any other document; D03B 12 the one declared-vs-delivered
      bracket finding; A15's signature at D08 29 and 39 alone, COUNTED; no delivered reading
      unbalanced where its source's balances; 23 other differences from the source, a count.
  (b) --ref REF: NO DELIVERED BYTE MOVES. The chain -- apply, post_process, reorder, repack --
      runs with REF's scripts and with the working tree's, and every output (document.xml, the
      journal, every member of the repacked .docx, by content) and every exit code is compared.
      A REF whose scripts equal the working tree's is a self-comparison and VOID, never a pass.

SLICE 2b (2026-09-25 (3)) CHANGES WHAT (b) ASSERTS, DELIBERATELY, as branch 10 did per slice:
repack now scrubs U+200B and blocks on a source-language remnant, so bytes MUST move -- by a
U+200B removal and nothing else, and only where the pinned tree's delivery carried one. Per
workdir: every exit code equal; every output identical or, for a .docx member, the pinned
bytes with every U+200B removed; members moved IFF the pin's delivery carried a U+200B; and
the pinned plan -- moved on uk D01 x2, D02, D03B, D10, D11, on us D01 x2, D03B, D11, repack
STOPPED by the drift gate on uk D04 D05 and us D02 D06 D09 D10 -- for the documents in the run.
The no-move case is this assertion's special case, so a pin with no U+200B still proves it.
AND THE CHECK NOW READS THE REPACKED .docx wherever repack produced one: the reordered XML is
read before repack, so it cannot see a scrub that happens inside repack. A stopped document is
read from the XML, SAID to be stopped, and never counted as a pass.

WHAT IT NEVER PRINTS: a filename, a path below the logs root, or any document text. Doc-ids,
paragraph indices, classes and lengths only (CLAUDE.md 5.6). Nothing is written into the logs
folder: every input is copied into a temporary directory first.

    uv run --with lxml python tools/delivered_corpus_arm.py              # both arms, uk
    uv run --with lxml python tools/delivered_corpus_arm.py --variant us
    uv run --with lxml python tools/delivered_corpus_arm.py --arm a      # one arm
    uv run --with lxml python tools/delivered_corpus_arm.py --arm b --ref 3654842 --doc D02 --doc D03
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
ap.add_argument("--doc", action="append", help="limit to these corpus doc-ids (run in batches)")
ap.add_argument("--ref", default=None, help="arm (b): also rebuild with this commit's scripts, compare bytes")
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
                 "tracked change IN THE NOTES, so declared and delivered agree; slice 2a's bracket "
                 "inventory against the SOURCE owns it -- A15's signature, below")]

# SLICE 2a's EXPECTATIONS. Each names the documents it needs and is VOID, never passed, when a
# --doc subset leaves one out. J1's counts are the register's, in the accept reading.
J1 = {"D01": 7, "D02": 5, "D10": 11, "D11": 48, "D03B": 1}
ALL_DOCS = ("D01", "D02", "D03", "D03B", "D04", "D05", "D06", "D07", "D08", "D09", "D10", "D11")


def did_of(key):
    return key.split("#")[0]


def per_doc(reports, fn):
    out = defaultdict(list)
    for key, (rep, _) in reports.items():
        out[did_of(key)].append(fn(rep))
    return dict(sorted(out.items()))


def zacc(rep):
    return (rep.get("zwsp") or {}).get("accept")


def bidx(rep, prefix):
    return sorted(f["idx"] for f in rep["findings"] if f["class"] == "bracket" and f["shape"].startswith(prefix))


def brk(rep, k):
    return (rep.get("brackets") or {}).get(k, 0)


NAMED_2A = [
    ("J1", tuple(J1), "U+200B at the register's counts, accept reading, on each of its five documents",
     lambda R: (all(n in per_doc(R, zacc).get(d, []) for d, n in J1.items()), f"accept counts {per_doc(R, zacc)}")),
    ("J1", ALL_DOCS, "TRUE NEGATIVE: no U+200B on any other document",
     lambda R: (all(set(v) == {0} for d, v in per_doc(R, zacc).items() if d not in J1), f"{per_doc(R, zacc)}")),
    ("D03B 12", ALL_DOCS, "the ONE declared-vs-delivered bracket finding in the corpus",
     lambda R: ({d: v for d, v in per_doc(R, lambda r: bidx(r, "declared:")).items() if any(v)}
                == {"D03B": [[12]]}, f"{per_doc(R, lambda r: bidx(r, 'declared:'))}")),
    ("A15", ALL_DOCS, "A15's signature at D08 29 and 39 alone, COUNTED and never blocking",
     lambda R: ({d: v for d, v in per_doc(R, lambda r: bidx(r, "source:")).items() if any(v)} == {"D08": [[29, 39]]}
                and all(not f["blocking"] for rep, _ in R.values() for f in rep["findings"]
                        if f["class"] == "bracket" and f["shape"].startswith("source:")),
                f"{per_doc(R, lambda r: bidx(r, 'source:'))}")),
    ("brackets", ALL_DOCS, "no delivered reading unbalanced where its source's balances (the naive test: 15)",
     lambda R: (sum(brk(rep, "unbalanced") for rep, _ in R.values()) == 0,
                f"{per_doc(R, lambda r: brk(r, 'unbalanced'))}")),
    ("brackets", ALL_DOCS, "23 other differences from the source, a count only",
     lambda R: (sum(brk(rep, "other") for rep, _ in R.values()) == 23, f"{per_doc(R, lambda r: brk(r, 'other'))}")),
]


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
    # WOUTER'S RULING, 2026-09-24: a trailing-whitespace loss the source shares is COUNTED and
    # never blocks. Printed per document, because a report that folded it into one total would
    # hide which documents carry anything that still blocks. A report written by a check that
    # predates the ruling has no such field, and says so rather than reading as zero.
    print(f"        blocking {rep.get('blocking', 'n/a — pre-ruling report')}  "
          f"counted {rep.get('counted', 'n/a — pre-ruling report')}")
    z, b = rep.get("zwsp"), rep.get("brackets")
    print(f"        U+200B accept {z['accept']} reject {z['reject']} in {z['paragraphs']} paragraph(s) · "
          f"brackets declared {b['declared']} unbalanced {b['unbalanced']} a15 {b['a15']} other {b['other']} "
          f"(paired {b['paired']}, no source {b['no_source']})" if z and b
          else "        U+200B / brackets: n/a — a report written before slice 2a")
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
print(f"  frozen workdirs enumerated: {len(workdirs)} · corpus folder(s) reachable: {len(CORPUS)}"
      + (f" · limited to {' '.join(args.doc)}" if args.doc else ""))

REFTREE, BYTES, BLOCK_NOTE = None, {}, {}
# WHICH GATE STOPPED REPACK, by the fixed text of its own refusal -- a label is printed, never
# repack's output, which can quote the document.
REPACK_GATES = (("lexicon", "lexicon_compliance.py --stage pre-repack returned exit code"),
                ("validate_apply", "validate_apply.py --strict (post-modification check) returned exit code"),
                ("glossary", "and --glossary was not supplied"),
                ("headers/footers", "original (untranslated) headers/footers"),
                ("integrity", "failed its own integrity checks"),
                ("zwsp-survived", "U+200B SURVIVED THE SCRUB"),
                ("remnant", "SOURCE-LANGUAGE REMNANT"))
# SLICE 2b's PINNED PLAN (PLAN-2-step-b.md section 3.2): the workdirs per document whose delivery
# must move, and the documents repack never reaches because post_process's drift gate stops them.
MOVE_2B = {"uk": {"D01": 2, "D02": 1, "D03B": 1, "D10": 1, "D11": 1},
           "us": {"D01": 2, "D03B": 1, "D11": 1}}
STOP_2B = {"uk": {"D04", "D05"}, "us": {"D02", "D06", "D09", "D10"}}
ZW = "​".encode("utf-8")
ZREF = re.compile(rb"&#(?:0*8203|[xX]0*200[bB]);")


def zcount(b):
    return b.count(ZW) + len(ZREF.findall(b)) if b else 0


def zstrip(b):
    return ZREF.sub(b"", b.replace(ZW, b""))
INPUTS = ("paragraphs.json", ".validate-state.json", "comments_translations.json",
          "headers_footers.json", "_boldmap.json")
if args.ref and args.arm in ("b", "both"):
    REFTREE = TMP / "ref_scripts"
    prefix = f"{args.variant}/scripts/"
    names = run(["git", "ls-tree", "-r", "--name-only", args.ref, prefix]).stdout.split()
    for name in names:
        dest = REFTREE / name[len(prefix):]
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(subprocess.run(["git", "show", f"{args.ref}:{name}"], capture_output=True,
                                        cwd=str(ROOT), check=True).stdout)
    here = sorted(str(p.relative_to(SCRIPTS)).replace("\\", "/") for p in SCRIPTS.rglob("*.py"))
    same = [r for r in here if (REFTREE / r).is_file() and (REFTREE / r).read_bytes() == (SCRIPTS / r).read_bytes()]
    print(f"  --ref {args.ref}: {len(names)} file(s) at the ref · {len(here) - len(same)} of {len(here)} "
          f"script(s) differ from the working tree")
    if len(same) == len(here) and len(names) == len(here):
        void("the byte comparison", f"{args.ref}'s scripts equal the working tree's — a self-comparison")
        REFTREE = None


def side_parts(wd, d):
    """repack's side-part flags, from the translated parts the July run kept in final/word -- the
    same bytes for both trees, so the chain reaches a .docx. A glossary part the original carries
    and the run did not keep is passed AS THE ORIGINAL'S, the keep-as-is decision repack's own help
    names. The body is today's; only the side parts are July's."""
    fw, out = wd / "final" / "word", []
    hf = sorted(p for p in fw.glob("*.xml") if re.match(r"(header|footer)\d+\.xml$", p.name)) if fw.is_dir() else []
    if hf:
        (d / "hf" / "word").mkdir(parents=True, exist_ok=True)     # repack reads <dir>/word/headerN.xml
        for p in hf:
            shutil.copyfile(p, d / "hf" / "word" / p.name)
        out += ["--headers-footers-dir", str(d / "hf")]
    for flag, name in (("--comments", "comments.xml"), ("--footnotes", "footnotes.xml"),
                       ("--endnotes", "endnotes.xml"), ("--numbering", "numbering.xml")):
        if (fw / name).is_file():
            shutil.copyfile(fw / name, d / name)
            out += [flag, str(d / name)]
    gl = d / "glossary.xml"
    if (fw / "glossary" / "document.xml").is_file():
        shutil.copyfile(fw / "glossary" / "document.xml", gl)
    else:
        with zipfile.ZipFile(d / "src.docx") as z:
            if "word/glossary/document.xml" in z.namelist():
                gl.write_bytes(z.read("word/glossary/document.xml"))
    return out + (["--glossary", str(gl)] if gl.is_file() else [])


def chain(scripts_dir, d, src, wd):
    """apply -> post_process -> reorder -> repack in d, inputs copied from wd. Keeps a copy of the
    reordered XML (the check's input, as in slice 1) before repack runs. Returns (rcs, pp)."""
    (d / "final" / "word").mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, d / "src.docx")
    for name in INPUTS:
        if (wd / name).is_file():
            shutil.copyfile(wd / name, d / name)
    xml, py = d / "final" / "word" / "document.xml", ["uv", "run", "--with", "lxml", "python"]
    rcs = {"apply": run(py + [str(scripts_dir / "apply_translations_textmatch.py"), str(d / "src.docx"),
                              str(d / "paragraphs.json"), str(xml)]).returncode}
    if not xml.is_file():
        return rcs, None
    pp = run(py + [str(scripts_dir / "post_process.py"), str(xml), "--fix", "--variant", args.variant], timeout=900)
    rcs["post_process"] = pp.returncode
    rcs["reorder"] = run(py + [str(scripts_dir / "reorder_definitions.py"), "--doc", str(xml)], timeout=900).returncode
    shutil.copyfile(xml, d / "checked.xml")
    rp = run(py + [str(scripts_dir / "repack_docx.py"), str(d / "src.docx"), str(xml),
                   str(d / "delivered.docx"), "--paragraphs", str(d / "paragraphs.json")]
             + side_parts(wd, d), timeout=900)
    out = (rp.stdout or "") + (rp.stderr or "")
    rcs["repack"] = rp.returncode
    rcs["repack_gate"] = next((label for label, marker in REPACK_GATES if marker in out),
                              "none" if rp.returncode == 0 else "unrecognised")
    # What the remnant block ran in and which ADVISORY markers it warned on: a language name,
    # zip member names and the skill's own marker patterns -- never repack's context snippets.
    lang = re.search(r"Remnant block: language=(\w+)", out)
    BLOCK_NOTE[d.name] = (lang.group(1) if lang else ("skipped" if "Remnant block skipped" in out
                                                      else "not reached"),
                          Counter(f"{m.group(1)} {m.group(2)}" for m in re.finditer(
                              r"WARNING \(ADVISORY, not blocking\): (\S+): (\S+) —", out))
                          + Counter({"(beyond the ten printed)": int(m.group(1)) for m in re.finditer(
                              r"\.\.\. (\d+) more advisory hit", out)}))
    return rcs, pp


def outputs(d):
    """Every output by content: the XML, the journal, each member of the repacked .docx."""
    out = {rel: ((d / rel).read_bytes() if (d / rel).is_file() else None)
           for rel in ("final/word/document.xml", "checked.xml", "post_process_journal.json")}
    if (d / "delivered.docx").is_file():
        with zipfile.ZipFile(d / "delivered.docx") as z:
            for name in sorted(z.namelist()):
                out["docx:" + name] = z.read(name)
    else:
        out["docx"] = None
    return out


def compare(new, ref):
    """Slice 2b's sense: each output identical, or a .docx member that is the PINNED bytes with
    every U+200B removed and none left. Returns (moved members, U+200B removed, other movement,
    whether the pin's delivery carried any U+200B at all)."""
    moved, removed, other = [], 0, []
    for k in sorted(set(new) | set(ref)):
        a, b = new.get(k), ref.get(k)
        if a == b:
            continue
        if k.startswith("docx:") and a is not None and b is not None and zstrip(b) == a and not zcount(a):
            moved.append(k[5:])
            removed += zcount(b)
        else:
            other.append(k)
    carried = any(zcount(v) for k, v in ref.items() if k.startswith("docx:"))
    return moved, removed, other, carried


reports_a, reports_b = {}, {}
for n, wd in enumerate(workdirs, 1):
    ids = DOC_ID.findall(str(wd.relative_to(LOGS)))
    did = ids[-1] if ids else f"D??{n}"
    key = did if did not in reports_a and did not in reports_b else f"{did}#{n}"
    if args.doc and did not in args.doc:
        continue
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
        rcs, pp = chain(SCRIPTS, b, src, wd)
        if pp is None:
            void(f"(b) {key}", f"apply produced no output (rc={rcs['apply']})")
            continue
        gate = pp.returncode != 0 and "SKILL GATE FIRED" in (pp.stdout or "") + (pp.stderr or "")
        if REFTREE is not None:
            rb = TMP / f"r{n:02d}"
            rrcs, _ = chain(REFTREE, rb, src, wd)
            dn, dr = outputs(b), outputs(rb)
            BYTES[key] = (rrcs == rcs, compare(dn, dr), len(dn), rcs, rrcs)
            shutil.rmtree(rb, ignore_errors=True)
        journal = b / "post_process_journal.json"
        # THE REPACKED .docx WHERE REPACK PRODUCED ONE (slice 2b): the reordered XML predates
        # repack, so it cannot see the scrub. A stopped document is read from the XML, and said.
        docx_out = b / "delivered.docx"
        target = docx_out if docx_out.is_file() else b / "checked.xml"
        rep, rc = delivered_check(b / "paragraphs.json", target, b / "src.docx",
                                  journal if journal.is_file() else None, f"b{n:02d}")
        if rep is None:
            void(f"(b) {key}", f"the check wrote no report (rc={rc})")
        else:
            rep["_read"] = "docx" if docx_out.is_file() else f"xml — repack STOPPED ({rcs['repack_gate']})"
            rep["_gate"] = rcs["repack_gate"]
            rep["_block"] = BLOCK_NOTE.get(b.name, ("not reached", Counter()))
            rep["_steps"] = (f"post_process rc={pp.returncode}{' (drift gate fired)' if gate else ''}, "
                             f"reorder rc={rcs['reorder']}, repack rc={rcs['repack']}"
                             f" [{rcs['repack_gate']}] · the check read the {rep['_read']}")
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
    print("\n  SLICE 2a — U+200B AND BRACKETS, pinned to documents:")
    present = {did_of(k) for k in reports_a}
    for row, needs, what, test in NAMED_2A:
        missing = [d for d in needs if d not in present]
        if missing:
            void(f"{row}: {what}", f"needs {' '.join(missing)}, not in this run")
            continue
        passed, detail = test(reports_a)
        ok(f"{row}: {what}", bool(passed), detail)
        if passed:
            print(f"        {detail}")
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
    blk = [(key, f) for key, (rep, _) in reports_b.items() for f in rep["findings"]
           if f.get("blocking", True)]
    print(f"\n  examined {len(reports_b)} of {len(workdirs)} workdirs; findings in all: {total} — "
          f"{len(blk)} BLOCKING, {total - len(blk)} counted under Wouter's ruling (2026-09-24). "
          f"Each blocking one must be explained by a register row before the check may block")
    bclasses = Counter(f"{f['class']}/{f['shape']}" if f["shape"] else f["class"] for _, f in blk)
    print("  BLOCKING BY CLASS: " + "  ".join(f"{k}={v}" for k, v in sorted(bclasses.items())))
    by_doc = defaultdict(list)
    for key, f in blk:
        by_doc[key].append(f"{f['class']}/{f['shape']}@{f['idx']}" if f["idx"] is not None
                           else f"{f['class']}/{f['shape']}")
    for key in by_doc:
        print(f"    {key:6} {' '.join(by_doc[key])}")
    print("  U+200B / BRACKETS IN ALL: " + "  ".join(
        f"{k}={sum((rep.get(g) or {}).get(k, 0) for rep, _ in reports_b.values())}"
        for g, ks in (("zwsp", ("accept", "reject", "paragraphs")),
                      ("brackets", ("declared", "unbalanced", "a15", "other"))) for k in ks))
    # SLICE 2b, the delivered check's own numbers: no U+200B where repack ran; the text and anchor
    # findings, the non-U+200B blocking ones, printed per document; no delivery refused by the
    # remnant block. A stopped document is listed as stopped and asserts nothing.
    print("\n  SLICE 2b — THE DELIVERED CHECK ON THE REPACKED .docx:")
    for key, (rep, _) in reports_b.items():
        z = rep.get("zwsp") or {}
        txt = sorted((f['class'], f['shape'], f['idx']) for f in rep["findings"]
                     if f.get("blocking", True) and f["class"] != "zwsp")
        if rep.get("_read") != "docx":
            print(f"    {key:6} STOPPED — {rep['_read']}; U+200B accept {z.get('accept')} reject {z.get('reject')} "
                  f"in {z.get('paragraphs')} paragraph(s), the scrub never ran; text/anchor blocking {len(txt)}")
            continue
        ok(f"{key}: the repacked .docx carries 0 U+200B in either reading",
           not z.get("accept") and not z.get("reject"), f"accept {z.get('accept')} reject {z.get('reject')}")
        blang, badv = rep.get("_block", ("n/a", Counter()))
        print(f"        remnant block: language {blang}; advisory warnings {sum(badv.values())}"
              + (" — " + "  ".join(f"{k} x{v}" for k, v in sorted(badv.items())) if badv else ""))
        print(f"        text/anchor blocking {len(txt)}: "
              + " ".join(f"{c}/{s}@{i}" if i is not None else f"{c}/{s}" for c, s, i in txt))
    refused = [k for k, (rep, _) in reports_b.items() if rep.get("_gate") in ("remnant", "zwsp-survived")]
    ok(f"no delivery refused by the remnant block or the U+200B survival check "
       f"({len(reports_b)} examined)", not refused, f"refused: {refused}")
    stopped = sorted({did_of(k) for k, (rep, _) in reports_b.items() if rep.get("_read") != "docx"})
    present = {did_of(k) for k in reports_b}
    ok(f"repack STOPPED exactly where the plan says ({args.variant}, of the documents in this run)",
       set(stopped) == STOP_2B[args.variant] & present, f"stopped {stopped}")
    if REFTREE is not None:
        print(f"\n  SLICE 2b — BYTES MOVE BY U+200B REMOVAL ONLY, AND ONLY WHERE THE PIN'S DELIVERY "
              f"CARRIED ONE — the chain run with {args.ref}'s scripts and the working tree's:")
        moved_by_doc = defaultdict(int)
        for key, (same_rc, (moved, removed, other, carried), nparts, rcs, rrcs) in BYTES.items():
            ok(f"{key}: every exit code equal {rcs}", same_rc, f"now {rcs}, at the ref {rrcs}")
            ok(f"{key}: of {nparts} output(s), nothing moved but U+200B removals",
               not other, f"other movement in {other}")
            ok(f"{key}: moved IFF the pin's delivery carried a U+200B "
               f"({'carried' if carried else 'none'}; {len(moved)} member(s), {removed} U+200B removed"
               + (f": {' '.join(moved)}" if moved else "") + ")", bool(moved) == carried)
            moved_by_doc[did_of(key)] += bool(moved)
        want = {d: n for d, n in MOVE_2B[args.variant].items() if d in present}
        got = {d: n for d, n in moved_by_doc.items() if n}
        ok(f"the workdirs that moved are exactly the plan's ({args.variant}, of the documents in this run)",
           got == want, f"moved {got}, plan {want}")
        print(f"  compared {len(BYTES)} of {len(reports_b)} rebuilt workdirs")

shutil.rmtree(TMP, ignore_errors=True)
print("\n" + "=" * 96)
print(f"  {CHECKED} check(s), {len(FAIL)} failure(s), {len(VOIDED)} void")
for v in VOIDED:
    print(f"    VOID  {v}")
print("=" * 96)
sys.exit(1 if FAIL or VOIDED else 0)
