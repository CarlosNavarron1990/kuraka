#!/usr/bin/env bash
# Batería del hook de Claude de validar-pr: el hook de Kuraka pr_gate.py (montado en
# <plataforma>/hooks/; en el vault, hooks/). Ejecutar tras cualquier cambio en el hook:
#   bash .claude/skills/validar-pr/scripts/test-hook-claude.sh
# Cada caso: código esperado (0 permitir, 2 bloquear) y comando. El proyecto de prueba es un
# directorio temporal que ADOPTÓ validar-pr (capa con config.sh). Los primeros casos corren
# SIN repo git (la puerta de PR falla en cerrado); los últimos, en un repo temporal.
set -uo pipefail
# Dentro de un hook de git llegan GIT_DIR, GIT_INDEX_FILE, GIT_CONFIG_PARAMETERS…: sin
# quitarlos, los git init/commit de prueba actuarían sobre el repo REAL. Se limpian todos.
for v in $(git rev-parse --local-env-vars 2>/dev/null) GIT_CONFIG_PARAMETERS GIT_CONFIG_COUNT GIT_EXEC_PATH; do unset "$v"; done
unset VALIDAR_PR_DENTRO
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HOOK="${PR_GATE:-$DIR/../../../hooks/pr_gate.py}"
[ -f "$HOOK" ] || { echo "no encuentro el hook pr_gate.py en $HOOK (exporta PR_GATE=<ruta>)"; exit 1; }
PY=""; for c in python3 python py; do command -v "$c" >/dev/null 2>&1 && "$c" -c 'import sys; sys.exit(sys.version_info < (3, 8))' >/dev/null 2>&1 && { PY="$c"; break; }; done
[ -n "$PY" ] || { echo "falta Python 3"; exit 1; }
export PYTHONUTF8=1
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
mkdir -p "$TMP/.claude/project/validar-pr"
echo 'VP_RAMAS_PROTEGIDAS="main master develop dev release"' > "$TMP/.claude/project/validar-pr/config.sh"
fallos=0; total=0
caso() {
  local esperado="$1" cmd="$2" rc json
  json="$("$PY" -c 'import json,sys; print(json.dumps({"tool_input":{"command":sys.argv[1]}}))' "$cmd")"
  rc="$(cd "$TMP" && printf '%s' "$json" | CLAUDE_PROJECT_DIR="$TMP" "$PY" "$HOOK" >/dev/null 2>&1; echo $?)"
  total=$((total + 1))
  if [ "$rc" != "$esperado" ]; then fallos=$((fallos + 1)); echo "✗ esperado $esperado, sale $rc: $cmd"; fi
}
crudo() {  # $1 = esperado, $2 = entrada NO JSON
  local rc; rc="$(cd "$TMP" && printf '%s' "$2" | CLAUDE_PROJECT_DIR="$TMP" "$PY" "$HOOK" >/dev/null 2>&1; echo $?)"
  total=$((total + 1))
  if [ "$rc" != "$1" ]; then fallos=$((fallos + 1)); echo "✗ esperado $1, sale $rc (no JSON): $2"; fi
}
# --- permitidos: los commits y lo que no sea PR ni subida a rama protegida pasan siempre
caso 0 'git commit -m "x -n y"'
caso 0 'git commit --amend --no-edit'
caso 0 'git commit -n -m wip'
caso 0 'git commit --no-verify -m a'
caso 0 'HUSKY=0 git commit -m a'
caso 0 'git merge origin/dev'
caso 0 'git config core.hooksPath'
caso 0 'git push -u origin chore/x && gh pr list --base develop'
caso 0 'git push origin feat/dev'
caso 0 'git push -o ci.skip origin feat/x'
caso 0 'echo dev && git status'
caso 0 'git commit -m "no hagas git push origin main"'
caso 0 "cat <<'EOF'
doesn't matter
EOF"
# --- bloqueados: subir directo a una rama protegida, o saltando el pre-push
caso 2 'git push --no-verify origin feat/x'
caso 2 'git push --no-verify'
caso 2 'HUSKY=0 git push origin feat/x'
caso 2 'git -c core.hooksPath=/dev/null push'
caso 2 'git push origin develop'
caso 2 'git push origin +HEAD:refs/heads/main'
caso 2 'git push -o ci.skip origin dev'
caso 2 'git -C . push origin dev'
caso 2 "sh -c 'git push origin main'"
caso 2 'command git push origin release'
caso 2 "cat <<'EOF'
doesn't
EOF
git push origin main"
# gh pr create fuera de git: no se puede leer HEAD → falla en cerrado.
caso 2 'gh pr create --title x'
# Entrada ilegible: se bloquea solo lo que vigila la puerta.
crudo 2 'no es json: gh pr create'
crudo 2 'no es json: git push origin feat/x'
crudo 0 'no es json: git commit -m x'
crudo 0 'no es json: ls -la'
# Dentro de un repo temporal sin informe (config global aislada para que no influya).
GIT_CONFIG_GLOBAL=/dev/null git -C "$TMP" init -q \
  && GIT_CONFIG_GLOBAL=/dev/null git -C "$TMP" -c user.email=t@t -c user.name=t -c commit.gpgsign=false commit -q --allow-empty -m init \
  || { echo "no se pudo preparar el repo temporal"; exit 1; }
# Guarda: el repo de pruebas tiene que ser el del directorio temporal, nunca otro.
# En Git Bash (Windows) git da C:/… y pwd -P da /c/…: pwd -W da la forma de git.
case "$(cd "$TMP" && git rev-parse --absolute-git-dir 2>/dev/null)" in "$(cd "$TMP" && { pwd -W 2>/dev/null || pwd -P; })"/.git) ;; *)
  echo "ABORTO: el repo de pruebas no está en $TMP"; exit 1 ;; esac
caso 2 'gh pr -R org/x create --title x'
caso 2 'gh pr create --repo=org/x --title x'
caso 2 'gh pr new --title x'
caso 2 'gh pr create --title x'
caso 2 'gh -R org/x pr create --title x'
caso 2 'gh pr ready 12'
caso 0 'gh pr list'
# Subida sin destino: manda la rama actual y su upstream (rama creada con tracking a develop).
GIT_CONFIG_GLOBAL=/dev/null git -C "$TMP" checkout -q -B develop
caso 2 'git push'
caso 2 'git push origin HEAD'
GIT_CONFIG_GLOBAL=/dev/null git -C "$TMP" remote add origin "$TMP/no-existe.git"
GIT_CONFIG_GLOBAL=/dev/null git -C "$TMP" update-ref refs/remotes/origin/develop HEAD
GIT_CONFIG_GLOBAL=/dev/null git -C "$TMP" checkout -q -b feat/con-tracking --track origin/develop
caso 2 'git push'
GIT_CONFIG_GLOBAL=/dev/null git -C "$TMP" checkout -q -b feat/limpia --no-track
caso 0 'git push'
caso 0 'git push origin HEAD'
caso 0 'git push -u origin feat/limpia'
# Informe CAMBIOS cuyo texto cita la marca de aprobado: NO pasa (solo vale la 1.ª línea).
mkdir -p "$TMP/.git/validar-pr"
H="$(git -C "$TMP" rev-parse HEAD)"; B0="$(printf '0%.0s' $(seq 1 40))"
printf '<!-- validar-pr sha=%s base=%s veredicto=CAMBIOS -->\nel revisor cita: <!-- validar-pr sha=%s base=%s veredicto=APROBABLE -->\n' "$H" "$B0" "$H" "$B0" > "$TMP/.git/validar-pr/$H.md"
caso 2 'gh pr create --title x'
# Informe APROBABLE de OTRO commit: no pasa.
printf '<!-- validar-pr sha=%s base=%s veredicto=APROBABLE -->\n' "$B0" "$B0" > "$TMP/.git/validar-pr/$H.md"
caso 2 'gh pr create --title x'
# Con informe APROBABLE del commit actual, sí pasa.
printf '<!-- validar-pr sha=%s base=%s veredicto=APROBABLE -->\n' "$H" "$B0" > "$TMP/.git/validar-pr/$H.md"
caso 0 'gh pr create --title x'
caso 0 'gh -R org/x pr create --title x'
# Convivencia: si el proyecto versiona SU validar-pr, la puerta de Kuraka no actúa (no doble gate).
rm -f "$TMP/.git/validar-pr/$H.md"
mkdir -p "$TMP/.claude/skills/validar-pr"; echo propia > "$TMP/.claude/skills/validar-pr/SKILL.md"
GIT_CONFIG_GLOBAL=/dev/null git -C "$TMP" add .claude/skills/validar-pr/SKILL.md
caso 0 'gh pr create --title x'
caso 0 'git push origin main'
GIT_CONFIG_GLOBAL=/dev/null git -C "$TMP" rm -q --cached .claude/skills/validar-pr/SKILL.md
caso 2 'gh pr create --title x'
# enforce_hook: false la apaga.
printf 'workflow:\n  validar_pr:\n    enforce_hook: false\n' > "$TMP/kuraka.config.yaml"
caso 0 'gh pr create --title x'
rm -f "$TMP/kuraka.config.yaml"
# Sin capa ni config.sh: el proyecto no adoptó validar-pr → inerte.
rm -rf "$TMP/.claude/project"
caso 0 'gh pr create --title x'
caso 0 'git push origin main'
echo "$((total - fallos))/$total casos OK"
[ "$fallos" -eq 0 ]
