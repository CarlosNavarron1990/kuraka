# shellcheck shell=bash
# Plantilla de la parte PROPIA del repo para validar-pr (skills/validar-pr del vault Kuraka).
# Cópiala a la capa del proyecto —  .claude/project/validar-pr/config.sh  — y complétala.
# La cargan con `source` los scripts comunes desde la raíz del repo, con `set -euo pipefail`
# ya activo. Las rutas que reciben son relativas a la raíz. Junto a este fichero, en la misma
# carpeta de la capa, van REPO.md (cómo levantar y probar este repo) y errores-tipicos.md
# (lo que ya se coló en ESTE repo: una línea general por bug escapado).

# ─── Obligatorio ───────────────────────────────────────────────────────

# Rama base de las PR. Si se omite: workflow.base_branch de kuraka.config.yaml, luego origin/HEAD.
# VP_RAMA_BASE="develop"

# Claves de tarea del equipo (regex Python, SIN \b ni grupo de captura). Sin ella, el informe
# dice «clave no configurada» y no se lee la tarea. Nunca un patrón genérico [A-Z]+-\d+.
export VP_CLAVE_REGEX='(?:PROJ)-\d+'

# Lint/formato SOLO de los ficheros que toca la PR ($@). Devuelve != 0 si algo falla.
vp_lint_rapido() {
  local py=() ts=() f
  for f in "$@"; do
    case "$f" in *.py) py+=("$f") ;; *.ts|*.tsx|*.vue|*.js) ts+=("$f") ;; esac
  done
  # [ "${#py[@]}" -eq 0 ] || ruff check "${py[@]}"
  # [ "${#ts[@]}" -eq 0 ] || (cd frontend && npx eslint "${ts[@]#frontend/}")
  return 0
}

# Suite oficial (la MISMA que la CI) en un stack aislado cuyo proyecto compose es $1.
# Lanza solo lo que toca la PR:   vp_toca '^backend/' && …   vp_toca '^frontend/' && …
# Devuelve 0 = verde, 10 = la PR no toca nada que la suite ejecute («no aplica»), otro = rojo.
vp_suite_oficial() {
  local proyecto="$1" algo=0
  # if vp_toca '^backend/'; then algo=1; docker compose -p "$proyecto" -f docker-compose.test.yml run --rm backend make test-run || return 1; fi
  # if vp_toca '^frontend/'; then algo=1; (cd frontend && npm run type-check && npm test) || return 1; fi
  [ "$algo" -eq 1 ] || return 10
}

# ─── Prueba de punta a punta (si el repo tiene servicio que se ejecuta) ──

# Stack aislado: SIEMPRE con el proyecto compose $1 (prefijo vp…), nunca el stack del dev.
# Proveedores externos en mock; red sin salida a internet si se puede.
vp_stack_arriba() { :; }   # docker compose -p "$1" -f docker-compose.yml -f <override> up -d --wait
vp_stack_abajo()  { :; }   # docker compose -p "$1" down -v --remove-orphans
vp_dc() { local p="$1"; shift; docker compose -p "$p" "$@"; }
# Cómo llega stack.sh http al backend: por exec dentro del contenedor…
# VP_HTTP_EXEC="backend"; VP_PUERTO_HTTP=8000
# …o con una URL local publicada por el stack:
# vp_url() { echo "http://127.0.0.1:18000"; }
# URL del FRONTEND del stack aislado ($1 = proyecto vp…): la usan la prueba de punta a punta y
# la skill recorrido-e2e (navegador). `stack.sh url <vp…>` imprime VP_BACK_URL=… y
# VP_FRONT_URL=…; solo se aceptan 127.0.0.1/localhost. Si los puertos son fijos, basta con:
# VP_BACK_URL="http://127.0.0.1:18000"; VP_FRONT_URL="http://127.0.0.1:15173"
# vp_front_url() { echo "http://127.0.0.1:15173"; }

# Promoción por fast-forward de develop/dev a main en el pre-push (validar-push.sh). Solo
# si el repo promociona así; por defecto, main solo por PR. Línea literal, sin espacios:
# VP_PROMOCION_FF=1

# ─── Opcional ──────────────────────────────────────────────────────────

# Normativas mecánicas del equipo sobre lo que introduce la PR (base...HEAD). $1 = base_sha.
# vp_normativas() { bash scripts/normativas-check.sh --pr "$1" --laxo; }

# Ramas a las que solo se llega por PR (el hook de Kuraka y validar-pr.sh las respetan).
# VP_RAMAS_PROTEGIDAS="main master develop dev release"

# Rutas que no piden suite (solo herramientas/docs) ni prueba de punta a punta (regex ERE).
# VP_RUTAS_SIN_SUITE='^\.claude/|^docs?/|\.md$'
# VP_RUTAS_SIN_E2E='(^|/)(docs?|tests?)/|^\.claude/|^\.github/|\.md$'

# Modelos del revisor (alias de Claude Code) y tope de turnos.
# VP_MODELO="opus"; VP_MODELO_RESERVA="sonnet"
