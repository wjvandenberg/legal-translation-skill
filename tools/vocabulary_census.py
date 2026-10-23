# -*- coding: utf-8 -*-
"""vocabulary_census.py - the house's words, held: no OLD word left in a swept document's living text.

Wouter, 2026-10-13 (DECISIONS-LOG.md (5)): this project's "step" became PHASE, its "branch" STEP, a "slice" a
SUB-STEP; living text takes the new words, dated records keep theirs. Each rename commit adds the document it swept
to SWEPT, with every record span it leaves alone and why. This is that commit's acceptance, and every later
commit's guard: an old word put back into living text turns it red.

WHAT IT COUNTS, in living text only: a project branch with its number (`branch 7`, `BRANCHES 15`, `branch D2`),
any `slice`, and the dropped Step C (`Step C`, `the verification run`). WHAT IT CANNOT COUNT, said so a green run is
not read as more: an old `step 3` meaning phase 3 - `step 3` is legitimate new text - so that half of a sweep is
proved by the sweep reversing itself byte-identical, never by this count; a bare `branch` with no number, which
is also git's word (branch protection, a PR per branch) and is judged by reading; and the skill's own `Step 5` left
unprefixed - once the project's steps are `step N`, a capitalised `Step 14` at a sentence's start is the project's,
so the two cannot be told apart by pattern, and `skill Step N` is held by reading.

SWEPT so far: CLAUDE.md, rename commit (b1), 2026-10-14; PLAN-2-step-b.md, rename commit (b2), 2026-10-19 - its split
Wouter's of that day: Part One's live text and Part Three's look-up are living; each option's verdict and build
record after its FOR THE BUILD brief, 9.3's rows and Parts Two and Four keep their words, the document's own front
matter declaring Parts Two to Four the record. evidence/REGISTER-findings.md, rename (c), 2026-10-21 - its split
Wouter's of that day: the header, the open rows and the clusters' live prose are living; THE ROW IS THE UNIT, so a
skill-finding row whose own text records its closure is a record whole, and so is an instrument row whose status
cell says fixed; a row still open, partly closed, deferred or standing, and a positive, are living whole. Rename (d1),
2026-10-21 (2), Wouter's of that day: EVERY living document outside the shipped trees and tools/ and tests/ (whose
text is rename (d2)'s) joins, an old word in it or none, so a word put back anywhere is caught - the evidence
documents, verify.config.json, .gitattributes, every skill and rule, README.md and .gitignore; the A3 analysis and the
superseded Opus 5 plan are records whole; a dated declaration is a record, as a dated comment is in code; a record
span is declared only where a record holds an old word, counted or read. AND A TRACKED DOCUMENT IN THAT SCOPE THAT IS
NEITHER SWEPT NOR A RECORD BY KIND TURNS THE CENSUS VOID (code review of #169): a fixed list would leave a new skill,
rule or evidence document outside the guard while the census read green. A span that matches nothing, or a heading
prefix that matches more than one heading, is refused as stale: a declaration that quietly covers nothing would read
as a clean census. So is a declared phrase that occurs nowhere in living text.

    uv run python tools/vocabulary_census.py             # every swept document; exit 0 clean, 1 an old word, 3 VOID
    uv run python tools/vocabulary_census.py --selftest  # red on a planted old word, green on one planted in a record
    uv run python tools/vocabulary_census.py --list-pending  # also name the code files rename (d2) has still to sweep
"""
import io
import re
import subprocess
import sys
import tokenize
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
from sibling_dirs import beside  # noqa: E402  (register I-40)
SHAPES = [
    ("branch N", re.compile(r"\b(?:[Bb]ranch(?:es)?|BRANCH(?:ES)?)\s+(?:\d+|D[1-3])\b")),
    ("slice", re.compile(r"\b(?:[Ss]lices?|SLICES?)\b")),
    ("Step C", re.compile(r"\bStep C\b|\bverification run\b")),
]
# document -> record spans: (kind, anchor, why). kind: 'paragraph' (the block of non-blank lines that holds the
# anchor), 'section' (from the heading that IS the anchor to the next heading of the same or a higher level),
# 'line' (any line matching the anchor as a regex), 'heading' (as 'section', the ONE heading that starts with the
# anchor), 'brief-tail' (anchor (heading prefix, brief prefix): that section after the paragraph opening with the
# brief prefix - the brief itself stays living) and 'range' (anchor (start prefix, end prefix or None): from the ONE
# heading starting with the first up to the ONE starting with the second, or to the end). And 'phrase' (anchor an
# exact phrase): NOT a record - the line stays living and only that phrase is masked, for a word used in its own
# sense rather than the project's (a string "slice", a run that verifies), so a project word beside it still counts.
BRIEF = "> **FOR THE BUILD"
# the register's skill-finding rows whose own text records their closure, judged row by row by reading each status
# phrase (rename (c), 2026-10-21); a row that closes later is written in the new words and need not join this list
REGISTER_CLOSED = """A2 A16 A23 B1 B2 B3 B4 B5 B6 B7 B8 B9 B10 C1 C2 C4 C6 C7 C8 C9 C13 C14 C15 C17 C18 C19 C22 C28
C30 D3 E4 E15 E16 F6 F15 F16 F29 F43 F45 F47 F48 G5 G10 G11 H1 H2 H3 H4 J1 J2 L1 L5 S1 S2 S3 R1 R2 N1""".split()
SWEPT = {
    "CLAUDE.md": [
        ("paragraph", "**THE HOUSE'S WORDS, SINCE 2026-10-13**", "the mapping must name the old words it maps"),
        ("section", "### 2.3 What has been done", "the strands' dated record (ruling 3: records keep their words)"),
        ("line", r"^\| 20\d\d-\d\d-\d\d \|", "section 2.5's dated decisions keep the words they were taken in"),
        ("line", r"^\| \*\*`PLAN-3-opus5-migration\.md`\*\*", "names what the superseded Opus 5 plan holds"),
    ],
    "PLAN-2-step-b.md": [
        ("line", r"^\*\*SESSION PURPOSE — 20", "earlier sessions' purpose lines, each dated"),
        ("paragraph", "> **THIS DOCUMENT IS STEP 2'S PLAN FILE", "the 2026-09-10 rename and over-cap record"),
        ("paragraph", "> **Phase 3, Step B. THE EXPLORATION IS COMPLETE", "the 2026-08-05 preface: how it was made"),
        ("paragraph", "> **CORRECTED 2026-08-05, and the correction matters", "a dated correction"),
        ("paragraph", "> **AND A FOURTH, ADDED 2026-08-19", "a dated addition to the order, since discharged"),
        ("paragraph", "> **THIS GATE IS DISCHARGED, 2026-08-20", "the discharged gate, preserved as written"),
        ("paragraph", "**The four open defects in our own tooling belong to branch 1",
         "step 1's added scope, the deep audit's of 2026-08-05; step 1 is closed"),
        ("heading", "### The record, option by option", "the verdict record, option by option"),
        ("heading", "### 3.1 ", "the dropped fork's record: no brief"),
    ] + [("brief-tail", (f"### 3.{n} ", BRIEF), "the verdict and build record after the brief") for n in range(2, 12)] + [
        ("heading", "### 3.12 ", "a standing rule's record: no brief"),
        ("heading", "### 3.13 ", "a procedural record: no brief"),
        ("line", (r"^\| (?:\d|deferred: |standalone )", "### 9.3 "),
         "9.3's rows: their cells carry dated closure notes"),
        ("paragraph", "> **THIS LINE WAS STALE BY TWO", "a dated correction"),
        ("paragraph", "> **Regenerated 2026-08-05 by the deep audit", "a dated regeneration note"),
        ("range", ("## PART TWO ", "## PART THREE "), "Part Two, the case: the front matter declares it the record"),
        ("range", ("## PART FOUR ", None), "Part Four, the record"),
    ],
    "evidence/REGISTER-findings.md": [
        ("line", (r"^\| (?:" + "|".join(REGISTER_CLOSED) + r") \|", "## Register"),
         "skill-finding rows whose own text records their closure: the row is the unit"),
        ("line", (r"^\| I-\d+ \|.*\| fixed[^|]*\|\s*$", "## Measurement-instrument defects"),
         "instrument rows whose status cell says fixed"),
        ("phrase", "APPLY SLICES THE STRIPPED", "A20: string slicing, the defect's own mechanism"),
        ("phrase", "then slices *that*", "A20: string slicing"),
        ("phrase", "each span slices its neighbour", "A20: string slicing"),
        ("phrase", "the string apply slices", "A20: string slicing"),
        ("phrase", "OWN slice edge", "C16: a segment's slice of the string"),
        ("phrase", "onto the translated slice", "G9: a segment's slice of the string"),
        ("phrase", "*read-only* verification run", "I-7: a run that verifies, not the dropped Step C"),
    ],
    "evidence/EVIDENCE-a3-structure.md": [
        ("range", ("# A3 ", None), "every paragraph dated - the 2026-07-31 analysis, its corrections and additions - and "
         "its 'branch 2' names the register's July order, which no step number now means: a record whole"),
    ],
    "PLAN-3-opus5-migration.md": [
        ("range", ("# PLAN-3-opus5-migration.md ", None), "SUPERSEDED 2026-10-13 by its own header: a record whole"),
    ],
    "evidence/EVIDENCE-confidentiality.md": [
        ("paragraph", "> **SUBSTANTIALLY MITIGATED 2026-08-11", "a dated mitigation note"),
    ],
    "evidence/EVIDENCE-measurement.md": [
        ("heading", "### 3.5 ", "the 2026-08-06 cost story, dated"),
    ],
    "verify.config.json": [
        ("line", r'^\s*"verify_code\.py::::commit author identity": "PRE-EXISTING AND DEFERRED BY WOUTER, 2026-09-09',
         "Wouter's dated deferral: a dated declaration is a record"),
        ("line", r'^\s*"section_caps": "Section 7 is the handoff', "the section caps' dated re-set record"),
    ],
    ".gitattributes": [],
    "README.md": [],
    ".gitignore": [],
    ".claude/skills/audit-gate/SKILL.md": [],
    ".claude/skills/frozen-intermediate-test/SKILL.md": [],
    ".claude/skills/input-point-2-review/SKILL.md": [],
    ".claude/skills/publish-skill-archives/SKILL.md": [],
    ".claude/rules/gates.md": [],
    ".claude/rules/instruments.md": [],
    ".claude/rules/ooxml.md": [],
    ".claude/rules/skill-authoring.md": [],
    ".claude/rules/verification.md": [],
}
# records by their kind keep their words whole and are never swept (DECISIONS-LOG.md, 2026-10-13 (5), ruling 3)
RECORDS_BY_KIND = ("DECISIONS-LOG.md", "evidence/EVIDENCE-phase2-history.md")
# the shipped trees mean only their own steps; tools/ and tests/ are code, their text rename (d2)'s
OUT_OF_SCOPE = ("uk/", "us/", "tools/", "tests/")
CONFIG_DOCS = (".gitattributes", ".gitignore", "verify.config.json")


def unjudged(tracked):
    """Every tracked document in scope - a .md outside the shipped trees and the code, or one of the configuration
    files that carry prose - that is neither in SWEPT nor a record by kind."""
    return sorted(f for f in tracked if not f.startswith(OUT_OF_SCOPE) and (f.endswith(".md") or f in CONFIG_DOCS)
                  and f not in SWEPT and f not in RECORDS_BY_KIND)


def tracked_files():
    r = subprocess.run(["git", "-c", "core.quotePath=false", "ls-files"], cwd=ROOT, capture_output=True)
    if r.returncode != 0:
        raise OSError(f"git ls-files exited {r.returncode}")
    return r.stdout.decode("utf-8").splitlines()


# THE CODE ARM - rename (d2), Wouter's 2026-10-21 ruling (2): in the tracked Python of tools/ and tests/, read by
# Python's own tokenizer and never by a pattern on the line, every string is living - printed text and needles, an
# f-string's literal parts included (3.12+ tokenizes them apart from STRING) - and so is every comment that carries no
# date; identifiers, file names and git branch names never move and are never read. THE COMMENT BLOCK IS THE UNIT: a
# dated note runs over several comment lines and carries its date on one, so a block of comments each alone on its
# line, on consecutive lines, any one of which carries a date is a record whole; a comment trailing code is a unit of
# its own (code review of #170: consecutive trailing comments are no one note). A word kept in its own sense (Python's
# own slice) or inside a quotation of a record is declared as a 'phrase', as for a document - matched within ONE line,
# so a phrase wrapped across two lines of a string cannot be declared. The house's copies are fixed in the house,
# never here: the selftest holds this list against the shared standard-scripts folder. Each (d2) pull request adds the
# files it swept whole; the rest are counted as pending, by name with --list-pending.
DATE = re.compile(r"20\d\d-\d\d-\d\d")
HOUSE_COPIES = {"verify_md.py", "verify_charter.py", "verify_code.py", "verify_deliverable.py", "verify_expected.py",
                "verify_confidential.py", "cycle_evidence.py", "check_checkers.py", "run_tests.py", "auto_mode.py",
                "auto_mode_guard.py", "auto_mode_headless.py", "purpose_guard.py", "install_hooks.py",
                "house_common.py", "trace_instructions.py"}
SHARED = beside("templates") / "standard-scripts"   # beside the MAIN checkout, a worktree too (register I-40)
CODE_SWEPT = {
    # rename (d2a), 2026-10-21 (2): the four files the 2026-10-21 close named - stepb_verify's printed labels beside
    # its needles, and the three whose comments restated a phrase rename (c) changed
    "tools/stepb_verify.py": [],
    "tools/reachability.py": [],
    "tools/stepb_audit.py": [],
    "tests/probe-5b/make_probe_documents.py": [],
    # rename (d2c), batch 1, 2026-10-23: the tests holding up to nine counted old words and those holding none, the
    # probe pre-flight pair and the seven largest left for the next session - 150 logged swaps in 27 of these 48
    "tests/docx_census.py": [],
    "tests/negative_inputs.py": [],
    "tests/run_tests.py": [],
    "tests/test_admission_envelope.py": [],
    "tests/test_baseline_unmodified.py": [],
    "tests/test_charter_pointers.py": [],
    "tests/test_check_scoping.py": [],
    "tests/test_check_scoping_properties.py": [],
    "tests/test_checks_can_fail.py": [],
    "tests/test_claims_contents_cut.py": [],
    "tests/test_claims_counts_moved.py": [],
    "tests/test_claims_script_names.py": [],
    "tests/test_committability_probe.py": [],
    "tests/test_container_inventory.py": [],
    "tests/test_corpus_fingerprint.py": [],
    "tests/test_cycle_gate.py": [],
    "tests/test_declared_gaps.py": [],
    "tests/test_declared_language.py": [],
    "tests/test_document_language.py": [],
    "tests/test_evidence_guard.py": [
        ("phrase", 'the slice would run', 'a stretch of text between two headings, not a sub-step'),
    ],
    "tests/test_extraction_completeness.py": [],
    "tests/test_gate_tree_scan.py": [],
    "tests/test_glossary_route.py": [],
    "tests/test_keep_declarations.py": [],
    "tests/test_language_module_integrity.py": [],
    "tests/test_lexicon_choice.py": [],
    "tests/test_md_tables.py": [],
    "tests/test_no_bytecode_in_tree.py": [],
    "tests/test_no_delivered_byte_moves.py": [],
    "tests/test_no_document_moves.py": [],
    "tests/test_no_unguarded_restore.py": [],
    "tests/test_notes_gates.py": [
        ("phrase", "SLICE 4b's WRITTEN PLAN", "a quotation of the build plan's dated heading, which keeps its words"),
    ],
    "tests/test_parity_check.py": [],
    "tests/test_pass_conditions.py": [],
    "tests/test_pre_push_hook.py": [],
    "tests/test_precommit_gate.py": [],
    "tests/test_ratio_check.py": [],
    "tests/test_render_keep.py": [
        ("phrase", 'Branch 7 rendered comparison', "a needle: render_diff's old text must stay gone"),
        ("phrase", 'a slice of rp.stderr', "Python's own built-in sense"),
    ],
    "tests/test_repack_scrub_and_block.py": [],
    "tests/test_runner_names_every_suite.py": [],
    "tests/test_shipped_tables.py": [],
    "tests/test_sibling_dirs.py": [],
    "tests/test_sibling_import_integrity.py": [],
    "tests/test_step10_wiring.py": [],
    "tests/test_strip_noop_guard.py": [],
    "tests/test_toc_shapes.py": [],
    "tests/test_variant_conversion.py": [],
    "tests/test_whitespace_and_offsets.py": [
        ("phrase", 'own slice edge', "a segment's string bounds, the guard's own subject"),
    ],
    # rename (d2b), 2026-10-23: every tool of this project's own but the census, which joins last by phrases - 317
    # logged swaps in 24 of them, the other 18 holding no old word in living text
    "tools/apply_corpus_diff.py": [],
    "tools/audit_branches.py": [
        ("phrase", "audit_branches.py --branch 0", "its usage line: git's own --branch flag"),
    ],
    "tools/audit_register.py": [],
    "tools/changelog_confidentiality.py": [],
    "tools/check_coverage.py": [],
    "tools/claudemd_claims.py": [],
    "tools/claudemd_disposal.py": [],
    "tools/confirm_failure_chains.py": [],
    "tools/corpus_fingerprint.py": [],
    "tools/delivered_corpus_arm.py": [],
    "tools/descriptor_shape_sweep.py": [],
    "tools/evidence_ls.py": [],
    "tools/extraction_corpus_arm.py": [],
    "tools/freeze_intermediates.py": [],
    "tools/gate_replay.py": [],
    "tools/hf_corpus_diff.py": [],
    "tools/hooks/evidence_guard.py": [],
    "tools/inplace_guard.py": [],
    "tools/install_project_hooks.py": [],
    "tools/keep_declarations.py": [],
    "tools/leakage_scan.py": [],
    "tools/md_tables.py": [],
    "tools/notes_corpus_arm.py": [],
    "tools/numbering_corpus_arm.py": [],
    "tools/parity_check.py": [],
    "tools/postprocess_corpus_arm.py": [],
    "tools/precommit_gate.py": [],
    "tools/publication_check.py": [],
    "tools/qc_census.py": [],
    "tools/ratio_corpus_arm.py": [],
    "tools/render_diff.py": [],
    "tools/scan_trees.py": [],
    "tools/script_committability.py": [],
    "tools/sibling_dirs.py": [],
    "tools/stepb_audit3.py": [],
    "tools/stepb_harvest.py": [],
    "tools/stepb_metacheck.py": [
        ("phrase", "branch 19, the last of the twenty", "a mutation of a dated record line in the build plan"),
        ("phrase", "branch 27, the last of the twenty", "the same mutation, its planted variant"),
    ],
    "tools/stepb_refute.py": [],
    "tools/string_only_edit.py": [],
    "tools/verify_charter_continuity.py": [],
    "tools/xdoc_signs.py": [],
    "tools/xref_check.py": [],
    # THE CENSUS LAST, BY PHRASES, NO SWAP: every old word in its own living text is a MENTION - the words it counts,
    # the register's phrases it keeps, the phrases kept above, and its selftest's plants, all in the one form 'a
    # planted ...'. Masked in this order, so the longer docstring phrase goes before the shorter one inside it. KNOWN
    # LIMIT: a phrase declared here always matches its own declaration, so the stale-phrase refusal cannot fire for
    # this one file - a phrase whose other occurrence is gone stays declared until somebody reads this list.
    "tools/vocabulary_census.py": [
        ("phrase", '"slice"', "the word in quotes, as the docstring and a label name it"),
        ("phrase", "(`branch 7`, `BRANCHES 15`, `branch D2`)", "the docstring's examples of what is counted"),
        ("phrase", "any `slice`", "the docstring's example"),
        ("phrase", "the dropped Step C (`Step C`, `the verification run`)", "the docstring's examples"),
        ("phrase", "|SLICES?)", "the counting pattern itself"),
        ("phrase", '"Step C"', "the counting pattern's label"),
        ("phrase", "tooling belong to branch 1", "a record paragraph's anchor in the register"),
        ("phrase", "APPLY SLICES THE STRIPPED", "a register phrase kept in its own sense"),
        ("phrase", "then slices *that*", "a register phrase kept in its own sense"),
        ("phrase", "each span slices its neighbour", "a register phrase kept in its own sense"),
        ("phrase", "the string apply slices", "a register phrase kept in its own sense"),
        ("phrase", "OWN slice edge", "a register phrase kept in its own sense"),
        ("phrase", "onto the translated slice", "a register phrase kept in its own sense"),
        ("phrase", "*read-only* verification run", "a register phrase kept in its own sense"),
        ("phrase", "a segment's slice of the string", "the reason given for two of them"),
        ("phrase", "the dropped Step C", "the reason given for another"),
        ("phrase", "its 'branch 2' names", "the A3 analysis's record, quoted in its reason"),
        ("phrase", "audit_branches.py --branch 0", "a phrase kept above, declared here"),
        ("phrase", "branch 19, the last of the twenty", "a phrase kept above, declared here"),
        ("phrase", "branch 27, the last of the twenty", "a phrase kept above, declared here"),
        ("phrase", "a planted branch", "the selftest's plants"),
        ("phrase", "a planted slice", "the selftest's plants"),
        ("phrase", "a planted Step C", "the selftest's plants"),
        ("phrase", "four slices", "a quotation of a dated verdict the selftest anchors on"),
        ("phrase", "slice(1, 2)", "Python's own built-in, in a planted source"),
        ("phrase", "slices the text", "Python's own sense, in a planted source"),
        ("phrase", "the slice would run", "a phrase kept for a test, declared here"),
        ("phrase", "SLICE 4b's WRITTEN PLAN", "a phrase kept for a test, declared here"),
        ("phrase", "Branch 7 rendered comparison", "a phrase kept for a test, declared here"),
        ("phrase", "a slice of rp.stderr", "a phrase kept for a test, declared here"),
        ("phrase", "own slice edge", "a phrase kept for a test, declared here"),
    ],
}
_TEXT_TOKENS = {tokenize.STRING} | {getattr(tokenize, n) for n in ("FSTRING_MIDDLE", "TSTRING_MIDDLE")
                                    if hasattr(tokenize, n)}


def code_living(src):
    """(line, text) for every living piece of a Python source: each line of each string token (an f-string's literal
    parts included), and each line of a comment block that carries no date anywhere in it."""
    out, block = [], []

    def flush():
        if block and not any(DATE.search(t.string) for t in block):
            out.extend((t.start[0], t.string) for t in block)
        block.clear()
    for t in tokenize.generate_tokens(io.StringIO(src.replace("\r\n", "\n")).readline):
        if t.type == tokenize.COMMENT:
            if block and t.start[0] != block[-1].start[0] + 1:
                flush()
            if not t.line.lstrip().startswith("#"):     # trailing code: a unit of its own
                flush()
                block.append(t)
                flush()
                continue
            block.append(t)
        elif t.type in _TEXT_TOKENS:
            out.extend((t.start[0] + k, part) for k, part in enumerate(t.string.split("\n")))
    flush()
    return out


def code_census(name, src, spans):
    living = code_living(src)
    phrases = [anchor for kind, anchor, _ in spans if kind == "phrase"]
    if len(phrases) != len(spans):
        raise LookupError(f"{name}: a code file declares phrases only - the comment block's date decides a record")
    seen = dict.fromkeys(phrases, 0)
    hits = []
    for n, piece in living:
        for p in phrases:
            seen[p] += piece.count(p)
            piece = piece.replace(p, " " * len(p))
        hits += [(n, label, m.group(0)) for label, rx in SHAPES for m in rx.finditer(piece)]
    stale = [p for p, c in seen.items() if not c]
    if stale:
        raise LookupError(f"{name}: phrase {stale[0]!r} occurs nowhere in living text - the declaration is stale")
    return len(living), hits


def code_scope(tracked):
    """The tracked Python the code arm owns: tools/ and tests/, the house's copies apart - by PATH, since they live in
    tools/ only and tests/run_tests.py, this project's own suite runner, shares a name with the house's."""
    house = {f"tools/{n}" for n in HOUSE_COPIES}
    return sorted(f for f in tracked if f.startswith(("tools/", "tests/")) and f.endswith(".py") and f not in house)


def run_code(tracked):
    scope = set(code_scope(tracked))
    wrong = sorted(set(CODE_SWEPT) - scope)
    if wrong:
        raise LookupError(f"code file(s) in CODE_SWEPT that are not tracked project Python: {wrong}")
    bad = 0
    for name, spans in CODE_SWEPT.items():
        living, hits = code_census(name, (ROOT / name).read_bytes().decode("utf-8"), spans)
        kept = f", {len(spans)} phrase(s) kept" if spans else ""
        print(f"  {name}: {living} living piece(s){kept}, {len(hits)} old word(s)")
        for n, label, word in hits:
            print(f"    line {n}: {label} - {word!r}")
        bad += len(hits)
    print(f"  code: {len(CODE_SWEPT)} of {len(scope)} project Python file(s) in tools/ and tests/ swept, "
          f"{len(scope) - len(CODE_SWEPT)} pending rename (d2)")
    return len(CODE_SWEPT), bad


def _level(line):
    return len(line) - len(line.lstrip("#"))


def _one_heading(lines, prefix):
    hits = [i for i, l in enumerate(lines) if l.startswith("#") and l.strip().startswith(prefix)]
    if len(hits) != 1:
        raise LookupError(f"heading prefix {prefix!r} matched {len(hits)} headings - it must match exactly one")
    return hits[0]


def _section_end(lines, i):
    j = i + 1
    while j < len(lines) and not (lines[j].startswith("#") and _level(lines[j]) <= _level(lines[i])):
        j += 1
    return j


def exempt_lines(lines, spans):
    out = set()
    for kind, anchor, _ in spans:
        if kind == "heading":
            i = _one_heading(lines, anchor)
            hits = list(range(i, _section_end(lines, i)))
            out |= set(hits)
        elif kind == "brief-tail":
            head, brief = anchor
            i = _one_heading(lines, head)
            j = _section_end(lines, i)
            k = next((x for x in range(i + 1, j) if lines[x].startswith(brief)), None)
            if k is None:
                raise LookupError(f"brief-tail {head!r} holds no paragraph opening {brief!r} - the declaration is stale")
            while k + 1 < j and lines[k + 1].strip():
                k += 1
            hits = list(range(k + 1, j))
            out |= set(hits)
        elif kind == "range":
            start, end = anchor
            a = _one_heading(lines, start)
            b = _one_heading(lines, end) if end else len(lines)
            hits = list(range(a, b))
            out |= set(hits)
        elif kind == "line":
            # a bare regex reads the whole document; (regex, heading prefix) only the ONE section under that heading
            # (code review, 2026-10-19: a document-wide row pattern also exempted rows of unrelated tables)
            rx, scope = anchor if isinstance(anchor, tuple) else (anchor, None)
            if scope is None:
                where = range(len(lines))
            else:
                i = _one_heading(lines, scope)
                where = range(i, _section_end(lines, i))
            hits = [i for i in where if re.search(rx, lines[i])]
            out |= set(hits)
        elif kind == "paragraph":
            # the paragraph must OPEN with the anchor: one that merely quotes it is living text (code review)
            hits = [i for i, l in enumerate(lines) if l.startswith(anchor) and (i == 0 or not lines[i - 1].strip())]
            for i in hits:
                a = i
                while a > 0 and lines[a - 1].strip():
                    a -= 1
                b = i
                while b + 1 < len(lines) and lines[b + 1].strip():
                    b += 1
                out |= set(range(a, b + 1))
        elif kind == "section":
            hits = [i for i, l in enumerate(lines) if l.strip() == anchor]
            level = len(anchor) - len(anchor.lstrip("#"))
            for i in hits:
                j = i + 1
                while j < len(lines) and not (lines[j].startswith("#") and
                                              len(lines[j]) - len(lines[j].lstrip("#")) <= level):
                    j += 1
                out |= set(range(i, j))
        if not hits:
            raise LookupError(f"record span {kind} {anchor!r} matched nothing - the declaration is stale")
    return out


def census(name, text, spans):
    lines = text.replace("\r\n", "\n").split("\n")
    skip = exempt_lines(lines, [s for s in spans if s[0] != "phrase"])
    living = [(n + 1, l) for n, l in enumerate(lines) if n not in skip]
    phrases = [anchor for kind, anchor, _ in spans if kind == "phrase"]
    seen = dict.fromkeys(phrases, 0)
    masked = []
    for n, l in living:
        for p in phrases:
            seen[p] += l.count(p)
            l = l.replace(p, " " * len(p))
        masked.append((n, l))
    stale = [p for p, c in seen.items() if not c]
    if stale:
        raise LookupError(f"phrase {stale[0]!r} occurs nowhere in living text - the declaration is stale")
    hits = [(n, label, m.group(0)) for n, l in masked for label, rx in SHAPES for m in rx.finditer(l)]
    return len(lines), len(living), hits


def closed_ids_stale(text):
    """REGISTER_CLOSED ids that do not start exactly one register row: the alternation's span is refused only when it
    matches nothing at all, so a single mistyped or renumbered id would otherwise cover nothing in silence."""
    lines = text.replace("\r\n", "\n").split("\n")
    return [i for i in REGISTER_CLOSED if sum(1 for l in lines if l.startswith(f"| {i} |")) != 1]


def run(docs):
    bad, examined = 0, 0
    for name, (text, spans) in docs.items():
        stale = closed_ids_stale(text) if name == "evidence/REGISTER-findings.md" else []
        if stale:
            raise LookupError(f"closed row id(s) {stale} start no row, or more than one - the declaration is stale")
        total, living, hits = census(name, text, spans)
        examined += 1
        nphrase = sum(1 for s in spans if s[0] == "phrase")
        kept = f", {nphrase} phrase(s) kept in their own sense" if nphrase else ""
        print(f"  {name}: {living} living line(s) of {total}, {len(spans) - nphrase} record span(s) declared{kept}, "
              f"{len(hits)} old word(s)")
        for n, label, word in hits:
            print(f"    line {n}: {label} - {word!r}")
        bad += len(hits)
    return examined, bad


def selftest():
    text = (ROOT / "CLAUDE.md").read_bytes().decode("utf-8")
    spans = SWEPT["CLAUDE.md"]
    lines = text.replace("\r\n", "\n").split("\n")
    living_at = next(i for i, l in enumerate(lines) if l.startswith("### 3.2 "))
    record_at = next(i for i, l in enumerate(lines) if l.strip() == "### 2.3 What has been done") + 2
    checks = []
    for where, at, want, word in (("living", living_at, 1, "a planted branch 7 line"),
                                  ("living", living_at, 1, "a planted slice line"),
                                  ("living", living_at, 1, "a planted Step C line"),
                                  ("record", record_at, 0, "a planted branch 7 line")):
        planted = list(lines)
        planted.insert(at + 1, word)
        _, _, hits = census("CLAUDE.md", "\n".join(planted), spans)
        base = census("CLAUDE.md", text, spans)[2]
        checks.append((f"{word!r} planted in {where} text is {'counted' if want else 'left alone'}",
                       len(hits) - len(base) == want))
    # the build plan, rename (b2): counted in a brief and in section 2; left alone in a brief's record tail, in Part
    # Two and in a 9.3 row; and each new span kind refused when its declaration has gone stale
    ptext = (ROOT / "PLAN-2-step-b.md").read_bytes().decode("utf-8")
    pspans = SWEPT["PLAN-2-step-b.md"]
    plines = ptext.replace("\r\n", "\n").split("\n")
    pbase = len(census("PLAN-2-step-b.md", ptext, pspans)[2])

    def at(pred):
        return next(i for i, l in enumerate(plines) if pred(l))
    head_32 = at(lambda l: l.startswith("### 3.2 "))
    brief_32 = next(i for i in range(head_32, len(plines)) if plines[i].startswith(BRIEF))
    order = at(lambda l: l.startswith("### The order, and what owns it"))
    tail_32 = at(lambda l: l.startswith("**Wouter's verdict, in his words:**") and "four slices" in l)
    part_two = at(lambda l: l.startswith("## PART TWO ")) + 2
    row_93 = at(lambda l: l.startswith("| 13 declared modes |"))
    for where, i, want, word in (("a brief", brief_32, 1, "> a planted branch 7 line"),
                                 ("section 2", order, 1, "a planted slice line"),
                                 ("a brief's record tail", tail_32, 0, "a planted branch 7 line"),
                                 ("Part Two", part_two, 0, "a planted slice line")):
        planted = list(plines)
        planted.insert(i + 1, word)
        got = len(census("PLAN-2-step-b.md", "\n".join(planted), pspans)[2]) - pbase
        checks.append((f"the plan: {word!r} planted in {where} is {'counted' if want else 'left alone'}", got == want))
    planted = list(plines)
    planted[row_93] += " a planted branch 7"
    got = len(census("PLAN-2-step-b.md", "\n".join(planted), pspans)[2]) - pbase
    checks.append(("the plan: an old word added to a 9.3 row is left alone", got == 0))
    planted = list(plines)
    planted.insert(order + 1, "| 3 the planted row | a planted branch 7 |")
    got = len(census("PLAN-2-step-b.md", "\n".join(planted), pspans)[2]) - pbase
    checks.append(("the plan: a 9.3-shaped row OUTSIDE 9.3 is counted (the row span is scoped)", got == 1))
    for label, bad_span in (("a brief-tail whose section has no brief", ("brief-tail", ("### 3.1 ", BRIEF), "x")),
                            ("a heading prefix that matches many headings", ("heading", "### 3.", "x")),
                            ("a range whose first heading is absent", ("range", ("## PART NINE ", None), "x"))):
        try:
            census("PLAN-2-step-b.md", ptext, [bad_span])
            checks.append((f"the plan: refused - {label}", False))
        except LookupError:
            checks.append((f"the plan: refused - {label}", True))
    stale = [("section", "### 9.9 No such heading", "a stale span")]
    try:
        census("CLAUDE.md", text, stale)
        checks.append(("a record span that matches nothing is refused", False))
    except LookupError:
        checks.append(("a record span that matches nothing is refused", True))
    # the register, rename (c): the row is the unit - an old word counted in an open row, an open instrument row and
    # a cluster cell; left alone in a closed row and a fixed instrument row; counted beside a declared phrase; and a
    # phrase that occurs nowhere refused
    rname = "evidence/REGISTER-findings.md"
    rtext = (ROOT / rname).read_bytes().decode("utf-8")
    rspans = SWEPT[rname]
    rlines = rtext.replace("\r\n", "\n").split("\n")
    rbase = len(census(rname, rtext, rspans)[2])

    def row(rid):
        return next(i for i, l in enumerate(rlines) if l.startswith(f"| {rid} |"))
    for where, i, want in (("an open row (A1)", row("A1"), 1), ("a closed row (A2)", row("A2"), 0),
                           ("an open instrument row (I-26)", row("I-26"), 1),
                           ("a fixed instrument row (I-2)", row("I-2"), 0),
                           ("a clusters-table cell (G)", next(i for i, l in enumerate(rlines)
                                                             if l.startswith("| **G** |")), 1),
                           ("the row beside a declared phrase (A20)", row("A20"), 1)):
        planted = list(rlines)
        head, sep, tail = planted[i].partition(" | ")
        planted[i] = head + sep + "a planted branch 7 " + tail
        got = len(census(rname, "\n".join(planted), rspans)[2]) - rbase
        checks.append((f"the register: an old word planted in {where} is {'counted' if want else 'left alone'}",
                       got == want))
    try:
        census(rname, rtext, rspans + [("phrase", "a phrase that occurs nowhere", "x")])
        checks.append(("the register: a declared phrase that occurs nowhere is refused", False))
    except LookupError:
        checks.append(("the register: a declared phrase that occurs nowhere is refused", True))
    nphrase = sum(1 for s in rspans if s[0] == "phrase")
    unmasked = len(census(rname, rtext, [s for s in rspans if s[0] != "phrase"])[2]) - rbase
    checks.append((f"the register: without its {nphrase} phrase declarations, exactly {nphrase} own-sense words count",
                   unmasked == nphrase))
    checks.append(("the register: every closed-row id starts exactly one row", closed_ids_stale(rtext) == []))
    checks.append(("the register: a mistyped closed-row id is refused",
                   closed_ids_stale(rtext.replace("| C30 |", "| C31 |", 1)) == ["C30"]))
    # rename (d1): an old word planted in each kind of new document's living text is counted, one planted in a
    # declared record is left alone - a line inserted after the anchor line, or (inline) the anchor line itself added to
    for name, prefix, inline, want, where in (
            ("evidence/EVIDENCE-a3-structure.md", "## 6. ", False, 0, "a record whole"),
            ("PLAN-3-opus5-migration.md", "## 1. ", False, 0, "a record whole"),
            ("evidence/EVIDENCE-confidentiality.md", "## 5 — ", False, 1, "living text"),
            ("evidence/EVIDENCE-confidentiality.md", "> **SUBSTANTIALLY MITIGATED 2026-08-11", False, 0,
             "a dated paragraph"),
            ("evidence/EVIDENCE-measurement.md", "## 1 — ", False, 1, "the corpus listing"),
            ("evidence/EVIDENCE-measurement.md", "### 3.5 ", False, 0, "a dated section"),
            ("verify.config.json", '      "verify_deliverable.py":', True, 1, "an undated declaration"),
            ("verify.config.json", '          "verify_code.py::::commit author identity":', True, 0,
             "a dated declaration"),
            (".gitattributes", "# NEVER TRANSLATE", False, 1, "living text"),
            ("README.md", "## Contributing", False, 1, "living text"),
            (".claude/skills/frozen-intermediate-test/SKILL.md", "# How a change", False, 1, "a skill"),
            (".claude/rules/ooxml.md", "# OOXML hard rules", False, 1, "a rule, a CRLF file")):
        dtext = (ROOT / name).read_bytes().decode("utf-8")
        dspans = SWEPT[name]
        dlines = dtext.replace("\r\n", "\n").split("\n")
        dbase = len(census(name, dtext, dspans)[2])
        i = next((k for k, l in enumerate(dlines) if l.startswith(prefix)), None)
        if i is None:
            checks.append((f"{name}: the selftest's anchor {prefix!r} is present", False))
            continue
        planted = list(dlines)
        if inline:
            planted[i] += " a planted branch 7"
        else:
            planted.insert(i + 1, "a planted branch 7 line")
        got = len(census(name, "\n".join(planted), dspans)[2]) - dbase
        checks.append((f"{name}: an old word planted in {where} is {'counted' if want else 'left alone'}",
                       got == want))
    # and the scope: every tracked document in it judged, and one added outside SWEPT refused, code and trees out
    tracked = tracked_files()
    checks.append(("every tracked document in scope is swept or a record by kind", unjudged(tracked) == []))
    new = ["evidence/EVIDENCE-new.md", ".claude/rules/new.md", ".claude/skills/new/SKILL.md"]
    base = set(unjudged(tracked))
    checks.append(("a document added outside SWEPT is refused - an evidence document, a rule, a skill",
                   sorted(set(unjudged(tracked + new)) - base) == sorted(new)))
    checks.append(("the shipped trees and the code stay out of scope",
                   set(unjudged(tracked + ["uk/new.md", "tools/new.md", "tests/new.md"])) == base))
    # the code arm, rename (d2), on a synthetic source with a known answer: an old word counted in a docstring, a
    # string, an f-string's text and an undated comment; never read in an identifier; left alone on a dated comment
    # block's undated line; a declared phrase masked; a stale phrase and a non-phrase declaration refused
    src = ('"""A docstring: a planted branch 7."""\n'
           'x = "a planted slice"\n'
           'y = f"a planted Step C {x} beside"\n'
           '# an undated comment: a planted branch 8\n'
           'branch_7 = slice(1, 2)  # never read: the names on this line\n'
           '\n'
           '# 2026-01-01: a dated note\n'
           '# whose second line holds a planted branch 9\n'
           'z = "kept: string slicing slices the text"\n')
    keep = [("phrase", "slices the text", "Python's own sense")]
    got = sorted({n for n, _, _ in code_census("synthetic", src, keep)[1]})
    checks.append(("code: counted in a docstring, a string, an f-string's text and an undated comment",
                   got == [1, 2, 3, 4]))
    checks.append(("code: never read in an identifier, left alone on a dated block's undated line",
                   5 not in got and 8 not in got))
    checks.append(("code: without its phrase declaration, exactly the one own-sense word more counts",
                   len(code_census("synthetic", src, [])[1]) == len(code_census("synthetic", src, keep)[1]) + 1))
    for label, bad_spans in (("a phrase that occurs nowhere", keep + [("phrase", "nowhere at all", "x")]),
                             ("a declaration other than a phrase", [("line", "x", "y")])):
        try:
            code_census("synthetic", src, bad_spans)
            checks.append((f"code: refused - {label}", False))
        except LookupError:
            checks.append((f"code: refused - {label}", True))
    real = "tools/stepb_verify.py"
    rsrc = (ROOT / real).read_bytes().decode("utf-8")
    rbase_n = len(code_census(real, rsrc, CODE_SWEPT.get(real, []))[1])
    for tail, want, where in (("\n# a planted branch 7\n", 1, "an undated comment"),
                              ("\n# 2026-10-21: a dated note\n# a planted branch 7\n", 0, "a dated comment block")):
        n = len(code_census(real, rsrc + tail, CODE_SWEPT.get(real, []))[1]) - rbase_n
        checks.append((f"code: {real}: an old word planted in {where} is {'counted' if want else 'left alone'}",
                       n == want))
    cs = code_scope(tracked)
    checks.append(("code: tests/run_tests.py is the project's, in scope; tools/run_tests.py the house's, out",
                   "tests/run_tests.py" in cs and "tools/run_tests.py" not in cs))
    trail = ('x = 1  # 2026-01-01: a dated trailing note\n'
             'y = 2  # an undated trailing comment: a planted branch 7\n'
             '# a standalone note dated 2026-01-01\n'
             'z = 3  # trailing the next line, undated: a planted branch 8\n')
    tgot = sorted({n for n, _, _ in code_census("synthetic", trail, [])[1]})
    checks.append(("code: a trailing comment is its own unit - a dated neighbour exempts neither", tgot == [2, 4]))
    # the house's copies held against the shared folder: a tools/ script named there and missing here would be swept
    # as project code; a name here that is not a tracked tools/ script is a stale entry. Unreachable is a FAILED check
    shared = {p.name for p in SHARED.glob("*.py")} if SHARED.is_dir() else None
    here = {Path(f).name for f in tracked if f.startswith("tools/") and f.endswith(".py") and "/" not in f[6:]}
    checks.append((f"code: HOUSE_COPIES is exactly the tools/ scripts named in {SHARED.name}/ "
                   f"({'unreachable' if shared is None else len(shared & here)})",
                   shared is not None and HOUSE_COPIES == (shared & here)))
    for label, good in checks:
        print(("  OK   " if good else "  XX   ") + label)
    ok = all(g for _, g in checks)
    print("selftest PASS" if ok else "selftest FAIL")
    return 0 if ok else 1


def main():
    if "--selftest" in sys.argv:
        return selftest()
    docs = {}
    for name, spans in SWEPT.items():
        p = ROOT / name
        try:
            docs[name] = (p.read_bytes().decode("utf-8"), spans)
        except (OSError, UnicodeDecodeError) as exc:
            print(f"  VOID  {name} could not be read ({type(exc).__name__})")
            return 3
    print("vocabulary census - the house's words in living text")
    try:
        tracked = tracked_files()
        missing = unjudged(tracked)
    except OSError as exc:
        print(f"  VOID  the tracked documents could not be listed ({exc})")
        return 3
    if missing:
        print(f"  VOID  tracked document(s) never judged - each joins SWEPT with its split, or is a record by kind: "
              f"{missing}")
        return 3
    if "--list-pending" in sys.argv:
        for f in sorted(set(code_scope(tracked)) - set(CODE_SWEPT)):
            print(f"  pending: {f}")
    try:
        examined, bad = run(docs)
        code_examined, code_bad = run_code(tracked)
    except (LookupError, OSError, UnicodeDecodeError, SyntaxError, tokenize.TokenError) as exc:
        print(f"  VOID  {exc}")
        return 3
    if examined == 0:
        print("VOID: no swept document examined")
        return 3
    print(f"{examined} document(s) and {code_examined} code file(s) examined, {bad + code_bad} old word(s) in "
          f"living text")
    return 1 if bad + code_bad else 0


if __name__ == "__main__":
    sys.exit(main())
