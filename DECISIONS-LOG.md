# DECISIONS-LOG.md — the dated record of what was decided, and why

> **Split out of `CLAUDE.md` on 2026-08-06**, when that file was rewritten around the seven-section
> structure Wouter set. **Nothing was retyped: the log below was moved by script and the move was proved
> content-preserving** (`temp/split_decisions_log.py`).
>
> **What this file is for.** It stops settled questions being re-litigated, and it records the *reasoning*
> behind decisions whose *effect* now lives in the charter. **`CLAUDE.md` §2.5 carries the short list of
> decisions that still bind; this file carries the argument behind each one.** Where the two disagree about
> what was decided, read the dated entry here — it is the contemporaneous record — then correct §2.5.
>
> **Nothing here is a live question.** Every entry is closed. Two entries are recorded as *pre-registered
> controls relaxed after the result was seen*, and they are labelled as such rather than tidied away.

---

# Decisions log

**2026-08-20** — **THE RULE-5b BEHAVIOURAL GATE ON BRANCH 5 IS DISCHARGED, AND RULE 5b IS DEMOTED FROM
"WHAT MAKES BRANCH 5 SAFE" TO "INSURANCE PLUS A FORCING FUNCTION."** Three rigs were built; **every one
turned out to be a check that was WRONGLY SCOPED rather than a deadlock**, and in each case the operator
proved it from the check's own source and exited under rule 5a with full disclosure.

| arm | row | designed to test | what it turned out to be |
|---|---|---|---|
| 1 | F1 | rule 5b | `validate_apply` mirrors `strip_noop`'s rule 1 and never its rule 4 — **scope defect** |
| 2 | L1 | rule 5a (decoy) | scope defect by design; unbuilt, because arm 1 answered it |
| 3 | F28 | rule 5b | `check_truncation`'s method B ignores the `source_data` method A uses — **scope defect, now G11** |

**What the two live runs established.** The installed tree was untouched on both — **198 of 198
byte-identical, measured against a manifest built before the run** — the translation was never altered to
satisfy a check, and both delivered a complete document. On arm 3 all five of rule 5a's conditions were
discharged, including the one that matters most: the notes state that the shipped artefact is unchanged and
will fail identically next time.

**WHY DISCHARGED RATHER THAN SATISFIED, because the distinction is the honest part.** The gate asked for
proof that a model will *use* 5b. That was not obtained and **cannot be obtained from the recorded
evidence**, because three attempts to construct a genuine 5b situation each dissolved into a 5a one. What
*was* established is the gate's underlying **concern** — that branch 5 leaves runs with no legal exit. It
does not: the exit exists, the operator finds it, and it discloses it. **A test aimed at a situation that
does not arise is not a test that failed; it is the wrong test.**

**AND THE PLAN'S REASONING WAS WRONG, which is the part to carry forward.** §2's fourth sequencing fact
treats 5b as what makes branch 5 safe. It is not. **The census measured branch 5's real risk as FALSE-ALARM
LOAD** — checks stopping runs that were fine — handled by 5a and fixed properly by branch 14. Nine
mechanically-confirmed false positives across the whole recorded corpus, all from one rule, with six of ten
reachable documents completely clean.

**5b is KEPT, for three reasons rather than sentiment.** *(1)* **It is what makes 5a safe.** Without it every
complaint becomes a licence to change a checker; with it the operator must first ask whether the checker is
actually wrong. Arm 1's operator said so directly — it began composing a 5b block, then pulled back because
5b's own entry condition required attempted repairs it had not made, which told it it had stopped analysing
too early. **5b did its work by not being used.** *(2)* **Its product is the disclosure, not the escape.**
The register records operators improvising out of closed loops; the rule that a known defect may never ship
unspoken is load-bearing however rarely the channel fires. *(3)* **"Near-unreachable" describes the TEST,
not the rule.** Two of section 5.5 of `PLAN-2-step-b.md`'s three impossible requirements — **F30** and **F33** — remain genuine dead
ends; they simply do not run through a script that returns an exit code, so branch 5 cannot block on them
and this gate could never have reached them.

**Arm 2 stays unbuilt and no fourth arm is planned.** Three rigs have been read as 5a, each correctly. A
fourth would most likely be a fourth scope defect, and building one to force a predetermined answer is not a
measurement.

**2026-08-20** — **A private RUN-LOGGING TIER for Wouter's own use, plus a monthly analysis of what it
records, is APPROVED and becomes STEP 5 — after publication, never part of it.** Wouter's words: *"make
sure that all logs of legal translation are logged for me and researched by an agent every month, and
tested against the then installed skill!! Analyse and present solutions, then verify."*

**It is NOT a third variant, and that is what keeps 2026-07-27 intact rather than overturning it.** That
entry rules out a third **client-internal** variant — a third *published English* tree. Checked in this
file before deciding, not reasoned from `CLAUDE.md` §2.5's summary of it, because §1.5 says a claim that
matters gets read at source. **This is the same tree with logging turned up: a CONFIG OVERLAY, decided
against a third tree.** The reason is measured — 176 of 198 files already diverge between two trees
*(2026-08-18)*, so a third triples the reconciliation and adds a tree that must never be published to a
repository whose whole discipline is *what you see is what ships*. **Same shape as §5.6's rule that the
scanner ships and the name list never does: the CAPABILITY ships, the VERBOSITY does not.**

**Sequencing, and Wouter was explicit: the overlay is built only after the UK and US skills are published
for external users.** But the **LOG FORMAT is designed before publication**, with D3's manifest work, and
that is not a hedge — §5.5 records that the forensic log and the shipped run report *"is the same
artefact, so designing the log format well gives the shipped report for free."* Design them apart and the
project owns two formats and a reconciliation. **So: one format, two verbosity tiers — the shipped
metadata-only report (§5.7, opt-in, already decided 2026-07-29) and Wouter's verbose local tier.**

**The monthly job tests against the then-installed skill, and that is the sharpest part of the idea rather
than a detail.** It is not log-reading: it replays the recorded failures against the skill **as it stands
that month** and reports which still reproduce. The machinery exists — §5.4's frozen-intermediate trick
makes the mechanical half a deterministic function, so a replay is seconds and needs no model. **That
turns production use into a regression suite that grows itself**, which is the never-regress rule (§5.3)
fed by real documents instead of by twelve July runs.

**PORTABLE, REPRODUCIBLE AND OBSERVABLE FROM THE START, because it moves to the cloud later.** Wouter:
*"local for now but I will eventually make all of my automations (including this check) portable,
reproducible and observable."* So it is **built for that from commit one rather than ported afterwards**:
no hard-coded local paths — every location by environment variable, the pattern `tools/gate_replay.py` and
`tools/stepb_audit.py` already use; the analysis reads its inputs by declared path and prints counts, never
names; and it exits non-zero on VOID rather than reporting a clean run over an empty set.

**AND THE CONSTRAINT THAT GOVERNS THE WHOLE DESIGN: A VERBOSE LOG OF A REAL TRANSLATION CONTAINS CLIENT
TEXT.** §6.4 already records that the A1 forensic logs quote real client text and are the most
content-rich artefacts this project has produced; a verbose production log is the same class. Four
consequences, decided now rather than discovered later: the logs live in a **sibling folder, never the
repo**; the **evidence guard must know that folder** or a monthly job running `ls` over it prints
counterparty names into a transcript, which is the one leak class no scanner here can reach (§5.6); only
**sanitised conclusions** enter the register, as with Wouter's review feedback; and the register needs a
**new origin class for production evidence** — the same gap the 5b probe hit when the validator rejected
`probe-5b` as unknown vocabulary, so it is one change serving both.

**What is NOT decided and is deliberately left open:** the log's field list, whether the monthly job is a
scheduled session or a cron-driven script, and what "presents changes to me" looks like as an artefact.
Those are Step B-style exploration, and §3.2's step-4 rule applies — *anything still short gets explored in the
Step B style, not patched straight to code.*

**2026-07-27** — The third, client-internal skill variant is **out of scope**; two variants only.
Pre-rev16 history **accepted as undocumented**; no reconstruction. Test corpus **outside the tree,
permanently**. Distribution **GitHub + lawve.ai, public**, which makes *Confidentiality* a design
constraint from the first commit. Reverse skill **out of scope**.

**2026-07-28** — Repo layout **Option C** (one private monorepo, both trees, parity check). The UK/US
reconciliation gets **its own branch**, after the measurement-only baseline. **No `CHANGELOG.md` going
forward.** Step A has **three strands** (A1 forensic runs, A2 grading, A3 desk analysis) plus Wouter's
review. Phase 3 opens with **Step B**. **Two autonomous blocks, two input points.** All test translations
are a deliberate **mix of US and UK output**. Phase 5 opens with **Step D**. The grader must be
**validated for both variants before any graded run**. **Chat mode is never used; Cowork only** — but the
skill's Chat-mode warning **stays in**, because it protects users. **Install truncation is a named goal.**

**2026-07-29** — Layout **Option 1**, repo name **`legal-translation-skill`**, **`.gitignore` by path**.
Branch protection on `main` from creation with **0 required approvals**. `README.md` from commit one.
**`git bisect` is the standard method for regressions**, run against the smoke suite or the fixture
byte-comparison — never against "translate and grade". **No credentials in the repo, ever**, and
**`.gitignore` is not a security control**. Smoke suite gets **its own branch (branch 2)**. The monorepo
**will be made public** after branches 1–3 and a history scan. **Git history is permanent**, so
`CLAUDE.md` was sanitised **before** `git init`. **All raw forensic logs live outside the repo.**
**Sentry / PostHog: NOT viable** for the published skill; build a **local, opt-in, metadata-only run
report** instead. A1 runs in **Cowork** under a harness. **`.doc → .docx` conversion loss (C3)** added as
a defect class and branch. **The ZWSP question SETTLED**: ZWSP in the deliverable is always a defect, and
the fix is a **pre-repack scrub**, not a prohibition on the device.

**2026-07-30** — **A1 scope raised to all 11 documents** (every document produced a new defect *class*,
not just new instances). **Grader fixed to v3 and FROZEN** until Step C. **A findings register is the
input to Step B.** Wouter's review is **BLIND** and triaged **three ways**. **The thinking level is a
measurement parameter**: hold `extra` across A1, test `max`/`low` additively at Step C. **The
multi-document batch session runs LAST**, D01 → D10 → D03B, with **D03 run singly as the control**.
**No comment filter** — the orphaned comments were a real defect, not a deliberate drop.

**2026-07-31 (later, during the review)** — **`CLAUDE.md` gets a canonical §2 *Plan of action***
holding every phase, step and sub-step with status; the old Roadmap section keeps **scope only**, and
the ownership rule is stated in both places (**§2 owns order and status; Roadmap owns scope**) because
undivided ownership is what let the plan drift. Charter renumbered **1–5 → 1–6**. **Wouter's review is
confirmed to run BEFORE A3, reversing the pre-rewrite plan** — his findings are an input to A3, so
running A3 first would mean redoing it; the stale Autonomy table said the opposite and he caught it.
**Review loop amended: the next document pair is opened IMMEDIATELY on receiving his feedback, before
any analysis**, so he reviews document *n+1* while Claude analyses document *n*. **D01's execution-line
rendering decided: `Signed at <place>, <date>`** (register E7).

**2026-07-31 (session close)** — **A4 IS THREE SESSIONS**: method + criteria, then the written
protocol, then the blind run. **Version control starts AFTER A4**, from the current sanitised state —
and the premise that there is a risky *history* is wrong, because nothing has ever been committed; the
risk is the content of commit one. **The 93-pattern control was run over both published trees for the
first time and found 15 files per tree**, mostly false positives from short patterns matching ordinary
foreign legal vocabulary, but including at least two genuine real-document artefacts already shipped
publicly. **Two consequences: branch 1 scans the trees before committing them, and the scan list is
tightened before it is trusted as a gate.**

**2026-07-31 (closing the A3 session)** — **A3 IS COMPLETE AND AUDITED but NOT signed off**: Wouter
reviews it and asks his critical questions first. **A NEW STRAND A4 IS ADDED — a BLIND desk review**, the
same skill judged from the outside by a notional competition judge who has seen no test result, scored
against **eleven** criteria **fixed and frozen before looking at the skill**, producing a second report that Step B reads
alongside A3. **Overlap between the two is expected and wanted.** **The blindness is an operational
constraint, not an aspiration: `CLAUDE.md` and `REGISTER-findings.md` now contain the answers, so A4 needs
a sealed brief that excludes both** — I-11's lesson, which cost four spoiled documents in the last review.
**A4 is PLANNED in one session and RUN in another.** Also decided at Wouter's prompting: **A3 owed answers
on RUNTIME and on REDUNDANCY** and had given neither — both are now measured sections rather than Step B
questions, because goal (i) asks for redundancy in terms and 25 minutes of fixed overhead is a structural
fact about the skill, not a fact about a fix.

**2026-07-31** — **A1 COMPLETE.** Batch session graded; register extended with cluster **T**; **A17's
mechanism corrected** (character style, not paragraph style) and **C19 reversed** (it recurs,
unrepaired). **A name-based leakage scan is not sufficient on its own** — two controls now required, and
three private tool files identified as never-committable. **`REGISTER-findings.md` gets a validator**,
run before and after every edit. **This file rewritten and restructured**; pre-rewrite copy archived
privately.

**2026-08-04 (A4's design, and it produced two findings about this project's own habits)** — **A4-i and
A4-ii are COMPLETE.** Eleven criteria, not ten: two independent selectors each cut the candidate pool to
ten by *different* merges, and the union is eleven genuinely distinct areas — dropping one to reach a round
number would delete a real area. **Wouter's five decisions: eleven criteria stand · C6 and C8 get
re-derived in a clean session before the freeze · use the HKCU managed policy, with removal in the same
script · NO second Windows account (so the subprocess hole is ACCEPTED, not solved, and refusing to
pre-allow shells becomes load-bearing rather than belt-and-braces) · A4-iii runs in Claude Code, which
means A4 says nothing about install-time behaviour in the host most users actually use — that belongs to
Step C.**

**A NEW GATE: the step-0 REHEARSAL.** The freeze used to wait only on the criteria re-derivation. It now
waits on a dress run of the judge's environment, because **every protective layer was an inference from
documentation and no path rule in the design had ever been observed to fire.** The rehearsal settles that
*and* hosts the re-derivation, so it costs one session rather than two.

**Two findings that generalise beyond A4, and both are about instruments rather than about the skill:**

- **The contamination channel is real, silent and defeats instruction — demonstrated by accident.** Every
  agent that helped design the rubric had this file auto-injected before its task text arrived, including
  the one whose only job was to be an uncontaminated control. It arrived with no tool call, before the
  first token, and invisibly to the agent itself. **So an attestation of good faith would have been
  sincere and wrong**, which is exactly why the blindness protocol opens with a launch flag rather than a
  rule. *(It also means the "cold control" is at best partially contaminated — hence the C6/C8
  re-derivation.)*
- **Every one of the four worst tooling defects was an INTERFACE MISMATCH**, and each failed as a cheerful
  pass rather than an error. The worst: a blindness auditor that read the wrong file for the seal, found
  nothing, and printed *"verified: 0 files unchanged"* — **a false CLEAN**. Two components each correct in
  isolation, disagreeing about a schema. **This is the same failure shape as the extraction/apply data
  contract Step B is already planning to fix, and a self-test that exercises one side of an interface will
  never find it.** Three of the nine defects were found by running components against each other; two more
  by probing outside the self-tests entirely.

**Also settled:** the containment guard must live **outside** the judge's room — a settings file inside it
hands over its own deny list, which names the withheld evidence. That is instrument defect **I-11** (the
helper that summarised the answers) rebuilt inside the fix for it, and it was caught by the red team rather
than by review.

**2026-08-04 (the step-0 rehearsal). CRITERIA FROZEN AT ELEVEN.** It paid three times over.

**(1) It found a contamination channel nobody had modelled, and it needs no tool call.** A session's
transcript carries an injected listing of every installed skill **and its description**, at session start,
with no tool call. On this machine that included a second copy of the published skill — i.e. its own
advertised feature summary — and the project's own grader. **This is the invocation-versus-listing
distinction, and it is the general lesson: a permission deny stops a tool being CALLED, not the tool being
DESCRIBED in the system prompt.** It would have voided criterion C1 outright, since C1 asks the judge to
extract the advertised capability list *from the artefact* and check each claim against a mechanism. Fixed
by hiding the two skills for the duration; the blindness audit now has a dedicated check for it.

**(2) The clean session reached two things all eleven criteria had missed** — both now in C6, and both
obvious in hindsight: **can a reader tell a check that PASSED from one that NEVER RAN?**, and **does
anything exist whose purpose is to make a check FAIL?** An explicit but uncalibrated instrument is weaker
than it looks. It also produced three conventions better than what was written, now applied to all eleven:
**search only for vocabulary harvested from the artefact's own entry document** (searching for terms *we*
supplied measures our expectations, not the artefact); **weakest-link scoring, never an average**, because
averaging rewards bulk and this artefact's features are largely counts; and **absence scores 1, never
"not applicable"**.

**(3) It caught contamination in our own instrument.** C6's sharpest framing — *is the comparison as strong
as the property the check announces* — was **not** independently reproduced: zero occurrences in the clean
session's 34,233 bytes. That is evidence, not proof, that it had been shaped by a known defect. **It is
DEMOTED, not deleted:** it is now an observation the judge may record, rather than what the criterion is
looking for. **A criterion that goes hunting a known bug is a bug-hunt wearing a rubric's clothes.** C8, by
contrast, was reproduced independently and better phrased, so its leakage question is closed.

**And one honest ceiling on the whole of A4, which its report must state:** every criterion measures
**written and coded disposition, not behaviour.** An artefact can score well by being written well, and a
rule that exists but never reaches the agent at the step that needs it scores as though it were in force.
Mitigation applied throughout: **prose-only assurance cannot score above 4.** This is precisely why the
11-document evidence base and the blind review are worth having *both*.

**A PROCESS LESSON THAT COST REAL TIME, recorded so it is not repeated.** The protocol accumulated a
lockdown — managed registry policy, permission allowlists, a containment hook — and it collapsed on contact:
the account has read-only rights on the policy registry key, a CLI-launched session would not authenticate,
one flag disabled the very commands used to verify the others, and the binary on PATH was an old version
running a different model. **Meanwhile the hazards it was defending against had already been closed by
WHERE THE ROOM IS** — no ancestor instruction file, hence nothing auto-loads, hence a fresh empty memory
key. The rehearsal then confirmed it: **two tool calls, zero reads outside the room, seal intact.**
**Absence by location beat policing by rule, and the post-hoc audit is what makes a breach recoverable
rather than fatal.** Wouter's question — *"why are we making this so difficult for ourselves?"* — was the
correct one and was asked several steps before it was heeded.

**2026-08-04 (A4-iii ran, then the comparison; STEP A IS COMPLETE).** The blind judge scored the vector
`4 9 4 4 4 4 7 4 4 4 4` and its report is 2,222 lines with 454 `file:line` citations. **Wouter's decision on
the one real contamination: C1 STANDS** — the injected skill listing named a second copy of the subject, the
pre-registered rule said void, but the harm it guards against did not operate; **recorded as a
pre-registered control relaxed after the result was seen, so C1 is usable but not independently certified.**

**Then the comparison, and five things came out of it that change how the project works.**

- **The predicted "blind-only" cell did not exist.** Register **C3** already held the quality-gate mechanism
  at CRITICAL on three documents. The prediction had been reasoned from **this file's summary of the
  register** rather than the register. **Rule, now explicit: a précis of the evidence is not the evidence,
  and that includes `CLAUDE.md`'s own précis.** What replaced it is the project's strongest convergence.
- **A NEW CLASS OF FINDING: the legibility gap, register cluster X.** Six places where a competent
  independent reader **praised** what the register shows is broken — the verification layer scoring highest
  of any structural area, the shared definitions detector praised as good de-duplication (it is L6), the
  anti-drift absolutism called *"mature"* (it is cluster K), the ZWSP device credited as coverage (it leaks,
  J1), the admission gate credited where F12 shows it cannot be operated, and `check_step_8` credited where
  C10 shows it over-fires. **Both readings are correct in every case, and the consequence for Step B is that
  six findings need the CLAIM fixed as well as the code.**
- **The blind review corrected A3.** W2's sentinel count was 177/198; it is **178** — A3 counted a *prose
  quotation* of the sentinel inside `08-aux-and-quality.md` as protection. **A3's own audit gate names the
  error class** (*"a grep over source counts a mechanism wherever a message merely describes it"*), and the
  tell was in W2's own words: *"for no reason anything in the tree explains."*
- **A CRITERIA LESSON THAT WILL RECUR AT STEP C.** C6's sharpest framing — *is the comparison as strong as
  the property the check announces* — was **demoted during the rehearsal** as a suspected bug-hunt. That was
  defensible on the information available **and it cost the blind review cluster C's master finding (C1, the
  token-set comparison), which it came within one sentence of.** The lesson is not "don't demote": **demote a
  suspect framing to a MANDATORY observation with its own enumeration, never to an optional one.**
- **A sampling rule that measures a pairwise property cannot sample linearly.** The blind review sampled 38
  of 128 mandatory statements across 3 of 9 instruction files — 30% of statements, therefore **~9% of
  pairs** — and missed 29 of the F-cluster's 31 rows, which is close to what that arithmetic predicts.

**Also decided: Wouter delegated the §9 adjudications** (*"fix everything, including 1, 2, 3 and 4"*), so
the partial agreements and the legibility rows were adjudicated by Claude and applied. **A second
pre-registered control set aside, recorded as such. And: Step B's exploration now runs BEFORE Phase 1
branches 1–2** — *"we need to explore first completely."*

**2026-08-04 (Step B's shape agreed IN ADVANCE, with a new top-level priority ordering).** Four decisions,
all in *Roadmap → Phase 3 → THE AGREED SHAPE OF THE STEP B ANALYSIS*, which the next session inherits as a
brief.

> **EDITORIAL NOTE, 2026-08-06.** That brief lived in `CLAUDE.md` and was removed when the charter was
> rewritten, **because the session it briefed has run and `PLAN-2-step-b.md` is what it produced.** The
> reference above is preserved as written; the four requirements it set are recorded here so nothing depends
> on a deleted section. **(1) Every option gets FOUR columns — pros · cons · what it would BREAK · what it
> does NOT fix** — the last two added because this project's documented failure mode is under-scoping, not
> over-scoping. **(2) Rank the options**, with the reasoning exposed, rather than presenting a neutral menu.
> **(3) Plain English grouped by CONSEQUENCE rather than by cause in the code**, with a one-page glossary and
> a traceability appendix, because the register's grouping is right for building and useless for reading.
> **(4) Three verification passes, each by a DIFFERENT method** — is it real (scripted, against the recorded
> failures) · would it work (adversarial: try to *refute* each proposal) · what does it break and what does
> it NOT fix (an omission hunt). **All four were delivered and are visible in the analysis's own structure.** **The one that reaches beyond Step B: QUALITY IS THE MAIN DRIVER, SPEED MATTERS LESS, AND SPEED MUST
NEVER COMPROMISE QUALITY.** That settles arguments A3 left level — the 25 minutes of fixed overhead is worth
attacking, but never by reading fewer lexicons, raising the 35-paragraph cap or thinning a gate. Also
decided: **a rebuild is presented as a genuine seventh option but the default is to keep the present
architecture** unless the cost-benefit shows a leap in quality, with the tension stated openly that a
rebuild is the one option that cannot be decomposed into merge-sized steps; **the options are RANKED**, not
listed neutrally; and **frozen translated intermediates from the real corpus documents are approved as
local-only test fixtures**, on Wouter's condition — *"as long as we keep being aware not committing sensitive
info"* — which makes them a **new artefact class for `.gitignore` by path**, being the most content-rich
files the project has ever produced. **Also agreed for after Step B: a serious overhaul of this file, then
publication — and the premise there needs correcting once, in writing: there is NO history to scan, because
nothing has ever been committed. The risk is the content of commit one.**

**2026-08-04 (the 20% spot-check RAN, and it changed the result — the best methodological outcome of the
day).** Two pairs were nominated before the answer was known. **#1 (J11↔C3) held on all four tests. #2
(J36↔C18) FAILED the mechanism test and was withdrawn.** Both sides had agreed that the run-written
baseline is the defect, but they drew **opposite consequences** from it — C18 cannot see what *apply and
`post_process`* did; the blind review cannot see what *extraction never captured* — **and C18's fix does not
close the second, because it diffs against declared translations that come from the JSON.** Two mechanical
checks then showed the apparent agreement had been manufactured by the amendment written that same day: the
only occurrences of *"at extraction"* in the register were inside it. **Three consequences, all applied:**
new register row **C28** (HIGH); the C18 amendment rewritten to state that its own fix leaves the extraction
half open; and **KS3 rescoped as the whole baseline problem — conversion (M1) + extraction (C28) +
post-apply (C18), three blind spots with one cause.** *The lesson is the protocol's own, now demonstrated
rather than asserted: **the matching rule is where a comparison quietly becomes whatever the analyst
wanted**, and the only defence is someone checking a pair they did not propose.*

---

## 2026-08-24 — the companion files keep their legacy names until after phase 3d

**The names hide what the documents ARE.** `PLAN-2-step-b.md` is a **PLAN** — formally step 2's plan file
— and reads as an analysis. `EVIDENCE-a3-structure.md` is **EVIDENCE**. `PLAN-3-opus5-migration.md` is a
**PLAN**. The house naming convention would call them `PLAN-`, `EVIDENCE-` and `REGISTER-`, and a reader
who does not already know cannot tell which is which. *(Wouter raised it in exactly those terms.)*

**DECIDED: rename at the very end, after phase 3d, as ONE scripted commit** — the names, the kind labels,
and the six `tools/stepb_*.py` scripts whose own filenames carry one of them.

**The cost was measured by listing rather than estimated: ~178 references across ~30 files.**

| document | references | in files |
|---|---:|---:|
| `PLAN-2-step-b.md` | 68 | 24 |
| `REGISTER-findings.md` | 40 | 17 |
| `EVIDENCE-a3-structure.md` | 31 | 14 |
| `DECISIONS-LOG.md` | 22 | 11 |
| `PLAN-3-opus5-migration.md` | 17 | 11 |

**Why not now, and it is the same reasoning `PLAN-3d-lt-route0.md` already uses against renumbering:**
phase 3d is still **moving content between these files**, so a cross-reference audit run today is an audit
against a moving target — it would pass and prove nothing. **Why not never:** every session that passes
adds references, so the migration only gets more expensive, and the confusion is real rather than cosmetic.

**What this decision does NOT include.** It was offered as an option to label each document's KIND in §1.3
immediately — a column, breaking zero references — and **that was not taken**: the whole migration happens
once, at the end, rather than in two disturbances. **So until then the names stay misleading, and §1.3's
prose is the only thing telling a reader what each document is.** Recorded plainly because a reader
arriving mid-project will hit this, and the answer must not be *"nobody noticed"*.

## 2026-09-02 — C16's fix keeps both halves, and C16 stays PARTIAL rather than buying its closure

**Two decisions at branch 6 slice 4's closing exchange, both taken after the measurement rather than
before it, which is why they are here and not in the plan.**

**FIRST: THE C16 FIX SHIPS WIDER THAN THE ONE APPROVED AT THE INPUT POINT, AND THAT WAS PUT TO WOUTER AS AN
OVERRUN RATHER THAN PRESENTED AS COMPLIANCE.** At the input point he chose *restore at most ONE whitespace
character* over three alternatives. Building it found a second, unpredicted mechanism: the restoration guard
tested a segment's **own** slice edge and was blind to its neighbour, so **one** source space restored beside
an authored one still makes two — `"Clause "` + a cleared `ins` + `" applies."` delivered
`"Clause 12  applies."`. It needs only one source space, so it is the **commoner** shape, and *at most one*
does not touch it: it was already restoring one.

**DECIDED: keep both halves** — *at most one character, and only where the boundary has no whitespace from
either side.* **The reasoning, which generalises past this row:** the two halves are one rule rather than a
rule plus an extension — make the operator's input authoritative at a boundary — and the narrower version
would have left a defect that is **visible on the rendered page in the very pull request claiming to fix
it**. The rev42 repair the wider rule had to preserve is asserted as the fixture's own negative, so the
widening cannot quietly become a deletion.

**AND THE PROCEDURAL POINT MATTERS MORE THAN THE RULE.** The decision was implemented *before* it was
confirmed, with the overrun flagged in the pull request, the commit message and the closing exchange, on the
reasoning that stalling a verified branch to re-ask a question whose answer the measurement had already
constrained costs a session and buys nothing. **That is only defensible because the flag was unmissable and
the alternative was reversible.** It would not be defensible for anything irreversible.

**SECOND: C16 STAYS PARTIAL. Its residue does NOT get a branch, and the queue is NOT reordered.** The slice
built the delivered-versus-declared arm the row had always needed, and the arm **attributes rather than
totals** — the source's own interior doubles and the operator's declared ones are subtracted, because
*"apply CREATES it"* is a claim about the excess alone. Measured: **D04 delivers ONE interior double against
12 in its own SOURCE and 0 declared**, so nothing on the row's own document is attributable to apply at all;
**D07 keeps 3**, which the fix did not remove.

**DECIDED: leave the row PARTIAL with the measurement written into it, and take branch 7 next.** Three
reasons, in order of weight. **(1)** the auto-loading house file's rule that the queue is worked in order and a reordering is
Wouter's decision, never a side effect — and wanting to finish a row one is already holding is exactly how
that rule gets broken. **(2)** Paragraph-level attribution is **unbounded until the first measurement comes
back**, so it cannot be scoped into a branch that is otherwise finished and verified. **(3)** The instrument
now exists, so whoever picks the residue up starts from evidence rather than from this row's prose — which
is the difference between the row as it stood this morning *("the un-catchability is the finding")* and as it
stands tonight.

**What was explicitly NOT decided: whether the residue is a defect in apply at all.** D04's delivered double
space may be inherited from a source that carries twelve of them, in which case C16's own document never
demonstrated the row. **That question is open and is recorded as open**, rather than being settled by the
convenient reading.

---

## The closed decisions that had their own sections

# Observability — decided 2026-07-29, and closed

**The goal is right and the SaaS route is not viable for a published skill.** Sentry and PostHog were
explored and rejected on four grounds, the decisive one being **confidentiality**: this skill processes
confidential legal documents, Sentry captures stack traces and local variables, and in this pipeline those
contain **paragraph text**. Even a filename is unsafe. Sending it to a third-party US platform, for EU law
firms' documents, is a GDPR and privilege problem before it is a technical one. The other three: there is
no application you control, no reliable outbound network, and any API key inside a public skill is public.
**Do not revisit this for the skill.**

**Build instead: a local, opt-in, metadata-only run report.** The skill already produces the raw material
— gate banners, `verify_diligence.py`'s report, the `.validate-state.json` batch record, integrity checks
— but it is neither collected in one place nor aggregated. Have the pipeline write **one structured run
report** into the workdir: steps run, per-step duration, gates fired and what satisfied them, validator
warnings, iteration loops, integrity results, file manifest. **Metadata and counts only — never document
text, never filenames.** **This is the same artefact as the A1 forensic log**, so designing the log format
well gives the shipped report for free.

**Where Sentry and PostHog genuinely do fit: the Word add-in, not this skill.** That is a
`comment-qualifier` decision.


---

**2026-08-05 (Step B ran, and every option was decided).** `PLAN-2-step-b.md` was written, reviewed option
by option, and then **reorganised into build order** on Wouter's instruction at the close of the second
session. **Eleven options explored; ten approved and the rebuild declined on measured arithmetic** — it
addresses at most 94 of the recorded findings, cannot be decomposed into merge-sized steps, and risks the
half that measurably works. **The leap is delivered instead by the formatting option, in three slices.**

**The six numbered decisions, all answered.** Decision 1 = **1c restated** (generate the compliance rules
*from* the Avoid rows, seed from evidence already held, top up at each graded run). Decision 2 = **2c
revised** (every tidy-up pass tests the condition it currently assumes; where the condition cannot be
determined it reports and changes nothing; **no flag, no user question, no operator switch**). Decision 3 =
**3b**, the sanctioned way out, available only where all four conditions hold — **and Wouter reviews the
specification before it lands.** Decision 4 = **build 11a now, defer 11b**, with 11a required to
*classify* every instance so the deferred decision becomes arithmetic. Decision 5 = **no cross-language
parity check** — none could be honestly written — **but one sentence in the claims pass.** Decision 6 =
**no shared library**; the approved options dissolve every duplication that has caused a logged defect, and
the standing rule *a shared capability lives in one place* goes in **our** coding standards, never in the
shipped skill.

**Option 7's five questions.** *(a)* One tree literally — a shared source with generated variants — is
**DEFERRED with a trigger**, revisited when the reconciliation's row-by-row adjudication is done and the
618-pair residue is classified, because that classification is the deciding number. *(b)* The three drifted
scripts are **parameterised**, which is the part of "one tree" available now with no generator. *(c)* The
**adjudication principle is two arms** — variant questions restored mechanically as dual-variant rows,
substance questions decided by Wouter, and **anything the mechanical arm cannot classify is escalated,
never guessed.** *(d)* The reconciliation keeps its deferred position and its re-grade folds into the
verification run; the drift cannot grow meanwhile because the parity check lands early. *(e)* Cross-language
parity: out of scope as a check, in scope as one sentence.

**Also settled in the same sessions.** **Frozen translated intermediates from the real corpus documents are
approved as local-only test fixtures**, on Wouter's condition — *"as long as we keep being aware not
committing sensitive info"* — which makes them **a new artefact class that must be excluded by path before
`git init`**, being the most content-rich files the project has ever produced. **Negative test inputs are
mandatory, not optional.** **Publication means the SKILL's publication**, always — the bare word had been
doing two jobs and Wouter caught it. And **no separate `furniture.md`**: the section that already claims the
subject is where the conventions go.

**Three process findings, and they generalise past Step B.**

- **NEVER WORK FROM A PRÉCIS — and this time the rule was broken by the document that states it.** Step B
  worked from the comparison rather than from the blind review's own 2,222-line report. Reading the report
  later produced **six items nothing else carried**, including independent build-cost estimates the analysis
  had asserted did not exist. *(The comparison's ledger disposes every CLAIM to a cell, so no finding was
  lost — but recommendations, costs and reasoning are not claims.)*
- **A check that passes on a coincidence is worse than no check.** Eleven logged instances now, several
  inside Step B's own verification scripts — including a probe passing on the two-word needle *"both
  variants"* against a sentence about re-grading both variants, and another passing on a sentence saying a
  check **cannot** do the thing being probed for. **Normalise by default, and make every needle a phrase
  that could only appear if the thing is carried.**
- **A twenty-line script beats three careful readings.** Prose review passed five defects that a short
  script then killed; `a3_md_tables.py` caught a four-column row inserted into a two-column table and an
  appendix that had silently stopped being a table, **both of which the register's own validator passed.**

---

**2026-08-06 (`CLAUDE.md` rewritten to the seven-section structure).** Wouter's instruction: rebuild the
file around **1 how to read · 2 project overview · 3 plan of action · 4 tech stack · 5 working method and
rules · 6 file, folder & repo structure · 7 current status**, with **§3 carrying only what is still to be
done** and **§7 carrying only the handoff.** Three consequences recorded because they are decisions rather
than edits:

1. **`PLAN-3-opus5-migration.md` and this file were split out**, on the same principle Wouter set for the Opus 5
   work: a self-contained workstream, and a dated historical record, are both easier to keep true outside a
   charter than inside one. **A new standing rule follows** and is in `CLAUDE.md` §5.4: anything
   substantial being added to the charter is placed in §2–§6 by subject, and if it is extensive, **ask
   whether it belongs in its own document before writing it in.**
2. **The build plan is no longer restated in the charter.** `PLAN-2-step-b.md` §2 owns the order, §3 the
   brief and §4 the test method. The charter's old indicative branch list, its six-keystone framing and its
   fourteen-item scoping-caution list are **superseded**, and the standing prescription check
   (`temp/stepb_harvest.py`) proves every one of the cautions was carried into the analysis — **63 carried,
   0 missing** — which is what makes removing them from the charter safe rather than lossy.
3. **A claims check was run over `CLAUDE.md` before it was restructured, not after** (`temp/claudemd_claims.py`,
   35 failures on the old text). Its most useful result was not a stale count: **one of the two failures this
   session was handed as already-confirmed did not reproduce.** The charter had been said to still claim the
   dual-variant design *"holds in `references/`"*; it does not, and has not since the 2026-07-31 rewrite —
   the analysis that reported it was quoting the pre-rewrite file. **Second time in this project that a claim
   about the evidence, made from a précis, failed on measurement.**

---

**2026-08-06 (a new confidentiality rule: how a test document may be named).** Wouter, reading the rewritten
charter: *"Would like you to mention only: Agreement (Norwegian), Power of Attorney (Hungarian) etc — not the
names/types of the agreements themselves. This should also be in other documents and be a rule in terms of
confidentiality."*

**THE RULE, now `CLAUDE.md` §5.6: instrument class plus language, and nothing else.** Never what the
instrument is *about*. The reasoning is the same one that produced the two-control requirement in July:
**subject matter plus a language plus a date range identifies a real instrument more sharply than a name
does**, to anyone who knows the market — **and the 93-pattern scan is structurally blind to it**, reporting
0 hits on every qualifier the project had been using, correctly, because none of it is a name. **The same
rule reaches clause content:** say what a lost span *did*, never what it said.

**What is NOT covered by it, deliberately: the technical character of the file.** No sub-lexicon · legacy
binary `.doc` · only non-Latin script · most tables · bold-run counts · paragraph counts · batch position.
Those are the evidence base and they describe the file rather than the deal.

**Four things came out of applying it, and three are worth more than the edit.**

1. **39 descriptors were replaced across four documents**, by two scripts that refuse to write unless every
   pattern matches its expected count. Both descriptor scans then report zero.
2. **The list-free sweep found four the term list had missed** — including a subject-matter qualifier sitting
   in the *charter's own runtime argument* and one in A3. **That is the July lesson reproduced exactly: a
   list-based control cannot see the class of leak it was not written for**, which is why both controls run.
3. **The new blocking probe fired on the rule that created it.** The first version listed the forbidden
   qualifiers inline, and the charter's rule text listed them as examples — so the probe caught the rule.
   It was right to. **The qualifier list now lives in the private folder beside `leakage-names.txt`**, read
   by path or environment variable, and the probe announces **DISABLED** rather than CLEAN if it is missing.
   **The rule that decides committability is not "is this a script?" but "does this file hold one real string
   per pattern?"**
4. **The judgement pass over every committable document found two real dates quoted from client clauses** —
   the last of the operative-commercial-terms class the July audit named. Genericised to placeholders; the
   bracket positions that were the actual evidence are untouched. `temp/confidentiality_review.py` is the
   record of what was judged and on what basis, so "we reviewed it" is a document rather than a memory.

**Declared judgements, recorded so they are not re-decided:** *notarial deed* (an instrument class in
civil-law systems, no language, no subject) · *real-property instrument* (a legal DOMAIN, and the finding it
appears in is precisely that no domain reference covers that domain) · *civil-law instrument* and
*choice-of-forum agreement* (categories and a lexicon term) — **all four stay.**

---

**2026-08-06 (the confidentiality review is not committed, and the committability list was re-measured
because of it).** Wouter, on being offered the review script for promotion into `tools/`: *"I don't want
confidentiality review to be committed btw."*

**Accepted, and the reason generalises.** `temp/confidentiality_review.py` is clean on every probe. What
makes it unpublishable is not a string it holds but **what it reveals about the control**: it sets out which
shapes are scanned for *and which candidates are accepted*, which is a map of what gets waved through. **No
probe can see that class of exposure**, so the measured list is a floor, not a ceiling.

**Taking the instruction seriously meant re-measuring the whole set**, because the repository step's first
act is `git add` and the charter's committability list named only the scripts that existed in July.
`temp/script_committability.py` runs the publication check's probes over the *code*: **69 of 90 scripts are
clean; 21 hold a real string.** Four kinds, and only the first was on the old list — the lists and their test
vectors · the two workspace-building scripts · **the replacement scripts, because a counted replacement must
carry the *before* text, so a script that removes a real string necessarily contains every one it removed**
· and one-off measurement scripts with a hard-coded local path.

**Three of the scripts intended for `tools/` were caught and fixed the same day, and how they failed matters
more than the fix: each had quoted a real string inside an explanatory COMMENT.** The publication check's own
comment quoted the home-relative path it exists to block; the list-free descriptor sweep illustrated itself
with two real qualifiers. **A comment ships. A docstring example is published prose. Invent the examples.**

---

**2026-08-06 (the changelog is not committed, and `docs/history/` does not exist).** Extending the check to
the whole commit list found the one artefact nobody had scanned: **the recovered rev16→rev44 changelog,
scheduled for `docs/history/` at branch 0.** It had never been checked **because it is not a file yet** — it
is recovered at branch 0 from the `CHANGELOG.md` inside the archived `.skill` revisions, and an artefact that
does not exist cannot be scanned. Measured: **four name-shaped patterns matching 69 times, one a multi-word
proper name**, three corpus descriptors, a company-form suffix, two capacity figures, three document
filenames — **rising monotonically by revision**, 10 in the earliest to 32 by rev20, which is what a working
log kept while translating real documents looks like.

**Wouter's decision, and it closed the question rather than deferring it:** *"Changelog should NOT be on
commit list. It was part of the A3 and B analyses but there is no sense in committing it. Docs/history should
never be committed."*

**Why that is the better answer than sanitising it.** The changelog earned its place as an *input* — it is
where the rev16→rev44 discipline was recovered from, and both the structural analysis and the build plan used
it. **It is not a deliverable.** Sanitising 100 KB of working log to publish history that nothing downstream
needs would have spent real effort on a new risk surface, and every lesson it carried is already in the
charter's §5, sourced and dated. **The archive keeps it, outside the repository, where it already was.**

**Applied to the plan the same day:** branch 0 no longer archives it, `docs/history/` is gone from the
layout, the skill-authoring convention no longer points at it, and the archived revisions are named in §6.4
as a never-committable location in their own right. **A decision that changes the plan and not only a file
has to change every place the plan is written down** — which is the failure mode the charter overhaul existed
to fix, applied to itself within the hour.

**2026-08-07 (the repository went PUBLIC, and the flip was MEASURED rather than assumed).** *(Recorded here
on 2026-08-24, moved out of `CLAUDE.md` §6.4 by phase 3a step 4 — the charter keeps the standing facts and
this log keeps the measurement. It had no entry here before, so this is a relocation, not a duplicate.)*

**The moment was chosen, not stumbled into.** The repository was created private on 2026-08-06 and flipped
once branches 0, 1 and 2 had merged — **the cheapest possible moment**, because the history was then **eight
commits long** and held only the two unmodified trees plus the instruments. Every later commit is a commit
that would have had to be scanned.

**MAKING A REPOSITORY PUBLIC EXPOSES THE WHOLE HISTORY, NOT THE CURRENT STATE**, which is why the
measurement was taken over the history and not over the checkout. **Every blob in every commit was scanned:**

- **security: 0.**
- **Nothing outside `uk/` and `us/` matched any probe.**
- **No file had ever been deleted**, so nothing was hiding in history behind a removal.
- **The four superseded skill files are byte-identical to the published rev44 archives**, which had been
  downloadable for months — so the only pre-existing content the flip exposed was already public.

**Branch protection was live at the moment of the flip, with `enforce_admins` TRUE**, and was tested both
ways on the day: a direct push to `main` is rejected with `GH006` even for an admin with the local override
set, and a pull request stays `MERGEABLE` with no review required, so nothing about Wouter's own merging was
made harder. **Required approvals stay 0 deliberately** — on a solo repository GitHub would otherwise refuse
to let him merge his own pull request, which breaks the agreed workflow rather than protecting it.

**AND THE LIMIT MATTERS MORE THAN THE SETTING, stated here because it is easy to read the protection as more
than it is.** No GitHub configuration can make Claude ask Wouter's permission, because Claude operates under
his own account — to GitHub they are one identity. **The setting stops the accident; it cannot stop the
decision.** What actually requires his approval is the charter rule, the local hooks, and compliance.

---

**2026-08-07 (how an instruction branch is tested — the graded run is replaced, not skipped).** Branch 3 was
presented with `PLAN-2-step-b.md` §4's method for instruction branches — *"a graded run plus your review"* —
and with the honest caveat that folding it into Step C would be a **new** decision, since §4 records that
answer only for option 4. Wouter's response was neither: **"Can you not test this in any other way? Please
let's explore this first."**

**Exploring it changed the reasoning, and the measurement is the reason.** A branch of this kind only bites
when a check fires **with the wrong scope**. That situation — register cluster G — is attested on **5 of the
11 corpus documents**, so a single graded run reaches it slightly under half the time; and where it does, the
grader scores the *output* while what changed is the *operator's reasoning at a gate*. **So the graded run
was not merely the expensive instrument here, it was the wrong one.** That is a stronger ground for moving it
than cost, and it is the ground on which it moved.

**Decided: four instruments replace it — static reachability, the static decision on the rule collision,
execution against the real gate, and a retrospective replay over the A1 logs — each with a negative input
proving it can fail.** The behavioural residue (*does an operator meeting a wrongly-scoped gate now do the
right thing?*) is **not** absorbed: it stays at Step C, where §4.1 had already put it as the third arm.
**§4's method table was amended in the same branch**, because a plan that keeps prescribing an instrument the
build does not use is a plan the next session will follow wrongly — the same rule the 2026-08-06 entry above
states, applied again.

**One thing the exploration found that no graded run would have.** §4.1 assigns *static reachability* to
branch 3 in terms, and neither §2's branch row nor §3.4 mentions it — so the branch was planned without it
until §4.1 was read. **That is the second time a section pointing at another section has been the difference
between a right and a wrong plan** *(the first was branch 2, planned from §3.3 without §6)*.

---

**2026-08-11 (branch 4 landed, and its one unanswerable question got a gate).** Rule 5b — the sanctioned
way out when a check is right and no compliant repair exists — was built, verified and presented for
Wouter's review. He approved the text with one condition, and the condition is the interesting part:
*"as long as you are sure this will really work in cowork — that the model will really not deviate."*

**The honest answer was no, and saying so is what produced the decision.** Branch 4 proves 5b is present,
readable at every step a check can block, identical in both trees, softened nothing, and is aimed at
situations the logs record — 147 instances across the twelve runs, 7 of them *no compliant repair*, and
**four repair loops that never went green, the deepest running to eighteen attempts.** None of that shows a
model will *apply* the rule. That is behavioural, and no script can settle it.

**Decided: a behavioural probe gates branch 5, rather than waiting for Step C.** One document, one
deliberately rigged deadlock. **The reasoning is sequencing, not thoroughness:** branch 5 is what turns
eighteen silent defects into blocked runs, and 5b is then the only legitimate way such a run can end — so if
5b fails, branch 5 makes the pipeline unusable on real documents, and Step C comes *after* branch 5 has
shipped. Recorded as a fourth sequencing fact in `PLAN-2-step-b.md` §2, with its design and the direction
to read it in.

**Also decided the same day, both cheap and both converting an unverifiable claim into a checkable one.**
*(i)* The confidentiality gate now scans the **published trees**, which it never did — by diffing to added
lines only, because scanning whole trees returns 46 known-benign hits per tree and a reviewer facing those
starts skimming. Measured: branch 4's eight files give 6 hits, its 102 added lines give 0. *(ii)* An
**evidence-folder guard** runs before a shell command executes, because the one leak class this project
cannot scan for is the transcript — §6.4 says session metadata is reachable by neither the scanners nor the
location rule, and a session proved it by globbing a log folder and printing real corpus filenames into the
conversation.

**Left open, and put to Wouter rather than decided:** whether a 5b invocation should be required in a
**fixed, machine-recognisable shape** in the delivery notes. It cannot prove the five attempts happened —
but it makes a *silent* 5b impossible, which turns an undisclosed exception from invisible into a detectable
defect. Independent of the probe; ordering it first would make the probe's result mechanical rather than a
judgement about the operator's prose.

## 2026-09-08 — branch 7's seven scope decisions, and the two taken at the close

**All seven were put before any code was written**, which is the point worth recording: the container
inventory's *width* is not a coding detail, and a plan that named only the register rows would have
produced an inventory of the register rows.

**THE SIX TAKEN AT THE OPENING INPUT POINT.**

1. **All five containers of the schema group** — `sdt`, `smartTag`, `customXml`, `dir`, `bdo` — **rather
   than the two with register rows.** The measurement is the argument: a 20-shape sweep through the real
   apply found all five stranding text identically, and it is one code change rather than five. *Fix the
   class, not the caller.* `w:ruby` and `w:fldSimple` are different mechanisms and got rows instead.
2. **"Fail loudly" means BLOCK, but only where an unlisted container CARRIES TEXT.** §5.7's test is
   whether a compliant way out exists, and the source is the client's own document, so the operator
   cannot delete an element to satisfy a checker. An unlisted element carrying no text is left alone —
   `w:subDoc` measured CLEAN, and a gate firing there would fire on correct input, which is what branch
   6's first offset guard did. **The measured population makes this safe:** across all 52 WML parts of 10
   of the 11 documents, the complete set of non-run children of `w:p` is ten elements and exactly three
   carry text. There is no math anywhere — the one shape that would otherwise refuse input nobody can
   change — and it is listed as inert so a document carrying one gets a named decline.
3. **KEEP an emptied content control; DROP an emptied annotation wrapper.** A `w:sdt` renders, and may be
   locked, data-bound, a date picker or a checkbox — so removing it is a structural edit to the client's
   document, which A16's own row records as unsanctioned. A smart tag, a `w:customXml`, a `w:dir` or a
   `w:bdo` is a pure annotation over text that no longer exists, so once empty it is *provably redundant*,
   which is clause 3's own test and the only warrant this branch has to delete anything.
4. **A19: report every graphic surface AND TRANSLATE THE ALT TEXT.** Wider than the recommendation, which
   was report-only, and the reason is the one the recommendation missed: **a `@descr` is what a screen
   reader speaks**, so leaving it in the source language is an accessibility defect as well as a
   translation gap. Chart and diagram text stay detected-only, having no corpus instance to verify a
   translation against — and neither has the alt text, so that must be said rather than implied.
5. **C19: the `--glossary` flag PLUS repack's own refusal pattern**, which it already applies to
   numbering, comments, footnotes and endnotes. This is the script's existing convention rather than a new
   mechanism. *(Note the trigger differs from those five: theirs fire on a workdir file looking translated;
   this must fire on the ORIGINAL carrying the part.)*
6. **Three slices**, one per script and one per acceptance condition.

**AND THE TWO TAKEN AT THE CLOSE, after the measurement rather than before it.**

7. **A22 GETS A ROW NOW AND NO BRANCH YET, and the queue is not reordered.** Measured on this branch, A22
   is not a cosmetic duplication but a **DEADLOCK**: the field's cached result glues to the English,
   gluing merges token types, and `validate_apply --strict` refuses the repack with no compliant repair —
   F41's family, exactly as C17 turned out to be. **It is nonetheless not scheduled**, and the reason is
   that fixing it means reopening clause 3's keyword narrowing, which was itself set on a corpus
   measurement: *"drop the skeleton when its cached result is consumed"* applied to every field type would
   freeze a `PAGE` field at whatever number happened to be cached. **Zero corpus instances**, so nothing
   ships wrong today. That reopening deserves its own exploration rather than a decision taken in passing.
8. **BOTH READ-BUT-NOT-RUN MEASUREMENTS ARE SCHEDULED.** *(a)* The **header/footer `sdt` surface** — 5
   across 4 corpus documents, where `translate_headers_footers.py` appears to strand nothing because it
   writes into the first `w:t` and clears the rest. **That is a reading, and this project's record on
   readings is poor** — the same session refuted A16's row from structure and was wrong. *(b)* The
   **`w:dataBinding` question** — 2 corpus documents carry a bound control, and Word can repopulate its
   text from `customXml` on open, so a correct `document.xml` edit may be undone on the page. It needs
   Word in the loop, which no current instrument has. **Neither blocks a branch; both are now owed a
   measurement rather than left as prose.**

## 2026-09-09 — branch 7's close: four scope decisions at the open, four at the close

**All four opening decisions came before any code**, which is the point worth recording: three of
them would have changed what slice 3 built, and one of them decided whether it could be believed.

**THE FOUR AT THE OPENING INPUT POINT.**

1. **A19's alt-text route goes in HEADER AND FOOTER PARTS ONLY, and every other surface is
   REPORTED.** The measurement is the argument: all 14 of the corpus's graphics are in headers and
   footers and **none is in the body**, `translate_headers_footers.py` already has the extract-apply
   round trip, and `repack --headers-footers-dir` already bundles what it writes. A body route would
   need a new script in both trees, a new repack flag, and would collide with apply's own
   `document.xml` output — for a surface no corpus document carries. **The residue is not hidden:**
   §5.7's compliant-exit test says a body drawing, a chart title and SmartArt text cannot be
   refused, because the source is the client's own document and the operator may not edit it to
   satisfy a checker. So they are reported, loudly, which is the honest form of *fail loudly rather
   than ship silently* where a gate would fire on input nobody can change.
2. **The header/footer CORPUS ARM is in scope, and it is not about A19.** `apply_corpus_diff` drives
   apply and cannot see this slice at all, so before `tools/hf_corpus_diff.py` existed **nothing in
   this repository measured the header/footer translator against a real document.** What it actually
   guards is the **scaffold SHAPE**: slice 3 adds a `kind` key, all 10 frozen scaffolds predate it,
   and if a `kind`-less entry ever stopped being treated as a paragraph entry then every real
   document would silently stop having its headers and footers translated **while the fixture suite
   went on passing**, because a freshly extracted fixture scaffold has the key.
3. **The corpus's inability to reach measurement (a) is §5.5's THIRD reason, NOT a fifth.** The
   corpus does hold the shape — one inline `sdt` in a footer — and nothing removed it; the paragraph
   is simply never rebuilt, because the operator left that scaffold entry's `en` null. So the
   mechanism is the **artefact's** rather than the shape's, and it is *holds the mechanism but not
   the damage*. **Naming the mechanism in the row buys the same understanding without adding a
   fifth category to a charter already over its cap** — and slice 2 nearly added a fifth for a
   similar case and did not. *A category that merely happens to fit is a claim waiting to go stale.*
4. **PR #68 merges first, so slice 3 branches off a main that already carries the pin moves.**
   Stacking it would have put slice 3 on `close/branch7-slice2`, and §5.2's stacked-branch rule has
   already cost this project a pull request.

**AND THE FOUR AT THE CLOSE, after the measurement rather than before it.**

5. **`hf_corpus_diff.py`'s PIN IS FIXED, NOT MOVING — the opposite of `apply_corpus_diff`'s rule,
   and decided on a measurement.** With its pin moved to slice 3's merge in the ordinary way, both
   arms carry the new code, its VOID guard fires correctly, and it reports **VOID on every run for
   ever** until the translator next changes. The question it asks only exists against a tree that
   predates the `kind` key. **A check that can only report VOID is not a check**, and a
   permanently-red row is one people learn to scroll past. It follows
   `test_no_delivered_byte_moves.py`'s precedent instead — that suite and two others already pin to
   a fixed pre-change revision. **When to move it is written into the file, and it is not at a
   close.**
6. **THE `.pyc` CLASS GETS ITS OWN SLICE, BEFORE BRANCH 8, IN THE SAME SESSION** *(Wouter)*. Slice
   3's new import can leave a `.pyc` inside a **shipped** tree, and `precommit_gate` check 6 caught
   one on the very commit that added it. Four other tree scripts import a sibling the same way and
   none guarded. **It was deliberately not fixed inside slice 3:** a line added to
   `apply_translations_textmatch.py` would have changed what `apply_corpus_diff` was comparing,
   mid-slice, in a slice about graphic metadata. Done alone, the same change becomes a **proof**
   instead of a confound — apply genuinely differs from the pin, the self-comparison notice is
   absent, and 13 of 13 frozen intermediates come back byte-identical, which is §5.4 rule 3's
   *proved byte-for-byte, or not claimed*. **And the fix is a check that DISCOVERS the importers by
   reading the tree rather than a patch on the four that exist**, so caller N+1 is covered without
   anybody adding a row.
7. **REGISTER F43 IS FILED AT CANDIDATE STRENGTH AND INVESTIGATED WITH BRANCH 8** *(Wouter)*. The
   frozen header/footer scaffolds went partly or wholly unfilled on the three workdirs that match a
   corpus document, and an unfilled entry means apply left that paragraph alone — so if those are
   delivered runs, header and footer text shipped in the source language. **It is not established,
   and the reason is the denominator:** the other 7 of 10 match no document and hold 0–1 entries,
   so some of the thirteen are stubs or arms, and *a fill rate over a population of unknown
   provenance is not a fill rate.* Filing it now and investigating later keeps it from dying with
   the session without spending a session on it; it rides in branch 8's prompt.
8. **THE SESSION COST IS 44%, READ BY WOUTER.** Claude cannot see the figure and may never estimate
   it. Recorded, never obeyed: the session ended because its planned work ran out.

## 2026-09-09 — the commit MESSAGES carrying a forbidden phrase: DEFERRED, and DECIDED

**§3 carries the decision and its trigger in two lines. This is the reasoning behind it, and the
population, which §3 must never restate.** *(Owed since the decision was taken and written here on
2026-09-09, because a pointer to a dated entry that does not exist is worse than no pointer.)*

**THE POPULATION, MEASURED WITHOUT PRINTING ANY PHRASE OR ANY MESSAGE TEXT.** `verify_confidential.py`
v4 was run over five populations with `VERIFY_FORBIDDEN_LIST` set and its selftest passed first, so the
instrument was proved before its verdict was read. **List fingerprint `e76c67eb55c1`, 8 phrases checked,
the positive control FIRED** — so the run is a verdict and not a VOID.

- **THE TREE IS CLEAN AND THE MESSAGES ARE NOT.** 517 of 517 tracked files PASS; **802 history blobs from
  every ref PASS**; **22 of 117 commit messages FAIL.**
- **132 (commit, phrase) findings across those 22, with 6 of the 8 needles in every one of them** — because
  **every hit sits on exactly ONE trailer-shaped line per commit** (`Key: value`, the shape git itself
  recognises). One occurrence trips six needles at once.
- **ALL 22 ARE REACHABLE FROM `main` AND ALL 22 ARE ON A REMOTE**, so they are **already served by a public
  repository**. That is the half a clean tree cannot answer, and it is what decides this.
- **CONTENT IS CLEAN ACROSS ALL HISTORY**, so the defect is confined to message metadata — **the one
  population no content scan reaches**, which is why no record in this project had ever mentioned it.

**THE DECISION: IT STAYS DEFERRED — *decided*, not merely un-acted-on.** *(Wouter, with the full scope in
front of him.)* **The distinction is the point:** an undecided finding invites re-litigation every time a
session rediscovers it, and a decided one does not.

**HIS REASONING, AND THE STRONGER HALF IS THE GATE RATHER THAN THE COST.** Removing them is a **history
rewrite** — irreversible, one message-callback pass, but re-SHAing every commit across every ref, breaking
branch 7's comparison **pins** *(which are commit SHAs)* and the commit references inside `tests/baselines/`.
**And the house gate — *rewrite BEFORE a repository goes public, never after* — CANNOT BE MET HERE AT ALL**,
the remote having been public since 2026-08-07 with two public siblings. **So what a rewrite buys has shrunk
from *prevents exposure* to *stops future copies***, and that is a much weaker thing to pay an irreversible
operation for. *A rewrite would not un-serve what has already been served.*

**BOTH ALTERNATIVES WERE PUT AND BOTH WERE DECLINED BY NAME, recorded so they are not re-proposed as new:**

1. **Rewriting the messages alone, now.** Declined: it pays the whole blast radius for the smaller half of
   the problem, and the author-identity population would still be waiting.
2. **Bundling them into the deferred author-identity pass.** Declined *as a thing to do now*, but **it
   remains the natural home when the trigger comes** — one blast radius paid once rather than twice, which
   is the house rule's own shape: *one pass covering both addresses.*

**THE TRIGGER IS AN EVENT AND NOT A DATE: the next force-push-class history operation on this repository,
whatever prompts it.** The messages ride in that pass rather than earning one of their own. **A date passes
and nothing happens; an event is something a session can recognise.**

**AND ONE THING THIS ENTRY EXISTS TO FIX.** Until it was written, the decision lived **only in the house
tooling repository's campaign record** — a file nothing in this project reads. The auto-loading house file
says in terms that what to do about a history already carrying the wrong address belongs to **this project's
own §3, with its trigger**. *A rule that lives in exactly one place, and that place is not where the work
happens, is the shape this whole propagation exists to remove.*

## 2026-09-11 — what the monorepo layout preserves, adds and costs

**Relocated out of `CLAUDE.md` §6.4 at THE CHARTER REDUCTION part (e), under route 2.** The charter keeps the
live constraint — *the duplication is deliberate and its removal is DEFERRED until the reconciliation
classifies the 618-pair residue* — and points here for the rest. **This is the reasoning, not a second copy
of the rule.**

**WHAT THE LAYOUT PRESERVES, none of it tidy-up-able.** The **154 separate sub-lexicon files** *(§6.1 forbids
reducing the file count for its own sake, and A3 measured the design correct)* · **both the US and the UK
term in every lexicon row**, which is what makes a variant build a selection rather than a translation · and
**the two distribution repos' URLs**, which users install from.

**WHAT IT ADDS:** one pull request touches **both** trees, so a fix cannot land in one variant and be
forgotten. **That is not hypothetical — it happened once and it shipped**, which is the whole reason the
monorepo was chosen over two repositories on 2026-07-28.

**WHAT IT COSTS:** the content is edited twice. **Removing the duplication — one source, generated variants —
is DEFERRED**, and the trigger is the reconciliation classifying the **618-pair residue**. Until that
classification exists, a generator would have to guess which of a pair is canonical, and a wrong guess ships
into both variants at once.

*(The layout itself — `uk/` IS the publishable tree, `tools/` and `tests/` siblings never inside it,
`.gitignore` by path — stays in `CLAUDE.md` §6.4: it is load-bearing every session, not reasoning.)*

## 2026-09-24 — the purpose guard's marker and route, and slice 4 made a detector rather than a reader of the original

**THE PURPOSE GUARD, INSTALLED AT THE OPEN OF BRANCH 10 SLICE 4** *(deferred at slice 3b's close on a
measurement: its probe looked for a marker this project's purpose line did not carry)*. Three choices, each
on the recommended option, put to Wouter at the opening input point:

1. **THE MARKER LIVES IN THE STATUS ROW.** The house guard accepts a line in a root `PLAN-*.md` carrying the
   literal `SESSION PURPOSE` and today's date. This project's purpose line is the status row's clause, which
   now opens **`THIS SESSION, <date> — SESSION PURPOSE — what · how · purpose:`**. `PLAN-3-opus5-migration.md`
   stays in the root: the guard reads it too, harmlessly, it being a future plan rather than a closed one.
2. **WIRED THROUGH THE HOUSE INSTALLER'S PURPOSE HALF ONLY.** Run as documented, the house
   `install_hooks.py` would have done three things nobody asked for: copied the house `pre-push` over this
   project's own, a different file by hash; wired `auto_mode_guard.py`, which `verify.config.json` declares
   absent with a reason; and pointed the purpose entry at the shared copy. So its own install and bite-test
   functions were called for the purpose guard alone, against `tools/purpose_guard.py`, and both git hooks
   were verified byte-identical before and after.
3. **AND THE SHARED INSTALLER WAS FIXED IN THE SAME SESSION**, under the house rule for a standard-script
   bug: `install_hooks.py` v4, with `--only` and `--guard-dir`, committed in the templates repository. **Its
   `standard-scripts/CHANGELOG.md` entry owns the reasoning** and it is not restated here.

**AND IT PROTECTED THE SESSION THAT INSTALLED IT, WHICH THIS ENTRY FIRST SAID IT COULD NOT.** The first draft
read *"hooks load at session start, so the first session it governs is the next one"* — the house
rule, written down unmeasured. **Measured the same day:** the guard's state file carried the INSTALLING
session's own id, written by the live hook on an edit made after the install, so an entry added to
`settings.local.json` took effect mid-session in the desktop app. **Not generalised past what was measured:**
the charter's section 5.6 sentence about the evidence guard concerns a different file and was not re-tested.
**Its escape route, stated because an unwritten one is the same as
none:** it matches only the four editing tools, so its entry in the gitignored `.claude/settings.local.json`
can always be deleted through Bash or PowerShell.

**SLICE 4's THREE CHOICES** — the page-break pass becomes a DETECTOR with no new input; the principle is a
declared `PASS_CONDITIONS` table in `post_process.py`'s header, enforced by `tests/test_pass_conditions.py`;
and the detections reach the change journal at schema 3 — **are owned, with the measurement they were chosen
on, by section 3.8 of `PLAN-2-step-b.md`**, and are not summarised here. **What was DECLINED, and why it is
recorded:** reading the original through a new `--original` input at Step 6, the slice's literal shape. On
this corpus it would have restored **0 of 11** breaks, and it would have added the flag decision 2c forbids.

## 2026-09-29 — section 4 re-capped at its measured 30, and why the signed-Python rule was not relocated

**§4 OF `CLAUDE.md` IS RE-CAPPED FROM 23 TO 30 IN `verify.config.json`** *(Wouter, 2026-09-29 (2), at the
closing input point, on the recommended option)*. The seven lines are the signed-Python rule he put in §4 on
2026-09-28 (4) — no Python process moves or renames a Word, email or PDF file, and the project runs on the
signed system Python 3.14 — **so that it is read before any code touches a file.** A filled section's cap is
its measured size, so this is a re-measurement and not slack; every other section keeps its margin.

**THE TWO ALTERNATIVES, AND WHY EACH WAS DECLINED.** *(1)* **Moving the rule to `.claude/rules/`** behind a
`paths:` glob over the Python files: a scoped rule loads once per session, when a matching file is first read,
and is not put back after a compact — which defeats the reason the rule is in the charter at all. *(2)*
**Moving §4's dev-host toolchain paragraph** to a companion document: it would pay for the rule by relocating
text that is read for the same reason, before a script is run.

**HOW IT WAS CAUGHT, AND WHY THAT IS RECORDED.** `feature/signed-python-no-doc-moves` merged `66af307`
(PR #119) with `verify_md`'s *section length* row newly RED, and nothing said so: its verify ran the eight
document instruments and its commit gate the confidentiality controls, and `verify_md` is in neither. **Slice
4a's gate comparison, run by content against its base, is what saw it** — a standing red compared by content
and never by its exit code, the house rule that caught it.

## 2026-09-29 (3) — C30's refusal kept narrow, slice 4b pushed, and the stale checkers deferred to the next open

**THREE RULINGS AT THE CLOSING INPUT POINT, EACH ON THE RECOMMENDED OPTION** *(Wouter, 2026-09-29 (3))*.

**(1) C30's SEGMENT HALF COUNTS ONLY ONCE A PARAGRAPH HAS `en`.** His choice (5) on 2026-09-28 (3) said
`validate_translations.py` refuses a `<<TRANSLATE:` placeholder left in `en` or a segment, and slice 4b's
written plan read *any `en_segments` entry*. The in-context review of the diff found that form wrong in
scope: Step 3b writes the placeholders BEFORE translation, and this script runs after every batch of 35,
so it would refuse batch 1 on a paragraph not due until batch 3 — a gate whose only compliant way out
fights the batch discipline. **Apply skips a paragraph with no `en`, so none of its segments can reach
the document either way**; a placeholder in `en` itself is refused whatever the paragraph. The broad form
was declined for that reason. `tests/test_notes_gates.py` arm 29 pins the rule as kept.

**(2) THE BRANCH PUSHED AND ITS PULL REQUEST OPENED**, the repository being public, so pushing publishes
it; the merge stays his.

**(3) `verify_code.py` v10 AND `check_checkers.py` v17 ARE RE-COPIED AT THE NEXT SESSION'S OPEN**, a
commit of their own with the gate re-baselined after it. They were found a version behind the shared
folder at this session's open and left, so the gate measured with one set of instruments throughout.
Re-copying on this branch was declined because it mixes an instrument change into a slice's evidence;
leaving them stale again was declined because the house rule for a STALE checker is to re-copy it.

## 2026-09-29 (4) — the project's own installer renamed, rather than declared around

**ONE RULING AT THIS SESSION'S OPEN, ON THE RECOMMENDED OPTION** *(Wouter, 2026-09-29 (4))*.

**`tools/install_hooks.py` IS NOW `tools/install_project_hooks.py`.** `check_checkers.py` v18, re-copied
at this open under ruling (3) above, began tracking the house installer by name, and read this project's
file of that name UNKNOWN: it differs from the house script and carries no `CHECKER VERSION`, because it
is a different program — it installs this project's git hooks from `tools/hooks/`, where the house one
installs the house's. **The house's four questions put the fix in this project:** the checker's logic is
right to say a file under a house name is not the house's file, so question 1 fails; the project-only
route the house offers is a `FORKED FROM` header, which would state something false, the file's own
docstring having said since 2026-09-09 that it is not a fork. **Declined:** a general "own script"
declaration added to the house checker, a change to every project for one name clash; leaving the row
UNKNOWN to the close; and the fork header. The house installer is declared absent in
`verify.config.json` with its reason and a trigger, and the name is left free should this project ever
want it.

**AND THE RENAME FOUND A DEFECT IN THE INSTALLER ITSELF, FIXED IN THE SAME COMMIT.** Its `--check` swept
every file in `tools/hooks/`, `evidence_guard.py` included — a Claude Code hook wired through
`.claude/settings.json`, which Git never runs — so it reported that file "not installed" and exited 1 on
a correctly installed repository. A git hook is named for its event and has no extension; a file with one
is now skipped and said so.

## 2026-09-29 (4), at the close — C16's class counted, the wiring its own slice, arm 9's re-pin kept

**FOUR RULINGS AT THE CLOSING INPUT POINT, EACH ON THE RECOMMENDED OPTION** *(Wouter, 2026-09-29 (4))*,
put with what each would do measured first, from this session's own corpus runs.

**(1) C16's CLASS IS COUNTED, NEVER BLOCKING** — his choice (8)'s first question. After slice 4, today's
output blocks on 14 findings in the delivered check's text-and-anchor arm, every one C16's — 3
`changed/space` and 11 `inner-space`, on six documents — a spacing apply itself creates, which no operator
can repair. **Declined:** keeping them blocking until a C16 fix exists, which would stop those six documents
with no way out; and deciding only after his page read of D02's paragraphs 101 and 168, which can still
promote those two if they split a word. **One assumption, stated at the close:** implementing the ruling in
`validate_apply.py` belongs to the wiring slice, which acts on that very count, so it is built there with
its own acceptance rather than here.

**(2) STEP 10's WIRING IS ITS OWN SLICE**, explored and planned next session, its acceptance measured before
any choice. Measured today, a wired Step 10 would block on C16's 14 unless counted and on D03B's glossary —
2 findings an operator CAN clear — and six document-variants never reach Step 10, stopped earlier by
post_process's drift gate. **Declined:** wiring it next session without a planning round; and leaving Step 10
report-only to move on to branch 12.

**(3) ARM 9's RE-PIN IS KEPT**, a judgement slice 4c took alone: its declaration carried a line break, which
4c splits, so it was moved onto a declaration with NO break, keeping its claim that a flattened comment is
counted and never blocks. **Declined:** restoring it repointed at the split, with a new arm for the no-break
case — two arms where one already pins it.

**(4) SLICE 4c's BRANCH PUSHED, ITS PULL REQUEST OPENED, AND SQUASH-MERGED** once `verify_md` and the eight
document instruments pass on its head, as #122 and #123 were; the repository being public, pushing
publishes it.

## 2026-09-29 (5) — slice 2b's page read, and four rulings on what it found

**RECORDED 2026-09-30, BECAUSE SESSION (5) STOPPED AT WOUTER'S WORD WITH NOTHING COMMITTED**, so until
this entry the rulings below lived only in a handoff prompt — including (c), the one that says WHEN.

**THE PAGE READ.** At the session's open Wouter read slice 2b's changed pages of D02, D10 and D11, the
item carried since 2026-09-25 (3). What it found is in section 3.2 of `PLAN-2-step-b.md` and in register
rows J2, D2, D4 and I-33, measured before filing; it is not restated here.

**FOUR RULINGS, EACH ON THE RECOMMENDED OPTION** *(Wouter, 2026-09-29 (5))*. **(a)** The words-touching
finding is a new row, **J2**, in cluster J beside J1 — not an amendment of J1 alone, because J1's claim
and J2's cause are different things. **(b)** The stale note beside the rendered pages is filed as
**I-33**, and its CLASS is fixed inside Step 10's wiring slice: the tool refuses to write pages for a
person to read unless the run states, in its own command, what change is under review — a note typed
once into a tool cannot be kept current by remembering to. **(c)** D08's page 2 and D02's paragraphs
101 and 168, his other two page reads, are rendered for him in the NEXT session. **(d)** Pace: each
sub-step opens with the board and its purpose and then carries straight on; questions wait for an input
point and always go through the question tool, never as prose.

**AND WHAT THE FILING CHANGED, 2026-09-30, WHICH IS A MEASUREMENT RATHER THAN A RULING.** Session (5)
read J2 as glue the scrub introduced. Measured seam by seam from the notes, every one of the 18 declared
insertion/deletion seams the operator separated by U+200B alone, with the English meeting letter to
letter, meets letter to letter in the SOURCE at the same boundary — so the delivered redline is the
source's own, and what is wrong is the reason Step 4's Rule 1 gives, not what it prescribes. J2 was
filed LOW on that basis; which branch corrects the reason, and whether to, is put to Wouter at the
2026-09-30 input point.

## 2026-09-30 — Step 10's wiring planned as one slice, and seven answers at one input point

**SEVEN ANSWERS, EACH ON THE RECOMMENDED OPTION** *(Wouter, 2026-09-30)*, put after the wiring was measured
on both variants — section 3.2 of `PLAN-2-step-b.md` owns the measurement and the plan, not restated here.

**(1) C16's CLASS IS COUNTED IN BOTH MEASURED SHAPES.** Every one of the 14 findings adds a space and none
loses one: 12 add it beside a space already there, 2 add it between two letters at a tracked-change boundary
where the source has whitespace. Both shapes are counted, a lost space and a space added inside a segment
still block — the narrowing the trailing-space ruling set, one exemption per measured population.
**Declined:** doubled spaces only, which would stop D02 at Step 10 on two findings no input can repair; and
the whole class, which would let a glued word through unblocked.

**(2) THE CHECK IS CALLED BY REPACK, ON A CHECK COPY, BEFORE ITS ONE WRITE**, as its other delivery gates
are, so a blocking finding leaves nothing at the delivery path. **Declined:** reading the archive in memory,
a larger change to a script already past W1's observed size; and Step 11a, after the write, where a failed
file already sits at the delivery path.

**(3) RULE 5b's WAY OUT IS A DECLARED `accepted_consequences.json`** beside the notes — each accepted
finding by identity, with its attempts and the five ACCEPTED CONSEQUENCE lines; a stale entry refused, an
undeclared finding still blocking, no flag switching the check off. **Declined:** no way out, which leaves
a right check with no repair ending undelivered where rule 5b expects a disclosed delivery; and deciding it
at the build.

**(4) J2: RULE 1's STATED REASON IS CORRECTED INSIDE THE WIRING SLICE**, both trees, the prescription kept,
so branch 11 owns J2. **Declined:** leaving it to D2's claim audit; adding a space on each side, measured to
put a gap the source's redline lacks at 18 of 18 seams; and recording it only.

**(5) ONE SLICE, SUB-STEPS 1 TO 4 IN ORDER**, one branch and one pull request. **Declined:** two slices with
I-33 apart, and I-33 first.

**(6) THE PURPOSE GUARD — "the house fix is done, continue and start using the new files".** Read at the
answer: the house withdrew `purpose_guard.py` v3 and `install_hooks.py` v6 on 2026-09-30 and restored v2
and v5 byte-identical, with the board rule cut back to four moments. This project holds v2, and
`check_checkers.py` reads 15 tracked, 0 needing a decision, so nothing is copied.

**(7) THIS SESSION's DOCUMENTATION IS PUSHED AND ITS PULL REQUEST OPENED**, once `verify_md` and the eight
document instruments pass on its head; the repository being public, pushing publishes it. His to merge.

## 2026-09-30 (2) — C16 counted in the three places measured, and two judgements taken building the wiring

**THE APPROVED NUMBER DID NOT HOLD, SO IT WENT BACK** *(Wouter, 2026-09-30 (2), on the recommended
option)*. Measured as the check itself sees them (`temp/s0930b_c16_view.py`, a patched copy of the check,
classes only), every one of the 14 blocking C16 findings is plain spaces ADDED and none lost — but three
add one in a place neither shape of choice (1) named: next to punctuation at a tracked-change boundary
where the source has whitespace (D02 168, D08 40), and at a paragraph's end where the source paragraph
ends in whitespace (D08 28). Built literally, choice (1) left uk 3 and us 2 blocking, not 0. **Ruling:
count all three places** — beside whitespace already there, at a boundary the source spaces whatever the
neighbours, at an end the source shares; a lost space, a split word, a space where the source has none, a
no-break space and a reading that differs by more still block. **Declined:** exactly the two shapes, which
would stop uk D02 and D08 on both variants at Step 10 on findings no input can repair; and the boundary
without the paragraph end, which would stop D08.

**TWO JUDGEMENTS TAKEN ALONE, CARRIED TO THE CLOSE.** **(a)** `tests/test_delivered_check.py` arm 16's
`gain-inner`, which the plan did not name, re-pinned beside arm 18's `rebase-inner`, which it did: both
deliver a doubled space, the shape the ruling counts. **(b)** `tests/test_repack_scrub_and_block.py` case
1c given the footnote declaration a compliant run makes: its synthetic original's footnote shipped in the
original's words, undeclared, which the wired check rightly refuses — C6's shape — so the test's input
changed and the gate did not.

**AND A MEASUREMENT FOR J2.** The notes of all 13 workdirs declare 0 ins|ins and 0 del|del seams
(`temp/s0930b_seam_same.py`), so Rule 1's ins-ins half has never been exercised; the corrected reason
describes it and prescribes nothing new.

## 2026-09-30 (3) — the auto-mode tools installed, one unattended hop armed, and how it stops

**THE HOUSE AUTO-MODE TOOLS ARE INSTALLED, AND THE SETUP RIDES ON THE SLICE'S BRANCH** *(Wouter,
2026-09-30 (2): install the house guard and counter, then run N = 1 hop)*. `tools/auto_mode.py`,
`auto_mode_guard.py`, `auto_mode_headless.py` and `install_hooks.py` are byte-identical to the house copies,
each selftest passing; `install_hooks.py --only auto,purpose` wired the guard beside the purpose guard, fired a
real forbidden call at each and left this project's own git hooks alone; the evidence guard was proved still
biting. **The setup is committed on `feature/branch11-wiring`, not on `main`**, because the hop and its guard
run from the checked-out tree: a guard on `main` is not the one the hop loads. `AUTO-MODE-RUN.md` is
gitignored by name — this repository is public, and the counter rewrites the file at every claim and release.
The three declared absences in `verify.config.json` came OUT rather than being reworded: the first said this
project runs no unattended chain, which Wouter's choice made false. **Its TEST is scoped to what it touches**
— the smoke suite and the four selftests — because sub-step 2's uncommitted wiring shares the working tree
and fails `tests/test_glossary_route.py` on both variants, which is the hop's first task.

**THREE RULINGS ON HOW THE HOP STOPS, EACH REPLACING A MECHANISM MEASURED NOT TO WORK HERE** *(Wouter,
2026-09-30 (3))*. **(1) No dollar ceiling.** **(2) Three hours of work, or all of branch 11's remaining work,
whichever comes first.** He asked first for *context full or the weekly limit at 93%*, and a headless probe
measured that such a session has NO usage tool, so it can read neither figure. The runner's own time limit,
which defaults to one hour and kills the hop when it runs out, is raised to a backstop just above three hours.
**(3) The hop still asks its questions, answers each itself on the recommended option and carries on**,
recording what it built on every answer, and the next attended session tests each one with him. This replaces
the house's stop-on-a-blocking-question for this hop only; an irreversible act stays refused by the guard
whatever the answer.

**AND TWO CORRECTIONS TO THE HANDOFF PROMPT.** It said the record commit reuses sub-step 2's evidence, *the
same worktree hash*: `cycle_evidence.py` hashes `git diff HEAD` and keeps one record per phase per branch, so
once sub-step 2 commits, HEAD moves and that evidence is stale for the record — the hop re-records before it.
And the launch command it gave, `--run --max-budget-usd`, names an option the runner does not have.

## 2026-09-30 (4) — wiring-hop1 hop 1: the judgements taken alone building sub-steps 2 to 4

**ONE UNATTENDED HOP, NOBODY TO ASK** *(the run armed 2026-09-30 (3); every question the hop would have put is in `temp/auto-closing-questions.md`, answered on its recommended option, for Wouter to confirm or overturn)*. Each judgement below changed a test's input or a design detail the approved plan left open — **none changed a gate, an approved number or a delivered byte for a run without the new file.**

- **J-B1** test_glossary_route arm 5 given slice 3b's glossary keep declaration. The arm passed the ORIGINAL glossary to --glossary (the keep-as-is route) with no glossary_translations.json; the wired delivered check refuses that as side-glossary / kept-source, rc=1 on both variants. Case 1c's shape exactly: the check right in scope, the test's operator non-compliant since slice 3b. The input changed, never the gate. Reversible by one revert of the sub-step 2 commit's test hunk.
- **J-B1b** tests/test_no_delivered_byte_moves.py's repack harness declared a tab as a space (its own declared_text) and left the fixture's comment and footnote undeclared; the wired check reads the body as extraction does (a tab contributes nothing) and refused 4 findings. The harness now declares extraction's own text, en equal to it, plus slice 3b's keeps for the comment and the footnote. The gate unchanged; byte identity to the pin held on both fixtures, 12 of 12.
- **J-B1c** tests/test_checks_can_fail.py C25 fed repack an empty paragraphs.json, which the wired check reads as VOID (exit 3) and refuses, rightly. Its claim is only that repack completes when --paragraphs is given, so the notes are now extraction's text with en equal to it. The gate unchanged.
- **J-B2a** Sub-step 3 lives in repack's _delivered_gate, not in validate_apply. The check keeps reporting every finding and exiting 1; repack reads its report and the declaration. So "no flag switches the check off" holds literally - the check has no new input at all - and the decision sits where the refusal already lives.
- **J-B2b** The file's shape: {"accepted": [ {idx | part (+ id), class, shape, attempts 1-5, check, consequence, where, "reader must"} ]} - the five ACCEPTED CONSEQUENCE lines as verbatim keys, so the printed block is the file read back. Identity is the check's own report fields.
- **J-B2c** A document-level finding (an anchor count, which has neither idx nor part) is named "part": "document" - the label the check itself prints for it.
- **J-B2d** Sub-step 3's TEST: the full s0930b set; the corpus arm not re-run, declared - no workdir holds the file, so the corpus path is sub-step 2's, proved at 75a4e54.
- **J-B3a** render_diff's kept folder stays under the logs folder's branch6-render/, where Wouter already looks, named <document>-<variant>; only the leaf changes.
- **J-B3b** Sub-step 4's TEST declared narrow - smoke, test_render_keep, test_parity_check - since no other suite drives render_diff (it needs LibreOffice and the logs folder); a real --doc render was not run, because nothing it renders or compares changed and the hop may not read a page.

## 2026-09-30 (3), after the hop — the hop's six answers confirmed, its effort kept, five review findings fixed

**THE HOP'S SIX ANSWERS, EACH CONFIRMED ON ITS RECOMMENDED OPTION** *(Wouter, 2026-09-30 (3), through the
question tool, after the attended session re-measured the hop's work: 17 of 17 suites re-run green, and the
13-command gate identical to the hop's close but for three lines its last commit and two later commits explain)*.
**Q2** keep arm 16's re-pin and case 1c's footnote declaration. **Q3** no register row for Rule 1's ins-ins
half until a document declares such a seam. **Q4** keep the hop's three test-input fixes. **Q6** measure
render_diff's repack arm on a real document next session — mechanically, no page kept — then give it the keep
declarations a compliant run writes, and file a register row with the measurement. **Q5 with Q1** review the
slice's diff first, then push and open ONE pull request, #126; he then approved the push and the squash merge in
chat before the tests had finished, the merge to follow the record. Nothing the hop built was undone.

**THE HOP RAN AT MEDIUM EFFORT, AND IT WAS KEPT** *(Wouter)*. The arming session ran at xhigh; a runner
launched from a plain terminal gets the CLI default, measured as medium on 66 of 66 of the hop's messages.
Offered a relaunch at xhigh fourteen minutes in, nothing committed, he let it run. **The fix is the house's,
not this project's** — *"confirm next time that we use the same effort as we are using in the session which
started the auto-run ... across all projects"* — and it is re-copied here in `86dc767`: `auto_mode.py` v3
records the arming session's effort and refuses to arm without one, `auto_mode_headless.py` v6 passes it on
and reports a hop that ran at another.

**THE REVIEW: EIGHT FINDINGS, NONE LETTING A WRONG DOCUMENT THROUGH, FIVE FIXED NOW** *(Wouter's choice)*. A
`/code-review` at xhigh over `052987d..HEAD`, in the attended session. **Fixed in `a5ec030`:** an unreadable check
report refuses with the gate's own marker; Step 10 states rule 5b's attempts as SKILL.md does, at most five; the
render_diff note and manifest name the pages actually written, per arm; a failed extraction is a named VOID in
the byte-moves suite; two teardowns hold on the failing path. **Carried to the Q6 work, which touches the same
code:** render_diff's repack arm itself; rule 5b's side-part and anchor identities, untested through repack; and
the keep-declaration builder, hand-built separately in three harnesses.

**AND THE FIRST MEASURED WORKING HOP:** 160 turns in 1 h 50 min; its cost is in the runner's own usage line in
`temp/auto-mode-transcripts/`, never in a committed file, whose confidentiality gate refuses any amount.

## 2026-10-08 — branch 11's follow-up: Q6 measured and fixed, rule 5b's identities tested, one keep builder, the close pass decided

**SIX ANSWERS, EACH ON THE RECOMMENDED OPTION, AND A SEVENTH BELOW** *(Wouter, 2026-10-08, through the question tool)*. **At the open:** all four items in this session, on one branch and one pull request. **At the close, on the measurements `PLAN-2-step-b.md` section 3.2 records:** **(1)** C1, C6 and C18 CLOSED — each row's open half was "the check exists but Step 10 does not block on it", built by #126 and measured. **(2)** C8 and J1, whose text already read CLOSED, marked so in their severity cells; C22 CLOSED for branch 11, its language-detection half branch 12's, as its own text already said. **(3) and (4)** A24 and A25 DEFERRED together, out of branch 11: since #126 their shapes are refused at Step 10 rather than shipped, rule 5b the only exit, and no corpus document carries either. The trigger is an event: the first real document, Step C's eleven included, carrying a tracked change in a side part, or Step D before publication, whichever comes first. **(5)** I-36 filed OPEN, its fix the next session's first item — the pins and the coverage they guard together. **(6)** The branch pushed, one pull request, squash-merged once the record commit is green.

**(7) AND A SEVENTH, AT THE SAME CLOSE, ON A RED THE RECORD ITSELF RAISED** *(Wouter, 2026-10-08, choosing it over holding the merge)*. Writing A24's measurement made `tools/stepb_audit.py` check 3a count the no-compliant-repair set at nineteen against the eighteen the plan is written on — A24 and A25 are rows an operator can now walk into with rule 5b the only exit, and A25 escaped the pattern only by its wording. **The set was re-derived to TWENTY in this session:** A25 worded as A24, the plan's section 12 and branch 4's row in section 9.3 and F41's row given a dated TWENTY beside the eighteen they were written on, which stays as history; `stepb_audit.py` expects 20 and `stepb_metacheck.py`'s count fault was moved onto the new figure, and fires. Every other statement of eighteen is dated reasoning about branch 5, an unrelated count, or this log's history, and was left.

**JUDGEMENTS TAKEN ALONE, EACH CARRIED TO THE CLOSE.** **(a)** render_diff reports a refused repack by its gate marker and class counts, never by the raw tail of its output, which can carry lexicon context snippets — taken inside I-34's fix because it is the same function; the code review then found the same class one call earlier, and a real document's failed post_process or reorder is now reported by exit code. **(b)** render_diff declares the side parts kept from the WORKING TREE's scripts on both arms, so the two arms get one input and the code stays the one variable. **(c)** I-35 fixed rather than declared: the corpus flag's keep is written only where repack is given the original's own glossary. **(d)** The code review at xhigh raised nine findings. Five were fixed: the pin constant `REF` shadowed in the wiring suite, the raw post_process line, a crash path that could leave a real document's files in the temporary folder, the fixture path's lost diagnostic, and the helper's docstring. Four were declined: the gate-marker table copied from `tools/delivered_corpus_arm.py`, which cannot be imported and is declared there as a copy; the helper running twice per document, seconds beside LibreOffice's minutes; its `w:`-prefix regex, which is Step 8d's own template and so what a compliant run writes; and new scripts outside `temp/`, where this project's instruments and suites have always lived.

**AND ONE MEASUREMENT THAT IS NOT A RULING.** The first VERIFY ran to the end with three commands' output stopping at the same minute and the corpus runs' empty — killed with the shell a plain `&` had started the chain in, not failed — and was re-run in full through the tool's own background run with the machine kept awake; every number above is the re-run's.

## 2026-10-08 (2) — I-36 fixed, the gate's control 6 scoped to a working copy, C6 amended, branch 12 planned

**SEVEN ANSWERS AND TWO MORE, EACH ON THE RECOMMENDED OPTION** *(Wouter, 2026-10-08 (2), through the question tool)*. **At the open:** both items this session, on one branch and one pull request; and `--sides` with `--declare-glossary-kept` measured and pinned in I-36's fix, refused beside `--skip-step8`, which it contradicts. **At the close:** **(1)** the pre-commit gate's control 6 given the narrow scope fix — a working copy's own fixtures allowed, a Word file anywhere else in it still caught — rather than waiting for the other session or excluding the whole folder; **(2)** C6 given a dated amendment, its closure standing; **(3)** the branch pushed and squash-merged once the record commit is green; and branch 12's four — **(4)** the language DECLARED at Step 1 and cross-checked by repack's agreement; **(5)** an unsupported or unsettled language reported NOT SUPPORTED, never CLEAN, the run continuing; **(6)** three slices; **(7)** 12a's acceptance as measured. `PLAN-2-step-b.md` section 3.2 holds the measurements each rests on.

**JUDGEMENTS TAKEN ALONE, EACH CARRIED TO THE CLOSE.** **(a)** The skip-Step-8 scenario made faithful — the chain hands repack no declaration — on reading `chain()` against the red runs, the prediction written before the run; it is what the arm's own docstring said it measured, and it moved C6's record, which went to Wouter. **(b)** A refused document's flattened-comment pin printed NOT ASSERTED rather than VOID: a counted finding never blocks, so no refusal can carry it, and a VOID would fail every run on a structural gap. **(c)** The code review at xhigh raised eight findings. Six were fixed: the footer tally and its VOID naming the documents they cover, a mixed-stop document failing on its own, a git error read as VOID rather than as after the wiring, the refused document's label, expected refusals counting only non-zero pins, and a nested conditional written as if and elif. Two were declined: the refusal read from human-readable text, guarded by its stated total, a machine-readable one meaning a change to a shipped script; and the three-line count matcher beside `side_match`. **(d)** The metacheck incident repaired byte-exact twice and flagged as a separate task rather than fixed here; Wouter started that session. **(e)** The same scope gap found at the close in `tools/claudemd_claims.py` check 6 — a working copy's own `temp/` read as a stray — fixed under the same ruling rather than put to Wouter again, the house's fix-the-class rule applying: the same narrow rule, red first, a stray elsewhere still caught.

## 2026-10-08 (3) — the in-place mutation class closed: the metacheck plants in a copy and scores by content, and every test changes a repository file through one recoverable guard (I-37, I-38)

**WOUTER'S FOUR ANSWERS, at the opening input point, each the recommended option.** **(1)** All eleven sites, plus guards against a twelfth. **(2)** The metacheck's hollow verdict made honest in the same branch. **(3)** This session writes its files through Python run from the shell — `tools/purpose_guard.py` reads the MAIN checkout's plan file, where another session's purpose line stood, not this worktree's — and the guard is fixed in the shared standard-scripts copy last. **(4)** Two register rows, I-37 and I-38.

**JUDGEMENTS TAKEN ALONE, EACH CARRIED TO THE CLOSE.** **(a)** The ten tests use a recorded guard, not a copy: the tools they drive read the repository through git or fixed paths, so a copy would need a root option in six tools and a git history in two. **(b)** A `protecting()` record — the evidence store — is never settled automatically, a protected file's change being indistinguishable from a person's; `--restore` or `--discard` decides. **(c)** The commit gate exempts only the records of a LIVE process that ASKS, by `PRECOMMIT_GATE_EXEMPT_PID`. The first version matched the gate's parent process, which never matches here — a uv environment's `python.exe` is a launcher, measured 30600 against the test's own 7700 — and `test_gate_tree_scan` fell from 17 of 17 to 14 until it was changed; the code review found it by running the test. **(d)** The second guard against a twelfth site — the runner checking that each test leaves the tree as it found it — was NOT built: no committed runner runs `tests/test_*.py`. The guard's hash-checked restore and the static test stand in its place. **(e)** `stepb_audit.py` and `stepb_audit3.py` read the private folder from `LT_PRIVATE_DIR`, as `precommit_gate.py` already did; five more tools build that path from the checkout's parent or the current folder, and are left as their own task. **(f)** `test_cycle_gate`'s docstring said its evidence store was a throwaway. It never was, and a kill there left the test's own passing evidence where the commit gate would accept it.

**MEASURED, NOT A RULING.** Two overlapping metachecks bake a defect in with no kill at all: the second reads the first's planted bytes as the original, restores them, and prints that the file is byte-identical — demonstrated at `66418bb`. Whether that is what happened in the two incidents of 2026-10-08 (2) is not established: no second metacheck of that session was running at 16:19, and the one of these that started is not known.

**(g) AND ONE THE RECORD ITSELF RAISED.** A blank line between register rows I-20 and I-21 had ended the instrument table, so I-21 to I-36 — and the two filed here — rendered as loose text; removed, and `md_tables.py` reports 5 orphan rows where it reported 21. The five left are cluster F's own break, before F43, left for its owner. Neither was ever reported: the document runner calls `md_tables.py` with no file, and that prints CLEAN having read nothing.

## 2026-10-09 — the table checker's bare run checks the documents, and the register's two table breaks rejoined (I-39)

**FOUR ANSWERS, EACH ON THE RECOMMENDED OPTION** *(Wouter, 2026-10-09, through the question tool, in a worktree session beside #130 and the branch-12a session)*. **(1)** `tools/md_tables.py` run with no file named checks the project's documents — the same set `tools/publication_check.py` reads, its six core names kept by name and its globs — prints what it read, and exits 2, VOID, when that set is empty, a core name is gone, or any file it was to read cannot be opened; it was neither refused outright, which would have left every bare caller to be edited, nor widened to all 376 tracked Markdown files, which would have turned every document runner red on two shipped lexicons. **(2)** This branch starts from `main` and deletes the blank line between I-20 and I-21 as well as the one between F42 and F43 — #130 makes the first deletion identically, so the two combine without a conflict in either order — so that the register shows 0 orphan rows on this branch alone. **(3)** The false CLEAN is filed as **I-39**: I-37 and I-38 are #130's and are cited by its commits, so neither may be taken, and the count line both branches edit is resolved by whichever merges second. **(4)** Section 7 of `CLAUDE.md` is left alone — it is being rewritten by #130 and by the branch-12a session — and this entry, the register row and the pull request carry the record.

**THE PLAN, WRITTEN BEFORE ANY CODE.** *Sub-step 1, the checker:* change only how the file list is formed and what an unreadable file does; the table logic — what counts as a header, a delimiter, an orphan row or a width mismatch — must NOT move, and a file it reads still exits 0 or 1 as before. Done when a new test, red against `main`'s checker on its bare run, is green, with a positive control still firing and a guard that fails if its document set drifts from the publication check's. *Sub-step 2, the register:* delete exactly two blank lines and nothing else — no row renumbered, no row's text touched — checked against the table model the checker itself uses. Done when `md_tables.py evidence/REGISTER-findings.md` reports 0 orphan rows and 0 width mismatches, the register validator passes with only I-39's counts moved, and the byte difference is those two lines plus the new row. *Sub-step 3, the record:* I-39 and its two counts; the audit-gate skill's command that names two documents by their pre-move paths, so that it crashes today, replaced by the bare run; this entry; one pull request.

**WHAT WAS BUILT.** `tests/test_md_tables.py`, twelve cases, was red first on the unmodified checker — cases 1 to 5, the drift guard, the two the code review added and the capped-report case failing, its three controls passing — and is green on the fixed one. Run bare, the checker now reads 19 documents and lists each; on `main` that run reports the register's 21 orphan rows where it had printed CLEAN. The register lost exactly two blank lines, four bytes, and gained I-39 and its two counts, taken from `audit_register.py`'s `instrument=37(32f/5o)` after the row was filed; it reports 0 orphan rows and 0 width mismatches, and the validator passes.

**JUDGEMENTS TAKEN ALONE, EACH CARRIED TO THE CLOSE.** **(a)** FILES READ is printed on every run, named or bare: a denominator is the cheapest thing a check prints. **(b)** A run that reads some files and cannot read another is VOID even when the rest are clean — a partial read cannot certify — while problems in what it did read are still printed. **(c)** A named file is still opened as given, relative to the folder the command runs in, unlike `publication_check.py`, which resolves it from the root: the callers that name files either pass absolute paths or run from the root, so changing it buys nothing and moves a contract. **(d)** The six bare callers — five gitignored runners in the main checkout's `temp/`, one in #130's working copy — were not edited: they now read the documents, and the gitignored ones belong to other sessions. **(e)** Two shipped lexicons carry a third column under a two-column header — `italian-finance-banking.md` 12 rows and `italian-transport-and-insurance.md` 1, in both trees — which the checker sees only when named. Outside this scope, so offered as a separate task rather than filed here, filing a skill row moving typed counts in four files. **(f)** The checker was not given a `--selftest`: the house runner discovers every tool carrying one and its entry-point arm counts them, so a new one would move that arm. The test is a top-level command, as this project's other tests are. **(g)** The code review at high raised five findings and all five were fixed: a row the console cannot encode no longer kills the report, a file named twice is read once, case 1 compares the FILES READ list itself rather than searching the output, the drift guard covers the shape sweep's copy of the list too, and the test's temporary folder cannot leak. **(h)** A second defect in the same file, relayed by the lexicon session at Wouter's choice: the report printed only the first eight mismatches and five orphans with no word of the rest, so twelve mismatches in one lexicon read as eight and hid a second, unrelated fault. It now names every unprinted row by line number, red first as case 12; `PIPE` and `DELIM`, which that session's new test imports by name, are unchanged.

## 2026-10-09 (2) — two shipped lexicon tables made to match their headers, GENCON and BALTIME corrected, E15 and E16 filed and closed

**SIX ANSWERS AT ONE INPUT POINT** *(Wouter, 2026-10-09, through the question tool; branch `fix/lexicon-table-widths`)*. **(1)** The finance sub-lexicon's *Section Headings* table gains a `Context` column and its eight two-cell rows an empty third cell — over splitting it into two tables or dropping the nine descriptions. **(2)** The four short rows get an empty cell and no rendering is reworded — over moving the bracketed explanations out of the English cell, or writing new context. **(3)** The finding is filed in cluster E, as E15. **(4)** A guard is added, `tests/test_shipped_tables.py`, over every table of both shipped trees. **(5)** The transport sub-lexicon's GENCON and BALTIME rows are corrected HERE, as a second row, E16 — over the recommended separate task — so one pull request carries a structural and a content change, each with its own row. **(6)** The checker's capped report, which printed eight of twelve rows and made two unrelated tables read as one block, is relayed to the parallel session already editing `tools/md_tables.py` rather than fixed here; that session fixed it on `feature/md-tables-void-f-table`.

**JUDGEMENTS TAKEN ALONE.** **(a)** E15 sits under option 8 alone, not option 4 beside E1–E14: its guard reads the whole package, which is option 8's subject, and a malformed table is neither document furniture nor the prohibition column option 4 carries. **(b)** E16 sits in consequence group 5, *the manual is wrong*, beside E7 and E8, and under option 4 with the rest of the lexicon-content rows. **(c)** Section 9.3 of `PLAN-2-step-b.md` gives this branch a row of its own rather than adding either id to branch 19's row: neither is branch 19's to fix, and both are closed. **(d)** The empty cell is written `| |`, which every table reader here already splits into one empty cell — asserted by the new test's clean control. **(e)** BALTIME's designation is BIMCO's own title as HM Revenue & Customs lists it, *Uniform Time-Charter*; GENCON's is BIMCO's own description, *General-purpose voyage charter*, with *voyage* in its Notes cell too — checked against BIMCO's contract pages and that list on 2026-10-09, and recorded in E16. The first wording was GENCON's formal title, *Uniform General Charter*, and the commit gate refused it: the title is three capitalised words in a row, which the commit gate's added-line arm reads as a personal name — and the answer to that is to stop writing the shape where nothing needs it, never to loosen the check. **(f)** `CLAUDE.md` section 7 is NOT replaced on this branch: four sessions worked in parallel today and section 7 is the main line's handoff, slice 12a's; this branch's record is this entry, the two register rows and its pull request — carried to the close for Wouter. **(g)** The guard is called from `tests/run_tests.py`, the suite run on every change, and NOT from the pre-commit gate: the code review found that a suite nobody calls guards only when someone names it, which is E15's own root cause, and two parallel branches are editing `tools/precommit_gate.py` today while none touches `tests/run_tests.py`. Whether it should also block a commit is carried to the close. **(h)** `tools/stepb_metacheck.py`'s option-4 probe now reads the plan's current figure and adds 3: its literal anchor went inert at 16 → 17 inside this very change, and would again at the next row option 4 gains.

**AT THE CLOSE** *(Wouter, 2026-10-09, through the question tool)*. **(1)** #132 approved for squash-merge. **(2)** `CLAUDE.md` section 7 is left to the main line, which settles (f). **(3)** The guard stays in the smoke suite and does NOT join the pre-commit gate, which settles (g) — and the code review's reuse finding, the suite repeating `md_tables`'s walk, stays as it is, its drift caught by the per-file count cross-check. **(4)** The three house scripts the session-start version check flagged behind the shared copies — `purpose_guard`, `install_hooks`, `auto_mode_guard` — go to a session of their own.
