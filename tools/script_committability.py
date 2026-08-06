# -*- coding: utf-8 -*-
"""WHICH OF OUR SCRIPTS MAY BE COMMITTED -- measured, not assumed.

Wouter, 2026-08-06: "I don't want confidentiality review to be committed btw."

THE TEST, as the charter states it: not "is this a script?" but **"does this file hold one
real string per pattern?"** A scanner is publishable; the list it reads is not. Some scripts
hold real strings BY DESIGN -- a counted replacement has to carry its own "before" text, so
a script that removes a real string necessarily contains every one it removed.

THREE THINGS THIS GAINED WHEN IT WAS PROMOTED OUT OF `temp/` ON 2026-08-06, each of which
was a hole rather than a refinement:

  1. IT NOW SCANS `tools/`. The draft scanned `temp/` only -- the scratch folder, which is
     gitignored. The folder that actually gets committed was outside the measurement.
  2. IT NOW SCANS `../legal-translation-private/tools/`. The charter names four scripts for
     `tools/` that live there, and the probes had never been run over them. That is how
     `confidentiality_sweep.py` was found to hold a real corpus descriptor while the charter
     listed it as a `tools/` script.
  3. IT NOW RUNS THE 93-PATTERN NAME LIST. The draft ran the descriptor list and the shape
     probes but never the name list -- the largest pattern set this project owns -- against
     its own stated rule of "one real string per pattern". Measured effect: over `temp/` it
     changes nothing, because every script holding a name also holds a path and the path
     probe already caught it. It earns its place in the private folder, where three files
     carry a name and no path.

OUTPUT POLICY, copied from `leakage_scan.py` and for its reason: a hit is a COUNT and a
CATEGORY, never the matched text. This output lands in transcripts and scrollback, and a
client name reproduced there is the exact leak the list exists to prevent. `--show` reveals.

Exit codes:  0 = every committable folder is clean · 1 = something committable holds a real
string · 2 = a pattern list is missing, so the control has NOT run.

    uv run python tools/script_committability.py
    uv run python tools/script_committability.py --show
"""
import io
import os
import re
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parent.parent
PRIV = Path(os.environ.get("LT_PRIVATE_DIR", ROOT.parent / "legal-translation-private"))
SHOW = "--show" in sys.argv


def load(env, default):
    p = Path(os.environ.get(env, default))
    return ([l.strip() for l in p.read_text(encoding="utf-8").splitlines()
             if l.strip() and not l.lstrip().startswith("#")] if p.exists() else None)


DESC = load("CORPUS_DESCRIPTORS_FILE", PRIV / "corpus-descriptors.txt")
NAMES = load("LEAKAGE_LIST_PATH", PRIV / "leakage-names.txt")

if DESC is None or NAMES is None:
    missing = [n for n, v in [("corpus-descriptors.txt", DESC),
                              ("leakage-names.txt", NAMES)] if v is None]
    print(f"CONTROL VOID: {', '.join(missing)} not found under {PRIV}.")
    print("A control that cannot load its list has NOT run. This is not a clean result.")
    sys.exit(2)

PROBES = [
    ("corpus subject-matter descriptor", "(?i)" + "|".join(DESC)),
    ("a name or term from the 93-pattern list", "(?i)" + "|".join(NAMES)),
    ("absolute or home path",
     r"[A-Za-z]:\\[\w\-.]+(?:\\[\w\-. ]+)+|~[\\/][\w\-.]+(?:[\\/][\w\-. ]+)+"),
    ("container path", r"(?<![\w.])/(?:home|mnt)/[\w\-./]+"),
    ("money amount", r"(?:EUR|USD|GBP|PLN|HUF|NOK|£|€)\s?[\d][\d,. ]{2,}"),
    ("capacity figure", r"\d[\d,. ]*\s?(?:MW|kW|GW|MWh|kWh)\b"),
    ("a date that could pin a transaction",
     r"\b(?:[0-3]?\d\s+)?(?:January|February|March|April|May|June|July|August|September|"
     r"October|November|December)\s+(?:19|20)[0-4]\d\b|\b(?:19|20)5\d\b"),
]

# `committable` decides the exit code. `temp/` is gitignored scratch and the private folder
# never ships, so a hit there is information; a hit in `tools/` is a BLOCKER.
FOLDERS = [("tools/", ROOT / "tools", True),
           ("temp/", ROOT / "temp", False),
           ("private/tools/", PRIV / "tools", False)]

blocking = []
print("=" * 96)
print("SCRIPT COMMITTABILITY -- does this file hold one real string per pattern?")
print("=" * 96)
print(f"  {len(DESC)} descriptor + {len(NAMES)} name pattern(s) + {len(PROBES) - 2} shape probe(s)")

for label, folder, committable in FOLDERS:
    if not folder.exists():
        print(f"\n  {label:<18} does not exist")
        continue
    clean, dirty = [], []
    for p in sorted(folder.glob("*.py")):
        text = p.read_text(encoding="utf-8", errors="replace")
        hits = {}
        for lab, pat in PROBES:
            found = sorted({m.group(0)[:44] for m in re.finditer(pat, text)})
            if found:
                hits[lab] = found
        (dirty if hits else clean).append((p.name, hits))

    print()
    print("-" * 96)
    print(f"{label}   {len(clean)} clean  |  {len(dirty)} hold a real string"
          + ("   << THIS FOLDER IS COMMITTED" if committable else ""))
    print("-" * 96)
    for name, hits in dirty:
        cats = ", ".join(f"{lab} x{len(f)}" for lab, f in hits.items())
        print(f"  {'BLOCKER' if committable else 'blocked'}  {name:<38} {cats}")
        if SHOW:
            for lab, f in hits.items():
                print(f"               {lab}: {f[:6]}")
        if committable:
            blocking.append(f"{label}{name}")
    if committable and not dirty:
        print("  every script in this folder is clean on every probe")

print()
print("=" * 96)
print("STILL A HUMAN CALL, because no probe can see it")
print("=" * 96)
print("  * A script may be probe-clean and still unpublishable if what it REVEALS is the")
print("    control's own shape -- which of our checks accept what. Wouter ruled on the")
print("    confidentiality review script for that reason on 2026-08-06; it is clean on")
print("    every probe here and it does not ship. Read a script and ask what it reveals")
print("    about the control, not only what strings it holds.")
print("  * A script that reads its list from outside the repo is publishable even though")
print("    its OUTPUT is not. That is the leakage_scan.py pattern and it is the one to copy.")
print("=" * 96)
if blocking:
    print(f"RESULT: {len(blocking)} COMMITTABLE script(s) hold a real string -- fix before committing:")
    for b in blocking:
        print(f"    {b}")
    sys.exit(1)
print("RESULT: every script in a committed folder is clean.")
