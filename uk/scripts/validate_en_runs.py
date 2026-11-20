"""Pre-apply gate: BLOCK if a detected definitions section in
paragraphs.json has any paragraph without `en_runs`.

Auto-invoked by apply_translations_textmatch.py before the main
translation step. Operators don't run this directly; the subprocess
call from apply produces the BLOCK message and exit code.

It also BLOCKS, on EVERY paragraph and not only the definitions section, when
a paragraph's `en_runs` do not TILE its `en`: integer offsets, in list order,
the first span starting at 0, each starting where the one before ended, the
last ending at len(en). Apply writes only what a span covers, so a gap drops
text and an overlap doubles it, with apply exiting 0 (register C13). No flag
waives it: --allow-bold-loss excuses missing emphasis, never wrong offsets.

And it BLOCKS a span whose optional `source_run` (sub-step 17.4: the position,
counted from 0, of the source run in the entry's `runs` whose properties the
span carries) is not a whole number or names no run of that entry. A span
without the key is not read for it, and no flag waives it either.

Usage:
    python validate_en_runs.py <paragraphs.json> [--allow-bold-loss]

Exit codes:
    0 — PASS (every en_runs tiles its en; no definitions section, or all
        paragraphs in it have en_runs)
    1 — WARN (--allow-bold-loss passed; missing en_runs ignored)
    2 — BLOCK (en_runs that do not tile en, or a malformed source_run,
        whatever the flag; or missing en_runs without override)
"""
import argparse
import json
import os
import sys

def _check_self_integrity():
    """Rev29: detect install-time truncation"""
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


def tiling_violations(paras):
    """[(idx, reason)] for every paragraph whose `en_runs` do not tile `en`.

    Measured against the RAW authored `en`, the string apply measures its own
    out-of-range refusal against (F16) -- the offsets index what the operator
    wrote. One reason per paragraph, the first that applies; offsets only,
    never the paragraph's text.
    """
    out = []
    for i, p in enumerate(paras):
        if not isinstance(p, dict) or not p.get('en_runs'):
            continue
        idx = p.get('idx', i)
        runs = p['en_runs']
        en = p.get('en') if isinstance(p.get('en'), str) else ''
        n = len(en)
        if not isinstance(runs, list):
            out.append((idx, 'en_runs is not a list of spans'))
            continue
        spans, why = [], None
        for k, s in enumerate(runs):
            if not isinstance(s, dict):
                why = f'span {k} is not an object'
                break
            a, b = s.get('start'), s.get('end')
            # A bool is an int to Python and is never an offset.
            if type(a) is not int or type(b) is not int:
                why = (f'span {k} has a non-integer offset (start is '
                       f'{type(a).__name__}, end is {type(b).__name__})')
                break
            if a < 0 or b < a or b > n:
                why = f'span {k} is out of range (start={a}, end={b}, len(en)={n})'
                break
            spans.append((a, b))
        if why is None and spans != sorted(spans):
            why = 'the spans are not in order'
        if why is None and spans[0][0] != 0:
            why = f'the first span starts at {spans[0][0]}, not 0'
        if why is None:
            for k in range(1, len(spans)):
                prev_end, start = spans[k - 1][1], spans[k][0]
                if start != prev_end:
                    kind = 'gap' if start > prev_end else 'overlap'
                    why = (f'{kind}: span {k - 1} ends at {prev_end} and span {k} '
                           f'starts at {start}')
                    break
        if why is None and spans[-1][1] != n:
            why = f'the last span ends at {spans[-1][1]}, but len(en) is {n}'
        if why is not None:
            out.append((idx, why))
    return out


def source_run_violations(paras):
    """SUB-STEP 17.4: [(idx, reason)] for every paragraph carrying a span whose
    optional `source_run` is malformed - not a whole number, below 0, or naming
    no run of the entry's own `runs`. The key names the source run whose
    properties the span carries on apply's regular path; a span without it, or
    with it null, is not read here. One reason per paragraph, the first that
    applies; positions only, never the paragraph's text.
    """
    out = []
    for i, p in enumerate(paras):
        if not isinstance(p, dict) or not isinstance(p.get('en_runs'), list):
            continue
        idx = p.get('idx', i)
        listed = p.get('runs')
        n = len(listed) if isinstance(listed, list) else 0
        for k, s in enumerate(p['en_runs']):
            if not isinstance(s, dict) or s.get('source_run') is None:
                continue
            v = s['source_run']
            # A bool is an int to Python and is never a position.
            if type(v) is not int:
                out.append((idx, f'span {k} names source_run as {type(v).__name__}, '
                                 f'not a whole number'))
                break
            if v < 0 or v >= n:
                out.append((idx, f'span {k} names source_run {v}, but the entry lists '
                                 f'{n} source run(s), counted from 0'))
                break
    return out


def _sibling_integrity_exit(name, exc):
    """A sibling module this script imports is missing or cut short: a broken install, which SKILL.md rule 6
    answers by re-installing. So the banner and the exit 3 this script prints for its OWN truncation - never a
    raw traceback and exit 1, and never a gate's costume. Only ImportError (deleted, or cut before the names it
    is asked for) and SyntaxError (cut mid-statement) arrive here: a broader class would dress a real defect as
    a broken install - and an ImportError about some OTHER module, raised inside the sibling, is that sibling's
    defect, so it is raised as it is."""
    if isinstance(exc, ImportError) and exc.name not in (None, os.path.splitext(name)[0]):
        raise exc
    bar = "=" * 60
    for line in ("", bar, "[skill] FILE INTEGRITY CHECK FAILED — script truncated.",
                 f"  File: {os.path.join(os.path.dirname(os.path.abspath(__file__)), name)}",
                 f"  Needed by: {os.path.basename(__file__)} ({type(exc).__name__}: {exc})",
                 "  Re-install the skill from the .skill / .zip archive.", bar, ""):
        print(line, file=sys.stderr)
    sys.exit(3)


def main():
    parser = argparse.ArgumentParser(
        description='Pre-apply gate: BLOCK if a detected definitions section '
                    'has paragraphs without en_runs.')
    parser.add_argument('paragraphs_json', help='Path to paragraphs.json')
    parser.add_argument('--allow-bold-loss', action='store_true',
                        help='Bypass the gate. Use only when bold loss is '
                             'genuinely acceptable (e.g., simple drafts).')
    args = parser.parse_args()

    # NO .pyc INSIDE A SHIPPED TREE (register I-18's family): the guard precedes the sibling import.
    sys.dont_write_bytecode = True
    scripts_dir = os.path.dirname(os.path.abspath(__file__))
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)
    try:
        from reorder_definitions import find_definitions_section_in_texts, declared_sections
    except (ImportError, SyntaxError) as exc:  # deleted, or cut short: a broken install, SKILL.md rule 6
        _sibling_integrity_exit('reorder_definitions.py', exc)

    with open(args.paragraphs_json, 'r', encoding='utf-8') as f:
        paras = json.load(f)

    # C13: every paragraph carrying en_runs, before and independent of the
    # definitions-section presence test below, and never waived by its flag.
    bad = tiling_violations(paras)
    if bad:
        print(
            "\n" + "=" * 60 + "\n"
            f"[validate_en_runs] SKILL GATE FIRED — INTENTIONAL BLOCK, NOT A SCRIPT ERROR.\n"
            f"The script is working as designed. The skill is enforcing a rule;\n"
            f"read the explanation below, fix paragraphs.json, then re-run apply.\n"
            f"Do NOT work around this by patching the script or skipping gates —\n"
            f"doing so silently ships output below the quality the skill is\n"
            f"designed to deliver.\n"
            + "=" * 60 + "\n"
            f"[validate_en_runs] BLOCK — en_runs that do not tile en.\n"
            f"\n"
            f"{len(bad)} paragraph(s) carry en_runs whose spans do not cover `en`\n"
            f"exactly. Apply writes only what a span covers, so a gap DROPS text\n"
            f"and an overlap DOUBLES it — silently, with apply exiting 0.\n"
            f"\n"
            + "".join(f"  idx {idx}: {why}\n" for idx, why in bad)
            + f"\n"
            f"FIX: re-derive every span of each paragraph above against the `en`\n"
            f"you now have — whole-number offsets, in order, the first starting\n"
            f"at 0, each starting where the one before ended, the last ending at\n"
            f"len(en). Do NOT delete en_runs to get past this: on a definitions\n"
            f"paragraph that loses the defined term's emphasis.\n"
            f"\n"
            f"--allow-bold-loss does NOT waive this: it excuses missing emphasis,\n"
            f"never offsets that point at the wrong characters.\n"
            + "=" * 60 + "\n",
            file=sys.stderr,
        )
        return 2

    # SUB-STEP 17.4: a malformed `source_run`, on every paragraph, never waived by the flag.
    bad = source_run_violations(paras)
    if bad:
        print(
            "\n" + "=" * 60 + "\n"
            f"[validate_en_runs] SKILL GATE FIRED — INTENTIONAL BLOCK, NOT A SCRIPT ERROR.\n"
            f"[validate_en_runs] BLOCK — a malformed source_run on an en_runs span.\n"
            f"\n"
            f"A span may name the source run whose properties it carries, as\n"
            f"\"source_run\": the position of that run in the entry's `runs`,\n"
            f"counted from 0. These do not name one:\n"
            f"\n"
            + "".join(f"  idx {idx}: {why}\n" for idx, why in bad)
            + f"\n"
            f"FIX: give each such span the position of the run whose properties\n"
            f"it carries, or leave the key out, then re-run apply.\n"
            f"--allow-bold-loss does NOT waive this.\n"
            + "=" * 60 + "\n",
            file=sys.stderr,
        )
        return 2

    # Prefer en text; fall back to source text for untranslated paragraphs.
    texts = []
    for p in paras:
        en = (p.get('en') or '').strip()
        src = (p.get('text') or '').strip()
        texts.append(en if en else src)

    # SUB-STEP 16.6: a section the operator DECLARED ("role": "definition", read by
    # reorder_definitions.declared_sections, the one reader) is checked in place of the
    # detector's answer; a malformed declaration is refused here, before apply.
    sections, problems = declared_sections(paras)
    problems += [f"declared idx {e - 1} is past the notes' {len(paras)} entries"
                 for _s, e in sections if e > len(paras)]
    if problems:
        print(
            "\n" + "=" * 60 + "\n"
            f"[validate_en_runs] SKILL GATE FIRED — INTENTIONAL BLOCK, NOT A SCRIPT ERROR.\n"
            f"[validate_en_runs] BLOCK — a malformed definitions declaration.\n"
            + "".join(f"  {why}\n" for why in problems)
            + f"FIX: correct the declaration in paragraphs.json, then re-run apply.\n"
            + "=" * 60 + "\n",
            file=sys.stderr,
        )
        return 2
    if sections:
        by_idx = {p.get('idx', i): p for i, p in enumerate(paras) if isinstance(p, dict)}
        span = [i for s, e in sections for i in range(s, e)]
        start, end, size = sections[0][0], sections[-1][1], len(span)
        found = (f"declared in paragraphs.json (\"role\": \"definition\")\n"
                 f"at paragraphs " + ", ".join(f"{s}-{e - 1}" for s, e in sections) + ".")
        missing = [i for i in span if i in by_idx and (by_idx[i].get('en') or '').strip()
                   and not by_idx[i].get('en_runs')]
    else:
        start, end = find_definitions_section_in_texts(texts)
        if start is None:
            return 0
        size = end - start
        found = (f"detected at paragraphs {start}-{end - 1}\n"
                 f"by the heading + predicate-cluster pattern.")

        missing = []
        for i in range(start, end):
            if i >= len(paras):
                break
            p = paras[i]
            en_runs = p.get('en_runs')
            if not en_runs:
                missing.append(p.get('idx', i))

    if not missing:
        return 0

    if args.allow_bold_loss:
        print(
            "\n" + "=" * 60 + "\n"
            f"[validate_en_runs] WARNING — definitions section at paragraphs "
            f"{start}-{end - 1} has {len(missing)} entries without "
            f"en_runs.\n"
            f"--allow-bold-loss was passed; proceeding anyway. Bold/italic\n"
            f"on defined terms will be missing in the output.\n"
            f"Affected indices: {missing[:20]}"
            + (f" ... +{len(missing) - 20} more" if len(missing) > 20 else "")
            + "\n" + "=" * 60 + "\n",
            file=sys.stderr,
        )
        return 1

    print(
        "\n" + "=" * 60 + "\n"
        f"[validate_en_runs] SKILL GATE FIRED — INTENTIONAL BLOCK, NOT A SCRIPT ERROR.\n"
        f"The script is working as designed. The skill is enforcing a rule;\n"
        f"read the explanation below, fix paragraphs.json, then re-run apply.\n"
        f"Do NOT work around this by patching the script or skipping gates —\n"
        f"doing so silently ships output below the quality the skill is\n"
        f"designed to deliver.\n"
        + "=" * 60 + "\n"
        f"[validate_en_runs] BLOCK — definitions section detected without en_runs.\n"
        f"\n"
        f"A definitions section was {found} {len(missing)} of the\n"
        f"{size} paragraphs in the section lack `en_runs`.\n"
        f"\n"
        f"Without en_runs on each definition paragraph, apply emits\n"
        f'<w:b w:val="0"/> to prevent style-bold from leaking into body\n'
        f"text — and that off-override strips the style-provided bold-italic\n"
        f"that defines the term in this document family. The defined terms\n"
        f"will render plain in the output. Re-author paragraphs.json to\n"
        f"include en_runs for every paragraph in the section, e.g.:\n"
        f"\n"
        f'  "en_runs": [\n'
        f'    {{"start": 0,           "end": <term_end>, '
        f'"bold": true,  "italic": true}},\n'
        f'    {{"start": <term_end>, "end": <text_len>, '
        f'"bold": false, "italic": false}}\n'
        f"  ]\n"
        f"\n"
        f"Affected paragraph indices ({len(missing)}):\n"
        f"  {missing[:30]}"
        + (f"\n  ... +{len(missing) - 30} more" if len(missing) > 30 else "")
        + "\n"
        f"\n"
        f"To override (only when bold loss is genuinely acceptable), pass\n"
        f"--allow-bold-loss to apply_translations_textmatch.py.\n"
        + "=" * 60 + "\n",
        file=sys.stderr,
    )
    return 2

if __name__ == '__main__':
    # C29: a character the console cannot show prints as an escape, never as a crash.
    for _stream in (sys.stdout, sys.stderr):
        try:
            _stream.reconfigure(errors='backslashreplace')
        except (AttributeError, ValueError):
            pass
    _check_self_integrity()
    sys.exit(main())

# === SKILL FILE COMPLETE ===
