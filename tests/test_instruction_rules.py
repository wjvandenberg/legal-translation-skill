# -*- coding: utf-8 -*-
"""ACCEPTANCE TEST FOR THE INSTRUCTION LAYER — step 3 (the scope rule), and the file the
later instruction branches extend.

PLAN-2-step-b.md §4 puts steps 3, 4, 13, 17 and 19 in one row: "instruction and
dictionary changes ... a graded run plus your review. There is no script instrument for
these." **This is a script instrument for the part of them that IS decidable** -- not for
whether the prose persuades an operator, which needs phase 3's test, but for whether the rule is
present, whether it says what the register requires, whether it is in BOTH trees, and
whether adding it softened anything it was forbidden to soften.

Step 4 should add its cases here rather than start a parallel file.

WHY EVERY NEEDLE IS A PHRASE. §5.3 rule 6: eleven checks in this project have passed for
the wrong reason and every one used a needle short enough to occur by accident. "in scope"
matches ordinary prose about scoping; the phrases below cannot appear unless the rule is
actually carried.

RESTORATION. Mutations are held in memory and written back -- never restored through git.
The handoff records uncommitted work destroyed twice by `git checkout --`; the tests that
were safe are the ones that kept the original bytes themselves.

    uv run python tests/test_instruction_rules.py
"""
import io
import os
import re
import subprocess
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parent.parent
sys.dont_write_bytecode = True  # importing from tools/ must leave no bytecode there
sys.path.insert(0, str(ROOT / "tools"))
import inplace_guard as guard  # noqa: E402  (register I-37: a repository file changes only through it)
TREES = ("uk", "us")

# --------------------------------------------------------------------------------------
# WHAT MUST BE PRESENT — register row -> (file, phrase). Both trees, every row.
# --------------------------------------------------------------------------------------
# The header of a list that closes TWO skill steps (F21), and when an item naming no step is confirmed.
HEAD_TWO_STEP = "Confirm each item once the step it names has run, one naming no step at the first step's close:"
# Two characters no needle may type: a zero-width space (U+200B) and a backslash. Built, never typed.
ZW, BS = chr(0x200B), chr(92)
REQUIRED = [
    # K1 + X3 — the scope rule. The cheapest fix in the project, and the one X3 says must
    # ADD a rule rather than soften one.
    ("K1", "SKILL.md",
     "A check can be wrong IN SCOPE, and saying so is not permission to bypass it"),
    ("K1", "SKILL.md", "Fix the check, never work around it"),
    ("K1", "SKILL.md", "fidelity wins and the check gets fixed"),
    ("K1", "SKILL.md", "Never alter a source-faithful translation to satisfy a check"),
    # The scope rule has to be reachable where the operator meets the APPLY gates too.
    ("K1", "skill-docs/05-apply.md", "SKILL.md's script-integrity rule governs"),

    # F35 — the two colliding truncation instructions, reconciled. One must state which
    # governs; the other must stop asserting the opposite.
    ("F35", "SKILL.md", "THIS RULE TAKES PRECEDENCE OVER THE GATE READING"),
    ("F35", "SKILL.md", "If the reported exit code is **3**"),
    ("F35", "skill-docs/05-apply.md", "Rule out a truncated install FIRST"),
    ("F35", "skill-docs/05-apply.md",
     "exit code 3 from either of those means the script is truncated"),

    # K3 — what delivery notes must contain, and the completion invariant.
    ("K3", "SKILL.md", "## What the delivery notes must contain"),
    ("K3", "SKILL.md", "the only thing that speaks to the person who receives the document"),
    ("K3", "SKILL.md", "THE COMPLETION INVARIANT"),
    ("K3", "SKILL.md", "There is no partial deliverable"),
    ("K3", "SKILL.md", "the source-language document remains the operative text"),

    # K2 — the Step 6 gate stops telling the operator to make the JSON match the document.
    # WIDENED 2026-08-19 FROM TWO SIDES TO THREE. The needle used to be "WORK OUT WHICH SIDE
    # IS WRONG BEFORE EDITING EITHER", and the rule-5b probe showed what that framing cost:
    # the operator accepted the binary the banner offered, concluded every repair was
    # forbidden, and was one step from invoking 5b on a check that was simply miscounting.
    # Its own words -- "what made 5b look inevitable was accepting the banner's binary".
    # So these needles now assert the THIRD possibility is named and routed, which is a
    # stronger claim than the two-sided one they replace, not a relocated one.
    ("K2", "scripts/post_process.py", "WORK OUT WHICH OF THREE THINGS IS WRONG"),
    ("K2", "scripts/post_process.py", "it clears the gate and ships the defect"),
    ("F1", "scripts/post_process.py", "THIS CHECK IS WRONGLY SCOPED"),
    ("F1", "scripts/post_process.py", "cannot detect (3) about itself"),
    ("F1", "scripts/post_process.py", "SKILL.md rule 5a"),

    # F1 — rule 5a stops forbidding the repair it mandates. "Never patch the script" and
    # "narrow the pattern" were the same sentence pointing two ways; for a check implemented
    # in Python they cannot both be obeyed. The needles bind the resolution to its own five
    # conditions, so a file that merely says "correct the check" cannot satisfy them.
    ("F1", "SKILL.md", "never patch the installed skill"),
    ("F1", "SKILL.md", "Correcting a wrongly-scoped check is not working around it"),
    ("F1", "SKILL.md", "show the wrong scope from the check's OWN source or stated contract"),
    ("F1", "SKILL.md", "You correct it in a WORKING COPY, never in the installed skill"),
    ("F1", "SKILL.md", "narrowed until it fires on nothing is not a fix"),
    ("F1", "SKILL.md", "that the INSTALLED skill still carries the defect"),
    ("F1", "SKILL.md", "AND CHECK 5a BEFORE 5b, NOT AFTER"),
    ("F1", "SKILL.md", "Read the check's source before concluding that no repair exists"),

    # ---- STEP 4 — the exception channel -------------------------------------------
    # The channel is for the case rule 5a is NOT for: the check is right and every repair
    # left is forbidden. The needles bind the rule to its own conditions, so a file that
    # merely mentions "no compliant repair" cannot satisfy them.
    ("F41", "SKILL.md",
     "When a check is RIGHT and there is NO compliant repair"),
    ("F41", "SKILL.md",
     "the only sanctioned way a repair loop may end other than the check passing"),
    # Each of the four conditions, individually. Decision 3b is not re-openable, so a later
    # edit that drops one has to delete a line here and show it in the diff.
    ("F41", "SKILL.md", "(a) The check has actually fired"),
    ("F41", "SKILL.md", "(b) You attempted repair, and you can say what you tried"),
    ("F41", "SKILL.md", "(c) You name the specific consequence in the delivery notes"),
    ("F41", "SKILL.md", "(d) You did not alter the translation to get here"),
    # The fifth gap: the bound. Without it the channel is optional.
    ("F41", "SKILL.md", "THE BOUND — five attempts, then stop"),
    ("F41", "SKILL.md", "do not make a sixth"),
    # K3 again — condition (c) has to land in the format step 3 laid down, not a new one.
    ("F41", "SKILL.md", "this item is where its condition (c) is discharged"),
    # THE DISCLOSURE BLOCK. Free prose cannot discharge condition (c): an undisclosed
    # exception and a well-handled one look identical in prose, and no gate can tell them
    # apart. The fixed shape cannot prove the five attempts happened -- it makes SILENCE
    # detectable, which is a different and achievable thing. Every key is asserted
    # individually so dropping one has to show in a diff.
    ("F41", "SKILL.md", "ACCEPTED CONSEQUENCE (SKILL.md rule 5b)"),
    ("F41", "SKILL.md", "check:        <the check that fired"),
    ("F41", "SKILL.md", "attempts:     <how many repairs you made"),
    ("F41", "SKILL.md", "consequence:  <what is wrong in the delivered document>"),
    ("F41", "SKILL.md", "where:        <clause, page or part"),
    ("F41", "SKILL.md", "reader must:  <what the reader has to do about it>"),
    ("F41", "SKILL.md", "verbatim keys, all five lines present"),
    ("F41", "SKILL.md", "This does not make you more honest; it makes a lapse visible"),
    # And condition (c) must POINT at the block, or the rule and the format drift apart.
    ("F41", "SKILL.md", "in the fixed ACCEPTED CONSEQUENCE block set out there"),
    ("F41", "SKILL.md", "Free prose does not discharge this condition"),

    # The bound must be stated WHERE THE LOOP IS. All four prose sites, not the two F41
    # named -- the sweep on step 4 found two more, one of them in the always-loaded file.
    ("F41", "skill-docs/04b-translate-gates.md",
     "THE REPAIR LOOP IS BOUNDED AT FIVE ATTEMPTS"),
    ("F41", "skill-docs/08-aux-and-quality.md",
     "THAT LOOP IS BOUNDED AT FIVE ATTEMPTS"),
    ("F41", "skill-docs/10-repack-and-validate.md",
     "This loop is bounded at five attempts"),
    ("F41", "SKILL.md", "bounded at five attempts, per rule 5b"),
    # 08-aux must send the two cases to DIFFERENT rules. Collapsing them would make 5b the
    # answer to a false positive, which is the one reading that turns it into a bypass.
    ("F41", "skill-docs/08-aux-and-quality.md", "governs: fix the check, and never alter"),
    ("F41", "skill-docs/08-aux-and-quality.md", "no compliant repair exists"),

    # ---- STEP 14.9.2 — skill Steps 1 and 11 -----------------------------------------
    # F11: the conversion command an operator copies. The wrapper hands every argument to
    # soffice unchanged, so the needle is the whole working argument list, output folder too.
    ("F11", "skill-docs/01-setup-and-extract.md",
     "soffice.py --headless --convert-to docx --outdir <workdir> <input>.doc"),
    ("F11", "skill-docs/01-setup-and-extract.md", "hands its arguments to LibreOffice unchanged"),
    # LibreOffice writes only the base name into --outdir, whatever folder the input sits in.
    ("F11", "skill-docs/01-setup-and-extract.md", "writes the input's name, ending `.docx`, into `<workdir>`"),
    # F9: the conversion items say when they apply, and what to do on the case that must not run.
    ("F9", "skill-docs/01-setup-and-extract.md", "N/A for a `.docx` source"),
    ("F9", "skill-docs/01-setup-and-extract.md", "on a redline you skipped it"),
    # F21, the class: every file that closes TWO skill steps with one list, not the two the row
    # named. The per-step loop walks that list at each step's close, so the header must say an
    # item waits for its step, and the second step's items must name it.
    ("F21", "skill-docs/01-setup-and-extract.md", HEAD_TWO_STEP),
    ("F21", "skill-docs/06-postprocess-and-reorder.md",
     HEAD_TWO_STEP),
    ("F21", "skill-docs/08-aux-and-quality.md", HEAD_TWO_STEP),
    ("F21", "skill-docs/10-repack-and-validate.md",
     HEAD_TWO_STEP),
    # Every second-step item, one needle each: a list naming only some of them is the defect again.
    ("F21", "skill-docs/01-setup-and-extract.md",
     "You produced `paragraphs.json` with `extract_paragraphs.py` (Step 2)"),
    ("F21", "skill-docs/01-setup-and-extract.md",
     "`validate_apply.py --extraction-completeness` (Step 2)"),
    ("F21", "skill-docs/01-setup-and-extract.md", "the auxiliary parts it listed (Step 2)"),
    ("F21", "skill-docs/06-postprocess-and-reorder.md", "`reorder_definitions.py --dry-run` (Step 7)"),
    ("F21", "skill-docs/08-aux-and-quality.md", "You ran `quality_check.py` (Step 9)"),
    ("F21", "skill-docs/08-aux-and-quality.md", "remnants `quality_check.py` flagged (Step 9)"),
    ("F21", "skill-docs/08-aux-and-quality.md", "If QC (Step 9) flagged a paragraph"),
    # F20: the last list before delivery keeps a redline's revisions instead of stripping them.
    ("F20", "skill-docs/10-repack-and-validate.md", "**No spurious tracked changes**"),
    ("F20", "skill-docs/10-repack-and-validate.md", "the source's own revisions are all there"),
    # ...and a count lower than the source's is no loss when Step 3b merged a fragmented cluster.
    ("F20", "skill-docs/10-repack-and-validate.md", "(Step 3b may merge its fragments)"),

    # ---- STEP 14.9.3 — skill Step 4's rules -------------------------------------------
    # F2: Rule 1's bookends are right for a PAIRED change and deliver a double space around a
    # LONE one, measured on invented documents through apply, fix_spacing and the U+200B scrub.
    ("F2", "skill-docs/04-translate.md", "a LONE ins or del on one side only, as below"),
    ("F2", "skill-docs/04-translate.md",
     "**A LONE ins or del — no deletion or insertion beside it — is the exception,"),
    ("F2", "skill-docs/04-translate.md",
     "would meet as a double space, unseen by `validate_reject_all.py` (a ZWSP is not"),
    ("F2", "skill-docs/04-translate.md",
     "So bookend only the regular segment BEFORE it, put the space after"),
    ("F2", "skill-docs/04-translate.md", "Worked example for a lone alpha ins between alpha regulars:"),
    ("F2", "skill-docs/04-translate.md", '{"type": "ins",     "en": "Investment ' + ZW + '"},'),
    ("F2", "skill-docs/04-translate.md", '{"type": "regular", "en": "' + ZW + 'Insurance"}'),
    # /code-review: punctuation after a lone change needs no space; and the general rule every
    # tracked-change operator reads, appendix or not, carries the lone change's space too.
    ("F2", "skill-docs/04-translate.md",
     "Where the regular after it opens with punctuation, the change carries a ZWSP alone."),
    ("F2", "skill-docs/04-translate.md", "so does the space a lone ins or del needs on one side.**"),
    # F3: a preposition strands only where its object is a LONE change; and Rule 2, the same class.
    ("F3", "skill-docs/04-translate.md",
     "**A preposition whose object is a lone ins or del goes inside it, with its"),
    ("F3", "skill-docs/04-translate.md",
     "drops the change (`the provisions of apply`). Before a paired change, where"),
    ("F3", "skill-docs/04-translate.md", "**A digit at a seam takes Rule 1's bookends like a letter.**"),
    # F14: the appendix is read where a seam lacks whitespace, in any script.
    ("F14", "skill-docs/04-translate.md", "**A seam without whitespace has additional segment-shape rules.**"),
    ("F14", "skill-docs/04-translate.md",
     "#### Sub-appendix: Seams without whitespace — for TC docs, in any script"),
    ("F14", "skill-docs/04-translate.md", "> **READ if any tracked-change seam lacks whitespace in the source**"),
    ("F14", "skill-docs/04-translate.md",
     "where a change begins or ends inside a word: an Italian amount spelled as one"),
    ("F14", "skill-docs/04-translate.md",
     "> **SKIP only if the source is Latin-script and every seam has whitespace on one"),
    # /code-review: one skip test in pointer and box, the appendix body and the gate's label in any script.
    ("F14", "skill-docs/04-translate.md",
     "A Latin-script source whose every seam has whitespace on one side can"),
    ("F14", "skill-docs/04-translate.md", "A seam without whitespace gets none from the source, in any script; and"),
    ("F14", "skill-docs/04b-translate-gates.md",
     "(a seam without whitespace, in any script), a double-space straddling"),
    ("F14", "SKILL.md", "with no whitespace — a seam without whitespace, in any script"),
    # F18: what extract writes at a tab, a line break and a page break, and what apply makes of `en`.
    ("F18", "skill-docs/01-setup-and-extract.md",
     "**A tab or a line break: what `text` shows, and what you write in `en`.**"),
    ("F18", "skill-docs/01-setup-and-extract.md",
     f"line break (`<w:br/>`) shows in `text` as `{BS}n`: write `{BS}n` in `en` where the"),
    ("F18", "skill-docs/01-setup-and-extract.md",
     f"first word (`11.3.1Il 10%…`): write `{BS}t` in `en` where the tab stood"),
    ("F18", "skill-docs/01-setup-and-extract.md", "A page break shows as nothing too: write nothing for it."),
    ("F18", "skill-docs/01-setup-and-extract.md",
     f"`w:t` text alone, never a `{BS}n`; your `en_runs` offsets count every character of"),
    # F32: the WARN a multi-batch document meets after every batch but the last, named.
    ("F32", "skill-docs/04b-translate-gates.md",
     "`N paragraphs without translations` (printed only when nothing else warned):"),
    ("F32", "skill-docs/04b-translate-gates.md",
     "expected after every batch but the last, N being the paragraphs later batches will"),
    ("F32", "skill-docs/04b-translate-gates.md",
     "translate; after the last batch, translate the missed paragraphs before Step 5."),
    # F4 (and F8): the date rule stated once, where it is read in full at Step 3 in every mode.
    ("F4", "references/general-legal.md",
     "## Dates and Calendar Conventions — MANDATORY (all source languages)"),
    ("F4", "references/general-legal.md", "**The date rule, stated here alone; SKILL.md points here.**"),
    ("F4", "references/general-legal.md",
     "change as anywhere else: `15 April 2026` (UK), `April 15, 2026` (US)."),
    ("F4", "references/general-legal.md",
     "source writes in figures is written in words, a bracketed placeholder within its"),
    ("F4", "references/general-legal.md", "a numeric table cell stays as it stands."),
    ("F4", "SKILL.md",
     "- **Date format**: each variant's order — the date rule in `references/general-legal.md`,"),
    ("F4", "sub-lexicons/dutch-general-legal.md",
     "Render them by the date rule in `references/general-legal.md`."),

    # ---- STEP 14.9.4 — the claims about the skill ------------------------------------
    # F23: apply runs five checks, measured at its call sites, two on tracked-change documents only;
    # and the class at repack, which runs three where two lists named two.
    ("F23", "SKILL.md", "which validators auto-invoke from `apply_translations_textmatch.py` (there are five)"),
    ("F23", "SKILL.md", "`apply_translations_textmatch.py` (auto-invokes 5 validators)"),
    ("F23", "SKILL.md", "`repack_docx.py` (auto-invokes lexicon_compliance, validate_apply --strict, then --delivered)"),
    ("F23", "SKILL.md", "auto-runs five validators: `validate_en_runs` and `validate_translations` before applying,"),
    ("F23", "SKILL.md",
     "`validate_segment_shapes` and `validate_reject_all` too on a TC document, then `validate_apply --strict`"),
    ("F23", "SKILL.md",
     "`repack_docx.py` auto-runs `lexicon_compliance --stage pre-repack` and `validate_apply --strict` again"),
    ("F23", "SKILL.md", "Auto-runs `validate_en_runs.py` and `validate_translations.py` (each BLOCK code 2 only)"),
    ("F23", "skill-docs/04b-translate-gates.md",
     "(definitions-section bold-italic gate) + the final `validate_translations.py` pass"),
    ("F23", "skill-docs/04b-translate-gates.md",
     "+ `validate_segment_shapes.py` + `validate_reject_all.py` (these two on TC docs only)"),
    ("F23", "skill-docs/05-apply.md",
     "(validate_en_runs, validate_translations, segment_shapes, reject_all, validate_apply)"),
    ("F23", "skill-docs/10-repack-and-validate.md",
     "`validate_en_runs.py` (pre-apply, BLOCK on missing or broken `en_runs`) and"),
    ("F23", "scripts/apply_translations_textmatch.py",
     "mandatory validators: en_runs and translations before applying, segment_shapes and"),
    # F37: apply writes with ElementTree behind four guards, each run on an invented document; and
    # translate_numbering, which the same list said used lxml, rewrites by regex.
    ("F37", "SKILL.md", "problem although `apply_translations_textmatch.py` uses ElementTree too: it registers every"),
    ("F37", "SKILL.md", "prefix the source's root declares, grafts the original root tag back, injects any missing"),
    ("F37", "SKILL.md", "declaration, and stops rather than write a synthetic `nsN:` prefix."),
    ("F37", "SKILL.md", "for the auxiliary files has none of these guards, which is where ElementTree sneaks in."),
    ("F37", "SKILL.md", "correctly; the second rewrites its strings by regex."),
    # F36: a gate in apply exits 1; argparse's mistyped command is the only exit 2.
    ("F36", "skill-docs/05-apply.md",
     "exits with code 1 on a `RuntimeError` mentioning `BLOCK`, or prints a banner"),
    ("F36", "skill-docs/05-apply.md", "that is a gate firing intentionally; an exit 2 is a mistyped command."),
    ("F36", "skill-docs/05-apply.md", "- [ ] No validator's exit code 2 was suppressed or worked around"),
    # F38: each sentence an automated edit broke, made whole without its version token, one needle a site.
    ("F38", "SKILL.md", "The script's own invariant check would"),
    ("F38", "skill-docs/04-translate.md", "style provides bold.** The auto-detector inside"),
    ("F38", "skill-docs/04-translate.md", "**Style-provided bold.** Definitions sections and clause/article"),
    ("F38", "skill-docs/04-translate.md", "**Backstop: `fix_spacing` covers ins↔del seams.**"),
    ("F38", "skill-docs/04-translate.md", "the hybrid is now the default in Rule 1 above (was a caveat).**"),
    ("F38", "skill-docs/06-postprocess-and-reorder.md", "**Run a dry-run first** so you see what the script will do"),
    ("F38", "skill-docs/06-postprocess-and-reorder.md", "**structurally**: a definitions section is"),
    ("F38", "skill-docs/08-aux-and-quality.md",
     "**`--aux-dir` is mandatory here, though the script runs without it.**"),
    ("F38", "skill-docs/08-aux-and-quality.md", "source-language text in an auxiliary file?"),
    ("F38", "scripts/apply_translations_textmatch.py", "Handles the hybrid bookends correctly."),
    ("F38", "scripts/validate_apply.py", "``1234.50``) is left exactly as it stands. The substitution"),
    ("F38", "scripts/validate_apply.py", "# Through _emit_error, defined near the top of the file, where a truncated"),
    ("F38", "scripts/validate_en_runs.py", "paragraphs.json has any paragraph without `en_runs`."),
    ("F38", "scripts/repack_docx.py", "repack now runs both, so the operator runs ONE command and"),
    ("F38", "scripts/post_process.py", "# The earlier blanket replacement broke legitimate adjective use"),
    ("F38", "scripts/post_process.py", "It now iterates ``<w:t>`` AND ``<w:delText>`` together in"),
    ("F38", "scripts/post_process.py", "document order. The earlier version only walked ``<w:t>``"),
    ("F38", "scripts/post_process.py", "preposition, not a label). The length cap doesn't"),
    ("F38", "scripts/post_process.py", "# The skill replaced the LEGISLATION_KW hardcoded list"),
    ("F38", "scripts/reorder_definitions.py", "paragraphs.json, OR a paragraph whose English text matches"),
    ("F38", "scripts/reorder_definitions.py", "defined terms (Doc 1 post-mortem; cascade root cause)."),
    ("F38", "scripts/source_language_markers.py", "references that once walked through every gate, because"),
]

# One-tree rules: (row, tree, file, phrase, must be present). US rule 7a and the US Japanese examples,
# and a control that the UK tree keeps its own order.
TREE_RULES = [
    ("F4", "us", "skill-docs/04-translate.md",
     "7a. **Dates: the date rule in `references/general-legal.md`**, read in full at Step 3,", True),
    ("F4", "us", "skill-docs/04-translate.md", "Date format — US default", False),
    ("F4", "us", "sub-lexicons/japanese-general-legal.md", "| `平成29年11月29日` | `November 29, 2017` |", True),
    ("F4", "us", "sub-lexicons/japanese-general-legal.md", "`29 November 2017`", False),
    ("F4", "us", "sub-lexicons/japanese-general-legal.md", "Render the whole span as `[Month] [__], 20__`", True),
    ("F4", "uk", "sub-lexicons/japanese-general-legal.md", "| `平成29年11月29日` | `29 November 2017` |", True),
]

# --------------------------------------------------------------------------------------
# WHAT MUST BE GONE — the half a presence-only test leaves out.
# --------------------------------------------------------------------------------------
FORBIDDEN = [
    # F35: the categorical claim that produced the collision. It said the scripts are "not
    # truncated" on the one condition where they may be exactly that.
    ("F35", "skill-docs/05-apply.md",
     "The scripts are not crashing, not truncated, and not buggy"),
    # K2: the remedy that told the operator to edit one side without asking which was wrong.
    ("K2", "scripts/post_process.py", "Fix paragraphs.json and re-run from Step 5"),
    # Step 14.9.2. F11: a flag LibreOffice does not have, which printed its usage and converted nothing.
    ("F11", "skill-docs/01-setup-and-extract.md", "--format docx"),
    ("F11", "SKILL.md", "--format docx"),
    # F9: an item asking to confirm output of a script it also says must not run.
    ("F9", "skill-docs/01-setup-and-extract.md", "output and did not run it on a redline"),
    # F21: the header that asked at the close of the FIRST step for the second's work. The four
    # one-step files keep it, so it is forbidden in the two-step files alone.
    ("F21", "skill-docs/01-setup-and-extract.md", "Before moving to the next step, confirm:"),
    ("F21", "skill-docs/06-postprocess-and-reorder.md", "Before moving to the next step, confirm:"),
    ("F21", "skill-docs/08-aux-and-quality.md", "Before moving to the next step, confirm:"),
    ("F21", "skill-docs/10-repack-and-validate.md", "Before moving to the next step, confirm:"),
    # F20: the sentence that, on a redline, meant stripping the revisions just translated.
    ("F20", "skill-docs/10-repack-and-validate.md", "No tracked changes visible"),
    # Step 14.9.3. F2: the example that IS the defect, a lone insertion bookended on both sides.
    ("F2", "skill-docs/04-translate.md", "Worked example for alpha ins/del abutting alpha regular"),
    ("F2", "skill-docs/04-translate.md", '{"type": "ins",     "en": "' + ZW + "Investment" + ZW + '"}'),
    ("F2", "skill-docs/04-translate.md", '{"type": "regular", "en": "' + ZW + ' Insurance"}'),
    # F3, and Rule 2 of its class: both contradicted by Rule 1's own first example.
    ("F3", "skill-docs/04-translate.md", "Never end a regular segment with a preposition"),
    ("F3", "skill-docs/04-translate.md", "Never end a segment with a digit"),
    # F14: the scope by script family, and the premise that failed for a Latin seam.
    ("F14", "skill-docs/04-translate.md", "Non-Latin script sources only"),
    ("F14", "skill-docs/04-translate.md", "can skip that appendix entirely"),
    ("F14", "skill-docs/04-translate.md", "Latin-script sources carry inter-word whitespace that"),
    ("F14", "skill-docs/04b-translate-gates.md", "(Non-Latin script gotcha)"),
    ("F14", "SKILL.md", "non-Latin script gotcha"),
    # F18: the sentence that, obeyed, loses every line break and tab.
    ("F18", "skill-docs/01-setup-and-extract.md", "Do NOT insert tab or newline characters"),
    ("F18", "skill-docs/01-setup-and-extract.md", "which are preserved in the XML during the apply step"),
    # F32: WARN described only as a quality signal.
    ("F32", "skill-docs/04b-translate-gates.md", "some paragraphs have low ratios"),
    # F4 and F8: the misleading statements and the day-first exemplars.
    ("F4", "SKILL.md", "leave original-language dates in source documents alone"),
    ("F4", "references/general-legal.md", "`29 November 2017`, `1 April 2023`, `15 March 1989`"),
    ("F4", "sub-lexicons/dutch-general-legal.md", "per project style"),
    # Step 14.9.4. F23: every wrong count, and every list of apply's or repack's checks missing one.
    ("F23", "SKILL.md", "(there are four)"),
    ("F23", "SKILL.md", "(auto-invokes 4 validators)"),
    ("F23", "SKILL.md", "(auto-invokes validate_apply --strict, then --delivered)"),
    ("F23", "SKILL.md", "auto-runs four pre-apply validators"),
    ("F23", "SKILL.md", "Auto-runs `validate_translations.py` (BLOCK code 2 only)"),
    ("F23", "skill-docs/04b-translate-gates.md", "Pre-apply gates (TC documents)"),
    ("F23", "skill-docs/05-apply.md", "(segment_shapes, reject_all, validate_en_runs, validate_apply)"),
    ("F23", "scripts/apply_translations_textmatch.py",
     "validators (segment_shapes, reject_all, validate_apply) the full gate sequence"),
    # F37: the library apply does not use, and a second script said to use it.
    ("F37", "SKILL.md", "uses lxml and grafts the original root"),
    ("F37", "SKILL.md", "They use lxml, which preserves prefixes correctly."),
    # F36: an exit code no gate in apply gives.
    ("F36", "skill-docs/05-apply.md", "exits with code 2, raises `RuntimeError`"),
    ("F36", "skill-docs/05-apply.md", "No gate exit code 2 was suppressed"),
    # F38: each broken sentence, the one step 11's rewrite removed included, so none comes back.
    ("F38", "SKILL.md", "The  invariant check"),
    ("F38", "skill-docs/04-translate.md", "style provides bold .**"),
    ("F38", "skill-docs/04-translate.md", "**Style-provided bold .**"),
    ("F38", "skill-docs/04-translate.md", "**Backstop:  `fix_spacing`"),
    ("F38", "skill-docs/04-translate.md", "(was  caveat)"),
    ("F38", "skill-docs/06-postprocess-and-reorder.md", "**Run a dry-run first**  so"),
    ("F38", "skill-docs/06-postprocess-and-reorder.md", "**structurally** : a definitions"),
    ("F38", "skill-docs/08-aux-and-quality.md", "is and strongly recommended"),
    ("F38", "skill-docs/08-aux-and-quality.md", "in auxiliary file ?"),
    ("F38", "skill-docs/10-repack-and-validate.md", "added in  by covering"),
    ("F38", "scripts/apply_translations_textmatch.py", "Handles  hybrid bookends"),
    ("F38", "scripts/validate_apply.py", "preserved exactly as in . The substitution"),
    ("F38", "scripts/validate_apply.py", "# refactored to use a helper at byte-shifted position."),
    ("F38", "scripts/validate_en_runs.py", "(gate introduced) and  (extracted to standalone file)"),
    ("F38", "scripts/repack_docx.py", "     folds them into repack"),
    ("F38", "scripts/post_process.py", "# The  blanket replacement"),
    ("F38", "scripts/post_process.py", "    now iterates ``<w:t>``"),
    ("F38", "scripts/post_process.py", "The  version only walked"),
    ("F38", "scripts/post_process.py", "The  length cap"),
    ("F38", "scripts/post_process.py", "# replaced the LEGISLATION_KW"),
    ("F38", "scripts/reorder_definitions.py", "paragraphs.json , OR"),
    ("F38", "scripts/reorder_definitions.py", "(Doc 1  post-mortem"),
    ("F38", "scripts/source_language_markers.py", "every gate in  because"),
]

# --------------------------------------------------------------------------------------
# WHAT MUST NOT HAVE MOVED — X3, made mechanical.
#
# X3 is the row that says a competent outside reader called this absolutism "mature", and
# §3.4's Must-not line is "soften a single word of the anti-drift text". A promise not to
# soften is worth nothing unless something checks it, so these sentences are asserted
# byte-for-byte. If a later branch has a reason to change one, it changes this list in the
# same commit and the diff shows it.
# --------------------------------------------------------------------------------------
PRESERVED = [
    ("SKILL.md", "**Do NOT work around a gate by patching the script or skipping the "
                 "validator** — fix the input (usually paragraphs.json) and re-run."),
    ("SKILL.md", "This is the script doing its job, not the script breaking."),
    ("SKILL.md", "**STOP** — re-install the skill from the .skill / .zip archive before "
                 "re-running the affected step."),
    ("SKILL.md", "Do NOT work around the failure by skipping the step, calling the script "
                 "through a wrapper, or treating the result as \"optional.\""),
    ("skill-docs/05-apply.md",
     "**Do NOT work around a gate by calling `textmatch_apply()` from a wrapper that "
     "bypasses the auto-invoked validators, by suppressing `--strict` flags, or by "
     "patching the script to return success.**"),
    ("skill-docs/05-apply.md",
     "The gates exist because every prior occasion the operator went around them shipped "
     "output below the quality the skill is designed to deliver."),
    # Step 4's own guard rails. PLAN-2-step-b.md calls the exception channel "the
    # highest-risk documentation change in the whole plan" -- written loosely it is a licence
    # to bypass checks. These four sentences are what stop that reading, so they are asserted
    # byte-for-byte exactly like the anti-drift text they sit beside.
    ("SKILL.md", "It is not permission to skip a check, not a judgement that a defect is "
                 "minor, and never available because repair is slow, awkward or expensive."),
    ("SKILL.md", "**If the check is still firing after the fifth attempt, do not make a "
                 "sixth.**"),
    ("SKILL.md", "It does not make the requirement satisfied, and you must never record it "
                 "as satisfied."),
    ("SKILL.md", "If you have done it, you have not earned this channel — you have broken a "
                 "different rule."),
]

# The one place the two trees are ALLOWED to differ inside the added prose. Everything else
# in the new sections must be word-for-word identical, or the variant layer has grown a new
# divergence that D1 will have to reconcile -- and markdown prose is the one thing the
# parity check does not compare, so nothing else would catch it.
VARIANT_PAIR = ("UK English", "US English")

results = []


def check(name, ok, detail=""):
    results.append((name, ok))
    print(f"  {'OK  ' if ok else 'FAIL'}  {name}{('  — ' + detail) if detail else ''}")
    return ok


def read(tree, rel):
    return (ROOT / tree / rel).read_text(encoding="utf-8")


print("=" * 96)
print("INSTRUCTION-LAYER ACCEPTANCE — steps 3 and 4, and step 14's instruction fixes")
print("=" * 96)

print("\n1. EVERY REQUIRED RULE IS PRESENT, IN BOTH TREES")
for row, rel, phrase in REQUIRED:
    missing = [t for t in TREES if phrase not in read(t, rel)]
    check(f"{row}  {rel}  “{phrase[:58]}…”", not missing,
          f"absent from {', '.join(missing)}" if missing else "")

print("\n2. THE SUPERSEDED TEXT IS GONE, IN BOTH TREES")
for row, rel, phrase in FORBIDDEN:
    present = [t for t in TREES if phrase in read(t, rel)]
    check(f"{row}  {rel}  “{phrase[:58]}…”", not present,
          f"still in {', '.join(present)}" if present else "")

print("\n2b. THE ONE-TREE RULES — each in the tree it names, as it says")
for row, tree, rel, phrase, want in TREE_RULES:
    have = phrase in read(tree, rel)
    check(f"{row}  {tree}/{rel}  {'has' if want else 'lacks'}  “{phrase[:50]}…”", have == want,
          "" if have == want else ("absent" if want else "still present"))

print("\n3. THE ANTI-DRIFT TEXT WAS ADDED TO, NOT SOFTENED  (X3)")
for rel, phrase in PRESERVED:
    missing = [t for t in TREES if phrase not in read(t, rel)]
    check(f"survives verbatim  {rel}  “{phrase[:52]}…”", not missing,
          f"CHANGED in {', '.join(missing)}" if missing else "")

print("\n4. THE ADDED PROSE IS THE SAME IN BOTH TREES")
# Markdown prose is invisible to the parity check -- it compares scripts and the dictionary
# tables, nothing else -- so without this the two trees could drift here unnoticed.
for label, rel, start, end in [
    # This span now covers 5a AND 5b, so step 4's new prose is compared across trees by
    # the same assertion -- no second block needed, and no way to add a third sub-rule that
    # escapes it.
    ("rules 5a + 5b (scope rule and exception channel)", "SKILL.md",
     "   **5a. A check can be wrong IN SCOPE", "\n6. **Script-integrity errors."),
    ("the delivery-notes section", "SKILL.md",
     "## What the delivery notes must contain", "## Maintainer discipline"),
    # The bound is authored in step docs too, and those are NOT SKILL.md. The first version
    # of this list left the file hardcoded, so both new entries would have searched SKILL.md,
    # failed to locate, and reported "section not found" -- a check that fails for the wrong
    # reason is as bad as one that passes for the wrong reason.
    ("the bounded loop at skill Step 4b", "skill-docs/04b-translate-gates.md",
     "**THE REPAIR LOOP IS BOUNDED AT FIVE ATTEMPTS", "\nWarnings are printed"),
    ("the bounded loop at skill Step 9", "skill-docs/08-aux-and-quality.md",
     "**THAT LOOP IS BOUNDED AT FIVE ATTEMPTS", "\n**Do NOT silently strip"),
    # Step 14.9.2's prose, which no other check compares across the trees.
    ("the skill Step 1b conversion command", "skill-docs/01-setup-and-extract.md",
     "If the input is `.doc`, convert first:", "**After `.doc` → `.docx` conversion:**"),
    ("the skill Steps 1-2 closing list", "skill-docs/01-setup-and-extract.md",
     "## Internal compliance check — 01", "**Next:**"),
    ("the skill Steps 6-7 closing list", "skill-docs/06-postprocess-and-reorder.md",
     "## Internal compliance check — 06", "**Next:**"),
    ("the skill Steps 8-9 closing list", "skill-docs/08-aux-and-quality.md",
     "## Internal compliance check — 08", "**Next:**"),
    ("skill Step 11b and the Steps 10-11 closing list", "skill-docs/10-repack-and-validate.md",
     "#### Step 11b — Visual checks", "If any check is uncertain, STOP."),
    # Step 14.9.3's prose. Rule 2 names Clause or Section by tree, so its span stops short of it.
    ("the skill Step 4 seam pointer", "skill-docs/04-translate.md",
     "**A seam without whitespace has additional segment-shape rules.**",
     "Run `validate_segment_shapes.py` on the filled"),
    ("the seams appendix's opening box", "skill-docs/04-translate.md",
     "#### Sub-appendix: Seams without whitespace", "**TROUBLESHOOTING"),
    ("Rule 1's lone change", "skill-docs/04-translate.md",
     "   **A LONE ins or del", "   Worked example (verified on"),
    ("Rule 1's second example", "skill-docs/04-translate.md",
     "   Worked example for a lone alpha ins", "2. **A digit at a seam"),
    ("Rules 3 and 4", "skill-docs/04-translate.md",
     "3. **Articles live inside", "`validate_segment_shapes.py` (universal"),
    ("the skill Step 2 tab and line-break sentence", "skill-docs/01-setup-and-extract.md",
     "**A tab or a line break: what `text` shows", "This creates a JSON array"),
    ("the skill Step 4b WARN", "skill-docs/04b-translate-gates.md",
     "- **WARN** (exit 1)", "- **BLOCK** (exit 2)"),
    ("the date rule", "references/general-legal.md",
     "## Dates and Calendar Conventions", "Calendars commonly encountered"),
    ("SKILL.md's date bullet", "SKILL.md", "- **Date format**:", "- **Quotation conventions**"),
    # Step 14.9.4's prose.
    ("SKILL.md's anti-drift safeguard 3", "SKILL.md", "3. **Auto-invoked gates.**", "\n4. **Per-batch validation.**"),
    ("SKILL.md's ElementTree passage", "SKILL.md", "**Where this bites**", "**Do not**: use `xml.etree"),
    ("skill Step 4b's pointer to Step 5's gates", "skill-docs/04b-translate-gates.md",
     "**Pre-apply gates and the post-apply", "For a manual pre-flight check before Step 5"),
    ("skill Step 5's gate reading", "skill-docs/05-apply.md",
     "**Distinguishing skill gates from script errors.**", "```bash"),
    ("skill Step 9's --aux-dir", "skill-docs/08-aux-and-quality.md", "**`--aux-dir` is mandatory here", "**Variant flag"),
]:
    blocks = {}
    for t in TREES:
        s = read(t, rel)
        i, j = s.find(start), s.find(end)
        blocks[t] = s[i:j] if i >= 0 and j > i else None
    if None in blocks.values():
        check(f"{label} — locatable in both trees", False, "section not found")
        continue
    normalised = blocks["us"].replace(VARIANT_PAIR[1], VARIANT_PAIR[0])
    check(f"{label} — identical but for “{VARIANT_PAIR[0]}”/“{VARIANT_PAIR[1]}”",
          blocks["uk"] == normalised,
          "" if blocks["uk"] == normalised else "the trees have drifted in new prose")

print("\n5. THE REACHABILITY INSTRUMENT AGREES  (STEP-B §4.1, half one)")
r = subprocess.run([sys.executable, str(ROOT / "tools" / "reachability.py")],
                   capture_output=True, text=True, encoding="utf-8",
                   errors="replace", cwd=ROOT)
check("tools/reachability.py exits 0 — the scope rule is readable at every blocking step",
      r.returncode == 0, f"exit {r.returncode}")
check("and it reports BOTH gate rules in the ALWAYS-LOADED file, not a step doc",
      r.stdout.count("stated in: SKILL.md") == 2 * len(TREES),
      f"saw {r.stdout.count('stated in: SKILL.md')}, expected {2 * len(TREES)}")
check("and no repair-repeat instruction is left unbounded in either tree",
      r.stdout.count("still UNBOUNDED in prose: none") == len(TREES))

# --------------------------------------------------------------------------------------
# 6. THE NEGATIVES. A check that cannot fail is not a check.
# --------------------------------------------------------------------------------------
print("\n6. NEGATIVE TESTS — each check is shown to FAIL on a tree that violates it")


def with_mutation(rel, mutate, probe, base="uk"):
    """Apply a mutation, run `probe`, restore the original bytes. Never touches git. Through the
    guard (register I-37), so a run killed mid-probe cannot leave a shipped file mutated."""
    p = ROOT / base / rel if base else ROOT / rel
    text = p.read_bytes().decode("utf-8")
    changed = mutate(text)
    assert changed != text, "the mutation did not change the file"
    with guard.mutated(p, changed.encode("utf-8")):
        return probe()


# (a) remove the scope rule -> section 1 must notice, and so must reachability
def _probe_reach():
    rr = subprocess.run([sys.executable, str(ROOT / "tools" / "reachability.py")],
                        capture_output=True, text=True, encoding="utf-8",
                        errors="replace", cwd=ROOT)
    return rr.returncode


rc = with_mutation("SKILL.md",
                   lambda t: t.replace("A check can be wrong IN SCOPE, and saying so is "
                                       "not permission to bypass it",
                                       "A gate is always right"),
                   _probe_reach)
check("reachability FAILS when the scope rule is removed", rc == 1, f"exit {rc}")

# (b) soften the anti-drift text -> section 3 must notice
softened = with_mutation(
    "SKILL.md",
    lambda t: t.replace("**Do NOT work around a gate by patching the script or skipping "
                        "the validator**",
                        "**Try not to work around a gate**"),
    lambda: PRESERVED[0][1] in read("uk", "SKILL.md"))
check("the softening check FAILS when the absolutist sentence is watered down",
      softened is False)

# (c) let the trees drift in the new prose -> section 4 must notice
drifted = with_mutation(
    "SKILL.md",
    lambda t: t.replace("Fix the check, never work around it",
                        "Fix the check, or don't"),
    lambda: read("uk", "SKILL.md").find("Fix the check, never work around it") == -1)
check("the cross-tree prose check FAILS when one tree is edited alone", drifted is True)

# (d) string-only-edit must FAIL on a control-flow change, not just pass on a text one.
#
# BOTH ARMS NOW USE A PLANTED EDIT, AND THE REASON IS THAT THE OLD PAIR BROKE SILENTLY ON
# STEP 9. They were aimed at `post_process.py` and compared it against origin/main, on the
# premise that the only thing any branch had ever done to that file was reword a message.
# Step 9 added a change journal to it, and the pair came apart in BOTH directions at once:
# the PASS arm failed honestly, which is how this was found — but the FAIL arm went on
# reporting OK while testing nothing, because by then the file differed structurally from
# origin/main whether the mutation was applied or not. A check whose premise is "no future
# branch will ever touch this file" is a check with an expiry date nobody wrote down, and
# the arm that keeps passing is the more expensive half.
#
# So both arms are aimed at a script the instrument branches do NOT edit, and each plants
# its own difference: one a string, one a condition. The pair now calibrates the instrument
# instead of describing somebody's diff, and it does not go stale when a branch edits a
# script. `with_mutation` restores the bytes in a `finally` and never touches git.
STRING_ONLY_TARGET = "scripts/extract_paragraphs.py"
# AND THE BASELINE IS THE INDEX, NOT origin/main, FOR THE SAME REASON ONE LEVEL UP: "a script the
# instrument branches do not edit" stopped existing on 14.9.1 (C29), which gives all twenty a guard,
# and the third arm below went red as it was built to. The index holds the unmutated target on every
# branch that stages before it tests, as the house cycle does -- `git show :path`, an empty ref.
STRING_ONLY_BASE = ""


def _probe_string_only():
    rr = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "string_only_edit.py"), STRING_ONLY_BASE,
         "uk/" + STRING_ONLY_TARGET],
        capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=ROOT)
    return rr.returncode


clean_rc = with_mutation(
    STRING_ONLY_TARGET,
    lambda t: t.replace('print(f"Extracted {len(paragraphs)} paragraphs',
                        'print(f"Read apart {len(paragraphs)} paragraphs', 1),
    _probe_string_only)
flow_rc = with_mutation(
    STRING_ONLY_TARGET,
    lambda t: t.replace("    if len(sys.argv) != 3:",
                        "    if len(sys.argv) != 4:", 1),
    _probe_string_only)
check("string_only_edit PASSES on a planted text-only edit", clean_rc == 0,
      f"exit {clean_rc}")
check("string_only_edit FAILS when control flow changes", flow_rc == 1, f"exit {flow_rc}")
# AND THE THIRD READING THE PAIR NEVER TOOK: with nothing planted at all the answer must
# also be 0, which is what proves the two arms above differ because of the PLANT and not
# because the file was already dirty. Without it, a target that some other branch had
# edited would make the pass arm fail for a reason neither arm names.
check("and the unmutated file is itself clean against the index",
      _probe_string_only() == 0, f"exit {_probe_string_only()}")

# ---- STEP 4's negatives ------------------------------------------------------------
# (e) remove the exception channel -> reachability must notice it is unreachable. Rule 5a
#     surviving is not enough: 5a says a check can be WRONG, and an operator facing a check
#     that is RIGHT with no compliant repair gets no answer from it.
rc = with_mutation("SKILL.md",
                   lambda t: t.replace(
                       "the only sanctioned way a repair loop may end other than the "
                       "check passing",
                       "one option among several"),
                   _probe_reach)
check("reachability FAILS when the exception channel is removed", rc == 1, f"exit {rc}")

# (f) un-bound one of the four loop sites -> the sweep must notice. This is the negative
#     that matters most: the bound is what makes the channel mandatory rather than optional,
#     and a bound present in SKILL.md but absent where the loop is authored is exactly the
#     shape F41 recorded. Both phrasings have to go, or the site is still bounded.
rc = with_mutation("skill-docs/04b-translate-gates.md",
                   lambda t: t.replace("THE REPAIR LOOP IS BOUNDED AT FIVE ATTEMPTS",
                                       "ON REPAIR")
                              .replace("but at most five times — see the\n   bound below.",
                                       "as often as needed."),
                   _probe_reach)
check("reachability FAILS when a repair loop loses its bound", rc == 1, f"exit {rc}")

# (g) the sweep must not be satisfied by the bound sitting in a DIFFERENT file. Remove it
#     from 10-repack only; SKILL.md still carries rule 5b in full.
rc = with_mutation("skill-docs/10-repack-and-validate.md",
                   lambda t: t.replace("**This loop is bounded at five attempts, per "
                                       "`SKILL.md` rule 5b**", "**Take care**"),
                   _probe_reach)
check("and FAILS when only ONE site loses it, with rule 5b still intact", rc == 1,
      f"exit {rc}")

# (i) THE DISCLOSURE BLOCK, KEY BY KEY. A block missing one field is the realistic decay --
#     nobody deletes the whole thing, someone drops the line they found awkward to fill in.
#     "reader must" is the one to guard hardest: without it the note records that something
#     is wrong and leaves the reader with nothing to do about it, which is the trap rule 5b
#     names in its own text.
for key in ("reader must:", "attempts:", "where:"):
    # Probe the MUTATED tree only. The first version asked `any(... for t in TREES)`, so the
    # untouched US copy kept satisfying it and all three negatives reported a false FAIL --
    # a check whose own probe was looking in the wrong place.
    gone = with_mutation(
        "SKILL.md",
        lambda t, k=key: t.replace(f"     {k}", f"removed-{k}"),
        lambda k=key: f"     {k}" in read("uk", "SKILL.md"))
    check(f"the block check FAILS when the “{key}” line is dropped", gone is False)

# (j) and free prose must not be able to satisfy condition (c) again: the pointer from the
#     rule to the format is what stops the two drifting apart.
loose = with_mutation(
    "SKILL.md",
    lambda t: t.replace("in the fixed ACCEPTED CONSEQUENCE block set out there",
                        "in whatever form seems appropriate"),
    lambda: "in the fixed ACCEPTED CONSEQUENCE block set out there" in read("uk", "SKILL.md"))
check("and condition (c) FAILS if it stops pointing at the fixed block", loose is False)

# (h) gate_replay must VOID rather than pass when its reconciliation against CLAUDE.md's
#     baseline table breaks. That assertion is what turned a one-digit error in a published
#     table into a build failure, so it has to be shown to fail.
def _probe_replay():
    rr = subprocess.run([sys.executable, str(ROOT / "tools" / "gate_replay.py")],
                        capture_output=True, text=True, encoding="utf-8",
                        errors="replace", cwd=ROOT)
    return rr.returncode


live_rc = _probe_replay()
if live_rc == 2:
    check("gate_replay reconciles against the baseline table (logs reachable)", False,
          "VOID — logs not reachable, or the reconciliation failed")
else:
    check("gate_replay reconciles against the baseline table", live_rc == 0,
          f"exit {live_rc}")
    broke = with_mutation("tools/gate_replay.py",
                          lambda t: t.replace('"D03": (56, 1, 41)', '"D03": (56, 1, 40)'),
                          _probe_replay, base=None)
    check("and VOIDs when the published re-run column is wrong by one", broke == 2,
          f"exit {broke}")

# --------------------------------------------------------------------------------------
# 7. THE K2 MESSAGE, BY EXECUTION.
#
# Sections 1 and 2 search the source for a phrase. That proves the words are in the file,
# not that the operator ever sees them. This fires the real skill Step 6 post-strip drift gate on
# a real (synthetic) violation and reads what the gate actually prints -- which is the only
# way to know the edited string is on the path the operator hits. post_process.py has no
# case in tests/negative_inputs.py, so before this branch nothing had ever made this gate
# fire.
# --------------------------------------------------------------------------------------
print("\n7. THE skill STEP 6 GATE, FIRED FOR REAL — not a text search")

import json
import tempfile


# HOW A SKILL SCRIPT IS INVOKED, and this section had it wrong from the day it was written.
#
# 7 of the 20 skill scripts import lxml. Under `uv run`, sys.executable is an environment
# that does NOT carry it, so post_process.py died with ModuleNotFoundError before reaching
# any gate. The section's only structural assertion was `rc != 0` -- and a crash satisfies
# that as happily as a gate does. So it reported "the gate actually fires" on every run while
# nothing had ever fired: a check passing for the wrong reason, inside the one section
# written specifically to avoid that by executing rather than text-searching.
#
# tests/run_tests.py HAD ALREADY SOLVED THIS, with a comment saying why: it invokes every
# skill script as `uv run --with lxml python`. This file was added later and reached for
# sys.executable instead. That is the same shape as the __pycache__ leak the handoff records
# -- a shared hazard fixed in one caller and reintroduced through the next -- so the fix here
# is to use the SAME mechanism rather than invent a second one.
#
# The second half matters more than the first: assert the GATE BANNER, not the exit code, so
# no future breakage of this kind can be mistaken for a block.
SKILL_PY = ["uv", "run", "--with", "lxml", "python"]


def uv_available():
    try:
        return subprocess.run(["uv", "--version"], capture_output=True).returncode == 0
    except OSError:
        return False


PY = uv_available()

XML = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
       '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
       '<w:body><w:p><w:r><w:t>The Supplier shall deliver</w:t></w:r></w:p></w:body>'
       '</w:document>')
# Declared English that never reached the XML -- validate_apply --strict fails on it, which
# is what the post-strip gate re-runs. Synthetic, invented, deliberately bland.
PARAS = [{"idx": 0, "style": "Normal",
          "text": "De leverancier levert de goederen op tijd.",
          "en": "The Supplier shall deliver the goods punctually."}]

if not PY:
    for tree in TREES:
        check(f"{tree}: the skill Step 6 gate could be executed at all", False,
              "VOID — `uv` is not on PATH, so the gate scripts cannot be run with their "
              "lxml dependency. This is not a pass; the gate was never fired.")

for tree in TREES if PY else []:
    with tempfile.TemporaryDirectory() as tmp:
        wd = Path(tmp)
        (wd / "final" / "word").mkdir(parents=True)
        (wd / "final" / "word" / "document.xml").write_text(XML, encoding="utf-8")
        (wd / "paragraphs.json").write_text(json.dumps(PARAS), encoding="utf-8")
        # PYTHONDONTWRITEBYTECODE: running a skill script from inside the tree makes
        # CPython drop a __pycache__/ next to it, INSIDE the shipped tree. It is gitignored
        # so it cannot be committed -- but tools/package.py builds the .skill from the tree,
        # so the bytecode would ship to users. run_tests.py already sets this; the first
        # version of this file did not, and leaked into both trees on its first run. The
        # assertion after the loop is the part that matters: it catches the NEXT caller.
        # PYTHONIOENCODING/PYTHONUTF8 for the same reason run_tests.py sets them: on Windows
        # a redirected stdout defaults to cp1252 and a script printing outside it dies before
        # returning its verdict, which reads as a gate firing.
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1",
                   PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
        rr = subprocess.run(
            SKILL_PY + [str(ROOT / tree / "scripts" / "post_process.py"),
             str(wd / "final" / "word" / "document.xml"),
             "--paragraphs", str(wd / "paragraphs.json"), "--variant", tree],
            capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=ROOT,
            env=env)
        out = (rr.stdout or "") + (rr.stderr or "")
        # The script must not merely exit non-zero -- it must BLOCK. A crash exits non-zero
        # too, and that is precisely how this check used to pass while the script was dying
        # on a missing import before reaching any gate.
        #
        # NOT a blanket "no traceback" assertion, which the first version of this fix used
        # and which was wrong: this gate blocks by RAISING, so a traceback is its normal
        # designed output and the banner and remedy are inside the exception message. The
        # discriminator is a STARTUP failure -- the script never reached its own logic.
        started = "ModuleNotFoundError" not in out and "ImportError" not in out
        check(f"{tree}: the script started (no import failure)", started,
              "" if started else "died on a missing dependency before reaching the gate")
        check(f"{tree}: the gate actually fires",
              rr.returncode != 0 and "SKILL GATE FIRED" in out,
              f"exit {rr.returncode}, banner "
              f"{'present' if 'SKILL GATE FIRED' in out else 'ABSENT'}")
        check(f"{tree}: and prints the new remedy the operator will read",
              "WORK OUT WHICH OF THREE THINGS IS WRONG" in out)
        # AT RUNTIME, NOT MERELY IN THE FILE. The whole point of the widening is what the
        # operator READS at the moment it has to decide, so the third possibility and its
        # governing rule are asserted against the gate's actual output, not the source.
        check(f"{tree}: and names the third possibility — the check itself",
              "THIS CHECK IS WRONGLY SCOPED" in out)
        check(f"{tree}: and routes it to the rule that governs it",
              "rule 5a" in out)
        check(f"{tree}: and no longer prints the superseded one",
              "Fix paragraphs.json and re-run from Step 5" not in out)
        check(f"{tree}: and still refuses to be worked around",
              "Do NOT work around this gate" in out)

# --------------------------------------------------------------------------------------
# 8. NOTHING WAS LEFT BEHIND IN THE SHIPPED TREES.
#
# The handoff records this exact defect twice: "a __pycache__ leak into the shipped trees,
# fixed once and back through the next caller". It came back here too -- section 7 executes
# a skill script from inside the tree, and the first run of this file dropped bytecode into
# BOTH trees. Fixing only this caller is what failed last time, so the assertion is on the
# TREES, not on the caller: any tool that leaks, now or later, fails here.
#
# It is gitignored, so it can never be committed. That is not the risk. tools/package.py
# builds each .skill from the tree it finds on disk, so bytecode left lying around is
# bytecode shipped to a user.
# --------------------------------------------------------------------------------------
print("\n8. THE SHIPPED TREES ARE CLEAN — no bytecode, no scratch, left by anything above")
for tree in TREES:
    strays = sorted(p.relative_to(ROOT).as_posix()
                    for p in (ROOT / tree).rglob("*")
                    if p.is_file() and ("__pycache__" in p.parts or p.suffix == ".pyc"))
    check(f"{tree}/ carries no bytecode", not strays,
          f"{len(strays)} stray file(s): {strays[:3]}" if strays else "")

# --------------------------------------------------------------------------------------
# 9. EVERY QUOTED CROSS-REFERENCE RESOLVES  (register row F40, widened to a class)
#
# One misdirected pointer is a typo; two in different files is a class, and a class needs a
# check rather than another pair of eyes. The negative below is the part that matters: it
# breaks a citation the way the real ones were broken -- by dropping words from the middle
# of a quoted title -- and asserts the check notices.
# --------------------------------------------------------------------------------------
print("\n9. QUOTED CROSS-REFERENCES RESOLVE TO REAL HEADINGS  (F40)")


def _probe_xref():
    rr = subprocess.run([sys.executable, str(ROOT / "tools" / "xref_check.py")],
                        capture_output=True, text=True, encoding="utf-8",
                        errors="replace", cwd=ROOT)
    return rr.returncode


check("tools/xref_check.py exits 0 — no citation points at nothing", _probe_xref() == 0)

broken = with_mutation(
    "SKILL.md",
    # Drop "and typo-fix" back out, which is exactly how the four real instances failed.
    lambda t: t.replace('See "Collapsing orthographic-only and typo-fix\n   TC edits',
                        'See "Collapsing orthographic-only\n   TC edits'),
    _probe_xref)
check("and it FAILS when a quoted title loses a word from the middle", broken == 1,
      f"exit {broken}")

# --------------------------------------------------------------------------------------
print()
print("=" * 96)
ok = sum(1 for _, c in results if c)
print(f"RESULT: {ok} of {len(results)} checks passed")
for n, c in results:
    if not c:
        print(f"    FAILED: {n}")
print()
print("  WHAT THIS DOES NOT PROVE: that an operator meeting a wrongly-scoped gate will")
print("  now do the right thing. That is behavioural, it needs a model in the loop, and")
print("  PLAN-2-step-b.md §4.1 puts it at phase 3's test. This proves the rule is there, says")
print("  what the register requires, is in both trees, and softened nothing.")
print("=" * 96)
sys.exit(0 if ok == len(results) else 1)
