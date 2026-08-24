---
name: publish-skill-archives
description: The release procedure for this repository - how the two variant trees become two .skill archives and reach the two public install repos. Use when packaging a release, publishing to the UK or US distribution repo, or answering what the deliverable is and which of the three public repos is which. Relocated from CLAUDE.md 6.6 under route 3 on 2026-08-24.
---

# Publishing from the monorepo

**This is a release procedure — it runs at one moment, not every session, which is why it is a skill
rather than charter text.** `CLAUDE.md` 6.6 keeps the standing facts and points here.

> **READ THIS FIRST: NEITHER SCRIPT EXISTS YET.** `tools/package.py` and `tools/publish.py` are named
> below and in the charter's 6.6, and **both are absent from `tools/` — checked by listing, 2026-08-24,
> and named nowhere else in the repository.** So this document is a **specification**, not a runbook.
> **Building them is step 4's work** *(section 3.4 of `CLAUDE.md`, third bullet: the deferred items land
> there, not in step 2)*. Do not write a release script from memory of this page without re-reading 3.4
> first, and do not describe either script as existing.

## What the deliverable is, and what it is not

**Two independent `.skill` archives of 198-odd files each, uploaded and installed separately.** The
monorepo changes how the content is *edited*, not what ships: there is **no build step**, no assembly and
no generator. **`uk/` IS the publishable tree** — what you see in the repository is what ships.

## The two scripts, once they exist

1. **`tools/package.py`** → one `.skill` per variant. Each is a zip of the corresponding variant tree
   **excluding `README.md` and `LICENSE`** — verified against the published archives, which contain 198
   files and carry neither.
2. **`tools/publish.py`** → copies the contents of `uk/` (this time *including* `README.md` and
   `LICENSE`) into a local clone of the public UK repo, commits and pushes; same for `us/`.
   **Deliberately a plain copy-and-commit rather than a git subtree**, so Wouter can read the diff before
   it pushes. That is the whole reason for the choice — do not "improve" it into a subtree.

## Three public repos will exist, and users need that disambiguated

`legal-translation-skill` is the **source**. The two variant repos remain the **install channels**, and
they keep their existing URLs, descriptions and install instructions. **Every README must say which is
which** — a reader who installs from the source repo gets a directory of two trees and a `tools/` folder,
which is not a skill.

## What this skill deliberately does NOT carry

- **The approval rule.** *Never make a repo public, or publish, without Wouter's explicit OK* is in
  **section 3.4 of `CLAUDE.md`** and stays there. It is the only irreversible act in step 4, and a rule
  whose absence is irreversible may not live behind an invocation — it has to load every session.
- **The confidentiality gate.** Both controls and the publication check over the archives **and the
  commit history** are section 3.4's second bullet, and section 5.4 owns the rules themselves.
- **What goes inside the archive.** *No changelog inside the archive, ever* is section 5.11's, and it
  stays in the charter for the same reason as the approval rule.
