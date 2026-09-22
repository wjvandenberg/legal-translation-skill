---
paths:
  - "uk/**"
  - "us/**"
  - "tools/**/*.py"
  - "tests/**/*.py"
---

# Gate philosophy and error handling — do not weaken this

Relocated from `CLAUDE.md` §5.7 on 2026-09-22 under route 4: these govern how a pipeline gate behaves and
how an operator meets it, so they load when a variant tree or a tool is touched rather than every session.

**None of these is irreversible if forgotten**, which is the test §5.8 rule 2 sets: working around a gate
produces a bad translation, and a bad translation is re-run. **The rules whose loss cannot be undone — the
confidentiality set — are route 1 and stay in §5.6 of the charter, unconditionally.**

- **A gate firing is the script doing its job.** Never work around one — no patch to the script, no override
  flag, no Python wrapper, no skipped validator. **Fix the input and re-run.**
- **Never alter a source-faithful translation to satisfy a linter** — where a QC finding conflicts with
  fidelity, **fidelity wins and the linter gets fixed.**
- **A gate CAN be wrong in SCOPE**, and the skill's own language discourages that conclusion, so operators
  improvise. **The remedy is to fix the gate where the operator meets it, never to bypass it** — the cheapest
  fix in the project, and it makes every scoping defect recoverable.
- **A heuristic check degrades to a confident wrong answer, never to nothing.** Validate against ground
  truth, and make it announce that it is guessing rather than print CLEAN for a language it cannot support.
- **Script-integrity failure means a corrupted install** — stop and reinstall, never work around it.
