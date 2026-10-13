#!/usr/bin/env python3
"""verify_charter.py - the charter checks, split out of verify_md.py.  CHECKER VERSION 2 (2026-10-13)

If a project's copy says a lower version than this one, it is stale - see the "Checkers"
line for each version in ...\\Coding\\templates\\TEMPLATE-CHANGELOG.md and re-copy.

WHAT IT IS. The six checks that hold a CHARTER to CLAUDE-TEMPLATE.md's shape - charter
structure, charter archetype, core sections present, relocation pointers, sections agreed
out and plan purpose - and the four constants that mirror the template. It has no run of its
own: verify_md.py imports it and calls check_charter() for every document, so a project still
runs ONE command and reads ONE report.

    uv run python tools/verify_charter.py --selftest    # prove every charter check can FAIL

WHY IT WAS SPLIT OUT (2026-10-12, verify_md.py v30). verify_md.py had become two jobs: a
general Markdown checker and a charter-template inspector. Its 15 checks had grown to 21, all
six new ones charter checks, and 5 of the 8 version bumps between 2026-09-01 and 2026-09-30
came from the TEMPLATE - each one marking every project's copy of the general checker stale
for a change most documents could not feel. Now a template change bumps THIS file only.

v2 (2026-10-13) changes no check: the sentence above wrote a month NAME before a year, a shape a
project's own gate may refuse as a date that could pin a client transaction. review_scripts.py's
selftest now refuses that shape in every shared script, so a release cannot carry it again.

WHY verify_md.py CALLS IT, RATHER THAN EACH PROJECT RUNNING IT. A declared toleration is keyed
'checker::document::row', so a checker run on its own would have changed the key of every
charter row in every project. Called from verify_md.py, every row keeps its name AND its key,
and no config moves: the settings stay under "md" in verify.config.json.

COPY IT BESIDE verify_md.py. Without it, verify_md.py reports the six rows as FAIL, naming this
file, on every document - never a silent drop, because a missing row reads exactly like a
passed one. check_checkers.py tracks it.
"""
from __future__ import annotations

import re

# The shared plumbing, and since 2026-10-12 the shared Markdown parsers too: they moved to
# house_common.py from verify_md.py so that this file and that one read headings, tables and
# code spans with ONE parser. Two copies are how two checkers come to disagree.
from house_common import (                                       # noqa: E402
    DELIM_RE, FAIL, NA, PASS, Case, code_fence_mask, collapse, headings, report_pairing,
    row_cells, run_cases, strip_inline_code,
)

#: THE SIX ROW NAMES, AND THEY ARE A CONTRACT. A declared toleration is keyed on them, and
#: verify_md.py holds the same tuple so it can report them when this file is missing. The
#: selftest asserts the two agree, so a rename on one side alone fails here.
ROWS = ("charter structure", "charter archetype", "core sections present",
        "sections agreed out", "relocation pointers", "plan purpose")

#: THE TEMPLATE'S OWN SUBSECTION COUNTS, section 1 to 7, and they live HERE rather than in
#: config for a measured reason: CLAUDE-TEMPLATE.md is copied into NO project. Every
#: propagated project holds a charter GENERATED FROM the template, never the template - so a
#: check that read the file at run time would work only in the house repository, which is the
#: one place the answer does not matter. The checker is the one artefact that actually
#: travels, and check_checkers.py already reports when a copy falls behind, so a stale
#: constant is visible as a VERSION difference instead of being silent.
#:
#: Sections 4 and 7 carry no numbered subsections at all. Section 7's headings are unnumbered
#: BY DESIGN - it is replaced every session, and a number there would be a stable identifier
#: for something that is deliberately not stable.
TEMPLATE_SUBSECTIONS = {1: 7, 2: 5, 3: 2, 4: 0, 5: 8, 6: 5, 7: 0}

#: THE FLOOR, and it is the half TEMPLATE_SUBSECTIONS could never see. That map is a CEILING -
#: never MORE subsections than the template. Nothing checked that a CORE one was PRESENT, so
#: the one instrument pointed at charter shape could only see EXCESS, and a charter missing
#: 5.4 (TEST) passed it perfectly. Measured 2026-09-10 across all six house charters: THREE
#: are missing at least one, INCLUDING THE HOUSE REPOSITORY'S OWN.
#:
#: LISTED from CLAUDE-TEMPLATE.md's tier table rather than counted - the tier table marks
#: these fourteen rows CORE, which it defines as "in every charter, however small the project.
#: Never negotiated away". A DEFAULT or OPTIONAL row is deliberately absent: a missing 1.4 or
#: 5.6 is a decision, and only CORE is never a decision.
#:
#: It lives here for the same reason TEMPLATE_SUBSECTIONS does, and the reason is not
#: convenience: CLAUDE-TEMPLATE.md is copied into NO project, so a check that read the file at
#: run time would work only in the house repository - the one place the answer does not
#: matter. A stale constant surfaces as a VERSION difference, which check_checkers.py reports.
TEMPLATE_CORE = ("1.1", "1.2", "1.3", "1.5", "2.1", "2.2", "3", "4",
                 "5.1", "5.3", "5.4", "5.8", "6", "7")

#: DEVICE 4 - the NEGOTIABLE subsections: everything the tier table marks DEFAULT, OPTIONAL or
#: mixed. These are exactly the rows Round 0.5 walks one at a time with its trigger question,
#: and therefore exactly the rows a project may legitimately leave out.
#:
#: THE SET IS THE COMPLEMENT OF TEMPLATE_CORE, and stating it separately rather than deriving
#: it is deliberate: sections 5.2 and 5.7 are MIXED - part CORE, part not - so a derived
#: complement would either admit them wrongly or exclude them wrongly, and the tier table is
#: the authority on which. Listed, not computed.
TEMPLATE_NEGOTIABLE = ("1.4", "1.6", "2.3", "2.4", "2.5", "3.1", "3.2",
                       "5.2", "5.5", "5.6", "5.7")

#: DEVICE 3 - the eleven archetypes, row for row from CLAUDE-TEMPLATE.md's archetype-defaults
#: table. Round 0.2's list and that table MUST match row for row; the template says so in
#: terms, having once offered nine against eleven for five days.
#:
#: WHY A LABELLED DECLARATION AND NOT A PHRASE SEARCH, and it was measured both ways before
#: this check was written. Searching for these NAMES in a charter returns FALSE POSITIVES from
#: ordinary prose - two house charters "name" *Claude skill* in passing while declaring
#: nothing. Searching for the WORD *archetype* passes a charter whose only hit is a sentence
#: about emit sizes. Only a LABELLED declaration tells a decision from a mention, which is why
#: the check asks for one shape and the template emits that shape.
ARCHETYPES = (
    "Claude skill",
    "Word / Excel add-in",
    "JavaScript / web",
    "API tool / library",
    "Guided build / playbook",
    "Research / analysis",
    "Docs / Markdown only",
    "Analysis + rebuild of an existing artefact",
    "Automation 1 - file and data",
    "Automation 2 - workflow orchestration",
    "Automation 3 - autonomous agent",
)

#: The declaration the charter must carry, in section 1.7 beside the size class (Wouter,
#: 2026-09-10). Bold, colon, then one of the eleven. The name is matched with punctuation and
#: case folded away, so an em dash, a slash or a stray article does not turn a correct
#: declaration into a failure - the check is about WHETHER the decision was recorded, never
#: about typography.
ARCHETYPE_LABEL = re.compile(r"ARCHETYPE\s*[:—-]\s*(.+)", re.I)


def check_charter_structure(rep, doc, lines, declared, in_scope=True):
    """A charter's section N may have FEWER subsections than the template's, NEVER MORE.

    A SUBSET IS MAPPING. A project takes the subsections of a house section it actually
    needs, which is why one charter legitimately carries 3 where the template carries 8.
    MORE is the opposite act: the section grew its own structure instead of being mapped
    onto one, and nothing in this house could see it.

    WHY THE GAPLESS CHECK CONFIRMS THE DEFECT INSTEAD OF CATCHING IT. check_headings
    requires subsections to run 1..n with no gaps, and '1..16' satisfies that perfectly. So
    the one instrument pointed at subsection numbering reports PASS over the exact shape
    this check exists to find - measured on two charters at sixteen and fourteen against
    eight, both of which had answered "already house-shaped, so the work is numbering, not
    mapping" and been believed.

    AN EXCESS IS DECLARED, NEVER SILENTLY TOLERATED, and the declaration is held to the same
    two rules a declared checker absence is: a BLANK reason is REFUSED, because a command
    line cannot carry a reason and the reason is the whole distinction between a decision and
    an oversight; and a declaration for a section that is NOT in excess FAILS as stale, so
    the config cannot outlive its own facts.
    """
    if not in_scope:
        rep.record(doc, "charter structure", 0, [],
                   na_reason="not in size_scope - a charter's structure is a charter's")
        return
    numbered = [k for _, _, _, k in headings(lines) if k]
    if not numbered:
        rep.record(doc, "charter structure", 0, [],
                   na_reason="document uses no numbered headings")
        return
    got = {}
    for key in numbered:
        top, _, sub = key.partition(".")
        try:
            n = int(top)
        except ValueError:
            continue
        got.setdefault(n, set())
        if sub:
            try:
                got[n].add(int(sub))
            except ValueError:
                pass
    declared = {str(k): v for k, v in (declared or {}).items()}
    problems, examined = [], 0
    for n in sorted(TEMPLATE_SUBSECTIONS):
        if n not in got:
            # A section the charter does not have is not an excess. A MISSING section is
            # check_required_sections' subject, and two checks failing on one fact is how a
            # reader learns to stop reading one of them.
            if str(n) in declared:
                problems.append(
                    f"section {n} has a declared excess and no heading here - stale")
            continue
        examined += 1
        have, cap = len(got[n]), TEMPLATE_SUBSECTIONS[n]
        if have > cap:
            reason = declared.get(str(n))
            if str(n) not in declared:
                problems.append(
                    f"section {n}: {have} subsections against the template's {cap} "
                    f"- {have - cap} more. A SUBSET is mapping; an EXCESS means the section "
                    f"grew its own structure instead of mapping onto one. Map it, or declare "
                    f"it in md.charter_structure with a reason")
            elif not str(reason).strip():
                problems.append(
                    f"section {n}: excess declared with a BLANK reason - REFUSED. The reason "
                    f"is the whole distinction between a decision and an oversight")
        elif str(n) in declared:
            problems.append(
                f"section {n}: excess declared, but {have} subsections against the "
                f"template's {cap} is not an excess - the declaration is stale")
    rep.record(doc, "charter structure", examined, problems)


def _fold(s: str) -> str:
    """Punctuation and case folded away, so an em dash and a hyphen are one name.

    The check is about whether a DECISION was recorded, never about typography. A charter
    that writes 'Automation 1 — file and data' has named the archetype exactly as well as one
    writing 'Automation 1 - file and data', and a check that told them apart would be
    teaching people to copy a dash rather than to make a choice.
    """
    return re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).strip()


def check_charter_archetype(rep, doc, lines, declared, in_scope=True):
    """DEVICE 3. Does the charter NAME one of the template's eleven archetypes?

    IT IS THE CHEAPEST OF THE FIVE DEVICES AND IT UNLOCKS THE OTHER TWO. The archetype table
    is 11 rows x 10 optional-block columns at (in) / (ask) / (out); EVERY ONE of those lookups
    starts by knowing which row this project is. A charter that records no archetype makes the
    whole table unreadable, so this arm lands before the ones that depend on it.

    WHAT IT ASKS FOR IS A LABELLED DECLARATION, AND THE ALTERNATIVE WAS MEASURED. Searching a
    charter for the eleven NAMES returns false positives from ordinary prose - two house
    charters mention *Claude skill* while being neither. Searching for the WORD *archetype*
    passes a charter whose only occurrence is a sentence about emitted line counts. Both naive
    needles answer wrongly, in OPPOSITE directions, over the same six documents. So the check
    asks for one shape, the template emits that shape, and new_charter.py fills it from the
    flag it was already given.

    THE ROOT CAUSE THIS ARM EXISTS FOR SITS IN THE GENERATOR, NOT IN THE CHARTERS.
    new_charter.py REQUIRES --archetype, uses it to pre-select the optional blocks that
    archetype needs, and until 2026-09-10 never wrote it into the charter it emitted - so
    every generated charter recorded none, and the single house charter that did record one
    had it added by hand. A device only the generator consumes leaves no trace; here the
    generator did not even leave the trace it was handed.

    A DECLARED ABSENCE carries its reason, and the reason is the whole distinction between a
    decision and an oversight. A declaration standing over a charter that DOES name its
    archetype fails as stale, so the config cannot outlive its own facts.
    """
    if not in_scope:
        rep.record(doc, "charter archetype", 0, [],
                   na_reason="not in size_scope - an archetype is a charter's")
        return
    named, unknown = None, None
    for raw in lines:
        m = ARCHETYPE_LABEL.search(strip_inline_code(raw))
        if not m:
            continue
        # The rest of the line may carry bold markers, a parenthetical attribution or an
        # article. Fold it and ask whether any of the eleven names is IN it, longest first so
        # 'Automation 1 - file and data' is not shadowed by a shorter neighbour.
        tail = _fold(m.group(1))
        for a in sorted(ARCHETYPES, key=len, reverse=True):
            if _fold(a) in tail:
                named = a
                break
        if named:
            break
        unknown = m.group(1).strip()[:60]
    reason = (declared or "") if isinstance(declared, str) else ""
    problems = []
    if named and str(reason).strip():
        problems.append(
            f"an absent archetype is declared, but the charter names '{named}' "
            f"- the declaration is stale")
    elif not named:
        if declared is None or declared == "":
            near = f" The line found reads '{unknown}'." if unknown else ""
            problems.append(
                "no archetype declared. Section 1.7 must carry a line naming ONE of the "
                "template's eleven archetypes, e.g. '**ARCHETYPE: Research / analysis**' - "
                "every optional-block lookup in the archetype table starts from it." + near)
        elif not str(reason).strip():
            problems.append(
                "an absent archetype is declared with a BLANK reason - REFUSED. The reason "
                "is the whole distinction between a decision and an oversight")
    rep.record(doc, "charter archetype", 1, problems)


def check_core_sections(rep, doc, lines, declared, in_scope=True):
    """DEVICE 1's FLOOR. Is every CORE subsection PRESENT?

    THE HALF charter structure COULD NEVER SEE. That check is a CEILING - never MORE
    subsections than the template - and a subset is legitimate, being what MAPPING produces.
    So nothing in this house asked the opposite question, and a charter missing 5.4 (TEST)
    passed every structural check it had. Measured 2026-09-10 over all six house charters:
    three are missing at least one CORE subsection, THE HOUSE REPOSITORY'S OWN INCLUDED.

    ONLY CORE IS CHECKED, AND THAT IS THE WHOLE DISCRIMINATOR. The tier table defines CORE as
    'in every charter, however small the project. Never negotiated away'. A missing DEFAULT or
    OPTIONAL subsection is a decision Round 0.5 took; a missing CORE one is not a decision
    anybody is allowed to take, which is why this arm can fail on absence where no other can.

    IT CANNOT REDDEN A NEW PROJECT, and that was measured before it was built: a charter
    emitted by new_charter.py carries every CORE heading, 1.5 included. The defect is confined
    to hand-maintained charters, which is the difference between a check that gets used and
    one somebody switches off.

    A GENUINELY IMPOSSIBLE CORE SUBSECTION IS DECLARED WITH ITS REASON - blank REFUSED, and a
    declaration for a subsection that is present FAILS as stale. But the tier table's own
    wording means the honest answer is almost always to WRITE the subsection.
    """
    if not in_scope:
        rep.record(doc, "core sections present", 0, [],
                   na_reason="not in size_scope - a CORE floor is a charter's")
        return
    keys = {k for _, _, _, k in headings(lines) if k}
    if not keys:
        rep.record(doc, "core sections present", 0, [],
                   na_reason="document uses no numbered headings")
        return
    declared = {str(k): v for k, v in (declared or {}).items()}
    problems, examined = [], 0
    for key in TEMPLATE_CORE:
        examined += 1
        present = key in keys
        if not present and key not in declared:
            problems.append(
                f"CORE subsection {key} is MISSING. The tier table marks it CORE - 'in every "
                f"charter, however small the project. Never negotiated away'. Write it, or "
                f"declare it in md.core_sections with a reason")
        elif not present and not str(declared[key]).strip():
            problems.append(
                f"CORE subsection {key} is absent and declared with a BLANK reason - REFUSED. "
                f"The reason is the whole distinction between a decision and an oversight")
        elif present and key in declared:
            problems.append(
                f"CORE subsection {key} is declared absent, but the charter has it "
                f"- the declaration is stale")
        elif present:
            # GAP 62, CHECKER VERSION 29. A PRESENT heading is not a present SUBSECTION, and
            # until now this arm could not tell them apart: it asked whether the heading
            # existed and never whether anything stood under it. MEASURED 2026-09-14 on a
            # charter reduction - a verifier emptied a CORE subsection to nothing and the file
            # went 354 -> 308 lines with THIS ROW READING PASS AT 14 AND THE RUN OVERALL PASS.
            #
            # WHY THAT IS THE DANGEROUS DIRECTION. A reduction's whole method is collapsing a
            # block to a one-line pointer, so the failure mode it tends towards is collapsing
            # one block too far - and that was the single route with no mechanical check at
            # all, guarded only by a person reading the blueprint's rule 1.
            #
            # A POINTER IS ENOUGH AND MUST STAY ENOUGH: the test is whether ANY non-blank,
            # non-heading, non-rule line stands in the body, not how many. Deliberately NOT a
            # line-count floor - that would fight the relocation regime it exists to protect.
            # A container section whose own prose is nil still passes, because _section_body
            # spans to the next heading of the same or higher level and so includes the
            # subsections' bodies.
            body = _section_body(lines, key)
            if body is not None and not [
                    ln for ln in body[1:]
                    if ln.strip() and not ln.lstrip().startswith("#")
                    and set(ln.strip()) != {"-"}]:
                problems.append(
                    f"CORE subsection {key} has its HEADING but NOTHING UNDER IT. The tier "
                    f"table marks it CORE, and an emptied subsection is indistinguishable "
                    f"from a deleted one to every other arm here - leave at least the "
                    f"one-line pointer a relocation owes")
    rep.record(doc, "core sections present", examined, problems)


def _section_body(lines, key):
    """The lines of one section or subsection, its heading included, or None if absent.

    Spans to the next heading of the SAME OR HIGHER level, the same rule section_sizes uses -
    never to the next heading of ANY level, which measures the gap to the first subsection
    rather than the section.
    """
    # headings() reports ONE-BASED line numbers, which is what the report prints. Slicing
    # with them directly starts a line late and swallows the NEXT section's heading - caught
    # here because the good arm of every pointer case failed while the bad arm passed.
    hs = [(i - 1, lvl, k) for i, lvl, _, k in headings(lines)]
    for at, (i, lvl, k) in enumerate(hs):
        if k != key:
            continue
        end = len(lines)
        for j, lvl2, _ in hs[at + 1:]:
            if lvl2 <= lvl:
                end = j
                break
        return lines[i:end]
    return None


def check_pointers(rep, doc, lines, pointers, in_scope=True):
    """DEVICE 5. Every relocation leaves a POINTER, and the pointer is still there.

    THE HOUSE RULE IS 'EVERY RELOCATION LEAVES A ONE-LINE POINTER BEHIND', and its reason is
    that a rule which simply VANISHES is indistinguishable from a rule that was REPEALED.
    Nothing checked it. A relocation is invisible to every other arm here: the charter gets
    shorter, which is what a relocation is supposed to look like, and so does a deletion.

    IT IS DECLARED, NOT INFERRED, AND THAT WAS MEASURED. The obvious alternative - detect
    relocation CLAIMS in prose and require a destination near each - was built and measured
    over the six house charters before this arm was written: 33 claims, 6 flagged, and at
    least FOUR of the six were false positives. Three came from HARD WRAPPING, the claim and
    its destination landing three lines apart; one from a destination that is a config key
    rather than a .md file. A needle with that error rate reddens three charters on bad
    grounds, which is precisely how this house has twice lost a control.

    So the project names what moved and what must still be findable, and the arm asserts the
    RETURN PATH survives - the same question verify_charter_continuity's check 5 asks for one
    project, generalised. A phrase that stops appearing in its section is a pointer that has
    gone, reported by name.

    EMPTY IS N/A WITH ITS REASON, never a silent pass: a project that has relocated nothing
    has nothing to assert, and a project that has relocated something and declared nothing
    should see a row saying so rather than a row saying PASS.
    """
    if not in_scope:
        rep.record(doc, "relocation pointers", 0, [],
                   na_reason="not in size_scope - a relocation pointer is a charter's")
        return
    pointers = {str(k): v for k, v in (pointers or {}).items()}
    if not pointers:
        rep.record(doc, "relocation pointers", 0, [],
                   na_reason="md.pointers is empty (disabled) - name each relocated block's "
                             "section and the phrase its pointer must still carry. A "
                             "relocation and a deletion look identical from here otherwise")
        return
    problems, examined = [], 0
    for key in sorted(pointers):
        phrases = pointers[key]
        if isinstance(phrases, str):
            phrases = [phrases]
        body = _section_body(lines, key)
        if body is None:
            examined += len(phrases)
            problems.append(
                f"section {key} is declared to carry a pointer and has no heading here at "
                f"all - the return path a pointer resolves against is GONE, which is the "
                f"one shape this check exists to catch")
            continue
        # The SAME wrap-tolerant matcher check_required uses, not a second copy: a pointer is
        # one line of prose in a hard-wrapped charter, so a line-by-line search would report
        # a missing pointer over a document that plainly carries it. That was measured on
        # this very population - three of six candidate findings were wrap artefacts.
        blob = collapse(body)[0].lower()
        for phrase in phrases:
            examined += 1
            if not str(phrase).strip():
                problems.append(
                    f"section {key}: a BLANK pointer phrase - REFUSED. It would assert "
                    f"nothing while reading exactly like an assertion")
            # STRIPPED, because collapse() appends a trailing space per line - an unstripped
            # needle only ever matched a phrase at the very end of a sentence, so 'see the
            # house file' failed against '...see the house file, and not restated.'
            elif collapse([str(phrase)])[0].lower().strip() not in blob:
                problems.append(
                    f"section {key} no longer carries its pointer '{phrase}'. A relocated "
                    f"block whose pointer has gone is indistinguishable from one that was "
                    f"REPEALED - restore the pointer, or remove this declaration if the "
                    f"rule really was repealed")
    rep.record(doc, "relocation pointers", examined, problems)


def check_sections_agreed_out(rep, doc, lines, agreed, in_scope=True):
    """DEVICE 4. Round 0.5's decisions, checked through their ARTEFACT.

    ROUND 0.5 IS A CONVERSATION AND A CONVERSATION CANNOT BE CHECKED. The template asks that
    the section set be PROPOSED and agreed one optional block at a time, each with its trigger
    question - and the output of that conversation has never been written anywhere. So a
    charter missing 5.6 is indistinguishable from a charter whose owner was never asked about
    5.6, and the second is the failure mode the whole round exists to prevent.

    THE ARTEFACT IS THE SAME SHAPE checkers.declared_absent ALREADY USES: subsection -> reason.
    A reader can then tell a decision from an oversight, which is the only thing that
    distinguishes them once the conversation is over.

    IT IS OPT-IN, AND THE COST IS DECLARED RATHER THAN HIDDEN (Wouter, 2026-09-10). An empty
    map reports N/A with its reason instead of failing, following md.plan_scope's precedent -
    so it CANNOT redden six charters at once, which is how this house has twice lost a
    control. The price, stated because it is real: nothing sets it on the day it ships, so
    device 4 begins DISABLED everywhere, and *a control that is always exempt is not a
    control*. Setting it per project is the sweep's work, not the checker's.

    ONLY NEGOTIABLE SUBSECTIONS MAY APPEAR. A CORE row is 'never negotiated away', so naming
    one here is a category error rather than a decision - and it would let a charter buy its
    way out of the FLOOR by writing a reason, which is the one thing that must not be
    purchasable.
    """
    if not in_scope:
        rep.record(doc, "sections agreed out", 0, [],
                   na_reason="not in size_scope - Round 0.5's decisions are a charter's")
        return
    agreed = {str(k): v for k, v in (agreed or {}).items()}
    if not agreed:
        rep.record(doc, "sections agreed out", 0, [],
                   na_reason="md.sections_agreed_out is empty (disabled) - record Round 0.5's "
                             "agreed-out set to enable. An empty map cannot tell a section "
                             "nobody wanted from a section nobody was asked about")
        return
    keys = {k for _, _, _, k in headings(lines) if k}
    problems = []
    for key in sorted(agreed):
        reason = agreed[key]
        if key in TEMPLATE_CORE:
            problems.append(
                f"{key} is marked CORE by the tier table - 'never negotiated away'. It "
                f"cannot be agreed out, and a reason here would buy a way past the CORE "
                f"floor. Write the subsection")
        elif key not in TEMPLATE_NEGOTIABLE:
            problems.append(
                f"{key} is not a subsection the template offers, so agreeing it out records "
                f"a decision about nothing. The negotiable set is "
                f"{', '.join(TEMPLATE_NEGOTIABLE)}")
        elif not str(reason).strip():
            problems.append(
                f"{key} is agreed out with a BLANK reason - REFUSED. Round 0.5's whole "
                f"output is the REASON; without it this records only that somebody typed "
                f"a number")
        elif key in keys:
            problems.append(
                f"{key} is recorded as agreed out, but the charter HAS it - the record is "
                f"stale, and a stale one reads exactly like a decision somebody took")
    rep.record(doc, "sections agreed out", len(agreed), problems)


PLAN_TRIPLE = ("purpose", "serves", "deliverable")


def _norm_head(cell: str) -> str:
    """A table heading reduced to its letters, so '**sub-step**' and 'Sub-Step' are one key."""
    return re.sub(r"[^a-z]", "", cell.lower())


def _row_is_closed(cell: str) -> bool:
    """A CLOSED row is struck through in its NAME cell - the house's own convention.

    Leading emphasis is stripped first: the cell is written '~~**NAME**~~' about as often as
    '**~~NAME~~**', and reading only the first two characters would call one of those open.
    """
    return cell.lstrip("* \t").startswith("~~")


def check_plan_purpose(rep, doc, lines, in_scope=True):
    """Every OPEN row of a plan file states its PURPOSE, what parent purpose it SERVES, and
    its DELIVERABLE - at phase, step and sub-step alike.

    WHY THIS EXISTS. A plan that names what will be done, without naming what it is FOR,
    cannot be checked by the person it is written for. Measured on the template that governs
    every plan file in this house: it asked a PHASE for 'produces', a STEP for 'documents
    produced', the CURRENT step for a 'what it is for' paragraph - and a SUB-STEP for nothing
    at all. The level where the work actually happens was the level with no statement of
    intent.

    WHY A SEPARATE SCOPE KEY AND NOT size_scope, AND IT IS THE MEASUREMENT THAT DECIDED IT.
    size_scope means 'is this a charter'. This asks 'is this a LIVE plan file', which is a
    different population and a moving one - a plan file is live until its phase closes and is
    a finished record for ever after.

    WHY NOT SIMPLY 'EVERY PLAN-*.md', WHICH IS THE OBVIOUS DESIGN AND IS WRONG. Measured over
    15 plan files in the house repository: the 14 CLOSED ones never used strikethrough at all
    - they recorded completion in a 'status' COLUMN instead - so 44 finished rows read as
    OPEN and a strikethrough-only arm reddens twelve finished records. And the discriminator
    that suggests itself next is worse: the LIVE file's own status row contains the word
    CLOSED (it says which steps are closed), so prose-matching the status row marks the one
    live plan finished and the check passes over the very file it exists to read. A check
    that goes green on its whole subject is indistinguishable from a check that ran.

    SO THE SCOPE IS DECLARED, NOT INFERRED - md.plan_scope, defaulting to EMPTY. A project
    names its live plan file, exactly as it names the live plan file in its charter's section
    3, and updating the glob is the same act as renaming the file when the phase turns over.
    An empty list reports N/A WITH THAT REASON on every run rather than passing silently,
    which is the difference between a disabled check and an invisible one.

    WHAT IS CHECKED AND WHAT IS DELIBERATELY NOT. That the three are WRITTEN DOWN is
    mechanical. Whether a purpose was MET is a judgement no script can make, and it is stated
    in prose at the close instead of being faked here.
    """
    if not in_scope:
        rep.record(doc, "plan purpose", 0, [],
                   na_reason="not in plan_scope - a purpose column is a live plan file's")
        return

    mask = code_fence_mask(lines)
    problems, examined = [], 0

    # ---- the PHASE level: the header key-value table's own 'purpose' row
    header_purpose = None
    for i, ln in enumerate(lines):
        if mask[i] or not ln.lstrip().startswith("|"):
            continue
        c = row_cells(ln)
        if len(c) == 2 and _norm_head(c[0]) == "purpose":
            header_purpose = c[1].strip()
            break
    examined += 1
    if header_purpose is None:
        problems.append(
            "the phase itself states no purpose - the header table has no 'purpose' row. "
            "'produces' is the DELIVERABLE and 'serves' is the parent; neither says what "
            "this phase is FOR")
    elif not header_purpose:
        problems.append("the phase's 'purpose' row is BLANK - a declared NONE with its "
                        "reason, never an empty cell")

    # ---- the STEP and SUB-STEP levels: every table whose header names one of them
    i, tables = 0, 0
    while i < len(lines):
        if (not mask[i] and lines[i].lstrip().startswith("|")
                and i + 1 < len(lines) and DELIM_RE.match(lines[i + 1])):
            head = [_norm_head(c) for c in row_cells(lines[i])]
            namecol = next((k for k, h in enumerate(head)
                            if h in ("step", "substep", "steps", "substeps")), None)
            if namecol is None:
                i += 1
                continue
            tables += 1
            level = "sub-step" if head[namecol].startswith("sub") else "step"
            where = {t: head.index(t) for t in PLAN_TRIPLE if t in head}
            j = i + 2
            while j < len(lines) and not mask[j] and lines[j].lstrip().startswith("|"):
                c = row_cells(lines[j])
                if namecol < len(c) and not _row_is_closed(c[namecol]):
                    examined += 1
                    ident = c[0].strip("* ") or c[namecol][:30]
                    missing = [t for t in PLAN_TRIPLE
                               if t not in where or where[t] >= len(c)
                               or not c[where[t]].strip()]
                    if missing:
                        absent = [t for t in PLAN_TRIPLE if t not in where]
                        why = (f"the table has no {', '.join(absent)} column"
                               if absent else "left blank")
                        problems.append(
                            f"line {j + 1}: OPEN {level} {ident} states no "
                            f"{', '.join(missing)} - {why}. An open row answers all three, "
                            f"and a deliverable that does not exist is a declared NONE with "
                            f"its reason")
                j += 1
            i = j
            continue
        i += 1

    if not tables:
        problems.append(
            "no step or sub-step table found - a plan file in plan_scope with no table of "
            "steps is either misfiled or unplanned, and either is a finding")
    rep.record(doc, "plan purpose", examined, problems)


def check_charter(rep, doc, lines, cfg, scoped, plan_scoped):
    """All six charter rows for one document, in the order verify_md.py has always printed them.

    `scoped` is verify_md.py's answer to 'is this a charter' (md.size_scope), and `plan_scoped`
    its answer to 'is this a LIVE plan file' (md.plan_scope) - None when plan_scope is empty.
    Both are worked out THERE, because glob matching belongs to the general checker and the
    same matcher serves its size caps. This file judges only what it is handed.
    """
    check_charter_structure(rep, doc, lines, cfg.get("charter_structure"), scoped)
    # THE FLOOR AND THE ARCHETYPE, both scoped exactly as charter structure is: the question
    # 'is this a charter' is one question, asked once, and three arms read the answer.
    check_charter_archetype(rep, doc, lines, cfg.get("archetype_absent"), scoped)
    check_core_sections(rep, doc, lines, cfg.get("core_sections"), scoped)
    check_sections_agreed_out(rep, doc, lines, cfg.get("sections_agreed_out"), scoped)
    check_pointers(rep, doc, lines, cfg.get("pointers"), scoped)
    # A SEPARATE SCOPE, not size_scope: 'is this a charter' and 'is this a LIVE plan file'
    # are different populations, and the second one moves as phases close.
    if plan_scoped is None:
        rep.record(doc, "plan purpose", 0, [],
                   na_reason="plan_scope is empty (disabled) - name the live plan file to enable")
    else:
        check_plan_purpose(rep, doc, lines, plan_scoped)


# -------------------------------------------------------------------------- selftest
#
# THE CASES RUN THROUGH verify_md.verify_file, exactly as they did before the split, so they
# still prove the WHOLE path a project uses - the general checker calling this one - and not
# merely these functions on their own. That harness lives in verify_md.py and is bound here
# at SELFTEST time, never at import: verify_md.py imports THIS file, and an import in both
# directions at load time is a cycle.

#: The harness names the moved fixtures and cases use, bound from verify_md.py.
HARNESS = ("verify_file", "Report", "SELFTEST_CFG", "NL", "checks", "checks_cfg",
           "HEADS", "TABLES")


def _bind_harness():
    """Bind verify_md.py's harness names into this module, and return verify_md itself."""
    import verify_md
    g = globals()
    for name in HARNESS:
        g[name] = getattr(verify_md, name)
    return verify_md


def writes_subsections(top, n, declared=None):
    """A charter with ONE top-level section `top` carrying `n` gapless subsections.

    It carries its own `charter_structure` map where one is given, for the same reason
    writes_body_under carries max_lines: the declared and undeclared arms differ only in the
    CONFIG, so a builder that dropped it would let the pair pass while comparing two
    different documents.

    The subsections are always 1..n, which is the whole point: they satisfy the gapless
    check perfectly, so only the new check can tell 9 from 8.
    """
    def build(tmp):
        out = ["# Doc", "", f"## {top} - Section {top}", ""]
        for i in range(1, n + 1):
            out += [f"### {top}.{i} Sub {i}", "", "Body.", ""]
        q = tmp / "case.md"
        q.write_text(NL.join(out) + NL, encoding="utf-8")
        return (q, declared) if declared is not None else q
    return build


def checks_struct_under(spec):
    """The charter-structure verdict for one document under one declared-excess map."""
    path, declared = spec
    rep = Report()
    verify_file(rep, path, dict(SELFTEST_CFG, charter_structure=declared))
    return rep.by_name().get(STRUCT)


#: A sentinel, because None is a MEANINGFUL declaration value for the archetype arm - it is
#: 'nothing declared', which is the case that must FAIL. Using None to mean 'no map given'
#: as well would make the one case the arm exists for unwritable, and the first attempt
#: crashed on exactly that.
NO_DECL = object()


def writes_charter(omit=(), archetype=None, declared=NO_DECL, key=None, extra=()):
    """A charter carrying every CORE heading except those in `omit`.

    THE FIXTURE IS BUILT FROM TEMPLATE_CORE ITSELF, not from a hand-typed list. A second copy
    of the fourteen keys would let the constant and its own test drift apart silently, which
    is the one failure a selftest must never be capable of - the test would keep passing
    against the list it shipped with.

    Subsections are emitted under their own top-level parent so the gapless check has no
    opinion: this fixture exists to exercise the FLOOR, and a case that failed for a
    numbering reason would prove nothing about presence.
    """
    def build(tmp):
        out = ["# Charter", ""]
        if archetype is not None:
            out += [f"**ARCHETYPE: {archetype}.**", ""]
        tops, subs = [], {}
        # `extra` carries NEGOTIABLE subsections. The CORE set alone cannot express 'the
        # charter HAS a subsection somebody recorded as agreed out', because a CORE row can
        # never legitimately be agreed out - the category-error arm fires first and the stale
        # arm is unreachable. Measured: the first version of that case silently PASSED.
        for k in tuple(TEMPLATE_CORE) + tuple(extra):
            if k in omit:
                continue
            top, _, sub = k.partition(".")
            if top not in tops:
                tops.append(top)
            if sub:
                subs.setdefault(top, []).append(sub)
        for top in sorted(tops, key=int):
            out += [f"## {top} - Section {top}", "", "Body.", ""]
            for sub in sorted(subs.get(top, []), key=int):
                out += [f"### {top}.{sub} Sub {sub}", "", "Body.", ""]
        q = tmp / (key or "charter.md")
        q.write_text(NL.join(out) + NL, encoding="utf-8")
        return q if declared is NO_DECL else (q, declared)
    return build


def checks_core_under(spec):
    """The CORE-floor verdict for one document under one declared-absence map."""
    path, declared = spec
    rep = Report()
    verify_file(rep, path, dict(SELFTEST_CFG, core_sections=declared))
    return rep.by_name().get(CORE)


def checks_arch_under(spec):
    """The archetype verdict for one document under one declared-absence reason."""
    path, declared = spec
    rep = Report()
    verify_file(rep, path, dict(SELFTEST_CFG, archetype_absent=declared))
    return rep.by_name().get(ARCH)


def checks_agreed_under(spec):
    """The agreed-out verdict for one document under one agreed-out map."""
    path, agreed = spec
    rep = Report()
    verify_file(rep, path, dict(SELFTEST_CFG, sections_agreed_out=agreed))
    return rep.by_name().get(AGREED)


def writes_pointer_charter(body, declared=NO_DECL, wrap=False):
    """A charter whose section 5 carries `body` as its pointer text.

    `wrap` hard-wraps the pointer across a line ending, which is the case a line-by-line
    matcher gets WRONG - and getting it wrong is what killed the first design of this arm.
    """
    def build(tmp):
        text = body
        if wrap and " " in body:
            cut = body.rfind(" ", 0, max(len(body) // 2, 1))
            text = body[:cut] + NL + body[cut + 1:]
        # THE PARENTS ARE DERIVED, NOT LISTED. Sections 1, 2 and 5 appear in TEMPLATE_CORE
        # only as SUBSECTIONS, so a loop that emits a heading per CORE entry produces no
        # '## 5' at all - and the arm then reported the section missing on both arms, which
        # read as the check firing correctly on the bad one.
        out = ["# Charter", "", "**ARCHETYPE: Research / analysis.**", ""]
        tops, subs = [], {}
        for k in TEMPLATE_CORE:
            top, _, sub = k.partition(".")
            if top not in tops:
                tops.append(top)
            if sub:
                subs.setdefault(top, []).append(sub)
        for top in sorted(tops, key=int):
            out += [f"## {top} - Section {top}", ""]
            out += ([text, ""] if top == "5" else ["Body.", ""])
            for sub in sorted(subs.get(top, []), key=int):
                out += [f"### {top}.{sub} Sub {sub}", "", "Body.", ""]
        q = tmp / "pointer.md"
        q.write_text(NL.join(out) + NL, encoding="utf-8")
        return q if declared is NO_DECL else (q, declared)
    return build


def checks_pointers_under(spec):
    """The relocation-pointer verdict for one document under one pointer map."""
    path, pointers = spec
    rep = Report()
    verify_file(rep, path, dict(SELFTEST_CFG, pointers=pointers,
                                check_numbered_headings="off"))
    return rep.by_name().get(PTR)


def _selftest_ceiling_confirms_the_floor(tmp):
    """THE CROSS-CHECK NO CASE ROW CAN MAKE: the ceiling PASSES what the floor FAILS.

    The defect the floor exists for was not merely unreported - it was CONFIRMED by the one
    instrument already pointed at charter shape. `charter structure` asks for never MORE than
    the template, and a charter missing 5.4 has fewer, which is exactly what MAPPING produces
    and therefore a PASS. So the check that looked like it covered charter shape said the
    charter was fine while TEST was missing from it.

    Without this assertion the two arms could drift into agreeing, and a case table can only
    show the new arm fires - never that nothing else would have.
    """
    d = tmp / "ceiling-confirms"
    d.mkdir(parents=True, exist_ok=True)
    path = writes_charter(omit=("5.4",), archetype="Research / analysis")(d)
    rep = Report()
    verify_file(rep, path, SELFTEST_CFG)
    by = rep.by_name()
    struct, core = by.get(STRUCT), by.get(CORE)
    if struct != PASS:
        return f"FAIL - expected the CEILING check to PASS on a charter missing 5.4, got {struct!r}"
    if core != FAIL:
        return f"FAIL - expected the FLOOR check to FAIL on a charter missing 5.4, got {core!r}"
    return PASS


def _selftest_archetype_needles_disagree(tmp):
    """THE MEASUREMENT THAT DECIDED THE SHAPE, kept as an assertion so it cannot be undone.

    Two naive needles were tried over the six house charters before this arm was written, and
    they answered WRONGLY IN OPPOSITE DIRECTIONS. Searching for the eleven NAMES matches
    ordinary prose - a charter discussing another project's archetype "declares" one. Searching
    for the WORD 'archetype' matches a sentence about emitted line counts.

    So the arm requires a LABELLED declaration, and this asserts both failure modes stay
    rejected. Without it, a later 'helpful' loosening would silently restore the false
    positives that made the original measurement wrong.
    """
    d = tmp / "archetype-needles"
    d.mkdir(parents=True, exist_ok=True)
    prose = writes_charter(archetype=None, key="prose.md")(d)
    body = prose.read_text(encoding="utf-8")
    # Both traps in one document: an archetype NAME in prose, and the WORD archetype.
    prose.write_text(body + NL.join([
        "", "This project is not a Claude skill, though it borrows from one.",
        "The archetype table has eleven rows; 20 of 22 archetype emits meet the cap.", "",
    ]), encoding="utf-8")
    rep = Report()
    verify_file(rep, prose, SELFTEST_CFG)
    if rep.by_name().get(ARCH) != FAIL:
        return ("FAIL - a charter merely MENTIONING an archetype name and the word "
                "'archetype' was accepted as declaring one")
    return PASS


def _selftest_gapless_confirms_the_defect(tmp):
    """THE ASSERTION NO CASE ROW CAN MAKE: the OLD instrument passes what the new one fails.

    The defect this check exists for was not merely unreported - it was CONFIRMED. A section
    numbered 1..16 satisfies check_headings' gapless rule perfectly, so the one instrument
    already pointed at subsection numbering said PASS. A case table can show the new check
    fires; only this can show that nothing else would have.

    It is a cross-CHECK assertion off ONE fixture, the same shape verify_confidential's
    cross-arm assertion uses, and without it the pair of checks could drift into agreeing.
    """
    d = tmp / "gapless-confirms"
    d.mkdir(parents=True, exist_ok=True)
    path = writes_subsections(5, 16)(d)
    rep = Report()
    verify_file(rep, path, SELFTEST_CFG)
    by = rep.by_name()
    heads, struct = by.get(HEADS), by.get(STRUCT)
    if heads != PASS:
        return f"FAIL - expected the gapless check to PASS on 1..16, got {heads!r}"
    if struct != FAIL:
        return f"FAIL - expected the structure check to FAIL on 16-vs-8, got {struct!r}"
    return PASS


def writes_plan(rows, triple=True, header_purpose=True):
    """A PLAN FILE: a header key-value table, then a sub-step table.

    `rows` is a list of (name, closed, filled) - `filled` being the text put in all three
    of purpose/serves/deliverable, or None/"" for the blank case.

    THE ARMS DIFFER IN ONE THING EACH, deliberately. `triple` toggles whether the three
    COLUMNS exist at all; `filled` toggles whether they are ANSWERED; `closed` toggles
    whether the row is a finished record. Those are three different defects and a builder
    that could only produce one of them would let the check pass while proving one third of
    what it claims.
    """
    def build(tmp):
        out = ["# PLAN - a phase", "",
               "| | |", "| --- | --- |",
               "| **status** | IN PROGRESS |"]
        if header_purpose:
            out.append("| **purpose** | so that the phase is for something nameable |")
        out += ["", "## 1 - The sub-steps", ""]
        if triple:
            out += ["| # | sub-step | purpose | serves | deliverable |",
                    "| --- | --- | --- | --- | --- |"]
        else:
            out += ["| # | sub-step | done when |", "| --- | --- | --- |"]
        for i, (name, closed, filled) in enumerate(rows, 1):
            nm = "~~**" + name + "**~~" if closed else "**" + name + "**"
            if triple:
                v = filled or ""
                out.append(f"| **{i}** | {nm} | {v} | {v} | {v} |")
            else:
                out.append(f"| **{i}** | {nm} | it is done |")
        q = tmp / "case.md"
        q.write_text(NL.join(out) + NL, encoding="utf-8")
        return q
    return build


def _selftest_plan_purpose_is_the_only_witness(tmp):
    """THE ASSERTION NO CASE ROW CAN MAKE: every OTHER check passes the document this one
    fails.

    The defect was not merely unreported - it was CONFIRMED by everything pointed at a plan
    file. A sub-step table with no purpose column is a perfectly well-formed table with
    perfectly gapless headings, so `tables well-formed` and `heading numbering` both say
    PASS over the exact shape this check exists to find. A case row can show the new check
    fires; only this can show that nothing already in the checker would have.
    """
    d = tmp / "plan-only-witness"
    d.mkdir(parents=True, exist_ok=True)
    path = writes_plan([("A STEP WITH NO STATED PURPOSE", False, None)], triple=False)(d)
    rep = Report()
    verify_file(rep, path, dict(SELFTEST_CFG, plan_scope=["*.md"]))
    by = rep.by_name()
    for name in (TABLES, HEADS):
        if by.get(name) != PASS:
            return f"FAIL - expected {name!r} to PASS on the purposeless plan, got {by.get(name)!r}"
    if by.get(PLANP) != FAIL:
        return f"FAIL - expected {PLANP!r} to FAIL on the purposeless plan, got {by.get(PLANP)!r}"
    return PASS


STRUCT = "charter structure"
ARCH, CORE = "charter archetype", "core sections present"
AGREED = "sections agreed out"
PTR = "relocation pointers"
PLANP = "plan purpose"


def cases():
    """The charter checks' case table, moved row for row from verify_md.py's on 2026-10-12.

    EVERY ROW IS PROVED BOTH WAYS unless it says why it cannot be.
    """
    return [
        # THE CHARTER-STRUCTURE PAIR. Both arms are gapless 1..n, so check_headings PASSES
        # on BOTH - which is the defect, and why the twin is 8 rather than something ragged.
        # A twin with a gap would fail for the wrong reason and prove nothing about excess.
        Case("section with MORE subsections than the template", checks(STRUCT),
             writes_subsections(5, 9), writes_subsections(5, 8)),
        # A SUBSET IS MAPPING, and this is the arm that stops the check being "must equal 8".
        # Without it, a check that fired on any count != 8 would pass the row above and
        # condemn three of the five charters this house has already closed as correct.
        Case("FEWER subsections than the template is mapping, not a finding", checks(STRUCT),
             writes_subsections(5, 9), writes_subsections(5, 3)),
        # THE DECLARATION, proved on ONE document: the same excess fails undeclared and
        # passes declared. Two documents would let the pair pass while comparing two things.
        Case("a DECLARED excess passes", checks_struct_under,
             writes_subsections(5, 9, {}),
             writes_subsections(5, 9, {"5": "this section owns the domain rules"})),
        # A BLANK REASON IS REFUSED - the same rule check_checkers v13 applies one level up,
        # because a command line cannot carry a reason and the reason IS the distinction.
        Case("a declared excess with a BLANK reason is refused", checks_struct_under,
             writes_subsections(5, 9, {"5": "   "}),
             writes_subsections(5, 9, {"5": "declared, with an actual reason"})),
        # AND THE DECLARATION CANNOT OUTLIVE ITS FACTS. Once the section is mapped back down
        # the declaration must go red, or a config records an exemption for a defect that no
        # longer exists - the DECL-STALE shape, one level down.
        Case("a declaration for a section that is NOT in excess is stale",
             checks_struct_under,
             writes_subsections(5, 8, {"5": "was an excess once"}),
             writes_subsections(5, 8, {})),
        # THE SCOPE, proved on one input: a non-charter is not judged against a charter's
        # shape. Without it the check would condemn every README and plan file in a run.
        Case("out of size_scope reports N/A, not a failure (structure)",
             checks_cfg(STRUCT, size_scope=["nothing-matches-this"]),
             writes_subsections(5, 9), writes_subsections(5, 9),
             want=NA, good_want=NA),
        # ---------------------------------------------------------------- DEVICE 1: the FLOOR
        # THE PAIR IS ONE KEY APART. Both arms are gapless and both are a SUBSET of the
        # template, so charter structure PASSES on both - which is the whole point, and why
        # the twin omits nothing rather than omitting something else.
        Case("a MISSING CORE subsection is a finding", checks(CORE),
             writes_charter(omit=("5.4",), archetype="Research / analysis"),
             writes_charter(archetype="Research / analysis")),
        # THE DISCRIMINATOR, and without it the arm would be 'every subsection must exist'.
        # A DEFAULT or OPTIONAL subsection is Round 0.5's decision to take; only CORE is
        # "never negotiated away". 1.4 is DEFAULT and 1.6 OPTIONAL, so neither may fire.
        Case("a missing DEFAULT or OPTIONAL subsection is NOT a finding", checks(CORE),
             writes_charter(omit=("1.5",), archetype="Research / analysis"),
             writes_charter(archetype="Research / analysis")),
        Case("a DECLARED absent CORE subsection passes", checks_core_under,
             writes_charter(omit=("5.8",), archetype="Research / analysis", declared={}),
             writes_charter(omit=("5.8",), archetype="Research / analysis",
                            declared={"5.8": "no charter-writing rules yet; see the plan"})),
        Case("a declared CORE absence with a BLANK reason is refused", checks_core_under,
             writes_charter(omit=("5.8",), archetype="Research / analysis",
                            declared={"5.8": "   "}),
             writes_charter(omit=("5.8",), archetype="Research / analysis",
                            declared={"5.8": "declared, with an actual reason"})),
        # AND IT CANNOT OUTLIVE ITS FACTS - the DECL-STALE shape, exactly as the ceiling and
        # check_checkers apply it. Once 5.8 is written the declaration must go red.
        Case("a declaration for a CORE subsection that IS present is stale", checks_core_under,
             writes_charter(archetype="Research / analysis",
                            declared={"5.8": "was absent once"}),
             writes_charter(archetype="Research / analysis", declared={})),
        Case("out of size_scope reports N/A, not a failure (CORE floor)",
             checks_cfg(CORE, size_scope=["nothing-matches-this"]),
             writes_charter(omit=("5.4",), archetype="Research / analysis"),
             writes_charter(omit=("5.4",), archetype="Research / analysis"),
             want=NA, good_want=NA),
        Case("the CEILING check PASSES the charter the FLOOR fails",
             _selftest_ceiling_confirms_the_floor, lambda tmp: tmp, want=PASS,
             unpaired_reason="this is a CROSS-CHECK invariant off one fixture, not a "
                             "fire-on-bad check - it asserts that the OLD instrument passes "
                             "the very document the new one fails, which is what makes the "
                             "floor a new question rather than a second opinion"),
        # ---------------------------------------------------------------- DEVICE 3: archetype
        Case("a charter naming NO archetype is a finding", checks(ARCH),
             writes_charter(archetype=None),
             writes_charter(archetype="Analysis + rebuild of an existing artefact")),
        # PUNCTUATION AND CASE ARE FOLDED AWAY ON PURPOSE. The check is about whether the
        # DECISION was recorded, never about typography - a charter written with an em dash
        # has named its archetype exactly as well as one written with a hyphen, and an arm
        # that told them apart would teach people to copy a dash rather than make a choice.
        Case("an archetype written with different punctuation still counts", checks(ARCH),
             writes_charter(archetype="Automation 4 - telepathy"),
             writes_charter(archetype="automation 1 — FILE and Data")),
        Case("a DECLARED absent archetype passes", checks_arch_under,
             writes_charter(archetype=None, declared=None),
             writes_charter(archetype=None,
                            declared="a house-tooling repo, not one of the eleven")),
        Case("a declared absent archetype with a BLANK reason is refused", checks_arch_under,
             writes_charter(archetype=None, declared="   "),
             writes_charter(archetype=None, declared="declared, with an actual reason")),
        Case("a declaration over a charter that DOES name one is stale", checks_arch_under,
             writes_charter(archetype="Claude skill", declared="fits none of the eleven"),
             writes_charter(archetype="Claude skill", declared=None)),
        Case("out of size_scope reports N/A, not a failure (archetype)",
             checks_cfg(ARCH, size_scope=["nothing-matches-this"]),
             writes_charter(archetype=None), writes_charter(archetype=None),
             want=NA, good_want=NA),
        Case("a MENTION is not a DECLARATION",
             _selftest_archetype_needles_disagree, lambda tmp: tmp, want=PASS,
             unpaired_reason="it asserts that two NAIVE needles stay rejected - the pair "
                             "that answered wrongly in OPPOSITE directions over the six "
                             "house charters before this arm was written. There is no "
                             "'good' arm: the good arm is every other archetype case"),
        # ------------------------------------------------------------- DEVICE 4: agreed out
        # THE CATEGORY ERROR, and it is the one that matters: naming a CORE row here would
        # buy a way past the FLOOR by writing a sentence. 5.4 is CORE, 5.6 is OPTIONAL.
        Case("a CORE subsection cannot be agreed out", checks_agreed_under,
             writes_charter(omit=("5.4",), archetype="Research / analysis",
                            declared={"5.4": "we do not test"}),
             writes_charter(omit=("5.4",), archetype="Research / analysis",
                            declared={"5.6": "publication is genuinely off the table"})),
        Case("agreeing out a subsection the template does not offer", checks_agreed_under,
             writes_charter(archetype="Research / analysis",
                            declared={"9.9": "a section that does not exist"}),
             writes_charter(archetype="Research / analysis",
                            declared={"1.6": "under 250 lines; no index needed"})),
        Case("an agreed-out entry with a BLANK reason is refused", checks_agreed_under,
             writes_charter(archetype="Research / analysis", declared={"1.6": "  "}),
             writes_charter(archetype="Research / analysis",
                            declared={"1.6": "under 250 lines; no index needed"})),
        # AND IT CANNOT OUTLIVE ITS FACTS. 1.5 is CORE and always emitted by the fixture, so
        # a record saying it was agreed out is stale by construction; the twin names a row
        # the fixture genuinely omits.
        Case("a record for a subsection the charter HAS is stale", checks_agreed_under,
             writes_charter(archetype="Research / analysis", extra=("5.2",),
                            declared={"5.2": "not a git repository"}),
             writes_charter(archetype="Research / analysis", extra=("5.2",),
                            declared={"1.6": "under 250 lines; no index needed"})),
        # THE OPT-IN, proved on one input. Wouter's ruling: an empty map is N/A with its
        # reason, never a silent pass - the md.plan_scope precedent. It ships DISABLED, and
        # this row is what stops that being mistaken for a pass.
        Case("an EMPTY agreed-out map reports N/A with its reason, not a pass",
             checks_cfg(AGREED, sections_agreed_out={}),
             writes_charter(archetype="Research / analysis"),
             writes_charter(archetype="Research / analysis"),
             want=NA, good_want=NA),
        Case("out of size_scope reports N/A, not a failure (agreed out)",
             checks_cfg(AGREED, size_scope=["nothing-matches-this"],
                        sections_agreed_out={"5.4": "we do not test"}),
             writes_charter(archetype="Research / analysis"),
             writes_charter(archetype="Research / analysis"),
             want=NA, good_want=NA),
        # -------------------------------------------------------- DEVICE 5: relocation pointers
        # THE PAIR IS ONE SENTENCE APART, and both documents are otherwise identical: the
        # relocation is invisible to every other arm, which is the whole reason this exists.
        Case("a relocated block whose POINTER has gone", checks_pointers_under,
             writes_pointer_charter("This section was reorganised.",
                                    declared={"5": ["see the house file"]}),
             writes_pointer_charter("Relocated - see the house file, and not restated.",
                                    declared={"5": ["see the house file"]})),
        # THE WRAP CASE, and it is the one that decided the design. The first version of this
        # device searched prose LINE BY LINE and produced four false positives in six over the
        # real charters, three of them purely because a claim and its destination landed on
        # different lines. Both arms here declare the same phrase; only the wrapping differs.
        Case("a pointer HARD-WRAPPED across a line ending still counts", checks_pointers_under,
             writes_pointer_charter("This section was reorganised.",
                                    declared={"5": ["see the house file"]}),
             writes_pointer_charter("Relocated - see the house file, and not restated.",
                                    declared={"5": ["see the house file"]}, wrap=True)),
        # A SECTION THAT IS GONE ENTIRELY is the shape a pointer's return path disappearing
        # takes, and the house rule it enforces - never delete a heading, it is the return
        # path a pointer resolves against - had no check at all before this.
        Case("a declared pointer whose SECTION has gone", checks_pointers_under,
             writes_pointer_charter("Relocated - see the house file.",
                                    declared={"9": ["see the house file"]}),
             writes_pointer_charter("Relocated - see the house file.",
                                    declared={"5": ["see the house file"]})),
        Case("a BLANK pointer phrase is refused", checks_pointers_under,
             writes_pointer_charter("Relocated - see the house file.",
                                    declared={"5": ["  "]}),
             writes_pointer_charter("Relocated - see the house file.",
                                    declared={"5": ["see the house file"]})),
        Case("an EMPTY pointer map reports N/A with its reason, not a pass",
             checks_cfg(PTR, pointers={}, check_numbered_headings="off"),
             writes_pointer_charter("Relocated - see the house file."),
             writes_pointer_charter("Relocated - see the house file."),
             want=NA, good_want=NA),
        Case("out of size_scope reports N/A, not a failure (pointers)",
             checks_cfg(PTR, size_scope=["nothing-matches-this"],
                        pointers={"5": ["a phrase that is absent"]},
                        check_numbered_headings="off"),
             writes_pointer_charter("Relocated."), writes_pointer_charter("Relocated."),
             want=NA, good_want=NA),
        Case("the gapless check CONFIRMS what the structure check catches",
             _selftest_gapless_confirms_the_defect, lambda tmp: tmp, want=PASS,
             unpaired_reason="this is a CROSS-CHECK invariant off one fixture, not a "
                             "fire-on-bad check - it asserts that the OLD instrument passes "
                             "the very document the new one fails, which is the fact that "
                             "made the defect invisible. Both arms would want PASS"),
        # THE PLAN-PURPOSE PAIR. The bad arm is the shape every plan file in this house had
        # on 2026-09-10: a sub-step table with no purpose column at all.
        Case("an OPEN sub-step row with no purpose/serves/deliverable column",
             checks_cfg(PLANP, plan_scope=["*.md"]),
             writes_plan([("A", False, None)], triple=False),
             writes_plan([("A", False, "so that the drift cannot come back unnamed")])),
        # A CLOSED ROW IS A FINISHED RECORD. This is the arm that stops the check being
        # "every row": without it, enabling the check on a repository would redden 44 rows
        # across 12 archived plan files, and a check that reddens finished work is one
        # somebody switches off. The two arms differ ONLY in the strikethrough.
        Case("a CLOSED row is not judged - it is a finished record",
             checks_cfg(PLANP, plan_scope=["*.md"]),
             writes_plan([("A", False, None)], triple=False),
             writes_plan([("A", True, None)], triple=False)),
        # A BLANK CELL IS REFUSED even where the column exists - the same rule a declared
        # checker absence is held to. An empty cell reads the same whether somebody decided
        # or nobody looked, which is exactly what a declared NONE prevents.
        Case("a column that exists but is left BLANK is refused",
             checks_cfg(PLANP, plan_scope=["*.md"]),
             writes_plan([("A", False, "")]),
             writes_plan([("A", False, "NONE - this sub-step leaves only edits behind")])),
        # THE PHASE LEVEL, which is the one the retrofit is likeliest to skip: the rows get
        # filled in and the header table keeps only 'produces' and 'serves', neither of
        # which says what the phase is FOR.
        Case("the phase itself must state a purpose, not only its rows",
             checks_cfg(PLANP, plan_scope=["*.md"]),
             writes_plan([("A", False, "so that X")], header_purpose=False),
             writes_plan([("A", False, "so that X")], header_purpose=True)),
        # THE SCOPE, both ways. Out of plan_scope a charter or a README is not judged
        # against a plan file's shape; and an EMPTY plan_scope is a DISABLED check that says
        # so, never a silent pass.
        Case("out of plan_scope reports N/A, not a failure",
             checks_cfg(PLANP, plan_scope=["nothing-matches-this"]),
             writes_plan([("A", False, None)], triple=False),
             writes_plan([("A", False, None)], triple=False),
             want=NA, good_want=NA),
        Case("an EMPTY plan_scope reports N/A with its reason, not a pass",
             checks_cfg(PLANP, plan_scope=[]),
             writes_plan([("A", False, None)], triple=False),
             writes_plan([("A", False, None)], triple=False),
             want=NA, good_want=NA),
        Case("nothing else in the checker catches a purposeless plan row",
             _selftest_plan_purpose_is_the_only_witness, lambda tmp: tmp, want=PASS,
             unpaired_reason="a CROSS-CHECK invariant off one fixture, the same shape as "
                             "the gapless one above: it asserts that the checks ALREADY "
                             "pointed at a plan file pass the document this one fails. "
                             "Both arms would want PASS"),
    ]


def selftest() -> int:
    """Every charter case through verify_md.verify_file, then the contract with verify_md.py."""
    import shutil
    import tempfile
    from pathlib import Path

    vm = _bind_harness()
    print("SELFTEST - each charter check must fire on a bad document AND stay quiet on a good one")
    print()
    tmp = Path(tempfile.mkdtemp(prefix="verify_charter_selftest_"))
    try:
        ok, paired, unpaired = run_cases(cases(), tmp, width=28)
        report_pairing(paired, unpaired)
        # THE CONTRACT. verify_md.py reports these names when this file is missing, and a
        # toleration is keyed on them - so a rename on one side alone would make a missing
        # checker and a stale declaration both look like something else.
        same = tuple(vm.CHARTER_ROWS) == ROWS
        ok &= same
        print(f"  {'OK  ' if same else 'MISS'} {'row names match verify_md':<28} -> "
              f"{len(ROWS)} here, {len(vm.CHARTER_ROWS)} there")
        names = {STRUCT, ARCH, CORE, AGREED, PTR, PLANP}
        named = names == set(ROWS)
        ok &= named
        print(f"  {'OK  ' if named else 'MISS'} {'every row has a case name':<28} -> "
              f"{sorted(names ^ set(ROWS)) or 'none differ'}")
        # THE WIRING. A case table proves each check fires when called; only this proves the
        # general checker still CALLS them - a dropped call would pass every case above.
        doc = tmp / "wired.md"
        doc.write_text("# Doc" + NL + NL + "## 1 - One" + NL + NL + "Body." + NL, encoding="utf-8")
        rep = Report()
        verify_file(rep, doc, SELFTEST_CFG)
        seen = [n for n in ROWS if n in rep.by_name()]
        wired = len(seen) == len(ROWS)
        ok &= wired
        print(f"  {'OK  ' if wired else 'MISS'} {'verify_md reports all six':<28} -> "
              f"{len(seen)} of {len(ROWS)}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print("\nSELFTEST: " + ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


def main(argv) -> int:
    if argv[1:] == ["--selftest"]:
        return selftest()
    print("verify_charter.py has no run of its own: verify_md.py calls it for every document.")
    print("    uv run python tools/verify_charter.py --selftest    # prove every charter check can FAIL")
    print("Nothing was checked.")
    return 2


if __name__ == "__main__":
    import sys
    sys.exit(main(sys.argv))
