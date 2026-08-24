# EVIDENCE-measurement.md — the corpus, and what the measuring instruments cost to get right

**This document owns two things and no rules:** the **eleven-document test corpus as a listing** *(from
§5.7 of `CLAUDE.md`)*, and the **dated cost stories behind the measurement rules** *(from §5.6)*. Every
rule stayed in the charter. **Where this document and the charter appear to disagree, THE CHARTER WINS.**

**Created 2026-08-24, phase 3c step 9 of the charter reduction.** Wouter's call *(2026-08-24)*: 5.6's and
5.7's material is **measurement, not confidentiality**, so it does not belong in
`EVIDENCE-confidentiality.md` — two evidence documents grouped by subject, rather than one mixed one or one
per subsection.

> **THIS DOCUMENT DESCRIBES REAL CLIENT DOCUMENTS AND IS THEREFORE WRITTEN UNDER §5.4's NAMING RULE:**
> instrument class and language, and **nothing else. Never what the instrument is about.** The
> *"what it uniquely tests"* column is a property of the **FILE**, not of the deal — a paragraph count, a
> script, a tracked-change load — which is exactly why it is publishable and a subject-matter qualifier is
> not. Its own confidentiality review is in section 4.

---

## 1 — The test corpus: eleven real client documents, outside the repo tree, permanently

**Referred to by instrument class and language only, per §5.4** — never by filename, because **the
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
| D09 | Document (Hungarian) | 96 | the most tables; **four known-answer judgement calls**, which is why it is the Step C arm document |
| D10 | Guarantee (Polish) | 45 | delivered both the positive and the negative highlight control in one file |
| D11 | MOU (Japanese) | 43 | **the only non-Latin script**, plus tracked changes |

**Variant assignment — 3 US / 8 UK, and the principle is not arbitrary.** The **hard technical paths run on
UK**, the default, so a failure is unambiguously a pipeline defect rather than a variant defect; **US goes
to terminologically rich but technically straightforward documents**, so variant divergence is what gets
tested. **US: D04, D05, D07. UK: the other eight**, including both hard paths.

**Two things the corpus cannot reach, so they need synthetic fixtures** *(the requirement itself stays in
§5.7)*: there are **no `Symbol` or `Wingdings` runs anywhere**, so the Greek-glyph defect cannot be
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
only revert path.** *(The freeze rule and the four instruments to hold constant are §5.6's and stay
there.)*

---

## 3 — The two dated cost stories behind the measurement rules

**Both rules stay in §5.6. These are what they cost.**

### 3.1 Scoring a run property from element counts — a false positive on SEVEN consecutive documents

**Translation consolidates runs, so nearly every count falls even when nothing is lost.** And it fails in
**both directions**: putting the English back **emits an explicit *off*-flag on every non-emphasised run**,
so the count can rise as well as fall for reasons that have nothing to do with the formatting.

**This produced a false positive on seven consecutive documents** before the rule was written. Hence
§5.6's: *never score ANY run property from element counts — compare the affected TEXT, then render.*

### 3.2 Taking a count from the narrative instead of the log analyser

**Across one batch the self-reported note totals were 14 / 12 / 11 against the analyser's 18 / 16 / 11**,
and **one document's non-zero exits were reported as 4 against a real 7.**

**The narratives remain the only source for *reasoning*** — that is why they are kept, and why the rule is
*take counts from the analyser, never from the narrative*, rather than *distrust the narrative*.

---

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
highlight count. **None of it says what any instrument is about**, which is the whole test §5.4 sets.
