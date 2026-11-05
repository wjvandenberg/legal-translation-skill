# -*- coding: utf-8 -*-
"""SKILL STEP 3'S READ RECEIPT, FILED AS AN OPERATOR FILES IT — for every suite and corpus tool that runs apply.

Since sub-step 14.9.5 (register C26) `apply_translations_textmatch.py` refuses to start without a matching
`lexicon_read_receipt.json` beside paragraphs.json, so anything that runs apply end to end files one first. This is
the one place that does it, and it does it the operator's way: the receipt is issued through the tree's own
`lexicon_compliance.py --read-receipt`, and each line it names is then copied from its file. Nothing here builds a
receipt by hand, so a change to the receipt's format reaches every caller through the real command.

The set it names is the least the script accepts: `references/general-legal.md`, and for a declared language the
skill supports, that language's `<language>-general-legal.md`. Call it AFTER Step 1c's declaration is written -
a receipt issued before another language is declared is refused, as it should be.

A tree whose `lexicon_compliance.py` predates the receipt (an old copy a before-and-after arm runs) needs none,
and gets none: `file_receipt` returns None. A tree that has the receipt but cannot issue one raises.

    from read_receipt import file_receipt
    file_receipt(notes_path, tree_dir)              # before every apply run

Synthetic or frozen workdirs only, and always a COPY: the receipt is written beside the notes.
"""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

RECEIPT = "lexicon_read_receipt.json"
MODE = "--read-receipt"
_ENV = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1", PYTHONDONTWRITEBYTECODE="1")


def lines_of(path):
    """A lexicon's lines as the receipt numbers them: split on LF, a CR before it dropped, 1-based by index + 1."""
    return Path(path).read_bytes().decode("utf-8-sig").replace("\r\n", "\n").split("\n")


def minimum_set(notes, tree):
    files = ["references/general-legal.md"]
    try:
        decl = json.loads((Path(notes).parent / "source_language.json").read_bytes().decode("utf-8-sig"))
        lang = str(decl.get("source_language", "")).strip().lower()
    except (OSError, ValueError, AttributeError):
        lang = ""
    sub = f"sub-lexicons/{lang}-general-legal.md"
    if lang and (Path(tree) / sub).is_file():
        files.append(sub)
    return files


def has_receipt(tree):
    script = Path(tree) / "scripts" / "lexicon_compliance.py"
    return script.is_file() and MODE in script.read_text(encoding="utf-8", errors="replace")


def issue(notes, tree, files):
    """Run the tree's own issuing command; (exit code, its output)."""
    r = subprocess.run([sys.executable, str(Path(tree) / "scripts" / "lexicon_compliance.py"), str(notes), MODE,
                        *files], capture_output=True, text=True, encoding="utf-8", errors="replace", env=_ENV,
                       timeout=300)
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def quote_all(notes, tree):
    """Copy each line the receipt names from its file into its quote, as an operator does."""
    rp = Path(notes).parent / RECEIPT
    data = json.loads(rp.read_bytes().decode("utf-8"))
    for e in data["lines"]:
        e["quote"] = lines_of(Path(tree) / e["file"])[e["line"] - 1]
    rp.write_bytes(json.dumps(data, ensure_ascii=False, indent=1).encode("utf-8"))
    return rp


def lexicons_beside(scripts_copy, tree):
    """A copied scripts folder (a before-and-after arm's) gets the tree's lexicons beside it, so an apply there that
    checks the receipt finds the files it was issued for - the check reads them from its own skill folder."""
    parent = Path(scripts_copy).parent
    for name in ("references", "sub-lexicons"):
        if not (parent / name).exists():
            shutil.copytree(Path(tree) / name, parent / name)


def file_receipt(notes, tree, files=None):
    """Issue the receipt beside `notes` through `tree`'s own script and quote every line. Returns its path, or None
    for a tree whose script predates the receipt."""
    tree = Path(tree)
    if not has_receipt(tree):
        return None
    rc, out = issue(notes, tree, files or minimum_set(notes, tree))
    if rc != 0:
        raise RuntimeError(f"read receipt not issued (exit {rc}): {out.strip()[-400:]}")
    return quote_all(notes, tree)
