# -*- coding: utf-8 -*-
"""DID THE CHARTER REDUCTION LOSE ANYTHING, AND DOES THE CHARTER STILL STATE ITS OWN SIZE TRUTHFULLY?

CHECKER VERSION 1 (2026-08-24)

WHY THIS IS IN `tools/` AND NOT IN `temp/`. It began as `temp/verify_3a_continuity.py`, written for one
phase of the charter reduction. Section 1.7 of CLAUDE.md declares the charter's own line count in prose,
and **that figure went stale five times in one day, twice inside a single step.** `verify_md.py` cannot
catch it: it measures the file and reports the cap, but the declaration is a sentence, and no checker
compares a sentence to a measurement. So the one control that catches it ran only when somebody
remembered -- which is the wrong kind of control, and it is why this is promoted rather than rewritten
again next session.

THE SIX CHECKS, and each exists because the failure it names has actually happened here:

  0  THE BASELINE IS REAL             a before/after comparison pinned to a branch name compares the
                                      fixed content with itself and reports 100% carried (5.16 rule 4)
  1  THE MUST-NOT LIST                a section owned by another phase must be BYTE-unchanged SINCE
                                      THIS PHASE'S ENTRY -- see the two-baseline note below
  2  NO HEADING LOST, NO RENUMBER     headings are what every pointer resolves against
  3  THE DECLARED SIZE                every sentence in which the charter states its own length must
                                      equal the measured length. THIS IS THE REASON THIS FILE EXISTS
  4  SECTION 7 AT ITS CAP             the handoff is replaced every session, so it bloats fastest
  5  EVERY RELOCATION LEFT A POINTER  a rule that simply vanishes reads as a rule that was repealed
  6  2 -> 1, NEVER 2 -> 0             relocation can promote a duplicate into the ONLY copy, and then
                                      cutting it as "redundant" removes the rule outright

WHAT IT DOES NOT PROVE: that the surviving copy says it WELL. That is a reading, and no script does it.
An audit reporting nothing found is evidence it was too shallow, not that the work was clean.

    uv run python tools/verify_charter_continuity.py
    uv run python tools/verify_charter_continuity.py --selftest

CHECK 6b READS A DOCUMENT OUTSIDE THIS REPOSITORY and is therefore gated on an environment variable,
exactly as `tools/stepb_audit.py` reads `LEGAL_TRANSLATION_A4`: the tool ships, the location does not.
An earlier draft of this file hard-coded that path, which put a home-relative path carrying a username
into a PUBLIC repository -- the exact class `tools/publication_check.py` exists to block.

    LT_HOUSE_TEMPLATES="<the house templates folder>" uv run python tools/verify_charter_continuity.py

Without it that check is VOID and this script exits 1 with a banner. An unreadable source is not a pass.
"""
import os
import re
import subprocess
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parent.parent

# --------------------------------------------------------------------------- configuration
# THE PIN IS THE PRE-REDUCTION CHARTER. Never a branch name: a branch stops meaning "before" the
# moment it merges, and the vacuous case looks exactly like the passing case.
BASELINE = "49cf6df1a0379afdfa69e1e6225c1d63ea0d92f6"

# Something ONLY the pre-reduction charter had. If this is absent the pin is wrong and every
# comparison below is vacuous -- so it is check 0 and it is fatal.
ONLY_IN_BASELINE = "| **1** | How to read this document | communication · the document set · reading order |"

# TWO BASELINES, AND CONFLATING THEM IS A FALSE ALARM I RAISED ON MY OWN FIRST RUN. The continuity
# ledger (check 6) asks "did the whole reduction lose anything?", so it needs the PRE-REDUCTION pin.
# The must-not list (check 1) asks "did THIS phase touch what belongs to another?", so it needs the
# pin at THIS PHASE'S ENTRY. Measured against the pre-reduction pin, section 5.1 reads as CHANGED --
# and it was, legitimately, when phase 3a moved RUN, DO NOT READ into it from section 7. An alarming
# false report is no more useful than a reassuring one.
PHASE_BASELINE = os.environ.get("LT_PHASE_BASELINE", "").strip() or "fab2050"

# Sections owned by a phase that is NOT running. Update this when the phase changes; it is the whole
# point of the check that it names them explicitly rather than inferring them.
MUST_NOT_TOUCH = ["5.1", "5.15", "5.16"]          # phase 3d

# A DECLARED TOUCH IS NOT AN EXEMPTION -- IT IS A NARROWER ASSERTION.
#
# Phase 3b step 8 had to rewrite the misdirected `§` references wherever they were, and two of the
# eleven sat inside 5.1's cycle table. That is a genuine collision between two instructions: "do
# not touch 5.1" and "every misdirected reference needs a reader". Silencing the check would train
# a reader to skim it, which is this project's own objection to a bad control.
#
# So instead: each row below is (section, new_text, old_text). The check REVERSES the declared
# substitutions and requires the result to be BYTE-IDENTICAL to the phase pin. Anything else that
# changed in that section still fails, and a declaration that no longer applies fails too.
DECLARED_TOUCHES = [
    ("5.1",
     "Read the branch's brief in **section 3 of `STEP-B-ANALYSIS.md`**",
     "Read the branch's brief in `STEP-B-ANALYSIS.md` §3"),
    ("5.1",
     "**that document's section 3.3** says option 7's substance lives in **its section 6**, and a "
     "session that planned branch 2 from section 3.3 alone",
     "§3.3 says option 7's substance lives in §6, and a session that planned branch 2 from §3.3 "
     "alone"),
    ("5.1",
     "The method for that branch kind in **section 4 of `STEP-B-ANALYSIS.md`**, plus the smoke "
     "suite, plus the parity check from branch 2 onward, plus a graded run where **that section** "
     "says a graded run",
     "The method for that branch kind in `STEP-B-ANALYSIS.md` §4, plus the smoke suite, plus the "
     "parity check from branch 2 onward, plus a graded run where §4 says a graded run"),
]

# Headings that did not exist at the baseline and are allowed to now.
HEADINGS_ADDED_SINCE_BASELINE = ["1.7"]

SECTION_7_CAP = 35
DECLARED_CAP = 350

# --------------------------------------------------------------------------- check 3 data
# A DECLARATION is a sentence in which the charter states ITS OWN length. Each pattern below has a
# vector in the selftest. A figure named as SUPERSEDED -- "1,322 lines, NOT 1,666" -- is legitimate
# and must not fire, so the "NOT ..." position is excluded before the patterns run.
SUPERSEDED = re.compile(r"\bNOT (?:THE )?([\d,]{3,7})\b", re.I)
DECLARATIONS = [
    ("the 1.7 over-cap exemption",
     re.compile(r"OVER-CAP EXEMPTION, DECLARED [\d-]+: ([\d,]+) lines against a cap of (\d+)")),
    ("a shouted charter-length claim",
     re.compile(r"THE CHARTER IS ([\d,]+) LINES")),
    ("a plain charter-length claim",
     re.compile(r"(?:this file|the charter|this charter) is ([\d,]+) lines", re.I)),
    ("a generic against-a-cap claim",
     re.compile(r"\b([\d,]+) lines against a cap of (\d+)")),
]

# --------------------------------------------------------------------------- check 5 data
# (section, the phrase that says what was cut and where it went)
POINTERS = [
    ("1.6", "CUT 2026-08-24"),
    ("6.2", "CUT 2026-08-24"),
    ("5.10", ".claude/rules/ooxml.md"),
    ("5.11", ".claude/rules/skill-authoring.md"),
]

# --------------------------------------------------------------------------- check 6 data
# (label, needle, the files any ONE of which may carry it). The charter counts as a home too.
# A needle found in NONE of them is 2 -> 0 and the rule is gone.
LEDGER = [
    ("the tree totals",            "3,651,835",                    ["A3-STRUCTURAL-ANALYSIS.md"]),
    ("a per-file byte figure",     "57,269",                       ["A3-STRUCTURAL-ANALYSIS.md"]),
    ("the truncation position",    "55,466",                       ["A3-STRUCTURAL-ANALYSIS.md"]),
    ("L1's unpairable entries",    "46 of 1,158",                  ["FINDINGS-REGISTER.md"]),
    ("G9's segment keys",          "412 of 412",                   ["FINDINGS-REGISTER.md"]),
    ("C9's detector rate",         "2 times in 13",                ["FINDINGS-REGISTER.md"]),
    ("G12's residue",              "16 `quality_check` FINDINGS",  ["FINDINGS-REGISTER.md"]),
    ("I-17's closure",             "I-17",                         ["FINDINGS-REGISTER.md"]),
    ("I-18's recurrence",          "I-18",                         ["FINDINGS-REGISTER.md"]),
    ("I-19's baseline pin",        "I-19",                         ["FINDINGS-REGISTER.md"]),
    ("I-20's fixture rebuild",     "I-20",                         ["FINDINGS-REGISTER.md"]),
    ("RUN, DO NOT READ",           "RUN, DO NOT READ",             ["CLAUDE.md"]),
    ("the frozen-intermediate blind spot", "post-compliance",
     ["CLAUDE.md", ".claude/skills/frozen-intermediate-test/SKILL.md"]),
    ("its measured figure",        "0 findings over 81 tracked-change",
     ["CLAUDE.md", ".claude/skills/frozen-intermediate-test/SKILL.md"]),
    ("the ten OOXML rules",        "ZWSP",                         ["CLAUDE.md", ".claude/rules/ooxml.md"]),
    # THE NEEDLE WAS WRONG ON THE FIRST RUN, not the rule: it read "no changelog" against a charter
    # that says "No changelog inside the archive, ever." A lowercase two-word needle reported a
    # route-1 rule as GONE. This is 5.12's sixth point committed inside the instrument that cites it.
    ("no changelog in the archive", "No changelog inside the archive", ["CLAUDE.md"]),
    ("the rev44 token",            "v2026.04.22-rev44",            ["CLAUDE.md"]),
    # STEP 7 -- the three skills. A skill's body is not in context until invoked, so the charter must
    # keep an unconditional twin of anything whose absence is irreversible.
    ("the release procedure",      "package.py",
     ["CLAUDE.md", ".claude/skills/publish-skill-archives/SKILL.md"]),
    ("the freeze-the-intermediate trick", "FREEZE THE TRANSLATED INTERMEDIATE",
     ["CLAUDE.md", ".claude/skills/frozen-intermediate-test/SKILL.md"]),
    ("the seven-point audit method", "NEVER A TWO-WORD NEEDLE",
     ["CLAUDE.md", ".claude/skills/audit-gate/SKILL.md"]),
    ("audit_session_stepb never ships", "audit_session_stepb.py",
     ["CLAUDE.md", ".claude/skills/audit-gate/SKILL.md"]),
    # STEP 9 -- the confidentiality split. EVERY ONE OF THESE MUST HAVE A HOME IN THE CHARTER ITSELF,
    # never only in the evidence document, and NEVER in a path-scoped rule file. Prohibition 2.
    ("no client names ever",       "No client or counterparty names, ever",  ["CLAUDE.md"]),
    ("instrument class and language only",
     "NAME A TEST DOCUMENT BY ITS INSTRUMENT CLASS AND ITS LANGUAGE",        ["CLAUDE.md"]),
    ("the location rule",          "THE LOCATION RULE",                      ["CLAUDE.md"]),
    ("a comment ships",            "A comment ships",                        ["CLAUDE.md"]),
    ("the run report is metadata-only", "metadata-only by construction",     ["CLAUDE.md"]),
    ("synthetic examples only",    "Renaming is not enough",                 ["CLAUDE.md"]),
    ("run all three controls",     "Three controls",                         ["CLAUDE.md"]),
]

# Route-1 phrases that may never sit ONLY in a path-scoped rule file. Prohibition 2, and it is the one
# prohibition whose failure is a publication that cannot be undone.
#
# THE FIRST VERSION OF THIS CHECK FORBADE PRESENCE, AND THAT IS THE WRONG READING. It fired on
# `skill-authoring.md`, which carries the run-report rule -- correctly, because step 6a moved it there
# AND left an unconditional twin in section 5.4. Belt and braces is not the failure; being behind the
# glob and NOWHERE ELSE is. So the test is SOLE presence, and an over-strict check that condemns
# correct work is the same defect as a lax one that waves through bad work.
NEVER_ONLY_PATH_SCOPED = [
    "No client or counterparty names, ever",
    "NAME A TEST DOCUMENT BY ITS INSTRUMENT CLASS AND ITS LANGUAGE",
    "THE LOCATION RULE",
    "metadata-only by construction",
]

CR = bytes([13]).decode("ascii")

failures = []
notes = []


def head(n, title):
    print("\n" + "=" * 100)
    print(f"{n}. {title}")
    print("=" * 100)


def ok(msg):
    print(f"  [OK  ] {msg}")


def bad(n, msg):
    failures.append((n, msg))
    print(f"  [FAIL] {n}: {msg}")


def note(msg):
    notes.append(msg)
    print(f"  [NOTE] {msg}")


def git_show(rev, path, root=None):
    r = subprocess.run(["git", "show", f"{rev}:{path}"], cwd=str(root or ROOT),
                       capture_output=True, timeout=120)
    if r.returncode != 0:
        return None
    return r.stdout.decode("utf-8", errors="replace")


def flat(text):
    """CRLF -> LF, for comparing CONTENT.

    `git show` returns raw bytes with CRLF intact; `Path.read_text()` applies universal newlines and
    hands back LF. Comparing one against the other once reported all NINE must-not sections as
    CHANGED, every one with an identical line count -- which is the tell: a real edit moves a line
    count, and nine simultaneous no-op changes is an instrument, not a finding. Terminators are
    checked separately, so normalising here loses nothing.
    """
    return text.replace(CR + "\n", "\n").replace(CR, "\n")


def section_body(text, number):
    """The body of a `### N.M` heading, up to the next heading of the same or higher level."""
    m = re.search(r"^### " + re.escape(number) + r" [^\n]*\n(.*?)(?=^#{2,3} |\Z)",
                  text, re.S | re.M)
    return m.group(1) if m else None


def declared_sizes(text):
    """Every place the text states its own line count, with the label of the pattern that found it.

    Figures named as superseded are removed FIRST, so "1,305 lines, NOT 1,666" yields 1,305 alone.
    """
    stale_ok = set(SUPERSEDED.findall(text))
    # DEDUPE BY THE OFFSET OF THE NUMBER ITSELF. Several patterns match the same sentence on
    # purpose -- the generic one is a net under the specific ones -- and without this the same
    # declaration is reported two or three times, which reads as several defects rather than one.
    seen = {}
    for label, pat in DECLARATIONS:
        for m in pat.finditer(text):
            raw = m.group(1)
            if raw in stale_ok and not m.group(0).upper().startswith(("OVER-CAP", "THE CHARTER IS")):
                continue
            seen.setdefault(m.start(1), (label, raw, int(raw.replace(",", "")), m.group(0)[:70]))
    return [seen[k] for k in sorted(seen)]


# =========================================================================== the run
def run(charter_path="CLAUDE.md", root=None):
    root = Path(root or ROOT)
    charter_file = root / charter_path
    charter = charter_file.read_text(encoding="utf-8")

    # ------------------------------------------------------------------ 0
    head(0, "IS THE BASELINE REAL? — the guard that stops this whole run being vacuous")
    base = git_show(BASELINE, charter_path, root)
    if base is None:
        print(f"  VOID — {BASELINE[:8]} could not be read. Every check below would compare the")
        print("  working tree against itself and report success. Nothing has been established.")
        return 2
    if ONLY_IN_BASELINE not in base:
        print("  VOID — the pinned baseline does not hold the pre-reduction marker, so it is not")
        print("  the 'before' content. Fix the pin; do not read the results below.")
        return 2
    if base == charter:
        print("  VOID — baseline is byte-identical to the working tree. Nothing was measured.")
        return 2
    ok(f"baseline {BASELINE[:8]} resolves, holds the pre-reduction marker, and differs from the tree")
    measured = len(charter.splitlines())
    ok(f"baseline {len(base.splitlines())} lines · working {measured} lines")

    # LINE TERMINATORS, IN BYTES. A `grep -c` for a carriage return once reported 0 on this file
    # while it had one per line, so the reassuring answer came from a broken needle. `.gitattributes`
    # forbids translating line endings, and a flip is invisible in a diff while breaking every byte
    # comparison below.
    raw_base = subprocess.run(["git", "show", f"{BASELINE}:{charter_path}"], cwd=str(root),
                              capture_output=True, timeout=120).stdout
    raw_now = charter_file.read_bytes()
    cr_b, cr_n = raw_base.count(bytes([13])), raw_now.count(bytes([13]))
    lf_b, lf_n = raw_base.count(bytes([10])), raw_now.count(bytes([10]))
    print(f"  baseline {len(raw_base)} bytes · CR {cr_b} · LF {lf_b}")
    print(f"  working  {len(raw_now)} bytes · CR {cr_n} · LF {lf_n}")
    if (cr_b == lf_b and cr_n == lf_n) or (cr_b == 0 and cr_n == 0):
        ok("terminators consistent end to end — nothing was translated")
    else:
        bad("0", f"MIXED OR FLIPPED terminators: baseline CR/LF {cr_b}/{lf_b}, working {cr_n}/{lf_n}")

    # ------------------------------------------------------------------ 1
    head(1, "THE MUST-NOT LIST — sections owned by another phase, against THIS PHASE'S entry pin")
    phase = git_show(PHASE_BASELINE, charter_path, root)
    anc = subprocess.run(["git", "merge-base", "--is-ancestor", PHASE_BASELINE, "HEAD"],
                         cwd=str(root), capture_output=True, timeout=60)
    if phase is None:
        bad("1", f"VOID — the phase pin {PHASE_BASELINE} could not be read, so nothing below "
                 f"about the must-not list has been established")
    elif anc.returncode != 0:
        bad("1", f"VOID — {PHASE_BASELINE} is not an ancestor of HEAD, so it is not this phase's "
                 f"entry point and every comparison against it is meaningless")
    else:
        ok(f"phase pin {PHASE_BASELINE} is an ancestor of HEAD "
           f"({len(phase.splitlines())} lines at entry)")
        for num in MUST_NOT_TOUCH:
            was, now = section_body(flat(phase), num), section_body(flat(charter), num)
            if was is None or now is None:
                bad("1", f"section {num} could not be located in "
                         f"{'the phase pin' if was is None else 'the working tree'} — renamed?")
                continue
            touches = [(new, old) for s, new, old in DECLARED_TOUCHES if s == num]
            reversed_now = now
            unused = []
            for new, old in touches:
                if flat(new) in reversed_now:
                    reversed_now = reversed_now.replace(flat(new), flat(old))
                else:
                    unused.append(new[:44])
            if unused:
                bad("1", f"section {num}: declared touch(es) no longer present — {unused}. A "
                         f"declaration that does not apply is a stale exemption, not a pass")
            elif reversed_now == was:
                if touches:
                    ok(f"section {num:5} changed ONLY in the {len(touches)} declared way(s); "
                       f"reversing them is byte-identical to the phase pin")
                else:
                    ok(f"section {num:5} byte-unchanged since phase entry "
                       f"({len(now.splitlines())} lines)")
            else:
                bad("1", f"section {num} CHANGED beyond its declared touches "
                         f"({len(was.splitlines())} -> {len(now.splitlines())} lines) and it is "
                         f"not this phase's to touch")

    # ------------------------------------------------------------------ 2
    head(2, "NO HEADING LOST, NO RENUMBER — headings are what every pointer resolves against")
    hd = lambda t: [n for _, n in re.findall(r"^(#{2,3}) (\d+(?:\.\d+)?)[. ]", t, re.M)]
    was_h, now_h = hd(base), hd(charter)
    lost = [n for n in was_h if n not in now_h]
    gained = [n for n in now_h if n not in was_h]
    if lost:
        bad("2", f"heading(s) LOST: {lost}")
    else:
        ok(f"all {len(was_h)} baseline headings still present")
    if gained == HEADINGS_ADDED_SINCE_BASELINE:
        ok(f"headings added: {gained} — as declared, so no renumber")
    else:
        bad("2", f"headings added: {gained}; declared {HEADINGS_ADDED_SINCE_BASELINE}")
    if was_h == [n for n in now_h if n not in HEADINGS_ADDED_SINCE_BASELINE]:
        ok("heading ORDER unchanged — nothing was resequenced")
    else:
        bad("2", "heading order changed")

    # ------------------------------------------------------------------ 3
    head(3, "THE DECLARED SIZE — every sentence stating this file's own length, against the measurement")
    decls = declared_sizes(charter)
    if not decls:
        bad("3", "the charter declares its own length NOWHERE. 1.7 must carry the exemption, taken "
                 "from the checker on the commit that declares it")
    for label, raw, value, snippet in decls:
        if value == measured:
            ok(f"{label:34} says {raw} and the file is {measured} — measured, not remembered")
        else:
            bad("3", f"{label} says {raw}; the file is {measured}. A number that was true when "
                     f"written and is false now misleads exactly as much as one never true "
                     f"— {snippet!r}")
    caps = {int(m) for pat in (DECLARATIONS[0][1], DECLARATIONS[3][1])
            for m in [g[1] for g in pat.findall(charter)] if m}
    if caps and caps != {DECLARED_CAP}:
        bad("3", f"a declared cap of {sorted(caps)} against the configured {DECLARED_CAP}")
    elif caps:
        ok(f"every declared cap is {DECLARED_CAP}")
    # A REPORT, NEVER A FAILURE: four-digit thousands figures near the file's own size that no
    # pattern claimed. The patterns are a list, and a list is always incomplete.
    near = sorted({m for m in re.findall(r"\b\d,\d{3}\b", charter)
                   if abs(int(m.replace(",", "")) - measured) <= measured * 0.25
                   and int(m.replace(",", "")) != measured})
    if near:
        print(f"  [REPORT] thousands figures within 25% of {measured} that no pattern claimed: "
              f"{near} — read each; a superseded figure named as superseded is fine")

    # ------------------------------------------------------------------ 4
    head(4, f"SECTION 7 AT ITS CAP — it is replaced every session, so it bloats fastest")
    m7 = re.search(r"^## 7\.(.*)\Z", charter, re.S | re.M)
    if not m7:
        bad("4", "no section 7 found at all")
    else:
        n7 = len(("## 7." + m7.group(1)).splitlines())
        if n7 <= SECTION_7_CAP:
            ok(f"section 7 is {n7} lines against the cap of {SECTION_7_CAP}")
        else:
            bad("4", f"section 7 is {n7} lines against a cap of {SECTION_7_CAP}")

    # ------------------------------------------------------------------ 5
    head(5, "EVERY RELOCATION LEFT A POINTER — a cut with no pointer reads as a repeal")
    for num, must in POINTERS:
        body = section_body(charter, num) or ""
        if not body:
            bad("5", f"section {num} is missing entirely — the heading is the pointer's return path")
        elif must in body:
            ok(f"section {num:5} carries its pointer ({len(body.splitlines())} lines)")
        else:
            bad("5", f"section {num} has no pointer naming what left it (looked for {must!r})")

    # ------------------------------------------------------------------ 6
    head(6, "2 -> 1, NEVER 2 -> 0 — relocation can promote a duplicate into the ONLY copy")
    # THE NEEDLE IS NORMALISED, AND SO IS THE HAYSTACK -- case, whitespace and emphasis. Three
    # separate case-sensitivity bugs in this ledger in one day, each reporting a rule that is
    # plainly present as GONE: 'no changelog' against "No changelog...", 'A comment ships' against
    # "A COMMENT SHIPS...". A rule gets SHOUTED when it is rewritten to be more prominent, which
    # is exactly when a case-sensitive needle breaks. That is §5.12's sixth point: never a needle
    # that a rewrap or a capital can defeat.
    def needle_norm(t):
        return re.sub(r"\s+", " ", re.sub(r"[*`]", "", t)).lower()

    charter_n = needle_norm(charter)
    base_n = needle_norm(base)
    for label, needle, homes in LEDGER:
        n = needle_norm(needle)
        found = {}
        for h in homes:
            p = root / h
            if p.exists():
                c = (charter_n if h == charter_path else
                     needle_norm(p.read_text(encoding="utf-8"))).count(n)
                if c:
                    found[h] = c
        if not found:
            bad("6", f"{label}: {needle!r} is in NONE of {homes} — 2 -> 0, the rule is gone")
        else:
            ok(f"{label:38} baseline {base_n.count(n)} -> " +
               " · ".join(f"{k} {v}" for k, v in found.items()))

    head("6b", "PROHIBITION 2 — no route-1 rule may sit ONLY in a path-scoped rule file")
    rules_dir = root / ".claude" / "rules"
    rule_files = sorted(rules_dir.glob("*.md")) if rules_dir.exists() else []
    if not rule_files:
        note("no .claude/rules/*.md found — nothing to check, and that is not a pass for anything")
    else:
        for phrase in NEVER_ONLY_PATH_SCOPED:
            scoped = [f.name for f in rule_files if phrase in f.read_text(encoding="utf-8")]
            in_charter = phrase in charter
            if scoped and not in_charter:
                bad("6b", f"route-1 phrase {phrase!r} is in path-scoped {scoped} and NOT in the "
                          f"charter. A scoped rule is absent until a matching file is read — and "
                          f"absent here means a publication that cannot be undone")
            elif scoped:
                ok(f"{phrase[:44]:44} in {scoped} AND unconditionally in the charter")
            else:
                ok(f"{phrase[:44]:44} in the charter only" if in_charter else
                   f"{phrase[:44]:44} in no rule file")

    # ------------------------------------------------------------------ 7
    head(7, "THE HOUSE EVIDENCE DOCUMENT — gated on LT_HOUSE_TEMPLATES, and VOID without it")
    house = os.environ.get("LT_HOUSE_TEMPLATES", "").strip()
    if not house:
        print("  VOID — LT_HOUSE_TEMPLATES is not set, so the house evidence document could not be")
        print("  read and its arithmetic is UNVERIFIED. This is not a pass. The tool ships; the")
        print("  location does not. Set it and re-run:")
        print('      LT_HOUSE_TEMPLATES="<the house templates folder>" '
              "uv run python tools/verify_charter_continuity.py")
        bad("7", "check 7 could not be completed — an unreadable source is not a pass")
    else:
        ev = Path(house) / "EVIDENCE-lt-charter-reduction.md"
        if not ev.exists():
            bad("7", f"{ev.name} not found under LT_HOUSE_TEMPLATES")
        else:
            text = ev.read_text(encoding="utf-8")
            targets = [int(m) for m in
                       re.findall(r"^### Section \d — [^·\n]*· \d+ → ~?(\d+)", text, re.M)]
            if len(targets) != 7:
                bad("7", f"found {len(targets)} per-section targets, expected 7 — needle drifted")
            else:
                ok(f"the seven targets list as {targets}, summing to {sum(targets)}")
                if targets[6] != SECTION_7_CAP:
                    bad("7", f"section 7's target is {targets[6]}, not {SECTION_7_CAP}")
                else:
                    ok(f"section 7's target is {SECTION_7_CAP}")
                if f"is {sum(targets)} from the seven sections" not in text:
                    bad("7", f"the column sums to {sum(targets)}; the document does not state it")
                else:
                    ok("the stated after-figure equals the sum of the column, re-derived by listing")

    # ------------------------------------------------------------------ verdict
    print("\n" + "=" * 100)
    print("VERDICT")
    print("=" * 100)
    for n, msg in failures:
        print(f"  FAIL {n}: {msg}")
    for msg in notes:
        print(f"  NOTE   {msg}")
    print(f"\n  {len(failures)} failure(s), {len(notes)} note(s).")
    print("  What this does NOT prove: that the surviving copies say it WELL. That is a reading.")
    return 1 if failures else 0


# =========================================================================== selftest
def selftest():
    """EVERY CHECK MUST BE ABLE TO FAIL. A check that cannot fail is not a check.

    Check 3 is the reason this file exists, so it gets the most vectors -- including the one that
    caught the live defect the promotion was ordered for.
    """
    ok_all = True

    def case(name, got, want):
        nonlocal ok_all
        good = got == want
        ok_all &= good
        print(f"  [{'OK  ' if good else 'FAIL'}] {name}: got {got!r}, want {want!r}")

    print("declared_sizes — the widened check 3")
    case("1.7's exemption is read ONCE, not once per matching pattern",
         [d[2] for d in declared_sizes(
             "> **OVER-CAP EXEMPTION, DECLARED 2026-08-24: 1,305 lines against a cap of 350.**")],
         [1305])
    case("THE LIVE DEFECT: a shouted §7 count is read",
         [d[2] for d in declared_sizes("**THE CHARTER IS 1,322 LINES, NOT 1,666.**")],
         [1322])
    case("a superseded figure alone does NOT count as a declaration",
         [d[2] for d in declared_sizes("It is 1,305 lines, NOT 1,666.")],
         [])
    case("a plain claim is read",
         [d[2] for d in declared_sizes("The charter is 1,305 lines today.")],
         [1305])
    case("prose with no self-declaration yields nothing",
         declared_sizes("A cap of 350 lines is the L class."), [])

    print("section_body — the span used by checks 1, 4 and 5")
    doc = "### 5.1 A\nalpha\n\n### 5.2 B\nbeta\n\n## 6. C\ngamma\n"
    case("5.1's body stops at the next heading", section_body(doc, "5.1"), "alpha\n\n")
    case("5.2's body stops at a HIGHER-level heading", section_body(doc, "5.2"), "beta\n\n")
    case("a missing section is None, never empty string", section_body(doc, "9.9"), None)

    print("flat — the CRLF trap that once reported nine no-op changes as findings")
    case("CRLF normalises to LF", flat("a" + CR + "\nb"), "a\nb")
    case("a bare CR normalises too", flat("a" + CR + "b"), "a\nb")

    print("configuration sanity")
    case("the continuity baseline is a full sha, not a branch name", len(BASELINE), 40)
    case("the phase pin and the continuity pin are DIFFERENT commits — the two-baseline design",
         BASELINE.startswith(PHASE_BASELINE), False)
    case("the must-not list names the phase that is NOT running",
         MUST_NOT_TOUCH, ["5.1", "5.15", "5.16"])
    case("prohibition 2 is tested as SOLE presence, not presence",
         "NEVER_ONLY_PATH_SCOPED" in Path(__file__).read_text(encoding="utf-8"), True)
    case("no home-relative path is hard-coded in this file",
         [l for l in Path(__file__).read_text(encoding="utf-8").splitlines()
          if re.search(r"[A-Za-z]:" + re.escape(chr(92)) + r"Users", l)], [])

    print(f"\nselftest {'PASS' if ok_all else 'FAIL'}")
    return 0 if ok_all else 1


if __name__ == "__main__":
    sys.exit(selftest() if "--selftest" in sys.argv else run())
