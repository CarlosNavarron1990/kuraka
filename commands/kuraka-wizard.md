---
description: "Guided, PLATFORM-AWARE Kuraka onboarding wizard. First detects which AI tool it's running in (Claude Code / Cursor / Codex / Antigravity), then verifies Kuraka is correctly mounted FOR THAT platform, then routes the project's next step (mount → inspect → amauta brownfield / inti+arki greenfield → ready-for-/kuraka). Re-runnable: each run advances one stage and reports state."
---

# Task: Kuraka onboarding wizard (multiplataforma)

Purpose: (1) figure out **which AI platform** you're running in, (2) verify Kuraka
is **correctly mounted for that platform**, (3) route the project to the right next
onboarding step. Re-run after each restart; it always reports state and advances the
next pending stage.

**Portability**: this wizard may run in Claude Code, Cursor, Codex or Antigravity,
on macOS/Linux/Windows. Do **not** assume `bash` — inspect the project with your own
file tools, or a shell command appropriate to the OS. Vault path comes from
`$KURAKA_VAULT`; the CLI is `kuraka` (Unix) / `kuraka` · `kuraka.cmd` (Windows).

## Step 0 — Detect the platform (do this FIRST)

Determine which environment you are running in. Infer it from **where this command
lives** plus **which artifacts exist**; if it's ambiguous, **ask the user**:
"¿En qué entorno estás usando Kuraka: Claude Code, Cursor, Codex o Antigravity?"

| Signal (this command's location / how it was invoked) | Platform |
|-------------------------------------------------------|----------|
| under `.claude/commands/`, and `.claude/agents/` exists | **Claude Code** |
| under `.cursor/commands/`, `AGENTS.md` + `.cursor/` exist | **Cursor** |
| invoked as `/prompts:…` from `~/.codex/prompts/`, `AGENTS.md` exists | **Codex** |
| under `.agent/workflows/`, `AGENTS.md` + `.agent/` exist | **Antigravity** |

**State the detected platform out loud before continuing.**

## Step 1 — Verify the mount is correct FOR THAT platform

Check the expected artifacts for the detected platform. Each platform mounts
differently — Claude Code uses native subagents under `.claude/`; the others adopt
roles via `AGENTS.md` + native slash-commands. If the expected artifacts are
missing, the mount for this platform hasn't run: give the user the exact command
and STOP.

| Platform | Must exist | If missing → run (from the project root) | Then |
|----------|-----------|-------------------------------------------|------|
| Claude Code | `.claude/agents/` (18 .md), `.claude/commands/`, `.claude/skills/` | `kuraka mount`  (elegí Claude) | restart Claude Code: `/exit` + new session (subagents register only at start) |
| Cursor | `AGENTS.md`, `.cursor/commands/`, `.cursor/rules/` | `kuraka mount --target cursor` | reiniciá el chat de Cursor (recarga `AGENTS.md`) |
| Codex | `AGENTS.md`, and prompts in `~/.codex/prompts/` | `kuraka mount --target codex` (luego copiá `.codex/prompts/*.md` → `~/.codex/prompts/`) | reabrí `codex` |
| Antigravity | `AGENTS.md`, `.agent/workflows/` | `kuraka mount --target antigravity` | recargá los workflows |

Report: the platform, whether it is **correctly mounted for that platform**, and
what (if anything) is missing. If the mount is missing, STOP here with the single
command to run and the restart note — do not proceed to Step 2.

## Step 2 — Project state (config + layer) — same across platforms

Once the platform mount is OK, check the project's Kuraka config (the project layer
lives in `.claude/project/` for **all** platforms — every agent/role reads it):

- `kuraka.config.yaml` present?
- `.claude/project/` layer present?
- any source files present (brownfield) or none (greenfield)? (heuristic: count
  `*.ts/js/py/go/rb/java/php/rs/vue` outside `.claude/`, `.git/`, `node_modules/`, `docs/`)
- **any design file** (`docs/*.pen`, a Figma URL in `kuraka.config.yaml`/`docs/`)? If
  present, it is the frontend's source of truth → `.claude/project/conventions/frontend-branding.md`
  must register it (design-file path + frame index screen→frame + tokens). A design
  that exists but isn't registered there is a gap the frontend agents won't honor.

Apply the FIRST matching rule, act, then report and close:

| # | Condition | Action |
|---|-----------|--------|
| A | config **and** layer both present | **Ready.** Validate if you can (`kuraka validate`). If a design file exists but `conventions/frontend-branding.md` doesn't register it (frame index + tokens), flag it as a `<TODO>` and offer to wire it — the `frontend-developer` only honors designs registered there. Then offer the two entry points: `/kuraka <requerimiento>`, or Discovery ("tengo una idea, no un requerimiento") for a fuzzy feature. Done. |
| B | no config **and** no source files → **greenfield** | Route to `inti` (discovery), then `arki` (architecture + config). In Claude these are `/inti` and `/arki`; in Cursor/Codex/Antigravity, adopt the `inti` then `arki` role. |
| C | no config **and** has source files → **brownfield** | Ensure the inspect report (if absent, run `kuraka inspect > inspect-report.json` or `python3 "$KURAKA_VAULT/kuraka-inspect.py" . > inspect-report.json`). Then run `amauta` (`/amauta` command or role) to generate `kuraka.config.yaml` + `.claude/project/` from the **real code** — golden rule: never invent, mark unknowns `<TODO>`. **Pass amauta any design file found above** (`.pen` path / Figma URL) so it registers it in `conventions/frontend-branding.md` — amauta seeds the same convention surface arki does (api-design, query-and-repository, frontend-branding, test-fixtures…), sourced from the detected code. |

## Step 3 — Always close with one clear next step

End every run with a single line: exactly what the user should do next (mount for
your platform + restart, resolve `<TODO>`s in `kuraka.config.yaml`, run `/kuraka`,
etc.). Never leave the user guessing which stage they're in.

## Notes

- **Platform first, mount-check second.** The wizard verifies the mount that matches
  the environment you're *actually* in — not just Claude. A Cursor mount has no
  `.claude/agents/` and that's correct; its "mount" is `AGENTS.md` + `.cursor/commands/`.
- Greenfield detection is heuristic. If the user says there's code but it shows 0
  (unusual languages / generated dirs), treat it as brownfield (rule C).
- The wizard writes no business code. It only mounts/inspects, generates the config +
  project layer (via `amauta`), and routes.
- `kuraka-init.py` (or `kuraka init`) is the external cold-start equivalent; use the
  wizard when Kuraka is already partly present in the project.
