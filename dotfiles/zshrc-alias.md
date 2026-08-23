# Aliases permanentes para `.zshrc`

## `kuraka-update` — actualizar el framework en el proyecto actual (recomendado)

Actualiza SOLO la capa de framework (agentes con capacidades de harness, skills
`SKILL.md`, hooks, rules, contexts, stack-profiles, templates, tests/kuraka)
desde el vault, re-aplica tus overrides y **jamás toca el historial del
proyecto** (`docs/process/**`, checkpoints, `.claude/project/`,
`kuraka.config.yaml`). No interactivo. Después: `/exit` + sesión nueva.

**Consciente de plataforma**: detecta automáticamente qué plataforma(s) están
montadas en el proyecto (`.claude` / `.agents` / `.codex` / `.cursor`) y
refresca CADA una con su propio render — el material solo-Claude (frontmatter
de harness, hooks, claves de invocabilidad) nunca llega a
Antigravity/Codex/Cursor, y viceversa. Se niega a estrenar una plataforma no
montada (para eso está el mount completo).

```bash
cat >> ~/.zshrc << 'EOF'
# Kuraka — framework-only update en el proyecto actual (historial intacto)
alias kuraka-update='bash "${KURAKA_VAULT:-/Users/xmn/Documents/Agentes/AgentesTrabajos/kuraka}/mount-kuraka.sh" "$PWD" --update'
EOF
source ~/.zshrc
```

---

# Alias permanente `claude-sync` para `.zshrc`

Este alias te permite restaurar `.claude/` y `scripts/sync-obsidian.sh` desde el vault
Obsidian con un solo comando (`claude-sync`) desde cualquier proyecto, sin tener que
pegar el comando completo cada vez.

**Incluye conversión automática de wikilinks `[[name]]` (formato Obsidian) a
backticks `` `name` `` (formato Claude Code)** en agents, contexts, skills y rules.
Commands se copian verbatim (no deben convertirse).

---

## 📦 Instalación (una sola vez)

Copia y pega este bloque completo en la terminal:

```bash
cat >> ~/.zshrc << 'EOF'

# ========================================
# Claude Code - Restaurar .claude/ y scripts/ desde Obsidian vault
# ========================================
# Uso: desde la raíz de cualquier proyecto, ejecutar: claude-sync
# Convierte [[wikilinks]] de Obsidian a `backticks` para Claude Code
claude-sync() {
  local VAULT=${KURAKA_VAULT:-/Users/xmn/Documents/Agentes/AgentesTrabajos/kuraka}
  mkdir -p .claude/agents/contexts .claude/skills .claude/commands .claude/rules scripts
  cp "$VAULT"/agents/*.md .claude/agents/ 2>/dev/null
  cp "$VAULT"/agents/contexts/*.md .claude/agents/contexts/ 2>/dev/null
  cp "$VAULT"/skills/*.md .claude/skills/ 2>/dev/null
  cp "$VAULT"/commands/*.md .claude/commands/ 2>/dev/null
  cp "$VAULT"/rules/*.md .claude/rules/ 2>/dev/null
  cp "$VAULT"/scripts/sync-obsidian.sh scripts/ 2>/dev/null && chmod +x scripts/sync-obsidian.sh
  # Revert [[wikilinks]] to `backticks` (except in commands/)
  for dir in .claude/agents .claude/agents/contexts .claude/skills .claude/rules; do
    for file in "$dir"/*.md; do
      [ -f "$file" ] || continue
      sed -i.bak 's/\[\[\([a-z][a-z0-9-]*\)\]\]/`\1`/g' "$file" && rm "${file}.bak"
    done
  done
  echo "Restaurado: $(ls .claude/agents/*.md 2>/dev/null | wc -l) agentes, $(ls .claude/skills/*.md 2>/dev/null | wc -l) skills, $(ls .claude/commands/*.md 2>/dev/null | wc -l) commands, $(ls .claude/rules/*.md 2>/dev/null | wc -l) rules, $([ -x scripts/sync-obsidian.sh ] && echo sync-obsidian.sh-OK || echo sync-obsidian.sh-MISSING)"
}

EOF
source ~/.zshrc
echo "✅ Función claude-sync instalada. Ahora puedes usarla desde cualquier proyecto."
```

---

## 🚀 Uso después de instalar

Desde la raíz de cualquier proyecto:

```bash
claude-sync
```

Salida esperada:

```
Restaurado: 13 agentes, 21 skills, 4 commands, 16 rules, sync-obsidian.sh-OK
```

---

## 🔄 En una máquina nueva

Si reinstalas macOS o cambias de máquina:

1. Clona el vault: `git clone` (si lo tienes en git) o copia la carpeta
2. Si el path cambió: exportá `KURAKA_VAULT` en tu `~/.zshrc`, p.ej.
   `export KURAKA_VAULT="$HOME/.kuraka"`. La función lee esa variable
   antes de caer al default hardcoded.
3. Ejecuta el bloque de instalación de arriba

---

## 🧹 Desinstalar

Si quieres quitarlo del `.zshrc`:

```bash
sed -i '' '/# Claude Code - Restaurar \.claude\/ y scripts\/ desde Obsidian vault/,/^}$/d' ~/.zshrc
source ~/.zshrc
```

---

## 📝 Notas

- Cambié `alias` por `function` porque el script interno requiere múltiples comandos y lógica de for-loops
- Las funciones en zsh se comportan exactamente igual al llamarlas desde la terminal
- `2>/dev/null` suprime errores si alguna carpeta del vault está vacía
- `chmod +x` al final asegura que el script sea ejecutable tras la restauración
- **Conversión inversa automática**: `[[architect-reviewer]]` → `` `architect-reviewer` `` (solo en agents/contexts/skills/rules)
- Los `commands/` se copian verbatim porque sus prompts ejecutables usan backticks intencionalmente
- Si usas bash en vez de zsh, cambia `~/.zshrc` por `~/.bashrc` en los comandos

---

## 🗂 Qué restaura la función

| Carpeta/Archivo local | Origen en el vault | Conversión |
|-----------------------|-------------------|-----------|
| `.claude/agents/*.md` | `agents/` | `[[name]]` → `` `name` `` |
| `.claude/agents/contexts/*.md` | `agents/contexts/` | `[[name]]` → `` `name` `` |
| `.claude/skills/*.md` | `skills/` | `[[name]]` → `` `name` `` |
| `.claude/commands/*.md` | `commands/` | Verbatim |
| `.claude/rules/*.md` | `rules/` | `[[name]]` → `` `name` `` |
| `scripts/sync-obsidian.sh` | `scripts/` | Verbatim + `chmod +x` |
