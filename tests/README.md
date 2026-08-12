# The harness

Nothing in the 198 shipped files could demonstrate that any of its own checks fires at all.
This folder is what changes that.

```bash
uv run python tests/run_tests.py
```

Three things, in order: the fixtures build; every executable check is given an input built to
violate its own pass condition **and** a conforming one; and the pipeline's mechanical half is
shown to be a deterministic function.

**Every check is tested with a PAIR.** One-sided testing passes a check that fires on
everything, and a check that cannot tell good from bad is not a check. Three of the fourteen
cases here failed their *clean* arm first — that is the arm that earns its place.

## The branch-5 acceptance test

```bash
uv run python tests/test_checks_can_fail.py
```

Branch 5 is the first branch in step 2 that changes behaviour: runs that used to finish now stop.
Seven changes, each with an input built to make its new block fire **and** a conforming input that
must not — 50 cases, both trees.

**Two of the fifty are labelled `PREDICATE ONLY` and say so in the output.** Neither `testzip()`
nor the case-conflict check can be induced to fail through the repack's own path: the path
normaliser dedups by lowercase so a collision cannot reach the archive, and a write that completes
cannot produce a bad CRC. Those two exercise the predicates against a deliberately corrupted
archive, which tests their logic and not their wiring. **The inducible half of that finding is
tested end to end** — corrupting a member the repack copies through makes the read fail *inside*
the write loop, which is exactly the case that used to leave a partial `.docx` at the delivery
path.

**Section 8 mutates the tree to prove the inverted instrument can still fail**, three ways: the
exit-3 test defeated, the guard call deleted, and the guard call moved back below `__main__`. The
second of those found a real hole — with the call deleted, `quality_check.py` dropped out of the
tool's own population, so its comparison had nothing to compare and reported the chain closed.
Deleting and relocating are kept as separate mutations because deletion proves nothing about
ordering, and the first version of the test used deletion for both.

## `git bisect`

```bash
git bisect start <bad> <good>
git bisect run uv run python tests/run_tests.py --quiet
```

Bisect needs a cheap, deterministic pass/fail test. *"Translate a document and grade it"* is
neither: it takes 20 to 50 minutes, needs a model, and about 40% of paragraphs differ between
two runs of the same document. The suite here is seconds and byte-exact, which is the whole
reason it exists.

## The frozen intermediates

```bash
uv run python tools/freeze_intermediates.py --verify
```

The expensive half of a run is the translation. Mechanically two runs are identical — measured,
on the project's only same-document repeat — so with the translated notes frozen the whole
mechanical half becomes a deterministic function.

**They are never committed.** A frozen intermediate holds a real document's full source text and
its full English text side by side. They stay in the logs folder; `.gitignore` names their shape
by path; `tools/freeze_intermediates.py` catalogues them where they lie and never copies them.
All twelve July runs carry one.

## What branch 1 found on the way

**Eighteen of the twenty scripts carry a verdict of their own.** The two that do not can
neither exit non-zero (other than the integrity sentinel) nor raise, so whatever they print they
cannot stop anything: **`source_language_markers.py` and `translate_numbering.py`.**

> **This read SEVENTEEN, and the third script was `quality_check.py` — the mandatory quality
> gate.** Branch 5 gave it an exit code (register C3), so it now carries a verdict and the
> count is 18. The figure is not edited by hand: `tools/check_coverage.py` derives it, which is
> why it moved on its own when the code did.

> **This figure was published as "13 of 20, reproducing the build plan's thirteen executable
> checks exactly" and that was wrong twice over.** The tool read `sys.exit` calls and nothing
> else, so it missed every script that blocks by RAISING — which is the apply step's entire gate
> mechanism, an uncaught `RuntimeError`. And because the wrong method happened to land on the
> plan's number, it was reported as an independent confirmation of it. **It confirmed nothing.**
> A figure that agrees with the one you expected is the one to re-derive, not the one to relax
> about. Corrected 2026-08-06 by a verification pass; `tools/check_coverage.py` now counts both
> mechanisms and names which scripts use which.

**Exit 3 is the shared integrity sentinel, not a check.** All twenty carry it. Counting it makes
every script look like a validator; the first version of `tools/check_coverage.py` reported
20 of 20 and said nothing.

**Five of the seventeen pipeline steps have no check that can block** — setup, the host-mode
warning, cross-references, auxiliary files, and the final validate. A failing input cannot be
built for any of them because there is nothing to give it to. That is a declared blind spot,
not an oversight: `tools/check_coverage.py` prints it every run.

> **This number survived the correction above, and it is worth knowing it did so by luck.** The
> first method (counting the integrity sentinel as a check) said 5. The half-corrected method
> (sentinel excluded, raises still missed) said **9**. The fully corrected method says 5 again.
> Two errors cancelled. The list is the same one in the first and third runs — but "the number
> did not move" is not evidence a method is sound.

**Both predicted failure chains were real in execution, and branch 5 CLOSED both** —
`tools/confirm_failure_chains.py`. Apply restricted blocking to exit code 2 at both call sites,
so a validator reporting a truncated install was ignored; and `quality_check.py` invoked its
integrity guard below its `__main__`, the only one of the twenty scripts placed that way.

> **THAT TOOL'S QUESTION INVERTED, and the inversion is the interesting part.** A tool built to
> prove a defect is real FAILS the moment the defect is repaired. It now asserts the repair and
> keeps failing if either chain reopens, which makes it the standing regression guard on both
> fixes rather than a historical note. Its four truncation controls were deliberately left
> untouched: after a repair, they are what distinguishes a caller that now respects the
> detection from a fix that quietly disabled it.
>
> **And chain 1 had to stop using a proxy.** It asked whether `3` appeared in apply's
> `block_codes` sets — sound while that was the only mechanism, wrong afterwards, because the
> fix blocks exit 3 in an explicit test *before* `block_codes` is consulted. The sets still omit
> 3, so the proxy still reported the defect as live. It now drives the real helper with a probe
> that exits 3.

**A refinement, corrected.** A truncated script is always caught, but by two mechanisms and only
one explains itself: where the truncated file still **compiles** the guard runs and exits 3 with
a diagnosis, and where it does not, Python raises `SyntaxError` and exits 1 before the guard is
reached — wherever the guard sits. **Which of the two you get depends on where the cut lands in a
particular file, not on how deep it is.** This README previously said deep cuts trip the guard
and shallow ones do not; that is true of `extract_paragraphs.py` and the **opposite** is true of
`quality_check.py`, so the earlier text generalised from one file. Safety is unaffected either
way — nothing runs. What differs is whether the message names the cause.

**Moving the guard repaired a documented diagnostic, measured across every cut point that still
compiles: 0 of 29 fired before, 31 of 31 after.** `skill-docs/08-aux-and-quality.md` tells the
operator to run `quality_check.py --help` to see whether the guard fires. From below `__main__`
that could never work, because argparse handles `--help` and exits first.

**`verify_diligence.py` returned `1 if strict else 0` for WARN**, so without `--strict` a warning
was indistinguishable from a pass — and *with* it a WARN became 1 rather than the documented FAIL
code, so one line contradicted both the exit-code table above it and the flag description below
it. The blind desk review found this by tracing the code; `tools/check_coverage.py` reproduced it
mechanically. **Branch 5 changed it to `2 if strict else 1`**, and that tool now asserts the
contract instead of prescribing it, so a revert shows up as a failure rather than as advice.

**A portability defect, environment-dependent and worth recording.** On Windows with a
redirected stdout, `verify_diligence.py` dies with `UnicodeEncodeError` before it can return a
verdict — cp1252 cannot encode `≤`, and that character appears only on the **passing** path, so
the audit crashes exactly when everything is fine. The skill's real host is Linux under UTF-8, so
this is the harness's problem to solve and it does (`PYTHONIOENCODING=utf-8`). It is written down
because it is genuine and because it cost an hour: the crash exit read as *"the check fires on a
clean input"*.

## Writing a new case

Add it to `tests/negative_inputs.py`. Return `(violating_input, conforming_input)`.

**If your new test touches a skill script, set BOTH bytecode guards.** Running or importing one
drops a `__pycache__` directory inside `uk/scripts` or `us/scripts`. It is gitignored so it never
reaches a commit, but it would be packaged into a `.skill`, which is why
`tests/test_instruction_rules.py` checks for it.

```python
sys.dont_write_bytecode = True                    # for an in-process import
env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")   # for a subprocess
```

**Both, and the first is the one that gets forgotten.** This hazard has now arrived through three
separate callers: fixed in `run_tests.py`, back through `tools/audit_branches.py`, back again
through `tests/test_checks_can_fail.py`. The first two only ever spawned subprocesses, so the env
var was the whole fix and became the remembered one — an in-process import ignores it completely.
It is written here rather than left to be rediscovered because a fix scoped to one caller of a
shared hazard is this project's most-repeated failure shape.

**Take the schema from a frozen intermediate, not from the step documents.** Four of the
fourteen cases here were wrong first time because the schema was guessed: `en_segments` uses
`type`, not `kind`; `en_runs` are `{start, end, bold}` offsets, not copies of the text; a
paragraph is only examined for tracked changes when it declares them; and the definitions
detector needs a recognised heading **plus at least three** predicate-shaped paragraphs. Each
wrong guess produced a check reporting `PASS: all 0 paragraphs` — a pass over an empty set,
which is the classic shape of a check passing for the wrong reason.

**Every fixture is invented.** No fixture derives from a real document and none may: anonymising
one still leaks its shape, its clause structure and its commercial terms, and renaming is not
enough. Four things can only be tested synthetically — the corpus contains no `Symbol` or
`Wingdings` run anywhere, and no content control, smart tag, image with alt text or chart with a
title.
