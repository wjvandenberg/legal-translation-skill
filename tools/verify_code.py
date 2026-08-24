#!/usr/bin/env python3
"""verify_code.py - the code checker.  CHECKER VERSION 5 (2026-08-24)

If a project's copy says a lower version than this one, it is stale - see the "Checkers"
line for each version in ...\\Coding\\TEMPLATE-CHANGELOG.md and re-copy.

Runs the project's own tests, then checks the things a test suite never notices:
leaked build artefacts, secrets about to be committed, debug leftovers, missing
negative tests, and whether a change claimed to be non-behavioural really is.

    uv run python tools/verify_code.py                # everything the config enables
    uv run python tools/verify_code.py --fast         # skip the test command
    uv run python tools/verify_code.py --selftest     # prove every check can FAIL
    uv run python tools/verify_code.py --write-config

Language-agnostic: it shells out to whatever test command you configure, so it works
for Python, Node/JavaScript, or an Office add-in's build. Standard library only.

TWO RULES BUILT INTO THIS FILE, both learned expensively:

  * EVERY CHECK REPORTS ITS DENOMINATOR. "0 problems" over 0 files scanned is VOID, not
    a pass. A control that could not run has not passed.
  * EVERY PATTERN HAS A TEST VECTOR. Each secret and debug pattern below is exercised by
    --selftest against a string it is meant to catch AND one it must ignore. An untested
    pattern that never matches is indistinguishable from a clean result.

EXIT CODES.  0 = every check passed or was a declared N/A.  1 = at least one check FAILED.
2 = at least one check COULD NOT RUN (VOID) and none failed. "It could not run" and "it
failed" are different facts and a caller that cannot tell them apart cannot react to
either correctly. A FAIL outranks a VOID, because a concrete defect outranks an
unestablished one; both are non-zero, so any gate wired to "non-zero blocks" is unchanged.
"""
from __future__ import annotations

import fnmatch
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

# The shared plumbing. COPY house_common.py ALONGSIDE THIS FILE - without it the checker
# cannot start. check_checkers.py tracks it, so a project that copied one and not the other
# gets a reported finding rather than an import error at the worst possible moment.
from house_common import (                                       # noqa: E402
    FAIL, NA, PASS, VOID, Case, Report,
    load_section, report_pairing, run_cases, selftest_config, write_section,
)

# --------------------------------------------------------------------------- config

DEFAULT_CONFIG = {
    "test_command": "",
    "test_timeout_seconds": 900,
    "source_globs": ["**/*.py", "**/*.js", "**/*.ts", "**/*.mjs", "**/*.jsx", "**/*.tsx"],
    "exclude_dirs": [".git", "node_modules", ".venv", "venv", "__pycache__", "dist",
                     "build", ".next", "temp", ".claude"],
    "ship_paths": [],
    "forbidden_in_ship": ["__pycache__", ".pyc", ".DS_Store", ".env", "node_modules",
                          ".git", "CHANGELOG.md"],
    "must_be_gitignored": ["temp/", ".env", "secrets.json", "*.local"],
    "scan_exclude_globs": ["**/verify_md.py", "**/verify_code.py", "**/verify_deliverable.py"],
    "check_secrets": True,
    "check_debug_leftovers": True,
    "debug_patterns": ["console\\.log\\(", "debugger;", "breakpoint\\(\\)",
                       "pdb\\.set_trace\\(", "print\\(['\\\"]DEBUG"],
    "debug_allow_globs": ["**/test_*.py", "**/*.test.js", "**/tests/**", "**/logger*"],
    "check_negative_tests": True,
    "test_globs": ["**/test_*.py", "**/*_test.py", "**/*.test.js", "**/*.spec.ts"],
    "negative_test_markers": ["raises", "assertRaises", "toThrow", "must_fail",
                              "expect_fail", "should_fail", "_fails", "rejects"],
    "max_file_bytes": 2_000_000,
    "byte_baselines": [],
    "check_commit_authors": True,
    # noreply@github.com is GitHub's OWN committer on a web merge or squash - it appears
    # once per merged PR and is not anybody's address. Omitting it made the check fire on
    # 34 legitimate commits on its first real run, and a check that cries wolf gets
    # switched off rather than read.
    "author_allow": ["*@users.noreply.github.com", "noreply@github.com"],
    "author_allow_before": "",
}

CONFIG_COMMENT = {
    "test_command": "The project's test command, e.g. 'uv run python -m pytest -q' or 'npm test'. Empty = VOID.",
    "source_globs": "What counts as source for the scans below.",
    "scan_exclude_globs": "Files the secret/debug scans skip. The checkers themselves are listed BY NAME, not by wildcard, so your own file is never skipped silently. Excluded files are counted in the output.",
    "ship_paths": "Directories that get packaged and sent to a user. Empty = do not check.",
    "forbidden_in_ship": "Names/extensions that must never appear under ship_paths.",
    "must_be_gitignored": "Paths that must be matched by .gitignore. Prevents accidental commits.",
    "debug_allow_globs": "Files where debug statements are legitimate (tests, loggers).",
    "negative_test_markers": "Substrings proving a test asserts a FAILURE, not just a success.",
    "byte_baselines": "[{'command': '...', 'expect_sha256': '...'}] - proves a change is non-behavioural.",
    "author_allow": "Globs for acceptable commit author AND committer emails. An author address is metadata on EVERY commit, so no content scan can see it and going public exposes it once per commit. Default allows only a GitHub noreply address; widen it deliberately, never by accident.",
    "author_allow_before": "A commit-ish. Everything reachable from it is GRANDFATHERED - for a history that cannot be rewritten. The count is reported in the check's name, so an accepted exposure stays visible instead of becoming invisible. Set it to the commit where the identity was fixed, so every NEW commit is still checked. A value that does not resolve is VOID, never clean.",
}

# Each pattern is paired with a must-match and a must-not-match vector in SECRET_VECTORS.
SECRET_PATTERNS = [
    (r"(?i)\b(?:api[_-]?key|apikey)\s*[:=]\s*['\"][A-Za-z0-9_\-]{16,}['\"]", "hard-coded API key"),
    (r"(?i)\b(?:secret|password|passwd|pwd)\s*[:=]\s*['\"][^'\"]{8,}['\"]", "hard-coded password/secret"),
    (r"-----BEGIN (?:RSA |EC |OPENSSH |PGP )?PRIVATE KEY-----", "private key block"),
    (r"\bsk-[A-Za-z0-9]{20,}\b", "OpenAI-style secret key"),
    (r"\bsk-ant-[A-Za-z0-9\-_]{20,}\b", "Anthropic-style secret key"),
    (r"\bgh[pousr]_[A-Za-z0-9]{30,}\b", "GitHub token"),
    (r"(?i)\baws_secret_access_key\s*[:=]\s*\S{20,}", "AWS secret access key"),
    # The separator may be ':' '=' or plain whitespace, and the value may itself be
    # prefixed 'Bearer '. An earlier version omitted that prefix and silently matched
    # nothing, because the space in 'Bearer ' is not in the value character class.
    (r"(?i)\b(?:bearer|authorization)(?:\s*[:=]\s*|\s+)['\"]?(?:bearer\s+)?[A-Za-z0-9._\-]{24,}",
     "bearer token"),
    (r"(?i)://[^/\s:@]+:[^/\s:@]{6,}@", "credentials embedded in a URL"),
]

# (pattern_index, string_that_MUST_match, string_that_MUST_NOT_match)
SECRET_VECTORS = [
    (0, 'api_key = "abcd1234efgh5678ijkl"', 'api_key = os.environ["API_KEY"]'),
    (1, 'password = "hunter2hunter2"', 'password = get_password()'),
    (2, '-----BEGIN PRIVATE KEY-----', 'the private key lives outside the repo'),
    (3, 'sk-ABCDEFGHIJKLMNOPQRSTUVWX', 'sk-short'),
    (4, 'sk-ant-ABCDEFGHIJKLMNOPQRSTUV', 'sk-ant-'),
    (5, 'ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789', 'ghp_tooshort'),
    (6, 'aws_secret_access_key = wJalrXUtnFEMIK7MDENGbPxRfiCYEXAMPLEKEY', 'aws_secret_access_key = ""'),
    (7, 'Authorization: "Bearer abcdefghijklmnopqrstuvwxyz012345"', 'Authorization: header'),
    # deliberately a DIFFERENT shape from the vector above - no colon, no quotes, no
    # 'Bearer ' prefix. Hand-picked vectors that share a shape test the shape, not the
    # pattern, which is exactly how the first version of this regex passed while broken.
    (7, 'Bearer eyJhbGciOiJIUzI1NiwidHlwIjoiSldUIn0', 'bearer of the seal'),
    (8, 'postgres://user:supersecret@host/db', 'https://example.com/path'),
]

# ------------------------------------------------------------------------- utilities

def iter_files(root: Path, globs, exclude_dirs):
    seen = set()
    for g in globs:
        for p in root.glob(g):
            if not p.is_file():
                continue
            if any(part in exclude_dirs for part in p.parts):
                continue
            if p in seen:
                continue
            seen.add(p)
            yield p


def read_text(p: Path):
    try:
        return p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def apply_exclusions(files, root: Path, globs):
    """Drop the checkers themselves from a content scan, and SAY HOW MANY were dropped.

    Without this, verify_code.py flags its own pattern definitions and test vectors as
    nine hard-coded secrets - a scanner matching itself. A check that always fails gets
    ignored, and then you have a control nobody believes. But a silent exclusion is
    worse, so the count is reported alongside the result.
    """
    excluded = set()
    for g in globs:
        excluded |= set(root.glob(g))
    kept = [p for p in files if p not in excluded]
    return kept, len(files) - len(kept)


# ---------------------------------------------------------------------------- checks

def check_tests(rep, root, cfg, fast):
    cmd = cfg["test_command"].strip()
    if fast:
        rep.record("test command", 0, [], na_reason="--fast given; tests deliberately skipped")
        return
    if not cmd:
        rep.record("test command", 0, [],
                   na_reason="no test_command configured - DECLARE why, or set one")
        return
    try:
        r = subprocess.run(cmd, shell=True, cwd=root, capture_output=True, text=True,
                           timeout=cfg["test_timeout_seconds"])
    except subprocess.TimeoutExpired:
        rep.record("test command", 1, [f"timed out after {cfg['test_timeout_seconds']}s: {cmd}"])
        return
    rc = r.returncode
    if rc != 0:
        tail = (r.stdout + r.stderr).strip().splitlines()[-6:]
        rep.record("test command", 1, [f"exit {rc}: {cmd}"] + [f"  {t}" for t in tail])
    else:
        rep.record("test command", 1, [])


def check_ship_clean(rep, root, cfg):
    ship = cfg["ship_paths"]
    if not ship:
        rep.record("shipped tree clean", 0, [], na_reason="no ship_paths declared")
        return
    forbidden = cfg["forbidden_in_ship"]
    scanned, problems = 0, []
    for d in ship:
        base = root / d
        if not base.exists():
            problems.append(f"declared ship path does not exist: {d}")
            continue
        for p in base.rglob("*"):
            scanned += 1
            name = p.name
            for bad in forbidden:
                if name == bad or name.endswith(bad) or bad in p.parts:
                    problems.append(f"{p.relative_to(root)} - forbidden in a shipped tree ({bad})")
                    break
    rep.record("shipped tree clean", scanned, problems)


def scan_secrets(text):
    hits = []
    for pat, label in SECRET_PATTERNS:
        if re.search(pat, text):
            hits.append(label)
    return hits


def check_secrets(rep, root, cfg):
    if not cfg["check_secrets"]:
        rep.record("no secrets in source", 0, [], na_reason="disabled in config")
        return
    files = list(iter_files(root, cfg["source_globs"] + ["**/*.json", "**/*.yaml", "**/*.yml",
                                                         "**/*.env*", "**/*.md"],
                            cfg["exclude_dirs"]))
    files, skipped = apply_exclusions(files, root, cfg.get("scan_exclude_globs", []))
    problems = []
    for p in files:
        for label in scan_secrets(read_text(p)):
            problems.append(f"{p.relative_to(root)} - {label}")
    name = "no secrets in source" + (f" ({skipped} excluded)" if skipped else "")
    rep.record(name, len(files), problems)


def check_gitignore(rep, root, cfg):
    wanted = cfg["must_be_gitignored"]
    gi = root / ".gitignore"
    if not wanted:
        rep.record("gitignore covers", 0, [], na_reason="nothing declared")
        return
    if not gi.exists():
        rep.record("gitignore covers", len(wanted), [".gitignore does not exist"])
        return
    body = {ln.strip() for ln in gi.read_text(encoding="utf-8").splitlines()}
    problems = [f"not ignored: {w}" for w in wanted
                if w not in body and w.rstrip("/") not in body]
    rep.record("gitignore covers", len(wanted), problems)


def check_debug(rep, root, cfg):
    if not cfg["check_debug_leftovers"]:
        rep.record("no debug leftovers", 0, [], na_reason="disabled in config")
        return
    allow = set()
    for g in cfg["debug_allow_globs"]:
        allow |= set(root.glob(g))
    files = [p for p in iter_files(root, cfg["source_globs"], cfg["exclude_dirs"]) if p not in allow]
    files, skipped = apply_exclusions(files, root, cfg.get("scan_exclude_globs", []))
    pats = [re.compile(p) for p in cfg["debug_patterns"]]
    problems = []
    for p in files:
        text = read_text(p)
        for i, ln in enumerate(text.splitlines(), 1):
            for pat in pats:
                if pat.search(ln):
                    problems.append(f"{p.relative_to(root)}:{i} - {ln.strip()[:60]}")
                    break
    name = "no debug leftovers" + (f" ({skipped} excluded)" if skipped else "")
    rep.record(name, len(files), problems)


def check_negative_tests(rep, root, cfg):
    if not cfg["check_negative_tests"]:
        rep.record("negative tests exist", 0, [], na_reason="disabled in config")
        return
    files = list(iter_files(root, cfg["test_globs"], cfg["exclude_dirs"]))
    markers = cfg["negative_test_markers"]
    problems = []
    for p in files:
        text = read_text(p)
        if not any(m in text for m in markers):
            problems.append(f"{p.relative_to(root)} - only asserts success; no test proves a failure")
    rep.record("negative tests exist", len(files), problems,
               na_reason=None if files else "no test files matched test_globs - is that right?")


def check_file_sizes(rep, root, cfg):
    limit = cfg["max_file_bytes"]
    if not limit:
        rep.record("no oversized files", 0, [], na_reason="max_file_bytes is 0 (disabled)")
        return
    files = list(iter_files(root, ["**/*"], cfg["exclude_dirs"]))
    problems = [f"{p.relative_to(root)} - {p.stat().st_size:,} bytes" for p in files
                if p.stat().st_size > limit]
    rep.record("no oversized files", len(files), problems)


def check_commit_authors(rep, root, cfg):
    """Every commit's AUTHOR and COMMITTER email against author_allow.

    WHY THIS IS NOT A CONTENT SCAN, and why every content scan missed it. An author
    address is metadata on every commit. A leak scanner reads files; a publication check
    reads files; both report CLEAN over a history in which every commit carries a work
    address. The failure is invisible to the whole existing control set, and going public
    exposes it once per commit rather than once.

    IT REPORTS SHAs AND COUNTS, NEVER THE ADDRESS. The report ends up in terminals and CI
    logs, and echoing the thing you are trying to keep out of public view leaks it by a
    route nothing can clean up afterwards. Whoever needs the value runs git log.

    NOT A PASS WHEN IT CANNOT RUN. No git, or not a repository, is N/A - the question does
    not apply. A git call that FAILS is VOID, never CLEAN: a check that could not read its
    subject has not checked it.
    """
    name = "commit author identity"
    if not cfg.get("check_commit_authors", True):
        rep.record(name, 0, [], na_reason="disabled in config")
        return
    allow = cfg.get("author_allow") or []
    if not allow:
        rep.record(name, 0, [], na_reason="author_allow is empty (disabled)")
        return
    if not (root / ".git").exists():
        rep.record(name, 0, [], na_reason="not a git repository")
        return
    try:
        r = subprocess.run(["git", "log", "--all", "--format=%h%x1f%ae%x1f%ce"],
                           cwd=root, capture_output=True, text=True, timeout=120)
    except (OSError, subprocess.SubprocessError) as exc:
        rep.record(name, 0, [f"git could not be run: {exc.__class__.__name__}"])
        return
    if r.returncode != 0:
        rep.record(name, 0, [f"git log failed with exit {r.returncode}"])
        return

    # THE GRANDFATHER BOUNDARY. Everything reachable from author_allow_before is accepted,
    # so a history that cannot be rewritten is DECLARED ONCE instead of re-reported for
    # ever. That is the whole point: a check that always fails gets switched off, and a
    # switched-off check protects nothing - including the new commits it would have caught.
    #
    # A BOUNDARY THAT DOES NOT RESOLVE IS VOID, NEVER CLEAN. A typo here would otherwise
    # grandfather nothing while looking deliberate, or - far worse in a later version -
    # grandfather everything. It has to fail loudly.
    grandfathered = set()
    boundary = (cfg.get("author_allow_before") or "").strip()
    if boundary:
        b = subprocess.run(["git", "rev-list", boundary],
                           cwd=root, capture_output=True, text=True)
        if b.returncode != 0:
            rep.record(name, 0, [
                f"author_allow_before does not resolve to a commit: {boundary!r}",
                "  the boundary is unusable, so nothing was checked"])
            return
        grandfathered = {s[:len(s)] for s in b.stdout.split()}

    lines = [l for l in r.stdout.splitlines() if l.strip()]
    bad, addresses, skipped = [], set(), 0
    for line in lines:
        parts = line.split("\x1f")
        if len(parts) != 3:
            continue
        sha, author, committer = parts
        # %h is abbreviated; rev-list gives full SHAs. Match on the prefix.
        if any(full.startswith(sha) for full in grandfathered):
            skipped += 1
            continue
        for who, addr in (("author", author), ("committer", committer)):
            if addr and not any(fnmatch.fnmatch(addr, pat) for pat in allow):
                bad.append((sha, who))
                addresses.add(addr)

    # THE GRANDFATHERED COUNT GOES IN THE CHECK'S NAME, so it is visible on a PASS as well
    # as on a FAIL - the same shape as "no secrets in source (3 excluded)" above. A
    # grandfathered commit is an ACCEPTED exposure, not an absent one, and a reader who
    # cannot see the count cannot re-open the decision. Putting it in the problem list
    # instead would fail a repository that is in exactly the state we declared acceptable.
    if skipped:
        name = f"{name} ({skipped} grandfathered)"

    problems = []
    if bad:
        shown = ", ".join(f"{s} ({w})" for s, w in bad[:8])
        more = f" and {len(bad) - 8} more" if len(bad) > 8 else ""
        problems.append(
            f"{len(bad)} commit identit{'y' if len(bad) == 1 else 'ies'} outside author_allow, "
            f"across {len(addresses)} distinct address(es): {shown}{more}")
        problems.append(
            "  addresses are NOT printed - run: git log --all --format='%h %ae %ce'")
        problems.append(
            "  history is what gets published: a rewrite after a repo is public and cloned "
            "does not reliably unserve it")
    rep.record(name, len(lines), problems)


def check_byte_baselines(rep, root, cfg):
    from hashlib import sha256
    baselines = cfg["byte_baselines"]
    if not baselines:
        rep.record("byte baselines match", 0, [],
                   na_reason="none declared - add one for any change claimed non-behavioural")
        return
    problems = []
    for b in baselines:
        r = subprocess.run(b["command"], shell=True, cwd=root, capture_output=True)
        got = sha256(r.stdout).hexdigest()
        if got != b["expect_sha256"]:
            problems.append(f"{b['command']} -> {got[:16]}... expected {b['expect_sha256'][:16]}...")
    rep.record("byte baselines match", len(baselines), problems)


# -------------------------------------------------------------------------- selftest

def tree(sub, files, cfg):
    """Builder: a fresh subdirectory holding the named files, plus the config to read it
    with. THE CONFIG TRAVELS WITH THE TREE, and that is not tidiness.

    The first version bound one config to the probe and used it for both halves of a pair.
    The 'failing test command' case then ran the FAILING command against its own good tree
    and reported a miss - the conforming input was not conforming at all. A one-sided
    suite could never have shown that, because it never runs the good half.
    """
    def build(tmp):
        d = tmp / sub
        shutil.rmtree(d, ignore_errors=True)
        d.mkdir(parents=True)
        for name, body in files.items():
            q = d / name
            q.parent.mkdir(parents=True, exist_ok=True)
            q.write_text(body, encoding="utf-8")
        return cfg, d
    return build


def gitrepo(sub, emails, cfg):
    """Builder: a real one-commit-per-email git repository, plus the config to read it with.

    A REAL REPOSITORY, not a stub, because the check shells out to git and a stub would
    prove only that the stub matches the parser. The identity is passed per-commit with
    -c so the machine's global config cannot decide the outcome - which would make the
    result depend on who ran the suite.
    """
    def build(tmp):
        d = tmp / sub
        shutil.rmtree(d, ignore_errors=True)
        d.mkdir(parents=True)
        q = lambda *a: subprocess.run(list(a), cwd=d, capture_output=True, text=True)
        q("git", "init", "-q")
        for i, email in enumerate(emails):
            (d / f"f{i}.txt").write_text(f"{i}\n", encoding="utf-8")
            q("git", "add", "-A")
            q("git", "-c", f"user.email={email}", "-c", "user.name=T",
              "commit", "-q", "-m", f"c{i}")
        return cfg, d
    return build


def gitrepo_boundary(sub, emails, cfg, boundary_index):
    """Builder: a repo whose author_allow_before points at the commit at boundary_index.

    THE BOUNDARY SHA IS ONLY KNOWABLE AFTER THE COMMITS EXIST, so the config is built
    here rather than passed in. That is what lets the pair below differ ONLY in where the
    boundary sits relative to the bad commit - which is the thing that has to be proved.
    A pair that differed in the emails too would show that grandfathering can pass, never
    that it discriminates.
    """
    def build(tmp):
        d = tmp / sub
        shutil.rmtree(d, ignore_errors=True)
        d.mkdir(parents=True)
        q = lambda *a: subprocess.run(list(a), cwd=d, capture_output=True, text=True)
        q("git", "init", "-q")
        shas = []
        for i, email in enumerate(emails):
            (d / f"f{i}.txt").write_text(f"{i}\n", encoding="utf-8")
            q("git", "add", "-A")
            q("git", "-c", f"user.email={email}", "-c", "user.name=T",
              "commit", "-q", "-m", f"c{i}")
            shas.append(q("git", "rev-parse", "HEAD").stdout.strip())
        return dict(cfg, author_allow_before=shas[boundary_index]), d
    return build


def runs(fn, *extra):
    """Probe: run one check over a built (cfg, dir) and give back its status."""
    def probe(built):
        cfg, d = built
        rep = Report()
        fn(rep, d, cfg, *extra)
        return rep.statuses()[0]
    return probe


def cases(cfg):
    """The case table. EVERY ROW IS PROVED BOTH WAYS unless it says why it cannot be.

    These checks were previously exercised only against trees that should fail them -
    a shape passed perfectly by a check that fires on everything, and one that says
    nothing about whether the check can tell good from bad.
    """
    ship = dict(cfg, ship_paths=["dist"])
    gi = dict(cfg, must_be_gitignored=["temp/"])
    failing = dict(cfg, test_command='python -c "import sys; sys.exit(3)"')
    passing = dict(cfg, test_command='python -c "import sys; sys.exit(0)"')
    return [
        Case("planted secret", runs(check_secrets),
             tree("sec_bad", {"leak.py": 'api_key = "abcd1234efgh5678ijkl"\n'}, cfg),
             tree("sec_good", {"clean.py": 'api_key = os.environ["API_KEY"]\n'}, cfg)),
        Case("planted debug statement", runs(check_debug),
             tree("dbg_bad", {"app.js": "console.log('x');\n"}, cfg),
             tree("dbg_good", {"app.js": "export const x = 1;\n"}, cfg)),
        Case("missing .gitignore entry", runs(check_gitignore),
             tree("gi_bad", {".gitignore": "*.pyc\n"}, gi),
             tree("gi_good", {".gitignore": "temp/\n"}, gi)),
        Case("test suite with no failure test", runs(check_negative_tests),
             tree("neg_bad", {"test_thing.py": "def test_ok():\n    assert 1 == 1\n"}, cfg),
             tree("neg_good", {"test_thing.py": "def test_bad():\n"
                                                "    with pytest.raises(ValueError):\n"
                                                "        boom()\n"}, cfg)),
        Case("bytecode in shipped tree", runs(check_ship_clean),
             tree("ship_bad", {"dist/__pycache__/x.pyc": ""}, ship),
             tree("ship_good", {"dist/app.py": "x = 1\n"}, ship)),
        Case("failing test command", runs(check_tests, False),
             tree("cmd_bad", {"x.py": "\n"}, failing),
             tree("cmd_good", {"x.py": "\n"}, passing)),
        # The bad tree mixes a conforming commit with a non-conforming one. A repo where
        # EVERY commit is bad would pass a check that fires on "any commit at all", which
        # is the shape a one-sided vector cannot tell apart from a working check.
        Case("work email in commit metadata", runs(check_commit_authors),
             gitrepo("auth_bad", ["9@users.noreply.github.com", "person@company.example"], cfg),
             # the good tree carries GitHub's own web-merge committer alongside a personal
             # noreply, so the allow-list is proved to admit BOTH shapes rather than one.
             gitrepo("auth_good", ["9@users.noreply.github.com", "noreply@github.com"], cfg)),
        # BOTH TREES HAVE THE SAME BAD ADDRESS. They differ ONLY in where the boundary
        # sits, so this proves the grandfather DISCRIMINATES BY POSITION rather than
        # merely being able to pass. bad: boundary at commit 0, the work address lands at
        # commit 1, AFTER it -> still caught. good: the work address IS commit 0 and the
        # boundary is commit 0 -> accepted.
        Case("work email AFTER the grandfather boundary", runs(check_commit_authors),
             gitrepo_boundary("gf_bad",
                              ["9@users.noreply.github.com", "person@company.example"], cfg, 0),
             gitrepo_boundary("gf_good",
                              ["person@company.example", "9@users.noreply.github.com"], cfg, 0)),
    ]


def selftest() -> int:
    print("SELFTEST - patterns must catch what they target and ignore what they should\n")
    ok = True

    print("  secret patterns (must-match / must-not-match):")
    for idx, hit, miss in SECRET_VECTORS:
        pat, label = SECRET_PATTERNS[idx]
        got_hit = bool(re.search(pat, hit))
        got_miss = bool(re.search(pat, miss))
        good = got_hit and not got_miss
        ok &= good
        print(f"    {'OK  ' if good else 'MISS'} {label:<34} "
              f"catch={got_hit} falsepos={got_miss}")

    tmp = Path(tempfile.mkdtemp(prefix="verify_code_selftest_"))
    try:
        cfg = dict(DEFAULT_CONFIG)
        cfg["test_command"] = ""
        print("\n  each check must fire on a bad tree AND stay quiet on a good one:")
        cok, paired, unpaired = run_cases(cases(cfg), tmp, indent="    ", width=34)
        ok &= cok
        report_pairing(paired, unpaired, indent="    ")

        # VOID rather than a false clean. No conforming twin: "there is nothing to scan"
        # has no version of itself with something to scan - that is a different question,
        # and it is the one every case above already asks.
        rep = Report(); check_secrets(rep, tmp / "nowhere", cfg)
        s = rep.statuses()[0]; ok &= s == VOID
        print(f"    {'OK  ' if s == VOID else 'MISS'} {'nothing to scan reports VOID':<34} -> {s}")

        # the scanner must not match ITSELF, and the exclusion must be the reason - so
        # test it in both directions. Without this, the checker flags its own pattern
        # table as nine secrets and the check is useless.
        selfdir = tmp / "selfscan"
        selfdir.mkdir()
        shutil.copy(Path(__file__), selfdir / "verify_code.py")
        rep = Report(); check_secrets(rep, selfdir, cfg)
        name, s = rep.rows[0][1], rep.statuses()[0]
        good = s == VOID and "excluded" in name  # only file present is the excluded one
        ok &= good
        print(f"    {'OK  ' if good else 'MISS'} {'scanner excludes itself':<34} -> {s} [{name}]")

        rep = Report(); check_secrets(rep, selfdir, dict(cfg, scan_exclude_globs=[]))
        s = rep.statuses()[0]; ok &= s == FAIL
        print(f"    {'OK  ' if s == FAIL else 'MISS'} {'...and exclusion is the reason':<34} -> {s}")

        ok &= selftest_config(tmp, "code", "source_globs", load_config,
                              indent="    ", width=34)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print("\nSELFTEST: " + ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


# ------------------------------------------------------------------------------ main

def load_config(root: Path):
    return load_section(root, "code", DEFAULT_CONFIG)


def main(argv):
    root = Path.cwd()
    if "--write-config" in argv:
        write_section(root, "code", DEFAULT_CONFIG, CONFIG_COMMENT); return 0
    if "--selftest" in argv:
        return selftest()

    os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")
    sys.dont_write_bytecode = True  # an in-process import ignores the env var

    cfg = load_config(root)
    fast = "--fast" in argv
    rep = Report()
    check_tests(rep, root, cfg, fast)
    check_ship_clean(rep, root, cfg)
    check_secrets(rep, root, cfg)
    check_gitignore(rep, root, cfg)
    check_debug(rep, root, cfg)
    check_negative_tests(rep, root, cfg)
    check_file_sizes(rep, root, cfg)
    check_commit_authors(rep, root, cfg)
    check_byte_baselines(rep, root, cfg)

    print(rep.render())
    na = rep.count_of(NA)
    rc = rep.exit_code
    print(f"\n{len(rep.rows)} checks, {na} declared not applicable")
    print("OVERALL: " + {0: "PASS", 1: "FAIL", 2: "VOID - a check could not run"}[rc])
    return rc


if __name__ == "__main__":
    sys.exit(main(sys.argv))
