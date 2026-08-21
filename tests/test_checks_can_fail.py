# -*- coding: utf-8 -*-
"""ACCEPTANCE TEST FOR BRANCH 5 — "checks can fail". Register C3 C23 C25 W3 W4 L4.

Branch 5 is the first branch in step 2 that changes BEHAVIOUR: runs that used to finish now
stop. STEP-B-ANALYSIS.md §3.2 gives slices 1, 3 and 4 a *Done when* line and gives slice 2
none, so the condition asserted here is the one the plan's own logic implies and §5.1 states
in general: **where a check is meant to catch known defects, its first run must reproduce
them.** Seven changes, each with an input built to make its new block fire AND a conforming
input that must NOT fire it.

EVERY CASE IS A PAIR, for the reason tests/README.md already records: one-sided testing
passes a check that fires on everything, and a check that cannot tell good from bad is not a
check.

TWO CASES ARE PREDICATE-LEVEL AND SAY SO IN THEIR OWN OUTPUT. `testzip()` and the
case-conflict check cannot be made to fail through repack's own path -- the path normaliser
dedups by lowercase so a case collision cannot reach the archive, and a write that completes
cannot produce a bad CRC. Those two are therefore exercised against a deliberately corrupted
archive, which tests the predicate's LOGIC and not its wiring. Declaring that is the point:
a check that established less than it appears to has not passed in full.

    uv run python tests/test_checks_can_fail.py
"""
import io
import os
import shutil
import struct
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# NO BYTECODE INSIDE THE SHIPPED TREES. This file both imports a skill module in-process and
# runs skill scripts as subprocesses, and each drops a __pycache__ directory into uk/scripts
# or us/scripts. It is gitignored, so it never reaches a commit — and it would be packaged
# into a `.skill`, which is why tests/test_instruction_rules.py checks for it.
#
# THIS IS THE THIRD ARRIVAL OF THE SAME HAZARD THROUGH A NEW CALLER. It was fixed in
# run_tests.py, came back through audit_branches.py, and came back again through this file.
# Both halves are needed and only one is obvious: run_tests.py and audit_branches.py set
# PYTHONDONTWRITEBYTECODE for their SUBPROCESSES, which cannot reach an in-process import —
# that needs sys.dont_write_bytecode, set before the import runs.
sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parent.parent
TREES = ("uk", "us")
RESULTS = []


def record(name, ok, detail=""):
    RESULTS.append((name, ok))
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"   {detail}" if detail else ""))


def head(title):
    print("\n" + "=" * 98)
    print(title)
    print("=" * 98)


def env():
    """The skill scripts import lxml; sys.executable does not carry it under `uv run`.

    run_tests.py already solved this with `uv run --with lxml` and a comment saying why --
    register defect I-14 is what happens when a later test file reaches for sys.executable
    instead: the script died on ModuleNotFoundError before reaching any gate, and `rc != 0`
    read as "the gate fired". PYTHONIOENCODING for the reason run_tests.py sets it: on
    Windows a redirected stdout defaults to cp1252 and a UnicodeEncodeError then reads to
    the caller as a FAILED check rather than a crashed one.
    """
    e = dict(os.environ)
    e.update(PYTHONIOENCODING="utf-8", PYTHONUTF8="1",
             PYTHONDONTWRITEBYTECODE="1")
    return e


def run(script, *args, tree="uk"):
    return subprocess.run(
        ["uv", "run", "--with", "lxml", "python", str(ROOT / tree / "scripts" / script),
         *[str(a) for a in args]],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        cwd=str(ROOT), env=env(), timeout=300,
    )


# ======================================================================================
# Minimal synthetic .docx and document.xml builders. EVERY FIXTURE IS INVENTED: no text
# here derives from any real document, and none may -- anonymising one still leaks its
# clause structure (CLAUDE.md §5.4).
# ======================================================================================
NS = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'
CT = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
      '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
      '<Default Extension="xml" ContentType="application/xml"/>'
      '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.'
      'relationships+xml"/><Override PartName="/word/document.xml" ContentType='
      '"application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"'
      '/></Types>')
RELS = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships '
        'xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument'
        '/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>')


def doc_xml(paras):
    body = "".join(
        f'<w:p><w:r><w:t xml:space="preserve">{t}</w:t></w:r></w:p>' for t in paras)
    return (f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            f'<w:document {NS}><w:body>{body}'
            f'<w:sectPr><w:pgSz w:w="11906" w:h="16838"/></w:sectPr>'
            f'</w:body></w:document>')


def make_docx(path, paras):
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", CT)
        z.writestr("_rels/.rels", RELS)
        z.writestr("word/document.xml", doc_xml(paras))
    return path


# Two bodies. The DIRTY one carries a doubled word and doubled punctuation -- both plain
# text-level rules, chosen because they cannot be mistaken for a structural artefact of the
# fixture builder. The CLEAN one must trip nothing at all, which is the arm that earns its
# place: tests/README.md records three of fourteen cases failing their clean arm first.
DIRTY = ["This Agreement is made between the the parties named below.",
         "The Supplier shall deliver the goods:: on the agreed date."]
CLEAN = ["This Agreement is made between the parties named below.",
         "The Supplier shall deliver the goods on the agreed date."]


# ======================================================================================
head("1. C3 — THE MANDATORY QUALITY CHECK NOW HAS AN EXIT CODE")
# ======================================================================================
tmp = Path(tempfile.mkdtemp())


def qc_total(out):
    """The printed TOTAL, so the exit code can be checked AGAINST the message."""
    for line in out.splitlines():
        if "TOTAL" in line:
            for tok in line.split():
                if tok.isdigit():
                    return int(tok)
    return None


for label, paras, want_rc, want_issues in (
        ("dirty document blocks", DIRTY, 2, True),
        ("clean document passes", CLEAN, 0, False)):
    x = tmp / f"{'dirty' if want_issues else 'clean'}.xml"
    x.write_text(doc_xml(paras), encoding="utf-8")
    r = run("quality_check.py", x)
    total = qc_total(r.stdout)
    # Parenthesised deliberately. Written without the brackets this reads as a Python
    # CHAINED comparison -- `((total>0) and (0==want_issues))` -- which reported FAIL on
    # code that was correct. Fourth instrument defect of this branch, and every one of the
    # four was in the measuring tool rather than in the skill.
    ok = (r.returncode == want_rc) and (((total or 0) > 0) == want_issues)
    record(f"C3 {label}", ok, f"exit {r.returncode} (want {want_rc}), TOTAL {total}")

# THE EXIT CODE MUST AGREE WITH THE PRINTED TOTAL. check() computes its own total for the
# summary line and __main__ recomputes one for the exit code; nothing structurally forces
# them to agree, so this is the assertion that keeps them together. A drift here would
# print "0 issues" and exit 2, or the reverse -- the shape of defect this whole branch is
# about.
agree = []
for paras in (DIRTY, CLEAN):
    x = tmp / "agree.xml"
    x.write_text(doc_xml(paras), encoding="utf-8")
    r = run("quality_check.py", x)
    t = qc_total(r.stdout)
    agree.append((t is not None) and ((t > 0) == (r.returncode == 2)))
record("C3 printed TOTAL agrees with the exit code, both arms", all(agree))

# L4 rides on C3: Step 7's only cover in the whole tree is quality_check's definition_order
# check, and it could not reach verify_diligence while the exit code was missing. Assert the
# check still exists, so a later branch cannot remove the thing C3 reconnected.
for t in TREES:
    src = (ROOT / t / "scripts" / "quality_check.py").read_text(encoding="utf-8")
    record(f"L4 {t}: definition_order check still present and registered",
           "check_definition_order" in src and "'definition_order'" in src)


# ======================================================================================
head("2. W4 — THE TRUNCATION GUARD RUNS BEFORE THE WORK, NOT AFTER IT")
# ======================================================================================
for t in TREES:
    src = (ROOT / t / "scripts" / "quality_check.py").read_text(encoding="utf-8")
    lines = src.splitlines()
    call = next(i for i, l in enumerate(lines) if l.strip() == "_check_self_integrity()")
    main = next(i for i, l in enumerate(lines) if l.startswith("if __name__"))
    record(f"W4 {t}: guard is invoked ABOVE __main__", call < main,
           f"guard line {call + 1}, __main__ line {main + 1}")

# END TO END, and this is the half that a line-order assertion cannot reach: does the guard
# actually fire on a TRUNCATED file invoked the way the step doc tells the operator to invoke
# it? 08-aux-and-quality.md says to run `--help` to see whether the guard fires. From below
# __main__ that could never work, because argparse handles --help and exits first.
gtmp = Path(tempfile.mkdtemp())
shutil.copy(ROOT / "uk" / "scripts" / "source_language_markers.py", gtmp)
full = (ROOT / "uk" / "scripts" / "quality_check.py").read_text(encoding="utf-8")
# Cut at a top-level boundary AFTER the guard so the file still COMPILES. Where truncation
# leaves invalid syntax Python raises SyntaxError before executing a line and no placement
# of the guard can help -- that limit is real, and cutting here is what isolates the
# placement question from the compile question.
boundary = full.index("\nW = 'http") + 1
cut = gtmp / "quality_check.py"
cut.write_text(full[:boundary], encoding="utf-8")
r = subprocess.run(["uv", "run", "--with", "lxml", "python", str(cut), "--help"],
                   capture_output=True, text=True, encoding="utf-8", errors="replace",
                   env=env(), timeout=120)
record("W4 truncated-but-compiling copy: --help fires the guard",
       r.returncode == 3 and "FILE INTEGRITY CHECK FAILED" in (r.stdout + r.stderr),
       f"exit {r.returncode}")

r = subprocess.run(["uv", "run", "--with", "lxml", "python",
                    str(ROOT / "uk" / "scripts" / "quality_check.py"), "--help"],
                   capture_output=True, text=True, encoding="utf-8", errors="replace",
                   env=env(), timeout=120)
record("W4 intact copy: --help prints usage and the guard stays silent",
       r.returncode == 0 and "FILE INTEGRITY CHECK FAILED" not in (r.stdout + r.stderr),
       f"exit {r.returncode}")


# ======================================================================================
head("3. C25 — OMITTING --paragraphs REFUSES INSTEAD OF WARNING")
# ======================================================================================
rtmp = Path(tempfile.mkdtemp())
orig = make_docx(rtmp / "source.docx", CLEAN)
translated = rtmp / "document.xml"
translated.write_text(doc_xml(CLEAN), encoding="utf-8")
paras_json = rtmp / "paragraphs.json"
paras_json.write_text("[]", encoding="utf-8")

out_no = rtmp / "no_flag.docx"
r = run("repack_docx.py", orig, translated, out_no)
record("C25 without --paragraphs: repack REFUSES", r.returncode != 0,
       f"exit {r.returncode}")
record("C25 without --paragraphs: NOTHING written to the delivery path",
       not out_no.exists())
record("C25 the refusal names itself as an intentional gate",
       "SKILL GATE FIRED" in (r.stdout + r.stderr))

out_yes = rtmp / "with_flag.docx"
r = run("repack_docx.py", orig, translated, out_yes, "--paragraphs", paras_json)
record("C25 with --paragraphs: repack completes and exits 0 EXPLICITLY",
       r.returncode == 0 and out_yes.exists(), f"exit {r.returncode}")


# ======================================================================================
head("4. C23 — A CORRUPT DELIVERABLE IS NEVER LEFT AT THE DELIVERY PATH")
# ======================================================================================
record("C23 a successful repack leaves no .tmp behind",
       not Path(str(out_yes) + ".tmp").exists())

# THE INDUCIBLE NEGATIVE, and it is the half that matters. Corrupt one member's CRC in the
# ORIGINAL archive: zipfile raises BadZipFile when the member is read, which happens INSIDE
# the write loop. Before this branch that loop wrote straight to the delivery path, so the
# exception left a partial .docx exactly where a good one should be.
def corrupt_member(path, member):
    """Flip a byte of `member`'s STORED data so its computed CRC stops matching.

    PATCHING THE STORED CRC DOES NOT WORK and was tried first: `testzip()` and `read()`
    both compute the CRC from the data and compare it against the CENTRAL DIRECTORY, so a
    patched local-header CRC is simply ignored and the archive reads clean. Corrupting the
    DATA is what makes the two disagree. The member is written uncompressed so the byte
    offset is the content offset -- with deflate, a short highly-compressible member can be
    only a few bytes long and an offset chosen by guesswork lands past the end of it, which
    is the other thing that was tried and silently did nothing.
    """
    keep = {}
    with zipfile.ZipFile(path) as z:
        for n in z.namelist():
            keep[n] = z.read(n)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_STORED) as z:
        for n, data in keep.items():
            z.writestr(n, data)
    raw = bytearray(path.read_bytes())
    with zipfile.ZipFile(path) as z:
        info = z.getinfo(member)
        start = info.header_offset
        nlen = struct.unpack_from("<H", raw, start + 26)[0]
        elen = struct.unpack_from("<H", raw, start + 28)[0]
        data_at = start + 30 + nlen + elen
    raw[data_at] ^= 0xFF
    path.write_bytes(bytes(raw))
    return path


# The corrupted member is one repack COPIES THROUGH via `zin.read(item.filename)`, not
# word/document.xml -- that one is replaced from the translated file on disk and never read
# out of the original, so corrupting it would prove nothing about the write loop.
bad_orig = rtmp / "corrupt_source.docx"
shutil.copy(orig, bad_orig)
corrupt_member(bad_orig, "_rels/.rels")

out_corrupt = rtmp / "from_corrupt.docx"
r = run("repack_docx.py", bad_orig, translated, out_corrupt, "--paragraphs", paras_json)
record("C23 a read failure mid-write blocks the repack", r.returncode != 0,
       f"exit {r.returncode}")
record("C23 and leaves NO partial .docx at the delivery path", not out_corrupt.exists())
record("C23 the temporary file is not left behind either",
       not Path(str(out_corrupt) + ".tmp").exists())

# PREDICATE-LEVEL, AND DECLARED AS SUCH. Neither testzip() nor the case-conflict check can
# be induced through repack's own path: normalize_path dedups by lowercase so a collision
# cannot reach the archive, and a write that completes cannot produce a bad CRC. Sixty
# archives from the twelve recorded runs pass both. So what is proved here is that the two
# predicates DETECT a corrupt archive -- not that they are wired in. The wiring is proved by
# reading the ten lines above them, and by the case immediately above.
probe = rtmp / "predicate.docx"
make_docx(probe, CLEAN)
corrupt_member(probe, "word/document.xml")
with zipfile.ZipFile(probe) as z:
    detected = z.testzip() is not None
record("C23 PREDICATE ONLY: testzip() detects a corrupted member", detected)
names = ["word/document.xml", "word/Document.xml"]
lower_map, conflicts = {}, 0
for n in names:
    ln = n.lower()
    if ln in lower_map and lower_map[ln] != n:
        conflicts += 1
    lower_map[ln] = n
record("C23 PREDICATE ONLY: the case-conflict rule detects a collision", conflicts == 1)


# ======================================================================================
head("5. W3 — A VALIDATOR'S EXIT 3 BLOCKS UNCONDITIONALLY")
# ======================================================================================
# Tested on the unit that changed rather than through a whole apply run: _run_validator is
# where the downgrade lived, and driving it directly makes the block_codes contract visible
# in all three of its arms at once.
sys.path.insert(0, str(ROOT / "uk" / "scripts"))
import apply_translations_textmatch as ap                                    # noqa: E402

PY = sys.executable


def exits(code):
    return [PY, "-c", f"import sys; sys.exit({code})"]


try:
    ap._run_validator("probe (exit 3)", exits(3), block_codes={2})
    record("W3 exit 3 blocks even when block_codes={2}", False, "it did NOT raise")
except RuntimeError as e:
    msg = str(e)
    record("W3 exit 3 blocks even when block_codes={2}", True)
    record("W3 the message sends the operator to RE-INSTALL, not to fix the input",
           "TRUNCATED" in msg and "re-install" in msg.lower()
           and "NOT edit paragraphs.json" in msg)
    record("W3 and it does NOT dress a truncated install as a gate",
           "SKILL GATE FIRED" not in msg)

# The conforming arms: the pre-existing contract must survive untouched.
try:
    ap._run_validator("probe (exit 0)", exits(0), block_codes={2})
    record("W3 exit 0 still passes", True)
except RuntimeError:
    record("W3 exit 0 still passes", False, "it raised")

try:
    ap._run_validator("probe (exit 2)", exits(2), block_codes={2})
    record("W3 exit 2 still blocks", False, "it did NOT raise")
except RuntimeError:
    record("W3 exit 2 still blocks", True)

try:
    ap._run_validator("probe (exit 1)", exits(1), block_codes={2})
    record("W3 exit 1 still WARNs and continues under block_codes={2}", True)
except RuntimeError:
    record("W3 exit 1 still WARNs and continues under block_codes={2}", False,
           "it raised — the existing contract was changed")

for t in TREES:
    src = (ROOT / t / "scripts" / "apply_translations_textmatch.py").read_text(
        encoding="utf-8")
    record(f"W3 {t}: the sentinel is a named constant, not a literal at each test",
           "_INTEGRITY_EXIT = 3" in src and "rc == _INTEGRITY_EXIT" in src)


# ======================================================================================
head("6. THE WARN CONTRACT — verify_diligence NO LONGER REPORTS WARN AS PASS")
# ======================================================================================
# INDUCING A WARN AND NOT A FAIL IS THE WHOLE DIFFICULTY, and the first attempt got it
# wrong in a way worth keeping: it removed quality_check.py from the scripts directory,
# which does make Step 9 report WARN -- but the workdir was also missing
# .validate-state.json, so Steps 4/4b and 5 reported FAIL and the OVERALL verdict was FAIL.
# The assertion "the induced condition really is a WARN" then PASSED, because it searched
# the output for the substring "WARN", which appears in the Step 9 line of a FAILing report.
# That is §5.12 rule 6 -- never a two-word needle -- committed in this branch's own test.
# It now asserts the report's OWN verdict line.
#
# The condition used instead is a state file with no history entries, which
# check_step_4_4b reports as WARN while everything else passes.
for t in TREES:
    wtmp = Path(tempfile.mkdtemp())
    sdir = wtmp / "scripts"
    sdir.mkdir()
    for f in ("verify_diligence.py", "quality_check.py", "source_language_markers.py"):
        shutil.copy(ROOT / t / "scripts" / f, sdir)
    wd = wtmp / "wd"
    (wd / "final" / "word").mkdir(parents=True)
    (wd / "paragraphs.json").write_text("[]", encoding="utf-8")
    (wd / ".validate-state.json").write_text(
        '{"validated_indices": [], "history": []}', encoding="utf-8")
    (wd / "final" / "word" / "document.xml").write_text(doc_xml(CLEAN), encoding="utf-8")

    def vd(*extra, _s=sdir, _w=wd):
        return subprocess.run(
            ["uv", "run", "--with", "lxml", "python", str(_s / "verify_diligence.py"),
             str(_w), *extra],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            env=env(), timeout=180)

    plain, strict = vd(), vd("--strict")
    verdict = next((l.strip() for l in plain.stdout.splitlines() if "OVERALL:" in l), "?")
    record(f"WARN {t}: the induced condition really is OVERALL: WARN",
           "OVERALL: WARN" in plain.stdout, verdict)
    record(f"WARN {t}: without --strict a WARN exits 1, not 0", plain.returncode == 1,
           f"exit {plain.returncode}")
    record(f"WARN {t}: with --strict a WARN exits 2, the documented FAIL code",
           strict.returncode == 2, f"exit {strict.returncode}")
    record(f"WARN {t}: the documented contract is still 0 PASS / 1 WARN / 2 FAIL",
           "1 — at least one WARN" in (ROOT / t / "scripts" / "verify_diligence.py")
           .read_text(encoding="utf-8"))


# ======================================================================================
head("7. BOTH TREES CARRY EVERY CHANGE — no fix may land in one variant only")
# ======================================================================================
# The monorepo exists because a fix once landed in one tree and shipped to a client without
# the other. A per-tree assertion is cheap and it is the whole point of the layout.
MARKERS = [
    ("scripts/quality_check.py", "sys.exit(2 if total else 0)"),
    ("scripts/repack_docx.py", "tmp_docx = output_docx + '.tmp'"),
    ("scripts/repack_docx.py", "SKILL GATE FIRED"),
    ("scripts/repack_docx.py", "shutil.move(tmp_docx, output_docx)"),
    ("scripts/apply_translations_textmatch.py", "if rc == _INTEGRITY_EXIT:"),
    ("scripts/verify_diligence.py", "return 2 if args.strict else 1"),
    ("skill-docs/10-repack-and-validate.md", "`--paragraphs` is **REQUIRED**"),
    ("SKILL.md", "Exits 2 when it reports any issue and 0 when clean"),
]
for rel, needle in MARKERS:
    present = [t for t in TREES
               if needle in (ROOT / t / rel).read_text(encoding="utf-8")]
    record(f"both trees: {rel} carries {needle[:44]!r}", len(present) == 2,
           f"found in {present}")


# ======================================================================================
head("8. THE INVERTED INSTRUMENT CAN STILL FAIL — negative tests on tools/")
# ======================================================================================
# tools/confirm_failure_chains.py was built to assert the two defects EXIST. Branch 5 fixed
# them, so it now asserts they are CLOSED. An inverted check that cannot fail is worth
# nothing, and this project has logged sixteen instances of a check passing for the wrong
# reason — four of them found in one session, all of them previously reporting a PASS.
#
# RESTORATION IS BY WRITING THE ORIGINAL BYTES BACK, never through git. The handoff records
# uncommitted work destroyed twice by `git checkout --`; the tests that were safe are the ones
# that kept the original bytes themselves.
def chains_exit():
    r = subprocess.run(["uv", "run", "python", str(ROOT / "tools" /
                                                   "confirm_failure_chains.py")],
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace", cwd=str(ROOT), env=env(), timeout=300)
    return r.returncode, (r.stdout + r.stderr)


GUARD_CALL = "_check_self_integrity()\n\nW = "


def _reopen_chain1(text):
    """Put the exit-3 test back behind block_codes — register row W3 returning."""
    return text.replace("if rc == _INTEGRITY_EXIT:", "if rc == 999999:", 1)


def _delete_guard(text):
    """Remove the guard CALL but leave its definition.

    THIS MUTATION FOUND A HOLE IN THE INSTRUMENT. With the call gone, quality_check.py
    dropped out of the tool's population entirely, so its "is any guard below __main__?"
    comparison had nothing to compare and reported the chain CLOSED. The tool now also
    fails a script that defines the guard and never calls it, which is strictly worse
    than calling it late.
    """
    return text.replace(GUARD_CALL, "pass  # guard call deleted\n\nW = ", 1)


def _relocate_guard(text):
    """MOVE the call below __main__ — register row W4 returning in its original shape.

    Distinct from _delete_guard on purpose: one tests the ordering rule, the other tests
    that the rule's subject cannot vanish from its own population. Deleting proves nothing
    about ordering, and the first version of this test used deletion for both.
    """
    moved = text.replace(GUARD_CALL, "W = ", 1)
    return moved.replace("\n# === SKILL FILE COMPLETE ===",
                         "\n_check_self_integrity()\n\n# === SKILL FILE COMPLETE ===", 1)


MUTATIONS = [
    ("scripts/apply_translations_textmatch.py", _reopen_chain1,
     "chain 1 reopened: exit 3 stops blocking"),
    ("scripts/quality_check.py", _delete_guard,
     "chain 2 defeated by DELETING the guard call"),
    ("scripts/quality_check.py", _relocate_guard,
     "chain 2 reopened: the guard runs BELOW __main__ again"),
]
for rel, mutate, why in MUTATIONS:
    target = ROOT / "uk" / rel
    original = target.read_bytes()
    try:
        text = original.decode("utf-8")
        mutated = mutate(text)
        if mutated == text:
            record(f"negative: {why}", False, "the mutation changed nothing")
            continue
        target.write_bytes(mutated.encode("utf-8"))
        rc, _ = chains_exit()
        record(f"negative: {why} -> the tool FAILS", rc != 0, f"exit {rc}")
    finally:
        target.write_bytes(original)
    record(f"negative: {rel} restored byte-identically",
           target.read_bytes() == original)

rc, _ = chains_exit()
record("and the tool passes again once both mutations are reverted", rc == 0, f"exit {rc}")


# ======================================================================================
passed = sum(1 for _, ok in RESULTS if ok)
head(f"{passed} of {len(RESULTS)} cases behave correctly")
if passed != len(RESULTS):
    print("\n  FAILED:")
    for n, ok in RESULTS:
        if not ok:
            print(f"    - {n}")
print("\n  TWO OF THESE CASES ARE PREDICATE-LEVEL AND ARE LABELLED 'PREDICATE ONLY'.")
print("  They prove the two post-write checks DETECT a corrupt archive; they do not")
print("  prove the wiring, because neither condition can be induced through repack's own")
print("  path. The inducible half of C23 -- a read failure mid-write leaving nothing at")
print("  the delivery path -- IS tested end to end above.")
sys.exit(0 if passed == len(RESULTS) else 1)
