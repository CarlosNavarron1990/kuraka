#!/usr/bin/env bash
# Hook pre-push de validar-pr. Solo una cosa: nada directo a una rama protegida, solo por PR
# (útil también con planes de GitHub sin protección de ramas). Sin secretos, sin lint, sin
# avisos: todo eso va en validar-pr.sh, antes de abrir la PR, una sola vez.
# Ramas protegidas: VP_RAMAS_PROTEGIDAS del config.sh del proyecto (capa
# <plataforma>/project/validar-pr/config.sh; fallback: config.sh junto a la skill);
# por defecto main master develop dev release.
set -uo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CFG=""
for c in "$DIR/../../../project/validar-pr/config.sh" "$DIR/../config.sh"; do
  [ -f "$c" ] && { CFG="$c"; break; }
done
PROTEGIDAS="main master develop dev release"
# Promoción por fast-forward de la base a main: solo si el repo la usa (VP_PROMOCION_FF=1 en
# su config.sh). Desactivada por defecto: en la mayoría de repos main solo se toca por PR.
VP_PROMOCION_FF=0
if [ -n "$CFG" ]; then
  # Se LEEN las dos variables (sin ejecutar config.sh: un pre-push no corre código del repo).
  v="$(sed -nE 's/^[[:space:]]*(export[[:space:]]+)?VP_RAMAS_PROTEGIDAS=["'\'']?([^"'\''#]*)["'\'']?.*/\2/p' "$CFG" | tail -1)"
  [ -n "${v// /}" ] && PROTEGIDAS="$v"
  eval "$(grep -E '^VP_PROMOCION_FF=[01]$' "$CFG" | tail -1)"
fi
es_protegida() { local p; for p in $PROTEGIDAS; do [ "$1" = "$p" ] && return 0; done; return 1; }
CEROS=0000000000000000000000000000000000000000
while read -r _local local_sha remote_ref remote_sha; do
  rama="${remote_ref#refs/heads/}"
  es_protegida "$rama" || continue
  # Única excepción (si el repo la activa): fast-forward REAL de origin/develop|dev a main:
  # lo que se empuja es exactamente la base recién traída y main remoto es su ancestro.
  if [ "$VP_PROMOCION_FF" = 1 ] && { [ "$rama" = main ] || [ "$rama" = master ]; }; then
    for b in develop dev; do
      git fetch -q origin "$b" 2>/dev/null || continue
      if [ "$local_sha" = "$(git rev-parse -q --verify "refs/remotes/origin/$b")" ] \
         && [ "$remote_sha" != "$CEROS" ] \
         && git merge-base --is-ancestor "$remote_sha" "$local_sha" 2>/dev/null; then
        echo "validar-pr: promoción por fast-forward de origin/$b a $rama: permitida." >&2
        continue 2
      fi
    done
  fi
  echo "✗ validar-pr: prohibido empujar directo a '$rama'. Solo por PR desde una rama feature." >&2
  exit 1
done
exit 0
