# Kuraka process artifacts live at REPO ROOT `docs/process/`

> Established 2026-06-26 — recurring agent path-confusion across cycles.

## The rule

ALL Kuraka process artifacts resolve from the **repository root**, NOT from `backend/`:

| Artifact | Path (repo root) |
|---|---|
| REQ | `docs/process/REQ-<date>-<slug>.md` |
| Stories | `docs/process/stories/REQ-<date>-<slug>-S<n>.md` |
| Test plan | `docs/process/test-plans/…` |
| Frozen schema | `docs/process/schemas/SCHEMA-FROZEN-…md` |
| Checkpoint | `docs/process/checkpoints/…-state.json` |
| Telemetry | `docs/process/agent-telemetry/…-telemetry.json` |
| RETRO | `docs/process/retros/RETRO-…md` (canonical; also mirrored to `agent-retrospectives/` for the archiver) |

**Never write any of these under `backend/docs/process/`.** Several agents (po-analyst,
architect-reviewer) have repeatedly created `backend/docs/process/…` by resolving a relative path
against a backend-centric working context. Before writing a process artifact, confirm the absolute
target is `<repo-root>/docs/process/…`.

## Cross-check before declaring a "missing artifact" BLOCKER

If a reviewer cannot find a story/REQ/schema, it has almost always been written to the correct
repo-root `docs/process/…` — look there before raising a BLOCKER. (REQ-20260626 architect raised a
false "stories absent" blocker; the stories were at repo root.)

## RETRO directory consolidation (open debt)

There are currently three RETRO locations with drifting `RETRO-LATEST.md`:
`docs/process/retros/`, `docs/process/agent-retrospectives/`, and a stale
`backend/docs/process/agent-retrospectives/`. The archiver + `output-schemas.md` treat
`agent-retrospectives/` as canonical. Consolidate to ONE dir (or symlink) so `pattern-detector`
reads a complete corpus. Until then, pattern-detector MUST read all three.
