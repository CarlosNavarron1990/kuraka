#!/usr/bin/env bash
# Validación COMPLETA antes de abrir o actualizar una PR.
#   bash .claude/skills/validar-pr/scripts/validar-pr.sh            → valida e informa
#   bash .claude/skills/validar-pr/scripts/validar-pr.sh --crear-pr → valida y, si sale bien,
#        crea la PR (o actualiza la existente) con el informe en la descripción.
#   … --base main → valida y abre la PR contra otra rama base (por defecto, la del config.sh,
#        o workflow.base_branch de kuraka.config.yaml).
#   … --completa  → revisión con IA de toda la PR aunque haya una validación anterior.
# Pasos (lo barato primero; la IA solo si todo lo mecánico está en verde):
#   copia aislada (clon local) en el commit actual + fusión con la base · normativas, lint y secretos
#   de todo el diff · suite oficial (config.sh) · revisión con IA (claude -p, sin
#   contexto del autor): de toda la PR la primera vez y, en las siguientes, solo de lo nuevo
#   desde la última validación; prueba de punta a punta solo si cambia código que se ejecuta.
#   Informe en .git/validar-pr/<sha>.md
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"
source "$(dirname "${BASH_SOURCE[0]}")/comun.sh"

CREAR_PR=0; TITULO=""; BASE_PEDIDA=""; COMPLETA=0
while [ $# -gt 0 ]; do
  case "$1" in
    --crear-pr) CREAR_PR=1 ;;
    --completa) COMPLETA=1 ;;
    # Otra rama base (p. ej. main para un hotfix o para llevar un cambio de herramientas a
    # producción sin arrastrar lo pendiente de la base).
    --base) [ $# -ge 2 ] || { vp_rojo "--base necesita una rama"; exit 64; }; shift; BASE_PEDIDA="$1" ;;
    --titulo) [ $# -ge 2 ] || { vp_rojo "--titulo necesita un valor"; exit 64; }; shift; TITULO="$1" ;;
    *) vp_rojo "Opción desconocida: $1"; exit 64 ;;
  esac; shift
done

[ -n "$BASE_PEDIDA" ] && VP_RAMA_BASE="$BASE_PEDIDA"
VP_PY="$(vp_python)" || { vp_rojo "Falta Python 3 (Windows: winget install Python.Python.3.12; Mac: xcode-select --install)."; exit 2; }
RAMA="$(git branch --show-current)"
[ -n "$RAMA" ] || { vp_rojo "Estás en HEAD suelto: cámbiate a tu rama."; exit 1; }
for _p in $VP_RAMAS_PROTEGIDAS "$VP_RAMA_BASE"; do
  [ "$RAMA" = "$_p" ] && { vp_rojo "Estás en $RAMA: las PR salen de una rama feature (git switch -c tipo/PROJ-123-descripcion --no-track origin/$VP_RAMA_BASE)."; exit 1; }
done
if [ -n "$(git status --porcelain --untracked-files=no)" ]; then
  vp_rojo "Hay cambios sin commitear. Se valida lo commiteado: commitea o guárdalo con git stash."; exit 1
fi

git fetch -q origin "$VP_RAMA_BASE"
SHA="$(git rev-parse HEAD)"; CORTO="${SHA:0:8}"
BASE_SHA="$(git rev-parse "origin/$VP_RAMA_BASE")"
INFORME="$VP_INFORMES/$SHA.md"
PROY="vp$(basename "$VP_RAIZ" | tr -cd 'a-z0-9' | head -c 10)$CORTO"
# Ruta distinta de la del estado del stack ($TMPDIR/validar-pr-<p> o vp-stack-<p>): si no,
# los ficheros del stack caerían dentro del worktree que se revisa.
WT="${TMPDIR:-/tmp}/validar-pr-wt-$PROY"

# La copia es un clon local con su propio .git (no un git worktree): el .git de un worktree es
# un fichero que apunta a una ruta del host, y dentro de los contenedores de la suite esa ruta
# no existe (en Windows, ni siquiera se puede montar): git fallaba con «not a git repository».
borrar_copia() {
  case "$WT" in */validar-pr-wt-vp*) vp_borrar_dir "$WT" ;; esac
}
limpiar() {
  vp_stack_abajo "$PROY" >/dev/null 2>&1 || true
  borrar_copia
}
trap limpiar EXIT

vp_info "Paso 1/4: copia aislada en $CORTO fusionada con origin/$VP_RAMA_BASE (${BASE_SHA:0:8})."
borrar_copia
# --local: enlaces duros a los objetos (rápido, sin red). El origin de la copia apunta a GitHub
# (para gh) y origin/<base> al mismo commit que en el clon del dev (para merge-base y contexto).
URL_ORIGIN="$(git remote get-url origin 2>/dev/null || true)"
git clone -q --local --no-checkout "$VP_RAIZ" "$WT"
cd "$WT"
[ -n "$URL_ORIGIN" ] && git remote set-url origin "$URL_ORIGIN"
git update-ref "refs/remotes/origin/$VP_RAMA_BASE" "$BASE_SHA"
git checkout -q --detach "$SHA"
export VP_BASE_SHA="$BASE_SHA"
# Normativas ANTES de fusionar: las líneas de BASE...HEAD casan con el árbol de este commit.
# Normativas mecánicas del equipo: opcionales, las define config.sh (vp_normativas <base_sha>).
NORM_LOG="$(mktemp)"
if declare -F vp_normativas >/dev/null; then
  vp_normativas "$BASE_SHA" >"$NORM_LOG" 2>&1 && NORM_OK=1 || NORM_OK=0
else
  echo "normativas: no configuradas (config.sh no define vp_normativas)" >"$NORM_LOG"; NORM_OK=1
fi
if ! git -c user.name=validar-pr -c user.email=validar-pr@localhost merge -q --no-commit --no-ff "$BASE_SHA" >/dev/null 2>&1; then
  vp_rojo "✗ Conflictos al fusionar con origin/$VP_RAMA_BASE:"; git diff --name-only --diff-filter=U >&2
  vp_rojo "Solución: git fetch && git merge origin/$VP_RAMA_BASE en tu rama, resuelve, commitea y repite."
  exit 1
fi

FALLOS=(""); LOG="$VP_INFORMES/$SHA.log"; : > "$LOG"
cat "$NORM_LOG" >>"$LOG"; rm -f "$NORM_LOG"
if [ "$NORM_OK" = 1 ]; then echo "normativas: OK" >>"$LOG"; else FALLOS+=("Normativas del equipo: hay FALLO en lo que introduce la PR (detalle en $LOG)."); fi
# Qué toca la PR: decide si hace falta la suite (y sus dependencias) o basta la batería.
VP_TOCADOS="$(git diff --name-only "$BASE_SHA...$SHA")"; export VP_TOCADOS
SOLO_HERRAMIENTAS=0
printf '%s\n' "$VP_TOCADOS" | vp_solo_herramientas && SOLO_HERRAMIENTAS=1
if [ "$SOLO_HERRAMIENTAS" -eq 0 ]; then
  vp_deps_worktree "$VP_RAIZ" >>"$LOG" 2>&1 || FALLOS+=("No se pudieron instalar las dependencias de Node en la copia (detalle en $LOG).")
fi
CAMBIADOS=()
while IFS= read -r f; do [ -n "$f" ] && [ -e "$f" ] && CAMBIADOS+=("$f"); done < <(git diff --name-only --diff-filter=ACMR "$BASE_SHA"...HEAD)
VP_NUEVOS="$(git diff --name-only --diff-filter=A "$BASE_SHA"...HEAD)"; export VP_NUEVOS

vp_info "Paso 2/4: lint y formato de los ${#CAMBIADOS[@]} fichero(s) de la PR."
if [ "${#CAMBIADOS[@]}" -gt 0 ]; then
  vp_lint_rapido "${CAMBIADOS[@]}" >>"$LOG" 2>&1 && echo "lint: OK" >>"$LOG" || FALLOS+=("Lint o formato en rojo (detalle en $LOG).")
fi
vp_secretos "$BASE_SHA..HEAD" 2>>"$LOG" || FALLOS+=("Posible secreto en la PR (detalle en $LOG).")

# La suite solo con lo que toca la PR: config.sh usa vp_toca para lanzar backend y frontend
# por separado, y una PR solo de herramientas o docs pasa la batería en lugar de la suite.
# >>> estado-suite (la batería ejecuta este bloque tal cual, con una suite y una batería falsas)
# Qué se ejecuta según lo que toca la PR:
#  - solo herramientas o docs: la batería de validar-pr, sin suite;
#  - cambia config.sh (donde vive la suite): la suite ENTERA, sin separar backend/frontend;
#  - el resto: la suite de las partes que toca (vp_toca en config.sh);
#  - y si la PR toca la propia herramienta, la batería también, haya suite o no.
# Con set -e, la suite va con «|| RC_SUITE=$?»: como orden suelta, un rojo cortaba el script.
TOCA_HERRAMIENTA=0
printf '%s\n' "$VP_TOCADOS" | grep -qE '^\.claude/skills/validar-pr/|^'"$(dirname "$VP_CFG_REL" | sed 's/[.]/\\./g')"'/' && TOCA_HERRAMIENTA=1
if [ "$SOLO_HERRAMIENTAS" -eq 1 ]; then
  vp_info "Paso 3/4: la PR solo toca herramientas o docs: batería de validar-pr en vez de la suite."
  SUITE="no aplica (solo herramientas/docs)"
else
  if printf '%s\n' "$VP_TOCADOS" | grep -qxF "$VP_CFG_REL"; then
    vp_info "Paso 3/4: la PR cambia config.sh: suite oficial entera en Docker."
    unset VP_TOCADOS
  else
    vp_info "Paso 3/4: suite oficial en Docker de lo que toca la PR (puede tardar unos minutos)."
  fi
  # Código 10 = la PR no toca ninguna parte que la suite ejecute: «no aplica», no «OK».
  RC_SUITE=0; vp_suite_oficial "${PROY}t" >>"$LOG" 2>&1 || RC_SUITE=$?
  if [ "$RC_SUITE" -eq 0 ]; then SUITE="OK"
  elif [ "$RC_SUITE" -eq 10 ]; then SUITE="no aplica (la PR no toca backend ni frontend)"
  else SUITE="ROJO"; FALLOS+=("La suite oficial falla (últimas líneas en $LOG). Compárala con origin/$VP_RAMA_BASE: si también falla allí, dilo en la PR."); fi
fi
if { [ "$TOCA_HERRAMIENTA" -eq 1 ] || [ "$SOLO_HERRAMIENTAS" -eq 1 ]; } && [ -f "$VP_DIR/scripts/test-validar-pr.sh" ]; then
  if bash "$VP_DIR/scripts/test-validar-pr.sh" >>"$LOG" 2>&1; then SUITE="$SUITE; batería de validar-pr OK"
  else SUITE="$SUITE; batería de validar-pr ROJA"; FALLOS+=("La batería de validar-pr falla (detalle en $LOG)."); fi
fi
# <<< estado-suite
echo "suite oficial: $SUITE" >>"$LOG"
# La suite local lee del ci.yml los run: de una línea de backend-lint/backend-test; frontend y pyright están copiados en config.sh.
case "$SUITE" in ROJO*)
  if git diff --name-only "$BASE_SHA...$SHA" | grep -q '^\.github/workflows/' \
     && ! git diff --name-only "$BASE_SHA...$SHA" | grep -qxF "$VP_CFG_REL"; then
    FALLOS+=("La PR cambia .github/workflows/. La suite local ejecuta los run: de una línea de backend-lint y backend-test de tu ci.yml (sin los pip install); los pasos de frontend y de pyright están copiados en $VP_CFG_REL (vp_suite_oficial): si cambiaste uno de esos, cámbialo también allí en esta PR.")
  fi ;;
esac

# Paso 4: la IA solo si lo mecánico está en verde. Con lint, secretos o suite en rojo, el
# informe ya dice qué arreglar y una revisión cara no cambiaría el veredicto.
if [ "${#FALLOS[@]}" -gt 1 ]; then
  vp_info "Paso 4/4: se omite la revisión con IA (hay fallos mecánicos: arréglalos primero, no gastan tokens)."
  MODELO="no ejecutado"; SALIDA="$(mktemp)"
  echo "Revisión con IA no ejecutada: primero hay que dejar en verde lo mecánico (abajo)." > "$SALIDA"
else
  # ¿Revisión incremental? Si un commit anterior de esta rama ya tiene informe y desde entonces
  # no se ha fusionado nada (sin merges), solo se revisa lo nuevo y si se atendió lo pedido.
  PREVIO=""
  if [ "$COMPLETA" -eq 0 ]; then
    for c in $(git rev-list "$BASE_SHA..$SHA^" 2>/dev/null | head -50); do
      # Solo cuenta un informe en el que la IA llegó a revisar (no los cortados por fallos mecánicos).
      grep -q '· modelo: ' "$VP_INFORMES/$c.md" 2>/dev/null \
        && ! grep -qE '· modelo: (no ejecutado|ninguno|sin veredicto)' "$VP_INFORMES/$c.md" \
        && { PREVIO="$c"; break; }
    done
    [ -n "$PREVIO" ] && [ -n "$(git rev-list --merges "$PREVIO..$SHA")" ] && PREVIO=""
  fi
  if [ -n "$PREVIO" ]; then
    ALCANCE="incremental"; RANGO="$PREVIO..$SHA"
    TOCADOS="$(git diff --name-only "$PREVIO" "$SHA")"
  else
    ALCANCE="completa"; RANGO="$BASE_SHA...$SHA"
    TOCADOS="$(printf '%s\n' "${CAMBIADOS[@]}")"
  fi
  # Prueba de punta a punta solo si cambia algo que se ejecuta (no docs, tests, CI ni .claude).
  if printf '%s\n' "$TOCADOS" | sed '/^$/d' | grep -qvE "$VP_RUTAS_SIN_E2E"; then E2E=1; TURNOS="${VALIDAR_PR_TURNOS:-60}"; else E2E=0; TURNOS="${VALIDAR_PR_TURNOS:-25}"; fi
  vp_info "Paso 4/4: revisión $ALCANCE con IA ($RANGO), prueba de punta a punta: $( [ $E2E = 1 ] && echo sí || echo 'no hace falta')."
  PROMPT="$(mktemp)"; SALIDA="$(mktemp)"
  {
    cat "$VP_DIR/prompt-pr.md"; echo
    cat "$VP_DIR/errores-tipicos.md"; echo
    # Lo que ya se coló en ESTE repo (capa del proyecto): crece una línea por bug escapado.
    [ -f "$VP_CFG_DIR/errores-tipicos.md" ] && { cat "$VP_CFG_DIR/errores-tipicos.md"; echo; }
    cat <<DATOS

## Datos de esta validación
- Repo: $(basename "$VP_RAIZ") · rama: $RAMA · commit: $SHA · base: origin/$VP_RAMA_BASE ($BASE_SHA)
- Directorio de trabajo (ya fusionado con la base, sin commitear): $WT
- Alcance: **$ALCANCE**$( [ -n "$PREVIO" ] && printf ' (lo nuevo desde %s, que ya se revisó; su informe va abajo)' "${PREVIO:0:8}")
- Prueba de punta a punta: $( [ $E2E = 1 ] && echo "OBLIGATORIA. Stack aislado: bash .claude/skills/validar-pr/scripts/stack.sh arriba $PROY (comandos: stack.sh dc|http $PROY …; al acabar: stack.sh abajo $PROY). Cómo probar cada tipo de cambio: $VP_CFG_DIR/REPO.md" || echo "no (el cambio no toca código que se ejecute)")
- Lo mecánico ya está en verde (normativas, lint, secretos, suite oficial: $SUITE). No lo repitas.
- Ficheros a revisar:
$(printf '%s\n' "$TOCADOS" | sed '/^$/d; s/^/  - /' | head -80)
DATOS
    echo
    # El diff va dentro del prompt (ahorra turnos de lectura) si no es enorme.
    DIFF="$(mktemp)"; git diff -U10 "$RANGO" -- . ':(exclude)*.lock' ':(exclude)*lock.json' ':(exclude)*.min.*' > "$DIFF" 2>/dev/null || true
    if [ "$(wc -c < "$DIFF")" -le 150000 ]; then
      echo "## Diff a revisar ($RANGO)"; echo '```diff'; cat "$DIFF"; echo '```'
    else
      echo "## Diff a revisar: es grande ($(wc -c < "$DIFF" | tr -d ' ') bytes). Léelo por ficheros: bash .claude/skills/validar-pr/scripts/git-ro.sh diff $RANGO -- <ruta>"
    fi
    rm -f "$DIFF"
    if [ -n "$PREVIO" ]; then
      echo; echo "## Informe de la validación anterior (${PREVIO:0:8}): comprueba que lo que pedía está resuelto"
      sed -e 's/<!-- *validar-pr[^>]*-->//g' "$VP_INFORMES/$PREVIO.md" | head -120
    fi
    echo
    # Tarea de Jira (REST) y PR (gh): DATOS para el revisor, recortados.
    "$VP_PY" "$VP_DIR/scripts/contexto-pr.py" "$RAMA" "$BASE_SHA" "$VP_RAMA_BASE" "$TITULO" 2>>"$LOG" \
      || echo "(no se pudo reunir el contexto de Jira y de la PR)"
  } > "$PROMPT"
  # Permisos del revisor autónomo: SOLO lectura (git vía git-ro.sh) y el stack aislado vía
  # stack.sh. Sin curl, make, npm run ni docker compose/exec sueltos.
  HERR="Read,Grep,Glob,Bash(bash .claude/skills/validar-pr/scripts/git-ro.sh:*),Bash(bash .claude/skills/validar-pr/scripts/stack.sh:*),Bash(docker ps:*),Bash(ls:*),Bash(grep:*),Bash(jq:*),Bash(sleep:*)"
  if vp_modelo "$PROMPT" "$SALIDA" "$HERR" "$TURNOS"; then
    MODELO="$(cat "$SALIDA.modelo") · revisión $ALCANCE"
    [ "$(vp_veredicto "$SALIDA")" = APROBABLE ] || FALLOS+=("La revisión pide cambios (informe abajo).")
  else
    MODELO="ninguno"; echo "VEREDICTO: CAMBIOS" > "$SALIDA"
    FALLOS+=("No se pudo hacer la revisión ni con $VP_MODELO ni con $VP_MODELO_RESERVA (sesión de claude o saldo).")
  fi
  rm -f "$PROMPT"
fi

if [ "${#FALLOS[@]}" -gt 1 ]; then VEREDICTO="CAMBIOS"; else VEREDICTO="APROBABLE"; fi
{
  echo "<!-- validar-pr sha=$SHA base=$BASE_SHA veredicto=$VEREDICTO -->"
  echo "## Validación validar-pr"
  echo "- Commit: \`$CORTO\` fusionado sobre \`$VP_RAMA_BASE\` \`${BASE_SHA:0:8}\` · modelo: $MODELO · $(date '+%Y-%m-%d %H:%M')"
  echo "- Lint/formato: $(grep -q 'lint: OK' "$LOG" && echo OK || echo revisar) · suite oficial: $SUITE · veredicto: **$VEREDICTO**"
  echo
  # Fuera del texto del revisor cualquier marca de validar-pr: solo vale la de la primera línea.
  sed -e '/^VEREDICTO:/d' -e 's/<!-- *validar-pr[^>]*-->//g' "$SALIDA"
  echo; echo "VEREDICTO: $VEREDICTO"
} > "$INFORME"
rm -f "$SALIDA" "$SALIDA.modelo"
cd "$VP_RAIZ"

cat "$INFORME" >&2
if [ "$VEREDICTO" != "APROBABLE" ]; then
  vp_rojo "✗ La PR NO está lista:"; for f in "${FALLOS[@]}"; do [ -n "$f" ] && vp_rojo "  - $f"; done
  vp_rojo "Informe: $INFORME. Arregla, commitea y vuelve a lanzar la validación."
  exit 1
fi
vp_verde "✓ Validación completa OK. Informe: $INFORME"

[ "$CREAR_PR" -eq 1 ] || exit 0
# El informe se publica en GitHub y el revisor leyó texto de terceros (Jira, PR): antes de
# publicarlo, el mismo filtro de secretos que en los commits. Si salta, no se publica nada.
if ! sed 's/^/+/' "$INFORME" | vp_secretos_diff; then
  vp_rojo "El informe contiene algo con forma de secreto: no se publica. Revísalo en $INFORME."
  exit 1
fi
command -v gh >/dev/null || { vp_rojo "Falta gh (GitHub CLI)."; exit 2; }
git push -u origin "$RAMA"
CUERPO="$(mktemp)"
if NUM="$(gh pr view "$RAMA" --json number,state -q 'select(.state=="OPEN").number' 2>/dev/null)" && [ -n "$NUM" ]; then
  gh pr view "$NUM" --json body -q .body | "$VP_PY" -c '
import sys,re
b=sys.stdin.read(); inf=open(sys.argv[1], encoding="utf-8").read().strip()
b=re.sub(r"<!-- validar-pr .*?\nVEREDICTO: [A-Z]+\n?", "", b, flags=re.S).rstrip()
print((b+"\n\n" if b else "")+inf)' "$INFORME" > "$CUERPO"
  gh pr edit "$NUM" --body-file "$CUERPO"
  vp_verde "PR #$NUM actualizada con el informe."
else
  [ -n "$TITULO" ] || TITULO="$(git log -1 --format=%s)"
  { git log --format='- %s' "$BASE_SHA"..HEAD; echo; cat "$INFORME"; } > "$CUERPO"
  gh pr create --base "$VP_RAMA_BASE" --head "$RAMA" --title "$TITULO" --body-file "$CUERPO"
fi
rm -f "$CUERPO"
