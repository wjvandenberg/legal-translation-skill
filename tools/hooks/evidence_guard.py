# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""PreToolUse HOOK — stop a shell command from printing evidence-folder FILENAMES.

THE INCIDENT. On 2026-08-11 a session ran `ls` and `find` over the sibling logs folder to
learn its layout, and the output printed real corpus filenames carrying counterparty and
personal names into the conversation transcript. Nothing was committed and nothing could be:
the leak never touched a file.

WHY A HOOK AND NOT A RULE. Every other confidentiality control in this project reads
COMMITTED CONTENT -- leakage_scan, publication_check, descriptor_shape_sweep, the pre-commit
gate. This leak reached the TRANSCRIPT, and CLAUDE.md 6.5 states plainly that session
metadata is reachable by neither the scanners nor the location rule. There is no
after-the-fact control, so the control has to run BEFORE the command does. And the written
rule already existed -- 6.5's "any glob over an evidence folder must be explicit about which
files it expects" -- and was read the same morning and broken anyway. That is the project's
own standing argument, from 5.1, that prose is not a control and only an artefact is.

WHAT IT BLOCKS. A command that (1) names a configured evidence folder AND (2) runs a
name-EMITTING utility -- ls, dir, find, tree, Get-ChildItem and friends -- or smuggles the
same thing through inline `-c` code.

WHAT IT DELIBERATELY ALLOWS, because the hazard is OUTPUT, not access:
  * `uv run python tools/gate_replay.py`         — reads those logs, prints counts only
  * `uv run python ../legal-translation-private/tools/audit_register.py`
                                                  — prescribed by CLAUDE.md 5.12 itself
  * `uv run python tools/evidence_ls.py <path>`  — the sanctioned way to see a folder's shape
A block with no alternative gets worked around, and then you have a control nobody believes.

THE LIMIT, STATED RATHER THAN HIDDEN. Two evidence folders are named here because their
names are already public in this repository (tools/gate_replay.py defaults to one of them).
The TEST-DOCUMENT folder's name is not, and must not be committed, so it is read from
`.claude/evidence-dirs.local` or `$LEGAL_TRANSLATION_EVIDENCE_DIRS` -- the same shape as
leakage_scan.py, where the scanner ships and the list never does. Consequence: in a fresh
clone with no local file, that third folder is unguarded. Better to say so than to imply
cover this does not have.

Exit codes: 0 = allow · 2 = BLOCK (message on stderr, shown to the model and the user).
"""
import json
import os
import re
import sys
from pathlib import Path

# Public already: tools/gate_replay.py carries the first as a default path, and CLAUDE.md
# 5.12 prescribes a command inside the second. Naming them here reveals nothing new.
DEFAULT_DIRS = ["legal-translation-logs", "legal-translation-private"]

# Utilities whose whole job is to emit names. `cat`/`head`/`tail`/`Get-Content` are here too:
# they emit CONTENT, which is strictly worse than a name.
NAME_EMITTING = r"""ls|dir|find|tree|du|stat|file|basename|realpath|readlink|
                    cat|head|tail|less|more|type|strings|
                    Get-ChildItem|gci|Get-Item|gi|Get-Content|gc|Resolve-Path"""
NAME_EMITTING_RE = re.compile(
    r"^\s*(?:sudo\s+)?(?:" + NAME_EMITTING.replace("\n", "").replace(" ", "") + r")\b",
    re.IGNORECASE)

# Inline code is the obvious way round a first-token check.
INLINE_CODE = re.compile(r"-c\s*['\"]|<<\s*['\"]?\w*EOF|python\s+-c", re.IGNORECASE)
LISTING_CALL = re.compile(
    r"\b(?:listdir|scandir|iterdir|rglob|glob|walk|Get-ChildItem|readdir)\b", re.IGNORECASE)


def evidence_dirs():
    dirs = list(DEFAULT_DIRS)
    env = os.environ.get("LEGAL_TRANSLATION_EVIDENCE_DIRS", "")
    dirs += [d.strip() for d in env.split(",") if d.strip()]
    local = Path(os.environ.get("CLAUDE_PROJECT_DIR", ".")) / ".claude" / "evidence-dirs.local"
    try:
        if local.exists():
            dirs += [ln.strip() for ln in local.read_text(encoding="utf-8").splitlines()
                     if ln.strip() and not ln.lstrip().startswith("#")]
    except OSError:
        pass
    return [d for d in dict.fromkeys(dirs)]


def segments(cmd):
    """Split a command line into pipeline / sequence segments, so `x | find ...` is seen."""
    return [s for s in re.split(r"\|\||&&|[|;&\n]", cmd) if s.strip()]


def main():
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0                                   # never break the session on bad input

    tool = data.get("tool_name", "")
    if tool not in ("Bash", "PowerShell", ""):
        return 0
    cmd = (data.get("tool_input") or {}).get("command", "")
    if not cmd:
        return 0

    dirs = evidence_dirs()
    hit = next((d for d in dirs if d.lower() in cmd.lower()), None)
    if not hit:
        return 0

    offender = None
    for seg in segments(cmd):
        if NAME_EMITTING_RE.match(seg):
            offender = NAME_EMITTING_RE.match(seg).group(0).strip()
            break
    if offender is None and INLINE_CODE.search(cmd) and LISTING_CALL.search(cmd):
        offender = "inline code that enumerates a directory"
    if offender is None:
        return 0

    print(
        "\n".join([
            "BLOCKED — this command would print evidence-folder filenames.",
            "",
            f"  folder  : {hit}",
            f"  command : {offender}",
            "",
            "Those filenames carry counterparty and personal names. This output would go",
            "into the conversation transcript, which no scanner in this project can reach",
            "(CLAUDE.md 6.5) and which cannot be un-said. Reading the folder is fine;",
            "PRINTING WHAT IS IN IT is not.",
            "",
            "Do this instead:",
            "  uv run python tools/evidence_ls.py <path>     # shape, counts, no names",
            "",
            "Or read it from a script whose output policy you have checked — see",
            "tools/gate_replay.py, which reads these logs and prints counts only.",
            "",
            "If you genuinely need one specific file, name it explicitly rather than",
            "globbing: CLAUDE.md 6.5 — 'any glob over an evidence folder must be explicit",
            "about which files it expects.'",
        ]),
        file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
