# CLAUDE.md — legal-translation

**A Claude skill that translates legal documents into English without breaking the Word file** — `README.md`
owns the description; the quality target is **magic-circle law firm**, in translation *and* formatting. **This
project updates, and may partly rebuild, that skill** — first built in Cowork, unversioned and unplanned.

---

## 1. How to read this document

### 1.1 How to talk to me — read this before answering anything

**In the user-global `.claude/CLAUDE.md`, which loads in every project, and not restated** — plain layman's
terms by default, define each term on first use, number your questions. The jargon this project defines on
first use:
*OOXML, run, glyph, ZWSP, monorepo, variant build, fixture, smoke test, squash-merge, progressive
disclosure, token budget.*

### 1.2 What this file is, and what it is not

**It is the charter** — what the project is, what is left, how the work gets done, where things live, where
it stands. **It is public from commit one.** **It is not the evidence, the build plan or the history:** those
are other files, and this one points at them rather than summarising them, because a session once reasoned
from a summary of the evidence and reached a wrong conclusion.

### 1.3 The document set — what to read for what

| file | what it is | when you need it | it owns |
|---|---|---|---|
| **`CLAUDE.md`** *(this)* | the charter | first, always | goals · order · status · rules · structure |
| **`PLAN-2-step-b.md`** | **the build plan, phase 2's PLAN FILE** — only Part One is needed to build; its header declares its size | every build step | its section 2 the order · 3 the brief · 4 the test method · 9 the step → findings map |
| **`evidence/REGISTER-findings.md`** | the evidence base — every finding with its proof, **the fastest way to understand what the project has learned** | for the proof behind any claim | every finding, clustered by root cause |
| **`evidence/EVIDENCE-a3-structure.md`** | the structural analysis | a structural judgement, **or any run compared against baseline** | context, runtime, redundancy, divergence; **the A2 grade baselines**, section 11 |
| **`PLAN-3-opus5-migration.md`** | goal (iii) — **SUPERSEDED 2026-10-13**, Opus 5 dropped *(Wouter)* | for its reasoning only | the Opus 5 steps and Step C's design, neither now planned |
| **`DECISIONS-LOG.md`** | the dated reasons for what was decided; beside it `evidence/EVIDENCE-phase2-history.md`, moved word for word out of §3.1 | before re-opening anything settled | closed questions · phase 2's history |
| **`evidence/EVIDENCE-confidentiality.md`** | the dated evidence behind §5.6 — **no rule**: each stayed in the charter, route 1 | **before touching a confidentiality control** | measurements, incidents, the controls' history, the census |
| **`evidence/EVIDENCE-measurement.md`** | the twelve-row test-corpus listing *(from §5.5)* and the cost stories *(from §5.1, §5.3 and §5.5)* | corpus facts, defect costs | the corpus, grader gaps, every cost story, the gate's measures |
| **the private sibling folder** | `context.md`, `leakage-names.txt`, the A4 set, grader backups, the harness | before anything touching confidentiality, packaging or publication | **never committable** |

**The build plan, the register and the structural analysis are live inputs; the rest are reference.** The A4
blind desk review's 2,222-line report lives outside the repository, its path in the private `context.md`.

**THE HOUSE'S WORDS, SINCE 2026-10-13** *(Wouter)*: a **phase**
is one row of §3.1 *(this file said **step**, 0–5)*; a **step** is one row of section 2 of `PLAN-2-step-b.md`
*(said **branch**, 0–19 plus D1–D3, now 20–22)*; a **sub-step** is a step's slice, numbered 12.1 and never 12c;
and **the skill's own eleven steps are written skill Step N**, so step 10 and skill Step 10 never meet. **Text
dated before 2026-10-13 keeps its words**, read through this mapping; `DECISIONS-LOG.md`, 2026-10-13 (5), owns
the four rulings.

### 1.4 Reading order for a new session

**The house file's reading order applies — §7, then §3.** By task: **building** → sections 2, 3 and 4 of
`PLAN-2-step-b.md`, in order · **the evidence** → `REGISTER-findings.md` · **how the work is done** → §5 here.

### 1.5 Two rules about reading, both bought with real time

**Never work from a précis, and re-measure do not re-read, are in the user-global `.claude/CLAUDE.md`, not
restated** *(§5.3 has the cost stories)*. **A third, project-specific: a claim can be refuted for the WRONG
REASON, which costs more than believing it — so measure a claim about BEHAVIOUR where the behaviour happens,
never in the document's structure.** The tell is a refutation reached from a different KIND of evidence than
the claim was made from; the A16 instance that bought this is in `EVIDENCE-measurement.md`.

### 1.6 Contents

**CUT 2026-08-24 and must not come back** — a table of headings is derivable and goes stale in silence.
§1.3 and §1.4 own the navigation.

### 1.7 The size class, and the cap this charter is held to

**ARCHETYPE: Analysis + rebuild of an existing artefact** (`rebuild`) — the closest of the template's eleven,
and the one row ● on every optional column, so this charter carries those blocks rather than dropping any.

**SIZE CLASS: L**, this project having run far past eight sessions, the observable test. **Every cap lives in
`verify.config.json`, in wrapped lines, and none is restated here** — a restated cap is a second place to go
stale. Every cap is enforced, not aspirational; the over-cap declaration this section carried until 2026-10-16
is in `DECISIONS-LOG.md` under that date.

## 2. Project overview

### 2.1 What the skill is, and who needs it

**`README.md` owns the description** — the problem, the eleven-step pipeline, the golden rule and the feature
list *(also in both `SKILL.md` files, so a feature claim changes in three places or in none)*. **What stays here:**

- **The driving use case is the author's own in-house energy practice** — cross-border wind and energy work,
  sources in eight languages.
- **Two published claims have measured evidence, six do not:** *"others translate very well too"* rests on
  D03 alone *(§5.5)*, *"minutes, not seconds"* on `EVIDENCE-a3-structure.md` section 11. **Fixing the claim is
  part of the build.**
- **This is a PUBLIC skill** (GitHub, lawve.ai) — strangers read every file *(§5.6, a hard constraint)*.
- **A reverse skill (English → each language) is OUT OF SCOPE** — a free lexicon option if direction-neutral
  at no cost, never a reason to add scope or compromise quality.

### 2.2 What this project is — the four goals

Not a feature-add project — four goals, in priority order:

| | goal | where it stands |
|---|---|---|
| **(i)** | **Deep structural review** — the scaffolding and files, for redundancy and *better translations* | **Delivered** by Step A: `EVIDENCE-a3-structure.md`, all eleven structural questions settled (**§6.1**) |
| **(ii)** | **Close the known quality and formatting defects** — bold, signature blocks and layout, tracked changes | **Planned, not built:** all three turned out to be classes rather than defects (§2.4); phase 2 builds the plan |
| **(iii)** | **Make the skill Opus 5-ready** — **never touching the anti-drift and anti-deviation safeguards in its name** | **DROPPED, 2026-10-13** *(Wouter)*: phase 3 is the full Cowork test instead; the batch cap stays, on evidence |
| **(iv)** | **Minimise install-truncation risk and repair its detection** — a truncated install degrades every user's translation | **Two pieces:** the size discipline *lapsed*, a regression; the coverage **never built**; options 8 and 9 |

> **QUALITY IS THE MAIN DRIVER. SPEED MATTERS, BUT LESS — AND SPEED MUST NEVER COMPROMISE QUALITY.**
> *(Wouter, 2026-08-04; it governs all four goals and every option under them.)* The **25 minutes of fixed overhead**
> is a real cost and worth attacking, **but not by reading fewer lexicons, not by raising the 35-paragraph
> cap, and not by thinning a gate** — the evidence says all three would cost quality.

### 2.3 What has been done

**Do not re-open any of it.** Eight strands, each owned by a document in §1.3: Step 0's choices · A1+A2's twelve
runs · **INPUT POINT 1, CLOSED 2026-07-31** · A3 · A4's sealed report · the A3↔A4 comparison, which
produced register cluster X · Step B · Step 1, **the repository PUBLIC, protection live.**

**THE EVIDENCE-BASE COUNTS ARE NO LONGER TYPED HERE** *(load-bearing wording — `claudemd_claims.py` keys six
assertions on it)*: a typed count goes stale silently, so **quote it from `audit_register.py` and name the
population** — I-1 to I-11 are defects in the A1 harness and review tooling, I-12 onward in the repository's
own committed checks.

### 2.4 What the evidence says — the seven things a new session must know

1. **THIS IS NOT A FORMATTING PROJECT.** The pipeline has silently destroyed legally material content — a
   deed's only footnote, 14 of 28 comment anchors, more in `REGISTER-findings.md` — **each time the auxiliary
   part translated perfectly, the *pointer* destroyed, and every gate reporting PASS.**
2. **THREE independent mechanisms explain why nothing was caught — never scope from the token-set sentence
   alone**, or the build under-builds: `validate_apply --strict` polices only *missing* tokens · the mandatory
   quality gate discards its own verdict · a delivered `.docx` failing its own ZIP test warns and exits 0.
3. **Do not spend the build on translation** — quality and terminology scored 9, conformance 10, on all twelve.
4. **Render BOTH documents: the visual diff is the PRIMARY instrument, not a final check** — reading the
   translation alone misses what is *absent*; §5.2 makes it a condition of done.
5. **DO NOT WEAKEN THE ANTI-DRIFT SAFEGUARDS in response to any of this** — add the *missing* rule, never soften
   an existing one; fix a gate wrong in SCOPE, never bypass it, never alter a faithful translation.
6. **Fix the CLAIM as well as the code** — six findings need it *(register cluster X)*: an independent reader
   praised as strongest the exact layer the register shows is blind, and credited as coverage a device it
   shows leaks. *(Pointed at by number — do not renumber this item.)*
7. **Judge a layout device on its RENDERED EFFECT, never its element count** — and what looked like one cluster
   is two independent failures: putting the English back *deletes* structure it should keep, while the data
   contract *cannot describe* the formatting. Two fixes, two files, neither closing the other's rows.

**Each of the four defects Wouter named at the outset is a CLASS, not a defect** — `REGISTER-findings.md`
holds each with its measurement, two further classes being workstreams in `PLAN-2-step-b.md`.

### 2.5 Decisions that still bind

**`DECISIONS-LOG.md` holds each one's reasoning by date — read that entry before re-opening any of these.**

| decided | what |
|---|---|
| 2026-07-27 | **Two variants only**, a client-internal third out of scope; the test corpus **outside the tree, permanently**; distribution **public**, so confidentiality binds from commit one; no reverse skill |
| 2026-07-28 | **One private monorepo**, both trees side by side, no build step, a parity check; **no `CHANGELOG.md` going forward**; **Cowork only** for testing, the skill's Chat-mode warning kept for users |
| 2026-07-29 | Flat layout, repo **`legal-translation-skill`**, `.gitignore` **by path, not by extension**, 0 required approvals; **no credentials in the repo, ever**; **no third-party telemetry**, a **metadata-only** run report |
| 2026-07-30 | Grader **frozen at v3** until phase 3 ends; **thinking level** is a measurement parameter, held fixed |
| 2026-07-31 | **A name-based scan is not sufficient on its own**; **the register validator** runs around every edit |
| 2026-08-04 | **Quality first** *(§2.2)*; **frozen translated intermediates approved as local-only test fixtures** |
| 2026-08-05 | **eleven options: ten GO, the rebuild declined**; no shared library, no furniture file, **no cross-language parity check**; the sanctioned way out of a deadlocked gate, **its specification reviewed by Wouter first** |
| 2026-08-06 | This file rewritten to seven sections, **the build plan never restated in it**; **a test document named by instrument class and language only** — §5.6 — the qualifier list outside the repo |
| 2026-08-20 | **The private run-logging tier and monthly replay APPROVED as phase 5** *(§3.2)* — a **config overlay, never a third variant**, built only after publication, observable from commit one; its logs hold client text |

## 3. Plan of action — what is still to be done

> **This section owns the ORDER, the STATUS and the GATES, and nothing else** — `PLAN-2-step-b.md` owns the
> build's scope and sequence, §5 the rules, §6 the structure. **On what a step contains that document wins; on
> WHEN a phase happens this section wins**, undivided, because shared ownership let the previous plan drift.

**Future work only** — what is done is §2.3's.

> **DEFERRED — the commit messages carrying a forbidden phrase** *(Wouter, 2026-09-09)*: rewritten at the next
> force-push-class history operation, never before; `DECISIONS-LOG.md`, 2026-09-09 owns why.

### 3.1 The five phases

`NOT STARTED` · `IN PROGRESS` · `BLOCKED ON <what>` · `DONE`

| phase | what | status | blocked on |
|---|---|---|---|
| **1** | **Foundation: the repository** | **DONE, 2026-08-07** — PUBLIC, branch protection live with `enforce_admins` | — |
| **2** | **Building** (goals ii and iv) — steps 3 to 22 of `PLAN-2-step-b.md`, whose section 2 owns the order | **IN PROGRESS: 3–12 CLOSED · 13 DONE but for the runtime problem, open until phase 3's timing — five sub-steps, section 3.4 of the build plan · renames (c) and (d) next *(Wouter)* · 14's `quality_check` sub-step merged · 15–22 not begun** — history: `evidence/EVIDENCE-phase2-history.md` | nothing technical |
| **3** | **The full Cowork test, and its repairs** — every test document through Cowork, all recorded, each failure repaired here | **NOT STARTED**; its plan written when it starts | phase 2 |
| **4** | **Polish, then publish** — the skill's steps renumbered, smaller repairs, **Step D**, *then* repackaging and publication | **NOT STARTED** | phase 3 |
| **5** | **The private run-logging tier and its monthly analysis** — **a config overlay, never a third variant, never published** | **NOT STARTED**; its log FORMAT designed at step 22 | phase 4 — **built only after both skills publish** |

**Re-read this table's status at a session's open, not only §7's** — a row here once stood stale for seven days
*(2026-09-09)*. Phases 1 and 2 share the build plan's step numbering, phase 1 being steps 0–2.

### 3.2 The phases in detail — phase 2 is the live one

**`PLAN-2-step-b.md` is the leading document for phase 2** — its section 2 the order, section 3 the brief per
option, section 4 the test method. This section does not restate any of it and must never start to. Every
step runs Explore → Plan → Code → Verify → Test → Commit under §5.1–§5.2.

**Three sequencing facts are absolute** *(they are ORDER, which §3 owns)*: (1) the checks cannot be given
teeth before the scope rule and the sanctioned way out exist, or the pipeline deadlocks; (2) the
delivered-document check cannot be built before the tidy-up script journals its edits; (3) the formatting
work's second sub-step cannot begin before that check exists, and carries the off-flag removal in the same step.

#### Phase 3 — the full Cowork test, and its repairs
**Opus 5 is DROPPED** *(Wouter, 2026-10-13; `DECISIONS-LOG.md` owns it)*; `PLAN-3-opus5-migration.md` is
superseded. **After every step of phase 2:** every document through Cowork, all recorded, each failure repaired here; and one short document timed with no harness notes, the gear designed on it *(Wouter, 2026-10-19 (2))*.

#### Phase 4 — Polish, then publish
The skill's steps renumbered, as §6.3 allows, and smaller repairs; step 22 and the publish step are the build
plan's. **Never make a repo public or publish without Wouter's explicit OK** — the only irreversible act here.

#### Phase 5 — the private run-logging tier, and the monthly analysis
`DECISIONS-LOG.md`, 2026-08-20 owns it. **Its verbose logs contain client text**, so the sibling-folder rule and
the evidence guard apply; field list and scheduling are NOT decided; **track that the automation RAN**
(metadata, safe), never store what it **FOUND** (client text, ruled non-viable 2026-07-29).

#### Autonomy, and the two input points
**Exactly two input points** *(§5.4)*. Run translation and grading **as autonomously as possible**, no mid-run
questions — but **autonomy covers running and grading, never the collaboration rules on code:** every step still
gets explore, plan, a PR and a presented review before merge *(§5.2)*. Blocked mid-run, finish everything
independent of the answer, then ask once.

## 4. Tech stack

**Anything is acceptable as long as it works well as a skill in Claude Cowork** — the hard constraint, easy to
forget from a terminal: **most users will NOT be in Claude Code**, which is the development environment only.

**The skill's own stack:** `SKILL.md` plus progressive-disclosure Markdown, packaged as a `.skill`/`.zip` ·
**Python 3** for all 20 pipeline scripts, **`lxml` the only third-party import (7 of 20)** · **OOXML
manipulated as text**, the hard rules in §5.7 · lexicons and step documents split small · **`uv run`**.

**Dev-host toolchain, every element load-bearing — VERSIONS DELIBERATELY NOT LISTED: run the tool**, a typed
table having been measured wrong in four of seven rows. **ALWAYS `uv run python`, NEVER bare `python`, AND THE
PROJECT RUNS ON THE SIGNED SYSTEM PYTHON 3.14** — `.python-version` and `uv.toml` pin it *(Wouter, 2026-09-28 (4))*,
because this machine's security agent silently ends an UNSIGNED process that moves or renames a Word or email
file, and a run it ends can still look finished; the fixtures were rebuilt on 3.14, identical in content
*(register I-25)*. **Word (COM)** gives reference-fidelity `.doc → .docx`, the evidence baseline;
**LibreOffice** the user-reality conversion and `docx → pdf`; `pandoc` the grader's `docx → markdown`;
**PyMuPDF** the `pdf → png` render.

**NO PYTHON PROCESS MAY MOVE OR RENAME A WORD, EMAIL OR PDF FILE** *(Wouter, 2026-09-28 (4))* — never
`os.replace`, `os.rename`, `shutil.move` or `Path.rename`/`replace`: build it in memory and write it once, after
every check has passed. `tests/test_no_document_moves.py` refuses every move call in tracked Python.

**The rendered visual diff is the highest-yield defect detector, on this host** *(§2.4 item 4)* — Word converts
legacy `.doc` for evidence, LibreOffice for user reality, and the comparison between the two IS the test.

## 5. Working method and rules

### 5.1 The cycle — Explore → Plan → Code → Verify → Test → Commit

**The six stages are the house file's, which auto-loads here, and are not restated.** What **this project** adds:

| | what THIS PROJECT adds to the stage |
|---|---|
| **Explore** | the brief in **section 3 of `PLAN-2-step-b.md`**, **the register rows behind it** (its section 9.3 maps them) and **what the brief POINTS AT** *(`EVIDENCE-measurement.md` 3.8)* |
| **Plan** | what it builds, must not do and counts as done: all in the build plan's section 3, **never your own** |
| **Verify** | that section's *Done when* — the byte comparison, a negative input per new check, the acceptance test |
| **Test** | section 4 of the build plan for the step's kind, plus the smoke suite, parity check and any graded run |
| **Commit** | §5.2, both halves — the step-and-PR rules and the definition of done |

#### The cycle must produce ARTEFACTS, not intentions

**The step-list rule is the house file's, and this project enforces it mechanically:** `tools/cycle_evidence.py`
binds a passing verify and test to a hash of the working tree's diff, and the pre-commit hook refuses a commit
with no matching evidence — proving a command ran and exited zero, never that it was a good one.

**RUN, DO NOT READ** *(the house file's* re-measure, do not re-read; **§5.3 cites this wording)*.
**The failure shape with no house twin: a check that passes for the WRONG REASON** — never a two-word needle,
ask the same question a second way, and a figure agreeing with the one you expected is the moment to
re-derive it *(the eleven instances: `EVIDENCE-measurement.md` 3.3 and 3.5)*. **Two disciplines bind every
option:** every change points at a specific observed failure or grade, never at theory; and the anti-drift
safeguards are not on the table.

### 5.2 Branches, pull requests, and what "done" means

#### Branches, pull requests and commits

- **The house commit-flow rule governs, but NOT while branch protection stands**, which rejects a direct push
  to `main` with `GH006` even for an admin. **So: a PR per branch, the diff and the `/code-review` findings
  shown, and Claude squash-merges once VERIFY, TEST and the review are green** *(Wouter, 2026-10-14 (2))*.
- **Stacked branches: merge bottom-up, and never delete a base branch while anything sits on it**
  *(2026-08-07, cost a PR)* — deleting base A CLOSES branch B, and a closed PR cannot be retargeted. Prefer
  branching from `main`; a rebuilt branch carries no old evidence, so re-run the full check set.
- **Branch protection on `main` is LIVE, `enforce_admins` TRUE, required approvals 0** (0 or GitHub refuses
  to let Wouter merge his own PR). It stops the accident, not the decision — **no GitHub setting can make
  Claude ask permission**, because it runs under Wouter's own account.
- **`README.md` is the public front door on two public repos** — update it in the same PR as any change to
  behaviour, the feature list or installation.
- **Debug a regression with `git bisect`**, against the smoke suite or the fixture byte-comparison, never
  "translate and grade" (not deterministic).

#### Definition of done — every step, every phase

**The house definition of done applies in full.** The gates THIS charter adds: the parity check green · the
step's *Done when* in section 3 of `PLAN-2-step-b.md` met, tested by its section 4's method · no criterion
regressed against the frozen v3 baseline where a graded run applies · a rendered PDF diff of BOTH documents,
page by page · all three confidentiality controls run *(§5.6)*.

### 5.3 VERIFY — proving this change did what it claimed

#### "IT EXITED 0" IS NOT "IT DID THE WORK" — and this section is here because §7 gets replaced

**The house file's hygiene rules apply; the five with no twin — each a check that passed HERE for the wrong
reason — load from `.claude/rules/verification.md`** with `tools/**` and `tests/**`, their worked examples in
`EVIDENCE-measurement.md` section 3.

#### The checker roster — what this project keeps, and why it dropped the rest

**`check_checkers.py` PRINTS the roster and the verdict on every run, so NO FIGURE IS TYPED HERE**; each declared
absence carries its reason in `verify.config.json`, blank refused. **What that verdict cannot hold:**
`install_project_hooks.py` is this project's own; **most of `tools/` is PROJECT-SPECIFIC** — OOXML, the corpus,
the register, leakage, parity, the Step-B audits; and **`xref_check.py` is a deliberate TWIN**, green where the
house `verify_refs` misfires over files whose content IS quoted terminology.

#### The audit gate — for any analysis deliverable
**Wouter's standing requirement — *"triple check, do a deep audit and verify your summary"* — triggers the
`audit-gate` skill: invoke it, do not improvise.** It has found real errors every time, and an audit reporting
NOTHING was too shallow. The register's validator is `uv run python tools/audit_register.py`.

#### Never-regress — the rule, and how it becomes enforceable

**Wouter's hard rule: quality must only IMPROVE, never go lower.** Grading is manual and non-deterministic, so
two tiers make it real: **(1) a scripted mechanical gate on every change** — the deterministic measures of
`EVIDENCE-measurement.md` section 3.7, which make `git bisect` possible — and **(2) a full LLM re-grade only at
step boundaries**, on a fixed subset, against the frozen v3 baselines. **Efficiency is strictly subordinate:**
*"make it faster"* must never become *"read less"*, and fixing the defects IS the efficiency work.

### 5.4 TEST — proving nothing else broke

#### How a change is actually tested
**Invoke the `frozen-intermediate-test` skill for the method**; section 4 of `PLAN-2-step-b.md` owns it per step
kind. **Binding outside a test run:** synthetic fixtures in `tests/fixtures/` are committable, frozen
intermediates NEVER *(§5.6, §6.4)*; a frozen-intermediate result is evidence about the MECHANICAL half only; and
a change claimed non-behavioural is PROVED byte-for-byte or not claimed, which is what makes `git bisect` work.

#### The review protocol — for INPUT POINT 2
**For INPUT POINT 2, the `input-point-2-review` skill. Invoke it, do not improvise.** Binding outside a review:
**there are exactly two input points** — 1 CLOSED 2026-07-31, 2 phase 3's documents — and **Wouter forms his
view before reading the grade**, so Claude never summarises or hints at findings first, and **any tool touching
a blind review inherits the blindness.**

### 5.5 The instruments

#### The measuring instruments
**Properties of the measurement, not the skill: state them wherever numbers appear, and never vary one inside a
comparison.** The measurement rules load from `.claude/rules/instruments.md` (route 4) and their cost stories are
`EVIDENCE-measurement.md` section 3's; **the STATE stays here:**

| instrument | state | the rule |
|---|---|---|
| **Grader** | **v3, FROZEN** until phase 3 ends | **never change it sooner** — a moving ruler breaks never-regress |
| **Harness** | **v2.2** (two v1, one v2, one v2.1) | re-run, gate, iteration counts NOT comparable across versions |
| **Thinking** | **`extra`** on all 12 (`low` < `high` < `extra` < `max`) | `max` never used, so A1 grades are floors |
| **Batch or single** | two docs batch-run, one has both | reproduce it, or a before/after is not like-for-like |

**The grader is v3 with 17 criteria;** `EVIDENCE-measurement.md` section 2 owns its package, its three gaps
and why a pairwise comparison reports sixteen. Its bash paths are Cowork container paths; substitute local.

#### The test corpus
**The twelve-row listing is in `EVIDENCE-measurement.md` section 1.** Eleven real client documents live
outside the repo tree, permanently, named **by instrument class and language only, per §5.6**.

- **D03, Agreement (Norwegian), is the only language with NO sub-lexicon** — the sole evidence for §2.1's
  *"others translate very well too"*, D03/D03B the most controlled pair; **D09 is no longer an arm document**.
- **Variant assignment is 3 US / 8 UK, not arbitrary:** the hard technical paths run on UK, so a failure is
  unambiguously a pipeline defect; US takes the terminologically rich, so divergence is what gets tested.
- **The two reasons a corpus cannot reach a defect, and the three shapes needing synthetic fixtures, are in
  `.claude/rules/instruments.md`** — the general lesson is §5.1's: 100% over one document is not 100%.

### 5.6 Confidentiality
**The dated evidence is in `EVIDENCE-confidentiality.md`; NOT ONE RULE MOVED WITH IT, AND NONE MAY** — a
confidentiality rule absent when needed is a publication that cannot be undone, so this is **route 1: not one
line of this section may become a path-scoped rule or a skill.** Read that document before touching a control.

**The repository has been PUBLIC since 2026-08-07 and the skill is published publicly, so its whole history
is served: treat every file as world-readable from the moment it is committed — a commit cannot be
un-published.** **No confidential or sensitive business data in the skill, the repo or the commit history,
and that includes examples.**

- **No client or counterparty names, ever** — not in step docs, lexicons, script comments, fixtures, commit
  messages, any committed log, or this file. **The scan list lives in the private sibling folder, outside the
  tree rather than merely gitignored**, because a client name cannot be rotated once published; the scanner
  reads it by path or environment variable. **Keep the list current.**
- **No real-document examples — every worked example, fixture and XML snippet must be SYNTHETIC.**
  Anonymising still leaks the shape, clause structure and commercial terms, so **renaming is not enough**:
  keep the lesson, discard the document. Replacing the known real-derived step-doc examples is part of phase 2.
- **NAME A TEST DOCUMENT BY ITS INSTRUMENT CLASS AND ITS LANGUAGE, AND BY NOTHING ELSE** *(Wouter)* —
  Agreement (Norwegian), Power of Attorney (Hungarian), Guarantee (Polish), Deed (Italian), MOU (Japanese).
  **Never say what the instrument is about:** a subject-matter qualifier plus a language plus a date range
  identifies a real instrument more sharply than a name, and a name-based scan is STRUCTURALLY BLIND to it.
  The qualifiers are NOT listed here, deliberately — they live with the scan list in the private folder.
- **The same rule covers clause content:** say what a lost span *did* (*"an operative condition"*), never
  what it said. What stays, being evidence and not sensitive, is the FILE's technical character — no
  sub-lexicon, legacy `.doc`, non-Latin script, tables, bold-run and paragraph counts, batch position,
  tracked-change load — never the deal; the doc-id → real-document mapping is in the private folder.
- **THE LOCATION RULE, a rule about place rather than a judgement about content:** raw forensic logs, the
  test corpus, Wouter's review feedback and the frozen intermediates live **entirely outside the repo**, in
  the sibling folders named in §6.4, and **only the *derived* work is committed.** Nothing depends on
  classifying each line correctly, and the raw log can then be maximally detailed, never being published.
- **The test corpus filenames alone carry counterparty names**, so they are as unpublishable as the contents
  — never copy one into the repo, name one in a commit message, or paste an excerpt into a public artefact.
- **The run report DOES ship, so it is metadata-only by construction** — counts and durations, never document
  text and never filenames. **AND IT IS THE ONLY EGRESS THERE IS: the skill authenticates against nothing and
  makes no network call** — measured 2026-09-10, **0 network, auth or credential imports across the 40
  shipped scripts**, control fired.
- **A COMMENT SHIPS, AND AN EXAMPLE IN A DOCSTRING IS PUBLISHED PROSE. Invent the examples.** Three scripts
  intended for `tools/` were caught this way — `EVIDENCE-confidentiality.md` section 4.
- **A PROBE CANNOT SEE WHAT A SCRIPT REVEALS ABOUT THE CONTROL.** §6.4's never-commit list is a floor and not
  a ceiling: read a script and ask what it discloses about *which candidates get waved through*, not only
  what strings it holds.

> **One leak class no control can reach — THE TRANSCRIPT.** Every control here reads committed content, and
> session metadata reaches neither the scanners nor the location rule, so there is no after-the-fact remedy
> *(it has happened — `EVIDENCE-confidentiality.md` section 2)*. **So the control runs BEFORE the command:**
> `tools/hooks/evidence_guard.py`, a PreToolUse hook, blocks a name-emitting command (`ls`, `find`, `cat`,
> `Get-ChildItem`, inline enumeration) aimed at an evidence folder. **The hazard is OUTPUT, not access:**
> `tools/evidence_ls.py` is the sanctioned way to see a folder's shape, printing no name — a block with no
> alternative gets worked around.
>
> **A rendered page of a corpus document is client text as an image, so Claude may never look at one.** Real
> corpus is compared MECHANICALLY, every image deleted; synthetic fixtures may be viewed; **a page-by-page
> read of a real document is Wouter's alone** *(the tool `render_diff.py` keeps a pointer)*.
>
> **Two limits:** hooks load at SESSION START, so this one never protects the session that adds it *(probe it
> with a command naming a non-existent directory under an evidence folder)*; and the test-document folder is
> read from gitignored `.claude/evidence-dirs.local`, so in a fresh clone it is unguarded until that file
> exists.

**Three controls, all run on every committable file before any commit, and EACH MUST REPORT WHAT IT READ** —
a clean report from a control that could not reach the file is not a pass *(both list-readers were once blind
to `.claude/`)*. **`tools/leakage_scan.py`**, the name-and-term scan, 93 patterns, **exits 2 when the list is
unreadable**, so the pattern count is the proof it ran; it is not sufficient alone, being silent on
commercial terms and subject-matter qualifiers, which must be **genericised** (*"the seven-figure guaranteed
amount"*). **`tools/descriptor_shape_sweep.py`**, the list-free shape sweep, so it can find a qualifier
nobody listed; everything it prints is a candidate for judgement. **`tools/publication_check.py`**, which
asserts the forbidden classes and fails rather than listing, and **once suppressed a real finding, so every
pattern needs a test vector beside it.**

**Two list-maintenance rules:** use `\s+` for every space in a multi-word pattern, never a literal space (a
single space silently failed against a doubled one, and a missed name reports clean); and every pattern is
tested against the string it was written for, in the same commit (`'\bName\b'` non-raw is
BACKSPACE+Name+BACKSPACE). **Which files may never be committed is decided not by *"is it a script?"* but
*"does it hold one real string per pattern?"*** — the four are in §6.4 (route 1); the 90-script census is
`EVIDENCE-confidentiality.md` section 4. **One item is still open:** the scan list needs tightening before it
is a trusted pre-commit gate *(`EVIDENCE-confidentiality.md` 5.2)*. **`.gitignore` prevents accident, not
exposure** — making a repo public exposes the entire history and a leaked client name cannot be rotated,
which is why the location rules outweigh any cleanup.

### 5.7 The artefact — domain rules and deliverable conventions

#### Gate philosophy and error handling — do not weaken this
**A gate firing is the script doing its job — fix the input and re-run, never the gate.** The other gate rules
load from `.claude/rules/gates.md` with the variant trees and the tools: working around a gate is reversible,
so they may sit behind a glob where §5.6 may not.

#### OOXML hard rules — all confirmed in production
**The ten OOXML rules are in `.claude/rules/ooxml.md`** *(route 4 not route 1: forgetting one produces a file
Word rejects, which is reversible)*; §6.5 lists this project's scoped rules.

#### Skill-authoring conventions
**Five of the seven are in `.claude/rules/skill-authoring.md`**, each with an unconditional twin here
*(§2.4, §6.3, §2.5, §3.2)*. **The two that did NOT move and must not** — route 1, forgetting either publishes
client names into a distributed archive: **no changelog inside the archive, ever** (the packaged `.skill` has
zero changelog entries, and the rev16→rev44 history stays outside the repository, §5.6(c)); and **no
confidential data and no real-document examples** (§5.6).

### 5.8 Working with this charter, and the session

#### Adding to this file
**The house file's mechanism for adding to a charter applies and is not restated. The five this project adds:**

1. **No cap is stated in this file** — `verify.config.json` alone gates, in the unit its `line_measure` names,
   and `tools/verify_charter_continuity.py` checks any length this file does state against the measurement.
2. **A skill's body is not in context until invoked, and neither a skill nor a scoped rule can be exercised in
   the session that creates it** — so nothing whose absence is irreversible goes behind either: **§5.6 and §6.4
   are route 1 entire**, asserted by `verify_charter_continuity.py` check 6b.
3. **Prefer a relationship to a number** — *"§7 is under its cap"* cannot go stale, *"§7 is 18 lines"* can —
   and where a number must be written, **state its unit**.
4. **Where this charter and a companion document disagree, this one wins** — a defect to fix, never a
   judgement call; §1.3 says what each owns, and `tools/xdoc_signs.py` judges a `§` aimed at another document.
5. **After any substantial edit, run** `verify_md.py`, `verify_charter_continuity.py`, `xdoc_signs.py`,
   `md_tables.py` and **all three confidentiality controls** (§5.6), and invoke the `audit-gate` skill.

#### Inherited house rules

**The house file's four critical rules apply; the rider they lack: the archived `.skill` revisions and the test
corpus are irreplaceable**, which *"never delete files you didn't create"* does not say.

## 6. File, folder & repo structure

### 6.1 The design principle, and what it is not

Goal: a structure **optimised for the context window** — small files, few loaded at once, the right file at the
right step. **Do NOT reduce the file count for its own sake:** 154 small sub-lexicons and eight step documents
rather than monoliths is deliberate, and **A3 confirmed it correct in principle.** **Eleven structural questions
were open until A3 settled them; do not re-open them** — `EVIDENCE-a3-structure.md` sections 0 and 5.

### 6.2 The skill tree today

**Latest published version: `v2026.04.22-rev44`** (13 May 2026), 198 files, 20 scripts per variant — a token kept
here because it is nowhere else in the repository. The per-file byte table was CUT 2026-08-24 (derivable, and it
had drifted); `EVIDENCE-a3-structure.md` holds the byte figures; the 55,466-byte truncation finding is register row W1.

### 6.3 What the build changes — the envisaged tree

**Standing constraints on anyone tempted to reorganise:** the tree keeps its shape — no new directory, no
reorganisation, **NO RENUMBERING of the eleven steps** before phase 4 (a renumber breaks every skill-step id in
the forensic logs). **The tree may hold 199 files, is at 198, and the one remaining slot is spoken for**
*(Wouter, 2026-09-10)* — a Cowork skill over 200 files will not install, and step 22's manifest is the committed
+1, so another step wanting a file must free one (§6.1 forbids the easy trims).

### 6.4 The repository — what it holds, what never enters it, and what ships from it

#### The repository — CREATED 2026-08-06, PUBLIC SINCE 2026-08-07

**One monorepo, both full trees side by side, no build step, plus an automated parity check** —
**`github.com/wjvandenberg/legal-translation-skill`**, distinct from the two public distribution repos.
Making a repo public exposes **the whole history, not the current state** *(§5.6; the creation and
flip records are `DECISIONS-LOG.md`'s, 2026-08-06 and 2026-08-07)*.

> **FOUR SCRIPTS MAY NEVER BE COMMITTED, and this stays because forgetting it is irreversible.**
> `confidentiality_sweep.py`, `corpus_descriptor_scan.py` and `confidentiality_review.py` live outside the
> repo and the gate calls them by path; **`temp/audit_session_stepb.py` holds two corpus descriptors and
> stays in gitignored `temp/` permanently.** The rule that decides all four is §5.6's — *does this
> file hold one real string per pattern?* — **the scanner ships, the list never does.** *(No `docs/history/`
> either.)*

**The load-bearing property: `uk/` IS the publishable tree** — what you see is what ships, and **`tools/` and
`tests/` are siblings of the variant trees, never inside them**, so nothing development-only can leak into a
shipped skill. **`.gitignore` is BY PATH, never by extension** — a blanket `*.docx` blocks the synthetic
fixtures and does nothing about a renamed client document.

**The duplication is deliberate and its removal is DEFERRED** until the reconciliation classifies the
618-pair residue — one PR touches both trees, so a fix cannot land in one variant and be forgotten
*(`DECISIONS-LOG.md`, 2026-09-11)*.

#### What never enters the repository

**FOUR sibling folders, outside the repo tree — not merely gitignored.** *(It said THREE until 2026-09-10, one line above a table of four — counted by LISTING them, which is the only thing that catches it.)*

| folder | what is in it | why it can never be committed |
|---|---|---|
| **the private folder** | `context.md` (the real paths, the employer, the corpus composition this public file generalises) · `leakage-names.txt` · **`corpus-descriptors.txt`** · the grader backups · the harness and its changelog · the `claude-md-archive` · the whole A4 set and its twelve tools · the shared tooling | it holds the two scan lists and the material they exist to protect |
| **the logs folder** | the raw A1 forensic logs · the grade reports · the narratives · the renders · Wouter's review feedback · **and the frozen intermediates** | every one of them quotes real client text. The frozen intermediates are the most content-rich files the project has ever produced |
| **the test-document folder** | the 11-document corpus, pristine | **the filenames alone carry counterparty names** |
| **the archived `.skill` revisions** | every packaged revision, and **the rev16→rev44 changelog carried inside them** | the changelog names real documents and parties — measured, §5.6(c). An input to the analysis and the build plan; **not a deliverable** |

**And one more, outside all of them:** the two rev44 `.skill` archives, the code baseline and the blind
review's only reading material.

**A working folder shared between sessions accumulates unrelated matter** — two client documents from an
unrelated matter once appeared in an evidence folder, and a session title once carried a real counterparty
name. **Session metadata is reachable by neither scanner nor the location rule**, so any glob over an
evidence folder must be explicit about which files it expects.

#### Publishing from the monorepo

**MOVED TO `.claude/skills/publish-skill-archives/SKILL.md` ON 2026-08-24** (route 3). **It is a
SPECIFICATION, not a runbook: `tools/package.py` and `tools/publish.py` DO NOT EXIST** — checked by listing,
and **building them is §3.2's phase-4 block's**, not phase 2's.

**What stays, because it binds outside a release:** the deliverable is **two independent `.skill` archives of
198-odd files each, no build step**, uploaded and installed separately; and **three public repos will exist**
— `legal-translation-skill` is the **source**, the two variant repos the **install channels**, and **every
README must say which is which.** *(§3.2's phase-4 block owns the one irreversible act: never publish without
Wouter's explicit OK.)*

### 6.5 `.claude/rules/` — the path-scoped rules this project has

**FIVE** — listed from `.claude/rules/`, never from a count; each loads by the `paths:` block at its line 1.

| file | what it holds | its charter twin |
| --- | --- | --- |
| **`ooxml.md`** | the ten OOXML hard rules, each a production incident | §5.7 |
| **`skill-authoring.md`** | five of the seven skill-authoring conventions | §5.7 |
| **`instruments.md`** | the seven measurement rules, forensic logging, the corpus-blind-spot reasons | §5.5 |
| **`verification.md`** | the five ways a check passes here for the WRONG reason | §5.3 |
| **`gates.md`** | the five gate-philosophy and error-handling rules | §5.7 |

**The route-1 rules never move here** — §5.6 entire, and the two §5.7 keeps for that reason.

## 7. Current status

> **The handoff and nothing else** — done is §2.3, left is §3, method is §5. **REPLACED every session,
> never appended to; fold anything durable into §1–§6 first** *(§5.8; the cap is in `verify.config.json`)*.

### HANDOFF — 2026-10-20 (3), I-43 FILED, 13.5 BUILT, STEP 13 DONE BUT FOR THE RUNTIME PROBLEM

**PURPOSE: MET.** It was *so that the four silent reds are on the record beside the guard that ends them, and every
part of a delivered document declares the target English instead of the source language*: #163 filed register
I-43; #164 sets the language in every part the delivery holds and closes R2.

**BUILT:** #163 — I-43, re-measured in a scratch worktree, and the eight stale charter numbers #74 left in seven
places mended. #164 — `repack_docx.py` both trees; its suite 25 of 89 red on main, 89 after; on the 13, uk 7 of 11
delivered workdirs moved, us 6 of 9, nothing else. Rulings and judgements: `DECISIONS-LOG.md`, 2026-10-20 (3).

**SINGLE NEXT ACTION: RENAME (c), THE REGISTER**, with check 2's vacuity filed as its row *(Wouter: the 2026-10-19
entry's rulings (6) and (7), confirmed 2026-10-20 (3))*; then (d), the rest; then step 14's remainder.

**WHAT A NEW SESSION WOULD GET WRONG:** per pull request only its own acceptance check, the three confidentiality
controls and the covering suites; the base list, the twelve-tool comparison and the ~40-minute full runner ONCE, at
the end *(Wouter)*; the corpus arm's 13.5 pin is `8ad07c3`; "the glossary" means all its parts *(Wouter, kept)*.

**Open, none blocking:** the charter-pointer checker built here, `tests/test_charter_pointers.py`, the house's
version Wouter's to plan; the house runner's suite-coverage arm; `SKILL.md`'s size, goal (iv)'s. **Context: 59% when written, measured.**
