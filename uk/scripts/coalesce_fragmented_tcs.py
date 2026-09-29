#!/usr/bin/env python3
"""Detect character-fragmented tracked-change clusters in paragraphs.json and
scaffold the en_segments array for the translator.

Problem
-------
Civil-law concept drafts sometimes edit a single word or ordinal letter by
letter, producing a tc_segments array with many character-level splits that
map to one conceptual edit in English. Because English normally replaces the
whole word (not character ranges), the segment-aware translator cannot cleanly
map source character segments onto English without orphan letters leaking into
the redline view.

Canonical example (Spanish road-use draft):
  Source clause heading changed from "Duodécima" to "Decimotercera".
  OOXML stores 7 interleaved runs for that one edit:
    [ins "D"], [del "Duod"], [ins "e"], [del "é"],
    [regular "cim"], [ins "otercera"], [del "a"],
    [regular ".- Legislación, Fuero y jurisdicción"]
  The intended English edit is a simple 2-token replacement:
    del = "Clause 12"   ins = "Clause 13"
  plus the untouched trailing ".- Legislación…" → ". Governing law…"

What this script does
---------------------
For each paragraph with `has_track_changes: true`, it scans `tc_segments`
looking for contiguous clusters of ins/del/regular entries that (a) contain at
least 3 pieces and at least one ins and one del, (b) have no whitespace in any
piece, and (c) reassemble on each of the Accept and Reject sides into a
coherent single word (different on each side). A piece is an ins or a del, or
regular text glued LETTER TO LETTER to one — inside the run, or the stem of the
neighbouring regular segment up to its whitespace, which then joins the word
(C14: a renumbered ordinal whose unchanged half sits in a regular run). A
junction between two CJK characters never counts: those scripts put no space
between words. Every run prints how many tracked-change paragraphs it examined
and how many it scaffolded.

When a cluster is found, the script writes a pre-filled `en_segments` skeleton
into the paragraph, matching the original tc_segments type pattern 1-for-1
(because the XML still has those runs). Inside the detected cluster it places:

  - on the **first `ins` segment**: a placeholder like
        `<<TRANSLATE: ins='Decimotercera' (accepted)>>`
  - on the **first `del` segment**: a placeholder like
        `<<TRANSLATE: del='Duodécima' (rejected)>>`
  - on **every other cluster segment**: the empty string `""`.
  - on a **neighbouring regular segment holding a stem** of the edited word:
        `<<TRANSLATE: regular='<segment text>' (its '<stem>' belongs to the
        edited word, written whole on the ins/del: write this segment's
        English without it)>>`

Outside the cluster, the script leaves `en` fields empty (so the translator
still writes them) — but each tc_segment that carries non-cluster text is
exposed in the skeleton so the translator sees the whole paragraph at once.

The translator then replaces the `<<TRANSLATE: …>>` placeholders with the
final English (`"Clause 13"` / `"Clause 12"`) and fills the remaining empty
`en` fields for non-cluster segments. The empty strings inside the cluster
carry through to apply time, where `apply_translations_textmatch.py` clears
the matching XML runs (v2024+ empty-string behaviour), producing a clean
Accept/Reject redline.

Structural fields that the script does NOT touch: `text`, `deleted_text`,
`tc_segments`, `has_track_changes`. Any existing `en_segments` is overwritten
only if the script actually detects a cluster; paragraphs without clusters
are untouched entirely.

Usage
-----
    python coalesce_fragmented_tcs.py <paragraphs.json> [--dry-run]
                                                        [--min-pieces N]

Run AFTER extract_paragraphs.py (Step 2) and BEFORE translation (Step 4).
Idempotent; re-running replaces the scaffolding on the same clusters and is a
no-op on paragraphs that have no fragmented clusters.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import os
import unicodedata

def _check_self_integrity():
    """Detect install-time truncation. Whole-file scan tolerates null-padding."""
    try:
        with open(os.path.abspath(__file__), 'r', encoding='utf-8') as f:
            content = f.read()
    except OSError:
        return
    if '\n# === SKILL FILE COMPLETE ===' not in content:
        msg = (
            "\n" + "=" * 60 + "\n"
            "[skill] FILE INTEGRITY CHECK FAILED — script truncated.\n"
            f"  File: {os.path.abspath(__file__)}\n"
            f"  Size: {len(content):,} bytes (sentinel marker missing).\n"
            "  Re-install the skill from the .skill / .zip archive.\n"
            + "=" * 60 + "\n"
        )
        print(msg, file=sys.stderr)
        sys.exit(3)


_check_self_integrity()



PLACEHOLDER_PREFIX = "<<TRANSLATE: "

def _is_wordlike(s: str) -> bool:
    """True if s is a single 'word-like' token: no internal whitespace, at
    least one alphabetic character, plausibly a single edited token."""
    if not s or len(s) > 80:
        return False
    stripped = s.strip()
    if not stripped or re.search(r"\s", stripped):
        return False
    if not re.search(r"[^\W\d_]", stripped, flags=re.UNICODE):
        return False
    return True

def _is_cjk(ch: str) -> bool:
    name = unicodedata.name(ch, "")
    return any(k in name for k in ("CJK", "HIRAGANA", "KATAKANA", "HANGUL"))


def _glued(before: str, after: str) -> bool:
    """True when the character `before` meets `after` LETTER TO LETTER, so the
    edit changes part of a word rather than a whole one. A junction between two
    CJK characters never counts: those scripts put no whitespace between words,
    so every junction there is letter to letter and none says a word was split."""
    if not (before.isalpha() and after.isalpha()):
        return False
    return not (_is_cjk(before) or _is_cjk(after))


def _find_cluster_detail(tc_segments: list[dict], min_pieces: int) -> list[dict]:
    """Every fragmented cluster, as {start, end, pre, post, accepted, rejected}.

    A cluster is a maximal run of adjacent segments whose individual texts
    have no whitespace, and whose concatenations by side (Accept = non-del,
    Reject = non-ins) both read as coherent single words — different from
    each other — and which contains at least `min_pieces` pieces with at least
    one ins and one del.

    A PIECE is an ins or a del, AND (C14) a stretch of regular text glued
    letter to letter to an ins or del: a regular segment inside the run, or the
    STEM of the neighbouring whitespace-bearing regular segment — its letters up
    to the nearest whitespace — which then joins both words. That is how a
    renumbered ordinal whose unchanged half sits in a regular run (`ins 'Duo'` /
    `del 'Un'` / regular `'décima.- …'`) reaches the threshold with two edits.
    `pre` and `post` are those stems ('' where there is none). A run the rule
    without stems would flag is never lost to them: where the stems break the
    single-word test, the cluster is kept without them."""
    clusters: list[dict] = []
    n = len(tc_segments)
    txt = [(s.get("text") or "") for s in tc_segments]
    typ = [s.get("type") for s in tc_segments]
    edit = ("ins", "del")
    i = 0
    while i < n:
        if re.search(r"\s", txt[i]) or len(txt[i]) > 60:
            i += 1
            continue
        j = i
        while j < n and not re.search(r"\s", txt[j]) and len(txt[j]) <= 60:
            j += 1
        ins_count = sum(1 for k in range(i, j) if typ[k] == "ins")
        del_count = sum(1 for k in range(i, j) if typ[k] == "del")
        if ins_count and del_count:
            glued_in = 0
            for k in range(i, j):
                if typ[k] in edit or not txt[k]:
                    continue
                left = (k - 1 >= i and typ[k - 1] in edit and txt[k - 1]
                        and _glued(txt[k - 1][-1], txt[k][0]))
                right = (k + 1 < j and typ[k + 1] in edit and txt[k + 1]
                         and _glued(txt[k][-1], txt[k + 1][0]))
                if left or right:
                    glued_in += 1
            pre = post = ""
            if (i > 0 and typ[i - 1] not in edit and txt[i - 1] and txt[i]
                    and typ[i] in edit and _glued(txt[i - 1][-1], txt[i][0])):
                m = re.search(r"\S+$", txt[i - 1])
                pre = m.group(0) if m else ""
            if (j < n and typ[j] not in edit and txt[j] and txt[j - 1]
                    and typ[j - 1] in edit and _glued(txt[j - 1][-1], txt[j][0])):
                m = re.match(r"\S+", txt[j])
                post = m.group(0) if m else ""
            core_acc = "".join(txt[k] for k in range(i, j) if typ[k] != "del")
            core_rej = "".join(txt[k] for k in range(i, j) if typ[k] != "ins")
            pieces = ins_count + del_count + glued_in + bool(pre) + bool(post)
            accepted, rejected = pre + core_acc + post, pre + core_rej + post
            found = None
            if (pieces >= min_pieces and _is_wordlike(accepted)
                    and _is_wordlike(rejected) and accepted != rejected):
                found = {"pre": pre, "post": post,
                         "accepted": accepted, "rejected": rejected}
            elif (j - i >= 2 and ins_count + del_count >= min_pieces
                  and _is_wordlike(core_acc) and _is_wordlike(core_rej)
                  and core_acc != core_rej):
                found = {"pre": "", "post": "",
                         "accepted": core_acc, "rejected": core_rej}
            if found is not None:
                clusters.append(dict(found, start=i, end=j - 1))
                i = j
                continue
        i = j if j > i else i + 1
    return clusters


def _find_clusters(tc_segments: list[dict], min_pieces: int) -> list[tuple[int, int]]:
    """Return (start_idx, end_idx_inclusive) ranges of fragmented clusters —
    `_find_cluster_detail`'s, without the stems."""
    return [(c["start"], c["end"])
            for c in _find_cluster_detail(tc_segments, min_pieces)]

def _build_en_segments_skeleton(tc_segments: list[dict],
                                clusters: list,
                                direct_ins_en: str | None = None,
                                direct_del_en: str | None = None) -> list[dict]:
    """Generate an en_segments array of the SAME length and type pattern as
    tc_segments, populated with:
      - '' (empty) for cluster segments other than the first ins / first del
      - on the first ins / first del of each cluster: either a TRANSLATE
        placeholder (default) or, if direct_ins_en/direct_del_en are given
        AND there is exactly ONE cluster, the final English text directly.
      - on a neighbouring regular segment whose STEM belongs to the edited
        word (C14): a TRANSLATE placeholder naming that stem, because the
        word is written whole on the ins / del and the rest of the segment
        is still the translator's to fill.
      - '' (empty) for every other non-cluster segment (translator fills these)

    `clusters` holds `_find_cluster_detail` dicts, or (start, end) pairs,
    which carry no stems.
    """
    en_segs: list[dict] = [
        {"type": s.get("type"), "en": ""} for s in tc_segments
    ]

    direct_fill = (
        direct_ins_en is not None
        and direct_del_en is not None
        and len(clusters) == 1
    )

    stems: dict[int, list[str]] = {}
    for c in clusters:
        if isinstance(c, dict):
            start, end = c["start"], c["end"]
            accepted, rejected = c["accepted"], c["rejected"]
            if c.get("pre"):
                stems.setdefault(start - 1, []).append(c["pre"])
            if c.get("post"):
                stems.setdefault(end + 1, []).append(c["post"])
        else:
            start, end = c
            accepted = "".join((tc_segments[k].get("text") or "")
                               for k in range(start, end + 1)
                               if tc_segments[k].get("type") != "del")
            rejected = "".join((tc_segments[k].get("text") or "")
                               for k in range(start, end + 1)
                               if tc_segments[k].get("type") != "ins")
        first_ins = next(
            (k for k in range(start, end + 1)
             if tc_segments[k].get("type") == "ins"),
            None,
        )
        first_del = next(
            (k for k in range(start, end + 1)
             if tc_segments[k].get("type") == "del"),
            None,
        )
        if first_ins is not None:
            if direct_fill:
                en_segs[first_ins]["en"] = direct_ins_en
            else:
                en_segs[first_ins]["en"] = (
                    f"{PLACEHOLDER_PREFIX}ins='{accepted}' (accepted)>>"
                )
        if first_del is not None:
            if direct_fill:
                en_segs[first_del]["en"] = direct_del_en
            else:
                en_segs[first_del]["en"] = (
                    f"{PLACEHOLDER_PREFIX}del='{rejected}' (rejected)>>"
                )
        # All other cluster segments keep en='' so apply will clear the
        # corresponding runs. This is the whole point.

    for k, found in sorted(stems.items()):
        named = " and ".join(f"'{s}'" for s in found)
        en_segs[k]["en"] = (
            f"{PLACEHOLDER_PREFIX}regular='{tc_segments[k].get('text') or ''}' "
            f"(its {named} belongs to the edited word, written whole on the "
            f"ins/del: write this segment's English without it)>>"
        )

    return en_segs

def process_paragraph(p: dict, min_pieces: int,
                      report: list[str],
                      direct_ins_en: str | None = None,
                      direct_del_en: str | None = None) -> bool:
    if not p.get("has_track_changes"):
        return False
    tcs = p.get("tc_segments")
    if not tcs or not isinstance(tcs, list):
        return False
    clusters = _find_cluster_detail(tcs, min_pieces)
    if not clusters:
        return False
    skeleton = _build_en_segments_skeleton(
        tcs, clusters,
        direct_ins_en=direct_ins_en,
        direct_del_en=direct_del_en,
    )
    p["en_segments"] = skeleton
    for c in clusters:
        start, end = c["start"], c["end"]
        stem = "".join(
            f" + stem in segment {k}" for k, s in ((start - 1, c["pre"]), (end + 1, c["post"])) if s)
        report.append(
            f"  idx={p.get('idx')}: fragmented cluster segments[{start}..{end}]{stem} "
            f"=> rejected='{c['rejected']}' / accepted='{c['accepted']}'"
        )
    return True

def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(
        description="Detect character-fragmented TC clusters and scaffold en_segments."
    )
    ap.add_argument("paragraphs_json")
    ap.add_argument("--dry-run", action="store_true",
                    help="Report without modifying the file.")
    ap.add_argument("--min-pieces", type=int, default=3,
                    help="Minimum ins+del count per cluster (default: 3).")
    # Direct-fill shortcut for whole-word clusters (the only scenario observed
    # in practice: clause renumbering like "Duodécima" → "Decimotercera").
    # When --idx/--ins-en/--del-en are all passed, the script writes the final
    # English directly into the scaffold instead of a TRANSLATE placeholder.
    # Requires --idx so the fill only touches a single, unambiguous cluster.
    ap.add_argument("--idx", type=int, default=None,
                    help="Paragraph idx to target for direct --ins-en/--del-en fill. "
                         "Required when --ins-en or --del-en is used.")
    ap.add_argument("--ins-en", default=None,
                    help="English text for the accepted (ins) side of a whole-word "
                         "cluster. Requires --idx and --del-en.")
    ap.add_argument("--del-en", default=None,
                    help="English text for the rejected (del) side of a whole-word "
                         "cluster. Requires --idx and --ins-en.")
    args = ap.parse_args(argv)

    # Validate direct-fill usage.
    _direct_flags = [args.ins_en, args.del_en]
    if any(f is not None for f in _direct_flags):
        if args.idx is None:
            ap.error("--ins-en/--del-en require --idx <paragraph_idx>.")
        if any(f is None for f in _direct_flags):
            ap.error("--ins-en and --del-en must be used together.")

    try:
        with open(args.paragraphs_json, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        print(f"ERROR reading {args.paragraphs_json}: {e}", file=sys.stderr)
        return 2

    report: list[str] = []
    touched = 0
    examined = 0
    direct_applied = False
    for p in data:
        if (p.get("has_track_changes") and isinstance(p.get("tc_segments"), list)
                and p.get("tc_segments")):
            examined += 1
        # Route direct-fill args only to the targeted paragraph idx. Every
        # other paragraph still gets the placeholder scaffold.
        if (args.idx is not None and args.ins_en is not None
                and p.get("idx") == args.idx):
            tcs = p.get("tc_segments") or []
            clusters = _find_clusters(tcs, args.min_pieces)
            if len(clusters) != 1:
                print(
                    f"ERROR: --idx={args.idx} has {len(clusters)} fragmented "
                    f"cluster(s); --ins-en/--del-en only supports paragraphs with "
                    f"exactly one cluster. Use placeholder mode (omit --ins-en/--del-en).",
                    file=sys.stderr,
                )
                return 2
            if process_paragraph(p, args.min_pieces, report,
                                 direct_ins_en=args.ins_en,
                                 direct_del_en=args.del_en):
                touched += 1
                direct_applied = True
            continue
        if process_paragraph(p, args.min_pieces, report):
            touched += 1

    if args.idx is not None and args.ins_en is not None and not direct_applied:
        print(
            f"ERROR: --idx={args.idx} did not match any fragmented-cluster "
            "paragraph (no ins/del cluster detected at that idx).",
            file=sys.stderr,
        )
        return 2

    # C14: on EVERY run, so a count of one cluster can be read against how
    # many tracked-change paragraphs there were to look at.
    print(f"Examined {examined} tracked-change paragraph(s); scaffolded {touched}.")

    if not report:
        print("No character-fragmented TC clusters detected. Nothing to do.")
        return 0

    print(f"Detected fragmented clusters in {touched} paragraph(s):")
    for line in report:
        print(line)

    print()
    print("Scaffolded en_segments on each flagged paragraph. At translation time:")
    print(f"  1. Replace each '{PLACEHOLDER_PREFIX}…>>' placeholder with the final English")
    print("     (e.g. 'Clause 13' on the ins side, 'Clause 12' on the del side).")
    print("  2. Fill the remaining empty 'en' fields for non-cluster segments with")
    print("     normal English translations — but do NOT populate the empty-string")
    print("     slots inside the cluster; those must stay as '' so apply_translations_")
    print("     textmatch.py can clear the matching source runs.")
    print(f"  3. A '{PLACEHOLDER_PREFIX}regular=…>>' placeholder names a stem that belongs")
    print("     to the edited word: replace it with that segment's English WITHOUT the")
    print("     stem, which the ins/del English already carries.")

    if args.dry_run:
        print()
        print("(--dry-run: no file written)")
        return 0

    with open(args.paragraphs_json, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print()
    print(f"Wrote scaffolded JSON to {args.paragraphs_json}")
    return 0

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

# === SKILL FILE COMPLETE ===
