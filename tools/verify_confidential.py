#!/usr/bin/env python3
"""verify_confidential.py - is a forbidden phrase in this project's FILES, or in its HISTORY?
CHECKER VERSION 4 (2026-09-08)

If a project's copy says a lower version than this one, it is stale - see the "Checkers"
line for each version in ...\\Coding\\templates\\TEMPLATE-CHANGELOG.md and re-copy.

THE GAP THIS FILLS, AND IT IS TWO GAPS. The document checker scans DOCUMENTS: point it at
*.md and a commit touching only source, config and data reports its forbidden-phrase check
as N/A, 0 examined - structurally, not because it looked and found nothing. And no checker
here has ever looked at a repository's HISTORY at all.

    uv run python tools/verify_confidential.py
    uv run python tools/verify_confidential.py --project ../other-project
    uv run python tools/verify_confidential.py --history CLAUDE.md README.md
    uv run python tools/verify_confidential.py --baseline origin/main
    uv run python tools/verify_confidential.py --selftest

FIVE POPULATIONS, AND EACH IS A DIFFERENT QUESTION RATHER THAN A LONGER VERSION OF THE LAST.

    TREE          every file git TRACKS at HEAD, whatever its type
    ADDED LINES   only what this change ADDS, against a pinned baseline
    MESSAGES      every commit message reachable from any ref
    HISTORY       every revision of the paths DECLARED for it, across all refs
    ALL BLOBS     every blob reachable from any ref, whatever its path

WHY FIVE AND NOT ONE MERGED VERDICT: the whole finding behind them is that a CLEAN TREE SAYS
NOTHING ABOUT ANY OF THE OTHER FOUR. A merged row would let the cheapest arm's PASS stand in
for the population nobody scanned, which is the failure this checker exists to name.

AND A SIXTH ROW THAT IS NOT A POPULATION AT ALL - THE REPORT SCANNED FOR ITS OWN LIST (v3).
It is the answer to a leak v2 shipped WHILE OBEYING ITS OWN RULE: this checker prints a
phrase's POSITION and never its text, and every finding it prints is LOCATED BY A FILE PATH.
Where a path segment is itself a forbidden phrase, the report published it verbatim - into a
terminal, a CI log, or a document naming which files carry a phrase. Measured on a real
project: two tracked paths carried a client identifier in the FILENAME, and the report named
both. Every build site now masks (house_common.mask_phrases), and the sixth row asserts the
result, because masking the arms that exist covers today and an assertion covers the arm
somebody adds next. A path IS a population no arm scans, separately - that gap is recorded,
not closed here.

AND A SEVENTH ROW, WHICH ASSERTS THAT THE TREE ARM ACTUALLY READ WHAT IT COUNTED (v4).
Until v4 a tracked file this checker could not OPEN was answered with `continue`: it left
the denominator, and the arm reported PASS over whatever was left. Measured on a repository
of four tracked files - "PASS, 1 examined" with three never opened, and nothing in the
output saying which or why.

THE CAUSE WAS NOT IN THIS FILE, WHICH IS WHY THE FIX IS IN TWO PLACES. git quotes any
output path holding a byte above 0x80, so a filename carrying an em dash came back as
`"Some Name \\342\\200\\224 More.md"` - not a path. house_common.git now disables
core.quotePath for every caller, because three sites in THIS script alone read a path out
of git and none of them looked wrong. But quoting was one route to an unopenable path and
not the only one - a permission denial, a path over the platform's limit, a file tracked at
HEAD and deleted from disk - so the symptom is REPORTED as well as the cause fixed. A
scanner whose denominator can silently shrink is the exact failure every other arm here
exists to name, arriving from inside.

ITS DENOMINATOR IS WHAT THE ARM TRIED TO OPEN, not the number of failures, because a zero
denominator is VOID in the shared result model - so counting failures would void the row on
every clean run, and a row that is always void is not a control.

AND THE FOOTER CARRIES A FINGERPRINT OF THE LIST (v3), never the list. A SCAN MEASURES A
LIST AGAINST A TREE, AND UNTIL v3 ONLY ONE OF THE TWO WAS RECORDED - the report said how
MANY needles it checked and nothing about WHICH. Measured: adding ONE needle took one
project's finding from 27 locations in 6 files to 87 in 12, and turned another - closed,
verified and force-pushed clean the day before - RED again on two arms with nothing in it
changed. So a CLEAN verdict could not be told from a stale one, and the one-pass argument
that justifies every irreversible history rewrite here is only as good as the list on the
day. A hash and never a copy: a copy of the list in a report is this checker's own leak.

THE THREE ARMS ADDED IN v2 CAME FROM A MEASUREMENT, NOT AN IDEA - a phrase can sit in six
places and v1 covered two of them.

  * ADDED LINES: the document checker's --baseline arm is MARKDOWN-ONLY, so a commit
    touching only source, config and data reports "forbidden in added lines" as N/A over
    zero examined lines. Structurally, not because it looked.
  * MESSAGES: read by NOTHING in this house. `git log` over a public repository publishes a
    message exactly as widely as it publishes a file, and a rewrite scoped by a blob scan
    leaves the message standing - `--replace-text` rewrites blobs, `--replace-message` is a
    different flag. Measured on two repositories: one carrying message each, and in both
    cases the tree arm was CLEAN.
  * ALL BLOBS: the HISTORY arm is PATH-SCOPED, so a phrase in an UNDECLARED path, or in one
    DELETED before HEAD, is invisible to it. Measured: an arm reporting PASS over 134
    revisions of one declared path, on a repository whose history carried the phrase in 5
    blobs across 2 other paths. The declared arm was not wrong - it answered the question it
    was asked - which is why the fix is a second arm rather than a correction to the first.

WHY HISTORY IS NOT AN EXTENSION OF TREE: making a repository public exposes every commit,
not the current state. Taking a phrase out of the working tree changes nothing about what a
clone can read, and the only thing that removes it is a history rewrite - which is
irreversible, so this checker MEASURES and never repairs. The order matters and it is not
symmetrical: rewrite BEFORE a repository goes public, never after. While it is private the
old objects were only ever visible to their owner and a rewrite costs a force-push; once
public they have been served, and a force-push does not reliably unserve them.

IT SCANS WHAT GIT TRACKS, WHICH IS THE POINT FOR A REPOSITORY THAT MIGHT BE PUBLISHED - an
untracked working file is not what gets published. THE COROLLARY IS A TRAP: a NEW file is
invisible to this check until it is staged, and the whole point of a new file is that all of
it is new. STAGE FIRST, THEN SCAN. It reports the count of files it actually opened, because
a scan that opened none is VOID rather than clean.

IT PRINTS A PHRASE'S POSITION IN THE LIST, NEVER ITS TEXT. Moving a sensitive list outside
the repository and then echoing its contents into a terminal, a CI log or a pasted failure
report is the same leak by a different route - and that route reaches places no scanner can
clean up afterwards. The scanner ships; the list never does.

A POSITIVE CONTROL RUNS EVERY TIME, AND A RUN WHOSE CONTROL DID NOT FIRE IS VOID. A scan
reporting zero over a tree you believe is clean is the answer you were hoping for, which is
exactly why it does not get questioned. The control is PLANTED from what the tree actually
contains rather than hardcoded, because a fixed phrase stops being present the moment the
work moves elsewhere.

AND SINCE v2 EVERY ARM PLANTS ITS OWN, FROM ITS OWN POPULATION. One control cannot validate
five scans: the tree control firing says nothing whatever about whether the message walk
read a single message. An arm whose control did not fire is VOID BY ITSELF, and the summary
row names which arms were validated - so a reader cannot take one green row as the answer
for a population it never covered.

    THE FAILURE MODES THIS ARRANGEMENT IS BUILT AGAINST, all of them observed:
      * a pattern tool aborting mid-run, printing nothing and exiting 0
      * a backslash in a pattern read as a regex escape, so a literal path matches nothing
      * a '#' line in the list read as a needle rather than as a comment
      * a declared list that is not on disk, reported as N/A instead of VOID
      * a control planted in a file the scan's own file set excludes, so it can never fire

WHERE THE LIST COMES FROM, AND WHY THERE IS NO SECOND KEY FOR IT. It reads the SAME
declaration the document checker reads - 'md.forbidden_phrases' inline, plus
'md.forbidden_phrases_file', with VERIFY_FORBIDDEN_LIST overriding the path so CI can supply
its own copy as a secret. A key of its own would be a second place to declare one list,
which is how the two come to disagree. A declared list that cannot be read is VOID.

Exit 0 when every arm passed or is a declared N/A and the control fired. Exit 1 on a
finding. Exit 2 when the comparison COULD NOT RUN - no list, an unreadable list, nothing
tracked, or a control that did not fire - which is not the same fact as having looked.
"""
from __future__ import annotations

import argparse
import fnmatch
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

# The shared plumbing. COPY house_common.py ALONGSIDE THIS FILE - without it the checker
# cannot start. check_checkers.py tracks it, so a project that copied one and not the other
# gets a reported finding rather than an import error at the worst possible moment.
from house_common import (                                       # noqa: E402
    FAIL, NA, PASS, RC_FAILED, RC_OK, VOID, Case, Report, added_line_runs, baseline_guard,
    finish, git, git_bytes, list_fingerprint, load_section, mask_phrases, report_pairing,
    resolve_list, resolve_revision, run_cases, safe_stdout, wants_report_json,
)

safe_stdout()

FORBIDDEN_LIST_ENV = "VERIFY_FORBIDDEN_LIST"

DEFAULT_CONFIG = {
    "history_paths": [],
    "skip_globs": [],
    "scan_commit_messages": True,
    "scan_all_history_blobs": True,
    "max_history_blobs": 20000,
}

CONFIG_COMMENTS = {
    "history_paths": "Paths whose EVERY REVISION is scanned, e.g. ['CLAUDE.md']. Empty means the DECLARED-PATH arm reports N/A WITH THAT REASON - never CLEAN, because 'nobody declared a path' and 'every revision is clean' are different facts. It is the cheap, targeted arm; scan_all_history_blobs is the one that answers 'what can a clone read'.",
    "skip_globs": "Tracked paths to leave out, e.g. ['tests/fixtures/*']. Each one is a DECISION - a scan that quietly skips a file is the failure this checker exists to prevent - so the report names how many were skipped and by which glob. It applies to the tree, added-lines and all-blobs arms, matched in the all-blobs arm against the path the object had IN THAT REVISION, which is not always the path it has now.",
    "scan_commit_messages": "Scan every commit message reachable from any ref. TRUE BY DEFAULT, and the default is the point: nothing else in this house reads a message at all, and `git log` over a public repository publishes one exactly as widely as a file. Setting it false is a DECLARATION that has to carry a reason someone will read, not a quiet default - and the row then reports N/A WITH THAT REASON rather than passing.",
    "scan_all_history_blobs": "Walk EVERY blob reachable from every ref, whatever its path. TRUE BY DEFAULT because history_paths is path-scoped, so its PASS is not evidence that a repository's history is clean - a phrase in an undeclared path, or in a path DELETED before HEAD, is invisible to it. Making the wider arm opt-in would reproduce the very defect it was built to fix. Off is a declaration, and the row then says so.",
    "max_history_blobs": "A ceiling on the all-blobs arm. Over it the arm is VOID WITH ITS REASON, never a pass - because a checker that HANGS an unattended run is worse than one that fails, and 'it was still going' is indistinguishable afterwards from 'it found nothing'. Raise it deliberately, or narrow the arm with skip_globs.",
}

# The document checker's keys, read rather than duplicated. One list, one declaration.
MD_LIST_KEYS = {"forbidden_phrases": [], "forbidden_phrases_file": ""}

# THE ROW NAMES, AT MODULE LEVEL SO THE REPORT AND THE SELFTEST CANNOT DISAGREE. v1 defined
# three of them down in the selftest, which worked only while build_report happened to spell
# the same strings by hand - a probe keyed to a row name that no longer exists does not fail
# loudly, it reports "NO SUCH ROW" for whichever arm was under test.
TREE = "forbidden phrases absent (tree)"
UNREAD = "every tracked file was actually read"
ADDED = "forbidden phrases absent (added lines)"
MSGS = "forbidden phrases absent (commit messages)"
HIST = "forbidden phrases absent (history)"
BLOBS = "forbidden phrases absent (all history blobs)"
LEAK = "the report itself names no phrase"
CTRL = "the positive control fired"


def tracked_files(root: Path) -> list[str]:
    """What git tracks at HEAD. An untracked file is not what gets published."""
    r = git(root, "ls-files")
    if r.returncode != 0:
        return []
    return [ln for ln in (r.stdout or "").splitlines() if ln.strip()]


def skipped_by(rel: str, globs) -> str | None:
    for g in globs:
        if fnmatch.fnmatch(rel, g):
            return g
    return None


def scan_text(text: str, phrases, extra: str | None = None):
    """Return [(line no, needle index)]. Index 0 marks the planted control.

    CASE-INSENSITIVE AND PLAIN SUBSTRING, never a regex: a backslash in a pattern is a
    regex escape, so searching for a literal Windows path asks for whitespace where a
    separator was meant and matches nothing at all - a clean-looking zero.
    """
    pairs = [(i + 1, p.lower()) for i, p in enumerate(phrases)]
    if extra:
        pairs.append((0, extra.lower()))
    hits = []
    for n, line in enumerate(text.splitlines(), 1):
        low = line.lower()
        for idx, needle in pairs:
            if needle in low:
                hits.append((n, idx))
    return hits


def scan_tree(root: Path, files, phrases, globs, control=None):
    """Return (hits, opened, skipped, unreadable). A hit is (rel, line, index) - no text.

    AN UNREADABLE TRACKED FILE IS A FINDING, NOT A SMALLER RUN (v4). Until v4 the OSError
    below was answered with `continue`: the file left the denominator, `opened` never
    counted it, and the arm reported PASS over whatever remained. MEASURED on a repository
    of four tracked files: "PASS, 1 examined", with three files never opened and nothing in
    the output saying so.

    THE CAUSE WAS FIXED IN house_common.git (core.quotePath), AND THIS GUARD IS THE OTHER
    HALF, deliberately kept although the cause is gone. Quoting was one route to an
    unopenable tracked path; a permission denial, a path longer than the platform allows, a
    file tracked at HEAD but deleted from disk, and a path git still quotes because it holds
    a control character are others. Fixing the cause protects against the route that was
    measured; reporting the symptom protects against the next one - which is this house's
    rule to prefer a guard inside the shared thing to a patch on the caller that bit.

    IT DOES NOT COUNT TOWARDS `opened`, ON PURPOSE. The denominator must stay the number of
    files actually READ, or a run that opened nothing could report a healthy count made
    entirely of failures - and `opened` is what the VOID test keys on.
    """
    hits, opened, skipped, unreadable = [], 0, [], []
    for rel in files:
        g = skipped_by(rel, globs)
        if g:
            skipped.append((rel, g))
            continue
        try:
            text = (root / rel).read_text(encoding="utf-8", errors="replace")
        except OSError as e:
            unreadable.append((rel, e.__class__.__name__))
            continue
        opened += 1
        for n, idx in scan_text(text, phrases, control):
            hits.append((rel, n, idx))
    return hits, opened, skipped, unreadable


def plant_control(root: Path, files, globs) -> str | None:
    """A needle CERTAIN to be present, taken from the tree rather than hardcoded.

    The first whitespace-delimited token of the first readable file in the scan's OWN file
    set. Taking it from that set is the load-bearing part: a control planted somewhere the
    scan does not reach can never fire, and this house has measured exactly that - a
    control written into an ignored directory, which no listing of tracked files includes.
    """
    for rel in files:
        if skipped_by(rel, globs):
            continue
        try:
            words = (root / rel).read_text(encoding="utf-8", errors="replace").split()
        except OSError:
            continue
        if words:
            return words[0]
    return None


def scan_history(root: Path, paths, phrases):
    """Return (per-path results, control, fired). Counts of revisions, never any content.

    THE CONTROL IS TAKEN FROM THE FIRST REVISION THIS ARM ACTUALLY READS, and then matched
    through the same scan_text() the phrases go through - so it proves the matcher works
    over THIS population. A control taken from the working tree would prove the tree arm
    works and say nothing whatever about whether a single revision was read back.

    per[i] counts REVISIONS carrying phrase i, not occurrences of it: the report says "in N
    of M revisions", and a count of hits would silently inflate that to something no reader
    could check against the revision count beside it.
    """
    results, control, fired = [], None, False
    for rel in paths:
        rl = git(root, "rev-list", "--all", "--", rel)
        revs = [x for x in (rl.stdout or "").splitlines() if x.strip()]
        if rl.returncode != 0 or not revs:
            results.append((rel, 0, 0, {}, "no revision of this path exists"))
            continue
        read_ok, per = 0, {}
        for sha in revs:
            sh = git(root, "show", f"{sha}:{rel}")
            if sh.returncode != 0:
                continue
            read_ok += 1
            text = sh.stdout or ""
            if control is None:
                control = first_token(text)
            got = {idx for _ln, idx in scan_text(text, phrases, control)}
            if 0 in got:
                fired = True
                got.discard(0)
            for i in got:
                per[i] = per.get(i, 0) + 1
        results.append((rel, len(revs), read_ok, per, None if read_ok else
                        "not one revision of this path could be read"))
    return results, control, fired


def first_token(text: str) -> str | None:
    """A control needle taken from real content. None when there is nothing to take.

    Shared by all five arms so 'planted from the arm's OWN population' is one rule with one
    implementation, rather than five that drift apart.
    """
    toks = text.split()
    return toks[0] if toks else None


def commit_messages(root: Path):
    """[(sha, body)] for every commit reachable from any ref, or None if git failed.

    SPLIT ON NUL, which a commit message CANNOT contain - git rejects one. Every printable
    separator anyone reaches for first can legally appear in a message, and the failure is
    silent: a message containing the separator splits into two, so the walk reads a body as
    a sha, finds no phrase in it, and reports a smaller clean run.
    """
    r = git(root, "log", "--all", "--format=%H%x00%B%x00")
    if r.returncode != 0 or r.stdout is None:
        return None
    parts = (r.stdout or "").split("\x00")
    out = []
    for i in range(0, len(parts) - 1, 2):
        sha = parts[i].strip()
        if sha:
            out.append((sha, parts[i + 1]))
    return out


def history_blobs(root: Path, ceiling: int):
    """({sha: {paths}}, [(sha, text)], void_reason) - every blob reachable from any ref.

    THE PATH IS THE ONE THE OBJECT HAD IN THAT REVISION, which is the whole point of the
    arm: a file renamed, moved to an archive, or deleted outright still has its old content
    reachable under its old name, and a scan keyed to the paths that exist at HEAD cannot
    see any of it.

    One `cat-file --batch` rather than a `git show` per object. That is not only speed: a
    per-object subprocess over a real history is slow enough that people switch the arm off,
    and an arm switched off reports nothing at all.
    """
    r = git(root, "rev-list", "--all", "--objects")
    if r.returncode != 0 or r.stdout is None:
        return {}, [], "git rev-list failed - the object list could not be enumerated"
    by_sha: dict[str, set] = {}
    for line in (r.stdout or "").splitlines():
        sha, _, path = line.partition(" ")
        if path.strip() and sha.strip():
            by_sha.setdefault(sha.strip(), set()).add(path.strip())
    if not by_sha:
        return {}, [], "no named object is reachable from any ref"
    names = "\n".join(by_sha).encode("ascii") + b"\n"
    chk = git_bytes(root, ["cat-file", "--batch-check=%(objectname) %(objecttype)"], names)
    blobs = [ln.split()[0] for ln in chk.stdout.decode("ascii", "replace").splitlines()
             if len(ln.split()) >= 2 and ln.split()[1] == "blob"]
    if not blobs:
        return by_sha, [], "no blob is reachable from any ref"
    if len(blobs) > ceiling:
        return by_sha, [], (f"{len(blobs)} blobs exceeds max_history_blobs {ceiling} - the "
                            f"arm did NOT run. Raise the ceiling deliberately or narrow it "
                            f"with skip_globs; a run that was still going and one that "
                            f"found nothing are indistinguishable afterwards")
    batch = git_bytes(root, ["cat-file", "--batch"], "\n".join(blobs).encode("ascii") + b"\n")
    data, pos, out = batch.stdout, 0, []
    while pos < len(data):
        nl = data.find(b"\n", pos)
        if nl == -1:
            break
        head = data[pos:nl].decode("ascii", "replace").split()
        pos = nl + 1
        if len(head) < 3 or not head[2].isdigit():
            break              # a malformed header means the walk has lost its place
        size = int(head[2])
        out.append((head[0], data[pos:pos + size].decode("utf-8", "replace")))
        pos += size + 1        # the object, then the newline git writes after it
    if not out:
        return by_sha, [], "not one blob could be read back from cat-file"
    return by_sha, out, None


def _problem(where: str, idx: int, phrases, sources) -> str:
    """One finding, as a POSITION - and `where` is MASKED, which v2 did not do.

    THE LEAK v2 SHIPPED WITH, and it sat inside the rule it was breaking. This checker
    declares that it prints a phrase's position and never its text - and every finding it
    prints is located BY A FILE PATH. Where a path segment is itself a forbidden phrase, the
    report published it verbatim, into a terminal, a CI log, or a document naming which files
    carry a phrase. Measured on a real project: two tracked paths carried an identifier in
    the FILENAME, and the report named both.

    THE COUNT IS DERIVED FROM `phrases` RATHER THAN PASSED. v2 took `n` separately and every
    call site passed `len(phrases)`; two arguments that must always agree are one chance for
    them not to, and 'phrase #4 of 6' beside a seven-needle list is a report nobody can
    reconcile afterwards.
    """
    return (f"{mask_phrases(where, phrases)}: forbidden phrase #{idx} of {len(phrases)} "
            f"(source: {sources[idx - 1]})")


def _why_void(examined: int, control, fired: bool, empty_reason: str):
    """None if this arm is judgeable, else the reason it is VOID. Shared by all five.

    THE THREE WAYS AN ARM FAILS TO MEAN ANYTHING, and each reads as a clean zero from
    outside: it examined nothing; its population had nothing to plant a control in; or the
    control was planted and did not come back. Written once because five copies of this
    reasoning is five chances for one of them to say "pass" where the others say VOID.
    """
    if not examined:
        return empty_reason
    if control is None:
        return ("nothing in this arm's own population to plant a control in, so a zero "
                "here proves nothing about the scan")
    if not fired:
        return ("the planted control did NOT fire over this population - the scan is not "
                "working here, so a zero is VOID rather than clean")
    return None


def arm_tree(rep, root, phrases, sources, files, globs, controls):
    """Every file git TRACKS at HEAD. An untracked file is not what gets published."""
    if not files:
        controls[TREE] = None
        # THE PROJECT'S OWN DIRECTORY NAME IS MASKED TOO. It is the one path segment a
        # reader would never think of as content, and a project folder named after a client
        # is exactly how a repository comes to need this checker in the first place.
        rep.record(TREE, 0, [], void_reason=(
            f"git tracks no file under {mask_phrases(root.name, phrases)} - either this is "
            f"not a repository, or nothing is staged. STAGE FIRST, then scan"))
        return
    hits, opened, skipped, unreadable = scan_tree(root, files, phrases, globs)
    problems = [_problem(f"{rel}:{n}", idx, phrases, sources) for rel, n, idx in hits]
    control = plant_control(root, files, globs)
    fired = False
    if control is not None:
        chits, _o, _s, _u = scan_tree(root, files, phrases, globs, control=control)
        fired = any(idx == 0 for _r, _n, idx in chits)
    controls[TREE] = fired
    rep.record(TREE, opened, problems, void_reason=_why_void(
        opened, control, fired,
        "no tracked file could be opened - the scan looked at nothing"))
    if skipped:
        rep.record("paths skipped by declaration", len(skipped), [],
                   judge_reason="each skip_globs entry is a decision to re-read")
    # A SEPARATE ROW, AND IT FAILS (v4). Folding these into the TREE row would make an
    # unscanned file look like a clean one, which is the defect. Folding them into "paths
    # skipped by declaration" would be worse still: a skip is a DECISION somebody recorded,
    # and an unreadable file is a decision nobody took. The path is masked like every other
    # finding, and the exception CLASS is named because it is what tells a permission
    # denial from a file that is not there.
    #
    # THE DENOMINATOR IS WHAT THE ARM TRIED TO OPEN, NEVER THE NUMBER OF FAILURES. Recording
    # len(unreadable) reads naturally and is wrong in the one direction that matters: the
    # shared record() makes a zero denominator VOID, so the HEALTHY case - nothing
    # unreadable - would report "examined nothing" and the row would be void on every clean
    # run in the house. A row that is always void is not a control, which is the argument
    # that retired two caps here.
    rep.record(UNREAD, opened + len(unreadable),
               [f"{mask_phrases(rel, phrases)}: tracked but could not be read ({kind}) "
                f"- it was NOT scanned" for rel, kind in unreadable])


def arm_added(rep, root, phrases, sources, globs, baseline, controls):
    """Only what this change ADDS, over EVERY file type - which is the gap it fills.

    A line number is the run's FIRST, and a run is matched whitespace-collapsed: a phrase
    broken across a hard wrap is still one phrase, while two added lines a thousand apart
    are not one and must never be joined into a phrase nobody wrote.
    """
    if not baseline:
        rep.record(ADDED, 0, [], na_reason=(
            "no --baseline REV given. The arm did NOT run, which is a different fact from "
            "having run and found nothing. A baseline belongs to an INVOCATION: pinned in "
            "config it would make every routine run VOID as soon as the tree was clean"))
        return
    sha, err = resolve_revision(root, baseline)
    if err or not sha:
        rep.record(ADDED, 0, [], void_reason=err or "the baseline did not resolve")
        return
    guard = baseline_guard(root, sha)
    if guard:
        rep.record(ADDED, 0, [], void_reason=guard)
        return
    r = git(root, "diff", "--name-only", sha)
    if r.returncode not in (0, 1) or r.stdout is None:
        rep.record(ADDED, 0, [], void_reason=(
            f"could not list the paths changed against {sha[:12]} - nothing was compared"))
        return
    problems, texts, examined = [], [], 0
    for rel in [x for x in (r.stdout or "").splitlines() if x.strip()]:
        if skipped_by(rel, globs):
            continue
        runs = added_line_runs(root, sha, rel)
        if runs is None:
            problems.append(f"{mask_phrases(rel, phrases)}: VOID - the added lines could "
                            f"not be read")
            continue
        for run in runs:
            if not run:
                continue
            examined += len(run)
            joined = " ".join(t for _n, t in run)
            texts.append(joined)
            for _ln, idx in scan_text(joined, phrases):
                problems.append(_problem(f"{rel}:{run[0][0]}", idx, phrases, sources))
    control = next((c for c in (first_token(t) for t in texts) if c), None)
    fired = control is not None and any(
        idx == 0 for t in texts for _ln, idx in scan_text(t, phrases, control))
    controls[ADDED] = fired
    rep.record(ADDED, examined, problems, void_reason=_why_void(
        examined, control, fired,
        f"nothing was added against baseline {sha[:12]} - this arm examined no line"))


def arm_messages(rep, root, cfg, phrases, sources, controls):
    """Every commit message reachable from any ref - read by NOTHING before v2."""
    if not cfg.get("scan_commit_messages", True):
        rep.record(MSGS, 0, [], na_reason=(
            "scan_commit_messages is false - a DECLARED decision, not a default. The arm "
            "did NOT run, which is a different fact from having run and found nothing"))
        return
    msgs = commit_messages(root)
    if msgs is None:
        rep.record(MSGS, 0, [], void_reason=(
            "git log failed - not one commit message could be enumerated"))
        return
    control = next((c for c in (first_token(b) for _s, b in msgs) if c), None)
    found, fired = set(), False
    for sha, body in msgs:
        got = {idx for _ln, idx in scan_text(body, phrases, control)}
        if 0 in got:
            fired = True
            got.discard(0)
        for idx in got:
            found.add((sha, idx))
    problems = [_problem(f"commit {sha[:12]}", idx, phrases, sources)
                for sha, idx in sorted(found)]
    controls[MSGS] = fired
    rep.record(MSGS, len(msgs), problems, void_reason=_why_void(
        len(msgs), control, fired,
        "no commit message could be read - this arm examined nothing"))


def arm_history_paths(rep, root, cfg, phrases, sources, controls):
    """Every revision of the paths DECLARED for it. Cheap, targeted, and PATH-SCOPED."""
    paths = list(cfg.get("history_paths") or [])
    if not paths:
        rep.record(HIST, 0, [], na_reason=(
            "no history_paths declared. The arm did NOT run, which is a different fact "
            "from having run and found nothing. Note it is PATH-SCOPED even when declared "
            "- the all-blobs arm is the one that answers what a clone can read"))
        return
    results, control, fired = scan_history(root, paths, phrases)
    problems, examined = [], 0
    for rel, n_revs, read_ok, per, why in results:
        # MASKED HERE TOO, and these two lines are why the fix could not live only in
        # _problem: this arm builds its own strings because it reports a RATIO rather than a
        # position, so a guard placed at the shared formatter alone would have left the two
        # hand-built cases leaking - caller N+1, inside the very change that fixed caller N.
        shown = mask_phrases(rel, phrases)
        if why:
            problems.append(f"{shown}: VOID - {why}")
            continue
        examined += read_ok
        for idx, count in sorted(per.items()):
            problems.append(f"{shown}: forbidden phrase #{idx} of {len(phrases)} in {count} "
                            f"of {read_ok} revisions ({n_revs} touch this path)")
    controls[HIST] = fired
    rep.record(HIST, examined, problems, void_reason=_why_void(
        examined, control, fired,
        "no revision of any declared path could be read"))


def arm_all_blobs(rep, root, cfg, phrases, sources, globs, controls):
    """Every blob reachable from any ref, under the path it had IN THAT REVISION."""
    if not cfg.get("scan_all_history_blobs", True):
        rep.record(BLOBS, 0, [], na_reason=(
            "scan_all_history_blobs is false - a DECLARED decision, not a default. The arm "
            "did NOT run, so nothing here says what a clone of this repository can read"))
        return
    # `or` WOULD DISCARD A LEGITIMATE 0 HERE, silently substituting the default - and a
    # ceiling of 0 means "examine nothing", which is the OPPOSITE of 20000. Found by the
    # selftest arm that asserts VOID over the ceiling: it read FAIL, because the arm had
    # quietly run the full walk. An `or` default is only safe where every falsy value is
    # genuinely absent, which is never true of a number.
    ceiling = cfg.get("max_history_blobs")
    by_sha, contents, why = history_blobs(root, 20000 if ceiling is None else int(ceiling))
    if why:
        rep.record(BLOBS, 0, [], void_reason=why)
        return
    control, fired, found, examined, skipped = None, False, set(), 0, 0
    for sha, text in contents:
        kept = [p for p in sorted(by_sha.get(sha, set())) if not skipped_by(p, globs)]
        if not kept:
            skipped += 1
            continue
        examined += 1
        if control is None:
            control = first_token(text)
        got = {idx for _ln, idx in scan_text(text, phrases, control)}
        if 0 in got:
            fired = True
            got.discard(0)
        for idx in got:
            for p in kept:
                found.add((p, sha, idx))
    problems = [_problem(f"{p}@{sha[:12]}", idx, phrases, sources)
                for p, sha, idx in sorted(found)]
    controls[BLOBS] = fired
    rep.record(BLOBS, examined, problems, void_reason=_why_void(
        examined, control, fired, "no blob could be read - this arm examined nothing"))
    if skipped:
        rep.record("history blobs skipped by declaration", skipped, [],
                   judge_reason="each skip_globs entry is a decision to re-read")


def arm_report_leak(rep, phrases, controls):
    """THE REPORT, SCANNED FOR THE LIST IT IS REPORTING ON. Read this arm before the others.

    IT IS AN ASSERTION RATHER THAN A PATCH, AND THAT IS THE WHOLE POINT. v2 leaked a client
    identifier through a file PATH while obeying its own positions-only rule to the letter,
    because the rule was about a phrase's TEXT and a finding is located by a path. Masking
    every build site fixes the arms that exist today; this row fixes the arm somebody adds
    next year. A guard inside the shared thing costs one row and covers the callers that do
    not exist yet, where fixing each site covers only the ones found today.

    IT SCANS THE RENDERED ROWS, WITH TRUNCATION TURNED OFF. render() shows twelve problems
    per row by default, so a leak sitting at position thirteen would be masked by the
    reporting layer rather than by the masker - a clean-looking pass produced by not looking.

    ITS OWN CONTROL IS PLANTED FROM THE REPORT'S OWN TEXT, like every other arm's: a needle
    taken from what this arm actually reads, matched through the same scan_text the phrases
    go through. A control borrowed from the tree would prove the tree arm works and say
    nothing about whether one rendered line was ever examined.

    AND IT RUNS LAST, over rows recorded BEFORE it. Its own row carries no path, so it has
    nothing to say about itself - and a guard that scanned its own output could be satisfied
    by a report that had stopped saying anything.
    """
    rows = list(rep.rows)
    if not rows or not phrases:
        controls[LEAK] = None
        rep.record(LEAK, 0, [], void_reason=(
            "there was no row to scan, or no list to scan it for - so nothing here says "
            "whether this report would have leaked one"))
        return
    problems, examined = [], 0
    for _doc, name, _status, _count, probs in rows:
        text = "\n".join([str(name)] + [str(p) for p in probs])
        examined += 1
        for idx in sorted({i for _ln, i in scan_text(text, phrases)}):
            problems.append(f"row {name!r} carries forbidden phrase #{idx} of "
                            f"{len(phrases)} - the report is leaking its own list")
    rendered = rep.render(max_problems=10 ** 6)
    control = first_token(rendered)
    fired = control is not None and any(
        idx == 0 for _ln, idx in scan_text(rendered, phrases, control))
    controls[LEAK] = fired
    rep.record(LEAK, examined, problems, void_reason=_why_void(
        examined, control, fired,
        "the report rendered no line - this arm examined nothing"))


def arm_control_summary(rep, controls):
    """WHICH arms were validated - because five scans cannot share one control.

    Kept as a row of its own even though every arm already goes VOID by itself, for the
    reason v1 gave and v2 multiplies by five: a reader scanning the report for one word
    must be able to see that the run means something at all. A zero beside a control that
    never fired is not a measurement, and now there are five zeros to mistake.
    """
    ran = {k: v for k, v in controls.items() if v is not None}
    if not ran:
        rep.record(CTRL, 0, [], void_reason=(
            "not one arm ran, so no control could be planted in any population"))
        return
    dead = sorted(k for k, v in ran.items() if not v)
    rep.record(CTRL, len(ran),
               [f"{k}: the planted needle was NOT found" for k in dead],
               void_reason=None if not dead else
               f"{len(dead)} of {len(ran)} arms did not validate - those arms are VOID")


def build_report(root: Path, cfg, phrases, sources, list_void, baseline=None):
    rep = Report()
    blocked = list_void or (None if phrases else (
        "no forbidden list is declared - set VERIFY_FORBIDDEN_LIST or "
        "md.forbidden_phrases_file. Nothing was compared"))
    if blocked:
        # EVERY row, not only the ones v1 had. A missing row and a VOID row are different
        # facts, and a caller keying on a row name gets a KeyError from the first.
        for row in (TREE, UNREAD, ADDED, MSGS, HIST, BLOBS, LEAK, CTRL):
            rep.record(row, 0, [], void_reason=blocked)
        return rep

    globs = list(cfg.get("skip_globs") or [])
    controls: dict = {}
    arm_tree(rep, root, phrases, sources, tracked_files(root), globs, controls)
    arm_added(rep, root, phrases, sources, globs, baseline, controls)
    arm_messages(rep, root, cfg, phrases, sources, controls)
    arm_history_paths(rep, root, cfg, phrases, sources, controls)
    arm_all_blobs(rep, root, cfg, phrases, sources, globs, controls)
    # LAST BUT ONE, and the order is load-bearing: it scans what the five arms wrote, and
    # the control summary must come after it so a leak counts as an arm that did not validate.
    arm_report_leak(rep, phrases, controls)
    arm_control_summary(rep, controls)
    return rep


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Is a forbidden phrase in this project's "
                                            "tracked files, or in its git history?")
    p.add_argument("--project", default=".", help="project root (a git repository)")
    p.add_argument("--history", nargs="*", default=None,
                   help="paths whose every revision to scan, overriding the config")
    p.add_argument("--baseline", default=None, metavar="REV",
                   help="scan only the lines ADDED since REV, over every file type. A FLAG "
                        "and not a config key: a permanently pinned baseline makes the arm "
                        "VOID on every run where the tree is clean")
    p.add_argument("--selftest", action="store_true")
    p.add_argument("--write-config", action="store_true")
    args, _ = p.parse_known_args(argv)
    if args.selftest:
        return selftest()
    quiet = wants_report_json(sys.argv if argv is None else argv)

    root = Path(args.project).resolve()
    if args.write_config:
        from house_common import write_section
        write_section(root, "confidential", DEFAULT_CONFIG, CONFIG_COMMENTS)
        return RC_OK
    cfg = load_section(root, "confidential", DEFAULT_CONFIG)
    if args.history is not None:
        cfg = dict(cfg, history_paths=list(args.history))
    md_cfg = load_section(root, "md", MD_LIST_KEYS)
    phrases, sources, list_void = resolve_list(
        root, md_cfg, "forbidden_phrases", "forbidden_phrases_file",
        FORBIDDEN_LIST_ENV, "forbidden")

    rep = build_report(root, cfg, phrases, sources, list_void, baseline=args.baseline)
    if not quiet:
        print(rep.render())
        # THE FINGERPRINT IS WHAT MAKES A CLEAN VERDICT COMPARABLE. Until v3 a report said
        # how MANY needles it checked and nothing about WHICH - so a scan measured a list
        # against a tree and only one of the two was ever recorded. Measured: one added
        # needle turned a project that had been closed, verified and force-pushed clean the
        # day before RED again on two arms, with nothing in it changed. A hash and never a
        # copy: a copy of the list in a report is the leak this checker exists to prevent.
        print(f"\n{len(phrases)} phrase(s) checked, never printed "
              f"- list fingerprint {list_fingerprint(phrases)}")
        print("OVERALL: " + rep.verdict())
    return finish(rep, "verify_confidential.py", rep.exit_code, quiet)


# -------------------------------------------------------------------------- selftest

def _repo(t: Path, files: dict, *, commit=True) -> Path:
    """A real git repository, because both arms read git rather than the filesystem."""
    d = t / f"proj{len(list(t.iterdir()))}"
    d.mkdir(parents=True)
    git(d, "init", "-q")
    git(d, "config", "user.email", "t@example.invalid")
    git(d, "config", "user.name", "t")
    for rel, body in files.items():
        f = d / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_bytes(body.encode("utf-8"))
    if commit:
        git(d, "add", "-A")
        git(d, "commit", "-qm", "one")
    return d


def _list(t: Path, *phrases: str) -> Path:
    f = t / f"needles{len(list(t.iterdir()))}.txt"
    f.write_bytes(("# a comment line, NOT a needle\n" + "\n".join(phrases) + "\n")
                  .encode("utf-8"))
    return f


def _built(root: Path, listing: Path | None, history=None, baseline=None, over=None):
    """Return the Report, built exactly as main() builds it. ONE builder for every probe.

    EXTRACTED IN v3 WHEN A THIRD PROBE NEEDED IT. Two callers already assembled the config,
    the md section, the resolver and build_report by hand - and a third copy is where one of
    them comes to resolve the list slightly differently while every suite keeps passing.
    """
    import os
    old = os.environ.get(FORBIDDEN_LIST_ENV)
    if listing is None:
        os.environ.pop(FORBIDDEN_LIST_ENV, None)
    else:
        os.environ[FORBIDDEN_LIST_ENV] = str(listing)
    try:
        cfg = dict(DEFAULT_CONFIG, history_paths=list(history or []), **(over or {}))
        md_cfg = load_section(root, "md", MD_LIST_KEYS)
        phrases, sources, void = resolve_list(root, md_cfg, "forbidden_phrases",
                                              "forbidden_phrases_file",
                                              FORBIDDEN_LIST_ENV, "forbidden")
        return build_report(root, cfg, phrases, sources, void, baseline=baseline)
    finally:
        if old is None:
            os.environ.pop(FORBIDDEN_LIST_ENV, None)
        else:
            os.environ[FORBIDDEN_LIST_ENV] = old


def _run(root: Path, listing: Path | None, history=None, baseline=None, over=None):
    """Return (exit code, the statuses by row name)."""
    rep = _built(root, listing, history, baseline, over)
    return rep.exit_code, {name: status for _d, name, status, _c, _p in rep.rows}


def _render(root: Path, listing: Path | None, history=None) -> str:
    """The report AS TEXT, with truncation turned off - for the assertions about output.

    max_problems is raised deliberately: render() shows twelve per row by default, so a leak
    at position thirteen would be hidden by the reporting layer and the assertion would pass
    for having looked at less than the report contains.
    """
    return _built(root, listing, history).render(max_problems=10 ** 6)


NEEDLE = "Sekrit-Co"


def _probe(row):
    """Build a probe returning ONE row's status, so a case names what it is proving.

    A probe over the whole exit code would let a case pass for the wrong row's reason -
    the history arm going VOID while the tree arm was under test, say.
    """
    def go(built):
        _rc, statuses = _run(*built)
        return statuses.get(row, f"NO SUCH ROW: {row}")
    return go


def selftest() -> int:
    """Every arm proved BOTH ways, because each alone passes a different broken scanner.

    A dirty-only suite is passed perfectly by a scanner that flags everything; a clean-only
    suite is passed by one that flags nothing - and the second is the direction that ships,
    because a clean run is the answer everybody wants.
    """
    print("SELFTEST - both arms, each proved both ways\n")
    t = Path(tempfile.mkdtemp(prefix="verify_conf_selftest_"))
    ok = True
    try:
        cases = [
            # THE TREE ARM, and the needle sits in a .py file on purpose: a document-only
            # scanner reports N/A over exactly this commit, which is the gap this fills.
            Case("a needle in a NON-document file",
                 _probe(TREE),
                 lambda d: (_repo(d, {"a.py": f"x = '{NEEDLE}'\n"}), _list(d, NEEDLE), []),
                 lambda d: (_repo(d, {"a.py": "x = 1\n"}), _list(d, NEEDLE), [])),
            # THE STAGING TRAP, proved as a PAIR - the same needle, tracked then untracked.
            # Stated as a property rather than a bug: an untracked file is not published.
            Case("tracked is found, UNTRACKED is not",
                 _probe(TREE),
                 lambda d: (_repo(d, {"a.py": f"x = '{NEEDLE}'\n"}), _list(d, NEEDLE), []),
                 lambda d: (_untracked(d), _list(d, NEEDLE), [])),
            # A '#' LINE IS A COMMENT, NOT A NEEDLE. Read as a needle it matches every file
            # in the tree, which is how a list of six once reported hundreds of hits.
            Case("the needle fires; its '#' comment does not",
                 _probe(TREE),
                 lambda d: (_repo(d, {"a.py": f"# {NEEDLE}\n"}), _list(d, NEEDLE), []),
                 lambda d: (_repo(d, {"a.py": "# a comment line, NOT a needle\n"}),
                            _list(d, NEEDLE), [])),
            # A BACKSLASH IS A CHARACTER, NOT A REGEX ESCAPE. The good arm is the regex
            # READING of the same needle - whitespace where a separator was meant - which
            # must NOT match. That is the pair that catches a scanner using a regex engine.
            Case("a backslash matches literally, not as \\s",
                 _probe(TREE),
                 lambda d: (_repo(d, {"a.py": "p = 'C:\\Users\\someone'\n"}),
                            _list(d, "\\Users\\someone"), []),
                 lambda d: (_repo(d, {"a.py": "p = 'C: Users someone'\n"}),
                            _list(d, "\\Users\\someone"), [])),
            # NO LIST IS VOID, NEVER PASS - the trap an external list opens.
            Case("no declared list is VOID",
                 _probe(TREE),
                 lambda d: (_repo(d, {"a.py": "x = 1\n"}), None, []),
                 lambda d: (_repo(d, {"a.py": "x = 1\n"}), _list(d, NEEDLE), []),
                 want=VOID),
            Case("a declared list NOT on disk is VOID",
                 _probe(TREE),
                 lambda d: (_repo(d, {"a.py": "x = 1\n"}), d / "nope.txt", []),
                 lambda d: (_repo(d, {"a.py": "x = 1\n"}), _list(d, NEEDLE), []),
                 want=VOID),
            Case("nothing tracked is VOID, not clean",
                 _probe(TREE),
                 lambda d: (_no_repo(d), _list(d, NEEDLE), []),
                 lambda d: (_repo(d, {"a.py": "x = 1\n"}), _list(d, NEEDLE), []),
                 want=VOID),
            # THE CONTROL ROW. Its bad arm is a tree with nothing to plant a control IN -
            # every tracked file empty - because a control that cannot be planted must
            # make the run VOID rather than leave a clean-looking zero standing.
            Case("a tree with no plantable control is VOID",
                 _probe(CTRL),
                 lambda d: (_repo(d, {"empty.txt": ""}), _list(d, NEEDLE), []),
                 lambda d: (_repo(d, {"a.py": "x = 1\n"}), _list(d, NEEDLE), []),
                 want=VOID),
            # THE HISTORY ARM. The bad arm's HEAD is CLEAN and only an old revision
            # carries the needle - which is the whole reason this arm exists, and the one
            # case the tree arm cannot see.
            Case("a needle only in an OLD revision",
                 _probe(HIST),
                 lambda d: (_old_revision(d), _list(d, NEEDLE), ["a.md"]),
                 lambda d: (_repo(d, {"a.md": "clean\n"}), _list(d, NEEDLE), ["a.md"])),
            Case("an undeclared history arm is N/A",
                 _probe(HIST),
                 lambda d: (_repo(d, {"a.md": "clean\n"}), _list(d, NEEDLE), []),
                 lambda d: (_repo(d, {"a.md": "clean\n"}), _list(d, NEEDLE), ["a.md"]),
                 want=NA),
            Case("a history path that does not exist is VOID",
                 _probe(HIST),
                 lambda d: (_repo(d, {"a.md": "clean\n"}), _list(d, NEEDLE), ["gone.md"]),
                 lambda d: (_repo(d, {"a.md": "clean\n"}), _list(d, NEEDLE), ["a.md"]),
                 want=VOID),
            # ---------------------------------------------- v2, arm A: ADDED LINES
            # THE DEFECT, REPRODUCED: the needle is added to a .py file, which the DOCUMENT
            # checker's own --baseline arm reports N/A over - 0 examined, structurally.
            Case("a needle ADDED to a .py file",
                 _probe(ADDED),
                 lambda d: (_added(d, f"y = '{NEEDLE}'\n"), _list(d, NEEDLE), [], "HEAD"),
                 lambda d: (_added(d, "y = 2\n"), _list(d, NEEDLE), [], "HEAD")),
            # THE DISCRIMINATOR that makes it an ADDED-lines arm rather than a second tree
            # scan: a phrase already at the baseline and untouched is NOT a finding here.
            # Without this pair the arm could be a whole-file scan and every case still pass.
            Case("a PRE-EXISTING needle is not an added line",
                 _probe(ADDED),
                 lambda d: (_added(d, f"y = '{NEEDLE}'\n"), _list(d, NEEDLE), [], "HEAD"),
                 lambda d: (_added_over(d, f"x = '{NEEDLE}'\n", "y = 2\n"),
                            _list(d, NEEDLE), [], "HEAD")),
            Case("no --baseline is N/A, never a pass",
                 _probe(ADDED),
                 lambda d: (_repo(d, {"a.py": "x = 1\n"}), _list(d, NEEDLE), []),
                 lambda d: (_added(d, "y = 2\n"), _list(d, NEEDLE), [], "HEAD"),
                 want=NA),
            # AN EMPTY DIFF IS VOID, NOT CLEAN - "no added lines, therefore nothing was
            # added" is the sentence a baseline pinned to the current state produces.
            Case("a tree identical to the baseline is VOID",
                 _probe(ADDED),
                 lambda d: (_repo(d, {"a.py": "x = 1\n"}), _list(d, NEEDLE), [], "HEAD"),
                 lambda d: (_added(d, "y = 2\n"), _list(d, NEEDLE), [], "HEAD"),
                 want=VOID),
            # ---------------------------------------------- v2, arm B: COMMIT MESSAGES
            # THE TREE IS CLEAN IN BOTH ARMS. That is the whole case: nothing in this house
            # read a message before v2, and git log publishes one as widely as a file.
            Case("a needle in a COMMIT MESSAGE, clean tree",
                 _probe(MSGS),
                 lambda d: (_msg(d, f"about {NEEDLE} today"), _list(d, NEEDLE), []),
                 lambda d: (_msg(d, "about nothing today"), _list(d, NEEDLE), [])),
            # THE PAIR IS OFF-WITH-A-NEEDLE against ON-AND-CLEAN. Both arms must differ in
            # STATUS, so the good arm has to be one the arm actually runs and passes -
            # pairing "off" against "off" would prove only that the switch is sticky.
            Case("a declared-off message arm is N/A",
                 _probe(MSGS),
                 lambda d: (_msg(d, f"about {NEEDLE} today"), _list(d, NEEDLE), [], None,
                            {"scan_commit_messages": False}),
                 lambda d: (_msg(d, "about nothing today"), _list(d, NEEDLE), []),
                 want=NA),
            # ---------------------------------------------- v2, arm C: ALL HISTORY BLOBS
            # THE PATH IS GONE AT HEAD, so neither the tree arm nor any history_paths entry
            # anybody would think to declare can reach it. This is the arm's whole reason.
            Case("a needle in a DELETED path's old blob",
                 _probe(BLOBS),
                 lambda d: (_deleted(d, f"{NEEDLE}\n"), _list(d, NEEDLE), []),
                 lambda d: (_deleted(d, "harmless\n"), _list(d, NEEDLE), [])),
            Case("a declared-off all-blobs arm is N/A",
                 _probe(BLOBS),
                 lambda d: (_deleted(d, f"{NEEDLE}\n"), _list(d, NEEDLE), [], None,
                            {"scan_all_history_blobs": False}),
                 lambda d: (_deleted(d, "harmless\n"), _list(d, NEEDLE), []),
                 want=NA),
            # OVER THE CEILING IS VOID, and the pair matters: a ceiling that silently
            # PASSED would turn every large repository into a clean-looking zero.
            Case("over max_history_blobs is VOID, not clean",
                 _probe(BLOBS),
                 lambda d: (_deleted(d, f"{NEEDLE}\n"), _list(d, NEEDLE), [], None,
                            {"max_history_blobs": 0}),
                 lambda d: (_deleted(d, "harmless\n"), _list(d, NEEDLE), []),
                 want=VOID),
            # ------------------------------- v4: THE DENOMINATOR CAN SILENTLY SHRINK
            # A NON-ASCII FILENAME, which git quotes on output - so `ls-files` hands
            # back a string that is not a path and the file left the scan without a
            # word. The pair carries the SAME NAME either way, so what is proved is
            # the reading of the path and not the content.
            Case("a needle in a NON-ASCII filename",
                 _probe(TREE),
                 lambda d: (_nonascii(d, f"x = '{NEEDLE}'\n"), _list(d, NEEDLE), []),
                 lambda d: (_nonascii(d, "x = 1\n"), _list(d, NEEDLE), [])),
            # AND THE GUARD, WHICH IS A DIFFERENT CLAIM FROM THE CAUSE. A file tracked
            # at HEAD and gone from disk is unopenable for a reason no config change
            # reaches, so it proves the REPORTING half rather than the quoting fix.
            Case("a tracked file that cannot be read FAILS",
                 _probe(UNREAD),
                 lambda d: (_tracked_but_missing(d), _list(d, NEEDLE), []),
                 lambda d: (_repo(d, {"a.py": "x = 1\n", "b.py": "y = 2\n"}),
                            _list(d, NEEDLE), [])),
        ]
        ok, paired, unpaired = run_cases(cases, t, width=42)
        report_pairing(paired, unpaired)
        ok &= _selftest_cross_arm(t)
        ok &= _selftest_positions_only(t)
        ok &= _selftest_path_is_the_needle(t)
        ok &= _selftest_leak_guard()
        ok &= _selftest_denominator(t)
    finally:
        import shutil
        shutil.rmtree(t, ignore_errors=True)
    print("\nSELFTEST: " + ("PASS" if ok else "FAIL"))
    return RC_OK if ok else RC_FAILED


def _nonascii(d: Path, body: str) -> Path:
    """A repo whose ONLY tracked file has a NON-ASCII NAME. The name IS the fixture.

    git quotes any output path holding a byte above 0x80, so `ls-files` returns
    `"note \\342\\200\\224 one.md"` and a caller that opens it reads nothing. The em dash is
    the character this was measured on; any high byte does it. The needle stays out of the
    FILENAME on purpose - a path that is itself a needle is a different case, and
    _selftest_path_is_the_needle already owns it.
    """
    return _repo(d, {"note — one.md": body})


def _tracked_but_missing(d: Path) -> Path:
    """Two tracked files, one DELETED from disk - unopenable for a reason config cannot fix.

    Deliberately not a permissions fixture: chmod is unreliable on this platform and a test
    that silently does nothing is worse than none. A missing file reaches the same code path
    through the same OSError, and it is reproducible everywhere.
    """
    r = _repo(d, {"a.py": "x = 1\n", "b.py": "y = 2\n"})
    (r / "b.py").unlink()
    return r


def _untracked(d: Path) -> Path:
    """A repo whose needle is in an UNTRACKED file - deliberately not found."""
    r = _repo(d, {"a.py": "x = 1\n"})
    (r / "new.py").write_bytes(f"y = '{NEEDLE}'\n".encode("utf-8"))
    return r


def _old_revision(d: Path) -> Path:
    """A repo whose HEAD is CLEAN and whose first revision is not."""
    r = _repo(d, {"a.md": f"before {NEEDLE} here\n"})
    (r / "a.md").write_bytes(b"after, cleaned\n")
    git(r, "add", "-A")
    git(r, "commit", "-qm", "two")
    return r


def _added(d: Path, line: str) -> Path:
    """A repo with a CLEAN committed a.py and `line` appended but not committed."""
    r = _repo(d, {"a.py": "x = 1\n"})
    with (r / "a.py").open("ab") as fh:
        fh.write(line.encode("utf-8"))
    return r


def _added_over(d: Path, committed: str, line: str) -> Path:
    """The needle is ALREADY at the baseline; the uncommitted line is clean.

    This is the good twin that makes the added-lines arm provable: a whole-file scanner
    passes every other case in this group and fails only this one.
    """
    r = _repo(d, {"a.py": committed})
    with (r / "a.py").open("ab") as fh:
        fh.write(line.encode("utf-8"))
    return r


def _msg(d: Path, subject: str) -> Path:
    """A repo whose TREE is clean and whose second commit MESSAGE is the variable."""
    r = _repo(d, {"a.md": "clean\n"})
    (r / "b.md").write_bytes(b"also clean\n")
    git(r, "add", "-A")
    git(r, "commit", "-qm", subject)
    return r


def _deleted(d: Path, body: str) -> Path:
    """A repo where a file was committed and then REMOVED, so only its blob survives.

    Neither the tree arm nor any history_paths entry can reach it: the path does not exist
    at HEAD, so nobody would think to declare it and `git show HEAD:gone.md` fails.
    """
    r = _repo(d, {"keep.md": "clean\n", "gone.md": body})
    git(r, "rm", "-q", "gone.md")
    git(r, "commit", "-qm", "two")
    return r


def _no_repo(d: Path) -> Path:
    p = d / "bare"
    p.mkdir(parents=True, exist_ok=True)
    (p / "a.py").write_bytes(f"x = '{NEEDLE}'\n".encode("utf-8"))
    return p


def _selftest_cross_arm(t: Path) -> bool:
    """THE v2 CLAIM ITSELF, off ONE repository: a clean tree says nothing about the rest.

    NO CASE ROW CAN STATE THIS, because a row reports one arm at a time. What has to be
    shown is that on the SAME fixture the two cheap arms PASS while the two new history
    arms FAIL - so a reader who stops at the first green row has the wrong answer, which is
    precisely the reading that let a repository sit with 5 carrying blobs behind a green
    path-scoped row. Cross-arm acceptance off one fixture is this house's standard shape
    for a claim about the RELATION between arms rather than about any one of them.
    """
    print("\n  ONE fixture: the tree is CLEAN and two other arms are not\n")
    r = _repo(t, {"keep.md": "clean\n", "gone.md": f"{NEEDLE}\n"})
    git(r, "rm", "-q", "gone.md")
    git(r, "commit", "-qm", f"removing the {NEEDLE} file")
    _rc, st = _run(r, _list(t, NEEDLE), ["keep.md"])
    ok = True
    for row, expect in ((TREE, PASS), (HIST, PASS), (MSGS, FAIL), (BLOBS, FAIL)):
        got = st.get(row, "NO SUCH ROW")
        good = got == expect
        ok &= good
        print(f"  {'OK  ' if good else 'MISS'} {row:<46} {got} (want {expect})")
    return ok


def _selftest_positions_only(t: Path) -> bool:
    """THE CONFIDENTIALITY PROPERTY ITSELF: no report may contain the phrase.

    This is the one check that cannot be inferred from a status. A scanner that finds
    everything and then prints what it found has leaked the list into every terminal and CI
    log that ran it - so the assertion is on the OUTPUT, not on the verdict.
    """
    print("\n  the report must never contain the phrase itself\n")
    import os
    secret = "Sekrit-Co-Holdings"
    r = _repo(t, {"a.py": f"x = '{secret}'\n", "b.md": f"# {secret}\n"})
    # A SECOND COMMIT WHOSE MESSAGE ALSO CARRIES IT, so the leak test covers the v2 rows
    # rather than only the two v1 had. Each new arm formats its own problem line, and a
    # leak test that never sees an arm's output cannot say that arm does not leak.
    (r / "c.md").write_bytes(b"more\n")
    git(r, "add", "-A")
    git(r, "commit", "-qm", f"mentioning {secret} in a subject")
    listing = _list(t, secret)
    # THROUGH THE SHARED BUILDER SINCE v3. This block used to assemble the config, the md
    # section and the resolver by hand, which made it a second implementation of _run's
    # setup - and the two would have drifted at the first change to how a list resolves.
    rep = _built(r, listing, ["b.md"])
    text = rep.render(max_problems=10 ** 6)
    found = rep.exit_code == RC_FAILED
    leaked = secret.lower() in text.lower()
    good = found and not leaked
    print(f"  {'OK  ' if good else 'MISS'} {'found it AND did not print it':<46} "
          f"found={found} leaked={leaked} (want True, False)")
    # AND THE OTHER ARM: the assertion must be capable of failing. If the phrase were
    # printed, this is the comparison that would catch it - proved on a string that IS in
    # the report, so a broken check cannot pass by always answering 'not leaked'.
    control_leak = "phrase #1" in text
    print(f"  {'OK  ' if control_leak else 'MISS'} "
          f"{'the leak test can see report text at all':<46} "
          f"control={control_leak} (want True)")
    return good and control_leak


def _selftest_path_is_the_needle(t: Path) -> bool:
    """THE v3 CLAIM, AND IT IS A PAIR BECAUSE NEITHER HALF IS EVIDENCE ALONE.

    A report locates every finding by a PATH, so where a path segment is itself a forbidden
    phrase the report leaks it while obeying the positions-only rule to the letter. Arm 1
    requires the needle to be gone from the output; arm 2 requires a CLEAN path to survive
    byte for byte - and arm 2 is the one that matters, because a masker that redacts
    everything passes arm 1 perfectly and makes every report in the house unreadable.

    THE FIXTURE PUTS THE NEEDLE IN BOTH THE PATH AND THE CONTENT, and that is not
    belt-and-braces - it is the only way the path is printed at all. This arm scans CONTENTS,
    so a file whose name carries a needle and whose body does not produces no finding and no
    line to leak. That is a real gap and it is recorded rather than closed here: a path is a
    population no arm reads, needing its own arm and its own rewrite flag.
    """
    print("\n  a needle in the PATH is masked; a clean path is printed verbatim\n")
    r_bad = _repo(t, {f"config/{NEEDLE}.yaml": f"name: {NEEDLE}\n"})
    r_good = _repo(t, {"a.py": f"x = '{NEEDLE}'\n"})
    ok = True
    for label, root, want_absent, want_present in (
            ("the needle is gone from the report", r_bad, NEEDLE, "<phrase #1>"),
            ("and a clean path survives verbatim", r_good, None, "a.py:1")):
        text = _render(root, _list(t, NEEDLE))
        absent = want_absent is None or want_absent.lower() not in text.lower()
        present = want_present in text
        good = absent and present
        ok &= good
        print(f"  {'OK  ' if good else 'MISS'} {label:<46} "
              f"absent={absent} present={present} (want True, True)")
    return ok


def _selftest_leak_guard() -> bool:
    """THE GUARD ROW, PROVED BOTH WAYS - and it is driven on a report built to be wrong.

    THE MASKING AND THE GUARD ARE TWO CONTROLS AND MUST BE TESTED SEPARATELY. Above, masking
    is shown to work; here the guard is shown to CATCH masking that did not. Testing them
    together would let one cover for the other: a suite that only ever sees masked output
    cannot distinguish a working guard from one that always answers 'nothing leaked', which
    is the direction that ships.

    NO MONKEYPATCHING - a leaking row is simply RECORDED, which is what a future arm that
    forgot to mask would do. That is the caller this row exists for.
    """
    print("\n  the guard catches a row that leaked, and clears one that did not\n")
    secret, ok = "Sekrit-Co-Holdings", True
    leaking = Report()
    leaking.record(TREE, 1, [f"config/{secret}.yaml:1: forbidden phrase #1 of 1 (env)"])
    arm_report_leak(leaking, [secret], {})
    masked = Report()
    masked.record(TREE, 1, [_problem(f"config/{secret}.yaml:1", 1, [secret], ["env"])])
    arm_report_leak(masked, [secret], {})
    # AND THE THIRD STATE, which is neither: with no list there is nothing to scan FOR, and
    # a PASS there would be a guard reporting 'clean' about a question it never asked.
    listless = Report()
    listless.record(TREE, 1, [])
    arm_report_leak(listless, [], {})
    for label, rep, want in (("a leaking row is caught", leaking, FAIL),
                             ("a masked row is clean", masked, PASS),
                             ("and no list at all is VOID", listless, VOID)):
        got = rep.status_of(LEAK) or "NO SUCH ROW"
        good = got == want
        ok &= good
        print(f"  {'OK  ' if good else 'MISS'} {label:<46} {got} (want {want})")
    return ok


def _selftest_denominator(t: Path) -> bool:
    """THE COUNT, WHICH NO CASE ROW CAN ASSERT (v4).

    THIS IS HERE BECAUSE THE DEFECT NEVER MOVED A STATUS. The tree arm read PASS before the
    fix and reads PASS after it; what moved was the DENOMINATOR - 1 examined against 4 - so
    a suite comparing statuses would have shipped it however many cases it held. Every Case
    above compares statuses, which is the right shape for a verdict and blind to a
    population.

    BOTH DIRECTIONS, because each alone is passed by a different broken scanner. Asserting
    only the full count is met by a checker that counts files without reading them; asserting
    only the split is met by one that reports every file unreadable. So: three tracked files,
    one ASCII and two not, must be THREE opened and THREE tried - and a tree holding one
    unopenable file must FAIL while still reporting the file it DID read.
    """
    print("\nTHE DENOMINATOR - a count no status can prove")
    ok = True
    listing = _list(t, NEEDLE)

    clean = _repo(t, {"plain.md": "clean\n",
                      "note — one.md": "clean\n",
                      "note — two.md": "clean\n"})
    rows = {n: (s, c) for _d, n, s, c, _p in _built(clean, listing).rows}
    for row, want_status, want_count, label in (
            (TREE, PASS, 3, "two of three names NON-ASCII, all read"),
            (UNREAD, PASS, 3, "and the read-everything row agrees")):
        got_status, got_count = rows.get(row, ("NO SUCH ROW", -1))
        good = got_status == want_status and got_count == want_count
        ok &= good
        print(f"  {'OK  ' if good else 'MISS'} {label:<46} {got_status}, "
              f"{got_count} examined (want {want_status}, {want_count})")

    missing = _tracked_but_missing(t)
    rows = {n: (s, c) for _d, n, s, c, _p in _built(missing, listing).rows}
    for row, want_status, want_count, label in (
            (UNREAD, FAIL, 2, "one of two unreadable -> FAIL over 2 tried"),
            (TREE, PASS, 1, "and the tree arm honestly says 1 read")):
        got_status, got_count = rows.get(row, ("NO SUCH ROW", -1))
        good = got_status == want_status and got_count == want_count
        ok &= good
        print(f"  {'OK  ' if good else 'MISS'} {label:<46} {got_status}, "
              f"{got_count} examined (want {want_status}, {want_count})")

    # AND THE REPORT MUST NAME IT. A row that fails without saying WHICH file was not read
    # leaves the reader to find it, and the whole finding is that nothing said so.
    text = _built(missing, listing).render(max_problems=10 ** 6)
    good = "b.py" in text and "could not be read" in text
    ok &= good
    print(f"  {'OK  ' if good else 'MISS'} {'the unread file is NAMED in the report':<46} "
          f"{'named' if good else 'NOT NAMED'}")
    return ok


if __name__ == "__main__":
    sys.exit(main())
