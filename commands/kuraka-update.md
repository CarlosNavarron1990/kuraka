---
description: "Update the mounted Kuraka framework in THIS project from the vault (agents with harness capabilities, SKILL.md skills, hooks, rules, contexts, stack-profiles, templates, tests/kuraka). Uses the mount's --update mode: non-interactive, preserves overrides, and NEVER touches project history (docs/process/**, checkpoints, .claude/project/, kuraka.config.yaml). Requires a Claude Code restart afterward."
---

# Task: Update Kuraka framework in this project

Refresh the framework layer from the vault using the mount's dedicated
`--update` mode — it updates agents, skills, commands, rules, hooks and
artifacts, re-applies the project's overrides, and by design cannot touch
implementation history or project-specific content.

**Portability**: the vault location is NOT hardcoded. It is read from the
`KURAKA_VAULT` environment variable, falling back to the author's default
only if the variable is unset. On a different machine, set it once:
`export KURAKA_VAULT="/your/path/to/kuraka"` (put it in `~/.zshrc`).

## Steps

### 1. Pre-check for hand edits (safety)

Run:
```bash
git status --short .claude/ 2>/dev/null
```
If there are uncommitted changes inside `.claude/agents/` or `.claude/skills/`
(framework files that should normally be customized via `.claude/project/`,
not edited in place), report them to the user and ask whether to continue
before re-mounting — `rsync --update` would overwrite them if the vault copy
is newer.

### 2. Resolve the vault, find the project root, and mount

Run this block exactly. It resolves the vault from `$KURAKA_VAULT`
(portable), walks up from the current directory to find the project root
that contains `.claude/`, and mounts into it — so it works no matter which
subdirectory you launched from, and on any machine:

```bash
# --- portable vault resolution (env var first, fallback second) ---
VAULT="${KURAKA_VAULT:-/Users/xmn/Documents/Agentes/AgentesTrabajos/kuraka}"
if [ ! -d "$VAULT" ]; then
  echo "❌ Vault no encontrado en: $VAULT"
  echo "   Define la ruta correcta y reintenta:"
  echo "     export KURAKA_VAULT=\"/ruta/a/kuraka\"   # añádelo a ~/.zshrc para que persista"
  exit 1
fi

# --- find project root = nearest ancestor (incl. $PWD) with ANY mounted platform ---
DIR="$PWD"
has_platform() { [ -d "$1/.claude/agents" ] || [ -d "$1/.agents/agents" ] || [ -d "$1/.codex/agents" ] || [ -d "$1/.cursor/agents" ]; }
while [ "$DIR" != "/" ] && ! has_platform "$DIR"; do DIR="$(dirname "$DIR")"; done
if ! has_platform "$DIR"; then
  echo "❌ No hay un proyecto con Kuraka montado (.claude/.agents/.codex/.cursor) desde: $PWD"
  echo "   Corre /kuraka-update dentro de un proyecto que ya tenga Kuraka montado."
  exit 1
fi
PROJECT_ROOT="$DIR"

echo "🪢 vault:    $VAULT"
echo "🪢 proyecto: $PROJECT_ROOT"
echo ""

# --- framework-only refresh (non-interactive; history untouched by design) ---
bash "$VAULT/mount-kuraka.sh" "$PROJECT_ROOT" --update
```

The `--update` mode guarantees it does **NOT** modify `kuraka.config.yaml`,
`.claude/project/` (conventions, lessons-learned, glossary, promoted experts),
`docs/process/**` (REQ, stories, checkpoints, retros, telemetry,
lessons-learned), or the vault registry — and it re-applies your
project-specific overrides after the copy (the override always wins).

**Platform-aware**: without `--target`, the mode auto-detects which platform(s)
are already mounted in the project (`.claude` / `.agents` / `.codex` /
`.cursor`) and refreshes EACH with its own render — Claude-only material
(harness frontmatter, hooks, SKILL.md invocability keys) never reaches
Antigravity/Codex/Cursor, and vice versa. It refuses to first-mount a platform
that isn't there (use the full mount for that).

### 3. Report what changed

Summarize the script output: which categories had new/updated files
(`+ skills/`, `+ commands/`, `✓ templates/`, etc.). Call out notable
additions when present.

### 4. Validate (optional but recommended)

```bash
VAULT="${KURAKA_VAULT:-/Users/xmn/Documents/Agentes/AgentesTrabajos/kuraka}"
DIR="$PWD"; while [ "$DIR" != "/" ] && [ ! -d "$DIR/.claude" ]; do DIR="$(dirname "$DIR")"; done
bash "$VAULT/validate-kuraka.sh" "$DIR"
```
Report PASS/FAIL. If it fails, show the offending agent/skill frontmatter.

### 5. Tell the user to restart

End by reminding the user — this is MANDATORY:

> "Listo. Reinicia Claude Code (`/exit` + sesión nueva) para que se
>  registren las skills/agentes/commands nuevos — se registran solo al
>  inicio de sesión."

## Notes

- This only updates the framework. It does NOT re-run `amauta`,
  `kuraka-inspect`, or regenerate `kuraka.config.yaml`.
- The vault path is portable via `$KURAKA_VAULT`. If the script reports the
  vault is not found, export `KURAKA_VAULT` to the right path (and add it to
  `~/.zshrc`). The same variable is honored by `mount-kuraka.sh` and the
  shell alias, so set it once per machine.
