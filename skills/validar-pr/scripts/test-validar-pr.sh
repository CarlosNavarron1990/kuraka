#!/usr/bin/env bash
# Batería de las piezas COMUNES que hacen cumplir validar-pr (sin Docker ni red):
#   bash .claude/skills/validar-pr/scripts/test-validar-pr.sh
# - hook de Claude (test-hook-claude.sh → pr_gate.py)   - pre-push (validar-push.sh)
# - secretos (vp_secretos_diff)  - veredicto (vp_veredicto)  - qué corre según lo tocado
# - reserva de modelo y modelo según el plan montado  - guardas de stack.sh y git-ro.sh
# - rutas Windows / Git Bash
# validar-pr.sh la ejecuta cuando la PR toca la herramienta o su config. Las comprobaciones
# PROPIAS de un repo (normativas, versión de un linter…) van en su capa, no aquí.
set -uo pipefail
# Dentro de un hook de git llegan GIT_DIR, GIT_INDEX_FILE, GIT_CONFIG_PARAMETERS…: sin
# quitarlos, los git init/commit de prueba actuarían sobre el repo REAL. Se limpian todos.
for v in $(git rev-parse --local-env-vars 2>/dev/null) GIT_CONFIG_PARAMETERS GIT_CONFIG_COUNT GIT_EXEC_PATH; do unset "$v"; done
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
# En Git Bash, comun.sh deja TMPDIR en C:/...: $TMP/bin va en el PATH, así que en formato /c/...
command -v cygpath >/dev/null 2>&1 && TMP="$(cygpath -u "$TMP")"
fallos=0; total=0
ok() { total=$((total + 1)); if [ "$1" != "$2" ]; then fallos=$((fallos + 1)); echo "✗ esperado $2, sale $1: $3"; fi; }
# Extrae del comun.sh las funciones nombradas (sin cargar config.sh ni exigir repo).
funcs() { local re; re="$(printf '^%s\\(\\)|' "$@")"; awk -v re="${re%|}" '$0 ~ re {p=1} p{print} p&&/^}$/{p=0}' "$DIR/comun.sh"; }

echo "· hook de Claude (pr_gate.py)"
if [ -f "${PR_GATE:-$DIR/../../../hooks/pr_gate.py}" ]; then
  bash "$DIR/test-hook-claude.sh" | tail -1; ok "${PIPESTATUS[0]}" 0 "test-hook-claude.sh"
else
  echo "  (sin pr_gate.py montado: se omite)"
fi

funcs vp_secretos_diff vp_veredicto > "$TMP/f.sh"
vp_rojo() { :; }
# shellcheck source=/dev/null
. "$TMP/f.sh"
sec() { printf 'diff --git a/%s b/%s\n+++ b/%s\n+%s\n' "$1" "$1" "$1" "$2" | vp_secretos_diff 2>/dev/null; ok $? "$3" "secreto $1: $2"; }
echo "· secretos"
# Los secretos de prueba se arman con printf para que NO aparezcan literales en este
# fichero (si no, gitleaks y la propia regla bloquearían cualquier commit que lo toque).
s() { printf "$@"; }
sec app/config.py "$(s 'SECRET_%s = "%s"' KEY mi-secreto-hardcodeado-123)" 1
sec app/config.py "$(s 'API_%s="%s"' KEY abcdefghijkl)" 1
sec app/config.py "$(s 'aws = "%s%s"' AKIA ABCDEFGHIJKLMNOP)" 1
sec tests/test_x.py "$(s 'aws = "%s%s"' AKIA ABCDEFGHIJKLMNOP)" 1
sec app/db.py "$(s 'URL = "%s://%s:%s@db/x"' postgresql u clave1234)" 1
sec app/pay.py "$(s 'K = "%s%s"' sk_live_ abcdefghijklmnopqrstuvwx)" 1
sec tests/test_auth.py "$(s 'pass%s = "%s"' word Abc12345678)" 0
sec src/__tests__/a.spec.ts "$(s "tok%s: '%s'" en jwt-token-largo)" 0
sec app/auth.py "$(s 'TOKEN_%s = "%s"' URL https://login.microsoftonline.com/x)" 0
sec app/auth.py "$(s 'pass%s = os.environ["X"]' word)" 0
sec docs/tests/guia.md "$(s 'SECRET_%s = "%s"' KEY sigue-siendo-secreto-1)" 0
sec backend/.env.example "$(s 'aws = "%s%s"' AKIA ABCDEFGHIJKLMNOP)" 1

echo "· veredicto"
printf 'x\nVEREDICTO: OK\n\n' > "$TMP/v1"; ok "$(vp_veredicto "$TMP/v1")" OK "veredicto al final"
printf 'VEREDICTO: OK\nsigue\n' > "$TMP/v2"; ok "$(vp_veredicto "$TMP/v2")" "" "veredicto a mitad"
printf 'x\nVEREDICTO: CAMBIOS \n' > "$TMP/v3"; ok "$(vp_veredicto "$TMP/v3")" CAMBIOS "veredicto con espacio"

echo "· qué ejecuta la suite según lo que toca la PR"
funcs vp_toca vp_solo_herramientas > "$TMP/t.sh"
# shellcheck source=/dev/null
. "$TMP/t.sh"
eval "$(grep -E '^: "\$\{VP_RUTAS_SIN_SUITE:=' "$DIR/comun.sh")"
CFG=.claude/project/validar-pr/config.sh; VP_CFG_REL="$CFG"
solo_herr() { printf '%s\n' "$1" | vp_solo_herramientas && echo 1 || echo 0; }
ok "$(solo_herr $'.claude/skills/validar-pr/SKILL.md\ndocs/a.md')" 1 "solo herramientas y docs: sin suite"
ok "$(solo_herr $'.claude/rules/x.md\nbackend/app.py')" 0 "herramientas + backend: con suite"
ok "$(solo_herr $'.github/workflows/ci.yml')" 0 "cambiar ci.yml pide suite"
ok "$(solo_herr "$CFG"$'\n.claude/x.md')" 0 "cambiar config.sh de la capa pide la suite"
ok "$( VP_TOCADOS=$'frontend/src/a.ts'; export VP_TOCADOS; vp_toca '^backend/' && echo 1 || echo 0)" 0 "PR de frontend: no toca backend"
ok "$( VP_TOCADOS=$'frontend/src/a.ts'; export VP_TOCADOS; vp_toca '^frontend/' && echo 1 || echo 0)" 1 "PR de frontend: toca frontend"
ok "$( unset VP_TOCADOS; vp_toca '^backend/' && echo 1 || echo 0)" 1 "suite a mano (sin lista): todo"
# El bloque real de validar-pr.sh que decide qué se ejecuta, bajo set -euo pipefail, con una
# suite falsa (devuelve RC_FALSO y anota si la llamaron con la lista de tocados o entera) y una
# batería falsa (anota que corrió). Comprueba el resultado de punta a punta, no funciones sueltas.
sed -n '/^# >>> estado-suite/,/^# <<< estado-suite/p' "$DIR/validar-pr.sh" > "$TMP/estado.sh"
mkdir -p "$TMP/vpdir/scripts"; printf 'echo bateria >> "%s/rastro"\n' "$TMP" > "$TMP/vpdir/scripts/test-validar-pr.sh"
estado() { : > "$TMP/rastro"; ( set -euo pipefail
  RC_FALSO="$1"; VP_TOCADOS="$2"; export VP_TOCADOS
  vp_suite_oficial() { if [ -n "${VP_TOCADOS+x}" ]; then echo suite:parcial; else echo suite:entera; fi >> "$TMP/rastro"; return "$RC_FALSO"; }
  vp_info() { :; }; LOG=/dev/null; PROY=x; VP_RAMA_BASE=dev; VP_DIR="$TMP/vpdir"; FALLOS=(""); VP_CFG_REL="$CFG"
  SOLO_HERRAMIENTAS=0; printf '%s\n' "$VP_TOCADOS" | vp_solo_herramientas && SOLO_HERRAMIENTAS=1
  # shellcheck source=/dev/null
  . "$TMP/estado.sh"
  echo "${SUITE%%;*}|$((${#FALLOS[@]} - 1))|$(tr '\n' ' ' < "$TMP/rastro" | sed 's/ $//')" ) 2>/dev/null || echo "cortado"; }
ok "$(estado 0 'backend/a.py')" "OK|0|suite:parcial" "PR de backend en verde"
ok "$(estado 1 'backend/a.py')" "ROJO|1|suite:parcial" "suite en rojo: anota el fallo y sigue"
ok "$(estado 10 'scripts/x.sh')" "no aplica (la PR no toca backend ni frontend)|0|suite:parcial" "suite que no aplica: no corta"
ok "$(estado 0 $'.claude/skills/validar-pr/SKILL.md\ndocs/a.md')" "no aplica (solo herramientas/docs)|0|bateria" "solo herramientas: batería, sin suite"
ok "$(estado 0 "$CFG"$'\nbackend/a.py')" "OK|0|suite:entera bateria" "cambia config.sh de la capa: suite ENTERA y batería"
ok "$(estado 0 $'backend/a.py\n.claude/skills/validar-pr/scripts/comun.sh')" "OK|0|suite:parcial bateria" "código + herramienta: suite y batería"

echo "· modelo del revisor según el plan montado"
sed -n '/^vp_modelo_del_plan()/,/^unset _vp_m _vp_r/p' "$DIR/comun.sh" > "$TMP/plan.sh"
plan() { # $1 = frontier del manifest ('' = sin manifest); imprime "modelo reserva"
  rm -rf "$TMP/pl"; mkdir -p "$TMP/pl/.claude"
  [ -n "$1" ] && printf '{\n "claude_plan": "x",\n "claude_plan_models": {\n  "balanced": "sonnet",\n  "fast": "haiku",\n  "frontier": "%s",\n  "heavy": "opus"\n }\n}\n' "$1" > "$TMP/pl/.claude/.kuraka-mount-manifest.json"
  ( unset VALIDAR_PR_MODELO VALIDAR_PR_MODELO_RESERVA; VP_RAIZ="$TMP/pl"
    # shellcheck source=/dev/null
    . "$TMP/plan.sh"; echo "$VP_MODELO $VP_MODELO_RESERVA" ); }
ok "$(plan fable)" "fable opus" "plan max: fable, reserva opus"
ok "$(plan sonnet)" "sonnet haiku" "plan pro/team: sonnet, sin fable"
ok "$(plan '')" "opus sonnet" "sin manifest: opus/sonnet"
ok "$(VALIDAR_PR_MODELO=x; export VALIDAR_PR_MODELO; VP_RAIZ="$TMP/pl"; . "$TMP/plan.sh"; echo "$VP_MODELO")" x "el entorno manda"

echo "· reserva de modelo (claude falso)"
funcs vp_modelo vp_requiere_claude > "$TMP/m.sh"
vp_info() { :; }
# shellcheck source=/dev/null
. "$TMP/m.sh"
mkdir -p "$TMP/bin"
cat > "$TMP/bin/claude" <<'FALSO'
#!/usr/bin/env bash
m=""; while [ $# -gt 0 ]; do [ "$1" = --model ] && m="$2"; shift; done
echo "$m" >> "$CLAUDE_FALSO_LOG"
case "$m:$CLAUDE_FALSO_MODO" in
  principal:sin-saldo) echo "You're out of usage credits."; exit 1 ;;
  principal:sin-turnos) echo 'Error: Reached max turns (2)'; exit 1 ;;
  *) printf 'revisado\nVEREDICTO: OK\n' ;;
esac
FALSO
chmod +x "$TMP/bin/claude"
modelo_con() { : > "$TMP/log"; echo p > "$TMP/p"
  ( PATH="$TMP/bin:$PATH" CLAUDE_FALSO_LOG="$TMP/log" CLAUDE_FALSO_MODO="$1" VP_MODELO=principal VP_MODELO_RESERVA=reserva \
    vp_modelo "$TMP/p" "$TMP/s" Read 2 >/dev/null 2>&1 ); }
modelo_con sin-saldo; ok "$(tr '\n' ' ' < "$TMP/log")" "principal reserva " "sin saldo: entra la reserva"
ok "$(cat "$TMP/s.modelo")" reserva "sin saldo: la revisión es de la reserva"
modelo_con sin-turnos; ok "$(tr '\n' ' ' < "$TMP/log")" "principal " "sin turnos: no se paga dos veces"
ok "$(vp_veredicto "$TMP/s")" CAMBIOS "sin turnos: se da por CAMBIOS"

echo "· pre-push (validar-push.sh)"
# Copia la herramienta dentro de un repo de prueba con su capa: validar-push.sh lee la capa
# relativa a su propia ubicación (<plataforma>/skills/validar-pr/scripts → <plataforma>/project).
( set -e; cd "$TMP"; git init -q --bare r.git; git init -q -b develop c; cd c
  g() { GIT_CONFIG_GLOBAL=/dev/null git -c user.email=t@t -c user.name=t -c commit.gpgsign=false "$@"; }
  mkdir -p .claude/skills/validar-pr/scripts .claude/project/validar-pr
  cp "$DIR/validar-push.sh" .claude/skills/validar-pr/scripts/
  g commit -q --allow-empty -m a; git remote add origin ../r.git
  git push -q origin develop HEAD:main 2>/dev/null; g commit -q --allow-empty -m b; git push -q origin develop 2>/dev/null; git fetch -q origin ) \
  || { echo "no se pudo preparar el repo de pruebas"; exit 1; }
cd "$TMP/c"
case "$(git rev-parse --absolute-git-dir)" in "$(cd "$TMP/c" && { pwd -W 2>/dev/null || pwd -P; })"/.git) ;; *) echo "ABORTO: el repo de pruebas no está en $TMP"; exit 1 ;; esac
A="$(git rev-parse HEAD~1)"; B="$(git rev-parse HEAD)"; Z=0000000000000000000000000000000000000000
VPUSH="$TMP/c/.claude/skills/validar-pr/scripts/validar-push.sh"
push() { echo "refs/heads/x $1 refs/heads/$2 $3" | bash "$VPUSH" >/dev/null 2>&1; ok $? "$4" "push $2 ($5)"; }
push "$B" feat/x "$A" 0 "rama feature"
push "$B" develop "$A" 1 "develop"
push "$B" dev "$A" 1 "dev"
push "$B" release "$A" 1 "release"
push "$Z" develop "$A" 1 "borrar develop"
push "$B" main "$A" 1 "ff sin VP_PROMOCION_FF"
echo "VP_PROMOCION_FF=1" > .claude/project/validar-pr/config.sh
push "$B" main "$A" 0 "ff real con VP_PROMOCION_FF=1"
push "$A" main "$B" 1 "no es origin/develop"
push "$B" main "$Z" 1 "main nueva"
printf 'VP_RAMAS_PROTEGIDAS="main qa"\n' > .claude/project/validar-pr/config.sh
push "$B" qa "$A" 1 "rama protegida propia del repo (qa)"
push "$B" develop "$A" 0 "develop no protegida en este repo"
cd "$DIR"

echo "· instalar-hooks.sh no pisa un pre-push ajeno"
( set -e; cd "$TMP"; rm -rf h; git init -q h; cd h
  mkdir -p .claude/skills/validar-pr/scripts; cp "$DIR/instalar-hooks.sh" "$DIR/validar-push.sh" .claude/skills/validar-pr/scripts/
  bash .claude/skills/validar-pr/scripts/instalar-hooks.sh 2>/dev/null
  grep -q validar-pr .git/hooks/pre-push && echo propio > ../h_ok
  printf '#!/bin/sh\necho ajeno\n' > .git/hooks/pre-push
  bash .claude/skills/validar-pr/scripts/instalar-hooks.sh 2>/dev/null
  grep -q ajeno .git/hooks/pre-push && echo intacto > ../h_ajeno
  VALIDAR_PR_DENTRO=1 git config core.hooksPath x; ) 2>/dev/null
ok "$(cat "$TMP/h_ok" 2>/dev/null)" propio "instala un pre-push mínimo marcado"
ok "$(cat "$TMP/h_ajeno" 2>/dev/null)" intacto "no pisa un pre-push ajeno"

echo "· dependencias de la copia aislada"
funcs vp_deps_worktree vp_deps_workspaces > "$TMP/d.sh"
# shellcheck source=/dev/null
. "$TMP/d.sh"
deps_caso() { # $1 = nombre; $2 = locks del repo (relativos, uno por línea); crea origen y copia
  local base="$TMP/deps-$1" l
  mkdir -p "$base/origen/node_modules/x" "$base/origen/pkg/node_modules/.bin" "$base/wt/pkg"
  : > "$base/origen/pkg/node_modules/.bin/prettier"; : > "$base/wt/pkg/package.json"
  while IFS= read -r l; do
    mkdir -p "$base/origen/$(dirname "$l")/node_modules/y" "$base/wt/$(dirname "$l")"
    echo lock > "$base/origen/$l"; echo lock > "$base/wt/$l"
  done <<< "$2"
  ( cd "$base/wt" && git init -q . && git add -A && vp_deps_worktree "$base/origen" >/dev/null 2>&1; echo $? )
}
ok "$(deps_caso raiz $'package-lock.json\ninfra/cdk/package-lock.json')" 0 "workspaces: la copia termina bien"
ok "$( [ -d "$TMP/deps-raiz/wt/infra/cdk/node_modules/y" ] && echo 1 || echo 0)" 1 "workspaces: el lock propio de infra/cdk sigue el suyo"
ok "$(deps_caso ultimo $'web/package-lock.json')" 0 "el último lock no es la raíz: no devuelve error"

echo "· guardas de stack.sh y git-ro.sh"
bash "$DIR/stack.sh" abajo mi_proyecto >/dev/null 2>&1; ok $? 64 "stack.sh con proyecto del dev"
bash "$DIR/stack.sh" url mi_proyecto >/dev/null 2>&1; ok $? 64 "stack.sh url con proyecto del dev"
bash "$DIR/stack.sh" dc vpx -p otro ps >/dev/null 2>&1; ok $? 64 "stack.sh dc con -p"
bash "$DIR/stack.sh" dc vpx down -v >/dev/null 2>&1; ok $? 64 "stack.sh dc down"
bash "$DIR/stack.sh" http vpx GET http://evil.com >/dev/null 2>&1; ok $? 64 "stack.sh http con URL"
bash "$DIR/git-ro.sh" grep -O x y >/dev/null 2>&1; ok $? 64 "git-ro grep"
bash "$DIR/git-ro.sh" diff --output=/tmp/x >/dev/null 2>&1; ok $? 64 "git-ro --output"
bash "$DIR/git-ro.sh" log -c core.pager=x >/dev/null 2>&1; ok $? 64 "git-ro -c"

echo "· rutas absolutas (Windows devuelve C:/...)"
grep -E '^vp_es_ruta_absoluta\(\)' "$DIR/comun.sh" > "$TMP/r.sh"
# shellcheck source=/dev/null
. "$TMP/r.sh"
for r in /home/x/.git C:/Users/x/.git 'C:\Users\x\.git' d:/repo/.git; do vp_es_ruta_absoluta "$r"; ok $? 0 "absoluta: $r"; done
for r in .git ../repo/.git c:x; do vp_es_ruta_absoluta "$r"; ok $? 1 "relativa: $r"; done

echo "· Git Bash: TMPDIR en C:/ para Docker y rutas del PATH en /c/ (cygpath falso)"
mkdir -p "$TMP/cyg"
cat >"$TMP/cyg/cygpath" <<'EOF'
#!/usr/bin/env bash
case "$1" in
  -m) case "$2" in /tmp*) echo "C:/Temp${2#/tmp}" ;; *) echo "$2" ;; esac ;;
  -u) case "$2" in C:/*) echo "/c/${2#C:/}" ;; *) echo "$2" ;; esac ;;
esac
EOF
chmod +x "$TMP/cyg/cygpath"
BLOQUE="$(sed -n '/^if command -v cygpath/,/^fi$/p' "$DIR/comun.sh"; grep -E '^vp_ruta_posix\(\)' "$DIR/comun.sh")"
r="$(PATH="$TMP/cyg:$PATH" TMPDIR=/tmp bash -c "$BLOQUE"'
echo "$TMPDIR"')"; ok "$r" "C:/Temp" "TMPDIR pasa a ruta Windows"
r="$(PATH="$TMP/cyg:$PATH" TMPDIR=/tmp bash -c "$BLOQUE
$BLOQUE"'
echo "$TMPDIR"')"; ok "$r" "C:/Temp" "conversión idempotente (comun.sh cargado dos veces)"
r="$(PATH="$TMP/cyg:$PATH" bash -c "$BLOQUE"'
vp_ruta_posix C:/Temp/venv/Scripts')"; ok "$r" "/c/Temp/venv/Scripts" "ruta para el PATH en formato Git Bash"

echo "$((total - fallos))/$total comprobaciones OK"
[ "$fallos" -eq 0 ]
