---
name: llimpi
description: "Greenfield step between /arki and the first /kuraka cycle (Quechua llimpi = color, to paint). Turns the approved discovery + architecture into (1) a prototype of every screen grouped by user type and flow, each with its use-case card (use case · flow · options/states); (2) the design registration (path + frame index + tokens) in the project layer's conventions/frontend-branding.md; (3) the closed list of decisions the prototype assumed; and (4) the development plan docs/plan/vN/ — one checkbox .md per /kuraka cycle with a ready-to-paste prompt and an R-DERIVA coverage table verified by script. Optional: Pencil high-fidelity file, navigable viewer, client PDF. Orchestrator-run; ends at a user approval gate."
disable-model-invocation: true
user-invocable: false
---

# llimpi — prototipo, casos de uso y plan de ciclos

> Adoptada en el harvest 2026-11 desde editorialcesarvallejo. Tras `/arki`, el proyecto tenía
> arquitectura y esqueleto pero nada que mostrar al cliente ni una secuencia de trabajo para
> Kuraka; el prototipo, sus fichas y el plan por ciclos se hicieron a mano. Esta skill
> convierte ese recorrido en un paso del framework: **inti → arki → llimpi → kuraka**.
>
> La invoca el comando `/llimpi` (la skill no se registra: el comando es la entrada). La
> ejecuta el ORQUESTADOR — un subagente no puede publicar artefactos ni usar el MCP de diseño.

## Qué es obligatorio y qué es opcional

| Obligatorio (sin esto no hay gate) | Opcional (según proyecto y herramienta) |
|---|---|
| Inventario de pantallas con código estable, confirmado por el usuario | Prototipo de alta fidelidad en Pencil (`.pen`) |
| Ficha de caso de uso por pantalla | Visor HTML navegable |
| Registro del diseño + frame index en `conventions/frontend-branding.md` | PDF para el cliente |
| Decisiones asumidas cerradas o listadas como abiertas | Flujo G transversal (alertas, cargas, avisos) — muy recomendado si hay UI |
| `docs/plan/vN/` con roadmap, tabla de cobertura verificada por script y un `.md` por ciclo con prompt listo | Cotización al inicio del PDF |

## Cuándo correr

- Proyecto greenfield con `docs/discovery/` aprobado y `/arki` cerrado (existe `kuraka.config.yaml`).
- Antes del primer `/kuraka`. Se puede re-correr para una versión nueva (`docs/plan/v2/`).
- No aplica a brownfield (allí el diseño se registra con `amauta`). Un proyecto sin interfaz
  de usuario puede saltarla si el usuario lo decide — el plan de ciclos sigue siendo útil:
  en ese caso hacé solo el Paso 6 sobre los RN/casos de uso.

## Entradas (leer, no re-derivar)

- `docs/discovery/vision.md`, `requirements.md` (actores, recorridos, reglas RN-n, decisiones
  U-n, preguntas P-n abiertas).
- `docs/arquitectura/` (ADRs, modelo de dominio, modelo de seguridad).
- La capa del proyecto: `conventions/` (rbac, branding, naming, api-design).
- Restricciones comerciales si existen (cotización, plazo, horas).

## Paso 0 — Herramienta de diseño

1. **Pencil MCP conectado**: pedir al usuario que **guarde el `.pen` dentro del repo**
   (`docs/prototipo/<proyecto>.pen`) antes de diseñar. Un `.pen` sin guardar o fuera del repo
   se pierde; uno guardado sin extensión `.pen` deja de acomodar los elementos nuevos. Cargar
   el esquema y las guías de Pencil una sola vez.
2. **Sin Pencil**: prototipo en HTML (publicado como Artifact si la sesión lo permite, o
   `docs/prototipo/index.html`), mismas fichas y mismos códigos.

## Paso 1 — Inventario de pantallas (antes de dibujar)

Desde los recorridos de `requirements.md`, armar la lista de pantallas **por tipo de usuario y
flujo**, con código estable (A-1, B-3…):

| Flujo | Contenido típico |
|---|---|
| A · Acceso (todos) | login con errores y bloqueo, recuperar contraseña, primer ingreso, cuenta suspendida, sesión cerrada |
| B..n · un flujo por tipo de usuario | inicio, listas, detalle, altas, asignaciones, la pantalla núcleo del producto |
| Admin / control | usuarios, actividad, roles y permisos, configuración |
| G · Alertas, cargas y avisos (transversal, recomendado) | modales (confirmación, éxito, error, con motivo), cargas (esqueletos, botón cargando, progreso), avisos breves, banners, errores de formulario, estados vacíos |

Presentar el inventario al usuario y **confirmar antes de diseñar**.

## Paso 2 — Diseñar

- **Componentes primero** (shell de cada portal, layout de acceso, campo, botones, etiqueta de
  estado); las pantallas son instancias.
- **Tokens** de diseño (tinta, superficie, acento, estados, fuentes) definidos una vez.
- **Ficha sobre cada pantalla**: código, nombre, *Caso de uso*, *Flujo* (de dónde llega → a
  dónde va, con códigos) y *Opciones* (acciones, errores, estados vacíos, confirmaciones).
- **Datos de ejemplo coherentes** entre pantallas (mismas personas, fechas, entidades).
- **Una sección por vez**, verificando cada pantalla (sin problemas reportados por la
  herramienta, una captura). Nunca dejar una pantalla con placeholder.
- Íconos solo de nombres verificados en la librería usada.
- Al final: sin raíces solapadas y ninguna ficha tapa su pantalla.

## Paso 3 — Exportar y publicar (opcional)

1. Exportar cada pantalla a `docs/prototipo/pantallas/<código>-<slug>.png`.
2. Visor HTML navegable: índice por flujo, imagen, ficha con códigos enlazados,
   anterior/siguiente, `#código` por pantalla. Las fichas se EXTRAEN del archivo de diseño, no
   se reescriben a mano.
3. PDF para el cliente: portada, portada por tipo de usuario, una página por pantalla con su
   ficha, pie con sección y «Página N de M». Verificar con `pdftotext` que cada página tiene su
   número correcto (una página partida rompe la cuenta).

## Paso 4 — Registrar el diseño (obligatorio)

Actualizar `conventions/frontend-branding.md` de la capa del proyecto: ruta del archivo de
diseño, cómo leerlo (con el MCP de diseño, nunca con `Read`/`Grep` sobre un `.pen`; fallback a
las PNG y fichas), tabla de tokens, layout, y **frame index** (pantalla → frame id → componente
destino → versión). Sin este registro el `frontend-developer` no está obligado a respetar el
diseño. Si los tokens del código difieren, anotar que el primer ciclo de frontend los alinea.

## Paso 5 — Decisiones que el prototipo asumió (obligatorio)

Listar cada supuesto (método de login, quién suspende, umbrales…) en el índice del prototipo y
en `requirements.md`. Pedir al usuario que los cierre; registrar los cerrados como `U-n` y
marcar las `P-n` resueltas. Si el prototipo define permisos, escribir la matriz por rol en
`docs/arquitectura/` y actualizar `conventions/rbac.md`.

## Paso 6 — Plan de ciclos para Kuraka (`docs/plan/vN/`, obligatorio)

- `00-ROADMAP.md`: tabla de ciclos (orden, estimación, pantallas, estado), hitos, «cómo usar»,
  y **tabla de cobertura R-DERIVA** (`rules/19`): una fila por pantalla del prototipo + cada RN
  + cada U-n relevante, con `INCLUIDO Cnn` / `DIFERIDO <fase>` / `EXCLUIDO (decisión citada)`.
- **Verificar la cobertura con un script** (no a ojo): conteo de filas = ítems de la fuente,
  sin duplicados, todo ciclo citado tiene archivo, y un **control positivo** (un código
  inventado debe salir como faltante — `rules/19` R-CONTROL). Pegar la salida en el roadmap.
- `C00-preparacion.md` (manual): aprobación, repositorio y remoto, entorno y gate base,
  decisiones bloqueantes.
- `Cnn-<slug>.md`, uno por ciclo, **secuenciales**: objetivo, pantallas y reglas, **prompt
  listo para `/kuraka`**, tareas con casillas (backend, frontend, pruebas), criterios de
  aceptación (siempre incluyen los gates del proyecto en verde — los comandos de
  `kuraka.config.yaml` `stack.*`), y «fuera de este ciclo».
- Orden sugerido: acceso → roles y aislamiento → dominio central → pantalla núcleo (demo
  temprana) → altas y asignaciones → portales → control → pruebas de seguridad
  (`pentest-auditor`, e2e) → despliegue.
- Si una pantalla núcleo depende de datos de un ciclo posterior, diseñar un servicio con una
  implementación mínima ahora y conectar la regla real después, sin cambiar el endpoint.

## Paso 7 — Gate de aprobación

Presentar: el prototipo (enlace o ruta), el PDF si se hizo, el inventario por flujo, las
decisiones cerradas y pendientes, y el roadmap con la salida del script de cobertura.
**No marcar el proyecto listo para `/kuraka` hasta que el usuario apruebe el prototipo y el
plan.** Después: `docs/plan/vN/C00-preparacion.md` y luego `/kuraka` con el prompt de `C01`.
Al cerrar cada ciclo, el orquestador marca las casillas de su `Cnn` y el estado en el roadmap.

## Salidas

| Ruta | Contenido | |
|---|---|---|
| `docs/prototipo/` | Prototipo (`.pen` o HTML) con fichas | obligatorio |
| `conventions/frontend-branding.md` (capa) | Diseño registrado + frame index | obligatorio |
| `docs/plan/vN/` | Roadmap con cobertura verificada + un `.md` por ciclo | obligatorio |
| `docs/prototipo/pantallas/*.png`, visor, `*.pdf` | Exportaciones para el cliente | opcional |

## Antipatrones (vistos en el proyecto de origen)

- Diseñar en un archivo temporal o fuera del repo.
- Escribir fichas a mano en el PDF en vez de extraerlas del diseño (se desincronizan).
- Plan sin tabla de cobertura verificada: pantallas que nadie construye.
- Ciclos que asumen datos de un ciclo posterior sin un servicio intermedio.
- Prototipo sin el flujo G: alertas, cargas y avisos quedan al criterio de cada desarrollador.
