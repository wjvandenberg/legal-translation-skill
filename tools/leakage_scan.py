"""
leakage_scan.py -- apply the name/term pattern list to one or more files.

WHY THIS EXISTS. CLAUDE.md's Confidentiality section requires TWO controls on every
committable file: the 93-pattern name/term scan, and the shape-based sweep. The second
existed. The first did NOT: `test_leakage_patterns.py` only self-tests the patterns -- it
verifies they compile, match their own vectors and do not fire on neutral prose -- and has
no file argument at all. So "run both controls" was, for control 1, unrunnable. Found
2026-08-04 while verifying CLAUDE.md.

This is the scanner CLAUDE.md already names. It reads the pattern list BY PATH (or from
LEAKAGE_LIST_PATH), so the scanner is publishable while the list is not.

OUTPUT POLICY, and it matters. A hit is reported as pattern index + line number + a short
hash of the matched text -- NEVER the matched text itself -- because this tool's output ends
up in transcripts, terminals and scrollback, and a client name reproduced there is the exact
leak the list exists to prevent. Pass --show only when you are looking at the screen alone
and need to identify what matched.

Exit codes:  0 = clean · 1 = hits found · 2 = the list could not be read (control VOID)

Usage:
    uv run python leakage_scan.py <file> [<file> ...]
    uv run python leakage_scan.py --show <file>
"""

import hashlib
import os
import re
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
# The list lives OUTSIDE this repository and always will -- a .gitignore entry is one mistake
# away from failing and a client name cannot be rotated once published. Resolution order:
# LEAKAGE_LIST_PATH (CI supplies it as a secret), then LT_PRIVATE_DIR, then the sibling
# private folder. The copy of this scanner that still sits in that folder finds it one level
# up, so both locations work and neither hardcodes a path.
_PRIV = os.environ.get(
    "LT_PRIVATE_DIR",
    os.path.join(HERE, "..", "..", "legal-translation-private"))
DEFAULT_LIST = (os.path.join(HERE, "..", "leakage-names.txt")
                if os.path.exists(os.path.join(HERE, "..", "leakage-names.txt"))
                else os.path.join(_PRIV, "leakage-names.txt"))


def P(s=""):
    sys.stdout.write(str(s).encode("ascii", "replace").decode("ascii") + "\n")


def load_patterns():
    path = os.environ.get("LEAKAGE_LIST_PATH", DEFAULT_LIST)
    if not os.path.exists(path):
        return None, path, []
    pats, bad = [], []
    for raw in open(path, encoding="utf-8").read().splitlines():
        s = raw.strip()
        if not s or s.startswith("#"):
            continue
        try:
            pats.append((s, re.compile(s, re.IGNORECASE)))
        except re.error as e:
            bad.append((s[:20] + "...", str(e)))
    return pats, path, bad


def _scan_lines(lines, pats, show, hits, where=""):
    """Match every pattern against every line, appending to `hits`. `where` names the member."""
    for n, line in enumerate(lines, 1):
        for i, (src, rx) in enumerate(pats):
            m = rx.search(line)
            if m:
                token = m.group(0)
                hits.append({
                    "line": n,
                    "member": where,
                    "pattern_index": i,
                    "matched_sha": hashlib.sha256(token.encode()).hexdigest()[:10],
                    "matched": token if show else None,
                })


def scan(path, pats, show):
    """Scan a file. IF IT IS A ZIP CONTAINER, SCAN ITS MEMBERS INSTEAD OF ITS BYTES.

    FINDING I-21, fixed 2026-09-02. This function read the file's bytes, and a `.docx` is a ZIP
    whose XML parts are DEFLATE-compressed -- so it reported CLEAN on a document containing any
    number of real names, and the blindness was invisible to anyone reasoning from the
    filename. **Measured both ways with a live pattern planted and never printed
    (`temp/probe_leak_docx.py`): NOT detected in a real DEFLATE document and reported clean;
    DETECTED, exit 1, in a byte-identical STORED ZIP.** So the limit was COMPRESSION, not the
    extension, which is why widening a filename check would not have fixed it.

    THE FIX IS THE CLASS, NOT THE EXTENSION. It tests whether the file IS a ZIP rather than
    whether it is named `.docx`, so `.xlsx`, `.pptx`, `.zip` and the project's own `.skill`
    archive -- which is the DELIVERABLE -- are all covered by the same three lines. A byte
    scanner is blind to every container; a member scanner is blind to none of them.

    A member that is itself unreadable is REPORTED, never skipped in silence: the whole point
    of the finding is that a control must say what it could not reach.
    """
    hits = []
    if zipfile.is_zipfile(path):
        try:
            with zipfile.ZipFile(path) as z:
                names = z.namelist()
                for name in names:
                    try:
                        raw = z.read(name)
                    except Exception as e:
                        hits.append({"line": 0, "member": name, "pattern_index": -1,
                                     "matched_sha": "UNREADABLE", "matched": repr(e)})
                        continue
                    _scan_lines(raw.decode("utf-8", errors="replace").splitlines(),
                                pats, show, hits, where=name)
        except Exception as e:
            return None, "container unreadable (%r)" % e, 0
        return hits, None, len(names)
    try:
        lines = open(path, encoding="utf-8", errors="replace").read().splitlines()
    except Exception as e:
        return None, "unreadable (%r)" % e, 0
    _scan_lines(lines, pats, show, hits)
    return hits, None, 0


def main():
    show = "--show" in sys.argv
    targets = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not targets:
        P(__doc__.strip())
        return 2

    pats, listpath, bad = load_patterns()
    if pats is None:
        P("CONTROL VOID: pattern list not found at %s" % listpath)
        P("A control that cannot load its list has not run. Fix this before committing.")
        return 2

    P("LEAKAGE SCAN")
    P("=" * 74)
    P("pattern list : %s" % os.path.normpath(listpath))
    P("patterns     : %d live%s" % (len(pats), (", %d FAILED TO COMPILE" % len(bad)) if bad else ""))
    for b in bad:
        P("   [!] uncompilable pattern (%s) -- it has never matched anything: %s" % (b[1], b[0]))
    P("")

    total = 0
    containers = 0
    for t in targets:
        hits, err, members = scan(t, pats, show)
        if err:
            P("  %-46s %s" % (os.path.basename(t), err))
            continue
        # SAY WHEN A CONTAINER WAS OPENED, because that is the whole of finding I-21: the same
        # word "clean" used to cover a file whose contents had never been read. A reader must
        # be able to tell the two apart from the output alone.
        tag = " (%d member(s) read)" % members if members else ""
        if members:
            containers += 1
        if not hits:
            P("  %-46s clean%s" % (os.path.basename(t), tag))
            continue
        total += len(hits)
        P("  %-46s %d HIT(S)%s" % (os.path.basename(t), len(hits), tag))
        for h in hits:
            loc = ("%s:%d" % (h.get("member"), h["line"])) if h.get("member") else \
                  ("line %d" % h["line"])
            if h["pattern_index"] < 0:
                P("     %-28s UNREADABLE MEMBER -- not scanned: %s" % (loc, h["matched"]))
            elif show:
                P("     %-28s pattern #%-3d  %r" % (loc, h["pattern_index"], h["matched"]))
            else:
                P("     %-28s pattern #%-3d  sha=%s  (text withheld; --show to reveal)"
                  % (loc, h["pattern_index"], h["matched_sha"]))

    P("")
    P("=" * 74)
    if bad:
        P("WARNING: %d pattern(s) did not compile and therefore protect nothing." % len(bad))
    if total:
        P("%d hit(s). Judge each against CLAUDE.md > Confidentiality before committing." % total)
        P("A hit is not automatically a leak -- short patterns match ordinary foreign-language")
        P("legal vocabulary. But every one needs a human decision, not a skim.")
        return 1
    P("CLEAN -- no pattern matched.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
