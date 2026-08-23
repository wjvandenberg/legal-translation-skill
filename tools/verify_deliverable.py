#!/usr/bin/env python3
"""verify_deliverable.py - the packaged-artefact checker.  CHECKER VERSION 3 (2026-08-20)

If a project's copy says a lower version than this one, it is stale - see the "Checkers"
line for each version in ...\\Coding\\TEMPLATE-CHANGELOG.md and re-copy.

For the thing a user actually installs or opens: a .skill / .zip package, a Word or
Excel add-in manifest, a generated .docx / .xlsx, or a variant tree about to be
published. These are the failures a test suite never sees, because they happen after
the code is correct.

    uv run python tools/verify_deliverable.py               # everything the config enables
    uv run python tools/verify_deliverable.py --selftest    # prove every check can FAIL
    uv run python tools/verify_deliverable.py --write-config

WHAT IT CATCHES
  * an archive that is corrupt, or that a user's unzip will silently truncate
  * dev-only files that leaked into a shipped tree (__pycache__, .git, a changelog)
  * a required file that is missing, or a file count that quietly changed
  * a file large enough to hit an install-truncation limit
  * archive entries with absolute paths or '..' traversal
  * a manifest that is malformed, missing a required element, or still points at localhost
  * two variant trees that have drifted apart

xml.etree is used to READ manifests only. Never use it to WRITE OOXML - it rebinds
namespace prefixes on serialisation and Word rejects the file.

EXIT CODES.  0 = every check passed or was a declared N/A.  1 = at least one check FAILED.
2 = at least one check COULD NOT RUN (VOID) and none failed. "It could not run" and "it
failed" are different facts and a caller that cannot tell them apart cannot react to
either correctly. A FAIL outranks a VOID, because a concrete defect outranks an
unestablished one; both are non-zero, so any gate wired to "non-zero blocks" is unchanged.
"""
from __future__ import annotations

import itertools
import re
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path
from xml.etree import ElementTree

# The shared plumbing. COPY house_common.py ALONGSIDE THIS FILE - without it the checker
# cannot start. check_checkers.py tracks it, so a project that copied one and not the other
# gets a reported finding rather than an import error at the worst possible moment.
from house_common import (                                       # noqa: E402
    FAIL, NA, PASS, RC_COULD_NOT_RUN, VOID, Case, Report,
    load_section, report_pairing, run_cases, selftest_config, write_section,
)

DEFAULT_CONFIG = {
    "archives": [],
    "required_in_archive": [],
    "forbidden_in_archive": ["__pycache__/", ".git/", ".DS_Store", "CHANGELOG.md",
                             ".env", "node_modules/"],
    "expected_file_count": None,
    "file_count_tolerance": 0,
    "max_member_bytes": 0,
    "manifests": [],
    "manifest_required_elements": [],
    "manifest_forbid_patterns": ["localhost", "127.0.0.1", "ngrok.io", "file://"],
    "office_files": [],
    "variant_trees": [],
    "variant_ignore": ["README.md", "LICENSE"],
}

CONFIG_COMMENT = {
    "archives": "Packages to check, e.g. ['dist/my-skill.skill'].",
    "required_in_archive": "Member paths that must exist inside every archive.",
    "forbidden_in_archive": "Substrings that must never appear in a member path.",
    "expected_file_count": "null disables. Set once you know the real number - a silent change is a defect.",
    "max_member_bytes": "0 disables. Set below any known install-truncation limit.",
    "manifests": "XML manifests to validate, e.g. ['manifest.xml'] for an Office add-in.",
    "manifest_required_elements": "Local tag names that must be present, e.g. ['Id','Version','DisplayName'].",
    "manifest_forbid_patterns": "Strings that must not survive into a production manifest.",
    "office_files": "Generated .docx/.xlsx/.pptx to structurally validate.",
    "variant_trees": "Two or more directories that must stay in step, e.g. ['uk','us'].",
    "variant_ignore": "Filenames allowed to differ or exist in only one variant tree.",
}

OFFICE_REQUIRED_PARTS = {
    ".docx": ["[Content_Types].xml", "word/document.xml"],
    ".xlsx": ["[Content_Types].xml", "xl/workbook.xml"],
    ".pptx": ["[Content_Types].xml", "ppt/presentation.xml"],
}


# ---------------------------------------------------------------------------- checks

def check_archives(rep, root, cfg):
    archives = [root / a for a in cfg["archives"]]
    present = [a for a in archives if a.exists()]
    missing = [f"declared archive not found: {a}" for a in archives if not a.exists()]
    if not archives:
        rep.record("archive integrity", 0, [], na_reason="no archives declared")
        rep.record("archive contents", 0, [], na_reason="no archives declared")
        return

    integrity, contents = list(missing), []
    members_seen = 0
    for a in present:
        try:
            with zipfile.ZipFile(a) as z:
                bad = z.testzip()
                if bad is not None:
                    integrity.append(f"{a.name}: corrupt member {bad}")
                names = z.namelist()
                members_seen += len(names)

                # entries that escape the extraction directory
                for n in names:
                    if n.startswith("/") or ".." in Path(n).parts or re.match(r"^[A-Za-z]:", n):
                        contents.append(f"{a.name}: unsafe entry path {n!r}")

                # case-insensitive collisions break extraction on Windows
                lowered = [n.lower() for n in names]
                if len(set(lowered)) != len(lowered):
                    dupes = {n for n in lowered if lowered.count(n) > 1}
                    contents.append(f"{a.name}: names collide case-insensitively: {sorted(dupes)[:3]}")

                for want in cfg["required_in_archive"]:
                    if not any(n == want or n.endswith("/" + want) for n in names):
                        contents.append(f"{a.name}: required member missing - {want}")

                for bad_frag in cfg["forbidden_in_archive"]:
                    hits = [n for n in names if bad_frag in n]
                    if hits:
                        contents.append(f"{a.name}: forbidden member {hits[0]} ({bad_frag})")

                exp = cfg["expected_file_count"]
                if exp is not None:
                    files = [n for n in names if not n.endswith("/")]
                    tol = cfg["file_count_tolerance"]
                    if abs(len(files) - exp) > tol:
                        contents.append(
                            f"{a.name}: {len(files)} files, expected {exp} (+/-{tol}) - "
                            "a silent change in file count is a defect until explained")

                limit = cfg["max_member_bytes"]
                if limit:
                    for i in z.infolist():
                        if i.file_size > limit:
                            contents.append(
                                f"{a.name}: {i.filename} is {i.file_size:,} bytes, over the "
                                f"{limit:,} truncation limit")
        except zipfile.BadZipFile:
            integrity.append(f"{a.name}: not a valid zip archive")

    rep.record("archive integrity", len(archives), integrity)
    rep.record("archive contents", members_seen, contents,
               na_reason=None if members_seen else "archives opened but contained no members")


def check_manifests(rep, root, cfg):
    mans = [root / m for m in cfg["manifests"]]
    if not mans:
        rep.record("manifest valid", 0, [], na_reason="no manifests declared")
        return
    problems = []
    for m in mans:
        if not m.exists():
            problems.append(f"declared manifest not found: {m}")
            continue
        raw = m.read_text(encoding="utf-8", errors="replace")
        try:
            tree = ElementTree.fromstring(raw)
        except ElementTree.ParseError as e:
            problems.append(f"{m.name}: malformed XML - {e}")
            continue
        tags = {el.tag.split("}")[-1] for el in tree.iter()}
        for want in cfg["manifest_required_elements"]:
            if want not in tags:
                problems.append(f"{m.name}: required element <{want}> missing")
        for pat in cfg["manifest_forbid_patterns"]:
            if pat.lower() in raw.lower():
                problems.append(f"{m.name}: contains {pat!r} - not shippable")
    rep.record("manifest valid", len(mans), problems)


def check_office(rep, root, cfg):
    files = [root / f for f in cfg["office_files"]]
    if not files:
        rep.record("office files structural", 0, [], na_reason="no office files declared")
        return
    problems = []
    for f in files:
        if not f.exists():
            problems.append(f"declared file not found: {f}")
            continue
        required = OFFICE_REQUIRED_PARTS.get(f.suffix.lower())
        if required is None:
            problems.append(f"{f.name}: unsupported extension for a structural check")
            continue
        try:
            with zipfile.ZipFile(f) as z:
                if z.testzip() is not None:
                    problems.append(f"{f.name}: archive is corrupt")
                    continue
                names = set(z.namelist())
                for part in required:
                    if part not in names:
                        problems.append(f"{f.name}: missing required part {part}")
        except zipfile.BadZipFile:
            problems.append(f"{f.name}: not a valid Office file (not a zip)")
    rep.record("office files structural", len(files), problems)


def check_variants(rep, root, cfg):
    trees = [root / t for t in cfg["variant_trees"]]
    if len(trees) < 2:
        rep.record("variant trees in step", 0, [],
                   na_reason="fewer than two variant trees declared")
        return
    ignore = set(cfg["variant_ignore"])

    def listing(base):
        return {str(p.relative_to(base)).replace("\\", "/")
                for p in base.rglob("*") if p.is_file() and p.name not in ignore}

    problems = []
    missing_tree = [t for t in trees if not t.exists()]
    for t in missing_tree:
        problems.append(f"declared variant tree not found: {t}")
    live = [t for t in trees if t.exists()]
    base_name, base_set = (live[0].name, listing(live[0])) if live else (None, set())
    total = len(base_set)
    for t in live[1:]:
        other = listing(t)
        total += len(other)
        # asymmetric comparison in BOTH directions - a one-directional test of a
        # symmetric assertion is how a parity check once missed the defect it existed for
        only_base = sorted(base_set - other)
        only_other = sorted(other - base_set)
        for f in only_base[:5]:
            problems.append(f"in {base_name} but not {t.name}: {f}")
        for f in only_other[:5]:
            problems.append(f"in {t.name} but not {base_name}: {f}")
    rep.record("variant trees in step", total, problems,
               na_reason=None if total else "variant trees exist but contain no files")


# -------------------------------------------------------------------------- selftest

def _make_zip(path, members):
    with zipfile.ZipFile(path, "w") as z:
        for name, data in members.items():
            z.writestr(name, data)


def probe(fn, idx=0):
    """Run one check over a built (cfg, dir) and give back the status it recorded."""
    def run(built):
        cfg, d = built
        rep = Report()
        fn(rep, d, cfg)
        return rep.statuses()[idx]
    return run


def _zip(path, members):
    with zipfile.ZipFile(path, "w") as z:
        for name, data in members.items():
            z.writestr(name, data)
    return path


_FIXTURE_SEQ = itertools.count()


def _unique(name):
    """A FRESH FILENAME FOR EVERY FIXTURE, because the case table shares ONE temp dir.

    Both arms of a case, and every case in the table, are handed the same directory. Reusing
    a name therefore REWRITES a file the previous arm has just opened and closed - and on
    Windows that raises a transient PermissionError, because a closed handle is not always
    a released one. The table reports it as CRASHED, so the run fails against no defect in
    the checker, and only sometimes, which is the worst way for a gate to be wrong.
    """
    n, dot = next(_FIXTURE_SEQ), name.find(".")
    return f"{name[:dot]}-{n}{name[dot:]}" if dot > 0 else f"{name}-{n}"


def _file(tmp, name, data):
    """Write a loose file and give back its NAME.

    Path.write_text returns the CHARACTER COUNT, so the obvious `write_text(...) or name`
    hands the config an integer instead of a filename. It cost four crashed cases here,
    and the crash is the good outcome: the case table reports CRASHED as a miss rather
    than swallowing it.
    """
    name = _unique(name)
    q = tmp / name
    q.write_bytes(data) if isinstance(data, bytes) else q.write_text(data, encoding="utf-8")
    return name


def _mk(tmp, name, members):
    name = _unique(name)
    _zip(tmp / name, members)
    return name


CLEAN = {"SKILL.md": "x", "scripts/a.py": "y"}


def cases(tmp):
    """The case table. EVERY ROW IS PROVED BOTH WAYS unless it says why it cannot be.

    Before this table these checks were tested only against inputs that should fail them,
    which is a shape a check firing on everything passes perfectly.
    """
    base = dict(DEFAULT_CONFIG)
    arch = probe(check_archives, idx=1)          # row 1 is 'archive contents'
    integ = probe(check_archives, idx=0)         # row 0 is 'archive integrity'
    man = probe(check_manifests)
    off = probe(check_office)
    var = probe(check_variants)

    def trees(tmp, extra):
        for v in ("uk", "us"):
            (tmp / v).mkdir(exist_ok=True)
            (tmp / v / "shared.md").write_text("a", encoding="utf-8")
        drift = tmp / "us" / "extra.md"
        if extra:
            drift.write_text("b", encoding="utf-8")
        elif drift.exists():
            drift.unlink()
        return tmp

    return [
        Case("bytecode inside package", arch,
             lambda t: (dict(base, archives=[_mk(t, "leak.zip", {"SKILL.md": "x", "s/__pycache__/a.pyc": "y"})]), t),
             lambda t: (dict(base, archives=[_mk(t, "good.zip", CLEAN)]), t)),
        Case("required member missing", arch,
             lambda t: (dict(base, archives=[_mk(t, "thin.zip", {"other.md": "x"})], required_in_archive=["SKILL.md"]), t),
             lambda t: (dict(base, archives=[_mk(t, "good.zip", CLEAN)], required_in_archive=["SKILL.md"]), t)),
        Case("file count drifted", arch,
             lambda t: (dict(base, archives=[_mk(t, "good.zip", CLEAN)], expected_file_count=99), t),
             lambda t: (dict(base, archives=[_mk(t, "good.zip", CLEAN)], expected_file_count=2), t)),
        Case("member over truncation limit", arch,
             lambda t: (dict(base, archives=[_mk(t, "big.zip", {"SKILL.md": "x" * 5000})], max_member_bytes=1000), t),
             lambda t: (dict(base, archives=[_mk(t, "good.zip", CLEAN)], max_member_bytes=1000), t)),
        Case("path traversal in archive", arch,
             lambda t: (dict(base, archives=[_mk(t, "evil.zip", {"../escape.txt": "x"})]), t),
             lambda t: (dict(base, archives=[_mk(t, "good.zip", CLEAN)]), t)),
        Case("corrupt archive", integ,
             lambda t: (dict(base, archives=[_file(t, "corrupt.zip", b"not a zip")]), t),
             lambda t: (dict(base, archives=[_mk(t, "good.zip", CLEAN)]), t)),
        Case("malformed manifest", man,
             lambda t: (dict(base, manifests=[_file(t, "bad.xml", "<a><b></a>")]), t),
             lambda t: (dict(base, manifests=[_file(t, "ok.xml", "<OfficeApp><Id>1</Id><Version>1</Version></OfficeApp>")]), t)),
        Case("manifest element missing / localhost", man,
             lambda t: (dict(base, manifests=[_file(t, "m.xml", '<OfficeApp><Id>1</Id><SourceLocation DefaultValue="https://localhost:3000"/></OfficeApp>')], manifest_required_elements=["Version"]), t),
             lambda t: (dict(base, manifests=[_file(t, "ok.xml", "<OfficeApp><Id>1</Id><Version>1</Version></OfficeApp>")], manifest_required_elements=["Version"]), t)),
        Case("invalid .docx", off,
             lambda t: (dict(base, office_files=[_file(t, "fake.docx", b"PK-not-really")]), t),
             lambda t: (dict(base, office_files=[_mk(t, "real.docx", {"[Content_Types].xml": "<x/>", "word/document.xml": "<x/>"})]), t)),
        Case("variant drift (us has extra)", var,
             lambda t: (dict(base, variant_trees=["uk", "us"]), trees(t, True)),
             lambda t: (dict(base, variant_trees=["uk", "us"]), trees(t, False))),
        Case("variant drift (reversed order)", var,
             lambda t: (dict(base, variant_trees=["us", "uk"]), trees(t, True)),
             lambda t: (dict(base, variant_trees=["us", "uk"]), trees(t, False)),
             ),
        Case("nothing declared reports N/A", var,
             lambda t: (dict(base, variant_trees=[]), t), want=NA,
             unpaired_reason="'nothing declared' has no conforming twin - declaring "
                             "something is a different question, tested by the row above"),
    ]


def selftest() -> int:
    print("SELFTEST - each check must fire on a bad input AND stay quiet on a good one")
    print()
    tmp = Path(tempfile.mkdtemp(prefix="verify_deliverable_selftest_"))
    try:
        ok, paired, unpaired = run_cases(cases(tmp), tmp, width=38)
        report_pairing(paired, unpaired)
        ok &= selftest_config(tmp, "deliverable", "archives", load_config, width=38)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print()
    print("SELFTEST: " + ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


# ------------------------------------------------------------------------------ main

def load_config(root: Path):
    return load_section(root, "deliverable", DEFAULT_CONFIG)


def main(argv):
    root = Path.cwd()
    if "--write-config" in argv:
        write_section(root, "deliverable", DEFAULT_CONFIG, CONFIG_COMMENT); return 0
    if "--selftest" in argv:
        return selftest()

    cfg = load_config(root)
    rep = Report()
    check_archives(rep, root, cfg)
    check_manifests(rep, root, cfg)
    check_office(rep, root, cfg)
    check_variants(rep, root, cfg)

    print(rep.render(name_width=32))
    na = sum(1 for _, s, _, _ in rep.rows if s == NA)
    if na == len(rep.rows):
        print("\nVOID: nothing was declared for this project. Either configure it, or "
              "record in CLAUDE.md why no deliverable check applies.")
        return 2
    rc = rep.exit_code
    print(f"\n{len(rep.rows)} checks, {na} declared not applicable")
    print("OVERALL: " + {0: "PASS", 1: "FAIL", 2: "VOID - a check could not run"}[rc])
    return rc


if __name__ == "__main__":
    sys.exit(main(sys.argv))
