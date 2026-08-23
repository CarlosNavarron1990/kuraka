#!/bin/bash
# Kuraka review mechanics — the deterministic half of the reviewers' directed
# checks, run by the ORCHESTRATOR at ~0 model cost before Phase 5 / 5.5. The
# output (markdown) goes into the reviewer digest; the reviewer ADJUDICATES
# these results (false positives, severity) instead of spending frontier-model
# turns running greps.
#
# Usage:  bash .claude/hooks/review_mechanics.sh [changed-file ...]
#   With file args: greps scope to those files. Without: scans the configured
#   backend/frontend roots from kuraka.config.yaml.
set -u
CONFIG="kuraka.config.yaml"
[ -f "$CONFIG" ] || { echo "review_mechanics: no kuraka.config.yaml here" >&2; exit 1; }

cfg() { grep -E "^[[:space:]]*$1:" "$CONFIG" | head -1 | sed -E 's/^[^:]+:[[:space:]]*"?([^"#]*[^"# ])"?.*/\1/'; }
BACK=$(cfg backend_root); FRONT=$(cfg frontend_root)
SCOPE=("$@")
[ ${#SCOPE[@]} -eq 0 ] && SCOPE=($(for d in "$BACK" "$FRONT"; do [ -n "$d" ] && [ -d "$d" ] && echo "$d"; done))
[ ${#SCOPE[@]} -eq 0 ] && { echo "review_mechanics: nothing to scan" >&2; exit 1; }

section() { echo; echo "### $1"; }
hits() {  # hits <label> <grep-args...> — prints matches or OK
    local label="$1"; shift
    local out
    out=$(grep -rn "$@" "${SCOPE[@]}" 2>/dev/null | grep -v -E 'node_modules|\.venv|dist/|build/|\.min\.' | head -30)
    if [ -n "$out" ]; then
        echo "- ⚠ ${label}:"
        echo '```'
        echo "$out"
        echo '```'
    else
        echo "- ✓ ${label}: 0 matches"
    fi
}

echo "## Review mechanics — deterministic pre-checks"
echo "_Scope: ${SCOPE[*]} — adjudicate each ⚠ (false positive vs finding + severity)._"

section "Secret scan (CRITICAL if real)"
hits "hardcoded password" -E "password[[:space:]]*=[[:space:]]*['\"][^'\"]+['\"]" --include='*.py' --include='*.js' --include='*.ts'
hits "hardcoded api_key"  -E "api_key[[:space:]]*=[[:space:]]*['\"][^'\"]+['\"]"  --include='*.py' --include='*.js' --include='*.ts'
hits "hardcoded secret"   -E "secret[[:space:]]*=[[:space:]]*['\"][^'\"]+['\"]"   --include='*.py' --include='*.js' --include='*.ts'
hits "private key block"  -F "BEGIN RSA PRIVATE KEY"
hits "inline bearer token" -E "Bearer [A-Za-z0-9_\-]{16,}" --include='*.py' --include='*.js' --include='*.ts'

section "Production output hygiene"
hits "console.log in frontend" -E "console\.log\(" --include='*.ts' --include='*.tsx' --include='*.vue' --include='*.js'
hits "bare print() in backend" -E "^[[:space:]]*print\(" --include='*.py'
hits "commented-out code (heuristic)" -E "^[[:space:]]*(#|//)[[:space:]]*(def |class |function |const |return |await )" --include='*.py' --include='*.ts' --include='*.js'

section "Frontend directed checks"
hits "namespace type-imports (React.X in type position)" -E ":[[:space:]]*React\.[A-Z]" --include='*.ts' --include='*.tsx'
hits "double submit wiring (ngSubmit + click on same form-file)" -l -E "ngSubmit" --include='*.html' --include='*.ts'
# design tokens: referenced var(--x) with no definition
if [ -n "$FRONT" ] && [ -d "$FRONT" ]; then
    refs=$(grep -rhoE 'var\(--[A-Za-z0-9_-]+\)' "$FRONT" 2>/dev/null | sort -u | sed -E 's/var\((--[^)]+)\)/\1/')
    missing=""
    for t in $refs; do
        grep -rq -- "${t}:" "$FRONT" 2>/dev/null || missing="$missing $t"
    done
    if [ -n "$missing" ]; then
        echo "- ⚠ design tokens referenced but never defined:$missing"
    else
        echo "- ✓ design tokens: all referenced var(--x) are defined"
    fi
fi

section "Backend directed checks"
hits "imports inside functions (py)" -E "^[[:space:]]{4,}(import |from [a-zA-Z_.]+ import )" --include='*.py'
hits "cache invalidation sites (enumerate sub-keys manually)" -E "(invalidate|delete)\(.*(KEY|cache)" --include='*.py' --include='*.ts'

echo
echo "_End of mechanics. The reviewer keeps ownership of judgment checks:_"
echo "_contract cross-check semantics, scope-fidelity diff, silent deviation,_"
echo "_severity adjudication._"
