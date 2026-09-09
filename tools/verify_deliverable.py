#!/usr/bin/env python3
"""verify_deliverable.py - the packaged-artefact checker.  CHECKER VERSION 9 (2026-09-01)

If a project's copy says a lower version than this one, it is stale - see the "Checkers"
line for each version in ...\\Coding\\templates\\TEMPLATE-CHANGELOG.md and re-copy.

For the thing a user actually installs or opens: a .skill / .zip package, a Word or
Excel add-in manifest, a generated .docx / .xlsx, or a variant tree about to be
published. These are the failures a test suite never sees, because they happen after
the code is correct.

    uv run python tools/verify_deliverable.py               # everything the config enables
    uv run python tools/verify_deliverable.py --selftest    # prove every check can FAIL
    uv run python tools/verify_deliverable.py --write-config

THE SCOPE, WRITTEN DOWN, BECAUSE A GATE THAT DOES NOT STATE ITS OWN BOUNDARY HAS A SILENT ONE.
It replaced a "WHAT IT CATCHES" list that said the first third of this and stopped: two
lists of what one gate does is how the two come to disagree, and the half that was missing
is the half a reader cannot infer.

  CHECKED HERE     an archive that is corrupt, or that a user's unzip will silently
                   truncate · entries with absolute paths, a drive letter, or '..'
                   traversal · names that collide case-insensitively, which breaks
                   extraction on Windows · required and forbidden members · a file count
                   that quietly changed · a member over max_member_bytes · a manifest that
                   is malformed, missing a required element, or still points at localhost ·
                   an Office file that is not a zip or is missing a required OOXML part ·
                   two variant trees whose FILE LISTINGS have drifted, compared in BOTH
                   directions · variant trees whose same-named files are DIFFERENT PROGRAMS,
                   compared as parsed ASTs so reflowing and recommenting are not findings ·
                   and a file declared in variant_must_differ that is BYTE-IDENTICAL across
                   trees, which means nobody localised it.
  ALLOWED, NAMED   files named in variant_ignore differing freely between trees (README,
                   LICENSE) · at most 5 differences printed per direction per tree pair -
                   a declared truncation of the LIST only: the denominator stays whole, so
                   the count never shrinks with the output.
  NOT CHECKED      whether the deliverable WORKS. Nothing here installs it, opens it or
                   runs it; every check is STRUCTURAL, and a package that satisfies all of
                   them can still fail on a user's machine · the CONTENT of any shipped
                   file, so a .docx carrying every required part and the wrong text passes
                   · a variant defect that is IDENTICALLY WRONG in both trees and that
                   NOTHING DECLARED - the within-tree arm is driven by variant_must_differ,
                   so a file nobody listed there is still invisible to every comparison
                   between trees. B4 made the class checkable; it cannot make it automatic,
                   because only a person knows which files carry jurisdiction · a
                   non-Python program, which cannot be parsed here and so falls back to
                   being compared by name only · signatures, checksums,
                   notarisation, provenance · a manifest that is well-formed and
                   semantically wrong.
  HANDED OVER      a member that is ITSELF an archive. Nothing here recurses, so an inner
                   package has had none of the checks above run over it. Reported as
                   JUDGE - the checker can see that it is there and cannot see inside it.

xml.etree is used to READ manifests only. Never use it to WRITE OOXML - it rebinds
namespace prefixes on serialisation and Word rejects the file.

EXIT CODES.  0 = every check passed or was a declared N/A.  1 = at least one check FAILED.
2 = at least one check COULD NOT RUN (VOID) and none failed. "It could not run" and "it
failed" are different facts and a caller that cannot tell them apart cannot react to
either correctly. A FAIL outranks a VOID, because a concrete defect outranks an
unestablished one; both are non-zero, so any gate wired to "non-zero blocks" is unchanged.

AND A FIFTH VERDICT THAT CHANGES NO EXIT CODE: JUDGE, for the nested archive above. It is
not a defect - shipping a package inside a package is a legitimate thing to do - so failing
on it would be wrong. It is also not nothing: the inner artefact has been checked by
nobody. A person decides, and sees it in the report, in the OVERALL line and in a
JUDGE-CLAIMS mark that run_tests.py reads.
"""
from __future__ import annotations

import ast
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
    FAIL, JUDGE, NA, PASS, RC_COULD_NOT_RUN, VOID, Case, Report,
    finish, load_section, report_pairing, run_cases, selftest_config,
    wants_report_json, write_section,
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
    "variant_ast_suffixes": [".py"],
    "variant_must_differ": [],
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
    "variant_ast_suffixes": "Suffixes compared as PARSED PROGRAMS, not filenames. Only .py can be parsed here.",
    "variant_must_differ": "Paths that MUST differ between trees - the localised ones. Byte-identical means never localised, and a CROSS-tree diff passes that as clean.",
}

OFFICE_REQUIRED_PARTS = {
    ".docx": ["[Content_Types].xml", "word/document.xml"],
    ".xlsx": ["[Content_Types].xml", "xl/workbook.xml"],
    ".pptx": ["[Content_Types].xml", "ppt/presentation.xml"],
}


# ---------------------------------------------------------------------------- checks

# Suffixes that make a member a deliverable in its own right. OOXML files are deliberately
# absent even though a .docx IS a zip: check_office_files already opens those and looks for
# the parts that matter, so listing them here would hand a person a question that another
# check has already answered - and a JUDGE row full of answered questions gets ignored,
# taking the unanswered ones with it.
NESTED_SUFFIXES = {".zip", ".tar", ".gz", ".tgz", ".bz2", ".xz", ".7z", ".rar", ".skill"}


def check_archives(rep, root, cfg):
    archives = [root / a for a in cfg["archives"]]
    present = [a for a in archives if a.exists()]
    missing = [f"declared archive not found: {a}" for a in archives if not a.exists()]
    if not archives:
        rep.record("archive integrity", 0, [], na_reason="no archives declared")
        rep.record("archive contents", 0, [], na_reason="no archives declared")
        # DECLARED HERE TOO, and not left out. A check that simply vanishes on one path
        # through the function reads, on the report, exactly like a check that passed.
        rep.record("nested archives", 0, [], na_reason="no archives declared")
        return

    integrity, contents, nested = list(missing), [], []
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

                # A MEMBER THAT IS ITSELF AN ARCHIVE. Every check in this function stops at
                # the outer zip - it does not recurse - so an inner archive is a whole
                # deliverable nothing here has examined: not its integrity, not its unsafe
                # paths, not its forbidden members. The checker can see that it is there
                # and cannot see inside it, which is the definition of a JUDGE and the
                # reason "nested archives" sat in the NOT CHECKED list until version 5.
                nested += [f"{a.name}: contains {n} - an archive inside an archive, and "
                           f"NOTHING here looked inside it"
                           for n in names if Path(n).suffix.lower() in NESTED_SUFFIXES]

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
    rep.record("nested archives", members_seen, nested,
               na_reason=None if members_seen else "archives opened but contained no members",
               judge_reason="an inner archive is a deliverable of its own that no check "
                            "here has opened. Extract it and run this checker on it, or "
                            "write down why it does not need one.")


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

    # ---- ARM 2: PARSED PROGRAMS, not filenames.
    # The listing above is satisfied by a matching NAME. Two trees can carry the same
    # filename holding different programs and it reports clean, which is change-list B4.
    # ast.dump without attributes drops line numbers and formatting, so reflowing a file
    # is not a finding and changing what it DOES is.
    suffixes = tuple(cfg["variant_ast_suffixes"])
    ast_problems, compared = [], 0
    if live and suffixes:
        shared = set(listing(live[0]))
        for t in live[1:]:
            shared &= set(listing(t))
        for rel in sorted(r for r in shared if r.endswith(suffixes)):
            shapes = {}
            for t in live:
                try:
                    shapes[t.name] = ast.dump(ast.parse((t / rel).read_text(encoding="utf-8")))
                except (SyntaxError, UnicodeDecodeError, OSError) as e:
                    ast_problems.append(f"{t.name}/{rel}: cannot be parsed, so it cannot be "
                                        f"compared - {type(e).__name__}")
            if len(shapes) > 1 and len(set(shapes.values())) > 1:
                differing = sorted(shapes)
                ast_problems.append(f"{rel}: same filename, DIFFERENT program in "
                                    f"{' vs '.join(differing)}")
            compared += len(shapes)
    rep.record("variant programs in step", compared, ast_problems,
               na_reason=None if compared else
               "no shared parseable files in the variant trees to compare as programs")

    # ---- ARM 3: THE WITHIN-TREE ARM, and it exists because arm 1 is STRUCTURALLY blind.
    # A cross-tree comparison's success criterion IS identity, so a file that was supposed
    # to be localised and never was - byte-identical in every tree - passes arms 1 and 2 as
    # PERFECTLY clean. That is the defect "identically wrong in both trees": US users given
    # UK rules, invisible to every comparison BETWEEN the trees. So it is asserted per
    # declared file instead: these must differ, and if they do not, nobody localised them.
    must = list(cfg["variant_must_differ"])
    same_problems, examined = [], 0
    for rel in must:
        present = [t for t in live if (t / rel).is_file()]
        if len(present) < 2:
            same_problems.append(f"{rel}: declared must-differ but present in "
                                 f"{len(present)} of {len(live)} tree(s) - nothing to compare")
            continue
        examined += len(present)
        blobs = {t.name: (t / rel).read_bytes() for t in present}
        if len(set(blobs.values())) == 1:
            same_problems.append(f"{rel}: BYTE-IDENTICAL across {', '.join(sorted(blobs))} "
                                 f"- declared must-differ, so it was never localised")
    rep.record("variant files that must differ", examined, same_problems,
               na_reason=None if must else
               "variant_must_differ is empty - nothing is declared as needing to be localised")


# -------------------------------------------------------------------------- selftest

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

#: The same program, written two ways. Reflowed, recommented, an extra blank line, and a
#: different amount of space after `return`. ast.dump without attributes sees ONE program,
#: which is what makes the AST arm a comparison of programs rather than of bytes.
_PROG_A = "def rate():\n    return 1\n"
_PROG_A_REFLOWED = "# localised for this jurisdiction\n\ndef rate():\n\n    return  1\n"
_PROG_B = "def rate():\n    return 2\n"


def _var_trees(tmp, *trees):
    """Fresh, UNIQUELY-NAMED variant trees, and the naming is not cosmetic.

    The older `trees()` helper reuses uk/ and us/, which is safe only while every case
    touching them wants the same contents. These arms deliberately put DIFFERENT bytes
    behind the SAME filenames, so sharing directories would make one case rewrite the
    fixture another has already built - the same hazard _unique() exists for, and it
    surfaces as an intermittent CRASHED row rather than as a defect in the checker.
    """
    stamp = next(_FIXTURE_SEQ)
    names = []
    for i, files in enumerate(trees):
        d = tmp / f"vt{stamp}_{i}"
        d.mkdir(parents=True, exist_ok=True)
        for rel, data in files.items():
            p = d / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(data, encoding="utf-8")
        names.append(d.name)
    return names


def cases(tmp):
    """The case table. EVERY ROW IS PROVED BOTH WAYS unless it says why it cannot be.

    Before this table these checks were tested only against inputs that should fail them,
    which is a shape a check firing on everything passes perfectly.
    """
    base = dict(DEFAULT_CONFIG)
    arch = probe(check_archives, idx=1)          # row 1 is 'archive contents'
    integ = probe(check_archives, idx=0)         # row 0 is 'archive integrity'
    nest = probe(check_archives, idx=2)          # row 2 is 'nested archives'
    man = probe(check_manifests)
    off = probe(check_office)
    var = probe(check_variants)                  # row 0 - the listing comparison
    prog = probe(check_variants, idx=1)          # row 1 - parsed programs (B4-a)
    same = probe(check_variants, idx=2)          # row 2 - the within-tree arm (B4-b)

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
        # THE JUDGE CASE. Note what the good arm is NOT: it is not an empty package, it is
        # a package with ordinary members. An inner .zip is handed over; a .md and a .py are
        # not. Had the good arm been the empty case, the check could have been made to pass
        # by firing whenever an archive has any member at all.
        Case("nested archive needs a person", nest,
             lambda t: (dict(base, archives=[_mk(t, "outer.zip",
                                                 {"SKILL.md": "x", "inner.zip": "PK\x03\x04"})]), t),
             lambda t: (dict(base, archives=[_mk(t, "flat.zip", CLEAN)]), t),
             want=JUDGE),
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
        # B4-a. The GOOD arm is the point: same program, reflowed and recommented. A
        # byte-compare would fail it, so passing it is what proves this compares PROGRAMS.
        Case("same filename, different program", prog,
             lambda t: (lambda v: (dict(base, variant_trees=v), t))(
                 _var_trees(t, {"shared.md": "a", "rate.py": _PROG_A},
                               {"shared.md": "a", "rate.py": _PROG_B})),
             lambda t: (lambda v: (dict(base, variant_trees=v), t))(
                 _var_trees(t, {"shared.md": "a", "rate.py": _PROG_A},
                               {"shared.md": "a", "rate.py": _PROG_A_REFLOWED}))),
        # B4-b. THE SYMMETRIC DEFECT. Both trees carry the same bytes behind a file that
        # was supposed to be localised, so every comparison BETWEEN trees calls it clean.
        Case("must-differ file never localised", same,
             lambda t: (lambda v: (dict(base, variant_trees=v, variant_must_differ=["rate.py"]), t))(
                 _var_trees(t, {"shared.md": "a", "rate.py": _PROG_A},
                               {"shared.md": "a", "rate.py": _PROG_A})),
             lambda t: (lambda v: (dict(base, variant_trees=v, variant_must_differ=["rate.py"]), t))(
                 _var_trees(t, {"shared.md": "a", "rate.py": _PROG_A},
                               {"shared.md": "a", "rate.py": _PROG_B}))),
        # THE TWO "NOTHING HAPPENED" STATES, PROVED DISTINCT. Declaring a file that is not
        # there is VOID - the check could not run, and A2's rule that a declared-but-
        # unreadable LIST is VOID applies just as well to a declared-but-absent FILE.
        # Declaring nothing at all is N/A. Neither is allowed to read as clean, and
        # collapsing them into one verdict is how "we checked" comes to mean "we didn't".
        Case("must-differ file declared but absent", same,
             lambda t: (lambda v: (dict(base, variant_trees=v, variant_must_differ=["absent.py"]), t))(
                 _var_trees(t, {"shared.md": "a"}, {"shared.md": "a"})),
             lambda t: (lambda v: (dict(base, variant_trees=v, variant_must_differ=[]), t))(
                 _var_trees(t, {"shared.md": "a"}, {"shared.md": "a"})),
             want=VOID, good_want=NA),
        Case("variant drift (reversed order)", var,
             lambda t: (dict(base, variant_trees=["us", "uk"]), trees(t, True)),
             lambda t: (dict(base, variant_trees=["us", "uk"]), trees(t, False)),
             ),
        Case("nothing declared reports N/A", var,
             lambda t: (dict(base, variant_trees=[]), t), want=NA,
             unpaired_reason="'nothing declared' has no conforming twin - declaring "
                             "something is a different question, tested by the row above"),
    ]


def _assert_symmetric_defect(tmp) -> bool:
    """B4's ACCEPTANCE CONDITION, and a case row cannot state it.

    The condition is not "the new arm fires". It is that the new arm fires on a fixture the
    CROSS-TREE comparison passes as clean - because if the old arms caught it too, the new
    one is redundant and the whole change is decoration. A Case row reads one check's
    verdict; this reads THREE off ONE input and asserts they disagree in the one direction
    that matters.

    ONE FIXTURE, THREE VERDICTS: two trees, identical filenames, byte-identical contents,
    and rate.py declared as needing localisation. Arms 1 and 2 are structurally incapable
    of seeing it, because their success criterion IS identity.
    """
    print()
    names = _var_trees(tmp, {"shared.md": "a", "rate.py": _PROG_A},
                            {"shared.md": "a", "rate.py": _PROG_A})
    cfg = dict(DEFAULT_CONFIG, variant_trees=names, variant_must_differ=["rate.py"])
    rep = Report()
    check_variants(rep, tmp, cfg)
    listing, programs, must = rep.statuses()[0], rep.statuses()[1], rep.statuses()[2]

    good = listing == PASS and programs == PASS and must == FAIL
    print(f"  {'OK  ' if good else 'MISS'} the SYMMETRIC defect, one fixture, three arms")
    print(f"         listings across trees   -> {listing}"
          f"   {'(blind: the names match)' if listing == PASS else '(UNEXPECTED)'}")
    print(f"         programs across trees   -> {programs}"
          f"   {'(blind: the bytes match)' if programs == PASS else '(UNEXPECTED)'}")
    print(f"         must-differ, within-tree-> {must}"
          f"   {'(CAUGHT it)' if must == FAIL else '(MISSED IT - the arm is not built right)'}")
    if good:
        print("         a cross-tree comparison passes this as clean; that is why arm 3 exists.")
    return good


def selftest() -> int:
    print("SELFTEST - each check must fire on a bad input AND stay quiet on a good one")
    print()
    tmp = Path(tempfile.mkdtemp(prefix="verify_deliverable_selftest_"))
    try:
        ok, paired, unpaired = run_cases(cases(tmp), tmp, width=38)
        report_pairing(paired, unpaired)
        ok &= selftest_config(tmp, "deliverable", "archives", load_config, width=38)
        ok &= _assert_symmetric_defect(tmp)
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

    # --report-json suppresses the prose and emits the rows instead, so something other than
    # a person can judge this run. Every print below is guarded rather than the function
    # being split: the exit-code logic is the part a wrapper must agree with, and duplicating
    # it into a second path is how the two would come to disagree.
    quiet = wants_report_json(argv[1:])
    if not quiet:
        print(rep.render(name_width=32))
    # rep.statuses(), NEVER an unpack of rep.rows. This line unpacked FOUR values from a
    # 5-tuple and crashed the whole run with a traceback - every time, not intermittently -
    # and nothing reported it, because run_tests.py runs only --selftest and a checker's
    # main() is exercised by no suite at all. The row layout belongs to house_common; a
    # caller that reaches into it breaks whenever that layout gains a field.
    na = sum(1 for s in rep.statuses() if s == NA)
    if na == len(rep.rows):
        if not quiet:
            print("\nVOID: nothing was declared for this project. Either configure it, or "
                  "record in CLAUDE.md why no deliverable check applies.")
        # 2, NOT rep.exit_code - every row is a declared N/A, so the report alone says PASS.
        # This is exactly why finish() is PASSED the code rather than deriving it.
        return finish(rep, "verify_deliverable.py", 2, quiet)
    rc = rep.exit_code
    if not quiet:
        print(f"\n{len(rep.rows)} checks, {na} declared not applicable")
        # rep.verdict(), not the third private copy of it - see the note in verify_code.py.
        print("OVERALL: " + rep.verdict())
        mark = rep.judge_line()
        if mark:
            print(mark)
    return finish(rep, "verify_deliverable.py", rc, quiet)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
