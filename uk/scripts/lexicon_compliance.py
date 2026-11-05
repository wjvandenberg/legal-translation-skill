#!/usr/bin/env python3
"""
lexicon_compliance.py — scan a translation JSON or document.xml for forbidden
calque phrases and hard-rule terminology violations drawn from the reference
lexicons' "Avoid" columns and the language sub-lexicons.

Exits with code 0 if the input is clean, non-zero (and prints each offending
location) if any forbidden phrase is found.

Usage:
    # Scan paragraphs.json BEFORE applying translations (Step 4d)
    python scripts/lexicon_compliance.py paragraphs.json --stage pre-apply

    # Scan the translated document.xml AFTER post-processing (Step 8d, pre-repack);
    # --notes names the paragraphs.json the Step 1c declaration sits beside
    python scripts/lexicon_compliance.py final/word/document.xml --stage pre-repack --notes paragraphs.json

    # The source language is the one DECLARED at Step 1c (source_language.json beside
    # paragraphs.json). Nothing declared, the scan guesses, and says NOT SUPPORTED, never
    # PASSED; a declared language the skill does not support runs every language's rules,
    # as an unknown language always has, and says NOT SUPPORTED too.

    # Skill Step 3, after the read: name each lexicon read; it names the lines to quote into
    # lexicon_read_receipt.json, beside paragraphs.json
    python scripts/lexicon_compliance.py paragraphs.json --read-receipt references/general-legal.md sub-lexicons/italian-general-legal.md

    # Skill Step 5: apply runs this FIRST, and does not start unless the receipt matches
    python scripts/lexicon_compliance.py paragraphs.json --check-read-receipt

    # Disable source-language hints (use only the language-agnostic ruleset)
    python scripts/lexicon_compliance.py paragraphs.json --language none

    # Restrict to a specific source language (narrows language-specific rules)
    python scripts/lexicon_compliance.py paragraphs.json --language dutch

The script is intentionally conservative: it only flags phrases that are
explicitly listed in a reference lexicon's "Avoid" column, or that have been
documented (with a real example) as a calque by previous translations produced
by this skill. False positives on bona fide correct usages are kept rare by
using word-boundary-aware regex and, where needed, negative look-behind /
context checks.

Exit codes:
    0 — clean
    1 — violations found (script prints each, then exits 1); a read receipt
        not issued, or not matching
    2 — I/O error or bad invocation
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import secrets
import sys
import unicodedata
from pathlib import Path
from typing import Iterable, List, Optional, Tuple

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

# THE DECLARED SOURCE LANGUAGE (branch 12 slice 12a) is read through the one shared
# reader in source_language_markers.py, beside this script.
# NO .pyc INSIDE A SHIPPED TREE: the guard must precede the sibling import (register
# I-18's family; tests/test_no_bytecode_in_tree.py discovers the importers).
sys.dont_write_bytecode = True
_SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)


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


try:
    from source_language_markers import (  # noqa: E402
        LANGUAGE_MARKERS,
        not_supported,
        read_declared_language,
        resolve_source_language,
    )
except (ImportError, SyntaxError) as _exc:  # deleted, or cut short: a broken install, SKILL.md rule 6
    _sibling_integrity_exit('source_language_markers.py', _exc)


# --------------------------------------------------------------------------
# Rule table
# --------------------------------------------------------------------------
#
# Each rule is:
#   (severity, pattern, message, applies_to_languages)
#
# severity: "BLOCK" (exit 1) or "WARN" (printed but does not fail).
# pattern:  Python regex. Case-insensitive by default; escape \b for word
#           boundaries. Keep patterns *narrow* — the Avoid column of the
#           lexicon is authoritative.
# message:  Short human-readable explanation including the correct rendering.
# applies_to_languages:
#           List of source languages for which this rule applies, OR
#           ["*"] for language-agnostic rules derived from the English
#           reference lexicons.
#
# Adding a new rule: it must be traceable to a specific lexicon line
# (English reference or language sub-lexicon Avoid column). Do not add
# rules based on personal preference — only documented guidance.

Rule = Tuple[str, "re.Pattern[str]", str, List[str]]

def _c(pat: str) -> "re.Pattern[str]":
    return re.compile(pat, re.IGNORECASE)

# THE LEGISLATION TAIL the 'Article N' warning below stays quiet on (register G2, G8 and G14;
# sub-step 14.4). The look-ahead once read a bare 'of the' as legislation, so 'Article 7 of the
# Agreement' was silent where 'of this Agreement' warned (G14), while a decree with no 'the'
# (G2) and a citation with a paragraph between the number and the code (G8) warned on every
# civil-law statute. Now the tail must END on a head noun naming an outside instrument, after
# 'the', 'that' or 'those' and at most three naming words, none of them a connective, 'the', a
# pronoun or an inward pointer -- so an internal reference warns whatever stands before it, and
# the tail cannot bridge from 'the Agreement and' or 'the Agreement that' to a code. A naming
# word may be a year ('the 1998 Act') or a dotted abbreviation, but never end on a full stop, so
# the tail cannot cross a sentence. Between the number and the tail may sit the shapes measured
# on the corpus: a -bis suffix, a paragraph or letter, a list of further articles.
_ART_ORDINAL = r"(?:first|second|third|fourth|fifth|sixth|seventh|eighth|ninth|tenth|last|\d+(?:st|nd|rd|th))"
_ART_ITEM = r"(?:\d+[a-z]?|\(?[a-z]\))"
_ART_SUFFIX = r"(?:\s*-?\s*(?:bis|ter|quater|quinquies|sexies|septies|octies|novies|decies)\b)?"
_ART_SUBDIV = (r"(?:\s*,?\s*(?:" + _ART_ORDINAL + r"\s+(?:sub-?)?paragraph|(?:sub-?)?paragraphs?\s+" + _ART_ITEM
               + r"|letters?\s+" + _ART_ITEM + r")(?:\s*(?:,|and|or)\s*" + _ART_ITEM + r")*)*")
_ART_NUMBER = r"\d+(?:\.\d+)*" + _ART_SUFFIX + _ART_SUBDIV
_ART_LIST = (r"(?:\s*,?\s*(?:and|or)\s+(?:Articles?\s+)?" + _ART_NUMBER
             + r"(?:\s*(?:,|and|or)\s*" + _ART_NUMBER + r")*)*")
_ART_GAP = _ART_SUFFIX + _ART_SUBDIV + _ART_LIST + r"\s*,?\s*"
_ART_HEAD = (r"(?:Codes?|Acts?|Treat(?:y|ies)|Regulations?|Directives?|Constitution|Decrees?(?:-Laws?)?|Laws?"
             r"|Resolutions?|Statutes?|Conventions?|Charter(?!\s*-?\s*part)|Ordinances?|Rules"
             r"|Articles\s+of\s+Association|By-?laws|GDPR|TFEU|TEU"
             r"|D\.\s*Lgs|D\.\s*P\.\s*C\.\s*M|D\.\s*P\.\s*R|D\.\s*M|D\.\s*L)\b")
_ART_STOP = (r"(?:and|or|nor|but|to|of|in|on|at|by|for|with|from|under|between|as|than|which|that|this|these|those"
             r"|the|its|their|his|her|our|present|hereof|herein|hereto|hereunder|thereof|above|below)\b")
_ART_TAIL = (r"of\s+(?:(?:the|that|those)\s+)?(?:(?!" + _ART_STOP + r")[^\W_][\w'’-]*(?:(?:\.[\w'’-]+)+\.?)?\s+)"
             r"{0,3}" + _ART_HEAD)

RULES: List[Rule] = [
    # ------ Language-agnostic (from references/general-legal.md) ------
    ("BLOCK", _c(r"\bthe present (?:agreement|contract|deed)\b"),
     "'the present agreement/contract/deed' is a civil-law calque. Use 'this Agreement' / 'this Contract' / 'this Deed' (general-legal.md).",
     ["*"]),
    ("BLOCK", _c(r"\bthis present (?:agreement|contract|deed)\b"),
     "'this present agreement' is a calque (often from NL 'deze onderhavige overeenkomst'). Use 'this Agreement' (general-legal.md; dutch-general-legal.md).",
     ["*"]),
    ("BLOCK", _c(r"\bauthenticating signature\b"),
     "'authenticating signature' is a calque (HU 'hitelesítő aláírás'). Use 'signature' or 'authorised signatory' (general-legal.md).",
     ["*"]),
    ("BLOCK", _c(r"\brepresentative acting on behalf of the\b"),
     "Verbose calque. Use 'authorised representative' (general-legal.md).",
     ["*"]),
    ("BLOCK", _c(r"\bduly invested with (?:the )?(?:necessary )?powers?\b"),
     "'duly invested with powers' is a civil-law calque. Use 'duly authorised' (general-legal.md).",
     ["*"]),
    ("BLOCK", _c(r"\bendowed with (?:the )?necessary powers?\b"),
     "Civil-law calque. Use 'duly authorised' (general-legal.md).",
     ["*"]),
    ("BLOCK", _c(r"\bon the basis of and pursuant to\b"),
     "Redundant stacking. Use 'pursuant to' (general-legal.md).",
     ["*"]),
    ("BLOCK", _c(r"\bbearing the date of\b"),
     "Verbose calque. Use '[Title], dated [date]' (general-legal.md).",
     ["*"]),
    ("BLOCK", _c(r"\bin the name and on behalf of\b"),
     "Stacked calque. Use 'on behalf of' unless the 'in the name of' distinction is intentional (general-legal.md).",
     ["*"]),
    ("BLOCK", _c(r"\b(?:plants|receivables|assets) existing and future\b"),
     "Civil-law adjective-after-noun word order. Use 'existing and future plants/receivables/assets' (general-legal.md).",
     ["*"]),
    ("BLOCK", _c(r"\bapplicant organisation:\s*$"),
     "Verbose on a cover page. Drop 'organisation' when the entity name makes it obvious (general-legal.md).",
     ["*"]),
    ("BLOCK", _c(r"\bfor the grant application entitled\b"),
     "Vague indirect phrasing on cover pages. Use 'Application under Call [ref]' (general-legal.md).",
     ["*"]),

    # UK signature-block label — this is a HARD RULE in general-legal.md
    # so we flag the alternatives. We only match them *when they look like
    # a signature-block label* (colon at end-of-line or followed by capitalised name).
    ("BLOCK", _c(r"(?m)^\s*(?:Position|Function|Capacity|Role)\s*:\s*[A-Z]"),
     "English signature-block label is 'Title:', never 'Position/Function/Capacity/Role:'. Re-label (general-legal.md).",
     ["*"]),

    # Headings — internal refs must be 'Clause', 'Article' is for legislation
    # Too easy to false-positive; only warn.
    # Flag 'Article N' only when it clearly is NOT a statutory/regulatory
    # reference: statutory refs include colons (civil-code style 'Article 2:24b'),
    # or are followed by a legislation tail (_ART_TAIL above), 'of Book', 'BW', etc.
    ("WARN", _c(r"\bArticle\s+\d+(?:\.\d+)*\b"
                r"(?![\:\.]\d)"
                r"(?!" + _ART_GAP + r"(?:" + _ART_TAIL
                + r"|of Book|BW|of Directive|of Regulation|of the EU|of the European|of Law))"),
     "'Article N' for an internal reference is non-standard in UK legal drafting — prefer 'Clause N' unless this is a reference to legislation (general-legal.md).",
     ["*"]),

    # Date format under UK variant — we do not hard-block here (US output is supported).

    # ------ Dutch-specific (from sub-lexicons/dutch-*.md) ------
    ("BLOCK", _c(r"\bframework conditions?\b"),
     "'framework conditions' is a Eurospeak calque (NL 'randvoorwaarden'). Use 'conditions' or 'parameters' (dutch-general-legal.md; dutch-corporate-ma-jv.md).",
     ["dutch"]),
    ("BLOCK", _c(r"\bin more concrete terms\b"),
     "'in more concrete terms' is a calque (NL 'concretiseren'). Use 'set out' / 'specify' / 'flesh out' (dutch-general-legal.md).",
     ["dutch"]),
    ("BLOCK", _c(r"\benvirons fund\b"),
     "'environs fund' is a calque (NL 'omgevingsfonds'). Use 'community fund' or 'local-impact fund' (dutch-energy-infrastructure.md).",
     ["dutch"]),
    ("BLOCK", _c(r"\bacceptance by the environs\b"),
     "'acceptance by the environs' is a calque (NL 'acceptatie door de omgeving'). Use 'acceptance by the local community' (dutch-energy-infrastructure.md).",
     ["dutch"]),
    ("BLOCK", _c(r"\bwind park\b"),
     "'Wind Park' is a calque (NL 'Windpark'). UK English is 'Wind Farm' (dutch-energy-infrastructure.md).",
     ["dutch"]),
    ("BLOCK", _c(r"\bsun park\b"),
     "Literal calque. Use 'Solar Farm' or 'PV plant' (dutch-energy-infrastructure.md).",
     ["dutch"]),
    ("BLOCK", _c(r"\bground rights\b"),
     "'ground rights' is a calque (NL 'grondrechten' in project context). Use 'land rights' (dutch-energy-infrastructure.md).",
     ["dutch"]),
    ("BLOCK", _c(r"\bground owners?\b"),
     "'ground owners' is a calque (NL 'grondeigenaren'). Use 'landowners' (dutch-energy-infrastructure.md).",
     ["dutch"]),
    ("BLOCK", _c(r"\bnet connection\b"),
     "'net connection' is a calque (NL 'netaansluiting'). Use 'grid connection' (dutch-energy-infrastructure.md).",
     ["dutch"]),
    ("BLOCK", _c(r"\bbehaviour code\b"),
     "'behaviour code' is a calque (NL 'gedragscode'). Use 'code of conduct' (dutch-energy-infrastructure.md).",
     ["dutch"]),
    ("BLOCK", _c(r"\bstriking shadow\b"),
     "'striking shadow' is a calque (NL 'slagschaduw'). Use 'shadow flicker' or 'flicker' (dutch-energy-infrastructure.md).",
     ["dutch"]),
    ("BLOCK", _c(r"\bsupport base\b"),
     "'support base' is a calque (NL 'draagvlak'). Use 'support' or 'public support' (dutch-energy-infrastructure.md).",
     ["dutch"]),
    ("BLOCK", _c(r"\blandscape insertion\b"),
     "'landscape insertion' is a calque (NL 'landschappelijke inpassing'). Use 'landscape integration' (dutch-energy-infrastructure.md).",
     ["dutch"]),
    ("BLOCK", _c(r"\bgroup society\b"),
     "'group society' is a calque (NL 'groepsmaatschappij'). Use 'group company' (dutch-corporate-ma-jv.md).",
     ["dutch"]),
    ("BLOCK", _c(r"\b(?:statutorily|legally) (?:established|domiciled) at\b"),
     "Calque. Use 'having its registered office at' (dutch-general-legal.md).",
     ["dutch"]),
    ("BLOCK", _c(r"\blegally validly represented\b"),
     "Calque (NL 'ten deze rechtsgeldig vertegenwoordigd'). Use 'duly represented' (dutch-general-legal.md).",
     ["dutch"]),
    ("BLOCK", _c(r"\bputting in default\b"),
     "Calque (NL 'ingebrekestelling'). Use 'notice of default' (dutch-general-legal.md).",
     ["dutch"]),
    ("BLOCK", _c(r"\bsuspensive conditions?\b"),
     "Civil-law calque (NL 'opschortende voorwaarden'). Use 'conditions precedent' (dutch-general-legal.md; general-legal.md).",
     ["dutch"]),
    ("BLOCK", _c(r"\bresolutive conditions?\b"),
     "Civil-law calque (NL 'ontbindende voorwaarden'). Use 'conditions subsequent' (dutch-general-legal.md).",
     ["dutch"]),
    ("BLOCK", _c(r"\bsolidarily liable\b"),
     "Civil-law calque (NL 'hoofdelijk aansprakelijk'). Use 'jointly and severally liable' (dutch-general-legal.md).",
     ["dutch"]),
    ("BLOCK", _c(r"\bintent or gross fault\b"),
     "Calque (NL 'opzet of grove schuld'). Use 'wilful misconduct or gross negligence' (dutch-general-legal.md).",
     ["dutch"]),
    ("BLOCK", _c(r"\bequivalent partner\b"),
     "Calque (NL 'gelijkwaardige partner'). Use 'equal partner' (dutch-corporate-ma-jv.md).",
     ["dutch"]),
    ("BLOCK", _c(r"\bconcurrent activities\b"),
     "False-friend calque (NL 'concurrerende activiteiten' = competing). Use 'competing activities' (dutch-corporate-ma-jv.md).",
     ["dutch"]),
    ("BLOCK", _c(r"\bapproach plan\b"),
     "Calque (NL 'Plan van Aanpak'). Use 'Plan of Action' / 'Action Plan' (dutch-corporate-ma-jv.md).",
     ["dutch"]),
    ("WARN", _c(r"\bcooperation on an equal footing\b"),
     "Acceptable UK rendering of 'samenwerking op basis van gelijkwaardigheid' — this is a positive marker, not a violation. Retained here only so that reviewers can confirm the term is used consistently.",
     ["dutch"]),

    # ------ Italian-specific placeholders (for future work) ------
    ("BLOCK", _c(r"\blegislative changes\b(?!\s+(?:and|or))"),
     "Likely calque (IT 'Mutamenti Legislativi'). Use 'Change in Law' (FIDIC/PF standard) (italian-*.md).",
     ["italian"]),
    ("BLOCK", _c(r"\bfinancing institutions?\b"),
     "Literal calque (IT 'Istituti Finanziatori'). Use 'Finance Parties' (PF standard) (italian-*.md).",
     ["italian"]),
    ("BLOCK", _c(r"\bpenalties for delay\b"),
     "Calque (IT 'penali per ritardo'). Use 'delay damages' / 'liquidated damages for delay' (energy-infrastructure.md).",
     ["italian"]),
    ("BLOCK", _c(r"\bdefinitive project\b"),
     "Calque (IT 'progetto definitivo'). Use 'detailed design' (Stage 2) (energy-infrastructure.md).",
     ["italian"]),
    ("BLOCK", _c(r"\bexecutive project\b"),
     "Calque (IT 'progetto esecutivo'). Use 'construction design' (Stage 3) (energy-infrastructure.md).",
     ["italian"]),

    # ------ Spanish-specific (from sub-lexicons/spanish-*.md) ------
    # The sub-lexicon already prescribes "Notices" for Comunicación / Notificaciones
    # section headings; this rule enforces that explicitly on clause-heading lines.
    ("BLOCK", _c(r"(?m)^\s*(?:Clause\s+\d+\.?\s+)?Notification\s*$"),
     "Clause heading 'Notification' must be 'Notices' per spanish-general-legal.md (Section Headings / Universal Legal Terms: 'ALWAYS Notices; never Notification, never Communication').",
     ["spanish"]),
    ("BLOCK", _c(r"(?m)^\s*(?:Clause\s+\d+\.?\s+)?Communication\s*$"),
     "Clause heading 'Communication' must be 'Notices' per spanish-general-legal.md.",
     ["spanish"]),

    # Ley Común Española — classic false friend. Spain is a civil-law jurisdiction;
    # "common law" in English denotes the English common-law tradition.
    ("BLOCK", _c(r"\bSpanish\s+common\s+law\b"),
     "False friend for 'Ley Común Española'. Use 'Spanish general law' or 'Spanish law' — Spain is civil-law, not common-law (spanish-general-legal.md: False Friends).",
     ["spanish"]),

    # EXPONEN — standard English heading is RECITALS, not RECITE.
    ("BLOCK", _c(r"(?m)^\s*RECITE\s*$"),
     "Spanish 'EXPONEN' as a section heading should be 'RECITALS', not 'RECITE' (spanish-general-legal.md: Section Headings).",
     ["spanish"]),

    # Closing-formula calque.
    ("BLOCK", _c(r"\bfor\s+a\s+single\s+effect\b"),
     "Calque of 'a un solo efecto'. Use 'as a single instrument' or 'in [N] original counterparts' (spanish-general-legal.md: Closing Formulae).",
     ["spanish"]),

    # Passive-stack calque — warn only, since a narrow active-voice variant may appear.
    ("WARN", _c(r"\bshall\s+be\s+endeavoured\s+to\s+be\b"),
     "Awkward passive stack. Prefer active voice — 'the Parties shall seek to' / 'shall endeavour to' (spanish-general-legal.md: Dispute-Resolution Formulae).",
     ["spanish"]),
]

# --------------------------------------------------------------------------
# I/O helpers
# --------------------------------------------------------------------------

_WT = re.compile(r"<w:t(?:\s[^>]*)?>([^<]*)</w:t>")
_WDT = re.compile(r"<w:delText(?:\s[^>]*)?>([^<]*)</w:delText>")

def _extract_from_json(path: str) -> List[Tuple[str, int, str]]:
    """Return list of (field_label, idx, text) from a paragraphs.json."""
    out: List[Tuple[str, int, str]] = []
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError(f"Expected a JSON array in {path}")
    for p in data:
        idx = p.get("idx", -1)
        en = p.get("en")
        if en:
            out.append(("en", idx, en))
        en_del = p.get("en_deleted")
        if en_del:
            out.append(("en_deleted", idx, en_del))
        for i, seg in enumerate(p.get("en_segments") or []):
            t = seg.get("en") if isinstance(seg, dict) else None
            if t:
                out.append((f"en_segments[{i}]:{seg.get('type','?')}", idx, t))
    return out

def _extract_from_xml(path: str) -> List[Tuple[str, int, str]]:
    """Return list of (field_label, seq, text) from a document.xml — treats
    w:t and w:delText content as separate streams so that a calque in
    deleted text is still surfaced."""
    with open(path, "r", encoding="utf-8") as f:
        xml = f.read()
    out: List[Tuple[str, int, str]] = []
    for seq, m in enumerate(_WT.finditer(xml)):
        t = m.group(1)
        if t.strip():
            out.append(("w:t", seq, t))
    for seq, m in enumerate(_WDT.finditer(xml)):
        t = m.group(1)
        if t.strip():
            out.append(("w:delText", seq, t))
    return out

def _extract(path: str) -> List[Tuple[str, int, str]]:
    if path.endswith(".json"):
        return _extract_from_json(path)
    if path.endswith(".xml"):
        return _extract_from_xml(path)
    # Allow docx too, for convenience
    if path.endswith(".docx"):
        import zipfile
        with zipfile.ZipFile(path) as z:
            with z.open("word/document.xml") as f:
                xml = f.read().decode("utf-8")
        out: List[Tuple[str, int, str]] = []
        for seq, m in enumerate(_WT.finditer(xml)):
            if m.group(1).strip():
                out.append(("w:t", seq, m.group(1)))
        for seq, m in enumerate(_WDT.finditer(xml)):
            if m.group(1).strip():
                out.append(("w:delText", seq, m.group(1)))
        return out
    raise ValueError(f"Unsupported input extension: {path}")

# --------------------------------------------------------------------------
# Scan
# --------------------------------------------------------------------------

def scan(entries: List[Tuple[str, int, str]], language: str) -> Tuple[List[str], List[str]]:
    """Return (blocking_messages, warning_messages)."""
    blocks: List[str] = []
    warns: List[str] = []
    lang = (language or "*").lower()
    for sev, pat, msg, langs in RULES:
        if "*" not in langs and lang not in langs and lang != "*":
            continue
        for field, idx, text in entries:
            m = pat.search(text)
            if not m:
                continue
            snippet = _ctx(text, m.start(), m.end())
            line = f"[{sev}] {field} idx={idx}: {msg}\n        …{snippet}…"
            if sev == "BLOCK":
                blocks.append(line)
            else:
                warns.append(line)
    return blocks, warns

def _ctx(text: str, a: int, b: int, radius: int = 40) -> str:
    s = max(0, a - radius)
    e = min(len(text), b + radius)
    chunk = text[s:e].replace("\n", " ")
    return chunk

# --------------------------------------------------------------------------
# The read receipt — skill Step 3, checked first at skill Step 5 (register C26)
# --------------------------------------------------------------------------
#
# Skill Step 3's end-to-end read of the lexicons left no trace, and no mechanism can prove a
# file was read rather than skimmed. So this asks for something the operator cannot predict
# (Wouter's design, 2026-11-02): after the read, --read-receipt names two random lines in each
# lexicon read, one in each half; the operator copies each into the receipt; and apply's first
# check, --check-read-receipt, refuses to start without a match. It proves the files were
# opened at those lines, not that every line was read, and says so - never more.

RECEIPT_FILE = 'lexicon_read_receipt.json'
_SKILL_DIR = os.path.dirname(_SCRIPTS_DIR)
_LEXICON_DIRS = ('references', 'sub-lexicons')
_GENERAL = 'references/general-legal.md'
_PROVES = 'It proves the files were opened at those lines, not that every line was read.'
_ISSUE = 'lexicon_compliance.py <workdir>/paragraphs.json --read-receipt <each lexicon read>'


def _receipt_path(notes: str) -> str:
    return os.path.join(os.path.dirname(os.path.abspath(notes)), RECEIPT_FILE)


def _lexicon(name: str) -> Optional[str]:
    """A lexicon's path in the skill folder - 'references/x.md' or 'sub-lexicons/x.md' - or
    None for anything else: a script, a folder, a path leaving the skill."""
    full = os.path.normpath(name if os.path.isabs(name) else os.path.join(_SKILL_DIR, name))
    try:
        rel = os.path.relpath(full, _SKILL_DIR).replace(os.sep, '/')
    except ValueError:  # another drive
        return None
    parts = rel.split('/')
    if len(parts) != 2 or parts[0] not in _LEXICON_DIRS or not parts[1].endswith('.md'):
        return None
    return rel


def _read_lines(rel: str) -> Tuple[bytes, List[str]]:
    """A lexicon's bytes, and its lines as an editor numbers them: split on LF, from 1."""
    with open(os.path.join(_SKILL_DIR, rel), 'rb') as fh:
        data = fh.read()
    return data, data.decode('utf-8-sig').replace('\r\n', '\n').split('\n')


def _same(quote: str, line: str) -> bool:
    """Equal once both are NFC, their runs of whitespace collapsed and their ends trimmed."""
    def norm(s):
        return ' '.join(unicodedata.normalize('NFC', s).split())
    return norm(quote) == norm(line)


def _required(notes: str) -> List[str]:
    """What every receipt covers: the general reference and, for a declared language the skill
    supports, that language's general sub-lexicon - the two skill Step 3 makes mandatory."""
    language, state, _why = read_declared_language(notes)
    return [_GENERAL] + ([f'sub-lexicons/{language}-general-legal.md'] if state == 'supported' else [])


def _seal(files: dict, lines: list) -> str:
    blob = json.dumps([sorted(files.items()), [[e['file'], e['line']] for e in lines]])
    return hashlib.sha256(blob.encode('utf-8')).hexdigest()


def issue_read_receipt(notes: str, names: List[str], rng=None) -> Tuple[int, List[str]]:
    """Skill Step 3, after the read: name two random lines in each lexicon read, one in each half
    of its lines holding three letters or more, and write the receipt beside paragraphs.json.
    (exit code, what to print). `rng` is a test's draw; in use it is the system's random
    source, and nothing the operator passes can set it. Issuing again replaces the receipt."""
    rng = rng or secrets.SystemRandom()
    files, problems = [], []
    for name in names:
        rel = _lexicon(name)
        if rel is None:
            problems.append(f'{name}: not a lexicon — name a file in references/ or sub-lexicons/ '
                            'by its path in the skill folder')
        elif not os.path.isfile(os.path.join(_SKILL_DIR, rel)):
            problems.append(f'{rel}: no such lexicon in this skill')
        elif rel not in files:
            files.append(rel)
    for rel in _required(notes):
        if rel not in files:
            problems.append(f'{rel}: skill Step 3 makes it mandatory for this document — read it '
                            'in full and name it too')
    if problems:
        return 1, problems
    hashes, lines = {}, []
    for rel in files:
        data, text = _read_lines(rel)
        hashes[rel] = hashlib.sha256(data).hexdigest()
        cands = [i + 1 for i, s in enumerate(text) if sum(c.isalpha() for c in s) >= 3]
        if not cands:
            return 1, [f'{rel}: holds no line to quote']
        half = len(cands) // 2
        for part in ((cands[:half], cands[half:]) if half else (cands,)):
            lines.append({'file': rel, 'line': rng.choice(part), 'quote': ''})
    receipt = {'what': 'skill Step 3 read receipt: copy each named line, exactly as it stands in '
                       'its file, into its quote',
               'files': hashes, 'lines': lines, 'seal': _seal(hashes, lines)}
    with open(_receipt_path(notes), 'w', encoding='utf-8', newline='\n') as fh:
        json.dump(receipt, fh, ensure_ascii=False, indent=1)
        fh.write('\n')
    return 0, [f'{e["file"]}  line {e["line"]}' for e in lines]


def check_read_receipt(notes: str) -> Tuple[int, List[str]]:
    """Apply's first check: (0, [the verdict]) when the receipt beside paragraphs.json matches,
    else (1, [each reason, with its fix]). A refusal names a file and a line, never the line's
    text, which would hand over the answer."""
    path = _receipt_path(notes)
    again = f'issue it again with `{_ISSUE}`'
    if not os.path.isfile(path):
        return 1, [f'no {RECEIPT_FILE} beside paragraphs.json. Skill Step 3 ends with it: read the '
                   f'lexicons in full, run `{_ISSUE}`, and copy each line it names into its quote '
                   '(skill-docs/03-lexicons-and-segments.md, rule 7).']
    try:
        with open(path, 'r', encoding='utf-8-sig') as fh:
            data = json.load(fh)
        files, lines, seal = data['files'], data['lines'], data['seal']
        well_formed = (isinstance(files, dict) and isinstance(lines, list) and bool(lines)
                       and all(isinstance(k, str) and isinstance(v, str) for k, v in files.items())
                       and all(isinstance(e, dict) and e.get('file') in files
                               and type(e.get('line')) is int and isinstance(e.get('quote'), str)
                               for e in lines))
    except (OSError, ValueError, KeyError, TypeError):
        well_formed = False
    if not well_formed:
        return 1, [f'{RECEIPT_FILE} cannot be read as a receipt — {again}.']
    if _seal(files, lines) != seal:
        return 1, [f'its named lines or files were edited after it was issued — {again}, and '
                   'never edit a line number or the file list.']
    problems = []
    for rel, digest in files.items():
        if _lexicon(rel) != rel or not os.path.isfile(os.path.join(_SKILL_DIR, rel)):
            problems.append(f'{rel}: no longer in this skill — {again} for the lexicons you read.')
        elif hashlib.sha256(_read_lines(rel)[0]).hexdigest() != digest:
            problems.append(f'{rel}: changed since the receipt was issued — read it again in '
                            f'full, then {again}.')
    for rel in _required(notes):
        if rel not in files:
            problems.append(f'{rel}: mandatory for this document and not covered, as when Step 1c '
                            f'declares another language — read it in full, then {again}, naming '
                            'every lexicon you read.')
    if problems:
        return 1, problems
    for e in lines:
        text = _read_lines(e['file'])[1]
        where = f'{e["file"]} line {e["line"]}'
        if not e['quote'].strip():
            problems.append(f'{where}: not quoted — open the file at that line and copy it into '
                            'its quote.')
        elif not 1 <= e['line'] <= len(text) or not _same(e['quote'], text[e['line'] - 1]):
            problems.append(f'{where}: the quote does not match that line — open the file at '
                            'that line and copy the line exactly as it stands.')
    if problems:
        return 1, problems
    return 0, [f'{len(lines)} line(s) in {len(files)} file(s) match. {_PROVES}']


def _receipt_main(args) -> int:
    """The two receipt modes. PATH is the paragraphs.json the receipt sits beside."""
    if not args.path.lower().endswith('.json'):
        print('lexicon_compliance: the read receipt sits beside paragraphs.json — name that as '
              f'PATH, not {args.path}', file=sys.stderr)
        return 2
    if args.check_read_receipt:
        code, said = check_read_receipt(args.path)
        if not code:
            print(f'Lexicon read receipt: {said[0]}')
            return 0
        print('Lexicon read receipt — REFUSED: skill Step 5 does not start without one that matches.')
    else:
        code, said = issue_read_receipt(args.path, args.read_receipt)
        if not code:
            print(f'Lexicon read receipt — skill Step 3: {len(said)} line(s), written to '
                  f'{_receipt_path(args.path)}.')
            print('  Open each file at each line below and copy that line, exactly as it stands, '
                  'into its "quote":')
            for s in said:
                print(f'    {s}')
            print(f'  {_PROVES}')
            return 0
        print('Lexicon read receipt — NOT ISSUED:')
    for s in said:
        print(f'  - {s}')
    return code

# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("path", help="paragraphs.json, document.xml, or .docx to scan")
    ap.add_argument("--language", default="auto",
                    help="Source language (dutch, italian, etc.) — drives language-specific rules. "
                         "Default: 'auto' reads the language DECLARED at Step 1c "
                         "(source_language.json beside paragraphs.json); "
                         "'none' disables language-specific rules.")
    ap.add_argument("--notes", default=None,
                    help="paragraphs.json, beside which the Step 1c declaration sits. Needed only "
                         "when PATH is the XML; a paragraphs.json PATH is its own notes.")
    ap.add_argument("--guessed", default=None,
                    help="Read only when NOTHING was declared: a language the caller has guessed "
                         "(repack passes its two-detector agreement on the original). It is used "
                         "as a guess, and the scan says so rather than PASSED.")
    ap.add_argument("--stage", default="pre-repack",
                    choices=["pre-apply", "pre-repack"],
                    help="Advisory label printed in output; does not change rule selection.")
    ap.add_argument("--warnings-are-errors", action="store_true",
                    help="Treat WARN severity as BLOCK and fail on them too.")
    receipt = ap.add_mutually_exclusive_group()
    receipt.add_argument("--read-receipt", nargs="+", metavar="LEXICON", default=None,
                         help="Skill Step 3, after the read: each lexicon read, by its path in "
                              "the skill folder. Names two random lines in each and writes "
                              "lexicon_read_receipt.json beside PATH, the paragraphs.json, "
                              "for the operator to quote.")
    receipt.add_argument("--check-read-receipt", action="store_true",
                         help="Skill Step 5, apply's first check: exits 1 unless the receipt "
                              "beside PATH matches the lexicons, every quote its line.")
    args = ap.parse_args(argv)

    path = args.path
    if not os.path.exists(path):
        print(f"lexicon_compliance: file not found: {path}", file=sys.stderr)
        return 2
    if args.read_receipt is not None or args.check_read_receipt:
        return _receipt_main(args)

    try:
        entries = _extract(path)
    except Exception as e:
        print(f"lexicon_compliance: failed to read {path}: {e}", file=sys.stderr)
        return 2

    language, cannot_rule, warning = _resolve_language(args, path)

    blocks, warns = scan(entries, language)
    if args.warnings_are_errors:
        blocks.extend(warns)
        warns = []

    print(f"Lexicon compliance scan — stage={args.stage}, language={language}, input={path}")
    if warning:
        print(f"  WARNING — {warning}")
    if cannot_rule:
        print(f"  source language: {not_supported('this lexicon scan', cannot_rule)}"
              + (" Every language's rules ran, none of them written for this document's language."
                 if language == "*" else ""))
    print(f"  entries scanned: {len(entries)}")
    print(f"  blocking violations: {len(blocks)}")
    print(f"  warnings:            {len(warns)}")
    if warns:
        print("")
        print("Warnings:")
        for w in warns:
            print(f"  {w}")
    if blocks:
        print("")
        print("Blocking violations:")
        for b in blocks:
            print(f"  {b}")
        print("")
        print("  *** BLOCKED: resolve all BLOCK-severity findings before proceeding. ***")
        return 1
    if cannot_rule:
        # S1 and S2: a pass from rules chosen by a guess, or from the language-agnostic
        # rules alone, is not a pass on this document's language, and must not read as one.
        print("  NO BLOCKING VIOLATION FOUND — but NOT SUPPORTED: see the source-language line "
              "above. The run goes on.")
        return 0
    print("  PASSED: no lexicon violations detected.")
    return 0

def _resolve_language(args, path: str) -> Tuple[str, Optional[str], Optional[str]]:
    """(the language the rules are chosen by, why this scan cannot rule or None, a warning or
    None), by source_language_markers.resolve_source_language — the one policy: an explicit
    --language, else the Step 1c declaration beside the notes, else a guess, which may never
    say PASSED. `none` (any case) is the language-agnostic run the operator asked for.

    A language no rules are written for — one the skill does not support, an explicit `*`,
    or none guessed — runs EVERY language's rules, as an unknown language always has: never
    a narrower scan than a guess would have run (CLAUDE.md 2.4 item 5), and NOT SUPPORTED."""
    named = args.language.strip().lower()
    if named == "none":
        return "none", None, None
    if named == "*":
        return "*", "--language * names no source language", None

    def guess():
        g = (args.guessed or "").strip().lower() or _guess_language(path)
        return None if g in ("", "*") else g

    notes = args.notes or (path if path.lower().endswith(".json") else None)
    r = resolve_source_language(notes, explicit=None if named == "auto" else named, guess=guess)
    return (r.language if r.language in LANGUAGE_MARKERS else "*"), r.cannot_rule, r.warning

def _guess_language(path: str) -> str:
    """Best-effort source-language detection from a paragraphs.json or document.xml.

    The detector deliberately uses source-language markers that do NOT overlap
    with common English legal drafting vocabulary. Earlier versions of this
    function matched on bare " clause " / " article " for French — which
    collided with post-translation English output (every English clause
    contract contains "clause"/"article") and mis-tagged English XMLs as French.

    For JSON, the detector only looks at the `text` field (always the source
    language). For XML, it looks at all w:t content.
    """
    try:
        if path.endswith(".json"):
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            sample = " ".join((p.get("text") or "")[:400] for p in data[:40] if isinstance(p, dict))
        elif path.endswith(".xml"):
            with open(path, "r", encoding="utf-8") as f:
                xml = f.read(40000)
            sample = " ".join(m.group(1) for m in _WT.finditer(xml))
        else:
            return "*"
        low = sample.lower()
        # Diacritic-based fingerprint first — cheap and strong signal for
        # Finnish, Hungarian, Polish, Portuguese, Spanish, German, French.
        # Count occurrences of language-unique characters.
        counts = {
            "finnish": sum(low.count(c) for c in "äöå"),
            "hungarian": sum(low.count(c) for c in "őűáéíóú"),
            "polish": sum(low.count(c) for c in "ąćęłńóśźż"),
            "portuguese": sum(low.count(c) for c in "ãõçâêôáéíóú"),
            "spanish": sum(low.count(c) for c in "ñ¿¡áéíóú"),
            "german": sum(low.count(c) for c in "äöüß"),
            "french": low.count("ç") + low.count("œ"),
        }
        # Chinese / Japanese — by codepoint range.
        has_cjk = any(0x4E00 <= ord(c) <= 0x9FFF for c in sample[:2000])
        has_hiragana = any(0x3040 <= ord(c) <= 0x309F for c in sample[:2000])
        has_katakana = any(0x30A0 <= ord(c) <= 0x30FF for c in sample[:2000])
        if has_hiragana or has_katakana:
            return "japanese"
        if has_cjk:
            return "chinese"

        # Source-language token markers that do NOT overlap with English legal
        # vocabulary. Each list intentionally excludes bare words like "clause",
        # "article", "agreement" that collide with English output.
        if any(k in low for k in [" overeenkomst", " bijlage", " partijen",
                                    " nederland", " stuurgroep", " coöperatie",
                                    " onderhavige", " wederpartij", " zijnde"]):
            return "dutch"
        if any(k in low for k in [" l'articolo", " fra le parti", " il presente",
                                    " contratto", " comunicazione di avvio",
                                    " ai sensi", " fermo restando", " nonché"]):
            return "italian"
        if any(k in low for k in [" yhtiö", " yhtiön", " sopimus", " sopimuksen",
                                    " tiekunta", " tiekunnan", " tuulivoima",
                                    " kiinteistö", " sekä ", " tämän ", " tässä ",
                                    " ehdossa", " mukaisesti"]):
            return "finnish"
        if any(k in low for k in [" der vertrag", " vertragspartner", " hiermit",
                                    " gesellschaft", " verpflichtet", " anlage"]):
            return "german"
        if any(k in low for k in [" la présente", " entre les parties",
                                    " société ", " le présent contrat",
                                    " nonobstant", " dénommé"]):
            return "french"
        if any(k in low for k in [" presente contrato", " conforme ",
                                    " nos termos ", " cláusula ", " sociedade "]):
            return "portuguese"
        if any(k in low for k in [" umowa", " umowy", " strona umowy",
                                    " zgodnie z", " niniejszą ", " spółka"]):
            return "polish"
        if any(k in low for k in [" jelen szerződés", " szerződő fél", " társaság",
                                    " képviseli", " kötelezett", " jogosult"]):
            return "hungarian"
        if any(k in low for k in [" el presente contrato", " las partes",
                                    " sociedad ", " en virtud de", " mediante"]):
            return "spanish"
        # Diacritic fallback — if nothing matched but we see a strong diacritic
        # signal, use that. Threshold = 5 to avoid single-loanword false hits.
        top = max(counts, key=counts.get)
        if counts[top] >= 5:
            return top
        return "*"
    except Exception:
        return "*"

if __name__ == "__main__":
    # C29: a character the console cannot show prints as an escape, never as a crash.
    for _stream in (sys.stdout, sys.stderr):
        try:
            _stream.reconfigure(errors='backslashreplace')
        except (AttributeError, ValueError):
            pass
    sys.exit(main())

# === SKILL FILE COMPLETE ===
