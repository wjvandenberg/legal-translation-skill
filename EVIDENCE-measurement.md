# EVIDENCE-measurement.md — the corpus, and what measurement and verification cost to get right

**This document owns three things and no rules:** the **eleven-document test corpus as a listing** *(from
section 5.7 of `CLAUDE.md`)*, the **dated cost stories behind the measurement rules** *(from section 5.6)*,
and the **dated instances behind the verification-hygiene rules** *(from section 5.16, added 2026-08-25)*.
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

**Referred to by instrument class and language only, per section 5.4 of `CLAUDE.md`** — never by filename, because **the
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
section 5.7 of `CLAUDE.md`)*: there are **no `Symbol` or `Wingdings` runs anywhere**, so the Greek-glyph defect cannot be
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
only revert path.** *(The freeze rule and the four instruments to hold constant belong to section 5.6 of
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
section 5.6 of `CLAUDE.md`: *never score ANY run property from element counts — compare the affected TEXT,
then render.*

### 3.2 Taking a count from the narrative instead of the log analyser

**Across one batch the self-reported note totals were 14 / 12 / 11 against the analyser's 18 / 16 / 11**,
and **one document's non-zero exits were reported as 4 against a real 7.**

**The narratives remain the only source for *reasoning*** — that is why they are kept, and why the rule is
*take counts from the analyser, never from the narrative*, rather than *distrust the narrative*.

### 3.3 Six green numbers in one session, each reporting on something other than the thing being checked

**Moved here from section 5.16 of `CLAUDE.md` on 2026-08-25, phase 12.** The rules those instances bought
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

**The rule itself stays in section 5.16 of `CLAUDE.md`: it has no house twin, and this document owns no
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
highlight count. **None of it says what any instrument is about**, which is the whole test section 5.4 of
`CLAUDE.md` sets.
