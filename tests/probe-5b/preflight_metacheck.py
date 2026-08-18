# -*- coding: utf-8 -*-
"""CAN THE PRE-FLIGHT STILL SAY NO? Three mutations, each breaking a different link of F1's
chain, each of which must turn ARM 1 RIG CONFIRMED back into NOT CONFIRMED.

WHY THIS EXISTS. `preflight.py` now reports arm 1 CONFIRMED, and that is the answer the
session wanted — which is exactly when this project's own record says to stop trusting it.
The first version of the pre-flight printed `ins_then_del phantom built : True` over a
document containing no phantom at all, because it asked for one `ins` plus one `del` instead
of asking for the segment type: an arithmetic that a pair of ordinary siblings satisfies. A
positive result from a check that cannot produce a negative one is not evidence.

So each mutation below attacks a claim rather than the code that reports it:

  A  THE NESTING IS LOAD-BEARING. Rebuild the phantom as two siblings — the shape the rig
     carried until 2026-08-18 — and the run must go quiet. If it does not, `ins_then_del` was
     never what made the chain run.
  B  OBEYING STEP 4 IS WHAT CAUSES THE DEADLOCK. Declare the phantom segment empty, which is
     both F1's proposed fix and a disobedience of Step 4's "always fill these in", and the
     gate must stop firing. This is the mutation that turns the rig from "a run that blocks"
     into "a run that blocks BECAUSE the manual was followed" — the whole claim of arm 1.
  C  THE MARKER WORDS MUST BE UNIQUE TO THE PHANTOM. Give the phantom an English rendering
     built only from words the regular half already contains. validate_apply compares token
     SETS, so every declared token survives the deletion, and the rig goes silent while
     looking healthy. That is the failure this rig is one careless edit away from.

Each mutation is applied to the file's BYTES and restored from the bytes read before it, then
the restoration is asserted byte-for-byte. `.gitattributes` forbids translating line endings
and `Path.write_text` does exactly that on this platform, which is why nothing here goes near
it.

AND NO MUTATION HARD-CODES A LINE ENDING, because this directory does not have one. Measured
2026-08-18 against the committed blobs: `preflight.py` is CRLF, while `make_probe_documents.py`
and `SCORING.md` are LF. A multi-line needle written with `\\r\\n` therefore matches one file
here and silently misses the other — which it did, and the run reported VOID rather than a
pass because that distinction is built in. Every needle below is a list of LINES, joined with
whatever ending the target file itself uses.

    uv run python tests/probe-5b/preflight_metacheck.py
"""
import os
import subprocess
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
PREFLIGHT = HERE / "preflight.py"
MAKER = HERE / "make_probe_documents.py"
ENV = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1",
           PYTHONDONTWRITEBYTECODE="1")


def ending(path):
    """The file's OWN line ending, not this machine's. See the docstring."""
    b = path.read_bytes()
    return b"\r\n" if b.count(b"\r\n") > (b.count(b"\n") - b.count(b"\r\n")) else b"\n"


def needle(path, *lines):
    """Join source lines with the target file's own ending, and terminate the last one."""
    eol = ending(path)
    return eol.join(l.encode("utf-8") for l in lines) + eol


SIBLING_PHANTOM = (
    """        '<w:p><w:r><w:t xml:space="preserve">De Leverancier draagt de kosten van '""",
    """        'vervoer.</w:t></w:r>'""",
    """        '<w:ins w:id="101" w:author="Reviewer" w:date="2020-01-01T00:00:00Z">'""",
    """        '<w:r><w:t xml:space="preserve"> Deze verplichting vervalt na oplevering.'""",
    """        '</w:t></w:r></w:ins>'""",
    """        '<w:del w:id="102" w:author="Reviewer" w:date="2020-01-01T00:00:00Z">'""",
    """        '<w:r><w:delText xml:space="preserve"> Deze verplichting vervalt na oplevering.'""",
    """        '</w:delText></w:r></w:del>'""",
)
NESTED_PHANTOM = (
    """        '<w:p><w:r><w:t xml:space="preserve">De Leverancier draagt de kosten van '""",
    """        'vervoer. </w:t></w:r>'""",
    """        '<w:ins w:id="101" w:author="Reviewer" w:date="2020-01-01T00:00:00Z">'""",
    """        '<w:del w:id="102" w:author="Controller" w:date="2020-01-02T00:00:00Z">'""",
    """        '<w:r><w:delText xml:space="preserve">Deze verplichting vervalt na '""",
    """        'oplevering.</w:delText></w:r>'""",
    """        '</w:del></w:ins>'""",
)

MUTATIONS = [
    ("A  nesting is load-bearing — rebuild the phantom as two siblings",
     MAKER,
     needle(MAKER, *NESTED_PHANTOM),
     needle(MAKER, *SIBLING_PHANTOM)),
    ("B  obeying Step 4 is the cause — declare the phantom segment empty",
     PREFLIGHT,
     needle(PREFLIGHT, '{"type": "ins_then_del", "en": PHANTOM}]'),
     needle(PREFLIGHT, '{"type": "ins_then_del", "en": ""}]')),
    ("C  the marker words must be unique — reuse the regular half's vocabulary",
     PREFLIGHT,
     needle(PREFLIGHT, 'PHANTOM = "This obligation shall lapse upon handover."'),
     needle(PREFLIGHT, 'PHANTOM = "The Supplier shall bear the costs."')),
]


def build_documents():
    return subprocess.run(
        ["uv", "run", "python", str(MAKER)],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        cwd=str(ROOT), env=ENV, timeout=300)


def run_preflight():
    r = subprocess.run(
        ["uv", "run", "python", str(PREFLIGHT)],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        cwd=str(ROOT), env=ENV, timeout=900)
    return r.returncode, r.stdout + r.stderr


print("=" * 96)
print("BASELINE — the unmutated rig must report ARM 1 RIG CONFIRMED")
print("=" * 96)
build_documents()
rc, out = run_preflight()
baseline_ok = rc == 0 and "ARM 1 RIG CONFIRMED" in out
print(f"  exit {rc} · ARM 1 RIG CONFIRMED present: {'ARM 1 RIG CONFIRMED' in out}")
if not baseline_ok:
    print("  VOID — the baseline does not pass, so a mutation proving it can fail would")
    print("  establish nothing. Fix the rig before running this.")
    sys.exit(1)

results = []
for label, target, original, replacement in MUTATIONS:
    print("\n" + "=" * 96)
    print(f"MUTATION {label}")
    print("=" * 96)
    before = target.read_bytes()
    if original not in before:
        print(f"  VOID — the text this mutation patches is not in {target.name}. The file has")
        print("  moved on and this mutation is asserting nothing. FIX THE MUTATION, and do")
        print("  not read this as a pass.")
        results.append((label, None))
        continue
    try:
        target.write_bytes(before.replace(original, replacement, 1))
        build_documents()
        rc, out = run_preflight()
        detected = rc != 0 and "ARM 1 RIG **NOT** CONFIRMED" in out
        print(f"  exit {rc} · detected as NOT CONFIRMED: {detected}")
        for line in out.splitlines():
            if line.strip().startswith(("phantom built", "wrappers survived",
                                        "strip_noop removed", "post_process raised",
                                        "and it blocked")):
                print(f"    {line.strip()}")
        results.append((label, detected))
    finally:
        target.write_bytes(before)
        assert target.read_bytes() == before, f"RESTORATION FAILED for {target}"

build_documents()          # leave the correct documents on disk

print("\n" + "=" * 96)
print("METACHECK VERDICT")
print("=" * 96)
for label, detected in results:
    mark = "DETECTED    " if detected else ("VOID        " if detected is None
                                            else "MISSED      ")
    print(f"  {mark}{label}")
print()
n_ok = sum(1 for _, d in results if d)
print(f"  {n_ok} of {len(results)} mutations detected. A MISSED mutation means the pre-flight")
print("  reports CONFIRMED on a rig that does not test F1; a VOID means this metacheck has")
print("  gone stale and is asserting nothing, which is not a pass either.")
print()
print("  Both source files restored byte-for-byte, asserted rather than assumed.")
sys.exit(0 if all(d for _, d in results) else 1)
