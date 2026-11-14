#!/usr/bin/env bash
# git de SOLO lectura para el revisor autónomo: diff, log, show y status.
# Rechaza las opciones que ejecutan comandos o escriben ficheros (-O/--open-files-in-pager,
# --output, --ext-diff, --textconv, -c/--config-env, --exec-path) y cualquier otro subcomando.
set -euo pipefail
sub="${1:-}"; shift || true
case "$sub" in diff|log|show|status) ;; *) echo "git-ro: solo diff|log|show|status" >&2; exit 64 ;; esac
for a in "$@"; do
  case "$a" in
    -O*|--open-files-in-pager*|--output*|--ext-diff|--textconv|-c|--config-env*|--exec-path*|--upload-pack*|--paginate)
      echo "git-ro: opción no permitida: $a" >&2; exit 64 ;;
  esac
done
case "$sub" in
  diff|show|log) git --no-pager -c core.pager=cat "$sub" --no-ext-diff --no-textconv "$@" ;;
  status) git --no-pager status "$@" ;;
esac
