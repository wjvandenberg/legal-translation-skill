# -*- coding: utf-8 -*-
"""FREEZE THE TRANSLATED INTERMEDIATES FROM THE JULY RUNS.

THE TRICK THIS MAKES POSSIBLE, and it is what makes the whole test method affordable. The
expensive, non-repeatable half of a run is the translation: a model, 20 to 50 minutes, and
about 40% of paragraphs differing between two runs of the same document. But MECHANICALLY
two runs are identical -- that is measured, on the project's only same-document repeat. So
with the translated notes frozen, the entire mechanical half becomes a DETERMINISTIC
FUNCTION: run the scripts, compare the bytes. Seconds, repeatable, no model.

THEY CAN NEVER BE COMMITTED, AND THIS SCRIPT NEVER COPIES THEM ANYWHERE. A frozen
intermediate holds the document's full source text AND its full English text side by side --
the most content-rich artefact this project has ever produced. The location rule has always
covered them in principle and this is the first time it is applied to them in practice:
they stay in the logs folder, outside the repository, and `.gitignore` names their shape by
path.

What this writes is a CATALOGUE: for each document, which files make up its frozen set and
the SHA-256 of each. The catalogue records no document text, so the catalogue itself is
safe -- but it is still written outside the repository, because a per-document file
inventory is a description of the corpus.

    uv run python tools/freeze_intermediates.py            # report
    uv run python tools/freeze_intermediates.py --write    # write the catalogue
    uv run python tools/freeze_intermediates.py --verify   # has anything moved since?
"""
import hashlib
import io
import json
import os
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parent.parent
LOGS = Path(os.environ.get("LT_LOGS_DIR", ROOT.parent / "legal-translation-logs"))
CATALOGUE = LOGS / "frozen-intermediates.json"

# The artefacts that make a run's mechanical half reproducible. `paragraphs.json` is the one
# that matters -- it carries the translation. The rest are the auxiliary translations and
# the state the later steps read.
WANTED = ["paragraphs.json", ".validate-state.json", "comments_translations.json",
          "headers_footers.json", "_boldmap.json"]

WRITE = "--write" in sys.argv
VERIFY = "--verify" in sys.argv

if not LOGS.exists():
    print(f"  logs folder not reachable at {LOGS}")
    print("  This is a SKIP, not a pass. Set LT_LOGS_DIR.")
    sys.exit(0)

# KEYED BY DIRECTORY, NOT BY DOC-ID — A BUG FIX, NOT A REFACTOR. This read
# `runs[doc] = ...`. D01 has TWO run directories, and that is deliberate evidence rather
# than clutter: the register cites "an independently abandoned earlier run of the same
# document" as the proof that A3's tab relocation is DETERMINISTIC. Keyed by doc-id the
# second silently overwrote the first, so the tool reported 12 run directories where 13
# exist, and the catalogue it wrote was missing one run's artefacts entirely.
#
# THE ONLY SYMPTOM WAS A COUNT, which is why it survived: "12 run director(ies)" over a
# corpus everyone thinks of as twelve documents reads exactly right. A frozen BASELINE
# that quietly drops one of its own members is the one thing a baseline may not do.
# Found 2026-09-01 while pinning branch 6's byte comparison to this catalogue.
runs = {}
seen_docs = {}
for wd in sorted(LOGS.rglob("wd")) + sorted(LOGS.rglob("wd-*")):
    if not wd.is_dir():
        continue
    # D02/wd -> D02 ; BATCH-.../wd-D03B -> D03B
    doc = wd.name[3:] if wd.name.startswith("wd-") else wd.parent.name
    files = {}
    for name in WANTED:
        p = wd / name
        if p.is_file():
            files[name] = {"bytes": p.stat().st_size,
                           "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}
    if files:
        rel = str(wd.relative_to(LOGS)).replace("\\", "/")
        seen_docs[doc] = seen_docs.get(doc, 0) + 1
        # THE LABEL IS THE DOC-ID PLUS AN ORDINAL, AND NEVER THE DIRECTORY NAME. A run
        # directory can sit under a batch folder whose name is not committable, and this
        # label is PRINTED — so it carries a file's place in the corpus and nothing else,
        # which is the same licence tools/evidence_ls.py operates under. CLAUDE.md 5.4.
        label = doc if seen_docs[doc] == 1 else f"{doc} #{seen_docs[doc]}"
        runs[rel] = {"doc": doc, "label": label, "dir": rel, "files": files}

print("=" * 96)
print("FROZEN INTERMEDIATES — the July runs, catalogued where they lie")
print("=" * 96)
for key in sorted(runs, key=lambda k: runs[k]["label"]):
    f = runs[key]["files"]
    total = sum(v["bytes"] for v in f.values())
    core = "paragraphs.json" in f
    print(f"  {runs[key]['label']:<9} {len(f)} file(s)  {total:>9,} B  "
          f"{'translation present' if core else 'NO paragraphs.json — not usable as a fixture'}")
usable = [k for k in runs if "paragraphs.json" in runs[k]["files"]]
docs = sorted({m["doc"] for m in runs.values()})
print()
print(f"  {len(runs)} run director(ies) · {len(usable)} carry a translated intermediate")
# BOTH NUMBERS, BECAUSE THEY DIFFER AND THE DIFFERENCE IS THE THING THAT WAS HIDDEN.
print(f"  {len(docs)} distinct corpus doc-id(s) — a doc-id with more than one run is "
      f"labelled #2, #3 …")
print(f"  location: {LOGS}   —  OUTSIDE the repository, and it stays there")

if VERIFY:
    if not CATALOGUE.exists():
        print("\n  no catalogue to verify against — run with --write first")
        sys.exit(1)
    old = json.loads(CATALOGUE.read_text(encoding="utf-8"))["runs"]
    drift = []
    # A CATALOGUE WRITTEN BEFORE 2026-09-01 IS KEYED BY DOC-ID; ONE WRITTEN AFTER IS KEYED
    # BY DIRECTORY. Accept both, or the key-shape fix would report every artefact GONE and
    # look exactly like the drift it exists to detect.
    by_dir = {m["dir"]: k for k, m in runs.items()}
    for key, meta in old.items():
        label = meta.get("label") or meta.get("doc") or key
        cur = runs.get(key)
        if cur is None and meta.get("dir") in by_dir:
            cur = runs[by_dir[meta["dir"]]]
        if cur is None:
            # Old-shape key: fall back to the first run carrying that doc-id.
            cur = next((m for m in runs.values() if m["doc"] == key), None)
        files_now = (cur or {}).get("files", {})
        for name, want in meta["files"].items():
            got = files_now.get(name)
            if got is None:
                drift.append(f"{label}/{name}: GONE")
            elif got["sha256"] != want["sha256"]:
                drift.append(f"{label}/{name}: CHANGED")
    # AND THE SAME BLIND SPOT FROM THE OTHER SIDE — fix the CLASS, not the caller. The loop
    # above only ever iterated the CATALOGUE, so a run directory present on disk and absent
    # from the catalogue was invisible: precisely how D01's second run went unrecorded for
    # weeks while --verify reported VERIFIED every time.
    catalogued_dirs = {m.get("dir", k) for k, m in old.items()}
    # THE TEST IS THE DIRECTORY AND NOTHING ELSE. An earlier draft of this line also required
    # the doc-id to be absent from the catalogue, which defeated the whole check: D01's second
    # run has doc-id D01, the old catalogue HAS a D01 key, so the one run this was written to
    # find was the one run it excluded. A guard that cannot fire on its own founding case.
    uncatalogued = sorted(m["label"] for m in runs.values()
                          if m["dir"] not in catalogued_dirs)
    for label in uncatalogued:
        drift.append(f"{label}: PRESENT ON DISK, ABSENT FROM THE CATALOGUE — re-run --write")
    print()
    print("=" * 96)
    if drift:
        print(f"  {len(drift)} frozen artefact(s) have MOVED since the catalogue was written:")
        for d in drift:
            print(f"      {d}")
        print("  A frozen baseline that changes is not a baseline. Investigate before")
        print("  trusting any byte comparison made against it.")
        sys.exit(1)
    print(f"  VERIFIED — all {sum(len(m['files']) for m in old.values())} artefacts unchanged.")
    sys.exit(0)

if WRITE:
    CATALOGUE.write_text(json.dumps(
        {"_what": "SHA-256 catalogue of the frozen translated intermediates. No document "
                  "text here, but a per-document file inventory is still a description of "
                  "the corpus, so this lives outside the repository with the runs it "
                  "describes.",
         "_frozen": "These are a BASELINE. Do not edit them. Branches 15 and 16 change the "
                    "notes format and must REGENERATE them from the archived runs, never "
                    "by re-translating -- re-translating moves the baseline, which is the "
                    "one thing a baseline may not do.",
         "runs": runs}, indent=1, sort_keys=True), encoding="utf-8")
    print(f"\n  catalogue written: {CATALOGUE}")
    print("  Re-run with --verify before any byte comparison to prove nothing has moved.")
else:
    print("\n  (report only — pass --write to record the catalogue)")
print("=" * 96)
