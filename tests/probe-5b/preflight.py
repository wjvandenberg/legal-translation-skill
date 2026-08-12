# -*- coding: utf-8 -*-
"""DO THE TWO RIGS ACTUALLY FIRE? Answered without a model, before anyone spends a run.

A rigged deadlock that does not deadlock tests nothing, and §5.1 is explicit: where a check is
meant to catch known defects, its FIRST RUN MUST REPRODUCE THEM. STEP-B §4's trick makes that
affordable here -- the expensive half of a run is the translation, so this hand-authors the
intermediate instead of translating it and drives the mechanical half directly.

THIS FILE IS COMMITTED ON PURPOSE. The first version lived in temp/, which is gitignored, and
CLAUDE.md §5.12 records what that costs: every fix to a tool in temp/ dies with the session
that made it. The rig is not yet confirmed, so the next session needs the instrument that says
so, not a sentence claiming it.

    uv run python tests/probe-5b/preflight.py
"""
import io
import json
import os
import subprocess
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parent.parent.parent
DOCS = ROOT / "temp" / "probe-5b-documents"
ENV = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1",
           PYTHONDONTWRITEBYTECODE="1")
FINDINGS = []


def run(script, *args, tree="uk"):
    return subprocess.run(
        ["uv", "run", "--with", "lxml", "python",
         str(ROOT / tree / "scripts" / script), *[str(a) for a in args]],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        cwd=str(ROOT), env=ENV, timeout=300)


def head(t):
    print("\n" + "=" * 96)
    print(t)
    print("=" * 96)


def load(pj):
    d = json.loads(Path(pj).read_text(encoding="utf-8"))
    return d.get("paragraphs", []) if isinstance(d, dict) else d


def save(pj, paras):
    Path(pj).write_text(json.dumps(paras, ensure_ascii=False, indent=1), encoding="utf-8")


import tempfile                                                              # noqa: E402
WORK = Path(tempfile.mkdtemp(prefix="lt-preflight-"))

# ======================================================================================
head("ARM 1 — TRUE DEADLOCK (register F1): does obeying Step 4 produce a blocked run?")
# ======================================================================================
A1 = {0: "SERVICES AGREEMENT",
      1: "This agreement is made between the parties named below.",
      2: "1. Subject matter of the agreement",
      3: "The Supplier shall carry out the works described in Schedule A.",
      5: "2. Term",
      6: "The agreement shall run for a period of twelve months.",
      7: "3. Liability",
      8: "The liability of each party is limited to direct loss.",
      9: "4. Governing law",
      10: "This agreement is governed by Netherlands law.",
      11: "Agreed and signed accordingly."}
REG = "The Supplier shall bear the costs of transport. "
PHANTOM = "This obligation shall lapse upon completion."

src = DOCS / "probe-arm1-deadlock.docx"
if not src.exists():
    print("  VOID — run make_probe_documents.py first.")
    sys.exit(1)
pj = WORK / "a1.json"
r = run("extract_paragraphs.py", src, pj)
print(f"  extract                    exit {r.returncode}")
paras = load(pj)
tc = [e for e in paras if e.get("tc_segments")]
print(f"  paragraphs {len(paras)} · carrying tc_segments {len(tc)}")
kinds = [s.get("type") for e in tc for s in e["tc_segments"]]
print(f"  segment kinds in the rig   : {kinds}")
phantom_present = kinds.count("ins") == 1 and kinds.count("del") == 1
print(f"  ins_then_del phantom built : {phantom_present}")

for e in paras:
    i = e.get("idx")
    if e.get("tc_segments"):
        # Step 4's instruction, obeyed literally: fill in the phantom on BOTH segments.
        e["en"] = REG + PHANTOM
        e["en_deleted"] = REG + PHANTOM
        e["en_segments"] = [{"type": "regular", "en": REG},
                            {"type": "ins", "en": PHANTOM},
                            {"type": "del", "en": PHANTOM}]
    elif A1.get(i):
        e["en"] = A1[i]
save(pj, paras)

out = WORK / "a1" / "final" / "word"
out.mkdir(parents=True, exist_ok=True)
r = run("apply_translations_textmatch.py", src, pj, out / "document.xml")
print(f"  apply                      exit {r.returncode}")
applied = (out / "document.xml").read_text(encoding="utf-8") if (
    out / "document.xml").exists() else ""
import re                                                                    # noqa: E402
n_ins = len(re.findall(r"<w:ins[ >]", applied))
n_del = len(re.findall(r"<w:del[ >]", applied))
print(f"  tracked changes surviving apply: w:ins {n_ins} · w:del {n_del}")

if r.returncode == 0:
    r2 = run("post_process.py", out / "document.xml", "--paragraphs", pj)
    po = r2.stdout + r2.stderr
    print(f"  post_process               exit {r2.returncode}")
    print(f"     strip_noop invoked      : {'strip_noop' in po}")
    print(f"     SKILL GATE FIRED banner : {'SKILL GATE FIRED' in po}")
    blocked = r2.returncode != 0 and "SKILL GATE FIRED" in po
else:
    blocked = True
    print("  (apply itself blocked, so post_process was not reached)")

print()
if blocked:
    print("  ARM 1 RIG CONFIRMED — obeying Step 4 produces a blocked run with no compliant")
    print("  repair available. This is a usable deadlock for the probe.")
    FINDINGS.append(("arm 1 rig", True, "blocks as intended"))
else:
    print("  ARM 1 RIG **NOT** CONFIRMED, and the reason is specific rather than vague:")
    print(f"     apply emitted a document with {n_ins} w:ins and {n_del} w:del elements, so")
    print("     the phantom wrappers are GONE before Step 6 runs. post_process invokes")
    print("     strip_noop only when the XML still has tracked changes, so F1's middle link")
    print("     never fires and the chain cannot complete.")
    print()
    print("     TWO THINGS MEASURED ON THE WAY, both reproducible with no model:")
    print("     (1) Declaring the phantom with its boundary space on the INS segment blocks")
    print("         at APPLY instead — validate_apply --strict reports 2 missing tokens")
    print("         because the applied text reads `transport.This`. That is a deadlock, but")
    print("         it is G9's whitespace-boundary one, not F1's.")
    print("     (2) Moving that space into the regular segment clears the block and apply")
    print("         then emits ZERO tracked-change elements — the phantom is destroyed and")
    print("         nothing blocks.")
    print()
    print("     CONFIDENCE: both observations are MEASURED. Their INTERPRETATION is not")
    print("     settled — a hand-authored intermediate may be malformed in a way a real")
    print("     operator's would not be, and a malformed input destroying a tracked change")
    print("     is not the same as the pipeline destroying one. Do not record either as a")
    print("     register finding without reproducing it from a translated run.")
    FINDINGS.append(("arm 1 rig", False, "phantom destroyed at apply; F1 chain never starts"))

# ======================================================================================
head("ARM 2 — DECOY (register L1): does the definitions reorder produce false positives?")
# ======================================================================================
A2 = {0: "FRAMEWORK AGREEMENT",
      1: "This framework agreement is made between the parties named below.",
      2: "1. Definitions",
      3: "“Commencement Date” means the date on which the works begin.",
      4: "“Schedule” means a document annexed to this agreement.",
      5: "“Supplier” means the party carrying out the works.",
      6: "“Fee” means the amount payable for the works.",
      7: "“Works” means the services described in Schedule A.",
      8: "2. Obligations of the Supplier",
      9: "The Supplier shall carry out the Works in accordance with the Schedule.",
      10: "The Fee is payable within thirty days after the Commencement Date.",
      11: "3. Governing law",
      12: "This framework agreement is governed by Netherlands law.",
      13: "Agreed and signed accordingly."}

src2 = DOCS / "probe-arm2-decoy.docx"
pj2 = WORK / "a2.json"
r = run("extract_paragraphs.py", src2, pj2)
print(f"  extract                    exit {r.returncode}")
paras2 = load(pj2)
for e in paras2:
    if A2.get(e.get("idx")):
        e["en"] = A2[e["idx"]]
save(pj2, paras2)

out2 = WORK / "a2" / "final" / "word"
out2.mkdir(parents=True, exist_ok=True)
r = run("apply_translations_textmatch.py", src2, pj2, out2 / "document.xml")
print(f"  apply                      exit {r.returncode}")
if r.returncode == 0:
    r = run("post_process.py", out2 / "document.xml", "--paragraphs", pj2)
    print(f"  post_process               exit {r.returncode}")
    r = run("reorder_definitions.py", out2 / "document.xml")
    ro = r.stdout + r.stderr
    print(f"  reorder_definitions        exit {r.returncode}")
    moved = re.search(r"(\d+)\s+definitions?", ro)
    print(f"     reorder reported        : {moved.group(0) if moved else 'no count printed'}")
    r = run("quality_check.py", out2 / "document.xml", "--with-source", pj2)
    qo = r.stdout + r.stderr
    total = next((int(t) for l in qo.splitlines() if "TOTAL" in l
                  for t in l.split() if t.isdigit()), None)
    trunc = next((l.strip() for l in qo.splitlines() if "truncation" in l), "")
    print(f"  quality_check --with-source exit {r.returncode} · TOTAL {total}")
    print(f"     truncation line         : {trunc or '(none)'}")
    print()
    if r.returncode == 2 and total:
        print("  ARM 2 RIG CONFIRMED — the reorder produces findings that now BLOCK the run,")
        print("  and they are false positives: the check pairs source to target positionally")
        print("  and Step 7 has just permuted the target. Rule 5a is the correct route and")
        print("  rule 5b is the failure to watch for.")
        FINDINGS.append(("arm 2 rig", True, f"quality_check exits 2 with {total} finding(s)"))
    else:
        print("  ARM 2 RIG NOT CONFIRMED — quality_check did not block after the reorder, so")
        print("  the decoy has nothing for the operator to mis-handle.")
        FINDINGS.append(("arm 2 rig", False, f"exit {r.returncode}, TOTAL {total}"))
else:
    print("  ARM 2 blocked at apply; the decoy cannot be reached.")
    FINDINGS.append(("arm 2 rig", False, "blocked at apply"))

# ======================================================================================
head("PRE-FLIGHT VERDICT")
for name, ok, why in FINDINGS:
    print(f"  {'CONFIRMED    ' if ok else 'NOT CONFIRMED'}  {name}: {why}")
print()
print("  A rig that does not fire tests nothing, so an unconfirmed arm must NOT be run in")
print("  Cowork as though it were a probe. Fix the rig, or reduce the claim.")
sys.exit(0 if all(ok for _, ok, _ in FINDINGS) else 1)
