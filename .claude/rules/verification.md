---
paths:
  - "tools/**/*.py"
  - "tests/**/*.py"
---

# Verification hygiene — the ways a check passes for the WRONG reason

Relocated from `CLAUDE.md` §5.3 on 2026-09-22 under route 4: each of these bites when you are writing or
running a check, so they load when `tools/` or `tests/` is touched rather than every session. **The general
verification-hygiene list is in the auto-loading house file and is not restated here.** These five have no
twin there — each is a check that passed in THIS project for the wrong reason. The worked examples and the
dated instances are `EVIDENCE-measurement.md` section 3's.

**None of these is irreversible if forgotten**, which is the test §5.8 rule 2 sets for what may sit behind a
scoped rule at all: a check that passes for the wrong reason produces a wrong verdict, and a wrong verdict is
re-taken. Anything whose absence cannot be undone stays in the charter.

## The five

1. **Run this project's suites as TOP-LEVEL commands, never from a parent runner**, and make a before/after
   suite exit VOID when the baseline is byte-identical to the working tree. A suite invoked from a wrapper
   reports the wrapper's exit code, and a self-comparison reports 100% carried.
2. **Ask whether a claim asserts a HISTORICAL DELIVERY or a LIVE INVENTORY.** A historical claim may read
   `main`; a live one must read the INDEX. One measuring itself against `main` is green on the very branch
   that breaks it and red only after the merge. **The sweep of the other claims for this shape is not done.**
3. **A reader that normalises its input cannot see a change in what it normalised away** — and the reader is
   usually shared between the two sides of the comparison. Ask of any comparison what the function you
   compare WITH throws away; **the fix is a second reader, never a changed one.**
4. **A directional "did the fix fire?" check must FAIL, not go quiet, when its premise stops holding** — a
   self-comparison, a fix already present in the pinned baseline, an unwired new arm. Assert what must be
   TRUE for its question to still be open; `git merge-base --is-ancestor` settles the pinned-baseline case.
5. **A check that reads its subject independently must honour the same text contract**, or it reports its own
   semantics as a defect. State the contract once, restate it deliberately, and let a test assert both obey it.
