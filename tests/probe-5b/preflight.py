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
# The content words here are chosen to appear nowhere else IN THIS PARAGRAPH, which is the
# scope that matters: validate_apply compares token SETS per paragraph, so a phantom word that
# also occurs in the paragraph's surviving text would still be "present" after the phantom is
# deleted, and the gate would go quiet — the rig would then read NOT CONFIRMED for a reason
# with nothing to do with F1. Asserted below rather than trusted; this is the two-word-needle
# failure class and an assertion is the only defence against it.
#
# PER-PARAGRAPH, NOT PER-DOCUMENT, AND THE DIFFERENCE BIT ONCE ALREADY. "this" occurs in three
# other paragraphs, so a document-wide "are the phantom's words gone?" probe reports True for
# a reason that has nothing to do with this paragraph. The first version of the line below did
# exactly that and printed a reassuring True over a correctly-emptied paragraph.
PHANTOM = "This obligation shall lapse upon handover."

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

# ASK FOR THE SEGMENT TYPE THE RIG IS NAMED AFTER, NOT FOR TWO COUNTS THAT RESEMBLE IT.
# The first version of this line read `kinds.count("ins") == 1 and kinds.count("del") == 1`
# and printed True over a document containing NO phantom at all: two sibling wrappers give
# one `ins` and one `del`, which satisfies that arithmetic exactly. The phantom is a single
# element with its own type, so that is what gets asserted.
phantom_present = kinds.count("ins_then_del") == 1
print(f"  ins_then_del phantom built : {phantom_present}")
if not phantom_present:
    print("     The document does not carry the shape this arm exists to test. Sibling")
    print("     w:ins + w:del is NOT a phantom — see make_probe_documents.tc_paragraph.")

for e in paras:
    i = e.get("idx")
    if e.get("tc_segments"):
        # Step 4's instruction, obeyed literally: "Always fill these in; leaving the source
        # language there is the single most common silent remnant in tracked-change
        # documents" (04-translate.md:488). The phantom renders empty in BOTH the accept-all
        # and the reject-all view, so `en` and `en_deleted` carry the regular text only —
        # which is what makes the deletion invisible to every check except the token diff.
        e["en"] = REG
        e["en_deleted"] = REG
        e["en_segments"] = [{"type": "regular", "en": REG},
                            {"type": "ins_then_del", "en": PHANTOM}]
    elif A1.get(i):
        e["en"] = A1[i]
save(pj, paras)

import re                                                                    # noqa: E402
# Which of the phantom's words could only be there because the phantom is? Same tokeniser
# rule as validate_apply: 3+ characters, case-folded, trailing punctuation stripped.
_tok = re.compile(r"[A-Za-z0-9][A-Za-z0-9.\-]*[A-Za-z0-9]|[A-Za-z0-9]+")


def toks(text):
    return {t.strip(".,;:!?()[]{}'\"-").lower()
            for t in _tok.findall(text or "")
            if len(t.strip(".,;:!?()[]{}'\"-")) >= 3}


def phantom_paragraph(xml):
    """The rigged paragraph, found by a word from its REGULAR half — the half that survives.

    Named by a phrase rather than by an index because the reorder and the tidy-up passes are
    free to move paragraphs, and an index that silently points at the wrong paragraph is how
    an instrument comes to report on an empty set.
    """
    for m in re.finditer(r"<w:p[ >].*?</w:p>", xml, re.DOTALL):
        if "costs of transport" in m.group(0):
            return m.group(0)
    return ""


marker_toks = toks(PHANTOM) - toks(REG)
print(f"  phantom-only tokens        : {sorted(marker_toks)}")

out = WORK / "a1" / "final" / "word"
out.mkdir(parents=True, exist_ok=True)
r = run("apply_translations_textmatch.py", src, pj, out / "document.xml")
print(f"  apply                      exit {r.returncode}")
applied = (out / "document.xml").read_text(encoding="utf-8") if (
    out / "document.xml").exists() else ""
n_ins = len(re.findall(r"<w:ins[ >]", applied))
n_del = len(re.findall(r"<w:del[ >]", applied))
print(f"  tracked changes surviving apply: w:ins {n_ins} · w:del {n_del}")

# The apply-time gate must PASS. F1's whole shape is that the run looks clean at Step 5 and
# blocks at the end of Step 6, so an arm that blocked at apply would be a different finding.
stripped = gate = tokens_are_phantom = False
po = ""
if r.returncode == 0:
    r2 = run("post_process.py", out / "document.xml", "--paragraphs", pj)
    po = r2.stdout + r2.stderr
    print(f"  post_process               exit {r2.returncode}")
    m = re.search(r"(\d+)\s+phantom ins-wraps-del wrapper", po)
    stripped = bool(m) and int(m.group(1)) >= 1
    gate = r2.returncode != 0 and "SKILL GATE FIRED" in po
    missing = set()
    for line in po.splitlines():
        mm = re.search(r"missing=\[(.*?)\]", line)
        if mm:
            missing |= {t.strip().strip("'\"").lower() for t in mm.group(1).split(",")}
    tokens_are_phantom = bool(marker_toks) and marker_toks <= missing
    print(f"     strip_noop invoked      : {'strip_noop' in po}")
    print(f"     phantom wrappers stripped: {m.group(1) if m else 'not reported'}")
    print(f"     SKILL GATE FIRED banner : {gate}")
    print(f"     tokens reported missing : {sorted(missing) or '(none)'}")
    print(f"     the missing tokens ARE the phantom's: {tokens_are_phantom}")
    # Scoped to the rigged PARAGRAPH, because that is the scope validate_apply compares at.
    before = phantom_paragraph(applied).lower()
    after = phantom_paragraph(
        (out / "document.xml").read_text(encoding="utf-8")).lower()
    if not before or not after:
        print("     VOID — could not locate the rigged paragraph; read nothing, so assert"
              " nothing.")
    print(f"     phantom words in that paragraph: "
          f"after strip {sorted(t for t in marker_toks if t in after) or '(none)'} · "
          f"before strip {sorted(t for t in marker_toks if t in before) or '(none)'}")
else:
    print("  (apply itself blocked, so post_process was not reached — and an apply-time")
    print("   block is NOT F1: F1 passes Step 5 and fails at the end of Step 6.)")

print()
# CONFIRMED means all four links of F1's chain ran, in order, and nothing else did the
# blocking. "It blocked" on its own is not enough — a rig that deadlocks for another
# finding's reason measures that finding.
if phantom_present and n_ins == 1 and stripped and gate and tokens_are_phantom:
    print("  ARM 1 RIG CONFIRMED — and confirmed as F1's chain rather than merely as a block:")
    print("     Step 4 obeyed  -> the phantom's English is declared, as the step doc requires")
    print("     Step 5 apply   -> exit 0, wrappers intact, the apply-time gate PASSES")
    print("     Step 6 strip   -> strip_noop removes the phantom wrapper, as designed")
    print("     Step 6 gate    -> validate_apply --strict finds the declared English gone")
    print("                       and post_process raises SKILL GATE FIRED")
    print()
    print("  AND THERE IS NO COMPLIANT REPAIR, which is what makes it a deadlock rather than")
    print("  an error. Step 4 forbids leaving the segment unfilled. strip_noop's")
    print("  --keep-phantom-tcs flag is UNREACHABLE: post_process invokes the script with the")
    print("  xml path and nothing else, so using it means wrapping or patching a script, and")
    print("  anti-drift rule 5 forbids both. Editing paragraphs.json to drop the declared")
    print("  English is the repair the gate's own message names as the WRONG one. Rule 5b is")
    print("  the only sanctioned end.")
    FINDINGS.append(("arm 1 rig", True, "F1's chain runs end to end and blocks at Step 6"))
else:
    print("  ARM 1 RIG **NOT** CONFIRMED. Which link failed, so the next session starts from")
    print("  a fact rather than from a re-derivation:")
    print(f"     phantom built (ins_then_del segment)     : {phantom_present}")
    print(f"     wrappers survived apply (expect w:ins 1) : {n_ins}")
    print(f"     strip_noop removed the phantom wrapper   : {stripped}")
    print(f"     post_process raised SKILL GATE FIRED     : {gate}")
    print(f"     and it blocked on the PHANTOM's tokens   : {tokens_are_phantom}")
    print()
    print("     The last line is the one to read twice. A block on other tokens is a")
    print("     different deadlock — G9's boundary-whitespace one is the near neighbour —")
    print("     and a rig that fires for the wrong reason is worse than one that does not")
    print("     fire, because its result looks like an answer.")
    FINDINGS.append(("arm 1 rig", False, "F1's chain did not complete; see the link table"))

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

DEFS = (3, 4, 5, 6, 7)          # the five definition paragraphs


def def_runs(en):
    """en_runs for one definition paragraph: the quoted defined term bold-italic, rest plain.

    Authored because `validate_en_runs.py` BLOCKS apply on any detected definitions section
    whose paragraphs carry no `en_runs` — it exists to stop the bold-off override from
    stripping the style-provided emphasis that marks a defined term. A real operator writes
    these; the first version of this pre-flight did not, so arm 2 stopped at Step 5 and the
    reported cause ("blocks at apply") named the symptom rather than the gate.
    """
    close = en.index("”") + 1
    return [{"start": 0, "end": close, "bold": True, "italic": True},
            {"start": close, "end": len(en), "bold": False, "italic": False}]


src2 = DOCS / "probe-arm2-decoy.docx"
pj2 = WORK / "a2.json"
r = run("extract_paragraphs.py", src2, pj2)
print(f"  extract                    exit {r.returncode}")
paras2 = load(pj2)
for e in paras2:
    i = e.get("idx")
    if A2.get(i):
        e["en"] = A2[i]
        if i in DEFS:
            e["en_runs"] = def_runs(A2[i])
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
        print("  the decoy has nothing for the operator to mis-handle. TWO MEASURED CAUSES,")
        print("  both reproducible with no model, so the next session starts from facts:")
        print()
        print("  (1) THE PERMUTATION IS TOO SMALL. reorder_definitions read the block as")
        print("      'Commencement Date', 'Schedule', 'Supplier', 'Fee', 'Works' and sorted it")
        print("      to Commencement Date, Fee, Schedule, Supplier, Works — so only 'Fee'")
        print("      actually moved. L1 fires positionally, so one displaced pair is the")
        print("      minimum possible disturbance rather than a representative one.")
        print("  (2) L1 IS SILENT UNLESS THE MISPAIRED DEFINITIONS DIFFER SHARPLY IN LENGTH.")
        print("      The register says so in as many words, and the corpus instance surfaced")
        print("      as 11 bogus TRUNCATION findings — a length-ratio rule. This decoy's five")
        print("      definitions are all about one line long, so nothing mispairs far enough")
        print("      to trip it.")
        print()
        print("  AND ONE BEHAVIOUR WORTH A LOOK BEFORE THE DOCUMENT IS REDESIGNED: the")
        print("  detector reported \"'Works' (7 paras) [7,8,9,10,11,12,13]\" — it absorbed the")
        print("  whole remainder of the document into the last definition, because nothing")
        print("  after the block ends it. Whether that is a rig defect or a register finding")
        print("  is UNDECIDED here and must not be assumed either way.")
        print()
        print("  SO THE ROUTE IS: definitions whose English renderings differ sharply in")
        print("  length AND whose alphabetical order differs sharply from the source's, with")
        print("  a clear terminator after the block. That is a document change, not a")
        print("  pre-flight change, and it was deliberately NOT made in the session that")
        print("  fixed arm 1 — see SCORING.md.")
        FINDINGS.append(("arm 2 rig", False,
                         f"reorder ran but quality_check exit {r.returncode}, TOTAL {total}"))
else:
    print("  ARM 2 blocked at apply; the decoy cannot be reached.")
    print("  Read the gate's own banner above — it names which validator refused and why.")
    FINDINGS.append(("arm 2 rig", False, "blocked at apply"))

# ======================================================================================
head("PRE-FLIGHT VERDICT")
for name, ok, why in FINDINGS:
    print(f"  {'CONFIRMED    ' if ok else 'NOT CONFIRMED'}  {name}: {why}")
print()
print("  A rig that does not fire tests nothing, so an unconfirmed arm must NOT be run in")
print("  Cowork as though it were a probe. Fix the rig, or reduce the claim.")
print()
# WHAT THE EXIT CODE MEANS, STATED RATHER THAN INFERRED FROM THE SOURCE.
# The protocol runs arm 1 first and says a failure there answers the gate on its own
# (SCORING.md, "Read it in the failure direction"), so the exit code tracks the arm that will
# actually be run next. It is NOT an all-arms pass, and saying so is the point: an exit code
# whose meaning has to be reverse-engineered is how a check comes to pass for the wrong
# reason. Arm 2's verdict is printed above and is NOT covered by this code.
arm1_ok = next((ok for name, ok, _ in FINDINGS if name == "arm 1 rig"), False)
print("  EXIT CODE CONTRACT: 0 means ARM 1 — the arm the protocol runs first — is confirmed.")
print("  It says NOTHING about arm 2, whose verdict is printed above and which must not be")
print("  run in Cowork while it reads NOT CONFIRMED.")
sys.exit(0 if arm1_ok else 1)
