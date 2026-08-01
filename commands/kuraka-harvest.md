---
description: "VAULT-ONLY. Harvest the adjustments consumer projects made to their mounted agents (projects/<slug>/overrides/), classify them (stale copy / project tuning / core candidate), detect custom agents worth adopting, PROPOSE integrations to the user (never auto-apply), and manage the suite version bump + changelog. Run it each time you open the vault to continuously improve the agent suite."
---

# Task: Harvest project feedback into the core agent suite

Collect what the consumer projects changed in their mounted agents/skills/commands,
figure out which of those changes are **framework-level improvements**, propose them
to the user, and — only after approval — integrate them and bump the suite version.

## Step 0 — Vault-only guard (HARD)

This command operates on the vault's central store. Verify the cwd is the vault:
`projects/` dir + `SUITE-VERSION` + `kuraka_common.py` must all exist here. If not,
STOP: "Este comando solo corre en el vault Kuraka (`/Users/xmn/Documents/Agentes/AgentesTrabajos/kuraka`)."

## Step 1 — Hygiene pass

- Delete any AppleDouble junk: `find projects -name "._*" -delete` (an overrides
  snapshot made of ONLY `._*` files is 100% junk — remove the whole `overrides/`
  subdir and say so).
- Note every override snapshot whose `MANIFEST.md` `snapshot:` date predates the
  last vault commit touching the same files — those are **stale-suspect** and get
  extra scrutiny in Step 3.

## Step 2 — Inventory (BOTH channels — the layer is the main one)

Phase-7 improvements reach the vault through TWO channels; scanning only
`overrides/` misses most of the signal:

**Channel A — the specialization layer** (`projects/<slug>/layer/` = snapshot of
the project's `.claude/project/`). This is where Phase 7 writes agent
improvements, and `detect_overrides` deliberately EXCLUDES `*.append.md` — so
this channel NEVER appears in overrides. Scan per project:

- `layer/agents/*.append.md` — per-agent additions (the richest source).
- `layer/lessons-learned/*.md` — frontmatter `applies_to` names target agents.
- `layer/review-checks/*.md` — checks the team added to reviewer agents.
- `cycles/*/RETRO-*.md` archived **since the last harvest** (newest date in
  `SUITE-CHANGELOG.md`) — only the sections proposing agent/framework
  improvements. With many retros, grep-filter first; never read 40 retros whole.

Skip anything named `._*`. When the material is large (several projects with
many lessons), fan out one read-only subagent per heavy project to extract
candidates, instructing each to check the current vault text before proposing
(vault agents cite integrated lessons inline — e.g. "(clinica-dental: …)",
"(kuraka-control S5c)" — substance already present = ALREADY-INTEGRATED).

**Channel B — whole-file overrides** (`projects/<slug>/overrides/`):

1. Read `MANIFEST.md` (snapshot date, file list).
2. For each `<cat>/<file>`, diff against the vault baseline (`<vault>/<cat>/<file>`).
3. A file with **no vault baseline** is a **custom agent/skill/command** → Step 4.

## Step 3 — Classify every divergence (the core judgment)

Direction matters: the diff shows `vault(current) → override(snapshot)`. Classify:

- **STALE** — the override is an OLD vault copy: its "removals" are content the
  vault ADDED after the snapshot date, and it adds nothing of its own. Typical of
  pre-manifest snapshots. → Not an improvement. Action: recommend re-mount +
  `kuraka-backup.py --overrides-only` in that project to clear it. NEVER read a
  stale removal as "the project rejected this feature".
- **PROJECT TUNING** — genuinely project-specific (hardcoded paths, that project's
  doc layout, model downgrades for cost, project glossary). → Stays as override;
  no vault change.
- **CORE CANDIDATE** — a generalizable improvement: a new check, a better gate, a
  clearer output contract, a guard against a failure mode that other projects also
  hit (cross-reference the RETROs). → Goes to the proposal table.

When in doubt between STALE and CORE, check `git log -p -- <cat>/<file>` in the
vault: if the override content matches a committed historical vault version, it is
STALE.

## Step 4 — Custom agents (adoption candidates)

For each custom file: is it reusable beyond its project? (A Jira sync, a deploy
diagnostician, a domain-specific validator…). If yes, sketch the **generalized**
version: hardcoded paths → `kuraka.config.yaml` refs, project names → config,
tier for `MODEL-ROUTING.yaml`. If it is inherently single-project, classify as
PROJECT TUNING and move on.

## Step 5 — PROPOSE to the user (MANDATORY GATE — never skip)

**Do NOT apply anything yet.** Present ONE proposal table, then ask which items to
integrate (per-item approval; AskUserQuestion with multiSelect when available):

| # | Origen | Tipo | Cambio propuesto | Qué mejora en los agentes actuales | Riesgo |
|---|--------|------|------------------|------------------------------------|--------|

- `Tipo`: `mejora-agente` / `agente-nuevo` / `fix-infra` / `staleness` (staleness
  rows are informational: list the project + recommended cleanup, nothing to merge).
- `Qué mejora` must be concrete: which failure mode it prevents, which phase gets
  more precise, which rework it avoids (cite the RETRO/lesson if one motivated it).
- Include your recommendation per row (integrar / descartar / dejar como tuning).

Wait for the user's selection. Items not approved are recorded in the changelog's
"Descartado" note only if the user wants a trace; otherwise dropped.

## Step 6 — Apply ONLY the approved items

- **Agent improvements**: edit the vault `agents/*.md` / `skills/*.md` (backticks,
  never wikilinks). Keep the change general — strip project specifics.
- **New agents**: create `agents/<name>.md` (frontmatter: `name` = filename stem,
  `description`, `model`), assign a tier in `MODEL-ROUTING.yaml` (do NOT hand-edit
  `model:` — run `python3 kuraka-apply-models.py` after), add the name to
  `AGENTS=()` in `scripts/sync-obsidian.sh`, and if it participates in the
  lifecycle, add it to the phase map or "Conditional agents" table in
  `skills/kuraka.md`.
- Run `python3 kuraka-apply-models.py --check` — must pass.

## Step 7 — Version bump + changelog

1. Decide the bump against `SUITE-CHANGELOG.md` scheme: behavior changes or new
   agents → **MINOR**; only fixes/typos → **PATCH**; contract breaks → **MAJOR**
   (confirm with the user).
2. Write the new version to `SUITE-VERSION` and prepend a `SUITE-CHANGELOG.md`
   entry: Añadido / Cambiado / Corregido, each item with its origin project and
   the "qué mejora" one-liner. Leave `### Resultados` as "_pendiente_".
3. **Fill in Resultados of PREVIOUS versions**: group `projects/*/cycles/*/meta.yaml`
   by `suite_version` — cycles count, verdicts, rework signals from their RETROs
   (late BLOCKERs, re-runs, new overrides that correct the framework). This is how
   versions get compared: less rework in vN+1 than vN = the harvest worked.

## Step 8 — Close

- Propose the commit (`git add` the touched framework files + store cleanups) and
  ask before committing. Suggested message: `feat(harvest): v<X.Y.Z> — <n> mejoras
  integradas desde <proyectos>`.
- Remind the user: consumer projects pick up the new version on their **next
  mount** (`mount-kuraka` in each project), and stale-override projects need the
  Step 3 cleanup for future harvests to read clean signal.
- Final summary: integrated items, discarded items, new version, projects needing
  action.
