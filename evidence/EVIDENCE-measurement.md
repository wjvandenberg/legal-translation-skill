# EVIDENCE-measurement.md — the corpus, and what measurement and verification cost to get right

**This document owns four things and no rules:** the **eleven-document test corpus as a listing** *(from
section 5.5 of `CLAUDE.md`)*, the **dated cost stories behind the measurement rules** *(from section 5.5)*,
the **dated instances behind the verification-hygiene rules** *(from section 5.3, added 2026-08-25)*, and
**the published law read for the retention check's drafting words** *(section 5, added 2026-11-10)*.
Every rule stayed in the charter or is carried by the auto-loaded house file. **Where this document and the
charter appear to disagree, THE CHARTER WINS.**

> **EVERY CROSS-FILE `§` IN THIS DOCUMENT WAS REWRITTEN IN WORDS ON 2026-08-25.** Nine of them read `§5.4`,
> `§5.6`, `§5.7` and meant sections of `CLAUDE.md` — but **a `§` resolves against the file it appears in**,
> so each was passing silently against the wrong section, or failing. `verify_md.py` reported all nine.

**Created 2026-08-24, phase 3c step 9 of the charter reduction.** Wouter's call *(2026-08-24)*: 5.6's and
5.7's material is **measurement, not confidentiality**, so it does not belong in
`EVIDENCE-confidentiality.md` — two evidence documents grouped by subject, rather than one mixed one or one
per subsection.

> **THIS DOCUMENT DESCRIBES REAL CLIENT DOCUMENTS AND IS THEREFORE WRITTEN UNDER THE NAMING RULE IN
> SECTION 5.4 OF `CLAUDE.md`:**
> instrument class and language, and **nothing else. Never what the instrument is about.** The
> *"what it uniquely tests"* column is a property of the **FILE**, not of the deal — a paragraph count, a
> script, a tracked-change load — which is exactly why it is publishable and a subject-matter qualifier is
> not. Its own confidentiality review is in section 4.

---

## 1 — The test corpus: eleven real client documents, outside the repo tree, permanently

**Referred to by instrument class and language only, per section 5.6 of `CLAUDE.md`** — never by filename, because **the
filenames alone carry counterparty names**, and never by subject matter. The doc-id → real-document mapping
lives in the private sibling folder, as it always has.

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
| D09 | Document (Hungarian) | 96 | the most tables; **four known-answer judgement calls**, which made it the arm document of the dropped Opus 5 run — **no longer an arm document** *(2026-10-14)* |
| D10 | Guarantee (Polish) | 45 | delivered both the positive and the negative highlight control in one file |
| D11 | MOU (Japanese) | 43 | **the only non-Latin script**, plus tracked changes |

**Variant assignment — 3 US / 8 UK, and the principle is not arbitrary.** The **hard technical paths run on
UK**, the default, so a failure is unambiguously a pipeline defect rather than a variant defect; **US goes
to terminologically rich but technically straightforward documents**, so variant divergence is what gets
tested. **US: D04, D05, D07. UK: the other eight**, including both hard paths.

**Two things the corpus cannot reach, so they need synthetic fixtures** *(the requirement itself stays in
section 5.5 of `CLAUDE.md`)*: there are **no `Symbol` or `Wingdings` runs anywhere**, so the Greek-glyph defect cannot be
reproduced from a real document; and content controls, smart tags, images with alt text and charts with
titles appear in **none of the eleven**.

---

## 2 — The grader, and the comparison that reads like a different rubric

**The grader is v3 and has 17 criteria** — its own package: `SKILL.md`, `references/methodology.md` and
`variant-conformance.md`. It was validated, found usable but with three gaps, and **extended twice.**

> **WHERE A COMPARISON OF TWO RUNS REPORTS "TWELVE OF SIXTEEN CRITERIA IDENTICAL", THAT IS NOT A DIFFERENT
> RUBRIC.** It is the register's own pairwise comparison, which **excludes one criterion that cannot be
> compared across runs.** Recorded because 16 against 17 reads as a discrepancy and is not one.

**Dated backups of the grader are in the private folder — it is deliberately not in Git, so those are the
only revert path.** *(The freeze rule and the four instruments to hold constant belong to section 5.5 of
`CLAUDE.md` and stay there.)*

---

## 3 — The dated cost stories behind the measurement and verification rules

**Every rule here stays in `CLAUDE.md` or in the auto-loaded house file. These are what they cost.**
*(The heading no longer says "two": a count in a heading goes stale the moment a story is added, and this
one did.)*

### 3.1 Scoring a run property from element counts — a false positive on SEVEN consecutive documents

**Translation consolidates runs, so nearly every count falls even when nothing is lost.** And it fails in
**both directions**: putting the English back **emits an explicit *off*-flag on every non-emphasised run**,
so the count can rise as well as fall for reasons that have nothing to do with the formatting.

**This produced a false positive on seven consecutive documents** before the rule was written. Hence
section 5.5 of `CLAUDE.md`: *never score ANY run property from element counts — compare the affected TEXT,
then render.*

### 3.2 Taking a count from the narrative instead of the log analyser

**Across one batch the self-reported note totals were 14 / 12 / 11 against the analyser's 18 / 16 / 11**,
and **one document's non-zero exits were reported as 4 against a real 7.**

**The narratives remain the only source for *reasoning*** — that is why they are kept, and why the rule is
*take counts from the analyser, never from the narrative*, rather than *distrust the narrative*.

### 3.3 Six green numbers in one session, each reporting on something other than the thing being checked

**Moved here from section 5.3 of `CLAUDE.md` on 2026-08-25, phase 12.** The rules those instances bought
are the **auto-loaded house verification hygiene**, and the one with no house twin stayed in the charter.
**This table is what they cost**, all on 2026-08-21.

| what was read | what it was actually reporting |
|---|---|
| `printf "… rc=%s" "$(basename $t)" "$?"` | **`basename`'s** exit code. A command substitution runs before `$?` is expanded, so this is always 0. Twelve test files were reported green while two were exiting 1 |
| `cmd \| tail -4; echo "rc=$?"` | **`tail`'s** exit code, never `cmd`'s |
| a long runner returning 0 | a process that **stopped part-way**. Four reproductions. Proved only because a sentinel FILE it should have written was absent |
| a monitor reporting "failed, exit 1" | **`grep`** finding nothing, on a sweep that was entirely green |
| a before/after suite reporting green | the fix **compared with itself**, because "before" was pinned to a branch name that had since moved. Worst on a byte comparison, where a file against itself is trivially identical and the vacuous case looks exactly like the passing case |
| `make_fixtures` returning 0 | a build **killed part-way** that had already deleted 8 of 11 fixtures |

### 3.4 Why this project's suites run as top-level commands — the two measurements behind the rule

**The rule itself stays in section 5.3 of `CLAUDE.md`: it has no house twin, and this document owns no
rule.** These are the two measurements it rests on.

- **`tests/make_fixtures.py` run as a captured child was measured to KILL ITS PARENT**, which is how a
  fixture set came to be half-deleted.
- **The suites share `tests/fixtures/` and rewrite it**, so anything run alongside a sweep invalidates it
  and is invalidated by it. A foreground suite caught a fixture mid-write and died with `BadZipFile` —
  **which reads exactly like a corrupt source document rather than a race**, and was diagnosed as one.

### 3.5 What running the cycle without artefacts cost, 2026-08-06 — four defects in work already presented as complete

**Moved here from section 5.1 of `CLAUDE.md` on 2026-08-25, phase 12.** The rule it bought — *the cycle must
produce artefacts, not intentions* — is the auto-loaded house file's. **This is why anyone believes it.**

**The repository session ran three branches end to end without pausing once, and the failure was not
ignorance:** section 5.1 had been read. **What was missing was any artefact whose absence would show.** When
VERIFY was finally run properly it found, in work already committed and presented as complete:

- **a published figure that was wrong** and had been reported as an *independent confirmation* of the plan;
- **fixtures that were not byte-reproducible**, which broke the one tool that branch existed to enable;
- **a parity check that missed the very defect it was built for**, because it tested one direction of a
  symmetric assertion;
- **a `__pycache__` leak into the shipped trees** that had been fixed once and returned through the next
  caller.

**None was found by reading. Every one was found by running something.**

**AND THE BYTECODE LEAK IS THE HOUSE RULE *fix the CLASS, not the caller* WITH A PRICE ON IT.** It was fixed
in the test runner, came back through the audit tool, came back again through the cycle gate, and came back a
**fourth** time through the tests added alongside the fix for the third. **Three of four callers patched
reads exactly like four of four until somebody greps.**

### 3.6 The A16 refutation, 2026-09-08 — a claim refuted for the WRONG REASON, and right after all

**Moved here from section 1.5 of `CLAUDE.md` on 2026-09-11, at THE CHARTER REDUCTION part (e), under route
2.** The rule it bought stays in the charter: **a claim can be refuted for the WRONG REASON, which costs
more than believing it — so measure a claim about BEHAVIOUR where the behaviour happens, never in the
document's structure.** **This is why anyone believes it.**

**A behavioural claim about A16 was refuted from the XML shape alone — and turned out exactly right on
measurement.** The refutation read as sound: the structure did not show what the claim implied. But the claim
was never about structure. **A claim about what an operator DOES is measured in the operator's notes**, which
is where the behaviour happens; the document's structure is a different kind of evidence entirely and cannot
settle it in either direction.

**THE TELL, and it is the transferable part: a refutation reached from a different KIND of evidence than the
claim was made from.** It is not a weak refutation — it is a refutation of a different proposition, and
nothing in its output says so. It cost more than simply believing the claim would have, because a claim
believed stays open to measurement while a claim refuted is closed.

---

### 3.7 The deterministic measures the mechanical gate computes — relocated from the charter, 2026-09-22

**Relocated out of `CLAUDE.md` section 5.3's *Never-regress* block under route 2.** What stayed in the
charter is the rule and both its tiers; what moved here is the ENUMERATION, which is mechanism narration: a
session needs to know a mechanical gate exists and that it is tier one, not to recite what it computes.

**Tier one, run on every change**, and between them these cover most of the structural criteria, which is
what makes `git bisect` usable on this pipeline at all:

- paragraph counts
- note and comment REFERENCE counts *(references, never parts — a translated footnotes part whose pointer
  was destroyed is unreachable while the part inventory still passes)*
- tabs against tab stops
- effective bold and italic text
- run-property tables
- remnant and invisible-character sweeps
- definitions ordering
- accept/reject reconstruction

**Tier two is a full LLM re-grade at step boundaries only**, on a fixed subset, against the frozen v3
baselines. **The measurement that makes tier one primary rather than merely cheaper** is the only
same-document repeat this project has: **~40% of paragraphs differed linguistically while the mechanical
output was identical** — variance large in prose, nil in mechanics. A grading tier that moves by 40% on an
unchanged document cannot be the gate; a tier that does not move at all can.

### 3.8 Planning from the brief alone — relocated from the charter's section 5.1, 2026-10-16

**Read what the brief POINTS AT, not only the brief.** Section 3.3 of `PLAN-2-step-b.md` says option 7's
substance lives in that document's section 6, and a session that planned step 2 from section 3.3 alone got
the arm count, the comparison method and the term-list source all wrong. The house file now carries the
general rule; this is the project's instance of it, kept here when the charter's Explore cell was shortened.

## 4 — This document's own confidentiality review

**Run before its first commit, like `EVIDENCE-confidentiality.md`'s** — and it matters more here, because
this is the document that describes real client documents.

| control | what it read | result |
|---|---|---|
| `tools/leakage_scan.py` | **93 patterns live** — the count is the proof the control ran, since it exits 2 on an unreadable list | recorded in the commit |
| `tools/publication_check.py` | this file, found by the `EVIDENCE-*.md` glob | recorded in the commit |
| `tools/descriptor_shape_sweep.py` | this file, list-free — **and this is the control that matters here**, because a subject-matter qualifier is invisible to a name scan by construction | recorded in the commit |
| a reading | the corpus table row by row, asking of each cell: does this describe the FILE or the DEAL? | recorded in the commit |

**Every cell of the corpus table describes the file.** No sub-lexicon · legacy binary `.doc` · non-Latin
script · table count · bold-run count · paragraph count · batch position · tracked-change load ·
highlight count. **None of it says what any instrument is about**, which is the whole test section 5.6 of
`CLAUDE.md` sets.

## 5 — Published law, read for the retention check's drafting words — sub-step 14.9.7, 2026-11-10

**Why.** Sub-step 14.5 took register G7's marker and title exemptions in `validate_translations.py` to every
language with words that were, beyond those the corpus and the lexicons hold, *"its language's usual drafting
formula, unmeasured"*; Wouter ordered them sourced from published law *(`DECISIONS-LOG.md`, 2026-11-02 (7))*.
**Public law only: no client document was read for this section**, so nothing in it falls under section 5.6
of `CLAUDE.md`.

**What was read.** Three EU acts in ten languages, fetched on 2026-11-10 from the Publications Office's
Cellar repository by content negotiation on `http://publications.europa.eu/resource/celex/<CELEX>`: the
public procurement directive `32014L0024`, the renewable energy directive `32018L2001`, and the 2021
standard contractual clauses `32021D0914`, the one written as a contract. Thirty files, each proved to be in
its language by the act's own word for the Commission and to differ from every other; the first twelve hex
digits of each file's SHA-256:

| language | `32014L0024` | `32018L2001` | `32021D0914` |
|---|---|---|---|
| deu | `c97a294508f1` | `6accafee97ec` | `af4655e47ce5` |
| eng | `f1bda7780252` | `397c92486129` | `85d76f03ea30` |
| fin | `7eee92bf1bb4` | `b8a6142eab0f` | `c04c4f8149a2` |
| fra | `b9067d2131d7` | `bebb50724767` | `1ad6d1926afb` |
| hun | `6029e1a4b75a` | `d4664d99c55d` | `e2958087f67e` |
| ita | `96ecf2bc3c9c` | `4d8868c48072` | `c1f5e6b3c2bf` |
| nld | `43455f0d585c` | `cc5d0b008405` | `f20ecb6e1469` |
| pol | `a7c9a29f94a3` | `31a49fd92887` | `c572d6d6b614` |
| por | `803cc7b00d59` | `0b33624d5819` | `ecb3631f20db` |
| spa | `976fdab432c5` | `4e7ac2b41362` | `58f77d46815f` |

**How.** `temp/s1110b_law_probe.py` read each word of the module's lists in its own language's three acts,
counting it in the **marker shape** — in a bracket before a quotation that closes inside it, or set off by a
comma with a quotation in the 40 characters after — in the **title shape**, the 40 characters before an
opening quotation (after a closing one for a Hungarian title word), and **anywhere**, a planted control
first. `temp/s1110b_law_cover.py` then asked the module's own exemption about every bracketed or comma-set
quotation in the same text, before and after the sub-step.

**The quotation marks, in spans per language:** English `‘…’` 258; Italian, French, Spanish and Portuguese
`«…»` 290, 269, 280 and 271; German `„…“` 287; Dutch `„…”` 252 and `“…”` 18; Polish `„…”` 284; Hungarian
`„…”` 250; **Finnish `”…”` 114 and `’…’` 145**, each opening only where no letter precedes it and closing only
where none follows, and no other style. *(A count of `»…«` between two guillemet quotations is the gap from
one to the next, not a style, and is left out.)*

**The words 14.5 added**, every word but Italian's and English's, which 14.3 measured on the corpus: of 86,
seven were measured on the corpus or the lexicons (Dutch `hierna`, `hierna te noemen` and `hieronder`, Polish
`zwana dalej`, French `ci-après` and `ci-dessous`, German `nachstehend`). **Of the other 79: 26 stand in
published law in their shape, 38 stand there but not in it, and 15 were not found in the three acts.**

| language | in the shape | in the law, not in the shape | not found |
|---|---|---|---|
| French | ensemble, chacun(e), dénommé, appelé, par, intitulé | conjointement, collectivement, individuellement, désigné | — |
| Spanish | en lo sucesivo, denominado, titulado | conjuntamente, colectivamente, individualmente, designado, como | en adelante, llamado |
| Portuguese | a seguir, designado, por, intitulado | adiante, conjuntamente, coletivamente, individualmente | doravante, denominado, simplesmente, abreviadamente |
| German | im Folgenden, jeweils, als, mit dem Titel | nachfolgend, im Weiteren, gemeinsam, zusammen, einzeln, genannt, bezeichnet, kurz, auch | betitelt, unter dem Titel |
| Dutch | getiteld | gezamenlijk, afzonderlijk, ieder, elk, genoemd, ook | tezamen, met de titel, onder de titel |
| Polish | dalej, zwany, także, również, zatytułowany | łącznie, odpowiednio, każdy | pod tytułem |
| Hungarian | a továbbiakban, című | együttesen, külön-külön, egyenként | címmel |
| Finnish | jäljempänä | yhdessä, erikseen, kumpikin, myös | otsikolla, otsikoltaan |

**Norwegian is not EU law:** `heretter` was measured on the corpus; `samlet`, `kalt` and `benevnt` are not
sourced. **Two lead-ins the law writes were MISSING from the lists and were added:** Italian
`(in prosieguo «X»)`, 3 times, and Spanish `(cada una denominada en lo sucesivo «X»)`, twice, a second
formula after the first. **And every Finnish marker in the three acts — 26 of 26 — is set off by commas, none
in a bracket,** as are 1 to 3 in each of six other languages, Dutch with its participle after the term
(`, hierna de „X” genoemd,`): that is the comma-set marker the sub-step built.

**Through the module, `b39f438` against the sub-step:** bracketed quotations recognised as markers 129 to 145
of 281, those not read at all 6 to 0; comma-set markers recognised 0 to 39 of 41, the two left being Polish
`zwanej także`, "also called" — a naming phrase, not a formula, and under the word threshold besides. The
136 bracketed quotations still not recognised are, by their first words, mostly ordinary bracketed text, and
otherwise a bare `("X")`, which 14.5 keeps checked on purpose.

**Decided, not by Wouter but by the sub-step, recorded:** **every word stays** — an exemption hides no loss
while the English keeps at least as many quoted spans as the source, and three acts cannot prove a word
unused; a word not found here is a drafting formula the law did not need, not one a contract never uses.
