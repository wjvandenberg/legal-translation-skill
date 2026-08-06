# OPUS-5-MIGRATION.md — goal (iii), and the verification run that follows it

> **Split out of `CLAUDE.md` on 2026-08-06**, on Wouter's instruction, because it is a self-contained
> workstream that nothing before it depends on. `CLAUDE.md` §1 and §3 point here; **this document owns the
> detail and `CLAUDE.md` owns the order.** Where the two disagree about *when* this work happens,
> `CLAUDE.md` §3 wins.
>
> **STATUS: NOT STARTED. Blocked on the build** (`CLAUDE.md` §3, step 2). Nothing here is a decision
> awaiting an answer — the design is settled. It is waiting for its turn.

---

## 1. What this workstream is, and what it is not

**Goal (iii) of the project: make the skill Opus 5-ready.** Expected to be a *small* change set, and the
reason it is small is measured rather than hoped: **every A1 run was already an Opus 5 run**, so the
baseline the whole project measures against is an Opus 5 baseline. Goal (iii)'s first requirement —
*observe how the skill behaves under Opus 5 before changing it* — **is already satisfied by A1.**

**It is not a performance project and not a licence to simplify.** The one rule that governs every line
below: **do not touch the anti-drift and anti-deviation safeguards in the name of Opus 5.** They catch
*document* defects, not *model-capability* defects — a better model does not fix a ZWSP bug. The same
applies to the gates, the eleven-step structure, gate nomenclature, tracked-change handling and the OOXML
logic.

**Why it runs AFTER the build, not with it.** Doing them together makes attribution impossible: if a grade
moves you cannot tell whether it was the fix or the model configuration.

---

## 2. Platform facts, as at the July 2026 Anthropic documentation

**Re-check these against the current documentation before the first branch opens** — they are the oldest
input in this document.

| fact | consequence for this skill |
|---|---|
| **1M context**, both default and maximum | the skill's peak load is **6.4% of the window** — context is not a constraint |
| **128k max output** | never approached; batches are capped at 35 paragraphs for an unrelated reason |
| **Thinking on by default**, with a breaking change to when it can be disabled | the thinking-level ladder is a *host* setting, not something a skill can set |
| **A new per-request `effort` parameter** | assessed below and probably not worth exposing per step |
| **Cacheable prompt minimum drops 1,024 → 512 tokens** | relevant to lexicon caching, which is 53.6% of the peak load |
| Default responses run longer than prior Opus models | consistent with the measured 18–50 minute runtime |

Anthropic claims quality holds across the full 1M window. **Treat that as a vendor claim, not as proven.**

---

## 3. What is already closed, on evidence

**The 35-paragraph batch cap STAYS.** Twelve runs, and every operator reported that context was never the
binding constraint and attention was. On the largest document the cap caught a real slip that the harness's
own checkpoints had passed as compliant. **It is an ATTENTION cap, not a context cap** — so a bigger context
window is not an argument for raising it. Evidence-based closure; do not re-open it under Opus 5.

**The no-sub-agents rule STAYS.** Each sub-agent would have to load the relevant lexicons and step docs
itself — bad for context and for token economics — and on the previous model sub-agents did not reliably
respect either the batch cap or the per-sector lexicon preloading. *If it is ever revisited:* a narrow probe
(three batches in parallel, lexicon passed explicitly, check that the cap and the lexicon terms hold), and
**measure the token cost of duplicating context against the parallelism gain** — the gain probably cancels.

---

## 4. The two branches

**They come after the build's branches, and they are the last code before the verification run.**

### 4.1 `feature/opus5-context-audit`

Simplify **only** the defensive logic that existed for 4.8 *context-window* reasons.

**Do not touch:** the anti-drift safeguards · the gates · the eleven-step structure · gate nomenclature ·
ZWSP handling · tracked-change handling · the OOXML logic.

**The test is the same as for any doc-and-instruction branch:** a graded run plus Wouter's review. There is
no script instrument for an instruction change.

### 4.2 `feature/opus5-effort-and-batch`

Run the thinking-level arms (§6), and consider exposing `effort` per step — high for gates and
terminology-critical steps, lower for mechanical ones.

**Per-step `effort` is probably not worth it, and the reason is measured:** script time is **0–1% of every
run**, so there is almost no mechanical work to economise on, and the attribution cost of a per-step
parameter is high. Recommend against unless the arms in §6 produce a reason.

---

## 5. Step C — the full verification run · autonomous block 2

**This is where the build gets its grade, so its configuration is not a matter of taste.**

1. **Translate all 11 corpus documents** on the **3 US / 8 UK** split, with the **same forensic logging as
   A1**, and grade every one against the frozen v3 baselines.
2. **Reproduce the configuration.** **D01 and D10 must run in a batch**, because their baselines are
   batch-run baselines and a single run against a batch baseline is not like-for-like. D03 has **both** a
   single and a batch baseline, which makes it the most valuable document in the corpus for measuring a fix.
3. **Hold the three instruments constant** — grader v3, harness v2.2, one thinking level. The project has
   been bitten twice by a moving ruler.
4. **Then, and only then, the arms** (§6) and **the reconciliation's re-grade**, which folds in here rather
   than being paid for separately.
5. **Then Wouter reviews all 11 himself — INPUT POINT 2.** The protocol is `CLAUDE.md` §5.12; it is the
   review that already ran once, unchanged.

**The host is still open on purpose.** Decide on evidence when the run is scheduled. Cowork is attractive as
a final check in the environment users actually have, and it is the environment A4 says nothing about.

**One residual non-equivalence no installation can fix: compaction behaviour is host-specific.** Log every
compaction event. *(None occurred in any A1 run.)*

**The grader unfreezes here and not before.** Two v4 candidates are already queued: criterion 4's
invisible-character cap is **presence-based**, so 1 zero-width space and 48 score identically — the same
bluntness v3 fixed for criterion 14; and **`w:rStyle` is absent from criterion 14's checklist.**

---

## 6. The thinking-level experiment — design settled, additive by construction

**Every A1 run used `extra`, one rung below `max`.** The ladder is `low` < `high` < `extra` < `max`. So the
**entire baseline is a lower bound**, with two honest implications:

- Some defects an operator *missed* at `extra` might be caught at `max`, so a subset of the register may be
  **operator-attention findings rather than skill findings**.
- But every **structural** defect — the run-rebuild mechanisms, the token-set gate, the missing audit, the
  instruction contradictions — is a property of the code and the docs. **No amount of thinking makes it go
  away**, and those are the bulk of the register.

**Is thinking level even relevant to a skill this heavily specified? Yes, and the evidence inverts the
intuition.** The specification is *why* judgement is needed, because the specification contradicts itself:
the instruction cluster is now **39 findings** of mandatory rules that cannot both be obeyed or are simply
wrong. An operator that does not stop to check follows the contradictory instruction and ships the defect.
**Every save recorded across the runs was an act of checking something the instructions did not ask to be
checked** — refusing a destructive script on a live redline, reading `styles.xml` and deviating from the
heading-bold rule, converting a comma decimal separator, rendering the output and looking at it. **In every
one of those cases no gate would have caught the error.** So the risk of lowering effort is not slightly
worse prose; it is **silent substantive errors that pass every gate green.**

**The design — additive, so it cannot destroy the never-regress comparison:**

1. **All 11 of Step C run at `extra`, unchanged.** That is the fix-verification comparison and it must stay
   one configuration.
2. **Then re-run ONE document at `max` and ONE at `low`**, as separate measurements. Because that document
   has an A2 baseline *and* a Step C run both at `extra`, this yields a three-point read with the skill held
   constant: **pre-fix/extra → post-fix/extra → post-fix/other.**
3. **Use D09 for both arms.** It is short, it has an existing baseline, and it contains **at least four
   discrete judgement calls with known-correct answers that no gate would catch**: the decimal separator,
   the heading-bold deviation, the first-*formatted*-fragment placement, and the footnote-anchor detection
   and repair. **Avoid D11** — its non-Latin appendix was reverse-engineered from that very document, so its
   provenance is contaminated.
4. **Score the arms on the JUDGEMENT CALLS, not on the grade.** Quality and terminology already score 9
   everywhere and the translation criterion is graded on a *sample*, so a `low` run could plausibly return
   8.5 while having silently shipped two substantive errors. The readout is *"how many of the four
   known-answer calls did it get right, and did it render the output and look at it?"*

**A third arm runs beside them: the prose-reachability probe.** Its full design is
`STEP-B-ANALYSIS.md` §4.1. In one paragraph: one variable — **the mandatory step-file reads are suppressed**,
headings only — everything else held, scored on the same four known-answer calls. It measures not *whether*
the prose reaches the agent (the register already shows it does) but **how much**. **It can CONFIRM and it
cannot REFUTE:** at n=1 a small effect is indistinguishable from none. And it carries a contamination the
design cannot remove — the operator must be *told* to suppress its reads, so it knows it is in an arm. The
thinking-level arms have the identical problem. **Label it; do not pretend otherwise.** The deliverable from
the suppressed arm is discarded — it is an experiment, not a translation.

**What the experiment cannot change, and this is worth stating up front.** Whatever it returns, the shipping
recommendation is fixed by asymmetric risk: extra thinking costs the user minutes; insufficient thinking
costs a silent substantive error in a legal document. **So the README and `SKILL.md` will say "run at
maximum thinking" regardless.** The experiment blocks nothing; its value is quantifying *how emphatic* that
instruction needs to be, and whether `max` earns its extra time over `extra`.

**A published skill cannot set its own effort** — a skill is Markdown plus Python, and the thinking level is
a host setting. **The only lever is to tell the user**, in the same place the "minutes, not seconds"
expectation is set. That belongs to the publication step, `CLAUDE.md` §3 step 4.

---

## 7. Definition of done for this workstream

Both branches merged under the ordinary branch rules (`CLAUDE.md` §5.2) · Step C run in full with the
configuration reproduced · **no grade regressed against the frozen v3 baselines** · the two thinking arms
and the reachability arm run and scored on the judgement calls · **Wouter's review of all 11 complete
(INPUT POINT 2)** · and the recommendation on `effort` and on the README's thinking-level instruction
written down here, in this file.
