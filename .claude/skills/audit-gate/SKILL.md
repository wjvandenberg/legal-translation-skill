---
name: audit-gate
description: The seven-point audit method for any analysis deliverable in this project, plus the standing instruments to run after editing a committable document and the four scripts deliberately left in temp/. Use when auditing or verifying a summary, report, register edit or plan document, when a numeric claim needs re-deriving, or when asked to triple-check work that other changes will be based on. Relocated from CLAUDE.md 5.12 under route 3 on 2026-08-24.
---

# The audit gate — for any analysis deliverable

**Wouter's standing requirement:** *"triple check, do a deep audit and verify your summary. This summary
is the basis of the changes, and I REALLY don't want it to contain errors or omissions."*

`CLAUDE.md` 5.12 keeps the trigger and points here. **The gate applies wherever the deliverable is an
analysis rather than code** — that condition is part of the charter's VERIFY stage and does not depend on
this page being loaded.

## Why it exists — it has found real errors EVERY time it has been asked for

A note count taken from another document's report · two runs described as one operator · a tab count that
was one paragraph's rather than the block's · a character count off by one · **a lexicon instruction that
does not exist in the file it was attributed to** · keystone totals that summed to 134 against a real 122
· **seven per-file byte counts written into a table without ever being measured** · and three stale counts
in the build plan.

**None would have been caught by re-reading.** That is the finding the method is built on.

## THE SEVEN POINTS — the method that actually worked, not diligence in general

1. **RE-MEASURE, DO NOT RE-READ.** Every numeric claim re-derived from the artefact by a script written
   fresh. **And where a standing instrument already measures the thing, reproduce ITS answer before
   trusting your own.**
2. **CHECK EVERY CITATION AGAINST THE FILE IT CITES.** If the report says a file says something, **open
   that file.** Note the trap that has caught this project twice: **a search over source counts a
   mechanism wherever a message merely describes it.**
3. **AUDIT THE BOOKKEEPING SEPARATELY FROM THE PROSE.** The errors cluster in counts, id sets,
   cross-references and every claim of the form *"N of M"*. Prose review does not see them.
4. **HUNT OMISSIONS, NOT ONLY ERRORS.** Walk the evidence row by row and confirm each row is either
   accounted for or explicitly recorded as out of scope. **State the arithmetic;** if it does not
   reconcile, the work is not done.
5. **STATE CONFIDENCE PER CLAIM, and distinguish MEASURED from INFERRED.** A claim asserted with the
   confidence of a measurement, when it is an inference, is exactly the error that mis-scopes the next
   step.
6. **NEVER A TWO-WORD NEEDLE.** Eleven checks in this project have passed for the wrong reason.
   **Normalise whitespace and emphasis by default, and make every needle a phrase that could only appear
   if the thing is actually carried.**
7. **RUN BOTH CONFIDENTIALITY CONTROLS, THE PUBLICATION CHECK AND THE RELEVANT VALIDATORS** on every
   committable file at the end.

**Report the audit's findings openly, including its own corrections. An audit that reports NOTHING found
should be treated as evidence the audit was too shallow, not that the work was clean.**

## The standing instruments — and their paths MOVED

> **THE THREE COMMANDS BELOW USED TO NAME `temp/`. ALL THREE INSTRUMENTS NOW LIVE IN `tools/`** — checked
> by listing, 2026-08-24, and the charter's 5.12 had been carrying the old paths since the promotion.
> `temp/` is gitignored, so a path there is a command that works only on the machine that wrote it.

Run these after editing any of the committable documents:

```bash
uv run python tools/md_tables.py CLAUDE.md FINDINGS-REGISTER.md A3-STRUCTURAL-ANALYSIS.md STEP-B-ANALYSIS.md DECISIONS-LOG.md OPUS-5-MIGRATION.md
```

```bash
uv run python tools/publication_check.py
```

**Before editing `FINDINGS-REGISTER.md`, and after, run its validator** — hand-editing it has produced
quiet errors twice, and two of the validator's checks exist because they caught real ones. Expect
**PASS, 0 failures, 0 warnings**:

```bash
uv run python tools/audit_register.py
```

**And the charter's own continuity check**, which is the only thing that compares the charter's declared
line count with its measured one:

```bash
uv run python tools/verify_charter_continuity.py
```

**`tools/md_tables.py` has caught five defects nothing else in this project can see** — including a
four-column row inserted into a two-column table, and an appendix that lost its delimiter row and stopped
being a table. **The register's own validator passed both.**

## `STEP-B-ANALYSIS.md`'s six suites

After editing it, run all six. They live in `tools/` and are **COMMITTED as of 2026-08-11**, so a fix to
one of them survives the session that makes it.

| suite | what it does |
|---|---|
| `tools/stepb_harvest.py` | 63 prescriptions from five sources, 0 missing |
| `tools/stepb_verify.py` | 84 claims, and it generates the traceability appendix |
| `tools/stepb_audit.py` | 15 checks — **needs `LEGAL_TRANSLATION_A4`, see below** |
| `tools/stepb_audit3.py` | |
| `tools/stepb_metacheck.py` | **eleven negative tests: it mutates the document to prove each check can fail, then restores it byte-identically** |
| `tools/stepb_refute.py` | |

```bash
LEGAL_TRANSLATION_A4="<the sealed directory>" uv run python tools/stepb_audit.py
```

`stepb_audit.py` hard-coded the **sealed A4 judging directory**, whose location section 1.3 of `CLAUDE.md`
deliberately keeps in the private `context.md`. It now reads that environment variable, exactly as
`tools/gate_replay.py` reads `LEGAL_TRANSLATION_LOGS` — **the tool ships, the location does not.**

> **Without it the script exits 1 and prints a banner saying check 10 cannot be completed** — it does NOT
> excuse the quotations it could not verify. **That distinction was got wrong first:** the initial version
> reasoned that a quotation whose only source is unreadable is *void rather than false* and skipped it,
> which looked principled and **immediately dropped `stepb_metacheck.py` from 10 of 10 mutations detected
> to 9.** Softening a check to make it honest had made it blind, which is the failure this project logs
> more than any other — committed here in one of our own instruments, and caught only because the
> metacheck exists. **AN UNREADABLE SOURCE IS NOT A PASS.**

## The four scripts left behind in `temp/`, each for a stated reason

**They were all in `temp/`, which is gitignored, and that was the defect:** the suites guarding this
project's three largest documents could not be improved, because every fix to one of them died with the
session that made it. **A promotion that quietly drops things is worse than none, so the four that stayed
are named:**

- **`temp/audit_session_stepb.py` — BLOCKED ON CONFIDENTIALITY, and it stays in `temp/` permanently.** It
  holds **two corpus subject-matter descriptors**, precisely the class section 5.4 of `CLAUDE.md` says the
  93-pattern name scan is structurally blind to. It is the file a `§`-resolver fix was made in, so **that
  fix does not survive** — the honest cost of the block, recorded rather than worked around.
  ***This one is also listed unconditionally in `CLAUDE.md` 6.4's never-commit list, because forgetting it
  publishes a corpus descriptor and a commit cannot be un-published.***
- **`temp/stepb_audit2.py` and `temp/stepb_audit2b.py`** — both crash looking for a heading deleted in the
  2026-08-05 reorganisation. Broken on `main` today, and one-off session scripts rather than standing
  instruments.
- **`temp/stepb_measure.py`** — three hard-coded register counts that went stale.

**Committing a broken tool into a public repository implies coverage that does not exist**, which is the
same objection this project raises against a check nobody believes. The `temp/` originals are left in
place untouched — *never delete files you didn't create*, section 5.15 — and are superseded by the
`tools/` copies.
