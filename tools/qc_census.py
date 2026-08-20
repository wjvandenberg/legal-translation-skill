# -*- coding: utf-8 -*-
"""THE quality_check FALSE-POSITIVE CENSUS over the recorded corpus.

THE QUESTION. Branch 5 gives `quality_check` an exit code, so from branch 5 onward a finding STOPS
the run. Nobody has measured how often those findings are false positives, which is the number
that decides whether branch 5 is safe to merge ahead of branch 14. CLAUDE.md publishes that 6 of
12 runs saw a non-zero total and that at least 19 of D06's 32 are documented false positives; the
rate has never been derived.

RE-MEASURED, NOT READ. The findings are recreated by running `quality_check` against each recorded
deliverable, not lifted from the narrative logs -- CLAUDE.md 5.12 rule 1, and 5.6's warning that
the narratives under-report counts (14/12/11 against a real 18/16/11).

HOW L1's SHARE IS ESTABLISHED WITHOUT JUDGEMENT, and this is the heart of it. `check_truncation`
method A does `p = all_p[idx]` -- it indexes the DOCUMENT by the JSON's idx (quality_check.py:494).
Step 7 permutes the document first. So for every entry that yields a finding, ask a question that
needs no human: DOES all_p[idx] ACTUALLY HOLD THE ENGLISH THIS ENTRY DECLARED? If it does not, the
rule compared two unrelated paragraphs and the finding is a positional artefact BY CONSTRUCTION.
No patch, no re-run, no reading of any finding's text.

OUTPUT POLICY. Prints rule-class names, counts, and corpus doc-ids. NEVER a finding's text, a
paragraph's text, a filename or a path -- every finding string embeds 50-70 characters of the
client document, which is exactly what CLAUDE.md 6.5 says cannot be un-said once it reaches a
transcript. There is no verbose flag.

Location from LEGAL_TRANSLATION_LOGS, so nothing about this machine is baked in.
"""
import json
import os
import re
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parent.parent
LOGS = Path(os.environ.get("LEGAL_TRANSLATION_LOGS",
                           str(ROOT.parent / "legal-translation-logs")))
ENV = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1",
           PYTHONDONTWRITEBYTECODE="1")
W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
DOC_ID = re.compile(r"\b(D0[1-9]|D1[01])(B?)\b")

if not LOGS.is_dir():
    print("VOID — logs folder unreachable. Nothing measured, so nothing passed.")
    sys.exit(1)


def docid(p):
    m = DOC_ID.search(str(p))
    return (m.group(1) + m.group(2)) if m else "unattributed"


def load_entries(pj):
    d = json.loads(pj.read_text(encoding="utf-8", errors="replace"))
    return d.get("paragraphs", []) if isinstance(d, dict) else d


def para_texts(xml_path):
    """Every w:p's concatenated w:t text, in the SAME ORDER quality_check sees.

    PARSED WITH lxml, NOT REGEX, and the first version's regex was wrong in a way that
    invalidated every index-based comparison downstream. `<w:p(?:\\s[^>]*)?>...</w:p>` cannot
    match a SELF-CLOSING `<w:p/>`, which Word emits for an empty paragraph — so every index
    after the first empty paragraph was off by one, and the census claimed 13 method-A
    candidates on two documents where quality_check itself reported zero. That disagreement is
    what exposed it. `check_truncation` does `list(root.iter(w:p))`, so this does exactly the
    same thing and inherits its ordering rather than reimplementing it. CLAUDE.md 5.10's rule
    — prefer lxml for structural work — applies to our instruments too, not only to the skill.
    """
    from lxml import etree
    root = etree.parse(str(xml_path)).getroot()
    return ["".join(t.text or "" for t in p.iter(f"{{{W}}}t"))
            for p in root.iter(f"{{{W}}}p")]


def norm(s):
    return re.sub(r"\s+", " ", (s or "")).strip().lower()


workdirs = []
for pj in sorted(LOGS.rglob("paragraphs.json")):
    dx = pj.parent / "final" / "word" / "document.xml"
    if dx.is_file():
        workdirs.append((pj, dx))
if not workdirs:
    print("VOID — no workdir holds both artefacts. Not a clean result.")
    sys.exit(1)

print(f"  {len(workdirs)} recorded workdir(s), {len({docid(p) for p, _ in workdirs})} doc-id(s)\n")

CLASS_RE = re.compile(r"^\s{2}([a-z_]+)\s{2,}(CLEAN|\d+)", re.M)
TOTAL_RE = re.compile(r"^\s{2}TOTAL\s+(\d+)", re.M)

rows, class_totals, l1_split = [], Counter(), Counter()
# THE FIRST VERSION OF THIS CENSUS PASSED NEITHER FLAG, AND THAT WAS A DEFECT IN THE
# INSTRUMENT RATHER THAN A FINDING ABOUT THE SKILL. `--variant` defaults to 'uk', and the
# corpus is 3 US / 8 UK — D04, D05, D07 — so the spelling check ran BACKWARDS on exactly
# those three, flagging US spellings as violations in documents that are meant to be US
# English. They were also the three non-zero runs, so the headline number was mostly my own
# invocation. `--language` is passed for the same reason: omitting it leaves C9's unreliable
# auto-detection to guess, and a language-dependent check does not degrade to nothing, it
# degrades to a confident wrong answer (CLAUDE.md 5.9).
VARIANT = {"D04": "us", "D05": "us", "D07": "us"}          # 5.7: the rest are UK
LANGUAGE = {"D01": "hungarian", "D02": "dutch", "D03": "norwegian", "D03B": "norwegian",
            "D04": "spanish", "D05": "italian", "D06": "italian", "D07": "english",
            "D08": "finnish", "D09": "hungarian", "D10": "polish", "D11": "japanese"}

for pj, dx in workdirs:
    d = docid(pj)
    # --verbose IS REQUIRED, and its absence made the first correlation report 0 of 0.
    # Without it quality_check prints only the per-class summary, so the census parsed finding
    # lines out of output that never contained any and printed "0 (0%)" — a check reporting on
    # an empty set, which CLAUDE.md 5.1 says must read VOID and never a number. The assertion
    # below is the fix for the class of error, not just this instance.
    args = ["--with-source", str(pj), "--variant", VARIANT.get(d, "uk"), "--verbose"]
    if d in LANGUAGE:
        args += ["--language", LANGUAGE[d]]
    r = subprocess.run(
        ["uv", "run", "--with", "lxml", "python",
         str(ROOT / "uk" / "scripts" / "quality_check.py"), str(dx), *args],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        cwd=str(ROOT), env=ENV, timeout=600)
    out = r.stdout + r.stderr
    total = int(TOTAL_RE.search(out).group(1)) if TOTAL_RE.search(out) else None
    classes = {k: (0 if v == "CLEAN" else int(v)) for k, v in CLASS_RE.findall(out)}
    for k, v in classes.items():
        class_totals[k] += v

    # L1's share, mechanically: of the entries the truncation rule could fire on, how many
    # have all_p[idx] holding text that is NOT the English this entry declared?
    entries, texts = load_entries(pj), para_texts(dx)
    eligible, mispaired_idx = 0, set()
    # Method A recomputed from quality_check.py:487-505's own conditions, so the DISPLAY CAP
    # cannot limit the measurement. Line 893 prints only `issues[:5]` per class even under
    # --verbose, so parsing the output measured a capped sample and would have understated
    # D06 by six. Recomputing asks the same question a second way, which CLAUDE.md 5.1
    # prescribes for exactly this reason.
    a_candidates, a_on_mispaired = 0, 0
    for e in entries:
        idx, src, en = e.get("idx", -1), e.get("text") or "", e.get("en") or ""
        if not src.strip() or len(src) < 20 or idx < 0 or idx >= len(texts):
            continue
        eligible += 1
        wrong_pair = bool(en.strip()) and norm(texts[idx]) != norm(en)
        if wrong_pair:
            mispaired_idx.add(idx)
        doc_en = texts[idx]
        if not doc_en.strip():
            if len(src.strip()) > 30:                     # the EMPTY-translation branch, :499
                a_candidates += 1
                a_on_mispaired += 1 if wrong_pair else 0
            continue
        if len(src) > 50 and (len(doc_en) / len(src)) < 0.4:   # the ratio branch, :504
            a_candidates += 1
            a_on_mispaired += 1 if wrong_pair else 0

    # AND CORRELATE, because the mispairing RATE is not the finding count. Each truncation
    # finding carries `idx=N` in its own text; parsing the number tells us which entry it fired
    # on WITHOUT printing the surrounding client text. A finding on a mispaired entry compared
    # two unrelated paragraphs, so it is L1's artefact by construction.
    fired_idx = [int(m) for m in re.findall(r"\(idx=(\d+)\)", out)]
    # VOID, NOT ZERO. If the class summary says the truncation rule found something but no
    # finding line was parsed, the parse is broken and the correlation below is meaningless.
    # Method B's own message is "Dangling ending '...' in '...'" (quality_check.py:535) — read
    # from the source rather than guessed, after the first assertion fired on D07 because I had
    # guessed "ends with".
    n_dangling = len(re.findall(r"Dangling ending", out))
    if classes.get("truncation", 0) and not fired_idx and not n_dangling:
        print(f"  VOID — {docid(pj)}: truncation class reports "
              f"{classes['truncation']} but no finding line parsed. The parse is wrong; "
              f"fix it rather than reading the 0.")
        sys.exit(1)
    l1_findings = sum(1 for i in fired_idx if i in mispaired_idx)
    l1_split[docid(pj)] += l1_findings
    rows.append((docid(pj), r.returncode, total, eligible, len(mispaired_idx),
                 classes.get("truncation", 0), a_candidates, a_on_mispaired, n_dangling,
                 len(fired_idx), l1_findings))

print(f"  {'doc':8s} {'rc':>3s} {'TOTAL':>6s} {'mispaired':>10s} {'trunc-cls':>10s} "
      f"{'A total':>8s} {'A mispaired':>12s} {'B printed':>10s}")
stops = 0
for d, rc, total, elig, mis, trunc, acand, amis, dang, fired, l1 in rows:
    if total:
        stops += 1
    print(f"  {d:8s} {rc:>3d} {('-' if total is None else total):>6} "
          f"{mis:>10d} {trunc:>10d} {acand:>8d} {amis:>12d} {dang:>10d}")

n_fired = sum(r[6] for r in rows)
n_l1 = sum(r[7] for r in rows)
n_dang_all = sum(r[8] for r in rows)
n_printed = sum(r[9] for r in rows)
print(f"\n  DELIVERABLES THAT WOULD STILL BE BLOCKED AT STEP 9: {stops} of {len(rows)} workdir(s)")
print(f"  distinct doc-ids blocked                          : "
      f"{len({r[0] for r in rows if r[2]})} of {len({r[0] for r in rows})}")
print(f"  entries whose all_p[idx] holds the WRONG English   : {sum(r[4] for r in rows)}")
print(f"  method A findings, recomputed past the display cap : {n_fired}")
print(f"  of those, ON A MISPAIRED ENTRY = L1 artefact       : {n_l1}"
      f"  ({'n/a' if not n_fired else str(round(100 * n_l1 / n_fired)) + '%'})")
print(f"  method B (dangling endings) findings PRINTED       : {n_dang_all}"
      f"   — capped at 5 per class by quality_check.py:893")
print(f"  cross-check, finding lines parsed from output      : {n_printed}"
      f"   (capped; the recomputation above is the measurement)")

print("\n  FINDINGS BY RULE CLASS, all workdirs")
for k, v in sorted(class_totals.items(), key=lambda kv: -kv[1]):
    if v:
        print(f"    {k:32s} {v:>5d}")

print("\n  WHAT IS AND IS NOT ESTABLISHED")
print("    MISPAIRED is measured and needs no judgement: all_p[idx] does not hold the English")
print("    that entry declared, so the truncation rule compared unrelated paragraphs. Every")
print("    finding it produced on such an entry is L1's positional artefact by construction.")
print("    The other rule classes are COUNTS ONLY. Classifying an individual finding true or")
print("    false needs its text read, and each finding embeds client document text — so that")
print("    residue is for Wouter or a sanitised route, NOT for this script to guess.")
sys.exit(0)
