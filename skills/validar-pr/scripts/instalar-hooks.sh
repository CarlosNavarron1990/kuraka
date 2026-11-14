#!/usr/bin/env bash
# Deja activo el pre-push de validar-pr (validar-push.sh: nada directo a ramas protegidas) en
# este clon. Idempotente y NO destructivo: nunca pisa un hook ajeno.
#   bash .claude/skills/validar-pr/scripts/instalar-hooks.sh
# Tres casos, en este orden:
#   1. El repo versiona sus hooks en .githooks/ → core.hooksPath=.githooks (el pre-push del
#      repo es quien llama a validar-push.sh).
#   2. El repo usa husky y su pre-push lleva la marca «validar-pr» → core.hooksPath a husky.
#   3. Ninguno de los dos y sin core.hooksPath propio → .git/hooks/pre-push mínimo (marcado
#      «validar-pr») que llama a validar-push.sh. Si ya existe un pre-push ajeno, solo avisa.
set -uo pipefail
# Nunca desde el revisor autónomo ni desde la copia temporal de una validación: la
# configuración de git es COMPARTIDA con el clon del dev y no se le cambia por la espalda.
[ -n "${VALIDAR_PR_DENTRO:-}" ] && exit 0
case "$(pwd -P)" in */validar-pr-wt-*) exit 0 ;; esac
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RAIZ="$(git rev-parse --show-toplevel 2>/dev/null)" || exit 0
cd "$RAIZ"
actual="$(git config --get core.hooksPath || true)"

if [ -f .githooks/pre-push ] || [ -f .githooks/pre-commit ]; then
  [ "$actual" = ".githooks" ] || git config core.hooksPath .githooks
  chmod +x .githooks/* 2>/dev/null || true
  exit 0
fi

for d in .husky */.husky; do
  [ -f "$d/pre-push" ] && grep -q validar-pr "$d/pre-push" || continue
  chmod +x "$d/pre-push" "$d/pre-commit" 2>/dev/null || true
  if [ -f "$d/_/husky.sh" ] || [ -f "$d/_/h" ]; then
    [ "$actual" = "$d/_" ] || git config core.hooksPath "$d/_"
  else
    [ "$actual" = "$d" ] || git config core.hooksPath "$d"
  fi
  exit 0
done

if [ -n "$actual" ]; then
  echo "[validar-pr] core.hooksPath=$actual es del repo: añade a su pre-push la línea" >&2
  echo "             bash .claude/skills/validar-pr/scripts/validar-push.sh" >&2
  exit 0
fi
HOOK="$(git rev-parse --git-common-dir)/hooks/pre-push"
case "$HOOK" in /* | [A-Za-z]:[/\\]*) ;; *) HOOK="$RAIZ/$HOOK" ;; esac
if [ -f "$HOOK" ] && ! grep -q validar-pr "$HOOK"; then
  echo "[validar-pr] Ya hay un pre-push propio en $HOOK: no se toca. Añádele" >&2
  echo "             bash .claude/skills/validar-pr/scripts/validar-push.sh" >&2
  exit 0
fi
mkdir -p "$(dirname "$HOOK")"
cat > "$HOOK" <<'EOF'
#!/usr/bin/env bash
# validar-pr (Kuraka): nada directo a ramas protegidas. Instalado por instalar-hooks.sh.
R="$(git rev-parse --show-toplevel)"
S="$R/.claude/skills/validar-pr/scripts/validar-push.sh"
[ -f "$S" ] || exit 0
exec bash "$S" "$@"
EOF
chmod +x "$HOOK"
exit 0
