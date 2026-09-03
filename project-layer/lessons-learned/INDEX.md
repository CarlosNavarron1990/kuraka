# Lessons learned — INDEX

`LL-NNN` entries for PetSuite. Agent prompts and convention files cite these by
ID, so **IDs are permanent**: never renumber, never reuse. Supersede an
obsolete lesson by marking it and pointing to its replacement.

## Entries

| ID | Title | Origin | Cited by |
|----|-------|--------|----------|
| [LL-001](LL-001-fixture-que-inventa-su-esquema.md) | Un fixture que declara su propio esquema no puede detectar la deriva codigo↔BD | REQ-20260822 / REQ-20260825-registro-cliente-roto | `.claude/rules/20-esquema-real-en-tests.md` |

## How to add one

1. Create `LL-NNN-short-slug.md` in this directory.
2. Add the row here.
3. Cite the ID from whichever `conventions/*.md` file the lesson constrains.

Each entry:

```markdown
# LL-NNN — {one-line title}

**Date**: YYYY-MM-DD
**Cycle / incident**: {REQ id, or the incident}
**Cost**: {rework, outage, tokens — be concrete}

## What happened
## Root cause
## The rule that follows from it
## How it is enforced now
{convention file amended, gate added, review check added — or "unenforced,
relies on this lesson being read"}
```

Write a lesson only when something **cost** something. A preference is a
convention; a lesson is a scar.

## Related

- This index is the **only** `LL-NNN` registry for PetSuite. A
  `docs/process/lessons-learned.md` was seeded into this project by the Kuraka
  mount on 2026-08-01, but its six lessons belonged to other projects
  (`sie_v2`, `guai-specialties`, `DD-896`, `DD-1031`) and it was deleted — a
  new project starts with no lesson history. Framework-level lessons still
  live in the vault at `$KURAKA_VAULT/docs/process/lessons-learned.md`; agent
  prompts that cite `[LL-001]`..`[LL-006]` resolve against that copy, not
  against anything in this repo.
- Cross-cycle patterns are consolidated by the `pattern-detector` agent into
  `RECURRING-ISSUES.md`; a recurring issue usually deserves promotion into a
  `conventions/*.md` rule rather than a new lesson.
