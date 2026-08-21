# DECISIONS-LOG.md — the dated record of what was decided, and why

> **Split out of `CLAUDE.md` on 2026-08-06**, when that file was rewritten around the seven-section
> structure Wouter set. **Nothing was retyped: the log below was moved by script and the move was proved
> content-preserving** (`temp/split_decisions_log.py`).
>
> **What this file is for.** It stops settled questions being re-litigated, and it records the *reasoning*
> behind decisions whose *effect* now lives in the charter. **`CLAUDE.md` §2.6 carries the short list of
> decisions that still bind; this file carries the argument behind each one.** Where the two disagree about
> what was decided, read the dated entry here — it is the contemporaneous record — then correct §2.6.
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
not the rule.** Two of §5.5's three impossible requirements — **F30** and **F33** — remain genuine dead
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
file before deciding, not reasoned from `CLAUDE.md` §2.6's summary of it, because §1.5 says a claim that
matters gets read at source. **This is the same tree with logging turned up: a CONFIG OVERLAY, decided
against a third tree.** The reason is measured — 176 of 198 files already diverge between two trees
*(2026-08-18)*, so a third triples the reconciliation and adds a tree that must never be published to a
repository whose whole discipline is *what you see is what ships*. **Same shape as §5.4's rule that the
scanner ships and the name list never does: the CAPABILITY ships, the VERBOSITY does not.**

**Sequencing, and Wouter was explicit: the overlay is built only after the UK and US skills are published
for external users.** But the **LOG FORMAT is designed before publication**, with D3's manifest work, and
that is not a hedge — §5.6 records that the forensic log and the shipped run report *"is the same
artefact, so designing the log format well gives the shipped report for free."* Design them apart and the
project owns two formats and a reconciliation. **So: one format, two verbosity tiers — the shipped
metadata-only report (§5.11, opt-in, already decided 2026-07-29) and Wouter's verbose local tier.**

**The monthly job tests against the then-installed skill, and that is the sharpest part of the idea rather
than a detail.** It is not log-reading: it replays the recorded failures against the skill **as it stands
that month** and reports which still reproduce. The machinery exists — §5.8's frozen-intermediate trick
makes the mechanical half a deterministic function, so a replay is seconds and needs no model. **That
turns production use into a regression suite that grows itself**, which is the never-regress rule (§5.5)
fed by real documents instead of by twelve July runs.

**PORTABLE, REPRODUCIBLE AND OBSERVABLE FROM THE START, because it moves to the cloud later.** Wouter:
*"local for now but I will eventually make all of my automations (including this check) portable,
reproducible and observable."* So it is **built for that from commit one rather than ported afterwards**:
no hard-coded local paths — every location by environment variable, the pattern `tools/gate_replay.py` and
`tools/stepb_audit.py` already use; the analysis reads its inputs by declared path and prints counts, never
names; and it exits non-zero on VOID rather than reporting a clean run over an empty set.

**AND THE CONSTRAINT THAT GOVERNS THE WHOLE DESIGN: A VERBOSE LOG OF A REAL TRANSLATION CONTAINS CLIENT
TEXT.** §6.5 already records that the A1 forensic logs quote real client text and are the most
content-rich artefacts this project has produced; a verbose production log is the same class. Four
consequences, decided now rather than discovered later: the logs live in a **sibling folder, never the
repo**; the **evidence guard must know that folder** or a monthly job running `ls` over it prints
counterparty names into a transcript, which is the one leak class no scanner here can reach (§5.4); only
**sanitised conclusions** enter the register, as with Wouter's review feedback; and the register needs a
**new origin class for production evidence** — the same gap the 5b probe hit when the validator rejected
`probe-5b` as unknown vocabulary, so it is one change serving both.

**What is NOT decided and is deliberately left open:** the log's field list, whether the monthly job is a
scheduled session or a cron-driven script, and what "presents changes to me" looks like as an artefact.
Those are Step B-style exploration, and §3.4's rule applies — *anything still short gets explored in the
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
constraint, not an aspiration: `CLAUDE.md` and `FINDINGS-REGISTER.md` now contain the answers, so A4 needs
a sealed brief that excludes both** — I-11's lesson, which cost four spoiled documents in the last review.
**A4 is PLANNED in one session and RUN in another.** Also decided at Wouter's prompting: **A3 owed answers
on RUNTIME and on REDUNDANCY** and had given neither — both are now measured sections rather than Step B
questions, because goal (i) asks for redundancy in terms and 25 minutes of fixed overhead is a structural
fact about the skill, not a fact about a fix.

**2026-07-31** — **A1 COMPLETE.** Batch session graded; register extended with cluster **T**; **A17's
mechanism corrected** (character style, not paragraph style) and **C19 reversed** (it recurs,
unrepaired). **A name-based leakage scan is not sufficient on its own** — two controls now required, and
three private tool files identified as never-committable. **`FINDINGS-REGISTER.md` gets a validator**,
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
> rewritten, **because the session it briefed has run and `STEP-B-ANALYSIS.md` is what it produced.** The
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

**2026-08-05 (Step B ran, and every option was decided).** `STEP-B-ANALYSIS.md` was written, reviewed option
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

1. **`OPUS-5-MIGRATION.md` and this file were split out**, on the same principle Wouter set for the Opus 5
   work: a self-contained workstream, and a dated historical record, are both easier to keep true outside a
   charter than inside one. **A new standing rule follows** and is in `CLAUDE.md` §5.13: anything
   substantial being added to the charter is placed in §2–§6 by subject, and if it is extensive, **ask
   whether it belongs in its own document before writing it in.**
2. **The build plan is no longer restated in the charter.** `STEP-B-ANALYSIS.md` §2 owns the order, §3 the
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

**THE RULE, now `CLAUDE.md` §5.4: instrument class plus language, and nothing else.** Never what the
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
layout, the skill-authoring convention no longer points at it, and the archived revisions are named in §6.5
as a never-committable location in their own right. **A decision that changes the plan and not only a file
has to change every place the plan is written down** — which is the failure mode the charter overhaul existed
to fix, applied to itself within the hour.

**2026-08-07 (how an instruction branch is tested — the graded run is replaced, not skipped).** Branch 3 was
presented with `STEP-B-ANALYSIS.md` §4's method for instruction branches — *"a graded run plus your review"* —
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
shipped. Recorded as a fourth sequencing fact in `STEP-B-ANALYSIS.md` §2, with its design and the direction
to read it in.

**Also decided the same day, both cheap and both converting an unverifiable claim into a checkable one.**
*(i)* The confidentiality gate now scans the **published trees**, which it never did — by diffing to added
lines only, because scanning whole trees returns 46 known-benign hits per tree and a reviewer facing those
starts skimming. Measured: branch 4's eight files give 6 hits, its 102 added lines give 0. *(ii)* An
**evidence-folder guard** runs before a shell command executes, because the one leak class this project
cannot scan for is the transcript — §6.5 says session metadata is reachable by neither the scanners nor the
location rule, and a session proved it by globbing a log folder and printing real corpus filenames into the
conversation.

**Left open, and put to Wouter rather than decided:** whether a 5b invocation should be required in a
**fixed, machine-recognisable shape** in the delivery notes. It cannot prove the five attempts happened —
but it makes a *silent* 5b impossible, which turns an undisclosed exception from invisible into a detectable
defect. Independent of the probe; ordering it first would make the probe's result mechanical rather than a
judgement about the operator's prose.
