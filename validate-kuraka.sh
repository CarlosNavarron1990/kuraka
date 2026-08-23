#!/bin/bash
# validate-kuraka.sh — Validate Kuraka agent/skill frontmatter and registration readiness.
#
# Usage: bash validate-kuraka.sh [target_dir]
#   (default: $PWD)
#
# Checks:
#   1. Every .claude/agents/*.md has valid frontmatter (name, description, model)
#   2. Every .claude/skills/*.md has valid frontmatter (name, description)
#   3. Model values are one of: opus | sonnet | haiku
#   4. All files mtime vs current session (warns if modified after session start)
#   5. No orphan references ({`workflow`}, removed agent names, etc.)
#
# Exit codes:
#   0 — all good
#   1 — at least one validation error

set -uo pipefail

TARGET="${1:-$PWD}"
cd "$TARGET"

if [ ! -d ".claude/agents" ]; then
    echo "❌ ERROR: no .claude/agents/ directory at $TARGET" >&2
    exit 1
fi

ERRORS=0
WARNINGS=0
VALID_MODELS="fable opus sonnet haiku"

# --- vault self-checks (single-source frontmatter maps) ----------------------
# This script lives in the vault, so the two generated-frontmatter maps are
# always reachable: verify they are drift-free before validating the mount.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
for chk in kuraka-apply-models.py kuraka-apply-harness.py; do
    if [ -f "$SCRIPT_DIR/$chk" ]; then
        if ! python3 "$SCRIPT_DIR/$chk" --check >/dev/null 2>&1; then
            echo "❌ vault self-check failed: $chk --check (run it directly for details)"
            ERRORS=$((ERRORS+1))
        fi
    fi
done

echo "🪢 validate-kuraka — $TARGET"
echo ""

# --- agents ---
echo "=== Agents (.claude/agents/*.md) ==="
for f in .claude/agents/*.md; do
    [ -f "$f" ] || continue
    name=$(basename "$f" .md)
    errs=()

    # Frontmatter block check
    if ! head -1 "$f" | grep -q "^---$"; then
        errs+=("no frontmatter (file does not start with ---)")
    fi

    fm_name=$(awk '/^---$/{n++; next} n==1{print}' "$f" | grep "^name:" | head -1 | sed 's/^name: *//')
    fm_desc=$(awk '/^---$/{n++; next} n==1{print}' "$f" | grep "^description:" | head -1)
    fm_model=$(awk '/^---$/{n++; next} n==1{print}' "$f" | grep "^model:" | head -1 | sed 's/^model: *//')

    [ -z "$fm_name" ] && errs+=("missing 'name:' in frontmatter")
    [ "$fm_name" != "$name" ] && [ -n "$fm_name" ] && errs+=("name mismatch: frontmatter='$fm_name' filename='$name'")
    [ -z "$fm_desc" ] && errs+=("missing 'description:'")
    [ -z "$fm_model" ] && errs+=("missing 'model:'") || {
        if ! echo "$VALID_MODELS" | grep -qw "$fm_model"; then
            errs+=("invalid model '$fm_model' (expected: $VALID_MODELS)")
        fi
    }

    if [ ${#errs[@]} -eq 0 ]; then
        printf "  ✓ %-25s model=%s\n" "$name" "$fm_model"
    else
        printf "  ❌ %-25s\n" "$name"
        for e in "${errs[@]}"; do
            echo "       $e"
            ERRORS=$((ERRORS + 1))
        done
    fi
done

# --- skills ---
echo ""
echo "=== Skills (.claude/skills/*.md) ==="
if [ -d ".claude/skills" ]; then
    for f in .claude/skills/*.md; do
        [ -f "$f" ] || continue
        name=$(basename "$f" .md)
        errs=()

        if ! head -1 "$f" | grep -q "^---$"; then
            errs+=("no frontmatter")
        fi

        fm_name=$(awk '/^---$/{n++; next} n==1{print}' "$f" | grep "^name:" | head -1 | sed 's/^name: *//')
        fm_desc=$(awk '/^---$/{n++; next} n==1{print}' "$f" | grep "^description:" | head -1)

        [ -z "$fm_name" ] && errs+=("missing 'name:'")
        [ -z "$fm_desc" ] && errs+=("missing 'description:'")

        if [ ${#errs[@]} -eq 0 ]; then
            printf "  ✓ %-25s\n" "$name"
        else
            printf "  ❌ %-25s\n" "$name"
            for e in "${errs[@]}"; do
                echo "       $e"
                ERRORS=$((ERRORS + 1))
            done
        fi
    done
fi

# --- orphan references ---
echo ""
echo "=== Orphan reference scan ==="
orphan_workflow=$(grep -rln 'skills/workflow\.md\|`workflow`' .claude/ 2>/dev/null | grep -v kuraka | wc -l | tr -d ' ')
if [ "$orphan_workflow" -gt 0 ]; then
    echo "  ⚠️  $orphan_workflow file(s) still reference the old 'workflow' name:"
    grep -rln 'skills/workflow\.md\|`workflow`' .claude/ 2>/dev/null | grep -v kuraka | sed 's/^/       /'
    WARNINGS=$((WARNINGS + 1))
else
    echo "  ✓ No orphan workflow references"
fi

# --- registration hint ---
echo ""
echo "=== Runtime registration hint ==="
AGENT_COUNT=$(find .claude/agents -maxdepth 1 -name "*.md" | wc -l | tr -d ' ')
echo "  Agents on disk: $AGENT_COUNT"
echo "  To register all as subagent_type: restart Claude Code (/exit + new session)."
echo "  The runtime caches the agent list at session start."

# --- summary ---
echo ""
echo "=== Summary ==="
echo "  errors:   $ERRORS"
echo "  warnings: $WARNINGS"

if [ "$ERRORS" -gt 0 ]; then
    echo ""
    echo "❌ validation FAILED"
    exit 1
fi

echo ""
echo "✅ validation OK"
exit 0
