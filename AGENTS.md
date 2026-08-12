# Repository Guidelines

## Project Structure & Module Organization

Kuraka is a framework vault, not an application. Root-level Python scripts (`kuraka.py`, `kuraka-mount.py`, `kuraka-init.py`, `kuraka-backup.py`) provide the CLI and lifecycle tooling. Framework content lives in `agents/`, `skills/`, `commands/`, and `rules/`; these are mounted into consumer projects under `.claude/` or exported for other agent environments. Shared schemas, stack profiles, docs templates, and structural tests live in `kuraka-artifacts/`. Static brand assets are in `assets/`, operational docs are root Markdown files, and project history snapshots are stored under `projects/`.

## Build, Test, and Development Commands

There is no package manager or build step; scripts use Python 3 and POSIX shell only.

- `python3 kuraka.py doctor`: check local Kuraka installation readiness.
- `python3 kuraka-init.py [target_dir]`: inspect, configure, scaffold, mount, and register a target project.
- `python3 kuraka-mount.py [target_dir]`: mount the current vault into a consumer project.
- `bash validate-kuraka.sh [target_dir]`: validate mounted `.claude/agents` and `.claude/skills` frontmatter.
- `python3 kuraka-apply-models.py --check`: verify `MODEL-ROUTING.yaml` and agent frontmatter are in sync.
- `cd <target-project> && python3 -m pytest tests/kuraka/ -v`: run the mounted structural eval harness.

## Coding Style & Naming Conventions

Keep Python scripts dependency-free and compatible with direct `python3 script.py` execution. Prefer small, explicit functions and standard-library modules. Use `snake_case` for Python identifiers and kebab-case filenames for Markdown framework components, matching existing names such as `backend-developer.md` and `analyze-requirement.md`. Agent frontmatter `name` must match the filename stem; skill files require `name` and `description`. Do not hand-edit agent `model:` values; update `MODEL-ROUTING.yaml` and run `kuraka-apply-models.py`.

## Testing Guidelines

Use `validate-kuraka.sh` after editing mounted agent or skill definitions. For framework test changes, mount into a fixture or consumer project and run `python3 -m pytest tests/kuraka/ -v` there. Keep structural tests focused on mount output, frontmatter contracts, registration readiness, and schema compatibility.

## Commit & Pull Request Guidelines

Git history uses concise Conventional Commit-style messages: `feat(scope): ...`, `fix(scope): ...`, or `feat: ...`. Prefer a scope when the change is localized, for example `fix(overrides): ...` or `feat(models): ...`. Pull requests should explain the framework behavior changed, list validation commands run, and call out any impact on mounted consumer projects. Include screenshots only for asset or documentation-rendering changes.

## Agent-Specific Instructions

Edit vault files as the source of truth. Preserve project-specific override behavior: do not delete or rewrite `projects/<slug>/overrides/` unless the task explicitly concerns override cleanup. Prefer backtick references such as `backend-developer` over Obsidian wikilinks in runtime-facing files.
