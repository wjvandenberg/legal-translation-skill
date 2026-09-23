> **Pre-flight.** You should be entering this step having completed the previous step. **SKILL.md governs every step's discipline; if you have not read SKILL.md in full this session, STOP and `Read('SKILL.md')` before continuing.** Hard Rules from SKILL.md apply to this step too. **In Chat mode (no workspace folder, no auto-managed todo list) the same discipline applies — do not skim this step doc, do not bundle batches, do not skip the per-step Internal compliance check at the bottom.** **If this turn began from a compacted transcript, the compaction summary does NOT count as having read this step doc — `Read()` it now in full before any tool call.**

### Step 6: Post-process

*[Internal compliance check — do not echo or paraphrase to the user. Re-read every rule in this step before executing. Do not deviate from any line of the skill. Do not bundle work, skip checks, or "interpret for efficiency" — every prior deviation has produced output below the quality the skill is designed to deliver. The skill's hard gates block deviations anyway; complying upfront is always faster than running into a gate and re-authoring paragraphs.json.]*

```bash
python <skill-path>/scripts/post_process.py <workdir>/final/word/document.xml --fix --variant uk
```

**Variant flag — re-verify before you type it.** `--variant uk` is the hardcoded default
and should be used unless the user's original prompt explicitly contained a US-English
indicator. Before passing `--variant us`, go back and re-read the user's *original*
request. Only use `us` if the prompt contained something unambiguous like "US English",
"American English", "American spelling", or similar. If there is any doubt, pass
`--variant uk`. (~98% of translations use UK English — UK is the real default, not a
polite suggestion.)

This applies automated quality fixes:
- Missing spaces between elements
- Definition boundary spacing ("Xmeans" → "X means")
- Double punctuation (::, .., ,,, ;;)
- Terminology standardisation (Facility Agreement, Secured Assets, etc.) — **never
  where a lexicon in this skill presents the string as correct**: a heading or term you
  wrote because a lexicon told you to is left as you wrote it, and the run prints a
  `[detector]` line naming it
- Spelling fixes per the active variant (default: UK — authorise, judgement, favour,
  centre, organisation, etc.)
- Annex / Schedule — **reported, never rewritten.** The lexicon offers "Schedule (UK) or
  Annex (EU/international)" as a free choice matched to the source's convention, so the
  label you wrote in `paragraphs.json` is the one delivered. Use one label throughout:
  auto-numbered attachment headings follow it at Step 8a
- Article → Clause for internal cross-references
- Duplicate word removal
- Quote balancing on defined terms
- Definition line-break removal
- Spurious italic removal
- Schedule page-break insertion (each Schedule starts on a new page)

**Tracked-change run formatting is preserved as-authored.** Run-level properties
inside `w:ins` / `w:del` wrappers (`w:sz`, `w:szCs`, `w:rFonts`, `w:color`) are
preserved byte-for-byte from the source. Do not normalise them, even when the
source author used a smaller font or a different colour for deletions and the
result looks visually inconsistent in the delivered English document. Fidelity
to the source author's formatting choices beats cosmetic harmonisation —
translation must not silently modify how the original was styled.
(See grading-skill methodology.md, Criterion 13, for the matching grading rule.)

**No-op tracked changes auto-stripped on TC documents.** `post_process.py`
auto-invokes `strip_noop_tracked_changes.py` at the end when the document
contains `<w:ins>` / `<w:del>` / `<w:delText>` — runs in the same
`post_process.py --fix` invocation, no separate operator command needed.
The strip pass:

* Finds adjacent `<w:del>` + `<w:ins>` pairs (either order, tolerating
  `commentRangeStart`/`commentRangeEnd`/`bookmarkStart`/`bookmarkEnd`/`proofErr`
  between them) whose normalised text content is identical; removes the
  `<w:del>` and unwraps the `<w:ins>`. This collapses orthographic-only
  source edits — Dutch `mn` ↔ `m.n.`, German `daß` ↔ `dass`, etc., where
  both sides translate to the same English — into a single piece of plain
  English text rather than a no-op redline.
* Removes `<w:del>` / `<w:ins>` wrappers whose content is empty, pure
  whitespace, or pure punctuation after normalisation.
* **Keeps** any pair where the English differs by even a single letter or
  digit. Date-digit changes (`2` → `6`), attachment-letter changes
  (`Schedule X` → `Schedule G`), defined-term substitutions, and any other
  real content edit all survive as tracked changes in the output.
* **Bracket-aware**: bracket-only ins/del wrappers (`[`, `]`, `(`, `)`) are
  PRESERVED when they sit adjacent to a content-bearing ins/del neighbour
  within 8 siblings — keeps placeholder-date tracked changes coherent.

**Companion translation rule**: when drafting `en_segments` for a TC paragraph,
give both `del` and `ins` segments the **same English text** when the source
edit is orthographic-only (see "Collapsing orthographic-only and typo-fix TC
edits — MANDATORY" in Step 4). The auto-strip relies on that. If you translated del
and ins to different English where the source edit was orthographic-only, the
auto-strip cannot detect the no-op and the marker stays visible.

Idempotent. Running `post_process.py --fix` twice has no effect on the second pass.

**A change journal is written, and it is the first thing to read when Step 6 blocks.**
`post_process.py` writes `post_process_journal.json` into the workdir — beside
`paragraphs.json`, never inside `final/` — listing every piece of text this step changed
and **which pass changed it**. It is written before the drift gate runs, so it is always
there when that gate fires.

* **When the post-strip drift gate blocks, open the journal before anything else.** The
  gate can only say the document and `paragraphs.json` disagree. The journal says whether
  *this step* is what moved the text, and which pass did it. If the flagged text is in the
  journal, the diagnosis is not "drift" — it is whatever that pass does, and the fix
  belongs there. If the flagged text is **not** in the journal, this step did not touch it
  and the cause is upstream or in the check itself.
* **It records TEXT and FORMATTING, in two separate records that share one numbering.**
  The text record lists every character that moved. The formatting record lists every run
  whose properties changed — an italic stripped — and every paragraph whose properties
  changed — a page break imposed. Both use the same element and paragraph numbers, so a
  wording change and a formatting change in one place read as one place.
* **`self_check.unexplained_fixes` is the figure to read first, and it should be empty.**
  It names any pass that reported a fix which *neither* record describes. `non_text_fixes`
  sits beside it and still names the passes that changed no wording — but those changes
  are now described, by the formatting record. So `0 edits` beside a non-empty
  `non_text_fixes` no longer means "something happened and we cannot say what": look at
  the formatting record and it will say what.
* **One case the formatting record does not claim, and it says so.** Where a pass changes
  the *number* of text-bearing elements or of paragraphs, every number after that point
  shifts and no record written against them would be true. The strip pass does exactly
  that on a tracked-change document. The journal states the case in its `notes` rather
  than reporting a clean zero.
* **It is not part of the deliverable.** It is a working file like `paragraphs.json`.
  Repack builds the `.docx` from the original's part list, so it cannot be bundled by
  accident, but do not copy it into `final/` and do not send it to the client.
* **If it reports that it could not account for something, that is a defect in the script,
  not in your document.** The run continues and the translation is unaffected. Report it.
  **Do not edit the document or the notes to make the message go away.**

**Four of these passes now TEST the condition they used to assume, and two of them REPORT
instead of rewriting.** Each one used to act on a guess, and each guess damaged a real
document. **Nothing here is a switch you can turn off, and there is no flag: if a pass
declines to act, that is the pass working.**

* **A missing space is only added where nothing already separates the two sides.** The
  spacing backstop compared the last character of one run against the first of the next and
  inserted a space that an intervening tab or line break already provided — putting a
  spurious space at the head of the second column of every signature block. It now looks at
  what sits between them. A seam with nothing between it behaves exactly as before.
* **A tracked-change wrapper holding only punctuation is removed only when it is a
  DELETION.** Removing an *insertion* wrapper deletes its character from the accepted text,
  which is the document you deliver — on one contract that left an accepted sentence with no
  closing bracket and no full stop, and every gate reported PASS. The line to hold on to:
  a deletion's text is in the reject view only, an insertion's is in the delivery.
* **`Article N` is left alone where the sentence does not say which instrument it means.**
  It used to default to "internal" and rewrite, and on one deed that turned a statutory
  citation into a clause number that does not exist. Where the reference points backward —
  "Article 1341 **thereof**" — the forward reading learns nothing, so the run now reports it
  and changes nothing. **You may still translate it correctly yourself; what has stopped is
  the script deciding for you.**
* **A doubled `.` `,` `;` or `:` is REPORTED, never collapsed.** Nothing in the document
  says whether the doubling is yours or the source's, and on one document the collapse
  deleted a character of a hand-typed signature rule. The run prints what it found; you
  decide.

**Two `[detector]` lines can appear after the fix counts, and they are not errors.** They
say what the stage FOUND and deliberately did not change. A detection is not a fix and is
deliberately not added to the total, so that "this stage changed nothing" and "this stage
found nothing" stay different statements.

### Step 7: Reorder definitions alphabetically — MANDATORY

*[Internal compliance check — do not echo or paraphrase to the user. Re-read every rule in this step before executing. Do not deviate from any line of the skill. Do not bundle work, skip checks, or "interpret for efficiency" — every prior deviation has produced output below the quality the skill is designed to deliver. The skill's hard gates block deviations anyway; complying upfront is always faster than running into a gate and re-authoring paragraphs.json.]*

**Run a dry-run first**  so you see what the script will do before it touches the
document. This is a 30-second pre-flight that catches the bug class that previously cost
~8 minutes per occurrence:

```bash
# 1. Dry-run with expected count
python <skill-path>/scripts/reorder_definitions.py \
    --doc <workdir>/final/word/document.xml \
    --dry-run --expected-defs <N>

# 2. If the count + extracted terms look right, run for real
python <skill-path>/scripts/reorder_definitions.py \
    --doc <workdir>/final/word/document.xml
```

`<N>` is the number of defined terms you actually count in the source document. Pass it
on every run — if the script extracts more or fewer than `<N>`, it aborts loudly rather
than reorder the wrong thing. If the document has no definitions section, omit
`--expected-defs` (the script will exit cleanly with "no definitions section found").

Run AFTER applying translations, since we sort by the English defined term.

**Do not skip this step.** Source-language alphabetical order is almost never the same as
English alphabetical order — for example, the Hungarian definition "Elidegenítési tilalom"
sits under "E", but its English translation "Prohibition on transfer" sits under "P".
Leaving the section in source-language order leaves a jarring, non-alphabetical definitions
list for an English reader — a HIGH-severity defect.

The script detects the definitions block **structurally** : a definitions section is
a cluster of ≥2 paragraphs that match the bold-term-then-colon shape (or quote-mark-wrapped
term-then-colon shape) within a tight window. No language-specific phrase matching — works
for every supported source language without hardcoding any keyword. If no such cluster
exists, the script exits cleanly without modifying anything.

**Rev11 safeguards (the bug-class catchers).** Three independent checks run before any
write-back:

1. **Term sanity (A2)** — every extracted "defined term" is checked. If any term contains
   a quote mark, the substring "means" / "indica" / "shall mean", or ends with a colon,
   the script aborts with a list of suspicious terms. This catches the LibreOffice
   `<w:b w:val="0"/>` misread that previously corrupted the reorder silently.
2. **Expected-count cross-check (A6)** — if `--expected-defs N` is set and the count
   doesn't match, abort.
3. **Out-of-window invariant (A3)** — every paragraph index outside `[def_start, def_end)`
   must have the same text after reordering as before. If anything outside the definitions
   block moved, abort.

Any of these aborts means the document on disk is **unchanged** — no corruption.

**Rev45 detector hardening (account-pledge / quota-pledge post-mortems).**
Three additional protections layer on top of the rev11 safeguards so the
script does not misdetect (or fail to detect) the definitions section when
the document contains structurally definition-shaped paragraphs that are
not real defined terms — letter Subject lines, recital openers
(`WHEREAS:` / `PREMESSO:`), notice-block labels (`Address:`,
`Attention:`), and addressee lines (`If to the Borrower:`).

1. **Fix A — Stop-list at `get_bold_term`.** A curated list of bold-then-colon
   prefixes (`subject`, `re`, `whereas`, `now therefore`, `attention`, `address`,
   `attn`, `fax`, `tel`, `email`, `e-mail`, `pec`, plus source-language
   equivalents across the eleven lexicon languages, plus phrase-start patterns
   `if to ` / `with copy to `) is rejected at extraction time. The matcher
   normalises by taking the substring before the first colon, so a fully-bolded
   cover-letter line such as `Subject: Account Pledge Agreement - Acceptance`
   compares as `subject` and is rejected. Real defined terms are never on the
   stop-list (e.g. `Subject Matter of the Pledge` is preserved — the head before
   the first colon is `subject matter of the pledge`, not on the list).

2. **Fix B — Cluster-fail falls through to the heading fallback.** If the
   primary detector returns ≥2 candidates but the K=20 / K*3=60 cluster guard
   rejects them (because spurious candidates spread the first three across more
   than 60 paragraphs), the script now runs the heading-anchored fallback
   (`Definitions` heading + ≥3 predicate-shape paragraphs in the next 8) instead
   of returning `(None, None)`. Previously the fallback only ran when the
   primary detector found <2 candidates, which left the script silent on
   documents with many spurious bold-colon hits.

3. **Fix C — Trim leading isolated false positives.** Before the cluster guard,
   if `def_starts_idx[0]` is more than K=20 paragraphs away from
   `def_starts_idx[1]` AND the tail forms a tight cluster, the head is dropped
   and the cluster guard is re-checked on the trimmed list. Bounded by
   `max_trims=5` to avoid pathological inputs. Recovery path for the quota-
   pledge case where `WHEREAS:` at P[28] sat 34 paragraphs before the real
   definitions cluster at P[62..92].

All three fixes leave the rev11 safeguards (A2/A3/A6) intact. A fallback
warning is still printed when the heading-anchored path is the one that
located the section — but the warning text now lists *both* common causes
(missing `en_runs` on definition paragraphs OR a stop-list miss), not just
the first.

**If reorder refuses (sanity check fires).** The most likely cause is `<w:b w:val="0"/>`
emitted by LibreOffice when converting `.odt` → `.docx`. The bold-detection helper now
recognises `0` and `off` (case-insensitive) per ECMA-376 ST_OnOff, but if a document hits
some other variation, the safest workaround is:

- Re-run with `--dry-run` to inspect the extracted terms.
- If the count is wrong, accept that the document ships in source order. Definitions stay
  un-alphabetised; quality_check will emit `definition_order` warnings as known false
  positives. Document this in the delivery notes.

If the script prints `"no definitions section found"` even though the document clearly has
a definitions section, the cause is almost always a structurally-definition-shaped
paragraph that the rev45 stop-list did not catch (a Subject line in an unsupported
language, an unusual notice-block label, an exotic recital opener). Use `--dry-run` to
inspect the cluster candidates: search the dry-run output for any extracted "term" that
clearly is not a defined term, and extend `_NON_DEFINITION_BOLD_PREFIXES_EXACT` or
`_NON_DEFINITION_BOLD_PREFIX_STARTS` in `reorder_definitions.py`. If the section
nonetheless gets detected via the heading+predicate fallback, that path is fine to ship —
just review the dry-run output to confirm the real definitions are the ones being sorted.

## Internal compliance check — 06-postprocess-and-reorder

Before moving to the next step, confirm:

- [ ] You ran `post_process.py` (Step 6) on the applied document
- [ ] You ran `reorder_definitions.py` (Step 7) if the document has a definitions section
- [ ] You did NOT skip post-processing on the assumption that translations are already perfect
- [ ] For documents WITHOUT a definitions section, you confirmed `reorder_definitions.py --dry-run` returns zero detections

If any check is uncertain, STOP. Re-read this file. Do not proceed.

**Next:** `skill-docs/08-aux-and-quality.md`
