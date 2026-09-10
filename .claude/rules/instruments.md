---
paths:
  - "tools/**/*.py"
  - "tests/**/*.py"
---

# Measurement and instrument conventions

Relocated from `CLAUDE.md` §5.5 on 2026-09-10 under route 4: these matter only when writing or using a
measurement instrument or a fixture, so they load when `tools/` or `tests/` is touched rather than every
session. The instrument STATE (grader version, harness version, thinking level) stays in §5.5, because a
session needs to know it without opening a tool.

## The seven measurement rules — each generalises beyond the grader

- **Never score any run property from element counts — compare the affected TEXT, then render.** Translation
  consolidates runs, so nearly every count falls even when nothing is lost, and it fails in both directions:
  putting the English back emits an explicit *off*-flag on every non-emphasised run.
- **Count auxiliary REFERENCES, not just auxiliary parts.** A translated footnotes part whose pointer was
  destroyed is unreachable, and the part-inventory check passes.
- **Compare auxiliary part CONTENT, not the inventory.** Empty footnote and header parts exist as
  boilerplate in any Word-written `.docx`.
- **Render BOTH documents and compare page against page.** Inspection finds what looks wrong; only
  comparison finds what is *missing*.
- **Reconcile any tracked-change count drop** against legitimate coalescing before calling it loss.
- **Identical paragraph properties are not evidence that layout survived.**
- **Never compare properties BY PARAGRAPH INDEX across the definitions block** — that step permutes it. Match
  definitions **by term**.

## Forensic logging is a primary method, not a nice-to-have

When observing the skill on a real document, log **everything** — every file read, tool call, reasoning
step, gate firing, wasted call and iteration loop, every ambiguous instruction, plus per-step token and time
cost. **A summary is not a log.** Every real fix in the rev16→rev44 history came out of it. **Take counts
from the log analyser, never from the narrative** *(the figures are `EVIDENCE-measurement.md` section 3.2)*;
narratives remain the only source for *reasoning*.

## The two reasons a corpus cannot reach a defect

A synthetic fixture is needed when either holds, and a zero read as *already fixed* is the defect both
produce:

1. **The corpus does not CONTAIN the shape** — measured both ways, e.g. the one corpus `w:smartTag` is gone
   from the copy the pipeline applied to, removed upstream at conversion or re-save, so the row closes on the
   synthetic fixture alone and that must be DECLARED.
2. **The corpus CANNOT contain it, because a gate removes the shape before anything is recorded** — e.g. an
   `en_runs` offset past the end of `en`: `validate_en_runs.py` runs BEFORE apply, so a run carrying one
   could never have produced a frozen intermediate. Measured 0 across all 13, the zero PROVED (729 of 729
   offsets landing on `len(en)`, a planted needle firing). The evidence base is clean BECAUSE the gate
   worked. **The test before believing any zero: ask whether the artefact you are counting could physically
   have recorded the thing you are counting.**

**Three things the corpus cannot reach, so they need synthetic fixtures:** no `Symbol` or `Wingdings` runs
anywhere (the Greek-glyph defect); content controls, smart tags, images with alt text and charts with titles
appear in none of the eleven; and only ONE document has a table of contents, so any TOC measurement is of
D06's house style. A synthetic sweep found two real defects the corpus was structurally blind to on its
first run; `tests/test_toc_shapes.py` owns that population.
