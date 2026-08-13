
#!/usr/bin/env bash
# install.sh — one-command Kuraka setup (clone if needed + put the CLI on PATH).
#
# Brand-new machine, ONE line:
#     curl -fsSL https://raw.githubusercontent.com/xaman1990/kuraka/main/install.sh | bash
#   (optional: choose the dir →  ... | bash -s -- ~/dev/kuraka)
#
# Or, if you already cloned the repo:
#     ~/.kuraka/install.sh
#
# It (1) clones the vault to ~/.kuraka when run via curl (skips if already there),
# (2) records KURAKA_VAULT in your shell rc, (3) puts the `kuraka` CLI on your PATH
# (~/.local/bin). Idempotent: safe to re-run (updates an existing clone with pull).

set -euo pipefail

REPO_URL="${KURAKA_REPO:-https://github.com/xaman1990/kuraka.git}"
BIN_DIR="$HOME/.local/bin"
MARKER="# >>> kuraka >>>"
END_MARKER="# <<< kuraka <<<"

# --- where is the vault? if we run from inside the clone, use it; else clone ---
_src="${BASH_SOURCE[0]:-}"
_src_dir=""
[ -n "$_src" ] && _src_dir="$(cd "$(dirname "$_src")" 2>/dev/null && pwd || true)"

if [ -n "$_src_dir" ] && [ -f "$_src_dir/kuraka-init.py" ]; then
  # running from a real clone (e.g. ~/.kuraka/install.sh)
  VAULT="$_src_dir"
  echo "🪢 Instalando Kuraka  (clon existente: $VAULT)"
else
  # piped via curl|bash (or not inside a vault) → clone it
  VAULT="${1:-${KURAKA_VAULT:-$HOME/.kuraka}}"
  echo "🪢 Instalando Kuraka  (destino: $VAULT)"
  if ! command -v git >/dev/null 2>&1; then
    echo "❌ falta git. Instalalo y reintentá (macOS: xcode-select --install)." >&2; exit 1
  fi
  if [ -d "$VAULT/.git" ]; then
    echo "   ~ ya existe un clon, actualizando…"
    git -C "$VAULT" pull --ff-only 2>/dev/null || echo "   (no se pudo hacer pull; sigo con lo que hay)"
    git -C "$VAULT" submodule update --init --recursive 2>/dev/null || true
  else
    git clone --recurse-submodules "$REPO_URL" "$VAULT"
  fi
fi
echo ""

# 1) make the CLI executable + symlink it onto PATH
chmod +x "$VAULT/kuraka" "$VAULT/mount-kuraka.sh" "$VAULT/validate-kuraka.sh" 2>/dev/null || true
mkdir -p "$BIN_DIR"
ln -sf "$VAULT/kuraka" "$BIN_DIR/kuraka" 2>/dev/null || cp -f "$VAULT/kuraka" "$BIN_DIR/kuraka"
echo "   ✓ CLI: $BIN_DIR/kuraka → $VAULT/kuraka"

# 2) write the env + PATH block into the shell rc(s), idempotently
block="$MARKER
export KURAKA_VAULT=\"$VAULT\"
case \":\$PATH:\" in *\":$BIN_DIR:\"*) ;; *) export PATH=\"$BIN_DIR:\$PATH\" ;; esac
$END_MARKER"

for rc in "$HOME/.zshrc" "$HOME/.bashrc"; do
  if [ "$rc" = "$HOME/.bashrc" ] && [ ! -f "$rc" ]; then continue; fi
  touch "$rc"
  if grep -qF "$MARKER" "$rc"; then
    tmp="$(mktemp)"
    awk -v s="$MARKER" -v e="$END_MARKER" '
      $0==s{skip=1} !skip{print} $0==e{skip=0}' "$rc" > "$tmp"
    printf '%s\n' "$block" >> "$tmp"
    mv "$tmp" "$rc"
    echo "   ~ $rc (bloque kuraka actualizado)"
  else
    printf '\n%s\n' "$block" >> "$rc"
    echo "   + $rc (KURAKA_VAULT + PATH)"
  fi
done

echo ""
echo "✅ Listo. Abrí una terminal nueva (o:  source ~/.zshrc)."
echo ""
echo "   Uso:"
echo "     cd /ruta/a/tu/solución && kuraka mount     # monta Kuraka acá"
echo "     kuraka mount /ruta/a/otra/solución          # o indicá la ruta"
echo "     kuraka doctor                               # verifica el setup"
echo ""
case "${OSTYPE:-}" in
  msys*|cygwin*|mingw*|win32*)
    echo "   ℹ️ Nota para Windows (PowerShell / CMD):"
    echo "      Para integrar Kuraka en PowerShell o CMD nativo, ejecutá:"
    echo "      powershell -ExecutionPolicy Bypass -File .\\install.ps1"
    echo ""
    ;;
esac
if ! command -v rtk >/dev/null 2>&1; then
  echo "   (recomendado) RTK para ahorrar 70–90% de tokens:"
  echo "     brew install rtk && rtk init -g"
  echo ""
fi
