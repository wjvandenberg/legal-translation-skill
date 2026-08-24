# EVIDENCE-confidentiality.md — how the confidentiality controls were built, and what they caught

**This document owns the DATED EVIDENCE behind §5.4 of `CLAUDE.md`. It does not own a single rule.**
Every rule stayed in the charter, deliberately and under route 1: a confidentiality rule that is absent
when it is needed means a publication that cannot be undone, and this document is read on entry to a
confidentiality question rather than every session. **Where this document and the charter appear to
disagree, THE CHARTER WINS** — and the disagreement is a defect to fix here, not a judgement call.

> **WHY THIS DOCUMENT IS THE MOST DANGEROUS FILE IN THE REPOSITORY, and it is worth saying at the top.**
> **An evidence document about leaks is the likeliest thing in the repo to contain one.** So it was
> assembled, **scanned, and only then committed** — never created and committed in one movement. The
> controls that were run over it before its first commit are recorded in section 6 below, with what they
> read, because a clean report from a control that could not reach the file is not a pass.

**Created 2026-08-24, phase 3c step 9 of the charter reduction.** It receives ~170 lines from §5.4, which
was **202 lines — the largest single block in the charter**, and the reason the whole reduction was
ordered cheapest-first.

---

## 1 — The naming rule's measurement: why a name scan is structurally blind

**The rule is §5.4's and stays there:** name a test document by its instrument class and its language and
by nothing else. This is the measurement that made it a rule *(Wouter, 2026-08-06)*.

**The 93-pattern scan reported 0 hits on every one of the subject-matter qualifiers this project had been
using — correctly, because none of it is a name.** A qualifier is the noun that says what an agreement is
*over*, what a guarantee is *for*, what a deed *conveys*. Plus a language plus a date range, it identifies
a real instrument **far more sharply than a name does**, to anyone who knows the market.

**It is the same class of leak as the commercial terms found in July, and it got the same two-control
answer:** a blocking probe in `tools/publication_check.py`, and `tools/descriptor_shape_sweep.py`, which is
**list-free and found four that the term list had missed.**

> **AND THE FIRST VERSION OF THAT PROBE CARRIED THE QUALIFIERS INLINE, so the probe fired on the rule that
> described it.** It was right to. The qualifiers live with the scan list in the private sibling folder;
> the probe reads them by path or from an environment variable. **Enumerating them in a committable file
> would publish exactly what the rule protects** — the same reasoning that keeps the name list outside the
> repository.

---

## 2 — The transcript leak, 2026-08-11, and the control that had to run BEFORE the command

**A session ran `ls` and `find` over the sibling logs folder to learn its layout, and the output printed
real corpus filenames carrying counterparty and personal names INTO THE CONVERSATION.** Nothing was
committed and nothing could be: **the leak never touched a file.**

**Every control this project has reads committed content.** §6.5 of the charter already says session
metadata is reachable by neither the scanners nor the location rule — so there is **no after-the-fact
remedy at all**, and it cannot be un-said.

**THE RULE EXISTED AND WAS BROKEN ANYWAY.** §6.5's *"any glob over an evidence folder must be explicit
about which files it expects"* had been read that same morning. **That is §5.1's argument restated: prose
is not a control.**

**So the control runs BEFORE the command.** `tools/hooks/evidence_guard.py` is a `PreToolUse` hook wired in
`.claude/settings.json`. It blocks a name-emitting command — `ls`, `find`, `tree`, `cat`, `Get-ChildItem`,
or inline code that enumerates a directory — whose target is an evidence folder.

**THE HAZARD IS OUTPUT, NOT ACCESS.** A script that reads those logs and prints counts is exactly what
`tools/gate_replay.py` does and still runs, as does the register validator. `tools/evidence_ls.py` is the
sanctioned way to see a folder's **shape** — extensions, size buckets, per-directory counts, corpus doc-ids
— and **it prints no name, ever.** *(A block with no alternative gets worked around, and then you have a
control nobody believes.)*

**Two limits, and they stay stated in the charter too because forgetting either is what the guard exists
to prevent.** Hooks load at **session start**, so the guard does not protect the session that adds it —
probe it with a command naming a directory that does not exist under an evidence folder, which is BLOCKED
if the guard is live and harmlessly reports a missing directory if it is not. And the **test-document
folder is not named in the guard**, because its name is not committable; it is read from
`.claude/evidence-dirs.local`, which is gitignored, so **in a fresh clone that folder is unguarded until
someone creates that file.** Same shape as the scan list: the scanner ships, the list never does.

> **NARROWED 2026-08-24, and the bug is worth keeping.** The guard held the bare folder name `skills`,
> matched as a plain substring, so it blocked **every command containing that word** — including
> `.claude/skills/`, which is the only place Claude Code finds a project skill, and which route 3 of the
> reduction needed. Narrowed to a path fragment under both separators and proved on both arms, 8 of 8: the
> archive still blocked, the destination free.

---

## 3 — The three controls, and the suppressor that hid a real finding

**The rule — run all three on every committable file before any commit — is §5.4's.** This is what each
one cost to get right.

### 3.1 The name-and-term scan, and why it is not sufficient alone

**93 patterns, every one with a test vector.** It was proved insufficient when an audit found **the
operative commercial terms of real client instruments in two committable files**: the scan reported 0 hits,
correctly, because none of it is a name. Hence the standing instruction to **genericise commercial terms in
committable prose** — *"the seven-figure guaranteed amount"*, *"a three-digit two-decimal figure with a
comma decimal separator"* — which preserves every analytical point without the value.

### 3.2 The shape-based sweep

**List-free.** Non-ASCII tokens, capitalised multi-word sequences, money and capacity figures,
identifier-shaped strings, filenames, absolute paths, long quoted strings. **Everything it prints is a
candidate for human judgement, not a hit.**

### 3.3 The publication check, and the filter that suppressed a real hit

**`tools/publication_check.py` asserts the specific forbidden classes and FAILS rather than listing.**

> **Its regex-metacharacter filter used to suppress one real hit** — a home-relative path, because the path
> contains a backslash followed by a capital D and the filter read that as a quoted regex. **It reported
> four findings of five and said nothing about the fifth.** Narrowed and given seven test vectors on
> 2026-08-06 — `temp/test_pubcheck_suppressor.py`. **A check that suppresses a real finding for the wrong
> reason is the failure class this project keeps logging**, and it is why every pattern needs a test vector
> next to it.

### 3.4 BOTH LIST-READING CONTROLS WERE BLIND TO `.claude/`, FOUND 2026-08-24

`publication_check.py` and `descriptor_shape_sweep.py` each carried **six hard-coded filenames**, written
before `.claude/rules/` and `.claude/skills/` existed — and `descriptor_shape_sweep` **silently ignored the
argument it was given**, reporting on `CLAUDE.md` when pointed at a new `SKILL.md`. **The blocking one is
the worse of the two: a file it does not open is a file that cannot fail it, and the output is
indistinguishable from coverage.** Both now discover by glob, honour an explicit list, **print what they
read**, and exit 2 as VOID on an empty set. Proved by planting a probe file carrying three blocking
classes: 14 files read, 3 blocking findings, exit 1; probe removed, 13 files and 0 findings.

### 3.5 Two list-maintenance rules, both learned the hard way

*(The rules stay in §5.4. These are the incidents.)* A bank-name pattern written with a literal space
**silently failed against a document containing a doubled space** — and **a missed name is invisible: the
scan simply reports clean.** And in Python, a word-boundary pattern written in a non-raw string literal
becomes BACKSPACE + the word + BACKSPACE and **will never match** — which is why every pattern must be
tested against the string it was written for, in the same commit.

---

## 4 — Which files may never be committed: the 90-script measurement

**The deciding rule is §5.4's** — not *"is this a script?"* but ***"does this file hold one real string per
pattern?"*** — which is why a scanner is publishable and the list it reads never is.

**Re-measured across all 90 scripts on 2026-08-06** (`temp/script_committability.py`, which runs the same
probes over the code that the publication check runs over the prose): **69 are clean and 21 hold a real
string.** The 21 fall into four kinds, and **only the first was on the old list:**

1. **The lists and their test vectors** — the name list, the corpus-descriptor list, and the pattern-test
   file, which holds one real string per vector *by design* and is therefore exactly as sensitive as the
   list itself.
2. **The two workspace-building scripts** that map document ids to real corpus filenames.
3. **The replacement scripts** written to apply a genericisation. A counted replacement has to carry the
   *before* text, so **a script that removes a real string necessarily contains every one it removed.**
4. **One-off measurement scripts with a hard-coded local path** — the A3 and A4 tooling. They were never
   destined for `tools/`; they are named so nobody assumes otherwise.

> **THREE OF THE SCRIPTS INTENDED FOR `tools/` WERE CAUGHT BY THIS AND FIXED THE SAME DAY**, and the way
> they failed is worth more than the fix: **each had quoted a real string inside an explanatory COMMENT.**
> The publication check's own comment quoted the home-relative path it exists to block, and the list-free
> descriptor sweep illustrated itself with two real qualifiers. **A COMMENT SHIPS. AN EXAMPLE IN A
> DOCSTRING IS PUBLISHED PROSE.** Invent the examples. *(That rule stays in §5.4.)*

> **AND ONE FILE IS WITHHELD BY JUDGEMENT RATHER THAN BY PROBE.** *(Wouter, 2026-08-06: "I don't want
> confidentiality review to be committed.")* `temp/confidentiality_review.py` is clean on every probe, and
> it still does not ship: it sets out which shapes we scan for **and which candidates we accept**, which is
> a map of what gets waved through. **A probe cannot see that class of exposure**, so the never-commit list
> is a floor and not a ceiling — **read a script and ask what it reveals about the CONTROL, not only what
> strings it holds.** *(The four files themselves are listed in §6.4, which is route 1.)*

---

## 5 — The three things that were open at branch 0

**(a) and (c) are CLOSED. (b) is still open, and it is the only live item in this document.**

### 5.1 (a) — CLOSED 2026-08-07. The two published trees were scanned, read, and cleaned

**The scan hit 46 files per tree, identically in both** — overwhelmingly false positives from short
patterns matching ordinary Dutch, Polish, Hungarian, Finnish, French and German legal vocabulary inside the
sub-lexicons, **plus one pattern derived from a filename whose first word is itself a common legal term,
which alone accounted for 26.**

**Four items were real, all already public, so cleanup rather than containment.** Two were replaced:

- a worked example in a shipped script built from **two real people's names taken from real source
  documents**, where **renaming had never been applied at all**; and
- **named outside law firms in the always-loaded file's prose.**

Two were kept by Wouter's decision:

- the author's email, **with his LinkedIn added beside it**; and
- the **firm heading-style patterns in `reorder_definitions.py`, which are FUNCTIONAL** — they are what
  lets the skill recognise those firms' heading styles in a real document, so deleting them removes
  capability rather than a reference. **Capability over disclosure, decided knowingly.**

### 5.2 (b) — STILL OPEN: the scan list needs tightening before it is a pre-commit gate

**Its false-positive rate against the skill trees is high enough that a reviewer will start skimming**,
which is the exact failure mode this project has already diagnosed in the skill's own validators. **A
control nobody believes is not a control.**

**Partly mitigated:** the gate separates the trees from everything else, and the pre-flip triage splits
matches into ALREADY PUBLIC and NEW EXPOSURE — the cut that makes 715 hits readable. **The list itself is
unchanged.**

> **SUBSTANTIALLY MITIGATED 2026-08-11 — THE GATE NOW SCANS THE TREES, BY DIFF.** Separating the trees out
> meant `tools/precommit_gate.py` did not look at `uk/` or `us/` **at all**: it counted their files and
> stopped. Defensible while no branch changed them; branch 4 changes eight files, and branches 6, 7, 16 and
> 17 will change far more. **A confidentiality gate blind to the two directories that actually ship is the
> wrong blind spot to keep.**
>
> **The fix is to judge only what a branch INTRODUCES.** Its section 7 diffs `uk/` and `us/` against
> `origin/main` (override with `LT_TREE_BASELINE`) and runs three controls over the **added lines only** —
> the 93-pattern name scan, the 13 corpus-descriptor patterns **applied as regex and never `re.escape`d**,
> and the publication check's forbidden classes. **The pre-existing false positives sit in the baseline and
> cancel out.**
>
> **Measured on branch 4: the eight whole files give 6 hits; the 102 added lines give 0.** Same evidence,
> and the second is readable. **It reports VOID and refuses to certify when it cannot resolve a baseline**
> — a control that established nothing has not passed. `tests/test_gate_tree_scan.py` plants a leak of each
> class into a tree file and asserts the gate blocks on every one, then asserts the tree is byte-unchanged
> afterwards.

### 5.3 (c) — CLOSED THE DAY IT WAS FOUND. The changelog is not committed and `docs/history/` does not exist

*(Wouter, 2026-08-06: "Changelog should NOT be on commit list… Docs/history should never be committed.")*

**The recovered rev16→rev44 changelog sat on the commit list and had never been scanned, because it is not
a file yet** — it is recovered from the `CHANGELOG.md` inside the archived `.skill` revisions, and **an
artefact that does not exist cannot be scanned.**

**Measured on 2026-08-06** (`temp/changelog_confidentiality.py`): **four name-shaped patterns matching 69
times, one a multi-word proper name**, plus **three corpus descriptors**, a company-form suffix, two
capacity figures and three document filenames — **rising monotonically by revision, from 10 hits in the
earliest to 32 by rev20**, which is what a working log kept while translating real documents looks like.

**Not a defect in the archive; a defect in the plan.** Closed the clean way rather than by sanitisation:
**the changelog stays in the archived revisions, outside the repository, where it already was.** It did its
job as an input to the structural analysis and the build plan, and **nothing downstream needs it** — every
lesson it carried is already in §5 of the charter, sourced and dated.

### 5.4 On credentials and history

**This project has no credentials at all** — the skill authenticates against nothing — so that rule is
preventative and **the live risk is client names and document content.** *(The standing rules —
`.gitignore` prevents accident and is not a security control; a leaked client name cannot be rotated;
making a repo public exposes the whole history — are all §5.4's and stay there.)*

**History *can* be rewritten, but it needs a force-push, which our own branch protection blocks, and after
a repo has been public it is no longer a remedy** — forks and scrapers may already hold the content.

> **A SUPERSEDED OBSERVATION, KEPT BECAUSE IT WOULD MISLEAD IF IT STAYED IN THE CHARTER.** §5.4 carried,
> until 2026-08-24, a block headed *"THE GOOD NEWS: THERE IS NO HISTORY TO SCAN — nothing has ever been
> committed."* **That was true before `git init` on 2026-08-06 and has been false ever since.** The
> repository exists, it has been PUBLIC since 2026-08-07, and its whole history is served. A session
> reading that block today would conclude there is no history exposure, which is the opposite of the
> position. **It is recorded here as a dated, superseded observation and must not be quoted as current.**

---

## 6 — This document's own confidentiality review, run BEFORE its first commit

**Prohibition: it must not create the evidence document and commit it in one movement.** Assembled,
scanned, then committed. **A clean report from a control that could not reach the file is not a pass, so
what each control READ is recorded, not merely its verdict.**

| control | what it read | result |
|---|---|---|
| `tools/leakage_scan.py` | **93 patterns live** *(it exits 2 when the list is unreadable, so the count is the proof the control ran)*, this file named explicitly | recorded in the commit |
| `tools/publication_check.py` | this file, via the glob widened the same day so `EVIDENCE-*.md` is discovered automatically | recorded in the commit |
| `tools/descriptor_shape_sweep.py` | this file, list-free — every candidate reported for judgement | recorded in the commit |
| a reading | the whole file, for the class no probe can see: what it reveals about the CONTROL rather than what strings it holds | recorded in the commit |

**Nothing in this document names a client, a counterparty, a person, a subject-matter qualifier, a corpus
filename, an email address or an absolute path.** Where a real string was the *source* of a lesson, **the
lesson is here and the string is not** — *"two real people's names taken from real source documents"*,
*"named outside law firms"*, *"the operative commercial terms"*. That is §5.4's rule applied to the
document about §5.4, which is the only way it could have been written.
