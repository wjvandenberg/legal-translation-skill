# legal-translation-skill

**The source repository for a Claude skill that translates legal documents into English
without breaking the Word file.**

Hand it a `.docx` in almost any language; get back an English `.docx` you could read, mark up,
negotiate and in principle sign — with the numbering, styles, tables, headers, footers,
footnotes, comments and tracked changes still intact, and the definitions re-sorted into
English alphabetical order.

Two variants are published: **UK English** (the default) and **US English**.

---

## This is the source repository. It is not the one you install.

Three repositories exist and it is worth being clear which is which, because installing the
wrong one gets you a development tree instead of a skill.

| repository | what it is | who it is for |
|---|---|---|
| **`legal-translation-skill`** *(this one)* | the **source** — both variant trees side by side, plus the tooling and tests that keep them honest | anyone reading, auditing or changing the skill |
| the **UK English** distribution repo | the packaged UK variant | **users — install from here** |
| the **US English** distribution repo | the packaged US variant | **users — install from here** |

The skill is also available from **lawve.ai**.

---

## Why it exists

Machine translation gets the words roughly right and the *document* wrong. It reaches for an
everyday-English or calqued rendering where English legal drafting has a settled term of art,
and it is inconsistent about it within a single document. It destroys `.docx` structure —
numbering, styles, tables, signature blocks, headers, footers, footnotes and comments. It
cannot handle **tracked changes**, so it cannot tell you what the document says if you accept
them and what it says if you reject them. It leaves the definitions in source-language
alphabetical order, which is not alphabetical in English. And it gives you no way to tell
whether what came back is complete.

This skill is built for the case where the answer has to be a *document* rather than a gist:
cross-border transactions where the source is in a language the deal team does not work in.

## How it works, in one paragraph

An eleven-step pipeline that **never rewrites the document from scratch**. It extracts every
paragraph out of the original `document.xml`, translates them in small batches under a
two-layer dictionary — cross-language English references plus per-language sub-dictionaries —
and then **text-matches** the English back onto the *original* XML, replacing only the run
content and leaving styles, numbering and structure untouched. That last property is the
golden rule of the design, and it is measured to work: zero style or numbering mismatches on
every document tested so far. Quality gates fire throughout; the auxiliary parts of the
package get translated too.

It is deliberately **slower and larger** than a translate-this skill. Minutes, not seconds —
between 18 and 50 across the runs measured, scaling with paragraph count.

## What it does that the alternatives do not

- Built-in **English legal reference dictionaries** across 15 domains, plus **per-language
  sub-dictionaries** covering M&A, IP, IT/SaaS, finance, tax, litigation, employment and more.
  Full sub-dictionary coverage for **11 languages**; other languages translate very well too.
- **Tracked changes read correctly both when accepted and when rejected.**
- **Definitions reordered alphabetically** in English.
- **Headers, footers, footnotes and comments translated.**
- **UK English by default, US English on request.**
- Quality gates at every stage.

---

## Layout

```
uk/     a complete skill tree — this IS the publishable UK variant, no build step
us/     the same, US-default
tools/  never ships — packaging, publication, the parity check, the confidentiality controls
tests/  never ships — synthetic fixtures, the smoke suite, one failing input per check
```

`uk/` and `us/` are each a complete skill. **What you see in the repository is what ships**:
packaging is a zip of the variant tree, not a generator run, so there is no step at which the
published artefact can differ from the reviewed one. `tools/` and `tests/` are siblings of the
variant trees and never inside them, so nothing development-only can leak into a shipped skill.

Holding both variants in one repository is a deliberate trade. The content is still edited
twice — but a single pull request touches both trees, so a fix cannot land in one variant and
be forgotten in the other. That has happened, and it shipped.

## Working on it

```bash
uv run python tools/precommit_gate.py
```

Every control over everything on the commit list, with one verdict. It must be **CLEAR**
before anything is committed. It reads its pattern lists from outside the repository, so it
reports `CANNOT CERTIFY` rather than `CLEAR` when it cannot load them — a control that could
not run has not passed.

```bash
uv run python tools/parity_check.py
uv run python tests/run_tests.py
```

The parity check compares the two trees and fails on any divergence that is not a deliberate
variant difference. The test suite runs the synthetic fixtures and the negative inputs.

**Every check in this repository has at least one input built to make it fail**, and those
inputs are part of the suite. A check that has never been seen to fail is not a check.

## Contributing

Pull requests only — `main` is protected. Every branch carries its own test, and a change
claimed to be non-behavioural has to prove it by byte comparison rather than by assertion.

## Licence

See `LICENSE` in each variant tree.
