---
paths:
  - "uk/**"
  - "us/**"
  - "tools/**/*.py"
  - "tests/**/*.py"
---

# OOXML hard rules — every one confirmed in production

**Relocated from `CLAUDE.md` §5.10 on 2026-08-24, phase 3b step 6.** They matter only when touching
OOXML-handling code, and **forgetting one produces a file Word rejects — unpleasant but REVERSIBLE**,
which is what makes them route 4 rather than route 1.

**A scoped rule is good for ONE USE PER SESSION** — after a `/compact` it is not put back, and it does
not return when a matching file is read again. Measured, settled, and designed around rather than
re-tested. If you need these twice in one session, re-open this file deliberately.
- **Never use `xml.etree.ElementTree` to write OOXML.** It rebinds namespace prefixes on serialisation and
  Word rejects the file. Use lxml or pure string/regex edits, and keep an `assert 'ns0:' not in xml` guard
  after every edit.

- **Never let an XML regex cross an element boundary.** A non-greedy `.*?` under `re.DOTALL` will silently
  jump runs. Two production incidents: one inserted **464** highlights and scrambled paragraph order; one
  silently swallowed an `"E-mail address:"` label. Bound it with a negative lookahead —
  `(?:(?!</w:r>).)*?`. Prefer lxml for structural edits.

- **Never match `<w:t>` as `<w:t[^>]*>`** — that also matches `<w:tcPr>`, `<w:tbl>` and `<w:tab/>`. Use
  `<w:t(?:\s[^>]*)?>`.

- **`<w:b w:val="0"/>` means bold OFF.** Any bold check must read `w:val` and treat `0|false|off` as
  not-bold. The same applies to `w:i`, `w:strike` and `w:u`.

- **Count tab CHARACTERS separately from tab STOPS.** A `w:tab` inside `pPr/tabs` is a stop and carries the
  same tag name as a rendered tab, so a naive iteration sums the two.

- **Table-nested paragraphs are first-class.** Signature blocks, schedules, form fields and party grids live
  in `w:tbl/w:tr/w:tc/w:p`. Extraction and apply must both recurse, or those paragraphs ship untranslated.
  **The same asymmetry exists for containers the skill never lists** — `w:sdt` content controls and
  `w:smartTag`.

- **Text-matching, not index-matching, is why this works.** One real document produced 577 JSON entries for
  564 XML paragraphs — a 6–13 position drift that under index-matching corrupted styles, numbering and
  indentation and left the last ~60 paragraphs in the source language. **Do not reintroduce index-based
  application.**

- **Non-Latin tracked changes need the visible-space plus ZWSP hybrid.** Source text in CJK carries no
  inter-word whitespace, so `.strip()` in apply eats the operator's authored boundary space. A zero-width
  space (U+200B) is Unicode category `Cf`, so `str.isspace()` is False and it survives `.strip()`. **Do not**
  iterate through NBSP, ideographic space or thin/en/em spaces — that path is documented and dead. **And a
  ZWSP in the deliverable is always a defect:** the fix is a pre-repack scrub, not a prohibition on the
  device.

- **Terminology rewrites must protect multi-word defined terms.** An `Annex → Schedule` rule collided with
  the defined term "Service and Maintenance Schedule", and a blanket revert produced "Annexs". Use ordered
  rules with negative lookbehind.

- **Upstream PDF→Word conversion is lossy and lies about it.** Where the source was itself converted from
  PDF, highlighting, strikethrough, hyperlinks, checkboxes and table borders may already be gone,
  *inconsistently*. **Never attribute such a loss to the pipeline without rendering the SOURCE Word file.**
  Keep the buckets distinct: **A** = introduced by us, **B** = inherited.
