---
paths:
  - "uk/**"
  - "us/**"
---

# Skill-authoring conventions

**Relocated from `CLAUDE.md` §5.11 on 2026-08-24, phase 3b step 6 — FIVE of its seven rules.**
**Two did NOT come**, and the reason is the whole test: *no changelog inside the archive* and *no
confidential data or real-document examples* are **irreversible if forgotten** — each publishes client
names into a distributed archive, and a commit cannot be un-published. **Those two stay in the charter
under route 1.** The five below are reversible, so they live here.

**Each of these keeps an unconditional twin in the charter**, checked before the move: the anti-drift
rule in §2.5 item 5, the no-renumbering rule in §6.3, the telemetry prohibition in §2.6 and §3.5.
**So this file is the DETAIL, and the charter still carries the rule.**
- **Anti-drift safeguards are load-bearing.** The layered defences — mandatory step-file reads, the five
  hard rules, auto-invoked gates, per-batch validation with the batch-cap state file, gate semantics,
  integrity checks, transcript-mode discipline, the compaction-resume trigger — **exist because of repeated
  real post-mortems. Do not remove or soften any of them** as part of an Opus 5 or context-optimisation
  change unless proven redundant by testing.

- **Keep the eleven-step structure and the gate nomenclature stable** unless there is a positive reason to
  change them. **No renumbering of the steps:** a renumbering invalidates every step id in the existing
  forensic logs, which are the project's only behavioural evidence base. The cheap version first — fix the
  hole and the inconsistent letters.

- **The shipped run report is metadata-only by construction.** Steps run, per-step duration, gates fired and
  what satisfied them, validator warnings, iteration loops, integrity results, file manifest. **Never
  document text, never filenames. And no third-party telemetry, ever** — this skill processes privileged
  documents. *(It is the same artefact as the forensic log, so designing the log format well gives the
  shipped report for free.)*

- **No sub-agents inside the skill** — §3 of `OPUS-5-MIGRATION.md`.

- **A shared capability lives in one place.** This is a rule for **our** maintenance of the artefact, not an
  instruction to the skill's operator, and it belongs here rather than in a shipped step document —
  putting a maintenance convention into a shipped document is how a 221-entry phrase map came to be a de
  facto thirteenth dictionary inside the scripts folder.
