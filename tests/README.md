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

**Thirteen of the twenty scripts carry a verdict of their own.** Reproduced independently and it
matches the build plan's figure exactly. The other seven can only ever exit 0 or 3 — whatever
they print, they cannot stop anything, and they include the mandatory quality gate and the
repackager.

**Exit 3 is the shared integrity sentinel, not a check.** All twenty carry it. Counting it makes
every script look like a validator; the first version of `tools/check_coverage.py` reported
20 of 20 and said nothing.

**Five of the seventeen pipeline steps have no check that can block** — setup, the host-mode
warning, cross-references, auxiliary files, and the final validate. A failing input cannot be
built for any of them because there is nothing to give it to. That is a declared blind spot,
not an oversight: `tools/check_coverage.py` prints it every run.

**Both predicted failure chains are real in execution** — `tools/confirm_failure_chains.py`.
Apply restricts blocking to exit code 2 at both call sites, so a validator reporting a truncated
install is ignored; and `quality_check.py` invokes its integrity guard at line 918, below its
`__main__` at line 855.

**A refinement the plan does not carry, found by running rather than reading.** A truncated
script is always caught, but by two mechanisms and only one explains itself. Cut deeply (50%,
75%) the guard runs and exits 3 saying the install is truncated. Cut shallowly (90%, 99%) the
file no longer compiles, so Python raises `SyntaxError` and exits 1 before the guard — near the
top of the file — is ever reached. Safety is unaffected. What the user gets differs completely:
a diagnosis, or a traceback. **And the shallow cut is the likelier one**, because it is what an
install that almost finished produces.

**`verify_diligence.py` returns `1 if strict else 0` for WARN**, so without `--strict` a warning
is indistinguishable from a pass. The blind desk review found this by tracing the code;
`tools/check_coverage.py` now reproduces it mechanically, so it stays true.

**A portability defect, environment-dependent and worth recording.** On Windows with a
redirected stdout, `verify_diligence.py` dies with `UnicodeEncodeError` before it can return a
verdict — cp1252 cannot encode `≤`, and that character appears only on the **passing** path, so
the audit crashes exactly when everything is fine. The skill's real host is Linux under UTF-8, so
this is the harness's problem to solve and it does (`PYTHONIOENCODING=utf-8`). It is written down
because it is genuine and because it cost an hour: the crash exit read as *"the check fires on a
clean input"*.

## Writing a new case

Add it to `tests/negative_inputs.py`. Return `(violating_input, conforming_input)`.

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
