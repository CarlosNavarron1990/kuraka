#!/usr/bin/env bash
# Funciones comunes de validar-pr. Se carga con `source` desde los demás scripts.
# Parte COMÚN (vault Kuraka, skills/validar-pr/). Lo propio de cada repo vive en la capa del
# proyecto: <plataforma>/project/validar-pr/{config.sh,REPO.md,errores-tipicos.md}.

# En Windows Python lee y escribe texto en cp1252 salvo que se le pida UTF-8: los
# informes, las PR, Jira y los comandos llevan acentos y emojis y fallaria con
# UnicodeDecodeError/UnicodeEncodeError. Lo heredan todos los python que se lanzan.
export PYTHONUTF8=1

VP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VP_RAIZ="$(git rev-parse --show-toplevel)"
# Python 3 que de verdad arranca: en Windows python3 suele ser el atajo de la Microsoft Store.
export PYTHONUTF8=1
vp_python() {
  local c
  for c in python3 python py; do
    if command -v "$c" >/dev/null 2>&1 && "$c" -c 'import sys; sys.exit(sys.version_info < (3, 8))' >/dev/null 2>&1; then
      echo "$c"; return 0
    fi
  done
  return 1
}
VP_GITDIR="$(git rev-parse --git-common-dir)"
# En Windows git devuelve rutas absolutas como C:/Users/...: tambien son absolutas.
vp_es_ruta_absoluta() { case "$1" in /* | [A-Za-z]:[/\\]*) return 0 ;; esac; return 1; }
vp_es_ruta_absoluta "$VP_GITDIR" || VP_GITDIR="$VP_RAIZ/$VP_GITDIR"
VP_INFORMES="$VP_GITDIR/validar-pr"
# Modelo del revisor = el tier frontier del PLAN de Claude con que se montó Kuraka
# (.claude/.kuraka-mount-manifest.json → claude_plan_models.frontier):
#   max → fable, reserva opus · pro/team → sonnet, reserva haiku · sin manifest → opus/sonnet.
# Siempre alias (se resuelven al modelo vigente del tier). El entorno o config.sh
# (VALIDAR_PR_MODELO / VALIDAR_PR_MODELO_RESERVA, o VP_MODELO / VP_MODELO_RESERVA) mandan.
vp_modelo_del_plan() {
  awk '/"claude_plan_models"/{f=1} f&&/"frontier"/{gsub(/[",]/,""); print $2; exit}' \
    "$VP_RAIZ/.claude/.kuraka-mount-manifest.json" 2>/dev/null
}
case "$(vp_modelo_del_plan)" in
  fable)  _vp_m=fable;  _vp_r=opus ;;
  sonnet) _vp_m=sonnet; _vp_r=haiku ;;
  haiku)  _vp_m=haiku;  _vp_r=haiku ;;
  *)      _vp_m=opus;   _vp_r=sonnet ;;
esac
VP_MODELO="${VALIDAR_PR_MODELO:-$_vp_m}"
VP_MODELO_RESERVA="${VALIDAR_PR_MODELO_RESERVA:-$_vp_r}"
unset _vp_m _vp_r
mkdir -p "$VP_INFORMES"

vp_rojo()  { printf '\033[0;31m%s\033[0m\n' "$*" >&2; }
vp_verde() { printf '\033[0;32m%s\033[0m\n' "$*" >&2; }
vp_info()  { printf '\033[0;36m[validar-pr]\033[0m %s\n' "$*" >&2; }

vp_es_windows() { case "$(uname -s)" in MINGW* | MSYS* | CYGWIN*) return 0 ;; esac; return 1; }

# En Windows (Git Bash) /tmp solo existe para Git Bash: Docker Compose y los programas nativos
# no lo conocen. Una ruta /tmp/... escrita en un compose (env_file) o en un -v la toman relativa
# al proyecto y no encuentran los ficheros. Se pasa TMPDIR a ruta Windows (C:/Users/.../Temp),
# que entienden los dos; mktemp y todo lo que cuelga de TMPDIR la heredan. cygpath solo existe
# en Git Bash/MSYS/Cygwin: en Mac y Linux no cambia nada.
if command -v cygpath >/dev/null 2>&1; then
  TMPDIR="$(cygpath -m "${TMPDIR:-/tmp}")"; export TMPDIR
fi
# vp_ruta_posix <ruta>: la misma ruta en formato de Git Bash (/c/Users/...). Para lo que va
# en una lista separada por «:» (PATH): una ruta C:/... se partiría en «C» y «/Users/...».
vp_ruta_posix() { if command -v cygpath >/dev/null 2>&1; then cygpath -u "$1"; else printf '%s\n' "$1"; fi; }

# vp_borrar_dir <ruta>: borra una carpeta temporal de validar-pr. En Windows, kill y pgrep
# de Git Bash no ven los procesos nativos (node, esbuild, workers de Next) que arranca la
# prueba de punta a punta: quedan vivos, bloquean la carpeta y el rm da «Device or resource
# busy», tambien en la siguiente validacion. Se matan los que lleven la carpeta en su linea
# de comandos (el nombre es unico por repo y commit) y se reintenta el borrado.
vp_borrar_dir() {
  local dir="$1" nombre intento
  [ -e "$dir" ] || return 0
  nombre="$(basename "$dir")"
  if vp_es_windows && command -v powershell.exe >/dev/null 2>&1; then
    powershell.exe -NoProfile -NonInteractive -Command \
      "Get-CimInstance Win32_Process | Where-Object { \$_.ProcessId -ne \$PID -and \$_.CommandLine -and \$_.CommandLine.Contains('$nombre') } | ForEach-Object { Stop-Process -Id \$_.ProcessId -Force -ErrorAction SilentlyContinue }" \
      >/dev/null 2>&1 || true
  fi
  for intento in 1 2 3 4 5; do
    rm -rf "$dir" 2>/dev/null && return 0
    sleep 1
  done
  vp_rojo "No se puede borrar $dir: algún proceso la tiene abierta (en Windows, mira en el Administrador de tareas node.exe o esbuild.exe con esa ruta)."
  rm -rf "$dir"
}

# Carga la parte propia del repo (VP_RAMA_BASE, vp_lint_rapido, vp_suite_oficial,
# vp_stack_arriba, vp_stack_abajo…). Vive en la capa del proyecto, que el mount de Kuraka no
# pisa y kuraka-backup respalda: <plataforma>/project/validar-pr/config.sh. Orden:
# $VP_CFG_DIR explícito → capa del proyecto → config.sh junto a la skill (instalaciones viejas).
VP_CFG_DIR="${VP_CFG_DIR:-}"
if [ -z "$VP_CFG_DIR" ]; then
  if [ -f "$VP_DIR/../../project/validar-pr/config.sh" ]; then
    VP_CFG_DIR="$(cd "$VP_DIR/../../project/validar-pr" && pwd)"
  elif [ -f "$VP_DIR/config.sh" ]; then
    VP_CFG_DIR="$VP_DIR"
  fi
fi
if [ -z "$VP_CFG_DIR" ] || [ ! -f "$VP_CFG_DIR/config.sh" ]; then
  vp_rojo "validar-pr no está configurado en este repo: copia $VP_DIR/config.example.sh a .claude/project/validar-pr/config.sh (o el equivalente de tu plataforma) y complétalo."
  exit 2
fi
export VP_CFG_DIR
# Ramas a las que solo se llega por PR (config.sh puede cambiarlo).
: "${VP_RAMAS_PROTEGIDAS:=main master develop dev release}"
# shellcheck source=/dev/null
source "$VP_CFG_DIR/config.sh"
# El entorno manda sobre config.sh (que manda sobre el plan montado).
[ -n "${VALIDAR_PR_MODELO:-}" ] && VP_MODELO="$VALIDAR_PR_MODELO"
[ -n "${VALIDAR_PR_MODELO_RESERVA:-}" ] && VP_MODELO_RESERVA="$VALIDAR_PR_MODELO_RESERVA"
# Ruta del config.sh relativa a la raíz del repo: si la PR lo cambia, la suite va entera.
VP_CFG_REL="${VP_CFG_DIR#"$VP_RAIZ"/}/config.sh"
# Rama base: config.sh > workflow.base_branch de kuraka.config.yaml > origin/HEAD > main.
if [ -z "${VP_RAMA_BASE:-}" ]; then
  VP_RAMA_BASE="$(sed -nE 's/^[[:space:]]+base_branch:[[:space:]]*"?([^"#[:space:]]+)"?.*/\1/p' "$VP_RAIZ/kuraka.config.yaml" 2>/dev/null | head -1)"
  [ -n "$VP_RAMA_BASE" ] || VP_RAMA_BASE="$(git symbolic-ref --short refs/remotes/origin/HEAD 2>/dev/null | sed 's#^origin/##')"
  [ -n "$VP_RAMA_BASE" ] || VP_RAMA_BASE=main
fi

# vp_toca <regex>: ¿la PR toca algún fichero que case? validar-pr.sh exporta VP_TOCADOS (los
# ficheros de la PR). Sin esa lista (suite lanzada a mano) se responde que sí: se ejecuta todo.
vp_toca() {
  [ -n "${VP_TOCADOS+x}" ] || return 0
  printf '%s\n' "$VP_TOCADOS" | grep -qE "$1"
}

# Ficheros que no piden suite: herramientas de desarrollo y documentación. Una PR que solo toca
# esto pasa la batería de validar-pr en vez de la suite entera. config.sh puede cambiarlo.
: "${VP_RUTAS_SIN_SUITE:=^\.claude/|^\.githooks/|(^|/)\.husky/|^\.github/workflows/validar-pr\.yml$|^docs?/|\.md$}"

# ¿La PR es solo de herramientas o docs? (lista de ficheros por stdin). 0 = sí.
vp_solo_herramientas() {
  local f; f="$(sed '/^$/d')"
  # config.sh define la suite: si cambia, la suite se ejecuta para probarla.
  printf '%s\n' "$f" | grep -qxF "$VP_CFG_REL" && return 1
  [ -z "$(printf '%s\n' "$f" | sed '/^$/d' | grep -vE "$VP_RUTAS_SIN_SUITE")" ]
}

# Ficheros que no piden prueba de punta a punta (no se ejecutan en el servicio): docs, tests,
# CI y la propia configuración de Claude. config.sh puede cambiarlo para su repo.
: "${VP_RUTAS_SIN_E2E:=(^|/)(docs?|tests?|__tests__|e2e|fixtures?)/|^\.claude/|^\.github/|^\.husky/|^\.githooks/|\.md$|\.(spec|test)\.[a-z]+$|(^|/)test_[^/]*\.py$|(^|/)conftest\.py$}"

vp_requiere_claude() {
  if ! command -v claude >/dev/null 2>&1; then
    vp_rojo "Falta la CLI de Claude Code. Instálala (https://docs.claude.com/claude-code) y ejecuta 'claude' una vez para iniciar sesión."
    return 2
  fi
}

# Dependencias de Node en un worktree recién creado (node_modules no se versiona).
# Por cada package-lock.json: si es idéntico al del clon del dev y allí hay node_modules,
# se clona la carpeta (copia, nunca enlace: un npm ci posterior borraría la del dev);
# si no, npm ci. Se ejecuta desde la raíz del worktree; $1 = raíz del clon del dev.
vp_deps_worktree() {
  local origen="$1" lock dir
  command -v npm >/dev/null 2>&1 || return 0
  while IFS= read -r lock; do
    dir="$(dirname "$lock")"
    [ -d "$dir/node_modules" ] && continue
    if [ -d "$origen/$dir/node_modules" ] && cmp -s "$lock" "$origen/$lock"; then
      vp_info "Dependencias de $dir: copia de las del clon local."
      cp -cR "$origen/$dir/node_modules" "$dir/node_modules" 2>/dev/null \
        || cp -R --reflink=auto "$origen/$dir/node_modules" "$dir/node_modules" 2>/dev/null \
        || cp -R "$origen/$dir/node_modules" "$dir/node_modules"
      if [ "$dir" = "." ]; then vp_deps_workspaces "$origen"; fi
    else
      vp_info "Dependencias de $dir: npm ci."
      # HUSKY=0: el prepare de husky escribiría core.hooksPath en la config COMPARTIDA del clon.
      ( cd "$dir" && HUSKY=0 npm ci --no-audit --no-fund --loglevel=error ) || return 1
    fi
  done < <(git ls-files -- '*package-lock.json' ':(exclude)**/node_modules/**')
}

# Con workspaces, npm deja node_modules propios junto a cada paquete (agent-platform,
# packages/*) cuando su versión choca con la de la raíz: Prettier vive en
# agent-platform/node_modules. Copiar solo el de la raíz los dejaba fuera de la copia.
vp_deps_workspaces() {
  local origen="$1" nm
  while IFS= read -r nm; do
    nm="${nm#"$origen"/}"
    [ -d "$nm" ] && continue
    [ -f "$(dirname "$nm")/package.json" ] || continue
    [ -f "$(dirname "$nm")/package-lock.json" ] && continue
    cp -cR "$origen/$nm" "$nm" 2>/dev/null \
      || cp -R --reflink=auto "$origen/$nm" "$nm" 2>/dev/null \
      || cp -R "$origen/$nm" "$nm"
  done < <(find "$origen" -mindepth 1 -maxdepth 3 -path "$origen/node_modules" -prune \
             -o -type d -name node_modules -not -path '*/node_modules/*' -print 2>/dev/null)
}

# Ficheros NUEVOS del cambio que se valida (uno por línea). En el commit, los añadidos en
# stage; en la validación completa, los que añade la PR (VP_NUEVOS lo fija validar-pr.sh,
# porque allí el stage contiene la fusión con la base y no solo la PR).
vp_nuevos() {
  if [ -n "${VP_NUEVOS+x}" ]; then printf '%s\n' "$VP_NUEVOS" | sed '/^$/d'
  else git diff --cached --name-only --diff-filter=A; fi
}

# Veredicto de la ÚLTIMA línea no vacía (si el modelo lo cita a mitad y se corta, no vale).
vp_veredicto() {
  awk 'NF{l=$0} END{print l}' "$1" | sed -nE 's/^VEREDICTO: (OK|BLOQUEA|APROBABLE|CAMBIOS)[[:space:]]*$/\1/p'
}

# vp_modelo <fichero_prompt> <fichero_salida> <herramientas_permitidas> [max_turns]
# Ejecuta la revisión con el modelo principal. El de reserva SOLO entra si el principal no
# llega a revisar (sin saldo, límite, error de red: sale con error o con una respuesta
# corta). Si revisó pero sin veredicto (se quedó sin turnos), repetir con otro modelo
# pagaría la revisión entera dos veces: se da por CAMBIOS y se dice.
vp_modelo() {
  local prompt="$1" salida="$2" herramientas="$3" turnos="${4:-40}" modelo err rc
  vp_requiere_claude || return 2
  err="$(mktemp)"
  for modelo in "$VP_MODELO" "$VP_MODELO_RESERVA"; do
    vp_info "Revisión con ${modelo} (máx. $turnos turnos)…"
    # Revisor ligero: sin ajustes ni plugins de usuario, sin MCP y sin lista de skills (el
    # contexto de Jira y de la PR ya va en el prompt) y solo con las herramientas que usa.
    # Medido: el arranque baja de ~46.000 a ~11.700 tokens, y eso se paga en cada turno.
    env -u CLAUDECODE VALIDAR_PR_DENTRO=1 claude -p \
         --model "$modelo" \
         --setting-sources project --strict-mcp-config --disable-slash-commands \
         --no-session-persistence --tools Read,Grep,Glob,Bash \
         --permission-mode dontAsk --allowedTools "$herramientas" \
         --max-turns "$turnos" --output-format text \
         < "$prompt" > "$salida" 2> "$err"
    rc=$?
    if [ -n "$(vp_veredicto "$salida")" ]; then
      echo "$modelo" > "$salida.modelo"; rm -f "$err"; return 0
    fi
    # Sin turnos, `claude -p` sale con 1 y una sola línea («Reached max turns»): es una revisión
    # que sí se hizo y se pagó; repetirla con la reserva la pagaría dos veces.
    if cat "$salida" "$err" 2>/dev/null | grep -qi 'reached max turns'; then
      vp_rojo "La revisión con $modelo se quedó sin turnos ($turnos). No se repite con otro modelo."
      echo "sin veredicto ($modelo)" > "$salida.modelo"
      printf '\nLa revisión se quedó sin turnos (%s) antes de dictaminar: se da por CAMBIOS. Divide la PR o sube VALIDAR_PR_TURNOS.\nVEREDICTO: CAMBIOS\n' "$turnos" >> "$salida"
      rm -f "$err"; return 0
    fi
    # Una revisión de verdad que se quedó sin turnos deja texto largo y sale con 0. Un error del
    # modelo (sin saldo, límite, red) sale con error o con una línea corta: ahí entra la reserva.
    if [ "$rc" -eq 0 ] && [ "$(wc -c < "$salida" | tr -d ' ')" -gt 1500 ]; then
      vp_rojo "La revisión con $modelo terminó sin veredicto (¿límite de turnos?). No se repite con otro modelo."
      # Sin «claude-» delante: un informe sin veredicto no sirve de base para la revisión incremental.
      echo "sin veredicto ($modelo)" > "$salida.modelo"
      printf '\n(La revisión no llegó a dictaminar: se da por CAMBIOS. Repite con --completa si hace falta.)\nVEREDICTO: CAMBIOS\n' >> "$salida"
      rm -f "$err"; return 0
    fi
    vp_rojo "La revisión con $modelo no arrancó ($(cat "$err" "$salida" 2>/dev/null | head -c 300 | tr '\n' ' ')). $( [ "$modelo" = "$VP_MODELO" ] && echo 'Paso al modelo de reserva.')"
  done
  rm -f "$err"
  return 3
}

# vp_secretos --staged | <rango git>  → única entrada para buscar secretos (commit, push y PR).
# gitleaks si está instalado (con .gitleaks.toml del repo si existe) y, siempre, las reglas
# propias de vp_secretos_diff sobre las líneas añadidas. Devuelve 1 si encuentra algo.
vp_secretos() {
  local modo="${1:?vp_secretos necesita --staged o un rango}" rc=0 log
  log="$(mktemp)"
  if command -v gitleaks >/dev/null 2>&1; then
    if [ "$modo" = "--staged" ]; then
      gitleaks git --pre-commit --staged --no-banner --redact >"$log" 2>&1 \
        || gitleaks protect --staged --no-banner --redact >"$log" 2>&1 || rc=1
    else
      gitleaks git --log-opts="$modo" --no-banner --redact >"$log" 2>&1 \
        || gitleaks detect --log-opts="$modo" --no-banner --redact >"$log" 2>&1 || rc=1
    fi
    [ "$rc" -eq 0 ] || { vp_rojo "gitleaks ha encontrado un posible secreto:"; grep -E 'Finding|Secret|File|Line|RuleID' "$log" | head -20 >&2; }
  fi
  rm -f "$log"
  if [ "$modo" = "--staged" ]; then
    git diff --cached -U0 -- . ':(exclude).claude/skills/validar-pr/scripts/comun.sh' | vp_secretos_diff || rc=1
  else
    git diff -U0 "${modo/../...}" -- . ':(exclude).claude/skills/validar-pr/scripts/comun.sh' 2>/dev/null | vp_secretos_diff || rc=1
  fi
  return "$rc"
}

# Busca secretos en un diff unificado (stdin). Dos reglas:
#  - formatos de clave conocidos (AKIA…, ghp_…, claves privadas, cadenas de conexión con
#    contraseña): en cualquier fichero;
#  - clave = "valor" (password, secret, api_key, token…): sin distinguir mayúsculas, pero
#    NO en ficheros de test ni cuando el valor es un identificador EN_MAYÚSCULAS, una URL o un
#    valor ya cifrado (prefijo ENCv1:, convención de algunos repos).
# Se llama a través de vp_secretos (que además lanza gitleaks si está instalado).
vp_secretos_diff() {
  local anadidas hallados exclusiones tests
  # «ruta<TAB>línea» de cada línea añadida (sin las cabeceras +++).
  anadidas="$(awk '/^\+\+\+ /{f=$2; sub(/^b\//,"",f); next} /^\+/{print f "\t" $0}')"
  exclusiones='example|ejemplo|changeme|dummy|placeholder|-local["'"'"']|localhost|127\.0\.0\.1|ficticio|<[^>]+>|\$\{|os\.environ|getenv|process\.env|test_?password|fake'
  # Rutas de test: se mira SOLO la ruta (primer campo), nunca el contenido de la línea.
  tests='(^|/)(tests?|__tests__|e2e|fixtures?|spec)/|(^|/)conftest\.py$|\.(spec|test)\.[a-z]+$'
  # Las exclusiones (example, fake, localhost…) se aplican SOLO al contenido, nunca a la ruta:
  # un secreto real pegado en «.env.example» tiene que saltar igual.
  local candidatos tmp; tmp="$(mktemp)"
  printf '%s\n' "$anadidas" > "$tmp"
  # «0» es un centinela: con la lista vacía, awk trataría el segundo fichero como el primero.
  { echo 0; cut -f2- "$tmp" | grep -niE "$exclusiones" | cut -d: -f1 || true; } > "$tmp.ex"
  candidatos="$(awk 'NR==FNR{ex[$1]=1; next} !(FNR in ex)' "$tmp.ex" "$tmp")"
  rm -f "$tmp" "$tmp.ex"
  hallados="$(printf '%s\n' "$candidatos" | grep -nE \
    'AKIA[0-9A-Z]{16}|ASIA[0-9A-Z]{16}|-----BEGIN [A-Z ]*PRIVATE KEY-----|AccountKey=[A-Za-z0-9+/=]{20,}|SharedAccessSignature=|sk-(ant-|proj-)?[A-Za-z0-9_-]{20,}|xox[baprs]-[A-Za-z0-9-]{10,}|ghp_[A-Za-z0-9]{30,}|(sk|rk)_live_[A-Za-z0-9]{20,}|whsec_[A-Za-z0-9]{20,}|xai-[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,}|eyJ[A-Za-z0-9_-]{15,}\.eyJ[A-Za-z0-9_-]{15,}\.|(postgres(ql)?|mysql|mssql|redis|amqp)://[^:/@ ]+:[^@ ]{3,}@' \
    || true)"
  # Un valor ya cifrado (ENCv1:…) se vacía, no se descarta la línea: otro valor en claro de la
  # misma línea tiene que seguir saltando.
  hallados="${hallados:+$hallados$'\n'}$(printf '%s\n' "$candidatos" | sed -E "s/([:=] *[\"'])ENCv1:[^\"']*/\1/g" | VP_T="$tests" awk -F'\t' '$1 !~ ENVIRON["VP_T"]' | grep -inE \
    '(password|passwd|pwd|secret|api_?key|token)[A-Za-z_]*["'"'"' ]*[:=] *["'"'"'][^"'"'"' ]{8,}["'"'"']' \
    | grep -vE '[:=] *["'"'"'](https?://|[A-Z0-9_]+["'"'"'])' || true)"
  hallados="$(printf '%s\n' "$hallados" | sed '/^$/d')"
  if [ -n "$hallados" ]; then
    vp_rojo "Posibles secretos en el diff (ruta y línea):"; printf '%s\n' "$hallados" | head -20 >&2
    return 1
  fi
}
