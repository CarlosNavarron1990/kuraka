#!/usr/bin/env bash
# Stack local aislado para la prueba de punta a punta. Siempre sobre el proyecto compose
# indicado, con su override (sin tocar el stack de desarrollo del dev).
#   stack.sh arriba <proyecto>
#   stack.sh abajo  <proyecto>
#   stack.sh url    <proyecto>   → URLs locales del stack, en formato eval-able:
#                                    VP_BACK_URL=http://127.0.0.1:<p>
#                                    VP_FRONT_URL=http://127.0.0.1:<p>
#     (de vp_url / vp_front_url en config.sh, o de VP_BACK_URL / VP_FRONT_URL fijas; solo
#      127.0.0.1/localhost. Lo usa también la skill recorrido-e2e para el navegador.)
#   stack.sh dc     <proyecto> <args de docker compose>      (exec -T, logs, ps…)
#   stack.sh http   <proyecto> <MÉTODO> </ruta> [json] [cabecera…]   (json solo si empieza por { o [)
#     p. ej.  stack.sh http vpX GET /api/casos 'Authorization: Bearer T'
# 'http' llega SOLO al backend de ese stack: la URL la construye este script, nunca el
# llamante, así que no hay forma de apuntar a otro host.
set -euo pipefail
case "${1:-}" in arriba|abajo|dc|http|url) ;; *) echo "uso: stack.sh arriba|abajo|dc|http|url <proyecto> …" >&2; exit 64 ;; esac
# Solo proyectos de validar-pr (prefijo vp): así nunca se baja ni se toca el stack del dev.
[[ "${2:-}" =~ ^vp[a-z0-9_-]*$ ]] || { echo "proyecto no válido: '${2:-}' (debe empezar por 'vp', como los que crea validar-pr)" >&2; exit 64; }
if [ "$1" = dc ]; then
  # El primer argumento tras el proyecto es el subcomando y solo estos: así no se cuelan
  # opciones globales de compose (-p otro, -f, --project-directory) ni run/up/down/cp.
  case "${3:-}" in exec|logs|ps|top|port|images) ;; *)
    echo "stack.sh dc: subcomando no permitido '${3:-}' (exec|logs|ps|top|port|images)" >&2; exit 64 ;; esac
fi
if [ "$1" = http ]; then
  [[ "${4:-}" =~ ^/[^[:space:]@]*$ ]] || { echo "la ruta debe empezar por / y no llevar espacios ni @" >&2; exit 64; }
fi
# Las guardas van antes de cargar nada: no dependen del repo ni de Docker.
source "$(dirname "${BASH_SOURCE[0]}")/comun.sh"
case "${1:-}" in
  arriba) vp_stack_arriba "${2:?proyecto}" ;;
  abajo)  vp_stack_abajo "${2:?proyecto}" ;;
  url)    p="${2:?proyecto}"; algo=0
          for par in "BACK:vp_url" "FRONT:vp_front_url"; do
            lado="${par%%:*}"; fn="${par#*:}"; var="VP_${lado}_URL"; u=""
            if declare -F "$fn" >/dev/null; then u="$("$fn" "$p")"; else u="${!var:-}"; fi
            [ -n "$u" ] || continue
            [[ "$u" =~ ^http://(127\.0\.0\.1|localhost)(:[0-9]+)?(/[^[:space:]@]*)?$ ]] \
              || { echo "$var no es una URL local: $u" >&2; exit 2; }
            echo "$var=$u"; algo=1
          done
          [ "$algo" -eq 1 ] || { echo "config.sh no define vp_url/vp_front_url ni VP_BACK_URL/VP_FRONT_URL" >&2; exit 2; } ;;
  dc)     shift; p="${1:?proyecto}"; shift
          # Sin vp_dc no hay forma segura de apuntar al stack aislado (un compose sin -f
          # cargaría el stack de desarrollo del dev): mejor fallar.
          declare -F vp_dc >/dev/null || { echo "config.sh no define vp_dc" >&2; exit 2; }
          vp_dc "$p" "$@" ;;
  http)   shift; p="${1:?proyecto}"; metodo="${2:?MÉTODO}"; ruta="${3:?/ruta}"; shift 3
          # El 4.º argumento es el cuerpo solo si es JSON ({ o [); si no, todo son cabeceras.
          datos=""; case "${1:-}" in \{*|\[*) datos="$1"; shift ;; esac
          case "$metodo" in GET|POST|PUT|PATCH|DELETE|HEAD) ;; *) echo "método no permitido: $metodo" >&2; exit 64 ;; esac
          [[ "$ruta" =~ ^/[^[:space:]@]*$ ]] || { echo "la ruta debe empezar por / y no llevar espacios ni @" >&2; exit 64; }
          [ "$metodo" = HEAD ] && [ -n "$datos" ] && { echo "HEAD no lleva cuerpo" >&2; exit 64; }
          if [ "$metodo" = HEAD ]; then args=(-s -S -I --max-time 60); else args=(-s -S -i -X "$metodo" --max-time 60); fi
          for h in "$@"; do args+=(-H "$h"); done
          # --data-raw: un cuerpo que empiece por @ no se lee como fichero.
          [ -n "$datos" ] && args+=(-H "Content-Type: application/json" --data-raw "$datos")
          if [ -n "${VP_HTTP_EXEC:-}" ]; then
            # Desde dentro del contenedor del backend (red del stack aislado).
            vp_dc "$p" exec -T "$VP_HTTP_EXEC" curl "${args[@]}" "http://localhost:${VP_PUERTO_HTTP:?}${ruta}"
          elif declare -F vp_url >/dev/null; then
            # Repos cuyo stack publica el puerto del backend en 127.0.0.1 (o la app corre en el host).
            base="$(vp_url "$p")"
            [[ "$base" =~ ^http://(127\.0\.0\.1|localhost):[0-9]+$ ]] || { echo "vp_url no devolvió una URL local: $base" >&2; exit 2; }
            curl "${args[@]}" "${base}${ruta}"
          else
            echo "config.sh no define VP_HTTP_EXEC ni vp_url" >&2; exit 2
          fi ;;
  *) exit 64 ;;  # inalcanzable: el subcomando ya se validó arriba
esac
