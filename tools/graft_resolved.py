"""graft_resolved.py - SUB-STEP 16.2 (PLAN-2-step-b.md section 3.16): the frozen notes given today's `resolved`,
AT LOAD TIME, IN MEMORY.

Step 15 taught extraction to write, on a run whose formatting in force differs from its `bold` and `italic`, one
sparse key, `resolved`. The frozen notes of the July runs predate it, and step 16 changes apply to READ it - so a
corpus arm that hands apply the July notes would measure the new apply on notes that lack what it reads. Wouter's
answer (6) of 2026-11-12: graft it at load time, from today's extraction of the matched source, NOTHING WRITTEN
INTO THE ARCHIVE.

So this takes a workdir's notes and its matched source and returns the notes with `resolved` copied in, run by run,
from today's extraction - and REFUSES, with GraftVoid, wherever the two do not describe the same paragraphs:

  * the same idx on both sides, each exactly once, and no idx on one side only;
  * the same `text` at each idx;
  * the same runs at each idx, each run compared as the WHOLE entry with `resolved` set aside - measured
    2026-11-16 over the 13 frozen workdirs, both trees: 1,891 of 1,891 entries and 5,999 of 5,999 runs equal
    that way, so the strictest reading costs nothing;
  * a frozen run already carrying `resolved` must carry exactly today's.

A refusal is VOID, never a pass and never a quiet fall-back to the ungrafted notes: a caller that ran the notes
ungrafted would answer a different question and report it as this one. Its reason names idx values and key names,
NEVER a value - a run's text is client text (charter section 5.6).

WHAT IT WRITES: nothing outside a folder it creates under the system temp folder and removes. The frozen list it
is given is never mutated; the archive is read and never written. Where no run gains the key, the notes' OWN bytes
come back unchanged, so a workdir with nothing to graft is byte-identical to the July file; otherwise the grafted
list is serialised in extraction's own format (`ensure_ascii=False, indent=1`).

    from graft_resolved import graft_notes_bytes, GraftVoid
    data, stats = graft_notes_bytes(wd / "paragraphs.json", source_docx, ROOT / "uk" / "scripts")
"""
import copy
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

EXTRACT = "extract_paragraphs.py"
ENV = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1", PYTHONDONTWRITEBYTECODE="1")


class GraftVoid(Exception):
    """The notes and today's extraction do not describe the same paragraphs - or today's extraction could not
    be read. The message names idx values and key names only."""


def _bare(run):
    """A run entry with `resolved` set aside - what alignment compares."""
    return {k: v for k, v in run.items() if k != "resolved"} if isinstance(run, dict) else run


def fresh_notes(source, scripts_dir, timeout=900):
    """Today's extraction of `source`, by the tree's own script, into a folder this creates and removes. Its output
    is captured and discarded - it can quote the document."""
    tmp = Path(tempfile.mkdtemp(prefix="graft-resolved-"))
    try:
        out = tmp / "notes.json"
        try:
            r = subprocess.run(["uv", "run", "--with", "lxml", "python", str(Path(scripts_dir) / EXTRACT),
                                str(source), str(out)], capture_output=True, text=True, encoding="utf-8",
                               errors="replace", env=ENV, timeout=timeout)
        except (subprocess.TimeoutExpired, OSError) as exc:
            raise GraftVoid(f"today's extraction did not run to its end ({type(exc).__name__})") from None
        if r.returncode != 0 or not out.is_file():
            raise GraftVoid(f"today's extraction exited {r.returncode} and "
                            f"{'wrote notes' if out.is_file() else 'wrote no notes'}")
        try:
            fresh = json.loads(out.read_text(encoding="utf-8"))
        except ValueError as exc:
            raise GraftVoid(f"today's extraction wrote notes that do not parse ({type(exc).__name__})") from None
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    if not isinstance(fresh, list):
        raise GraftVoid("today's extraction wrote notes that are not a list")
    return fresh


def _by_idx(entries, side):
    out = {}
    for e in entries:
        k = e.get("idx")
        if k in out:
            raise GraftVoid(f"idx {k} appears more than once in the {side} notes")
        out[k] = e
    return out


def graft(notes, fresh):
    """(grafted copy of `notes`, stats). Raises GraftVoid wherever the two do not align."""
    if not isinstance(notes, list):
        raise GraftVoid("the frozen notes are not a list")
    frozen = [e for e in notes if isinstance(e, dict)]
    today = [e for e in fresh if isinstance(e, dict)]
    fz, fr = _by_idx(frozen, "frozen"), _by_idx(today, "today's")
    only_frozen, only_today = sorted(set(fz) - set(fr), key=str), sorted(set(fr) - set(fz), key=str)
    if only_frozen or only_today:
        raise GraftVoid(f"the entries differ: {len(only_frozen)} idx only in the frozen notes "
                        f"{only_frozen[:5]}, {len(only_today)} only in today's {only_today[:5]}")
    out = copy.deepcopy(notes)
    runs = grafted = already = 0
    for e in out:
        if not isinstance(e, dict):
            continue
        k = e.get("idx")
        f = fr[k]
        if (e.get("text") or "") != (f.get("text") or ""):
            raise GraftVoid(f"idx {k}: the text differs")
        er, frr = e.get("runs") or [], f.get("runs") or []
        if len(er) != len(frr):
            raise GraftVoid(f"idx {k}: {len(er)} frozen run(s), {len(frr)} today")
        for n, (a, b) in enumerate(zip(er, frr)):
            if not isinstance(a, dict) or not isinstance(b, dict):
                raise GraftVoid(f"idx {k}, run {n}: not a run entry")
            if _bare(a) != _bare(b):
                keys = sorted(x for x in set(_bare(a)) | set(_bare(b)) if a.get(x) != b.get(x))
                raise GraftVoid(f"idx {k}, run {n}: the run differs in {keys}")
            runs += 1
            if "resolved" in a:
                if a["resolved"] != b.get("resolved"):
                    raise GraftVoid(f"idx {k}, run {n}: the frozen run's resolved is not today's")
                already += 1
            elif "resolved" in b:
                a["resolved"] = copy.deepcopy(b["resolved"])
                grafted += 1
    return out, {"entries": len(frozen), "aligned": len(frozen), "runs": runs, "grafted": grafted,
                 "already": already}


def graft_notes_bytes(notes_path, source, scripts_dir):
    """(bytes to hand the pipeline in place of `notes_path`, stats). The file's OWN bytes where no run gains the
    key; extraction's format otherwise. Reads `notes_path` and never writes it."""
    raw = Path(notes_path).read_bytes()
    try:
        notes = json.loads(raw.decode("utf-8"))
    except ValueError as exc:
        raise GraftVoid(f"the frozen notes do not parse ({type(exc).__name__})") from None
    grafted, stats = graft(notes, fresh_notes(source, scripts_dir))
    if not stats["grafted"]:
        return raw, stats
    return json.dumps(grafted, ensure_ascii=False, indent=1).encode("utf-8"), stats


def carried(path):
    """How many runs in the notes file at `path` carry `resolved` - the READ-BACK each arm takes after the pipeline
    ran, so a graft computed and never handed over is caught: today's apply ignores the key, so the delivered bytes
    alone could never show it. None where the file is absent or does not parse."""
    try:
        notes = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return sum(1 for e in notes if isinstance(e, dict) for r in (e.get("runs") or [])
               if isinstance(r, dict) and "resolved" in r)


def describe(stats):
    """One line, counts only."""
    return (f"graft: {stats['aligned']} of {stats['entries']} entries aligned, {stats['runs']} runs, "
            f"{stats['grafted']} given resolved, {stats['already']} already carrying it")
