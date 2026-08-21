# CLAUDE.md — legal-translation

A **Claude skill** that translates legal documents from any language into publication-ready English while
preserving `.docx` formatting completely. Hand it a Word file in any language; get back an English `.docx`
you could sign as a stand-alone legal document — formatting, tracked changes, headers/footers/footnotes/
comments, and alphabetically reordered definitions all intact. Quality target: **magic-circle law firm**, in
translation *and* formatting; notably better than DeepL-class tooling. Two published variants: **UK English**
(default) and **US English**.

**This project is the update, and possibly the partial rebuild, of that skill.** The original was built in
Cowork, before Claude Code, without version control or an up-front structural plan.

> **STATE, 2026-08-07.** **All the looking is finished and all the deciding is done.** Step A (five strands
> plus the comparison) and Step B (eleven options, ten approved, the rebuild declined) are complete and
> separately audited. **Nothing in the plan is awaiting a decision.** **Step 1 is finished: the repository
> exists, it is PUBLIC, branch protection is live, and branches 0, 1 and 2 are merged** — so the project now
> has version control, a test harness and a parity check. **Ten lines of skill file have been modified —
> that is ADDED LINES ACROSS BOTH TREES, in two files per tree: five added and four removed each side** —
> deliberately, to remove real-document material from the two published trees. *(The basis was implicit
> until 2026-08-18, when an audit re-derived the figure, assumed it meant per-tree, measured four and
> reported it as a failure. Ten is right under exactly one of six natural readings and four of the six
> give a different number, so the unit is now stated. A count whose unit is implicit is a count the next
> session re-derives differently.)* The next action is in §7.
>
> **This file was rewritten on 2026-08-06** to the seven-section structure below, after a claims check found
> 35 factual errors in the previous version — almost all of them counts and statuses that the work had moved
> past. `OPUS-5-MIGRATION.md` and `DECISIONS-LOG.md` were split out of it in the same pass. The previous
> version is at `temp/CLAUDE.md.pre-overhaul`.

---

## 1. How to read this document

### 1.1 How to talk to me — read this before answering anything

Wouter is not a professional developer; his background is legal and contract review. **Explain things in
plain, layman's terms by default, and teach the technical vocabulary along the way.** When you first use a
term like *OOXML, run, glyph, ZWSP, monorepo, variant build, fixture, smoke test, squash-merge, progressive
disclosure, token budget*, define it in one plain sentence. Assume the concept is new unless he has used it
himself. Favour analogies over jargon. It is fine to be technical *after* the term has been introduced once.

**Number your questions.** Whenever you ask more than one, present them as a **numbered list (1, 2, 3…)**,
never bullets, so he can answer by number and refer back.

### 1.2 What this file is, and what it is not

**It is the charter:** what the project is, what is left to do, how the work gets done, where everything
lives, and where the project stands today. **It is public from commit one** — every edit to it is an edit to
a document strangers will read.

**It is not the evidence, not the build plan and not the history.** Those are three other files, and this
one points at them rather than summarising them. That division is deliberate: the last time this file
carried a summary of the evidence, a session reasoned from the summary instead of the evidence and reached a
wrong conclusion.

### 1.3 The document set — what to read for what

| file | what it is | when you need it | it owns |
|---|---|---|---|
| **`CLAUDE.md`** *(this)* | the charter | first, always | goals · order · status · rules · structure |
| **`STEP-B-ANALYSIS.md`** | **the build plan.** What to build, in what order, and what counts as having built it | **before and during every build branch — it is the leading document for all of step 2** | §2 the order · §3 the brief per option · §4 the test method |
| **`FINDINGS-REGISTER.md`** | the evidence base — **215 rows**, every finding with its per-document proof. **The fastest way to understand what the project has learned** | whenever you need the proof behind any claim | every finding, clustered by root cause |
| **`A3-STRUCTURAL-ANALYSIS.md`** | the evidence-led structural analysis | when a structural judgement comes up | the measurements: context, runtime, redundancy, divergence |
| **`OPUS-5-MIGRATION.md`** | goal (iii) and the verification run that follows it | at step 3, not before | the Opus 5 branches and Step C's design |
| **`DECISIONS-LOG.md`** | the dated record of what was decided and why | when tempted to re-open something settled | the reasoning behind closed questions |
| **the private sibling folder** | `context.md` (real paths, employer, corpus composition), `leakage-names.txt`, the whole A4 set, the grader backups, the harness | before anything touching confidentiality, packaging or publication | **never committable** |

**Three of these are live inputs to the work ahead — the build plan, the register and the structural
analysis. The rest are reference.** The A4 blind desk review's own 2,222-line report is the primary artefact
of that strand and lives in the sealed judging directory outside the repository; its path is in the private
`context.md`.

### 1.4 Reading order for a new session

1. **§7 — current status.** Two minutes. It is the handoff and nothing else.
2. **§3 — plan of action.** What happens next and what it waits on.
3. Then, by task: **building** → `STEP-B-ANALYSIS.md` §2, then §3, then §4, in that order · **a question
   about the evidence** → `FINDINGS-REGISTER.md` · **how the work is done** → §5 here.

### 1.5 Two rules about reading, both bought with real time

- **NEVER WORK FROM A PRÉCIS — including this file's.** A session once predicted which defects the blind
  review had found uniquely, reasoning from this file's summary of the register rather than from the
  register; one search settled it and the prediction was wrong. Step B then broke the same rule against the
  blind review's report, and reading the report properly produced **six items nothing else carried**. If a
  claim matters, open the file it came from.
- **RE-MEASURE, DO NOT RE-READ.** Every audit this project has run has found real errors, and none of them
  would have been caught by reading more carefully. See §5.12.

### 1.6 Contents

| § | section | what it covers |
|---|---|---|
| **1** | How to read this document | communication · the document set · reading order |
| **2** | Project overview | the skill · the four goals · what has been done · what the evidence says · the decisions that still bind |
| **3** | Plan of action | **only what is still to be done** — five steps, in order, with their gates |
| **4** | Tech stack | the runtime constraint, the skill's own stack, the dev-host toolchain |
| **5** | Working method and rules | the build cycle · branches and PRs · confidentiality · never-regress · the instruments · testing · gates · OOXML · the audit gate |
| **6** | File, folder & repo structure | the skill tree today · what the build changes · the repository, now and after |
| **7** | Current status | the handoff, and nothing else |

---

## 2. Project overview

### 2.1 What the skill is, and who needs it

**Who has the problem.** Lawyers and deal teams who receive a legal document in a language they do not work
in and need it in English — not a gist, but a document they can read, mark up, negotiate and in principle
sign. The author's own **in-house energy practice** is the driving use case (cross-border wind and energy
transactions, sources in Dutch, Italian, Spanish, Norwegian, Finnish, Polish, Hungarian and Japanese), but
the skill is published for anyone with the same problem.

**The problem.** Machine translation (DeepL, Legora, Google) gets the words roughly right and the *document*
wrong. It uses everyday-English or calqued renderings where English legal drafting has a settled term of
art, and is inconsistent within one document; it destroys `.docx` structure — numbering, styles, tables,
signature blocks, headers, footers, footnotes and comments; it cannot handle **tracked changes** (what does
the document say if you accept? if you reject?); it leaves definitions in source-language alphabetical
order, which is not alphabetical in English; and it gives no way to tell whether the output is complete and
faithful.

**How the skill solves it.** An **eleven-step pipeline** that never rewrites the document from scratch. It
extracts every paragraph out of the original `document.xml`, translates them in small batches under a
two-layer lexicon (cross-language English references plus per-language sub-lexicons), then **text-matches**
the English back onto the *original* XML — replacing only run content, leaving styles, numbering and
structure untouched. **That last property is the golden rule and it is measured to work:** zero style or
numbering mismatches on every tested document. Every failure in the register sits in the run-level layer
*beneath* it. Quality gates fire at every stage; definitions are reordered alphabetically in English;
auxiliary XML parts get translated too.

**Distinctive features — this is the published feature list. Keep it true.**

- Built-in **English general lexicons** (15 domain references) plus **per-language sub-lexicons** covering
  M&A, IP, IT/SaaS, finance, tax, litigation, employment and more. Full sub-lexicon coverage for **11
  languages**; others translate very well too.
- **Tracked changes read correctly when accepted *and* when rejected**; orthographic-only typo pairs
  collapsed.
- **Definitions reordered alphabetically.**
- **Headers, footers, footnotes and comments translated.**
- **UK English by default, US English on request** (two variants).
- **Quality gates throughout.**
- Deliberately **slower and larger** than a simple translate-this skill — minutes, not seconds.

> **Two of these claims now have measured evidence.** *"Others translate very well too"* — the only corpus
> document whose language has no sub-lexicon scored **9 on terminology with zero calques, on two independent
> runs**. *"Minutes, not seconds"* — **18 to 50 minutes** across twelve runs (measured 17.8 to 49.6),
> scaling with paragraph count rather than page count.
>
> **And six of them are read more generously than they deserve — see §2.5, point 6.** Fixing the claim is
> part of the build, not a tidy-up afterwards.

**Distribution — this is a public skill.** Both variants are published on **GitHub** and on **lawve.ai**.
Everything about the structure, the examples and the packaging must be written on the assumption that
**strangers will read every file.** See §5.4 — a hard constraint, not a polish step.

**Out of scope, but on the horizon.** A **reverse skill** (English → each of the 11 languages) is likely at
some point. It is **not part of this project or these repositories.** If a lexicon or reference file can be
made direction-neutral at no cost, that is a free option — but **do not design for it, do not add scope for
it, and do not compromise this skill's quality for it.**

### 2.2 What this project is — the four goals

Not a feature-add project. Four goals, in priority order, with where each now stands:

| | goal | where it stands |
|---|---|---|
| **(i)** | **Deep structural review.** Analyse the scaffolding and file structure for redundancy and for anything that can be restructured *in order to get better translations* | **Delivered.** Step A answered it: `A3-STRUCTURAL-ANALYSIS.md`, all eleven structural questions settled (§6.2), and the redundancy and runtime measured for the first time |
| **(ii)** | **Close out the known quality and formatting defects** — bold formatting, signature blocks and layout, tracked changes. Likely **structural**, not cosmetic, which is why (ii) is entangled with (i) | **Scoped and planned, not built.** All three turned out to be classes rather than defects (§2.5). The plan is `STEP-B-ANALYSIS.md`; the work is step 2 |
| **(iii)** | **Make the skill Opus 5-ready.** Expected to be a *small* change set. **Do not touch the anti-drift and anti-deviation safeguards in the name of Opus 5** | **Designed, not started.** One item already closed on evidence (the batch cap stays). `OPUS-5-MIGRATION.md`; the work is step 3 |
| **(iv)** | **Minimise install-truncation risk and repair its detection.** A truncated install silently degrades every translation the *user* produces — a distribution-reliability goal, not a cosmetic one | **Scoped, and it is two pieces of work rather than one.** The size discipline *lapsed*; the coverage was **never built**. Only the first is a regression. Carried by Step B's options 8 and 9 |

**The decision criterion that governs all four, and every option under them:**

> **QUALITY IS THE MAIN DRIVER. SPEED MATTERS, BUT LESS — AND SPEED MUST NEVER COMPROMISE QUALITY.**
> *(Wouter, 2026-08-04.)* The **25 minutes of fixed overhead** is a real cost and worth attacking, **but not
> by reading fewer lexicons, not by raising the 35-paragraph cap, and not by thinning a gate.** The evidence
> says all three of those would cost quality.

### 2.3 What has been done

**Do not re-open any of it.** The detail lives in the files named, not here.

| | what it was | what it produced |
|---|---|---|
| **Step 0** — decisions | the up-front choices and the toolchain | monorepo layout · `.gitignore` by path · branch protection · grader validated and frozen at v3 · corpus probed and the 3 US / 8 UK split chosen · toolchain installed and verified · Claude Code / Cowork equivalence checked |
| **A1** — the forensic runs | all 11 corpus documents plus a controlled batch arm, translated under a harness and logged exhaustively | 12 runs · grades 8.4–9.3 · the runtime and behaviour measurements everything since rests on |
| **A2** — grading | all 12 graded against the frozen v3 rubric | the never-regress baselines |
| **Wouter's review** | he read all 12 in Word, blind, one at a time | **INPUT POINT 1, closed.** Findings triaged three ways and folded into the register |
| **A3** — the structural analysis | evidence-led: what the corpus exercised | six keystones priced against each other · context, runtime and redundancy measured · all eleven structural questions answered · deep audit, 108 checks, 0 failures |
| **A4** — the blind desk review | the same artefact judged from outside by a reader who had seen no test result, no grade and no prior analysis, against eleven criteria frozen before anyone looked | a report of **2,222 lines** with **454 `file:line` citations** · 25 new findings · and the finding no amount of running the pipeline could have surfaced |
| **the A3↔A4 comparison** | all thirteen steps, with a 20% spot-check that **failed one of its two pairs and changed the result** | a new cluster **X** — the legibility gap · a correction to A3 · a coverage matrix naming what *neither* method reached |
| **Step B** — the fix exploration | eleven options, four-columned and ranked, three verification passes by three different methods, five audits | **`STEP-B-ANALYSIS.md`** — ten options approved, the rebuild declined, twenty branches sequenced with the instruments first, and a test method per branch kind |
| **Step 1** — the repository *(branches 0, 1, 2)* | the project had **no version control at all**, so every change was unrecoverable and *"change one thing, re-grade, compare"* was unenforceable. Branch 0 committed both trees unmodified as a provable original; branch 1 built the harness; branch 2 built the parity check. The pre-`git init` order was non-negotiable and was followed: sanitise, `.gitignore` **by path**, write the scan, **run it and read it**, only then `git init` | **The repository exists and is PUBLIC** — `github.com/wjvandenberg/legal-translation-skill`, branch protection live with `enforce_admins`. 11 synthetic fixtures · 14 negative inputs · the byte comparison `git bisect` rides on · the two-tree parity check. **The public flip was measured, not assumed:** every blob in every commit scanned, security 0, nothing outside `uk/`/`us/` matching any probe, and the superseded skill files byte-identical to archives already downloadable. **Four defects in our own measuring tools remain open** — they belong to branch 1, change no skill finding, and will corrupt Step C's evidence if still open when it runs *(§7)* |

**The evidence base as it now stands, and these are the numbers to quote:**

> **`FINDINGS-REGISTER.md`: 215 rows — 15 clusters · 171 skill findings (159 clustered + 12 single-instance)
> · 27 positives to preserve · 17 defects in our own measuring instruments (12 fixed, 5 open).** The largest
> cluster is the instruction contradictions, at **39**. Validator **PASS, 0 failures, 0 warnings**.
>
> **The instrument count moved from 11 to 16 on 2026-08-11, and the five new rows are a different
> population from the first eleven.** I-1 to I-11 are defects in the **A1 harness and review tooling** —
> instruments outside the repository that were used to *produce* the evidence, and **four of them are still
> open** and will corrupt Step C if they still are when it runs. **I-12 onward are defects in the
> repository's own committed checks** — the ones that now guard the build. **The skill-finding counts are
> untouched by any of them**, because none is a defect in the skill.
>
> **THE FIFTH OPEN ONE IS I-17 AND IT IS NOT A STEP C RISK — read the two populations before quoting
> "five open".** *(Added 2026-08-21 on branch 14.)* The four that threaten Step C are still exactly
> **I-7, I-8, I-9, I-10**, all in the A1 harness. **I-17 is in our own fixture set**: one of the eleven
> synthetic documents cannot be opened by any renderer, because it carries auxiliary parts with no
> relationship part pointing at them. It cost nothing here — the byte comparison covers that fixture
> exactly — but **branch 18's test IS a render**, so it has to be repaired before that branch, and it
> means no render-based test can currently reach the comment and footnote anchors that fixture exists
> to carry. It is left open deliberately: fixing a fixture is harness work, and several arms of the
> negative-input suite read that file.

### 2.4 What was produced, and which documents matter from here

Six committable documents exist. **Three are live inputs to the work ahead; three are reference.**

- **LIVE — `STEP-B-ANALYSIS.md`.** The build plan and **the leading document for the whole of step 2**. Its
  §2 is the order, §3 the brief per option, §4 the test method. It is in four parts and **only Part One is
  needed to build.**
- **LIVE — `FINDINGS-REGISTER.md`.** Every claim in the build plan traces to a row here. The build
  plan's own `STEP-B-ANALYSIS.md` §9 appendix maps branch → findings, and is generated by script so
  it cannot drift.
- **LIVE — `A3-STRUCTURAL-ANALYSIS.md`.** The measurements. Consult it when a structural judgement comes up
  inside a branch.
- Reference — **`OPUS-5-MIGRATION.md`** (step 3), **`DECISIONS-LOG.md`** (why things were settled), and
  **this file**.

### 2.5 What the evidence says — the seven things a new session must know

**1. This is not a formatting project.** The pipeline has silently destroyed legally material content on
several documents — a deed's only footnote, fourteen of twenty-eight comment anchors, a contract's
closing bracket and terminal full stop, untranslated source-language text on the first page of a delivered
document. **In every case the auxiliary part was translated perfectly and the *pointer* destroyed**, so the
English exists in the package and is unreachable — **and every gate reported PASS.** Twenty-seven of the 170
findings are content losses; six are the worst grade the register has.

**2. Three independent mechanisms explain why nothing was caught, and one sentence is not enough.**

- `validate_apply --strict`, the strictest and most-invoked gate, **compares token sets** — no order, no
  punctuation, not even a multiset — and polices only *missing* tokens, never extra ones.
- **The mandatory quality gate discards its own verdict**, so it reports success to its own auditor on runs
  it has itself declared failed.
- **A delivered `.docx` that fails its own ZIP integrity test produces a printed warning and exits 0.**

**Anyone scoping this from the token-set sentence alone will under-build it — that mistake was made in this
file and cost a wrong prediction.**

**3. Translation quality is not the problem.** Quality and terminology scored **9 on every one of the twelve
graded documents**; English-variant conformance scored **10 on all twelve**. **Do not spend the build on
translation.**

**4. The rendered visual diff is the primary instrument, not a final check** — it produced or confirmed the
top finding on **every** document. **And both documents must be rendered:** reading the translation alone
misses what is *absent*.

**5. Do not weaken the anti-drift safeguards in response to any of this.** The correct move is the **missing
rule**, not a softer version of the existing ones: *a gate can be wrong in scope; fix the gate, never bypass
it, and never alter a faithful translation to satisfy a linter.* An independent reader called the present
absolutism *"mature"*, which is evidence it is worth keeping.

**6. Six findings need the CLAIM fixed as well as the code — this is register cluster X, and it was a new
class of finding.** A competent independent reader, working from the published package and nothing else,
**praised as the artefact's strongest feature the exact layer this register shows is blind**, and credited
as coverage a device the register shows leaks. **Both readings are correct in every case.** That is not a
disagreement to resolve; it is a measurement of how convincingly the skill claims things it does not do.

**7. Two structural statements carry more weight than any individual finding.**

- **The pipeline preserves form as COUNTS and FLAGS, never as EFFECTS.** True of run properties, tab
  characters, width-bearing padding, empty-paragraph page breaks and manual line breaks alike. It is the
  register's most-repeated lesson, restated as a design fault. **A layout device must be judged on its
  RENDERED EFFECT, never on its element count.**
- **What looked like one cluster is two independent failures.** Putting the English back *deletes* structure
  it should keep (where every critical content loss sits) and the data contract is *unable to describe* the
  formatting (where the visual defects sit). **Two fixes, two files, and neither closes the other's rows.**

**Where the four defects Wouter named at the outset actually live:**

| named defect | what it turned out to be |
|---|---|
| **bold formatting** | **not one defect but a class.** Emphasis reaches a run three ways — a run-level flag, a **character style**, or a **paragraph style** — and the pipeline handles only the first. Worse, it does not merely fail to carry style-borne bold forward: putting the English back writes explicit *off*-flags that **switch it off**, measured at 0 → 694 switched-off runs on one document |
| **signature blocks and layout** | **four mechanisms co-acting on the same eight lines** — leading tab runs, justification before a manual break, an unsplittable table, and width-bearing padding preserved by count. A one-mechanism fix leaves the block wrong |
| **tracked changes** | scoped from real data rather than from the post-mortem that had none: **six of eleven** corpus documents carry them, including a construct the skill has no concept of at all |
| **install truncation** | detection did not degrade — **it was never extended past the scripts folder.** 20 of 20 scripts are protected; **178 of 198 files are not** |

**Two defect classes the project did not know it had, both now scoped as workstreams:** **document
furniture** — the formulaic apparatus of an instrument rather than its subject matter (title block,
execution line, attestation, signature-block labels, section symbols, numbering words, cross-reference
conventions), which belongs to neither axis of a lexicon organised by domain × language, so no amount of
domain scoping reaches it; and **the run-written baseline** — every check compares the delivered document
against an artefact the run itself produced, which is blind at three separate points: conversion, extraction
and post-apply.

**The measured performance record — the never-regress baseline, and the thing every later run is compared
against:**

| doc | document | var | **grade (v3)** | ACTIVE | script / model | cmds | gates | re-runs | batches |
|---|---|---|---|---|---|---|---|---|---|
| D03 | Agreement (Norwegian) — **no sub-lexicon** | UK | **9.3** | 33.1 min | 1% / 99% | 56 | 1 | 41 | 26,18,18 |
| D01 | Power of Attorney (Hungarian) — batch pos 1 | UK | **9.2** | 20.6 min | 0% / 100% | 29 | 0 | 15 | 17 |
| D09 | Document (Hungarian) — most tables | UK | **9.1** | 27.3 min | 0% / 100% | 41 | 1 | 27 | 29,33 |
| D10 | Guarantee (Polish) — batch pos 2 | UK | **9.1** | 17.8 min | 0% / 100% | 37 | 0 | 23 | 20,18 |
| D04 | Contract (Spanish) — heaviest tracked changes | US | **9.0** | 33.2 min | 1% / 99% | 75 | 1 | 60 | 31,34 |
| D11 | MOU (Japanese) — only non-Latin | UK | **8.8** | 25.6 min | 0% / 100% | 41 | 1 | 25 † | 14,12 |
| D06 | Contract (Italian) — legacy `.doc` | UK | **8.8** | 49.6 min | 1% / 99% | 84 | 4 | 69 | 18 × ≤35 |
| D07 | Novation (English) | US | **8.6** | 35.0 min | 0% / 100% | 28 | 2 | 13 | 35,17 |
| **D03B** | **same document as D03 — batch pos 3, ARM** | UK | **8.6** | 32.0 min | 0% / 100% | 42 | 1 | 27 | 29,19,14 |
| D08 | Agreement (Finnish) | UK | **8.5** | 27.6 min | 0% / 100% | 43 | 2 | 28 | 21,16 |
| D02 | Agreement (Dutch) — richest | UK | **8.4** | 28.7 min | 1% / 99% | 59 | 5 | 43 † | 6 × ≤26 |
| D05 | Deed (Italian) | US | **8.4** | 38.8 min | 0% / 100% | 41 | 2 | 29 | 6×35,21 |

† ran on harness v1 — re-run, gate and iteration counts are not comparable. **Interruptions are excluded
from ACTIVE.** **Read D01 and D10 with the simplicity caveat in their grade reports:** between them they have
no tables, no footnotes, no comments, no definitions section and almost no auxiliary parts, so several
structure and formatting criteria score 10 on *absence* rather than capability. Their high scores are not
evidence the pipeline is stronger than the richer documents show.

**One cell was corrected on 2026-08-11: D03's re-runs read 40 and are 41.** Found on branch 4, when a new
instrument asserted this table against the private `analyse_log.py` that produced it and the assertion
failed. Confirmed by running that analyser on D03's own forensic log, which reports 41. **All 35 other
machine-produced cells — commands, gates and re-runs across twelve runs — reproduce exactly**, so the
corpus total is **400 re-runs, not 399**. `tools/gate_replay.py` now asserts the whole column on every run,
which is why a one-digit error in a public table is now a build failure rather than a reading exercise.

**Six conclusions from those runs, each replicated across documents:**

1. **Script time is 0–1%; model time 99–100%. Twelve runs from twelve.** **No efficiency work should touch
   the Python.**
2. **Runtime is `24.6 + 0.040 × paragraphs` minutes** — about **25 minutes of fixed overhead and 2.4 seconds
   a paragraph.** Translating is **43%** of the time; on a 24-paragraph document **96%** of the run is fixed
   cost. **The skill has one gear**, and that is the runtime problem.
3. **The 35-paragraph batch cap is correctly calibrated, and it is an ATTENTION cap, not a context cap.**
   Context was never the binding constraint on any run. **Evidence against raising it under Opus 5.**
4. **Context is not a constraint:** the skill-side peak is **6.4% of the 1M window** (8.3% on a profile
   heavier than anything observed). The live reasons to care about file size are **findability and
   truncation, not tokens.**
5. **The over-engineering is in capabilities, not in files.** No dead scripts, no orphan lexicons, only 4%
   duplicated prose — but **four shared capabilities across thirteen independent implementations**.
6. **Batch position degrades the POLICING, not the translation.** The controlled pair (same document, batch
   position the only variable) scored 9/9/9 on the translation criteria in both runs; every point the arm
   lost, it lost to out-of-pipeline defects the single run had found and repaired. **The consequence is an
   argument for the fixes, not for a batch rule.**

### 2.6 Decisions that still bind

**The reasoning behind each is in `DECISIONS-LOG.md`, by date. This table is the short list of what is
settled — if you are about to re-open one of these, read the dated entry first.**

| decided | what |
|---|---|
| 2026-07-27 | Two variants only; a third client-internal variant is out of scope. Test corpus lives **outside the tree, permanently**. Distribution is **public**, which makes confidentiality a design constraint from commit one. The reverse skill is out of scope |
| 2026-07-28 | **One private monorepo** holding both full trees side by side, no build step, plus an automated parity check. **No `CHANGELOG.md` going forward.** Chat mode is never used for testing; **Cowork only** — but the skill's Chat-mode warning stays in, because it protects users |
| 2026-07-29 | Flat layout; repo name **`legal-translation-skill`**; **`.gitignore` by path, not by extension**. Branch protection on `main` from creation, **0 required approvals**. `README.md` from commit one. **`git bisect` is the standard method for regressions**, run against the smoke suite or the fixture byte-comparison — never against "translate and grade". **No credentials in the repo, ever.** All raw forensic logs live outside the repo. **Third-party telemetry (Sentry, PostHog) is NOT viable** for a published skill that processes privileged documents — build a local, opt-in, **metadata-only** run report instead. **ZWSP in the deliverable is always a defect**, and the fix is a pre-repack scrub, not a prohibition on the device |
| 2026-07-30 | Grader **frozen at v3** until the verification run. The **thinking level is a measurement parameter** — hold it constant inside any comparison. The register is the input to the fix exploration |
| 2026-07-31 | **A name-based leakage scan is not sufficient on its own**; two controls are required. **The register gets a validator**, run before and after every edit |
| 2026-08-04 | **Quality is the main driver; speed matters less and must never compromise quality.** A rebuild is presented as a real option but the default is to keep the present architecture. **Frozen translated intermediates from the real corpus are approved as local-only test fixtures** — a new artefact class that must be excluded by path before `git init` |
| 2026-08-05 | **All eleven options decided: ten GO, the rebuild declined.** No shared library. No separate furniture file. **No cross-language parity check** — none could honestly be written. The sanctioned way out of a deadlocked gate exists, with four conditions, **and Wouter reviews its specification before it lands** |
| 2026-08-06 | This file rewritten to seven sections; `OPUS-5-MIGRATION.md` and `DECISIONS-LOG.md` split out; **the build plan is no longer restated in the charter**. **A test document is named by its instrument class and its language and by nothing else** — §5.4 — and the qualifier list lives outside the repo, like the name list |
| 2026-08-20 | **A private run-logging tier plus a monthly replay-and-analyse job is APPROVED as STEP 5** — §3.5. **A CONFIG OVERLAY, never a third variant**, so 2026-07-27 stands rather than being overturned; **built only after the UK and US skills are published**, though the log FORMAT is designed at D3 because it is the same artefact as the shipped run report. **Portable, reproducible and observable from commit one**, because it moves to the cloud later. **The verbose logs contain client text**, so the sibling-folder rule, the evidence guard and sanitised-conclusions-only all apply, and the register gains a **production-evidence origin class** |

---

## 3. Plan of action — what is still to be done

> **This section owns the ORDER, the STATUS and the GATES, and nothing else.** **`STEP-B-ANALYSIS.md` owns
> the scope and the sequence of the build itself**; §5 here owns the rules; §6 owns the structure. **If this
> section and `STEP-B-ANALYSIS.md` disagree about what a branch contains, that document wins. If they
> disagree about when a step happens, this section wins.** Never restate a branch's scope here, and never
> restate the project order there. Undivided ownership is what let the previous version of this plan drift.

**Everything that has been done is in §2.3 and is not repeated here.** This section is future work only.

### 3.1 The five steps

`NOT STARTED` · `IN PROGRESS` · `BLOCKED ON <what>` · `DONE`

| step | what | status | blocked on |
|---|---|---|---|
| **1** | **Foundation: the repository** — version control, the baseline commit, the test harness, the parity check, then the public flip | **DONE, 2026-08-07.** Branches 0, 1 and 2 built, verified, tested, audited and **merged**; the confidentiality cleanup and the cycle enforcement merged beside them. **The repository is PUBLIC and branch protection is live with `enforce_admins`.** The exit gate is closed | — |
| **2** | **Building** (goals ii and iv) — the rest of `STEP-B-ANALYSIS.md`: branches 3 to 19, plus the three deferred items | **IN PROGRESS since 2026-08-07. Branches 3 and 4 merged**; **branch 5 is BUILT AND NOT MERGED.** Its seven code changes are complete and verified in both trees, and its merge is held by the fourth sequencing fact: the behavioural probe of rule 5b must run first. **THE PROBE RAN IN COWORK ON 2026-08-19, and arm 1 turned out NOT to be a true deadlock** — a compliant repair existed, the operator found it by reading the check's source, reached rule 5a rather than 5b, and disclosed it. **So 5b itself is still untested**, while the run exposed and closed two real defects: rule 5a forbade the repair it mandated, and the Step 6 gate's remedy named only two of the three things that can be wrong. **THE GATE IS DISCHARGED, 2026-08-20** — three rigs, three checks that turned out to be wrongly scoped rather than deadlocked, two live runs leaving the installed tree 198 of 198 byte-identical. Its test could not be constructed; its concern was answered. **`DECISIONS-LOG.md`, 2026-08-20 owns the reasoning, including that the plan was wrong to treat 5b as what makes branch 5 safe** — the census measured the real risk as false-alarm load, which is branch 14's. **Arm 2 stays unbuilt and no fourth arm is planned.** The remaining fifteen branches plus the three deferred items are fully planned and fully decided | branch 5's merge: **Wouter's approval. Nothing technical remains** |
| **3** | **Opus 5** (goal iii) — two branches, then **Step C**, the full verification run, then **INPUT POINT 2** | **NOT STARTED**, designed. `OPUS-5-MIGRATION.md` | step 2 |
| **4** | **Revisit, then publish** — **Step D** consolidates everything learned, *then* repackaging and publication | **NOT STARTED** | step 3 |
| **5** | **The private run-logging tier, and the monthly analysis of what it records** — Wouter's own instrumented use of the published skill, plus a scheduled job that replays what went wrong against the skill as it then stands. **A config overlay, never a third variant, and never published** | **NOT STARTED.** Approved 2026-08-20; the log FORMAT is designed earlier, at D3, because it is the same artefact as the shipped run report | step 4 — **the overlay is built only after the UK and US skills are published for external users** |

**Steps 1 and 2 share one branch numbering, and this is worth being clear about because two schemes used to
exist.** `STEP-B-ANALYSIS.md` §2 numbers all the work 0–19 plus D1–D3. **Step 1 was branches 0, 1 and
2 of that sequence. Step 2 is branches 3–19 plus the deferred items.** The old charter names map onto it
exactly: `feature/baseline-and-inventory` is branch 0, `feature/test-harness` is branch 1, and
`feature/variant-parity-and-reconcile` split in two — the check is branch 2 and the reconciliation is D1.

> **Step 1 has no section of its own any more, and that is deliberate** *(Wouter, 2026-08-07)*. **This
> section is future work; a finished step described here is a step the next session will start planning
> again.** What it did is in **§2.3**, with the row of this table as its status. The 44 lines that used to
> sit here — the pre-`git init` order, the three branch briefs, the exit gate — were all discharged, and the
> two rules among them that still bind live in §5.4 rather than in a plan.

### 3.2 Step 2 — Building

> **`STEP-B-ANALYSIS.md` IS THE LEADING DOCUMENT FOR THIS ENTIRE STEP. Read it and follow it.** Its **§2**
> is the order — twenty branches plus three deferred items, each with its dependency and its gate. Its **§3**
> is the brief per option: **what to build, what it must NOT do, and what counts as done.** Its **§4** is the
> test method by branch kind. **Read §2, then §3, then §4, in that order; that is the whole build path.**
> Nothing outside its Part One is needed to start work.
>
> **This section does not restate any of it, and must never start doing so.**

**Every branch — this one and every step described in `STEP-B-ANALYSIS.md` — is done as:**

> ### **Explore → Plan → Code → Verify → Test → Commit**

and under the branch, pull-request and merge rules in **§5.1 to §5.3**. That is not a slogan; §5.1 says what
each of the six words requires, and **Verify and Test are separate on purpose**: verify proves *this* branch
did what it claimed, test proves nothing *else* broke.

**Four things about the shape of the build, which the plan owns but a reader should not be surprised by:**

- **The instruments come before the fixes.** Nothing can be judged until the thing that judges it exists.
- **Nine of the twenty branches change nothing a document can see.** The behaviour-change column in
  `STEP-B-ANALYSIS.md` §2 is the risk column; read it first.
- **Three sequencing facts are absolute:** the checks cannot be given teeth before the scope rule and the
  sanctioned way out exist, or the pipeline deadlocks with no compliant exit; the delivered-document check
  cannot be built before the tidy-up script journals its edits; and the formatting work's second slice
  cannot begin before the delivered-document check exists, and must carry the off-flag removal in the same
  branch.
- **The leap Wouter asked for is in the plan, and it is not a rebuild.** The rebuild was declined on
  measured arithmetic — it addresses **at most 94 of the 170 recorded findings**, cannot be decomposed into
  merge-sized steps, and risks the half that measurably works. **The leap is the formatting option,
  delivered in three slices that can each be merged, tested and reverted.** Its first slice is also the
  probe that would reopen the question: whoever runs it must **report explicitly** whether a per-span model
  can be layered onto the present extraction and apply, or whether both must be replaced wholesale. **Do not
  proceed silently.**

**One gate inside this step needs Wouter, not a script:** the specification for the sanctioned way out of a
deadlocked gate. He approved the principle, not the text, and asked to see it. **That branch ends in his
review, not in a merge**, and the branch where the checks get teeth cannot start until the review is closed.

### 3.3 Step 3 — Opus 5, and the verification run

**`OPUS-5-MIGRATION.md` owns this step in full.** In outline: two small branches (a context audit that
simplifies only the defensive logic written for the previous model's context window, and the effort/batch
work), then **Step C — the full verification run**: all 11 documents on the 3 US / 8 UK split with the same
forensic logging as A1, graded against the frozen v3 baselines, **with the configuration reproduced** (two
documents must run in a batch, because their baselines are batch-run baselines), then the two thinking-level
arms and the reachability arm. **Then Wouter reviews all 11 himself — INPUT POINT 2.**

**Do this after the build, never alongside it.** Doing them together makes attribution impossible: if a
grade moves you cannot tell whether it was the fix or the model configuration.

### 3.4 Step 4 — Revisit, then publish

1. **Step D — consolidate and revisit. This step does NOT open with packaging.** Take all the accumulated
   evidence — the A1 logs, the A2 baselines, A3, A4, everything learned in steps 2 and 3, the Step C logs
   and scores, **and Wouter's feedback from both input points** — and revisit the skill on that basis.
   **Anything still short gets explored in the Step B style, not patched straight to code.** Re-run and
   re-grade after any change.
2. **Then `feature/repackage-and-publish`.** Rebuild both `.skill` archives; run **both** confidentiality
   controls and the publication check over the archives *and* the commit history; confirm nothing
   changelog-like is inside the archives; add the **"run at maximum thinking"** instruction to `SKILL.md`
   and both READMEs; then publish to the two public repos and lawve.ai. **Never make a repo public, or
   publish, without Wouter's explicit OK.**

**Two deferred items land here rather than in step 2**, because they belong to the skill's publication: the
**manifest and the coverage-and-size discipline**, and the residue of the claims pass. **The manifest comes
first** — a Markdown file cannot carry its own integrity guard, so the truncation-coverage fix cannot be
built without it.

### 3.5 Step 5 — the private run-logging tier, and the monthly analysis

**`DECISIONS-LOG.md`, 2026-08-20, owns the reasoning. This section owns only where it sits and what it
waits on.** Wouter's words: *"make sure that all logs of legal translation are logged for me and researched
by an agent every month, and tested against the then installed skill!! Analyse and present solutions, then
verify."*

1. **A config overlay, not a third variant** — the same published tree with logging turned up. The
   2026-07-27 decision against a third variant is about a third *client-internal published* tree and
   **stands untouched**; this is not one. **The capability ships, the verbosity does not** — §5.4's rule
   that the scanner ships and the list never does, applied to instrumentation.
2. **Built only after the UK and US skills are published**, on Wouter's instruction. **But the log FORMAT
   is designed at D3, with the manifest** — §5.11 and §5.6 make the forensic log and the shipped run report
   *the same artefact*, so one format with two verbosity tiers is free and two formats is a reconciliation.
3. **The monthly job replays, it does not merely read.** It takes what the logs record and re-runs it
   against the skill **as it stands that month**, reporting which failures still reproduce. §5.8's
   frozen-intermediate trick makes that deterministic and model-free.
4. **Portable, reproducible and observable from commit one**, because it moves to the cloud later — every
   location by environment variable, never a hard-coded path, and it exits non-zero on VOID rather than
   reporting a clean run over an empty set.
5. **The logs contain client text**, so they live in a sibling folder, the evidence guard must name that
   folder, only sanitised conclusions reach the register, and the register needs a **new origin class for
   production evidence** — the same gap the 5b probe hit.

**Its field list, its scheduling mechanism and the shape of what it presents are NOT decided**, and §3.4's
rule governs: explored in the Step B style, not patched straight to code.

> **AND ONE TOOL IS ON THE TABLE, UNEXAMINED. NOTION.** *(Wouter, 2026-08-20: he may want to use it to
> keep track of the automation. **He has never worked with it, has not installed it, and is going on
> "I heard it is the right tool".** Recorded at that strength deliberately — an option nobody has
> tested is not a choice yet, and writing it down as though it were is how an inference acquires the
> confidence of a measurement.)*
>
> **What it plausibly fits: the AUTOMATION's own status** — did the monthly job run, when, did it exit
> clean, what is scheduled next. That is metadata about a process and carries nothing sensitive.
>
> **What it must not become without a decision: a home for the ANALYSIS.** Notion is a third-party
> cloud service, and **2026-07-29 already ruled third-party telemetry non-viable for a skill that
> processes privileged documents** — the reasoning being that even a filename is unsafe. The monthly
> analysis derives from logs that quote real client text, so **the sanitisation that §5.13 requires
> before anything reaches the register becomes load-bearing in a second place**, and this time the
> destination is someone else's server where a mistake cannot be un-published.
>
> **So the line to draw before anything is installed is between tracking that the automation RAN and
> storing what it FOUND.** The first looks safe on today's reading; the second needs the 2026-07-29
> reasoning applied to it properly rather than by analogy. **Neither is decided, and the tool has not
> been evaluated against any alternative** — including the plainest one, a file in the private folder.

### 3.6 Autonomy, and the two input points

Run the translation and grading work **as autonomously as possible**: no mid-run questions, no confirming
obvious choices, no step-by-step progress reports. **There are exactly two input points, and they bracket
the two autonomous blocks.**

| | autonomous block | → | Wouter's input |
|---|---|---|---|
| **1** | **A1 + A2** — translate all 11 plus the arm, log forensically, grade | → | **INPUT POINT 1 — his blind review of all 12.** **CLOSED 2026-07-31** |
| **2** | **Step C** — translate 11, log forensically, grade | → | **INPUT POINT 2 — he reviews all 11.** Feeds Step D. Protocol at §5.13 |

**What autonomy does NOT change.** It covers *running the skill and grading the output*. It is not a licence
to skip the collaboration rules on code: **every branch still gets explore and plan with Wouter, a pull
request, a presented review, and Wouter's approval before merge. Autonomy never means self-merging.** If an
autonomous run hits something genuinely blocking, finish everything that does not depend on the answer
first, then ask once.

---

## 4. Tech stack

**Anything is acceptable as long as the result works well as a skill in Claude Cowork.** That is the hard
constraint, and it is easy to forget from inside a terminal: **most users will NOT be in Claude Code.**
Cowork (and Chat) is the primary runtime; **Claude Code is the development environment only.**

**The skill's own stack:**

- **Skill format:** `SKILL.md` (YAML frontmatter plus Markdown) and progressive-disclosure Markdown
  documents — meaning the skill loads a little at a time, at the step that needs it, rather than all at
  once. Packaged as a `.skill` / `.zip`.
- **Python 3** for all 20 pipeline scripts. **No third-party dependencies beyond the standard library where
  avoidable** — the skill must run in whatever sandbox Cowork gives it. **`lxml` is the only third-party
  import, in 7 of the 20 scripts.**
- **OOXML manipulated as text**, not through an XML object model. The hard rules are §5.10 and they are not
  stylistic preferences — each one is a production incident.
- **Lexicons and step documents as Markdown**, deliberately split small so only a few load at once.
- Run Python via **`uv run`** (inherited house rule).

**Dev-host toolchain — installed and verified 2026-07-29, and every element of it is load-bearing:**

| tool | version | used for |
|---|---|---|
| Python | 3.14.3 | the 20 pipeline scripts and every measurement script |
| `lxml` | 6.0.2 | the only third-party import in the skill |
| `uv` | — | house rule: run Python via `uv run` |
| **Microsoft Word (COM)** | 16.0 | **reference-fidelity `.doc → .docx`** — our own evidence baseline |
| **LibreOffice** | 26.2.4.2 | the **user-reality** converter, and `docx → pdf` |
| **pandoc** | 3.10 | the grader's `docx → markdown` comparison |
| **PyMuPDF** (`fitz`) | 1.28.0 | `pdf → png` page rendering |

**The rendered visual diff — the project's highest-yield defect detector — is available on this host**, and
A1 proved it: it produced or confirmed the top finding on every document. **Convert legacy `.doc` with Word
for our own evidence and with LibreOffice for user reality: the comparison between the two IS the test.**

---

## 5. Working method and rules

*Ordered from the rules that apply to every piece of work, through the quality spine, to the domain-specific
rules and the ones that apply to particular kinds of session.*

### 5.1 The cycle — Explore → Plan → Code → Verify → Test → Commit

**For every branch, always, with no exceptions and no compression. And for EVERYTHING WRITTEN, not only
code** — this file, `STEP-B-ANALYSIS.md`, the register, a README. *(Added 2026-08-06. The session that built
the repository edited this charter twice and treated neither edit as a branch: no verify, no test, no audit.
Prose that is wrong misdirects the next session exactly as a broken script does, and this file has already
cost one wrong prediction that way.)*

| | what it requires |
|---|---|
| **Explore** | Read the branch's brief in `STEP-B-ANALYSIS.md` §3 **and the register rows behind it** (its §9.3 maps branch → findings). Open the code the branch will touch. **Never work from a précis** — §1.5. **And read what the brief POINTS AT, not only the brief:** §3.3 says option 7's substance lives in §6, and a session that planned branch 2 from §3.3 alone got the arm count, the comparison method and the term-list source all wrong |
| **Plan** | **With Wouter, before any code.** State what the branch builds, **what it must not do**, and **what counts as done** — all three are in §3 of the build plan; do not invent your own |
| **Code** | **One feature branch per capability.** Small and orthogonal, because a merge is hard to unpick. Where a change genuinely cannot be decomposed, say so — that is a decision for Wouter, not a risk to bury |
| **Verify** | **Prove this branch did what it claimed.** The acceptance condition in §3's *Done when* line — the byte comparison, the negative input that makes each new check fail, the named acceptance test. Where a check is meant to catch known defects, **its first run must reproduce them**; if it does not, it is not built correctly |
| **Test** | **Prove nothing else broke.** The method for that branch kind in `STEP-B-ANALYSIS.md` §4, plus the smoke suite, plus the parity check from branch 2 onward, plus a graded run where §4 says a graded run |
| **Commit** | §5.2 and §5.3 |

#### The cycle must produce ARTEFACTS, not intentions

**Open a task list before any code, carrying all six phases plus every applicable item from §5.3, and cross
each off only against the OUTPUT OF A COMMAND YOU HAVE RUN** — not against a recollection, and not against an
intention to run it later.

**A branch whose VERIFY and TEST entries are not crossed off is not finished, whatever its diff looks like.**
The pull request may be opened; it may not be presented as complete.

**Where an item does not apply, cross it off as a DECLARED N/A with its reason** — never omit it. *"Branches
0, 1 and 2 change no skill file, verified as zero files differing under `uk/` or `us/`, so no graded run and
no rendered visual diff apply"* discharges the requirement. Silence does not.

**And it is enforced mechanically, because prose is what was already read and skipped past.**
`tools/cycle_evidence.py` records that a verify and a test command ran and exited 0, bound to a hash of the
staged content — so editing a file after testing it invalidates the evidence automatically. The pre-commit
hook refuses a commit with no matching evidence. **It proves a command ran against this content and exited
zero; it cannot prove the command was a good one, and it says so in its own output.**

> **WHY THIS IS A RULE AND NOT AN ENCOURAGEMENT.** *(2026-08-06.)* The repository session ran three branches
> end to end without pausing once, and the failure was not ignorance — §5.1 had been read. What was missing
> was any artefact whose absence would show. When VERIFY was finally run properly it found, in work already
> committed and presented as complete: **a published figure that was wrong and had been reported as an
> independent confirmation of the plan** · **fixtures that were not byte-reproducible, which broke the one
> tool that branch existed to enable** · **a parity check that missed the very defect it was built for,
> because it tested one direction of a symmetric assertion** · and **a `__pycache__` leak into the shipped
> trees that had been fixed once and returned through the next caller.** None was found by reading. Every one
> was found by running something.

**Three failure shapes to expect, because each has now happened more than once.** *(1)* **A check that passes
for the wrong reason** — eleven logged instances, several inside this project's own verification scripts.
Never a two-word needle; ask the same question a second way; and **when a figure agrees with the one you
expected, that is the moment to re-derive it, not to relax.** *(2)* **A fix scoped to one caller of a shared
hazard** — the bytecode leak was fixed in the test runner and came back through the audit tool. Ask what else
does the same thing. *(3)* **An instrument reporting on an empty set** — `PASS: all 0 paragraphs` is not a
pass. **Assert the READ COUNT as well as the result;** a control that opened no files must say VOID, never
CLEAN.

**Two disciplines bind every option, and they are not in tension with taking a leap:** every change points
at a **specific observed failure or grade**, never at theory; and **the anti-drift safeguards are not on the
table.**

### 5.2 Branches, pull requests and commits

- **Pull requests, NOT direct merges.** Open a PR per branch, review the diff — walk it, summarise it, flag
  the risks — and **present that review. Do not merge; Wouter approves.** Merge style is
  **squash-and-merge**. Push and update §7 after each branch.
- **STACKED BRANCHES: MERGE FROM THE BOTTOM UP, AND DO NOT DELETE A BASE BRANCH WHILE ANYTHING SITS ON IT.**
  *(2026-08-07, and it cost a pull request.)* Where branch B is opened against branch A rather than `main`,
  **deleting A on merge makes GitHub CLOSE B**, and a closed PR **cannot be reopened or retargeted** once its
  base is gone — `gh pr edit --base` fails with *"Cannot change the base branch of a closed pull request"*.
  The work is not lost, but the PR number, its review and its discussion are. **Either retarget B to `main`
  BEFORE merging A, or merge A with the branch left in place and delete it afterwards.** The recovery is a
  fresh branch off the new `main` plus `git cherry-pick`, which applies cleanly because the squash of A
  already contains everything B was built on — **re-run the full check set on the rebuilt branch before
  pushing it**, since it is a different commit on a different base and the old evidence does not carry over.
  **This is why stacking is a cost, not a convenience:** prefer branching from `main` whenever the change is
  genuinely independent, and stack only when the later branch truly needs the earlier one's content.
- **Before every commit:** run `git status` and **explain it to Wouter** in plain terms.
- **Branch protection on `main` — LIVE since the repository went public, 2026-08-07.** Require a PR; block
  force pushes and branch deletion; **`enforce_admins` TRUE**. Required approvals stay **0** — on a solo repo
  GitHub would otherwise refuse to let Wouter merge his own PR, breaking the agreed workflow rather than
  protecting it. **Tested both ways on the day:** a direct push to `main` is now rejected with `GH006`, even
  for an admin with the local override set; and a pull request remains `MERGEABLE` with no review required,
  so nothing about Wouter's merging is made harder.
  **AND THE LIMIT MATTERS MORE THAN THE SETTING.** No GitHub configuration can make Claude ask Wouter's
  permission, because Claude operates under Wouter's own account — to GitHub they are one identity. What
  actually requires his approval is the rule below, the local hooks, and compliance. The setting stops the
  *accident*; it cannot stop the *decision*. Add the smoke suite and the parity check as required
  status checks once they run in CI. Fall back to a repository **ruleset** if protection is unavailable.
- **`README.md` from the first commit, kept current.** It is the **public front door** on two public repos
  and the install instructions for a non-technical lawyer — a product surface, not a formality. **Update it
  in the same PR as any change that alters behaviour, the feature list or installation.**
- **Debugging a regression: `git bisect`, not guesswork** — but bisect needs a *cheap, deterministic*
  pass/fail test, and "translate a document and grade it" is neither. **Bisect against the smoke suite or
  the fixture byte-comparison.**
- **Session restart after a gap of more than a day:** read the last ~8 commit messages plus §7, summarise
  them, *then* work.

### 5.3 Definition of done — every branch, every step

Smoke suite green · parity check green (from branch 2 onward) · **the branch's own *Done when* condition in
`STEP-B-ANALYSIS.md` §3 met** · tested by the method its branch kind requires in §4 · **where a graded run
applies, no criterion regressed against the frozen v3 baseline** · **rendered PDF visual diff against the
source, page by page, BOTH documents** · `git status` explained to Wouter · whole-picture review
(consistency, completeness, accuracy, code quality, security) · **both confidentiality controls and the
publication check run** · PR opened and reviewed, **Wouter approves the merge** · squash-merge · push ·
**§7 updated.**

### 5.4 Confidentiality — a hard constraint on every commit

The skill is **published publicly**. Treat every file in the repo as world-readable from the moment it is
committed: a private repo made public later exposes its entire history, and **a commit cannot be
un-published.**

**No confidential or sensitive business data in the skill, in the repo, or in the commit history. This
includes examples.**

- **No client or counterparty names, ever** — not in step docs, lexicons, script comments, test fixtures,
  commit messages, any committed log, or this file. **Enumerating the names here in order to scan for them
  would publish exactly what the rule protects.** The scan list lives in the **private sibling folder**,
  *outside* the repo tree rather than merely gitignored, because a `.gitignore` entry is one mistake away
  from failing and **a client name cannot be rotated once published.** The scanner reads the list by path or
  from an environment variable, so CI can supply its own copy as a secret. **Keep the list current.**
- **No real-document examples.** Every worked example, fixture and illustrative XML snippet must be
  **synthetic** — invented for the purpose. **Anonymising a real example still leaks its shape, its clause
  structure and its commercial terms.** Where a real document was the *source* of a lesson, keep the lesson
  and discard the document. **Renaming is not enough**, and the existing step docs are known to contain
  real-derived examples that were handled by renaming — replacing them is part of the claims pass in step 2.
- **NAME A TEST DOCUMENT BY ITS INSTRUMENT CLASS AND ITS LANGUAGE, AND BY NOTHING ELSE** *(Wouter,
  2026-08-06)* — **Agreement (Norwegian)** · **Power of Attorney (Hungarian)** · **Guarantee (Polish)** ·
  **Deed (Italian)** · **MOU (Japanese)**. **Never say what the instrument is about.** The subject-matter
  qualifier — the noun that says what the agreement is *over*, what the guarantee is *for*, what the deed
  *conveys* — plus a language plus a date range identifies a real instrument far more sharply than a name
  does, to anyone who knows the market. **And the 93-pattern scan is structurally blind to it:** it reported
  0 hits on every one of the qualifiers this project had been using, correctly, because none of it is a
  name. It is the same class of leak as the commercial terms found in July, and it gets the same two-control
  answer — a blocking probe in `temp/publication_check.py`, and `temp/descriptor_shape_sweep.py`, which is
  list-free and found four that the term list had missed.
  **The qualifiers themselves are NOT listed here, and the omission is the point.** They live with the scan
  list in the private folder; the probe reads them by path or from an environment variable. *(The first
  version of that probe carried them inline and this rule listed them as examples — so the probe fired on
  the rule. It was right to. Enumerating them here would publish exactly what the rule protects, which is
  the same reasoning that keeps the name list outside the repo.)*
  **The same rule covers clause content:** say what a lost span *did* — *"an operative condition"* — never
  what it said.
  **What stays, because it is the evidence and it is not sensitive:** the technical character of the file.
  No sub-lexicon · legacy binary `.doc` · only non-Latin script · most tables · 160 bold runs · paragraph
  counts · batch position · tracked-change load. **Those describe the FILE, not the deal.** The doc-id →
  real-document mapping lives in the private folder, as it always has.
- **THE LOCATION RULE, and it is a rule about place rather than a judgement about content.** Raw forensic
  logs, the test corpus, Wouter's review feedback and the frozen intermediates live **entirely outside the
  repo**, in the sibling folders named in §6.5. **Only the *derived* work is committed.** Nothing depends on
  correctly classifying each line, and it has a real benefit: **the raw log can be maximally detailed,
  because it is never published.**
- **The test corpus filenames alone carry counterparty names**, so they are as unpublishable as the
  contents. Never copy one into the repo, never name one in a commit message, never paste an excerpt into a
  public artefact.
- **A separate rule for one artefact that DOES ship:** the run report goes inside the skill, so it must be
  **metadata-only by construction** — counts and durations, never document text and never filenames.

> **AND ONE LEAK CLASS THAT NONE OF THE CONTROLS BELOW CAN REACH — THE TRANSCRIPT.** *(2026-08-11.)* A
> session ran `ls` and `find` over the sibling logs folder to learn its layout, and the output printed real
> corpus filenames carrying counterparty and personal names **into the conversation**. Nothing was committed
> and nothing could be: the leak never touched a file. **Every control below reads committed content**, and
> §6.5 already says session metadata is reachable by neither the scanners nor the location rule — so there
> is **no after-the-fact remedy at all**, and it cannot be un-said.
>
> **The rule existed and was broken anyway** — §6.5's *"any glob over an evidence folder must be explicit
> about which files it expects"* had been read that same morning. That is §5.1's argument restated: prose is
> not a control. **So the control runs BEFORE the command:** `tools/hooks/evidence_guard.py`, a PreToolUse
> hook wired in `.claude/settings.json`, blocks a name-emitting command — `ls`, `find`, `tree`, `cat`,
> `Get-ChildItem`, or inline code that enumerates a directory — whose target is an evidence folder.
> **The hazard is OUTPUT, not access:** a script that reads those logs and prints counts is exactly what
> `gate_replay.py` does and still runs, as does the register validator §5.12 prescribes by path.
> `tools/evidence_ls.py` is the sanctioned way to see a folder's **shape** — extensions, size buckets,
> per-directory counts, corpus doc-ids — and it prints no name, ever. **A block with no alternative gets
> worked around, and then you have a control nobody believes.**
>
> **Two limits, stated rather than implied.** Hooks load at **session start**, so this one does not protect
> the session that adds it — probe with `ls ../legal-translation-logs/NO-SUCH-DIRECTORY-PROBE`, which is
> BLOCKED if it is live and harmlessly reports a missing directory if it is not. And the **test-document
> folder is not named in the guard**, because its name is not committable; it is read from
> `.claude/evidence-dirs.local`, which is gitignored, so **in a fresh clone that folder is unguarded until
> someone creates that file.** Same shape as the scan list — the scanner ships, the list never does.

**Three controls, and they catch different things. Run all three on every committable file before any
commit.**

1. **The name-and-term scan** — 93 patterns, every one with a test vector. **A name-based scan is not
   sufficient on its own**, which was proved when an audit found the operative commercial terms of real
   client instruments in two committable files: the scan reported 0 hits, correctly, because none of it is a
   name. **Genericise commercial terms in committable prose** — *"the seven-figure guaranteed amount"*, *"a
   three-digit two-decimal figure with a comma decimal separator"* — which preserves every analytical point
   without the value.
2. **The shape-based sweep** — list-free. Non-ASCII tokens, capitalised multi-word sequences, money and
   capacity figures, identifier-shaped strings, filenames, absolute paths, long quoted strings. Everything
   it prints is a candidate for human judgement, not a hit.
3. **`temp/publication_check.py`** — asserts the specific forbidden classes and **fails rather than
   listing.** *(Its regex-metacharacter filter used to suppress one real hit — a home-relative path, because
   the path contains a backslash followed by a capital D and the filter read that as a quoted regex. It
   reported four findings of five and said nothing about the fifth. **Narrowed and given seven test vectors
   on 2026-08-06** — `temp/test_pubcheck_suppressor.py`. **A check that suppresses a real finding for the
   wrong reason is the failure class this project keeps logging**, and it is why every pattern needs a test
   vector next to it.)*

**Two list-maintenance rules, both learned the hard way.** Use `\s+` for every space in a multi-word
pattern, never a literal space — a bank-name pattern written with one space silently failed against a
document containing a doubled space, and **a missed name is invisible: the scan simply reports clean.** And
**every pattern must be tested against the string it was written for, in the same commit** — in Python,
`'\bName\b'` in a non-raw literal is BACKSPACE+Name+BACKSPACE and will never match.

**Which files may never be committed — measured, not assumed.** **The rule that decides it is not *"is this a
script?"* but *"does this file hold one real string per pattern?"*** — which is why a scanner is publishable
and the list it reads never is.

**Re-measured across all 90 scripts on 2026-08-06** (`temp/script_committability.py`, which runs the same
probes over the code that the publication check runs over the prose): **69 are clean and 21 hold a real
string.** The 21 fall into four kinds, and only the first was on the old list:

1. **The lists and their test vectors** — the name list, the corpus-descriptor list, and the pattern-test
   file, which holds one real string per vector *by design* and is therefore exactly as sensitive as the
   list itself.
2. **The two workspace-building scripts** that map document ids to real corpus filenames.
3. **The replacement scripts** written to apply a genericisation. A counted replacement has to carry the
   *before* text, so a script that removes a real string necessarily contains every one it removed.
4. **One-off measurement scripts with a hard-coded local path** — the A3 and A4 tooling. They were never
   destined for `tools/`; they are named here so nobody assumes otherwise.

> **Three of the scripts intended for `tools/` were caught by this and fixed the same day**, and the way they
> failed is worth more than the fix: **each had quoted a real string inside an explanatory COMMENT.** The
> publication check's own comment quoted the home-relative path it exists to block, and the list-free
> descriptor sweep illustrated itself with two real qualifiers. **A comment ships. An example in a docstring
> is published prose.** Invent the examples.

> **AND ONE FILE IS WITHHELD BY JUDGEMENT RATHER THAN BY PROBE.** *(Wouter, 2026-08-06: "I don't want
> confidentiality review to be committed.")* `temp/confidentiality_review.py` is clean on every probe, and it
> still does not ship: it sets out which shapes we scan for **and which candidates we accept**, which is a
> map of what gets waved through. **A probe cannot see that class of exposure**, so the list above is a floor
> and not a ceiling — read a script and ask what it reveals about the control, not only what strings it
> holds.

**Three things were known and open at branch 0. (a) and (c) are CLOSED; (b) is still open.**

**(a) — CLOSED 2026-08-07. The two published trees were scanned, read, and cleaned.** The scan hit 46 files
per tree, identically in both — overwhelmingly false positives from short patterns matching ordinary Dutch,
Polish, Hungarian, Finnish, French and German legal vocabulary inside the sub-lexicons, plus one pattern
derived from a filename whose first word is itself a common legal term, which alone accounted for 26.
**Four items were real, all already public, so cleanup rather than containment.** Two were replaced: a
worked example in a shipped script built from **two real people's names taken from real source documents**,
where renaming had never been applied at all; and **named outside law firms in the always-loaded file's
prose**. Two were kept by Wouter's decision: the author email, with his LinkedIn added beside it; and the
**firm heading-style patterns in `reorder_definitions.py`, which are FUNCTIONAL** — they are what lets the
skill recognise those firms' heading styles in a real document, so deleting them removes capability rather
than a reference. **Capability over disclosure, decided knowingly.**

**(b) The scan list still needs tightening before it is trusted as a pre-commit gate**: its false-positive
rate against the skill trees is high enough that a reviewer will start skimming, which is the exact failure
mode this project has already diagnosed in the skill's own validators. **A control nobody believes is not a
control.** *(Partly mitigated: the gate now separates the trees from everything else, and the pre-flip triage
splits matches into ALREADY PUBLIC and NEW EXPOSURE — the cut that makes 715 hits readable. The list itself
is unchanged.)*

> **SUBSTANTIALLY MITIGATED 2026-08-11 — THE GATE NOW SCANS THE TREES, BY DIFF.** Separating the trees out
> meant `tools/precommit_gate.py` did not look at `uk/` or `us/` **at all**: it counted their files and
> stopped. Defensible while no branch changed them; branch 4 changes eight files, and branches 6, 7, 16 and
> 17 will change far more. **A confidentiality gate blind to the two directories that actually ship is the
> wrong blind spot to keep.**
>
> **The fix is to judge only what a branch INTRODUCES.** Section 7 diffs `uk/` and `us/` against
> `origin/main` (override with `LT_TREE_BASELINE`) and runs three controls over the **added lines only** —
> the 93-pattern name scan, the 13 corpus-descriptor patterns **applied as regex and never `re.escape`d**,
> and the publication check's forbidden classes. The pre-existing false positives sit in the baseline and
> cancel out.
>
> **Measured on branch 4: the eight whole files give 6 hits; the 102 added lines give 0.** Same evidence,
> and the second is readable. **It reports VOID and refuses to certify when it cannot resolve a baseline** —
> a control that established nothing has not passed. `tests/test_gate_tree_scan.py` plants a leak of each
> class into a tree file and asserts the gate blocks on every one, then asserts the tree is byte-unchanged
> afterwards.

**(c) — CLOSED THE DAY IT WAS FOUND. THE CHANGELOG IS NOT COMMITTED AND `docs/history/` DOES NOT EXIST.**
*(Wouter, 2026-08-06: "Changelog should NOT be on commit list… Docs/history should never be committed.")*
The recovered rev16→rev44 changelog **sat on the commit list and had never been scanned, because it is not a
file yet** — it is recovered from the `CHANGELOG.md` inside the archived `.skill` revisions, and an artefact
that does not exist cannot be scanned. Measured on 2026-08-06
(`temp/changelog_confidentiality.py`): **four name-shaped patterns matching 69 times, one a multi-word proper
name**, plus **three corpus descriptors**, a company-form suffix, two capacity figures and three document
filenames — rising monotonically by revision, from 10 hits in the earliest to 32 by rev20, which is what a
working log kept while translating real documents looks like. **Not a defect in the archive; a defect in the
plan.** It is now closed the clean way rather than by sanitisation: **the changelog stays in the archived
revisions, outside the repository, where it already was.** It did its job as an input to the structural
analysis and the build plan, and **nothing downstream needs it** — every lesson it carried is already in §5,
sourced and dated.

**On credentials and history.** This project has **no credentials at all** — the skill authenticates against
nothing — so that rule is preventative and the live risk is client names and document content. **`.gitignore`
prevents accident; it is not a security control.** It does not remove anything already committed and does not
stop a deliberate `git add -f`. **Making a repo public exposes the entire history, not the current state**;
the only correct response to a committed secret is to **rotate** it, and **for a leaked client name there is
no rotation** — which is why the location rules matter more than any cleanup capability. History *can* be
rewritten, but it needs a force-push, which our own branch protection blocks, and **after a repo has been
public it is no longer a remedy** — forks and scrapers may already hold the content. **Hence the
non-negotiable pre-`git init` order, followed in full and recorded in §2.3.**

> **The good news, and it changes what the risk actually is: THERE IS NO HISTORY TO SCAN.** Nothing has ever
> been committed. Git will only ever see what is added at commit one, so **the exposure is the content of
> commit one and everything after it** — a better position than "scan the history" implies. Every earlier,
> less-sanitised version of this file exists only as a dated file in the private archive folder, outside the
> repo, and stays there permanently.

### 5.5 Never-regress — the rule, and how it becomes enforceable

**Wouter's hard rule: quality must only IMPROVE, never go lower.** Today it is untestable — grading is
manual, LLM-driven and non-deterministic, so re-grading every document per commit is not viable. **Two
tiers make it real:**

1. **A scripted mechanical gate, run on every change.** Most of what has been measured by hand is
   deterministic: paragraph counts, footnote/endnote/**comment** reference counts, tab characters versus tab
   stops, effective bold and italic **text**, run-property tables, remnant sweeps, invisible-character
   sweeps, variant sweeps, definitions ordering, accept/reject reconstruction. That covers most of the
   structural criteria, is reproducible, and **is what finally makes `git bisect` possible.**
2. **A full LLM re-grade only at branch boundaries**, on a fixed subset, against the frozen v3 baselines.

**Efficiency is strictly subordinate to this rule.** The expensive full-lexicon reads have paid on every
document, so *"make it faster"* must never become *"read less"*. **And there is no separate efficiency
workstream: fixing the defects IS the efficiency work**, because the gate cycles wasted on false alarms and
the re-runs forced by tool bugs *are* the time.

**The measurement that makes tier 1 possible:** between two runs of the same document, **about 40% of
paragraphs differ linguistically and the mechanical output is identical.** That is measured on the project's
only same-document repeat, not assumed. **So run-to-run variance is large in prose and nil in mechanics** —
the case for a scripted mechanical gate as the primary instrument and against an LLM re-grade.

### 5.6 The measuring instruments — hold all four constant

**These are properties of the measurement, not of the skill. State them wherever numbers appear, and never
vary one inside a comparison.** Two of the four have already cost this project real time.

| instrument | state | the rule |
|---|---|---|
| **Grader** | **v3, FROZEN** until the verification run. Dated backups are in the private folder — the grader is deliberately not in Git, so those are the only revert path | **Do not change it until Step C is complete.** A moving ruler destroys the never-regress comparison |
| **Harness** | **v2.2.** Two documents ran v1, one v2, one v2.1, the rest v2.2 | **Re-run, gate and iteration counts are NOT comparable across versions** |
| **Thinking level** | **`extra` on all 12 runs.** The ladder is `low` < `high` < `extra` < `max` | **`max` has never been used, so every A1 grade is a LOWER BOUND** |
| **Batch versus single** | Two documents have **batch-run** baselines; one document has **both** | **Reproduce the configuration** or the before/after is not like-for-like |

**The grader is v3 and has 17 criteria** (its own package: `SKILL.md`, `references/methodology.md` and
`variant-conformance.md`). It was validated, found usable but with three gaps, and extended twice.
*(Where a comparison of two runs reports "twelve of sixteen criteria identical", that is the register's own
pairwise comparison, which excludes one criterion that cannot be compared across runs — not a different
rubric.)* **Its bash paths are Cowork container paths; substitute local equivalents.**

**Eight measurement rules came out of building it, and every one generalises beyond the grader:**

- **Never score ANY run property from element counts — compare the affected TEXT, then render.** Translation
  consolidates runs, so nearly every count falls even when nothing is lost — and **it fails in both
  directions**, because putting the English back emits an explicit *off*-flag on every non-emphasised run.
  This produced a false positive on seven consecutive documents.
- **Count auxiliary REFERENCES, not just auxiliary parts.** A translated footnotes part whose pointer was
  destroyed is unreachable, and the part-inventory check passes.
- **Compare auxiliary part CONTENT, not the inventory.** Empty footnote and header parts exist as
  boilerplate in any Word-written `.docx`.
- **Render BOTH documents and compare page against page.** Inspection finds what looks wrong; only
  comparison finds what is *missing*.
- **Reconcile any tracked-change count drop** against legitimate coalescing before calling it loss.
- **Identical paragraph properties are not evidence that layout survived.**
- **Never compare properties BY PARAGRAPH INDEX across the definitions block** — that step permutes it.
  Match definitions **by term**.
- **Re-measure, do not re-read.** Re-measuring found defects that re-reading a previous report never would.

**Forensic logging is a primary method, not a nice-to-have.** When observing the skill on a real document,
log **everything** — every file read, every tool call, every reasoning step, every gate firing, every wasted
call and iteration loop, every ambiguous instruction, plus per-step token and time cost. **A summary is not
a log.** Every real fix in the rev16→rev44 history came out of exactly this kind of observation. **And take
counts from the log analyser, never from the narrative:** across one batch the self-reported note totals were
14 / 12 / 11 against the analyser's **18 / 16 / 11**, and one document's non-zero exits were reported as 4
against a real **7**. The narratives remain the only source for *reasoning*.

### 5.7 The test corpus

**Eleven real client documents, outside the repo tree, permanently.** Referred to **by instrument class and
language only, per §5.4** — never by filename, because the filenames carry counterparty names, and never by
subject matter. **The *what it uniquely tests* column is a property of the file, not of the deal**, which is
why it stays.

| doc | document | paras | what it uniquely tests |
|---|---|---|---|
| D01 | Power of Attorney (Hungarian) | 24 | the shortest run; batch position 1 |
| D02 | Agreement (Dutch) | 316 | the richest: heavy tracked changes, 24 highlights, comments, full auxiliary parts |
| D03 | Agreement (Norwegian) | 98 | **the only language with NO sub-lexicon** — the sole evidence for *"others translate very well too"*, and the only isolation of the lexicon's second layer |
| **D03B** | **the same document, batch position 3** | 98 | **the most controlled pair in the project** — batch position is the only variable |
| D04 | Contract (Spanish) | 137 | the heaviest tracked-change load |
| D05 | Deed (Italian) | 241 | 160 bold runs; the lost-footnote case |
| D06 | Contract (Italian) | 613 | **the only TRUE legacy binary `.doc`** — the sole exercise of the conversion path; the largest document |
| D07 | Novation (English) | 97 | **source language == target language**, which nothing in the pipeline notices |
| D08 | Agreement (Finnish) | 57 | comments plus highlights |
| D09 | Document (Hungarian) | 96 | the most tables; **four known-answer judgement calls**, which is why it is the Step C arm document |
| D10 | Guarantee (Polish) | 45 | delivered both the positive and the negative highlight control in one file |
| D11 | MOU (Japanese) | 43 | **the only non-Latin script**, plus tracked changes |

**Variant assignment — 3 US / 8 UK, and the principle is not arbitrary.** The **hard technical paths run on
UK**, the default, so a failure is unambiguously a pipeline defect rather than a variant defect; **US goes to
terminologically rich but technically straightforward documents**, so variant divergence is what gets tested.
**US: D04, D05, D07. UK: the other eight**, including both hard paths.

**Two things the corpus cannot reach, so they need synthetic fixtures:** there are **no `Symbol` or
`Wingdings` runs anywhere**, so the Greek-glyph defect cannot be reproduced from a real document; and
content controls, smart tags, images with alt text and charts with titles appear in none of the eleven.

### 5.8 How a change is actually tested

**`STEP-B-ANALYSIS.md` §4 owns the method per branch kind. This is the principle behind it.**

> **THE TRICK: FREEZE THE TRANSLATED INTERMEDIATE FROM AN EXISTING RUN.** The expensive, non-repeatable part
> of a run is the translation — a model, 20 to 50 minutes, and 40% of paragraphs differing between two runs.
> But **mechanically two runs are identical**, and that is measured. So with the translated notes frozen,
> **the whole mechanical half — put the English back, tidy up, reorder, auxiliary parts, repackage — becomes
> a deterministic function.** Run the scripts, compare the bytes. Seconds, repeatable, no model, no Cowork.
> **The frozen intermediates already exist from the July runs.**

**Two tiers, and the distinction is a confidentiality requirement rather than a convenience:**

| tier | what | committable? | when it runs |
|---|---|---|---|
| **Synthetic** | hand-built documents with no client text, in `tests/fixtures/` | **YES** — and these are what runs on every change and what `git bisect` uses | every commit |
| **Real, frozen** | the frozen intermediates from the eleven corpus documents; they contain the **full client text** | **NEVER.** They live with the logs, outside the repo, and must be excluded **by path** before `git init` | before every merge |

**Negative test inputs are mandatory, not optional.** Nothing in the shipped package can currently make a
check fail, so a fixture set of only-passing cases produces tests that pass because nothing is being tested.
**One input per check, built to violate that check's stated pass condition.**

**And for any change claimed to be non-behavioural, prove it** — SHA-256 compare the affected files and
byte-compare pipeline output on the fixtures. That discipline is exactly what makes `git bisect` possible;
never delete it in the name of tidying up.

### 5.9 Gate philosophy and error handling — do not weaken this

- **A gate firing is the script doing its job.** Gates print `SKILL GATE FIRED — INTENTIONAL BLOCK, NOT A
  SCRIPT ERROR`. **Never work around a gate** by patching the script, passing an override flag "just this
  once", wrapping the script in Python, or skipping the validator. **Fix the input and re-run.**
- **Never let the translator alter a source-faithful translation to satisfy a linter.** If a QC finding
  conflicts with fidelity, **fidelity wins and the linter gets fixed.**
- **A gate CAN be wrong in scope, and nothing in the skill currently says so** — its language actively
  discourages the conclusion, and the operators improvised as a result. **The remedy is to fix the gate,
  never to bypass it, and never to alter a faithful translation to satisfy it.** Surfacing that rule where
  the operator meets the gate is **the cheapest fix in the project** and it makes every scoping defect
  recoverable instead of expensive.
- **Heuristic checks have false positives and false negatives** — validate a heuristic against ground truth
  before trusting it. **A language-dependent check does not degrade to nothing; it degrades to a confident
  wrong answer**, which is worse. Every one must announce that it is guessing and refuse to print CLEAN for
  a language it does not support.
- **Script-integrity failure means a corrupted install.** Stop and reinstall; never work around it.

### 5.10 OOXML hard rules — all confirmed in production

- **Never use `xml.etree.ElementTree` to write OOXML.** It rebinds namespace prefixes on serialisation and
  Word rejects the file. Use lxml or pure string/regex edits, and keep an `assert 'ns0:' not in xml` guard
  after every edit.
- **Never let an XML regex cross an element boundary.** A non-greedy `.*?` under `re.DOTALL` will silently
  jump runs. Two production incidents: one inserted **464** highlights and scrambled paragraph order; one
  silently swallowed an `"E-mail address:"` label. Bound it with a negative lookahead —
  `(?:(?!</w:r>).)*?`. Prefer lxml for structural edits.
- **Never match `<w:t>` as `<w:t[^>]*>`** — that also matches `<w:tcPr>`, `<w:tbl>` and `<w:tab/>`. Use
  `<w:t(?:\s[^>]*)?>`.
- **`<w:b w:val="0"/>` means bold OFF.** Any bold check must read `w:val` and treat `0|false|off` as
  not-bold. The same applies to `w:i`, `w:strike` and `w:u`.
- **Count tab CHARACTERS separately from tab STOPS.** A `w:tab` inside `pPr/tabs` is a stop and carries the
  same tag name as a rendered tab, so a naive iteration sums the two.
- **Table-nested paragraphs are first-class.** Signature blocks, schedules, form fields and party grids live
  in `w:tbl/w:tr/w:tc/w:p`. Extraction and apply must both recurse, or those paragraphs ship untranslated.
  **The same asymmetry exists for containers the skill never lists** — `w:sdt` content controls and
  `w:smartTag`.
- **Text-matching, not index-matching, is why this works.** One real document produced 577 JSON entries for
  564 XML paragraphs — a 6–13 position drift that under index-matching corrupted styles, numbering and
  indentation and left the last ~60 paragraphs in the source language. **Do not reintroduce index-based
  application.**
- **Non-Latin tracked changes need the visible-space plus ZWSP hybrid.** Source text in CJK carries no
  inter-word whitespace, so `.strip()` in apply eats the operator's authored boundary space. A zero-width
  space (U+200B) is Unicode category `Cf`, so `str.isspace()` is False and it survives `.strip()`. **Do not**
  iterate through NBSP, ideographic space or thin/en/em spaces — that path is documented and dead. **And a
  ZWSP in the deliverable is always a defect:** the fix is a pre-repack scrub, not a prohibition on the
  device.
- **Terminology rewrites must protect multi-word defined terms.** An `Annex → Schedule` rule collided with
  the defined term "Service and Maintenance Schedule", and a blanket revert produced "Annexs". Use ordered
  rules with negative lookbehind.
- **Upstream PDF→Word conversion is lossy and lies about it.** Where the source was itself converted from
  PDF, highlighting, strikethrough, hyperlinks, checkboxes and table borders may already be gone,
  *inconsistently*. **Never attribute such a loss to the pipeline without rendering the SOURCE Word file.**
  Keep the buckets distinct: **A** = introduced by us, **B** = inherited.

### 5.11 Skill-authoring conventions

- **No changelog inside the archive, ever.** The packaged `.skill` contains zero changelog entries, and
  there is no `CHANGELOG.md` going forward. **The rev16→rev44 history is not committed either** — it stays
  in the archived revisions, outside the repository *(§5.4(c))*.
- **No confidential data and no real-document examples** — §5.4.
- **Anti-drift safeguards are load-bearing.** The layered defences — mandatory step-file reads, the five
  hard rules, auto-invoked gates, per-batch validation with the batch-cap state file, gate semantics,
  integrity checks, transcript-mode discipline, the compaction-resume trigger — **exist because of repeated
  real post-mortems. Do not remove or soften any of them** as part of an Opus 5 or context-optimisation
  change unless proven redundant by testing.
- **Keep the eleven-step structure and the gate nomenclature stable** unless there is a positive reason to
  change them. **No renumbering of the steps:** a renumbering invalidates every step id in the existing
  forensic logs, which are the project's only behavioural evidence base. The cheap version first — fix the
  hole and the inconsistent letters.
- **The shipped run report is metadata-only by construction.** Steps run, per-step duration, gates fired and
  what satisfied them, validator warnings, iteration loops, integrity results, file manifest. **Never
  document text, never filenames. And no third-party telemetry, ever** — this skill processes privileged
  documents. *(It is the same artefact as the forensic log, so designing the log format well gives the
  shipped report for free.)*
- **No sub-agents inside the skill** — §3 of `OPUS-5-MIGRATION.md`.
- **A shared capability lives in one place.** This is a rule for **our** maintenance of the artefact, not an
  instruction to the skill's operator, and it belongs here rather than in a shipped step document —
  putting a maintenance convention into a shipped document is how a 221-entry phrase map came to be a de
  facto thirteenth dictionary inside the scripts folder.

### 5.12 The audit gate — for any analysis deliverable

**Wouter's standing requirement:** *"triple check, do a deep audit and verify your summary. This summary is
the basis of the changes, and I REALLY don't want it to contain errors or omissions."*

**It exists because the same request has found real errors EVERY time it has been made** — a note count
taken from another document's report, two runs described as one operator, a tab count that was one
paragraph's rather than the block's, a character count off by one, **a lexicon instruction that does not
exist in the file it was attributed to**, keystone totals that summed to 134 against a real 122, **seven
per-file byte counts written into a table without ever being measured**, and three stale counts in the build
plan. **None would have been caught by re-reading.**

**So the gate prescribes the method that actually worked, not diligence in general:**

1. **RE-MEASURE, DO NOT RE-READ.** Every numeric claim re-derived from the artefact by a script written
   fresh. **And where a standing instrument already measures the thing, reproduce ITS answer before trusting
   your own.**
2. **CHECK EVERY CITATION AGAINST THE FILE IT CITES.** If the report says a file says something, **open that
   file.** Note the trap that has caught this project twice: **a search over source counts a mechanism
   wherever a message merely describes it.**
3. **AUDIT THE BOOKKEEPING SEPARATELY FROM THE PROSE.** The errors cluster in counts, id sets,
   cross-references and every claim of the form *"N of M"*. Prose review does not see them.
4. **HUNT OMISSIONS, NOT ONLY ERRORS.** Walk the evidence row by row and confirm each row is either
   accounted for or explicitly recorded as out of scope. **State the arithmetic;** if it does not reconcile,
   the work is not done.
5. **STATE CONFIDENCE PER CLAIM, and distinguish MEASURED from INFERRED.** A claim asserted with the
   confidence of a measurement, when it is an inference, is exactly the error that mis-scopes the next step.
6. **NEVER A TWO-WORD NEEDLE.** Eleven checks in this project have passed for the wrong reason. **Normalise
   whitespace and emphasis by default, and make every needle a phrase that could only appear if the thing is
   actually carried.**
7. **RUN BOTH CONFIDENTIALITY CONTROLS, THE PUBLICATION CHECK AND THE RELEVANT VALIDATORS** on every
   committable file at the end.

**Report the audit's findings openly, including its own corrections. An audit that reports NOTHING found
should be treated as evidence the audit was too shallow, not that the work was clean.**

**The standing instruments live in `temp/` and are all re-runnable.** Run these after editing any of the
committable documents:

```bash
uv run python temp/a3_md_tables.py CLAUDE.md FINDINGS-REGISTER.md A3-STRUCTURAL-ANALYSIS.md STEP-B-ANALYSIS.md DECISIONS-LOG.md OPUS-5-MIGRATION.md
```

```bash
uv run python temp/publication_check.py
```

**Before editing `FINDINGS-REGISTER.md`, and after, run its validator** — hand-editing it has produced quiet
errors twice, and two of the validator's checks exist because they caught real ones. Expect **PASS, 0
failures, 0 warnings**:

```bash
uv run python ../legal-translation-private/tools/audit_register.py
```

**And after editing `STEP-B-ANALYSIS.md`, run its own suites — they live in `tools/` and are COMMITTED as
of 2026-08-11**, so a fix to one of them survives the session that makes it. Six of them:
`tools/stepb_harvest.py` (63 prescriptions from five sources, 0 missing), `tools/stepb_verify.py` (84
claims, and it generates the traceability appendix), `tools/stepb_audit.py` (15 checks),
`tools/stepb_audit3.py`, `tools/stepb_metacheck.py` (**eleven negative tests: it mutates the document to prove
each check can fail, then restores it byte-identically**), and `tools/stepb_refute.py`. **All six pass.**

> **THEY WERE IN `temp/`, WHICH IS GITIGNORED, AND THAT WAS THE DEFECT.** The suites guarding this
> project's three largest documents could not be improved: every fix to one of them died with the session
> that made it, unreviewable and unrepeatable. **Four were left behind and each for a stated reason, because
> a promotion that quietly drops things is worse than none:**
>
> - **`audit_session_stepb.py` — BLOCKED ON CONFIDENTIALITY and it stays in `temp/` permanently.** It holds
>   **two corpus subject-matter descriptors**, which is precisely the class §5.4 says the 93-pattern name
>   scan is structurally blind to. It is the file this session's `§`-resolver fix was made in, so **that fix
>   does not survive** — the honest cost of the block, recorded rather than worked around.
> - **`stepb_audit2.py` and `stepb_audit2b.py`** — both crash looking for a heading deleted in the
>   2026-08-05 reorganisation. Broken on `main` today, and one-off session scripts rather than standing
>   instruments.
> - **`stepb_measure.py`** — three hard-coded register counts that went stale.
>
> **Committing a broken tool into a public repository implies coverage that does not exist**, which is the
> same objection this project raises against a check nobody believes. The `temp/` originals are left in
> place untouched (§5.15) and are now superseded by the `tools/` copies.
>
> **One of the six needed a change before it could be committed at all, and `LEGAL_TRANSLATION_A4` must be
> set to run it.** `stepb_audit.py` hard-coded the **sealed A4 judging directory**, whose location §1.3
> deliberately keeps in the private `context.md`. It now reads that environment variable, exactly as
> `tools/gate_replay.py` reads `LEGAL_TRANSLATION_LOGS` — **the tool ships, the location does not.**
>
> ```bash
> LEGAL_TRANSLATION_A4="<the sealed directory>" uv run python tools/stepb_audit.py
> ```
>
> **Without it the script exits 1 and prints a banner saying check 10 cannot be completed** — it does NOT
> excuse the quotations it could not verify. That distinction was got wrong first: the initial version
> reasoned that a quotation whose only source is unreadable is *void rather than false* and skipped it, which
> looked principled and **immediately dropped `stepb_metacheck.py` from 10 of 10 mutations detected to 9.**
> Softening a check to make it honest had made it blind, which is the failure this project logs more than any
> other, committed here in one of our own instruments and caught only because the metacheck exists. **An
> unreadable source is not a pass.**

> **`temp/a3_md_tables.py` has now caught five defects nothing else in this project can see** — including a
> four-column row inserted into a two-column table, and an appendix that lost its delimiter row and stopped
> being a table. **The register's own validator passed both.** It should be promoted out of `temp/` into
> `tools/` at branch 0.

### 5.13 The review protocol — for INPUT POINT 2

**The twelve-document review is complete. This is kept because Step C repeats it.** Only the rules that
survived contact with reality are here.

**The loop, per document.** A helper opens the original and the translation side by side, read-only, with no
filename typed. **Wouter gives his input in whatever shape he likes** — prose, a list, a screenshot, a
one-liner. **Claude does the structuring.** **Open the NEXT pair immediately on receiving his feedback,
before analysing anything**, so he reads document *n+1* while Claude analyses document *n* — under the naive
loop each sat idle through the other's work, which over twelve documents was the single largest waste. **But
finish document *n*'s analysis and update the register before his next feedback lands.** Run the validator
after each edit.

**The three-way triage, applied to every point he raises:**

1. **Already reported** — confirms both instruments. Tick it into the existing row.
2. **Missed, but the method COULD have caught it** — a gap in the *grading instrument*. Fix the method, then
   **re-check the earlier documents for the same thing**.
3. **Missed, and the method STRUCTURALLY could not.** **Expect most of his findings here**, because the
   translation criterion is graded on a *sample*: Claude does not re-translate 230 paragraphs and judge
   whether they read as a lawyer would write them. **That axis is his alone, and it is the whole reason the
   review is worth doing.**

**Two artefacts, two rules.** His raw feedback and Claude's per-document analysis go to the **logs folder
and are never committed** — he quotes real clause text and party names. Only the **sanitised conclusions**
enter the register, origin `WvdB`, with names *and commercial terms* genericised.

**Order: ascending complexity**, so the method is proven before the largest document. **The D03/D03B pair is
reviewed together and deliberately NOT blind** — same document, batch position the only variable, and the
anchoring that would spoil a blind review is exactly what makes that comparison work. Say so in the write-up.

**The blind rule:** Wouter forms his view **before** reading that document's grade report. Claude must not
summarise the grade, name its findings, or hint at them before he has spoken. Knowing a *score* is far
weaker anchoring than reading *findings*, so whether to skip the score is his call, not a rule. **Any tool
touching a blind review inherits the blindness requirement** — a convenience field in the review helper once
named four documents' findings outright and spoiled them before anyone noticed.

**What Claude must not do:** defend the grade (if he finds something the grade missed, that is the review
working) · modify the source or delivered documents (read-only; they are the evidence) · start fixing the
skill (the review feeds the analysis, not a patch).

### 5.14 Adding to this file

**A rule, because this file grew to 168 KB and 35 factual errors before anyone checked it.**

1. **Decide WHERE it goes before writing it.** Everything belongs in **§2 to §6, by subject**. §1 is
   navigation and §7 is the handoff and nothing else. **If you cannot name the section, you do not yet know
   what the thing is.**
2. **If it is extensive, ask Wouter first whether it should be its own document** rather than a section
   here — as was done for the Opus 5 workstream and the decisions log. A charter that carries a workstream
   inside it stops being readable and starts going stale.
3. **Never restate what another document owns.** Point at it. The one thing this file may carry about
   another document is *what it is for* and *where in it to look*.
4. **Re-run the claims check and the table check after any substantial edit** — §5.12. A count typed into
   prose here is a count that will be wrong within a week.

### 5.15 Inherited house rules

- **Never delete files you didn't create.** Especially: the archived `.skill` revisions and the test corpus
  are irreplaceable.
- Run Python via **`uv run`**.
- New scratch scripts go in **`temp/`**.
- **Verify** that the solution fully addresses the request before marking anything done.

---

## 6. File, folder & repo structure

### 6.1 The design principle, and what it is not

Goal: a structure **optimised for the context window** — small files, few loaded at once, the right file
loaded at the right step. **Do NOT reduce the file count for its own sake.** The current design — 154 small
sub-lexicons rather than a few large ones, eight step documents rather than one monolith — is deliberate and
**A3 confirmed it is correct in principle.**

**Eleven structural questions were open until A3 answered them. They are settled; do not re-open them.**
The measurement behind each is in `A3-STRUCTURAL-ANALYSIS.md` §5.

| # | the question | the settled answer |
|---|---|---|
| 1 | `SKILL.md` is 57 KB and always loads | **Re-motivate, do not cut for context.** The live reasons to shrink it are **findability and truncation, not tokens** |
| 2 | `04-translate.md` is the second-largest thing loaded at the worst moment | **Change — as a consequence of the formatting fix, not as a size exercise.** Its longest rule is 8,028 bytes and exists *only* because extraction cannot compute effective formatting; it collapses at branch 17 |
| 3 | the step-number gaps in filenames | **Keep** — intentional, not a defect. But packaging eleven steps into eight files *is* a live defect |
| 4 | 176 of 198 files diverge over ~3,600 lines | **Change.** Both figures reproduce exactly: **3,593** changed lines whole-tree, **420** in the scripts folder. The line count is the *easy* part of the price |
| 5 | one domain reference has no matching sub-lexicon | **Keep** — the only such asymmetry in either direction, documented and deliberate |
| 6 | the scripts carry integrity sentinels — is the constraint live? | **Keep and extend.** 20 of 20 scripts protected and truncation-tested; **178 of 198 files unprotected**; three files per tree past the only observed cut. **And the detection is defeated at the point of USE as well** — one exit code is downgraded to a warning, another guard runs after the work it protects |
| 7 | the two packages are not at the same revision | **Change, and wider than recorded** — the UK tree is behind in *executable logic*, not just spelling data |
| 8 | the UK sub-lexicons have lost dual-variant annotations | **Change.** The shortfall is **158** across sub-lexicons and **165** whole-tree — **and the reference layer has eroded too**, which the original observation denied |
| 9 | the 420 changed script lines are almost entirely comments | **Falsified in part** — true of 7 of 15 scripts; **3 differ in executable content** |
| 10 | **Wouter's hypothesis** — almost none of the UK/US divergence is load-bearing | **Confirmed for `SKILL.md`** (31 of its 49 changed line-pairs *are* the variant-selection logic); **refuted everywhere else.** Converging is right, but it is an **editorial adjudication, not a merge**, because the two general-legal references carry *different advice* |
| 11 | host detection enumerates products, not capabilities | **Change** — a documentation-only fix. Keep the user-facing warning text unchanged |

### 6.2 The skill tree today

**198 files per variant, both trees, re-measured from the two rev44 publication archives.** Exact bytes.

```
                                    UK bytes    US bytes
SKILL.md                              57,269      57,532   # always loaded — discipline, hard rules, pipeline map
skill-docs/                          128,106     131,115   # 8 step docs, read in full at their step
  01-setup-and-extract.md             10,168      10,168   #   Steps 1 + 2  (+ Step 1a host-mode warning)
  03-lexicons-and-segments.md         14,632      14,759   #   Steps 3 + 3b
  04-translate.md                     47,707      50,463   #   Step 4 — the heaviest step
  04b-translate-gates.md               7,019       7,150   #   Steps 4b + 4c + 4d
  05-apply.md                          5,255       5,255   #   Step 5
  06-postprocess-and-reorder.md       12,814      12,811   #   Steps 6 + 7
  08-aux-and-quality.md               15,905      15,903   #   Steps 8 + 9
  10-repack-and-validate.md           14,606      14,606   #   Steps 10 + 11 (+ 11a diligence audit)
references/                          444,766     446,998   # 15 cross-language English domain lexicons
scripts/                             518,726     525,629   # 20 Python scripts (extract → apply → validate → repack)
sub-lexicons/                      2,502,968   2,506,476   # 154 files = 11 languages x 14 domains
TOTAL                              3,651,835   3,667,750   # ~3.7 MB unpacked, either way
```

**Latest published version: `v2026.04.22-rev44`** (13 May 2026). 198 files, 20 scripts, per variant.

> **Three files per tree sit past the only install-truncation position ever OBSERVED (byte 55,466)** — the
> apply script, `SKILL.md` and the post-processing script. The larger figure this project has measured
> against since rev30 is a *reported* number, not an observed one, and nothing is near it.

### 6.3 What the build changes — the envisaged tree

**Derived from `STEP-B-ANALYSIS.md` §2 and §3, branch by branch.** Two honest caveats first: the build plan
**never commits to a specific new script file** — several branches add a check and leave the packaging of it
open — so **the file count per tree will rise, by an amount the plan deliberately does not fix.** And this
table is a projection of decided work, not a measurement.

| what changes | which branch | effect on the tree |
|---|---|---|
| **`SKILL.md` and the step documents** gain the scope rule, the sanctioned way out, the delivery-notes format, the declared modes, the furniture checklist, and the honest statement of which hard rules the gates actually enforce | 3, 4, 13, 17, 19 | **content, not count.** `04-translate.md` **shrinks by ~8 KB** when its longest rule collapses at branch 17 |
| **The apply script** stops deleting what it does not recognise; gains a shared, explicitly tested container inventory that fails loudly on anything unlisted; then consumes per-span computed formatting | 6, 7, 16 | rewritten in part; **no new file** |
| **The extraction script** emits effective computed formatting per run, resolving the style chain and character styles | 15 | **the notes format changes** — the frozen intermediates must be regenerated **from the archived runs, never by re-translating** |
| **The tidy-up script** is split into mechanical and opinionated passes and records every edit it makes, machine-readably | 9, 10 | rewritten; **a new run artefact in the workdir**, not in the tree |
| **New checks:** extraction completeness · the delivered-document character-exact diff · the layout-effect flag · language declaration | 8, 11, 12, 18 | **the largest addition. Some will be new scripts; the plan does not say how many** |
| **Existing checks get honest exit codes**, a failed integrity test stops the run, and the skipped-by-omission check refuses | 5 | small edits in three scripts |
| **The reference layer** gains the document-furniture conventions; the 221-entry phrase map trapped in a script is reconciled to them | 19 | `references/general-legal.md` grows; **no new file — deliberately no separate furniture document** |
| **The two trees are reconciled**: the missing dual-variant markers restored — **158 in the sub-lexicons, 165 once the reference layer is counted in** — the drifted rule tables converged, and **the three drifted scripts parameterised so one copy takes the variant as an argument** | D1 | **the divergence collapses**; scripts stop being two copies |
| **A manifest per tree**, plus **one version identifier replacing eighteen revision tokens**, plus integrity coverage past the scripts folder | D3 | **+1 file per tree, and it is a precondition** — a Markdown file cannot carry its own integrity guard |
| **`README.md` and `LICENSE`** per tree, excluded from the `.skill` archives | step 1 onward | **+2 files in the repo, 0 in the archive** |

**So, in one line: the tree stays the same shape.** No new directory, no reorganisation, no renumbering —
**198 files becomes roughly 200 to 205 per variant**, one step document gets materially shorter, the
reference layer gets materially richer, and the two trees stop diverging. **The context design is
preserved intact**, because A3 measured it as correct and the constraint it was built for was never the
binding one.

### 6.4 The repository — CREATED 2026-08-06, PUBLIC SINCE 2026-08-07

**One monorepo holding both full trees side by side. No build step. Plus an automated parity check.**
Chosen over two independent repos and over a shared-core + generated-variant build.
**`github.com/wjvandenberg/legal-translation-skill`** — distinct from the two public distribution repos.

> **It was created private and flipped public once branches 0, 1 and 2 had merged**, which is the cheap
> cheap moment the plan had named: the history was eight commits long and held only the unmodified trees plus the
> instruments. **The flip was measured, not assumed.** Every blob in every commit was scanned: **security
> 0** · **nothing outside `uk/` and `us/` matched any probe** · no file had ever been deleted, so nothing
> was hiding in history · and the four superseded skill files are **byte-identical to the published rev44
> archives**, which have been downloadable for months. **Making a repository public exposes the whole
> history, not the current state** — which is why the measurement was of the history and not of the checkout.

```
legal-translation-skill/          # today: this folder, with no .git in it
├── CLAUDE.md                     # the charter — never ships inside a .skill
├── OPUS-5-MIGRATION.md           # goal (iii)
├── DECISIONS-LOG.md              # the dated record
├── STEP-B-ANALYSIS.md            # the build plan
├── FINDINGS-REGISTER.md          # the evidence base
├── A3-STRUCTURAL-ANALYSIS.md     # the structural measurements
├── README.md                     # describes the MONOREPO, for developers
├── .gitignore
├── uk/                           # A COMPLETE SKILL TREE — 198 files + README + LICENSE
│   ├── SKILL.md
│   ├── skill-docs/  references/  scripts/  sub-lexicons/
│   ├── README.md                 # the PUBLISHED readme → goes to the public UK repo root
│   └── LICENSE
├── us/                           # identical shape, US-default
├── .claude/                      # settings.json wires the PreToolUse evidence guard;
│                                 #   evidence-dirs.local is gitignored, its .example is not
├── tools/                        # never ships — 29 scripts, in three groups:
│                                 #   THE BUILD GUARDS — parity_check · check_coverage ·
│                                 #     confirm_failure_chains · freeze_intermediates ·
│                                 #     audit_branches · cycle_evidence · precommit_gate ·
│                                 #     md_tables · claudemd_claims · claudemd_disposal ·
│                                 #     audit_register · install_hooks · scan_trees ·
│                                 #     gate_replay · reachability · xref_check ·
│                                 #     string_only_edit · hooks/ (3)
│                                 #   CONFIDENTIALITY — leakage_scan · publication_check ·
│                                 #     descriptor_shape_sweep · script_committability ·
│                                 #     changelog_confidentiality · evidence_ls
│                                 #   THE STEP-B SUITES, promoted out of temp/ 2026-08-11 —
│                                 #     stepb_harvest · stepb_verify · stepb_audit ·
│                                 #     stepb_audit3 · stepb_metacheck · stepb_refute
├── tests/                        # never ships — run_tests · make_fixtures · negative_inputs ·
│                                 #   fixtures/ (11 SYNTHETIC .docx) · baselines/ · NINE test_*.py ·
│                                 #   probe-5b/ — the rule-5b behavioural probe: two rigged
│                                 #     documents, a pre-registered SCORING.md, preflight.py,
│                                 #     which says whether either rig actually fires, and
│                                 #     preflight_metacheck.py, which proves it can say no
└── temp/                         # gitignored scratch — it already exists and sits INSIDE the repo root
```

> **The tools count read 16 against a real 23, and the tests count read four against six.**
> Corrected 2026-08-11 by listing the folders rather than adding to the figure that was
> there — the same error shape as the register's cluster-F count, which went stale three
> times because each session added to the previous stale number instead of counting.

> **ONE CORRECTION TO THE ORIGINAL LIST, and it is a rule rather than a typo.** `confidentiality_sweep.py`
> was named for `tools/` and **may never be committed** — it holds a real corpus descriptor inline, measured
> 2026-08-06 by extending the committability probe to the private folder for the first time. It stays
> outside, with `corpus_descriptor_scan.py` and `confidentiality_review.py`, and the gate calls all three by
> path. **The rule that decides it is unchanged — *does this file hold one real string per pattern?* — and
> `leakage_scan.py` is the pattern to copy: the scanner ships, the list never does.**

> **There is no `docs/history/`, and that is a decision rather than an omission** *(Wouter, 2026-08-06)*.
> The earlier layout carried one, to hold the recovered rev16→rev44 changelog. **It is not committed** —
> §5.4(c).

**The load-bearing property: `uk/` *is* the publishable tree.** No assembly, no generator. **`tools/` and
`tests/` are siblings of the variant trees, never inside them**, so nothing development-only can leak into a
shipped skill.

**What this preserves, all deliberately:** the 154 separate sub-lexicon files (the context design is the
point) · **both the US and the UK term in every lexicon row** (a quality requirement, not a formatting
preference) · **what you see in the repo is what ships** · and the two existing public repos keep their
URLs, descriptions and install instructions.

**What it adds:** **one pull request touches both trees**, so a fix cannot land in one variant and be
forgotten in the other — which is exactly what happened once and shipped to a client. Plus the **parity
check** at branch 2.

**What it costs, accepted knowingly:** the content is still edited twice. This layout makes forgetting hard;
it does not remove the duplication. **Removing it — one source with generated variants — is deferred with a
trigger, not dropped:** revisit when the reconciliation's row-by-row adjudication is done and the 618-pair
residue is classified, because that classification is the deciding number and the reconciliation produces
it.

**Two points where the earlier layout decision has been overtaken, and this is the current version:**

1. **The six analysis documents sit at the repository root**, beside `CLAUDE.md`. The 2026-07-28 layout
   predates all but one of them. *(If they ever crowd the root, `docs/` is the obvious home — but a move
   must be one commit, by script, and every cross-reference re-checked.)*
2. **`.gitignore` is by path, not by extension.** A blanket `*.docx` rule would block the synthetic test
   fixtures while doing nothing about a real client document that had been renamed. Ignore **paths** —
   `temp/`, the test-document folder, the logs folder, `*.local`, **and the frozen intermediates** — and let
   the pre-commit scan be the actual control.

### 6.5 What never enters the repository

**Three sibling folders, outside the repo tree — not merely gitignored.**

| folder | what is in it | why it can never be committed |
|---|---|---|
| **the private folder** | `context.md` (the real paths, the employer, the corpus composition this public file generalises) · `leakage-names.txt` · **`corpus-descriptors.txt`** · the grader backups · the harness and its changelog · the `claude-md-archive` · the whole A4 set and its twelve tools · the shared tooling | it holds the two scan lists and the material they exist to protect |
| **the logs folder** | the raw A1 forensic logs · the grade reports · the narratives · the renders · Wouter's review feedback · **and the frozen intermediates** | every one of them quotes real client text. The frozen intermediates are the most content-rich files the project has ever produced |
| **the test-document folder** | the 11-document corpus, pristine | **the filenames alone carry counterparty names** |
| **the archived `.skill` revisions** | every packaged revision, and **the rev16→rev44 changelog carried inside them** | the changelog names real documents and parties — measured, §5.4(c). It was an input to the structural analysis and the build plan; **it is not a deliverable** |

**And one more, outside all of them:** the two rev44 `.skill` archives, which are the code baseline and were
the blind review's only reading material.

**A pattern worth naming rather than the instances behind it: a working folder shared between sessions
accumulates unrelated matter.** Two client documents from an unrelated matter once appeared in an evidence
folder because a session was pointed there by accident, and a session title once carried a real counterparty
name. **Session metadata is reachable by neither scanner nor the location rule.** Any glob over an evidence
folder must be explicit about which files it expects.

### 6.6 Publishing from the monorepo

Two scripts in `tools/`, run at release time. **The deliverable does not change:** still two independent
`.skill` archives of 198-odd files each, uploaded and installed separately.

1. **`tools/package.py`** → one `.skill` per variant. Each is a zip of the corresponding variant tree
   **excluding `README.md` and `LICENSE`** — verified: the published archives contain 198 files and carry
   neither.
2. **`tools/publish.py`** → copies the contents of `uk/` (this time *including* `README.md` and `LICENSE`)
   into a local clone of the public UK repo, commits and pushes; same for `us/`. **Deliberately a plain
   copy-and-commit rather than a subtree**, so Wouter can read the diff before it pushes.

**Three public repos will then exist, and users need that disambiguated:** `legal-translation-skill` is the
**source**; the two variant repos remain the **install channels**. **Every README must say which is which.**

---

## 7. Current status

> **This section is the handoff and nothing else.** Everything that has been done is §2.3; everything still
> to do is §3. **Replace this section at the end of every session — do not append to it. Every handoff opens
> with the standing block below, verbatim and unedited** — it is the first thing the next session reads, and
> it exists because a session that had read §5.1 still ran three branches without it.

### HOW THIS SESSION WORKS — read before touching anything

**EVERY BRANCH IS Explore → Plan → Code → VERIFY → TEST → Commit. Including documentation:** this file,
`STEP-B-ANALYSIS.md`, the register, a README. Prose that is wrong misdirects the next session exactly as a
broken script does.

**BEFORE ANY CODE, open a task list** carrying all six phases plus §5.3's applicable items, and cross each
off **only against the output of a command you have run.** An item that does not apply is crossed off as a
**declared N/A with its reason**, never omitted.

**PLAN MEANS WITH WOUTER, BEFORE CODE.** Autonomy covers running translations and grading them. It has never
covered code or documents. Present the plan — what it builds, what it must **not** do, what counts as done —
and wait.

**A BRANCH WHOSE VERIFY AND TEST ARE NOT CROSSED OFF IS NOT FINISHED**, whatever its diff looks like. Open
the pull request; do not call it complete.

**RUN, DO NOT READ.** Every error worth finding in this project has been found by running something.
Re-reading has never found one.
### HANDOFF — 2026-08-21. BRANCH 14's `quality_check` SLICE IS BUILT AND NOT MERGED.

**PR #25 was merged first** — it repaired two numbered lists a blind `str.replace` had
damaged, and every numbered list in this file is now sequential. **Then branch 14's slice
was built: EIGHT false-positive fixes, each with a test proving it still catches its true
positive.** That discipline is the branch, and it is why the branch is mostly tests.

| | |
|---|---|
| **branch** | `feature/check-scoping-quality-check`, from `main` @ `2178cce` |
| **what it fixes** | L1 · G11 · G10 · M1 · C9 · F15 — plus **G5 and G9**, added on Wouter's decision |
| **the measured effect** | the recorded corpus goes **44 findings → 16**, and **D07 becomes clean** — blocked deliverables 4 of 13 → **3 of 13** |
| **NEXT** | **Wouter's review and approval. Nothing technical remains.** |

### WHAT MOVED, MEASURED — the numbers not to re-derive

`tools/qc_census.py` is the instrument and it now reports BOTH sides, so the pre-branch
figures stay reproducible from the recorded evidence rather than from a memory of them.

| rule class | before | after | after, with `--original` | what closed it |
|---|---|---|---|---|
| truncation | 17 | **0** | 0 | L1 (9, method A) · G11 (5) · G5 (3) |
| numbering | 11 | 11 | **0** | M1 — needs the new `--original` flag |
| internal_article_refs | 15 | 15 | 15 | **nothing — this is the residue, now register G12** |
| formatting | 1 | 1 | 1 | **nothing — residue, G12** |
| **TOTAL** | **44** | **27** | **16** | |

Per document, with `--original`: **D03 1 · D05 2 · D06 13 · D07 0**. Proved end to end by
`temp/b14_m1_endtoend.py`, which runs the shipped command line rather than calling the
function: D05 5→2, D06 21→13, all eleven numbering findings gone, and the notice that says
the comparison did not happen goes from printed to silent.

### THE FOUR THINGS THAT WOULD OTHERWISE BE RE-DERIVED

1. **L1's fix had four hidden decisions and one of them is a negative result.** Pairing on
   the declared English leaves **46 of 1,158 eligible entries unpairable**, and **neither
   the accept-all nor the reject-all reading recovers a single one** — so the tracked-change
   explanation is refuted. A four-key ladder (exact · containment · prefix · tail) was built
   and measured to add **nothing**, so it was dropped. The shipped rule pairs on the declared
   English and falls back to the entry's own `en`, which judges **every** entry and adds no
   finding the paired route would not have produced.
2. **G9 IS HALF-CLOSED AND THE OTHER HALF CANNOT BE CLOSED BY SCOPING.** `en_segments` carry
   exactly two keys — `type` and `en`, on 412 of 412 segments across all 13 workdirs. The
   source text the alpha-collision rule would need **is not in the file the check reads**, and
   putting it there is a notes-SCHEMA change, which is branch 15's and invalidates the frozen
   intermediates. **The operator had no third option because the CHECK has none.**
3. **`validate_segment_shapes` finds NOTHING on the whole recorded corpus** — 0 findings over
   81 tracked-change paragraphs — because the recorded `paragraphs.json` is the
   **post-compliance** artefact: the operator satisfied the gate during the run, so the file
   records the outcome and not the collision. **A frozen intermediate cannot reproduce a gate
   that was satisfied while the run was happening.** Know that before branch 11 leans on the
   method.
4. **C9's stated fix is not sufficient on its own.** Reading the translated body gets the
   source language right **2 times in 13**; reading the original gets it right **9 in 13** —
   so the detector was never the defect, its input was. But a wrong SPECIFIC language
   silently SKIPS the correct language's rules while `*` runs them all, so the naive fix
   trades noise for silence. The shipped version passes the language **only where two
   independently-written detectors agree**: 9 agreements (8 correct) and 4 honest
   disagreements. **Norwegian is in neither detector's vocabulary**, so a D03-class document
   correctly reaches the disagreement branch. Making it SAY so is branch 12's.

### WHAT THIS BRANCH FOUND THAT IT WAS NOT LOOKING FOR

- **`STEP-B-ANALYSIS.md` §9.1's arithmetic line was stale by two, and had been.** It read `27 + 27 + 41 + 30 + 43
  = 168` above a generated table already holding 43 in group 3 and 170 in total — and its own
  severity column disagreed with it as well. The tables are generated; that line was typed.
  **`tools/stepb_verify.py` now asserts the line against the tables**, and the assertion was
  proved able to fail before being trusted.
- **I-17, a new OPEN instrument defect: one of the eleven fixtures cannot be rendered at
  all.** LibreOffice refuses `anchors-and-tabs.docx` — and refuses the *original* fixture, so
  the cause is not this branch: it carries `comments.xml` and `footnotes.xml` with no
  relationship part pointing at them. 8 of the 9 valid fixtures render. **Branch 18's test IS
  a render**, so this has to be repaired before it. Left open deliberately — fixing a fixture
  is harness work and several negative-input arms read that file. **The irony is the point:
  the fixture is unreadable for cluster A's own reason — the content is there and the pointer
  is not.**
- **The harness had the very blindness the branch was fixing.** The byte-identity test's
  first notes-builder concatenated `w:t` only, so it declared `Party AParty B` where
  `validate_apply`'s own joiner reads `Party A Party B` — and the gate correctly refused it.
  §5.1's second failure shape, in our own test: ask what else does the same thing.
- **ADDING A REGISTER ROW MOVES COUNTS IN FOUR PLACES AND AN ANCHOR IN A FIFTH — and no two
  instruments agreed on how many.** G12 and I-17 between them moved the register's own
  header, `CLAUDE.md` §1.3 and §2.3, and the build plan's two generated appendix tables. With all
  of those green, **`tools/stepb_audit.py` then found three more** — §5.3's heading, option
  2's pros cell and its ranking row, each still saying 43 or 53. And with THOSE green,
  **`tools/stepb_metacheck.py` reported one of its own eleven mutations INERT**, because its
  anchor carries the group-3 count and that count had moved; re-anchored, 11 of 11 again.
  **So: run the register validator, the claims check, `stepb_audit` AND `stepb_metacheck`
  after any register edit** — each of the last three found what the ones before it had
  passed. A probe whose mutation silently stops applying is a test that has become a
  decoration, and only the metacheck can see that.
- **`validate_apply` already had G10's answer.** It treats `w:tab` **and `w:br`** as
  separators and its docstring documents this exact false positive. So the fix is a
  convergence, not a widening — and that is why it covers manual line breaks too.

### WHAT IS OPEN

1. **The 16 residual findings, now register G12, are UNCLASSIFIED and a script cannot
   classify them.** Each finding embeds 60–70 characters of a real instrument, so deciding
   whether `Article N` is a terminology defect or a civil-law citation needs **Wouter, or a
   sanitised route that reports the citation shape without its text.** Three of the four
   blocked deliverables are still blocked and this is the whole reason.
2. **G9's first half** — needs branch 15's schema change; see point 2 above.
3. **`--original` must be added to Step 9's step document**, or the numbering comparison is
   a flag nobody passes. **NOT done in this branch** — it is a doc change and §4 tests those
   differently. The check announces its own absence in the meantime, which is the mitigation,
   not the fix.
4. **A `probe` origin class for the register** — still unbuilt, still needed.
5. **I-7, I-8, I-9, I-10** — the four open A1 harness defects, unchanged, and still the ones
   that will corrupt Step C. **I-17 is a fifth open instrument defect but is NOT a Step C
   risk** — read §2.3 before quoting "five open".
6. **The six untracked house scripts in `tools/`.** Still untracked, deliberately: they were
   staged by a `git add -A` and **unstaged again**, because whether they belong in this
   repository is Wouter's open question and `tools/run_tests.py` still collides by name with
   `tests/run_tests.py`.

### WHAT WAS RUN

**Verify.** `tests/test_check_scoping.py` — **51 assertions**, and every false-positive
control is proved to have fired against the pre-branch script loaded out of git, so a control
that tests nothing shows up as a failure. It caught one: a G9 control that reversed the
segment types without moving the spaces, which could not have fired. `tests/
test_no_delivered_byte_moves.py` — **12 assertions**: the two reporters leave a workdir
byte-identical, and the two scripts that write produce byte-identical output, including every
member of the delivered `.docx` on two fixtures.

**Test.** 11 of 11 test files · smoke suite PASS on **both** variants · parity check PASS,
0 NEW divergences · `test_baseline_unmodified` 368 of 396 byte-identical with **28 declared**
· register PASS 0/0 · claims 0/0 · tables CLEAN · branch audit and xref 0 · five STEP-B suites
0 · `precommit_gate` **CLEAR on all seven controls**.

**The rendered comparison, which Wouter asked for beside the byte proof.** Five fixtures
repacked with the baseline scripts and with this branch's, converted by LibreOffice and
rasterised at 150 dpi: **every page pixel-identical**. A second instrument agreeing with the
byte comparison rather than repeating it. `anchors-and-tabs.docx` is **declared N/A with its
reason** — I-17, it cannot be rendered at all — and its coverage is the byte comparison,
which does include it.

**No graded run.** Declared N/A: §4 puts script branches on byte comparison, the grader is
frozen at v3 until Step C, and a graded run measures the wrong variable for a change that
provably moves no delivered byte.
