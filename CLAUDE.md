# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

This is **not** an application codebase. It is the **Kuraka framework vault** — the
source-of-truth for a portable multi-agent system that mounts into any other project via
`mount-kuraka.sh`. The repo contains agent definitions, skill prompts, meta-rules,
two inspection/telemetry scripts, and a pytest-based structural eval harness.

"Kuraka" (Quechua *kuraq* = "el mayor") is the orchestrator skill (`skills/kuraka.md`)
that coordinates 23 subagents across an 8-phase dev lifecycle: 13 pipeline agents,
3 entry agents (`inti`/`arki`/`amauta`), and 7 on-demand agents outside the phase
map (see `skills/kuraka.md` §On-demand agents).

## Commands

```bash
# One-shot initializer (RECOMMENDED entry point). Runs inspect → draft config →
# project skeleton → mount → registry, in one command, from anywhere. The only manual
# step left is restarting Claude Code in the target. Interactive or flag-driven (the
# future control-plane web app wraps this). Never overwrites an existing config/layer.
python3 kuraka-init.py [target_dir]                  # or: --target ... --name ... --yes
python3 kuraka-init.py --target /path --name foo --yes --no-mount
python3 kuraka-init.py --target /path --register-only --yes   # only upsert the registry note

# Discover ALL Kuraka-mounted projects on disk and reconcile the registry (both ways:
# mounted-but-unregistered, and registered-but-not-mounted). mount-kuraka.sh now also
# auto-registers, so new mounts never drift. Read-only without --register.
python3 kuraka-discover.py [--register] [--roots ~/Desarrollos,~/work]

# Mount the vault into a consumer project (copies agents/skills/rules/artifacts into
# .claude/ and updates .gitignore of the target). Always run in the target repo root.
# (kuraka-init.py calls this for you; use directly only for a re-mount.)
# The CANONICAL mount is kuraka-mount.py (pure Python, no rsync — runs on
# macOS/Linux/Windows). mount-kuraka.sh is now a thin bash wrapper that execs it,
# and kuraka-init.py::run_mount invokes it via sys.executable. On Windows the CLI
# is kuraka.cmd → kuraka.py (mirror of the bash `kuraka`); installer is install.ps1.
python3 kuraka-mount.py [target_dir]                  # cross-platform (Windows too)
# On a TTY it shows a banner + a small menu (which categories to mount / status-only)
# and a live MCP-component detection block; piped/agent runs mount everything silently.
# It also (a) snapshots any local agent tuning BEFORE the rsync and (b) re-applies
# project overrides AFTER it (see "Project-specific overrides" below).
bash mount-kuraka.sh [target_dir]            # default target is $PWD

# Validate frontmatter + registration readiness of a mounted .claude/
bash validate-kuraka.sh [target_dir]         # exit 1 if any agent/skill FM is invalid

# Stack detector (used by the amauta brownfield agent and ad-hoc)
python3 kuraka-inspect.py [target_dir]       # JSON to stdout, summary to stderr

# Aggregated telemetry dashboard across cycles
python3 aggregate-telemetry.py [project_root]  # writes docs/process/agent-telemetry/DASHBOARD.md

# Back up a project's FULL Kuraka state into the vault's unified store. Snapshots
# layer/ (.claude/project), state/docs-process/ (REQ, stories, schemas, checkpoints),
# cycles/<REQ>/ (RETRO + telemetry + meta, branch-tagged) AND overrides/ (agent/skill/
# command files that diverge from the vault baseline — project-specific tuning). Run at
# Phase 7 (the final-auditor calls it). Idempotent. Feeds cross-project pattern-detection
# AND preserves Kuraka work outside the solution's git.
python3 kuraka-backup.py [project_root]                 # layer+state+cycles+overrides
python3 kuraka-backup.py [project_root] --overrides-only  # only re-snapshot overrides (mount pre-flight)
python3 kuraka-archive.py [project_root]                # cycles-only (backward-compat wrapper)

# Restore a project's Kuraka history from the vault on branch switch / re-mount.
# mount-kuraka.sh calls this and ASKS before pasting layer/state; overrides are ALWAYS
# re-applied (no prompt) so project agent tuning survives every mount.
python3 kuraka-restore.py [project_root]                 # central → project (layer + state + overrides)
python3 kuraka-restore.py [project_root] --overrides-only  # only re-apply overrides (always; used by mount)

# Structural eval harness (runs from a consumer project that has mounted the artifacts)
cd <target-project> && python3 -m pytest tests/kuraka/ -v
# A single test:
python3 -m pytest tests/kuraka/test_structure.py::test_should_have_valid_frontmatter -v
```

There is no build system, linter, or package manager here. All scripts are POSIX shell
or standalone Python 3 (no dependencies).

### Suite versioning + harvest loop

The framework suite is versioned: `SUITE-VERSION` (single line, semver) +
`SUITE-CHANGELOG.md` (scheme + per-version results). Every mount stamps
`suite_version` into the consumer's `.claude/.kuraka-mount-manifest.json`, and
`archive_cycles` copies it into each archived cycle's `meta.yaml` — so retros can
be grouped per suite version to compare rework across versions.

`/kuraka-harvest` (vault-only command, `commands/kuraka-harvest.md`, symlinked into
`.claude/commands/` so it's invocable here; in `EXPORT_SKIP`) is the improvement
loop: run it when opening the vault. It collects `projects/*/overrides/`, classifies
each divergence (stale vault copy / project tuning / core candidate), detects
custom agents worth adopting, **proposes** integrations (user approves per item —
NEVER auto-apply agent changes), then applies + bumps the version + updates the
changelog. Version bumps happen ONLY through this flow.

`/kuraka-eval` (vault-only, `commands/kuraka-eval.md`, also symlinked) is the
complementary loop: it executes an agent definition in a SANDBOX against a real
registered project (target repo read-only, outputs to scratchpad), verifies the
agent's claims against the real code by spot-check, and collects the
"GAPS DE LA DEFINICIÓN" the agent itself reports — then proposes fixes (per-item
approval, changes recorded under "Sin publicar" in the changelog; the bump still
belongs to harvest). Harvest learns from what projects tuned; eval learns from
running the current definition and seeing where it creaks. First run (2026-08):
`amauta` vs kuraka-control → seed-project-conventions parity + config-schema fixes.

## Architecture — what lives where, and why

### The vault layout mirrors `.claude/` in consumer projects

| Here (vault)              | Mounted to (project)              | Role                                      |
|---------------------------|-----------------------------------|-------------------------------------------|
| `agents/*.md`             | `.claude/agents/`                 | Subagent definitions (16)                 |
| `agents/contexts/*.md`    | `.claude/agents/contexts/`        | Per-agent rule bundles and output schemas |
| `skills/*.md`             | `.claude/skills/<n>/SKILL.md` + flat `.claude/skills/<n>.md` (transition) | Skill prompts (phase-level). Claude Code only registers the DIR form; the flat copy keeps old path references working (retire one suite version after references migrate). Both byte-identical to the vault; `kuraka_common._skill_dir_canonical` maps SKILL.md to the flat baseline for overrides, and restores mirror SKILL.md → flat. Invocability lives in vault frontmatter (`disable-model-invocation`/`user-invocable`/`context: fork`, stripped for non-Claude): phase skills + kuraka core non-invocable (the `/kuraka` COMMAND is the entry point), utilities fork, only facilitate-discovery / diagnose-deploy / seed-project-conventions stay user-invocable. **Collision rule**: a registered skill SHADOWS the same-named slash command, so a skill whose name matches a `commands/*.md` (today only `kuraka`) is mounted ONLY as the flat copy and any stale `<n>/SKILL.md` is deleted — otherwise `/kuraka` resolved to the non-invocable skill ("this skill can only be invoked by Claude") instead of the command entrypoint. |
| `commands/*.md`           | `.claude/commands/` · `.cursor/commands/` · `.agent/workflows/` · `.codex/prompts/` | Slash-command prompts. Claude: copied verbatim. Non-Claude: rendered by `kuraka-export.py::export_commands` (arg-placeholder + role preamble adapted per tool). `EXPORT_SKIP` = clean-cases/lint/run-tests (sie_v2) + sync-from-vault (Claude-only). |
| `rules/16-*.md`, `17-*.md`, `18-*.md`, `19-*.md` | `.claude/rules/`           | Framework meta-rules (only these)         |
| `kuraka-artifacts/docs/process/**`    | `docs/process/**`           | lessons-learned + telemetry dashboard template |
| `kuraka-artifacts/tests/kuraka/**`    | `tests/kuraka/**`           | Structural eval harness                   |

Consumer projects pull **from** this vault (read-only for the vault during `mount-kuraka`),
but their `.claude/` may be synced **back** to the vault by the hook in
`scripts/sync-obsidian.sh`. That script has an 80%-of-vault safety guard per category:
if the consumer's `.claude/` is incomplete (e.g. just after `git switch`), it aborts
that category's sync rather than wiping the vault.

### Project-specific overrides (agent/skill/command tuning)

Consumer projects often tune a framework agent to their needs (e.g. editing
`.claude/agents/backend-developer.md`). Those dirs are gitignored **and** overwritten
by the vault rsync on every mount, so the tuning would otherwise be lost. The override
subsystem preserves it, centrally, with zero change to how you tune (keep editing the
files directly):

- **Detect** (`kuraka_common.detect_overrides`): a `.claude/{agents,skills,commands}/*.md`
  file is an override if it diverges byte-for-byte from its vault baseline (or has no
  baseline = custom). `*.append.md` fragments are excluded. **Staleness is NOT an
  override**: `kuraka-mount.py` writes `.claude/.kuraka-mount-manifest.json` (vault
  baseline hash per mounted file); a file that differs from the current vault but still
  matches its mount-time baseline was never touched by the project — it is skipped so
  the next mount refreshes it. Legacy projects without a manifest get a git-history
  fallback (`_matches_vault_history`): divergent-but-matching-a-committed-vault-version
  = stale, skipped. (Without this, a stale project pinned itself to an old framework
  forever: kuraka-control 2026-07 had 27 June files snapshotted as "overrides".)
- **Snapshot** (`kuraka-backup.py`, also `--overrides-only`): copies divergent files to
  `projects/<slug>/overrides/<cat>/<file>` + a `MANIFEST.md`. If nothing diverges it
  **clears** the store subdir, so a reverted tuning disappears (no orphan re-applied later).
- **Re-apply** (`kuraka-restore.py --overrides-only`): overwrites the fresh vault copy
  with the stored overrides — the project override always wins. `mount-kuraka.sh` runs
  this on EVERY mount (TTY or not), and also snapshots pre-rsync so an un-backed-up tuning
  is captured before it's clobbered.

Trade-off (intentional): an override is a whole-file copy, so that one agent stops
receiving framework updates while the override exists. Delete the override (revert the
file to the vault version, then backup) to opt back into framework updates.

### Wikilinks vs backticks — mostly historical

Historically the vault stored cross-references as Obsidian wikilinks (`[[po-analyst]]`)
and the runtime expects backticks (`` `po-analyst` ``). Today the vault content under
`agents/`, `skills/`, `rules/`, `commands/` is **already backticked** (only a couple of
stray `[[…]]` remain), and **`mount-kuraka.sh` does NOT convert — it is a straight rsync**.
This is what makes override detection a safe byte comparison (no formatting confound).
The reverse conversion still exists for the sync-back path:

- **Project → vault**: `scripts/sync-obsidian.sh` converts `` `name` `` → `[[name]]`
  via a `sed` expression built from the hardcoded `AGENTS=()` and `SKILLS=()` arrays
  near the top of that script.

**When you edit here**: prefer backticks (`` `po-analyst` ``) — that is what the runtime
reads and what the vault already uses. If you do add a wikilink in `agents/`,
`agents/contexts/`, `skills/`, or `rules/` for the graph view, note that mount will copy
it **verbatim** (no conversion), so it reaches the runtime as a literal `[[…]]`.
`commands/*.md` is copied verbatim too — never use wikilinks there; they would break grep
patterns in the executable prompts.

**When you rename or add an agent/skill**: update the `AGENTS=()` / `SKILLS=()` array
in `scripts/sync-obsidian.sh` or the reverse conversion breaks silently.

### Agent frontmatter contract

Every `agents/*.md` must have `name` + `description` + `model` (one of `fable | opus |
sonnet | haiku`), and the frontmatter `name` must equal the filename stem. Every
`skills/*.md` needs `name` + `description`. `validate-kuraka.sh` enforces this (its
`VALID_MODELS`); CI-style usage is to run it in the target project after mounting.

**Model routing is centralized in `MODEL-ROUTING.yaml` — do NOT hand-edit `model:` lines.**
That file is the single source of truth: it maps each agent to a capability **tier**
(`frontier`/`heavy`/`balanced`/`fast`) and each tier to a concrete model **per platform**
(Claude, Antigravity, Cursor, Codex…). `kuraka-apply-models.py` reads it and rewrites
every `agents/*.md` frontmatter `model:` for the Claude column:

```bash
python3 kuraka-apply-models.py           # apply the claude column to frontmatter
python3 kuraka-apply-models.py --check    # validate map↔files + report drift (exit 1 on drift)
```

Current tiers → Claude model: **frontier → `fable`** (the judgment GATES: po-analyst,
architect-reviewer, code-reviewer, security-reviewer, final-auditor), **heavy → `opus`**
(architecture/brownfield/pentest/security-audit agents), **balanced → `sonnet`**
(backend/frontend/story/test), **fast → `haiku`** (mechanical). To re-route an agent,
change its tier in `MODEL-ROUTING.yaml` and run the script — never edit the frontmatter
directly (the next `--check` would flag it as drift).

Two things worth knowing (verified against code.claude.com/docs model-config):
1. **Tier names are Claude aliases, not pinned IDs** — `opus`/`sonnet`/`haiku`/`fable`
   auto-resolve to the *current* model in that tier, so a model version bump (Opus 5 →
   Opus 6) needs **zero** edits here. You only touch the map to move an agent between
   tiers or add a platform.
2. **Non-Claude platforms don't take a per-subagent model** — the export drops `model:`
   and the tool picks its own model. So the `antigravity`/`cursor`/`codex` columns in the
   map are recommendations, surfaced as a "Model tier" column + legend in the exported
   `AGENTS.md` role table (`kuraka-export.py`), telling the user which roles need their
   strongest model.

**Harness capabilities are centralized in `AGENT-HARNESS.yaml` — do NOT hand-edit
`tools:` / `disallowedTools:` / `maxTurns:` (/ future `skills:` / `memory:`) lines.**
Sibling of MODEL-ROUTING, same governance: change the map, then run
`python3 kuraka-apply-harness.py` (`--check` flags drift; `validate-kuraka.sh` runs
both `--check`s as vault self-checks). These keys are **Claude Code only**: the vault
frontmatter is the Claude-native superset, and non-Claude renders (Antigravity /
Cursor / Codex) subtract them at mount time via
`kuraka_common.strip_claude_frontmatter` (`CLAUDE_ONLY_FRONTMATTER_KEYS`). Claude
mounts stay byte-identical to the vault — required by the override subsystem's byte
comparison, so NEVER inject frontmatter at mount time for the claude target.
Vault-side regression tests for this contract live in `tests-vault/`
(`python3 -m pytest tests-vault/ -v`; not mounted into consumers).

**Hooks (`hooks/`, Claude-only) + discipline blocks (`discipline/`).** Four
deterministic enforcement hooks (telemetry completeness, gate integrity T7,
orchestrator write guard, output validation — see `hooks/README.md`) are mounted
into `.claude/hooks/` and wired into the consumer's `.claude/settings.json` by a
non-destructive merge (`merge_claude_hook_settings`), for the claude target ONLY.
Where a hook replaces manual discipline prose, the vault text keeps a slim
hook-note plus a `<!-- kuraka:discipline:<name> -->` marker; non-Claude renders
re-expand the marker to the full manual prose from `discipline/<name>.md`
(`_expand_discipline` in `kuraka-mount.py`) — no platform loses a rule when
Claude's prompts slim down.

### The orchestrator workflow

`skills/kuraka.md` is the main workflow. `kuraka-modes.md` and `kuraka-policies.md`
are companions — modes (Bootstrap/Brownfield/Normal/Lite/Retroactive/Reduced),
and cross-cutting policies (retry, timeout, token budgets, checkpointing, telemetry).
Per-phase skills live in `skills/<verb>-<object>.md` (`analyze-requirement`,
`implement-story`, etc.).

Token budgets in `aggregate-telemetry.py` (the `BUDGETS` dict) must stay in sync with
`kuraka-policies.md` and `rules/17-kuraka-token-optimizations.md`. These three places
are the only authoritative source of per-agent targets.

**Hard invariant** (enforced in `skills/kuraka.md` §Orchestrator constraint): the
orchestrator never writes to `backend/`, `frontend/`, `tests/`, or `migrations/` in a
consumer project before Phase 4 — all implementation must route through
`backend-developer` or `frontend-developer`. Editing `docs/`, `.claude/agents/`,
`.claude/skills/`, `.claude/rules/` is the only legitimate exception.

## Repo-specific gotchas

### `/docs/` and `/documentacion-backend/` are gitignored mirrors

Both top-level `/docs/` and `/documentacion-backend/` are **gitignored mirrors of
sie_v2 project docs**, not part of the framework. See `.gitignore` comments. Never
edit these assuming they ship with the framework — they don't. The framework's own
docs live inside `kuraka-artifacts/docs/` (note: `kuraka-artifacts/` is tracked).

### `rules/01-*.md` through `rules/15-*.md` are also gitignored

Those are sie_v2 team conventions that live in *that* project's git, not here. Only
`rules/16-agent-backup.md`, `17-kuraka-token-optimizations.md`,
`18-duplication-aware-refactor.md`, and `19-evidence.md` are framework rules
tracked by this repo. If you
need to edit a rule in the 01–15 range, you are in the wrong repository.

### The `VAULT=` path is hardcoded in three places

`mount-kuraka.sh`, `scripts/sync-obsidian.sh`, and the `00-RESTAURAR-PROYECTO.md`
one-liner all hardcode `/Users/xmn/Documents/Agentes/AgentesTrabajos/kuraka`. If the
vault is ever relocated, update all three (plus the alias block in
`dotfiles/zshrc-alias.md`).

### Branch switch workflow in consumer projects

`01-CAMBIO-DE-RAMA.md` is the canonical procedure. Summary: after `git switch` in the
consumer project, run `mount-kuraka` and then `/exit` + new Claude Code session —
subagents are registered at session start only.

## Docs that matter

- `README.md` — user-facing overview
- `00-RESTAURAR-PROYECTO.md` — legacy one-liner restore (alternative to `mount-kuraka.sh`)
- `01-CAMBIO-DE-RAMA.md` — branch-switch playbook for consumer projects
- `dotfiles/zshrc-alias.md` — alias/function to install in `~/.zshrc`
- `kuraka-artifacts/tests/kuraka/README.md` — what the eval harness does **not** test
  (no LLM invocation, no perf, no dynamic behavior — only structure/contracts)
