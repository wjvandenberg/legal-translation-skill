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


def scan(path, pats, show):
    hits = []
    try:
        lines = open(path, encoding="utf-8", errors="replace").read().splitlines()
    except Exception as e:
        return None, "unreadable (%r)" % e
    for n, line in enumerate(lines, 1):
        for i, (src, rx) in enumerate(pats):
            m = rx.search(line)
            if m:
                token = m.group(0)
                hits.append({
                    "line": n,
                    "pattern_index": i,
                    "matched_sha": hashlib.sha256(token.encode()).hexdigest()[:10],
                    "matched": token if show else None,
                })
    return hits, None


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
    for t in targets:
        hits, err = scan(t, pats, show)
        if err:
            P("  %-46s %s" % (os.path.basename(t), err))
            continue
        if not hits:
            P("  %-46s clean" % os.path.basename(t))
            continue
        total += len(hits)
        P("  %-46s %d HIT(S)" % (os.path.basename(t), len(hits)))
        for h in hits:
            if show:
                P("     line %-6d pattern #%-3d  %r" % (h["line"], h["pattern_index"], h["matched"]))
            else:
                P("     line %-6d pattern #%-3d  sha=%s  (text withheld; --show to reveal)"
                  % (h["line"], h["pattern_index"], h["matched_sha"]))

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
