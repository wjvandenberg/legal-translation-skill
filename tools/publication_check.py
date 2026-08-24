# -*- coding: utf-8 -*-
"""PUBLICATION CHECK — run before pushing any committable file to a public repository.

Wouter, 2026-08-05: "Make a sensitive info / personal info / commercial info check at the very
end - this document will be pushed to github before we start coding."

This is a THIRD control, not a replacement for the two the charter already requires. Those are
name-based (93 patterns) and shape-based (candidates for human judgement). This one asserts the
specific classes the charter names as forbidden, and FAILS rather than listing candidates.

Written with raw strings throughout: two earlier attempts at this check were written through a
shell heredoc, which ate the backslashes and reported a clean result on a file that was not.

    uv run python tools/publication_check.py                 # every committable markdown
    uv run python tools/publication_check.py EVIDENCE-x.md   # or just these

THE FILE LIST USED TO BE SIX HARD-CODED NAMES -- written before `.claude/rules/` and
`.claude/skills/` existed, so THE BLOCKING CONTROL WAS NOT LOOKING AT THEM AT ALL. Found
2026-08-24, alongside the same defect in `descriptor_shape_sweep.py`. It is the worse of the two
because this one is the gate: a file it does not open is a file that cannot fail it, and the
output is indistinguishable from coverage. Phase 3c adds an EVIDENCE- document whose subject is
past leaks, which is the likeliest place in the repository to hold one.

It now DISCOVERS the committable markdown by glob, honours an explicit list, PRINTS WHAT IT READ,
and exits 2 as VOID on an empty set rather than certifying nothing.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# The six that were hard-coded, kept by NAME so a rename is noticed rather than silently dropped.
CORE = ["CLAUDE.md", "FINDINGS-REGISTER.md", "A3-STRUCTURAL-ANALYSIS.md", "STEP-B-ANALYSIS.md",
        "DECISIONS-LOG.md", "OPUS-5-MIGRATION.md"]
# Globs, so a document added later is checked without anybody remembering to add it here.
DISCOVER = ["README.md", "EVIDENCE-*.md", "REGISTER-*.md", "PLAN-*.md",
            ".claude/rules/*.md", ".claude/skills/*/SKILL.md", "tests/README.md"]


def _targets(argv):
    if argv:
        return [Path(a) if Path(a).is_absolute() else ROOT / a for a in argv]
    out = [ROOT / n for n in CORE if (ROOT / n).exists()]
    for g in DISCOVER:
        out.extend(sorted(ROOT.glob(g)))
    seen, uniq = set(), []
    for p in out:
        if p.resolve() not in seen:
            seen.add(p.resolve())
            uniq.append(p)
    return uniq


_PATHS = _targets(sys.argv[1:])
_ABSENT = [n for n in CORE if not (ROOT / n).exists()] if not sys.argv[1:] else []
print("=" * 88)
print(f"FILES READ: {len(_PATHS)}")
for _p in _PATHS:
    print(f"    {_p.resolve().relative_to(ROOT) if _p.resolve().is_relative_to(ROOT) else _p}")
if _ABSENT:
    print(f"  MISSING from the core list, so NOT checked: {_ABSENT}")
if not _PATHS:
    print("VOID -- no file was opened. Nothing has been established; this is not a pass.")
    sys.exit(2)
print("=" * 88)

FILES = [str(p.resolve().relative_to(ROOT)).replace("\\", "/")
         if p.resolve().is_relative_to(ROOT) else str(p) for p in _PATHS]

# (label, pattern, is_failure) -- a failure blocks; otherwise it is reported for judgement
PROBES = [
 ("absolute Windows path", r"[A-Za-z]:\\[\w\-. \\]+", True),
 ("absolute POSIX path", r"(?<![\w.])/(?:home|Users|mnt)/[\w\-./]+", True),
 ("home-relative path", r"~[\\/][\w\-. \\/]+", True),
 ("email address", r"[\w.\-]+@[\w.\-]+\.\w{2,}", True),
 ("credential-shaped string", r"(?i)\b(?:api[_-]?key|secret|token|password|passwd)\s*[:=]\s*\S+", True),
 ("money amount", r"(?:EUR|USD|GBP|CHF|PLN|HUF|NOK|£|\$|€)\s?[\d][\d,. ]{2,}", True),
 ("capacity or power figure", r"\d[\d,. ]*\s?(?:MW|kW|GW|MWh|kWh|MWp|kWp)\b", True),
 ("company-form suffix", r"\b[A-Z][\w'\-]+\s+(?:B\.?V\.?|N\.?V\.?|GmbH|S\.?p\.?A\.?|S\.?à?\.?r\.?l\.?|"
                        r"A/S|Oy|Sp\.\s?z\s?o\.?o\.?|Kft|Ltd\.?|LLP|LLC|Inc\.?|PLC)\b", True),
 ("registration-number shape", r"\b(?:KvK|VAT|BTW|NIF|CIF|P\.?IVA)\s*[:.]?\s*[\w\-]{6,}", True),
 ("external URL", r"https?://(?!schemas\.openxmlformats|schemas\.microsoft)[\w./\-]+", False),
 ("named person other than the author", r"\b(?:Mr|Ms|Mrs|Dr|Prof)\.?\s+[A-Z]\w+", True),
 # ADDED 2026-08-06 on Wouter's instruction. A test document is named by its INSTRUMENT CLASS
 # and its LANGUAGE -- "Agreement (Norwegian)", "Power of Attorney (Hungarian)" -- and never
 # by what it is about. Subject matter plus language identifies a real instrument more sharply
 # than a name does, and the 93-pattern name scan is structurally blind to it: it reported 0
 # hits on every one of these, correctly, because none of it is a name. Same failure class as
 # the commercial-terms leak of 2026-07-31, so it gets the same answer -- a specific blocking
 # probe here, and the list-free temp/descriptor_shape_sweep.py beside it for the qualifiers
 # nobody thought to list. That pairing is not belt-and-braces: the sweep found four more that
 # this list would have missed.
]

# ...and the patterns themselves are loaded from OUTSIDE the repository, for the reason the
# charter has always given for the name list: a file holding one real string per pattern is
# as sensitive as the thing it protects. The first version of this probe carried them inline
# and fired on the charter's own rule text, which had listed them as examples. That was the
# probe working.
import os

_desc = Path(os.environ.get("CORPUS_DESCRIPTORS_FILE",
                            ROOT.parent / "legal-translation-private" / "corpus-descriptors.txt"))
if _desc.exists():
    _pats = [l.strip() for l in _desc.read_text(encoding="utf-8").splitlines()
             if l.strip() and not l.lstrip().startswith("#")]
    PROBES.append(("corpus subject-matter descriptor", "(?i)" + "|".join(_pats), True))
    DESCRIPTOR_PROBE = f"{len(_pats)} pattern(s) loaded"
else:
    # A check that silently stops checking is worse than no check.
    DESCRIPTOR_PROBE = "DISABLED — descriptor list not found at %s" % _desc

# Strings that LOOK like a hit but are the project's own public identity or a published artefact.
ALLOW = [
    "lawve.ai",                       # the project's own publication channel, named in the charter
    "github.com",                     # the distribution channel, named in the charter
    "claude.ai",
]

FAIL, NOTE = [], []
for name in FILES:
    t = (ROOT / name).read_text(encoding="utf-8")
    print("=" * 88)
    print(name)
    print("=" * 88)
    clean = True
    for label, pat, blocking in PROBES:
        hits = [h for h in sorted(set(re.findall(pat, t)))
                if not any(a in h for a in ALLOW)]
        # a relative path such as ..\legal-translation-private\ is not absolute
        if "path" in label:
            hits = [h for h in hits if not h.startswith("..")]
            # ...and a QUOTED REGEX from the skill's own code is not a path either: the pattern
            # `\bapplicant organisation:\s*$` matched "letter colon backslash" and was reported
            # as an absolute path in A3. Regex metacharacters next to the match rule it out.
            # FIXED 2026-08-06: this suppressor was too broad and was hiding a REAL hit. A
            # home-relative path whose first segment began with a capital D contains a
            # backslash followed by D, which the old test read as the regex escape \D, so the
            # check reported 4 of 5 findings and said CLEAN about the fifth. A regex escape is
            # followed by a quantifier, a delimiter or the end of the token -- never by more
            # word characters, which is what a path segment looks like. Narrowed with a
            # negative lookahead; both the real path and the quoted regex that motivated the
            # original filter now classify correctly. Test vectors: the sibling test file,
            # which is NOT committable because it holds one real string per vector by design.
            # (This comment used to quote the path itself, which would have carried a home
            # path into `tools/` inside the very check that blocks home paths.)
            hits = [h for h in hits
                    if not re.match(r"^[a-z]:\\[a-z]$", h)
                    and not re.search(r"\\[bsdwSDW](?![A-Za-z0-9])|\[[a-z]{2}\]|\*\$", h)]
        if not hits:
            continue
        clean = False
        tag = "FAIL" if blocking else "note"
        for h in hits[:8]:
            print("  [%s] %-26s %r" % (tag, label, h[:78]))
        (FAIL if blocking else NOTE).append((name, label, len(hits)))
    if clean:
        print("  [OK  ] none of the forbidden classes present")
    print()

print("=" * 88)
print("JUDGEMENT ITEMS THIS CHECK CANNOT DECIDE — read them, do not assume")
print("=" * 88)
print("  1. The author's own name and his quoted verdicts appear throughout. That is the")
print("     charter's established practice for these files and it is his call, not a defect.")
print("  2. Quotations from the SKILL's own text are quotations of an already-published")
print("     artefact, so they add no exposure.")
print("  3. Relative paths to sibling folders (..\\legal-translation-private\\, ..\\logs\\)")
print("     name directories that are NOT in the repository. They reveal a folder name and")
print("     nothing in it. The charter names those folders itself.")
print()
print("=" * 88)
print("corpus subject-matter descriptor probe: %s" % DESCRIPTOR_PROBE)
print("RESULT: %d blocking finding(s), %d note(s)" % (len(FAIL), len(NOTE)))
for n, l, c in FAIL:
    print("  BLOCKING  %-28s %s (%d)" % (n, l, c))
for n, l, c in NOTE:
    print("  note      %-28s %s (%d)" % (n, l, c))
print("=" * 88)
sys.exit(1 if FAIL else 0)
