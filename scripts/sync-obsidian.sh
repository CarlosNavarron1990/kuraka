#!/bin/bash
# DEPRECATED — scheduled for removal in migration Fase 4.
#
# This bidirectional .claude/ <-> vault sync is being replaced by a one-way
# model in which the framework lives in its own versioned repo pinned via
# `kuraka.lock` in each consumer project. Consumers don't sync back to the
# vault; they upgrade explicitly when they choose to. For Obsidian visibility,
# prefer a symlink over running this script.
#
# Until Fase 4 lands this script still works for the legacy workflow, but
# DO NOT add new dependencies on it.
#
# See 02-MIGRACION-FRAMEWORK.md (Fases 1, 4) for the migration plan.
# ----------------------------------------------------------------------------
#
# Sync .claude/ content to Obsidian vault, converting backtick refs to wikilinks.
#
# Direction: .claude/ (local) --> Obsidian vault (backup)
# Called by Claude Code hook after any .claude/ file is modified.
#
# SAFETY GUARDS:
# 1. Aborts each category independently if local has < 80% of vault files.
#    This prevents wiping the vault when the branch has an incomplete .claude/
#    state (e.g., just switched branches and haven't restored from vault yet).
# 2. If a local category is empty but vault has files, that category is skipped.
#
# If the guard fires, restore first with: /sync-from-vault (or claude-sync alias)

set -euo pipefail

CLAUDE_DIR="$(cd "$(dirname "$0")/../.claude" && pwd)"
OBSIDIAN_DIR="${KURAKA_VAULT:-/Users/xmn/Documents/Agentes/AgentesTrabajos/kuraka}"

# ---------------------------------------------------------------------------
# Current agent and skill names (keep in sync with .claude/agents/ and .claude/skills/)
# These generate wikilink replacements: `name` --> [[name]] for Obsidian graph
# ---------------------------------------------------------------------------

AGENTS=(
  po-analyst
  story-refiner
  test-engineer
  architect-reviewer
  backend-developer
  frontend-developer
  code-reviewer
  security-reviewer
  migration-reviewer
  e2e-tester
  deployment-verifier
  final-auditor
  pattern-detector
  deploy-diagnostician
  provider-contract-validator
  jira-ticket-sync
)

SKILLS=(
  facilitate-discovery
  seed-project-conventions
  analyze-requirement
  refine-stories
  plan-tests
  review-stories
  review-implementation
  review-migrations
  schema-freeze
  implement-story
  security-audit
  analyze-testability
  generate-unit-tests
  generate-endpoint-tests
  generate-e2e-tests
  validate-coverage
  write-tests
  verify-deployment
  verify-output
  run-audit
  detect-patterns
  compact-context
  workflow
  diagnose-deploy
)

# ---------------------------------------------------------------------------
# Ensure destination directories exist
# ---------------------------------------------------------------------------

mkdir -p "$OBSIDIAN_DIR"/{agents,skills,commands,rules}
mkdir -p "$OBSIDIAN_DIR/agents/contexts"

# ---------------------------------------------------------------------------
# Safety check: abort sync of a category if local count < 80% of vault count.
# Vault count of 0–2 is considered "new category" and always synced.
# ---------------------------------------------------------------------------

is_safe_to_sync() {
  local subpath="$1"
  local src="$CLAUDE_DIR/$subpath"
  local dest="$OBSIDIAN_DIR/$subpath"

  local src_count=0
  local dest_count=0
  if [ -d "$src" ]; then
    src_count=$(find "$src" -maxdepth 1 -name "*.md" 2>/dev/null | wc -l | tr -d ' ')
  fi
  if [ -d "$dest" ]; then
    dest_count=$(find "$dest" -maxdepth 1 -name "*.md" 2>/dev/null | wc -l | tr -d ' ')
  fi

  # New category (vault has 0–2 files) — always sync
  if [ "$dest_count" -le 2 ]; then
    return 0
  fi

  # Calculate 80% threshold
  local threshold=$((dest_count * 80 / 100))
  if [ "$src_count" -lt "$threshold" ]; then
    echo "[sync-obsidian] SKIP $subpath (local=$src_count < 80% of vault=$dest_count). Run /sync-from-vault first." >&2
    return 1
  fi
  return 0
}

# ---------------------------------------------------------------------------
# Build single sed expression for all wikilink conversions
# ---------------------------------------------------------------------------

build_sed_expression() {
  local expr=""
  for name in "$@"; do
    expr+="s/\`${name}\`/[[${name}]]/g;"
  done
  # Trim trailing semicolon
  echo "${expr%;}"
}

SED_EXPR="$(build_sed_expression "${AGENTS[@]}" "${SKILLS[@]}")"

# ---------------------------------------------------------------------------
# Sync one directory.
#   convert_wikilinks=true  -> apply backtick→[[wikilink]] conversion (docs)
#   convert_wikilinks=false -> verbatim copy (executables, rules)
# ---------------------------------------------------------------------------

sync_dir() {
  local src_dir="$1"
  local dest_dir="$2"
  local convert_wikilinks="${3:-true}"

  [ -d "$src_dir" ] || return 0
  mkdir -p "$dest_dir"

  for src_file in "$src_dir"/*.md; do
    [ -f "$src_file" ] || continue
    local filename
    filename=$(basename "$src_file")
    local dest_file="$dest_dir/$filename"
    if [ "$convert_wikilinks" = "true" ]; then
      sed "$SED_EXPR" "$src_file" > "$dest_file"
    else
      cp "$src_file" "$dest_file"
    fi
  done
}

# ---------------------------------------------------------------------------
# Run sync per category with safety check.
#
# Wikilinks are ONLY applied to categories where Obsidian's graph view adds
# value AND the files are never executed: agents, agents/contexts, skills, rules.
#
# Commands are copied verbatim — they are executable prompts where converting
# backticks to [[wikilinks]] would break grep patterns and embedded code examples.
# ---------------------------------------------------------------------------

is_safe_to_sync "agents"          && sync_dir "$CLAUDE_DIR/agents"          "$OBSIDIAN_DIR/agents"          true
is_safe_to_sync "agents/contexts" && sync_dir "$CLAUDE_DIR/agents/contexts" "$OBSIDIAN_DIR/agents/contexts" true
is_safe_to_sync "skills"          && sync_dir "$CLAUDE_DIR/skills"          "$OBSIDIAN_DIR/skills"          true
is_safe_to_sync "commands"        && sync_dir "$CLAUDE_DIR/commands"        "$OBSIDIAN_DIR/commands"        false
is_safe_to_sync "rules"           && sync_dir "$CLAUDE_DIR/rules"           "$OBSIDIAN_DIR/rules"           true

exit 0
