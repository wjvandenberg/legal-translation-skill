---
name: frozen-intermediate-test
description: How a change to this pipeline is actually tested - freeze the translated intermediate from an existing run so the whole mechanical half becomes a deterministic function, plus the two fixture tiers, the blind spot the trick does not announce, and the mandatory negative inputs. Use when planning or running a branch's TEST stage, building a fixture, deciding whether a change needs a graded run, or making git bisect possible. Relocated from CLAUDE.md 5.8 under route 3 on 2026-08-24.
---

# How a change is actually tested

**Section 4 of `STEP-B-ANALYSIS.md` owns the method per branch kind. This is the principle behind it,**
and `CLAUDE.md` 5.8 keeps the standing rules and points here.

## THE TRICK: FREEZE THE TRANSLATED INTERMEDIATE FROM AN EXISTING RUN

The expensive, non-repeatable part of a run is the translation — a model, 20 to 50 minutes, and 40% of
paragraphs differing between two runs. But **mechanically two runs are identical, and that is measured**,
not assumed: it is the project's only same-document repeat, and the mechanical output was byte-identical
while about 40% of paragraphs differed linguistically.

So with the translated notes frozen, **the whole mechanical half — put the English back, tidy up,
reorder, auxiliary parts, repackage — becomes a deterministic function.** Run the scripts, compare the
bytes. **Seconds, repeatable, no model, no Cowork.** The frozen intermediates already exist from the July
runs; `tools/freeze_intermediates.py` is the instrument.

**This is what makes `git bisect` possible**, which is the standing method for a regression *(section 2.6
of `CLAUDE.md`, 2026-07-29)*. Bisect needs a cheap deterministic pass/fail test, and *"translate a
document and grade it"* is neither.

## The two tiers — and the distinction is a confidentiality requirement, not a convenience

| tier | what | committable? | when it runs |
|---|---|---|---|
| **Synthetic** | hand-built documents with no client text, in `tests/fixtures/` | **YES** — these are what runs on every change and what `git bisect` uses | every commit |
| **Real, frozen** | the frozen intermediates from the eleven corpus documents; they contain the **full client text** | **NEVER.** They live with the logs, outside the repo, and are excluded **by path** | before every merge |

**The never-commit half of that table also lives unconditionally in `CLAUDE.md` 6.5 and 5.4**, because
forgetting it publishes client text and there is no un-publishing. If this page and the charter ever
disagree about what may be committed, **the charter wins.**

## AND THE TRICK HAS ONE BLIND SPOT, WHICH IT DOES NOT ANNOUNCE

A frozen intermediate is the **post-compliance** artefact — the `paragraphs.json` the run left behind
*after* its gates were satisfied. **So it cannot reproduce a gate that was satisfied while the run was
happening**, and a check that leans on it reports a clean sweep over the very cases the gate already
fixed.

**Measured on 2026-08-21: `validate_segment_shapes` finds 0 findings over 81 tracked-change paragraphs
on the whole recorded corpus.** That is not a clean corpus; it is a blind instrument.

**A frozen-intermediate result is evidence about the mechanical half only.** Say so when reporting one —
a result presented without that qualifier reads as coverage of the run, which it is not.

## Negative test inputs are mandatory, not optional

Nothing in the shipped package can currently make a check fail, so **a fixture set of only-passing cases
produces tests that pass because nothing is being tested.** **One input per check, built to violate that
check's stated pass condition.** `tests/negative_inputs.py` and `tests/test_checks_can_fail.py` are where
they live.

**A check meant to catch a known defect must reproduce that defect on its first run.** If it passes
immediately, it is not built correctly — that is section 5.1's Verify condition, and it is unconditional
in the charter rather than here.

## And for any change claimed to be non-behavioural, PROVE IT

SHA-256 compare the affected files and byte-compare pipeline output on the fixtures. **Never delete that
discipline in the name of tidying up** — it is what makes bisect work.

## Two traps that make a green run meaningless

- **`tests/make_fixtures.py` run as a captured child was measured to KILL ITS PARENT**, which is how a
  fixture set came to be half-deleted while the build returned 0. Run this project's suites as
  **top-level commands**, never from a parent runner.
- **The suites share `tests/fixtures/` and rewrite it**, so anything run alongside a sweep invalidates it
  and is invalidated by it. A foreground suite once caught a fixture mid-write and died with
  `BadZipFile`, which reads exactly like a corrupt document rather than a race.

*(Both are section 5.16's rule 5 and stay in the charter unconditionally; they are repeated here because
this is the page somebody reads while about to run a suite.)*
