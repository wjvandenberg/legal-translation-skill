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

runs = {}
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
        runs[doc] = {"dir": str(wd.relative_to(LOGS)).replace("\\", "/"), "files": files}

print("=" * 96)
print("FROZEN INTERMEDIATES — the July runs, catalogued where they lie")
print("=" * 96)
for doc in sorted(runs):
    f = runs[doc]["files"]
    total = sum(v["bytes"] for v in f.values())
    core = "paragraphs.json" in f
    print(f"  {doc:<7} {len(f)} file(s)  {total:>9,} B  "
          f"{'translation present' if core else 'NO paragraphs.json — not usable as a fixture'}")
usable = [d for d in runs if "paragraphs.json" in runs[d]["files"]]
print()
print(f"  {len(runs)} run director(ies) · {len(usable)} carry a translated intermediate")
print(f"  location: {LOGS}   —  OUTSIDE the repository, and it stays there")

if VERIFY:
    if not CATALOGUE.exists():
        print("\n  no catalogue to verify against — run with --write first")
        sys.exit(1)
    old = json.loads(CATALOGUE.read_text(encoding="utf-8"))["runs"]
    drift = []
    for doc, meta in old.items():
        for name, want in meta["files"].items():
            got = runs.get(doc, {}).get("files", {}).get(name)
            if got is None:
                drift.append(f"{doc}/{name}: GONE")
            elif got["sha256"] != want["sha256"]:
                drift.append(f"{doc}/{name}: CHANGED")
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
