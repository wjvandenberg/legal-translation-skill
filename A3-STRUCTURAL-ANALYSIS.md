# A3 — Structural analysis

> **Phase 2, strand A3. The last strand of Step A.** Produces no code. This document is the input to
> **Step B**, alongside `FINDINGS-REGISTER.md`.
>
> **Date:** 2026-07-31. **Run at:** Opus 5, `max` thinking, in Claude Code.
> **Subject, fixed in advance by the charter:** the eleven structural observations in charter §4; the
> context-cost inventory; Wouter's hypothesis (observation 10) tested against graded evidence rather
> than reasoning; and — the one question A3 had to answer explicitly — **whether the extraction output
> format is the keystone.**
>
> **What A3 does NOT do.** It does not choose fixes and it does not draft the branch list. Choosing is
> Step B, with Wouter. A3 maps the ground and prices the options.

## How to read the evidence markers

Every factual claim below carries one of four markers, because the audit gate requires measured and
inferred to be distinguishable at a glance:

| marker | means |
|---|---|
| **[M]** | **Measured** in this session by a script over the rev44 trees, or read directly out of the cited file. Re-derivable; the scripts are in `temp/`. |
| **[C]** | **Cited** from `FINDINGS-REGISTER.md` or a changelog, and then checked against the file it cites. |
| **[I]** | **Inferred** — a reading of measured facts that could be wrong. Every keystone claim of the "this causes that" kind is marked here unless a controlled measurement isolates it. |
| **[P]** | **Prediction** — not observed on any document. Recorded so it is not mistaken for evidence. |

**Naming.** This document calls its six structural keystones **KS1–KS6**, deliberately *not* K1–K6,
because the register already has a cluster **K** whose findings are called K1 and K2. Wherever `K1`/`K2`
appear below without the `S`, they are the register's rows, not keystones.

**Two trees, two numbers.** Where UK and US differ, both are given. Charter §4's file-size block turns
out to describe the **US** tree **[M]** — see §5, observation 0.

---

## What the cluster letters mean — in plain English

*Added at Wouter's request, 2026-07-31. These letters have been used throughout the project and never
defined in ordinary language. A compact version now also sits in the register's own "How to read this".*

**A "cluster" is a group of findings that share one ROOT CAUSE** — not one symptom, not one document. The
whole point of the letters is that one structural fix may close several findings that look unrelated on
the page. The letter is a label for the cause; the number just distinguishes the findings within it.

**First, two pieces of vocabulary the letters keep depending on.** A **run** is a stretch of text inside a
Word paragraph that shares one set of formatting — change to bold halfway through a sentence and Word
splits it into two runs. **OOXML** is the XML format inside a `.docx`; a `.docx` is a zip file of XML
parts, and `word/document.xml` is the main one.

| letter | short name | what it actually means |
|---|---|---|
| **A** | run rebuild | When the skill puts the English back, it **rebuilds each paragraph's runs from scratch** and loses whatever the new runs cannot carry. **Two halves:** things *deleted* (footnote and comment markers, tab characters, hyperlinks) and formatting the skill has **no way to describe** (underline, highlight, small capitals, character styles). |
| **B** | `post_process` | A **mandatory clean-up script** that runs at the very end and **edits correct English into something else** — stripping italics the drafter chose, inserting page breaks the source never had, rewriting a statutory citation. |
| **C** | blind gates | The **automatic checks pass documents that are broken**, because of *what they compare*. The master case: the strictest check compares **sets of words**, so it cannot see order, punctuation, or a word deleted where the same word occurs elsewhere. |
| **D** | layout | **English is ~30% longer than the source**, and the devices that position text on a page — tab characters, padding spaces, runs of blank paragraphs — do not stretch with it. Preserving *how many* there are does not preserve *what they do*. |
| **E** | lexicon scoping | The dictionaries are organised **by legal domain × language**, so the right entry is often **not in a file the operator was told to read** — or, for document *furniture* like the "Signed at …, [date]" line, **does not exist anywhere**. |
| **F** | instruction contradictions | **Rules inside the skill that contradict each other, or are simply wrong**, so obeying one breaks another. The largest cluster. Three of them are *closed loops*: mandatory requirements that cannot be met at all. |
| **G** | false positives | **Checks that cry wolf.** Nine warnings, nine false, zero real findings on one document — which trains the operator to skim the one block that would show a genuine problem. |
| **H** | source == target | An **already-English document** fed to an English-output pipeline. Nothing in the skill notices, and three quality checks go inert while reporting PASS. |
| **J** | ZWSP leakage | A **zero-width space** — an invisible character the operator uses as a legitimate workaround — **survives into the delivered file**, where it can make a defined term unsearchable. |
| **K** | gate scope | **Nothing tells the operator that a check can be wrong about what it is checking**, and the skill's language actively discourages that conclusion. Cultural, not technical, and it is what makes every other scoping defect expensive. |
| **L** | definitions detection | The code that finds the **definitions clause guesses**, gets it wrong, and says nothing. Four documented misses, the fourth in a delivered client document. |
| **S** | language guessing | Scripts that need to know the **source language guess it, guess wrong, and still print CLEAN**. Four scripts, three different wrong answers, on one document. |
| **T** | batch behaviour | **What degrades when several documents run in one session.** The finding is that translation quality does *not* degrade — the *policing* of the pipeline does. |

**And the prefixes that are not clusters, because this is where the letters get genuinely confusing:**

| prefix | what it is |
|---|---|
| **P1–P26** | **Positives to preserve.** Things the skill does *right* that a fix must not break. |
| **I-1 … I-11** | **Measurement-instrument defects** — bugs in *our own* harness, grader and review tooling, not in the skill. Deliberately kept in a separate table so they can never contaminate a skill finding. *(They were called `H-n` until 2026-07-30, when they were renamed to stop colliding with cluster H.)* |
| **M1, N1, O1, Q1, R1, U1, V1, W1, W2** | **Single-instance findings** — one letter each, no cluster, because they share a root cause with nothing else. |
| **D01–D11, D03B** | **DOCUMENTS**, not findings. **This is the one real trap:** `D1`–`D6` are cluster-D *findings* and `D01`–`D11` are the eleven *corpus documents*. The register's own validator excludes the letter `D` from its cross-reference check for exactly this reason. **Two digits means a document; one digit means a finding.** |
| **CRITICAL / HIGH / MED / LOW / POS** | severity — CRITICAL means content lost or corrupted, HIGH means a visible defect. |

**Why there is no cluster I:** `I-n` was already taken by the instrument defects. **Why the letters jump
from D to E to F to G to H to J:** `I` is skipped for that reason and the rest were simply allocated in
the order the causes were discovered, not alphabetically — **the letters carry no ordering and no
priority.** `A` is first only because it was found first, though it does happen to be the largest.

---

## 0. Summary — the eleven conclusions

1. **The keystone question has a split answer, and the split is clean.** The extraction/apply data
   contract is the keystone for the **formatting** half of cluster A and for three F-cluster rows —
   but it is the cause of **none** of cluster A's content losses, which are where every CRITICAL row
   sits. Cluster A is two independent failures wearing one letter. **§1.**
2. **The register's own indicative branch 2, as scoped, would make A18 worse — measurably so.**
   "Carry a whitelist of incidental run properties from the matched source run" keeps the
   one-template-per-paragraph architecture, and A18 shows that a richer template *spreads* the deviant
   run's properties across the whole paragraph. **§1.3.** This is the sharpest single result of A3.
3. **Six structural keystones, not four.** The review's four are confirmed; A3 adds two — apply's
   structural contract, and `post_process`'s authority to overwrite faithful output. **§2.**
4. **One sequencing fact is not a preference: the gate substrate (KS3) is the instrument by which every
   other fix is judged.** CLAUDE.md's never-regress rule is unenforceable today, and KS1 and KS2 both
   change formatting in ways only a rendered/XML comparison can police. **§2.7.**
5. **Context is not a constraint under Opus 5, and the file-size work should be re-motivated.** The
   skill-side peak at Step 4 is **~64,500 tokens at the heaviest lexicon load A1 actually observed —
   6.4% of the 1M window** — and **~83,000 (8.3%)** on a profile heavier than anything A1 saw **[M]**. Charter observations 1 and 2 are
   correct as measurements and wrong as *context* arguments. **§3.**
6. **The install-truncation work has been measured against the wrong number for fourteen revisions.**
   The only cut position ever *observed* is **byte 55,466** (rev27, on `apply_translations_textmatch.py`).
   Every size check since rev30 has compared against **126,865**, recorded as "previously reported".
   **Three files in each tree are past the observed cut today**, including `SKILL.md` **[M]**. **§3.3.**
7. **Wouter's hypothesis is directionally right and currently false.** `SKILL.md` genuinely is
   variant-bearing; the scripts should not be, and today **they are — in executable logic, not
   comments**, with the **default (UK) tree carrying the degraded half** **[M]**. Convergence is not a
   mechanical merge: the two `references/general-legal.md` files carry **different substantive advice**,
   not mirrored advice. **§4.**
8. **A cross-cluster coupling nobody has recorded: cluster L's brittle detector silently disables the
   pipeline's only formatting gate.** `validate_en_runs.py` returns PASS whenever
   `find_definitions_section_in_texts` returns nothing, and cluster L documents four false negatives of
   that detector **[M]**. One detector, two consumers, both silent on failure. **§6; now register row L6.**
9. **The runtime complaint is right, and the cause is structural.** Re-derived from the twelve logs:
   **`minutes = 24.6 + 0.040 × paragraphs`** — about **25 minutes of fixed overhead and 2.4 seconds a
   paragraph**. The largest corpus document has **26× the paragraphs of the smallest and took 2.4× the
   time**. Translating is **43%** of the time; the pipeline around it is 57%, and on a 24-paragraph
   document **96%** of the run is fixed cost. **The skill has one gear. [M] §3.4.**
10. **The over-engineering is in capabilities, not in files.** No dead scripts, no orphan lexicons, and
   only 4% duplicated prose — but **four independent language detectors that gave three different wrong
   answers on one document, four remnant scanners, three bold/italic readers and two spelling tables that
   have drifted apart**. Every disagreement between copies is already logged as a defect. **There is no
   shared library — and the one capability with a single implementation is the one whose master defect is
   a one-place fix. [M] §3.5.**
11. **The register reorganisation is done and proved, the six new findings are written in, and the split
   is refused with reasons.** The move kept all 166 rows byte-identical and cleared the validator's
   standing warning; a second, unrecorded defect was found in the same pass — **eleven rows were not
   rendering as table rows at all**. The register now holds **172 rows / 135 skill findings**, validator
   **PASS, 0 failures, 0 warnings**, and a **deep audit of 94 independent re-derivations, 0 failures**.
   **§7, §8, §9.2.**

---

## 1. THE KEYSTONE QUESTION, ANSWERED

> *"Is the extraction output format the keystone? If `en_runs` is the binding constraint behind A12,
> A17, A18, C20 and half of cluster A, then Step B's indicative branch order is wrong and should open
> with extraction rather than the run-child whitelist."*

### 1.1 The answer

**For A12, A17, A18, C20 — yes, and more strongly than the question assumes.** They are not four rows
that happen to share a cause; they are four descriptions of one missing thing, and fixing extraction
also closes three instruction rows (F7, F13, F22) and removes 8 KB from the heaviest step doc.

**For "half of cluster A" — no.** The half it does not reach is the half that loses content, and that
is where every CRITICAL row sits.

**So the honest answer is that cluster A is two independent failures wearing one letter** **[M]**:

| | rows | what fails | where the fix lives | worst severity |
|---|---|---|---|---|
| **A-content** (7) | A1 A2 A3 A6 A8 A9 A16 (+N1, C19) | apply **deletes** structure it should keep, or never reaches it | `apply_translations_textmatch.py`'s child-classification loop; `repack_docx.py`'s part list | **CRITICAL** — a lost footnote, 14 unreachable comments, source-language text on page one |
| **A-format** (10) | A4 A5 A7 A10 A11 A12 A13 A14 A17 A18 (+C20, O1, E12b) | the pipeline **cannot represent** the formatting, so it cannot preserve it | `extract_paragraphs.py`'s output format and apply's rebuild | **HIGH** — appearance, plus one semantic case (A18's *spread*) |
| **A-exception** (1) | A15 | no compliant lever existed to repair another pass's damage | the exception channel, not the code | HIGH |

Fixing one closes none of the other's rows **[M]**. They are not sequenced; they are disjoint.

**One reclassification, made during the audit and worth flagging because it dates the mechanism.** A5 —
*"English prose landing in a `Symbol`-font run renders as Greek glyphs"*, from the June post-mortem — is
filed by the charter alongside A6's glued bullets as "re-concentration into one run". A6 is that; **A5 is
not.** English lands in a Symbol-font run because the rebuild copies `get_default_rpr_et()`'s template
onto every new run, and the template is the first run with an explicit `rPr`. **A5 is A18's mechanism with
`rFonts` as the property — the earliest recorded instance of it, two months before A18 was identified from
D02's highlight and D06's small capitals** **[I — reasoned from the code path; A5 is not reproducible from
the corpus and needs the synthetic fixture branch 2 already plans]**. Three properties, three documents,
one selection rule.

### 1.2 What `en_runs` actually is — measured at both ends

The register describes `en_runs` as carrying "bold/italic only". That is exact, and A3 can now state it
at the line, in both directions:

**At the producing end** — `extract_paragraphs.py` **[M]**:

- It emits, per source run: `start`, `end`, `text`, `bold`, `italic`, and *conditionally* `underline`,
  `font`, `sz`, `color`.
- It reads **no** `w:rStyle`, **no** `w:highlight`, **no** `w:smallCaps`, **no** `w:vertAlign`, **no**
  `w:shd`, **no** `w:strike` — verified by absence of the strings from the whole file **[M]**.
- It resolves **no style cascade**. `has_prop(rpr, 'b')` reads the run's own `rPr`; when that is absent
  it falls back to the **paragraph mark's** `rPr` — never the `pStyle` chain, never `docDefaults`.
- The doc says so itself, in the middle of rule 3 of `04-translate.md`: *"the extract reads run-level
  only and cannot distinguish 'silent' from 'explicitly false'"* **[M]**.

**At the consuming end** — `apply_translations_textmatch.py` **[M]**:

- The rebuild loop reads exactly four keys from an `en_runs` span: `start`, `end`, `bold`, `italic`.
  Nothing else is looked at, anywhere.
- On a tracked-change paragraph, `en_runs` is read for **one boolean** and nothing else — whether any
  span has `bold: true`, which sets `skip_bold_override`. *(This refines **A10**, which says `en_runs`
  is "computed, declared, validated and then ignored" on TC paragraphs: it is not wholly inert, it has
  exactly one effect, and that effect is to suppress a defect rather than to place formatting.)* **[M]**
- The rebuild takes its `rPr` template from `get_default_rpr_et()`, which — exactly as **A18** says —
  returns the first text-bearing run **that has an explicit `rPr`**, because the `if rpr is not None`
  test sits *inside* the loop. Its own docstring says "first text-bearing run" **[M]**.

**So the format is asymmetric.** The source-side description is richer than the instruction channel:
extraction *reports* underline, font, size and colour, and there is no way to ask for any of them back.
That asymmetry is why A12's list of "no vocabulary for" reads oddly against the code — the vocabulary
exists on the way in and dies on the way out.

**And the most damaging behaviour in cluster A is a deliberate compensation for that blindness, with a
code comment saying so.** `make_run_et()` always emits `<w:b w:val="0"/>` (and `bCs`, `i`, `iCs`) when
`bold=False`, and the comment reads **[M]**:

> *"We MUST emit the explicit off-override rather than simply omitting `<w:b>`, because paragraph styles
> can inherit bold from `basedOn` parents … If we omit `<w:b>` in that case, the style's inherited bold
> shows through and the entire body renders bold."*

That is the author choosing to **defeat the style cascade at apply time because extraction cannot
resolve it** **[I — the causal reading; the comment is measured, the "because" is my inference from the
absence of any cascade resolution upstream]**. It is what produced D06's `b=0` runs **0 → 694** and
`i=0` **1 → 680** (**A12** **[C]**). It is not a bug to be patched out; remove the off-flags without
computing effective formatting and D06's body renders entirely bold instead.

### 1.3 Why the register's indicative branch 2, as scoped, would make A18 worse

This is the load-bearing consequence and it changes Step B's shape.

`Roadmap → Phase 3 → branch 2` reads: *"carry a whitelist of incidental run properties from the matched
source run and merge with the `en_runs` bold/italic."*

**But there is no "matched source run".** Apply does not know which source run any English span came
from. It has one paragraph-level template, chosen by `get_default_rpr_et()`, and it deep-copies that
template onto **every** rebuilt run **[M]**. So "carry a whitelist of properties" can only mean "let
more of the template's properties survive the copy" — and A18 measured what that does **[C]**:

- D02: a six-run heading, only the **last** run highlighted, first five carrying no `rPr` at all. The
  template is therefore the highlighted run. Delivered: **one run, entirely highlighted** — a spread.
- D06: `smallCaps` on the party names only. Delivered: party names **and** capacity phrases. Runs
  **14 → 14**, characters **276 → 245** — a count check sees nothing and a character check reports a
  *loss*, while the text shows a *spread*.

**A wider whitelist makes both of those worse, not better**, because it widens what the deviant run
donates to the paragraph **[I — a direct reading of the copy-template mechanism; not measured on a
modified build]**. Today `highlight` and `smallCaps` already ride along on the template; the same
mechanism would then carry `u`, `strike`, `color`, `rFonts`, `vertAlign` and `rStyle` too.

**The only formulation of branch 2 that is safe is per-span property carry-over, and that requires
knowing which source run each English span corresponds to.** Which is the extraction-side computation.
So branch 2 and branch 3 (`span-precise-bold`) are not two branches; they are one, and its precondition
is KS1.

### 1.4 Verdict on the indicative branch order

The indicative order in `Roadmap → Phase 3` is **wrong in three specific respects**, and right about
its first item:

1. **Branch 1 (`run-child-preservation`) is correctly first on severity.** It carries the CRITICAL
   content losses and it is the cheapest high-severity work in the project — contained to one file, no
   schema change, byte-comparable on fixtures. Nothing in A3 argues against it.
2. **Branches 2 and 3 should not exist as separate branches.** They are one change to one data contract,
   and branch 2's stated scope would regress A18. **§1.3.**
3. **Branch 5 (`gate-honesty`, containing C18) is fifth and is a precondition.** It is the only proposed
   work that produces the never-regress instrument the other branches are judged by. **§2.7.**
4. **The register's cluster-A framing — "one fix closes them: carry a whitelist of properties *and*
   children from the matched source run" — should be retired.** It is the sentence that produced the
   mis-scoping. Two fixes, two mechanisms, two files.

**The question as posed offered a choice between opening with extraction and opening with the
whitelist. The measured answer is that they are disjoint and can proceed in parallel** — and if a single
opener must be chosen, severity chooses the whitelist, while *verifiability* chooses the gate.

---

## 2. The six keystones, as alternatives with costs

Wouter, 2026-07-31: *"I would not want to limit myself to small fixes only … I would like to really take
a leap."* These are presented as genuine alternatives, priced. **Four are the review's; two are A3's
additions and are marked.**

### KS1 — The pipeline represents form as *counts and flags*, never as *effects*

**What it is.** There is no model of correspondence between a source run and an English span, and no
computed notion of what a run actually renders as. What exists instead: a flat source string, a flat run
list whose offsets index a *slightly different* string, a flat English string, and an optional span list
carrying two booleans. Everything above that — the template `rPr`, the explicit off-flags, rule 3's 121
lines, A18's selection heuristic, A11's hardcoded override — is improvisation around the gap.

**The same principle has a second face, and naming it is what earns KS1 its scope.** The pipeline
preserves layout *devices* by count and loses their *effect*: tab characters (D1/A3), full-width padding
(D4 — 11 ideographic spaces became 11 ASCII spaces, ~2.75 em where 11 em was intended), empty-paragraph
page breaks (D5 — preserved exactly, rendered inert), `w:br` position (D2). The grader learned the same
lesson independently and it is the register's most-repeated rule: *never score a run property from
element counts — compare the text, then render.* **Cluster D and cluster A's formatting half are the same
error in two dimensions** **[I]**.

**And it has a third face nobody has connected.** `paragraphs.json` cannot say what a paragraph *is*.
That is why `reorder_definitions.py` has to guess where the definitions section is — the register says it
plainly: *"detection only exists because the pipeline throws away something it already knew."* Cluster L
is a data-contract row, not a heuristics row **[I]**.

**What it closes or enables:** A4, **A5**, A7, A10, A11, A12, A13, A14, A17, A18, C13, C20, O1, E12(b),
L2, L3, plus instruction rows **F7, F13, F19, F22** — and the layout face of D1, D2, D4, D5.

**What it costs.**
- `extract_paragraphs.py` gains a capability it has never had: reading `styles.xml` to resolve the
  `pStyle` → `basedOn` chain, `docDefaults`, `w:rStyle`, and (for table paragraphs) table styles. This
  is genuinely fiddly OOXML.
- `apply_translations_textmatch.py`'s rebuild path is replaced, not amended: per-span property
  derivation instead of one deep-copied template.
- The JSON schema changes, which invalidates every worked example in the step docs and every archived
  `paragraphs.json`.
- Rule 3 of `04-translate.md` — **8,028 bytes, 121 lines, 16.8% of the heaviest step doc, three times
  the size of rules 4–14 combined** **[M]** — collapses. That is a benefit, but rewriting it is work.
- `validate_en_runs.py` needs re-purposing (it currently gates *presence*, not *agreement*).

**What it risks.** A computed-formatting emitter that gets the cascade **wrong** is worse than today's
honest guess, because the operator will stop checking. The current design at least forces rule 3's
explicit reasoning. Mitigation is a per-document assertion that computed effective bold/italic matches
the *rendered* source — which is a KS3 instrument.

**What it does NOT close.** Every content-loss row. Every gate row. Every lexicon row.

**Confidence.** That A12/A17/A18/C20 share this cause: **measured** — verified at the line in both
scripts. That fixing it closes them: **inferred** — no modified build has been run.

### KS2 — Apply's structural contract *(A3 addition, not one of the review's four)*

**What it is.** Apply classifies each direct child of a paragraph into keep / rebuild / delete, and the
classification is wrong in four separable ways **[M]**:

- `_run_should_be_preserved()` is a **seven-item whitelist** — `w:br type="page"`, `drawing`, `pict`,
  `fldChar`, `instrText`, `lastRenderedPageBreak`, `tab`. Anything else in a structural-only run is
  deleted (**A-i**).
- `_run_is_text_bearing()` is tested **first**, so a run carrying text *and* a whitelisted child loses
  the child (**A-ii**).
- `w:hyperlink` is deleted wholesale before the whitelist is reached (**A-iii**).
- Two container types are read by extraction (`p.iter()` is recursive) and never written by apply, whose
  loop handles only `w:hyperlink` and `w:r` as direct children: **`w:sdt` and `w:smartTag`** (A16, N1).
  And `repack_docx.py` carries no route for `word/glossary/document.xml` (C19).

**Why it is a keystone and not a bug list.** All four are instances of one decision: *the paragraph is a
list of runs and everything that is not a run is either whitelisted or noise.* OOXML says otherwise —
runs nest inside wrappers, wrappers nest inside content controls, and references are structural-only runs
that carry meaning. **The contract needs inverting: preserve by default, rebuild only what you can
account for.**

**What it closes:** A1, A2, A3, A6, A8, A9, A16, N1, C19, C17, C16, F27, F16.
**Cost:** one file (plus a repack flag). No schema change. Byte-comparable on synthetic fixtures.
**Risk:** low, and it is the only candidate where that is true.
**Does NOT close:** anything in A-format.
**Confidence:** the mechanisms are **measured in code**; the closure claim is **cited** (the register's
three-mechanism decomposition, verified here line by line).

### KS3 — The gate substrate: everything is checked against the JSON, not against the deliverable

**What it is.** Every gate reads either `paragraphs.json` (so it cannot see what apply and `post_process`
did) or word tokens (so it cannot see order, punctuation, whitespace or formatting). `validate_apply
--strict` compares **token sets** — not sequences, not multisets — and polices only *missing* tokens,
never *extra* ones (C1). `quality_check.py` has no `sys.exit` for the issues case (C3). Hard Rule 3
describes a coverage gate that does not exist — **verified: zero occurrences of any coverage check in
`apply_translations_textmatch.py`** (C5) **[M]**.

**The proposal already exists and it is the operator's**: C18 — reconstruct the accept-all and reject-all
views **from the final `document.xml`** and diff them against the declared translations; extend with an
aux-part **content** diff and a source-language sweep over **every** part.

**What it closes or detects:** the 13 gate-substrate C-rows, all 9 of G, all 3 of S, L1/L4, E4, J1 and M1 —
and, just as importantly, it is the *detector* for A1, A2, A15, B1, B3, B7, C17, C19, which today are
caught only when an operator renders the page and looks.

**Cost:** one new script plus wiring; no change to the data model; no change to translation behaviour.
**Risk:** low. The one real risk is scope creep into a second grader.
**Its distinct property, and the reason it is not merely fifth in a list:** every other candidate fixes
what we already found. **KS3 changes what the project can find next time**, and it is the only route to
the scripted never-regress gate CLAUDE.md requires and cannot currently enforce.

### KS4 — The lexicon layer has no dimension for document apparatus

**What it is.** The lexicons are organised as *legal domain × language*. Document furniture — the title
block, the place-and-date execution line, the attestation, signature-block labels, section symbols,
numbering words, cross-reference conventions, editorial notices — belongs to **neither** axis, so no
amount of domain scoping reaches it. E7's measurement is the proof: sweeping all 15 references and all
154 sub-lexicons for the dating label and its ten siblings returns **zero hits in every language**, and
`Done at` appears **nowhere in the 198-file tree** — **re-verified here [M]**.

**Two further measurements sharpen it.**
- The skill's **richest store of furniture vocabulary is locked inside a script**: `translate_headers_footers.py`
  carries **221 phrase entries across NINE language maps** (Hungarian 43, Italian 25, French 23, German 21,
  Spanish 22, Portuguese 22, Dutch 22, Polish 22, Finnish 21) **[M]**. *(**Correction to F31c**, which says
  eight languages. It is nine. The 221 total is exactly right.)* The map's own comment scopes it to
  headers, so a body translator never reads it — a *de facto* thirteenth lexicon domain in `scripts/`.
- The section symbol returns **zero hits across `SKILL.md` and all eight step docs** — re-verified
  here **[M]** (E8).

**What it closes:** E7–E12, F17 (numeric locale is the same class: a universal convention with no home),
F31, F33, and the E1/E2/E3/E6 coverage half if a term→file index is built.
**Cost:** content authoring, not code — the one candidate that cannot be closed by structure alone. Plus
one genuine structural decision: **does furniture become a third axis (a `furniture` reference file), or a
section inside `general-legal.md`, or a promoted lexicon built from the script map?**
**Risk:** the failure mode is writing it as a list of strings. E7 already proved a flat row cannot express
a place marked by a case ending, and E9 already proved the rule must be about a *class* of text.
**Its distinct property:** it is the only candidate that touches criteria 1 and 2 — which already score 9
everywhere — from the direction Wouter's review says actually matters.

### KS5 — The instruction substrate: no single authority, no conflict rule, no sanctioned exceptions, no declared modes

**What it is.** Four separable gaps that between them own **35 rows** — 23 of the 30 F-rows, all of H and
all of K, plus C5/C7, E5/E10, A15, L5 and R1:

- **No single authority per convention.** E10: statute-citation form is prescribed in three domain
  references that contradict each other while `general-legal.md` is silent. E5: two sub-lexicons in the
  same layer disagree and the priority rule covers only cross-layer conflicts.
- **No conflict-resolution rule.** SKILL.md's lexicon priority resolves sub-lexicon vs reference and
  nothing else.
- **No sanctioned way out.** Three **closed loops** (F28, F30, F33) are mandatory requirements that
  cannot be met. A15 and D3 are the same shape from the architecture side: the golden rule forbids the
  only available repair and there is **no channel for "known consequence, accepted and disclosed"**.
  Cluster K is the cultural half — nothing tells an operator a gate can be wrong *in scope*.
- **No declared modes.** H3 (source == target) and L5 (image-only source) are input *classes* the
  pipeline cannot express. The pipeline has exactly one mode.

**A3 adds one measurement to F23, and it makes the row sharper.** The ground truth is that apply
auto-invokes **five** validators — `validate_en_runs`, `validate_translations`, `validate_segment_shapes`
(TC), `validate_reject_all` (TC), and `validate_apply --strict` post-write **[M]**. SKILL.md's anti-drift
safeguard 3 names four and omits `validate_translations`; SKILL.md's Scripts-reference row names four and
omits `validate_en_runs`; `04b-translate-gates.md` says five. **The step doc is the only one of the three
that is right, and both wrong statements are in the always-loaded file** — while the Pre-step checkpoint
makes naming them from memory a STOP condition **[M]**.

**Cost:** most rows are one-line edits. The *structural* version — one authority per convention, a stated
precedence rule, a sanctioned-exception channel, and declared modes — is a real design decision and the
only part that belongs in a "leap".
**Risk:** the cheap version is nearly free and the expensive version is nearly all judgement. The danger is
doing the cheap version and calling the cluster closed while the three closed loops remain unresolvable.

### KS6 — `post_process`'s authority to overwrite faithful output *(A3 addition, not one of the review's four)*

**What it is.** A **mandatory, non-configurable** rewriting stage that runs **downstream of every content
gate** and upstream of only a token-set check. Eight of its passes are documented as altering faithful text
unasked (B1, B2, B3, B4, B7, B8, plus F29's Annex→Schedule and the terminology-table override at B5/B6).
Two of its rules are tuned to one template family and misfire elsewhere without saying so (B7's skip-list is
Italian style names; F29). No flag disables any of it.

**Why it is a keystone rather than eight bugs.** It is one design decision — *the pipeline imposes house
convention by script* — colliding with one stated principle: *fidelity to the source author's formatting
choices beats cosmetic harmonisation.* D5 and B7 together state it best: **the skill imposes a page break
the source never asked for and fails to preserve the one the source made by hand. It has an opinion about
pagination where it should have none, and none where it should have one.**

**The structural question Step B has to answer is not "which passes to fix" but "should this stage have an
opinion at all, and if so who authorises it".** Three shapes exist: keep it mandatory and fix each pass;
make every opinionated pass advisory (report, do not rewrite) with the operator deciding; or split it into a
mandatory *mechanical* half (spacing, drift) and an optional *stylistic* half.

**Cost:** one file, but a behaviour change on every document, so it must be re-graded.
**Risk:** B1's evidence is the strongest in the register — 38 italic spans destroyed on D05, isolated by
comparing `doc_pre_postprocess.xml` against the deliverable — so this is not a marginal call.
**Note:** the isolation technique that produced that evidence is itself the cheapest possible version of KS3.

### 2.7 How they compose — one fact, not a preference

**KS3 is the instrument by which KS1, KS2 and KS6 are judged.** This is not a ranking argument; it is a
consequence of two measured facts:

1. **The never-regress rule is unenforceable today.** Grading is manual, LLM-driven and non-deterministic;
   P23 measured that two runs of one document differ linguistically in 10 of 24 paragraphs while being
   *mechanically identical*. So an LLM re-grade cannot be the regression instrument.
2. **KS1, KS2 and KS6 all change formatting or structure**, and the register's own repeated lesson is that
   run-property changes are invisible to count-based checks in **both** directions.

Therefore: whichever branch Step B opens with, **the mechanical comparison has to exist before its result
can be believed.** KS3's C18 is that comparison plus a great deal more.

The other composition facts, stated without prescribing an order:

- **KS1 and KS2 are disjoint** — no shared code path, no shared row. They can proceed in parallel.
- **KS1 is a precondition for a safe branch 2/3** (§1.3) and for C20's check.
- **KS1 also closes L2/L3** if the data contract gains a `role`/`definitions_range` field — which is the
  register's own option 2 for cluster L, arrived at from a different direction.
- **KS4 is independent of all of them** and is the only one that needs writing rather than coding.
- **KS6 is independent but must be re-graded**, so it wants KS3 first more than the others do.
- **KS5's cheap half is independent of everything** and includes the cheapest fix in the project
  (cluster K's one paragraph).

### 2.9 The six on one page — yield against cost

*Added after Wouter asked whether this document lets us judge the **most efficient** changes. The first
draft priced each keystone in prose but never put them side by side, so it supported "which is causal"
and not "which is worth doing first". Cost bands are my estimate and are the least reliable column here;
the row counts and the dependencies are measured.*

| | rows closed | cost | risk | what it unblocks | what it leaves untouched |
|---|---|---|---|---|---|
| **KS2** apply's structural contract | **13** — incl. every CRITICAL content loss | **low** — one file, no schema change, byte-comparable on fixtures | **low** | nothing depends on it | all formatting |
| **KS3** gate substrate | **30** | **low-medium** — one new script plus wiring | **low** | **verification for KS1, KS2 and KS6** | nothing it can fix itself |
| **KS5** instruction substrate | **35** | **low per row**, high for the four structural parts (authority, precedence, exceptions, modes) | **low** for the edits; the mode work is a design decision | the mode work unblocks the time problem (§3.4) | all code |
| **KS6** `post_process`'s authority | **8** | **medium** — one file, but behaviour changes on every document | **medium** — needs a full re-grade | nothing | all of A |
| **KS1** form as effects | **25** | **HIGH** — new capability in extraction, apply's rebuild replaced, JSON schema changes, rule 3 rewritten | **HIGH** — a wrong cascade is worse than today's honest guess | a safe branch 2/3; C20's check; cluster L's guessing | all content loss |
| **KS4** furniture dimension | **10** | **medium** — writing, not coding | **low**, but easy to write badly (E7, E9 both show why) | nothing | all code |

**Read the table with three cautions.** (i) *Rows closed* is not value — KS2's 13 rows include the lost
footnote, the fourteen unreachable comments and untranslated source text on page one, while several of
KS5's 35 are one-line wording fixes. (ii) *Cost* is judged from what the change touches, not from an
estimate of effort I have no basis for. (iii) **The only ordering constraint that is a measured fact
rather than a preference is KS3's** — §2.7.

**What the table makes visible that the prose did not:** the two cheapest keystones (KS2, KS3) together
close **43 rows including every CRITICAL one**, need no schema change, and are independently testable —
and the most expensive one (KS1) closes 25 and cannot be verified without KS3 existing first.

### 2.8 The rebuild question — what a rebuild would and would not touch

Because Step B is explicitly open to a rebuild, A3 should say plainly what a rebuild would buy.

**The golden rule is not the problem and should not be on the table.** Original-as-base with text matching
is measured to work: zero style/numbering mismatches across every tested document, and P23 shows the
pipeline's structural behaviour is *deterministic* across two independent runs of one document. Every
failure in this register sits in the **run-level layer beneath** the golden rule, not in the rule.

**The 11-step structure is not the problem either.** F21 shows the *packaging* of steps into eight files is
awkward and F23 shows the taxonomy is inconsistently documented, but no defect in the register is caused by
there being eleven steps.

**What a genuine "leap" would replace is the paragraph data contract** — `runs` / `en_runs` / `text` /
`en` / `en_segments` — with a span model that carries (a) effective computed formatting per source span,
(b) a source-span reference on each English span, and (c) declared roles and ranges. That is KS1 at full
scope. It keeps the golden rule, keeps the 11 steps, keeps every gate, and is the only change in this
document that would let branch 2 be built safely, collapse rule 3, close cluster L's guessing, and make
C20's check possible — all from one change.

**And one honest counter-argument to weigh in Step B:** it invalidates every worked example in the step
docs and every archived artefact, and it is the change most likely to introduce a new class of defect into
a pipeline that currently scores 9 on translation quality. The whole project's discipline says *change one
thing, re-grade, compare*. A full data-contract replacement is the opposite of that.

---

## 3. What the current structure COSTS — context, time, redundancy

### 3.1 Measured

Token figures are **chars ÷ 4**, the conventional estimate; a words × 1.35 cross-check runs 20–25% lower
(e.g. SKILL.md 14,317 vs 10,900). Both are given where the conclusion could turn on it. It does not.

**The tree** **[M]**:

| directory | UK files | UK bytes | US files | US bytes |
|---|---|---|---|---|
| `SKILL.md` | 1 | 57,269 | 1 | 57,532 |
| `skill-docs/` | 8 | 128,106 | 8 | 131,115 |
| `references/` | 15 | 444,766 | 15 | 446,998 |
| `scripts/` | 20 | 518,726 | 20 | 525,629 |
| `sub-lexicons/` | 154 | 2,502,968 | 154 | 2,506,476 |
| **total** | **198** | **3,651,835** | **198** | **3,667,750** |

**Always on** — `SKILL.md`, re-read per document and on every compaction-resume: **57,269 bytes ≈ 14,300
tokens** (UK).

**Per step** — the step doc, read in full on arrival:

| step | file | bytes | ~tokens |
|---|---|---|---|
| 1+2 | `01-setup-and-extract.md` | 10,168 | 2,542 |
| 3+3b | `03-lexicons-and-segments.md` | 14,632 | 3,658 |
| **4** | **`04-translate.md`** | **47,707** | **11,927** |
| 4b+4c+4d | `04b-translate-gates.md` | 7,019 | 1,755 |
| 5 | `05-apply.md` | 5,255 | 1,314 |
| 6+7 | `06-postprocess-and-reorder.md` | 12,814 | 3,204 |
| 8+9 | `08-aux-and-quality.md` | 15,905 | 3,976 |
| 10+11 | `10-repack-and-validate.md` | 14,606 | 3,652 |
| | **all eight** | **128,106** | **32,026** |

**Step 3's lexicon load** — `general-legal.md` plus each applicable domain reference plus the language
sub-lexicons, all *"in full, end-to-end"* (rules 1–3 of Step 3):

| profile | references | sub-lexicons | total | ~tokens |
|---|---|---|---|---|
| light — 1 domain, 4 files | 2 → 40,981 | 2 → 20,900 | 61,881 | 15,470 |
| **typical — 2 domains, 6 files (A1's observed maximum, T5c)** | 3 → 75,825 | 3 → 62,553 | **138,378** | **34,594** |
| heavy — 3 domains, 8 files (beyond anything A1 observed) | 4 → 122,062 | 4 → 90,500 | 212,562 | 53,140 |

**The peak — Step 4, everything nominally live, skill-side only:**

| profile | bytes | ~tokens | share of the 1M window |
|---|---|---|---|
| light | 181,489 | 45,372 | 4.5% |
| **typical** | **257,986** | **64,496** | **6.4%** |
| heavy | 332,170 | 83,042 | 8.3% |

Composition of the typical peak: lexicons **53.6%**, SKILL.md 22.2%, `04-translate.md` 18.5%,
`03-lexicons` 5.7%.

### 3.2 What follows — and it re-motivates the whole file-size strand

**Context is not the constraint.** At the heaviest lexicon load A1 observed the skill occupies **6.4%** of
the Opus 5 window before a single paragraph of document text — **8.3%** on a heavier profile than any A1
run, and roughly a quarter less on the lower token estimate. Charter
observations 1 and 2 are correct as measurements — SKILL.md *is* 57 KB and always-on, `04-translate.md`
*is* the second-largest thing loaded at the worst moment — but **as context arguments they are answered.**
Twelve A1 runs said the same thing from the other side: every operator reported context was never the
binding constraint and attention was (P4, P18, T3).

**So the file-size work should not be motivated by tokens. It has two other motivations and both are
real:**

1. **Attention and findability.** F23's three-way contradiction, F31's two devices documented where nobody
   looks, and rule 3's 121 lines are not context problems; they are *retrieval* problems inside a document
   the operator has genuinely read. The Common-Pitfalls catalogue is **18,574 bytes — 32.4% of SKILL.md**
   **[M]**, 17 sub-sections deep, and it is the natural place to look for a structural answer.
2. **Install truncation.** §3.3.

**And one thing the inventory settles negatively: do not cut the lexicons.** They are 53.6% of the peak and
therefore the only place a real cut could come from — and P5, P17 and T5(c) all measured that full-lexicon
reads pay for themselves, including the third read of the file the operator was most tempted to skip.
CLAUDE.md already states the rule; the inventory now gives it a number to defend.

### 3.3 The install cap — verified, and the number the project has been using is the wrong one

**Charter goal (iv) asks A3 to verify the ~126,865-byte figure. It does not hold up, and the real story is
more useful.** **[M]**

- **`126,865` is not an observation.** It enters at rev30 and is thereafter always described as *"the
  previously reported install-truncation point"*. Every size check from rev33 to rev39 compares against it
  and reports comfort.
- **`55,466` IS an observation.** The rev27 changelog: *"The install pipeline was observed cutting at byte
  55,466"* on `apply_translations_textmatch.py`, at *"content-deterministic byte positions"*. rev27 trimmed
  that file from 65,915 to ~57.4 KB; **rev29 exists solely to bring it back below 55 KB, and got it to
  54,617.**
- **`extract_paragraphs.py` still carries a comment recording a truncation position inside itself** —
  *"var renamed pattern_re to shift content past the byte position where install pipeline was observed
  truncating extract_paragraphs.py"* — and that file is only **27,154 bytes UK / 27,153 US** **[M]**. So the phenomenon was
  observed on at least two files at very different sizes, which is consistent with rev27's
  "content-deterministic" wording and **inconsistent with a simple byte cap** **[I]**.

**Measured against each threshold today:**

| threshold | UK files over | US files over |
|---|---|---|
| 126,865 (the figure in use) | **0** | **0** |
| 55,466 (the only observed cut) | **3** | **3** |

| file | UK | US | over the observed cut by |
|---|---|---|---|
| `scripts/apply_translations_textmatch.py` | 58,714 | 58,713 | +3,248 / +3,247 |
| `SKILL.md` | 57,269 | 57,532 | +1,803 / +2,066 |
| `scripts/post_process.py` | 56,188 | 60,271 | +722 / +4,805 |

**`apply_translations_textmatch.py` is 4,097 bytes larger than the size rev29 trimmed it to for exactly this
reason.** The discipline was real, it worked, and it was silently abandoned when the comparison switched to
the larger number.

**Detection coverage, measured [M]:**

| class | files | with integrity sentinel | unprotected |
|---|---|---|---|
| `SKILL.md` | 1 | 0 | **1** |
| `skill-docs/` | 8 | 1 | 7 |
| `references/` | 15 | 0 | 15 |
| `scripts/` | 20 | **20** | 0 |
| `sub-lexicons/` | 154 | 0 | 154 |
| **total** | **198** | **21** | **177 (89.4% of files, 85.4% of bytes)** |

So the charter's framing — *"only the 20 Python scripts have integrity checks; a truncated lexicon or step
doc is invisible"* — is confirmed and can now be stated exactly. **The single sharpest way to put goal (iv):
`SKILL.md` carries the five Hard Rules, is loaded on every document and every compaction-resume, sits 1,803
bytes past the only truncation position ever observed, and has no integrity check at all.**

*(Anti-drift safeguard 6 in SKILL.md says "Every script in the skill carries the integrity check". That is
true — 20 of 20 **[M]**. Of the **178 non-scripts, 177 are unprotected** — the single exception is
`skill-docs/08-aux-and-quality.md`, which carries a sentinel for reasons nothing in the tree explains — and
nothing anywhere says so.)*

**What A3 concludes for goal (iv), without choosing the fix:** the detection mechanism did not "degrade" —
it was rolled out to every script at rev36 and truncation-tested at 50/75/90/99%. What degraded is the
**size discipline** (measured against the wrong threshold) and what was never built is **coverage of the
85% of the tree that carries the translation knowledge**. Those are two different pieces of work.

### 3.4 Where the time goes — 25 minutes of ceremony and 2.4 seconds a paragraph

*Added after Wouter's question: "anything over 20 minutes is actually really, really long for a
translation." The first draft quoted the 18–50 minute range as a fact about the skill and never asked
where it went. It is answerable from the A1 logs, so here it is answered.*

**Method, and a correction to my own first attempt.** `temp/a3_timing.py` reads the twelve raw `.jsonl`
logs and re-derives the per-step timings, rather than copying the analyser's printed tables. My first
version used its own rules and disagreed with the standing instrument on every document; it is now aligned
to `analyse_log.py` exactly — a 300-second interruption threshold, each gap attributed to the step of the
record that **ends** it, and one time basis per log (`epoch` only if every record has it, otherwise `ts`).
**All twelve ACTIVE figures now reproduce the analyser's to the decimal** — which is the cross-check that
makes the decomposition below trustworthy. *(The two errors are recorded at §9.2: forward attribution
under-reported every run by 10–45%, and using `epoch` unconditionally silently dropped 30 of one log's
151 records.)*

**Fixed overhead against document size** **[M]**:

| doc | paragraphs | ACTIVE min | seconds per paragraph |
|---|---|---|---|
| D01 | 24 | 20.6 | 51.6 |
| D11 | 43 | 25.6 | 35.7 |
| D10 | 45 | 17.8 | 23.7 |
| D08 | 57 | 27.6 | 29.0 |
| D09 | 96 | 27.3 | 17.1 |
| D07 | 97 | 35.0 | 21.7 |
| D03 | 98 | 33.1 | 20.3 |
| D03B | 98 | 32.0 | 19.6 |
| D04 | 137 | 33.2 | 14.5 |
| D05 | 241 | 38.8 | 9.7 |
| D02 | 316 | 28.7 | 5.4 |
| D06 | 613 | 49.6 | 4.9 |

**Least squares over all twelve: `minutes = 24.5 + 0.040 × paragraphs`, R² = 0.64** — about **25 minutes
of fixed overhead and 2.4 seconds per paragraph**. *(Refitting from the raw seconds rather than from the
rounded figures in the table above gives 24.6. The difference is far inside the uncertainty of an R²=0.64
fit on twelve points, and the audit caught me quoting the second decimal as though it meant something —
so the number to carry is **"about 25 minutes"**, not 24.5 or 24.6.)* At 24 paragraphs the fixed part is **96%** of the run;
at 613 it is still **50%**.

**And the model-free version, which needs no regression and cannot be argued with: the largest document in
the corpus has 26× the paragraphs of the smallest and took 2.4× the time.** 24 paragraphs → 20.6 minutes;
613 paragraphs → 49.6 minutes.

**Where the 369 aggregate minutes go** **[M]** — twelve runs, per step:

| group | minutes | share |
|---|---|---|
| **TRANSLATION** — lexicons, TC scaffold, translate, cross-refs | 157.6 | **42.7%** |
| APPLY + REWRITE — apply, post-process, reorder, repack | 68.6 | 18.6% |
| SETUP + EXTRACT + AUX | 68.4 | 18.5% |
| FINAL VALIDATE / RENDER | 39.1 | 10.6% |
| GATES — per-batch, lexicon compliance, quality, diligence | 35.7 | 9.7% |

Largest single steps: `04-translate` **32.9%**, `11-validate` 10.6%, `05-apply` 10.2%, `02-extract` 6.8%,
`03-lexicons` 5.7%, `01-setup` 5.4%, `06-postprocess` 5.2%, `08-aux` 4.9%.

**Six conclusions, and the first is the one that answers the question.**

1. **The complaint is right, and the cause is structural rather than slow work.** Translating is 43% of
   the time; **57% is the pipeline around it.** On a short document that ratio is far worse — at 24
   paragraphs, 96% of a 20-minute run is fixed cost. **The skill has one gear**, and it runs an
   eleven-step, ~50-invocation ceremony over a two-page power of attorney and a 613-paragraph
   contract alike.
2. **Script execution is not the cost and never was.** Total Python time is **3.4 to 21.4 seconds per
   run** against 18–50 minutes — 0–1%, confirming P-cluster's finding from a second direction. **No
   optimisation of the Python can move this.** What costs time is the number of sequential model
   round-trips: **603 step invocations across twelve runs, ~50 per document, of which 85 (14%) exited
   non-zero.**
3. **The register already contains the measurement that proves the point.** H3: an already-English
   document took **35 minutes and 28 commands to change 11 paragraphs**, because the eleven steps ran in
   full over a document that needed a variant conversion. That is the fixed overhead with the variable
   part removed, and it is the clearest single argument for KS5's declared-mode gap being a *time*
   problem as well as a correctness one.
4. **Do not cut the final validate.** `11-validate` is 10.6% of all time and it is the render-and-compare
   that A1 records as producing or confirming the top finding on **every** document. It is the best-value
   ten minutes in the pipeline.
5. **Do not cut the lexicon reads either.** `03-lexicons` is 5.7% — about 90 seconds a document — and P5,
   P17 and T5(c) all measured that reading them in full pays. **The two things most often proposed as
   savings are together 16% of the time and both earn it.**
6. **The savings are in rework and in ceremony, which is to say: in the defects already in the register.**
   Every gate cycle spent on a false positive (cluster G: nine warnings, nine false, zero real on one
   document), every re-apply forced because *"the pipeline cannot re-apply a single paragraph"* (F28: six
   wrapped invocations to change one line), every block from a validator that disagrees with itself across
   three invocations (C15) is time. **Fixing the register makes the skill faster; there is no separate
   efficiency workstream.**

**What A3 can and cannot say here, stated plainly.** It can decompose the time and it can show the fixed
overhead dominates. **It cannot isolate how much of `04-translate`'s 121 minutes is genuine first-pass
translation and how much is re-translation caused by a defect downstream** — the logs record invocations,
not intent. **[I]** That needs a controlled run, and it is the one measurement Step C could add cheaply:
instrument the harness to mark an invocation as *first pass* or *rework*.

**One honest tension for Step B to resolve, because it is a product decision and not a technical one.**
The charter sells the runtime as a feature — *"deliberately slower and larger … minutes, not seconds"* —
and for a 613-paragraph contract at 4.9 seconds a paragraph that is entirely defensible. **For a
24-paragraph power of attorney at 51.6 seconds a paragraph it is not**, and no amount of describing it as
thoroughness will make a lawyer feel otherwise. The measured answer is not "make the skill faster" but
**"give it more than one gear"** — which is the same declared-mode change KS5 already needs for H3 and L5.

### 3.5 Redundancy and over-engineering — the answer is capabilities, not files

*Added after Wouter asked whether A3 had looked for redundant or over-engineered elements. It had not,
and it should have: goal (i) asks in terms for the scaffolding to be analysed **"for redundancy"**. This
is A3's scope, not Step B's.*

**Start with the negative results, because three popular suspicions are wrong** **[M]**:

- **The 154 sub-lexicons are not redundancy.** Every one of the 14 domains has both a reference and a
  sub-lexicon layer except `trading-capital-markets`, whose absence is documented and deliberate. There
  is no orphan, no duplicate, no unused domain.
- **There are no dead scripts.** All 20 are reachable. Four never appear in a command line across twelve
  runs — `validate_en_runs`, `strip_noop_tracked_changes`, `source_language_markers` and
  `clean_conversion_artifacts` — but the first three are **auto-invoked from inside other scripts** and
  the fourth applies only to a legacy `.doc`, where the one operator who met it refused to run it for the
  reason F12 records. *(That last one is a test-coverage gap, not redundancy: a mandatory script has
  never actually run in this project's evidence base.)*
- **SKILL.md and the step docs do not repeat each other.** Exact-block duplication across those nine files
  is **7,397 bytes, 4.0%**, and it is **entirely two deliberate boilerplate blocks**: the 659-character
  Pre-flight banner on all 8 step docs, and the 464-character Internal compliance check on 7 of 8. Both
  are anti-drift devices doing their job. *(This measures verbatim blocks only. Paraphrase-level
  redundancy is not measurable this way and I have not measured it — an honest gap.)*

**Now the positive result, and it is the useful one. The redundancy is in CAPABILITIES, not in files —
and the duplicated implementations disagree with each other, which is what several clusters record as
defects** **[M]**:

| capability | implementations | evidence, and which cluster records the disagreement |
|---|---|---|
| **source-language detection** | **4 measured in a run**, 5 by static inspection | **S1 is ground truth, not a grep**: on one document `lexicon_compliance` said *finnish*, `apply_translations_textmatch` said *polish*, `translate_numbering` said *french* and `quality_check` said *polish* — **four components, three different wrong answers, every one printing CLEAN or PASSED** |
| **source-language remnant scan** | **4** | S1's "five clean reports"; C2 (no month names or date shapes), C9, A16 (the scan built for content controls was blinded by a misdetected language) |
| **bold / italic read from the XML** | **3** — `extract_paragraphs`, `apply_translations_textmatch`, `translate_headers_footers` | A12, A17, A18, F7, F13, F22 — **the largest cluster in the project is about this one question being answered wrongly**, and it is answered in three places |
| **UK/US spelling table** | **2** | **V1** — the two copies have drifted apart: 37 rules against 60, and 34 against 91 |
| *named word tokeniser* | **1** — `validate_apply` | **a POSITIVE, and worth stating: C1's token-set defect — the master cause of cluster C — lives in exactly one implementation, so its fix lands in one place** |
| *integrity sentinel* | 20 | deliberate and correct — goal (iv) |

> **A methodological caution I earned twice in this session, and it belongs in the section rather than in
> a footnote.** My first count of these capabilities gave 7 / 6 / 4 / 4 / 2; a second pattern gave
> 4 / 5 / 3 / 1 / 2. **A grep over source counts a mechanism wherever a message merely describes it** —
> `validate_en_runs.py` "reads bold" only because its BLOCK banner quotes `<w:b w:val="0"/>`. The figures
> above are measured with **all string literals stripped**, and anchored on **run-measured** evidence
> wherever a real run supplies it. **Where the two disagree, the run wins.** This is the register's own
> rule about heuristics — *validate a heuristic against ground truth before trusting it* — applied to my
> own instrument, and it is the reason this table is smaller than my first draft's.

**The structural statement: there is no shared library. Twenty standalone scripts, each re-implementing
what it needs.** That is the over-engineering, and it is not a tidiness point — it is why a fix has to
land in three or four places to be complete, and why the copies have diverged. It maps directly onto the
keystones: the **three bold readers are KS1**, the **four detectors and four remnant scanners are KS3**,
the **two spelling tables are the variant question (§4)**.

**So the verdict on over-engineering is not what the question expected.** The skill is **not** over-built
in file count, step count, or script count — the 154 small lexicons are the context design working, the
eleven steps are not the problem, and no script is dead. It is over-built in **independent
re-implementation of four shared capabilities — thirteen implementations of four things** — and *that*
redundancy is expensive twice over: once in maintenance, and once in every defect where two copies answer
the same question differently. **The counter-example is the one that shows the fix works: there is exactly
one word tokeniser, and C1, the master cause of the whole gate cluster, is therefore a one-place fix.**

**One thing this section deliberately does not conclude.** *"Extract a shared library"* is an obvious
response and it is a **Step B decision, not an A3 finding** — it would touch every script, it is exactly
the kind of change that needs KS3's verification in place first, and on its own it fixes nothing a user
would notice. A3's contribution is the measurement: **four duplicated capabilities, thirteen
implementations, one capability with a single implementation as the control — and every disagreement
between copies is already logged as a defect.**
---

## 4. Wouter's hypothesis (charter observation 10), tested

> *"I just want two skills … one US-standard and one UK-standard. **Probably only SKILL.md will be
> different.**"*

### 4.1 What actually diverges

**[M]** 176 of 198 files differ; **22 are byte-identical**, and only **15 of 154** sub-lexicons are among them. Whole-tree changed lines **1,702 UK + 1,891 US =
3,593** — the charter's *"~3,600 lines"*. Within that, `scripts/` alone is **139 + 281 = 420** — the
charter's *"420 changed lines across 15 scripts"*. **Both charter figures reproduce exactly.**

| directory | differing files | UK lines | US lines |
|---|---|---|---|
| `SKILL.md` | 1 | 44 | 46 |
| `skill-docs/` | 6 of 8 | 75 | 114 |
| `references/` | 15 of 15 | 262 | 266 |
| `scripts/` | 15 of 20 | 139 | 281 |
| `sub-lexicons/` | 139 of 154 | 1,182 | 1,184 |

A **deliberately crude** fold of the known variant layer (spelling families, Clause/Section,
licence/license, indemnity/indemnification and ~35 doublets) accounts for **68.3%** of the 1,947 changed
line-pairs mechanically; **618 pairs in 93 files** it does not. *The fold is a filter, not a verdict — it
is tuned to under-explain, so a residue does not by itself mean a line is outside the variant layer.* The
residue was then read by file, heaviest first: `post_process` 132, `quality_check` 62, `04-translate` 50,
`general-legal` 37, `lexicon_compliance` 33, `SKILL.md` 31 — **345 of the 618 (56%) in six files** — plus
the remaining nine differing scripts in full. **[M for the counts; the classification below is my reading
of those lines, not a mechanical result.]**

### 4.2 Verdict, per category

**`SKILL.md` — the hypothesis is confirmed, and the divergence is load-bearing.** 31 of its 49 changed
line-pairs are the variant-selection logic itself: the `name:` field, the "do NOT ask the user" section,
which indicator to search the user's prompt for, which `--variant` default to pass, and the switch
semantics in both directions **[M]**. This is exactly the deliberate anti-drift hardcoding the charter's
counter-argument describes.

**`scripts/` — the hypothesis is directionally right and currently FALSE, which is the important result.**
An AST-equivalence test (which ignores comments entirely) over all 15 differing scripts **[M]**:

| what differs | scripts |
|---|---|
| **comments and docstrings only** (AST identical after docstring-stripping) | `extract_paragraphs`, `reorder_definitions`, `source_language_markers`, `translate_comments`, `translate_headers_footers`, `validate_reject_all`, `validate_segment_shapes` — **7** |
| **a `--variant` default value + help text** (legitimately variant-bearing, one line) | `verify_diligence` (+ the defaults inside `post_process`, `quality_check`) |
| **user-facing message strings only** | `apply_translations_textmatch` (2), `coalesce_fragmented_tcs` (2), `strip_noop_tracked_changes` (5), `validate_apply` (5) |
| **executable rule tables and a function signature** | `post_process`, `quality_check`, `lexicon_compliance` — **3** |

The last row is the finding, and it is one-directional — **the UK tree is the degraded one** **[M]**:

- `post_process.py`: `UK_SPELLING` **37 rules (UK tree) vs 60 (US tree)**; `US_SPELLING` **34 vs 91**. The
  UK package — the **default** variant, the one most users install — runs the *smaller* table in both
  directions. The 23 missing US→UK rules are the rev45b long-tail doublets: `plough` appears **17 times in
  the US tree and 0 times in the UK tree**.
- `post_process.py`: `fix_article_to_clause(root)` in the UK tree takes **no variant argument and
  hardcodes "Clause"**; in the US tree it is `fix_article_to_clause(root, variant='us')` and honours both.
  **Consequence: a UK-package user who follows SKILL.md's own documented US-English switch gets `--variant
  us` spelling and UK cross-references.** This is a **fourth U1 instance, the first in executable logic, and
  the first reachable through the skill's own instructions** **[M]** — see new finding N1.
- `lexicon_compliance.py`: a BLOCK regex reads `\bapplicant organisation:\s*$` in the UK tree and
  `\bapplicant organi[sz]ation:\s*$` in the US tree. **The UK gate cannot see the US spelling of the same
  calque** **[M]**.

**`strip_noop_tracked_changes.py` also shows the conversion reached identifiers**, not just prose:
`normalised` → `normalized`, `neighbour` → `neighbor` as **local variable names** **[M]**. Harmless to run,
corrosive to maintain — no diff between the trees can ever be clean.

**`references/` and `sub-lexicons/` — the hypothesis is right in principle and the current divergence is
worse than the charter records.**

Marker counts **[M]**:

| marker | UK sub-lex | US sub-lex | UK refs | US refs |
|---|---|---|---|---|
| `(US default)` | **0** | 25 | **0** | 16 |
| `(UK)` | 318 | 387 | 47 | 50 |
| `(US)` | 298 | 362 | 42 | 30 |

Two corrections to charter observation 8 follow. **(a)** Its own three sub-lexicon figures sum to a
shortfall of **158**, not "roughly 130"; including `references/` the totals are **UK 705 vs US 870, a
delta of 165**. **(b)** Its claim that the dual-variant design *"holds in `references/` but has eroded in
`sub-lexicons/`"* is **falsified** — `references/` has 16 `(US default)` markers in the US tree and 0 in
the UK tree, and the `(US)` marker count actually runs the *other* way (42 UK vs 30 US).

**And the cost of convergence is higher than a merge, because the two trees carry different substantive
advice.** In `references/general-legal.md` alone **[M]**:

- the *"shall vs will/must"* guidance is a **different paragraph** in each tree — the US one is longer,
  cites Bryan Garner and federal-court style guides, and concludes "default to *shall* — it reads correctly
  in both"; the UK one concludes "default to *shall* for UK and *will*/*must* for US". These are not
  mirror images; they are different advice.
- the UK spelling table's US column reads `practice (noun)` where the US table reads `practise (verb)` —
  the UK tree has **lost the noun/verb distinction** that `variant-conformance.md` calls the single
  most-missed pair.
- the UK row `| Schedule | Exhibit |` asserts that the US equivalent of *Schedule* is *Exhibit*; the US row
  reads `| Exhibit / Schedule | Schedule |`. Different mappings, not mirrored ones.
- the *amendment / modification* row is a free choice in the US tree and a UK-default instruction in the UK
  tree.

### 4.3 The decisive datum, and A3's verdict

Criterion 15 scored **10 on all twelve graded runs**, in both directions, including the hardest calls —
which reads as evidence that hardcoding protects. **U1's third instance refutes that reading**: a US
deliverable shipped `CLAUSES` as its operative-part heading while all 21 internal references read
`Section`, because a Spanish sub-lexicon row **in the US package** hardcoded the UK form with no marker,
contradicting `general-legal.md` in that same package.

**The review's reading holds, and A3 adds a fourth instance in code.** Hardcoding did not protect; it is
the *thing that failed*. What would have protected is a dual-variant row with explicit markers on both
sides — which is exactly what convergence requires anyway. And the parity check planned for branch 3 must
therefore cover **script string literals and function signatures**, not only lexicon rows.

**So, per category, and this is A3's answer to observation 10:**

| category | is the divergence load-bearing? | evidence |
|---|---|---|
| `SKILL.md` | **YES, genuinely** | 31 of 49 changed pairs are the variant-selection logic |
| `scripts/` | **NO — except one default flag value per script** | 7 of 15 differ only in comments; the 3 that differ in logic are drift, one-directional, with the default tree degraded |
| `references/` + `sub-lexicons/` | **NO, if every row carries both terms with markers** — but converging them is an editorial adjudication, not a merge | 165 missing markers; four measured cases of divergent *advice* in one file |
| gloss prose, Python comments, identifiers | **NO** | AST-identical after docstring stripping on 7 scripts |

**One thing the hypothesis did not anticipate, and it is the strongest argument for converging: the drift
is not only in the variant layer. `SKILL.md` in the UK tree carries a content error the US tree does not.**
Lines 326–327 of the UK file read *"do not anglicise them to US equivalents … and do not Americanise them
to UK equivalents"* — **the verbs are swapped**. The US file reads them the right way round **[M]**. A
blanket UK→US spelling conversion would have produced *"Anglicize … to US"*, so the US tree was
hand-corrected and the UK tree never received the correction. **A semantic error, in the always-loaded
file, in the variant section, in the default variant.**

---

## 5. The eleven structural observations — keep / change / Step B decision

**Observation 0, found while measuring: charter §4's file-size block describes the US tree** **[M]**.
`skill-docs/` 131 KB = US 131,115 (UK is 128,106); `references/` 447 = US 446,998; `scripts/` 526 = US
525,629; `sub-lexicons/` 2,506 = US 2,506,476. So *"`04-translate.md` is 50 KB"* is the US figure; the UK
file is **47,707**. Immaterial to any conclusion, but it should be corrected, and it is a small worked
example of the thing this project keeps re-learning — a number without its tree is half a number.

| # | observation | verdict | reason |
|---|---|---|---|
| **1** | SKILL.md is 57 KB and always loads | **RE-MOTIVATE, do not cut for context** | Confirmed at 57,269 UK / 57,532 US, 18 H2 + 18 H3 **[M]**. But context is 6.4% of the window at peak (§3.2). The two live reasons to shrink it are **findability** (the Common-Pitfalls catalogue is 32.4% of the file) and **truncation** (it is 1,803 bytes past the observed cut and has no integrity check). Re-motivate; do not delete content on a token argument that the measurement does not support. |
| **2** | `04-translate.md` is 50 KB at the step needing headroom | **CHANGE — but as a consequence of KS1, not as a size exercise** | 47,707 UK / 50,463 US **[M]**. **Rule 3 alone is 8,028 bytes / 121 lines / 16.8% of the file — three times rules 4–14 combined [M]** — and it exists only because extraction cannot compute effective formatting. Fix KS1 and the file shrinks by ~17% as a side effect, with the contradiction (F22) removed rather than reworded. |
| **3** | Step-number gaps in filenames are intentional | **KEEP — confirmed, not a defect** | Prefixes measured as `01, 03, 04, 04b, 05, 06, 08, 10` **[M]**; each names the first step covered. **But note F21: the *packaging* is a live defect** — two files cover two steps each and carry one closing compliance block whose items span both, which forced an untruthful confirmation on D01. That is a packaging question, not a filename question. |
| **4** | 176 of 198 files diverge over ~3,600 lines | **CHANGE — Option C already decided; A3 confirms and re-prices** | **Both of the charter's figures reproduce exactly.** 176 differing files; whole-tree changed lines **1,702 UK + 1,891 US = 3,593** ("~3,600"); and `scripts/` alone **139 + 281 = 420**, which is observation 9's figure **[M]**. See §4 for what converging actually costs — the line count is the *easy* part of the price. |
| **5** | `trading-capital-markets` is a reference domain with no sub-lexicon | **KEEP the asymmetry; it is documented and deliberate** | Verified: it is the **only** reference domain with no sub-lexicon layer, and the only sub-lexicon/reference asymmetry in either direction **[M]**. `03-lexicons-and-segments.md` explains the merge and tells the operator exactly what to read. Revisit only if a capital-markets document ever grades badly on terminology. |
| **6** | Scripts carry self-integrity sentinels; check whether the constraint still exists | **KEEP, and EXTEND — the constraint is live** | 20 of 20 scripts protected and truncation-tested at 50/75/90/99% since rev36 **[C]**; 177 of 198 files unprotected **[M]**; three files per tree past the only observed cut **[M]**. The sentinels are the one part of goal (iv) that works. §3.3. |
| **7** | The two packages are not at the same revision | **CHANGE — confirmed and WIDER than recorded** | `plough` 17 (US) / 0 (UK) confirmed **[M]**. But the gap is not five doublets: `post_process`'s `UK_SPELLING` is 37 vs 60 and `US_SPELLING` 34 vs 91; `quality_check` is missing the same long-tail block; `fix_article_to_clause` is variant-parameterised only in the US tree; `lexicon_compliance`'s calque regex is variant-tolerant only in the US tree; and `SKILL.md`'s swapped-verb sentence is corrected only in the US tree **[M]**. **The UK tree is behind in executable logic, not just in spelling data.** |
| **8** | UK sub-lexicons have lost ~130 dual-variant annotations | **CHANGE — confirmed, but the numbers and the scope both need correcting** | The shortfall is **158** across sub-lexicons and **165** including references **[M]**, and `references/` has *also* diverged, contrary to the observation's text. §4.2. |
| **9** | The 420 changed script lines are almost entirely comment and docstring spelling | **FALSIFIED IN PART — this is the observation that most needs rewriting** | True of **7 of 15** scripts. **3 differ in executable content** and 4 more in user-facing strings **[M]**. The observation's conclusion — *"a single variant-parameterised script set would remove most of the maintenance surface"* — is **right, and the US tree already demonstrates the pattern** in `fix_article_to_clause`. Its premise is wrong; its recommendation survives. *(U1 already flagged this from the string-literal side; A3 extends it to signatures and rule tables.)* |
| **10** | Wouter's hypothesis | **Answered in full at §4** | Confirmed for `SKILL.md`; refuted as a description of the present state everywhere else; the recommendation stands and is strengthened. |
| **11** | Host detection enumerates products, not capabilities | **CHANGE — confirmed verbatim, and it is a doc-only fix** | Step 1a's three signals measured **[M]**: an `<application_details>` block naming "Cowork mode", an `mcp__cowork__*` tool, or `<env>` reporting a workspace folder. All three are branded; Claude Code qualifies only via the third, by accident. The capability the rule actually cares about is *can I write files that persist between steps* — which is what `.validate-state.json` and the 35-cap require. Keep the user-facing warning text verbatim; change only the detection rule. |

---

## 6. The complete 135-row structural map

> **Audit requirement 4.** Every skill finding is either mapped to a structural keystone or explicitly
> recorded as not structural. A row silently absent is the failure this catches.
>
> **The arithmetic: 135 skill findings = 128 mapped to structure + 7 explicitly non-structural.**
> *(135 = 126 clustered + 9 single-instance, re-derived row by row from the register **[M]**. The six
> rows A3 itself produced — C21, F34, L6, V1, W1, W2 — are included and mapped like any other.)*

**Primary keystone per row.** Where a row has a secondary, it is given in brackets. "Primary" means the
keystone whose fix would close the row; a secondary would only mitigate it.

| cluster | rows | primary keystone | notes |
|---|---|---|---|
| **A — content** (7) | A1, A2, A3, A6, A8, A9, A16 | **KS2** | A3 also has a KS1 face — tab characters are a positional device. **A5 was moved out of this group during the audit: see §1.1** |
| **A — format** (10) | A4, A5, A7, A10, A11, A12, A13, A14, A17, A18 | **KS1** | A13's cause is the *two-path* architecture (TC vs non-TC), which KS1 must unify or explicitly keep. A5 is A18's mechanism with `rFonts` (§1.1) |
| **A — exception** (1) | A15 | **KS5** | no compliant lever existed to repair B3's damage; the cost was a destroyed tracked change |
| **B** (8) | B1–B8 | **KS6** | B5, B6 also KS5 (a script silently overrides a lexicon instruction) |
| **C — gate substrate** (14) | C1, C2, C3, C4, C6, C8, C9, C10, C11, C12, C14, C15, C18, **C21** | **KS3** | C9 is also cluster S's mechanism; C11 is also KS5 (the false claim lives in SKILL.md). *M1, a single-instance row, shares this cause and is counted below* |
| **C — apply behaviour** (3) | C16, C17, C19 | **KS2** | C19 is `repack_docx.py`'s part list rather than apply's, same contract |
| **C — data contract** (2) | C13, C20 | **KS1** | neither check is buildable without KS1's computation |
| **C — instruction** (2) | C5, C7 | **KS5** | C5 is a described gate that does not exist; C7 is a conditional-vs-unconditional collision |
| **D** (6) | D1, D2, D3, D4, D5, D6 | **KS1** (layout face) | D3 and D4 additionally need **KS5**'s disclosure channel; there is no compliant repair for D1/D4/D5 today |
| **E — furniture** (4) | E7, E8, E9, E12 | **KS4** | |
| **E — coverage** (5) | E1, E2, E3, E6, E11 | **KS4** | closed by a term→file index or an instructed pre-translation grep |
| **E — conflict** (2) | E5, E10 | **KS5** | same-layer and reference-vs-reference precedence, both unstated |
| **E — silent negative** (1) | E4 | **KS3** | `translate_numbering` exits 0 with "Writing unchanged" on a covered language |
| **F — instruction substrate** (24) | F1, F2, F3, F4, F5, F6, F8, F9, F10, F11, F12, F14, F15, F18, F20, F21, F23, F28, F29, F30, F31, F32, F33, **F34** | **KS5** | F29 also KS6; F31 also KS4 (the 221-entry map is a lexicon in `scripts/`); F18 also KS1 (the run-offset inconsistency) |
| **F — extraction-caused** (4) | F7, F13, F19, F22 | **KS1** | these exist *only* because extraction cannot compute effective formatting; KS1 deletes them rather than rewording them |
| **F — apply behaviour** (2) | F16, F27 | **KS2** | `en.strip()` and the Step 4c offset desync |
| **F — content gap** (1) | F17 | **KS4** | numeric locale: a universal convention with no home in the lexicon layer |
| **G** (9) | G1–G9 | **KS3** | every row is a validator-scoping defect; G6 is the meta-observation that two validators produced 9 warnings and 0 true findings on one document |
| **H** (3) | H1, H2, H3 | **KS5** (mode) | H3 states it: source==target is an input class wanting its own mode |
| **J** (1) | J1 | **KS3** | the settled fix is a pre-repack scrub, i.e. a gate |
| **K** (2) | K1, K2 *(register ids)* | **KS5** | the cheapest fix in the project |
| **L — detector** (2) | L2, L3 | **KS1** (data contract) | detection exists only because the JSON cannot declare a role or a range |
| **L — audit / mode / order** (4) | L1, L4, L5, **L6** | L1, L4 → **KS3**; L5 → **KS5** (mode) | L4 is a missing Step 7 check; L1 is two mandatory steps that are mutually incompatible |
| **S** (3) | S1, S2, S3 | **KS3** | a check that guesses the language, guesses wrong, and prints CLEAN; the "declare it once" fix has the same shape as L's |
| **single-instance** (8 of 9) | R1 → **KS5**; M1 → **KS3**; N1 → **KS2**; O1 → **KS1**; U1 and **V1** → **§4** (variant convergence); **W1** and **W2** → **goal (iv)**, distribution rather than pipeline | | R1: the skill says what language metadata must NOT appear and never says what SHOULD. M1's surviving half is the *structural blindness* — three mechanisms all baselining on the converted file. **Q1 is the sixth and is non-structural** |

**Explicitly NON-structural — 7 rows, and why:**

| row | why it is not structural |
|---|---|
| **T1** | a measurement of what a multi-document session degrades. Its *content* (three unrepaired defects) is already mapped via A16, B1, B7, C19 |
| **T2** | technique bleed — an operator-behaviour observation |
| **T3** | attention density falling across a session — operator behaviour |
| **T4** | one instance of state contamination, self-reported and harmless |
| **T5** | five refutations of predicted batch effects — evidence about the *method*, not the skill |
| **T6** | an analytical conclusion (*fix the defects and batch position stops mattering*), not a defect |
| **Q1** | the installed Cowork build is the lawve.ai build; 4 metadata lines, no behavioural difference. A **distribution** fact, and it belongs to phase 5's packaging work rather than to the pipeline's structure |

**The arithmetic, group by group, so it can be checked rather than trusted:**
A 18 (7 + 10 + 1) · B 8 · **C 21** (13 + 3 + 2 + 2 + **C21**) · D 6 · E 12 (4 + 5 + 2 + 1) ·
**F 31** (23 + 4 + 2 + 1 + **F34**) · G 9 · H 3 · J 1 · K 2 · **L 6** (2 + 3 + **L6**) · S 3 ·
**single-instance 8** = **128 structural**.
T1–T6 and Q1 = **7 non-structural**. **128 + 7 = 135. Reconciled.**

**By keystone, primary only so every row is counted exactly once:**

| keystone | rows | made up of |
|---|---|---|
| **KS5** — instruction substrate | **36** | F-instruction 23 · **F34** · H 3 · C5/C7 2 · E5/E10 2 · K 2 · A15 1 · L5 1 · R1 1 |
| **KS3** — gate substrate | **32** | C-gate 13 · **C21** · G 9 · S 3 · L1/L4 2 · **L6** · E4 1 · J1 1 · M1 1 |
| **KS1** — form as effects | **25** | A-format 10 · D 6 · F7/F13/F19/F22 4 · C13/C20 2 · L2/L3 2 · O1 1 |
| **KS2** — apply's structural contract | **13** | A-content 7 · C16/C17/C19 3 · F16/F27 2 · N1 1 |
| **KS4** — the furniture dimension | **10** | E-furniture 4 · E-coverage 5 · F17 1 |
| **KS6** — `post_process`'s authority | **8** | B1–B8 |
| *(§4 — the variant question, not a keystone)* | **2** | U1 · V1 |
| *(goal (iv) — distribution, not a keystone)* | **2** | W1 · W2 |
| **total** | **128** | |

*Several rows have a defensible second home and Step B may move them; the ordering is not sensitive to
one or two moves.*

**One consequence of the map worth stating on its own.** **KS5 is the largest single group at 36 rows and
also the cheapest per row** — most of it is one-line edits — while **KS1, the most ambitious change in the
project, carries 25.** **The cluster letters organise the register by where the defect was SEEN; the
keystones organise it by where the FIX goes, and the two orderings do not agree.** Cluster F is one
keystone and a bit; cluster C is four different keystones; cluster A is three. That mismatch is the
practical output of this section for Step B, and it is why the branch list must be derived from the
keystones rather than from the cluster letters.

---

## 7. New findings this analysis produced — WRITTEN INTO THE REGISTER

> **Status: APPLIED 2026-07-31, on Wouter's approval.** A3's first draft parked these outside the register
> on the ground that A3's remit was to reorganise rather than add. Wouter's decision was that a finding not
> in the register is a finding that will be lost, and that is plainly right. **All six are now rows, U1 has
> its fourth instance, and the register's counts have been re-derived: 129 → 135 skill findings, 166 → 172
> total rows.** Validator: PASS, 0 failures, 0 warnings.
>
> **To be explicit about provenance, because Wouter asked: these are NOT his review findings.** They were
> produced by A3 itself, by running scripts over the two published rev44 trees in this session. His review
> findings were folded in earlier and are already rows (E7–E12, D4, D5, D6, C20, A18, F33, H3, U1). Every
> row below carries origin **`code`** — a new origin token meaning *read directly out of the published
> trees, with no document involved* — so the two can never be confused again.

**The draft ids collided and were renumbered.** My working labels were N1–N7, and **`N1` is already a
register row** (extraction descends into `w:smartTag`; application does not). Caught by the check that
every new id is new, before writing. Final placement, each in the cluster whose root cause it shares:

| draft | final id | where | why there |
|---|---|---|---|
| N1 | **U1**, fourth instance | single-instance | same root cause as U1's other three: a variant-specific rendering hardcoded with no marker. First one in a **function signature** rather than a string |
| N2 | **V1** | single-instance | the UK tree is behind in executable logic — charter observation 7's class, which had no register row at all |
| N3 | **C21** | cluster C | it is a hole in a **gate**, and it compounds C11's hole in the same rule |
| N4 | **F34** | cluster F | a wrong instruction in the always-loaded file |
| N5 | **W1** | single-instance | goal (iv): the size threshold |
| N6 | **W2** | single-instance | goal (iv): sentinel coverage. Kept separate from W1 because they are two different pieces of work |
| N7 | **L6** | cluster L | it is a second consumer of cluster L's detector |

| id | finding | sev |
|---|---|---|
| **U1** *(4th instance)* | `fix_article_to_clause` is variant-parameterised in the US tree and **hardcoded to "Clause" in the UK tree**, so a UK-package run following SKILL.md's own documented US-English switch gets US spelling and **UK cross-references**. First instance in executable logic, and the first reachable through the skill's own instructions rather than through a lexicon row. **[M]** | MED |
| **V1** | The UK tree is behind in **executable logic, not only spelling data**: `UK_SPELLING` 37 rules vs 60, `US_SPELLING` 34 vs 91, `quality_check` missing the matching long-tail block. **The default variant runs the smaller tables in both directions.** Falsifies charter observation 9's premise; its recommendation survives. **[M]** | MED |
| **C21** | `lexicon_compliance.py`'s calque BLOCK regex is `applicant organi**s**ation:` in the UK tree and `applicant organi[sz]ation:` in the US tree — **the UK gate cannot catch the US spelling of a phrase it blocks.** Two independent holes in one rule: coverage (C11) and variant (this). **[M]** | MED |
| **F34** | `SKILL.md` in the UK tree has **the two verbs swapped** in the jurisdiction-specific-terms rule, corrected in the US tree. A *semantic* error a blanket spelling conversion cannot have produced, in the always-loaded file, in the default variant. **[M]** | LOW |
| **W1** | The install-size discipline has measured against **the wrong threshold since rev30**. Only observed cut: byte **55,466**. **Three files per tree are past it**; zero are near 126,865. `apply_translations_textmatch.py` is **4,097 bytes above the size rev29 trimmed it to for exactly this reason**. **[M]** | HIGH |
| **W2** | **177 of 198 files carry no integrity sentinel** — 89.4% of files, 85.4% of bytes, including `SKILL.md`. Detection did not degrade; it was **never extended past `scripts/`**. **[M]** | HIGH |
| **L6** | `validate_en_runs.py` **returns PASS whenever the definitions detector finds nothing**, so each of cluster L's four documented false negatives silently disabled the pipeline's only formatting gate. One detector, two consumers, both silent. **[M]** | HIGH |

**Corrections to existing rows — APPLIED**, wording only, no change to counts:

| row | correction |
|---|---|
| **F31(c)** | the phrase map is **nine** languages, not eight: HU 43, IT 25, FR 23, ES 22, PT 22, NL 22, PL 22, DE 21, FI 21 = **221** entries **[M]**. The 221 was exact. |
| **F23** | ground truth is **five** auto-invoked validators; `04b-translate-gates.md` is the only one of the three passages that is right, and **both wrong ones are in the always-loaded file** **[M]**. |
| **A10** | `en_runs` is not wholly inert on a tracked-change paragraph — it is read for **exactly one boolean** (`skip_bold_override`) and never for placement **[M]**. |
| **cluster A header** | the *"one fix closes them: carry a whitelist of properties **and** children from the matched source run"* sentence is **retired in place** — quoted, then corrected, so the record of what it used to say survives. There is no "matched source run"; it is two fixes in two files. |

**Corrections to `CLAUDE.md` — ALL APPLIED:**

| where | what changed |
|---|---|
| §4 file listing | replaced with **both trees' exact byte counts**, re-measured per file. The old figures were the US tree's throughout — so *"`04-translate.md` is 50 KB"* was the US file; **UK is 47,707**. A pointer to W1 added beneath. |
| §4 observation 8 | "roughly 130" → **158** across sub-lexicons, **165** whole-tree; and the claim that `references/` had *not* eroded is corrected — it has, in both directions. |
| §4 observation 9 | marked **falsified in part**, with the AST result (7 of 15 comments-only, 3 in executable content) and the two concrete cases; **its recommendation kept and strengthened.** |
| the validator note near the top | expected output is now **PASS with 0 warnings** *(applied earlier, before Wouter's approval, because left uncorrected it would have told the next session to distrust a clean run)*. |
| §2 Phase 2 status | **still NOT applied.** Wouter: *"it is not done"* until the deep audit and his review are complete. |

## 8. The register — reorganisation performed, and the split decision

### 8.1 The reorganisation: done, and proved

**Two defects, the second unrecorded and found by measurement rather than reading:**

1. **A15, A16, A17 and A18 are cluster A findings whose rows sat below the Cluster B table.** The
   validator warned about it on every run; the register itself declined to fix it, calling a cut-and-paste
   of that size *"a worse risk than a signpost"*.
2. **Both that block and the C19/C20/C17/C18/C14/C15/C16 block were separated from their table's header
   row by a BLANK LINE.** In GitHub-flavoured Markdown a blank line ends a table, and a pipe-delimited
   block with no delimiter row is not a table at all. **Eleven of the register's 166 rows were rendering
   as literal pipe-delimited paragraph text** **[M]** — including C18, which cluster T promotes to the
   highest-value single item in the register.

**The move was proved content-preserving, not reviewed for it** — the brief's condition, met at a stricter
standard than it asked for:

| check | required | result |
|---|---|---|
| identical **set** of finding ids | yes | **166 = 166, identical set** |
| identical **row count** | yes | **166 → 166** |
| identical SHA-256 of each row's **finding-cell** text | yes | **identical for all 166** |
| identical SHA-256 of each row's **FULL line** | *stricter than required* | **identical for all 166** |
| every non-row line edit accounted for against a declared list | *stricter than required* | **no unexpected edits** |
| validator before | PASS, 0 failures, 1 warning | as expected |
| **validator after** | **the A15–A18 warning should disappear** | **PASS, 0 failures, 0 warnings** ✔ |

Script: `temp/a3_reorg_register.py` (dry-run by default; refuses to write if any check fails). A pre-edit
copy is at `temp/FINDINGS-REGISTER.md.pre-a3-backup`.

**The rendering defect also produced a check worth keeping, and it was validated in both directions** — the
project's own rule for heuristics. `temp/a3_md_tables.py` asserts that every Markdown table row is
contiguous with a header and delimiter and carries the header's column count. Against the pre-edit backup it
reports **11 orphan rows**, naming exactly the eleven; against all three committable files today it reports
**0 orphans, 0 width mismatches across 55 tables**. **Candidate for the future `tools/`** — the register's
validator checks what the rows *say* and had no opinion on whether they *render*, and this is the second
time in the project that a defect hid in the gap between two checks.

**Placement, with a reason for each** rather than a bulk append:

- **A16** with the other CRITICAL rows, after A2.
- **A18** immediately after A14 — A14's own first sentence says "READ WITH A18".
- **A17** immediately after A12 — A12 says "See A17", and A17 is A12's `w:rStyle` case.
- **A15** at the end of the HIGH block, after A10 — it records the *cost of repairing* another row's damage
  rather than a mechanism of its own.

Two short dated notes were added (one under each table) recording what moved and why, and the
audit-history line that asserted the misplacement now records that it was fixed. Nothing was deleted except
the navigation warning the move made false.

### 8.2 The split — refused, with reasons

The brief made the split conditional: *"only if `audit_register.py` still works across the split. If the
split would break the validator, do not split."*

**It would break it, in three of its six checks** **[M]**:

- **Check 3, dangling cross-references**, scans the whole file for id-shaped tokens and requires each to
  resolve to a row in the same string. The register is dense with cross-cluster references — A12↔A17,
  C20→A12/A17/F7, T6→A16/B1/B7/C19, E9→A7/B1, L4→L2/L3. Split it and every one of those is reported as
  dangling.
- **Check 2** compares the Clusters table against the rows that exist; **check 4** reconciles the Coverage
  header against a row-by-row count across clusters, positives *and* the instrument table. Both need the
  whole corpus in one string.

Concatenating the parts before validating is a two-line change — but it makes the `ln` line numbers in every
failure message meaningless across the join, and those messages are how the validator's failures get found.
**And the validator is one of the seven publishable-clean private tools; changing it is code, and A3
produces none.**

**The merits argue the same way.** The premise of the split is context cost: **251,262 bytes ≈ 62,800
tokens, 6.3% of the window** **[M]** — the same measurement that says the *skill's* context load is a
non-issue says this is one too. Against that, the register's value is precisely that a cross-cluster
reference resolves in one place, and §6 shows that the most useful re-grouping of the register cuts
*across* cluster boundaries, which a file split would freeze in the wrong dimension.

**Decision: DO NOT SPLIT.** Improve navigability instead, which is free and keeps the validator whole —
which is what §8.1 did. If a future session finds the file genuinely unreadable, the right move is a
generated index at the top, not a split.

---

## 9. THE A3 AUDIT GATE

> Wouter, 2026-07-31: *"triple check, do a deep audit and verify your summary … I REALLY don't want it to
> contain errors or omissions."* The gate exists because the same request during the document review found
> errors **every time it was made**. An audit that reports nothing found should be treated as evidence the
> audit was too shallow.

**All six requirements were run three times: on the first draft (items 1-12), as the deep verification
Wouter asked for after the fixes (items 13-17), and again over the two sections added in answer to his
questions on efficiency, redundancy and runtime (items 18-21). The audit now runs 108 independent
re-derivations and changed twenty-two things, twelve of them errors of my own.**

### Requirement 1 — RE-MEASURE, DO NOT RE-READ

Every numeric claim was derived by a script written fresh in this session, run over the two unpacked rev44
archives, never taken from `CLAUDE.md`, the register, or a changelog summary. Scripts: `temp/a3_unpack.py`,
`a3_measure_tree.py`, `a3_divergence.py`, `a3_unexplained.py`, `a3_sections.py`, `a3_context_inventory.py`,
`a3_truncation.py`, `a3_verify_claims.py`, `a3_reorg_register.py`, `a3_md_tables.py`.

**What re-measuring changed:**

- **Charter observation 8's "roughly 130" is 158** (165 including references). Re-reading would never have
  caught it — the charter's own three figures sum to 158.
- **Charter observation 9 is falsified in part.** The AST test found 3 scripts differing in executable
  content where the observation says "almost entirely comment and docstring spelling".
- **The install cap.** Re-reading the charter would have confirmed 126,865 and moved on. Re-measuring the
  changelogs found 55,466 as the only observed figure and three files past it.
- **Charter §4's sizes are the US tree's.** Only a two-tree measurement shows this.
- **F31c is nine languages, not eight.**

### Requirement 2 — CHECK EVERY CITATION AGAINST THE FILE IT CITES

`temp/a3_verify_claims.py` runs thirteen mechanical citation checks. **First run: 10 pass, 3 fail. All three
failures were MY tests being imprecise, not the register being wrong — and I record that rather than
quietly fixing the tests:**

| check | first result | resolution |
|---|---|---|
| F31c's 221-entry map | FAIL — counted 230 | my count included `LANGUAGE_MAPS`, the 9-entry index. 230 − 9 = **221 exactly.** The register is right; **but the map is nine languages, not eight** |
| the seven-item whitelist | FAIL — counted 8 | my regex captured `{W}type` from `child.get(f'{W}type','')`. The tags are **7** as the register says |
| `en_runs` reads only bold/italic | FAIL — found 6 keys | my regex matched `en_seg.get(...)` in the tracked-changes path, a different variable. From an **`en_runs`** span, apply reads exactly `start`, `end`, `bold`, `italic` — the register is right |

**Ten claims verified first time**, including the ones A3's keystone rests on: extraction reads no
`rStyle`/`highlight`/`smallCaps`/`vertAlign`/`shd`/`strike`; extraction *does* emit `underline`/`font`/
`sz`/`color`; `get_default_rpr_et`'s test sits inside the loop; apply contains no coverage check (C5);
`Done at` appears nowhere in the tree (E7); the section symbol appears in none of SKILL.md or the eight step
docs (E8); 154 = 11 × 14; `trading-capital-markets` is the only asymmetric domain; the step-doc prefixes.

**Two citations I chased to the file rather than trusting a summary, because the review's worst error was
exactly that:** rule 3's self-admission (*"the extract reads run-level only and cannot distinguish 'silent'
from 'explicitly false'"* — verified in `04-translate.md`), and `make_run_et`'s off-flag comment (verified
in `apply_translations_textmatch.py`).

### Requirement 3 — AUDIT THE BOOKKEEPING SEPARATELY FROM THE PROSE

Counts, id sets, ranges and every *"N of M"* were checked as their own pass, and this is where the errors
clustered during the review.

- Register rows re-derived by script: **166 = 123 clustered + 6 single-instance + 26 positives + 11
  instrument** — matches the Coverage header and the validator **[M]**.
- **129 skill findings** re-derived independently as 123 + 6 **[M]**.
- Cluster row counts re-derived: A 18, B 8, C 20, D 6, E 12, F 30, G 9, H 3, J 1, K 2, L 5, S 3, T 6 = 123.
- The F-cluster's `F1–F23, F27–F33` = 23 + 7 = **30** ✔ (F24–F26 declared unallocated).
- **Divergence line counts, re-checked against my own table rather than against my summary of it:**
  `scripts/` alone is **139 UK + 281 US = 420** — the charter's "420 changed lines across 15 scripts" —
  and the whole tree is **1,702 + 1,891 = 3,593**, the charter's "~3,600 lines" of observation 4. **Both
  charter figures reproduce exactly.** An earlier draft of §5 called the 3,600 unreproducible and
  attributed the 420 to the whole tree; both statements were mine, both were wrong, and §4.1 and §5 are
  corrected. *This is the clearest instance in this session of why the gate exists: the measurement was
  right in the table and wrong in the sentence about the table.*
- The 122 + 7 = 129 structural map reconciles.

### Requirement 4 — HUNT OMISSIONS, NOT ONLY ERRORS

§6 walks all 129 rows. **122 mapped to a keystone, 7 explicitly recorded as non-structural, 122 + 7 = 129.**
Building that table is what surfaced three things prose review had not:

- **L6** (drafted as N7) — the L-detector/`validate_en_runs` coupling. It appeared in no row because it sits *between* two
  clusters.
- **cluster D belongs with cluster A's formatting half**, under one principle (form preserved as counts,
  not as effects) — which no cluster-ordered reading makes visible.
- **KS5 is the largest group by row count (~38) and the cheapest per row**, which the cluster ordering hides
  because those rows are spread across F, C, E, H, K, L, A and D.

### Requirement 5 — STATE CONFIDENCE PER CLAIM

The **[M] / [C] / [I] / [P]** markers are used throughout. The claims that matter most and are **inferred,
not measured**, are flagged again here so they cannot be read as measurements:

1. **That fixing KS1 closes A4/A7/A10–A14/A17/A18.** The shared cause is measured; the closure is inferred.
   No modified build has been run.
2. **That a wider property whitelist would make A18 worse.** A direct reading of the copy-template
   mechanism, which is measured — but not demonstrated on a modified build. **[I]** This is the single most
   consequential inference in the document and Step B should test it before relying on it. The test is
   cheap: widen the whitelist on a fixture with a mixed-state paragraph and render.
3. **That the explicit off-flags exist *because* extraction cannot resolve the cascade.** The comment and
   the absence are both measured; the causal "because" is my reading of the author's intent.
4. **That the two truncation figures describe one phenomenon at different sizes.** Consistent with rev27's
   "content-deterministic" wording and with the comment inside `extract_paragraphs.py`, but the mechanism is
   in Cowork's install pipeline and outside anything this project can measure.
5. **That converging the trees is safe.** Criterion 15's twelve 10s were measured *with the trees still
   hardcoded*, so they do not settle it; U1's shipped instance argues hardcoding did not protect. Both are
   evidence; neither is proof.

### Requirement 6 — RUN BOTH CONFIDENTIALITY CONTROLS AND THE VALIDATOR

Run at the end of the session over both committable files and this document. Results in §9.1.

### 9.1 What the first pass changed — the honest list

| # | what the audit changed | how it was found |
|---|---|---|
| 1 | **Observation 4's line count restored.** An earlier draft said the "~3,600 lines" figure was not reproducible; the bookkeeping pass found 1,702 + 1,891 = **3,593**, and that the 420 belongs to `scripts/` exactly as the charter says. **Both charter figures are correct and my first reading was wrong.** | requirement 3 |
| 2 | **F31c's language count corrected** from eight to nine | requirement 2 |
| 3 | **Three of my own citation tests were wrong**, not the register (§9, requirement 2) | requirement 2 |
| 4 | **L6 added** (drafted as N7) — the L-detector coupling, invisible to any cluster-ordered reading | requirement 4 |
| 5 | **Cluster D re-mapped** to KS1's second face rather than left as its own unexplained cluster | requirement 4 |
| 6 | **A10 refined** — one boolean, not wholly inert | requirement 2 |
| 7 | **F23 sharpened** — five validators, and the step doc is the only correct passage | requirement 2 |
| 8 | **Charter §4's sizes identified as the US tree's** | requirement 1 |
| 9 | **`CLAUDE.md`'s validator-expectation line updated** so a clean run is not read as a broken validator | requirement 6 |
| 10 | **The by-keystone totals were wrong in my first draft** — I wrote them as approximations (KS5 ≈ 38, KS4 ≈ 11, KS6 ≈ 9) and they summed to 134 against a structural total of 122. Re-derived row by row: **KS5 35, KS3 30, KS1 25, KS2 13, KS4 10, KS6 8, U1 1 = 122.** The *ordering* was right and the arithmetic was not — which is exactly the class of error the bookkeeping pass exists for, and it is the second time in this session that a correct measurement was spoiled by the sentence summarising it | requirement 3 |
| 11 | **M1 was double-counted** — listed under cluster C for cause *and* under single-instance. Corrected; C is 20 rows and M1 is counted once, with single-instance | requirement 3 |
| 12 | **A5 was mapped to the wrong keystone.** I had followed the charter's grouping of A5 with A6 as "re-concentration into one run". Walking the code path shows A5 is the *template-selection* mechanism — A18's, with `rFonts` — and therefore KS1, not KS2. **It is the earliest recorded instance of A18 and nobody had connected it.** KS1 25, KS2 13 | requirement 3 |

### 9.2 The second pass — the deep audit Wouter asked for after the fixes

> Wouter, 2026-07-31, on approving the seven findings and the corrections: *"After these fixes we need a
> very deep audit and verification."*

**`temp/a3_deep_audit.py` re-derives every number this document asserts, from scratch.** It imports none
of the A3 measurement scripts, so a shared bug in those cannot survive into the check, and where a second
counting method exists it uses the other one. It then confirms that the A3 document, the register and
`CLAUDE.md` each *state* the value it measured — a claim that is right in a script and absent from the
prose is still a defect, and that is precisely how items 1 and 10 got in.

**Result: 108 checks, 0 failures.** Covering: both trees' file counts and byte totals; every per-directory
and per-file size quoted anywhere; the byte-identical file counts; all twelve variant-marker counts and
the two shortfall figures; both spelling-table lengths in both trees; the `plough` counts;
`fix_article_to_clause`'s signature in both trees; the calque regex in both trees; the swapped-verb
sentence in both trees; both truncation thresholds and the three over-size files; sentinel coverage in
files and in bytes; the Step-4 context peak in bytes, tokens and share-of-window; rule 3's size in three
units; the Common-Pitfalls share; the phrase map's nine maps and 221 entries; the register's full
arithmetic and every new id; that every register id A3 cites exists; that the renumbered draft labels
survive nowhere except the renumbering table; the register validator; the Markdown-table renderer; and
the 93-pattern leakage scan over all three files.

**The deep audit found five more things, and four of them were bugs in its own tests** — recorded because
a verifier whose failures are all its own is a verifier that has not been calibrated:

| # | what the deep audit changed | |
|---|---|---|
| 13 | **The draft ids N1–N7 collided with an existing register row.** `N1` is already *"extraction descends into `w:smartTag`; application does not"*. Caught by the pre-write assertion that every new id is new, **before** anything was written. Renumbered to C21, F34, L6, V1, W1, W2 and U1's fourth instance | real |
| 14 | **I wrote seven per-file US byte counts into `CLAUDE.md` that I had never measured.** I had measured the `skill-docs/` *total* and `04-translate.md`; the other seven step-doc figures were plausible numbers I supplied to fill a column. Caught within the same minute, measured, and replaced. **This is the worst thing either audit found, it is exactly what the gate exists for, and it is worth stating as a rule: a table with an empty cell is safer than a table with a guessed one** | real |
| 15 | `extract_paragraphs.py` is **27,154 UK / 27,153 US**; A3 and register row W1 gave one figure with no tree | real |
| 16 | **Three stale references to draft label `N7`** survived the renumbering to L6. Now caught by a standing check that draft labels appear only in the renumbering table | real |
| 17 | Four of the deep audit's own assertions were wrong before any of the above were found — a US size compared against the UK figure, two quoted fragments that did not match the prose, and an exclusion list clobbered by a duplicated line. **All four were my tests, not the documents**, exactly as in requirement 2's first pass | test bug |
| 18 | **"Four independent word tokenisers" in my first draft of §3.5 was 1.** The 4 came from a regex that did not survive shell escaping into the script. **The real figure is a POSITIVE** — C1, the master cause of the whole gate cluster, has exactly one implementation and therefore a one-place fix | real |
| 19 | **The §3.5 capability counts moved between 7/6/4/4/2 and 4/4/3/2/1 depending on the pattern**, because a grep over source counts a mechanism wherever a *message* describes it — `validate_en_runs` "reads bold" only because its BLOCK banner quotes `<w:b w:val="0"/>`. Re-measured with all string literals stripped and re-anchored on **run-measured** evidence (S1) wherever a real run supplies it | real |
| 20 | **"24.6 minutes fixed" is 24.5 when refitted from the published rounded table.** I was quoting a second decimal that the data does not support; the figure to carry is **"about 25 minutes"** | real |
| 22 | **Adding items 18-21 to this very table orphaned four rows** — a blank line between row 17 and row 18, which in GitHub-flavoured Markdown ends the table. **The identical defect §10.1 records fixing in the register, committed by me into the audit log about the register, three sections later.** Caught by `a3_md_tables.py`, the check that defect produced. *The lesson is not "be careful": it is that the check earns its place in `tools/`, because prose review does not see this and I had just written a paragraph about it* | real |
| 21 | **The timing script disagreed with the project's own analyser on all twelve documents** before it was aligned to it — wrong interruption threshold (120 s against 300 s), wrong attribution direction (forward, which the analyser's own comment explains is wrong), and `epoch` used unconditionally, silently dropping 30 of one log's 151 records. **All twelve ACTIVE figures now reproduce the analyser to the decimal**, which is what makes the decomposition usable | real |

**An audit that found nothing would have been too shallow.** Across three passes this one found **twelve
errors of my own** (items 1, 3, 10, 11, 12, 14, 15, 18, 19, 20, 21, 22), **two register corrections** (items
2, 6), **one register sharpening** (item 7), **two findings that only the row-by-row walk could produce**
(items 4, 12), **one charter correction** (item 8), and **one id collision caught before it was written**
(item 13). **Items 18-21 all come from the two sections added after Wouter's questions, which is the
expected pattern: the newest prose is the least audited prose.**

**Three patterns in my own errors are worth banking.** Items 1 and 10: **the measurement was right in the
table and wrong in the sentence about the table** — the *re-measure, do not re-read* rule turned on prose
rather than on data. Items 5 and 12: **I inherited a grouping from the charter instead of deriving it from
the code** — cluster D looked like its own cluster because the register files it that way, and A5 looked
like A6's sibling because the charter says so. And item 14, the new one and the worst: **under pressure to
complete a table, I produced numbers of the right shape instead of leaving the cell empty.** None of the
three would have been caught by reading more carefully; all three were caught by re-deriving.

---

## 10. What Step B inherits

1. **Six keystones, priced, with their overlaps and the one hard dependency** (§2).
2. **A definite answer on extraction** — yes for the formatting half, no for the content half, and a
   specific, testable reason why the indicative branch 2 would regress A18 (§1).
3. **A re-motivated file-size strand** — not tokens, but findability and truncation, with the truncation
   threshold corrected (§3.1–§3.3).
3a. **A decomposition of the runtime** — 25 minutes fixed, 2.4 seconds a paragraph, 43% translation and
   57% machinery — and the conclusion that **fixing the register is the efficiency work** (§3.4).
3b. **A measurement of over-engineering** — five capabilities, twenty-three implementations, no shared
   library — and the three popular suspicions that are wrong (§3.5).
4. **A settled reading of the variant question** — converge, but budget for editorial adjudication rather
   than a merge, and extend the parity check to script signatures (§4).
5. **A register that renders, validates clean, reads in cluster order, and now explains its own letters**
   (§8, and the plain-English key at the front of both files).
6. **Six new register rows plus U1's fourth instance, written in and audited** — C21, F34, L6, V1, W1,
   W2 (§7). The register is 172 rows / 135 skill findings, validator clean.

**One thing A3 deliberately did not do, and Step B should not read the omission as an oversight:** it did
not rank the keystones. Severity ranks KS2 first, verifiability ranks KS3 first, ambition ranks KS1 first, and
Wouter's own review ranks KS4 first. Those are four different questions and the answer is his.
