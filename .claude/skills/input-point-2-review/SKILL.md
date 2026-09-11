---
name: input-point-2-review
description: The per-document review protocol for INPUT POINT 2 - how Wouter's blind review of the 11 Step C documents is run, the three-way triage per point, the two artefacts and where they may live, the blind rule, and what Claude must not do. Use when running or preparing INPUT POINT 2, when Step C's graded documents come back for review, or when any blind review of translated output is being set up. Relocated from CLAUDE.md 5.4 under route 3 on 2026-09-11, at THE CHARTER REDUCTION part (e) - the official trigger applies word for word: a section of CLAUDE.md that has grown into a procedure rather than a fact.
---

# The review protocol — for INPUT POINT 2

**Kept because Step C repeats it.** `CLAUDE.md` 5.4 keeps the trigger and points here. This is a procedure
run at one moment, not a fact that must hold every session — which is why it lives here and not in the
charter.

## Why this is a procedure and not a rule

There are **exactly two input points** in this project, and 1 is closed (Wouter's blind review of all 12
A1+A2 documents, CLOSED 2026-07-31). **INPUT POINT 2 is his review of all 11 Step C documents**, and it
happens once, at step 3, after the build. The charter keeps *that* fact — the order and the count — because
order is what section 3 owns. Everything below is how the session is actually run on the day.

## The loop, per document

- A helper opens the original and the translation **side by side, read-only, with no filename typed** — the
  test corpus filenames alone carry counterparty names, so typing one into a transcript is a leak no scanner
  can reach afterwards.
- **Wouter gives input in any shape; Claude structures it.** He is not required to produce findings in a
  format.
- **Open the NEXT pair immediately on his feedback**, so he reads document n+1 while Claude analyses n.
- **But finish n's analysis and update the register before the next feedback lands**, running
  `uv run python tools/audit_register.py` after each edit. A backlog of unanalysed feedback is how a point
  gets silently dropped.
- **Order: ascending complexity.**
- **The D03/D03B pair is reviewed together and NOT blind** — batch position is the only variable between
  them, so blinding it would destroy the one controlled comparison the corpus has.

## The three-way triage, per point

| the point was | what to do |
| --- | --- |
| **already reported** | tick the row in `evidence/REGISTER-findings.md` |
| **missed, but the method COULD have caught it** | fix the method, then **re-check the earlier documents** with the fixed method |
| **missed, and it STRUCTURALLY could not** | record it — **expect most findings here**, the translation criterion being graded on a sample, and **that axis is Wouter's alone** |

## The two artefacts, and where they may live

- **Wouter's raw feedback and Claude's per-document analysis go to the logs folder and are NEVER committed**
  — they carry real clause text and real names.
- **Only sanitised conclusions enter the register**, origin `WvdB`.

*(The location rule is the charter's 5.6 and is not restated here: raw forensic material lives entirely
outside the repository, and only derived work is committed.)*

## THE BLIND RULE

**Wouter forms his view before reading the grade.** Claude must not summarise the grade, or hint at findings,
before he has given his. **Any tool touching a blind review inherits the blindness** — if a script would
print a grade beside a document, it may not be run here.

## What Claude must NOT do

- **Do not defend the grade.**
- **Do not modify the read-only documents.**
- **Do not start fixing the skill** — this is a measurement, and fixing mid-measurement destroys it.
- **Do not look at a rendered page of a corpus document.** A render is client text as an image; a
  page-by-page read of a real document is Wouter's alone *(charter 5.6)*.
